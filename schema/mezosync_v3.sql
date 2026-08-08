-- mezosync v3 — СХЕМА КОНТУРА. СОБРАНА ИЗ ЖИВОЙ БАЗЫ, НЕ НАПИСАНА РУКОЙ.
--
-- Повод (замер 2026-08-08 22:39 UTC): рукописная v2 отстала от живой базы на ПЯТЬ сосудов,
-- и заметить это было нечем — рукописная схема есть вторая копия правды, а вторая копия
-- расходится молча. Контур, собранный из v2 в этот день, не получал НИЧЕГО из сделанного
-- за смену и выглядел при этом исправным.
--
-- ⚖️ ПОЭТОМУ: этот файл ГЕНЕРИРУЕТСЯ (vnext/tools/gen-schema.py) из структуры живой базы.
--    Править его руками — значит завести расхождение заново.
--
-- ЧТО ДОБАВИЛОСЬ ПРОТИВ v2 (всё — работы 2026-08-07/08):
--   rules.basis / authorized / source_ref / expiry_kind / expiry_cond
--                              основание правила и УСЛОВИЕ ЕГО ОТМЕНЫ полями, а не прозой
--   phoenix.confirmed_at       возраст ВЗГЛЯДА отдельно от возраста ТЕКСТА
--   message_addressee          имена адресатов: обращение отдельно от копии
--   role_rights (+ витрина)    права роли полями; разовое право ТРАТИТСЯ и это видно
--   sync_backoff               разгон сна между синками — одно место на весь контур
--   cursor_segments · message_thread · message_task · roles · backlog_* и прочее из v3-наката
--
-- собрано: index 13 · table 27 · view 4

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    actor_role  TEXT NOT NULL,
    action      TEXT NOT NULL,       -- 'update_rule' | 'save_phoenix' | 'update_track' | ...
    target      TEXT NOT NULL,       -- что именно изменено
    diff_md     TEXT                 -- краткое описание изменения
);

CREATE TABLE IF NOT EXISTS backlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, title TEXT NOT NULL,
    body_md TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', priority TEXT NOT NULL DEFAULT 'normal',
    tags TEXT DEFAULT '[]', parent_id INTEGER, parent_track TEXT, rank INTEGER, blocked_reason TEXT,
    created_by TEXT NOT NULL DEFAULT 'coord', created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')), done_when TEXT);

CREATE TABLE IF NOT EXISTS backlog_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, backlog_id INTEGER NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')),
    actor_role TEXT NOT NULL, event_type TEXT NOT NULL, from_status TEXT, to_status TEXT, body_md TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS backlog_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, backlog_id INTEGER NOT NULL, title TEXT NOT NULL, method TEXT NOT NULL,
    spec_md TEXT DEFAULT '', command TEXT, expected TEXT, status TEXT NOT NULL DEFAULT 'pending',
    last_run_at TEXT, last_result_md TEXT, created_by TEXT NOT NULL DEFAULT 'coord');

CREATE TABLE IF NOT EXISTS bridge_reviewed (  file_name TEXT NOT NULL,  role      TEXT NOT NULL,  note_id   INTEGER REFERENCES messages(id),  at        TEXT NOT NULL DEFAULT (datetime('now')),  PRIMARY KEY (file_name, role));

CREATE TABLE IF NOT EXISTS broadcast_acks (
            message_id INTEGER NOT NULL,
            role       TEXT NOT NULL,
            acked_at   TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (message_id, role)
        );

CREATE TABLE IF NOT EXISTS cross_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_group    TEXT NOT NULL,
    target_group    TEXT NOT NULL,
    target_db_path  TEXT NOT NULL,
    description     TEXT,
    last_sync_at    TEXT,
    UNIQUE(source_group, target_group)
);

CREATE TABLE IF NOT EXISTS cursor_segments (
                id          INTEGER PRIMARY KEY,
                role        TEXT NOT NULL REFERENCES roles(role) ON DELETE CASCADE,
                from_id     INTEGER NOT NULL,
                to_id       INTEGER NOT NULL,
                kind        TEXT NOT NULL CHECK (kind IN ('read','declared','born')),
                basis       TEXT,
                authorized  TEXT,
                note_id     INTEGER,
                at          TEXT NOT NULL DEFAULT (datetime('now')),
                CHECK (to_id >= from_id),
                CHECK (kind = 'read' OR (basis IS NOT NULL AND authorized IS NOT NULL))
            );

CREATE TABLE IF NOT EXISTS invariants (
    code            TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    established_at  TEXT NOT NULL DEFAULT (datetime('now')),
    established_by  TEXT NOT NULL DEFAULT 'coord'
);

CREATE TABLE IF NOT EXISTS message_addressee (
    message_id INTEGER NOT NULL REFERENCES messages(id),
    role       TEXT    NOT NULL,
    kind       TEXT    NOT NULL CHECK (kind IN ('to','cc')),
    linked_by  TEXT    NOT NULL DEFAULT 'field'
                       CHECK (linked_by IN ('field','backfill')),
    PRIMARY KEY (message_id, role, kind)
);

CREATE TABLE IF NOT EXISTS message_task (
                message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                task_id     INTEGER NOT NULL REFERENCES backlog(id)  ON DELETE CASCADE,
                linked_by   TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
                PRIMARY KEY (message_id, task_id)
            );

CREATE TABLE IF NOT EXISTS message_thread (
                message_id  INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                reply_to    INTEGER REFERENCES messages(id),
                thread_id   INTEGER REFERENCES messages(id),
                kind        TEXT CHECK (kind IN ('question','answer','handover','status','decision')),
                linked_by   TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
                CHECK (reply_to  IS NULL OR reply_to  <> message_id),
                CHECK (thread_id IS NULL OR thread_id <> message_id),
                CHECK (kind <> 'answer' OR reply_to IS NOT NULL)
            );

CREATE TABLE IF NOT EXISTS "messages" (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    writer_role TEXT NOT NULL,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    body_md     TEXT NOT NULL,
    tags        TEXT DEFAULT '[]',  -- JSON array: ["F-24","TRACK-X"]
    priority    TEXT DEFAULT 'normal'  -- 'normal' | 'high' | 'critical'
, resolved INTEGER DEFAULT 0, broadcast INTEGER NOT NULL DEFAULT 0, addressed_by TEXT NOT NULL DEFAULT 'unset' CHECK (addressed_by IN ('field','backfill','unset')));

CREATE TABLE IF NOT EXISTS messages_history (
                id          INTEGER PRIMARY KEY,
                writer_role TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                body_md     TEXT NOT NULL,
                tags        TEXT DEFAULT '[]',
                priority    TEXT DEFAULT 'normal',
                resolved    INTEGER DEFAULT 0
            );

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phoenix (
    role        TEXT NOT NULL,
    section     TEXT NOT NULL,       -- 'identity' | 'state' | 'plan' | 'history'
    body        TEXT NOT NULL,
    saved_at    TEXT NOT NULL DEFAULT (datetime('now')), confirmed_at TEXT,
    PRIMARY KEY (role, section)
);

CREATE TABLE IF NOT EXISTS read_batches (  token     TEXT PRIMARY KEY,  role      TEXT NOT NULL,  last_id   INTEGER NOT NULL,  issued_at TEXT NOT NULL DEFAULT (datetime('now')), shown_max INTEGER, acked_at TEXT);

CREATE TABLE IF NOT EXISTS read_cursors (
    reader_role TEXT PRIMARY KEY,
    last_read_id INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS role_rights (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    role          TEXT NOT NULL,
    right_key     TEXT NOT NULL,
    scope         TEXT,
    kind          TEXT NOT NULL CHECK (kind IN ('standing','once')),
    authorized_by TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    source_ref    TEXT NOT NULL,
    spent_at      TEXT,
    revoked_at    TEXT,
    revoked_why   TEXT,
    declared_by   TEXT NOT NULL DEFAULT 'field' CHECK (declared_by IN ('field','backfill')),
    note          TEXT
);

CREATE TABLE IF NOT EXISTS role_status (  role       TEXT PRIMARY KEY,  status     TEXT NOT NULL,  updated_at TEXT NOT NULL DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS roles (
                role        TEXT PRIMARY KEY,
                -- 'unknown' — ДЕФОЛТ ПРИ ПЕРЕНОСЕ: след в данных не говорит о статусе.
                -- Заполняется словом, а не выводом из наличия нот.
                status      TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (status IN ('unknown', 'active', 'dormant', 'closed')),
                seen_in     TEXT,
                in_roster   INTEGER,      -- 1 — есть в живом реестре · 0 — нет · NULL — реестр не прочитан
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key    TEXT NOT NULL UNIQUE,
    body        TEXT NOT NULL,
    locked_by   TEXT NOT NULL DEFAULT 'coord',  -- 'owner' | 'coord'
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
, basis TEXT, authorized TEXT, source_ref TEXT, expiry_kind TEXT, expiry_cond TEXT);

CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
            note        TEXT
        , fingerprint TEXT);

CREATE TABLE IF NOT EXISTS stats_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL DEFAULT (datetime('now')),
            snapshot_json TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS sync_backoff (
                        role TEXT PRIMARY KEY,
                        sleep_sec INTEGER NOT NULL,
                        quiet_streak INTEGER NOT NULL DEFAULT 0,
                        last_seen_id INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT);

CREATE TABLE IF NOT EXISTS templates (
    role_type       TEXT PRIMARY KEY,  -- 'coord' | 'core' | 'stud' | ...
    display_name    TEXT NOT NULL,
    launcher_prompt TEXT NOT NULL,
    capabilities    TEXT DEFAULT '[]',   -- JSON array
    tools_needed    TEXT DEFAULT '[]',   -- JSON array
    version         INTEGER NOT NULL DEFAULT 1,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'paused' | 'done'
    plan_md         TEXT,
    owner_decision  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_addressee_msg  ON message_addressee(message_id);

CREATE INDEX IF NOT EXISTS idx_addressee_role ON message_addressee(role, kind);

CREATE INDEX IF NOT EXISTS idx_backlog_events_bid ON backlog_events(backlog_id);

CREATE INDEX IF NOT EXISTS idx_backlog_role ON backlog(role);

CREATE INDEX IF NOT EXISTS idx_backlog_status ON backlog(status);

CREATE INDEX IF NOT EXISTS idx_backlog_tests_bid ON backlog_tests(backlog_id);

CREATE INDEX IF NOT EXISTS idx_cursor_seg ON cursor_segments (role, from_id, to_id);

CREATE INDEX IF NOT EXISTS idx_message_task_task ON message_task (task_id, message_id);

CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);

CREATE INDEX IF NOT EXISTS idx_messages_writer ON messages(writer_role);

CREATE INDEX IF NOT EXISTS idx_thread_reply ON message_thread (reply_to);

CREATE INDEX IF NOT EXISTS idx_thread_root  ON message_thread (thread_id);

CREATE INDEX IF NOT EXISTS ix_role_rights_role ON role_rights (role);

CREATE VIEW IF NOT EXISTS backlog_without_criterion AS
            SELECT id, role, title, priority, created_at
            FROM backlog
            WHERE status = 'open'
              AND (done_when IS NULL
                   OR TRIM(done_when, ' ' || char(9) || char(10) || char(13)) = '');

CREATE VIEW IF NOT EXISTS messages_all AS
    SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, 'live'    AS source FROM messages
    UNION ALL
    SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, 'history' AS source FROM messages_history;

CREATE VIEW IF NOT EXISTS role_rights_live AS
    SELECT * FROM role_rights
     WHERE revoked_at IS NULL
       AND NOT (kind = 'once' AND spent_at IS NOT NULL);

CREATE VIEW IF NOT EXISTS schema_version AS
            SELECT
                (SELECT version FROM schema_migrations WHERE version GLOB 'v[0-9]*'
                  ORDER BY rowid DESC LIMIT 1)                                    AS version,
                (SELECT COUNT(*) FROM schema_migrations WHERE version NOT GLOB 'v[0-9]*') AS steps_total,
                (SELECT COUNT(*) FROM schema_migrations m
                  WHERE m.version NOT GLOB 'v[0-9]*'
                    AND m.rowid > COALESCE((SELECT rowid FROM schema_migrations
                                             WHERE version GLOB 'v[0-9]*'
                                             ORDER BY rowid DESC LIMIT 1), 0))    AS steps_after_milestone;
