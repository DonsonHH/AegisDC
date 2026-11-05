"""Declared nonfixed records; private completion sampling is a separate boundary."""
import math
import json
from hashlib import sha256
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from patrol_rsi.contracts import strict_json, digest
from .evidence_ledger import validate_ledger

REPORT_KINDS = {
    'asset_record': 'HISTORICAL_CONTEXT_ONLY',
    'maintenance_history': 'HISTORICAL_CONTEXT_ONLY',
    'human_report': 'DECLARED_UNCONFIRMED_CLAIM',
    'work_order': 'DECLARED_OR_COPIED_CLAIM',
}


def _finite(value, label):
    valid = type(value) in (int, float)
    if valid:
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
    if not valid:
        raise ValueError(label + ' requires a finite decoded number, not boolean/null')
    return value


def _plain(value, ancestors=None, depth=0):
    if depth >= 64:
        raise ValueError('Producer inputs exceed the declared plain-JSON depth')
    if value is None or type(value) in (str, bool):
        return
    if type(value) in (int, float):
        _finite(value, 'JSON number')
        return
    if type(value) not in (dict, list):
        raise ValueError('Producer inputs are plain JSON, not objects/callbacks')
    ancestors = set() if ancestors is None else ancestors
    if id(value) in ancestors:
        raise ValueError('Producer inputs cannot contain cycles')
    ancestors.add(id(value))
    if type(value) is dict:
        if not all(type(k) is str for k in value):
            raise ValueError('Producer JSON keys must be text')
        children = value.values()
    else:
        children = value
    for child in children:
        _plain(child, ancestors, depth + 1)
    ancestors.remove(id(value))


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise ValueError(name + ' must be nonempty text')


def _completion(value):
    _plain(value)
    expected = {'schema', 'origin', 'id', 'source_id', 'target_id', 'observable_id', 'instrument_id',
        'qualification_declared', 'planned_started_at_s', 'planned_completed_at_s', 'started_at_s',
        'completed_at_s', 'status', 'coverage', 'arrival_latency_s', 'valid_until_s', 'provenance', 'basis', 'source_note'}
    if type(value) is not dict or set(value) != expected or value['schema'] != 'aegisdc-producer-completion-v1' \
            or value['origin'] != 'DECLARED_PRODUCER_FIXTURE' or value['basis'] != 'synthetic_assumption':
        raise ValueError('Use a typed declared producer completion, never an M1 engineering work record')
    for name in ('id', 'source_id', 'target_id', 'observable_id', 'instrument_id', 'source_note'):
        _text(value[name], name)
    if type(value['qualification_declared']) is not bool or value['status'] not in {'COMPLETED', 'INCOMPLETE', 'ABORTED', 'REJECTED'}:
        raise ValueError('Completion status/declared qualification must be explicit')
    for name in ('planned_started_at_s', 'planned_completed_at_s', 'started_at_s', 'arrival_latency_s'):
        if _finite(value[name], name) < 0:
            raise ValueError('Completion times/latency must be nonnegative')
    if value['planned_completed_at_s'] <= value['planned_started_at_s']:
        raise ValueError('Planned observation interval must be positive')
    if value['completed_at_s'] is not None:
        _finite(value['completed_at_s'], 'Effective completion')
    if value['status'] == 'COMPLETED' and (value['completed_at_s'] is None or value['completed_at_s'] <= value['started_at_s']):
        raise ValueError('Successful producer completion requires a positive actual observation interval')
    if type(value['coverage']) is not list:
        raise ValueError('Declare measured coverage')
    for row in value['coverage']:
        if type(row) is not dict or set(row) != {'target_id', 'observable_id'}:
            raise ValueError('Coverage entries name one target/observable')
        for name in row:
            _text(row[name], name)
    if type(value['provenance']) is not dict or set(value['provenance']) != {'origin_id', 'copied_from_record_id'}:
        raise ValueError('Carry explicit provenance, not a private origin lookup')
    _text(value['provenance']['origin_id'], 'Reported origin')
    if value['provenance']['copied_from_record_id'] is not None:
        _text(value['provenance']['copied_from_record_id'], 'Carried copy reference')
    return value


def _arrival(completed, latency):
    exact = Fraction(completed) + Fraction(latency)
    if exact.denominator == 1:
        result = exact.numerator
    else:
        result = float(exact)
        if Fraction(result) < exact:
            result = math.nextafter(result, math.inf)
    return _finite(result, 'Representable non-early arrival')


SIGNALS = {
    'immersion.coolant_temperature': ('immersion', 'K', ('equipment_environment', 'refrigerant', 'temperature_K')),
    'internal_pump.volume_flow': ('internal_pump', 'm3/s', ('facility_cooling', 'internal_pump', 'volume_flow_m3_s')),
    'intake_pump.volume_flow': ('intake_pump', 'm3/s', ('facility_cooling', 'lake_pump', 'volume_flow_m3_s')),
}


class SavedRunSignals:
    """PRIVATE lazy exact-point sampler: no interpolation, future row, or fault-label path."""

    def __init__(self, directory):
        self._directory = Path(directory)
        self._rows = None
        self._manifest = None
        self._identity = None

    def _load(self):
        folder = self._directory
        run_bytes = (folder / 'run.json').read_bytes()
        manifest = strict_json(run_bytes.decode('utf-8'))
        if type(manifest) is not dict or manifest.get('schema') != 'aegisdc-engineering-facility-run-v1' \
                or manifest.get('status') != 'ENGINEERING_FIXTURE_COMPLETED' \
                or manifest.get('state_visibility') != 'PRIVATE_PLANT_EVALUATOR_ONLY':
            raise ValueError('Use a completed private engineering saved run')
        expected = {'scenario.json', 'private-state.jsonl', 'balances.jsonl'}
        if set(manifest['artifacts']) != expected:
            raise ValueError('Saved-run artifact roles differ')
        data = {}
        for name, identity in manifest['artifacts'].items():
            data[name] = (folder / name).read_bytes()
            if sha256(data[name]).hexdigest() != identity['sha256']:
                raise ValueError('Private saved input hash mismatch: ' + name)
        scenario = strict_json(data['scenario.json'].decode('utf-8'))
        if scenario['id'] != manifest['facility_id'] or digest(scenario) != manifest['scenario_sha256']:
            raise ValueError('Private run facility/scenario identity mismatch')
        rows = [strict_json(line) for line in data['private-state.jsonl'].decode('utf-8').splitlines()]
        if len(rows) != manifest['artifacts']['private-state.jsonl']['records'] or not rows:
            raise ValueError('Private saved point count differs')
        previous = None
        for row in rows:
            if type(row) is not dict or type(row.get('domains')) is not dict:
                raise ValueError('Invalid private saved point structure')
            time = _finite(row['time_s'], 'Private saved time')
            if previous is not None and time <= previous:
                raise ValueError('Private saved points must be strictly ordered')
            previous = time
        self._rows = rows
        self._manifest = manifest
        self._identity = dict(code_identity=manifest['code_identity'], scenario_sha256=manifest['scenario_sha256'],
            run_sha256=sha256(run_bytes).hexdigest(), saved_artifacts={k: v['sha256'] for k, v in manifest['artifacts'].items()},
            property_reference=manifest['property_reference'])

    def sample_at(self, completed_at_s, *, signal_id, target_id, facility_id):
        """Private measurement seam; only an exact authorized completion point is supported."""
        _finite(completed_at_s, 'Effective completion')
        if signal_id not in SIGNALS or SIGNALS[signal_id][0] != target_id:
            raise ValueError('Signal is outside the explicit measurable target whitelist')
        if self._rows is None:
            self._load()
        if self._manifest['facility_id'] != facility_id:
            raise ValueError('Private saved run belongs to a different declared facility')
        selected = [row for row in self._rows if row['time_s'] == completed_at_s]
        if len(selected) != 1:
            raise ValueError('No exact saved point at effective completion; no future/interpolated sample is authorized')
        value = selected[0]['domains']
        for part in SIGNALS[signal_id][2]:
            value = value[part]
        return dict(value=_finite(value, 'Authorized measured signal'), unit=SIGNALS[signal_id][1],
                    source_sample_at_s=selected[0]['time_s'], private_source=deepcopy(self._identity))


def _numeric_model(model, observable):
    _plain(model)
    expected = {'schema', 'id', 'kind', 'signal_id', 'unit', 'reported_error_bound', 'quality_note', 'basis', 'source_note'}
    if type(model) is not dict or set(model) != expected or model['schema'] != 'aegisdc-handheld-model-v1' \
            or model['kind'] != 'numeric' or model['basis'] != 'synthetic_assumption':
        raise ValueError('Declare the supported synthetic numeric instrument model')
    for name in ('id', 'signal_id', 'unit', 'quality_note', 'source_note'):
        _text(model[name], name)
    if observable['value_type'] != 'number' or model['unit'] != observable['unit']:
        raise ValueError('Instrument output does not match the declared SI observable')
    if _finite(model['reported_error_bound'], 'Declared instrument bound') < 0:
        raise ValueError('Declared instrument bound must be nonnegative')
    return model


def _realization(value):
    _plain(value)
    if type(value) is not dict or set(value) != {'seed', 'bias', 'noise_half_width'} or type(value['seed']) is not int:
        raise ValueError('Declare a private seed/bias/noise realization')
    _finite(value['bias'], 'Private instrument bias')
    if _finite(value['noise_half_width'], 'Private instrument noise half-width') < 0:
        raise ValueError('Private noise half-width must be nonnegative')
    return value


def _draw(realization, token, label):
    epoch = Fraction(token['completed_at_s'])
    key = [realization['seed'], token['source_id'], token['provenance']['origin_id'], token['target_id'],
           token['observable_id'], [epoch.numerator, epoch.denominator], label]
    raw = sha256(json.dumps(key, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).digest()
    return Fraction(int.from_bytes(raw, 'big'), 2 ** 256)


def _reported_number(value):
    try:
        result = value.numerator if value.denominator == 1 else float(value)
    except OverflowError as error:
        raise ValueError('Instrument output is outside the finite numeric domain') from error
    return _finite(result, 'Reported measurement')


class NonfixedEvidenceProducer:
    """Produce only declared messages; this interface has no private fault input."""

    def __init__(self, registry):
        self._registry = validate_ledger(registry)
        if self._registry['records']:
            raise ValueError('Provide a public static empty-record registry, not a private/full ledger')
        self._sources = {row['id']: row for row in self._registry['sources']}
        self._audit = []

    def source_descriptions(self):
        return [dict(source_id=row['id'], source_kind=row['kind'], time_model=REPORT_KINDS[row['kind']],
                     independence='NOT_ESTABLISHED')
                for row in sorted(self._sources.values(), key=lambda value: value['id']) if row['kind'] in REPORT_KINDS]

    def publish_report(self, record, *, as_of_s):
        """Keep original claim/time/quality/provenance; late arrival never refreshes history."""
        _finite(as_of_s, 'Publication time')
        document = dict(self._registry, records=[record])
        checked = validate_ledger(document)['records'][0]
        if self._sources[checked['source_id']]['kind'] not in REPORT_KINDS:
            raise ValueError('This producer accepts history, asset, human or work-order claims only')
        if checked['observed_at_s'] > as_of_s or checked['arrived_at_s'] > as_of_s:
            return None
        return checked

    def publish_completion(self, completion, *, model, private_signals, realization, as_of_s):
        """A fixture-side gate for later22; no private signal is read before permission/time."""
        _finite(as_of_s, 'Publication time')
        token = _completion(completion)
        if token['status'] != 'COMPLETED' or not token['qualification_declared']:
            return None
        if {'target_id': token['target_id'], 'observable_id': token['observable_id']} not in token['coverage']:
            return None
        if as_of_s < _arrival(token['completed_at_s'], token['arrival_latency_s']):
            return None
        if token['source_id'] not in self._sources or self._sources[token['source_id']]['kind'] != 'handheld':
            raise ValueError('Completion records require a declared handheld source')
        source = self._sources[token['source_id']]
        if token['target_id'] not in source['target_ids'] or token['observable_id'] not in source['observable_ids']:
            raise ValueError('Completion exceeds declared source coverage')
        observable = next(row for row in self._registry['observables'] if row['id'] == token['observable_id'])
        model = _numeric_model(model, observable)
        realization = _realization(realization)
        signal = private_signals.sample_at(token['completed_at_s'], signal_id=model['signal_id'],
            target_id=token['target_id'], facility_id=self._registry['facility_id'])
        if signal['unit'] != model['unit']:
            raise ValueError('Private signal and instrument units differ')
        draw = _draw(realization, token, 'numeric-noise')
        exact = Fraction(signal['value']) + Fraction(realization['bias']) \
            + Fraction(realization['noise_half_width']) * (2 * draw - 1)
        value = _reported_number(exact)
        quality = dict(status='bounded', error_bound=model['reported_error_bound'], note=model['quality_note'])
        record = dict(id=token['id'], source_id=token['source_id'], target_id=token['target_id'],
            observable_id=token['observable_id'], unit=observable['unit'], value=value,
            observed_at_s=token['completed_at_s'], arrived_at_s=_arrival(token['completed_at_s'], token['arrival_latency_s']),
            valid_until_s=token['valid_until_s'], quality=quality, provenance=deepcopy(token['provenance']))
        checked = validate_ledger(dict(self._registry, records=[record]))['records'][0]
        self._audit.append(dict(event_id=token['id'], raw_planned_completed_at_s=token['planned_completed_at_s'],
            effective_completed_at_s=token['completed_at_s'], source_sample_at_s=signal['source_sample_at_s'],
            arrived_at_s=checked['arrived_at_s'], private_source=signal['private_source'],
            private_realization=deepcopy(realization), private_draw=dict(numerator=draw.numerator, denominator=draw.denominator),
            authorized_raw_signal=signal['value'], model=deepcopy(model),
            actual_error_vs_signal=_reported_number(Fraction(value)-Fraction(signal['value'])),
            declared_bound_contains_signal=abs(Fraction(value)-Fraction(signal['value'])) <= Fraction(model['reported_error_bound'])))
        return checked

    def private_audit(self):
        """PRIVATE engineering traceability, never a dispatcher result or producer public message."""
        return dict(schema='aegisdc-nonfixed-private-audit-v1', classification='PRIVATE_ENGINEERING_AUDIT_NOT_DISPATCH',
                    events=deepcopy(self._audit))
