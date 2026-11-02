"""One entry point for understanding, running and checking the retained project.

Commands never download models, call an LLM, train research models, or start
historical campaigns. Demo/proposal runs are labelled engineering examples.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from .baseline_correction import Rule, parse_response, require_mutation, rule_from_dict
from .contracts import strict_json

ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = "f2c20b3a642ff1df9426e523614d3da9a5cf1129"
METRIC_KEYS = (
    "missed_segments", "consequence_weighted_censored_delay_s", "travel_m",
    "service_s", "completed_inspections", "tasks_violating_exact_gap",
    "maximum_exact_gap_ratio", "numeric_scoring_failures", "estimator_calls",
)


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def project_path(value: str | None, default: str) -> Path:
    return Path(value).resolve() if value else ROOT / default


def status():
    return {
        "研究问题": "真实运行反馈能否帮助改进受资格、工时和持续重访约束的巡检流程？",
        "当前执行路径": "原机房过程 → 公开观测/名义估计 → 受保护Tour或局部规则 → 实际测量 → 评价",
        "默认策略": "Tour",
        "可选工具": {"CVAE": "需要本地冻结权重及SHA；默认不启用", "PPO": "保留实现，未接入默认局部调度", "Qwen": "保留历史证据；这些命令不调用模型"},
        "本地验收": "python -m patrol_rsi verify --output runs/verification",
        "已证明的范围": "核心行为可回归，保留的历史数据与预测可复算",
        "尚未证明": "稳定任务增益、经验独立贡献、递归改进增益、现场有效性",
        "唯一下一任务": "docs/NEXT.md：真实后果反馈与无后果反馈的受限流程改进比较",
        "新研究实验": "NOT_RUN",
        "历史快照": f"https://github.com/DonsonHH/Zhinengti-RSI/tree/{SOURCE_COMMIT}",
    }


def frozen_estimator(checkpoint: str | None, expected_sha: str | None):
    if checkpoint is None:
        if expected_sha:
            raise ValueError("--cvae-sha256 requires --cvae-checkpoint")
        return None, {"name": "nominal", "neural_inference": False}
    path = Path(checkpoint).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha is None or digest != expected_sha.lower():
        raise ValueError("Frozen CVAE requires a matching --cvae-sha256; no fallback to a fake model")
    import torch
    from .estimation_model import TemperatureCVAE
    pack = torch.load(path, map_location="cpu", weights_only=True)
    model = TemperatureCVAE(pack["inputs"])
    model.load_state_dict(pack["state_dict"])
    model.eval()

    def predict(context):
        with torch.inference_mode():
            return model.predict(torch.as_tensor(context)).numpy().squeeze(-1) * 20 + 50
    return predict, {"name": "frozen_CVAE", "sha256": digest, "neural_inference": True}


def load_demo(args):
    from .process import ATOMS

    config = strict_json(project_path(args.config, "configs/demo.json").read_text(encoding="utf-8"))
    if set(config) != {"purpose", "spec"} or config["purpose"] != "engineering_example_not_new_research":
        raise ValueError("Use the explicitly labelled engineering example configuration")
    spec = dict(config["spec"])
    expected = {"seed", "scenario", "episode_horizon_s", "fault_duration_s", "fault_start_s", "noise_c", "estimator", "control", "resources"}
    if set(spec) != expected or spec["estimator"] != "nominal":
        raise ValueError("Use the closed task schema: episode_horizon_s and fault_duration_s are distinct; estimator defaults to nominal")
    if type(spec["episode_horizon_s"]) is not int or spec["episode_horizon_s"] != 1800:
        raise ValueError("The retained core supports a fixed 1800-second episode")
    if type(spec["seed"]) is not int or spec["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(spec["fault_duration_s"]) is not int or spec["fault_duration_s"] not in (60, 180, 900):
        raise ValueError("fault_duration_s must be 60, 180 or 900")
    if type(spec["fault_start_s"]) is not int or spec["fault_start_s"] not in (150, 335, 520, 705):
        raise ValueError("fault_start_s must be 150, 335, 520 or 705")
    if type(spec["noise_c"]) not in (int, float) or spec["noise_c"] not in (.2, 1.):
        raise ValueError("noise_c must be 0.2 or 1.0")
    if spec["control"] != "feedback" or spec["resources"] != "provisioned":
        raise ValueError("The retained task fixes feedback control and provisioned staffing")
    if not isinstance(spec["scenario"], str) or any(atom not in ATOMS for atom in spec["scenario"].split("+")):
        raise ValueError("scenario must contain declared synthetic fault atoms")
    # Keep the historical engine schema behind this unambiguous public interface.
    spec.pop("episode_horizon_s")
    spec["duration_s"] = spec.pop("fault_duration_s")
    predictor, tool = frozen_estimator(args.cvae_checkpoint, args.cvae_sha256)
    if predictor is not None:
        spec["estimator"] = "history"
    return spec, predictor, tool


def summarize(record):
    return {
        "metrics": {k: record["metrics"][k] for k in METRIC_KEYS},
        "action_sha256": record["action_sha256"],
        "process_sha256": record["process"]["numeric_digest"],
        "PPO_scoring_calls": record["PPO_scoring_calls"],
    }


def save_run(folder: Path, record, env):
    folder.mkdir()
    write_json(folder / "summary.json", summarize(record))
    write_json(folder / "actions.json", record["action_log"])
    with (folder / "timeline.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ["time_s", "agent", "role", "task", "task_id", "kind", "x_m", "y_m", "service_s",
                  "alarm", "measurement_transition", "measurement"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for event in record["inspection_events"]:
            row = {key: event.get(key) for key in fields}
            row["x_m"], row["y_m"] = env.tasks[event["task"]].position_m
            row["measurement"] = json.dumps(event["measurement"], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)
    # A short public decision explanation, not thousands of candidate snapshots.
    decisions = record.get("local_decisions", [])
    changed = [d for d in decisions if not d["selected_original"]]
    examples = changed[:3] if changed else decisions[:1]
    write_json(folder / "decision-examples.json", [
        {k: d.get(k) for k in ("time_s", "agent", "round_id", "window", "selected_order", "selected_original", "public_tasks")}
        for d in examples
    ])


def compare_candidate(parent, child):
    """Illustrative, conservative decision, never a formal research acceptance."""
    p, c = parent["metrics"], child["metrics"]
    axes = ["missed_segments", "consequence_weighted_censored_delay_s", "travel_m"]
    pairs = [(c[key], p[key]) for key in axes if c[key] is not None and p[key] is not None]
    pairs.append((-c["completed_inspections"], -p["completed_inspections"]))
    safe = c["tasks_violating_exact_gap"] == 0 and c["numeric_scoring_failures"] == 0
    better = safe and all(a <= b + 1e-9 for a, b in pairs) and any(a < b - 1e-9 for a, b in pairs)
    return {
        "illustrative_decision": "retain_candidate_in_example" if better else "keep_parent",
        "comparison": "All comparable outcomes no worse, at least one better; completion must not fall",
        "formal_default": "Tour",
        "research_acceptance": "NOT_EVALUATED: one engineering example is not an independent study",
    }


def run_example(args, proposal=False):
    from .correction_execution import execute_correction
    from .reorder_execution import run_reorder
    spec, predictor, tool = load_demo(args)
    parent = rule_from_dict(strict_json((ROOT / "configs/parent-rule.json").read_text(encoding="utf-8")))
    child, mechanism, candidate_raw = None, None, None
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    ledger = {"purpose": "engineering_example_not_new_research", "LLM_calls": 0, "research_training": 0,
              "attempts": [], "candidate_source": "provided_json_no_model_called" if proposal else "human_rule_fixture"}
    write_json(output / "attempts.json", ledger)
    try:
        if proposal:
            candidate_raw = Path(args.candidate).read_text(encoding="utf-8")
            ledger["proposal_attempt"] = {"raw_sha256": hashlib.sha256(candidate_raw.encode()).hexdigest(), "status": "parsing"}
            (output / "candidate.raw.json").write_text(candidate_raw, encoding="utf-8")
            child, mechanism = parse_response(candidate_raw)
            require_mutation(child, parent)
            ledger["proposal_attempt"]["status"] = "valid_unique_rule"
        records = {}
        for name, rule in [("tour", None), ("parent", parent)] + ([("candidate", child)] if proposal else []):
            entry = {"name": name, "status": "started"}
            ledger["attempts"].append(entry)
            write_json(output / "attempts.json", ledger)
            record, env = run_reorder(spec, predictor, {"method": "T"}) if rule is None else execute_correction(
                spec, predictor, {"kind": "correction", "rule": rule.to_dict()})
            if env.clock != 1800 or env.config.fault_end_s != spec["fault_start_s"] + spec["duration_s"]:
                raise ValueError("Executed episode or injection window differs from the declared configuration")
            save_run(output / name, record, env)
            records[name] = record
            entry["status"] = "completed"
        public_spec = {k: v for k, v in spec.items() if k != "duration_s"}
        public_spec.update(episode_horizon_s=int(env.clock), fault_duration_s=spec["duration_s"])
        result = {"purpose": ledger["purpose"], "spec": public_spec, "estimator": tool, "LLM_calls": 0,
                  "executed_configuration": {"episode_horizon_s": int(env.clock), "physical_step_s": env.config.dt_s,
                      "fault_start_s": env.config.fault_start_s, "fault_end_s": env.config.fault_end_s,
                      "racks": env.config.racks, "inspectors": len(env.agents)},
                  "output_directory": str(output),
                  "research_status": "NOT_RUN", "formal_default": "Tour",
                  "results": {name: summarize(record) for name, record in records.items()},
                  "read_next": "Open each timeline.csv to see who completed which inspection and measurement."}
        if proposal:
            result["proposal"] = {"parent_id": parent.identity, "child_id": child.identity, "mechanism": mechanism,
                                  **compare_candidate(records["parent"], records["candidate"])}
            write_json(output / "feedback.json", {"scope": "aggregate engineering-example feedback; not new research evidence",
                       "parent_rule": parent.to_dict(), "candidate_rule": child.to_dict(),
                       "outcomes": result["results"], "decision": result["proposal"]})
            write_json(output / "retained-example-rule.json", child.to_dict() if
                       result["proposal"]["illustrative_decision"] == "retain_candidate_in_example" else parent.to_dict())
        write_json(output / "summary.json", result)
        lines = ["# 巡检工程示例", "", "这是现有执行核的演示，不是新的科研确认或RSI增益实验。", "",
                 f"{env.config.racks}机柜、{len(env.agents)}名执行者；整次巡检{int(env.clock)}秒，故障窗口为第{env.config.fault_start_s:g}至{env.config.fault_end_s:g}秒。",
                 f"本次估计器：{tool['name']}。PPO不参与本地顺序评分，Qwen调用为0。", "",
                 "|运行|漏检段|等待/秒|移动/米|完成检查|重访违规|", "|---|---:|---:|---:|---:|---:|"]
        for name, record in records.items():
            m = record["metrics"]
            lines.append(f"|{name}|{m['missed_segments']}|{m['consequence_weighted_censored_delay_s']}|{m['travel_m']:.3f}|{m['completed_inspections']}|{m['tasks_violating_exact_gap']}|")
        lines.extend(["", "每个运行目录中的 timeline.csv 是完整完成时间线，actions.json 是完整派单序列。",
                      "time_s是完成时刻，agent/role是执行者及专业，task_id是检查对象，x_m/y_m是位置，measurement是实际测量。",
                      "decision-examples.json 展示公开依据和所选顺序；保留原序也可能是正确的结果。",
                      "专业重访合格不等于所有短时异常都会被发现。", ""])
        (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
        ledger["status"] = "completed"
        return result
    except Exception as exc:
        ledger["status"] = "failed"
        ledger["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_json(output / "attempts.json", ledger)


def verify(args):
    module_path = ROOT / "scripts/acceptance.py"
    spec = importlib.util.spec_from_file_location("patrol_acceptance", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify(ROOT, Path(args.output).resolve())


def main(argv=None):
    parser = argparse.ArgumentParser(description="巡检项目统一入口：status / demo / explain / proposal / verify")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="只读显示主线、状态、实际工具与下一任务")
    for command in ("demo", "proposal"):
        p = sub.add_parser(command, help="运行明确标注的工程示例；不调用LLM")
        p.add_argument("--config", help="默认configs/demo.json")
        p.add_argument("--output", required=True, help="必须是新目录，防止覆盖原结果")
        p.add_argument("--cvae-checkpoint")
        p.add_argument("--cvae-sha256")
        if command == "proposal":
            p.add_argument("--candidate", required=True, help="原始候选JSON；示例为人工fixture")
    p = sub.add_parser("explain", help="回看一个供电—液冷耦合案例，输出独立HTML；不调用模型")
    p.add_argument("--config", help="默认configs/coupled-example.json；仅支持辅助馈线异常案例")
    p.add_argument("--output", required=True, help="必须是新目录")
    p = sub.add_parser("verify", help="工程检查＋历史证据复算，科研效果单独列出")
    p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "explain":
            from .case_report import run_explanation
            result = run_explanation(args)
        else:
            result = status() if args.command == "status" else verify(args) if args.command == "verify" else run_example(args, args.command == "proposal")
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.get("overall", "PASS") == "PASS" else 1
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
