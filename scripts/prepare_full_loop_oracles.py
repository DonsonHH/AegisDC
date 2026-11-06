"""Independent ticket27 literal arithmetic; never import or run the plant."""
from fractions import Fraction as F
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/mainline/engineering/27-full-loop/reference/independent-literals-v1.json'


def ratio(value):
    return [value.numerator, value.denominator]


def main():
    prior = F(1, 100)
    report_bad, report_good = F(3, 4), F(3, 100)
    posterior = prior * report_bad / (prior * report_bad + (1 - prior) * report_good)
    positive_mass = posterior * F(4, 5) + (1 - posterior) * F(1, 10)
    positive = posterior * F(4, 5) / positive_mass
    negative = posterior * F(1, 5) / (1 - positive_mass)
    defer = 6 * posterior
    direct = 1 + posterior / 4
    # Positive report -> act:2seconds of bad-state delay plus1second outage.
    # Negative report -> defer:6seconds of bad-state deficit.
    inspect = positive_mass + 2 * posterior * F(4, 5) + 6 * posterior * F(1, 5)
    value = dict(schema='aegisdc-full-loop-independent-literals-v1',
        status='PROPOSED_BEFORE_ANY_PROJECT_CALL_NOT_FROZEN_RUN_PROTOCOL',
        classification='PURE_ARITHMETIC_AND_DECLARED_EVENT_EXPECTATIONS_NOT_EFFECT_EVIDENCE',
        physical=dict(duration_s=10, offered_demand_integral=ratio(F(1, 2) * F(1, 2) + F(19, 2)),
            delivered_integral=ratio(F(1, 4) + F(3, 2) + 6), unserved_integral=ratio(F(2)),
            normalized_deficit_time_s=ratio(F(2)),
            condition='Existing local protection resets at4seconds only if its actual temperature/flow gates hold; otherwise this literal fails and the run stops.',
            load_requested_W_before=1_000_000, load_requested_W_after=2_000_000,
            grid_outage_s=[2, 3.4], compute_permission_expected_off_s=[2, 4],
            ups_maintenance_from_s=1, diesel_start_delay_s=30,
            head_Pa=150000, passive_resistance=12000000, valve_resistance=3000000,
            clean_flow_squared=ratio(F(1, 100)), degraded_flow_squared=ratio(F(1, 340)),
            clean_mass_flow_kg_s=ratio(F(998, 10))),
        public_model=dict(prior_bad=ratio(prior), work_order_positive_bad=ratio(report_bad),
            work_order_positive_good=ratio(report_good), bad_after_arrived_work_order=ratio(posterior),
            positive_report_mass=ratio(positive_mass), positive_bad=ratio(positive), negative_bad=ratio(negative),
            defer_deficit_s=ratio(defer), direct_deficit_s=ratio(direct), inspect_deficit_s=ratio(inspect),
            before_work_order_defer_deficit_s=ratio(6 * prior),
            actual_horizon_s=10, model_horizon_s=6, model_horizon_interpretation='Relative to each public decision'),
        expected_times_s=dict(work_order_observed=1.5, work_order_arrived=3,
            inspection_issued=3, inspection_started=3.25, inspection_completed=4.25,
            handheld_record_arrived=4.75, action_issued=4.75, action_started=5, action_completed=6,
            action_report_arrived=6.5, postaction_sample_times=[7, 8],
            postaction_arrival_times=[7.5, 8.5], first_possible_verified_closure=8.5),
        attribution=dict(service_recovery='Local automatic reset after external mains restoration; not a human repair effect.',
            filter_recovery='Authorized paid clean_filter at6seconds; increases cooling margin, does not erase previous service deficit.',
            closure='At least2post-action current flow and actual service samples spanning1second, using accepted24rules.'),
        new_selector_calls=0, new_physical_calls=0, new_full_regressions=0,
        registered_research_trials=0, field_calibration='PENDING', overall_goal='ACTIVE')
    assert posterior == F(25, 124)
    assert (defer, direct, inspect) == (F(75, 62), F(521, 496), F(999, 1240))
    assert (positive, negative) == (F(200, 299), F(50, 941))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(status=value['status'], path=OUTPUT.relative_to(ROOT).as_posix(), new_project_calls=0)))


if __name__ == '__main__':
    main()
