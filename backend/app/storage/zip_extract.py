from __future__ import annotations

import hashlib
import os
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath

from app.discovery.walker import SKIP

MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB guard against zip bombs


class UnsafeZipError(ValueError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_noise(member_name: str) -> bool:
    """True for archive entries under a directory we never analyze (.git,
    node_modules, dbt_packages, etc -- see discovery/walker.py::SKIP).
    Filtering these out AT EXTRACTION TIME (not just when later walking the
    tree for discovery) matters on Windows: .git in particular contains many
    deeply-nested, long-named object files (`.git/objects/xx/<38 chars>`)
    that, combined with this app's `data/projects/{uuid}/artifacts/{uuid}/
    extracted/...` storage path, can exceed Windows' 260-character MAX_PATH
    and fail with a misleading "No such file or directory" error. Since we
    never read these files anyway, the correct fix is to never extract them.
    """
    return any(part in SKIP for part in PurePosixPath(member_name).parts)


def _long_path_safe(path: Path) -> Path:
    """Prefix with \\\\?\\ on Windows so writes work even if the final path
    exceeds MAX_PATH, regardless of whether the OS's long-path support is
    enabled. Defense in depth on top of `_is_noise` -- a legitimate project
    with deeply nested folders (rare, but possible) should still extract.

    `path` MUST already be absolute (e.g. via `.resolve()`) -- the `\\?\`
    prefix is only valid on a fully-qualified path; applying it to a
    relative path (like the app's default `./data` dir) produces an
    unresolvable UNC-ish path and Windows rejects it outright.
    """
    if os.name == "nt" and path.is_absolute():
        s = str(path)
        if not s.startswith("\\\\?\\"):
            return Path("\\\\?\\" + s)
    return path


def safe_extract(zip_path: Path, dest_dir: Path) -> None:
    """Extract a zip file, rejecting path traversal (zip-slip) and oversized
    archives, and skipping noise directories (.git, node_modules, etc) that
    are never analyzed and are the most likely source of Windows MAX_PATH
    failures.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()

    with zipfile.ZipFile(zip_path) as zf:
        members = [info for info in zf.infolist() if not _is_noise(info.filename)]

        total_uncompressed = sum(info.file_size for info in members)
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise UnsafeZipError(
                f"Archive expands to {total_uncompressed} bytes, exceeding the "
                f"{MAX_UNCOMPRESSED_BYTES} byte limit."
            )

        for info in members:
            target = (dest_dir / info.filename).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise UnsafeZipError(f"Unsafe path in archive: {info.filename}")

        zf.extractall(_long_path_safe(dest_resolved), members=members)


def clear_dir(path: Path, retries: int = 3, delay_seconds: float = 0.5) -> None:
    """Delete a directory tree, retrying on Windows' transient
    "directory not empty" / file-in-use errors -- common right after writing
    many files under a OneDrive-synced or antivirus-scanned path, where an
    external process can briefly hold a handle open on a just-created file.
    """
    if not path.exists():
        return
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error
