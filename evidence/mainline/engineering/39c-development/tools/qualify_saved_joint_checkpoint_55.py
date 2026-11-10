"""Qualify original joint captures with corrected edge gates; never import facility code."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import socket
import sys
import traceback
import zipfile


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def close(actual, expected, label):
    need(type(actual) in (int, float) and math.isfinite(actual)
         and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), label)


def qualify(data, manifest):
    """Compare exact original records, independent literal outcomes and dimensional sums."""
    results, external_checks = [], []
    expected = {
        'single-worker': dict(travel=2, work=2, gate=.5, rendezvous=0, total=4.5, tool=4.5, tool_work=2,
            action=3.25, action_report=3.75, recheck=5, recheck_report=5.5, closed=5.5, deficit=0, tasks=2, decisions=8),
        'crew-rendezvous': dict(travel=5, work=3, gate=1, rendezvous=1.25, total=10.25, tool=5.75, tool_work=2,
            action=4.5, action_report=5, recheck=6.25, recheck_report=6.75, closed=7, deficit=0, tasks=2, decisions=11),
        'no-human': dict(travel=0, work=0, gate=0, rendezvous=0, total=0, tool=0, tool_work=0,
            action=None, action_report=None, recheck=None, recheck_report=None, closed=None, deficit=0, tasks=0, decisions=8),
        'service-unqualified': dict(travel=2, work=2, gate=.5, rendezvous=0, total=4.5, tool=4.5, tool_work=2,
            action=3.25, action_report=3.75, recheck=5, recheck_report=5.5, closed=None, deficit=3.5, tasks=2, decisions=8),
    }
    original54 = json.loads(data[manifest['original54_terminal']])
    need(original54['status'] == 'FAILED' and original54['failures'] == 2 and original54['errors'] == 0,
         'Original54 failure must remain FAILED with its two assertions')
    original_rows = json.loads(data[manifest['original54_qualification']])
    need([(r['case'], r['passed']) for r in original_rows] ==
         [('crew-rendezvous', False), ('no-human', True), ('service-unqualified', True)],
         'Original54 subcase states changed')
    for capture in manifest['captures']:
        name, prefix, case = capture['name'], capture['prefix'], capture['case_directory']
        terminal = json.loads(data[prefix+'/terminal.json'])
        source = json.loads(data[prefix+'/source-manifest.json'])
        for suffix in ('frozen-call-input.json', 'business-result.json', 'public-decisions.json', 'actual-summary.json'):
            rel = case+'/'+suffix
            raw = data[prefix+'/'+rel]
            need(terminal['output_files'][rel] == dict(bytes=len(raw), sha256=sha(raw)), 'Original member changed: '+rel)
        call = json.loads(data[prefix+'/'+case+'/frozen-call-input.json'])
        joint = json.loads(data[prefix+'/'+case+'/business-result.json'])
        public = json.loads(data[prefix+'/'+case+'/public-decisions.json'])
        summary = json.loads(data[prefix+'/'+case+'/actual-summary.json'])
        need(source['execution_source'] == manifest['execution_source'], 'Original runtime revision differs')
        for path, identity in joint['execution_code_identity']['files'].items():
            need(source['files'][path]['sha256'] == identity, 'Original runtime file hash differs: '+path)
        native_root = Path(capture['native_root']).resolve()
        allowed = {Path(p).resolve() for p in manifest['allowed_native_roots']}
        need(native_root in allowed, 'Unexpected original private capture root')
        raw_run, selected_trace = None, {}
        for suffix in ('run.json', 'private-state.jsonl', 'balances.jsonl'):
            rel = case+'/actual-run/'+suffix
            path = native_root/rel
            need(path.resolve().is_relative_to(native_root) and not path.is_symlink(), 'Original path escaped')
            raw = path.read_bytes()
            need(terminal['output_files'][rel] == dict(bytes=len(raw), sha256=sha(raw)), 'Private original hash differs: '+rel)
            external_checks.append(dict(path=str(path), bytes=len(raw), sha256=sha(raw)))
            if suffix == 'run.json':
                raw_run = json.loads(raw)
            elif suffix == 'private-state.jsonl' and name == 'crew-rendezvous':
                for line in raw.splitlines():
                    row = json.loads(line)
                    if row['time_s'] in (3.25, 3.5):
                        selected_trace[row['time_s']] = row['domains']['people_tools_work']['workers']
        need(raw_run['business_evaluation'] == joint and raw_run['policy_public_decisions'] == public,
             'Returned joint/public records differ from the original private run')
        need(raw_run['summary'] == summary['summary'] and raw_run['work_records'] == summary['work_records'],
             'Returned actual summary differs from original run')
        business = call['business_program']
        normalized = sorted((dict(b, time_s=float(b['time_s']), value=float(b['value'])) for b in call['boundary_events']),
                            key=lambda b:b['time_s'])
        binding = dict(scenario_sha256=digest(call['scenario']), dispatch_program_sha256=digest(call['dispatch_program']),
            boundary_events_sha256=digest(normalized), action_commands_sha256=digest([]),
            duration_s=float(call['duration_s']), maximum_step_s=call['step_s'])
        need(joint['run_binding'] == business['run_binding'] == binding, 'Common normalized input binding differs')
        need(joint['business_program_sha256'] == digest(business), 'Whole business program hash differs')
        for key, component in joint['components'].items():
            need(component['execution_code_identity'] == joint['execution_code_identity']
                 and component['facility_id'] == call['scenario']['id'] and component['window_end_s'] == call['duration_s']
                 and component['visibility'] == 'PRIVATE_EVALUATOR_ONLY', 'Component identity/window differs')
            need(joint['component_program_sha256'][key] == digest(business['components'][key]), 'Component input hash differs')
        exp = expected[name]
        diagnostic = joint['components']['diagnostic']
        need(diagnostic['events'][0]['first_corroborated_fault_report_at_s'] == .5
             and diagnostic['events'][0]['reference_opportunity']['status'] == 'ELIGIBLE'
             and diagnostic['counts']['eligible_fault_matured'] == 1
             and diagnostic['counts']['timely_confirmed_fault'] == 1, 'Diagnostic opportunity/confirmation differs')
        need(diagnostic['prevention_effect']['status'] == 'NOT_IDENTIFIED_NO_PAIRED_COUNTERFACTUAL', 'Prevention claim changed')
        episodes = {e['question_id']:e for e in joint['components']['instance_closure']['episodes']}
        old, new = (episodes['cooling-direct/question-'+str(i)] for i in (0, 1))
        for qid, episode in episodes.items():
            need(episode['assessments'] == [q for d in public for q in d['choice']['question_lifecycle']['questions']
                                           if q['question_id'] == qid], 'Public/private instance assessment differs')
        for field, value in dict(actual_action_completed_at_s=exp['action'], action_report_arrived_at_s=exp['action_report'],
            actual_recheck_completed_at_s=exp['recheck'], recheck_report_arrived_at_s=exp['recheck_report'],
            first_verified_closed_at_s=exp['closed']).items():
            need(old[field] == value, name+' corrected literal clock differs: '+field)
        need(new['first_risk_accepted_at_s'] == 5.75 and new['first_verified_closed_at_s'] is None
             and new['actual_action_completed_at_s'] is None and new['actual_recheck_completed_at_s'] is None
             and new['assessments'][-1]['risk_closed'] is False
             and new['assessments'][-1]['physical_restoration_claim'] is False, 'Management/physical scope differs')
        cost = joint['components']['costs']
        values = {k:v['value'] for k,v in cost['actual'].items()}
        wanted = dict(worker_travel_person_s=exp['travel'], worker_work_person_s=exp['work'],
            worker_wait_person_s=exp['gate']+exp['rendezvous'], access_check_person_s=exp['gate'],
            rendezvous_wait_person_s=exp['rendezvous'], queue_wait_person_s=0,
            tool_occupation_tool_s=exp['tool'], tool_work_tool_s=exp['tool_work'])
        for key, target in wanted.items():
            close(values[key], target, name+' actual '+key)
            need(cost['actual'][key]['unit'] == ('tool_s' if key.startswith('tool_') else 'person_s'), 'Cost unit differs')
        close(cost['personnel_total']['value'], exp['total'], 'Personnel total differs')
        close(values['worker_travel_person_s']+values['worker_work_person_s']+values['worker_wait_person_s'], exp['total'], 'Person partition differs')
        need(values['tool_work_tool_s'] <= values['tool_occupation_tool_s'], 'Tool subset differs')
        attribution = cost['failure_attribution']
        for key in values:
            close(sum(row['actual'][key]['value'] for row in attribution['per_task']+attribution['shared_queue_costs']),
                  values[key], 'Task cost reconciliation differs')
        close(cost['issue_fees']['value'], exp['tasks'], 'Issued fee differs')
        need(cost['issue_fees']['unit'] == 'declared_research_cost', 'Fee unit differs')
        need(cost['distance_m']['value'] is None and cost['currency_payment']['value'] is None
             and cost['computation']['internal_nested_calls']['value'] is None, 'Unmeasured cost was turned into zero')
        audits = raw_run['policy_computation_audit']
        need(cost['computation']['audit_record_details'] == audits, 'Raw audit copy differs')
        for key, aggregate in (('elapsed_ns', 'selector_elapsed_ns'), ('condition_assessment_elapsed_ns', 'condition_assessment_elapsed_ns')):
            need(all(type(a[key]) is int and a[key] >= 0 for a in audits), 'Invalid raw wall-time value')
            need(cost['computation'][aggregate]['value'] == sum(a[key] for a in audits), 'Timing aggregate differs from its own raw sum')
        close(summary['summary']['service_deficit_time_s'], exp['deficit'], 'Service deficit differs')
        need(len(public) == exp['decisions'] and len(summary['work_records']) == exp['tasks'], 'Actual task/decision count differs')
        need('joint53-private' not in json.dumps(public), 'Private declaration appeared in public dispatch')
        if name == 'crew-rendezvous':
            need(selected_trace[3.25]['worker_control']['stage'] == 'gate_check'
                 and selected_trace[3.25]['worker_cooling']['status'] == 'waiting', 'Second edge gate/rendezvous witness differs')
            need(all(selected_trace[3.5][worker]['status'] == 'working' for worker in ('worker_control', 'worker_cooling')),
                 'Both crew members must start together at3.5')
        if name == 'service-unqualified':
            need([b['time_s'] for b in call['boundary_events']] == [2, 1]
                 and [b['time_s'] for b in raw_run['inputs']['boundary_events']] == [1, 2], 'Raw/normalized order differs')
            need(binding['boundary_events_sha256'] != digest(call['boundary_events']), 'Raw and normalized identities were conflated')
            need(business['components']['diagnostic']['reference']['boundary_events_sha256'] == digest(call['boundary_events']),
                 'Legacy raw diagnostic reference changed')
            need(old['assessments'][-1]['own_recheck']['passed'] is True
                 and not next(c for c in old['assessments'][-1]['checks'] if c['role'] == 'service')['passed'], 'Service negative differs')
        results.append(dict(case=name, saved_qualification='PASS', horizon_s=call['duration_s'],
            confirmation_at_s=.5, own_first_verified_closed_at_s=old['first_verified_closed_at_s'],
            new_instance_first_management_accept_at_s=5.75, service_deficit_time_s=exp['deficit'],
            actual=values, personnel_total=cost['personnel_total']['value'], issue_fee=cost['issue_fees']['value'],
            task_count=exp['tasks'], returned_decisions=exp['decisions']))
    return dict(status='SAVED_JOINT_QUALIFICATION_PASSED', original54_status='FAILED_RETAINED',
        corrected_finding='39C-COMPOSITE-SPEC-11', corrected_active_regression_test_executed=False,
        cases=results, private_original_hash_checks=external_checks, new_facility_calls=0,
        new_public_choices=0, new_model_calls=0, new_research_trials=0, whole39c_accepted=False)


def figures(plt, rows, output):
    labels = ['Single worker\n53', 'Two workers\n54 corrected', 'No human\n54', 'Service loss\n54']
    fig, axes = plt.subplots(2, 2, figsize=(13.4, 8.5))
    bottom = [0.0]*4
    for key, label, color in [('worker_work_person_s', 'Work', '#0072B2'),
        ('worker_travel_person_s', 'Travel', '#009E73'), ('access_check_person_s', 'Edge/access checks', '#8b96a3'),
        ('rendezvous_wait_person_s', 'Rendezvous', '#E69F00')]:
        heights = [r['actual'][key] for r in rows]
        axes[0,0].bar(range(4), heights, bottom=bottom, label=label, color=color)
        bottom = [a+b for a,b in zip(bottom,heights)]
    for i,r in enumerate(rows):
        axes[0,0].text(i, r['personnel_total']+.14, f"{r['personnel_total']:g}", ha='center', fontsize=10)
    axes[0,0].set(title='A   Actual personnel occupation', ylabel='person_s', ylim=(0,12))
    axes[0,0].legend(fontsize=8, loc='upper right')
    axes[0,1].bar(range(4), [r['actual']['tool_occupation_tool_s'] for r in rows], color='#cbdfee', label='Occupation')
    axes[0,1].bar(range(4), [r['actual']['tool_work_tool_s'] for r in rows], width=.35, color='#0072B2', label='Working subset')
    for i,r in enumerate(rows):
        axes[0,1].text(i, r['actual']['tool_occupation_tool_s']+.12, f"{r['actual']['tool_occupation_tool_s']:g}", ha='center')
    axes[0,1].set(title='B   Actual tool occupation and work', ylabel='tool_s', ylim=(0,7))
    axes[0,1].legend(fontsize=9)
    for ax in axes[0,:]:
        ax.set_xticks(range(4), labels)
        ax.grid(axis='y', color='#e3e8ec'); ax.set_axisbelow(True)
    ax = axes[1,0]
    ax.axvline(.5, color='#009E73', linestyle=':', label='Flow confirmation (all cases)')
    for i,r in enumerate(rows):
        closed = r['own_first_verified_closed_at_s']
        if closed is None:
            ax.scatter(r['horizon_s'], i-.1, marker='x', color='#7d8793', s=65, label='q0 closure censored' if i==2 else None)
        else:
            ax.scatter(closed, i-.1, color='#0072B2', s=55, label='q0 physically verified' if i==0 else None)
        ax.scatter(5.75, i+.1, marker='D', color='#E69F00', s=42, label='q1 management acceptance' if i==0 else None)
    ax.set_yticks(range(4), ['Single worker', 'Two workers', 'No human', 'Service loss'])
    ax.set(xlim=(0,7.7), ylim=(3.6,-.65), xlabel='Facility time (s)', title='C   Different instances and closure meanings')
    ax.grid(axis='x',color='#e3e8ec'); ax.set_axisbelow(True)
    ax.legend(fontsize=7.5, ncols=2, loc='lower left')
    ax = axes[1,1]; ax.axis('off')
    table = ax.table(cellText=[[label.replace('\n',' '),r['task_count'],f"{r['service_deficit_time_s']:g}",r['issue_fee']]
        for label,r in zip(labels,rows)], colLabels=['Configuration','Tasks','Service deficit (s)','Issue fee'],
        cellLoc='center', bbox=[0,.18,1,.65], colWidths=[.35,.12,.34,.19])
    table.auto_set_font_size(False); table.set_fontsize(9)
    for (row,_),cell in table.get_celld().items():
        cell.set_edgecolor('white'); cell.set_facecolor('#e9f1f7' if row==0 else '#f4f6f8')
    ax.set_title('D   Actual outcomes; fees in declared research units',loc='left',fontsize=10)
    for ax in (axes[0,0],axes[0,1],axes[1,0]):
        ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    fig.suptitle('Joint endpoint qualification: saved actual records',fontsize=15,fontweight='bold')
    fig.text(.5,.018,'Engineering configurations, not a method-effect comparison. Original54 failure retained; crew oracle corrected for per-edge checks.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.95],h_pad=2.5,w_pad=2.5)
    for ext in ('png','svg'):
        fig.savefig(output/('joint-endpoints-and-costs.'+ext),dpi=300,metadata={'Creator':'AegisDC saved qualification55'})
    plt.close(fig)
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig,ax=plt.subplots(figsize=(12,6));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    boxes = {
        'plant':(.03,.73,.26,.18,'Private eight-domain plant\nworkers, tools, gates and service'),
        'evidence':(.37,.73,.26,.18,'Public arrived evidence\nfixed / handheld / work orders'),
        'dispatch':(.71,.73,.26,.18,'Public inspection / action choice\nqualifications and resource budgets'),
        'result':(.03,.39,.26,.18,'One actual RunResult\nprivate trace, work and public records'),
        'diagnostic':(.37,.39,.18,.18,'Private diagnostic /\ntemporal v3'),
        'closure':(.58,.39,.18,.18,'Private instance\nclosure v2'),
        'costs':(.79,.39,.18,.18,'Private actual\ncost v2'),
        'joint':(.37,.09,.39,.16,'One composite result\ncommon input / source / time binding'),
        'replay':(.80,.09,.17,.16,'Recorded read /\nexact replay\nPENDING')}
    for key,(x,y,w,h,label) in boxes.items():
        color='#e7f5ee' if key in ('evidence','dispatch') else '#eef3f8'
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.01',facecolor=color,
            edgecolor='#a1adb9',linestyle='--' if key=='replay' else '-',linewidth=1.1))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=9)
    def arrow(a,b,style='-'):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,linewidth=1.1,color='#697b8d',linestyle=style))
    arrow((.29,.82),(.36,.82));arrow((.63,.82),(.70,.82))
    ax.add_patch(FancyArrowPatch((.84,.73),(.16,.73),connectionstyle='arc3,rad=-.12',
        arrowstyle='-|>',mutation_scale=12,linewidth=1.1,color='#697b8d'))
    arrow((.16,.73),(.16,.58))
    for x in (.46,.67,.88):
        arrow((.29,.48),(x,.58));arrow((x,.39),(.565,.26))
    arrow((.76,.17),(.79,.17),'--')
    ax.text(.50,.98,'Actual public/private boundaries and remaining replay work',ha='center',fontsize=14,fontweight='bold')
    ax.text(.50,.655,'Authorized work executes in the plant; only arrived evidence is returned to selection.',ha='center',fontsize=10)
    ax.text(.50,.02,'Green: public decision inputs. Blue: private plant/evaluator outputs. Private truth has no route into the selector.',ha='center',fontsize=9)
    for ext in ('png','svg'):
        fig.savefig(output/('joint-public-private-architecture.'+ext),dpi=300,bbox_inches='tight',metadata={'Creator':'AegisDC saved qualification55'})
    plt.close(fig)
    with (output/'joint-actual-data.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['case','horizon_s','confirmation_s','q0_first_physical_close_s','q1_management_accept_s',
            'travel_person_s','work_person_s','gate_person_s','rendezvous_person_s','person_total_s','tool_occupation_s','tool_work_s','service_deficit_s','issue_fee_research_unit'])
        for r in rows:
            writer.writerow([r['case'],r['horizon_s'],.5,r['own_first_verified_closed_at_s'],5.75,
                *[r['actual'][k] for k in ('worker_travel_person_s','worker_work_person_s','access_check_person_s','rendezvous_wait_person_s')],
                r['personnel_total'],r['actual']['tool_occupation_tool_s'],r['actual']['tool_work_tool_s'],r['service_deficit_time_s'],r['issue_fee']])


def html_report(output, qualification):
    images = [base64.b64encode((output/name).read_bytes()).decode() for name in
              ('joint-endpoints-and-costs.png','joint-public-private-architecture.png')]
    cells=''.join('<tr><td>'+r['case']+'</td><td>'+str(r['own_first_verified_closed_at_s'] if r['own_first_verified_closed_at_s'] is not None else '未观察到')+
        '</td><td>5.75</td><td>'+str(r['personnel_total'])+'</td><td>'+str(r['actual']['tool_occupation_tool_s'])+
        '</td><td>'+str(r['service_deficit_time_s'])+'</td></tr>' for r in qualification['cases'])
    report='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AegisDC 联合评价阅读检查点</title><style>body{margin:0;background:#f4f6f8;color:#233044;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1360px;margin:auto;padding:32px 20px}h1{font-size:clamp(26px,4vw,42px);line-height:1.3}section{background:white;border-radius:16px;padding:24px;margin:22px 0}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}th,td{text-align:left;border-bottom:1px solid #e1e7ee;padding:10px}.scroll{overflow:auto}.muted{color:#56677a}a{color:#0069a8}@media(max-width:600px){main{padding:16px 12px}section{padding:16px}}@media print{body{background:white}section{break-inside:avoid;padding:0}main{padding:0}}</style><main>
<p class="muted">完整合成设施 · 39c工程开发检查点 · 原180次研究及NO_PRACTICAL_GAIN保持</p><h1>诊断、处置后关闭与实际成本<br>现在来自同一次设施运行</h1>
<p>固定测点在0.5秒确认异常。单人自身链在5.5秒核验关闭，双人链经逐边门禁后在7秒核验关闭。新问题在5.75秒的接受风险属于管理处置，物理关闭仍为空。</p>
<section><h2>四个实际工况</h2><div class="scroll"><table><thead><tr><th>工况</th><th>旧问题首次物理关闭/秒</th><th>新问题管理接受/秒</th><th>实际人秒</th><th>工具占用秒</th><th>服务缺额秒</th></tr></thead><tbody>ROWS</tbody></table></div>
<p>无人策略仍保留适用的确认机会分母；服务负例中冷却复检合格，服务证据不合格，所以旧问题保持未关闭。不同工况用于工程资格，不作为策略增益样本。</p><img alt="实际工时、工具、关闭语义及服务结果" src="data:image/png;base64:IMAGE0"></section>
<section><h2>公开决策与私有评价边界</h2><img alt="同一运行的三个私有评价组件和待实现重放" src="data:image/png;base64:IMAGE1"><p>场景、完整派工及生产者、规范化边界/命令、步长、窗口与源码身份共同绑定。诊断真值只进入私有评价器。</p></section>
<section><h2>原失败与更正</h2><p>54原资格保持FAILED。原双人预期漏计控制人员第二条边的门禁；原运行全部完成且完整保留。55只核对保存原件，未新增设施运行。双人实际等待2.25人秒＝门禁1＋集合1.25，人时总量10.25，工具占用5.75。密度原说明另有1000→实际998kg/m³更正，物理输入未改。</p>
<p>后续还需完成业务记录/读取/精确重放、整票独立复核、零跳过根验收与fresh，再进入39d时间尺度/数值范围及后续AI研究。AI/RSI效果未测，现场标定PENDING。</p>
<p><a href="https://github.com/DonsonHH/AegisDC/tree/donson/mainline-39c-endpoints/evidence/mainline/engineering/39c-development">源数据、冻结协议和失败原件</a> · <a href="joint-actual-data.csv">图表CSV</a></p></section></main></html>'''
    report=report.replace('ROWS',cells).replace('IMAGE0',images[0]).replace('IMAGE1',images[1])
    with (output/'AegisDC-joint-checkpoint.html').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(report+'\n')


def main():
    need(not sys.flags.optimize, 'Optimized saved qualification is forbidden')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw_manifest=args.manifest.read_bytes();manifest=json.loads(raw_manifest)
    root=Path('/root/private_data/aegisdc-mainline-39c').resolve()
    need(os.geteuid()==0 and socket.gethostname()==manifest['hostname'] and platform.python_version()=='3.12.7'
         and not os.environ.get('SLURM_JOB_ID') and Path('/root/private_data').is_mount(), 'Saved qualification host differs')
    need(args.output.resolve()==Path(manifest['output_root']).resolve() and args.output.resolve().is_relative_to(root), 'Output root differs')
    for name, expected in manifest['software'].items():
        need(version(name)==expected,'Frozen plotting distribution differs: '+name)
    args.output.mkdir(mode=0o700,exist_ok=False)
    terminal=dict(status='FAILED',source=manifest['source_commit'],new_facility_calls=0,new_public_choices=0,new_model_calls=0,new_research_trials=0)
    save(args.output/'attempt.json',dict(classification='SAVED_QUALIFICATION_AND_FIGURES_NO_FACILITY_EXECUTION',
        source=manifest['source_commit'],manifest_sha256=sha(raw_manifest),python=sys.version,
        started_utc=datetime.now(timezone.utc).isoformat(),software=manifest['software']))
    try:
        need(sha(args.snapshot.read_bytes())==manifest['snapshot_sha256'],'Frozen saved-data archive differs')
        with zipfile.ZipFile(args.snapshot) as archive:
            need(sorted(archive.namelist())==sorted(manifest['files']),'Frozen saved-data paths differ')
            data={name:archive.read(name) for name in archive.namelist()}
        for name, record in manifest['files'].items():
            need(len(data[name])==record['bytes'] and sha(data[name])==record['sha256'],'Frozen input differs: '+name)
        qualification=qualify(data,manifest)
        save(args.output/'saved-qualification.json',qualification)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none'})
        figures(plt,qualification['cases'],args.output)
        html_report(args.output,qualification)
        need(not any(name=='aegis_dc' or name.startswith('aegis_dc.') for name in sys.modules),'Facility code was imported')
        need(sha(args.manifest.read_bytes())==sha(raw_manifest)
             and sha(args.snapshot.read_bytes())==manifest['snapshot_sha256'],'Saved inputs changed')
        terminal.update(status='SAVED_JOINT_QUALIFICATION_AND_FIGURES_PASSED',original54_status='FAILED_RETAINED',
            cases=4,original_native_captures_reused=4,corrected_regression_test_executed=False)
    except BaseException as error:
        terminal.update(error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(finished_utc=datetime.now(timezone.utc).isoformat(),
            output_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in args.output.iterdir() if p.is_file()})
        save(args.output/'terminal.json',terminal)
    print(json.dumps(dict(status=terminal['status'],source=terminal['source'],new_facility_calls=0,new_research_trials=0)))


if __name__ == '__main__':
    main()
