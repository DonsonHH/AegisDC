"""Index explicitly public inputs for future custodian dedup; no candidate search.

Raw unit identities retain invalid/legacy/interface inputs as well as complete
H20 configs. Exact config hashes are not semantic novelty or qualification.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket

from london_confirmation_entry import FIELDS, EntryError, config_hash

PREFIX='docs/mainline/review-gated/'
SOURCES=[
    PREFIX+'R2/execution/cases-v2.json',
    PREFIX+'R2/extensions/e1-e4-v2/cases.json',
    PREFIX+'R2/extensions/e1-e4-v2/regressions.json',
    PREFIX+'R2/extensions/read-verify-admission-v1/cases.json',
    PREFIX+'R2/extensions/read-verify-admission-v1/guards.json',
    PREFIX+'R3/runner-v1/engineering-cases.json',
    PREFIX+'R3/runner-v1/guards.json',
    PREFIX+'R3/formal-protocol-v1/development-inputs.json',
    PREFIX+'R4/confirmation-entry-v1/inputs.json',
    PREFIX+'R4/confirmation-entry-v1/interface-fixtures.json',
    PREFIX+'R4/confirmation-entry-v1/interface-addendum.json',
]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def index(root):
    sources=[];units=[];configs={}
    def config_visit(value,origin,pointer=''):
        if isinstance(value,dict):
            if set(value)==FIELDS:
                try:key=config_hash(value);state='CANONICAL_H20_CONFIG'
                except EntryError:key=digest(value);state='RAW_CONFIG_OUTSIDE_ENTRY_SHAPE'
                row=configs.setdefault(state+':'+key,dict(kind=state,sha256=key,origins=[]))
                row['origins'].append(dict(source=origin,pointer=pointer))
                return
            for key,child in value.items():config_visit(child,origin,pointer+'/'+key)
        elif isinstance(value,list):
            for i,child in enumerate(value):config_visit(child,origin,pointer+'/'+str(i))
    for name in SOURCES:
        raw=(root/name).read_bytes();data=json.loads(raw)
        rows=data.get('units',data.get('cases',data.get('conditions',[data])))
        sources.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),units=len(rows)))
        for row in rows:
            identifier=row.get('id',row.get('condition_id','SINGLE'))
            value=row.get('input',row.get('common',row))
            units.append(dict(source=name,id=identifier,input_sha256=digest(value),classification='PUBLIC_DISCLOSED_DO_NOT_SELECT_FOR_CONFIRMATION'))
            config_visit(value,name+'#'+identifier)
        # Fully disclosed normalization/type mutations also belong to the corpus,
        # even if they were only interface tests and never facility executions.
        if name.endswith('interface-fixtures.json'):
            base=json.loads((root/PREFIX/'R4/confirmation-entry-v1/inputs.json').read_text())['conditions'][0]['common']
            for row in rows:
                if row['operation'] in ('normalize_equal','invalid_config'):
                    modified=deepcopy(base);modified.update(row['change'])
                    config_visit(modified,name+'#'+row['id']+'/resolved-public-config')
    return dict(schema='aegisdc-public-dedup-baseline-v1',purpose='PUBLIC_CUSTODY_HANDOFF_NOT_SELECTION',
        sources=sources,units=units,config_identities=list(configs.values()),
        counts=dict(source_files=len(sources),public_units=len(units),canonical_configs=sum(x['kind']=='CANONICAL_H20_CONFIG' for x in configs.values()),raw_other_configs=sum(x['kind']!='CANONICAL_H20_CONFIG' for x in configs.values())),
        scope='All retained London PRE frozen JSON unit packs, disclosed development inputs, new engineering inputs and resolved public interface mutations. Other legacy facility schemas cannot be exact H20 confirmation inputs; semantic comparisons remain C/V duty.',
        qualification_or_selection_implied=False,confirmation_candidates_generated=0,model_calls=0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or socket.gethostname().split('.')[0]=='mu01':raise SystemExit('Remote allocation required')
    value=index(Path(__file__).resolve().parents[1])
    with a.output.open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps(value['counts']))


if __name__=='__main__':main()
