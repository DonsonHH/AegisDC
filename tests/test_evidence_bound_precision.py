"""Independent exact-gap counterexamples at the public evidence ledger seam."""
from copy import deepcopy
import json
import sys
import unittest

from aegis_dc.evidence_ledger import EvidenceLedger
from test_evidence_ledger import example


def declared_pair(left_value, left_error, right_value, right_error):
    document = example()
    document['observables'][0]['quantity'] = 'temperature_offset'
    left = document['records'][0]
    left.update(id='left', value=left_value)
    left['quality']['error_bound'] = left_error
    left['provenance']['origin_id'] = 'origin-left'
    right = deepcopy(left)
    right.update(id='right', value=right_value)
    right['quality']['error_bound'] = right_error
    right['provenance']['origin_id'] = 'origin-right'
    document['records'].append(right)
    return document


class DeclaredBoundPrecisionTests(unittest.TestCase):
    def test_equal_JSON_integer_and_float_zero_bounds_keep_the_integer_gap(self):
        integer = declared_pair(9007199254740992, 0, 9007199254740993, 0)
        floating = declared_pair(9007199254740992, 0.0, 9007199254740993, 0.0)
        self.assertEqual(integer, floating)
        for document in (integer, floating):
            with self.subTest(bound_type=type(document['records'][0]['quality']['error_bound']).__name__):
                conflicts = EvidenceLedger(document).snapshot(2)['conflicts']
                self.assertEqual(len(conflicts), 1)
                self.assertEqual(conflicts[0]['record_ids'], ['left', 'right'])

    def test_binary64_declared_intervals_with_exact_gap_2_to_minus_55_are_disjoint(self):
        # These decoded binary64 literals are exactly 1, 2^-55, 1+2^-52,
        # and 3*2^-54. Their intervals have positive gap 2^-55; rounded
        # endpoint addition/subtraction incorrectly makes both endpoints 1.
        document = declared_pair(1.0, 2.7755575615628914e-17,
                                 1.0000000000000002, 1.6653345369377348e-16)
        conflicts = EvidenceLedger(document).snapshot(2)['conflicts']
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['kind'], 'disjoint_declared_bounds')

    def test_equal_duplicate_preserves_existing_record_encoding_and_outcome(self):
        document = declared_pair(9007199254740992, 0, 9007199254740993, 0)
        ledger = EvidenceLedger(document)
        before = json.dumps(ledger.snapshot(2), sort_keys=True)
        equivalent = deepcopy(document['records'][1])
        equivalent['quality']['error_bound'] = 0.0
        self.assertEqual(equivalent, document['records'][1])
        self.assertEqual(ledger.ingest(equivalent), 'ALREADY_PRESENT')
        self.assertEqual(json.dumps(ledger.snapshot(2), sort_keys=True), before)
        document['records'].append(equivalent)
        self.assertEqual(json.dumps(EvidenceLedger(document).snapshot(2), sort_keys=True), before)

    def test_equal_time_encodings_keep_large_integral_age_exact(self):
        integer = example()
        integer['records'][0].update(observed_at_s=0, arrived_at_s=0, valid_until_s=None)
        floating = deepcopy(integer)
        floating['records'][0].update(observed_at_s=0.0, arrived_at_s=0.0)
        self.assertEqual(integer, floating)
        first = EvidenceLedger(integer).snapshot(9007199254740993)
        second = EvidenceLedger(floating).snapshot(9007199254740993)
        self.assertEqual(first, second)
        self.assertEqual(second['records'][0]['age_s'], 9007199254740993)
        self.assertIs(type(second['records'][0]['age_s']), int)

    def test_fractional_age_has_one_binary64_rule_and_overflow_is_refused(self):
        document = example()
        document['records'][0].update(observed_at_s=0, arrived_at_s=0, valid_until_s=None)
        age = EvidenceLedger(document).snapshot(.25)['records'][0]['age_s']
        self.assertEqual(age, .25)
        self.assertIs(type(age), float)
        for observed in (-(2 ** 1023), float(-(2 ** 1023))):
            with self.subTest(observed_type=type(observed).__name__):
                document['records'][0]['observed_at_s'] = observed
                with self.assertRaises(ValueError):
                    EvidenceLedger(document).snapshot(2 ** 1023)

    def test_equivalent_bound_encodings_have_the_same_finite_endpoint_admission(self):
        # Exact upper endpoint is one below the binary64 overflow midpoint.
        # Converting x to binary64 before adding the bound loses that one.
        integer = example()
        integer['observables'][0]['quantity'] = 'temperature_offset'
        integer['records'][0]['value'] = int(sys.float_info.max) - 1
        integer['records'][0]['quality']['error_bound'] = 2 ** 970
        floating = deepcopy(integer)
        floating['records'][0]['quality']['error_bound'] = float(2 ** 970)
        self.assertEqual(integer, floating)
        for document in (integer, floating):
            with self.subTest(bound_type=type(document['records'][0]['quality']['error_bound']).__name__):
                snapshot = EvidenceLedger(document).snapshot(2)
                self.assertEqual(snapshot['current_record_ids'], ['r-temperature'])
                self.assertEqual(snapshot['records'][0]['value'], int(sys.float_info.max) - 1)


if __name__ == '__main__':
    unittest.main()
