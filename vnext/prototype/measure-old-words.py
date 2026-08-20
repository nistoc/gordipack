#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure-old-words — сколько прежних слов осталось: в памятях ролей и в пояснениях.

    python <КОНТУР>/vnext-tools/measure-old-words.py           # обе половины
    python <КОНТУР>/vnext-tools/measure-old-words.py --memories  # только памяти
    python <КОНТУР>/vnext-tools/measure-old-words.py --short     # одна строка (для проверок)

ЗАЧЕМ ИНСТРУМЕНТ, А НЕ РАЗОВЫЙ ЗАПРОС: 17–18.08 вывод инструментов переведён на
общепонятные слова (правило `plain-words`). Проверки, ищущие протухшие утверждения,
знают ОБА написания — прежнее и новое; прежнее снимется, когда в памятях его не останется.
Условие снятия названо ЧИСЛОМ, значит число надо уметь получить одной командой, а не
вспоминать «а сколько там было». Замер, который надо помнить, не проводят.

⚖️ ГРАНИЦА: инструмент СЧИТАЕТ, а не судит. Прежнее слово в памяти — не долг сам по себе:
в уроке или надгробии оно уместно («раньше это звалось сторожем»). Красным здесь не светит
ничего; решение о снятии прежних написаний принимает человек, глядя на разбор поимённо.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

WORDS = {
    # 🪤 ГРАНИЦА СЛОВА, А НЕ ПОДСТРОКА. Найдено @COORD 18.08 (записка #3635) на своей же
    # памяти: образец ловил «оСТОРОЖности» — обычное русское слово, к жаргону отношения
    # не имеющее. Замер, считающий верный текст долгом, толкает калечить верный текст.
    "сторож": r"(?<![а-яёa-z])сторож\w*",
    "решето": r"решет[оаеу]\w*",
    "градусник": r"градусник\w*",
    "рубеж": r"рубеж\w*",
    "витрина": r"витрин\w*",
    "слепок": r"слеп(?:ок|ка|ки|ке|ком|ков|кам|ках)\w*",
    "курсор": r"курсор\w*",
    "мутант": r"мутант\w*",
    "укус": r"укус\w*",
    "прибор": r"прибор\w*",
    "врезка": r"врезк\w*",
    # Слово владельца 2026-08-20 05:34 UTC: добавить «ведро». В наших записках оно означало
    # группу, куда что-то относят («попали в ведро», «запихнёт в неверное ведро»). Норма —
    # группа · разряд · набор. ⚖️ Считаем ТОЛЬКО в переносном смысле: ведро как настоящая
    # ёмкость — обычное русское слово, и запрет на него калечил бы верный текст.
    # Слово владельца 2026-08-20 06:38 UTC: «гейт» и придуманные соседним контуром «ворота» —
    # оба про полный прогон проверок. Замер 19.08: в живых правилах 20 мест в шести правилах,
    # в памяти ролей 51 у пяти. Слово живёт не там, где на него смотрели, а в приказных текстах.
    "гейт": r"гейт\w*",
    "ворота": r"ворот[аыу]\w*",
    "ведро (о группе)": r"(?:в|из)\s+(?:это|то|прочe|друго|невернo|нужнo)?\w*\s*ведр[оеау]\w*|"
                        r"ведр[оеау]\w*(?=[^\n]{0,40}(?:групп|разряд|набор|относ|попад))",
    # 🪤 ДВА СЛОВА СЧИТАЮТСЯ ТОЛЬКО РЯДОМ С ПРИЗНАКОМ ИНСТРУМЕНТА. Найдено @TAXO 18.08
    # (записка #3610) при разборе её же памяти: замер считал прежним словом МЕТАФОРУ
    # («строка запрёт преемницу перед дверью, которую никто не толкал») и ПРЕДМЕТНЫЙ
    # ТЕРМИН БАЗЫ («ревизия арендатора» — это tenant, так говорит вся схема ядра).
    # ⚖️ Признак, ловящий образ речи, заставляет калечить верный текст ради нуля — а
    # «не подгоняй текст под проверку» контур держит принципиально. ⇒ сузили.
    "аренда (инструмента)": r"аренд\w*(?=[^\n]{0,40}(?:\.py|инструмент|объявлен))|"
                            r"(?:\.py|инструмент|объявлен)[^\n]{0,40}аренд\w*",
    "дверь (инструмента)": r"двер[ьи]\w*(?=[^\n]{0,40}(?:\.py|инструмент|запуск))|"
                           r"(?:\.py|инструмент|запуск)[^\n]{0,40}двер[ьи]\w*",
}
# 🪤 СЛОВО С ДВУМЯ ХОЗЯЕВАМИ. Найдено @RCC 18.08 (#3605), решено словом владельца 13:56 UTC:
# «витрина» в механизме со-работы запрещена, а в области хранилища данных это обычный термин
# («витрина данных», слой хранилища). Считать её там прежним словом значит требовать калечить
# верный предметный текст ради нуля в замере — а подгонять текст под проверку контур не даёт.
DOMAIN_OK = {
    "витрина": re.compile(r"данн|DWH|BigQuery|SQL|хранилищ|таблиц|витрин\w*\s+данн", re.I),
}
ANY = re.compile("|".join(WORDS.values()), re.I)


def count(name: str, pat: str, text: str) -> int:
    """Сколько раз слово встретилось ПРЕЖНИМ, а не в законном предметном смысле."""
    near = DOMAIN_OK.get(name)
    n = 0
    for m in re.finditer(pat, text or "", re.I):
        if near and near.search(text[max(0, m.start() - 60):m.end() + 60]):
            continue          # рядом стоит признак предметной области — слово законно
        n += 1
    return n


def in_memories(db) -> tuple[int, dict[str, int], dict[str, collections.Counter]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    alive = {r[0].upper() for r in con.execute("SELECT role FROM roles WHERE lifecycle='alive'")}
    per_role: dict[str, int] = collections.Counter()
    detail: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for role, body in con.execute("SELECT role, body FROM phoenix"):
        if role.upper() not in alive:
            continue
        for name, pat in WORDS.items():
            n = count(name, pat, body or "")
            if n:
                per_role[role] += n
                detail[role][name] += n
    con.close()
    return sum(per_role.values()), dict(per_role), detail


def in_comments() -> tuple[int, dict[str, int]]:
    """Прежние слова в пояснениях — по каталогам, чтобы было видно, ЧЬЯ это зона."""
    spec = pathlib.Path(__file__).resolve().parent / "plain-words-comments.py"
    import importlib.util
    sp = importlib.util.spec_from_file_location("pwc", spec)
    pwc = importlib.util.module_from_spec(sp)
    argv, sys.argv = sys.argv, ["measure"]
    sp.loader.exec_module(pwc)
    sys.argv = argv
    per_dir: dict[str, int] = collections.Counter()
    for root, label in ((mezo_paths.live_scripts(), "инструменты контура (.mezosync/scripts)"),
                        (pathlib.Path(__file__).resolve().parent, "инструменты v-next (vnext-tools)")):
        for p in pathlib.Path(root).rglob("*.py"):
            src = p.read_text(encoding="utf-8", errors="replace")
            spans = pwc.editable_spans(src)
            for i, line in enumerate(src.splitlines(), 1):
                if i in spans:
                    per_dir[label] += len(ANY.findall(line[spans[i]:]))
    return sum(per_dir.values()), dict(per_dir)


def мерило(db) -> str:
    """Чем мерено: версия правила-словаря и число слов в самом признаке.

    🪤 ЗАЯВКА @COORD (записка #3702), поддержанная @CHROME (#3704) своим случаем.
    20.08 его вывод вырос со 131 до 181 за час — и НИ ОДНА роль ничего не ухудшила:
    в 06:39 UTC в словарь добавились «гейт» и «ворота». Число было арифметически верным
    и по существу ложным: читалось как «контур деградировал».
    🎯 Класс: ЧИСЛО БЕЗ СВОЕЙ МЕРКИ ЛЖЁТ, ОСТАВАЯСЬ ПРАВИЛЬНЫМ. Лечится не оговоркой
    в записке (её пишет тот, кто и так помнит), а тем, что мерка печатается САМИМ замером.

    ⚖️ Печатаются ДВЕ величины, а не одна: правило и признак живут порознь, и разойтись
    они могут молча. Версия правила без числа слов признака сказала бы «мерено v4»,
    когда признак ещё не знает новых слов, — то есть соврала бы точнее прежнего.
    """
    версия = "?"
    try:
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT version FROM rules WHERE rule_key = 'plain-words'").fetchone()
        con.close()
        if row and row[0] is not None:
            версия = f"v{row[0]}"
    except sqlite3.Error:
        версия = "правило не прочиталось"
    return f"правило plain-words {версия} · слов в признаке {len(WORDS)}"


def main() -> int:
    ap = argparse.ArgumentParser(description="замер прежних слов: памяти ролей и пояснения")
    ap.add_argument("--db", default=None)
    ap.add_argument("--memories", action="store_true", help="только памяти ролей")
    ap.add_argument("--short", action="store_true", help="одна строка — для встраивания")
    a = ap.parse_args()
    # ⚠️ У копии модуля путей в vnext-tools своя точка входа: live_db() знает живую
    # базу, а resolve_db считает корнем каталог инструмента. Разница поймана прогоном.
    db = a.db or mezo_paths.live_db()

    total_mem, per_role, detail = in_memories(db)
    мерка = мерило(db)
    if a.short:
        print(f"прежних слов в памятях: {total_mem} у {len(per_role)} ролей, {мерка} "
              f"(цитаты и уроки среди них законны — разбор поимённо)")
        return 0

    print(f"📊 ПАМЯТИ РОЛЕЙ: прежних слов {total_mem} у {len(per_role)} ролей")
    print(f"   📏 МЕРЕНО: {мерка} — два замера РАЗНЫМИ мерками несравнимы")
    for role, n in sorted(per_role.items(), key=lambda x: -x[1]):
        top = " · ".join(f"{w} {c}" for w, c in detail[role].most_common(4))
        print(f"   {role:8} {n:4}   {top}")
    print("   ⚖️ Прежнее слово в памяти — НЕ долг сам по себе: в уроке, надгробии и цитате")
    print("      снятого совета оно уместно и должно остаться. ⇒ УСЛОВИЕ СНЯТИЯ прежних")
    print("      написаний из проверок — не «ноль любой ценой», а ноль ЖИВЫХ приказов")
    print("      старыми словами; это разбирается поимённо, а не счётом (@TAXO #3610).")
    if a.memories:
        return 0

    total_c, per_dir = in_comments()
    print(f"\n📊 ПОЯСНЕНИЯ ИНСТРУМЕНТОВ: прежних слов {total_c}")
    for label, n in sorted(per_dir.items(), key=lambda x: -x[1]):
        print(f"   {n:4}  {label}")
    print("   ⚖️ Это места, которые машина отложила как рискованные (согласование) либо")
    print("      многозначные. Их правит ВЛАДЕЛЕЦ КАТАЛОГА, а не роль-читатель.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
