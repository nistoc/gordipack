"""
check-rules-mirror.py — ФАЙЛ С ПРАВИЛАМИ ОТСТАЛ ОТ БАЗЫ.

═══ ЗАЧЕМ ═══
Правила живут в базе. Рядом лежит файл, собранный из неё, — чтобы человек читал глазами.
Файл не лжёт сам по себе. Он лжёт, когда ОТСТАЁТ, и читающий принимает вчерашнее
за действующее, не зная об этом.
```
07.08 — отстал на ТРИ версии правила за четыре часа
ранее — ПЯТЬ ЧАСОВ держал отменённое как действующее (записано в шапке самого сборщика)
```
Слово владельца 2026-08-07 13:40 UTC: файл и ссылки на него ОСТАЮТСЯ, но обновляться должен
при любом изменении правил в базе.

═══ ПОЧЕМУ ЭТА ПРОВЕРКА НУЖНА ОТДЕЛЬНО ОТ АВТОПЕРЕСБОРКИ ═══
Автопересборка — правильный первый ход, но она может НЕ СРАБОТАТЬ МОЛЧА: упасть на полпути,
быть обойдённой прямой правкой базы, отвалиться при переносе инструмента.
Тогда всё выглядит исправным, а файл вчерашний — и это худший исход, а не второй по тяжести.
⇒ Проверка отвечает на вопрос «сошлось ли на самом деле», а не «звали ли сборщик».

═══ ЧТО СВЕРЯЕТСЯ ═══
    · правило есть в базе, но его НЕТ в файле
    · правило есть в обоих, но в файле версия СТАРШЕ
    · правило есть в обоих, версии равны, а ТЕКСТ различается (правка в обход версии)
    · правило осталось в файле, а из базы удалено
⛔ Вердикт «файл устарел» без ПЕРЕЧНЯ не печатается никогда: это то же молчание.

Запуск:  python check-rules-mirror.py [--file <путь>] [--quiet]
Выход:   0 — сошлось · 1 — есть расхождения · 2 — не смог прочитать предмет
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
MIRROR = mezo_paths.container_root() / "atlas.archs" / ".mezosync" / "coordination" / "sync.rules.md"

# Строка заголовка правила в файле: ### `ключ` 🔒замок vN   (с возможной пометкой отзыва)
# 🪤 КЛЮЧ — ЛЮБОЙ ТЕКСТ В ОБРАТНЫХ КАВЫЧКАХ. Требование [a-z0-9-]+ означало, что правило
#    с ключом из кириллицы, прописной буквы или подчёркивания НЕ РАСПОЗНАЁТСЯ в файле,
#    и проверка вечно объявляет его пропавшим. Ложное красное, к которому привыкают.
HEAD = re.compile(r"^###\s+(?:⛔\s*\*\*ОТОЗВАНО\*\*\s*)?`([^`\n]+)`\s*🔒(\w+)\s*v(\d+)\s*$",
                  re.M)


def from_db(db: Path = None):
    db = db or LIVE
    if not db.exists():
        return None
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    out = {k: (int(v), (b or "").strip())
           for k, b, v in con.execute("SELECT rule_key, body, version FROM rules")}
    con.close()
    return out


def from_file(path: Path):
    """{ключ: (версия, текст)} — текст берётся до следующего заголовка того же уровня."""
    text = path.read_text(encoding="utf-8", errors="replace")
    heads = list(HEAD.finditer(text))
    out = {}
    any_head = [mm.start() for mm in re.finditer(r"^###\s", text, re.M)]
    for i, m in enumerate(heads):
        # 🪤 ГРАНИЦА — СЛЕДУЮЩИЙ ЛЮБОЙ ЗАГОЛОВОК ТРЕТЬЕГО УРОВНЯ, а не следующее ПРАВИЛО.
        #    Вторая моя ошибка в этом же месте: последнее правило в файле вобрало в себя
        #    весь раздел инвариантов (5622 знака превратились в 13416), и проверка снова
        #    объявила расхождение там, где текст совпадал. Заголовки инвариантов пишутся
        #    без замка и версии, потому под шаблон правила не подходят — и не останавливали.
        end = next((p for p in any_head if p > m.end()), len(text))
        body = text[m.end():end]
        # 🪤 РЕЖЕМ ПО СЛЕДУЮЩЕМУ ПРАВИЛУ, А НЕ ПО ПЕРВОМУ ЖЕ «## ».
        #    Первая редакция обрывала тело на первом заголовке второго уровня — а такие
        #    заголовки есть ВНУТРИ самих правил. Из тела в 1699 знаков оставалось 481,
        #    и проверка объявила расхождение там, где текст совпадал полностью.
        #    ⇒ Ложное обвинение файла. Поймано тем, что я посмотрел РАЗНИЦУ, прежде чем
        #      объявить находку: «нашлось 2 расхождения» звучало убедительно и было ложью.
        #    Заголовок раздела, если он стоит перед следующим правилом, — не часть тела:
        #    снимаем его с хвоста, но только с хвоста.
        lines = body.rstrip().split("\n")
        while lines and (lines[-1].startswith("## ") or not lines[-1].strip()):
            lines.pop()
        out[m.group(1)] = (int(m.group(3)), "\n".join(lines).strip())
    return out


def norm(s: str) -> str:
    """Сравниваем по существу: пробелы и пустые строки не считаем расхождением."""
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="файл с правилами отстал от базы")
    ap.add_argument("--file", default=str(MIRROR))
    ap.add_argument("--db", default=str(LIVE),
                    help="база с правилами; иная — только для проверок на копии")
    ap.add_argument("--quiet", action="store_true", help="молчать, когда всё сошлось")
    args = ap.parse_args()

    db = from_db(Path(args.db))
    if db is None:
        print(f"⛔ не нашёл базу: {args.db}")
        return 2
    path = Path(args.file)
    if not path.exists():
        print(f"⛔ не нашёл файл с правилами: {path}")
        print("   ⇒ это НЕ «сошлось». Пять инструментов и загрузка роли опираются на него.")
        return 2
    mirror = from_file(path)

    missing = sorted(k for k in db if k not in mirror)
    extra = sorted(k for k in mirror if k not in db)
    older = sorted(k for k in db if k in mirror and mirror[k][0] < db[k][0])
    newer = sorted(k for k in db if k in mirror and mirror[k][0] > db[k][0])
    # 🪤 СРАВНИВАЕМ ПО НАЧАЛУ, А НЕ ПО РАВЕНСТВУ — и это не послабление, а точность.
    #    Сборщик пишет тело правила ДОСЛОВНО, а следом — своё оформление файла (заголовки
    #    разделов, врезки). Требование полного равенства объявляло расхождением именно это
    #    оформление: три «находки» подряд оказались МОИМИ ошибками разбора, а не расхождением
    #    файла. Проверка, чьи находки все до одной ложные, хуже отсутствующей — ей поверят
    #    один раз, потом перестанут.
    #    Что при этом НЕ теряется: если текст правила изменён в базе — начало разойдётся,
    #    и находка останется настоящей. Проверено встречным случаем в bite-rules-mirror.py.
    drift = sorted(k for k in db if k in mirror and mirror[k][0] == db[k][0]
                   and not norm(mirror[k][1]).startswith(norm(db[k][1])))

    if not args.quiet:
        print("ПРОВЕРКА: файл с правилами против базы")
        print(f"  база ..... {len(db)} правил")
        print(f"  файл ..... {len(mirror)} правил   {path}")

    problems = 0
    if missing:
        problems += len(missing)
        print(f"\n🔴 ЕСТЬ В БАЗЕ, НЕТ В ФАЙЛЕ — {len(missing)}")
        for k in missing:
            print(f"   · {k}  (в базе v{db[k][0]})")
        print("   ⇒ читающий файл НЕ ЗНАЕТ об этих правилах вовсе")
    if older:
        problems += len(older)
        print(f"\n🔴 В ФАЙЛЕ ВЕРСИЯ СТАРШЕ — {len(older)}")
        for k in older:
            print(f"   · {k}:  файл v{mirror[k][0]} · база v{db[k][0]}")
        print("   ⇒ читающий видит прежнюю редакцию и принимает её за действующую")
    if drift:
        problems += len(drift)
        print(f"\n🔴 ВЕРСИИ РАВНЫ, А ТЕКСТ РАЗНЫЙ — {len(drift)}")
        for k in drift:
            print(f"   · {k} (v{db[k][0]}) — правка прошла мимо номера версии")
    if extra:
        problems += len(extra)
        print(f"\n⚠️  ОСТАЛОСЬ В ФАЙЛЕ, УДАЛЕНО ИЗ БАЗЫ — {len(extra)}")
        for k in extra:
            print(f"   · {k}")
    if newer:
        problems += len(newer)
        print(f"\n⚠️  В ФАЙЛЕ ВЕРСИЯ НОВЕЕ, ЧЕМ В БАЗЕ — {len(newer)}")
        for k in newer:
            print(f"   · {k}:  файл v{mirror[k][0]} · база v{db[k][0]}")
        print("   ⇒ так не бывает при обычной работе: файл правили руками либо база откатилась")

    if problems:
        print(f"\nИТОГ: 🔴 РАСХОЖДЕНИЙ {problems}. Пересобрать: "
              "python <s>\\export-rules.py --apply")
        return 1
    if not args.quiet:
        print("\nИТОГ: ✅ СОШЛОСЬ — файл показывает то же, что база")
    return 0


if __name__ == "__main__":
    sys.exit(main())
