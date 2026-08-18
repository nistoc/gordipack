# -*- coding: utf-8 -*-
"""
phoenix-vnext.py — ПРОТОТИП Э-А: память роли, которая не утекает (R6 + R7).

ЧТО ЛЕЧИТ (полевые факты, не теория):
  F3  — роль умирает без свёртки (STUD 2026-07-25), а свежий слепок устаревает за минуты;
        гард свежести краснел у 4 ролей из 8 одновременно.
  F11 — `save-phoenix` делает ON CONFLICT DO UPDATE: прежнее тело секции затирается
        БЕЗВОЗВРАТНО, в audit_log попадает только длина. «Слепок затёрли» нельзя ни
        расследовать, ни откатить — при том что вся остальная система append-only.
  F16 — присутствие/ритм живёт в СЕССИИ, а не в данных: следующая инкарнация не знает,
        сняли таймер словом владельца или он умер вместе с чатом (TAXO #2668).

ЗАМЕР, НА КОТОРОМ СТОИТ ДИЗАЙН (2026-07-26 06:34 UTC, живая БД, read-only):
    184 539 символов ручного текста в слепках 8 ролей;
    ~22 % строк несут ПРОИЗВОДНЫЕ факты — 153 ссылки на ноты, 98 git-хэшей,
    94 упоминания отметки прочитанного, 104 порта, 57 меток времени.
  Всё это уже лежит в первичных данных. И протухает первым — ровно эти строки делают
  «свежий» слепок ложным через минуты.

ИДЕЯ: память расслаивается по ПРОИСХОЖДЕНИЮ, а не по темам.
    derived — собирает МАШИНА из первичных данных (лента · отметка прочитанного · heartbeat · бэклог · git).
              Никогда не пишется руками, не может протухнуть — пересобирается при каждом чтении.
    intent  — тонкий РУЧНОЙ слой: намерение, гипотезы, границы, «чего жду». Того, чего в данных нет.
    stable  — identity/history/sources/launcher: редко меняется, остаётся как есть.
  Роль перестаёт переписывать то, что система и так знает. Смерть без свёртки теряет только
  intent с момента последнего сохранения — а не всё состояние.

    python phoenix-vnext.py --db <песочница> derive  --role CORE
    python phoenix-vnext.py --db <песочница> save    --role CORE --section plan --file <файл>
    python phoenix-vnext.py --db <песочница> history --role CORE [--section plan]
    python phoenix-vnext.py --db <песочница> restore --role CORE --section plan --version 3
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()
STABLE = ("identity", "history", "sources", "launcher")


# ─────────────────────────────────────────────────────────────────────────────
# R7: версионирование. append-only история + указатель на текущую версию
# ─────────────────────────────────────────────────────────────────────────────
def ensure_schema(con):
    """Идемпотентно (правило migration-safety). Таблица истории — append-only:
    UPDATE по ней не делается никогда, только INSERT. Текущая версия — максимум version."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS phoenix_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT NOT NULL,
            section   TEXT NOT NULL,
            version   INTEGER NOT NULL,
            body      TEXT NOT NULL,
            saved_at  TEXT NOT NULL DEFAULT (datetime('now')),
            saved_by  TEXT NOT NULL DEFAULT 'role',
            reason    TEXT DEFAULT '')""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ph_hist ON phoenix_history(role, section, version)")
    con.commit()


def next_version(con, role, section):
    row = con.execute("SELECT MAX(version) FROM phoenix_history WHERE role=? AND section=?",
                      (role, section)).fetchone()
    return (row[0] or 0) + 1


def save_versioned(con, role, section, body, reason=""):
    """Сохранение, которое НЕ теряет прежнее.

    Порядок важен: сначала в историю уезжает ТЕКУЩЕЕ тело (если оно есть и ещё не в истории),
    потом пишется новое. Иначе первая же правка после включения версионирования потеряла бы
    ровно то состояние, ради которого версионирование и заводили.
    """
    ensure_schema(con)
    cur = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                      (role, section)).fetchone()
    if cur and not con.execute(
            "SELECT 1 FROM phoenix_history WHERE role=? AND section=? AND body=? LIMIT 1",
            (role, section, cur[0])).fetchone():
        con.execute("INSERT INTO phoenix_history (role, section, version, body, reason) "
                    "VALUES (?,?,?,?,?)",
                    (role, section, next_version(con, role, section), cur[0], "снимок перед правкой"))
    con.execute("""INSERT INTO phoenix (role, section, body, saved_at)
                   VALUES (?,?,?,datetime('now'))
                   ON CONFLICT(role, section) DO UPDATE
                   SET body=excluded.body, saved_at=excluded.saved_at""", (role, section, body))
    con.execute("INSERT INTO phoenix_history (role, section, version, body, reason) VALUES (?,?,?,?,?)",
                (role, section, next_version(con, role, section), body, reason or "сохранение роли"))
    con.commit()


# ─────────────────────────────────────────────────────────────────────────────
# R6: derived — то, что машина знает и так
# ─────────────────────────────────────────────────────────────────────────────
def headline(body, width=86):
    for line in (body or "").splitlines():
        s = re.sub(r"[*_`#>]+", "", line).strip()
        if len(s) >= 8:
            return s if len(s) <= width else s[:width - 1] + "…"
    return "(пусто)"


def derive(con, role, notes=6):
    out = []
    a = out.append
    now = con.execute("SELECT datetime('now')").fetchone()[0]
    a(f"# СОБРАНО МАШИНОЙ {now} UTC — руками НЕ править, пересобирается при каждом чтении")
    a("# (источники: messages · read_cursors · role_status · backlog · phoenix_history)")
    a("")

    # ── присутствие: прямой ответ на F16
    hb = con.execute("SELECT status, updated_at FROM role_status WHERE role=?", (role,)).fetchone()
    cur = con.execute("SELECT last_read_id, updated_at FROM read_cursors WHERE reader_role=?",
                      (role,)).fetchone()
    head = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    if cur:
        unread, unread_kb = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(body_md)),0)/1024 FROM messages WHERE id > ?",
            (cur[0],)).fetchone()
    else:
        unread, unread_kb = 0, 0
    a("## ПРИСУТСТВИЕ И ЛЕНТА")
    a(f"- курсор: {cur[0] if cur else '—'} (обновлён {cur[1] if cur else '—'} UTC), голова ленты #{head}")
    a(f"- непрочитано: {unread} нот / ~{unread_kb} КБ" +
      ("  ⚠️ больше окна вывода — начни с дайджеста" if unread_kb > 24 else ""))
    a(f"- heartbeat: {hb[1] if hb else '—'} UTC — {headline(hb[0]) if hb else '(нет)'}")
    # незакрытый батч — половина F15: видно, что чтение оборвалось между read и ack
    ob = con.execute("SELECT token, last_id, issued_at FROM read_batches WHERE role=? "
                     "ORDER BY issued_at DESC LIMIT 1", (role,)).fetchone()
    if not ob:
        a("- неподтверждённых батчей нет")
    elif cur and ob[1] <= cur[0]:
        # Точность важнее драмы: батч, перекрытый курсором, — СЛЕД оборванного чтения,
        # а не потеря. Иначе derived сам стал бы артефактом, который лжёт о мире.
        a(f"- след оборванного чтения: батч до #{ob[1]} (выдан {ob[2]} UTC) так и не подтверждён, "
          f"но курсор {cur[0]} уже дальше — ноты не потеряны, читались заново")
    else:
        a(f"- ⚠️ НЕПОДТВЕРЖДЁННЫЙ батч до #{ob[1]}, выдан {ob[2]} UTC — чтение оборвалось между "
          f"read и ack; эти ноты прочитаны, но лента считает иначе (F15)")
    a("")

    a(f"## ЧТО Я ГОВОРИЛ ПОСЛЕДНИМ (последние {notes} моих нот)")
    for mid, ts, body in con.execute(
            "SELECT id, timestamp, body_md FROM messages WHERE writer_role=? "
            "ORDER BY id DESC LIMIT ?", (role, notes)):
        a(f"- #{mid} {ts[5:16]}  {headline(body)}")
    a("")

    a("## АДРЕСОВАНО МНЕ И ЕЩЁ НЕ ПРОЧИТАНО")
    mine = [(mid, w, ts, b) for mid, w, ts, b in con.execute(
        "SELECT id, writer_role, timestamp, body_md FROM messages WHERE id > ? ORDER BY id",
        (cur[0] if cur else 0,)) if re.search(rf"@{role}\b", b or "", re.I) and w != role]
    a(f"- {len(mine)} шт." if mine else "- нет")
    for mid, w, ts, b in mine[:8]:
        a(f"  · #{mid} [{w}] {ts[5:16]}  {headline(b, 70)}")
    a("")

    rows = list(con.execute(
        "SELECT id, title, status, priority FROM backlog WHERE role=? AND status NOT IN "
        "('done','dropped') ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
        "ELSE 2 END, id", (role,)))
    a(f"## ОТКРЫТЫЙ БЭКЛОГ ({len(rows)})")
    for bid, title, status, prio in rows:
        a(f"- #{bid} [{status}/{prio}] {title}")
    if not rows:
        a("- пусто")
    a("")

    try:
        hist = list(con.execute(
            "SELECT section, MAX(version), MAX(saved_at) FROM phoenix_history WHERE role=? "
            "GROUP BY section ORDER BY section", (role,)))
    except sqlite3.OperationalError:
        hist = []
    a("## РУЧНОЙ СЛОЙ — когда роль последний раз писала о себе САМА")
    for section, saved in con.execute(
            "SELECT section, saved_at FROM phoenix WHERE role=? ORDER BY section", (role,)):
        v = next((f"v{h[1]}" for h in hist if h[0] == section), "v—")
        mark = "" if section in STABLE else "  ← слой intent (протухает первым)"
        a(f"- {section:9} {saved} UTC  {v}{mark}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Прототип памяти роли (R6+R7)")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("derive", "save", "history", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--role", required=True)
        if name != "derive":
            p.add_argument("--section", required=(name != "history"), default=None)
        if name == "save":
            p.add_argument("--file", required=True)
            p.add_argument("--reason", default="")
        if name == "restore":
            p.add_argument("--version", type=int, required=True)
        if name == "derive":
            p.add_argument("--notes", type=int, default=6)
    a = ap.parse_args()

    db = Path(a.db).resolve()
    role = a.role.upper()
    write = a.cmd in ("save", "restore")
    if write and db == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Прототип пишет только в песочницу.")
    con = sqlite3.connect(f"file:{db}?mode={'rw' if write else 'ro'}", uri=True, timeout=5)

    if a.cmd == "derive":
        print(derive(con, role, a.notes))
    elif a.cmd == "save":
        body = Path(a.file).read_text(encoding="utf-8")
        save_versioned(con, role, a.section, body, a.reason)
        v = con.execute("SELECT MAX(version) FROM phoenix_history WHERE role=? AND section=?",
                        (role, a.section)).fetchone()[0]
        print(f"OK phoenix/{role}/{a.section} ({len(body)} симв.) → версия v{v}, прежнее сохранено")
    elif a.cmd == "history":
        ensure_schema(con)
        q = ("SELECT section, version, saved_at, LENGTH(body), reason FROM phoenix_history "
             "WHERE role=?" + (" AND section=?" if a.section else "") + " ORDER BY section, version")
        rows = list(con.execute(q, (role, a.section) if a.section else (role,)))
        if not rows:
            print(f"[{role}] истории нет (версионирование начинается с первого save)")
        for s, v, ts, n, r in rows:
            print(f"  {s:9} v{v:<3} {ts} UTC  {n:6} симв.  {r}")
    elif a.cmd == "restore":
        row = con.execute("SELECT body FROM phoenix_history WHERE role=? AND section=? AND version=?",
                          (role, a.section, a.version)).fetchone()
        if not row:
            sys.exit(f"⛔ версии v{a.version} для {role}/{a.section} нет")
        save_versioned(con, role, a.section, row[0], f"откат к v{a.version}")
        print(f"OK откат {role}/{a.section} к v{a.version} — как НОВАЯ версия (история не переписана)")
    con.close()


if __name__ == "__main__":
    main()
