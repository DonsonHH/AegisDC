"""Read-only T8 verifier. The saved request, authority and catalogue come from trusted publications."""

import sys

sys.dont_write_bytecode = True

import argparse
from datetime import datetime
import hashlib
import hmac
import importlib.metadata
import io
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
REGISTRATION = "06ff51c5578f00951c42b4dd2e53cfb4989b0b8be923056332241058d4eb9f3b"
SHARED_FIT = "f8a4d6d320c090a4a74280542df5c864677dcfe78e79638843b1fad86887340f"
SHARED_KEY_FINGERPRINT = "ae9b3a9714961a0f6f7e85288c414107c34df15934d382e97d9e11a947f74cb8"
PANEL_LAW = "222cb1aaca8c2fe565696714981453f4422539b4a9d76c4bec4ea8849ea42a62"
R1_DELIVERY = "adcc122f8d03facd45a48adf18dbd08fbf254c796b9ed84da17fd87da2ebee50"
CRYPTO_VERSION = "44.0.0"
PI, CUSTODIAN = "PENDING_PI", "PENDING_CUSTODIAN"
ROLE_PATTERN = r"^[a-z][a-z0-9_-]{0,31}(?![\s\S])"
ROOT_RULE = {"type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[0-9a-f]{64}$"}
ROLE_RULE = {"type": "string", "minLength": 1, "maxLength": 32, "pattern": ROLE_PATTERN}
REQUEST = {
    "registration_id": {"type": "string", "enum": [REGISTRATION, SHARED_FIT]},
    "split": {"type": "string", "enum": ["FIT", "DEV"]},
    "batch_root": ROOT_RULE, "catalogue_root": ROOT_RULE,
}
RECEIPT = {
    **REQUEST, "custodian_id": ROLE_RULE, "auditor_id": ROLE_RULE,
    "aggregate_coverage_pct": {"type": "integer", "minimum": 0, "maximum": 100},
    "all_required_tests_complete": {"type": "boolean"},
    "decision": {"type": "string", "enum": ["PASS", "BLOCKED"]},
}
FIT_PERCENTAGES = sorted({100 * n // 48 for n in range(49)})
AUTH_FIELDS = {"custodian_id", "auditor_id", "algorithm", "public_key_hex", "fingerprint_sha256",
               "generated_at_utc", "signing_method", "credential_separation", "device_separation"}
SOURCE_BINDINGS = {
    "T3": (0, "legacy"), "T4b": (1, "v3"), "T4c": (2, "v3"),
    "T5-v1": (3, "v3"), "T5-v2": (4, "v3"), "T5-v3a": (5, "v3"), "T5-v3b": (5, "v3"),
    "T5-v3c": (6, "v3"), "T7-stage1": (7, "legacy"), "H3-sealed-index": (8, "sealed"),
}
ENCODINGS = {"legacy": ["historical_full", "legacy_common"], "v3": ["historical_full", "v3_operative"],
             "sealed": ["sealed_full", "sealed_operative"]}
PARTS = {
    "T3": ["engineering", "development"], "T4b": ["original"], "T4c": ["engineering", "development"],
    "T5-v1": ["FIT", "DEV"], "T5-v2": ["FIT", "DEV"], "T5-v3a": ["original"],
    "T5-v3b": ["v3a panel reused"], "T5-v3c": ["v3a panel reused", "new panel"],
    "T7-stage1": ["original incident rows"], "H3-sealed-index": ["pre-score index"],
}
REUSE = {"T5-v3b": "T5-v3a", "T5-v3c": "first part reuses T5-v3a", "T7-stage1": "subset of T3"}


class Invalid(ValueError):
    pass


def need(condition):
    if not condition:
        raise Invalid("Invalid public record")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def is_root(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def is_role(value):
    return isinstance(value, str) and re.fullmatch(ROLE_PATTERN, value) is not None


def exact_keys(obj, keys):
    need(type(obj) is dict and set(obj) == set(keys))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def parse(raw):
    def unique(pairs):
        result = dict(pairs)
        need(len(result) == len(pairs))
        return result

    def reject_number(_):
        raise Invalid("Expected an integer")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_float=reject_number, parse_constant=reject_number)


def wire(raw):
    # The largest canonical nine-field payload is shorter than one KiB.
    need(len(raw) <= 1024)
    obj = parse(raw)
    need(raw == canonical(obj) + b"\n")
    return obj


def read_wire(path):
    with path.open("rb") as stream:
        return wire(stream.read(1025))


def pinned(path, digest):
    raw = path.read_bytes()
    need(sha(raw) == digest)
    return raw


def conditions():
    def when(field, value, constraints):
        return {"if": {"properties": {field: {"const": value}}}, "then": {"properties": constraints}}
    return [
        when("split", "FIT", {"aggregate_coverage_pct": {"enum": FIT_PERCENTAGES}}),
        when("all_required_tests_complete", True, {"aggregate_coverage_pct": {"const": 100}}),
        when("decision", "PASS", {"aggregate_coverage_pct": {"const": 100},
                                  "all_required_tests_complete": {"const": True}}),
    ]


def check_schemas():
    shared_split = {"if": {"properties": {"registration_id": {"const": SHARED_FIT}}},
                    "then": {"properties": {"split": {"const": "FIT"}}}}
    for name, fields in (("request", REQUEST), ("receipt", RECEIPT)):
        doc = parse((HERE / (name + ".schema.json")).read_bytes())
        expected = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": f"T8 {name} public payload", "type": "object", "additionalProperties": False,
                    "required": list(fields), "properties": fields, "allOf": [shared_split]}
        if name == "receipt":
            expected["allOf"].extend(conditions())
        need(canonical(doc) == canonical(expected))


def validate_request(request):
    exact_keys(request, REQUEST)
    need(request["registration_id"] in (REGISTRATION, SHARED_FIT) and request["split"] in ("FIT", "DEV"))
    if request["registration_id"] == SHARED_FIT:
        need(request["split"] == "FIT")
    need(is_root(request["batch_root"]) and is_root(request["catalogue_root"]))


def validate_receipt(receipt):
    exact_keys(receipt, RECEIPT)
    validate_request({k: receipt[k] for k in REQUEST})
    need(is_role(receipt["custodian_id"]) and is_role(receipt["auditor_id"]) and
         receipt["custodian_id"] != receipt["auditor_id"])
    pct, complete, decision = (receipt[k] for k in ("aggregate_coverage_pct", "all_required_tests_complete", "decision"))
    need(type(pct) is int and 0 <= pct <= 100 and type(complete) is bool and decision in ("PASS", "BLOCKED"))
    if receipt["split"] == "FIT":
        need(pct in FIT_PERCENTAGES)
    if complete:
        need(pct == 100)
    if decision == "PASS":
        need(complete and pct == 100)


def registration_for(authority):
    if authority["credential_separation"] == "shared_account":
        need(authority["fingerprint_sha256"] == SHARED_KEY_FINGERPRINT and
             authority["device_separation"] == "pi_local_no_device_separation")
        return SHARED_FIT
    need(authority["credential_separation"] == "independent" and
         authority["fingerprint_sha256"] != SHARED_KEY_FINGERPRINT)
    return REGISTRATION


def verify_shared_pairing(key):
    stage = HERE.parent / "stage1b"
    amendment = parse(pinned(stage/"fit-shared-account.json", SHARED_FIT))
    need(amendment["parent_registration_sha256"] == REGISTRATION and
         amendment["public_key_fingerprint_sha256"] == sha(key) == SHARED_KEY_FINGERPRINT)
    pair = stage / "key-pairing" / "ef37ca0e-challenge.txt"
    original = pinned(pair, amendment["pairing_challenge_sha256"])
    verify_signature(key, pair.with_suffix(".sig").read_bytes(), original)


def authority_key(authority, engineering_keys):
    exact_keys(authority, AUTH_FIELDS)
    need(PI not in authority.values())
    custodian, auditor = authority["custodian_id"], authority["auditor_id"]
    need(is_role(custodian) and is_role(auditor) and custodian != auditor)
    need(authority["algorithm"] == "Ed25519" and authority["signing_method"] == "detached")
    registered = registration_for(authority)
    need(authority["device_separation"] in ("separate_device", "pi_local_no_device_separation"))
    timestamp = authority["generated_at_utc"]
    need(type(timestamp) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", timestamp))
    datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    need(is_root(authority["public_key_hex"]) and is_root(authority["fingerprint_sha256"]))
    raw = bytes.fromhex(authority["public_key_hex"])
    need(hmac.compare_digest(sha(raw), authority["fingerprint_sha256"]) and raw not in engineering_keys)
    if registered == SHARED_FIT:
        verify_shared_pairing(raw)
    return raw


def catalogue(doc, authority, *, template):
    exact_keys(doc, {"registration_id", "count_source", "issued_by", "catalogue_root",
                     "additional_realizations_and_aliases_reconciled", "sources"})
    need(doc["registration_id"] in (REGISTRATION, SHARED_FIT) and doc["count_source"] == "../r0/panel-law.json#/historical_catalogue")
    if not (template and authority["credential_separation"] == PI):
        need(doc["registration_id"] == registration_for(authority))
    if template:
        need(all(doc[k] == CUSTODIAN for k in ("issued_by", "catalogue_root", "additional_realizations_and_aliases_reconciled")))
    else:
        need(is_root(doc["catalogue_root"]) and doc["issued_by"] == authority["custodian_id"] and
             doc["additional_realizations_and_aliases_reconciled"] is True)
    # Only the frozen public count references are read. No path named by a historical entry is opened.
    reference = parse(pinned(HERE.parent/"r0"/"panel-law.json", PANEL_LAW))["historical_catalogue"]
    sources = doc["sources"]
    need(type(sources) is list and len(sources) == len(SOURCE_BINDINGS))
    need({s["source"] for s in sources} == set(SOURCE_BINDINGS))
    for s in sources:
        exact_keys(s, {"source", "count_reference", "reference_revision", "parts", "registered_counts",
                       "required_encodings", "recorded_reuse", "custodian"})
        index, family = SOURCE_BINDINGS[s["source"]]
        row = reference["entries"][index]
        counts = row["counts"]
        need(s["count_reference"] == f"entries/{index}/counts" and
             s["reference_revision"] == row.get("revision", reference["reference_revision_except_H3"]))
        need(canonical(s["registered_counts"]) == canonical(counts) and s["parts"] == PARTS[s["source"]] and
             s["recorded_reuse"] == REUSE.get(s["source"]) and s["required_encodings"] == ENCODINGS[family])
        att = s["custodian"]
        exact_keys(att, {"version", "expected_counts", "identity_encodings"})
        if template:
            need(all(value == CUSTODIAN for value in att.values()))
        else:
            need(type(att["version"]) is str and att["version"] not in (PI, CUSTODIAN) and
                 re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+-]{0,79}", att["version"]))
            need(canonical(att["expected_counts"]) == canonical(counts) and att["identity_encodings"] == ENCODINGS[family])
    return doc["catalogue_root"]


def bound(request, receipt, authority, catalogue_root):
    validate_request(request)
    validate_receipt(receipt)
    need(all(request[k] == receipt[k] for k in REQUEST))
    need(request["registration_id"] == registration_for(authority))
    need(request["catalogue_root"] == catalogue_root)
    need(all(receipt[k] == authority[k] for k in ("custodian_id", "auditor_id")))


def engineering_evidence():
    """Prior public engineering signers are excluded from the PI trust anchor."""
    folder = HERE.parent / "r1"
    inventory = parse(pinned(folder/"delivery.json", R1_DELIVERY))["artifacts"]
    keys = set()
    example = None
    for name in ("standin-failed-135555.tar.gz", "standin-records.tar.gz"):
        blob = pinned(folder/name, inventory[name]["sha256"])
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
            def member(path):
                stream = archive.extractfile(path)
                need(stream is not None)
                with stream:
                    return stream.read()

            for path in archive.getnames():
                if re.fullmatch(r"records/[a-z-]+/case\.json", path):
                    info = json.loads(member(path))
                    keys.update(bytes.fromhex(info[k]) for k in ("journal_key", "score_key"))
            if name == "standin-records.tar.gz":
                ref = json.loads(member("records/gain/events/0001.json"))
                need(is_root(ref["sha256"]) and ref["locator"] == "objects/" + ref["sha256"])
                raw = member("records/gain/" + ref["locator"])
                need(sha(raw) == ref["sha256"] and len(raw) == ref["bytes"])
                envelope = json.loads(raw)
                example = (bytes.fromhex(envelope["signer"]), bytes.fromhex(envelope["signature"]),
                           canonical(envelope["payload"]))
    need(example is not None and example[0] in keys and len(keys) == 22)
    return keys, example


def verify_signature(key, signature, message):
    from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    need(importlib.metadata.version("cryptography") == CRYPTO_VERSION)
    need(len(key) == 32 and len(signature) == 64)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, message)
    except (InvalidSignature, UnsupportedAlgorithm):
        raise Invalid("Signature not verified") from None


def expect_invalid(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError("Negative control unexpectedly passed")


def self_check(authority, declaration):
    check_schemas()
    request = {"registration_id": REGISTRATION, "split": "FIT",
               "batch_root": sha(b"format check only: batch"), "catalogue_root": sha(b"format check only: catalogue")}
    roles = {"custodian_id": "format-custodian", "auditor_id": "format-auditor"}
    ids = {**roles, "credential_separation": "independent", "fingerprint_sha256": sha(b"format-only role")}
    receipt = {**request, **roles, "aggregate_coverage_pct": 100, "all_required_tests_complete": True, "decision": "PASS"}
    for obj, check in ((request, validate_request), (receipt, validate_receipt)):
        check(wire(canonical(obj) + b"\n"))
        for field in obj:
            expect_invalid(check, {k: v for k, v in obj.items() if k != field})
        for extra in ("peer_hash", "matched_identity", "family", "source_counts", "old_index", "failure_detail", "signature"):
            expect_invalid(check, {**obj, extra: "unused"})
        expect_invalid(check, {**obj, "batch_root": {"value": request["batch_root"]}})
        expect_invalid(check, {**obj, "catalogue_root": request["catalogue_root"]+"\n"})
        expect_invalid(wire, canonical(obj))
        expect_invalid(wire, canonical(obj) + b" \n")
    duplicate = canonical(request).replace(b'"split":"FIT"', b'"split":"FIT","split":"FIT"')
    expect_invalid(wire, duplicate + b"\n")
    print("PASS request schema: 4 required fields; closed payload, duplicate keys and noncanonical bytes checked")
    for split in ("FIT", "DEV"):
        req = {**request, "split": split}
        pos = {**receipt, "split": split}
        for reply in (pos, {**pos, "decision": "BLOCKED"},
                      {**pos, "decision": "BLOCKED", "aggregate_coverage_pct": 50, "all_required_tests_complete": False}):
            bound(req, reply, ids, req["catalogue_root"])
    for bad in ({"decision":"PASS", "all_required_tests_complete":False}, {"aggregate_coverage_pct":99},
                {"aggregate_coverage_pct": True}, {"aggregate_coverage_pct": 100.0},
                {"decision":"BLOCKED", "aggregate_coverage_pct":50}, {"custodian_id":"format\n"},
                {"auditor_id":ids["custodian_id"]},
                {"decision":"BLOCKED", "aggregate_coverage_pct":99, "all_required_tests_complete":False}):
        expect_invalid(validate_receipt, {**receipt, **bad})
    for field, wrong in (("registration_id","other"), ("split","DEV"), ("batch_root",request["catalogue_root"]),
                         ("catalogue_root",request["batch_root"]), ("custodian_id","other"), ("auditor_id","other")):
        expect_invalid(bound, request, {**receipt, field:wrong}, ids, request["catalogue_root"])
    expect_invalid(bound, request, receipt, ids, request["batch_root"])
    shared_ids = {**roles, "credential_separation": "shared_account", "fingerprint_sha256": SHARED_KEY_FINGERPRINT,
                  "device_separation": "pi_local_no_device_separation"}
    shared_request = {**request, "registration_id": SHARED_FIT}
    shared_receipt = {**receipt, "registration_id": SHARED_FIT}
    bound(shared_request, shared_receipt, shared_ids, request["catalogue_root"])
    expect_invalid(bound, shared_request, shared_receipt, ids, request["catalogue_root"])
    expect_invalid(bound, request, receipt, shared_ids, request["catalogue_root"])
    expect_invalid(registration_for, {**shared_ids, "credential_separation": "independent"})
    expect_invalid(validate_request, {**shared_request, "split": "DEV"})
    print("PASS receipt schema: 9 required fields; coverage, BLOCKED and registration-specific trust checked")
    keys, example = engineering_evidence()
    exact_keys(authority, AUTH_FIELDS)
    pending = all(v == PI for v in authority.values())
    if pending:
        expect_invalid(authority_key, authority, keys)
    else:
        authority_key(authority, keys)
    if not pending and registration_for(authority) == SHARED_FIT:
        print("PAIRING VERIFIED; shared-account FIT, procedural custody")
    else:
        print("PASS authority: " + ("all 9 fields PENDING_PI; formal verification unavailable" if pending else "published field format checked"))
    template = declaration["catalogue_root"] == CUSTODIAN
    if not template:
        need(not pending)
    catalogue(declaration, authority, template=template)
    # Use only public r0 baselines to exercise the publication format. Nothing is signed or saved.
    public_rows = [
        {**s, "custodian": {"version": s["reference_revision"], "expected_counts": s["registered_counts"],
                            "identity_encodings": s["required_encodings"]}} for s in declaration["sources"]
    ]
    publication = {**declaration, "registration_id": REGISTRATION, "sources": public_rows, "issued_by": ids["custodian_id"],
                   "catalogue_root": request["catalogue_root"], "additional_realizations_and_aliases_reconciled": True}
    need(catalogue(publication, ids, template=False) == request["catalogue_root"])
    expect_invalid(catalogue, {**publication, "sources": public_rows[:-1]}, ids, template=False)
    expect_invalid(catalogue, {**publication, "additional_realizations_and_aliases_reconciled": False}, ids, template=False)
    wrong_encoding = {**public_rows[0], "custodian": {**public_rows[0]["custodian"], "identity_encodings": []}}
    expect_invalid(catalogue, {**publication, "sources": [wrong_encoding, *public_rows[1:]]}, ids, template=False)
    print("PASS catalogue: 10 named sources checked against r0 count references; " +
          ("custodian declarations pending" if template else "published declaration fields checked"))
    key, signature, original = example
    verify_signature(key, signature, original)
    expect_invalid(verify_signature, key, signature, original + b" ")
    expect_invalid(verify_signature, key, bytes([signature[0] ^ 1]) + signature[1:], original)
    expect_invalid(verify_signature, key, signature, canonical(receipt))
    dummy_authority = {**ids, "algorithm":"Ed25519", "signing_method":"detached", "credential_separation":"independent",
                       "device_separation":"pi_local_no_device_separation", "generated_at_utc":"2000-01-01T00:00:00Z",
                       "public_key_hex":key.hex(), "fingerprint_sha256":sha(key)}
    expect_invalid(authority_key, dummy_authority, keys)
    print(f"PASS Ed25519 / cryptography {CRYPTO_VERSION}: archived engineering signature verified; "
          "message change, signature change and cross-use rejected; engineering signers excluded")
    print("SELF-CHECK ONLY; no official request, receipt, signature creation or file write")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="offline, read-only skeleton self-check")
    parser.add_argument("--request", type=Path, help="the saved original public request")
    parser.add_argument("--receipt", type=Path, help="the received public payload")
    parser.add_argument("--signature", type=Path, help="the detached binary signature")
    args = parser.parse_args()
    attachments = (args.request, args.receipt, args.signature)
    if (args.check and any(attachments)) or (not args.check and not all(attachments)):
        parser.error("use --check alone, or provide the original request, receipt and detached signature")
    try:
        authority = parse((HERE/"authority.json").read_bytes())
        declaration = parse((HERE/"catalogue-coverage.json").read_bytes())
        need(type(authority) is dict and type(declaration) is dict)
        if args.check:
            self_check(authority, declaration)
            return 0
        check_schemas()
        if PI in authority.values():
            print("NOT READY: authority pending")
            return 1
        keys, _ = engineering_evidence()
        key = authority_key(authority, keys)
        if declaration.get("catalogue_root") == CUSTODIAN:
            print("NOT READY: catalogue coverage pending")
            return 1
        catalogue_root = catalogue(declaration, authority, template=False)
        request = read_wire(args.request)
        receipt = read_wire(args.receipt)
        bound(request, receipt, authority, catalogue_root)
        with args.signature.open("rb") as stream:
            verify_signature(key, stream.read(65), canonical(receipt))
        qualifier = "PROCEDURAL " if receipt["registration_id"] == SHARED_FIT else ""
        print("VERIFIED " + qualifier + receipt["decision"])
        return 0 if receipt["decision"] == "PASS" else 3
    except (ValueError, KeyError, TypeError, OSError, ImportError, RecursionError, tarfile.TarError):
        # Never echo private paths, unexpected field names, untrusted payload values, or source-specific diagnostics.
        print("UNVERIFIED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
