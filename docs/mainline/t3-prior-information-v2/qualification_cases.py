"""Independent literals for engineering. Cases are never selected from development results."""
from common import BIZ
from generator_v2 import FAMILIES,SEED,complete,incident_case,qualification,msg


def engineering_a(src):
    cases={}
    for family in FAMILIES:
        for kind in ('NA','PV'):
            case,meta=qualification(family,kind,src);s=meta['target'];start=155 if s=='C/c0' else 35
            read=s+'::'+('I' if kind=='NA' else 'R')
            expects=dict(subject=s,states=[kind]*4,required_sample=read,renewal=s+'::X',first_action_end=start if kind=='PV' else None,
                primary_sample_end=start if kind=='NA' else (215 if start==155 else 95),
                primary_sample_arrival=(start if kind=='NA' else 215 if start==155 else 95)+15,
                renewal_sample_end=1715,renewal_arrival=1730,paid_ttl=2100,earliest_legal_first=(360 if kind=='NA' else 660))
            if family=='RESERVE_TRANSFER':expects['physical_witness']=['1020','ups','supplying']
            if family=='COOLING_ACCESS':expects['physical_witness']=['90','cooling','active' if kind=='NA' else 'maintenance']
            cases[family+'-'+kind]=(case,meta['plan'],expects)
    case,meta=qualification('NETWORK_POWER','EXPIRE',src)
    cases['NETWORK_POWER-EXPIRY']=(case,meta['plan'],dict(subject='N/n0',states=['NA','NA','OPEN_EXPIRED','OPEN_EXPIRED'],
        required_sample='N/n0::I',renewal=None,primary_sample_end=35,primary_sample_arrival=50,expiry=2135,earliest_legal_first=360))
    return cases


def engineering_c(src):
    out={}
    def build(name,family,cfg,plan,expected):
        case=incident_case(SEED,0,family,'TWIN_A')
        if family=='LONDON':
            case['incident'].update(fault_at=1500,restore_at=2100)
        else:
            case['incident'].update(fault_at=1500,restore_at=1620,transfer_kW=70,construction=True,auto_restart=False)
        case['incident'].update(cfg)
        if family=='NETHERLANDS':
            case['stream']=[r for r in case['stream'] if r['kind']!='release']
            case['stream'].append(msg('release','NC','works-office',60,90,3240,'HANDOVER_RELEASED' if case['incident']['handover'] else 'WORK_OPEN'))
        out[name]=(complete(case,src,SEED),plan,expected)
    # expected physical states are right-sided at the quoted event epoch, not inferred from returned scores.
    build('L-base','LONDON',{}, {},dict(L=540,first=1680,submitted=[],at={'1500':{'A':False,'B':False,'request':False,'source':'UPS'},
          '1680':{'source':'NONE','device':'OFF'},'2100':{'source':'A','device':'BOOT'},'2220':{'device':'RUNNING'}}))
    build('L-read-fix','LONDON',{}, {0:'LC::I',60:'LB::I',120:'LC::A'},dict(L=0,first=None,
          writes={'LC::A':'APPLIED'},reads={'LC::I':{'versions':['SHARED_UPSTREAM','SHARED_UPSTREAM']},'LB::I':{'contact':0,'upstream':1}},
          at={'1500':{'request':True,'permission':True,'ready':False,'actual_takeover':False},'1560':{'source':'G','actual_takeover':True}}))
    build('L-prestart','LONDON',{}, {120:'LG::A'},dict(L=0,first=None,writes={'LG::A':'APPLIED'},at={'155':{'request':True,'ready':False},
          '215':{'ready':True,'actual_takeover':False},'1500':{'actual_takeover':True,'source':'G'}}))
    build('L-path','LONDON',{'released':True,'hardware_ready':False},{120:'LB::A'},dict(L=0,first=None,
          writes={'LB::A':'APPLIED'},at={'155':{'contact_B':True},'1500':{'source':'B','actual_takeover':False}}))
    build('L-refused','LONDON',{'permit':False},{120:'LB::A',300:'LC::A'},dict(L=540,first=1680,
          writes={'LB::A':'NO_EFFECT','LC::A':'APPLIED'},at={'1500':{'request':True,'permission':False,'ready':False,'actual_takeover':False}}))
    build('L-connection','LONDON',{'transfer_ok':False},{120:'LC::A'},dict(L=540,first=1680,
          writes={'LC::A':'APPLIED'},at={'1560':{'permission':True,'ready':True,'actual_takeover':False,'source':'UPS'}}))
    build('L-hardware','LONDON',{'hardware_ready':False},{120:'LC::A'},dict(L=540,first=1680,
          writes={'LC::A':'APPLIED'},at={'1560':{'request':True,'permission':True,'ready':False,'actual_takeover':False}}))
    build('N-base','NETHERLANDS',{}, {},dict(L=1920,first=1500,submitted=[],at={'1500':{'group_demand_kW':100,'tripped':True,'controller_on':False},
           '1620':{'controller_on':True,'pump_running':False,'pump_latched':True},'1800':{'capacity':0,'cooling_exhausted':True}}))
    build('N-group','NETHERLANDS',{}, {120:'NR::A'},dict(L=1800,first=1800,
          writes={'NR::A':'APPLIED'},at={'1500':{'group_demand_kW':60,'alternative_group_kW':40,'tripped':False}}))
    build('N-restart','NETHERLANDS',{}, {120:'NP::A',1680:'NP::A'},dict(L=120,first=1500,
          refused=[[120,'NP','A','NO_RETURN_RECEIPT']],writes={'NP::A':'APPLIED'},at={'1715':{'pump_running':True,'pump_latched':False}}))
    build('N-both','NETHERLANDS',{}, {120:'NR::A',1680:'NP::A'},dict(L=0,first=None,writes={'NR::A':'APPLIED','NP::A':'APPLIED'},
          at={'1500':{'tripped':False},'1715':{'pump_running':True}}))
    build('N-handover','NETHERLANDS',{'transfer_kW':120,'handover':True,'restart_capable':False},{840:'NC::A'},
          dict(L=0,first=None,writes={'NC::A':'APPLIED'},at={'1000':{'backup_commissioned':True},'1620':{'pump_latched':True,'capacity':1}}))
    build('N-late','NETHERLANDS',{}, {840:'NC::A',1920:'NP::A'},dict(L=335,first=1500,refused=[[840,'NC','A','NO_HANDOVER_RELEASE']],
          writes={'NP::A':'APPLIED'},at={'1955':{'pump_running':True,'cooling_exhausted':True},'2015':{'capacity':1}}))
    build('N-insufficient','NETHERLANDS',{'transfer_kW':45,'auto_restart':True},{120:'NR::A'},dict(L=120,first=1500,
          writes={'NR::A':'APPLIED'},at={'1500':{'group_demand_kW':60,'tripped':True},'1620':{'tripped':False,'pump_running':True}}))
    return out
