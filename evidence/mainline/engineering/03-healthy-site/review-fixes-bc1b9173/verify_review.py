"""Fresh-read review regressions and verify that all prior fixtures are intact."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
ROOT = HERE.parents[4]
SCHEMA_COMMIT = '037d82fb0348d89b33f1f76585c49eace5fb18f4'
LATCH_COMMIT = 'bc1b9173d8b0deb796b7a2938924dc146e0e4588'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(path):
    return sha256(path.read_bytes()).hexdigest()


def verify_saved_run(directory, expected_commit, current_source):
    manifest = read_json(directory / 'run.json')
    assert manifest['code_identity']['git_commit'] == expected_commit
    assert manifest['code_identity']['implementation_has_changes'] is False
    assert manifest['engineering_fixture'] and manifest['research_trials'] == 0
    for name, record in manifest['artifacts'].items():
        path = directory / name
        assert identity(path) == record['sha256']
        if name.endswith('.jsonl'):
            assert len(path.read_bytes().splitlines()) == record['records']
    if current_source:
        assert all(identity(ROOT / name) == value for name, value in manifest['code_identity']['files'].items())
    return manifest


def verify():
    old = read_json(FIXTURES / 'receipt-37432b25.json')
    assert all(identity(FIXTURES / name) == value for name, value in old['files_sha256'].items())
    schema_folder, latch_folder = FIXTURES / 'schema-review-fix', FIXTURES / 'latch-review-fix'
    assert "TypeError: unhashable type: 'list'" in (schema_folder / 'red.log').read_text(encoding='utf-8')
    assert "TypeError: unhashable type: 'dict'" in (schema_folder / 'red.log').read_text(encoding='utf-8')
    assert 'FAILED (failures=4, errors=2)' in (schema_folder / 'red.log').read_text(encoding='utf-8')
    assert 'Ran 36 tests' in (schema_folder / 'green.log').read_text(encoding='utf-8')
    assert "AssertionError: 'normal' != 'protected'" in (latch_folder / 'red.log').read_text(encoding='utf-8')
    assert 'Ran 37 tests' in (latch_folder / 'green.log').read_text(encoding='utf-8')
    for folder in (schema_folder, latch_folder):
        tested = read_json(folder / 'tested-source.json')
        assert all(identity(ROOT / name) == value for name, value in tested['files_sha256'].items())
    red_directory, green_directory = latch_folder / 'red-037d82fb', latch_folder / 'green-bc1b9173'
    red, green = read_json(red_directory / 'summary.json'), read_json(green_directory / 'summary.json')
    red_cycle, green_cycle = red['cases']['power-cycle'], green['cases']['power-cycle']
    assert red_cycle['final_temperature_K'] > red_cycle['reset_temperature_K']
    assert red_cycle['final_mode'] == 'normal' and red_cycle['compute_power_W'] == 2000000
    assert green_cycle['final_temperature_K'] > green_cycle['reset_temperature_K']
    assert green_cycle['final_mode'] == 'protected' and green_cycle['compute_power_W'] == 0
    assert green_cycle['protection_latched'] is True
    reset = green['cases']['below-reset']
    assert reset['final_temperature_K'] <= reset['reset_temperature_K']
    assert reset['internal_volume_flow_m3_s'] >= 0.01
    assert reset['final_mode'] == 'normal' and reset['protection_latched'] is False
    assert green['cases']['uninterrupted']['final_mode'] == 'protected'
    for name in ('uninterrupted', 'power-cycle', 'below-reset'):
        verify_saved_run(red_directory / name, SCHEMA_COMMIT, False)
        verify_saved_run(green_directory / name, LATCH_COMMIT, True)
    acceptance = read_json(HERE / 'acceptance/summary.json')
    assert acceptance['overall'] == 'PASS'
    assert acceptance['tests']['run'] == 179 and acceptance['tests']['executed'] == 177
    assert acceptance['tests']['failures'] == acceptance['tests']['errors'] == 0
    assert len(acceptance['tests']['optional_neural_skips']) == 2
    assert not acceptance['tests']['unexpected_skips']
    files = {}
    for folder in (schema_folder, latch_folder, HERE / 'acceptance'):
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                files[str(path.relative_to(FIXTURES)).replace('\\', '/')] = identity(path)
    files[str(Path(__file__).resolve().relative_to(FIXTURES)).replace('\\', '/')] = identity(Path(__file__))
    return {'schema': 'aegisdc-ticket03-review-fixes-v1', 'status': 'PASS',
            'scope': 'Finite engineering regression and artifact integrity; no scientific gain or field validation',
            'schema_fix_commit': SCHEMA_COMMIT, 'latch_fix_commit': LATCH_COMMIT,
            'target_tests': {'run': 37, 'failures': 0, 'errors': 0, 'skipped': 0},
            'full_acceptance': acceptance['tests'], 'prior_receipt_files_preserved': len(old['files_sha256']),
            'red_power_cycle': red_cycle, 'green_power_cycle': green_cycle, 'green_valid_reset': reset,
            'root_integration_acceptance': 'PENDING', 'mainline_status': 'active',
            'research_trials': 0, 'model_calls': 0, 'training_calls': 0,
            'files_sha256': files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    result = verify()
    content = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if arguments.output:
        with arguments.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    print(json.dumps({name: result[name] for name in ('status', 'schema_fix_commit', 'latch_fix_commit',
                      'target_tests', 'full_acceptance', 'prior_receipt_files_preserved',
                      'red_power_cycle', 'green_power_cycle', 'green_valid_reset', 'root_integration_acceptance')}, indent=2))
