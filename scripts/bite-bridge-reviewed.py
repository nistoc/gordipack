r"""
bite-bridge-reviewed.py — приёмка ЖЕСТА РАЗБОРА записки моста (карточка #117).

ПРЕДМЕТ. Признак «записка моста лежит без разбора» гасился запросом
`body_md LIKE '%имя файла%'` — то есть ЛЮБЫМ упоминанием имени в ленте. Замер @opssre
07.08 16:36 UTC: признак погасила ЕГО ЖЕ записка, в которой он жаловался, что записку
никто не разобрал. Проверка стерегла ПРИЗНАК (имя встретилось) вместо СВОЙСТВА (прочли).

ПЯТЬ СЛУЧАЕВ, ЧЕТЫРЕ ВСТРЕЧНЫХ. Плюс КОНТРОЛЬНАЯ ПАРА в каждом «молчащем» случае —
норма @PROTO 07.08 16:40 UTC: молчание засчитывается за верный ответ ТОЛЬКО когда
доказано, что программа не молчит вообще. Его первая приёмка была зелёной на трёх
случаях подряд просто потому, что не видела ничего.

⛔ РАБОТАЕТ ПО КОПИИ живой базы: пишет ноты. Копия создаётся сама.
Запуск:  python <КОНТУР>/.mezosync/scripts/bite-bridge-reviewed.py
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
FILE = "answer.probe-bite-bridge.md"          # имя, которого в ленте нет ни разу
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"{'✅' if cond else '🔴'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


def note(db, tmp, text, *extra):
    p = tmp / "note.md"
    p.write_text(text, encoding="utf-8")
    r = subprocess.run([PY, str(HERE / "write-message.py"), "--db", str(db),
                        "--role", "COORD", "--file", str(p), *extra],
                       capture_output=True, text=True)
    return r


def reviewed(db, name=FILE):
    """Ровно тот запрос, которым теперь гасит guard-all."""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute("SELECT MAX(at) FROM bridge_reviewed WHERE file_name = ?", (name,)).fetchone()[0]
    except sqlite3.OperationalError:
        return None                            # таблицы ещё нет — «разбора не было»
    finally:
        c.close()


tmp = mezo_stand.new("bite-bridge-reviewed-")
db = tmp / "mezosync.db"
shutil.copy2(LIVE, db)
print(f"копия живой базы: {db}\n")

# ① ВСТРЕЧНЫЙ: имени нет нигде ⇒ разбора нет
check("① чистое имя — разбора нет", reviewed(db) is None)

# ② ВСТРЕЧНЫЙ И ГЛАВНЫЙ: записка НАЗЫВАЕТ файл, жеста нет ⇒ по-прежнему не разобрано.
#    Это ровно случай @opssre: жалоба на неразобранную записку гасила признак.
r = note(db, tmp, f"Записка {FILE} лежит час, разобрать её некому — жалуюсь на это.")
check("② упоминание имени НЕ гасит", reviewed(db) is None,
      f"нота записана: {'OK' in r.stdout}")

# ③ ВСТРЕЧНЫЙ: жест на ДРУГОЙ файл не гасит наш
note(db, tmp, "разобрал соседнюю", "--reviewed", "answer.some-other-file.md")
check("③ жест на другой файл НЕ гасит", reviewed(db) is None)

# ④ КОНТРОЛЬНАЯ ПАРА: жест на НАШ файл — гасит. Без этого случая три «нет» выше
#    доказывали бы лишь то, что запрос всегда возвращает пустоту.
r = note(db, tmp, "прочёл и разобрал по существу", "--reviewed", FILE)
got = reviewed(db)
check("④ КОНТРОЛЬ: жест гасит", got is not None, f"at={got}")
check("④ и след назван: кто и какой нотой", "разбор записан" in r.stdout, r.stdout.strip()[:60])

# ⑤ ВСТРЕЧНЫЙ: жест без ноты — ОТКАЗ, а не тихое гашение
p = tmp / "empty.md"
r = subprocess.run([PY, str(HERE / "write-message.py"), "--db", str(db), "--role", "COORD",
                    "--poll", "жив", "--reviewed", "answer.no-note.md"],
                   capture_output=True, text=True)
check("⑤ жест без ноты отвергнут громко", r.returncode != 0 and reviewed(db, "answer.no-note.md") is None,
      (r.stderr or r.stdout).strip()[:70])

# ⑥ СЛЕД ЧИТАЕМ ЦЕЛИКОМ: строка знает роль и номер ноты
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
row = c.execute("SELECT role, note_id FROM bridge_reviewed WHERE file_name=?", (FILE,)).fetchone()
c.close()
check("⑥ след несёт роль и ноту", bool(row and row[0] == "COORD" and row[1]), f"{row}")

mezo_stand.release(tmp)  # уборка отложена до исхода прогона
print("\n" + ("✅ ПРИЁМКА ЗЕЛЁНАЯ" if ok else "🔴 ПРИЁМКА КРАСНАЯ"))
sys.exit(mezo_stand.finish(0 if ok else 1))
