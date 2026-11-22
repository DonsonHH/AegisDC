"""Bind the accepted comparison and failure criteria by source file."""
import importlib.util
from pathlib import Path
import sys

from context_t5 import LOCK, PK, ROOT, T4B, read, require, sha, verify_sources


def load_pinned(name, path):
    registered = read(LOCK)["files"][path.relative_to(ROOT).as_posix()]
    require(sha(path) == registered, "frozen analysis module: " + name)
    source = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(source)
    sys.modules[name] = module
    source.loader.exec_module(module)
    return module


def main():
    binding = read(PK/"analysis-entry.json")
    require(sha(Path(__file__)) == binding["entry_sha256"] and sha(LOCK) == binding["source_freeze_sha256"],
            "registered reporting entry")
    if sys.argv[1:] == ["submit"]:
        import schedule_t5

        resources = schedule_t5.resources

        def analysis_resources(name, records):
            cpus, minutes, memory, script, args, positions = resources(name, records)
            require(name == "analyse" and script == "analyse.py" and not args and not positions, "saved-only job")
            return cpus, minutes, memory, Path(__file__).name, args, positions

        schedule_t5.resources = analysis_resources
        sys.argv[:] = [sys.argv[0], "submit", "analyse"]
        schedule_t5.main()
        return

    verify_sources()
    load_pinned("readback", T4B/"readback.py")
    load_pinned("t5_saved_analysis", PK/"analyse.py").main()


if __name__ == "__main__":
    main()
