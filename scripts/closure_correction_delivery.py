"""Explicit trace-completeness correction; preserve the original closure capture."""
import argparse
import json
from pathlib import Path
import closure_delivery as base

ROOT=base.ROOT
PROTOCOL='docs/mainline/24-closure-correction-01-protocol.json'
original_pins=base.pins
original_check=base.check_case

def pins(protocol,revision):
    identities=original_pins(protocol,revision)
    identities['tools'].update(base.hashes(revision,protocol['additional_tools']))
    identities['inputs'].update(base.hashes(revision,protocol['preserved_inputs']))
    return identities

def check_case(folder,case):
    check=original_check(folder,case)
    if check['assessment_status']=='REJECTED':return check
    result=base.read(folder/case['id']/'result.json');question=result['questions'][0]
    inputs=base.read(ROOT/case['input']);records={r['id']:r for r in inputs['frame']['evidence']['records']}
    evaluated=question['checks']+[c for review in question['review_evaluations'] for role in ('review_checks','current_checks') for c in review[role]]
    blocking={identifier for c in evaluated for identifier in c['insufficient_record_ids']}
    considered=blocking|set(question['supporting_record_ids'])|{identifier for c in evaluated for identifier in c['supporting_record_ids']}
    base.require(blocking==set(question['blocking_record_ids']),'Blocking decision identities omitted')
    trace={e['record_id']:e for e in question['trace'] if e['event'] in {'VERIFICATION_RECORD_AVAILABLE','VERIFICATION_RECORD_BLOCKED'}}
    base.require(set(trace)==considered,'Decision evidence trace is incomplete')
    for identifier in considered:
        event=trace[identifier];row=records[identifier]
        base.require(event['event']==('VERIFICATION_RECORD_BLOCKED' if identifier in blocking else 'VERIFICATION_RECORD_AVAILABLE'),'Decision evidence disposition differs')
        base.require(all(event[k]==row[k] for k in ('observed_at_s','arrived_at_s','valid_until_s','provenance')),'Blocking/considered evidence timing or origin differs')
    fa={identifier for identifier in question['disposition_record_ids'] if records[identifier]['value']=='FALSE_ALARM'}
    base.require({e['review_record_id'] for e in question['review_evaluations']}==fa,'False-alarm review evaluation omitted')
    for review in question['review_evaluations']:
        base.require(type(review['passed']) is bool and bool(review['reason']),'Review decision reason missing')
    if case['id'] in {'false-alarm-adverse','cross-source-conflict'}:
        base.require('fixed-adverse-5' in blocking,'Frozen decisive contradiction omitted')
        event=trace['fixed-adverse-5']
        base.require(event['observed_at_s']==5 and event['arrived_at_s']==5.5,'Frozen decisive contradiction times differ')
    if case['id']=='false-alarm-adverse':
        review=question['review_evaluations'][0]
        base.require(not review['passed'] and bool(review['current_checks']),'Failed review criteria discarded')
    check.update(blocking_record_ids=sorted(blocking),considered_trace_records=len(considered),review_evaluations=len(fa))
    return check

base.PROTOCOL=PROTOCOL
base.pins=pins
base.check_case=check_case

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--delivery');args=parser.parse_args()
    folder=(ROOT/args.capture).resolve();base.require(folder.parent==ROOT/base.PACKAGE,'Use unique declared correction directory')
    protocol=base.read(ROOT/PROTOCOL)
    print(json.dumps(base.capture(folder,protocol) if args.mode=='capture' else base.verify(folder,protocol,args.delivery),ensure_ascii=False))
