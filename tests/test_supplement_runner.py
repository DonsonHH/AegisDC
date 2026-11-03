import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('supplement_runner', Path(__file__).resolve().parents[1] / 'scripts/run_supplement_study.py')
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


if __name__ == '__main__':
    unittest.main()
