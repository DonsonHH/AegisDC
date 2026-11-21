"""Synthetic downstream service branch attached during the native V6 loop. No site control software."""
from copy import deepcopy
from math import inf


class London:
    def __init__(self,cfg):
        self.cfg=deepcopy(cfg);self.now=0;self.closed=cfg['b_connected'];self.version=cfg['logic']
        self.pre=False;self.started=None;self.battery=float(cfg['ups_J']);self.spent=0.
        self.device='RUNNING';self.boot=None;self.events=[];self.last=None
        self.advance(0)

    def advance(self,t):
        self.now=t;c=self.cfg
        self.fault=c['fault_at'] is not None and c['fault_at']<=t<c['restore_at']
        self.a=not self.fault
        self.b=bool(c['b_voltage'] and self.closed)
        signal=c['b_voltage'] if self.version=='SHARED_UPSTREAM' else self.b
        command=not(self.a or signal)
        self.commands=(command,command)
        self.request=bool(self.pre or any(self.commands))
        self.permission=self.request and c['permit']
        if self.permission and self.started is None:self.started=t
        if not self.permission:self.started=None
        self.ready=bool(c['hardware_ready'] and self.started is not None and t>=self.started+c['gen_delay'])
        self.takeover=bool(not(self.a or self.b) and self.permission and self.ready and c['transfer_ok'])
        self.source='A' if self.a else 'B' if self.b else 'G' if self.takeover else 'UPS' if self.battery>0 else 'NONE'
        if self.source=='NONE':self.device='OFF';self.boot=None
        elif self.device=='OFF':self.device='BOOT';self.boot=t+c['boot_s']
        if self.device=='BOOT' and t>=self.boot:self.device='RUNNING';self.boot=None
        self.cap=int(self.device=='RUNNING')
        sig=(self.a,self.b,self.version,self.commands,self.request,self.permission,self.ready,self.takeover,self.source,self.device)
        if sig!=self.last:
            self.events.append(dict(t=t,A=self.a,B=self.b,upstream_B=c['b_voltage'],contact_B=self.closed,
                versions=[self.version,self.version],shared_source='shared-voltage-context',commands=list(self.commands),
                request=self.request,permission=self.permission,ready=self.ready,actual_takeover=self.takeover,
                source=self.source,device=self.device,capacity=self.cap,UPS_J=self.battery))
            self.last=sig

    def next(self,t):
        c=self.cfg;ts=[c['fault_at'],c['restore_at'],self.boot]
        if self.started is not None:ts.append(self.started+c['gen_delay'])
        if self.source=='UPS':ts.append(t+self.battery/c['group_W'])
        return min((v for v in ts if v is not None and v>t),default=inf)

    def integrate(self,a,b):
        if self.source=='UPS':
            amount=(b-a)*self.cfg['group_W']
            if amount>self.battery+1e-7:raise ValueError('Unsplit UPS depletion')
            self.battery-=amount;self.spent+=amount

    def apply(self,op,t):
        if op=='revise_shared':self.version='SHARED_CONTACT'
        elif op=='restore_path' and self.cfg['released'] and self.cfg['b_voltage']:self.closed=True
        elif op=='prestart':self.pre=True
        else:return False
        self.advance(t);return True

    def measure(self,key):
        if key=='LC':return dict(versions=[self.version,self.version],source_group='shared-voltage-context')
        if key=='LB':return dict(contact=int(self.closed),upstream=int(self.cfg['b_voltage']),released=self.cfg['released'])
        if key=='LG':return dict(request=self.request,permitted=self.cfg['permit'],ready=self.ready,actual_takeover=self.takeover)
        raise ValueError(key)

    def account(self):
        return dict(initial_J=self.cfg['ups_J'],final_J=self.battery,delivered_by_UPS_J=self.spent,
            residual_J=self.cfg['ups_J']-self.spent-self.battery)


class Netherlands:
    def __init__(self,cfg):
        self.cfg=deepcopy(cfg);self.now=0;self.transient=False;self.returned=False
        self.relocated=False;self.tripped=False;self.controller=True;self.pump=True;self.latched=False
        self.commissioned=not cfg['construction'];self.cool_trip=False;self.reset=None
        self.store=1000.*cfg['thermal_hold_s'];self.spent=0.;self.events=[];self.last=None;self.advance(0)

    def advance(self,t):
        self.now=t;c=self.cfg;tf=c['fault_at']
        self.load=c['critical_kW']+(0 if self.relocated else c['other_kW'])
        if tf is not None and t>=tf and not self.transient:
            self.transient=True;self.tripped=self.load>c['transfer_kW']
            self.controller=False;self.pump=False;self.latched=True
        if self.transient and t>=c['restore_at'] and not self.returned:
            self.returned=True;self.controller=True;self.tripped=False
            if c['auto_restart']:self.pump=True;self.latched=False
        self.cooling=self.pump or self.commissioned
        if not self.cooling and self.store<=0:self.cool_trip=True;self.reset=None
        if self.cooling and self.cool_trip:
            if self.reset is None:self.reset=t+c['cool_reset_s']
            if t>=self.reset:self.cool_trip=False;self.reset=None
        self.cap=int(not self.tripped and not self.cool_trip)
        sig=(self.transient,self.returned,self.tripped,self.controller,self.pump,self.latched,self.commissioned,
             self.relocated,self.cool_trip,self.cap)
        if sig!=self.last:
            self.events.append(dict(t=t,transient=self.transient,returned=self.returned,group_demand_kW=self.load,
                transfer_limit_kW=c['transfer_kW'],alternative_group_kW=c['other_kW'] if self.relocated else 0,
                critical_kW=c['critical_kW'],tripped=self.tripped,controller_on=self.controller,
                pump_running=self.pump,pump_latched=self.latched,backup_commissioned=self.commissioned,
                cooling_exhausted=self.cool_trip,capacity=self.cap,thermal_buffer_J=self.store))
            self.last=sig

    def next(self,t):
        c=self.cfg;ts=[c['fault_at'],c['restore_at'],self.reset]
        if not self.cooling and self.store>0:ts.append(t+self.store/1000)
        return min((v for v in ts if v is not None and v>t),default=inf)

    def integrate(self,a,b):
        if not self.cooling and self.store>0:
            amount=(b-a)*1000
            if amount>self.store+1e-7:raise ValueError('Unsplit heat buffer depletion')
            self.store-=amount;self.spent+=amount

    def apply(self,op,t):
        c=self.cfg
        if op=='relieve_group' and c['spare_kW']>=c['other_kW']:self.relocated=True
        elif op=='restart_pump' and self.controller and self.latched and c['restart_capable']:
            self.latched=False;self.pump=True
        elif op=='commission_backup' and c['handover']:self.commissioned=True
        else:return False
        self.advance(t);return True

    def measure(self,key):
        c=self.cfg
        if key=='NR':return dict(group_kW=self.load,transfer_kW=c['transfer_kW'],alternate_kW=c['spare_kW'])
        if key=='NP':return dict(running=self.pump,latched=self.latched,controller_on=self.controller,
                                 automatic_restart=c['auto_restart'],power_returned=self.returned)
        if key=='NC':return dict(under_construction=c['construction'] and not self.commissioned,
                                 handover=c['handover'],commissioned=self.commissioned)
        raise ValueError(key)

    def account(self):
        initial=1000.*self.cfg['thermal_hold_s']
        return dict(initial_J=initial,final_J=self.store,uncooled_load_J=self.spent,residual_J=initial-self.spent-self.store)


def coupled_class(base,terminal):
    """Limit actual common service before its native mass/energy/service interval is integrated."""
    class Coupled(base):
        def discrete(self,t):
            super().discrete(t);terminal.advance(t)
        def point(self):
            p=super().point();svc=p['service']
            svc['capacities']['protected_group']=terminal.cap
            svc['delivered']=min(svc['delivered'],terminal.cap)
            svc['unserved']=svc['demand']-svc['delivered']
            return p
        def next_physical_event(self,t,point):
            return min(super().next_physical_event(t,point),terminal.next(t))
        def integrate(self,start,end,point):
            out=super().integrate(start,end,point);terminal.integrate(start,end);return out
    return Coupled
