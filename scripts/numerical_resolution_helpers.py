"""Pure-data helpers for the explicitly expanded v3 numeric domain."""
from copy import deepcopy


def check_extension(original,updated):
    first,second=deepcopy(original),deepcopy(updated)
    a=next(row for row in first['parameters'] if row['id']=='step_time')
    b=next(row for row in second['parameters'] if row['id']=='step_time')
    if a['valid_range'][0]!=.01 or b['valid_range'][0]!=.00125 or a['valid_range'][1]!=b['valid_range'][1]:
        raise ValueError('Unexpected numeric domain extension')
    for record in (a,b):
        for key in ('valid_range','basis','source_note'):del record[key]
    if first!=second:raise ValueError('Physical value or undeclared scenario field changed')
