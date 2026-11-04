"""Versioned full-facility replay through recorded-run/read/replay and CLI seams."""
from pathlib import Path
import json
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


if __name__ == '__main__':
    unittest.main()
