# -*- coding: utf-8 -*-
r"""
bite-dryrun-tool-boundary.py — приёмка карточки #473 (заявитель @ING, встречный ② от @TAXO):
холостой ход НЕ ПЕРЕХОДИТ ЧЕРЕЗ ГРАНИЦУ ИНСТРУМЕНТА. Отправка записки с сохранением
памяти запускает save-phoenix ОТДЕЛЬНЫМ ПРОЦЕССОМ, и тот открывает своё соединение:
`--dry-run` откатывал записку и писал память НАСОВСЕМ, печатая «НИЧЕГО НЕ ЗАПИСАНО».

Всё на КОПИИ базы (mezo_stand); живая база только читается.

Случаи:
  ① холостой прогон: длина раздела памяти и число редакций НЕ меняются
  ② холостой прогон: записка в ленту НЕ уходит (прежнее поведение цело)
  ③ холостой прогон ГОВОРИТ СЛОВОМ, что память не сохранена — молчание тут неотличимо
     от «сохранено»; и роль читала отчёт дочернего как предсказание, а он был фактом
  ④ ВСТРЕЧНЫЙ ① (обязателен по критерию): БОЕВОЙ прогон память ПИШЕТ. Починка, которая
     перестала писать и в боевом, критерий НЕ проходит — она чинит вред уничтожением пользы
  ⑤ ВСТРЕЧНЫЙ ①-бис: боевой прогон записку в ленту пишет
  ⑥ ВСТРЕЧНЫЙ ② (@TAXO, записка #4440): save-phoenix.py --dry-run обязан ПО-ПРЕЖНЕМУ
     не писать. Починка одного пути не должна увести за собой исправный второй
  ⑦ польза холостого прогона СОХРАНЕНА: отчёт об исчезающих блоках печатается и в нём
  ⑧ контроль: своих следов в ЖИВОЙ базе нет
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

SUBJECT = mezo_target.script("write-message.py")
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
ROLE = "ZZD"


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
                MEZO_CONTAINER=str(mezo_paths.container_root()))


def send(db, body_file, memory_file, dry):
    cmd = [sys.executable, str(SUBJECT), "--db", str(db), "--role", ROLE,
           "--file", str(body_file), "--save-state", str(memory_file)]
    if dry:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def measure(db):
    """Состояние ОБОИХ предметов: память и лента. Судим по базе, не по выводу."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    length = con.execute("SELECT LENGTH(body) FROM phoenix WHERE role=? AND section='state'",
                        (ROLE,)).fetchone()
    revisions_count = con.execute("SELECT COUNT(*) FROM phoenix_history WHERE role=? "
                           "AND section='state'", (ROLE,)).fetchone()[0]
    notes_count = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    con.close()
    return (length[0] if length else None), revisions_count, notes_count


stand = mezo_stand.new("dryrun-boundary-")
db = stand / "mezosync.db"
mezo_stand.empty_db(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба границы')", (ROLE,))
con.execute("INSERT INTO phoenix (role, section, body, saved_at) VALUES (?,'state',?,"
            "datetime('now'))", (ROLE, "ИСХОДНОЕ ТЕЛО ПАМЯТИ.\n" + ("строка-набивка\n" * 60)))
con.commit()
con.close()

body = stand / "nota.md"
body.write_text("# проба границы холостого хода\n\nтело записки для опыта.\n", encoding="utf-8")
new_memory = stand / "state-new.md"
new_memory.write_text("НОВОЕ ТЕЛО ПАМЯТИ — заметно другой длины.\n"
                        + ("иная строка\n" * 90), encoding="utf-8")

before = measure(db)
print(f"⚖️ ДО опытов: длина памяти {before[0]} · редакций {before[1]} · записок {before[2]}")

# ═══ ①②③ ХОЛОСТОЙ ПРОГОН
rc, out = send(db, body, new_memory, dry=True)
after_dry = measure(db)
case("① холостой: длина раздела памяти и число редакций НЕ изменились",
     after_dry[0] == before[0] and after_dry[1] == before[1],
     f"длина {before[0]} → {after_dry[0]} · редакций {before[1]} → {after_dry[1]}")
case("② холостой: записка в ленту НЕ ушла",
     after_dry[2] == before[2], f"записок {before[2]} → {after_dry[2]}")
case("③ холостой ГОВОРИТ СЛОВОМ, что память не сохранена (молчание неотличимо от записи)",
     "НЕ сохранена: холостой прогон" in out and "случилось БЫ" in out)
case("⑦ польза холостого прогона цела: отчёт о том, что изменилось бы, напечатан",
     re.search(r"было \d+ → стало \d+|ИСЧЕЗА", out) is not None)

# ═══ ④⑤ ВСТРЕЧНЫЙ ①: боевой прогон обязан ПИСАТЬ
rc2, out2 = send(db, body, new_memory, dry=False)
after_real = measure(db)
case("④ ВСТРЕЧНЫЙ: БОЕВОЙ прогон память ПИШЕТ (починка не убила пользу)",
     rc2 == 0 and after_real[0] != before[0],
     f"длина {after_dry[0]} → {after_real[0]} · редакций "
     f"{after_dry[1]} → {after_real[1]}")
case("⑤ ВСТРЕЧНЫЙ: боевой прогон записку в ленту ПИШЕТ",
     after_real[2] == before[2] + 1, f"записок {after_dry[2]} → {after_real[2]}")

# ═══ ⑥ ВСТРЕЧНЫЙ ② (@TAXO): отдельный вызов инструмента памяти в холостом ходе НЕ пишет
before6 = measure(db)
more = stand / "state-third.md"
more.write_text("ТРЕТЬЕ ТЕЛО.\n" + ("третья строка\n" * 30), encoding="utf-8")
p6 = subprocess.run([sys.executable, str(SCRIPTS / "save-phoenix.py"), "--db", str(db),
                     "--role", ROLE, "--section", "state", "--file", str(more),
                     "--allow-shrink", "--dry-run"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=env())
after6 = measure(db)
case("⑥ ВСТРЕЧНЫЙ @TAXO: save-phoenix --dry-run по-прежнему НЕ пишет "
     "(починка одного пути не увела исправный второй)",
     after6[0] == before6[0] and after6[1] == before6[1],
     f"длина {before6[0]} → {after6[0]} · редакций {before6[1]} → {after6[1]}")

# ═══ ⑧ контроль: живая база не тронута
live = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
traces_found = live.execute("SELECT COUNT(*) FROM roles WHERE role=?", (ROLE,)).fetchone()[0]
traces_found += live.execute("SELECT COUNT(*) FROM phoenix WHERE role=?", (ROLE,)).fetchone()[0]
live.close()
case("⑧ контроль: своих следов в живой базе нет", traces_found == 0, f"следов: {traces_found}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
