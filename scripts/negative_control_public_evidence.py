"""Check the public ticket 28 record boundary without any facility execution."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from inspection_delivery import ROOT, digest, durable, git, hashes, read, require, unchanged, write

PROTOCOL = 'docs/mainline/28-public-evidence-preflight-v1.json'


def note(path, row):
    with path.open('ab') as f:
        f.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode())
        f.flush()
        os.fsync(f.fileno())


def registry(program):
    ledger=deepcopy(program['evidence_ledger'])
    extras=(program['sensor_program']['profile']['ledger'],
            program['inspection_program']['profile']['nonfixed_profile']['registry'])
    for extra in extras:
        for field in ('sources','observables'):
            rows={r['id']:r for r in ledger[field]}
            for row in extra[field]:
                require(row['id'] not in rows or rows[row['id']]==row, 'Public evidence registry conflicts')
                if row['id'] not in rows:
                    ledger[field].append(deepcopy(row))
                    rows[row['id']]=row
    return ledger


def capture(source):
    protocol=read(ROOT/PROTOCOL)
    require(git('rev-parse','HEAD').decode().strip()==source and not git('status','--porcelain'),
            'Use a clean exact committed public evidence fixture source')
    folder=ROOT/protocol['output']
    require(not folder.exists(),'Public evidence fixture output already exists')
    runtime=[p for p in git('ls-tree','-rz','--name-only',source,'src').decode().strip('\0').split('\0')
             if p.endswith('.py') and '__pycache__' not in p]
    roles=dict(runtime=runtime,inputs=[PROTOCOL,protocol['input']],tools=protocol['tools'])
    identities={role:hashes(source,paths) for role,paths in roles.items()}
    require(unchanged(source,identities),'Public evidence fixture source bytes changed')
    folder.mkdir(parents=True)
    events=folder/'attempts.jsonl'
    counters=dict(public_frames=0,public_choice_calls=0,standalone_closure_calls=0,physical_calls=0)
    receipt=dict(status='FAIL',source=source,pins=identities,counters=counters,
        source_guard=False,registered_research_trials=0,error=None)
    write(folder/'attempt.json',dict(status='STARTED',source=source,pins=identities,
        executable_sha256=digest(Path(sys.executable).read_bytes()),python=sys.version,
        utc=datetime.now(timezone.utc).isoformat(),scope=protocol['classification'],
        durable_artifacts=protocol['durable_outputs']))
    def invoke(operation,key,call):
        note(events,dict(operation=operation,case=key,status='STARTED'))
        counters[operation]+=1
        try:
            result=call()
            write(folder/(key+'.json'),result)
        except Exception as error:
            note(events,dict(operation=operation,case=key,status='FAILED',
                              error_type=type(error).__name__,message=str(error)))
            raise
        note(events,dict(operation=operation,case=key,status='COMPLETED'))
        return result
    try:
        sys.path.insert(0,str(ROOT/'src'))
        from aegis_dc.decision_view import DecisionGateway
        from aegis_dc.dispatch_policy import choose_work
        from aegis_dc.verified_closure import assess_closure
        cases=read(ROOT/protocol['input'])['cases']
        public={}
        for case_name in ('normal','false_report'):
            program=cases[case_name]['replay_inputs']['dispatch_program']
            plan=dict(schema='aegisdc-public-preparation-plan-v1',id='ticket28-evidence-preflight',
                basis='synthetic_assumption',time_unit='s',
                decision_times_s=protocol['frame_times_s'][case_name],requests=program['preparation_requests'])
            gateway=DecisionGateway(program['nominal_knowledge'],registry(program),plan)
            public[case_name]={}
            for epoch in plan['decision_times_s']:
                frame=invoke('public_frames',f'frame-{case_name}-{epoch}',gateway.next_frame)
                ids={r['id'] for r in frame['evidence']['records']}
                require(('delayed-lake-work-order' in ids)==(case_name=='false_report' and epoch>=3)
                        and ('cooling-review-record-28' in ids)==(case_name=='false_report' and epoch>=7),
                        'Report or review is visible at the wrong time')
                require(all(row['observed_at_s']<=row['arrived_at_s']<=epoch for row in frame['evidence']['records']),
                        'Future record entered public input fixture')
                public[case_name][epoch]=frame
                if epoch in (1,3):
                    verdict=invoke('public_choice_calls',f'choice-{case_name}-{epoch}',lambda:choose_work(
                        frame,program['policy_program'],dict(issued=[],work_feedback=[]),
                        intervention_declaration=program['intervention_program'],closure_program=program['closure_program']))
                    expected='first-inspection' if (case_name,epoch)==('false_report',3) else None
                    require(verdict['chosen_candidate_id']==expected and not verdict['execution_permission'],
                            'Public report-only behavior differs')
                if epoch==7:
                    review=invoke('standalone_closure_calls','closure-false-report-no-measurements',
                                  lambda:assess_closure(frame,program['closure_program']))
                    question,=review['questions']
                    require(question['status']=='OPEN_UNCONFIRMED' and not question['question_closed']
                            and not question['risk_closed'], 'Review without real supporting samples closed the question')
        require(public['normal'][1]==public['false_report'][1],'A future record changed the early public view')
        observed,=[row for row in public['false_report'][3]['evidence']['records'] if row['id']=='delayed-lake-work-order']
        require(observed['quality']['note']==protocol['neutral_note']
                and observed['provenance']['origin_id']=='operator-lake-suspicion-28','Operator report reveals evaluator truth')
        require(counters==protocol['expected_counters'] and durable(folder)==set(protocol['durable_outputs']),
                'Fixture durable set or call budget differs')
        receipt['status']='PASS_PUBLIC_EVIDENCE_ONLY'
    except Exception as error:
        receipt['error']=dict(type=type(error).__name__,message=str(error))
        note(events,dict(scope='PUBLIC_EVIDENCE_FIXTURE',status='FAILED',**receipt['error']))
    finally:
        try:
            receipt['source_guard']=unchanged(source,identities)
        except (OSError,subprocess.SubprocessError) as error:
            receipt.update(source_guard=False,source_guard_error=str(error))
        if not receipt['source_guard']:
            receipt['status']='FAIL'
        receipt['artifacts']={name:digest((folder/name).read_bytes()) for name in sorted(durable(folder))}
        write(folder/'receipt.json',receipt)
    require(receipt['status']=='PASS_PUBLIC_EVIDENCE_ONLY','Public evidence fixture failed; preserve original and stop')
    return dict(status=receipt['status'],source=source,counters=counters,registered_research_trials=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    args=parser.parse_args()
    print(json.dumps(capture(args.source),ensure_ascii=False))
