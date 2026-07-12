"""
check-errors.py — COORD: быстрый сбор ошибок двойной записи от всех коллег.

Использование:
    python check-errors.py --db .mezosync/mezosync.db
    python check-errors.py --db .mezosync/mezosync.db --resolve 5 7
    python check-errors.py --db .mezosync/mezosync.db --stats
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path


def utc_to_local(s):
    """Метки БД в UTC → показываем локальное (DST-safe)."""
    if not s:
        return "—"
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return s


def main():
    parser = argparse.ArgumentParser(description="Сбор и разрешение ошибок двойной записи")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--resolve", nargs="+", type=int, metavar="ID",
                        help="Пометить сообщения как resolved (COORD подтвердил фикс)")
    parser.add_argument("--stats", action="store_true",
                        help="Статистика: сколько ошибок по ролям, resolved/open")
    args = parser.parse_args()

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

    print(f"Разрешить: python check-errors.py --db <path> --resolve {' '.join(str(r[0]) for r in rows)}")


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
