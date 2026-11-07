"""Render the first registered development readout from saved report facts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0,'C:/Users/Donson/Documents/ChatGPT/Renly/.work/paper-writing-deps')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ARMS=['no_human','periodic','fifo','risk_condition_priority_adapted','one_observation_lookahead','evidence_consistent_contingent']
LABELS=['仅自动保护','到期检查','FIFO','风险／状态优先','一步观察前瞻','证据一致候选']
WORLDS=['网络可恢复','冷却改善被遮蔽','误导报告','共用路径中断','团队会合／迟到信息','安全访问中断']
BLUE,TEAL,INK,GRAY='#3156a3','#148174','#172e44','#556c7f'

def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=160,metadata={'Software':'AegisDC registered development'})
    fig.savefig(out/(name+'.svg'),metadata={'Date':None,'Creator':'AegisDC registered development'})
    plt.close(fig)

def render(data,out):
    rows={(row['world_id'],row['arm']):row for row in data['runs']}
    values=np.full((6,6),np.nan)
    for i in range(6):
        for j,arm in enumerate(ARMS):
            row=rows.get((f'development-{i+1:02}',arm))
            if row and row['status']=='COMPLETED':
                values[i,j]=row['totals']['service_deficit_time_s']
    fig,ax=plt.subplots(figsize=(12.2,6.8),facecolor='#f6f8fb')
    fig.subplots_adjust(left=.19,bottom=.18,top=.79,right=.9)
    image=ax.imshow(values,vmin=0,vmax=10,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(6),LABELS,fontsize=9)
    ax.set_yticks(range(6),WORLDS,fontsize=10)
    ax.tick_params(length=0,pad=10)
    for i in range(6):
        for j in range(6):
            value=values[i,j]
            ax.text(j,i,'缺失' if not np.isfinite(value) else f'{value:.3f}',ha='center',va='center',
                color='white' if np.isfinite(value) and value>5 else INK,fontsize=10)
    c=fig.colorbar(image,ax=ax,fraction=.028,pad=.03)
    c.set_label('关键服务缺额（秒，越低越好）',fontsize=9)
    fig.text(.055,.92,'开发评估：六种方法的实际服务结果',fontsize=22,weight='bold',color=INK)
    fig.text(.055,.855,'6 个工况 × 6 种方法 · 固定外生条件和人员权限 · 开发结果不替代独立确认',fontsize=11,color=GRAY)
    fig.text(.055,.065,'每次窗口 10 秒；数值从原始物理轨迹积分。空白或失败保留在原分母中。',fontsize=10,color=GRAY)
    save(fig,out,'31-service-by-method')
    fig,(a,b)=plt.subplots(1,2,figsize=(12.2,6.5),facecolor='#f6f8fb')
    fig.subplots_adjust(left=.21,bottom=.18,top=.77,right=.94,wspace=.35)
    for axis in (a,b):
        axis.set_yticks(range(6),WORLDS if axis is a else [])
        axis.set_ylim(5.6,-.6)
        axis.axvline(0,color='#90a5b6',lw=1)
        axis.grid(axis='x',color='#e0e8ef');axis.set_axisbelow(True)
        axis.tick_params(length=0)
    for i,pair in enumerate(data['pairs']):
        if not pair['complete']:continue
        delta=pair['delta_service_deficit_s']
        paid=pair['extra_costs']['paid_person_s']
        a.barh(i,delta,color=TEAL if delta>=0 else '#b05021',height=.5)
        b.barh(i,paid,color=BLUE,height=.5)
        a.annotate(f'{delta:+.3f}',(delta,i),xytext=(5 if delta>=0 else -5,0),
            textcoords='offset points',ha='left' if delta>=0 else 'right',va='center',fontsize=9)
        b.annotate(f'{paid:+.3f}',(paid,i),xytext=(5 if paid>=0 else -5,0),
            textcoords='offset points',ha='left' if paid>=0 else 'right',va='center',fontsize=9)
    for axis in (a,b):
        lo,hi=axis.get_xlim();pad=max(hi-lo,1)*.25
        axis.set_xlim(min(lo,-.1)-pad,max(hi,.1)+pad)
    a.set_xlabel('基线 − 候选缺额时间（秒）\n正值表示候选减少服务缺额',fontsize=10)
    b.set_xlabel('候选 − 基线付费人时（人秒）\n正值表示多花人工',fontsize=10)
    fig.text(.055,.92,'主配对：服务收益与人工代价分开看',fontsize=22,weight='bold',color=INK)
    fig.text(.055,.855,'同一条件中的一步观察前瞻与证据一致候选；保留零差异、反向结果和资源竞争',fontsize=10.5,color=GRAY)
    fig.text(.055,.052,'付费人时 = 行走 + 专业作业 + 等待；门禁／会合／排队已计入等待，不再重复加总。',fontsize=9.5,color=GRAY)
    save(fig,out,'31-paired-service-and-cost')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('data',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    font=Path('C:/Windows/Fonts/msyh.ttc')
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b9c8d4',
        'axes.labelcolor':INK,'xtick.color':GRAY,'ytick.color':INK,'svg.fonttype':'path','svg.hashsalt':'aegisdc-31'})
    data=json.loads(a.data.read_bytes())
    a.output.mkdir()
    render(data,a.output)
    manifest=dict(scope='Saved development report only; no new facility or selector calls.',
        input_sha256=sha256(a.data.read_bytes()).hexdigest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        matplotlib=matplotlib.__version__,font_sha256=sha256(font.read_bytes()).hexdigest(),
        artifacts={path.name:sha256(path.read_bytes()).hexdigest() for path in a.output.iterdir()})
    (a.output/'figure-source.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
