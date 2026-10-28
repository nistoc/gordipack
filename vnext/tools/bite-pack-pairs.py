#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-pack-pairs — приёмка guard-pack-pairs.py (issue #39, предложение «б»).

    python vnext/tools/bite-pack-pairs.py                  # проверка, лежащая рядом с этим файлом
    python vnext/tools/bite-pack-pairs.py --guard ФАЙЛ     # другая копия проверки
    python vnext/tools/bite-pack-pairs.py --break ИМЯ      # нарочная поломка на копии проверки

Каждый случай строит во временном каталоге мини-пакет (scripts/, vnext/prototype/, при нужде vnext/tools/)
и гоняет проверку подпроцессом с --root. Настоящий пакет не читается и не правится. Временный каталог
убирается, если все проверки на нём прошли, и остаётся при провале — путь печатается.

СЛУЧАИ
  ① пара одного размера с разными байтами — код 1, пара названа (ловит сравнение по размеру и по имени);
  ② встречный: пара совпадает байт в байт — код 0, «совпадают байт в байт», виновника нет;
  ③ файл только в одном из каталогов — это не пара: код 0, никто не назван;
  ④ вглубь: migrations/m.py разные — код 1, назван путь migrations/m.py (ловит сверку одного верхнего уровня);
  ⑤ __pycache__ не в счёт: разные .pyc под __pycache__ — код 0;
  ⑥ перечень: разошедшаяся пара с причиной — код 0, причина напечатана;
  ⑦ лишняя строка перечня — код 1: (а) копии совпали; (б) одной копии нет;
  ⑧ строка перечня без причины — код 2 «НЕ ПРОВЕРЕНЫ», а не «совпадают»;
  ⑨ нет каталога vnext/prototype/ — код 2 «НЕ ПРОВЕРЕНЫ»;
  ⑩ --commit судит версию, а не диск: в commit пара разная, на диске сведена — с --commit код 1, без него код 0;
  ⑪ перечень на диске не прощает commit: в commit перечня нет — код 1 и строка «судится без исключений»;
  ⑫ встречный к ⑪: перечень, лежащий в самом commit, прощает — код 0, причина из commit напечатана;
  ⑬ __pycache__ не в счёт и с --commit: разные .pyc, попавшие в commit, — код 0;
  ⑭ путь дважды в перечне — код 2 «НЕ ПРОВЕРЕНЫ», названа первая строка (вторая строка молча
     переписала бы причину первой);
  ⑮ концы строк (дополнение PROTO, 2026-10-28): (а) в рабочем дереве копии различаются ТОЛЬКО CRLF и LF —
     код 0, сказано «концы строк рабочего дерева не в счёт» (на Windows так выкладывает checkout);
     (б) встречный: в самом commit один blob с CRLF, другой с LF — с --commit код 1, пара названа.
  Случаи ⑩–⑬ и ⑮б строят подставной git-репозиторий во временном каталоге (перехватчики git в нём
  выключены пустым core.hooksPath стенда, core.autocrlf=false). Нет git — «НЕ ПРОВЕРЕН», а не «прошёл».

НАРОЧНЫЕ ПОЛОМКИ (--break ИМЯ). Копия проверки во временном каталоге получает одну правку «было → стало»,
и все случаи гоняются по ней. Какие случаи обязаны провалиться, записано ниже ДО прогона (BREAKS);
итог печатает «ожидание ПОДТВЕРДИЛОСЬ», только если провалились РОВНО они. Образец правки не найден
в проверке — «НЕ ЗАПУСТИЛАСЬ», код 2: поломка, которую некуда вложить, ничего не доказывает.
  top-level-only ............. сверка только верхнего уровня (glob вместо rglob)           → ④
  pycache-disk ............... __pycache__ в счёт в рабочем дереве                         → ⑤
  stale-forgiven ............. лишние строки перечня не ищутся                             → ⑦а ⑦б
  reason-optional ............ причина в перечне необязательна                             → ⑧
  differ-from-disk-in-commit . с --commit перечень берётся с диска                         → ⑪ ⑫
  files-from-disk-in-commit .. с --commit файлы берутся с диска                            → ⑩ ⑪ ⑮б
  cannot-check-zero .......... «не проверено» выходит кодом 0                              → ⑧ ⑨ ⑭
  by-size .................... сравнение по размеру, а не по байтам                        → ① ④ ⑥ ⑩ ⑪ ⑫ ⑮б
  pycache-commit ............. __pycache__ в счёт с --commit                               → ⑬
  dup-line-ok ................ повтор пути в перечне не ловится                            → ⑭
  crlf-counts ................ концы строк рабочего дерева в счёт                          → ⑮а

КОД ВЫХОДА. 0 — все случаи прошли · 1 — есть провал (с --break — всегда: поломка на то и вложена;
подтвердилось ли ожидание, сказано строкой) · 2 — провалов нет, но есть непроверенный случай, или
поломку вложить некуда.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
S, P, T = "scripts/", "vnext/prototype/", "vnext/tools/pack-pairs-differ.tsv"
results = []   # (имя, "ok" | "fail" | "skip", подробность, временный каталог)

BS = "\\"
BREAKS = {
    "top-level-only": ([('for p in sorted(d.rglob("*"))', 'for p in sorted(d.glob("*"))')], {"④"}),
    "pycache-disk": ([('if p.is_file() and "__pycache__" not in p.parts}', 'if p.is_file()}')], {"⑤"}),
    "stale-forgiven": ([("    stale = [n for n in sorted(differ) if n not in diverged]\n", "    stale = []\n")],
                       {"⑦а", "⑦б"}),
    "reason-optional": ([("        if not path.strip() or not reason.strip():\n",
                          "        if not path.strip():\n")], {"⑧"}),
    "differ-from-disk-in-commit": ([("    if rev:\n        names = git(", "    if False:\n        names = git(")],
                                   {"⑪", "⑫"}),
    "files-from-disk-in-commit": ([("sides, content = from_commit(root, args.commit) if args.commit else from_disk(root)",
                                    "sides, content = from_disk(root)")], {"⑩", "⑪", "⑮б"}),
    "cannot-check-zero": ([("        print(\"   «Не проверено» не значит «совпадают».\")\n        return 2\n",
                            "        print(\"   «Не проверено» не значит «совпадают».\")\n        return 0\n")],
                          {"⑧", "⑨", "⑭"}),
    "by-size": ([("    diverged = [n for n in common if left[n] != right[n]]\n",
                  "    diverged = [n for n in common if len(left[n]) != len(right[n])]\n")],
                {"①", "④", "⑥", "⑩", "⑪", "⑫", "⑮б"}),
    "pycache-commit": ([('if kind == "blob" and "__pycache__" not in rel.split("/"):', 'if kind == "blob":')],
                       {"⑬"}),
    "dup-line-ok": ([("        if path.strip() in entries:\n", "        if False:\n")], {"⑭"}),
    "crlf-counts": ([('p.read_bytes().replace(b"' + BS + 'r' + BS + 'n", b"' + BS + 'n")', "p.read_bytes()")],
                    {"⑮а"}),
}


def stand(tag: str, files: dict) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=f"bite-pack-pairs-{tag}-"))
    write(tmp, files)
    return tmp


def write(root: Path, files: dict) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body.encode("utf-8") if isinstance(body, str) else body)


def run(guard: Path, root: Path, *args: str):
    r = subprocess.run([sys.executable, str(guard), "--root", str(root), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"),
                       stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def check(name: str, tmp: Path, ok: bool, rc: int, out: str) -> None:
    results.append((name, "ok" if ok else "fail", f"код {rc} · {out.strip()[-300:]}", tmp))


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
                    "-c", f"core.hooksPath={root / '.no-hooks'}", "-c", "user.name=bite",
                    "-c", "user.email=bite@example.invalid", *args],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def git_stand(tag: str, files: dict, message: str) -> Path:
    """Мини-пакет, сразу положенный в commit подставного репозитория."""
    tmp = stand(tag, files)
    (tmp / ".no-hooks").mkdir()
    git(tmp, "init", "-q")
    git(tmp, "add", "-f", "scripts", "vnext")
    git(tmp, "commit", "-q", "-m", message)
    return tmp


def _writable_and_retry(func, path, _exc):
    """Windows не удаляет файл «только для чтения», а git так кладёт .git/objects: снять метку и повторить."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove(path: Path) -> bool:
    """Убрать стенд вместе с подставным git; False — каталог остался (вызывающий печатает путь).

    Прежде было rmtree(ignore_errors=True): на Windows .git/objects оставались, а отказ глушился —
    три стенда на каждый прогон молча (замечание COORD к PR 54, записка #6071)."""
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_writable_and_retry)
        else:
            shutil.rmtree(path, onerror=_writable_and_retry)
    except OSError:
        pass
    return not Path(path).exists()


def broken_copy(guard: Path, name: str):
    """Копия проверки с нарочной поломкой во временном каталоге; None — образца правки нет."""
    text = guard.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for old, new in BREAKS[name][0]:
        if text.count(old) != 1:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{name}» вложить некуда "
                  f"(образец найден {text.count(old)} раз): {old.strip()[:70]}")
            return None
        text = text.replace(old, new)
    d = Path(tempfile.mkdtemp(prefix=f"bite-pack-pairs-break-{name}-"))
    copy = d / guard.name
    # байтами: запись текстом на Windows сменила бы концы строк копии
    copy.write_bytes(text.encode("utf-8"))
    return copy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", default=str(HERE / "guard-pack-pairs.py"), help="копия проверки, которую судим")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии проверки")
    a = ap.parse_args()
    guard = Path(a.guard).resolve()
    if not guard.is_file():
        print(f"⛔ ПРИЁМКА НЕ ПРОВЕРЕНА: нет проверки {guard}")
        return 2
    if a.break_name:
        guard = broken_copy(guard, a.break_name)
        if guard is None:
            return 2
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА в {guard}. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    tmp = stand("1", {S + "a.py": "x = 1\n", P + "a.py": "x = 2\n", S + "same.py": "ok\n", P + "same.py": "ok\n"})
    rc, out = run(guard, tmp)
    check("① пара одного размера с разными байтами — код 1, названа поимённо", tmp,
          rc == 1 and "⛔ a.py" in out and "⛔ same.py" not in out, rc, out)

    tmp = stand("2", {S + "a.py": "x = 1\n", P + "a.py": "x = 1\n"})
    rc, out = run(guard, tmp)
    check("② встречный: пара совпадает — код 0, «совпадают байт в байт»", tmp,
          rc == 0 and "совпадают байт в байт" in out and "⛔" not in out, rc, out)

    tmp = stand("3", {S + "only.py": "1\n", P + "other.py": "2\n"})
    rc, out = run(guard, tmp)
    check("③ файл только в одном каталоге — не пара, код 0", tmp,
          rc == 0 and "⛔" not in out and "only.py" not in out and "other.py" not in out, rc, out)

    tmp = stand("4", {S + "migrations/m.py": "1\n", P + "migrations/m.py": "2\n"})
    rc, out = run(guard, tmp)
    check("④ вглубь: migrations/m.py разные — код 1, назван путь", tmp,
          rc == 1 and "⛔ migrations/m.py" in out, rc, out)

    tmp = stand("5", {S + "__pycache__/x.cpython-3.pyc": b"\x00\x01", P + "__pycache__/x.cpython-3.pyc": b"\x00\x02",
                      S + "x.py": "1\n", P + "x.py": "1\n"})
    rc, out = run(guard, tmp)
    check("⑤ __pycache__ не в счёт — код 0", tmp, rc == 0 and "⛔" not in out, rc, out)

    tmp = stand("6", {S + "a.py": "1\n", P + "a.py": "2\n", T: "# пример\na.py\tнарочно разные: пример причины\n"})
    rc, out = run(guard, tmp)
    check("⑥ перечень: пара с причиной — код 0, причина напечатана", tmp,
          rc == 0 and "нарочно разные" in out and "пример причины" in out and "⛔" not in out, rc, out)

    tmp = stand("7a", {S + "a.py": "1\n", P + "a.py": "1\n", T: "a.py\tпричина\n"})
    rc, out = run(guard, tmp)
    check("⑦а лишняя строка перечня: копии совпали — код 1", tmp,
          rc == 1 and "лишняя строка" in out and "копии совпадают" in out, rc, out)
    tmp = stand("7b", {S + "a.py": "1\n", P + "b.py": "1\n", T: "a.py\tпричина\n"})
    rc, out = run(guard, tmp)
    check("⑦б лишняя строка перечня: одной копии нет — код 1", tmp,
          rc == 1 and "лишняя строка" in out and "пары нет" in out, rc, out)

    tmp = stand("8", {S + "a.py": "1\n", P + "a.py": "2\n", T: "a.py\n"})
    rc, out = run(guard, tmp)
    check("⑧ строка перечня без причины — код 2 «НЕ ПРОВЕРЕНЫ»", tmp,
          rc == 2 and "НЕ ПРОВЕРЕНЫ" in out and "совпадают байт" not in out, rc, out)

    tmp = stand("9", {S + "a.py": "1\n"})
    rc, out = run(guard, tmp)
    check("⑨ нет каталога vnext/prototype/ — код 2 «НЕ ПРОВЕРЕНЫ»", tmp,
          rc == 2 and "НЕ ПРОВЕРЕНЫ" in out, rc, out)

    tmp = stand("14", {S + "a.py": "1\n", P + "a.py": "2\n", T: "a.py\tпервая причина\na.py\tвторая причина\n"})
    rc, out = run(guard, tmp)
    check("⑭ путь дважды в перечне — код 2 «НЕ ПРОВЕРЕНЫ», названа первая строка", tmp,
          rc == 2 and "НЕ ПРОВЕРЕНЫ" in out and "уже есть в строке 1" in out, rc, out)

    tmp = stand("15a", {S + "a.py": "x = 1\r\ny = 2\r\n", P + "a.py": "x = 1\ny = 2\n"})
    rc, out = run(guard, tmp)
    check("⑮а рабочее дерево: копии различаются только CRLF и LF — код 0, «концы строк … не в счёт»", tmp,
          rc == 0 and "концы строк рабочего дерева не в счёт" in out and "⛔" not in out, rc, out)

    git_cases = ("⑩ --commit судит версию, а не диск",
                 "⑪ перечень на диске не прощает commit",
                 "⑫ встречный: перечень из самого commit прощает",
                 "⑬ __pycache__ не в счёт и с --commit",
                 "⑮б встречный: в commit один blob с CRLF, другой с LF")
    if shutil.which("git") is None:
        for name in git_cases:
            results.append((name, "skip", "нет git", None))
    else:
        tmp = git_stand("10", {S + "a.py": "1\n", P + "a.py": "2\n"}, "pair differs")
        write(tmp, {P + "a.py": "1\n"})
        rc_c, out_c = run(guard, tmp, "--commit", "HEAD")
        rc_d, out_d = run(guard, tmp)
        check(git_cases[0] + ": с --commit код 1, по диску код 0", tmp,
              rc_c == 1 and "⛔ a.py" in out_c and rc_d == 0, rc_c, out_c + "\n--- диск:\n" + out_d)
        write(tmp, {T: "a.py\tтолько на диске\n"})
        rc, out = run(guard, tmp, "--commit", "HEAD")
        check(git_cases[1] + ": код 1, «судится без исключений»", tmp,
              rc == 1 and "⛔ a.py" in out and "без исключений" in out and "только на диске" not in out, rc, out)
        write(tmp, {P + "a.py": "2\n", T: "a.py\tпричина из commit\n"})
        git(tmp, "add", "vnext")
        git(tmp, "commit", "-q", "-m", "list the pair")
        write(tmp, {T: "a.py\tпричина с диска\n"})
        rc, out = run(guard, tmp, "--commit", "HEAD")
        check(git_cases[2] + ": код 0, причина из commit", tmp,
              rc == 0 and "причина из commit" in out and "причина с диска" not in out, rc, out)

        tmp = git_stand("13", {S + "__pycache__/x.cpython-3.pyc": b"\x00\x01",
                               P + "__pycache__/x.cpython-3.pyc": b"\x00\x02",
                               S + "x.py": "1\n", P + "x.py": "1\n"}, "pyc in commit")
        rc, out = run(guard, tmp, "--commit", "HEAD")
        check(git_cases[3] + ": код 0", tmp, rc == 0 and "⛔" not in out and "НЕ ПРОВЕРЕНЫ" not in out, rc, out)

        tmp = git_stand("15b", {S + "a.py": "x = 1\r\ny = 2\r\n", P + "a.py": "x = 1\ny = 2\n"}, "crlf blob")
        rc, out = run(guard, tmp, "--commit", "HEAD")
        check(git_cases[4] + ": с --commit код 1, пара названа", tmp,
              rc == 1 and "⛔ a.py" in out, rc, out)

    print("🔬 ПРИЁМКА: guard-pack-pairs — пары одного пути scripts/ ↔ vnext/prototype/")
    print(f"   проверка: {guard}")
    for name, status, detail, _tmp in results:
        mark = {"ok": "✅", "fail": "🔴", "skip": "⏸️ НЕ ПРОВЕРЕН:"}[status]
        print(f"   {mark} {name}" + (f"   ← {detail}" if status != "ok" else ""))
    bad = sum(1 for _n, s, _d, _t in results if s == "fail")
    skipped = sum(1 for _n, s, _d, _t in results if s == "skip")
    exact = None
    if a.break_name:
        red = {n.split()[0] for n, s, _d, _t in results if s == "fail"}
        expected = BREAKS[a.break_name][1]
        exact = red == expected and not skipped
        print(f"   {'🧪' if exact else '⚠️'} поломка «{a.break_name}»: провалились "
              f"{' '.join(sorted(red)) or 'никто'} · ждали {' '.join(sorted(expected))} — "
              f"{'ожидание ПОДТВЕРДИЛОСЬ' if exact else 'ожидание НЕ ПОДТВЕРДИЛОСЬ'}"
              + (f" (не проверено {skipped})" if skipped else ""))
    # стенды прошедших случаев убираются; провалы — тоже, если поломка поймана ровно как записано
    kept = set() if exact else {t for _n, s, _d, t in results if s != "ok" and t is not None}
    left = [t for t in sorted({t for *_x, t in results if t is not None} - kept) if not remove(t)]
    if a.break_name:
        if exact:
            left += [] if remove(guard.parent) else [guard.parent]
        else:
            print(f"   📁 копия с поломкой оставлена для разбора: {guard.parent}")
    for t in sorted(kept):
        print(f"   📁 стенд оставлен для разбора: {t}")
    for t in left:
        print(f"   📁 стенд не убран (удалить не удалось): {t}")
    print(f"   ИТОГ: {len(results) - bad - skipped}/{len(results)}"
          + (f" · не проверено {skipped}" if skipped else ""))
    if a.break_name:
        return 1
    return 1 if bad else (2 if skipped else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
