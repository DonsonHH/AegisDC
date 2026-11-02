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
         text(20, 70, '机柜17：原办法按固定顺序巡回检查', 21, MUTED),
         rect(a, 109, b - a, 150, SHADE),
         text((a + b) / 2, 102, '短时异常', 23, RED, 'middle', 600),
         line(65, 225, 670, 225, GREY, 3)]
    for when in [d['previous_s'], d['next_s']]:
        x = scale(when)
        p += [dot(x, 225, GREY, 9), text(x, 266, f'{when:g}秒', 27, anchor='middle', weight=600),
              text(x, 299, '检查正常', 22, MUTED, 'middle')]
    p += [text((a + b) / 2, 163, f"{d['onset_s']:g}—{d['end_s']:g}秒", 22, RED, 'middle'),
          text((a + b) / 2, 197, f"持续{d['duration_s']:g}秒", 24, RED, 'middle', 600),
          line(scale(d['previous_s']), 335, scale(d['next_s']), 335, BLUE),
          text(367, 374, f"两次检查相隔{d['gap_s']:g}秒，仍在{d['revisit_limit_s']:g}秒上限内", 26, BLUE, 'middle', 600),
          text(367, 407, '按时完成检查，仍可能错过中间的异常。', 22, MUTED, 'middle')]
    return svg('missed-gap', 735, 418, '按时巡回仍漏掉25秒异常',
               f"固定巡回在{d['previous_s']}和{d['next_s']}秒正常测量，异常发生于{d['onset_s']}至{d['end_s']}秒。灰区由事后评价取得。", p)


def architecture():
    p = ['<defs><marker id="execution-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#526675" stroke-width="1.4"/></marker></defs>',
         text(15, 36, '原来：按既定顺序循环检查（固定巡回 Tour）', 29, weight=650)]
    for x, label in [(55, '原定检查'), (355, '下一项检查'), (655, '后续检查'), (955, '下一轮巡回')]:
        p += [rect(x, 61, 227, 65, '#f2f4f6', rx=4), text(x + 113, 103, label, 27, MUTED, 'middle')]
        if x < 955:
            p.append(line(x + 236, 94, x + 290, 94, MUTED, **{'marker-end': 'url(#execution-arrow)'}))
    p += [text(15, 184, '现在：有提示就申请加查，合法事件先到先处理（FIFO）', 29, BLUE, weight=650)]
    nodes = [(15, 211, 203, '公开风险提示', '当时可见的信息'),
             (254, 211, 204, '记下待确认任务', '先提出检查请求'),
             (494, 211, 312, '核对资格与后续可行性', '加查后，原任务来得及吗？'),
             (842, 211, 183, '通过才加查', '完成一次测量'),
             (1061, 211, 204, '继续原例行任务', '原来的义务保留')]
    for i, (x, y, width, title, subtitle) in enumerate(nodes):
        p += [rect(x, y, width, 91, '#eaf2f8', rx=4), text(x + width / 2, y + 36, title, 24, BLUE, 'middle', 600),
              text(x + width / 2, y + 70, subtitle, 20, MUTED, 'middle')]
        if i < len(nodes) - 1:
            p.append(line(x + width + 4, y + 45, nodes[i + 1][0] - 9, y + 45,
                          MUTED, **{'marker-end': 'url(#execution-arrow)'}))
    p += [line(650, 303, 650, 346, MUTED), line(650, 346, 1158, 346, MUTED,
                                                         **{'marker-end': 'url(#execution-arrow)'}),
          text(897, 378, '未通过检查：继续例行巡回', 23, MUTED, 'middle')]
    return svg('execution', 1280, 395, '固定巡回与事件响应的执行架构',
               '公开线索建立待确认任务。核对资格、所属、预约、预算及后续巡回可行性，通过才额外检查，原例行义务继续保留。', p)


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
        p += [rect(x - 62, y0 - h, 124, h, color, rx=2,
                   **{'data-method': method, 'data-count': count, 'data-denominator': total}),
              text(x, y0 - h - 18, f'{count}/{total}', 43, color, 'middle', 650),
              text(x, 348, label, 25, anchor='middle', weight=600),
              text(x, 379, short, 21, MUTED, 'middle')]
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
               '纵向顺序为p00到p11，净增为FIFO确认数减Tour确认数。多条候选规则不增加独立过程数。', p)


def task_timeline(task, data):
    lo, hi = 630, 745
    scale = lambda t: 110 + (t - lo) / (hi - lo) * 495
    onset, end = data['anomaly_s']
    gained = task == '17'
    color = TEAL if gained else RED
    p = [text(18, 35, f"机柜{task}：{'新增确认' if gained else '丢失确认'}", 30, color, weight=650),
         text(18, 72, f'异常发生在{onset:g}—{end:g}秒', 22, MUTED),
         rect(scale(onset), 95, scale(end) - scale(onset), 222, SHADE),
         text(6, 150, '固定巡回', 20, MUTED), text(6, 264, '事件响应', 20, BLUE)]
    for method, y, method_color in [('tour', 160, GREY), ('fifo', 274, BLUE)]:
        p.append(line(110, y, 605, y, LINE, 3))
        measure = data[method]
        x = scale(measure['finish_s'])
        if measure['alarm']:
            p.append(dot(x, y, method_color, 9))
        else:
            p += [line(x - 7, y - 7, x + 7, y + 7, method_color, 3),
                  line(x - 7, y + 7, x + 7, y - 7, method_color, 3)]
        wording = '确认异常' if measure['alarm'] else '测量正常'
        label_y = 133 if method == 'tour' else 316
        p.append(text(x, label_y, f"{measure['finish_s']:g} {wording}", 23,
                      method_color, 'middle' if method == 'tour' or not gained else 'start', 600))
    if gained:
        d = data['fifo']
        a, b, clue = scale(d['dispatch_s']), scale(d['finish_s']), scale(d['visible_s'])
        p += [line(a, 274, b, 274, BLUE, 6), rect(a - 4, 270, 8, 8, 'white', stroke=BLUE, **{'stroke-width': 2}),
              line(clue, 217, clue, 260, GOLD, 2, **{'stroke-dasharray': '4 4'}),
              f'<path d="M{clue:g},202 l8,8 l-8,8 l-8,-8 z" fill="{GOLD}"/>',
              text(clue, 192, f"{d['visible_s']:g} 风险提示", 23, GOLD, 'middle', 600),
              text(a, 316, f"{d['dispatch_s']:g} 派出例行检查", 22, BLUE, 'end')]
    p.append(line(110, 349, 605, 349, LINE))
    for tick in [640, 680, 720]:
        p += [line(scale(tick), 349, scale(tick), 355, GREY), text(scale(tick), 382, f'{tick}秒', 20, MUTED, 'middle')]
    return svg(f'task-{task}', 640, 398, f'机柜{task}的两条策略时间线',
               f"同一过程同一巡检员，异常区间{onset}至{end}秒。"
               + ('FIFO于665秒派出的是例行检查，685秒风险才出现，690秒完成确认。' if gained else 'Tour于695秒确认，FIFO于725秒检查时已经恢复正常。'), p)


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
        'paired-net': paired_net(facts), 'task-17': task_timeline('17', facts['tasks']['17']),
        'task-21': task_timeline('21', facts['tasks']['21']),
        'completed-work': completed(), 'registered-rules': registered_rules(facts),
    }
