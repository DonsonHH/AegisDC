"""Private exact-epoch live sampling through the accepted finite sensor law."""
from copy import deepcopy
from fractions import Fraction
import math
from .sensor_channels import validate_channel_profile,sample_trace,_number,_private_inputs
from .evidence_ledger import EvidenceLedger,_fields,_require

class LiveSensorSession:
    def __init__(self,program,duration_s):
        _fields(program,{'profile','realization'},'Live sensor program')
        self.profile=validate_channel_profile(program['profile']);self.realization=deepcopy(program['realization'])
        carrier=dict(schema='aegisdc-observation-private-trace-v1',facility_id=self.profile['ledger']['facility_id'],
            entity_ids=self.profile['ledger']['entity_ids'],points=[dict(time_s=0,domains={})])
        _private_inputs(self.profile,carrier,self.realization)
        self.ledger=EvidenceLedger(self.profile['ledger']);self.audit=[];self.index=0;epochs=set();self.polls={}
        for measurement in self.profile['measurements']:
            if not measurement['enabled']:continue
            phase,period=Fraction(measurement['phase_s']),Fraction(measurement['period_s'])
            # Include the adjacent rational counter, then gate on its actual
            # binary64 coordinate. A rational time just beyond the horizon can
            # round to that horizon and must match a longer run's same prefix.
            count=max(0,int((Fraction(duration_s)-phase)//period)+1)+1
            previous=None
            for index in range(count):
                instant=_number(phase+index*period)
                if instant>duration_s:break
                _require(index<10000,'Live finite sensor schedule exceeds10000 polls per instrument')
                _require(previous is None or instant>previous,'Live sensor polling coordinates collapse')
                previous=instant;epochs.add(instant)
                self.polls.setdefault(instant,{}).setdefault(measurement['id'],[]).append(index)
        self.epochs=sorted(epochs)

    def process(self,time_s,snapshot):
        if self.index>=len(self.epochs) or time_s<self.epochs[self.index]:return
        _require(time_s==self.epochs[self.index] and snapshot['time_s']==time_s,'Live sensors sample their actual current epoch only')
        # A one-point carrier contains no past/future physical trajectory. The
        # existing adapter skips polls before this point and produces only the
        # currently due channels with their original counter, origin and error law.
        trace=dict(schema='aegisdc-observation-private-trace-v1',facility_id=self.profile['ledger']['facility_id'],
            entity_ids=self.profile['ledger']['entity_ids'],points=[snapshot])
        polls={m['id']:self.polls[time_s].get(m['id'],[]) for m in self.profile['measurements']}
        result=sample_trace(self.profile,trace,self.realization,poll_indices=polls)
        for record in result['ledger']['records']:self.ledger.ingest(record)
        self.audit.extend(result['private_audit']);self.index+=1

    def next_event(self):
        return self.epochs[self.index] if self.index<len(self.epochs) else math.inf
