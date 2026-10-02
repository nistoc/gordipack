# -*- coding: utf-8 -*-
r"""ПРИЁМКА проверки «текст памяти правили мимо инструмента» — карточка #252.

🩸 ЧЕМ ОПЛАЧЕНО. Условие «новейшая версия равна телу» — то, на чём держится вся защита
памяти, — печаталось один раз шагом схемы. Путей записи при этом три, и третий (прямой
SQL) не закрывается ничем: его можно только замечать. До этой проверки о нарушении
узнали бы чужим удивлением, как контур узнал о потере памяти 21.08.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① КОНТРОЛЬ: копия живой базы — молчит (иначе включаем вечно-красное)   РАЗЛИЧАЮЩИЙ
  ② правка тела МИМО инструмента — красное, раздел назван поимённо        РАЗЛИЧАЮЩИЙ
  ③ законная запись ШТАТНЫМ инструментом — после неё молчит               РАЗЛИЧАЮЩИЙ
  ④ раздел, вставленный мимо инструмента И посева, — красное ОТДЕЛЬНЫМ    РАЗЛИЧАЮЩИЙ
    словом («версий нет вовсе»), не тем же, что у правки
  ⑤ база БЕЗ таблицы истории — код 2 «мерить нечем», не «чисто»           РАЗЛИЧАЮЩИЙ
  ⑥ ОБРАТНЫЙ ХОД: сравнение ослаблено до «есть хоть какая-то версия» —    РАЗЛИЧАЮЩИЙ
    случай ② обязан ПОЗЕЛЕНЕТЬ у сломанной копии

🎯 ⑥ — главный: без него зелень ①③ означала бы «сегодня не болит», а не «проверка
различает». Ломается ровно то, что и есть предмет: СИЛА сравнения.

⛔ Живой базы не касается: каждый случай строит СВОЮ копию.

🩹 ДОГОН (карточка #667, пустой новый контур): случаи ②③④⑥ раньше мерили на разделе
ЖИВОЙ роли PROTO (role='PROTO', section='state') — на свежесобранном контуре такой
роли в памяти нет вовсе, SELECT отвечал NULL, и приёмка падала трассой TypeError
прямо на случае ③. Подставная роль/раздел (BITEINVARIANT/state) заводится штатным
инструментом (save-phoenix.py) НА КОПИИ, тем же ходом, что и тело, и история версий —
приёмка продолжает проверять МЕХАНИЗМ (а не слова чужой памяти) и на пустом контуре.
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
import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

CHECK_TOOL = pathlib.Path(__file__).with_name("check-phoenix-invariant.py")
SAVE_TOOL = (mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
             / "save-phoenix.py")
LIVE_DB = mezo_paths.container_root(__file__) / ".mezosync" / "mezosync.db"

# Подставная роль/раздел приёмки — не зависит от того, какие роли и разделы памяти
# уже есть в контуре (живом или пустом свежесобранном).
TEST_ROLE = "BITEINVARIANT"
TEST_SECTION = "state"
PHANTOM_ROLE = "BITEPHANTOM"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def snapshot(d: pathlib.Path) -> pathlib.Path:
    db = d / "mezosync.db"
    mezo_stand.snapshot_db(LIVE_DB, db)
    return db


def run_check(db: pathlib.Path, checker: pathlib.Path = None):
    r = subprocess.run([sys.executable, str(checker or CHECK_TOOL), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def seed_subject(db: pathlib.Path, body: str) -> None:
    """Завести подставную роль/раздел приёмки штатным инструментом (save-phoenix.py):
    он пишет И тело, И версию истории ТЕМ ЖЕ ходом — ровно то согласованное состояние,
    на котором инвариант обязан молчать (случай ①, control)."""
    body_file = db.parent / "subject-body.md"
    body_file.write_text(body, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SAVE_TOOL), "--db", str(db),
                        "--role", TEST_ROLE, "--section", TEST_SECTION,
                        "--file", str(body_file), "--actor", TEST_ROLE],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    if r.returncode != 0:
        sys.exit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: заведение подставного раздела приёмки "
                 f"(save-phoenix.py) отказало кодом {r.returncode}:\n"
                 f"{r.stdout}{r.stderr}")


def main() -> int:
    ok = True
    for needed in (CHECK_TOOL, SAVE_TOOL, LIVE_DB):
        if not needed.exists():
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет файла — {needed}")
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-"))
    try:
        # ① КОНТРОЛЬ: копия живой базы + своя подставная роль, заведённая штатно, — молчит.
        db = snapshot(d)
        seed_subject(db, "подставной раздел приёмки bite-phoenix-invariant: версия 1")
        code, _ = run_check(db)
        ok &= case("① КОНТРОЛЬ: копия живой базы — молчит",
                   code == 0,
                   f"код {code}; красное здесь значило бы, что мы включаем вечно-красное —"
                   " оно учит не верить красному", differ=True)

        # ② ПРАВКА МИМО ИНСТРУМЕНТА — красное, поимённо.
        con = sqlite3.connect(db)
        con.execute("UPDATE phoenix SET body = body || ' ПРАВКА МИМО' "
                    "WHERE role=? AND section=?", (TEST_ROLE, TEST_SECTION))
        con.commit()
        con.close()
        code2, output2 = run_check(db)
        subject = f"{TEST_ROLE}/{TEST_SECTION}"
        ok &= case("② правка тела МИМО инструмента — красное, раздел назван поимённо",
                   code2 == 1 and subject in output2 and "МИМО ИНСТРУМЕНТА" in output2,
                   f"код {code2}; ровно тот путь, который нельзя закрыть — только заметить",
                   differ=True)

        # ③ ЗАКОННАЯ ЗАПИСЬ ШТАТНЫМ ИНСТРУМЕНТОМ — молчит. Своя свежая копия со своим посевом.
        d3 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-3-"))
        db3 = snapshot(d3)
        seed_subject(db3, "подставной раздел приёмки bite-phoenix-invariant: версия 1")
        con = sqlite3.connect(f"file:{db3.as_posix()}?mode=ro", uri=True)
        body_text = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                                (TEST_ROLE, TEST_SECTION)).fetchone()[0]
        con.close()
        body_file = d3 / "body.md"
        body_file.write_text(body_text + chr(10) + "дописано штатно" + chr(10),
                             encoding="utf-8")
        r = subprocess.run([sys.executable, str(SAVE_TOOL), "--db", str(db3),
                            "--role", TEST_ROLE, "--section", TEST_SECTION,
                            "--file", str(body_file), "--actor", TEST_ROLE],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        code3, _ = run_check(db3)
        ok &= case("③ законная запись ШТАТНЫМ инструментом — после неё молчит",
                   r.returncode == 0 and code3 == 0,
                   f"запись код {r.returncode} · проверка код {code3}; встречный к ② —"
                   " иначе проверка красна на всё подряд и её перестают читать",
                   differ=True)
        shutil.rmtree(d3, ignore_errors=True)

        # ④ РАЗДЕЛ БЕЗ ИСТОРИИ — отдельное слово, не то же, что у правки.
        d4 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-4-"))
        db4 = snapshot(d4)
        con = sqlite3.connect(db4)
        con.execute("INSERT INTO phoenix (role, section, body, saved_at)"
                    " VALUES (?, 'state', 'раздел мимо всего', datetime('now'))",
                    (PHANTOM_ROLE,))
        con.commit()
        con.close()
        code4, output4 = run_check(db4)
        ok &= case("④ раздел, вставленный мимо инструмента И посева, — «версий нет вовсе»",
                   code4 == 1 and "БЕЗ ИСТОРИИ" in output4 and PHANTOM_ROLE in output4,
                   f"код {code4}; свести с ② значило бы искать «какую версию правили»"
                   " у раздела, у которого версий не было никогда", differ=True)
        shutil.rmtree(d4, ignore_errors=True)

        # ⑤ БАЗА БЕЗ ТАБЛИЦЫ ИСТОРИИ — отказ мерить, не «чисто».
        d5 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-5-"))
        db5 = snapshot(d5)
        con = sqlite3.connect(db5)
        con.execute("DROP TABLE phoenix_history")
        con.commit()
        con.close()
        code5, output5 = run_check(db5)
        ok &= case("⑤ база БЕЗ таблицы истории — код 2 «мерить нечем», не «чисто»",
                   code5 == 2 and "нечем" in output5,
                   f"код {code5}; сказать тут «инвариант держится» — выдать бессилие"
                   " за исправность", differ=True)
        shutil.rmtree(d5, ignore_errors=True)

        # ⑥ ОБРАТНЫЙ ХОД: ослабляем сравнение до «есть хоть какая-то версия» —
        #    случай ② обязан позеленеть у сломанной копии.
        original_text = CHECK_TOOL.read_text(encoding="utf-8")
        patched_text = original_text.replace("elif row[0] != (body or \"\"):",
                                              "elif False:", 1)
        if patched_text == original_text:
            ok &= case("⑥ ОБРАТНЫЙ ХОД: сравнение ослаблено — случай ② зеленеет", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: места сравнения в проверке нет — она менялась,"
                       " правь приёмку. Молча пропустить нельзя: зелёный без опыта")
        else:
            d6 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-6-"))
            weak_copy = d6 / "weak-check.py"
            weak_copy.write_text(patched_text, encoding="utf-8")
            shutil.copy(CHECK_TOOL.with_name("mezo_paths.py"), d6 / "mezo_paths.py")
            code6, _ = run_check(db, checker=weak_copy)   # db — та же копия с правкой мимо (②)
            ok &= case("⑥ ОБРАТНЫЙ ХОД: сравнение ослаблено — случай ② ЗЕЛЕНЕЕТ у сломанной",
                       code6 == 0 and code2 == 1,
                       f"слабая {code6} против настоящей {code2} — разница и есть"
                       " доказательство, что ловит именно СИЛА сравнения", differ=True)
            shutil.rmtree(d6, ignore_errors=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ПРОВЕРКА ИНВАРИАНТА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
