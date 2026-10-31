"""Explicit compact model contract; fixed metadata belongs to the interface."""
from patrol_rsi.meta_schema import strict_json
from patrol_rsi.multistep_workflow import compile_edit


def compile_compact(raw, parent):
    value = strict_json(raw)
    if not isinstance(value, dict) or set(value) != {'changes', 'mechanism'}:
        raise ValueError('Compact-v1 requires exactly changes and mechanism')
    envelope = dict(schema='workflow-edit-v1', parent_sha256=parent.sha256, **value)
    return compile_edit(parent, envelope), envelope
