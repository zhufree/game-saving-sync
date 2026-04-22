"""Utility helpers."""

import os
from pathlib import Path

import psutil
import segno
from loguru import logger

try:
    from winotify import Notification

    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False
    from plyer import notification


def detect_steam_path() -> str | None:
    """Detect a likely Steam installation path on Windows."""
    candidates = []

    for env_name in ["PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"]:
        root = os.environ.get(env_name)
        if root:
            candidates.append(Path(root) / "Steam")

    for candidate in candidates:
        if (candidate / "steam.exe").exists() or (candidate / "steamapps").exists():
            logger.info(f"Detected Steam path: {candidate}")
            return str(candidate)

    logger.warning("Steam path was not detected")
    return None


def detect_dst_path() -> str | None:
    """Detect the default Don't Starve Together save path as a legacy built-in rule."""
    userprofile = os.environ.get("USERPROFILE", "")
    if not userprofile:
        logger.warning("USERPROFILE environment variable is unavailable")
        return None

    default_path = Path(userprofile) / "Documents" / "Klei" / "DoNotStarveTogether"

    if default_path.exists():
        logger.info(f"Detected DST save path: {default_path}")
        return str(default_path)

    logger.warning(f"Default DST path does not exist: {default_path}")
    return None


def validate_path(path: str) -> bool:
    """Return whether a path exists and is a directory."""
    if not path:
        return False

    p = Path(path)
    return p.exists() and p.is_dir()


def expand_path(path: str) -> str:
    """Expand environment variables and user-home markers."""
    return os.path.expandvars(os.path.expanduser(path))


def is_dst_running() -> bool:
    """Detect whether Don't Starve Together appears to be running."""
    try:
        for proc in psutil.process_iter(["name"]):
            proc_name = (proc.info.get("name") or "").lower()
            if "dontstarve" in proc_name or "dst" in proc_name:
                logger.info(f"Detected DST process: {proc.info['name']}")
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to inspect processes: {e}")
        return False


def generate_qr_code(data: str, output_path: str, scale: int = 5) -> bool:
    """Generate a QR code image."""
    try:
        qr = segno.make(data)
        qr.save(output_path, scale=scale, border=2)
        logger.info(f"QR code generated: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return False


def show_notification(title: str, message: str, duration: int = 3) -> None:
    """Show a desktop notification when the platform supports it."""
    try:
        if WINOTIFY_AVAILABLE:
            toast = Notification(
                app_id="Game Save Transfer",
                title=title,
                msg=message,
            )
            toast.show()
        else:
            notification.notify(
                title=title,
                message=message,
                app_name="Game Save Transfer",
                timeout=duration,
            )
        logger.debug(f"Notification shown: {title}")
    except Exception as e:
        logger.error(f"Failed to show notification: {e}")


def format_size(size_bytes: int) -> str:
    """Format bytes as a human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
