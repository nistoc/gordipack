r"""
bite-backlog-view.py — приёмка сводки открытых карточек (карточка #112, пункты ② и ④).

⛔ РАБОТАЕТ ТОЛЬКО ПО КОПИИ живой базы: он ЗАВОДИТ карточку — это мутация, и делать её
на живой базе ради проверки нельзя. Копия создаётся сама, во временный каталог.

ЧЕТЫРЕ СЛУЧАЯ, И ТРИ ИЗ НИХ ВСТРЕЧНЫЕ (проверка, которая только подтверждает, ничего
не проверяет — класс @CORE 07.08: «①слепая → ②узаконивает → ③зелёная ИЗ-ЗА дефекта»):
  ① сохранённая память роли ПЕЧАТАЕТ её открытые карточки, и число совпадает с backlog.py list
  ② РАЗЛИЧАЮЩИЙ: завёл карточку — она в сохранённой памяти БЕЗ единой её правки
  ③ ВСТРЕЧНЫЙ: роль без открытых карточек получает «открытых нет», а не пустоту
  ④ ВСТРЕЧНЫЙ: половинка токена ленты осталась в ПОСЛЕДНЕЙ строке вывода читалки —
     сводка карточек не имеет права сдвинуть её (иначе сломан механизм, ради которого она там)

Запуск:  python <КОНТУР>/.mezosync/scripts/bite-backlog-view.py
"""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_paths  # noqa: E402 — базу берём резолвером, а не по положению файла (карточка #689)

HERE = Path(__file__).resolve().parent
# База — РЕЗОЛВЕРОМ, а не «рядом с моим каталогом». В установленном контуре это один
# и тот же путь, а в клоне пакета рядом лежит ПУСТОЙ mezosync.db в 0 байт: приёмка
# снимала копию пустышки и падала позже на «no such table» (карточка #689, замер
# 13.11 18:42 UTC). Базы нет — отказ словами с кодом 2, а не падение.
LIVE = mezo_paths.live_db_for_check(__file__, "приёмка сводки открытых карточек")
PY = sys.executable

ok = True


def run(script, *a):
    r = subprocess.run([PY, str(HERE / script), *a], capture_output=True, text=True)
    return r.stdout, r.stderr, r.returncode


def check(name, cond, detail=""):
    global ok
    print(f"{'✅' if cond else '🔴'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


tmp = mezo_stand.new("bite-backlog-view-")
db = tmp / "mezosync.db"
mezo_stand.snapshot_db(LIVE, db)
print(f"копия живой базы: {db}\n")

# НОРМАЛИЗАЦИЯ: пулы в паузу. С 27.08 карточки АКТИВНОГО пула стоят первыми (шаг 0
# нового порядка), и «критическая попадёт в пятёрку» перестаёт быть обещанием у роли
# с пятью+ карточками пула — случай ② краснел ЧЕСТНО, но чужим обещанием. Порядок
# пула стережёт своя приёмка (bite-pool-step0); эта меряет сводку карточек и память.
_con = sqlite3.connect(str(db))
_con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
_con.commit()
_con.close()

# роль с карточками и роль без — берём из самой базы, не из своей памяти
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
_rich_row = con.execute(
    "SELECT role, count(*) c FROM backlog WHERE status IN ('open','in_progress','blocked','in_review') "
    "AND role <> 'SHARED' GROUP BY role ORDER BY c DESC LIMIT 1").fetchone()
if _rich_row is None:
    # Свежий контур: карточек нет НИ ОДНОЙ, и сводку мерить не на чем. Прежде здесь
    # падало «TypeError: NoneType is not subscriptable» — беда среды выглядела бедой
    # кода (замер 13.11 19:02 UTC на контуре, собранном init-group.py). Отказ словами
    # с кодом 2, как велит карточка #689; признак «нулевой день» тут не нужен — пустой
    # список карточек и есть прямой ответ на вопрос приёмки.
    con.close()
    print("⛔ НЕ ЗАПУСТИЛАСЬ: в базе нет ни одной открытой карточки (свежий контур) — сводку\n"
          "   открытых карточек мерить не на чем. Это отказ приёмки, а не её провал: код 2\n"
          "   (карточка #689).")
    sys.exit(mezo_stand.finish(2))
rich = _rich_row[0]
known = [r for r, in con.execute("SELECT DISTINCT role FROM phoenix")]
con.close()

# ① сохранённая память печатает карточки, число совпадает с backlog.py list
out, _e, _c = run("read-phoenix.py", "--db", str(db), "--role", rich, "--section", "state")
lst, _e, _c = run("backlog.py", "--db", str(db), "list", "--role", rich)
n_list = int(lst.split("—")[1].split("задач")[0].strip()) if "—" in lst else -1
n_snap = -2
for line in out.splitlines():
    if "ТВОИХ НЕЗАКРЫТЫХ КАРТОЧЕК:" in line:
        n_snap = int(line.split(":")[1].split("·")[0].strip())
check(f"① сохранённая память {rich} печатает открытые карточки", "§4½" in out and n_snap > 0,
      f"в памяти {n_snap}")
check("① число совпадает с backlog.py list", n_snap == n_list, f"в памяти {n_snap} · list {n_list}")

# ② РАЗЛИЧАЮЩИЙ: новая карточка появляется в сохранённой памяти сама
# ⚠️ priority=critical НЕ ради красоты: сводка печатает итог + пять самых срочных.
# Обычная новая карточка у роли с двумя десятками открытых честно НЕ попадёт в пятёрку,
# и требовать её имени значило бы завести проверку под НЕВЕРНОЕ ожидание — то есть
# узаконить в приёмке то, чего механизм не обещает. Проверяем оба обещания раздельно:
# счётчик меняется у ЛЮБОЙ карточки, имя печатается у той, что попала в показанные.
run("backlog.py", "--db", str(db), "add", "--role", rich, "--title", "ПРИЁМКА: карточка-призрак",
    "--priority", "critical",
    "--body", "заведена приёмкой bite-backlog-view.py на КОПИИ базы",
    "--done-when", "существует ровно до конца прогона приёмки")
out2, _e, _c = run("read-phoenix.py", "--db", str(db), "--role", rich, "--section", "state")
n2 = -3
for line in out2.splitlines():
    if "ТВОИХ НЕЗАКРЫТЫХ КАРТОЧЕК:" in line:
        n2 = int(line.split(":")[1].split("·")[0].strip())
check("② заведённая карточка видна в памяти БЕЗ правки памяти", n2 == n_snap + 1,
      f"было {n_snap} → стало {n2}")
check("② и она названа поимённо", "карточка-призрак" in out2)

# ③ ВСТРЕЧНЫЙ: роль без открытых карточек
con = sqlite3.connect(db)
empty = None
for r in known:
    c = con.execute("SELECT count(*) FROM backlog WHERE role=? AND status IN "
                    "('open','in_progress','blocked','in_review')", (r,)).fetchone()[0]
    if c == 0:
        empty = r
        break
if empty is None:                       # у всех что-то открыто — освобождаем одну роль НА КОПИИ
    empty = known[0]
    con.execute("UPDATE backlog SET status='done' WHERE role IN (?, 'SHARED')", (empty,))
    con.commit()
con.close()
out3, _e, _c = run("read-phoenix.py", "--db", str(db), "--role", empty, "--section", "state")
check(f"③ роль {empty} без карточек получает ПРЯМОЕ «открытых нет»",
      "открытых карточек нет" in out3 and "ТВОИХ НЕЗАКРЫТЫХ" not in out3)

# ④ ВСТРЕЧНЫЙ: половинка токена — в ПОСЛЕДНЕЙ строке вывода читалки
con = sqlite3.connect(db)
reader = con.execute("SELECT reader_role FROM read_cursors ORDER BY last_read_id LIMIT 1").fetchone()[0]
con.execute("UPDATE read_cursors SET last_read_id = (SELECT max(id)-3 FROM messages) "
            "WHERE reader_role = ?", (reader,))
con.execute("UPDATE read_batches SET acked_at = datetime('now') WHERE role = ? AND acked_at IS NULL", (reader,))
con.commit()
con.close()
out4, _e, _c = run("read-messages.py", "--db", str(db), "--role", reader, "--limit", "2")
lines = [l for l in out4.splitlines() if l.strip()]
check("④ список карточек напечатан в ленте", any("НЕЗАКРЫТЫХ КАРТОЧЕК" in l for l in lines)
      or any("открытых карточек" in l for l in lines), f"роль {reader}")
check("④ последняя строка вывода — команда --ack с половинкой токена",
      "--ack" in lines[-1], f"последняя строка: {lines[-1][:70]}")
check("④ первая строка несёт ПЕРВУЮ половину", "ПЕРВАЯ половина" in lines[0])

# ⑤ и сам ack по этому выводу проходит — сводка карточек не сломала контракт чтения
half2 = lines[-1].split("<первая>-")[1].strip() if "<первая>-" in lines[-1] else ""
half1 = lines[0].split("ПЕРВАЯ половина")[1].split(",")[0].strip() if "ПЕРВАЯ половина" in lines[0] else ""
out5, err5, _c = run("read-messages.py", "--db", str(db), "--role", reader, "--ack", f"{half1}-{half2}")
check("⑤ ack по напечатанным половинкам принят", "[ack]" in out5, out5.strip()[:70] or err5.strip()[:70])

# ═══ Карточка #774: ВТОРАЯ строка счёта — снятые с хода карточки с событиями за 7 суток ═══
# Свой стенд на копии базы: отдельная роль ACC774 и карточки, заведённые прямо в таблицы;
# время события задаётся смещением от «сейчас» — так же, как его судит сам инструмент.
# Окно считается от текущего ЧАСА, поэтому границу пробуем с запасом: 61 минута за краем —
# вне окна при любой минуте часа, 5 минут внутри края — внутри при любой минуте часа.
MARK_774 = "снятых с хода, но с событиями за 7 суток"
ROLE_774 = "ACC774"
OUT_774 = ("-7 days", "-61 minutes")        # событие старше окна
IN_774 = ("-7 days", "+5 minutes")          # событие моложе края окна


def card_774(con, role, title, status, events):
    """Карточка роли в нужном состоянии; events — перечень наборов смещений времени, по событию на набор."""
    bid = con.execute("INSERT INTO backlog (role, title, status, created_by) VALUES (?,?,?, 'ACC')",
                      (role, title, status)).lastrowid
    for mods in events:
        con.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type) "
                    "VALUES (?, datetime('now', " + ", ".join("?" * len(mods)) + "), 'ACC', 'comment')",
                    (bid, *mods))
    return bid


def line_774(role=ROLE_774):
    """Вторая строка счёта из вывода list: (есть ли, номера, число из строки, весь вывод)."""
    text, _e, _c = run("backlog.py", "--db", str(db), "list", "--role", role)
    row = [l for l in text.splitlines() if MARK_774 in l]
    if not row:
        return False, [], None, text
    # пустой перечень («(карточки )») — не повод падать: случай ⑨ обязан назвать себя, а не дать трассировку
    ids = [int(p.strip().lstrip("#")) for p in row[0].split("(карточки")[1].rstrip(") ").split("·")
           if p.strip().lstrip("#").isdigit()]
    return True, ids, int(row[0].split("суток:")[1].split("(")[0]), text


con = sqlite3.connect(db)
card_774(con, ROLE_774, "открытая, чтобы список не был пуст", "open", [("-1 hours",)])
fresh_774 = card_774(con, ROLE_774, "снята, событие час назад", "dropped", [("-1 hours",)])
bare_774 = card_774(con, ROLE_774, "снята, событий НЕТ вовсе", "dropped", [])
stale_774 = card_774(con, ROLE_774, "снята, событие старше окна", "dropped", [OUT_774])
inside_774 = card_774(con, ROLE_774, "снята, событие внутри окна у самого края", "dropped", [IN_774])
other_774 = card_774(con, "ACC774B", "снята ДРУГОЙ роли, событие час назад", "dropped", [("-1 hours",)])
con.commit()
con.close()

has, ids, n_line, out_774 = line_774()
check("⑥ вторая строка счёта печатается, с числом и номерами снятых с недавними событиями",
      has and n_line == len(ids) and {fresh_774, inside_774} <= set(ids),
      f"номера {ids}, число {n_line}")
check("⑦ встречный: снятая БЕЗ событий за 7 суток (и снятая чужой роли) в строку не попадает",
      has and bare_774 not in ids and other_774 not in ids,
      f"без событий #{bare_774}, чужой роли #{other_774}, в строке {ids}")
check("⑧ встречный (граница окна): событие старше 7 суток карточку не поднимает, моложе — поднимает",
      has and stale_774 not in ids and inside_774 in ids,
      f"старше #{stale_774} · моложе #{inside_774} · в строке {ids}")
# ⑨ при нуле строка не печатается вовсе. Роль БЕЗ снятых карточек: так случай не зависит ни от
# окна, ни от отбора событий — их судят ⑦ и ⑧, и нарочная поломка одного не роняет чужой случай.
con = sqlite3.connect(db)
card_774(con, "ACC774C", "открытая, снятых у роли нет", "open", [("-1 hours",)])
con.commit()
con.close()
has0, ids0, _n0, out0 = line_774("ACC774C")
check("⑨ встречный: у роли нет снятых — строки НЕТ вовсе, заголовок списка цел",
      (not has0) and "📋 backlog [ACC774C + SHARED]" in out0, f"строка есть: {has0}")

mezo_stand.release(tmp)  # уборка отложена до исхода прогона
print("\n" + ("✅ ПРИЁМКА ЗЕЛЁНАЯ" if ok else "🔴 ПРИЁМКА КРАСНАЯ"))
sys.exit(mezo_stand.finish(0 if ok else 1))
