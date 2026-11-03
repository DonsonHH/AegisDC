import hashlib
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('source_lineage',Path(__file__).resolve().parents[1]/'scripts/source_lineage.py')
lineage=importlib.util.module_from_spec(spec);spec.loader.exec_module(lineage)


class SourceLineageTests(unittest.TestCase):
    ORIGINAL=b'def status():\n    return "old"\n\ndef metric(x):\n    return x*2\n'

    def test_status_update_keeps_the_original_source_identity(self):
        updated=self.ORIGINAL.replace(b'"old"',b'"new completed study"')
        self.assertTrue(lineage.verify_status_maintenance(updated,self.ORIGINAL,hashlib.sha256(self.ORIGINAL).hexdigest()))

    def test_metric_change_is_not_mistaken_for_status_maintenance(self):
        updated=self.ORIGINAL.replace(b'x*2',b'x*3')
        with self.assertRaisesRegex(ValueError,'outside status'):
            lineage.verify_status_maintenance(updated,self.ORIGINAL,hashlib.sha256(self.ORIGINAL).hexdigest())

    def test_rewritten_historical_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'snapshot SHA'):
            lineage.verify_status_maintenance(self.ORIGINAL,self.ORIGINAL+b'\n',hashlib.sha256(self.ORIGINAL).hexdigest())

    def test_import_time_status_decorator_is_not_allowed(self):
        changed=b'@side_effect\n'+self.ORIGINAL
        with self.assertRaisesRegex(ValueError,'signature or import-time'):
            lineage.verify_status_maintenance(changed,self.ORIGINAL,hashlib.sha256(self.ORIGINAL).hexdigest())

    def test_archival_banner_preserves_the_historical_contract_body(self):
        original=b'# Recorded contract\nunchanged scope\n';prefix='> historical scope\n\n'
        self.assertTrue(lineage.verify_archival_banner(prefix.encode()+original,original,hashlib.sha256(original).hexdigest(),prefix))

    def test_archival_banner_cannot_hide_a_rewritten_contract(self):
        original=b'# Recorded contract\nunchanged scope\n';prefix='> historical scope\n\n'
        with self.assertRaisesRegex(ValueError,'body changed'):
            lineage.verify_archival_banner(prefix.encode()+original.replace(b'unchanged',b'changed'),original,hashlib.sha256(original).hexdigest(),prefix)
