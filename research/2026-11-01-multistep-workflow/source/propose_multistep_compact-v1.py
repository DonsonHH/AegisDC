"""Compact CPU proposal after charged full-envelope failures; v3 is unchanged."""
import argparse
import json
import os
from pathlib import Path
import signal
import time

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from run_multistep import (MODEL, reserve, current_rows, gate_directory, verify_source,
                          read, write, sha, need, record_of)
from patrol_rsi.multistep_workflow import Workflow, SCOPES, RANKERS, TOOLS
try:
    from patrol_rsi.multistep_proposal import compile_compact
except ModuleNotFoundError as error:
    if error.name != 'patrol_rsi.multistep_proposal':
        raise
    from multistep_proposal_v1 import compile_compact


def feedback(rows):
    result = []
    for case in sorted({r['case_id'] for r in rows}):
        own = [r for r in rows if r['case_id'] == case]
        d = record_of(next(r for r in own if r['arm'] == 'D'))
        observations = []
        for item in d['optional_chain']:
            event, info = item['completed'], item['information']
            observations.append({'dispatch': item['dispatch_time_s'], 'complete': event['time_s'],
                'agent': event['agent'], 'task': event['task'], 'profession': event['kind'],
                'pod': item['before_task']['pod'], 'reference': event['measurement'], 'measured_alarm': event['alarm'],
                'prior_reference': [info['prior_qualified'].get('time_s'), info['prior_qualified'].get('value')],
                'same_time_remote': [info['contemporaneous_remote_same_quantity'], info['remote_value']]})
        choices = [[f['time_s'], f['state'], f['selected']['task'],
                    (f['frozen_second_if_currently_legal'] or {}).get('task')]
                   for f in d['workflow_frames'] if f['selected'] is not None]
        scores = {r['arm']: [r['metrics'][key] for key in ('missed_segments',
            'consequence_weighted_censored_delay_s', 'travel_m', 'service_s', 'selected_detours')]
            for r in own}
        result.append({'case': case, 'simulation_development_scores': scores,
                       'actual_qualified_completions': observations, 'actual_choices': choices})
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    need('SLURM_JOB_ID' in os.environ and not torch.cuda.is_available(), 'CPU Slurm allocation')
    root, source = args.root.resolve(), args.source.resolve()
    signature = verify_source(source)
    gate = read(gate_directory(root, source) / 'complete.json')
    need(gate['passed'] and gate['source_manifest_sha256'] == signature, 'Exact v3 interface/safety gate')
    rows = [r for r in current_rows(root, source) if r['arm'] in ('A', 'B', 'C', 'D')]
    need(len(rows) == 24 and all(r['audit']['passed'] for r in rows), 'Only actual completed development records')
    need(not (root / 'child-workflow.json').exists(), 'One legal child only')
    area = root / 'model-compact'
    area.mkdir(exist_ok=False)
    deadline = time.monotonic() + 270
    torch.set_num_threads(int(os.environ['SLURM_CPUS_PER_TASK']))
    # Reuse the full byte verification performed by the immediately preceding
    # CPU job, with exact manifest, sizes and unchanged write times checked now.
    prior = read(root / 'model-cpu/startup.json')['verified_model']
    manifest = read(MODEL / 'verified_manifest.json')
    need(sha(MODEL / 'verified_manifest.json') == prior['manifest_sha256'], 'Same fully verified model manifest')
    first_call = json.loads((root / 'model-calls.jsonl').read_text().splitlines()[0])
    for row in manifest['files']:
        path = MODEL / row['file']
        need(path.stat().st_size == row['bytes'] and path.stat().st_mtime <= first_call['unix'], 'No model file rewritten since full verification')
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32,
        attn_implementation='eager', local_files_only=True, trust_remote_code=False).eval()
    versions = tuple(v._version for v in model.parameters())
    write(area / 'startup.json', {'job_id': os.environ['SLURM_JOB_ID'], 'device': 'cpu', 'dtype': 'float32',
        'threads': torch.get_num_threads(), 'source_manifest_sha256': signature,
        'proposal_sidecar_sha256': sha(Path(__file__)), 'verification': 'Prior full byte verification + current same manifest/size/old-mtime; no repeated shard hash',
        'prior_verification': prior, 'training': False})
    parent = Workflow()
    public = feedback(rows)
    failures = []
    for local_index in range(2):
        if time.monotonic() + 70 > deadline:
            break
        user = {'task': 'Propose ONE executable inspection workflow change. Output exactly TWO keys: changes and mechanism.',
            'parent_workflow': parent.to_dict(),
            'raw_reply_contract': {'changes': {'after_alarm': 'one allowed value'}, 'mechanism': 'One short English sentence'},
            'metadata_contract': 'The interface attaches its fixed schema and exact parent SHA. You must NOT output those metadata keys. No missing/extra raw keys are repaired.',
            'allowed_changed_fields': {'after_alarm': SCOPES, 'after_normal': SCOPES, 'ranker': RANKERS, 'estimator': TOOLS},
            'semantics': 'after_alarm/after_normal choose scope AFTER the actual first reference; prefer safe scoped tasks then supported global tasks; return_tour skips further checks. risk_lead ranks signal*importance*lead; urgency ranks age+cost ratios; risk_per_cost ranks signal/effort. estimator selects existing CVAE+nominal outputs or nominal only, never true temperature.',
            'constraints': 'Change1or2 enum fields only. K=2, qualifications, safety, data, scoring, physics and owners are immutable. All actual FIRST references supplied below were positive; editing only after_normal has no exercised opportunity here. Improvement is not required, but explain a concrete mechanism.',
            'score_columns': ['missed_segments', 'weighted_censored_wait_seconds_or_null', 'travel_m', 'service_s', 'extra_checks'],
            'choice_columns': ['time_s', 'branch', 'selected_task', 'precommitted_task_if_legal'],
            'feedback_label': 'Completed simulation DEVELOPMENT feedback. No hidden schedule, seed, oracle or validation/test labels are supplied to you or online control.',
            'public_development': public, 'prior_compact_failures': failures}
        rendered = tokenizer.apply_chat_template([{'role': 'system', 'content': 'Return only one JSON object with exactly changes and mechanism. No prose, metadata keys or code. Use only supplied public development feedback.'},
            {'role': 'user', 'content': json.dumps(user)}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(rendered, return_tensors='pt')
        count = int(inputs['input_ids'].numel())
        need(count <= 4096, 'Compact prompt hard token bound')
        receipt = reserve(root, 'model-calls', 4, {'device': 'cpu', 'raw_contract': 'compact-v1',
            'parent_sha256': parent.sha256, 'proposal_sidecar_sha256': sha(Path(__file__))})
        call = area / f"call-{receipt['number']:02d}"
        call.mkdir()
        write(call / 'start.json', {'receipt': receipt, 'prompt': user, 'rendered_prompt': rendered,
            'input_tokens': count, 'output_cap': 256, 'thinking': False, 'decoder': 'greedy'})
        response = None
        begin = time.perf_counter()
        def timeout(signum, frame):
            raise TimeoutError('Compact CPU real call timed out and remains charged')
        previous = signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, min(180, deadline - time.monotonic() - 10))
        try:
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=256, do_sample=False)
            response = tokenizer.decode(generated[0, count:], skip_special_tokens=True)
            write(call / 'response.json', {'raw_response': response, 'output_tokens': int(generated.shape[1] - count),
                'seconds': time.perf_counter() - begin, 'device': 'cpu', 'raw_contract': 'compact-v1'})
            child, envelope = compile_compact(response, parent)
            need(tuple(v._version for v in model.parameters()) == versions, 'No model training')
            write(call / 'accepted-interface.json', {'child': child.to_dict(), 'child_sha256': child.sha256,
                'assembled_envelope': envelope, 'fixed_metadata_added_by_interface': True,
                'raw_compact_valid': True, 'raw_full_envelope_claimed': False})
            write(root / 'child-workflow.json', {'workflow': child.to_dict(), 'parent': parent.to_dict(),
                'parent_sha256': parent.sha256, 'proposal_response_path': str(call / 'response.json'),
                'proposal_response_sha256': sha(call / 'response.json'), 'assembled_envelope': envelope,
                'raw_contract': 'compact-v1', 'device': 'cpu', 'proposal_sidecar_sha256': sha(Path(__file__)),
                'environment_execution_source_sha256': signature})
            print('LEGAL_COMPACT_CHILD', receipt['number'], child.sha256, flush=True)
            return
        except Exception as error:
            write(call / 'failed.json', {'type': type(error).__name__, 'error': str(error), 'raw_response': response,
                'call_charged': True, 'seconds': time.perf_counter() - begin, 'unknown_output_upper_bound': 256})
            failures.append({'error': str(error)})
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    write(area / 'no-child.json', {'failures': failures, 'no_free_retry': True})


if __name__ == '__main__':
    main()
