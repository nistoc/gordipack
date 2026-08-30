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

ИСПЫТУЕМЫЙ = mezo_target.script("write-message.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0
РОЛЬ = "ZZD"


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
                MEZO_CONTAINER=str(mezo_paths.container_root()))


def отправить(db, тело_файл, память_файл, сухой):
    cmd = [sys.executable, str(ИСПЫТУЕМЫЙ), "--db", str(db), "--role", РОЛЬ,
           "--file", str(тело_файл), "--save-state", str(память_файл)]
    if сухой:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def замер(db):
    """Состояние ОБОИХ предметов: память и лента. Судим по базе, не по выводу."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    длина = con.execute("SELECT LENGTH(body) FROM phoenix WHERE role=? AND section='state'",
                        (РОЛЬ,)).fetchone()
    редакций = con.execute("SELECT COUNT(*) FROM phoenix_history WHERE role=? "
                           "AND section='state'", (РОЛЬ,)).fetchone()[0]
    записок = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    con.close()
    return (длина[0] if длина else None), редакций, записок


stand = mezo_stand.new("dryrun-boundary-")
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба границы')", (РОЛЬ,))
con.execute("INSERT INTO phoenix (role, section, body, saved_at) VALUES (?,'state',?,"
            "datetime('now'))", (РОЛЬ, "ИСХОДНОЕ ТЕЛО ПАМЯТИ.\n" + ("строка-набивка\n" * 60)))
con.commit()
con.close()

тело = stand / "nota.md"
тело.write_text("# проба границы холостого хода\n\nтело записки для опыта.\n", encoding="utf-8")
новая_память = stand / "state-new.md"
новая_память.write_text("НОВОЕ ТЕЛО ПАМЯТИ — заметно другой длины.\n"
                        + ("иная строка\n" * 90), encoding="utf-8")

до = замер(db)
print(f"⚖️ ДО опытов: длина памяти {до[0]} · редакций {до[1]} · записок {до[2]}")

# ═══ ①②③ ХОЛОСТОЙ ПРОГОН
rc, out = отправить(db, тело, новая_память, сухой=True)
после_сухого = замер(db)
case("① холостой: длина раздела памяти и число редакций НЕ изменились",
     после_сухого[0] == до[0] and после_сухого[1] == до[1],
     f"длина {до[0]} → {после_сухого[0]} · редакций {до[1]} → {после_сухого[1]}")
case("② холостой: записка в ленту НЕ ушла",
     после_сухого[2] == до[2], f"записок {до[2]} → {после_сухого[2]}")
case("③ холостой ГОВОРИТ СЛОВОМ, что память не сохранена (молчание неотличимо от записи)",
     "НЕ сохранена: холостой прогон" in out and "случилось БЫ" in out)
case("⑦ польза холостого прогона цела: отчёт о том, что изменилось бы, напечатан",
     re.search(r"было \d+ → стало \d+|ИСЧЕЗА", out) is not None)

# ═══ ④⑤ ВСТРЕЧНЫЙ ①: боевой прогон обязан ПИСАТЬ
rc2, out2 = отправить(db, тело, новая_память, сухой=False)
после_боевого = замер(db)
case("④ ВСТРЕЧНЫЙ: БОЕВОЙ прогон память ПИШЕТ (починка не убила пользу)",
     rc2 == 0 and после_боевого[0] != до[0],
     f"длина {после_сухого[0]} → {после_боевого[0]} · редакций "
     f"{после_сухого[1]} → {после_боевого[1]}")
case("⑤ ВСТРЕЧНЫЙ: боевой прогон записку в ленту ПИШЕТ",
     после_боевого[2] == до[2] + 1, f"записок {после_сухого[2]} → {после_боевого[2]}")

# ═══ ⑥ ВСТРЕЧНЫЙ ② (@TAXO): отдельный вызов инструмента памяти в холостом ходе НЕ пишет
до6 = замер(db)
ещё = stand / "state-third.md"
ещё.write_text("ТРЕТЬЕ ТЕЛО.\n" + ("третья строка\n" * 30), encoding="utf-8")
p6 = subprocess.run([sys.executable, str(SCRIPTS / "save-phoenix.py"), "--db", str(db),
                     "--role", РОЛЬ, "--section", "state", "--file", str(ещё),
                     "--allow-shrink", "--dry-run"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=env())
после6 = замер(db)
case("⑥ ВСТРЕЧНЫЙ @TAXO: save-phoenix --dry-run по-прежнему НЕ пишет "
     "(починка одного пути не увела исправный второй)",
     после6[0] == до6[0] and после6[1] == до6[1],
     f"длина {до6[0]} → {после6[0]} · редакций {до6[1]} → {после6[1]}")

# ═══ ⑧ контроль: живая база не тронута
живой = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы = живой.execute("SELECT COUNT(*) FROM roles WHERE role=?", (РОЛЬ,)).fetchone()[0]
следы += живой.execute("SELECT COUNT(*) FROM phoenix WHERE role=?", (РОЛЬ,)).fetchone()[0]
живой.close()
case("⑧ контроль: своих следов в живой базе нет", следы == 0, f"следов: {следы}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
