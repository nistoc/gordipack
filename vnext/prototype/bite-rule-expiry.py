# -*- coding: utf-8 -*-
# PLANTS: rules
r"""
bite-rule-expiry.py — приёмка захода 2.3: наступление сроков годности правил.
На КОПИИ живой базы (mezo_stand); суд по подсаженным правилам zzexp-*.

Случаи:
  ① until_event «карточка #N», карточка ЗАКРЫТА → 🔴 «событие наступило»
  ② ВСТРЕЧНЫЙ: карточка открыта → тихо
  ③ срок «до YYYY-MM-DD» прошёл → 🔴          ④ ВСТРЕЧНЫЙ: срок впереди → тихо
  ⑤ ГОЛАЯ дата-происхождение («На 2026-08-08 доля…») → НЕ красное: судим
     по происхождению, а не по виду (первый прогон дал 4 ложных из 4 на живом)
  ⑥ немашинное условие, правило не трогали дольше порога → 🟡 «перечитай рукой»
  ⑦ отозванное правило с наступившим условием → НЕ судится (история)
  ⑧ ОБРАТНЫЙ ХОД: ветка карточек отключена в копии → ① гаснет
  ⑨ контроль: живая база прогоном не изменилась
"""
import importlib.util
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402

LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

GUARD = HERE / "guard-rule-expiry.py"
OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = load(GUARD, "gre_live")
stand = mezo_stand.new("rule-expiry-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)

con = sqlite3.connect(str(db))
cur = con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
                  "created_by, done_when) VALUES ('ZZE','закрытая','т','done','normal','[]',"
                  "'PROTO','к')")
closed_id = cur.lastrowid
cur = con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
                  "created_by, done_when) VALUES ('ZZE','открытая','т','open','normal','[]',"
                  "'PROTO','к')")
open_id = cur.lastrowid


def add_rule(key, kind, cond, status="active", old=False):
    con.execute("INSERT INTO rules (rule_key, body, status, expiry_kind, expiry_cond"
                + (", revoked_at, revoked_by, revoked_reason" if status == "revoked" else "")
                + ") VALUES (?,?,?,?,?" + (",datetime('now'),'bite','проба'" if status == "revoked" else "") + ")",
                (key, "тело пробы", status, kind, cond))
    if old:
        con.execute("UPDATE rules SET updated_at=datetime('now','-45 days') WHERE rule_key=?",
                    (key,))


add_rule("zzexp-card-closed", "until_event", f"снимается, когда карточка #{closed_id} закрыта")
add_rule("zzexp-card-open", "until_event", f"снимается, когда карточка #{open_id} закрыта")
add_rule("zzexp-deadline-past", "until_event", "держится до 2026-01-01, дальше пересмотр")
add_rule("zzexp-deadline-future", "until_event", "держится до 2099-01-01, дальше пересмотр")
add_rule("zzexp-origin-date", "while_measured",
         "порог предложен PROTO; смягчается при доле 9 из 10 — вчерашний замер", old=False)
con.execute("UPDATE rules SET expiry_cond='доля объявленных дойдёт до 9 из 10; "
            "На 2026-06-01 объявляют три роли' WHERE rule_key='zzexp-origin-date'")
add_rule("zzexp-stale-hand", "while_measured", "пересмотр, если разгон станет дороже экономии",
         old=True)
add_rule("zzexp-revoked", "until_event", "снимается, когда карточка "
         f"#{closed_id} закрыта", status="revoked")
con.commit()
con.close()

conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
red, yellow, skipped, total = mod.judge(conn, 30)
conn.close()
rk = {k for k, _ in red}
yk = {k for k, _ in yellow}

case("① карточка условия закрыта → 🔴 «событие наступило»", "zzexp-card-closed" in rk,
     next((w for k, w in red if k == "zzexp-card-closed"), "—"))
case("② встречный: карточка открыта → тихо",
     "zzexp-card-open" not in rk and "zzexp-card-open" not in yk)
case("③ «до 2026-01-01» прошло → 🔴", "zzexp-deadline-past" in rk)
case("④ встречный: «до 2099-01-01» → тихо",
     "zzexp-deadline-future" not in rk and "zzexp-deadline-future" not in yk)
case("⑤ голая дата-происхождение («На 2026-06-01…») → НЕ красное, 🟡 по возрасту замера",
     "zzexp-origin-date" not in rk and "zzexp-origin-date" in yk,
     next((w for k, w in yellow if k == "zzexp-origin-date"), "—"))
case("⑥ немашинное условие + 45 дн без касания → 🟡 «перечитай рукой»",
     "zzexp-stale-hand" in yk)
case("⑦ отозванное с наступившим условием → не судится",
     "zzexp-revoked" not in rk and "zzexp-revoked" not in yk)

# ⑧ обратный ход
src = GUARD.read_text(encoding="utf-8")
ANCHOR = "m = CARD.search(cond)"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь ветки карточек не найден")
weak = stand / "weak-guard.py"
weak.write_text(src.replace(ANCHOR, "m = None"), encoding="utf-8")
wmod = load(weak, "gre_weak")
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
red2, _, _, _ = wmod.judge(conn, 30)
conn.close()
case("⑧ обратный ход: ветка карточек снята → ① гаснет",
     "zzexp-card-closed" not in {k for k, _ in red2})

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑨ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
