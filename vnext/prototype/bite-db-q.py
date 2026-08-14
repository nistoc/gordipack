#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: db-q читает, отказ подсказывает НАСТОЯЩИЕ имена, пишущий запрос не проходит.

ПОВОД (план 3, этап 1). За одну смену 14.08 имя колонки угадано ТРИЖДЫ; лечение каждый
раз — PRAGMA. Подсказка перенесена В ОТКАЗ: ошибка чинит себя за один шаг, не за два.

⚖️ С ДВУХ СТОРОН:
  · неверное имя — отказ С НАСТОЯЩИМИ колонками (иначе подсказка — украшение);
  · верное имя — ответ (иначе запросник учит не спрашивать);
  · пишущий запрос — отказ ДО исполнения, база бит-в-бит не изменилась;
  · длинный хвост — обрезание НАЗВАНО, не молчит.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ (и это же доказывается хэшем до/после).
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

DBQ = mezo_target.script("db-q.py")
LIVE_DB = mezo_paths.live_db()

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, sql: str, *extra: str) -> tuple[int, str, str]:
    r = subprocess.run([sys.executable, str(DBQ), sql, "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout or "", r.stderr or ""


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    CASES.clear()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "copy.db"
        shutil.copy(LIVE_DB, db)
        before = digest(db)

        rc, out, err = run(db, "SELECT role FROM roles LIMIT 2")
        case("① верное имя — ответ с данными", rc == 0 and "role" in out)

        rc, out, err = run(db, "SELECT role FROM read_cursors")
        case("② угаданная колонка — отказ С НАСТОЯЩИМИ именами",
             rc != 0 and "reader_role" in err, err[:120])

        rc, out, err = run(db, "SELECT x FROM таблицы_нет")
        case("③ несуществующая таблица — отказ со СПИСКОМ таблиц",
             rc != 0 and "roles" in err and "messages" in err)

        rc, out, err = run(db, "UPDATE roles SET lifecycle='dead'")
        case("④ пишущий запрос — отказ ДО исполнения, внятный",
             rc != 0 and "ПИШУЩИЙ" in err)
        rc, out, err = run(db, "DROP TABLE roles")
        case("④b DROP — тот же отказ", rc != 0 and "ПИШУЩИЙ" in err)

        case("⑤ база бит-в-бит НЕ изменилась после всех попыток",
             digest(db) == before)

        rc, out, err = run(db, "SELECT id FROM messages", "--limit", "3")
        case("⑥ обрезание длинного хвоста НАЗВАНО вслух",
             rc == 0 and "ЕСТЬ ЕЩЁ" in err, err[:120])

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}")
    return 0


# ══ МУТАНТЫ (правят живой db-q.py с откатом). Не вставший = ВЫЖИВШИЙ. ══
MUTANTS = {
    "M1-подсказка-колонок-отключена": lambda s: s.replace(
        'if "no such column" in err:', 'if False:'),
    "M2-ворота-письма-сняты": lambda s: s.replace(
        "if head not in READONLY_HEADS:", "if False:"),
    "M3-обрезание-молчит": lambda s: s.replace(
        "if len(rows) > a.limit:", "if False:"),
}


def selftest() -> int:
    print("═══ чистый прогон ═══")
    if main() != 0:
        print("🔴 УКУС КРАСНЫЙ НА ЧИСТОМ — самопроверка невозможна")
        return 1
    survived = 0
    orig = DBQ.read_text(encoding="utf-8")
    for name, mut in MUTANTS.items():
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден — мутант НЕ ВСТАЛ, считаю ВЫЖИВШИМ")
            survived += 1
            continue
        DBQ.write_text(bad, encoding="utf-8")
        try:
            print(f"═══ мутант {name} ═══")
            caught = main() != 0
        finally:
            DBQ.write_text(orig, encoding="utf-8")
        print(f"{'✅ поймал' if caught else '🔴 НЕ ПОЙМАЛ'}: {name}")
        survived += 0 if caught else 1
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} мутантов пойманы")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        sys.exit(selftest())
    sys.exit(main())
