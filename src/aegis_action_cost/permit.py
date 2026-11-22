"""One signed change window shared by every crew. All arguments are public."""
import public_work


def exposure(public_view):
    values={r['value'] for r in public_work.live(public_view,'order') if r['value'].startswith('OPEN/MAINT-')}
    if not values:
        return 0
    if len(values)!=1:
        raise ValueError('Inconsistent signed maintenance limits')
    return int(values.pop().split('-')[-1])


def release(issued, recovery):
    return max((r['planned_end']+recovery for r in issued if r['phase']=='A'), default=0)


class Gate:
    def __init__(self, recovery):
        self.recovery=recovery

    def __getattr__(self, name):
        return getattr(public_work,name)

    def admit(self, pub, view, subject, phase, slot=None):
        request,reason=public_work.admit(pub,view,subject,phase,slot)
        if request and phase=='A' and view['time']<release(view['issued'],self.recovery):
            return None,'MAINTENANCE_CHANGE_BUSY'
        return request,reason
