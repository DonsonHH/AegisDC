"""Use the original saved-data checks, resolving just the retained two-attempt pilot position."""
from pathlib import Path
import sys
import summarize_study as summary

original=summary.position


def read_position(row,mode,bindings,manifest):
    if (row,mode)!=('4-01','ORACLE'):
        return original(row,mode,bindings,manifest)
    base=summary.ROOT/'positions'/(row+'-'+mode)
    failed=summary.load(base/'start.json')
    summary.need(failed['job']=='134753' and failed['input']==bindings[row] and failed['manifest']==manifest
                 and not (base/'result.json').exists(),'failed pilot original changed')
    p=base/'attempt-02'
    x=summary.load(p/'result.json');entry=summary.load(p/'start.json')
    summary.need(x['key']==entry['key']==row and x['mode']==entry['mode']==mode and
                 x['input_sha256']==entry['input']==bindings[row] and entry['manifest']==manifest and
                 x['job']==entry['job'] and x['pid']==entry['pid'] and x['public_calls']==61,'recovery return identity')
    summary.need(summary.sha(p/'original.jsonl.gz')==x['native_sha256'] and
                 all(summary.load(p/'identity.json')['checks'].values()),'recovery original')
    x['score_sha256']=summary.sha(p/'result.json')
    x['previous_pre_score_return_rejection_job']=failed['job']
    return x


if __name__=='__main__':
    summary.position=read_position
    summary.main()
