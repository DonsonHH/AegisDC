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
    p += [text(18,190,'液冷：两套循环通过CDU换热，冷却液不直接混为一股',28,TEAL,weight=650),
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
          text(18,590,'这是合成降阶依赖图；电气暂态、真实管网和工业控制条款未被完整复建。',21,MUTED)]
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
            p += ['<g>',f'<title>机柜{rack}：{value:.4f}{"°C；事后值" if truth else "；公开风险代理，非概率"}</title>',
                  rect(cx,cy,29,21,fill,**{'data-rack':rack,'data-value':value,'data-kind':'temperature' if truth else 'risk'})]
            if rack in [64,67,70]:
                p.append(text(cx+14.5,cy+17,rack,16,'white' if t>.6 else INK,'middle',600))
            if not truth and frame['remote_temperature_c'][rack] is not None:p.append(dot(cx+4,cy+4,INK,2))
            p.append('</g>')
    for n in range(10):p.append(rect(24+n*32,432,32,16,blend('#f3f6f8' if not truth else '#fff5f2',root,n/9)))
    for x,label in [(24,f'{lo:g}'),(184,f'{(lo+hi)/2:g}'),(344,f'{hi:g}')]:p.append(text(x,476,label,20,MUTED,'middle' if x==184 else 'start'))
    p += [text(390,446,'色标：°C' if truth else '色标：无量纲代理',20,MUTED),
          text(390,477,'仿真内部值，非实测空气温度' if truth else '黑点：32个固定温度遥测点',18,MUTED)]
    return svg('offline-heat' if truth else 'public-risk',665,500,title,
               '按16组、每组8柜画离散分布，不是现场图纸或插值温度场。'
               +('此图只在仿真完成后读取，未传给在线调度。' if truth else '风险分来自当时允许读取的信息和名义估计，不是故障概率。'),p)


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
          text(18,333,'临时加查不删掉原任务；原定下一项真正完成后才继续。一次测量可以同时确认风险并完成原任务。',22,MUTED)]
    return svg('fifo-cycle',1280,355,'FIFO在本巡检程序中的完整决策循环',
               '正在移动或测量时不打断。完成后只在本执行者负责的合规请求中先到先处理；无合法事件则继续例行任务。每次完成后重新筛选，不是固定返回时间表。',p)


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
       text(18,64,'点为均值，横线为95%置信区间；横轴为原文分数刻度。此处不是本机房实验。',22,MUTED)]
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
               'DRL加VAE和Myopic的差异是估计器消融；并有Greedy对照。两组场景共用0.38至0.51的点图尺度，不能与机房确认比例直接排名。',p)


def clean_legacy(source):
    return re.sub(r'\sdata-stage-[\w-]+="[^"]*"','',source)


def build_report_diagrams(data, inherited):
    drawings={'model':coupled_model(),'public-risk':heatmap(data['engineering']),
              'offline-temperature':heatmap(data['engineering'],True),'fifo-cycle':dispatch_cycle(),
              'fifo-actions':fifo_actions(data['fifo']),'original-paper-scores':paper_scores(data['paper_scores'])}
    for name,source in inherited.items():drawings[name]=clean_legacy(source)
    return drawings
