"""Minimal client for a hosted libSQL / Turso database over its HTTP API.

libSQL speaks the SQLite dialect, so the exact same SQL used locally runs remotely.
This adapter exposes just enough of the ``sqlite3`` connection interface
(``execute`` -> cursor with ``fetchone/fetchall/rowcount/lastrowid``) for
``DatabaseManager``. It uses plain ``requests`` - no native driver is needed, which
keeps deployment on Streamlit Community Cloud simple.

Docs: https://docs.turso.tech/sdk/http/reference  (POST /v2/pipeline)
Configuration (environment variables / Streamlit secrets):
    TURSO_DATABASE_URL   e.g. libsql://my-db-myorg.turso.io
    TURSO_AUTH_TOKEN     database token
"""
from __future__ import annotations

import base64
import os
import sqlite3
from typing import Any, Optional, Sequence

import requests

TIMEOUT = (5, 25)


class RemoteDBError(sqlite3.Error):
    """Raised for network, authentication or SQL errors from the hosted database."""


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    for prefix in ("libsql://", "wss://", "ws://"):
        if url.startswith(prefix):
            url = "https://" + url[len(prefix):]
    if not url.startswith(("https://", "http://")):
        url = "https://" + url
    return url


def remote_config_from_env() -> Optional[tuple[str, str]]:
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if url and token:
        return normalize_url(url), token
    return None


def _encode_arg(value: Any) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(value)).decode("ascii")}
    return {"type": "text", "value": str(value)}


def _decode_value(cell: dict) -> Any:
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    if kind == "blob":
        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")


class RemoteRow:
    """Row supporting ``row[0]``, ``row["name"]``, ``keys()``, iteration and ``dict(row)``."""

    __slots__ = ("_cols", "_values")

    def __init__(self, cols: list[str], values: list[Any]):
        self._cols, self._values = cols, values

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return self._values[self._cols.index(key)]
            except ValueError:
                raise IndexError(f"No item with that key: {key!r}") from None
        return self._values[key]

    def keys(self) -> list[str]:
        return list(self._cols)

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class RemoteCursor:
    def __init__(self, rows: list[RemoteRow], rowcount: int, lastrowid: Optional[int]):
        self._rows, self.rowcount, self.lastrowid = rows, rowcount, lastrowid

    def fetchone(self) -> Optional[RemoteRow]:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[RemoteRow]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class RemoteConnection:
    """Stateless connection: every ``execute`` is one HTTPS request."""

    def __init__(self, url: str, token: str, session: Optional[requests.Session] = None, timeout=TIMEOUT):
        self.url = normalize_url(url)
        self.token = token
        self.session = session or requests.Session()
        self.timeout = timeout
        self.row_factory = None  # kept for interface compatibility; rows are always RemoteRow

    # --- sqlite3-like surface
    def execute(self, sql: str, params: Sequence[Any] = ()) -> RemoteCursor:
        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": [_encode_arg(p) for p in params]}},
                {"type": "close"},
            ]
        }
        data = self._post(body)
        try:
            first = data["results"][0]
        except (KeyError, IndexError, TypeError):
            raise RemoteDBError("Unexpected response from the database service.") from None
        if first.get("type") == "error":
            message = (first.get("error") or {}).get("message", "unknown error")
            raise RemoteDBError(f"Database error: {message}")
        try:
            result = first["response"]["result"]
            cols = [c.get("name") for c in result.get("cols", [])]
            rows = [RemoteRow(cols, [_decode_value(c) for c in row]) for row in result.get("rows", [])]
            last = result.get("last_insert_rowid")
            return RemoteCursor(rows, int(result.get("affected_row_count") or 0), int(last) if last is not None else None)
        except (KeyError, TypeError, ValueError):
            raise RemoteDBError("Unexpected response from the database service.") from None

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...

    # --- transport
    def _post(self, body: dict) -> dict:
        try:
            resp = self.session.post(
                f"{self.url}/v2/pipeline", json=body, timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            )
        except requests.Timeout as exc:
            raise RemoteDBError("The database took too long to respond. Please try again.") from exc
        except requests.RequestException as exc:
            raise RemoteDBError("Could not reach the database service. Check the network and the database URL.") from exc
        if resp.status_code in (401, 403):
            raise RemoteDBError("Database authentication failed - check TURSO_AUTH_TOKEN.")
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = (resp.json() or {}).get("error", "")
            except ValueError:
                pass
            raise RemoteDBError(f"Database service returned HTTP {resp.status_code}. {detail}".strip())
        try:
            return resp.json()
        except ValueError as exc:
            raise RemoteDBError("The database service returned an unreadable response.") from exc
