# -*- coding: utf-8 -*-
r"""ПРИЁМКА восстановимости выгрузки backup-db.py с таблицей поиска — карточка #610.

🩸 ЧЕМ ОПЛАЧЕНО. Таблица полнотекстового поиска phoenix_records_fts (FTS5, внешнее
содержимое) сломала выгрузку: iterdump на Python 3.14.6 представляет виртуальную
таблицу строкой PRAGMA writable_schema + INSERT INTO sqlite_master, следующая же
строка INSERT INTO "phoenix_records_fts" падает — таблицы ещё нет. А проверка
разворотом печатала последней строкой уборку временного файла, а не исход —
находка tapas 2026-09-13, задокументирована в карточке #610.

Случаи С1–С8 — как названы в карточке (буквы и номера её же). Нарочные поломки
П1–П5 — ослабленные копии backup-db.py; каждая обязана провалить СВОИ случаи и
только их (обратный ход, как в bite-backup-shrink.py). Якорь каждой поломки
существует в исходнике ДО ослабления и пропадает ПОСЛЕ — weaken() возвращает
None, если якорь не найден, и приёмка тогда останавливается на этом случае,
а не притворяется, что случай прошёл.

⛔ Живой mezosync.db этот файл не пишет НИКОГДА: копия снимается ТОЛЬКО через
   sqlite3.connect("file:...?mode=ro", uri=True).backup().
⚠️ Каждый временный стенд — в СВОЁМ каталоге (--tmp, по умолчанию — обычный
   временный каталог системы, как у bite-backup-shrink.py); убирается в finally.

🩸 С8 — ПРАВКА ПО СЛОВУ PROTO (2026-09-14, в ходе приёмки). Первая редакция сверяла
sha256/mtime ЖИВОЙ базы «до» и «после» — и была обречена мигать красным без своей
вины: живую базу штатно пишут все роли (записки, подтверждения прочтения), и стоит
кому-то записать записку в те же секунды — случай красится по чужой причине (ровно
так 2026-09-14 08:11 UTC упал приёмщик шага 3 карточки #608). Починка: судим не
СОСТОЯНИЕ живой базы (её меняет весь контур, не эта приёмка), а ПОВЕДЕНИЕ САМОЙ
ПРИЁМКИ — три раздельных пункта:
  (а) КАЖДЫЙ вызов backup-db.py идёт через обёртку run_tool(), а та ДО запуска
      подпроцесса проверяет: --db задан и лежит внутри песочницы этого прогона,
      --out задан и лежит внутри неё же. Не так — обёртка ОТКАЗЫВАЕТ и подпроцесс
      не запускается вовсе (живая база не открывается НИ РАЗУ, даже на чтение).
      С8(а) зелёный, если обёртка ни разу не отказала.
  (б) рядом с живой базой (каталог .mezosync) не появилось новых файлов с именем,
      содержащим «_verify», или временных файлов выгрузки (*.tmp/*.sql.tmp) —
      сравнение списка имён каталога ДО и ПОСЛЕ всего прогона.
  (в) в тексте самой приёмки нет ни одного sqlite3.connect(...) к LIVE_DB без
      mode=ro — проверяется СТАТИЧЕСКИ, разбором своего же исходника.
Нарочная поломка (обратный ход, не входит в счёт П1–П5 — те целятся в backup-db.py,
эта — в саму приёмку): пробный вызов backup-db.py внутри случая С8 лишается --db
в ослабленной копии ЭТОГО файла; обёртка обязана отказать ДО запуска, и С8(а)
обязан покраснеть ИМЕННО по этой причине.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import pathlib
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
TOOL = SCRIPTS / "backup-db.py"
MIRROR = mezo_paths.container_root(__file__) / "atlas.agents-sync.db"      # ТОЛЬКО чтение
RESTORE_VERIFY = MIRROR / "restore-verify.py"                              # ТОЛЬКО чтение
LIVE_DB = mezo_paths.live_db(__file__)                                     # ТОЛЬКО чтение

CASES = DIFFER = BAD = 0
SANDBOX_ROOT = None      # корень песочницы этого прогона — выставляется в main()
RUN_LOG = []             # каждый вызов run_tool(): dict(db, out, script, flags, refused, reason)


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, BAD
    CASES += 1
    DIFFER += bool(differ)
    BAD += 0 if verdict else 1
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _in_sandbox(path) -> bool:
    """True — путь лежит внутри песочницы этого прогона (SANDBOX_ROOT)."""
    if SANDBOX_ROOT is None or path is None:
        return False
    try:
        pathlib.Path(path).resolve().relative_to(SANDBOX_ROOT.resolve())
        return True
    except (ValueError, OSError):
        return False


def run_tool(db, out, *flags, script=TOOL):
    """Обёртка вызова backup-db.py. ДО запуска подпроцесса проверяет, что --db и
    --out ОБА лежат внутри песочницы этого прогона — иначе ОТКАЗЫВАЕТ и подпроцесс
    не стартует вовсе (случай С8: живая база через эту обёртку не открывается
    НИ РАЗУ, даже на чтение, при любом исходе проверки)."""
    entry = {"db": (str(db) if db is not None else None),
             "out": (str(out) if out is not None else None),
             "script": str(script), "flags": list(flags),
             "refused": False, "reason": None}
    if db is None or not _in_sandbox(db):
        entry["refused"] = True
        entry["reason"] = f"--db отсутствует или вне песочницы ({db!r})"
    elif out is None or not _in_sandbox(out):
        entry["refused"] = True
        entry["reason"] = f"--out отсутствует или вне песочницы ({out!r})"
    RUN_LOG.append(entry)
    if entry["refused"]:
        return 99, f"⛔ ОБЁРТКА ОТКАЗАЛА, подпроцесс не запущен: {entry['reason']}"
    r = subprocess.run([sys.executable, str(script), "--db", str(db),
                        "--out", str(out), *flags],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _temp_file_listing(d: pathlib.Path):
    """Имена в каталоге d, похожие на временные артефакты backup-db.py (случай С8б)."""
    return sorted(p.name for p in d.iterdir()
                 if "_verify" in p.name or p.name.endswith(".tmp") or p.name.endswith(".sql.tmp"))


def weaken(d: pathlib.Path, anchor: str, replacement: str, label: str) -> pathlib.Path:
    """Копия гарда с ослабленной веткой. None — якорь не найден (гард поменялся)."""
    original = TOOL.read_text(encoding="utf-8")
    broken = original.replace(anchor, replacement, 1)
    if broken == original:
        return None
    if anchor in broken:          # контроль: якорь обязан ИСЧЕЗНУТЬ после замены
        return None
    weak_path = d / f"weak-{label}.py"
    weak_path.write_text(broken, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    return weak_path


def weaken_self(d: pathlib.Path, anchor: str, replacement: str, label: str) -> pathlib.Path:
    """Копия ЭТОЙ приёмки (не backup-db.py) с ослабленной веткой — обратный ход для
    поломок, целящих в саму приёмку (случай С8). Тот же контроль якоря, что и weaken().

    ⚠️ Эта копия исполняется ИЗ ПЕСОЧНИЦЫ (вне корня контура), а модульный код
    приёмки зовёт mezo_paths.container_root(__file__) уже при импорте (SCRIPTS/MIRROR/
    LIVE_DB) — без подсказки поиск контейнера от расположения копии упрётся вверх
    в системный временный каталог и упадёт. local.paths рядом со СВОЕЙ же копией
    mezo_paths.py — штатный, документированный в mezo_paths.py способ (③), не
    переменная среды: она не течёт дальше этого прогона и не грозит классом
    «стенд наследует среду вызывающего» (MEZO_CONTAINER процессу не выставляется).
    """
    here = pathlib.Path(__file__).resolve()
    original = here.read_text(encoding="utf-8")
    broken = original.replace(anchor, replacement, 1)
    if broken == original or anchor in broken:
        return None
    weak_path = d / f"self-weak-{label}.py"
    weak_path.write_text(broken, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    (d / "local.paths").write_text(f"container={mezo_paths.container_root(__file__)}\n",
                                   encoding="utf-8")
    return weak_path


def load_tool_module(path: pathlib.Path, name: str):
    """Загрузить backup-db.py (или его ослабленную копию) как модуль — для прямой
    проверки функций write_and_verify/restore_and_check (случаи С5/С6, поломка П4)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


# ── стенды ────────────────────────────────────────────────────────────────

RARE = "единственноесловоредкое"
FREQUENT = "повторяемоесловочастое"
CYRILLIC = "кириллица"
LATIN = "latinword"
YO_WORD = "ёжиковое"


def build_rich_stand(d: pathlib.Path) -> pathlib.Path:
    """Таблица поиска (FTS5, внешнее содержимое) + триггеры + обычные таблицы
    с законной и незаконной убылью — для случаев С1(мал.)/С2/С7, поломок П1/П2/П5."""
    d.mkdir(parents=True, exist_ok=True)
    db = d / "rich.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE phoenix_records (id INTEGER PRIMARY KEY, role TEXT,"
               " subject TEXT, body TEXT)")
    con.execute("CREATE VIRTUAL TABLE phoenix_records_fts USING fts5(subject, body,"
               " content='phoenix_records', content_rowid='id')")
    con.execute("""CREATE TRIGGER phoenix_records_ai AFTER INSERT ON phoenix_records BEGIN
      INSERT INTO phoenix_records_fts(rowid, subject, body) VALUES (new.id, new.subject, new.body);
    END""")
    con.execute("""CREATE TRIGGER phoenix_records_ad AFTER DELETE ON phoenix_records BEGIN
      INSERT INTO phoenix_records_fts(phoenix_records_fts, rowid, subject, body)
        VALUES('delete', old.id, old.subject, old.body);
    END""")
    con.execute("""CREATE TRIGGER phoenix_records_au AFTER UPDATE ON phoenix_records BEGIN
      INSERT INTO phoenix_records_fts(phoenix_records_fts, rowid, subject, body)
        VALUES('delete', old.id, old.subject, old.body);
      INSERT INTO phoenix_records_fts(rowid, subject, body) VALUES (new.id, new.subject, new.body);
    END""")
    rows = [
        ("CORE", "тема1", f"{RARE} встречается один раз"),
        ("ING", "subject2", f"{LATIN} appears in plain english text"),
        ("TAXO", "тема3", f"{CYRILLIC} и обычный русский текст рядом"),
        ("COORD", "тема4", f"{YO_WORD} слово с буквой ё внутри"),
        ("PROTO", "тема5", f"{FREQUENT} тут и {FREQUENT} там и ещё раз {FREQUENT}"),
        ("OPSSRE", "тема6", f"просто заполняющий текст без особых слов, {FREQUENT} тоже здесь"),
    ]
    con.executemany("INSERT INTO phoenix_records (role, subject, body) VALUES (?,?,?)", rows)
    con.execute("CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, body TEXT)")
    con.executemany("INSERT INTO phoenix_history (body) VALUES (?)",
                    [(f"версия {i} " + "х" * 40,) for i in range(15)])
    con.execute("CREATE TABLE read_batches (id INTEGER PRIMARY KEY, token TEXT)")
    con.executemany("INSERT INTO read_batches (token) VALUES (?)", [(f"t{i}",) for i in range(6)])
    con.commit()
    con.close()
    return db


def build_selfcontained_stand(d: pathlib.Path) -> pathlib.Path:
    """FTS5 БЕЗ внешнего содержимого — текст хранится в самой таблице поиска. Случай С4."""
    d.mkdir(parents=True, exist_ok=True)
    db = d / "selfcontained.db"
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE notes_fts USING fts5(body)")
    con.execute("INSERT INTO notes_fts(rowid, body) VALUES (1, 'самодостаточная таблица поиска')")
    con.execute("INSERT INTO notes_fts(rowid, body) VALUES (2, 'текста нигде больше нет')")
    con.commit()
    con.close()
    return db


def build_plain_stand(d: pathlib.Path) -> pathlib.Path:
    """Без таблицы поиска вовсе — случай С7а(в): таблица поиска, пропавшая из прежней
    шапки, должна пропасть и из ТЕКУЩЕЙ базы, чтобы сверить оба случая честно."""
    d.mkdir(parents=True, exist_ok=True)
    db = d / "plain.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, body TEXT)")
    con.executemany("INSERT INTO phoenix_history (body) VALUES (?)",
                    [(f"версия {i}",) for i in range(15)])
    con.execute("CREATE TABLE read_batches (id INTEGER PRIMARY KEY, token TEXT)")
    con.executemany("INSERT INTO read_batches (token) VALUES (?)", [(f"t{i}",) for i in range(6)])
    con.commit()
    con.close()
    return db


def write_previous_header(path: pathlib.Path, counts: dict, pad_bytes: int = 0):
    """Сымитировать шапку счётчиков, какую писала СТАРАЯ версия backup-db.py
    (случай С7а — переход через таблицу поиска в шапке).

    pad_bytes>0 — имитирует то, что СТАРАЯ версия писала строки таблицы поиска
    построчно (файл был заметно больше новой выгрузки) — случай С7а(г)."""
    lines = ["-- mezosync.db — текстовый дамп для git-восстановимости",
             "-- снят: 2026-09-01 00:00:00 UTC (имитация старой версии)",
             "-- источник: имитация",
             "-- восстановление: sqlite3 new.db < этот_файл",
             "-- строк по таблицам: " + ", ".join(f"{t}={n}" for t, n in counts.items()),
             "", "BEGIN TRANSACTION;"]
    if pad_bytes:
        lines.append("-- имитация построчных INSERT таблицы поиска старой версии: "
                    + "х" * pad_bytes)
    lines += ["COMMIT;", ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_no_search_stand(dst: pathlib.Path) -> pathlib.Path:
    """Копия живой базы, из которой сняты таблицы поиска и их триггеры. Случай С3.

    🩸 ЗДЕСЬ СТОЯЛ разворот выгрузки 05.09 прямо из atlas.agents-sync.db. 14.09 туда легла
    новая выгрузка — уже С таблицей поиска, — и случай С3 молча перестал бы проверять то,
    что названо в его имени, оставаясь зелёным. Стенд теперь строится сам и не зависит
    от того, какая выгрузка сейчас лежит в зеркале.
    """
    snapshot_live(dst)
    con = sqlite3.connect(dst)
    try:
        virtual = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE 'CREATE VIRTUAL TABLE%'")]
        for name in virtual:
            for (trig,) in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND sql LIKE ?",
                    (f"%{name}%",)).fetchall():
                con.execute(f'DROP TRIGGER "{trig}"')
            con.execute(f'DROP TABLE "{name}"')
        con.commit()
    finally:
        con.close()
    return dst


def snapshot_live(dst: pathlib.Path) -> pathlib.Path:
    """Копия живой базы через штатный backup() — источник открыт ТОЛЬКО НА ЧТЕНИЕ."""
    src = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    d = sqlite3.connect(str(dst))
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dst


# ── С1/С2: копия живой базы ─────────────────────────────────────────────

def case_c1_c2(d: pathlib.Path, out_dir: pathlib.Path):
    live_copy = d / "live-copy.db"
    t0 = time.time()
    snapshot_live(live_copy)
    t_snapshot = time.time() - t0

    out_sql = d / "live.dump.sql"
    t0 = time.time()
    code, output = run_tool(live_copy, out_sql, "--apply", "--verify")
    t_backup = time.time() - t0
    (out_dir / "c1-backup-run.txt").write_text(output, encoding="utf-8")
    case("С1 копия живой базы · --apply --verify → код 0",
         code == 0, f"код {code}; время снятия копии {t_snapshot:.2f} с,"
                    f" время backup-db.py {t_backup:.2f} с (файл ~65 МБ)", differ=True)

    restored = d / "live-restored.db"
    t0 = time.time()
    r = subprocess.run([sys.executable, str(RESTORE_VERIFY), "--dump", str(out_sql),
                        "--out", str(restored)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    t_restore_verify = time.time() - t0
    routput = (r.stdout or "") + (r.stderr or "")
    (out_dir / "c1-restore-verify.txt").write_text(routput, encoding="utf-8")
    case("С1 restore-verify.py на развёрнутой копии → зелёная сверка ролей",
         r.returncode == 0 and "СВЕРКА ЗЕЛЁНАЯ" in routput,
         f"код {r.returncode}, время {t_restore_verify:.2f} с; строка со счётом ролей — в файле", differ=True)

    # независимая сверка строк по обычным таблицам источник↔копия (кроме служебных поиска)
    src = sqlite3.connect(f"file:{live_copy}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
    tables = [r0[0] for r0 in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        " AND name NOT LIKE 'phoenix_records_fts%'")]
    mismatches = []
    for t in tables:
        a = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        b = dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if a != b:
            mismatches.append(f"{t}: источник {a} ≠ копия {b}")
    case("С1 независимая сверка строк по обычным таблицам (не через backup-db.py)",
         not mismatches, f"таблиц сверено {len(tables)}; расхождений {len(mismatches)}"
                         + (": " + "; ".join(mismatches[:5]) if mismatches else ""), differ=True)

    # integrity-check таблицы поиска на развёрнутой копии
    try:
        dst2 = sqlite3.connect(str(restored))
        dst2.execute("INSERT INTO phoenix_records_fts(phoenix_records_fts) VALUES('integrity-check')")
        integ_ok = True
        integ_msg = "прошёл"
    except sqlite3.Error as exc:
        integ_ok = False
        integ_msg = str(exc)
    case("С1 integrity-check таблицы поиска на развёрнутой копии",
         integ_ok, integ_msg, differ=True)

    # ── С2: триггеры живы после разворота ──
    dst2.execute("""INSERT INTO phoenix_records (role, section, subject, body, body_chars, created_by)
                    VALUES ('PROTO','test','с610проверкатриггеров','словодляновойзаписи610',10,'PROTO')""")
    dst2.commit()
    ins_id = dst2.execute(
        "SELECT id FROM phoenix_records WHERE subject='с610проверкатриггеров'").fetchone()[0]
    after_insert = dst2.execute(
        "SELECT rowid FROM phoenix_records_fts WHERE phoenix_records_fts MATCH 'словодляновойзаписи610'"
    ).fetchall()
    dst2.execute("UPDATE phoenix_records SET body='совершенноиноетекстовоесодержимое610' WHERE id=?",
                (ins_id,))
    dst2.commit()
    old_gone = dst2.execute(
        "SELECT rowid FROM phoenix_records_fts WHERE phoenix_records_fts MATCH 'словодляновойзаписи610'"
    ).fetchall()
    new_found = dst2.execute(
        "SELECT rowid FROM phoenix_records_fts WHERE phoenix_records_fts MATCH 'совершенноиноетекстовоесодержимое610'"
    ).fetchall()
    dst2.execute("DELETE FROM phoenix_records WHERE id=?", (ins_id,))
    dst2.commit()
    del_gone = dst2.execute(
        "SELECT rowid FROM phoenix_records_fts WHERE phoenix_records_fts MATCH 'совершенноиноетекстовоесодержимое610'"
    ).fetchall()
    case("С2 триггеры после восстановления копии: INSERT находится, UPDATE меняет, DELETE убирает",
         len(after_insert) == 1 and old_gone == [] and len(new_found) == 1 and del_gone == [],
         f"insert={after_insert}, после update старое={old_gone} новое={new_found}, после delete={del_gone}",
         differ=True)
    dst2.close()
    src.close()
    dst.close()
    return live_copy, out_sql   # возвращаем для повторного использования поломками, если нужно


# ── С3: база без таблицы поиска ─────────────────────────────────────────

def case_c3(d: pathlib.Path, out_dir: pathlib.Path):
    no_fts_db = build_no_search_stand(d / "no-fts.db")
    con = sqlite3.connect(f"file:{no_fts_db}?mode=ro", uri=True)
    left = con.execute("SELECT count(*) FROM sqlite_master WHERE sql LIKE 'CREATE VIRTUAL TABLE%'").fetchone()[0]
    con.close()
    out_sql = d / "no-fts.dump.sql"
    code, output = run_tool(no_fts_db, out_sql, "--apply", "--verify")
    (out_dir / "c3-backup-run.txt").write_text(output, encoding="utf-8")
    case("С3 база БЕЗ таблицы поиска (копия живой, поиск снят) · --apply --verify → код 0",
         code == 0 and left == 0, f"код {code}; таблиц поиска в стенде {left}", differ=True)

    restored = d / "no-fts-restored.db"
    r = subprocess.run([sys.executable, str(RESTORE_VERIFY), "--dump", str(out_sql),
                        "--out", str(restored)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    routput = (r.stdout or "") + (r.stderr or "")
    (out_dir / "c3-restore-verify.txt").write_text(routput, encoding="utf-8")
    case("С3 restore-verify.py на развёрнутой (без поиска) → зелёная сверка ролей",
         r.returncode == 0 and "СВЕРКА ЗЕЛЁНАЯ" in routput,
         f"код {r.returncode}; строка со счётом ролей — в файле c3-restore-verify.txt", differ=True)


# ── С9: знак CR в значении переживает нормализацию концов строк в git ────
# Находка PROTO 2026-09-14 09:40 UTC (карточка #610): в atlas.agents-sync.db стоит
# `*.sql text eol=lf`, git при коммите меняет CRLF на LF во всём файле, и один комментарий
# карточки в живой базе (37 знаков CR) доезжал до удалёнки без них. Случай имитирует ровно
# то, что делает git, — CRLF → LF по всему файлу, — и разворачивает результат.

CR_VALUE = "строка первая\r\nстрока вторая\rодинокий CR\nодинокий LF"


def build_cr_stand(d: pathlib.Path) -> pathlib.Path:
    d.mkdir(parents=True, exist_ok=True)
    db = d / "cr.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("INSERT INTO notes (id, body) VALUES (1, ?)", (CR_VALUE,))
    con.execute("INSERT INTO notes (id, body) VALUES (2, 'без знака CR')")
    con.commit()
    con.close()
    return db


def run_c9(d: pathlib.Path, out_dir: pathlib.Path, tool=TOOL, label="c9"):
    """→ (код backup-db.py, сырых CR в файле, значение id=1 после «git» и разворота)."""
    db = build_cr_stand(d)
    out_sql = d / "cr.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=tool)
    (out_dir / f"{label}-run.txt").write_text(output, encoding="utf-8")
    raw = out_sql.read_bytes() if out_sql.exists() else b""
    normalized = raw.replace(b"\r\n", b"\n")        # что делает git с eol=lf при коммите
    restored = d / "cr-restored.db"
    restored.unlink(missing_ok=True)
    con = sqlite3.connect(restored)
    try:
        con.executescript(normalized.decode("utf-8"))
        row = con.execute("SELECT body FROM notes WHERE id=1").fetchone()
        got = row[0] if row else None
    except sqlite3.Error as exc:
        got = f"<разворот не выполнился: {exc}>"
    finally:
        con.close()
    return code, raw.count(b"\r"), got


def case_c9(d: pathlib.Path, out_dir: pathlib.Path):
    code, cr_in_file, got = run_c9(d, out_dir)
    case("С9 знак CR в значении: сырых CR в выгрузке нет, после замены CRLF→LF (как git"
         " с eol=lf) значение разворачивается тем же",
         code == 0 and cr_in_file == 0 and got == CR_VALUE,
         f"код {code}; сырых CR в файле {cr_in_file}; значение после восстановления "
         + ("равно исходному" if got == CR_VALUE else f"ДРУГОЕ: {got!r}"), differ=True)


def case_c9_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(d, "kept.append(escape_carriage_returns(stmt))", "kept.append(stmt)",
                  "no-cr-escape")
    if weak is None:
        case("П-С9 обратный ход: без замены CR значение теряет CR", False,
             "якорь «kept.append(escape_carriage_returns(stmt))» не найден — инструмент поменялся")
        return
    code, cr_in_file, got = run_c9(d, out_dir, tool=weak, label="p-c9")
    case("П-С9 обратный ход: без замены CR в выгрузке сырые CR, после замены CRLF→LF"
         " значение ДРУГОЕ (случай С9 краснеет)",
         cr_in_file > 0 and got != CR_VALUE,
         f"код {code}; сырых CR в файле {cr_in_file}; значение {got!r}", differ=True)


# ── С10: подсказка «Дальше» — про фактическую папку выгрузки, не про наш контур ──
# 🩸 Находка tapas 2026-09-14 11:24 UTC: строка после выгрузки называла atlas.agents-sync.db
# и наше право отправки «без отдельного слова». У них такого хранилища нет, право отправки
# поимённое, а инструмент приехал к ним из пакета. Два исхода — папка вне git и папка
# внутри git-репозитория; в обоих ни имени нашего хранилища, ни пересказа нашего права.

OUR_REPO_NAME = "atlas.agents-sync.db"
OUR_PUSH_RIGHT = "без отдельного слова"


def run_c10(d: pathlib.Path, out_dir: pathlib.Path, tool=TOOL, label="c10"):
    """→ {исход: (код, строка «Дальше…» или None)} для папки вне git и папки в git."""
    results = {}
    plain = d / "plain"
    db = build_cr_stand(plain)
    code, output = run_tool(db, plain / "x.dump.sql", "--apply", script=tool)
    (out_dir / f"{label}-plain-run.txt").write_text(output, encoding="utf-8")
    results["plain"] = (code, output, plain)
    repo = d / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True, text=True)
    inner = repo / "dumps"
    db2 = build_cr_stand(inner)
    code2, output2 = run_tool(db2, inner / "x.dump.sql", "--apply", script=tool)
    (out_dir / f"{label}-repo-run.txt").write_text(output2, encoding="utf-8")
    results["repo"] = (code2, output2, repo)
    return results


def _hint_line(output: str):
    return next((ln for ln in output.splitlines() if ln.startswith("Дальше:")), None)


def case_c10(d: pathlib.Path, out_dir: pathlib.Path):
    res = run_c10(d, out_dir)
    code_p, out_p, plain = res["plain"]
    code_r, out_r, repo = res["repo"]
    hint_p, hint_r = _hint_line(out_p), _hint_line(out_r)
    foreign = [h for h in (hint_p, hint_r) if h and (OUR_REPO_NAME in h or OUR_PUSH_RIGHT in h)]
    plain_ok = (code_p == 0 and hint_p is not None and "не в git-репозитории" in hint_p
                and str(plain.resolve()) in hint_p)
    repo_ok = (code_r == 0 and hint_r is not None and str(repo.resolve()) in hint_r
               and "x.dump.sql" in hint_r and "правилам отправки вашего контура" in hint_r)
    case("С10 подсказка «Дальше» называет ФАКТИЧЕСКУЮ папку выгрузки: вне git — «не в"
         " git-репозитории», в git — сам репозиторий; нашего хранилища и нашего права в ней нет",
         plain_ok and repo_ok and not foreign,
         f"вне git: код {code_p}, строка {hint_p!r}\n   в git: код {code_r}, строка {hint_r!r}",
         differ=True)


def case_c10_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(d, 'print("\\n" + next_step_hint(out))',
                  'print("\\nДальше: закоммить выгрузку в atlas.agents-sync.db поимённо и отправить"'
                  ' " (push разрешён без отдельного слова; сверь состав ВЕТКИ перед отправкой)")',
                  "old-hint")
    if weak is None:
        case("П-С10 обратный ход: прежняя строка «Дальше» — случай С10 проваливается", False,
             "якорь «print(\"\\n\" + next_step_hint(out))» не найден — инструмент поменялся")
        return
    res = run_c10(d, out_dir, tool=weak, label="p-c10")
    hint = _hint_line(res["plain"][1])
    case("П-С10 обратный ход: прежняя строка «Дальше» снова называет наше хранилище и наше"
         " право — случай С10 проваливается",
         hint is not None and OUR_REPO_NAME in hint and OUR_PUSH_RIGHT in hint,
         f"строка {hint!r}", differ=True)


# ── С4: таблица поиска, хранящая текст в себе ───────────────────────────

def run_c4_scenario(d: pathlib.Path, out_dir: pathlib.Path, tool=TOOL, label="С4"):
    db = build_selfcontained_stand(d / "sc")
    out_sql = d / "sc.dump.sql"
    out_sql.write_text("-- прежняя годная выгрузка, трогать нельзя\n", encoding="utf-8")
    before = out_sql.read_bytes()
    code, output = run_tool(db, out_sql, "--apply", script=tool)
    (out_dir / f"{label.lower()}-run.txt").write_text(output, encoding="utf-8")
    after = out_sql.read_bytes()
    return code, output, before == after


def case_c4_main(d: pathlib.Path, out_dir: pathlib.Path):
    code, output, unchanged = run_c4_scenario(d, out_dir)
    case("С4 таблица поиска с содержимым В СЕБЕ → отказ ДО записи, файл не тронут",
         code != 0 and "перестроить нечем" in output and "НЕ ЗАПИСАНА" in output and unchanged,
         f"код {code}; файл выгрузки не изменился: {unchanged}", differ=True)


# ── С5/С6: механика «пишем-после-проверки» и уборка временной базы ─────

def case_c5_c6(d: pathlib.Path, out_dir: pathlib.Path):
    mod = load_tool_module(TOOL, "backup_db_c5c6")
    stand = build_rich_stand(d / "wv")
    conn = sqlite3.connect(stand)

    # Строим ДЕЙСТВИТЕЛЬНО восстановимую выгрузку — той же функцией, что и main()
    # (сырой iterdump() на базе с виртуальной таблицей САМ по себе не восстановим —
    # это и есть исходная беда карточки #610, тут её проверять незачем).
    virtual_sql = mod.find_virtual_tables(conn)
    shadow_names = mod.find_shadow_tables(conn, virtual_sql)
    all_tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    real_tables = [t for t in all_tables if t not in virtual_sql and t not in shadow_names]
    counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in real_tables}
    good_lines = mod.filter_dump_statements(conn, virtual_sql, shadow_names)
    good_dump = "\n".join(good_lines) + "\n"
    victim = "phoenix_history"
    bad_lines = [l for l in good_lines if mod.statement_table_name(l) != victim]
    bad_dump = "\n".join(bad_lines) + "\n"

    out_path = d / "target.sql"
    prior = b"-- prior good dump, must survive a failed verify\n"
    out_path.write_bytes(prior)
    verify_db = out_path.parent / "_verify.db"

    ok5, outcome5 = mod.write_and_verify(conn, bad_dump, counts, virtual_sql, out_path, True)
    after5 = out_path.read_bytes()
    case("С5 испорченная выгрузка (нет CREATE одной таблицы) → «копия негодна», файл не тронут",
         (not ok5) and outcome5.startswith("копия негодна:") and after5 == prior
         and not verify_db.exists(),
         f"ok={ok5}, исход: {outcome5!r}; файл не тронут: {after5 == prior};"
         f" _verify.db остался: {verify_db.exists()}", differ=True)

    ok6, outcome6 = mod.write_and_verify(conn, good_dump, counts, virtual_sql, out_path, True)
    after6 = out_path.read_bytes()
    case("С6 удачный разворот → файл заменён, _verify.db не остался",
         ok6 and outcome6.startswith("копия разворачивается:") and after6 == good_dump.encode("utf-8")
         and not verify_db.exists(),
         f"ok={ok6}, исход: {outcome6!r}; _verify.db остался: {verify_db.exists()}", differ=True)

    conn.close()
    return stand, counts, virtual_sql, good_dump, bad_dump   # для П4


# ── С7: служебные таблицы поиска не судятся по числу строк ─────────────

def case_c7(d: pathlib.Path, out_dir: pathlib.Path):
    db = build_rich_stand(d / "c7")
    out_sql = d / "c7.dump.sql"
    code0, output0 = run_tool(db, out_sql, "--apply")
    if code0 != 0:
        case("С7 базовая выгрузка стенда не снялась", False, output0)
        return

    header = out_sql.read_text(encoding="utf-8").splitlines()[4]
    case("С7 шапка счётчиков не содержит служебные/виртуальную таблицы поиска",
         header.startswith("-- строк по таблицам: ") and "phoenix_records_fts" not in header,
         f"шапка: {header}", differ=True)

    con = sqlite3.connect(db)
    # МНОГО вставок+удалений + явное слияние сегментов — по-настоящему меняет
    # раскладку служебных таблиц поиска (_data/_idx) против исходной. Сверке шапки
    # это видеть не положено — она эти таблицы вообще не считает (проверено выше);
    # здесь смотрим, что и живой прогон после такой перестройки не тревожится.
    for i in range(60):
        con.execute("INSERT INTO phoenix_records (role, subject, body) VALUES (?,?,?)",
                   ("ING", f"тема-доп-{i}", f"заполняющий текст номер {i} для слияния сегментов"))
    con.commit()
    con.execute("INSERT INTO phoenix_records_fts(phoenix_records_fts, rank) VALUES('merge', 400)")
    con.execute("DELETE FROM phoenix_records WHERE subject LIKE 'тема-доп-%'")
    con.commit()
    con.execute("INSERT INTO phoenix_records_fts(phoenix_records_fts, rank) VALUES('merge', 400)")
    con.commit()
    data_after_churn = con.execute("SELECT COUNT(*) FROM phoenix_records_fts_data").fetchone()[0]
    # законная убыль рядом — история версий чистится штатно
    con.execute("DELETE FROM phoenix_history WHERE id <= 8")
    con.commit()
    con.close()

    code1, output1 = run_tool(db, out_sql, "--apply")
    (out_dir / "c7-second-run.txt").write_text(output1, encoding="utf-8")

    case("С7 после реальной перестройки индекса поиска — тревоги о служебных таблицах нет",
         code1 == 0 and "phoenix_records_fts" not in output1.split("Цель:")[-1].split("копия")[0],
         f"код {code1}; _data после перестройки: {data_after_churn} строк"
         " (это к сверке шапки не относится — она их не считает вовсе)", differ=True)
    case("С7 законная убыль phoenix_history рядом с поиском по-прежнему признаётся",
         "ЗАКОННО" in output1 and "phoenix_history" in output1 and "🔴" not in output1,
         "строка «ЗАКОННО» и имя таблицы — в c7-second-run.txt", differ=True)


# ── С7а: ПЕРЕХОД — прежняя шапка снята СТАРОЙ версией (несёт таблицу поиска
#        и служебные в счёте) — находка COORD, карточка #610 ───────────────

def case_c7a_a(d: pathlib.Path, out_dir: pathlib.Path, tool=TOOL, label="c7a-a"):
    """(а) прежняя шапка старой версии (поиск + служебные в счёте) → тревоги нет."""
    db = build_rich_stand(d / "stand")
    con = sqlite3.connect(db)
    old_counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                 for t in ("phoenix_history", "phoenix_records", "read_batches")}
    con.close()
    old_counts.update({"phoenix_records_fts": 444, "phoenix_records_fts_data": 10,
                       "phoenix_records_fts_idx": 4, "phoenix_records_fts_docsize": 6,
                       "phoenix_records_fts_config": 1})
    out_sql = d / "out.sql"
    write_previous_header(out_sql, old_counts)
    code, output = run_tool(db, out_sql, "--apply", script=tool)
    (out_dir / f"{label}-run.txt").write_text(output, encoding="utf-8")
    return code, output


def case_c7a_a_main(d: pathlib.Path, out_dir: pathlib.Path):
    code, output = case_c7a_a(d, out_dir)
    case("С7а(а) прежняя шапка старой версии (поиск+служебные) → тревоги нет, код 0,"
         " строка объяснения есть",
         code == 0 and "🔴" not in output and "ИСЧЕЗЛА" not in output
         and "теперь сверяются выдачей" in output,
         f"код {code}; полный вывод — c7a-a-run.txt", differ=True)


def case_c7a_b(d: pathlib.Path, out_dir: pathlib.Path):
    """(б) КОНТРОЛЬ: обычная таблица из прежней шапки пропала из базы → тревога есть."""
    db = build_rich_stand(d / "stand")
    con = sqlite3.connect(db)
    old_counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                 for t in ("phoenix_history", "phoenix_records", "read_batches")}
    con.close()
    old_counts["some_removed_table"] = 99
    out_sql = d / "out.sql"
    write_previous_header(out_sql, old_counts)
    code, output = run_tool(db, out_sql, "--apply")
    (out_dir / "c7a-b-run.txt").write_text(output, encoding="utf-8")
    case("С7а(б) КОНТРОЛЬ: обычная таблица из прежней шапки пропала из базы → тревога есть",
         code != 0 and "some_removed_table" in output and "ИСЧЕЗЛА" in output,
         f"код {code}; полный вывод — c7a-b-run.txt", differ=True)


def case_c7a_c(d: pathlib.Path, out_dir: pathlib.Path):
    """(в) таблица поиска из прежней шапки пропала из ТЕКУЩЕЙ базы вместе со
    служебными → тревога есть (это смена схемы, не переход версии)."""
    db = build_plain_stand(d / "stand")
    old_counts = {"phoenix_history": 15, "read_batches": 6,
                 "phoenix_records_fts": 444, "phoenix_records_fts_data": 10,
                 "phoenix_records_fts_idx": 4, "phoenix_records_fts_docsize": 6,
                 "phoenix_records_fts_config": 1}
    out_sql = d / "out.sql"
    write_previous_header(out_sql, old_counts)
    code, output = run_tool(db, out_sql, "--apply")
    (out_dir / "c7a-c-run.txt").write_text(output, encoding="utf-8")
    case("С7а(в) таблица поиска пропала из ТЕКУЩЕЙ базы вместе со служебными → тревога есть",
         code != 0 and "phoenix_records_fts" in output and "ИСЧЕЗЛА" in output,
         f"код {code}; полный вывод — c7a-c-run.txt", differ=True)


def case_c7a_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    """Обратный ход: исключение по текущим таблицам поиска снято → случай С7а(а)
    проваливается ПО СВОЕЙ причине («ИСЧЕЗЛА»)."""
    weak = weaken(
        d,
        '    for t, was in previous.items():\n'
        '        if t in search_related_names:\n'
        '            search_note = SEARCH_HEADER_NOTE\n'
        '            continue\n'
        '        now = counts.get(t)',
        '    for t, was in previous.items():\n'
        '        if False and t in search_related_names:  # П-С7а: исключение снято\n'
        '            search_note = SEARCH_HEADER_NOTE\n'
        '            continue\n'
        '        now = counts.get(t)',
        "c7a")
    if weak is None:
        case("П-С7а обратный ход: исключение по текущим таблицам поиска снято", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь не найден — гард менялся, правь приёмку")
        return
    code, output = case_c7a_a(d, out_dir, tool=weak, label="p-c7a")
    case("П-С7а обратный ход: без исключения случай С7а(а) КРАСНЕЕТ по «ИСЧЕЗЛА»",
         code != 0 and "ИСЧЕЗЛА" in output and "phoenix_records_fts" in output,
         f"код {code}; полный вывод — p-c7a-run.txt", differ=True)


def case_c7a_d(d: pathlib.Path, out_dir: pathlib.Path, tool=TOOL, label="c7a-d"):
    """(г) ВТОРОЙ СЛЕД перехода (находка PROTO): прежняя выгрузка старого образца —
    шапка с таблицами поиска, ФАЙЛ БОЛЬШЕ новой (старая версия писала их построчно)."""
    db = build_rich_stand(d / "stand")
    con = sqlite3.connect(db)
    old_counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                 for t in ("phoenix_history", "phoenix_records", "read_batches")}
    con.close()
    old_counts.update({"phoenix_records_fts": 444, "phoenix_records_fts_data": 10,
                       "phoenix_records_fts_idx": 4, "phoenix_records_fts_docsize": 6,
                       "phoenix_records_fts_config": 1})
    out_sql = d / "out.sql"
    write_previous_header(out_sql, old_counts, pad_bytes=200_000)   # заведомо больше новой
    code, output = run_tool(db, out_sql, "--apply", script=tool)
    (out_dir / f"{label}-run.txt").write_text(output, encoding="utf-8")
    return code, output


def case_c7a_d_main(d: pathlib.Path, out_dir: pathlib.Path):
    code, output = case_c7a_d(d, out_dir)
    case("С7а(г) прежняя выгрузка старого образца БОЛЬШЕ новой → без «записи стали"
         " короче», есть строка про таблицы поиска",
         code == 0 and "записи стали короче" not in output
         and "выгрузка меньше: таблицы поиска" in output,
         f"код {code}; полный вывод — c7a-d-run.txt", differ=True)


def case_c7a_d_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    """Обратный ход: различение байтовой убыли снято → случай С7а(г) проваливается
    ПО СВОЕЙ причине («записи стали короче»)."""
    weak = weaken(
        d,
        '    elif search_note and delta < 0:\n'
        '        # см. SEARCH_SIZE_SHRINK_NOTE выше: та же причина, что у search_note,\n'
        '        # объясняет и байтовую убыль — «взгляни глазами» здесь была бы ложной тревогой.\n'
        '        print(f"  ℹ️  {SEARCH_SIZE_SHRINK_NOTE}")\n'
        '    elif old_size and delta < 0:',
        '    elif old_size and delta < 0:  # П-С7а(г): различение байтовой убыли снято',
        "c7a-d")
    if weak is None:
        case("П-С7а(г) обратный ход: различение байтовой убыли снято", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь не найден — гард менялся, правь приёмку")
        return
    code, output = case_c7a_d(d, out_dir, tool=weak, label="p-c7a-d")
    case("П-С7а(г) обратный ход: без различения случай (г) КРАСНЕЕТ по «записи стали короче»",
         "записи стали короче" in output,
         f"код {code}; полный вывод — p-c7a-d-run.txt", differ=True)


# ── СF: замечание COORD — сбой restore_and_check НЕ sqlite3.Error не должен
#        оставлять временный файл и не должен превращаться в трассировку ──────

def case_cf(d: pathlib.Path, out_dir: pathlib.Path):
    """Подменяем restore_and_check так, чтобы бросал OSError → «копия негодна»,
    временного файла нет, цель байт в байт та же."""
    mod = load_tool_module(TOOL, "backup_db_cf")
    stand = build_rich_stand(d / "stand")
    conn = sqlite3.connect(stand)
    out_path = d / "target.sql"
    prior = b"-- prior good dump, must survive a non-sqlite3.Error failure\n"
    out_path.write_bytes(prior)

    def boom(*a, **k):
        raise OSError("испытание: диск недоступен")
    mod.restore_and_check = boom

    ok, outcome = mod.write_and_verify(conn, "BEGIN;COMMIT;", {"t": 0}, {}, out_path, True)
    after = out_path.read_bytes()
    tmp = out_path.parent / (out_path.name + ".tmp")
    conn.close()
    case("СF сбой НЕ sqlite3.Error (OSError) → «копия негодна», временного файла нет,"
         " цель не тронута",
         (not ok) and outcome.startswith("копия негодна: OSError") and after == prior
         and not tmp.exists(),
         f"ok={ok}, исход={outcome!r}; файл не тронут: {after == prior};"
         f" .tmp остался: {tmp.exists()}", differ=True)


def case_cf_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    """Обратный ход: finally снят → при сбое НЕ sqlite3.Error временный файл остаётся."""
    # Якорь — только сам блок finally: 14.09 строка чтения выше него поменялась
    # (чтение без свёртки концов строк, случай С9), и якорь, державшийся за неё,
    # перестал находиться — поломка молча не запускалась бы.
    weak = weaken(
        d,
        '        finally:\n'
        '            if not ok:\n'
        '                tmp_sql.unlink(missing_ok=True)\n'
        '        if not ok:\n'
        '            return False, outcome',
        '        # П-finally: уборка временного файла снята\n'
        '        if not ok:\n'
        '            return False, outcome',
        "cf")
    if weak is None:
        case("П-finally обратный ход: уборка временного файла снята", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь не найден — гард менялся, правь приёмку")
        return
    mod = load_tool_module(weak, "backup_db_cf_weak")
    stand = build_rich_stand(d / "stand")
    conn = sqlite3.connect(stand)
    out_path = d / "target.sql"
    prior = b"-- prior good dump\n"
    out_path.write_bytes(prior)

    def boom(*a, **k):
        raise OSError("испытание: диск недоступен")
    mod.restore_and_check = boom

    ok, outcome = mod.write_and_verify(conn, "BEGIN;COMMIT;", {"t": 0}, {}, out_path, True)
    tmp = out_path.parent / (out_path.name + ".tmp")
    conn.close()
    case("П-finally обратный ход: без finally .tmp остаётся при сбое НЕ sqlite3.Error",
         tmp.exists(),
         f"ok={ok}, tmp существует: {tmp.exists()} — у верного кода (случай СF) его не"
         " было никогда", differ=True)
    tmp.unlink(missing_ok=True)   # наш тестовый артефакт, не живой контур


# ── СГ: находка PROTO — запись в источник МЕЖДУ счётом и выгрузкой (гонка) ─────
#      backup-db.py срезает источник в память ОДНИМ атомарным чтением (open_snapshot)
#      и дальше работает по срезу — живую базу, которую пишут все роли, отдельные
#      чтения счётчиков и iterdump больше не видят по-разному.

_RACE_COUNTS_ANCHOR = ('    counts = {t: conn.execute(f\'SELECT COUNT(*) FROM "{t}"\').fetchone()[0]'
                       ' for t in real_tables}')
_RACE_INJECTION = (_RACE_COUNTS_ANCHOR + '\n'
    '    _race = sqlite3.connect(args.db)  # ИСПЫТАНИЕ (случай СГ): гонка записи\n'
    '    _race.execute("INSERT INTO phoenix_history (body) VALUES'
    ' (\'гонка записи, испытание СГ\')")\n'
    '    _race.commit()\n'
    '    _race.close()')
_RACE_SNAPSHOT_ANCHOR = ('    conn = open_snapshot(args.db)   # источник открыт mode=ro один раз;'
                         ' дальше — по срезу')
_RACE_SNAPSHOT_REVERT = ('    conn = sqlite3.connect(args.db)  # П-СГ: срез снят,'
                         ' работаем по живому соединению')


def build_race_copy(d: pathlib.Path, label: str, with_snapshot: bool):
    """Копия гарда, куда МЕЖДУ счётом строк и выгрузкой врезана запись в источник
    отдельным соединением. with_snapshot=False дополнительно снимает срез (П-СГ —
    возврат к прежнему прямому соединению) — это и есть сама поломка."""
    original = TOOL.read_text(encoding="utf-8")
    text = original.replace(_RACE_COUNTS_ANCHOR, _RACE_INJECTION, 1)
    if text == original:
        return None
    if not with_snapshot:
        text2 = text.replace(_RACE_SNAPSHOT_ANCHOR, _RACE_SNAPSHOT_REVERT, 1)
        if text2 == text:
            return None
        text = text2
    path = d / f"race-{label}.py"
    path.write_text(text, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    return path


def case_source_race(d: pathlib.Path, out_dir: pathlib.Path):
    fixed = build_race_copy(d, "fixed", with_snapshot=True)
    if fixed is None:
        case("СГ источник: якорь счётчиков строк не найден", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь не найден — гард менялся, правь приёмку")
        return
    db = build_rich_stand(d / "stand-fixed")
    out_sql = d / "fixed.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=fixed)
    (out_dir / "cg-fixed-run.txt").write_text(output, encoding="utf-8")
    case("СГ запись в источник МЕЖДУ счётом и выгрузкой, срез ЕСТЬ →"
         " копия разворачивается, код 0",
         code == 0 and "копия разворачивается" in output,
         f"код {code}; срез в память защитил от гонки; полный вывод — cg-fixed-run.txt",
         differ=True)


def case_source_race_reverse_gate(d: pathlib.Path, out_dir: pathlib.Path):
    """Обратный ход: срез снят (работа по живому соединению) → та же гонка даёт
    «копия негодна» по счёту строк на совершенно здоровой базе."""
    weak = build_race_copy(d, "weak", with_snapshot=False)
    if weak is None:
        case("П-СГ обратный ход: якорь снятия среза не найден", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: гард менялся, правь приёмку")
        return
    db = build_rich_stand(d / "stand-weak")
    out_sql = d / "weak.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=weak)
    (out_dir / "p-cg-run.txt").write_text(output, encoding="utf-8")
    case("П-СГ обратный ход: без среза та же гонка → «копия негодна» по счёту строк",
         code != 0 and "копия негодна" in output and "phoenix_history" in output,
         f"код {code}; полный вывод — p-cg-run.txt", differ=True)


# ── П1: нет 'rebuild' после разворота ───────────────────────────────────

def case_p1(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(
        d,
        '        tail.append(create_sql)\n'
        '        tail.append(f\'INSERT INTO "{name}"("{name}") VALUES(\\\'rebuild\\\');\')',
        '        tail.append(create_sql)\n'
        '        pass  # П1: перестройка индекса нарочно пропущена',
        "p1")
    if weak is None:
        case("П1 нет 'rebuild' после восстановления", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь в гарде не найден — гард менялся, правь приёмку")
        return
    db = build_rich_stand(d / "p1")
    out_sql = d / "p1.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=weak)
    (out_dir / "p1-run.txt").write_text(output, encoding="utf-8")
    case("П1 без 'rebuild' → поиск красный ВЫДАЧЕЙ (пустые наборы), а не по счёту",
         code != 0 and "поиск" in output and "копия негодна" in output,
         f"код {code}; поймано декларацией mismatch по выдаче — строка в p1-run.txt", differ=True)


# ── П2: служебные таблицы сверяются по числу строк ──────────────────────

def case_p2(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(
        d,
        'real_tables = [t for t in all_tables if t not in virtual_sql and t not in shadow_names]',
        'real_tables = [t for t in all_tables if t not in virtual_sql]  # П2: служебные не исключены',
        "p2")
    if weak is None:
        case("П2 служебные таблицы сверяются по числу строк", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь в гарде не найден — гард менялся, правь приёмку")
        return
    db = build_rich_stand(d / "p2")
    out_sql = d / "p2.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=weak)
    (out_dir / "p2-run.txt").write_text(output, encoding="utf-8")
    # для контроля: выдача при этом верна (это ровно та же таблица/данные, что и у С1)
    case("П2 служебные таблицы в счёте → красное ПО СЧЁТУ на здоровой базе (ложная тревога)",
         code != 0 and "копия негодна" in output and "в копии" in output,
         f"код {code}; строка расхождения счёта — в p2-run.txt (свежий rebuild меняет"
         " раскладку _data/_idx против исходной, хотя выдача сошлась бы)", differ=True)


# ── П3: нет проверки вида таблицы поиска ────────────────────────────────

def case_p3(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(
        d,
        '    for name, sql in sorted(virtual_sql.items()):\n'
        '        ok, reason = check_restorable(name, sql)\n'
        '        if not ok:\n'
        '            refusals.append(reason)',
        '    for name, sql in sorted(virtual_sql.items()):\n'
        '        ok, reason = True, None  # П3: проверка вида таблицы поиска пропущена\n'
        '        if not ok:\n'
        '            refusals.append(reason)',
        "p3")
    if weak is None:
        case("П3 нет проверки вида таблицы поиска", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь в гарде не найден — гард менялся, правь приёмку")
        return
    code_good, output_good, _ = run_c4_scenario(d / "good", out_dir, tool=TOOL, label="p3-good")
    code_weak, output_weak, _ = run_c4_scenario(d / "weak", out_dir, tool=weak, label="p3-weak")
    case("П3 без проверки вида → ранний отказ («перестроить нечем») ПРОПАДАЕТ",
         "перестроить нечем" in output_good and "перестроить нечем" not in output_weak
         and code_weak != 0,
         f"верный код {code_good} с текстом отказа; ослабленный код {code_weak} без него"
         " (ловится позже, общей проверкой восстановления, но СВОЯ ранняя строка decision-2 пропала)",
         differ=True)


# ── П4: выгрузка пишется ДО проверки (обратный ход С5) ──────────────────

def case_p4(d: pathlib.Path, out_dir: pathlib.Path, stand, counts, virtual_sql, good_dump, bad_dump):
    weak = weaken(
        d,
        '        tmp_sql.write_text(dump_text, encoding="utf-8", newline="\\n")\n'
        '        verify_db = out.parent / "_verify.db"',
        '        tmp_sql.write_text(dump_text, encoding="utf-8", newline="\\n")\n'
        '        out.write_text(dump_text, encoding="utf-8", newline="\\n")  # П4: пишем ДО проверки\n'
        '        verify_db = out.parent / "_verify.db"',
        "p4")
    if weak is None:
        case("П4 обратный ход С5: выгрузка пишется ДО проверки", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь в гарде не найден — гард менялся, правь приёмку")
        return
    weak_mod = load_tool_module(weak, "backup_db_p4")
    conn = sqlite3.connect(stand)
    out_path = d / "target.sql"
    prior = b"-- prior good dump, must survive a failed verify\n"
    out_path.write_bytes(prior)
    ok, outcome = weak_mod.write_and_verify(conn, bad_dump, counts, virtual_sql, out_path, True)
    after = out_path.read_bytes()
    conn.close()
    case("П4 обратный ход: прежний файл ЗАТЁРТ испорченной выгрузкой (случай С5 краснеет)",
         after != prior,
         f"ok={ok}, исход={outcome!r}; файл {'изменился' if after != prior else 'не изменился'}"
         " — у верного кода (случай С5) он не менялся никогда", differ=True)


# ── П5: соединение с _verify.db не закрыто до unlink ────────────────────

def case_p5(d: pathlib.Path, out_dir: pathlib.Path):
    weak = weaken(
        d,
        '    finally:\n        v.close()\n        verify_db.unlink(missing_ok=True)',
        '    finally:\n        verify_db.unlink(missing_ok=True)  # П5: соединение не закрыто',
        "p5")
    if weak is None:
        case("П5 соединение с _verify.db не закрыто до unlink", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь в гарде не найден — гард менялся, правь приёмку")
        return
    db = build_rich_stand(d / "p5")
    out_sql = d / "p5.dump.sql"
    code, output = run_tool(db, out_sql, "--apply", script=weak)
    (out_dir / "p5-run.txt").write_text(output, encoding="utf-8")
    leftover = out_sql.parent / "_verify.db"  # out.parent для этого прогона
    # ⚠️ ПЕРЕСМОТРЕНО после случая СF (замечание COORD): раньше не закрытое соединение
    # роняло PermissionError НЕПОЙМАННЫМ, и последняя строка была об уборке/трассировке.
    # Теперь write_and_verify ловит ЛЮБОЙ сбой и печатает честный «копия негодна: …» —
    # это ХОРОШО (декларация 6 держится даже здесь), но старый различитель («строка не
    # об исходе») этим снят. Различитель этого случая теперь один: файл ОСТАЁТСЯ на
    # диске (unlink внутри restore_and_check падает на не закрытом соединении раньше,
    # чем успевает убрать файл) — это и есть сама поломка, а не оформление вывода.
    case("П5 не закрытое соединение → _verify.db остаётся на диске",
         leftover.exists() and code != 0 and "_verify.db" in output,
         f"код {code}; _verify.db остался: {leftover.exists()}; полный вывод в p5-run.txt",
         differ=True)
    if leftover.exists():
        leftover.unlink(missing_ok=True)   # это НАШ тестовый артефакт, не живой контур


# ── С8: приёмка ведёт себя правильно (не «живая база не изменилась» — её меняет
#       весь контур, не эта приёмка; см. правку в шапке файла) ──────────────────

CONNECT_LIVE_RE = re.compile(r"sqlite3\.connect\([^)]*LIVE_DB[^)]*\)")


def build_c8_probe_stand(d: pathlib.Path) -> pathlib.Path:
    """Крошечный стенд — только чтобы дать случаю С8 один настоящий вызов backup-db.py
    для проверки. Специально маленький: обратный ход этого случая обязан быть дешёвым."""
    d.mkdir(parents=True, exist_ok=True)
    db = d / "probe.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO t (v) VALUES ('x')")
    con.commit()
    con.close()
    return db


def case_c8_probe(d: pathlib.Path):
    """Один настоящий вызов backup-db.py через обёртку run_tool() — сырьё для
    случая С8(а). Поломка (обратный ход) убирает здесь --db."""
    db = build_c8_probe_stand(d / "probe")
    out = d / "probe.dump.sql"
    run_tool(db, out, "--apply")


def case_c8a_command_hygiene():
    refusals = [e for e in RUN_LOG if e["refused"]]
    case("С8(а) обёртка запуска backup-db.py ни разу не отказала — все вызовы шли"
         " с --db/--out внутри песочницы",
         len(RUN_LOG) > 0 and not refusals,
         f"вызовов всего {len(RUN_LOG)}; отказов {len(refusals)}"
         + ("; " + "; ".join(f"{e['reason']}" for e in refusals) if refusals else ""),
         differ=True)


def case_c8b_no_temp_files_near_live(before, after):
    case("С8(б) рядом с живой базой не появилось новых _verify.db / временных файлов выгрузки",
         after == before,
         f"каталог {LIVE_DB.parent}: до {before}, после {after}", differ=True)


TOOL_CONNECT_SOURCE_RE = re.compile(r"sqlite3\.connect\([^)]*db_path[^)]*\)")


def _no_mode_ro(matches):
    return [m for m in matches
           if "mode=ro" not in m and "mode='ro'" not in m and 'mode="ro"' not in m]


def case_c8c_static_readonly():
    text = pathlib.Path(__file__).resolve().read_text(encoding="utf-8")
    matches = CONNECT_LIVE_RE.findall(text)
    bad = _no_mode_ro(matches)
    case("С8(в) в тексте приёмки нет connect к живому пути без mode=ro (проверено статически)",
         len(matches) >= 1 and not bad,
         f"обращений к LIVE_DB через sqlite3.connect: {len(matches)}; без mode=ro: {len(bad)}",
         differ=True)

    # 🩸 ДОПОЛНЕНО (находка PROTO, карточка #610): backup-db.py сам открывает
    # источник (db_path в open_snapshot) ТОЛЬКО mode=ro и один раз — дальше вся
    # работа по срезу в памяти. Проверяем и это статически, тем же ходом.
    tool_text = TOOL.read_text(encoding="utf-8")
    tool_matches = TOOL_CONNECT_SOURCE_RE.findall(tool_text)
    tool_bad = _no_mode_ro(tool_matches)
    case("С8(в-доп) backup-db.py открывает источник только mode=ro (проверено статически)",
         len(tool_matches) >= 1 and not tool_bad,
         f"обращений к db_path через sqlite3.connect в backup-db.py: {len(tool_matches)};"
         f" без mode=ro: {len(tool_bad)}", differ=True)


def case_c8_reverse_gate(d: pathlib.Path):
    """Обратный ход С8(а): в ослабленной копии ЭТОЙ приёмки пробный вызов
    backup-db.py лишается --db. Обёртка обязана отказать ДО запуска подпроцесса —
    живая база при этом не открывается НИ РАЗУ, даже на чтение (уточнение PROTO)."""
    weak = weaken_self(
        d,
        '    db = build_c8_probe_stand(d / "probe")\n'
        '    out = d / "probe.dump.sql"\n'
        '    run_tool(db, out, "--apply")',
        '    out = d / "probe.dump.sql"\n'
        '    run_tool(None, out, "--apply")  # П-С8: --db нарочно убран',
        "c8")
    if weak is None:
        case("П-С8 обратный ход: --db убран у пробного вызова", False,
             "⛔ НЕ ЗАПУСТИЛАСЬ: якорь пробного вызова в приёмке не найден —"
             " приёмка менялась, правь этот случай")
        return
    run_dir = d / "run"
    r = subprocess.run([sys.executable, str(weak), "--only", "c8",
                        "--tmp", str(run_dir / "tmp"), "--out-dir", str(run_dir / "out")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    output = (r.stdout or "") + (r.stderr or "")
    (d / "p-c8-run.txt").parent.mkdir(parents=True, exist_ok=True)
    (d / "p-c8-run.txt").write_text(output, encoding="utf-8")
    case("П-С8 обратный ход: без --db у пробного вызова случай С8(а) КРАСНЕЕТ",
         "🔴 С8(а)" in output and "отказ" in output.lower(),
         f"код {r.returncode}; живая база при этом не открывалась — обёртка отказала"
         " ДО запуска подпроцесса; полный вывод в p-c8-run.txt", differ=True)


def main() -> int:
    global SANDBOX_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default=None,
                    help="каталог для временных стендов (по умолчанию — временный каталог системы)")
    ap.add_argument("--out-dir", default=None,
                    help="куда сохранять полный вывод прогонов (по умолчанию — рядом с --tmp)")
    ap.add_argument("--only", default="all", choices=["all", "c8"],
                    help="запустить только этот случай — используется обратным ходом"
                         " поломки С8, чтобы не гонять всю приёмку заново")
    args = ap.parse_args()

    made_tmp = args.tmp is None
    tmp_root = pathlib.Path(args.tmp) if args.tmp else pathlib.Path(tempfile.mkdtemp(prefix="bite-backup-restore-"))
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else tmp_root
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.tmp:
        tmp_root.mkdir(parents=True, exist_ok=True)
    SANDBOX_ROOT = tmp_root

    before_listing = _temp_file_listing(LIVE_DB.parent)

    try:
        if args.only == "c8":
            d8 = tmp_root / "c8"; d8.mkdir(parents=True, exist_ok=True)
            case_c8_probe(d8)
        else:
            d1 = tmp_root / "c1c2"; d1.mkdir(parents=True, exist_ok=True)
            case_c1_c2(d1, out_dir)

            d3 = tmp_root / "c3"; d3.mkdir(parents=True, exist_ok=True)
            case_c3(d3, out_dir)

            d9 = tmp_root / "c9"; d9.mkdir(parents=True, exist_ok=True)
            case_c9(d9, out_dir)
            dp9 = tmp_root / "p-c9"; dp9.mkdir(parents=True, exist_ok=True)
            case_c9_reverse_gate(dp9, out_dir)

            d10 = tmp_root / "c10"; d10.mkdir(parents=True, exist_ok=True)
            case_c10(d10, out_dir)
            dp10 = tmp_root / "p-c10"; dp10.mkdir(parents=True, exist_ok=True)
            case_c10_reverse_gate(dp10, out_dir)

            d4 = tmp_root / "c4"; d4.mkdir(parents=True, exist_ok=True)
            case_c4_main(d4, out_dir)

            d56 = tmp_root / "c5c6"; d56.mkdir(parents=True, exist_ok=True)
            stand, counts, virtual_sql, good_dump, bad_dump = case_c5_c6(d56, out_dir)

            d7 = tmp_root / "c7"; d7.mkdir(parents=True, exist_ok=True)
            case_c7(d7, out_dir)

            d7a = tmp_root / "c7a-a"; d7a.mkdir(parents=True, exist_ok=True)
            case_c7a_a_main(d7a, out_dir)
            d7b = tmp_root / "c7a-b"; d7b.mkdir(parents=True, exist_ok=True)
            case_c7a_b(d7b, out_dir)
            d7c = tmp_root / "c7a-c"; d7c.mkdir(parents=True, exist_ok=True)
            case_c7a_c(d7c, out_dir)
            dp7a = tmp_root / "p-c7a"; dp7a.mkdir(parents=True, exist_ok=True)
            case_c7a_reverse_gate(dp7a, out_dir)

            d7d = tmp_root / "c7a-d"; d7d.mkdir(parents=True, exist_ok=True)
            case_c7a_d_main(d7d, out_dir)
            dp7d = tmp_root / "p-c7a-d"; dp7d.mkdir(parents=True, exist_ok=True)
            case_c7a_d_reverse_gate(dp7d, out_dir)

            dcf = tmp_root / "cf"; dcf.mkdir(parents=True, exist_ok=True)
            case_cf(dcf, out_dir)
            dpcf = tmp_root / "p-finally"; dpcf.mkdir(parents=True, exist_ok=True)
            case_cf_reverse_gate(dpcf, out_dir)

            dcg = tmp_root / "cg"; dcg.mkdir(parents=True, exist_ok=True)
            case_source_race(dcg, out_dir)
            dpcg = tmp_root / "p-cg"; dpcg.mkdir(parents=True, exist_ok=True)
            case_source_race_reverse_gate(dpcg, out_dir)

            dp1 = tmp_root / "p1"; dp1.mkdir(parents=True, exist_ok=True)
            case_p1(dp1, out_dir)

            dp2 = tmp_root / "p2"; dp2.mkdir(parents=True, exist_ok=True)
            case_p2(dp2, out_dir)

            dp3 = tmp_root / "p3"; dp3.mkdir(parents=True, exist_ok=True)
            case_p3(dp3, out_dir)

            dp4 = tmp_root / "p4"; dp4.mkdir(parents=True, exist_ok=True)
            case_p4(dp4, out_dir, stand, counts, virtual_sql, good_dump, bad_dump)

            dp5 = tmp_root / "p5"; dp5.mkdir(parents=True, exist_ok=True)
            case_p5(dp5, out_dir)

            d8 = tmp_root / "c8"; d8.mkdir(parents=True, exist_ok=True)
            case_c8_probe(d8)

            dpc8 = tmp_root / "p-c8"; dpc8.mkdir(parents=True, exist_ok=True)
            case_c8_reverse_gate(dpc8)

        after_listing = _temp_file_listing(LIVE_DB.parent)
        case_c8a_command_hygiene()
        case_c8b_no_temp_files_near_live(before_listing, after_listing)
        case_c8c_static_readonly()
    finally:
        if made_tmp:
            shutil.rmtree(tmp_root, ignore_errors=True)

    print()
    ok = BAD == 0 and CASES > 0
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}, неудачных {BAD}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
