"""Seal authored coverage notes and text/Git integrity evidence only."""
import hashlib,json
from pathlib import Path
out=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
receipt=json.loads((out/'receipt.json').read_bytes())
assert receipt['metric_recomputations']==receipt['project_calls']==0
manifest=dict(schema='aegisdc-independent-spec39a-scope-review-v1',
    source='f73c57f8806dcc6e23d510e83391b0f46677b6cc',
    status='CROSSSTAGE_NOTES_COMPLETE_WITH_DOC_FINDINGS',authoritative_report='report.md',
    matrix='coverage-01-38.md',meeting_notes='meeting-coverage-notes.md',
    final_root_tables_and_remote_readout_accepted=False,
    local_scope='Text authoring and pinned Git/integrity only; no project, tests, model, metric recomputation, browser, install, export, clone or worktree creation.',
    artifacts={path.name:dict(sha256=sha(path.read_bytes()),bytes=path.stat().st_size)
        for path in sorted(out.iterdir()) if path.is_file() and path.name!='original-manifest.json'},
    excluded=['Self-hash','Runtime caches'])
with (out/'original-manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(status=manifest['status'],source=manifest['source'],
    original_manifest_sha256=sha((out/'original-manifest.json').read_bytes()),
    local_metric_recomputation=False,project_calls=0)))
