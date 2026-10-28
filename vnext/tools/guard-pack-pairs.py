#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard-pack-pairs — проверка пакета: файл с одним путём в scripts/ и в vnext/prototype/ — одна и та же копия.

    python vnext/tools/guard-pack-pairs.py                 # рабочее дерево пакета
    python vnext/tools/guard-pack-pairs.py --commit X      # версия X из git
    python vnext/tools/guard-pack-pairs.py --root DIR      # другое дерево пакета (распакованная версия, стенд приёмки)

ПРЕДМЕТ (issue #39, предложение «б»). Пакет ставит в контур два каталога: scripts/ и vnext/prototype/.
Файл с одним путём в обоих — две копии одного инструмента, и какая из них сработает, зависит только от
того, откуда её зовут. Такие пары сличает сверка контура (scripts/guard-scripts-drift.py, «общие
помощники»), но у ПОТРЕБИТЕЛЯ, после установки, и только когда у контура объявлено зеркало. В самом
пакете их не сличало ничто: на 253fc3e пара bite-phoenix-empty.py расходилась (34918 и 10968 байт),
и об этом молчали и пакет, и контуры без зеркала.

ЧТО СВЕРЯЕТСЯ. Все файлы под scripts/ и под vnext/prototype/ — вглубь, ключ — путь относительно
каталога (migrations/x.py сличается с migrations/x.py), __pycache__ не в счёт. Сравниваются БАЙТЫ:
в рабочем дереве — содержимое файлов на диске (правка, ещё не попавшая в commit, тоже видна), с
--commit — blob из git (один blob ⇔ одни байты). Размер и имя не доказывают ничего: копии одного
размера бывают разными.
КОНЦЫ СТРОК РАБОЧЕГО ДЕРЕВА НЕ В СЧЁТ (дополнение PROTO, 2026-10-28). На Windows при
core.autocrlf=true git кладёт текст на диск с CRLF, а файл, только что записанный инструментом,
лежит с LF — у git это один blob, а байты на диске разные. Сличение рабочего дерева сводит CRLF
к LF у обеих копий; с --commit сличаются blob как есть, и копии, различные ТОЛЬКО концами строк
в самом commit, — расхождение.

НАРОЧНО РАЗНЫЕ — ПЕРЕЧНЕМ, А НЕ МОЛЧАНИЕМ. Если две копии с одним путём должны различаться, это пишется
строкой в vnext/tools/pack-pairs-differ.tsv: путь, табуляция, причина. Причина обязательна. Строка,
которой нечего прощать (копии совпали или одной из них нет), — тоже провал: такая строка молча
простила бы следующее расхождение той же пары. С --commit перечень берётся из того же commit, а не с
диска: судится версия целиком. Перечня нет — судится без исключений, и это сказано строкой.

КАКАЯ КОПИЯ ВЕРНА — НЕ РЕШАЕТ. Проверка называет пару и различие; свести копии одной версией,
переименовать одну из них или внести пару в перечень — решение автора инструмента.

КОД ВЫХОДА. 0 — расхождений вне перечня нет и в перечне нет лишних строк · 1 — есть расхождение вне
перечня или лишняя строка перечня · 2 — проверить не удалось (нет каталога, перечень не разобран, git
не ответил) — словами, чего именно. «Не проверено» не бывает «совпадают».

ГРАНИЦЫ. Переименованная копия (у одного инструмента два имени) не ловится — её не с чем сравнить.
Проверку никто не зовёт сам: вызывает её тот, кто правит пакет. Подключить её к перехватчику
.githooks/pre-commit — решение автора пакета.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK_ROOT_DEFAULT = HERE.parent.parent
LEFT, RIGHT = "scripts", "vnext/prototype"
DIFFER_PATH = "vnext/tools/pack-pairs-differ.tsv"


class CannotCheck(Exception):
    """Проверить не удалось: код 2 и слова, чего именно не хватило."""


def git(root: Path, *args: str) -> bytes:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise CannotCheck("git не найден") from None
    if r.returncode != 0:
        said = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise CannotCheck(f"git {' '.join(args[:2])}: {said[0] if said else 'код ' + str(r.returncode)}")
    return r.stdout


def from_disk(root: Path):
    """{каталог: {путь: байты}} рабочего дерева и чтение содержимого для разбора различий."""
    sides = {}
    for sub in (LEFT, RIGHT):
        d = root / sub
        if not d.is_dir():
            raise CannotCheck(f"нет каталога {d}")
        # CRLF → LF: так копии сличаются, как их хранит git, а не как их выложил checkout
        sides[sub] = {p.relative_to(d).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
                      for p in sorted(d.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    # размер и отпечаток в строке расхождения — байты файла как есть, их сверит ls и sha256sum
    return sides, (lambda sub, rel: (root / sub / rel).read_bytes())


def from_commit(root: Path, rev: str):
    """{каталог: {путь: blob}} версии rev; содержимое читается из git только для разошедшихся пар."""
    sides = {}
    for sub in (LEFT, RIGHT):
        entries = {}
        for rec in git(root, "ls-tree", "-r", "-z", rev, "--", sub + "/").decode("utf-8").split("\0"):
            if not rec:
                continue
            meta, path = rec.split("\t", 1)
            _mode, kind, oid = meta.split()
            rel = path[len(sub) + 1:]
            if kind == "blob" and "__pycache__" not in rel.split("/"):
                entries[rel] = oid
        if not entries:
            raise CannotCheck(f"в {rev} нет файлов под {sub}/")
        sides[sub] = entries
    return sides, (lambda sub, rel: git(root, "cat-file", "blob", sides[sub][rel]))


def parse_differ(text: str, where: str) -> dict:
    """{путь: (номер строки, причина)} перечня нарочно разных; строка без причины — CannotCheck."""
    entries = {}
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        path, _tab, reason = line.partition("\t")
        if not path.strip() or not reason.strip():
            raise CannotCheck(f"{where}:{no}: нужна строка «путь<табуляция>причина», причина обязательна")
        if path.strip() in entries:
            raise CannotCheck(f"{where}:{no}: {path.strip()} уже есть в строке {entries[path.strip()][0]}")
        entries[path.strip()] = (no, reason.strip())
    return entries


def read_differ(root: Path, rev: str | None, named: str | None):
    """Перечень и строка о том, откуда он взят."""
    if named:
        p = Path(named)
        if not p.is_file():
            raise CannotCheck(f"перечня {p} нет")
        return parse_differ(p.read_text(encoding="utf-8"), p.name), f"перечень нарочно разных: {p}"
    if rev:
        names = git(root, "ls-tree", "--name-only", rev, "--", DIFFER_PATH).decode("utf-8").split()
        if DIFFER_PATH not in names:
            return {}, f"перечня нарочно разных в {rev} нет — судится без исключений"
        text = git(root, "show", f"{rev}:{DIFFER_PATH}").decode("utf-8")
        return parse_differ(text, f"{rev}:{DIFFER_PATH}"), f"перечень нарочно разных: {rev}:{DIFFER_PATH}"
    p = root / DIFFER_PATH
    if not p.is_file():
        return {}, f"перечня нарочно разных нет ({p}) — судится без исключений"
    return parse_differ(p.read_text(encoding="utf-8"), DIFFER_PATH), f"перечень нарочно разных: {p}"


def changed_lines(a: bytes, b: bytes) -> int:
    """Строк, различающихся по содержимому (удалено + добавлено), без учёта концов строк."""
    la = a.replace(b"\r\n", b"\n").decode("utf-8", "replace").splitlines()
    lb = b.replace(b"\r\n", b"\n").decode("utf-8", "replace").splitlines()
    m = difflib.SequenceMatcher(a=la, b=lb, autojunk=False)
    return sum((i2 - i1) + (j2 - j1) for tag, i1, i2, j1, j2 in m.get_opcodes() if tag != "equal")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="файлы с одним путём в scripts/ и vnext/prototype/ — одна копия")
    ap.add_argument("--root", help="корень дерева пакета (по умолчанию — два уровня выше этого файла)")
    ap.add_argument("--commit", help="судить версию из git, а не рабочее дерево")
    ap.add_argument("--differ", help="перечень нарочно разных вместо vnext/tools/pack-pairs-differ.tsv")
    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else PACK_ROOT_DEFAULT
    try:
        sides, content = from_commit(root, args.commit) if args.commit else from_disk(root)
        differ, differ_said = read_differ(root, args.commit, args.differ)
    except CannotCheck as e:
        print(f"⛔ пары {LEFT}/ ↔ {RIGHT}/ НЕ ПРОВЕРЕНЫ: {e}")
        print("   «Не проверено» не значит «совпадают».")
        return 2

    left, right = sides[LEFT], sides[RIGHT]
    common = sorted(set(left) & set(right))
    diverged = [n for n in common if left[n] != right[n]]
    unlisted = [n for n in diverged if n not in differ]
    listed = [n for n in diverged if n in differ]
    stale = [n for n in sorted(differ) if n not in diverged]

    print(f"пары одного пути {LEFT}/ ↔ {RIGHT}/ ({'версия ' + args.commit if args.commit else 'рабочее дерево'} "
          f"{root}): общих {len(common)}, расходятся {len(diverged)}")
    print(f"   {differ_said}")
    for n in unlisted:
        a, b = content(LEFT, n), content(RIGHT, n)
        print(f"⛔ {n}: {LEFT}/ {len(a)}б {hashlib.sha256(a).hexdigest()[:12]} ≠ "
              f"{RIGHT}/ {len(b)}б {hashlib.sha256(b).hexdigest()[:12]} · строк по существу: {changed_lines(a, b)}")
    if unlisted:
        print("   👉 какая копия верна, решает автор: свести их одной версией, переименовать одну из них "
              f"или внести путь в {DIFFER_PATH} с причиной")
    for n in listed:
        print(f"✅ нарочно разные (перечень, строка {differ[n][0]}): {n} — {differ[n][1]}")
    for n in stale:
        why = "копии совпадают" if n in common else "пары нет — одной из копий нет"
        print(f"⛔ лишняя строка перечня {differ[n][0]}: {n} — {why}; строка молча простила бы следующее расхождение")
    if not (unlisted or stale):
        print(f"✅ {len(common) - len(listed)} из {len(common)} общих совпадают байт в байт"
              + ("" if args.commit else " (концы строк рабочего дерева не в счёт)")
              + (f", {len(listed)} — нарочно разные по перечню" if listed else ""))
        print("   ⚖️ ГРАНИЦА: сверены копии с ОДНИМ путём; переименованная копия не ловится — её не с чем сравнить.")
    return 1 if (unlisted or stale) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
