import copy
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from patrol_rsi import event_validation as module


class ResumptionTests(unittest.TestCase):
    def fixture(self, root):
        prior = root/'prior'; prior.mkdir()
        cases = [dict(id=f'c{i}',group='coupled',spec=dict(seed=i,fault_rack=i),permutation_seed=i) for i in range(4)]
        protocol = dict(cases=cases,methods=['tour','fifo','shuffled'],max_evaluations=12,seen_seeds=[],
                        extra_visit_budget=12,bootstrap_seed=1,decision_thresholds=dict(
                            minimum_anomalous_primary_processes=8,minimum_mean_net_confirmations=1,
                            maximum_travel_increase_pct=5,maximum_completion_loss_pct=2))
        module.write(prior/'protocol.json',protocol)
        attempts, rows = [], []
        metrics = dict(anomaly_segments=0,confirmed_segments=0,missed_segments=0,
                       consequence_weighted_censored_delay_s=None,travel_m=100,service_s=10,
                       completed_inspections=10,extra_event_visits=0,tasks_violating_exact_gap=0,
                       invalid_assignments=0,duplicate_reservations=0)
        record = dict(process_sha256='fixture',anomaly_intervals=[],metrics=metrics)
        for case in cases[:3]:
            for method in protocol['methods']:
                filename=case['id']+'-'+method+'.json.gz'
                with gzip.open(prior/filename,'wt',encoding='utf-8') as stream:
                    json.dump(dict(record,spec=case['spec']),stream)
                attempts.append(dict(case=case['id'],method=method,status='completed'))
                rows.append(dict(case=case['id'],group='coupled',seed=case['spec']['seed'],method=method,
                                 record=filename,**metrics,multiple_legal_event_decisions=0,event_outcomes={}))
        attempts.append(dict(case='c3',method='tour',status='failed',error='Risk provenance components do not match executed risk'))
        module.write(prior/'attempts.json',attempts); module.write(prior/'rows.json',rows)
        index = {p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in prior.iterdir()}
        index_path = root/'index.json'; module.write(index_path,index)
        revised=copy.deepcopy(protocol); revised['max_evaluations']=13
        revised['amendment']=dict(authorization='user_approved',prior_index_path=str(index_path),
            prior_index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(),
            resumption_source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(module.__file__).parent.glob('*.py')})
        return prior,index_path,revised,record

    def test_resume_skips_successes_preserves_failure_and_charges_new_attempts(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); prior,index,protocol,record=self.fixture(root)
            path=root/'amendment.json'; module.write(path,protocol)
            args=SimpleNamespace(protocol=str(path),output=str(root/'new'),resume_from=str(prior))
            env=SimpleNamespace(trace=SimpleNamespace(fingerprint='fixture',metadata={}))
            def fake(*a,**kw):return copy.deepcopy(record),env
            with patch.object(module,'run_reorder',side_effect=fake) as tour,patch.object(module,'run_response',side_effect=fake) as response:
                result=module.run_validation(args)
            self.assertEqual(tour.call_count,1)
            self.assertEqual(response.call_count,2)
            self.assertEqual(result['total_attempts'],13)
            self.assertEqual(result['failed_attempts'],1)
            self.assertEqual(result['reused_successful_records'],9)
            for p in prior.glob('*.json.gz'):
                self.assertEqual(p.read_bytes(),(root/'new'/p.name).read_bytes())

    def test_pending_authorization_and_changed_protocol_are_rejected(self):
        with TemporaryDirectory() as directory:
            prior,index,protocol,_=self.fixture(Path(directory))
            protocol['amendment']['authorization']='pending_user'
            with self.assertRaisesRegex(ValueError,'pending user'):module.load_resume(protocol,prior,index)
            protocol['amendment']['authorization']='user_approved'
            protocol['extra_visit_budget']=99
            with self.assertRaisesRegex(ValueError,'scientific protocol'):module.load_resume(protocol,prior,index)

    def test_changed_record_or_index_is_rejected(self):
        with TemporaryDirectory() as directory:
            prior,index,protocol,_=self.fixture(Path(directory))
            (prior/'c0-tour.json.gz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'artifact changed'):module.load_resume(protocol,prior,index)
            index.write_text('{}')
            with self.assertRaisesRegex(ValueError,'index identity'):module.load_resume(protocol,prior,index)


if __name__=='__main__':unittest.main()
