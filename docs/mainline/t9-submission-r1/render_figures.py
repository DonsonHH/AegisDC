"""Export the two reviewed aggregate figures as SVG for the editable manuscript.

The original vector PDFs are archived alongside their SVG renditions.
"""
from pathlib import Path
import argparse
import re
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

REV = "28c5969191bab0c7e3c4d508135cc057f89b809d"
OUT = Path(__file__).resolve().parent / 'figures'
BLUE, ORANGE, INK, MUTED, GREY, PALE = "#086A98", "#B24D13", "#202C36", "#475966", "#CBD3D8", "#EFF3F4"


def contents(repo, path):
    return subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", REV+":"+path]).decode()


def style():
    available = {f.name for f in font_manager.fontManager.ttflist}
    cjk = next((f for f in ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei") if f in available), None)
    if cjk is None:
        raise SystemExit("Install a Chinese sans-serif font to render the original labels.")
    plt.rcParams.update({"font.family": [cjk, "DejaVu Sans"], "font.size": 9,
                         "axes.unicode_minus": False, "axes.labelcolor": INK,
                         "text.color": INK, "xtick.color": MUTED, "ytick.color": INK,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "savefig.facecolor": "white"})


def save(fig, stem, caption):
    with matplotlib.rc_context({"svg.fonttype": "path", "svg.hashsalt": "aegis-t9-figures-r1"}):
        fig.savefig(OUT / (stem + ".svg"), metadata={"Date": None, "Title": caption, "Creator": "AegisDC"})
    target = OUT / (stem + ".svg")
    raw = target.read_text(encoding="utf8")
    target.write_bytes(("\n".join(line.rstrip() for line in raw.splitlines()) + "\n").encode())
    plt.close(fig)


def incidents(repo):
    text = contents(repo, "docs/mainline/t7-closeout/numeric-sources.md")
    direction = next(l for l in text.splitlines() if 'id="service-counts"' in l)
    events = next(l for l in text.splitlines() if 'id="events"' in l)
    m = re.search(r"伦敦的 (\d+)、(\d+)、(\d+) 与荷兰的 (\d+)、(\d+)、(\d+)", direction)
    if not m:
        raise ValueError("Family direction counts not located")
    vals = list(map(int, m.groups()))
    reduced, equal, worse = [vals[0], vals[3]], [vals[1], vals[4]], [vals[2], vals[5]]
    pairs = [[int(a),int(b)] for a,b in re.findall(r"（伦敦 (\d+)、荷兰 (\d+)）", events)]
    assert len(pairs)==2 and all(sum(r)==60 for r in (vals[:3],vals[3:])) and all(v==0 for v in worse)
    assert [sum(col) for col in zip(*pairs)]==[45,45] and sum(pairs[0])==45
    fig, axes = plt.subplots(1,2,figsize=(8.2,3.42))
    fig.subplots_adjust(left=.075,right=.972,bottom=.33,top=.69,wspace=.27)
    fig.text(.02,.925,"两类合成事故的服务变化",fontsize=15,weight="bold")
    fig.text(.02,.834,"风险策略 V** 与仅保留既有保护的 P 在同一条件内配对",color=MUTED,fontsize=10)
    for ax,title,num,labels,den in [
            (axes[0],"A   全部配对条件",[reduced,equal],["缺额较小","缺额相同"],60),
            (axes[1],"B   仅 P 原有缺额的条件",pairs,["缺额归零","仍有缺额"],45)]:
        ax.set_title(title,loc="left",fontsize=10.5,weight="bold",pad=9)
        left=[0,0]
        for k,(counts,color) in enumerate(zip(num,[BLUE,GREY])):
            ax.barh([1,0],counts,left=left,color=color,height=.48,edgecolor="white",linewidth=.7)
            for j,x in enumerate(counts):
                ax.text(left[j]+x/2,1-j,str(x),ha="center",va="center",weight="bold",
                        color="white" if k==0 else INK,fontsize=11)
            left=[a+b for a,b in zip(left,counts)]
        ax.set_yticks([1,0],["伦敦式","荷兰式"])
        ax.set(ylim=(-.52,1.55),xlim=(0,den),xlabel="合成条件数")
        ax.set_xticks([0,15,30,45,60] if den==60 else [0,15,30,45])
        ax.spines["left"].set_visible(False);ax.spines["bottom"].set_color(GREY)
        ax.tick_params(axis="y",length=0);ax.tick_params(axis="x",length=3)
        ax.legend(handles=[Patch(facecolor=BLUE,label=labels[0]),Patch(facecolor=GREY,label=labels[1])],
                  loc="upper center",bbox_to_anchor=(.5,-.35),ncol=2,frameon=False,handlelength=1.3,fontsize=8.5)
    fig.text(.02,.091,"A  两族缺额增加的行数均为 0。B  另有 30 行 P 原本无缺额，V** 新增事件为 0。",fontsize=8,color=MUTED)
    fig.text(.02,.035,"图示为配对方向和事件转换计数。合成事件率的确认端点 HC 为不可判。",fontsize=8,color=MUTED)
    save(fig,"T7-paired-directions","T7 公开配对方向与事件转换")


def edits(repo):
    text=contents(repo,"docs/mainline/t8-rsi-wait-repair/stage1b/analysis/tables.md")
    rows=[]
    for l in text.splitlines():
        if not re.match(r"^\| (DIRECT|ALARM|ORDER)_(NEAR|FAR)=[123] \|",l):
            continue
        cells=[s.strip() for s in l.strip().strip("|").split("|")]
        loss,labor=map(float,cells[4].split("/"))
        rows.append((cells[0],loss,labor))
    assert len(rows)==len(set(r[0] for r in rows))==16 and sum(r[1]<0 for r in rows)==2
    fig, (ax,ay)=plt.subplots(1,2,figsize=(7.75,6.1),sharey=True)
    fig.subplots_adjust(left=.262,right=.955,top=.835,bottom=.205,wspace=.29)
    fig.text(.03,.945,"16 个已付编辑的服务与工时",fontsize=15,weight="bold")
    fig.text(.03,.898,"每项为 48 条 FIT 条件的均差，方向为候选减共享父。O 与 R 得到同一组编辑。",fontsize=9,color=MUTED)
    for j,(a,(lo,hi),ticks,title) in enumerate([
            (ax,(-17.1,2.4),[-15,-10,-5,0],"平均服务缺额差（秒）"),
            (ay,(-1.2,23.4),[0,5,10,15,20],"平均人员实耗差（人秒）")]):
        a.set_title(title,loc="left",fontsize=10,weight="bold",pad=8)
        a.axvline(0,color="#667C89",linewidth=.8);a.set_axisbelow(True)
        a.grid(axis="x",color="#E2E7E9",linewidth=.65)
        for i, row in enumerate(rows):
            value=row[1+j]; selected=row[0]=="ORDER_FAR=3"; amber=row[0]=="ALARM_FAR=3"
            color=BLUE if selected else ORANGE if amber else "#536A78"
            a.plot([0,value],[i,i],color=color,linewidth=1.55,alpha=.65)
            a.scatter([value],[i],s=41 if selected or amber else 23,marker="D" if selected else "^" if amber else "o",zorder=3,
                      color=color,edgecolors="white",linewidths=.5)
            if selected or amber:
                fmt=f"{value:+.3f}".rstrip("0").rstrip(".") if j else f"{value:g}"
                xoffset=6 if (not j and selected) or (j and not selected) else -6
                a.annotate(fmt,(value,i),xytext=(xoffset,6),textcoords="offset points",
                           ha="left" if xoffset>0 else "right",fontsize=8,color=color,weight="bold")
        for y in (3.5,7.5,11.5):a.axhline(y,color="#C9D2D7",ls="--",lw=.7)
        a.set_xlim(lo,hi);a.set_xticks(ticks)
        a.spines["left"].set_visible(False);a.spines["bottom"].set_color(GREY)
        a.tick_params(axis="y",length=0);a.tick_params(axis="x",length=3)
    ax.set_ylim(15.8,-.8)
    ax.set_yticks(range(16),[x[0] for x in rows],fontsize=8.2)
    ay.tick_params(axis="y",labelleft=False)
    handles=[Line2D([0],[0],color=BLUE,marker="D",linestyle="",label="两臂锁定"),
             Line2D([0],[0],color=ORANGE,marker="^",linestyle="",label="另一个降低缺额的编辑"),
             Line2D([0],[0],color="#536A78",marker="o",linestyle="",label="其余已付编辑")]
    fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.5,.104),ncol=3,frameon=False,fontsize=8.4)
    fig.text(.03,.073,"每四行对应一轮。两臂各支付 16 个候选槽；两臂重合的描述符在图中各列一次。",fontsize=8.3,color=MUTED)
    fig.text(.03,.031,"人员列为整板均差。Q3 的 +5 人秒门槛适用于分族单侧上界。",fontsize=8.3,color=MUTED)
    save(fig,"T8-edit-tradeoffs","T8 单点编辑的缺额与人秒差")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo",type=Path)
    args=parser.parse_args()
    style();incidents(args.repo);edits(args.repo)
