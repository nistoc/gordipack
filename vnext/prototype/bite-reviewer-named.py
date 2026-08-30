# -*- coding: utf-8 -*-
r"""
bite-reviewer-named.py — приёмка карточки #482: КТО ПРИНИМАЕТ работу спрашивает ИНСТРУМЕНТ
в момент сдачи, а не норма в чужой памяти.

ПОВОД. Правило требует чужую руку для приёмки, но кто именно — не назначает никто. Замер
@COORD (записка #4436): своя заявка ждёт втрое дольше по медиане (2.1 ч против 0.6 ч),
худший случай 264 ч против 107 ч, и таких в очереди две трети.

⚖️ ЧТО ЭТА ПРИЁМКА СУДИТ ОСОБЕННО: что подсказка НЕ СТАЛА ВОРОТАМИ. Инструмент, не давший
роли сдать работу, толкает её сдавать мимо механизма — это хуже молчания, ради которого
всё затевалось. Случай ④ проверяет именно это и обязан оставаться зелёным.

Всё на КОПИИ базы (mezo_stand); живая база только читается.

Случаи:
  ① сдача БЕЗ приёмщика: сказано ВСЛУХ, что рук не назначено
  ② ВСТРЕЧНЫЙ: сдача С приёмщиком — подсказки НЕТ (признак, горящий всегда, не значит ничего)
  ③ приёмщик записан ПОЛЕМ и читается обратно
  ④ ВСТРЕЧНЫЙ (главный): сдача без приёмщика ПРОХОДИТ — статус сменился, код успешный
  ⑤ приёмщиком законно ПРАВИЛО СЛОВАМИ, а не только имя роли
  ⑥ подсказка называет ЗАВЕДШУЮ роль, когда карточку завёл кто-то другой
  ⑦ поле видно в стартовой сводке роли; «не назначен» сказано СЛОВОМ
  ⑧ ТРЕТИЙ ИСХОД: базы без столбца сводка читает и НЕ падает (старые копии живут)
  ⑨ контроль: своих следов в ЖИВОЙ базе нет
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

ИСПЫТУЕМЫЙ = mezo_target.script("backlog.py")
СВОДКА = mezo_target.script("role-brief.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0
РОЛЬ = "ZZR"
ЧУЖАЯ = "ZZS"


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
                MEZO_CONTAINER=str(mezo_paths.container_root()))


def сдать(db, cid, actor, reviewer=None):
    cmd = [sys.executable, str(ИСПЫТУЕМЫЙ), "--db", str(db), "status", str(cid),
           "in_review", "--actor", actor]
    if reviewer:
        cmd += ["--reviewer", reviewer]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def сводка(db, role):
    p = subprocess.run([sys.executable, str(СВОДКА), "--role", role, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def поле(db, cid):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    r = con.execute("SELECT status, COALESCE(reviewer,'') FROM backlog WHERE id=?",
                    (cid,)).fetchone()
    con.close()
    return r


stand = mezo_stand.new("reviewer-named-")
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
for r in (РОЛЬ, ЧУЖАЯ):
    con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба приёмщика')", (r,))
ids = {}
for имя, завёл in (("своя-без-приёмщика", РОЛЬ), ("своя-с-приёмщиком", РОЛЬ),
                   ("своя-с-правилом", РОЛЬ), ("заведена-чужой", ЧУЖАЯ)):
    cur = con.execute(
        "INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, "
        "done_when) VALUES (?,?,'тело','in_progress','normal','[]',?,'критерий')",
        (РОЛЬ, имя, завёл))
    ids[имя] = cur.lastrowid
con.commit()
con.close()

# ═══ ① сдача БЕЗ приёмщика — сказано вслух
rc1, out1 = сдать(db, ids["своя-без-приёмщика"], РОЛЬ)
case("① сдача БЕЗ приёмщика: сказано ВСЛУХ, что рук не назначено",
     "ПРИЁМЩИК НЕ НАЗНАЧЕН" in out1)

# ═══ ④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: перевод всё равно прошёл
st1 = поле(db, ids["своя-без-приёмщика"])
case("④ ВСТРЕЧНЫЙ (главный): сдача без приёмщика ПРОШЛА — подсказка не стала воротами",
     rc1 == 0 and st1[0] == "in_review",
     f"код {rc1} · статус {st1[0]}")

# ═══ ② ВСТРЕЧНЫЙ: с приёмщиком подсказки НЕТ
rc2, out2 = сдать(db, ids["своя-с-приёмщиком"], РОЛЬ, reviewer="TAXO")
case("② ВСТРЕЧНЫЙ: сдача С приёмщиком — подсказки НЕТ (признак не горит всегда)",
     rc2 == 0 and "ПРИЁМЩИК НЕ НАЗНАЧЕН" not in out2 and "приёмщик: TAXO" in out2)

# ═══ ③ поле записано и читается обратно
st2 = поле(db, ids["своя-с-приёмщиком"])
case("③ приёмщик записан ПОЛЕМ и читается обратно", st2[1] == "TAXO",
     f"в базе: {st2[1]!r}")

# ═══ ⑤ приёмщиком законно ПРАВИЛО СЛОВАМИ
правило = "любая, не писавшая правку"
rc3, out3 = сдать(db, ids["своя-с-правилом"], РОЛЬ, reviewer=правило)
st3 = поле(db, ids["своя-с-правилом"])
case("⑤ приёмщиком законно ПРАВИЛО СЛОВАМИ, не только имя роли",
     rc3 == 0 and st3[1] == правило, f"в базе: {st3[1]!r}")

# ═══ ⑥ подсказка называет ЗАВЕДШУЮ роль
rc4, out4 = сдать(db, ids["заведена-чужой"], РОЛЬ)
case("⑥ подсказка называет ЗАВЕДШУЮ роль, когда карточку завёл другой",
     f"карточку завела роль {ЧУЖАЯ}" in out4 and f"--reviewer {ЧУЖАЯ}" in out4)

# ═══ ⑦ поле видно в сводке; «не назначен» сказано словом
rc5, out5 = сводка(db, РОЛЬ)
case("⑦ поле видно в стартовой сводке: и назначенный, и «НЕ НАЗНАЧЕН» словом",
     rc5 == 0 and "приёмщик: TAXO" in out5 and "приёмщик НЕ НАЗНАЧЕН" in out5
     and "БЕЗ НАЗНАЧЕННОГО ПРИЁМЩИКА" in out5)

# ═══ ⑧ ТРЕТИЙ ИСХОД: база без столбца — сводка живёт
db_old = stand / "old.db"
shutil.copy(db, db_old)
con = sqlite3.connect(str(db_old))
# ⚖️ Представления, опирающиеся на таблицу, снимаются и ВОЗВРАЩАЮТСЯ: иначе «база без
# столбца» отличалась бы от настоящей старой копии ещё и отсутствием представлений,
# и случай судил бы не то, что назван. Поймано падением при первом прогоне.
виды = [(r[0], r[1]) for r in con.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='view' AND sql LIKE '%backlog%'")]
for имя, _ in виды:
    con.execute(f"DROP VIEW {имя}")
cols = [r[1] for r in con.execute("PRAGMA table_info(backlog)") if r[1] != "reviewer"]
con.execute(f"CREATE TABLE backlog_old AS SELECT {','.join(cols)} FROM backlog")
con.execute("DROP TABLE backlog")
con.execute("ALTER TABLE backlog_old RENAME TO backlog")
for _, sql in виды:
    con.execute(sql)
con.commit()
проверка = [r[1] for r in con.execute("PRAGMA table_info(backlog)")]
assert "reviewer" not in проверка, "случай ⑧ ничего не различает: столбец остался"
con.close()
rc6, out6 = сводка(db_old, РОЛЬ)
case("⑧ ТРЕТИЙ ИСХОД: база БЕЗ столбца — сводка читается и не падает",
     rc6 == 0 and "ИСТОЧНИК НЕ ПРОЧИТАН" not in out6 and "📤 ТЫ СДАЛ" in out6)

# ═══ ⑨ контроль
живой = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы = живой.execute("SELECT COUNT(*) FROM roles WHERE role IN (?,?)",
                      (РОЛЬ, ЧУЖАЯ)).fetchone()[0]
следы += живой.execute("SELECT COUNT(*) FROM backlog WHERE role=?", (РОЛЬ,)).fetchone()[0]
живой.close()
case("⑨ контроль: своих следов в живой базе нет", следы == 0, f"следов: {следы}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
