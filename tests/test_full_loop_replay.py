"""The recorded run interface recomputes online work from frozen inputs."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import subprocess
import unittest
from uuid import uuid4

from aegis_dc.replay import read_attempt, replay_attempt, run_recorded
from test_full_loop_service import REFERENCE, ROOT, _json_new, service_fixture


def online_replay_fixture():
    model, dispatch, events = service_fixture()
    parameters = {row['id']: row for row in model['parameters']}
    parameters['filter_resistance_multiplier']['value'] = 4
    parameters['pump_min_speed']['value'] = 1
    dispatch['id'] = 'recorded-online-cleaning-27-development'
    dispatch['decision_times_s'] = [0, .25, .75, 1.25, 1.75]
    policy = dispatch['policy_program']
    policy['policy'] = 'fifo'
    policy['candidates'] = [row for row in policy['candidates'] if row['kind'] == 'intervene']
    actions = dispatch['intervention_program']
    actions['profile']['operations'][0].update(id='clean-filter-engineering',
        source_note='Named authorized cleaning in a short recorded-run engineering fixture.')
    actions['profile']['authorizations'][0]['operation_ids'] = ['clean-filter-engineering']
    actions['bindings'][0].update(operation_id='clean-filter-engineering', setting=1)
    policy['intervention_declaration'] = deepcopy(actions)
    dispatch['inspection_program'] = None
    return model, dict(schema='aegisdc-facility-replay-inputs-v2', seed=27,
        exogenous_events=events, action_commands=[], work_requests=[], dispatch_program=dispatch)


def start_development_attempt(model, inputs, label):
    folder = ROOT / '.work/27-replay-development' / (label + '-' + uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    paths = [*sorted((ROOT / 'src').rglob('*.py')), Path(__file__), ROOT / 'tests/test_full_loop_service.py',
             REFERENCE, ROOT / model['runtime']['property_table']]
    pins = {}
    for path in paths:
        relative = path.relative_to(ROOT)
        snapshot = folder / 'pre-call' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        snapshot.write_bytes(raw)
        pins[relative.as_posix()] = sha256(raw).hexdigest()
    _json_new(folder / 'input.json', dict(model=model, replay_inputs=inputs, duration_s=1.75, maximum_step_s=.01))
    _json_new(folder / 'development-attempt.json', dict(status='STARTED', source_files=pins,
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        classification='DEVELOPMENT_ENGINEERING_REPLAY_NOT_FORMAL_CAPTURE_OR_EFFECT_TRIAL',
        operation=label, registered_research_trials=0))
    print('development_original ' + str(folder), flush=True)
    return folder / 'recorded'


class FullLoopReplayTests(unittest.TestCase):
    def test_recorded_online_dispatch_reexecutes_the_named_effect_and_arrived_records(self):
        model, inputs = online_replay_fixture()
        original = start_development_attempt(model, inputs, 'record')
        attempt = run_recorded(model, original, inputs=inputs, duration_s=1.75, step_s=.01)
        self.assertEqual(attempt['status'], 'COMPLETED', attempt.get('failure'))
        before = read_attempt(original)
        self.assertEqual(before['inputs']['dispatch_program'], inputs['dispatch_program'])
        self.assertEqual(before['run']['inputs']['dispatch_program'], inputs['dispatch_program'])
        self.assertEqual(before['run']['inputs']['action_commands'] if 'action_commands' in before['run']['inputs'] else [], [])
        self.assertEqual(before['run']['inputs']['work_requests'], [])
        self.assertEqual([d['choice']['chosen_candidate_id'] for d in before['run']['policy_public_decisions']],
            ['first-action', None, None, None, None])
        effect = before['run']['intervention_private_audit']['events'][0]
        self.assertEqual((effect['parameter_id'], effect['applied_at_s'], effect['old_value'], effect['new_value']),
            ('filter_resistance_multiplier', 1.25, 4, 1))
        self.assertEqual(before['run']['intervention_public_feedback'][0]['arrived_at_s'], 1.75)
        self.assertFalse(before['run']['intervention_public_feedback'][0]['risk_closed'])
        at_completion = next(row for row in before['run']['trace'] if row['time_s'] == 1.25)
        self.assertAlmostEqual(at_completion['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'], .1)
        replay = start_development_attempt(model, before['inputs'], 'replay')
        rerun = replay_attempt(original, replay)
        self.assertEqual(rerun['status'], 'COMPLETED', rerun.get('failure'))
        after = read_attempt(replay)
        self.assertEqual(after['inputs'], before['inputs'])
        self.assertEqual(rerun['replay_of']['attempt_sha256'], before['record_sha256'])
        # Exempt only diagnostic wall time. Every model count, decision,
        # provenance record, effect, physical point and balance still compares.
        compared = [deepcopy(saved['run']) for saved in (before, after)]
        for run in compared:
            for row in run['policy_computation_audit']:
                self.assertGreaterEqual(row.pop('elapsed_ns'), 0)
        self.assertEqual(*compared)
        self.assertEqual(read_attempt(original)['record_sha256'], before['record_sha256'])


if __name__ == '__main__':
    unittest.main()
