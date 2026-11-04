"""Explicit additive engineering protocol revision after the original NO-GO."""
import json
from pathlib import Path

from verify_reserve_delivery import file_sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    prior = ROOT / 'evidence/mainline/engineering/12-numerical/capture-04'
    receipt = json.loads((prior / 'receipt.json').read_text(encoding='utf-8'))
    if receipt['numerical_gate']:
        raise ValueError('The revision must have an observed, preserved reference-resolution failure')
    old = json.loads((prior / 'runbook-copy.json').read_text(encoding='utf-8'))
    names = ['zero-flow', 'outage', 'shared-AC-capacity', 'finite-generator-hand', 'thermal-protection', 'combined-240s']
    book = dict(old, schema='aegisdc-numerical-refinement-v2',
        classification='ADDITIVE_ENGINEERING_PROTOCOL_REVISION_NOT_RESEARCH',
        revision_reason='Original .025 s candidate and .02/.01 reference resolution did not meet unchanged heat-flow limits; retain every original outcome and diagnose with finer reference.',
        analysis_revision='FIXED_IDENTITY_PAIRED_EPOCH_WITH_CAUSAL_LEFT_HELD_RAW_V2',
        analysis_basis='Independent 0-to-2MW hand-jump red/green, 8/9ULP, nontransitive chain, distinct nearby event, unmatched/order and real 1s shift. Legacy v1 independent forward peek is retained as a failed analysis diagnostic, not a strict raw envelope.',
        gate_metric='Epoch-consistent maximum after only unique <=8ULP event groups; preserve causal raw maxima, both one-sided limits, excluded point count/window width and independent actual event-time error. More than8ULP/unmatched/reordered/intervening distinct events cannot be aligned.',
        v1_directory=prior.relative_to(ROOT).as_posix(), v1_receipt_sha256=file_sha(prior / 'receipt.json'),
        cases=[next(item for item in old['cases'] if item['id'] == name) for name in names],
        rejections=[], inherited_rejection_ids=[item['id'] for item in old['rejections']],
        newly_run_steps_s=[.005, .0025], reused_original_steps_s=old['maximum_steps_s'],
        maximum_steps_s=old['maximum_steps_s'] + [.005, .0025],
        fine_reference_s=.0025, reference_refinement_s=.005, proposed_qualified_maximum_step_s=.01,
        numeric_domain_extension=dict(parameter_id='step_time', original_minimum_s=.01, new_minimum_s=.0025,
            scope='Only the SI record valid_range/basis/source_note in derived V6 research copies. Physical values, all entities/relations, original V6 file and runtime equations unchanged.'),
        full_regression_policy='Reuse the one full v1 acceptance only if every runtime source byte is identical; new fine cases run through public load/simulate/save. No repeated full suite for numeric-range declaration alone.')
    target = ROOT / 'docs/mainline/12-numerical-refinement-v2.json'
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(book, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
