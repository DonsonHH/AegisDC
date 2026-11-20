"""Run only predeclared engineering witnesses on an identified Slurm allocation."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'docs/mainline/v6-native-comparison-qualification-v1'
sys.path.insert(0,str(PACK))
import oracle
import witnesses


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--launch',type=Path,required=True)
    parser.add_argument('--sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(sha(args.launch)==args.sha,'Launch hash differs')
    launch=read(args.launch)
    out=args.output.resolve()
    require(str(out)==launch['output'] and os.environ.get('SLURM_JOB_ID') and
            os.environ.get('SLURM_CPUS_PER_TASK')=='1' and os.environ.get('SLURM_MEM_PER_NODE')=='1024',
            'Wrong allocation or destination')
    out.mkdir()
    f=read(PACK/'fixtures.json')
    report=dict(schema='aegisdc-native-comparison-engineering-attempt-v1',mode=launch['mode'],job=os.environ['SLURM_JOB_ID'],
        launch_sha256=args.sha,implementation_revision=launch['implementation_revision'],checker_revision=launch['checker_revision'],
        checks={},historical_reads={},public_started=[],public_returned=[],substitutes_started=[],substitutes_returned=[],
        facility_started=0,facility_returned=0,facility_unreturned=0,internal_policy_known=0,unknown_facility_internal=[],
        unexecuted=[],research_runs=0)
    try:
        for name,digest in launch['files'].items():require(sha(ROOT/name)==digest,'Source identity differs: '+name)
        require(sha(Path(sys.executable).resolve())==launch['python_sha256'],'Interpreter drift')
        for name,digest in f['source_sha256'].items():require(sha(ROOT/name)==digest,'Frozen document drift: '+name)
        if launch['mode']=='red':
            missing=importlib.util.find_spec('aegis_dc.native_compare_run') is None
            report.update(expected_red=missing,status='EXPECTED_RED_ABSENT_COMPARISON_ENTRY' if missing else 'UNEXPECTED_BASELINE')
            return 2 if missing else 1
        from aegis_dc.native_compare_inputs import Conditions
        from aegis_dc.native_compare_run import run_native
        from aegis_dc.native_compare_score import read_native
        from aegis_dc.dispatch_policy import choose_work
        conditions=Conditions(ROOT)
        units=launch['units']
        definitions={cat:{u.get('unit',u.get('id')):u for u in f[cat]} for cat in ('public','facilities','fixtures')}
        require(all(len(set(units[cat]))==len(units[cat]) and set(units[cat])<=defs.keys() for cat,defs in definitions.items()),'Undeclared engineering unit')
        require(launch['purpose']=='PUBLIC_ENGINEERING' and launch['research_execution'] is False,'Engineering purpose required')
        if launch['mode']=='initial':
            require(all(units[cat]==list(defs) for cat,defs in definitions.items()),'Initial denominator drift')
        def prior(label):
            defn=f['prior_runs'][label]
            directory=Path(f['prior_root'])/defn['attempt']/'output'/defn['unit']/'run'
            raw=directory/'run.json';actual=sha(raw)
            require(actual==defn['run_sha256'],'Historical native source drift')
            report['historical_reads'][label]=dict(path=str(raw),sha256=actual)
            return directory
        for key in units['public']:
            u=definitions['public'][key];path=out/('public-'+key);path.mkdir()
            try:
                doc=conditions.call(u['condition'],u['arm'])
                require(oracle.json_sha(doc)==u['call_sha256'],'Public program input drift')
                arg=witnesses.public_arguments(u,doc,read(prior(u['prefix'])/'run.json'))
                write(path/'arguments.json',arg)
                write(path/'begin.json',dict(entry='choose_work',argument_sha256=oracle.json_sha(arg)))
                report['public_started'].append(key)
                ret=choose_work(**arg)
                report['public_returned'].append(key)
                write(path/'return.json',ret)
                result=oracle.public(u,ret)
                result.update(input_sha256=sha(path/'arguments.json'),output_sha256=sha(path/'return.json'))
                report['checks']['public/'+key]=result
            except Exception:
                report['checks']['public/'+key]=dict(passed=False,error=traceback.format_exc())
        for key in units['fixtures']:
            u=definitions['fixtures'][key];path=out/('substitute-'+key);path.mkdir()
            try:
                input_path=prior('direct') if key=='Z3' else None
                write(path/'begin.json',dict(fixture_sha256=oracle.json_sha(u)))
                report['substitutes_started'].append(key)
                actual=witnesses.substitutes(u,path,input_path)
                report['substitutes_returned'].append(key)
                write(path/'return.json',actual)
                report['checks']['fixtures/'+key]=oracle.substitute(u,actual)
            except Exception:
                report['checks']['fixtures/'+key]=dict(passed=False,error=traceback.format_exc())
        if any(not v['passed'] for v in report['checks'].values()):
            report['unexecuted']=['facilities/'+k for k in units['facilities']]
        elif units['facilities']:
            order=[(definitions['facilities'][key]['condition'],definitions['facilities'][key]['arm']) for key in units['facilities']]
            def after_arm(case,arm,path,scored):
                key=case+'-'+arm
                run,trace,balances=read_native(path/'run')
                result=oracle.facility(definitions['facilities'][key],run,trace,balances,scored)
                report['checks']['facilities/'+key]=result
                write(path/'engineering-assertions.json',result)
                if not result['passed']:raise ValueError('Frozen engineering assertion failed: '+key)
            ledger=run_native(out/'native',order,conditions,after_arm=after_arm)
            report.update(facility_started=ledger['started'],facility_returned=ledger['complete_returns'],
                facility_unreturned=ledger['unreturned'],internal_policy_known=ledger['known_policy_subtotal'],
                unknown_facility_internal=[r['unit'] for r in ledger['rows'] if r['started'] and r['internal_policy_calls'] is None],
                native_ledger=ledger)
            report['unexecuted']=['facilities/'+r['unit'] for r in ledger['rows'] if r['state']=='NOT_EXECUTED']
            report['checks']['native-order']=oracle.native_order(ledger,units['facilities'])
        expected={cat+'/'+key for cat,vals in units.items() for key in vals}
        report['unexecuted']=sorted(set(report['unexecuted'])|{key for key in expected if key not in report['checks'] and
             (not key.startswith('facilities/') or key.split('/')[1] not in {r['unit'] for r in report.get('native_ledger',{}).get('rows',[]) if r['started']})})
        report['passed']=(expected<=report['checks'].keys() and not report['unexecuted'] and all(c['passed'] for c in report['checks'].values()))
        return 0 if report['passed'] else 1
    except Exception:
        report.update(passed=False,fatal=traceback.format_exc())
        return 1
    finally:
        artifacts={}
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name!='report.json':
                artifacts[path.relative_to(out).as_posix()]=dict(sha256=sha(path),bytes=path.stat().st_size)
        write(out/'durable-files.json',artifacts)
        report['durable_manifest_sha256']=sha(out/'durable-files.json')
        write(out/'report.json',report)


if __name__=='__main__':sys.exit(main())
