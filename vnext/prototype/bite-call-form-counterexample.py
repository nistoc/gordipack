"""Приёмка карточки #50: гард «форма вызова» отличает ПРИКАЗ от КОНТРПРИМЕРА.

Находка @ING #2756: образец `python .mezosync/scripts` искался по всему тексту разом, и
строка-предупреждение («⛔ НЕ зови так: python .mezosync/scripts/x.py — падает») давала
тот же сигнал, что живой относительный вызов. Роль, записавшая урок правильно, получала
вечное красное и переставала верить гарду.

⚠️ ПОЧЕМУ ПРОГОН, А НЕ ЧТЕНИЕ: критерий карточки требует обе стороны ЗАПУСКОМ. Живых
совпадений в слепках сегодня НОЛЬ (замер 14:37 UTC) — то есть на текущих данных дефект
не воспроизводится вовсе. Поэтому слепки-образцы подкладываются в КОПИЮ базы, а гард
зовётся с `--db` (ручка заведена тем же ходом: сторож, который нельзя запустить по копии,
нельзя и проверить).

⛔ ЖИВАЯ БАЗА НЕ ТРОГАЕТСЯ: копия делается файловым копированием, гард открывает её ro.
"""
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(r"C:\guts\.atlas\.mezosync\scripts\guard-all.py")
LIVE = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")

ORDER = r"python .mezosync\scripts\read-messages.py --role COORD"
COUNTER = r"⛔ НЕ зови относительно: python .mezosync\scripts\read-messages.py — падает"

ok = True


def run_with_snapshot(line, label):
    """Кладёт строку в слепок КОПИИ базы и возвращает вывод гарда по этой копии."""
    tmp = Path(tempfile.gettempdir()) / f"bite-callform-{label}.db"
    shutil.copy(LIVE, tmp)
    c = sqlite3.connect(tmp)
    c.execute("UPDATE phoenix SET body = body || ? WHERE role='COORD' AND section='state'",
              ("\n" + line + "\n",))
    c.commit()
    c.close()
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(tmp),
                        "--skip", "utc,drift,чтение ленты,заглушки"],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or "")


def check(num, cond, what, got=""):
    global ok
    print(f"{'✅' if cond else '🔴'} {num} {what}")
    if got:
        print(f"   {got}")
    if not cond:
        ok = False


# ── ① КОНТРПРИМЕР НЕ ОБВИНЯЕТСЯ. Это и есть предмет карточки.
out = run_with_snapshot(COUNTER, "counter")
flagged = "относительная в слепках" in out
check("①", not flagged, "строка-предупреждение НЕ поднимает жёлтое (урок записан правильно)",
      "прощено: " + (re.search(r"прощено как контрпримеры.*", out).group(0)[:80]
                     if "прощено" in out else "(строка не напечатана!)"))

# ② РАЗЛИЧАЮЩИЙ: прощение обязано быть ВИДНЫМ. Молчаливое прощение — ложное зелёное,
#   и оно опаснее ложного красного: усыпляет вместо того, чтобы раздражать.
check("②", "прощено как контрпримеры" in out, "прощение НАЗВАНО числом, а не молчаливо")

# ③ РАЗЛИЧАЮЩИЙ: настоящий приказ по-прежнему ловится. Без этого починка была бы
#   не починкой, а снятием защиты — ровно тот исход, которого боится карточка.
out2 = run_with_snapshot(ORDER, "order")
check("③", "относительная в слепках" in out2, "живой относительный вызов ПО-ПРЕЖНЕМУ ловится",
      next((l.strip() for l in out2.splitlines() if "относительная в слепках" in l), "")[:100])

# ④ РАЗЛИЧАЮЩИЙ: обе строки рядом. Прощение одной не должно глушить другую —
#   иначе достаточно приписать «⛔» где угодно в слепке, чтобы ослепить гард целиком.
out3 = run_with_snapshot(COUNTER + "\n" + ORDER, "both")
check("④", "относительная в слепках" in out3,
      "контрпример РЯДОМ с приказом не глушит приказ")

# ⑤ РАЗЛИЧАЮЩИЙ: чистый слепок молчит — гард не стал срабатывать на всём подряд.
out4 = run_with_snapshot("обычная строка без вызовов", "clean")
check("⑤", "относительная в слепках" not in out4, "на чистом слепке гард молчит")

# ⑥ ЖИВАЯ БАЗА НЕ ЗАДЕТА: приёмка не смеет менять то, что проверяет.
c = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
body = c.execute("SELECT body FROM phoenix WHERE role='COORD' AND section='state'").fetchone()[0]
check("⑥", ORDER not in body and COUNTER not in body,
      "ЖИВАЯ база не изменена приёмкой (образцы легли только в копии)")

print()
print("✅ КАРТОЧКА #50: обе стороны проверены ПРОГОНОМ" if ok else "🔴 ПРИЁМКА КРАСНАЯ")
sys.exit(0 if ok else 1)
