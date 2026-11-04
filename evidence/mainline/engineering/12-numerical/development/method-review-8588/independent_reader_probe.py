"""Frozen-source algebra only: no plant, property solver, physics or original writes."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'frozen-snapshot-02'
ROOT = Path(r'C:/Users/Donson/Documents/ChatGPT/Renly')
WRITER = ROOT / '.work/worktrees/full-site-12'
spec = importlib.util.spec_from_file_location('frozen_numeric_reader', SNAPSHOT / 'scripts/numerical_refinement_checks.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
LIMITS = dict(temperature_K=.05, pressure_Pa=1000, heat_W=25000,
              service_deficit_time_s=.001, unserved_service_unit_s=.001,
              resource_time_s=.001, switch_time_s=.001)
unit = math.ulp(1.)


def trace(times, series, events=(), metrics=None):
    return dict(times=times, series=series, events=list(events),
                metrics=metrics or {'service_deficit_time_s': 0.}, literal_checks_pass=True)


def event(when, identity=('reserve_transition', 'ups', 'supplying')):
    return dict(identity=list(identity), time_s=when)


def compare(a, b):
    return reader.epoch_compare(a, b, LIMITS)


results = {}
def check(name, a, b, predicate, expected):
    result = compare(a, b)
    assert predicate(result), (name, expected, result)
    results[name] = dict(status='PASS', independently_expected=expected, comparison=result)
    return result


# Two affine temperature curves exactly .02 K apart; a different event epoch
# cannot discard that continuous-state offset.
a = trace([0., 1., 3.], {'room_K': [300., 301., 303.]}, [event(1.)])
b = trace([0., 1.+8*unit, 3.], {'room_K': [300.02, 301.02+8*unit, 303.02]}, [event(1.+8*unit)])
check('affine_temperature_offset_retained', a, b,
      lambda r: abs(r['maximum_absolute_series_error']['room_K']-.02) < 5e-13,
      'Maximum error .02 K, including paired continuous limits, not zero.')

# Manual one-sided limits: pre-jump 0 vs 100 kW, post-jump 2 vs 2.1 MW.
a = trace([0., 1., 3.], {'condenser_W': [0., 2e6, 2e6]}, [event(1.)])
b = trace([0., 1.+8*unit, 3.], {'condenser_W': [1e5, 2.1e6, 2.1e6]}, [event(1.+8*unit)])
biased = check('both_heat_side_errors_retained', a, b,
      lambda r: r['maximum_absolute_series_error']['condenser_W'] == 1e5 and not r['within_predeclared_limits'],
      'Both matched side limits differ by 100000 W; 25000 W bound fails.')
reverse = compare(b, a)
assert reverse['maximum_absolute_series_error'] == biased['maximum_absolute_series_error']
assert reverse['raw_causal']['maximum_absolute_series_error'] == biased['raw_causal']['maximum_absolute_series_error']
assert reverse['maximum_switch_time_error_s'] == biased['maximum_switch_time_error_s']
results['role_reversal_symmetry'] = dict(status='PASS', comparison=reverse)

zero = trace([0., 1., 3.], {'condenser_W': [0., 2e6, 2e6]}, [event(1.)])
delayed = trace([0., 1.+8*unit, 3.], {'condenser_W': [0., 2e6, 2e6]}, [event(1.+8*unit)])
bad_resource = deepcopy(delayed)
zero['metrics']['worker_work_person_s'] = 1.
bad_resource['metrics']['worker_work_person_s'] = 1.002
check('resource_cost_not_erased_by_epoch_alignment', zero, bad_resource,
      lambda r: r['absolute_integral_error']['worker_work_person_s'] > .001 and not r['within_predeclared_limits'],
      'A .002 person-second resource discrepancy exceeds its unchanged .001 bound.')

check('pressure_offset_fails_independently',
      trace([0.,1.,3.], {'pressure_Pa':[1e6,1e6,1e6]}, [event(1.)]),
      trace([0.,1.+8*unit,3.], {'pressure_Pa':[1001250.,1001250.,1001250.]}, [event(1.+8*unit)]),
      lambda r: r['maximum_absolute_series_error']['pressure_Pa'] == 1250. and not r['within_predeclared_limits'],
      '1250 Pa constant error exceeds 1000 Pa, including aligned event interval.')

check('no_event_heat_error_stays_visible',
      trace([0.,1.,3.], {'condenser_W':[0.,30000.,0.]}),
      trace([0.,.5,2.,3.], {'condenser_W':[0.,0.,0.,0.]}),
      lambda r: r['maximum_absolute_series_error']['condenser_W'] == 30000. and not r['within_predeclared_limits'],
      '30000 W held discrepancy on [1,3) exceeds 25000 W; no alignment exists.')

check('missing_event_fails_even_with_zero_value_error',
      trace([0.,1.,3.], {'condenser_W':[0.,0.,0.]}, [event(1.)]),
      trace([0.,1.,3.], {'condenser_W':[0.,0.,0.]}),
      lambda r: r['event_sequence_match'] is False and not r['within_predeclared_limits'],
      'An absent event fails the sequence gate despite identical numeric values.')

check('time_error_fails_even_with_zero_value_error',
      trace([0.,1.,3.], {'condenser_W':[0.,0.,0.]}, [event(1.)]),
      trace([0.,1.002,3.], {'condenser_W':[0.,0.,0.]}, [event(1.002)]),
      lambda r: r['maximum_switch_time_error_s'] > .001 and not r['within_predeclared_limits'],
      'A .002 second real shift fails independently even with identical series.')

# Exploratory counterexample: an interior saved flux excursion at a non-event
# integration point is not a second declared event. A time warp or two-sided
# jump comparison cannot justify erasing its 5 MW amplitude. Save both inputs
# and the exact reader response; this is not a facility-run observation.
interior = trace([0.,1.,1.+4*unit,1.+8*unit,3.],
                 {'condenser_W':[0.,2e6,5e6,2e6,2e6]}, [event(1.)])
flat_reference = trace([0.,1.+8*unit,3.], {'condenser_W':[0.,2e6,2e6]}, [event(1.+8*unit)])
interior_result = compare(interior, flat_reference)
diagnostic = dict(scope='ALGORITHMIC_COUNTEREXAMPLE_ONLY_NOT_OBSERVED_FACILITY_RUN',
                  actual=interior, reference=flat_reference, comparison=interior_result,
                  observed_false_pass=interior_result['within_predeclared_limits'] and interior_result['maximum_absolute_series_error']['condenser_W'] == 0.,
                  independently_expected='The unmatched interior 5 MW excursion must remain visible or invalidate alignment; its amplitude exceeds every reference value by at least 3 MW.')

official = subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_numerical_alignment.py','-v'], cwd=SNAPSHOT, text=True,capture_output=True)
assert official.returncode == 0, official.stderr
before=json.loads((HERE/'source-guard-before-02.json').read_text(encoding='utf-8'))
after={name:hashlib.sha256((WRITER/name).read_bytes()).hexdigest() for name in before['paths']}
unchanged=all(after[name] == row['writer_sha256'] for name,row in before['paths'].items())
assert unchanged,'Pinned writer file changed during independent read-only probes'
record=dict(source_commit=before['pin'], baseline=before['baseline'], algebraic_targets=len(results),
            results=results, interior_excursion_diagnostic=diagnostic,
            official_tests=dict(command=official.args, exit_code=official.returncode, stdout=official.stdout,stderr=official.stderr),
            guarded_files=len(after), source_guard='PASS', guarded_after_sha256=after,
            physics_runs=0,research_trials=0,model_calls=0,training_calls=0)
with (HERE/'independent-reader-probe-01.json').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(record,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(algebraic_targets=len(results),official_tests=7,source_guard='PASS',interior_excursion_false_pass=diagnostic['observed_false_pass'],
                      epoch_heat_error=interior_result['maximum_absolute_series_error']['condenser_W'],raw_heat_error=interior_result['raw_causal']['maximum_absolute_series_error']['condenser_W'])))
