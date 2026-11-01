"""Repository acceptance: code contracts, readable entry points and old evidence."""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest


def check_structure(root: Path):
    required = ["README.md", "docs/RESEARCH.md", "docs/ARCHITECTURE.md", "docs/EVIDENCE.md", "docs/NEXT.md",
                "configs/demo.json", "configs/parent-rule.json", "configs/candidate-example.json",
                "cleanup.json", "evidence/provenance.json", "evidence/migration.json", "scripts/verify_evidence.py"]
    missing = [p for p in required if not (root / p).is_file()]
    if missing:
        raise ValueError("Missing maintained entry points: " + ", ".join(missing))
    for old in ("research", "reports", "cluster", "CURRENT_RESEARCH.md", "CONTEXT.md"):
        if (root / old).exists():
            raise ValueError("Historical parallel entry point restored to active tree: " + old)
    package = root / "src/patrol_rsi"
    files = sorted(package.glob("*.py"))
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                target = package / (node.module.split(".")[0] + ".py")
                if not target.is_file():
                    raise ValueError(f"Dangling historical import: {path.name}: {node.module}")
    for path in [root / "README.md", *sorted((root / "docs").glob("*.md")), root / "evidence/README.md"]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            if not (path.parent / target).exists():
                raise ValueError(f"Broken local documentation link: {path.name}: {target}")
    cleanup = json.loads((root / "cleanup.json").read_text(encoding="utf-8"))
    if cleanup["source_commit"] != "f2c20b3a642ff1df9426e523614d3da9a5cf1129":
        raise ValueError("Unrecognized cleanup baseline")
    return {"status": "PASS", "source_modules": len(files), "historical_parallel_entry_points": 0,
            "local_document_links": "checked", "scope": "Structural integrity, not scientific effectiveness"}


def verify(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    sys.path.insert(0, str(root / "src"))
    result = {"engineering": "FAIL", "evidence": "FAIL", "research": "NOT_RUN",
              "historical_research_gain": "NOT_ESTABLISHED", "overall": "FAIL",
              "output_directory": str(output),
              "scope": "Engineering regression and saved-evidence recomputation; no research training or LLM calls"}
    try:
        result["structure"] = check_structure(root)
        stream = io.StringIO()
        suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
        with redirect_stdout(stream), redirect_stderr(stream):
            tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        (output / "tests.log").write_text(stream.getvalue(), encoding="utf-8")
        result["tests"] = {"run": tested.testsRun, "failures": len(tested.failures),
                           "errors": len(tested.errors), "skipped": len(tested.skipped)}
        numeric = []
        for line in stream.getvalue().splitlines():
            if "migration_numeric " not in line:
                continue
            detail = json.loads(line.split("migration_numeric ", 1)[1])
            comparisons = detail.get("comparisons") or {"public_history_inputs": detail["public_history_inputs"]}
            numeric.append({"case": detail["case"], "maximum_absolute_by_quantity":
                            {key: value["maximum_absolute"] for key, value in comparisons.items()}})
        result["numeric_regression"] = {"details": "tests.log", "observed_errors": numeric}
        result["engineering"] = "PASS" if tested.wasSuccessful() and tested.testsRun > 0 and not tested.skipped else "FAIL"
        if result["engineering"] == "FAIL":
            result["test_details"] = stream.getvalue()
        spec = importlib.util.spec_from_file_location("saved_evidence_verifier", root / "scripts/verify_evidence.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        evidence = verifier.verify(root)
        (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        result["evidence"] = evidence["evidence_integrity"]
        result["verified_original_files"] = evidence.get("verified_original_files")
        result["optional_neural_checkpoint_replay"] = "NOT_RUN: frozen private checkpoints were not supplied"
        result["overall"] = "PASS" if result["engineering"] == result["evidence"] == "PASS" else "FAIL"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result
