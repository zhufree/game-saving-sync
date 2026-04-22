"""Client helpers for the signaling + relay fallback server."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

try:
    from .p2p_transport import PairingKey, receive_archive
    from .save_package_builder import BuiltSaveArchive, sha256_file
except ImportError:
    from p2p_transport import PairingKey, receive_archive
    from save_package_builder import BuiltSaveArchive, sha256_file


@dataclass(frozen=True)
class RelayTransferKey:
    """Short user-facing key that points at a relay/signaling session."""

    kind: str
    server_url: str
    code: str

    def encode(self, compact: bool = False) -> str:
        if compact:
            return f"GST-{self.code}"
        payload = json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")
        return "GST-" + base64.urlsafe_b64encode(payload).decode("ascii")

    @classmethod
    def decode(cls, value: str, server_url: str = "") -> RelayTransferKey:
        text = value.strip()
        if not text.startswith("GST-"):
            raise ValueError("Not a relay transfer key")

        body = text.removeprefix("GST-")
        try:
            padded = body + "=" * (-len(body) % 4)
            payload = base64.urlsafe_b64decode(padded.encode("ascii"))
            data = json.loads(payload.decode("utf-8"))
            key = cls(**data)
            if key.kind != "relay":
                raise ValueError(f"Unsupported transfer key kind: {key.kind}")
            return key
        except Exception:
            if not server_url:
                raise ValueError("Short relay key requires a relay server URL")
            return cls(kind="relay", server_url=server_url, code=body)


@dataclass(frozen=True)
class RelaySession:
    """A session registered on the relay server."""

    code: str
    upload_token: str
    transfer_key: str


def is_relay_transfer_key(value: str) -> bool:
    """Return whether text looks like a relay transfer key."""
    return value.strip().startswith("GST-")


def create_relay_session(
    server_url: str,
    pairing_key: PairingKey,
    archive: BuiltSaveArchive,
    timeout_seconds: float = 30.0,
) -> RelaySession:
    """Register signaling metadata and upload the archive as relay fallback."""
    base_url = _normalize_server_url(server_url)
    response = httpx.post(
        f"{base_url}/api/sessions",
        json={
            "pairing_key": pairing_key.encode(),
            "filename": Path(archive.archive_path).name,
            "size_bytes": archive.size_bytes,
            "sha256": archive.sha256,
            "file_count": archive.file_count,
            "expires_at": pairing_key.expires_at,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    code = data["code"]
    upload_token = data["upload_token"]

    with open(archive.archive_path, "rb") as f:
        upload = httpx.put(
            f"{base_url}/api/sessions/{code}/archive",
            headers={"X-Upload-Token": upload_token},
            content=f.read(),
            timeout=timeout_seconds,
        )
    upload.raise_for_status()

    transfer_key = RelayTransferKey(
        kind="relay",
        server_url=base_url,
        code=code,
    ).encode(compact=True)
    return RelaySession(code=code, upload_token=upload_token, transfer_key=transfer_key)


def receive_with_relay_fallback(
    transfer_key: str,
    output_dir: str,
    server_url: str = "",
    timeout_seconds: float = 20.0,
) -> str:
    """Try direct P2P first, then download the relay archive if direct fails."""
    relay_key = RelayTransferKey.decode(transfer_key, server_url=server_url)
    base_url = _normalize_server_url(relay_key.server_url)

    session = httpx.get(f"{base_url}/api/sessions/{relay_key.code}", timeout=timeout_seconds)
    session.raise_for_status()
    metadata = session.json()

    direct_error: Exception | None = None
    pairing_key = metadata.get("pairing_key")
    if isinstance(pairing_key, str) and pairing_key:
        try:
            return receive_archive(
                pairing_key,
                output_dir,
                timeout_seconds=timeout_seconds,
            ).archive_path
        except Exception as e:
            direct_error = e

    if not metadata.get("relay_available"):
        if direct_error:
            raise ConnectionError(f"直连失败，且服务器没有可下载的中继文件: {direct_error}")
        raise FileNotFoundError("服务器没有可下载的中继文件")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(str(metadata.get("filename", "received-save.zip")))
    archive_path = output / filename

    with httpx.stream(
        "GET",
        f"{base_url}/api/sessions/{relay_key.code}/archive",
        timeout=timeout_seconds,
    ) as response:
        response.raise_for_status()
        with open(archive_path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

    digest = sha256_file(archive_path)
    if digest != metadata.get("sha256"):
        archive_path.unlink(missing_ok=True)
        raise ValueError("中继下载文件校验失败")

    return str(archive_path)


def _normalize_server_url(server_url: str) -> str:
    value = server_url.strip().rstrip("/")
    if not value:
        raise ValueError("Relay server URL is empty")
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value


def _safe_filename(value: str) -> str:
    name = Path(value).name or "received-save.zip"
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name
