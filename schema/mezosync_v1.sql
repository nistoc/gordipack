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
-- META (версия схемы, имя группы)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1.0');
INSERT OR IGNORE INTO meta (key, value) VALUES ('group_name', 'unnamed');
INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', datetime('now'));
