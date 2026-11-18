#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА карточки 596: повтор флага адресата НАКАПЛИВАЕТ имена (--to A --to B = --to A,B).

Предмет. У write-message.py повтор --to и --cc молча брал ПОСЛЕДНЕЕ имя: «--to PROTO --to COORD»
записывал одного COORD, а соседний флаг (--reviewed) повтор накапливал. Адресаты терялись без
единого слова при больше одного имени на флаг (замер STUD, записка #4953).
Решение PROTO, три части: накопление повтором · строка «адресатов: N — to K · cc M» рядом с
подтверждением записи · справка называет обе формы теми же словами, что у --reviewed.

Случаи (различающий = инструмент обязан ответить ИНАЧЕ, а не одинаково):
  ① повтор флага — все имена записаны: «--to A --to B --cc C --cc D» даёт в таблице адресатов те же
     строки, что «--to A,B --cc C,D»; смесь форм и повтор имени — без дублей     РАЗЛИЧАЮЩИЙ
  ② встречный: через запятую — как прежде (строки таблицы адресатов ровно ожидаемые)  РАЗЛИЧАЮЩИЙ
  ③ строка «адресатов: N — to K · cc M» печатается, числа верны                РАЗЛИЧАЮЩИЙ
  ④ строка «OK #» стоит на том же месте от конца вывода, что и у записки без адресатов;
     новая строка — непосредственно перед ней                                  РАЗЛИЧАЮЩИЙ
  ⑤ справка --to и --cc называет обе формы теми же словами, что справка --reviewed  РАЗЛИЧАЮЩИЙ
  ⑥ записка «всем сразу» без поимённых: строка говорит это словами, нуля адресатов в ней нет  РАЗЛИЧАЮЩИЙ

Нарочная поломка «last-wins» (--break last-wins) возвращает «повтор берёт последнее» у --to и --cc:
красным обязан стать РОВНО случай ①; ②–⑥ — нет.

ЧЕГО НЕ ПРОВЕРЯЕТ: перенос числом (сколько вызовов за 30 дней звали повтором флага — замер по записям
разговоров делает PROTO, пункт ⑤ карточки); слова «ВСЕ» и синонимов в повторе; холостой прогон
(строка «адресатов» там не печатается — подтверждения «OK #» в нём тоже нет).

⛔ Живой базы не касается: своя песочница (mezo_stand). Три исхода: 0 прошла · 1 не прошла · 2 не запустилась.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем
import mezo_stand  # noqa: E402 — песочница

WRITE = str(mezo_target.script("write-message.py"))
CASES = DIFFER = 0
ROLE = "PROTO"
NAMES = ("CORE", "STUD", "ING", "TAXO")
FORM_WORDS = "несколько — повтором флага ИЛИ через запятую; обе формы равны"
EXPECT_ROWS = [("ING", "cc"), ("TAXO", "cc"), ("CORE", "to"), ("STUD", "to")]
BREAK_ANCHORS = (('parser.add_argument("--to", action="append", default=None,',
                  'parser.add_argument("--to", default=None,'),
                 ('parser.add_argument("--cc", action="append", default=None,',
                  'parser.add_argument("--cc", default=None,'))


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    d = str(mezo_stand.new("bite-repeat-"))
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
            priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
            addressed_by TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
        CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
            linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
        CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT);
        CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
    """)
    for r in (ROLE, *NAMES):
        con.execute("INSERT INTO roles VALUES (?, 'alive')", (r,))
    con.commit()
    con.close()
    return d, db


def write(tool, db, d, body, extra=()):
    """→ (код, вывод в ОДНОМ потоке в порядке записи, номер записки из строки «OK #»)."""
    r = subprocess.run([sys.executable, tool, "--db", db, "--role", ROLE, "--body", body, *extra],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace", env=mezo_stand.stand_env(d))
    out = r.stdout or ""
    m = re.search(r"^OK #(\d+)\b", out, re.M)
    return r.returncode, out, (int(m.group(1)) if m else None)


def rows(db, mid):
    con = sqlite3.connect(db)
    got = con.execute("SELECT role, kind FROM message_addressee WHERE message_id=? "
                      "ORDER BY kind, role", (mid,)).fetchall()
    con.close()
    return got


def ok_from_end(out):
    lines = [l for l in out.splitlines() if l.strip()]
    for i, line in enumerate(reversed(lines)):
        if line.startswith("OK #"):
            return i, (lines[len(lines) - 1 - i - 1] if len(lines) - 1 - i - 1 >= 0 else "")
    return None, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_key", choices=["last-wins"], default=None,
                    help="нарочная поломка: повтор --to/--cc берёт последнее имя")
    a = ap.parse_args()
    tool = WRITE
    if not os.path.exists(WRITE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    if a.break_key:
        stand = mezo_stand.new("bite-repeat-porcha-")
        copy_path = mezo_stand.copy_tool(WRITE, stand)
        text = copy_path.read_text(encoding="utf-8")
        for old, new in BREAK_ANCHORS:
            if old not in text:
                raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: поломку «last-wins» не удалось навести — "
                                 f"образец не найден в коде: {old}")
            text = text.replace(old, new, 1)
        copy_path.write_text(text, encoding="utf-8")
        tool = str(copy_path)
        print("🧪 НАРОЧНАЯ ПОЛОМКА «last-wins» ВЗВЕДЕНА\n")

    ok = True
    d, db = build()
    now = datetime.now(timezone.utc).strftime("%H:%M")
    head = f"[{ROLE} {now} UTC] приёмка повтора флага адресата\n\n"

    # ② через запятую — как прежде (выполняется первой: её строки — образец для ①)
    code_c, out_c, mid_c = write(tool, db, d, head + "запятая", ["--to", "CORE,STUD", "--cc", "TAXO,ING"])
    got_c = rows(db, mid_c) if mid_c else []
    # ① повтор флага; смесь форм и повтор имени
    code_r, out_r, mid_r = write(tool, db, d, head + "повтор",
                                 ["--to", "CORE", "--to", "STUD", "--cc", "TAXO", "--cc", "ING"])
    got_r = rows(db, mid_r) if mid_r else []
    code_m, out_m, mid_m = write(tool, db, d, head + "смесь",
                                 ["--to", "CORE,STUD", "--to", "core", "--to", "@STUD", "--cc", "TAXO", "--cc", "ING,TAXO"])
    got_m = rows(db, mid_m) if mid_m else []
    ok &= case("① повтор флага — все имена записаны: те же строки, что через запятую; смесь форм без дублей",
               sorted(got_r) == sorted(EXPECT_ROWS) == sorted(got_c) and sorted(got_m) == sorted(EXPECT_ROWS),
               f"повтор → {got_r} · смесь → {got_m} · ждали {sorted(EXPECT_ROWS)} (по одному имени на флаг "
               f"прежний код записал бы 2 строки из 4)", differ=True)
    ok &= case("② встречный: через запятую — как прежде",
               code_c == 0 and sorted(got_c) == sorted(EXPECT_ROWS),
               f"код {code_c} · в таблице {got_c}", differ=True)

    # ③ строка о числе адресатов (у формы через запятую: судится строка, а не накопление — оно в ①)
    ok &= case("③ строка «адресатов: N — to K · cc M» печатается, числа верны",
               "адресатов: 4 — to 2 · cc 2" in out_c,
               f"через запятую: {'есть' if 'адресатов: 4 — to 2 · cc 2' in out_c else 'НЕТ'}", differ=True)

    # ④ место «OK #» от конца вывода
    code_n, out_n, mid_n = write(tool, db, d, head + "без адресата")
    pos_n, _ = ok_from_end(out_n)
    pos_r, before_r = ok_from_end(out_c)
    ok &= case("④ «OK #» стоит на том же месте от конца, что у записки без адресатов; новая строка — перед ней",
               pos_n is not None and pos_n == pos_r and before_r.startswith("адресатов:"),
               f"от конца: без адресатов {pos_n}, с адресатами {pos_r} (ждём равны) "
               f"· строка перед «OK #»: {before_r!r}", differ=True)

    # ⑤ справка
    h = subprocess.run([sys.executable, tool, "--help"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=mezo_stand.stand_env(d))
    flat = " ".join((h.stdout or "").split())

    def help_of(flag, nxt):
        m = re.search(re.escape(flag) + r" [A-Z_]*\s*(.*?)\s+" + re.escape(nxt), flat)
        return m.group(1) if m else ""

    help_to, help_cc, help_rev = help_of("--to", "--cc"), help_of("--cc", "--save-state"), help_of("--reviewed", "--dry-run")
    ok &= case("⑤ справка --to и --cc называет обе формы теми же словами, что справка --reviewed",
               FORM_WORDS in help_to and FORM_WORDS in help_cc and FORM_WORDS in help_rev,
               f"--to: {FORM_WORDS in help_to} · --cc: {FORM_WORDS in help_cc} · --reviewed (образец): "
               f"{FORM_WORDS in help_rev}", differ=True)

    # ⑥ «всем сразу» без поимённых: число «0» в строке читалось бы как «никому не ушло»
    code_a, out_a, _mid_a = write(tool, db, d, head + "всем", ["--to", "ВСЕ"])
    _pos_a, before_a = ok_from_end(out_a)
    ok &= case("⑥ записка «всем сразу» без поимённых — строка говорит это словами, нуля адресатов в ней нет",
               code_a == 0 and before_a.startswith("адресатов: всем сразу") and "адресатов: 0" not in out_a,
               f"код {code_a} · строка перед «OK #»: {before_a!r}", differ=True)

    print()
    print(f"{'✅ ПОВТОР ФЛАГА АДРЕСАТА ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
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
