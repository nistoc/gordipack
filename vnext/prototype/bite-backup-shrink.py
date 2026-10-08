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

🩸 КАРТОЧКА #683 (2026-10-08, находка onto на приёмке Э3 и AIA ④-7): законная убыль, которой
не было в перечне, — пересборка записей памяти при сохранении раздела и перенос отметок
чужих ролей шагом схемы. Случаи:
  ⑬ раздел сохранён после прежней выгрузки, его записи удалены → законно, код 0  РАЗЛИЧАЮЩИЙ
  ⑭ ВСТРЕЧНЫЙ: записи удалены у НЕсохранённого раздела (рукой) → 🔴, код 1         РАЗЛИЧАЮЩИЙ
  ⑮ СМЕСЬ: один раздел сохранён, у другого записи удалены рукой → 🔴 называет     РАЗЛИЧАЮЩИЙ
    только несохранённый (сохранение одного раздела не прикрывает другой)
  ⑯ ОБРАТНЫЙ ХОД ветки записей → случай ⑬ ПРОВАЛИВАЕТСЯ у сломанной               РАЗЛИЧАЮЩИЙ
  ⑰ перенос role_rebirths → role_rebirths_foreign — без тревоги, код 0           РАЗЛИЧАЮЩИЙ
  ⑱ ВСТРЕЧНЫЙ: role_rebirths худеет без переноса → 🔴, код 1                      РАЗЛИЧАЮЩИЙ
  ⑲ ОБРАТНЫЙ ХОД ветки переносов → случай ⑰ ПРОВАЛИВАЕТСЯ у сломанной              РАЗЛИЧАЮЩИЙ
Обход мест удаления по коду пакета (08.10) нашёл ещё три переезда того же рода: свёртку
ленты в messages_archive и обратно (messages-fold.py) и возврат версий памяти из архива
(memory-history-fold.py). Переезд теперь судится по НОМЕРАМ строк, а не по росту цели:
  ⑳ свёртка messages → messages_archive под теми же номерами → код 0             РАЗЛИЧАЮЩИЙ
  ㉑ возврат messages_archive → messages → код 0                                  РАЗЛИЧАЮЩИЙ
  ㉒ ВСТРЕЧНЫЙ: архив худеет, лента растёт НОВЫМИ номерами → 🔴, код 1            РАЗЛИЧАЮЩИЙ
    (сверка счётом сказала бы «законно»: рост 3 больше убыли 2)
  ㉓ возврат phoenix_history_archive → phoenix_history → код 0                    РАЗЛИЧАЮЩИЙ
  ㉔ ОБРАТНЫЙ ХОД свёртки в ветке messages → случай ⑳ ПРОВАЛИВАЕТСЯ у сломанной   РАЗЛИЧАЮЩИЙ

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
import mezo_stand  # noqa: E402

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
    # Карточка #683: память роли и её записи; час сохранения раздела — заведомо старый,
    # «сохранён после прежней выгрузки» случай ставит сам.
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    con.execute("CREATE TABLE phoenix_records (id INTEGER PRIMARY KEY, role TEXT,"
                " section TEXT, subject TEXT, body TEXT)")
    con.execute("CREATE TABLE role_rebirths (id INTEGER PRIMARY KEY, role TEXT, at TEXT)")
    con.execute("CREATE TABLE role_rebirths_foreign (id INTEGER PRIMARY KEY, role TEXT, at TEXT)")
    # Карточка #683: архивы свёртки ленты и версий памяти; номера архива с лентой не
    # пересекаются — так их держат messages-fold.py и memory-history-fold.py.
    con.execute("CREATE TABLE messages_archive (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE phoenix_history_archive (id INTEGER PRIMARY KEY, body TEXT)")
    con.executemany("INSERT INTO messages_archive VALUES (?, ?)",
                    [(100 + i, f"свёрнутая записка {i}") for i in range(4)])
    con.executemany("INSERT INTO phoenix_history_archive VALUES (?, ?)",
                    [(200 + i, f"архивная версия {i}") for i in range(3)])
    con.executemany("INSERT INTO phoenix VALUES (?, ?, ?, '2026-01-01 00:00:00')",
                    [("ALPHA", "state", "положение дел"), ("ALPHA", "plan", "план")])
    con.executemany("INSERT INTO phoenix_records (role, section, subject, body) VALUES (?, ?, ?, ?)",
                    [("ALPHA", "state", f"запись {i}", "тело записи " + "х" * 40) for i in range(3)]
                    + [("ALPHA", "plan", f"шаг {i}", "тело шага " + "х" * 40) for i in range(2)])
    con.executemany("INSERT INTO role_rebirths (role, at) VALUES (?, ?)",
                    [(f"ЧУЖАЯ{i}", f"2026-09-0{i + 1} 10:00:00") for i in range(4)])
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
                       errors="replace", timeout=300,
                       env=mezo_stand.stand_env(pathlib.Path(db).parent))
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

        # ⑪ КАРТОЧКА #617 (замечание COORD): --out указывает на СУЩЕСТВУЮЩИЙ КАТАЛОГ →
        # отказ СЛОВАМИ, код ≠ 0, БЕЗ трассировки. Было: os.replace(tmp_sql, out) в
        # write_and_verify падал непойманным PermissionError (Windows) / IsADirectoryError
        # (POSIX) — трассировка вместо понятного отказа.
        d11 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-11-"))
        cleanup_dirs.append(d11)
        db11 = build_stand(d11)
        out_as_dir = d11 / "outdir"
        out_as_dir.mkdir()
        code11, output11 = run_tool(db11, out_as_dir, "--apply")
        ok &= case("⑪ --out указывает на СУЩЕСТВУЮЩИЙ КАТАЛОГ → отказ словами, код ≠ 0,"
                   " без трассировки",
                   code11 != 0 and "Traceback" not in output11
                   and "СУЩЕСТВУЮЩИЙ КАТАЛОГ" in output11,
                   f"код {code11}; «Traceback» в выводе: {'Traceback' in output11}", differ=True)

        # ⑫ ОБРАТНЫЙ ХОД: гард каталога снят → случай ⑪ ПРОВАЛИВАЕТСЯ (прежняя
        # трассировка возвращается вместо отказа словами).
        d12 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-12-"))
        cleanup_dirs.append(d12)
        weak12 = weaken(
            d12,
            '    if out.exists() and out.is_dir():\n'
            '        print(f"⛔ --out указывает на СУЩЕСТВУЮЩИЙ КАТАЛОГ, а не на файл: {out}")\n'
            '        print(f"   выгрузка НЕ ЗАПИСАНА: дай путь к ФАЙЛУ, например {out / \'mezosync.dump.sql\'}")\n'
            '        raise SystemExit(1)',
            '    pass  # П-#617: гард каталога снят')
        if weak12 is None:
            ok &= case("⑫ ОБРАТНЫЙ ХОД: гард каталога снят", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якорь гарда каталога не найден — backup-db.py"
                       " менялся, правь приёмку")
        else:
            code12, output12 = run_tool(db11, out_as_dir, "--apply", script=weak12)
            ok &= case("⑫ ОБРАТНЫЙ ХОД: без гарда каталога случай ⑪ ПРОВАЛИВАЕТСЯ"
                       " (трассировка вместо отказа словами)",
                       code12 != 0 and ("Traceback" in output12
                                        or "СУЩЕСТВУЮЩИЙ КАТАЛОГ" not in output12),
                       f"код {code12}; «Traceback» в выводе: {'Traceback' in output12};"
                       " «СУЩЕСТВУЮЩИЙ КАТАЛОГ» в выводе:"
                       f" {'СУЩЕСТВУЮЩИЙ КАТАЛОГ' in output12}", differ=True)

        # ⑬ КАРТОЧКА #683: раздел сохранён после прежней выгрузки — пересборка удалила его
        # записи. Так ведёт себя save-phoenix.py у любого контура (находка onto, Э3 шаг 0).
        d13, db13, out13 = fresh_stand("bite-shrink-13-")
        cleanup_dirs.append(d13)
        sql(db13, "DELETE FROM phoenix_records WHERE role='ALPHA' AND section='state' AND id IN (1, 2)",
            "UPDATE phoenix SET saved_at=datetime('now') WHERE role='ALPHA' AND section='state'")
        code13, output13 = run_tool(db13, out13)
        ok &= case("⑬ раздел сохранён, его записи удалены пересборкой → законно, код 0",
                   code13 == 0 and "🔴" not in output13
                   and "пересборка записей при сохранении памяти" in output13
                   and "ALPHA/state −2" in output13,
                   f"код {code13}; до карточки #683 здесь была тревога «удалять из неё никто"
                   " не должен» — она и остановила приёмку Э3 у onto", differ=True)

        # ⑭ ВСТРЕЧНЫЙ: записи удалены у раздела, который НЕ сохраняли, — рукой.
        d14, db14, out14 = fresh_stand("bite-shrink-14-")
        cleanup_dirs.append(d14)
        sql(db14, "DELETE FROM phoenix_records WHERE role='ALPHA' AND section='plan'")
        code14, output14 = run_tool(db14, out14)
        ok &= case("⑭ ВСТРЕЧНЫЙ: записи удалены у несохранённого раздела → 🔴, код 1",
                   code14 == 1 and "🔴" in output14 and "ALPHA/plan −2" in output14
                   and "НЕ объяснено" in output14,
                   f"код {code14}; таблицу НЕ внесли в перечень законной убыли целиком —"
                   " иначе удаление рукой прошло бы молча", differ=True)

        # ⑮ СМЕСЬ: state сохранён и почищен пересборкой, у plan записи удалены рукой.
        d15, db15, out15 = fresh_stand("bite-shrink-15-")
        cleanup_dirs.append(d15)
        sql(db15, "DELETE FROM phoenix_records WHERE role='ALPHA' AND section='state' AND id = 1",
            "UPDATE phoenix SET saved_at=datetime('now') WHERE role='ALPHA' AND section='state'",
            "DELETE FROM phoenix_records WHERE role='ALPHA' AND section='plan' AND id = 4")
        code15, output15 = run_tool(db15, out15)
        alert15 = next((l for l in output15.splitlines() if "phoenix_records" in l and "НЕ объяснено" in l), "")
        ok &= case("⑮ СМЕСЬ: сохранение одного раздела не прикрывает удаление в другом → 🔴,"
                   " названа только plan, код 1",
                   code15 == 1 and "ALPHA/plan −1" in alert15 and "ALPHA/state" not in alert15,
                   f"код {code15}; строка тревоги: {alert15.strip()[:160] or '— нет'}", differ=True)

        # ⑯ ОБРАТНЫЙ ХОД ветки записей: убрана → случай ⑬ снова тревожит.
        d16 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-16-"))
        cleanup_dirs.append(d16)
        weak16 = weaken(d16, "elif t == RECORDS_TABLE and conn is not None:", "elif False:")
        if weak16 is None:
            ok &= case("⑯ ОБРАТНЫЙ ХОД ветки записей", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря ветки записей в backup-db.py нет — он менялся,"
                       " правь приёмку")
        else:
            code16, _ = run_tool(db13, out13, script=weak16)   # состояние случая ⑬
            ok &= case("⑯ ОБРАТНЫЙ ХОД ветки записей — случай ⑬ ПРОВАЛИВАЕТСЯ у сломанной",
                       code16 == 1 and code13 == 0,
                       f"сломанная {code16} против настоящей {code13} — законность даёт именно"
                       " ветка записей", differ=True)

        # ⑰ перенос role_rebirths → role_rebirths_foreign (шаг схемы, находка AIA ④-7).
        d17, db17, out17 = fresh_stand("bite-shrink-17-")
        cleanup_dirs.append(d17)
        sql(db17, "INSERT INTO role_rebirths_foreign SELECT id, role, at FROM role_rebirths WHERE id <= 2",
            "DELETE FROM role_rebirths WHERE id <= 2")
        code17, output17 = run_tool(db17, out17)
        ok &= case("⑰ перенос role_rebirths → role_rebirths_foreign — без тревоги, код 0",
                   code17 == 0 and "🔴" not in output17
                   and "role_rebirths −2 → role_rebirths_foreign под теми же номерами (2)"
                   in output17,
                   f"код {code17}; у AIA здесь была тревога «role_rebirths −18»", differ=True)

        # ⑱ ВСТРЕЧНЫЙ: role_rebirths худеет, а перенос не вырос.
        d18, db18, out18 = fresh_stand("bite-shrink-18-")
        cleanup_dirs.append(d18)
        sql(db18, "DELETE FROM role_rebirths WHERE id <= 2")
        code18, output18 = run_tool(db18, out18)
        ok &= case("⑱ ВСТРЕЧНЫЙ: role_rebirths худеет без переноса → 🔴, код 1",
                   code18 == 1 and "переносом НЕ объяснено" in output18,
                   f"код {code18}; перенос признаётся только по номерам строк во второй"
                   " таблице", differ=True)

        # ⑲ ОБРАТНЫЙ ХОД ветки переносов: убрана → случай ⑰ снова тревожит.
        d19 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-19-"))
        cleanup_dirs.append(d19)
        weak19 = weaken(d19, "elif t in MOVES:", "elif False:")
        if weak19 is None:
            ok &= case("⑲ ОБРАТНЫЙ ХОД ветки переносов", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря ветки переносов в backup-db.py нет — он менялся,"
                       " правь приёмку")
        else:
            code19, _ = run_tool(db17, out17, script=weak19)   # состояние случая ⑰
            ok &= case("⑲ ОБРАТНЫЙ ХОД ветки переносов — случай ⑰ ПРОВАЛИВАЕТСЯ у сломанной",
                       code19 == 1 and code17 == 0,
                       f"сломанная {code19} против настоящей {code17}", differ=True)

        # ⑳ свёртка ленты: записки уезжают в messages_archive под теми же номерами.
        d20, db20, out20 = fresh_stand("bite-shrink-20-")
        cleanup_dirs.append(d20)
        sql(db20, "INSERT INTO messages_archive SELECT id, body FROM messages WHERE id <= 5",
            "DELETE FROM messages WHERE id <= 5")
        code20, output20 = run_tool(db20, out20)
        ok &= case("⑳ свёртка ленты messages → messages_archive — без тревоги, код 0",
                   code20 == 0 and "🔴" not in output20 and "свёртка ленты" in output20,
                   f"код {code20}; до правки здесь была тревога «messages −5 … переездом НЕ"
                   " объяснено» — счёт смотрел только на messages_history", differ=True)

        # ㉑ обратный ход свёртки: записки возвращаются из архива в ленту.
        d21, db21, out21 = fresh_stand("bite-shrink-21-")
        cleanup_dirs.append(d21)
        sql(db21, "INSERT INTO messages SELECT id, body FROM messages_archive WHERE id <= 101",
            "DELETE FROM messages_archive WHERE id <= 101")
        code21, output21 = run_tool(db21, out21)
        ok &= case("㉑ возврат из messages_archive в ленту — без тревоги, код 0",
                   code21 == 0 and "🔴" not in output21
                   and "messages_archive −2 → messages под теми же номерами (2)" in output21,
                   f"код {code21}", differ=True)

        # ㉒ ВСТРЕЧНЫЙ: архив худеет, а лента растёт НОВЫМИ записками. Счёт «цель выросла
        # не меньше» сказал бы «законно» — номера говорят «потеря».
        d22, db22, out22 = fresh_stand("bite-shrink-22-")
        cleanup_dirs.append(d22)
        sql(db22, "DELETE FROM messages_archive WHERE id <= 101",
            "INSERT INTO messages (body) VALUES ('новая 1'), ('новая 2'), ('новая 3')")
        code22, output22 = run_tool(db22, out22)
        ok &= case("㉒ ВСТРЕЧНЫЙ: архив худеет, лента растёт новыми номерами → 🔴, код 1",
                   code22 == 1 and "messages_archive −2" in output22
                   and "переносом НЕ объяснено" in output22,
                   f"код {code22}; рост ленты на 3 прикрыл бы потерю 2 при сверке счётом",
                   differ=True)

        # ㉓ возврат версий памяти из архива (memory-history-fold.py, обратный ход).
        d23, db23, out23 = fresh_stand("bite-shrink-23-")
        cleanup_dirs.append(d23)
        sql(db23, "INSERT INTO phoenix_history SELECT id, body FROM phoenix_history_archive",
            "DELETE FROM phoenix_history_archive")
        code23, output23 = run_tool(db23, out23)
        ok &= case("㉓ возврат phoenix_history_archive → phoenix_history — без тревоги, код 0",
                   code23 == 0 and "🔴" not in output23
                   and "phoenix_history_archive −3 → phoenix_history" in output23,
                   f"код {code23}", differ=True)

        # ㉔ ОБРАТНЫЙ ХОД свёртки в ветке messages: убрана → случай ⑳ снова тревожит.
        d24 = pathlib.Path(tempfile.mkdtemp(prefix="bite-shrink-24-"))
        cleanup_dirs.append(d24)
        weak24 = weaken(d24, "elif fold[0]:", "elif False:")
        if weak24 is None:
            ok &= case("㉔ ОБРАТНЫЙ ХОД свёртки ленты", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря свёртки в ветке messages нет — backup-db.py"
                       " менялся, правь приёмку")
        else:
            code24, _ = run_tool(db20, out20, script=weak24)   # состояние случая ⑳
            ok &= case("㉔ ОБРАТНЫЙ ХОД свёртки ленты — случай ⑳ ПРОВАЛИВАЕТСЯ у сломанной",
                       code24 == 1 and code20 == 0,
                       f"сломанная {code24} против настоящей {code20}", differ=True)
    finally:
        for d in cleanup_dirs:
            shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ГАРД УБЫЛИ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
