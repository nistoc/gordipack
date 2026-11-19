# -*- coding: utf-8 -*-
"""20261118-read-batches-columns — ДВЕ КОЛОНКИ ТАБЛИЦЫ ВЫДАЧ ЛЕНТЫ ЗАВОДИТ ШАГ СХЕМЫ, А НЕ ЧТЕНИЕ
(карточка #510).

ЧТО БОЛЕЛО. Колонки read_batches.shown_max и read_batches.acked_at добавляло само чтение ленты
(read-messages.py) при первом вызове — правкой схемы на ходу, без строки в журнале схемы. Шаг
20260809-batch-race-lock строит по acked_at частичный индекс: колонку он предполагает, но не
заводит. Были колонки в базе или нет, зависело от того, что позвали раньше — чтение ленты или
шаг. Второй потребитель пакета наткнулся на это честным путём: его шаг упал на базе, где
чтение ленты ещё ни разу не звали.

ЧТО ДЕЛАЕТ ШАГ:
  · таблицы read_batches нет ............ заводит её целиком, шесть колонок;
  · таблица есть, колонок не хватает .... добавляет недостающие из двух (shown_max, acked_at);
  · обе колонки на месте ................ структуру не трогает (их принёс файл схемы либо
                                          прежнее чтение ленты);
  · во всех трёх случаях записывает себя в журнал схемы, если строки там ещё нет: с неё у
    колонок есть след, откуда они взялись.
Строк таблицы шаг не трогает и не удаляет.

ПОРЯДОК НА СТАРОЙ БАЗЕ: если колонки acked_at нет, этот шаг идёт ПЕРЕД 20260809-batch-race-lock
(тот теперь отказывает словами и называет этот шаг).

ИДЕМПОТЕНТЕН: колонки на месте и строка в журнале есть — «уже сведено», база не меняется.
--dry-run ничего не пишет.
КОДЫ ВЫХОДА: 0 — применено или уже сведено · 1 — применение не сошлось с проверкой, база
возвращена к состоянию до шага · 2 — не запустился (нет файла базы, не база, нет журнала схемы).
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import precheck, record_step  # noqa: E402

VERSION = "20261118-read-batches-columns"
TABLE = "read_batches"

# Полный вид таблицы — тот же, что несёт файл схемы пакета начиная с v3.
CREATE_TABLE = (
    "CREATE TABLE read_batches ("
    "  token     TEXT PRIMARY KEY,"
    "  role      TEXT NOT NULL,"
    "  last_id   INTEGER NOT NULL,"
    "  issued_at TEXT NOT NULL DEFAULT (datetime('now')),"
    # shown_max — сколько записок фактически показано этой выдачей
    "  shown_max INTEGER,"
    # acked_at — час подтверждения; строка остаётся следом, а не стирается
    "  acked_at  TEXT)")

# Две колонки, которые прежде добавляло чтение ленты.
COLUMNS = (("shown_max", "INTEGER"), ("acked_at", "TEXT"))


def survey(conn):
    """→ (таблица есть, каких колонок из двух нет, строка шага в журнале есть)."""
    have = [r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")]
    missing = [name for name, _ in COLUMNS if name not in have]
    journaled = conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?",
                             (VERSION,)).fetchone() is not None
    return bool(have), missing, journaled


def row_count(conn):
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]


def main():
    ap = argparse.ArgumentParser(
        description="шаг схемы: колонки shown_max и acked_at таблицы read_batches")
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true',
                    help='показать, что будет сделано; база не меняется')
    args = ap.parse_args()

    db = os.path.abspath(args.db)
    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if args.dry_run else ""}')
    print(f'📂 БАЗА: {db}')
    print('=' * 78)
    refusal = precheck(db)
    if refusal:
        print(refusal)
        return 2

    conn = sqlite3.connect(db, timeout=10)
    has_table, missing, journaled = survey(conn)
    print(f'таблица {TABLE} ....... {"есть" if has_table else "НЕТ — шаг заведёт её целиком"}')
    for name, _decl in COLUMNS:
        if not has_table:
            state = "придёт вместе с таблицей"
        elif name in missing:
            state = "НЕТ — шаг добавит"
        else:
            state = "есть"
        print(f'колонка {name:<10} ......... {state}')
    print(f'строка шага в журнале схемы ... {"есть" if journaled else "НЕТ — шаг запишет"}')

    if has_table and not missing and journaled:
        conn.close()
        print('\n✅ уже сведено — обе колонки на месте, строка в журнале схемы есть. Делать нечего')
        return 0
    if args.dry_run:
        conn.close()
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return 0

    rows_before = row_count(conn) if has_table else 0
    # Явная транзакция: правка схемы и строка журнала ложатся вместе либо не ложатся вовсе.
    conn.execute("BEGIN IMMEDIATE")
    if not has_table:
        conn.execute(CREATE_TABLE)
        done = f"таблица {TABLE} заведена целиком"
    elif missing:
        for name, decl in COLUMNS:
            if name in missing:
                conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {name} {decl}")
        done = "добавлены колонки: " + ", ".join(missing)
    else:
        done = "колонки уже были (файл схемы либо прежнее чтение ленты) — записан след"
    _has_table, still_missing, _journaled = survey(conn)
    rows_after = row_count(conn)
    if still_missing or rows_after != rows_before:
        conn.rollback()
        conn.close()
        print(f'\n🔴 НЕ ПРИМЕНЕНО: после правки не сошлось — колонок нет: '
              f'{", ".join(still_missing) or "—"} · строк таблицы {rows_before} → {rows_after}. '
              f'База возвращена к состоянию до шага')
        return 1
    fp = record_step(conn, VERSION,
                     f"read_batches.shown_max и read_batches.acked_at заводит шаг схемы, а не "
                     f"чтение ленты: {done}. Карточка #510")
    conn.commit()
    conn.close()
    print(f'\n✅ ПРИМЕНЕНО. {done} · строк таблицы {rows_before} → {rows_after} · '
          f'отпечаток схемы: {fp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
