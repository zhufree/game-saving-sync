"""Small signaling + relay fallback server.

Run with:
    uv run python src\relay_server.py --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

import argparse
import json
import secrets
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class RelayStore:
    """File-backed relay session store."""

    def __init__(self, storage_dir: str, ttl_seconds: int = 86400) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def create_session(self, payload: dict[str, object]) -> dict[str, object]:
        self.cleanup_expired()
        code = self._new_code()
        upload_token = secrets.token_urlsafe(24)
        now = time.time()
        session = {
            "code": code,
            "upload_token": upload_token,
            "pairing_key": payload.get("pairing_key", ""),
            "filename": payload.get("filename", "save.zip"),
            "size_bytes": int(payload.get("size_bytes", 0)),
            "sha256": payload.get("sha256", ""),
            "file_count": int(payload.get("file_count", 0)),
            "created_at": now,
            "expires_at": float(payload.get("expires_at", now + self.ttl_seconds)),
            "relay_available": False,
        }
        self._write_session(code, session)
        return session

    def public_session(self, code: str) -> dict[str, object]:
        session = self.get_session(code)
        return {
            key: value
            for key, value in session.items()
            if key not in {"upload_token"}
        }

    def get_session(self, code: str) -> dict[str, object]:
        path = self._session_path(code)
        if not path.exists():
            raise KeyError(code)
        session = json.loads(path.read_text(encoding="utf-8"))
        if time.time() > float(session["expires_at"]):
            self.delete_session(code)
            raise KeyError(code)
        return session

    def store_archive(self, code: str, upload_token: str, body: bytes) -> None:
        session = self.get_session(code)
        if upload_token != session["upload_token"]:
            raise PermissionError("invalid upload token")
        self._archive_path(code).write_bytes(body)
        session["relay_available"] = True
        self._write_session(code, session)

    def archive_path(self, code: str) -> Path:
        self.get_session(code)
        path = self._archive_path(code)
        if not path.exists():
            raise FileNotFoundError(code)
        return path

    def cleanup_expired(self) -> None:
        now = time.time()
        for path in self.storage_dir.glob("*.json"):
            try:
                session = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if now > float(session.get("expires_at", 0)):
                self.delete_session(path.stem)

    def delete_session(self, code: str) -> None:
        self._session_path(code).unlink(missing_ok=True)
        self._archive_path(code).unlink(missing_ok=True)

    def _new_code(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if not self._session_path(code).exists():
                return code

    def _session_path(self, code: str) -> Path:
        return self.storage_dir / f"{code}.json"

    def _archive_path(self, code: str) -> Path:
        return self.storage_dir / f"{code}.zip"

    def _write_session(self, code: str, session: dict[str, object]) -> None:
        self._session_path(code).write_text(
            json.dumps(session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class RelayRequestHandler(BaseHTTPRequestHandler):
    """HTTP API handler for signaling and relay file transfer."""

    store: RelayStore

    def do_POST(self) -> None:
        if self.path != "/api/sessions":
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return

        payload = self._read_json()
        session = self.store.create_session(payload)
        self._send_json(
            {
                "code": session["code"],
                "upload_token": session["upload_token"],
                "expires_at": session["expires_at"],
            }
        )

    def do_GET(self) -> None:
        parts = _path_parts(self.path)
        if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
            self._get_session(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "archive":
            self._get_archive(parts[2])
            return
        self._json_error(HTTPStatus.NOT_FOUND, "not found")

    def do_PUT(self) -> None:
        parts = _path_parts(self.path)
        if len(parts) != 4 or parts[:2] != ["api", "sessions"] or parts[3] != "archive":
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return

        code = parts[2]
        token = self.headers.get("X-Upload-Token", "")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            self.store.store_archive(code, token, body)
        except KeyError:
            self._json_error(HTTPStatus.NOT_FOUND, "session not found")
            return
        except PermissionError:
            self._json_error(HTTPStatus.FORBIDDEN, "invalid upload token")
            return
        self._send_json({"ok": True})

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _get_session(self, code: str) -> None:
        try:
            self._send_json(self.store.public_session(code))
        except KeyError:
            self._json_error(HTTPStatus.NOT_FOUND, "session not found")

    def _get_archive(self, code: str) -> None:
        try:
            path = self.store.archive_path(code)
            session = self.store.public_session(code)
        except KeyError:
            self._json_error(HTTPStatus.NOT_FOUND, "session not found")
            return
        except FileNotFoundError:
            self._json_error(HTTPStatus.NOT_FOUND, "archive not uploaded")
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Archive-Sha256", str(session.get("sha256", "")))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status)


def create_server(host: str, port: int, storage_dir: str, ttl_seconds: int) -> ThreadingHTTPServer:
    """Create a relay HTTP server."""
    RelayRequestHandler.store = RelayStore(storage_dir, ttl_seconds)
    return ThreadingHTTPServer((host, port), RelayRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Game Save Transfer relay server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--storage", default="./relay_storage")
    parser.add_argument("--ttl-seconds", type=int, default=86400)
    args = parser.parse_args()

    server = create_server(args.host, args.port, args.storage, args.ttl_seconds)
    print(f"Relay server listening on http://{args.host}:{args.port}")
    print(f"Storage directory: {Path(args.storage).resolve()}")
    server.serve_forever()


def _path_parts(path: str) -> list[str]:
    return [part for part in urlparse(path).path.split("/") if part]


if __name__ == "__main__":
    main()
