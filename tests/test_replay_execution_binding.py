"""Public stored-execution identity and interval-time consistency boundaries."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from aegis_dc.replay import AttemptReadError, read_attempt, replay_attempt
from aegis_dc.scenario import load_scenario
from aegis_dc.replay import run_recorded

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'evidence/mainline/engineering/13-replay/capture-04/causal-baseline'


def replace_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8', newline='\n')


def rehash(folder, name):
    record = json.loads((folder / 'attempt.json').read_text(encoding='utf-8'))
    record['artifacts'][name] = sha256((folder / name).read_bytes()).hexdigest()
    replace_json(folder / 'attempt.json', record)


def replace_balances(folder, rows):
    path = folder / 'trajectory/balances.jsonl'
    path.write_text(''.join(json.dumps(row, allow_nan=True) + '\n' for row in rows), encoding='utf-8', newline='\n')
    inner = folder / 'trajectory/run.json'
    manifest = json.loads(inner.read_text(encoding='utf-8'))
    manifest['artifacts']['balances.jsonl']['sha256'] = sha256(path.read_bytes()).hexdigest()
    replace_json(inner, manifest)
    rehash(folder, 'trajectory/balances.jsonl')
    rehash(folder, 'trajectory/run.json')


class ExecutionBindingTests(unittest.TestCase):
    def test_different_request_duration_or_step_cannot_change_a_frozen_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, (name, value) in enumerate((('duration_s', 3), ('maximum_step_s', .25),
                                                   ('duration_s', None), ('maximum_step_s', None))):
                with self.subTest(parameter=name):
                    folder = Path(temporary) / (str(index) + name)
                    shutil.copytree(ORIGINAL, folder)
                    path = folder / 'request.json'
                    request = json.loads(path.read_text(encoding='utf-8'))
                    request[name] = value
                    replace_json(path, request)
                    rehash(folder, 'request.json')
                    with self.assertRaises(AttemptReadError) as refused:
                        read_attempt(folder)
                    self.assertEqual((refused.exception.stage, refused.exception.artifact), ('request', 'request.json'))
                    output = Path(temporary) / (str(index) + name + '-refused')
                    record = replay_attempt(folder, output)
                    self.assertEqual(record['status'], 'FAILED')
                    self.assertEqual(record['execution_kind'], 'NOT_STARTED')
                    self.assertEqual(record['failure']['stage'], 'replay_origin.request')
                    self.assertEqual((output / 'origin/request.json').read_bytes(), path.read_bytes())

    def test_none_parameters_resolve_frozen_defaults_and_replay_validated_actual_values(self):
        scenario = load_scenario(ROOT / 'configs/full-facility-mainline-reserve-v6.json')
        for row in scenario['parameters']:
            if row['id'] in {'duration', 'step_time'}:
                row['value'] = {'duration': 3, 'step_time': .25}[row['id']]
        frozen = dict(schema='aegisdc-facility-replay-inputs-v1', seed=1301,
                      exogenous_events=[], action_commands=[], work_requests=[])
        with tempfile.TemporaryDirectory() as temporary:
            origin, repeated = Path(temporary) / 'default', Path(temporary) / 'replayed'
            run_recorded(scenario, origin, inputs=frozen)
            one = read_attempt(origin)
            self.assertIsNone(one['request']['duration_s'])
            self.assertIsNone(one['request']['maximum_step_s'])
            self.assertEqual(one['execution_inputs'], dict(duration_s=3, maximum_step_s=.25))
            self.assertEqual(replay_attempt(origin, repeated)['status'], 'COMPLETED')
            two = read_attempt(repeated)
            self.assertEqual(two['request']['duration_s'], 3)
            self.assertEqual(two['request']['maximum_step_s'], .25)
            for name in ('trace', 'balances', 'events', 'inputs', 'summary'):
                self.assertEqual(one['run'][name], two['run'][name])

    def test_balance_times_are_finite_numeric_positive_intervals_and_a_consistent_partition(self):
        mutations = ('string', 'boolean', 'nonfinite', 'reversed', 'zero_interval', 'gap', 'overlap', 'wrong_end')
        with tempfile.TemporaryDirectory() as temporary:
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    folder = Path(temporary) / mutation
                    shutil.copytree(ORIGINAL, folder)
                    rows = [json.loads(line) for line in (folder / 'trajectory/balances.jsonl').read_text().splitlines()]
                    if mutation in {'string', 'boolean', 'nonfinite'}:
                        rows[0]['start_s'] = {'string': 'not-a-time', 'boolean': False, 'nonfinite': float('inf')}[mutation]
                    elif mutation == 'reversed':
                        rows[0]['end_s'] = -1
                    elif mutation == 'zero_interval':
                        rows[0]['end_s'] = rows[0]['start_s']
                    elif mutation in {'gap', 'overlap'}:
                        rows[1]['start_s'] = rows[0]['end_s'] + (.01 if mutation == 'gap' else -.01)
                    else:
                        rows[-1]['end_s'] += .1
                    replace_balances(folder, rows)
                    with self.assertRaises(AttemptReadError) as refused:
                        read_attempt(folder)
                    self.assertEqual((refused.exception.stage, refused.exception.artifact),
                                     ('trajectory_balances', 'trajectory/balances.jsonl'))

    def test_balance_partition_cannot_exceed_a_coherently_declared_maximum_step(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'wrong-step'
            shutil.copytree(ORIGINAL, folder)
            request = json.loads((folder / 'request.json').read_text())
            request['maximum_step_s'] = .1
            replace_json(folder / 'request.json', request)
            manifest = json.loads((folder / 'trajectory/run.json').read_text())
            manifest['inputs']['maximum_step_s'] = .1
            replace_json(folder / 'trajectory/run.json', manifest)
            record = json.loads((folder / 'attempt.json').read_text())
            record['maximum_step_s'] = .1
            for name in ('request.json', 'trajectory/run.json'):
                record['artifacts'][name] = sha256((folder / name).read_bytes()).hexdigest()
            replace_json(folder / 'attempt.json', record)
            with self.assertRaises(AttemptReadError) as refused:
                read_attempt(folder)
            self.assertEqual(refused.exception.stage, 'trajectory_balances')

    def test_valid_historical_v1_and_v2_partitions_remain_readable(self):
        for package in ('capture-01', 'capture-02', 'capture-04'):
            for name in ('normal-600s', 'combined-episode-CLI', 'causal-baseline'):
                with self.subTest(package=package, case=name):
                    result = read_attempt(ROOT / 'evidence/mainline/engineering/13-replay' / package / name)
                    self.assertEqual(result['record']['status'], 'COMPLETED')
                    self.assertEqual(result['run']['balances'][0]['start_s'], 0)
                    self.assertEqual(result['run']['balances'][-1]['end_s'], result['execution_inputs']['duration_s'])


if __name__ == '__main__':
    unittest.main()
