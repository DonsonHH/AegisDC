"""Use two separately verified, read-only public bundles; never supply the private case to a worker."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import subprocess
from common_v3 import *
import bridge
import isolation as prior_witness


def initialize():
    frozen=read(T4/'freeze.json')
    old=bridge.bundle_files(frozen)
    check(bridge.BUNDLE==OLD_BUNDLE and bridge.check_bundle(frozen)==read(T4/'isolation-witness.json')['bundle'],'original V*')
    pins=read(PK/'freeze.json')['files']
    extra={k.removeprefix('src/'):v for k,v in pins.items() if k.startswith('src/aegis_action_cost/')}
    check(set(read(SRC/'rules.json'))=={'schema','window_s','exclusive_recovery_s','exposure_menu_s',
          'counts_per_twelve','bypass_capacity','public_order_prefix','lambda','fee_person_seconds','versions','main','engineering_caps','development_caps'},
          'only predeclared public design constants, no realized factors or seed')
    BUNDLE.mkdir()
    for k,h in {**old,**extra}.items():
        target=BUNDLE/k;target.parent.mkdir(exist_ok=True)
        source=OLD_BUNDLE/k if k in old else SRC/Path(k).name
        check(sha(source)==h,k)
        target.write_bytes(source.read_bytes())
    bundle=hash_obj({**old,**extra})
    write(ACT/'bundles.json',dict(old=hash_obj(old),new=bundle,files={**old,**extra},original=old))
    return bundle


class Child(bridge.PublicProcess):
    def __init__(self,role,stderr):
        old=role in ('VSTAR','PA','B')
        name='V3' if role=='VSTAR' else role
        root=OLD_BUNDLE if old else BUNDLE
        entry=root/('aegis_risk_dispatch/worker.py' if old else 'aegis_action_cost/worker.py')
        self.role=role;self.wire=name
        self.stderr=Path(stderr).open('x')
        self.child=subprocess.Popen([sys.executable,'-I','-S','-B',str(entry),name],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,cwd=root,
            env={'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1'})
        self.static=None;self.events=[]

    def start(self,pub):
        check(self.message({'public':pub})=={'ready':True,'role':self.wire},'public handshake')
        self.static=hash_obj(pub)

    def choose(self,pub,view,role,plan):
        check(role==self.role and not plan and hash_obj(pub)==self.static,'clean public ingress')
        answer=self.message({'view':view})
        self.events.append([view['time'],hash_obj(view),hash_obj(answer)])
        return answer


def main():
    pinned();sealed_manifest('eng');sealed_manifest('dev');folder=ACT/'isolation';folder.mkdir();bundle=initialize()
    a,b=(prior_witness.history(k) for k in ('5-04','5-10'))
    check(a[:2]==b[:2] and a[2]!=b[2],'two actual private worlds with identical public history')
    from copy import deepcopy
    def test(role):
        children=[Child(role,folder/(role+suffix+'.stderr')) for suffix in ('-left','-right')]
        try:
            for c,item in zip(children,(a,b)):c.start(item[0])
            frames=[]
            for av,bv in zip(a[1],b[1],strict=True):
                outs=[]
                for c,v in zip(children,(av,bv)):
                    view=deepcopy(v)
                    for r in view['records']:
                        if r['kind']=='order':r['value']='OPEN/MAINT-600'
                    outs.append(c.choose(a[0],view,role,{}))
                check(outs[0]==outs[1],role+' private divergence')
                if role.endswith('NOPROBE'):check(not outs[0]['request'] or outs[0]['request']['phase']!='I','ablation')
                frames.append(hash_obj(outs[0]))
            return frames
        finally:
            for c in children:c.close()
    roles=('VSTAR','VSTAR_NOPROBE','V_COST','V_COST_NOPROBE')
    results={r:test(r) for r in roles}
    checks={}
    for k in ('early','private'):
        proc=Child('V_COST',folder/(k+'.stderr'));proc.start(a[0]);v=deepcopy(a[1][0])
        if k=='early':v['records'][0]['arrived']=v['time']+60
        else:v['cause']='PRIVATE'
        try:proc.message({'view':v})
        except RuntimeError:checks[k]=True
        finally:proc.close(failed=True)
    check(all(len(results[r])==61 for r in roles) and checks=={'early':True,'private':True},'public witness')
    write(folder/'result.json',dict(job=job(),bundle=bundle,worlds=[a[2],b[2]],old_originals=[a[3],b[3]],decisions=results,
        public_guards=checks,unchanged_old_bundle=read(ACT/'bundles.json')['old'],native_runs=0))

if __name__=='__main__':main()
