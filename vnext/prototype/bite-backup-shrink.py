# -*- coding: utf-8 -*-
r"""ПРИЁМКА гарда убыли дампа в backup-db.py — карточка #250.

🩸 ЧЕМ ОПЛАЧЕНО. Гард стоял на посылке «данные append-only ⇒ дамп уменьшаться не должен».
24.08 посылка умерла: чистка истории версий ШТАТНО удаляет строки. Не тронь гард —
он кричал бы на исправной работе, и ему перестали бы верить ровно в день настоящей
потери («проверка, чьи находки все до одной ложные, хуже отсутствующей»).
Починка: сверка СТРОК ПО ТАБЛИЦАМ против шапки прежнего дампа; байты — справка.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① КОНТРОЛЬ: база выросла → молчит, код 0                                РАЗЛИЧАЮЩИЙ
  ② ЗАКОННАЯ убыль (чистка phoenix_history + read_batches) → «ЗАКОННО»,   РАЗЛИЧАЮЩИЙ
    без тревоги, код 0 — прогон №1 критерия карточки
  ③ ПОДОЗРИТЕЛЬНАЯ убыль (messages худеет, history не растёт) → 🔴,       РАЗЛИЧАЮЩИЙ
    код 1 — прогон №2 критерия карточки
  ④ переезд messages → messages_history — без тревоги, код 0              РАЗЛИЧАЮЩИЙ
  ⑤ таблица ИСЧЕЗЛА → 🔴 отдельным словом, код 1                          РАЗЛИЧАЮЩИЙ
  ⑥ МАСКИРОВКА РОСТОМ: строки пропали, а дамп в байтах ВЫРОС → всё равно  РАЗЛИЧАЮЩИЙ
    🔴 код 1 — ровно то, чего байтовый гард не видел вовсе
  ⑦ убыль в ОБЫЧНОЙ таблице (rules) → 🔴 «удалять никто не должен», код 1 РАЗЛИЧАЮЩИЙ
  ⑧ шапки счётчиков у прежнего дампа нет → ⚠ «сверить нечем», не молчание РАЗЛИЧАЮЩИЙ
  ⑨ ОБРАТНЫЙ ХОД ветки messages → случай ③ зеленеет у сломанной           РАЗЛИЧАЮЩИЙ
  ⑩ ОБРАТНЫЙ ХОД общей ветки → случай ⑦ зеленеет у сломанной              РАЗЛИЧАЮЩИЙ

🎯 Обратных хода ДВА, по одному на ветку тревоги: первая редакция ломала общую ветку
и мерила случаем ③ — а тот ходит веткой messages. Ослабление не теряло ни одного
красного, и «обратный ход» мерил не то, что ломал.

⛔ Живой базы и живого дампа не касается: каждый случай строит СВОЙ стенд.
⚠️ В стенде НИКАКИХ RANDOMBLOB: случайные байты в TEXT-колонке валят iterdump
   битым UTF-8 — приёмка краснела бы на смерти СТЕНДА, а не на предмете.

🩸 КАРТОЧКА #610 (2026-09-14): имена в backup-db.py переведены на английский
(тревоги→alerts, прежние_счётчики→previous_counts и т. п.) — тем же ходом переведены
и здесь. Смысл случаев ⑨/⑩ не изменился, изменился только якорь-строка (она ищет
английское имя переменной в тексте гарда, а не русское).
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
TOOL = SCRIPTS / "backup-db.py"
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def build_stand(d: pathlib.Path) -> pathlib.Path:
    """Мини-база с теми таблицами, чья убыль различается по-разному."""
    db = d / "stand.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE messages_history (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE read_batches (id INTEGER PRIMARY KEY, token TEXT)")
    con.execute("CREATE TABLE rules (k TEXT, v TEXT)")
    con.executemany("INSERT INTO messages (body) VALUES (?)",
                    [(f"записка {i} " + "х" * 60,) for i in range(20)])
    con.executemany("INSERT INTO phoenix_history (body) VALUES (?)",
                    [(f"версия {i} " + "х" * 90,) for i in range(15)])
    con.executemany("INSERT INTO read_batches (token) VALUES (?)",
                    [(f"t{i}",) for i in range(6)])
    con.executemany("INSERT INTO rules VALUES (?, ?)",
                    [(f"ключ{i}", f"значение{i}") for i in range(4)])
    con.commit()
    con.close()
    return db


def run_tool(db, out, *flags, script=TOOL):
    r = subprocess.run([sys.executable, str(script), "--db", str(db),
                        "--out", str(out), *flags],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def fresh_stand(pref: str):
    """Каждому случаю — свой стенд со снятым базовым дампом."""
    d = pathlib.Path(tempfile.mkdtemp(prefix=pref))
    db = build_stand(d)
    out = d / "stand.sql"
    code, output = run_tool(db, out, "--apply")
    if code != 0:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: базовый дамп стенда не снялся (код {code})\n{output}")
    return d, db, out


def sql(db, *stmts):
    con = sqlite3.connect(db)
    for s in stmts:
        con.execute(s)
    con.commit()
    con.close()


def weaken(d: pathlib.Path, anchor: str, replacement: str) -> pathlib.Path:
    """Копия гарда с ослабленной веткой; None-эквивалент — пустой путь при ненайденном якоре."""
    original = TOOL.read_text(encoding="utf-8")
    broken = original.replace(anchor, replacement, 1)
    if broken == original:
        return None
    weak_path = d / "prior.py"
    weak_path.write_text(broken, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    return weak_path


def main() -> int:
    ok = True
    cleanup_dirs = []
    try:
        # ① КОНТРОЛЬ: рост — молчит.
        d, db, out = fresh_stand("bite-shrink-1-")
        cleanup_dirs.append(d)
        sql(db, "INSERT INTO messages (body) VALUES ('новая записка без случайных байт')")
        code, output = run_tool(db, out)
        ok &= case("① КОНТРОЛЬ: база выросла — молчит, код 0",
                   code == 0 and "🔴" not in output and "⚠" not in output,
                   f"код {code}; красное здесь = вечно-красное, ему перестают верить",
                   differ=True)

        # ② ЗАКОННАЯ убыль — чистка истории. Прогон №1 критерия карточки.
        d, db, out = fresh_stand("bite-shrink-2-")
        cleanup_dirs.append(d)
        sql(db, "DELETE FROM phoenix_history WHERE id <= 8",
            "DELETE FROM read_batches WHERE id <= 3")
        code, output = run_tool(db, out)
        ok &= case("② законная убыль (чистка) → «ЗАКОННО», без тревоги, код 0",
                   code == 0 and "ЗАКОННО" in output and "🔴" not in output
                   and "phoenix_history" in output,
                   f"код {code}; прежний гард кричал бы здесь на исправной работе —"
                   " ради этого случая карточка и заведена", differ=True)

        # ③ ПОДОЗРИТЕЛЬНАЯ убыль — messages худеет без переезда. Прогон №2 критерия.
        d3, db3, out3 = fresh_stand("bite-shrink-3-")
        cleanup_dirs.append(d3)
        sql(db3, "DELETE FROM messages WHERE id <= 10")
        code3, output3 = run_tool(db3, out3)
        ok &= case("③ подозрительная убыль (messages без переезда) → 🔴, код 1",
                   code3 == 1 and "🔴" in output3 and "messages −10" in output3
                   and "НЕ объяснено" in output3,
                   f"код {code3}; тревога называет таблицу и число, а не «что-то усохло»",
                   differ=True)

        # ④ переезд messages → messages_history — закон.
        d, db, out = fresh_stand("bite-shrink-4-")
        cleanup_dirs.append(d)
        sql(db, "INSERT INTO messages_history (body) SELECT body FROM messages WHERE id <= 10",
            "DELETE FROM messages WHERE id <= 10")
        code, output = run_tool(db, out)
        ok &= case("④ переезд messages → messages_history — без тревоги, код 0",
                   code == 0 and "🔴" not in output,
                   f"код {code}; сумма сохранилась — split-history-table работает именно так",
                   differ=True)

        # ⑤ таблица исчезла — отдельное слово.
        d, db, out = fresh_stand("bite-shrink-5-")
        cleanup_dirs.append(d)
        sql(db, "DROP TABLE rules")
        code, output = run_tool(db, out)
        ok &= case("⑤ таблица ИСЧЕЗЛА → 🔴 отдельным словом, код 1",
                   code == 1 and "ИСЧЕЗЛА" in output and "rules" in output,
                   f"код {code}; «минус все строки» и «таблицы нет» — разные беды", differ=True)

        # ⑥ МАСКИРОВКА РОСТОМ: строки пропали, байты выросли — всё равно тревога.
        d, db, out = fresh_stand("bite-shrink-6-")
        cleanup_dirs.append(d)
        sql(db, "DELETE FROM messages WHERE id <= 10",
            "INSERT INTO rules VALUES ('жир', '" + "Ж" * 20000 + "')")
        code, output = run_tool(db, out)
        ok &= case("⑥ строки пропали, а дамп в байтах ВЫРОС → всё равно 🔴, код 1",
                   code == 1 and "messages −10" in output and "+" in output,
                   f"код {code}; байтовый гард здесь молчал — рост соседа маскировал потерю."
                   " Сверка строк видит", differ=True)

        # ⑦ убыль в ОБЫЧНОЙ таблице — общая ветка тревоги, своим случаем.
        d7, db7, out7 = fresh_stand("bite-shrink-7-")
        cleanup_dirs.append(d7)
        sql(db7, "DELETE FROM rules WHERE k IN ('ключ0','ключ1')")
        code7, output7 = run_tool(db7, out7)
        ok &= case("⑦ убыль в обычной таблице (rules) → 🔴 «удалять никто не должен», код 1",
                   code7 == 1 and "rules −2" in output7 and "никто не должен" in output7,
                   f"код {code7}; у этой ветки не было своего случая — обратный ход ⑩"
                   " без него мерил бы пустоту", differ=True)

        # ⑧ шапки нет — «сверить нечем», не молчание и не тревога.
        d, db, out = fresh_stand("bite-shrink-8-")
        cleanup_dirs.append(d)
        text = out.read_text(encoding="utf-8").splitlines()
        out.write_text("\n".join(l for l in text
                                 if not l.startswith("-- строк по таблицам:")) + "\n",
                       encoding="utf-8", newline="\n")
        sql(db, "DELETE FROM phoenix_history WHERE id <= 8")
        code, output = run_tool(db, out)
        ok &= case("⑧ шапки счётчиков нет → ⚠ «сверить нечем», код 0",
                   code == 0 and "нечем" in output,
                   f"код {code}; отказ мерить назван вслух — молчание читалось бы как"
                   " «всё хорошо»", differ=True)

        # ⑨ ОБРАТНЫЙ ХОД ветки messages: ослаблена → случай ③ зеленеет у сломанной.
        d9 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-9-"))
        cleanup_dirs.append(d9)
        weak9 = weaken(
            d9,
            'alerts.append(f"messages −{was - now}, а messages_history выросла лишь"',
            '_ = (f"messages −{was - now}, а messages_history выросла лишь"')
        if weak9 is None:
            ok &= case("⑨ ОБРАТНЫЙ ХОД ветки messages", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря ветки messages в гарде нет — он менялся,"
                       " правь приёмку")
        else:
            code9, _ = run_tool(db3, out3, script=weak9)   # состояние случая ③
            ok &= case("⑨ ОБРАТНЫЙ ХОД ветки messages — случай ③ ЗЕЛЕНЕЕТ у сломанной",
                       code9 == 0 and code3 == 1,
                       f"слабая {code9} против настоящей {code3} — ловит именно ветка"
                       " messages, а не что-то рядом", differ=True)

        # ⑩ ОБРАТНЫЙ ХОД общей ветки: ослаблена → случай ⑦ зеленеет у сломанной.
        d10 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-10-"))
        cleanup_dirs.append(d10)
        weak10 = weaken(
            d10,
            'alerts.append(f"{t} −{was - now} строк — удалять из неё никто не должен")',
            'pass')
        if weak10 is None:
            ok &= case("⑩ ОБРАТНЫЙ ХОД общей ветки", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря общей ветки в гарде нет — он менялся,"
                       " правь приёмку")
        else:
            code10, _ = run_tool(db7, out7, script=weak10)   # состояние случая ⑦
            ok &= case("⑩ ОБРАТНЫЙ ХОД общей ветки — случай ⑦ ЗЕЛЕНЕЕТ у сломанной",
                       code10 == 0 and code7 == 1,
                       f"слабая {code10} против настоящей {code7} — ловит именно общая"
                       " ветка", differ=True)
    finally:
        for d in cleanup_dirs:
            shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ГАРД УБЫЛИ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
