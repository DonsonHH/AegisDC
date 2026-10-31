"""Live dispatch checks for a fixed owner; original ReturnPlan is unchanged."""
from .coverage_plan import InfeasibleCoverage
from .facility_observation import eligible


def certify_dispatch(plan, agent, target, clock, last, cursor, reserved, remaining):
    """Always recompute from current position, stamps and cumulative schedule."""
    if agent['task'] is not None or target not in agent['allowed'] or target not in plan.tour:
        raise InfeasibleCoverage('Busy inspector or task outside its original ownership')
    if target in reserved or not eligible(agent['role'], plan.tasks[target]):
        raise InfeasibleCoverage('Reservation, profession or access conflict')
    optional = target != plan.tour[cursor]
    if optional and remaining <= 0:
        raise InfeasibleCoverage('Global extra-check budget exhausted')
    if clock + plan.travel_service(agent['position'], target) > 1800.:
        raise InfeasibleCoverage('Path/service cannot finish in this episode')
    certificate = plan.check(clock, agent['position'], last, cursor, target)
    if not certificate['ok']:
        raise InfeasibleCoverage('Current candidate and full return round are not jointly feasible')
    return certificate
