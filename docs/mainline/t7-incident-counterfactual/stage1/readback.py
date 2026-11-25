"""Read and reconcile the published development returns without a facility or worker."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from tables import ROLES, ROSTER, describe


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
EXECUTION = "9381a5df4d3afcb1b2c458b5078481eaf798cf7d"
T3 = "85af7e48b60e61dc453456b5b7bc73ab832900b5"
T3_PATH = "docs/mainline/t3-prior-information-v2/development-result.json.gz"


def need(ok, name):
    if not ok:
        raise ValueError(name)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read(name):
    data = (HERE / name).read_bytes()
    return json.loads(gzip.decompress(data) if name.endswith(".gz") else data)


def seconds(clock):
    days, sep, rest = clock.partition("-")
    parts = (rest if sep else days).split(":")
    a = 86400 * int(days) if sep else 0
    return a + sum(float(x) * 60**i for i, x in enumerate(reversed(parts)))


def accounting(name, job):
    lines = (HERE / name).read_text("ascii").splitlines()
    header, *rows = [line.split("|") for line in lines if line.strip()]
    records = [dict(zip(header, row, strict=True)) for row in rows]
    allocation = next(r for r in records if r["JobID"] == job)
    step = next(r for r in records if r["JobID"] == job + ".batch")
    need(all(r["State"] == "COMPLETED" and r["ExitCode"] == "0:0" for r in (allocation, step)), "Slurm terminal result: " + job)
    return {"job": job, "cpus": int(allocation["AllocCPUS"]), "elapsed_s": int(allocation["ElapsedRaw"]),
            "reserved_cpu_s": int(allocation["TimelimitRaw"]) * 60 * int(allocation["AllocCPUS"]),
            "total_cpu_s": seconds(allocation["TotalCPU"]), "max_rss": step["MaxRSS"], "memory": allocation["ReqMem"]}


def fmt(value):
    return "未建立" if value is None else f"{value:.4f}".rstrip("0").rstrip(".")


def rows_markdown(report):
    result = ["# T3 原条件与新增 V_COST 的逐行对照", "",
              "每格依次为整窗服务缺额 L（秒）和人员实耗（人秒）。四个原臂直接取 T3 封存评分。", "",
              "| 条件 | V_COST | P | ORACLE | PERIODIC | ALARM |", "|---|---:|---:|---:|---:|---:|"]
    for row in report["rows"]:
        cells = []
        for role in ("V_COST", *ROLES):
            metrics = row["arms"][role]
            cells.append("未建立" if metrics is None else f"{fmt(metrics['L'])} / {fmt(metrics['person'])}")
        result.append(f"| {row['key']} | " + " | ".join(cells) + " |")
    result += ["", "## 同一条件上的配对差", "", "方向为 V_COST 减表头所列原臂，每格依次为秒和人秒。", "",
               "| 条件 | 对 P | 对 ORACLE | 对 PERIODIC | 对 ALARM |", "|---|---:|---:|---:|---:|"]
    for row in report["rows"]:
        arms = row["arms"]
        cells = [("未建立" if arms["V_COST"] is None else
                  " / ".join(fmt(arms["V_COST"][m] - arms[role][m]) for m in ("L", "person"))) for role in ROLES]
        result.append(f"| {row['key']} | " + " | ".join(cells) + " |")
    result += ["", "## 逐族均值和方向", "",
               "均值取同一组有效配对，最后一列依次为 V_COST 较低、持平、较高的行数。L 使用 T3 的 1e−7 秒数值容差，人员实耗直接比较。", "",
               "| 族 | 原臂 | 指标 | 配对/计划 | V_COST 均值 | 原臂均值 | 均差 | 优/平/劣 |",
               "|---|---|---|---:|---:|---:|---:|---:|"]
    for name, family in report["families"].items():
        for role in ROLES:
            for label, metric in (("L（秒）", "L"), ("人员（人秒）", "person")):
                s = family["comparisons"][role][metric]
                result.append(f"| {name} | {role} | {label} | {family['paired']}/{family['planned']} | "
                              f"{fmt(s['method_mean'])} | {fmt(s['comparator_mean'])} | "
                              f"{fmt(s['paired_mean_difference'])} | " + "/".join(map(str, s["better_equal_worse"])) + " |")
    return ("\n".join(result) + "\n").encode()


def witness(key, row):
    raw = gzip.decompress((HERE / ("ipc-" + key + ".jsonl.gz")).read_bytes())
    need(sha(raw) == row["files_sha256"]["ipc.jsonl"], "actual wire bytes " + key)
    records = [json.loads(line) for line in raw.splitlines()]
    need(len(records) == 2 + 2 * 61 + 1 and records[1]["return"] == {"ready": True, "role": "V_COST"}
         and records[-1] == {"worker_exit": 0}, "wire envelope " + key)
    encode = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    need(sha(encode(records[0]["send"]["public"])) == row["public_sha256"], "actual public static identity")
    ticks = [(records[i]["send"]["view"], records[i+1]["return"]) for i in range(2, len(records)-1, 2)]
    need([v["time"] for v,a in ticks] == list(range(0, 3601, 60)) and
         [[v["time"], a["request"]["task"]] for v, a in ticks if a["request"]] == row["requests"], "actual dispatch sequence")
    for tag, decision in row["decision_evidence"].items():
        view, answer = next((v, a) for v, a in ticks if a["request"] and a["request"]["task"] == tag)
        need(decision["public_view_sha256"] == sha(encode(view)) and decision["at"] == view["time"] and
             decision["request"] == answer["request"] and decision["reason"] == answer["rationale"]["reason"]
             and decision["winning_first"] == answer["rationale"]["winning_first"] and
             decision["posterior_groups"] == answer["rationale"]["posterior"]["groups"], "recorded choice " + tag)
        for k in ("records", "fixed", "paid", "writes"):
            need(decision["visible_" + k] == view[k], "dispatch-time evidence " + tag)
    for q in row["paid"]:
        msg = {k: v for k, v in q.items() if k != "first_visible_tick"}
        first = next((v["time"] for v, _ in ticks if msg in v["paid"]), None)
        need(first == q["first_visible_tick"] and (first is None or q["arrived"] <= first), "receipt publication " + q["origin"])
    return ticks


def check_representative(key, baseline, row):
    ticks = witness(key, row)
    ref = next(r for r in baseline["rows"] if r["key"] == key)
    arrival, tick, subject, start, sampled = ref["info"]["paid"]
    need(ref["info"]["paid_is_counterfactual_opportunity"] and (start, sampled, arrival, tick) == (0, 35, 50, 60),
         "dated counterfactual opportunity: " + key)
    paid = [q for q in row["paid"] if q["fields"] is not None]
    need(not any(q["subject"] == subject and q["phase"] == "I" and q["arrived"] <= ref["latest"] for q in paid),
         "claimed absence of the timely target read: " + key)
    if key == "5-01":
        need(subject == "LB" and ref["latest"] == 720 and row["requests"][0] == [720, "LB::A"] and
             (paid[0]["task"], paid[0]["sampled"], paid[0]["arrived"], paid[0]["first_visible_tick"],
              paid[0]["execution"]) == ("LB::R", 815, 830, 840, "LB::A@755"), "London observed action and receipt")
    else:
        need(subject == "NP" and ref["latest"] == 540 and row["requests"] == [[2040, "NP::A"]] and not paid
             and any(w["task"] == "NP::A" and w["outcome"] == "NO_EFFECT" and w["at"] == 2075
                     and w["arrived"] == 2090 for w in ticks[-1][0]["writes"]), "Netherlands observed action and outcome")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--rows", action="store_true")
    parser.add_argument("--checkout-bytes", action="store_true")
    args = parser.parse_args()
    execution = read("execution.json")
    need((HERE / "execution.json").read_bytes() == git("show", EXECUTION + ":" + REL + "/execution.json"),
         "actual execution lock")
    for name, value in execution["stage_files"].items():
        need(sha((HERE / name).read_bytes()) == value == sha(git("show", EXECUTION + ":" + REL + "/" + name)),
             "actual execution source: " + name)
    saved = read("development-return.json.gz")
    original = git("show", T3 + ":" + T3_PATH)
    need(sha(original) == execution["t3_results_sha256"], "original T3 scores")
    baseline = json.loads(gzip.decompress(original))
    derived = describe(baseline, saved["returns"])
    need(derived == read("comparison.json"), "server scoring tables vs original paired readback")
    table = rows_markdown(derived)
    if args.rows:
        sys.stdout.buffer.write(table)
        return
    need((HERE / "rows.md").read_bytes() == table, "published row and family tables")
    pilot = read("pilot-return.json")
    budget = read("batch-budget.json")
    groups = (pilot["terminal"], saved["terminal"])
    need([t["planned"] for t in groups] == [ROSTER[:1], ROSTER[1:]], "two authorized groups")
    identity = {r["key"]: r for r in read("compatibility.json")["handshakes"]}
    pairs = set()
    for terminal in groups:
        need(terminal["facility_entries"] == terminal["scored"] == terminal["planned"] and
             set(terminal["exit_codes"].values()) == {0} and not terminal["not_launched"], "group terminal")
        for k in terminal["scored"]:
            s = saved["returns"][k]
            need(s["execution_revision"] == EXECUTION and s["key"] == k and s["job"] == terminal["job"] and
                 s["input_sha256"] == identity[k]["input_sha256"] and s["public_sha256"] == identity[k]["public_sha256"]
                 and s["public_decisions"] == 61 and s["role"] == "V_COST" and s["status"] == "SCORED", "scored identity: " + k)
            body = json.dumps(s, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
            need(sha(body) == terminal["result_sha256"][k] and (s["job"], k) not in pairs, "native return hash: " + k)
            pairs.add((s["job"], k))
    need(saved["returns"][ROSTER[0]] == pilot["returns"][ROSTER[0]] and len(saved["returns"]) == len(pairs) == 24, "unique rows")
    processes = [(s["job"], s[field]) for s in saved["returns"].values() for field in ("host_pid", "worker_pid")]
    need(len(set(processes)) == 48, "separate original facility and worker process for each study position")
    for k in ("5-01", "6-02"):
        check_representative(k, baseline, saved["returns"][k])
    a, b = [accounting(label + "-accounting.psv", t["job"]) for label, t in zip(("pilot", "batch"), groups)]
    need(a["total_cpu_s"] == budget["pilot_actual_cpu_s"] and b["cpus"] == budget["cpus"] and
         b["reserved_cpu_s"] == budget["reserved_cpu_s"] <= 2 * 23 * a["total_cpu_s"], "batch resource gate")
    index = read("delivery.json")
    need(index["jobs"] == [a, b] and index["facility_calls"] == len(pairs) and
         index["public_decisions"] == sum(s["public_decisions"] for s in saved["returns"].values()), "accounting receipt")
    originals = read("originals.json")["files_sha256"]
    for group, terminal in zip(("pilot", "batch"), groups):
        for k in terminal["scored"]:
            pins = saved["returns"][k]["files_sha256"] | {"result.json": terminal["result_sha256"][k]}
            need(all(originals[group + "/" + k + "/" + name] == value for name, value in pins.items()),
                 "private original index: " + k)
    need(sha(gzip.decompress((HERE / "development-return.json.gz").read_bytes())) == originals["batch/public-return.json"]
         and sha((HERE / "pilot-return.json").read_bytes()) == originals["pilot/public-return.json"]
         and sha((HERE / "comparison.json").read_bytes()) == originals["batch/comparison.json"], "transferred original returns")
    need(sha((HERE / "execution.json").read_bytes()) == originals["source/execution.json"] and
         originals["source/execution.json"] != originals["staging-a1-source/execution.json"], "staged source boundary")
    for name, pin in index["files_sha256"].items():
        need(sha((HERE / name).read_bytes()) == pin, "delivery bytes: " + name)
    print("PASS published compatibility and execution identities; original T3 input hashes match all 24 V_COST rows")
    print("PASS 1 pilot + 23 batch entries; 24 unique facilities and 1464 public decisions; no retries or replacements")
    print("PASS full IPC for 5-01 and 6-02: actual dispatches, visible evidence and identified receipt arrival")
    print("PASS all 24 five-arm rows and both family summaries reconcile with archived T3 scores and the server readback")
    print("PASS terminal accounting and batch CPU reservation against the completed pilot")
    print("PASS private-original index: IPC, entry, native trace, score, worker log and individual result for each row")
    if args.checkout_bytes:
        anchor = git("log", "-1", "--format=%H", "HEAD", "--", REL + "/delivery.json").decode().strip()
        need(anchor, "published delivery commit")
        paths = {REL + "/" + n for n in (*index["files_sha256"], "delivery.json")}
        for rev in (anchor, "HEAD"):
            need(set(git("ls-tree", "-r", "--name-only", rev, "--", REL).decode().splitlines()) == paths, "full delivery tree")
            for path in paths:
                need((ROOT / path).read_bytes() == git("show", rev + ":" + path), "checked-out artifact: " + path)
        prior = "docs/mainline/t7-incident-counterfactual/r1/"
        for path in git("ls-tree", "-r", "--name-only", "9d6bfd45", "--", prior).decode().splitlines():
            need((ROOT / path).read_bytes() == git("show", "9d6bfd45:" + path), "accepted r1 file: " + path)
        need("Delivery-SHA256: " + sha((HERE / "delivery.json").read_bytes()) in
             git("show", "-s", "--format=%B", anchor).decode().splitlines(), "release hash trailer")
        print(f"PASS checkout bytes: {len(paths)} declared stage-1 artifacts, original r1 files, and delivery trailer")
    print("Delivery-SHA256:", sha((HERE / "delivery.json").read_bytes()))


if __name__ == "__main__":
    main()
