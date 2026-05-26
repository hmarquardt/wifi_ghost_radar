from __future__ import annotations

import csv
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from .config import DEFAULT_SETTINGS
from .models import IncomingSample, ProcessedSample, utc_now_iso


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def connect(self) -> aiosqlite.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        return db

    @asynccontextmanager
    async def session(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await self.connect()
        try:
            yield db
        finally:
            await db.close()

    async def initialize(self) -> None:
        async with self.session() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    channel INTEGER NULL,
                    frequency_mhz INTEGER NULL,
                    bssid TEXT NULL,
                    client_mac TEXT NULL,
                    rssi REAL NULL,
                    bfi_variance REAL NOT NULL,
                    amplitude_delta REAL NULL,
                    phase_delta REAL NULL,
                    motion_score REAL NOT NULL,
                    status TEXT NOT NULL,
                    raw_json TEXT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON samples(timestamp);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT NULL,
                    peak_motion_score REAL NOT NULL,
                    avg_motion_score REAL NOT NULL,
                    status TEXT NOT NULL,
                    label TEXT NULL,
                    notes TEXT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_timestamp);
                CREATE TABLE IF NOT EXISTS baselines (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    mean_bfi_variance REAL NOT NULL,
                    std_bfi_variance REAL NOT NULL,
                    mean_motion_score REAL NOT NULL,
                    std_motion_score REAL NOT NULL,
                    notes TEXT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, value),
                )
            await db.commit()

    async def get_settings(self) -> dict[str, str]:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT key, value FROM settings ORDER BY key")
        return {row["key"]: row["value"] for row in rows}

    async def update_settings(self, settings: dict[str, Any]) -> dict[str, str]:
        async with self.session() as db:
            for key, value in settings.items():
                await db.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value)),
                )
            await db.commit()
        return await self.get_settings()

    async def insert_sample(self, sample: ProcessedSample) -> int:
        async with self.session() as db:
            cur = await db.execute(
                """
                INSERT INTO samples(timestamp, source, channel, frequency_mhz, bssid, client_mac, rssi,
                bfi_variance, amplitude_delta, phase_delta, motion_score, status, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample.timestamp,
                    sample.source,
                    sample.channel,
                    sample.frequency_mhz,
                    sample.bssid,
                    sample.client_mac,
                    sample.rssi,
                    sample.bfi_variance,
                    sample.amplitude_delta,
                    sample.phase_delta,
                    sample.motion_score,
                    sample.status,
                    json.dumps(sample.raw_json) if sample.raw_json is not None else None,
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def latest_sample(self) -> dict[str, Any] | None:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT * FROM samples ORDER BY id DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    async def get_samples(self, limit: int = 500) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 5000))
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT * FROM samples ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]

    async def get_events(self) -> list[dict[str, Any]]:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT * FROM events ORDER BY id DESC LIMIT 200")
        return [dict(row) for row in rows]

    async def get_baselines(self) -> list[dict[str, Any]]:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT * FROM baselines ORDER BY id DESC LIMIT 50")
        return [dict(row) for row in rows]

    async def latest_baseline(self) -> dict[str, Any] | None:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT * FROM baselines ORDER BY id DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    async def create_baseline_from_recent(self, duration_seconds: int, notes: str | None) -> dict[str, Any]:
        async with self.session() as db:
            rows = await db.execute_fetchall(
                """
                SELECT source, bfi_variance, motion_score FROM samples
                WHERE timestamp >= datetime('now', ?)
                ORDER BY id DESC
                """,
                (f"-{duration_seconds} seconds",),
            )
            if not rows:
                raise ValueError("No recent samples are available for baseline creation.")
            bfi = [float(row["bfi_variance"]) for row in rows]
            scores = [float(row["motion_score"]) for row in rows]
            mean_bfi = sum(bfi) / len(bfi)
            mean_score = sum(scores) / len(scores)
            std_bfi = (sum((x - mean_bfi) ** 2 for x in bfi) / len(bfi)) ** 0.5
            std_score = (sum((x - mean_score) ** 2 for x in scores) / len(scores)) ** 0.5
            source = rows[0]["source"] or "mixed"
            cur = await db.execute(
                """
                INSERT INTO baselines(created_at, source, duration_seconds, mean_bfi_variance,
                std_bfi_variance, mean_motion_score, std_motion_score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (utc_now_iso(), source, duration_seconds, mean_bfi, std_bfi, mean_score, std_score, notes),
            )
            await db.commit()
            baseline_id = int(cur.lastrowid)
            result = await db.execute_fetchall("SELECT * FROM baselines WHERE id = ?", (baseline_id,))
        return dict(result[0])

    async def open_event(self, sample: ProcessedSample) -> int:
        async with self.session() as db:
            cur = await db.execute(
                """
                INSERT INTO events(start_timestamp, peak_motion_score, avg_motion_score, status, label)
                VALUES (?, ?, ?, 'open', 'unknown')
                """,
                (sample.timestamp, sample.motion_score, sample.motion_score),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def update_event(self, event_id: int, peak: float, average: float) -> None:
        async with self.session() as db:
            await db.execute(
                "UPDATE events SET peak_motion_score = ?, avg_motion_score = ? WHERE id = ?",
                (peak, average, event_id),
            )
            await db.commit()

    async def close_event(self, event_id: int, timestamp: str, peak: float, average: float) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE events SET end_timestamp = ?, peak_motion_score = ?, avg_motion_score = ?,
                status = 'closed' WHERE id = ?
                """,
                (timestamp, peak, average, event_id),
            )
            await db.commit()

    async def label_event(self, event_id: int, label: str, notes: str | None) -> dict[str, Any]:
        async with self.session() as db:
            rows = await db.execute_fetchall("SELECT id FROM events WHERE id = ?", (event_id,))
            if not rows:
                raise ValueError(f"Event {event_id} does not exist.")
            await db.execute("UPDATE events SET label = ?, notes = ? WHERE id = ?", (label, notes, event_id))
            await db.commit()
            updated = await db.execute_fetchall("SELECT * FROM events WHERE id = ?", (event_id,))
        return dict(updated[0])

    async def export_csv(self, table: str) -> str:
        if table not in {"samples", "events"}:
            raise ValueError("Unsupported export table.")
        async with self.session() as db:
            rows = await db.execute_fetchall(f"SELECT * FROM {table} ORDER BY id DESC")
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
        return output.getvalue()

    async def recent_export(self) -> dict[str, Any]:
        return {
            "generated_at": utc_now_iso(),
            "status": await self.latest_sample(),
            "samples": await self.get_samples(500),
            "events": await self.get_events(),
            "baselines": await self.get_baselines(),
            "settings": await self.get_settings(),
        }
