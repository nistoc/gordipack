#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПЕРЕВОД РАБОЧЕЙ БАЗЫ НА НОВУЮ СТРУКТУРУ — ПО ОДНОЙ ТАБЛИЦЕ ЗА ШАГ.

Решения владельца 2026-08-06 09:55 UTC (выбор из вариантов, карточка #61):
  ① путь ................ ПО ОДНОЙ ТАБЛИЦЕ
  ② переносимость ....... СНАЧАЛА НАМ, потом обобщить для других контуров
  ③ старые данные ....... ПЕРЕНЕСТИ КАК ЕСТЬ (регистр `opssre`, ноты без адресата — переезжают)

⛔ ВЫБОР ПУТИ — НЕ РАЗРЕШЕНИЕ НА НАКАТ. Накат на живую базу требует ОТДЕЛЬНОГО живого слова
   владельца и делается COORD (живой субстрат — его зона). Этот файл пишу и проверяю на КОПИИ.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🪤 ЗАЩИТА, ВСТРОЕННАЯ ИЗ ЧУЖОГО ПРОМАХА (@COORD, #2955, 2026-08-06)

Он проверял починку гарда «на копии»: подменил путь к базе через sed, подмена МОЛЧА не
сработала (обратные слэши), скрипт остался смотреть в ЖИВУЮ базу и напечатал «✅ всё хорошо».
Его слова:
    «Стенд, который молча не подменился, отвечает за настоящую систему — и отвечает убедительно.»

Поэтому здесь путь к базе НЕ подменяется и НЕ угадывается:
  ① фактический абсолютный путь печатается ПЕРЕД каждым действием — всегда, не по флагу;
  ② совпадение с живой базой определяется по resolve(), а не по строке (строка «.mezosync/…»
     и «C:\\guts\\.atlas\\.mezosync\\…» — один файл, но разные строки);
  ③ живая база без --i-am-coord-and-owner-said отвергается ДО открытия соединения;
  ④ отчёт печатает не «готово», а ЧИСЛА до и после — «готово» нельзя проверить, числа можно.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ПОРЯДОК ШАГОВ ЗАДАН НЕ ПОЛЬЗОЙ, А ЗАВИСИМОСТЯМИ (замер 2026-08-06 по живой копии):
    roles ................ ни от чего        ⇐ на неё ссылаются 5 из 8 новых таблиц
    schema_migrations .... ни от чего        ⇐ ею записываются сами шаги, поэтому она ПЕРВАЯ
    messages +2 колонки .. ADD COLUMN
    message_addressee .... → roles, messages
    cursor_segments ...... → roles
    message_closure ...... → roles, messages

⚠️ `rules` В ЭТОТ СЦЕНАРИЙ НЕ ВХОДИТ, и это не забывчивость: в живой таблице есть колонка `id`,
   которой в новой схеме нет (ключом стал rule_key). SQLite не умеет DROP COLUMN в старых версиях
   и не умеет менять первичный ключ — таблицу пришлось бы пересоздавать с переносом строк, а это
   единственный ломающий шаг во всём переводе. Его надо нести владельцу отдельно, а не прятать
   в общий сценарий.
"""

import argparse
import pathlib
import re
import sqlite3
import sys
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()
GUARD_FLAG = "--i-am-coord-and-owner-said"


# ═════════════════════════════════════════════════════════════════════════════
# ЗАЩИТА ПУТИ
# ═════════════════════════════════════════════════════════════════════════════

def open_db(db_path: str, allow_live: bool) -> sqlite3.Connection:
    """Открывает базу, НАЗЫВАЯ вслух, какую именно. Живую — только по явному флагу."""
    p = pathlib.Path(db_path).expanduser()
    try:
        real = p.resolve()
    except OSError:
        real = p.absolute()

    print(f"📂 БАЗА: {real}")
    if not p.exists():
        sys.exit(f"⛔ ОТКАЗ: файла нет. Проверь путь — молчаливая опечатка увела бы прогон "
                 f"в другую базу или создала пустышку.")

    is_live = False
    try:
        is_live = real == LIVE_DB.resolve()
    except OSError:
        is_live = str(real).lower() == str(LIVE_DB).lower()

    if is_live and not allow_live:
        sys.exit(f"⛔ ОТКАЗ: это ЖИВАЯ база контура.\n"
                 f"   Перевод рабочей базы делает COORD и только по ОТДЕЛЬНОМУ живому слову\n"
                 f"   владельца. Выбор пути (карточка #61) разрешением не является.\n"
                 f"   Если слово есть — повтори с {GUARD_FLAG}.")
    print("   ⚠️ ЭТО ЖИВАЯ БАЗА, флаг снят вручную." if is_live else "   ✅ не живая база — песочница/копия")

    con = sqlite3.connect(str(p))
    con.execute("PRAGMA foreign_keys = ON")
    return con


# ═════════════════════════════════════════════════════════════════════════════
# УЧЁТ ШАГОВ
# ═════════════════════════════════════════════════════════════════════════════

def ensure_journal(con: sqlite3.Connection) -> None:
    """Шаг 0. Таблица учёта шагов заводится ПЕРВОЙ — иначе нечем записать остальные."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
            note        TEXT
        )""")
    con.commit()


def is_done(con: sqlite3.Connection, version: str) -> bool:
    return con.execute("SELECT 1 FROM schema_migrations WHERE version = ?",
                       (version,)).fetchone() is not None


def mark_done(con: sqlite3.Connection, version: str, note: str) -> None:
    con.execute("INSERT OR REPLACE INTO schema_migrations (version, note) VALUES (?,?)",
                (version, note))
    con.commit()


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (name,)).fetchone() is not None


def has_column(con: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 1 — roles
# ═════════════════════════════════════════════════════════════════════════════

STEP1 = "001-roles"


def step1_roles(con: sqlite3.Connection, dry: bool) -> dict:
    """Реестр ролей. В живой базе такой таблицы НЕТ ВОВСЕ: состав ролей выводится из
    phoenix, read_cursors и правила role-roster-and-zones. Пять из восьми новых таблиц
    ссылаются на неё внешним ключом — без неё не встанет ни одна.

    Состав СОБИРАЕТСЯ ИЗ ДАННЫХ, а не переписывается руками: руками — значит по чьему-то
    представлению о составе, а оно, как мы знаем, протухает молча.
    ⚠️ Решение владельца ③ «перенести как есть» соблюдено буквально: регистр ролей НЕ
    нормализуется. Если в живой базе роль записана и как OPSSRE, и как opssre — переедут
    ОБЕ, и это будет видно в отчёте, а не тихо слито.
    """
    found = {}
    for src, q in (
        ("phoenix",      "SELECT DISTINCT role FROM phoenix"),
        ("read_cursors", "SELECT DISTINCT reader_role FROM read_cursors"),
        ("messages",     "SELECT DISTINCT writer_role FROM messages"),
    ):
        for (r,) in con.execute(q):
            if r:
                found.setdefault(r, set()).add(src)

    # 🔴 СВЕРКА С ЖИВЫМ РЕЕСТРОМ — найдена прогоном на копии 2026-08-06 14:38 UTC.
    # Первый вариант ставил всем ролям status='active' по умолчанию. В данных живут следы
    # ролей, ЗАКРЫТЫХ владельцем (апоптоз 16.07): они писали ноты и имеют слепки. Шаг
    # воскресил бы их как активные — и реестр, собранный «из данных», стал бы утверждать
    # то, чего данные не говорят. Ровно наш класс: механизм делает не то, что о нём думают.
    # ⇒ Статус НЕ УГАДЫВАЕТСЯ. Данные несут «роль встречалась», и только это записывается.
    #   Живой состав знает правило role-roster-and-zones — оно и есть реестр; расхождение
    #   с ним НАЗЫВАЕТСЯ в отчёте, а не чинится молча (решение владельца ③).
    # ⚠️ ЦЕНА ПЕРВОГО ВАРИАНТА ЭТОГО РАЗБОРА, оплаченная прогоном на копии 14:39 UTC:
    #    брал первое слово каждой строки на «·» — и «нашёл» роли ЯДРО, ВИДЖЕТЫ, ССЫЛКА,
    #    `/V1/SEARCH`. Строки-пояснения в правиле начинаются тем же символом, что строки
    #    реестра. Это мой собственный незакрытый класс «употребление против упоминания»,
    #    и здесь он был опаснее обычного: разбор выдал УСПОКАИВАЮЩЕЕ «расхождений нет».
    # ⇒ Разбор СТРОГИЙ (роль = заглавные латиницей + тире), и распознанное ПЕЧАТАЕТСЯ
    #   целиком: если оно снова наберёт мусора, это будет видно в отчёте, а не спрятано
    #   за словом «нет».
    roster = set()
    try:
        row = con.execute("SELECT body FROM rules WHERE rule_key='role-roster-and-zones'").fetchone()
        if row:
            for line in row[0].splitlines():
                m = re.match(r"^\s*·\s*([A-Za-z][A-Za-z0-9]{1,15})\s*[—–-]\s", line)
                if m:
                    roster.add(m.group(1).upper())
    except sqlite3.Error:
        pass

    before = con.execute("SELECT COUNT(*) FROM roles").fetchone()[0] if table_exists(con, "roles") else 0

    if not dry:
        con.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                role        TEXT PRIMARY KEY,
                -- 'unknown' — ДЕФОЛТ ПРИ ПЕРЕНОСЕ: след в данных не говорит о статусе.
                -- Заполняется словом, а не выводом из наличия нот.
                status      TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (status IN ('unknown', 'active', 'dormant', 'closed')),
                seen_in     TEXT,
                in_roster   INTEGER,      -- 1 — есть в живом реестре · 0 — нет · NULL — реестр не прочитан
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )""")
        con.executemany(
            "INSERT OR IGNORE INTO roles (role, seen_in, in_roster) VALUES (?,?,?)",
            [(r, ",".join(sorted(s)), (1 if r.upper() in roster else 0) if roster else None)
             for r, s in sorted(found.items())])
        con.commit()

    after = con.execute("SELECT COUNT(*) FROM roles").fetchone()[0] if table_exists(con, "roles") else 0
    # регистровые двойники — называем, а не чиним: чинить = менять данные, чего владелец не просил
    lower = {}
    for r in found:
        lower.setdefault(r.lower(), []).append(r)
    dupes = {k: v for k, v in lower.items() if len(v) > 1}
    ghosts = sorted(r for r in found if roster and r.upper() not in roster)
    silent = sorted(r for r in roster if r not in {f.upper() for f in found})
    return {"найдено ролей": len(found), "было": before, "стало": after,
            "регистровые двойники": dupes or "нет",
            # печатается СОСТАВ, а не число: число «16 ролей» в прошлом прогоне скрыло,
            # что четыре из них — не роли вовсе
            "реестр распознан как": sorted(roster) if roster else "НЕ ПРОЧИТАН — сверки не было",
            "🔴 в данных есть, в реестре НЕТ (следы закрытых — статус НЕ 'active')": ghosts or "нет",
            "в реестре есть, в данных следов нет": silent or "нет",
            "состав": sorted(found)}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 2 — messages: две колонки
# ═════════════════════════════════════════════════════════════════════════════

STEP2 = "002-messages-broadcast-addressed_by"


def step2_messages_columns(con: sqlite3.Connection, dry: bool) -> dict:
    """Две колонки для адресата. ADD COLUMN — единственная операция, которую SQLite делает
    без пересоздания таблицы, поэтому шаг дешёвый и откатывается только пересозданием.

    `addressed_by` со значением 'backfill' у ВСЕХ старых нот — это и есть решение ③ владельца
    в машинном виде: старое не притворяется заполненным по-новому. Новое пойдёт с 'field'.
    """
    before = {
        "broadcast": has_column(con, "messages", "broadcast"),
        "addressed_by": has_column(con, "messages", "addressed_by"),
    }
    if not dry:
        if not before["broadcast"]:
            con.execute("ALTER TABLE messages ADD COLUMN broadcast INTEGER NOT NULL DEFAULT 0")
        if not before["addressed_by"]:
            con.execute("ALTER TABLE messages ADD COLUMN addressed_by TEXT NOT NULL "
                        "DEFAULT 'backfill' CHECK (addressed_by IN ('field','backfill'))")
        con.commit()
    after = {
        "broadcast": has_column(con, "messages", "broadcast"),
        "addressed_by": has_column(con, "messages", "addressed_by"),
    }
    n = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return {"было": before, "стало": after, "нот помечено 'backfill'": n if after["addressed_by"] else 0}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 3 — cursor_segments
# ═════════════════════════════════════════════════════════════════════════════

STEP3 = "003-cursor-segments"


def step3_cursor_segments(con: sqlite3.Connection, dry: bool) -> dict:
    """Честный курсор. Существующее плоское значение переносится ОДНИМ отрезком на роль.

    🔴 И вот здесь решение ③ «перенести как есть» имеет цену, которую надо назвать вслух,
    а не обнаружить потом: КАКОЙ ВИД поставить перенесённому отрезку?
      'read'     — соврёт: мы не знаем, что роль прочла глазами всё до курсора
      'declared' — соврёт иначе: объявит долгом то, что, возможно, читано честно
      'born'     — соврёт третьим способом
    Ставится 'declared' с основанием «перенос плоского курсора 06.08; способ прохождения
    участка в старой структуре НЕ ХРАНИЛСЯ» — то есть запись честно говорит, что не знает.
    ⚠️ Следствие: сразу после перевода витрина «что до роли не дошло» покажет ВСЕ старые
    участки как непройденные глазами. Это не поломка и не долг — это отсутствие данных,
    названное своим именем. Новые отрезки пойдут уже с настоящим видом.
    """
    made = []
    if not dry:
        con.execute("""
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
            )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cursor_seg ON cursor_segments (role, from_id, to_id)")

    for role, cur in con.execute("SELECT reader_role, last_read_id FROM read_cursors ORDER BY reader_role"):
        if not cur or cur < 1:
            made.append((role, "пропущен: курсор 0 — переносить нечего"))
            continue
        if not dry:
            exists = con.execute("SELECT 1 FROM cursor_segments WHERE role=? AND from_id=1",
                                 (role,)).fetchone()
            if exists:
                made.append((role, "уже перенесён"))
                continue
            con.execute(
                "INSERT INTO cursor_segments (role, from_id, to_id, kind, basis, authorized) "
                "VALUES (?,1,?,'declared',?,?)",
                (role, cur,
                 "перенос плоского курсора 2026-08-06; способ прохождения участка "
                 "в старой структуре НЕ ХРАНИЛСЯ — вид неизвестен, а не 'не читано'",
                 "owner"))
        made.append((role, f"[1..{cur}]"))
    if not dry:
        con.commit()
    total = con.execute("SELECT COUNT(*) FROM cursor_segments").fetchone()[0] if table_exists(con, "cursor_segments") else 0
    return {"перенесено": dict(made), "отрезков в таблице": total}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 4 — message_thread
# ═════════════════════════════════════════════════════════════════════════════

STEP4 = "004-message-thread"


def step4_message_thread(con: sqlite3.Connection, dry: bool) -> dict:
    """Треды. Связь «ответ → вопрос» полем вместо прозы.

    Замер, ради которого шаг делается (окно #2500…#2956): 83 % нот ссылаются на другие
    прозой, 1413 ссылок. Связь плотная — и вся нечитаема машиной.

    🔴 РЕШЕНИЕ ③ ВЛАДЕЛЬЦА («переносить как есть») ЗДЕСЬ ЗНАЧИТ: старые ноты переезжают
    БЕЗ треда вообще. Ни одной строки в message_thread не создаётся — притворяться, что
    связи известны, нельзя: `#2775` в теле бывает и ответом, и упоминанием номера
    в примере (наш незакрытый класс «употребление против упоминания», 5 подтверждений).
    ⚠️ Следствие, называю до наката: сразу после шага витрина «вопросы ко мне без ответа»
    будет ПУСТОЙ — не потому что вопросов нет, а потому что видов у старых нот нет.
    Наполняется она только новыми записями. Это отсутствие данных, а не поломка.
    📌 Гипотезы для ручной сшивки не теряются: VIEW thread_backfill_candidates показывает
    найденные прозой ссылки, ничего не записывая.

    Отдельная таблица, а не колонки в messages, — сознательно: у messages уже 9 колонок,
    а треды нужны не каждой ноте. Плюс отдельную таблицу можно снести целиком при откате,
    не пересоздавая messages (SQLite не умеет DROP COLUMN в старых версиях — тот же
    капкан, из-за которого `rules` вынесена из этого сценария).
    """
    before = table_exists(con, "message_thread")
    if not dry:
        con.execute("""
            CREATE TABLE IF NOT EXISTS message_thread (
                message_id  INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                reply_to    INTEGER REFERENCES messages(id),
                thread_id   INTEGER REFERENCES messages(id),
                kind        TEXT CHECK (kind IN ('question','answer','handover','status','decision')),
                linked_by   TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
                CHECK (reply_to  IS NULL OR reply_to  <> message_id),
                CHECK (thread_id IS NULL OR thread_id <> message_id),
                CHECK (kind <> 'answer' OR reply_to IS NOT NULL)
            )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_thread_root  ON message_thread (thread_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_thread_reply ON message_thread (reply_to)")
        con.commit()

    total = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    linked = (con.execute("SELECT COUNT(*) FROM message_thread").fetchone()[0]
              if table_exists(con, "message_thread") else 0)
    # Сколько связей ЛЕЖИТ В ПРОЗЕ и осталось невзятым — число называется вслух,
    # чтобы «пусто в витрине» не читалось как «связей нет».
    prose = con.execute(
        "SELECT COUNT(*) FROM messages WHERE body_md LIKE '%#2%' OR body_md LIKE '%#1%'"
    ).fetchone()[0]
    return {"таблица была": before, "таблица есть": table_exists(con, "message_thread"),
            "нот всего": total, "связей записано": linked,
            "нот со ссылкой в прозе (НЕ взяты — решение ③)": prose}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 5 — критерий «готово» + связь записки с задачей
# ═════════════════════════════════════════════════════════════════════════════

STEP5 = "005-task-criterion-and-link"


def step5_task_criterion(con: sqlite3.Connection, dry: bool) -> dict:
    """Критерий закрытия у карточки + связь записки с задачей.

    Замер живой БД 14:43 UTC: карточек 72 (открытых 40), колонок со словом
    done/criteria/accept — НИ ОДНОЙ. «Готово» решается мнением закрывающего.

    ⚠️ СВЯЗЬ — ТАБЛИЦА, А НЕ КОЛОНКА task_id: 348 записок упоминают несколько номеров
    карточек против 399 с одним. Одна колонка заставила бы выбрать одну из шести, и
    остальные пять снова ушли бы в прозу — шаг не сделал бы ничего.

    ⛔ ЧЕГО ЭТОТ ШАГ НАРОЧНО НЕ ДЕЛАЕТ — сторож закрытия (триггер, запрещающий закрыть
       карточку без критерия). Он написан и проверен укусом, но МЕНЯЕТ ПОВЕДЕНИЕ живого
       механизма: после включения существующие инструменты координатора перестанут
       закрывать карточки. Такое не прячут в общий сценарий — включается отдельно
       и отдельным словом.
    📌 И честно про цену этого воздержания: без сторожа колонка рискует остаться пустой.
       Ровно то, что случилось с полем `resolved` — 1 запись из 1483, потому что ставить
       было нечем. Витрина `backlog_without_criterion` показывает долг, но витрину надо
       позвать, а позвать — значит помнить. Выбор настоящий, и он не мой.
    """
    if not table_exists(con, "backlog"):
        return {"пропущен": "таблицы backlog в этой базе нет"}

    had_col = has_column(con, "backlog", "done_when")
    had_tbl = table_exists(con, "message_task")

    if not dry:
        if not had_col:
            con.execute("ALTER TABLE backlog ADD COLUMN done_when TEXT")
        con.execute("""
            CREATE TABLE IF NOT EXISTS message_task (
                message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                task_id     INTEGER NOT NULL REFERENCES backlog(id)  ON DELETE CASCADE,
                linked_by   TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
                PRIMARY KEY (message_id, task_id)
            )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_message_task_task "
                    "ON message_task (task_id, message_id)")
        con.commit()

    total = con.execute("SELECT COUNT(*) FROM backlog").fetchone()[0]
    open_n = con.execute("SELECT COUNT(*) FROM backlog WHERE status='open'").fetchone()[0]
    no_crit = (con.execute("SELECT COUNT(*) FROM backlog WHERE status='open' "
                           "AND (done_when IS NULL OR TRIM(done_when)='')").fetchone()[0]
               if has_column(con, "backlog", "done_when") else open_n)
    links = (con.execute("SELECT COUNT(*) FROM message_task").fetchone()[0]
             if table_exists(con, "message_task") else 0)
    # ⚠️ КЛЮЧИ РАЗНЫЕ. В первом варианте оба факта писались под ключом "есть", и второй
    #    молча затирал первый — в отчёте пропала целая строка, и заметить это можно было
    #    только сравнив число строк. Отчёт, теряющий факт без единого признака потери, —
    #    тот же класс, что молчаливый no-op проверки.
    return {"колонка done_when была": had_col,
            "колонка done_when есть": has_column(con, "backlog", "done_when"),
            "таблица message_task была": had_tbl,
            "таблица message_task есть": table_exists(con, "message_task"),
            "карточек всего": total, "открытых": open_n,
            "🔴 открытых БЕЗ критерия (весь долг сразу виден)": no_crit,
            "связей записка↔задача записано": links,
            "сторож закрытия": "НЕ включён — меняет поведение живых инструментов, нужно слово"}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 6 — номер версии вычисляется, старый снимается надгробием
# ═════════════════════════════════════════════════════════════════════════════

STEP6 = "006-schema-version-computed"


def step6_schema_version(con: sqlite3.Connection, dry: bool) -> dict:
    """Номер версии перестаёт храниться строкой и начинает вычисляться (решение
    владельца 2026-08-06 15:21 UTC).

    🔴 ЗАМЕР, РАДИ КОТОРОГО ШАГ ДЕЛАЕТСЯ: в рабочей базе лежит `schema_version = '1.0'`
    при фактической ВТОРОЙ версии, а после шагов 001…005 — при третьей. Номер отстал
    на ДВЕ версии и всё это время выглядел достоверным. Строка в meta ничем не связана
    с тем, что в базе есть.

    ⚠️ СТАРАЯ СТРОКА НЕ УДАЛЯЕТСЯ И НЕ ЗАМЕНЯЕТСЯ МОЛЧА. Молчаливая замена '1.0'→'3.0'
    неотличима от того, что значение было верным всё это время, — а оно врало полтора
    месяца, и следующий, кто увидит там аккуратное число, снова ему поверит.
    ⇒ Значение заменяется НАДГРОБИЕМ с датой, причиной и указанием, где смотреть.

    📌 Рубеж версии — явная строка `v3` в журнале шагов, а не максимум номеров шагов:
    `005-task-criterion…` — номер ШАГА, не версия СХЕМЫ, и читался бы как версия.
    """
    if not table_exists(con, "meta"):
        return {"пропущен": "таблицы meta в этой базе нет"}

    old = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    old_val = old[0] if old else None
    had_milestone = con.execute(
        "SELECT 1 FROM schema_migrations WHERE version='v3'").fetchone() is not None

    tombstone = ("⛔ ОТОЗВАНО 2026-08-06 (шаг 006): это поле врало ДВЕ версии подряд "
                 "('1.0' при фактической v2, затем v3) — хранимый номер ничем не связан "
                 "с составом базы. Действующий источник: VIEW schema_version, "
                 "вычисляется из журнала schema_migrations.")

    if not dry:
        # 🪤 «ПОСЛЕ РУБЕЖА» СЧИТАЕТСЯ ПО ПОРЯДКУ ЗАПИСИ (rowid), А НЕ ПО ВРЕМЕНИ.
        #    Первый вариант сравнивал applied_at — и дал верный ноль ТОЛЬКО потому,
        #    что рубеж и шаг 006 попали в одну секунду (проверено на копии 15:26:03).
        #    Секундой позже вышла бы ложная тревога «1 шаг сверх рубежа».
        #    Условие, которое держится на совпадении, а не на конструкции, —
        #    это не условие. Порядок вставки не зависит от разрешения часов.
        # 📌 И сам рубеж объявляется НЕ ЗДЕСЬ, а в конце прогона (declare_milestone):
        #    версия собрана, когда применены все её шаги, включая этот.
        con.execute("DROP VIEW IF EXISTS schema_version")
        con.execute("""
            CREATE VIEW schema_version AS
            SELECT
                (SELECT version FROM schema_migrations WHERE version GLOB 'v[0-9]*'
                  ORDER BY rowid DESC LIMIT 1)                                    AS version,
                (SELECT COUNT(*) FROM schema_migrations WHERE version NOT GLOB 'v[0-9]*') AS steps_total,
                (SELECT COUNT(*) FROM schema_migrations m
                  WHERE m.version NOT GLOB 'v[0-9]*'
                    AND m.rowid > COALESCE((SELECT rowid FROM schema_migrations
                                             WHERE version GLOB 'v[0-9]*'
                                             ORDER BY rowid DESC LIMIT 1), 0))    AS steps_after_milestone
            """)
        if old_val is not None and not old_val.startswith("⛔"):
            con.execute("UPDATE meta SET value=? WHERE key='schema_version'", (tombstone,))
        con.commit()

    return {"было в meta.schema_version": old_val,
            "стало в meta.schema_version": "надгробие с датой, причиной и указателем"
                                           if not dry else "(сухой прогон)",
            "рубеж v3 в журнале был": had_milestone,
            "витрина schema_version": "создана; рубеж объявляется в конце прогона",
            "как читать": "«шагов после рубежа» больше нуля ⇒ версия объявлена не до конца, "
                          "и это видно без чьей-либо сверки"}


# ═════════════════════════════════════════════════════════════════════════════
# ШАГ 7 — подсветка карточек без критерия приёмки
# ═════════════════════════════════════════════════════════════════════════════

STEP7 = "007-backlog-criterion-view"


def step7_criterion_view(con: sqlite3.Connection, dry: bool) -> dict:
    """Подсветка задач без критерия приёмки — слово владельца 2026-08-06 15:26 UTC:
    «критерий обязателен; у старых, где его нет, — ПОДСВЕТИТЬ, а не блокировать».

    🔴 ПОЧЕМУ ЭТО ОТДЕЛЬНЫЙ ШАГ, А НЕ ЧАСТЬ ПЯТОГО — И ЭТО МОЙ ПРОМАХ, НЕ УТОЧНЕНИЕ.
    Шаг 005 завёл колонку `done_when` и таблицу связи, а витрину подсветки — НЕТ:
    она существовала только в эталонной схеме прототипа. При этом я сам написал
    контуру (#2989), что «витрина показывает долг», координатор повторил это в отчёте
    о накате, третья роль сослалась на неё в разборе — и все трое говорили о механизме,
    которого в рабочей базе не было.
    > **Механизм, существующий в эталоне, пересказывается как существующий в системе.**
    Проверяется одним запросом к списку витрин, и никто из троих его не сделал:
    эталон читали как факт о мире.
    ⇒ Шаг 005 уже помечен выполненным, и его повтор пропускается по построению.
      Дополнять задним числом нечем — значит новый шаг, а не тихая правка старого.
    """
    if not table_exists(con, "backlog"):
        return {"пропущен": "таблицы backlog в этой базе нет"}
    if not has_column(con, "backlog", "done_when"):
        return {"пропущен": "колонки done_when нет — сначала шаг 005"}

    before = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' "
                         "AND name='backlog_without_criterion'").fetchone()[0]
    if not dry:
        con.execute("DROP VIEW IF EXISTS backlog_without_criterion")
        # TRIM с явным набором символов: голый TRIM в SQLite снимает только пробел,
        # и критерий из одной табуляции считался бы настоящим (поймано приёмкой 14:46 UTC).
        con.execute("""
            CREATE VIEW backlog_without_criterion AS
            SELECT id, role, title, priority, created_at
            FROM backlog
            WHERE status = 'open'
              AND (done_when IS NULL
                   OR TRIM(done_when, ' ' || char(9) || char(10) || char(13)) = '')
            """)
        con.commit()

    open_n = con.execute("SELECT COUNT(*) FROM backlog WHERE status='open'").fetchone()[0]
    lit = (con.execute("SELECT COUNT(*) FROM backlog_without_criterion").fetchone()[0]
           if not dry and con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' "
                                      "AND name='backlog_without_criterion'").fetchone()[0]
           else None)
    return {"витрина была": bool(before),
            "витрина есть": (not dry),
            "открытых карточек": open_n,
            "подсвечено (без критерия)": lit if lit is not None else "(сухой прогон)",
            "⛔ запрет НЕ включён": "сторож закрытия остаётся выключенным — слово владельца "
                                   "«подсветить, а не блокировать»",
            "⚠️ чего витрина не делает": "её надо ПОЗВАТЬ. Подсветка сильнее там, куда роль "
                                        "и так смотрит — в выводе списка карточек; это зона COORD"}


MILESTONE = "v3"


def declare_milestone(con: sqlite3.Connection) -> str:
    """Рубеж версии объявляется ПОСЛЕДНИМ — когда все её шаги применены.

    Порядок здесь несущий, а не косметический: витрина считает «шаги сверх рубежа»
    по порядку записи. Объяви рубеж раньше последнего шага — и он же покажет
    расхождение, которого нет.
    """
    if not table_exists(con, "schema_migrations"):
        return "журнала шагов нет — рубеж не объявлен"
    missing = [v for v, _, _ in STEPS if not is_done(con, v)]
    if missing:
        return f"рубеж НЕ объявлен: не применены шаги {missing}"
    con.execute("DELETE FROM schema_migrations WHERE version = ?", (MILESTONE,))
    con.execute("INSERT INTO schema_migrations (version, note) VALUES (?,?)",
                (MILESTONE, f"рубеж: версия {MILESTONE} = шаги "
                            f"{STEPS[0][0][:3]}…{STEPS[-1][0][:3]}"))
    con.commit()
    row = con.execute("SELECT version, steps_total, steps_after_milestone "
                      "FROM schema_version").fetchone()
    return f"версия {row[0]} · шагов {row[1]} · сверх рубежа {row[2]}"


STEPS = [
    (STEP1, "реестр ролей (опора для пяти таблиц)", step1_roles),
    (STEP2, "messages: broadcast + addressed_by", step2_messages_columns),
    (STEP3, "честный курсор отрезками", step3_cursor_segments),
    (STEP4, "треды: ответ связан с вопросом полем", step4_message_thread),
    (STEP5, "критерий «готово» + связь записки с задачей", step5_task_criterion),
    (STEP6, "номер версии вычисляется, старый снят надгробием", step6_schema_version),
    (STEP7, "подсветка карточек без критерия приёмки", step7_criterion_view),
]


# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description="Перевод базы мезосинка на новую структуру, по шагам")
    ap.add_argument("--db", required=True, help="путь к базе (копия/песочница; живая — только с флагом)")
    ap.add_argument("--step", help="выполнить один шаг по имени (по умолчанию — все невыполненные)")
    ap.add_argument("--dry", action="store_true", help="сухой прогон: ничего не пишет, печатает что было бы")
    ap.add_argument("--status", action="store_true", help="показать, какие шаги уже выполнены")
    ap.add_argument(GUARD_FLAG, dest="allow_live", action="store_true",
                    help="снять защиту живой базы (только COORD и только по слову владельца)")
    args = ap.parse_args()

    con = open_db(args.db, args.allow_live)
    ensure_journal(con)

    if args.status:
        print("\nШАГИ:")
        for ver, title, _ in STEPS:
            row = con.execute("SELECT applied_at FROM schema_migrations WHERE version=?", (ver,)).fetchone()
            print(f"  {'✅' if row else '⬜'} {ver:<40} {title}"
                  + (f"   ({row[0]} UTC)" if row else ""))
        return 0

    todo = [s for s in STEPS if not args.step or s[0] == args.step]
    if args.step and not todo:
        sys.exit(f"⛔ нет такого шага: {args.step}. Есть: {[s[0] for s in STEPS]}")

    print(f"\n{'СУХОЙ ПРОГОН — ничего не пишется' if args.dry else 'ВЫПОЛНЕНИЕ'}\n" + "─" * 78)
    for ver, title, fn in todo:
        if is_done(con, ver) and not args.dry:
            print(f"⏭  {ver} — уже выполнен, пропуск")
            continue
        print(f"\n▶ {ver} — {title}")
        report = fn(con, args.dry)
        for k, v in report.items():
            print(f"    {k}: {v}")
        if not args.dry:
            mark_done(con, ver, title)
            print(f"    ✅ записан в журнал шагов")
    if not args.dry:
        print(f"\n🔢 РУБЕЖ ВЕРСИИ: {declare_milestone(con)}")
    con.close()
    print("\n" + "─" * 78)
    print("Отчёт — ЧИСЛА до и после, а не слово «готово»: «готово» проверить нельзя, числа можно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
