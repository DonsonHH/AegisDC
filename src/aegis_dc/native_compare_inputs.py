"""Materialize committed V6 comparison calls without importing the plant or policies."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from patrol_rsi.contracts import digest


PROTOCOL = 'docs/mainline/v6-native-method-comparison-v1/conditions.json'
CONDITIONS_SHA256 = '3212a7096a57438c54a98e7d1143db4e60f89c865c490d3af993f7b981c0cf4a'
ARMS = ('V','D','K','H','P')


def read(path):
    return json.loads(Path(path).read_bytes())


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        stream.write('\n')


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def locate(document, path):
    for part in path:
        document=document[part]
    return document


def overlay(document, edits):
    for path,value in edits:
        locate(document,path[:-1])[path[-1]]=deepcopy(value)


def apply_changes(document, changes):
    for item in changes:
        path=item['path']
        target=locate(document,path)
        if item['op']=='append' and len(target)==item['old_length']:
            target.append(deepcopy(item['value']))
        elif item['op']=='replace' and digest(target)==digest(item['was']):
            parent=locate(document,path[:-1])
            if 'parameter_id' in item and parent['id']!=item['parameter_id']:
                raise ValueError('Physical parameter identity differs')
            parent[path[-1]]=deepcopy(item['value'])
        else:
            raise ValueError(f'Condition amendment precondition failed: {path}')


def bind(document):
    dispatch=document['dispatch_program']
    policy=dispatch['policy_program']
    business=document['business_program']
    observation=dispatch['inspection_program']['profile']
    policy['inspection_declaration']=deepcopy(observation)
    for declaration in (policy, dispatch['closure_program']):
        declaration['intervention_declaration']=deepcopy(dispatch['intervention_program'])
    reference=business['components']['diagnostic']['reference']
    reference.update({key+'_sha256':digest(value) for key,value in {
        'scenario':document['scenario'],'boundary_events':document['boundary_events'],
        'nominal_knowledge':dispatch['nominal_knowledge'],'ledger':dispatch['evidence_ledger'],
        'workforce_profile':policy['workforce_profile'],'inspection_profile':observation}.items()})
    business['run_binding'].update(scenario_sha256=digest(document['scenario']),dispatch_program_sha256=digest(dispatch),
        boundary_events_sha256=digest(document['boundary_events']),action_commands_sha256=digest([]),
        duration_s=float(document['duration_s']),maximum_step_s=float(document['step_s']))


class Conditions:
    def __init__(self, root):
        self.root=Path(root)
        if file_hash(self.root/PROTOCOL)!=CONDITIONS_SHA256:
            raise ValueError('Comparison protocol identity differs')
        self.protocol=read(self.root/PROTOCOL)
        constructor=self.protocol['constructor']
        for key in ('source_raw','source_normalization'):
            path=constructor[key]
            if file_hash(self.root/path)!=self.protocol['sources'][path]:
                raise ValueError('Frozen input source differs: '+path)
        self.base=read(self.root/constructor['source_raw'])
        self.amendments=read(self.root/constructor['source_normalization'])['units']
        self.rows={row['id']:row for row in self.protocol['conditions']}

    def call(self, condition, arm):
        row=self.rows[condition]
        tokens=self.protocol['constructor']['arm_tokens'][arm]
        source=row['source_unit']
        original=self.base['units'][source]
        if original['base']!='common':
            raise ValueError('Comparison requires the registered common V6 scenario')
        document=deepcopy(self.base['common'])
        for entry in (original,self.amendments[source]):
            overlay(document,entry['edits'])
            if digest(document)!=entry['sha256']:
                raise ValueError('Historical source call binding differs')
        if digest(document)!=row['source_call_sha256']:
            raise ValueError('Incorrect source unit for comparison')
        apply_changes(document,self.protocol['constructor']['common_edits'])
        apply_changes(document,row['row_edits'])
        policy=document['dispatch_program']['policy_program']
        policy.update(schema=tokens['schema'],policy=tokens['policy'])
        if tokens['value_model']=='remove_from_policy':
            del policy['value_model']
        bind(document)
        identities={'complete_call':digest(document),'scenario':digest(document['scenario']),'events':digest(document['boundary_events']),
            'policy_program':digest(policy),'dispatch':digest(document['dispatch_program']),'business':digest(document['business_program'])}
        if identities!=row['arms'][arm]:
            raise ValueError(f'Complete native call differs for {condition}/{arm}')
        return document
