# -*- coding: utf-8 -*-
r"""
bite-pool-brief.py — приёмка захода 2.1 + П⑥: собираемый наказ (role-brief.py) и паёк
пула. На КОПИИ живой базы (mezo_stand); живая база только читается.

Случаи:
  ① целые источники → наказ несёт зону, права, формы, свод — БЕЗ предупреждений
  ② участница активного пула → паёк несёт ВСЕ ТРИ блока: наказ + выжимка пула
     (карточки) + скиллы (пула и роли)
  ③ ВСТРЕЧНЫЙ: роль вне пула → блока пула нет, «твоих карточек нет» СЛОВАМИ
  ④ пустое поле скиллов пула → «НЕ НАЗВАНЫ» словами, не молчание
  ⑤ умение с expired_at в паёк НЕ попадает; живое — попадает; скрытое посчитано вслух
  ⑥ ИСТОЧНИКИ ЛОМАЮТСЯ ПОРОЗНЬ (DROP TABLE) → наказ НАЗЫВАЕТ, чего не хватает,
     и НЕ молчит; остальные секции живут (по одному прогону на источник)
  ⑦ базы нет вовсе → отказ «НЕ СОБРАН», не пустой наказ
  ⑧ контроль: живая база прогоном не изменилась
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def brief(db, role):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "role-brief.py"),
                        "--role", role, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


stand = mezo_stand.new("pool-brief-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status, skills) VALUES "
            "('TRACK-ZZBR','пул пайка','active','скилл-до-задачи: чинить предикаты')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZB','alive','проба пайка')")
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
            "created_by, done_when) VALUES ('ZZB','часть пайка','тело','open','normal','[]',"
            "'TRACK-ZZBR','PROTO','критерий')")
con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, written_by) "
            "VALUES ('ZZB','живое умение пробы','записка-проба','2026-08-27 10:00','ZZB')")
con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, written_by, "
            "expired_at, expired_why) VALUES ('ZZB','протухшее умение пробы','записка-проба',"
            "'2026-08-01 10:00','ZZB','2026-08-27 09:00','условие наступило пробой')")
con.commit()
con.close()

# ①② участница пула
rc, out = brief(db, "ZZB")
case("① целые источники → зона+права+формы+свод, без «НЕ ПРОЧИТАН»",
     rc == 0 and "проба пайка" in out and "ФОРМЫ ВЫЗОВА" in out and "СВОД" in out
     and "НЕ ПРОЧИТАН" not in out)
case("② паёк участницы: пул + карточки + скиллы пула",
     "TRACK-ZZBR" in out and "часть пайка" in out and "скилл-до-задачи" in out)

# ③ роль вне пула
rc3, out3 = brief(db, "CHROME")
case("③ вне пула → «твоих карточек нет» словами, блока пула нет",
     rc3 == 0 and "твоих карточек нет" in out3 and "TRACK-ZZBR:" not in out3)

# ④ пустое поле скиллов пула
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET skills=NULL WHERE track_id='TRACK-ZZBR'")
con.commit()
con.close()
_, out4 = brief(db, "ZZB")
case("④ скиллы пула не названы → СЛОВАМИ", "НЕ НАЗВАНЫ" in out4)

# ⑤ протухшее умение скрыто и посчитано
_, out5 = brief(db, "ZZB")
case("⑤ протухшее умение НЕ в пайке, живое — в пайке, скрытое посчитано",
     "живое умение пробы" in out5 and "протухшее умение пробы" not in out5
     and "протухших скрыто 1" in out5)

# ⑥ источники ломаются порознь — наказ называет
for tbl, метка in [("role_rights", "права"), ("role_skill", "умения"),
                   ("tracks", "пул"), ("rules", "свод")]:
    db6 = stand / f"broke-{tbl}.db"
    shutil.copy(db, db6)
    con = sqlite3.connect(str(db6))
    con.execute(f"DROP TABLE {tbl}")
    con.commit()
    con.close()
    rc6, out6 = brief(db6, "ZZB")
    others = ("ФОРМЫ ВЫЗОВА" in out6)
    case(f"⑥ сломан источник «{метка}» ({tbl}) → назван «НЕ ПРОЧИТАН», остальное живёт",
         "НЕ ПРОЧИТАН" in out6 and others,
         [l for l in out6.splitlines() if "НЕ ПРОЧИТАН" in l][:1])

# ⑦ базы нет
rc7, out7 = brief(stand / "нет-такой.db", "ZZB")
case("⑦ базы нет → «НАКАЗ НЕ СОБРАН», не пустой наказ", rc7 != 0 and "НЕ СОБРАН" in out7)

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑧ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
