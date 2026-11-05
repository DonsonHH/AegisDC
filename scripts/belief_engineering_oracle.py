"""Independent finite calibration oracle for the ticket 18 arithmetic witness."""
from collections import defaultdict
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json


def bernoulli(probability, outcome):
    return probability if outcome else 1 - probability


def build_oracle(raw):
    witness = json.loads(raw)
    states = witness['hypotheses']
    prior = list(map(Fraction, witness['prior']))
    transition = [list(map(Fraction, row)) for row in witness['transition']]
    hot = list(map(Fraction, witness['observation_likelihoods']['hot_at_first_epoch']))
    power = list(map(Fraction, witness['observation_likelihoods']['low_power_at_second_epoch']))

    # A tabulated joint measure over two hidden states and two binary reports.
    # It is generated independently of the ticket 18 inference implementation.
    atoms = []
    for previous, current, hot_report, power_report in product(range(4), range(4), (False, True), (False, True)):
        mass = (prior[previous] * transition[previous][current]
                * bernoulli(hot[previous], hot_report) * bernoulli(power[current], power_report))
        atoms.append((current, (hot_report, power_report), mass))
    assert len(atoms) == 64 and sum(atom[2] for atom in atoms) == 1

    expected = {}
    for count, label in enumerate(('no-reports', 'arrived-hot-only', 'both-arrived')):
        counts = defaultdict(lambda: [Fraction(0)] * 4)
        for current, reports, mass in atoms:
            counts[reports[:count]][current] += mass
        rows = []
        brier = Fraction(0)
        for pattern, masses in sorted(counts.items()):
            pattern_mass = sum(masses)
            posterior = [mass / pattern_mass for mass in masses]
            assert sum(posterior) == 1
            for truth, mass in enumerate(masses):
                brier += mass * sum((p - int(truth == state)) ** 2 for state, p in enumerate(posterior))
            rows.append(dict(reports=list(pattern), probability=str(pattern_mass),
                             exact_frequencies=dict(zip(states, map(str, posterior)))))
        expected[label] = dict(rows=rows, weighted_multiclass_brier=str(brier),
                               weighted_multiclass_brier_decimal=float(brier))

    # Negative comparators use the same true atom weights. Neither is a proposed
    # production rule. One stamps the delayed hot report at the current epoch,
    # the other falsely treats its copy as an independent observation.
    negatives = {}
    for error in ('late-hot-at-current', 'duplicate-hot-as-independent'):
        incorrect = {}
        for reports in product((False, True), repeat=2):
            joint = [Fraction(0)] * 4
            for previous, current in product(range(4), repeat=2):
                first = bernoulli(hot[current if error == 'late-hot-at-current' else previous], reports[0])
                if error == 'duplicate-hot-as-independent':
                    first **= 2
                joint[current] += (prior[previous] * transition[previous][current]
                                   * first * bernoulli(power[current], reports[1]))
            incorrect[reports] = [mass / sum(joint) for mass in joint]
        brier = sum(mass * sum((p - int(truth == state)) ** 2
                               for state, p in enumerate(incorrect[reports]))
                    for truth, reports, mass in atoms)
        negatives[error] = dict(weighted_multiclass_brier=str(brier), weighted_multiclass_brier_decimal=float(brier))
        assert brier > Fraction(expected['both-arrived']['weighted_multiclass_brier'])

    result = dict(
        scope='Independent 64-atom exact engineering oracle under the declared synthetic witness law',
        input_sha256=sha256(raw).hexdigest(), atoms=len(atoms), exact_total_probability='1',
        brier='Probability-weighted sum across all four squared class errors, not divided by class count.',
        outcome_partitions=expected, negative_comparators=negatives,
        limitation='Exact finite expectations support a comparison against inference output. Empirical facility calibration requires separate observations.',
        registered_research_trials=0, model_calls=0, training_calls=0,
    )
    return result
