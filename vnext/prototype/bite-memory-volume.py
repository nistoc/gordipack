#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: проверка роста объёма памяти (guard-all ⑯) — из базы, с ростом, честная про базу сравнения.

ПОВОД (план 3 этап 7, 14.08). Разовая чистка памяти без сторожа отрастает обратно молча.
Сторож информационный: объём не грех, видимой должна быть ДЕЛЬТА от рубежа в meta.

⚖️ С ДВУХ СТОРОН:
  · объёмы и дельта — ИЗ БАЗЫ: роль, добавленная в копию, появляется в счёте (не впечатанный список);
  · потерянная база сравнения — сказано вслух, а не молчание и не выдуманный ноль;
  · строка НЕ красит контур: имя «память: объём» не появляется в перечне красных.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: guard-all зовётся с --db на КОПИЯХ.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

GUARD = mezo_target.script("guard-all.py")
LIVE_DB = mezo_paths.live_db()

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run_guard(db: Path) -> str:
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def volume_line(out: str) -> str:
    for ln in out.splitlines():
        if "память: объём" in ln:
            return ln
    return ""


def main() -> int:
    CASES.clear()
    with tempfile.TemporaryDirectory() as tmp:
        # ① Нормальная копия: строка с объёмом и ростом из базы.
        db = Path(tmp) / "a.db"
        shutil.copy(LIVE_DB, db)
        ln = volume_line(run_guard(db))
        m = re.search(r"объём (\d+) симв по (\d+) ролям", ln)
        case("① строка печатает объём и рост из базы", bool(m) and "рост" in ln, ln[:110])
        n_roles = int(m.group(2)) if m else 0

        # ② Роль, добавленная в копию, появляется в счёте — список не впечатан.
        con = sqlite3.connect(db)
        con.execute("INSERT INTO roles (role, lifecycle) VALUES ('ЗОНДОБЪЁМ', 'alive')")
        con.execute("INSERT INTO phoenix (role, section, body, saved_at) "
                    "VALUES ('ЗОНДОБЪЁМ','state','зонд', datetime('now'))")
        con.commit(); con.close()
        ln2 = volume_line(run_guard(db))
        m2 = re.search(r"по (\d+) ролям", ln2)
        case("② подложная роль в копии видна счётом (роли из БАЗЫ)",
             bool(m2) and int(m2.group(1)) == n_roles + 1,
             f"было {n_roles}, стало {m2.group(1) if m2 else '—'}")

        # ③ Потерянная база сравнения — сказано вслух; контур из-за этого НЕ краснеет.
        db3 = Path(tmp) / "b.db"
        shutil.copy(LIVE_DB, db3)
        con = sqlite3.connect(db3)
        con.execute("DELETE FROM meta WHERE key='memory_volume_baseline'")
        con.commit(); con.close()
        out3 = run_guard(db3)
        ln3 = volume_line(out3)
        case("③ потерянная база сравнения — сказано вслух, не ноль", "БАЗЫ СРАВНЕНИЯ НЕТ" in ln3, ln3[:110])
        red_line = next((l for l in out3.splitlines() if "КРАСНЫХ" in l), "")
        case("③b имя «память: объём» НЕ в перечне красных (информационная)",
             "память: объём" not in red_line, red_line[:110])

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}")
    return 0


MUTANTS = {
    "M1-рубежа-нет-молчит": lambda s: s.replace(
        'print("⚠️ память: объём — РУБЕЖА НЕТ (meta.memory_volume_baseline): дельту "\n'
        '                  "мерить не от чего. Это не ноль и не зелёный.")',
        "pass"),
    "M2-строка-объёма-исчезла": lambda s: s.replace(
        '            print(f"✅ память: объём {total_now} симв по {len(vols)} ролям · рост от "',
        '            _ = (f"✅ память: объём {total_now} симв по {len(vols)} ролям · рост от "'),
}


def selftest() -> int:
    print("═══ чистый прогон ═══")
    if main() != 0:
        print("🔴 ПРИЁМКА КРАСНАЯ НА ЧИСТОМ — самопроверка невозможна")
        return 1
    survived = 0
    orig = GUARD.read_text(encoding="utf-8")
    for name, mut in MUTANTS.items():
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден — нарочная поломка НЕ ВСТАЛА, считаю ВЫЖИВШИМ")
            survived += 1
            continue
        GUARD.write_text(bad, encoding="utf-8")
        try:
            print(f"═══ нарочная поломка {name} ═══")
            caught = main() != 0
        finally:
            GUARD.write_text(orig, encoding="utf-8")
        print(f"{'✅ поймал' if caught else '🔴 НЕ ПОЙМАЛ'}: {name}")
        survived += 0 if caught else 1
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        sys.exit(selftest())
    sys.exit(main())
