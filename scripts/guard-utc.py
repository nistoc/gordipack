r"""
guard-utc.py — гард правила timestamp-utc-in-sqlite v2: в тулките не должно остаться
конвертации времени в локальную зону.

ИСТОРИЯ (зачем скрипт, а не однострочный grep). 2026-07-16 COORD переводил тулкит на UTC
и проверял себя грепом. Грep соврал ДВАЖДЫ, и оба раза — из-за того, КАК он был написан:
  ① `grep ... | head -12` — вывод обрезался, stats.py по алфавиту шёл ниже и в список
     правки НЕ ПОПАЛ. Это прямое нарушение инварианта VERIFY-AT-SOURCE, который сам же
     COORD и залочил: «грепнул — читай ВСЕ попадания, не первое».
  ② `grep -v "timezone.utc"` — фильтр ложняков выбросил строку
     `dt.replace(tzinfo=datetime.timezone.utc).astimezone()`, где были И то, И другое.
     Гард искал astimezone и сам же его отбрасывал ⇒ ГАРД, КОТОРЫЙ НЕ МОЖЕТ СРАБОТАТЬ.
Итог: гард отрапортовал «чисто», а локальное время жило дальше в 2 файлах и всплыло лишь
потому, что ЧЕЛОВЕК ГЛАЗАМИ увидел «14:18» при стенных «12:33».

ПРИНЦИП, ради которого это скрипт: ИСКЛЮЧАЮЩИЙ ФИЛЬТР В ГАРДЕ ОПАСНЕЕ ОТСУТСТВИЯ ГАРДА —
он даёт ложное спокойствие. Поэтому здесь НИЧЕГО не выбрасывается молча: подозрительное
классифицируется и ПЕЧАТАЕТСЯ, решение принимает человек. Ложняк, который видно, дешевле
пропуска, которого не видно.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/guard-utc.py              # проверить . (или --dir)
    python <КОНТУР>/.mezosync/scripts/guard-utc.py --self-check # проверить САМ РАЗБОРЩИК
    exit 0 — чисто · exit 1 — найдено локальное время в КОДЕ
"""

import argparse
import re
import sys
import tokenize
from pathlib import Path

# Признаки конвертации/наивного времени. Ищем ШИРОКО — сузить всегда успеем, а пропуск дорог.
SUSPECT = re.compile(r"astimezone|localtime|datetime\.now\(\s*\)|\bnow\(\s*\)\.strftime")
# Легитимно: явный UTC.
LEGIT = re.compile(r"now\(\s*(datetime\.)?timezone\.utc\s*\)|utcnow")
# Карточка #384, слово владельца 29.08.2026 12:08 UTC («брать местное время машины, где
# запускается скрипт»): показ «UTC (местное)» разрешён — но конвертация живёт в ОДНОМ
# файле. Его находки печатаются ОТДЕЛЬНО и вслух (принцип этого гарда: ничего не прятать),
# в любом другом файле astimezone по-прежнему красное.
SANCTIONED = "local_time.py"

# ── НАПРАВЛЕНИЕ ПЕРЕВОДА (заявка #21 пакета, замер на живом контуре 2026-09-16) ─────────
# ЗАЧЕМ. До этой правки гард ловил подстроку `astimezone` и НЕ смотрел, КУДА переводят.
# Перевод В UTC — то самое, чего правило и требует, — попадал в красное наравне с переводом
# в местное: четыре строки из восьми были ложными. Красный, горящий всегда, не значит
# ничего, и настоящие четыре в нём тонули.
#
# ПОЧЕМУ НЕ ФИЛЬТРОМ ПО СТРОКЕ. Это ровно ошибка ② из шапки: тогда `grep -v "timezone.utc"`
# выбросил строку, где были И то, И другое. Живой экземпляр лежал в тулките в день правки:
#     .replace(tzinfo=_UTC).astimezone(timezone(timedelta(hours=2)))
# строка УПОМИНАЕТ _UTC и при этом переводит в местное. Любое «в строке есть UTC ⇒ чисто»
# её пропустит. Поэтому судится АРГУМЕНТ вызова, а не строка.
#
# ПОЧЕМУ НЕ ПО ИМЕНИ. `_UTC` — местное имя файла, и само по себе оно ничего не обещает:
# файл волен связать его с чем угодно. Имя принимается, только если В ЭТОМ ЖЕ файле оно
# присвоено именно UTC. Имя без проверенной привязки — не довод, а догадка.
_UTC_LITERAL = re.compile(
    r"^(?:datetime\.|dt\.)?timezone\.utc$"                # timezone.utc · datetime.timezone.utc
    r"|^pytz\.utc$"
    r"|^timezone\(\s*timedelta\(\s*0\s*\)\s*\)$"           # timezone(timedelta(0)) — тот же UTC
)


def utc_aliases(text: str) -> set:
    """Имена, связанные В ЭТОМ ФАЙЛЕ именно с UTC (`_UTC = timezone.utc`)."""
    return {m.group(1)
            for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", text, re.M)
            if _UTC_LITERAL.match(m.group(2))}


def astimezone_calls(line: str) -> list:
    """Для каждого `.astimezone(` в строке — (начало, конец, аргумент).

    Скобки СЧИТАЮТСЯ, а не ищутся образцом: аргумент бывает вложенным
    (`timezone(timedelta(hours=2))`). Вызов, не закрывшийся в этой строке, даёт аргумент
    None и ниже считается НЕизвестным, то есть красным: гард ошибается в сторону крика,
    не в сторону молчания.
    """
    out = []
    for m in re.finditer(r"\.astimezone\(", line):
        depth, j = 1, m.end()
        while j < len(line) and depth:
            if line[j] == "(":
                depth += 1
            elif line[j] == ")":
                depth -= 1
            j += 1
        out.append((m.start(), j, line[m.end():j - 1].strip() if depth == 0 else None))
    return out


def converts_to_utc_only(line: str, aliases: set) -> bool:
    """True, если ВСЁ подозрительное в строке — это перевод В UTC.

    Два условия, и второе не менее важно первого:
      ① у каждого вызова astimezone аргумент — признанный UTC. ПУСТОЙ аргумент =
         зона машины запуска, это НЕ UTC;
      ② после вычёркивания этих вызовов в строке не остаётся других признаков — иначе
         законный сосед прикрыл бы `datetime.now()` на той же строке.
    """
    calls = astimezone_calls(line)
    if not calls:
        return False
    for _, _, arg in calls:
        a = " ".join(arg.split()) if arg else ""
        if not (a and (_UTC_LITERAL.match(a) or a in aliases)):
            return False
    rest, prev = "", 0
    for start, end, _ in calls:
        rest += line[prev:start]
        prev = end
    rest += line[prev:]
    return not SUSPECT.search(rest)


def self_check() -> int:
    """Проверка САМОГО разборщика на строках с известным ответом.

    Заведена потому, что правило «различать направление» иначе осталось бы дисциплиной:
    словом в комментарии, которое ничто не проверяет. Случаи взяты с живого тулкита,
    а не выдуманы; два последних — те самые ловушки, на которых гард уже падал.
    """
    A = {"_UTC"}                                    # имя, которому в файле присвоен timezone.utc
    cases = [
        # (строка, ожидаем «это перевод В UTC», зачем случай)
        ("return dt.astimezone(_UTC), amb, m.group(1)",
         True,  "имя, связанное с UTC в этом же файле"),
        ("x = dt.astimezone(timezone.utc)",
         True,  "литерал timezone.utc"),
        ("x = dt.astimezone(datetime.timezone.utc)",
         True,  "литерал с полным путём"),
        ("x = dt.astimezone(timezone(timedelta(0)))",
         True,  "нулевое смещение — тот же UTC"),
        ("result[role] = utc.astimezone().replace(tzinfo=None)",
         False, "ПУСТОЙ аргумент = зона машины, не UTC"),
        ("loc = dt.astimezone(tz)",
         False, "имя без проверенной привязки — догадка, не довод"),
        (".replace(tzinfo=_UTC).astimezone(timezone(timedelta(hours=2))))",
         False, "ЛОВУШКА ②: строка упоминает _UTC и переводит в МЕСТНОЕ"),
        ("a = dt.astimezone(_UTC); b = datetime.now()",
         False, "ЛОВУШКА: законный сосед не прикрывает naive now() на той же строке"),
        ("stamp = datetime.strptime(s, f).replace(tzinfo=_UTC).astimezone(_UTC",
         False, "скобка не закрылась в строке — неизвестно, значит красное"),
    ]
    bad = 0
    print("guard-utc --self-check: случаев %d" % len(cases))
    for line, want, why in cases:
        got = converts_to_utc_only(line, A)
        ok = got == want
        bad += not ok
        print("   %s ожидалось %-5s получено %-5s · %s"
              % ("✅" if ok else "🔴", want, got, why))
    # Встречная проверка разбора имён: имя, связанное НЕ с UTC, признаваться не должно.
    seen = utc_aliases("_UTC = timezone.utc\n_LOC = timezone(timedelta(hours=2))\n")
    if seen != {"_UTC"}:
        bad += 1
        print("   🔴 разбор имён: ожидалось {'_UTC'}, получено %s" % seen)
    else:
        print("   ✅ разбор имён: _UTC признан, _LOC (смещение +2) — нет")
    if bad:
        print("\n⛔ САМОПРОВЕРКА ПРОВАЛЕНА: %d из %d — разборщику верить нельзя" % (bad, len(cases) + 1))
        return 1
    print("\n✅ самопроверка пройдена: разборщик судит направление, а не наличие вызова")
    return 0


def code_lines(path: Path) -> set:
    """Номера строк, где есть НАСТОЯЩИЙ код (не комментарий и не строковый литерал).

    Лексером, а не эвристикой. Первая версия резала грубо «до первого #» — и падала на
    ДОКСТРИНГАХ: мой же комментарий в stats.py, где слово astimezone упомянуто в разборе
    бага, гард счёл кодом и заорал на чистом тулките. Гард, который кричит на зелёном,
    перестают читать — а значит он перестаёт защищать. tokenize знает, где код, а где
    текст, и не требует от меня угадывать.

    Если файл не токенизируется (битый синтаксис) — считаем КОДОМ ВСЁ: лучше ложная
    тревога, чем пропуск. Гард ошибается в сторону крика, не в сторону молчания.
    """
    try:
        with tokenize.open(path) as fh:
            return {t.start[0] for t in tokenize.generate_tokens(fh.readline)
                    if t.type not in (tokenize.COMMENT, tokenize.STRING,
                                      tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                                      tokenize.DEDENT)}
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError):
        return set(range(1, 10 ** 6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(Path(__file__).parent))
    ap.add_argument("--self-check", action="store_true",
                    help="проверить разборщик направления на случаях с известным ответом")
    args = ap.parse_args()

    if args.self_check:
        sys.exit(self_check())

    files = sorted(Path(args.dir).glob("*.py"))
    real, prose, sanct, to_utc = [], [], [], []

    scanned = 0
    for f in files:
        if f.name == Path(__file__).name:
            continue
        scanned += 1
        code = code_lines(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        aliases = utc_aliases(text)
        for i, line in enumerate(text.splitlines(), 1):
            if not SUSPECT.search(line):
                continue
            if LEGIT.search(line):
                continue
            hit = (f.name, i, line.strip())
            # В КОДЕ или в тексте (комментарий/докстринг)? Оба показываем — но по-разному.
            if i in code and f.name == SANCTIONED:
                sanct.append(hit)          # разрешено поимённо — но НЕ молча
            elif i in code and converts_to_utc_only(line, aliases):
                to_utc.append(hit)         # перевод В UTC — не нарушение, но и не молчание
            else:
                (real if i in code else prose).append(hit)

    print(f"guard-utc: просмотрено файлов: {scanned}")

    if sanct:
        print(f"\n🕐 Разрешено поимённо ({SANCTIONED}, карточка #384, слово владельца "
              f"29.08.2026) — {len(sanct)}; в любом другом файле это было бы красное:")
        for name, i, line in sanct:
            print(f"   {name}:{i}  {line[:96]}")

    if to_utc:
        print(f"\n🧭 Перевод В UTC — {len(to_utc)}. Это то, чего правило и ТРЕБУЕТ, поэтому "
              f"не красное; печатаю, чтобы фильтр ничего не прятал молча:")
        for name, i, line in to_utc:
            print(f"   {name}:{i}  {line[:96]}")

    if prose:
        print(f"\nℹ️  Упоминания в ТЕКСТЕ (комментарии/докстринги) — {len(prose)}. "
              f"Не нарушение; печатаю, чтобы фильтр ничего не прятал молча:")
        for name, i, line in prose:
            print(f"   {name}:{i}  {line[:96]}")

    if real:
        print(f"\n⛔ ЛОКАЛЬНОЕ ВРЕМЯ В КОДЕ — {len(real)}. Правило timestamp-utc-in-sqlite v2:")
        for name, i, line in real:
            print(f"   {name}:{i}  {line[:96]}")
        print("\n   Чинить: UTC везде, суффикс 'UTC' явно. Метка без зоны неотличима от локальной.")
        sys.exit(1)

    print("\n✅ ЧИСТО: конвертации в локальное время в коде нет.")


if __name__ == "__main__":
    main()
