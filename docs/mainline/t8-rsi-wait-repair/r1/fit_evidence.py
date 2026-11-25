"""Immutable FIT evidence objects, authenticated packets and ordered record seals."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import time_ns

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from fit_program import canonical, fingerprint, require


class Objects:
    def __init__(self, root):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=False)
        (self.root/"objects").mkdir()
        (self.root/"events").mkdir()
        (self.root/"rounds").mkdir()

    def put(self, value):
        raw=canonical(value);h=hashlib.sha256(raw).hexdigest()
        loc="objects/"+h;dest=self.root/loc
        if dest.exists():
            require(dest.read_bytes()==raw,"content-addressed object disagreement")
        else:
            with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as fp:
                fp.write(raw);fp.flush();os.fsync(fp.fileno())
            try:
                try:os.link(fp.name,dest)
                except FileExistsError:require(dest.read_bytes()==raw,"concurrent object disagreement")
            finally:os.unlink(fp.name)
        return {"sha256":h,"bytes":len(raw),"locator":loc}

    def get(self, reference):
        return dereference(self.root,reference)


def dereference(root, ref):
    require(set(ref)=={"sha256","bytes","locator"} and len(ref["sha256"])==64 and
            ref["locator"]=="objects/"+ref["sha256"] and
            all(c in "0123456789abcdef" for c in ref["sha256"]),"invalid sidecar locator")
    raw=(root/ref["locator"]).read_bytes()
    require(len(raw)==ref["bytes"] and hashlib.sha256(raw).hexdigest()==ref["sha256"],"sidecar integrity")
    return json.loads(raw)


def exclusive(path,value):
    # All existing journals/records must survive an interrupted or repeated invocation.
    with path.open("xb") as f:
        f.write(canonical(value)+b"\n");f.flush();os.fsync(f.fileno())


def public_hex(key):
    return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()


def signed(key,payload):
    return {"payload":payload,"signature":key.sign(canonical(payload)).hex(),"signer":public_hex(key)}


def authenticated(box, public_key):
    require(set(box)=={"payload","signature","signer"} and box["signer"]==public_key,"wrong receipt authority")
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(bytes.fromhex(box["signature"]),canonical(box["payload"]))
    return box["payload"]


class Journal:
    """The signer is injected. The engineering fixture uses a clearly labelled test signer."""
    def __init__(self,store,key,context):
        self.store=store;self.key=key;self.context=context;self.head=None;self.seq=0

    def seal(self,purpose,body):
        self.seq+=1
        envelope=signed(self.key,{"context":self.context,"sequence":self.seq,"time_ns":time_ns(),"previous":self.head,
                                  "purpose":purpose,"body":body})
        ref=self.store.put(envelope)
        exclusive(self.store.root/"events"/f"{self.seq:04}.json",ref)
        self.head=ref["sha256"]
        return ref

    def round(self,record,validate):
        payload_hash=fingerprint(record)
        record["audit"]["record_seal"]=self.seal("round",{"arm":record["arm"],"round":record["round"],"payload_sha256":payload_hash})
        validate(record)
        ref=self.store.put(record)
        exclusive(self.store.root/"rounds"/f"{record['arm']}-{record['round']}.json",record)
        return ref["sha256"]
