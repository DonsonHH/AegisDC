"""Render actual saved negative-control trajectories and separate labor costs."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

LABELS = {'normal':'Normal', 'false_report':'False report', 'local_protection':'Local protection', 'too_late':'Too late'}
COLORS = {'normal':'#087a76','false_report':'#2c5fbb','local_protection':'#71528e','too_late':'#b95021'}
METRICS = [('worker_travel_person_s','Travel'),('access_check_person_s','Access checks'),('worker_work_person_s','Professional work')]


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    saved = read(args.capture/'receipt.json')
    assert saved['status']=='PASS'
    args.output.mkdir(parents=True)
    records={}
    sources={'receipt.json':digest(args.capture/'receipt.json')}
    for name in LABELS:
        folder=args.capture/name/'trajectory'
        run=read(folder/'run.json')
        trace=[json.loads(line) for line in (folder/'private-state.jsonl').read_bytes().splitlines()]
        records[name]=(run,trace)
        for leaf in ('run.json','private-state.jsonl'):
            sources[f'{name}/trajectory/{leaf}']=digest(folder/leaf)
    mpl.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.labelcolor':'#4a6574','text.color':'#162b3c','svg.hashsalt':'ticket28-saved-negative-controls'})
    fig,axes=plt.subplots(4,1,figsize=(11.8,10),sharex=False)
    fig.subplots_adjust(left=.09,right=.95,top=.865,bottom=.075,hspace=.55)
    fig.text(.09,.96,'Four negative controls, one facility',fontsize=22,weight='bold',va='top')
    fig.text(.09,.915,'Saved synthetic engineering trajectories | Service demand stays external | No policy superiority claim',
             fontsize=10,color='#4a6574',va='top')
    for ax,(name,(run,trace)) in zip(axes,records.items()):
        times=[r['time_s'] for r in trace]
        demand=[r['domains']['it_service']['demand'] for r in trace]
        delivery=[r['domains']['it_service']['delivered'] for r in trace]
        ax.step(times,demand,where='post',color='#748796',ls='--',lw=1.1,zorder=4,label='Offered demand')
        ax.step(times,delivery,where='post',color=COLORS[name],lw=2.7,zorder=3,label='Actual delivery')
        ax.fill_between(times,delivery,demand,step='post',color=COLORS[name],alpha=.12)
        ax.set_ylim(0,1.12)
        ax.set_xlim(0,run['summary']['duration_s'])
        ax.set_ylabel('Service rate [1]')
        ax.set_xlabel('Physical time [s]')
        ax.grid(axis='y',color='#e3e9ee',lw=.7)
        s=run['summary']
        ax.set_title(f"{LABELS[name]}   |   Deficit {s['service_deficit_time_s']:.3g} s"
                     f"   |   Work {s['worker_work_person_s']:.3g} person*s",loc='left',fontsize=12,pad=8)
        for task in run['work_records']:
            start=task.get('work_started_at_s')
            finish=task.get('completed_at_s',task.get('finished_at_s'))
            if start is not None and finish is not None:
                ax.axvspan(start,finish,color=COLORS[name],alpha=.1)
                ax.plot([start,finish],[1.05,1.05],color=COLORS[name],lw=4,solid_capstyle='butt')
        if name=='false_report':
            records_at_end=run['policy_public_decisions'][-1]['frame']['evidence']['records']
            for identifier,label,x_offset,alignment in (
                    ('delayed-lake-work-order','Work order arrives',-.06,'right'),
                    ('actual-lake-flow-before-action','Handheld reading arrives',.06,'left')):
                record=next(r for r in records_at_end if r['id']==identifier)
                t=record['arrived_at_s']
                ax.axvline(t,color='#748796',ls=':',lw=.9)
                ax.text(t+x_offset,.73,label,ha=alignment,fontsize=8)
            for decision in run['policy_public_decisions']:
                q=decision['choice']['question_lifecycle']['questions'][0]
                if q['status']=='FALSE_ALARM_REVIEWED':
                    ax.axvline(q['as_of_s'],color=COLORS[name],ls=':',lw=1)
                    ax.text(q['as_of_s']-.1,.84,'Reviewed false alarm',ha='right',fontsize=8)
                    break
        if name=='local_protection':
            times_with_states=[(r['time_s'],r['domains']['control_monitoring']['protection_latched']) for r in trace]
            reset=next(t for (old_t,latched),(t,new_latched) in zip(times_with_states,times_with_states[1:])
                       if latched and not new_latched)
            events=[e for e in run['events'] if e['kind']=='exogenous_boundary_input'
                    and e['parameter_id']=='internal_valve_opening']
            shut,reopened=(e['applied_at_s'] for e in events)
            for t,label,x_offset,y,alignment in (
                    (shut,'Pump interlock',-.04,.9,'right'),
                    (reopened,'Valve reopens; service remains off',.04,.43,'left'),
                    (reset,'PLC resets',.04,.9,'left')):
                ax.axvline(t,color=COLORS[name],ls=':',lw=.9)
                ax.text(t+x_offset,y,label,ha=alignment,fontsize=8)
        if name=='too_late':
            feedback,=run['intervention_public_feedback']
            ax.axvline(feedback['observed_at_s'],color=COLORS[name],ls=':',lw=1)
            ax.text(feedback['observed_at_s']+.05,.9,'Safety abort',fontsize=8)
            ax.scatter([feedback['arrived_at_s']],[.25],marker='o',s=30,color=COLORS[name],zorder=4)
            ax.text(feedback['arrived_at_s']-.08,.42,'NO_EFFECT arrives',ha='right',fontsize=8)
    axes[0].legend(loc='upper right',frameon=False,ncol=2,fontsize=9)
    fig.text(.09,.02,'Colored work bands mark professional work; review, repair and service recovery are separate events.',
             fontsize=9,color='#4a6574')
    png=args.output/'28-negative-service.png';svg=args.output/'28-negative-service.svg'
    fig.savefig(png,dpi=180,facecolor='white')
    fig.savefig(svg,metadata={'Date':None})
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(11.8,5.6))
    fig.subplots_adjust(left=.09,right=.95,top=.79,bottom=.17)
    fig.text(.09,.95,'Work can cost resources without restoring service',fontsize=20,weight='bold',va='top')
    fig.text(.09,.875,'Actual travel, access checks and professional labor are shown separately; all quantities here are person*s.',
             fontsize=10,color='#4a6574',va='top')
    for offset,(key,label) in zip((-.25,0,.25),METRICS):
        values=[records[name][0]['summary'][key] for name in LABELS]
        bars=ax.bar([x+offset for x in range(4)],values,width=.22,label=label,
                    color={'worker_travel_person_s':'#748796','access_check_person_s':'#b95021','worker_work_person_s':'#087a76'}[key])
        for bar,value in zip(bars,values):
            ax.text(bar.get_x()+bar.get_width()/2,value+.025,f'{value:g}',ha='center',va='bottom',fontsize=9)
    ax.set_xticks(range(4),[LABELS[name] for name in LABELS])
    ax.set_ylabel('Person*s')
    ax.set_ylim(0,1.25)
    ax.grid(axis='y',color='#e3e9ee',lw=.7)
    ax.set_axisbelow(True)
    ax.legend(frameon=False,ncol=3,loc='upper right',fontsize=9)
    for ext in ('png','svg'):
        fig.savefig(args.output/f'28-negative-work.{ext}',dpi=180,facecolor='white',**({'metadata':{'Date':None}} if ext=='svg' else {}))
    plt.close(fig)
    files=sorted(p.name for p in args.output.iterdir() if p.is_file())
    receipt=dict(status='RENDERED_PENDING_VISUAL_INSPECTION',source=sources,
        execution_source=saved['source'],python=sys.version,python_executable_sha256=digest(Path(sys.executable)),
        matplotlib=mpl.__version__,renderer_sha256=digest(Path(__file__)),new_project_calls=0,
        artifacts={name:digest(args.output/name) for name in files})
    with (args.output/'render.json').open('x',encoding='utf-8',newline='\n') as out:
        out.write(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=receipt['status'],files=files,new_project_calls=0)))


if __name__=='__main__':
    main()
