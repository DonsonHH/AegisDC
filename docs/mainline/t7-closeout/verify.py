"""Check manuscript citations and primary statistics against published Git blobs."""

import re
import subprocess
import sys
from decimal import Decimal
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVISION = "72d10c07250cd43395cff7ad07e3c1d325c8e3e7"
STUDY = "docs/mainline/t7-incident-counterfactual/"
PUBLIC_FILES = {
    STUDY + name for name in (
        "README.md", "contamination.md", "r1/registration.json", "stage1/README.md",
        "stage2/README.md", "stage2/protocol.md", "stage2/tables.md",
    )
} | {"docs/mainline/t6-paper-consolidation/r3/manuscript.md"}
LINK = re.compile(r"\[([^\[\]\n]+)\]\[([a-z-]+)\]")
DEFINITION = re.compile(r"^\[([a-z-]+)\]: (\S+)$", re.M)
NUMBER = re.compile(r"[−-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?[⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹]*")
RESTRICTED = ("事故" + "可避免", "确认降低" + "事故率", "主动采样" + "提前发现")


def require(condition, message):
    if not condition:
        raise ValueError(message)


@cache
def published(path):
    require(path in PUBLIC_FILES, f"Undeclared source: {path}")
    return subprocess.check_output(
        ["git", "cat-file", "blob", f"{REVISION}:{path}"],
        cwd=HERE.parents[2], encoding="utf-8",
    ).splitlines()


def citations(source_map):
    prefix = f"https://github.com/DonsonHH/AegisDC/blob/{REVISION}/"
    cited = {}
    for key, target in DEFINITION.findall(source_map):
        match = re.fullmatch(re.escape(prefix) + r"([^#]+)#L(\d+)(?:-L(\d+))?", target)
        require(key not in cited and match, f"Invalid source reference: {key}")
        path, first, last = match.groups()
        lines = published(path)
        start, end = int(first), int(last or first)
        require(1 <= start <= end <= len(lines), f"Invalid source lines: {key}")
        cited[key] = lines[start - 1:end]

    groups = {}
    group_sources = {}
    used_sources = set()
    for key, facts, refs in re.findall(r'^\| <a id="([a-z-]+)"></a>[^|]+\| ([^|]+)\| (.+) \|$', source_map, re.M):
        labels = set(re.findall(r"\]\[([a-z-]+)\]", refs))
        require(key not in groups and labels and labels <= cited.keys(), f"Invalid source group: {key}")
        used_sources.update(labels)
        groups[key] = facts
        group_sources[key] = labels
    require(used_sources == cited.keys(), "Unused or missing source references")
    return cited, groups, group_sources


def cells(line):
    return [cell.strip() for cell in line.strip("|").split("|")]


def holm_display(value):
    mantissa, exponent = f"{Decimal(value):.2E}".split("E")
    power = str(int(exponent)).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{mantissa}×10{power}"


def visible(line):
    # Printed source filenames, line numbers and reference definitions are metadata.
    return LINK.sub(lambda match: "" if ":" in match[1] else match[1], line)


def check_paired_counts(manuscript, cited):
    def numbers(prefix):
        line = next(line for line in manuscript.splitlines() if line.startswith(prefix))
        return [int(number) for number in NUMBER.findall(visible(line))]

    passive = [cells(cited[key][0]) for key in ("london-passive", "netherlands-passive")]
    directions = zip(*(map(int, row[4].split("/")) for row in passive))
    pairs = sum(int(row[2].split("/")[0]) for row in passive)
    require(numbers("相对仅保留既有保护的 P")[1:] == [pairs, *map(sum, directions)], "P paired L counts")
    event_rows = [list(map(int, cells(line)[1:])) for line in cited["pairs"][-2:]]
    neither, removed, new, both, missing = map(sum, zip(*event_rows))
    require(missing == 0 and numbers("在 P 有缺额的") == [removed + both, removed, both, neither + new, new],
            "Event counts and conditional denominators")
    wait = re.search(r"(\d+)/\d+ 行可判。.*?(\d+) 行满足等待失败。.*?其中与等待失败相交 (\d+) 行", cited["wait"][0])
    require(wait and numbers("荷兰族 60 个条件中") == list(map(int, wait.groups())), "Waiting witness intersection")


def check():
    manuscript = (HERE / "manuscript.md").read_text(encoding="utf-8")
    source_map = (HERE / "numeric-sources.md").read_text(encoding="utf-8")
    require(all(term not in manuscript + source_map for term in RESTRICTED), "Restricted wording")
    cited, groups, group_sources = citations(source_map)
    map_targets = dict(DEFINITION.findall(source_map))
    paper_targets = dict(DEFINITION.findall(manuscript))
    require(all(map_targets.get(key) == url for key, url in paper_targets.items()), "Unpinned manuscript source")
    headings = re.findall(r"^## (.+)$", manuscript, re.M)
    require(headings == ["设计", "主结果", "事故是否避免", "人力取舍", "失败型", "局限"], "Manuscript headings")
    used_groups = set()
    used_targets = set()
    for line_no, line in enumerate(manuscript.splitlines(), 1):
        if not line or line.startswith(("#", "|---", "[数字溯源表]")) or DEFINITION.fullmatch(line):
            continue
        refs = LINK.findall(line)
        require(refs, f"Missing direct source on manuscript line {line_no}")
        for label, key in refs:
            require(key in paper_targets, f"Missing direct source: {key}")
            if (label, key) != ("95% 区间", "table-header"):
                path, span = label.split(":")
                require(paper_targets[key].endswith("/" + path + "#L" + span.replace("–", "-L")),
                        f"Printed source locator differs: {label}")
        keys = {key for _, key in refs}
        used_targets.update(keys)
        matches = {group for group, sources in group_sources.items() if keys & sources}
        used_groups.update(matches)
        missing = set(NUMBER.findall(visible(line))) - set(NUMBER.findall(" ".join(groups[key] for key in matches)))
        require(not missing, f"Unmapped numerals on manuscript line {line_no}: {missing}")
    require(used_groups == groups.keys(), "Unused source groups")
    require(used_targets == paper_targets.keys(), "Unused manuscript source definitions")
    check_paired_counts(manuscript, cited)

    for key in ("ha", "hb", "hc"):
        original = cells(cited[key][0])
        row = cells(next(line for line in manuscript.splitlines() if line.startswith(f"| {key.upper()} |")))
        require(len(row) == 7 and LINK.fullmatch(row[-1])[2] == key, f"Primary table source: {key}")
        displayed = row[2:6]
        unit = " 个百分点" if key == "hc" else " 秒"
        estimate = original[3].replace("-", "−") + unit
        interval = original[4] if key == "hc" else original[4].replace("-", "−") + unit
        adjusted = original[6] if key == "hc" else holm_display(original[6])
        require(displayed == [estimate, interval, adjusted, original[7]], f"Published result differs: {key}")
        require(original[5] in groups[key], f"Original p missing in source table: {key}")
    print(f"PASS: {len(headings)} sections, {len(groups)} source groups, {len(cited)} pinned line ranges, "
          f"{len(used_targets)} direct manuscript sources. Primary statistics, paired counts, "
          "waiting witness intersection and wording verified.")


if __name__ == "__main__":
    if sys.argv[1:] != ["--check"]:
        raise SystemExit("Usage: python -B verify.py --check")
    check()
