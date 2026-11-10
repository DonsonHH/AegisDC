"""Cost statements cannot inject actual values or change provenance and clock units."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


class CostDeclarationQualificationTests(unittest.TestCase):
    def test_closed_cost_identity_provenance_units_and_record_fields_before_integration(self):
        descriptor = json.loads((ROOT/'tests/fixtures/39c-cost-declaration-46.json').read_bytes())
        base = json.loads((ROOT/descriptor['base_input']).read_bytes())
        output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        self.facility_calls = self.completed_native_horizons = self.returned_decisions = 0
        self.completed_native_duration_s = 0
        rows = []
        try:
            for case in descriptor['cases']:
                row = dict(case=case['id'], passed=False)
                rows.append(row)
                with self.subTest(case=case['id']):
                    data = deepcopy(base)
                    data['business_program']['schema'] = 'aegisdc-business-cost-evaluation-v2'
                    data['business_program'].update(case['program_patch'])
                    directory = output/case['id'] if output is not None else None
                    if directory is not None:
                        directory.mkdir()
                        with (directory/'frozen-call-input.json').open('x', encoding='utf-8', newline='\n') as stream:
                            json.dump(data, stream, indent=2, allow_nan=False)
                            stream.write('\n')
                    self.facility_calls += 1
                    try:
                        result = simulate_scenario(**data)
                    except ValueError as error:
                        row['actual_error'] = str(error)
                        self.assertEqual(str(error), case['expected_error'])
                        row['passed'] = True
                    else:
                        self.completed_native_horizons += 1
                        self.completed_native_duration_s += result['summary']['duration_s']
                        self.returned_decisions += len(result.get('policy_public_decisions', []))
                        if directory is not None:
                            save_run(result, directory/'unexpected-actual-run')
                        self.fail('Invalid cost statement unexpectedly completed a physical run')
        finally:
            if output is not None:
                with (output/'qualification.json').open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(rows, stream, indent=2, allow_nan=False)
                    stream.write('\n')
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row['passed'] for row in rows))


if __name__ == '__main__':
    unittest.main()
