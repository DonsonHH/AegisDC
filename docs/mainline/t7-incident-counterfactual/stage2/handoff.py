"""Read the nominated original exactly once; only its encrypted transport leaves this process."""

import argparse
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("private_transfer_directory", type=Path)
    parser.add_argument("verified_public_key_sha256")
    args = parser.parse_args()
    folder = args.private_transfer_directory
    reg = Path(__file__).resolve().parents[1] / "r1/registration.json"
    registration = reg.read_bytes()
    assert hashlib.sha256(registration).hexdigest() == "27c16e98c6c345630077fd65a5a07e58cb973a15cf0072cb6cc75716c229019f"
    expected = json.loads(registration)["custody"]["sha256"]
    public_bytes = (folder / "transport-public.pem").read_bytes()
    if hashlib.sha256(public_bytes).hexdigest() != args.verified_public_key_sha256:
        raise ValueError("SSH-verified transport key mismatch")
    public_key = serialization.load_pem_public_key(public_bytes)
    with (folder / "original-read-entry").open("x", encoding="ascii") as mark:
        mark.write("one original-file read authorized\n")
    with args.original.open("rb") as src:
        data = bytearray(src.read(33))
    try:
        actual = hashlib.sha256(data).hexdigest()
        receipt = {"raw_bytes": len(data), "expected_sha256": expected, "actual_sha256": actual,
                   "original_file_opens": 1, "matched": len(data) == 32 and actual == expected,
                   "public_transport_key_sha256": args.verified_public_key_sha256,
                   "custody_observation": "用户指定本机主目录中的原件交接。登记前的设备保管情况未独立审计。"}
        if receipt["matched"]:
            encrypted = public_key.encrypt(bytes(data), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                                    algorithm=hashes.SHA256(), label=None))
            with (folder / "h3.sealed").open("xb") as stream:
                stream.write(encrypted)
            receipt["encrypted_sha256"] = hashlib.sha256(encrypted).hexdigest()
        with (folder / "handoff.json").open("xb") as dst:
            dst.write((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
        print("H3 bytes =", len(data), "SHA-256 =", actual, "MATCH =", receipt["matched"])
        if not receipt["matched"]:
            raise SystemExit(2)
    finally:
        data[:] = bytes(len(data))


if __name__ == "__main__":
    main()
