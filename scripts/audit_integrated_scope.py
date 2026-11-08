"""Read saved artifacts in Slurm; never import the plant or create new trials."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def fraction(value):
    return Fraction(str(value))


def audit(root, protocol):
    expected = protocol['independent_expected_values_from_user_review']
    tolerance = protocol['absolute_tolerance']

    def same(actual, name):
        target = expected[name]
        if isinstance(actual, (int, float, Fraction)) and not isinstance(actual, bool):
            if abs(float(actual - fraction(target))) > tolerance:
                raise ValueError(f'{name}: {actual} differs from frozen {target}')
        elif actual != target:
            raise ValueError(f'{name}: {actual!r} differs from frozen {target!r}')
        return float(actual) if isinstance(actual, Fraction) else actual

    with (root / 'pairs.csv').open(encoding='utf-8', newline='') as stream:
        pairs = list(csv.DictReader(stream))
    if len({p['world_id'] for p in pairs}) != len(pairs):
        raise ValueError('Repeated original world identity')
    gains = [fraction(p['service_gain_s']) for p in pairs]
    paid = [fraction(p['extra_paid_person_s']) for p in pairs]
    for row in pairs:
        if fraction(row['baseline_deficit_s']) - fraction(row['candidate_deficit_s']) != fraction(row['service_gain_s']):
            raise ValueError('Saved pair arithmetic differs')
    count = len(pairs)
    world12 = next(p for p in pairs if p['world_id'] == 'confirmation-12')
    other = [p for p in pairs if p['world_id'] != 'confirmation-12']
    primary = json.loads((root / 'primary.json').read_text(encoding='utf-8'))
    method_means = {}
    for arm in ('no_human', 'evidence_consistent_contingent'):
        runs = [r for r in primary['runs'] if r['arm'] == arm]
        if len(runs) != count or {r['world_id'] for r in runs} != {p['world_id'] for p in pairs}:
            raise ValueError('Method run denominator differs from complete original worlds')
        method_means[arm] = {
            'mean_deficit_s': sum(fraction(r['totals']['service_deficit_time_s']) for r in runs) / count,
            'mean_paid_person_s': sum(fraction(r['totals']['paid_person_s']) for r in runs) / count,
        }
    checks = {
        'pairs': same(count, 'pairs'),
        'better_same_worse': same([sum(g > tolerance for g in gains), sum(abs(g) <= tolerance for g in gains), sum(g < -tolerance for g in gains)], 'better_same_worse'),
        'mean_service_gain_s': same(sum(gains) / count, 'mean_service_gain_s'),
        'mean_extra_paid_person_s': same(sum(paid) / count, 'mean_extra_paid_person_s'),
        'total_paid_saving_person_s': same(-sum(paid), 'total_paid_saving_person_s'),
        'confirmation_12_paid_saving_person_s': same(-fraction(world12['extra_paid_person_s']), 'confirmation_12_paid_saving_person_s'),
        'without_12_mean_service_gain_s': same(sum(fraction(p['service_gain_s']) for p in other) / len(other), 'without_12_mean_service_gain_s'),
        'without_12_mean_paid_saving_person_s': same(-sum(fraction(p['extra_paid_person_s']) for p in other) / len(other), 'without_12_mean_paid_saving_person_s'),
        'no_human_mean_deficit_s': same(method_means['no_human']['mean_deficit_s'], 'no_human_mean_deficit_s'),
        'candidate_mean_deficit_s': same(method_means['evidence_consistent_contingent']['mean_deficit_s'], 'candidate_mean_deficit_s'),
        'candidate_mean_paid_person_s': same(method_means['evidence_consistent_contingent']['mean_paid_person_s'], 'candidate_mean_paid_person_s'),
    }
    if method_means['no_human']['mean_paid_person_s'] != 0:
        raise ValueError('No-human arm has nonzero paid labor')
    for field in ('mean_service_gain_s', 'mean_extra_paid_person_s'):
        raw_field = 'mean_service_delta_s' if field == 'mean_service_gain_s' else field
        if abs(primary[raw_field] - checks[field]) > tolerance:
            raise ValueError('Primary JSON and saved CSV disagree')
    checks['confirmation_12_share_of_total_paid_saving'] = float(fraction(world12['extra_paid_person_s']) / sum(paid))

    facility = json.loads((root / 'facility.json').read_text(encoding='utf-8'))
    risks = json.loads((root / 'risks.json').read_text(encoding='utf-8'))
    value = json.loads((root / 'value.json').read_text(encoding='utf-8'))
    checks['parameter_basis'] = same(dict(Counter(p['basis'] for p in facility['parameters'])), 'parameter_basis')
    checks['risk_question_count'] = same(len(risks['questions']), 'risk_question_count')
    checks['quantified_risk_questions'] = same(sorted(q['id'] for q in risks['questions'] if q['quantification'] == 'FINITE_CONDITIONAL_LAW'), 'quantified_risk_questions')
    checks['unmodeled_question_count'] = same(sum(q['quantification'] == 'UNMODELED' for q in risks['questions']), 'unmodeled_question_count')
    checks['value_question_ids'] = same(sorted(q['question_id'] for q in value['question_models']), 'value_question_ids')
    checks['unmodeled_question_ids'] = [q['id'] for q in risks['questions'] if q['quantification'] == 'UNMODELED']

    formal = json.loads((root / 'formal-input.json').read_text(encoding='utf-8'))
    declaration = formal['dispatch_program']
    workforce = declaration['policy_program']['workforce_profile']
    parameters = {p['id']: p['value'] for p in facility['parameters']}
    timing = {
        'formal_duration_s': same(formal['duration_s'], 'formal_duration_s'),
        'formal_candidate_count': same(len(declaration['policy_program']['candidates']), 'formal_candidate_count'),
        'formal_work_time_s': same(sorted(set(workforce['work_times_s'].values())), 'formal_work_time_s'),
        'formal_walk_time_s': same(sorted(set(workforce['walk_times_s'].values())), 'formal_walk_time_s'),
        'formal_closure_program': same(declaration['closure_program'], 'formal_closure_program'),
        'default_inspection_s': same(parameters['inspection_time'], 'default_inspection_s'),
        'default_walk_time_s': same(sorted({parameters[e['duration_parameter']] for e in facility['graphs']['access']}), 'default_walk_time_s'),
        'control_sample_s': same(parameters['control_sample_time'], 'control_sample_s'),
        'diesel_start_s': same(parameters['diesel_start_time'], 'diesel_start_s'),
        'formal_access_check_s': workforce['access_check_s'],
        'formal_feedback_latency_s': workforce['feedback_latency_s'],
        'formal_inspection_deadline_s': declaration['policy_program']['candidates'][0]['task']['deadline_s'],
        'formal_action_deadline_s': declaration['policy_program']['candidates'][1]['task']['deadline_s'],
        'formal_candidate_kinds': [c['kind'] for c in declaration['policy_program']['candidates']],
        'formal_candidate_targets': [c['task']['target_id'] for c in declaration['policy_program']['candidates']],
        'ratio_formal_work_to_controller_sample': workforce['work_times_s']['inspect_facility_cooling'] / parameters['control_sample_time'],
        'ratio_default_work_to_controller_sample': parameters['inspection_time'] / parameters['control_sample_time'],
        'ratio_formal_horizon_to_diesel_start': formal['duration_s'] / parameters['diesel_start_time'],
        'interpretation': 'Nonuniform time scaling; a diesel started after t=0 cannot finish a30s start within10s. Prestarted states remain distinct. Old numerical witnesses do not qualify future windows or disturbances.',
    }
    return {'classification': protocol['classification'], 'checks': checks, 'primary_status': primary['status'], 'registered_primary_denominator_unchanged': count, 'interpretation': protocol['interpretation']}, timing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0] == 'mu01':
        raise SystemExit('Saved-result evaluation requires a Slurm compute allocation')
    args.output.mkdir(exist_ok=False)
    start = {
        'classification': 'saved_artifact_audit_not_research_trial',
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'slurm_job_id': os.environ['SLURM_JOB_ID'],
        'node': socket.gethostname(),
        'python': sys.version,
        'manifest_sha256': sha256(args.manifest),
        'new_facility_calls': 0, 'new_policy_calls': 0, 'new_model_calls': 0, 'new_statistical_units': 0,
    }
    save(args.output / 'attempt.json', start)
    terminal = {'started_record_sha256': sha256(args.output / 'attempt.json'), 'status': 'FAILED'}
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        root = args.manifest.resolve().parent
        def guard():
            for name, record in manifest['files'].items():
                path = root / name
                if path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
                    raise ValueError(f'Immutable input/tool changed: {name}')
        guard()
        if sha256(Path(__file__)) != manifest['files']['audit_integrated_scope.py']['sha256']:
            raise ValueError('Executed tool differs from frozen staged tool')
        protocol = json.loads((root / 'protocol.json').read_text(encoding='utf-8'))
        diagnostics, timing = audit(root, protocol)
        guard()
        save(args.output / 'diagnostic-results.json', diagnostics)
        save(args.output / 'timing-scope.json', timing)
        terminal.update(status='COMPLETED', source_commit=manifest['source_commit'], durable_outputs={p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in args.output.iterdir() if p.is_file()})
        print(json.dumps({'status': 'COMPLETED', 'pairs': diagnostics['checks']['pairs'], 'new_trials': 0}))
    except BaseException as error:
        terminal.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        terminal['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.output / 'terminal.json', terminal)


if __name__ == '__main__':
    main()
