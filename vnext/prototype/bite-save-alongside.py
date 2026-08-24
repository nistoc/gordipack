#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА МЕРЫ ② ВАРИАНТА А: память сохраняется ТЕМ ЖЕ действием, что и записка.

Слово владельца 2026-08-08 16:19 UTC — «вариант А».

Предмет. Отдельная необязательная кнопка у нас умирает: четыре механизма, заведённые так,
имеют НОЛЬ вызовов на тысячах записей. Прижилось ровно то, что вложено ВНУТРЬ уже
совершаемого действия. Поэтому сохранение памяти кладётся на путь записки.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① записка без ручек пишется как раньше            контроль: ничего не сломано
  ② --save-state тем же вызовом СОХРАНЯЕТ память                    РАЗЛИЧАЮЩИЙ
  ③ записка при этом всё равно записана (одно не съело другое)      РАЗЛИЧАЮЩИЙ
  ④ ОТКАЗ сохранения (пустое тело) НЕ отменяет записку              РАЗЛИЧАЮЩИЙ
  ⑤ защиты НЕ ПРОДУБЛИРОВАНЫ: отказ приходит СЛОВАМИ живого
     save-phoenix, а не своей копией правила                        РАЗЛИЧАЮЩИЙ
  ⑥ подсказка об отставании молчит, когда память СВЕЖА              РАЗЛИЧАЮЩИЙ
     (признак, горящий всегда, перестаёт значить что-либо)

⛔ Живой базы не касается: своя песочница.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

WRITE = str(mezo_target.script("write-message.py"))
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    d = str(mezo_stand.new("bite-alongside-"))
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
            priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
            addressed_by TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
        CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
            confirmed_at TEXT, PRIMARY KEY (role, section));
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor_role TEXT, action TEXT,
            target TEXT, diff_md TEXT);
        CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
            linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
        CREATE TABLE roles (role TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
        INSERT INTO read_cursors VALUES ('PROTO', 0);
        INSERT INTO roles VALUES ('PROTO', 'active');
    """)
    con.commit()
    con.close()
    return d, db


def write(db, d, body, extra=()):
    f = os.path.join(d, "note.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(body)
    r = subprocess.run([sys.executable, WRITE, "--db", db, "--role", "PROTO", "--file", f, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def counts(db):
    con = sqlite3.connect(db)
    m = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    p = con.execute("SELECT body FROM phoenix WHERE role='PROTO' AND section='state'").fetchone()
    con.close()
    return m, (p[0] if p else None)


def main() -> int:
    if not os.path.exists(WRITE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    ok = True
    d, db = build()
    STATE = "СОСТОЯНИЕ РОЛИ. Достаточно длинный текст, чтобы не сработала защита от обвала."

    out, code = write(db, d, "обычная записка без всяких ручек")
    m1, p1 = counts(db)
    ok &= case("① записка без ручек пишется как раньше (контроль)",
               code == 0 and m1 == 1 and p1 is None,
               f"код {code} · записок {m1} · память не тронута: {p1 is None}")

    sf = os.path.join(d, "state.md")
    open(sf, "w", encoding="utf-8").write(STATE)
    out2, code2 = write(db, d, "записка вместе с сохранением памяти", ["--save-state", sf])
    m2, p2 = counts(db)
    ok &= case("② --save-state тем же вызовом СОХРАНИЛ память",
               p2 == STATE,
               f"в памяти {len(p2 or '')} знаков, ждали {len(STATE)}", differ=True)
    ok &= case("③ записка при этом всё равно записана — одно не съело другое",
               code2 == 0 and m2 == 2,
               f"код {code2} · записок {m1} → {m2}", differ=True)

    empty = os.path.join(d, "empty.md")
    open(empty, "w", encoding="utf-8").write("   \n ")
    out3, code3 = write(db, d, "записка, у которой память НЕ сохранится", ["--save-state", empty])
    m3, p3 = counts(db)
    ok &= case("④ ОТКАЗ сохранения НЕ отменяет записку",
               m3 == 3 and p3 == STATE,
               f"записок {m2} → {m3} · прежняя память ЦЕЛА: {p3 == STATE}", differ=True)
    ok &= case("⑤ отказ пришёл СЛОВАМИ живого save-phoenix, а не своей копией правила",
               "ОТКАЗ" in out3 and "тело секции ПУСТО" in out3,
               "вторая копия правила разошлась бы с первой — этот класс ловили шесть раз",
               differ=True)

    out4, _ = write(db, d, "записка сразу после сохранения — память СВЕЖА")
    ok &= case("⑥ подсказка об отставании МОЛЧИТ, когда память свежа",
               "НЕ ПОДТВЕРЖДАЛАСЬ" not in out4,
               "признак, который горит всегда, перестаёт значить что-либо", differ=True)

    print()
    print(f"{'✅ МЕРА ② ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
