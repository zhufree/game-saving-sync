"""Configuration tests."""

import json
import tempfile
from pathlib import Path

from src.config import AppConfig, GameEntry, SavePackage, TransferRecord


def test_default_config():
    """Default config uses the new transfer-oriented model."""
    config = AppConfig()
    assert config.steam_root == ""
    assert config.steam_libraries == []
    assert len(config.save_location_templates) > 0
    assert config.snapshot_dir == "./snapshots"
    assert config.first_run is True
    assert config.language == "zh_CN"
    assert len(config.known_games) == 0
    assert len(config.transfer_history) == 0


def test_config_save_and_load():
    """Config can be saved and loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"

        config = AppConfig(
            steam_root="C:\\Program Files (x86)\\Steam",
            steam_libraries=["D:\\SteamLibrary"],
            snapshot_dir="D:\\snapshots",
            first_run=False,
        )

        config.save(str(config_path))
        assert config_path.exists()

        loaded_config = AppConfig.load(str(config_path))
        assert loaded_config.steam_root == "C:\\Program Files (x86)\\Steam"
        assert loaded_config.steam_libraries == ["D:\\SteamLibrary"]
        assert loaded_config.snapshot_dir == "D:\\snapshots"
        assert loaded_config.first_run is False


def test_config_load_nonexistent():
    """Loading a missing config creates a default file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent.json"

        config = AppConfig.load(str(config_path))
        assert config.first_run is True
        assert config_path.exists()


def test_game_entry():
    """Game entries store Steam game and save discovery data."""
    game = GameEntry(
        app_id="322330",
        name="Don't Starve Together",
        install_path="D:\\SteamLibrary\\steamapps\\common\\Don't Starve Together",
        save_paths=["C:\\Users\\Test\\Documents\\Klei\\DoNotStarveTogether"],
        rule_id="dst-default",
    )

    assert game.app_id == "322330"
    assert game.name == "Don't Starve Together"
    assert len(game.save_paths) == 1
    assert game.rule_id == "dst-default"


def test_add_and_get_game():
    """Games can be added and replaced by app id."""
    config = AppConfig()
    game = GameEntry(name="世界1", app_id="100")
    config.add_game(game)

    assert len(config.known_games) == 1
    assert config.get_game("100") is not None
    assert config.get_game("100").name == "世界1"
    assert config.get_game("missing") is None

    replacement = GameEntry(name="世界1 Updated", app_id="100")
    config.add_game(replacement)
    assert len(config.known_games) == 1
    assert config.get_game("100").name == "世界1 Updated"


def test_add_game_preserves_manual_save_paths():
    """Refreshing a game should not remove manually added save paths."""
    config = AppConfig()
    config.add_game(GameEntry(name="Game", app_id="100", save_paths=["C:\\manual"]))

    config.add_game(GameEntry(name="Game", app_id="100", save_paths=["C:\\auto"]))

    assert config.get_game("100").save_paths == ["C:\\manual", "C:\\auto"]


def test_add_game_preserves_manual_save_packages():
    """Refreshing a game should not remove manually added world packages."""
    config = AppConfig()
    manual_package = SavePackage(id="100:manual", label="Manual", path="C:\\manual")
    auto_package = SavePackage(id="100:auto", label="Auto", path="C:\\auto")
    config.add_game(GameEntry(name="Game", app_id="100", save_packages=[manual_package]))

    config.add_game(GameEntry(name="Game", app_id="100", save_packages=[auto_package]))

    assert [package.path for package in config.get_game("100").save_packages] == [
        "C:\\manual",
        "C:\\auto",
    ]


def test_transfer_record():
    """Transfer history stores send/receive attempts."""
    record = TransferRecord(
        transfer_id="transfer-1",
        game_id="322330",
        game_name="Don't Starve Together",
        direction="receive",
        status="completed",
        target_path="C:\\Users\\Test\\Documents\\Klei\\DoNotStarveTogether",
    )

    assert record.transfer_id == "transfer-1"
    assert record.direction == "receive"
    assert record.status == "completed"


def test_add_transfer_record():
    """Transfer records can be appended."""
    config = AppConfig()
    record = TransferRecord(
        transfer_id="transfer-1",
        game_id="322330",
        game_name="Don't Starve Together",
    )

    config.add_transfer_record(record)

    assert len(config.transfer_history) == 1
    assert config.transfer_history[0].transfer_id == "transfer-1"


def test_config_json_format():
    """Saved JSON uses the new field names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        config = AppConfig(steam_root="C:\\Steam")
        game = GameEntry(name="测试游戏", app_id="123")
        config.add_game(game)
        config.save(str(config_path))

        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "steam_root" in data
        assert "snapshot_dir" in data
        assert "known_games" in data
        assert len(data["known_games"]) == 1
        assert data["known_games"][0]["name"] == "测试游戏"
        assert "dst_save_path" not in data
        assert "sync_groups" not in data


def test_legacy_config_migration():
    """Old DST/Syncthing config files are migrated into the new shape."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "legacy_config.json"
        legacy_data = {
            "dst_save_path": "C:\\Users\\Test\\Documents\\Klei\\DoNotStarveTogether",
            "syncthing_path": "C:\\Syncthing\\syncthing.exe",
            "syncthing_api_key": "old-key",
            "backup_dir": "D:\\old-backups",
            "sync_groups": [{"name": "old", "folder_id": "folder"}],
            "first_run": False,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        config = AppConfig.load(str(config_path))

        assert config.snapshot_dir == "D:\\old-backups"
        assert len(config.known_games) == 1
        assert config.known_games[0].app_id == "322330"
        assert config.known_games[0].save_paths == [
            "C:\\Users\\Test\\Documents\\Klei\\DoNotStarveTogether"
        ]
