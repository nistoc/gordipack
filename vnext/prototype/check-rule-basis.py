#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРАВИЛО КАНОНА, У КОТОРОГО НЕЛЬЗЯ НАЙТИ ОСНОВАНИЕ.

Предмет. У каждого правила свода есть замок: `owner` — менять вправе только владелец,
`coord` — координатор. Замок говорит, ЧЬЁ решение, и не говорит НИ КОГДА оно принято,
НИ ГДЕ его искать. Основание живёт прозой в теле — если автор вообще его написал.

Чем это платится. Правило, чьё основание не находится, нельзя ни проверить, ни отозвать:
отзывающий не знает, отменяет он живое решение или собственный пересказ. Контур уже платил
за этот класс — предупреждение без срока годности прожило семь недель и учило не верить
давно починенному.

Что считается основанием — ТРИ вопроса, и они не равны по силе:
  КТО  ... сказано «слово владельца» / «по слову» / назван замок
  КОГДА .. есть дата
  ГДЕ .... есть ссылка на записку

🪤 Дата САМА ПО СЕБЕ основанием не считается. В теле правила даты стоят и у замеров, и у
примеров — принять любую за дату решения значило бы принять совпадение формы за совпадение
смысла. Сильным признаком считается только дата РЯДОМ со словом о решении (одно окно текста).
Этот же класс сегодня стоил контуру трёх ложных выводов.

⛔ Живую базу открываем ТОЛЬКО на чтение.
"""
import argparse
import re
import sqlite3
import sys

DEFAULT_DB = r"C:\guts\.atlas\.mezosync\mezosync.db"
WORD = re.compile(r"слов[оаму]\w*\s+владельц\w*|по\s+слову|владелец\s+\w+\s*:", re.I)
# 🪤 РЕШЕНИЕ ПРИНИМАЕТ НЕ ТОЛЬКО ВЛАДЕЛЕЦ. Первая редакция признавала основанием ИСКЛЮЧИТЕЛЬНО
# «слово владельца» — и объявила слепым правило `dowry-facts-carry-source`, у которого основание
# выписано образцово: «замер @RCC, 2026-08-07 17:26 UTC, записка #3345, внесено рукой COORD».
# Оно НАМЕРЕННО не под замком владельца: это рабочая норма роли, и ставить чужой замок на своё
# решение — отдельный дефект, за который контур сегодня и платил (15 слепых «так решил владелец»).
# ⇒ Проверка объявляла негодным ровно то правило, которое написано ПО ЕЁ ЖЕ ТРЕБОВАНИЮ.
# Хуже промаха: она учила, что выписывать основание бесполезно.
ROLES = r"(?:COORD|CORE|ING|STUD|TAXO|RCC|OPSSRE|PROTO|CHROME|владелец)"
# Слово, которым решение ПРИПИСЫВАЮТ кому-то. Без него любое упоминание роли в тексте правила
# засчиталось бы основанием — а роли упоминаются в правилах постоянно, по делу процедуры.
ATTR = re.compile(r"(?:основани\w*|внесен\w*|внес\w*|внёс|по\s+замеру|замер\w*|предложил\w*"
                  r"|решени\w*|норма\s+рол\w*|рукой|источник\w*|автор\w*)", re.I)
DATE = re.compile(r"20\d\d[-.]\d\d[-.]\d\d|\d\d\.\d\d\.20\d\d|\d\d\.\d\d\s+\d\d:\d\d")
NOTE = re.compile(r"(?:записк\w*|нот[аеуы])\s+#\d{1,5}", re.I)
WINDOW = 200          # окно, в котором дата считается относящейся к слову о решении
ATTR_WINDOW = 120     # окно, в котором «замер/внесено/рукой» относится к названной роли


def who_anchors(body: str):
    """Места, где решение КОМУ-ТО ПРИПИСАНО. Владелец словом — или роль с приметой приписки."""
    spans = [(m.start(), m.end()) for m in WORD.finditer(body)]
    for m in re.finditer(ROLES, body):
        lo, hi = max(0, m.start() - ATTR_WINDOW), min(len(body), m.end() + ATTR_WINDOW)
        if ATTR.search(body[lo:hi]):
            spans.append((m.start(), m.end()))
    return spans


def strong_when(body: str) -> bool:
    """Дата рядом с местом, где решение приписано, — а не любая дата в теле."""
    for start, end in who_anchors(body):
        lo, hi = max(0, start - WINDOW), min(len(body), end + WINDOW)
        if DATE.search(body[lo:hi]):
            return True
    return False


def audit(db: str):
    con = sqlite3.connect(f"file:{db.replace(chr(92), '/')}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    rows = con.execute(
        "SELECT rule_key, body, locked_by, version FROM rules ORDER BY rule_key").fetchall()
    con.close()

    out = []
    for key, body, lock, ver in rows:
        b = body or ""
        who = bool(who_anchors(b))
        when = strong_when(b)
        where = bool(NOTE.search(b))
        out.append({"key": key, "lock": lock or "—", "ver": ver,
                    "who": who, "when": when, "where": where,
                    "traceable": who or where})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="правила канона без прослеживаемого основания")
    ap.add_argument("--db", default=DEFAULT_DB, help="база мезосинка (ТОЛЬКО чтение)")
    ap.add_argument("--all", action="store_true", help="печатать все правила, а не только слепые")
    ap.add_argument("--strict", action="store_true",
                    help="вернуть 1 при находках. В обычной работе НЕ нужен: это замер, а не запрет")
    args = ap.parse_args()

    rules = audit(args.db)
    if not rules:
        print("⛔ правил в базе нет — сверять нечего. Это НЕ «чисто».")
        return 1

    blind = [r for r in rules if not r["traceable"]]
    owner_blind = [r for r in blind if r["lock"] == "owner"]
    full = [r for r in rules if r["who"] and r["when"] and r["where"]]

    print("=" * 78)
    print("ОСНОВАНИЕ ПРАВИЛ КАНОНА: можно ли его НАЙТИ, не спрашивая автора")
    print("=" * 78)
    print(f"правил всего .............................. {len(rules)}")
    print(f"названо КТО решил ......................... {sum(r['who'] for r in rules)}")
    print(f"названо КОГДА (дата рядом со словом) ...... {sum(r['when'] for r in rules)}")
    print(f"названо ГДЕ (ссылка на записку) ........... {sum(r['where'] for r in rules)}")
    print(f"названы все три ........................... {len(full)}")
    print()
    print(f"🔴 ОСНОВАНИЕ НЕ НАЙТИ ВОВСЕ ............... {len(blind)}")
    print(f"   из них с замком владельца .............. {len(owner_blind)}")
    print("   — правило объявляет решение владельца и не говорит, когда и где он его принял")

    if blind:
        print()
        print("-" * 78)
        print("СЛЕПЫЕ ПРАВИЛА (замок · версия · ключ)")
        print("-" * 78)
        for r in sorted(blind, key=lambda x: (x["lock"] != "owner", x["key"])):
            mark = "⛔" if r["lock"] == "owner" else "· "
            print(f"  {mark} {r['lock']:6} v{r['ver']:<3} {r['key']}")

    if args.all:
        print()
        print("-" * 78)
        print("ВСЕ ПРАВИЛА: кто · когда · где")
        print("-" * 78)
        for r in rules:
            m = lambda f: "✅" if r[f] else "🔴"
            print(f"  {m('who')}{m('when')}{m('where')}  {r['lock']:6} v{r['ver']:<3} {r['key']}")

    print()
    print("⚖️ ПОТОЛОК: проверка читает ФОРМУ, а не смысл. Она видит, что основание НАЗВАНО,")
    print("   и не может проверить, что оно ВЕРНО. Правило со ссылкой на несуществующую")
    print("   записку она зачтёт — эту дыру закрывает проверка неразрешимых ссылок, не эта.")
    return 1 if (args.strict and blind) else 0


if __name__ == "__main__":
    sys.exit(main())
