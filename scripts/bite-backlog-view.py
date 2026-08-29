r"""
bite-backlog-view.py — приёмка витрины открытых карточек (карточка #112, пункты ② и ④).

⛔ РАБОТАЕТ ТОЛЬКО ПО КОПИИ живой базы: он ЗАВОДИТ карточку — это мутация, и делать её
на живой базе ради проверки нельзя. Копия создаётся сама, во временный каталог.

ЧЕТЫРЕ СЛУЧАЯ, И ТРИ ИЗ НИХ ВСТРЕЧНЫЕ (проверка, которая только подтверждает, ничего
не проверяет — класс @CORE 07.08: «①слепая → ②узаконивает → ③зелёная ИЗ-ЗА дефекта»):
  ① слепок роли ПЕЧАТАЕТ её открытые карточки, и число совпадает с backlog.py list
  ② РАЗЛИЧАЮЩИЙ: завёл карточку — она в слепке БЕЗ единой правки слепка
  ③ ВСТРЕЧНЫЙ: роль без открытых карточек получает «открытых нет», а не пустоту
  ④ ВСТРЕЧНЫЙ: половинка токена ленты осталась в ПОСЛЕДНЕЙ строке вывода читалки —
     витрина не имеет права сдвинуть её (иначе сломан механизм, ради которого она там)

Запуск:  python <КОНТУР>/.mezosync/scripts/bite-backlog-view.py
"""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent / "mezosync.db"
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
shutil.copy2(LIVE, db)
print(f"копия живой базы: {db}\n")

# НОРМАЛИЗАЦИЯ: пулы в паузу. С 27.08 карточки АКТИВНОГО пула стоят первыми (шаг 0
# нового порядка), и «критическая попадёт в пятёрку» перестаёт быть обещанием у роли
# с пятью+ карточками пула — случай ② краснел ЧЕСТНО, но чужим обещанием. Порядок
# пула стережёт своя приёмка (bite-pool-step0); эта меряет витрину и память.
_con = sqlite3.connect(str(db))
_con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
_con.commit()
_con.close()

# роль с карточками и роль без — берём из самой базы, не из своей памяти
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
rich = con.execute(
    "SELECT role, count(*) c FROM backlog WHERE status IN ('open','in_progress','blocked','in_review') "
    "AND role <> 'SHARED' GROUP BY role ORDER BY c DESC LIMIT 1").fetchone()[0]
known = [r for r, in con.execute("SELECT DISTINCT role FROM phoenix")]
con.close()

# ① слепок печатает карточки, число совпадает с backlog.py list
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
# ⚠️ priority=critical НЕ ради красоты: витрина печатает СВОДКУ + пять самых срочных.
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

# ⑤ и сам ack по этому выводу проходит — витрина не сломала контракт чтения
half2 = lines[-1].split("<первая>-")[1].strip() if "<первая>-" in lines[-1] else ""
half1 = lines[0].split("ПЕРВАЯ половина")[1].split(",")[0].strip() if "ПЕРВАЯ половина" in lines[0] else ""
out5, err5, _c = run("read-messages.py", "--db", str(db), "--role", reader, "--ack", f"{half1}-{half2}")
check("⑤ ack по напечатанным половинкам принят", "[ack]" in out5, out5.strip()[:70] or err5.strip()[:70])

mezo_stand.release(tmp)  # уборка отложена до исхода прогона
print("\n" + ("✅ ПРИЁМКА ЗЕЛЁНАЯ" if ok else "🔴 ПРИЁМКА КРАСНАЯ"))
sys.exit(mezo_stand.finish(0 if ok else 1))
