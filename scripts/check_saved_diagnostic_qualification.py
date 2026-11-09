"""Verify original six diagnostic runs; never invoke a plant, policy or evaluator."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import traceback


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and socket.gethostname().split('.')[0]!='mu01'
    root=args.manifest.resolve().parent;manifest=json.loads(args.manifest.read_bytes());manifest_sha=sha(args.manifest)
    args.output.mkdir(exist_ok=False)
    save(args.output/'attempt.json',dict(classification='SAVED_ONLY_ENGINEERING_CORRECTION_NOT_NEW_NATIVE_RUN',
        source_commit=manifest['source_commit'],manifest_sha256=manifest_sha,slurm_job_id=os.environ['SLURM_JOB_ID'],
        started_at_utc=datetime.now(timezone.utc).isoformat(),new_facility_calls=0,new_model_calls=0,new_research_trials=0))
    terminal=dict(status='FAILED',source_commit=manifest['source_commit'],new_facility_calls=0,new_model_calls=0,new_research_trials=0)
    try:
        def guard():
            assert sha(args.manifest)==manifest_sha
            assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==manifest['source_commit']
            for name,record in manifest['files'].items():
                path=root/name;assert path.resolve().is_relative_to(root) and not path.is_symlink()
                assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
        guard()
        protocol=json.loads((root/'docs/mainline/39c-qualification-saved-correction-06.json').read_bytes())
        original=Path(protocol['original_remote_root'])
        assert original.as_posix()=='/share/home/renly/renly-patrol-rsi/mainline/39c-development/07-state-diagnostic-qualification'
        assert sha(original/'manifest.json')==protocol['original_manifest_sha256']
        assert sha(original/'results/terminal.json')==protocol['original_terminal_sha256']
        prior=json.loads((original/'results/terminal.json').read_bytes())
        assert prior['status']=='FAILED' and prior['tests_run']==5 and prior['failures']==1 and prior['errors']==0
        assert prior['new_facility_calls']==6 and prior['returned_decisions']==18 and prior['source_guard']=='PASS_BEFORE_AND_AFTER'
        def original_guard():
            for name,record in prior['output_files'].items():
                path=original/'results'/name
                assert path.resolve().is_relative_to(original/'results') and not path.is_symlink()
                assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
            assert sha(original/'results/terminal.json')==protocol['original_terminal_sha256']
        original_guard();results={};projections={}
        for identifier in protocol['case_ids']:
            result=json.loads((original/'results'/identifier/'business-result.json').read_bytes())
            projections[identifier]=json.loads((original/'results'/identifier/'public-projection.json').read_bytes())
            native=json.loads((original/'results'/identifier/'actual-run/run.json').read_bytes())
            assert result['execution_code_identity']['git_commit']==protocol['original_execution_source']
            assert result['execution_code_identity']['implementation_has_changes'] is False
            assert native['code_identity']==result['execution_code_identity']
            results[identifier]=result
        fault=results['no-human-fault'];normal=results['no-human-normal']
        assert projections['no-human-fault']==projections['no-human-normal']
        descriptor=json.loads((root/'tests/fixtures/39c-network-state-diagnostic.json').read_bytes())
        assert fault['reference']==descriptor['business_program']['reference']
        assert fault['counts']['eligible_fault_matured']==1 and fault['counts']['missed_fault_confirmation']==1
        assert normal['events'][0]['initial_truth']=='NORMAL' and normal['counts']['normal_matured']==1
        assert results['normal']['counts']['false_positive_state_events']==0
        assert results['normal']['rates']['false_positive_state_events']['value']==0
        assert results['normal']['rates']['missed_confirmation']['value'] is None
        uncertain=results['uncertain']
        assert [row['condition_assessment']['conditions'][0]['status'] for row in projections['uncertain']]==['UNKNOWN']*3
        assert uncertain['counts']['eligible_fault_matured']==1 and uncertain['counts']['missed_fault_confirmation']==1
        unknown=results['unmodeled-proxy'];assert unknown['events'][0]['initial_truth']=='UNKNOWN'
        assert unknown['events'][0]['initial_private_value'] is None
        assert all(row['value'] is None for row in unknown['rates'].values())
        wrong=results['wrong-demand-model'];event=wrong['events'][0]
        inputs=json.loads((original/'results/wrong-demand-model/frozen-call-input.json').read_bytes())
        parameters={row['id']:row['value'] for row in inputs['model']['parameters']}
        assert parameters['network_service_capacity']==.75 and parameters['service_demand']==.5
        assert event['initial_truth']=='NORMAL' and event['initial_private_value']==.5
        records=projections['wrong-demand-model'][1]['frame']['evidence']['records']
        measured=next(row for row in records if row['id']=='it-capacity-before')
        assert measured['value']==.5 and measured['quality']['error_bound']==0
        assert measured['observed_at_s']==1.25 and measured['arrived_at_s']==1.75
        assert [row['condition_assessment']['conditions'][0]['status'] for row in projections['wrong-demand-model']]==['UNKNOWN','ABNORMAL','ABNORMAL']
        assert wrong['counts']['events_total']==1 and wrong['counts']['normal_matured']==1 and wrong['counts']['false_positive_state_events']==1
        assert wrong['rates']['false_positive_state_events']['denominator']==1 and wrong['rates']['false_positive_state_events']['value']==1
        rows=[]
        for identifier,result in results.items():
            event=result['events'][0];counts=result['counts']
            rows.append(dict(case_id=identifier,initial_truth=event['initial_truth'],initial_private_value=event['initial_private_value'],
                last_public_status=projections[identifier][-1]['condition_assessment']['conditions'][0]['status'],
                fault_denominator=counts['eligible_fault_matured'],missed=counts['missed_fault_confirmation'],
                normal_denominator=counts['normal_matured'],false_positive=counts['false_positive_state_events']))
        with (args.output/'original-six-endpoints.csv').open('x',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        original_guard();guard()
        terminal.update(status='SAVED_ORIGINALS_AND_CORRECTED_LITERAL_PASSED',original_native_runs=6,
            original_status='FAILED',original_job='133274',original_runtime_source=protocol['original_execution_source'],
            original_files_verified=len(prior['output_files']),expected_actual_capacity=.5,
            original_assertion_wrong_value=.75,public_scalar_reading=.5,normal_event_false_positive=1,
            prevention_effect='NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL',source_guard='PASS_BEFORE_AND_AFTER')
    except BaseException as error:
        terminal.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc());raise
    finally:
        terminal['output_files']={p.relative_to(args.output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in args.output.rglob('*') if p.is_file()}
        terminal['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(args.output/'terminal.json',terminal)
    print(json.dumps(terminal))


if __name__=='__main__':main()
