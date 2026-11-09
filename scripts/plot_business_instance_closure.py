"""Render original instance closure observations and their public evidence gates."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback


def require(ok, message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False);stream.write('\n')


def main():
    if sys.flags.optimize:raise SystemExit('Optimized evidence rendering is forbidden')
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(os.environ.get('SLURM_JOB_ID') and socket.gethostname().split('.')[0]!='mu01','Use Slurm compute')
    root=args.manifest.resolve().parent;manifest=json.loads(args.manifest.read_bytes());manifest_sha=sha(args.manifest)
    args.output.mkdir(exist_ok=False)
    save(args.output/'attempt.json',dict(classification='SAVED_ONLY_FIGURE_RENDER_NOT_RESEARCH',
        source_commit=manifest['source_commit'],manifest_sha256=manifest_sha,slurm_job_id=os.environ['SLURM_JOB_ID'],
        interpreter_optimize=0,started_at_utc=datetime.now(timezone.utc).isoformat(),new_facility_calls=0,new_model_calls=0,new_research_trials=0))
    terminal=dict(status='FAILED',source_commit=manifest['source_commit'],new_facility_calls=0,new_model_calls=0,new_research_trials=0)
    try:
        def guard():
            require(sha(args.manifest)==manifest_sha,'Frozen manifest changed')
            require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==manifest['source_commit'],'Render source changed')
            for name,record in manifest['files'].items():
                path=root/name
                require(path.resolve().is_relative_to(root) and not path.is_symlink(),'Input escaped source')
                require(path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],'Input differs: '+name)
        guard()
        folder=root/'evidence/mainline/engineering/39c-development/slice-18/21-instance-service-qualification'
        original_terminal=json.loads((folder/'terminal.json').read_bytes())
        original_manifest=json.loads((folder/'source-manifest.json').read_bytes())
        input_identity=json.loads((folder/'case-input-identity.json').read_bytes())
        source='8eeef6b724a130dad12fb21cfe8bf68c46ec47f5'
        require(original_terminal['status']=='QUALIFICATION_BEHAVIORS_PASSED' and original_manifest['source_commit']==source,'Original qualification differs')
        require(input_identity['all_other_actual_input_fields_equal'] and input_identity['original133377_negative_input_equal'],'Actual case input identity missing')
        cases=['network-healthy','network-still-blocked'];labels=['Network healthy (1)','Network limited (0.25)']
        rows=[];assessments=[];states=[]
        for case in cases:
            saved={}
            for name in ('business-result.json','actual-instance-summary.json'):
                path=folder/('cases--'+case+'--'+name);record=original_terminal['output_files']['cases/'+case+'/'+name]
                require(path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],'Original saved case differs')
                saved[name]=json.loads(path.read_bytes())
            business=saved['business-result.json'];actual=saved['actual-instance-summary.json']
            identity=business['execution_code_identity']
            require(identity==actual['code_identity'] and identity['git_commit']==source and not identity['implementation_has_changes'],'Actual runtime identity differs')
            for name,digest in identity['files'].items():require(digest==original_manifest['files'][name]['sha256'],'Original runtime file differs')
            event=business['episodes'][0];work={row['id']:row for row in actual['work_records']}
            rows.append(dict(case_id=case,window_s=business['window_end_s'],action_completed_s=event['actual_action_completed_at_s'],
                action_report_arrived_s=event['action_report_arrived_at_s'],recheck_completed_s=work['cooling-direct/recheck-0']['completed_at_s'],
                first_verified_closed_s=event['first_verified_closed_at_s'],closure_right_censored=event['closure_right_censored'],
                latest_status=event['latest_assessed_status'],service_deficit_s=actual['summary']['service_deficit_time_s'],
                work_person_s=actual['summary']['worker_work_person_s'],travel_person_s=actual['summary']['worker_travel_person_s'],
                access_person_s=actual['summary']['access_check_person_s'],wait_person_s=actual['summary']['worker_wait_person_s']))
            states.append([row['status'] for row in event['assessments']])
            for row in event['assessments']:
                assessments.append(dict(case_id=case,at_s=row['as_of_s'],status=row['status'],risk_closed=row['risk_closed']))
        for filename,data in [('instance-endpoints.csv',rows),('instance-assessments.csv',assessments)]:
            with (args.output/filename).open('x',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(data[0]),lineterminator='\n');writer.writeheader();writer.writerows(data)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch,FancyBboxPatch,Patch
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
        figure=plt.figure(figsize=(16,10))
        figure.text(.04,.95,'Actual work and joint evidence verification',fontsize=21,fontweight='bold',color='#16384c')
        figure.text(.04,.90,'Two saved 6 s engineering conditions; only the declared network capacity differs. Original failures are retained.',fontsize=11,color='#526c7d')
        axis=figure.add_axes([.235,.54,.46,.25]);axis.set_xlim(-.5,5.5);axis.set_ylim(1.65,-.7)
        axis.set_yticks([0,1],labels);axis.tick_params(length=0,pad=10)
        axis.set_xticks(range(6),['0','3.75','4.5','5','5.5','6']);axis.set_xlabel('Actual public assessment time / s',labelpad=10)
        palette={'OPEN_UNCONFIRMED':('#e3e9ef','Open'), 'ACTION_COMPLETED_PENDING_VERIFICATION':('#f3e6cd','Pending'),
                 'VERIFIED_CLOSED':('#6ca89a','Verified'), 'SYMPTOM_RETREATED_PENDING_VERIFICATION':('#dfae7b','Service\nunverified')}
        for i,values in enumerate(states):
            require(len(values)==6,'Actual assessment grid differs')
            for j,status in enumerate(values):
                color,label=palette[status]
                axis.add_patch(FancyBboxPatch((j-.46,i-.32),.92,.64,boxstyle='round,pad=.01',fc=color,ec='white'))
                axis.text(j,i,label,ha='center',va='center',fontsize=9,color='#16384c')
        axis.set_title('Sampled public lifecycle',loc='left',pad=20,fontweight='bold')
        for spine in axis.spines.values():spine.set_visible(False)
        table=figure.add_axes([.76,.54,.21,.25]);table.axis('off');table.set_xlim(-.5,1.5);table.set_ylim(1.65,-.7)
        table.set_title('Saved endpoints',loc='left',pad=20,fontweight='bold')
        table.text(0,-.5,'First close / s',ha='center',fontsize=9,color='#5d7483');table.text(1,-.5,'Deficit / s',ha='center',fontsize=9,color='#5d7483')
        for i,row in enumerate(rows):
            table.text(0,i,'censored' if row['first_verified_closed_s'] is None else f"{row['first_verified_closed_s']:g}",ha='center',va='center',fontsize=13,color='#173d52')
            table.text(1,i,f"{row['service_deficit_s']:g}",ha='center',va='center',fontsize=13,color='#173d52')
        figure.text(.04,.43,'Both cases: action completed 3.25 s; report 3.75 s; own recheck sampled 5 s and arrived 5.5 s.',fontsize=10,color='#345368')
        flow=figure.add_axes([.04,.225,.93,.145]);flow.set_xlim(0,15);flow.set_ylim(0,2);flow.axis('off')
        titles=['Instance identity','Own action + ACK','Own recheck + ACK','Condition + service','Finite assessment']
        bodies=['template + opening + slot','APPLIED; arrived work report','Issued after own action report','2 genuine samples per role\n1 s span; current evidence','Verify or remain unclosed']
        for index,(title,body) in enumerate(zip(titles,bodies)):
            x=index*3
            flow.add_patch(FancyBboxPatch((x+.04,.22),2.65,1.5,boxstyle='round,pad=.05',fc='#edf4f7' if index!=3 else '#e8f1ed',ec='#bacbd5'))
            flow.text(x+.2,1.43,title,ha='left',va='center',fontsize=10,fontweight='bold',color='#193d52')
            flow.text(x+.2,.91,body,ha='left',va='center',fontsize=8.5,color='#436171',linespacing=1.5)
            if index<4:flow.add_patch(FancyArrowPatch((x+2.72,.95),(x+2.99,.95),arrowstyle='-|>',mutation_scale=14,color='#8199a8'))
        figure.text(.04,.195,'All gates use arrived public evidence. The private evaluator extracts completed-run endpoints; no truth returns to dispatch.',fontsize=10,color='#345368')
        figure.text(.04,.132,'The healthy-network service was already fully delivered during this window. Verification is not a demonstrated service-restoration gain.',fontsize=10,color='#526c7d')
        figure.text(.04,.088,'Shared actual costs: work 2 person-s; travel 2 person-s; access 0.5 person-s; wait 0.5 person-s. Budget envelopes are separate.',fontsize=10,color='#526c7d')
        figure.text(.04,.044,'Original 180 registered trials unchanged. This is finite synthetic engineering qualification, not a policy-effect comparison or field calibration.',fontsize=10,color='#526c7d')
        figure.canvas.draw();renderer=figure.canvas.get_renderer();bounds=[]
        for artist in figure.findobj(matplotlib.text.Text):
            if not artist.get_visible() or not artist.get_text():continue
            box=artist.get_window_extent(renderer);canvas=figure.bbox
            if box.x0<canvas.x0-1 or box.y0<canvas.y0-1 or box.x1>canvas.x1+1 or box.y1>canvas.y1+1:bounds.append(artist.get_text())
        for extension in ('png','svg'):figure.savefig(args.output/('instance-joint-verification.'+extension),dpi=140,facecolor='white')
        plt.close(figure);require(not bounds,'Text extends beyond canvas: '+json.dumps(bounds))
        guard();terminal.update(status='SAVED_INSTANCE_FIGURE_RENDERED',source_guard='PASS_BEFORE_AND_AFTER',
            original_job='133378',original_runtime_source=source,source_rows=2,assessment_rows=12,figures=1,pngs=1,svgs=1,
            interpreter_optimize=0,text_bounds='PASS',visual_inspection='PENDING_SEPARATE_ACTUAL_VIEW')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc());raise
    finally:
        terminal['output_files']={path.relative_to(args.output).as_posix():dict(bytes=path.stat().st_size,sha256=sha(path)) for path in args.output.rglob('*') if path.is_file()}
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(args.output/'terminal.json',terminal)
    print(json.dumps(terminal))


if __name__=='__main__':main()
