"""Freeze named V6 inputs, capture each once, and verify saved-only deliveries."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from inspection_delivery import ROOT, digest, durable, git, hashes, read, require, unchanged, write
from parameter_domain_witness_checks import prepared_checks, trajectory_checks

PROTOCOL = 'docs/mainline/29-domain-engineering-protocol.json'
PACKAGE = 'evidence/mainline/engineering/29-uncertainty-domain'
BASELINE = 'configs/full-facility-mainline-reserve-v6.json'
PROPERTY = 'configs/materials/reference-r134a-saturation.json'
TOOLS = ['scripts/run_parameter_domain_witnesses.py', 'scripts/parameter_domain_witness_checks.py',
         'scripts/inspection_delivery.py', 'scripts/preserve_parameter_domain_development.py',
         'scripts/build_parameter_provenance_inventory.py']
NON_CALLS = ('registered_research_trials', 'dispatch_calls', 'model_calls', 'training_calls')


def head():
    return git('rev-parse', 'HEAD').decode().strip()


def protocol_paths(protocol, mode):
    return {pattern.replace('{id}', case['id']) for pattern in protocol['outputs'][mode]
            for case in protocol['cases']}


def _require_protocol(protocol, declaration):
    budget = protocol['budget']
    rows = protocol['cases']
    require(protocol['schema'] == 'aegisdc-parameter-domain-engineering-protocol-v1'
            and protocol['classification'] == 'FINITE_SYNTHETIC_ENGINEERING_ONLY'
            and len(rows) == budget['initialization_calls'] == budget['plant_calls'] == 8
            and len({row['id'] for row in rows}) == 8
            and sum(row['seconds'] for row in rows) == budget['simulated_duration_s'] == 33
            and all(budget[key] == 0 for key in NON_CALLS), 'Frozen budget or role differs')
    require([(row['id'],row['seconds']) for row in rows] ==
            [(row['id'],row['duration_s']) for row in declaration['cases']], 'Protocol/declaration order differs')
    require(protocol['limits']['maximum_step_s'] == declaration['maximum_step_s'], 'Maximum step differs')


def _pins(source, protocol, declaration, mode):
    runtime = [name for name in git('ls-tree','-rz','--name-only',source,'src/aegis_dc').decode().split('\0')
               if name.endswith('.py') and name.count('/') == 2]
    runtime.append('src/patrol_rsi/contracts.py')
    inputs = [PROTOCOL, protocol['declaration'], PROPERTY, *declaration['references_sha256'],
              '.gitattributes', 'docs/mainline/29-uncertainty-domain-contract.md',
              'docs/mainline/29-public-evidence-scope.md',
              f'{PACKAGE}/reference/v6-parameter-inventory-v1.json',
              f'{PACKAGE}/development/development-originals.zip', f'{PACKAGE}/development/manifest.json',
              f'{PACKAGE}/development/prepare-cli-refusal-01.zip', f'{PACKAGE}/development/prepare-cli-refusal-01.json']
    if mode == 'capture':
        inputs.extend(f"{PACKAGE}/{protocol['prepared_directory']}/{name}"
                      for name in protocol_paths(protocol, 'prepare'))
    return {'runtime':hashes(source,runtime), 'bootstrap':hashes(source,['src/patrol_rsi/__init__.py']),
            'tools':hashes(source,TOOLS), 'inputs':hashes(source,inputs)}


def _file_shas(folder, files):
    return {name:digest((folder / name).read_bytes()) for name in sorted(files)}


def _append(folder, record):
    row = dict(record, recorded_at_utc=datetime.now(timezone.utc).isoformat())
    with (folder / 'attempts.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(row, allow_nan=False, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _load_prepared(folder, case_id):
    return read(folder / 'cases' / f'{case_id}.json')


def _check_case(prepared, case_id, declaration):
    row = next(row for row in declaration['cases'] if row['id'] == case_id)
    return prepared_checks(prepared, row, declaration, read(ROOT / BASELINE),
                           digest((ROOT / _declaration_path()).read_bytes()))


def _declaration_path():
    return read(ROOT / PROTOCOL)['declaration']


def _check_lifecycle(folder, protocol, receipt, mode):
    rows = [json.loads(line) for line in (folder / 'attempts.jsonl').read_bytes().splitlines()]
    cases = protocol['cases']
    require(len(rows) == 2*len(cases), 'Incomplete capture lifecycle')
    for i, case in enumerate(cases):
        a,b = rows[2*i:2*i+2]
        require(a['status'] == 'STARTED' and b['status'] == 'PASS'
                and a['case_id'] == b['case_id'] == case['id']
                and a['attempt'] == b['attempt'] == i+1 and b['returned'] is True
                and a['simulated_charge_s'] == (case['seconds'] if mode == 'capture' else 0),
                'Attempt order or charge differs')
    require(receipt['started'] == receipt['passed'] == len(cases)
            and receipt['charged_simulated_s'] == sum(a['simulated_charge_s'] for a in rows[::2]),
            'Terminal attempt count or charge differs')


def _check_original(folder, protocol, declaration, mode):
    receipt = read(folder / 'receipt.json')
    source = receipt['execution_commit']
    expect = protocol_paths(protocol, mode)
    require(receipt['status'] == 'PASS' and receipt['source_unchanged'] and receipt['mode'] == mode
            and durable(folder) == expect and set(receipt['artifacts']) == expect-{'receipt.json'},
            'Delivery does not match the complete durable set')
    require(all(receipt[key] == 0 for key in NON_CALLS), 'Capture scope differs')
    require(_file_shas(folder, receipt['artifacts']) == receipt['artifacts'], 'Captured bytes differ')
    require(_pins(source, protocol, declaration, mode) == receipt['pinned'], 'Recorded Git pins differ')
    require(git('merge-base','--is-ancestor',source,head()) == b'', 'Current source is not a descendant')
    for group in receipt['pinned'].values():
        require(group == hashes(head(),group) and all(
            digest((ROOT / name).read_bytes()) == sha for name,sha in group.items()), 'Execution/delivery bytes differ')
    names = {(folder / name).relative_to(ROOT).as_posix() for name in expect}
    require(hashes(head(),names) == {name:digest((ROOT / name).read_bytes()) for name in names},
            'Working delivery differs from committed blobs')
    _check_lifecycle(folder, protocol, receipt, mode)
    return receipt


def _run(mode, folder, protocol, declaration):
    source = head()
    require(not git('status','--porcelain'), 'Run from the clean frozen checkout')
    require(Path(os.environ.get('PYTHONPATH','')).resolve() == ROOT / 'src' and sys.dont_write_bytecode,
            'Use the isolated repository PYTHONPATH and -B')
    require(sys.pycache_prefix is not None and not Path(sys.pycache_prefix).exists(),
            'Set an unused PYTHONPYCACHEPREFIX before launching Python')
    pins = _pins(source, protocol, declaration, mode)
    require(unchanged(source,pins), 'Execution bytes do not match the frozen source')
    prep = folder.parent / protocol['prepared_directory']
    if mode == 'capture':
        _check_original(prep, protocol, declaration, 'prepare')
    folder.mkdir()
    if mode == 'prepare':
        (folder / 'cases').mkdir()
    expected = protocol_paths(protocol,mode)-{'receipt.json'}
    receipt = dict(schema='aegisdc-domain-witness-receipt-v1', mode=mode, status='FAIL',
        execution_commit=source, pinned=pins, started=0, passed=0, charged_simulated_s=0,
        field_calibration='PENDING', python=sys.version, executable=sys.executable,
        unused_pycache_prefix=sys.pycache_prefix,
        executable_sha256=digest(Path(sys.executable).read_bytes()), argv=sys.argv,
        **{key:0 for key in NON_CALLS})
    results = {}
    try:
        if mode == 'prepare':
            from aegis_dc.parameter_domain import prepare_domain_case
        else:
            from aegis_dc.plant import save_run, simulate_scenario
        for case in protocol['cases']:
            require(unchanged(source,pins), 'Execution source changed before the next attempt')
            case_id = case['id']
            receipt['started'] += 1
            number = receipt['started']
            charged = case['seconds'] if mode == 'capture' else 0
            receipt['charged_simulated_s'] += charged
            _append(folder,dict(status='STARTED', case_id=case_id, attempt=number, simulated_charge_s=charged))
            returned = False
            try:
                if mode == 'prepare':
                    prepared = prepare_domain_case(case_id)
                    returned = True
                    write(folder / 'cases' / f'{case_id}.json', prepared)
                    results[case_id] = _check_case(prepared,case_id,declaration)
                else:
                    prepared = _load_prepared(prep,case_id)
                    init = _check_case(prepared,case_id,declaration)
                    result = simulate_scenario(prepared['scenario'], duration_s=prepared['duration_s'],
                        step_s=prepared['maximum_step_s'], boundary_events=prepared['boundary_events'])
                    returned = True
                    save_run(result,folder / case_id)
                    results[case_id] = dict(initialization=init, **trajectory_checks(
                        folder / case_id, prepared, case, protocol['limits'], source, pins['runtime'], pins['inputs'][PROPERTY]))
                require(unchanged(source,pins), 'Execution source changed during attempt')
            except BaseException as exc:
                _append(folder,dict(status='FAIL', case_id=case_id, attempt=number, returned=returned,
                                    error_type=type(exc).__name__, error=str(exc)))
                raise
            else:
                receipt['passed'] += 1
                _append(folder,dict(status='PASS', case_id=case_id, attempt=number, returned=True))
        if mode == 'capture':
            write(folder / 'checks.json',results)
        require(durable(folder) == expected, 'Captured artifacts do not match the durable declaration')
        receipt['status'] = 'PASS'
    except BaseException as exc:
        receipt.update(error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        receipt['source_unchanged'] = unchanged(source,pins)
        if not receipt['source_unchanged']:
            receipt['status'] = 'FAIL'
        receipt['artifacts'] = _file_shas(folder,durable(folder))
        write(folder / 'receipt.json',receipt)
    require(receipt['status'] == 'PASS', 'Original execution failed')
    return {key:receipt[key] for key in ('mode','status','execution_commit','started','passed','charged_simulated_s')}


def _verify(folder, protocol, declaration, delivery):
    require(head() == delivery and not git('status','--porcelain'), 'Use the clean requested delivery checkout')
    prep = folder / protocol['prepared_directory']
    capture = folder / protocol['capture_directory']
    prep_receipt = _check_original(prep,protocol,declaration,'prepare')
    captured = _check_original(capture,protocol,declaration,'capture')
    recomputed = {}
    for case in protocol['cases']:
        case_id = case['id']
        prepared = _load_prepared(prep,case_id)
        recomputed[case_id] = dict(initialization=_check_case(prepared,case_id,declaration),
            **trajectory_checks(capture / case_id,prepared,case,protocol['limits'],captured['execution_commit'],
                                captured['pinned']['runtime'],captured['pinned']['inputs'][PROPERTY]))
    require(recomputed == read(capture / 'checks.json'), 'Saved analysis differs')
    return dict(status='PASS', delivery=delivery, initialization_source=prep_receipt['execution_commit'],
        physical_source=captured['execution_commit'], verified_prepared=len(durable(prep)),
        verified_capture=len(durable(capture)), verified_cases=len(recomputed),
        verified_trace_points=sum(row['trace_points'] for row in recomputed.values()),
        physical_reruns=0, **{key:0 for key in NON_CALLS})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare','capture','verify'))
    parser.add_argument('--delivery')
    args = parser.parse_args()
    protocol = read(ROOT / PROTOCOL)
    declaration = read(ROOT / protocol['declaration'])
    _require_protocol(protocol,declaration)
    folder = ROOT / PACKAGE
    directory_key = 'prepared_directory' if args.mode == 'prepare' else 'capture_directory'
    result = (_verify(folder,protocol,declaration,args.delivery) if args.mode == 'verify'
              else _run(args.mode,folder / protocol[directory_key],protocol,declaration))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
