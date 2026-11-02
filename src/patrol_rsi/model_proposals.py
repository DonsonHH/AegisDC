"""Finite offline Qwen worker for a Slurm allocation, never a public service.

Run this file directly in the separate frozen inference environment. It does not
import the simulation, receive confirmation data, or execute generated text.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha_file(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def completed_request(folder, index, protocol_sha):
    request_path = folder / f"request-{index:02d}.json"
    response_path = folder / f"response-{index:02d}.json"
    started_path = folder / f"started-{index:02d}.json"
    if response_path.exists():
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if (response["protocol_sha256"] != protocol_sha or request["protocol_sha256"] != protocol_sha
                or response["call_index"] != index or request["call_index"] != index
                or response["request_sha256"] != sha_file(request_path)
                or response["status"] not in ("completed", "failed")):
            raise ValueError("Completed response identity mismatch")
        return request
    if started_path.exists():
        raise RuntimeError("Ambiguous started-only call; inspect its terminal job before resolving, never regenerate")
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--mailbox", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Run inference only inside a Slurm allocation")
    folder, model_path = Path(args.mailbox), Path(args.model)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_sha = sha_file(protocol_path)
    settings = protocol["model"]
    folder.mkdir(parents=True, exist_ok=True)
    metadata = {"status": "checking_weights", "job_id": os.environ.get("SLURM_JOB_ID"),
                "hostname": socket.gethostname(), "protocol_sha256": protocol_sha,
                "worker_sha256": sha_file(Path(__file__)), "model": settings["id"], "revision": settings["revision"]}
    save(folder / "worker.json", metadata)
    manifest_path = model_path / "verified_manifest.json"
    if sha_file(manifest_path) != settings["manifest_sha256"]:
        raise ValueError("Model manifest differs from pre-registration")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["revision"] != settings["revision"] or manifest["id"] != settings["id"]:
        raise ValueError("Wrong model revision")
    for entry in manifest["files"]:
        path = model_path / entry["file"]
        if path.parent != model_path or path.stat().st_size != entry["bytes"] or sha_file(path) != entry["sha256"]:
            raise ValueError("Frozen model file failed verification: " + entry["file"])
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    import transformers
    import numpy
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if (torch.__version__, transformers.__version__, numpy.__version__) != (
            settings["torch"], settings["transformers"], settings["model_numpy"]):
        raise ValueError("Inference environment differs from pre-registration")
    if not torch.cuda.is_available():
        raise RuntimeError("GPU required; no silent CPU fallback")
    metadata.update(status="loading", torch=torch.__version__, transformers=transformers.__version__,
                    numpy=numpy.__version__, gpu=torch.cuda.get_device_name(0),
                    device_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
                    model_files_verified=len(manifest["files"]))
    save(folder / "worker.json", metadata)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.float16,
                attn_implementation="eager", local_files_only=True).to("cuda").eval()
    metadata["status"] = "ready"
    save(folder / "worker.json", metadata)
    print("READY", metadata, flush=True)
    run_id = None
    for index in range(protocol["limits"]["model_calls"]):
        request_path = folder / f"request-{index:02d}.json"
        response_path = folder / f"response-{index:02d}.json"
        started_path = folder / f"started-{index:02d}.json"
        cached = completed_request(folder, index, protocol_sha)
        if cached is not None:
            if run_id is not None and cached["run_id"] != run_id:
                raise ValueError("Cannot mix requests from different study runs")
            run_id = cached["run_id"]
            print("VERIFIED_COMPLETED_CALL", index, flush=True)
            continue
        deadline = time.monotonic() + 1200
        while not request_path.exists():
            if time.monotonic() > deadline:
                raise TimeoutError("No next request; stop allocation instead of waiting indefinitely")
            time.sleep(1)
        if started_path.exists() or response_path.exists():
            raise RuntimeError("Another worker already claimed this request")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if request["protocol_sha256"] != protocol_sha or request["call_index"] != index:
            raise ValueError("Wrong request identity")
        if run_id is not None and request["run_id"] != run_id:
            raise ValueError("Cannot mix requests from different study runs")
        run_id = request["run_id"]
        metadata["run_id"] = run_id
        save(folder / "worker.json", metadata)
        with started_path.open("x", encoding="utf-8") as stream:
            json.dump({"call_index": index, "protocol_sha256": protocol_sha, "status": "started"}, stream)
        result = {"call_index": index, "protocol_sha256": protocol_sha,
                  "request_sha256": sha_file(request_path), "job_id": metadata["job_id"]}
        started = time.perf_counter()
        try:
            torch.manual_seed(request["seed"])
            torch.cuda.manual_seed_all(request["seed"])
            text = tokenizer.apply_chat_template(request["messages"], tokenize=False,
                                                  add_generation_prompt=True, enable_thinking=False)
            inputs = tokenizer([text], return_tensors="pt").to("cuda")
            torch.cuda.reset_peak_memory_stats()
            with torch.inference_mode():
                generated = model.generate(**inputs, do_sample=True, temperature=settings["temperature"],
                    top_p=settings["top_p"], top_k=settings["top_k"], max_new_tokens=settings["max_new_tokens"],
                    max_time=240, pad_token_id=tokenizer.pad_token_id)
            output = generated[0, inputs["input_ids"].shape[-1]:]
            result.update(status="completed", raw=tokenizer.decode(output, skip_special_tokens=True),
                          input_tokens=int(inputs["input_ids"].shape[-1]), output_tokens=int(output.shape[0]),
                          peak_gpu_bytes=torch.cuda.max_memory_allocated())
        except Exception as exc:
            result.update(status="failed", error=f"{type(exc).__name__}: {exc}", raw="")
        result["elapsed_s"] = time.perf_counter() - started
        save(response_path, result)
        print("CALL", index, result["status"], result["elapsed_s"], flush=True)
    metadata["status"] = "completed"
    save(folder / "worker.json", metadata)


if __name__ == "__main__":
    main()
