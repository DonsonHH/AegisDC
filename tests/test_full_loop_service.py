"""Actual sampled service evidence at the public facility run interface."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from aegis_dc.plant import save_run, simulate_scenario
from aegis_dc.sensor_channels import validate_channel_profile


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'evidence/mainline/engineering/25-baselines/reference/no-human.json'


def service_fixture():
    """New short engineering inputs; the sealed 25 reference is read only."""
    original = json.loads(REFERENCE.read_bytes())
    model, program = original['model'], original['dispatch_program']
    for row in model['parameters']:
        if row['id'] in {'compute_demand_power', 'service_demand', 'network_service_capacity',
                         'filter_resistance_multiplier'}:
            row['value'] = {'compute_demand_power': 1_000_000, 'service_demand': .5,
                'network_service_capacity': 1, 'filter_resistance_multiplier': 1}[row['id']]
    program['id'] = 'service27-actual-sampling-development'
    program['decision_times_s'] = [0, .125, .25, .625, .75, 1.125, 1.25]
    sensor = program['sensor_program']
    profile, realization = sensor['profile'], sensor['realization']
    meter = 'service-meter'
    profile['ledger']['observables'].append(dict(id='service_delivered_rate', quantity='service_capacity',
        value_type='number', unit='1'))
    profile['ledger']['sources'].append(dict(id=meter + '-record', kind='fixed_sensor', basis='synthetic_assumption',
        target_ids=['critical_service'], observable_ids=['service_delivered_rate'], dependency_group=None,
        source_note='Declared instrument for actual normalized delivered rate, not a demand ratio.'))
    profile['measurements'].append(dict(id=meter, signal='joint_service_delivered', target_id='critical_service',
        period_s=.5, phase_s=0, enabled=True, input_range=[.25, 1], declared_bias_bound=0,
        declared_noise_bound=0, quantization_bound=0, declared_dropout_probability=0, calibration_group=None))
    profile['channels'].append(dict(id='service-rate', measurement_id=meter, source_id=meter + '-record',
        observable_id='service_delivered_rate', transform='identity', threshold=None, delay_s=.25,
        validity_s=2, quality_mode='bounded'))
    for key in ('biases', 'noise_bounds', 'dropout_probabilities'):
        realization[key][meter] = 0
    events = [dict(time_s=time, parameter_id=name, value=value, source_note='Short independent service-meter fixture.')
        for time, name, value in ((.5, 'service_demand', 1), (.5, 'compute_demand_power', 2_000_000),
                                  (1, 'network_service_capacity', 0))]
    return model, program, events


def _json_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def captured_service_run(model, program, events):
    """Preserve this new test call, including pre-integration refusal."""
    folder = ROOT / '.work/27-development' / ('service-' + uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    source_paths = sorted((ROOT / 'src').rglob('*.py'))
    support = [Path(__file__), REFERENCE, ROOT / model['runtime']['property_table']]
    pins = {}
    for path in source_paths + support:
        relative = path.relative_to(ROOT)
        snapshot = folder / 'pre-call' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        snapshot.write_bytes(raw)
        pins[relative.as_posix()] = sha256(raw).hexdigest()
    _json_new(folder / 'input.json', dict(model=model, dispatch_program=program, boundary_events=events,
        duration_s=1.25, maximum_step_s=.01))
    _json_new(folder / 'attempt.json', dict(status='STARTED', source_commit=source, source_files=pins,
        classification='DEVELOPMENT_ENGINEERING_FIXTURE_NOT_FORMAL_CAPTURE', python=sys.version,
        executable=sys.executable, executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
        started_public_run_calls=1, registered_research_trials=0))
    terminal = dict(source_commit=source, status='NO_SAVED_TRAJECTORY', integration_returned=False)
    try:
        result = simulate_scenario(model, duration_s=1.25, step_s=.01, boundary_events=events,
            dispatch_program=program)
        terminal['integration_returned'] = True
        save_run(result, folder / 'original')
        terminal.update(status='PHYSICAL_CALL_COMPLETED_NOT_TEST_ACCEPTANCE', executed_source=result['code_identity'])
        return result
    except Exception as error:
        terminal.update(status='FAILED', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        try:
            terminal['source_unchanged'] = (source == subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                cwd=ROOT, text=True).strip() and all(sha256((ROOT / name).read_bytes()).hexdigest() == digest
                for name, digest in pins.items()))
        except (OSError, subprocess.SubprocessError) as error:
            terminal.update(source_unchanged=False, source_guard_error=str(error))
        if not terminal['source_unchanged']:
            terminal.update(status='FAILED_SOURCE_GUARD')
        _json_new(folder / 'terminal.json', terminal)
        print('development_original ' + str(folder), flush=True)
        if not terminal['source_unchanged']:
            raise ValueError('Development runtime or authored inputs changed')


class FullLoopServiceTests(unittest.TestCase):
    def test_actual_delivered_rate_arrives_later_and_out_of_range_is_missing(self):
        self.check_service_result(captured_service_run(*service_fixture()))

    def check_service_result(self, result):
        # One MW per unit requested at demand 1/2 yields 1/2 MW actual, or 1/4
        # of the two MW nominal capacity. This differs from both demand and ratio.
        samples = {row['time_s']: row['domains']['it_service']['delivered'] for row in result['trace']}
        self.assertEqual([samples[t] for t in (0, .5, 1)], [.25, 1, 0])
        by_decision = []
        for row in result['policy_public_decisions']:
            records = [r for r in row['frame']['evidence']['records'] if r['source_id'] == 'service-meter-record']
            by_decision.append(records)
            self.assertTrue(all(r['arrived_at_s'] <= row['frame']['as_of_s'] for r in records))
        self.assertEqual([len(rows) for rows in by_decision], [0, 0, 1, 1, 2, 2, 3])
        final = by_decision[-1]
        self.assertEqual([(r['observed_at_s'], r['arrived_at_s'], r['value']) for r in final],
            [(0, .25, .25), (.5, .75, 1), (1, 1.25, None)])
        self.assertEqual([r['provenance']['origin_id'] for r in final], ['service-meter@0', 'service-meter@1/2', 'service-meter@1'])
        self.assertTrue(all(r['target_id'] == 'critical_service' and r['unit'] == '1' for r in final))
        self.assertEqual([r['quality']['status'] for r in final], ['bounded', 'bounded', 'unknown'])
        self.assertEqual(final[-1]['availability'], 'missing')
        self.assertEqual(result['work_records'], [])
        self.assertAlmostEqual(result['summary']['demand_service_unit_s'], 1)
        self.assertAlmostEqual(result['summary']['delivered_service_unit_s'], .625)
        self.assertAlmostEqual(result['summary']['service_deficit_time_s'], .5)

    def test_service_instrument_refuses_an_unlisted_signal_wrong_target_or_unit(self):
        for mismatch, error in (('signal', 'declared measurable whitelist'),
                               ('target', 'declared public target'), ('unit', 'unit')):
            _, program, _ = service_fixture()
            profile = program['sensor_program']['profile']
            meter = profile['measurements'][-1]
            if mismatch == 'signal':
                meter['signal'] = 'private_failure_label'
            elif mismatch == 'target':
                meter['target_id'] = 'network'
            else:
                profile['ledger']['observables'][-1]['unit'] = 'W'
            with self.subTest(mismatch=mismatch), self.assertRaisesRegex(ValueError, error):
                validate_channel_profile(profile)


if __name__ == '__main__':
    unittest.main()
