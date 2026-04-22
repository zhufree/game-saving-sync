"""Steam library discovery helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass(frozen=True)
class SteamGame:
    """A game installed in a Steam library."""

    app_id: str
    name: str
    install_dir: str
    install_path: str
    library_path: str


TOKEN_RE = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')


def parse_vdf(text: str) -> dict[str, object]:
    """Parse the subset of Valve VDF used by Steam library and app manifests."""
    tokens = _tokenize_vdf(text)
    index = 0

    def parse_object() -> dict[str, object]:
        nonlocal index
        result: dict[str, object] = {}

        while index < len(tokens):
            token = tokens[index]
            index += 1

            if token == "}":
                break
            if token == "{":
                raise ValueError("Unexpected opening brace in VDF")

            if index >= len(tokens):
                raise ValueError(f"Missing value for VDF key: {token}")

            value = tokens[index]
            index += 1

            if value == "{":
                result[token] = parse_object()
            elif value == "}":
                raise ValueError(f"Unexpected closing brace after VDF key: {token}")
            else:
                result[token] = value

        return result

    parsed = parse_object()
    if index != len(tokens):
        raise ValueError("Unexpected trailing VDF tokens")
    return parsed


def discover_steam_libraries(steam_root: str) -> list[str]:
    """Return Steam library directories, including the root library."""
    root = Path(steam_root).expanduser()
    libraries: list[Path] = []

    if root.exists():
        libraries.append(root)

    library_file = root / "steamapps" / "libraryfolders.vdf"
    if not library_file.exists():
        logger.info(f"Steam libraryfolders.vdf not found: {library_file}")
        return _unique_paths(libraries)

    try:
        data = parse_vdf(library_file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        data = parse_vdf(library_file.read_text(encoding="utf-8-sig"))
    except Exception as e:
        logger.warning(f"Failed to parse Steam library file {library_file}: {e}")
        return _unique_paths(libraries)

    libraryfolders = data.get("libraryfolders", {})
    if not isinstance(libraryfolders, dict):
        return _unique_paths(libraries)

    for entry in libraryfolders.values():
        if not isinstance(entry, dict):
            continue

        path_value = entry.get("path")
        if isinstance(path_value, str) and path_value.strip():
            libraries.append(Path(path_value.replace("\\\\", "\\")))

    return _unique_paths(libraries)


def discover_installed_games(steam_root: str) -> list[SteamGame]:
    """Scan Steam app manifests and return installed games."""
    games: list[SteamGame] = []

    for library in discover_steam_libraries(steam_root):
        library_path = Path(library)
        steamapps = library_path / "steamapps"
        if not steamapps.exists():
            continue

        for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
            game = parse_app_manifest(manifest, library_path)
            if game:
                games.append(game)

    return games


def parse_app_manifest(manifest_path: str | Path, library_path: str | Path) -> SteamGame | None:
    """Parse a Steam app manifest into a SteamGame."""
    manifest = Path(manifest_path)
    library = Path(library_path)

    try:
        data = parse_vdf(manifest.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        data = parse_vdf(manifest.read_text(encoding="utf-8-sig"))
    except Exception as e:
        logger.warning(f"Failed to parse Steam app manifest {manifest}: {e}")
        return None

    app_state = data.get("AppState")
    if not isinstance(app_state, dict):
        return None

    app_id = app_state.get("appid")
    name = app_state.get("name")
    install_dir = app_state.get("installdir")

    if not all(isinstance(value, str) and value for value in [app_id, name, install_dir]):
        logger.warning(f"Steam app manifest is missing required fields: {manifest}")
        return None

    install_path = library / "steamapps" / "common" / install_dir

    return SteamGame(
        app_id=app_id,
        name=name,
        install_dir=install_dir,
        install_path=str(install_path),
        library_path=str(library),
    )


def _tokenize_vdf(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text):
        quoted, brace = match.groups()
        if quoted is not None:
            tokens.append(quoted.replace(r"\\", "\\").replace(r"\"", '"'))
        elif brace is not None:
            tokens.append(brace)
    return tokens


def _unique_paths(paths: list[Path]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []

    for path in paths:
        normalized = str(path)
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)

    return unique
