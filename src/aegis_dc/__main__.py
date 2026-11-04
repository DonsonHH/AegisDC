import argparse
import json
from pathlib import Path
from patrol_rsi.contracts import strict_json
from .facility import load_model,describe,candidate_service_exposure
from .risk import recommend
from .scenario import load_scenario,describe_scenario
from .plant import simulate_scenario,describe_run,save_run

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
    demo=sub.add_parser('risk-demo');demo.add_argument('--case',type=Path,default=ROOT/'configs/risk-method-demo.json');demo.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='status':
            result=strict_json((ROOT/'docs/current-research.json').read_text(encoding='utf-8'))
            result.update(implementation='structural validation and synthetic decision-value prototype',field_calibration='PENDING',postmeeting_model_calls=0,postmeeting_training=0)
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
            trajectory=simulate_scenario(load_scenario(args.model),duration_s=args.duration,step_s=args.step,**inputs)
            result=save_run(trajectory,args.output) if args.output else describe_run(trajectory)
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


if __name__=='__main__':main()
