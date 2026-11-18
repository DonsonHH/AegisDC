"""Static transfer audit and review manifests, inside the preparation allocation."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
import os

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import BASE, FIXTURE, OLD, PACK, REAL, ROOT, STUDY_OUTPUT, durable, file_sha, need, read
from make_manifest import construct
from prepare_conditions import build, encoded, get_public_configs, mechanism, static_certificate

SOURCES={
    "plant":"docs/mainline/review-gated/R2/extensions/e1-e4-v2/cases.json",
    "admission":"docs/mainline/review-gated/R2/extensions/read-verify-admission-v1/cases.json",
    "runner":"docs/mainline/review-gated/R3/runner-v1/engineering-cases.json",
    "guards":"docs/mainline/review-gated/R3/runner-v1/guards.json",
    "entry":OLD+"inputs.json"}
PREFIXES={
    "A01 B01":"runner/E03 entry/X01 entry/X02",
    "A02":"plant/I11-revised plant/A07 runner/E03",
    "A03 B02":"runner/E01 runner/E11 entry/X07",
    "B03":"runner/E12 plant/S08 entry/X08",
    "C01":"plant/I03a plant/I03b runner/E04",
    "D01":"runner/E08 admission/F10-c4-budget-equal-B1",
    "E01":"runner/E05","E02":"runner/E06 plant/A03-commit","E03":"entry/X03 plant/A03-guard",
    "E04":"runner/E07","E05":"entry/X04 plant/A06c",
    "F01":"runner/E16 plant/C05-ready entry/X05","F02":"plant/C05-permit entry/X05 entry/X06",
    "G01 G02 G03 G04 G05 G06":"plant/T01 plant/T02 plant/T03 runner/E02 runner/E14",
    "H01 H02":"plant/T10 runner/E10",
    "H03 H04 H05 H06":"plant/T10 admission/F09-c4-budget-short-B1 admission/F10-c4-budget-equal-B1",
    "J01 J02 J03 J04":"admission/F05-c4-window-short-B1 admission/F06-c4-window-equal-B1 admission/F02-c7-long-verify-B1 entry/X07",
    "K01 K02":"runner/E09 runner/E15 admission/F07-c4-queue-B1 entry/X07",
    "L01":"plant/T09 plant/S13","L02":"plant/S02 entry/X05 entry/X06"}
BASIS={slot:items.split() for slots,items in PREFIXES.items() for slot in slots.split()}
GLOBAL=["runner/E13","guards/G01","guards/G02","guards/G03","guards/G04"]


def sources(refs):
    result=[]
    for ref in refs:
        source,prefix=ref.split("/")
        path=SOURCES[source];document=read(ROOT/path)
        ids=[r.get("id",r.get("condition_id")) for r in document.get("units",document.get("conditions",[]))]
        matches=[s for s in ids if s==prefix or s.startswith(prefix+"-")]
        need(len(matches)==1,"EVIDENCE_REFERENCE:"+ref)
        result.append(dict(path=path,id=matches[0]))
    return result


def scope_note(slot,c,cert):
    ri=cert["I"];rd=cert["D"];reads=cert["reads"]
    if slot in ("A01","B01","A02"):
        record=reads[2 if slot=="A02" else 0]
        return f"{record['source']} 在 {record['available']} 到达，至 {record['expires']} 前有效。D 正常复核在 {rd['verify_arrival']} 发布。"
    if slot in ("A03","B02","B03"):
        return f"I／D 名义作业开工 {ri['fix_start']}/{rd['fix_start']}，名义退出 {ri['exit_end']}/{rd['exit_end']}。记录实际隔离和退出。"
    if slot=="C01":return f"POS 无结论路径仍有 VOLT／CONFIG 在 {reads[1]['available']}/{reads[2]['available']} 的合法资料机会。"
    if slot=="D01":return f"D 缺 direct 许可，I 资料合法且名义修订申请可在 {ri['request']} 提出。"
    if slot.startswith("E"):
        field={"E01":"approval","E02":"commit","E03":"guard","E04":"verification","E05":"verification"}[slot]
        clocks={"approval":"approval","commit":"commit","guard":"commit","verification":"verify_arrival"}
        stage=clocks[field]
        return f"{field}={c[field]}，I／D 正常前序到计划检查点 {ri[stage]}/{rd[stage]}。按回执及实际阶段核对。"
    if slot.startswith("F"):return f"两条核验链在 {ri['verify_arrival']}/{rd['verify_arrival']} 可达，挑战 {c['tF']}。以 g_state 与实际供给段识别后备父条件。"
    if slot.startswith("G"):
        chain=rd if slot<="G03" else ri
        return f"名义提交 {chain['commit']}，截断 {c['tF']}，严格比较完成时点，安全退出照常计费。"
    if slot.startswith("H"):
        threshold=(reads[2]["prior_spent"]+reads[2]["reserve"] if slot<="H02" else (rd if slot<="H04" else ri)["min_budget"])
        return f"已消耗加所需预留的阈值 {threshold}，两种资源各 {c['budget']}。以实际请求及准入区别读取与完整修订。"
    if slot.startswith("J"):
        chain=rd if slot<="J02" else ri
        return f"发布 {chain['verify_arrival']} 必须小于窗口末，预留末 {chain['verify_reserve_end']} 可等于窗口末 {c['window'][1]}。"
    if slot.startswith("K"):return f"首读排至 {reads[0]['start']}，I／D 名义提交 {ri['commit']}/{rd['commit']}。依据实际队列、截断与回执核对。"
    return f"tF={c['tF']}，恢复端为 {c['tR'] if c['tR'] is not None else 'NEVER'}。分开核对PRE关闭、A源右状态、全窗服务及恢复删失。"


def main(output):
    output.mkdir(exist_ok=False)
    scratch=output/"static-reconciliation"
    scratch.mkdir()
    result=build(scratch)
    original=ROOT/(PACK+"conditions.json")
    need((scratch/"conditions.json").read_bytes()==original.read_bytes(),"FIRST_ELIGIBLE_SELECTION_CHANGED")
    audit=read(scratch/"static-audit.json");old=read(ROOT/(PACK+"static-audit.json"))
    need(audit["attempts"]==old["attempts"],"GROUP_REFUSAL_SEQUENCE_CHANGED")
    baseline=read(ROOT/(OLD+"public-dedup.json"))
    prior=get_public_configs(baseline)
    profiles={key:mechanism(c,static_certificate(c)) for key,c in prior.items()}
    historic_revocations={k:dict(revoke=c["revoke"],projection=profiles[k]) for k,c in prior.items() if c["revoke"]}
    rules=read(ROOT/(PACK+"selection.json"))
    input_rows={r["condition_id"]:r for r in read(original)["conditions"]}
    # Independent fixed literal boundary calculations from the written-domain review.
    for ids,field,wants in [
        (["G01","G02","G03","G04","G05","G06"],"tF",[4,5,6,11,12,13]),
        (["H01","H02","H03","H04","H05","H06"],"budget",[4,5,7,8,10,11]),
        (["J01","J02","J03","J04"],"window",[[0,10],[0,11],[0,17],[0,18]]),
        (["F01","F02"],"tF",[17,17])]:
        need([input_rows[s]["common"][field] for s in ids]==wants,"STATIC_BOUNDARY:"+field)
    for group in rules["groups"]:
        reference=input_rows[group["slots"][0]]["common"]
        for slot in group["slots"][1:]:
            c=input_rows[slot]["common"]
            need({k for k in c if c[k]!=reference[k]}.issubset(group["paired_fields"]),"GROUP_BACKGROUND:"+slot)
    need(len({r["canonical_sha256"] for r in input_rows.values()})==35 and not set(prior).intersection(r["canonical_sha256"] for r in input_rows.values()),"EXACT_DEDUP")
    rows=[];summary=["# 35个槽位的静态前提与资格承接","","时刻单位为秒。下表给出每行入组前可核对的条件。实际到达阶段留给获授权后的归档轨迹。既有工程依据的完整路径和单位 ID 见 [static-transfer.json](static-transfer.json)。","","| 槽位 | 同背景组 | 静态前提与实际取证依据 | 对应有限见证 |","|---|---|---|---|"]
    for row in audit["rows"]:
        slot=row["slot"];c=input_rows[slot]["common"];sig=row["static_mechanism"];cert=row["public_certificate"]
        diffs=collections.Counter()
        for other in profiles.values():
            discriminant=next((k for k in sig if sig[k]!=other[k]),None)
            need(discriminant is not None,"SEMANTIC_DUPLICATE:"+slot)
            diffs[discriminant]+=1
        refs=sources(BASIS[slot]);note=scope_note(slot,c,cert)
        rows.append(dict(slot=slot,group=row["group"],canonical_sha256=row["canonical_sha256"],
                    transfer_status="SUPPORTED_BY_NAMED_FINITE_WITNESSES_AND_ROW_ARITHMETIC_FOR_REVIEW",
                    static_eligibility=note,source_witnesses=refs,nearest_public=row["nearest_disclosed"],
                    all_public_differences_by_first_active_field=diffs,disclosed_compared=len(profiles),
                    study_coverage_observed=None,additional_facility_calls=0))
        summary.append("| "+" | ".join([slot,"/".join(row["members"]),note,", ".join(r["id"] for r in refs)])+" |")
    summary.extend(["","全部槽位共同继承已经接受的组间隔离、冻结需求评分和失败留存见证 E13、G01–G04。各行对整秒配方作解析迁移，正式运行前由用户审阅。","",
        "三份旧配置含权限或授权撤销。首次静态审计对这些旧配置给出了过宽的行动机会。追加审计用原规则顺序重新核对全部组，校正撤销、无结论与权限守卫的来源定位。原始清单和首次审计均可追溯。"])
    (output/"qualification.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    durable(output/"static-transfer.json",dict(passed=True,model_calls=0,source_revision=read(ROOT/"staged.json")["revision"],
        input_sha256=file_sha(original),original_static_audit_sha256=file_sha(ROOT/(PACK+"static-audit.json")),
        corrected_detailed_audit_sha256=file_sha(scratch/"static-audit.json"),selection_order_unchanged=True,all_rejections_identical=True,
        public_revocation_projections=historic_revocations,global_witnesses=sources(GLOBAL),counts=result,rows=rows,unresolved_slots=[]))
    suite=construct("suite",BASE/"witness-suite-01")
    durable(output/"suite.json",suite)
    for slot,purpose in [("W02","CONFIRMATION"),("W15",REAL)]:
        durable(output/(slot+".json"),dict(suite,purpose=purpose))
    durable(output/"serial.json",construct("serial",BASE/"witness-serial-01"))
    print(json.dumps(dict(static_review=result,manifests={f.name:file_sha(f) for f in output.glob("*.json")},real_calls=0)))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("output",type=Path)
    need(os.environ.get("SLURM_JOB_ID"),"SLURM_REQUIRED")
    main(p.parse_args().output)
