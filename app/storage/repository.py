import json
from datetime import datetime, timedelta, timezone

from app.domain.models import SnapshotRecord, UnreadSnapshot
from app.storage.database import Database


_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    total_unread INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    notification_status TEXT NOT NULL,
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    notified_at TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_observed_at
    ON snapshots(observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_notification_status
    ON snapshots(notification_status);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SnapshotRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def initialize(self) -> None:
        await self._db.connection.executescript(_SCHEMA)
        await self._db.connection.commit()

    async def get_last(self) -> SnapshotRecord | None:
        cursor = await self._db.connection.execute(
            "SELECT * FROM snapshots ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        return self._row_to_record(row) if row else None

    async def create_snapshot(
        self,
        snapshot: UnreadSnapshot,
        notification_status: str,
    ) -> SnapshotRecord:
        payload_json = snapshot.model_dump_json()
        cursor = await self._db.connection.execute(
            """
            INSERT INTO snapshots (
                fingerprint,
                total_unread,
                payload_json,
                observed_at,
                notification_status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot.fingerprint,
                snapshot.total_unread,
                payload_json,
                snapshot.captured_at.isoformat(),
                notification_status,
            ),
        )
        await self._db.connection.commit()
        record_id = int(cursor.lastrowid)
        await cursor.close()
        return SnapshotRecord(
            id=record_id,
            fingerprint=snapshot.fingerprint,
            total_unread=snapshot.total_unread,
            payload_json=payload_json,
            observed_at=snapshot.captured_at,
            notification_status=notification_status,
            notification_attempts=0,
        )

    async def mark_sent(self, record_id: int) -> None:
        await self._db.connection.execute(
            """
            UPDATE snapshots
            SET notification_status = 'sent',
                notified_at = ?,
                notification_attempts = notification_attempts + 1,
                last_error = NULL
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), record_id),
        )
        await self._db.connection.commit()

    async def mark_failed(self, record_id: int, error: str) -> None:
        await self._db.connection.execute(
            """
            UPDATE snapshots
            SET notification_status = 'failed',
                notification_attempts = notification_attempts + 1,
                last_error = ?
            WHERE id = ?
            """,
            (error[:2000], record_id),
        )
        await self._db.connection.commit()

    async def list_pending(self, limit: int = 20) -> list[SnapshotRecord]:
        cursor = await self._db.connection.execute(
            """
            SELECT * FROM snapshots
            WHERE notification_status IN ('pending', 'failed')
              AND notification_attempts < 10
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_record(row) for row in rows]

    async def get_state(self, key: str) -> str | None:
        cursor = await self._db.connection.execute(
            "SELECT value FROM app_state WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return str(row["value"]) if row else None

    async def set_state(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.connection.execute(
            """
            INSERT INTO app_state(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        await self._db.connection.commit()

    async def alert_allowed(self, key: str, interval_seconds: int) -> bool:
        value = await self.get_state(key)
        if not value:
            return True
        try:
            last = datetime.fromisoformat(value)
        except ValueError:
            return True
        return datetime.now(timezone.utc) - last >= timedelta(seconds=interval_seconds)

    async def mark_alert_sent(self, key: str) -> None:
        await self.set_state(key, datetime.now(timezone.utc).isoformat())

    async def cleanup(self, retention_days: int) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        await self._db.connection.execute(
            "DELETE FROM snapshots WHERE observed_at < ?",
            (threshold.isoformat(),),
        )
        await self._db.connection.commit()

    @staticmethod
    def _row_to_record(row) -> SnapshotRecord:
        return SnapshotRecord(
            id=int(row["id"]),
            fingerprint=str(row["fingerprint"]),
            total_unread=int(row["total_unread"]),
            payload_json=str(row["payload_json"]),
            observed_at=datetime.fromisoformat(row["observed_at"]),
            notification_status=str(row["notification_status"]),
            notification_attempts=int(row["notification_attempts"]),
            notified_at=(
                datetime.fromisoformat(row["notified_at"])
                if row["notified_at"]
                else None
            ),
            last_error=str(row["last_error"]) if row["last_error"] else None,
        )
