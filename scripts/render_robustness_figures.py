"""Draw the saved finite robustness contrasts; never run a model."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
raw=a.input.read_bytes();data=json.loads(raw);a.output.mkdir(parents=True,exist_ok=False)
font_path=Path('C:/Windows/Fonts/msyh.ttc');font=FontProperties(fname=str(font_path))
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':11,'svg.fonttype':'path'})
labels=[{'load-level':'负荷','sensor-coverage':'固定测点','reserve-path':'有效备用','model-error':'预测误差'}[r['family']]+'\n'+('参照' if r['level']=='reference' else '变体') for r in data['paired']]
fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
colors=['#2563eb' if i%2==0 else '#c77d14' for i in range(8)]
for ax,key,title,unit in [(axes[0],'delta_service_s','服务缺额改善：参照方法 − 候选','秒'),(axes[1],'extra_paid_person_s','人工代价差：候选 − 参照方法','人秒')]:
    values=[r[key] for r in data['paired']];ax.bar(range(8),values,color=colors,width=.65);ax.axhline(0,color='#334155',linewidth=.8)
    ax.set_title(title,fontproperties=font,loc='left');ax.set_ylabel(unit,fontproperties=font);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    span=max(max(map(abs,values)),.05)
    for i,v in enumerate(values):ax.text(i,v+(span*.03 if v>=0 else -span*.03),f'{v:+.4f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=9)
axes[0].text(.99,.95,'正值表示服务改善',fontproperties=font,transform=axes[0].transAxes,ha='right',va='top',fontsize=9)
axes[1].text(.99,.95,'负值表示人工减少',fontproperties=font,transform=axes[1].transAxes,ha='right',va='top',fontsize=9)
axes[1].set_xticks(range(8),labels,fontproperties=font)
fig.suptitle('四组预定稳健性对照 · 8 工况 / 16 次运行',fontproperties=font,fontsize=15)
fig.savefig(a.output/'36-robustness-service-cost.svg');fig.savefig(a.output/'36-robustness-service-cost.png',dpi=190);plt.close(fig)
files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.output.iterdir()}
(a.output/'manifest.json').write_text(json.dumps({'input_sha256':hashlib.sha256(raw).hexdigest(),'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__,'font_sha256':hashlib.sha256(font_path.read_bytes()).hexdigest(),'artifacts':files,'new_model_calls':0},indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'status':'RENDERED_FROM_SAVED_DATA','figures':2,'new_model_calls':0}))
