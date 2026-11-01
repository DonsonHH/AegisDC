import unittest
import numpy as np

from patrol_rsi.facility_observation import InspectionTask
from patrol_rsi.local_reorder import RoundLedger, LocalPlanChecker


class LineGraph:
    def path(self, a, b):
        return abs(a[0]-b[0]), (a,b)


class ReorderLedgerTests(unittest.TestCase):
    def test_early_completion_removes_only_current_round_obligation(self):
        ledger=RoundLedger([0,1,2,3])
        ledger.commit([2,0,1])
        ledger.dispatch(2)
        key=ledger.complete(2)
        self.assertEqual(key,(0,2))
        self.assertEqual(ledger.remaining,[0,1,3])
        with self.assertRaises(ValueError):ledger.commit([0,1,3])
        for j in (0,1):ledger.dispatch(j);ledger.complete(j)
        ledger.commit([3]);ledger.dispatch(3);ledger.complete(3)
        self.assertEqual(ledger.round_id,1)
        self.assertEqual(ledger.remaining,[0,1,2,3])
        self.assertEqual(ledger.committed,[])

    def test_full_restore_check_rejects_delayed_future_visit(self):
        tasks=[InspectionTask(str(j),'thermal',j,'thermal',10.,(j*10.,0.)) for j in range(3)]
        checker=LocalPlanChecker(LineGraph(),tasks,[0,1,2],np.full(3,100.),'thermal')
        safe=checker.check(5.,(0.,0.),np.full(3,-1.),[0,1,2],[1,0,2],set())
        self.assertTrue(safe['ok'])
        self.assertEqual(safe['segment_completion_s'],[25.,45.,75.])
        bad=checker.check(5.,(0.,0.),np.full(3,-1.),[0,1,2],[2,0,1],set())
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['failed_task'],2)
        self.assertEqual((bad['finish_s'],bad['due_s']),(145.,135.))

    def test_several_committed_rounds_keep_every_obligation(self):
        tasks=[InspectionTask(str(j),'thermal',j,'thermal',10.,(j*10.,0.)) for j in range(3)]
        checker=LocalPlanChecker(LineGraph(),tasks,[0,1,2],np.full(3,100.),'thermal')
        ledger=RoundLedger([0,1,2]);last=np.full(3,-1.);clock=5.;position=(0.,0.)
        for _ in range(5):
            certificate=checker.check(clock,position,last,ledger.remaining,[1,0,2],set())
            self.assertTrue(certificate['ok']);ledger.commit([1,0,2])
            for j,finish in zip((1,0,2),certificate['segment_completion_s']):
                ledger.dispatch(j);ledger.complete(j);last[j]=finish;clock=finish;position=tasks[j].position_m
        self.assertEqual(ledger.round_id,5)
        self.assertEqual(len(set(ledger.completed)),15)

    def test_tail_proof_does_not_forbid_completable_prefix(self):
        tasks=[InspectionTask(str(j),'thermal',j,'thermal',10.,(j*10.,0.)) for j in range(3)]
        checker=LocalPlanChecker(LineGraph(),tasks,[0,1,2],np.full(3,100.),'thermal')
        certificate=checker.check(1770.,(0.,0.),np.array([1750.,1710.,1730.]),[0,1,2],[0,1,2],set())
        self.assertTrue(certificate['ok'])
        self.assertEqual(certificate['segment_completion_s'],[1780.,1800.,1820.])


if __name__=='__main__':unittest.main()
