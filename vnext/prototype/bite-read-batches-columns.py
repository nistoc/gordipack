#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА карточки 510: колонки read_batches.shown_max и read_batches.acked_at заводит ШАГ СХЕМЫ,
а чтение ленты схему базы не правит.

Предмет. Чтение ленты (read-messages.py) при первом вызове само заводило таблицу выдач и добавляло
ей две колонки — без строки в журнале схемы. Шаг 20260809-batch-race-lock строит по acked_at
частичный индекс: колонку предполагает, но не заводит. Правка: колонки заводит шаг
migrations/20261118-read-batches-columns.py и записывает себя в журнал; чтение ленты только
смотрит и отказывает словами; шаг 0809 без колонки отказывает словами и называет новый шаг.

Случаи (у каждого своя база в стенде; виды базы: «старая» — таблица из четырёх колонок,
«половина» — нет только acked_at, «без таблицы», «полная» — обе колонки есть):
  ①   чтение ленты на старой базе отказывает кодом 2, называет обе колонки и шаг; база не тронута
  ②   шаг на старой базе добавляет обе колонки; прежняя строка таблицы цела
  ②б  ВСТРЕЧНЫЙ из критерия: после шага чтение ленты на той же базе работает и пишет shown_max
  ②ж  шаг записал себя в журнал схемы одной строкой, и в ней сказано, что сделано
  ③   повторный прогон шага: «уже сведено», структура и строка журнала те же
  ④   ВСТРЕЧНЫЙ из критерия: на базе, где колонки уже есть, шаг не падает, структуру не меняет
      и записывает себя в журнал
  ④б  на базе, где нет только acked_at, шаг добавляет одну её; значение shown_max цело
  ④в  таблицы нет вовсе: чтение ленты отказывает своими словами, шаг заводит таблицу целиком
  ⑤   холостой прогон шага (--dry-run) базу не меняет
  ⑥   шаг 20260809-batch-race-lock на старой базе отказывает кодом 2 и называет новый шаг;
      после нового шага он проходит и ставит свой индекс
  ⑦   в чтении ленты нет ни одной команды, меняющей схему (разбором исходника)
  ⑧   базе без журнала схемы шаг отказывает кодом 2 словами, база не тронута

Нарочные поломки — каждая в КОПИИ каталога инструментов внутри стенда; до них та же копия без
поломки обязана пройти все случаи (ступень «копия запустилась»). У каждой поломки ниже записано
заранее, какие случаи обязаны упасть; итог сверяет множества поимённо.

ЧЕГО НЕ ПРОВЕРЯЕТ: путь обновления настоящего контура ниже v3 (здесь старая таблица собрана
руками в стенде); другие режимы чтения ленты, кроме обычного чтения; что шаг вписан в порядок
шагов (schema_step_order.py) — это держат tests/test_schema.py и bite-fresh-circuit.py.

⛔ Живой базы не касается: все базы — копии схемы в стенде. Три исхода: 0 принята · 1 не принята ·
2 не запустилась.   Запуск: python <абсолютный путь>/bite-read-batches-columns.py [--no-breaks]
"""
import ast
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем
import mezo_paths  # noqa: E402 — где база контура, с которой снимается схема
import mezo_stand  # noqa: E402 — стенд

READER_NAME = "read-messages.py"
STEP = "20261118-read-batches-columns"
LOCK_STEP = "20260809-batch-race-lock"
ROLE = "PROTO"
MARK = "посев приёмки bite-read-batches-columns"
OLD_HOUR = "2000-01-01 00:00:00"

OLD_TABLE = ("CREATE TABLE read_batches (token TEXT PRIMARY KEY, role TEXT NOT NULL, "
             "last_id INTEGER NOT NULL, issued_at TEXT NOT NULL DEFAULT (datetime('now')))")
FULL_TABLE = OLD_TABLE[:-1] + ", shown_max INTEGER, acked_at TEXT)"
LOCK_INDEX = ("CREATE UNIQUE INDEX ux_batch_race ON read_batches(role, last_id) "
              "WHERE acked_at IS NULL")
SCHEMA_EDIT = re.compile(r"\b(ALTER\s+TABLE|CREATE\s+(?:VIRTUAL\s+)?TABLE|CREATE\s+(?:UNIQUE\s+)?INDEX|"
                         r"CREATE\s+TRIGGER|CREATE\s+VIEW|DROP\s+(?:TABLE|INDEX|COLUMN|TRIGGER|VIEW))\b",
                         re.IGNORECASE)

TITLES = {
    "①": "① чтение ленты на старой базе отказывает кодом 2, называет обе колонки и шаг; база не тронута",
    "②": "② шаг на старой базе добавляет обе колонки; прежняя строка таблицы цела",
    "②б": "②б ВСТРЕЧНЫЙ: после шага чтение ленты на той же базе работает и пишет shown_max",
    "②ж": "②ж шаг записал себя в журнал схемы одной строкой, и в ней сказано, что сделано",
    "③": "③ повторный прогон шага: «уже сведено», структура и строка журнала те же",
    "④": "④ ВСТРЕЧНЫЙ: где колонки уже есть, шаг не падает, структуру не меняет, пишет себя в журнал",
    "④б": "④б где нет только acked_at, шаг добавляет одну её; значение shown_max цело",
    "④в": "④в таблицы нет: чтение ленты отказывает своими словами, шаг заводит таблицу целиком",
    "⑤": "⑤ холостой прогон шага (--dry-run) базу не меняет",
    "⑥": "⑥ шаг 0809 на старой базе отказывает и называет новый шаг; после него проходит",
    "⑦": "⑦ в чтении ленты нет ни одной команды, меняющей схему",
    "⑧": "⑧ базе без журнала схемы шаг отказывает кодом 2 словами, база не тронута",
}

READER_GAP_CALL = "    gap = batches_table_gap(conn)\n"
OLD_READER_CODE = (
    "    conn.execute(\"CREATE TABLE IF NOT EXISTS read_batches (token TEXT PRIMARY KEY, \"\n"
    "                 \"role TEXT NOT NULL, last_id INTEGER NOT NULL, \"\n"
    "                 \"issued_at TEXT NOT NULL DEFAULT (datetime('now')), \"\n"
    "                 \"shown_max INTEGER, acked_at TEXT)\")\n"
    "    for _col, _decl in ((\"shown_max\", \"INTEGER\"), (\"acked_at\", \"TEXT\")):\n"
    "        if _col not in {r[1] for r in conn.execute(\"PRAGMA table_info(read_batches)\")}:\n"
    "            conn.execute(f\"ALTER TABLE read_batches ADD COLUMN {_col} {_decl}\")\n"
    "    conn.commit()\n"
    "    gap = None\n")
ALTER_LINE = '                conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {name} {decl}")\n'

# (название · файл в копии · [(было, стало)] · какие случаи обязаны упасть)
BREAKS = (
    ("П1 чтение ленты снова правит схему на ходу (прежний код)", READER_NAME,
     [(READER_GAP_CALL, OLD_READER_CODE)], ("①", "④в", "⑦")),
    ("П2 чтение ленты не отказывает, когда колонок нет", READER_NAME,
     [('    if missing:\n        return "в таблице read_batches нет колонок: "',
       '    if False:\n        return "в таблице read_batches нет колонок: "')], ("①",)),
    ("П3 отсутствие таблицы названо не своими словами", READER_NAME,
     [('    if not have:\n        return "таблицы read_batches нет"\n',
       '    if False:\n        return "таблицы read_batches нет"\n')], ("④в",)),
    ("П4 чтение ленты отказывает и на готовой базе", READER_NAME,
     [('+ ", ".join(missing)\n    return None\n', '+ ", ".join(missing)\n    return "нарочная поломка"\n')],
     ("②б",)),
    ("П5 в чтении ленты появилась своя правка схемы", READER_NAME,
     [(READER_GAP_CALL, READER_GAP_CALL +
       '    if False:\n        conn.execute("ALTER TABLE read_batches ADD COLUMN probe TEXT")\n')], ("⑦",)),
    ("П6 шаг меняет строки таблицы", f"migrations/{STEP}.py",
     [(ALTER_LINE, ALTER_LINE +
       '                conn.execute(f"UPDATE {TABLE} SET last_id = last_id + 1")\n')], ("②",)),
    ("П7 шаг не говорит в журнале, что сделал", f"migrations/{STEP}.py",
     [('f"чтение ленты: {done}. Карточка #510")', '"чтение ленты. Карточка #510")')], ("②ж",)),
    ("П8 шаг пишет в журнал не свою строку", f"migrations/{STEP}.py",
     [("    fp = record_step(conn, VERSION,\n", '    fp = record_step(conn, VERSION + "-x",\n')],
     ("②ж", "③", "④")),
    ("П9 повторный прогон шага снова пишет в базу", f"migrations/{STEP}.py",
     [("    if has_table and not missing and journaled:\n", "    if False:\n")], ("③",)),
    ("П10 шаг добавляет колонки, не глядя, есть ли они", f"migrations/{STEP}.py",
     [("            if name in missing:\n" + ALTER_LINE, "            if True:\n" + ALTER_LINE)], ("④б",)),
    ("П11 шаг отказывает базе, где колонки уже есть", f"migrations/{STEP}.py",
     [('        done = "колонки уже были (файл схемы либо прежнее чтение ленты) — записан след"\n',
       "        conn.rollback()\n        conn.close()\n        return 1\n")], ("④",)),
    ("П12 холостой прогон шага пишет в базу", f"migrations/{STEP}.py",
     [("    if args.dry_run:\n        conn.close()\n", "    if False:\n        conn.close()\n")], ("⑤",)),
    ("П13 шаг 0809 снова молчит о колонке", f"migrations/{LOCK_STEP}.py",
     [('    if "acked_at" not in batch_columns:\n', "    if False:\n")], ("⑥",)),
    ("П14 шаг не проверяет журнал схемы до работы", f"migrations/{STEP}.py",
     [("    refusal = precheck(db)\n", "    refusal = None\n")], ("⑧",)),
)


class NotStarted(Exception):
    """Приёмке нечем мерить: исход «не запустилась», код 2."""


def run(tool: Path, *args, root: Path):
    """Запустить инструмент на стенде. → (код, весь вывод)."""
    proc = subprocess.run([sys.executable, str(tool), *map(str, args)], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=300,
                          env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                                                   PYTHONDONTWRITEBYTECODE="1"))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def query(db: Path, sql: str, args=()):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def columns(db: Path) -> list:
    return [row[1] for row in query(db, "PRAGMA table_info(read_batches)")]


def structure(db: Path) -> str:
    return "\n".join(row[0] for row in query(
        db, "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"))


def journal(db: Path, version: str = STEP) -> list:
    return query(db, "SELECT version, applied_at, note, fingerprint FROM schema_migrations "
                     "WHERE version = ?", (version,))


def batches(db: Path) -> list:
    return query(db, "SELECT * FROM read_batches ORDER BY token")


def make_template(home: Path, shape: str, live_db: Path) -> Path:
    """База-образец одного вида: схема контура без строк, таблица выдач собрана под вид."""
    db = home / f"template-{shape}.db"
    mezo_stand.empty_db(live_db, db)
    mezo_stand.seed_roles(db, [ROLE])
    con = sqlite3.connect(db)
    con.execute("DELETE FROM schema_migrations WHERE version = ?", (STEP,))
    con.execute("DROP INDEX IF EXISTS ux_batch_race")
    con.execute("DROP TABLE IF EXISTS read_batches")
    if shape in ("old", "half"):
        con.execute(OLD_TABLE)
        con.execute("INSERT INTO read_batches (token, role, last_id) VALUES ('prior-batch', 'TAXO', 7)")
    if shape == "half":
        con.execute("ALTER TABLE read_batches ADD COLUMN shown_max INTEGER")
        con.execute("UPDATE read_batches SET shown_max = 7")
    if shape == "full":
        con.execute(FULL_TABLE)
        con.execute(LOCK_INDEX)
        con.execute("INSERT INTO read_batches (token, role, last_id, shown_max) "
                    "VALUES ('prior-batch', 'TAXO', 7, 7)")
    for number in range(1, 4):
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority) "
                    "VALUES ('COORD', datetime('now'), ?, '[]', 'normal')", (f"{MARK}: записка {number}",))
    con.commit()
    con.close()
    return db


class Bench:
    """Один проход всех случаев по одному каталогу инструментов."""

    def __init__(self, tools: Path, templates: dict, home: Path, tag: str):
        self.reader = tools / READER_NAME
        self.step = tools / "migrations" / f"{STEP}.py"
        self.lock_step = tools / "migrations" / f"{LOCK_STEP}.py"
        self.templates = templates
        self.home = home / tag
        self.counter = 0

    def base(self, shape: str):
        """Своя база случая: копия образца в <стенд>/<проход>/<номер>/.mezosync/. → (корень, база)."""
        self.counter += 1
        root = self.home / f"{self.counter:02d}-{shape}"
        (root / ".mezosync").mkdir(parents=True)
        db = root / ".mezosync" / "mezosync.db"
        shutil.copyfile(self.templates[shape], db)
        return root, db

    def read(self, root, db):
        return run(self.reader, "--db", db, "--role", ROLE, root=root)

    def apply(self, root, db, *extra):
        return run(self.step, "--db", db, *extra, root=root)

    # ── случаи: каждый возвращает (прошёл, что видел) ─────────────────────────────────────────
    def case_1(self):
        root, db = self.base("old")
        before = (columns(db), batches(db), structure(db))
        code, out = self.read(root, db)
        ok = (code == 2 and "НЕ ЗАПУСТИЛОСЬ" in out and "shown_max, acked_at" in out
              and STEP in out and "Traceback" not in out
              and (columns(db), batches(db), structure(db)) == before)
        return ok, f"код {code} · колонок {len(columns(db))} · шаг назван: {STEP in out}"

    def case_2(self):
        root, db = self.base("old")
        before = query(db, "SELECT token, role, last_id, issued_at FROM read_batches")
        code, out = self.apply(root, db)
        have = columns(db)
        after = query(db, "SELECT token, role, last_id, issued_at FROM read_batches")
        ok = (code == 0 and "ПРИМЕНЕНО" in out and "shown_max" in have and "acked_at" in have
              and len(before) == 1 and after == before)
        return ok, f"код {code} · колонки {have} · строка цела: {after == before}"

    def case_2b(self):
        root, db = self.base("old")
        step_code, _ = self.apply(root, db)
        code, out = self.read(root, db)
        rows = query(db, "SELECT shown_max FROM read_batches WHERE role = ?", (ROLE,)) \
            if "shown_max" in columns(db) else []
        ok = (step_code == 0 and code == 0 and MARK in out and "Traceback" not in out
              and len(rows) == 1 and rows[0][0] is not None)
        return ok, f"шаг код {step_code} · чтение код {code} · выдач роли {len(rows)}"

    def case_2j(self):
        root, db = self.base("old")
        code, _ = self.apply(root, db)
        rows = journal(db)
        ok = (code == 0 and len(rows) == 1
              and "добавлены колонки: shown_max, acked_at" in (rows[0][2] or "") and bool(rows[0][3]))
        return ok, f"код {code} · строк шага в журнале {len(rows)} · " \
                   f"запись: {(rows[0][2] or '')[-70:] if rows else '—'}"

    def case_3(self):
        root, db = self.base("old")
        first, _ = self.apply(root, db)
        con = sqlite3.connect(db)
        con.execute("UPDATE schema_migrations SET applied_at = ? WHERE version = ?", (OLD_HOUR, STEP))
        con.commit()
        con.close()
        before = (structure(db), journal(db), batches(db))
        code, out = self.apply(root, db)
        after = (structure(db), journal(db), batches(db))
        ok = (first == 0 and code == 0 and "уже сведено" in out and after == before
              and len(after[1]) == 1 and after[1][0][1] == OLD_HOUR)
        return ok, f"первый код {first} · повтор код {code} · «уже сведено»: {'уже сведено' in out} · " \
                   f"база та же: {after == before}"

    def case_4(self):
        root, db = self.base("full")
        before = (structure(db), batches(db))
        code, out = self.apply(root, db)
        rows = journal(db)
        ok = (code == 0 and "колонки уже были" in out and "Traceback" not in out
              and (structure(db), batches(db)) == before and len(rows) == 1)
        return ok, f"код {code} · структура та же: {(structure(db), batches(db)) == before} · " \
                   f"строк шага в журнале {len(rows)}"

    def case_4b(self):
        root, db = self.base("half")
        code, out = self.apply(root, db)
        have = columns(db)
        shown = query(db, "SELECT shown_max FROM read_batches WHERE token = 'prior-batch'")
        ok = (code == 0 and "добавлены колонки: acked_at" in out and have.count("shown_max") == 1
              and "acked_at" in have and shown == [(7,)])
        return ok, f"код {code} · колонки {have} · shown_max прежней строки: {shown}"

    def case_4v(self):
        root, db = self.base("none")
        read_code, read_out = self.read(root, db)
        untouched = columns(db) == []
        code, out = self.apply(root, db)
        have = columns(db)
        ok = (read_code == 2 and "таблицы read_batches нет" in read_out and STEP in read_out
              and "Traceback" not in read_out and untouched and code == 0 and "заведена целиком" in out
              and have == ["token", "role", "last_id", "issued_at", "shown_max", "acked_at"])
        return ok, f"чтение код {read_code} · таблицы до шага нет: {untouched} · шаг код {code} · " \
                   f"колонок {len(have)}"

    def case_5(self):
        root, db = self.base("old")
        before = (structure(db), batches(db), query(db, "SELECT COUNT(*) FROM schema_migrations"))
        code, out = self.apply(root, db, "--dry-run")
        after = (structure(db), batches(db), query(db, "SELECT COUNT(*) FROM schema_migrations"))
        ok = code == 0 and "ВХОЛОСТУЮ" in out and after == before and journal(db) == []
        return ok, f"код {code} · база та же: {after == before} · строк шага в журнале {len(journal(db))}"

    def case_6(self):
        root, db = self.base("old")
        code, out = run(self.lock_step, "--db", db, root=root)
        index_sql = "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = 'ux_batch_race'"
        refused = (code == 2 and "НЕ ЗАПУСТИЛСЯ" in out and STEP in out and "Traceback" not in out
                   and query(db, index_sql) == [(0,)])
        step_code, _ = self.apply(root, db)
        code2, out2 = run(self.lock_step, "--db", db, root=root)
        ok = refused and step_code == 0 and code2 == 0 and query(db, index_sql) == [(1,)]
        return ok, f"до шага: код {code}, отказ словами: {refused} · после шага: код {code2}, " \
                   f"индексов {query(db, index_sql)[0][0]}"

    def case_7(self):
        tree = ast.parse(self.reader.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docstrings.add(id(body[0].value))
        found = sorted({match.group(0).upper() for node in ast.walk(tree)
                        if isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and id(node) not in docstrings
                        for match in SCHEMA_EDIT.finditer(node.value)})
        return not found, f"команд правки схемы в строках кода: {found or 'нет'}"

    def case_8(self):
        root, db = self.base("old")
        con = sqlite3.connect(db)
        con.execute("DROP TABLE schema_migrations")
        con.commit()
        con.close()
        before = (columns(db), batches(db))
        code, out = self.apply(root, db)
        ok = (code == 2 and "НЕТ ЖУРНАЛА СХЕМЫ" in out and "Traceback" not in out
              and (columns(db), batches(db)) == before)
        return ok, f"код {code} · отказ словами: {'НЕТ ЖУРНАЛА СХЕМЫ' in out} · " \
                   f"база та же: {(columns(db), batches(db)) == before}"

    def judge(self) -> dict:
        """Все случаи по порядку. → {имя: (прошёл, что видел)}; сбой случая — провал со словом."""
        plan = (("①", self.case_1), ("②", self.case_2), ("②б", self.case_2b), ("②ж", self.case_2j),
                ("③", self.case_3), ("④", self.case_4), ("④б", self.case_4b), ("④в", self.case_4v),
                ("⑤", self.case_5), ("⑥", self.case_6), ("⑦", self.case_7), ("⑧", self.case_8))
        verdicts = {}
        for name, case in plan:
            try:
                verdicts[name] = case()
            except (sqlite3.Error, OSError, subprocess.TimeoutExpired, SyntaxError) as problem:
                verdicts[name] = (False, f"случай не досчитан: {type(problem).__name__}: {problem}")
        return verdicts


def copy_tools(source: Path, dest: Path) -> Path:
    """Копия каталога инструментов (модули и шаги схемы) — испытуемое для поломки."""
    (dest / "migrations").mkdir(parents=True)
    for file in source.glob("*.py"):
        shutil.copyfile(file, dest / file.name)
    for file in (source / "migrations").glob("*.py"):
        shutil.copyfile(file, dest / "migrations" / file.name)
    return dest


def plant(tools: Path, relative: str, swaps) -> None:
    """Поставить поломку в копию: каждая подмена обязана найтись ровно один раз."""
    target = tools / relative
    with open(target, encoding="utf-8", newline="") as handle:
        text = handle.read()
    ending = "\r\n" if "\r\n" in text else "\n"
    for old, new in swaps:
        old, new = old.replace("\n", ending), new.replace("\n", ending)
        if text.count(old) != 1:
            raise NotStarted(f"место поломки найдено {text.count(old)} раз (нужно 1) в {relative}: "
                             f"{old[:60]!r} — испытуемое изменилось, поломка бьёт мимо")
        text = text.replace(old, new, 1)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main() -> int:
    with_breaks = "--no-breaks" not in sys.argv[1:]
    try:
        reader = mezo_target.script(READER_NAME)
        tools = reader.parent
        for needed in (reader, tools / "migrations" / f"{STEP}.py",
                       tools / "migrations" / f"{LOCK_STEP}.py", tools / "schema_journal.py"):
            if not needed.is_file():
                raise NotStarted(f"у испытуемого нет файла {needed}")
        live_db = Path(mezo_paths.live_db())
        if not live_db.is_file():
            raise NotStarted(f"базы контура, с которой снимается схема, нет: {live_db}")
        home = mezo_stand.new("bite-rbcols-")
        templates = {shape: make_template(home, shape, live_db)
                     for shape in ("old", "half", "none", "full")}

        print(f"ПРИЁМКА карточки 510 · испытуемое: {tools.as_posix()}")
        verdicts = Bench(tools, templates, home, "main").judge()
        failed = [name for name, (ok, _) in verdicts.items() if not ok]
        for name, (ok, seen) in verdicts.items():
            print(f"  {'✅' if ok else '🔴'} {TITLES[name]}\n        {seen}")

        break_lines, breaks_ok = [], True
        if with_breaks:
            control = copy_tools(tools, home / "copy-control")
            control_failed = [name for name, (ok, _) in
                              Bench(control, templates, home, "control").judge().items() if not ok]
            print(f"\nКОПИЯ БЕЗ ПОЛОМКИ (ступень «копия запустилась»): "
                  f"{'все случаи прошли' if not control_failed else 'упали ' + ' '.join(control_failed)}")
            if control_failed:
                raise NotStarted("копия инструментов без поломки не проходит случаи: "
                                 + " ".join(control_failed) + " — судить поломки не на чем")
            for number, (title, relative, swaps, expected) in enumerate(BREAKS, 1):
                broken = copy_tools(tools, home / f"copy-{number:02d}")
                plant(broken, relative, swaps)
                fallen = [name for name, (ok, _) in
                          Bench(broken, templates, home, f"break-{number:02d}").judge().items() if not ok]
                exact = set(fallen) == set(expected)
                breaks_ok &= exact
                break_lines.append(f"  {'✅' if exact else '🔴'} {title}\n        ждали: {' '.join(expected)} · "
                                   f"упали: {' '.join(fallen) or 'ни один'}")
            print("НАРОЧНЫЕ ПОЛОМКИ (ожидания записаны в таблице BREAKS до прогона):")
            print("\n".join(break_lines))
    except NotStarted as reason:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: {reason}")
        return mezo_stand.finish(2)

    total = len(verdicts)
    accepted = not failed and breaks_ok
    breaks_word = (f"нарочных поломок {sum(1 for line in break_lines if line.lstrip().startswith('✅'))} "
                   f"из {len(BREAKS)} уронили ровно своё" if with_breaks else "нарочные поломки не гонялись")
    print(f"\nИТОГ: {'✅ ПРИНЯТА' if accepted else '🔴 НЕ ПРИНЯТА'} — случаев прошло "
          f"{total - len(failed)} из {total}"
          f"{' · упали: ' + ' '.join(failed) if failed else ''} · {breaks_word}")
    return mezo_stand.finish(0 if accepted else 1)


if __name__ == "__main__":
    sys.exit(main())
