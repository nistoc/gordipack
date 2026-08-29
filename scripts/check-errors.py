"""
check-errors.py — COORD: быстрый сбор ошибок двойной записи от всех коллег.

Использование (АБСОЛЮТНЫЙ путь; `--db` не нужен — R15a, норма 26.07):
    python <КОНТУР>/.mezosync/scripts/check-errors.py
    python <КОНТУР>/.mezosync/scripts/check-errors.py --resolve 5 7
    python <КОНТУР>/.mezosync/scripts/check-errors.py --stats
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD


# карточка #384 (слово владельца 29.08.2026): показ «UTC (местное)» вернулся — но ОДНИМ
# местом, модулем local_time.py (зона host OS на дату записи; хранение — только UTC).
# Прежнее надгробие «конвертации больше нет» снято тем же словом; разбор — в модуле.
try:
    from local_time import utc_to_local
except Exception:  # noqa: BLE001 — без модуля разбор живёт: прежний показ «только UTC»
    def utc_to_local(s, tz=None):
        return f"{s} UTC" if s else "—"

def main():
    parser = argparse.ArgumentParser(description="Сбор и разрешение ошибок двойной записи")
    # R15a довезён 27.07 (мой docstring уже обещал «--db не нужен» — обещание без механизма = ложь).
    parser.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    parser.add_argument("--resolve", nargs="+", type=int, metavar="ID",
                        help="Пометить сообщения как resolved (COORD подтвердил фикс)")
    parser.add_argument("--stats", action="store_true",
                        help="Статистика: сколько ошибок по ролям, resolved/open")
    args = parser.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта, не от CWD

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    _ensure_resolved_column(conn)

    if args.resolve:
        _resolve(conn, args.resolve)
    elif args.stats:
        _stats(conn)
    else:
        _show_open(conn)

    conn.close()


def _ensure_resolved_column(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "resolved" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN resolved INTEGER DEFAULT 0")
        conn.commit()


def _show_open(conn):
    rows = conn.execute("""
        SELECT id, writer_role, timestamp, body_md, tags, priority
        FROM messages
        WHERE tags LIKE '%"DWERR"%' AND (resolved IS NULL OR resolved = 0)
        ORDER BY id ASC
    """).fetchall()

    if not rows:
        print("✅ Нет открытых ошибок двойной записи (DWERR).")
        return

    print(f"⚠️  {len(rows)} открытых ошибок:\n")
    for row in rows:
        msg_id, writer, ts, body, tags, priority = row
        tags_list = json.loads(tags) if tags else []
        tags_str = " ".join(f"[{t}]" for t in tags_list)
        prio_mark = "" if priority == "normal" else f" ⚠️{priority}"
        print(f"  #{msg_id} [{writer}] {utc_to_local(ts)}{prio_mark} {tags_str}")
        print(f"    {body[:200]}")
        print()

    # Путь СВОЙСТВОМ, без --db (R15a, @STUD #2864 — рабочий вывод учит сильнее docstring).
    print(f"Разрешить: python {Path(__file__).resolve().as_posix()} --resolve {' '.join(str(r[0]) for r in rows)}")


def _resolve(conn, ids):
    for msg_id in ids:
        cur = conn.execute(
            "UPDATE messages SET resolved = 1 WHERE id = ? AND tags LIKE '%\"DWERR\"%'",
            (msg_id,)
        )
        if cur.rowcount:
            print(f"  ✅ #{msg_id} resolved")
        else:
            print(f"  ⚠️  #{msg_id} не найден или не DWERR")
    conn.commit()


def _stats(conn):
    rows = conn.execute("""
        SELECT writer_role,
               COUNT(*) as total,
               SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) as resolved,
               SUM(CASE WHEN resolved IS NULL OR resolved = 0 THEN 1 ELSE 0 END) as open
        FROM messages
        WHERE tags LIKE '%"DWERR"%'
        GROUP BY writer_role
        ORDER BY open DESC, total DESC
    """).fetchall()

    if not rows:
        print("✅ Ни одной ошибки DWERR не зарегистрировано.")
        return

    print(f"{'Роль':<10} {'Всего':>6} {'Open':>6} {'Fixed':>6}")
    print("-" * 30)
    total_all = total_open = total_fixed = 0
    for writer, total, fixed, open_cnt in rows:
        print(f"{writer:<10} {total:>6} {open_cnt:>6} {fixed:>6}")
        total_all += total
        total_open += open_cnt
        total_fixed += fixed
    print("-" * 30)
    print(f"{'ИТОГО':<10} {total_all:>6} {total_open:>6} {total_fixed:>6}")


if __name__ == "__main__":
    main()
