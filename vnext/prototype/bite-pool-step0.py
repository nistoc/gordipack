# -*- coding: utf-8 -*-
r"""
bite-pool-step0.py — приёмка шага 0 пула: «карточки пула первыми, статус тем же вызовом»
(карточка #348, пул TRACK-ROLES-REMEMBER, план snuggly-sniffing-planet.md).

ЧТО СУДИТСЯ (на КОПИИ живой базы, mezo_stand):
  ① карточка пула стоит ПЕРВОЙ в `backlog.py list`, хотя срочность у неё НИЖЕ соседней
  ② то же в обзоре пробуждения (backlog_view.reminder_lines)                РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ: у роли без карточек пула — СЛОВА «в пуле … твоих карточек нет»,
     а не пустая секция (класс «молчащий отказ читается как успех»)
  ④ ВСТРЕЧНЫЙ-2: активного пула НЕТ вовсе — строки про пул НЕТ (вечный заголовок слепит),
     порядок прежний: срочность, номер
  ⑤ закрытие карточки пула (done) пишет role_status ТЕМ ЖЕ вызовом            РАЗЛИЧАЮЩИЙ
  ⑥ ВСТРЕЧНЫЙ: закрытие карточки ВНЕ пула role_status НЕ трогает
  ⑦ ВСТРЕЧНЫЙ-2: ПРОМЕЖУТОЧНАЯ смена (in_progress) карточки пула статус НЕ трогает
  ⑧ карточки вне пула НЕ перепривязаны: parent_track всех посторонних карточек
     после всех прогонов побайтно тот же
  ⑨ ОБРАТНЫЙ ХОД: в копии backlog.py пул-ветка ключа сортировки ослаблена —
     случай ① обязан ПОКРАСНЕТЬ (карточка пула тонет)                        РАЗЛИЧАЮЩИЙ
  ⑩ контроль: живая база прогоном НЕ изменилась (размер+mtime)

СУД — ПО ПОДСАЖЕННОМУ КЛЮЧУ (роль ZZR, пул TRACK-ZZPROBE-POOL), не по общему исходу:
краснота от чужих карточек сюда не доедет (урок bite-launcher-forms 27.08).
Песочница НОРМАЛИЗУЕТСЯ: чужие пулы паузятся, аренды чистятся — приёмка меряет механизм,
а не текущее состояние контура. Живой инвариант «активный пул ровно один» этой приёмкой
НЕ судится: сегодня их два, и судьба TRACK-NEWUX — слово владельца; замер печатается
СПРАВКОЙ в конце, чтобы не красить механизм чужим решением.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(r"C:\guts\.atlas\.mezosync\scripts")
LIVE_DB = SCRIPTS.parent / "mezosync.db"
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


def first_card_line(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith("🎯#"):
            return s
    return ""


stand = mezo_stand.new("pool-step0-")
db = stand / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db)

con = sqlite3.connect(str(db))
# НОРМАЛИЗАЦИЯ ПЕСОЧНИЦЫ: чужие пулы в паузу, аренды прочь (в копии живёт и моя аренда
# на backlog.py — писать через неё пришлось бы чужим именем, а приёмка не роль).
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
            "('TRACK-ZZPROBE-POOL','подсаженный пул приёмки','active')")
try:
    con.execute("DELETE FROM leases")
except sqlite3.OperationalError:
    pass
# Подсадка: у ZZR карточка ПУЛА нарочно МЕНЕЕ срочная (normal) и МОЛОЖЕ (id больше),
# чем посторонняя critical, — старый порядок поставил бы её ВТОРОЙ.
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9001,'ZZR','посторонняя срочная','open','critical','есть',NULL)")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9002,'ZZR','карточка пула','open','normal','есть','TRACK-ZZPROBE-POOL')")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9003,'ZZEMPTY','вне пула','open','high','есть',NULL)")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9004,'ZZR','вторая карточка пула на закрытие','open','low','есть',"
            "'TRACK-ZZPROBE-POOL')")
outside_before = con.execute(
    "SELECT id, COALESCE(parent_track,'') FROM backlog "
    "WHERE id NOT IN (9001,9002,9003,9004) ORDER BY id").fetchall()
con.commit()
con.close()

# ① пул первым в list — вопреки срочности
_, out = run(SCRIPTS / "backlog.py", "list", "--role", "ZZR", db=db)
case("① карточка пула первой в list, хотя срочность ниже",
     "#9002" in first_card_line(out), f"первая строка: {first_card_line(out)[:80]}")

# ② то же в обзоре пробуждения
import importlib  # noqa: E402
sys.path.insert(0, str(SCRIPTS))
import backlog_view  # noqa: E402
importlib.reload(backlog_view)
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
lines = backlog_view.reminder_lines(conn, "ZZR")
card_lines = [l for l in lines if l.strip().startswith(("#", "🎯#"))]
case("② карточка пула первой в обзоре пробуждения",
     card_lines and "#9002" in card_lines[0], f"первая: {card_lines[0][:80] if card_lines else '—'}")
case("② шапка называет пул словами",
     any("пул" in l and "TRACK-ZZPROBE-POOL" in l for l in lines))

# ③ роль без карточек пула — слова, не пустая секция
lines3 = backlog_view.reminder_lines(conn, "ZZEMPTY")
case("③ без карточек пула — слова «твоих карточек нет»",
     any("в пуле" in l and "нет" in l for l in lines3),
     " / ".join(l.strip() for l in lines3[:2]))
conn.close()
_, out3 = run(SCRIPTS / "backlog.py", "list", "--role", "ZZEMPTY", db=db)
case("③ то же в list", "твоих карточек нет" in out3)

# ④ встречный-2: пула нет вовсе — строки про пул нет, порядок прежний
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE track_id='TRACK-ZZPROBE-POOL'")
con.commit()
con.close()
_, out4 = run(SCRIPTS / "backlog.py", "list", "--role", "ZZR", db=db)
case("④ пула нет — строки про пул НЕТ (вечный заголовок слепил бы)",
     "в пуле" not in out4 and "пул TRACK" not in out4)
case("④ и порядок прежний: срочность первой", "#9001" in first_card_line(out4),
     f"первая строка: {first_card_line(out4)[:80]}")
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='active' WHERE track_id='TRACK-ZZPROBE-POOL'")
con.commit()
con.close()

# ⑤ закрытие карточки пула пишет role_status тем же вызовом
rc, out5 = run(SCRIPTS / "backlog.py", "status", "9004", "done",
               "--actor", "ZZR", "--note", "проба закрытия", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
row = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()
case("⑤ done по карточке пула → role_status записан тем же вызовом",
     rc == 0 and row and "#9004" in row[0] and "TRACK-ZZPROBE-POOL" in row[0],
     (row[0][:100] if row else f"строки нет; rc={rc}"))
case("⑤ и вызов сам сказал об этом", "тем же вызовом" in out5.lower() or "ТЕМ ЖЕ" in out5)

# ⑥ встречный: закрытие карточки ВНЕ пула статус не трогает
rc6, _ = run(SCRIPTS / "backlog.py", "status", "9003", "done", "--actor", "ZZEMPTY", db=db)
row6 = con.execute("SELECT status FROM role_status WHERE role='ZZEMPTY'").fetchone()
case("⑥ done вне пула → role_status НЕ тронут", rc6 == 0 and row6 is None,
     f"rc={rc6}, запись: {'есть — ЛОЖНАЯ' if row6 else 'нет'}")

# ⑦ встречный-2: промежуточная смена карточки пула статус не трогает
before7 = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()[0]
con.close()
run(SCRIPTS / "backlog.py", "status", "9002", "in_progress", "--actor", "ZZR", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
after7 = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()[0]
case("⑦ in_progress по карточке пула → role_status НЕ переписан", before7 == after7)

# ⑧ посторонние карточки не перепривязаны
outside_after = con.execute(
    "SELECT id, COALESCE(parent_track,'') FROM backlog "
    "WHERE id NOT IN (9001,9002,9003,9004) ORDER BY id").fetchall()
case("⑧ parent_track посторонних карточек не тронут прогоном",
     outside_before == outside_after, f"карточек сверено: {len(outside_after)}")
con.close()

# ⑨ ОБРАТНЫЙ ХОД: ослабить пул-ветку ключа в КОПИИ backlog.py → ① краснеет
weak_dir = stand / "weak"
weak_dir.mkdir()
for name in ("backlog.py", "mezo_paths.py", "dryrun.py", "refs_check.py", "backlog_view.py"):
    shutil.copy(SCRIPTS / name, weak_dir / name)
src = (weak_dir / "backlog.py").read_text(encoding="utf-8")
ANCHOR = "return (0 if (pools and r[-1] in pools) else 1,"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь пул-ветки ключа не найден в backlog.py — "
                     "обратный ход ⑨ ослаблять нечего, случаи выше могли зеленеть не тем кодом")
(weak_dir / "backlog.py").write_text(src.replace(ANCHOR, "return (1,"), encoding="utf-8")
_, out9 = run(weak_dir / "backlog.py", "list", "--role", "ZZR", db=db)
case("⑨ обратный ход: ключ ослаблен → карточка пула БОЛЬШЕ НЕ первая (① краснеет)",
     "#9002" not in first_card_line(out9), f"первая строка: {first_card_line(out9)[:80]}")

# ⑩ живая база не изменилась
live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑩ живая база прогоном не тронута", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")

# СПРАВКА (не случай): живой инвариант «активный пул ровно один» — решение владельца
con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
живые = [r[0] for r in con.execute("SELECT track_id FROM tracks WHERE status='active'")]
con.close()
if len(живые) != 1:
    print(f"⏳ СПРАВКА: активных пулов в ЖИВОЙ базе {len(живые)} ({', '.join(живые)}) — "
          f"норма нового порядка: ОДИН; судьба лишнего — слово владельца, механизм это "
          f"печатает сам в каждом list")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
