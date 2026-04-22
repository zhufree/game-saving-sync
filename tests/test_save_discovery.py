"""Save discovery tests."""


from src.config import SaveLocationTemplate
from src.save_discovery import (
    discover_dst_world_packages,
    discover_project_zomboid_save_packages,
    discover_save_paths_for_game,
    discover_stardew_save_packages,
    discover_supported_games,
    expand_save_template,
    is_supported_game,
)
from src.steam_library import SteamGame


def test_expand_save_template_uses_user_folders(monkeypatch):
    """Templates can use user-folder and game placeholders."""
    monkeypatch.setenv("USERPROFILE", "C:\\Users\\Tester")
    monkeypatch.setenv("APPDATA", "C:\\Users\\Tester\\AppData\\Roaming")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\Tester\\AppData\\Local")

    path = expand_save_template(
        "{APPDATA}\\{game_name}\\{app_id}",
        app_id="413150",
        game_name="Stardew Valley",
    )

    assert path == "C:\\Users\\Tester\\AppData\\Roaming\\Stardew Valley\\413150"


def test_discover_save_paths_for_supported_game(monkeypatch, tmp_path):
    """Built-in rules discover existing save directories."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    save_dir = tmp_path / "Roaming" / "StardewValley" / "Saves"
    farm = save_dir / "RiverFarm_123456789"
    farm.mkdir(parents=True)
    (farm / "SaveGameInfo").write_text("info", encoding="utf-8")
    game = SteamGame(
        app_id="413150",
        name="Stardew Valley",
        install_dir="Stardew Valley",
        install_path=str(tmp_path / "Steam" / "steamapps" / "common" / "Stardew Valley"),
        library_path=str(tmp_path / "Steam"),
    )

    entry = discover_save_paths_for_game(game)

    assert entry.rule_id == "stardew-valley-default"
    assert entry.save_paths == [str(save_dir)]
    assert entry.save_packages[0].path == str(farm)
    assert entry.save_packages[0].label == "RiverFarm_123456789"


def test_discover_supported_games_filters_unsupported(tmp_path):
    """Only games with built-in rules are returned for the simple MVP."""
    games = [
        SteamGame("413150", "Stardew Valley", "Stardew Valley", "", ""),
        SteamGame("108600", "Project Zomboid", "ProjectZomboid", "", ""),
        SteamGame("999", "Unsupported", "Unsupported", "", ""),
    ]

    entries = discover_supported_games(
        games,
        steam_root=str(tmp_path / "Steam"),
        common_templates=[],
    )

    assert [entry.app_id for entry in entries] == ["413150", "108600"]


def test_common_templates_are_used_for_existing_paths(tmp_path):
    """Configured common templates participate in save discovery."""
    save_dir = tmp_path / "CustomSaves"
    save_dir.mkdir()
    template = SaveLocationTemplate(
        id="custom",
        label="Custom",
        path_template=str(save_dir),
    )
    game = SteamGame("999", "Unsupported", "Unsupported", "", "")

    entry = discover_save_paths_for_game(game, common_templates=[template])

    assert entry.save_paths == [str(save_dir)]
    assert is_supported_game("413150") is True
    assert is_supported_game("999") is False


def test_discover_dst_world_packages_finds_clusters(tmp_path):
    """DST root is refined into Cluster_* world packages."""
    dst_root = tmp_path / "DoNotStarveTogether"
    cluster = dst_root / "123456789" / "Cluster_1"
    (cluster / "Master" / "save").mkdir(parents=True)
    (cluster / "Caves" / "save").mkdir(parents=True)
    (cluster / "cluster.ini").write_text("[GAMEPLAY]\n", encoding="utf-8")

    packages = discover_dst_world_packages([str(dst_root)])

    assert len(packages) == 1
    assert packages[0].path == str(cluster)
    assert packages[0].metadata["profile"] == "123456789"
    assert packages[0].metadata["cluster"] == "Cluster_1"
    assert packages[0].metadata["has_caves"] == "true"
    assert "Master/**" in packages[0].include_patterns
    assert "**/*.log" in packages[0].exclude_patterns


def test_discover_dst_world_packages_ignores_non_cluster_dirs(tmp_path):
    """DST scanner skips folders that are not actual worlds."""
    dst_root = tmp_path / "DoNotStarveTogether"
    (dst_root / "client_save").mkdir(parents=True)
    (dst_root / "123" / "NotACluster").mkdir(parents=True)

    assert discover_dst_world_packages([str(dst_root)]) == []


def test_discover_dst_world_packages_accepts_account_dir_as_world(tmp_path):
    """Some manually selected folders may already be the world directory."""
    world_dir = tmp_path / "123456789"
    (world_dir / "Master" / "save").mkdir(parents=True)

    packages = discover_dst_world_packages([str(world_dir)])

    assert len(packages) == 1
    assert packages[0].path == str(world_dir)


def test_discover_dst_world_packages_searches_one_extra_level(tmp_path):
    """DST scanner tolerates one extra nesting level below the account folder."""
    dst_root = tmp_path / "DoNotStarveTogether"
    cluster = dst_root / "123456789" / "LocalSaves" / "Cluster_2"
    (cluster / "Master").mkdir(parents=True)

    packages = discover_dst_world_packages([str(dst_root)])

    assert len(packages) == 1
    assert packages[0].path == str(cluster)


def test_discover_stardew_save_packages_finds_each_save_folder(tmp_path):
    """Stardew scanner refines the Saves root into individual save folders."""
    saves_root = tmp_path / "StardewValley" / "Saves"
    farm = saves_root / "Meadow_987654321"
    farm.mkdir(parents=True)
    (farm / "SaveGameInfo").write_text("info", encoding="utf-8")
    (farm / "Meadow_987654321").write_text("save", encoding="utf-8")

    packages = discover_stardew_save_packages([str(saves_root)])

    assert len(packages) == 1
    assert packages[0].path == str(farm)
    assert packages[0].include_patterns == ["*", "**/*"]


def test_discover_project_zomboid_save_packages_finds_mode_saves(tmp_path):
    """Project Zomboid scanner sends each Saves/<mode>/<save> folder separately."""
    saves_root = tmp_path / "Zomboid" / "Saves"
    save = saves_root / "Sandbox" / "Muldraugh"
    save.mkdir(parents=True)
    (save / "map_ver.bin").write_bytes(b"zomboid")

    packages = discover_project_zomboid_save_packages([str(saves_root)])

    assert len(packages) == 1
    assert packages[0].label == "Sandbox / Muldraugh"
    assert packages[0].path == str(save)
    assert packages[0].metadata["mode"] == "Sandbox"
    assert packages[0].include_patterns == ["*", "**/*"]
