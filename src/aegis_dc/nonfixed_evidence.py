"""Declared nonfixed records; private completion sampling is a separate boundary."""
import math
import json
from hashlib import sha256
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from patrol_rsi.contracts import strict_json, digest
from .evidence_ledger import validate_ledger, EvidenceLedger

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
    if type(value['qualification_declared']) is not bool or type(value['status']) is not str or value['status'] not in {'COMPLETED', 'INCOMPLETE', 'ABORTED', 'REJECTED'}:
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
    if value['valid_until_s'] is not None:
        _finite(value['valid_until_s'], 'Completion validity end')
        if value['completed_at_s'] is not None and value['valid_until_s'] <= value['completed_at_s']:
            raise ValueError('Completion validity end must follow its actual observation')
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


def _measurement_model(model, observable):
    _plain(model)
    common = {'schema', 'id', 'kind', 'signal_id', 'unit', 'quality_note', 'basis', 'source_note'}
    variants = {'numeric': {'reported_error_bound'},
                'binary_detection': {'threshold', 'threshold_unit', 'sensitivity', 'false_positive_rate'}, 'unknown': set()}
    if type(model) is not dict or type(model.get('kind')) is not str or model['kind'] not in variants \
            or set(model) != common | variants[model['kind']] or model['schema'] != 'aegisdc-handheld-model-v1' \
            or model['basis'] != 'synthetic_assumption':
        raise ValueError('Declare a supported synthetic instrument model')
    for name in ('id', 'signal_id', 'unit', 'quality_note', 'source_note'):
        _text(model[name], name)
    if model['unit'] != observable['unit'] or model['signal_id'] not in SIGNALS:
        raise ValueError('Instrument output/signal does not match a declared SI observable')
    if model['kind'] == 'numeric':
        if observable['value_type'] != 'number' or model['unit'] != SIGNALS[model['signal_id']][1]:
            raise ValueError('Numeric instrument requires matching numeric signal units')
        if _finite(model['reported_error_bound'], 'Declared instrument bound') < 0:
            raise ValueError('Declared instrument bound must be nonnegative')
    elif model['kind'] == 'binary_detection':
        if observable['value_type'] != 'boolean' or model['unit'] != '1' or model['threshold_unit'] != SIGNALS[model['signal_id']][1]:
            raise ValueError('Binary detector requires declared physical threshold units and boolean output')
        _finite(model['threshold'], 'Declared detector threshold')
        for name in ('sensitivity', 'false_positive_rate'):
            if not 0 <= _finite(model[name], name) <= 1:
                raise ValueError('Declared detector probabilities must be within0..1')
    elif observable['value_type'] != 'number' or model['unit'] != SIGNALS[model['signal_id']][1]:
        raise ValueError('Indeterminate numeric inspection still declares its SI channel')
    return deepcopy(model)


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


def _measurement_result(model, token, signal, realization):
    """Private pure observation law shared by fixture17 and actual execution22."""
    if model['kind'] == 'unknown':
        return None, dict(status='unknown', error_bound=None, note=model['quality_note']), dict(declared_indeterminate=True), None, None
    realization = _realization(realization)
    if model['kind'] == 'binary_detection' and (realization['bias'] != 0 or realization['noise_half_width'] != 0):
        raise ValueError('Binary threshold performance is separate from the numeric bias/noise model')
    if model['kind'] == 'numeric':
        draw = _draw(realization, token, 'numeric-noise')
        exact = Fraction(signal['value']) + Fraction(realization['bias']) + Fraction(realization['noise_half_width']) * (2 * draw - 1)
        value = _reported_number(exact)
        quality = dict(status='bounded', error_bound=model['reported_error_bound'], note=model['quality_note'])
        outcome = dict(actual_error_vs_signal=_reported_number(Fraction(value)-Fraction(signal['value'])),
            declared_bound_contains_signal=abs(Fraction(value)-Fraction(signal['value'])) <= Fraction(model['reported_error_bound']))
    else:
        draw = _draw(realization, token, 'threshold-detector')
        latent = Fraction(signal['value']) >= Fraction(model['threshold'])
        rate = model['sensitivity'] if latent else model['false_positive_rate']
        value = draw < Fraction(rate)
        quality = dict(status='reported', error_bound=None, note=model['quality_note'])
        outcome = dict(latent_signal_above_threshold=latent, declared_detection_rate=rate)
    return value, quality, outcome, realization, draw


class NonfixedEvidenceProducer:
    """Produce only declared messages; this interface has no private fault input."""

    def __init__(self, registry):
        self._registry = validate_ledger(registry)
        if self._registry['records']:
            raise ValueError('Provide a public static empty-record registry, not a private/full ledger')
        self._sources = {row['id']: row for row in self._registry['sources']}
        self._audit = []

    def source_descriptions(self):
        return [dict(source_id=row['id'], source_kind=row['kind'], time_model={**REPORT_KINDS, 'handheld': 'EFFECTIVE_COMPLETION_OBSERVATION'}[row['kind']],
                     independence='NOT_ESTABLISHED')
                for row in sorted(self._sources.values(), key=lambda value: value['id']) if row['kind'] in set(REPORT_KINDS) | {'handheld'}]

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
        model = _measurement_model(model, observable)
        if SIGNALS[model['signal_id']][0] != token['target_id']:
            raise ValueError('Instrument channel and completion target differ')
        if model['kind'] == 'unknown':
            signal = dict(value=None, source_sample_at_s=None, private_source=None)
        else:
            if type(private_signals) is not SavedRunSignals:
                raise ValueError('Use the typed private SavedRunSignals adapter, not a world object or callback')
            # Validate private realization before opening the saved signal, as in17.
            checked = _realization(realization)
            if model['kind'] == 'binary_detection' and (checked['bias'] != 0 or checked['noise_half_width'] != 0):
                raise ValueError('Binary threshold performance is separate from the numeric bias/noise model')
            signal = private_signals.sample_at(token['completed_at_s'], signal_id=model['signal_id'],
                target_id=token['target_id'], facility_id=self._registry['facility_id'])
        value, quality, private_outcome, realization, draw = _measurement_result(model, token, signal, realization)
        record = dict(id=token['id'], source_id=token['source_id'], target_id=token['target_id'],
            observable_id=token['observable_id'], unit=observable['unit'], value=value,
            observed_at_s=token['completed_at_s'], arrived_at_s=_arrival(token['completed_at_s'], token['arrival_latency_s']),
            valid_until_s=token['valid_until_s'], quality=quality, provenance=deepcopy(token['provenance']))
        checked = validate_ledger(dict(self._registry, records=[record]))['records'][0]
        self._audit.append(dict(event_id=token['id'], raw_planned_completed_at_s=token['planned_completed_at_s'],
            effective_completed_at_s=token['completed_at_s'], source_sample_at_s=signal['source_sample_at_s'],
            arrived_at_s=checked['arrived_at_s'], private_source=signal['private_source'],
            private_realization=deepcopy(realization), private_draw=dict(numerator=draw.numerator, denominator=draw.denominator) if draw is not None else None,
            authorized_raw_signal=signal['value'], model=deepcopy(model), **private_outcome))
        return checked

    def private_audit(self):
        """PRIVATE engineering traceability, never a dispatcher result or producer public message."""
        return dict(schema='aegisdc-nonfixed-private-audit-v1', classification='PRIVATE_ENGINEERING_AUDIT_NOT_DISPATCH',
                    events=deepcopy(self._audit))


def validate_nonfixed_profile(document):
    """Validate public static registry/performance assumptions without any private realization."""
    _plain(document)
    if type(document) is not dict or set(document) != {'schema', 'registry', 'models'} \
            or document['schema'] != 'aegisdc-nonfixed-profile-v1':
        raise ValueError('Use the closed nonfixed public profile')
    registry = validate_ledger(document['registry'])
    if registry['records'] or type(document['models']) is not list:
        raise ValueError('Public profile contains an empty-record registry and declared model list')
    sources = {s['id']:s for s in registry['sources']}
    observables = {o['id']:o for o in registry['observables']}
    models, identifiers = [], set()
    for row in document['models']:
        if type(row) is not dict or set(row) != {'source_id', 'target_id', 'observable_id', 'instrument_id', 'model'}:
            raise ValueError('Bind each public instrument model to its declared source/coverage')
        for name in ('source_id', 'target_id', 'observable_id', 'instrument_id'):
            _text(row[name], name)
        source = sources.get(row['source_id'])
        if source is None or source['kind'] != 'handheld' or row['target_id'] not in source['target_ids'] \
                or row['observable_id'] not in source['observable_ids']:
            raise ValueError('Public model binding exceeds declared handheld coverage')
        model = _measurement_model(row['model'], observables[row['observable_id']])
        if SIGNALS[model['signal_id']][0] != row['target_id'] or model['id'] in identifiers:
            raise ValueError('Public model has inconsistent target or duplicate identity')
        identifiers.add(model['id']);models.append(dict(row,model=model))
    return dict(schema=document['schema'],registry=registry,models=deepcopy(models))


class NonfixedSession:
    """Private producer backend; only snapshot/public_models are decision-side plain data."""

    def __init__(self, profile, plan, *, private_signals=None):
        self._profile = validate_nonfixed_profile(profile)
        self._producer = NonfixedEvidenceProducer(self._profile['registry'])
        _plain(plan)
        if type(plan) is not dict or set(plan) != {'schema','reported_records','external_records','completion_requests'} \
                or plan['schema'] != 'aegisdc-nonfixed-plan-v1' \
                or any(type(plan[name]) is not list for name in ('reported_records','external_records','completion_requests')):
            raise ValueError('Use the closed private nonfixed plan')
        checked = validate_ledger(dict(self._profile['registry'], records=plan['reported_records']+plan['external_records']))
        sources = {s['id']:s for s in checked['sources']}
        if any(sources[r['source_id']]['kind'] not in REPORT_KINDS for r in plan['reported_records']):
            raise ValueError('Handheld/fixed messages cannot bypass their producer through reported claims')
        if any(sources[r['source_id']]['kind'] not in {'fixed_sensor', 'control_record'} for r in plan['external_records']):
            raise ValueError('External upstream records must use fixed/control channels; nonfixed records require their producer/completion gate')
        self._models = {row['model']['id']:row for row in self._profile['models']}
        identifiers = {r['id'] for r in plan['reported_records']+plan['external_records']}
        for row in plan['completion_requests']:
            if type(row) is not dict or set(row) != {'completion','model_id','realization'}:
                raise ValueError('Declare a completion/model/private realization request')
            _text(row['model_id'],'Model identity')
            token = _completion(row['completion'])
            binding = self._models.get(row['model_id'])
            if binding is None or any(token[name] != binding[name] for name in ('source_id','target_id','observable_id','instrument_id')):
                raise ValueError('Completion does not match its public model/source/instrument binding')
            if token['id'] in identifiers:
                raise ValueError('Producer event identity conflicts with another planned record')
            identifiers.add(token['id'])
        self._plan = deepcopy(plan)
        self._private_signals = private_signals

    def snapshot(self, as_of_s):
        _finite(as_of_s,'Snapshot time')
        ledger = EvidenceLedger(self._profile['registry'])
        for row in self._plan['external_records']:
            ledger.ingest(row)
        for row in self._plan['reported_records']:
            record = self._producer.publish_report(row,as_of_s=as_of_s)
            if record is not None:
                ledger.ingest(record)
        for request in self._plan['completion_requests']:
            binding = self._models[request['model_id']]
            record = self._producer.publish_completion(request['completion'],model=binding['model'],
                private_signals=self._private_signals,realization=request['realization'],as_of_s=as_of_s)
            if record is not None:
                ledger.ingest(record)
        return ledger.snapshot(as_of_s)

    def public_models(self):
        return dict(schema='aegisdc-nonfixed-public-models-v1',source_time_models=self._producer.source_descriptions(),
                    models=deepcopy(self._profile['models']), independence='NOT_ESTABLISHED',
                    arrival_coordinate='First finite representable value not before decoded completion+latency')

    def private_audit(self):
        return self._producer.private_audit()


def _write_new_json(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    """Standalone operator CLI: stdout is only the14 public snapshot; audit/receipt are private."""
    import argparse
    import sys
    from .replay import execution_source_identity
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True, help='Private declared report/completion plan')
    parser.add_argument('--private-run', type=Path, help='Private immutable engineering saved run, never a public input')
    parser.add_argument('--as-of', type=strict_json, required=True, help='Finite JSON int/binary64 decision time')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    try:
        _finite(arguments.as_of, 'Decision time')
    except ValueError:
        print('Nonfixed producer decision time is unsupported', file=sys.stderr)
        return 2
    if arguments.output.exists():
        print('Output directory already exists; use a new producer output', file=sys.stderr)
        return 2
    try:
        arguments.output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print('Output directory already exists; use a new producer output', file=sys.stderr)
        return 2
    declared = ['declaration.json', 'public-snapshot.json', 'public-models.json', 'private-audit.json']
    _write_new_json(arguments.output / 'declaration.json', dict(schema='aegisdc-nonfixed-output-declaration-v1',
        declared_when_completed=declared, public_files=['public-snapshot.json','public-models.json'],
        private_files=['private-audit.json'], terminal_private_receipt='receipt.json', runtime_caches='NOT_DELIVERABLE'))
    receipt = dict(schema='aegisdc-nonfixed-operator-receipt-v1', classification='PRIVATE_ENGINEERING_NOT_DISPATCH',
        status='FAILED', delivery_gate='PENDING_COMMIT_AND_FRESH_CHECKOUT', as_of_s=arguments.as_of,
        source_identity=execution_source_identity(), input_sha256={}, research_trials=0, model_calls=0, training_calls=0)
    public = None
    try:
        profile_raw, plan_raw = arguments.profile.read_bytes(), arguments.plan.read_bytes()
        receipt['input_sha256'] = dict(public_profile=sha256(profile_raw).hexdigest(),private_plan=sha256(plan_raw).hexdigest())
        signals = SavedRunSignals(arguments.private_run) if arguments.private_run is not None else None
        session = NonfixedSession(strict_json(profile_raw.decode('utf-8')),strict_json(plan_raw.decode('utf-8')),private_signals=signals)
        public = session.snapshot(arguments.as_of)
        outputs = {'public-snapshot.json':public,'public-models.json':session.public_models(),'private-audit.json':session.private_audit()}
        for name, value in outputs.items():
            _write_new_json(arguments.output/name,value)
        receipt['status'] = 'COMPLETED'
    except (ValueError,OSError,KeyError,TypeError) as error:
        receipt['failure'] = dict(type=type(error).__name__,message=str(error))
    files = [path for path in arguments.output.iterdir() if path.is_file()]
    receipt['artifacts'] = {path.name:sha256(path.read_bytes()).hexdigest() for path in files}
    if not set(receipt['artifacts']) <= set(declared) or receipt['status']=='COMPLETED' and set(receipt['artifacts'])!=set(declared):
        raise ValueError('Producer output roles differ from initial declaration')
    _write_new_json(arguments.output/'receipt.json',receipt)
    if receipt['status']!='COMPLETED':
        print('Nonfixed producer request refused; private operator receipt retained',file=sys.stderr)
        return 1
    print(json.dumps(public,ensure_ascii=False,allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
