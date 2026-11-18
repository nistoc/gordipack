#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА карточки 480: строка частичного исхода называет НОМЕР записки.

Предмет. Записка ушла, а сохранение памяти тем же вызовом (--save-state) отклонено защитой.
Инструмент печатал «записка #уже записана»: решётка без номера, оборванная ссылка — в самый
тревожный миг, когда роли нужен номер ушедшей записки (сослаться, поправить, не отправить дубль).
Решение PROTO: подставить номер — он к этому месту уже известен.

Случаи (различающий = инструмент обязан ответить ИНАЧЕ, а не одинаково):
  ① отказ сохранения памяти: строка частичного исхода несёт номер записки из «OK #N»
     и не несёт «#» без номера                                              РАЗЛИЧАЮЩИЙ
  ② встречный: память сохранилась — код 0, строки частичного исхода нет, «OK #N» есть
     (успешный ход не изменился)                                             РАЗЛИЧАЮЩИЙ
  ③ встречный: при отказе записка ЗАПИСАНА, код 4, номер из строки совпадает с номером
     записки в базе                                                          РАЗЛИЧАЮЩИЙ

Нарочная поломка «old-line» (--break old-line) возвращает прежнюю строку «записка #уже записана»:
① обязан покраснеть, ② и ③ — нет (код 4 и запись записки от строки не зависят).

ЧЕГО НЕ ПРОВЕРЯЕТ: сохранение §plan (тот же цикл, одна строка кода); холостой прогон (там строка
частичного исхода не печатается); вызов без записки (номера нет — строка говорит словами и без «#»).

⛔ Живой базы не касается: своя песочница (mezo_stand). Три исхода: 0 прошла · 1 не прошла · 2 не запустилась.
"""
import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем
import mezo_stand  # noqa: E402 — песочница

WRITE = str(mezo_target.script("write-message.py"))
CASES = DIFFER = 0
ROLE = "ZZPARTIAL"
STATE = "СОСТОЯНИЕ РОЛИ. Достаточно длинный текст, чтобы не сработала защита от обвала."
OLD_LINE = ('            print(f"⚠️ память (§{section}) НЕ сохранена — {_note_part}, память НЕТ.",',
            '            print(f"⚠️ память (§{section}) НЕ сохранена — записка #уже записана, память НЕТ.",')


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    d = str(mezo_stand.new("bite-partial-"))
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
    """)
    con.execute("INSERT INTO read_cursors VALUES (?, 0)", (ROLE,))
    con.execute("INSERT INTO roles VALUES (?, 'active')", (ROLE,))
    con.commit()
    con.close()
    return d, db


def write(tool, db, d, body, extra=()):
    f = os.path.join(d, "note.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(body)
    r = subprocess.run([sys.executable, tool, "--db", db, "--role", ROLE, "--file", f, *extra],
                       capture_output=True, text=True, encoding="utf-8",
                       env=mezo_stand.stand_env(d))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def last_id(db):
    con = sqlite3.connect(db)
    n = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    con.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_key", choices=["old-line"], default=None,
                    help="нарочная поломка: вернуть прежнюю строку «записка #уже записана»")
    a = ap.parse_args()
    tool = WRITE
    if not os.path.exists(WRITE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    if a.break_key:
        stand = mezo_stand.new("bite-partial-porcha-")
        copy_path = mezo_stand.copy_tool(WRITE, stand)
        text = copy_path.read_text(encoding="utf-8")
        if OLD_LINE[0] not in text:
            raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: поломку «old-line» не удалось навести — образец не найден в коде")
        copy_path.write_text(text.replace(OLD_LINE[0], OLD_LINE[1], 1), encoding="utf-8")
        # write-message.py зовёт save-phoenix.py по соседству со своей копией: кладём и его (без этого
        # сохранение памяти падало бы не от защиты, а от отсутствия файла, и случай ② краснел бы зря)
        import shutil
        shutil.copy2(mezo_target.script("save-phoenix.py"), copy_path.parent / "save-phoenix.py")
        tool = str(copy_path)
        print("🧪 НАРОЧНАЯ ПОЛОМКА «old-line» ВЗВЕДЕНА\n")

    ok = True
    d, db = build()
    empty = os.path.join(d, "empty.md")
    with open(empty, "w", encoding="utf-8") as fh:
        fh.write("   \n ")
    good = os.path.join(d, "state.md")
    with open(good, "w", encoding="utf-8") as fh:
        fh.write(STATE)

    out1, code1 = write(tool, db, d, "записка, у которой память не сохранится", ["--save-state", empty])
    mid = last_id(db)
    m_ok = re.search(r"^OK #(\d+)\b", out1, re.M)
    m_line = re.search(r"память \(§state\) НЕ сохранена — (.*)", out1)
    line = m_line.group(1) if m_line else ""
    ok &= case("① отказ сохранения памяти: строка частичного исхода несёт номер записки",
               bool(m_line) and f"записка #{mid} уже записана" in line and "#уже" not in out1,
               f"номер в базе {mid} · «OK #»: {m_ok.group(1) if m_ok else None} · строка: {line!r}",
               differ=True)
    ok &= case("③ встречный: при отказе записка ЗАПИСАНА, код 4, номер «OK #» = номер в базе",
               code1 == 4 and bool(m_ok) and int(m_ok.group(1)) == mid,
               f"код {code1} (ждём 4) · «OK #{m_ok.group(1) if m_ok else None}» · записка в базе #{mid}",
               differ=True)

    out2, code2 = write(tool, db, d, "записка, у которой память сохранится", ["--save-state", good])
    ok &= case("② встречный: память сохранилась — код 0, строки частичного исхода нет, «OK #» есть",
               code2 == 0 and "НЕ сохранена" not in out2 and re.search(r"^OK #\d+\b", out2, re.M) is not None,
               f"код {code2} · строка отказа есть: {'НЕ сохранена' in out2} · хвост вывода: {out2.strip()[:900]}", differ=True)

    print()
    print(f"{'✅ СТРОКА ЧАСТИЧНОГО ИСХОДА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    print(f"ИТОГ: {'прошла' if ok else 'не прошла'}")
    if a.break_key and not ok:
        print("✅ так и надо: под поломкой случаи краснеют — они судят предмет, а не форму")
        return 0
    if a.break_key and ok:
        print("⚠️ ПОЛОМКА ВЗВЕДЕНА, А ВСЁ ПРОШЛО ПРИЁМКУ — случаи НЕ РАЗЛИЧАЮТ этот дефект")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
