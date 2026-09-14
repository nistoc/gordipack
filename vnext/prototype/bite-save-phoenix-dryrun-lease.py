#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ВСТРЕЧНЫЙ СЛУЧАЙ карточки #629 ③ — save-phoenix.py --dry-run под чужим объявлением
о правке: читающий, а не пишущий.

ПРЕДМЕТ. До правки #629 холостой прогон (--dry-run) save-phoenix.py не называл своего
характера вызова (readonly) вторым замком аренды (mezo_paths.resolve_db → lease.check) —
инструмент судился ПО ИМЕНИ ФАЙЛА, а имя "save-phoenix.py" не похоже на читающее.
Под чужим объявлением о правке холостой прогон получал ОТКАЗ ПИШУЩЕГО (код 3), и
lease._remember_wait успевала записать ожидание в tool_lease_waits ДО отказа — то есть
холостой прогон переставал быть холостым для механизма аренды (живой случай 2026-09-14
16:58 UTC: PROTO не сняла своё объявление о правке save-phoenix.py, приёмка
bite-phoenix-service-blocks.py прогнала --dry-run от имени STUD/BITE519 и оставила
запись ожидания в ЖИВОЙ базе).

ЧЕМ СУДИМ. Всё на СОГЛАСОВАННОЙ КОПИИ живой базы (mezo_stand.snapshot_db), с
MEZO_LEASE_TEST=1 (без него lease.check молчит на копии — карточка #204/#391, объявление
действует только в живом контуре). Объявление берёт роль TAXO, холостой и настоящий
прогон зовёт роль ZZTEST629 (не существующая в контуре — не спутать с настоящей ролью).

ПОРЧА (--break no-readonly): в КОПИИ save-phoenix.py снимается правка карточки #629
(readonly больше не называется явно) — холостой прогон снова получает отказ пишущего
и снова пишет ожидание; встречный обязан покраснеть.

    python <КОНТУР>/vnext-tools/bite-save-phoenix-dryrun-lease.py
    python <КОНТУР>/vnext-tools/bite-save-phoenix-dryrun-lease.py --break no-readonly
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — карточка #505/#624: согласованная копия живой базы

LEASE = mezo_paths.live_scripts() / "lease.py"
SAVE_PHOENIX = mezo_paths.live_scripts() / "save-phoenix.py"
LEASE_ROLE = "TAXO"          # объявление о правке берёт эта роль
CALLER_ROLE = "ZZTEST629"    # холостой/настоящий прогон зовёт эта — не существующая в контуре
TEST_SECTION = "state"

RESULTS = []


def case(title, ok, detail=""):
    RESULTS.append(ok)
    print(("✅ " if ok else "🔴 ") + title + (f"\n   {detail}" if detail else ""))


def wait_rows(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT COUNT(*) FROM tool_lease_waits WHERE tool='save-phoenix.py'"
        ).fetchone()[0]
    finally:
        con.close()


def run_save_phoenix(save_tool, db, stand_env, dry_run):
    env = dict(stand_env)
    env["MEZO_ROLE"] = CALLER_ROLE
    env["MEZO_LEASE_TEST"] = "1"
    cmd = [sys.executable, "-B", str(save_tool), "--role", CALLER_ROLE,
           "--section", TEST_SECTION, "--body", "проба встречного случая #629",
           "--db", str(db)]
    if dry_run:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="база-образец; по умолчанию живая (копируется)")
    ap.add_argument("--break", dest="break_name", choices=["no-readonly"], default=None,
                    help="нарочная поломка: no-readonly — вернуть отказ холостому прогону")
    a = ap.parse_args()

    src = Path(a.db) if a.db else mezo_paths.live_db()
    stand = mezo_stand.new("bite-dryrun-lease-")
    db = stand / "mezosync.db"
    mezo_stand.snapshot_db(src, db)
    # ⚡ КАРТОЧКА #613: испытуемые (lease.py, save-phoenix.py) зовём средой СТЕНДА,
    # не средой вызывающего — иначе MEZO_CONTAINER вызывающего доедет до них.
    stand_env = mezo_stand.stand_env(stand)

    save_tool = SAVE_PHOENIX
    if a.break_name == "no-readonly":
        was = "    readonly = True if args.dry_run else None\n    args.db = str(resolve_db(args.db, __file__, readonly=readonly))"
        became = "    args.db = str(resolve_db(args.db, __file__))"
        text = SAVE_PHOENIX.read_text(encoding="utf-8")
        if was not in text:
            print("⛔ порчу «no-readonly» навести не удалось: образец не найден в коде"); return 2
        # 🪤 ИМЯ ФАЙЛА — ЧАСТЬ ПРЕДМЕТА: lease.check узнаёт инструмент по Path(script_file).name
        # ("save-phoenix.py" в списке --tools объявления), а НЕ по содержимому. Копия под
        # ДРУГИМ именем (напр. save-phoenix.__break__.py) для аренды — ДРУГОЙ, никем не
        # закрытый инструмент: объявление TAXO её не накрывает, и порча молча гаснет —
        # ⑤/⑥ остались бы зелёными ПО ПОСТОРОННЕЙ причине, а не потому что порча не сработала.
        # ⇒ порча ложится в СВОЙ каталог (mezo_stand.new), но ПОД ПРЕЖНИМ ИМЕНЕМ — рядом
        # едут соседи (mezo_paths.py, dryrun.py), без которых инструмент не запустится
        # (mezo_stand.copy_tool/neighbours_of — тот же урок, карточка #572).
        break_dir = mezo_stand.new("bite-dryrun-lease-break-")
        broken_copy = mezo_stand.copy_tool(SAVE_PHOENIX, break_dir)
        broken_copy.write_text(text.replace(was, became, 1), encoding="utf-8")
        save_tool = broken_copy
        print("⚠️ ПОРЧА «no-readonly» ВЗВЕДЕНА — ждём красного в обоих случаях (дырка возвращена)\n")

    # объявление о правке save-phoenix.py — берёт роль TAXO, НЕ CALLER_ROLE
    take = subprocess.run(
        [sys.executable, "-B", str(LEASE), "take", "--role", LEASE_ROLE,
         "--tools", "save-phoenix.py", "--reason", "приёмка встречного случая #629",
         "--minutes", "5", "--db", str(db)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=stand_env)
    rc = take.returncode
    con = sqlite3.connect(str(db))
    lease_id = con.execute(
        "SELECT id FROM tool_leases WHERE role=? AND tools=? ORDER BY id DESC LIMIT 1",
        (LEASE_ROLE, "save-phoenix.py")).fetchone()
    con.close()
    case("① объявление о правке save-phoenix.py взято ролью TAXO на копии",
         rc == 0 and lease_id is not None, f"lease id={lease_id}")

    before = wait_rows(db)
    code, output = run_save_phoenix(save_tool, db, stand_env, dry_run=True)
    after = wait_rows(db)
    case("② холостой прогон (--dry-run) под чужим объявлением — код 0, не 3",
         code == 0, f"код {code}")
    case("③ холостой прогон предупреждает читающего, не отказывает",
         ("ЧИТАЮЩАЯ" in output or "⚖️" in output) and "ОТКАЗ" not in output,
         output.strip().splitlines()[-1] if output.strip() else "")
    case(f"④ холостой прогон НЕ пишет ожидание в tool_lease_waits (строк {before} → {after})",
         before == after)

    code2, output2 = run_save_phoenix(save_tool, db, stand_env, dry_run=False)
    after2 = wait_rows(db)
    case("⑤ настоящая запись (без --dry-run) под тем же объявлением — по-прежнему отказ кодом 3",
         code2 == 3, f"код {code2}")
    case(f"⑥ настоящая запись пишет ожидание в tool_lease_waits (строк {after} → {after2})",
         after2 == after + 1)

    # снять объявление — гигиена (копия одноразовая, но так честнее)
    if lease_id is not None:
        subprocess.run(
            [sys.executable, "-B", str(LEASE), "release", "--role", LEASE_ROLE,
             "--id", str(lease_id[0]), "--db", str(db)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=stand_env)

    n = len(RESULTS); ok = sum(RESULTS)
    if a.break_name:
        red = n - ok
        print(f"\n{'✅ так и надо' if red else '⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ЗЕЛЁНОЕ'}: под порчей красных {red} из {n}")
        return 0 if red else 1
    print(f"\n{'✅ ПРИНЯТА' if ok == n else '🔴 НЕ ПРИНЯТА'} — случаев {n}, зелёных {ok}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
