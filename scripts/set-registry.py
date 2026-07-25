r"""
set-registry.py — писатель для реестровых таблиц mezosync.db: tracks, invariants,
backlog_tests, templates.

ЗАЧЕМ: 16.07 обнаружено системно (грепом по тулкиту), что эти 4 таблицы пусты
НЕ по забывчивости — у них просто НЕТ ПИСАТЕЛЯ:
    tracks        — читает export-markdown.py, писать нечем
    invariants    — читает export-markdown.py, писать нечем
    backlog_tests — читает backlog.py (cmd_show:125), писать нечем
    templates     — не читает и не пишет никто
Тот же класс, что находка STUD #1959 про двойную запись: читатель есть,
правило ссылается, а механизма нет. Данные, залитые руками мимо инструмента,
превращаются в ложь при первой же правке — поэтому сначала писатель.

ЗАПУСК:
    python set-registry.py --db <p> track     --id TRACK-X --title "..." [--status active]
    python set-registry.py --db <p> invariant --code VERIFY-AT-SOURCE --desc "..."
    python set-registry.py --db <p> test      --backlog-id 5 --title "..." --method "..." \
                                              [--command "..."] [--expected "..."]
    python set-registry.py --db <p> template  --role-type coord --name "COORD" --prompt-file f
    python set-registry.py --db <p> list      [track|invariant|test|template]

Все подкоманды идемпотентны (INSERT OR REPLACE по ключу) и пишут в audit_log.
Без --apply — dry-run.
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def audit(conn, actor, action, target, diff):
    conn.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
        (actor, action, target, diff))


def cmd_track(conn, a):
    old = conn.execute("SELECT title, status FROM tracks WHERE track_id=?", (a.id,)).fetchone()
    print(f"{'ОБНОВЛЕНИЕ' if old else 'СОЗДАНИЕ'} трека {a.id}")
    print(f"  title  : {old[0] if old else '—'} → {a.title}")
    print(f"  status : {old[1] if old else '—'} → {a.status}")
    if not a.apply:
        return
    plan = Path(a.plan_file).read_text(encoding="utf-8") if a.plan_file else a.plan
    conn.execute(
        "INSERT INTO tracks (track_id, title, status, plan_md, owner_decision) VALUES (?,?,?,?,?) "
        "ON CONFLICT(track_id) DO UPDATE SET title=excluded.title, status=excluded.status, "
        "plan_md=COALESCE(excluded.plan_md, tracks.plan_md), "
        "owner_decision=COALESCE(excluded.owner_decision, tracks.owner_decision), "
        "updated_at=datetime('now')",
        (a.id, a.title, a.status, plan, a.owner_decision))
    audit(conn, a.actor, "update_track" if old else "create_track", a.id, f"{a.title} [{a.status}]")
    conn.commit()
    print(f"✅ трек {a.id} записан")


def cmd_invariant(conn, a):
    old = conn.execute("SELECT description FROM invariants WHERE code=?", (a.code,)).fetchone()
    print(f"{'ОБНОВЛЕНИЕ' if old else 'СОЗДАНИЕ'} инварианта {a.code}")
    if old:
        print(f"  было : {old[0][:90]}")
    print(f"  стало: {a.desc[:90]}")
    if not a.apply:
        return
    conn.execute(
        "INSERT INTO invariants (code, description, established_by) VALUES (?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET description=excluded.description",
        (a.code, a.desc, a.by))
    audit(conn, a.actor, "update_invariant" if old else "create_invariant", a.code, a.desc)
    conn.commit()
    print(f"✅ инвариант {a.code} записан")


def cmd_test(conn, a):
    b = conn.execute("SELECT title FROM backlog WHERE id=?", (a.backlog_id,)).fetchone()
    if not b:
        print(f"ERR: тикета backlog #{a.backlog_id} нет", file=sys.stderr)
        sys.exit(1)
    print(f"ТЕСТ к тикету #{a.backlog_id} «{b[0]}»")
    print(f"  title    : {a.title}")
    print(f"  method   : {a.method}")
    print(f"  command  : {a.command or '—'}")
    print(f"  expected : {a.expected or '—'}")
    if not a.apply:
        return
    spec = Path(a.spec_file).read_text(encoding="utf-8") if a.spec_file else a.spec
    conn.execute(
        "INSERT INTO backlog_tests (backlog_id, title, method, spec_md, command, expected, created_by) "
        "VALUES (?,?,?,?,?,?,?)",
        (a.backlog_id, a.title, a.method, spec, a.command, a.expected, a.actor))
    audit(conn, a.actor, "add_backlog_test", f"backlog#{a.backlog_id}", f"{a.title} / {a.method}")
    conn.commit()
    print(f"✅ тест привязан к #{a.backlog_id}")


def cmd_template(conn, a):
    old = conn.execute("SELECT display_name FROM templates WHERE role_type=?", (a.role_type,)).fetchone()
    print(f"{'ОБНОВЛЕНИЕ' if old else 'СОЗДАНИЕ'} шаблона роли {a.role_type}")
    if not a.apply:
        return
    prompt = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else a.prompt
    conn.execute(
        "INSERT INTO templates (role_type, display_name, launcher_prompt, capabilities, tools_needed, version) "
        "VALUES (?,?,?,?,?,1) "
        "ON CONFLICT(role_type) DO UPDATE SET display_name=excluded.display_name, "
        "launcher_prompt=excluded.launcher_prompt, version=templates.version+1, updated_at=datetime('now')",
        (a.role_type, a.name, prompt, a.capabilities, a.tools))
    audit(conn, a.actor, "update_template" if old else "create_template", a.role_type, a.name)
    conn.commit()
    print(f"✅ шаблон {a.role_type} записан")


def cmd_list(conn, a):
    what = a.what or "all"
    if what in ("track", "all"):
        print("=== TRACKS ===")
        for r in conn.execute("SELECT track_id,title,status FROM tracks ORDER BY status,track_id"):
            print(f"  {'🟢' if r[2]=='active' else '⚪'} {r[0]:22} {r[1]}  [{r[2]}]")
    if what in ("invariant", "all"):
        print("=== INVARIANTS ===")
        for r in conn.execute("SELECT code,description FROM invariants ORDER BY code"):
            print(f"  🛡️ {r[0]:28} {r[1][:80]}")
    if what in ("test", "all"):
        print("=== BACKLOG_TESTS ===")
        for r in conn.execute(
                "SELECT t.id,t.backlog_id,t.title,t.method,t.status FROM backlog_tests t ORDER BY t.backlog_id"):
            print(f"  #{r[0]} →backlog#{r[1]} [{r[4]}] {r[2]}  ({r[3]})")
    if what in ("template", "all"):
        print("=== TEMPLATES ===")
        for r in conn.execute("SELECT role_type,display_name,version FROM templates ORDER BY role_type"):
            print(f"  {r[0]:8} {r[1]}  v{r[2]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("track", "invariant", "test", "template", "list"):
        p = sub.add_parser(name)
        p.add_argument("--actor", default="COORD")
        p.add_argument("--apply", action="store_true", help="без него — dry-run")
        if name == "track":
            p.add_argument("--id", required=True)
            p.add_argument("--title", required=True)
            p.add_argument("--status", default="active", choices=["active", "paused", "done"])
            p.add_argument("--plan"); p.add_argument("--plan-file", dest="plan_file")
            p.add_argument("--owner-decision", dest="owner_decision")
        elif name == "invariant":
            p.add_argument("--code", required=True)
            p.add_argument("--desc", required=True)
            p.add_argument("--by", default="coord")
        elif name == "test":
            p.add_argument("--backlog-id", dest="backlog_id", type=int, required=True)
            p.add_argument("--title", required=True)
            p.add_argument("--method", required=True, help="ЧЕМ проверяется: команда/запрос/смоук")
            p.add_argument("--spec"); p.add_argument("--spec-file", dest="spec_file")
            p.add_argument("--command"); p.add_argument("--expected")
        elif name == "template":
            p.add_argument("--role-type", dest="role_type", required=True)
            p.add_argument("--name", required=True)
            p.add_argument("--prompt"); p.add_argument("--prompt-file", dest="prompt_file")
            p.add_argument("--capabilities", default="[]"); p.add_argument("--tools", default="[]")
        elif name == "list":
            p.add_argument("what", nargs="?", choices=["track", "invariant", "test", "template", "all"])

    a = ap.parse_args()
    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{a.db}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {a.db}")
    {"track": cmd_track, "invariant": cmd_invariant, "test": cmd_test,
     "template": cmd_template, "list": cmd_list}[a.cmd](conn, a)
    if a.cmd != "list" and not a.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")


if __name__ == "__main__":
    main()
