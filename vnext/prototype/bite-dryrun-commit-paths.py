# -*- coding: utf-8 -*-
"""bite-dryrun-commit-paths.py — приёмка правки dryrun.py (слово владельца 2026-09-25
21:36 UTC; объявление о правке #366 у PROTO): холостой режим закрывает КЛАСС путей
фиксации, а не пересчитанные сегодня точки.

ЗАЧЕМ. Проба PROTO на копии базы нашла: холостой режим (--dry-run у пишущих
инструментов, модуль <КОНТУР>/.mezosync/scripts/dryrun.py) подменял ТОЛЬКО метод
commit() класса _DryConnection. Мимо этого метода фиксация уходит в живой файл
несколькими путями: `with conn:` (выход из блока фиксирует на уровне C — Connection.
__exit__ — Python-метод commit() не зовёт), `conn.executescript(...)` (библиотека сама
фиксирует происходящее внутри, идя мимо переопределённого метода), `conn.execute(
"COMMIT")` (прямой SQL, тоже мимо метода) и соединение в режиме автофиксации
(isolation_level=None — каждый execute() фиксируется сам). Проба показала это числом:
0 → 2 → 3 строки. Правка меняет МЕХАНИЗМ: при dry=True источник открывается только на
чтение и копируется в базу в памяти (Connection.backup()); инструмент работает с
копией, и фиксировать в ней можно чем угодно — живому файлу это уже не мешает никак.

Случаи (своя маленькая база на стенде — НЕ живая, без опоры на живые роли, поэтому
приёмка идёт и в контуре, собранном из пакета; проба — отдельный процесс, который
импортирует КОПИЮ dryrun.py со стенда через mezo_stand.copy_tool):
  ①  commit() — было защищено ДО этой правки; холостой прогон базу не меняет
  ②  with conn: — Connection.__exit__ фиксирует на уровне C
  ③  conn.executescript(...) — библиотека сама фиксирует, идя мимо метода
  ④  conn.execute("COMMIT") — прямой SQL мимо метода
  ⑤  isolation_level=None — автофиксация, метод commit() не зовётся вовсе
  ⑥  путь, по которому файла нет, — холостой прогон файл НЕ СОЗДАЁТ (обычный
     sqlite3.connect создал бы его молча уже в момент открытия соединения)
  ⑦  ВСТРЕЧНЫЙ: dry=False — запись доходит (проба умеет писать; без этого случая
     зелёные ①–⑥ не доказывали бы ничего — приёмка могла бы просто не уметь писать)
  ⑧  при dry=False соединение — ОБЫЧНЫЙ sqlite3.Connection, без подмены класса
  ⑨  ДОПОЛНЕНИЕ PROTO 2026-09-25 21:36 UTC (карточка — пробел холостого режима): база
     ЗАНЯТА другим пишущим (второй процесс держит BEGIN EXCLUSIVE в базе режима журнала
     отката) — снятие копии не ждёт бесконечно: холостой прогон завершается отказом
     «живая база не тронута» за ограниченное время (предел BUSY_SECONDS читается из
     самой копии dryrun.py на стенде, не держим то же число второй раз), своя база
     стенда не меняется. Случай ⑨ НЕ участвует в поломке --break old-connect (прежний
     код не пробует снимать копию вовсе, сравнивать с ним нечего) — под поломкой
     пропускается отдельной строкой, не входит в счёт случаев.
  ⑩  ВОЗВРАТ PROTO (тот же день): URI с `mode=rw` (живой вид вызова save-phoenix.py) —
     холостой ход ОБЯЗАН идти той же веткой отказа, что настоящий: файла нет → И
     холостое, И настоящее соединение поднимают ОДИНАКОВОЕ sqlite3.OperationalError
     («unable to open database file»), файл не создаётся ни там, ни там. Встречный
     (голый путь без файла → пустая рабочая копия, а не отказ) уже покрыт случаем ⑥ —
     здесь не дублируется. Случай ⑩ проходит и под --break old-connect (та же URI
     с mode=rw отказала бы и там — отказ идёт от самого режима файла, а не от нового
     кода), но проваливается РОВНО под отдельной поломкой --break no-rw-refusal.

Нарочные поломки:
  --break old-connect (--porcha — синоним): холостой режим снова открывает САМ ФАЙЛ
    через _DryConnection, как было до правки 2026-09-25 (тело connect() заменено на
    прежнее). Ждём провала РОВНО ②③④⑤⑥ — это пути мимо метода commit() и мимо подмены
    источника копией; ①⑦⑧⑩ проходят и с поломкой: ① — commit() был защищён и раньше,
    ⑦⑧ — они про dry=False, ⑩ — отказ там идёт от режима URI, а не от нового кода.
  --break no-rw-refusal: снят подъём OperationalError при отсутствии файла под URI
    mode=ro/rw (возврат PROTO, п. 2) — холостой ход снова расходится с настоящим на
    опечатке пути. Ждём провала РОВНО ⑩.

⛔ Живого контура не касается: своя база на стенде, своя (при поломке — правленая)
копия dryrun.py на стенде, среда каждого подпроцесса закреплена mezo_stand.stand_env
прямо на месте вызова.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.live_scripts()
DRYRUN_TOOL = SCRIPTS / "dryrun.py"
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

# ── тело connect() ДО и ПОСЛЕ правки 2026-09-25 — поломка возвращает старое ────────
# Текст справа — БУКВАЛЬНОЕ прежнее тело (редакция 13.08): холостое соединение снова
# открывает сам живой файл через _DryConnection, и защищён только commit().
_NEW_CONNECT_BODY = (
    "    if not dry:\n"
    "        return sqlite3.connect(db, factory=sqlite3.Connection, **kw)\n"
    "    print(BANNER, file=sys.stderr)\n"
    "    conn = _connect_dry(db, **kw)\n"
    "    atexit.register(_finish, conn)\n"
    "    return conn\n"
)
_OLD_CONNECT_BODY = (
    "    conn = sqlite3.connect(db, factory=(_DryConnection if dry else sqlite3.Connection),"
    " **kw)\n"
    "    if dry:\n"
    "        print(BANNER, file=sys.stderr)\n"
    "        atexit.register(_finish, conn)\n"
    "    return conn\n"
)
# ── возврат PROTO: снятие подъёма OperationalError при mode=ro/rw + файла нет ──────
# Три строки, добавленные правкой; поломка их убирает целиком — холостой ход снова
# расходится с настоящим на опечатке пути (падает обратно на пустую копию + stderr).
_NEW_MISSING_GUARD = (
    "    if not path.exists() and is_uri and _refuses_missing_file(db):\n"
    "        # Та же ветка, что и у настоящего connect() с этим mode — см."
    " _refuses_missing_file.\n"
    "        raise sqlite3.OperationalError(\"unable to open database file\")\n"
)
_OLD_MISSING_GUARD = ""
BREAKS = {
    "old-connect": ([(_NEW_CONNECT_BODY, _OLD_CONNECT_BODY)],
                    {"②", "③", "④", "⑤", "⑥"}),
    "no-rw-refusal": ([(_NEW_MISSING_GUARD, _OLD_MISSING_GUARD)],
                      {"⑩"}),
}

OK = FAIL = 0
RED: list[str] = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)
    return cond


def build_db(path: Path) -> None:
    """Своя маленькая база стенда: одна таблица, две строки. Не живая, без ролей."""
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    con.executemany("INSERT INTO t (val) VALUES (?)", [("a",), ("b",)])
    con.commit()
    con.close()


def row_count(path: Path) -> int:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    con.close()
    return n


PROBE_PREAMBLE = (
    "import sys\n"
    "sys.path.insert(0, {tools!r})\n"
    "import dryrun\n"
    "db = sys.argv[1]\n"
    "dry = sys.argv[2] == '1'\n"
)

# Тело пробы на каждый путь фиксации — ОДНО действие на случай, без подмешивания
# нескольких путей в один прогон (иначе провалы стало бы невозможно различить).
CASE_BODIES = {
    "①": (  # commit()
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
        "conn.commit()\n"
        "conn.close()\n"
    ),
    "②": (  # with conn: — Connection.__exit__ фиксирует на уровне C
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "with conn:\n"
        "    conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
        "conn.close()\n"
    ),
    "③": (  # executescript — библиотека сама фиксирует
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "conn.executescript(\"INSERT INTO t (val) VALUES ('x');\")\n"
        "conn.close()\n"
    ),
    "④": (  # execute("COMMIT") — прямой SQL мимо метода
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
        "conn.execute(\"COMMIT\")\n"
        "conn.close()\n"
    ),
    "⑤": (  # isolation_level=None — автофиксация
        "conn = dryrun.connect(db, dry, timeout=5, isolation_level=None)\n"
        "conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
        "conn.close()\n"
    ),
    "⑦": (  # встречный: dry=False — запись доходит
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
        "conn.commit()\n"
        "conn.close()\n"
    ),
    "⑧": (  # dry=False — обычный sqlite3.Connection
        "conn = dryrun.connect(db, dry, timeout=5)\n"
        "print('TYPE=' + type(conn).__name__)\n"
        "print('IS_DRY=' + str(isinstance(conn, dryrun._DryConnection)))\n"
        "conn.close()\n"
    ),
}
CASE6_BODY = (  # путь без файла — копия должна быть рабочей ПУСТОЙ базой в памяти
    "conn = dryrun.connect(db, dry, timeout=5)\n"
    "conn.execute(\"CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)\")\n"
    "conn.execute(\"INSERT INTO t (val) VALUES ('x')\")\n"
    "conn.commit()\n"
    "conn.close()\n"
)
CASE9_BODY = (  # занятая база — само connect() обязано отказать за ограниченное время
    "conn = dryrun.connect(db, dry, timeout=1)\n"
)
# Второй процесс (не поток — требование ⑨: замок держит ОТДЕЛЬНЫЙ процесс) держит
# BEGIN EXCLUSIVE до собственного sleep(); база по умолчанию в режиме журнала отката
# (build_db ничего в этом не меняет), там чужая запись мешает читающему НАЧАТЬ читать.
LOCKER_SRC = (
    "import sqlite3, sys, time\n"
    "conn = sqlite3.connect(sys.argv[1], timeout=1)\n"
    "conn.execute('BEGIN EXCLUSIVE')\n"
    "print('LOCKED', flush=True)\n"
    "time.sleep(float(sys.argv[2]))\n"
)
# ⑩ возврат PROTO: db здесь — уже ГОТОВАЯ URI-строка с mode=rw (её строит run_case10),
# не голый путь — PROBE_PREAMBLE отдаёт argv[1] как есть, разбора здесь не требуется.
# Печатаем класс и текст исключения (или его отсутствие) — сверяет вызывающий процесс.
CASE10_BODY = (
    "try:\n"
    "    dryrun.connect(db, dry, uri=True, timeout=5)\n"
    "    print('NO_EXCEPTION')\n"
    "except Exception as e:\n"
    "    print('EXC:' + type(e).__name__ + ':' + str(e))\n"
)


def write_probe(root: Path, tools: Path, mark: str, body: str) -> Path:
    p = root / f"probe-{ord(mark[0])}.py"
    p.write_text(PROBE_PREAMBLE.format(tools=str(tools)) + body, encoding="utf-8")
    return p


def run_probe(root: Path, probe: Path, db: Path, dry: bool):
    """Один случай — один подпроцесс, среда закреплена ПРЯМО ЗДЕСЬ (check-acceptance-env.py
    переменные не прослеживает — закрепление стои́т на месте вызова, а не в переменной)."""
    return subprocess.run(
        [sys.executable, str(probe), str(db), "1" if dry else "0"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"))


def run_write_case(root, tools, mark, name, dry, expect_change):
    """Случаи ①②③④⑤⑦: своя свежая база на два ряда, один путь фиксации, сверка числа строк."""
    db = root / f"case-{ord(mark[0])}.db"
    build_db(db)
    before = row_count(db)
    probe = write_probe(root, tools, mark, CASE_BODIES[mark])
    r = run_probe(root, probe, db, dry)
    after = row_count(db)
    changed = after != before
    ok = r.returncode == 0 and changed == expect_change
    case(mark, name, ok,
         f"код {r.returncode} · строк в живом файле стенда {before} → {after}"
         + ("" if ok else f"\n   вывод пробы: {(r.stdout + r.stderr).strip()[:500]}"))


def run_case6(root, tools):
    db = root / "case-6-missing.db"   # заведомо НЕ существует — не создаём заранее
    probe = write_probe(root, tools, "⑥", CASE6_BODY)
    r = run_probe(root, probe, db, dry=True)
    created = db.exists()
    ok = r.returncode == 0 and not created
    case("⑥", "путь без файла — холостой прогон файл НЕ создаёт (обычный "
              "sqlite3.connect создал бы его молча)",
         ok, f"код {r.returncode} · файл существует после: {created}"
         + ("" if ok else f"\n   вывод пробы: {(r.stdout + r.stderr).strip()[:500]}"))


def run_case8(root, tools):
    db = root / "case-8.db"
    build_db(db)
    probe = write_probe(root, tools, "⑧", CASE_BODIES["⑧"])
    r = run_probe(root, probe, db, dry=False)
    out = r.stdout
    ok = r.returncode == 0 and "TYPE=Connection" in out and "IS_DRY=False" in out
    case("⑧", "при dry=False соединение — обычный sqlite3.Connection, без подмены класса",
         ok, f"код {r.returncode} · вывод: {out.strip()}"
         + ("" if ok else f"\n   stderr: {r.stderr.strip()[:300]}"))


def _busy_seconds(tools: Path) -> int:
    """Предел ожидания занятой базы — читаем из КОПИИ dryrun.py на стенде текстом (не
    исполняя её в процессе приёмки): то же число, что видит инструмент, без риска
    держать его в приёмке отдельной, расходящейся копией."""
    src = (tools / "dryrun.py").read_text(encoding="utf-8")
    m = re.search(r"^BUSY_SECONDS\s*=\s*(\d+)", src, re.MULTILINE)
    if not m:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: в копии dryrun.py нет константы BUSY_SECONDS — "
                 "инструмент менялся, поправь приёмку")
    return int(m.group(1))


def run_case9(root, tools):
    """⑨ занятая база: второй процесс держит BEGIN EXCLUSIVE, снятие копии обязано
    отказать за ограниченное время, а не ждать без предела. Свой вызов подпроцесса
    для замка и свой — для пробы, оба со средой стенда прямо на месте вызова."""
    busy_seconds = _busy_seconds(tools)
    db = root / "case-9.db"
    build_db(db)
    locker_file = root / "locker-9.py"
    locker_file.write_text(LOCKER_SRC, encoding="utf-8")
    locker = subprocess.Popen(
        [sys.executable, str(locker_file), str(db), str(busy_seconds + 30)],
        stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"))

    locked = locker.stdout.readline().strip() == "LOCKED"
    result = None
    if locked:
        probe = write_probe(root, tools, "⑨", CASE9_BODY)
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                [sys.executable, str(probe), str(db), "1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"),
                timeout=busy_seconds + 20)
            result = ("ran", r, time.monotonic() - t0)
        except subprocess.TimeoutExpired:
            result = ("timeout", None, time.monotonic() - t0)

    locker.kill()
    try:
        locker.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

    name = ("занятая база (второй процесс держит BEGIN EXCLUSIVE): холостой прогон "
            "завершается отказом за ограниченное время, база не изменена")
    if not locked:
        case("⑨", name, False, "⛔ второй процесс не подтвердил захват блокировки")
        return
    kind, r, elapsed = result
    if kind == "timeout":
        case("⑨", name, False,
             f"⛔ пробу пришлось оборвать — предел {busy_seconds} с не сработал за "
             f"{busy_seconds + 20} с ожидания")
        return
    after = row_count(db)   # лок уже снят (locker убит и дождались выхода) — читаем безопасно
    out = (r.stdout or "") + (r.stderr or "")
    timely = (busy_seconds - 1) <= elapsed <= (busy_seconds + 15)
    ok = r.returncode != 0 and "живая база не тронута" in out and timely and after == 2
    case("⑨", name, ok,
         f"код {r.returncode} · ждал {elapsed:.1f} с (предел {busy_seconds} с) · "
         f"строк после: {after}" + ("" if ok else f"\n   вывод пробы: {out.strip()[:400]}"))


def run_case10(root, tools):
    """⑩ возврат PROTO: URI mode=rw + файла нет — холостой и настоящий отказывают
    ОДНОЙ И ТОЙ ЖЕ веткой (OperationalError), файл не создаётся ни там, ни там.
    Свой вызов подпроцесса на каждую сторону сравнения, среда стенда прямо в вызове."""
    db_path = root / "case-10-missing.db"      # заведомо НЕ существует
    uri_db = f"file:{db_path.as_posix()}?mode=rw"
    probe = write_probe(root, tools, "⑩", CASE10_BODY)

    r_dry = run_probe(root, probe, uri_db, dry=True)
    r_real = run_probe(root, probe, uri_db, dry=False)
    created = db_path.exists()

    def exc_line(r):
        out = (r.stdout or "") + (r.stderr or "")
        return next((l for l in out.splitlines() if l.startswith("EXC:")), None)

    exc_dry, exc_real = exc_line(r_dry), exc_line(r_real)
    ok = (exc_dry is not None and exc_real is not None
          and exc_dry.split(":", 2)[1] == "OperationalError"
          and exc_real.split(":", 2)[1] == "OperationalError"
          and exc_dry == exc_real and not created)
    case("⑩", "URI mode=rw + файла нет: холостой и настоящий отказывают ОДИНАКОВО "
              "(OperationalError), файл не создан ни там, ни там",
         ok, f"холостой: {exc_dry!r} · настоящий: {exc_real!r} · файл создан: {created}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()
    if a.break_name:
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    root = mezo_stand.new("bite-dryrun-commit-paths-")
    tools = root / "tools"
    mezo_stand.copy_tool(DRYRUN_TOOL, tools)
    tool_copy = tools / "dryrun.py"
    if a.break_name:
        text = tool_copy.read_text(encoding="utf-8")
        for old, new in BREAKS[a.break_name][0]:
            if text.count(old) != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                         f"(образец найден {text.count(old)} раз в копии dryrun.py — "
                         "инструмент менялся, поправь якорь приёмки)")
            text = text.replace(old, new)
        tool_copy.write_text(text, encoding="utf-8")

    run_write_case(root, tools, "①", "commit(): холостой прогон базу не меняет",
                  dry=True, expect_change=False)
    run_write_case(root, tools, "②", "with conn: холостой прогон базу не меняет "
                  "(фиксация на уровне C, мимо метода commit())",
                  dry=True, expect_change=False)
    run_write_case(root, tools, "③", "executescript(...): холостой прогон базу не меняет "
                  "(библиотека фиксирует сама, мимо метода)",
                  dry=True, expect_change=False)
    run_write_case(root, tools, "④", "execute(\"COMMIT\"): холостой прогон базу не меняет "
                  "(прямой SQL мимо метода)",
                  dry=True, expect_change=False)
    run_write_case(root, tools, "⑤", "isolation_level=None: холостой прогон базу не меняет "
                  "(автофиксация, метод commit() не зовётся)",
                  dry=True, expect_change=False)
    run_case6(root, tools)
    run_write_case(root, tools, "⑦", "ВСТРЕЧНЫЙ: dry=False — запись доходит "
                  "(проба умеет писать)",
                  dry=False, expect_change=True)
    run_case8(root, tools)
    run_case10(root, tools)
    if a.break_name:
        print("ℹ️ ⑨ (занятая база) под поломкой не проверяется — прежний код не пробует "
              "снимать копию вовсе, сравнивать нечего; не входит в счёт случаев")
    else:
        run_case9(root, tools)

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'✅' if exact else '🔴'} поломка «{a.break_name}»: провалились "
              f"{' '.join(sorted(RED)) or 'никто'} · ждали {' '.join(sorted(expected))}")
        return mezo_stand.finish(0 if exact else 1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
