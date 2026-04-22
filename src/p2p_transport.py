"""Minimal direct peer-to-peer transfer over TCP.

This is the first transport prototype. It works on localhost/LAN and gives the
rest of the app a stable pairing-key + send/receive API before we tackle NAT
traversal or relay fallback.
"""

from __future__ import annotations

import base64
import json
import secrets
import socket
import struct
import time
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .save_package_builder import BuiltSaveArchive, sha256_file
except ImportError:
    from save_package_builder import BuiltSaveArchive, sha256_file

PROTOCOL_VERSION = 1
HEADER_SIZE = 8
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class PairingKey:
    """Connection details shared from sender to receiver."""

    version: int
    session_id: str
    host: str
    port: int
    token: str
    expires_at: float

    def encode(self) -> str:
        """Encode a pairing key into URL-safe text."""
        payload = json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    @classmethod
    def decode(cls, value: str) -> PairingKey:
        """Decode and validate pairing-key text."""
        try:
            payload = base64.urlsafe_b64decode(value.encode("ascii"))
            data = json.loads(payload.decode("utf-8"))
            key = cls(**data)
        except Exception as e:
            raise ValueError(f"Invalid pairing key: {e}") from e

        if key.version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported pairing protocol version: {key.version}")
        return key

    def is_expired(self) -> bool:
        """Return whether the key has expired."""
        return time.time() > self.expires_at


@dataclass(frozen=True)
class ReceivedArchive:
    """A received archive and its metadata."""

    archive_path: str
    metadata: dict[str, object]
    sha256: str
    size_bytes: int


def create_pairing_key(host: str, port: int, ttl_seconds: int = 600) -> PairingKey:
    """Create a new pairing key for a listening sender."""
    return PairingKey(
        version=PROTOCOL_VERSION,
        session_id=secrets.token_urlsafe(12),
        host=host,
        port=port,
        token=secrets.token_urlsafe(24),
        expires_at=time.time() + ttl_seconds,
    )


class DirectTcpSender:
    """One-shot TCP sender for a built save archive."""

    def __init__(
        self,
        archive: BuiltSaveArchive,
        host: str = "0.0.0.0",
        port: int = 0,
        ttl_seconds: int = 600,
    ) -> None:
        self.archive = archive
        self.host = host
        self.port = port
        self.ttl_seconds = ttl_seconds
        self._server: socket.socket | None = None
        self.pairing_key: PairingKey | None = None

    def start(self) -> PairingKey:
        """Bind a local socket and return a pairing key."""
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(1)
        bound_host, bound_port = self._server.getsockname()
        share_host = _default_share_host(bound_host)
        self.pairing_key = create_pairing_key(share_host, bound_port, self.ttl_seconds)
        return self.pairing_key

    def serve_once(self, timeout_seconds: float = 120.0) -> None:
        """Accept one receiver and transfer the archive."""
        if not self._server or not self.pairing_key:
            raise RuntimeError("Sender has not been started")
        if self.pairing_key.is_expired():
            raise TimeoutError("Pairing key has expired")

        self._server.settimeout(timeout_seconds)
        connection, _ = self._server.accept()
        with connection:
            request = _recv_json(connection)
            if request.get("token") != self.pairing_key.token:
                _send_json(connection, {"ok": False, "error": "invalid token"})
                raise PermissionError("Receiver provided an invalid token")

            archive_path = Path(self.archive.archive_path)
            metadata = {
                "ok": True,
                "session_id": self.pairing_key.session_id,
                "package_id": self.archive.package_id,
                "label": self.archive.label,
                "filename": archive_path.name,
                "size_bytes": self.archive.size_bytes,
                "sha256": self.archive.sha256,
                "file_count": self.archive.file_count,
            }
            _send_json(connection, metadata)

            with open(archive_path, "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    connection.sendall(chunk)

    def close(self) -> None:
        """Close the listening socket."""
        if self._server:
            self._server.close()
            self._server = None


def receive_archive(
    pairing_key_text: str,
    output_dir: str,
    timeout_seconds: float = 120.0,
) -> ReceivedArchive:
    """Connect to a sender using a pairing key and receive an archive."""
    pairing_key = PairingKey.decode(pairing_key_text)
    if pairing_key.is_expired():
        raise TimeoutError("Pairing key has expired")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    with socket.create_connection(
        (pairing_key.host, pairing_key.port),
        timeout=timeout_seconds,
    ) as client:
        client.settimeout(timeout_seconds)
        _send_json(client, {"token": pairing_key.token, "session_id": pairing_key.session_id})
        metadata = _recv_json(client)
        if not metadata.get("ok"):
            raise PermissionError(str(metadata.get("error", "sender rejected connection")))

        filename = _safe_filename(str(metadata.get("filename", "received-save.zip")))
        archive_path = output / filename
        expected_size = int(metadata["size_bytes"])

        remaining = expected_size
        with open(archive_path, "wb") as f:
            while remaining > 0:
                chunk = client.recv(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ConnectionError("Connection closed before transfer completed")
                f.write(chunk)
                remaining -= len(chunk)

    digest = sha256_file(archive_path)
    if digest != metadata.get("sha256"):
        archive_path.unlink(missing_ok=True)
        raise ValueError("Received archive checksum mismatch")

    return ReceivedArchive(
        archive_path=str(archive_path),
        metadata=metadata,
        sha256=digest,
        size_bytes=archive_path.stat().st_size,
    )


def _send_json(connection: socket.socket, payload: dict[str, object]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    connection.sendall(struct.pack("!Q", len(data)))
    connection.sendall(data)


def _recv_json(connection: socket.socket) -> dict[str, object]:
    size = struct.unpack("!Q", _recv_exact(connection, HEADER_SIZE))[0]
    data = _recv_exact(connection, size)
    return json.loads(data.decode("utf-8"))


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("Connection closed while reading framed message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _default_share_host(bound_host: str) -> str:
    if bound_host not in {"0.0.0.0", "::"}:
        return bound_host
    return _detect_lan_ip()


def _detect_lan_ip() -> str:
    """Best-effort LAN IP detection for pairing keys."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def _safe_filename(value: str) -> str:
    name = Path(value).name or "received-save.zip"
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name
