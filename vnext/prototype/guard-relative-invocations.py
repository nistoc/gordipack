# -*- coding: utf-8 -*-
"""
guard-relative-invocations.py — ПРОТОТИП гарда R15b: канон не должен учить относительной форме вызова.

ГИПОТЕЗА, КОТОРУЮ ГАРД ПРОВЕРЯЕТ (и которая подтвердилась замером 2026-07-26 06:22 UTC):
роли не «забывают» про смену рабочего каталога — они ДОБРОСОВЕСТНО КОПИРУЮТ форму вызова
из канона. Замер живого контура:

    CLAUDE.md проекта  — 5 относительных вызовов, 0 абсолютных   ← ИСТОЧНИК
    памяти 8 ролей     — 24 относительных, 9 абсолютных
    из них §launcher (пишет ВЛАДЕЛЕЦ)  — абсолютный у 5 из 8
           §rebirth  (роль пишет СЕБЕ) — относительный у 7 из 8

То есть строка, которую роль получает извне, — абсолютная; строка, которую она пишет себе,
скопирована из канона и относительна. 24 копии одной ошибки. Чинить память ролей бессмысленно —
чинить надо источник.

ЧТО ЛОВИТ: вызовы вида `.mezosync/scripts/<имя>.py` (и обратный слэш) в:
  · памятях ролей (phoenix)      — то, что роль прочитает при воскрешении;
  · правилах (rules)             — то, что контур считает нормой;
  · файлах канона (CLAUDE.md и т.п., через --canon).
ЧЕГО НЕ ЛОВИТ (честная граница): что роль НАБЕРЁТ в командной строке. Гард лечит источник
формы, а не руки. Если роль сама придумает относительный вызов — не поймает никто.

Read-only: не пишет ни в БД, ни в файлы. Безопасен для живого контура.

    python guard-relative-invocations.py --db <путь> [--canon C:\\guts\\.atlas\\CLAUDE.md] [--json]
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

# `.mezosync/scripts/x.py` или `.mezosync\scripts\x.py`, НЕ предварённый абсолютным префиксом.
REL = re.compile(r'(?<![\w:\\/.])\.mezosync[\\/]scripts[\\/][\w-]+\.py')
ABS = re.compile(r'[A-Za-z]:[\\/][^\s"\']*[\\/]scripts[\\/][\w-]+\.py')


def scan_text(text):
    return REL.findall(text or ""), ABS.findall(text or "")


def main():
    ap = argparse.ArgumentParser(description="Проверка: относительная форма вызова в каноне и в памятях ролей")
    ap.add_argument("--db", required=True)
    ap.add_argument("--canon", action="append", default=[],
                    help="файл канона (можно несколько раз): CLAUDE.md и т.п.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    findings, rel_total, abs_total = [], 0, 0

    for role, section, body in con.execute(
            "SELECT role, section, body FROM phoenix ORDER BY role, section"):
        rel, abso = scan_text(body)
        rel_total += len(rel); abs_total += len(abso)
        if rel:
            findings.append({"where": f"phoenix/{role}/{section}", "relative": len(rel),
                             "absolute": len(abso), "samples": sorted(set(rel))[:3]})

    for key, body in con.execute("SELECT rule_key, body FROM rules"):
        rel, abso = scan_text(body)
        rel_total += len(rel); abs_total += len(abso)
        if rel:
            findings.append({"where": f"rules/{key}", "relative": len(rel),
                             "absolute": len(abso), "samples": sorted(set(rel))[:3]})
    con.close()

    for c in args.canon:
        p = Path(c)
        if not p.exists():
            findings.append({"where": f"canon/{c}", "relative": 0, "absolute": 0,
                             "samples": ["(файл канона не найден)"]})
            continue
        rel, abso = scan_text(p.read_text(encoding="utf-8", errors="replace"))
        rel_total += len(rel); abs_total += len(abso)
        if rel:
            findings.append({"where": f"canon/{p.name}", "relative": len(rel),
                             "absolute": len(abso), "samples": sorted(set(rel))[:3]})

    if args.json:
        print(json.dumps({"ok": not findings, "relative_total": rel_total,
                          "absolute_total": abs_total, "findings": findings},
                         ensure_ascii=False, indent=2))
        sys.exit(0 if not findings else 1)

    if not findings:
        print(f"✅ относительных вызовов нет (абсолютных: {abs_total})")
        sys.exit(0)

    print(f"⛔ относительная форма вызова: {rel_total} шт. в {len(findings)} местах "
          f"(абсолютных рядом: {abs_total})")
    for f in findings:
        print(f"   {f['where']:28} {f['relative']:2} отн. / {f['absolute']:2} абс.   "
              f"{', '.join(f['samples'])}")
    print("   Роль копирует форму из того, что читает. Правь ИСТОЧНИК (канон или память) —\n"
          "   абсолютный путь; тогда следующая инкарнация скопирует уже его.")
    sys.exit(1)


if __name__ == "__main__":
    main()
