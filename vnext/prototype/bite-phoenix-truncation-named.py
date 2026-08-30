# -*- coding: utf-8 -*-
r"""bite-phoenix-truncation-named.py — приёмка находки @RCC (записка #4472 §④):
отчёт сохранения памяти обрезал список исчезнувших СТРОК до трёх и МОЛЧАЛ об остатке.

ПОВОД. Замер @RCC 30.08 11:57 UTC на своей же памяти: «исчезло дословно 16 (11%)»,
НАЗВАНО ИМЁН 3, строки «…и ещё 13» нет. Соседняя ветка того же отчёта — про БЛОКИ —
остаток называет. Один инструмент, две ветки, разное поведение.

⚡ ПОЧЕМУ ЭТО ДОРОЖЕ ОПРЯТНОСТИ. У отчёта две строки: ЧИСЛО и ИМЕНА. @ING потерял
четыре урока, прочитав ЧИСЛО вместо имён, и вывел урок «читай имена». Роль, исполнившая
его урок буквально, видела ТРИ имени из шестнадцати — то есть послушание уводило от правды.

⚖️ ГРАНИЦА, названная сразу: порог ТРИ остаётся. Предмет не в обрезке (она бережёт вывод
от заслонения тревоги), а в МОЛЧАНИИ о ней.

Всё на копии базы (mezo_stand); живая база только читается.

Случаи:
  ① исчезло больше трёх — остаток НАЗВАН числом
  ② остаток назван ВЕРНО: «ещё N» + сколько исчезло всего
  ③ ВСТРЕЧНЫЙ: исчезло РОВНО три — строки об остатке НЕТ (признак не горит всегда)
  ④ ВСТРЕЧНЫЙ: исчезло меньше трёх — строки об остатке НЕТ
  ⑤ имена по-прежнему печатаются: обрезка не заменила список числом
  ⑥ ВСТРЕЧНЫЙ: ничего не исчезло — ни имён, ни остатка
  ⑦ контроль: своих следов в живой базе нет
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

ИСПЫТУЕМЫЙ = mezo_target.script("save-phoenix.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0
РОЛЬ = "ZZP"


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
                MEZO_CONTAINER=str(mezo_paths.container_root()))


def сохранить(db, тело, путь):
    Path(путь).write_text(тело, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(ИСПЫТУЕМЫЙ), "--db", str(db), "--role", РОЛЬ,
         "--section", "state", "--file", str(путь), "--allow-shrink"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


stand = mezo_stand.new("phoenix-trunc-")
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("DELETE FROM tool_leases")            # чужая занятость приёмку не красит
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба обрезки')",
            (РОЛЬ,))
con.commit()
con.close()
файл = stand / "тело.md"


def тело(строк, метка="строка"):
    шапка = "# Раздел\n\n**Жирная строка разметки**\n\n"
    return шапка + "\n".join(f"{метка} номер {i}: содержательное утверждение" for i in range(строк))


# ═══ основа: 20 содержательных строк
сохранить(db, тело(20), файл)

# ═══ ① ② ⑤ исчезает 16 из 20 — остаток обязан быть назван
rc1, out1 = сохранить(db, тело(4), файл)
case("① исчезло больше трёх — остаток НАЗВАН числом", "… и ещё" in out1, f"код {rc1}")
case("② остаток назван ВЕРНО: и «ещё N», и сколько исчезло всего",
     "… и ещё 13" in out1 and "исчезло 16" in out1,
     [s.strip() for s in out1.splitlines() if "и ещё" in s][:1])
# ⚖️ Считаем ТОЛЬКО строки-имена, без строки остатка: первая редакция брала все «✂ »
# разом и потому краснела ВМЕСТЕ с ① при откате починки — то есть мерила не своё.
# Третий случай этого класса за смену, и все три поймало число, названное ДО прогона.
имена1 = [s for s in out1.splitlines() if "✂ " in s and "и ещё" not in s]
case("⑤ имена по-прежнему печатаются: обрезка не заменила список числом",
     len(имена1) == 3, f"строк-имён: {len(имена1)}")

# ═══ ③ ВСТРЕЧНЫЙ: исчезает РОВНО три
сохранить(db, тело(20), файл)
rc2, out2 = сохранить(db, тело(17), файл)
case("③ ВСТРЕЧНЫЙ: исчезло РОВНО три — строки об остатке НЕТ",
     "… и ещё" not in out2 and out2.count("✂ ") == 3, f"код {rc2}")

# ═══ ④ ВСТРЕЧНЫЙ: исчезает одна
сохранить(db, тело(20), файл)
rc3, out3 = сохранить(db, тело(19), файл)
case("④ ВСТРЕЧНЫЙ: исчезла одна — строки об остатке НЕТ",
     "… и ещё" not in out3 and out3.count("✂ ") == 1, f"код {rc3}")

# ═══ ⑥ ВСТРЕЧНЫЙ: ничего не исчезло
сохранить(db, тело(20), файл)
rc4, out4 = сохранить(db, тело(20) + "\nдописанная строка без потерь\n", файл)
case("⑥ ВСТРЕЧНЫЙ: ничего не исчезло — ни имён, ни остатка",
     "… и ещё" not in out4 and "✂ " not in out4, f"код {rc4}")

# ═══ ⑦ контроль
живой = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы = живой.execute("SELECT COUNT(*) FROM roles WHERE role=?", (РОЛЬ,)).fetchone()[0]
следы += живой.execute("SELECT COUNT(*) FROM phoenix WHERE role=?", (РОЛЬ,)).fetchone()[0]
живой.close()
case("⑦ контроль: своих следов в живой базе нет", следы == 0, f"следов: {следы}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
