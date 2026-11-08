"""Compose a mentor reading report from pinned, already accepted evidence only."""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--figures', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = args.output if args.output.is_absolute() else ROOT / args.output
out.mkdir(parents=True, exist_ok=False)
(out/'figures').mkdir()
sha = lambda b: hashlib.sha256(b).hexdigest()
sources = {}

def original(path):
    data = subprocess.check_output(['git','show',args.source+':'+path],cwd=ROOT)
    sources[path] = dict(sha256=sha(data), bytes=len(data))
    return data

def load(path):
    return json.loads(original(path))

source_index = {
 'S01': ('会后确认的研究要求','docs/meetings/2026-11-03-research-reset.md'),
 'S02': ('完整设施研究目标与范围','docs/MAINLINE.md'),
 'S03': ('当前V6合成设施配置','configs/full-facility-mainline-reserve-v6.json'),
 'S04': ('风险与检查价值的封存工程结果','evidence/mainline/engineering/20-action-value/capture-01/check-results.json'),
 'S05': ('证据认识与有限法则校验','evidence/mainline/engineering/18-root-acceptance/README.md'),
 'S06': ('风险情景及未识别项','evidence/mainline/engineering/19-root-acceptance/README.md'),
 'S07': ('完整设施闭环原件说明','evidence/mainline/engineering/27-root-acceptance/README.md'),
 'S08': ('实际检查时序','evidence/mainline/engineering/22-root-acceptance/README.md'),
 'S09': ('处置作用与执行边界','evidence/mainline/engineering/23-root-acceptance/README.md'),
 'S10': ('正常和完整负例','evidence/mainline/engineering/28-negative-controls/README.md'),
 'S11': ('16工况独立确认结果','evidence/mainline/research/34-paired-analysis/results.json'),
 'S12': ('8工况机制消融结果','evidence/mainline/research/35-ablation/results.json'),
 'S13': ('开发评价原件','evidence/mainline/research/31-development/results.json'),
 'S14': ('控制体及状态方程依据','docs/research/20261104/facility-cases/state-equations.md'),
 'S15': ('FEMA过程参照与设施改编','docs/research/20261103/fema-risk-framework.md'),
 'S16': ('当前进度与注册预算','docs/mainline/progress.json'),
 'S17': ('物理模型接口和服务损失定义','docs/mainline/healthy-run-model.md'),
 'S18': ('信息与处置价值的接口约定','docs/mainline/20-action-value-contract.md'),
 'S19': ('实际在线候选工程见证','docs/mainline/26-root-acceptance.md'),
 'S20': ('三案例资料与来源边界','docs/research/20261104/facility-cases/README.md'),
 'S21': ('注册协议的压缩时间与适用范围','docs/mainline/30-comparison-protocol-v1.json'),
}
for _, path in source_index.values(): original(path)
model = load(source_index['S03'][1])
value = load(source_index['S04'][1])
confirmation = load(source_index['S11'][1])
ablation = load(source_index['S12'][1])
progress = load(source_index['S16'][1])
assert len(model['domains'])==8 and len(model['entities'])==45 and len(model['parameters'])==113
assert confirmation['status']=='NO_PRACTICAL_GAIN' and confirmation['mean_service_delta_s']==0.03515625
assert ablation['completed_runs']==32 and progress['research_trials']['attempts']==164
assert progress['research_trials']['robustness']['attempts']==0
for name in ['mentor-facility-systems.png','mentor-facility-systems.svg','mentor-value-frozen.png','mentor-value-frozen.svg','figure-sources.json']:
    shutil.copyfile(args.figures/name,out/'figures'/name)

figure_specs = {
 'overview': ('evidence/mainline/research/checkpoint35/figures/35-facility-and-evaluation-architecture.png',
    '设施、证据与评价的总体架构','结构说明图。八域实际设施与调度者可用信息分开，人员作为专业执行者进入闭环。'),
 'systems': ('@mentor-facility-systems.png','供电、冷却与服务的具体连接',
    '按V6配置中的命名实体与边重新绘制主要连接。全部45个实体与91条关系可从本报告下载；各图中的同名节点为同一实体。'),
 'numerics': ('evidence/mainline/engineering/12-numerical/capture-04/figures/numerical-qualification.png',
    '已有数值见证：步长、平衡与解析比较','工程验证图。不同见证按各自冻结阶梯解释，用于检查数值实现及平衡，不是巡检收益比较。'),
 'belief': ('evidence/mainline/engineering/18-root-acceptance/figures/archived-posterior.png',
    '已有公开记录怎样改变认识','27个保存时点读取既有公开快照。阴影为声明似然变体的范围，复制与同源记录没有被当作多份独立证据。'),
 'value': ('@mentor-value-frozen.png','同一风险下，暂缓、直接处置与检查后处置的比较',
    '重绘已封存的100秒有限决策树算例，先验1/4。服务缺额与人员占用分轴呈现；它们是该法则下的预测值。'),
 'inspection': ('evidence/mainline/engineering/22-root-acceptance/figures/inspection-timing.png',
    '到场、实际工作、采样与结果到达分别计时','已有工程检查记录。调度者只能在报告到达后使用测量，不能提前取得观察结果。'),
 'intervention': ('evidence/mainline/engineering/23-root-acceptance/figures/intervention-data.png',
    '处置完成以后，设备和服务怎样实际变化','已有命名处置工程数据。滤阻、计算请求、网络容量和后备冷却命令分别受实际完成、授权和当地控制规则约束。'),
 'loop': ('evidence/mainline/engineering/27-root-acceptance/figures/27-actual-loop.png',
    '同场闭环：服务恢复、清滤完成与证据关闭','同一10秒工程轨迹：4秒自动恢复服务，6秒人工清滤完成，8.5秒恢复记录到达后关闭风险。'),
 'negative': ('evidence/mainline/engineering/28-negative-controls/figures/28-negative-service.png',
    '正常、误导提示、自动保护与来不及人工救援的已有负例','保留无收益及不能挽回的工况，检查工程闭环是否错误制造恢复。它们与注册方法比较分别记账。'),
 'primary': ('evidence/mainline/research/34-paired-analysis/figures/34-confirmation-paired-service-cost.png',
    '16个主配对的服务改善与人工代价','原图保留全部正值、反向值与零差异。服务改善按主基线缺额减候选缺额计算；人工差额单独报告。'),
 'methods': ('evidence/mainline/research/34-paired-analysis/figures/34-confirmation-all-methods.png',
    '六种方法的全部独立确认结果','每行是同一封存工况；六种方法共用初态、外生事件、测量生成机制与资源权限。动作不同会改变后续实测记录。'),
 'families': ('evidence/mainline/research/34-paired-analysis/figures/34-confirmation-family-effects.png',
    '工况族中的正向、反向与零作用','主配对在网络族反向、误导报告族有利，另外两族为零。当前数据不足以支持普遍的平均服务优势。'),
 'ablation': ('evidence/mainline/research/35-ablation/figures/35-ablation-service-cost.png',
    '非固定线索、依赖后果与团队选项的服务作用和人工代价','8个固定工况的配对有限均值。服务列为屏蔽臂缺额减完整臂缺额；人工列为完整臂减屏蔽臂。'),
 'ablation_all': ('evidence/mainline/research/35-ablation/figures/35-ablation-all-methods.png',
    '八个消融工况、四个规划视图的全量结果','四臂保留相同实际设施与执行规则，只按已注册定义屏蔽规划者获得的因素。'),
 'development': ('evidence/mainline/research/31-development/figures/31-paired-service-and-cost.png',
    '开发集的主配对与成本','36次开发运行按6个工况解释，平均改善−1/24秒；开发集与独立确认集分开呈现。'),
}
figures=[]; downloads=[]; blocks=[]; claims=[]
esc=html.escape
def inline(text):
    text=esc(str(text))
    text=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',text)
    return re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
def citations(ids):
    return '<span class="citations">'+''.join(f'<a href="#source-{s}">〔{s}〕</a>' for s in ids)+'</span>' if ids else ''
def head(level,title,anchor):blocks.append(dict(kind='heading',level=level,title=title,anchor=anchor))
def p(text,*refs):blocks.append(dict(kind='paragraph',text=text,refs=list(refs)))
def table(headers,rows,caption=None,*refs):blocks.append(dict(kind='table',headers=headers,rows=rows,caption=caption,refs=list(refs)))
def note(title,text,*refs):blocks.append(dict(kind='note',title=title,text=text,refs=list(refs)))
def eq(latex,mathml,text,*refs):blocks.append(dict(kind='equation',latex=latex,mathml=mathml,text=text,refs=list(refs)))
def figure(key):blocks.append(dict(kind='figure',key=key))
def claim(identity,text,refs):claims.append(dict(id=identity,text=text,sources=refs))
def uri(raw,mime):return 'data:'+mime+';base64,'+base64.b64encode(raw).decode()
def downloadable(name,raw,mime,label):
    downloads.append(dict(name=name,sha256=sha(raw),bytes=len(raw)))
    return f'<a class="download" download="{esc(name)}" href="{uri(raw,mime)}">{esc(label)}</a>'

head(2,'0. 导读：导师要求的研究成果是什么','guide')
p('本研究围绕一个问题展开：**固定测点覆盖有限、设施相互依赖时，如何决定哪些风险值得派专业人员去查，并通过可执行处置改善算力服务？** 研究链条从完整设施开始，经过证据与风险判断、核查和处置，最终用服务结果与运维代价评价。','S01','S02')
table(['会后确认的要求','本报告展示什么','阅读位置'],[
 ['从机柜扩大到完整设施','八域、45个实体、四类关系，以及供电与排热的具体连接','第1章'],
 ['不依赖全覆盖实时遥测','稀疏固定测点、历史与资产、人工工单、现场检查及其时标','第2章'],
 ['先模型，再科学量化风险','控制体、服务缺额、概率与后果、检查对后续行动的价值','第1、2章'],
 ['依据问题安排动态核查','暂缓、直接处置、检查后行动与人员/工具约束','第3章'],
 ['检验业务价值','服务保障、人工、行走、工具及硬约束分别计量','第4章'],
 ['凝练可解释的方法','已有闭环、正/负例、机制消融和可追溯图表','第3—5章'],
 ['再评价智能体与RSI','进入条件、已有学习研究的定位及待验证增量','第5章']
 ],'研究要求按用户会后确认口径转述；原AI纪要不作逐字发言记录。','S01')
p('现有成果包括：可运行的完整设施模型；以时点证据为输入的风险和检查价值接口；有资格、工具、时间与授权约束的实际作业闭环；以及已封存的独立比较。主要确认中，候选平均节约0.96875人秒，服务改善0.03515625秒，未达到预定0.25秒门槛。','S02','S11','S16')
figure('overview')

head(2,'1. 设施物理层：供电、排热与算力服务怎样耦合','facility')
head(3,'1.1 工程来源、研究设定与现场缺口','facility-sources')
p('主研究对象采用郑州核心节点／曙光8000的工程组织作参照，运行对象是一座命名的合成研究设施。Frontier与El Capitan资料用于比较供电、机械冷却、换热和监控层级。工程资料提供模块及接口约束，具体实例、连接和工作点由版本化场景显式声明。','S01','S20','S03')
table(['证据类别','在本研究中的作用','展示方式'],[
 ['公开工程来源','确定设施层级、系统类别和可查接口','三案例来源台账，按原来源区分设计与实际测量'],
 ['研究模型与设定','把拓扑、容量、动态和作业组织成可运行系统','V6配置、SI单位、适用范围及模型代码'],
 ['已有工程与比较结果','检验守恒、执行闭环及方法效果','已有轨迹、封存原件、独立对照与数据图'],
 ['待补现场资料','决定真实场景适用性和参数校准','实际工质、馈线/后备覆盖、水力曲线、人员与访问资料']
 ],None,'S03','S14','S20')
head(3,'1.2 八个行为域进入同一座设施','domains')
table(['域','当前模型中的对象和实际规则','可能影响'],[
 ['供配电','外部电源、主配电、整流、负载分配与容量/损耗','IT及辅机实际供电与发热'],
 ['后备能源/排热','UPS储能、柴油机燃料与启动、后备排热及切换','受保负载连续性、恢复延迟与剩余保障'],
 ['设施冷却','湖水边界、取水泵、滤网、阀组、板换、内部水与循环泵','流量、换热与蓄热'],
 ['设备冷却/房间','设备固体热容、相变参考工质、房间热量与环境门槛','温度演化、保护与作业条件'],
 ['计算/网络/存储','外生需求、实际执行能力及串联服务瓶颈','已交付服务与未服务需求'],
 ['当地控制/监测','本地采样、控制滞回、保护、稀疏测点与证据入口','自动响应与调度可见记录'],
 ['空间/访问','位置、积水/排水、门禁、访问资格与可达关系','人员能否及时到场并安全作业'],
 ['人员/工具/作业','四类专业人员、专业工具、移动、占用、会合与实际完成','可执行检查、干预时刻与付费工时']
 ],'场景含45个共享身份实体、113项参数。行为域表示当前声明规则的覆盖范围。','S03')
figure('systems')
head(3,'1.3 四种关系各自回答不同问题','relations')
table(['关系','当前边数','解决的问题'],[
 ['物理',len(model['graphs']['physical']),'电能、流体与热量从哪里进入和离开'],
 ['功能/容量/冗余',len(model['graphs']['functional']),'哪些能力与共同瓶颈决定关键服务'],
 ['控制与信息',len(model['graphs']['control_information']),'谁测量、谁控制、什么记录能到达决策者'],
 ['人员访问',len(model['graphs']['access']),'人怎样移动，何时具备进入和作业条件']
 ],'四图共用实体ID；人员行走边不会被当作供电或排热连接。','S03')
p('关键服务由共同能力约束。即使冷却流量已经恢复，网络容量仍可能限制服务；两台后备设备若共享受限馈线、泵或控制条件，也不能按台数直接认定为两条独立保障路径。','S03','S19')
head(3,'1.4 已实现模型的主干方程与量纲','equations')
eq(r'P_{out}=\eta P_{in},\quad P_{loss}=P_{in}-P_{out}',
 '<msub><mi>P</mi><mtext>out</mtext></msub><mo>=</mo><mi>η</mi><msub><mi>P</mi><mtext>in</mtext></msub><mo>，</mo><msub><mi>P</mi><mtext>loss</mtext></msub><mo>=</mo><msub><mi>P</mi><mtext>in</mtext></msub><mo>−</mo><msub><mi>P</mi><mtext>out</mtext></msub>',
 '供电和转换损耗分别记账，单位均为W。IT实际发热依据实际执行功率，不能在降载后删除外生需求。','S17')
eq(r'\Delta p=Kq^2,\quad P_{pump}=\Delta p\,q/\eta',
 '<mi>Δp</mi><mo>=</mo><mi>K</mi><msup><mi>q</mi><mn>2</mn></msup><mo>，</mo><msub><mi>P</mi><mtext>pump</mtext></msub><mo>=</mo><mfrac><mrow><mi>Δp</mi><mi>q</mi></mrow><mi>η</mi></mfrac>',
 '准稳态泵/阻力工作点：q为m³/s，Δp为Pa，K为Pa·s²/m⁶。串联阀组、滤阻和可用泵功率会改变流量；完全关闭按联锁分支处理。','S03','S17')
eq(r'\dot Q_{HX}=\varepsilon C_{min}(T_{h,in}-T_{c,in})',
 '<msub><mover><mi>Q</mi><mo>˙</mo></mover><mtext>HX</mtext></msub><mo>=</mo><mi>ε</mi><msub><mi>C</mi><mtext>min</mtext></msub><mo>(</mo><msub><mi>T</mi><mtext>h,in</mtext></msub><mo>−</mo><msub><mi>T</mi><mtext>c,in</mtext></msub><mo>)</mo>',
 '板换使用声明的ε/NTU关系。两侧热容率C的单位为W/K；一侧减去的热量进入另一侧，质量不穿壁，停流另走零流动换热分支。','S14','S17')
eq(r'\frac{dU}{dt}=\sum_{in}\dot m h-\sum_{out}\dot m h+\dot Q+P_{diss}',
 '<mfrac><mrow><mi>dU</mi></mrow><mrow><mi>dt</mi></mrow></mfrac><mo>=</mo><msub><mo>∑</mo><mtext>in</mtext></msub><mover><mi>m</mi><mo>˙</mo></mover><mi>h</mi><mo>−</mo><msub><mo>∑</mo><mtext>out</mtext></msub><mover><mi>m</mi><mo>˙</mo></mover><mi>h</mi><mo>+</mo><mover><mi>Q</mi><mo>˙</mo></mover><mo>+</mo><msub><mi>P</mi><mtext>diss</mtext></msub>',
 '控制体保存质量与内能，固体、内部水、参考工质和房间分别分账。相变性质采用冻结的R134a纯流体平衡参考；实际工程工质仍待确认。','S03','S14','S17')
eq(r's(t)=\min\{d(t),c_{compute}(t),c_{network}(t),c_{storage}(t)\}',
 '<mi>s</mi><mo>(</mo><mi>t</mi><mo>)</mo><mo>=</mo><mi>min</mi><mo>{</mo><mi>d</mi><mo>(</mo><mi>t</mi><mo>)</mo><mo>,</mo><msub><mi>c</mi><mtext>compute</mtext></msub><mo>,</mo><msub><mi>c</mi><mtext>network</mtext></msub><mo>,</mo><msub><mi>c</mi><mtext>storage</mtext></msub><mo>}</mo>',
 'd是外生服务需求，s是实际交付。共同瓶颈用同一条服务时间线累计，避免供电与冷却同时受限时重复计算同一损失。','S17')
eq(r'D_H=\int_t^{t+H} [d(u)-s(u)]/d(u)\,du\quad(d(u)>0)',
 '<msub><mi>D</mi><mi>H</mi></msub><mo>=</mo><msubsup><mo>∫</mo><mi>t</mi><mrow><mi>t</mi><mo>+</mo><mi>H</mi></mrow></msubsup><mfrac><mrow><mi>d</mi><mo>(</mo><mi>u</mi><mo>)</mo><mo>−</mo><mi>s</mi><mo>(</mo><mi>u</mi><mo>)</mo></mrow><mrow><mi>d</mi><mo>(</mo><mi>u</mi><mo>)</mo></mrow></mfrac><mi>du</mi>',
 'D为归一化服务缺额时间，单位秒；零需求时该时刻贡献为零。它与未交付的服务单位·秒分开报告。','S17')
figure('numerics')
head(3,'1.5 参数可查、可调，缺失资料单列','parameters')
p('完整配置提供每项参数的数值、SI单位、有效范围、依据类别与来源。下表是基准V6配置，给出理解模型所需的主要工作点；这些数值是合成设定或参考物性推导，现场标定仍待完成。注册比较中的时间覆盖在表后另列。','S03')
key_params=[('grid_capacity','全设施电输入容量'),('rectifier_capacity','整流容量'),('ups_energy','UPS初始储能'),('ups_output_capacity','UPS输出上限'),('diesel_capacity','柴油机输出容量'),('diesel_initial_fuel_energy','柴油机初始燃料能量'),('compute_demand_power','计算请求功率'),('network_service_capacity','名义网络能力'),('lake_volume_flow','湖侧名义流量'),('internal_volume_flow','内部名义流量'),('lake_hydraulic_resistance','湖侧聚合阻力'),('filter_resistance_multiplier','滤阻倍数'),('inspection_time','基准检查时间'),('walk_short','基准短路径时间'),('walk_long','基准长路径时间')]
param_by_id={r['id']:r for r in model['parameters']}
table(['参数','数值','单位','依据'],[[label,f"{param_by_id[key]['value']:.9g}",param_by_id[key]['unit'],'参考物性推导' if param_by_id[key]['basis']=='derived_reference' else '合成设定'] for key,label in key_params],None,'S03')
p('第4章注册比较在各输入里显式覆盖为：检查/专业作业1秒，短/长行走1/2秒；评价窗为10秒。这是用于机制比较的压缩合成时间，与上表30秒检查、60/120秒路径的基准配置分开。人秒结果仅用于这批输入内部比较，不能换算成现场巡检周期或真实节省时长。','S21')
blocks.append(dict(kind='parameters'))

head(2,'2. 证据与风险层：从已有记录形成待核查问题','evidence')
head(3,'2.1 问题从哪里来，什么信息当时能用','evidence-time')
p('风险线索可以来自资产与维护记录、人工报告和工单、已有固定测点、现场专业检查及手持仪器。固定传感器现实存在，但覆盖与可用性有限；未覆盖位置保留为未知。调度只接收当时已经到达的记录，后台故障与未来标签留在设施/评估器。','S01','S02')
table(['输入','能回答什么','必须随记录保存什么'],[
 ['资产、设计与历史','存在什么保障路径、维护下线和未关闭缺陷','版本、对象、工况及尚未核实的配置'],
 ['人工报告与工单','有人发现了什么、需要核查哪个问题','报告者来源、观察时刻、到达时刻及可信度'],
 ['稀疏固定测点','指定位置和采样时刻的局部状态','覆盖、缺测、采样/到达时间、观测模型'],
 ['专业检查与手持测量','在实际条件下能否取得指定证据','人员/工具、工作区间、采样时刻、结果到达和适用条件'],
 ['复制或传递记录','原始发现如何被转述','共同根源和复制关系，避免重复独立计数']
 ],None,'S01','S05')
figure('belief')
head(3,'2.2 风险量化需要明确情景、时间窗和后果','risk')
p('FEMA在这里提供危险源、资产、情景、影响、脆弱性和能力复盘的过程参照；设施失效概率、服务损失和检查性能由本研究另行定义。一个问题应写成“诱因—设施状态/屏障—服务后果—可核查证据—可执行处置”，再在明确时窗内计算风险。','S01','S15')
eq(r'R_H(\mathcal I_t)=\sum_s p_s(H\mid\mathcal I_t)\,\mathbb E[L\mid s,H,\mathcal I_t]',
 '<msub><mi>R</mi><mi>H</mi></msub><mo>(</mo><msub><mi>I</mi><mi>t</mi></msub><mo>)</mo><mo>=</mo><msub><mo>∑</mo><mi>s</mi></msub><msub><mi>p</mi><mi>s</mi></msub><mo>(</mo><mi>H</mi><mo>|</mo><msub><mi>I</mi><mi>t</mi></msub><mo>)</mo><mi>E</mi><mo>[</mo><mi>L</mi><mo>|</mo><mi>s</mi><mo>,</mo><mi>H</mi><mo>,</mo><msub><mi>I</mi><mi>t</mi></msub><mo>]</mo>',
 'I是当时可用信息，H是评价时间窗，s是互斥损失情景。概率与条件损失对应同一情景和时窗；服务、人员、工具与费用分别计量。','S15','S18')
p('风险接口的已有有限见证量化了指定热/供电问题，并为其他六类问题保留影响路径、条件后果界、证据缺口和专业转介。尚未识别的概率与点风险保持缺失。设施被完整建模，并不自动意味着全设施故障概率已经完成现场校准。','S06')
table(['示例问题','已有依据与待核查点','可考虑的行动'],[
 ['冷却保障是否不足','滤阻/阀组/泵与可用排热路径；查实际流量和配置','专业检查、授权清滤或申请后备冷却'],
 ['供电后备是否可用','储能、维护、启动与切换记录；查受保负载和实际状态','检查、升级、受限工况下的授权处置'],
 ['IT服务为何仍受限','计算/网络/存储共同瓶颈；查服务与网络状态','专业IT检查、恢复网络容量或调整执行请求'],
 ['能否安全进入作业','房间温度、积水、门禁、资格与当时访问证据','等待、改派、补证或升级；不以降低分数消除限制']
 ],'问题模板来自当前模型与接口，具体作业权限由实际执行器重新核查。','S03','S06','S09')

head(2,'3. 决策与执行层：检查怎样产生实际价值','decision')
head(3,'3.1 暂缓、直接处置与检查后行动共同进入比较','value')
p('风险描述可能损失多少，检查价值描述这次获得的信息能否改变后续可执行行动。比较对象同时包含暂缓、直接处置与检查后条件行动；报告延迟和行动生效之前仍继续承担服务损失。','S18')
eq(r'\mathrm{NetVOI}_j=\min_a E[L(a)\mid I]-E_{Y_j}[\min_a E[L(a)\mid I,Y_j]]-K_j',
 '<msub><mtext>NetVOI</mtext><mi>j</mi></msub><mo>=</mo><msub><mi>min</mi><mi>a</mi></msub><mi>E</mi><mo>[</mo><mi>L</mi><mo>(</mo><mi>a</mi><mo>)</mo><mo>|</mo><mi>I</mi><mo>]</mo><mo>−</mo><msub><mi>E</mi><msub><mi>Y</mi><mi>j</mi></msub></msub><mo>[</mo><msub><mi>min</mi><mi>a</mi></msub><mi>E</mi><mo>[</mo><mi>L</mi><mo>(</mo><mi>a</mi><mo>)</mo><mo>|</mo><mi>I</mi><mo>,</mo><msub><mi>Y</mi><mi>j</mi></msub><mo>]</mo><mo>]</mo><mo>−</mo><msub><mi>K</mi><mi>j</mi></msub>',
 '这是同一损失量纲内的检查净价值表达。现有接口分别报告服务、人时、工具时和研究费用的变化，不任意折算相加；每个正支持分支都须满足完整资源承诺。','S15','S18')
figure('value')
p('把该已有100秒工程法则展开：缺陷先验q=1/4，检查灵敏度为0.8、假阳性率为0.1。检查占用10秒，阳性后执行20秒处置；阳性报告概率为0.25×0.8＋0.75×0.1=0.275，阳性后缺陷概率为0.2/0.275=8/11。这里展示声明观测法则下的计算，未使用现场校准概率。','S04')
table(['潜在状态与报告','分支概率','该分支服务缺额','加权缺额'],[
 ['有缺陷、查阳性','0.25×0.8=0.20','检查10秒＋处置20秒，共30秒','6秒'],
 ['有缺陷、查阴性','0.25×0.2=0.05','未处置，100秒窗口继续受损','5秒'],
 ['无该缺陷、查阳性','0.75×0.1=0.075','不必要处置导致20秒缺额','1.5秒'],
 ['无该缺陷、查阴性','0.75×0.9=0.675','0秒','0秒']
 ],'四个分支互斥且概率和为1；这是已封存二元有限法则的演算，独立方法比较仍按第4章评价。','S04')
p('预期服务缺额为0.20×30＋0.05×100＋0.075×20=12.5秒；预期人员占用为10＋0.275×20=15.5人秒。暂缓的预期缺额为0.25×100=25秒，直接处置为20秒。因此本法则中，检查后行动相对直接处置少损失20−12.5=7.5秒，人员占用另记为15.5人秒。','S04')
table(['故障先验','暂缓：缺额 / 人时','直接处置：缺额 / 人时','检查后按结果行动：缺额 / 人时','该法则下缺额最小的选择'],[
 ['0','0秒 / 0人秒','20秒 / 20人秒','2秒 / 12人秒','暂缓'],
 ['1/4','25秒 / 0人秒','20秒 / 20人秒','12.5秒 / 15.5人秒','检查后行动'],
 ['9/10','90秒 / 0人秒','20秒 / 20人秒','39.8秒 / 24.6人秒','直接处置']
 ],'三个先验均来自既有封存工程结果。有限决策树验证计算与边界，实际设施收益由第4章独立比较评价。','S04')
head(3,'3.2 人员、工具与安全决定行动是否可执行','execution')
p('人员是电气、冷却、控制和IT专业的领域执行者。任务需满足目标绑定、专业资格、工具、路径、访问、会合、工作时间及授权；同一人或工具不能在重叠时段重复占用。实际执行到完成时再次核查安全与权限，未完成或被中止的任务不产生成功处置效果。','S03','S08','S09')
figure('inspection')
p('已有检查见证中，采样发生在实际作业期间；例如2.25秒取得的测量到2.75秒才可被调度使用。已有在线候选见证中，4秒处置完成、4.5秒反馈到达。移动、等待、检查、处置、报告延迟和验证关闭因此各有自己的时刻。','S08','S19')
table(['当前命名处置','实际改变什么','仍须保留什么'],[
 ['清理滤网','指定目标的滤阻倍数','残余阻力、工作耗时与后续真实流量'],
 ['恢复网络容量','指定网络服务能力','其他串联瓶颈、资质/授权与实际完成'],
 ['调整计算执行请求','实际执行功率及发热','外生服务需求与未服务需求'],
 ['申请后备冷却','后备命令','PLC采样、切换延迟、风机能耗和当地保护']
 ],'执行器只开放命名操作，不接受任意参数写入。','S09')
figure('intervention')
head(3,'3.3 用同场轨迹区分恢复、处置与关闭','loop')
p('同一工程轨迹同时包含负荷变化、后备维护、滤阻变化、失电、本地自动响应、工单、检查、清滤和复查。**服务在4秒恢复，清滤在6秒完成，风险在8.5秒由已到达恢复记录核验关闭。** 服务恢复有自动机制的作用，不能把全部恢复归给巡检策略。','S07')
figure('loop')
table(['从已有10秒工程轨迹复算','原运行与重放结果'],[
 ['外生需求积分','9.75 服务单位·秒'],['实际交付积分','7.75 服务单位·秒'],
 ['归一化服务缺额','2 秒'],['检查与处置工作','2 人秒'],['门禁检查','0.5 人秒'],
 ['整场能量残差','约6.82×10⁻⁶ J'],['最大质量残差','约4.55×10⁻¹³ kg']
 ],'这是一项工程闭环见证，独立方法比较的注册样本另行统计。','S07')
figure('negative')
p('正常、误导提示、自动保护已经恢复以及人工来不及救援的完整轨迹也被保留。阴性检查可以更新认识；到访、处置完成、症状消退和证据核验关闭分别记录。','S10')

head(2,'4. 独立比较层：服务收益、资源代价与机制作用','results')
head(3,'4.1 先固定比较，再读取结果','design')
table(['阶段','独立工况','方法/视图','实际运行','本报告的用途'],[
 ['开发','6','6种方法','36次','检查机制是否产生可区分选择，单列开发结果'],
 ['主要独立确认','16','6种方法','96次','按冻结主配对、门槛和成本约束评价'],
 ['机制消融','8','4种规划视图','32次','解释非固定线索、依赖后果和团队选项的作用']
 ],'每次评价窗口10秒，共164次、1640秒模拟时间。独立单位是工况，方法轨迹和逐时状态点不增加独立样本数。','S11','S12','S13','S16')
p('注册输入把专业工作设为1秒、短/长路径设为1/2秒，形成10秒压缩合成评价窗。它们与第1章基准配置、以及第3章100秒有限决策树算例分别定义；本章报告的是固定机制条件下的配对结果，不能直接解释为现场工时或真实运维周期。','S21')
p('六种方法为仅自动保护、到期检查、FIFO、风险/状态优先改编、一步观察前瞻和证据一致候选。固定主配对为最后两者。不同方法共用初态、外生扰动、观测生成机制和资源权限，后续状态与检查记录允许因实际行动而改变。','S11')
head(3,'4.2 主确认：平均省下人工，服务改善未达门槛','primary')
table(['预先规定的判据','16个确认工况的结果','解释'],[
 ['平均服务缺额至少减少0.25秒','+0.03515625秒','未达到最低收益门槛'],
 ['额外付费人时≤0.5人秒','−0.96875人秒','平均节约人工'],
 ['额外行走≤0.25人秒','−0.25人秒','未超限'],
 ['额外工具占用≤0.5工具秒','−0.609375工具秒','未超限'],
 ['至少4个首次不同选择、覆盖2个工况族','12个、3族','存在可区分的真实选择'],
 ['实际硬约束违规为0','本批未观察到违规','约束合规与方法收益分别评价']
 ],None,'S11')
note('主要确认结论：NO_PRACTICAL_GAIN','本批平均服务改善未达到注册门槛；人工成本下降是单独成立的有限设计结果。没有用节省工时替换预定的服务收益标准。','S11')
figure('primary');figure('methods')
table(['方法','平均服务缺额（秒）','平均付费人时（人秒）'],[
 ['仅自动保护','3.812500','0'],['到期检查','3.812500','1.250000'],['FIFO','3.932617','3.718750'],
 ['风险/状态优先改编','3.847656','2.687500'],['一步观察前瞻','3.847656','2.375000'],['证据一致候选','3.812500','1.406250']
 ],'服务与人员分别展示，数值为16个固定工况的均值。','S11')
p('候选的平均服务缺额与仅自动保护相同，但额外使用1.40625人秒。逐工况并不相同：相对无人工对照，候选在网络族平均少损失1.078125秒，在误导报告族平均多损失1.078125秒，其余两族为零，等权平均因此相抵。','S11')
figure('families')
p('固定主配对在网络族平均改善−0.1875秒，误导报告族+0.328125秒，其余两族为零。去掉误导报告族后，剩余12个工况平均改善−0.0625秒。全部16个配对返回，缺失值边界收缩到同一个有限均值；该边界不是总体置信区间。','S11')
head(3,'4.3 消融：哪些因素在当前用法中产生作用','mechanisms')
table(['被屏蔽的规划因素','屏蔽−完整服务缺额（秒）','完整−屏蔽人工（人秒）','本批观察'],[
 ['非固定线索','+0.073242','−1.37500','保留线索平均少损失、少用人工'],
 ['依赖后果知识','−0.014648','+5.09375','当前用法没有平均服务改善，人工更多'],
 ['团队任务选择','−0.014648','+4.15625','当前用法没有平均服务改善，人工更多']
 ],'服务列正值表示保留因素有利；人工列正值表示完整候选付出更多。','S12')
figure('ablation');figure('ablation_all')
p('非固定线索消融只从规划账删除人工报告及其复制后代；依赖消融同时屏蔽边声明和串联容量后果，是组合知识因素；团队消融删除多人候选及相应价值绑定，评价团队任务能否被选择。实际设施和执行器能力保持。上述结果约束当前方法的机制解释，并不否定真实工程依赖或专业协作。','S12')
head(3,'4.4 开发结果单列，结论保持冻结口径','development')
figure('development')
p('开发阶段6个工况的主配对平均改善−1/24秒。开发、确认与消融分别保留，未合并为更大的独立样本；候选没有根据确认结果重新调参。','S13','S16')

head(2,'5. 研究结论：已经形成什么，哪些主张仍待验证','conclusion')
p('现有工作的实质成果是：**完整设施的可计算工程对象、时点证据与风险问题接口、异质核查和授权处置闭环，以及对收益和机制的独立检验。** 这些成果把“哪里可能出问题、去查能改变什么、谁能执行、服务实际恢复多少”连到同一套可追溯记录中。','S02','S07','S11','S12')
table(['导师关切','现有成果支持的结论','当前尚缺的证据'],[
 ['模型应覆盖完整设施','八域在同场景中通过电、热、服务与作业条件发生作用','竣工拓扑、真实设备曲线和现场工况校准'],
 ['风险评估要有科学量化','给定时窗、概率对象、联合后果及观测法则时可复算','全设施现场故障率、检查性能与处置效果的标定'],
 ['巡检要有实际价值','闭环能执行；主要确认节约人工，服务改善未达门槛','预定参数/结构稳健性和更广适用域验证'],
 ['跨系统知识与协作应有解释','当前消融显示线索有作用，依赖/团队用法增加人工而无平均改善','新的、独立可检验的改进假设及其确认'],
 ['智能体和RSI应落到方法上','已有透明基线和可测瓶颈；本轮未调用LLM、未训练','第38项资格审计及后续独立技术增量比较']
 ],None,'S01','S03','S11','S12','S16')
p('会前RGB→IR、CVAE-U-Net、PPO及1080回合研究保留在原报告中，属于原固定巡回和观测条件下的证据。它们说明已有感知与学习基础；当前按需核查主线中的智能体/RSI增量仍须独立评价。','S01','S02')
note('本次交付范围','按用户本次确认，仅用现有成果完成导师阅读展示，不新增试验。研究执行仍停在第35项；第36—42项、现场校准及智能体/RSI资格与增量工作未完成。','S16')

head(2,'附录A. 现有原件、失败记录与复算入口','evidence-index')
p('注册研究共164次：开发36、确认96、消融32，全部返回，注册失败和自动重试均为0。工程调用、准备入口、分析入口、CI及审查中的原失败分别保留。它们与注册设施试验分账；本报告只读取保存结果并重新组织图文。','S16')
blocks.append(dict(kind='downloads'))
p('完整尝试账、输入冻结、实际执行源、失败与修订、图表数据和独立审查随各票原件保存。报告中的数字以冻结条件和执行记录为准，工程验证、独立方法比较和现场标定分别解释。','S02','S16')
head(2,'附录B. 来源与适用范围','sources')
blocks.append(dict(kind='sources'))

claim('facility-inventory','V6包含8域、45实体、113参数，四类关系共91边',['S03'])
claim('risk-witness','先验1/4的已有100秒法则：25/20/12.5秒缺额，0/20/15.5人秒',['S04'])
claim('closed-loop','已有同场工程见证：4秒服务恢复、6秒清滤完成、8.5秒证据关闭',['S07'])
claim('primary-outcome','16工况主要确认改善0.03515625秒，人工−0.96875人秒，NO_PRACTICAL_GAIN',['S11'])
claim('budget-no-new-trials','本报告不新增研究运行；注册总量保持164次，第36项未启动',['S16'])

def csv_bytes(headers,rows):
    f=io.StringIO(newline='');w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    return f.getvalue().encode('utf-8-sig')
download_payloads=[('V6-113参数.csv',csv_bytes(['id','value','unit','valid_range','basis','source_note'],[[r['id'],r['value'],r['unit'],json.dumps(r['valid_range']),r['basis'],r['source_note']] for r in model['parameters']]),'text/csv','下载完整113项参数'),
 ('V6-45实体.csv',csv_bytes(['id','domain','kind','label'],[[r['id'],r['domain'],r['kind'],r['label']] for r in model['entities']]),'text/csv','下载45个实体'),
 ('V6-四类关系.csv',csv_bytes(['graph','id','from','to','kind'],[[g,r['id'],r['from'],r['to'],r['kind']] for g,rows in model['graphs'].items() for r in rows]),'text/csv','下载全部91条关系'),
 ('V6-完整配置.json',original(source_index['S03'][1]),'application/json','下载完整V6配置')]
for path in ['evidence/mainline/research/34-paired-analysis/paired-worlds.csv','evidence/mainline/research/34-paired-analysis/method-summary.csv','evidence/mainline/research/35-ablation/paired-mask-effects.csv','evidence/mainline/research/35-ablation/arm-summary.csv']:
    download_payloads.append((Path(path).name,original(path),'text/csv',Path(path).name))

def render_figure(key):
    path,title,caption=figure_specs[key]
    if path.startswith('@'):
        png=(out/'figures'/path[1:]).read_bytes();svg=(out/'figures'/Path(path[1:]).with_suffix('.svg')).read_bytes()
        target='figures/'+path[1:]
    else:
        svg_sources={
            'belief':'evidence/mainline/engineering/18-beliefs/capture-01/archived-posterior.svg',
            'inspection':'evidence/mainline/engineering/22-inspections/capture-01/inspection-timing.svg',
            'intervention':'evidence/mainline/engineering/23-interventions/capture-01/intervention-data.svg',
        }
        png=original(path);svg=original(svg_sources.get(key,str(Path(path).with_suffix('.svg')).replace('\\','/')))
        target='figures/'+Path(path).name
        (out/target).write_bytes(png);(out/Path(target).with_suffix('.svg')).write_bytes(svg)
    number=len(figures)+1
    figures.append(dict(number=number,key=key,title=title,caption=caption,path=target,source_path=path,sha256=sha(png),svg_sha256=sha(svg)))
    link=downloadable(Path(target).with_suffix('.svg').name,svg,'image/svg+xml','下载矢量图')
    body=f'<figure id="figure-{key}"><h4>图{number}　{esc(title)}</h4><button class="figure-open" type="button" data-zoom aria-label="放大图{number}"><img src="{uri(png,"image/png")}" alt="{esc(title)}"></button><figcaption>{esc(caption)} {link}</figcaption></figure>'
    md=f'![图{number} {title}]({target})\n\n图{number}。{caption}\n'
    return body,md

html_blocks=[];markdown=['# 大型液冷算力设施的多系统巡检研究报告\n','导师阅读版 · 证据截止2026年11月8日 · 使用已有成果，无新增试验。\n'];toc=[]
for b in blocks:
    kind=b['kind'];h='';md=''
    if kind=='heading':
        h=f'<h{b["level"]} id="{b["anchor"]}">{esc(b["title"])}</h{b["level"]}>'
        md='#'*b['level']+' '+b['title']+'\n'
        if b['level']==2:toc.append((b['anchor'],b['title']))
    elif kind=='paragraph':h='<p>'+inline(b['text'])+citations(b['refs'])+'</p>';md=b['text']+' '+''.join('['+s+']' for s in b['refs'])+'\n'
    elif kind=='note':h='<aside class="note"><strong>'+esc(b['title'])+'</strong><p>'+inline(b['text'])+citations(b['refs'])+'</p></aside>';md='> **'+b['title']+'**：'+b['text']+'\n'
    elif kind=='equation':
        h='<div class="equation"><math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'+b['mathml']+'</math><p>'+esc(b['text'])+citations(b['refs'])+'</p></div>'
        md='$$\n'+b['latex']+'\n$$\n\n'+b['text']+'\n'
    elif kind=='table':
        h='<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+esc(str(v))+'</th>' for v in b['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(v)+'</td>' for v in row)+'</tr>' for row in b['rows'])+'</tbody></table></div>'
        if b['caption']:h+='<p class="caption">'+esc(b['caption'])+citations(b['refs'])+'</p>'
        md='| '+' | '.join(b['headers'])+' |\n| '+' | '.join('---' for _ in b['headers'])+' |\n'+''.join('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |\n' for row in b['rows'])
        if b['caption']:md+='\n'+b['caption']+'\n'
    elif kind=='figure':h,md=render_figure(b['key'])
    elif kind=='parameters':
        rows=''.join('<tr data-param><td><code>'+esc(r['id'])+'</code></td><td>'+esc(str(r['value']))+'</td><td>'+esc(r['unit'])+'</td><td>'+esc(str(r['valid_range']))+'</td><td>'+esc(r['basis'])+'</td></tr>' for r in model['parameters'])
        h='<details id="parameters-full"><summary>展开全部113项参数、范围和依据</summary><label class="search-label">筛选参数 <input id="parameter-search" type="search" placeholder="例如：flow、ups、capacity"></label><p id="parameter-count" aria-live="polite">显示113项参数</p><div class="table-scroll parameters"><table><thead><tr><th>参数ID</th><th>值</th><th>单位</th><th>范围</th><th>依据</th></tr></thead><tbody>'+rows+'</tbody></table></div></details>'
        md='完整113项参数、范围、依据见同目录 [model-parameters.csv](model-parameters.csv)。\n'
    elif kind=='downloads':
        h='<div class="downloads">'+''.join(downloadable(*a) for a in download_payloads)+'</div>'
        md='完整参数、实体、关系、主要配对及消融CSV已嵌入HTML，可离线下载。\n'
    elif kind=='sources':
        h='<ol class="source-list">';md=''
        for sid,(title,path) in source_index.items():
            h+=f'<li id="source-{sid}"><strong>{sid}　{esc(title)}</strong><span>{esc(path)}</span><small>来源提交 {args.source[:12]} · SHA-256 {sources[path]["sha256"]}</small></li>'
            md+=f'- **{sid} {title}**：`{path}`，SHA-256 `{sources[path]["sha256"]}`。\n'
        h+='</ol><p class="caption">本页原始纪要只通过去身份化的会后确认记录引用，未复制私人会议原文。图表、来源和作图脚本身份记录于 report-manifest.json。</p>'
    html_blocks.append(h);markdown.append(md)

style='''
:root{--ink:#183449;--teal:#087f79;--muted:#526d80;--line:#d9e4eb;--paper:#fff;--back:#f4f7fa}*{box-sizing:border-box}html{scroll-behavior:auto;scroll-padding-top:30px}body{margin:0;background:var(--back);color:var(--ink);font:17px/1.85 "Microsoft YaHei",system-ui,sans-serif}a{color:var(--teal);text-underline-offset:4px}button,input{font:inherit}button{cursor:pointer}header{max-width:1320px;margin:auto;padding:64px 38px 42px;border-bottom:1px solid var(--line)}.eyebrow{font-size:13px;letter-spacing:.08em;color:var(--teal);font-weight:700}h1{font-size:42px;line-height:1.45;margin:22px 0;max-width:1050px;letter-spacing:-.025em}header>p{max-width:1040px;font-size:20px;line-height:1.9}.meta{font-size:13px;color:var(--muted)}.layout{max-width:1480px;margin:auto;padding:26px 38px 70px;display:grid;grid-template-columns:210px minmax(0,1fr);gap:46px}.toc{align-self:start;position:sticky;top:24px;font-size:13px;line-height:1.8}.toc a{display:block;text-decoration:none;padding:9px 0;border-bottom:1px solid var(--line)}.toc strong{font-size:14px}.toc button{margin:24px 0;padding:9px 16px;border:0;border-radius:6px;background:var(--ink);color:white}.report{min-width:0;max-width:1150px}.report>h2{font-size:28px;line-height:1.55;margin:70px 0 26px;padding-top:18px;border-top:2px solid var(--line)}.report>h2:first-child{margin-top:14px}.report>h3{font-size:21px;line-height:1.6;margin:40px 0 18px}p{margin:16px 0 24px}code{font:13px/1.7 Consolas,monospace;overflow-wrap:anywhere}.citations{white-space:normal;font-size:11px;margin-left:4px}.citations a{text-decoration:none}.table-scroll{overflow:auto;margin:24px 0 12px;border:1px solid var(--line);border-radius:8px;background:white}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.8}th,td{padding:13px 16px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#eaf2f6;font-size:13px;white-space:nowrap}tbody tr:last-child td{border-bottom:0}.caption,figcaption{font-size:13px;color:var(--muted);line-height:1.85}.caption{margin:10px 0 26px}.equation{background:white;border-left:3px solid #92b7ba;padding:24px 22px 4px;margin:24px 0;overflow:auto}.equation math{font-size:21px;min-height:42px;white-space:nowrap}.equation p{font-size:14px;line-height:1.85}.note{padding:22px 24px;background:#edf5f4;border-left:4px solid var(--teal);margin:28px 0}.note p{margin:10px 0 0}figure{margin:36px 0;padding:24px 20px;background:white;border:1px solid var(--line);border-radius:10px;break-inside:avoid}figure h4{font-size:16px;margin:0 0 20px;line-height:1.65}figure img{display:block;width:100%;height:auto}.figure-open{padding:0;margin:0;border:0;background:transparent;display:block;width:100%}figcaption{margin-top:18px}.download{display:inline-block;padding:6px 10px;margin:4px;border:1px solid #c4d9db;border-radius:5px;font-size:12px;text-decoration:none}.downloads{margin:22px 0}details{padding:20px;border:1px solid var(--line);background:white;margin:24px 0}summary{cursor:pointer;font-weight:700;font-size:15px}.parameters{max-height:520px}.search-label{display:block;margin-top:20px;font-size:14px}input{margin-left:8px;padding:8px 12px;border:1px solid #b4c8d5;border-radius:5px;max-width:100%;font-size:14px}.source-list{padding-left:24px;font-size:13px}.source-list li{margin:18px 0}.source-list span,.source-list small{display:block;overflow-wrap:anywhere}.source-list small{color:var(--muted);font-size:11px}.source-list strong{font-size:14px}footer{max-width:1320px;margin:auto;padding:26px 38px 50px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}dialog{border:1px solid var(--line);border-radius:10px;width:96vw;max-width:1800px;height:94vh;padding:14px;overflow:auto;background:white}dialog::backdrop{background:#183449ad}dialog header{position:sticky;top:0;padding:0 0 12px;border:0;text-align:right;background:#fffffff5;z-index:2}dialog button{border:0;border-radius:6px;padding:9px 16px;background:var(--ink);color:white}dialog img{width:100%;min-width:1100px;height:auto;display:block}.mobile-links{display:none}
@media(min-width:1700px){.layout{gap:58px;grid-template-columns:215px minmax(0,1fr)}}
@media(max-width:1100px){header{padding:42px 26px 30px}.layout{display:block;padding:20px 26px}.toc{position:static;display:flex;gap:18px;overflow-x:auto;white-space:nowrap;padding:0 0 18px;border-bottom:1px solid var(--line)}.toc strong{display:none}.toc a{border:0;flex:0 0 auto;padding:5px 0}.toc button{margin:0;flex:0 0 auto;padding:4px 13px}.report{max-width:none}h1{font-size:36px}.report>h2{margin-top:52px}}
@media(max-width:600px){body{font-size:16px;line-height:1.95}header{padding:30px 20px 26px}h1{font-size:27px;line-height:1.5;margin:18px 0}header>p{font-size:17px}.layout{padding:18px 18px 45px}.report>h2{font-size:23px;line-height:1.65;margin-top:46px}.report>h3{font-size:19px;margin-top:30px}table{font-size:13px;min-width:580px}th,td{padding:10px 12px}figure{padding:14px 10px;margin:28px 0}figure h4{font-size:14px;margin-bottom:15px}figcaption{font-size:12px}.equation{padding:20px 14px 0}.equation math{font-size:19px}.note{padding:18px 16px}details{padding:15px}input{margin:10px 0 0;width:100%}footer{padding:25px 20px}.eyebrow{font-size:12px}.meta{font-size:12px}}
@media print{body{background:white;font-size:10.5pt;line-height:1.7}.layout{display:block;padding:0;max-width:none}.toc,.download,.search-label,#parameter-count,dialog{display:none}header{padding:0 0 22pt}h1{font-size:26pt}header>p{font-size:13pt}.report>h2{font-size:19pt;margin-top:28pt;break-after:avoid}.report>h3{font-size:14pt;break-after:avoid}figure{padding:8pt;margin:18pt 0;max-height:none}.table-scroll{overflow:visible}table{font-size:9pt;min-width:0}th,td{padding:7pt}.equation{break-inside:avoid}.citations{font-size:8pt}details:not([open]){display:none}.source-list{font-size:9pt}footer{padding:16pt 0}a{color:inherit}figure img{max-height:240mm;object-fit:contain}@page{size:A4;margin:17mm}}
'''
script='''
const zoom=document.getElementById('zoom');const zimg=zoom.querySelector('img');
document.querySelectorAll('[data-zoom]').forEach(b=>b.addEventListener('click',()=>{const i=b.querySelector('img');zimg.src=i.src;zimg.alt=i.alt;zoom.showModal();zoom.scrollTo(0,0)}));
document.getElementById('zoom-close').addEventListener('click',()=>zoom.close());
zoom.addEventListener('click',e=>{if(e.target===zoom)zoom.close()});
const search=document.getElementById('parameter-search');search.addEventListener('input',()=>{let n=0;const q=search.value.trim().toLowerCase();document.querySelectorAll('[data-param]').forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q);if(!r.hidden)n++});document.getElementById('parameter-count').textContent='显示'+n+'项参数'});
document.getElementById('print').addEventListener('click',()=>window.print());
'''
navigation='<nav class="toc" aria-label="报告目录"><strong>阅读目录</strong>'+''.join(f'<a href="#{anchor}">{esc(title)}</a>' for anchor,title in toc)+'<button id="print" type="button">打印 / 保存PDF</button></nav>'
document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>大型液冷算力设施的多系统巡检研究报告｜导师阅读版</title><style>'+style+'</style></head><body><header><div class="eyebrow">AEGISDC · 导师阅读版 · 2026年11月8日</div><h1>大型液冷算力设施的<br>多系统巡检研究报告</h1><p>从完整设施出发，说明风险怎样被识别、哪些问题值得检查、专业人员怎样处置，以及实际服务与人工代价如何变化。</p><div class="meta">本版重组已有模型、封存数据与图表，未新增试验。工程模型、有限算例和独立比较在正文中分别标明。</div></header><div class="layout">'+navigation+'<main class="report">'+''.join(html_blocks)+'</main></div><footer>现有成果展示 · 研究执行停在第35项 · 现场标定PENDING。原协议、失败、执行源码和研究原件保持原身份。</footer><dialog id="zoom" aria-label="图表放大"><header><button type="button" id="zoom-close">关闭大图（Esc）</button></header><img alt="放大图"></dialog><script>'+script+'</script></body></html>'
(out/'AegisDC-导师研究报告.html').write_text(document,encoding='utf-8',newline='\n')
(out/'report.md').write_text('\n'.join(markdown),encoding='utf-8',newline='\n')
(out/'model-parameters.csv').write_bytes(download_payloads[0][1])
(out/'claims.json').write_text(json.dumps(claims,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
manifest=dict(schema='aegisdc-mentor-reading-report-v1',source_commit=args.source,as_of='2026-11-08',
    audience='导师和用户自行阅读',scope='Existing evidence presentation only; no new experiments.',
    source_files=sources,source_index={k:dict(title=v[0],path=v[1]) for k,v in source_index.items()},
    figures=figures,downloads=downloads,html_sha256=sha(document.encode()),
    authoring_sha256=sha(Path(__file__).read_bytes()),
    figure_authoring_sha256=sha((ROOT/'scripts/render_mentor_report_figures.py').read_bytes()),
    registered_runs_before=164,registered_runs_after=164,new_physical_calls=0,new_selector_calls=0,
    new_inference_calls=0,new_research_trials=0,field_calibration='PENDING',full_research_goal='INCOMPLETE')
(out/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status='BUILT_EXISTING_RESEARCH_MENTOR_REPORT',figures=len(figures),downloads=len(downloads),sources=len(sources),html_bytes=len(document.encode()),new_trials=0)))
