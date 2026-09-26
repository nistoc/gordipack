#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА СТРОКИ «ПАМЯТЬ ОТСТАЛА» (карточка #664, слово владельца 2026-09-26 10:45 UTC, чат PROTO).

Что испытывается: общая функция .mezosync/scripts/phoenix_lag.py и hook-unread-digest.py,
который печатает её строку под сводкой непрочитанного при каждой реплике человека.

⚖️ Опаснее всего здесь два молчаливых исхода:
    · строка горит всегда (кричит про спящую роль) ⇒ её перестают читать;
    · строка молчит при сбое ⇒ «никто не отстал» неотличимо от «не посчитано».
Поэтому различающие случаи проверяют, ЧТО считается отставанием и что печатается при сбое.

Случаи:
  ① роль сохранилась после своей последней записки — строки нет          контроль
  ② работа 5 ч после сохранения state — роль, часы, число записок        РАЗЛИЧАЮЩИЙ
  ③ записка через секунды после сохранения — не отставание               РАЗЛИЧАЮЩИЙ
  ④ state старый, другой раздел свежий — отставание ЕСТЬ (мерим по state) РАЗЛИЧАЮЩИЙ
  ⑤ раздела state нет — мерим по самому свежему и говорим это            РАЗЛИЧАЮЩИЙ
  ⑥ закрытая роль в строку не попадает                                   РАЗЛИЧАЮЩИЙ
  ⑦ таблицы памяти нет — строка о сбое, а не молчание                     РАЗЛИЧАЮЩИЙ
  ⑧ hook на стенде: сводка, под ней строка «память отстала», код 0        РАЗЛИЧАЮЩИЙ
  ⑨ hook без модуля функции: сводка на месте, строка о сбое, код 0        РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: свои стенды во временном каталоге.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

sys.path.insert(0, str(mezo_target.scripts_root()))
import phoenix_lag as pl  # noqa: E402

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build(db, phoenix=True):
    """База стенда: лента, отметки прочитанного, реестр ролей и (по желанию) память."""
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT, "
                "timestamp TEXT, body_md TEXT, priority TEXT DEFAULT 'normal')")
    con.execute("CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER)")
    con.execute("CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT)")
    if phoenix:
        con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT, "
                    "confirmed_at TEXT, PRIMARY KEY (role, section))")
    con.commit()
    return con


def role(con, name, lifecycle="alive"):
    con.execute("INSERT INTO roles VALUES (?, ?)", (name, lifecycle))
    con.execute("INSERT INTO read_cursors VALUES (?, 0)", (name,))


def save(con, name, section, at):
    con.execute("INSERT OR REPLACE INTO phoenix VALUES (?, ?, 'тело', ?, ?)", (name, section, at, at))


def note(con, name, at):
    con.execute("INSERT INTO messages (writer_role, timestamp, body_md) VALUES (?, ?, 'тело')",
                (name, at))


def stand_db(tmp, name, phoenix=True):
    return build(str(tmp / f"{name}.db"), phoenix)


def hook_stand(tmp, with_module=True):
    """Контур на стенде: <c>/.mezosync/mezosync.db · <c>/.mezosync/scripts/phoenix_lag.py ·
    <c>/vnext-tools/hook-unread-digest.py — та же раскладка, что у живого контура."""
    c = tmp / "contour"
    (c / ".mezosync" / "scripts").mkdir(parents=True)
    (c / "vnext-tools").mkdir(parents=True)
    shutil.copy2(HERE / "hook-unread-digest.py", c / "vnext-tools" / "hook-unread-digest.py")
    if with_module:
        shutil.copy2(mezo_target.script("phoenix_lag.py"), c / ".mezosync" / "scripts" / "phoenix_lag.py")
    return c, build(str(c / ".mezosync" / "mezosync.db"))


def run_hook(c):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(c / "vnext-tools" / "hook-unread-digest.py")],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    return p.returncode, p.stdout


def main() -> int:
    ok = True
    tmp = Path(mezo_stand.new("bite-memory-lag-"))

    con = stand_db(tmp, "c1")
    role(con, "COORD")
    note(con, "COORD", "2026-09-26 09:00:00")
    save(con, "COORD", "state", "2026-09-26 10:00:00")
    r1 = pl.lag_line(con)
    ok &= case("① роль сохранилась после своей последней записки — строки нет (контроль)",
               r1 is None, f"строка: {r1!r}")

    con = stand_db(tmp, "c2")
    role(con, "COORD")
    save(con, "COORD", "state", "2026-09-26 10:00:00")
    note(con, "COORD", "2026-09-26 11:00:00")
    note(con, "COORD", "2026-09-26 15:00:00")
    r2 = pl.lag_line(con) or ""
    ok &= case("② работа 5 ч после сохранения state — роль, часы и число записок названы",
               "COORD 5 ч, записок после 2" in r2 and "💾" in r2,
               r2.splitlines()[0][-80:] if r2 else "строки нет", differ=True)

    con = stand_db(tmp, "c3")
    role(con, "ING")
    save(con, "ING", "state", "2026-09-20 10:00:00")
    note(con, "ING", "2026-09-20 10:00:10")
    r3 = pl.lag_line(con)
    ok &= case("③ записка через секунды после сохранения (давнего) — не отставание",
               r3 is None,
               "сохранение шестидневной давности само по себе не крик: роль с тех пор не работала",
               differ=True)

    con = stand_db(tmp, "c4")
    role(con, "TAXO")
    save(con, "TAXO", "state", "2026-09-26 10:00:00")
    save(con, "TAXO", "plan", "2026-09-26 18:00:00")
    note(con, "TAXO", "2026-09-26 16:00:00")
    r4 = pl.lag_line(con) or ""
    ok &= case("④ state старый, другой раздел свежий — отставание ЕСТЬ: мерим по state",
               "TAXO 6 ч" in r4,
               "запись мелкого раздела не глушит строку при устаревшем положении дел",
               differ=True)

    con = stand_db(tmp, "c5")
    role(con, "STUD")
    save(con, "STUD", "plan", "2026-09-26 10:00:00")
    note(con, "STUD", "2026-09-26 15:00:00")
    r5 = pl.lag_line(con) or ""
    ok &= case("⑤ раздела state нет — мерим по самому свежему и говорим это",
               "STUD 5 ч" in r5 and "раздела state нет — по plan" in r5,
               r5.splitlines()[0][-70:] if r5 else "строки нет", differ=True)

    con = stand_db(tmp, "c6")
    role(con, "EYE", "closed")
    role(con, "CORE")
    for who in ("EYE", "CORE"):
        save(con, who, "state", "2026-09-26 10:00:00")
        note(con, who, "2026-09-26 16:00:00")
    r6 = pl.lag_line(con) or ""
    ok &= case("⑥ закрытая роль в строку не попадает",
               "CORE 6 ч" in r6 and "EYE" not in r6,
               "закрытая роль не проснётся: крик о ней — шум для всех", differ=True)

    con = stand_db(tmp, "c7", phoenix=False)
    role(con, "RCC")
    r7 = pl.lag_line(con) or ""
    ok &= case("⑦ таблицы памяти нет — строка о сбое, а не молчание",
               "НЕ посчитано" in r7,
               r7.strip()[:90] if r7 else "молчание — прочлось бы как «все сохранены»", differ=True)

    c, con = hook_stand(tmp / "h8")
    role(con, "OPSSRE")
    save(con, "OPSSRE", "state", "2026-09-26 10:00:00")
    note(con, "OPSSRE", "2026-09-26 17:00:00")
    con.commit()
    con.close()
    rc8, out8 = run_hook(c)
    lines8 = out8.splitlines()
    pos = [i for i, x in enumerate(lines8) if "💾" in x]
    ok &= case("⑧ hook на стенде: сводка, под ней «память отстала», код 0",
               rc8 == 0 and lines8 and lines8[0].startswith("📬") and pos == [1]
               and "OPSSRE 7 ч" in lines8[1],
               f"код {rc8}; строк {len(lines8)}; " + (lines8[1][:90] if len(lines8) > 1 else "—"),
               differ=True)

    c, con = hook_stand(tmp / "h9", with_module=False)
    role(con, "OPSSRE")
    con.commit()
    con.close()
    rc9, out9 = run_hook(c)
    ok &= case("⑨ hook без модуля функции: сводка на месте, строка о сбое, код 0",
               rc9 == 0 and out9.startswith("📬 MEZO непрочитано") and "НЕ посчитано" in out9,
               f"код {rc9}; " + out9.replace("\n", " ⏎ ")[:140], differ=True)

    print()
    print(f"{'✅ ПАМЯТЬ ОТСТАЛА — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
