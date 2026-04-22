"""Save archive builder tests."""

import zipfile

from src.config import SavePackage
from src.save_package_builder import build_save_archive, collect_package_files


def test_collect_package_files_respects_include_and_exclude(tmp_path):
    """Package file collection follows include/exclude patterns."""
    world = tmp_path / "Cluster_1"
    (world / "Master" / "save").mkdir(parents=True)
    (world / "Master" / "save" / "session").write_text("world", encoding="utf-8")
    (world / "Master" / "server_log.txt").write_text("log", encoding="utf-8")
    (world / "cluster.ini").write_text("[GAMEPLAY]", encoding="utf-8")
    package = SavePackage(
        id="dst:cluster",
        label="Cluster_1",
        path=str(world),
        include_patterns=["cluster.ini", "Master/**"],
        exclude_patterns=["**/*.txt"],
    )

    files = collect_package_files(package)

    assert [path.as_posix() for path in files] == ["cluster.ini", "Master/save/session"]


def test_build_save_archive_writes_manifest_and_files(tmp_path):
    """Archives include a manifest and selected save files."""
    world = tmp_path / "Cluster_1"
    (world / "Master" / "save").mkdir(parents=True)
    (world / "Master" / "save" / "session").write_text("world", encoding="utf-8")
    package = SavePackage(
        id="dst:cluster",
        label="Cluster_1",
        path=str(world),
        include_patterns=["Master/**"],
    )

    archive = build_save_archive(package, str(tmp_path / "out"))

    assert archive.file_count == 1
    assert archive.size_bytes > 0
    assert len(archive.sha256) == 64
    with zipfile.ZipFile(archive.archive_path) as zf:
        assert sorted(zf.namelist()) == ["Master/save/session", "manifest.json"]


def test_double_star_include_matches_root_files(tmp_path):
    """Generic directory packages include files directly inside the selected folder."""
    save = tmp_path / "Meadow_123"
    save.mkdir()
    (save / "SaveGameInfo").write_text("info", encoding="utf-8")
    (save / "Meadow_123").write_text("save", encoding="utf-8")
    package = SavePackage(
        id="stardew:test",
        label="Meadow_123",
        path=str(save),
        include_patterns=["**/*"],
    )

    files = collect_package_files(package)

    assert [path.as_posix() for path in files] == ["Meadow_123", "SaveGameInfo"]
