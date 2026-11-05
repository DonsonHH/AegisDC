"""Independent saved-data checks; never rerun physics or a research policy."""
from hashlib import sha256
import json
from pathlib import Path

from aegis_dc.decision_view import decision_options, public_feasibility


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check_package(directory):
    directory = Path(directory)
    book = read(directory / 'runbook-copy.json')
    expected = book['independent_expectations']
    nominal = read(directory / 'fixture-copy/public-nominal.json')
    plan = read(directory / 'fixture-copy/public-plan.json')
    require(len(nominal['entities']) == 45 and len(nominal['domain_ids']) == 8
            and len(nominal['graphs']) == 4, 'Complete V6 identity/scope differs')
    require(len(nominal['graphs']['access']) == 5 and all(row['bidirectional']
            for row in nominal['graphs']['access']), 'Canonical public access directions differ')
    require(plan['decision_times_s'] == [0, 2, 4, 5.999999999999999, 6, 7], 'Frozen public ticks differ')
    private, traces = {}, {}
    for world in ('A', 'B'):
        folder = directory / 'audit/private-worlds' / world
        manifest = read(folder / 'run.json')
        states = [json.loads(line) for line in (folder / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        require(manifest['facility_id'] == nominal['facility_id'], 'Hidden world changed facility identity')
        require(manifest['inputs']['duration_s'] == 7 and manifest['inputs']['maximum_step_s'] == .01,
                'Physical witness does not use the frozen V6 duration/step')
        require(manifest['code_identity']['implementation_has_changes'] is False, 'Actual plant ran dirty source')
        for name, item in manifest['artifacts'].items():
            require(sha256((folder / name).read_bytes()).hexdigest() == item['sha256'], 'Private original manifest differs: ' + name)
        require(len(states[-1]['domains']) == 8, 'An operational domain disappeared')
        require(states[-1]['domains']['control_monitoring']['compute_permitted']
                is expected['world_' + world + '_compute_permitted_at_end'], 'Private local permit witness differs')
        job = next(row for row in manifest['work_records'] if row['id'] == 'private-it-audit-job')
        require(job['status'] == expected['world_' + world + '_private_job_status'], 'Private job status differs')
        if world == 'B':
            require(job['reason'] == 'access_unreachable', 'Private access safety was bypassed')
        service = manifest['summary']['delivered_service_unit_s']
        require(abs(service - expected['world_' + world + '_delivered_service_unit_s']) <= 1e-9,
                'Independent delivered-service witness differs')
        private[world] = dict(delivered_service_unit_s=service, job_status=job['status'],
            compute_permitted=states[-1]['domains']['control_monitoring']['compute_permitted'],
            state_points=len(states), execution_commit=manifest['code_identity']['git_commit'])
        for stream in ('common', 'open', 'closed'):
            trace = read(directory / f'audit/evaluator-traces/{world}/{stream}/private-decision-trace.json')
            require(trace['visibility'] == 'PRIVATE_EVALUATOR_ONLY_NOT_A_DISPATCH_INPUT', 'Hindsight trace has wrong visibility')
            require([row['frame']['as_of_s'] for row in trace['steps']] == plan['decision_times_s'],
                    'Public schedule changed with hidden events')
            for step in trace['steps']:
                frame, options = step['frame'], step['options']
                require(frame['nominal_knowledge'] == nominal, 'Current world changed nominal public knowledge')
                require(decision_options(frame) == options, 'Saved current-frame consumer output does not reproduce')
                require(all(public_feasibility(frame, row['request_id']) == row
                            for row in options['candidate_assessments']), 'Public feasibility differs from saved mask')
                require(options['execution_permission'] is False, 'Preparation became actual execution permission')
                require(options['legal_mask']['intent-unqualified-it-check'] is False, 'Nominal qualification counterexample disappeared')
            try:
                decision_options(trace)
            except ValueError:
                pass
            else:
                raise ValueError('Consumer accepted accumulated private hindsight')
            command = read(directory / f'audit/cli-transcripts/{world}/{stream}.command.json')
            require(command['returncode'] == 0, 'Actual standalone CLI failed')
            require(trace == read(directory / f'audit/cli-transcripts/{world}/{stream}.stdout.txt'), 'Saved CLI stdout differs')
            traces[world, stream] = trace
    require(private['A']['execution_commit'] == private['B']['execution_commit'], 'Paired worlds used different source')
    for stream in ('common', 'open', 'closed'):
        require(traces['A', stream] == traces['B', stream], 'Hidden world leaked into the same public stream')
    for world in ('A', 'B'):
        require(traces[world, 'open']['steps'][:4] == traces[world, 'closed']['steps'][:4], 'Unarrived record changed current frames')
        for step in traces[world, 'common']['steps']:
            require(step['options']['demo_choice_id'] == 'intent-it-check', 'Missing dynamic status hid a planning intention')
        for index in (4, 5):
            opened = traces[world, 'open']['steps'][index]['options']
            closed = traces[world, 'closed']['steps'][index]['options']
            require(opened['demo_choice_id'] == 'intent-it-check' and closed['demo_choice_id'] == 'intent-filter-check',
                    'Arrived declared report did not control the planning choice')
            require(closed['candidate_assessments'][0]['blocking_record_ids'] == ['it-entry-report-t4'],
                    'Deferred intention is not traceable to its legal arrived report')
    require(traces['A', 'closed'] == traces['B', 'closed'] and traces['B', 'open'] == traces['A', 'open'],
            'Crossed public streams followed the private world')
    return dict(status='PASS', private_worlds=private, complete_shared_entity_ids=45, operational_domains=8,
        relation_graphs=4, actual_private_worlds=2, actual_standalone_CLI_commands=6,
        public_frames_recomputed=36, public_feasibility_queries_recomputed=108,
        same_stream_cross_world_equal_frames=18, crossed_streams_follow_records=True,
        open_closed_equal_frames_each_world_before_arrival=4, changed_frames_each_world_after_arrival=2,
        public_ticks=[0, 2, 4, 5.999999999999999, 6, 7], execution_permission=False,
        observation_generation='NOT_IMPLEMENTED_HERE_HAND_AUTHORED_PUBLIC_INPUTS',
        physics_rerun=False, full_regression_rerun=False, registered_research_trials=0, model_calls=0, training_calls=0)
