"""Apply a current, authorized management disposition to one public question instance."""
from copy import deepcopy

from .evidence_ledger import _fields, _finite, _registry, _require, _strings, _text

AUTHORIZATION_FIELDS = {'id', 'source_id', 'question_ids', 'dispositions', 'starts_at_s', 'expires_at_s', 'basis', 'source_note'}
CHANNEL_FIELDS = {'id', 'question_id', 'source_id', 'target_id', 'observable_id', 'authorization_id', 'record_id'}
REVIEW_STATUS = {'ACCEPT_RISK': 'RISK_ACCEPTED', 'ESCALATE': 'ESCALATED'}
REVIEW_EVENT = {'ACCEPT_RISK': 'AUTHORIZED_RISK_ACCEPTANCE_AVAILABLE',
                'ESCALATE': 'AUTHORIZED_ESCALATION_AVAILABLE'}


def validate_instance_review_declarations(frame, profile):
    """Validate the narrow v2 review channel without granting physical authority."""
    authorizations = _registry(profile['authorizations'], 'Instance review authorization')
    channels = _registry(profile['review_channels'], 'Instance review channel')
    sources = {row['id']: row for row in frame['evidence']['static_knowledge']['sources']}
    observables = {row['id']: row for row in frame['evidence']['static_knowledge']['observables']}
    seen_records = set()
    for grant in authorizations.values():
        _fields(grant, AUTHORIZATION_FIELDS, 'Instance review authorization')
        for key in ('id', 'source_id', 'basis', 'source_note'):
            _text(grant[key], 'Instance review authorization ' + key)
        _strings(grant['question_ids'], 'Instance review question IDs')
        _strings(grant['dispositions'], 'Instance review dispositions')
        _require(grant['basis'] == 'synthetic_assumption'
                 and set(grant['dispositions']) <= REVIEW_STATUS.keys(),
                 'Unknown or non-synthetic instance review authority')
        _finite(grant['starts_at_s'], 'Instance review authority start')
        _finite(grant['expires_at_s'], 'Instance review authority expiry')
        _require(0 <= grant['starts_at_s'] < grant['expires_at_s'],
                 'Invalid instance review authority interval')
        _require(grant['source_id'] in sources, 'Unknown instance review authority source')

    for channel in channels.values():
        _fields(channel, CHANNEL_FIELDS, 'Instance review channel')
        for key in CHANNEL_FIELDS:
            _text(channel[key], 'Instance review channel ' + key)
        _require(channel['record_id'] not in seen_records,
                 'Instance review record bindings must be unique')
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
             'False-alarm dossiers are outside the current management disposition scope')
    return authorizations, channels


def _history_at(history, as_of_s):
    projected = deepcopy(history)
    projected['issued'] = [row for row in projected['issued'] if row['issued_at_s'] <= as_of_s]
    projected['work_feedback'] = [row for row in projected['work_feedback'] if row['arrived_at_s'] <= as_of_s]
    projected['question_instances'] = [row for row in projected['question_instances']
                                       if row['opened_at_s'] <= as_of_s]
    projected['intervention_feedback'] = [row for row in projected['intervention_feedback']
                                          if row['arrived_at_s'] <= as_of_s]
    return projected


def _prior_lifecycle(frame, policy, history, program, question_id, record):
    """Replay the visible public frame/history at the review's arrival clock."""
    from .problem_closure import _assess_instance_closure
    from .verified_closure import _review_frame

    prior_frame = _review_frame(frame, record['arrived_at_s'])
    prior_history = _history_at(history, record['arrived_at_s'])
    prior_program = deepcopy(program)
    prior_program['intervention_feedback'] = deepcopy(prior_history['intervention_feedback'])
    prior = _assess_instance_closure(prior_frame, policy, prior_history, prior_program,
                                     project_prior_lifecycle=False)
    return next((row for row in prior['questions'] if row['question_id'] == question_id), None)


def apply_instance_reviews(frame, policy, history, program, assessment, *, project_prior_lifecycle=True):
    """Return a detached current assessment with authorized past dispositions retained."""
    profile = program['profile']
    authorizations, channels = validate_instance_review_declarations(frame, profile)
    questions = {row['question_id']: row for row in assessment['questions']}
    records = {row['id']: row for row in frame['evidence']['records']}
    current_ids = set(frame['evidence']['current_record_ids'])
    disputed = {identifier for issue in frame['evidence']['conflicts']
                if set(issue['record_ids']) <= current_ids for identifier in issue['record_ids']}
    disputed |= {identifier for issue in frame['evidence']['provenance_issues']
                 if set(issue['record_ids']) & current_ids for identifier in issue['record_ids']}
    current_reviews = {}

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
                 and record['value'] in grant['dispositions']
                 and record['observed_at_s'] >= question['opened_at_s']
                 and record['arrived_at_s'] <= frame['as_of_s']
                 and grant['starts_at_s'] <= record['observed_at_s'] < grant['expires_at_s']
                 and grant['starts_at_s'] <= frame['as_of_s'] < grant['expires_at_s'])
        if not valid:
            if project_prior_lifecycle and record['arrived_at_s'] <= frame['as_of_s']:
                historical = _prior_lifecycle(frame, policy, history, program,
                                              channel['question_id'], record)
                if (historical is not None
                        and historical['status'] == REVIEW_STATUS.get(record['value'])
                        and record['id'] in historical['disposition_record_ids']):
                    question.setdefault('historical_dispositions', []).append(dict(
                        record_id=record['id'], disposition=record['value'],
                        observed_at_s=record['observed_at_s'], arrived_at_s=record['arrived_at_s'],
                        status_at_arrival=historical['status'],
                        question_closed_at_arrival=historical['question_closed'],
                        risk_closed_at_arrival=historical['risk_closed'],
                        physical_restoration_claim_at_arrival=historical['physical_restoration_claim'],
                        authorization_id=grant['id'],
                        scope='HISTORICAL_AUTHORIZED_DISPOSITION_REPLAYED_FROM_PUBLIC_ARRIVAL_FRAME'))
                    question['historical_dispositions'].sort(
                        key=lambda row: (row['arrived_at_s'], row['record_id']))
            continue

        current_reviews.setdefault(question['question_id'], []).append((record, grant))

    for question_id, reviews in current_reviews.items():
        question = questions[question_id]
        status = ('ESCALATED' if any(record['value'] == 'ESCALATE' for record, _ in reviews)
                  else 'RISK_ACCEPTED')
        question.update(status=status, question_closed=status == 'RISK_ACCEPTED', risk_closed=False,
                        physical_restoration_claim=False,
                        disposition_record_ids=sorted(record['id'] for record, _ in reviews),
                        scope='OWN_INSTANCE_AUTHORIZED_MANAGEMENT_DISPOSITION_NOT_PHYSICAL_RESTORATION')
        for record, grant in reviews:
            question['trace'].append(dict(event=REVIEW_EVENT[record['value']], record_id=record['id'],
                disposition=record['value'], observed_at_s=record['observed_at_s'],
                arrived_at_s=record['arrived_at_s'], valid_until_s=record['valid_until_s'],
                authorization_id=grant['id'], provenance=deepcopy(record['provenance'])))
        question['trace'].sort(key=lambda row: (row['arrived_at_s'], row.get('record_id', '')))

    return assessment
