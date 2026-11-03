import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


RUNNER_PATH=Path(os.environ.get('RENLY_SUPPLEMENT_RUNNER_PATH',Path(__file__).resolve().parents[1] / 'scripts/run_supplement_study.py'))
SPEC = importlib.util.spec_from_file_location('supplement_runner',RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class StudyGateTests(unittest.TestCase):
    def test_failed_pilot_summary_does_not_unlock_collection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, 'OUT', Path(directory)):
            runner.write_json(Path(directory) / 'pilot-summary.json', {'compound': {'anomaly_segments': 0}})
            with self.assertRaisesRegex(RuntimeError, 'successful preflight'):
                runner.Study().require_preflight()

    def test_authorized_failed_attempt_is_preserved_and_has_new_ordinal(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, 'OUT', Path(directory)):
            study = runner.Study()
            runner.append_log(study.ledger, {'phase': 'pilot', 'id': 'case', 'status': 'started', 'attempt_number': 1})
            runner.append_log(study.ledger, {'phase': 'pilot', 'id': 'case', 'status': 'failed', 'attempt_number': 1})
            runner.write_json(Path(directory) / 'amendments.json', [{'resolved_attempts': [{'phase': 'pilot', 'id': 'case', 'attempt_number': 1}], 'additional_attempts': {'pilot': 1}}])
            original = Path(directory) / 'pilot' / 'case' / 'partial.txt'
            original.parent.mkdir(parents=True); original.write_text('original failed evidence')
            with patch.object(study, 'check_seal'):
                with study.attempt('pilot', 'case'):
                    original.write_text('completed replacement')
            rows = study.entries()
            self.assertEqual([row['status'] for row in rows], ['started', 'failed', 'started', 'completed'])
            self.assertEqual(rows[-1]['attempt_number'], 2)
            retained = Path(directory) / 'retained-failed-attempts/pilot/case/attempt-1/episode/partial.txt'
            self.assertEqual(retained.read_text(), 'original failed evidence')
            with patch.object(study, 'check_seal'), self.assertRaisesRegex(RuntimeError, 'already exists'):
                with study.attempt('pilot', 'case'):
                    pass

    def test_recovery_authorization_does_not_allow_another_failed_retry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, 'OUT', Path(directory)):
            study = runner.Study()
            for number in (1, 2):
                for status in ('started', 'failed'):
                    runner.append_log(study.ledger, {'phase': 'pilot', 'id': 'case', 'status': status, 'attempt_number': number})
            runner.write_json(Path(directory) / 'amendments.json', [{'resolved_attempts': [{'phase': 'pilot', 'id': 'case', 'attempt_number': 1}], 'additional_attempts': {'pilot': 2}}])
            with patch.object(study, 'check_seal'), self.assertRaisesRegex(RuntimeError, 'already exists'):
                with study.attempt('pilot', 'case'):
                    pass

    def test_partial_training_never_locks_final_test_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, 'OUT', Path(directory)):
            study = runner.Study()
            for seed in study.protocol['model_seeds']:
                runner.write_json(Path(directory) / 'training' / f'cvae-{seed}.json', {'history': [{'epoch': 1}]})
            with patch.object(study, 'require_preflight'), self.assertRaisesRegex(RuntimeError, 'epochs incomplete'):
                study.freeze_checkpoints()
            self.assertFalse((Path(directory) / 'test-checkpoint-lock.json').exists())

    def test_policy_retry_preserves_actual_history_and_both_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner,'OUT',Path(directory)):
            study=runner.Study();identifier='nominal-271-001'
            for status in ('started','failed'):
                runner.append_log(study.ledger,{'phase':'ppo_train','id':identifier,'status':status,'attempt_number':1})
            runner.write_json(Path(directory)/'amendments.json',[{'resolved_attempts':[{'phase':'ppo_train','id':identifier,'attempt_number':1}],'additional_attempts':{'ppo_train':1}}])
            originals={'training/ppo-nominal-271.json':'failed-history','checkpoints/ppo-nominal-271.pt':'uncommitted-checkpoint',
                       'checkpoint-recovery/ppo-nominal-271.pt':'last-committed-checkpoint'}
            for relative,value in originals.items():
                path=Path(directory)/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
            with patch.object(study,'check_seal'):
                with study.attempt('ppo_train',identifier,estimator='nominal',model_seed=271):
                    for relative in originals:(Path(directory)/relative).write_text('replacement')
            archive=Path(directory)/'retained-failed-attempts/ppo_train'/identifier/'attempt-1/external'
            for relative,value in originals.items():self.assertEqual((archive/relative).read_text(),value)

    def test_atomic_policy_save_retains_previous_committed_state(self):
        class CheckpointWriter:
            @staticmethod
            def save(value,path):Path(path).write_text(value)
        with tempfile.TemporaryDirectory() as directory:
            current=Path(directory)/'checkpoints/policy.pt';current.parent.mkdir()
            previous=Path(directory)/'checkpoint-recovery/policy.pt'
            current.write_text('episode4')
            runner.atomic_checkpoint(CheckpointWriter,'episode5',current,previous)
            self.assertEqual(current.read_text(),'episode5')
            self.assertEqual(previous.read_text(),'episode4')

    def test_two_crashes_after_save_keep_the_last_committed_policy(self):
        class CheckpointWriter:
            @staticmethod
            def save(value,path):Path(path).write_text(json.dumps(value))
        with tempfile.TemporaryDirectory() as directory:
            current=Path(directory)/'checkpoints/policy.pt';current.parent.mkdir()
            previous=Path(directory)/'checkpoint-recovery/policy.pt';previous.parent.mkdir()
            current.write_text(json.dumps({'episodes':5,'weights':'first-uncommitted'}))
            previous.write_text(json.dumps({'episodes':4,'weights':'committed'}))
            for retry in range(2):
                pack=runner.select_policy_resume_checkpoint(json.loads(current.read_text()),json.loads(previous.read_text()),4)
                runner.restore_policy_checkpoint_for_retry(CheckpointWriter,current,pack,4)
                runner.atomic_checkpoint(CheckpointWriter,{'episodes':5,'weights':f'uncommitted-retry{retry}'},current,previous)
                # Crash here: episode5 never enters the completion ledger.
            recovered=runner.select_policy_resume_checkpoint(json.loads(current.read_text()),json.loads(previous.read_text()),4)
            self.assertEqual(recovered,{'episodes':4,'weights':'committed'})


if __name__ == '__main__':
    unittest.main()
