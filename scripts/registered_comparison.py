"""Inspect frozen comparison inputs without loading the simulator or a policy."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

METHODS = ('one_observation_lookahead', 'evidence_consistent_contingent')
POLICY_FIELD = 'dispatch_program.policy_program.policy'
FACILITY = 'zhengzhou-inspired-synthetic-full-facility-reserve-v6'
DOMAINS = {'power', 'backup', 'facility_cooling', 'equipment_environment',
           'it_service', 'control_monitoring', 'space_access', 'people_tools_work'}
RELATIONS = {'physical', 'functional', 'control_information', 'access'}


def read(path):
    def unique(pairs):
        values = {}
        for key,value in pairs:
            if key in values:
                raise ValueError(f'Duplicate JSON key: {key}')
            values[key] = value
        return values

    return json.loads(path.read_bytes(),object_pairs_hook=unique)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def audit_pair(paths):
    shared = []
    for path,name in zip(paths,METHODS,strict=True):
        document = read(path)
        dispatch = document['dispatch_program']
        policy = dispatch['policy_program']
        model = document['model']
        if (dispatch['schema'] != 'aegisdc-policy-run-program-v3'
                or policy['schema'] != 'aegisdc-dispatch-policy-program-v4'
                or policy.pop('policy') != name):
            raise ValueError(f'Expected paired V4 method: {name}')
        if (model['id'] != FACILITY or len(model['domains']) != len(DOMAINS)
                or {row['id'] for row in model['domains']} != DOMAINS or set(model['graphs']) != RELATIONS):
            raise ValueError('The pair must use the complete eight-domain V6 facility')
        shared.append(canonical(document))
    if shared[0] != shared[1]:
        raise ValueError('Another pair input differs')
    return dict(status='PASS_EXACT_INPUT_PARITY',allowed_difference=POLICY_FIELD,
        shared_input_sha256=sha256(shared[0]).hexdigest(),facility_calls=0,selector_calls=0,
        registered_research_trials=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest='command',required=True)
    pair = command.add_parser('audit-pair', help='Check the exact primary paired input boundary')
    pair.add_argument('baseline',type=Path)
    pair.add_argument('candidate',type=Path)
    args = parser.parse_args()
    try:
        receipt = audit_pair((args.baseline,args.candidate))
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(2,f'{error}\n')
    print(json.dumps(receipt,allow_nan=False))


if __name__ == '__main__':
    main()
