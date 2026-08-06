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
    ('006_addressee_field', 'PROTO'),
    ('007_cursor_segments', 'PROTO'),
    ('008_message_closure', 'PROTO'),
    ('009_message_thread', 'PROTO');

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

-- ────────────────────────────────────────────────────────────────────────────
-- ⑨ КУРЬЕРСКИЙ КУРСОР — ЧЕМ ПРОЙДЕН КАЖДЫЙ УЧАСТОК ЛЕНТЫ  (Э-З)
-- Оплачено дважды, независимо, в один день 2026-08-05:
--   · @RCC (#2897/#2898): 692 ноты ≈ 83 окна вывода — честный путь «дочитать» не
--     дорог, он НЕПРОХОДИМ. Курсор сдвинут словом владельца, основание записано
--     ОТДЕЛЬНОЙ НОТОЙ до действия. Его же вывод: «субстрат не умеет записать,
--     ПОЧЕМУ курсор оказался там, где оказался».
--   · AIA (дельта 04.08→05.08 §5.1): у них курсор врал о 3436 нотах, три инкарнации
--     подряд не двигали его вовсе. Ввели `--advance-to <id> --basis "<чем>"`.
--
-- ⚠️ ЧЕМ ЭТО ОТЛИЧАЕТСЯ ОТ РЕШЕНИЯ AIA (и почему я не копирую его дословно):
--   у них основание — ПОЛЕ рядом со значением курсора, а строка курсора ОДНА на роль.
--   Значит следующий честный `ack` либо затрёт основание, либо оставит его висеть —
--   и оно начнёт врать, будто и НОВЫЙ сдвиг был заявлен. Различение «докуда прочитано
--   глазами, докуда сдвинуто заявлением» живёт ровно до следующего чтения.
-- ⇒ Здесь не поле, а СЕГМЕНТЫ: лента делится на интервалы, каждый со своим способом
--   прохождения. Тогда вопрос «видела ли роль ноту #2500» имеет точный ответ ВСЕГДА,
--   а не до ближайшего ack. Замер живой БД 05.08: read_cursors — 3 колонки, одна строка
--   на роль; из БД узнать про 692 непрочитанные RCC НЕЛЬЗЯ ВООБЩЕ.
--
-- 📌 И это ответ на прямую просьбу @RCC контуру (#2898): «если вы писали мне
--    16.07→05.08 — не дошло, повторите». Сегодня это устная договорённость в ноте,
--    которую надо найти; здесь — ЗАПРОС к VIEW cursor_gaps.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE cursor_segments (
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL REFERENCES roles(role) ON DELETE CASCADE,
    from_id     INTEGER NOT NULL,
    to_id       INTEGER NOT NULL,
    -- 'read'     — прошло через глаза роли (ack по прочитанному батчу);
    -- 'declared' — сдвинуто заявлением: сводка вместо чтения, слово владельца, дормант;
    -- 'born'     — роли НЕ СУЩЕСТВОВАЛО: лента до её заведения. См. блок ниже.
    kind        TEXT NOT NULL CHECK (kind IN ('read', 'declared', 'born')),
    basis       TEXT,        -- ЧЕМ обосновано (обязательно для 'declared' и 'born')
    authorized  TEXT,        -- КТО дал основание: 'owner' | роль (обязательно для обоих)
    note_id     INTEGER,     -- нота, которой основание объявлено контуру
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (to_id >= from_id),
    -- Заявленный сдвиг без основания и без авторизации = молчаливый пропуск, то есть
    -- ровно то, что мы лечим. Схема не даёт его записать (у AIA это проверка в CLI —
    -- значит обходится вторым писателем; здесь обойти нечем).
    -- 'born' требует того же: рождение роли — тоже решение, у него есть автор и нота.
    CHECK (kind = 'read' OR (basis IS NOT NULL AND authorized IS NOT NULL))
);

-- ────────────────────────────────────────────────────────────────────────────
-- 🆕 ПОЧЕМУ ВИДОВ ТРИ, А НЕ ДВА — НАЙДЕНО ЖИВЫМ СЛУЧАЕМ 2026-08-06, НЕ ПРОЕКТИРОВАНИЕМ
--
-- В контуре завели девятую роль (CHROME, нота #2934). Её курсор сдвинули с нуля на
-- голову ленты — правильно и с основанием, опубликованным ДО действия. Смоделировал
-- это в прототипе двумя видами, которые у меня были, и МЕХАНИЗМ ПРОИЗВЁЛ ЛОЖЬ:
--
--     📄 [1..2909] 2909 нот — ЗАЯВЛЕНО (не читано)
--     ⚠️ Писавшим этой роли: 2909 нот НЕ ДОШЛИ. Нужен ответ — повторите запрос свежей нотой.
--
-- Никто ей не писал. Роли не существовало. Предупреждение адресовано пустому множеству
-- и требует действия, которого совершить нельзя: повторить запрос, которого не было.
-- Хуже цифра: 2909 «заявлением» встаёт в один ряд с 692 у RCC, и читающий сравнит их
-- как однородные — выйдет, что у новорождённой роли долг вчетверо больше, чем у роли,
-- которая семь недель не читала ленту. У неё долга НЕТ ВООБЩЕ.
--
-- РАЗЛИЧЕНИЕ, которое несёт третий вид:
--     'declared' — роль БЫЛА, ей писали, она не прочла    ⇒ долг реален, писавшим повторить
--     'born'     — роли НЕ БЫЛО, ей не писали             ⇒ долга нет, повторять нечего
--
-- 📌 Подтверждение, что различение живое, а не моё: @COORD в самой ноте #2934 дописал его
--    СЛОВАМИ — «её молчание читать как "не видел", а не как "отказался"». Он рукой
--    компенсировал то, чего нет в механизме. Компенсатор в прозе = недостающий вид в схеме.
-- ⚠️ Граница: 'born' НЕ отменяет обязанность обосновать сдвиг. Рождение роли — решение
--    владельца, у него есть автор и нота, и CHECK требует их так же строго.
-- ────────────────────────────────────────────────────────────────────────────
CREATE INDEX idx_cursor_seg ON cursor_segments (role, from_id, to_id);

-- ЧЕСТНАЯ КАРТИНА ПО РОЛИ: сколько пройдено глазами, сколько заявлением.
-- Не «курсор = N», а «из чего этот N состоит».
CREATE VIEW cursor_truth AS
SELECT role,
       MAX(to_id)                                                    AS cursor_at,
       SUM(CASE WHEN kind = 'read'     THEN to_id - from_id + 1 END) AS notes_read,
       SUM(CASE WHEN kind = 'declared' THEN to_id - from_id + 1 END) AS notes_declared,
       -- отдельной колонкой, а НЕ в notes_declared: пропущенное и небывшее нельзя
       -- складывать — сумма читалась бы как долг роли, которого у неё нет.
       SUM(CASE WHEN kind = 'born'     THEN to_id - from_id + 1 END) AS notes_before_birth,
       COUNT(*)                                                      AS segments
FROM cursor_segments GROUP BY role;

-- ⚠️ ГЛАВНАЯ ВИТРИНА: что роль НЕ видела ИЗ АДРЕСОВАННОГО ЕЙ. Отвечает на вопрос @RCC
-- вместо устной просьбы. Заметь: отдаёт ДИАПАЗОНЫ с основанием, а не вердикт — вердикт
-- роль заглушит, факт нет.
-- 🔴 'born' СЮДА НЕ ВХОДИТ НАМЕРЕННО: витрина существует, чтобы писавший ПОВТОРИЛ запрос.
--    До рождения роли писавших не было — повторять нечего и некому. Включи 'born' сюда —
--    и витрина начнёт требовать невыполнимого действия тем громче, чем новее роль.
CREATE VIEW cursor_gaps AS
SELECT role, from_id, to_id, to_id - from_id + 1 AS notes, basis, authorized, note_id, at
FROM cursor_segments WHERE kind = 'declared';

-- ────────────────────────────────────────────────────────────────────────────
-- ⑩ СРОЧНОСТЬ ГАСНЕТ ЗАКРЫТИЕМ ВОПРОСА, А НЕ ЧАСАМИ  (Э-Г, вариант B)
-- Замер 2026-08-05: 403 ноты старше 01.08 несут high/critical — вопрос закрыт
-- недели назад, пометка горит. Реакция адресата на high и normal ОДИНАКОВА
-- (медианы 8.1 и 8.8 мин) ⇒ пометка не сортирует живое, но мусорит в долге:
-- в непрочитанном ролей 20–36 % помечено high, и это в основном истёкшая срочность.
--
-- ⛔ ПОЧЕМУ НЕ «ИСТЕЧЕНИЕ ПО ВРЕМЕНИ» (я предлагал, владелец отверг — и он прав):
--    контур останавливается на сутки и более (30.07–04.08 — семь суток тишины).
--    Срок, отмеряемый КАЛЕНДАРЁМ, за такую паузу гасит ВСЕ пометки разом, включая
--    настоящие: проснувшийся контур получает чистое поле и теряет реальную срочность.
--    Это ровно класс «производное от календарного времени врёт, когда носитель
--    остановился» — родня mtime, сброшенного копированием.
--
-- 🪤 И ПОЧЕМУ ПРЕЖНЕЕ ПОЛЕ `resolved` НЕ РАБОТАЛО (1 нота из 1483 — я объяснил это
--    дисциплиной, и ошибся): его НЕЧЕМ поставить. Единственный писатель —
--    `check-errors.py --resolve`, и он бьёт по `WHERE tags LIKE '%"DWERR"%'`, то есть
--    только по ошибкам двойной записи Фазы 1–3. Для обычной ноты поле недоступно.
--    ⇒ Незаполняемое поле — не лень ролей, а отсутствующий механизм. Проверять надо
--    ДО вывода о дисциплине (формула AIA: «перед введением требования проверить,
--    что его можно выполнить»).
--
-- ⇒ Закрытие — не булево, а СВЯЗЬ: какая нота какую закрыла. Булево «resolved=1»
--   повторило бы класс, только что вылеченный в курсоре: факт без основания, который
--   через месяц неотличим от потери. Здесь видно ЧЕМ закрыто, и закрыть молча нечем.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE message_closure (
    message_id  INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    closed_by   INTEGER NOT NULL REFERENCES messages(id),   -- нота, которая закрыла
    closed_role TEXT NOT NULL REFERENCES roles(role),
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    -- Нота не закрывает сама себя: иначе «закрыто» ставится тем же ходом, что и вопрос,
    -- и перестаёт что-либо значить.
    CHECK (closed_by <> message_id)
);

-- СРОЧНОСТЬ — ПРОИЗВОДНАЯ, НЕ ХРАНИМАЯ. Хранится priority (что автор объявил),
-- показывается urgency (что действует сейчас). Замер Э-А: хранимое производное
-- протухает первым — поэтому вычисляем, а не пишем второе поле.
CREATE VIEW message_urgency AS
SELECT m.id, m.writer_role, m.timestamp, m.priority,
       CASE WHEN c.message_id IS NOT NULL THEN 'normal' ELSE m.priority END AS urgency,
       c.closed_by, c.closed_role, c.at AS closed_at
FROM messages m LEFT JOIN message_closure c ON c.message_id = m.id;

-- ⚠️ ВИТРИНА ДЛЯ РОЛИ: «что на тебе висит незакрытым». Показывается там, куда роль
-- и так смотрит (вывод ридера), а не отдельной командой, которую надо не забыть.
-- Забывание — это и есть механизм, который мы лечим, а не порок роли.
CREATE VIEW open_high_for_role AS
SELECT ma.role, m.id, m.writer_role, m.timestamp, m.priority
FROM messages m
JOIN message_addressee ma ON ma.message_id = m.id AND ma.kind = 'to'
LEFT JOIN message_closure c ON c.message_id = m.id
WHERE m.priority IN ('high', 'critical') AND c.message_id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- ⑪ ТРЕД: ОТВЕТ СВЯЗАН С ВОПРОСОМ ПОЛЕМ, А НЕ ПРОЗОЙ  (Ш4, 2.6)
-- Конструкция предложена AIA; НУЖДА подтверждена НАШИМ замером, а не их опытом
-- (окно #2500…#2956, 457 нот активной работы):
--     83 % наших нот ссылаются на другие ПРОЗОЙ — 1413 ссылок, 3.7 на ноту.
-- То есть связь у нас плотнее, чем у них, и вся она нечитаема машиной. Вопрос
-- «какие вопросы ко мне без ответа» сегодня не запрос, а чтение глазами.
--
-- ⚠️ ПОЧЕМУ КОРЕНЬ ХРАНИТ NULL, А НЕ СОБСТВЕННЫЙ id (это не мелочь):
--    id присваивается ПРИ вставке, поэтому «корень указывает на себя» требует второго
--    UPDATE после INSERT. Второй ход можно забыть, и тогда корень молча станет сиротой,
--    неотличимым от ноты вне треда. ⇒ корень = thread_id IS NULL, а «корень треда»
--    ВЫЧИСЛЯЕТСЯ как COALESCE(thread_id, id). Хранимое производное протухает первым —
--    тот же принцип, что у срочности и версии схемы.
--
-- ⚠️ ЧЕМ ЭТО ОТЛИЧАЕТСЯ ОТ УЖЕ ЛЕЖАЩЕГО РЯДОМ `message_closure` — иначе будут спорить:
--    thread   = «к чему это относится»  (структура разговора)
--    closure  = «вопрос закрыт»          (состояние вопроса)
--    Ответ НЕ закрывает вопрос автоматически: «ответили, но не устроило» — реальное
--    и частое состояние. Витрина ниже различает три, а не два.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE message_thread (
    message_id  INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    -- НА ЧТО отвечаю. NULL = не ответ.
    reply_to    INTEGER REFERENCES messages(id),
    -- КОРЕНЬ обсуждения. NULL = эта нота и есть корень (см. оговорку выше).
    thread_id   INTEGER REFERENCES messages(id),
    -- ВИД записки. Без него тред не отличает «висит вопрос» от «идёт разговор».
    -- NULL допустим НАМЕРЕННО: у перенесённых старых нот вида нет, и притворяться,
    -- что он известен, — ровно то, что мы лечим.
    kind        TEXT CHECK (kind IN ('question','answer','handover','status','decision')),
    -- Откуда взята связь. 'field' — роль указала при записи; 'backfill' — восстановлено
    -- из прозы. Та же честность, что у addressed_by: разбор регекспом ошибается,
    -- и ошибка обязана быть ВИДНОЙ, а не молчаливой.
    linked_by   TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
    -- Нота не отвечает сама себе и не бывает корнем самой себе через поле: два способа
    -- записать одно состояние — это два способа разойтись.
    CHECK (reply_to  IS NULL OR reply_to  <> message_id),
    CHECK (thread_id IS NULL OR thread_id <> message_id),
    -- КОНТРАКТ: ответ без вопроса — не ответ. Единственный вид, который требует связи.
    CHECK (kind <> 'answer' OR reply_to IS NOT NULL)
);
CREATE INDEX idx_thread_root  ON message_thread (thread_id);
CREATE INDEX idx_thread_reply ON message_thread (reply_to);

-- Разговор целиком, с вычисленным корнем. Ради этого всё и затевалось.
CREATE VIEW thread_view AS
SELECT COALESCE(t.thread_id, m.id) AS root_id,
       m.id, m.writer_role, m.timestamp, t.reply_to, t.kind, t.linked_by
FROM messages m LEFT JOIN message_thread t ON t.message_id = m.id;

-- 🎯 ГЛАВНАЯ ВИТРИНА Ш4: что роль СПРОСИЛИ и чем это кончилось.
-- Три состояния, а не два — потому что «ответили» и «закрыто» разные вещи:
--     'висит'            — ответа нет вовсе
--     'отвечено, не закрыто' — ответ есть, но вопрос никто не признал закрытым
--     (закрытые сюда не попадают вовсе)
CREATE VIEW open_questions_for_role AS
SELECT ma.role, m.id, m.writer_role, m.timestamp, m.priority,
       CASE WHEN a.n > 0 THEN 'отвечено, не закрыто' ELSE 'висит' END AS state,
       COALESCE(a.n, 0) AS answers
FROM messages m
JOIN message_thread t  ON t.message_id = m.id AND t.kind = 'question'
JOIN message_addressee ma ON ma.message_id = m.id AND ma.kind = 'to'
LEFT JOIN message_closure c ON c.message_id = m.id
LEFT JOIN (SELECT reply_to, COUNT(*) AS n FROM message_thread
           WHERE kind = 'answer' GROUP BY reply_to) a ON a.reply_to = m.id
WHERE c.message_id IS NULL;

-- ⚠️ ГИПОТЕЗЫ, А НЕ ДАННЫЕ. Старые ноты переезжают БЕЗ треда (решение владельца ③
-- «переносить как есть»), но 83 % из них ссылку прозой несут. Витрина ПОКАЗЫВАЕТ
-- найденное регекспом, НЕ записывая: «#2775» в теле может быть и ответом, и просто
-- упоминанием номера в примере — ровно наш незакрытый класс «употребление против
-- упоминания». Кто захочет — свяжет руками, видя, на что опирается.
CREATE VIEW thread_backfill_candidates AS
SELECT m.id, m.writer_role, m.timestamp,
       CAST(REPLACE(SUBSTR(m.body_md, INSTR(m.body_md, '#') + 1, 4), ' ', '') AS INTEGER) AS maybe_ref
FROM messages m
LEFT JOIN message_thread t ON t.message_id = m.id
WHERE t.message_id IS NULL AND INSTR(m.body_md, '#') > 0;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta (key, value) VALUES
    ('group_name', 'unnamed'),
    ('created_at', datetime('now')),
    -- ⚠️ НАРОЧНО не пишем сюда номер версии: хранимая копия производного и есть
    -- источник лжи (замер: '1.0' при фактической v2). Версия — VIEW ниже.
    ('schema_version_source', 'view schema_version — вычисляется из schema_migrations');

CREATE VIEW schema_version AS
    SELECT MAX(version) AS version, COUNT(*) AS applied FROM schema_migrations;
