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

ПРОВЕРКА = pathlib.Path(__file__).with_name("check-phoenix-invariant.py")
ИНСТРУМЕНТ = (mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
              / "save-phoenix.py")
БАЗА = mezo_paths.container_root(__file__) / ".mezosync" / "mezosync.db"
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def копия(d: pathlib.Path) -> pathlib.Path:
    db = d / "mezosync.db"
    shutil.copy(БАЗА, db)
    return db


def прогон(db: pathlib.Path, разбор: pathlib.Path = None):
    r = subprocess.run([sys.executable, str(разбор or ПРОВЕРКА), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    for нужен in (ПРОВЕРКА, ИНСТРУМЕНТ, БАЗА):
        if not нужен.exists():
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет файла — {нужен}")
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-"))
    try:
        # ① КОНТРОЛЬ: нетронутая копия живой базы — молчит.
        db = копия(d)
        код, _ = прогон(db)
        ok &= case("① КОНТРОЛЬ: копия живой базы — молчит",
                   код == 0,
                   f"код {код}; красное здесь значило бы, что мы включаем вечно-красное —"
                   " оно учит не верить красному", differ=True)

        # ② ПРАВКА МИМО ИНСТРУМЕНТА — красное, поимённо.
        con = sqlite3.connect(db)
        con.execute("UPDATE phoenix SET body = body || ' ПРАВКА МИМО' "
                    "WHERE role='PROTO' AND section='state'")
        con.commit()
        con.close()
        код2, вывод2 = прогон(db)
        ok &= case("② правка тела МИМО инструмента — красное, раздел назван поимённо",
                   код2 == 1 and "PROTO/state" in вывод2 and "МИМО ИНСТРУМЕНТА" in вывод2,
                   f"код {код2}; ровно тот путь, который нельзя закрыть — только заметить",
                   differ=True)

        # ③ ЗАКОННАЯ ЗАПИСЬ ШТАТНЫМ ИНСТРУМЕНТОМ — молчит. Свежая копия, своё состояние.
        d3 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-3-"))
        db3 = копия(d3)
        ф = d3 / "тело.md"
        con = sqlite3.connect(f"file:{db3.as_posix()}?mode=ro", uri=True)
        тело = con.execute("SELECT body FROM phoenix WHERE role='PROTO'"
                           " AND section='state'").fetchone()[0]
        con.close()
        ф.write_text(тело + chr(10) + "дописано штатно" + chr(10), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--db", str(db3),
                            "--role", "PROTO", "--section", "state", "--file", str(ф),
                            "--actor", "PROTO"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        код3, _ = прогон(db3)
        ok &= case("③ законная запись ШТАТНЫМ инструментом — после неё молчит",
                   r.returncode == 0 and код3 == 0,
                   f"запись код {r.returncode} · проверка код {код3}; встречный к ② —"
                   " иначе проверка красна на всё подряд и её перестают читать",
                   differ=True)
        shutil.rmtree(d3, ignore_errors=True)

        # ④ РАЗДЕЛ БЕЗ ИСТОРИИ — отдельное слово, не то же, что у правки.
        d4 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-4-"))
        db4 = копия(d4)
        con = sqlite3.connect(db4)
        con.execute("INSERT INTO phoenix (role, section, body, saved_at)"
                    " VALUES ('ФАНТОМ','state','раздел мимо всего',datetime('now'))")
        con.commit()
        con.close()
        код4, вывод4 = прогон(db4)
        ok &= case("④ раздел, вставленный мимо инструмента И посева, — «версий нет вовсе»",
                   код4 == 1 and "БЕЗ ИСТОРИИ" in вывод4 and "ФАНТОМ" in вывод4,
                   f"код {код4}; свести с ② значило бы искать «какую версию правили»"
                   " у раздела, у которого версий не было никогда", differ=True)
        shutil.rmtree(d4, ignore_errors=True)

        # ⑤ БАЗА БЕЗ ТАБЛИЦЫ ИСТОРИИ — отказ мерить, не «чисто».
        d5 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-5-"))
        db5 = копия(d5)
        con = sqlite3.connect(db5)
        con.execute("DROP TABLE phoenix_history")
        con.commit()
        con.close()
        код5, вывод5 = прогон(db5)
        ok &= case("⑤ база БЕЗ таблицы истории — код 2 «мерить нечем», не «чисто»",
                   код5 == 2 and "нечем" in вывод5,
                   f"код {код5}; сказать тут «инвариант держится» — выдать бессилие"
                   " за исправность", differ=True)
        shutil.rmtree(d5, ignore_errors=True)

        # ⑥ ОБРАТНЫЙ ХОД: ослабляем сравнение до «есть хоть какая-то версия» —
        #    случай ② обязан позеленеть у сломанной копии.
        цел = ПРОВЕРКА.read_text(encoding="utf-8")
        поломка = цел.replace("elif row[0] != (body or \"\"):",
                              "elif False:", 1)
        if поломка == цел:
            ok &= case("⑥ ОБРАТНЫЙ ХОД: сравнение ослаблено — случай ② зеленеет", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: места сравнения в проверке нет — она менялась,"
                       " правь приёмку. Молча пропустить нельзя: зелёный без опыта")
        else:
            d6 = pathlib.Path(tempfile.mkdtemp(prefix="bite-invariant-6-"))
            слаб = d6 / "прежняя.py"
            слаб.write_text(поломка, encoding="utf-8")
            shutil.copy(ПРОВЕРКА.with_name("mezo_paths.py"), d6 / "mezo_paths.py")
            код6, _ = прогон(db, разбор=слаб)   # db — та же копия с правкой мимо (②)
            ok &= case("⑥ ОБРАТНЫЙ ХОД: сравнение ослаблено — случай ② ЗЕЛЕНЕЕТ у сломанной",
                       код6 == 0 and код2 == 1,
                       f"слабая {код6} против настоящей {код2} — разница и есть"
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
