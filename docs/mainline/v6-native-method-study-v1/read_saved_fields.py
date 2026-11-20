"""Stream selected fields for publication only after the reviewed controller has stopped."""
from pathlib import Path
import hashlib
import json
import sys

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_bytes())
def fields(row, names):return {key:row.get(key) for key in names}


def main(activity, control_log):
    if not (control_log/'controller.exit').is_file() or not ((activity/'finished.json').is_file() or (activity/'halt.json').is_file()):
        raise ValueError('Study has no archived controller exit and stop/seal')
    progress=read(activity/'progress.json')
    if progress['purpose']!='NATIVE_V6_RESEARCH' or progress['denominator']!=85:raise ValueError('Unexpected study')
    for slot in progress['rows']:
        unit=slot['unit']
        case,arm=unit.split('-')
        arm_dir=activity/'jobs'/case/'arms'/unit
        path=arm_dir/'run/run.json'
        row={'unit':unit,'slot':slot,'run_present':path.is_file()}
        if path.is_file():
            blob=path.read_bytes();h=sha(blob)
            pin_file=arm_dir/'native-return.json'
            pin=read(pin_file) if pin_file.is_file() else None
            if pin and pin['native_sha256']!=h:raise ValueError('Saved return drift: '+unit)
            row.update(native_sha256=h,validated_receipt=pin)
            if pin:
                native=json.loads(blob)
                row['source_tree_sha256']=native['code_identity']['source_tree_sha256']
                row['artifacts']=native['artifacts']
                row['service_summary']=fields(native['summary'],['duration_s','service_deficit_time_s','demand_service_unit_s','delivered_service_unit_s'])
                row['work_records']=[fields(r,['id','target_id','issued_at_s','accepted','status','started_at_s','work_started_at_s','completed_at_s','finished_at_s','reason']) for r in native['work_records']]
                row['action_reports']=native.get('intervention_public_feedback',[])
                row['observation_binding']={b['task_id']:b['record_id'] for b in native['inputs']['inspection_program']['profile']['bindings']}
                row['arrived_work_receipts']=[fields(r,['task_id','status','observed_at_s','arrived_at_s','reason']) for r in native.get('workforce_public_feedback',[])]
                reached=[];measurements={};first_decisions={}
                for d in native.get('policy_public_decisions',[]):
                    ch=d['choice'];frame=d['frame']
                    details=[]
                    for q in ch.get('intake_decisions',[]):
                        key=q['question_id']
                        details.append([key,q.get('state'),q.get('observation'),q.get('record_id')])
                        if key not in first_decisions:
                            first_decisions[key]=dict(at_s=frame['as_of_s'],state=q.get('state'),continuation=q.get('continuation'),
                                conditional_forecast=q.get('scores'),direct_preferred=q.get('direct_preferred'),
                                fixed_threshold_inspection=q.get('fixed_threshold_inspection'))
                    reached.append([frame['as_of_s'],ch['reason'],ch['chosen_candidate_id'],details])
                    for r in frame['evidence']['records']:
                        if r['source_id']=='portable-intake-meter' and r['id'] not in measurements:
                            measurements[r['id']]=fields(r,['id','source_id','target_id','observable_id','value','unit','observed_at_s','arrived_at_s','valid_until_s','availability'])
                row.update(decisions=reached,arrived_portable_records=list(measurements.values()),first_public_selections=first_decisions)
        sys.stdout.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))
