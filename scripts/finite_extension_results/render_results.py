"""Produce the frozen per-condition comparisons and descriptive F1–F5 decisions."""
from collections import Counter, defaultdict
from fractions import Fraction
from observations import ARMS, KINDS, equal, insist, norm


def display(value):
    return "—" if value is None else str(value)


def triple(row,field,cost=False):
    result=[]
    for name in ARMS:
        arm=row["arms"][name]
        result.append(display(None if arm is None else (arm["costs"] if cost else arm)[field]))
    return " / ".join(result)


def sign_lists(rows,name,lower_is_example):
    out={"I_lower":[],"equal":[],"I_higher":[]}
    for r in rows:
        val=Fraction(r[name])
        # Primary D-I; background I-P.
        if name=="delta_L_D_minus_I":val=-val
        out["I_lower" if val<0 else "I_higher" if val>0 else "equal"].append(r["slot"])
        prop="F3_counterexample" if lower_is_example=="P" else "F1_counterexample"
        equal(r["effective_propositions"][prop],val<0,"Effective sign versus frozen proposition")
    return out


def stage_detail(row):
    slot=row["slot"];i,d,p=[row["arms"][a] for a in ARMS]
    if i is None:return row["gap_reason"]
    def seq(arm):
        return ", ".join(x["action"]+"@"+str(x["time"]) for x in arm["requests"]) or "无请求"
    def commit(arm):
        return [x.get("committed_at") for x in arm["execution_receipts"] if x["status"]=="EXECUTED_UNVERIFIED"]
    def probe(arm):
        return [(x["status"],x["available_at"]) for x in arm["verify_records"]]
    def cut(arm):
        return f'{arm["stop"]["reason"]}@{arm["stop"]["time"]}，{arm["reached"]["commit_result"]}'
    if slot in ("A01","A02","B01"):
        evidence=", ".join(f'{r["action"]}={r["value"]}，到达 {r["available_at"]}，失效 {r["expires_at"]}' for r in i["negative_record_at_stop"]) or "停止帧未见合法否定记录"
        isolation=f'，D 隔离 {intervals(d["load_isolation"])}' if slot=="B01" else ""
        return f'I {evidence}，停止 {i["stop"]["time"]}；D 提交 {commit(d)}、复核 {probe(d)}{isolation}'
    if slot in ("A03","B02","B03"):
        return f'I/D 提交 {commit(i)}/{commit(d)}，隔离 {intervals(i["load_isolation"])}/{intervals(d["load_isolation"])}，复核 {probe(i)}/{probe(d)}'
    if slot=="C01":
        return "I 到达记录 "+", ".join(f'{x["action"]}={x["status"]}@{x["available_at"]}' for x in i["observations"])+"，停止 "+i["stop"]["reason"]
    if slot=="D01":
        return f'D 在 {d["stop"]["time"]} 读公开许可后 {d["stop"]["reason"]}，{seq(d)}；I 复核 {probe(i)}'
    if slot.startswith("E"):
        return f'I/D 审批 {i["grant"]["decision"]}/{d["grant"]["decision"]}，提交 {i["reached"]["commit_result"]}/{d["reached"]["commit_result"]}，复核 {i["reached"]["verification_result"]}/{d["reached"]["verification_result"]}；各停止于 {i["stop"]["time"]}/{d["stop"]["time"]}'
    if slot.startswith("F"):
        return f'I/D 复核 {probe(i)}/{probe(d)}，G 终态 {i["final_G"]}/{d["final_G"]}。I/D/P 均记录供给段，见下方专表。'
    if slot.startswith("G"):
        arm=d if slot in ("G01","G02","G03") else i
        return f'实际外生事件 {events(arm)}；目标臂 {cut(arm)}，成功提交时刻 {commit(arm)}'
    if slot.startswith(("H","J")):
        return f'I {seq(i)}，{i["stop"]["reason"]}@{i["stop"]["time"]}；D {seq(d)}，{d["stop"]["reason"]}@{d["stop"]["time"]}'
    if slot.startswith("K"):
        return f'I/D 实际排队 {i["costs"]["resource_queue_seconds"]}/{d["costs"]["resource_queue_seconds"]}，{cut(i)} / {cut(d)}'
    return f'I 事件 {events(i)}，{cut(i)}；I/D/P 终态 vA={triple(row,"final_vA")}；恢复与删失见成本表'


def intervals(rows):
    return ", ".join(f'{display(r["state"])}[{r["start"]},{r["end"]})' for r in rows) or "无"


def events(arm):
    return ", ".join(f'{e["event"]}@{e["time"]}' for e in arm["fault_restore_events"]) or "无"


def summarize(rows,status):
    usable=[r for r in rows if r["eligible"]]
    completed=[r for r in rows if r["score_available"] and all(r["arms"][a] is not None for a in ARMS)]
    nc=[r["slot"] for r in rows if r["dispatch_status"]=="NONCOMPLIANT"]
    unexecuted=[r["slot"] for r in rows if r["dispatch_status"]=="NOT_SUBMITTED"]
    unknown=[r["slot"] for r in rows if r["calls_proved"] is None or (r["unknown_internal_calls"] or 0)>0]
    counts=Counter()
    for row in rows:
        if row.get("accounting"):
            counts.update(row["accounting"].get("known_reported_subtotal",{}))
    primary=sign_lists(usable,"delta_L_D_minus_I","D")
    background=sign_lists(usable,"delta_L_I_minus_P","P")
    reached=[r["slot"] for r in rows if r["assigned_stage_observed"] is True]
    gaps={r["slot"]:r.get("gap_reason") for r in rows if r["assigned_stage_observed"] is not True}
    def verdict(signed):
        if signed["I_lower"]:return "FALSIFIED_BY_VALID_COUNTEREXAMPLE"
        if gaps or len(completed)!=len(rows):return "NO_OBSERVED_VALID_COUNTEREXAMPLE_INCOMPLETE_COVERAGE"
        return "SUPPORTED_ON_COMPLETE_COMPLIANT_ROWS_OF_THIS_LIST"
    f2={}
    for r in rows:
        if r["slot"] not in ("A01","A02"):continue
        i,d=r["arms"]["I"],r["arms"]["D"]
        frozen=(r["effective_propositions"] or {}).get("F2")
        if not frozen:
            f2[r["slot"]]={"verdict":"INSUFFICIENT_OR_INELIGIBLE"};continue
        diffs={k:norm(Fraction(d["costs"][k])-Fraction(i["costs"][k])) for k in ("person_seconds","tool_seconds")}
        observed_short=bool(i["negative_record_at_stop"]) and i["stop"]["reason"]=="NO_ACTION_CURRENT_SCOPE" and all(x["action"]!="FIX_CTRL" for x in i["requests"])
        equal(observed_short,frozen["short_circuit_without_FIX"],"F2 stop frame")
        same=i["L"]==d["L"];equal(same,frozen["same_service"],"F2 equal service")
        equal(all(Fraction(v)>0 for v in diffs.values()) if same else None,frozen["less_person_and_tool"],"F2 savings")
        f2[r["slot"]]=dict(**frozen,savings_D_minus_I=diffs,stop=i["stop"],stop_evidence=i["negative_record_at_stop"],
            verdict="SUPPORTED_IN_ASSIGNED_ROW" if observed_short and same and frozen["less_person_and_tool"] else
                    "COST_SUBCLAIM_NOT_APPLICABLE" if observed_short and not same else "FALSIFIED_ASSIGNED_CLAIM")
    f4=[];technical_findings={};probes=0;probe_requests=0;success_commits=0;repeat_frames=0
    statuses=defaultdict(list);censored=defaultdict(list);endpoint=defaultdict(list);source_unrestored=defaultdict(list)
    for r in completed:
        props=r["worker_propositions"]
        i,p=r["arms"]["I"],r["arms"]["P"]
        applicable=r["preclassified"]["work_mode"]=="ONLINE" and i["reached"]["commit_result"]!="SUCCESS"
        equal(bool(props["F4"]),applicable,"F4 applicability")
        if applicable:
            same=i["service_states"]==p["service_states"]
            equal(props["F4"][0]["matched"],same,"F4 physical intervals")
            f4.append(dict(slot=r["slot"],matched=same))
        if props["F5_technical_findings"]:technical_findings[r["slot"]]=props["F5_technical_findings"]
        for a in ARMS:
            arm=r["arms"][a]
            statuses[arm["stage"]].append(r["slot"]+"/"+a)
            repeat_frames+=arm["identical_public_packet_matches"]
            probe_requests+=sum(q["action"]=="VERIFY_CTRL" for q in arm["requests"])
            probes+=len(arm["verify_records"])
            success_commits+=sum(e["status"]=="EXECUTED_UNVERIFIED" for e in arm["execution_receipts"])
            if arm["right_censored"]:
                censored[a].append(r["slot"])
                if all(e.get("lower_bound")==0 for e in arm["right_censored"]):endpoint[a].append(r["slot"])
            if any(e["event"]=="fault" for e in arm["fault_restore_events"]) and arm["final_vA"]==0:
                source_unrestored[a].append(r["slot"])
    return dict(
        scope="仅适用于冻结同账号有限合成条件",
        denominator=dict(planned=len(rows),executed_with_complete_scores=len(completed),valid_rows=len(usable),noncompliant_rows=nc,
            technical_error_rows=[r["slot"] for r in rows if r["dispatch_status"] not in ("PASS","NONCOMPLIANT","NOT_SUBMITTED")],
            missing_complete_score=[r["slot"] for r in rows if not r["score_available"]],unsubmitted=unexecuted,
            unknown_or_pending_calls=unknown,assigned_stage_observed=reached,coverage_not_attained=gaps,terminal=status),
        calls=dict(proved_runner_calls=sum(r["calls_proved"] or 0 for r in rows),known_reported_subtotal=counts,unknown_or_pending_slots=unknown,
                   call_totals_exact=not unknown,completed_arm_runs=sum(len(r["arms"]) for r in completed)),
        F1=dict(verdict=verdict(primary),eligible_scope=[r["slot"] for r in usable],delta="L_D - L_I",by_sign=primary,
                valid_counterexamples=[dict(slot=r["slot"],delta_L=r["delta_L_D_minus_I"]) for r in usable if r["effective_propositions"]["F1_counterexample"]]),
        F2=dict(assigned_slots=["A01","A02"],by_slot=f2),
        F3=dict(verdict=verdict(background),delta="L_I - L_P",by_sign=background,
                valid_counterexamples=[dict(slot=r["slot"],delta_L=r["delta_L_I_minus_P"]) for r in usable if r["effective_propositions"]["F3_counterexample"]],
                I_both_resource_costs_higher_than_P=[r["slot"] for r in usable if all(Fraction(r["delta_costs_I_minus_P"][k])>0 for k in ("person_seconds","tool_seconds"))]),
        F4=dict(applicable_online_without_successful_I_fix=f4,matched=sum(x["matched"] for x in f4),
                verification_requests_bound_to_arrived_execution=probe_requests,published_verification_records_bound_to_execution=probes,
                verdict="MATCH_ON_OBSERVED_APPLICABLE_ROWS_AND_BOUND_IDENTITIES" if all(x["matched"] for x in f4) and f4 else "CHECK_FAILED_OR_NOT_OBSERVED"),
        F5=dict(reconciled_rows=len(completed),technical_findings=technical_findings,actual_successful_commit_receipts_checked=success_commits,
                identical_treatment_public_packet_repeats_checked=repeat_frames,policy_packets_checked=counts["policy_calls"],
                verdict="NO_FROZEN_TECHNICAL_VIOLATION_IN_OBSERVED_ROWS" if not technical_findings and completed else "TECHNICAL_VIOLATION_OR_MISSING"),
        actual_stage_index=dict(statuses),service_right_censored_by_arm={a:censored[a] for a in ARMS},
        censoring_start_at_H_by_arm={a:endpoint[a] for a in ARMS},
        external_A_still_unavailable_at_H_by_arm={a:source_unrestored[a] for a in ARMS},
        noncompliance={r["slot"]:{a:r["arms"][a]["violated_constraints"] for a in ARMS} for r in completed if r["slot"] in nc})


def write_markdown(path,lines):
    with path.open("x",encoding="utf-8",newline="\n") as out:
        out.write("\n".join(lines)+"\n")


def write_reports(output,rows,status):
    propositions=summarize(rows,status)
    pairs=["# 35 行配对结果","","每个三元组内均按 I / D / P 排列。L 为 [0,20) 的需求归一化缺额秒数，U 为未服务量。预算和工时均在各组独立结算。有效比较需三组数据完整、合规且外层作业成功。非合规的差值仍列出，并标明有效资格。","","| 条件 | 作业 | 有效比较 | 分配阶段到达 | L | U | D−I 缺额 | I−P 缺额 | 人员秒 | 工具秒 |","|---|---:|---|---|---|---|---:|---:|---|---|"]
    cover=["# 实际阶段与恢复证据","","阶段来自实际请求、观察、回执、私有状态与事件。预先分配的覆盖义务使用冻结判据复核。阶段未达时保留原行。","","| 条件 | I 实际阶段 | D 实际阶段 | P 实际阶段 | 到达 | 实际依据或缺口 |","|---|---|---|---|---|---|"]
    costs=["# 等待、占用与停止","","每格按 I / D / P 排列。等待指标可以重叠，人员秒和工具秒各自报告。按动作、阶段细分的实际占用、完整恢复记录、各组对模型的调用数及每项硬约束保存在 [paired-results.json](paired-results.json)。","","| 条件 | 资源排队秒 | 审批等待秒 | 未开工观察等待秒 | 观察停止时刻 | 请求数 | 策略调用数 | 设施接口调用数 | 服务恢复状态 |","|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        yes="是" if r["eligible"] else r["dispatch_status"]
        observed={True:"是",False:"未达",None:"未执行或未决"}[r["assigned_stage_observed"]]
        pairs.append("| "+" | ".join([r["slot"],display(r["job_id"]),yes,observed,triple(r,"L"),triple(r,"U"),display(r.get("delta_L_D_minus_I")),display(r.get("delta_L_I_minus_P")),triple(r,"person_seconds",True),triple(r,"tool_seconds",True)])+" |")
        cover.append("| "+" | ".join([r["slot"],*[display(r["arms"][a]["stage"] if r["arms"][a] else None) for a in ARMS],observed,stage_detail(r)])+" |")
        costs.append("| "+" | ".join([r["slot"],*[triple(r,k,True) for k in ("resource_queue_seconds","approval_wait_seconds","unstarted_observed_wait_seconds","observed_stop_time","request_count","policy_call_count")],
            " / ".join(display(r["arms"][a]["calls"].get("plant",0) if r["arms"][a] else None) for a in ARMS),triple(r,"service_recovery_status")])+" |")
    cover+=["","## F01／F02 的后备父条件","","G 的初末状态取自实际审计。区间为左闭右开。电量单位 kJ，右删失下界为秒。","","| 条件／组 | ready／permit | 终态控制族／epoch | G 初态 → 终态 | 实际供给 | UPS 已交付／H 剩余 | H 时设备 | 右删失下界 |","|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["slot"] not in ("F01","F02"):continue
        for a,arm in r["arms"].items():
            if arm:
                c=r["preclassified"]
                cover.append(f'| {r["slot"]}/{a} | {c["ready"]}/{c["permit"]} | {arm["final_family"]}/{arm["final_epoch"]} | {arm["initial_G"]} → {arm["final_G"]} | {intervals(arm["supply"])} | {arm["ups_energy"]}/{arm["ending_UPS"]} | {arm["final_device"]} | {[e.get("lower_bound") for e in arm["right_censored"]]} |')
    write_markdown(output/"paired-results.md",pairs)
    write_markdown(output/"actual-stage-coverage.md",cover)
    write_markdown(output/"costs-and-recovery.md",costs)
    return propositions
