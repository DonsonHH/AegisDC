"""Independently check report extracts against existing full local records."""
from __future__ import annotations
from collections import Counter, defaultdict
import ast
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def verify_comparison(data):
    comparison=load(ROOT/'paper/source-data/report-comparison-metrics.json')
    assert data['comparison']==comparison['aggregates'] and data['comparison_definition']==comparison['definitions']
    for identity in comparison['sources']:assert digest(ROOT/identity['path'])==identity['sha256'],identity['path']
    deadlines=comparison['common_tasks']['deadlines_s'];assert len(deadlines)==176
    recomputed=defaultdict(list);completed_events=0
    for case in comparison['cases']:
        tour=load_gzip(ROOT/case['weights_source']);weights={};limits={}
        for decision in tour['local_decisions']:
            for row in decision.get('public_tasks',[]):
                task=row['task'];weight=2*row['weight'];limit=row['deadline_s']
                if task in weights:assert weights[task]==weight and limits[task]==limit
                weights[task]=weight;limits[task]=limit
        assert sorted(weights)==list(range(176))
        assert [weights[j] for j in range(176)]==case['asset_weights'] and [limits[j] for j in range(176)]==deadlines
        for method,saved in case['methods'].items():
            record=tour if method=='tour' else load_gzip(ROOT/saved['record_path'])
            assert record['process_sha256']==case['process_sha256']
            area=0.;gaps=record['exact_task_gaps'];assert len(gaps)==176
            measurements=defaultdict(list)
            for event in record['inspection_events']:measurements[event['task']].append(event['time_s'])
            for item in gaps:
                task=item['task'];times=item['completion_times_s'];assert sorted(measurements[task])==times
                endpoints=[0.,*times,1800.];limit=deadlines[task]
                for before,after in zip(endpoints,endpoints[1:]):
                    gap=after-before;assert gap>=0
                    # Integral of min(age / deadline, 1), including initial/terminal gaps.
                    capped=min(gap,limit)
                    area+=weights[task]*(capped*capped/(2*limit)+max(0.,gap-limit))
            denominator=1800*sum(weights.values());score=area/denominator
            assert math.isclose(area,saved['weighted_age_time_integral_s'],rel_tol=1e-12)
            assert denominator==saved['weighted_age_denominator_s'] and math.isclose(score,saved['weighted_normalized_age'],rel_tol=1e-12)
            confirmed=sum(a['detected'] for a in record['anomaly_intervals'])
            assert confirmed==saved['confirmed_segments']==record['metrics']['confirmed_segments']
            for item in record['anomaly_intervals']:
                when=item['first_confirmation_s']
                assert item['detected']==(when is not None)
                if when is not None:
                    assert item['onset_s']<when<=item['end_s']
                    assert any(e['time_s']==when and e['task_id']==item['task_id'] and e['alarm'] for e in record['inspection_events'])
            for key in ['temperature_rmse_c','temperature_weighted_rmse_c','temperature_r2','single_step_inference_ms']:assert saved[key] is None
            recomputed[method].append(score);completed_events+=len(record['inspection_events'])
    assert len(comparison['cases'])==12 and set(recomputed)==set(comparison['aggregates'])
    for method,scores in recomputed.items():assert math.isclose(mean(scores),comparison['aggregates'][method]['mean_weighted_normalized_age'],rel_tol=1e-12)
    for key in ['vae_unet_greedy','vae_unet_drl']:
        item=comparison['unrun_methods'][key]
        assert item['all_metric_values'] is None and not item['trained_or_training_claim_supported'] and not item['completed_128_rack_and_mask_adaptation_claim_supported']
    return {'comparison_methods_recomputed':len(recomputed),'comparison_task_gap_sets_checked':12*5*176,
            'comparison_measurements_checked':completed_events,'comparison_input_hashes_checked':len(comparison['sources'])}


def verify_supplement(data,manifest):
    supplement=load(ROOT/'paper/source-data/supplement-study.json')
    assert data['supplement']==supplement
    receipt=load(ROOT/'evidence/supplement-study/analysis-receipt.json')
    assert receipt['paper_source_sha256']==digest(ROOT/'paper/source-data/supplement-study.json')
    assert receipt['analyzer_sha256']==digest(ROOT/'scripts/analyze_supplement_study.py')
    assert receipt['test_rows_sha256']==digest(ROOT/'evidence/supplement-study/test-rows.json')
    assert receipt['checkpoint_archive_sha256']==digest(ROOT/'evidence/supplement-study/checkpoints.zip')
    original=load(ROOT/'evidence/supplement-study/local-artifacts.json')
    raw_root=ROOT/original['root']
    for relative,identity in original['files'].items():
        path=raw_root/relative
        assert path.stat().st_size==identity['bytes'] and digest(path)==identity['sha256'],relative
    checkpoints=supplement['checkpoint_lock']['checkpoints']
    with zipfile.ZipFile(ROOT/'evidence/supplement-study/checkpoints.zip') as archive:
        assert set(archive.namelist())==set(checkpoints)
        for name,identity in checkpoints.items():assert hashlib.sha256(archive.read(name)).hexdigest()==identity
    execution=supplement['executed_source']
    assert digest(ROOT/'evidence/supplement-study/source-executed.zip')==execution['archive_sha256']
    with zipfile.ZipFile(ROOT/'evidence/supplement-study/source-executed.zip') as archive:
        assert set(archive.namelist())==set(execution['files'])
        for name,identity in execution['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==identity
    rows=load(ROOT/'evidence/supplement-study/test-rows.json')
    assert len(rows)==1080 and manifest['test_episode_count']==1080
    primary=set(supplement['protocol']['analysis']['primary_families'])
    selected=[r for r in rows if r['family'] in primary]
    keys=['confirmed_segments','consequence_weighted_censored_delay_s','weighted_normalized_age','all_weighted_rmse_c']
    # Separate implementation of the report's inference unit from the raw
    # extraction: one conditional mean per model set, then four equal families.
    blocks={}
    for method in supplement['method_order']:
        block_values=[]
        for block in range(12):
            values={}
            for key in keys:
                family_values=[]
                for family in primary:
                    found=[r['metrics'][key] for r in selected if r['method']==method and r['block']==block and r['family']==family and r['metrics'][key] is not None]
                    if found:family_values.append(sum(found)/len(found))
                values[key]=sum(family_values)/len(family_values) if family_values else None
                saved=supplement['block_values'][method][block][key]
                assert saved is None if values[key] is None else math.isclose(values[key],saved,rel_tol=1e-11,abs_tol=1e-12)
            block_values.append(values)
        blocks[method]=block_values
        for key in keys:
            values=[r[key] for r in block_values if r[key] is not None]
            record=supplement['primary_aggregates'][method][key]
            assert math.isclose(sum(values)/len(values),record['mean'],rel_tol=1e-11,abs_tol=1e-12)
    contrasts_checked=0
    for contrast in supplement['contrasts']:
        for key in keys:
            if key not in contrast['metrics']:continue
            values=[a[key]-b[key] for a,b in zip(blocks[contrast['first']],blocks[contrast['second']]) if a[key] is not None and b[key] is not None]
            rng=np.random.default_rng(20261103);array=np.asarray(values)
            draws=rng.choice(array,size=(10000,len(array)),replace=True).mean(1)
            interval=np.quantile(draws,[.025,.975])
            saved=contrast['metrics'][key]
            assert math.isclose(float(array.mean()),saved['mean'],rel_tol=1e-11,abs_tol=1e-12)
            assert np.allclose(interval,saved['percentile95'],rtol=1e-11,atol=1e-12)
            contrasts_checked+=1
    narrative=load(ROOT/'paper/source-data/supplement-narrative.json')
    assert narrative['analysis_sha256']==digest(ROOT/'paper/source-data/supplement-study.json')
    example=load(ROOT/supplement['example']['path'])
    assert digest(ROOT/supplement['example']['path'])==supplement['example']['sha256']
    case=supplement['protocol']['case_sets']['test'][0];assert example['case']==case and example['model_seed']==271
    reference=raw_root/'test'/(case['id']+'-nominal-tour')/'arrays.npz'
    predicted=raw_root/'fixed-stream-predictions'/f"{case['id']}-cvae-271.npz"
    assert digest(reference)==example['source_arrays_sha256'] and digest(predicted)==example['source_prediction_sha256']
    frame=int(example['frame_time_s']/5)-1;rack=example['trace_rack_index'];pod=example['pod_index']
    assert rack==case['spec']['fault_rack']//8*8+1 and example['frame_time_s']==case['spec']['fault_start_s']+90
    with np.load(reference) as a,np.load(predicted) as b:
        for key,value in [('nominal',a['predicted_temperature_c']),('cvae',b['predicted_temperature_c']),('truth',a['true_temperature_c'])]:
            assert np.array_equal(example['frame_temperature_c'][key],value[frame])
            assert np.array_equal(example['trace'][key+'_c'],value[:,rack])
        assert np.array_equal(example['trace']['fresh_mask'],a['fresh_measurement_mask'][:,rack])
        assert np.array_equal(example['trace']['pod_flow_kg_s'],a['offline_rack_flow_kg_s'].reshape(360,16,8).sum(2)[:,pod])
    assert supplement['audit']['raw_label_professional_outcomes_recomputed']==1080
    assert supplement['audit']['fixed_stream_error_cases_recomputed']==216
    assert manifest['independent_test_seed_blocks']==12 and manifest['unique_test_physical_processes']==60
    archive=load(ROOT/'paper/briefing-history/f35b172e/baseline.json')
    for identity in archive['files'].values():assert digest(ROOT/identity['archived_as'])==identity['sha256']
    return {'supplement_original_files_hashed':len(original['files']),'supplement_checkpoints_hashed':9,
            'supplement_model_seed_family_block_aggregates_checked':7*12*len(keys),
            'supplement_paired_intervals_recomputed':contrasts_checked,
            'supplement_analysis_audit':supplement['audit'],'pre_study_report_files_unchanged':len(archive['files'])}


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
                             ('estimated-temperature','estimated-temperature',engineering['public_estimated_temperature_c']),
                             ('offline-temperature','temperature',engineering['offline_temperature_c'])]:
        encoded={int(e.attrib['data-rack']):float(e.attrib['data-value']) for e in drawings[name].iter() if e.attrib.get('data-kind')==kind}
        assert encoded==dict(enumerate(values)),name
    risk_overlay=[int(e.attrib['data-rack']) for e in drawings['estimated-temperature'].iter() if 'data-risk-positive' in e.attrib]
    assert risk_overlay==[i for i,value in enumerate(engineering['public_thermal_risk']) if value>0]==[64,67,70]
    visual=load(ROOT/'paper/source-data/pid-visual-sample.json')
    image_elements=[e for e in drawings['pid-visual-sample'].iter() if e.tag.endswith('image')];assert len(image_elements)==3
    for image_element,key in zip(image_elements,['rgb','generated','display-target']):
        encoded=image_element.attrib['href'];assert encoded.startswith('data:image/png;base64,')
        raw=base64.b64decode(encoded.split(',',1)[1],validate=True);identity=visual['assets'][key]
        assert hashlib.sha256(raw).hexdigest()==identity['sha256'] and raw==(ROOT/identity['path']).read_bytes()
    alignment=load(ROOT/'paper/source-data/report-engineering-alignment.json')
    assert alignment==data['engineering_alignment']
    for row in alignment['primary_records']:
        path=ROOT/row['record'];assert digest(path)==row['sha256']
        record=load_gzip(path);assert record['process_metadata']['peak_source_input_MW']==row['peak_source_input_mw']
        assert record['process_metadata']['configuration']['racks']==128
    assert all(not row['formal_clauses_read'] for row in alignment['standards'])
    comparison_checks=verify_comparison(data)
    supplement_checks=verify_supplement(data,manifest)
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
            'embedded_svg_files_checked':len(drawings),'embedded_hotspot_values_checked':384,'existing_pid_images_checked':3,
            'registered_rules_checked':len(rules),'main_costs_recomputed_from_rows':True,'new_environment_evaluations':0,
            'fault_processes_checked':12,'diagnosis_input_hashes_checked':len(diagnosis['source_files']),
            's0_risk_deferred_binary_decisions':deferred,'s0_risk_maximum_observed_score_input':maximum_risk,
            's1_age_gained':gains,'s1_age_lost_intervals_without_in_window_measurements':losses,
            'risk_470_component_recalculation':methods['risk_470s']['component_recomputation_status'],
            **comparison_checks,**supplement_checks,
            'scope':'This checker reads retained historical/new originals and extracts, hashes all supplementary artifacts and independently recomputes block aggregates/paired intervals. The separate completed analyzer reconstructs raw-label outcomes, errors, costs and model identities. No new simulation/training/inference in this check.'}
    (ROOT/'paper/generated/supervisor-report-source-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS:',frozen_count,'original files unchanged; engineering maps, actual FIFO queue, certificates and visits match source records.')


if __name__=='__main__':main()
