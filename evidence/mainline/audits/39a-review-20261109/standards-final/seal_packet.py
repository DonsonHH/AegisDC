"""Seal reviewer artifacts and the narrow fresh-tool source disposition only."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(r"C:\Users\Donson\Documents\ChatGPT\Renly")
OUT = Path(__file__).resolve().parent
OLD = 'd73ffed453cfc5dcbe5b6865bc0d4d4183586ccb'
NEW = '79480f06804221e1dde68c083bc6ea68e4d82071'
PATH = 'scripts/verify_scope_audit_delivery.py'
git = lambda *args: subprocess.check_output(['git', '-C', str(ROOT), *args])
sha = lambda raw: hashlib.sha256(raw).hexdigest()
old = git('cat-file', 'blob', OLD + ':' + PATH)
new = git('cat-file', 'blob', NEW + ':' + PATH)
assert (ROOT / PATH).read_bytes() == new, 'current narrow tool differs from reviewed committed source'
assert sha(new) == 'b5211b64cca400292820d7b96c1bb56af30d208e07d27e4e23929502fe52dbab'
text = new.decode('utf-8')
assert text.index("manifest_bytes != git('show', commit + ':' + args.manifest)") < text.index("manifest = json.loads(manifest_bytes.decode('utf-8'))") < text.index("if type(manifest.get('artifacts')) is not dict or not manifest['artifacts']:") < text.index("for name, record in manifest['artifacts'].items():")
record = {'id': 'S39A-FRESH-01', 'priority': 'P2', 'path': PATH, 'original_line': 21, 'original_source': OLD, 'original_git_sha256': sha(old), 'original_observed_working_sha256': '00c716b18c2c6fb16ba74fa04391bff48bd68e3065ae385ac2661b954d46e74e', 'original_finding': 'Working manifest was parsed without comparing it to the declared commit. Accidental deletion of artifact entries, including an empty set, could skip report members and still yield PASS.', 'rule': 'AGENTS durable delivery must match original manifest and committed blobs; exact declared set may not be weakened by working metadata.', 'status': 'CLOSED_STATIC_ONLY', 'correction_source': NEW, 'correction_sha256': sha(new), 'closure': 'Manifest raw bytes first match the declared committed blob, then parsing rejects empty or non-dictionary artifact sets before iterating.', 'execution': 'Neither old nor corrected verifier was run by this reviewer.', 'outer_checkout_boundary': 'This verifier does not create/remove checkouts. Root must separately use no-checkout before sparse setup, materialize only declared small files and remove normally; no full source/dependency/evidence restoration is authorized.'}
with (OUT / 'fresh-tool-record.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
with (OUT / 'fresh-tool-review.diff').open('xb') as stream:
    stream.write(git('diff', OLD, NEW, '--', PATH))
names = ['review_metadata_01.py', 'review_metadata.py', 'review-01.log', 'review-02.log', 'reviewer-check-classification.json', 'findings-disposition.json', 'review-result.json', 'report.md', 'commands-and-source.json', 'fresh-tool-record.json', 'fresh-tool-review.diff', 'seal_packet.py']
manifest = {'schema': 'aegisdc-independent-standards39a-final-v1', 'status': 'PASS', 'content_source': 'c6fc3a737ba420d1fe752cce52a9aad52189bf26', 'saved_execution_source': 'cfea64cbb059e0059ea2d5e8f148d03b66011b26', 'tool_correction_source': NEW, 'scope': '39a bounded text/Git/source-output integrity and narrow fresh-tool closure; no scientific recomputation or successor-ticket acceptance', 'artifacts': {name: {'sha256': sha((OUT / name).read_bytes()), 'bytes': (OUT / name).stat().st_size} for name in names}, 'original_failure_preserved': True, 'remaining_standards_blockers': [], 'project_calls': 0, 'numeric_metric_recomputations': 0, 'excluded': ['Self hash', 'Runtime caches']}
raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
with (OUT / 'manifest.json').open('xb') as stream:
    stream.write(raw)
print(json.dumps({'status': 'PASS', 'manifest_sha256': sha(raw), 'files': len(names), 'content_source': manifest['content_source'], 'tool_correction_source': NEW}, ensure_ascii=False))
