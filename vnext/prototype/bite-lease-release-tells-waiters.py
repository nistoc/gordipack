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
  ⑬ ТРЕТИЙ ИСХОД (пункт ④ критерия): ожидание СТАРШЕ окна 12 ч протухло —
     сводка его НЕ показывает. Рецепт приёмщика @CHROME, закрыт 2026-08-30
  ⑭ ВСТРЕЧНЫЙ к ⑬: ожидание ВНУТРИ окна показано — порог отсекает старое, а не всё
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

LEASE = mezo_target.script("lease.py")
CARDS = mezo_target.script("backlog.py")
BRIEF = mezo_target.script("role-brief.py")
FEED = mezo_target.script("read-messages.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
# mezo_stand — из каталога самой приёмки, той же версии пакета (Э6: empty_db есть только с этой
# версии; scripts/ живого контура до установки выпуска — прежней). Порядок поиска модулей для
# испытуемых инструментов прежний: вставка снимается сразу после импорта.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
sys.path.pop(0)

OK = FAIL = 0
WAITER = "ZZW"          # упирается в чужое объявление
OTHER = "ZZX"          # упирается вторая, чтобы список был не из одного
OWNER = "ZZY"          # держит объявление


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


def take(db, role, tools, minutes=60):
    rc, out = run([sys.executable, str(LEASE), "--db", str(db), "take", "--role", role,
                   "--tools", tools, "--reason", "проба приёмки карточки #488",
                   "--minutes", str(minutes)])
    number = None
    for word in out.split():
        if word.startswith("#") and word[1:].isdigit():
            number = int(word[1:])
            break
    return number, out


def release(db, role, id1, note="проба"):
    return run([sys.executable, str(LEASE), "--db", str(db), "release",
                "--role", role, "--id", str(id1), "--note", note])


def waits(db):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT COALESCE(role,'∅'), tool, refused_at FROM tool_lease_waits "
            "ORDER BY id").fetchall()
    finally:
        con.close()


stand = mezo_stand.new("lease-waiters-")
db = stand / "mezosync.db"
mezo_stand.empty_db(LIVE_DB, db)
con = sqlite3.connect(str(db))
# ⚖️ Живые объявления контура из копии УБИРАЮТСЯ. Иначе приёмка судила бы занятость
# инструментов в живой базе на момент прогона — то есть честную работу восьми соседей.
# Ровно этим краснела приёмка bite-pool-step0 (карточка #483): признак, зависящий
# от чужой работы, различает шум.
con.execute("DELETE FROM tool_leases")
con.execute("DELETE FROM tool_lease_waits")
for r in (WAITER, OTHER, OWNER):
    con.execute("INSERT INTO roles (role, lifecycle, zone) "
                "VALUES (?,'alive','проба ожиданий')", (r,))
cur = con.execute(
    "INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, done_when)"
    " VALUES (?,?,'тело','open','normal','[]',?,'критерий')",
    (WAITER, "карточка ждущей роли", WAITER))
CARD = cur.lastrowid
con.commit()
con.close()

# ═══ ХОЗЯИН объявляет правку карточек и ленты
id1, _ = take(db, OWNER, "backlog.py read-messages.py")

# ═══ ① отказ пишущему записывает ожидание · ③ имя из --actor
rc1, out1 = run([sys.executable, str(CARDS), "--db", str(db), "comment", str(CARD),
                 "--actor", WAITER, "--body", "проба"])
traces_found = waits(db)
case("① отказ пишущему САМ записывает ожидание — роль не делает ничего лишнего",
     rc1 == 3 and len(traces_found) == 1, f"код {rc1} · записей {len(traces_found)}")
case("③ имя роли взято из --actor, когда MEZO_ROLE не задан",
     bool(traces_found) and traces_found[0][0] == WAITER, f"в базе: {traces_found[0][0] if traces_found else '—'}")

# ═══ ⑨ повторный отказ той же роли не плодит строк
first_hour = traces_found[0][2] if traces_found else None
run([sys.executable, str(CARDS), "--db", str(db), "comment", str(CARD),
     "--actor", WAITER, "--body", "проба два"])
traces_found2 = waits(db)
case("⑨ повторный отказ не плодит строк: час ПЕРВОГО отказа сохранён",
     len(traces_found2) == 1 and traces_found2[0][2] == first_hour,
     f"записей {len(traces_found2)} · час {traces_found2[0][2] if traces_found2 else '—'}")

# ═══ ② ВСТРЕЧНЫЙ: читающему отказа нет ⇒ ожидание не пишется
# ⚖️ Считаем ПРИРАЩЕНИЕ, а не итог. Первая редакция сверяла «записей ровно одна» — и при
# поломке «отказ не пишет ожидание» этот случай краснел ВМЕСТЕ с ①, то есть не различал
# ничего своего: ноль записей он читал как нарушение. Поймано нарочной поломкой A
# (предсказала 6 красных, вышло 7). Признак, краснеющий от чужой поломки, не различает.
was_before = len(waits(db))
rc2, _ = run([sys.executable, str(FEED), "--db", str(db), "--role", OTHER, "--limit", "1"])
became_after = len(waits(db))
case("② ВСТРЕЧНЫЙ: читающему инструменту отказа нет ⇒ ожидание НЕ прибавилось",
     became_after == was_before, f"было {was_before} → стало {became_after}")

# ═══ ④ имя из MEZO_ROLE, когда он задан (довода --actor в вызове нет)
run([sys.executable, str(CARDS), "--db", str(db), "status", str(CARD), "in_review",
     "--actor", OTHER], role=OTHER)
names = {r[0] for r in waits(db)}
case("④ имя роли взято из MEZO_ROLE, когда он задан", OTHER in names,
     f"в базе: {sorted(names)}")

# ═══ ⑤ безымянный вызов: имени нет ни в доводах, ни в окружении
con = sqlite3.connect(str(db))
con.execute("INSERT INTO tool_lease_waits (lease_id, role, tool) VALUES (?,NULL,'backlog.py')",
            (id1,))
con.commit()
con.close()
unnamed = sum(1 for r in waits(db) if r[0] == "∅")
case("⑤ безымянное ожидание хранится БЕЗ имени, а не под выдуманным", unnamed == 1,
     f"безымянных: {unnamed}")

# ═══ ⑥ снятие называет ждущих · ⑧ снятие ПРОХОДИТ
rc3, out3 = release(db, OWNER, id1, note="проба снятия")
case("⑥ снятие называет ждущих поимённо, с часом отказа",
     "ТЕБЯ ЖДАЛИ" in out3 and WAITER in out3 and OTHER in out3
     and "ждёт с" in out3 and "безымянных" in out3)
case("⑧ ВСТРЕЧНЫЙ (главный): снятие при ждущих ПРОХОДИТ — подсказка не стала запретом",
     rc3 == 0 and "СНЯТО ОБЪЯВЛЕНИЕ" in out3, f"код {rc3}")

# ═══ ⑦ ВСТРЕЧНЫЙ: снятие без ждущих — пустого раздела НЕТ
id2, _ = take(db, OWNER, "write-message.py")
rc4, out4 = release(db, OWNER, id2, note="никто не ждал")
case("⑦ ВСТРЕЧНЫЙ: снятие БЕЗ ждущих не печатает пустого раздела",
     rc4 == 0 and "ТЕБЯ ЖДАЛИ" not in out4)

# ═══ ⑩ ждущий видит освободившееся в СВОЕЙ сводке
rc5, out5 = run([sys.executable, str(BRIEF), "--role", WAITER, "--db", str(db)])
rc6, out6 = run([sys.executable, str(BRIEF), "--role", OWNER, "--db", str(db)])
case("⑩ ждущий видит освободившееся в своей сводке, а не ждавший — не видит",
     rc5 == 0 and "ОСВОБОДИЛОСЬ" in out5 and "backlog.py" in out5
     and "ОСВОБОДИЛОСЬ" not in out6,
     f"у ждущей: {'есть' if 'ОСВОБОДИЛОСЬ' in out5 else 'НЕТ'} · "
     f"у хозяина: {'есть' if 'ОСВОБОДИЛОСЬ' in out6 else 'НЕТ'}")

# ═══ ⑬/⑭ ПОРОГ ПРОТУХАНИЯ ОЖИДАНИЯ — пункт ④ критерия карточки #488.
# Рецепт приёмщика @CHROME (разбор 2026-08-30 12:35 UTC), дословно: «положить ожидание
# с часом отказа СТАРШЕ окна и потребовать, чтобы сводка его НЕ показала; встречным —
# ожидание внутри окна показывается; порча окна обязана развести оба».
# 🩸 ПОЧЕМУ ОН ДО СИХ ПОР НЕ БЫЛ ЗАКРЫТ: порог 12 часов стоял в коде и был назван словами
# в сдаче, но НИ ОДИН случай его не судил — приёмщик испортил окно (12 ч → 99999 ч)
# и получил те же 12 из 12. Проверку, которую нельзя заставить покраснеть, засчитывать нельзя.
# ⚖️ ГРАНИЦА, названная здесь, а не в отчёте: окно механизм считает ОТ ЧАСА СНЯТИЯ
# (role-brief.py: l.released_at > datetime('now','-12 hours')), а не от часа отказа
# ждущего. Рецепт говорит «час отказа» — поэтому старыми ставятся ОБА часа сразу:
# иначе случай прошёл бы по причине, которой в механизме нет.
AGING = "ZZT"
OLD_TOOL = "zz-давно-снятый.py"
FRESH_TOOL = "zz-только-что-снятый.py"

con = sqlite3.connect(str(db))
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба протухания')",
            (AGING,))
# ① объявление, снятое ЗА ПРЕДЕЛАМИ окна: 20 часов назад
cur = con.execute(
    "INSERT INTO tool_leases (role, tools, reason, taken_at, until_utc, released_at, note) "
    "VALUES (?,?,'проба протухания', datetime('now','-21 hours'), datetime('now','-19 hours'), "
    "        datetime('now','-20 hours'), 'снято двадцать часов назад')",
    (OWNER, OLD_TOOL))
old = cur.lastrowid
con.execute("INSERT INTO tool_lease_waits (lease_id, role, tool, refused_at) "
            "VALUES (?,?,?, datetime('now','-21 hours'))",
            (old, AGING, OLD_TOOL))
# ② ВСТРЕЧНОЕ объявление ТОЙ ЖЕ роли, снятое ВНУТРИ окна
cur = con.execute(
    "INSERT INTO tool_leases (role, tools, reason, taken_at, until_utc, released_at, note) "
    "VALUES (?,?,'проба свежего', datetime('now','-2 hours'), datetime('now','+1 hours'), "
    "        datetime('now','-1 hours'), 'снято час назад')",
    (OWNER, FRESH_TOOL))
fresh = cur.lastrowid
con.execute("INSERT INTO tool_lease_waits (lease_id, role, tool, refused_at) "
            "VALUES (?,?,?, datetime('now','-2 hours'))",
            (fresh, AGING, FRESH_TOOL))
con.commit()
con.close()

rc9, out9 = run([sys.executable, str(BRIEF), "--role", AGING, "--db", str(db)])
case("⑬ ТРЕТИЙ ИСХОД: ожидание СТАРШЕ окна протухло — сводка его НЕ показывает",
     rc9 == 0 and OLD_TOOL not in out9,
     f"снято 20 ч назад при окне 12 ч · в сводке: "
     f"{'ПОКАЗАН (порог не работает)' if OLD_TOOL in out9 else 'нет, как и должно'}")
case("⑭ ВСТРЕЧНЫЙ к ⑬: ожидание ВНУТРИ окна показано — порог отсекает старое, а не всё",
     rc9 == 0 and FRESH_TOOL in out9 and "ОСВОБОДИЛОСЬ" in out9,
     f"снято 1 ч назад · в сводке: "
     f"{'показан' if FRESH_TOOL in out9 else 'НЕТ — отсекается лишнее'}")

# ═══ ⑪ ТРЕТИЙ ИСХОД: база без таблицы
db_old = stand / "old.db"
shutil.copy(db, db_old)
con = sqlite3.connect(str(db_old))
con.execute("DROP TABLE tool_lease_waits")
con.commit()
check = con.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_lease_waits'").fetchone()
con.close()
assert check is None, "случай ⑪ ничего не различает: таблица осталась"
id3, _ = take(db_old, OWNER, "backlog.py")
rc7, out7 = release(db_old, OWNER, id3, note="без таблицы")
rc8, out8 = run([sys.executable, str(BRIEF), "--role", WAITER, "--db", str(db_old)])
case("⑪ ТРЕТИЙ ИСХОД: база БЕЗ таблицы — снятие и сводка живут, а не падают",
     rc7 == 0 and "СНЯТО ОБЪЯВЛЕНИЕ" in out7
     and rc8 == 0 and "ИСТОЧНИК НЕ ПРОЧИТАН" not in out8 and "ОСВОБОДИЛОСЬ" not in out8,
     f"снятие код {rc7} · сводка код {rc8}")

# ═══ ⑫ контроль
live = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
live_traces = live.execute("SELECT COUNT(*) FROM roles WHERE role IN (?,?,?)",
                            (WAITER, OTHER, OWNER)).fetchone()[0]
live_traces += live.execute("SELECT COUNT(*) FROM tool_leases WHERE role IN (?,?,?)",
                             (WAITER, OTHER, OWNER)).fetchone()[0]
live.close()
case("⑫ контроль: своих следов в живой базе нет", live_traces == 0,
     f"следов: {live_traces}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
