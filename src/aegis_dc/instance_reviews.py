"""Apply a current, authorized management disposition to one public question instance."""
from copy import deepcopy

from .evidence_ledger import _fields, _finite, _registry, _require, _strings, _text

AUTHORIZATION_FIELDS = {'id', 'source_id', 'question_ids', 'dispositions', 'starts_at_s', 'expires_at_s', 'basis', 'source_note'}
CHANNEL_FIELDS = {'id', 'question_id', 'source_id', 'target_id', 'observable_id', 'authorization_id', 'record_id'}


def validate_instance_review_declarations(frame, profile):
    """Validate the narrow v2 review channel without granting physical authority."""
    authorizations = _registry(profile['authorizations'], 'Instance review authorization')
    channels = _registry(profile['review_channels'], 'Instance review channel')
    sources = {row['id']: row for row in frame['evidence']['static_knowledge']['sources']}
    observables = {row['id']: row for row in frame['evidence']['static_knowledge']['observables']}
    seen_questions = set()
    seen_records = set()
    for grant in authorizations.values():
        _fields(grant, AUTHORIZATION_FIELDS, 'Instance review authorization')
        for key in ('id', 'source_id', 'basis', 'source_note'):
            _text(grant[key], 'Instance review authorization ' + key)
        _strings(grant['question_ids'], 'Instance review question IDs')
        _strings(grant['dispositions'], 'Instance review dispositions')
        _require(grant['basis'] == 'synthetic_assumption'
                 and set(grant['dispositions']) == {'ACCEPT_RISK'},
                 'This instance review slice permits only synthetic risk acceptance')
        _finite(grant['starts_at_s'], 'Instance review authority start')
        _finite(grant['expires_at_s'], 'Instance review authority expiry')
        _require(0 <= grant['starts_at_s'] < grant['expires_at_s'],
                 'Invalid instance review authority interval')
        _require(grant['source_id'] in sources, 'Unknown instance review authority source')

    for channel in channels.values():
        _fields(channel, CHANNEL_FIELDS, 'Instance review channel')
        for key in CHANNEL_FIELDS:
            _text(channel[key], 'Instance review channel ' + key)
        _require(channel['question_id'] not in seen_questions
                 and channel['record_id'] not in seen_records,
                 'Instance review question and record bindings must be unique')
        seen_questions.add(channel['question_id'])
        seen_records.add(channel['record_id'])
        grant = authorizations.get(channel['authorization_id'])
        source = sources.get(channel['source_id'])
        observable = observables.get(channel['observable_id'])
        _require(grant is not None and source is not None and observable is not None,
                 'Unknown instance review source, observable or authority')
        _require(grant['source_id'] == source['id']
                 and channel['question_id'] in grant['question_ids'],
                 'Instance review source or question exceeds authority')
        _require(channel['target_id'] in source['target_ids']
                 and channel['observable_id'] in source['observable_ids']
                 and observable['value_type'] == 'text',
                 'Instance review channel exceeds categorical source coverage')

    _require(type(profile['false_alarm_reviews']) is list and not profile['false_alarm_reviews'],
             'False-alarm review is outside this instance risk-acceptance slice')
    return authorizations, channels


def apply_instance_reviews(frame, program, assessment):
    """Close only the matching management question; never claim risk or physical closure."""
    profile = program['profile']
    authorizations, channels = validate_instance_review_declarations(frame, profile)
    questions = {row['question_id']: row for row in assessment['questions']}
    records = {row['id']: row for row in frame['evidence']['records']}
    current_ids = set(frame['evidence']['current_record_ids'])
    disputed = {identifier for issue in frame['evidence']['conflicts']
                if set(issue['record_ids']) <= current_ids for identifier in issue['record_ids']}
    disputed |= {identifier for issue in frame['evidence']['provenance_issues']
                 if set(issue['record_ids']) & current_ids for identifier in issue['record_ids']}

    for channel in channels.values():
        question = questions.get(channel['question_id'])
        record = records.get(channel['record_id'])
        if question is None or question['risk_closed'] or record is None:
            continue
        grant = authorizations[channel['authorization_id']]
        matches = (record['id'] == channel['record_id']
                   and all(record[key] == channel[key] for key in ('source_id', 'target_id', 'observable_id')))
        valid = (matches and record['id'] in current_ids and record['availability'] == 'current'
                 and record['quality']['status'] == 'reported'
                 and record['provenance']['copied_from_record_id'] is None
                 and record['id'] not in disputed
                 and record['value'] == 'ACCEPT_RISK'
                 and record['observed_at_s'] >= question['opened_at_s']
                 and record['arrived_at_s'] <= frame['as_of_s']
                 and grant['starts_at_s'] <= record['observed_at_s'] < grant['expires_at_s']
                 and grant['starts_at_s'] <= frame['as_of_s'] < grant['expires_at_s'])
        if not valid:
            continue

        question.update(status='RISK_ACCEPTED', question_closed=True, risk_closed=False,
                        physical_restoration_claim=False,
                        disposition_record_ids=[record['id']],
                        scope='OWN_INSTANCE_AUTHORIZED_MANAGEMENT_DISPOSITION_NOT_PHYSICAL_RESTORATION')
        question['trace'].append(dict(event='AUTHORIZED_RISK_ACCEPTANCE_AVAILABLE', record_id=record['id'],
            disposition=record['value'], observed_at_s=record['observed_at_s'],
            arrived_at_s=record['arrived_at_s'], valid_until_s=record['valid_until_s'],
            authorization_id=grant['id'], provenance=deepcopy(record['provenance'])))
        question['trace'].sort(key=lambda row: (row['arrived_at_s'], row.get('record_id', '')))

    return assessment
