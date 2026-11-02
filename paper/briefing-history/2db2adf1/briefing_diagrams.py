"""Editable SVG diagrams from already-recorded briefing facts, never simulation."""
from __future__ import annotations

from html import escape

INK = '#172d3b'
MUTED = '#526675'
BLUE = '#2369a5'
TEAL = '#147469'
RED = '#b63f50'
GOLD = '#b27420'
GREY = '#7b8791'
LINE = '#dce4e9'
SHADE = '#e9edef'


def text(x, y, value, size=23, color=INK, anchor='start', weight=400, **attributes):
    attrs = ' '.join(f'{escape(k)}="{escape(str(v), quote=True)}"' for k, v in attributes.items())
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}" {attrs}>{escape(str(value))}</text>')


def line(x1, y1, x2, y2, color=LINE, width=2, **attributes):
    attrs = ' '.join(f'{k}="{v}"' for k, v in attributes.items())
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{color}" stroke-width="{width}" {attrs}/>'


def rect(x, y, w, h, fill, **attributes):
    attrs = ' '.join(f'{k}="{v}"' for k, v in attributes.items())
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}" {attrs}/>'


def dot(x, y, color, radius=7, **attributes):
    attrs = ' '.join(f'{k}="{v}"' for k, v in attributes.items())
    return f'<circle cx="{x:g}" cy="{y:g}" r="{radius}" fill="{color}" {attrs}/>'


def staged(parts, start, key, focus=None):
    focus = focus if focus is not None else [start]
    return (f'<g data-stage-from="{start}" data-stage-focus="{" ".join(map(str, focus))}" '
            f'data-stage-key="{escape(key)}">' + ''.join(parts) + '</g>')


def svg(name, width, height, title, description, parts):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'role="img" aria-labelledby="{name}-title {name}-description" data-chart="{name}">\n'
            f'<title id="{name}-title">{escape(title)}</title>\n'
            f'<desc id="{name}-description">{escape(description)}</desc>\n'
            '<style>svg text{font-family:"Microsoft YaHei","PingFang SC",sans-serif}svg{background:white}</style>\n'
            + '\n'.join(parts) + '\n</svg>\n')


def facility(facts):
    p = [text(20, 34, f"电脑里模拟的机房：{facts['racks']}个机柜", 29, weight=650)]
    for pod in range(facts['pods']):
        x, y = 20 + (pod % 4) * 117, 61 + (pod // 4) * 53
        p.append(rect(x, y, 103, 45, '#f2f6f9', rx=3))
        for within in range(facts['racks_per_pod']):
            rack = pod * facts['racks_per_pod'] + within
            p.append(rect(x + 8 + within % 4 * 23, y + 6 + within // 4 * 18,
                          17, 14, '#c5d7e6', rx=1, **{'data-rack': rack}))
    p += [text(20, 295, f"{facts['inspectors']}名仿真巡检员", 29, weight=650),
          text(20, 325, '在模拟环境里移动、完成各自的检查', 21, MUTED)]
    for agent in range(facts['inspectors']):
        x = 30 + agent * 25
        p += [dot(x, 349, BLUE, 4, **{'data-agent': agent}), rect(x - 4, 356, 8, 16, BLUE, rx=3)]
    p.append(text(20, 403, f"{facts['pods']}组，每组{facts['racks_per_pod']}个机柜。图示不代表实际通道布局。", 18, MUTED))
    return svg('facility', 500, 418, '128个机柜与18名仿真巡检执行者',
               '数量读取封存过程与人员记录，示意布局不是实测机房。', p)


def missed_gap(facts):
    d = facts['missed_gap']
    lo, hi = d['previous_s'] - 15, d['next_s'] + 15
    scale = lambda t: 65 + (t - lo) / (hi - lo) * 605
    a, b = scale(d['onset_s']), scale(d['end_s'])
    p = [text(20, 34, '一次异常完全落在两次检查之间', 29, weight=650),
         text(20, 70, '灰区由事后评价取得，执行时不能提前知道', 21, MUTED),
         line(65, 225, 670, 225, GREY, 3)]
    for step, when in [(0, d['previous_s']), (2, d['next_s'])]:
        x = scale(when)
        p.append(staged([dot(x, 225, GREY, 9),
                         text(x, 266, f'{when:g}秒', 27, anchor='middle', weight=600),
                         text(x, 299, '检查正常', 22, MUTED, 'middle')], step,
                        'gap-check-' + str(int(when)), [step, 3]))
    p.append(staged([rect(a, 109, b - a, 150, SHADE),
                     text((a + b) / 2, 102, '事后异常', 23, RED, 'middle', 600),
                     text((a + b) / 2, 163, f"{d['onset_s']:g}—{d['end_s']:g}秒", 22, RED, 'middle'),
                     text((a + b) / 2, 197, f"持续{d['duration_s']:g}秒", 24, RED, 'middle', 600)],
                    1, 'gap-abnormality', [1, 3]))
    p.append(staged([line(scale(d['previous_s']), 335, scale(d['next_s']), 335, BLUE),
                     text(367, 374, f"间隔{d['gap_s']:g}秒 ≤ {d['revisit_limit_s']:g}秒，仍漏掉{d['duration_s']:g}秒异常", 25, BLUE, 'middle', 600),
                     text(367, 407, '按时巡检与确认短时异常，需要分别评价。', 21, MUTED, 'middle')],
                    3, 'gap-conclusion'))
    return svg('missed-gap', 735, 418, '按时巡回仍漏掉25秒异常',
               '645秒正常检查，680—705秒出现25秒异常，885秒再次正常检查。灰区是事后评价，不是执行时提前知道的信息。', p)


def architecture():
    p = ['<defs><marker id="execution-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#526675" stroke-width="1.4"/></marker></defs>']
    arrow = lambda x1,y1,x2,y2: line(x1,y1,x2,y2,MUTED,**{'marker-end':'url(#execution-arrow)'})
    top = [text(20, 32, '原定巡回：A、B、C（固定巡回 Tour）', 28, weight=650)]
    for x, label in [(70,'A'),(650,'B'),(1050,'C')]:
        top += [rect(x, 58, 155, 60, '#f2f4f6', rx=4), text(x+77,99,label,30,MUTED,'middle',650)]
    top += [arrow(230,88,640,88),arrow(810,88,1040,88)]
    p.append(staged(top,0,'insertion-original',[0,2]))
    p.append(staged([text(28,171,'出现风险线索',24,GOLD,weight=600),arrow(202,163,270,163),
                     text(288,171,'待确认任务X',24,GOLD,weight=600),
                     text(288,199,'此时尚未获准派单',19,MUTED)],1,'insertion-request',[1,2]))
    p.append(staged([arrow(465,163,530,163),rect(545,137,360,72,'#eaf2f8',rx=4),
                     text(725,166,'资格、所属、预算与后续期限',23,BLUE,'middle',600),
                     text(725,196,'加查后，原任务还来得及吗？',21,MUTED,'middle'),
                     text(942,160,'未通过：保持原巡回',22,MUTED),
                     text(1062,194,'A → B → C',24,MUTED,'middle')],2,'insertion-check',[2]))
    bottom = [text(20,255,'全部检查通过，才允许插入（合法事件先到先处理，FIFO）',26,BLUE,weight=650)]
    for x,label,fill in [(70,'A','#eaf2f8'),(360,'确认X','#fff2dc'),(650,'B','#eaf2f8'),(1050,'C','#eaf2f8')]:
        bottom += [rect(x,280,155,62,fill,rx=4),text(x+77,322,label,28,BLUE,'middle',650)]
    bottom += [arrow(230,311,350,311),arrow(520,311,640,311),arrow(810,311,1040,311),
               text(638,380,'原任务A、B、C继续保留。字母仅示意顺序，不对应实验编号。',21,MUTED,'middle')]
    p.append(staged(bottom,3,'insertion-approved'))
    return svg('execution',1280,395,'加查X如何插入A、B、C之间',
               '原顺序A、B、C。风险只生成待确认X。资格、所属、预算和后续期限检查失败则保留原巡回；全部通过才可执行A、X、B、C。',p)


def confirmations(facts):
    p = [text(25, 34, '确认了多少段异常？', 29, weight=650)]
    x0, y0, height = 82, 310, 205
    total = facts['segments']
    for tick in [0, 30, 60, total]:
        y = y0 - height * tick / total
        p += [line(x0, y, 740, y), text(65, y + 7, tick, 19, MUTED, 'end')]
    for x, method, label, short, color in [(175, 'tour', '固定巡回', 'Tour', GREY),
                                          (400, 'fifo', '事件响应', 'FIFO', BLUE),
                                          (625, 'shuffled', '风险位置打乱', '', GOLD)]:
        count = facts['confirmations'][method]
        h = count / total * height
        step = {'tour': 0, 'fifo': 1, 'shuffled': 2}[method]
        p.append(staged([rect(x - 62, y0 - h, 124, h, color, rx=2,
                            **{'data-method': method, 'data-count': count, 'data-denominator': total}),
                         text(x, y0 - h - 18, f'{count}/{total}', 43, color, 'middle', 650),
                         text(x, 348, label, 25, anchor='middle', weight=600),
                         text(x, 379, short, 21, MUTED, 'middle')], step, 'bar-' + method))
    title = '、'.join(f"{name}{facts['confirmations'][method]}" for method, name in
                     [('tour', '固定巡回'), ('fifo', '事件响应'), ('shuffled', '位置打乱')]) + '段确认'
    return svg('confirmations', 765, 400, title,
               '三种方法都在同12个预定合成主过程中比较，异常分母均为89段。', p)


def paired_net(facts):
    p = [text(15, 34, '每个独立过程的净增', 27, weight=650)]
    maximum = max(row['net'] for row in facts['paired'])
    for index, row in enumerate(facts['paired']):
        y = 71 + index * 25.5
        count = row['net']
        p += [text(18, y + 6, f"过程{index + 1:02d}", 20, MUTED),
              rect(100, y - 10, count / maximum * 245, 16, TEAL, rx=2,
                   **{'data-case': row['case'], 'data-net': count}),
              text(112 + count / maximum * 245, y + 6, f'+{count}' if count else '0', 21, TEAL, weight=600)]
        if not count:
            p.append(dot(100, y - 2, GREY, 3))
    positive = sum(row['net'] > 0 for row in facts['paired'])
    zero = sum(row['net'] == 0 for row in facts['paired'])
    p.append(text(15, 397, f'{positive}个净增，{zero}个不变', 23, TEAL, weight=600))
    return svg('paired-net', 425, 418, '12个独立过程有11个净增、1个不变',
               '纵向顺序为p00到p11，净增为FIFO确认数减Tour确认数。多条候选规则不增加独立过程数。', [staged(p,3,'paired-processes')])


def execution_chain(facts):
    p = [text(18,23,'同一巡检员：任务 @ 完成秒（节选，其他访问省略）',22,weight=600),
         text(1255,23,'橙框为额外访问',20,GOLD,'end'),
         text(25,70,'共同任务',20,MUTED),rect(18,81,156,43,'#f2f4f6',rx=4),
         text(96,110,'11 @ 605',26,INK,'middle',650),
         text(220,52,'Tour',23,MUTED),text(220,154,'FIFO',23,BLUE),
         '<path d="M174,102 L205,64 H490 M174,102 L205,122 H270" fill="none" stroke="#7b8791" stroke-width="2"/>']
    for method, y in [('tour',44),('fifo',102)]:
        color = GREY if method == 'tour' else BLUE
        for item in facts['execution_chains'][method][1:]:
            task = item['task']; x = {23:280,9:500,17:720,21:1070}[task]
            extra = item['extra_event_visit']
            parts = [rect(x,y,162,40,'#fff2dc' if extra else '#f2f6f9',rx=3),
                     text(x+81,y+28,f"{task} @ {item['completion_s']:g}",25,color,'middle',600)]
            focus = [0,1] if task == 17 else [0,2] if task == 21 else [0]
            p.append(staged(parts,0,f'chain-{method}-{task}',focus))
        for x1,x2 in ([(442,490)] if method=='fifo' else []) + [(662,710),(882,932),(1005,1060)]:
            p.append(line(x1,y+20,x2,y+20,color,2))
        p.append(text(969,y+28,'…',25,MUTED,'middle'))
    return svg('execution-chain',1280,163,'任务11之后，两条执行顺序分叉',
               '同一agent1。605秒完成11。Tour关键完成9@620、17@645、21@695。FIFO加查23@635，再完成9@665、17@690，额外21@725。Tour中19@660、23@680及FIFO中19@705等访问被省略。这不是单次插入的反事实消融。',p)


def task_timeline(task, data):
    lo, hi = 630, 745
    scale = lambda t: 110 + (t - lo) / (hi - lo) * 495
    onset, end = data['anomaly_s']
    gained = task == '17'; color = TEAL if gained else RED
    p = [text(18,29,f"机柜{task}：{'新增确认（例行访问）' if gained else '丢失确认（额外访问）'}",27,color,weight=650),
         text(18,59,f'事后异常窗口 {onset:g}—{end:g}秒',20,MUTED),
         rect(scale(onset),76,scale(end)-scale(onset),166,SHADE),
         text(6,107,'Tour',21,MUTED),text(6,203,'FIFO',21,BLUE)]
    for method,y,method_color in [('tour',120,GREY),('fifo',210,BLUE)]:
        p.append(line(110,y,605,y,LINE,3))
        measure=data[method];x=scale(measure['finish_s'])
        if measure['alarm']:p.append(dot(x,y,method_color,8))
        else:p += [line(x-6,y-6,x+6,y+6,method_color,3),line(x-6,y+6,x+6,y-6,method_color,3)]
        wording='确认异常' if measure['alarm'] else '正常' if method == 'fifo' else '测量正常'
        p.append(text(x,96 if method=='tour' else 244,f"{measure['finish_s']:g} {wording}",22,method_color,
                      'middle' if method=='tour' else 'start',600))
    d=data['fifo'];a,b,clue=scale(d['dispatch_s']),scale(d['finish_s']),scale(d['visible_s'])
    p += [line(a,210,b,210,BLUE,5),rect(a-4,206,8,8,'white',stroke=BLUE,**{'stroke-width':2}),
          line(clue,164,clue,200,GOLD,2,**{'stroke-dasharray':'4 4'}),
          f'<path d="M{clue:g},150 l7,7 l-7,7 l-7,-7 z" fill="{GOLD}"/>',
          text(clue,143,f"{d['visible_s']:g} 风险提示",21,GOLD,'middle',600),
          text(a,244,f"{d['dispatch_s']:g} {'派出例行检查' if gained else '额外派单'}",21,BLUE,'end'),
          line(110,269,605,269,LINE)]
    for tick in [640,680,720]:
        p += [line(scale(tick),269,scale(tick),275,GREY),text(scale(tick),299,f'{tick}秒',19,MUTED,'middle')]
    return svg(f'task-{task}',640,310,f'机柜{task}的两条策略时间线',
               '同一过程、同一巡检员。'
               + ('FIFO于665秒派出例行检查，685秒风险才出现，690秒完成确认。' if gained else '风险650秒可见，705秒额外派单，725秒完成时710秒异常已结束。Tour695秒确认。'),
               [staged(p,1 if gained else 2,'case-task-'+task)])


def completed():
    p = []
    for i, (title, subtitle) in enumerate([
            ('机制已实现', '风险提示能触发受约束加查'),
            ('条件性证明', '既定路程与耗时下保护原任务'),
            ('实验已完成', '主比较、取舍分析与负结果'),
            ('初稿已整理', '正文、模型方程及证据附录')]):
        x = 20 + i * 320
        p += [text(x, 40, title, 31, BLUE, weight=650), line(x, 59, x + 281, 59, BLUE, 3),
              text(x, 94, subtitle, 20, MUTED)]
    return svg('completed-work', 1280, 119, '机制、条件性证明、实验、论文初稿四项成果',
               '证明适用于固定路线、确定行程和服务耗时等条件。初稿状态为导师讨论稿。', p)


def registered_rules(facts):
    scale = lambda value: 45 + value / facts['segments'] * 635
    p = [text(15, 28, '每点一条规则，横轴为确认段数', 19, MUTED),
         line(45, 119, 680, 119, LINE, 2)]
    baseline = facts['confirmations']['fifo']
    x = scale(baseline)
    p += [line(x, 47, x, 129, BLUE, 3, **{'stroke-dasharray': '5 4'}),
          text(x, 30, f'FIFO {baseline}', 28, BLUE, 'middle', 650)]
    levels = [75, 110, 55, 110, 45, 85, 55, 115, 85]
    for i, row in enumerate(facts['registered_rules']):
        p += ['<g><title>' + escape(f"规则{i + 1}：确认{row['confirmed']}段") + '</title>',
              dot(scale(row['confirmed']), levels[i], GREY, 7,
                  **{'data-rule-sha': row['rule_sha256'], 'data-confirmed': row['confirmed']}), '</g>']
    for tick in [0, 30, 60, facts['segments']]:
        p += [line(scale(tick), 119, scale(tick), 125, GREY), text(scale(tick), 153, tick, 20, MUTED, 'middle')]
    return svg('registered-rules', 725, 165, '9条登记规则确认28至60段，均少于FIFO的70段',
               '每个点是一条不同规则在相同已见过程上的总确认量。有限开发诊断不是全部规则空间的最优性判断。', p)


def build_diagrams(facts):
    return {
        'facility': facility(facts), 'missed-gap': missed_gap(facts),
        'execution': architecture(), 'confirmations': confirmations(facts),
        'paired-net': paired_net(facts), 'execution-chain': execution_chain(facts), 'task-17': task_timeline('17', facts['tasks']['17']),
        'task-21': task_timeline('21', facts['tasks']['21']),
        'completed-work': completed(), 'registered-rules': registered_rules(facts),
    }
