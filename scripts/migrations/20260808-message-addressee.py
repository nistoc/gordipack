#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
МИГРАЦИЯ: адресат записки становится ПОЛЕМ, а не прозой в теле.

СЛОВО ВЛАДЕЛЬЦА 2026-08-08 11:50 UTC: «сделай адресата полем».

ЧТО БЫЛО (замер 11:50 UTC, живая база):
    таблицы адресатов ......... НЕТ ВОВСЕ
    ручка --to ................ ПРИНИМАЕТ имя и ВЫБРАСЫВАЕТ его: ставит лишь метку
                                addressed_by='field' (129 записок), список — в теле
    поле broadcast ............ 0 у ВСЕХ 1975 записок — третий мёртвый сосуд рядом
⇒ Признак завезли, сосуд под имена — нет. Роль, читающая указатель вместо тел, отличает
обращение от вежливой копии ДОГАДКОЙ по первой строке.

ЦЕНА, ЗАМЕРЕННАЯ НА СЕБЕ: из 145 чужих записок роль названа в 132, а ОБРАЩАЮТСЯ к ней
в 24 — шестикратная переплата чтения при каждом пробуждении. У роли с длинным хвостом
415 записок долга и 16 личных обращений, о которых её память молчит.

ЧТО ДЕЛАЕТ МИГРАЦИЯ — ТОЛЬКО ДОБАВЛЯЕТ:
    CREATE TABLE message_addressee (message_id, role, kind, linked_by)
      kind ....... 'to' (обращение) | 'cc' (в копию). Различие — весь смысл затеи
      linked_by .. 'field' (объявлено ручкой) | 'backfill' (разобрано из прозы)
⛔ Тел записок НЕ ТРОГАЕТ. Существующих колонок НЕ МЕНЯЕТ. Данных не удаляет.
⛔ Обратного заполнения ЗДЕСЬ НЕТ намеренно: разбор прозы — отдельный ход с отдельным
   разрешением, и его результат обязан быть помечен 'backfill', иначе догадка выдаст
   себя за объявленное.

ИДЕМПОТЕНТНА: IF NOT EXISTS, повторный прогон ничего не портит.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS message_addressee (
    message_id INTEGER NOT NULL REFERENCES messages(id),
    role       TEXT    NOT NULL,
    kind       TEXT    NOT NULL CHECK (kind IN ('to','cc')),
    linked_by  TEXT    NOT NULL DEFAULT 'field'
                       CHECK (linked_by IN ('field','backfill')),
    PRIMARY KEY (message_id, role, kind)
);
CREATE INDEX IF NOT EXISTS idx_addressee_role ON message_addressee(role, kind);
CREATE INDEX IF NOT EXISTS idx_addressee_msg  ON message_addressee(message_id);
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="адресат записки — полем (только добавляет)")
    ap.add_argument("--db", required=True, help="путь к базе; на живой — только после копии")
    args = ap.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f"⛔ базы нет: {db}")

    conn = sqlite3.connect(f"file:{str(db).replace(chr(92), '/')}?mode=rw", uri=True, timeout=10)

    before = {t for t, in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    msgs_before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    conn.executescript(DDL)
    conn.commit()

    after = {t for t, in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    msgs_after = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    rows = conn.execute("SELECT COUNT(*) FROM message_addressee").fetchone()[0]
    conn.close()

    print("=" * 70)
    print("МИГРАЦИЯ: адресат полем")
    print("=" * 70)
    print(f"таблиц было ......... {len(before)}   стало {len(after)}")
    print(f"добавлено ........... {', '.join(sorted(after - before)) or '— (уже было)'}")
    print(f"удалено ............. {', '.join(sorted(before - after)) or 'ничего ✅'}")
    print(f"записок ............. {msgs_before} → {msgs_after}"
          f"   {'✅ не тронуты' if msgs_before == msgs_after else '🔴 ИЗМЕНИЛОСЬ'}")
    print(f"строк адресатов ..... {rows}   (обратного заполнения здесь НЕТ — отдельный ход)")
    print(f"целостность ......... {integrity}")
    ok = (msgs_before == msgs_after) and integrity == "ok" and not (before - after)
    print()
    print("✅ ПРОШЛА" if ok else "🔴 НЕ ПРОШЛА — откатывай из точки отката")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
