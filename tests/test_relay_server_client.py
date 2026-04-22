"""Relay server/client integration tests."""

import threading
import time

import httpx

from src.config import SavePackage
from src.p2p_transport import DirectTcpSender, receive_archive
from src.relay_client import (
    RelayTransferKey,
    create_relay_session,
    receive_with_relay_fallback,
)
from src.relay_server import create_server
from src.save_package_builder import build_save_archive


def test_relay_transfer_key_round_trip():
    """Relay keys can still encode a server URL for backward compatibility."""
    key = RelayTransferKey(kind="relay", server_url="http://localhost:8765", code="ABCDEFGH")

    decoded = RelayTransferKey.decode(key.encode())

    assert decoded == key


def test_short_relay_transfer_key_uses_configured_server_url():
    """Short user-facing relay keys keep the visible GST prefix and code."""
    key = RelayTransferKey(kind="relay", server_url="http://localhost:8765", code="ABCDEFGH")

    encoded = key.encode(compact=True)
    decoded = RelayTransferKey.decode(encoded, server_url="http://localhost:8765")

    assert encoded == "GST-ABCDEFGH"
    assert decoded == key


def test_relay_fallback_downloads_archive_when_direct_fails(tmp_path):
    """Receiver falls back to server archive if the direct sender is unavailable."""
    server, thread = _start_relay_server(tmp_path)
    try:
        archive = _build_test_archive(tmp_path)
        sender = DirectTcpSender(archive, host="127.0.0.1", port=0)
        pairing_key = sender.start()
        sender.close()
        server_url = _server_url(server)
        session = create_relay_session(server_url, pairing_key, archive)

        received_path = receive_with_relay_fallback(
            session.transfer_key,
            str(tmp_path / "in"),
            server_url=server_url,
        )

        assert received_path.endswith(".zip")
        assert (tmp_path / "in").exists()
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_relay_direct_path_still_works_before_fallback(tmp_path):
    """Relay keys still allow direct P2P when the sender is reachable."""
    server, thread = _start_relay_server(tmp_path)
    try:
        archive = _build_test_archive(tmp_path)
        sender = DirectTcpSender(archive, host="127.0.0.1", port=0)
        pairing_key = sender.start()
        server_url = _server_url(server)
        session = create_relay_session(server_url, pairing_key, archive)

        errors = []

        def serve() -> None:
            try:
                sender.serve_once(timeout_seconds=10)
            except Exception as e:  # pragma: no cover - asserted below
                errors.append(e)
            finally:
                sender.close()

        send_thread = threading.Thread(target=serve, daemon=True)
        send_thread.start()

        received_path = receive_with_relay_fallback(
            session.transfer_key,
            str(tmp_path / "in"),
            server_url=server_url,
        )

        send_thread.join(timeout=5)
        assert errors == []
        assert received_path.endswith(".zip")
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_direct_receive_still_accepts_raw_pairing_key(tmp_path):
    """Raw direct pairing keys remain supported."""
    archive = _build_test_archive(tmp_path)
    sender = DirectTcpSender(archive, host="127.0.0.1", port=0)
    pairing_key = sender.start()

    thread = threading.Thread(target=sender.serve_once, daemon=True)
    thread.start()

    received = receive_archive(pairing_key.encode(), str(tmp_path / "in"), timeout_seconds=10)
    sender.close()

    assert received.sha256 == archive.sha256


def test_version_api_reports_update_url_when_client_is_old(tmp_path):
    """Relay server exposes a tiny client update check endpoint."""
    server, thread = _start_relay_server(tmp_path, latest_version="0.3.0")
    try:
        response = httpx.get(
            f"{_server_url(server)}/api/version",
            params={"current_version": "0.2.0"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["latest_version"] == "0.3.0"
        assert data["update_available"] is True
        assert data["update_url"] == "https://github.com/zhufree/game-saving-sync"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_version_api_reports_no_update_for_current_client(tmp_path):
    """Current clients can verify that no update is required."""
    server, thread = _start_relay_server(tmp_path, latest_version="0.3.0")
    try:
        response = httpx.get(
            f"{_server_url(server)}/api/version",
            params={"current_version": "0.3.0"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["update_available"] is False
        assert data["update_url"] == ""
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _start_relay_server(tmp_path, latest_version="0.2.0"):
    server = create_server(
        "127.0.0.1",
        0,
        str(tmp_path / "relay"),
        ttl_seconds=60,
        latest_version=latest_version,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    return server, thread


def _server_url(server) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}"


def _build_test_archive(tmp_path):
    source = tmp_path / "Cluster_1"
    (source / "Master" / "save").mkdir(parents=True)
    (source / "Master" / "save" / "session").write_text("world", encoding="utf-8")
    return build_save_archive(
        SavePackage(
            id="322330:test",
            label="Cluster_1",
            path=str(source),
            include_patterns=["Master/**"],
            metadata={"app_id": "322330", "cluster": "Cluster_1"},
        ),
        str(tmp_path / "out"),
    )
