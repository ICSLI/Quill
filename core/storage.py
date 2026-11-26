"""Crash-safe JSON persistence shared by configuration and prompts."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def back_up_file(path: Path) -> Path:
    """Preserve the original bytes under a unique name before repairing a file."""
    backup = None
    try:
        with path.open("rb") as source, tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f"{path.name}.", suffix=".bak", delete=False,
        ) as destination:
            backup = Path(destination.name)
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
    except OSError:
        if backup is not None:
            backup.unlink(missing_ok=True)
        raise
    return backup


def atomic_write_json(path: Path, data: Any) -> None:
    """Replace a JSON file only after serialization and flushing succeed."""
    serialized = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
