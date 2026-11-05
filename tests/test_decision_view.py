"""Literal public-interface examples; no private plant collaborator mocks."""
from copy import deepcopy
import unittest
import math


def example():
    domains = ['power', 'backup', 'facility_cooling', 'equipment_environment',
               'it_service', 'control_monitoring', 'space_access', 'people_tools_work']
    entities = [
        dict(id='room', kind='location', domain='space_access', nominal_location_id=None,
             qualification_ids=[], tool_ids=[]),
        dict(id='pump', kind='asset', domain='facility_cooling', nominal_location_id='room',
             qualification_ids=[], tool_ids=[]),
        dict(id='meter', kind='tool', domain='people_tools_work', nominal_location_id='room',
             qualification_ids=[], tool_ids=[]),
        dict(id='worker', kind='worker', domain='people_tools_work', nominal_location_id='room',
             qualification_ids=['qualified-cooling'], tool_ids=['meter']),
    ]
    knowledge = dict(schema='aegisdc-public-nominal-v1', id='literal-public-design',
        facility_id='literal-synthetic-facility', basis='synthetic_assumption',
        source_note='Declared nominal design, never a current-state snapshot.',
        domain_ids=domains, entities=entities, qualification_ids=['qualified-cooling'],
        work_interfaces=[dict(id='inspect-pump', domain_id='facility_cooling',
            target_ids=['pump'], qualification_id='qualified-cooling', tool_ids=['meter'])],
        graphs={kind: [] for kind in ['physical', 'functional', 'control_information', 'access']},
        reported_constraints=[])
    ledger = dict(schema='aegisdc-evidence-ledger-v1', id='literal-public-evidence',
        facility_id=knowledge['facility_id'], basis='synthetic_assumption', time_unit='s',
        entity_ids=[row['id'] for row in entities],
        observables=[dict(id='offset', quantity='temperature_offset', value_type='number', unit='K')],
        sources=[dict(id='declared-meter', kind='fixed_sensor', basis='synthetic_assumption',
            target_ids=['pump'], observable_ids=['offset'], dependency_group=None,
            source_note='Declared sparse source; not a generated observation.')],
        records=[dict(id='meter-t2', source_id='declared-meter', target_id='pump',
            observable_id='offset', unit='K', value=10, observed_at_s=2, arrived_at_s=3,
            valid_until_s=5, quality=dict(status='bounded', error_bound=.5, note='Literal bound.'),
            provenance=dict(origin_id='carried-t2', copied_from_record_id=None))])
    plan = dict(schema='aegisdc-public-preparation-plan-v1', id='literal-public-plan',
        basis='synthetic_assumption', time_unit='s', decision_times_s=[0, 2, 3],
        requests=[dict(id='public-pump-check', worker_id='worker', work_interface_id='inspect-pump', target_id='pump')])
    return knowledge, ledger, plan


class DecisionViewTests(unittest.TestCase):
    def test_fixed_public_ticks_release_detached_current_plain_frames(self):
        from aegis_dc.decision_view import DecisionGateway
        knowledge, ledger, plan = example()
        gateway = DecisionGateway(knowledge, ledger, plan)
        first = gateway.next_frame()
        self.assertIs(type(first), dict)
        self.assertEqual(first['as_of_s'], 0)
        self.assertEqual(first['evidence']['records'], [])
        self.assertEqual(first['requests'][0]['id'], 'public-pump-check')
        first['nominal_knowledge']['entities'][0]['id'] = 'changed-return'
        knowledge['entities'][0]['id'] = 'changed-input'
        ledger['records'][0]['value'] = -999
        plan['requests'][0]['id'] = 'changed-plan'
        second = gateway.next_frame()
        self.assertEqual(second['as_of_s'], 2)
        self.assertEqual(second['evidence']['records'], [])
        self.assertEqual(second['nominal_knowledge']['entities'][0]['id'], 'room')
        last = gateway.next_frame()
        self.assertEqual(last['as_of_s'], 3)
        self.assertEqual(last['evidence']['current_record_ids'], ['meter-t2'])
        self.assertEqual(last['evidence']['records'][0]['value'], 10)
        self.assertEqual(last['requests'][0]['id'], 'public-pump-check')
        with self.assertRaises(StopIteration):
            gateway.next_frame()
        with self.assertRaises(TypeError):
            gateway.next_frame(100)

    def test_nontrivial_planning_mask_changes_only_after_a_declared_report_arrives(self):
        from aegis_dc.decision_view import DecisionGateway, decision_options, public_feasibility
        knowledge, ledger, plan = example()
        knowledge['entities'] += [
            dict(id='outside', kind='location', domain='space_access', nominal_location_id=None,
                 qualification_ids=[], tool_ids=[]),
            dict(id='outside-pump', kind='asset', domain='facility_cooling', nominal_location_id='outside',
                 qualification_ids=[], tool_ids=[]),
            dict(id='visitor', kind='worker', domain='people_tools_work', nominal_location_id='room',
                 qualification_ids=[], tool_ids=[])]
        ledger['entity_ids'] = [row['id'] for row in knowledge['entities']]
        knowledge['work_interfaces'][0]['target_ids'].append('outside-pump')
        ledger['observables'].append(dict(id='entry-permit', quantity='binary', value_type='boolean', unit='1'))
        ledger['sources'].append(dict(id='gate-report', kind='control_record', basis='synthetic_assumption',
            target_ids=['room'], observable_ids=['entry-permit'], dependency_group=None,
            source_note='Declared remote status channel, not an instantaneous backend query.'))
        knowledge['reported_constraints'] = [dict(id='reported-room-entry', source_id='gate-report',
            target_id='room', observable_id='entry-permit', location_id='room')]
        ledger['records'].append(dict(id='gate-t3', source_id='gate-report', target_id='room',
            observable_id='entry-permit', unit='1', value=False, observed_at_s=3,
            arrived_at_s=4, valid_until_s=6, quality=dict(status='reported', error_bound=None,
                note='A reported restriction, not verified actual access.'),
            provenance=dict(origin_id='carried-gate-t3', copied_from_record_id=None)))
        plan['decision_times_s'] = [math.nextafter(4, -math.inf), 4, 6]
        plan['requests'] += [
            dict(id='bad-credentials', worker_id='visitor', work_interface_id='inspect-pump', target_id='pump'),
            dict(id='outside-check', worker_id='worker', work_interface_id='inspect-pump', target_id='outside-pump')]
        gateway = DecisionGateway(knowledge, ledger, plan)
        before = gateway.next_frame()
        original = deepcopy(before)
        options = decision_options(before)
        self.assertEqual(options['legal_mask'],
                         {'public-pump-check': True, 'bad-credentials': False, 'outside-check': True})
        self.assertEqual(options['demo_choice_id'], 'public-pump-check')
        self.assertFalse(public_feasibility(before, 'public-pump-check')['execution_permission'])
        at = gateway.next_frame()
        result = public_feasibility(at, 'public-pump-check')
        self.assertFalse(result['legal_for_planning'])
        self.assertEqual(result['blocking_record_ids'], ['gate-t3'])
        self.assertEqual(result['physical_feasibility'], 'UNVERIFIED')
        self.assertEqual(decision_options(at)['demo_choice_id'], 'outside-check')
        self.assertEqual(before, original)
        for _ in range(20):
            self.assertEqual(public_feasibility(at, 'public-pump-check'), result)
        expired = gateway.next_frame()
        self.assertTrue(public_feasibility(expired, 'public-pump-check')['legal_for_planning'])
        self.assertFalse(public_feasibility(expired, 'public-pump-check')['execution_permission'])

    def test_nominal_plan_admission_rejects_private_fields_bad_references_and_callbacks(self):
        from aegis_dc.decision_view import DecisionGateway
        mutations = [
            ('nominal-parameters', lambda k, e, p: k.update(parameters={'grid_capacity': 0})),
            ('entity-actual-state', lambda k, e, p: k['entities'][1].update(actual_state='failed')),
            ('worker-occupation', lambda k, e, p: k['entities'][3].update(occupation='busy')),
            ('unknown-location', lambda k, e, p: k['entities'][1].update(nominal_location_id='private-room')),
            ('duplicate-domain', lambda k, e, p: k['domain_ids'].append('power')),
            ('unknown-qualification', lambda k, e, p: k['entities'][3]['qualification_ids'].append('private-role')),
            ('unknown-interface-target', lambda k, e, p: k['work_interfaces'][0]['target_ids'].append('hidden-asset')),
            ('private-edge-field', lambda k, e, p: k['graphs']['access'].append(dict(
                id='a', **{'from': 'room', 'to': 'room'}, kind='walk', bidirectional=True,
                requires_qualification_ids=[], actual_closed=True))),
            ('private-request-field', lambda k, e, p: p['requests'][0].update(case_seed=21)),
            ('duplicate-request', lambda k, e, p: p['requests'].append(deepcopy(p['requests'][0]))),
            ('boolean-clock', lambda k, e, p: p.update(decision_times_s=[False, 2])),
            ('unsorted-clock', lambda k, e, p: p.update(decision_times_s=[2, 0])),
            ('private-ticks-field', lambda k, e, p: p.update(next_private_event_s=.1)),
            ('private-entity-registry', lambda k, e, p: e['entity_ids'].append('hidden-asset')),
            ('unregistered-restriction-channel', lambda k, e, p: k['reported_constraints'].append(dict(
                id='bad-channel', source_id='no-source', target_id='room', observable_id='offset', location_id='room'))),
        ]
        for name, mutation in mutations:
            with self.subTest(case=name):
                knowledge, ledger, plan = example()
                mutation(knowledge, ledger, plan)
                with self.assertRaises(ValueError):
                    DecisionGateway(knowledge, ledger, plan)
        executed = []

        class PrivateState:
            def __deepcopy__(self, memo):
                executed.append('private callback')
                return {}

        knowledge, ledger, plan = example()
        knowledge['entities'][0] = PrivateState()
        with self.assertRaises(ValueError):
            DecisionGateway(knowledge, ledger, plan)
        self.assertEqual(executed, [])

    def test_queries_reject_forged_future_metadata_and_backend_handles(self):
        from aegis_dc.decision_view import DecisionGateway, decision_options, public_feasibility
        knowledge, ledger, plan = example()
        gateway = DecisionGateway(knowledge, ledger, plan)
        empty = gateway.next_frame()
        mutations = [
            ('private-frame-id', lambda frame: frame.update(private_case_seed=4)),
            ('whole-input-hash', lambda frame: frame['evidence'].update(whole_input_sha256='hidden')),
            ('private-source-state', lambda frame: frame['evidence']['static_knowledge']['sources'][0].update(actual_bias=4)),
            ('claimed-independence', lambda frame: frame['evidence'].update(independence='PROVED')),
            ('private-nominal-state', lambda frame: frame['nominal_knowledge']['entities'][1].update(actual_state='off')),
        ]
        for name, mutate in mutations:
            with self.subTest(case=name):
                frame = deepcopy(empty)
                mutate(frame)
                with self.assertRaises(ValueError):
                    decision_options(frame)
        future = deepcopy(empty)
        future['evidence']['records'] = [dict(ledger['records'][0], age_s=-2, availability='current')]
        future['evidence']['current_record_ids'] = ['meter-t2']
        with self.assertRaises(ValueError):
            public_feasibility(future, 'public-pump-check')
        with self.assertRaises(ValueError):
            decision_options(gateway)
        gateway.next_frame()
        current = gateway.next_frame()
        wrong_age = deepcopy(current)
        wrong_age['evidence']['records'][0]['age_s'] = True
        with self.assertRaises(ValueError):
            decision_options(wrong_age)
        equivalent = deepcopy(current)
        equivalent['evidence']['as_of_s'] = 3.0
        equivalent['evidence']['records'][0]['age_s'] = 1.0
        self.assertEqual(decision_options(equivalent), decision_options(current))

    def test_registry_presentation_order_does_not_change_public_frames(self):
        from aegis_dc.decision_view import DecisionGateway, decision_options
        knowledge, ledger, plan = example()
        ledger['observables'].append(dict(id='permit', quantity='binary', value_type='boolean', unit='1'))
        ledger['sources'][0]['observable_ids'].append('permit')
        ledger['sources'].append(dict(deepcopy(ledger['sources'][0]), id='another-declared-source', kind='human_report'))
        permuted = deepcopy(ledger)
        permuted['entity_ids'].reverse()
        permuted['observables'].reverse()
        permuted['sources'].reverse()
        for source in permuted['sources']:
            source['observable_ids'].reverse()
        before = deepcopy(permuted)
        first = DecisionGateway(knowledge, ledger, plan)
        second = DecisionGateway(knowledge, permuted, plan)
        for _ in range(3):
            left, right = first.next_frame(), second.next_frame()
            self.assertEqual(left, right)
            self.assertEqual(decision_options(left), decision_options(right))
            self.assertEqual(left['evidence']['static_knowledge']['entity_ids'],
                             [row['id'] for row in knowledge['entities']])
        self.assertEqual(permuted, before)


if __name__ == '__main__':
    unittest.main()
