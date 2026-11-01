"""Small shared contracts; no experiment drivers or model imports.

Strict parsing and canonical hashes are preserved from the archived execution.
The trace guard blocks accidental use of future physical labels in selection.
"""
import hashlib
import json
import math

def require(value,message):
    if not value:raise ValueError(message)

def strict_json(raw):
    require(isinstance(raw,str),'Raw output must be text')
    def closed(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON object key');result[key]=value
        return result
    def finite(v):
        result=float(v);require(math.isfinite(result),'Nonfinite JSON number');return result
    return json.loads(raw,object_pairs_hook=closed,parse_float=finite,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

class DeniedOnlineTrace:
    def __getattr__(self, name):
        raise RuntimeError('Online controller cannot access physical trace: ' + name)
