"""Resolve the retained corrections, then run the frozen scoring/stratification readback."""
import checked_readback as audited
import bounded_execution as bounded


def lookup(row,mode,bindings,manifest):
    if (row,mode) not in bounded.AFFECTED:return audited.read_position(row,mode,bindings,manifest)
    p=bounded.final_folder(row,mode);s=audited.summary
    original=next(q for q in s.load(s.ROOT/'observation-scope-audit.json')['material_files']
                  if q['key']==row and q['role']==mode)
    s.need(s.sha(p.parent/'original.jsonl.gz')==original['raw_sha256'] and not original['within_contract'],'preserve affected')
    x=s.load(p/'result.json');entry=s.load(p/'start.json')
    s.need(x['key']==entry['key']==row and x['mode']==entry['mode']==mode and
           x['input_sha256']==entry['input']==bindings[row] and entry['manifest']==manifest and
           x['job']==entry['job'] and x['pid']==entry['pid'] and x['public_calls']==61,'recovered slot')
    s.need(s.sha(p/'original.jsonl.gz')==x['native_sha256'] and all(s.load(p/'identity.json')['checks'].values()),'new original')
    x['score_sha256']=s.sha(p/'result.json');x['superseded_observation_attempt_job']=original['job']
    return x


if __name__=='__main__':
    audited.summary.position=lookup
    audited.summary.main()
