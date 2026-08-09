# -*- coding: utf-8 -*-
"""
fix-relative-invocations.py — ПРОТОТИП миграции под R15b: перевести канон и слепки
на АБСОЛЮТНУЮ форму вызова.

Парная вещь к `guard-relative-invocations.py`: гард показывает, фиксер чинит ИСТОЧНИК.
Смысл — не «поправить тексты», а прекратить воспроизводство ошибки: роль копирует форму
из того, что читает, поэтому следующая инкарнация скопирует уже абсолютный путь.

⛔ ПО УМОЛЧАНИЮ — СУХОЙ ПРОГОН (ничего не пишет). Запись только с явным `--apply`.
⛔ ОТКАЗЫВАЕТСЯ работать по живой БД без `--i-know-its-live`: живой субстрат — зона COORD,
   не моя. Я предъявляю инструмент и замер; применяет владелец/COORD по слову.

    python fix-relative-invocations.py --db <песочница>            # сухой прогон
    python fix-relative-invocations.py --db <песочница> --apply    # записать
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()
DEFAULT_PREFIX = str(mezo_paths.container_root())
REL = re.compile(r'(?<![\w:\\/.])\.mezosync([\\/])scripts([\\/])([\w-]+\.py)')


def to_abs(prefix: str, m: re.Match) -> str:
    # Разделитель сохраняем тот, что был в тексте: не навязываем стиль, меняем только базу.
    s1, s2, name = m.group(1), m.group(2), m.group(3)
    base = prefix.rstrip("\\/")
    sep = "\\" if (s1 == "\\" or s2 == "\\") else "/"
    return f"{base}{sep}.mezosync{s1}scripts{s2}{name}"


def main():
    ap = argparse.ArgumentParser(description="Перевести вызовы в слепках/правилах на абсолютный путь")
    ap.add_argument("--db", required=True)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="корень контейнера")
    ap.add_argument("--apply", action="store_true", help="записать (иначе сухой прогон)")
    ap.add_argument("--i-know-its-live", action="store_true",
                    help="разрешить работу по боевой БД (нужно живое слово владельца)")
    args = ap.parse_args()

    db = Path(args.db).resolve()
    if db == LIVE_DB.resolve() and not args.i_know_its_live:
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Правка живого субстрата — зона COORD "
                 "и требует слова владельца. Прогони по песочнице.")

    con = sqlite3.connect(str(db))
    changes = []

    for table, keycols, bodycol in (("phoenix", ("role", "section"), "body"),
                                    ("rules", ("rule_key",), "body")):
        cols = ", ".join(keycols)
        for row in con.execute(f"SELECT {cols}, {bodycol} FROM {table}").fetchall():
            *keys, body = row
            new = REL.sub(lambda m: to_abs(args.prefix, m), body or "")
            if new != body:
                n = len(REL.findall(body))
                changes.append((table, keycols, keys, new, n))

    total = sum(c[4] for c in changes)
    print(f"{'ПРИМЕНЯЮ' if args.apply else 'СУХОЙ ПРОГОН'}: {total} вызовов в {len(changes)} записях "
          f"→ абсолютная форма (префикс {args.prefix})")
    for table, keycols, keys, _, n in changes:
        print(f"   {table}/{'/'.join(str(k) for k in keys):24} {n} шт.")

    if args.apply and changes:
        for table, keycols, keys, new, _ in changes:
            where = " AND ".join(f"{c}=?" for c in keycols)
            con.execute(f"UPDATE {table} SET body=? WHERE {where}", (new, *keys))
        con.commit()
        print(f"✅ записано. Проверь гардом: guard-relative-invocations.py --db {db}")
    elif not changes:
        print("✅ менять нечего — относительной формы нет")
    con.close()


if __name__ == "__main__":
    main()
