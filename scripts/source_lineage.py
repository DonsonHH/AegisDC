"""Preserve a recorded source snapshot while permitting status-only maintenance."""
import ast
from copy import deepcopy
import hashlib


def verify_status_maintenance(current, snapshot, expected_sha256):
    """Validate the original bytes and prove all non-status definitions unchanged."""
    if hashlib.sha256(snapshot).hexdigest() != expected_sha256:
        raise ValueError("Historical source snapshot SHA mismatch")
    old=ast.parse(snapshot.decode('utf-8'));new=ast.parse(current.decode('utf-8'))
    signatures=[]
    for tree in (old,new):
        selected=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='status']
        if len(selected)!=1:raise ValueError("Expected one status function")
        signature=deepcopy(selected[0]);signature.body=[]
        signatures.append(ast.dump(signature,include_attributes=False))
        tree.body=[node for node in tree.body if node is not selected[0]]
    if signatures[0]!=signatures[1]:
        raise ValueError("Status signature or import-time decorator changed")
    if ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):
        raise ValueError("Recorded scientific source changed outside status maintenance")
    return True
