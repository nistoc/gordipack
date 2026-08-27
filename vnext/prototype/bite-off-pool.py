# -*- coding: utf-8 -*-
r"""
bite-off-pool.py — приёмка П① пула (план «Роли не забывают»): ворота «новое — в пул»
и статус «заморожена» с обязательным условием разморозки.

Случаи (на КОПИИ живой базы, mezo_stand; суд по подсаженным карточкам, живая база
только читается):
  ① активный пул есть, карточка заводится БЕЗ --track → ПРЕДУПРЕЖДЕНИЕ (не отказ)
  ② с --track → предупреждения НЕТ (тихо)
  ③ ВСТРЕЧНЫЙ: активного пула НЕТ вовсе → предупреждения НЕТ (вечно горящее слепит)
  ④ frozen БЕЗ условия разморозки → ОТКАЗ (код 1, слова про условие)
  ⑤ frozen С условием → принят; в list --status frozen виден 🧊 и само условие
  ⑥ frozen НЕ в открытых: обычный list его не несёт
  ⑦ ОБРАТНЫЙ ХОД: ворота frozen сняты в копии инструмента → ④ проходит молча (краснеет)
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


def run(script, *args, db):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(script), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


stand = mezo_stand.new("off-pool-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
            "('TRACK-ZZOFF','пул приёмки','active')")
try:
    con.execute("DELETE FROM leases")
except sqlite3.OperationalError:
    pass
con.commit()
con.close()

BK = SCRIPTS / "backlog.py"

# ① без --track при активном пуле → предупреждение
rc, out = run(BK, "add", "--role", "ZZR", "--actor", "ZZR",
              "--title", "проба вне пула", "--body", "тело",
              "--done-when", "критерий", db=db)
case("① без --track при активном пуле → предупреждение «новое — только в пул»",
     rc == 0 and "новое — только в пул" in out)

# ② с --track → тихо
rc, out2 = run(BK, "add", "--role", "ZZR", "--actor", "ZZR",
               "--title", "проба в пуле", "--body", "тело",
               "--done-when", "критерий", "--track", "TRACK-ZZOFF", db=db)
case("② с --track → предупреждения нет", rc == 0 and "новое — только в пул" not in out2)

# ③ встречный: активного пула нет
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE track_id='TRACK-ZZOFF'")
con.commit()
con.close()
rc, out3 = run(BK, "add", "--role", "ZZR", "--actor", "ZZR",
               "--title", "проба без пула вовсе", "--body", "тело",
               "--done-when", "критерий", db=db)
case("③ активного пула нет → предупреждения нет (вечно горящее слепит)",
     rc == 0 and "новое — только в пул" not in out3)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='active' WHERE track_id='TRACK-ZZOFF'")
zzid = con.execute("SELECT id FROM backlog WHERE title='проба вне пула'").fetchone()[0]
con.commit()
con.close()

# ④ frozen без условия → отказ
rc, out4 = run(BK, "status", str(zzid), "frozen", "--actor", "ZZR", db=db)
case("④ frozen БЕЗ условия разморозки → отказ", rc == 1 and "УСЛОВИЯ РАЗМОРОЗКИ" in out4)

# ⑤ frozen с условием → принят, условие на витрине
rc, _ = run(BK, "status", str(zzid), "frozen", "--actor", "ZZR",
            "--note", "условие разморозки: пул закрыт", db=db)
rc5, out5 = run(BK, "list", "--role", "ZZR", "--status", "frozen", db=db)
case("⑤ frozen с условием → принят; 🧊 и условие видны в list --status frozen",
     rc == 0 and rc5 == 0 and "🧊" in out5 and "условие разморозки: пул закрыт" in out5)

# ⑥ frozen не в открытых
_, out6 = run(BK, "list", "--role", "ZZR", db=db)
case("⑥ открытый list замороженную НЕ несёт", f"#{zzid} " not in out6)

# ⑦ обратный ход: ворота сняты в копии
weak = stand / "weak"
weak.mkdir()
for name in ("backlog.py", "mezo_paths.py", "dryrun.py", "refs_check.py", "backlog_view.py"):
    shutil.copy(SCRIPTS / name, weak / name)
src = (weak / "backlog.py").read_text(encoding="utf-8")
ANCHOR = 'if a.new_status == "frozen" and not note.strip():'
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь ворот frozen не найден — "
                     "случай ④ мог зеленеть не тем кодом")
(weak / "backlog.py").write_text(src.replace(ANCHOR, "if False:"), encoding="utf-8")
con = sqlite3.connect(str(db))
zzid2 = con.execute("SELECT id FROM backlog WHERE title='проба в пуле'").fetchone()[0]
con.close()
rc7, out7 = run(weak / "backlog.py", "status", str(zzid2), "frozen", "--actor", "ZZR", db=db)
case("⑦ обратный ход: ворота сняты → заморозка без условия ПРОХОДИТ (④ краснеет)",
     rc7 == 0 and "УСЛОВИЯ РАЗМОРОЗКИ" not in out7)

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑧ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
