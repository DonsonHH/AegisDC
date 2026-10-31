"""CPU-only offline Qwen proposal fallback; execution stays on the v3 snapshot.

This sidecar never evaluates an environment. It consumes the same global
four-call ledger and uses v3's immutable compiler and development feedback.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from run_multistep import (MODEL, reserve, current_rows, gate_directory, verify_source,
                          model_feedback, read, write, sha, need, verify_open_model)
from patrol_rsi.multistep_workflow import Workflow, compile_edit, SCOPES, RANKERS, TOOLS


def compact_feedback(rows):
    result = []
    for case in model_feedback(rows):
        scores = {arm: {'missed': m['missed_segments'], 'wait_s': m['consequence_weighted_censored_delay_s'],
            'travel_m': m['travel_m'], 'service_s': m['service_s'], 'extra_checks': m['selected_detours'],
            'revisit_violations': m['tasks_violating_exact_gap']} for arm, m in case['simulation_development_scores'].items()}
        timeline = []
        for event in case['legal_public_timeline']:
            info = event['information']
            timeline.append({k: event[k] for k in ('dispatch_time_s', 'agent', 'task', 'completed_time_s',
                'profession', 'pod', 'actual_reference', 'measured_alarm')} | {
                'prior_qualified': info['prior_qualified'],
                'simultaneous_remote': {'available': info['contemporaneous_remote_same_quantity'],
                    'time_s': info['remote_time_s'], 'value': info['remote_value']}})
        result.append({'anonymous_case': case['case'], 'simulation_DEVELOPMENT_scores': scores,
            'public_real_completions': timeline, 'actual_workflow_choices': case['actual_workflow_choices']})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    need('SLURM_JOB_ID' in os.environ and not torch.cuda.is_available(), 'Allocated CPU-only Slurm fallback')
    source, root = args.source.resolve(), args.root.resolve()
    signature = verify_source(source)
    check = read(gate_directory(root, source) / 'complete.json')
    need(check['passed'] and check['source_manifest_sha256'] == signature, 'v3 exact-source safety/interface gate')
    rows = [r for r in current_rows(root, source) if r['arm'] in ('A', 'B', 'C', 'D')]
    need(len(rows) == 24 and all(r['audit']['passed'] for r in rows), 'Complete original baseline evidence')
    need(not (root / 'child-workflow.json').exists(), 'No duplicate proposal loop')
    area = root / 'model-cpu'
    area.mkdir(exist_ok=False)
    torch.set_num_threads(int(os.environ['SLURM_CPUS_PER_TASK']))
    started = time.perf_counter()
    deadline = time.monotonic() + 540
    manifest = verify_open_model(MODEL)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32,
        attn_implementation='eager', local_files_only=True, trust_remote_code=False).eval()
    versions = tuple(v._version for v in model.parameters())
    write(area / 'startup.json', {'job_id': os.environ['SLURM_JOB_ID'], 'device': 'cpu', 'dtype': 'float32',
        'threads': torch.get_num_threads(), 'verified_model': manifest, 'source_manifest_sha256': signature,
        'proposal_sidecar_sha256': sha(Path(__file__)), 'training': False,
        'startup_seconds': time.perf_counter() - started,
        'reason': 'All16 GPUs allocated; unstarted131046 canceled before CPU fallback to prevent duplicate calls'})
    parent = Workflow()
    feedback = compact_feedback(rows)
    failures = []
    for index in range(4):
        if time.monotonic() + 90 > deadline:
            break
        user = {'task': 'Make ONE executable workflow modification using these completed public development episodes.',
            'parent_workflow': parent.to_dict(), 'parent_sha256': parent.sha256,
            'response_schema': {'schema': 'workflow-edit-v1', 'parent_sha256': parent.sha256,
                'changes': 'object with ONE or TWO changed fields only', 'mechanism': '1-2 short English sentences, at most200 characters'},
            'allowed_values': {'after_alarm': SCOPES, 'after_normal': SCOPES, 'ranker': RANKERS, 'estimator': TOOLS},
            'semantics': 'after_alarm or after_normal branches on the ACTUAL first qualified reference; prefer scoped safe candidates then supported global fallback. return_tour skips further extra checks. risk_lead ranks signal*importance*lead; urgency ranks age/deadline+cost/deadline; risk_per_cost ranks signal*importance/cost. estimator chooses current frozen CVAE+nominal estimates or nominal alone, neither is a true measurement.',
            'immutable': 'K=2, first-check code except chosen estimate tool, safety, qualifications, task ownership, physics, scoring, data and budgets',
            'instruction': 'Prefer a branch/order/tool change exercised in the supplied public traces. Explain the mechanism; a positive score improvement is NOT required. Do not propose an unchanged parent. No Python, markdown, thresholds or extra response keys.',
            'feedback_label': 'Explicitly labeled simulation DEVELOPMENT scores. Online controllers cannot access these scores or future truth.',
            'public_feedback': feedback, 'previous_structural_failures': failures}
        # This whitelist was built from anonymous public trajectories and scores.
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    need(key not in {'seed', 'scenario', 'fault_start_s', 'fault_end_s', 'anomaly_intervals', 'oracle'}, 'Hidden prompt field')
                    keys(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    keys(child)
        keys(user)
        rendered = tokenizer.apply_chat_template([{'role': 'system', 'content': 'Return exactly one JSON object matching response_schema. No text outside JSON. Propose a concrete bounded workflow change using only the supplied public evidence.'},
            {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(rendered, return_tensors='pt')
        count = int(inputs['input_ids'].numel())
        need(count <= 6144, 'Same bounded6144 input limit')
        receipt = reserve(root, 'model-calls', 4, {'index': index, 'device': 'cpu', 'parent_sha256': parent.sha256,
            'source_manifest_sha256': signature, 'proposal_sidecar_sha256': sha(Path(__file__))})
        call = area / f'call-{index:02d}'
        call.mkdir()
        write(call / 'start.json', {'receipt': receipt, 'prompt': user, 'rendered_prompt': rendered,
            'input_tokens': count, 'output_cap': 384, 'thinking': False, 'decoder': 'greedy'})
        response = None
        begin = time.perf_counter()
        def timeout(signum, frame):
            raise TimeoutError('CPU generation timed out; this real call remains charged')
        previous = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, min(360, deadline - time.monotonic() - 10))
        try:
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=384, do_sample=False)
            response = tokenizer.decode(generated[0, count:], skip_special_tokens=True)
            write(call / 'response.json', {'raw_response': response, 'output_tokens': int(generated.shape[1] - count),
                'seconds': time.perf_counter() - begin, 'device': 'cpu'})
            child = compile_edit(parent, response)
            need(tuple(v._version for v in model.parameters()) == versions, 'No weight updates')
            write(call / 'accepted-interface.json', {'child': child.to_dict(), 'child_sha256': child.sha256,
                'meaning': 'Executable nonduplicate, not performance-accepted'})
            write(root / 'child-workflow.json', {'workflow': child.to_dict(), 'parent': parent.to_dict(),
                'parent_sha256': parent.sha256, 'proposal_response_path': str(call / 'response.json'),
                'proposal_response_sha256': sha(call / 'response.json'), 'device': 'cpu',
                'proposal_sidecar_sha256': sha(Path(__file__)), 'environment_execution_source_sha256': signature})
            print('LEGAL_CPU_MODEL_CHILD', index, child.sha256, flush=True)
            return
        except Exception as error:
            write(call / 'failed.json', {'type': type(error).__name__, 'error': str(error),
                'raw_response': response, 'call_charged': True, 'seconds': time.perf_counter() - begin})
            failures.append({'call': index, 'error': str(error)})
            if isinstance(error, TimeoutError):
                break
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    write(root / 'proposal-failure.json', {'failures': failures, 'real_calls_charged': True})


if __name__ == '__main__':
    main()
