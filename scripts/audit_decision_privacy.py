"""Actual private V6 witnesses and separate current-input consumer traces.

This is an evaluator tool. It never passes a world/run/trace to the consumer and
does not connect the planning demo to execution or generate observations.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario

BOOK = 'docs/mainline/15-truth-runbook.json'


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def execute(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    book = json.loads((ROOT / BOOK).read_text(encoding='utf-8'))
    write(output / 'runbook-copy.json', book)
    require(book['classification'] == 'FULL_V6_INFORMATION_FLOW_ENGINEERING_NOT_POLICY_RESEARCH',
            'This tool only runs the frozen information-flow engineering fixture')
    require(all(book[key] == 0 for key in ('registered_research_trials', 'model_calls', 'training_calls')),
            'No research/model/training budget is open')
    fixture = ROOT / book['public_fixture']
    worlds, traces, stage = {}, {}, 'start'
    try:
        # Private plant results stay in the evaluator. The public nominal file
        # was authored independently and is never rebuilt from these copies.
        for item in book['private_worlds']:
            name = item['id']
            stage = 'private_world/' + name
            scenario = load_scenario(ROOT / book['profile'])
            for parameter in scenario['parameters']:
                if parameter['id'] in item['overrides']:
                    parameter.update(value=item['overrides'][parameter['id']], basis='synthetic_assumption',
                        source_note='Ticket15 private engineering world override; not nominal dispatch knowledge.')
            result = simulate_scenario(scenario, duration_s=book['duration_s'], step_s=book['maximum_step_s'],
                boundary_events=item['boundary_events'], work_requests=book['private_work_requests'])
            save_run(result, output / 'private-worlds' / name)
            final = result['trace'][-1]['domains']
            job = next(row for row in result['work_records'] if row['id'] == 'private-it-audit-job')
            worlds[name] = dict(run_path=f'private-worlds/{name}/run.json',
                delivered_service_unit_s=result['summary']['delivered_service_unit_s'],
                floor_mass_kg=final['space_access']['floor_water_mass_kg'],
                blocked_locations=final['space_access']['blocked_location_ids'],
                compute_permitted=final['control_monitoring']['compute_permitted'],
                local_control_mode=final['control_monitoring']['mode'],
                job=job, domain_ids=list(final), state_points=len(result['trace']),
                actual_execution_commit=result['code_identity']['git_commit'],
                implementation_has_changes=result['code_identity']['implementation_has_changes'])
            del result
        # A new CLI process has no private-world Python object. World names are
        # only evaluator output paths, not nominal/ledger IDs or frame fields.
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        for world in worlds:
            for stream, filename in book['public_streams'].items():
                stage = 'evaluator_trace/' + world + '/' + stream
                directory = output / 'evaluator-traces' / world / stream
                command = [sys.executable, '-B', '-X', 'utf8', '-m', 'aegis_dc.decision_view',
                    '--nominal', str(fixture / 'public-nominal.json'), '--ledger', str(fixture / filename),
                    '--plan', str(fixture / 'public-plan.json'), '--output', str(directory)]
                done = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True)
                transcript = output / 'cli-transcripts' / world
                transcript.mkdir(parents=True, exist_ok=True)
                with (transcript / (stream + '.stdout.txt')).open('xb') as file:
                    file.write(done.stdout)
                with (transcript / (stream + '.stderr.txt')).open('xb') as file:
                    file.write(done.stderr)
                write(transcript / (stream + '.command.json'), dict(command=command, returncode=done.returncode))
                require(done.returncode == 0, 'Offline decision trace failed: ' + stage)
                saved = json.loads((directory / 'private-decision-trace.json').read_text(encoding='utf-8'))
                require(saved == json.loads(done.stdout), 'CLI stdout and saved trace differ')
                require(saved['visibility'] == 'PRIVATE_EVALUATOR_ONLY_NOT_A_DISPATCH_INPUT', 'Hindsight trace must remain private')
                traces[world, stream] = saved
        expected = book['independent_expectations']
        require(abs(worlds['A']['delivered_service_unit_s'] - expected['world_A_delivered_service_unit_s']) <= 1e-9,
                'Healthy private working-point service witness differs')
        require(worlds['B']['delivered_service_unit_s'] == expected['world_B_delivered_service_unit_s'],
                'Unprotected IT outage witness differs')
        for name in worlds:
            require(worlds[name]['job']['status'] == expected['world_' + name + '_private_job_status'], 'Private safety/work witness differs')
            require(worlds[name]['compute_permitted'] is expected['world_' + name + '_compute_permitted_at_end'],
                    'Private local-control witness differs')
            for stream in book['public_streams']:
                ticks = [step['frame']['as_of_s'] for step in traces[name, stream]['steps']]
                require(ticks == expected['public_ticks_each_stream'], 'Public schedule changed with a private event')
                require(all(not step['options']['execution_permission'] for step in traces[name, stream]['steps']),
                        'A planning result must not certify actual execution')
        require(worlds['B']['job']['reason'] == expected['world_B_private_job_reason'], 'Private access protection was bypassed')
        same_stream_pairs = {}
        for stream in book['public_streams']:
            equal = traces['A', stream] == traces['B', stream]
            require(equal, 'The same public input changed with a hidden world or output path')
            same_stream_pairs[stream] = equal
        pre, post = [], []
        for left, right in zip(traces['A', 'open']['steps'], traces['B', 'closed']['steps']):
            time = left['frame']['as_of_s']
            if time < 6:
                require(left == right, 'An unarrived permit record changed public inputs/options')
                pre.append(time)
            else:
                require(left['options']['demo_choice_id'] == expected['first_public_choice_without_restriction'], 'Open-report demo differs')
                require(right['options']['demo_choice_id'] == expected['public_choice_with_arrived_restriction'], 'Restricted-report demo differs')
                require(right['options']['candidate_assessments'][0]['blocking_record_ids'] == [expected['blocking_record_id']],
                        'A changed choice lacks its arrived source record')
                post.append(time)
        require(len(pre) == expected['open_closed_equal_frames_before_6']
                and len(post) == expected['open_closed_changed_frames_from_6'], 'Public before/after case coverage differs')
        for step in traces['B', 'common']['steps']:
            require(step['options']['legal_mask']['intent-it-check'], 'Unknown dynamics collapsed every planning option')
        result = dict(schema='aegisdc-private-truth-isolation-audit-v1', visibility='PRIVATE_EVALUATOR_ONLY',
            status='PASS', private_worlds=worlds, same_input_across_actual_worlds=same_stream_pairs,
            equal_before_legal_arrival_times_s=pre, changed_after_legal_arrival_times_s=post,
            private_event_times=[row['time_s'] for row in book['private_worlds'][1]['boundary_events']],
            physical_runs=2, offline_trace_commands=6, public_ticks_each=expected['public_ticks_each_stream'],
            crossed_streams_also_follow_records=True,
            observations='Externally hand-authored inputs; not generated by this evaluator or the private jobs',
            planning='Unverified preparation intentions only, no actual action execution or policy effect',
            registered_research_trials=0, model_calls=0, training_calls=0, research_gain_claim='NOT_ESTABLISHED')
        write(output / 'audit-summary.json', result)
        write(output / 'audit-status.json', dict(status='PASS', physical_runs=2, registered_research_trials=0))
        return result
    except Exception as error:
        write(output / 'audit-status.json', dict(status='FAIL', stage=stage, error=repr(error), traceback=traceback.format_exc()))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.output)
    print(json.dumps({key: result[key] for key in ('status', 'physical_runs', 'offline_trace_commands', 'same_input_across_actual_worlds')}))


if __name__ == '__main__':
    main()
