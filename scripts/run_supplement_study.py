"""Execute the separately registered supplemental benchmark and retain attempts.

The JSON protocol is the study authority. No historical evidence is rewritten.
Run with PYTHONPATH=src;<isolated torch dependencies> and the bundled Python.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
PROTOCOL = ROOT / 'configs/supplement-benchmark-20261103.json'
OUT = ROOT / 'runs/supplement-benchmark-20261103'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, default=clean, allow_nan=False) + '\n'
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(payload, encoding='utf-8', newline='\n')
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def append_log(path, value):
    with Path(path).open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, default=clean, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def source_hashes():
    paths = [PROTOCOL, Path(__file__).resolve(), *sorted((ROOT / 'src/patrol_rsi').glob('*.py'))]
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in paths}


def torch_runtime(seed=0):
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.cuda.set_per_process_memory_fraction(.35)
    return torch


class Study:
    def __init__(self):
        self.protocol = read_json(PROTOCOL)
        self.ledger = OUT / 'attempts.jsonl'
        self.runtime = None

    def freeze(self):
        if (OUT / 'seal.json').exists():
            self.check_seal()
            return
        torch = torch_runtime()
        OUT.mkdir(parents=True, exist_ok=True)
        write_json(OUT / 'protocol.json', self.protocol)
        seal = {'study_id': self.protocol['study_id'], 'sealed_at': now(),
                'source_hashes': source_hashes(), 'protocol_sha256': sha(OUT / 'protocol.json'),
                'git_parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'runtime': {'python': sys.version, 'numpy': np.__version__, 'torch': torch.__version__,
                            'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                            'platform': platform.platform(), 'torch_threads': 2, 'memory_fraction': .35,
                            'deterministic_algorithms': True, 'tf32': False},
                'interpretation': 'New supplemental study; historical packages remain sealed. Final tests are never used to select checkpoints.'}
        write_json(OUT / 'seal.json', seal)
        print(json.dumps({'event': 'sealed', 'study': seal['study_id'], 'runtime': seal['runtime']}, ensure_ascii=False), flush=True)

    def check_seal(self):
        seal = read_json(OUT / 'seal.json')
        if seal['source_hashes'] != source_hashes():
            raise RuntimeError('Study sources changed after sealing; record an explicit engineering amendment first')
        if seal['protocol_sha256'] != sha(OUT / 'protocol.json'):
            raise RuntimeError('Sealed protocol changed')

    def entries(self):
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text(encoding='utf-8').splitlines() if line]

    def status(self):
        rows = self.entries()
        counts = Counter((r['phase'], r['status']) for r in rows)
        return {'attempts': sum(r['status'] == 'started' for r in rows),
                'counts': {f'{phase}:{status}': n for (phase, status), n in sorted(counts.items())},
                'last': rows[-1] if rows else None}

    @contextmanager
    def attempt(self, phase, identifier, environment=True, **metadata):
        self.check_seal()
        rows = self.entries()
        earlier = [r for r in rows if r['phase'] == phase and r['id'] == identifier]
        if earlier:
            raise RuntimeError('Attempt ID already exists: ' + identifier)
        unresolved = {r['id'] for r in rows if r['phase'] == phase and r['status'] in ('failed', 'started')}
        resolved = {r['id'] for r in rows if r['phase'] == phase and r['status'] == 'completed'}
        # Failed attempts may only be retried after a separately recorded amendment.
        amendments = read_json(OUT / 'amendments.json') if (OUT / 'amendments.json').exists() else []
        authorized = {item for a in amendments for item in a.get('resolved_attempt_ids', [])}
        if unresolved - resolved - authorized:
            raise RuntimeError('Phase has an unresolved failure/interruption: ' + str(unresolved - resolved - authorized))
        limit_key = {'compatibility': 'compatibility_environment_attempts', 'pilot': 'pilot_environment_attempts',
                     'collect_train': 'training_observation_collection', 'collect_development': 'development_observation_collection',
                     'ppo_train': 'ppo_training_environment_attempts', 'ppo_development': 'ppo_development_diagnostics',
                     'test': 'test_environment_attempts', 'scale': 'physics_only_scale_runs'}.get(phase)
        used = sum(r['phase'] == phase and r['status'] == 'started' for r in rows)
        extra = sum(a.get('additional_attempts', {}).get(phase, 0) for a in amendments)
        if environment and limit_key and used >= self.protocol['limits'][limit_key] + extra:
            raise RuntimeError('Registered phase budget exhausted')
        start = time.perf_counter()
        event = {'phase': phase, 'id': identifier, 'environment': environment, 'at': now(), **metadata}
        append_log(self.ledger, dict(event, status='started'))
        try:
            yield
        except BaseException as error:
            append_log(self.ledger, dict(event, status='failed', finished_at=now(), wall_s=time.perf_counter()-start,
                                         error=repr(error), traceback=traceback.format_exc()))
            raise
        else:
            append_log(self.ledger, dict(event, status='completed', finished_at=now(), wall_s=time.perf_counter()-start))

    def done(self, phase, identifier):
        return any(r['phase'] == phase and r['id'] == identifier and r['status'] == 'completed' for r in self.entries())

    def save_episode(self, folder, record, arrays, context_stride=None):
        from patrol_rsi.supplement_metrics import episode_summary
        folder.mkdir(parents=True, exist_ok=True)
        summary = episode_summary(record, arrays)
        with gzip.open(folder / 'record.json.gz', 'wt', encoding='utf-8') as stream:
            json.dump(record, stream, default=clean, allow_nan=False, separators=(',', ':'))
        if context_stride:
            arrays = dict(arrays)
            arrays['context_clock_indices'] = np.arange(0, 360, context_stride)
            arrays['public_context'] = arrays['public_context'][::context_stride]
        np.savez_compressed(folder / 'arrays.npz', **arrays)
        write_json(folder / 'summary.json', summary)
        write_json(folder / 'files.json', {p.name: sha(p) for p in folder.iterdir() if p.name != 'files.json'})
        return summary

    def episode(self, phase, identifier, case, method, predictor=None, policy=None, stochastic=False, collect=False, **metadata):
        from patrol_rsi.supplement_task import run_episode
        folder = OUT / phase / identifier
        if self.done(phase, identifier):
            return read_json(folder / 'summary.json'), None
        with self.attempt(phase, identifier, case_id=case['id'], family=case['family'], physical_seed=case['spec']['seed'],
                          method=method, **metadata):
            record, arrays, rollout = run_episode(case['spec'], method, predictor, policy, stochastic, collect)
            record['supplement_metadata'] = {'phase': phase, 'id': identifier, 'case': case, **metadata}
            summary = self.save_episode(folder, record, arrays, self.protocol['estimator']['snapshot_stride_steps'] if collect and phase.startswith('collect_') else None)
            print(json.dumps({'phase': phase, 'id': identifier, 'confirmed': summary['confirmed_segments'],
                              'segments': summary['anomaly_segments'], 'completed': summary['completed_inspections']}, ensure_ascii=False), flush=True)
        return summary, rollout

    def preflight(self):
        from patrol_rsi.supplement_task import run_episode
        for item in self.protocol['compatibility']:
            identifier = item['method']
            if self.done('compatibility', identifier):
                continue
            with self.attempt('compatibility', identifier, source=item['source']):
                with gzip.open(ROOT / item['source'], 'rt', encoding='utf-8') as stream:
                    old = json.load(stream)
                record, arrays, _ = run_episode(old['spec'], item['method'])
                checks = {'actions': record['action_log'] == old['action_log'],
                          'process': record['process_sha256'] == old['process_sha256']}
                write_json(OUT / 'compatibility' / (identifier + '.json'), checks)
                if not all(checks.values()):
                    raise RuntimeError('Historical nominal action/process compatibility failed: ' + str(checks))
        cases = {r['id']: r for r in self.protocol['case_sets']['development']}
        result = {}
        for identifier in self.protocol['pilot_case_ids']:
            case = cases[identifier]
            summary, _ = self.episode('pilot', identifier, case, 'fifo', collect=True)
            result[case['family']] = summary
        write_json(OUT / 'pilot-summary.json', result)
        primary = [r['id'] for r in self.protocol['families'] if r['primary']]
        if any(result[k]['anomaly_segments'] == 0 for k in primary):
            raise RuntimeError('Development pilot lacks a primary-family anomaly; inspect before collection/training')
        print(json.dumps({'event': 'preflight_passed', 'segments': {k: r['anomaly_segments'] for k, r in result.items()}}), flush=True)

    def collect(self):
        if not (OUT / 'pilot-summary.json').exists():
            raise RuntimeError('Complete preflight first')
        for split in ('train', 'development'):
            for case in self.protocol['case_sets'][split]:
                for method in ('tour', 'fifo'):
                    self.episode('collect_' + split, case['id'] + '-' + method, case, method, collect=True)

    def dataset(self, split):
        from patrol_rsi.supplement_task import to_grid
        contexts, targets, weights = [], [], []
        for case in self.protocol['case_sets'][split]:
            for method in ('tour', 'fifo'):
                identifier = case['id'] + '-' + method
                if not self.done('collect_' + split, identifier):
                    raise RuntimeError('Incomplete observation collection')
                with np.load(OUT / ('collect_' + split) / identifier / 'arrays.npz') as arrays:
                    indices = arrays['context_clock_indices']
                    contexts.append(arrays['public_context'])
                    targets.append(np.stack([to_grid(row) for row in (arrays['true_temperature_c'][indices]-50)/20])[:, None])
                    weights.append(np.broadcast_to(to_grid(arrays['rack_weights']), (len(indices), 1, 8, 16)).copy())
        return tuple(np.concatenate(parts).astype(np.float32) for parts in (contexts, targets, weights))

    def train_estimator(self):
        from patrol_rsi.supplement_models import ResidualConditionalUNet
        torch = torch_runtime()
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        train = self.dataset('train')
        development = self.dataset('development')
        settings = self.protocol['estimator']
        batch = settings['batch_size']
        architecture = {'channels': 57, 'width': settings['channels'][0], 'latent': settings['latent']}
        for seed in self.protocol['model_seeds']:
            identifier = f'cvae-{seed}'
            if self.done('estimator_train', identifier):
                continue
            with self.attempt('estimator_train', identifier, environment=False, model_seed=seed):
                torch_runtime(seed)
                model = ResidualConditionalUNet(**architecture).to(device)
                optimizer = torch.optim.Adam(model.parameters(), lr=settings['learning_rate'])
                generator = np.random.default_rng(seed)
                history, best = [], float('inf')
                training_started = time.perf_counter()
                for epoch in range(1, settings['epochs']+1):
                    model.train()
                    order = generator.permutation(len(train[0]))
                    losses, reconstructions, kls = [], [], []
                    beta = settings['kl_beta'] * min(1, epoch/settings['kl_ramp_epochs'])
                    for start in range(0, len(order), batch):
                        index = order[start:start+batch]
                        x, y, w = [torch.as_tensor(a[index], device=device) for a in train]
                        optimizer.zero_grad()
                        loss, reconstruction, kl = model.loss(x, y, w, beta)
                        if not torch.isfinite(loss):
                            raise RuntimeError('Nonfinite CVAE loss')
                        loss.backward()
                        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                        optimizer.step()
                        losses.append(float(loss.detach()))
                        reconstructions.append(float(reconstruction)); kls.append(float(kl))
                    model.eval()
                    numerator = denominator = 0.
                    with torch.inference_mode():
                        for start in range(0, len(development[0]), batch):
                            x, y, w = [torch.as_tensor(a[start:start+batch], device=device) for a in development]
                            numerator += float(((model.prediction(x)-y).square()*w).sum())
                            denominator += float(w.sum())
                    dev_mse = numerator/denominator
                    row = {'epoch': epoch, 'train_loss': float(np.mean(losses)),
                           'train_reconstruction': float(np.mean(reconstructions)), 'train_kl': float(np.mean(kls)),
                           'kl_beta': beta, 'development_weighted_mse_normalized': dev_mse,
                           'development_weighted_rmse_c': 20*np.sqrt(dev_mse)}
                    history.append(row)
                    if dev_mse < best:
                        best = dev_mse
                        pack = {'architecture': architecture, 'state_dict': {k: v.detach().cpu() for k, v in model.state_dict().items()},
                                'model_seed': seed, 'epoch': epoch, 'development_weighted_mse': dev_mse,
                                'study_id': self.protocol['study_id'], 'source_seal_sha256': sha(OUT / 'seal.json')}
                        (OUT / 'checkpoints').mkdir(exist_ok=True)
                        torch.save(pack, OUT / 'checkpoints' / (identifier + '.pt'))
                    write_json(OUT / 'training' / (identifier + '.json'), {'model_seed': seed, 'history': history,
                               'training_snapshots': len(train[0]), 'development_snapshots': len(development[0]),
                               'parameter_count': sum(p.numel() for p in model.parameters()), 'wall_s': time.perf_counter()-training_started,
                               'checkpoint_sha256': sha(OUT / 'checkpoints' / (identifier + '.pt'))})
                    print(json.dumps({'phase': 'estimator_train', 'seed': seed, **row}), flush=True)
                del model, optimizer
                if device == 'cuda':
                    torch.cuda.empty_cache()

    def predictor(self, seed):
        from patrol_rsi.supplement_models import load_temperature_predictor
        torch = torch_runtime()
        predictor = load_temperature_predictor(OUT / 'checkpoints' / f'cvae-{seed}.pt', 'cuda' if torch.cuda.is_available() else 'cpu')
        context = np.zeros((57, 8, 16), dtype=np.float32)
        for _ in range(self.protocol['estimator']['warmup_calls']):
            predictor(context, np.full(128, 50.))
        return predictor

    def train_policy(self):
        from patrol_rsi.supplement_models import BenchmarkPolicy, update_policy
        settings = self.protocol['ppo']
        for seed in self.protocol['model_seeds']:
            generator = np.random.default_rng(seed)
            # Each shuffled cycle contains all six families exactly once per block.
            order = []
            while len(order) < settings['episodes_per_estimator_and_model_seed']:
                blocks = generator.permutation(len(self.protocol['splits']['train_seeds']))
                for block in blocks:
                    families = generator.permutation(6)
                    order.extend(int(block)*6 + int(family) for family in families)
            order = order[:settings['episodes_per_estimator_and_model_seed']]
            write_json(OUT / 'training' / f'ppo-case-order-{seed}.json', [self.protocol['case_sets']['train'][i]['id'] for i in order])
            for estimator in ('nominal', 'cvae'):
                torch = torch_runtime(seed)
                model = BenchmarkPolicy()
                optimizer = torch.optim.Adam(model.parameters(), lr=settings['learning_rate'])
                predictor = self.predictor(seed) if estimator == 'cvae' else None
                # predictor loading/warmup resets RNG; restore paired policy sampling seed.
                torch.manual_seed(seed)
                checkpoint = OUT / 'checkpoints' / f'ppo-{estimator}-{seed}.pt'
                history_path = OUT / 'training' / f'ppo-{estimator}-{seed}.json'
                history = []
                first = 0
                if checkpoint.exists():
                    pack = torch.load(checkpoint, map_location='cpu', weights_only=False)
                    model.load_state_dict(pack['state_dict']); optimizer.load_state_dict(pack['optimizer'])
                    torch.set_rng_state(pack['torch_rng']); first = pack['episodes']
                    history = read_json(history_path)['history']
                initial = hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in model.parameters())).hexdigest()
                for index in range(first, len(order)):
                    case = self.protocol['case_sets']['train'][order[index]]
                    identifier = f'{estimator}-{seed}-{index+1:03}'
                    # Training attempt includes its PPO update and checkpoint as one recoverable unit.
                    from patrol_rsi.supplement_task import run_episode
                    with self.attempt('ppo_train', identifier, case_id=case['id'], family=case['family'],
                                      physical_seed=case['spec']['seed'], model_seed=seed, estimator=estimator):
                        record, arrays, rollout = run_episode(case['spec'], 'ppo', predictor, model, True, False)
                        record['supplement_metadata'] = {'phase': 'ppo_train', 'id': identifier, 'case': case,
                                                         'model_seed': seed, 'estimator': estimator, 'episode': index+1}
                        summary = self.save_episode(OUT / 'ppo_train' / identifier, record, arrays)
                        update = update_policy(model, optimizer, rollout)
                        history.append({'episode': index+1, 'case_id': case['id'], **update,
                                        'confirmed': summary['confirmed_segments'], 'segments': summary['anomaly_segments']})
                        write_json(history_path, {'model_seed': seed, 'estimator': estimator, 'history': history,
                                                 'initial_weights_sha256': initial if first == 0 else read_json(history_path)['initial_weights_sha256']})
                        torch.save({'state_dict': model.state_dict(), 'optimizer': optimizer.state_dict(),
                                    'episodes': index+1, 'torch_rng': torch.get_rng_state(), 'model_seed': seed,
                                    'estimator': estimator, 'study_id': self.protocol['study_id']}, checkpoint)
                        print(json.dumps({'phase': 'ppo_train', 'id': identifier, 'case': case['id'], **update}), flush=True)
                del model, optimizer, predictor

    def policy(self, estimator, seed):
        from patrol_rsi.supplement_models import BenchmarkPolicy
        torch = torch_runtime()
        pack = torch.load(OUT / 'checkpoints' / f'ppo-{estimator}-{seed}.pt', map_location='cpu', weights_only=False)
        if pack['episodes'] != self.protocol['ppo']['episodes_per_estimator_and_model_seed']:
            raise RuntimeError('Final policy training incomplete')
        policy = BenchmarkPolicy()
        policy.load_state_dict(pack['state_dict'])
        return policy.eval()

    def development(self):
        cases = {r['id']: r for r in self.protocol['case_sets']['development']}
        for seed in self.protocol['model_seeds']:
            for estimator in ('nominal', 'cvae'):
                predictor = self.predictor(seed) if estimator == 'cvae' else None
                policy = self.policy(estimator, seed)
                for identifier in self.protocol['ppo']['development_case_ids']:
                    self.episode('ppo_development', f'{identifier}-{estimator}-{seed}', cases[identifier], 'ppo', predictor, policy,
                                 model_seed=seed, estimator=estimator)

    def freeze_checkpoints(self):
        paths = sorted((OUT / 'checkpoints').glob('*.pt'))
        if len(paths) != 9:
            raise RuntimeError('Expected three estimators and six final policies')
        selection = {p.name: sha(p) for p in paths}
        path = OUT / 'test-checkpoint-lock.json'
        if path.exists():
            if read_json(path)['checkpoints'] != selection:
                raise RuntimeError('Checkpoint changed after final-test lock')
        else:
            write_json(path, {'at': now(), 'checkpoints': selection, 'rule': 'CVAE by development MSE; PPO fixed episode120; no final-test selection'})

    def test(self):
        self.freeze_checkpoints()
        # Shared physical cases are adjacent for simulator-cache reuse.
        predictors = {seed: self.predictor(seed) for seed in self.protocol['model_seeds']}
        policies = {(estimator, seed): self.policy(estimator, seed)
                    for estimator in ('nominal', 'cvae') for seed in self.protocol['model_seeds']}
        for case in self.protocol['case_sets']['test']:
            for method in ('tour', 'fifo', 'greedy'):
                self.episode('test', case['id'] + '-nominal-' + method, case, method,
                             collect=method == 'tour', method_label='nominal_' + method, model_seed=None)
            for seed in self.protocol['model_seeds']:
                self.episode('test', f"{case['id']}-nominal-ppo-{seed}", case, 'ppo', policy=policies['nominal', seed],
                             method_label='nominal_ppo', model_seed=seed)
                for method in ('fifo', 'greedy', 'ppo'):
                    self.episode('test', f"{case['id']}-cvae-{method}-{seed}", case, method, predictors[seed],
                                 policies['cvae', seed] if method == 'ppo' else None, method_label='cvae_' + method, model_seed=seed,
                                 estimator_checkpoint_sha256=sha(OUT / 'checkpoints' / f'cvae-{seed}.pt'))
        self.freeze_checkpoints()

    def fixed_stream(self):
        from patrol_rsi.supplement_metrics import temperature_metrics
        from patrol_rsi.supplement_task import from_grid
        rows = []
        for seed in self.protocol['model_seeds']:
            predictor = self.predictor(seed)
            for case in self.protocol['case_sets']['test']:
                identifier = case['id'] + '-nominal-tour'
                if not self.done('test', identifier):
                    raise RuntimeError('Fixed-stream reference incomplete')
                with np.load(OUT / 'test' / identifier / 'arrays.npz') as a:
                    outputs = []
                    for i, context in enumerate(a['public_context']):
                        nominal = a['predicted_temperature_c'][i]
                        prediction = predictor(context, nominal)
                        fresh = a['fresh_measurement_mask'][i]
                        prediction[fresh] = nominal[fresh]
                        outputs.append(prediction)
                    rows.append({'case': case, 'model_seed': seed,
                                 'nominal': temperature_metrics(a['predicted_temperature_c'], a['true_temperature_c'], a['rack_weights'], a['fresh_measurement_mask']),
                                 'cvae': temperature_metrics(outputs, a['true_temperature_c'], a['rack_weights'], a['fresh_measurement_mask']),
                                 'source_arrays_sha256': sha(OUT / 'test' / identifier / 'arrays.npz')})
        write_json(OUT / 'fixed-stream-estimation.json', {'environment_runs': 0, 'prediction_calls': len(rows)*360,
                    'warmup_calls_per_loaded_checkpoint': self.protocol['estimator']['warmup_calls'], 'rows': rows})

    def scale(self):
        from patrol_rsi.active_inspection import graph_for
        from patrol_rsi.aisles import feasibility
        from patrol_rsi.facility import FacilityConfig
        from patrol_rsi.process import CompositeFacility, arrays_digest
        for racks in self.protocol['scale']['racks']:
            write_json(OUT / 'scale' / f'feasibility-{racks}.json', feasibility(graph_for(racks, 'open'), 'provisioned'))
            for seed in self.protocol['splits']['scale_seeds']:
                for family in self.protocol['scale']['families']:
                    identifier = f'{racks}-{seed}-{family}'
                    if self.done('scale', identifier):
                        continue
                    with self.attempt('scale', identifier, racks=racks, seed=seed, family=family):
                        import tracemalloc
                        tracemalloc.start()
                        started = time.perf_counter()
                        config = FacilityConfig(racks=racks, fault_rack=racks//2, fault_start_s=335, fault_end_s=515)
                        scenario = 'healthy' if family == 'healthy' else 'aux_feeder_loss+cdu_fouling'
                        plant = CompositeFacility(config, seed, scenario, 'feedback')
                        values, energy, electric, powers = [], [], [], []
                        for _ in range(360):
                            row = plant.step()
                            values.append(row['rack_temperature_c'])
                            energy.append(abs(row['energy_residual_kj'])); electric.append(abs(row['electric_residual_kw'])); powers.append(row['source_power_kw'])
                        elapsed = time.perf_counter()-started
                        current, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
                        a = np.stack(values)
                        write_json(OUT / 'scale' / (identifier + '.json'), {'racks': racks, 'seed': seed, 'family': family,
                            'wall_s_with_tracemalloc': elapsed, 'python_traced_peak_bytes': peak,
                            'temperature_array_bytes': a.nbytes, 'physical_temperature_sha256': arrays_digest({'T': a}),
                            'max_energy_residual_kj': max(energy), 'max_electric_residual_kw': max(electric),
                            'peak_source_input_MW': max(powers)/1000, 'physical_steps': 360, 'scheduling_episodes': 0})
                        print(json.dumps({'phase': 'scale', 'id': identifier, 'wall_s': elapsed, 'peak_bytes': peak}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['freeze', 'preflight', 'collect', 'train-estimator', 'train-policy', 'development', 'test', 'fixed-stream', 'scale', 'status', 'all'])
    args = parser.parse_args()
    study = Study()
    if args.phase == 'status':
        print(json.dumps(study.status(), ensure_ascii=False, indent=2)); return
    study.freeze()
    methods = {'preflight': study.preflight, 'collect': study.collect, 'train-estimator': study.train_estimator,
               'train-policy': study.train_policy, 'development': study.development, 'test': study.test,
               'fixed-stream': study.fixed_stream, 'scale': study.scale}
    if args.phase == 'all':
        for method in methods.values():
            method()
    elif args.phase != 'freeze':
        methods[args.phase]()


if __name__ == '__main__':
    main()
