#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА МЕРЫ ③ ВАРИАНТА А: возраст ТЕКСТА отделён от возраста ВЗГЛЯДА.

Слово владельца 2026-08-08 16:19 UTC: «вариант А» — сравнивать СОДЕРЖИМОЕ, а не время.

Предмет. У памяти роли было ОДНО поле времени, и оно отвечало на два разных вопроса сразу:
«когда текст менялся» и «когда роль его подтверждала». Одна дата не может быть верной в обоих
случаях — они требуют ПРОТИВОПОЛОЖНОГО поведения при пересохранении без правок:
    ① не двигать (иначе пересохранение вслепую выглядит свежестью — так гасился сторож ⑥);
    ② двигать (иначе верный, но нетронутый текст выглядит брошенным).

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① первое сохранение ставит ОБЕ даты          контроль: запись вообще работает
  ② ТЕКСТ ИЗМЕНИЛСЯ → двигаются ОБЕ даты                          РАЗЛИЧАЮЩИЙ
  ③ текст ТОТ ЖЕ до знака → возраст текста НЕ сдвинут             РАЗЛИЧАЮЩИЙ
  ④ текст ТОТ ЖЕ → возраст ВЗГЛЯДА СДВИНУТ                        РАЗЛИЧАЮЩИЙ
  ⑤ текст ТОТ ЖЕ → само тело не переписано (проверяем содержимым) РАЗЛИЧАЮЩИЙ
  ⑥ пустое тело по-прежнему ОТКАЗ, и ни одна дата не тронута      РАЗЛИЧАЮЩИЙ
  ⑦ на базе БЕЗ колонки confirmed_at механизм работает и ГОВОРИТ об этом вслух

⛔ Живой базы не касается: своя песочница.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом

SAVE = str(mezo_target.script("save-phoenix.py"))
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build(with_confirmed=True):
    d = tempfile.mkdtemp(prefix="bite-confirmed-")
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    cols = "role TEXT, section TEXT, body TEXT, saved_at TEXT"
    if with_confirmed:
        cols += ", confirmed_at TEXT"
    con.execute(f"CREATE TABLE phoenix ({cols}, PRIMARY KEY (role, section))")
    con.execute("""CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor_role TEXT,
                   action TEXT, target TEXT, diff_md TEXT)""")
    con.commit()
    con.close()
    return d, db


def save(db, text, d):
    f = os.path.join(d, "body.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(text)
    r = subprocess.run([sys.executable, SAVE, "--db", db, "--role", "PROTO",
                        "--section", "state", "--file", f],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def row(db):
    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(phoenix)")]
    sel = "body, saved_at" + (", confirmed_at" if "confirmed_at" in cols else "")
    r = con.execute(f"SELECT {sel} FROM phoenix WHERE role='PROTO' AND section='state'").fetchone()
    con.close()
    return r


def main() -> int:
    if not os.path.exists(SAVE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {SAVE} не найден — приёмке нечего испытывать.")
    ok = True
    TEXT = "СОСТОЯНИЕ. Первая редакция, достаточно длинная, чтобы не сработала защита от обвала."
    d, db = build()

    save(db, TEXT, d)
    b0, s0, c0 = row(db)
    ok &= case("① первое сохранение проставило ОБЕ даты (контроль: запись работает)",
               bool(s0) and bool(c0),
               f"возраст текста {s0} · возраст взгляда {c0}")

    # Секунда паузы — иначе даты совпадут по построению и любой случай станет зелёным вслепую:
    # у sqlite datetime('now') разрешение в секунду.
    time.sleep(1.1)
    save(db, TEXT + " Дописана строка — текст ИЗМЕНИЛСЯ.", d)
    b1, s1, c1 = row(db)
    ok &= case("② текст ИЗМЕНИЛСЯ → сдвинуты ОБЕ даты",
               s1 > s0 and c1 > c0,
               f"текст {s0} → {s1} · взгляд {c0} → {c1}", differ=True)

    time.sleep(1.1)
    out, code = save(db, b1, d)              # ровно то же тело, до знака
    b2, s2, c2 = row(db)
    ok &= case("③ текст ТОТ ЖЕ → возраст ТЕКСТА не сдвинут",
               s2 == s1,
               f"было {s1}, стало {s2} — пересохранение вслепую больше не выглядит свежестью",
               differ=True)
    ok &= case("④ текст ТОТ ЖЕ → возраст ВЗГЛЯДА СДВИНУТ",
               c2 > c1,
               f"взгляд {c1} → {c2} — верный, но нетронутый текст не выглядит брошенным",
               differ=True)
    ok &= case("⑤ текст ТОТ ЖЕ → тело не переписано",
               b2 == b1 and code == 0,
               f"тело совпало посимвольно ({len(b2)} знаков), код {code}", differ=True)

    time.sleep(1.1)
    out_empty, code_empty = save(db, "   \n  ", d)
    b3, s3, c3 = row(db)
    ok &= case("⑥ пустое тело — ОТКАЗ, и НИ ОДНА дата не тронута",
               code_empty != 0 and b3 == b2 and s3 == s2 and c3 == c2,
               f"код {code_empty} · текст {s3} · взгляд {c3} — отказ обязан быть без следа",
               differ=True)

    d2, db2 = build(with_confirmed=False)
    out2, code2 = save(db2, TEXT, d2)
    r2 = row(db2)
    ok &= case("⑦ на базе БЕЗ колонки взгляда механизм работает и ГОВОРИТ об этом",
               code2 == 0 and r2 is not None and r2[0] == TEXT,
               "старая база не должна ломаться от новой меры; молчаливая деградация запрещена")

    print()
    print(f"{'✅ МЕРА ③ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
