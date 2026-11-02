"""Budgeted same-interface search; a finite headroom gate before model calls."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from .contracts import digest
from .response_rule import ResponseRule
from .risk_response import run_response


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def paired_outcomes(candidate, baseline):
    if candidate['process_sha256'] != baseline['process_sha256']:
        raise ValueError('Candidate and baseline do not share a physical process')
    keys = lambda r: {(i['task_id'],i['onset_s'],i['end_s']) for i in r['anomaly_intervals']}
    if keys(candidate) != keys(baseline):
        raise ValueError('Candidate and baseline have different evaluation intervals')
    confirmed = lambda r: {(i['task_id'],i['onset_s'],i['end_s']) for i in r['anomaly_intervals'] if i['detected']}
    c,b = confirmed(candidate),confirmed(baseline)
    cm,bm = candidate['metrics'],baseline['metrics']
    return {'gained':len(c-b),'lost':len(b-c),'net':len(c)-len(b),
        'gained_intervals':sorted(c-b),'lost_intervals':sorted(b-c),
        'travel_delta_pct':100*(cm['travel_m']/bm['travel_m']-1),
        'completion_loss_pct':100*(1-cm['completed_inspections']/bm['completed_inspections']),
        'wait_s':cm['consequence_weighted_censored_delay_s'],'travel_m':cm['travel_m'],
        'completed_inspections':cm['completed_inspections'],'extra_visits':cm['extra_event_visits'],
        'revisit_violations':cm['tasks_violating_exact_gap'],'invalid_assignments':cm['invalid_assignments'],
        'duplicate_reservations':cm['duplicate_reservations']}


def aggregate(rows, limits):
    if not rows:
        raise ValueError('All registered development cases are required')
    n = len(rows)
    result = {key:sum(r[key] for r in rows) for key in ['gained','lost','net','revisit_violations','invalid_assignments','duplicate_reservations']}
    result.update({'mean_'+key:sum(r[key] for r in rows)/n for key in
                  ['travel_delta_pct','completion_loss_pct','travel_m','completed_inspections']})
    waits = [r['wait_s'] for r in rows if r['wait_s'] is not None]
    result['mean_wait_s'] = sum(waits)/len(waits) if waits else None
    result['eligible'] = (result['net'] >= limits['minimum_total_net_confirmations'] and
        result['mean_travel_delta_pct'] <= limits['maximum_travel_increase_pct'] and
        result['mean_completion_loss_pct'] <= limits['maximum_completion_loss_pct'] and
        result['revisit_violations']==result['invalid_assignments']==result['duplicate_reservations']==0)
    return result


def run_search(args):
    from .cli import ROOT
    protocol_path = Path(args.protocol)
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol['status'] != 'frozen_before_search' or protocol['study_id'] != 'response-defer-20261102-v1':
        raise ValueError('Expected frozen response/defer protocol')
    development = protocol['development']
    chains = protocol['search_chains']
    if len(development)!=12 or len(chains)!=3 or any(len(c['proposals'])!=4 for c in chains):
        raise ValueError('Registered search must contain12 cases and3x4 candidate opportunities')
    if len({c['id'] for c in development})!=12 or len({c['spec']['seed'] for c in development})!=12:
        raise ValueError('Development cases and process seeds must be distinct')
    if len({c['id'] for c in chains})!=3 or any(len({p['id'] for p in c['proposals']})!=4 for c in chains):
        raise ValueError('Chain and proposal identities must be unique')
    confirmation = protocol['confirmation']
    future_seeds = {c['spec']['seed'] for c in confirmation}
    if len(confirmation)!=12 or len(future_seeds)!=12 or future_seeds & set(protocol['seen_seeds']):
        raise ValueError('Expected12 new registered confirmation processes')
    if future_seeds & {c['spec']['seed'] for c in development}:
        raise ValueError('Development and confirmation seeds overlap')
    if protocol['execution'] != {'ttl_s':120,'extra_visit_budget':12,'priority':'fifo'}:
        raise ValueError('Execution permissions and expiry must remain fixed')
    if protocol['budgets']['search_environment_attempts'] != 144:
        raise ValueError('Unexpected search budget')
    if protocol['budgets']['model_calls'] != 24 or protocol['budgets']['all_environment_attempts'] != 552:
        raise ValueError('Unexpected full package allowance')
    baseline_dir = ROOT/protocol['baseline']['run_directory']
    index_path = ROOT/protocol['baseline']['index_path']
    if hashlib.sha256(index_path.read_bytes()).hexdigest()!=protocol['baseline']['index_sha256']:
        raise ValueError('Historical baseline index identity changed')
    index=json.loads(index_path.read_text(encoding='utf-8'))
    baselines={}
    for case in development:
        path=baseline_dir/(case['id']+'-fifo.json.gz')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=index[path.name]['sha256']:
            raise ValueError('Historical baseline record identity changed')
        with gzip.open(path,'rt',encoding='utf-8') as stream:record=json.load(stream)
        if record['spec']!=case['spec']:
            raise ValueError('Historical baseline specification mismatch')
        baselines[case['id']]=record
    for chain in chains:
        for proposal in chain['proposals']:ResponseRule.from_dict(proposal['rule'])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    (out/'protocol.json').write_bytes(protocol_bytes)
    sources={p.name:p.read_bytes() for p in Path(__file__).parent.glob('*.py')}
    (out/'source').mkdir()
    for name,data in sources.items():(out/'source'/name).write_bytes(data)
    write(out/'seal.json',{'at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':hashlib.sha256(protocol_bytes).hexdigest(),
        'source_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in sources.items()},
        'core_source_sha256':{name:hashlib.sha256(sources[name]).hexdigest() for name in protocol['core_source_files']}})
    (out/'baseline').mkdir()
    for case in development:
        filename=case['id']+'-fifo.json.gz'
        (out/'baseline'/filename).write_bytes((baseline_dir/filename).read_bytes())
    attempts,proposals,cache=[],[],{}
    selections=[]
    for chain in chains:
        retained=None
        for proposal in chain['proposals']:
            rule=ResponseRule.from_dict(proposal['rule'])
            entry={'chain':chain['id'],'proposal':proposal['id'],'rule':rule.to_dict(),
                   'rule_sha256':digest(rule.to_dict()),'status':'started','records':[]}
            proposals.append(entry);write(out/'proposals.json',proposals)
            pairs=[]
            try:
                for case in development:
                    key=digest({'spec':case['spec'],'rule':rule.to_dict()})
                    if key in cache:
                        record,filename=cache[key]
                        reused=True
                    else:
                        if len(attempts)>=protocol['budgets']['search_environment_attempts']:
                            raise RuntimeError('Search environment budget exhausted')
                        trial={'id':len(attempts)+1,'chain':chain['id'],'proposal':proposal['id'],
                            'case':case['id'],'at':datetime.now(timezone.utc).isoformat(),'status':'started'}
                        attempts.append(trial);write(out/'attempts.json',attempts)
                        try:
                            record,_=run_response(case['spec'],extra_visit_budget=12,response_rule=rule.to_dict())
                            filename=f"{chain['id']}-{proposal['id']}-{case['id']}.json.gz"
                            record['spec']=case['spec']
                            with gzip.open(out/filename,'wt',encoding='utf-8') as stream:json.dump(record,stream,allow_nan=False)
                            cache[key]=(record,filename);trial['status']='completed'
                        except Exception as error:
                            trial.update(status='failed',error=str(error));raise
                        finally:write(out/'attempts.json',attempts)
                        reused=False
                        print(f"search{len(attempts)}/144 {chain['id']} {proposal['id']} {case['id']}",flush=True)
                    pair=paired_outcomes(record,baselines[case['id']]);pairs.append({'case':case['id'],**pair})
                    entry['records'].append({'case':case['id'],'file':filename,'cached':reused})
                entry['paired']=pairs
                entry['aggregate']=aggregate(pairs,protocol['development_retention'])
                entry['status']='completed'
                score=lambda x:(-x['aggregate']['net'],x['aggregate']['mean_wait_s'],x['aggregate']['mean_travel_m'])
                if entry['aggregate']['eligible'] and (retained is None or score(entry)<score(retained)):
                    retained=entry
            except Exception as error:
                entry.update(status='failed',error=str(error));raise
            finally:write(out/'proposals.json',proposals)
        selections.append({'chain':chain['id'],'selected_proposal':retained['proposal'] if retained else None,
                           'selected_rule':retained['rule'] if retained else ResponseRule().to_dict(),
                           'aggregate':retained['aggregate'] if retained else None})
    if any((Path(__file__).parent/name).read_bytes()!=data for name,data in sources.items()) or protocol_path.read_bytes()!=protocol_bytes:
        raise RuntimeError('Code or protocol changed during search')
    proceed=any(s['selected_proposal'] is not None for s in selections)
    result={'study_id':protocol['study_id'],'phase':'search_completed','environment_attempts':len(attempts),
        'successful_environment_evaluations':sum(a['status']=='completed' for a in attempts),
        'candidate_opportunities':len(proposals),'historical_fifo_records_reused':len(baselines),
        'model_calls':0,'training':0,'selections':selections,
        'next_action':'continue_model_groups_under_frozen_budget' if proceed else 'stop_no_improvement_found_in_registered_search',
        'scope':'Development evidence only; no held-out process evaluated. No feedback or generalization gain conclusion.'}
    write(out/'selected-search.json',{'at':datetime.now(timezone.utc).isoformat(),'selections':selections})
    write(out/'summary.json',result)
    return result
