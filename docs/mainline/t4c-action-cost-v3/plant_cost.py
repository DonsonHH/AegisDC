"""Physical service envelope while an unnecessary accepted intervention is in maintenance."""
from math import inf


def indicated(kind,params,terminal):
    if kind=='C':return params['filter_resistance_multiplier']>1
    if kind=='N':return params['network_service_capacity']<1
    if kind=='LC':return terminal.version!='SHARED_CONTACT'
    if kind=='LB':return not terminal.closed and terminal.cfg['released'] and terminal.cfg['b_voltage']
    if kind=='LG':return not terminal.b and terminal.cfg['permit'] and terminal.cfg['hardware_ready'] and terminal.cfg['transfer_ok'] and not terminal.pre
    if kind=='NR':return terminal.load>terminal.cfg['transfer_kW']
    if kind=='NP':return terminal.latched and terminal.controller and not terminal.pump
    if kind=='NC':return not terminal.commissioned and terminal.cfg['handover']
    raise ValueError(kind)


class Maintenance:
    def __init__(self, exposure_s, cap):
        self.duration=exposure_s
        self.cap=cap
        self.now=0
        self.until=0
        self.entries=[]

    def accepted(self, task, now, need):
        end=now if need else now+self.duration
        self.entries.append(dict(task=task,at=now,indicated=bool(need),until=end))
        self.until=max(self.until,end)

    def attach(self, base):
        owner=self
        class Serviced(base):
            def discrete(self,t):
                owner.now=t
                return super().discrete(t)

            def point(self):
                p=super().point()
                service=p['service']
                limit=owner.cap if owner.now<owner.until else 1
                service['capacities']['maintenance_support']=limit
                service['delivered']=min(service['delivered'],limit)
                service['unserved']=service['demand']-service['delivered']
                return p

            def next_physical_event(self,t,point):
                change=owner.until if t<owner.until else inf
                return min(super().next_physical_event(t,point),change)
        return Serviced
