"""Game save discovery based on supported Steam games and user-folder rules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import GameEntry, SaveLocationTemplate, SavePackage
    from .steam_library import SteamGame
except ImportError:
    from config import GameEntry, SaveLocationTemplate, SavePackage
    from steam_library import SteamGame


@dataclass(frozen=True)
class GameSaveRule:
    """Known save-location rules for a supported game."""

    app_id: str
    rule_id: str
    aliases: tuple[str, ...]
    templates: tuple[str, ...]


SUPPORTED_GAME_RULES: dict[str, GameSaveRule] = {
    "322330": GameSaveRule(
        app_id="322330",
        rule_id="dst-default",
        aliases=("Don't Starve Together", "Klei\\DoNotStarveTogether"),
        templates=(
            "{DOCUMENTS}\\Klei\\DoNotStarveTogether",
            "{USERPROFILE}\\Documents\\Klei\\DoNotStarveTogether",
        ),
    ),
    "413150": GameSaveRule(
        app_id="413150",
        rule_id="stardew-valley-default",
        aliases=("Stardew Valley",),
        templates=("{APPDATA}\\StardewValley\\Saves",),
    ),
    "105600": GameSaveRule(
        app_id="105600",
        rule_id="terraria-default",
        aliases=("Terraria",),
        templates=("{DOCUMENTS}\\My Games\\Terraria",),
    ),
    "1145360": GameSaveRule(
        app_id="1145360",
        rule_id="hades-default",
        aliases=("Hades",),
        templates=("{USERPROFILE}\\Saved Games\\Hades",),
    ),
    "108600": GameSaveRule(
        app_id="108600",
        rule_id="project-zomboid-default",
        aliases=("Project Zomboid",),
        templates=("{USERPROFILE}\\Zomboid\\Saves",),
    ),
}


def discover_save_paths_for_game(
    game: SteamGame | GameEntry,
    steam_root: str = "",
    common_templates: list[SaveLocationTemplate] | None = None,
) -> GameEntry:
    """Return a GameEntry with discovered save paths for a supported Steam game."""
    app_id = game.app_id
    name = game.name
    install_path = game.install_path
    existing_paths = list(getattr(game, "save_paths", []))

    rule = SUPPORTED_GAME_RULES.get(app_id)
    rule_templates = list(rule.templates if rule else [])

    for template in common_templates or []:
        rule_templates.append(template.path_template)

    discovered = []
    for template in rule_templates:
        candidate = expand_save_template(
            template=template,
            app_id=app_id,
            game_name=name,
            install_path=install_path,
            steam_root=steam_root,
        )
        if candidate and Path(candidate).exists():
            discovered.append(str(Path(candidate)))

    save_paths = _dedupe_paths([*existing_paths, *discovered])
    save_packages = discover_save_packages_for_game(
        app_id=app_id,
        game_name=name,
        save_roots=save_paths,
    )
    return GameEntry(
        app_id=app_id,
        name=name,
        install_path=install_path,
        save_paths=save_paths,
        save_packages=save_packages,
        rule_id=rule.rule_id if rule else getattr(game, "rule_id", ""),
    )


def discover_supported_games(
    games: list[SteamGame],
    steam_root: str,
    common_templates: list[SaveLocationTemplate],
) -> list[GameEntry]:
    """Convert installed Steam games into supported GameEntry values with save paths."""
    entries: list[GameEntry] = []

    for game in games:
        if game.app_id not in SUPPORTED_GAME_RULES:
            continue
        entries.append(discover_save_paths_for_game(game, steam_root, common_templates))

    return entries


def expand_save_template(
    template: str,
    app_id: str,
    game_name: str,
    install_path: str = "",
    steam_root: str = "",
) -> str:
    """Expand a save-location template using common Windows user-folder variables."""
    userprofile = os.environ.get("USERPROFILE", str(Path.home()))
    documents = str(Path(userprofile) / "Documents")
    appdata = os.environ.get("APPDATA", str(Path(userprofile) / "AppData" / "Roaming"))
    localappdata = os.environ.get(
        "LOCALAPPDATA",
        str(Path(userprofile) / "AppData" / "Local"),
    )
    steam_userdata = str(Path(steam_root) / "userdata") if steam_root else ""

    return os.path.expandvars(
        template.format(
            APPDATA=appdata,
            APP_ID=app_id,
            DOCUMENTS=documents,
            GAME_NAME=game_name,
            INSTALL_PATH=install_path,
            LOCALAPPDATA=localappdata,
            STEAM_USERDATA=steam_userdata,
            USERPROFILE=userprofile,
            app_id=app_id,
            game_name=_safe_path_segment(game_name),
            install_path=install_path,
            steam_userdata=steam_userdata,
        )
    )


def discover_save_packages_for_game(
    app_id: str,
    game_name: str,
    save_roots: list[str],
) -> list[SavePackage]:
    """Discover concrete transferable save packages below discovered save roots."""
    if app_id == "322330":
        return discover_dst_world_packages(save_roots)
    if app_id == "413150":
        return discover_stardew_save_packages(save_roots)
    if app_id == "108600":
        return discover_project_zomboid_save_packages(save_roots)

    packages: list[SavePackage] = []
    for root in save_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        packages.append(
            SavePackage(
                id=f"{app_id}:{root_path}",
                label=game_name,
                path=str(root_path),
                root_path=str(root_path),
                include_patterns=["**/*"],
                exclude_patterns=["**/*.log"],
                metadata={"app_id": app_id},
            )
        )
    return packages


def discover_stardew_save_packages(save_roots: list[str]) -> list[SavePackage]:
    """Discover Stardew Valley save folders, one package per farm/character save."""
    packages: list[SavePackage] = []

    for root in save_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue

        save_dirs = [root_path] if _looks_like_stardew_save_dir(root_path) else []
        save_dirs.extend(
            child
            for child in root_path.iterdir()
            if child.is_dir() and _looks_like_stardew_save_dir(child)
        )

        for save_dir in save_dirs:
            packages.append(
                SavePackage(
                    id=f"413150:{save_dir}",
                    label=save_dir.name,
                    path=str(save_dir),
                    root_path=str(root_path),
                    include_patterns=["*", "**/*"],
                    exclude_patterns=["**/*.log"],
                    metadata={
                        "app_id": "413150",
                        "save_name": save_dir.name,
                    },
                )
            )

    return _dedupe_packages(packages)


def discover_project_zomboid_save_packages(save_roots: list[str]) -> list[SavePackage]:
    """Discover Project Zomboid saves below Saves/<mode>/<save name>."""
    packages: list[SavePackage] = []

    for root in save_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue

        for mode_dir in sorted(path for path in root_path.iterdir() if path.is_dir()):
            for save_dir in sorted(path for path in mode_dir.iterdir() if path.is_dir()):
                if not _looks_like_project_zomboid_save_dir(save_dir):
                    continue
                packages.append(
                    SavePackage(
                        id=f"108600:{save_dir}",
                        label=f"{mode_dir.name} / {save_dir.name}",
                        path=str(save_dir),
                        root_path=str(root_path),
                        include_patterns=["*", "**/*"],
                        exclude_patterns=["**/*.log", "**/console.txt"],
                        metadata={
                            "app_id": "108600",
                            "mode": mode_dir.name,
                            "save_name": save_dir.name,
                        },
                    )
                )

    return _dedupe_packages(packages)


def discover_dst_world_packages(save_roots: list[str]) -> list[SavePackage]:
    """Discover DST Cluster_* folders that represent individual transferable worlds."""
    packages: list[SavePackage] = []

    for root in save_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue

        for cluster_dir in _iter_dst_cluster_dirs(root_path):
            relative = cluster_dir.relative_to(root_path)
            has_caves = (cluster_dir / "Caves").exists()
            display_path = cluster_dir.name if str(relative) == "." else str(relative)
            label = f"{display_path} ({'地上 + 洞穴' if has_caves else '地上'})"
            packages.append(
                SavePackage(
                    id=f"322330:{cluster_dir}",
                    label=label,
                    path=str(cluster_dir),
                    root_path=str(root_path),
                    include_patterns=["cluster.ini", "Master/**", "Caves/**"],
                    exclude_patterns=[
                        "cluster_token.txt",
                        "**/server_log.txt",
                        "**/client_log.txt",
                        "**/*.log",
                    ],
                    metadata={
                        "app_id": "322330",
                        "cluster": cluster_dir.name,
                        "profile": cluster_dir.parent.name,
                        "has_caves": str(has_caves).lower(),
                    },
                )
            )

    return _dedupe_packages(packages)


def is_supported_game(app_id: str) -> bool:
    """Return whether the app id has a built-in save discovery rule."""
    return app_id in SUPPORTED_GAME_RULES


def supported_game_names() -> list[str]:
    """Return display names for games with built-in rules."""
    return [rule.aliases[0] for rule in SUPPORTED_GAME_RULES.values()]


def _safe_path_segment(value: str) -> str:
    for char in '<>:"/\\|?*':
        value = value.replace(char, "")
    return value.strip()


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        key = str(Path(path)).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _iter_dst_cluster_dirs(root_path: Path):
    if _looks_like_dst_cluster(root_path):
        yield root_path
        return

    for profile_dir in root_path.iterdir():
        if not profile_dir.is_dir():
            continue
        if _is_ignored_dst_dir(profile_dir):
            continue

        if _looks_like_dst_cluster(profile_dir):
            yield profile_dir
            continue

        candidates = [*profile_dir.glob("Cluster_*")]
        candidates.extend(child for child in profile_dir.iterdir() if child.is_dir())

        for candidate in candidates:
            if _is_ignored_dst_dir(candidate):
                continue
            if _looks_like_dst_cluster(candidate):
                yield candidate

        # Some layouts have one extra folder between the account id and Cluster_*.
        for child in profile_dir.iterdir():
            if not child.is_dir() or _is_ignored_dst_dir(child):
                continue
            for cluster_dir in child.glob("Cluster_*"):
                if cluster_dir.is_dir() and _looks_like_dst_cluster(cluster_dir):
                    yield cluster_dir


def _looks_like_dst_cluster(cluster_dir: Path) -> bool:
    return any(
        [
            (cluster_dir / "cluster.ini").exists(),
            (cluster_dir / "Master").is_dir(),
            (cluster_dir / "Caves").is_dir(),
        ]
    )


def _looks_like_stardew_save_dir(save_dir: Path) -> bool:
    if (save_dir / "SaveGameInfo").is_file():
        return True
    return any(
        path.is_file() and path.name.startswith(f"{save_dir.name}_")
        for path in save_dir.iterdir()
    )


def _looks_like_project_zomboid_save_dir(save_dir: Path) -> bool:
    return any(
        [
            (save_dir / "map_ver.bin").is_file(),
            (save_dir / "map.bin").is_file(),
            (save_dir / "players.db").is_file(),
            (save_dir / "worlddictionary.bin").is_file(),
        ]
    )


def _is_ignored_dst_dir(path: Path) -> bool:
    return path.name in {"backup", "client_save", "CloudSaves", "Agreements"}


def _dedupe_packages(packages: list[SavePackage]) -> list[SavePackage]:
    seen: set[str] = set()
    unique: list[SavePackage] = []
    for package in packages:
        key = str(Path(package.path)).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(package)
    return unique
