"""Author the declared ticket-12 engineering cases; never run physics here."""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    old = json.loads((ROOT / 'docs/mainline/11-coupled-runbook.json').read_text(encoding='utf-8'))
    first = json.loads((ROOT / 'docs/mainline/12-numerical-runbook.json').read_text(encoding='utf-8'))['cases'][0]
    cases = [first, dict(id='normal', duration_s=12, overrides={}, events=[], work_requests=[],
                        reference='Same V6 steady initialization; independent zero-change expectation.'),
             dict(id='thermal-hydraulic', duration_s=12, overrides={}, work_requests=[], events=[
                 dict(time_s=t, parameter_id=p, value=v, source_note='Frozen ticket 12 synthetic engineering perturbation.')
                 for t, p, v in [(1.125, 'service_demand', 1.2), (2.375, 'filter_resistance_multiplier', 4),
                                 (3.875, 'internal_valve_opening', .8), (5.125, 'backup_cooling_requested', 1),
                                 (9.125, 'backup_cooling_requested', 0)]],
                  reference='Two fine explicit-Euler full-facility trajectories; numerical convergence only.'),
             dict(id='zero-flow', duration_s=4, overrides={}, work_requests=[], events=[
                 dict(time_s=t, parameter_id='internal_valve_opening', value=v,
                      source_note='Frozen ticket 12 flow interruption and restoration.')
                 for t, v in [(1.25, 0), (3.25, 1)]],
                  reference='Full-facility fine-step reference; zero-flow transfer must be exactly zero.'),
             dict(id='outage', duration_s=8, overrides={'diesel_start_time': 3, 'diesel_transfer_delay': .5},
                  work_requests=[], events=[dict(time_s=t, parameter_id='grid_capacity', value=v,
                      source_note='Frozen ticket 12 outage; connection at .75+3+.5=4.25 s.')
                      for t, v in [(.75, 0), (5.25, 10000000)]],
                  reference='Independent switching times .75/.95/3.75/4.25/5.25 s; normalized deficit 3.5 s.')]
    for name in ('shared-AC-capacity', 'finite-generator-hand', 'finite-UPS-hand', 'room-thermal-work-limit'):
        case = deepcopy(next(item for item in old['cases'] if item['id'] == name))
        case['reference'] = case.pop('rationale')
        case.pop('step_s')
        case.pop('via_cli')
        cases.append(case)
    combined = deepcopy(next(item for item in old['cases'] if item['id'] == 'combined-episode-CLI'))
    combined['id'] = 'combined-240s'
    combined['reference'] = combined.pop('rationale')
    combined.pop('step_s')
    combined.pop('via_cli')
    cases.append(combined)
    cases.append(dict(id='thermal-protection', duration_s=60,
        overrides={'internal_hot_mass': 1000, 'internal_cold_mass': 1000,
                   'minimum_internal_hot_mass': 900, 'protection_temperature': 306,
                   'protection_reset_temperature': 305},
        events=[dict(time_s=1.125, parameter_id='plate_hx_conductance', value=10000,
                     source_note='Declared synthetic HX degradation; 306/305 K protection thresholds are frozen research settings, not site limits.')],
        work_requests=[], reference='Fine-step same-model water/solid/phase/PLC interaction. Threshold-driven service changes may be non-smooth in step; no threshold retuning after observation.'))
    for item in cases:
        item.setdefault('checks', [])
        for check in item['checks']:
            anchor = None
            if item['id'] == 'finite-UPS-hand':
                anchor = ({'kind': 'ups_depleted'} if check['time_s'] == 32.6 else
                          {'kind': 'reserve_transition', 'actor': 'ups', 'mode': 'supplying'} if check['time_s'] == .2 else None)
            if item['id'] == 'finite-generator-hand':
                anchor = ({'kind': 'reserve_transition', 'actor': 'generator', 'mode': 'transferring'} if check['time_s'] == 3 else
                          {'kind': 'reserve_transition', 'actor': 'generator', 'mode': 'supplying'} if check['time_s'] == 5 else
                          {'kind': 'fuel_depleted'} if check['time_s'] == 15 else None)
            if item['id'] == 'combined-240s' and check['time_s'] in (46, 48):
                anchor = {'kind': 'reserve_transition', 'actor': 'cooling',
                          'mode': 'switching' if check['time_s'] == 46 else 'active'}
            if anchor:
                check['event_anchor'] = anchor
    return dict(schema='aegisdc-numerical-qualification-v1',
        classification='FULL_V6_ENGINEERING_NUMERICAL_QUALIFICATION_NOT_RESEARCH',
        profile=old['profile'], cases=cases,
        rejections=deepcopy(old['rejections']),
        maximum_steps_s=[1, .5, .25, .125, .0625, .025, .02, .01],
        fine_reference_s=.01, reference_refinement_s=.02, proposed_qualified_maximum_step_s=.025,
        literal_checkpoint_time_tolerance_s=1e-8,
        comparison='Maximum error over the union of saved time coordinates: piecewise linear states, interval-held fluxes, declared eight-ULP time convention. Event sequence compared separately.',
        limits=dict(temperature_K=.05, pressure_Pa=1000, heat_W=25000,
                    service_deficit_time_s=.001, unserved_service_unit_s=.001,
                    resource_time_s=.001, switch_time_s=.001),
        fine_reference_fraction_of_limits=.25,
        restrictions=['Finite explicit synthetic fixture points only; no parameter-box proof or empirical/site calibration.',
                      'No single-phase continuation; no quality/inventory clipping; phase flash refusals remain failures.',
                      'Isolated-room analytic error <=.005 K is a separate stronger check; all other dynamic references are numerical.',
                      'Qualification of these equations/steps does not open registered mechanism comparisons before ticket 30.'],
        research_trials=0, model_calls=0, training_calls=0)


if __name__ == '__main__':
    (ROOT / 'docs/mainline/12-numerical-runbook.json').write_text(
        json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
