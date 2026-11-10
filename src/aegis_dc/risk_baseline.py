"""FEMA-adapted review baseline over existing public risk and value models."""
import hashlib
from pathlib import Path

from patrol_rsi.contracts import strict_json
from .action_value import assess_action_value
from .evidence_ledger import _fields,_require,_strings,_text

ROOT=Path(__file__).resolve().parents[2]
FIELDS={'schema','id','facility_id','source_note','references','method','domains'}
REFERENCES={'public_frame','belief_model','risk_catalog','value_model','facility_model'}
DOMAIN_FIELDS={'domain_id','label','primary_question_id','hazard_context','inspection_question',
               'evidence_triggers','probability_object','missing_inputs'}
TRIGGERS={'asset_record','maintenance_history','human_report','work_order','fixed_sensor','handheld'}


def review_baseline(manifest_path):
    """Read declared public inputs; keep unmodelled quantities null and dispatch disabled."""
    path=Path(manifest_path);raw=path.read_bytes();manifest=strict_json(raw.decode('utf-8'))
    _fields(manifest,FIELDS,'Risk baseline manifest')
    _require(manifest['schema']=='aegisdc-facility-risk-baseline-manifest-v1','Unsupported risk baseline schema')
    for name in ('id','facility_id','source_note'):_text(manifest[name],'Baseline '+name)
    _fields(manifest['references'],REFERENCES,'Risk baseline references')
    _fields(manifest['method'],{'kind','sources','mapping'},'FEMA adaptation')
    _require(manifest['method']['kind']=='FEMA_ADAPTED_PROCESS_NOT_DEVICE_SCORE','Declare the FEMA adaptation scope')
    _strings(manifest['method']['sources'],'FEMA source URLs');_strings(manifest['method']['mapping'],'FEMA process mapping')
    rows=manifest['domains'];_require(type(rows) is list and len(rows)==8,'Declare exactly eight domain baseline rows')
    for row in rows:
        _fields(row,DOMAIN_FIELDS,'closed domain baseline')
        for key in ('domain_id','label','primary_question_id','hazard_context','inspection_question','probability_object'):_text(row[key],'Domain '+key)
        _strings(row['evidence_triggers'],'Domain evidence triggers');_strings(row['missing_inputs'],'Domain missing inputs')
        _require(bool(row['evidence_triggers']) and set(row['evidence_triggers'])<=TRIGGERS,'Unknown or empty evidence trigger')
    loaded={};identities={}
    for key,name in manifest['references'].items():
        _text(name,'Baseline reference path');candidate=(ROOT/name).resolve()
        _require(not Path(name).is_absolute() and candidate.is_relative_to(ROOT),'Keep baseline references repository-relative')
        content=candidate.read_bytes();loaded[key]=strict_json(content.decode('utf-8'))
        identities[name]=dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
    frame,belief,catalog,value,facility=(loaded[k] for k in ('public_frame','belief_model','risk_catalog','value_model','facility_model'))
    _require(manifest['facility_id']==frame['facility_id']==facility['id'],'Baseline facility identities differ')
    domain_ids=frame['nominal_knowledge']['domain_ids']
    _require(len(set(r['domain_id'] for r in rows))==8 and set(r['domain_id'] for r in rows)==set(domain_ids),'Domain baseline coverage differs')
    _require(len(set(r['primary_question_id'] for r in rows))==8,'Use one distinct primary scenario per domain')
    questions={q['id']:q for q in catalog['questions']};assets={e['id'] for e in facility['entities']}
    for row in rows:
        q=questions.get(row['primary_question_id'])
        _require(q is not None and row['domain_id'] in q['domain_ids'],'Primary question does not cover this domain')
        _require(bool(q['target_ids']) and set(q['target_ids'])<=assets,'Risk baseline asset identity differs')
    values=assess_action_value(frame,belief,catalog,value);risks=values['risk']
    evaluated={q['id']:q for q in risks['questions']};valued={q['question_id']:q for q in values['question_values']}
    domains=[]
    for row in rows:
        q=questions[row['primary_question_id']];known=q['quantification']=='FINITE_CONDITIONAL_LAW';v=valued.get(q['id'])
        domains.append(dict(domain_id=row['domain_id'],label=row['label'],primary_question_id=q['id'],
            hazard_context=row['hazard_context'],asset_ids=q['target_ids'],functional_edge_ids=q['dependency_edge_ids'],
            probability_object=row['probability_object'],risk_status='FINITE_CONDITIONAL_LAW' if known else 'UNMODELED',
            conditional_risk=evaluated[q['id']] if known else None,consequence_bounds=q['consequence_bounds'],
            impact_description=q['impact_description'],barriers=q['barriers'],evidence_triggers=row['evidence_triggers'],
            evidence_gaps=row['missing_inputs'],inspection_question=row['inspection_question'],
            inspection_value_status='FINITE_CONDITIONAL_MODEL_UNALIGNED_TIME' if v is not None else 'UNMODELED',
            inspection_value=v,inspection_value_gap=None if v is not None else
                'Need an inspection alternative,observation likelihood,post-action consequence and matching time basis.',
            declared_options=q['options'],verification_evidence=q['closure_evidence']))
    parameters={p['id']:p for p in facility['parameters']}
    for key in ('inspection_time','walk_short','walk_long','diesel_start_time','duration'):
        _require(parameters[key]['unit']=='s' and type(parameters[key]['value']) in (int,float) and parameters[key]['value']>0,
                 'Declare positive default model seconds')
    local=value['question_models'][0];inspection=local['inspection'];work=parameters['inspection_time']['value']
    time=dict(status='UNRESOLVED_ALIGNMENT',scope='Conditional arithmetic fixture and declared default model,not calibrated field timing',
        as_of_s=frame['as_of_s'],risk_horizon_s=catalog['horizon_s'],default_horizon_s=parameters['duration']['value'],
        default_work_s=work,default_walk_s=[parameters[k]['value'] for k in ('walk_short','walk_long')],
        default_diesel_start_s=parameters['diesel_start_time']['value'],
        value_inspection_s=sum(inspection[k] for k in ('travel_s','wait_s','work_s','report_latency_s')),
        value_intervention_s=sum(local['intervention'][k] for k in ('travel_s','wait_s','work_s')),
        default_work_to_risk_horizon_ratio=work/catalog['horizon_s'],
        default_walk_to_work_ratios=[parameters[k]['value']/work for k in ('walk_short','walk_long')],
        time_to_harm_s=None,response_to_harm_ratio=None,
        required_before_operational_use=['Define a matched forecast and response time contract','Specify state evolution and event likelihood over that horizon','Validate new numerical scope before physical-effect comparisons'])
    modelled=sum(d['risk_status']!='UNMODELED' for d in domains);value_modelled=sum(d['inspection_value'] is not None for d in domains)
    return dict(schema='aegisdc-facility-risk-inspection-baseline-v1',id=manifest['id'],status='PARTIAL_BASELINE_AWAITING_USER_REVIEW',
        facility_id=manifest['facility_id'],method=manifest['method'],source_note=manifest['source_note'],
        coverage=dict(primary_domain_scenarios=8,risk_modelled_primary_domains=modelled,risk_unmodelled_primary_domains=8-modelled,
            inspection_value_modelled_primary_domains=value_modelled,inspection_value_unmodelled_primary_domains=8-value_modelled),
        domains=domains,known_subset_portfolio=risks['portfolio'],whole_facility_expected_risk=None,
        time_foundation=time,source_identities=identities,manifest_sha256=hashlib.sha256(raw).hexdigest(),
        field_calibrated=False,execution_permission=False,physical_actions=[],next_automatic_inspection=None,
        dispatch_blockers=['Whole-facility risk/value coverage is incomplete','Time alignment is unresolved','User review gate is active'],
        research_gain_claim='NOT_ESTABLISHED',new_facility_runs=0,new_neural_or_llm_calls=0,new_registered_research_runs=0)
