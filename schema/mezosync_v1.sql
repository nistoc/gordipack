-- Gordi Mezosync Schema v1.0
-- Создаёт структуру коммуникационной БД для группы агентов.
-- Использование: sqlite3 mezosync.db < mezosync_v1.sql

PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

----------------------------------------------------------------------
-- ПРАВИЛА (общие для всей группы)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key    TEXT NOT NULL UNIQUE,
    body        TEXT NOT NULL,
    locked_by   TEXT NOT NULL DEFAULT 'coord',  -- 'owner' | 'coord'
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

----------------------------------------------------------------------
-- СООБЩЕНИЯ (append-only лента, замена sync.*.md)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    writer_role TEXT NOT NULL,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    body_md     TEXT NOT NULL,
    tags        TEXT DEFAULT '[]',  -- JSON array: ["F-24","TRACK-X"]
    priority    TEXT DEFAULT 'normal'  -- 'normal' | 'high' | 'critical'
);

CREATE INDEX IF NOT EXISTS idx_messages_writer ON messages(writer_role);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);

----------------------------------------------------------------------
-- КУРСОРЫ ЧТЕНИЯ (каждый агент помнит, до какого id дочитал)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS read_cursors (
    reader_role TEXT PRIMARY KEY,
    last_read_id INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

----------------------------------------------------------------------
-- PHOENIX (слепки состояния ролей для ребёрса)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS phoenix (
    role        TEXT NOT NULL,
    section     TEXT NOT NULL,       -- 'identity' | 'state' | 'plan' | 'history'
    body        TEXT NOT NULL,
    saved_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (role, section)
);

----------------------------------------------------------------------
-- ШАБЛОНЫ РОЛЕЙ (launcher-промпты и описания)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS templates (
    role_type       TEXT PRIMARY KEY,  -- 'coord' | 'core' | 'stud' | ...
    display_name    TEXT NOT NULL,
    launcher_prompt TEXT NOT NULL,
    capabilities    TEXT DEFAULT '[]',   -- JSON array
    tools_needed    TEXT DEFAULT '[]',   -- JSON array
    version         INTEGER NOT NULL DEFAULT 1,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

----------------------------------------------------------------------
-- ТРЕКИ / ЦЕЛИ
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tracks (
    track_id        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'paused' | 'done'
    plan_md         TEXT,
    owner_decision  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

----------------------------------------------------------------------
-- ИНВАРИАНТЫ
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invariants (
    code            TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    established_at  TEXT NOT NULL DEFAULT (datetime('now')),
    established_by  TEXT NOT NULL DEFAULT 'coord'
);

----------------------------------------------------------------------
-- КРОСС-ССЫЛКИ (для связи между независимыми группами)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cross_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_group    TEXT NOT NULL,
    target_group    TEXT NOT NULL,
    target_db_path  TEXT NOT NULL,
    description     TEXT,
    last_sync_at    TEXT,
    UNIQUE(source_group, target_group)
);

----------------------------------------------------------------------
-- АУДИТ-ЛОГ (кто что менял в мутабельных таблицах)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    actor_role  TEXT NOT NULL,
    action      TEXT NOT NULL,       -- 'update_rule' | 'save_phoenix' | 'update_track' | ...
    target      TEXT NOT NULL,       -- что именно изменено
    diff_md     TEXT                 -- краткое описание изменения
);

----------------------------------------------------------------------
-- BACKLOG (durable per-role задачи; переживают ребёрс агента)
-- role = роль-владелец ('CORE'…) или 'SHARED' для общих задач.
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backlog (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    role           TEXT NOT NULL,
    title          TEXT NOT NULL,
    body_md        TEXT DEFAULT '',                 -- rich markdown
    status         TEXT NOT NULL DEFAULT 'open',    -- open|in_progress|blocked|in_review|done|dropped
    priority       TEXT NOT NULL DEFAULT 'normal',  -- low|normal|high|critical
    tags           TEXT DEFAULT '[]',               -- JSON array
    parent_id      INTEGER,                         -- подзадача/эпик
    parent_track   TEXT,                            -- tracks.track_id
    rank           INTEGER,                         -- ручной порядок
    blocked_reason TEXT,
    created_by     TEXT NOT NULL DEFAULT 'coord',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_backlog_role ON backlog(role);
CREATE INDEX IF NOT EXISTS idx_backlog_status ON backlog(status);

-- История задачи (append-only) — трейл переживает любой перезапуск
CREATE TABLE IF NOT EXISTS backlog_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    backlog_id  INTEGER NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now')),   -- UTC
    actor_role  TEXT NOT NULL,
    event_type  TEXT NOT NULL,   -- created|status_change|comment|edited|test_added|test_result
    from_status TEXT,
    to_status   TEXT,
    body_md     TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_backlog_events_bid ON backlog_events(backlog_id);

-- Приёмочные тесты задачи (4 метода: agent|script|code|user_ui)
CREATE TABLE IF NOT EXISTS backlog_tests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    backlog_id     INTEGER NOT NULL,
    title          TEXT NOT NULL,
    method         TEXT NOT NULL,   -- agent|script|code|user_ui
    spec_md        TEXT DEFAULT '',
    command        TEXT,            -- для script|code
    expected       TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',  -- pending|passing|failing|skipped
    last_run_at    TEXT,
    last_result_md TEXT,
    created_by     TEXT NOT NULL DEFAULT 'coord'
);
CREATE INDEX IF NOT EXISTS idx_backlog_tests_bid ON backlog_tests(backlog_id);

----------------------------------------------------------------------
-- BROADCAST-ACK (общий канал: кто подтвердил объявление-CTA)
-- Broadcast = сообщение с тегом "ALL" в messages; CTA — ещё и тег "CTA".
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS broadcast_acks (
    message_id  INTEGER NOT NULL,
    role        TEXT NOT NULL,
    acked_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (message_id, role)
);

----------------------------------------------------------------------
-- META (версия схемы, имя группы)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1.0');
INSERT OR IGNORE INTO meta (key, value) VALUES ('group_name', 'unnamed');
INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', datetime('now'));
