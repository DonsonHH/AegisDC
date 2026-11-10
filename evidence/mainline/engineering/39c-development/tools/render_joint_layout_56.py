"""Re-layout saved architecture and grayscale QA; reuse qualified55data unchanged."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import platform
import socket
import sys
import traceback
import types
import zipfile


def need(value, message):
    if not value:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def architecture(plt, output):
    from matplotlib.patches import FancyArrowPatch,FancyBboxPatch
    fig,ax=plt.subplots(figsize=(12,6));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    boxes={
        'plant':(.03,.73,.26,.18,'Private eight-domain plant\nworkers, tools, gates and service'),
        'evidence':(.37,.73,.26,.18,'Public arrived evidence\nfixed / handheld / work orders'),
        'dispatch':(.71,.73,.26,.18,'Public inspection / action choice\nqualifications and resource budgets'),
        'result':(.03,.39,.26,.18,'One actual RunResult\nprivate trace, work and public records'),
        'diagnostic':(.37,.39,.18,.18,'Private diagnostic /\ntemporal v3'),
        'closure':(.58,.39,.18,.18,'Private instance\nclosure v2'),
        'costs':(.79,.39,.18,.18,'Private actual\ncost v2'),
        'joint':(.37,.09,.39,.16,'One composite result\ncommon input / source / time binding'),
        'replay':(.80,.09,.17,.16,'Recorded read /\nexact replay\nPENDING')}
    for key,(x,y,w,h,label) in boxes.items():
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.01',
            facecolor='#e7f5ee' if key in ('evidence','dispatch') else '#eef3f8',
            edgecolor='#a1adb9',linestyle='--' if key=='replay' else '-',linewidth=1.1))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=9)
    def line(points):
        ax.plot([p[0] for p in points],[p[1] for p in points],color='#697b8d',linewidth=1.1)
    def arrow(a,b,dashed=False):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,linewidth=1.1,
            color='#697b8d',linestyle='--' if dashed else '-'))
    arrow((.29,.82),(.36,.82));arrow((.63,.82),(.70,.82))
    line([(.84,.73),(.84,.69),(.16,.69)]);arrow((.16,.69),(.16,.73))
    arrow((.16,.73),(.16,.58))
    line([(.29,.48),(.33,.48),(.33,.61),(.88,.61)])
    for x in (.46,.67,.88):
        arrow((x,.61),(x,.58));line([(x,.39),(x,.32)])
    line([(.46,.32),(.88,.32)]);arrow((.565,.32),(.565,.26))
    arrow((.76,.17),(.79,.17),True)
    ax.text(.50,.98,'Actual public/private boundaries and remaining replay work',ha='center',fontsize=14,fontweight='bold')
    ax.text(.50,.655,'Authorized work executes in the plant; only arrived evidence is returned to selection.',ha='center',fontsize=10)
    ax.text(.50,.02,'Green: public decision inputs. Blue: private plant/evaluator outputs. Private truth has no route into the selector.',ha='center',fontsize=9)
    for ext in ('png','svg'):
        fig.savefig(output/('joint-public-private-architecture.'+ext),dpi=300,bbox_inches='tight',metadata={'Creator':'AegisDC saved layout56'})
    plt.close(fig)


def main():
    need(not sys.flags.optimize,'Optimized authoring is forbidden')
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','snapshot','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();raw_manifest=args.manifest.read_bytes();m=json.loads(raw_manifest)
    root=Path('/root/private_data/aegisdc-mainline-39c').resolve()
    need(os.geteuid()==0 and socket.gethostname()==m['hostname'] and platform.python_version()=='3.12.7'
         and not os.environ.get('SLURM_JOB_ID') and Path('/root/private_data').is_mount(),'Saved layout host differs')
    need(args.output.resolve()==Path(m['output_root']).resolve() and args.output.resolve().is_relative_to(root),'Layout output differs')
    for name,expected in m['software'].items():need(version(name)==expected,'Plotting distribution differs:'+name)
    args.output.mkdir(mode=0o700,exist_ok=False)
    terminal=dict(status='FAILED',source=m['source_commit'],new_facility_calls=0,new_public_choices=0,new_model_calls=0,new_research_trials=0)
    save(args.output/'attempt.json',dict(classification='SAVED_LAYOUT_AND_GRAYSCALE_QA_ONLY',source=m['source_commit'],
        started_utc=datetime.now(timezone.utc).isoformat(),manifest_sha256=sha(raw_manifest),software=m['software']))
    try:
        need(sha(args.snapshot.read_bytes())==m['snapshot_sha256'],'Layout snapshot differs')
        with zipfile.ZipFile(args.snapshot) as z:
            need(sorted(z.namelist())==sorted(m['files']),'Layout file roles differ')
            data={name:z.read(name) for name in z.namelist()}
        for name,record in m['files'].items():need(len(data[name])==record['bytes'] and sha(data[name])==record['sha256'],'Input differs:'+name)
        prefix=m['qualified55_prefix'];q=json.loads(data[prefix+'/saved-qualification.json']);old_terminal=json.loads(data[prefix+'/terminal.json'])
        need(q['status']=='SAVED_JOINT_QUALIFICATION_PASSED' and q['original54_status']=='FAILED_RETAINED'
             and old_terminal['status']=='SAVED_JOINT_QUALIFICATION_AND_FIGURES_PASSED','Original saved55 qualification differs')
        need(len(q['cases'])==4 and all(c['saved_qualification']=='PASS' for c in q['cases']),'Saved case scope differs')
        copied=[]
        for name in ('joint-endpoints-and-costs.png','joint-endpoints-and-costs.svg','joint-actual-data.csv','saved-qualification.json'):
            raw=data[prefix+'/'+name]
            need(old_terminal['output_files'][name]==dict(bytes=len(raw),sha256=sha(raw)),'Original55 delivery hash differs')
            target='source-qualification55.json' if name=='saved-qualification.json' else name
            with (args.output/target).open('xb') as stream:stream.write(raw)
            copied.append(dict(name=target,source=prefix+'/'+name,bytes=len(raw),sha256=sha(raw)))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from PIL import Image
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none'})
        architecture(plt,args.output)
        parent=types.ModuleType('saved_authoring55')
        exec(compile(data[m['parent_authoring55']],m['parent_authoring55'],'exec'),parent.__dict__)
        parent.html_report(args.output,q)
        html_path=args.output/'AegisDC-joint-checkpoint.html'
        text=html_path.read_text(encoding='utf-8').replace('<h2>原失败与更正</h2>',
            '<h2>原失败与更正</h2><p>56仅修正架构图连线布局并生成灰度核对图；数据、主数据图及55保存资格不变，原55图保留。</p>')
        html_path.write_text(text,encoding='utf-8',newline='\n')
        grayscale=[]
        for name in ('joint-endpoints-and-costs','joint-public-private-architecture'):
            image_path=args.output/(name+'.png');gray=args.output/(name+'-grayscale-qa.png')
            with Image.open(image_path) as picture:
                need(picture.width>2000 and picture.height>1000,'Unexpected figure resolution')
                size=picture.size;picture.convert('L').save(gray)
            grayscale.append(dict(source=name+'.png',source_sha256=sha(image_path.read_bytes()),
                grayscale=gray.name,grayscale_sha256=sha(gray.read_bytes()),size=list(size)))
        need(not any(n=='aegis_dc' or n.startswith('aegis_dc.') for n in sys.modules),'Facility module imported')
        need(sha(args.manifest.read_bytes())==sha(raw_manifest) and sha(args.snapshot.read_bytes())==m['snapshot_sha256'],'Layout inputs changed')
        save(args.output/'layout-and-qa.json',dict(status='LAYOUT_CORRECTED_GRAYSCALE_PREVIEWS_GENERATED',
            data_and_main_figure_unchanged=copied,grayscale=grayscale,visual_review='PENDING_ACTUAL_VIEW',
            original55_qualification=q['status'],original54_status='FAILED_RETAINED',new_facility_calls=0,new_research_trials=0))
        terminal.update(status='SAVED_LAYOUT_CORRECTION_AND_QA_READY',original54_status='FAILED_RETAINED',
            original55_qualification='PASS_UNCHANGED',new_qualification_executed=False)
    except BaseException as error:
        terminal.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in args.output.iterdir() if p.is_file()})
        save(args.output/'terminal.json',terminal)
    print(json.dumps(dict(status=terminal['status'],new_facility_calls=0,new_research_trials=0)))


if __name__=='__main__':main()
