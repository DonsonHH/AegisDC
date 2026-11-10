import argparse
import json
from pathlib import Path
from patrol_rsi.contracts import strict_json
from .facility import load_model,describe,candidate_service_exposure
from .risk import recommend
from .scenario import load_scenario,describe_scenario
from .plant import simulate_scenario,describe_run,save_run
from .replay import record_files,replay_attempt
from .evidence_ledger import load_ledger

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description='AegisDC facility/risk research foundation; no model training')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    structure=sub.add_parser('foundation');structure.add_argument('--model',type=Path,default=ROOT/'configs/facility-structure-v0.1.json');structure.add_argument('--asset',default='main_switchgear')
    scenario=sub.add_parser('scenario');scenario.add_argument('--model',type=Path,default=ROOT/'configs/full-facility-mainline-v1.json')
    run=sub.add_parser('simulate',help='Run the private complete-facility engineering fixture; no policy trial')
    run.add_argument('--model',type=Path,default=ROOT/'configs/full-facility-mainline-v2.json')
    run.add_argument('--output',type=Path)
    run.add_argument('--duration',type=float)
    run.add_argument('--step',type=float)
    run.add_argument('--inputs',type=Path,help='Declared engineering work requests and timed boundary events')
    run.add_argument('--work-program',type=Path,help='Versioned current-frame crew submissions; private evaluator input')
    run.add_argument('--inspection-program',type=Path,help='Actual work-bound inspection profile and private observation realization')
    run.add_argument('--intervention-program',type=Path,help='Named authorized completion-gated research actions; private evaluator input')
    run.add_argument('--dispatch-program',type=Path,help='Declared same-facility evidence-only policy and private observation inputs; engineering only')
    record=sub.add_parser('record',help='Freeze and execute one private engineering attempt, including failures')
    record.add_argument('--model',type=Path,default=ROOT/'configs/full-facility-mainline-reserve-v6.json')
    record.add_argument('--inputs',type=Path,required=True)
    record.add_argument('--output',type=Path,required=True)
    record.add_argument('--duration',type=float)
    record.add_argument('--step',type=float)
    record.add_argument('--retry-of',type=Path)
    record.add_argument('--retry-reason')
    replay=sub.add_parser('replay',help='Re-execute frozen private inputs with exactly matching runtime bytes/interpreter')
    replay.add_argument('--attempt',type=Path,required=True)
    replay.add_argument('--output',type=Path,required=True)
    replay.add_argument('--commands',type=Path,help='Explicit engineering command list for a paired exogenous re-execution')
    evidence=sub.add_parser('evidence',help='Snapshot only declared static knowledge and evidence available at an explicit SI second')
    evidence.add_argument('--ledger',type=Path,required=True)
    evidence.add_argument('--as-of',type=float,required=True)
    evidence.add_argument('--output',type=Path,help='New directory for the public snapshot only')
    demo=sub.add_parser('risk-demo');demo.add_argument('--case',type=Path,default=ROOT/'configs/risk-method-demo.json');demo.add_argument('--output',type=Path)
    baseline=sub.add_parser('risk-baseline',help='Review eight-domain risk/value coverage and time alignment;no dispatch')
    baseline.add_argument('--manifest',type=Path,default=ROOT/'configs/facility-risk-baseline-v1.json')
    baseline.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='status':
            result=strict_json((ROOT/'docs/current-research.json').read_text(encoding='utf-8'))
            result.update(implementation=result.get('implementation','structural validation and synthetic decision-value prototype'),field_calibration='PENDING',postmeeting_model_calls=0,postmeeting_training=0)
            if 'progress' in result:
                progress=strict_json((ROOT/result['progress']).read_text(encoding='utf-8'))
                result['mainline_progress']={key:progress[key] for key in ('status','goal','current_ticket','current_milestone','agent_stage','rsi_gain','research_trials')}
                result['postmeeting_model_calls_scope']='agent/LLM research calls; engineering physics/property calculations are separate'
        elif args.command=='risk-baseline':
            from .risk_baseline import review_baseline
            result=review_baseline(args.manifest)
            if args.output:
                args.output.mkdir(parents=True,exist_ok=False)
                with (args.output/'result.json').open('x',encoding='utf-8',newline='\n') as stream:
                    stream.write(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        elif args.command=='foundation':
            model=load_model(args.model);result=describe(model);result['screened_asset']=args.asset
            result['candidate_exposed_services']=candidate_service_exposure(model,args.asset)
        elif args.command=='scenario':
            try:result=describe_scenario(load_scenario(args.model))
            except OSError as error:parser.error(str(error))
        elif args.command=='simulate':
            if args.output and args.output.exists():
                raise ValueError('Output directory already exists; use a new engineering run directory')
            inputs={'work_requests':[],'boundary_events':[]}
            if args.inputs:
                inputs=strict_json(args.inputs.read_text(encoding='utf-8'))
                if not isinstance(inputs,dict) or set(inputs)!={'schema','work_requests','boundary_events'} or inputs['schema']!='aegisdc-engineering-inputs-v1':
                    raise ValueError('Use the declared engineering inputs contract')
                inputs={name:inputs[name] for name in ('work_requests','boundary_events')}
            if args.work_program:
                inputs['work_program']=strict_json(args.work_program.read_text(encoding='utf-8'))
            if args.inspection_program:
                inputs['inspection_program']=strict_json(args.inspection_program.read_text(encoding='utf-8'))
            if args.intervention_program:
                inputs['intervention_program']=strict_json(args.intervention_program.read_text(encoding='utf-8'))
            if args.dispatch_program:
                inputs['dispatch_program']=strict_json(args.dispatch_program.read_text(encoding='utf-8'))
            trajectory=simulate_scenario(load_scenario(args.model),duration_s=args.duration,step_s=args.step,**inputs)
            result=save_run(trajectory,args.output) if args.output else describe_run(trajectory)
        elif args.command=='record':
            result=record_files(args.model,args.inputs,args.output,duration_s=args.duration,step_s=args.step,
                                retry_of=args.retry_of,retry_reason=args.retry_reason)
        elif args.command=='replay':
            result=replay_attempt(args.attempt,args.output,action_commands=args.commands)
        elif args.command=='evidence':
            if args.output and args.output.exists():
                raise ValueError('Output directory already exists; use a new evidence directory')
            result=load_ledger(args.ledger).snapshot(args.as_of)
            if args.output:
                args.output.mkdir(parents=True,exist_ok=False)
                with (args.output/'snapshot.json').open('x',encoding='utf-8',newline='\n') as stream:
                    stream.write(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        else:
            case=strict_json(args.case.read_text(encoding='utf-8'))
            if set(case)!={'schema','basis','facility_model','as_of_hour','questions','evidence'} or case['schema']!='aegisdc-risk-demo-v1' or case['basis']!='synthetic_assumption':
                raise ValueError('Use an explicitly synthetic example and the closed evidence contract')
            model=load_model(ROOT/case['facility_model'])
            asset_ids={asset['id'] for asset in model['assets']}
            if any(q['asset_id'] not in asset_ids for q in case['questions']):raise ValueError('Risk question has an unknown facility asset')
            result=recommend(case['questions'],case['evidence'],case['as_of_hour'])
            result.update(basis=case['basis'],research_gain_claim='NOT_ESTABLISHED')
            result['candidate_service_exposure']={q['id']:candidate_service_exposure(model,q['asset_id']) for q in case['questions']}
            if args.output:
                args.output.mkdir(parents=True,exist_ok=False)
                (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    except (ValueError,KeyError,OSError) as error:parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    if args.command in {'record','replay'} and result['status']!='COMPLETED':
        raise SystemExit(1)


if __name__=='__main__':main()
