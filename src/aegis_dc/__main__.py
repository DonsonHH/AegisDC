import argparse
import json
from pathlib import Path
from patrol_rsi.contracts import strict_json
from .facility import load_model,describe,candidate_service_exposure
from .risk import recommend

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description='AegisDC facility/risk research foundation; no model training')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    structure=sub.add_parser('foundation');structure.add_argument('--model',type=Path,default=ROOT/'configs/facility-structure-v0.1.json');structure.add_argument('--asset',default='main_switchgear')
    demo=sub.add_parser('risk-demo');demo.add_argument('--case',type=Path,default=ROOT/'configs/risk-method-demo.json');demo.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='status':
            result=strict_json((ROOT/'docs/current-research.json').read_text(encoding='utf-8'))
            result.update(implementation='structural validation and synthetic decision-value prototype',field_calibration='PENDING',postmeeting_model_calls=0,postmeeting_training=0)
        elif args.command=='foundation':
            model=load_model(args.model);result=describe(model);result['screened_asset']=args.asset
            result['candidate_exposed_services']=candidate_service_exposure(model,args.asset)
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
    except (ValueError,KeyError) as error:parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
