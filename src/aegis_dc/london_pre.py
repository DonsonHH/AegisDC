"""Bounded synthetic London PRE mechanism, frozen-v2 interfaces only.

PhysicalWorld and audit methods belong to the private evaluator. A decision
consumer receives only public_view() data and request() replies, never the
session/evaluator object. This is a data boundary, not a Python security sandbox.
No historical reconstruction, service-benefit or RSI claim is implemented here.
"""
from copy import deepcopy
import json


BITS = frozenset(('vA','vB','cA','cB','sA','sB','permit','accept_enabled',
                  'ready','connected','supports','exec_fault'))
WORLD_FIELDS = BITS | {'profile','completion'}
ACTIONS = ('READ_B_POSITION','READ_B_VOLTAGE')
EVENTS = ('e0','e1','e2','e3','e4')
OUTCOME_FIELDS = ('ordinary','line_present','request','accepted','takeover','effective_support')


def _same(left, right):
    return json.dumps(left,sort_keys=True,allow_nan=False)==json.dumps(right,sort_keys=True,allow_nan=False)


class PhysicalWorld:
    """Private world with explicit inputs and derived results, never an oracle for a requester."""

    def __init__(self, state):
        if type(state) is not dict or set(state)!=WORLD_FIELDS:
            raise ValueError('Use exactly the declared private world fields')
        if any(type(state[key]) is not int or state[key] not in (0,1) for key in BITS):
            raise ValueError('Private logical values must be integer 0 or 1')
        if state['profile'] not in ('LINE_ONLY','PATH_REF') or state['completion'] not in ('BEFORE','AT'):
            raise ValueError('Unknown private profile or completion event')
        self._state=deepcopy(state)

    def mechanics(self):
        s=self._state
        path_a=int(s['vA']==s['cA']==s['sA']==1)
        path_b=int(s['vB']==s['cB']==s['sB']==1)
        ordinary=int(bool(path_a or path_b))
        line_present=int(bool(s['vA'] or s['vB']))
        request=int(not (line_present if s['profile']=='LINE_ONLY' else ordinary))
        accepted=int(bool(request and s['permit'] and s['accept_enabled']))
        takeover=int(bool(s['completion']=='AT' and accepted and s['ready']
                          and s['connected'] and s['supports'] and not s['exec_fault']))
        groups=['g-voltage-A','g-voltage-B'] if s['profile']=='LINE_ONLY' else ['g-path-A','g-path-B']
        return dict(pathA=path_a,pathB=path_b,ordinary=ordinary,line_present=line_present,
                    request=request,accepted=accepted,takeover=takeover,
                    effective_support=int(bool(ordinary or takeover)),plc_requests=[request,request],
                    plc_source_groups=[list(groups),list(groups)])

    def audit(self):
        return dict(state=deepcopy(self._state),mechanics=self.mechanics())


class PRESession:
    """Evaluator-owned session; public methods project only legitimate PRE information."""

    def __init__(self, world, context, mode='DEFINITE'):
        self._world=PhysicalWorld(world)
        if type(context) is not dict or set(context)!={'role','access_slot'}:
            raise ValueError('Declare the trusted public context')
        if context['role'] not in ('AUDITOR','GUEST') or context['access_slot'] not in ('AVAILABLE','EXHAUSTED'):
            raise ValueError('Unknown trusted public context value')
        if mode not in ('DEFINITE','INCONCLUSIVE','CHANNEL_FAILED'):
            raise ValueError('Unknown private observation mode')
        self._context=deepcopy(context)
        self._mode=mode
        self._event='e0'
        self._attempted=False
        self._request=None
        self._admission=None
        self._status=None
        self._occupancy='NONE'
        self._completed=False
        self._pending_observation=None
        self._original=None
        self._copies={}
        self._admissions=0
        self._acquisitions=0

    def request(self, payload):
        """Public admission uses trusted public context, never private world state."""
        valid=(type(payload) is dict and set(payload)=={'action','request_id','target'}
               and payload.get('action') in ACTIONS and payload.get('request_id')=='rq-1'
               and payload.get('target')=='feeder-B')
        if self._attempted or self._event!='e1' or not valid:
            result='INVALID_REQUEST'
        elif self._context['role']!='AUDITOR':
            result='ACCESS_DENIED'
        elif self._context['access_slot']!='AVAILABLE':
            result='RESOURCE_UNAVAILABLE'
        else:
            result='ADMITTED'
        # Invalid later calls must not replace an earlier legitimate request.
        if not self._attempted:
            self._attempted=True
            self._admission=result
            self._status='PENDING' if result=='ADMITTED' else 'REJECTED'
            if result=='ADMITTED':
                self._request=deepcopy(payload)
                self._occupancy='RESERVED'
                self._admissions+=1
        return result

    def advance(self, event):
        index=EVENTS.index(self._event)
        if index+1>=len(EVENTS) or event!=EVENTS[index+1]:
            raise ValueError('Advance one declared PRE event at a time')
        self._event=event
        if self._admission!='ADMITTED':return
        if event=='e2':
            action=self._request['action']
            is_position=action=='READ_B_POSITION'
            definite=self._mode=='DEFINITE'
            self._pending_observation=dict(record_id='obs-1',target='feeder-B',
                quantity='breaker_position' if is_position else 'upstream_voltage',
                value=self._world._state['cB' if is_position else 'vB'] if definite else 'UNKNOWN',
                status='KNOWN' if definite else 'NO_RESULT',
                physical_provenance_group='g-pos-B' if is_position else 'g-voltage-B',
                observed_at='e2',available_at='e3',expires_at='e4',receiver='AUDITOR',
                request_id='rq-1',action=action)
            self._completed=True
            self._occupancy='RELEASED'
            self._acquisitions+=1
        elif event=='e3':
            self._original=deepcopy(self._pending_observation)
            self._status='RESULT_AVAILABLE'
        elif event=='e4':
            self._status='EXPIRED'

    def public_view(self):
        history=([self._original]+[self._copies[key] for key in sorted(self._copies)]
                 if self._original is not None else [])
        return deepcopy(dict(event=self._event,context=self._context,target='feeder-B',
            supported_actions=list(ACTIONS),request_status=self._status,admission=self._admission,
            occupancy=self._occupancy,completed=self._completed,
            current_observations=[self._original] if self._event=='e3' and self._original is not None else [],
            history=history))

    def audit_material(self, envelope):
        """Private delivery audit against already-public records, not hidden defect truth.

        Rejection never changes authoritative publication and is not exposed by
        public_view. Only valid propagation copies may append public history.
        """
        if type(envelope) is not dict or set(envelope)!={'records'} or type(envelope['records']) is not list:
            return 'INVALID_MATERIAL'
        records=envelope['records']
        if self._original is None:
            return 'ACCEPTED' if not records else 'INVALID_MATERIAL'
        original_seen=False
        copies=deepcopy(self._copies)
        try:
            for row in records:
                if type(row) is not dict:return 'INVALID_MATERIAL'
                if row.get('record_id')=='obs-1':
                    if not _same(row,self._original):return 'INVALID_MATERIAL'
                    original_seen=True
                elif row.get('record_id')=='obs-copy':
                    received=row.get('copy_received_at')
                    if received not in ('e3','e4') or EVENTS.index(received)>EVENTS.index(self._event):
                        return 'INVALID_MATERIAL'
                    expected=dict(self._original,record_id='obs-copy',copy_of='obs-1',copy_received_at=received)
                    if not _same(row,expected):return 'INVALID_MATERIAL'
                    if 'obs-copy' in copies:
                        if not _same(row,copies['obs-copy']):return 'INVALID_MATERIAL'
                    elif received!=self._event:
                        return 'INVALID_MATERIAL'
                    copies['obs-copy']=deepcopy(row)
                else:return 'INVALID_MATERIAL'
        except (ValueError,TypeError):
            return 'INVALID_MATERIAL'
        if not original_seen:return 'INVALID_MATERIAL'
        self._copies=copies
        return 'ACCEPTED'

    def audit(self):
        result=self._world.audit()
        groups=sorted({record['physical_provenance_group'] for record in self.public_view()['history']})
        result.update(mode=self._mode,admissions=self._admissions,acquisitions=self._acquisitions,
                      provenance_groups=groups)
        return result


class ChallengeRun:
    """Continuous private f/u/BEFORE/AT process on the same PRE world instance."""

    def __init__(self, world, context, mode='DEFINITE'):
        # The challenge schema is intentionally the frozen v2 route family.
        expected=dict(vA=1,vB=1,cA=1,cB=0,sA=1,sB=1,profile=world.get('profile') if type(world) is dict else None,
            permit=1,accept_enabled=1,ready=1,connected=1,supports=1,exec_fault=0,completion='BEFORE')
        if not _same(world,expected) or context!={'role':'AUDITOR','access_slot':'AVAILABLE'} or mode!='DEFINITE':
            raise ValueError('Use a complete declared challenge PRE initial state')
        self._pre=PRESession(world,context,mode)
        self._event='e0'
        self._frozen=None
        self._state_anchor=None

    def request(self, payload):
        if self._event not in EVENTS:
            raise ValueError('No PRE requests after freezing')
        if payload!={'request_id':'rq-1','action':'READ_B_POSITION','target':'feeder-B'}:
            raise ValueError('Challenge PRE uses the declared position request')
        return self._pre.request(payload)

    def public_view(self):
        return self._pre.public_view()

    def advance(self, event):
        if event in EVENTS:
            if self._event not in EVENTS:raise ValueError('Frozen PRE cannot be resumed')
            self._pre.advance(event)
            self._event=event
            return
        sequence={'e4':'f','f':'u','u':'j_before','j_before':'j_at'}
        if sequence.get(self._event)!=event:
            raise ValueError('Advance the same frozen challenge chain in order')
        if event=='f':
            if self._pre._acquisitions!=1 or self._pre._original is None or self._pre._copies:
                raise ValueError('Complete the declared unmodified PRE lifecycle before freezing')
            # Retain the actual mutable-state object so replacement cannot hide
            # behind wrapper identity or allocator reuse of a released ID.
            self._state_anchor=self._pre._world._state
            self._frozen=dict(state=deepcopy(self._pre._world._state),
                              public_view=self._pre.public_view(),challenge={'vA':0,'completion':'AT'})
        elif event=='u':
            self._pre._world._state['vA']=0
        elif event=='j_at':
            self._pre._world._state['completion']='AT'
        self._event=event

    def audit(self):
        data=self._pre._world.audit()
        return dict(event=self._event,state=data['state'],
                    outcome={key:data['mechanics'][key] for key in OUTCOME_FIELDS},
                    frozen=deepcopy(self._frozen),state_identity=id(self._pre._world._state))
