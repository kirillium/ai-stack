import sqlite3
import threading
import time
import json
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict
import dateparser
import os

# Helpers
def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
        # Выполняем schema script над выбранным файлом БД
        conn = self._get_conn()
        cur = conn.cursor()
        with open(self.schema_path, "r", encoding="utf-8") as f:
            script = f.read()
        cur.executescript(script)
        conn.commit()
        conn.close()

    # CRUD
    def add_reminder(self, text: str, remind_at_iso: str, meta: Optional[Dict]=None) -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reminders (text, remind_at, meta) VALUES (?, ?, ?)",
            (text, remind_at_iso, json.dumps(meta) if meta else None)
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid

    def get_pending_before(self, iso_time: str) -> List[Dict]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND remind_at <= ? ORDER BY remind_at ASC",
            (iso_time,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def mark_fired(self, reminder_id: int):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE reminders SET status='fired', fired_at = ? WHERE id = ?",
            (now_iso(), reminder_id)
        )
        conn.commit()
        conn.close()

    def cancel_last_pending(self) -> Optional[Dict]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reminders WHERE status='pending' ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        rid = row['id']
        cur.execute("UPDATE reminders SET status='cancelled' WHERE id = ?", (rid,))
        conn.commit()
        result = dict(row)
        conn.close()
        return result

    def list_pending(self, limit: int = 50) -> List[Dict]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE status='pending' ORDER BY remind_at ASC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_by_id(self, rid: int) -> Optional[Dict]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE id = ?", (rid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

class ReminderParser:
    def __init__(self, tz: str = "UTC", dateparser_settings: dict = None):
        self.tz = tz
        settings = {"PREFER_DATES_FROM": "future", "TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True}
        if dateparser_settings:
            settings.update(dateparser_settings)
        self.settings = settings

    def parse_datetime(self, text: str) -> Tuple[Optional[datetime], float]:
        dt = dateparser.parse(text, settings=self.settings)
        if not dt:
            return None, 0.0
        low = text.lower()
        confidence = 0.6
        if any(k in low for k in ["в ", "в:", "завтра", "через", "сегодня", "утром", "вечером", "ночью"]):
            confidence = 0.9
        return dt, confidence

class RemindersService:
    def __init__(self, db_path: str, check_interval_seconds: int = 30, tz: str = "UTC", dateparser_settings: dict = None, on_fire_callback=None, schema_path: Optional[str] = None):
        self.db = RemindersDB(db_path, schema_path=schema_path)
        self.parser = ReminderParser(tz, dateparser_settings)
        self.interval = check_interval_seconds
        self._running = False
        self._thread = None
        self.on_fire_callback = on_fire_callback

    # API
    def add(self, text: str, remind_at: datetime = None, meta: dict = None) -> int:
        if remind_at is None:
            raise ValueError("remind_at required")
        iso = to_iso(remind_at)
        return self.db.add_reminder(text, iso, meta)

    def add_from_text(self, text: str) -> Tuple[Optional[int], str]:
        dt, conf = self.parser.parse_datetime(text)
        if not dt:
            return None, "no_time"
        rid = self.add(text, dt)
        return rid, to_iso(dt)

    def cancel_last(self) -> Optional[Dict]:
        return self.db.cancel_last_pending()

    def list_pending(self, limit: int = 50) -> List[Dict]:
        return self.db.list_pending(limit)

    # Scheduler loop
    def _loop(self):
        self._running = True
        while self._running:
            try:
                now = now_iso()
                due = self.db.get_pending_before(now)
                for r in due:
                    try:
                        self.db.mark_fired(r['id'])
                        if self.on_fire_callback:
                            self.on_fire_callback(r)
                    except Exception as e:
                        print("Error firing reminder:", e)
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
