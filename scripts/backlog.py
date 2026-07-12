"""
backlog.py — durable per-role backlog (переживает перезапуск агента). Фаза B1: базовый CRUD.

Первое на пробуждении роли:
    python backlog.py list --db mezosync.db --role CORE        # мои открытые задачи + SHARED

Создание / работа:
    python backlog.py add --db mezosync.db --role CORE --title "prov-reject-events" \
        --body-file note.md --priority high --tags "prov,F"
    python backlog.py show   --db mezosync.db 3
    python backlog.py status --db mezosync.db 3 in_progress --actor CORE --note "взял в работу"
    python backlog.py comment --db mezosync.db 3 --actor CORE --body-file update.md
    python backlog.py list --db mezosync.db --role CORE --status all   # включая закрытые

Rich-md подаётся через --body/--body-file и --note/--note-file.
Тесты (test-add/test-run/test-result) — фаза B2, здесь нет.
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

STATUSES = ["open", "in_progress", "blocked", "in_review", "done", "dropped"]
OPEN_STATUSES = ["open", "in_progress", "blocked", "in_review"]
PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def utc_to_local(s):
    if not s:
        return "—"
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return s


def _text(inline, file_arg):
    if file_arg:
        return Path(file_arg).read_text(encoding="utf-8")
    return inline or ""


def _conn(db):
    p = Path(db)
    if not p.exists():
        print(f"ERR: БД не найдена: {p}", file=sys.stderr)
        sys.exit(1)
    c = sqlite3.connect(str(p), timeout=5)
    c.execute("PRAGMA busy_timeout=5000")
    return c


def _event(conn, bid, actor, etype, body="", frm=None, to=None):
    conn.execute(
        "INSERT INTO backlog_events (backlog_id, actor_role, event_type, from_status, to_status, body_md) "
        "VALUES (?,?,?,?,?,?)", (bid, actor.upper(), etype, frm, to, body))


def cmd_add(conn, a):
    body = _text(a.body, a.body_file)
    tags = json.dumps([t.strip() for t in a.tags.split(",") if t.strip()], ensure_ascii=False)
    cur = conn.execute(
        "INSERT INTO backlog (role, title, body_md, priority, tags, parent_id, parent_track, created_by) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (a.role.upper(), a.title, body, a.priority, tags, a.parent, a.track, (a.actor or a.role).upper()))
    bid = cur.lastrowid
    _event(conn, bid, a.actor or a.role, "created", f"created: {a.title}", None, "open")
    conn.commit()
    print(f"✅ backlog #{bid} [{a.role.upper()}] «{a.title}» ({a.priority}, open)")


def cmd_list(conn, a):
    if a.status == "all":
        where_status, params = "1=1", []
    elif a.status == "open":
        where_status = f"status IN ({','.join('?' * len(OPEN_STATUSES))})"
        params = list(OPEN_STATUSES)
    else:
        where_status, params = "status = ?", [a.status]

    roles = [a.role.upper()]
    if not a.only_mine:
        roles.append("SHARED")
    where_role = f"role IN ({','.join('?' * len(roles))})"
    params = roles + params

    rows = conn.execute(
        f"SELECT id, role, title, status, priority, tags FROM backlog "
        f"WHERE {where_role} AND {where_status}", params).fetchall()
    rows.sort(key=lambda r: (PRIORITY_ORDER.get(r[4], 9), r[0]))

    if not rows:
        print(f"📭 [{a.role.upper()}] backlog пуст (status={a.status}).")
        return
    print(f"📋 backlog [{a.role.upper()}{'' if a.only_mine else ' + SHARED'}] — {len(rows)} задач (status={a.status})\n")
    icon = {"open": "○", "in_progress": "◐", "blocked": "⛔", "in_review": "👀", "done": "✅", "dropped": "✗"}
    for bid, role, title, status, prio, tags in rows:
        pr = {"critical": "‼️", "high": "⬆️", "normal": "·", "low": "⬇️"}.get(prio, "·")
        tg = " ".join(f"#{t}" for t in json.loads(tags or "[]"))
        shared = " (SHARED)" if role == "SHARED" else ""
        print(f"  #{bid} {icon.get(status,'?')} {pr} {title}{shared}  {tg}")


def cmd_show(conn, a):
    row = conn.execute(
        "SELECT id, role, title, body_md, status, priority, tags, parent_id, parent_track, "
        "blocked_reason, created_by, created_at, updated_at FROM backlog WHERE id = ?", (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    (bid, role, title, body, status, prio, tags, parent, track, blocked, cby, cat, uat) = row
    print(f"# backlog #{bid} — {title}")
    print(f"роль: {role} · статус: {status} · приоритет: {prio} · теги: {', '.join(json.loads(tags or '[]')) or '—'}")
    if parent: print(f"родитель: #{parent}")
    if track: print(f"трек: {track}")
    if blocked: print(f"⛔ причина блокировки: {blocked}")
    print(f"создал: {cby} @ {utc_to_local(cat)} · обновлён: {utc_to_local(uat)}")
    print(f"\n{body or '(нет описания)'}\n")

    tests = conn.execute(
        "SELECT id, title, method, status FROM backlog_tests WHERE backlog_id = ? ORDER BY id", (a.id,)).fetchall()
    if tests:
        print("## Тесты")
        for tid, tt, method, tstatus in tests:
            print(f"  [{tstatus}] ({method}) {tt}  (test #{tid})")
        print()

    print("## История")
    for at, actor, etype, frm, to, ebody in conn.execute(
            "SELECT at, actor_role, event_type, from_status, to_status, body_md "
            "FROM backlog_events WHERE backlog_id = ? ORDER BY id", (a.id,)):
        arrow = f" {frm}→{to}" if etype == "status_change" else ""
        extra = f" — {ebody}" if ebody else ""
        print(f"  {utc_to_local(at)} [{actor}] {etype}{arrow}{extra}")


def cmd_status(conn, a):
    if a.new_status not in STATUSES:
        print(f"ERR: статус должен быть из {STATUSES}", file=sys.stderr)
        sys.exit(1)
    row = conn.execute("SELECT status FROM backlog WHERE id = ?", (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    old = row[0]
    note = _text(a.note, a.note_file)
    blocked_reason = note if a.new_status == "blocked" else None
    conn.execute(
        "UPDATE backlog SET status = ?, blocked_reason = ?, updated_at = datetime('now') WHERE id = ?",
        (a.new_status, blocked_reason, a.id))
    _event(conn, a.id, a.actor, "status_change", note, old, a.new_status)
    conn.commit()
    print(f"✅ backlog #{a.id}: {old} → {a.new_status}" + (f" ({note})" if note else ""))


def cmd_comment(conn, a):
    row = conn.execute("SELECT id FROM backlog WHERE id = ?", (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    body = _text(a.body, a.body_file)
    if not body.strip():
        print("ERR: пустой комментарий", file=sys.stderr)
        sys.exit(1)
    _event(conn, a.id, a.actor, "comment", body)
    conn.execute("UPDATE backlog SET updated_at = datetime('now') WHERE id = ?", (a.id,))
    conn.commit()
    print(f"✅ комментарий добавлен к backlog #{a.id}")


def main():
    p = argparse.ArgumentParser(description="Durable per-role backlog (B1 CRUD)")
    p.add_argument("--db", required=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add")
    pa.add_argument("--role", required=True)
    pa.add_argument("--title", required=True)
    pa.add_argument("--body", default="")
    pa.add_argument("--body-file", dest="body_file")
    pa.add_argument("--priority", default="normal", choices=["low", "normal", "high", "critical"])
    pa.add_argument("--tags", default="")
    pa.add_argument("--parent", type=int)
    pa.add_argument("--track")
    pa.add_argument("--actor")

    pl = sub.add_parser("list")
    pl.add_argument("--role", required=True)
    pl.add_argument("--status", default="open", help="open|all|<конкретный статус>")
    pl.add_argument("--only-mine", action="store_true", dest="only_mine", help="без SHARED")

    ps = sub.add_parser("show")
    ps.add_argument("id", type=int)

    pt = sub.add_parser("status")
    pt.add_argument("id", type=int)
    pt.add_argument("new_status")
    pt.add_argument("--actor", required=True)
    pt.add_argument("--note", default="")
    pt.add_argument("--note-file", dest="note_file")

    pc = sub.add_parser("comment")
    pc.add_argument("id", type=int)
    pc.add_argument("--actor", required=True)
    pc.add_argument("--body", default="")
    pc.add_argument("--body-file", dest="body_file")

    a = p.parse_args()
    conn = _conn(a.db)
    {"add": cmd_add, "list": cmd_list, "show": cmd_show,
     "status": cmd_status, "comment": cmd_comment}[a.cmd](conn, a)
    conn.close()


if __name__ == "__main__":
    main()
