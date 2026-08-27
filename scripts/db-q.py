#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db-q — запросник ТОЛЬКО ДЛЯ ЧТЕНИЯ, чей отказ сам подсказывает настоящие имена.

    python <КОНТУР>/.mezosync/scripts/db-q.py "SELECT role, lifecycle FROM roles WHERE lifecycle='alive'"

(Форма вызова — АБСОЛЮТНЫМ путём, без --db: база резолвится от расположения скрипта.
Голое имя в справке уже однажды учило форме, которая при уехавшем CWD молча попадает
не туда — заявка @STUD, записка #3559.)

ПОВОД (план 3, этап 1; замер 14.08). За одну смену имя колонки было УГАДАНО трижды
(role в messages · addressee · role в read_cursors) — и каждый раз лечение одно: PRAGMA.
Урок «спрашивай, не помни» не работает, пока спросить = писать python с угадыванием имён.
Здесь подсказка живёт В ОТКАЗЕ: не дисциплиной — устройством.

· «no such column» → печатаются НАСТОЯЩИЕ колонки всех таблиц запроса;
· «no such table»  → печатается список таблиц базы;
· пишущий запрос   → отказ ДО исполнения + база под PRAGMA query_only (двойной затвор);
· хвост длиннее --limit строк обрезается, и обрезание НАЗВАНО вслух, не молчит.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

import mezo_paths

READONLY_HEADS = ("SELECT", "WITH", "PRAGMA", "EXPLAIN", "VALUES")


def tables_of(sql: str) -> list[str]:
    # Имена после FROM/JOIN — для подсказки, не для валидации: промах здесь не страшен.
    return re.findall(r"(?:FROM|JOIN)\s+['\"`]?([A-Za-z_][A-Za-z0-9_]*)", sql, re.I)


def hint(con: sqlite3.Connection, sql: str, err: str) -> None:
    print(f"⛔ {err}", file=sys.stderr)
    if "no such column" in err:
        for t in dict.fromkeys(tables_of(sql)):
            try:
                cols = [c[1] for c in con.execute(f"PRAGMA table_info('{t}')")]
            except sqlite3.Error:
                cols = []
            if cols:
                print(f"   настоящие колонки {t}: {', '.join(cols)}", file=sys.stderr)
            else:
                print(f"   таблицы {t} нет — список таблиц ниже", file=sys.stderr)
                err = "no such table"  # провалиться в подсказку списком
    if "no such table" in err:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        print(f"   таблицы базы: {', '.join(names)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="читающий запрос к mezosync.db; отказ подсказывает имена")
    ap.add_argument("sql", help="один SELECT/PRAGMA-запрос")
    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--limit", type=int, default=200, help="строк в выводе (обрезание называется вслух)")
    a = ap.parse_args()

    head = (a.sql.strip().split(None, 1) or [""])[0].upper().rstrip("(")
    if head not in READONLY_HEADS:
        print(f"⛔ это ПИШУЩИЙ запрос ({head or 'пусто'}) — db-q только читает.\n"
              f"   Писать в базу — штатными инструментами (backlog.py, write-message.py, "
              f"save-phoenix.py): у них проверки и журнал, у сырого SQL — нет.", file=sys.stderr)
        return 2

    db = mezo_paths.resolve_db(a.db, __file__)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        cur = con.execute(a.sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(a.limit + 1)
    except sqlite3.Error as e:
        hint(con, a.sql, str(e))
        return 1
    if cols:
        print("\t".join(cols))
    for r in rows[:a.limit]:
        print("\t".join("∅" if v is None else str(v) for v in r))
    if len(rows) > a.limit:
        print(f"⚠️ показано {a.limit} строк, ЕСТЬ ЕЩЁ — сузь запрос или подними --limit "
              f"(обрезание названо, не молчит)", file=sys.stderr)
    print(f"── строк: {min(len(rows), a.limit)} · база: {db.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
