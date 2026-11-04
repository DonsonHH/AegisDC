"""Versioned full-facility replay through recorded-run/read/replay and CLI seams."""
from pathlib import Path
import json
import os
import math
import subprocess
import sys
import tempfile
import unittest

from aegis_dc.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/full-facility-mainline-reserve-v6.json'


def frozen_inputs(**changes):
    result = dict(schema='aegisdc-facility-replay-inputs-v1', seed=1301,
                  exogenous_events=[], action_commands=[], work_requests=[])
    result.update(changes)
    return result


class FacilityReplayTests(unittest.TestCase):
    def test_frozen_V6_run_replays_all_physical_accounts_exactly(self):
        from aegis_dc.replay import read_attempt, replay_attempt, run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary) / 'original'
            repeated = Path(temporary) / 'replayed'
            record = run_recorded(load_scenario(PROFILE), original, inputs=frozen_inputs(),
                                  duration_s=2, step_s=.5)
            replay = replay_attempt(original, repeated)
            first, second = read_attempt(original), read_attempt(repeated)
            self.assertEqual((record['status'], replay['status']), ('COMPLETED', 'COMPLETED'))
            self.assertEqual(first['run']['summary']['delivered_service_unit_s'], 2)
            self.assertEqual(first['run']['summary']['service_deficit_time_s'], 0)
            self.assertEqual(len(first['run']['trace'][-1]['domains']), 8)
            for field in ('summary', 'trace', 'balances', 'events', 'work_records', 'inputs'):
                self.assertEqual(first['run'][field], second['run'][field], field)
            self.assertEqual(first['record']['seed'], 1301)
            self.assertEqual(first['record']['source_identity']['schema'], 'aegisdc-execution-source-v1')
            self.assertEqual(first['record']['source_identity'], second['record']['source_identity'])
            self.assertEqual(first['inputs'], second['inputs'])
            self.assertEqual(replay['replay_of']['attempt_sha256'], first['record_sha256'])

    def test_same_offered_demand_and_weather_preserve_control_action_causality(self):
        from aegis_dc.replay import read_attempt, replay_attempt, run_recorded
        schedule = frozen_inputs(exogenous_events=[
            dict(time_s=.25, parameter_id='service_demand', value=1,
                 source_note='Frozen offered demand; unmet demand remains offered.'),
            dict(time_s=.25, parameter_id='lake_temperature', value=285,
                 source_note='Frozen synthetic lake boundary, not a dispatch observation.'),
        ])
        action = dict(id='close-internal-valve', time_s=.25, parameter_id='internal_valve_opening',
                      value=0, source_note='Predeclared engineering control; no professional repair layer.')
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / 'baseline'
            controlled = Path(temporary) / 'controlled'
            run_recorded(load_scenario(PROFILE), baseline, inputs=schedule, duration_s=2, step_s=.5)
            record = replay_attempt(baseline, controlled, action_commands=[action])
            first, second = read_attempt(baseline), read_attempt(controlled)
            self.assertEqual(record['status'], 'COMPLETED', record['failure'])
            self.assertEqual(record['replay_of']['mode'], 'PAIRED_EXOGENOUS_NEW_ENGINEERING_COMMANDS')
            self.assertEqual(first['inputs']['exogenous_events'], second['inputs']['exogenous_events'])
            self.assertEqual(first['run']['summary']['demand_service_unit_s'], 2)
            self.assertEqual(second['run']['summary']['demand_service_unit_s'], 2)
            self.assertEqual(first['run']['summary']['delivered_service_unit_s'], 2)
            # V6 samples at t=0,1,2: the .25s closure trips at t=1.
            self.assertEqual(second['run']['summary']['delivered_service_unit_s'], 1)
            at_close = next(row['domains'] for row in second['run']['trace'] if row['time_s'] == .25)
            self.assertEqual(at_close['facility_cooling']['internal_mass_flow_kg_s'], 0)
            self.assertNotEqual(first['run']['trace'][-1]['domains']['equipment_environment'],
                                second['run']['trace'][-1]['domains']['equipment_environment'])
            command = next(row for row in second['run']['events'] if row.get('id') == action['id'])
            self.assertEqual(command['kind'], 'engineering_control_command')
            self.assertEqual(len([row for row in second['run']['events']
                                  if row['kind'] == 'exogenous_boundary_input']), 2)

    def test_failed_physical_attempt_is_preserved_and_retry_is_an_explicit_new_attempt(self):
        from aegis_dc.replay import read_attempt, replay_attempt, run_recorded
        scenario = load_scenario(PROFILE)
        for parameter in scenario['parameters']:
            if parameter['id'] in {'internal_hot_mass', 'minimum_internal_hot_mass', 'internal_hot_leak_mass_flow'}:
                parameter['value'] = {'internal_hot_mass': 1000, 'minimum_internal_hot_mass': 999,
                                      'internal_hot_leak_mass_flow': 2}[parameter['id']]
        with tempfile.TemporaryDirectory() as temporary:
            failed, retry = Path(temporary) / 'failed', Path(temporary) / 'retry'
            record = run_recorded(scenario, failed, inputs=frozen_inputs(), duration_s=1, step_s=1)
            original = (failed / 'attempt.json').read_bytes()
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['failure']['stage'], 'simulate_scenario')
            self.assertIn('hydraulic validity minimum', record['failure']['message'])
            self.assertIsNone(read_attempt(failed)['run'])
            reexecuted = replay_attempt(failed, Path(temporary) / 'implicit-retry')
            self.assertEqual(reexecuted['status'], 'FAILED')
            self.assertIn('explicit retry', reexecuted['failure']['message'])
            retried = run_recorded(scenario, retry, inputs=frozen_inputs(), duration_s=1, step_s=1,
                                   retry_of=failed, retry_reason='Confirm unchanged hydraulic-domain refusal once.')
            self.assertEqual(retried['status'], 'FAILED')
            self.assertEqual(retried['retry_of']['attempt_id'], record['attempt_id'])
            self.assertEqual(retried['retry_of']['attempt_sha256'], read_attempt(failed)['record_sha256'])
            self.assertEqual((failed / 'attempt.json').read_bytes(), original)
            self.assertEqual(retried['research_trials'], 0)
            self.assertEqual([json.loads(line)['state'] for line in (retry / 'lifecycle.jsonl').read_text().splitlines()],
                             ['STARTED', 'FAILED'])

    def test_changed_execution_source_is_refused_as_a_recorded_replay_failure(self):
        from aegis_dc.replay import read_attempt, replay_attempt, run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            original, replayed = Path(temporary) / 'original', Path(temporary) / 'source-refused'
            run_recorded(load_scenario(PROFILE), original, inputs=frozen_inputs(), duration_s=1)
            source = json.loads((original / 'attempt.json').read_text())
            source['source_identity']['python']['version'] = 'an explicitly different interpreter'
            (original / 'attempt.json').write_text(json.dumps(source), encoding='utf-8')
            refused = replay_attempt(original, replayed)
            self.assertEqual(refused['status'], 'FAILED')
            self.assertIn('source mismatch', refused['failure']['message'])
            self.assertIsNone(read_attempt(replayed)['run'])

    def test_extra_or_changed_durable_artifacts_cannot_be_read_as_verified_replay(self):
        from aegis_dc.replay import read_attempt, run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'original'
            run_recorded(load_scenario(PROFILE), directory, inputs=frozen_inputs(), duration_s=1)
            (directory / 'unlisted-result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'durable'):
                read_attempt(directory)

    def test_research_requests_fail_closed_before_an_authorized_protocol_exists(self):
        from aegis_dc.replay import read_attempt, run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'not-a-research-trial'
            record = run_recorded(load_scenario(PROFILE), output, inputs=frozen_inputs(), duration_s=1,
                                  attempt_kind='registered_research',
                                  research_registration={'protocol': 'unopened-protocol', 'budget': 1})
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['failure']['stage'], 'attempt_classification')
            self.assertIn('ticket 30', record['failure']['message'])
            self.assertEqual(record['research_trials'], 0)
            self.assertIsNone(read_attempt(output)['run'])

    def test_actual_CLI_records_replays_and_refuses_overwrite_without_touching_original(self):
        from aegis_dc.replay import read_attempt
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            inputs = folder / 'inputs.json'
            inputs.write_text(json.dumps(frozen_inputs()), encoding='utf-8')
            original, replayed = folder / 'cli-original', folder / 'cli-replayed'
            command = [sys.executable, '-Xutf8', '-m', 'aegis_dc', 'record', '--model', str(PROFILE),
                       '--inputs', str(inputs), '--output', str(original), '--duration', '1', '--step', '.25']
            completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(completed.stdout)
            self.assertEqual(record['status'], 'COMPLETED')
            before = {path.relative_to(original).as_posix(): path.read_bytes()
                      for path in original.rglob('*') if path.is_file()}
            replay = subprocess.run([sys.executable, '-Xutf8', '-m', 'aegis_dc', 'replay',
                                     '--attempt', str(original), '--output', str(replayed)],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(read_attempt(original)['run']['trace'], read_attempt(replayed)['run']['trace'])
            refused = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('exists', refused.stderr)
            self.assertEqual(before, {path.relative_to(original).as_posix(): path.read_bytes()
                                      for path in original.rglob('*') if path.is_file()})

    def test_equal_time_work_order_is_canonical_and_not_caller_list_order(self):
        from aegis_dc.replay import read_attempt, run_recorded
        requests = [dict(id=identifier, time_s=.25, worker_id='worker_cooling',
                         work_interface_id='inspect_facility_cooling', target_id='intake_pump',
                         source_note='Competing finite engineering work records; no repair.')
                    for identifier in ('z-last', 'a-first')]
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / 'first', Path(temporary) / 'second'
            for directory, rows in ((first, requests), (second, list(reversed(requests)))):
                run_recorded(load_scenario(PROFILE), directory,
                             inputs=frozen_inputs(work_requests=rows), duration_s=1)
            one, two = read_attempt(first), read_attempt(second)
            self.assertEqual([row['id'] for row in one['inputs']['work_requests']], ['a-first', 'z-last'])
            self.assertEqual(one['inputs'], two['inputs'])
            self.assertEqual(one['run']['work_records'], two['run']['work_records'])
            self.assertEqual(one['run']['work_records'][0]['id'], 'a-first')
            self.assertEqual(one['run']['work_records'][1]['reason'], 'worker_busy')

    def test_command_authority_and_coincident_conflicts_fail_before_simulation(self):
        from aegis_dc.replay import run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            for index, parameter in enumerate(('service_demand', 'lake_temperature', 'filter_resistance_multiplier')):
                record = run_recorded(load_scenario(PROFILE), Path(temporary) / ('forbidden-' + str(index)),
                                      inputs=frozen_inputs(action_commands=[dict(id='bad', time_s=.25,
                                      parameter_id=parameter, value=0, source_note='Invalid engineer authority.')]), duration_s=1)
                self.assertEqual(record['status'], 'FAILED')
                self.assertIn('cannot write offered demand', record['failure']['message'])
            commands = [dict(id=str(index), time_s=.25 + index * math.ulp(.25),
                             parameter_id='internal_valve_opening', value=value,
                             source_note='Numerically coincident conflicting commands.')
                        for index, value in enumerate((0, 1))]
            conflict = run_recorded(load_scenario(PROFILE), Path(temporary) / 'conflict',
                                    inputs=frozen_inputs(action_commands=commands), duration_s=1)
            self.assertEqual(conflict['status'], 'FAILED')
            self.assertIn('Conflicting engineering command', conflict['failure']['message'])

    def test_unfinalized_attempt_is_unknown_and_cannot_be_replayed_as_success(self):
        from aegis_dc.replay import read_attempt, replay_attempt
        with tempfile.TemporaryDirectory() as temporary:
            interrupted = Path(temporary) / 'unfinalized'
            interrupted.mkdir()
            (interrupted / 'lifecycle.jsonl').write_text('{"state":"STARTED","attempt_id":"interrupted"}\n')
            state = read_attempt(interrupted)
            self.assertEqual(state['record']['status'], 'UNFINALIZED_RUNNING_OR_INTERRUPTED')
            self.assertIsNone(state['run'])
            refused = replay_attempt(interrupted, Path(temporary) / 'refused')
            self.assertEqual(refused['status'], 'FAILED')
            self.assertIn('unfinalized', refused['failure']['message'].lower())

    def test_invalid_submitted_JSON_is_retained_in_a_failed_CLI_attempt(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad_input = folder / 'duplicate-keys.json'
            raw = b'{"schema":"first","schema":"second"}\n'
            bad_input.write_bytes(raw)
            output = folder / 'invalid-input'
            result = subprocess.run([sys.executable, '-Xutf8', '-m', 'aegis_dc', 'record',
                                     '--inputs', str(bad_input), '--output', str(output), '--duration', '1'],
                                    cwd=ROOT, env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'FAILED')
            self.assertEqual((output / 'submitted-inputs.json').read_bytes(), raw)
            self.assertIn('Duplicate JSON object key', json.loads(result.stdout)['failure']['message'])

    def test_attempt_declares_durable_roles_before_hashing_and_does_not_deliver_caches(self):
        from aegis_dc.replay import read_attempt, run_recorded
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'declared'
            run_recorded(load_scenario(PROFILE), output, inputs=frozen_inputs(), duration_s=1)
            declaration = json.loads((output / 'declaration.json').read_text())
            record = read_attempt(output)['record']
            self.assertEqual(declaration['schema'], 'aegisdc-attempt-declaration-v1')
            self.assertEqual(set(record['artifacts']), set(declaration['required_when_completed']))
            self.assertEqual(declaration['runtime_caches'], 'NOT_DELIVERABLE')
            self.assertNotIn('attempt.json', record['artifacts'])


if __name__ == '__main__':
    unittest.main()
