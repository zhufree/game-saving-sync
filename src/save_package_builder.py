"""Build transferable save archives from SavePackage definitions."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import SavePackage
except ImportError:
    from config import SavePackage


@dataclass(frozen=True)
class BuiltSaveArchive:
    """A zip archive ready to transfer."""

    archive_path: str
    package_id: str
    label: str
    size_bytes: int
    sha256: str
    file_count: int


def build_save_archive(package: SavePackage, output_dir: str) -> BuiltSaveArchive:
    """Create a zip archive for a save package and return transfer metadata."""
    source = Path(package.path)
    if not source.exists():
        raise FileNotFoundError(f"Save package path does not exist: {source}")
    if not source.is_dir():
        raise ValueError(f"Only directory save packages are supported for now: {source}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    archive_path = output / f"{_safe_filename(package.label or source.name)}.zip"
    files = collect_package_files(package)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "package_id": package.id,
            "label": package.label,
            "source_name": source.name,
            "include_patterns": package.include_patterns,
            "exclude_patterns": package.exclude_patterns,
            "metadata": package.metadata,
            "files": [path.as_posix() for path in files],
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        for relative_path in files:
            zf.write(source / relative_path, relative_path.as_posix())

    return BuiltSaveArchive(
        archive_path=str(archive_path),
        package_id=package.id,
        label=package.label,
        size_bytes=archive_path.stat().st_size,
        sha256=sha256_file(archive_path),
        file_count=len(files),
    )


def collect_package_files(package: SavePackage) -> list[Path]:
    """Return relative files included in a save package."""
    source = Path(package.path)
    include_patterns = package.include_patterns or ["**/*"]
    exclude_patterns = package.exclude_patterns or []
    collected: list[Path] = []

    for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = file_path.relative_to(source)
        normalized = relative.as_posix()

        if not _matches_any(normalized, include_patterns):
            continue
        if _matches_any(normalized, exclude_patterns):
            continue

        collected.append(relative)

    return collected


def sha256_file(path: str | Path) -> str:
    """Calculate a file's sha256 digest."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matches_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if normalized_pattern in {"**", "**/*"}:
            return True
        if fnmatch.fnmatch(path, normalized_pattern):
            return True
    return False


def _safe_filename(value: str) -> str:
    value = value.strip() or "save-package"
    for char in '<>:"/\\|?*':
        value = value.replace(char, "_")
    return value[:120]
