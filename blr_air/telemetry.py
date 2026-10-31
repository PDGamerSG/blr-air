import hashlib
import hmac
import sqlite3
from pathlib import Path


class Usage:
    """Aggregate requests and pseudonymous senders; never store chat content."""

    def __init__(self, path: Path, salt: str):
        self.path = path
        self.salt = salt.encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS senders (id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS counts (name TEXT PRIMARY KEY, value INTEGER)")
        path.chmod(0o600)

    def track(self, sender: str, *, success: bool, channel: str):
        digest = hmac.new(self.salt, sender.encode(), hashlib.sha256).hexdigest()
        names = (
            "queries",
            "successful_queries" if success else "failed_queries",
            "chat_queries" if channel == "chat" else "typed_queries",
        )
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO senders VALUES (?)", (digest,))
            for name in names:
                db.execute(
                    "INSERT INTO counts VALUES (?, 1) "
                    "ON CONFLICT(name) DO UPDATE SET value=value+1",
                    (name,),
                )

    def stats(self):
        with sqlite3.connect(self.path) as db:
            counts = dict(db.execute("SELECT name, value FROM counts"))
            senders = db.execute("SELECT COUNT(*) FROM senders").fetchone()[0]
        return {
            **{
                key: counts.get(key, 0)
                for key in (
                    "queries",
                    "successful_queries",
                    "failed_queries",
                    "chat_queries",
                    "typed_queries",
                )
            },
            "unique_senders": senders,
        }
