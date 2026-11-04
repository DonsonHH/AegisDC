"""Capture frozen joint-service hand cases through public run/CLI interfaces."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.scenario import load_scenario


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'evidence/mainline/engineering/08-service'


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def boundary(parameter_id, value, time_s=0.25, source_note='Ticket 08 synthetic invalid-input negative fixture.'):
    return {'time_s': time_s, 'parameter_id': parameter_id, 'value': value, 'source_note': source_note}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases_file = BASE / 'hand-cases-v1.json'
    cases = json.loads(cases_file.read_text(encoding='utf-8'))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    bad_inputs = [
        {'id': 'negative-capacity', 'events': [boundary('compute_service_capacity', -0.1)]},
        {'id': 'capacity-outside-range', 'events': [boundary('network_service_capacity', 2.1)]},
        {'id': 'boolean-capacity', 'events': [boundary('storage_service_capacity', True)]},
        {'id': 'missing-source', 'events': [boundary('network_service_capacity', 0.5, source_note='')]},
        {'id': 'conflicting-capacity', 'events': [boundary('storage_service_capacity', 0.5),
                                                 boundary('storage_service_capacity', 1)]},
        {'id': 'static-coefficient', 'events': [boundary('compute_nominal_power', 1000000)]},
    ]
    write_new(output / 'declared-inputs.json', {'hand_case_file': str(cases_file.relative_to(ROOT)).replace('\\', '/'),
              'hand_case_sha256': file_sha(cases_file), 'implementation_commit': commit,
              'accepted_cases': cases, 'expected_rejections': bad_inputs,
              'scope': 'ENGINEERING_FIXTURES_ONLY'})

    summaries = {}
    for item in cases['cases']:
        name, destination = item['id'], output / item['id']
        inputs = {'schema': 'aegisdc-engineering-inputs-v1', 'work_requests': [],
                  'boundary_events': item['boundary_events']}
        input_file = output / (name + '.inputs.json')
        write_new(input_file, inputs)
        if item.get('via_cli'):
            process = subprocess.run([sys.executable, '-m', 'aegis_dc', 'simulate',
                                      '--duration', str(item['duration_s']), '--step', str(item['step_s']),
                                      '--inputs', str(input_file), '--output', str(destination)],
                                     cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
                                     capture_output=True, text=True, encoding='utf-8')
            with (output / (name + '.cli-stdout.json')).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(process.stdout)
            with (output / (name + '.cli-stderr.txt')).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(process.stderr)
            if process.returncode != 0:
                raise RuntimeError('CLI failed; its original stdout/stderr are retained')
        else:
            result = simulate_scenario(load_scenario(ROOT / 'configs/full-facility-mainline-v2.json'),
                                       duration_s=item['duration_s'], step_s=item['step_s'],
                                       boundary_events=item['boundary_events'])
            save_run(result, destination)

        # Acceptance consumes freshly read output, not the simulate/save return.
        manifest = json.loads((destination / 'run.json').read_text(encoding='utf-8'))
        assert manifest['code_identity']['git_commit'] == commit
        assert manifest['code_identity']['implementation_has_changes'] is False
        if item.get('via_cli'):
            assert json.loads(process.stdout) == manifest
        for artifact, identity in manifest['artifacts'].items():
            path = destination / artifact
            assert file_sha(path) == identity['sha256']
            if artifact.endswith('.jsonl'):
                assert len(path.read_text(encoding='utf-8').splitlines()) == identity['records']
        for key, expected in item['expected'].items():
            assert abs(manifest['summary'][key] - expected) <= 1e-12, (name, key)
        trace = [json.loads(line) for line in (destination / 'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
        assert all(len(row['domains']) == 8 for row in trace)
        assert all(0 <= row['domains']['it_service']['delivered'] <= row['domains']['it_service']['demand'] for row in trace)
        assert manifest['research_trials'] == manifest['model_calls'] == manifest['training_calls'] == 0
        summary = manifest['summary']
        summaries[name] = {'source_commit': commit, 'scenario_sha256': manifest['scenario_sha256'],
                           'manifest_sha256': file_sha(destination / 'run.json'),
                           'input_file_sha256': file_sha(input_file),
                           'expected': item['expected'],
                           'observed': {key: summary[key] for key in item['expected']},
                           'unserved_service_unit_s': summary['demand_service_unit_s'] - summary['delivered_service_unit_s'],
                           'max_energy_residual_J': summary['max_energy_residual_J'],
                           'whole_run_energy_residual_J': summary['whole_run_energy_residual_J'],
                           'max_mass_residual_kg': summary['max_mass_residual_kg'],
                           'trace_records': len(trace), 'balances': summary['integration_steps'],
                           'entry_point': 'CLI' if item.get('via_cli') else 'simulate_scenario'}

    rejections = []
    for item in bad_inputs:
        try:
            simulate_scenario(load_scenario(ROOT / 'configs/full-facility-mainline-v2.json'),
                              duration_s=2, boundary_events=item['events'])
        except ValueError as error:
            rejections.append(dict(item, error=str(error), successful_trajectory_returned=False))
        else:
            raise AssertionError('An invalid timed capacity input was accepted: ' + item['id'])
    write_new(output / 'expected-rejections.json', rejections)
    artifacts = {str(path.relative_to(output)).replace('\\', '/'): file_sha(path)
                 for path in sorted(output.rglob('*')) if path.is_file()}
    receipt = {'schema': 'aegisdc-service-engineering-receipt-v1', 'status': 'PASS',
               'scope': 'Finite complete-facility engineering checks; not empirical calibration or strategy research',
               'recorded_UTC': datetime.now(timezone.utc).isoformat(),
               'implementation_commit': commit, 'author_script_sha256': file_sha(Path(__file__).resolve()),
               'hand_cases_sha256': file_sha(cases_file), 'runs': summaries,
               'expected_rejections': len(rejections), 'artifacts': artifacts,
               'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
               'field_calibration': 'PENDING', 'research_gain': 'NOT_ESTABLISHED',
               'M1_gate': 'IN_PROGRESS', 'overall_goal': 'ACTIVE'}
    write_new(output / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'runs': len(summaries),
                      'expected_rejections': len(rejections), 'artifacts': len(artifacts),
                      'receipt_sha256': file_sha(output / 'receipt.json')}))


if __name__ == '__main__':
    main()
