"""Author a static sparse-channel declaration from V6 identity only."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aegis_dc.sensor_channels import validate_channel_profile


def build():
    identity = json.loads((ROOT / 'configs/full-facility-mainline-reserve-v6.json').read_text(encoding='utf-8'))
    ledger = dict(schema='aegisdc-evidence-ledger-v1', id='V6-sparse-fixed-evidence-v1',
        facility_id=identity['id'], basis='synthetic_assumption', time_unit='s',
        entity_ids=[row['id'] for row in identity['entities']], observables=[], sources=[], records=[])
    for identifier, quantity, kind, unit in [
            ('coolant_temperature', 'temperature', 'number', 'K'),
            ('coolant_hot_reported', 'binary', 'boolean', '1'),
            ('lake_mass_flow', 'mass_flow', 'number', 'kg/s'),
            ('rectifier_input_power', 'power', 'number', 'W'),
            ('controller_reported_temperature', 'temperature', 'number', 'K'),
            ('controller_reported_validity', 'binary', 'boolean', '1')]:
        ledger['observables'].append(dict(id=identifier, quantity=quantity, value_type=kind, unit=unit))
    for identifier, kind, target, observables, group in [
            ('coolant-probe-record', 'fixed_sensor', 'immersion', ['coolant_temperature'], 'coolant-calibration'),
            ('coolant-alarm-packet', 'fixed_sensor', 'immersion', ['coolant_hot_reported'], 'coolant-calibration'),
            ('intake-flow-record', 'fixed_sensor', 'intake_pump', ['lake_mass_flow'], None),
            ('rectifier-meter-record', 'fixed_sensor', 'rectifier', ['rectifier_input_power'], None),
            ('controller-log-record', 'control_record', 'local_controller',
             ['controller_reported_temperature', 'controller_reported_validity'], None)]:
        ledger['sources'].append(dict(id=identifier, kind=kind, basis='synthetic_assumption',
            target_ids=[target], observable_ids=observables, dependency_group=group,
            source_note='Static declared observation performance; realized errors and private state are not calibration claims.'))
    measurements = []
    for identifier, signal, target, period, bounds, bias, noise, quantization, dropout, group in [
            ('coolant-probe', 'coolant_temperature', 'immersion', 1, [270, 350], .5, .25, 1e-9, .05, 'coolant-calibration'),
            ('lake-flow', 'lake_mass_flow', 'intake_pump', 2, [0, 1000], .02, .05, 1e-9, .1, None),
            ('rectifier-meter', 'rectifier_input_power', 'rectifier', 5, [0, 10000000], 50, 100, 1e-6, 0, None),
            ('local-temperature-report', 'controller_temperature', 'local_controller', 1, [250, 360], 0, 0, 0, 0, None)]:
        measurements.append(dict(id=identifier, signal=signal, target_id=target,
            period_s=period, phase_s=0, enabled=True, input_range=bounds,
            declared_bias_bound=bias, declared_noise_bound=noise, quantization_bound=quantization,
            declared_dropout_probability=dropout, calibration_group=group))
    channels = []
    for identifier, measurement, source, observable, transform, threshold, delay, validity, quality in [
            ('coolant-transfer', 'coolant-probe', 'coolant-probe-record', 'coolant_temperature', 'identity', None, 2, 4, 'bounded'),
            ('coolant-alarm-transfer', 'coolant-probe', 'coolant-alarm-packet', 'coolant_hot_reported', 'above', 305, 1, 4, 'reported'),
            ('flow-transfer', 'lake-flow', 'intake-flow-record', 'lake_mass_flow', 'identity', None, 3, 5, 'bounded'),
            ('power-transfer', 'rectifier-meter', 'rectifier-meter-record', 'rectifier_input_power', 'identity', None, .5, 6, 'bounded'),
            ('controller-temperature-transfer', 'local-temperature-report', 'controller-log-record',
             'controller_reported_temperature', 'identity', None, .5, 2, 'unknown'),
            ('controller-validity-transfer', 'local-temperature-report', 'controller-log-record',
             'controller_reported_validity', 'validity', None, .5, 2, 'reported')]:
        channels.append(dict(id=identifier, measurement_id=measurement, source_id=source,
            observable_id=observable, transform=transform, threshold=threshold,
            delay_s=delay, validity_s=validity, quality_mode=quality))
    return validate_channel_profile(dict(schema='aegisdc-sparse-channels-v1', ledger=ledger,
                                         measurements=measurements, channels=channels))


def realization():
    return dict(schema='aegisdc-private-observation-realization-v1', seed=42,
        biases={'coolant-calibration': .2, 'lake-flow': .01, 'rectifier-meter': 25, 'local-temperature-report': 0},
        noise_bounds={'coolant-probe': .25, 'lake-flow': .03, 'rectifier-meter': 50, 'local-temperature-report': 0},
        dropout_probabilities={'coolant-probe': .05, 'lake-flow': .1, 'rectifier-meter': 0, 'local-temperature-report': 0})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--private-realization', type=Path, required=True)
    args = parser.parse_args()
    for path, value in [(args.profile, build()), (args.private_realization, realization())]:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
