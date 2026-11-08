"""Existing problem-task behaviors through actual facility runs, without mocks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from aegis_dc.plant import save_run, simulate_scenario

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / 'tests/fixtures/39b-triggered-inspection-v2.json').read_text(encoding='utf-8'))


def bind_slots(document, count):
    program = document['dispatch_program']
    program['policy_program']['templates'][0]['max_instances'] = count
    original = deepcopy(program['inspection_program']['profile']['bindings'][0])
    bindings = []
    for slot in range(count):
        binding = deepcopy(original)
        binding.update(task_id='cooling-desk/task-' + str(slot), record_id='repeat-flow-' + str(slot),
                       provenance=dict(origin_id='repeat-flow-' + str(slot), copied_from_record_id=None))
        bindings.append(binding)
    program['inspection_program']['profile']['bindings'] = bindings
    program['inspection_program']['realizations'] = {b['task_id']: dict(seed=23, bias=0, noise_half_width=0) for b in bindings}


class ExistingProblemBehaviorTests(unittest.TestCase):
    def run_case(self, document, name, duration):
        self.facility_calls = getattr(self, 'facility_calls', 0) + 1
        result = simulate_scenario(document['model'], duration_s=duration, step_s=.01,
                                   dispatch_program=document['dispatch_program'])
        self.returned_decisions = getattr(self, 'returned_decisions', 0) + len(result['policy_public_decisions'])
        if os.environ.get('AEGIS_ENGINEERING_RESULT_DIR'):
            output = Path(os.environ['AEGIS_ENGINEERING_RESULT_DIR']) / 'cases' / name
            output.mkdir(parents=True, exist_ok=False)
            save_run(result, output / 'actual-run')
            summary = dict(classification='PRIVATE_EVALUATOR_FINITE_ENGINEERING_QUALIFICATION',
                           case_id=name, code_identity=result['code_identity'],
                           work_records=result['work_records'], summary=result['summary'],
                           inspection_records=result['inspection_public_snapshot']['records'],
                           decisions=[dict(as_of_s=row['frame']['as_of_s'],
                                           chosen_candidate_id=row['choice']['chosen_candidate_id'],
                                           current_record_ids=row['frame']['evidence']['current_record_ids'],
                                           questions=row['choice']['questions'], candidate_audits=row['choice']['candidates'])
                                      for row in result['policy_public_decisions']])
            with (output / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
        return result

    def test_copy_and_delayed_other_case_preserve_stable_instances(self):
        document = fixture();program = document['dispatch_program'];bind_slots(document, 2)
        original = program['evidence_ledger']['records'][0]
        copied = deepcopy(original)
        copied.update(id='cooling-copy-0', arrived_at_s=3.75,
                      provenance=dict(origin_id=original['provenance']['origin_id'], copied_from_record_id=original['id']))
        delayed = deepcopy(original)
        delayed.update(id='cooling-other-case', observed_at_s=-1, arrived_at_s=4,
                       provenance=dict(origin_id='other-declared-case', copied_from_record_id=None))
        program['evidence_ledger']['records'].extend([copied, delayed])
        program['decision_times_s'] = [0, 3.75, 4, 6]
        result = self.run_case(document, 'copy-late', 6)
        decisions = result['policy_public_decisions']
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions],
                         ['cooling-desk/task-0', None, 'cooling-desk/task-1', None])
        self.assertEqual(len(decisions[1]['choice']['questions']), 1)
        instances = decisions[-1]['choice']['question_instances']
        self.assertEqual([(row['slot'], row['origin_id'], row['opened_at_s']) for row in instances],
                         [(0, 'cooling-case-0', 0), (1, 'other-declared-case', 4)])
        tasks = {row['id']: row for row in result['work_records']}
        self.assertEqual(tasks['cooling-desk/task-0']['completed_at_s'], 3.25)
        self.assertEqual(tasks['cooling-desk/task-1']['completed_at_s'], 5.25)
        records = {row['id']: row for row in result['inspection_public_snapshot']['records']}
        self.assertEqual((records['repeat-flow-1']['observed_at_s'], records['repeat-flow-1']['arrived_at_s']), (5.25, 5.75))

    def test_distinct_hidden_flows_have_equal_public_choices_before_measurement(self):
        restricted, clear = fixture(), fixture()
        for document in [restricted, clear]:
            document['dispatch_program']['decision_times_s'] = [0, .5]
        next(row for row in clear['model']['parameters'] if row['id'] == 'filter_resistance_multiplier')['value'] = 1
        first = self.run_case(restricted, 'hidden-restricted', .5)
        second = self.run_case(clear, 'hidden-clear', .5)
        self.assertNotEqual(first['trace'][0]['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'],
                            second['trace'][0]['domains']['facility_cooling']['lake_pump']['volume_flow_m3_s'])
        self.assertEqual(first['policy_public_decisions'], second['policy_public_decisions'])
        self.assertEqual(first['inspection_public_snapshot']['records'], [])
        self.assertEqual(second['inspection_public_snapshot']['records'], [])

    def test_shared_meter_blocks_the_other_professional_until_arrived_release(self):
        document = fixture();program = document['dispatch_program']
        first = program['policy_program']['templates'][0]
        first['id'] = 'a-intake'
        first['task']['deadline_s'] = 30
        second = deepcopy(first)
        second.update(id='b-internal', source_note='Same unconfirmed claim raises another cooling investigation; no independent risk multiplication.')
        second['task'].update(target_id='internal_pump',
                              crew=[dict(worker_id='worker_control', qualification_id='qualified_cooling_inspection')],
                              tool_carrier_id='worker_control')
        program['policy_program']['templates'] = [first, second]
        registry = program['inspection_program']['profile']['nonfixed_profile']['registry']
        source = dict(id='portable-internal-meter', kind='handheld', basis='synthetic_assumption',
                      target_ids=['internal_pump'], observable_ids=['flow'], dependency_group='shared-flow-meter-chain',
                      source_note='Same actual meter, separately paid professional inspection.')
        registry['sources'].append(deepcopy(source));program['evidence_ledger']['sources'].append(deepcopy(source))
        model = deepcopy(program['inspection_program']['profile']['nonfixed_profile']['models'][0])
        model.update(source_id=source['id'], target_id='internal_pump')
        model['model'].update(id='internal-flow', signal_id='internal_pump.volume_flow')
        program['inspection_program']['profile']['nonfixed_profile']['models'].append(model)
        one = program['inspection_program']['profile']['bindings'][0]
        one.update(task_id='a-intake/task-0')
        two = deepcopy(one)
        two.update(task_id='b-internal/task-0', model_id='internal-flow', record_id='internal-flow-result',
                   provenance=dict(origin_id='internal-flow-result', copied_from_record_id=None))
        program['inspection_program']['profile']['bindings'] = [one, two]
        program['inspection_program']['realizations'] = {b['task_id']: dict(seed=23, bias=0, noise_half_width=0) for b in [one, two]}
        program['decision_times_s'] = [0, 1, 4]
        result = self.run_case(document, 'shared-meter', 4.5)
        decisions = result['policy_public_decisions']
        self.assertEqual([row['choice']['chosen_candidate_id'] for row in decisions], ['a-intake/task-0', None, 'b-internal/task-0'])
        blocked = next(row for row in decisions[1]['choice']['candidates'] if row['candidate_id'] == 'b-internal/task-0')
        self.assertIn('PUBLIC_UNACKNOWLEDGED_RESOURCE_OCCUPATION', blocked['reasons'])
        tasks = {row['id']: row for row in result['work_records']}
        self.assertEqual(tasks['a-intake/task-0']['completed_at_s'], 3.25)
        self.assertEqual((tasks['b-internal/task-0']['issued_at_s'], tasks['b-internal/task-0']['started_at_s']), (4, 4))
        self.assertEqual(tasks['b-internal/task-0']['status'], 'travelling')
        self.assertNotIn('internal-flow-result', {row['id'] for row in result['inspection_public_snapshot']['records']})


if __name__ == '__main__':
    unittest.main()
