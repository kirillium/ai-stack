PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,          -- ISO8601 UTC
    created_at TEXT DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending', -- pending / fired / cancelled
    fired_at TEXT,
    meta TEXT                         -- JSON string for extensibility
);

CREATE INDEX IF NOT EXISTS idx_remind_at_status ON reminders(remind_at, status);
