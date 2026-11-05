"""Conservative common admission ledger; actual plant costs remain separate."""
from fractions import Fraction
from .evidence_ledger import _fields,_require,_finite,_text,_derived_number

DIMENSIONS=('person_s','tool_s','cost')

def _state(frame,program,history,candidates):
    budget=program['resource_budget'];_fields(budget,set(DIMENSIONS)|{'cost_unit'},'Common cumulative policy budget')
    _text(budget['cost_unit'],'Declared policy cost unit')
    for key in DIMENSIONS:
        _finite(budget[key],'Common budget '+key);_require(budget[key]>=0,'Negative common policy budget')
    interfaces={i['id']:i for i in frame['nominal_knowledge']['work_interfaces']};reservations={}
    for candidate in candidates.values():
        _finite(candidate['issue_cost'],'Declared task issue cost');_require(candidate['issue_cost']>=0,'Negative task issue cost')
        task=candidate['task'];window=Fraction(task['deadline_s'])-Fraction(candidate['available_at_s'])
        _require(window>=0,'Declared candidate deadline precedes availability')
        interface=interfaces[task['work_interface_id']]
        # Admission reserves the whole declared availability-to-deadline window.
        # It bounds any accepted task's elapsed crew/tool occupation conservatively;
        # a completed/aborted report releases concurrency, not this spent envelope.
        reservations[candidate['id']]=dict(person_s=window*len(task['crew']),tool_s=window*len(interface['tool_ids']),
            cost=Fraction(candidate['issue_cost']))
    spent={key:sum((reservations[row['candidate_id']][key] for row in history['issued']),Fraction(0)) for key in DIMENSIONS}
    _require(all(spent[k]<=Fraction(budget[k]) for k in DIMENSIONS),'Issued history already exceeds common cumulative budget')
    remaining={key:Fraction(budget[key])-spent[key] for key in DIMENSIONS}
    return reservations,spent,remaining,budget['cost_unit']


class AdmissionBudget:
    """One exact public-declaration account for issue and continuation gates."""
    def __init__(self,frame,program,history,candidates):
        self.reservations,self.spent,self.remaining,self.cost_unit=_state(frame,program,history,candidates)

    def can_reserve(self,candidate_ids):
        return all(sum((self.reservations[candidate_id][key] for candidate_id in candidate_ids),Fraction(0))
            <=self.remaining[key] for key in DIMENSIONS)

    def audit(self,audits):
        plain=lambda values:{k:_derived_number(v,'Public budget '+k) for k,v in values.items()}
        for audit in audits:
            demand=self.reservations[audit['candidate_id']];audit['declared_resource_reservation']=plain(demand)
            if not self.can_reserve([audit['candidate_id']]):audit['reasons'].append('COMMON_CUMULATIVE_BUDGET_EXHAUSTED')
            audit['reasons']=sorted(set(audit['reasons']));audit['eligible']=not audit['reasons']
        return dict(spent_or_reserved=plain(self.spent),remaining=plain(self.remaining),cost_unit=self.cost_unit,
            basis='COMMON_FULL_DECLARED_TASK_WINDOW_ENVELOPE_NOT_MEASURED_COST',terminal_report_refund=False,
            actual_person_and_tool_time='REPORTED_SEPARATELY_BY_PLANT_BALANCES')


def account(frame,program,history,candidates,audits):
    return AdmissionBudget(frame,program,history,candidates).audit(audits)
