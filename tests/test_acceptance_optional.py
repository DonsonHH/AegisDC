import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SPEC=importlib.util.spec_from_file_location('repository_acceptance',Path(__file__).resolve().parents[1]/'scripts/acceptance.py')
acceptance=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(acceptance)


def result(skips=(), failures=(), errors=(), run=5):
    return SimpleNamespace(testsRun=run,skipped=[(SimpleNamespace(id=lambda name=name:name),reason) for name,reason in skips],
                           failures=list(failures),errors=list(errors),wasSuccessful=lambda:not failures and not errors)


class OptionalDependencyAcceptanceTests(unittest.TestCase):
    def test_exact_optional_torch_skips_are_reported_without_failing_core(self):
        skips=[(name,acceptance.OPTIONAL_TORCH_REASON) for name in acceptance.OPTIONAL_TORCH_TESTS]
        summary=acceptance.test_summary(result(skips),torch_installed=False)
        self.assertEqual(summary['gate'],'PASS');self.assertEqual(summary['executed'],3)
        self.assertEqual(len(summary['optional_neural_skips']),2);self.assertEqual(summary['unexpected_skips'],[])

    def test_required_test_skip_still_fails(self):
        summary=acceptance.test_summary(result([('test_core.Required.test_contract','disabled')]),torch_installed=False)
        self.assertEqual(summary['gate'],'FAIL');self.assertEqual(len(summary['unexpected_skips']),1)

    def test_wrong_skip_reason_or_installed_but_broken_torch_fails(self):
        name=next(iter(acceptance.OPTIONAL_TORCH_TESTS))
        for installed,reason in [(False,'disabled'),(True,acceptance.OPTIONAL_TORCH_REASON)]:
            with self.subTest(installed=installed,reason=reason):
                self.assertEqual(acceptance.test_summary(result([(name,reason)]),torch_installed=installed)['gate'],'FAIL')

    def test_failures_and_an_all_skipped_suite_are_not_passes(self):
        name=next(iter(acceptance.OPTIONAL_TORCH_TESTS))
        self.assertEqual(acceptance.test_summary(result(failures=['broken']),torch_installed=False)['gate'],'FAIL')
        self.assertEqual(acceptance.test_summary(result([(name,acceptance.OPTIONAL_TORCH_REASON)],run=1),torch_installed=False)['gate'],'FAIL')


if __name__=='__main__':unittest.main()
