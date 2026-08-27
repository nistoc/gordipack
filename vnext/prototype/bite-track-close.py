# -*- coding: utf-8 -*-
r"""
bite-track-close.py — приёмка П③/П④ пула: track.py (вид · план · вердикты · закрытие ·
триаж). На КОПИИ живой базы (mezo_stand), суд по подсаженному пулу TRACK-ZZTC.

Случаи:
  ⓪ open: пул открыт, напечатан порядок пересоздания (П⑥)
  ① view: часть с role=SHARED → «⚠️ БЕЗ ХОЗЯИНА»
  ② ВСТРЕЧНЫЙ: всё роздано, но одна карточка blocked → «застрявшее» (розданность
     и движение — разные предикаты)
  ③ triage: сумма корзин = числу открытых вне пула (печатает ✅), код 0
  ④ close при участнике без вердикта → ОТКАЗ поимённо (роль + недостающий kind)
  ⑤ ВСТРЕЧНЫЙ: живая роль, НЕ участвовавшая, в отказе НЕ названа (шаг — не налог на всех)
  ⑥ verdict documentation «обновить …» → РОЖДЕНА карточка тем же ходом
  ⑦ после полного набора вердиктов close проходит; process-проблемы названы сырьём issues
  ⑧ --no-verdicts без причины → отказ; с причиной → закрыт + след в журнале действий
  ⑨ контроль: живая база прогоном не изменилась
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


def run(script, *args, db):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(script), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


stand = mezo_stand.new("track-close-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
try:
    con.execute("DELETE FROM leases")
except sqlite3.OperationalError:
    pass
con.commit()
con.close()

TR = SCRIPTS / "track.py"
BK = SCRIPTS / "backlog.py"

# ⓪ open
rc, out = run(TR, "open", "--id", "TRACK-ZZTC", "--title", "пул приёмки закрытия",
              "--actor", "PROTO", "--word", "проба 2026-08-27 22:00 UTC", db=db)
case("⓪ open: пул открыт и напечатан порядок пересоздания (П⑥)",
     rc == 0 and "порядок для участниц" in out and "сохранить память" in out)

# карточки: CORE (open), STUD (blocked), SHARED (без хозяина)
con = sqlite3.connect(str(db))
ids = {}
for role, title, st, reason in [
        ("CORE", "часть ядра", "open", None),
        ("STUD", "часть портала", "blocked", "жду ответа ядра"),
        ("SHARED", "ничья часть", "open", None)]:
    cur = con.execute(
        "INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
        "created_by, done_when, blocked_reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (role, title, "тело", st, "normal", "[]", "TRACK-ZZTC", "PROTO", "критерий", reason))
    ids[role] = cur.lastrowid
con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md) "
            "VALUES (?,?,?,?)", (ids["CORE"], "CORE", "comment", "работаю"))
con.commit()
con.close()

# ① ② view
rc, view = run(TR, "view", "--id", "TRACK-ZZTC", db=db)
case("① view: SHARED-часть помечена «БЕЗ ХОЗЯИНА»", rc == 0 and "БЕЗ ХОЗЯИНА" in view)
case("② view: заблокированная часть в «застрявшем» с причиной",
     "застряв" in view and "жду ответа ядра" in view)

# ③ triage: сумма корзин
rc, tri = run(TR, "triage", db=db)
case("③ triage: корзины сходятся с числом открытых вне пула (✅ напечатан)",
     rc == 0 and "сумма =" in tri and "✅" in tri)

# ④ close без вердиктов → отказ поимённо
rc, out4 = run(TR, "close", "--id", "TRACK-ZZTC", "--actor", "PROTO", db=db)
case("④ close при участниках без вердиктов → отказ ПОИМЁННО",
     rc == 1 and "CORE" in out4 and "documentation" in out4 and "process" in out4)
# ⑤ встречный: живая роль без участия не названа (ING не трогал пул)
case("⑤ роль, НЕ участвовавшая (ING), в обязанных НЕ названа", "ING" not in out4)

# ⑥ verdict «обновить …» рождает карточку
rc, out6 = run(TR, "verdict", "--id", "TRACK-ZZTC", "--role", "CORE",
               "--kind", "documentation", "--verdict", "обновить справку ядра о пулах", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
born = con.execute("SELECT id FROM backlog WHERE title LIKE 'обновить справку ядра%' "
                   "AND parent_track='TRACK-ZZTC'").fetchone()
con.close()
case("⑥ вердикт «обновить …» рождает карточку тем же ходом",
     rc == 0 and "рождена карточка" in out6 and born is not None)

# ⑦ полный набор → close проходит, process-проблемы названы
who_missing = []
for role in ("CORE", "STUD", "PROTO"):
    run(TR, "verdict", "--id", "TRACK-ZZTC", "--role", role,
        "--kind", "documentation", "--verdict", "чисто", db=db)
    v = "чисто" if role != "STUD" else "объявления гаснут раньше, чем роль успевает снять"
    run(TR, "verdict", "--id", "TRACK-ZZTC", "--role", role, "--kind", "process",
        "--verdict", v, db=db)
rc, out7 = run(TR, "close", "--id", "TRACK-ZZTC", "--actor", "PROTO", db=db)
case("⑦ полный набор вердиктов → закрыт; проблема процесса названа сырьём issues",
     rc == 0 and "закрыт" in out7 and "объявления гаснут" in out7 and "координатор" in out7)

# ⑧ --no-verdicts: без причины отказ, с причиной закрыт + журнал
con = sqlite3.connect(str(db))
con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
            "('TRACK-ZZTC2','второй пул приёмки','active')")
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
            "created_by, done_when) VALUES ('CORE','часть','тело','open','normal','[]',"
            "'TRACK-ZZTC2','PROTO','критерий')")
con.commit()
con.close()
rc_a, _ = run(TR, "close", "--id", "TRACK-ZZTC2", "--actor", "PROTO", "--no-verdicts", db=db)
rc_b, _ = run(TR, "close", "--id", "TRACK-ZZTC2", "--actor", "PROTO",
              "--no-verdicts", "--reason", "переходный пул, вердикты не собирались", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
trail = con.execute("SELECT 1 FROM audit_log WHERE action='close_track_no_verdicts' "
                    "AND target='TRACK-ZZTC2'").fetchone()
con.close()
case("⑧ лазейка: без причины отказ; с причиной закрыт и след в журнале действий",
     rc_a != 0 and rc_b == 0 and trail is not None)

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑨ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
