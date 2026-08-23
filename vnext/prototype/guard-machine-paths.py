#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРОВЕРКА: публичный образец не несёт путей ОДНОЙ КОНКРЕТНОЙ МАШИНЫ.

Повод — карточка #208. Образец раздают наружу; читающий его человек сидит на своей машине,
и строка `C:\guts\.atlas\...` для него не путь, а чужая раскладка диска. Хуже того, механизм
с таким путём внутри у него просто не работает: он ищет каталог, которого нет.

⚖️ ТРИ РОЛИ ОДНОЙ И ТОЙ ЖЕ СТРОКИ — их нельзя судить одинаково:
  🔴 в КОДЕ (строковый литерал, по которому механизм ходит) — механизм у чужого мёртв;
  🔴 в ИСПОЛНИМОМ ПРИМЕРЕ (шапка модуля, блок команд в доке) — читающий скопирует
     и получит отказ, а решит, что сломан механизм;
  🟡 в КОММЕНТАРИИ И ПРОЗЕ — там путь чаще всего ПРЕДМЕТ УРОКА («вот на этом пути
     сломалось»), и стирать его значит стирать причину решения. Называем, но не красим.

⛔ Заполнители не трогаем: `<ваш контейнер>`, `C:\path\to\...`, `…` — они уже обезличены,
   и требовать от них чистоты значит требовать переписать верный текст ради нуля в замере.

Зовут так (пример намеренно без пути одной машины — им же и меряемся):
    python C:/guts/.atlas/vnext-tools/guard-machine-paths.py            # образец
    python C:/guts/.atlas/vnext-tools/guard-machine-paths.py --root .   # любое дерево
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

# Абсолютный путь Windows или POSIX. Граница слева обязательна: без неё образец ловит
# «http://localhost» и «try:\n» — совпадения, к дискам отношения не имеющие.
МАШИННЫЙ = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/(?:home|Users)/)[^\s\"'`)\]]*")

# Уже обезличенное — не находка. Заполнитель честнее пустоты и его трогать нельзя.
ЗАПОЛНИТЕЛЬ = re.compile(r"<[^>]+>|\.\.\.|…|path[\\/]to|ВАШ|PATH_TO|%\w+%|\$\w+|\{\w*\}",
                         re.IGNORECASE)

def корни_этой_машины() -> list[str]:
    r"""Каталоги, существующие ИМЕННО ЗДЕСЬ. Выводятся, а не впечатываются.

    ⚖️ Почему не «любой абсолютный путь»: в образце законно живут ПРИДУМАННЫЕ примеры
    вида `C:\projects\app\.mezosync` — они никуда не ведут и никого не обманывают, это
    форма вызова. Долг — путь, ведущий в МОЙ диск: он выглядит рабочим и у чужого
    человека молча не работает. Отличает их не вид строки, а происхождение.
    """
    корни = []
    for p in (mezo_paths.container_root(), mezo_paths.template_root(), Path.home()):
        корни.append(str(p))
        if p.parent != p:
            корни.append(str(p.parent))       # соседний контур на том же диске
    return sorted({k.replace("/", "\\").rstrip("\\").lower() for k in корни},
                  key=len, reverse=True)


КОРНИ = корни_этой_машины()


def ведёт_на_эту_машину(кусок: str) -> bool:
    """Путь начинается с одного из корней этой машины — с точностью до вида разделителя."""
    ровно = кусок.replace("/", "\\").lower()
    return any(ровно.startswith(k) for k in КОРНИ)


СМОТРИМ = {".py", ".md", ".sql", ".json", ".ps1", ".sh", ".yml", ".yaml"}
МИМО = {".git", "__pycache__", "node_modules", ".venv", "venv"}


def строки_кода(src: str) -> set[int]:
    """Номера строк, где путь стои́т ВНУТРИ строкового литерала — то есть в самом коде.

    Комментарии в разбор не попадают вовсе: их номеров здесь не будет, и это ровно
    то различение, которое нужно. Файл, который не разбирается, судим как прозу —
    молча объявить его чистым было бы хуже.
    """
    try:
        # Разбор чужих исходников печатает предупреждения про escape-последовательности
        # в ИХ строках. Читающий припишет их этой проверке и пойдёт искать несуществующий
        # дефект — глушим ЧУЖОЙ шум, свой остаётся.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(src)
    except SyntaxError:
        return set()
    из_кода: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            конец = getattr(node, "end_lineno", node.lineno) or node.lineno
            из_кода.update(range(node.lineno, конец + 1))
    return из_кода


# Начало исполнимой строки: то, что читающий скопирует и запустит.
КОМАНДА = re.compile(r"^\s*[$>]?\s*(python|py|dotnet|npm|node|git|cd|powershell|pwsh|sh|bash"
                     r"|sqlite3|terraform|gcloud|docker)\b")


def строки_примеров(src: str) -> set[int]:
    r"""Номера строк, которые читающий СКОПИРУЕТ И ЗАПУСТИТ.

    🪤 Не всякая строка в блоке — команда. Первая редакция красила блок целиком и
    обвинила таблицу замера («этот файл ЕСТЬ, этого НЕТ») — там путь и есть предмет
    записи, а исполнять его никто не собирается. Судим по началу строки: команда
    начинается с имени того, чем её запускают.
    """
    внутри = False
    примеры: set[int] = set()
    for i, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith("```"):
            внутри = not внутри
            continue
        if внутри and КОМАНДА.match(line):
            примеры.add(i)
    return примеры


def разобрать(path: Path):
    """(красные, жёлтые) — списки (строка, номер, текст, почему)."""
    src = path.read_text(encoding="utf-8", errors="ignore")
    код = строки_кода(src) if path.suffix == ".py" else set()
    примеры = строки_примеров(src) if path.suffix == ".md" else set()
    красные, жёлтые = [], []
    for n, line in enumerate(src.splitlines(), 1):
        for m in МАШИННЫЙ.finditer(line):
            кусок = m.group(0)
            if ЗАПОЛНИТЕЛЬ.search(кусок) or not ведёт_на_эту_машину(кусок):
                continue
            if path.suffix == ".py" and n in код:
                красные.append((n, line.strip()[:120], "в коде: у чужого механизм мёртв"))
            elif path.suffix == ".md" and n in примеры:
                красные.append((n, line.strip()[:120],
                                "исполнимый пример: скопируют и получат отказ"))
            else:
                жёлтые.append((n, line.strip()[:120], "проза или комментарий — чаще урок"))
            break
    return красные, жёлтые


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="дерево, которое смотрим (по умолчанию — публичный образец)")
    ap.add_argument("--verbose", action="store_true", help="показывать и жёлтые целиком")
    a = ap.parse_args()

    root = Path(a.root).resolve() if a.root else mezo_paths.template_root()
    if not root.is_dir():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: смотреть нечего — {root}")
        return 2

    файлов = 0
    все_красные, все_жёлтые = [], []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in СМОТРИМ or not p.is_file():
            continue
        if any(часть in МИМО for часть in p.parts):
            continue
        файлов += 1
        к, ж = разобрать(p)
        все_красные += [(p, *x) for x in к]
        все_жёлтые += [(p, *x) for x in ж]

    print("=" * 84)
    print(f"ПУТИ ОДНОЙ МАШИНЫ В ОБРАЗЦЕ — смотрено: {root}")
    print(f"  файлов {файлов} · 🔴 живых {len(все_красные)} · 🟡 в прозе {len(все_жёлтые)}")
    print("=" * 84)

    for p, n, текст, почему in все_красные:
        print(f"🔴 {p.relative_to(root)}:{n}  ({почему})")
        print(f"     {текст}")
    if все_жёлтые:
        показ = все_жёлтые if a.verbose else все_жёлтые[:5]
        for p, n, текст, почему in показ:
            print(f"🟡 {p.relative_to(root)}:{n}  ({почему})")
        если_ещё = len(все_жёлтые) - len(показ)
        if если_ещё:
            print(f"   …ещё {если_ещё} в прозе — смотреть с --verbose")

    print("-" * 84)
    if все_красные:
        print(f"⛔ ЖИВЫХ ПУТЕЙ ОДНОЙ МАШИНЫ: {len(все_красные)} — у чужого человека это "
              "не заработает, и он решит, что сломан механизм.")
    else:
        print("✅ живых путей одной машины нет.")
    if все_жёлтые:
        print(f"🟡 В прозе и комментариях: {len(все_жёлтые)}. Это НЕ долг сам по себе — "
              "в уроке путь и есть предмет. Разбирать поимённо, а не гуртом.")
    return 1 if все_красные else 0


if __name__ == "__main__":
    sys.exit(main())
