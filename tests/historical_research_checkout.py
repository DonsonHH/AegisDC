"""Evaluate immutable registration CLI contracts at their actual old source."""
from contextlib import contextmanager
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
HISTORICAL_SOURCE='2dfe5537e4f95fa605f325b060ef32223dafb4f6'

@contextmanager
def historical_checkout(source=HISTORICAL_SOURCE):
    if type(source) is not str or len(source)!=40 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('Declare a full immutable historical source commit')
    with TemporaryDirectory(prefix='aegisdc-historical-ci-') as tmp:
        checkout=Path(tmp)/'source'
        subprocess.run(['git','-c','core.autocrlf=false','worktree','add','--detach','--quiet',
                        str(checkout),source],cwd=ROOT,check=True,capture_output=True)
        try:
            actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout).decode().strip()
            if actual!=source:raise AssertionError('Wrong immutable historical checkout')
            yield checkout
        finally:
            subprocess.run(['git','worktree','remove',str(checkout)],cwd=ROOT,check=True,capture_output=True)
