"""Format the already locked per-arm scores and adjudicated contrasts for readers."""
from fractions import Fraction
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
ARMS=('V','D','K','H','P')
STATE={'VERIFIED_CLOSED':'验','OPEN_UNCONFIRMED':'开','ACTION_COMPLETED_PENDING_VERIFICATION':'待核',
       'SYMPTOM_RETREATED_PENDING_VERIFICATION':'症退待核','NOT_OPENED':'未开','OPEN_ACTION_FAILED':'行动失败',
       'ACTION_REPORTED_AWAITING_WORK_ACK':'等工作回执'}
DIRECTION={'BETTER':'较低','EQUAL':'相同','WORSE':'较高','TRADEOFF':'取舍','NUMERIC_UNRESOLVED':'数值未决'}
STAGE={'inspect':'测','action':'清','recheck':'复'}


def number(x):
    if x is None:return '—'
    q=Fraction(x)
    return str(q.numerator) if q.denominator==1 else format(float(q),'.12g')


def line(cells):
    return '| '+' | '.join(str(c).replace('|','／') for c in cells)+' |'


def work_text(r):
    stages=r['actual_stages'];work=stages['work_records']
    if not work:return '无人工发行'
    reports={v['task_id']:v for v in stages['action_reports']}
    measured={v['id']:v for v in stages['arrived_portable_records']}
    acks={x['task_id']:x for x in stages['arrived_work_receipts'] if x['status'] in ('completed','aborted','rejected')}
    parts=[]
    for task in work:
        key=task['id'];kind,slot=key.split('/')[-1].split('-')
        evidence=reports.get(key) if kind=='action' else measured.get(stages['observation_binding'].get(key))
        parts.append(STAGE.get(kind,kind)+('¹' if slot!='0' else '')+' '+
            number(task['issued_at_s'])+'→'+number(task['completed_at_s'])+'/'+number((evidence or {}).get('arrived_at_s'))+'/'+number(acks.get(key,{}).get('arrived_at_s'))+
            ('' if task['status']=='completed' else ' ['+task['status']+']'))
    return ' · '.join(parts)


def context(qs):
    first=[];at=[]
    for key,q in qs.items():
        label=('槽'+key.rsplit('-',1)[-1]+' ') if len(qs)>1 else ''
        first.append(label+(number(q['first']) if q['first'] is not None else '窗内未验证'))
        at.append(label+'/'.join(STATE.get(x['state'],x['state']) for x in q['at']))
    return ' · '.join(first),' · '.join(at)


def main():
    r=json.loads((HERE/'result.json').read_bytes());pan=r['official_panel']
    rows=['# 原生首片的逐条件观测','',
          '固定次序 V（价值）、D（强直接）、K（固定核查）、H（同模型一步前瞻）、P（既有保护）。以下是本批实际保存的评分与作业记录。L 的单位为秒，U 的单位为服务单位·秒。表内全窗积分用余额口径，最多显示 12 位有效数字。精确分数、独立率积分与冻结方向在[结果原件](result.json)。',
          '', '实际阶段记为“测／清／复　发行→工作完成／读数或行动报告到达／本人工作完成回执到达”，时刻单位均为秒。开表示已开工单而未确认，待核表示行动完成后待验证，症退待核表示症状已退但当前尚待验证，验表示该时刻合法关闭。首次验证和三个当时状态分别列出。关闭差异同时查曾关闭和各指定时刻，所以一个实例可有多个关闭标记。完整的失败、未知和未执行身份保留在原件。']
    for i in range(17):
        batch=r['arms'][i*5:i*5+5];case=batch[0]['condition']
        rows+=['','## '+case,'',line(['臂','全窗 L','全窗 U','人秒','工具秒','发行费','首次验证（秒）','5／7.5／10 秒状态','实际作业与到达']),line(['---']*9)]
        for a in batch:
            if not a['score']:
                rows.append(line([a['arm'],'—','—','—','—','—','—','—',a['state']]))
                continue
            score=a['score'];first,current=context(score['questions'])
            rows.append(line([a['arm'],*[number(x) for x in score['service']['balance']],*[number(x) for x in score['resources']['balance']],first,current,work_text(a)]))
        if pan:
            c=pan['rows'][i]['contrasts']
            outcomes=[]
            for other in ('D','K','P','H'):
                q=c[other]
                if not q['comparable']:
                    outcomes.append(other+' 不可判');continue
                outcomes.append('对 '+other+' 的服务'+DIRECTION[q['physical']['direction']]+'、资源'+DIRECTION[q['resources']['direction']]+
                    ('，失去 '+str(len(q['closure']['lost']))+' 个关闭标记' if q['closure']['lost'] else '')+
                    ('，新增 '+str(len(q['closure']['gained']))+' 个关闭标记' if q['closure']['gained'] else ''))
            rows+=['','以 V 为候选，'+ ' · '.join(outcomes)+'。']
    (HERE/'per-condition.md').write_bytes(('\n'.join(rows)+'\n').encode())

if __name__=='__main__':main()
