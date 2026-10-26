"""Atomic, flushed diagnostic output; an existing guard survives write failure."""
import json
import os
from pathlib import Path
import tempfile


def persist_result(path, report):
    path = Path(path)
    scratch = None
    try:
        # Same-directory replacement is atomic on the local filesystem. Never
        # truncate the consumed guard while serializing a diagnostic report.
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",delete=False,
                prefix=f".{path.name}.",suffix=".tmp",dir=path.parent) as stream:
            scratch = Path(stream.name)
            json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(scratch,path)
    finally:
        if scratch is not None and scratch.exists():
            scratch.unlink()
