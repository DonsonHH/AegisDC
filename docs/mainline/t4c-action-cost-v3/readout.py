"""Select summaries from fully scored, saved outcomes for the first page of the development report."""
import gzip
from collections import Counter
from common_v3 import *

def main():
    job()
    with gzip.open(ACT/'development.json.gz','rt') as fp:r=json.load(fp)
    rows=r['rows'];s=r['scopes']['overall'];methods=('VSTAR','V_COST');all_layers=Counter(i['layer'] for i in rows)
    examples={}
    for item in rows:
        a=item['arms'];new=a['V_COST'];b=a['B'];blind=a['BPLUS'];p=a['P'];off=a['V_COST_NOPROBE'];key=item['key']
        had_read=any(name.endswith('::I') for _,name in new['requests'])
        facts={'direct_worse_than_protected':b['L']>p['L']+1e-7,'probe_lower_than_ablation':had_read and new['L']<off['L']-1e-7,
               'probe_higher_than_ablation':had_read and new['L']>off['L']+1e-7,
               'repurposed_rule_worse_than_direct':new['L']>b['L']+1e-7,'direct_positive_attains':key in r['direct_optimal_positive'],
               'actual_blind_receipt_differs':b['requests']!=blind['requests'],'blind_strictly_worse_than_direct':blind['L']>b['L']+1e-7}
        for fact,ok in facts.items():
            if ok and fact not in examples:
                examples[fact]=dict(key=key,family=item['family'],tier=item['duration'],min=item['minimum'],scores={k:a[k]['L'] for k in ('P','VSTAR','V_COST','V_COST_NOPROBE','B','BPLUS')},
                    paid=[{k:z[k] for k in ('task','sampled','arrived','fields')} for z in new['paid'] if z['phase']=='I'],
                    actions={k:a[k]['requests'] for k in ('V_COST','V_COST_NOPROBE','B','BPLUS')})
    def difference(role,comp):
        ds=[r['arms'][role]['L']-r['arms'][comp]['L'] for r in rows]
        return [sum(v<-1e-7 for v in ds),sum(abs(v)<=1e-7 for v in ds),sum(v>1e-7 for v in ds)]
    acquisition={}
    for v in methods:
        rs=r['acquisition'][v]['rows'];ds=[z['delta']['L'] for z in rs]
        acquisition[v]=dict(buy_rows=len(rs),directions=[sum(t<-1e-7 for t in ds),sum(abs(t)<=1e-7 for t in ds),sum(t>1e-7 for t in ds)],
            conditional=r['acquisition'][v]['conditional_means'],all=s['paired'][v][v+'_NOPROBE'])
    write(ACT/'headline.json',dict(n=len(rows),scopes={k:dict(n=v['n'],B=v['paired']['V_COST']['B']) for k,v in r['scopes'].items()},
        by_role=s['by_role'],comparisons=s['paired'],old=r['old_v2'],layer_n=dict(all_layers),acquisition=acquisition,gaps=r['remaining_gap'],
        direct_best_positive=r['direct_optimal_positive'],wrong_vs_P={v:difference(v,'P') for v in ('B','BPLUS','V_COST')},
        BPLUS_vs_B=difference('BPLUS','B'),examples=examples,exposure_frequencies=dict(Counter(q['duration'] for q in rows)),
        correct_and_missing_jobs='see consolidated receipt'))
if __name__=='__main__':main()
