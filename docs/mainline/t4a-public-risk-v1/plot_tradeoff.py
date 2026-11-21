"""Render the three observed public-development prices and the two new controls."""
import gzip
import json
from pathlib import Path
import sys

from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator


def main(root, output):
    with gzip.open(root/'development-result.json.gz','rt') as stream:
        data=json.load(stream)
    roles=data['scopes']['overall']['by_role']
    fig,ax=plt.subplots(figsize=(8.2,5.2))
    fig.subplots_adjust(left=.13,bottom=.2,top=.90,right=.95)
    ax.set_axisbelow(True)
    ax.grid(axis='both',color='#e2e5e6',lw=.7)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for edge in ('left','bottom'):
        ax.spines[edge].set_color('#858f94')
    versions=('V1','V3','V2')
    points=[(roles[k]['person'],roles[k]['L']) for k in versions]
    ax.plot(*zip(*points),color='#15705d',lw=1.6,zorder=2)
    ticks=(('V1',r'V1  $\lambda=0$'),('V3',r'V*  $\lambda=1$'),('V2',r'V2  $\lambda=4$'),
           ('PA','PA'),('B','B'))
    offsets={'V1':(2,-17),'V2':(7,8),'V3':(-24,13),'B':(7,7),'PA':(7,7)}
    for key,label in ticks:
        q=roles[key]
        control=key in ('B','PA')
        ax.scatter(q['person'],q['L'],s=65 if key=='V3' else 46,
                   marker='s' if control else 'o',c='#91572e' if control else '#15705d',edgecolors='white',lw=.8,zorder=4)
        ax.annotate(label,(q['person'],q['L']),xytext=offsets[key],textcoords='offset points',
                    fontsize=10,weight='bold' if key=='V3' else 'normal',color='#233438')
    ax.margins(x=.15,y=.18)
    ax.set_xlim(left=0)
    ax.xaxis.set_major_locator(MaxNLocator(7))
    ax.yaxis.set_major_locator(MaxNLocator(7))
    ax.set_xlabel('Mean personnel time per condition (s)',labelpad=10)
    ax.set_ylabel('Mean normalized service deficit L (s)',labelpad=10)
    ax.set_title('Service and personnel across three predeclared prices',loc='left',size=14,pad=12)
    fig.text(.13,.045,'72 disclosed development conditions per point. Connected points share one decision rule.',fontsize=9,color='#455458')
    fig.savefig(output/'service-personnel.png',dpi=180,facecolor='white')
    fig.savefig(output/'service-personnel.pdf',facecolor='white',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    main(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)>2 else Path(sys.argv[1]))
