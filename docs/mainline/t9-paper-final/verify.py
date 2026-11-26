"""Verify the editorial closeout against published text. Reads no study panel or score archive."""

import argparse
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent
CLOSE = HERE.parent / "t8-closeout"
ROOT = HERE.parents[2]
T6 = "d9f0d5365e4aad97b2c5bfb99ee573cf93eed832"
T7 = "40949cb0c97511b901c180ce6f2334573119bcdb"
OLD = "a5da1c07123f64de272dbc588feb7e2317ea0d2a"
R3 = "docs/mainline/t6-paper-consolidation/r3/"
INC = "docs/mainline/t7-closeout/"
FIT = "docs/mainline/t8-rsi-wait-repair/stage1b/"
PUBLIC = {R3 + n for n in ("manuscript.md", "manuscript-numbers.json", "evidence-notes.md")}
PUBLIC.update({INC + "manuscript.md", INC + "numeric-sources.md",
               "docs/mainline/t7-incident-counterfactual/stage1/witnesses.md",
               "docs/mainline/t7-incident-counterfactual/contamination.md"})
PUBLIC.update(FIT + n for n in ("analysis/HANDOFF.md", "analysis/statistics.json", "analysis/tables.md",
                                 "results/report.md", "fit-overlap/README.md"))
PIN = re.compile(r"\[([^\]]+)\]\(https://github\.com/DonsonHH/AegisDC/blob/([0-9a-f]{40})/([^#)]+)#L(\d+)(?:-L(\d+))?\)")
ANCHOR = re.compile(r'<a id="([\w-]+)"></a>')


def require(condition, name):
    if not condition:
        raise ValueError(name)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


@lru_cache(maxsize=None)
def published(revision, name):
    require(name in PUBLIC, "source outside the published-text list: " + name)
    return git("cat-file", "blob", f"{revision}:{name}").decode("utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def check_sources(folder):
    ledger = read(folder / "numeric-sources.md")
    groups = {}
    for line in ledger.splitlines():
        anchor = ANCHOR.search(line)
        if not anchor:
            continue
        key = anchor[1]
        require(key not in groups, "repeated source anchor: " + key)
        refs = PIN.findall(line)
        require(refs, "missing line evidence: " + key)
        entries = []
        for label, revision, path, first, last in refs:
            if folder == CLOSE:
                require(path.startswith(FIT), "T8 numerical source outside stage1b")
            lines = published(revision, path).splitlines()
            start, end = int(first), int(last or first)
            require(1 <= start <= end <= len(lines) and lines[start-1].strip() and lines[end-1].strip(),
                    "empty or missing source line: " + label)
            require(label.endswith(":" + first + ("–" + last if last else "")), "line label disagrees")
            entries.append((revision, path, start, end, "\n".join(lines[start-1:end])))
        groups[key] = entries
    for file in folder.glob("*.md"):
        for dest in re.findall(r"\]\(([^)]+)\)", read(file)):
            if "://" in dest:
                continue
            name, _, fragment = dest.partition("#")
            target = (file.parent / name).resolve() if name else file
            require(target.exists(), file.name + " missing link: " + dest)
            if target == folder / "numeric-sources.md" and fragment:
                require(fragment in groups, file.name + " missing numerical anchor: " + fragment)
    return groups


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = False
        self.text = []
        self.headings = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.hidden = True
        if tag == "h2":
            self.headings += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.text.append(data.strip())


def check():
    close = check_sources(CLOSE)
    main = check_sources(HERE)
    require(all(main[k] == v for k, v in close.items()), "different T8 sources in the two editions")
    paper = read(HERE / "manuscript.md")
    old_paper = published(T6, R3 + "manuscript.md")
    num = r"\[([^\[\]]+)\]\((?:evidence-notes|numeric-sources)\.md#(n\d{3})\)"
    original = json.loads(published(T6, R3 + "manuscript-numbers.json"))["occurrences"]
    expected = Counter((v["display"], k) for k, v in original.items())
    require(Counter(re.findall(num, old_paper)) == Counter(re.findall(num, paper)) == expected,
            "inherited numerical values or denominator changed")
    for key, info in original.items():
        revision, path, first, last, entry = main[key][0]
        require((revision, path) == (T6, R3 + "evidence-notes.md") and first == last and
                entry.startswith("**" + info["display"] + "**") and info["id"] in entry, "old source binding: " + key)
    require(re.findall(r"^## (C[1-4]) ", paper, re.M) == ["C1", "C2", "C3", "C4"], "four-claim structure")
    for folder in (CLOSE, HERE):
        rows = re.findall(r"^\| (C[1-4])[^|]+\| ([^|]+)\|", read(folder / "claims.md"), re.M)
        require([c for c, _ in rows] == ["C1", "C2", "C3", "C4"] and
                all(value.strip().startswith(s) for (_, value), s in zip(rows, ("部分成立","部分成立","不成立","未建立"))),
                "claim statuses: " + folder.name)
    print(f"PASS four claim statuses, {len(original)} inherited numerical occurrences and their original line bindings")

    def section(header, next_header):
        return paper.split("## " + header, 1)[1].split("\n## " + next_header, 1)[0]

    c1 = section("C1 ", "C2 ")
    for hypothesis, anchor in (("H1", "n003"), ("H2", "n006"), ("H3", "n007")):
        require(hypothesis in c1 and "numeric-sources.md#" + anchor in c1, "C1 " + hypothesis)
    observations = published(T7, INC + "manuscript.md").splitlines()
    for idx, hypothesis in ((22, "HA"), (23, "HB"), (24, "HC")):
        row = next(l for l in paper.splitlines() if l.startswith("| " + hypothesis + " |"))
        numbers = re.findall(r"[−+]\d+\.\d+", observations[idx])
        require(all(n in row for n in numbers) and ("INDETERMINATE" if hypothesis == "HC" else "MET") in row,
                "T7 hypothesis comparison and reported interval: " + hypothesis)
    require(all(s in paper for s in ("90 行", "45 行归零", "30 行", "新增事件为 0", "现场事件频率端仍未建立",
                                      "830 秒", "2040 秒")), "event denominators or actual purchase witnesses")
    c3, c4 = section("C3 ", "C4 "), section("C4 ", "局限")
    require(all(s in c3 for s in ("v1", "v2", "v3a", "v3b", "v3c", "−141.13", "+80.49", "18.96", "15 秒")),
            "ordinary search history and FIT tradeoff")
    archived = published(OLD, FIT + "analysis/tables.md")
    winning_row = next(l for l in archived.splitlines() if l.startswith("| ORDER_FAR=3 |")).split("|")
    loss, cost = map(Decimal, winning_row[5].strip().split(" / "))
    dutch = next(l for l in archived.splitlines() if l.startswith("| Q3-N |") and "person" in l).split("|")
    upper = Decimal(dutch[8].strip())
    require(f"{abs(loss)} 秒" in c3 and f"{cost:.2f}" in c3 and f"{upper:+.3f}" in c3 and "情景预测" in c3,
            "actual vs projected service and labor")
    require(all(s in c4 for s in ("未建立", "付费批次的候选为 0", "等价", "ORDER_FAR=3", "ALARM_NEAR=3",
                                   "ORDER_NEAR=3", "48 行", "42 行", "6 行", "未评分")), "C4 attribution and menu limits")
    limits = [s for s in section("局限", "结论").splitlines() if s.strip()]
    require(len(limits) == 4 and all(s.count("。") == 1 and PIN.search(s) and k in s
                                    for s, k in zip(limits, ("块", "配额", "同账号", "公开事故"))), "four sourced limitations")
    future = [s for s in section("未来工作", "附录").splitlines() if s.strip()]
    require(len(future) == 1 and all(s in future[0] for s in
            ("相同工时约束", "更早找到", "公开信息", "4 行", "5.83", "ALARM_FAR=3", "4.375", "新材料", "新的查重门",
             "付费", "锁定父链", "相对 O")), "future question and attribution")
    for doc in (paper, read(CLOSE / "README.md")):
        require("有异议、未独立证实" in doc and "同账号程序性查重" in doc and "PASS 回执" in doc,
                "procedural custody and disputed attribution")
    print("PASS T7 HA/HB/HC, event denominators, ordinary search history, FIT mechanism, scope and four limitations")
    page = PageText()
    page.feed(read(HERE / "review.html"))
    visible = " ".join(page.text)
    require(page.headings == 4 and all(s in visible for s in
            ("343.90", "55.83", "390.48", "−580.00", "−595.52", "−564.48", "−582.08", "−612.65", "−551.51",
             "INDETERMINATE", "30 行", "−15", "+18.96", "+38.15", "48/48", "PASS")), "visible one-page findings")
    print(f"PASS {len(close)} T8 source groups, {len(main)-len(original)} T9 updated source groups and four visible summary panels")


def checkout():
    allowed = tuple(f"docs/mainline/{p.name}/" for p in (CLOSE, HERE))
    changes = git("diff", "--name-status", "--no-renames", OLD, "HEAD").decode().splitlines()
    require(changes and all(s.startswith(tuple("A\t"+p for p in allowed)) for s in changes), "protected tree changed")
    for change in changes:
        name = change.split("\t", 1)[1]
        require((ROOT / name).read_bytes() == git("cat-file", "blob", "HEAD:" + name), "checkout bytes: " + name)
    print(f"PASS {len(changes)} new release files match Git byte-for-byte; changes confined to the two approved directories")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--checkout-bytes", action="store_true")
    args = parser.parse_args()
    check()
    if args.checkout_bytes:
        checkout()
