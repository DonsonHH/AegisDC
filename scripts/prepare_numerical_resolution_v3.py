"""Register only reference failures found by all-100 amplitude-safe readback."""
import json
from pathlib import Path
from verify_reserve_delivery import file_sha

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    folder=ROOT/'evidence/mainline/engineering/12-numerical/reanalysis-v3-01'
    result=json.loads((folder/'assessment.json').read_text(encoding='utf-8'))
    if result['original_archives']!=100 or not result['all_originals_read_without_result_selection']:
        raise ValueError('Read every original with the new matcher before selecting additional cases')
    names=result['cases_requiring_additional_reference_resolution']
    if result['candidate_failures']:raise ValueError('Candidate failures need an explicit separate diagnosis')
    old=json.loads((ROOT/'docs/mainline/12-numerical-runbook.json').read_text(encoding='utf-8'))
    if not names or any(name not in {item['id'] for item in old['cases']} for name in names):
        raise ValueError('No registered unresolved reference case')
    book=dict(schema='aegisdc-numerical-resolution-protocol-v3',classification='ADDITIVE_ENGINEERING_REFERENCE_RESOLUTION_NOT_RESEARCH',
        reason='Amplitude-safe reanalysis of all100 originals retained reference failures; neither limits nor existing outcomes change.',
        prior_reanalysis=folder.relative_to(ROOT).as_posix(),prior_assessment_sha256=file_sha(folder/'assessment.json'),
        prior_receipt_sha256=file_sha(folder/'receipt.json'),cases=[item for item in old['cases'] if item['id'] in names],
        profile=old['profile'],limits=old['limits'],fine_reference_fraction_of_limits=.25,
        maximum_steps_s=[.01,.0025,.00125],proposed_qualified_maximum_step_s=.01,
        reference_refinement_s=.0025,fine_reference_s=.00125,newly_run_steps_s=[.00125],
        numeric_domain_extension=dict(parameter_id='step_time',canonical_minimum_s=.01,new_minimum_s=.00125,
            changes=['valid_range lower endpoint','basis','source_note'],physical_values_unchanged=True),
        analysis_method='FIXED_PAIRED_EPOCH_WITH_CLOSED_INTERVAL_AMPLITUDE_GUARD_V3',
        prior_v1_and_v2_NO_GO_preserved=True,full_suite_rerun=False,research_trials=0,model_calls=0,training_calls=0)
    with (ROOT/'docs/mainline/12-numerical-resolution-v3.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(book,stream,ensure_ascii=False,indent=2);stream.write('\n')
