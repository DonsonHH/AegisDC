"""Export the two registered fit curves from saved estimates using Matplotlib."""
import json
from pathlib import Path
import sys

from matplotlib import pyplot as plt


def main(source,out):
    curves=json.loads(Path(source).read_bytes())["curves"]
    fig,axes=plt.subplots(1,2,figsize=(9,3.7),sharey=True)
    for name,title,color,ax in zip(("MAIN","HOT"),("B_cost start","V** warm start"),("#166769","#914422"),axes):
        values=curves[name]["points"]
        ax.plot([c["paid_calls"] for c in values],[c["delta_L"] for c in values],color=color,marker="o",lw=2)
        ax.axhline(0,color="#515c66",lw=0.8,linestyle="--")
        ax.grid(axis="y",alpha=0.22)
        ax.set_title(title)
        ax.set_xlabel("Cumulative paid facility calls")
        ax.spines[["right","top"]].set_visible(False)
    axes[0].set_ylabel("Mean L difference vs B_cost (s)")
    fig.text(0.5,0.01,"FIT panel, 6 families x 6 cases. Each point is the incumbent at a paid search round.",ha="center",fontsize=8)
    fig.tight_layout(rect=(0.01,0.045,0.99,0.99))
    fig.savefig(Path(out)/"learning-curves.png",dpi=190)
    fig.savefig(Path(out)/"learning-curves.pdf",metadata={"CreationDate":None,"ModDate":None})


if __name__=="__main__":
    main(*sys.argv[1:])
