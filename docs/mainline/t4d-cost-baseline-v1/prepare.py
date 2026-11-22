"""Materialize only registered derivatives of the disclosed v3 development inputs and public configurations."""
from copy import deepcopy
from workpackage import *


def make_case(old,setting):
    out=deepcopy(old)
    limits=out['maintenance']
    limits.update(capacity=setting['capacity'],recovery=setting['recovery'])
    if setting['zero_duration']:
        limits['exposure_s']=0
        for row in out['native']['dispatch_program']['channel']:
            if row['kind']=='order':
                must(row['value'].startswith('OPEN/MAINT-'),'parent order must declare the public tier')
                row['value']='OPEN/MAINT-0'
    return out


def build_bundle(payload):
    members={k:hashlib.sha256(v).hexdigest() for k,v in payload.items()}
    identity=digest(members);folder=ACT/'bundles'/identity
    if not folder.exists():
        folder.mkdir()
        for name,raw in payload.items():
            f=folder/name;f.parent.mkdir(exist_ok=True)
            with f.open('xb') as fp:fp.write(raw)
    verify_bundle(folder,members)
    return identity,members


def main():
    verify_source();cfg=spec();inputs=ACT/'inputs';inputs.mkdir()
    (ACT/'bundles').mkdir()
    prior_receipt=read(C/'receipt.json')
    must(filehash(PREV/'bundles.json')==prior_receipt['remote_retrieval']['bundles.json'],'upstream public package')
    old=read(PREV/'bundles.json');vf=read(C/'v-double-star-freeze.json')
    must(old['files']==vf['public_bundle_files'] and old['new']==vf['public_bundle_sha256'] and old['old']==vf['comparator_B_original_bundle_sha256'],'frozen roles')
    verify_bundle(V_OLD,old['files']);verify_bundle(B_OLD,old['original'])
    inputs_by_mode={};role_roots={};members={old['old']:old['original']}
    base_v={k:(V_OLD/k).read_bytes() for k in old['files']}
    migrated={k:(B_OLD/k).read_bytes() for k in old['original']}
    for k in ('aegis_action_cost/__init__.py','aegis_action_cost/permit.py'):migrated[k]=base_v[k]
    for n in ('__init__.py','rule.py','worker.py'):
        k='aegis_cost_baseline/'+n;migrated[k]=(ROOT/'src'/k).read_bytes()
    registrations=read(C/'dev-manifest.json')
    must(cfg['order']==registrations['order'] and cfg['public_inputs']==registrations['files'],'assert exact parent public panel')
    for mode,setting in cfg['settings'].items():
        keys=cfg['order'] if mode=='BASE' else cfg['sensitivity_keys']
        path=inputs/mode;path.mkdir();items={}
        for key in keys:
            src=PREV/'dev-inputs'/(key+'.json');original=cfg['public_inputs'][key]
            must(filehash(src)==original,'source condition '+key)
            old_case=read(src);case=make_case(old_case,setting);f=path/(key+'.json');save(f,case)
            child_hash=filehash(f)
            must(mode!='BASE' or child_hash==original,'unchanged 72 inputs')
            items[key]=dict(sha256=child_hash,prior_sha256=original,public_config=digest(case['native']['dispatch_program']['public']),
                channel=digest(case['native']['dispatch_program']['channel']),duration=case['maintenance']['exposure_s'])
        inputs_by_mode[mode]=items
        v=dict(base_v);k='aegis_action_cost/rules.json'
        if mode!='BASE':
            public=json.loads(v[k]);public.update(exclusive_recovery_s=setting['recovery'],bypass_capacity=setting['capacity'])
            v[k]=stable(public)+b'\n'
        vi,vm=build_bundle(v)
        must(all(vm[f]==old['files'][f] for f in vm if f!=k),'V** source changed')
        if mode=='BASE':must(vi==old['new'],'original V** package')
        bc=dict(migrated);bc['cost-permit.json']=stable(dict(exclusive_recovery_s=setting['recovery']))+b'\n'
        bi,bm=build_bundle(bc);members[vi]=vm;members[bi]=bm
        role_roots[mode]={'V_COST':vi,'V_COST_NOPROBE':vi,'B':old['old'],'B_COST':bi}
    save(inputs/'manifest.json',dict(schema='T4d-exact-public-conditions-and-worker-bundles',source=os.environ['T4D_SOURCE'],
        condition_list=filehash(PK/'settings-and-conditions.json'),items=inputs_by_mode,role_bundles=role_roots,bundle_members=members,
        author_job=job(),public_parent=filehash(C/'dev-manifest.json'),holdout_generated=0))
    print('conditions',[(k,len(v)) for k,v in inputs_by_mode.items()],'input manifest',filehash(inputs/'manifest.json'),flush=True)

if __name__=='__main__':main()
