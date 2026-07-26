# -*- coding: utf-8 -*-
"""
write-message-vnext.py — ПРОТОТИП R15a на самом нагруженном CLI: запись ноты БЕЗ зависимости от CWD.

Демонстратор, не замена: тело живого `write-message.py` (ноты/--poll/--file/аварийный --md) здесь
намеренно сведено к минимуму — доказывается ОДНО свойство: путь к БД перестал зависеть от того,
где роль стояла в файловой системе минуту назад.

Разница с живым скриптом ровно в двух строках:
    живой:   ap.add_argument("--db", required=True) ... Path(args.db)
    здесь:   ap.add_argument("--db", default=None)  ... resolve_db(args.db, __file__)

⛔ Отказывается писать в живую БД: прототип работает по песочнице.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # хелпер лежит рядом со скриптом
from mezo_paths import resolve_db                           # noqa: E402

LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")


def main():
    ap = argparse.ArgumentParser(description="Записать ноту (прототип R15a)")
    ap.add_argument("--db", default=None,
                    help="необязателен: по умолчанию — БД рядом со скриптом (см. mezo_paths)")
    ap.add_argument("--role", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--priority", default="normal", choices=["normal", "high", "critical"])
    args = ap.parse_args()

    db = resolve_db(args.db, __file__)
    if db == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Прототип работает только по песочнице.")

    role = args.role.upper()          # R5: нормализация в одной точке входа
    tags = json.dumps([t.strip() for t in args.tags.split(",") if t.strip()], ensure_ascii=False)
    con = sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=5)
    cur = con.execute(
        "INSERT INTO messages (writer_role, body_md, tags, priority) VALUES (?,?,?,?)",
        (role, args.body, tags, args.priority))
    mid = cur.lastrowid
    con.commit()
    con.close()
    print(f"OK #{mid} [{role}] tags={tags} priority={args.priority}   (БД: {db})")


if __name__ == "__main__":
    main()
