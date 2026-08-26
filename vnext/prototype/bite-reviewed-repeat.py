# -*- coding: utf-8 -*-
r"""ПРИЁМКА накопления --reviewed в write-message.py — карточка #253.

🩸 ЧЕМ ОПЛАЧЕНО (COORD, 25.08 08:07 UTC): три «--reviewed <файл>» подряд молча записали
ОДИН жест — последний; строка «разбор записан» об одном имени прочлась подтверждением
всей операции. Молчащий отказ в подвиде «частичный успех»: треть работы сделана,
отчёт о ней честен, об остальных двух третях — тишина.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① повтор флага ×3 ......... ТРИ жеста в bridge_reviewed, три строки в выводе  РАЗЛИЧАЮЩИЙ
  ② список через запятую .... те же ТРИ — числа форм РАВНЫ (критерий карточки)  КОНТРОЛЬ
  ③ смешанная форма ......... «--reviewed a,b --reviewed c» → три               РАЗЛИЧАЮЩИЙ
  ④ ОБРАТНЫЙ ХОД: накопление снято (прежнее объявление) → случай ① даёт ОДИН
    у сломанной копии — разница и есть доказательство                           РАЗЛИЧАЮЩИЙ

⛔ Живой базы не пишет: каждый прогон — своя копия.
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

СКРИПТЫ = mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
ПИСАТЕЛЬ = СКРИПТЫ / "write-message.py"
ЖИВАЯ = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def жестов(db, метка):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM bridge_reviewed WHERE file_name LIKE ?",
                    (f"{метка}%",)).fetchone()[0]
    con.close()
    return n


def прогон(db, нота, метка, *формы, скрипт=ПИСАТЕЛЬ):
    # Тело ноты — СВОЁ на случай: писатель отвергает повтор тела как дубль (код 3),
    # и случаи ②③④ на общей ноте умирали об эту защиту, а не о предмете приёмки.
    нота.write_text(f"проба приёмки жестов разбора {метка} — записка стенда\n",
                    encoding="utf-8")
    # PYTHONPATH на каталог писателя: слабая копия живёт в чужом каталоге, и без него
    # умирает на ПЕРВОМ ЖЕ импорте (mezo_paths, dryrun…) — красный был бы гибелью
    # копии, а не работой накопления. Копировать модули поимённо нельзя: список протухает.
    env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)),
               PYTHONPATH=str(СКРИПТЫ))
    r = subprocess.run([sys.executable, str(скрипт), "--db", str(db), "--role", "PROTO",
                        "--file", str(нота), *формы],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or ""), жестов(db, метка)


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-reviewed-"))
    try:
        db = d / "sand.db"
        shutil.copy(ЖИВАЯ, db)
        нота = d / "нота.md"

        # ① повтор флага ×3.
        код, вывод, n1 = прогон(db, нота, "п1-",
                                "--reviewed", "п1-один.md",
                                "--reviewed", "п1-два.md",
                                "--reviewed", "п1-три.md")
        ok &= case("① повтор флага ×3 → ТРИ жеста, три строки «разбор записан»",
                   код == 0 and n1 == 3 and вывод.count("разбор записан") == 3,
                   f"код {код}; жестов {n1}; ровно здесь COORD получил 1 из 3 молча",
                   differ=True)

        # ② список через запятую — числа форм равны (критерий).
        код, вывод, n2 = прогон(db, нота, "п2-",
                                "--reviewed", "п2-один.md,п2-два.md,п2-три.md")
        ok &= case("② список через запятую → те же ТРИ (формы равны — критерий карточки)",
                   код == 0 and n2 == 3 and n2 == n1,
                   f"код {код}; жестов {n2} против {n1} у повтора — числа сошлись",
                   differ=True)

        # ③ смешанная форма.
        код, вывод, n3 = прогон(db, нота, "п3-",
                                "--reviewed", "п3-один.md,п3-два.md",
                                "--reviewed", "п3-три.md")
        ok &= case("③ смешанная форма → три",
                   код == 0 and n3 == 3,
                   f"код {код}; жестов {n3}; смешение форм — самый вероятный живой вызов",
                   differ=True)

        # ④ ОБРАТНЫЙ ХОД: накопление снято → случай ① даёт ОДИН у сломанной.
        цел = ПИСАТЕЛЬ.read_text(encoding="utf-8")
        поломка = цел.replace('parser.add_argument("--reviewed", action="append",'
                              ' default=None, metavar="ФАЙЛ",',
                              'parser.add_argument("--reviewed", default=None,'
                              ' metavar="ФАЙЛ",', 1)
        поломка = поломка.replace(
            "for name in [n.strip() for кусок in args.reviewed\n"
            "                         for n in кусок.split(\",\") if n.strip()]:",
            "for name in [n.strip() for n in args.reviewed.split(\",\") if n.strip()]:", 1)
        if поломка == цел:
            ok &= case("④ ОБРАТНЫЙ ХОД: накопление снято", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якорей накопления в писателе нет — он менялся,"
                       " правь приёмку")
        else:
            слаб = d / "прежний.py"
            слаб.write_text(поломка, encoding="utf-8")
            код4, _, n4 = прогон(db, нота, "п4-",
                                 "--reviewed", "п4-один.md",
                                 "--reviewed", "п4-два.md",
                                 "--reviewed", "п4-три.md", скрипт=слаб)
            ok &= case("④ ОБРАТНЫЙ ХОД: накопление снято — у сломанной жестов ОДИН",
                       n4 == 1 and n1 == 3,
                       f"слабая {n4} против настоящей {n1} — теряет именно СНЯТОЕ накопление"
                       f" (код слабой {код4})", differ=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ НАКОПЛЕНИЕ ЖЕСТОВ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
