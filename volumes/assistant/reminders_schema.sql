PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    fired_at TEXT,
    meta TEXT
);

CREATE INDEX IF NOT EXISTS idx_reminders_status_remind_at
    ON reminders(status, remind_at);

CREATE INDEX IF NOT EXISTS idx_reminders_status_created_at
    ON reminders(status, created_at);
