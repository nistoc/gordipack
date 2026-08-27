# -*- coding: utf-8 -*-
r"""
bite-overdue-claim.py — приёмка П② пула: ворота итераций и предикат просроченного
объявления. На КОПИИ живой базы (mezo_stand), суд по подсаженным карточкам ZZ-ролей.

Случаи:
  ① просроченное объявление + молчание роли → строка «молчит над» в list ЛЮБОЙ роли,
     в обзоре пробуждения и на витрине пула (П②: предикат при каждом чтении, демона нет)
  ② после снятия объявления (release) → строки НЕТ
  ③ ВСТРЕЧНЫЙ: карточка пула БЕЗ объявления → просрочки нет (молчание без объявления
     законно)
  ④ claim карточки ПУЛА: срок по умолчанию 60 мин; >90 → «шаг длинный — раздели»
  ⑤ ВСТРЕЧНЫЙ: карточка ВНЕ пула — прежние 120 мин, предупреждения о длине нет
  ⑥ release без итога → предупреждение; с итогом → нет
  ⑦ in_progress карточки пула БЕЗ живого объявления → предупреждение «возьми
     объявлением»; ВСТРЕЧНЫЙ: вне пула → предупреждения нет
  ⑧ сон: живое объявление в пуле → потолок УЧАСТНИЦЫ прижат к 15 мин; ВСТРЕЧНЫЕ:
     без живых объявлений → прежний потолок; НЕ участница → прежний потолок
  ⑨ ОБРАТНЫЙ ХОД: предикат отключён в копии → ① гаснет (строки нет)
  ⑩ контроль: живая база прогоном не изменилась
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


stand = mezo_stand.new("overdue-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
            "('TRACK-ZZOD','пул приёмки просрочки','active')")
try:
    con.execute("DELETE FROM leases")
except sqlite3.OperationalError:
    pass
ids = {}
for key, role, track in [("late", "ZZW", "TRACK-ZZOD"), ("silent", "ZZW", "TRACK-ZZOD"),
                         ("free", "ZZV", None), ("pool2", "ZZV", "TRACK-ZZOD")]:
    cur = con.execute(
        "INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
        "created_by, done_when) VALUES (?,?,?,?,?,?,?,?,?)",
        (role, f"карточка-{key}", "тело", "open", "normal", "[]", track, "PROTO", "критерий"))
    ids[key] = cur.lastrowid
# ① подсадка: объявление, истёкшее 3 часа назад, событий роли после срока нет
con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md, at) "
            "SELECT ?, 'ZZW', 'claim', 'до ' || datetime('now', '-3 hours') || ' UTC · чиню предикат', "
            "datetime('now', '-4 hours')", (ids["late"],))
con.commit()
con.close()

BK = SCRIPTS / "backlog.py"

# ① строка в list любой роли + в обзоре пробуждения + на витрине пула
_, out = run(BK, "list", "--role", "ZZV", db=db)
case("① просрочка видна в list ЧУЖОЙ роли («молчит над»)",
     "молчит над" in out and f"#{ids['late']}" in out)
sys.path.insert(0, str(SCRIPTS))
import importlib  # noqa: E402
import backlog_view  # noqa: E402
importlib.reload(backlog_view)
lines = backlog_view.reminder_block(str(db), "ZZV")
case("① просрочка видна в обзоре пробуждения любой роли",
     any("молчит над" in l for l in lines))
_, tv = run(SCRIPTS / "track.py", "view", "--id", "TRACK-ZZOD", db=db)
case("① просрочка видна в просмотре пула", "молчит над" in tv or "истёк" in tv)

# ② после release строки нет
run(BK, "claim", str(ids["late"]), "--actor", "ZZW", "--release",
    "--note", "итог: предикат починен", db=db)
_, out2 = run(BK, "list", "--role", "ZZV", db=db)
case("② после снятия объявления строки нет", "молчит над" not in out2)

# ③ встречный: карточка пула без объявления — просрочки нет
_, out3 = run(BK, "list", "--role", "ZZW", db=db)
case("③ карточка пула БЕЗ объявления просрочки не даёт",
     f"молчит над карточкой #{ids['silent']}" not in out3)

# ④ claim пула: 60 мин по умолчанию; >90 → «раздели»
rc, out4 = run(BK, "claim", str(ids["silent"]), "--actor", "ZZW",
               "--note", "пробую шаг", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
body = con.execute("SELECT body_md FROM backlog_events WHERE backlog_id=? AND "
                   "event_type='claim' ORDER BY id DESC LIMIT 1", (ids["silent"],)).fetchone()[0]
mins = con.execute("SELECT CAST(ROUND((julianday(?)-julianday('now'))*1440) AS INTEGER)",
                   (body.split(" UTC")[0][3:],)).fetchone()[0]
con.close()
case("④ карточка пула: срок по умолчанию 60 мин", rc == 0 and 58 <= mins <= 60,
     f"вышло {mins} мин")
_, out4b = run(BK, "claim", str(ids["pool2"]), "--actor", "ZZV",
               "--minutes", "120", "--note", "длинный шаг", db=db)
case("④ >90 мин на карточке пула → «шаг длинный — раздели»", "раздели" in out4b)

# ⑤ встречный: вне пула — 120 мин и без «раздели»
_, out5 = run(BK, "claim", str(ids["free"]), "--actor", "ZZV", "--note", "вне пула", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
body = con.execute("SELECT body_md FROM backlog_events WHERE backlog_id=? AND "
                   "event_type='claim' ORDER BY id DESC LIMIT 1", (ids["free"],)).fetchone()[0]
mins5 = con.execute("SELECT CAST(ROUND((julianday(?)-julianday('now'))*1440) AS INTEGER)",
                    (body.split(" UTC")[0][3:],)).fetchone()[0]
con.close()
case("⑤ вне пула: прежние 120 мин, «раздели» нет",
     118 <= mins5 <= 120 and "раздели" not in out5, f"вышло {mins5} мин")

# ⑥ release без итога → предупреждение; с итогом — нет
_, out6a = run(BK, "claim", str(ids["free"]), "--actor", "ZZV", "--release", db=db)
_, out6b = run(BK, "claim", str(ids["pool2"]), "--actor", "ZZV", "--release",
               "--note", "итог: раздёлен на два", db=db)
case("⑥ снятие без итога → предупреждение; с итогом → нет",
     "БЕЗ итога" in out6a and "БЕЗ итога" not in out6b)

# ⑦ in_progress пула без объявления → предупреждение; вне пула — нет
con = sqlite3.connect(str(db))
cur = con.execute(
    "INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
    "created_by, done_when) VALUES ('ZZW','карточка-quiet','тело','open','normal','[]',"
    "'TRACK-ZZOD','PROTO','критерий')")
quiet = cur.lastrowid
cur = con.execute(
    "INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
    "created_by, done_when) VALUES ('ZZW','карточка-quiet-free','тело','open','normal','[]',"
    "NULL,'PROTO','критерий')")
quiet_free = cur.lastrowid
con.commit()
con.close()
_, out7a = run(BK, "status", str(quiet), "in_progress", "--actor", "ZZW", db=db)
_, out7b = run(BK, "status", str(quiet_free), "in_progress", "--actor", "ZZW", db=db)
case("⑦ in_progress пула без объявления → «возьми объявлением»; вне пула → тихо",
     "БЕЗ живого объявления" in out7a and "БЕЗ живого объявления" not in out7b)

# ⑧ сон: потолок участницы прижат при живом объявлении
import sync_backoff  # noqa: E402
importlib.reload(sync_backoff)
run(BK, "claim", str(ids["silent"]), "--actor", "ZZW", "--note", "живой шаг", db=db)
# ХОЛОСТОЙ вызов сна: копия базы видит «новый файл в мосте соседей» и честно сбрасывает
# сон к 5 мин — тогда потолок мерить нечем. Первый вызов проглатывает новизну моста
# (двигает отметку), замер идёт вторым. Первый прогон приёмки упал ровно на этом.
sync_backoff.next_sleep(db, "ZZW")
sync_backoff.next_sleep(db, "ZZOUT")
con = sqlite3.connect(str(db))
con.execute("INSERT INTO sync_backoff (role, sleep_sec, quiet_streak, last_seen_id) "
            "SELECT 'ZZW', 3000, 9, COALESCE(MAX(id),0) FROM messages WHERE true "
            "ON CONFLICT(role) DO UPDATE SET sleep_sec=3000, quiet_streak=9, "
            "last_seen_id=excluded.last_seen_id")
con.execute("INSERT INTO sync_backoff (role, sleep_sec, quiet_streak, last_seen_id) "
            "SELECT 'ZZOUT', 3000, 9, COALESCE(MAX(id),0) FROM messages WHERE true "
            "ON CONFLICT(role) DO UPDATE SET sleep_sec=3000, quiet_streak=9, "
            "last_seen_id=excluded.last_seen_id")
con.commit()
con.close()
r_in = sync_backoff.next_sleep(db, "ZZW")
r_out = sync_backoff.next_sleep(db, "ZZOUT")
case("⑧ участница живого пула: сон прижат к 15 мин и причина названа",
     r_in["minutes"] <= 15 and "ПУЛ ЖИВ" in r_in["reason"],
     f"{r_in['minutes']} мин · {r_in['reason'][:90]}")
case("⑧ НЕ участница: потолок прежний", r_out["minutes"] > 15,
     f"{r_out['minutes']} мин")
run(BK, "claim", str(ids["silent"]), "--actor", "ZZW", "--release",
    "--note", "итог: снял для встречного", db=db)
con = sqlite3.connect(str(db))
con.execute("UPDATE sync_backoff SET sleep_sec=3000, quiet_streak=9 WHERE role='ZZW'")
con.commit()
con.close()
r_dead = sync_backoff.next_sleep(db, "ZZW")
case("⑧ живых объявлений нет → потолок прежний (встречный)",
     r_dead["minutes"] > 15, f"{r_dead['minutes']} мин")

# ⑨ обратный ход: предикат отключён → ① гаснет
weak = stand / "weak"
weak.mkdir()
for name in ("backlog.py", "mezo_paths.py", "dryrun.py", "refs_check.py", "backlog_view.py"):
    shutil.copy(SCRIPTS / name, weak / name)
src = (weak / "backlog.py").read_text(encoding="utf-8")
ANCHOR = "_, overdue = live_and_overdue(conn, pool_open_ids(conn, pools))"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь предиката просрочки не найден — "
                     "случай ① мог зеленеть не тем кодом")
(weak / "backlog.py").write_text(src.replace(ANCHOR, "overdue = []"), encoding="utf-8")
con = sqlite3.connect(str(db))
# Подсадка — от роли ZZX БЕЗ событий после срока: у ZZW на этой карточке уже есть
# release ПОСЛЕ срока, и предикат ПРАВ, что молчания нет (первый прогон поймал это).
con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md, at) "
            "SELECT ?, 'ZZX', 'claim', 'до ' || datetime('now', '-3 hours') || ' UTC · снова тяну', "
            "datetime('now', '-4 hours')", (ids["late"],))
con.commit()
con.close()
_, chk = run(BK, "list", "--role", "ZZV", db=db)
if "молчит над" not in chk:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: подсадка ⑨ не воспроизвела просрочку живым кодом")
_, out9 = run(weak / "backlog.py", "list", "--role", "ZZV", db=db)
case("⑨ обратный ход: предикат отключён → строка гаснет (① краснеет)",
     "молчит над" not in out9)

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑩ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
