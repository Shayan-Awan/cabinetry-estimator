"""Local file storage helpers.

Phase 1 only needs directory creation and the path-safety primitives. The
upload, checksum and rendering logic that uses them arrives in Phase 2.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src import config
from src.database import create_data_directories

__all__ = ["create_data_directories", "safe_filename", "resolve_within"]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, fallback: str = "document") -> str:
    """Reduce an arbitrary filename to a safe basename.

    Strips directory components, normalises unicode, and keeps only characters
    that cannot be interpreted by a shell or a path parser. A name that reduces
    to nothing (or to a dot-file) falls back to ``fallback``.
    """
    # Take the basename under both POSIX and Windows separators, so a name like
    # "..\\..\\evil.pdf" arriving from a Windows client cannot escape.
    base = re.split(r"[\\/]", name)[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    cleaned = _UNSAFE.sub("_", base).strip("._")
    if not cleaned:
        return fallback
    return cleaned[:120]


def resolve_within(root: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``root`` and refuse anything that escapes ``root``.

    This is the guard against ``../`` traversal: the joined path is fully
    resolved and then checked to be inside the root.
    """
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Path {candidate} escapes {root}")
    return candidate


def originals_path(stored_filename: str) -> Path:
    return resolve_within(config.originals_dir(), stored_filename)


def generated_path(filename: str) -> Path:
    return resolve_within(config.generated_dir(), filename)
