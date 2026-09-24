# -*- coding: utf-8 -*-
"""bite-role-sessions.py — приёмка карточки #649: сверка адреса/session_id role_sessions
с хранилищем сессий приложения.

ПРЕДМЕТ ПРИЁМКИ — три звена одной правки:
  · шаг схемы .mezosync/scripts/migrations/20260924-role-sessions-transcript-id.py
  · signal-templates.py — сверка --session-id/--set-address с хранилищем (mezo_sessions.py)
  · guard-role-sessions-live.py — мягкая проверка, что записанный session_id ещё жив

СЛУЧАИ (различающий = приёмка обязана ответить ИНАЧЕ, а не одинаково):
  ① шаг схемы применяется на копии живой базы (уже несущей шаг 20260913)      контроль
  ② повторный прогон шага — «уже сведено», база не тронута                  РАЗЛИЧАЮЩИЙ
  ③ --dry-run шага не меняет базу вовсе                                     РАЗЛИЧАЮЩИЙ
  ④ --session-id ЖИВОЙ сессии → принят, transcript_id ЗАПОЛНЕН САМ           РАЗЛИЧАЮЩИЙ
  ⑤ --session-id АРХИВНОЙ сессии → ОТКАЗ, перечень живых сессий того же cwd  РАЗЛИЧАЮЩИЙ
  ⑥ --session-id, которого в хранилище НЕТ → ОТКАЗ                          РАЗЛИЧАЮЩИЙ
  ⑦ имя адреса НЕ СОВПАДАЕТ с заголовком сессии этого id → ОТКАЗ, назван
    живой заголовок                                                         РАЗЛИЧАЮЩИЙ
  ⑧ только --set-address (без --session-id), РОВНО одна живая сессия того
    же cwd с этим заголовком → принят, id и transcript_id взяты САМИ        РАЗЛИЧАЮЩИЙ
  ⑨ хранилища НЕТ (путь не существует) → принят, ГРОМКАЯ строка «сверить
    нечем», transcript_id НЕ заполняется                                    РАЗЛИЧАЮЩИЙ
  ⑩ guard-role-sessions-live.py: архивный session_id роли — находка поимённо РАЗЛИЧАЮЩИЙ
  ⑪ guard-role-sessions-live.py: живой session_id роли — НЕ находка
    (встречный случай ⑩)                                                    РАЗЛИЧАЮЩИЙ
  ⑫ guard-role-sessions-live.py: хранилища нет → «сверить нечем», а не
    «всё хорошо»                                                            РАЗЛИЧАЮЩИЙ
  ⑬ хранилища НЕТ, у роли ЕСТЬ прежний transcript_id, номер сессии НОВЫЙ →
    transcript_id СБРОШЕН, а не перенесён от прежнего чата (возврат COORD
    по ②, 24.09)                                                            РАЗЛИЧАЮЩИЙ

НАРОЧНЫЕ ПОЛОМКИ (--break; прежнее имя --porcha — синоним), каждая — на СВОЕЙ копии,
живых файлов не касаются:
  drop-archive-check ....... signal-templates.py перестаёт отказывать архивной сессии
                             (проверка `record.archived` снята) → ждём красным РОВНО ⑤,
                             остальные — как на чистом прогоне
  drop-title-check ......... signal-templates.py перестаёт сверять имя адреса с
                             заголовком сессии → ждём красным РОВНО ⑦
  empty-instead-of-missing . mezo_sessions.read_store() у ОТСУТСТВУЮЩЕГО хранилища
                             отвечает НАЙДЕННЫМ ПУСТЫМ (found=True, sessions=())
                             вместо found=False → ждём красным РОВНО ⑨, ⑫ и ⑬: все три
                             места читают хранилище через один и тот же mezo_sessions.py,
                             поломка их не различает
  carry-transcript ......... signal-templates.py снова ПЕРЕНОСИТ прежний transcript_id
                             при смене номера сессии без хранилища → ждём красным РОВНО ⑬
Прогон БЕЗ --break — чистый (ожидается ✅ по всем случаям). Прогон С --break портит
ОДНУ копию перед сборкой стенда и печатает случаи ④–⑫ ещё раз — красные строки этого
прогона сравниваются РУКОЙ (или сверяющим прогоном снаружи) с перечнем выше: поломка
доказана, если красных ровно столько, сколько названо, и не более.

⛔ Живой базы НЕ КАСАЕТСЯ никаким письмом: копия — mezo_stand.snapshot_db (backup API,
не копирование файла — живая база в режиме WAL, копирование файла даёт рваный снимок).
Инструменты стенда зовутся ТОЛЬКО со средой стенда (mezo_stand.stand_env) — без неё
испытуемый signal-templates.py унаследует MEZO_CONTAINER вызывающего и найдёт ЖИВОЙ
контур раньше песочницы. Подложное хранилище сессий — во ВРЕМЕННОМ каталоге приёмки;
реальное хранилище сессий приложения эта приёмка не открывает никогда.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

# ═══ ГДЕ ЖИВОЙ КОНТУР — тем же способом, что у mezo_paths.container_root: переменная
# MEZO_CONTAINER сильнее, иначе выводится от расположения этого файла. Путь машины здесь
# не пишется: в пакете у потребителя он был бы чужим.
import os  # noqa: E402
import mezo_paths  # noqa: E402
LIVE_CONTAINER = Path(mezo_paths.container_root(__file__))
LIVE_DB = LIVE_CONTAINER / ".mezosync" / "mezosync.db"
STEP_FILE = LIVE_CONTAINER / ".mezosync" / "scripts" / "migrations" / \
    "20260924-role-sessions-transcript-id.py"

EXPECTED_FLIPS = {
    "drop-archive-check": {"⑤"},
    "drop-title-check": {"⑦"},
    "empty-instead-of-missing": {"⑨", "⑫", "⑬"},
    "carry-transcript": {"⑬"},
}

CASE_TITLES = {
    "④": "④ --session-id живой сессии → принят, transcript_id заполнен САМ",
    "⑤": "⑤ --session-id архивной сессии → отказ, перечень живых сессий того же cwd",
    "⑥": "⑥ --session-id, которого в хранилище нет → отказ",
    "⑦": "⑦ имя адреса не совпадает с заголовком сессии → отказ, назван живой заголовок",
    "⑧": "⑧ только имя, РОВНО одно совпадение среди живых → принят, id взят сам",
    "⑨": "⑨ хранилища нет → принят, громкая строка «сверить нечем», transcript_id пуст",
    "⑩": "⑩ guard: архивный session_id роли — находка поимённо",
    "⑪": "⑪ guard: живой session_id роли — НЕ находка (встречный случай ⑩)",
    "⑫": "⑫ guard: хранилища нет → «сверить нечем», не «всё хорошо»",
    "⑬": "⑬ хранилища нет, номер сессии новый → прежний transcript_id сброшен, не перенесён",
}
CASE_ORDER = ["④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑬", "⑩", "⑪", "⑫"]

CASES = DIFFER = PASSED = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, PASSED
    CASES += 1
    DIFFER += bool(differ)
    PASSED += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


# ── помощники ────────────────────────────────────────────────────────────────────────

def table_columns(db: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def role_field(db: Path, role: str, field: str):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(f"SELECT {field} FROM role_sessions WHERE role = ?", (role,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def run_signal(tool: Path, db: Path, role: str, args: list, env: dict):
    cmd = [sys.executable, "-B", str(tool), "--role", role, "--db", str(db), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",  # env: caller — env приходит параметром, его строит mezo_stand.stand_env в build_stand
                       env=env, cwd=str(tool.parent))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_guard(tool: Path, db: Path, args: list, env: dict):
    cmd = [sys.executable, "-B", str(tool), "--db", str(db), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",  # env: caller — env приходит параметром, его строит mezo_stand.stand_env в build_stand
                       env=env, cwd=str(tool.parent))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def build_fixture_store(root: Path, container_cwd: str, other_cwd: str) -> Path:
    """Подложное хранилище сессий приложения — ЖИВОЙ формат (`local_<id>.json`, поля
    sessionId/cliSessionId/title/isArchived/cwd/lastActivityAt), но целиком во временном
    каталоге приёмки: реальное хранилище эта функция не читает и не трогает.

    ЧЕТЫРЕ ЗАПИСИ, каждая доказывает СВОЙ угол сверки:
      local_live_match .. живая, cwd контура, заголовок «TESTROLE-A» — то, что должно
                          быть ПРИНЯТО (случаи ④⑧)
      local_archived .... та же cwd и тот же заголовок, но В АРХИВЕ — то, что должно
                          быть ОТКАЗАНО (случай ⑤), хотя по имени и cwd она бы подошла
      local_live_other .. живая, cwd контура, ДРУГОЙ заголовок «TESTROLE-B» — доказывает,
                          что перечень живых сессий не ограничен одной записью (случай ⑤),
                          и что имя действительно СВЕРЯЕТСЯ, а не просто «жива ли» (случай ⑦)
      local_other_cwd ... живая, ТОТ ЖЕ заголовок «TESTROLE-A», но ДРУГОЙ cwd — доказывает,
                          что сверка cwd действительно фильтрует, а не берёт имя откуда попало
                          (случай ⑧: без этой записи «ровно одно совпадение» было бы верно
                          даже без фильтра по cwd)
    Рядом — `deleted_*.json` и `archived-sessions.idx`: встречный случай границы
    mezo_sessions.py (их эта функция читать не должна, и «нашёл ли мусор» видно по тому,
    что находки случаев не смещаются).
    """
    store = root / "session-store"
    leaf = store / "acct" / "proj"
    leaf.mkdir(parents=True)

    def write(name: str, **fields):
        (leaf / f"{name}.json").write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")

    write("local_live_match", sessionId="local_live_match", cliSessionId="transcript-live-match",
         title="TESTROLE-A", cwd=container_cwd, isArchived=False, lastActivityAt=1000)
    write("local_archived", sessionId="local_archived", cliSessionId="transcript-archived",
         title="TESTROLE-A", cwd=container_cwd, isArchived=True, lastActivityAt=900)
    write("local_live_other", sessionId="local_live_other", cliSessionId="transcript-live-other",
         title="TESTROLE-B", cwd=container_cwd, isArchived=False, lastActivityAt=950)
    write("local_other_cwd", sessionId="local_other_cwd", cliSessionId="transcript-other-cwd",
         title="TESTROLE-A", cwd=other_cwd, isArchived=False, lastActivityAt=800)

    (leaf / "deleted_local_ghost.json").write_text(
        json.dumps({"sessionId": "local_ghost", "title": "TESTROLE-A", "cwd": container_cwd,
                   "isArchived": False}), encoding="utf-8")
    (store / "archived-sessions.idx").write_text("не JSON — этот файл не читается вовсе",
                                                 encoding="utf-8")
    return store


def build_environment(stand: Path, tag: str, signal_tool: Path, guard_tool: Path) -> SimpleNamespace:
    """Полный независимый стенд: контейнер (для MEZO_CONTAINER) + копия живой БД с
    накатанным шагом схемы + подложное хранилище + копии двух испытуемых инструментов
    СО ВСЕМИ соседями (mezo_stand.copy_tool копирует их транзитивно). `tag` отделяет
    один вызов от другого — чистый прогон и прогон под --break используют РАЗНЫЕ стенды."""
    root = stand / tag
    root.mkdir(parents=True)

    container = root / "container"
    scripts_dir = container / ".mezosync" / "scripts"
    (scripts_dir / "migrations").mkdir(parents=True)
    shutil.copy2(LIVE_CONTAINER / ".mezosync" / "scripts" / "schema_journal.py",
                scripts_dir / "schema_journal.py")
    migration_copy = scripts_dir / "migrations" / STEP_FILE.name
    shutil.copy2(STEP_FILE, migration_copy)

    db = root / "db.sqlite"
    mezo_stand.snapshot_db(LIVE_DB, db)
    to_pre_step(db)
    r = subprocess.run([sys.executable, "-B", str(migration_copy), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(root))
    if r.returncode != 0:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: шаг схемы не применился при сборке стенда «{tag}»: "
                 f"{r.stdout}{r.stderr}")

    # роли для случаев guard ⑩⑪ — вставлены НАПРЯМУЮ, в обход signal-templates.py: guard
    # обязан ловить УЖЕ УСТАРЕВШИЕ записи (сессия ушла в архив ПОСЛЕ того, как её записали),
    # а не только те, что сам инструмент записи умеет отклонить на входе.
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                "session_id) VALUES (?,?,datetime('now'),?,?,?)",
                ("TESTROLE_LIVE", "TESTROLE-A [111111]", "TEST", "self", "local_live_match"))
    conn.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                "session_id) VALUES (?,?,datetime('now'),?,?,?)",
                ("TESTROLE_ARCHIVED", "TESTROLE-A [222222]", "TEST", "self", "local_archived"))
    # роль для ⑬: у неё УЖЕ есть номер записи разговора прежнего чата
    conn.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                "session_id, transcript_id) VALUES (?,?,datetime('now'),?,?,?,?)",
                ("TESTROLE13", "TESTROLE-A [131313]", "TEST", "self", "local_old_13",
                 "transcript-old-13"))
    conn.commit()
    conn.close()

    container_cwd = str(container)
    other_cwd = str(root / "unrelated-project")
    fake_store = build_fixture_store(root, container_cwd, other_cwd)
    missing_store = root / "no-such-store"          # никогда не создаётся — случаи ⑨/⑫

    tools_dir = root / "tools"
    signal_copy = mezo_stand.copy_tool(signal_tool, tools_dir)
    guard_copy = mezo_stand.copy_tool(guard_tool, tools_dir)

    env = mezo_stand.stand_env(container, MEZO_SESSION_STORE=str(fake_store))
    env_missing = mezo_stand.stand_env(container, MEZO_SESSION_STORE=str(missing_store))

    return SimpleNamespace(root=root, container=container, db=db, fake_store=fake_store,
                           missing_store=missing_store, signal=signal_copy, guard=guard_copy,
                           env=env, env_missing=env_missing)


def mutate(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        sys.exit(f"⛔ ПОЛОМКА НЕ ЛЕГЛА В {path.name}: найдено {n} вхождений (ожидался 1)")
    path.write_text(text.replace(old, new), encoding="utf-8")


def apply_break(tag: str, src_dir: Path) -> None:
    if tag == "drop-archive-check":
        mutate(src_dir / "signal-templates.py",
              "                if record is None or record.archived:\n",
              "                if record is None:\n")
    elif tag == "drop-title-check":
        mutate(src_dir / "signal-templates.py",
              '                if name_part is not None and (record.title or "") != name_part:\n',
              "                if False:\n")
    elif tag == "empty-instead-of-missing":
        mutate(src_dir / "mezo_sessions.py",
              '    if not store_path.is_dir():\n'
              '        return SessionStore(found=False, path=store_path, sessions=(),\n'
              '                            error=f"хранилище сессий приложения не найдено ({store_path})")\n',
              '    if not store_path.is_dir():\n'
              '        return SessionStore(found=True, path=store_path, sessions=(), error=None)\n')
    elif tag == "carry-transcript":
        mutate(src_dir / "signal-templates.py",
              "            if previous is not None and new_sid != previous[1] and new_tid is not None:\n",
              "            if False:\n")
    else:
        raise ValueError(tag)


# ── случаи ①②③: сам шаг схемы ────────────────────────────────────────────────────────

def to_pre_step(db: Path) -> None:
    """Копию базы привести к виду «до шага 20260924»: снять transcript_id, если он уже есть.

    Живая база шаг уже прошла (24.09 09:50 UTC), и копия с неё несёт колонку. Без этого
    случаи ① и ③ меряли бы не применение шага, а «колонка была и осталась» — приёмка
    проходила бы только у автора, до установки шага в живую базу.
    """
    conn = sqlite3.connect(str(db))
    try:
        for table in ("role_sessions", "role_sessions_history"):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if "transcript_id" in cols:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN transcript_id")
        conn.commit()
    finally:
        conn.close()


def run_migration_cases(stand: Path) -> bool:
    ok = True
    scripts_dir = stand / "migration-only" / ".mezosync" / "scripts"
    (scripts_dir / "migrations").mkdir(parents=True)
    shutil.copy2(LIVE_CONTAINER / ".mezosync" / "scripts" / "schema_journal.py",
                scripts_dir / "schema_journal.py")
    migration_copy = scripts_dir / "migrations" / STEP_FILE.name
    shutil.copy2(STEP_FILE, migration_copy)

    db_dry = stand / "db-dry.sqlite"
    mezo_stand.snapshot_db(LIVE_DB, db_dry)
    to_pre_step(db_dry)
    cols_before = table_columns(db_dry, "role_sessions")
    r = subprocess.run([sys.executable, "-B", str(migration_copy), "--db", str(db_dry), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(stand))
    out = (r.stdout or "") + (r.stderr or "")
    cols_after = table_columns(db_dry, "role_sessions")
    ok &= case("③ --dry-run шага НЕ меняет базу",
               r.returncode == 0 and "ВХОЛОСТУЮ" in out and cols_before == cols_after
               and "transcript_id" not in cols_after,
               f"код {r.returncode} · колонки role_sessions до и после равны: "
               f"{'да' if cols_before == cols_after else 'НЕТ'} ({len(cols_after)} колонок)",
               differ=True)

    db_main = stand / "db-main.sqlite"
    mezo_stand.snapshot_db(LIVE_DB, db_main)
    to_pre_step(db_main)
    r1 = subprocess.run([sys.executable, "-B", str(migration_copy), "--db", str(db_main)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=mezo_stand.stand_env(stand))
    out1 = (r1.stdout or "") + (r1.stderr or "")
    cols1 = table_columns(db_main, "role_sessions")
    hist1 = table_columns(db_main, "role_sessions_history")
    ok &= case("① шаг схемы применяется (role_sessions.transcript_id + история)",
               r1.returncode == 0 and "ПРИМЕНЕНО" in out1 and "transcript_id" in cols1
               and "transcript_id" in hist1,
               f"код {r1.returncode} · role_sessions.transcript_id: "
               f"{'есть' if 'transcript_id' in cols1 else 'НЕТ'} · "
               f"role_sessions_history.transcript_id: "
               f"{'есть' if 'transcript_id' in hist1 else 'НЕТ'}",
               differ=True)

    r2 = subprocess.run([sys.executable, "-B", str(migration_copy), "--db", str(db_main)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=mezo_stand.stand_env(stand))
    out2 = (r2.stdout or "") + (r2.stderr or "")
    ok &= case("② повторный прогон шага — «уже сведено», выхода нет",
               r2.returncode == 0 and "уже сведено" in out2,
               f"код {r2.returncode} · «уже сведено» в выводе: "
               f"{'да' if 'уже сведено' in out2 else 'НЕТ'}",
               differ=True)
    return ok


# ── случаи ④–⑨: signal-templates.py ─────────────────────────────────────────────────

def eval_signal_cases(e: SimpleNamespace) -> dict:
    out = {}

    code4, txt4 = run_signal(e.signal, e.db, "TESTROLE4",
                             ["--set-address", "TESTROLE-A [aaaaaa]", "--session-id",
                              "local_live_match", "--source", "self"], e.env)
    sid4 = role_field(e.db, "TESTROLE4", "session_id")
    tid4 = role_field(e.db, "TESTROLE4", "transcript_id")
    out["④"] = (code4 == 0 and sid4 == "local_live_match" and tid4 == "transcript-live-match",
               f"код {code4} · session_id={sid4} · transcript_id={tid4}")

    code5, txt5 = run_signal(e.signal, e.db, "TESTROLE5",
                             ["--set-address", "TESTROLE-A [bbbbbb]", "--session-id",
                              "local_archived", "--source", "self"], e.env)
    row5 = role_field(e.db, "TESTROLE5", "address")
    out["⑤"] = (code5 != 0 and row5 is None and "local_live_match" in txt5
               and "local_other_cwd" not in txt5,
               f"код {code5} · строка записана: {'да (ОШИБКА)' if row5 is not None else 'нет'} · "
               f"живой local_live_match назван: "
               f"{'да' if 'local_live_match' in txt5 else 'НЕТ'}")

    code6, txt6 = run_signal(e.signal, e.db, "TESTROLE6",
                             ["--set-address", "TESTROLE-A [cccccc]", "--session-id",
                              "local_does_not_exist", "--source", "self"], e.env)
    row6 = role_field(e.db, "TESTROLE6", "address")
    out["⑥"] = (code6 != 0 and row6 is None and "НЕ НАЙДЕН" in txt6,
               f"код {code6} · строка записана: {'да (ОШИБКА)' if row6 is not None else 'нет'}")

    code7, txt7 = run_signal(e.signal, e.db, "TESTROLE7",
                             ["--set-address", "TESTROLE-A [dddddd]", "--session-id",
                              "local_live_other", "--source", "self"], e.env)
    row7 = role_field(e.db, "TESTROLE7", "address")
    out["⑦"] = (code7 != 0 and row7 is None and "TESTROLE-B" in txt7,
               f"код {code7} · строка записана: {'да (ОШИБКА)' if row7 is not None else 'нет'} · "
               f"живой заголовок «TESTROLE-B» назван: "
               f"{'да' if 'TESTROLE-B' in txt7 else 'НЕТ'}")

    code8, txt8 = run_signal(e.signal, e.db, "TESTROLE8",
                             ["--set-address", "TESTROLE-A [eeeeee]", "--source", "self"], e.env)
    sid8 = role_field(e.db, "TESTROLE8", "session_id")
    tid8 = role_field(e.db, "TESTROLE8", "transcript_id")
    out["⑧"] = (code8 == 0 and sid8 == "local_live_match" and tid8 == "transcript-live-match",
               f"код {code8} · session_id={sid8} · transcript_id={tid8}")

    code9, txt9 = run_signal(e.signal, e.db, "TESTROLE9",
                             ["--set-address", "TESTROLE-A [ffffff]", "--session-id",
                              "local_whatever", "--source", "self"], e.env_missing)
    sid9 = role_field(e.db, "TESTROLE9", "session_id")
    tid9 = role_field(e.db, "TESTROLE9", "transcript_id")
    out["⑨"] = (code9 == 0 and sid9 == "local_whatever" and tid9 is None
               and "СВЕРИТЬ НЕЧЕМ" in txt9,
               f"код {code9} · session_id={sid9} · transcript_id={tid9} · "
               f"«сверить нечем»: {'да' if 'СВЕРИТЬ НЕЧЕМ' in txt9 else 'НЕТ'}")

    # ⑬ встречный к ⑨ (возврат COORD): у роли ЕСТЬ прежний transcript_id — в ⑨ его нет,
    # и пустое поле там получалось от пустой строки, а не от сброса.
    code13, txt13 = run_signal(e.signal, e.db, "TESTROLE13",
                               ["--session-id", "local_new_13", "--source", "self"], e.env_missing)
    sid13 = role_field(e.db, "TESTROLE13", "session_id")
    tid13 = role_field(e.db, "TESTROLE13", "transcript_id")
    out["⑬"] = (code13 == 0 and sid13 == "local_new_13" and tid13 is None
               and "сброшен" in txt13,
               f"код {code13} · session_id={sid13} · transcript_id={tid13} (прежний transcript-old-13)")
    return out


# ── случаи ⑩–⑫: guard-role-sessions-live.py ─────────────────────────────────────────

def eval_guard_cases(e: SimpleNamespace) -> dict:
    out = {}
    code10, txt10 = run_guard(e.guard, e.db, ["--session-store", str(e.fake_store)], e.env)
    out["⑩"] = (code10 != 0 and "TESTROLE_ARCHIVED" in txt10 and "В АРХИВЕ" in txt10,
               f"код {code10} · роль названа поимённо: "
               f"{'да' if 'TESTROLE_ARCHIVED' in txt10 else 'НЕТ'}")
    out["⑪"] = ("TESTROLE_LIVE" not in txt10,
               f"«TESTROLE_LIVE» среди находок: "
               f"{'да (ОШИБКА)' if 'TESTROLE_LIVE' in txt10 else 'нет'}")

    code12, txt12 = run_guard(e.guard, e.db, ["--session-store", str(e.missing_store)], e.env)
    out["⑫"] = (code12 != 0 and "СВЕРИТЬ НЕЧЕМ" in txt12 and "✅" not in txt12,
               f"код {code12} · «сверить нечем»: "
               f"{'да' if 'СВЕРИТЬ НЕЧЕМ' in txt12 else 'НЕТ'} · "
               f"«✅» отсутствует: {'да' if '✅' not in txt12 else 'НЕТ (заявляет «всё хорошо»)'}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(EXPECTED_FLIPS),
                    help="нарочная поломка — портит ОДНУ копию файла перед сборкой стенда; "
                         "какой случай должен покраснеть РОВНО от неё — см. шапку файла")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-role-sessions-")

    src_dir = stand / "src"
    src_dir.mkdir()
    for name in ("mezo_paths.py", "mezo_sessions.py", "signal-templates.py",
                "guard-role-sessions-live.py"):
        shutil.copy2(TOOLS_DIR / name, src_dir / name)
    if a.break_name:
        apply_break(a.break_name, src_dir)
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём красным РОВНО "
              f"{', '.join(sorted(EXPECTED_FLIPS[a.break_name]))}, остальные случаи — как на "
              f"чистом прогоне (сверка красных строк с этим списком — рукой вызывающего).\n")

    ok = True
    if not a.break_name:
        ok &= run_migration_cases(stand)

    env_obj = build_environment(stand, "run", src_dir / "signal-templates.py",
                                src_dir / "guard-role-sessions-live.py")
    verdicts = {}
    verdicts.update(eval_signal_cases(env_obj))
    verdicts.update(eval_guard_cases(env_obj))
    for label in CASE_ORDER:
        verdict, detail = verdicts[label]
        ok &= case(CASE_TITLES[label], verdict, detail, differ=True)

    print(f"\nИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
