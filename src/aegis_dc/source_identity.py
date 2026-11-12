"""Runtime byte and Git identity shared by the plant and recorded attempts."""
from hashlib import sha256
from pathlib import Path
import subprocess

from patrol_rsi.contracts import digest


def runtime_source_identity(root):
    """Read the current runtime, including its shared legacy JSON contract.

    Do not cache: record/replay checks must detect changes during execution.
    Git metadata can be unavailable for an exported source tree; file identity
    is still required. Runtime caches are excluded by the explicit file set.
    """
    root = Path(root)
    paths = sorted((root / 'src/aegis_dc').glob('*.py')) + [root / 'src/patrol_rsi/contracts.py']
    files = {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
             for path in paths}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(
            ['git', 'status', '--porcelain', '--', 'src/aegis_dc', 'src/patrol_rsi/contracts.py'],
            cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return dict(git_commit=commit, implementation_has_changes=dirty,
                source_tree_sha256=digest(files), files=files)
