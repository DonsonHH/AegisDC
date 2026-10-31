import unittest

from patrol_rsi.multistep_workflow import Workflow
from patrol_rsi.multistep_proposal import compile_compact


class CompactProposalTests(unittest.TestCase):
    def test_fixed_metadata_is_explicit_and_model_fields_are_not_repaired(self):
        parent = Workflow()
        child, envelope = compile_compact('{"changes":{"after_alarm":"global"},"mechanism":"Use other supported tasks."}', parent)
        self.assertEqual(child.after_alarm, 'global')
        self.assertEqual(envelope['parent_sha256'], parent.sha256)
        for raw in ['{"changes":{"K":3},"mechanism":"Unsafe"}',
                    '{"changes":{"after_alarm":"global"}}',
                    '{"changes":{"after_alarm":"global"},"mechanism":"x","extra":1}']:
            with self.assertRaises(ValueError):
                compile_compact(raw, parent)


if __name__ == '__main__':
    unittest.main()
