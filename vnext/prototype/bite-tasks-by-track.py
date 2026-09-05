# -*- coding: utf-8 -*-
r"""
bite-tasks-by-track.py — приёмка карточки #491 (половина ДАННЫХ полигона): служба показа
задач умеет отбор по набору, выдачу тела задачи по номеру и группировку по наборам.

Служба поднимается на КОПИИ живой базы (mezo_stand), на свободном порту, только чтение.
Стендов ДВА, и это не роскошь: подсадка «набор с именем none» и встречный случай
«отбор без набора работает» судят ОДИН И ТОТ ЖЕ ответ и в одной базе несовместимы —
на общем стенде один из них всегда врал бы.

Случаи (стенд A — копия живой базы как есть):
  ⓪ служба поднялась и говорит о себе: /api/health отвечает, замок «только чтение» ЗАМЕРЕН
  ① /api/tracks: заявленные наборы на месте, число задач у каждого сходится с прямым запросом
  ② ВСТРЕЧНЫЙ: набор, которого НЕТ в таблице наборов, показан отдельно (declared=false),
     а не потерян и не свален в «без набора»
  ③ ВСТРЕЧНЫЙ: заявленный, но ПУСТОЙ набор показан числом 0 — «набор есть и пуст» это факт,
     его отсутствие читалось бы как «набора нет»
  ④ отбор /api/tasks?track=<имя>: отданы ВСЕ и ТОЛЬКО задачи набора
  ⑤ ВСТРЕЧНЫЙ: /api/tasks?track=none — задачи БЕЗ набора, число сошлось с прямым запросом,
     и ни у одной из них набора нет
  ⑥ отбор совмещается с прежними: track + status даёт пересечение, а не подмену
  ⑦ поиск по номеру /api/tasks/{id}: отдано ТЕЛО задачи, номер тот самый
  ⑧ ВСТРЕЧНЫЙ: несуществующий номер → 404, а не пустой объект (пустое читалось бы как
     «задача есть и пуста»)
  ⑨ группировка /api/tasks/grouped: сумма по группам равна числу задач — ничего не потеряно
  ⑩ ВСТРЕЧНЫЙ (главный по критерию карточки): задачи без набора отданы ОТДЕЛЬНОЙ группой,
     она последняя, и её число равно замеру
  ⑪ отбор по несуществующему набору отдаёт ПУСТОЙ список с кодом 200 — «таких задач нет»
     это ответ, а не ошибка

Случай стенда B (в базу подсажен набор с именем «none»):
  ⑫ ВСТРЕЧНЫЙ-ПОДСАДКА: служебное слово отбора занято настоящим набором ⇒ отбор отвечает
     ОТКАЗОМ со словом, а не молча отдаёт не то. Ответ по подсадке обязан быть «НЕТ»

  ⑬ контроль: служба ничего не писала — стенд, который она открывала, не изменился
     (первая редакция судила ЖИВУЮ базу и краснела от честной работы коллег — карточка #483)

Запуск:
    python <КОНТУР>/vnext-tools/bite-tasks-by-track.py
"""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

# Путь к службе. Умолчание — РЕЗОЛВОМ от корня образца, а не строкой одной машины:
# у чужого человека вписанный путь мёртв, и он решит, что сломан механизм (гард машинных
# путей поймал это 2026-08-30 22:52 UTC у меня же, на первом заходе).
# Переменной среды PERISCOPE_PROJECT приёмку целят в ИСПОРЧЕННУЮ КОПИЮ проекта —
# так доказывается, что она краснеет на поломке, а живой проект при этом не трогается.
PROJECT = Path(os.environ.get("PERISCOPE_PROJECT")
               or mezo_paths.template_root() / "src" / "Gordi.Periscope.Api")

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("[ok]  " if cond else "[FAIL]"), name)
    if detail:
        print(f"       {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get(port, path):
    """Вернуть (код, тело). Отказ службы — тоже ответ, а не исключение: случай о нём и судит.

    ⚠️ Путь кодируется ЗДЕСЬ: первый прогон 2026-08-30 22:47 UTC покраснел на случае ⑪
    не по своей причине — имя набора кириллицей не проходило через urllib, и приёмка
    судила СВОЙ отказ, приняв его за отказ службы. Шестой случай этого класса в контуре.
    """
    url = f"http://127.0.0.1:{port}/api{urllib.parse.quote(path, safe='/?=&')}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # noqa: BLE001 — служба не поднялась: скажем словом, не следом стека
        return 0, str(e)


def serve(db_path):
    """Поднять службу на копии базы. Возвращает (процесс, порт, готова ли, тело health)."""
    port = free_port()
    env = dict(os.environ, ASPNETCORE_ENVIRONMENT="Development")
    proc = subprocess.Popen(
        ["dotnet", "run", "--no-build", "--project", str(PROJECT), "--",
         "--db", str(db_path), "--port", str(port), "--refresh", "3"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", env=env)
    body = None
    for _ in range(60):
        code, body = get(port, "/health")
        if code == 200 and isinstance(body, dict) and body.get("status") == "ok":
            return proc, port, True, body
        time.sleep(1)
    return proc, port, False, body


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── стенд A: копия живой базы как есть ───────────────────────────────────────
stand_a = mezo_stand.new("tasks-by-track-a-")
db_a = stand_a / "mezosync.db"
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
shutil.copy(LIVE_DB, db_a)
stand_before = (db_a.stat().st_size, db_a.stat().st_mtime_ns)

con = sqlite3.connect(str(db_a))


def q1(sql, *args):
    return con.execute(sql, args).fetchone()[0]


TOTAL = q1("SELECT COUNT(*) FROM backlog")
UNTRACKED = q1("SELECT COUNT(*) FROM backlog WHERE parent_track IS NULL OR TRIM(parent_track)=''")
BY_TRACK = dict(con.execute(
    "SELECT parent_track, COUNT(*) FROM backlog WHERE parent_track IS NOT NULL "
    "AND TRIM(parent_track)!='' GROUP BY parent_track").fetchall())
DECLARED = dict(con.execute("SELECT track_id, status FROM tracks").fetchall())
BIG_TRACK = max(BY_TRACK, key=lambda t: BY_TRACK[t])
ORPHAN = next((t for t in BY_TRACK if t not in DECLARED), None)
EMPTY_DECLARED = next((t for t in DECLARED if t not in BY_TRACK), None)
SOME_ID = q1("SELECT id FROM backlog WHERE body_md IS NOT NULL AND TRIM(body_md)!='' ORDER BY id DESC LIMIT 1")
MISSING_ID = q1("SELECT MAX(id) FROM backlog") + 10_000
OPEN_IN_BIG = q1("SELECT COUNT(*) FROM backlog WHERE parent_track=? AND status='open'", BIG_TRACK)
con.close()

print(f"замеры по стенду A: задач {TOTAL} · без набора {UNTRACKED} · наборов в таблице {len(DECLARED)} · "
      f"крупнейший {BIG_TRACK} ({BY_TRACK[BIG_TRACK]}) · сирота {ORPHAN} · пустой заявленный {EMPTY_DECLARED}")

# ── сборка ───────────────────────────────────────────────────────────────────
build = subprocess.run(["dotnet", "build", "-v", "q", "--nologo"], cwd=str(PROJECT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
if build.returncode != 0:
    print("[FAIL] сборка службы не прошла — приёмка НЕ ЗАПУСТИЛАСЬ (третий исход, не зелёный)")
    print((build.stdout or "")[-2000:])
    sys.exit(2)

proc, port, ready, health = serve(db_a)
try:
    case("(0) служба поднялась на копии базы и ЗАМЕРИЛА свой замок «только чтение»",
         ready and isinstance(health, dict) and health.get("readOnly") is True,
         f"порт {port} · статус {health.get('status') if isinstance(health, dict) else health}")
    if not ready:
        print("[FAIL] дальше судить нечего: службы нет. Это НЕ «зелёный» и НЕ «сломано» — она не запустилась")
        raise SystemExit(2)

    code, tracks = get(port, "/tracks")
    items = {t["trackId"]: t for t in tracks.get("items", [])} if code == 200 else {}
    declared_ok = all(name in items and items[name]["declared"] for name in DECLARED)
    counts_ok = all(items[name]["taskCount"] == BY_TRACK.get(name, 0) for name in DECLARED if name in items)
    case("(1) сводка по наборам: все заявленные на месте, число задач сошлось с прямым запросом",
         code == 200 and declared_ok and counts_ok,
         f"наборов в ответе {len(items)} · заявленных в базе {len(DECLARED)} · без набора {tracks.get('untracked')}")

    orphan_row = items.get(ORPHAN) if ORPHAN else None
    case("(2) ВСТРЕЧНЫЙ: набор, которого нет в таблице наборов, показан отдельно и не потерян",
         ORPHAN is not None and orphan_row is not None
         and orphan_row["declared"] is False and orphan_row["taskCount"] == BY_TRACK[ORPHAN],
         f"{ORPHAN}: в ответе {orphan_row['taskCount'] if orphan_row else '—'} из {BY_TRACK.get(ORPHAN)}")

    empty_row = items.get(EMPTY_DECLARED) if EMPTY_DECLARED else None
    case("(3) ВСТРЕЧНЫЙ: заявленный пустой набор показан числом 0, а не пропущен",
         EMPTY_DECLARED is not None and empty_row is not None
         and empty_row["declared"] is True and empty_row["taskCount"] == 0,
         f"{EMPTY_DECLARED}: {empty_row['taskCount'] if empty_row else '—'}")

    code, sel = get(port, f"/tasks?track={BIG_TRACK}")
    only_this = code == 200 and all((t.get("parentTrack") or "").upper() == BIG_TRACK.upper() for t in sel)
    case("(4) отбор по набору: отданы ВСЕ и ТОЛЬКО задачи набора",
         code == 200 and len(sel) == BY_TRACK[BIG_TRACK] and only_this,
         f"{BIG_TRACK}: отдано {len(sel) if code == 200 else code}, в базе {BY_TRACK[BIG_TRACK]}")

    code, none_sel = get(port, "/tasks?track=none")
    case("(5) ВСТРЕЧНЫЙ: отбор «без набора» отдал ровно те задачи, и ни у одной набора нет",
         code == 200 and len(none_sel) == UNTRACKED
         and all(not (t.get("parentTrack") or "").strip() for t in none_sel),
         f"track=none: отдано {len(none_sel) if code == 200 else code}, в базе {UNTRACKED}")

    code, both = get(port, f"/tasks?track={BIG_TRACK}&status=open")
    case("(6) отбор по набору совмещается с отбором по статусу — пересечение, а не подмена",
         code == 200 and len(both) == OPEN_IN_BIG,
         f"{BIG_TRACK} + status=open: отдано {len(both) if code == 200 else code}, в базе {OPEN_IN_BIG}")

    code, detail = get(port, f"/tasks/{SOME_ID}")
    body_md = detail.get("bodyMd") if code == 200 else None
    case("(7) поиск по номеру: отдано тело задачи, и номер тот самый",
         code == 200 and detail["task"]["id"] == SOME_ID and bool(body_md and body_md.strip()),
         f"задача {SOME_ID}: тело {len(body_md or '')} знаков")

    code, _ = get(port, f"/tasks/{MISSING_ID}")
    case("(8) ВСТРЕЧНЫЙ: несуществующий номер даёт отказ 404, а не пустую задачу",
         code == 404, f"номер {MISSING_ID} → код {code}")

    code, grouped = get(port, "/tasks/grouped")
    groups = grouped.get("groups", []) if code == 200 else []
    summed = sum(g["count"] for g in groups)
    case("(9) группировка: сумма по группам равна числу задач — ничего не потеряно",
         code == 200 and summed == TOTAL == grouped.get("totalTasks"),
         f"сумма по группам {summed} · задач в базе {TOTAL} · служба говорит {grouped.get('totalTasks')}")

    tail = groups[-1] if groups else {}
    case("(10) ВСТРЕЧНЫЙ по критерию карточки: задачи без набора не пропали — отдельная группа, последняя",
         bool(groups) and tail.get("trackId") is None and tail.get("count") == UNTRACKED
         and grouped.get("ungrouped") == UNTRACKED,
         f"группа «без набора»: {tail.get('count')} · замер по базе {UNTRACKED}")

    code, nobody = get(port, "/tasks?track=TRACK-ЕГО-НЕТ-В-ПРИРОДЕ")
    case("(11) отбор по несуществующему набору: пустой список с кодом 200 — «таких нет» это ответ",
         code == 200 and nobody == [], f"код {code}, отдано {len(nobody) if isinstance(nobody, list) else nobody}")
finally:
    stop(proc)

# ── стенд B: подсадка «набор с именем none» ──────────────────────────────────
stand_b = mezo_stand.new("tasks-by-track-b-")
db_b = stand_b / "mezosync.db"
shutil.copy(LIVE_DB, db_b)
con = sqlite3.connect(str(db_b))
con.execute(
    "INSERT INTO backlog (role, title, status, priority, parent_track, created_by, created_at, updated_at) "
    "VALUES ('PROTO', 'подсадка приёмки: набор с именем none', 'open', 'low', 'none', 'PROTO', "
    "'2026-08-30 22:00:00', '2026-08-30 22:00:00')")
con.commit()
con.close()

proc, port, ready, health = serve(db_b)
try:
    if not ready:
        case("(12) ВСТРЕЧНЫЙ-ПОДСАДКА: служба на стенде B не поднялась", False,
             "судить подсадку нечем — это третий исход")
    else:
        code, answer = get(port, "/tasks?track=none")
        said = isinstance(answer, dict) and "error" in answer and "none" in str(answer.get("error"))
        case("(12) ВСТРЕЧНЫЙ-ПОДСАДКА: имя набора занимает служебное слово ⇒ отбор ОТКАЗЫВАЕТ со словом",
             code == 400 and said,
             f"ответ {code} · {str(answer)[:160]}")
finally:
    stop(proc)

# ⑬ контроль «служба ничего не писала».
# 🩸 ПЕРВАЯ РЕДАКЦИЯ ЭТОГО СЛУЧАЯ СУДИЛА ЖИВУЮ БАЗУ — и покраснела 2026-08-30 22:49 UTC
#    на прогоне с поломкой D: пока шёл прогон, в живую базу законно писали коллеги.
#    Это ровно карточка #483: признак красит ЧУЖАЯ ЧЕСТНАЯ РАБОТА, а не наша порча.
#    Судить надо то, что служба ОТКРЫВАЛА, — стенд; про живую базу печатается замечание.
stand_after = (db_a.stat().st_size, db_a.stat().st_mtime_ns)
case("(13) контроль: служба ничего не писала — стенд, который она открывала, не изменился",
     stand_before == stand_after,
     "сверены размер и время правки КОПИИ (живую базу служба не открывала: ей передан путь стенда)")

live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
if live_before != live_after:
    print("       ⚖️ замечание, не случай: живая база за время прогона изменилась — "
          "это работа коллег, служба её не открывала")

print(f"\nитог: {OK} из {OK + FAIL}")
sys.exit(0 if FAIL == 0 else 1)
