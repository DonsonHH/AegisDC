"""Read-only replay of an engineering example, with public and offline data apart.

The recorder runs inside the existing selector's truth-denied boundary. Physical
truth is attached only after execution, for explaining the completed episode.
No report field is fed back to selection; no learned model is called here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from .contracts import DeniedOnlineTrace
from .local_score import BASE_EXPRESSION
from .reorder_execution import choose_local, run_reorder


ROLE_NAMES = {"thermal": "热巡检", "electrical": "电气", "cooling": "液冷", "control": "自控"}


def display_array(values):
    """Plot copies need four decimals; raw completed measurements stay intact."""
    return np.round(values, 4).tolist()


def public_frame(env):
    """Copy only information already available at this decision time."""
    packet, observer = env.current_packet, env.state.observer
    known = observer.temperature_stamp >= 0
    remote = [None] * env.config.racks
    for rack, value in zip(packet["temperature_indices"], packet["temperature_c"]):
        remote[int(rack)] = round(float(value), 4)
    flow_known = observer.flow_stamp >= 0
    risk, _ = env.public_risk()
    gap = 1 - packet["public_delivered_it_kw"] / np.maximum(packet["public_requested_it_kw"], 1e-12)
    return {
        "time_s": float(env.clock),
        "remote_temperature_c": remote,
        "last_temperature_c": [round(float(v), 4) if k else None for v, k in zip(observer.last_temperature, known)],
        "temperature_age_s": [float(env.clock - s) if k else None for s, k in zip(observer.temperature_stamp, known)],
        "estimated_temperature_c": display_array(observer.predicted_temperature),
        "thermal_risk": display_array(risk[:env.config.racks]),
        "pump_command": display_array(packet["pod_pump_command"]),
        "last_flow_kg_s": [round(float(v), 4) if k else None for v, k in zip(observer.last_flow, flow_known)],
        "flow_age_s": [float(env.clock - s) if k else None for s, k in zip(observer.flow_stamp, flow_known)],
        "public_power_gap": display_array(gap.reshape(env.config.pods, 8).mean(1)),
    }


def run_observed(spec, method):
    """Use the unmodified scheduler, copying public frames before its decisions."""
    frames = []

    def select(env, selected_method, expression):
        frames.append(public_frame(env))
        return choose_local(env, selected_method, expression)

    record, env = run_reorder(spec, None, {"method": method}, selector=select)
    trace, env.trace = env.trace, DeniedOnlineTrace()
    try:
        frames.append(public_frame(env))
    finally:
        env.trace = trace
    return record, env, frames


def compact_decisions(record, tasks):
    """Retain all choices, plus their actual obligations and local predictions."""
    completions = {(e["agent"], e["round_id"], e["task"]): e["time_s"]
                   for e in record["obligation_events"]}
    rows = []
    for decision in record["local_decisions"]:
        legal = [c for c in decision["candidates"] if c["certificate"]["ok"]]
        original = next(c for c in legal if c["original"])
        selected = next(c for c in legal if list(c["order"]) == decision["selected_order"])
        # Same-state arithmetic check only: this is not another executed policy.
        without_risk = original
        cost_only = lambda c: .2 * c["features"]["deadline_pressure"] + .05 * c["features"]["travel_cost"]
        for candidate in sorted(legal, key=lambda c: (not c["original"], c["order"])):
            if cost_only(candidate) < cost_only(without_risk) - 1e-9:
                without_risk = candidate
        public = []
        for row in decision["public_tasks"]:
            item = {k: deepcopy(row[k]) for k in (
                "task", "kind", "risk", "last_check_s", "deadline_s", "source",
                "observed_value", "observed_unit", "direct_age_s", "risk_components")}
            item["task_id"] = tasks[row["task"]].task_id
            public.append(item)
        affected = []
        for row in public:
            j = row["task"]
            target_round = decision["round_id"] + int(j not in decision["remaining_before"])
            first = original["certificate"]["first_completion_s"][j]
            chosen = selected["certificate"]["first_completion_s"][j]
            if j in decision["window"] or abs(chosen - first) > 1e-9:
                affected.append({
                    "task": tasks[j].task_id, "original_prediction_s": first,
                    "selected_prediction_s": chosen,
                    "actual_completion_s": completions.get((decision["agent"], target_round, j)),
                    "delta_s": chosen - first,
                })
        rows.append({
            "time_s": decision["time_s"], "agent": decision["agent"],
            "role": tasks[decision["window"][0]].kind,
            "original": [tasks[j].task_id for j in decision["window"]],
            "selected": [tasks[j].task_id for j in decision["selected_order"]],
            "changed": not decision["selected_original"], "legal_count": len(legal),
            "public_tasks": public, "affected": affected,
            "numeric_error": decision.get("numeric_error"),
            "without_risk_order": [tasks[j].task_id for j in without_risk["order"]],
            "candidates": [{"order": [tasks[j].task_id for j in c["order"]],
                            "original": c["original"], "features": c["features"],
                            "score": c.get("score", [None])[0]} for c in legal],
        })
    return rows


def default_decision(decisions):
    """First risk-associated change, else first change, else first alternative.

    This display selection never uses task outcomes and does not select cases.
    All decisions remain available in the replay.
    """
    for predicate in (
        lambda d: d["changed"] and any(r["risk"] > 0 for r in d["public_tasks"]),
        lambda d: d["changed"], lambda d: d["legal_count"] > 1,
    ):
        for index, decision in enumerate(decisions):
            if predicate(decision):
                return index
    return 0


def collect_case(spec, progress=None):
    records, environments, methods = {}, {}, {}
    for name, method in (("tour", "T"), ("risk", "expression")):
        if progress:
            progress(name, "started")
        try:
            record, env, frames = run_observed(spec, method)
        except Exception as exc:
            if progress:
                progress(name, "failed", f"{type(exc).__name__}: {exc}")
            raise
        if progress:
            progress(name, "completed")
        records[name], environments[name] = record, env
        methods[name] = {
            "label": "固定路线" if name == "tour" else "固定公开风险规则",
            "public_frames": frames, "metrics": record["metrics"],
            "events": record["inspection_events"],
            "anomaly_intervals": record["anomaly_intervals"],
            "decisions": compact_decisions(record, env.tasks),
            "action_sha256": record["action_sha256"],
        }
        methods[name]["default_decision"] = default_decision(methods[name]["decisions"])
    env, trace = environments["tour"], environments["tour"].trace
    if records["tour"]["process"]["numeric_digest"] != records["risk"]["process"]["numeric_digest"]:
        raise ValueError("The comparison must share exactly the same physical process")
    truth = trace.arrays["rack_temperature_c"]
    focus_rack = int(np.argmax(truth.max(axis=0)))
    data = {
        "purpose": "engineering_explanation_not_research_gain", "LLM_calls": 0,
        "research_training": 0, "neural_inference": False,
        "baseline_commit": "5e406d3820526fcf11d7df5044d3641c30046119",
        "source_modules_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(Path(__file__).parent.glob("*.py"))},
        "spec": dict(spec), "role_names": ROLE_NAMES,
        "racks": env.config.racks, "inspectors": len(env.agents),
        "rule_expression": BASE_EXPRESSION,
        "risk_is_calibrated_probability": False,
        "plot_precision": "图表过程量保留4位小数；原始完成测量与排序分数未舍入。",
        "process_sha256": trace.fingerprint,
        "same_actions": records["tour"]["action_sha256"] == records["risk"]["action_sha256"],
        "focus_rack": focus_rack, "focus_pod": focus_rack // 8,
        "focus_selection": "事后选本回合最高温机柜用于讲解，不参与巡检决策；全部机柜可切换。",
        "decision_selection": "优先首个有公开风险的重排；否则首个重排，再否则首个有合法替代的决策。不是挑收益最大的案例。",
        "offline_only": {
            "label": "事后仿真真值；未传入在线选择器",
            "time_s": [float(p["time_s"]) for p in trace.packets],
            "temperature_c": display_array(truth),
            "pod_flow_kg_s": display_array(trace.arrays["rack_flow_kg_s"].reshape(360, 16, 8).sum(2)),
        },
        "methods": methods,
    }
    return data, records, environments


def render_html(data):
    # Keep user/config strings from closing a script element in a local report.
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    return HTML.replace("__CASE_DATA__", encoded)


def run_explanation(args):
    from .cli import ROOT, load_demo, save_run, write_json

    # Reuse the closed, validated example schema. This command intentionally has
    # no checkpoint argument: it explains the nominal, non-neural path only.
    from types import SimpleNamespace
    config = args.config or str(ROOT / "configs/coupled-example.json")
    spec, _, _ = load_demo(SimpleNamespace(config=config, cvae_checkpoint=None, cvae_sha256=None))
    if spec["scenario"] != "aux_feeder_loss":
        raise ValueError("explain currently describes aux_feeder_loss only; use demo for other scenarios")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"purpose": "engineering_explanation_not_research_gain", "status": "started",
               "LLM_calls": 0, "research_training": 0, "attempts": []}
    write_json(output / "attempts.json", receipt)

    def progress(name, status, error=None):
        if status == "started":
            receipt["attempts"].append({"name": name, "status": status})
        else:
            receipt["attempts"][-1]["status"] = status
        if error:
            receipt["attempts"][-1]["error"] = error
        write_json(output / "attempts.json", receipt)

    try:
        data, records, environments = collect_case(spec, progress)
        for name, record in records.items():
            save_run(output / name, record, environments[name])
        (output / "case.json").write_text(json.dumps(data, ensure_ascii=False, allow_nan=False,
                                                   separators=(",", ":")) + "\n", encoding="utf-8")
        (output / "index.html").write_text(render_html(data), encoding="utf-8")
        summary = {"purpose": receipt["purpose"], "report": str(output / "index.html"),
                   "same_actions": data["same_actions"], "LLM_calls": 0,
                   "research_status": "NOT_RUN", "methods": {
                       name: record["metrics"] for name, record in records.items()}}
        decisions = data["methods"]["risk"]["decisions"]
        summary["local_risk_effect"] = {
            "decision_points": len(decisions),
            "choices_different_without_risk_term": sum(d["selected"] != d["without_risk_order"] for d in decisions),
            "scope": "Same-state arithmetic check, not an extra executed-policy experiment",
        }
        write_json(output / "summary.json", summary)
        receipt["status"] = "completed"
        return summary
    except Exception as exc:
        receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        write_json(output / "attempts.json", receipt)


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>一个跨系统巡检案例：看到了什么，实际查了什么</title>
<style>
:root{color-scheme:light;--blue:#174b80;--ink:#1c2c3e;--muted:#53667c;--line:#dbe4ee}*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:var(--ink);font:16px/1.65 "Microsoft YaHei","Segoe UI",sans-serif}main{max-width:1220px;margin:auto;padding:32px 28px 70px}h1{font-size:29px;line-height:1.4;margin:10px 0}h2{font-size:22px;margin:0 0 12px}h3{font-size:17px;margin:10px 0}p{margin:10px 0}.muted,small{color:var(--muted)}.tag{display:inline-block;border-radius:5px;background:#e4edf9;color:var(--blue);padding:3px 9px;font-size:13px}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:20px 0}.notice{border-left:4px solid #d98a15;background:#fff8e9;padding:12px 16px}.chain{display:flex;align-items:stretch;gap:12px;margin:18px 0}.chain>div{flex:1;border:1px solid var(--line);padding:15px;border-radius:8px}.arrow{align-self:center;font-size:24px;color:var(--blue)}.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap}select,button{font:inherit;border:1px solid #b8c9db;border-radius:6px;background:white;color:var(--ink);padding:6px 9px}input[type=range]{accent-color:var(--blue);flex:1;min-width:150px}button{cursor:pointer}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #699adb;outline-offset:3px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.map{width:100%;display:block}.legend{font-size:13px;color:var(--muted)}.swatch{display:inline-block;width:90px;height:9px;background:linear-gradient(90deg,#e9f2fb,#d74636);margin:0 7px}.truth{border-top:3px solid #cc6639}.charts svg{display:block;width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f3f6fa}td.number{text-align:right;font-variant-numeric:tabular-nums}.table-scroll{overflow-x:auto}.selected{background:#eaf3ff}.key{color:var(--blue);font-weight:700}a{color:#174b80}code{font:13px/1.5 Consolas,monospace;overflow-wrap:anywhere}.empty{color:var(--muted);padding:12px}#decisionSelect{max-width:100%}noscript{display:block;background:#fff0ce;padding:15px}@media(max-width:760px){main{padding:18px 12px}.grid{grid-template-columns:1fr}.chain{flex-direction:column}.arrow{transform:rotate(90deg)}h1{font-size:25px}.panel{padding:16px}}
</style></head><body><main>
<span class="tag">新 main 的工程讲解 · 无模型调用 · 无神经训练</span>
<h1>水泵供电出了问题，巡检系统实际做了什么？</h1>
<p>先看懂一个案例：机房如何变化 → 巡检系统知道多少 → 谁完成了检查 → 换顺序是否有帮助。</p>
<div class="notice"><b>本页是整回合结束后的回看。</b>右侧真值和故障设定用于解释，在线策略看不到它们。这里比较固定路线与一条人工公开风险规则，尚未检验 AI 或 RSI 收益。</div>
<p id="quickResult" class="key"></p>
<section class="panel"><h2>1. 要验证的想法</h2>
<p>不同系统相互影响，因此一次专业检查的信息，可能帮助安排其他检查。这个“可能”需要用实际决定与结果验证。</p>
<div class="chain"><div><b>供电</b><br>辅助馈线异常<br><small>这是仿真施加的原因</small></div><span class="arrow">→</span><div><b>液冷</b><br>水泵能力下降、流量变化<br><small>控制指令不等于实际转速</small></div><span class="arrow">→</span><div><b>机柜与自控</b><br>温度变化，控制器调节泵与负载<br><small>检查不会修复物理故障</small></div></div>
<p id="caseDescription"></p><p class="muted">执行者是模拟巡检人员，不是18个大模型。示意链不是现场校准模型。电气任务目前检查接点温度，液冷任务检查支路流量，自控任务检查传感器偏差；这些检查不能直接当成查明了辅助馈线故障根因。</p></section>
<section class="panel"><h2>2. 巡检系统看到了什么？</h2>
<div class="controls"><label>回看方案 <select id="method"><option value="tour">固定路线</option><option value="risk">固定公开风险规则</option></select></label><label>机柜 <select id="rack"></select></label></div>
<div class="controls" style="margin:15px 0"><button id="play" type="button">播放</button><label for="time">回看时刻</label><input id="time" type="range" min="0" max="359" value="0"><output id="timeLabel" for="time"></output></div>
<div class="grid"><div><h3>公开信息形成的热巡检优先分</h3><svg id="publicMap" class="map" viewBox="0 0 530 310" role="img" aria-label="各机柜的公开热巡检风险分示意图"></svg><div class="legend">低<span class="swatch"></span>高（颜色到1饱和，悬停查看分数）<br>分数不是故障概率。圆点表示连续远程温度遥测。缺少观测时估计也可能得0分，不能当成已确认正常。</div></div>
<div class="truth"><h3>事后仿真真值：实际温度</h3><svg id="truthMap" class="map" viewBox="0 0 530 310" role="img" aria-label="仅供事后解释的实际温度示意图"></svg><div class="legend">40℃<span class="swatch"></span>85℃及以上<br>这张图没有传给巡检策略，不能用它证明模型提前知道热点。</div></div></div>
<p id="rackDetail"></p><p class="muted">布局为机柜分组示意，机柜与执行者编号从0开始。未测到的值显示“未知”，估计值会明确标为估计。</p>
<div id="charts" class="charts"></div>
<p class="legend">蓝线：公开信息；橙线：事后真值；红点：已完成的现场测温；淡橙背景：仿真故障施加窗口。图中全程曲线供事后回看，决策只使用当时及以前的信息。</p></section>
<section class="panel"><h2>3. 谁在什么时候完成了什么检查？</h2>
<p>显示所选机柜所在支路、回看时刻前后60秒的实际完成记录。不同专业负责不同测量，共享信息不代表可以越过资格限制。</p><div id="events" class="table-scroll"></div></section>
<section class="panel"><h2>4. 公开风险规则为什么换序，或者为什么没换？</h2>
<p>每人只考虑本轮接下来的最多三项既定义务；所有候选都经过资格、耗时与后续重访检查。分数越低越优，并列保留原序优先。</p>
<p><code id="expression"></code></p><p class="muted">含义：风险加权的完成等待 ＋ 0.2×重访紧迫程度 ＋ 0.05×路程时间。三项均经过归一化，分数没有秒或米的单位。</p>
<label>查看真实决策 <select id="decisionSelect"></select></label><p id="decisionNarrative"></p><div id="candidateTable" class="table-scroll"></div>
<h3>提前与延后都要看</h3><p class="muted">“原序预计”与“所选预计”从同一个决策时刻计算，假设执行本段后恢复基础巡回；后续再次重排可能改变后面的预计时间。它们不是两个完整回合的直接配对。“实际完成”来自当前规则的真实执行；回合内未完成显示“未完成”。</p><div id="affectedTable" class="table-scroll"></div>
<details><summary>查看这个决定当时可以使用的专业信息</summary><div id="evidenceTable" class="table-scroll"></div></details></section>
<section class="panel"><h2>5. 整回合结果是否更好？</h2><div id="results" class="table-scroll"></div><p id="outcome"></p>
<h3>具体是哪一段异常提前或延后？</h3><div id="anomalyTable" class="table-scroll"></div>
<p class="muted">确认等待：从评价器定义的异常段开始，到有效现场测量确认；漏检段算到该异常段结束，并按合成后果权重汇总。它不是从故障注入开始的时间，也不是人员空闲时间。移动与服务是全体人员的合计，完成次数包含持续巡回的重复检查。满足重访时限也可能错过短时异常。一次固定案例不能证明方法普遍有效。</p></section>
<section class="panel"><h2>6. 这个案例能把研究推进到哪里？</h2>
<p><b>先确认信息能影响一个合理的检查决定，再比较模型能否提出更好的改法。</b>如果规则只靠路程改变顺序，就不能把收益归给跨系统信息；若任务本身不包含必要的诊断测量，也不能声称已完成故障诊断。</p>
<p>VAE可以研究“看不全时怎样估计状态”，强化学习可以研究“怎样安排检查”，改进器可以研究“怎样根据结果修改做法”。本页只解释已有执行核，三个模型角色均未在本次训练或调用。</p>
<p>导师指定论文的 VAE 估计部分观测下的区域重要度，调度使用多智能体 Double DQN；不能将当前 PPO 源码等同于原论文复现。来源：<a href="https://idus.us.es/server/api/core/bitstreams/79e88506-ca7f-48f1-86b8-5504d9cb3e39/content">作者所在大学保存的原论文</a>，DOI：<a href="https://doi.org/10.1016/j.eswa.2025.126483">10.1016/j.eswa.2025.126483</a>。</p>
<p class="muted">完整数据：同目录 case.json；图表过程量保留4位小数，原始完成测量与排序分数未舍入。两个方案的 timeline.csv 是实际检查记录，actions.json 是完整派单记录。页面独立运行，不依赖网络、字体服务或外部脚本。</p></section>
<noscript>此回看页面需要启用 JavaScript；原始结果仍可从同目录的 case.json、summary.json 与 timeline.csv 查看。</noscript>
</main><script id="caseData" type="application/json">__CASE_DATA__</script><script>
const data=JSON.parse(document.getElementById('caseData').textContent);
const $=id=>document.getElementById(id), role=k=>data.role_names[k]||k;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=2)=>v===null||v===undefined?'未知':Number(v).toFixed(n);
function taskName(id){const [kind,n]=id.split(':');return kind==='thermal'?`机柜${n}测温`:kind==='cooling'?`支路${n}测流量`:kind==='electrical'?`支路${n}测接点温度`:`支路${n}查传感器`;}
const table=(heads,rows)=>rows.length?'<table><thead><tr>'+heads.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+esc(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table>':'<p class="empty">这个范围没有实际完成记录。</p>';
const end=data.spec.fault_start_s+data.spec.duration_s;
$('caseDescription').textContent=`本案例：${data.racks}个机柜、${data.inspectors}名执行者，运行1800秒；第${data.spec.fault_start_s}至${end}秒施加辅助馈线异常。${data.focus_selection}`;
$('expression').textContent=data.rule_expression;
for(let i=0;i<data.racks;i++)$('rack').add(new Option(String(i),String(i)));
$('rack').value=String(data.focus_rack);$('method').value='risk';
$('time').value=String(Math.min(359,Math.floor((data.spec.fault_start_s+90)/5)-1));
function colour(v){const t=Math.max(0,Math.min(1,v));return `rgb(${Math.round(233+(215-233)*t)},${Math.round(242+(70-242)*t)},${Math.round(251+(54-251)*t)})`;}
function map(id,values,isTruth,frame,rack){let svg='';for(let i=0;i<data.racks;i++){const pod=Math.floor(i/8),local=i%8,x=11+(pod%4)*132+(local%4)*29,y=9+Math.floor(pod/4)*76+Math.floor(local/4)*28;const v=values[i],title=`机柜${i}：${fmt(v)}${isTruth?'℃':'（风险分，非概率）'}`;svg+=`<g><title>${esc(title)}</title><rect x="${x}" y="${y}" width="27" height="25" rx="3" fill="${colour(isTruth?(v-40)/45:v)}" stroke="${i===rack?'#132f55':'#cad7e4'}" stroke-width="${i===rack?3:1}"/><text x="${x+13}" y="${y+16}" text-anchor="middle" font-size="10" fill="${(isTruth?(v-40)/45:v)>.65?'white':'#21344a'}">${i}</text>${!isTruth&&frame.remote_temperature_c[i]!==null?`<circle cx="${x+23}" cy="${y+4}" r="2" fill="#174b80"/>`:''}</g>`;}$ (id).innerHTML=svg;}
function path(values,min,max){let p='',started=false;values.forEach((v,i)=>{if(v===null||v===undefined){started=false;return;}const x=55+data.offline_only.time_s[i]/1800*1010,y=145-(v-min)/(max-min)*112;p+=`${started?'L':'M'}${x.toFixed(2)},${y.toFixed(2)} `;started=true;});return p;}
function chart(title,series,at,points=[]){const vals=series.flatMap(s=>s.values.filter(v=>v!==null&&v!==undefined));let min=Math.min(...vals),max=Math.max(...vals);const pad=Math.max(.05,(max-min)*.12);min-=pad;max+=pad;let html=`<h3>${esc(title)}</h3><svg viewBox="0 0 1100 180" role="img" aria-label="${esc(title)}"><rect x="${55+data.spec.fault_start_s/1800*1010}" y="25" width="${data.spec.duration_s/1800*1010}" height="125" fill="#fff0dd"/>`;for(let k=0;k<3;k++){const y=145-k*56,v=min+(max-min)*k/2;html+=`<line x1="55" x2="1065" y1="${y}" y2="${y}" stroke="#dbe4ee"/><text x="48" y="${y+4}" text-anchor="end" font-size="12" fill="#53667c">${fmt(v,1)}</text>`;}if(title.includes('温度')&&min<65&&max>65){const y=145-(65-min)/(max-min)*112;html+=`<line x1="55" x2="1065" y1="${y}" y2="${y}" stroke="#b92b32" stroke-dasharray="3 5"/><text x="1062" y="${y-4}" text-anchor="end" font-size="11" fill="#b92b32">本仿真异常阈值65℃</text>`;}for(const s of series)html+=`<path d="${path(s.values,min,max)}" fill="none" stroke="${s.colour}" stroke-width="2" ${s.dash?'stroke-dasharray="5 4"':''}/>`;for(const p of points)html+=`<circle cx="${55+p.t/1800*1010}" cy="${145-(p.v-min)/(max-min)*112}" r="3.5" fill="#b92b32"><title>${p.t}秒：${fmt(p.v)}℃，${p.agent}号</title></circle>`;html+=`<line x1="${55+at/1800*1010}" x2="${55+at/1800*1010}" y1="25" y2="150" stroke="#526780" stroke-dasharray="4 4"/>`;for(const t of [0,450,900,1350,1800])html+=`<text x="${55+t/1800*1010}" y="169" text-anchor="middle" font-size="12" fill="#53667c">${t}秒</text>`;return html+'</svg>';}
function eventValue(e){const m=e.measurement;if(e.kind==='thermal')return `${fmt(m.temperature_c)}℃`;if(e.kind==='electrical')return `接点温度 ${fmt(m.contact_temperature_c)}℃`;if(e.kind==='cooling')return `流量 ${fmt(m.pod_flow_kg_s)} kg/s`;return `传感器偏差 ${fmt(m.controller_sensor_error_c)}℃`;}
function update(){const key=$('method').value,method=data.methods[key],index=+$('time').value,rack=+$('rack').value,pod=Math.floor(rack/8),f=method.public_frames[index],at=f.time_s;$('timeLabel').textContent=`第 ${at} 秒`;
map('publicMap',f.thermal_risk,false,f,rack);map('truthMap',data.offline_only.temperature_c[index],true,f,rack);
$('rackDetail').textContent=`机柜${rack}：当前远程温度 ${fmt(f.remote_temperature_c[rack])}℃；最近有效温度 ${fmt(f.last_temperature_c[rack])}℃（距今 ${fmt(f.temperature_age_s[rack],0)} 秒）；名义估计 ${fmt(f.estimated_temperature_c[rack])}℃；公开热巡检优先分 ${fmt(f.thermal_risk[rack],3)}。本支路最近流量观测距今 ${fmt(f.flow_age_s[pod],0)} 秒。`;
const frames=method.public_frames,truth=data.offline_only;
const measured=method.events.filter(e=>e.task_id===`thermal:${rack}`).map(e=>({t:e.time_s,v:e.measurement.temperature_c,agent:e.agent}));
$('charts').innerHTML=chart(`支路${pod}：公开水泵控制指令（无量纲）`,[{values:frames.map(v=>v.pump_command[pod]),colour:'#2863a5'}],at)+chart(`支路${pod}：流量（kg/s）`,[{values:truth.pod_flow_kg_s.map(v=>v[pod]),colour:'#cc6639'},{values:frames.map(v=>v.last_flow_kg_s[pod]),colour:'#2863a5',dash:true}],at)+chart(`机柜${rack}：温度（℃）`,[{values:truth.temperature_c.map(v=>v[rack]),colour:'#cc6639'},{values:frames.map(v=>v.remote_temperature_c[rack]),colour:'#2863a5'}],at,measured);
const events=method.events.filter(e=>(e.kind==='thermal'?Math.floor(e.measurement.rack_index/8):e.measurement.pod_index)===pod&&Math.abs(e.time_s-at)<=60);
$('events').innerHTML=table(['完成时刻/秒','执行者','专业','检查对象','有效测量','判定'],events.map(e=>[e.time_s,e.agent,role(e.role),taskName(e.task_id),eventValue(e),e.alarm?'异常确认':'正常范围']));}
const decisions=data.methods.risk.decisions;
decisions.forEach((d,i)=>$('decisionSelect').add(new Option(`${d.time_s}秒 · ${d.agent}号${role(d.role)} · ${d.changed?'改变顺序':'保留原序'}`,String(i))));
$('decisionSelect').value=String(data.methods.risk.default_decision);
function decision(){const d=decisions[+$('decisionSelect').value];if(!d)return;const same=JSON.stringify(d.selected)===JSON.stringify(d.without_risk_order);
$('decisionNarrative').textContent=`${d.time_s}秒，${d.agent}号${role(d.role)}：${d.original.map(taskName).join(' → ')} ${d.changed?'改为':'仍为'} ${d.selected.map(taskName).join(' → ')}。共有${d.legal_count}个合法排列。${same?'即使去掉风险项，本点也会选择相同顺序，因此不能把这次选择归因于风险项。':'在同一合法候选中去掉风险项，选择会不同，说明风险项影响了本点排序；这还不是整回合收益证明。'}`;
$('candidateTable').innerHTML=table(['合法排列','风险等待项','重访项×0.2','路程项×0.05','总分','实际选择'],d.candidates.map(c=>[c.order.map(taskName).join(' → '),fmt(c.features.risk_delay,5),fmt(.2*c.features.deadline_pressure,5),fmt(.05*c.features.travel_cost,5),fmt(c.score,5),JSON.stringify(c.order)===JSON.stringify(d.selected)?'✓':'']));
$('affectedTable').innerHTML=table(['检查对象','原序预计/秒','所选预计/秒','提前或延后/秒','实际完成/秒'],d.affected.map(r=>[taskName(r.task),fmt(r.original_prediction_s,0),fmt(r.selected_prediction_s,0),(r.delta_s>0?'延后 ':r.delta_s<0?'提前 ':'不变 ')+fmt(Math.abs(r.delta_s),0),r.actual_completion_s===null?'本回合未完成':fmt(r.actual_completion_s,0)]));
$('evidenceTable').innerHTML=table(['检查对象','专业','公开风险分','最近观测值','距观测/秒','要求重访/秒'],d.public_tasks.map(r=>[taskName(r.task_id),role(r.kind),fmt(r.risk,3),r.observed_value===null?'未知':fmt(r.observed_value)+' '+r.observed_unit,fmt(r.direct_age_s,0),r.deadline_s]));
$('method').value='risk';$('time').value=String(d.time_s/5-1);update();}
const metrics=[['未确认异常段数','missed_segments',0],['异常段加权确认等待/秒','consequence_weighted_censored_delay_s',2],['全体移动/米','travel_m',1],['全体服务/人秒','service_s',0],['实际完成检查/次','completed_inspections',0],['回合末本轮未完成义务/项','current_round_unfinished_obligations',0],['重访超期任务/项','tasks_violating_exact_gap',0],['发生重排的局部计划/段','reordered_plans',0]];
$('results').innerHTML=table(['指标','固定路线','公开风险规则'],metrics.map(([label,key,n])=>[label,...['tour','risk'].map(k=>{const v=data.methods[k].metrics[key];return v===null?'无异常，不适用':fmt(v,n);})]));
const t=data.methods.tour.metrics,r=data.methods.risk.metrics;
const change=(a,b,unit,n=2)=>`${a>b?'增加':a<b?'减少':'不变'}${fmt(Math.abs(a-b),n)}${unit}`;
const takeaway=data.same_actions?'本案例两个方案的完整派单相同，不能宣称规则改变了行为或改善了结果。':`相对固定路线：移动${change(r.travel_m,t.travel_m,'米',1)}，完成检查${change(r.completed_inspections,t.completed_inspections,'次',0)}；${r.consequence_weighted_censored_delay_s===null?'无异常，确认等待不适用':`加权确认等待${change(r.consequence_weighted_censored_delay_s,t.consequence_weighted_censored_delay_s,'秒')}`}。两个方案分别漏检${t.missed_segments}段与${r.missed_segments}段。`;
const riskUsed=decisions.filter(d=>JSON.stringify(d.selected)!==JSON.stringify(d.without_risk_order)).length;
$('quickResult').textContent='本例结果：'+takeaway;
$('outcome').textContent=takeaway+` 同状态去掉风险项再计分，${decisions.length}个决策中有${riskUsed}个改变所选排列。这是逐点算术核对，没有额外执行一组策略；${riskUsed?'风险项有局部作用，还需独立实验检验任务收益。':'本案例尚未观察到风险项改变排序，不能把省路程归因于风险信息。'}`;
$('anomalyTable').innerHTML=table(['异常对象','评价异常段/秒（事后）','固定路线确认/秒','风险规则确认/秒'],data.methods.tour.anomaly_intervals.map((a,i)=>[taskName(a.task_id),`${a.onset_s}—${a.end_s}`,a.first_confirmation_s===null?'未确认':a.first_confirmation_s,data.methods.risk.anomaly_intervals[i].first_confirmation_s===null?'未确认':data.methods.risk.anomaly_intervals[i].first_confirmation_s]));
let timer=null;$('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;$('play').textContent='播放';return;}if(+$('time').value===359)$('time').value='0';$('play').textContent='暂停';timer=setInterval(()=>{const next=+$('time').value+1;if(next>359){clearInterval(timer);timer=null;$('play').textContent='播放';return;}$('time').value=String(next);update();},120);};
$('time').oninput=update;$('method').onchange=update;$('rack').onchange=update;$('decisionSelect').onchange=decision;update();decision();
</script></body></html>'''
