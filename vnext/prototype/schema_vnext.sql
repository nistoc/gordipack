-- ============================================================================
-- schema_vnext.sql — ФУНДАМЕНТ СХЕМЫ mezosync v-next (этап Э-В, волна D)
--
-- Кредо: ЕСЛИ ФРИКЦИЮ МОЖНО СНЯТЬ КОНСТРУКЦИЕЙ — ЭТО ЛУЧШЕ ПРАВИЛА-КОМПЕНСАТОРА.
-- Всё ниже родилось из ЗАМЕРОВ живой БД 2026-07-26 (числа — в комментариях у каждого
-- блока), а не из вкусовых предпочтений. Прототип: применяется в ПЕСОЧНИЦЕ.
-- Применение к живому контуру — зона COORD и слово владельца.
--
-- ⚠️ ГЛАВНАЯ ОГОВОРКА ПРО FK (иначе весь файл — украшение):
--    В SQLite внешние ключи ВЫКЛЮЧЕНЫ по умолчанию и включаются В КАЖДОМ СОЕДИНЕНИИ
--    (`PRAGMA foreign_keys = ON`). Объявленный, но не включённый FK — это ровно тот же
--    обман, что контракт в комментарии: написано, не действует, никто не краснеет.
--    ⇒ гард `guard-schema-contract.py` проверяет ФАКТ включения, а не наличие текста.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ────────────────────────────────────────────────────────────────────────────
-- ④ РОЛЬ КАК СУЩНОСТЬ  (F2/R5)
-- Замер живой БД: таблицы roles НЕТ; роль хранится в 11 колонках под ПЯТЬЮ разными
-- именами (role · writer_role · reader_role · actor_role + role_type о другом понятии);
-- FK — ноль. Регистр держится дисциплиной каждого скрипта, и она уже протекла:
-- в audit_log живёт значение 'opssre' в нижнем регистре при роли OPSSRE.
-- Прежде это лечили правкой read-messages.py (role.upper()) — компенсатор в ОДНОМ
-- инструменте; любой другой писатель заводит расщепление курсор↔слепок заново.
-- ⇒ Нормализация переезжает в ЯДРО: одно имя колонки (role), CHECK на регистр, FK.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE roles (
    role        TEXT PRIMARY KEY
                CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),
    -- ① статус роли ПОЛЕМ. 'alive' работает · 'dormant' усыплена по слову (RCC) ·
    -- 'closed' апоптоз (EYE). Сегодня это различие живёт прозой в role_status и в
    -- памяти COORD; роль EYE пришлось охранять отдельной строкой в чужих слепках.
    lifecycle   TEXT NOT NULL DEFAULT 'alive'
                CHECK (lifecycle IN ('alive', 'dormant', 'closed')),
    -- Почему роль в этом состоянии — рядом с состоянием, а не в чужой ноте.
    lifecycle_at        TEXT NOT NULL DEFAULT (datetime('now')),
    lifecycle_by        TEXT,                      -- кто перевёл (роль или 'owner')
    lifecycle_reason    TEXT,
    zone        TEXT,                              -- за что отвечает (справочно)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ────────────────────────────────────────────────────────────────────────────
-- ① СТАТУС ПРАВИЛА ПОЛЕМ, А НЕ ПРОЗОЙ  (F12)
-- Замер живой БД 2026-07-26: правил 42, полей статуса — НИ ОДНОГО.
--   · истинно отозванных (надгробие «⛔ ОТОЗВАНО» в шапке тела): 7
--   · широкий текстовый поиск находит 15, из них 8 ЛОЖНЫХ (53 %): правило живое,
--     а в теле упоминается отзыв чего-то другого (full-scan-every-tick,
--     md-to-sqlite-phased-cutover, rhythm-survives-rebirth, …).
-- ⇒ Прозаический признак ошибается В ОБЕ СТОРОНЫ: строгий пропустит иную формулировку
--   надгробия, широкий нахватает живых. «Верь БД» тут не помогает — БД сама не знает.
-- Цена уже заплачена: 2026-07-16 sync.rules.md пять часов держал отозванное правило
-- как приказ. Это лечили правилом «при расхождении верь БД» — компенсатор, который
-- не работает, когда сама БД хранит статус текстом.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE rules (
    rule_key    TEXT PRIMARY KEY,
    body        TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'revoked', 'superseded')),
    -- Отзыв — СОБЫТИЕ: кто, когда, почему. Всё три обязательны при отзыве (CHECK ниже),
    -- потому что отзыв без причины через месяц неотличим от потери.
    revoked_at      TEXT,
    revoked_by      TEXT,
    revoked_reason  TEXT,
    -- Чем заменено. FK на само правило: «superseded_by» с опечаткой не должен
    -- молча указывать в пустоту — это тот же класс, что нота-призрак.
    superseded_by   TEXT REFERENCES rules(rule_key) ON DELETE SET NULL,
    locked_by   TEXT REFERENCES roles(role),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    -- КОНТРАКТ В СХЕМЕ: отозванное обязано нести обстоятельства отзыва,
    -- заменённое — указывать замену. Иначе статус так и останется прозой,
    -- просто переехавшей в другое поле.
    CHECK (status <> 'revoked'
           OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
               AND revoked_reason IS NOT NULL)),
    CHECK (status <> 'superseded' OR superseded_by IS NOT NULL),
    CHECK (superseded_by IS NULL OR superseded_by <> rule_key)   -- само себя не заменяет
);

-- Живые правила одним обращением — чтобы роль не решала текстом, что ещё действует.
CREATE VIEW rules_active AS
    SELECT rule_key, body, version, updated_at FROM rules WHERE status = 'active';

-- ────────────────────────────────────────────────────────────────────────────
-- ② ПРИСУТСТВИЕ И РИТМ — ПОЛЕМ  (F16, боль TAXO #2668)
-- Сегодня: role_status(role, status, updated_at) — ОДНА строка свободного текста
-- на роль. Машинно неразличимы три РАЗНЫХ мира:
--     «ритм снят по слову владельца» ⊥ «сессия умерла» ⊥ «работает молча».
-- Компенсатор сегодня — СПРОСИТЬ ВЛАДЕЛЬЦА (правило rhythm-survives-rebirth:
-- «если ритм был снят словом — спросить, возобновлять ли»). Это самый дорогой из
-- механизмов контура: вниманием человека.
-- 🔴 И замер показал вторую беду ровно там же: в живой role_status у COORD поле
--    updated_at = 2026-07-25 23:27:54, а В ТЕКСТЕ строки написано «2026-07-26 23:27 UTC».
--    Дата разъехалась на сутки, время — в будущем. Метку писали рукой, поле знало
--    точнее. ⇒ R12 в чистом виде: производное не хранить прозой рядом с истиной.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE role_presence (
    role        TEXT PRIMARY KEY REFERENCES roles(role) ON DELETE CASCADE,
    -- НАМЕРЕНИЕ (ставится словом — ролью или владельцем)
    rhythm      TEXT NOT NULL DEFAULT 'unset'
                CHECK (rhythm IN ('running', 'paused_by_owner', 'stopped_by_role', 'unset')),
    rhythm_at   TEXT NOT NULL DEFAULT (datetime('now')),
    rhythm_by   TEXT,                       -- 'owner' | роль
    rhythm_reason TEXT,
    -- ФАКТ (пишет инструмент при каждом обращении роли — рукой не заполняется)
    last_seen_at TEXT,
    session_id   TEXT,                      -- меняется при новой инкарнации
    note         TEXT,                      -- человеческая строка, СПРАВОЧНО
    CHECK (rhythm <> 'paused_by_owner' OR rhythm_by = 'owner')
);

-- Различение, которого сегодня нет ВОВСЕ. Заметь: «молчит N минут» ВЫЧИСЛЯЕТСЯ,
-- а не хранится — хранимое производное протухает первым (замер Э-А: ~22 % строк
-- слепков — производные факты, они и лгут раньше всех).
CREATE VIEW role_presence_read AS
SELECT
    p.role,
    r.lifecycle,
    p.rhythm,
    p.last_seen_at,
    CAST((julianday('now') - julianday(COALESCE(p.last_seen_at, p.rhythm_at)))
         * 1440 AS INTEGER)                              AS silent_minutes,
    CASE
        WHEN r.lifecycle <> 'alive'          THEN 'роль ' || r.lifecycle
        WHEN p.rhythm = 'paused_by_owner'    THEN 'ритм снят СЛОВОМ ВЛАДЕЛЬЦА — не возобновлять молча'
        WHEN p.rhythm = 'stopped_by_role'    THEN 'ритм снят самой ролью (передача смены)'
        WHEN p.rhythm = 'running'
             AND julianday('now') - julianday(COALESCE(p.last_seen_at, p.rhythm_at))
                 > 40.0 / 1440                THEN 'ритм ОБЪЯВЛЕН, но роль молчит — вероятно, умерла с сессией'
        WHEN p.rhythm = 'running'            THEN 'работает'
        ELSE 'состояние не объявлено'
    END                                                   AS presence
FROM role_presence p JOIN roles r ON r.role = p.role;

-- ────────────────────────────────────────────────────────────────────────────
-- ⑥ КОНТРАКТ СЕКЦИЙ — В СХЕМЕ, А НЕ В КОММЕНТАРИИ  (F13)
-- Замер: DDL живой таблицы phoenix объявляет в комментарии
--     section TEXT NOT NULL,  -- 'identity' | 'state' | 'plan' | 'history'
-- то есть ЧЕТЫРЕ секции. Фактических — СЕМЬ (+ launcher, rebirth, sources),
-- и они у ВСЕХ восьми ролей (8 × 7 = 56 строк). Комментарий был верен в день
-- написания и с тех пор лжёт — ровно класс TAXO про протухшее утверждение в эталоне.
-- ⇒ Список секций становится ТАБЛИЦЕЙ: добавить секцию можно только явной строкой,
--   и тогда расхождение невозможно — не потому что кто-то помнит, а потому что FK.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE phoenix_sections (
    section     TEXT PRIMARY KEY,
    ord         INTEGER NOT NULL,           -- порядок печати слепка
    required    INTEGER NOT NULL DEFAULT 1, -- обязательна ли для живой роли
    purpose     TEXT NOT NULL
);
INSERT INTO phoenix_sections (section, ord, required, purpose) VALUES
    ('identity', 1, 1, 'кто ты и чего тебе НЕЛЬЗЯ'),
    ('rebirth',  2, 1, 'что сделать ПЕРВЫМ делом'),
    ('sources',  3, 1, 'источники правды в порядке чтения'),
    ('state',    4, 1, 'где ты сейчас — передача дел'),
    ('plan',     5, 1, 'куда идёшь'),
    ('history',  6, 1, 'грабли, на которые не наступать'),
    ('launcher', 7, 0, 'строка, которой тебя разбудили (справочно)');

CREATE TABLE phoenix (
    role        TEXT NOT NULL REFERENCES roles(role) ON DELETE CASCADE,
    section     TEXT NOT NULL REFERENCES phoenix_sections(section),
    body        TEXT NOT NULL,
    saved_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (role, section)
);

-- Неполный слепок — не «наверное всё сохранено», а видимая строка.
CREATE VIEW phoenix_gaps AS
SELECT r.role, s.section, s.purpose
FROM roles r CROSS JOIN phoenix_sections s
LEFT JOIN phoenix p ON p.role = r.role AND p.section = s.section
WHERE r.lifecycle = 'alive' AND s.required = 1 AND p.role IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- ③ ЧЕСТНАЯ ВЕРСИЯ СХЕМЫ + РЕЕСТР МИГРАЦИЙ  (F10)
-- Замер живой БД: meta.schema_version = '1.0' при фактической v2 — в БД живут
-- read_batches, role_status, stats_log, messages_history, которых в v1 не было.
-- Реестра миграций у координационной БД НЕТ ВОВСЕ: схема менялась руками, версия
-- осталась от первого дня. То есть контур, который требует от ядра Atlas честный
-- schemaVersion в /health, сам о своей версии молчит.
-- ⇒ Версия становится СЛЕДСТВИЕМ применённых миграций, а не строкой, которую
--   кто-то должен не забыть обновить. Забыть обновление больше нельзя: версия
--   вычисляется из журнала, а гард сверяет её с ФАКТИЧЕСКИМ составом объектов.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE schema_migrations (
    version     TEXT PRIMARY KEY,           -- '002_role_entity'
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    applied_by  TEXT,
    checksum    TEXT
);
INSERT INTO schema_migrations (version, applied_by) VALUES
    ('001_base', 'PROTO'),
    ('002_role_entity', 'PROTO'),
    ('003_rule_status', 'PROTO'),
    ('004_presence', 'PROTO'),
    ('005_phoenix_sections', 'PROTO'),
    ('006_addressee_field', 'PROTO');

-- ────────────────────────────────────────────────────────────────────────────
-- ⑦ РЕЕСТР ВРЕЗОК — когда механизм менялся на самом деле
-- Добавлено 2026-07-26 10:35 UTC. Понадобилось, когда гард соответствия стал судить
-- «секция слепка старше правки механизма» по ВРЕМЕНИ ФАЙЛА — и оказалось, что mtime лжёт:
--   · его сбрасывает любое копирование, В ТОМ ЧИСЛЕ восстановление из бэкапа (после реального
--     отката признак покраснел бы у всех восьми ролей сразу);
--   · его сбрасывает `git checkout` — ровно так 2026-07-26 сломался гард «замороженные md»:
--     содержимое цело, mtime уехал, гард красный у всех НАВСЕГДА по невиновной причине.
-- ⇒ Время правки механизма — СОБЫТИЕ, а не свойство файла. Событие записывает тот, кто врезал.
-- Форма предложена @STUD (#2784): {механизм, когда, нота} — и она же даёт ПОДАЧУ:
-- не вердикт «устарело» (его роль заглушит пересохранением), а РЕЛЯЦИЮ «механизм менялся тогда,
-- секция сохранена тогда» — факт, который заглушить нечем.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE mechanism_changes (
    id          INTEGER PRIMARY KEY,
    mechanism   TEXT NOT NULL,              -- 'read-messages' | 'R16' | 'save-phoenix'
    changed_at  TEXT NOT NULL,              -- UTC, ЯВНО (шкала одна — см. урок ниже)
    changed_by  TEXT REFERENCES roles(role),
    note_id     INTEGER,                    -- нота, которой врезка объявлена контуру
    commit_ref  TEXT,
    summary     TEXT NOT NULL,
    -- Врезка, о которой не объявлено, — половина работы: учащая поверхность не узнает.
    CHECK (note_id IS NOT NULL OR commit_ref IS NOT NULL)
);
CREATE INDEX idx_mech_changes ON mechanism_changes (mechanism, changed_at);

-- Что роль видит про свои секции: реляция, а не приговор.
CREATE VIEW phoenix_vs_mechanisms AS
SELECT p.role, p.section, p.saved_at, m.mechanism, m.changed_at, m.summary,
       CASE WHEN m.changed_at > p.saved_at THEN 'механизм менялся ПОЗЖЕ — перемерь это место'
            ELSE 'секция новее правки' END AS relation
FROM phoenix p
JOIN mechanism_changes m
  ON instr(lower(p.body), lower(m.mechanism)) > 0;

-- ────────────────────────────────────────────────────────────────────────────
-- ⑧ ЛЕНТА + АДРЕСАТ КАК ПОЛЕ  (F6/R3, этап Э-Б)
-- Сегодня адресат живёт ПРОЗОЙ в теле: «[PROTO→COORD · FYI ALL]», «cc @TAXO @STUD»,
-- часто разорвано на несколько строк. Замер #2775 (живые данные, 07-26): лично
-- адресовано роли **1–20 %** прочитанного; у RCC исторически 18 нот из 482 (позже
-- перемерено на 692/46 — тот же порядок). Единственный способ найти своё сегодня —
-- прочитать ВСЁ тело: чтобы понять, что нота твоя, ты обязан её прочитать.
--
-- ⇒ Адресат переезжает в СХЕМУ: явная таблица `message_addressee` (many-to-many —
--   роль может стоять и в to, и в cc у разных нот в один момент), НЕ JSON-колонка.
--   Причина — запрос, ради которого всё затевается: «покажи адресованное мне» ОДНИМ
--   индексируемым обращением. JSON-массив в SQLite такого дёшево не даёт: без JSON1
--   фильтрация — LIKE-скан по каждой строке, то есть то же самое чтение всего.
--
-- ⚠️ ВТОРАЯ ПОЛОВИНА, БЕЗ КОТОРОЙ АДРЕСАТ ПОЛЕМ ВРЕДЕН (цена та же нота #2775):
--   индекс 187 нот = 24 КБ против 10 тел = 23 КБ — индекс ПЛОТНЕЕ в 18.7 раза.
--   «Читать ТОЛЬКО адресованное» = ослепнуть: канон/вехи/чужие уроки касаются всех
--   и адресата не несут. Поэтому `broadcast=1` — ЯВНЫЙ канал «касается всех», а
--   НЕ молчаливое отсутствие адресата (оно неотличимо от «забыл указать»,
--   см. VIEW messages_unaddressed — это ДОЛГ данных, а не нормальный broadcast).
--
-- ⚠️ ЧЕСТНОСТЬ МИГРАЦИИ (урок AIA §3.1, дельта 04.08→05.08, «детектор не отличает
--   употребление от упоминания»): регексп-разбор старой прозы (backfill) ошибается —
--   пропускает адресата, разбитого переносом строки, путает упоминание роли в
--   примере с адресацией ей. `addressed_by` делает эту разницу ВИДИМОЙ, а не
--   молчаливой: поле, заполненное явно при записи, доверия заслуживает больше,
--   чем восстановленное регекспом из истории.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    writer_role TEXT NOT NULL REFERENCES roles(role),
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    body_md     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    priority    TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'high', 'critical')),
    resolved    INTEGER NOT NULL DEFAULT 0,
    broadcast   INTEGER NOT NULL DEFAULT 0,
    -- 'field' — роль передала --to/--cc явно при записи; 'backfill' — восстановлено
    -- регекспом `@РОЛЬ` из прозы при миграции старых нот. Разница ОБЯЗАНА быть видна.
    addressed_by TEXT NOT NULL DEFAULT 'field' CHECK (addressed_by IN ('field', 'backfill'))
);

CREATE TABLE message_addressee (
    message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    role        TEXT NOT NULL REFERENCES roles(role),
    kind        TEXT NOT NULL CHECK (kind IN ('to', 'cc')),
    PRIMARY KEY (message_id, role, kind)
);
-- Индекс под ИМЕННО тот запрос, ради которого всё затевалось.
CREATE INDEX idx_addressee_role ON message_addressee (role, message_id);

-- «Моя лента» одним обращением — то, чего сегодня нет вовсе (сегодня — regex по телу).
CREATE VIEW messages_for_role AS
SELECT m.id, m.writer_role, m.timestamp, m.body_md, m.tags, m.priority, m.resolved,
       ma.kind AS my_reason
FROM messages m
JOIN message_addressee ma ON ma.message_id = m.id
UNION ALL
SELECT m.id, m.writer_role, m.timestamp, m.body_md, m.tags, m.priority, m.resolved,
       'broadcast' AS my_reason
FROM messages m
WHERE m.broadcast = 1;

-- Долг адресации, видимый СРАЗУ, а не найденный чтением: ни broadcast, ни адресата.
-- Либо забыли указать (реальный долг), либо это скрытый broadcast, который контур
-- сегодня не отличает от забытого поля — то есть та же дыра, которую чинит эта таблица.
CREATE VIEW messages_unaddressed AS
SELECT m.id, m.writer_role, m.timestamp
FROM messages m
LEFT JOIN message_addressee ma ON ma.message_id = m.id
WHERE m.broadcast = 0 AND ma.message_id IS NULL;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta (key, value) VALUES
    ('group_name', 'unnamed'),
    ('created_at', datetime('now')),
    -- ⚠️ НАРОЧНО не пишем сюда номер версии: хранимая копия производного и есть
    -- источник лжи (замер: '1.0' при фактической v2). Версия — VIEW ниже.
    ('schema_version_source', 'view schema_version — вычисляется из schema_migrations');

CREATE VIEW schema_version AS
    SELECT MAX(version) AS version, COUNT(*) AS applied FROM schema_migrations;
