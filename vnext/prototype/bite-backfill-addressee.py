#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА обратного заполнения адресатов (разбор прозы из тел).

Заполнение трогает 1985 записок разом. Ошибка здесь не «покраснеет» — она молча наполнит
базу неверными адресатами, и витрина станет уверенно врать. Поэтому приёмка испытывает
ЖИВОЙ скрипт на песочнице с заранее известным ответом.

Случаи (различающий = скрипт обязан ответить ИНАЧЕ, а не одинаково):
  ① обращение в шапке → 'to'                контроль: разбор вообще работает
  ② хвост «cc @…» → 'cc', и НЕ 'to'                              РАЗЛИЧАЮЩИЙ
  ③ роль в шапке И в хвосте → только 'to' (обращение сильнее)     РАЗЛИЧАЮЩИЙ
  ④ АВТОР себе не адресат                                        РАЗЛИЧАЮЩИЙ
  ⑤ цитата «> @РОЛЬ …» адресатом НЕ делает                       РАЗЛИЧАЮЩИЙ
  ⑥ объявленное ручкой ('field') НЕ ПЕРЕЗАПИСЫВАЕТСЯ             РАЗЛИЧАЮЩИЙ
  ⑦ всё записанное помечено 'backfill', ни одной строки 'field'  РАЗЛИЧАЮЩИЙ
  ⑧ повторный прогон НЕ УДВАИВАЕТ (идемпотентность)              РАЗЛИЧАЮЩИЙ
  ⑨ таблица messages не тронута ни одной строкой
  ⑩ без --apply база НЕ меняется вовсе                           РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: своя песочница.
"""
import os
import sqlite3
import subprocess
import sys
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

SCRIPT = os.path.join(str(mezo_paths.live_scripts()), "migrations",
                      "20260808-backfill-addressee.py")
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build(msgs, declared=()):
    d = str(mezo_stand.new("bite-backfill-"))
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT,
                   timestamp TEXT, body_md TEXT, tags TEXT, priority TEXT)""")
    con.execute("CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER)")
    con.execute("""CREATE TABLE message_addressee (
                   message_id INTEGER, role TEXT, kind TEXT, linked_by TEXT DEFAULT 'field',
                   PRIMARY KEY (message_id, role, kind))""")
    for r in ("COORD", "CORE", "STUD", "TAXO", "PROTO"):
        con.execute("INSERT INTO read_cursors VALUES (?, 0)", (r,))
    for mid, w, body in msgs:
        con.execute("INSERT INTO messages (id, writer_role, body_md) VALUES (?,?,?)",
                    (mid, w, body))
    for mid, role, kind in declared:
        con.execute("INSERT INTO message_addressee VALUES (?,?,?,'field')", (mid, role, kind))
    con.commit()
    con.close()
    return db


def run(db, apply=True):
    cmd = [sys.executable, SCRIPT, "--db", db] + (["--apply"] if apply else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def got(db, mid=None):
    con = sqlite3.connect(db)
    q = "SELECT message_id, role, kind, linked_by FROM message_addressee"
    if mid:
        q += f" WHERE message_id={mid}"
    rows = con.execute(q + " ORDER BY message_id, kind, role").fetchall()
    con.close()
    return rows


def main() -> int:
    if not os.path.exists(SCRIPT):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {SCRIPT} не найден — приёмке нечего испытывать.")
    ok = True

    MSGS = [
        (1, "PROTO", "✅ @CORE — вопрос по существу\nтело записки"),
        (2, "PROTO", "📏 разбор без адресата\nтело. cc @STUD @TAXO"),
        (3, "PROTO", "🔧 @CORE — вопрос. cc @CORE @STUD"),
        (4, "PROTO", "@PROTO — сам себе пишу\nтело"),
        (5, "PROTO", "разбор\n> цитирую: «@TAXO — твой вопрос»\nсвой текст"),
        (6, "PROTO", "🔑 @STUD — объявленное ручкой. cc @TAXO"),
    ]
    db = build(MSGS, declared=[(6, "COORD", "to")])
    out, code = run(db)

    ok &= case("① обращение в шапке разобрано как 'to' (контроль: разбор работает)",
               got(db, 1) == [(1, "CORE", "to", "backfill")],
               f"код {code} · в базе {got(db, 1)}")

    ok &= case("② хвост «cc @…» разобран как 'cc' и НЕ как обращение",
               got(db, 2) == [(2, "STUD", "cc", "backfill"), (2, "TAXO", "cc", "backfill")],
               f"в базе {[(g[1], g[2]) for g in got(db, 2)]}", differ=True)

    ok &= case("③ роль и в шапке, и в хвосте — только обращение, дважды не считается",
               got(db, 3) == [(3, "STUD", "cc", "backfill"), (3, "CORE", "to", "backfill")],
               f"в базе {[(g[1], g[2]) for g in got(db, 3)]} — CORE обязан быть только 'to'",
               differ=True)

    ok &= case("④ АВТОР себе не адресат",
               got(db, 4) == [],
               f"записка PROTO с «@PROTO» в шапке → строк {len(got(db, 4))}", differ=True)

    ok &= case("⑤ цитата «> @РОЛЬ» адресатом не делает",
               got(db, 5) == [],
               "пересказ чужой шапки адресует в прошлое, а не тебе", differ=True)

    ok &= case("⑥ объявленное ручкой НЕ ПЕРЕЗАПИСАНО и не дополнено разбором",
               got(db, 6) == [(6, "COORD", "to", "field")],
               f"в базе {got(db, 6)} — записка с 'field' пропускается целиком", differ=True)

    all_rows = got(db)
    ok &= case("⑦ всё разобранное помечено 'backfill'",
               all(r[3] == "backfill" for r in all_rows if r[0] != 6),
               "догадка не имеет права выглядеть как объявленное человеком", differ=True)

    before = len(all_rows)
    run(db)
    ok &= case("⑧ повторный прогон НЕ УДВАИВАЕТ",
               len(got(db)) == before,
               f"строк было {before}, после второго прогона {len(got(db))}", differ=True)

    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    con.close()
    ok &= case("⑨ таблица записок не тронута",
               n == len(MSGS), f"записок {n} из {len(MSGS)}")

    db2 = build(MSGS)
    out2, _ = run(db2, apply=False)
    ok &= case("⑩ без --apply база НЕ меняется",
               got(db2) == [] and "БАЗА НЕ ТРОНУТА" in out2,
               "замер обязан быть безопасным: иначе его перестанут звать перед записью",
               differ=True)

    print()
    print(f"{'✅ ЗАПОЛНЕНИЕ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан ЖИВОЙ скрипт")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
