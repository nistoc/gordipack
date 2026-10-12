#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bite-schema-step-wal-tail.py — точка отката шага схемы видит хвост WAL-журнала (карточки #624, #715).

ЗАЧЕМ ОТДЕЛЬНО ОТ ПРИЁМКИ КОНТУРА Atlas. В Atlas тот же опыт ставит
.mezosync/scripts/bite-schema-step-wal-tail-backup.py — но он судит ДВА инструмента сразу
(шаг схемы и split-history-table.py), а второго в пакете нет; прежнюю редакцию он берёт из
истории зеркала Atlas, которого у соседа тоже нет. Поэтому в контуре, собранном из пакета,
точка отката шага схемы не проверялась ничем (замечание COORD на карточке #624, 14.09).
Здесь — только шаг схемы, и прежний способ воспроизводится нарочной поломкой: она возвращает
ровно ту строку, что стояла в пакете до правки (0330860^: `shutil.copy(DB, backup)`).

ОПЫТ. База стенда в режиме WAL · держащий читатель (BEGIN; SELECT — журнал не сбрасывается
в основной файл) · запись ДРУГОЙ роли уходит в хвост журнала · шаг снимает точку отката.
Копирование одного файла чужой записи не видит; резервное копирование SQLite — видит.

Случаи:
  ⓪ опыту есть на что смотреть: журнал не пуст, копия одного основного файла записи не видит
  ① испытуемый шаг: код 0, в точке отката чужая запись есть
  ② точка отката легла в стенд, а не в общий временный каталог машины
  ③ НАРОЧНАЯ ПОЛОМКА: копия шага с прежней строкой shutil.copy теряет чужую запись —
     проваливается ровно то, что проверяет ①

⚖️ ПОЧЕМУ ВРЕМЕННЫЙ КАТАЛОГ ПОДМЕНЁН. Шаг кладёт точку отката в %TEMP% машины под постоянным
именем mezosync.pre-schema-journal.db. Приёмка Atlas стирает этот файл перед прогоном — и тем
уносит настоящую точку отката, если роль только что применила шаг к живой базе. Здесь шаг
запускается с TMP/TEMP/TMPDIR на каталог внутри стенда: общий файл машины не трогается
вовсе, и случай ② это проверяет.

⛔ Живая база не открывается ни на чтение, ни на запись: у стенда своя синтетическая база.
Испытуемый каталог — mezo_target (MEZO_SCRIPTS_ROOT), как у остальных приёмок пакета.

    python <абсолютный путь>/bite-schema-step-wal-tail.py
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand   # noqa: E402 — стенды и уборка по исходу
import mezo_target  # noqa: E402 — какую копию испытываем (карточка #148)

print(f"⚖️ испытуется: {mezo_target.label()}")
STEP_NAME = "20260808-schema-journal-fingerprint.py"
STEP = mezo_target.migration(STEP_NAME)
SCRIPTS = mezo_target.scripts_root()
BACKUP_NAME = "mezosync.pre-schema-journal.db"
FOREIGN_MARK = "чужая запись другой роли во время шага схемы"

# Нарочная поломка: блок резервного копирования → прежняя строка пакета (0330860^).
# Блок обязан найтись ровно один раз — иначе поломка не легла, и это говорится словами.
NEW_BACKUP_BLOCK = (
    "    backup_src = sqlite3.connect(f\"file:{Path(DB).as_posix()}?mode=ro\", uri=True)\n"
    "    backup_dst = sqlite3.connect(str(backup))\n"
    "    try:\n"
    "        with backup_dst:\n"
    "            backup_src.backup(backup_dst)\n"
    "    finally:\n"
    "        backup_src.close()\n"
    "        backup_dst.close()\n"
)
OLD_BACKUP_LINE = "    shutil.copy(DB, backup)\n"
# import shutil снят из шага вместе с правкой — поломке он снова нужен,
# иначе была бы ошибка имени, а не сравнение двух способов копирования.
IMPORT_ANCHOR = ("import sqlite3\nimport pathlib\n", "import sqlite3\nimport shutil\nimport pathlib\n")

CASES = 0
OK = True


def case(title: str, ok: bool, detail: str = "") -> bool:
    global CASES, OK
    CASES += 1
    OK = OK and bool(ok)
    print(("✅ " if ok else "🔴 ") + title)
    if detail:
        print("   " + detail)
    return ok


def build_db(path: Path) -> None:
    """Наименьшая схема, на которой шаг отрабатывает: журнал шагов, версия, таблица записок."""
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, note TEXT, "
                "fingerprint TEXT, applied_by TEXT)")
    con.execute("CREATE TABLE schema_version (v INTEGER, steps_after_milestone INTEGER)")
    con.execute("INSERT INTO schema_version VALUES (3, 0)")
    con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def has_foreign_row(db_path: Path) -> bool | None:
    """True/False — есть ли чужая запись; None — файла нет или он не с этого стенда."""
    if not db_path.exists():
        return None
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM notes WHERE body LIKE ?",
                           (f"%{FOREIGN_MARK}%",)).fetchone()[0] > 0
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()


def prepare_stand(label: str, step_file: Path) -> tuple[Path, Path, Path]:
    """Стенд: <стенд>/.mezosync/{mezosync.db, scripts/{соседи, migrations/<шаг>}}, <стенд>/tmp.
    Шаг ищет соседей уровнем выше migrations/ — раскладка та же, что в контуре."""
    stand = mezo_stand.new(f"bite-schema-wal-{label}-")
    scripts = stand / ".mezosync" / "scripts"
    (scripts / "migrations").mkdir(parents=True)
    for name in ("schema_journal.py", "mezo_paths.py"):
        mezo_stand.copy_tool(SCRIPTS / name, scripts)
    shutil.copy2(step_file, scripts / "migrations" / STEP_NAME)
    tmp = stand / "tmp"
    tmp.mkdir()
    db_path = stand / ".mezosync" / "mezosync.db"
    build_db(db_path)
    return stand, db_path, tmp


def run_step(label: str, step_file: Path) -> dict:
    """Держащий читатель → чужая запись в хвост журнала → шаг снимает точку отката."""
    stand, db_path, tmp = prepare_stand(label, step_file)
    holder = sqlite3.connect(str(db_path))
    holder.execute("BEGIN")
    holder.execute("SELECT COUNT(*) FROM notes").fetchone()
    writer = sqlite3.connect(str(db_path))
    writer.execute("INSERT INTO notes (body) VALUES (?)", (f"{FOREIGN_MARK} ({label})",))
    writer.commit()
    writer.close()

    wal = Path(str(db_path) + "-wal")
    wal_bytes = wal.stat().st_size if wal.exists() else 0
    plain_copy = stand / "plain-copy.db"
    shutil.copy(db_path, plain_copy)          # только для ⓪: так копировал прежний шаг
    plain_has = has_foreign_row(plain_copy)

    env = mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8",
                               TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp))
    r = subprocess.run([sys.executable, str(stand / ".mezosync" / "scripts" / "migrations" / STEP_NAME)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=60)
    holder.execute("ROLLBACK")
    holder.close()
    backup = tmp / BACKUP_NAME
    return {"code": r.returncode, "out": (r.stdout or "") + (r.stderr or ""),
            "wal_bytes": wal_bytes, "plain_has": plain_has,
            "backup": backup, "backup_has": has_foreign_row(backup), "stand": stand}


def broken_copy(dest_dir: Path) -> tuple[Path | None, str]:
    """Копия шага с прежней строкой. (путь, "") или (None, причина)."""
    text = STEP.read_text(encoding="utf-8")
    for find, _ in ((NEW_BACKUP_BLOCK, None), IMPORT_ANCHOR):
        n = text.count(find)
        if n != 1:
            return None, (f"образец поломки найден {n} раз (нужен один) — шаг изменился, "
                          f"поломку надо пересмотреть: {find.splitlines()[0]!r}")
    text = text.replace(NEW_BACKUP_BLOCK, OLD_BACKUP_LINE, 1)
    text = text.replace(IMPORT_ANCHOR[0], IMPORT_ANCHOR[1], 1)
    dest_dir.mkdir(parents=True, exist_ok=True)
    p = dest_dir / STEP_NAME
    p.write_text(text, encoding="utf-8")
    return p, ""


def main() -> int:
    print("=" * 88)
    print("ТОЧКА ОТКАТА ШАГА СХЕМЫ И ХВОСТ WAL-ЖУРНАЛА (карточки #624, #715)")
    print(f"   шаг: {STEP}")
    print("=" * 88)
    machine_backup = None
    try:
        import tempfile
        machine_backup = Path(tempfile.gettempdir()) / BACKUP_NAME
        machine_before = machine_backup.stat().st_mtime_ns if machine_backup.exists() else None
    except OSError:
        machine_before = None

    res = run_step("new", STEP)
    case("⓪ опыту есть на что смотреть: журнал не пуст, копия одного основного файла "
         "чужой записи не видит",
         res["wal_bytes"] > 0 and res["plain_has"] is False,
         f"-wal {res['wal_bytes']} байт · чужая запись в копии одного файла: {res['plain_has']}")
    case("① испытуемый шаг: код 0, в точке отката чужая запись есть",
         res["code"] == 0 and res["backup_has"] is True,
         f"код {res['code']} · чужая запись в точке отката: {res['backup_has']}"
         + (" (точки отката нет или она не со стенда)" if res["backup_has"] is None else "")
         + ("" if res["code"] == 0 else f" · вывод шага: {res['out'].strip()[-300:]}"))
    in_stand = f"точка отката: {res['backup']}" in res["out"]
    machine_after = machine_backup.stat().st_mtime_ns if machine_backup and machine_backup.exists() else None
    case("② точка отката легла в стенд; файл с тем же именем в общем временном каталоге "
         "машины не тронут",
         in_stand and machine_after == machine_before,
         f"путь из вывода шага в стенде: {in_stand} · общий файл машины "
         f"{'не тронут' if machine_after == machine_before else 'ИЗМЕНЁН'}")

    broken_dir = mezo_stand.new("bite-schema-wal-broken-src-")
    broken, why = broken_copy(broken_dir)
    if broken is None:
        case("③ НАРОЧНАЯ ПОЛОМКА (прежняя строка shutil.copy) — НЕ ЗАПУСТИЛАСЬ", False, why)
    else:
        bres = run_step("broken", broken)
        case("③ НАРОЧНАЯ ПОЛОМКА: копия шага с прежней строкой shutil.copy теряет чужую "
             "запись — проваливается ровно то, что проверяет ①",
             bres["code"] == 0 and bres["backup_has"] is False,
             f"код {bres['code']} · чужая запись в точке отката под поломкой: "
             f"{bres['backup_has']} (ждём False — как у пакета до правки)")

    print()
    print(f"{'✅ ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}")
    # Замер 12.10: точку отката КОДОМ снимает только этот шаг; у 20260807-addressed-by-unset
    # и 20260808-rule-basis-and-cancel она лишь названа в шапке — её сняли рукой один раз.
    print("⚖️ ГРАНИЦА: судится точка отката ОДНОГО шага (20260808) — другие шаги пакета кодом "
          "её не снимают. Что откат из неё возвращает базу целиком, здесь не проверяется.")
    return mezo_stand.finish(0 if OK else 1)


if __name__ == "__main__":
    sys.exit(main())
