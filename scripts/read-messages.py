"""
read-messages.py — CLI для агента: прочитать непрочитанные сообщения из mezosync.db.

Использование агентом (из Bash tool):
    python read-messages.py --db .mezosync/mezosync.db --role COORD
    python read-messages.py --db .mezosync/mezosync.db --role CORE --limit 20
    python read-messages.py --db .mezosync/mezosync.db --role STUD --tag TRACK-NEWUX
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
    parser = argparse.ArgumentParser(description="Прочитать непрочитанные сообщения")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--role", required=True, help="Роль читателя (для курсора)")
    parser.add_argument("--limit", type=int, default=50, help="Максимум сообщений")
    parser.add_argument("--tag", default=None, help="Фильтр по тегу")
    parser.add_argument("--all", action="store_true", help="Все сообщения (игнорировать курсор)")
    parser.add_argument("--no-advance", action="store_true", help="Не двигать курсор")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=5)

    # Получить курсор
    cursor_row = conn.execute(
        "SELECT last_read_id FROM read_cursors WHERE reader_role = ?", (args.role,)
    ).fetchone()

    if cursor_row is None:
        conn.execute(
            "INSERT INTO read_cursors (reader_role, last_read_id) VALUES (?, 0)", (args.role,)
        )
        conn.commit()
        last_read = 0
    else:
        last_read = cursor_row[0]

    # Запрос
    if args.all:
        sql = "SELECT id, writer_role, timestamp, body_md, tags, priority FROM messages"
        params = []
        conditions = []
    else:
        conditions = ["id > ?"]
        params = [last_read]

    if args.tag:
        conditions.append("tags LIKE ?")
        params.append(f'%"{args.tag}"%')

    sql = "SELECT id, writer_role, timestamp, body_md, tags, priority FROM messages"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += f" ORDER BY id ASC LIMIT {args.limit}"

    rows = conn.execute(sql, params).fetchall()

    if not rows:
        print(f"[{args.role}] Нет непрочитанных сообщений (cursor={last_read})")
        conn.close()
        return

    max_id = last_read
    for row in rows:
        msg_id, writer, ts, body, tags, priority = row
        max_id = max(max_id, msg_id)
        prio_mark = "" if priority == "normal" else f" ⚠️{priority}"
        tags_list = json.loads(tags) if tags else []
        tags_str = " ".join(f"[{t}]" for t in tags_list)
        print(f"--- #{msg_id} [{writer}] {utc_to_local(ts)}{prio_mark} {tags_str}")
        print(body)
        print()

    # Двинуть курсор
    if not args.no_advance and not args.all and max_id > last_read:
        conn.execute(
            "UPDATE read_cursors SET last_read_id = ?, updated_at = datetime('now') WHERE reader_role = ?",
            (max_id, args.role)
        )
        conn.commit()
        print(f"[cursor] {args.role}: {last_read} → {max_id} ({len(rows)} сообщений)")

    conn.close()


if __name__ == "__main__":
    main()
