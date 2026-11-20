"""Transcribe the sealed native study, manifests and official ledgers into a reviewable public record."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
M=ROOT/'docs/mainline/v6-native-research-launch-v1/research-manifest.json'
G=ROOT/'docs/mainline/authorizations/v6-native-method-study-v1.json'
H='59080339a1846f242e0b8664e80a59b91ac623c768010ad1652e7d648c3b3301'
REVIEW='288c325fcba196c0eab3426a0e10730d13d77bd0'
ARMS=('V','D','K','H','P')


def require(value,why):
    if not value:raise ValueError(why)
def read(path):return json.loads(path.read_bytes())
def sha(data):return hashlib.sha256(data).hexdigest()
def h(path):return sha(path.read_bytes())
def identity(data):return sha(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def directions(rows, comp):
    fields={'physical':defaultdict(list),'resources':defaultdict(list),'person':defaultdict(list),'tool':defaultdict(list),
        'fee':defaultdict(list),'same_service':[],'gain_with_closure':[],'saved_resources_with_closure':[],
        'lost_closure':{},'gained_closure':{},'incomparable':[]}
    for row in rows:
        item=row['contrasts'][comp];key=row['condition']
        if not item['comparable']:
            fields['incomparable'].append(key)
            continue
        for name in ('physical','resources'):
            fields[name][item[name]['direction']].append(key)
        for name,direction in zip(('person','tool','fee'),item['resources']['components'],strict=True):
            fields[name][direction].append(key)
        if item['physical']['direction']=='EQUAL':fields['same_service'].append(key)
        if item['service_gain']:fields['gain_with_closure'].append(key)
        if item['same_service_resource_improvement']:fields['saved_resources_with_closure'].append(key)
        for name in ('lost','gained'):
            if item['closure'][name]:fields[name+'_closure'][key]=item['closure'][name]
    return fields


def main(directory):
    m=read(M);grant=read(G);receipt=read(directory/'retrieval.json');out=directory/'study'
    require(h(M)==H==grant['manifest_sha256']==receipt['manifest'],'Invalid manifest identity')
    remote=m['activity_root'];ledger=read(out/'progress.json');live=read(directory/'official-status.json')
    status_equal=ledger['rows']==live['rows'] and ledger['counts']==live['counts']
    if (out/'finished.json').exists():
        require(status_equal,'Sealed and independently reopened official status differ')
    proof=read(out/'admission.json')
    require(proof==read(directory/'consume/consumption.json') and proof['approval']['grant']==grant and
        proof['approval']['review_revision']==REVIEW and proof['approval']['grant_digest']==identity(grant),'One-use authority drift')
    for base,field in [('study','study_files_sha256'),('study','per_job_files_sha256'),('consume','consumption_sha256'),('control','controller_files_sha256')]:
        for name,expected in receipt[field].items():require(h(directory/base/name)==expected,'Retrieved identity drift: '+name)
    require(h(directory/'official-status.json')==receipt['official_status_sha256'] and h(directory/'actual-stages.jsonl')==receipt['stage_projection_sha256'],'Saved projection differs')
    ordered=[(group['condition'],arm) for group in m['groups'] for arm in group['fixed_order']]
    require(len(ordered)==85 and [c+'-'+a for c,a in ordered]==[r['unit'] for r in live['rows']],'Lost denominator')
    projected=[json.loads(line) for line in (directory/'actual-stages.jsonl').read_bytes().splitlines()]
    require([r['unit'] for r in projected]==[r['unit'] for r in live['rows']],'Missing stage record')
    inputs={g['condition']:g for g in m['groups']}
    full=(out/'finished.json').is_file()
    sealed_panel=None
    if full:
        panel_path=out/'jobs/C17/panel.json'
        require(h(panel_path)==read(out/'finished.json')['panel_sha256']==read(out/'jobs/C17/worker-result.json')['panel_sha256'],'Panel seal differs')
        sealed_panel=read(panel_path)
    scheduler={};jobs=[];summary_by_arm={a:dict(scheduled=17,started=0,returned=0,compliant=0,
        issued_tasks=0,first_closed=0,valid_at_checkpoints=[0,0,0],observed_instances=0,
        phase_counts=Counter(),actual_person_tool_fee_sums=[Fraction(0)]*3) for a in ARMS}
    for line in receipt['sacct']:
        fields=line.split('|')
        if len(fields)>=10 and fields[0].isdecimal():scheduler[fields[0]]=fields
    for item in live['jobs']:
        case=item['case'];jd=out/'jobs'/case
        job=item.get('submitted')
        j=dict(condition=case,job_id=job,reservation=read(jd/'reserved.json'),predecessor_totals=read(jd/'reserved.json')['previous_totals'],
               scheduler_accounting=scheduler.get(job),committed=(jd/'committed.json').is_file())
        for name,key in [('scheduler-command','scheduler_argv'),('worker-claim','allocation_claim'),('scheduler-terminal','terminal'),
                     ('submitted','submitted'),('release-requested','release_request')]:
            if (jd/(name+'.json')).exists():j[key]=read(jd/(name+'.json'))
        if (jd/'worker-result.json').exists():
            wr=read(jd/'worker-result.json')
            j.update(worker_passed=wr['passed'],actual_counts=wr['counts'],sealed_scores=wr.get('scores'),worker_failure=wr.get('failure'),
                     worker_result_sha256=h(jd/'worker-result.json'))
        if j['committed']:
            commit=read(jd/'committed.json')
            for f,v in commit['files'].items():require(h(jd/f)==v,'Case commit differs: '+case+'/'+f)
            require(j['terminal']['state']=='COMPLETED' and j['terminal']['exit']=='0:0' and scheduler[job][3:5]==['COMPLETED','0:0'],'Slurm and controller terminal differ')
        jobs.append(j)
    arms=[]
    for (case,arm),slot,stage in zip(ordered,live['rows'],projected,strict=True):
        key=case+'-'+arm;jd=out/'jobs'/case;ad=jd/'arms'/key
        record=dict(unit=key,condition=case,arm=arm,state=slot['state'],expected_input_sha256=inputs[case]['arm_inputs'][arm]['complete_call'],
            process_account=slot,score=None,actual_stages=None)
        summary=summary_by_arm[arm];summary['started']+=int(slot['known_start']);summary['returned']+=int(slot['validated_return'])
        if stage.get('validated_receipt'):
            ret=stage['validated_receipt']
            require(ret==read(ad/'native-return.json') and ret['full_input']==record['expected_input_sha256'] and
                    ret['native_sha256']==stage['native_sha256'] and ret['source_tree']==m['native_source_tree'],'Actual native identity differs: '+key)
            changes=[]
            for decision in stage['decisions']:
                if not changes or decision[2] is not None or decision[1:]!=changes[-1][1:]:
                    changes.append(decision)
            record.update(native_sha256=stage['native_sha256'],native_artifacts=stage['artifacts'],
                native_return=ret,actual_stages={f:stage[f] for f in ('work_records','arrived_work_receipts','action_reports','arrived_portable_records','observation_binding')},
                separately_recorded_public_forecast=stage['first_public_selections'])
            record['actual_stages'].update(public_decision_changes=changes,decision_count=len(stage['decisions']),all_decisions_projection_sha256=identity(stage['decisions']))
            bind=read(ad/'execution-binding.json')
            require(bind['manifest_sha256']==H and bind['purpose']=='NATIVE_V6_RESEARCH' and bind['actual_worker_python_sha256']==m['python']['sha256'],'Execution identity differs')
            require(read(ad/'call.json')['input_sha256']==ret['full_input'],'Command receipt differs')
            record['execution_binding_sha256']=h(ad/'execution-binding.json');record['command_sha256']=h(ad/'call.json')
            record['conditional_predictions_scope']='First observed selection per question; model window 8 to 10 s. All trajectories, full forecasts and public histories are retained in the private native return.'
            summary['issued_tasks']+=len(stage['work_records'])
            for task in stage['work_records']:
                summary['phase_counts'][task['id'].split('/')[-1].rsplit('-',1)[0]]+=1
        if (ad/'score.json').is_file():
            score=read(ad/'score.json');pinned=h(ad/'score.json')
            require(score['input_sha256']==record['expected_input_sha256'] and score['native_sha256']==record.get('native_sha256') and
                    score['native_source']==m['native_source_tree'],'Score identity differs: '+key)
            if (jd/'committed.json').is_file():
                wr=read(jd/'worker-result.json')
                require(wr['scores'][arm]==pinned and wr['raw_bindings'][arm]['native']==score['native_sha256'],'Committed score digest differs: '+key)
            record.update(score_sha256=pinned,semantic_sha256=score['semantic_sha256'],score=dict(
                service={k:score['service'][k] for k in ('balance','rate')},native_summary=score['native_summary'],
                resources={k:score['resources'][k] for k in ('balance','rate','admission','actual_components')},
                questions=score['questions'],violations=score['violations'],internal_decisions=score['internal_policy_calls']))
            summary['compliant']+=int(slot['state']=='COMPLETED' and not score['violations'])
            summary['observed_instances']+=len(score['questions'])
            for q in score['questions'].values():
                summary['first_closed']+=int(q['first'] is not None)
                for i,k in enumerate(q['at']):summary['valid_at_checkpoints'][i]+=int(k['closed'])
            for i,value in enumerate(score['resources']['balance']):summary['actual_person_tool_fee_sums'][i]+=Fraction(value)
        arms.append(record)
    for s in summary_by_arm.values():s['actual_person_tool_fee_sums']=list(map(str,s['actual_person_tool_fee_sums']))
    directions_by_arm={k:directions(sealed_panel['rows'],k) for k in ('D','K','P','H')} if full else None
    if full:
        require(len(jobs)==17 and all(j['committed'] for j in jobs) and all(r['state']=='COMPLETED' and r['score'] for r in arms)
                and [r['condition'] for r in sealed_panel['rows']]==[g['condition'] for g in m['groups']],'Incomplete seal')
        require(all(r['consistency'] for r in sealed_panel['rows']) and
            all(arms[i]['semantic_sha256']==arms[i+3]['semantic_sha256'] and arms[i]['expected_input_sha256']==arms[i+3]['expected_input_sha256']
                and (arms[i]['process_account']['pid'],arms[i]['process_account']['start_ns'])!=(arms[i+3]['process_account']['pid'],arms[i+3]['process_account']['start_ns'])
                for i in range(0,85,5)),'V/H consistency or distinct launch drift')
    projection_archive=read(directory/'publication-archive.json')
    require(projection_archive['directory']==receipt['controller_receipt_directory']+'/publication' and
            projection_archive['files']=={k:h(directory/k) for k in ('retrieval.json','actual-stages.jsonl')}, 'Publication receipts not archived')
    result=dict(schema='aegisdc-native-v6-single-consumption-study-delivery-v1',status='SEALED_FULL_PANEL' if full else 'STOPPED_WITH_RETAINED_SUFFIX',
        master_roadmap='docs/mainline/master-roadmap.md',accepted_readiness='69bc0a52677d541e5726db1a919b743287887ca5',
        approval_revision=REVIEW,manifest_sha256=H,protocol=m['protocol_revision'],launch_source_revision=m['launch_source_revision'],
        source_tree=m['native_source_tree'],launcher_tree=m['launcher_tree'],python=m['python'],
        control=dict(canonical_grant=grant,grant_file_sha256=h(G),grant_digest=identity(grant),admission_sha256=h(out/'admission.json'),
            consumption_sha256=h(directory/'consume/consumption.json'),accepted_proof=proof,controller_exit=(directory/'control/controller.exit').read_text().strip(),
            controller_command_sha256=h(directory/'control/controller.sh'),controller_output=(directory/'control/controller.stdout').read_text().strip(),
            controller_errors=(directory/'control/controller.stderr').read_text().strip(),private_receipts=receipt['controller_receipt_directory']),
        frozen_budget=m['budget'],account=dict(persisted_progress_matches_reopened_status=status_equal,denominator=live['denominator'],counts=live['counts'],job_reservations=live['job_reservations'],
            reserved_cpu_s=live['reserved_cpu_s'],exact_decisions=live['total_decisions_exact'],exact_starts=live['total_starts_exact'],
            exact_manual_issues=live['total_manual_issues_exact'],not_executed=live['not_executed'],unresolved_jobs=live['unresolved_jobs'],
            unknown_submission_ids=live['unknown_submission_ids'],unresolved_scheduler_outcomes=live['unresolved_scheduler_outcomes'],
            measured_research_starts=live['research_arms_executed'],retries=0),
        halt=read(out/'halt.json') if (out/'halt.json').exists() else None,
        jobs=jobs,scheduler_fields=receipt['sacct_fields'],by_treatment=summary_by_arm,
        comparisons=directions_by_arm,official_panel=sealed_panel,arms=arms,
        preserved=dict(private_activity=remote,official_progress_sha256=h(out/'progress.json'),official_status_sha256=receipt['official_status_sha256'],
            sealed_panel_sha256=h(out/'jobs/C17/panel.json') if full else None,extracted_stages_sha256=receipt['stage_projection_sha256'],
            retrieval_sha256=h(directory/'retrieval.json'),publication_receipts=projection_archive,projection_tool_sha256=receipt['projection_tool_sha256'],collector_sha256=receipt['collector_sha256'],
            publication_tool_sha256=sha(Path(__file__).read_bytes())),
        scope='One disclosed condition panel on the complete native synthetic facility; old engineering/confirmation records remain separate. No successor, ordinary improvement, RSI or independent confirmation executed.')
    with (HERE/'result.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=1,allow_nan=False);f.write('\n')
    print('published rows',len(arms),'full seal',full,'jobs',len(jobs),'confirmed calls',ledger['counts']['known_decisions'])


if __name__=='__main__':main(Path(sys.argv[1]))
