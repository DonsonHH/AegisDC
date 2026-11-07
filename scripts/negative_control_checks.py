"""Evaluate saved ticket 28 outputs against pre-execution literal and timing witnesses."""
from copy import deepcopy
from fractions import Fraction
import json
import math
from pathlib import Path

from inspection_delivery import digest, read, require

DOMAINS = {'power', 'backup', 'facility_cooling', 'equipment_environment', 'it_service',
           'control_monitoring', 'space_access', 'people_tools_work'}
METRICS = {
    'demand_service_unit_s': 'demand_service_unit_s',
    'delivered_service_unit_s': 'delivered_service_unit_s',
    'normalized_deficit_s': 'service_deficit_time_s',
    'travel_person_s': 'worker_travel_person_s',
    'work_person_s': 'worker_work_person_s',
    'access_check_person_s': 'access_check_person_s',
}


def ratio(value):
    require(set(value) == {'numerator', 'denominator'}, 'Unknown rational literal')
    return Fraction(value['numerator'], value['denominator'])


def at_time(trace, time):
    points = [row['domains'] for row in trace if row['time_s'] == time]
    require(len(points) == 1, f'Missing unique saved time: {time}')
    return points[0]


def questions(decisions):
    result = {}
    for row in decisions:
        question, = row['choice']['question_lifecycle']['questions']
        result[row['frame']['as_of_s']] = question
    return result


def close(actual, expected, label, tolerance):
    require(type(actual) in (int, float) and math.isfinite(actual)
            and math.isclose(actual, float(expected), abs_tol=tolerance, rel_tol=0),
            'Independent literal differs: ' + label)


def common(folder, case, oracle, protocol, source, pins):
    run = read(folder / 'trajectory/run.json')
    trajectory = folder / 'trajectory'
    trace = [json.loads(line) for line in (trajectory / 'private-state.jsonl').read_bytes().splitlines()]
    balances = [json.loads(line) for line in (trajectory / 'balances.jsonl').read_bytes().splitlines()]
    require(read(folder / 'input.json') == case and read(trajectory / 'scenario.json') == case['model'],
            'Executed case inputs differ from fixed input')
    for name, identity in run['artifacts'].items():
        require(digest((trajectory / name).read_bytes()) == identity['sha256'], 'Original trajectory hash differs: ' + name)
    require(set(run['artifacts']) == {'scenario.json', 'private-state.jsonl', 'balances.jsonl'},
            'Unexpected physical artifact roles')
    require(all(set(row['domains']) == DOMAINS for row in trace) and run['facility_id'] == case['model']['id']
            and len(case['model']['domains']) == 8 and len(case['model']['graphs']) == 4, 'Full facility scope differs')
    actual_runtime = {name: sha for name, sha in pins['runtime'].items()
                      if name.startswith('src/aegis_dc/') or name == 'src/patrol_rsi/contracts.py'}
    identity = run['code_identity']
    require(identity['git_commit'] == source and not identity['implementation_has_changes']
            and identity['files'] == actual_runtime, 'Actual execution source differs')
    require(run['research_trials'] == run['model_calls'] == run['training_calls'] == 0
            and run['field_calibration'] == 'PENDING' and run['state_visibility'] == 'PRIVATE_PLANT_EVALUATOR_ONLY',
            'Engineering or private-state scope changed')
    summary = run['summary']
    require(summary['duration_s'] == case['duration_s']
            and run['inputs']['duration_s'] == case['duration_s']
            and run['inputs']['maximum_step_s'] == case['maximum_step_s'] == .01
            and len(trace) == len(balances) + 1 == summary['integration_steps'] + 1
            and trace[0]['time_s'] == 0 and trace[-1]['time_s'] == case['duration_s'], 'Physical duration or interval budget differs')
    require(all(b['start_s'] == trace[i]['time_s'] and b['end_s'] == trace[i+1]['time_s']
                and 0 < b['end_s'] - b['start_s'] <= .01 + 1e-13 for i,b in enumerate(balances)),
            'Saved trajectory and interval clocks disagree')
    for metric, key in METRICS.items():
        close(summary[key], ratio(oracle[metric]), key, protocol['literal_absolute_tolerance'])
        close(math.fsum(row[key] for row in balances), summary[key], 'interval sum ' + key, protocol['literal_absolute_tolerance'])
    require(abs(summary['whole_run_energy_residual_J']) < protocol['energy_tolerance_J']
            and summary['max_mass_residual_kg'] <= protocol['mass_tolerance_kg'], 'Whole facility boundary balance differs')
    for row in balances:
        close(math.fsum(row['storage_after_J'].values()) - math.fsum(row['storage_before_J'].values()),
              row['boundary_input_J'] - row['boundary_output_J'], 'independent interval energy inventory',
              protocol['energy_tolerance_J'])
        require(min(row['capacity_slack_W'].values()) >= -protocol['literal_absolute_tolerance'], 'Capacity exceeded')
    return run, trace, balances


def online(folder, case, run, trace, protocol, name):
    expected = case['replay_inputs']['dispatch_program']
    require(run['inputs']['dispatch_program'] == expected and run['inputs']['boundary_events'] == []
            and run['inputs']['work_requests'] == [], 'Actual online program was not the declared public input')
    decisions = run['policy_public_decisions']
    require([row['frame']['as_of_s'] for row in decisions] == protocol['online_decisions_s']
            and len(run['policy_computation_audit']) == 7, 'Online decision budget differs')
    chosen = [row['choice']['chosen_candidate_id'] for row in decisions]
    want = [None, 'first-inspection', None, None, None, None, None] if name == 'false_report' else [None] * 7
    require(chosen == want, 'Negative-control intention differs')
    require(run['intervention_private_audit']['events'] == [] and run['intervention_public_feedback'] == [],
            'Normal/false-report inspection changed physical parameters')
    q = questions(decisions)
    variants = {row['id'] for row in expected['policy_program']['options']['belief_model']['variants']}
    for decision in decisions:
        now = decision['frame']['as_of_s']
        if now not in {1,3,4.75}:
            continue
        world = decision['choice']['valuation_current_outcome_mass_by_belief_variant']
        value = [1,100] if name == 'normal' or now == 1 else [25,124] if now == 3 else [50,941]
        require(set(world) == variants and all(row['cooling-limited'] == value for row in world.values()),
                'Independent report/handheld posterior differs across declared variants')
    polls = run['policy_sensor_private_audit']
    for instrument, epochs in (('rectifier-meter',[0]),('lake-flow',[5,6,7]),('joint-service-meter',[5,6,7])):
        require([row['polled_at_s'] for row in polls if row['measurement_id'] == instrument] == epochs,
                'Sparse scheduled sensor polling differs')
    require(all(not value['risk_closed'] for value in q.values()), 'Normal or false alarm was labeled repaired')
    for row in decisions:
        now = row['frame']['as_of_s']
        records = {record['id']: record for record in row['frame']['evidence']['records']}
        require(all(record['observed_at_s'] <= record['arrived_at_s'] <= now for record in records.values()),
                'Decision received future evidence')
        choice = row['choice']
        require(not choice['execution_permission'] and not choice['generated_tour'], 'Policy gained execution privilege or imposed tour')
        if name == 'false_report':
            require(('delayed-lake-work-order' in records) == (now >= 3)
                    and ('actual-lake-flow-before-action' in records) == (now >= 4.75)
                    and ('false-alarm-review-28' in records) == (now >= 7),
                    'False report, actual measurement or authorized review arrived early')
    if name == 'normal':
        require(run['work_records'] == [] and run['inspection_public_snapshot']['records'] == []
                and all(value['status'] == 'OPEN_UNCONFIRMED' for value in q.values()), 'Normal state generated work or fake closure')
    else:
        task, = run['work_records']
        require((task['issued_at_s'], task['work_started_at_s'], task['completed_at_s'], task['status']) ==
                (3, 3.25, 4.25, 'completed'), 'False-report paid inspection timing differs')
        record, = run['inspection_public_snapshot']['records']
        raw = at_time(trace, record['observed_at_s'])['facility_cooling']['lake_pump']['volume_flow_m3_s']
        require(record['id'] == 'actual-lake-flow-before-action'
                and record['observed_at_s'] == 4.25 and record['arrived_at_s'] == 4.75
                and record['value'] >= .08 and record['quality']['status'] == 'bounded',
                'False suspicion did not produce a later real normal flow record')
        close(record['value'], raw, 'handheld actual current signal', protocol['literal_absolute_tolerance'])
        feedback, = run['inspection_public_feedback']
        require(feedback['confirmation'] == 'CONFIRMED_AT_OR_ABOVE_THRESHOLD'
                and feedback['record_id'] == record['id'] and feedback['additional_evidence_factor'] is False,
                'Handheld threshold support lost its provenance')
        require(all(value['status'] == 'OPEN_UNCONFIRMED' for time,value in q.items() if time < 7)
                and q[7]['status'] == 'FALSE_ALARM_REVIEWED' and q[7]['question_closed']
                and not q[7]['physical_restoration_claim'], 'False-alarm review was omitted, premature or labeled physical recovery')
        require(q[7]['supporting_record_ids'] == sorted(['flow-transfer:0', 'flow-transfer:1',
                'joint-service-transfer:0', 'joint-service-transfer:1']), 'False-alarm dossier lacks actual four arrived samples')
        early, later = decisions[0]['frame'], decisions[1]['frame']
        require('delayed-lake-work-order' not in {r['id'] for r in early['evidence']['records']}
                and 'delayed-lake-work-order' in {r['id'] for r in later['evidence']['records']}, 'Manual report did not drive the information change')
    return dict(status='PASS', chosen=chosen, closure={str(t): v['status'] for t,v in q.items()},
                public_decisions=len(decisions), paid_work=run['summary']['worker_work_person_s'])


def protection(folder, case, run, trace):
    events = [(row['parameter_id'], row['time_s'], row['value']) for row in run['inputs']['boundary_events']]
    require(events == [('internal_valve_opening', .75, 0), ('internal_valve_opening', 1.25, 1)]
            and run['work_records'] == [] and 'policy_public_decisions' not in run, 'Protection case gained manual work or different inputs')
    idle = read(folder / 'idle-crew-frame.json')
    work = run['inputs']['work_program']
    require(work['schema'] == 'aegisdc-work-program-v2' and work['submissions'] == []
            and work['initial_frame'] == idle and idle['as_of_s'] == 0
            and idle['evidence']['records'] == [], 'Local protection gained an undisclosed manual job')
    shut, trip, reopened, reset = (at_time(trace, t) for t in (.75, 1, 1.25, 2))
    require(not shut['control_monitoring']['hardwired_pump_permits']['internal_pump']
            and shut['facility_cooling']['internal_pump']['volume_flow_m3_s'] == 0, 'Immediate hardwired protection did not act')
    require(trip['control_monitoring']['protection_latched'] and trip['it_service']['delivered'] == 0
            and reopened['facility_cooling']['internal_pump']['volume_flow_m3_s'] > .01
            and reopened['control_monitoring']['protection_latched'] and reopened['it_service']['delivered'] == 0
            and not reset['control_monitoring']['protection_latched'] and reset['it_service']['delivered'] == .75,
            'Reopening bypassed the original sampled protection/reset rule')
    return dict(status='PASS', hardwired_at_s=.75, protected_at_s=1, flow_reopened_at_s=1.25,
                sampled_reset_at_s=2, manual_jobs=0)


def too_late(folder, case, run, trace):
    state = read(folder / 'public-preparation.json')
    frames = state['frames']
    before = read(folder / 'pre-call-preparation.json')
    work = run['inputs']['work_program']
    require(before['frames'] == frames[:2] and before['proposal'] == state['proposal']
            and work['schema'] == 'aegisdc-work-program-v2' and work['initial_frame'] == frames[0]
            and work['profile'] == case['public_preparation']['workforce_profile']
            and work['submissions'] == [dict(frame=frames[1],task=case['public_preparation']['task'])]
            and run['inputs']['intervention_program'] == case['intervention_program']
            and [(e['time_s'],e['parameter_id'],e['value']) for e in run['inputs']['boundary_events']]
                == [(3,'it_access_permit',0)], 'Late executed public/task inputs differ from declarations')
    require(all(frame['requests'] == case['public_preparation']['requests'] for frame in frames),
            'Static catalog preparation requests were not supplied at every declared frame')
    require([frame['as_of_s'] for frame in frames] == [0, 1, 3.25, 4]
            and all('delayed-network-work-order-28' not in {r['id'] for r in f['evidence']['records']}
                    for f in frames if f['as_of_s'] < 1), 'Late report entered an earlier frame')
    require(state['proposal']['legal_for_planning'] and not state['proposal']['execution_permission'],
            'Public static planning incorrectly asserted execution permission')
    task, = run['work_records']
    require((task['issued_at_s'],task['work_started_at_s'],task['scheduled_completion_at_s'],task['finished_at_s'],task['status']) ==
            (1, 2.25, 3.25, 3, 'aborted'), 'Actual task was not stopped before its earliest completion')
    effect, = run['intervention_private_audit']['events']
    feedback, = run['intervention_public_feedback']
    require(effect['outcome'] == 'NO_EFFECT' and effect['reason'] == 'actual_work_not_completed'
            and effect['task_status'] == 'aborted' and effect['observed_at_s'] == 3
            and not {'applied_at_s','parameter_id','old_value','new_value','effect_scope'} & set(effect)
            and feedback['outcome'] == 'NO_EFFECT' and feedback['reason'] == effect['reason'] and feedback['observed_at_s'] == 3
            and feedback['arrived_at_s'] == 3.5 and not feedback['risk_closed'], 'Aborted intervention gained an effect or early feedback')
    require(all(row['domains']['it_service']['delivered'] == .25 for row in trace)
            and all(row['kind'] != 'completed_research_intervention' for row in run['events']),
            'Failed work erased the network bottleneck')
    assessments = read(folder / 'closure.json')
    require([q['questions'][0]['status'] for q in assessments] == ['OPEN_UNCONFIRMED','OPEN_ACTION_FAILED']
            and all(not q['questions'][0]['question_closed'] and not q['questions'][0]['risk_closed'] for q in assessments),
            'Missing/failed action report was converted to closure')
    for frame, assessment in zip(frames[-2:], assessments):
        require(assessment['as_of_s'] == frame['as_of_s'] and frame['evidence']['records']
                and all(r['arrived_at_s'] <= frame['as_of_s'] for r in frame['evidence']['records']), 'Late closure assessment clock differs')
    return dict(status='PASS', earliest_completion_s=3.25, safety_abort_s=3, feedback_arrival_s=3.5,
                closure=[q['questions'][0]['status'] for q in assessments], public_preparation_frames=4)


def check_case(folder, name, case, oracle, protocol, source, pins):
    run, trace, _ = common(folder, case, oracle[name], protocol, source, pins)
    details = (online(folder, case, run, trace, protocol, name) if name in {'normal','false_report'} else
               protection(folder, case, run, trace) if name == 'local_protection' else too_late(folder, case, run, trace))
    return dict(**details, trace_points=len(trace), actual_summary=run['summary'])


def paired(folder):
    # Equal public inputs before the report must release the same decision frame.
    runs = [read(folder / name / 'trajectory/run.json') for name in ('normal','false_report')]
    first = [run['policy_public_decisions'][0] for run in runs]
    require(first[0]['frame'] == first[1]['frame'] and first[0]['choice']['chosen_candidate_id'] == first[1]['choice']['chosen_candidate_id'] is None,
            'A future false report or private case label changed the prior decision')
    # A crew can add numerical integration event boundaries. Do not call
    # different Euler grids byte-identical nonlinear thermal trajectories.
    models = [read(folder / name / 'trajectory/scenario.json') for name in ('normal','false_report')]
    require(models[0] == models[1] and
            runs[0]['inputs']['boundary_events'] == runs[1]['inputs']['boundary_events'] == [],
            'Normal and false-report physical inputs differ')
    require(all(event['kind'] not in {'completed_research_intervention', 'exogenous_boundary_input', 'engineering_control_command'}
                for run in runs for event in run['events']), 'An inspection wrote a physical parameter')
    for key in ('demand_service_unit_s', 'delivered_service_unit_s', 'service_deficit_time_s'):
        require(runs[0]['summary'][key] == runs[1]['summary'][key], 'Equal independent service integral differs')
    return dict(status='PASS', pre_report_public_frames_equal=True, physical_inputs_equal=True,
                no_intervention_or_physical_parameter_event=True,
                shared_service_integrals_equal=True,
                thermal_grid_note='Crew boundaries can split numerical intervals; no claim of byte-equal nonlinear trajectories.')
