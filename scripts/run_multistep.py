"""Bounded Slurm execution of the preregistered minimal workflow prototype."""
import argparse
from copy import deepcopy
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import time
import traceback
from unittest.mock import patch

import torch

from patrol_rsi.improver_task import PhasedTrace
from patrol_rsi.limited_prediction import read, write, sha, need
from patrol_rsi.m11 import frozen_predictor
from patrol_rsi.m12 import verify_open_model
from patrol_rsi.m4 import ModelCaller
from patrol_rsi.m9 import arrays_digest
from patrol_rsi.multistep_execution import run_workflow_episode
from patrol_rsi.multistep_workflow import Workflow, compile_edit, digest, SCOPES, RANKERS, TOOLS
from audit_m11 import independent_schedule, independent_events
from audit_m111 import independent_certificates
from run_m12d_paired import StoredTrace, save_trace, write_gz

STAGE = 'research/2026-11-01-multistep-workflow'
CVAE = Path('/share/home/renly/renly-patrol-rsi/runs/20261028-m111/frozen-estimator.pt')
MODEL = Path('/share/home/renly/renly-patrol-rsi/models/Qwen3-8B-b968826d')


def reserve(root, kind, cap, detail):
    """Count actual starts, including failures, before each attempt."""
    path = root / f'{kind}.jsonl'
    with (root / 'budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = path.read_text().splitlines() if path.exists() else []
        need(len(old) < cap, f'{kind} cap exhausted')
        value = dict(number=len(old), unix=time.time(), job_id=os.environ['SLURM_JOB_ID'], **detail)
        with path.open('a') as stream:
            stream.write(json.dumps(value, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    return value


def load_rows(root):
    return [read(path) for path in sorted((root / 'evaluations').glob('episode-*/complete.json'))]


def protocol(source):
    return read(source / STAGE / 'protocol-v1.json')


def verify_source(source):
    manifest = read(source / 'snapshot-manifest.json')
    for name, expected in manifest['files'].items():
        need(sha(source / name) == expected, 'Source snapshot changed: ' + name)
    need(not (source / '.git').exists(), 'Run immutable snapshot, not mutable checkout')
    return sha(source / 'snapshot-manifest.json')


def get_trace(root, source, case):
    folder = root / 'processes' / case['case_id']
    folder.parent.mkdir(exist_ok=True)
    if not folder.exists():
        spec = case['specification']
        trace = PhasedTrace(spec['seed'], spec['scenario'], spec['duration_s'], spec['fault_start_s'])
        history = read(source / STAGE / 'historical-identities.json')
        need(spec['seed'] not in history['seed_groups'] and trace.fingerprint not in history['numeric_fingerprints'],
             'New source must not overlap registered old seeds or numeric processes')
        for prior in folder.parent.glob('*/complete.json'):
            need(read(prior)['fingerprint'] != trace.fingerprint, 'Six distinct physical processes')
        save_trace(trace, folder)
    return StoredTrace(folder)


def run_one(root, source, case, arm, workflow, predictor):
    p = protocol(source)
    need(case in p['cases'], 'Only six preregistered development cases')
    key = digest({'case': case, 'arm': arm, 'workflow': workflow.to_dict()})
    existing = [row for row in load_rows(root) if row['evaluation_key'] == key]
    if existing:
        need(len(existing) == 1 and sha(Path(existing[0]['record_path'])) == existing[0]['record_sha256'], 'Reuse exact finished episode')
        return existing[0]
    receipt = reserve(root, 'environment-attempts', 60, {'case_id': case['case_id'], 'arm': arm,
        'workflow_sha256': workflow.sha256, 'source_manifest_sha256': verify_source(source)})
    folder = root / 'evaluations' / f"episode-{receipt['number']:02d}"
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / 'attempt.json', receipt)
    started = time.perf_counter()
    try:
        trace = get_trace(root, source, case)
        before = arrays_digest(trace.arrays)
        budget = 1 if arm in ('A', 'B') else 2
        with patch('patrol_rsi.improver_task.phased_trace', return_value=trace):
            record, env = run_workflow_episode(case['specification'], workflow, predictor, budget, arm)
        need(arrays_digest(trace.arrays) == before, 'No action alters physical process')
        independent_schedule(record, env)
        independent_events(record, env)
        accepted, plans = independent_certificates(record, env)
        extras = [r for r in record['selected_certificates'] if r['task'] != r['baseline_next']]
        need(len(extras) == len(record['optional_chain']) == record['metrics']['selected_detours'] <= budget,
             'Exact issued/completed/budget count')
        need(arm != 'A' or not extras, 'Tour has no optional work')
        need(record['team']['count'] == 18 and len(env.tasks) == 176, 'Original 128 racks and 18 qualified executors')
        for first, second in zip(record['optional_chain'], record['optional_chain'][1:]):
            need(second['dispatch_time_s'] >= first['completed']['time_s'], 'Real sequential measurement before next check')
        for item in record['optional_chain']:
            observed = item['after_task']['qualified']
            field = item['information']['quantity']
            need(observed['available'] and observed['time_s'] == item['completed']['time_s']
                 and observed['value'] == item['completed']['measurement'][field], 'Shared state contains actual reference and source time')
        record.update(case_id=case['case_id'], process_fingerprint=trace.fingerprint,
            execution_source_manifest_sha256=sha(source / 'snapshot-manifest.json'))
        path = folder / 'record.json.gz'
        write_gz(path, record)
        value = {'case_id': case['case_id'], 'arm': arm, 'evaluation_key': key,
            'workflow_sha256': workflow.sha256, 'workflow': workflow.to_dict(),
            'specification': case['specification'], 'process_fingerprint': trace.fingerprint,
            'record_path': str(path), 'record_sha256': sha(path), 'action_sha256': record['action_sha256'],
            'metrics': record['metrics'], 'optional_checks': len(extras),
            'actual_wall_seconds': time.perf_counter() - started, 'job_id': os.environ['SLURM_JOB_ID'],
            'source_manifest_sha256': sha(source / 'snapshot-manifest.json'),
            'audit': {'passed': True, 'qualified_completions': len(record['inspection_events']),
                'independent_return_certificates': accepted, 'actual_assignment_plans': plans,
                'old_measurement_physics_and_scoring': True, 'shared_reference_time_and_value': True,
                'sequential_budget_and_exact_revisit': True}}
        write(folder / 'complete.json', value)
        print('COMPLETED', case['case_id'], arm, len(extras), value['actual_wall_seconds'], flush=True)
        return value
    except BaseException as error:
        write(folder / 'failed.json', {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()})
        raise


def record_of(row):
    path = Path(row['record_path'])
    need(sha(path) == row['record_sha256'], 'Actual feedback authority')
    return json.loads(gzip.decompress(path.read_bytes()))


def model_feedback(rows):
    """Explicit whitelist. Scores are labeled simulated development feedback."""
    result = []
    for case_id in sorted({row['case_id'] for row in rows}):
        group = [row for row in rows if row['case_id'] == case_id]
        parent = next(row for row in group if row['arm'] == 'D')
        record = record_of(parent)
        timeline = []
        for item in record['optional_chain']:
            event = item['completed']
            timeline.append({'dispatch_time_s': item['dispatch_time_s'], 'agent': item['agent'], 'task': item['task'],
                'completed_time_s': event['time_s'], 'profession': event['kind'], 'pod': item['before_task']['pod'],
                'actual_reference': {field: value for field, value in event['measurement'].items()},
                'measured_alarm': event['alarm'], 'information': item['information']})
        decisions = [{k: frame[k] for k in ('time_s', 'state', 'selected', 'frozen_second_if_currently_legal')}
                     for frame in record['workflow_frames'] if frame['selected'] is not None]
        # Drop large same-input candidate channel records; keep actual public reasons.
        for frame in decisions:
            for name in ('selected', 'frozen_second_if_currently_legal'):
                if frame[name] is not None:
                    frame[name] = {k: frame[name][k] for k in ('agent', 'task', 'pod', 'kind', 'rank_signal', 'signal_source', 'lead_s')}
        result.append({'case': case_id, 'simulation_development_scores': {row['arm']: {k: row['metrics'][k] for k in
            ('missed_segments', 'consequence_weighted_censored_delay_s', 'travel_m', 'service_s', 'selected_detours', 'tasks_violating_exact_gap')}
            for row in group if row['arm'] in ('A', 'B', 'C', 'D')}, 'legal_public_timeline': timeline,
            'actual_workflow_choices': decisions})
    return result


def call_model(root, source):
    gate = read(root / 'gate/complete.json')
    need(gate['passed'], 'Interface/safety gate required; no score win prerequisite')
    rows = load_rows(root)
    need(len([r for r in rows if r['arm'] in ('A', 'B', 'C', 'D')]) == 24, 'All development baseline arms finished')
    need(torch.cuda.is_available(), 'Actual allocated GPU required')
    device = torch.cuda.get_device_properties(0)
    need('V100S' in device.name, 'Live resource class')
    area = root / 'model'
    area.mkdir(exist_ok=False)
    write(area / 'startup.json', {'job_id': os.environ['SLURM_JOB_ID'], 'GPU': device.name,
        'verified_model': verify_open_model(MODEL), 'training': False})
    caller = ModelCaller(MODEL, 'cuda')
    versions = tuple(v._version for v in caller.model.parameters())
    parent = Workflow()
    feedback = model_feedback(rows)
    failures = []
    for index in range(4):
        user = {'task': 'Propose one executable child of the current two-step inspection workflow.',
            'parent': parent.to_dict(), 'parent_sha256': parent.sha256,
            'contract': {'schema': 'workflow-edit-v1', 'response_keys': ['schema', 'parent_sha256', 'changes', 'mechanism'],
                'changes': {'after_alarm': list(SCOPES), 'after_normal': list(SCOPES),
                    'ranker': list(RANKERS), 'estimator': list(TOOLS)},
                'one_or_two_changed_fields_only': True,
                'semantics': 'after_alarm/after_normal branch on actual first reference; scoped candidates preferred then global supported fallback; return_tour stops optional followup; ranker orders safe tasks; estimator chooses existing public estimates, never true temperature',
                'immutable': 'Safety, K=2, ownership, physics, scoring, resources and data',
                'request': 'Explain a concrete branch/order/tool mechanism. No code, no threshold tweaks, no claims of proven gain.'},
            'feedback_label': 'Completed simulation DEVELOPMENT feedback, not online truth or validation/test evidence',
            'development_feedback': deepcopy(feedback), 'previous_failures': failures}
        rendered = caller.tokenizer.apply_chat_template([{'role': 'system', 'content': 'Return exactly one JSON object in the requested bounded workflow-edit-v1 schema. Use only the supplied public development evidence. No prose outside JSON.'},
            {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = caller.tokenizer(rendered, return_tensors='pt')
        tokens = int(inputs['input_ids'].numel())
        need(tokens <= 6144, 'Bounded public feedback context; no hidden truncation or free calls')
        receipt = reserve(root, 'model-calls', 4, {'call_index': index, 'parent_sha256': parent.sha256})
        path = area / f'call-{index:02d}'
        path.mkdir()
        write(path / 'start.json', {'receipt': receipt, 'prompt': user, 'rendered_prompt': rendered,
            'input_tokens': tokens, 'output_cap': 768, 'thinking': False})
        started = time.perf_counter()
        def timeout(signum, frame):
            raise TimeoutError('90 second real-call timeout; this call remains charged')
        previous = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, 90)
        response = None
        try:
            torch.manual_seed(71000 + index)
            with torch.inference_mode():
                generated = caller.model.generate(**inputs.to('cuda'), max_new_tokens=768,
                    do_sample=True, temperature=.7, top_p=.8, top_k=20)
            response = caller.tokenizer.decode(generated[0, tokens:], skip_special_tokens=True)
            write(path / 'response.json', {'raw_response': response, 'output_tokens': int(generated.shape[1] - tokens),
                'seconds': time.perf_counter() - started})
            child = compile_edit(parent, response)
            need(tuple(v._version for v in caller.model.parameters()) == versions, 'No model training or weight changes')
            write(path / 'accepted-interface.json', {'child': child.to_dict(), 'child_sha256': child.sha256,
                'meaning': 'Legal executable modification; no performance acceptance or generalization claim'})
            write(root / 'child-workflow.json', {'workflow': child.to_dict(), 'parent': parent.to_dict(),
                'parent_sha256': parent.sha256, 'proposal_response_path': str(path / 'response.json'),
                'proposal_response_sha256': sha(path / 'response.json')})
            print('LEGAL_MODEL_CHILD', index, child.sha256, flush=True)
            return
        except Exception as error:
            failure = {'error_type': type(error).__name__, 'message': str(error), 'raw_response': response,
                       'seconds': time.perf_counter() - started, 'call_charged': True}
            write(path / 'failed.json', failure)
            failures.append({'call': index, 'failure': str(error), 'parent_child_difference': 'No legal child executed'})
            if isinstance(error, (torch.OutOfMemoryError, TimeoutError)):
                break
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    write(root / 'proposal-failure.json', {'failures': failures, 'no_free_retry': True})


def gate(root, source):
    import unittest
    area = root / 'gate'
    area.mkdir(exist_ok=False)
    suite = unittest.TestSuite()
    for name in ('test_multistep_workflow.py', 'test_multistep_safety.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(source / 'tests'), pattern=name))
    with (area / 'tests.txt').open('x') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    value = {'passed': result.wasSuccessful() and not result.skipped, 'tests': result.testsRun,
             'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
             'job_id': os.environ['SLURM_JOB_ID'], 'source_manifest_sha256': verify_source(source)}
    write(area / 'complete.json', value)
    need(value['passed'], 'Workflow and cumulative safety interface tests')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--mode', choices=('pilot', 'baselines', 'model', 'child'), required=True)
    args = p.parse_args()
    need('SLURM_JOB_ID' in os.environ, 'All computation must run in Slurm')
    root, source = args.root.resolve(), Path(__file__).resolve().parents[1]
    root.mkdir(exist_ok=True)
    torch.set_num_threads(1)
    verify_source(source)
    spec = protocol(source)
    if args.mode == 'model':
        call_model(root, source)
        return
    if args.mode == 'pilot':
        gate(root, source)
    else:
        need(read(root / 'gate/complete.json')['passed'], 'Interface test gate')
    predictor = frozen_predictor(CVAE, source / 'research/2026-10-28-m111-coverage/frozen_estimator.json')
    if args.mode == 'pilot':
        row = run_one(root, source, spec['cases'][0], 'D', Workflow(), predictor)
        write(root / 'cost-probe.json', {'actual_seconds': row['actual_wall_seconds'], 'episode_reused': True,
            'projected_24_episode_wall_seconds': row['actual_wall_seconds'] * 24,
            'next_CPU_allocation_seconds_upper_bound': 1200})
    elif args.mode == 'baselines':
        for case in spec['cases']:
            for arm in ('A', 'B', 'C', 'D'):
                run_one(root, source, case, arm, Workflow(), predictor)
        write(root / 'baselines-complete.json', {'rows': [r for r in load_rows(root) if r['arm'] in ('A', 'B', 'C', 'D')]})
    else:
        child = Workflow.from_dict(read(root / 'child-workflow.json')['workflow'])
        for case in spec['cases']:
            run_one(root, source, case, 'child', child, predictor)
        write(root / 'child-complete.json', {'rows': [r for r in load_rows(root) if r['arm'] == 'child']})


if __name__ == '__main__':
    main()
