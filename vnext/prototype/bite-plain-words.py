#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-plain-words — приёмка: инструменты говорят общепонятными словами (слово владельца).

    python C:/guts/.atlas/vnext-tools/bite-plain-words.py

ПОВОД — СЛОВО ВЛАДЕЛЬЦА, дословно (17.08.2026 08:27 UTC, чат PROTO): «запрещено
использовать выдуманные названия или аллегории к понятиям, но нужно использовать
общепонятные термины». Примеры непонятного, названные владельцем: решето, сторож,
градусник, объём с рубежом, кандидат решета. Повод не выдуман: роль читает вывод,
переписывает слова в свою память — и оттуда они возвращаются в ответ владельцу.

⚖️ ЧТО ЭТА ПРИЁМКА СУДИТ И ЧЕГО НЕ СУДИТ — названо до кода:
  ✅ судит ПОКАЗЫВАЕМЫЙ текст: строки внутри print(...) и тексты --help. Именно их видит роль.
  ⛔ НЕ судит комментарии и пояснения в шапках: их роль читает, только когда правит
     инструмент, и там иносказание — не ложь, а история. Отдельная работа, не эта.
  ⛔ НЕ судит ОБРАЗЦЫ ПОИСКА (re.compile и подобное): они ищут старые слова В ПАМЯТЯХ
     РОЛЕЙ, которые ещё не переписаны. Переименовать образец — ослепить проверку.
     Это тот же класс, что «укус на содержимое списка умирает от правки списка».
  ⛔ НЕ судит имена файлов, флагов и полей базы: у них своя цена смены, и она не эта.

Случаи (различающий = приёмка обязана ответить ИНАЧЕ, а не одинаково):
  ① показываемый текст живых инструментов чист от выдуманных слов          РАЗЛИЧАЮЩИЙ
  ② НАРОЧНАЯ ПОЛОМКА: вернуть слово в печатаемую строку — приёмка краснеет  РАЗЛИЧАЮЩИЙ
  ③ КОНТРОЛЬ ГРАНИЦЫ: то же слово в КОММЕНТАРИИ приёмку НЕ красит          РАЗЛИЧАЮЩИЙ
  ④ КОНТРОЛЬ ГРАНИЦЫ: то же слово в ОБРАЗЦЕ ПОИСКА приёмку НЕ красит       РАЗЛИЧАЮЩИЙ
  ⑤ контроль: приёмка вообще что-то смотрит — файлов и строк больше нуля

⛔ Живого контура НЕ касается: разбор исходников + нарочные поломки во ВРЕМЕННОЙ копии.
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

# Выдуманные слова и иносказания. Список ЖИВОЙ: добавляя своё словцо в вывод, впиши сюда —
# иначе следующее поколение выучит его как норму.
INVENTED = re.compile(
    r"сторож|градусник|решет[аоуы]|решето|витрин|мутант|врезк|аренд[аеуоы]|"
    r"слеп(?:ок|ка|ки|ке|ком)|курсор|прибор|укус[ауео]?|дверь|двери",
    re.I)

SHOWN_CALLS = {"print", "add_argument", "ArgumentParser", "add_parser", "exit"}
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def shown_lines(src: str) -> set[int]:
    """Номера строк, где стоит ПОКАЗЫВАЕМЫЙ роли текст (print / --help / описания)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            nm = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if nm in SHOWN_CALLS:
                for sub in ast.walk(n):
                    if isinstance(sub, (ast.Constant, ast.JoinedStr)):
                        out.add(sub.lineno)
    return out


def scan(root: Path) -> tuple[list[str], int, int]:
    """Находки, сколько файлов и сколько показываемых строк посмотрено."""
    hits, files, lines = [], 0, 0
    for p in sorted(root.rglob("*.py")):
        src = p.read_text(encoding="utf-8", errors="replace")
        shown = shown_lines(src)
        if not shown:
            continue
        files += 1
        for i, line in enumerate(src.splitlines(), 1):
            if i not in shown:
                continue
            lines += 1
            if INVENTED.search(line):
                hits.append(f"{p.name}:{i} {line.strip()[:90]}")
    return hits, files, lines


def main() -> int:
    ok = True
    live = mezo_paths.live_scripts()
    tools = Path(__file__).resolve().parent

    # ── ① ЖИВОЙ ВЫВОД ЧИСТ ────────────────────────────────────────────────────
    hits_live, f1, l1 = scan(live)
    hits_tools, f2, l2 = scan(tools)
    hits = hits_live + hits_tools
    ok &= case("① показываемый текст инструментов чист от выдуманных слов",
               not hits,
               (f"смотрено файлов {f1 + f2}, показываемых строк {l1 + l2}, находок {len(hits)}"
                + ("" if not hits else "\n   " + "\n   ".join(hits[:12]))), differ=True)

    # ── ②③④ НАРОЧНЫЕ ПОЛОМКИ И ГРАНИЦЫ ───────────────────────────────────────
    d = Path(tempfile.mkdtemp(prefix="bite-words-"))
    sand = d / "s"
    sand.mkdir()
    probe = sand / "probe_tool.py"
    base = ('# -*- coding: utf-8 -*-\n'
            'import re\n'
            'def main():\n'
            '    print("всё в порядке: проверок 24")\n')
    probe.write_text(base, encoding="utf-8")
    clean, _, _ = scan(sand)

    probe.write_text(base.replace('print("всё в порядке: проверок 24")',
                                  'print("всё в порядке: сторожей 24")'), encoding="utf-8")
    broken, _, _ = scan(sand)
    ok &= case("② нарочная поломка: слово вернулось в печатаемую строку — приёмка видит",
               not clean and len(broken) == 1,
               f"на чистом {len(clean)} находок, с поломкой {len(broken)} — приёмка, не "
               f"различающая эти два случая, не проверяет ничего", differ=True)

    probe.write_text(base + '    # исторически это называлось сторожем\n', encoding="utf-8")
    in_comment, _, _ = scan(sand)
    ok &= case("③ граница: то же слово в КОММЕНТАРИИ приёмку НЕ красит",
               not in_comment,
               "комментарий роль читает, только когда правит инструмент; там иносказание — "
               "история, а не ложь. Иначе пришлось бы стирать причины решений", differ=True)

    probe.write_text(base + 'PAT = re.compile(r"курсор\\s*\\d+")\n', encoding="utf-8")
    in_pattern, _, _ = scan(sand)
    ok &= case("④ граница: то же слово в ОБРАЗЦЕ ПОИСКА приёмку НЕ красит",
               not in_pattern,
               "образец ищет старое слово в памятях ролей, которые ещё не переписаны: "
               "переименовать его — ослепить проверку, оставив её зелёной", differ=True)

    shutil.rmtree(d, ignore_errors=True)

    # ── ⑤ КОНТРОЛЬ: ПРИЁМКА ВООБЩЕ СМОТРИТ ───────────────────────────────────
    ok &= case("⑤ контроль: приёмке было на что смотреть",
               f1 + f2 > 30 and l1 + l2 > 500,
               f"файлов {f1 + f2}, показываемых строк {l1 + l2} — без этого случая зелёный "
               f"мог бы означать «ничего не нашлось, потому что ничего не искали»")

    print()
    if ok:
        print(f"✅ ОБЩЕПОНЯТНЫЕ СЛОВА — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
