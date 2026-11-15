"""Finite London PRE E1-E4 model; no research comparison or fixture lookup.

E14Run is evaluator-owned. Only detached public_view data may be passed to
decide. Local control consumes its declared signal pack, never the world.
Exact rational event times avoid favorable epsilon ordering at cutoffs.
"""
from copy import deepcopy
from fractions import Fraction
import heapq


def rational(value):
    if type(value) not in (int, str):
        raise ValueError('Expected integer or rational string')
    return Fraction(value)


def encode(value):
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return deepcopy(value)


CHANNELS = ('zVA', 'zVB', 'zCA', 'zCB', 'zSA', 'zSB')
FAMILIES = ('LEGACY_LINE', 'REVISED_LOCAL')
READS = ('READ_POS', 'READ_VOLT', 'READ_CONFIG')


def local_control(family, signals, time):
    if family not in FAMILIES or set(signals) != set(CHANNELS):
        raise ValueError('Invalid local control input')
    now = rational(time)
    effective = {}
    for name, channel in signals.items():
        if set(channel) != {'value', 'quality', 'sample_time'}:
            raise ValueError('Incomplete channel')
        sampled = rational(channel['sample_time'])
        quality, value = channel['quality'], channel['value']
        if sampled > now or quality not in ('OK', 'MISSING'):
            raise ValueError('Illegal sample time/quality')
        if quality == 'OK' and (type(value) is not int or value not in (0, 1)):
            raise ValueError('Invalid definite channel value')
        if quality == 'MISSING' and value != 'UNKNOWN':
            raise ValueError('Missing channel must be UNKNOWN')
        effective[name] = quality == 'OK' and sampled == now and value == 1
    if family == 'LEGACY_LINE':
        supported = effective['zVA'] or effective['zVB']
    else:
        supported = any(all(effective['z' + x + p] for x in ('V', 'C', 'S')) for p in ('A', 'B'))
    return int(not supported)


def decide(view, method):
    """One pure public decision. No access to a session or private config."""
    if method not in ('M0', 'B1'):
        raise ValueError('Unknown fixed method')
    v = deepcopy(view)
    c = v['context']
    now = rational(v['time'])
    def result(action, reason=None):
        return dict(action=action, mode='EVIDENCE' if action == 'PROPOSE_FIX' else None,
                    reason=reason or action)
    if not v['pre_open'] or now >= rational(c['window'][1]):
        return result('STOP')
    if v['terminal_failure']:
        return result('STOP_UNRESOLVED')
    if v['pending']:
        return result('WAIT_PENDING')
    known_epoch=v.get('known_epoch')
    execution=[r for r in v['receipts'] if r.get('record_kind')=='EXECUTION_RECEIPT' and r.get('status')=='EXECUTED_UNVERIFIED']
    records = [r for r in v['records'] if rational(r['available_at']) <= now < rational(r['expires_at'])
               and r['problem_id'] == 'q-1' and r['maintenance_epoch'] == 'm0' and r['receiver_role']=='AUDITOR'
               and r['target']==('feeder-B' if r.get('action') in ('READ_POS','READ_VOLT') or r.get('claim_field')=='breaker_position' else 'ctrl-1')
               and (r.get('config_epoch') is None or known_epoch is None or r['config_epoch']>=known_epoch)]
    if any(r.get('action') == 'VERIFY_CTRL' and r['status'] == 'VERIFIED_FOR_TARGET' and any(r.get('parent_execution_id')==e['execution_id'] and r.get('config_epoch')==e['target_config_epoch'] for e in execution) for r in records):
        return result('NO_ACTION_CURRENT_SCOPE')
    if v['phase'] == 'AWAITING_VERIFY':
        if c['permissions']['verify'] != 'ALLOW' or rational(c['available']) < rational(c['read_reserve']):
            return result('INSUFFICIENT_INFORMATION')
        return result('VERIFY_CTRL')
    values = []
    for action in READS:
        found = {r['value'] for r in records if r['status'] == 'KNOWN' and
                 (r.get('action') == action or action == 'READ_POS' and r.get('claim_field') == 'breaker_position')}
        values.append(next(iter(found)) if len(found) == 1 else None)
    tests = [None if x is None else x == target for x, target in zip(values, [0, 1, 'LEGACY_LINE'])]
    if False in tests:
        return result('NO_ACTION_CURRENT_SCOPE')
    if None in tests:
        for action, value in zip(READS, values):
            if value is None and action not in v['attempted'] and c['permissions']['read'] == 'ALLOW' and c['read_parameters_known'] and rational(c['available']) >= rational(c['read_reserve']):
                return result(action)
        return result('INSUFFICIENT_INFORMATION')
    if not c['chain_parameters_known'] or c['compatible'] == 'UNKNOWN' or c['permissions']['propose'] == 'UNKNOWN':
        return result('INSUFFICIENT_INFORMATION')
    if c['compatible'] != 'ALLOW' or c['permissions']['propose'] != 'ALLOW' or rational(c['available']) < rational(c['chain_reserve']) or rational(c['chain_finish']) >= rational(c['window'][1]):
        return result('INFEASIBLE')
    certificate = v['certificate']
    identical = certificate and certificate.get('kind') == 'PLAN_IDENTITY' and certificate.get('problem_id') == 'q-1' and certificate.get('target') == 'ctrl-1' and certificate.get('plan') == 'FIX_CTRL-v1' and certificate.get('version') == 1 and rational(certificate.get('expires_at', 0)) > now
    return result('PROPOSE_FIX', 'D3' if method == 'M0' and identical else 'C5')


FIELDS = set('H tF tR P E0 vA vB cA cB capA capB capG family epoch ready connected permit exec_fault tauG tauB read_work publish ttl approval_work prep commit_work exit_work verify_work budget calendar window grant_expiry revoke work_mode approval commit verification exit_result guard compatible permissions read_modes signal_missing demand'.split())
NUMBERS = set('H P E0 capA capB capG tauG tauB read_work publish ttl approval_work prep commit_work exit_work verify_work budget grant_expiry'.split())


class E14Run:
    """One continuous private state with public admission and timed projection."""

    def __init__(self, config):
        if type(config) is not dict or set(config) != FIELDS:
            raise ValueError('Complete closed E1-E4 input required')
        self.original = deepcopy(config)
        self.c = deepcopy(config)
        for key in NUMBERS:
            self.c[key] = rational(config[key])
        for key in ('tF', 'tR'):
            self.c[key] = None if config[key] is None else rational(config[key])
        self.c['window'] = [rational(x) for x in config['window']]
        self.c['calendar'] = [[rational(x) for x in row] for row in config['calendar']]
        self.c['demand'] = [[rational(row[0]), row[1]] for row in config['demand']]
        self.c['revoke'] = None if config['revoke'] is None else [rational(config['revoke'][0]), config['revoke'][1]]
        c = self.c
        if c['family'] not in FAMILIES or not 0 < c['H'] <= 100 or not 0 < c['P'] <= 10 or not 0 <= c['E0'] <= 100:
            raise ValueError('Out of finite domain')
        if c['tF'] is None and c['tR'] is not None or c['tR'] is not None and c['tR'] < c['tF']:
            raise ValueError('Invalid fault interval')
        if any(c[k] <= 0 for k in ('tauG','tauB','read_work','publish','prep','commit_work','exit_work','verify_work')) or c['publish'] >= c['ttl']:
            raise ValueError('Invalid duration/TTL')
        if c['budget'] < 0 or c['epoch'] != 0 or any(c[k] not in (0, c['P']) for k in ('capA','capB','capG')):
            raise ValueError('Invalid capacity/budget/epoch')
        for key in ('vA','vB','cA','cB'):
            if type(c[key]) is not int or c[key] not in (0,1):raise ValueError('Invalid physical bit')
        for key in ('ready','connected','permit','exec_fault'):
            if type(c[key]) is not bool:raise ValueError('Invalid physical predicate')
        if c['work_mode'] not in ('ONLINE','LOAD_ISOLATED') or c['approval'] not in ('APPROVE','DENY') or c['commit'] not in ('SUCCESS','FAIL') or c['exit_result'] not in ('SUCCESS','FAIL'):
            raise ValueError('Invalid execution plan')
        if set(c['read_modes']) != set(READS) or any(x not in ('DEFINITE','INCONCLUSIVE','CHANNEL_FAILED') for x in c['read_modes'].values()) or c['verification'] not in ('PASS','FAIL','INCONCLUSIVE','CHANNEL_FAILED'):
            raise ValueError('Invalid observation plan')
        if set(c['permissions']) != {'read','propose','verify','direct'} or any(x not in ('ALLOW','DENY','UNKNOWN') for x in c['permissions'].values()):raise ValueError('Invalid public context')
        if c['guard'] not in ('ALLOW','BLOCK') or c['compatible'] not in ('ALLOW','DENY','UNKNOWN') or not set(c['signal_missing']).issubset(CHANNELS):raise ValueError('Invalid local/public input')
        if c['window'][0] < 0 or not c['window'][0] < c['window'][1] <= c['H'] or not c['demand'] or c['demand'][0][0] != 0:
            raise ValueError('Invalid public window/demand')
        if any(t < 0 or t > c['H'] or d not in (0,1) for t,d in c['demand']) or any(c['demand'][i][0] >= c['demand'][i+1][0] for i in range(len(c['demand'])-1)):
            raise ValueError('Invalid demand schedule')
        if any(a < 0 or b <= a or b > c['H'] for a,b in c['calendar']) or any(c['calendar'][i][1] > c['calendar'][i+1][0] for i in range(len(c['calendar'])-1)):
            raise ValueError('Invalid reservations')
        if any(t is not None and not 0 <= t <= c['H'] for t in (c['tF'],c['tR'])) or c['approval_work'] < 0:raise ValueError('Invalid external time')
        if c['revoke'] and (not 0 <= c['revoke'][0] <= c['H'] or c['revoke'][1] not in ('READ_ROLE','FIX_GRANT')):raise ValueError('Invalid revocation')
        self.time = Fraction(0)
        self._state = dict(family=c['family'],epoch=0,vA=c['vA'])
        self.queue=[];self.serial=0;self.events=[];self.operations=[];self.segments=[]
        self.phase='NONE';self.commit_result='NOT_ATTEMPTED';self.verification_result='NOT_REQUESTED'
        self.pre_open=True;self.terminal_failure=False;self.grant_valid=False;self.fix=None
        self.active=None;self.queued=None;self.reserved=Fraction(0);self.spent=Fraction(0);self.reserve_end=None
        self.resource_overrun=False;self.isolated=False;self.started_actions=[];self.attempted=[];self.requests={}
        self.observations=[];self.receipts=[];self.copies=[];self.pending_publications=0;self.pending_receipts=0;self.internal_grant=None
        self.read_status='NONE';self.g_state='IDLE';self.g_due=None;self.device='RUNNING';self.boot_due=None
        self.E=c['E0'];self.L=Fraction(0);self.U=Fraction(0);self.load_energy=Fraction(0);self.ups_energy=Fraction(0)
        self.source=None;self.recoveries=[];self.off_since=None
        self._schedule(c['H'],9,'horizon')
        self._schedule(c['window'][1],2,'window')
        for t,kind in [(c['tF'],'fault'),(c['tR'],'restore')]:
            if t is not None:self._schedule(t,2,kind)
        if c['revoke']:self._schedule(c['revoke'][0],2,'revoke',c['revoke'][1])
        for t,d in c['demand'][1:]:self._schedule(t,2,'demand')
        self._events_at_now()
        self._reconcile()

    def _schedule(self,time,priority,kind,data=None):
        if kind=='publish_receipt':self.pending_receipts+=1
        heapq.heappush(self.queue,(time,priority,self.serial,kind,deepcopy(data)));self.serial+=1

    def _signals(self):
        c=self.c
        values=[self._state['vA'],c['vB'],c['cA'],c['cB'],int(c['capA']>=c['P']),int(c['capB']>=c['P'])]
        return {k:dict(value='UNKNOWN' if k in c['signal_missing'] else v,quality='MISSING' if k in c['signal_missing'] else 'OK',sample_time=encode(self.time)) for k,v in zip(CHANNELS,values)}

    def _g_conditions(self):
        return self.c['permit'] and self.c['ready'] and self.c['connected'] and self.c['capG'] >= self.c['P']

    def _demand(self):
        return next(d for t,d in reversed(self.c['demand']) if t <= self.time)

    def _reconcile(self):
        c=self.c;t=self.time
        if c['tF'] is not None and t>=c['tF']:
            self._state['vA']=int(c['tR'] is not None and t>=c['tR'])
        if self.g_state=='IDLE' and local_control(self._state['family'],self._signals(),encode(t)):
            if self._g_conditions():
                self.g_state='STARTING';self.g_due=t+c['tauG'];self._schedule(self.g_due,3,'g_complete')
            else:self.g_state='FAILED'
        source=None
        if not self.isolated:
            if self._state['vA'] and c['cA'] and c['capA']>=c['P']:source='A'
            elif c['vB'] and c['cB'] and c['capB']>=c['P']:source='B'
            elif self.g_state=='RUNNING' and self._g_conditions():source='G'
            elif self.E>0:source='UPS'
        self.source=source
        if source is None:
            if self.device!='OFF':
                if self.off_since is None:self.off_since=t
                self.device='OFF';self.boot_due=None
        elif self.device=='OFF':
            self.device='BOOTING';self.boot_due=t+c['tauB'];self._schedule(self.boot_due,5,'boot_complete',self.boot_due)

    def _integrate(self,end):
        start=self.time;dt=end-start
        if not dt:return
        P=self.c['P'] if self.source else Fraction(0)
        D=self._demand();served=D if self.device=='RUNNING' and self.source else 0
        loss=int(D>0 and served==0)
        self.L+=dt*loss;self.U+=dt*(D-served);self.load_energy+=dt*P
        if self.source=='UPS':self.E-=dt*P;self.ups_energy+=dt*P
        if self.active:
            self.spent+=dt;self.reserved=max(Fraction(0),self.reserved-dt)
            if self.reserve_end is not None and end>self.reserve_end:self.resource_overrun=True
        self.segments.append(encode(dict(start=start,end=end,source=self.source,power=P,demand=D,service=served,device=self.device,isolated=self.isolated,occupied=self.active is not None)))
        self.time=end

    def advance(self,time):
        target=rational(time)
        if target<self.time or target>self.c['H']:raise ValueError('Monotone bounded clock required')
        while self.time<target:
            nxt=min(target,self.queue[0][0] if self.queue else target)
            if self.source=='UPS' and self.E>0:nxt=min(nxt,self.time+self.E/self.c['P'])
            self._integrate(nxt);self._events_at_now();self._reconcile()
        self._events_at_now();self._reconcile()
        return self.public_view()

    def _events_at_now(self):
        while self.queue and self.queue[0][0]==self.time:
            _,_,_,kind,data=heapq.heappop(self.queue)
            self.events.append(encode(dict(time=self.time,event=kind)))
            self._event(kind,data)

    def _event(self,kind,data):
        t=self.time;c=self.c
        if kind in ('fault','window'):
            self.pre_open=False;self._abort('CUTOFF')
        elif kind=='restore':pass
        elif kind=='revoke':
            if data=='READ_ROLE':
                c['permissions']['read']='DENY';c['permissions']['verify']='DENY'
                if self.active and self.active['kind']=='read':self._abort('READ_REVOKED')
                if self.queued and self.queued['kind']=='read':self.queued=None;self.read_status='ABORTED_READ'
            else:
                self.grant_valid=False
                if self.commit_result!='SUCCESS':self._abort('GRANT_REVOKED')
        elif kind=='expiry':
            self.grant_valid=False
            if self.commit_result!='SUCCESS':self._abort('GRANT_EXPIRED')
        elif kind=='approval':self._approve()
        elif kind=='start':
            if self.queued and self.queued['request']['request_id']==data and self.pre_open:
                job=self.queued;self.queued=None
                permitted=job['kind']!='read' or c['permissions']['read']=='ALLOW' and (job['request']['action']!='VERIFY_CTRL' or c['permissions']['verify']=='ALLOW')
                if permitted:self._start(job)
                else:self.read_status='ABORTED_READ'
        elif kind=='read_complete':
            if self.active and self.active['kind']=='read' and self.active['request']['request_id']==data:self._sample()
        elif kind=='prepare_complete':
            if self.phase=='PREPARING' and self.active:
                self.phase='IMPLEMENTING';self._schedule(t+c['commit_work'],4,'commit_complete')
        elif kind=='commit_complete':
            if self.phase=='IMPLEMENTING' and self.active:self._commit()
        elif kind=='exit_complete':
            if self.active and self.active['kind']=='exit':self._exit_complete()
        elif kind=='g_complete':
            if self.g_state=='STARTING':self.g_state='RUNNING' if self._g_conditions() and not c['exec_fault'] else 'FAILED'
        elif kind=='boot_complete':
            # Reconcile supply first, including exact depletion and same-time source recovery.
            self._reconcile()
            if self.device=='BOOTING' and self.boot_due==data and self.source:
                self.device='RUNNING';self.boot_due=None
                if self.off_since is not None:
                    self.recoveries.append(dict(off=self.off_since,recovered=t,duration=t-self.off_since,right_censored=False));self.off_since=None
        elif kind=='publish_observation':
            self.pending_publications-=1
            if c['permissions']['read']=='ALLOW' and (data['action']!='VERIFY_CTRL' or c['permissions']['verify']=='ALLOW'):
                self.observations.append(data);self.read_status='RESULT_AVAILABLE'
                if data['action']=='VERIFY_CTRL' and self.pre_open:
                    self.verification_result={'VERIFIED_FOR_TARGET':'PASS','VERIFY_FAILED':'FAIL','INCONCLUSIVE':'INCONCLUSIVE'}[data['status']]
                    self.phase='TERMINAL';self.terminal_failure=self.verification_result!='PASS'
        elif kind=='publish_receipt':self.pending_receipts-=1;self.receipts.append(data)

    def _slot(self,duration):
        start=max(self.time,self.c['window'][0])
        for a,b in self.c['calendar']:
            if start<b and start+duration>a:start=b
        return start if start+duration<=self.c['window'][1] else None

    def _public_chain_plan(self):
        """Public calendar/recipe feasibility; never reads the fault plan."""
        c=self.c
        work=c['prep']+c['commit_work']+c['exit_work']
        def slot(start,duration):
            start=max(start,c['window'][0])
            for a,b in c['calendar']:
                if start<b and start+duration>a:start=b
            return start
        begin=slot(self.time+c['approval_work'],work)
        commit=begin+c['prep']+c['commit_work']
        verify=slot(max(begin+work,commit+c['publish']),c['verify_work']+c['exit_work'])
        finish=verify+c['verify_work']+c['publish']
        resource_end=verify+c['verify_work']+c['exit_work']
        return work+c['verify_work']+c['exit_work'],finish,resource_end

    def _reserve(self,duration):
        self.reserved=duration;self.reserve_end=self.time+duration

    def _start(self,job):
        self.active=job;duration=job['reserve'];self._reserve(duration)
        action=job['request']['action'];self.started_actions.append(action)
        if job['kind']=='read':
            self.read_status='WORKING'
            if action=='VERIFY_CTRL':self.phase='VERIFYING';self.verification_result='PENDING'
            work=self.c['verify_work'] if action=='VERIFY_CTRL' else self.c['read_work']
            self._schedule(self.time+work,4,'read_complete',job['request']['request_id'])
        else:
            self.phase='PREPARING';self.isolated=self.c['work_mode']=='LOAD_ISOLATED'
            self._schedule(self.time+self.c['prep'],4,'prepare_complete')
        self._reconcile()

    def _release(self):
        self.active=None;self.reserved=Fraction(0);self.reserve_end=None

    def _sample(self):
        request=self.active['request'];action=request['action'];c=self.c;t=self.time
        value='UNKNOWN';status='NO_RESULT';epoch=None;parent=None
        if action=='VERIFY_CTRL':
            epoch=self._state['epoch'];parent='ex-1'
            probe={k:dict(value=v,quality='OK',sample_time=encode(t)) for k,v in zip(CHANNELS,[0,1,1,0,1,1])}
            passed=c['verification']=='PASS' and epoch==request['target_config_epoch'] and self._state['family']=='REVISED_LOCAL' and local_control(self._state['family'],probe,encode(t))==1
            if c['verification'] in ('INCONCLUSIVE','CHANNEL_FAILED'):status='INCONCLUSIVE'
            else:value='PASS' if passed else 'FAIL';status='VERIFIED_FOR_TARGET' if passed else 'VERIFY_FAILED'
            group='probe-local'
        else:
            group={'READ_POS':'pos-B','READ_VOLT':'volt-B','READ_CONFIG':'cfg-local'}[action]
            channel={'READ_POS':'zCB','READ_VOLT':'zVB','READ_CONFIG':None}[action]
            if c['read_modes'][action]=='DEFINITE' and channel not in c['signal_missing']:
                status='KNOWN';value={'READ_POS':c['cB'],'READ_VOLT':c['vB'],'READ_CONFIG':self._state['family']}[action]
            if action=='READ_CONFIG':epoch=self._state['epoch']
        record=dict(record_kind='ACTION_RESULT',record_id='obs-'+str(len(self.observations)+1),problem_id='q-1',request_id=request['request_id'],action=action,target=request['target'],value=value,status=status,source_group=group,observed_at=t,available_at=t+c['publish'],expires_at=t+c['ttl'],maintenance_epoch='m0',receiver_role='AUDITOR',config_epoch=epoch,parent_execution_id=parent)
        self._release();self.read_status='PENDING_PUBLICATION';self.pending_publications+=1
        self._schedule(t+c['publish'],6,'publish_observation',record)

    def _receipt(self,kind,**fields):
        row=dict(record_kind=kind,request_id=self.fix['request_id'],action='FIX_CTRL',problem_id='q-1',target='ctrl-1',receiver_role='AUDITOR',**fields)
        self._schedule(row['available_at'],6,'publish_receipt',row)

    def _approve(self):
        if self.phase!='PROPOSED' or not self.pre_open:return
        c=self.c;t=self.time
        approved=c['approval']=='APPROVE' and c['permissions']['propose']=='ALLOW' and c['compatible']=='ALLOW'
        row=dict(record_kind='APPROVAL_RECEIPT',request_id=self.fix['request_id'],action='FIX_CTRL',problem_id='q-1',target='ctrl-1',decision='APPROVE' if approved else 'DENY',grant_id='grant-1' if approved else None,decided_at=t,available_at=t,receiver_role='EXECUTOR')
        self.internal_grant=deepcopy(row)
        self._schedule(t+c['publish'],6,'publish_receipt',dict(row,available_at=t+c['publish'],receiver_role='AUDITOR'))
        if not approved:self.phase='TERMINAL';self.terminal_failure=True;return
        if c['grant_expiry']<=t:self._not_implemented();return
        self.grant_valid=True;self._schedule(c['grant_expiry'],2,'expiry')
        reserve=c['prep']+c['commit_work']+c['exit_work'];start=self._slot(reserve)
        if start is None or start+c['prep']+c['commit_work']>=c['grant_expiry'] or self._available()<reserve:
            self._not_implemented();return
        self.phase='QUEUED';self.queued=dict(kind='fix',request=self.fix,reserve=reserve)
        self._schedule(start,7,'start',self.fix['request_id'])

    def _commit(self):
        c=self.c;t=self.time
        allowed=self.pre_open and self.grant_valid and t<c['window'][1] and t<c['grant_expiry'] and c['guard']=='ALLOW'
        if allowed and c['commit']=='SUCCESS':
            self._state['family']='REVISED_LOCAL';self._state['epoch']+=1;self.commit_result='SUCCESS'
            self._receipt('EXECUTION_RECEIPT',status='EXECUTED_UNVERIFIED',committed_at=t,available_at=t+c['publish'],execution_id='ex-1',target_config_epoch=self._state['epoch'])
            self._begin_exit()
        else:
            if allowed:self.commit_result='FAIL'
            self._not_implemented()

    def _not_implemented(self):
        self.terminal_failure=True
        self._receipt('EXECUTION_RECEIPT',status='NOT_IMPLEMENTED',committed_at=None,available_at=self.time+self.c['publish'],execution_id=None,target_config_epoch=None)
        if self.active:self._begin_exit()
        else:self.phase='TERMINAL';self.queued=None

    def _begin_exit(self):
        self.active=dict(kind='exit',request=self.active['request'],for_read=self.active['kind']=='read')
        if not self.active['for_read']:self.phase='EXITING'
        self._schedule(self.time+self.c['exit_work'],3,'exit_complete')

    def _exit_complete(self):
        if self.c['exit_result']=='FAIL':return
        was_read=self.active['for_read'];self._release();self.isolated=False
        if not was_read:
            self.phase='AWAITING_VERIFY' if self.commit_result=='SUCCESS' and self.pre_open else 'TERMINAL'
        elif self.verification_result=='ABORTED':self.phase='TERMINAL'
        self._reconcile()

    def _abort(self,reason):
        if self.active and self.active['kind']=='exit':return
        if self.active and self.active['kind']=='read':
            self.read_status='ABORTED_READ'
            if self.active['request']['action']=='VERIFY_CTRL':self.verification_result='ABORTED'
            self._begin_exit()
        elif self.fix and self.phase in ('PROPOSED','QUEUED','PREPARING','IMPLEMENTING'):
            self._not_implemented()
        elif self.queued:
            self.queued=None;self.read_status='ABORTED_READ'
        elif self.phase=='VERIFYING':
            self.verification_result='ABORTED';self.phase='TERMINAL'

    def _available(self):return self.c['budget']-self.spent-self.reserved

    def request(self,payload):
        p=deepcopy(payload)
        def response(status):
            self.operations.append(encode(dict(time=self.time,payload=p,status=status)))
            return dict(status=status)
        if type(p) is not dict or not {'action','request_id','problem_id','target'}.issubset(p):return response('INVALID_REQUEST')
        action=p['action'];allowed={'action','request_id','problem_id','target'}
        if action=='FIX_CTRL':allowed|={'mode','evidence_ids'}
        if action=='VERIFY_CTRL':allowed|={'execution_id','target_config_epoch'}
        if action not in (*READS,'FIX_CTRL','VERIFY_CTRL') or not set(p).issubset(allowed) or p['problem_id']!='q-1' or p['target']!=('feeder-B' if action in ('READ_POS','READ_VOLT') else 'ctrl-1'):return response('INVALID_REQUEST')
        if p['request_id'] in self.requests:
            old=self.requests[p['request_id']]
            return response(old['status'] if p==old['payload'] else 'INVALID_REQUEST')
        if not self.pre_open or self.time>=self.c['H']:return response('PRE_CLOSED')
        if self._pending():return response('INVALID_REQUEST')
        if action in self.attempted:return response('INVALID_REQUEST')
        c=self.c
        permission='propose' if action=='FIX_CTRL' else 'verify' if action=='VERIFY_CTRL' else 'read'
        if c['permissions'][permission]!='ALLOW':return response('ACCESS_DENIED')
        if action=='VERIFY_CTRL':
            receipts=[r for r in self.receipts if r['record_kind']=='EXECUTION_RECEIPT' and r['status']=='EXECUTED_UNVERIFIED']
            if not receipts or self.phase!='AWAITING_VERIFY' or p.get('execution_id')!=receipts[-1]['execution_id'] or p.get('target_config_epoch')!=receipts[-1]['target_config_epoch']:return response('INVALID_PARENT')
        if action=='FIX_CTRL':
            if p.get('mode')=='DIRECT':
                if c['permissions']['direct']!='ALLOW':return response('ACCESS_DENIED')
            elif p.get('mode')=='EVIDENCE':
                if decide(self.public_view(),'B1')['action']!='PROPOSE_FIX':return response('INSUFFICIENT_INFORMATION')
            else:return response('INVALID_REQUEST')
            if c['compatible']!='ALLOW':return response('INSUFFICIENT_INFORMATION')
            needed,finish,resource_end=self._public_chain_plan()
            if self._available()<needed:return response('BUDGET_UNAVAILABLE')
            if finish>=c['window'][1] or resource_end>c['window'][1]:return response('WINDOW_UNAVAILABLE')
            self.fix=p;self.phase='PROPOSED';self.attempted.append(action)
            self.requests[p['request_id']]=dict(payload=p,status='ADMITTED')
            self._schedule(self.time+c['approval_work'],4,'approval');self._events_at_now();self._reconcile()
            return response('ADMITTED')
        duration=(c['verify_work'] if action=='VERIFY_CTRL' else c['read_work'])+c['exit_work']
        if self._available()<duration:return response('BUDGET_UNAVAILABLE')
        start=self._slot(duration)
        if start is None:return response('NOT_STARTED_RESOURCE')
        self.attempted.append(action);self.requests[p['request_id']]=dict(payload=p,status='ADMITTED')
        self.queued=dict(kind='read',request=p,reserve=duration)
        self._schedule(start,7,'start',p['request_id']);self._events_at_now();self._reconcile()
        return response('ADMITTED')

    def _pending(self):
        return bool(self.active or self.queued or self.pending_publications or self.pending_receipts or self.phase in ('PROPOSED','QUEUED','PREPARING','IMPLEMENTING','EXITING','VERIFYING'))

    def _known_epoch(self):
        epochs=[r['config_epoch'] for r in self.observations if r['action']=='READ_CONFIG' and r['status']=='KNOWN']
        epochs += [r['target_config_epoch'] for r in self.receipts if r['record_kind']=='EXECUTION_RECEIPT' and r['status']=='EXECUTED_UNVERIFIED']
        return max(epochs) if epochs else None

    def _current(self):
        known=self._known_epoch()
        cutoff=self.c['window'][1] if self.c['tF'] is None else min(self.c['window'][1],self.c['tF'])
        return [r for r in self.observations if r['available_at']<cutoff and r['available_at']<=self.time<r['expires_at'] and (r['config_epoch'] is None or known is None or r['config_epoch']>=known)]

    def public_view(self):
        c=self.c
        failure=any(r.get('decision')=='DENY' or r.get('status')=='NOT_IMPLEMENTED' for r in self.receipts) or any(r['action']=='VERIFY_CTRL' and r['status'] in ('VERIFY_FAILED','INCONCLUSIVE') for r in self.observations)
        execution=any(r.get('status')=='EXECUTED_UNVERIFIED' for r in self.receipts)
        if self.active or self.queued:public_phase=self.phase
        elif self.fix and not execution and not failure:
            public_phase='APPROVED' if any(r.get('decision')=='APPROVE' for r in self.receipts) else 'PROPOSED'
        else:public_phase=self.phase
        # Before an execution receipt, identical safe-exit notifications do not
        # expose whether the private commit succeeded. Arrival supplies that fact.
        if self.active and self.active['kind']=='exit' and self.fix:public_phase='EXITING'
        if failure and not self.active and not self.queued:public_phase='TERMINAL'
        needed,finish,_=self._public_chain_plan()
        return encode(dict(time=self.time,pre_open=self.pre_open,pending=self._pending(),terminal_failure=failure,phase=public_phase,
          records=self._current(),receipts=self.receipts,history=self.observations+self.copies,attempted=self.attempted,known_epoch=self._known_epoch(),certificate=None,
          context=dict(permissions=c['permissions'],compatible=c['compatible'],window=c['window'],available=self._available(),read_reserve=c['read_work']+c['exit_work'],chain_reserve=needed,chain_finish=finish,read_parameters_known=True,chain_parameters_known=True)))

    def copy_record(self,record_id,copy_id):
        found=next((r for r in self.observations if r['record_id']==record_id),None)
        if found is None:return dict(status='INVALID_MATERIAL')
        if not any(r['record_id']==copy_id for r in self.copies):self.copies.append(dict(deepcopy(found),record_id=copy_id,copy_of=record_id,copy_received_at=self.time))
        return dict(status='ACCEPTED')

    def audit(self):
        recoveries=deepcopy(self.recoveries)
        if self.off_since is not None:recoveries.append(dict(off=self.off_since,recovered=None,lower_bound=self.time-self.off_since,right_censored=True))
        account=dict(limit=self.c['budget'],spent=self.spent,reserved=self.reserved,available=self._available())
        return encode(dict(time=self.time,state_identity=id(self._state),family=self._state['family'],epoch=self._state['epoch'],vA=self._state['vA'],
          phase=self.phase,commit_result=self.commit_result,verification_result=self.verification_result,pre_open=self.pre_open,
          g_state=self.g_state,device=self.device,isolated=self.isolated,spent=self.spent,reserved=self.reserved,available=self._available(),budgets=dict(person=account,tool=deepcopy(account)),
          resource_overrun=self.resource_overrun,read_status=self.read_status,started_actions=self.started_actions,observation_count=len(self.observations),
          observation_actions=[r['action'] for r in self.observations],current_actions=[r['action'] for r in self._current()],source_groups=list(dict.fromkeys(r['source_group'] for r in self.observations)),
          E=self.E,L=self.L,U=self.U,load_energy=self.load_energy,ups_energy=self.ups_energy,recoveries=recoveries,trace_status='COMPLETE' if self.time==self.c['H'] else 'INCOMPLETE_TRACE',
          observations=self.observations,receipts=self.receipts,internal_approval=self.internal_grant,segments=self.segments,events=self.events,operations=self.operations,original_input=self.original))
