"""Engineering EOS reference preparation, not a facility experiment or runner."""
from __future__ import annotations
import bisect
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'coolprop-deps'))
import CoolProp
import CoolProp.CoolProp as CP
import numpy

assert CoolProp.__version__=='8.0.0'
CP.set_reference_state('R134a','DEF')
FLUID='R134a'; PMIN=100000.0; PMAX=3000000.0; COUNT=512
THRESHOLDS={
 'raw_h_u_identity_abs_J_kg':1e-6,
 'interpolated_temperature_abs_K':0.01,
 'interpolated_property_max_relative':5e-4,
 'inverse_pressure_relative':1e-3,
 'inverse_temperature_abs_K':0.03,
 'inverse_quality_abs':5e-4,
 'external_flash_pressure_relative':1e-8,
 'external_flash_temperature_abs_K':1e-6,
 'external_flash_quality_abs':1e-8,
}
AS=CP.AbstractState('HEOS',FLUID)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def saturation(p):
    result={'p_Pa':float(p)}
    for q,side in [(0.0,'l'),(1.0,'v')]:
        AS.update(CP.PQ_INPUTS,p,q)
        result['T_'+side+'_K']=AS.T()
        result['rho_'+side+'_kg_m3']=AS.rhomass()
        result['u_'+side+'_J_kg']=AS.umass()
        result['h_'+side+'_J_kg']=AS.hmass()
        result['v_'+side+'_m3_kg']=1/AS.rhomass()
    result['T_sat_K']=result.pop('T_l_K')
    result['T_vapor_sat_K']=result.pop('T_v_K')
    return result

pressures=[math.exp(math.log(PMIN)+i*math.log(PMAX/PMIN)/(COUNT-1)) for i in range(COUNT)]
pressures[0]=PMIN;pressures[-1]=PMAX
rows=[saturation(p) for p in pressures]
logs=[math.log(p) for p in pressures]
primitive=['T_sat_K','v_l_m3_kg','v_v_m3_kg','u_l_J_kg','u_v_J_kg']

def interpolated(p):
    if not math.isfinite(p) or not PMIN<=p<=PMAX:raise ValueError('Pressure outside declared interpolation domain')
    index=min(COUNT-2,max(0,bisect.bisect_right(logs,math.log(p))-1))
    weight=(math.log(p)-logs[index])/(logs[index+1]-logs[index])
    values={key:(1-weight)*rows[index][key]+weight*rows[index+1][key] for key in primitive}
    values['p_Pa']=p
    for side in ['l','v']:
        values['rho_'+side+'_kg_m3']=1/values['v_'+side+'_m3_kg']
        values['h_'+side+'_J_kg']=values['u_'+side+'_J_kg']+p*values['v_'+side+'_m3_kg']
    return values

def phase_split(properties,v):
    return (v-properties['v_l_m3_kg'])/(properties['v_v_m3_kg']-properties['v_l_m3_kg'])

def invert_mu(M,U,V):
    if not (M>0 and V>0 and all(math.isfinite(x) for x in [M,U,V])):raise ValueError('Finite, positive mass/volume required')
    specific_v=V/M;specific_u=U/M;solutions=[]
    for index in range(COUNT-1):
        left,right=rows[index],rows[index+1]
        low,high=0.0,1.0
        # Every cell's v_l and v_v are linear in ln(p). Intersect their exact
        # admissible portions rather than clipping unphysical vapor quality.
        for field,sign in [('v_l_m3_kg',1),('v_v_m3_kg',-1)]:
            a=sign*(left[field]-specific_v);b=sign*(right[field]-left[field])
            if b==0:
                if a>0:low,high=1,0;break
            elif b>0:high=min(high,-a/b)
            else:low=max(low,-a/b)
        if high<low or high<0 or low>1:continue
        low=max(0,low);high=min(1,high)
        def evaluate(t):
            p=math.exp(logs[index]+t*(logs[index+1]-logs[index]))
            p=min(PMAX,max(PMIN,p)) # roundoff at the explicitly allowed endpoints
            props=interpolated(p);quality=phase_split(props,specific_v)
            error=(1-quality)*props['u_l_J_kg']+quality*props['u_v_J_kg']-specific_u
            return error,p,quality,props['T_sat_K']
        fl=evaluate(low)[0];fh=evaluate(high)[0]
        if fl*fh>0:continue
        for _ in range(64):
            midpoint=(low+high)/2;fm=evaluate(midpoint)[0]
            if fl*fm<=0:high=midpoint;fh=fm
            else:low=midpoint;fl=fm
        error,p,quality,temperature=evaluate((low+high)/2)
        if not -1e-10<=quality<=1+1e-10:raise ValueError('Root left two-phase domain')
        if not solutions or abs(p-solutions[-1]['p_Pa'])/p>1e-9:
            solutions.append({'p_Pa':p,'T_K':temperature,'quality':quality,'specific_energy_residual_J_kg':error})
    if len(solutions)!=1:raise ValueError(f'Expected one admissible two-phase root, got {len(solutions)}')
    return solutions[0]

metadata=json.loads((ROOT/'coolprop-pypi-metadata.json').read_text(encoding='utf-8'))
wheel=next(f for f in metadata['urls'] if f['filename']=='coolprop-8.0.0-cp312-abi3-win_amd64.whl')
constants={name:CP.PropsSI(key,FLUID) for name,key in [
 ('critical_pressure_Pa','pcrit'),('critical_temperature_K','Tcrit'),
 ('triple_pressure_Pa','ptriple'),('triple_temperature_K','Ttriple'),('molar_mass_kg_mol','molar_mass')]}
AS.update(CP.QT_INPUTS,0.0,273.15)
reference_anchor={'T_K':AS.T(),'p_Pa':AS.p(),'quality':0,'h_J_kg':AS.hmass(),'u_J_kg':AS.umass(),'s_J_kg_K':AS.smass()}
table={
 'schema':'aegisdc-reference-saturation-v1','purpose':'engineering property reference preparation; no facility trial or policy evaluation',
 'site_medium_identity':'UNKNOWN: R134a is a research/EOS surrogate, not an identified Zhengzhou coolant or material recommendation',
 'source':{'library':'CoolProp','version':CoolProp.__version__,'gitrevision':CoolProp.__gitrevision__,'backend':'HEOS','fluid':FLUID,
           'reference_state_requested':'DEF','reference_anchor':reference_anchor,'wheel_filename':wheel['filename'],
           'wheel_sha256':wheel['digests']['sha256'],'wheel_url':wheel['url'],
           'official_docs':'https://coolprop.org/coolprop/HighLevelAPI.html','fluid_docs':'https://coolprop.org/fluid_properties/fluids/R134a.html',
           'pypi_release':'https://pypi.org/project/CoolProp/8.0.0/','equation_of_state_doi':'10.1063/1.555958'},
 'validity':{'pure_single_substance':True,'noncondensable_gas_included':False,'equilibrium_saturation_only':True,
             'p_min_Pa':PMIN,'p_max_Pa':PMAX,'no_extrapolation':True,'point_count':COUNT,'grid':'uniform in ln(p)',
             'constants':constants,'notes':'Subcritical table; no claims about dryout/superheated/subcooled states, pressure transients or real-site calibration.'},
 'interpolation':{'coordinate':'ln(p_Pa)','scheme':'piecewise linear','primitive_fields':primitive,
                  'derived_fields':['rho_l=1/v_l','rho_v=1/v_v','h_l=u_l+p*v_l','h_v=u_v+p*v_v'],
                  'notes':'Derivation enforces h-u-pv identity off grid. Interpolation still approximates the EOS and is validated numerically below.'},
 'units':{'p_Pa':'Pa','T_sat_K':'K','T_vapor_sat_K':'K','rho_l_kg_m3':'kg/m3','rho_v_kg_m3':'kg/m3',
          'v_l_m3_kg':'m3/kg','v_v_m3_kg':'m3/kg','u_l_J_kg':'J/kg','u_v_J_kg':'J/kg','h_l_J_kg':'J/kg','h_v_J_kg':'J/kg'},
 'rows':rows,
}
table_path=ROOT/'reference-r134a-saturation.json';write(table_path,table)

# These limits were declared above before observing validation errors.
raw_identity=max(abs(row['h_'+s+'_J_kg']-row['u_'+s+'_J_kg']-row['p_Pa']/row['rho_'+s+'_kg_m3']) for row in rows for s in ['l','v'])
phase_temperature=max(abs(row['T_sat_K']-row['T_vapor_sat_K']) for row in rows)
all_finite=all(math.isfinite(value) for row in rows for value in row.values())
positive_physical=all(row['p_Pa']>0 and row['T_sat_K']>0 and row['rho_l_kg_m3']>row['rho_v_kg_m3']>0 and row['h_v_J_kg']>row['h_l_J_kg'] and row['u_v_J_kg']>row['u_l_J_kg'] for row in rows)
monotonic_temperature=all(a['T_sat_K']<b['T_sat_K'] for a,b in zip(rows,rows[1:]))
domain_ok=constants['triple_pressure_Pa']<PMIN<PMAX<constants['critical_pressure_Pa']
assert all_finite and positive_physical and monotonic_temperature and domain_ok
assert raw_identity<=THRESHOLDS['raw_h_u_identity_abs_J_kg'] and phase_temperature<=1e-9

probes=[math.exp((a+b)/2) for a,b in zip(logs,logs[1:])]
probes +=[math.exp(math.log(PMIN)+(i+.37)*math.log(PMAX/PMIN)/32) for i in range(32)]
fields=['T_sat_K','rho_l_kg_m3','rho_v_kg_m3','u_l_J_kg','u_v_J_kg','h_l_J_kg','h_v_J_kg']
errors={field:{'max_abs':0.0,'max_relative':0.0} for field in fields}
for p in probes:
    actual=saturation(p);estimate=interpolated(p)
    for field in fields:
        absolute=abs(estimate[field]-actual[field]);relative=absolute/abs(actual[field])
        if absolute>errors[field]['max_abs']:errors[field].update(max_abs=absolute,p_at_max_abs_Pa=p)
        if relative>errors[field]['max_relative']:errors[field].update(max_relative=relative,p_at_max_relative_Pa=p)
assert errors['T_sat_K']['max_abs']<=THRESHOLDS['interpolated_temperature_abs_K']
assert max(errors[field]['max_relative'] for field in fields if field!='T_sat_K')<=THRESHOLDS['interpolated_property_max_relative']

inverse_cases=[];external=CP.AbstractState('HEOS',FLUID)
for pressure in [130000.,350000.,800000.,1500000.,2700000.]:
    for quality in [.01,.1,.5,.9,.99]:
        AS.update(CP.PQ_INPUTS,pressure,quality)
        M=10.0;V=M/AS.rhomass();U=M*AS.umass();expected_T=AS.T()
        external.update(CP.DmassUmass_INPUTS,M/V,U/M)
        result=invert_mu(M,U,V)
        row={'given_pressure_Pa':pressure,'given_quality':quality,'M_kg':M,'U_J':U,'V_m3':V,
             'external_EOS_flash':{'p_Pa':external.p(),'T_K':external.T(),'quality':external.Q()},
             'table_inverse':result,
             'table_errors':{'pressure_relative':abs(result['p_Pa']-pressure)/pressure,'temperature_abs_K':abs(result['T_K']-expected_T),'quality_abs':abs(result['quality']-quality)},
             'external_errors':{'pressure_relative':abs(external.p()-pressure)/pressure,'temperature_abs_K':abs(external.T()-expected_T),'quality_abs':abs(external.Q()-quality)}}
        for which,prefix in [('table_errors','inverse'),('external_errors','external_flash')]:
            assert row[which]['pressure_relative']<=THRESHOLDS[prefix+'_pressure_relative']
            assert row[which]['temperature_abs_K']<=THRESHOLDS[prefix+'_temperature_abs_K']
            assert row[which]['quality_abs']<=THRESHOLDS[prefix+'_quality_abs']
        inverse_cases.append(row)

rejected=[]
for p in [PMIN/2,PMAX*1.01]:
    try:interpolated(p)
    except ValueError:rejected.append(p)
assert len(rejected)==2

verification={
 'schema':'aegisdc-property-verification-v1','status':'PASS','recorded_UTC':datetime.now(timezone.utc).isoformat(),
 'scope':'Finite EOS/table consistency and off-grid numerical checks; no empirical/site validation, facility simulation, scheduling trial or training',
 'runtime':{'python':platform.python_version(),'platform':platform.platform(),'numpy':numpy.__version__,
            'coolprop':CoolProp.__version__,'coolprop_gitrevision':CoolProp.__gitrevision__,'coolprop_module_path':CoolProp.__file__},
 'artifacts':{'table':{'file':table_path.name,'bytes':table_path.stat().st_size,'sha256':digest(table_path)},
              'wheel':{'file':'wheels/'+wheel['filename'],'sha256':digest(ROOT/'wheels'/wheel['filename'])},
              'installed_extension':{'file':str(Path(CP.__file__).relative_to(ROOT)),'sha256':digest(Path(CP.__file__))},
              'authoring_script':{'file':Path(__file__).name,'sha256':digest(Path(__file__))},
              'pypi_metadata':{'file':'coolprop-pypi-metadata.json','sha256':digest(ROOT/'coolprop-pypi-metadata.json')}},
 'predeclared_numerical_limits':THRESHOLDS,
 'table_checks':{'finite':all_finite,'positive_T_p_density_and_positive_phase_gaps':positive_physical,'strictly_monotonic_Tsat':monotonic_temperature,
                 'bounded_above_triple_below_critical':domain_ok,'max_raw_h_u_pv_residual_J_kg':raw_identity,'max_liquid_vapor_T_disagreement_K':phase_temperature,
                 'u_h_positive_on_this_DEF_table':all(row['u_l_J_kg']>0 and row['h_l_J_kg']>0 for row in rows),
                 'energy_reference_note':'Absolute u/h positivity is reference dependent; it is observed here, not a universal acceptance rule.'},
 'interpolation_checks':{'probe_count':len(probes),'geometric_cell_midpoints':COUNT-1,'additional_off_grid':32,'errors':errors,
                         'identity_note':'h=u+pv is enforced by deriving h off grid; independent off-grid EOS error comparisons are recorded separately.'},
 'initial_state_inverse':{'case_count':len(inverse_cases),'construction':'Direct EOS(P,Q)→M,U,V; independent EOS(Dmass,Umass) flash and table M/U/V inverse',
                          'max_table_errors':{key:max(row['table_errors'][key] for row in inverse_cases) for key in ['pressure_relative','temperature_abs_K','quality_abs']},
                          'max_external_flash_errors':{key:max(row['external_errors'][key] for row in inverse_cases) for key in ['pressure_relative','temperature_abs_K','quality_abs']},
                          'cases':inverse_cases},
 'out_of_table_pressure_rejected_Pa':rejected,
 'environment_change':'CoolProp only installed in requested Temp target; no global or pyproject dependency modification',
 'new_facility_research_trials':0,'new_training':0,
}
write(ROOT/'verification.json',verification)

summary=f'''# R134a饱和物性参考表

生成日期：2026-11-04。用途为主线模型实现前的**工程物性参考数据准备**；不是设施科研试验、调度或训练。R134a是具名纯物性替身，郑州实际冷媒身份仍unknown，也不构成工程材料选型结论。

## 固定来源与安装

- 官方PyPI现场查询与当前官方文档均为CoolProp **8.0.0**；使用Windows cp312 ABI3 wheel，一次安装成功，无版本回退。
- Git revision：`{CoolProp.__gitrevision__}`。
- Wheel：`{wheel['filename']}`，SHA256 `{wheel['digests']['sha256']}`。
- 隔离目录：`coolprop-deps/`。Python {platform.python_version()}，使用既有NumPy {numpy.__version__}；未更改全局环境或项目依赖。
- 后端/介质：`HEOS / R134a`；进程中显式`set_reference_state('R134a','DEF')`。同一参考态的273.15K饱和液锚点及表中全部字段来自同一EOS。

## 表结构与边界

`reference-r134a-saturation.json`：512点，p在0.1–3.0MPa按ln(p)均匀分布，所有值用SI：p=Pa，T=K，ρ=kg/m³，v=m³/kg，u/h=J/kg。每行独立读取液相Q=0和汽相Q=1的T、ρ、u、h，并存v=1/ρ。压力域位于三相点{constants['triple_pressure_Pa']:.9g}Pa和临界点{constants['critical_pressure_Pa']:.12g}Pa之间；三相温度{constants['triple_temperature_K']:.8g}K，临界温度{constants['critical_temperature_K']:.12g}K。

表SHA256：`{verification['artifacts']['table']['sha256']}`，大小{table_path.stat().st_size}字节。不外推；超出此表、离开两相区、接近临界或涉及不可凝气体/混合物时，须切模型或报告不适用。

插值对ln(p)下的T、v_l/v_v、u_l/u_v线性；ρ=1/v，h=u+pv派生，保持焓/内能一致。不要独立插ρ和h后再假定恒等式仍严格成立。此策略近似EOS，其误差不等于真实冷媒物性不确定性。

## 有限核验结果

- 512点正温压/密度、相序、严格递增Tsat及有限数均通过；原始h−u−p/ρ最大残差{raw_identity:.3g}J/kg。
- 511个几何中点＋32个离网点直接对照EOS：最大Tsat误差{errors['T_sat_K']['max_abs']:.6g}K，其他字段最大相对误差{max(errors[field]['max_relative'] for field in fields if field!='T_sat_K'):.6g}。误差阈值在脚本计算前声明，见verification.json。
- 5压力×5质量干度的25个初值：先EOS(P,Q)构造M/U/V，再由EOS(Dmass,Umass)直接flash，以及表反解；表压力相对误差最高{verification['initial_state_inverse']['max_table_errors']['pressure_relative']:.6g}、温度绝对误差{verification['initial_state_inverse']['max_table_errors']['temperature_abs_K']:.6g}K、干度绝对误差{verification['initial_state_inverse']['max_table_errors']['quality_abs']:.6g}。全部为有限数值交叉核验，不是独立经验验证。
- 两个超域压力查询均被拒绝。没有把固定压力的ṁh_fg热量式当固定容积ΔU，也没有静默裁剪质量干度。

## 给实现者的接口

外部EOS：`AbstractState('HEOS','R134a')`；`update(PQ_INPUTS,p,0/1)`读取饱和相；`update(DmassUmass_INPUTS,M/V,U/M)`做初值外部flash。饱和线上使用P,Q，避免以P,T落在饱和线上引起二义性。表反解仅在合法干度/物性域中寻找唯一根。

生成/核验脚本为同目录`prepare_reference_properties.py`。数据表、verification.json及wheel/扩展二进制/脚本SHA均已保存；实际库并非运行器的必需依赖，可在后续部署时只消费冻结的参考表。

## 主来源

- [PyPI 8.0.0](https://pypi.org/project/CoolProp/8.0.0/)，[官方JSON](https://pypi.org/pypi/CoolProp/json)：版本、Python兼容及wheel SHA。
- [CoolProp高层API](https://coolprop.org/coolprop/HighLevelAPI.html)：SI、P/Q饱和、参考态、Dmass/Umass输入。
- [R134a官方页](https://coolprop.org/fluid_properties/fluids/R134a.html)：纯工质EOS、边界及[原EOS DOI](https://doi.org/10.1063/1.555958)。

本次读取相关官方页面、库输出和25个参考初值；未声称核读原EOS论文全文，也未验证真实郑州介质、设备或工况。
'''
(ROOT/'reference-properties.md').write_text(summary,encoding='utf-8',newline='\n')
print(json.dumps({'status':'PASS','table_sha256':verification['artifacts']['table']['sha256'],'points':COUNT,
                  'midpoint_and_offgrid_probes':len(probes),'inverse_cases':len(inverse_cases),
                  'max_temperature_error_K':errors['T_sat_K']['max_abs'],
                  'max_property_relative_error':max(errors[field]['max_relative'] for field in fields if field!='T_sat_K'),
                  'max_inverse_errors':verification['initial_state_inverse']['max_table_errors']},indent=2))
