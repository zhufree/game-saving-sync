"""Application configuration models."""

import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class GameEntry(BaseModel):
    """A Steam game and the save locations discovered for it."""

    app_id: str
    name: str
    install_path: str = ""
    save_paths: list[str] = Field(default_factory=list)
    save_packages: list["SavePackage"] = Field(default_factory=list)
    rule_id: str = ""


class SavePackage(BaseModel):
    """A concrete transferable save unit, such as a DST Cluster folder."""

    id: str
    label: str
    path: str
    root_path: str = ""
    package_type: str = "directory"
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class SaveLocationTemplate(BaseModel):
    """A configurable save-location pattern for supported game rules."""

    id: str
    label: str
    path_template: str


class TransferRecord(BaseModel):
    """A completed or attempted save transfer."""

    transfer_id: str
    game_id: str
    game_name: str
    direction: str = "send"  # send, receive
    status: str = "pending"  # pending, transferring, completed, failed
    target_path: str = ""
    created_at: str = ""


class AppConfig(BaseModel):
    """Persistent application configuration."""

    steam_root: str = ""
    steam_libraries: list[str] = Field(default_factory=list)
    relay_server_url: str = ""
    save_location_templates: list[SaveLocationTemplate] = Field(default_factory=list)
    snapshot_dir: str = "./snapshots"
    known_games: list[GameEntry] = Field(default_factory=list)
    transfer_history: list[TransferRecord] = Field(default_factory=list)
    first_run: bool = True
    language: str = "zh_CN"

    def model_post_init(self, __context: object) -> None:
        """Ensure new configs include editable save-location templates."""
        if not self.save_location_templates:
            self.save_location_templates = [
                SaveLocationTemplate(**template) for template in default_save_location_templates()
            ]

    @classmethod
    def load(cls, config_path: str = "config.json") -> "AppConfig":
        """Load configuration from disk, migrating old sync-era fields when present."""
        path = Path(config_path)
        if not path.exists():
            logger.info(f"Config file does not exist, creating defaults: {config_path}")
            config = cls()
            config.save(config_path)
            return config

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            migrated = cls._migrate_legacy_config(data)
            logger.info(f"Config loaded: {config_path}")
            return cls(**migrated)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.info("Using default config")
            return cls()

    @staticmethod
    def _migrate_legacy_config(data: dict[str, Any]) -> dict[str, Any]:
        """Map the old DST/Syncthing config shape into the new transfer model."""
        migrated = dict(data)

        if "backup_dir" in migrated and "snapshot_dir" not in migrated:
            migrated["snapshot_dir"] = migrated["backup_dir"]

        legacy_dst_path = migrated.get("dst_save_path")
        if legacy_dst_path and not migrated.get("known_games"):
            migrated["known_games"] = [
                {
                    "app_id": "322330",
                    "name": "Don't Starve Together",
                    "save_paths": [legacy_dst_path],
                    "rule_id": "dst-default",
                }
            ]

        if not migrated.get("save_location_templates"):
            migrated["save_location_templates"] = default_save_location_templates()

        # Drop fields that belonged to the old continuous-sync design.
        for key in [
            "dst_save_path",
            "syncthing_path",
            "syncthing_api_key",
            "syncthing_api_url",
            "backup_dir",
            "sync_groups",
        ]:
            migrated.pop(key, None)

        return migrated

    def save(self, config_path: str = "config.json") -> None:
        """Save configuration to disk."""
        try:
            path = Path(config_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved: {config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise

    def add_game(self, game: GameEntry) -> None:
        """Add or replace a discovered game entry, preserving manual save paths."""
        existing = self.get_game(game.app_id)
        if existing:
            merged_paths = [*existing.save_paths, *game.save_paths]
            game.save_paths = list(dict.fromkeys(merged_paths))
            merged_packages = [*existing.save_packages, *game.save_packages]
            game.save_packages = list({package.id: package for package in merged_packages}.values())

        self.known_games = [g for g in self.known_games if g.app_id != game.app_id]
        self.known_games.append(game)
        logger.info(f"Game added: {game.name}")

    def get_game(self, app_id: str) -> GameEntry | None:
        """Return a discovered game by Steam app id."""
        for game in self.known_games:
            if game.app_id == app_id:
                return game
        return None

    def add_transfer_record(self, record: TransferRecord) -> None:
        """Append a transfer history record."""
        self.transfer_history.append(record)
        logger.info(f"Transfer recorded: {record.transfer_id}")


def default_save_location_templates() -> list[dict[str, str]]:
    """Common user-folder save locations stored in the config by default."""
    return [
        {
            "id": "documents-game",
            "label": "Documents/{game_name}",
            "path_template": "{DOCUMENTS}\\{game_name}",
        },
        {
            "id": "documents-my-games",
            "label": "Documents/My Games/{game_name}",
            "path_template": "{DOCUMENTS}\\My Games\\{game_name}",
        },
        {
            "id": "saved-games",
            "label": "Saved Games/{game_name}",
            "path_template": "{USERPROFILE}\\Saved Games\\{game_name}",
        },
        {
            "id": "appdata-roaming",
            "label": "AppData/Roaming/{game_name}",
            "path_template": "{APPDATA}\\{game_name}",
        },
        {
            "id": "appdata-local",
            "label": "AppData/Local/{game_name}",
            "path_template": "{LOCALAPPDATA}\\{game_name}",
        },
        {
            "id": "appdata-local-low",
            "label": "AppData/LocalLow/{game_name}",
            "path_template": "{USERPROFILE}\\AppData\\LocalLow\\{game_name}",
        },
        {
            "id": "steam-userdata-app",
            "label": "Steam userdata/{app_id}",
            "path_template": "{STEAM_USERDATA}\\{app_id}",
        },
        {
            "id": "install-save",
            "label": "Install folder/save",
            "path_template": "{INSTALL_PATH}\\save",
        },
        {
            "id": "install-saves",
            "label": "Install folder/saves",
            "path_template": "{INSTALL_PATH}\\saves",
        },
        {
            "id": "install-saved",
            "label": "Install folder/Saved",
            "path_template": "{INSTALL_PATH}\\Saved",
        },
    ]
