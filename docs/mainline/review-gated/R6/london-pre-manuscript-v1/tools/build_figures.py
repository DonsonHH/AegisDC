#!/usr/bin/env python3
"""Render publication figures from saved, extracted records only.

No AegisDC module is imported. No facility, policy, scorer, test, qualification,
or research execution is performed. Figure 4's energy line is an explicitly
labeled piecewise reconstruction from recorded UPS intervals and frozen power.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"lower": "#23816C", "equal": "#B8C4CE", "higher": "#D57C39", "ink": "#223346", "grid": "#E0E6EB", "A": "#4D84B4", "UPS": "#E5B557", "G": "#26846D", None: "#C95C57", "RUNNING": "#468D7D", "OFF": "#C95C57", "BOOTING": "#DCA244"}


def num(value):
    return float(Fraction(str(value)))


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 14, "axes.titleweight": "bold",
        "axes.labelsize": 11, "axes.edgecolor": "#93A1AE",
        "text.color": COLORS["ink"], "axes.labelcolor": COLORS["ink"],
        "xtick.color": COLORS["ink"], "ytick.color": COLORS["ink"],
        "svg.fonttype": "none", "svg.hashsalt": "aegisdc-london-pre-manuscript-v1",
        "savefig.facecolor": "white", "figure.facecolor": "white",
        "axes.spines.top": False, "axes.spines.right": False,
    })


def save(fig, output: Path, name: str):
    fig.savefig(output / (name + ".svg"), bbox_inches="tight", metadata={"Date": None, "Creator": "matplotlib; saved-record publication rendering"})
    fig.savefig(output / (name + ".png"), bbox_inches="tight", dpi=240, metadata={"Software": "matplotlib; saved-record publication rendering"})
    plt.close(fig)


def counts(rows, comparator):
    result = {"lower": 0, "equal": 0, "higher": 0}
    for row in rows:
        if not row["eligible"]:
            continue
        i = Fraction(str(row["arms"]["I"]["L"]))
        c = Fraction(str(row["arms"][comparator]["L"]))
        result["lower" if i < c else "higher" if i > c else "equal"] += 1
    return result


def comparison_figure(data, output):
    fig, axs = plt.subplots(1, 2, figsize=(12.8, 5.2), sharex=True)
    for ax, panel, title in zip(axs, ("dev19", "ext35"), ("A  Public development", "B  Finite extension")):
        p = data["panels"][panel]
        ax.set_title(title, loc="left", pad=30)
        ax.text(0, 1.08, f"{p['eligible_count']} eligible of {p['condition_count']} conditions", transform=ax.transAxes, fontsize=11)
        for y, comparator in ((1, "D"), (0, "P")):
            c = counts(p["rows"], comparator)
            left = 0
            for category in ("lower", "equal", "higher"):
                value = c[category]
                if value:
                    ax.barh(y, value, left=left, height=0.34, color=COLORS[category], edgecolor="white", linewidth=1)
                    ax.text(left + value/2, y, str(value), ha="center", va="center", color="white" if category == "lower" else COLORS["ink"], weight="bold")
                left += value
            ax.text(0, y - 0.33, f"{c['lower']} lower / {c['equal']} equal / {c['higher']} higher", fontsize=10)
        nc = [r for r in p["rows"] if not r["eligible"]]
        line = "; ".join(f"{r['source_id']}: L(I/D/P) = " + "/".join(str(r['arms'][a]['L']) for a in ("I", "D", "P")) for r in nc)
        ax.text(0, -0.98, "Noncompliant row retained separately\n" + line, fontsize=10, linespacing=1.7, bbox={"boxstyle": "round,pad=0.6", "facecolor": "#F6F2EE", "edgecolor": "#D8CDC0"})
        ax.set_yticks([1, 0], ["I vs D", "I vs P"])
        ax.set_ylim(-1.4, 1.4)
        ax.set_xlim(0, 35)
        ax.set_xticks([0, 5, 10, 15, 20, 25, 30, 35])
        ax.set_xlabel("Number of eligible conditions (not probabilities)")
        ax.spines["left"].set_visible(False)
        ax.grid(axis="x", color=COLORS["grid"], linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)
    fig.legend(handles=[Patch(color=COLORS[c], label=l) for c, l in (("lower", "I has less service deficit"), ("equal", "Equal deficit"), ("higher", "I has more service deficit"))], loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.subplots_adjust(bottom=0.18, top=0.78, wspace=0.28)
    save(fig, output, "fig01-panel-comparisons")


def time_axes(ax, ymax=2.9):
    ax.set_xlim(0, 20)
    ax.set_ylim(-0.6, ymax)
    ax.set_xticks([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
    ax.set_xlabel("Synthetic time (s); scoring window [0, 20)")
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)


def b01_figure(data, output):
    case = data["cases"]["ext35.B01"]
    fig, ax = plt.subplots(figsize=(12.5, 5.0))
    ax.set_title("B01: inspection avoids a harmful isolation job", loc="left", pad=25)
    for arm, y in (("I", 2), ("D", 1), ("P", 0)):
        v = case["arms"][arm]
        for segment in v["service_states"]:
            left, right = num(segment["start"]), num(segment["end"])
            state = segment["state"][4]
            ax.broken_barh([(left, right-left)], (y-0.17, 0.34), facecolors=COLORS[state], edgecolors="white", linewidth=0.9)
            if state != "RUNNING":
                ax.text((left+right)/2, y, "OFF" if state == "OFF" else "BOOT", ha="center", va="center", fontsize=10, color="white" if state=="OFF" else COLORS["ink"], weight="bold")
        ax.text(20.15, y, f"L = {v['L']} s", va="center", fontsize=11)
    record = case["arms"]["I"]["observations"][0]
    obs_time = num(record["available_at"])
    ax.scatter([obs_time], [2], marker="D", s=65, facecolors="white", edgecolors=COLORS["ink"], zorder=5)
    ax.annotate("POS = 1 arrives; I stops", (obs_time, 2.17), xytext=(obs_time+0.3, 2.6), arrowprops={"arrowstyle": "-", "color": COLORS["ink"]}, fontsize=11)
    receipt = case["arms"]["D"]["execution_receipts"][0]
    verify = case["arms"]["D"]["verify_records"][0]
    commit, available, verified = map(num, (receipt["committed_at"], receipt["available_at"], verify["available_at"]))
    ax.scatter([commit], [1.18], marker="v", color=COLORS["ink"], s=45, zorder=5)
    ax.annotate(f"commit {commit:g}; receipt {available:g}", (commit, 0.83), xytext=(3.3, 0.44), arrowprops={"arrowstyle": "-", "color": COLORS["ink"]}, fontsize=10)
    ax.scatter([verified], [1.18], marker="D", color=COLORS["ink"], s=45, zorder=5)
    ax.annotate("service resumes; VERIFY arrives", (verified, 1.17), xytext=(9.5, 1.63), arrowprops={"arrowstyle": "-", "color": COLORS["ink"]}, fontsize=10)
    ax.set_yticks([2, 1, 0], ["I  |  1 person-s", "D  |  6 person-s", "P  |  0 person-s"])
    time_axes(ax)
    fig.legend(handles=[Patch(color=COLORS[s], label=l) for s, l in (("RUNNING", "Service delivered"), ("OFF", "Isolated; device OFF"), ("BOOTING", "Power restored; device booting"))], loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.015))
    fig.subplots_adjust(left=0.13, right=0.91, bottom=0.18, top=0.83)
    save(fig, output, "fig02-b01-service-timeline")


def g_boundary_figure(data, output):
    fig, axs = plt.subplots(2, 1, figsize=(12.4, 7.5), sharex=True)
    for ax, case_id in zip(axs, ("G05", "G06")):
        case = data["cases"]["ext35."+case_id]
        cutoff = num(case["condition"]["tF"])
        title = "A  G05: cutoff at 12 blocks I's commit" if case_id=="G05" else "B  G06: I commits at 12 before cutoff at 13"
        ax.set_title(title, loc="left", pad=20)
        ax.axvspan(cutoff, 20, color="#F0F2F5", zorder=0)
        for arm, y in (("I", 2), ("D", 1), ("P", 0)):
            v = case["arms"][arm]
            for segment in v["service_states"]:
                left, right = num(segment["start"]), num(segment["end"])
                source, _, _, service, device, _ = segment["state"]
                hatch = "///" if num(service)==0 and device=="BOOTING" else None
                ax.broken_barh([(left, right-left)], (y-0.15, 0.3), facecolors=COLORS[source], edgecolors="white" if hatch is None else COLORS["ink"], linewidth=0.75, hatch=hatch)
            for receipt in v["execution_receipts"]:
                if receipt["committed_at"] is not None:
                    ax.scatter([num(receipt["committed_at"])], [y+0.22], marker="D", s=35, color=COLORS["ink"], zorder=5)
            for verify in v["verify_records"]:
                ax.scatter([num(verify["available_at"])], [y+0.22], marker="o", s=35, facecolor="white", edgecolor=COLORS["ink"], zorder=5)
            ax.text(20.15, y, f"L = {v['L']} s", va="center", fontsize=10)
        if case_id == "G05":
            ax.scatter([cutoff], [2.22], marker="x", s=60, color="#A14742", linewidth=2, zorder=6)
            ax.text(12.3, 2.5, "No commit; no VERIFY", fontsize=10)
        else:
            ax.text(cutoff+0.3, 2.5, "Executed; no VERIFY", fontsize=10)
        ax.axvline(cutoff, color="#A14742", linestyle="--", linewidth=1.2)
        ax.set_yticks([2, 1, 0], ["I", "D", "P"])
        time_axes(ax, ymax=2.85)
    axs[0].set_xlabel("")
    handles = [Patch(color=COLORS[s], label=l) for s,l in (("A","A supply"),("UPS","UPS supply"),("G","G supply"),(None,"No supply; no service"))]
    handles += [Patch(facecolor=COLORS["A"], edgecolor=COLORS["ink"], hatch="///", label="Booting; no service"), Line2D([0],[0],marker="D",color="none",markerfacecolor=COLORS["ink"],markeredgecolor=COLORS["ink"],label="Actual commit"), Line2D([0],[0],marker="o",color="none",markerfacecolor="white",markeredgecolor=COLORS["ink"],label="VERIFY arrival")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5,-0.015), fontsize=10)
    fig.subplots_adjust(left=0.06, right=0.92, bottom=0.16, top=0.92, hspace=0.57)
    save(fig, output, "fig03-g05-g06-boundary")


def ups_figure(data, output):
    cases = [data["cases"][f"ext35.{x}"] for x in ("F01", "F02")]
    reference = cases[0]["arms"]["I"]
    cfg = cases[0]["condition"]
    h, e0, power = map(num, (cfg["H"], cfg["E0"], cfg["P"]))
    # Publication identity comparison, not a rerun of a plant or a scorer.
    for case in cases:
        for arm in ("I", "D", "P"):
            v = case["arms"][arm]
            if v["supply"] != reference["supply"] or v["service_states"] != reference["service_states"]:
                raise ValueError("F01/F02 saved traces no longer coincide; do not render shared trajectory")
    time, energy = [0], [e0]
    for segment in reference["supply"]:
        left, right = num(segment["start"]), num(segment["end"])
        if time[-1] != left:
            time.append(left); energy.append(energy[-1])
        energy.append(energy[-1] - (right-left)*power if segment["state"]=="UPS" else energy[-1])
        time.append(right)
    fig, axs = plt.subplots(3, 1, figsize=(11.8, 7.4), sharex=True, gridspec_kw={"height_ratios": [2.5, 1.4, 1.6]})
    axs[0].set_title("F01/F02: zero window loss does not mean G takeover", loc="left", pad=28)
    axs[0].text(0,1.08,"All six saved I/D/P trajectories share the supply and service curves below",transform=axs[0].transAxes,fontsize=10)
    axs[0].plot(time, energy, color=COLORS["UPS"], linewidth=3)
    axs[0].fill_between(time, energy, color=COLORS["UPS"], alpha=0.16)
    axs[0].scatter([h], [energy[-1]], s=48, color=COLORS["ink"], zorder=5)
    axs[0].text(9.5, 1.6, "3 kJ used on [17, 20)\nEnergy line reconstructed from saved intervals", fontsize=10, linespacing=1.5)
    axs[0].set_ylabel("Remaining UPS (kJ)")
    axs[0].set_yticks([0,1,2,3])
    axs[0].set_ylim(-0.25, 3.35)
    for segment in reference["supply"]:
        left, right = num(segment["start"]), num(segment["end"])
        axs[1].broken_barh([(left,right-left)], (0.28,0.44),facecolors=COLORS[segment["state"]],edgecolors="white")
        axs[1].text((left+right)/2,0.5,segment["state"],ha="center",va="center",color="white" if segment["state"]=="A" else COLORS["ink"],weight="bold")
    axs[1].set_yticks([0.5],["Supply"])
    axs[1].set_ylim(0,1)
    axs[1].spines["left"].set_visible(False)
    axs[2].plot([0,h],[1,1],color=COLORS["RUNNING"],linewidth=3)
    axs[2].scatter([h],[1],s=55,facecolor="white",edgecolor=COLORS["RUNNING"],linewidth=1.8,zorder=6)
    axs[2].scatter([h],[0],s=55,color=COLORS["OFF"],zorder=6)
    axs[2].text(0.3,0.46,"L = U = 0 on [0, 20); device OFF at t = 20\nRecovery right-censored; recorded lower bound = 0 s",fontsize=10,linespacing=1.6)
    axs[2].set_ylabel("Service / demand")
    axs[2].set_yticks([0,1])
    axs[2].set_ylim(-0.15,1.2)
    axs[2].set_xlabel("Synthetic time (s); H = 20 is the scoring endpoint")
    for ax in axs:
        ax.set_xlim(0,20.35)
        ax.set_xticks([0,5,10,15,17,20])
        ax.axvline(17,color=COLORS["grid"],linewidth=1,zorder=0)
        ax.axvline(20,color=COLORS["ink"],linestyle="--",linewidth=1)
        ax.grid(axis="x",color=COLORS["grid"],linewidth=0.6)
        ax.set_axisbelow(True)
    fig.text(0.08,0.015,"G terminal state: I and D = FAILED; P = IDLE.  F01 lacks readiness; F02 lacks physical permit.",fontsize=10)
    fig.subplots_adjust(left=0.09,right=0.97,bottom=0.13,top=0.86,hspace=0.3)
    save(fig, output, "fig04-ups-horizon")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT/"data"/"figure-data.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"figures")
    args = parser.parse_args()
    raw = args.data.read_bytes()
    data = json.loads(raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    style()
    comparison_figure(data,args.output_dir)
    b01_figure(data,args.output_dir)
    g_boundary_figure(data,args.output_dir)
    ups_figure(data,args.output_dir)
    summary = {
        "classification": "PUBLICATION_RENDER_NO_NEW_MODEL_OR_RESEARCH_EXECUTION",
        "python": platform.python_version(), "matplotlib": matplotlib.__version__,
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "source_revision": data["source_revision"],
        "counts": {panel:{f"I_vs_{arm}":counts(p["rows"],arm) for arm in ("D","P")} for panel,p in data["panels"].items()},
        "noncompliant_retained": {panel:p["noncompliant_ids"] for panel,p in data["panels"].items()},
        "outputs": {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output_dir.iterdir()) if p.suffix in (".svg",".png")},
        "facility_calls":0,"policy_calls":0,"scorer_calls":0,"qualification_calls":0,"research_calls":0,
    }
    (args.output_dir/"render-receipt.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == "__main__":
    main()
