"""
read-broadcasts.py — общий канал: читать/подтверждать broadcast-объявления.

Broadcast = сообщение с тегом `ALL` в общей ленте `messages`.
Каждая роль каждый тик проверяет свой инбокс broadcast'ов одним запросом.

Использование:
    # мой инбокс: broadcast'ы, которые я ещё не видел (не мои, без моего ACK)
    python read-broadcasts.py --db mezosync.db --role CORE

    # подтвердить, что видел (для CTA — обязательно)
    python read-broadcasts.py --db mezosync.db --role CORE --ack 49 52

    # статус CTA: кто подтвердил, кто ещё нет (для автора/COORD)
    python read-broadcasts.py --db mezosync.db --status
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path


def utc_to_local(s):
    if not s:
        return "—"
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return s


def ensure_acks_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_acks (
            message_id INTEGER NOT NULL,
            role       TEXT NOT NULL,
            acked_at   TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (message_id, role)
        )
    """)
    conn.commit()


def is_broadcast(tags_json):
    try:
        return "ALL" in json.loads(tags_json or "[]")
    except (ValueError, TypeError):
        return False


def is_cta(tags_json):
    try:
        return "CTA" in json.loads(tags_json or "[]")
    except (ValueError, TypeError):
        return False


def main():
    p = argparse.ArgumentParser(description="Читать/подтверждать broadcast-объявления")
    p.add_argument("--db", required=True)
    p.add_argument("--role", help="Роль-читатель (для инбокса и ACK)")
    p.add_argument("--ack", nargs="+", type=int, metavar="ID", help="Подтвердить broadcast'ы")
    p.add_argument("--status", action="store_true", help="Статус CTA: кто ACK'нул, кто нет")
    p.add_argument("--all", action="store_true", help="Показать все broadcast'ы, не только непрочитанные")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    ensure_acks_table(conn)

    if args.status:
        _status(conn)
    elif args.ack:
        if not args.role:
            print("ERR: --ack требует --role", file=sys.stderr)
            sys.exit(1)
        _ack(conn, args.role, args.ack)
    else:
        if not args.role:
            print("ERR: инбокс требует --role (или используй --status)", file=sys.stderr)
            sys.exit(1)
        _inbox(conn, args.role, args.all)

    conn.close()


def _inbox(conn, role, show_all):
    rows = conn.execute(
        "SELECT id, writer_role, timestamp, body_md, tags, priority FROM messages ORDER BY id ASC"
    ).fetchall()
    acked = {r[0] for r in conn.execute(
        "SELECT message_id FROM broadcast_acks WHERE role = ?", (role,))}

    shown = []
    for mid, writer, ts, body, tags, prio in rows:
        if not is_broadcast(tags):
            continue
        if writer.upper() == role.upper():
            continue  # свои не показываем
        if not show_all and mid in acked:
            continue
        shown.append((mid, writer, ts, body, tags, prio))

    if not shown:
        print(f"📭 [{role}] Нет непрочитанных broadcast'ов.")
        return

    print(f"📣 [{role}] Broadcast'ов: {len(shown)}\n")
    cta_ids = []
    for mid, writer, ts, body, tags, prio in shown:
        cta = is_cta(tags)
        mark = "🔔CTA" if cta else "FYI"
        if cta:
            cta_ids.append(mid)
        seen = " (уже ACK)" if mid in acked else ""
        print(f"  #{mid} [{writer}] {utc_to_local(ts)} {mark}{seen}")
        print(f"    {body[:220]}")
        print()
    if cta_ids:
        print(f"⚠️ Есть CTA — подтверди: python read-broadcasts.py --db <path> --role {role} --ack {' '.join(map(str, cta_ids))}")


def _ack(conn, role, ids):
    for mid in ids:
        row = conn.execute("SELECT tags FROM messages WHERE id = ?", (mid,)).fetchone()
        if not row or not is_broadcast(row[0]):
            print(f"  ⚠️ #{mid} не broadcast — пропуск")
            continue
        conn.execute(
            "INSERT OR IGNORE INTO broadcast_acks (message_id, role) VALUES (?, ?)",
            (mid, role.upper()))
        print(f"  ✅ #{mid} ACK от {role.upper()}")
    conn.commit()


def _status(conn):
    # известные роли группы — из курсоров чтения (нормализуем к UPPER)
    roles = {r[0].upper() for r in conn.execute("SELECT reader_role FROM read_cursors")}
    ctas = [(mid, w, ts) for mid, w, ts, tags in conn.execute(
        "SELECT id, writer_role, timestamp, tags FROM messages ORDER BY id ASC") if is_cta(tags)]

    if not ctas:
        print("✅ Нет CTA-broadcast'ов.")
        return

    for mid, writer, ts in ctas:
        acked = {r[0].upper() for r in conn.execute(
            "SELECT role FROM broadcast_acks WHERE message_id = ?", (mid,))}
        expected = roles - {writer.upper()}  # автор себя не подтверждает
        pending = expected - acked
        status = "✅ ВСЕ" if not pending else f"⏳ ждём: {', '.join(sorted(pending))}"
        print(f"📣 CTA #{mid} [{writer}] {utc_to_local(ts)} — ACK: {', '.join(sorted(acked)) or '—'} · {status}")


if __name__ == "__main__":
    main()
