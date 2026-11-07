"""Declare an idle typed workforce so all negative controls have explicit cost accounts."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'evidence/mainline/engineering/28-negative-controls/reference-v2/cases-v1.json'
OUTPUT = ROOT / 'evidence/mainline/engineering/28-negative-controls/reference-workforce'


def main():
    assert not OUTPUT.exists()
    doc = json.loads((ROOT / SOURCE).read_bytes())
    online = doc['cases']['normal']['replay_inputs']['dispatch_program']
    value = dict(classification='DECLARED_EMPTY_CREW_NOT_A_POLICY',
        nominal_knowledge=deepcopy(online['nominal_knowledge']),
        evidence_ledger=deepcopy(online['evidence_ledger']),
        profile=deepcopy(online['policy_program']['workforce_profile']),
        plan=dict(schema='aegisdc-public-preparation-plan-v1', id='ticket28-idle-protection-crew',
                  basis='synthetic_assumption', time_unit='s', decision_times_s=[0], requests=[]),
        submissions=[])
    assert value['evidence_ledger']['records'] == []
    OUTPUT.mkdir(parents=True)
    def write(path, document):
        with path.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(document,stream,ensure_ascii=False,indent=2)
            stream.write('\n')
    write(OUTPUT / 'idle-crew.json', value)
    write(OUTPUT / 'preparation.json', dict(status='PREPARED_NOT_EXECUTED',
        source_inputs={SOURCE: sha256((ROOT / SOURCE).read_bytes()).hexdigest()},
        authoring_tool_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        artifacts={'idle-crew.json': sha256((OUTPUT / 'idle-crew.json').read_bytes()).hexdigest()},
        durable_files=['idle-crew.json','preparation.json'], initial_public_frames_to_release=1,
        reason='Legacy no-crew runs do not publish the typed access/queue counters. An explicitly idle crew reports actual zero rates; no missing field is coerced to zero.',
        new_project_calls=0))
    print(json.dumps(dict(prepared=OUTPUT.relative_to(ROOT).as_posix(),new_physics=0,new_selectors=0)))


if __name__ == '__main__':
    main()
