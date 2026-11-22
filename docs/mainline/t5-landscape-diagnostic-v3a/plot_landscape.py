"""Render the saved opposite-half selection curves and the central subset intervals."""
from pathlib import Path
import json
import sys
import numpy as np
from matplotlib import pyplot as plt


def main(source,destination):
    s=json.loads(Path(source).read_bytes())
    q=s["landscape"]["curves"]
    keys=sorted(map(int,q))
    x=np.arange(len(keys))
    fig,axes=plt.subplots(1,2,figsize=(10,4.2))
    styles=(("A_to_B","Select A, score B","#177367","o"),("B_to_A","Select B, score A","#A65331","s"),
            ("pooled","Pooled","#383D74","D"))
    for direction,title,color,marker in styles:
        for ax,metric,scale in ((axes[0],"target_L",1),(axes[1],"recovered",100)):
            values=[q[str(k)][direction][metric] for k in keys]
            if any(v is None for v in values):continue
            center=[v["mean"]*scale for v in values]
            ax.plot(x,center,label=title,color=color,marker=marker,markersize=4,lw=1.8)
            ax.fill_between(x,[v["lo"]*scale for v in values],[v["hi"]*scale for v in values],color=color,alpha=.10)
    for ax in axes:
        ax.set_xticks(x,keys)
        ax.grid(axis="y",alpha=.22)
        ax.spines[["top","right"]].set_visible(False)
        ax.set_xlabel("Random policies available for selection (k)")
    axes[0].set_ylabel("Mean service deficit on the other half (s)")
    axes[1].set_ylabel("B_cost-to-oracle gap recovered (%)")
    axes[1].axhline(80,color="#555555",ls="--",lw=.8)
    axes[0].legend(frameon=False,fontsize=8)
    fig.text(.5,.016,"Means and central 90% intervals across 2,000 policy subsets. Each half contains 18 conditions.",
             ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.06,1,1))
    fig.savefig(Path(destination)/"landscape.png",dpi=190)
    fig.savefig(Path(destination)/"landscape.pdf",metadata={"CreationDate":None,"ModDate":None})
    plt.close(fig)

if __name__=="__main__":main(*sys.argv[1:])
