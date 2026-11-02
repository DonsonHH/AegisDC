import copy
import unittest
from patrol_rsi.response_search import aggregate, paired_outcomes


class ResponseSearchTests(unittest.TestCase):
    def test_development_gate_requires_net_gain_cost_and_zero_violations(self):
        row=dict(gained=1,lost=0,net=1,travel_delta_pct=1,completion_loss_pct=1,wait_s=20,
                 travel_m=101,completed_inspections=99,extra_visits=1,revisit_violations=0,
                 invalid_assignments=0,duplicate_reservations=0)
        limits=dict(minimum_total_net_confirmations=1,maximum_travel_increase_pct=5,maximum_completion_loss_pct=2)
        self.assertTrue(aggregate([row],limits)['eligible'])
        self.assertFalse(aggregate([dict(row,gained=0,net=0)],limits)['eligible'])
        self.assertFalse(aggregate([dict(row,travel_delta_pct=6)],limits)['eligible'])
        self.assertFalse(aggregate([dict(row,revisit_violations=1)],limits)['eligible'])

    def test_pairing_rejects_changed_process_or_interval_and_counts_loss(self):
        m=dict(travel_m=100,completed_inspections=10,consequence_weighted_censored_delay_s=10,
               extra_event_visits=0,tasks_violating_exact_gap=0,invalid_assignments=0,duplicate_reservations=0)
        base=dict(process_sha256='same',metrics=m,anomaly_intervals=[dict(task_id='a',onset_s=0,end_s=30,detected=True)])
        candidate=copy.deepcopy(base);candidate['anomaly_intervals'][0]['detected']=False
        result=paired_outcomes(candidate,base)
        self.assertEqual((result['gained'],result['lost'],result['net']),(0,1,-1))
        candidate['process_sha256']='wrong'
        with self.assertRaises(ValueError):paired_outcomes(candidate,base)
        candidate['process_sha256']='same';candidate['anomaly_intervals'][0]['end_s']=35
        with self.assertRaises(ValueError):paired_outcomes(candidate,base)


if __name__ == '__main__':unittest.main()
