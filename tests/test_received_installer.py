"""Received archive installation tests."""

from src.config import AppConfig, GameEntry, SavePackage
from src.received_installer import install_received_archive, read_archive_manifest
from src.save_package_builder import build_save_archive


def test_install_dst_archive_uses_next_cluster_name(tmp_path):
    """DST archives are extracted into the next available Cluster_N folder."""
    source = tmp_path / "source" / "Cluster_1"
    (source / "Master" / "save").mkdir(parents=True)
    (source / "Master" / "save" / "session").write_text("world", encoding="utf-8")
    package = SavePackage(
        id="322330:test",
        label="Cluster_1",
        path=str(source),
        include_patterns=["Master/**"],
        metadata={"app_id": "322330", "cluster": "Cluster_1", "profile": "111"},
    )
    archive = build_save_archive(package, str(tmp_path / "archives"))

    dst_root = tmp_path / "DoNotStarveTogether"
    existing_cluster = dst_root / "222" / "Cluster_1"
    existing_cluster.mkdir(parents=True)
    config = AppConfig(
        known_games=[
            GameEntry(
                app_id="322330",
                name="Don't Starve Together",
                save_paths=[str(dst_root)],
            )
        ]
    )

    installed = install_received_archive(archive.archive_path, config)

    target = dst_root / "222" / "Cluster_2"
    assert installed.target_path == str(target)
    assert (target / "Master" / "save" / "session").read_text(encoding="utf-8") == "world"


def test_install_dst_archive_keeps_original_cluster_name_if_available(tmp_path):
    """The original cluster name is reused when it is not already present locally."""
    source = tmp_path / "source" / "Cluster_3"
    (source / "cluster.ini").parent.mkdir(parents=True, exist_ok=True)
    (source / "cluster.ini").write_text("[GAMEPLAY]", encoding="utf-8")
    package = SavePackage(
        id="322330:test",
        label="Cluster_3",
        path=str(source),
        include_patterns=["cluster.ini"],
        metadata={"app_id": "322330", "cluster": "Cluster_3"},
    )
    archive = build_save_archive(package, str(tmp_path / "archives"))
    dst_root = tmp_path / "DoNotStarveTogether"
    (dst_root / "222").mkdir(parents=True)
    config = AppConfig(
        known_games=[
            GameEntry(
                app_id="322330",
                name="Don't Starve Together",
                save_paths=[str(dst_root)],
            )
        ]
    )

    installed = install_received_archive(archive.archive_path, config)

    assert installed.target_path == str(dst_root / "222" / "Cluster_3")
    assert (dst_root / "222" / "Cluster_3" / "cluster.ini").exists()


def test_read_archive_manifest(tmp_path):
    """Received archive manifests can be inspected before install."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_text("x", encoding="utf-8")
    archive = build_save_archive(
        SavePackage(
            id="322330:test",
            label="World",
            path=str(source),
            metadata={"app_id": "322330"},
        ),
        str(tmp_path / "archives"),
    )

    manifest = read_archive_manifest(archive.archive_path)

    assert manifest["package_id"] == "322330:test"
    assert manifest["metadata"]["app_id"] == "322330"
