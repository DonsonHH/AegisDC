"""Neutralize the shared authorization note without changing its permitted disposition."""
from copy import deepcopy
import json
from pathlib import Path

from prepare_negative_control_inputs_v5 import NEW as OLD, ROOT, digest, write

NEW = OLD.with_name('reference-v6')
NOTE = 'Synthetic authority to review the cooling question within the declared disposition scope.'


def neutralize_authority(document):
    result = deepcopy(document)
    for name in ('normal','false_report'):
        auth, = result['cases'][name]['replay_inputs']['dispatch_program']['closure_program']['profile']['authorizations']
        assert auth['source_note'] == 'Synthetic authority to review an erroneous suspicion, not repair authority.'
        auth['source_note'] = NOTE
    return result


def main():
    assert not NEW.exists()
    result = neutralize_authority(json.loads((OLD/'cases-v1.json').read_bytes()))
    NEW.mkdir(parents=True)
    write(NEW/'cases-v1.json',result)
    with (NEW/'literals-v1.json').open('xb') as stream:
        stream.write((OLD/'literals-v1.json').read_bytes())
    names=('cases-v1.json','literals-v1.json')
    write(NEW/'preparation.json',dict(status='PREPARED_NOT_EXECUTED',
        source_inputs={(OLD/name).relative_to(ROOT).as_posix():digest(OLD/name) for name in names},
        outputs={name:digest(NEW/name) for name in names},
        authoring_tool_sha256=digest(Path(__file__)),
        roles='Two copies of one shared authorization source note; no evidence record, authority interval, rule, or disposition changed.',
        physical_inputs_changed=False,literals_changed=False,new_project_calls=0))
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',changed_authorization_source_notes=2,new_project_calls=0)))


if __name__=='__main__':
    main()
