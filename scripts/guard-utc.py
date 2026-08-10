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
    args = ap.parse_args()

    files = sorted(Path(args.dir).glob("*.py"))
    real, prose = [], []

    for f in files:
        if f.name == Path(__file__).name:
            continue
        code = code_lines(f)
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not SUSPECT.search(line):
                continue
            if LEGIT.search(line):
                continue
            hit = (f.name, i, line.strip())
            # В КОДЕ или в тексте (комментарий/докстринг)? Оба показываем — но по-разному.
            (real if i in code else prose).append(hit)

    print(f"guard-utc: просмотрено файлов: {len(files) - 1}")

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
