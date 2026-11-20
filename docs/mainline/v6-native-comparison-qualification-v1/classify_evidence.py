"""Classify the existing durable file inventories without re-running or rewriting their attempts."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def role(path,ids):
    parts=path.split('/')
    if parts[0]=='native':
        kind='facility'
        rest=parts[1:]
        if len(rest)>1 and rest[0] not in ids['facilities']:return None
    elif parts[0].startswith('public-') and parts[0][7:] in ids['public']:
        return {'arguments.json':'public input','begin.json':'pre-call','return.json':'public output'}.get('/'.join(parts[1:]))
    elif parts[0].startswith('substitute-') and parts[0][11:] in ids['fixtures']:
        if len(parts)==2:
            return {'begin.json':'pre-call','return.json':'substitute output'}.get(parts[1])
        if parts[:2]!=['substitute-Z4','injected-batch']:return None
        kind='injected';rest=parts[2:]
        if len(rest)>1 and rest[0] not in ('FIXTURE-V','FIXTURE-D'):return None
    else:return None
    if len(rest)==1:
        return {'ledger.json':'process ledger','events.jsonl':'process operations',
                'saved-evaluation.json':'saved full denominator' if kind=='facility' else None}.get(rest[0])
    relative='/'.join(rest[1:])
    common={'call.json':'process invocation','stdout':'process stdout','stderr':'process stderr'}
    if kind=='injected':
        return 'controlled return' if relative=='response.json' and rest[0]=='FIXTURE-V' else common.get(relative)
    files={'model.json':'actual scenario input','dispatch-program.json':'actual dispatch input','business-program.json':'actual evaluator input',
           'inputs.json':'actual exogenous inputs','engineering-assertions.json':'independent assertions','evaluated.json':'completed evaluation identity',
           'score.json':'saved finite arm score','run/balances.jsonl':'raw native balances','run/private-state.jsonl':'raw native physical state',
           'run/run.json':'raw native return','run/scenario.json':'native scenario copy'}
    return {**common,**files}.get(relative)


def main(root):
    result=json.loads((HERE/'result.json').read_bytes())
    fixture=json.loads((HERE/'fixtures.json').read_bytes())
    ids={c:{r.get('unit',r.get('id')) for r in fixture[c]} for c in ('public','facilities','fixtures')}
    classified={}
    for attempt in result['attempts']:
        folder=root/attempt['attempt']/'collected'
        file=folder/'output/durable-files.json'
        raw=file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=attempt['durable_manifest_sha256']:raise ValueError('Original durable inventory differs')
        original=json.loads(raw)
        roles={p:role(p,ids) for p in original}
        if not all(roles.values()):raise ValueError('Unclassified files: '+str([k for k,v in roles.items() if not v]))
        classified[attempt['attempt']]=dict(original_sha256=attempt['durable_manifest_sha256'],entries=len(roles),roles=roles,
            runtime_cache_files=[],unfinished_temporary_checkpoints=[],unclassified=[])
    audit=[]
    initial=result['checks']
    for name,file in [('C11-K','C11-K-root-return.json'),('K-c11-low','K-c11-low-return.json')]:
        raw=(root/'initial01'/file).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=initial['public/'+name]['output_sha256']:
            raise ValueError('Public decision identity differs')
        choice=json.loads(raw);inner=choice['intake_decisions'][0]
        audit.append(dict(unit=name,return_sha256=hashlib.sha256(raw).hexdigest(),state=inner['state'],actual_action=choice['chosen_candidate_id'],
            logged_model_evaluations=choice['model_evaluations'],logged_forecast_branch_count=choice['forecast_branch_count'],
            logged_tables_evaluated=inner['tables_evaluated'],logical_version_counter_only=True))
    doc=dict(schema='aegisdc-native-qualification-evidence-scope-v1',
        classification='Post-execution inspection of the original inventories. Each entry retains its original hash. No runtime caches, ledger.next or undeclared files were in the three observed inventories; future unrelated files have no automatic evidence role.',
        original_inventories=classified,ancillary='Source and launch archives, scheduler stdout/stderr and submission/terminal receipts are separately bound per attempt in result.json.',
        counter_boundary=dict(public_return_examples=audit,semantic='K uses fixed report support and admission; the stored action_value/forecast_branch_count labels measure logical variant slots, not measured calls to score alternatives or comparable computational cost. The measured top-level public calls, decisions and process ledgers are separate.'),
        evaluation_limits={'numeric_unresolved':'Executed with balance difference 0, rate difference 2^-52 and different-history flag at the sign classifier. No end-to-end ambiguous pair of native physical trajectories was executed.',
          'truncated_window':'service() has an explicit contiguous H10 guard. The stored failure witness tests missing process return and unexecuted suffix; a nonempty raw service trajectory ending before H10 was not presented to that guard during these jobs.',
          'future_research_gate':'The common native runner and C01 five-arm path were exercised under the engineering gate. Switching to a research-purpose manifest remains subject to separate authorization and identity checks.'},
        extra_scientific_calls=0,classification_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (HERE/'evidence-scope.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(doc,stream,indent=2,ensure_ascii=False);stream.write('\n')
    print({name:r['entries'] for name,r in classified.items()})

if __name__=='__main__':main(Path(sys.argv[1]))
