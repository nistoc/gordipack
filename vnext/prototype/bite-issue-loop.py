# -*- coding: utf-8 -*-
r"""
bite-issue-loop.py — приёмка П⑤ пула: канал проблем процесса → issues образца.
БЕЗ СЕТИ: create судится в --dry-run (ворота до команды), poll — на --fixture
(подсунутый ответ). Живая база только читается; карточки — в копии (mezo_stand).

Случаи:
  ① create с тремя непустыми разделами → ворота пройдены, команда gh собрана (dry-run)
  ② пустой раздел → отказ ПОИМЁННО (какой раздел)
  ③ путь этой машины в теле → отказ «обезличь»
  ④ писатель не COORD → отказ (канал публичный, писатель один)
  ⑤ poll (fixture): process-issue СТАРШЕ 7 суток без карточки → 🟡 и готовая команда
  ⑥ встречный: у issue ЕСТЬ карточка с тегом → 🟡 нет, карточка названа
  ⑦ встречный-2: закрытая владельцем пака issue в fixture не приходит → не судится
     (fixture отдаёт только open — граница названа в инструменте)
  ⑧ закрытие карточки с тегом «gordi-issue #N» → напоминание «закрой и issue»
  ⑨ ОБРАТНЫЙ ХОД: ворота разделов сняты в копии → ② проходит молча (краснеет)
  ⑩ close без слов → отказ; ⑪ живая база не тронута
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402 — испытуемое (gordi-issue.py) берём через MEZO_SCRIPTS_ROOT,
                    # как остальные приёмки набора; live_scripts/live_db остаются для СОСЕДЕЙ
                    # (backlog.py) и снимка базы, а не для самого испытуемого механизма.

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
CONTAINER_ROOT = mezo_paths.container_root()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def run(script, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


stand = mezo_stand.new("issue-loop-")
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
# было: GI = SCRIPTS / "gordi-issue.py" — рядом со «своим» live_scripts(), не через
# MEZO_SCRIPTS_ROOT (карточка #659): образец прочих приёмок набора берёт ИСПЫТУЕМОЕ
# через mezo_target.script(), оставляя live_scripts()/live_db() соседям и снимку базы.
GI = mezo_target.script("gordi-issue.py")

good = stand / "good.md"
good.write_text("## ЗАМЕР\nотказ дословно: «нет пути»\n## КЛАСС\nмолчащий отказ\n"
                "## ПРЕДЛОЖЕНИЕ\nпечатать причину; цена — час\n", encoding="utf-8")

# ① разделы полны (dry-run, сеть не зовётся)
rc, out = run(GI, "create", "--role", "COORD", "--title", "проба",
              "--body-file", str(good), "--pool", "TRACK-X", "--dry-run")
case("① три раздела непусты → отказа нет, команда gh собрана",
     rc == 0 and "gh issue create" in out and "pool-TRACK-X" in out)

# ② пустой раздел — поимённо
bad = stand / "bad.md"
bad.write_text("## ЗАМЕР\nчто-то\n## КЛАСС\n\n## ПРЕДЛОЖЕНИЕ\nчто-то\n", encoding="utf-8")
rc, out2 = run(GI, "create", "--role", "COORD", "--title", "проба",
               "--body-file", str(bad), "--dry-run")
case("② пустой раздел → отказ ПОИМЁННО", rc != 0 and "КЛАСС" in out2 and "ЗАМЕР" not in
     out2.split("пустые разделы:")[-1].split(".")[0])

# ③ машинный путь — отказ
dirty = stand / "dirty.md"
dirty.write_text("## ЗАМЕР\nупал на C:\\guts\\.atlas\\vnext-tools\\x.py\n## КЛАСС\nкл\n"
                 "## ПРЕДЛОЖЕНИЕ\nпр\n", encoding="utf-8")
rc, out3 = run(GI, "create", "--role", "COORD", "--title", "проба",
               "--body-file", str(dirty), "--dry-run")
case("③ путь этой машины в теле → отказ «обезличь»", rc != 0 and "обезличь" in out3)

# ④ писатель не COORD
rc, out4 = run(GI, "create", "--role", "PROTO", "--title", "проба",
               "--body-file", str(good), "--dry-run")
case("④ писатель не координатор → отказ (канал публичный, писатель один)",
     rc != 0 and "ОДИН" in out4)

# ⑤⑥ poll на фикстуре + копии базы
db = stand / "mezosync.db"
mezo_stand.snapshot_db(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, "
            "done_when) VALUES ('PROTO','починка по заявке','тело','open','normal',"
            "'[\"gordi-issue #77\"]','PROTO','критерий')")
con.commit()
con.close()
# ГРУППА F, карточка #659: было — АБСОЛЮТНЫЕ календарные даты («2026-08-10», «2026-08-27»).
# Возраст issue считается ОТ ТЕКУЩЕГО часа (julianday('now') в cmd_poll), поэтому абсолютная
# дата молча стареет вместе с настоящим временем: «свежая заявка» от 27.08 была моложе 7 суток
# только НЕДЕЛЮ-ДРУГУЮ после написания приёмки, а месяц спустя (замерено `date -u`: 2026-09-26)
# сама стала «старше 7 суток» — случаи ⑤ (счёт «без карточки >7 суток: 1» стал 2) и ⑥-встречный-2
# («в пределах 7 суток») ломались НЕ ОТ ПОРЧИ инструмента, а от даты в самой приёмке.
# ⇒ времена ОТНОСИТЕЛЬНЫЕ (сейчас − N дней), не выдуманы — свойство «старше/младше 7 суток»
# остаётся верным в любой день прогона.
_now = datetime.now(timezone.utc)


def _iso(days_ago: float) -> str:
    return (_now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


fixture = stand / "issues.json"
fixture.write_text(json.dumps([
    {"number": 55, "title": "заявка без карточки", "createdAt": _iso(10),
     "comments": [], "labels": [{"name": "process"}]},
    {"number": 77, "title": "заявка с карточкой", "createdAt": _iso(10),
     "comments": [], "labels": [{"name": "process"}]},
    {"number": 90, "title": "свежая заявка", "createdAt": _iso(2),
     "comments": [], "labels": [{"name": "process"}]},
], ensure_ascii=False), encoding="utf-8")
rc, out5 = run(GI, "poll", "--role", "COORD", "--db", str(db), "--fixture", str(fixture))
case("⑤ issue >7 суток без карточки → 🟡 и готовая команда заведения",
     rc == 0 and "🟡" in out5 and "#55" in out5 and "backlog.py" in out5
     and "без карточки >7 суток: 1" in out5)
case("⑥ встречный: issue #77 с карточкой → без 🟡, карточка названа",
     "«заявка с карточкой»" in out5 and "карточка #" in out5)
case("⑥ встречный-2: свежая issue #90 → без 🟡 (в пределах 7 суток)",
     "в пределах 7 суток" in out5)
# ⑦ закрытая не в фикстуре — инструмент судит только присланное open (граница)
case("⑦ fixture без закрытых → закрытое чужой рукой не судится (граница названа)",
     "#91" not in out5)

# ⑧ закрытие карточки с тегом → напоминание
con = sqlite3.connect(str(db))
bid = con.execute("SELECT id FROM backlog WHERE tags LIKE '%gordi-issue #77%'").fetchone()[0]
con.close()
rc, out8 = run(SCRIPTS / "backlog.py", "--db", str(db), "status", str(bid), "done",
               "--actor", "PROTO", "--note", "сделано")
case("⑧ done карточки с тегом → напоминание «закрой и issue»",
     rc == 0 and "gordi-issue #77" in out8 and "close" in out8)

# ⑨ обратный ход: ворота разделов сняты
weak = stand / "weak"
weak.mkdir()
shutil.copy(GI, weak / "gordi-issue.py")
shutil.copy(SCRIPTS / "mezo_paths.py", weak / "mezo_paths.py")
# ГРУППА F, карточка #659: копия лежит ОТДЕЛЬНО (stand — системный temp, не внутри контура),
# и mezo_paths копии искал бы контейнер подъёмом от weak/ — не нашёл бы НИКОГДА и упал бы
# отказом «контейнер группы не найден» ДО того, как дошёл бы до _writer_gate/секций (доказано
# прогоном: без этой строки ⑨ падал именно так). Второй замок — тот же приём, что и у
# рабочего контура: local.paths РЯДОМ с копией, а не переменная среды (её здесь неоткуда взять).
(weak / "local.paths").write_text(f"container={CONTAINER_ROOT}\n", encoding="utf-8")
src = (weak / "gordi-issue.py").read_text(encoding="utf-8")
ANCHOR = "if missing:"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь проверки разделов не найден")
(weak / "gordi-issue.py").write_text(src.replace(ANCHOR, "if False:"), encoding="utf-8")
rc, out9 = run(weak / "gordi-issue.py", "create", "--role", "COORD", "--title", "проба",
               "--body-file", str(bad), "--dry-run")
case("⑨ обратный ход: проверка разделов снята → пустой раздел проходит (② краснеет)",
     rc == 0 and "разделы полны" in out9)

# ⑩ close без слов
rc, outA = run(GI, "close", "--role", "COORD", "--number", "55", "--dry-run")
case("⑩ close без слов → отказ", rc != 0 and "БЕЗ слов" in outA)

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑪ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
