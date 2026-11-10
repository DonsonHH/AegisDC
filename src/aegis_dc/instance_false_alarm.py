"""Evidence-bound management review of an actual problem instance's original suspicion."""

from .evidence_ledger import _fields, _require, _strings, _text
from .verified_closure import _check, _review_frame

DOSSIER_FIELDS = {'review_record_id', 'question_id', 'original_record_id',
                  'supporting_record_ids', 'rationale'}


def validate_dossiers(profile, channels, authorizations):
    rows = profile['false_alarm_reviews']
    _require(type(rows) is list, 'Declare instance false-alarm review dossiers')
    by_record = {row['record_id']: row for row in channels.values()}
    dossiers = {}
    for row in rows:
        _fields(row, DOSSIER_FIELDS, 'Instance false-alarm dossier')
        for field in ('review_record_id', 'question_id', 'original_record_id', 'rationale'):
            _text(row[field], 'Instance dossier ' + field)
        _strings(row['supporting_record_ids'], 'Instance false-alarm support IDs')
        identifier = row['review_record_id']
        channel = by_record.get(identifier)
        _require(identifier not in dossiers and channel is not None
                 and channel['question_id'] == row['question_id']
                 and 'FALSE_ALARM' in authorizations[channel['authorization_id']]['dispositions'],
                 'Unknown, repeated or incorrectly bound instance false-alarm dossier')
        dossiers[identifier] = row
    return dossiers


def evaluate_review(frame, instance, rule, review, dossier):
    """Require the exact original, support at review time, and current corroboration."""
    evaluation = dict(
        review_record_id=review['id'], original_record_id=dossier['original_record_id'] if dossier else None,
        review_at_s=review['observed_at_s'], current_at_s=frame['as_of_s'], passed=False,
        reason='MISSING_OR_MISMATCHED_DOSSIER', review_checks=[], current_checks=[])
    if (dossier is None or dossier['question_id'] != instance['id']
            or dossier['original_record_id'] != instance['trigger_record_id']):
        return evaluation
    prior = _review_frame(frame, review['observed_at_s'])
    ids = set(dossier['supporting_record_ids'])
    available = {row['id'] for row in prior['evidence']['records']}
    if not ids <= available or dossier['original_record_id'] not in available:
        evaluation['reason'] = 'SUPPORT_NOT_AVAILABLE_AT_REVIEW'
        return evaluation
    before = [_check(prior, rule, check, instance['opened_at_s'], support_ids=ids)
              for check in rule['checks']]
    now = [_check(frame, rule, check, instance['opened_at_s']) for check in rule['checks']]
    passed = all(check['passed'] for check in before + now)
    evaluation.update(
        review_checks=before, current_checks=now, passed=passed,
        reason='DECLARED_INSTANCE_REVIEW_CRITERIA_MET' if passed else 'CRITERIA_INCOMPLETE_OR_CONTRADICTED')
    return evaluation
