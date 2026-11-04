"""Plot a verified private engineering trajectory, without policy-effect claims."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
DEPS=ROOT/'.work/paper-writing-deps'
if DEPS.is_dir():sys.path.insert(0,str(DEPS))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();folder=args.run_directory
    if args.output.exists():raise ValueError('Use a new engineering plot path')
    manifest=json.loads((folder/'run.json').read_text(encoding='utf-8'))
    if manifest['research_trials']!=0 or manifest['state_visibility']!='PRIVATE_PLANT_EVALUATOR_ONLY':
        raise ValueError('This plotter is for engineering fixtures, not registered effect studies')
    for name,record in manifest['artifacts'].items():
        if sha(folder/name)!=record['sha256']:raise ValueError('Input identity mismatch: '+name)
    trace=[json.loads(row) for row in (folder/'private-state.jsonl').read_text(encoding='utf-8').splitlines()]
    times=[row['time_s'] for row in trace]
    if not all(a<b for a,b in zip(times,times[1:])):raise ValueError('Trace times must increase')
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        fontManager.addfont(str(font));plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'svg.fonttype':'none','font.size':10,'axes.titlesize':12,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
    fig,axes=plt.subplots(3,2,figsize=(14,10),sharex=True,layout='constrained')
    def values(domain,*keys):
        output=[]
        for row in trace:
            value=row['domains'][domain]
            for key in keys:value=value[key]
            output.append(value)
        return output
    def line(ax,series,label,color,*,factor=1,step=False):
        data=[value*factor for value in series]
        if step:ax.step(times,data,where='post',label=label,color=color,lw=1.6)
        else:ax.plot(times,data,label=label,color=color,lw=1.6)
    ax=axes[0,0]
    for key,label,color in [('grid_draw_W','外电实际输入','#196b78'),('generator_output_W','发电机输出','#ae6a25'),('ups_output_W','UPS输出','#73558f')]:
        line(ax,values('power',key),label,color,factor=1e-6,step=True)
    ax.set(title='供电与后备接管',ylabel='MW');ax.legend(fontsize=8,loc='upper right')
    ax=axes[0,1];line(ax,values('it_service','demand'),'外生服务需求','#61747e',step=True);line(ax,values('it_service','delivered'),'实际交付','#167b72',step=True)
    ax.set(title='需求保留与服务缺额',ylabel='归一服务单位',ylim=(-.04,1.14));ax.legend(fontsize=8)
    ax=axes[1,0]
    for domain,keys,label,color in [
        ('equipment_environment',('solid_temperature_K',),'IT固体','#b6533d'),
        ('equipment_environment',('refrigerant','temperature_K'),'参考冷媒','#936493'),
        ('facility_cooling',('hot_temperature_K',),'热回水','#b88327'),
        ('facility_cooling',('cold_temperature_K',),'冷供水','#33889a'),
        ('equipment_environment',('room_temperature_K',),'房间','#6d7a4b')]:
        ax.plot(times,[v-273.15 for v in values(domain,*keys)],label=label,color=color,lw=1.5)
    ax.set(title='储热与热惯性',ylabel='°C');ax.legend(fontsize=8,ncol=3)
    ax=axes[1,1]
    for domain,key,label,color in [('equipment_environment','solid_coolant_heat_W','固体→冷媒','#b6533d'),('facility_cooling','condenser_heat_W','冷媒→内循环','#8b668d'),('facility_cooling','plate_hx_heat_W','内循环→湖水','#27778b')]:
        line(ax,values(domain,key),label,color,factor=1e-6)
    ax.set(title='停电后仍可能释放储热',ylabel='MW');ax.legend(fontsize=8)
    ax=axes[2,0]
    codes=values('people_tools_work','workers','worker_cooling','status')
    tools=values('people_tools_work','tools','tool_flow_meter','reserved_by')
    colors={'idle':'#d8e1e4','travelling':'#4b91a1','working':'#b88638'}
    for y,data,color_for in [(1,codes,lambda item:colors[item]),(0,tools,lambda item:'#a9824f' if item else '#d8e1e4')]:
        start=0
        for end in range(1,len(data)):
            if data[end]!=data[start]:
                ax.broken_barh([(times[start],times[end]-times[start])],(y-.28,.56),facecolors=color_for(data[start]));start=end
        if times[-1]>times[start]:ax.broken_barh([(times[start],times[-1]-times[start])],(y-.28,.56),facecolors=color_for(data[start]))
    ax.set(title='预定工程作业：移动、工作与工具占用',yticks=[0,1],yticklabels=['手持流量仪','冷却专业人员'],ylim=(-.6,1.6))
    ax.text(.02,.95,'蓝：移动；黄：工作；灰：空闲\n完成记录不表示诊断或修复',transform=ax.transAxes,va='top',fontsize=8)
    ax=axes[2,1]
    for key,label,color in [('ups_energy_J','UPS储能','#73558f'),('fuel_energy_J','发电燃料能量','#ae6a25')]:
        data=values('backup',key)
        if data[0]>0:line(ax,data,label,color,factor=1/data[0])
    ax.set(title='后备资源实际消耗',ylabel='相对初始能量',ylim=(-.02,1.04));ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.set_xlim(times[0],times[-1])
        for event in manifest['events']:
            if event['kind']=='generator_running' or (event['kind']=='exogenous_boundary_input' and event.get('parameter_id')=='grid_capacity'):
                ax.axvline(event['time_s'],color='#66757d',lw=.7,alpha=.5,ls='--')
    for ax in axes[-1,:]:ax.set_xlabel('模拟时间 / s')
    fig.suptitle('完整设施工程轨迹：外电中断、自动接管与独立作业时序\n合成研究场景 · 不是方法收益对照或现场数据',fontsize=14,fontweight='bold')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    svg=args.output.with_suffix('.svg');record_path=args.output.with_suffix('.json')
    if svg.exists() or record_path.exists():raise ValueError('Use new plot artifact paths')
    fig.savefig(args.output,dpi=160);fig.savefig(svg);plt.close(fig)
    record={'schema':'aegisdc-engineering-plot-v1','scope':'diagnostic engineering trace only','input_run_json_sha256':sha(folder/'run.json'),'input_artifact_sha256':{name:sha(folder/name) for name in manifest['artifacts']},'source_code_identity':manifest['code_identity'],'script_sha256':sha(Path(__file__)),'artifacts':{args.output.name:sha(args.output),svg.name:sha(svg)},'trace_rows':len(trace),'time_range_s':[times[0],times[-1]],'matplotlib':importlib.metadata.version('matplotlib'),'research_gain':'NOT_ESTABLISHED'}
    record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'plot':str(args.output),'source_data_identity':'PASS','trace_rows':len(trace),'purpose':'engineering'},ensure_ascii=False))


if __name__=='__main__':main()
