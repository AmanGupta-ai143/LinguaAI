"""A stand-in for the Turso HTTP API backed by an in-memory SQLite database.

It speaks the documented ``POST /v2/pipeline`` protocol, so tests can run the entire
``DatabaseManager`` through ``RemoteConnection`` without network access.
"""
import sqlite3


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload

    def json(self):
        return self._payload


def _decode(arg):
    kind = arg["type"]
    if kind == "null":
        return None
    if kind == "integer":
        return int(arg["value"])
    if kind == "float":
        return float(arg["value"])
    return arg["value"]


def _encode(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


class FakeTurso:
    def __init__(self, token="secret"):
        self.token = token
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.requests = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.requests.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if (headers or {}).get("Authorization") != f"Bearer {self.token}":
            return FakeResponse(401, {"error": "unauthorized"})
        results = []
        for req in json["requests"]:
            if req["type"] != "execute":
                results.append({"type": "ok", "response": {"type": "close"}})
                continue
            stmt = req["stmt"]
            try:
                cur = self.conn.execute(stmt["sql"], [_decode(a) for a in stmt.get("args", [])])
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                self.conn.commit()
                is_insert = stmt["sql"].lstrip().upper().startswith("INSERT")
                results.append({"type": "ok", "response": {"type": "execute", "result": {
                    "cols": [{"name": c, "decltype": None} for c in cols],
                    "rows": [[_encode(v) for v in row] for row in rows],
                    "affected_row_count": max(cur.rowcount, 0),
                    "last_insert_rowid": str(cur.lastrowid) if is_insert else None,
                }}})
            except sqlite3.Error as exc:
                results.append({"type": "error", "error": {"message": str(exc)}})
        return FakeResponse(200, {"baton": None, "base_url": None, "results": results})
