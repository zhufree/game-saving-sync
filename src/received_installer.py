"""Install received save archives into the local user's save folder."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import AppConfig
except ImportError:
    from config import AppConfig


@dataclass(frozen=True)
class InstalledSavePackage:
    """A received archive installed into a game save folder."""

    target_path: str
    app_id: str
    label: str
    file_count: int


def install_received_archive(archive_path: str, config: AppConfig) -> InstalledSavePackage:
    """Install a received archive into the matching local game save folder."""
    archive = Path(archive_path)
    manifest = read_archive_manifest(archive)
    app_id = _manifest_app_id(manifest)

    if app_id == "322330":
        return install_dst_archive(archive, manifest, config)
    if app_id in {"413150", "108600"}:
        return install_directory_archive(archive, manifest, config, app_id)

    raise ValueError(f"暂不支持自动安装该游戏的存档包: {app_id}")


def install_dst_archive(
    archive_path: Path,
    manifest: dict[str, object],
    config: AppConfig,
) -> InstalledSavePackage:
    """Install a DST Cluster archive as the next available Cluster_N folder."""
    game = config.get_game("322330")
    if not game or not game.save_paths:
        raise ValueError("没有找到 DST 本地存档根目录，请先扫描或手动添加存档目录。")

    save_root = Path(game.save_paths[0])
    if not save_root.exists():
        raise FileNotFoundError(f"DST 存档根目录不存在: {save_root}")

    profile_dir = _choose_dst_profile_dir(save_root, manifest)
    target_dir = _next_dst_cluster_dir(profile_dir, _manifest_cluster_name(manifest))
    target_dir.mkdir(parents=True, exist_ok=False)

    file_count = _extract_archive_files(archive_path, target_dir)

    return InstalledSavePackage(
        target_path=str(target_dir),
        app_id="322330",
        label=str(manifest.get("label", target_dir.name)),
        file_count=file_count,
    )


def install_directory_archive(
    archive_path: Path,
    manifest: dict[str, object],
    config: AppConfig,
    app_id: str,
) -> InstalledSavePackage:
    """Install a folder-style save archive below the local game's save root."""
    game = config.get_game(app_id)
    if not game or not game.save_paths:
        raise ValueError(f"没有找到该游戏的本地存档根目录，请先扫描或手动添加存档目录: {app_id}")

    save_root = Path(game.save_paths[0])
    if not save_root.exists():
        raise FileNotFoundError(f"本地存档根目录不存在: {save_root}")

    target_dir = _generic_target_dir(save_root, manifest, app_id)
    target_dir.mkdir(parents=True, exist_ok=False)

    file_count = _extract_archive_files(archive_path, target_dir)
    return InstalledSavePackage(
        target_path=str(target_dir),
        app_id=app_id,
        label=str(manifest.get("label", target_dir.name)),
        file_count=file_count,
    )


def read_archive_manifest(archive_path: str | Path) -> dict[str, object]:
    """Read manifest.json from a received archive."""
    with zipfile.ZipFile(archive_path) as zf:
        try:
            data = zf.read("manifest.json")
        except KeyError as e:
            raise ValueError("接收到的存档包缺少 manifest.json") from e
    return json.loads(data.decode("utf-8"))


def _manifest_app_id(manifest: dict[str, object]) -> str:
    metadata = manifest.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("app_id"):
        return str(metadata["app_id"])

    package_id = str(manifest.get("package_id", ""))
    if ":" in package_id:
        return package_id.split(":", 1)[0]
    raise ValueError("无法从存档包识别游戏 app_id")


def _manifest_cluster_name(manifest: dict[str, object]) -> str:
    metadata = manifest.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("cluster"):
        return str(metadata["cluster"])
    source_name = str(manifest.get("source_name", "Cluster_1"))
    return source_name if source_name.lower().startswith("cluster_") else "Cluster_1"


def _choose_dst_profile_dir(save_root: Path, manifest: dict[str, object]) -> Path:
    metadata = manifest.get("metadata", {})
    profile = str(metadata.get("profile", "")) if isinstance(metadata, dict) else ""
    if profile and profile.isdigit() and (save_root / profile).is_dir():
        return save_root / profile

    numeric_profiles = sorted(
        path for path in save_root.iterdir() if path.is_dir() and path.name.isdigit()
    )
    if numeric_profiles:
        return numeric_profiles[0]

    raise ValueError(
        "没有找到 DST 用户 ID 目录。请先启动一次游戏创建存档，"
        "或手动在存档根目录下选择正确的数字用户文件夹。"
    )


def _next_dst_cluster_dir(profile_dir: Path, preferred_name: str) -> Path:
    if not (profile_dir / preferred_name).exists():
        return profile_dir / preferred_name

    used_numbers = set()
    for path in profile_dir.glob("Cluster_*"):
        suffix = path.name.removeprefix("Cluster_")
        if suffix.isdigit():
            used_numbers.add(int(suffix))

    next_number = 1
    while next_number in used_numbers:
        next_number += 1
    return profile_dir / f"Cluster_{next_number}"


def _extract_archive_files(archive_path: Path, target_dir: Path) -> int:
    file_count = 0
    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename == "manifest.json":
                continue
            destination = _safe_extract_path(target_dir, info.filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(destination, "wb") as dst:
                dst.write(src.read())
            file_count += 1
    return file_count


def _generic_target_dir(save_root: Path, manifest: dict[str, object], app_id: str) -> Path:
    metadata = manifest.get("metadata", {})
    source_name = _safe_dir_name(str(manifest.get("source_name", "Received Save")))

    if app_id == "108600" and isinstance(metadata, dict):
        mode = _safe_dir_name(str(metadata.get("mode", "")))
        if mode:
            return _next_available_dir(save_root / mode / source_name)

    return _next_available_dir(save_root / source_name)


def _next_available_dir(preferred_dir: Path) -> Path:
    if not preferred_dir.exists():
        return preferred_dir

    index = 2
    while True:
        candidate = preferred_dir.with_name(f"{preferred_dir.name}_{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _safe_dir_name(value: str) -> str:
    value = value.strip() or "Received Save"
    for char in '<>:"/\\|?*':
        value = value.replace(char, "_")
    return value.rstrip(". ")


def _safe_extract_path(root: Path, member_name: str) -> Path:
    destination = (root / member_name).resolve()
    root_resolved = root.resolve()
    if root_resolved not in destination.parents and destination != root_resolved:
        raise ValueError(f"存档包包含不安全路径: {member_name}")
    return destination
