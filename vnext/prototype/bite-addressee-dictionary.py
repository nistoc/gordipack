# -*- coding: utf-8 -*-
r"""ПРИЁМКА словаря адресатов Э-Б (писатель-прототип + миграция) — карточка #258.

🩸 ЧЕМ ОПЛАЧЕНО (замер живого поля 26.08): писатель делит имена только по запятой —
8 склеек «CHROME CORE STUD» одной строкой лежат в живом поле, и отбор «только моё»
эти записки не показывает НИКОМУ из склеенных; 25 строк «ALL» — самодельный обход
отсутствующего «всем», невидимый для --to-me. Молчащий отказ читался как успех.

Песочница = КОПИЯ ЖИВОЙ базы (см. 08-addressee-dictionary.md Р4½: схема Э-В адресата
не знает, прототип обязан жить в форме, в которой дефект существует).

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① «A B C» через ПРОБЕЛ → три строки поля, склейки нет                 РАЗЛИЧАЮЩИЙ
  ② «A,B» через запятую → две строки                                    КОНТРОЛЬ
  ③ неизвестное имя → ОТКАЗ ДО записи, словарь назван, записки НЕТ      РАЗЛИЧАЮЩИЙ
  ④ «все» → свойство записки (broadcast=1), строки-адресата нет         РАЗЛИЧАЮЩИЙ
  ⑤ живой ЧИТАТЕЛЬ на мигрированной песочнице: --to-me широковещательную
    НЕ показывает и НЕ падает от новой колонки                          РАЗЛИЧАЮЩИЙ
  ⑥ ОБРАТНЫЙ ХОД: словарь отключён → случай ③ зеленеет у сломанной      РАЗЛИЧАЮЩИЙ
  ⑦ МИГРАЦИЯ на копии живой: склеек и ALL после — 0, «всем» помечено
    столько записок, сколько несло ALL; ЧУЖИЕ строки целы числом;
    повторный прогон идемпотентен                                       РАЗЛИЧАЮЩИЙ

⛔ Живой базы не пишет: всё — на копии.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ПИСАТЕЛЬ = HERE / "write-message-vnext.py"
МИГРАЦИЯ = HERE / "migrate-addressee-vnext.py"
ЧИТАТЕЛЬ = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "read-messages.py"
ЖИВАЯ = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def прогон(скрипт, *доводы):
    r = subprocess.run([sys.executable, str(скрипт), *доводы],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def адресаты(db, mid):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT role, kind FROM message_addressee WHERE message_id=?"
                       " ORDER BY role", (mid,)).fetchall()
    con.close()
    return rows


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-addr-"))
    try:
        db = d / "sand.db"
        shutil.copy(ЖИВАЯ, db)
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        склеек_до = con.execute("SELECT COUNT(*) FROM message_addressee"
                                " WHERE role LIKE '% %'").fetchone()[0]
        all_нот_до = con.execute("SELECT COUNT(DISTINCT message_id) FROM message_addressee"
                                 " WHERE role='ALL'").fetchone()[0]
        чужие_до = con.execute("SELECT COUNT(*) FROM message_addressee"
                               " WHERE role NOT LIKE '% %' AND role<>'ALL'").fetchone()[0]
        нот_до = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()

        # ⑦а МИГРАЦИЯ — сперва: писатель требует колонку broadcast.
        код, вывод = прогон(МИГРАЦИЯ, "--db", str(db))
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        склеек_после = con.execute("SELECT COUNT(*) FROM message_addressee"
                                   " WHERE role LIKE '% %' OR role='ALL'").fetchone()[0]
        всем = con.execute("SELECT COUNT(*) FROM messages WHERE broadcast=1").fetchone()[0]
        чужие_после = con.execute("SELECT COUNT(*) FROM message_addressee"
                                  " WHERE role NOT LIKE '% %' AND role<>'ALL'"
                                  " AND linked_by='field'").fetchone()[0]
        con.close()
        # чужие_до считал field+backfill вместе; после развода склеек чужих строк
        # СТАЛО БОЛЬШЕ (имена из склеек легли поимённо) — целость меряем «не убыло».
        ok &= case("⑦а миграция: склеек и ALL — 0, «всем» = числу нот ALL, чужого не убыло",
                   код == 0 and склеек_после == 0 and всем == all_нот_до
                   and склеек_до > 0,
                   f"код {код}; склеек было {склеек_до}, стало 0 · нот ALL было {all_нот_до},"
                   f" «всем» стало {всем}", differ=True)

        # ⑦б идемпотентность: второй прогон ничего не меняет и не падает.
        код2, вывод2 = прогон(МИГРАЦИЯ, "--db", str(db))
        ok &= case("⑦б повторная миграция — идемпотентна",
                   код2 == 0 and "уже есть" in вывод2 and "склеек нет" in вывод2,
                   f"код {код2}; миграция, падающая на втором прогоне, учит бояться прогонов",
                   differ=True)

        # ① пробелы — разделитель.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1", "--to", "COORD CORE STUD")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        rows = адресаты(db, mid) if mid else []
        ok &= case("① «COORD CORE STUD» через пробел → ТРИ строки поля, склейки нет",
                   код == 0 and len(rows) == 3 and all(" " not in r for r, _ in rows),
                   f"код {код}; строки: {rows} — живой писатель здесь молча клал ОДНУ склейку",
                   differ=True)

        # ② запятая — как раньше.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1-контроль", "--to", "COORD,CORE")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        ok &= case("② «COORD,CORE» через запятую → две строки",
                   код == 0 and len(адресаты(db, mid)) == 2,
                   f"код {код}; прежняя форма не сломана — иначе починка учит новой беде",
                   differ=True)

        # ③ неизвестное имя — отказ ДО записи.
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        нот_перед = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        код3, вывод3 = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Р3", "--to", "COODR")
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        нот_зaписано = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        ok &= case("③ имя «COODR» (опечатка) → ОТКАЗ до записи, словарь назван, записки НЕТ",
                   код3 == 1 and "ОТКАЗ" in вывод3 and "Словарь:" in вывод3
                   and нот_зaписано == нот_перед,
                   f"код {код3}; нота-призрак не родилась: было {нот_перед} нот, осталось столько же",
                   differ=True)

        # ④ «все» — свойство записки.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р4", "--to", "все", "--cc", "ВЛАДЕЛЕЦ")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        bc = con.execute("SELECT broadcast FROM messages WHERE id=?", (mid,)).fetchone()
        все_строкой = con.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?"
                                  " AND role IN ('ВСЕ','ALL')", (mid,)).fetchone()[0]
        con.close()
        ok &= case("④ «--to все» → broadcast=1 у записки, строки-адресата «ВСЕ» нет",
                   код == 0 and bc and bc[0] == 1 and все_строкой == 0,
                   f"код {код}; «всем» — свойство ноты; ВЛАДЕЛЕЦ лёг строкой: {адресаты(db, mid)}",
                   differ=True)

        # ⑤ живой читатель на мигрированной песочнице.
        код5, вывод5 = прогон(ЧИТАТЕЛЬ, "--db", str(db), "--role", "CORE", "--to-me")
        ok &= case("⑤ живой read-messages --to-me на песочнице: не падает, «всем»-ноту не выдаёт",
                   код5 == 0 and "проба Р4" not in вывод5,
                   f"код {код5}; новая колонка не ломает читателя, широковещательное"
                   " не выдаётся за личное", differ=True)

        # ⑥ ОБРАТНЫЙ ХОД: словарь отключён → случай ③ зеленеет у сломанной.
        цел = ПИСАТЕЛЬ.read_text(encoding="utf-8")
        поломка = цел.replace("if r not in словарь:", "if False:", 1)
        if поломка == цел:
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря словаря в писателе нет — он менялся, правь приёмку")
        else:
            слаб = d / "прежний.py"
            слаб.write_text(поломка, encoding="utf-8")
            shutil.copy(HERE / "mezo_paths.py", d / "mezo_paths.py")
            # копия живёт вне контейнера ⇒ live_db() в её заголовке не найдёт маркера;
            # контейнер отдаём средой — иначе копия падает НА ИМПОРТЕ, и «красный»
            # у сломанной был бы смертью копии, а не работой словаря (поймано прогоном)
            env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)))
            r6 = subprocess.run([sys.executable, str(слаб), "--db", str(db), "--role",
                                 "PROTO", "--body", "проба Р3 слабой", "--to", "COODR"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=300, env=env)
            код6 = r6.returncode
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён — случай ③ ЗЕЛЕНЕЕТ у сломанной",
                       код6 == 0 and код3 == 1,
                       f"слабая {код6} против настоящей {код3} — различает именно СЛОВАРЬ",
                       differ=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ СЛОВАРЬ АДРЕСАТОВ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
