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

# 🪤 НЕ ТОЛЬКО print. Найдено @RCC 18.08 (записка #3605): machine_layer.py ничего не
# печатает сам — он СОБИРАЕТ строки в список и отдаёт наружу, поэтому пять показываемых
# человеку строк с прежними словами были для приёмки невидимы, и она была зелёной.
# ⚖️ Класс: приёмка судила ФОРМУ ВЫЗОВА, а не НАЗНАЧЕНИЕ текста. Добавлено накопление
# в список с говорящим именем — этого достаточно и не тянет за собой образцы поиска.
SHOWN_CALLS = {"print", "add_argument", "ArgumentParser", "add_parser", "exit"}
COLLECTORS = {"out", "lines", "block", "blocks", "parts", "rows", "report", "text"}

# 🪤 И ТРЕТИЙ РОД, найденный на себе 19.08: СВОЙ ПЕЧАТАЮЩИЙ ПОМОЩНИК. Почти каждая приёмка
# контура печатает не сама, а через собственную функцию (`case(title, ok, detail)`), и весь
# её текст — то есть текст, который человек читает чаще всего, — для этой проверки был
# невидим. Замер в тот день: 44 запрещённых слова в 10 инструментах при ЗЕЛЁНОЙ проверке.
# ⚖️ Лечим НЕ списком имён (список — это опять «проверяем перечисленное»), а РАЗБОРОМ:
# печатающей считается функция, которая печатает СВОЙ ЖЕ параметр. Это выводится из кода
# и работает для чужих помощников с любыми именами.
CASES = DIFFER = 0


def printing_helpers(tree: ast.AST) -> set[str]:
    """Имена функций модуля, которые печатают собственный параметр.

    Контроль обратного: функция, которая параметры только копит или возвращает, сюда
    НЕ попадает — иначе признак начнёт считать показываемым любой текст в любом вызове.
    """
    names: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in list(fn.args.args) + list(fn.args.kwonlyargs)}
        if not params:
            continue
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print"):
                continue
            if any(isinstance(s, ast.Name) and s.id in params for s in ast.walk(n)):
                names.add(fn.name)
                break
    return names


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
    helpers = printing_helpers(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            nm = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            shown = nm in SHOWN_CALLS or nm in helpers
            if nm == "append" and isinstance(n.func, ast.Attribute):
                recv = getattr(n.func.value, "id", None)
                shown = shown or (recv in COLLECTORS)
            if shown:
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

    # -- (6) ТЕКСТ, КОТОРЫЙ ИНСТРУМЕНТ НЕ ПЕЧАТАЕТ, А ОТДАЁТ НАРУЖУ ---------
    # 🪤 Найдено @RCC 18.08 (записка #3605): machine_layer.py собирает строки в список и
    # возвращает их — печатает уже другой инструмент. Приёмка судила ФОРМУ ВЫЗОВА, а не
    # НАЗНАЧЕНИЕ текста, и весь файл был для неё невидим, оставаясь при этом зелёным.
    collected = ("# -*- coding: utf-8 -*-@def build():@    out = []@"
                 '    out.append("всё в порядке: %s 24")@    return out@').replace("@", chr(10))
    probe.write_text(collected % "проверок", encoding="utf-8")
    coll_clean, _, _ = scan(sand)
    probe.write_text(collected % "сторожей", encoding="utf-8")
    coll_broken, _, _ = scan(sand)
    ok &= case("⑥ собранный в список и отданный наружу текст приёмка тоже судит",
               not coll_clean and len(coll_broken) == 1,
               "на чистом %d находок, с поломкой %d — до 18.08 оба случая были зелёными: "
               "инструмент, отдающий строки вместо печати, приёмку не касался вовсе"
               % (len(coll_clean), len(coll_broken)), differ=True)

    # ── ⑦ СВОЙ ПЕЧАТАЮЩИЙ ПОМОЩНИК И ЕГО ГРАНИЦА (найдено на себе 19.08) ─────
    # Почти каждая приёмка контура печатает через собственную функцию, а не через print.
    # Пока разбор знал только print, весь этот текст был невидим: 44 запрещённых слова
    # в 10 инструментах при зелёной проверке. Второй случай — ГРАНИЦА: помощник, который
    # параметры только копит, показываемым текст НЕ делает, иначе признак покрасит всё.
    helper_shown = sand / "helper_tool.py"
    helper_shown.write_text(
        '# -*- coding: utf-8 -*-\n'
        'def case(title, detail):\n'
        '    print(title)\n'
        '    print("   " + detail)\n'
        'def main():\n'
        '    case("итог: сторож зелёный", "подробность")\n',
        encoding="utf-8")
    helper_hits, _, _ = scan(sand)
    ok &= case("⑦ текст, уходящий в СВОЙ печатающий помощник, приёмка судит",
               any("helper_tool.py" in h for h in helper_hits),
               "почти весь читаемый человеком текст приёмок идёт не в print, а в case(...): "
               "пока разбор знал только print, он был невидим целиком", differ=True)

    helper_shown.write_text(
        '# -*- coding: utf-8 -*-\n'
        'def collect(title, detail):\n'
        '    return [title, detail]\n'
        'def main():\n'
        '    rows = collect("итог: сторож зелёный", "подробность")\n'
        '    return len(rows)\n',
        encoding="utf-8")
    quiet_hits, _, _ = scan(sand)
    ok &= case("⑦-бис ГРАНИЦА: помощник, который НЕ печатает, показываемым текст не делает",
               not any("helper_tool.py" in h for h in quiet_hits),
               "печатающая функция узнаётся по тому, что печатает СВОЙ параметр, а не по "
               "имени: без этой границы признак объявил бы показываемым любой текст в "
               "любом вызове и стал бы шумным", differ=True)
    helper_shown.unlink()

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
