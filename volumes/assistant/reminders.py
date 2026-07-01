import sqlite3
import threading
import time
import json
import os
from datetime import datetime
from typing import Optional, Tuple, List, Dict

import dateparser


def now_local() -> datetime:
    return datetime.now()


def fmt_local(dt: datetime) -> str:
    return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def parse_any_datetime(value: str) -> datetime:
    if not value:
        raise ValueError("empty datetime value")

    dt = dateparser.parse(value)
    if dt is None:
        raise ValueError(f"cannot parse datetime: {value}")

    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)

    return dt.replace(microsecond=0)


class RemindersDB:
    def __init__(self, db_path: str, schema_path: Optional[str] = None):
        self.db_path = db_path
        self.schema_path = schema_path or os.path.join(os.path.dirname(__file__), "reminders_schema.sql")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._ensure_schema()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._get_conn() as conn:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

    def add_reminder(self, text: str, remind_at_local: str, meta: Optional[Dict] = None) -> int:
        created_at_local = fmt_local(now_local())
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO reminders (text, remind_at, created_at, status, fired_at, meta)
                VALUES (?, ?, ?, 'pending', NULL, ?)
                """,
                (text, remind_at_local, created_at_local, json.dumps(meta, ensure_ascii=False) if meta else None),
            )
            return cur.lastrowid

    def list_all(self) -> List[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, text, remind_at, status, created_at, fired_at, meta
                FROM reminders
                ORDER BY id ASC
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def list_pending(self, limit: int = 100) -> List[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, text, remind_at, status, created_at, fired_at, meta
                FROM reminders
                WHERE status = 'pending'
                ORDER BY remind_at ASC, id ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_due(self, now_local_str: str) -> List[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, text, remind_at, status, created_at, fired_at, meta
                FROM reminders
                WHERE status = 'pending' AND remind_at <= ?
                ORDER BY remind_at ASC, id ASC
                """,
                (now_local_str,),
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_fired(self, reminder_id: int) -> bool:
        fired_at_local = fmt_local(now_local())
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE reminders
                SET status = 'fired', fired_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (fired_at_local, reminder_id),
            )
            return cur.rowcount > 0

    def cancel_last_pending(self) -> Optional[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, text, remind_at, status, created_at, fired_at, meta
                FROM reminders
                WHERE status = 'pending'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                """
                UPDATE reminders
                SET status = 'cancelled'
                WHERE id = ? AND status = 'pending'
                """,
                (row["id"],),
            )
            return dict(row) if cur.rowcount > 0 else None

    def get_by_id(self, reminder_id: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, text, remind_at, status, created_at, fired_at, meta
                FROM reminders
                WHERE id = ?
                """,
                (reminder_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


class RemindersService:
    def __init__(self, db_path: str, check_interval_seconds: int = 30, on_fire_callback=None, schema_path: Optional[str] = None):
        self.db = RemindersDB(db_path, schema_path=schema_path)
        self.interval = check_interval_seconds
        self.on_fire_callback = on_fire_callback
        self._running = False
        self._thread = None

    def add(self, text: str, remind_at, meta: dict = None) -> int:
        if isinstance(remind_at, str):
            remind_at = parse_any_datetime(remind_at)
        elif isinstance(remind_at, datetime):
            if remind_at.tzinfo is not None:
                remind_at = remind_at.astimezone().replace(tzinfo=None)
        else:
            raise TypeError("remind_at must be str or datetime")

        return self.db.add_reminder(text, fmt_local(remind_at), meta)

    def add_from_text(self, text: str) -> Tuple[Optional[int], str]:
        dt = dateparser.parse(text)
        if dt is None:
            return None, "no_time"

        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)

        rid = self.add(text, dt)
        return rid, fmt_local(dt)

    def cancel_last(self) -> Optional[Dict]:
        return self.db.cancel_last_pending()

    def list_pending(self, limit: int = 100) -> List[Dict]:
        return self.db.list_pending(limit)

    def list_all(self) -> List[Dict]:
        return self.db.list_all()

    def mark_fired(self, reminder_id: int) -> bool:
        return self.db.mark_fired(reminder_id)

    def _loop(self):
        self._running = True
        while self._running:
            try:
                now_str = fmt_local(now_local())
                due = self.db.get_due(now_str)
                for r in due:
                    if self.db.mark_fired(r["id"]):
                        if self.on_fire_callback:
                            self.on_fire_callback(r)
                time.sleep(self.interval)
            except Exception as e:
                print("Reminders loop error:", e)
                time.sleep(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
