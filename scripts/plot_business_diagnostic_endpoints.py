"""Render saved public judgements and private event counts without new evaluation."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def main():
    if sys.flags.optimize:raise SystemExit('Optimized evidence rendering is forbidden')
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--matrix-only',action='store_true');args=parser.parse_args()
    require(bool(os.environ.get('SLURM_JOB_ID')) and socket.gethostname().split('.')[0]!='mu01','Use a Slurm compute allocation')
    root=args.manifest.resolve().parent;manifest=json.loads(args.manifest.read_bytes());manifest_sha=sha(args.manifest)
    args.output.mkdir(exist_ok=False)
    save(args.output/'attempt.json',dict(classification='SAVED_ONLY_FIGURE_RENDER_NOT_RESEARCH',
        source_commit=manifest['source_commit'],manifest_sha256=manifest_sha,slurm_job_id=os.environ['SLURM_JOB_ID'],
        interpreter_optimize=sys.flags.optimize,started_at_utc=datetime.now(timezone.utc).isoformat(),
        new_facility_calls=0,new_model_calls=0,new_research_trials=0))
    terminal=dict(status='FAILED',source_commit=manifest['source_commit'],new_facility_calls=0,new_model_calls=0,new_research_trials=0)
    try:
        def guard():
            require(sha(args.manifest)==manifest_sha,'Frozen render manifest changed')
            require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==manifest['source_commit'],'Actual render Git source differs')
            for name,record in manifest['files'].items():
                path=root/name
                require(path.resolve().is_relative_to(root) and not path.is_symlink(),'Render input path differs')
                require(path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],'Frozen render input differs: '+name)
        guard()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch,FancyBboxPatch,Patch
        import numpy as np
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
        data_root=root/'evidence/mainline/engineering/39c-development/slice-04/07-state-diagnostic-qualification'
        csv_path=root/'evidence/mainline/engineering/39c-development/slice-07/10-saved-verifier-mode-green/outputs/normal-child/original-six-endpoints.csv'
        audit=json.loads((csv_path.parent/'terminal.json').read_bytes())
        require(audit['status']=='SAVED_ORIGINALS_AND_CORRECTED_LITERAL_PASSED' and audit['interpreter_optimize']==0,'Need audited saved source in normal mode')
        rows=list(csv.DictReader(csv_path.read_text(encoding='utf-8').splitlines()))
        identifiers=['normal','no-human-fault','no-human-normal','wrong-demand-model','uncertain','unmodeled-proxy']
        labels=['Normal state','No human / fault','No human / normal','Wrong demand model','Uncertain interval','Unmodeled root cause']
        require([row['case_id'] for row in rows]==identifiers,'Saved case order differs')
        states={'UNKNOWN':0,'NORMAL':1,'ABNORMAL':2};colors=['#d8e1eb','#4d9b8f','#d58b57']
        matrix=[];truth=[];counts=[];export=[]
        for row,identifier in zip(rows,identifiers):
            result=json.loads((data_root/(identifier+'--business-result.json')).read_bytes())
            require(result['execution_code_identity']['git_commit']=='3e81e7faa61d1021cc9418172171de86e370750f','Original diagnostic source differs')
            event=result['events'][0];assessments=event['assessments']
            require([entry['available_at_s'] for entry in assessments]==[0,1.75,2],'Actual assessment clocks differ')
            public=[entry['public_status'] for entry in assessments]
            matrix.append([states[entry] for entry in public]);truth.append(row['initial_truth'])
            counts.append([int(row[k]) for k in ('fault_denominator','missed','normal_denominator','false_positive')])
            export.append(dict(case_id=identifier,initial_truth=row['initial_truth'],at0=public[0],at1_75=public[1],at2=public[2],
                **{k:row[k] for k in ('fault_denominator','missed','normal_denominator','false_positive')}))
        with (args.output/'diagnostic-plot-data.csv').open('x',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(export[0]),lineterminator='\n');writer.writeheader();writer.writerows(export)
        from matplotlib.colors import ListedColormap,BoundaryNorm
        fig=plt.figure(figsize=(14,7.2));grid=fig.add_gridspec(1,2,width_ratios=[1.28,1],left=.18,right=.97,top=.79,bottom=.30,wspace=.42)
        left=fig.add_subplot(grid[0]);right=fig.add_subplot(grid[1])
        left.imshow(np.array(matrix),cmap=ListedColormap(colors),norm=BoundaryNorm([-.5,.5,1.5,2.5],3),aspect='auto')
        left.set_xticks(range(3),['0 s','1.75 s','2 s']);left.set_yticks(range(6),labels)
        left.set_title('Public sampled condition',loc='left',pad=16,fontweight='bold');left.tick_params(length=0,pad=10)
        for i,values in enumerate(matrix):
            for j,value in enumerate(values):left.text(j,i,list(states)[value],ha='center',va='center',fontsize=9,color='#162b3b')
        for edge in np.arange(.5,6,1):left.axhline(edge,color='white',lw=3)
        left.set_xlabel('Judgement availability time; sample observed at 1.25 s',labelpad=13,fontsize=9)
        right.set_xlim(-.5,3.5);right.set_ylim(5.5,-.5);right.set_yticks(range(6),truth);right.tick_params(length=0,pad=10)
        right.set_xticks(range(4),['Fault\nopportunity','Missed\nconfirmation','Normal\nevent','False\npositive'],fontsize=9)
        right.set_title('One declared event per case',loc='left',pad=16,fontweight='bold')
        for i,values in enumerate(counts):
            for j,value in enumerate(values):
                right.add_patch(FancyBboxPatch((j-.43,i-.38),.86,.76,boxstyle='round,pad=.01',linewidth=0,
                    facecolor=('#e2edf5' if j%2==0 else '#f4dfd5') if value else '#f2f4f6'))
                right.text(j,i,str(value),ha='center',va='center',fontweight='bold' if value else 'normal',color='#233b4d' if value else '#718292')
        right.set_xlabel('Counts from the fixed event table; no sample-based accuracy',labelpad=13,fontsize=9)
        right.set_ylabel('Private initial event truth',labelpad=8,fontsize=9)
        for axis in [left,right]:
            for spine in axis.spines.values():spine.set_visible(False)
        fig.suptitle('State judgements and fixed opportunity denominators',x=.04,y=.96,ha='left',fontsize=19,fontweight='bold',color='#16384c')
        fig.text(.04,.89,'Six saved engineering variants, not independent research trials. Original failed assertion and corrections are retained.',fontsize=10,color='#506679')
        fig.text(.04,.07,'Wrong-model case: actual usable capacity 0.5 meets demand 0.5; public model still assumes 1.\nUnmodeled cause: a capacity finding cannot establish a root cause. Zero applicable denominators produce null rates.',fontsize=10,color='#344e60',linespacing=1.6)
        figures=[('diagnostic-state-and-denominators',fig)]
        fig,axis=plt.subplots(figsize=(13,7.5));axis.set_xlim(0,13);axis.set_ylim(0,7.5);axis.axis('off')
        def box(x,y,w,h,title,body,fill):
            axis.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.12',fc=fill,ec='#b8c9d5',lw=1))
            axis.text(x+.18,y+h-.3,title,ha='left',va='top',fontsize=12,fontweight='bold',color='#15374b')
            axis.text(x+.18,y+h-.76,body,ha='left',va='top',fontsize=10,color='#345368',linespacing=1.55)
        def arrow(a,b):axis.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=17,lw=1.5,color='#6d8a9c'))
        axis.text(.2,7.1,'Public judgements and private event evaluation',fontsize=19,fontweight='bold',color='#16384c')
        axis.text(.2,6.65,'Architecture of the implemented diagnostic slice; separate from verified closure and causal gain.',fontsize=10,color='#506679')
        box(.25,4.25,3.65,1.9,'Available public frame','Records + source / time / error\nDeclared nominal knowledge\nExternal work order = context','#edf4f8')
        box(4.6,4.25,3.65,1.9,'Public condition assessment','Qualify first, then latest sample\nUNKNOWN / NORMAL / ABNORMAL\nKeep observation and arrival clocks','#e6f1ee')
        box(9,4.25,3.6,1.9,'Public decision record','Sampled scalar state only\nNo private labels or opportunities\nRepeated record is not a new event','#edf4f8')
        arrow((3.9,5.2),(4.58,5.2));arrow((8.25,5.2),(8.98,5.2))
        box(.25,.9,3.65,2.15,'Private evaluation inputs','Exact completed-run trace\nPredeclared event + state predicate\nFixed reference opportunity / window\nUnknown truth stays UNKNOWN','#f3ece7')
        box(4.6,.9,3.65,2.15,'Post-run event evaluator','Compare at observation time\nCount each event once\nMiss / false positive / censoring\nNo denominator => null rate','#f5f0e5')
        box(9,.9,3.6,2.15,'Saved endpoint table','Normal, fault, unknown all kept\nNo-human does not erase opportunity\nPrevention effect NOT IDENTIFIED\nOriginal failures stay visible','#edf4f8')
        arrow((3.9,1.95),(4.58,1.95));arrow((8.25,1.95),(8.98,1.95));arrow((10.8,4.23),(6.4,3.1))
        axis.plot([.25,12.6],[3.6,3.6],ls='--',color='#c7b7ab',lw=1)
        axis.text(.3,3.75,'PUBLIC DECISION SIDE',fontsize=9,color='#6b8291')
        axis.text(.3,3.31,'PRIVATE, AFTER RUN COMPLETION',fontsize=9,color='#90745f')
        axis.text(.25,.28,'No private-to-dispatch path. Engineering scope; 180 registered baseline trials remain unchanged; field calibration pending.',fontsize=9,color='#506679')
        fig.subplots_adjust(left=0,right=1,top=1,bottom=0)
        if args.matrix_only:plt.close(fig)
        else:figures.append(('diagnostic-public-private-architecture',fig))
        bounds=[]
        for identifier,figure in figures:
            figure.canvas.draw();renderer=figure.canvas.get_renderer();canvas=figure.bbox
            for artist in figure.findobj(matplotlib.text.Text):
                if not artist.get_visible() or not artist.get_text():continue
                bound=artist.get_window_extent(renderer)
                if bound.x0<canvas.x0-1 or bound.y0<canvas.y0-1 or bound.x1>canvas.x1+1 or bound.y1>canvas.y1+1:
                    bounds.append(dict(figure=identifier,text=artist.get_text()))
            for extension in ('png','svg'):figure.savefig(args.output/(identifier+'.'+extension),dpi=140,facecolor='white')
            plt.close(figure)
        require(not bounds,'Figure text extends beyond canvas: '+json.dumps(bounds))
        guard();terminal.update(status='SAVED_FIGURES_RENDERED',source_guard='PASS_BEFORE_AND_AFTER',
            input_original_job='133274',audited_saved_job='133282',original_runtime_source='3e81e7faa61d1021cc9418172171de86e370750f',
            figures=len(figures),pngs=len(figures),svgs=len(figures),source_rows=6,interpreter_optimize=0,text_bounds='PASS',visual_inspection='PENDING_SEPARATE_ACTUAL_VIEW')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc());raise
    finally:
        terminal['output_files']={p.relative_to(args.output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in args.output.rglob('*') if p.is_file()}
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(args.output/'terminal.json',terminal)
    print(json.dumps(terminal))


if __name__=='__main__':main()
