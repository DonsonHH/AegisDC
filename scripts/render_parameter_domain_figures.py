"""Render ticket 29 figures from the frozen table and saved engineering data."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MultipleLocator

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'evidence/mainline/engineering/29-uncertainty-domain'
TABLE = ROOT / 'configs/materials/reference-r134a-saturation.json'
CAPTURE = PACKAGE / 'capture-01'
LABELS = {
    'nominal':'基准',
    'cooler-light-demand':'低温 · 轻负荷',
    'warm-restricted-intake':'高温 · 取水受限',
    'shared-path-loss':'共用供电路径中断',
    'capacity-limited':'供电容量受限',
    'wet-access-slow-work':'积水 · 访问受限',
    'local-sensor-loss':'本地流量测点失效',
    'coupled-adverse':'多因素叠加',
}
INK, GRAY, BLUE, TEAL, ORANGE = '#172e44','#566a7c','#3156a3','#148174','#b05021'


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def page(width, height, title, subtitle):
    fig = plt.figure(figsize=(width,height), facecolor='#f6f8fb')
    fig.text(.055,.925,title,fontsize=22,weight='bold',color=INK)
    fig.text(.055,.867,subtitle,fontsize=10.5,color=GRAY)
    return fig


def phase_figure(prepared):
    table = read(TABLE)['rows']
    p = [r['p_Pa']/1e6 for r in table]
    reference = prepared['nominal']['scenario']
    params = {r['id']:r for r in reference['parameters']}
    volume = params['coolant_control_volume']['value']
    low, high = params['coolant_inventory']['valid_range']
    lower = [volume/r['v_v_m3_kg'] for r in table]
    upper = [volume/r['v_l_m3_kg'] for r in table]
    fig = page(10.5,5.55,'冷媒质量与饱和压力的联合约束','固定容积 6.647 m³ · 用冻结物性表作几何筛查')
    ax = fig.add_axes([.10,.205,.83,.59],facecolor='white')
    ax.fill_between(p,low,high,color='#f5e5dc',label='单项质量范围内，可能不满足两相几何')
    ax.fill_between(p,[max(low,x) for x in lower],[min(high,x) for x in upper],
                    color='#d6ede8',label='同时满足液/汽比容边界')
    ax.plot(p,lower,color=TEAL,lw=2,label='饱和蒸气侧质量下界')
    positions = {
        'cooler-light-demand':(-57,-33),
        'nominal':(-66,33),
        'warm-restricted-intake':(53,1),
    }
    for case,offset in positions.items():
        phase = prepared[case]['initialization']['phase']
        x,y = phase['pressure_Pa']/1e6,phase['mass_kg']
        ax.scatter(x,y,s=59,color=BLUE,edgecolors='white',linewidth=1.25,zorder=4)
        ax.annotate(f"{y:,.0f} kg · {x:.3f} MPa",(x,y),xytext=offset,textcoords='offset points',
                    fontsize=9,color=BLUE,arrowprops=dict(arrowstyle='-',color=BLUE,lw=.7))
    ax.scatter(3,500,s=74,marker='x',color=ORANGE,lw=2,zorder=4)
    ax.annotate('拒绝：500 kg / 3 MPa',(3,500),xytext=(-134,15),textcoords='offset points',
                fontsize=9,color=ORANGE,arrowprops=dict(arrowstyle='-',color=ORANGE,lw=.7))
    ax.set(xlim=(.08,3.10),ylim=(360,5200),xlabel='饱和压力（MPa）',ylabel='冷媒质量（kg）')
    ax.yaxis.set_major_locator(MultipleLocator(1000))
    ax.grid(axis='y',color='#e2e8ef')
    ax.set_axisbelow(True)
    ax.legend(loc='upper left',ncol=1,frameon=True,facecolor='white',fontsize=8.5,framealpha=.94)
    fig.text(.055,.067,'色带只表示几何条件。蓝点通过质量、能量、容积联合初态检查；实际运行资格另行核验。',color=GRAY,fontsize=9.4)
    return fig


def service_figure(rows):
    ids = list(rows)
    ordered = [rows[k] for k in ids]
    positions = range(len(ordered))
    offered = [r['offered_service_unit_s'] for r in ordered]
    delivered = [r['delivered_service_unit_s'] for r in ordered]
    deficit = [r['deficit_time_s'] for r in ordered]
    fig = page(12,6.3,'八个工程工况的实际服务结果','33 秒仿真 · 需求保持外生 · 结果仅用于有限工程核验')
    ax = fig.add_axes([.175,.192,.47,.585],facecolor='white')
    bx = fig.add_axes([.735,.192,.205,.585],facecolor='white')
    ax.barh(positions,delivered,height=.55,color=TEAL,label='实际交付')
    ax.barh(positions,[max(0,a-b) for a,b in zip(offered,delivered,strict=True)],left=delivered,
            height=.55,color='#e4b8a1',label='未交付需求')
    bx.barh(positions,deficit,height=.55,color=BLUE)
    for i,(a,b) in enumerate(zip(offered,deficit,strict=True)):
        ax.text(a+.09,i,f'{a:.3f}'.rstrip('0').rstrip('.'),va='center',fontsize=8.8,color=GRAY)
        bx.text(b+.08,i,f'{b:.2f}'.rstrip('0').rstrip('.'),va='center',fontsize=8.8,color=GRAY)
    ax.set_yticks(list(positions),[LABELS[k] for k in ids])
    bx.set_yticks([])
    ax.set(xlim=(0,7),xlabel='服务量积分（服务单位·秒）',ylim=(len(ids)-.5,-.5))
    bx.set(xlim=(0,4.4),xlabel='归一化服务缺额时间（秒）',ylim=(len(ids)-.5,-.5))
    for axis in (ax,bx):
        axis.grid(axis='x',color='#e2e8ef')
        axis.set_axisbelow(True)
        axis.tick_params(length=0)
    ax.legend(loc='upper left',bbox_to_anchor=(0,1.13),frameon=False,ncol=2,fontsize=9.5)
    fig.text(.055,.064,'右图按每刻未交付需求的比例积分。积水案例关闭访问，但关键服务仍完全交付。',color=GRAY,fontsize=9.4)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--font',type=Path,required=True)
    args = parser.parse_args()
    receipt = read(CAPTURE/'receipt.json')
    checks = CAPTURE/'checks.json'
    prepared_files = {name:PACKAGE/'prepared-01/cases'/f'{name}.json' for name in LABELS}
    assert receipt['status']=='PASS' and receipt['pinned']['inputs'][TABLE.relative_to(ROOT).as_posix()]==digest(TABLE)
    assert receipt['artifacts']['checks.json']==digest(checks)
    for path in prepared_files.values():
        assert receipt['pinned']['inputs'][path.relative_to(ROOT).as_posix()]==digest(path)
    font_manager.fontManager.addfont(str(args.font))
    font_name = font_manager.FontProperties(fname=str(args.font)).get_name()
    plt.rcParams.update({'font.family':font_name,'axes.spines.top':False,'axes.spines.right':False,
        'axes.edgecolor':'#aebcc9','axes.labelcolor':INK,'xtick.color':GRAY,'ytick.color':INK,
        'svg.fonttype':'path','svg.hashsalt':'aegisdc-domain-29'})
    output = args.output
    output.mkdir()
    figures = [('29-phase-geometry',phase_figure({k:read(p) for k,p in prepared_files.items()})),
               ('29-service-by-case',service_figure(read(checks)))]
    for name,fig in figures:
        fig.savefig(output/f'{name}.png',dpi=165,metadata={'Software':'AegisDC ticket 29'})
        fig.savefig(output/f'{name}.svg',metadata={'Date':None,'Creator':'AegisDC ticket 29'})
        plt.close(fig)
    paths = [TABLE,checks,CAPTURE/'receipt.json',*prepared_files.values()]
    manifest = {
        'capture_execution':receipt['execution_commit'],
        'renderer_checkout':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'renderer_sha256':digest(Path(__file__)),
        'matplotlib':matplotlib.__version__, 'font':font_name, 'font_sha256':digest(args.font),
        'inputs':{p.relative_to(ROOT).as_posix():digest(p) for p in paths},
        'artifacts':{p.name:digest(p) for p in sorted(output.iterdir())},
        'scope':'Figure authoring from saved engineering inputs and originals. No facility or policy calls.',
    }
    with (output/'figure-source.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(manifest,f,indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
