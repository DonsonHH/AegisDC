"""Declared binary64 time-coordinate convention, never a physical tolerance.

An event within eight ulps of an epoch is due at that epoch. This bounded
coincidence convention prevents arithmetic spelling from adding a full PLC
period. Raw requested times remain in inputs/events; applied_at_s records the
actual processing epoch. Distinct times outside this window remain ordered.
"""
import math

TIME_COORDINATE_CONVENTION = {
    'version': 'aegisdc-binary64-time-v1',
    'coincidence_ulps': 8,
    'clock': 'PLC epoch n*fixed_period anchored at zero; one sample per epoch',
    'event_anchor': 'current processing time, fixed while processing due events; never a rolling adjacent-event chain',
    'requested_time': 'raw binary64 time_s retained; applied_at_s records processing time',
    'scope': 'numerical time coordinates only; not physical state clipping or real equipment clock resolution',
}


def same_time(first, second):
    """Whether finite time coordinates differ only within eight binary64 ulps."""
    return (math.isfinite(first) and math.isfinite(second)
            and abs(first - second) <= 8 * max(math.ulp(first), math.ulp(second)))


def time_due(now, scheduled):
    """Process a past or numerically coincident scheduled epoch once."""
    return now >= scheduled or same_time(now, scheduled)
