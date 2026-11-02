"""Independently check report extracts against existing full local records."""
from __future__ import annotations
from collections import Counter, defaultdict
import ast
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def main():
    frozen_count=0
    for index,folder in [('evidence/event-validation/final/local-artifacts.json','runs/event-validation-amended-20261102'),
                         ('evidence/response-defer/local-artifacts.json','runs/response-defer-search-20261102')]:
        files=load(ROOT/index)
        for name,identity in files.items():assert digest(ROOT/folder/name)==identity['sha256'],name
        frozen_count+=len(files)
    engineering=load(ROOT/'paper/source-data/engineering-snapshot-500.json')
    full=load(ROOT/engineering['source_record']);assert digest(ROOT/engineering['source_record'])==engineering['source_sha256']
    frame=next(f for f in full['methods']['tour']['public_frames'] if f['time_s']==500)
    i=full['offline_only']['time_s'].index(500)
    assert engineering['public_thermal_risk']==frame['thermal_risk']
    assert engineering['public_estimated_temperature_c']==frame['estimated_temperature_c']
    assert engineering['remote_temperature_c']==frame['remote_temperature_c']
    assert engineering['offline_temperature_c']==full['offline_only']['temperature_c'][i]
    fifo=load(ROOT/'paper/source-data/fifo-decision-p01-470.json')
    assert digest(ROOT/fifo['source_record'])==fifo['source_sha256']
    with gzip.open(ROOT/fifo['source_record'],'rt',encoding='utf-8') as stream:full=json.load(stream)
    events={e['event_id']:e for e in full['public_events']}
    point=next(d for d in full['decisions'] if d['time_s']==470 and d['agent']==0)
    assert point['routine_head']==fifo['routine_head']==0 and point['selected']==fifo['selected']==10
    for row in fifo['queue']:
        original=next(c for c in point['candidates'] if c['task']==row['task'])
        assert row['risk_at_decision']==original['public_risk']
        assert row['visible_s']==events[original['event_id']]['visible_s']
        assert row['certificate_ok']==original['certificate']['ok'] and row['budget_allowed']==original['budget_allowed']
    for row in fifo['checks']:
        point=next(d for d in full['decisions'] if d['time_s']==row['decision_s'] and d['agent']==0)
        cert=next(c for c in point['candidates'] if c['task']==row['selected_task'])['certificate']
        assert row['finish_s']==cert['candidate_finish_s'] and cert['fallback_order'][0]==0
        assert row['projected_return_finish_s']==cert['fallback_completion_s'][0]
        assert row['routine_due_s']==cert['fallback_due_s'][0]
        assert row['minimum_full_cycle_slack_s']==cert['minimum_projected_slack_s']
    for row in fifo['actual_dispatches']:
        dispatch=next(d for d in full['dispatches'] if d['agent']==0 and d['time_s']==row['dispatch_s'])
        measured=next(e for e in full['inspection_events'] if e['agent']==0 and e['time_s']==row['completion_s'])
        assert dispatch['task']==measured['task']==row['task']
        assert measured['extra_event_visit']==row['extra_event_visit'] and measured['alarm']==row['alarm']
    busy=fifo['preceding_busy_action']
    dispatch=next(d for d in full['dispatches'] if d['agent']==0 and d['time_s']==busy['dispatch_s'])
    assert dispatch['task']==busy['task'] and dispatch['certificate']['candidate_finish_s']==busy['completion_s']==470
    roles=defaultdict(set)
    durations=defaultdict(set)
    for event in full['inspection_events']:
        roles[event['kind']].add(event['agent']);durations[event['kind']].add(event['service_s'])
    assert {k:len(v) for k,v in roles.items()}=={k:v['inspectors'] for k,v in fifo['task_contract'].items()}
    module=ast.parse((ROOT/'src/patrol_rsi/aisles.py').read_text(encoding='utf-8'))
    limits=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEADLINES' for t in n.targets))
    for kind,contract in fifo['task_contract'].items():
        assert durations[kind]=={contract['service_s']} and limits[kind]==contract['revisit_limit_s']
    kinds=load(ROOT/'paper/source-data/primary-anomaly-kinds.json');counts=Counter()
    for name,identity in kinds['source_files_sha256'].items():
        record=ROOT/'runs/event-validation-amended-20261102'/name;assert digest(record)==identity
        with gzip.open(record,'rt',encoding='utf-8') as stream:counts.update(a['kind'] for a in json.load(stream)['anomaly_intervals'])
    assert dict(counts)==kinds['counts']=={'thermal':77,'cooling':12}
    # Bind the source checks to the actual delivered HTML and every embedded SVG.
    manifest=load(ROOT/'paper/generated/briefing-manifest.json')
    html=(ROOT/'paper/supervisor-briefing.html').read_text(encoding='utf-8')
    assert manifest['html_sha256']==digest(ROOT/'paper/supervisor-briefing.html')
    for name,identity in manifest['source_sha256'].items():assert digest(ROOT/name)==identity,name
    drawings={}
    for name,identity in manifest['figure_sha256'].items():
        path=ROOT/name;assert digest(path)==identity,name
        source=path.read_text(encoding='utf-8');assert source in html,name
        drawings[path.stem]=ET.fromstring(source)
    data_path=ROOT/'paper/generated/supervisor-report-data.json';data=load(data_path)
    assert digest(data_path)==manifest['data_sha256']
    for name,kind,values in [('public-risk','risk',engineering['public_thermal_risk']),
                             ('offline-temperature','temperature',engineering['offline_temperature_c'])]:
        encoded={int(e.attrib['data-rack']):float(e.attrib['data-value']) for e in drawings[name].iter() if e.attrib.get('data-kind')==kind}
        assert encoded==dict(enumerate(values)),name
    rows=load(ROOT/'evidence/event-validation/final/rows.json')
    for method in ['tour','fifo','shuffled']:
        selected=[r for r in rows if r['group']=='coupled' and r['method']==method]
        assert data['main'][method]['confirmed']==sum(r['confirmed_segments'] for r in selected)
        for field,raw in [('mean_travel_m','travel_m'),('mean_service_s','service_s'),
                          ('mean_completed_inspections','completed_inspections'),
                          ('mean_consequence_weighted_censored_delay_s','consequence_weighted_censored_delay_s')]:
            assert math.isclose(data['main_costs'][method][field],mean(r[raw] for r in selected),rel_tol=1e-12),field
    protocol=load(ROOT/'evidence/event-validation/final/protocol.json')
    assert data['decision_thresholds']==protocol['decision_thresholds']
    summary=load(ROOT/'evidence/event-validation/final/summary.json')
    assert data['primary_comparisons']==summary['primary_comparisons']['fifo_minus_tour']
    proposals=load(ROOT/'evidence/response-defer/proposals.json');rules={}
    for proposal in proposals:
        rules.setdefault(proposal['rule_sha256'],data['main']['fifo']['confirmed']+sum(p['net'] for p in proposal['paired']))
    encoded={e.attrib['data-rule-sha']:int(e.attrib['data-confirmed']) for e in drawings['registered-rules'].iter() if 'data-rule-sha' in e.attrib}
    assert encoded==rules and len(rules)==9
    expected_expressions=['4R−1','A−0.75','R+A−4E+S−0.1','4R+A−E+4S−0.25',
                          '4R−0.75','A−0.125','4R−0.1','4R+A−E+S−0.1','2R+A−E+2S−0.25']
    expressions=[e.attrib['data-rule-expression'] for e in drawings['registered-rules'].iter() if 'data-rule-expression' in e.attrib]
    assert expressions==expected_expressions
    methods=load(ROOT/'paper/source-data/report-method-evidence.json')
    diagnosis=load(ROOT/'paper/source-data/report-rule-diagnosis.json')
    for identity in methods['sources']:assert digest(ROOT/identity['path'])==identity['sha256']
    for name,identity in diagnosis['source_files'].items():assert digest(ROOT/name)==identity['sha256'],name
    primary_specs={r['id']:r['spec'] for r in protocol['cases'] if r['group']=='coupled'}
    assert data['fault_cases']==methods['primary_processes']['cases'] and len(data['fault_cases'])==12
    for case in data['fault_cases']:
        spec=primary_specs[case['id']]
        assert case['seed']==spec['seed'] and case['scenario']==spec['scenario']=='aux_feeder_loss+cdu_fouling'
        assert case['fault_anchor_rack_index']==spec['fault_rack'] and case['fault_pod_index']==spec['fault_rack']//8
        assert case['fault_start_s']==spec['fault_start_s'] and case['fault_duration_s']==spec['duration_s']==180
        assert case['fault_end_s_exclusive']==spec['fault_start_s']+spec['duration_s']
    deferred=0;maximum_risk=0.;losses=0;gains=0
    for match in diagnosis['s0_risk_matches_existing_tour']:
        case=match['case'];s0=load_gzip(ROOT/f'runs/response-defer-search-20261102/S0-risk-{case}.json.gz')
        tour=load_gzip(ROOT/match['tour_file'])
        assert s0['process_sha256']==tour['process_sha256'] and s0['action_log']==tour['action_log']
        decisions=[r for r in s0['binary_decisions'] if r['reason']=='rule']
        assert all(r['choice']=='defer' for r in decisions)
        deferred+=len(decisions);maximum_risk=max(maximum_risk,max((r['features']['risk']*4 for r in decisions),default=0))
        first=load_gzip(ROOT/f'runs/event-validation-amended-20261102/{case}-fifo.json.gz')
        age=load_gzip(ROOT/f'runs/response-defer-search-20261102/S1-age-{case}.json.gz')
        confirmed=lambda record:{(r['task_id'],r['onset_s'],r['end_s']) for r in record['anomaly_intervals'] if r['detected']}
        lost=confirmed(first)-confirmed(age);gains+=len(confirmed(age)-confirmed(first));losses+=len(lost)
        for task,start,end in lost:
            measurements=[r for r in age['inspection_events'] if r['task_id']==task]
            assert not any(start<=r['time_s']<=end for r in measurements)
            after=min((r for r in measurements if r['time_s']>end),key=lambda r:r['time_s'])
            assert not after['alarm']
    assert deferred==229 and math.isclose(maximum_risk,.7604212881250225) and (gains,losses)==(2,12)
    example=diagnosis['trace_examples']['p00_first_difference_and_loss']
    assert data['rule_diagnosis_example']==example
    marker=next(e for e in drawings['rule-diagnosis'].iter() if 'data-diagnosis-case' in e.attrib)
    assert {k:float(marker.attrib[k]) for k in ['data-anomaly-start','data-anomaly-end','data-fifo-dispatch','data-fifo-measured','data-rule-measured']}=={
        'data-anomaly-start':310.,'data-anomaly-end':335.,'data-fifo-dispatch':300.,'data-fifo-measured':320.,'data-rule-measured':365.}
    threshold_keys={'net_confirmations':'minimum_mean_net_confirmations',
                    'travel_delta_pct':'maximum_travel_increase_pct',
                    'completed_loss_pct':'maximum_completion_loss_pct'}
    markers=[e for e in drawings['outcome-costs'].iter() if 'data-cost-key' in e.attrib]
    assert len(markers)==3 and {e.attrib['data-cost-key'] for e in markers}==set(threshold_keys)
    for e in markers:
        key=e.attrib['data-cost-key'];value=data['primary_comparisons'][key]
        if key=='net_confirmations':value=value['mean']
        assert float(e.attrib['data-value'])==value
        assert float(e.attrib['data-threshold'])==protocol['decision_thresholds'][threshold_keys[key]]
    report={'status':'PASS','html_sha256':digest(ROOT/'paper/supervisor-briefing.html'),
            'checker_sha256':digest(Path(__file__)),'unchanged_frozen_files':frozen_count,
            'engineering_frame_arrays_checked':4,'actual_fifo_queue_checked':True,'both_return_certificates_checked':True,
            'actual_visits_checked':3,'primary_anomaly_kinds':dict(counts),
            'embedded_svg_files_checked':len(drawings),'embedded_hotspot_values_checked':256,
            'registered_rules_checked':len(rules),'main_costs_recomputed_from_rows':True,'new_environment_evaluations':0,
            'fault_processes_checked':12,'diagnosis_input_hashes_checked':len(diagnosis['source_files']),
            's0_risk_deferred_binary_decisions':deferred,'s0_risk_maximum_observed_score_input':maximum_risk,
            's1_age_gained':gains,'s1_age_lost_intervals_without_in_window_measurements':losses,
            'risk_470_component_recalculation':methods['risk_470s']['component_recomputation_status'],
            'scope':'Read existing full records and public report extracts only; no simulation, training or research-model inference.'}
    (ROOT/'paper/generated/supervisor-report-source-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS:',frozen_count,'original files unchanged; engineering maps, actual FIFO queue, certificates and visits match source records.')


if __name__=='__main__':main()
