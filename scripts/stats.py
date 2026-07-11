"""
stats.py — снимок статистики mezosync.db для COORD (периодический сбор).

Использование:
    python stats.py --db .mezosync/mezosync.db
    python stats.py --db .mezosync/mezosync.db --since-min 50   # активность за окно
    python stats.py --db .mezosync/mezosync.db --json           # машинный вывод
    python stats.py --db .mezosync/mezosync.db --record         # + записать снимок в stats_log

Ничего не мутирует в messages/rules/phoenix. С --record добавляет строку в
служебную таблицу stats_log (создаётся при первом вызове) — чтобы видеть динамику.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Снимок статистики mezosync.db")
    p.add_argument("--db", required=True)
    p.add_argument("--since-min", type=int, default=50, help="Окно активности, минут")
    p.add_argument("--json", action="store_true", help="Машинный JSON вместо таблицы")
    p.add_argument("--record", action="store_true", help="Записать снимок в stats_log")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")

    s = collect(conn, args.since_min)

    if args.record:
        _record(conn, s)

    conn.close()

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        _print_human(s, args.since_min)


def _q1(conn, sql, params=()):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def collect(conn, since_min):
    win = f"-{int(since_min)} minutes"

    group = _q1(conn, "SELECT value FROM meta WHERE key='group_name'") or "?"
    total_msg = _q1(conn, "SELECT COUNT(*) FROM messages") or 0
    roles = _q1(conn, "SELECT COUNT(DISTINCT writer_role) FROM messages") or 0
    rules = _q1(conn, "SELECT COUNT(*) FROM rules") or 0

    recent = _q1(conn,
        "SELECT COUNT(*) FROM messages WHERE timestamp >= datetime('now', ?)", (win,)) or 0

    # per-role: всего сообщений + время последней ноты (liveness)
    per_role = {}
    try:
        for role, cnt, last in conn.execute(
            "SELECT writer_role, COUNT(*), MAX(timestamp) FROM messages GROUP BY writer_role ORDER BY writer_role"):
            per_role[role] = {"messages": cnt, "last": last}
    except sqlite3.OperationalError:
        pass

    # ошибки двойной записи
    dwerr_open = _q1(conn,
        "SELECT COUNT(*) FROM messages WHERE tags LIKE '%\"DWERR\"%' AND (resolved IS NULL OR resolved=0)") or 0
    dwerr_total = _q1(conn, "SELECT COUNT(*) FROM messages WHERE tags LIKE '%\"DWERR\"%'") or 0

    # phoenix-слепки
    phoenix_cnt = _q1(conn, "SELECT COUNT(*) FROM phoenix") or 0

    # курсоры чтения — отставание ролей
    cursors = {}
    try:
        max_id = _q1(conn, "SELECT MAX(id) FROM messages") or 0
        for role, lr in conn.execute("SELECT reader_role, last_read_id FROM read_cursors ORDER BY reader_role"):
            cursors[role] = {"read": lr, "behind": max_id - lr}
    except sqlite3.OperationalError:
        pass

    return {
        "group": group,
        "totals": {"messages": total_msg, "roles": roles, "rules": rules, "phoenix": phoenix_cnt},
        "recent_messages": recent,
        "per_role": per_role,
        "dwerr": {"open": dwerr_open, "total": dwerr_total},
        "cursors": cursors,
    }


def _record(conn, s):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL DEFAULT (datetime('now')),
            snapshot_json TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO stats_log (snapshot_json) VALUES (?)",
                 (json.dumps(s, ensure_ascii=False),))
    conn.commit()


def _print_human(s, since_min):
    t = s["totals"]
    print(f"📊 Группа: {s['group']}")
    print(f"   Сообщений: {t['messages']}  ·  Ролей: {t['roles']}  ·  Правил: {t['rules']}  ·  Phoenix: {t['phoenix']}")
    print(f"   Новых за {since_min} мин: {s['recent_messages']}")
    d = s["dwerr"]
    mark = "⚠️" if d["open"] else "✅"
    print(f"   Ошибки DWERR: {mark} open={d['open']} / total={d['total']}")
    print()
    print(f"   {'Роль':<8} {'Сообщ':>6} {'Отставание':>11}  Последняя нота")
    print("   " + "-" * 52)
    # writer_role бывает в верхнем регистре, reader_role — в нижнем; сливаем по UPPER.
    per_role = {k.upper(): v for k, v in s["per_role"].items()}
    cursors = {k.upper(): v for k, v in s["cursors"].items()}
    for r in sorted(set(per_role) | set(cursors)):
        pr = per_role.get(r, {})
        cur = cursors.get(r, {})
        msgs = pr.get("messages", 0)
        last = pr.get("last") or "—"
        behind = cur.get("behind", "—")
        print(f"   {r:<8} {msgs:>6} {str(behind):>11}  {last}")


if __name__ == "__main__":
    main()
