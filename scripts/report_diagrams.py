"""Static, editable diagrams for a self-reading report from saved evidence."""
from __future__ import annotations

from html import escape
import math
import re

from briefing_diagrams import BLUE, GOLD, GREY, INK, LINE, MUTED, RED, TEAL, dot, line, rect, svg, text


def arrow(x1, y1, x2, y2, color=MUTED, width=2):
    distance=math.hypot(x2-x1,y2-y1);ux,uy=(x2-x1)/distance,(y2-y1)/distance
    a,b=x2-8*ux,y2-8*uy
    return line(x1,y1,x2,y2,color,width)+f'<path d="M{a-5*uy:g},{b+5*ux:g} L{x2:g},{y2:g} L{a+5*uy:g},{b-5*ux:g}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def node(x, y, width, title, subtitle='', color=BLUE, height=72):
    return [rect(x, y, width, height, '#f2f6f9', rx=3),
            text(x+width/2, y+31, title, 25, color, 'middle', 600),
            text(x+width/2, y+60, subtitle, 20, MUTED, 'middle')]


def coupled_model():
    p = [text(18, 30, '供电把能量送入机柜，也约束冷却设备的可用功率', 28, BLUE, weight=650)]
    power = [(20,180,'10 kV入口','电气拓扑标签'),(250,180,'变压／380 V AC','容量、效率与损耗代理'),
             (480,200,'UPS／整流','固定转换效率代理'),(730,180,'54 V DC','机柜侧电压标签'),
             (970,270,'128个算力机柜','IT功率转化为热')]
    for i,(x,w,title,subtitle) in enumerate(power):
        p += node(x,56,w,title,subtitle)
        if i<len(power)-1:p.append(arrow(x+w+5,92,power[i+1][0]-10,92,BLUE))
    p += [text(18,190,'液冷：一次与二次循环通过CDU交换热量',28,TEAL,weight=650),
          text(18,226,'CDU是冷却液分配／换热单元；本模型每8柜为一组，共16组。',21,MUTED)]
    p += node(20,255,180,'冷却塔','设施排热端',TEAL)
    p += node(260,255,180,'一次循环泵','共享一次回路',TEAL)
    p += [rect(510,239,270,107,'#eef6f4',rx=3),text(645,269,'CDU',28,TEAL,'middle',650),
          line(645,278,645,337,TEAL),text(576,306,'一次侧',23,TEAL,'middle'),
          text(713,306,'二次侧',23,TEAL,'middle'),arrow(704,328,591,328,GOLD),
          text(645,371,'热量由二次侧传向一次侧',20,GOLD,'middle')]
    p += node(835,255,180,'二次循环泵','各组局部回路',TEAL)
    p += node(1060,255,180,'机柜冷板','设备到液体的换热',TEAL)
    p += [arrow(205,290,250,290,TEAL),arrow(445,290,500,290,TEAL),
          arrow(785,290,825,290,TEAL),arrow(1020,290,1050,290,TEAL),
          '<path d="M575,346 V405 H110 V327" fill="none" stroke="#147469" stroke-width="2"/>',
          '<path d="M1150,327 V425 H714 V346" fill="none" stroke="#147469" stroke-width="2"/>',
          text(285,398,'一次回水',20,TEAL,'middle'),text(965,418,'二次回水',20,TEAL,'middle'),
          line(1100,128,1100,246,GOLD,3),text(1120,203,'发热',21,GOLD),
          '<path d="M340,128 V155 H925 V250" fill="none" stroke="#2369a5" stroke-width="2" stroke-dasharray="5 4"/>',
          text(670,142,'辅助供电可用性影响二次泵',20,BLUE,'middle')]
    p += [text(18,483,'设备自控回路',27,TEAL,weight=650),
          text(18,518,'温度等状态',23,MUTED),arrow(183,510,250,510,TEAL)]
    p += node(265,478,465,'局部温度反馈＋指令滞后','调节二次泵、塔风机与机柜限功率',TEAL)
    p += [arrow(735,510,800,510,TEAL),text(825,518,'改变流量、排热与发热，再影响温度',23,TEAL),
          text(18,590,'计算层次：电气容量与损耗、准稳态流量、集中热容，以及局部温度反馈。',21,MUTED)]
    return svg('coupled-model',1280,615,'供电、一次／二次液冷和设备自控的耦合',
               '电气以容量和损耗代理连接10kV、380VAC、整流与54VDC机柜。冷却塔、一次泵、CDU、二次泵和冷板构成两套回路。温度反馈调节泵、风机和功率。',p)


def blend(a, b, t):
    av=[int(a[i:i+2],16) for i in (1,3,5)];bv=[int(b[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(x+(y-x)*t):02x}' for x,y in zip(av,bv))


def heatmap(frame, truth=False):
    values=frame['offline_temperature_c'] if truth else frame['public_thermal_risk']
    lo,hi=(40,75) if truth else (0,.3)
    root=RED if truth else BLUE
    title='事后设备代表温度（°C）' if truth else '巡检端的公开热风险分'
    p=[text(18,34,title,29,root,weight=650),
       text(18,67,'已有工程例，仿真时钟500秒，128个机柜',21,MUTED)]
    for pod in range(16):
        x,y=20+(pod%4)*158,90+(pod//4)*80
        p.append(text(x,y+18,f'组{pod+1:02d}',20,MUTED,weight=600))
        for local in range(8):
            rack=pod*8+local;value=values[rack]
            cx,cy=x+(local%4)*32,y+28+(local//4)*24
            t=max(0,min(1,(value-lo)/(hi-lo)))
            fill=blend('#f3f6f8' if not truth else '#fff5f2',root,t)
            p += ['<g>',f'<title>机柜{rack}：{value:.4f}{"°C；事后值" if truth else "；公开热风险分"}</title>',
                  rect(cx,cy,29,21,fill,**{'data-rack':rack,'data-value':value,'data-kind':'temperature' if truth else 'risk'})]
            if rack in [64,67,70]:
                p.append(text(cx+14.5,cy+17,rack,16,'white' if t>.6 else INK,'middle',600))
            if not truth and frame['remote_temperature_c'][rack] is not None:p.append(dot(cx+4,cy+4,INK,2))
            p.append('</g>')
    for n in range(10):p.append(rect(24+n*32,432,32,16,blend('#f3f6f8' if not truth else '#fff5f2',root,n/9)))
    for x,label in [(24,f'{lo:g}'),(184,f'{(lo+hi)/2:g}'),(344,f'{hi:g}')]:p.append(text(x,476,label,20,MUTED,'middle' if x==184 else 'start'))
    p += [text(390,446,'色标：°C' if truth else '色标：无量纲代理',20,MUTED),
          text(390,477,'模型中的设备代表温度' if truth else '黑点：32个固定温度遥测点',18,MUTED)]
    return svg('offline-heat' if truth else 'public-risk',665,500,title,
               '按16组、每组8柜画离散分布。'
               +('此图用于事后评价。' if truth else '风险分来自公开观测、测量历史与名义热平衡估计。'),p)


def dispatch_cycle():
    p=[text(18,32,'每名巡检员完成上一项检查后，再决定下一项',29,weight=650)]
    boxes=[(18,195,'先看本人的任务','原定下一项＋风险请求'),
           (260,245,'筛出当下能执行的','资格、所属、预约、期限、预算'),
           (555,290,'有合法风险请求：FIFO','选择最早进入待办的一条'),
           (895,350,'移动＋服务，完成专业测量','无论正常或告警，都更新记录')]
    for i,(x,w,title,subtitle) in enumerate(boxes):
        p += node(x,76,w,title,subtitle,height=82)
        if i<len(boxes)-1:p.append(arrow(x+w+4,116,boxes[i+1][0]-10,116))
    p += [line(383,159,383,210,MUTED),arrow(383,210,1070,210),line(1070,210,1070,159,MUTED),
          text(710,201,'没有合法风险请求：继续原定下一项',23,MUTED,'middle'),
          '<path d="M1070,159 V284 H112 V159" fill="none" stroke="#2369a5" stroke-width="2"/>',
          text(612,276,'完成后重新规划；可以继续加查，也可以回到原循环',23,BLUE,'middle'),
          text(18,333,'额外加查时保留原任务；完成原定下一项后推进。一次测量可以同时履行风险和例行义务。',22,MUTED)]
    return svg('fifo-cycle',1280,355,'FIFO在本巡检程序中的完整决策循环',
               '移动与测量持续执行。完成后在本人负责的合规请求中先到先处理；没有合法事件则继续例行。每次完成后重新筛选。',p)


def inspection_architecture():
    p=[text(18,32,'本项目巡检系统：观测、派单、执行与评价怎样连接',29,weight=650),
       text(18,66,'上方为在线闭环；公开观测经名义估计形成风险，FIFO规则保持固定。',22,MUTED)]
    boxes=[(18,'公开观测与估计','遥测＋已完成的专业测量','名义估计 → 风险提示'),
           (338,'两本任务账','原循环下一项＋风险待办','分别保留，分别推进'),
           (658,'执行边界与FIFO','资格、所属、预约、期限、预算','合法请求中按首次提示排序'),
           (978,'执行检查与更新','移动、服务、完成专业量测','测量完成后更新观测与待办')]
    for i,(x,title,first,second) in enumerate(boxes):
        p += [rect(x,92,270,117,'#f2f6f9',rx=3),text(x+135,125,title,25,BLUE,'middle',600),
              text(x+135,160,first,18,MUTED,'middle'),text(x+135,191,second,18,MUTED,'middle')]
        if i<len(boxes)-1:p.append(arrow(x+278,150,boxes[i+1][0]-10,150,BLUE))
    p += ['<path d="M1113,209 V260 H153 V218" fill="none" stroke="#2369a5" stroke-width="2"/>',
          text(620,252,'新测量进入下一轮；设备自控仍由设施模型自己的回路运行',22,BLUE,'middle'),
          text(18,326,'离线评价：将真实异常区间与执行记录对齐',26,MUTED,weight=600)]
    p += node(18,355,395,'内部状态与异常标签','供事后评分读取',GREY,height=83)
    p += node(668,355,580,'离线评分与约束审计','有效确认、等待、移动／服务成本与重访间隔',GREY,height=83)
    p += [arrow(423,397,658,397,GREY),arrow(1200,215,1110,344,GREY),
          text(1190,317,'执行记录',19,MUTED),
          text(18,488,'巡检完成专业测量，更新观测、风险待办与确认时机；离线评价汇总收益与代价。',22,MUTED)]
    return svg('inspection-architecture',1280,515,'本项目公开观测到巡检执行、反馈及离线审计的总体架构',
               '公开观测由名义估计更新风险，原例行和风险待办分账，经过资格、所属、预约、返回核算和预算检查，由固定FIFO派单。测量反馈在线观测；内部真值只与执行记录一起用于离线评分。',p)


def outcome_costs(data):
    comp=data['primary_comparisons'];thresholds=data['decision_thresholds']
    p=[text(18,32,'收益与代价：实际结果放回预先约定的探索性门槛',29,weight=650),
       text(18,66,'三个小图使用各自单位与刻度；蓝色为实际结果，金色虚线为研究决策门槛。',22,MUTED)]
    panels=[('net_confirmations',comp['net_confirmations']['mean'],thresholds['minimum_mean_net_confirmations'],5.5,
             '每过程净增确认','段／过程，越高越好','至少1段'),
            ('travel_delta_pct',comp['travel_delta_pct'],thresholds['maximum_travel_increase_pct'],5.5,
             '移动距离增加','%，越低越好','不超过5%'),
            ('completed_loss_pct',comp['completed_loss_pct'],thresholds['maximum_completion_loss_pct'],2.2,
             '完成检查量下降','%，越低越好','不超过2%')]
    for index,(key,value,threshold,maximum,title,unit,limit) in enumerate(panels):
        left=18+index*430;start=left+20;width=335;scale=lambda v:start+v/maximum*width
        p += [text(left,115,title,26,INK,weight=600),text(left,151,unit,21,MUTED),
              line(start,230,start+width,230,LINE,2),line(scale(threshold),178,scale(threshold),241,GOLD,2,**{'stroke-dasharray':'5 4'}),
              text(scale(threshold),294,limit,20,GOLD,'middle'),
              text(left,339,f'实际 {value:.2f}'+('段／过程' if index==0 else '%'),25,BLUE,weight=650)]
        if index==0:
            lo,hi=comp['net_confirmations']['percentile95']
            p += [line(scale(lo),207,scale(hi),207,BLUE,3),line(scale(lo),201,scale(lo),213,BLUE,2),
                  line(scale(hi),201,scale(hi),213,BLUE,2),dot(scale(value),207,BLUE,7)]
        else:p.append(rect(start,191,max(1,scale(value)-start),26,BLUE))
        p.append(f'<g data-cost-key="{key}" data-value="{value}" data-threshold="{threshold}"></g>')
        for tick in [0,1,2,3,4,5] if index<2 else [0,.5,1,1.5,2]:
            x=scale(tick);p += [line(x,230,x,236,GREY),text(x,259,f'{tick:g}',18,MUTED,'middle')]
    tour=data['main_costs']['tour'];fifo=data['main_costs']['fifo']
    p += [text(18,381,f"有异常过程的加权截尾等待：{tour['mean_consequence_weighted_censored_delay_s']:.2f} → {fifo['mean_consequence_weighted_censored_delay_s']:.2f}秒；资格、预约、完整重访违规均为0。",23,TEAL,weight=600),
          text(18,419,'净增点的横线为探索性95%自举区间；代价按过程求均值。金色门槛用于本次研究决策。',21,MUTED)]
    return svg('outcome-costs',1280,445,'FIFO相对固定巡回的净确认、移动代价和完成量代价',
               '每过程净增3.50段，探索性95%自举区间2.42到4.50；移动增加约0.50%，完成量下降约0.33%；门槛依次为至少1段、不超过5%、不超过2%。违规为0。',p)


def rule_expression(rule):
    expression=''
    for key,symbol in [('risk','R'),('age','A'),('extra_time','E'),('slack_difference','S')]:
        weight=rule['weights'][key]
        if not weight:continue
        sign='−' if weight<0 else '+' if expression else ''
        expression+=sign+('' if abs(weight)==1 else f'{abs(weight):g}')+symbol
    bias=rule['bias']
    if bias:expression+=('−' if bias<0 else '+' if expression else '')+f'{abs(bias):g}'
    return expression or '0'


def registered_rules(rows, baseline):
    scale=lambda value:380+value/89*800
    p=[text(18,32,'九条响应／暂缓规则：得分式与确认结果',29,weight=650),
       text(18,66,'z≥0加查，z<0先做例行任务；各行展示同12个已见过程的开发结果。',22,MUTED),
       line(scale(baseline),104,scale(baseline),555,BLUE,3,**{'stroke-dasharray':'5 4'}),
       text(scale(baseline),99,f'FIFO {baseline}段',25,BLUE,'middle',650)]
    for index,row in enumerate(rows):
        y=131+index*47;value=row['confirmed']
        expression=rule_expression(row['rule'])
        p += [text(18,y+22,f'{index+1:02d}  '+expression,22,MUTED),
              rect(scale(0),y,scale(value)-scale(0),29,'#a6b5bf',**{'data-rule-sha':row['rule_sha256'],'data-confirmed':value}),
              f'<g data-rule-expression="{escape(expression,quote=True)}" data-rule-id="{index+1:02d}"></g>',
              text(scale(value)+12,y+23,f'{value}段',22,INK,weight=600)]
    p.append(line(scale(0),567,scale(89),567,LINE))
    for tick in [0,20,40,60,70,89]:
        x=scale(tick);p += [line(x,567,x,574,GREY),text(x,603,tick,20,MUTED,'middle')]
    p.append(text(18,651,'最好候选为60段，FIFO为70段；继续保留FIFO，重点诊断风险门槛与检查时机。',22,MUTED))
    return svg('registered-rules',1280,678,'9条登记规则的确认量及FIFO70段基线',
               '九条得分式按正文定义的R、A、E、S计算，依次确认'+','.join(str(r['confirmed']) for r in rows)+'段；FIFO确认70段。',p)


def rule_diagnosis(example):
    scale=lambda t:220+(t-300)/80*1000
    interval=next(r for r in example['fifo']['intervals'] if r['task']==4)
    fifo=next(r for r in example['fifo']['measurements'] if r['task']==4 and r['alarm'])
    normal=next(r for r in example['rule_record']['measurements'] if r['task']==4 and r['time_s']>300)
    p=[text(18,32,'15秒等待规则的一次时序得失：机柜4的确认窗口',29,weight=650),
       text(18,66,'同一过程、同一巡检员的两条实际轨迹；首次选单分歧发生在260秒。',22,MUTED),
       text(18,127,'评价异常段',23,INK),rect(scale(interval['onset_s']),102,scale(interval['end_s'])-scale(interval['onset_s']),33,'#f8dfb2'),
       text((scale(interval['onset_s'])+scale(interval['end_s']))/2,94,f"{interval['onset_s']:g}—{interval['end_s']:g}秒",22,GOLD,'middle',600),
       text(18,218,'FIFO实际轨迹',23,BLUE),text(18,322,'等待规则实际轨迹',23,MUTED)]
    fifo_dispatch=next(r for r in example['fifo']['dispatches'] if r['task']==4 and r['certified_finish_s']==fifo['time_s'])
    p += [rect(scale(fifo_dispatch['time_s']),191,scale(fifo['time_s'])-scale(fifo_dispatch['time_s']),40,'#eaf2f8'),
          text((scale(fifo_dispatch['time_s'])+scale(fifo['time_s']))/2,218,'例行查4',23,BLUE,'middle',600),
          dot(scale(fifo['time_s']),211,RED,7),text(scale(fifo['time_s'])+14,213,f"{fifo['time_s']:g}秒告警，确认",22,RED,weight=600)]
    for task,label,fill in [(12,'先做例行12','#eaf2f8'),(4,'再加查4','#fff2dc')]:
        row=next(r for r in example['rule_record']['dispatches'] if r['task']==task and r['time_s']>=315)
        x,end=scale(row['time_s']),scale(row['certified_finish_s'])
        p += [rect(x,290,end-x,40,fill,stroke='white',**{'stroke-width':2}),text((x+end)/2,317,label,23,BLUE if task==12 else GOLD,'middle',600)]
    p += [dot(scale(normal['time_s']),310,GREY,7),text(scale(normal['time_s']),273,f"{normal['time_s']:g}秒正常",22,MUTED,'middle',600),
          text(scale(315),365,'315秒选择暂缓',21,MUTED,'middle'),
          line(220,390,1220,390,LINE,2)]
    for tick in [300,320,340,360,380]:
        x=scale(tick);p += [line(x,390,x,397,GREY),text(x,426,f'{tick}秒',20,MUTED,'middle')]
    p.append(text(18,473,'实际结果：FIFO在异常段内完成测量；等待规则的测量落在异常结束之后。',22,MUTED))
    p.append(f'<g data-diagnosis-case="{example["case"]}" data-anomaly-start="{interval["onset_s"]}" data-anomaly-end="{interval["end_s"]}" data-fifo-dispatch="{fifo_dispatch["time_s"]}" data-fifo-measured="{fifo["time_s"]}" data-rule-measured="{normal["time_s"]}"></g>')
    return svg('rule-diagnosis',1280,500,'规则06与FIFO对机柜4的实际检查时序',
               'FIFO300秒派出机柜4的例行检查、320秒确认；等待规则315秒先查例行12、340秒再查4、365秒测量正常。事后异常段310到335秒。',p)


def fifo_actions(fifo):
    scale=lambda t:100+(t-470)/80*1070
    p=[text(18,34,'实际执行：先加查机柜10、8，再完成原定机柜0',29,weight=650)]
    for item in fifo['actual_dispatches']:
        x=scale(item['dispatch_s']);end=scale(item['completion_s']);extra=item['extra_event_visit']
        p += [rect(x,100,end-x,75,'#fff2dc' if extra else '#eaf2f8',stroke='white',**{'stroke-width':3}),
              text((x+end)/2,144,('额外查机柜' if extra else '原定机柜')+str(item['task']),27,GOLD if extra else BLUE,'middle',650),
              text(end,86,f"{item['completion_s']:g}秒完成",22,GOLD if extra else BLUE,'end',600)]
    due=scale(fifo['routine_due_s'])
    p += [line(due,59,due,201,RED,2,**{'stroke-dasharray':'5 4'}),text(due,52,'545秒截止',22,RED,'middle',600),
          line(100,209,1170,209,GREY,2)]
    for t in [470,500,515,540,550]:p += [line(scale(t),209,scale(t),215,GREY),text(scale(t),243,f'{t}',20,MUTED,'middle')]
    p.append(text(18,286,'仿真秒数；每个色块含移动与服务。第二次加查也重新核算，原任务0最后在540秒完成。',22,MUTED))
    return svg('fifo-actions',1280,307,'巡检员0从470秒起的实际派单与完成记录',
               '10号450秒先提示，8号455秒后提示。470派10、500完成；500派8、515完成；515派原任务0、540完成，早于545截止。',p)


def paper_scores(rows):
    p=[text(18,32,'原论文内部对比：最终巡检分数越低越好',29,weight=650),
       text(18,64,'点为均值，横线为95%置信区间；两组水域场景共用原文分数刻度。',22,MUTED)]
    lo,hi=.38,.51
    for panel,key,title in [(0,'wqp','水质参数 WQP'),(1,'algae','静态藻华')]:
        x0=250+panel*510;w=400
        p.append(text(x0+w/2,104,title,25,BLUE,'middle',600))
        for i,row in enumerate(rows):
            y=150+i*65;mean=row[key]['mean'];half=row[key]['ci95_half_width']
            x=x0+(mean-lo)/(hi-lo)*w;l=x0+(mean-half-lo)/(hi-lo)*w;r=x0+(mean+half-lo)/(hi-lo)*w
            color=BLUE if row['method']=='DRL＋VAE' else GREY
            p += [line(l,y,r,y,color,3),line(l,y-6,l,y+6,color,2),line(r,y-6,r,y+6,color,2),dot(x,y,color,6),
                  text(x,y-13,f'{mean:.3f} ± {half:.4f}',19,color,'middle')]
            if panel==0:p.append(text(18,y+8,row['method'],23,INK,weight=600 if row['method']=='DRL＋VAE' else 400))
        p.append(line(x0,365,x0+w,365,GREY))
        for tick in [.38,.42,.46,.50]:
            x=x0+(tick-lo)/(hi-lo)*w
            p += [line(x,365,x,371,GREY),text(x,398,f'{tick:.2f}',20,MUTED,'middle')]
    return svg('paper-scores',1280,418,'原文表8与表9四方法的最终巡检分数',
               'DRL加VAE和Myopic构成估计器消融；Greedy作为调度器对照。两组场景共用0.38至0.51的原文分数尺度。',p)


def clean_legacy(source):
    return re.sub(r'\sdata-stage-[\w-]+="[^"]*"','',source)


def build_report_diagrams(data, inherited):
    drawings={'model':coupled_model(),'public-risk':heatmap(data['engineering']),
              'offline-temperature':heatmap(data['engineering'],True),'inspection-architecture':inspection_architecture(),
              'fifo-cycle':dispatch_cycle(),'fifo-actions':fifo_actions(data['fifo']),
              'outcome-costs':outcome_costs(data),'registered-rules':registered_rules(data['registered_rules'],data['main']['fifo']['confirmed']),
              'rule-diagnosis':rule_diagnosis(data['rule_diagnosis_example']),
              'original-paper-scores':paper_scores(data['paper_scores'])}
    for name,source in inherited.items():drawings[name]=clean_legacy(source)
    return drawings
