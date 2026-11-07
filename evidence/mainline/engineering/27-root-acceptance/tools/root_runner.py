"""Single source-pinned ticket27 integrated engineering acceptance."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_CRLF = {'configs/candidate-example.json', 'configs/demo.json',
                'configs/feedback-study.json', 'configs/parent-rule.json'}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def identities():
    names = git('ls-files', '-z', 'src', 'scripts', 'tests', 'configs').decode().strip('\0').split('\0')
    names = sorted(n for n in names if n.endswith(('.py', '.json')))
    actual = {n: sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=ROOT,
        input=''.join('HEAD:' + n + '\n' for n in names).encode())
    committed, checkout_classification, offset = {}, {}, 0
    for name in names:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2]); start = end + 1
        blob = raw[start:start + size]
        committed[name] = sha256(blob).hexdigest()
        if actual[name] != committed[name]:
            assert name in CHECKOUT_CRLF, 'Undeclared source byte difference: ' + name
            checkout_bytes = (ROOT / name).read_bytes()
            assert b'\r' not in blob and checkout_bytes == blob.replace(b'\n', b'\r\n'), name
            checkout_classification[name] = dict(rule='exact_lf_to_crlf_checkout',
                actual_sha256=actual[name], committed_sha256=committed[name],
                crlf_count=checkout_bytes.count(b'\r\n'))
        offset = start + size + 1
    assert offset == len(raw)
    return dict(actual=actual, committed=committed, checkout_classification=checkout_classification)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = git('rev-parse', args.source).decode().strip()
    output = (ROOT / args.output).resolve()
    assert output.parent == ROOT / 'runs' and not output.exists()
    assert git('rev-parse', 'HEAD').decode().strip() == source
    assert git('branch', '--show-current').decode().strip() == 'donson/full-facility-mainline'
    assert not git('status', '--porcelain')
    before = identities()
    sys.path[:0] = [str(ROOT / '.work/benchmark-neural-deps'), str(ROOT / 'src'), str(ROOT / 'scripts')]
    os.environ['PYTHONPATH'] = str(ROOT / 'src')
    import numpy
    import torch
    from acceptance import verify
    result = verify(ROOT, output)
    after = identities()
    head_after = git('rev-parse', 'HEAD').decode().strip()
    guard = dict(source_commit_before=source, source_commit_after=head_after,
        actual_sources=before['actual'], committed_sources=before['committed'],
        checkout_classification=before['checkout_classification'],
        sources_match_declared_git_checkout=True, sources_unchanged=before == after,
        head_unchanged=head_after == source,
        python_executable=sys.executable, python_version=sys.version,
        python_executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
        runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        numpy=numpy.__version__, torch=torch.__version__,
        scope='Integrated engineering and historical evidence checks; no registered research, training or LLM experiment.')
    with (output / 'source-guard.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(guard, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    passed = (result['overall'] == 'PASS' and before == after and head_after == source
        and result['tests']['skipped'] == result['tests']['failures'] == result['tests']['errors'] == 0)
    print(json.dumps(dict(source=source, overall=result['overall'], tests=result.get('tests'),
        verified_original_files=result.get('verified_original_files'), guarded_files=len(before['actual']),
        source_guard='PASS' if before == after and head_after == source else 'FAIL',
        output=str(output), error=result.get('error'), root_gate='PASS' if passed else 'FAIL'), ensure_ascii=False))
    raise SystemExit(0 if passed else 1)

if __name__ == '__main__':
    main()
