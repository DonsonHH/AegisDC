"""Read the numbers that the published T7/T8 vectors actually draw.

The SVG tick marks calibrate points to data units. The standalone PDF uses the
same physical point coordinates, with its y axis reversed. Decode both and
compare with frozen public aggregates, independently of the plotting script.
"""
from collections import defaultdict
from decimal import Decimal
import json
import math
import re
from xml.etree import ElementTree

from pypdf import PdfReader


INK = {"086a98", "cbd3d8", "536a78", "b24d13"}
HREF = "{http://www.w3.org/1999/xlink}href"
NUMBER = r"[-+]?\d+(?:\.\d+)?"
CELLS = ("DIRECT_NEAR", "ALARM_NEAR", "ORDER_NEAR", "DIRECT_FAR", "ALARM_FAR", "ORDER_FAR")


def check(ok, why):
    if not ok:
        raise ValueError("Figure data: " + why)


def close(actual, expected, why, tolerance=.00002):
    check(math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance),
          f"{why}: {actual:g} vs {expected:g}")


def pdf_marks(page):
    """Read closed, filled data marks inside each Matplotlib axes clipping box."""
    height = float(page.mediabox.height)
    panels = defaultdict(list)
    stack = []
    fill, clip, transformed = "", None, False
    rect, points = None, []
    for args, op in page.get_contents().operations:
        if op == b"q":
            stack.append((fill, clip, transformed))
        elif op == b"Q":
            fill, clip, transformed = stack.pop()
        elif op == b"cm":
            transformed = True
        elif op == b"re":
            rect = tuple(map(float, args))
        elif op == b"W":
            clip = rect
        elif op == b"rg":
            fill = "".join(f"{round(255*float(c)):02x}" for c in args)
        elif op == b"g":
            fill = ""
        elif op in (b"m", b"l", b"c"):
            points.extend(zip(map(float, args[::2]), map(float, args[1::2])))
        elif op in (b"B", b"S", b"f", b"n"):
            if op == b"B" and clip and fill in INK and points:
                check(not transformed, "unexpected PDF transform on a data mark")
                xs, ys = zip(*points)
                panels[clip].append((fill, min(xs), max(xs), height-(max(ys)+min(ys))/2))
            points = []
    check(len(panels) == 2, "expected two measured PDF axes")
    return [panels[k] for k in sorted(panels)]


def glyph_label(group):
    """Decode visible font references and their origins; ignore SVG comments."""
    run = next(g for g in group.iter("g") if "translate(" in g.get("transform", ""))
    xy = re.search(r"translate\(([^)]+)\)", run.get("transform"))[1].split()
    glyphs = [chr(int(use.get(HREF).rsplit("-", 1)[1], 16)) for use in run.iter("use")]
    return "".join(glyphs).strip(), float(xy[0]), float(xy[1])


def groups(element, prefix):
    return [g for g in element.iter("g") if g.get("id", "").startswith(prefix)]


def drawing(folder, stem):
    root = ElementTree.parse(folder / (stem+".svg")).getroot()
    for element in root.iter():
        element.tag = element.tag.split("}")[-1]
    page = PdfReader(folder / (stem+".pdf")).pages[0]
    height = float(page.mediabox.height)
    pdf_text = defaultdict(list)

    def remember(text, cm, tm, font, size):
        if text.strip():
            pdf_text[text.strip()].append((cm[4]+tm[4], height-cm[5]-tm[5]))

    page.extract_text(visitor_text=remember)
    for group in groups(root, "text_"):
        text, x, y = glyph_label(group)
        check(any(abs(u-x) < .4 and abs(v-y) < .4 for u,v in pdf_text[text]),
              "SVG/PDF text, order or position differs: " + text)
    return groups(root, "axes_"), pdf_marks(page), set(pdf_text)


def axis_scale(axis, expected_ticks):
    ticks = []
    for tick in groups(axis, "xtick_"):
        label = int(glyph_label(groups(tick, "text_")[0])[0])
        mark = next(u for u in tick.iter("use") if u.get("y") is not None)
        ticks.append((label, float(mark.get("x"))))
    check(tuple(n for n,_ in ticks) == expected_ticks, "tick units or values")
    (lo, xlo), (hi, xhi) = ticks[0], ticks[-1]
    step = (xhi-xlo)/(hi-lo)
    zero = xlo-lo*step
    for n,x in ticks:
        close(x, zero+n*step, "nonlinear axis calibration")
    return zero, step


def expected_edits(saved):
    baseline = saved["baseline"]["score"]
    check(baseline["n"] == 48, "shared parent denominator")
    by_arm = {}
    for arm in ("O", "R"):
        rows = []
        rounds = saved["arms"][arm]["rounds"]
        check([r["round"] for r in rounds] == [1,2,3,4], "four registered rounds")
        for rd in rounds:
            check([s["slot"] for s in rd["slots"]] == [1,2,3,4], "registered slot order")
            for slot in rd["slots"]:
                cell, = slot["cells"]
                level = slot["levels"][CELLS.index(cell)]
                check(level in (1,2,3) and sum(v != 0 for v in slot["levels"]) == 1,
                      "edit label identifies the only changed coordinate")
                label = f"{cell}={level}"
                score = slot["score"]
                check(score["n"] == slot["completed"] == 48 and slot["paid_full"], "paid denominator")
                deltas = tuple((Decimal(score[k])-Decimal(baseline[k]))/48_000_000
                               for k in ("loss_sum_us", "person_sum_us"))
                rows.append((label, deltas, slot["selected"]))
        by_arm[arm] = rows
    rows = by_arm["O"]
    check(rows == by_arm["R"] and len({x[0] for x in rows}) == len(rows) == 16,
          "O/R membership, scores and selected edit")
    return rows


def verify_edits(folder, rows):
    axes, pdf, text = drawing(folder, "T8-edit-tradeoffs")
    labels = [glyph_label(groups(g, "text_")[0]) for g in groups(axes[0], "ytick_")]
    check([v[0] for v in labels] == [v[0] for v in rows], "T8 edit order")
    for j,(axis, ticks, marks) in enumerate(zip(axes, ((-15,-10,-5,0),(0,5,10,15,20)), pdf, strict=True)):
        zero, step = axis_scale(axis, ticks)
        symbols = [next(u for u in g.iter("use") if u.get("y") is not None)
                   for g in groups(axis, "PathCollection_")]
        points = sorted(symbols, key=lambda u:float(u.get("y")))
        ordered = sorted(marks, key=lambda mark:mark[3])
        check(len(points) == len(ordered) == len(rows), "T8 plotted denominator")
        printed = []
        for (name, diffs, won), (_, _, label_y), point, (ink, left, right, y) in zip(
                rows, labels, points, ordered, strict=True):
            x = float(point.get("x"))
            color = "086a98" if won else "b24d13" if diffs[0] < 0 else "536a78"
            check(ink == color and "fill: #"+color in point.get("style", ""), "T8 classification: "+name)
            close(float(point.get("y")), y, name+" SVG/PDF ordinate")
            check(abs(y-label_y) < 5, "T8 label does not belong to this row: "+name)
            close((left+right)/2, x, name+" SVG/PDF abscissa")
            close((x-zero)/step, float(diffs[j]), name+(" loss", " labor")[j])
            if diffs[0] < 0:
                label = f"{float(diffs[j]):+.3f}".rstrip("0").rstrip(".") if j else f"{float(diffs[j]):g}"
                printed.append(label)
        shown = [glyph_label(g)[0] for g in axis.findall("g") if g.get("id","").startswith("text_")]
        check([s for s in shown if re.fullmatch(NUMBER,s)] == printed, "printed T8 callouts")
    check(any("48 条 FIT" in s for s in text), "missing FIT denominator")


def verify_incidents(folder, source_text, caption):
    direction = next(row for row in source_text.splitlines() if 'id="service-counts"' in row)
    events = next(row for row in source_text.splitlines() if 'id="events"' in row)
    counts = re.search(r"伦敦的 (\d+)、(\d+)、(\d+) 与荷兰的 (\d+)、(\d+)、(\d+)", direction)
    outcomes = re.findall(r"（伦敦 (\d+)、荷兰 (\d+)）", events)
    check(counts and len(outcomes) == 2, "frozen paired directions and conversions")
    lwin, ltie, lworse, nwin, ntie, nworse = map(int, counts.groups())
    zeroed, retained = [tuple(map(int,v)) for v in outcomes]
    check(lworse == nworse == 0 and "新增事件为 0" in events, "omitted zero counts")
    all_rows = lwin+ltie+lworse+nwin+ntie+nworse
    affected = sum(zeroed)+sum(retained)
    unaffected = all_rows-affected
    check(lwin+ltie+lworse == nwin+ntie+nworse == 60 and
          f"P 有缺额的 {affected} 行中" in events and f"P 无缺额的 {unaffected} 行" in events,
          "complete family and affected denominators")
    check(all(s in caption for s in (f"每族 {all_rows//2} 个条件", f"有缺额的 {affected} 行中",
                                     f"{sum(zeroed)} 行归零", f"另 {unaffected} 行中", "新增事件为 0")),
          "figure 2 manuscript caption vs published cohorts")
    expected = ([(lwin,ltie),(nwin,ntie)], list(zip(zeroed, retained)))
    axes, pdf, text = drawing(folder, "T7-paired-directions")
    for axis, marks, pairs, ticks in zip(axes, pdf, expected, ((0,15,30,45,60),(0,15,30,45)), strict=True):
        zero, step = axis_scale(axis, ticks)
        ylabels = [glyph_label(groups(g, "text_")[0]) for g in groups(axis, "ytick_")]
        check([x[0] for x in ylabels] == ["伦敦式","荷兰式"], "T7 family order")
        svg_rects = []
        for path in axis.findall("./g/path[@clip-path]"):
            values = list(map(float,re.findall(NUMBER,path.attrib["d"])))
            xs,ys = values[::2],values[1::2]
            color = re.search(r"fill: #([0-9a-f]{6})", path.attrib["style"])[1]
            svg_rects.append((color,min(xs),max(xs),(min(ys)+max(ys))/2))
        rects = sorted(svg_rects, key=lambda v:(v[3],v[1]))
        ordered = sorted(marks, key=lambda v:(v[3],v[1]))
        check(len(rects) == len(ordered) == 4, "T7 bars per panel")
        digits = [glyph_label(g) for g in axis.findall("g") if g.get("id","").startswith("text_")]
        for i,(svg_rect,pdf_rect) in enumerate(zip(rects, ordered, strict=True)):
            family, part = divmod(i,2)
            required = pairs[family][part]
            color, x0, x1, y = svg_rect
            check(color == pdf_rect[0] == ("086a98","cbd3d8")[part], "T7 bar category")
            for u,v in zip(svg_rect[1:],pdf_rect[1:],strict=True):
                close(u,v,"T7 visible PDF/SVG bar")
            close((x0-zero)/step, sum(pairs[family][:part]), "T7 bar origin")
            close((x1-x0)/step, required, "T7 paired count")
            check(abs(y-ylabels[family][2]) < 5 and
                  any(s == str(required) and x0 < x < x1 and abs(y-h)<5 for s,x,h in digits),
                  "T7 numerical label and family")
    check(any("缺额增加的行数均为 0" in s and f"另有 {unaffected} 行" in s and "新增事件为 0" in s for s in text),
          "printed T7 zero and separate denominator")


def verify_figure_values(folder, read_source, paper, html):
    public = "docs/mainline/"
    captions = [c.get_text(" ", strip=True) for c in html.select("figcaption")]
    verify_incidents(folder, read_source(public+"t7-closeout/numeric-sources.md").decode(), captions[1])
    study = json.loads(read_source(public+"t8-rsi-wait-repair/stage1b/results/results.json"))
    rows = expected_edits(study)
    verify_edits(folder, rows)
    (winner, (loss, staff), _), = [r for r in rows if r[2]]
    (other, (other_loss, other_staff), _), = [r for r in rows if not r[2] and r[1][0]<0]
    annotation = captions[2].replace("−","-")
    prose = paper.replace("**","")
    check(winner in annotation and other in annotation and
          f"整板缺额差为 {other_loss} 秒、工时差为 +{other_staff} 人秒" in annotation and
          f"平均少损失 {abs(loss)} 秒服务，多用 {staff:.6f} 人秒" in prose,
          "figure 3 manuscript caption and locked score vs paid aggregates")
    print("PASS figure 2: 8 segments, labels and cohort counts; figure 3: 16 edits x 2 effects, labels and winner (PDF/SVG, captions and manuscript)")
