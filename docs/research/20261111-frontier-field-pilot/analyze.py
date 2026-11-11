"""Read one pinned public workbook; export a descriptive day and an annual gap audit."""

import argparse
import calendar
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string


def digest(path):
    with path.open("rb") as handle:
        return {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(handle, "sha256").hexdigest()}


def read_source(path, spec):
    layout = spec["layout"]
    source = layout["columns"]
    time_col = column_index_from_string(source["timestamp"]["col"])
    columns = {key: column_index_from_string(meta["col"]) for key, meta in source.items()}
    width = max(columns.values())
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book[spec["input"]["data_sheet"]]
        header, units = list(sheet.iter_rows(min_row=1, max_row=2, max_col=width, values_only=True))
        for key, meta in source.items():
            idx = columns[key] - 1
            if header[idx] != meta["header"] or ("source_unit" in meta and units[idx] != meta["source_unit"]):
                raise ValueError(f"Column identity changed: {key}, actual {header[idx]!r}/{units[idx]!r}")

        rows = defaultdict(list)
        malformed = 0
        row_order_reversals = 0
        previous = None
        value_issues = defaultdict(Counter)
        for excel_row, row in enumerate(
            sheet.iter_rows(min_row=layout["data_start_row"], max_col=width, values_only=True), layout["data_start_row"]
        ):
            stamp = row[time_col - 1]
            if stamp is None and all(row[col - 1] is None for col in columns.values()):
                continue
            if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
                malformed += 1
                continue
            row_order_reversals += previous is not None and stamp < previous
            previous = stamp
            values = {}
            for key, col in columns.items():
                if key == "timestamp":
                    continue
                val = row[col - 1]
                if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val):
                    values[key] = val
                else:
                    values[key] = None
                    value_issues[key]["blank" if val is None else "invalid_or_uncached"] += 1
            rows[stamp].append((excel_row, values))
        info = {"worksheets": [ws.title for ws in book.worksheets], "chart_sheets": len(book.chartsheets),
                "timestamp_type": "EXCEL_DATETIME_WITHOUT_TIMEZONE", "malformed_timestamp_rows": malformed,
                "source_order_reversals": row_order_reversals,
                "value_issues_by_column": {k: dict(v) for k, v in sorted(value_issues.items())}}
        return rows, info
    finally:
        book.close()


def gaps(grid, absent, step):
    start = None
    for stamp in [*grid, grid[-1] + step]:
        if stamp in absent:
            if start is None:
                start = stamp
        elif start is not None:
            yield {"start_inclusive": start.isoformat(), "end_exclusive": stamp.isoformat(),
                   "slots": (stamp - start) // step, "nominal_hours": (stamp - start).total_seconds() / 3600}
            start = None


def nearby_grid(dates, start, grid_set, step, band_seconds):
    """Count presence near grid points without changing any source timestamp."""
    buckets = defaultdict(list)
    offsets = []
    for stamp in dates:
        point = start + round((stamp - start) / step) * step
        offset = abs((stamp - point).total_seconds())
        offsets.append(offset)
        if point in grid_set and offset <= band_seconds:
            buckets[point].append(stamp)
    return buckets, max(offsets, default=0.0)


def derive(values, layout):
    data = dict(values)
    for loop in layout["loops"]:
        sup, ret = data.get(loop["supply"]), data.get(loop["return"])
        data[loop["delta"]] = None if sup is None or ret is None else ret - sup
    return data


def stats(rows, keys):
    result = {}
    for key in keys:
        vals = [row.get(key) for row in rows]
        valid = [v for v in vals if v is not None]
        changes = [abs(right - left) for left, right in zip(vals, vals[1:]) if left is not None and right is not None]
        result[key] = {"observed": len(valid), "min": min(valid, default=None), "max": max(valid, default=None),
                       "exact_zero": sum(v == 0 for v in valid), "consecutive_pairs": len(changes),
                       "max_abs_change_per_10_min": max(changes, default=None)}
    return result


def heat_check(rows, spec):
    heat = spec["heat_arithmetic"]
    factor = heat["density_kg_m3"] * heat["specific_heat_J_kg_K"] / 60 / 1e6
    results = {}
    for loop in spec["layout"]["loops"]:
        if not loop.get("waste_heat") or not loop.get("flow"):
            continue
        signed, workbook = [], []
        negative = 0
        for row in rows:
            flow, delta, published = (row.get(loop[k]) for k in ("flow", "delta", "waste_heat"))
            if flow is not None and delta is not None and published is not None:
                negative += delta < 0
                signed.append(factor * heat["us_gal_m3"] * flow * delta - published)
                workbook.append(factor * heat["workbook_gal_m3"] * flow * max(0, delta) - published)
        results[loop["label"]] = {"pairs": len(workbook), "negative_delta_samples": negative,
                                  "signed_max_abs_difference_MW": max(map(abs, signed), default=None),
                                  "workbook_formula_max_abs_difference_MW": max(map(abs, workbook), default=None)}
    return results


def write_csv(path, rows, columns):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in columns} for row in rows)


def figures(day_rows, months, layout, out, day):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#a7b3bf", "text.color": "#142535",
                         "axes.labelcolor": "#142535", "xtick.color": "#526477", "ytick.color": "#526477",
                         "svg.hashsalt": "aegisdc-frontier-v1"})
    power = [[dict(item, color=color)] for item, color in zip(layout["power_panels"], ["#17698d", "#804b93"])]
    loop_colors = ["#0072b2", "#d55e00", "#008563"]
    flows = [{"key": loop["flow"], "label": loop["label"], "color": color}
             for loop, color in zip(layout["loops"], loop_colors) if loop.get("flow")]
    if not flows:
        flows = [{"key": layout["overall_flow"], "label": "Overall", "color": "#0072b2"}]
    deltas = [{"key": loop["delta"], "label": loop["label"], "color": color}
              for loop, color in zip(layout["loops"], loop_colors)]
    panels = [*power, flows, deltas]
    titles = [item["title"] for item in layout["power_panels"]] + ["Coolant flow", "Coolant rise: return − supply"]
    units = ["MW"] * len(power) + ["US gal/min", "°C"]
    x = [idx / 6 for idx, _ in enumerate(day_rows)]
    absent = [idx for idx, row in enumerate(day_rows) if row["slot_status"] == "ABSENT_TIMESTAMP"]
    fig, axes = plt.subplots(len(panels), 1, figsize=(10.8, 8.4), sharex=True)
    fig.subplots_adjust(left=0.095, right=0.975, top=0.87, bottom=0.11, hspace=0.58)
    fig.text(0.095, 0.955, f"Frontier | {day.day} {calendar.month_name[day.month]} {day.year}",
             size=20, weight="bold")
    fig.text(0.095, 0.916, "Published 10-minute slots · aligned by the workbook clock", color="#526477", size=11)
    for ax, title, unit, panel in zip(axes, titles, units, panels):
        ax.set_title(title, loc="left", size=10, weight="bold", pad=5)
        ax.set_ylabel(unit)
        ax.grid(axis="y", color="#e1e7ee", linewidth=0.75)
        for idx in absent:
            ax.axvspan(idx / 6, (idx + 1) / 6, color="#f6d8aa", alpha=0.65, linewidth=0)
        for i, item in enumerate(panel):
            y = [row.get(item["key"]) for row in day_rows]
            ax.plot(x, y, color=item["color"], marker=("o", "s", "^")[i], markersize=2.5,
                    linewidth=1.15, linestyle=("-", "--", "-.")[i], label=item["label"])
        if len(panel) > 1:
            ax.legend(ncol=len(panel), loc="upper right", frameon=True, facecolor="white", edgecolor="#e1e7ee")
    axes[-1].set(xlim=(0, 24), xticks=list(range(0, 25, 3)),
                 xticklabels=[f"{hr:02}:00" for hr in range(0, 25, 3)],
                 xlabel="Workbook time (timezone not specified)")
    note = (f"{len(absent)} missing timestamp slots (amber)." if absent else "No missing timestamp slots on this day.")
    fig.text(0.095, 0.035, f"{note}  |  Source: Grant et al., Figshare v4 · CC BY 4.0", size=8.5, color="#526477")
    fig.savefig(out / "frontier-jan08.png", dpi=185)
    fig.savefig(out / "frontier-jan08.svg", metadata={"Date": None})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.8, 4.1))
    fig.subplots_adjust(left=0.085, right=0.98, top=0.74, bottom=0.18)
    fig.text(0.085, 0.908, "Frontier | 2023 observation gaps", size=19, weight="bold")
    fig.text(0.085, 0.827, "Exact grid misses split by whether a source row falls within 1 second", size=11, color="#526477")
    labels = [calendar.month_abbr[m["month"]] for m in months]
    missing = [m["no_nearby_slots"] / 6 for m in months]
    partial = [m["nearby_not_exact_slots"] / 6 for m in months]
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#e1e7ee", linewidth=0.8)
    ax.bar(labels, missing, width=0.61, color="#26688a", label="No timestamp within ±1 s")
    ax.bar(labels, partial, bottom=missing, width=0.61, color="#e9ad55",
           label="Nearby timestamp, exact grid miss")
    ax.set_ylabel("Nominal 10-minute hours")
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.085, 0.05, "Diagnostic only; source times were not changed.  |  Grant et al., Figshare v4 · CC BY 4.0",
             size=8.5, color="#526477")
    fig.savefig(out / "frontier-2023-gaps.png", dpi=185)
    plt.close(fig)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("workbook", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    protocol = Path(__file__).with_name("protocol.json")
    spec = json.loads(protocol.read_text(encoding="utf-8"))
    identity = digest(args.workbook)
    with args.workbook.open("rb") as handle:
        identity["md5"] = hashlib.file_digest(handle, "md5").hexdigest()
    if any(identity[key] != spec["input"][key] for key in ("bytes", "md5")):
        raise ValueError("Original workbook does not match pinned v4 metadata")
    rows, clock = read_source(args.workbook, spec)
    window, layout = spec["window"], spec["layout"]
    start, end, day = [datetime.fromisoformat(window[key]) for key in ("annual_start", "annual_end_exclusive", "source_date")]
    step = timedelta(seconds=window["nominal_grid_seconds"])
    grid = [start + i * step for i in range((end - start) // step)]
    span = set(grid)
    dates = sorted(stamp for stamp in rows if start <= stamp < end)
    base_fields = set(layout["required_plot_sources"])
    absent = span - rows.keys()
    band = window["proximity_diagnostic_seconds"]
    near, max_offset = nearby_grid(dates, start, span, step, band)
    no_nearby = span - near.keys()
    near_only = absent - no_nearby
    dupe = {t for t in span if len(rows.get(t, ())) > 1}
    incomplete = {t for t in span if len(rows.get(t, ())) == 1
                  and any(rows[t][0][1][key] is None for key in base_fields)}
    selected = [stamp for stamp in grid if day <= stamp < day + timedelta(days=1)]
    if any(stamp not in span and day <= stamp < day + timedelta(days=1) for stamp in dates):
        raise ValueError("Day includes off-grid rows; fixed-grid plot would hide actual timestamps")
    day_rows = []
    for stamp in selected:
        points = rows.get(stamp, [])
        if len(points) == 1:
            excel_row, data = points[0]
            status = "INCOMPLETE_INPUT" if stamp in incomplete else "OBSERVED"
        else:
            excel_row, data = None, {}
            status = "DUPLICATE_TIMESTAMP" if points else "ABSENT_TIMESTAMP"
        day_rows.append({"timestamp": stamp.isoformat(), "excel_row": excel_row,
                         "slot_status": status, **derive(data, layout)})
    months = [{"month": m, "expected_slots": sum(t.month == m for t in grid),
               "absent_slots": sum(t.month == m for t in absent),
               "incomplete_slots": sum(t.month == m for t in incomplete),
               "duplicate_slots": sum(t.month == m for t in dupe),
               "no_nearby_slots": sum(t.month == m for t in no_nearby),
               "nearby_not_exact_slots": sum(t.month == m for t in near_only)} for m in range(1, 13)]
    episodes = list(gaps(grid, absent, step))
    nearby_episodes = list(gaps(grid, no_nearby, step))
    clock.update({"first_2023": dates[0].isoformat(), "last_2023": dates[-1].isoformat(),
                  "timestamped_rows_2023": sum(len(rows[t]) for t in dates), "unique_timestamps_2023": len(dates),
                  "timestamped_rows_outside_2023": sum(len(group) for stamp, group in rows.items() if not start <= stamp < end),
                  "distinct_adjacent_seconds": dict(sorted(Counter((b - a).total_seconds() for a, b in zip(dates, dates[1:])).items())),
                  "off_grid_timestamps_2023": sum(t not in span for t in dates),
                  "max_absolute_offset_from_nearest_nominal_grid_s": max_offset})
    coverage = {"expected_slots": len(grid), "absent_slots": len(absent), "absent_nominal_hours": len(absent) / 6,
                "incomplete_slots": len(incomplete), "duplicate_slots": len(dupe), "gap_count": len(episodes),
                "max_gap": max(episodes, key=lambda e: e["slots"], default=None),
                "proximity_diagnostic": {"seconds": band, "matched_grid_slots": len(near),
                    "nearby_not_exact_slots": len(near_only), "no_nearby_slots": len(no_nearby),
                    "no_nearby_nominal_hours": len(no_nearby) / 6,
                    "multi_timestamp_buckets": sum(len(group) > 1 for group in near.values()),
                    "unassigned_source_timestamps": len(dates) - sum(map(len, near.values())),
                    "gap_count": len(nearby_episodes),
                    "max_gap": max(nearby_episodes, key=lambda e: e["slots"], default=None)},
                "by_month": months}
    fields = [key for key in layout["columns"] if key != "timestamp"] + [loop["delta"] for loop in layout["loops"]]
    args.output.mkdir()
    write_csv(args.output / "frontier-jan08.csv", day_rows, ["timestamp", "excel_row", "slot_status", *fields])
    gap_rows = ([dict(basis="EXACT_TIMESTAMP", **e) for e in episodes]
                + [dict(basis="NO_TIMESTAMP_WITHIN_1S", **e) for e in nearby_episodes])
    write_csv(args.output / "frontier-2023-absent-slots.csv", gap_rows,
              ["basis", "start_inclusive", "end_exclusive", "slots", "nominal_hours"])
    figures(day_rows, months, layout, args.output, day)
    result = {"status": "DESCRIPTIVE_EXTERNAL_FACILITY_DATA_ONLY", "input": {**spec["input"], **identity},
              "protocol": digest(protocol), "script": digest(Path(__file__)),
              "environment": {"python": sys.version.split()[0], **{lib: version(lib) for lib in ("openpyxl", "et-xmlfile", "matplotlib", "numpy", "pillow")}},
              "clock": clock, "annual": coverage, "day": {"date": window["source_date"],
                "expected_slots": len(selected), "slot_status_counts": dict(Counter(row["slot_status"] for row in day_rows)),
                "series": stats(day_rows, fields), "heat_arithmetic_only": heat_check(day_rows, spec)},
              "artifacts": {p.name: digest(p) for p in sorted(args.output.iterdir())},
              "field_calibration": "PENDING", "facility_runs": 0, "registered_research_runs": 0}
    (args.output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"input": identity, "annual": {k: v for k, v in coverage.items() if k != "by_month"},
                      "day_slots": result["day"]["slot_status_counts"]}, allow_nan=False))


if __name__ == "__main__":
    main()
