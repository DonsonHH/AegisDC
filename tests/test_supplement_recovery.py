import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('supplement_recovery',Path(__file__).resolve().parents[1]/'scripts/supplement_recovery.py')
recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)


class PolicyRecoveryTests(unittest.TestCase):
    def test_save_before_ledger_commit_uses_previous_policy(self):
        previous={'episodes':4,'weights':'committed'};current={'episodes':5,'weights':'uncommitted'}
        self.assertIs(recovery.select_policy_resume_checkpoint(current,previous,4),previous)

    def test_first_uncommitted_save_restarts_from_seeded_initialization(self):
        self.assertIsNone(recovery.select_policy_resume_checkpoint({'episodes':1},None,0))

    def test_missing_previous_save_never_silently_skips_an_episode(self):
        with self.assertRaisesRegex(RuntimeError,'matching previous'):
            recovery.select_policy_resume_checkpoint({'episodes':5},None,4)

    def test_fully_committed_policy_is_retained(self):
        current={'episodes':120}
        self.assertIs(recovery.select_policy_resume_checkpoint(current,{'episodes':119},120),current)

    def test_ledger_gap_is_a_failure(self):
        rows=[{'phase':'ppo_train','id':f'nominal-271-{number:03}','status':'completed'} for number in [1,3]]
        with self.assertRaisesRegex(RuntimeError,'ledger has a gap'):
            recovery.completed_policy_prefix(rows,'nominal',271)

    def test_failed_attempt_is_not_a_completed_episode(self):
        rows=[{'phase':'ppo_train','id':'nominal-271-001','status':'completed'},
              {'phase':'ppo_train','id':'nominal-271-002','status':'failed'}]
        self.assertEqual(recovery.completed_policy_prefix(rows,'nominal',271),1)

    def test_state_paths_use_actual_policy_names(self):
        paths=recovery.policy_state_files('study','cvae',1931)
        self.assertEqual(paths['history'],Path('study/training/ppo-cvae-1931.json'))
        self.assertEqual(paths['checkpoint'],Path('study/checkpoints/ppo-cvae-1931.pt'))


if __name__=='__main__':unittest.main()
