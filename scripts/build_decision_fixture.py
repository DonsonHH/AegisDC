"""Author public V6 design/intention inputs, independently of private worlds."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.decision_view import DecisionGateway, validate_nominal
from aegis_dc.evidence_ledger import validate_ledger


def build():
    # Only this independent canonical public profile is read. No world override,
    # parameter value, runtime/current state, run, seed or event input is used.
    public = json.loads((ROOT / 'configs/full-facility-mainline-reserve-v6.json').read_text(encoding='utf-8'))
    nominal = dict(schema='aegisdc-public-nominal-v1', id='V6-canonical-public-nominal-v1',
        facility_id=public['id'], basis='synthetic_assumption',
        source_note='Nominal identities, relation directions and personnel capabilities from the canonical public V6 profile; no current state or parameter values.',
        domain_ids=[row['id'] for row in public['domains']],
        entities=[dict(id=row['id'], kind=row['kind'], domain=row['domain'],
            nominal_location_id=row['location_id'], qualification_ids=list(row.get('qualification_ids', [])),
            tool_ids=list(row.get('tool_ids', []))) for row in public['entities']],
        qualification_ids=list(public['qualifications']), work_interfaces=[], graphs={},
        reported_constraints=[dict(id='reported-it-entry-restriction', source_id='declared-it-access-report',
            target_id='loc_it', observable_id='it-entry-permitted-reported', location_id='loc_it', blocking_value=False)])
    for domain in public['domains']:
        nominal['work_interfaces'] += [dict(id=row['id'], domain_id=domain['id'],
            target_ids=list(row['target_ids']), qualification_id=row['qualification_id'],
            tool_ids=list(row['tool_ids'])) for row in domain['work_interfaces']]
    for kind, rows in public['graphs'].items():
        nominal['graphs'][kind] = [dict(id=row['id'], **{'from': row['from'], 'to': row['to']},
            kind=row['kind'], bidirectional=row.get('bidirectional', False),
            requires_qualification_ids=list(row.get('requires_qualification_ids', []))) for row in rows]
    nominal = validate_nominal(nominal)
    plan = dict(schema='aegisdc-public-preparation-plan-v1', id='V6-public-preparation-tracer-v1',
        basis='synthetic_assumption', time_unit='s', decision_times_s=[0, 2, 4, math.nextafter(6, -math.inf), 6, 7],
        requests=[
            dict(id='intent-it-check', worker_id='worker_it', work_interface_id='inspect_it_service', target_id='compute'),
            dict(id='intent-filter-check', worker_id='worker_cooling', work_interface_id='inspect_facility_cooling', target_id='filter'),
            dict(id='intent-unqualified-it-check', worker_id='worker_electrical', work_interface_id='inspect_it_service', target_id='compute')])
    common = json.loads((ROOT / 'configs/full-facility-evidence-v1.json').read_text(encoding='utf-8'))
    old = {row['id']: row for row in common['records']}
    common['id'] = 'V6-public-decision-evidence-v1'
    common['records'] = [deepcopy(old[name]) for name in ('design-rating', 'maintenance-history')]
    human = deepcopy(old['human-false'])
    human.update(id='operator-no-vibration-t0', observed_at_s=0, arrived_at_s=1, valid_until_s=10)
    human['provenance']['origin_id'] = 'carried-operator-filter-t0'
    missing = deepcopy(old['missing-flow'])
    missing.update(id='unavailable-flow-t2', observed_at_s=2, arrived_at_s=2, valid_until_s=10)
    missing['provenance']['origin_id'] = 'carried-missing-flow-t2'
    offset = deepcopy(old['handheld-negative'])
    offset.update(id='uncalibrated-offset-t3', value=0, observed_at_s=3, arrived_at_s=3, valid_until_s=10)
    offset['quality'] = dict(status='unknown', error_bound=None,
        note='External hand-authored uncalibrated example; no completed worker measurement is claimed.')
    offset['provenance']['origin_id'] = 'carried-offset-t3'
    common['records'] += [human, missing, offset]
    common['observables'].append(dict(id='it-entry-permitted-reported', quantity='binary', value_type='boolean', unit='1'))
    common['sources'].append(dict(id='declared-it-access-report', kind='control_record', basis='synthetic_assumption',
        target_ids=['loc_it'], observable_ids=['it-entry-permitted-reported'], dependency_group=None,
        source_note='Declared sparse remote permit-status channel; values here are hand-authored engineering inputs, not generated from a private run.'))
    common = validate_ledger(common)
    streams = {}
    for name, value in [('reported-open-ledger.json', True), ('reported-closed-ledger.json', False)]:
        document = deepcopy(common)
        document['records'].append(dict(id='it-entry-report-t4', source_id='declared-it-access-report',
            target_id='loc_it', observable_id='it-entry-permitted-reported', unit='1', value=value,
            observed_at_s=4, arrived_at_s=6, valid_until_s=8,
            quality=dict(status='reported', error_bound=None, note='Unverified reported permit status, not an actual-state certificate.'),
            provenance=dict(origin_id='carried-it-entry-t4', copied_from_record_id=None)))
        streams[name] = validate_ledger(document)
    result = {'public-nominal.json': nominal, 'public-plan.json': plan, 'common-ledger.json': common, **streams}
    for document in (common, *streams.values()):
        DecisionGateway(nominal, document, plan)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    documents = build()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, document in documents.items():
        with (args.output / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(status='ENGINEERING_FIXTURE_WRITTEN', files=list(documents))))


if __name__ == '__main__':
    main()
