"""Game Save Transfer application entry point."""

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QApplication

from config import AppConfig
from save_discovery import discover_supported_games
from steam_library import discover_installed_games, discover_steam_libraries
from utils import detect_steam_path

APP_NAME = "Game Save Transfer"


def setup_logging() -> None:
    """Configure console and file logging."""
    logger.remove()

    if sys.stderr:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
                "<level>{message}</level>"
            ),
            level="INFO",
            colorize=True,
        )

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "game_save_transfer_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Logging initialized")


def initialize_app() -> AppConfig:
    """Initialize application configuration and first-run defaults."""
    logger.info("=" * 60)
    logger.info(f"{APP_NAME} starting")
    logger.info("=" * 60)

    config = AppConfig.load()

    if config.first_run:
        logger.info("First run detected, initializing defaults...")

        if not config.steam_root:
            steam_path = detect_steam_path()
            if steam_path:
                config.steam_root = steam_path
                logger.info(f"Detected Steam path: {steam_path}")
            else:
                logger.warning("Steam path was not detected; user must configure it in the GUI")

        if config.steam_root:
            config.steam_libraries = discover_steam_libraries(config.steam_root)
            installed_games = discover_installed_games(config.steam_root)
            supported_games = discover_supported_games(
                installed_games,
                config.steam_root,
                config.save_location_templates,
            )
            for game in supported_games:
                config.add_game(game=game)
            logger.info(
                f"Discovered {len(config.steam_libraries)} Steam libraries and "
                f"{len(installed_games)} installed games; "
                f"{len(supported_games)} are currently supported"
            )

        snapshot_dir = Path(config.snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Snapshot directory: {snapshot_dir.absolute()}")

        config.first_run = False
        config.save()
        logger.info("Initialization complete")

    return config


def main() -> int:
    """Run the application."""
    try:
        setup_logging()
        config = initialize_app()

        logger.info("Current configuration:")
        logger.info(f"  Steam path: {config.steam_root or 'not set'}")
        logger.info(f"  Steam libraries: {len(config.steam_libraries)}")
        logger.info(f"  Snapshot directory: {config.snapshot_dir}")
        logger.info(f"  Known games: {len(config.known_games)}")
        logger.info(f"  Transfer records: {len(config.transfer_history)}")

        logger.info("Starting qfluentwidgets GUI...")
        from ui.main_window import MainWindow

        app = QApplication(sys.argv)
        window = MainWindow(config)
        window.show()

        return app.exec()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.exception(f"Application exited unexpectedly: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
