"""Assemble the ticket 27 root acceptance packet from completed, preserved files."""
import json
from pathlib import Path
import shutil
import sys
import zipfile

import verify_27_root_packet as v

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work'
PACKET = ROOT / v.PACKET
RUN = ROOT / 'runs/mainline-M4-27-root-acceptance-20261107-01'
LAUNCH = WORK / '27-root-full-launch-01'
REVIEW_FOLDERS = [
    '27-contract-spec-review-01', '27-contract-standards-review-01',
    '27-service-spec-review-01', '27-service-standards-review-01',
    '27-replay-spec-review-01', '27-replay-standards-review-01',
    '27-frozen-spec-review-01', '27-frozen-spec-review-01/revision-02', '27-frozen-spec-review-01/revision-03',
    '27-frozen-standards-review-01', '27-frozen-standards-review-02', '27-frozen-standards-review-03',
    '27-replay-continuation-spec-01', '27-replay-continuation-standards-01',
    '27-saved-spec-review-01', '27-saved-standards-review-01',
]
EXPORTED_UNSEALED = {
    '27-replay-continuation-spec-01': {'export/' + v.AUTHOR + '/capture-02-launch/manifest.json'},
    '27-saved-spec-review-01': {'export/' + v.AUTHOR + f'/capture-{n}-launch/manifest.json' for n in ('02', '03')},
}
SUPPORT = (
    '27-clock-validator-check-01.json', '27-contract-root-review-01.json', '27-fresh-author-01.json',
    '27-independent-acceptance-gates-01.json', '27-independent-hydraulic-witness-01.json',
    '27-retained-original-review-01.json',
)


def write_text(path, content):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)


def write_archive(path, inputs):
    members = {}
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, source in sorted(inputs.items()):
            raw = source.read_bytes()
            archive.writestr(name, raw)
            members[name] = v.identity(raw)
    return members


def review_inputs():
    result, rows = {}, []
    for name in REVIEW_FOLDERS:
        folder = WORK / name
        seal = 'manifest.json' if (folder / 'manifest.json').exists() else 'delivery-manifest.json'
        bound = v.read(folder / seal)['artifacts']
        files = v.durable_files(folder)
        if name == '27-frozen-spec-review-01':
            files = {p for p in files if not p.startswith(('revision-02/', 'revision-03/'))}
        extras = EXPORTED_UNSEALED.get(name, set())
        v.require(files == set(bound) | {seal} | extras, f'Undeclared review files: {name}')
        for rel, identity in bound.items():
            v.require(v.identity((folder / rel).read_bytes()) == identity, f'Sealed review artifact changed: {name}/{rel}')
        for rel in extras:
            raw = v.blobs(ROOT, v.AUTHOR_DATA, [rel.removeprefix('export/')])[rel.removeprefix('export/')]
            v.require((folder / rel).read_bytes() == raw, f'Supplemental source export differs: {rel}')
        result.update({name + '/' + rel: folder / rel for rel in files})
        review = v.read(folder / 'review.json')
        rows.append(dict(folder=name, seal=seal, seal_sha256=v.digest((folder / seal).read_bytes()),
                         unsealed_git_exports=sorted(extras),
                         **{k: review[k] for k in ('axis', 'checks', 'status', 'unresolved')}))
    return result, rows


def fixtures(attempt):
    sources, cases = {}, {}
    for group in v.FIXTURE_GROUPS:
        old = set(attempt['fixture_baseline'][group])
        folder = WORK / group
        current = {p.name: p for p in folder.iterdir() if p.is_dir()}
        v.require(old <= set(current), f'Preexisting fixture removed during root full: {group}')
        cases[group] = {}
        for name in sorted(set(current) - old):
            run = current[name]
            replay = group == '27-replay-development'
            launch = v.read(run / ('development-attempt.json' if replay else 'attempt.json'))
            v.require(launch['source_commit'] == v.ROOT_SOURCE, f'Unexpected concurrent fixture: {group}/{name}')
            cases[group][name] = v.read(run / ('recorded/attempt.json' if replay else 'terminal.json'))['status']
            sources.update({f'{group}/{name}/{rel}': run / rel for rel in v.durable_files(run)})
    v.require(len(cases['27-development']) == 1 and len(cases['27-replay-development']) == 2
              and len(cases['26-online-development']) > 0, 'Not all expected test fixture records were generated')
    return sources, cases


def main():
    v.require(not PACKET.exists() and not (ROOT / v.AUTHORITY).exists(), 'Packet or authority already exists')
    v.require(v.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == v.ROOT_SOURCE and not v.git(ROOT, 'status', '--porcelain'),
              'Run the packager on the unchanged exact integrated source')
    attempt, terminal = (v.read(LAUNCH / name) for name in ('attempt.json', 'terminal.json'))
    summary, guard = (v.read(RUN / name) for name in ('summary.json', 'source-guard.json'))
    tests = summary['tests']
    v.require(terminal['status'] == 'COMPLETED' and terminal['returncode'] == 0 and summary['overall'] == 'PASS'
              and tests['run'] == tests['executed'] == 567 and tests['failures'] == tests['errors'] == tests['skipped'] == 0
              and summary['verified_original_files'] == 20 and guard['sources_unchanged'] and guard['head_unchanged'],
              'Integrated regression not fully passed')
    review_sources, reviews = review_inputs()
    fixture_sources, fixture_cases = fixtures(attempt)
    visual = WORK / '27-visual-qa-02'
    draft = WORK / '27-visual-qa-01'
    declared_files = {
        **{f'raw/{name}': RUN / name for name in ('summary.json', 'evidence.json', 'tests.log', 'source-guard.json')},
        **{f'launch/{name}': LAUNCH / name for name in ('attempt.json', 'terminal.json', 'process.json', 'stdout.txt', 'stderr.txt')},
        **{f'figures/{name}': visual / name for name in (*sorted(v.FIGURES), 'render.json', 'visual-review.json')},
        **{f'visual-draft/{name}': draft / name for name in (*sorted(v.FIGURES), 'render.json')},
        **{f'checks/{name}': WORK / name for name in SUPPORT},
        'verify_packet.py': WORK / 'verify_27_root_packet.py',
        'tools/build_packet.py': Path(__file__),
        'tools/render_27_loop.py': WORK / 'render_27_loop.py',
        'tools/root_runner.py': WORK / 'run_27_root_acceptance.py',
        'tools/root_launcher.py': WORK / 'launch_27_root_full_01.py',
        'README.md': WORK / '27-root-report.md',
    }
    declared = sorted(set(declared_files) | {'.gitattributes', 'declaration.json', 'inventory.json', 'reviews.zip', 'root-fixtures.zip'})
    PACKET.mkdir(parents=True)
    v.write_new(PACKET / 'declaration.json', dict(schema='aegisdc-root27-durable-delivery-v1', artifacts=declared,
        terminal='receipt.json', execution_source=v.ROOT_SOURCE, retained_original=v.ORIGINAL_DATA,
        capture_delivery=v.AUTHOR_DATA, exclusions=['__pycache__', '*.pyc', '*.pyo'],
        archive_roles={'reviews.zip': sorted(review_sources), 'root-fixtures.zip': sorted(fixture_sources)}))
    for name, source in declared_files.items():
        target = PACKET / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    exact = ('raw/summary.json', 'raw/evidence.json', 'raw/tests.log', 'launch/stdout.txt', 'launch/stderr.txt')
    write_text(PACKET / '.gitattributes', '# Preserve exact native regression streams.\n' + ''.join(
        f'{name} -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n' for name in exact) +
        '# Preserve Matplotlib SVG path whitespace and native line endings exactly.\n' +
        'figures/*.svg -text whitespace=-blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\nvisual-draft/*.svg -text whitespace=-blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n')
    archives = {name: write_archive(PACKET / name, sources) for name, sources in (
        ('reviews.zip', review_sources), ('root-fixtures.zip', fixture_sources),
    )}
    for axis, checks in v.REVIEW_COUNTS.items():
        row, = [row for row in reviews if row['axis'] == axis and row['folder'].startswith('27-saved-')]
        v.require(row['checks'] == checks and row['seal_sha256'] == v.REVIEW_SEALS[axis], f'Final {axis} seal differs')
    v.write_new(PACKET / 'inventory.json', dict(archives=archives, reviews=reviews, root_fixture_cases=fixture_cases,
        classification='Root test-created engineering fixtures and preserved review stages, separate from frozen capture budget.',
        original_source=v.ORIGINAL_SOURCE, original_data=v.ORIGINAL_DATA, replay_source=v.REPLAY_SOURCE, author_data=v.AUTHOR_DATA))
    v.require(v.durable_files(PACKET) == set(declared), 'Actual packet differs from predeclared durable set')
    v.write_new(PACKET / 'receipt.json', dict(status='CANDIDATE_PENDING_FRESH_DELIVERY', tested_source=v.ROOT_SOURCE,
        artifacts={name: v.identity((PACKET / name).read_bytes()) for name in declared},
        registered_research_trials=0))
    gate = dict(status='CANDIDATE_PENDING_FRESH_DELIVERY', ticket='27', milestone='M4', actual_root_source=v.ROOT_SOURCE,
        original_source=v.ORIGINAL_SOURCE, original_data_delivery=v.ORIGINAL_DATA, replay_source=v.REPLAY_SOURCE,
        author_data_delivery=v.AUTHOR_DATA, root_tests=tests, guarded_files=len(guard['committed_sources']),
        historical_originals=20, independent_final_checks=v.REVIEW_COUNTS, packet=v.PACKET,
        packet_receipt_sha256=v.digest((PACKET / 'receipt.json').read_bytes()),
        remaining_gate='FRESH_COMMITTED_DELIVERY_VERIFICATION', physical_runs=2, simulated_duration_s=20,
        retained_outer_failures=1, replay_passes=1, registered_research_trials=0,
        field_calibration='PENDING', overall_goal='ACTIVE')
    v.write_new(ROOT / v.AUTHORITY, gate)
    print(json.dumps(dict(packet_artifacts=len(declared), archive_members={k: len(m) for k,m in archives.items()},
                          fixture_cases={k: len(c) for k,c in fixture_cases.items()}, source=gate['actual_root_source'],
                          guarded_files=gate['guarded_files'], root_tests=tests, status=gate['status']), ensure_ascii=False))


if __name__ == '__main__':
    main()
