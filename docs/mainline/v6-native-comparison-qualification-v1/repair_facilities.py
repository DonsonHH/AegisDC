"""Affected-only repair. Retain the initial oracle; apply the pre-existing event coordinate law."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import traceback
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import oracle
from aegis_dc.native_compare_inputs import Conditions, file_hash, read, write_new
from aegis_dc.native_compare_run import run_native
from aegis_dc.native_compare_score import read_native
from patrol_rsi.contracts import digest


def need(condition, message):
    if not condition:raise ValueError(message)


def facility_result(unit,run,trace,balances,score):
    original=oracle.facility(unit,run,trace,balances,score)
    names={'network recovery','real exogenous writes'}
    legacy=[a for a in original['assertions'] if a['field'] in names]
    replaced=[a for a in original['assertions'] if a['field'] not in names]
    extra=oracle.Assertions(unit['unit'])
    events=[e for e in run['events'] if e.get('kind')=='exogenous_boundary_input']
    if legacy:
        ex=unit['expected']
        if 'event_bindings' in ex:
            expected=ex['event_bindings']
            seen=events
        else:
            expected=[[ex['network_recovery_s'],'network_service_capacity',1]]
            seen=[e for e in events if e['parameter_id']=='network_service_capacity' and e['value']==1]
        extra.equal('requested exogenous identity, time and value',[[e['time_s'],e['parameter_id'],e['value']] for e in seen],expected)
        convention=run['time_coordinate_convention']
        extra.equal('frozen facility clock declaration',[convention['version'],convention['coincidence_ulps']],['aegisdc-binary64-time-v1',8])
        epochs={r['time_s'] for r in trace}
        pairs=[]
        for e in seen:
            requested,processed=e['time_s'],e['applied_at_s']
            pairs.append([requested,processed])
            extra.equal('actual application is a saved native epoch '+e['parameter_id']+' '+str(requested), processed in epochs,True)
            # This bound is the original native clock contract; the requested time is also checked exactly above.
            extra.equal('processing coordinate within eight ulps '+e['parameter_id']+' '+str(requested),
                math.isfinite(processed) and abs(processed-requested)<=8*max(math.ulp(requested),math.ulp(processed)),True)
    else:
        pairs=[]
    if 'split_s' in unit['expected']:
        for start,end,minimum in [(0,4,2),(4,10,3)]:
            duration=L=U=0
            for i,b in enumerate(balances):
                dt=max(0,min(end,b['end_s'])-max(start,b['start_s']))
                it=trace[i]['domains']['it_service']
                duration+=dt; U+=dt*(it['demand']-it['delivered'])
                L+=dt*(it['demand']-it['delivered'])/it['demand'] if it['demand'] else 0
            extra.equal('whole split coverage '+str(start),abs(duration-(end-start))<=1e-8,True)
            extra.equal('whole split lower bounds '+str(start),L>=minimum-1e-8 and U>=minimum-1e-8,True)
    assertions=replaced+extra.items
    return dict(unit=unit['unit'],assertions=assertions,passed=all(a['passed'] for a in assertions),
                retained_original_coordinate_checks=legacy,requested_and_applied=pairs)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--launch',type=Path,required=True)
    parser.add_argument('--sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    need(file_hash(args.launch)==args.sha,'Launch binding differs')
    launch=read(args.launch);out=args.output.resolve()
    need(launch['mode']=='repair' and launch['purpose']=='PUBLIC_ENGINEERING' and not launch['research_execution'] and
        launch['output']==str(out) and os.environ.get('SLURM_JOB_ID') and os.environ['SLURM_CPUS_PER_TASK']=='1'
        and os.environ['SLURM_MEM_PER_NODE']=='1024','Wrong launch type, output or allocation')
    out.mkdir()
    report=dict(schema='aegisdc-native-comparison-engineering-attempt-v1',mode='repair',job=os.environ['SLURM_JOB_ID'],
        launch_sha256=args.sha,implementation_revision=launch['implementation_revision'],checker_revision=launch['checker_revision'],
        checks={},historical_reads={},public_started=[],public_returned=[],substitutes_started=[],substitutes_returned=[],
        facility_started=0,facility_returned=0,facility_unreturned=0,internal_policy_known=0,unknown_facility_internal=[],
        unexecuted=[],research_runs=0)
    try:
        for path,identity in launch['files'].items():need(file_hash(ROOT/path)==identity,'Staged file differs: '+path)
        need(file_hash(Path(sys.executable).resolve())==launch['python_sha256'],'Interpreter differs')
        f=read(Path(__file__).parent/'fixtures.json')
        for path,identity in f['source_sha256'].items():need(file_hash(ROOT/path)==identity,'Freeze drift: '+path)
        first_dir=out.parent.parent/'initial01'
        earlier=first_dir/'output/report.json'
        terminal=first_dir/'terminal-account.json'
        selection=launch['repair']
        need(file_hash(earlier)==selection['prior_report_sha256'] and file_hash(terminal)==selection['prior_terminal_sha256'],'Earlier evidence drift')
        old=read(earlier);account=read(terminal)
        need(account['native']['status']=='COMPLETE_ACCOUNTING' and account['checker_summary_consistent']
            and account['native']['started']==account['native']['complete_returns']==1
            and old['public_started']==old['public_returned'] and len(old['public_returned'])==27 and len(old['substitutes_returned'])==4,
            'Earlier accounting is not safe to retry')
        need(all(v['passed'] for k,v in old['checks'].items() if k.startswith(('public/','fixtures/'))),'Unexpected failed public or substitute unit')
        frozen={u['unit']:u for u in f['facilities']}
        requested=launch['units']['facilities']
        affected=[r['unit'] for r in old['native_ledger']['rows'] if r['state'] in ('FAILED','NOT_EXECUTED')]
        need(requested==affected==list(frozen) and not launch['units']['public'] and not launch['units']['fixtures'],'Retry scope differs')
        need(old['internal_policy_known']+20*len(requested)<=f['scope']['total_internal_decision_cap'],'Retry would exceed budget')
        report['transferred']={'initial_report_sha256':file_hash(earlier),'public':old['public_returned'],'fixtures':old['substitutes_returned']}
        conditions=Conditions(ROOT)
        runtime_files={p:h for p,h in launch['files'].items() if (p.startswith('src/aegis_dc/') and p.count('/')==2 and p.endswith('.py')) or p=='src/patrol_rsi/contracts.py'}
        def after(case,arm,path,score):
            name=case+'-'+arm
            run,trace,balances=read_native(path/'run')
            u=frozen[name]
            need(run['code_identity']['files']==runtime_files and run['code_identity']['source_tree_sha256']==digest(runtime_files),'Returned runtime differs from actual staged sources')
            inputs=run['inputs']
            need(inputs['duration_s']==10 and inputs['maximum_step_s']==0.01 and not inputs.get('action_commands',[])
                and u['identities']['scenario']==digest(read(path/'run/scenario.json')), 'Returned native fixed input differs')
            result=facility_result(u,run,trace,balances,score);report['checks']['facilities/'+name]=result
            write_new(path/'engineering-assertions.json',result)
            if not result['passed']:raise ValueError('Engineering witness mismatch: '+name)
        ledger=run_native(out/'native',[(frozen[n]['condition'],frozen[n]['arm']) for n in requested],conditions,after_arm=after)
        report.update(native_ledger=ledger,facility_started=ledger['started'],facility_returned=ledger['complete_returns'],
            facility_unreturned=ledger['unreturned'],internal_policy_known=ledger['known_policy_subtotal'],
            unknown_facility_internal=[r['unit'] for r in ledger['rows'] if r['started'] and r['internal_policy_calls'] is None],
            unexecuted=['facilities/'+r['unit'] for r in ledger['rows'] if r['state']=='NOT_EXECUTED'])
        report['checks']['native-order']=(oracle.native_order(ledger,requested) if all(r['state']=='COMPLETED' for r in ledger['rows'])
            else dict(passed=False,actual_states=[[r['unit'],r['state']] for r in ledger['rows']],reason='Retained failed arm or unexecuted suffix'))
        report['passed']=not report['unexecuted'] and len(report['checks'])==len(requested)+1 and all(c['passed'] for c in report['checks'].values())
        return 0 if report['passed'] else 1
    except Exception:
        report.update(passed=False,fatal=traceback.format_exc());return 1
    finally:
        artifacts={p.relative_to(out).as_posix():dict(sha256=file_hash(p),bytes=p.stat().st_size)
                   for p in sorted(out.rglob('*')) if p.is_file() and p.name!='report.json'}
        write_new(out/'durable-files.json',artifacts)
        report['durable_manifest_sha256']=file_hash(out/'durable-files.json')
        write_new(out/'report.json',report)

if __name__=='__main__':sys.exit(main())
