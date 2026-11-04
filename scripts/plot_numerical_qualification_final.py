"""Linear, explicitly status-labelled eleven-case scientific summary."""
import argparse,json
from pathlib import Path
import sys
from hashlib import sha256


def render(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    result=json.loads((folder/'summary.json').read_text(encoding='utf-8'));names=list(result['cases'])
    cases=[result['cases'][name] for name in names];y=np.arange(len(names));figure,axes=plt.subplots(1,3,figsize=(15,6.5),sharey=True,layout='constrained')
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
    for axis,kind,label,full_limit in [(axes[0],'_K','Phase-consistent temperature / 0.05 K',result['limits']['temperature_K']),
            (axes[1],'_Pa','Phase-consistent pressure / 1000 Pa',result['limits']['pressure_Pa']),
            (axes[2],'_W','Phase-consistent heat flow / 25 kW',result['limits']['heat_W'])]:
        candidate=[max(value for key,value in row['candidate_comparison']['maximum_absolute_series_error'].items() if key.endswith(kind))/full_limit for row in cases]
        reference=[max(value for key,value in row['reference_self_check']['maximum_absolute_series_error'].items() if key.endswith(kind))/full_limit for row in cases]
        axis.barh(y-.16,candidate,height=.3,color='#246b96',label='Candidate / full bound')
        axis.barh(y+.16,reference,height=.3,color='#49a078',label='Reference self-check / full bound')
        axis.axvline(1,color='black',linestyle='--',linewidth=1,label='Candidate bound = 1')
        axis.axvline(.25,color='grey',linestyle=':',linewidth=1,label='Reference bound = 0.25')
        axis.set_xlim(0,max(1.1,max(candidate+reference)*1.1));axis.set_xlabel(label);axis.grid(axis='x',alpha=.2)
    axes[0].set_yticks(y,names);axes[0].invert_yaxis();axes[2].legend(fontsize=8,loc='lower right')
    status='PASS' if result['all_eleven_declared_fixtures_qualified'] else 'NO-GO'
    ladders=sorted({(row['candidate_maximum_step_s'],*row['reference_refinement_steps_s']) for row in cases})
    ladder_text='; '.join(f"h={h:g}, ref={a:g}/{b:g}" for h,a,b in ladders)
    figure.suptitle(f'Finite full-V6 qualification: {status} ({len(names)} declared fixtures)\nEvent-side anchor / phase-consistent diagnostic; {ladder_text}',fontsize=11)
    figure.supxlabel('Linear axes: exact zeros stay at 0. These are phase-consistent limits, not raw error envelopes. Causal raw, resource and actual event-time errors remain in summary.json.',fontsize=8)
    for suffix in ('.png','.svg'):figure.savefig(folder/('qualification-summary'+suffix),dpi=160,bbox_inches='tight',pad_inches=.15)
    plt.close(figure)
    receipt=dict(matplotlib=matplotlib.__version__,numpy=np.__version__,author_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=sha256((folder/'summary.json').read_bytes()).hexdigest(),outputs={name:sha256((folder/name).read_bytes()).hexdigest() for name in ('qualification-summary.png','qualification-summary.svg')},zero_display='Exact zero; linear axes, no positive display floor')
    (folder/'figure-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--plot-dependencies',type=Path);args=parser.parse_args();import numpy
    if args.plot_dependencies:sys.path.insert(0,str(args.plot_dependencies.resolve()))
    render(args.directory)
