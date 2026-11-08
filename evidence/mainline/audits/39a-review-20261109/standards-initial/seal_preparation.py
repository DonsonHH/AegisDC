"""Seal small reviewer metadata packet only; no project imports or calculations."""
from pathlib import Path
import hashlib, json, subprocess

ROOT = Path(r"C:\Users\Donson\Documents\ChatGPT\Renly")
OUT = Path(__file__).resolve().parent
sha = lambda data: hashlib.sha256(data).hexdigest()
result = json.loads((OUT / 'metadata-result.json').read_bytes())
pin = result['observed_head']
git = lambda *args: subprocess.check_output(['git', '-C', str(ROOT), *args])
closure = []
for item in result['working_metadata']:
    path = item['path']
    committed = git('cat-file', 'blob', pin + ':' + path)
    assert sha(committed) == item['sha256'], ('reviewed closure differs from committed source', path)
    assert (ROOT / path).read_bytes() == committed, ('working closure changed since review', path)
    closure.append({'path': path, 'sha256': sha(committed), 'git_blob': git('rev-parse', pin + ':' + path).decode().strip(), 'bytes': len(committed)})
receipt = {'classification': 'PREPARATION_METADATA_CLOSURE_ONLY', 'fixed_initial_source': result['source'], 'closure_pin': pin, 'closure_files': closure, 'final_39a_acceptance': False, 'pending': result['awaited'], 'reviewer_activity': result['reviewer_activity']}
(OUT / 'closure-source.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
names = ['metadata_review_01.py', 'metadata_review.py', 'metadata-review-01.log', 'metadata-review-02.log', 'check-failure-classification.json', 'metadata-result.json', 'preparation-report.md', 'closure-source.json', 'seal_preparation.py']
manifest = {'schema': 'aegisdc-independent-standards-review-v1', 'scope': '39a preparation metadata closure, not final39a acceptance', 'initial_source': result['source'], 'closure_pin': pin, 'artifacts': [{'path': name, 'sha256': sha((OUT / name).read_bytes()), 'bytes': (OUT / name).stat().st_size} for name in names], 'preserves_original_failure': True, 'project_calls': 0, 'numeric_metric_recomputations': 0, 'awaited': result['awaited']}
raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
(OUT / 'preparation-manifest.json').write_bytes(raw)
print(json.dumps({'manifest_sha256': sha(raw), 'closure_pin': pin, 'files': len(names), 'scope': manifest['scope']}, ensure_ascii=False))
