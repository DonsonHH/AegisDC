"""One private remote environment preparation and tiny CUDA qualification,no model trial."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--expected-host', required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_bytes())
    plan_sha = sha(args.plan)
    root = Path(plan['private_output']).resolve()
    mount = Path('/root/private_data').resolve()
    if (os.geteuid() != 0 or platform.node() != args.expected_host
            or platform.python_version() != plan['python'] or os.environ.get('SLURM_JOB_ID')
            or not mount.is_mount() or root.parent != mount or root.name != 'aegisdc-gpu4090-env-20261110-02'
            or sha(Path(__file__)) != plan['preparation_script_sha256']):
        raise SystemExit('Pinned remote environment source,host or persistent root differs')
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                                   '--format=csv,noheader'], text=True).strip()
    if len(gpu.splitlines()) != 1 or plan['gpu_model'] not in gpu or plan['driver'] not in gpu:
        raise SystemExit('Allocated GPU or driver differs from inspected plan')
    root.mkdir(mode=0o700, exist_ok=False)
    save(root/'attempt.json', dict(classification='REMOTE_ENVIRONMENT_PREPARATION_NOT_RESEARCH',
        started_utc=datetime.now(timezone.utc).isoformat(), hostname=platform.node(), python=sys.version,
        plan_sha256=plan_sha, script_sha256=sha(Path(__file__)), gpu=gpu,
        install_invocation_budget=2, tiny_smoke_invocation_budget=1, new_research_trials=0))
    print('PREPARATION_SCRIPT_ENTERED', flush=True)
    terminal = dict(status='FAILED', new_research_trials=0, llm_inference_trials=0, training_trials=0)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='7', OPENBLAS_NUM_THREADS='7',
               TMPDIR=str(root/'tmp'), PIP_REQUIRE_VIRTUALENV='true')
    (root/'tmp').mkdir(mode=0o700)
    try:
        with (root/'install.log').open('x', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-m', 'venv', '--copies', str(root/'venv')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, env=env, timeout=120)
            python = str(root/'venv/bin/python')
            common = [python, '-m', 'pip', 'install', '--no-cache-dir', '--no-input', '--disable-pip-version-check',
                      '--progress-bar', 'off', '--timeout', '30', '--retries', '2']
            subprocess.run(common + ['numpy==2.3.5', '--index-url', 'https://pypi.org/simple',
                           '--report', str(root/'numpy-install-report.json')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, env=env, timeout=900)
            print('NUMPY_INSTALL_COMPLETED', flush=True)
            subprocess.run(common + ['torch==2.6.0', '--index-url', 'https://download.pytorch.org/whl/cu118',
                           '--report', str(root/'torch-install-report.json')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, env=env, timeout=1800)
            print('TORCH_INSTALL_COMPLETED', flush=True)
            subprocess.run([python, '-m', 'pip', 'check'], check=True, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=60)
        freeze = subprocess.check_output([python, '-m', 'pip', 'freeze', '--all'], text=True, env=env, timeout=60)
        save(root/'environment-lock.json', dict(python=platform.python_version(), packages=freeze.splitlines(),
            preparation_plan_sha256=plan_sha, numpy_install_report_sha256=sha(root/'numpy-install-report.json'),
            torch_install_report_sha256=sha(root/'torch-install-report.json'), gpu=gpu,
            source_rule='Official wheel indexes;exact installed versions and downloaded artifact hashes retained before smoke.'))
        lock_sha = sha(root/'environment-lock.json')
        smoke = '''import json,sys,torch,numpy as np
torch.set_num_threads(7)
assert torch.__version__ == "2.6.0+cu118", torch.__version__
assert np.__version__ == "2.3.5", np.__version__
assert torch.cuda.is_available() and torch.cuda.device_count()==1
assert torch.cuda.get_device_capability(0)==(8,9)
assert torch.version.cuda=="11.8"
assert torch.from_numpy(np.array([1.,2.],dtype=np.float32)).tolist()==[1.,2.]
torch.backends.cuda.matmul.allow_tf32=False
a=torch.ones((16,16),device="cuda",dtype=torch.float32)
b=a@a
torch.cuda.synchronize()
assert all(value==16.0 for row in b.cpu().tolist() for value in row)
report=dict(status="TINY_CUDA_SMOKE_PASSED",torch=torch.__version__,numpy=np.__version__,cuda_runtime=torch.version.cuda,device=torch.cuda.get_device_name(0),capability=list(torch.cuda.get_device_capability(0)),matrix_shape=[16,16],matrix_products=1,expected_each_result=16.0,torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),torch_reserved_bytes=torch.cuda.memory_reserved(0),actual_kernel_count="NOT_INSTRUMENTED",numpy_bridge="PASS",new_research_trials=0,llm_inference_trials=0,training_trials=0)
with open(sys.argv[1],"x",encoding="utf-8") as f:json.dump(report,f,indent=2);f.write("\\n")
print(json.dumps(report))
'''
        with (root/'smoke.log').open('x', encoding='utf-8') as log:
            subprocess.run([python, '-c', smoke, str(root/'cuda-smoke.json')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, env=env, timeout=120)
        if sha(root/'environment-lock.json') != lock_sha or sha(args.plan) != plan_sha:
            raise ValueError('Pinned environment lock or plan changed during smoke')
        terminal.update(status='ENVIRONMENT_AND_TINY_CUDA_SMOKE_PASSED',
                        environment_lock_sha256=lock_sha, tiny_smoke_invocations=1)
    except BaseException as error:
        terminal.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in root.iterdir() if p.is_file()})
        save(root/'terminal.json', terminal)
    print(json.dumps(terminal))


if __name__ == '__main__':
    main()
