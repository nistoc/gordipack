#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ОДНА КОМАНДА НА ВСЕ ПРИЁМКИ: зовёт каждый bite-*.py рядом с собой и печатает таблицу.

Зачем. Приёмка, которую надо вспомнить и позвать поимённо, не зовётся. Замер контура:
ручка `--task` существовала всегда и не была позвана НИ РАЗУ за 1724 записки. У постоянных
проверок такой запускатель есть (`guard-all.py`), у приёмок не было — и потому в паке
пролежала СТАРАЯ редакция одной из них, красневшая на верном коде, пока её не сверили руками.

⚖️ ТРИ ИСХОДА, А НЕ ДВА — и это главное свойство этой программы.
  ✅ зелёный ...... свойство держится
  🔴 красный ...... свойство сломано
  ⚠️ НЕ ЗАПУСТИЛАСЬ  приёмке нужен контур/база/аргументы, которых здесь нет
«Не запустилась» НЕ ЕСТЬ «зелёная». Сваливать их вместе — значит печатать «всё чисто» там,
где не проверено ничего: это ложный ноль, самый дорогой сорт вранья механизма.

⛔ Живую базу приёмки открывают сами и по своим правилам; эта программа только зовёт их.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# Приметы того, что приёмка не сломана, а не смогла начаться. Ищем в выводе.
CANT_START = (
    "no such file", "не найден", "unable to open database", "no such table",
    "usage:", "the following arguments are required", "modulenotfounderror",
    "нет базы", "не найдена база", "can't open file",
)


def bites(where: str, only: str):
    names = sorted(f for f in os.listdir(where)
                   if f.startswith("bite-") and f.endswith(".py") and f != os.path.basename(__file__))
    return [n for n in names if not only or only in n]


def verdict(code: int, out: str):
    low = out.lower()
    if code != 0 and any(m in low for m in CANT_START):
        return "⚠️", "не запустилась"
    return ("✅", "свойство держится") if code == 0 else ("🔴", "СЛОМАНО")


def main() -> int:
    ap = argparse.ArgumentParser(description="прогнать все приёмки рядом с этим файлом")
    ap.add_argument("--only", default="", help="подстрока имени: прогнать лишь совпавшие")
    ap.add_argument("--timeout", type=int, default=300, help="потолок на одну приёмку, сек")
    ap.add_argument("--verbose", action="store_true", help="печатать вывод каждой приёмки целиком")
    ap.add_argument("--dir", default=HERE,
                    help="каталог с приёмками (по умолчанию — рядом с этим файлом). "
                         "Нужен, чтобы САМ запускатель можно было проверить на подложенных случаях")
    args = ap.parse_args()

    where = os.path.abspath(args.dir)
    names = bites(where, args.only)
    if not names:
        print("⛔ приёмок не найдено — проверь каталог и --only")
        return 1

    print("=" * 78)
    print(f"ПРИЁМКИ: {len(names)} шт. в {where}")
    print("=" * 78)

    green = red = stuck = 0
    for name in names:
        try:
            r = subprocess.run([sys.executable, os.path.join(where, name)],
                               capture_output=True, text=True, encoding="utf-8",
                               timeout=args.timeout)
            out, code = (r.stdout or "") + (r.stderr or ""), r.returncode
        except subprocess.TimeoutExpired:
            out, code = f"потолок {args.timeout} с исчерпан", 1
            print(f"⚠️  {name:32} не запустилась — потолок времени")
            stuck += 1
            continue

        mark, word = verdict(code, out)
        print(f"{mark}  {name:32} {word}")
        if args.verbose or mark == "🔴":
            tail = [l for l in out.strip().splitlines() if l.strip()][-6:]
            for line in tail:
                print(f"        {line}")
        # 🪤 ПОЛНЫЙ ВЫВОД УПАВШЕЙ ПРИЁМКИ СОХРАНЯЕТСЯ, А НЕ ОБРЕЗАЕТСЯ ДО ХВОСТА.
        # Повод — карточка #150, замер 2026-08-09: общий набор даёт редкий отказ (1 из 7
        # прогонов) на НЕИЗМЕННОМ коде, а в одиночку тот же укус зелёный 8 из 8.
        # Хвоста в шесть строк хватает, чтобы УВИДЕТЬ отказ, и не хватает, чтобы РАЗОБРАТЬ:
        # какое из свойств не выполнилось, видно только в теле вывода.
        # ⇒ Редкое событие нельзя ловить руками: к моменту, когда оно случится, окно
        #   вывода уже уедет. Механизм обязан его ЗАПОМНИТЬ — иначе разбор стоит ожидания.
        if mark in ("🔴", "⚠️"):
            try:
                fail_dir = os.path.join(tempfile.gettempdir(), "bite-all-failures")
                os.makedirs(fail_dir, exist_ok=True)
                stamp = str(int(time.time()))
                path = os.path.join(fail_dir, f"{name}.{stamp}.txt")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(out)
                print(f"        📄 полный вывод сохранён: {path}")
            except OSError as e:
                # ⚖️ Отказ сохранения НЕ роняет прогон и НЕ молчит: молчащая страховка
                #    неотличима от сработавшей.
                print(f"        ⚠️ вывод сохранить не удалось: {e}")
        green += mark == "✅"
        red += mark == "🔴"
        stuck += mark == "⚠️"

    print("-" * 78)
    print(f"держится {green} · сломано {red} · НЕ ПРОВЕРЕНО {stuck}")
    if stuck:
        print("⚠️  «не проверено» — это НЕ «в порядке». Пока такие есть, «всё чисто» сказать нельзя.")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
