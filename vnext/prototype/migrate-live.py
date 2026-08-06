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
import sqlite3
import sys

LIVE_DB = pathlib.Path(r"C:\guts\.atlas\.mezosync\mezosync.db")
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

    before = con.execute("SELECT COUNT(*) FROM roles").fetchone()[0] if table_exists(con, "roles") else 0

    if not dry:
        con.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                role        TEXT PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'dormant', 'closed')),
                seen_in     TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )""")
        con.executemany(
            "INSERT OR IGNORE INTO roles (role, seen_in) VALUES (?,?)",
            [(r, ",".join(sorted(s))) for r, s in sorted(found.items())])
        con.commit()

    after = con.execute("SELECT COUNT(*) FROM roles").fetchone()[0] if table_exists(con, "roles") else 0
    # регистровые двойники — называем, а не чиним: чинить = менять данные, чего владелец не просил
    lower = {}
    for r in found:
        lower.setdefault(r.lower(), []).append(r)
    dupes = {k: v for k, v in lower.items() if len(v) > 1}
    return {"найдено ролей": len(found), "было": before, "стало": after,
            "регистровые двойники": dupes or "нет", "состав": sorted(found)}


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


STEPS = [
    (STEP1, "реестр ролей (опора для пяти таблиц)", step1_roles),
    (STEP2, "messages: broadcast + addressed_by", step2_messages_columns),
    (STEP3, "честный курсор отрезками", step3_cursor_segments),
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
    con.close()
    print("\n" + "─" * 78)
    print("Отчёт — ЧИСЛА до и после, а не слово «готово»: «готово» проверить нельзя, числа можно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
