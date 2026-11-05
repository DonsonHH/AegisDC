"""Private saved-signal sampling into the public ticket-14 record contract."""
from bisect import bisect_right
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
import math

from .evidence_ledger import validate_ledger


SIGNALS = {
    'coolant_temperature': dict(target='immersion', quantity='temperature', unit='K',
        path=('equipment_environment', 'refrigerant', 'temperature_K'), reported=False),
    'controller_temperature': dict(target='local_controller', quantity='temperature', unit='K',
        path=('control_monitoring', 'local_measurement', 'temperature_K'), reported=True),
}

MEASUREMENT_FIELDS = {'id', 'signal', 'target_id', 'period_s', 'phase_s', 'enabled',
                      'input_range', 'declared_bias_bound', 'declared_noise_bound',
                      'quantization_bound', 'declared_dropout_probability', 'calibration_group'}
CHANNEL_FIELDS = {'id', 'measurement_id', 'source_id', 'observable_id', 'transform',
                  'threshold', 'delay_s', 'validity_s', 'quality_mode'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value, label):
    valid = type(value) in (int, float)
    if valid:
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
    _require(valid, label + ' must be finite numeric data, not boolean or missing')


def _plain(value, ancestors=None, depth=0):
    _require(depth < 64, 'Observation declarations must be shallow plain JSON')
    if value is None or type(value) in (str, bool):
        return
    if type(value) in (int, float):
        _finite(value, 'JSON number')
        return
    _require(type(value) in (dict, list), 'No executable objects or callbacks in observation declarations')
    ancestors = set() if ancestors is None else ancestors
    _require(id(value) not in ancestors, 'Observation declarations cannot contain cycles')
    ancestors.add(id(value))
    if type(value) is dict:
        _require(all(type(key) is str for key in value), 'Observation keys must be text')
        children = value.values()
    else:
        children = value
    for child in children:
        _plain(child, ancestors, depth + 1)
    ancestors.remove(id(value))


def _fields(value, names, label):
    _require(type(value) is dict and set(value) == names, 'Closed ' + label + ' fields required')


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), label + ' must be nonempty text')


def _registry(rows, names, label):
    _require(type(rows) is list, label + ' must be a list')
    result = {}
    for row in rows:
        _fields(row, names, label)
        _text(row['id'], label + ' id')
        _require(row['id'] not in result, 'Duplicate ' + label + ' id')
        result[row['id']] = row
    return result


def validate_channel_profile(profile):
    """Detach a public static declaration; it cannot carry a pending queue."""
    _plain(profile)
    _fields(profile, {'schema', 'ledger', 'measurements', 'channels'}, 'channel profile')
    _require(profile['schema'] == 'aegisdc-sparse-channels-v1', 'Unknown channel profile schema')
    ledger = validate_ledger(profile['ledger'])
    _require(not ledger['records'], 'The public channel registry must have an empty record queue')
    measurements = _registry(profile['measurements'], MEASUREMENT_FIELDS, 'measurement')
    sources = {row['id']: row for row in ledger['sources']}
    observables = {row['id']: row for row in ledger['observables']}
    for row in measurements.values():
        _text(row['signal'], 'Signal selector')
        _require(row['signal'] in SIGNALS, 'Signal is not in the declared measurable whitelist')
        signal = SIGNALS[row['signal']]
        _require(row['target_id'] == signal['target'] and row['target_id'] in ledger['entity_ids'],
                 'Signal and declared public target disagree')
        _require(type(row['enabled']) is bool, 'Instrument enabled is a static boolean declaration')
        for name in ('period_s', 'phase_s', 'declared_bias_bound', 'declared_noise_bound',
                     'quantization_bound', 'declared_dropout_probability'):
            _finite(row[name], name)
        _require(row['period_s'] > 0 and row['phase_s'] >= 0, 'Positive period and nonnegative phase required')
        _require(all(row[name] >= 0 for name in ('declared_bias_bound', 'declared_noise_bound', 'quantization_bound')),
                 'Declared error components must be nonnegative')
        _require(0 <= row['declared_dropout_probability'] <= 1, 'Declared dropout probability must be in [0,1]')
        bounds = row['input_range']
        _require(type(bounds) is list and len(bounds) == 2, 'Declare a finite instrument input range')
        for value in bounds:
            _finite(value, 'Instrument range')
        _require(bounds[0] <= bounds[1], 'Instrument range is reversed')
        nominal = Fraction(row['declared_bias_bound']) + Fraction(row['declared_noise_bound'])
        magnitude = max(abs(Fraction(value)) for value in bounds) + nominal
        if nominal:
            minimum_rounding = math.ulp(_number(magnitude, upward=True))
            _require(Fraction(row['quantization_bound']) >= Fraction(minimum_rounding),
                     'Declared quantization allowance must cover a full ULP over the nominal output range')
        if row['calibration_group'] is not None:
            _text(row['calibration_group'], 'Calibration dependency group')
    channels = _registry(profile['channels'], CHANNEL_FIELDS, 'channel')
    for row in channels.values():
        for name in ('measurement_id', 'source_id', 'observable_id', 'transform', 'quality_mode'):
            _text(row[name], 'Channel ' + name)
        _require(row['measurement_id'] in measurements, 'Unknown channel measurement')
        _require(row['source_id'] in sources and row['observable_id'] in observables, 'Unregistered channel source/observable')
        measurement = measurements[row['measurement_id']]
        signal = SIGNALS[measurement['signal']]
        source, observable = sources[row['source_id']], observables[row['observable_id']]
        _require(measurement['target_id'] in source['target_ids'] and row['observable_id'] in source['observable_ids'],
                 'Channel is outside static declared instrument coverage')
        _require(source['kind'] == ('control_record' if signal['reported'] else 'fixed_sensor'),
                 'Channel source kind does not match the declared signal')
        _require(source['dependency_group'] == measurement['calibration_group'], 'Declare shared calibration dependence in the source registry')
        _require(row['transform'] in {'identity', 'above', 'validity'}, 'Unknown channel transform')
        _require(row['quality_mode'] in {'bounded', 'unknown', 'reported'}, 'Unknown channel quality declaration')
        for name in ('delay_s', 'validity_s'):
            _finite(row[name], name)
        _require(row['delay_s'] >= 0 and row['validity_s'] > 0, 'Delay must be nonnegative and validity positive')
        if row['transform'] == 'identity':
            _require(observable['value_type'] == 'number' and observable['quantity'] == signal['quantity']
                     and observable['unit'] == signal['unit'], 'Signal/observable type and SI units disagree')
            _require(row['threshold'] is None and row['quality_mode'] in {'bounded', 'unknown'}, 'Numeric identity quality/threshold mismatch')
            _require(not signal['reported'] or row['quality_mode'] == 'unknown',
                     'A reported controller value is not a calibrated actual-state bound')
        else:
            _require(observable['value_type'] == 'boolean' and row['quality_mode'] in {'reported', 'unknown'}, 'Derived flags are reports, not verified numeric bounds')
            if row['transform'] == 'above':
                _finite(row['threshold'], 'Threshold in the input signal SI unit')
            else:
                _require(row['threshold'] is None, 'Validity flags have no numeric threshold')
    result = deepcopy(profile)
    result['ledger'] = ledger
    return result


def _number(exact, *, upward=False):
    try:
        result = exact.numerator if exact.denominator == 1 else float(exact)
    except OverflowError as error:
        raise ValueError('Observation number exceeds the finite output domain') from error
    if upward and Fraction(result) < exact:
        result = math.nextafter(result, math.inf)
    _finite(result, 'Derived observation number')
    return result


def public_model(profile):
    """Only the operator-declared static model, never a realized error or seed."""
    profile = validate_channel_profile(profile)
    return dict(schema='aegisdc-public-observation-model-v1',
                ledger=deepcopy(profile['ledger']),
                measurements=deepcopy(profile['measurements']),
                channels=deepcopy(profile['channels']))


def _bucket(seed, measurement, observed, kind):
    key = ['aegisdc-keyed-observation-v1', seed, measurement, str(Fraction(observed)), kind]
    raw = json.dumps(key, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return int.from_bytes(sha256(raw).digest()[:8], 'big')


def _signal(point, measurement):
    specification = SIGNALS[measurement['signal']]
    value = point['domains']
    for part in specification['path']:
        if value is None:
            return None, point['time_s'], None
        _require(type(value) is dict and part in value, 'Declared signal is absent from the private saved schema')
        value = value[part]
    observed, valid = point['time_s'], True
    if specification['reported']:
        local = point['domains']['control_monitoring']['local_measurement']
        observed, valid = local['sampled_at_s'], local['temperature_valid']
        _finite(observed, 'Reported controller sample time')
        _require(type(valid) is bool, 'Reported controller validity must be boolean')
        if observed > point['time_s']:
            raise ValueError('A controller sample cannot come from a future source point')
    if value is None:
        valid = False
    else:
        _finite(value, 'Private declared signal')
    return value, observed, valid


def _private_inputs(profile, private_trace, realization):
    _require(type(private_trace) is dict and set(private_trace) in (
        {'schema', 'facility_id', 'entity_ids', 'points'},
        {'schema', 'facility_id', 'entity_ids', 'points', 'private_metadata'}), 'Use the private saved-signal trace contract')
    _require(private_trace['schema'] == 'aegisdc-observation-private-trace-v1', 'Unknown private trace schema')
    identifiers = private_trace['entity_ids']
    _require(type(identifiers) is list and all(type(value) is str for value in identifiers)
             and len(identifiers) == len(set(identifiers)), 'Private entity IDs must be unique text')
    _require(private_trace['facility_id'] == profile['ledger']['facility_id']
             and set(identifiers) == set(profile['ledger']['entity_ids']), 'Private trace facility identity differs')
    points = private_trace['points']
    _require(type(points) is list and bool(points), 'Private trace needs saved points')
    previous = None
    for point in points:
        _require(type(point) is dict and {'time_s', 'domains'} <= set(point), 'Private saved point requires time and domains')
        _finite(point['time_s'], 'Private saved time')
        _require(previous is None or point['time_s'] > previous, 'Private saved times must be strictly increasing')
        _require(type(point['domains']) is dict, 'Private saved domains must be plain mappings')
        previous = point['time_s']
    _plain(realization)
    _fields(realization, {'schema', 'seed', 'biases', 'noise_bounds', 'dropout_probabilities'}, 'private realization')
    _require(realization['schema'] == 'aegisdc-private-observation-realization-v1', 'Unknown private realization schema')
    _require(type(realization['seed']) is int and 0 <= realization['seed'] < 1 << 64, 'Private replay seed must be an unsigned 64-bit integer')
    groups = {row['calibration_group'] or row['id'] for row in profile['measurements']}
    names = {row['id'] for row in profile['measurements']}
    for name, expected in [('biases', groups), ('noise_bounds', names), ('dropout_probabilities', names)]:
        _require(type(realization[name]) is dict and set(realization[name]) == expected,
                 'Private realization must explicitly specify every declared ' + name)
        for value in realization[name].values():
            _finite(value, 'Private ' + name)
            _require(name == 'biases' or value >= 0, 'Private scale/probability must be nonnegative')
            _require(name != 'dropout_probabilities' or value <= 1, 'Private dropout probability must be in [0,1]')


def sample_trace(profile, private_trace, realization):
    """Evaluator-only adapter; give dispatch a ledger snapshot, not this result."""
    profile = validate_channel_profile(profile)
    _private_inputs(profile, private_trace, realization)
    ledger = validate_ledger(profile['ledger'])
    points = private_trace['points']
    times = [point['time_s'] for point in points]
    channels = {measurement['id']: [] for measurement in profile['measurements']}
    for channel in profile['channels']:
        channels[channel['measurement_id']].append(channel)
    observables = {row['id']: row for row in ledger['observables']}
    audit = []
    for measurement in sorted(profile['measurements'], key=lambda row: row['id']):
        if not measurement['enabled']:
            continue
        count = max(0, int((Fraction(times[-1]) - Fraction(measurement['phase_s'])) // Fraction(measurement['period_s'])) + 1)
        _require(count <= 1000000, 'Observation polling schedule exceeds the declared finite adapter budget')
        counter = 0
        while True:
            polled = _number(Fraction(measurement['phase_s']) + counter * Fraction(measurement['period_s']))
            if polled > times[-1]:
                break
            point_index = bisect_right(times, polled) - 1
            if point_index >= 0:
                point = points[point_index]
                signal, observed, valid = _signal(point, measurement)
                usable = (valid and signal is not None
                          and measurement['input_range'][0] <= signal <= measurement['input_range'][1])
                calibration = measurement['calibration_group'] or measurement['id']
                bias = realization['biases'][calibration]
                noise_bound = realization['noise_bounds'][measurement['id']]
                bucket = _bucket(realization['seed'], measurement['id'], observed, 'bounded-error')
                denominator = (1 << 64) - 1
                noise = Fraction(2 * bucket - denominator, denominator) * Fraction(noise_bound)
                measured = _number(Fraction(signal) + Fraction(bias) + noise) if signal is not None else None
                availability_bucket = _bucket(realization['seed'], measurement['id'], observed, 'reading-availability')
                dropout = Fraction(availability_bucket, 1 << 64) < Fraction(
                    realization['dropout_probabilities'][measurement['id']])
                origin = measurement['id'] + '@' + str(Fraction(observed))
                bound = _number(Fraction(measurement['declared_bias_bound'])
                                + Fraction(measurement['declared_noise_bound'])
                                + Fraction(measurement['quantization_bound']), upward=True)
                for channel in sorted(channels[measurement['id']], key=lambda row: row['id']):
                    value = valid if channel['transform'] == 'validity' else measured if usable else None
                    if channel['transform'] == 'above' and value is not None:
                        value = value > channel['threshold']
                    if dropout:
                        value = None
                    quality = (dict(status='unknown', error_bound=None,
                                    note='No reading available from this declared channel.') if value is None else
                               dict(status=channel['quality_mode'],
                                    error_bound=bound if channel['quality_mode'] == 'bounded' else None,
                                    note='Static declared instrument quality; synthetic assumption, not verified against private truth.'))
                    ledger['records'].append(dict(
                        id=channel['id'] + ':' + str(counter), source_id=channel['source_id'],
                        target_id=measurement['target_id'], observable_id=channel['observable_id'],
                        unit=observables[channel['observable_id']]['unit'], value=value,
                        observed_at_s=observed,
                        arrived_at_s=_number(Fraction(polled) + Fraction(channel['delay_s']), upward=True),
                        valid_until_s=_number(Fraction(observed) + Fraction(channel['validity_s']), upward=True),
                        quality=quality,
                        provenance=dict(origin_id=origin, copied_from_record_id=None)))
                audit.append(dict(measurement_id=measurement['id'], poll_index=counter,
                                  polled_at_s=polled, source_observed_at_s=observed,
                                  private_signal=signal, private_bias=bias,
                                  private_noise_bucket=bucket, private_noise_bound=noise_bound,
                                  private_reading_dropout=dropout,
                                  declared_bound_violated=(abs(Fraction(measured) - Fraction(signal)) > Fraction(bound)
                                                           if measured is not None and usable and not dropout else None)))
            counter += 1
    return dict(schema='aegisdc-private-observation-production-v1',
                state_visibility='PRIVATE_EVALUATOR_ONLY', ledger=validate_ledger(ledger),
                public_model=public_model(profile), private_audit=audit)
