"""Typeset the post-hoc panel from the already sealed Slurm readout; no statistics are recomputed."""
import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
RESULTS=HERE/"results"
OAT_NAMES={
    "lambda_low":"Labour price λ = 0.5", "lambda_high":"Labour price λ = 2",
    "kappa_low":"Fee equivalent κ = 15", "kappa_high":"Fee equivalent κ = 60",
    "match_low":"Sensor match p = 0.85", "match_high":"Sensor match p = 0.99",
    "unknown_low":"Uninterpretable report q = 1/64","unknown_high":"Uninterpretable report q = 1/16",
}
NAMES={"V_COST":"Frozen centre","MYOPIC":"Myopic VoI","POMCP":"Finite-budget POMCP",**OAT_NAMES}
def read(p):return json.loads(p.read_bytes())
def fmt(v):return "unestablished" if v is None else f"{v:.2f}"
def estimate(pair,endpoint):
    if pair["compliant_full_scope"] is None:return "indeterminate"
    v=pair["compliant_full_scope"][endpoint]
    return f'{fmt(v["mean"])} [{fmt(v["lo"])}, {fmt(v["hi"])}]'

def panel():
    acc=read(RESULTS/"accounting.json")
    out=["# Supplementary panel: online planning and policy-parameter sensitivity","",
         "**Post hoc, nonconfirmatory.** The panel was fixed to the 72 previously consumed development conditions. "
         "The archived centre policy retained its original scores. Each new arm had its own state, evidence, resources and receipts.",""]
    datafile=RESULTS/"analysis"/"analysis.json"
    if not datafile.is_file():
        out.extend([f'The allocation ledger records {acc["charged_native_calls"]} new facility calls. '
                    'No qualified statistical readback is available. The planned denominators are retained and no service advantage is inferred.',
                    "","[Execution ledger](results/per-role-ledger.tsv)"])
        return "\n".join(out)+"\n"
    data=read(datafile)
    overall=data["scopes"]["overall"]; absolute=overall["absolute"]; pairs=overall["pairs"]
    out+=["## Alternative online methods","",
         "Differences below are centre minus comparator. Negative service deficit means the centre lost less service. "
         "Intervals are two-sided 95% marginal percentile intervals from the registered 10,000 paired, within-family resamples.","",
         "| Comparator | Compliant pairs / planned | Deficit difference, s [95% interval] | Labour difference, person-s [95% interval] | Fee difference [95% interval] |",
         "|---|---:|---:|---:|---:|"]
    for role in ("MYOPIC","POMCP"):
        pair=pairs[role]
        out.append(f'| {NAMES[role]} | {pair["pairable"]}/{pair["planned"]} | {estimate(pair,"L")} | {estimate(pair,"person")} | {estimate(pair,"fee")} |')
    wording={"BASELINE_WORSE":"The centre had lower mean deficit than this comparator under the specified budget.",
             "BASELINE_BETTER":"The comparator had lower mean deficit than the centre on these conditions.",
             "NO_DIRECTION":"The interval included zero. This comparison did not establish a directional advantage.",
             "INDETERMINATE":"The compliant full-panel contrast is indeterminate."}
    for role in ("MYOPIC","POMCP"):
        p=pairs[role];grp=data["interpretation"][role]["case"]
        out.extend(["",f'**{NAMES[role]}.** '+wording[grp]+
                    (f' The raw deficit was equal on all {p["planned"]} conditions. The issued request sequence differed on '
                     f'{p["request_sequence_different_rows"]} conditions.' if p["raw_L_equal_rows"]==p["planned"] else "")])
    out+=["","## One-at-a-time sensitivity","",
          "Each row changes one setting of the frozen centre. Differences now run from variant to centre (variant minus centre). "
          "Positive deficit means more service lost by the variant. The physical facility and accounting rules use their original settings.","",
          "| Changed parameter | Pairs / planned | Absolute deficit, s | Deficit difference, s [95% interval] | Absolute labour, person-s | Fee units |",
          "|---|---:|---:|---:|---:|---:|"]
    for role,label in OAT_NAMES.items():
        p=pairs[role];mean=absolute[role]["compliant_full_scope_means"] or {}
        out.append(f'| {label} | {p["pairable"]}/{p["planned"]} | {fmt(mean.get("L"))} | {estimate(p,"L")} | '
                   f'{fmt(mean.get("person"))} | {fmt(mean.get("fee"))} |')
    out+=["","## Absolute service, resource use and work closure","",
          "Rows give condition means over each complete compliant scope. Refusals count the recorded candidate/admission "
          "refusal entries. Failed or unfinished work is reported from the actual workforce records. NA and PV count "
          "valid closures at window end, respectively without intervention and after verification of an applied intervention.","",
          "| Policy | Deficit, s | Person-s | Tool-s | Fees | Refusal entries | Failed / unfinished work | NA / PV at 3,600 s | Hard / unresolved started positions |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for role in ("V_COST","MYOPIC","POMCP",*OAT_NAMES):
        role_data=absolute[role]; vals=role_data["compliant_full_scope_means"] or {};counts=role_data["counts"]
        out.append("| "+" | ".join([NAMES[role],*[fmt(vals.get(key)) for key in ("L","person","tool","fee","refusals")],
                   fmt(vals.get("failed_work"))+" / "+fmt(vals.get("unfinished_work")),
                   fmt(vals.get("NA_3600"))+" / "+fmt(vals.get("PV_3600")),
                   str(counts["hard_violations"])+" / "+str(counts["started_legality_unresolved"])])+" |")
    out+=["","## Decision time and scope","",
          "| Policy / measurement | Returned timed decisions | Median, ms | 95th percentile, ms | Maximum, ms |",
          "|---|---:|---:|---:|---:|"]
    for role in ("V_COST","MYOPIC","POMCP"):
        row=data["timing"][role]
        dist=row["groups"]["ALL"]["timing_ns"]["ipc_wall_ns"]
        ms=lambda val:"unavailable" if val is None else f"{val/1_000_000:.3f}"
        label=NAMES[role]+" / "+row["source"].replace("_"," ")
        out.append(f'| {label} | {dist["n"]} | {ms(dist["median"])} | {ms(dist["p95"])} | {ms(dist["max"])} |')
    out+=["","Wall time spans public request serialization through response parsing. The centre timing source is identified in the table. "
          "Isolated replay uses archived public decisions whose returned proposals match their historical digests. Replay creates no new facility score. "
          "The timing ledger separates startup and reports worker CPU where observed, tree time and terminal evaluation time.",
          "",f'The run charged {acc["charged_native_calls"]} native entries and retained {acc["complete_new_scores"]} complete compliant scores. '
          "The two additional comparisons qualify the interpretation of C1 on this development panel. C1 and C2 retain partial support, "
          "the registered C3 transfer advantage remains unsupported, and an independent C4 increment remains unestablished. "
          "Original hypothesis tests and incident results retain their previous dispositions.","",
          "[Absolute resources, refusals and closures](results/analysis/scope-absolute.tsv) · "
          "[Paired endpoints and identification bounds](results/analysis/scope-contrasts.tsv) · "
          "[Timing by role and reason](results/analysis/timing.tsv) · [Complete development report](results/analysis/panel.md)"]
    return "\n".join(out)+"\n"

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true")
    args=parser.parse_args();path=HERE/"manuscript-panel-en.md";expected=panel().encode()
    if args.write:path.write_bytes(expected)
    elif path.read_bytes()!=expected:raise ValueError("English panel differs from sealed values")
