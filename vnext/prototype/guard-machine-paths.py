#!/usr/bin/env python
# SURFACES: template-docs
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
    python <КОНТУР>/vnext-tools/guard-machine-paths.py            # образец
    python <КОНТУР>/vnext-tools/guard-machine-paths.py --root .   # любое дерево
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

# Абсолютный путь Windows или POSIX. Граница слева обязательна: без неё образец ловит
# «http://localhost» и «try:\n» — совпадения, к дискам отношения не имеющие.
MACHINE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/(?:home|Users)/)[^\s\"'`)\]]*")

# Уже обезличенное — не находка. Заполнитель честнее пустоты и его трогать нельзя.
PLACEHOLDER_RE = re.compile(r"<[^>]+>|\.\.\.|…|path[\\/]to|ВАШ|PATH_TO|%\w+%|\$\w+|\{\w*\}",
                         re.IGNORECASE)

def this_machine_roots() -> list[str]:
    r"""Каталоги, существующие ИМЕННО ЗДЕСЬ. Выводятся, а не впечатываются.

    ⚖️ Почему не «любой абсолютный путь»: в образце законно живут ПРИДУМАННЫЕ примеры
    вида `C:\projects\app\.mezosync` — они никуда не ведут и никого не обманывают, это
    форма вызова. Долг — путь, ведущий в МОЙ диск: он выглядит рабочим и у чужого
    человека молча не работает. Отличает их не вид строки, а происхождение.
    """
    roots = []
    for p in (mezo_paths.container_root(), mezo_paths.template_root(), Path.home()):
        roots.append(str(p))
        if p.parent != p:
            roots.append(str(p.parent))       # соседний контур на том же диске
    return sorted({k.replace("/", "\\").rstrip("\\").lower() for k in roots},
                  key=len, reverse=True)


ROOTS = this_machine_roots()


def leads_to_this_machine(piece: str) -> bool:
    """Путь начинается с одного из корней этой машины — с точностью до вида разделителя."""
    norm = piece.replace("/", "\\").lower()
    return any(norm.startswith(k) for k in ROOTS)


WATCHED_SUFFIXES = {".py", ".md", ".sql", ".json", ".ps1", ".sh", ".yml", ".yaml",
           ".paths", ".txt", ".cfg", ".ini", ".toml"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
# В git-режиме белого списка нет — есть чёрный: бинарное не читаем, ОСТАЛЬНОЕ судим всё.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".db", ".sqlite", ".pyc", ".exe",
            ".dll", ".zip", ".gz", ".7z", ".woff", ".woff2", ".ttf", ".pdf", ".bak"}
# Файл-КОНФИГ: путь в нём не проза и не пример — его ИСПОЛНЯЕТ механизм. Любая находка красная.
CONFIG_SUFFIXES = {".paths", ".cfg", ".ini", ".toml", ".json", ".yml", ".yaml"}


def files_to_judge(root: Path):
    """Что судим — и почему двумя ветвями (карточка #248: область у́же предмета).

    В git-репозитории судим ровно ПУБЛИКУЕМОЕ (`git ls-files`): local.paths и прочее
    из .gitignore наружу не уезжает и долгом образца НЕ является — прежний обход по
    диску обвинял законный локальный файл. И наоборот: файл ЛЮБОГО расширения,
    попавший в git, судится — белый список расширений пропускал `.paths` молча,
    и попади он в git, никто бы не узнал.
    Вне git (--root на живое дерево) — прежний обход по белому списку."""
    if (root / ".git").exists():
        try:
            out = subprocess.run(["git", "-C", str(root), "ls-files"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 timeout=60, check=True).stdout
            files = [root / f for f in out.splitlines()
                     if (root / f).is_file() and (root / f).suffix.lower() not in BINARY_SUFFIXES]
            return files, "публикуемое: git ls-files минус бинарные"
        except (OSError, subprocess.SubprocessError) as e:
            print(f"⚠️ git ls-files не удался ({e}) — сужаюсь до обхода по расширениям")
    files = [p for p in sorted(root.rglob("*"))
             if p.is_file() and p.suffix.lower() in WATCHED_SUFFIXES
             and not any(part in SKIP_DIRS for part in p.parts)]
    return files, "обход диска по белому списку расширений"


def code_lines(src: str) -> set[int]:
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
    in_code: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            in_code.update(range(node.lineno, end + 1))
    return in_code


# Начало исполнимой строки: то, что читающий скопирует и запустит.
COMMAND_RE = re.compile(r"^\s*[$>]?\s*(python|py|dotnet|npm|node|git|cd|powershell|pwsh|sh|bash"
                     r"|sqlite3|terraform|gcloud|docker)\b")


def example_lines(src: str) -> set[int]:
    r"""Номера строк, которые читающий СКОПИРУЕТ И ЗАПУСТИТ.

    🪤 Не всякая строка в блоке — команда. Первая редакция красила блок целиком и
    обвинила таблицу замера («этот файл ЕСТЬ, этого НЕТ») — там путь и есть предмет
    записи, а исполнять его никто не собирается. Судим по началу строки: команда
    начинается с имени того, чем её запускают.
    """
    inside = False
    examples: set[int] = set()
    for i, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside and COMMAND_RE.match(line):
            examples.add(i)
    return examples


def judge_file(path: Path):
    """(красные, жёлтые) — списки (строка, номер, текст, почему)."""
    src = path.read_text(encoding="utf-8", errors="ignore")
    code = code_lines(src) if path.suffix == ".py" else set()
    examples = example_lines(src) if path.suffix == ".md" else set()
    reds, yellows = [], []
    for n, line in enumerate(src.splitlines(), 1):
        for m in MACHINE_PATH_RE.finditer(line):
            piece = m.group(0)
            if PLACEHOLDER_RE.search(piece) or not leads_to_this_machine(piece):
                continue
            if path.suffix.lower() in CONFIG_SUFFIXES:
                reds.append((n, line.strip()[:120],
                                "рабочий конфиг: путь исполняет механизм, не читатель"))
            elif path.suffix == ".py" and n in code:
                reds.append((n, line.strip()[:120], "в коде: у чужого механизм мёртв"))
            elif path.suffix == ".md" and n in examples:
                reds.append((n, line.strip()[:120],
                                "исполнимый пример: скопируют и получат отказ"))
            else:
                yellows.append((n, line.strip()[:120], "проза или комментарий — чаще урок"))
            break
    return reds, yellows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="дерево, которое смотрим (по умолчанию — публичный образец)")
    ap.add_argument("--verbose", action="store_true", help="показывать и жёлтые целиком")
    a = ap.parse_args()

    root = Path(a.root).resolve() if a.root else mezo_paths.template_root()
    if not root.is_dir():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: смотреть нечего — {root}")
        return 2

    files, source_note = files_to_judge(root)
    all_reds, all_yellows = [], []
    for p in files:
        reds_here, yellows_here = judge_file(p)
        all_reds += [(p, *x) for x in reds_here]
        all_yellows += [(p, *x) for x in yellows_here]

    print("=" * 84)
    print(f"ПУТИ ОДНОЙ МАШИНЫ В ОБРАЗЦЕ — смотрено: {root}")
    print(f"  файлов {len(files)} ({source_note}) · 🔴 живых {len(all_reds)} "
          f"· 🟡 в прозе {len(all_yellows)}")
    print("=" * 84)

    for p, n, text, reason in all_reds:
        print(f"🔴 {p.relative_to(root)}:{n}  ({reason})")
        print(f"     {text}")
    if all_yellows:
        shown = all_yellows if a.verbose else all_yellows[:5]
        for p, n, text, reason in shown:
            print(f"🟡 {p.relative_to(root)}:{n}  ({reason})")
        more = len(all_yellows) - len(shown)
        if more:
            print(f"   …ещё {more} в прозе — смотреть с --verbose")

    print("-" * 84)
    if all_reds:
        print(f"⛔ ЖИВЫХ ПУТЕЙ ОДНОЙ МАШИНЫ: {len(all_reds)} — у чужого человека это "
              "не заработает, и он решит, что сломан механизм.")
    else:
        print("✅ живых путей одной машины нет.")
    if all_yellows:
        print(f"🟡 В прозе и комментариях: {len(all_yellows)}. Это НЕ долг сам по себе — "
              "в уроке путь и есть предмет. Разбирать поимённо, а не гуртом.")
    return 1 if all_reds else 0


if __name__ == "__main__":
    sys.exit(main())
