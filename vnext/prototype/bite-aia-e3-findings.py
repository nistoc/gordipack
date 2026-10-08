# -*- coding: utf-8 -*-
r"""bite-aia-e3-findings.py — приёмка карточки #685: находки контура AIA при приёмке выпуска Э3.

ПОВОД. Контур AIA, принимая выпуск 05.10 (коммит 94b45b3), нашёл восемь мест ④-1…④-8 (письмо
2026-10-06 00:40 UTC в папке моста aia-atlas). ④-7 закрыта карточкой #683 (backup-db.py), ④-6 —
случаем R9 приёмки bite-local-paths.py, ④-3 и ④-5 — правкой текста документа выпуска 05.10.
Здесь — четыре места, где поведение инструмента было неверным; каждое перемерено на копии рукой
PROTO 2026-10-08, до правки и после:

  ① ④-1 set-rule.py --db <копия> --apply при объявлении о правке set-rule.py в живой базе:
       прежде — код 3 и строка ожидания в ЖИВОЙ базе (tool_lease_waits) раньше слов «БАЗА НЕ
       ЖИВАЯ»: путь живой базы для сравнения искался через resolve_db с проверкой объявлений.
       Теперь — код 0, слова «БАЗА НЕ ЖИВАЯ», строк ожидания в живой базе не прибавилось
  ② ④-2 guard-printed-forms.py, наблюдение read-phoenix --role X: прежде read-phoenix писал
       отметку «роль видела подсказку» (hint_seen) — проверка «съедала» первый показ подсказки
       у роли, чью память читала. Теперь наблюдение идёт с --full: отметок у роли не прибавилось
  ③ ④-4 export-rules.py: шапка файла правил печатала команду правки правила без --actor — по ней
       запись шла от координатора. Теперь в команде есть --actor
  ④ ④-8 update-tools.py: файл совпадает с пакетом, а отпечаток установки у него старый. Прежде
       отпечаток не трогался, и когда пакет менял файл, тот ложно вставал в «✋ правлен у тебя».
       Теперь план называет такие файлы строкой «≈ …», --apply переписывает им отпечаток, и после
       смены файла в пакете он идёт строкой «≠ … обновится», а не «✋»

Нарочные поломки (Р — копия инструмента со старым поведением в одном месте; якорь не нашёлся —
«НЕ ЗАПУСТИЛАСЬ», не молчание): каждая обязана уронить РОВНО свой случай.
  Р① путь живой базы снова через resolve_db       → ① проваливается (код 3, ожидание записано)
  Р② наблюдение без --full                         → ② проваливается (отметка записана)
  Р③ команда шапки без --actor                     → ③ проваливается
  Р④ отпечатки совпадающих файлов не переписываются → ④ проваливается («✋» после смены в пакете)

⛔ Живая база только копируется (mezo_stand.snapshot_db) — каждый случай работает на своей копии.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = DIFFER = 0
OK = True


class NotRun(Exception):
    """Приёмка не смогла начаться — не «сломано» и не «в порядке»."""


def case(title, verdict, detail):
    global CASES, DIFFER, OK
    CASES += 1
    DIFFER += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")


def weakened(src: Path, dest_dir: Path, anchor: str, replacement: str) -> Path:
    """Копия инструмента с одним местом в прежнем виде. Якорь обязан встретиться ровно раз."""
    text = src.read_text(encoding="utf-8")
    found = text.count(anchor)
    if found != 1:
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку некуда вложить — образец найден {found} раз в {src.name}:"
                     f" {anchor[:70]!r}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / src.name
    out.write_text(text.replace(anchor, replacement), encoding="utf-8")
    return out


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def count(db: Path, sql: str, *params) -> int:
    con = sqlite3.connect(str(db))
    try:
        return con.execute(sql, params).fetchone()[0]
    finally:
        con.close()


def container(root: Path, tag: str, snap: Path, tools=()) -> tuple[Path, Path, Path]:
    """Контейнер стенда: своя копия базы и копии инструментов с соседями. → (корень, скрипты, база)."""
    c = root / tag
    sc = c / ".mezosync" / "scripts"
    sc.mkdir(parents=True)
    db = c / ".mezosync" / "mezosync.db"
    shutil.copy2(snap, db)
    for t in tools:
        mezo_stand.copy_tool(t, sc)
    return c, sc, db


# ① ④-1: объявление о правке set-rule.py в «живой» базе стенда, запись — в копию.
def lease_case(root: Path, snap: Path, set_rule: Path, tag: str):
    c, sc, db = container(root, tag, snap, (mezo_target.script("set-rule.py"),
                                             mezo_target.script("lease.py")))
    shutil.copy2(set_rule, sc / "set-rule.py")
    other = root / f"{tag}-copy.db"
    shutil.copy2(snap, other)
    env = mezo_stand.stand_env(c, PYTHONIOENCODING="utf-8", MEZO_ROLE="ZZA")
    r = subprocess.run([sys.executable, str(sc / "lease.py"), "take", "--role", "ZZHOLD",
                        "--tools", "set-rule.py", "--reason", "проба приёмки", "--minutes", "30"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, cwd=str(root), timeout=120)
    if r.returncode != 0:
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: объявление на стенде не взялось (код {r.returncode}):"
                     f" {(r.stdout + r.stderr).strip()[-300:]}")
    before = count(db, "SELECT count(*) FROM tool_lease_waits")
    r = subprocess.run([sys.executable, str(sc / "set-rule.py"), "--db", str(other),
                        "--key", "zz-probe-685", "--body", "проба приёмки", "--locked-by", "coord",
                        "--actor", "ZZA", "--basis", "проба", "--authorized-by", "ZZA",
                        "--source-ref", "проба", "--expiry-kind", "forever", "--apply"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, cwd=str(root), timeout=300)
    after = count(db, "SELECT count(*) FROM tool_lease_waits")
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "БАЗА НЕ ЖИВАЯ" in out and after == before
    return ok, (f"код {r.returncode}; строк ожидания в «живой» базе стенда {before} → {after};"
                f" «БАЗА НЕ ЖИВАЯ» в выводе: {'БАЗА НЕ ЖИВАЯ' in out}")


# ② ④-2: наблюдение read-phoenix проверкой печатаемых форм не пишет отметок подсказок.
def observe_case(root: Path, snap: Path, guard: Path, tag: str):
    c, sc, db = container(root, tag, snap, (mezo_target.script("read-phoenix.py"),))
    con = sqlite3.connect(str(db))
    row = con.execute("SELECT role FROM phoenix ORDER BY role LIMIT 1").fetchone()
    if row is None:
        con.close()
        raise NotRun("⛔ НЕ ЗАПУСТИЛАСЬ: в копии базы нет ни одной сохранённой памяти роли — наблюдать нечего")
    role = row[0]
    con.execute("DELETE FROM hint_seen WHERE role = ?", (role,))
    con.commit()
    con.close()
    saved = os.environ.get("MEZO_CONTAINER")
    os.environ["MEZO_CONTAINER"] = str(c)
    try:
        mod = load(guard, f"guard_printed_forms_{tag.replace('-', '_')}")
        _, ran, _ = mod.observe(sc, role)
    finally:
        if saved is None:
            os.environ.pop("MEZO_CONTAINER", None)
        else:
            os.environ["MEZO_CONTAINER"] = saved
    marks = count(db, "SELECT count(*) FROM hint_seen WHERE role = ?", role)
    return marks == 0 and ran > 0, f"роль {role}; прогнано команд {ran}; отметок «видела подсказку» у роли: {marks}"


# ③ ④-4: команда правки правила в шапке файла правил несёт --actor.
def export_case(root: Path, snap: Path, export_rules: Path, tag: str):
    c, sc, db = container(root, tag, snap, (mezo_target.script("export-rules.py"),))
    shutil.copy2(export_rules, sc / "export-rules.py")
    out_file = root / f"{tag}-sync.rules.md"
    r = subprocess.run([sys.executable, str(sc / "export-rules.py"), "--db", str(db),
                        "--out", str(out_file), "--apply"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(c, PYTHONIOENCODING="utf-8"), cwd=str(root), timeout=300)
    if not out_file.is_file():
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: файл правил не записан (код {r.returncode}):"
                     f" {((r.stdout or '') + (r.stderr or '')).strip()[-300:]}")
    line = next((ln for ln in out_file.read_text(encoding="utf-8").splitlines()
                 if "set-rule.py" in ln and "--apply" in ln and "--key" in ln), "")
    return "--actor" in line, f"команда в шапке: {line[line.find('--key'):].strip()[:120] or '— не найдена'}"


# ④ ④-8: совпадающий с пакетом файл со старым отпечатком после смены в пакете — «≠», а не «✋».
def fingerprint_case(root: Path, update_tools: Path, tag: str):
    base = root / tag
    pack = base / "pack"
    (pack / "scripts").mkdir(parents=True)
    genv = mezo_stand.stand_env(base)

    def git(*a):
        return subprocess.run(["git", "-C", str(pack), *a], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=genv, timeout=120).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    (pack / "scripts" / "a.py").write_text("print('v1')\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "c1")
    c1 = git("rev-parse", "--short", "HEAD")
    c = base / "contour"
    sc = c / ".mezosync" / "scripts"
    sc.mkdir(parents=True)
    mezo_stand.copy_tool(mezo_target.script("update-tools.py"), sc)
    shutil.copy2(update_tools, sc / "update-tools.py")
    (sc / "a.py").write_text("print('v1')\n", encoding="utf-8")
    con = sqlite3.connect(str(c / ".mezosync" / "mezosync.db"))
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO meta VALUES (?, ?)",
                    [("template_source", str(pack)), ("template_commit", c1),
                     ("template_files_sha", json.dumps({"a.py": "0000-старый-отпечаток"}))])
    con.commit()
    con.close()

    def ut(*a):
        r = subprocess.run([sys.executable, str(sc / "update-tools.py"), *a], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(c, PYTHONIOENCODING="utf-8"), cwd=str(base),
                           timeout=300)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    _, plan1 = ut("--rev", c1)
    rc_apply, _ = ut("--rev", c1, "--apply")
    (pack / "scripts" / "a.py").write_text("print('v2')\n", encoding="utf-8")
    git("commit", "-qam", "c2")
    c2 = git("rev-parse", "--short", "HEAD")
    _, plan2 = ut("--rev", c2)
    named = any(ln.strip().startswith("≈") for ln in plan1.splitlines())
    lines2 = [ln.strip() for ln in plan2.splitlines() if "a.py" in ln]
    fresh = any(ln.startswith("≠") for ln in lines2)
    own = any(ln.startswith("✋") for ln in lines2)
    return (named and rc_apply == 0 and fresh and not own,
            f"план до записи назвал «≈»: {named}; запись — код {rc_apply}; после смены в пакете"
            f" строка файла: {lines2[0][:90] if lines2 else '— нет'}")


def main() -> int:
    root = mezo_stand.new("bite-aia-e3-")
    snap = root / "snapshot.db"
    mezo_stand.snapshot_db(mezo_paths.live_db(), snap)
    set_rule = mezo_target.script("set-rule.py")
    guard = HERE / "guard-printed-forms.py"
    if not guard.is_file():
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: рядом с приёмкой нет {guard.name}")
    export_rules = mezo_target.script("export-rules.py")
    update_tools = mezo_target.script("update-tools.py")
    brk = root / "breaks"

    ok1, d1 = lease_case(root, snap, set_rule, "c1")
    case("① ④-1 запись в копию при объявлении о правке set-rule.py: код 0, «БАЗА НЕ ЖИВАЯ»,"
         " в живой базе ожиданий не прибавилось", ok1, d1)
    ok2, d2 = observe_case(root, snap, guard, "c2")
    case("② ④-2 наблюдение read-phoenix проверкой печатаемых форм отметок подсказок не пишет", ok2, d2)
    ok3, d3 = export_case(root, snap, export_rules, "c3")
    case("③ ④-4 команда правки правила в шапке файла правил несёт --actor", ok3, d3)
    ok4, d4 = fingerprint_case(root, update_tools, "c4")
    case("④ ④-8 совпадающий с пакетом файл со старым отпечатком: «≈», затем после смены в пакете «≠»,"
         " а не «✋»", ok4, d4)

    w1 = weakened(set_rule, brk / "r1", "    live_db = str((mezo_root(__file__) / DB_NAME).resolve())",
                  "    live_db = str(resolve_db(None, __file__))")
    b1, e1 = lease_case(root, snap, w1, "r1")
    case("Р① путь живой базы снова через resolve_db — случай ① ПРОВАЛИВАЕТСЯ", not b1 and ok1, e1)
    w2 = weakened(guard, brk / "r2", '[sys.executable, str(rp), "--role", role, "--full"]',
                  '[sys.executable, str(rp), "--role", role]')
    b2, e2 = observe_case(root, snap, w2, "r2")
    case("Р② наблюдение без --full — случай ② ПРОВАЛИВАЕТСЯ", not b2 and ok2, e2)
    w3 = weakened(export_rules, brk / "r3", "--locked-by owner|coord --actor <РОЛЬ> --body-file",
                  "--locked-by owner|coord --body-file")
    b3, e3 = export_case(root, snap, w3, "r3")
    case("Р③ команда шапки без --actor — случай ③ ПРОВАЛИВАЕТСЯ", not b3 and ok3, e3)
    w4 = weakened(update_tools, brk / "r4",
                  "        for rel in stale_fp:\n"
                  "            updated_fingerprints[fingerprint_key(rel)] = digest(dest_of(rel).read_bytes())\n",
                  "")
    b4, e4 = fingerprint_case(root, w4, "r4")
    case("Р④ отпечатки совпадающих файлов не переписываются — случай ④ ПРОВАЛИВАЕТСЯ", not b4 and ok4, e4)

    print()
    print(f"{'✅ НАХОДКИ AIA Э3 — ПРИНЯТО' if OK else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if OK else 1


if __name__ == "__main__":
    try:
        code = main()
    except NotRun as e:
        print(e)
        code = 2
    sys.exit(mezo_stand.finish(code))
