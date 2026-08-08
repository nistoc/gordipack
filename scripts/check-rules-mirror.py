r"""
check-rules-mirror.py — ФАЙЛ С ПРАВИЛАМИ ОТСТАЛ ОТ БАЗЫ.

ЗАЧЕМ. Правила живут в таблице `rules`. Рядом лежит человекочитаемый файл, собранный из неё
`export-rules.py`. Файл не лжёт сам по себе — он лжёт, когда ОТСТАЁТ, и читающий принимает
вчерашнее за действующее, не зная об этом.

ЦЕНА, УЖЕ УПЛАЧЕННАЯ (замер контура-родителя, 2026-08-07):
    генератор существовал, работал и звался РУКАМИ
    последний раз позван ..... 27.07
    зеркало отстало .......... 11 СУТОК
    и на ..................... три ревизии САМОГО ЧИТАЕМОГО правила свода
    нашлось .................. случайно, когда попросили дописать одно правило
Раньше тот же файл ПЯТЬ ЧАСОВ держал отозванное правило как действующее.
⇒ Дисциплина «не забывай пересобирать» не работает. Работают два механизма:
    ① `set-rule.py --apply` зовёт генератор САМ (одно действие вместо двух);
    ② эта проверка — заслон для путей МИМО set-rule: прямой SQL, восстановление базы,
      чужая рука. Первый закрывает ОДИН путь, второй отвечает на вопрос «сошлось ли».

ЧТО СВЕРЯЕТСЯ (и всё — ПОИМЁННО; «файл устарел» без перечня равно молчанию):
    · правило есть в базе, но его НЕТ в файле
    · правило есть в обоих, но в файле версия СТАРШЕ
    · версии равны, а ТЕКСТ различается — правка прошла мимо номера версии
    · правило осталось в файле, а из базы удалено

ПОРТАТИВНОСТЬ. Пути выводятся ИЗ РАСПОЛОЖЕНИЯ СКРИПТА, как во всём тулките:
SCRIPTS = <контур>/.mezosync/scripts, база — <контур>/.mezosync/mezosync.db,
файл — <контур>/.mezosync/generated/sync.rules.md (туда же пишет `export-rules.py`).

СВЕЖАЯ СИСТЕМА. Если правил НЕТ и файла НЕТ — сверять нечего, проверка пропускается
с пометкой и НЕ краснит. Но если правила ЕСТЬ, а файла нет — это «сверить НЕЧЕМ», и это
красное: правила существуют, а прочитать их глазами нельзя.

ЗАПУСК:
    python check-rules-mirror.py                    # пути по умолчанию
    python check-rules-mirror.py --db … --file …    # иные (проверки на копии)
ВЫХОД: 0 — сошлось или сверять нечего · 1 — расхождения · 2 — не смог прочитать базу
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
MEZO = SCRIPTS.parent
DB = MEZO / "mezosync.db"
MIRROR = MEZO / "generated" / "sync.rules.md"

# Заголовок правила в файле: ### `ключ` 🔒замок vN  (с возможной пометкой отзыва)
# 🪤 КЛЮЧ — ЛЮБОЙ ТЕКСТ В ОБРАТНЫХ КАВЫЧКАХ, а не только латиница.
#    Первая редакция требовала [a-z0-9-]+ — и правило с ключом из кириллицы (или с прописной
#    буквой, или с подчёркиванием) НЕ РАСПОЗНАВАЛОСЬ в файле. Проверка вечно объявляла такое
#    правило пропавшим: ложное КРАСНОЕ, которое ничем не лечится и к которому привыкают.
#    Поймано приёмкой на свежем контуре — и заодно вскрыло, что случай «правило вырезано»
#    проходил по НЕВЕРНОЙ причине: ключ не находился в файле и без всякого вырезания.
HEAD = re.compile(r"^###\s+(?:⛔\s*\*\*ОТОЗВАНО\*\*\s*)?`([^`\n]+)`\s*🔒(\w+)\s*v(\d+)\s*$",
                  re.M)


def from_db(db: Path):
    if not db.exists():
        return None
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        rows = con.execute("SELECT rule_key, body, version FROM rules").fetchall()
    except sqlite3.OperationalError:
        con.close()
        return {}
    con.close()
    return {k: (int(v), (b or "").strip()) for k, b, v in rows}


def from_file(path: Path):
    """{ключ: (версия, текст)}."""
    text = path.read_text(encoding="utf-8", errors="replace")
    heads = list(HEAD.finditer(text))
    # Граница тела — СЛЕДУЮЩИЙ ЛЮБОЙ заголовок третьего уровня, а не следующее ПРАВИЛО.
    # Инварианты в этом же файле пишутся без замка и версии, под шаблон правила не подходят
    # и потому не останавливали разбор: последнее правило вбирало в себя весь их раздел.
    any_head = [m.start() for m in re.finditer(r"^###\s", text, re.M)]
    out = {}
    for m in heads:
        end = next((p for p in any_head if p > m.end()), len(text))
        lines = text[m.end():end].rstrip().split("\n")
        while lines and (lines[-1].startswith("## ") or not lines[-1].strip()):
            lines.pop()                       # заголовок раздела — не часть тела правила
        out[m.group(1)] = (int(m.group(3)), "\n".join(lines).strip())
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="файл с правилами отстал от базы")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--file", default=str(MIRROR))
    ap.add_argument("--quiet", action="store_true", help="молчать, когда всё сошлось")
    args = ap.parse_args()

    db = from_db(Path(args.db))
    if db is None:
        print(f"⛔ не нашёл базу: {args.db}")
        return 2
    path = Path(args.file)

    if not path.exists():
        if not db:
            print(f"⏭️  зеркало правил — пропущено: правил нет и файла нет ({path})")
            return 0            # свежая система: сверять нечего, и это не поломка
        print(f"⛔ ЗЕРКАЛО ПРАВИЛ: правил в базе {len(db)}, а файла НЕТ: {path}")
        print("   ⇒ это НЕ «сошлось», а «сверить НЕЧЕМ»: правила есть, прочитать их глазами нельзя.")
        print(f"   Собрать: python {SCRIPTS / 'export-rules.py'} --db {args.db} --apply")
        return 1

    mirror = from_file(path)
    missing = sorted(k for k in db if k not in mirror)
    extra = sorted(k for k in mirror if k not in db)
    older = sorted(k for k in db if k in mirror and mirror[k][0] < db[k][0])
    newer = sorted(k for k in db if k in mirror and mirror[k][0] > db[k][0])
    # Сравнение ПО НАЧАЛУ, а не по равенству: генератор пишет тело правила дословно, а следом
    # своё оформление файла. Требование полного равенства объявляло расхождением именно
    # оформление — три «находки» подряд оказались ошибками разбора, а не расхождением файла.
    # Проверка, чьи находки все до одной ложные, хуже отсутствующей: ей верят один раз.
    # Что при этом НЕ теряется: правку текста в базе начало ловит по-прежнему (доказано
    # подлогом в bite-rules-mirror.py).
    drift = sorted(k for k in db if k in mirror and mirror[k][0] == db[k][0]
                   and not norm(mirror[k][1]).startswith(norm(db[k][1])))

    if not args.quiet:
        print(f"ЗЕРКАЛО ПРАВИЛ: база {len(db)} · файл {len(mirror)} · {path.name}")

    problems = 0
    for title, keys, why in (
            ("ЕСТЬ В БАЗЕ, НЕТ В ФАЙЛЕ", missing,
             "читающий файл НЕ ЗНАЕТ об этих правилах вовсе"),
            ("В ФАЙЛЕ ВЕРСИЯ СТАРШЕ", older,
             "читающий видит прежнюю редакцию и принимает её за действующую"),
            ("ВЕРСИИ РАВНЫ, А ТЕКСТ РАЗНЫЙ", drift,
             "правка прошла мимо номера версии"),
            ("ОСТАЛОСЬ В ФАЙЛЕ, УДАЛЕНО ИЗ БАЗЫ", extra,
             "читающий исполняет то, чего уже нет"),
            ("В ФАЙЛЕ ВЕРСИЯ НОВЕЕ БАЗЫ", newer,
             "при обычной работе не бывает: файл правили руками либо база откатилась")):
        if not keys:
            continue
        problems += len(keys)
        print(f"\n⛔ {title} — {len(keys)}")
        for k in keys:
            v = f"файл v{mirror[k][0]} · база v{db[k][0]}" if k in mirror and k in db else ""
            print(f"   · {k}  {v}")
        print(f"   ⇒ {why}")

    if problems:
        print(f"\n⛔ ЗЕРКАЛО ПРАВИЛ: расхождений {problems}. "
              f"Собрать: python {SCRIPTS / 'export-rules.py'} --db {args.db} --apply")
        return 1
    if not args.quiet:
        print("✅ зеркало правил сошлось с базой")
    return 0


if __name__ == "__main__":
    sys.exit(main())
