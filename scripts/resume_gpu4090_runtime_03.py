"""Verify cached official wheels,resume missing byte ranges,and finish an unsealed private env."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import traceback
from urllib.parse import parse_qs, unquote, urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def official_wheel(filename):
    slug = re.sub('[-_.]+', '-', filename.split('-')[0]).lower()
    index = 'https://download.pytorch.org/whl/cu118/' + slug + '/'
    with urlopen(index, timeout=45) as response:
        document = response.read().decode('utf-8')
    matches = []
    for raw in re.findall(r'href=["\x27]([^"\x27]+)', document):
        link = urljoin(index, html.unescape(raw))
        parsed = urlsplit(link)
        hashes = parse_qs(parsed.fragment).get('sha256', [])
        if (unquote(parsed.path.rsplit('/', 1)[-1]) == filename and parsed.scheme == 'https'
                and parsed.hostname in ('download.pytorch.org', 'download-r2.pytorch.org')
                and len(hashes) == 1 and re.fullmatch('[a-f0-9]{64}', hashes[0])):
            matches.append((urldefrag(link).url, hashes[0]))
    if not matches or len({entry[1] for entry in matches}) != 1:
        raise ValueError('No unambiguous official wheel hash for ' + filename)
    return matches[0]


def resume_torch(original, target, url, expected_sha, workers, record_dir):
    with urlopen(Request(url, method='HEAD'), timeout=45) as response:
        total = int(response.headers['Content-Length'])
    start = original.stat().st_size
    if start >= total:
        raise ValueError('Cached partial does not precede the official total')
    original_sha = sha(original)
    shutil.copyfile(original, target)
    with target.open('r+b') as stream:
        stream.truncate(total)
    spans = []
    size = (total-start+workers-1)//workers
    for i in range(workers):
        lo, hi = start+i*size, min(total-1, start+(i+1)*size-1)
        if lo <= hi:
            spans.append((lo, hi))

    def transfer(span):
        lo, hi = span
        current = lo
        attempts = []
        for attempt in range(1, 4):
            record = dict(attempt=attempt, start=current, end=hi)
            try:
                request = Request(url, headers={'Range': f'bytes={current}-{hi}', 'Accept-Encoding': 'identity'})
                with urlopen(request, timeout=60) as response, target.open('r+b', buffering=0) as output:
                    expected = f'bytes {current}-{hi}/{total}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('Server did not honor exact authenticated byte range')
                    output.seek(current)
                    while current <= hi:
                        block = response.read(min(1024*1024, hi-current+1))
                        if not block:
                            raise EOFError('Range transfer ended early')
                        output.write(block)
                        current += len(block)
                record.update(status='COMPLETE', bytes_written=current-lo)
                attempts.append(record)
                print(f'RANGE_COMPLETE={lo}:{hi}', flush=True)
                return dict(start=lo, end=hi, attempts=attempts)
            except Exception as error:
                record.update(status='TRANSFER_STOP', error=repr(error), bytes_written=current-lo)
                attempts.append(record)
                if attempt == 3:
                    save(record_dir/f'range-failed-{lo}.json', attempts)
                    raise
        raise RuntimeError('Unreachable transfer state')

    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(transfer, spans))
    save(record_dir/'torch-resume-ranges.json', dict(original_bytes=start, total_bytes=total,
        original_sha256=original_sha, ranges=records))
    if sha(original) != original_sha or sha(target) != expected_sha:
        raise ValueError('Original prefix changed or recovered wheel failed official SHA256')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--expected-host', required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_bytes())
    plan_sha = sha(args.plan)
    root, previous = Path(plan['private_output']), Path(plan['previous_output'])
    mount = Path('/root/private_data').resolve()
    if (os.geteuid() != 0 or platform.node() != args.expected_host or platform.python_version() != '3.11.9'
            or not mount.is_mount() or root.resolve().parent != mount
            or root.name != 'aegisdc-gpu4090-env-20261110-03'
            or previous.resolve() != mount/'aegisdc-gpu4090-env-20261110-02'
            or sha(Path(__file__)) != plan['preparation_script_sha256']):
        raise SystemExit('Pinned resume source,host or private roots differ')
    original_terminal = previous/'terminal.json'
    failure = json.loads(original_terminal.read_bytes())
    if failure['status'] != 'FAILED' or not failure['error'].startswith('TimeoutExpired') or (previous/'cuda-smoke.json').exists():
        raise SystemExit('Resume only the observed pre-smoke package timeout')
    terminal_sha = sha(original_terminal)
    source = Path(plan['smoke_source'])
    if sha(source) != plan['smoke_source_sha256']:
        raise SystemExit('Previously frozen smoke source differs')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    smoke = next(node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'smoke' for target in node.targets))
    ast.parse(smoke)
    root.mkdir(mode=0o700, exist_ok=False)
    python = str(previous/'venv/bin/python')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='7', OPENBLAS_NUM_THREADS='7',
               PIP_REQUIRE_VIRTUALENV='true', PIP_CONFIG_FILE='/dev/null', TMPDIR=str(root/'tmp'))
    env.pop('PIP_EXTRA_INDEX_URL', None)
    (root/'tmp').mkdir(mode=0o700)
    wheelhouse = root/'verified-wheels'
    wheelhouse.mkdir(mode=0o700)
    save(root/'attempt.json', dict(classification='PACKAGE_TRANSFER_RESUME_INFRASTRUCTURE_NOT_RESEARCH',
        started_utc=datetime.now(timezone.utc).isoformat(), plan_sha256=plan_sha, script_sha256=sha(Path(__file__)),
        prior_terminal_sha256=terminal_sha, reused_unsealed_private_venv=str(previous/'venv'),
        original_logs_and_cached_wheels_preserved=True, new_research_trials=0))
    terminal = dict(status='FAILED', new_research_trials=0, llm_inference_trials=0, training_trials=0)
    try:
        before = subprocess.check_output([python, '-m', 'pip', 'freeze', '--all'], text=True, env=env, timeout=60)
        save(root/'packages-before-continuation.json', before.splitlines())
        inventory, paths = [], []
        for cached in sorted((previous/'tmp').rglob('*.whl')):
            url, expected = official_wheel(cached.name)
            actual = sha(cached)
            destination = wheelhouse/cached.name
            if actual == expected:
                try:
                    os.link(cached, destination)
                except OSError:
                    shutil.copyfile(cached, destination)
                print('CACHE_HASH_VERIFIED=' + cached.name, flush=True)
            elif cached.name == plan['torch_wheel']:
                resume_torch(cached, destination, url, expected, plan['range_workers'], root)
                print('TORCH_OFFICIAL_HASH_VERIFIED', flush=True)
            else:
                raise ValueError('A cached dependency is incomplete;preserve instead of adopting: ' + cached.name)
            inventory.append(dict(filename=cached.name, source_url=url, official_sha256=expected,
                                  original_sha256=actual, recovered_sha256=sha(destination)))
            paths.append(str(destination))
        save(root/'verified-wheel-inventory.json', inventory)
        if not any(Path(path).name == plan['torch_wheel'] for path in paths):
            raise ValueError('Expected recoverable Torch wheel absent')
        with (root/'install.log').open('x', encoding='utf-8') as log:
            subprocess.run([python, '-m', 'pip', 'install', '--force-reinstall', '--no-cache-dir', '--no-input',
                '--disable-pip-version-check', '--progress-bar', 'off', '--timeout', '45', '--retries', '2',
                '--index-url', 'https://download.pytorch.org/whl/cu118', '--report', str(root/'torch-install-report.json'),
                *paths], check=True, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=3600)
            subprocess.run([python, '-m', 'pip', 'check'], check=True, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=60)
        print('PACKAGE_INSTALL_COMPLETED', flush=True)
        freeze = subprocess.check_output([python, '-m', 'pip', 'freeze', '--all'], text=True, env=env, timeout=60)
        save(root/'environment-lock.json', dict(python='3.11.9', packages=freeze.splitlines(),
            private_venv=str(previous/'venv'), plan_sha256=plan_sha,
            wheel_inventory_sha256=sha(root/'verified-wheel-inventory.json'),
            install_report_sha256=sha(root/'torch-install-report.json'), prior_terminal_sha256=terminal_sha))
        lock_sha = sha(root/'environment-lock.json')
        with (root/'smoke.log').open('x', encoding='utf-8') as log:
            subprocess.run([python, '-c', smoke, str(root/'cuda-smoke.json')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, env=env, timeout=120)
        if sha(root/'environment-lock.json') != lock_sha or sha(original_terminal) != terminal_sha or sha(args.plan) != plan_sha:
            raise ValueError('Immutable lock,old failure record or preparation plan changed')
        terminal.update(status='ENVIRONMENT_AND_TINY_CUDA_SMOKE_PASSED', environment_lock_sha256=lock_sha,
                        verified_cached_wheels=len(inventory), tiny_smoke_invocations=1)
    except BaseException as error:
        terminal.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={path.name: dict(bytes=path.stat().st_size, sha256=sha(path)) for path in root.iterdir() if path.is_file()})
        save(root/'terminal.json', terminal)
    print(json.dumps(terminal))


if __name__ == '__main__':
    main()
