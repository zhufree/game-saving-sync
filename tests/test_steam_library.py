"""Steam library discovery tests."""

from pathlib import Path

from src.steam_library import (
    discover_installed_games,
    discover_steam_libraries,
    parse_app_manifest,
    parse_vdf,
)


def test_parse_vdf_nested_object():
    """VDF parser handles quoted keys, values, and nested sections."""
    data = parse_vdf(
        """
        "libraryfolders"
        {
            "0"
            {
                "path" "C:\\\\Program Files (x86)\\\\Steam"
                "apps"
                {
                    "322330" "123456"
                }
            }
        }
        """
    )

    libraryfolders = data["libraryfolders"]
    assert isinstance(libraryfolders, dict)
    first_library = libraryfolders["0"]
    assert isinstance(first_library, dict)
    assert first_library["path"] == "C:\\Program Files (x86)\\Steam"
    assert first_library["apps"] == {"322330": "123456"}


def test_discover_steam_libraries_includes_extra_libraries(tmp_path):
    """Steam libraries are read from libraryfolders.vdf."""
    steam_root = tmp_path / "Steam"
    extra_library = tmp_path / "SteamLibrary"
    (steam_root / "steamapps").mkdir(parents=True)
    extra_library.mkdir()
    (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
        f'''
        "libraryfolders"
        {{
            "0"
            {{
                "path" "{steam_root}"
            }}
            "1"
            {{
                "path" "{extra_library}"
            }}
        }}
        ''',
        encoding="utf-8",
    )

    libraries = discover_steam_libraries(str(steam_root))

    assert libraries == [str(steam_root), str(extra_library)]


def test_parse_app_manifest(tmp_path):
    """App manifests are converted into SteamGame objects."""
    library = tmp_path / "Steam"
    manifest = library / "steamapps" / "appmanifest_322330.acf"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '''
        "AppState"
        {
            "appid" "322330"
            "name" "Don't Starve Together"
            "installdir" "Don't Starve Together"
        }
        ''',
        encoding="utf-8",
    )

    game = parse_app_manifest(manifest, library)

    assert game is not None
    assert game.app_id == "322330"
    assert game.name == "Don't Starve Together"
    assert game.install_dir == "Don't Starve Together"
    assert game.install_path == str(
        library / "steamapps" / "common" / "Don't Starve Together"
    )


def test_discover_installed_games_across_libraries(tmp_path):
    """Installed games are discovered from every Steam library manifest."""
    steam_root = tmp_path / "Steam"
    extra_library = tmp_path / "SteamLibrary"
    (steam_root / "steamapps").mkdir(parents=True)
    (extra_library / "steamapps").mkdir(parents=True)

    (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
        f'''
        "libraryfolders"
        {{
            "0" {{ "path" "{steam_root}" }}
            "1" {{ "path" "{extra_library}" }}
        }}
        ''',
        encoding="utf-8",
    )
    _write_manifest(
        steam_root / "steamapps" / "appmanifest_100.acf",
        "100",
        "Root Game",
        "RootGame",
    )
    _write_manifest(
        extra_library / "steamapps" / "appmanifest_200.acf",
        "200",
        "Extra Game",
        "ExtraGame",
    )

    games = discover_installed_games(str(steam_root))

    assert [game.app_id for game in games] == ["100", "200"]
    assert [Path(game.library_path).name for game in games] == ["Steam", "SteamLibrary"]


def _write_manifest(path: Path, app_id: str, name: str, install_dir: str) -> None:
    path.write_text(
        f'''
        "AppState"
        {{
            "appid" "{app_id}"
            "name" "{name}"
            "installdir" "{install_dir}"
        }}
        ''',
        encoding="utf-8",
    )
