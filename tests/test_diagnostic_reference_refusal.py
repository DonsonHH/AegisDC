"""Versioned public facility boundary refuses unknown-time placeholders and forged references."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run,simulate_scenario

ROOT=Path(__file__).resolve().parents[1]


class DiagnosticReferenceRefusalTests(unittest.TestCase):
    def test_closed_versions_nulls_bindings_hash_and_event_identity_are_refused(self):
        cases=json.loads((ROOT/'tests/fixtures/39c-reference-refusal-14.json').read_bytes())['cases']
        descriptor=json.loads((ROOT/'tests/fixtures/39c-network-state-diagnostic.json').read_bytes())
        base=json.loads((ROOT/descriptor['base_fixture']).read_bytes())
        output=Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR') else None
        rejections=[];self.facility_calls=0;self.returned_decisions=0
        for case in cases:
            with self.subTest(case=case['id']):
                fixture=deepcopy(base);dispatch=fixture['dispatch_program'];dispatch['schema']='aegisdc-policy-run-program-v4'
                dispatch['decision_times_s']=[0,1.75,2];dispatch['diagnostic_profile']=deepcopy(descriptor['public_profile'])
                business=deepcopy(descriptor['business_program']);business['schema']=case['schema'];business['id']+='-'+case['id']
                business['events'][0]['opportunity'].update(status=case['status'],earliest_report_at_s=case['earliest'],inspection_task_id=case['task'])
                if case['spoof_hash']:business['reference']['scenario_sha256']='0'*64
                if case['duplicate']:
                    duplicate=deepcopy(business['events'][0]);duplicate['id']+='-alias';business['events'].append(duplicate)
                folder=None
                if output is not None:
                    folder=output/case['id'];folder.mkdir()
                    with (folder/'frozen-call-input.json').open('x',encoding='utf-8',newline='\n') as stream:
                        json.dump(dict(model=fixture['model'],dispatch_program=dispatch,business_program=business,
                            duration_s=2,step_s=.01,boundary_events=[]),stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
                self.facility_calls+=1
                error=None
                try:
                    result=simulate_scenario(fixture['model'],duration_s=2,step_s=.01,dispatch_program=dispatch,business_program=business)
                except ValueError as caught:error=caught
                if error is None:
                    self.returned_decisions+=len(result['policy_public_decisions'])
                    if folder is not None:save_run(result,folder/'unexpected-actual-run')
                    self.fail('Illegal reference input was accepted: '+case['id'])
                rejection=dict(case_id=case['id'],error_type=type(error).__name__,error=str(error))
                rejections.append(rejection)
                if folder is not None:
                    with (folder/'rejection.json').open('x',encoding='utf-8',newline='\n') as stream:
                        json.dump(rejection,stream,ensure_ascii=False,indent=2);stream.write('\n')
                self.assertIn(case['expected_error'],str(error))
        if output is not None:
            with (output/'rejections-summary.json').open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(rejections,stream,ensure_ascii=False,indent=2);stream.write('\n')
        self.assertEqual(len(rejections),10)
        self.assertEqual(self.returned_decisions,0)


if __name__=='__main__':unittest.main()
