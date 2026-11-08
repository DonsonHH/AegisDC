"""Render two explanatory figures from committed existing records, never new runs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.work/paper-writing-deps').is_dir():
    sys.path.insert(0, str(ROOT / '.work/paper-writing-deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.path import Path as PlotPath

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
sources = {}

def read(path):
    data = subprocess.check_output(['git', 'show', args.source + ':' + path], cwd=ROOT)
    sources[path] = hashlib.sha256(data).hexdigest()
    return json.loads(data)

model = read('configs/full-facility-mainline-reserve-v6.json')
witness = read('evidence/mainline/engineering/20-action-value/capture-01/check-results.json')
font = Path('C:/Windows/Fonts/msyh.ttc')
font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family': font_manager.FontProperties(fname=str(font)).get_name(),
    'svg.fonttype': 'path', 'svg.hashsalt': 'aegisdc-mentor-report-20261108',
    'axes.spines.top': False, 'axes.spines.right': False})
navy, teal, amber, muted = '#183449', '#087f79', '#b85a24', '#526d80'

fig, ax = plt.subplots(figsize=(15, 12), facecolor='#f7fafc')
ax.set(xlim=(0, 16), ylim=(0, 13.4)); ax.axis('off')
ax.text(.2, 13.0, '供电、冷却与服务：同一模型中的设备连接', fontsize=23, color=navy, weight='bold')
ax.text(.2, 12.5, '读取V6合成场景的命名实体与边；同名节点在各分图中代表同一实体。', fontsize=12, color=muted)
positions = {}
labels = {
 'grid':'外部电源\ngrid', 'generator':'柴油后备\ngenerator',
 'main_switchboard':'主配电\nmain_switchboard','load_distribution':'负载分配\nload_distribution',
 'ups':'UPS储能\nups','rectifier':'整流/直流支路\nrectifier',
 'compute':'计算服务\ncompute','network':'网络服务\nnetwork','storage':'存储服务\nstorage',
 'lake':'湖水边界\nlake','intake_pump':'取水泵\nintake_pump','filter':'滤网\nfilter',
 'lake_valve_group':'湖侧阀组\nlake_valve_group','plate_hx':'板式换热器\nplate_hx',
 'internal_water':'内部水控制体\ninternal_water','internal_pump':'内部循环泵\ninternal_pump',
 'internal_valve_group':'内侧阀组\ninternal_valve_group','immersion':'设备/相变冷却\nimmersion',
 'backup_tower':'后备排热\nbackup_tower','reserve_external_air':'外部空气边界\nreserve_external_air'}
def node(key, x, y, w=2.12, h=.72, color=navy):
    patch=FancyBboxPatch((x-w/2,y-h/2), w,h, boxstyle='round,pad=.03,rounding_size=.09',
        facecolor='white', edgecolor=color, linewidth=1.25,zorder=3)
    positions[key] = (x, y, w, h, patch)
    ax.add_patch(patch)
    ax.text(x,y,labels[key],ha='center',va='center',fontsize=10.3,color=navy,linespacing=1.4,zorder=4)
edges = {e['id']:e for e in model['graphs']['physical']}
selected = []
def edge(edge_id, color, rad=0, label=None):
    e=edges[edge_id]; a=positions[e['from']];b=positions[e['to']]
    ax.add_patch(FancyArrowPatch((a[0],a[1]),(b[0],b[1]),arrowstyle='-|>',mutation_scale=13,
        patchA=a[4],patchB=b[4],shrinkA=3,shrinkB=3,linewidth=1.6,color=color,connectionstyle=f'arc3,rad={rad}',zorder=2))
    selected.append(edge_id)
    if label: ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.18,label,fontsize=9.5,color=color,
        ha='center',bbox=dict(facecolor='#f7fafc',edgecolor='none',pad=1))
def routed(edge_id, vertices, color):
    assert edge_id in edges
    path=PlotPath(vertices,[PlotPath.MOVETO]+[PlotPath.LINETO]*(len(vertices)-1))
    ax.add_patch(FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=13,linewidth=1.6,color=color,zorder=2))
    selected.append(edge_id)

ax.text(.2,11.8,'A  电力供应与有限后备',fontsize=16,weight='bold',color=navy)
for key,x,y in [('grid',1.25,10.7),('main_switchboard',4.05,10.7),('load_distribution',7.0,10.7),
 ('rectifier',10.0,10.7),('generator',4.05,9.2),('ups',7.0,9.2),('compute',13.3,11.65),
 ('network',13.3,10.6),('storage',13.3,9.55)]:node(key,x,y)
for eid in ['p_grid','p_normal_distribution','p_rectifier','p_compute','p_network','p_storage','p_generator']:
    edge(eid,navy)
edge('p_ups',amber,.2);edge('p_protected_distribution',amber,.2)
ax.text(.3,8.35,'UPS受保负载：本地控制、取水泵、内部循环泵。后备还受能量、维护、启动和切换条件限制。',
    fontsize=11.2,color=muted)

ax.text(.2,7.65,'B  湖侧与设备侧排热',fontsize=16,weight='bold',color=navy)
for key,x,y in [('lake',1.25,6.6),('intake_pump',4.05,6.6),('filter',7.0,6.6),
 ('lake_valve_group',10.0,6.6),('plate_hx',13.3,6.6),('internal_water',13.3,4.65),
 ('internal_pump',10.0,4.65),('internal_valve_group',7.0,4.65),('immersion',13.3,3.05),
 ('backup_tower',7.0,3.05),('reserve_external_air',4.05,3.05)]:node(key,x,y,color=teal)
for eid in ['w_intake','w_filter','w_lake_valve_feed','w_hx','w_internal_hot','w_internal_pump_valve']:
    edge(eid,teal)
routed('w_return',[(13.3,7.0),(13.3,7.24),(1.25,7.24),(1.25,7.0)],teal)
routed('w_internal_valve_hx',[(7.0,5.05),(7.0,5.55),(12.75,5.55),(12.75,6.20)],teal)
routed('w_internal_cold',[(13.85,6.20),(13.85,5.05)],teal)
edge('q_condenser',amber)
edge('q_backup_water',amber,.02)
edge('q_backup_air',amber)
ax.text(2.2,4.6,'蓝绿：介质流动\n橙色：传热/后备分支',fontsize=11,color=muted,ha='center',linespacing=1.8)
ax.text(.3,1.8,'C  关键服务的共同瓶颈',fontsize=16,weight='bold',color=navy)
ax.text(.3,1.15,'实际交付 = min（外生需求，计算能力，网络能力，存储能力）',fontsize=17,color=navy,weight='bold')
ax.text(.3,.57,'滤网清理改善流量，能否恢复服务还取决于供电、网络、存储和当地保护。行走图另行保存。',fontsize=11.2,color=muted)
fig.savefig(args.output/'mentor-facility-systems.png',dpi=170,bbox_inches='tight')
fig.savefig(args.output/'mentor-facility-systems.svg',bbox_inches='tight')
plt.close(fig)

case=next(c for c in witness['independent_cases'] if c['prior_fault']=='1/4')
alternatives=case['result']['question_values'][0]['alternatives']
assert [(a['kind'],a['expected']['service_deficit_time_s']['value'],a['expected']['person_s']['value']) for a in alternatives]==[
    ('defer',25,0),('direct_intervention',20,20),('inspect_then_act',12.5,15.5)]
names=['暂缓','直接处置','检查后按结果处置']; colors=['#8796a5',amber,teal]
fig,axs=plt.subplots(1,2,figsize=(14,5.5),facecolor='#f7fafc',gridspec_kw={'wspace':.30})
fig.suptitle('已有风险算例：检查是否值得，取决于它怎样改变后续行动',fontsize=20,color=navy,weight='bold',y=1.03)
for axis,field,title,unit in [(axs[0],'service_deficit_time_s','预测服务缺额','秒'),(axs[1],'person_s','预测人员占用','人秒')]:
    values=[a['expected'][field]['value'] for a in alternatives]
    bars=axis.barh(range(3),values,color=colors,height=.52)
    axis.set_yticks(range(3),names,fontsize=12);axis.invert_yaxis();axis.set_xlim(0,30)
    axis.set_xlabel(unit,fontsize=12,color=muted);axis.set_title(title,fontsize=16,color=navy,pad=15)
    axis.grid(axis='x',alpha=.18);axis.set_axisbelow(True)
    for y,value in enumerate(values):axis.text(value+.4,y,f'{value:g}',va='center',fontsize=13,color=navy)
fig.text(.01,-.07,'100秒评价窗，故障先验1/4；读取已封存的有限决策树结果。预测账与实际闭环效果分别评价。',fontsize=11,color=muted)
fig.savefig(args.output/'mentor-value-frozen.png',dpi=170,bbox_inches='tight')
fig.savefig(args.output/'mentor-value-frozen.svg',bbox_inches='tight')
plt.close(fig)
metadata=dict(schema='aegisdc-mentor-figures-existing-records-v1',source_commit=args.source,
    sources=sources,physical_edge_ids_in_diagram=selected,
    figure_scope='Selected actual V6 connections; full edge inventories are supplied in the report downloads.',
    finite_witness_pointer='independent_cases[prior_fault=1/4].result.question_values[0].alternatives',
    matplotlib_version=matplotlib.__version__,font_sha256=hashlib.sha256(font.read_bytes()).hexdigest(),
    new_physical_calls=0,new_selector_calls=0,new_inference_calls=0,new_research_trials=0)
(args.output/'figure-sources.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status='RENDERED_FROM_EXISTING_RECORDS',figures=2,physical_calls=0,research_trials=0)))
