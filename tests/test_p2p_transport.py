"""Direct TCP P2P transport tests."""

import threading
import time
import zipfile

import pytest

from src.config import SavePackage
from src.p2p_transport import DirectTcpSender, PairingKey, receive_archive
from src.save_package_builder import build_save_archive


def test_pairing_key_round_trip():
    """Pairing keys can be encoded and decoded."""
    key = PairingKey(
        version=1,
        session_id="session",
        host="127.0.0.1",
        port=12345,
        token="token",
        expires_at=time.time() + 60,
    )

    decoded = PairingKey.decode(key.encode())

    assert decoded == key
    assert decoded.is_expired() is False


def test_pairing_key_rejects_invalid_text():
    """Invalid pairing text gives a friendly ValueError."""
    with pytest.raises(ValueError, match="Invalid pairing key"):
        PairingKey.decode("not-a-pairing-key")


def test_direct_tcp_transfer_round_trip(tmp_path):
    """A sender and receiver can transfer a save archive over localhost."""
    world = tmp_path / "Cluster_1"
    (world / "Master" / "save").mkdir(parents=True)
    (world / "Master" / "save" / "session").write_text("world-data", encoding="utf-8")
    package = SavePackage(
        id="dst:cluster",
        label="Cluster_1",
        path=str(world),
        include_patterns=["Master/**"],
    )
    archive = build_save_archive(package, str(tmp_path / "archives"))
    sender = DirectTcpSender(archive, host="127.0.0.1", port=0)
    pairing_key = sender.start()

    errors = []

    def serve() -> None:
        try:
            sender.serve_once(timeout_seconds=10)
        except Exception as e:  # pragma: no cover - surfaced below
            errors.append(e)
        finally:
            sender.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    received = receive_archive(pairing_key.encode(), str(tmp_path / "received"), timeout_seconds=10)
    thread.join(timeout=10)

    assert errors == []
    assert received.sha256 == archive.sha256
    assert received.size_bytes == archive.size_bytes
    with zipfile.ZipFile(received.archive_path) as zf:
        assert zf.read("Master/save/session") == b"world-data"


def test_direct_tcp_transfer_rejects_wrong_token(tmp_path):
    """Sender rejects receivers with the wrong token."""
    world = tmp_path / "Cluster_1"
    world.mkdir()
    (world / "cluster.ini").write_text("[GAMEPLAY]", encoding="utf-8")
    archive = build_save_archive(
        SavePackage(id="dst:cluster", label="Cluster_1", path=str(world)),
        str(tmp_path / "archives"),
    )
    sender = DirectTcpSender(archive, host="127.0.0.1", port=0)
    pairing_key = sender.start()
    bad_key = PairingKey(
        version=pairing_key.version,
        session_id=pairing_key.session_id,
        host=pairing_key.host,
        port=pairing_key.port,
        token="wrong",
        expires_at=pairing_key.expires_at,
    )

    errors = []

    def serve() -> None:
        try:
            sender.serve_once(timeout_seconds=10)
        except Exception as e:
            errors.append(e)
        finally:
            sender.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    with pytest.raises(PermissionError):
        receive_archive(bad_key.encode(), str(tmp_path / "received"), timeout_seconds=10)

    thread.join(timeout=10)
    assert errors
    assert isinstance(errors[0], PermissionError)
