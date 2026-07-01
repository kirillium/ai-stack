#!/usr/bin/env python3
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

DB_PATH = "/data/assistdata.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def print_rows(rows):
    if not rows:
        print("No rows")
        return
    for row in rows:
        print(dict(row))

def list_pending():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, text, remind_at, status, created_at, fired_at, meta
            FROM reminders
            WHERE status = 'pending'
            ORDER BY remind_at ASC, id ASC
        """)
        print_rows(cur.fetchall())

def list_all():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, text, remind_at, status, created_at, fired_at, meta
            FROM reminders
            ORDER BY id ASC
        """)
        print_rows(cur.fetchall())

def add_reminder(text, remind_at, meta=None):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reminders (text, remind_at, status, meta)
            VALUES (?, ?, 'pending', ?)
        """, (text, remind_at, json.dumps(meta, ensure_ascii=False) if meta else None))
        conn.commit()
        print({"added_id": cur.lastrowid, "text": text, "remind_at": remind_at})

def cancel_last():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, text, remind_at, status
            FROM reminders
            WHERE status = 'pending'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            print("No pending reminders to cancel")
            return

        cur.execute("""
            UPDATE reminders
            SET status = 'cancelled'
            WHERE id = ?
        """, (row["id"],))
        conn.commit()
        print({"cancelled_id": row["id"], "text": row["text"], "remind_at": row["remind_at"]})

def mark_fired(reminder_id):
    fired_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE reminders
            SET status = 'fired', fired_at = ?
            WHERE id = ?
        """, (fired_at, reminder_id))
        conn.commit()
        print({"marked_id": reminder_id, "fired_at": fired_at})

def parse_remind_at(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        raise SystemExit("remind_at must be ISO datetime, for example: 2026-07-01T13:00:00+03:00")

def main():
    parser = argparse.ArgumentParser(description="Reminder DB test CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    sub.add_parser("all")

    p_add = sub.add_parser("add")
    p_add.add_argument("text")
    p_add.add_argument("remind_at")
    p_add.add_argument("--meta", default=None, help="JSON string")

    sub.add_parser("cancel_last")

    p_fire = sub.add_parser("mark_fired")
    p_fire.add_argument("id", type=int)

    args = parser.parse_args()

    if args.cmd == "list":
        list_pending()
    elif args.cmd == "all":
        list_all()
    elif args.cmd == "add":
        meta = json.loads(args.meta) if args.meta else None
        add_reminder(args.text, parse_remind_at(args.remind_at), meta)
    elif args.cmd == "cancel_last":
        cancel_last()
    elif args.cmd == "mark_fired":
        mark_fired(args.id)

if __name__ == "__main__":
    main()
