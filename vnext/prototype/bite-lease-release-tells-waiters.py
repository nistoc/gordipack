# -*- coding: utf-8 -*-
r"""bite-lease-release-tells-waiters.py — приёмка карточки #488: СНЯТИЕ объявления о правке
доходит до тех, кто его ждёт.

ПОВОД. Взятие инструмента расходится само — кто упёрся, тот увидел. Снятие не расходится
никак: механизм не знает, что кто-то ждёт. Замер 30.08 11:36 UTC: объявлений 127, снято
раньше объявленного срока 126 (99%), медиана зазора 36.7 мин, сумма «числится занятым,
а свободен» 83.5 часа.

🔴 ЧТО ДЕЛАЕТ ЭТУ ПРИЁМКУ НУЖНОЙ, А НЕ ФОРМАЛЬНОЙ. Лечение СЛОВАМИ уже применялось:
после замера @OPSSRE 29.08 в текст отказа вписана строка «срок — верхняя граница,
не жди срока, спроси состояние». 30.08 её прочли @STUD (11:10) и @CHROME (11:23) —
и оба написали в ленте, что дождутся срока 12:36, хотя объявление сняли в 11:28:56.
⇒ приёмка судит не наличие слов, а то, что роль НЕ ДЕЛАЕТ НИЧЕГО ЛИШНЕГО.

⚖️ ГЛАВНЫЙ ВСТРЕЧНЫЙ — случай ⑧: снятие объявления при живых ждущих ПРОХОДИТ.
Инструмент, не давший роли снять СВОЁ объявление, хуже молчания.

Всё на КОПИИ базы (mezo_stand); живая база только читается.

Случаи:
  ① отказ пишущему САМ записывает ожидание
  ② ВСТРЕЧНЫЙ: читающему отказа нет ⇒ ожидание НЕ записывается
  ③ имя роли берётся из --actor, когда MEZO_ROLE не задан
  ④ имя роли берётся из MEZO_ROLE, когда он задан
  ⑤ безымянный вызов записывается БЕЗ имени и считается отдельно
  ⑥ снятие называет ждущих поимённо, с часом отказа
  ⑦ ВСТРЕЧНЫЙ: снятие БЕЗ ждущих не печатает пустого раздела
  ⑧ ВСТРЕЧНЫЙ (главный): снятие при ждущих ПРОХОДИТ — код 0, объявление снято
  ⑨ повторный отказ той же роли не плодит строк: час ПЕРВОГО отказа сохраняется
  ⑩ ждущий видит освободившееся в СВОЕЙ стартовой сводке
  ⑪ ТРЕТИЙ ИСХОД: база без таблицы — снятие и сводка живут, а не падают
  ⑫ контроль: своих следов в ЖИВОЙ базе нет
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

АРЕНДА = mezo_target.script("lease.py")
КАРТОЧКИ = mezo_target.script("backlog.py")
СВОДКА = mezo_target.script("role-brief.py")
ЛЕНТА = mezo_target.script("read-messages.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0
ЖДУЩАЯ = "ZZW"          # упирается в чужое объявление
ДРУГАЯ = "ZZX"          # упирается вторая, чтобы список был не из одного
ХОЗЯИН = "ZZY"          # держит объявление


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def env(role=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8",
             MEZO_LEASE_TEST="1",                 # объявления действуют и на копии
             MEZO_CONTAINER=str(mezo_paths.container_root()))
    e.pop("MEZO_ROLE", None)
    if role:
        e["MEZO_ROLE"] = role
    return e


def run(cmd, role=None):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env(role))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def взять(db, role, tools, minutes=60):
    rc, out = run([sys.executable, str(АРЕНДА), "--db", str(db), "take", "--role", role,
                   "--tools", tools, "--reason", "проба приёмки карточки #488",
                   "--minutes", str(minutes)])
    номер = None
    for сл in out.split():
        if сл.startswith("#") and сл[1:].isdigit():
            номер = int(сл[1:])
            break
    return номер, out


def снять(db, role, ид, note="проба"):
    return run([sys.executable, str(АРЕНДА), "--db", str(db), "release",
                "--role", role, "--id", str(ид), "--note", note])


def ожидания(db):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT COALESCE(role,'∅'), tool, refused_at FROM tool_lease_waits "
            "ORDER BY id").fetchall()
    finally:
        con.close()


stand = mezo_stand.new("lease-waiters-")
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
# ⚖️ Живые объявления контура из копии УБИРАЮТСЯ. Иначе приёмка судила бы занятость
# инструментов в живой базе на момент прогона — то есть честную работу восьми соседей.
# Ровно этим краснела приёмка bite-pool-step0 (карточка #483): признак, зависящий
# от чужой работы, различает шум.
con.execute("DELETE FROM tool_leases")
con.execute("DELETE FROM tool_lease_waits")
for r in (ЖДУЩАЯ, ДРУГАЯ, ХОЗЯИН):
    con.execute("INSERT INTO roles (role, lifecycle, zone) "
                "VALUES (?,'alive','проба ожиданий')", (r,))
cur = con.execute(
    "INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, done_when)"
    " VALUES (?,?,'тело','open','normal','[]',?,'критерий')",
    (ЖДУЩАЯ, "карточка ждущей роли", ЖДУЩАЯ))
КАРТОЧКА = cur.lastrowid
con.commit()
con.close()

# ═══ ХОЗЯИН объявляет правку карточек и ленты
ид, _ = взять(db, ХОЗЯИН, "backlog.py read-messages.py")

# ═══ ① отказ пишущему записывает ожидание · ③ имя из --actor
rc1, out1 = run([sys.executable, str(КАРТОЧКИ), "--db", str(db), "comment", str(КАРТОЧКА),
                 "--actor", ЖДУЩАЯ, "--body", "проба"])
следы = ожидания(db)
case("① отказ пишущему САМ записывает ожидание — роль не делает ничего лишнего",
     rc1 == 3 and len(следы) == 1, f"код {rc1} · записей {len(следы)}")
case("③ имя роли взято из --actor, когда MEZO_ROLE не задан",
     bool(следы) and следы[0][0] == ЖДУЩАЯ, f"в базе: {следы[0][0] if следы else '—'}")

# ═══ ⑨ повторный отказ той же роли не плодит строк
час_первого = следы[0][2] if следы else None
run([sys.executable, str(КАРТОЧКИ), "--db", str(db), "comment", str(КАРТОЧКА),
     "--actor", ЖДУЩАЯ, "--body", "проба два"])
следы2 = ожидания(db)
case("⑨ повторный отказ не плодит строк: час ПЕРВОГО отказа сохранён",
     len(следы2) == 1 and следы2[0][2] == час_первого,
     f"записей {len(следы2)} · час {следы2[0][2] if следы2 else '—'}")

# ═══ ② ВСТРЕЧНЫЙ: читающему отказа нет ⇒ ожидание не пишется
# ⚖️ Считаем ПРИРАЩЕНИЕ, а не итог. Первая редакция сверяла «записей ровно одна» — и при
# поломке «отказ не пишет ожидание» этот случай краснел ВМЕСТЕ с ①, то есть не различал
# ничего своего: ноль записей он читал как нарушение. Поймано нарочной поломкой A
# (предсказала 6 красных, вышло 7). Признак, краснеющий от чужой поломки, не различает.
было_до = len(ожидания(db))
rc2, _ = run([sys.executable, str(ЛЕНТА), "--db", str(db), "--role", ДРУГАЯ, "--limit", "1"])
стало_после = len(ожидания(db))
case("② ВСТРЕЧНЫЙ: читающему инструменту отказа нет ⇒ ожидание НЕ прибавилось",
     стало_после == было_до, f"было {было_до} → стало {стало_после}")

# ═══ ④ имя из MEZO_ROLE, когда он задан (довода --actor в вызове нет)
run([sys.executable, str(КАРТОЧКИ), "--db", str(db), "status", str(КАРТОЧКА), "in_review",
     "--actor", ДРУГАЯ], role=ДРУГАЯ)
имена = {r[0] for r in ожидания(db)}
case("④ имя роли взято из MEZO_ROLE, когда он задан", ДРУГАЯ in имена,
     f"в базе: {sorted(имена)}")

# ═══ ⑤ безымянный вызов: имени нет ни в доводах, ни в окружении
con = sqlite3.connect(str(db))
con.execute("INSERT INTO tool_lease_waits (lease_id, role, tool) VALUES (?,NULL,'backlog.py')",
            (ид,))
con.commit()
con.close()
безымянных = sum(1 for r in ожидания(db) if r[0] == "∅")
case("⑤ безымянное ожидание хранится БЕЗ имени, а не под выдуманным", безымянных == 1,
     f"безымянных: {безымянных}")

# ═══ ⑥ снятие называет ждущих · ⑧ снятие ПРОХОДИТ
rc3, out3 = снять(db, ХОЗЯИН, ид, note="проба снятия")
case("⑥ снятие называет ждущих поимённо, с часом отказа",
     "ТЕБЯ ЖДАЛИ" in out3 and ЖДУЩАЯ in out3 and ДРУГАЯ in out3
     and "ждёт с" in out3 and "безымянных" in out3)
case("⑧ ВСТРЕЧНЫЙ (главный): снятие при ждущих ПРОХОДИТ — подсказка не стала воротами",
     rc3 == 0 and "СНЯТО ОБЪЯВЛЕНИЕ" in out3, f"код {rc3}")

# ═══ ⑦ ВСТРЕЧНЫЙ: снятие без ждущих — пустого раздела НЕТ
ид2, _ = взять(db, ХОЗЯИН, "write-message.py")
rc4, out4 = снять(db, ХОЗЯИН, ид2, note="никто не ждал")
case("⑦ ВСТРЕЧНЫЙ: снятие БЕЗ ждущих не печатает пустого раздела",
     rc4 == 0 and "ТЕБЯ ЖДАЛИ" not in out4)

# ═══ ⑩ ждущий видит освободившееся в СВОЕЙ сводке
rc5, out5 = run([sys.executable, str(СВОДКА), "--role", ЖДУЩАЯ, "--db", str(db)])
rc6, out6 = run([sys.executable, str(СВОДКА), "--role", ХОЗЯИН, "--db", str(db)])
case("⑩ ждущий видит освободившееся в своей сводке, а не ждавший — не видит",
     rc5 == 0 and "ОСВОБОДИЛОСЬ" in out5 and "backlog.py" in out5
     and "ОСВОБОДИЛОСЬ" not in out6,
     f"у ждущей: {'есть' if 'ОСВОБОДИЛОСЬ' in out5 else 'НЕТ'} · "
     f"у хозяина: {'есть' if 'ОСВОБОДИЛОСЬ' in out6 else 'НЕТ'}")

# ═══ ⑪ ТРЕТИЙ ИСХОД: база без таблицы
db_old = stand / "old.db"
shutil.copy(db, db_old)
con = sqlite3.connect(str(db_old))
con.execute("DROP TABLE tool_lease_waits")
con.commit()
проверка = con.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_lease_waits'").fetchone()
con.close()
assert проверка is None, "случай ⑪ ничего не различает: таблица осталась"
ид3, _ = взять(db_old, ХОЗЯИН, "backlog.py")
rc7, out7 = снять(db_old, ХОЗЯИН, ид3, note="без таблицы")
rc8, out8 = run([sys.executable, str(СВОДКА), "--role", ЖДУЩАЯ, "--db", str(db_old)])
case("⑪ ТРЕТИЙ ИСХОД: база БЕЗ таблицы — снятие и сводка живут, а не падают",
     rc7 == 0 and "СНЯТО ОБЪЯВЛЕНИЕ" in out7
     and rc8 == 0 and "ИСТОЧНИК НЕ ПРОЧИТАН" not in out8 and "ОСВОБОДИЛОСЬ" not in out8,
     f"снятие код {rc7} · сводка код {rc8}")

# ═══ ⑫ контроль
живой = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы_живые = живой.execute("SELECT COUNT(*) FROM roles WHERE role IN (?,?,?)",
                            (ЖДУЩАЯ, ДРУГАЯ, ХОЗЯИН)).fetchone()[0]
следы_живые += живой.execute("SELECT COUNT(*) FROM tool_leases WHERE role IN (?,?,?)",
                             (ЖДУЩАЯ, ДРУГАЯ, ХОЗЯИН)).fetchone()[0]
живой.close()
case("⑫ контроль: своих следов в живой базе нет", следы_живые == 0,
     f"следов: {следы_живые}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
