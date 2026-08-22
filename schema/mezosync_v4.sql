-- mezosync v4 — СХЕМА КОНТУРА. СОБРАНА ИЗ ЖИВОЙ БАЗЫ, НЕ НАПИСАНА РУКОЙ.
--
-- ⚖️ Этот файл ГЕНЕРИРУЕТСЯ (vnext/tools/gen-schema.py) из структуры живой базы;
--    номер версии взят из её журнала шагов (витрина schema_version) в момент сборки.
--    Править файл руками — значит завести расхождение заново: рукописная v2 в своё
--    время отстала от живой базы на пять сосудов, и заметить это было нечем.
-- ⚠️ Если сверх рубежа есть шаги (steps_after_milestone > 0), сборка честно скажет
--    об этом здесь: схема тогда НОВЕЕ объявленной версии.
-- Что входит в версию — спрашивай журнал: SELECT * FROM schema_migrations.
--
-- 🔴 ВНИМАНИЕ: сверх рубежа 3 шагов — схема НОВЕЕ объявленной версии.
--
-- собрано: index 17 · table 29 · view 6

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

CREATE TABLE IF NOT EXISTS role_skill (
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL
                CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),
    -- ЧТО умеет: короткой строкой, словами предмета, а не именем инструмента.
    -- «читать графы .rcc» — умение; «уметь rcc-graph.py» — имя, которое переживёт предмет.
    skill       TEXT NOT NULL CHECK (LENGTH(TRIM(skill)) BETWEEN 3 AND 200),
    -- ЧЕМ подтверждено. NOT NULL намеренно: см. шапку. Форма свободная, но это ССЫЛКА
    -- на наблюдаемое — «записка #3698», «карточка #204», коммит, слово владельца с часом.
    evidence    TEXT NOT NULL CHECK (LENGTH(TRIM(evidence)) >= 3),
    -- КОГДА в последний раз убедились (UTC). Не час записи — час замера.
    measured_at TEXT NOT NULL,
    -- ПРИ ЧЁМ перестаёт быть верным. Пусто разрешено и видно.
    until_cond  TEXT,
    -- кто вписал: роль сама о себе. Чужой рукой — видно в поле, а не подразумевается.
    written_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (role, skill)
);

CREATE TABLE IF NOT EXISTS role_status (  role       TEXT PRIMARY KEY,  status     TEXT NOT NULL,  updated_at TEXT NOT NULL DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS "roles" (
    role        TEXT PRIMARY KEY
                CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),
    -- 'unknown' — ДЕФОЛТ ПРИ ПЕРЕНОСЕ: след в данных не говорит о состоянии.
    -- Заполняется СЛОВОМ, а не выводом из наличия нот.
    lifecycle   TEXT NOT NULL DEFAULT 'unknown'
                CHECK (lifecycle IN ('unknown', 'alive', 'dormant', 'closed')),
    lifecycle_at     TEXT,                   -- час перехода; пусто = неизвестен (см. шапку)
    lifecycle_by     TEXT,                   -- 'owner' | роль
    lifecycle_reason TEXT,
    zone        TEXT,
    seen_in     TEXT,
    in_roster   INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS "rules" (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key    TEXT NOT NULL UNIQUE,
    body        TEXT NOT NULL,
    locked_by   TEXT NOT NULL DEFAULT 'coord',
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    basis       TEXT, authorized TEXT, source_ref TEXT,
    expiry_kind TEXT, expiry_cond TEXT,
    -- ⚡ карточка #89 шаг 4: состояние правила ПОЛЕМ, а не прозой.
    -- ⚠️ status и expiry_* — НЕ дубль: expiry говорит, ПРИ КАКОМ УСЛОВИИ правило
    --    отменится в будущем; status — отменено ли УЖЕ. Условие и свершившийся факт.
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'revoked', 'superseded')),
    revoked_at      TEXT,
    revoked_by      TEXT,
    revoked_reason  TEXT,
    -- на НОМЕР, не на имя: переименование правила не должно рвать ссылку молча
    superseded_by   INTEGER REFERENCES rules(id) ON DELETE SET NULL,
    -- КОНТРАКТ: отзыв без обстоятельств через месяц неотличим от потери
    CHECK (status <> 'revoked'
           OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
               AND revoked_reason IS NOT NULL)),
    CHECK (status <> 'superseded' OR superseded_by IS NOT NULL),
    CHECK (superseded_by IS NULL OR superseded_by <> id)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
            note        TEXT
        , fingerprint TEXT, applied_by TEXT);

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
                        -- без NOT NULL намеренно: пусто = «обмен ещё не читали»,
                        -- ноль значил бы «читали, там пусто» — это разные факты
                        last_bridge_mtime REAL,
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

CREATE TABLE IF NOT EXISTS tool_leases (
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL,            -- кто взял: аренда без имени неоспорима
    tools       TEXT NOT NULL,            -- имена файлов через пробел (пайплайн — одной арендой)
    reason      TEXT NOT NULL,            -- зачем: без причины ждать нечего
    taken_at    TEXT NOT NULL DEFAULT (datetime('now')),
    until_utc   TEXT NOT NULL,            -- ИСТЕКАЕТ САМА: забытая аренда не держит контур
    released_at TEXT,                     -- снята досрочно (норма, а не исключение)
    note        TEXT                      -- что изменилось: читает тот, кто ждал
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

CREATE INDEX IF NOT EXISTS idx_role_skill_role  ON role_skill(role);

CREATE INDEX IF NOT EXISTS idx_role_skill_skill ON role_skill(skill);

CREATE INDEX IF NOT EXISTS idx_thread_reply ON message_thread (reply_to);

CREATE INDEX IF NOT EXISTS idx_thread_root  ON message_thread (thread_id);

CREATE INDEX IF NOT EXISTS ix_role_rights_role ON role_rights (role);

CREATE INDEX IF NOT EXISTS ix_tool_leases_live ON tool_leases (released_at, until_utc);

CREATE UNIQUE INDEX IF NOT EXISTS ux_batch_race
    ON read_batches(role, last_id) WHERE acked_at IS NULL;

CREATE VIEW IF NOT EXISTS backlog_without_criterion AS
            SELECT id, role, title, priority, created_at
            FROM backlog
            WHERE status = 'open'
              AND (done_when IS NULL
                   OR TRIM(done_when, ' ' || char(9) || char(10) || char(13)) = '');

CREATE VIEW IF NOT EXISTS cursor_gaps AS
SELECT role, from_id, to_id, to_id - from_id + 1 AS notes, basis, authorized, at
FROM cursor_segments WHERE kind = 'declared';

CREATE VIEW IF NOT EXISTS cursor_truth AS
SELECT role,
       SUM(CASE WHEN kind = 'read'     THEN to_id - from_id + 1 ELSE 0 END) AS notes_read,
       SUM(CASE WHEN kind = 'declared' THEN to_id - from_id + 1 ELSE 0 END) AS notes_declared,
       SUM(CASE WHEN kind = 'born'     THEN to_id - from_id + 1 ELSE 0 END) AS notes_before_birth,
       MAX(to_id) AS covered_to
FROM cursor_segments
GROUP BY role;

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
