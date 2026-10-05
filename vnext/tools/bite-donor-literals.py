#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-donor-literals — приёмка проверки guard-donor-literals.py (карточка #677, этап Э3, работа Р7).

    python vnext/tools/bite-donor-literals.py [--goal-dir <каталог goal-gordi-core>]
    python vnext/tools/bite-donor-literals.py --cases                 # только случаи, без нарочных поломок
    python vnext/tools/bite-donor-literals.py --break <имя>            # одна нарочная поломка (имена — в --help)
    python vnext/tools/bite-donor-literals.py --break all              # все нарочные поломки, без чистого прогона

ПРЕДМЕТ. guard-donor-literals.py (и движок donor_scan.py) не пускают литералы донора в код ядра
пакета. Приёмка судит их на ПОДСТАВНОМ мини-пакете: временный каталог, свой перечень файлов ядра,
свой файл имён с ВЫДУМАННЫМИ ролями ZZQ и ZZW. Настоящий пакет и настоящий клон читаются только на
чтение. Ни одного имени донора в этом файле нет: «чужая» роль для встречного случая берётся из
настоящего donor-names.json пакета при запуске.

СЛУЧАИ (различающие: проверка обязана ответить ИНАЧЕ на парных входах, а не одинаково):
  ① литерал роли в коде (ROLE = "ZZQ") — находка;
  ② литерал в печати (print("зови ZZQ")) — находка;
  ③ встречный: тот же литерал в комментарии и в строке документации — НЕ находка;
  ④ имена берутся из файла данных: при файле с ZZQ чужая роль в коде не находка, ZZQ — находка;
     при файле с чужой ролью наоборот;
  ⑤ исключение по тексту строки: покрытая строка не находка; правка текста строки — находка и
     «исключение без попадания»; сдвиг номера строки (текст тот же) — по-прежнему покрыта;
  ⑥ роль целой строкой в любом регистре: ["zzq"] — находка, "zzqrator" — нет, точное написание
     ZZQ считается один раз, а не дважды;
  ⑦ файл scripts/*.py вне перечня — находка «файл ядра не в перечне»; scripts/bite-x.py,
     scripts/migrations/x.py и файл из раздела [вне ядра] — нет;
  ⑧ коды выхода: 0 (чисто) · 1 (находка) · 2 (нет файла перечня, нет файла имён, нет git для --commit,
     нет commit) — словами, а не «прошла»; --strict делает исключение без попадания провалом;
  ⑨ настоящий пакет, только чтение: --reconcile-with даёт (а) и (б) сходящимися; на искажённой копии
     каталога замеров — расходящимися; нет каталога или commit — «НЕ ПРОВЕРЕНО» с кодом 2;
  ⑩ sync-to-template.py (его копия во временном мини-пакете, где корни указывают во временные
     каталоги): с --apply при находке — код 1 и строка «commit не делать»; без находки — код 0;
     в режиме замера код выхода от находок не меняется.

НАРОЧНЫЕ ПОЛОМКИ применяются К ТЕКСТУ проверки В ПАМЯТИ (compile + exec); на диск ничего не пишется.
Ожидание каждой записано ЗАРАНЕЕ (таблица BREAKS ниже): поломка роняет свой случай и ничего больше.
Под каждой поломкой прогоняются и остальные случаи ①–⑧ (⑨ и ⑩ — только когда они свои): если
провалился кто-то, кого не ждали, приёмка не принята.
  code-unchecked          «код не проверяется»                   → ①
  print-unchecked         «печать не проверяется»                → ②
  comment-counted         «комментарий считается»                → ③
  names-in-code           «имена вписаны в код»                  → ④
  exception-by-line       «исключение по номеру строки»          → ⑤
  no-role-literal-group   «нет группы роли целой строкой»        → ⑥
  file-list-unchecked     «перечень файлов не сверяется»         → ⑦
  exit2-as-0              «код 2 подменён на 0»                  → ⑧
  reconcile-skips-b       «сверка (б) пропускает расхождение»    → ⑨
  sync-no-guard           «sync-to-template не зовёт проверку»   → ⑩
Исход каждого случая — один из трёх: прошёл · провалился · НЕ ПРОВЕРЕН (⑨ без каталога замеров).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable, NamedTuple

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent.parent
GUARD_PATH = HERE / "guard-donor-literals.py"
SCAN_PATH = HERE / "donor_scan.py"
SYNC_PATH = HERE / "sync-to-template.py"
NAMES_PATH = HERE / "donor-names.json"

FICTIONAL = ("ZZQ", "ZZW")      # выдуманные роли подставного мини-пакета
CASE_MARKS = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨", 10: "⑩"}
CASE_TITLES = {
    1: "литерал роли в коде — находка",
    2: "литерал в печати — находка",
    3: "встречный: тот же литерал в комментарии и строке документации — не находка",
    4: "имена берутся из файла данных, а не из кода проверки",
    5: "исключение держится за текст строки, а не за её номер",
    6: "роль целой строкой в любом регистре: «zzq» — находка, «zzqrator» — нет",
    7: "файл scripts/*.py вне перечня — находка; bite-*.py, migrations/ и «вне ядра» — нет",
    8: "коды выхода 0 / 1 / 2 — словами; «не проверено» не бывает «прошла»",
    9: "настоящий пакет: сверка с замером Э2 и счётом Э3 сходится; искажённую копию ловит; без каталога — НЕ ПРОВЕРЕНО",
    10: "sync-to-template.py: находка при --apply — код 1 и «commit не делать»",
}

CASES = 0
PASSED = 0
UNCHECKED = 0


def case(title: str, verdict, detail: str) -> bool:
    """verdict: True прошёл · False провалился · None НЕ ПРОВЕРЕН (не считается ни прошедшим, ни проваленным)."""
    global CASES, PASSED, UNCHECKED
    if verdict is None:
        UNCHECKED += 1
        print(f"⚪ НЕ ПРОВЕРЕН: {title}")
    else:
        CASES += 1
        PASSED += bool(verdict)
        print(f"{'✅' if verdict else '🔴'} {title}")
    for line in detail.split("\n"):
        print(f"   {line}")
    return verdict is not False


# ── загрузка модулей из текстов (нарочная поломка правит текст в памяти) ──────────

def load_source(path: Path, name: str, patch: Callable | None = None):
    src = path.read_text(encoding="utf-8")
    if patch is not None:
        src, n = patch(src)
        if n != 1:
            raise AssertionError(f"поломка нашла свою цель {n} раз(а) в {path.name}, ждали ровно один — "
                                 f"проверка могла измениться, поломку надо пересмотреть")
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        exec(compile(src, str(path), "exec"), mod.__dict__)
    finally:
        sys.modules.pop(name, None)
    return mod


def load_pair(patch_scan: Callable | None = None, patch_guard: Callable | None = None):
    """-> (donor_scan, guard). Проверка делает «import donor_scan»: на время загрузки подставляем нужный движок."""
    had = "donor_scan" in sys.modules
    old = sys.modules.get("donor_scan")
    scan = load_source(SCAN_PATH, "donor_scan", patch_scan)
    sys.modules["donor_scan"] = scan
    try:
        guard = load_source(GUARD_PATH, "guard_donor_literals_bite", patch_guard)
    finally:
        if had:
            sys.modules["donor_scan"] = old
        else:
            sys.modules.pop("donor_scan", None)
    return scan, guard


def replace_once(src: str, old: str, new: str):
    return src.replace(old, new), src.count(old)


# ── подставной мини-пакет ────────────────────────────────────────────────────────

class Ctx(NamedTuple):
    scan: object
    guard: object
    tmp: Path
    real_role: str            # чужая роль из настоящего файла имён — встречный литерал для ④
    goal: Path | None         # каталог замеров для ⑨
    sync_patch: Callable | None = None


def names_json(roles) -> str:
    return json.dumps({
        "format_version": 1,
        "lists": {"roles": list(roles)},
        "groups": {"role": [{"type": "words", "list": "roles"}],
                   "role_any_case": [{"type": "whole_literal", "list": "roles"}]},
    }, ensure_ascii=False, indent=1)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def mini(tmp: Path, name: str, files: dict, core, outside=None, roles=FICTIONAL, allowed=()) -> Path:
    """Подставной пакет: файлы, перечень ядра, имена, исключения. -> корень. Каталог данных — root/vnext/tools."""
    root = tmp / name
    data = root / "vnext" / "tools"
    data.mkdir(parents=True)
    for rel, text in files.items():
        write(root / rel, text)
    head = "# подставной перечень\n[ядро]\n" + "".join(f"{p}\n" for p in core)
    head += "[вне ядра]\n" + "".join(f"{p}\t{why}\n" for p, why in (outside or {}).items())
    write(data / "core-files.txt", head)
    write(data / "donor-names.json", names_json(roles))
    rows = "file\tname\tkind\tclass\ttext\treason\n" + "".join("\t".join(r) + "\n" for r in allowed)
    write(data / "donor-literals-allowed.tsv", rows)
    return root


def run_check(ctx: Ctx, root: Path, strict: bool = False):
    res = ctx.guard.check(root, root / "vnext" / "tools")
    lines = []
    ctx.guard.report(res, strict, out=lines.append)
    return res, ctx.guard.exit_code(res, strict), "\n".join(lines)


def run_main(ctx: Ctx, root: Path, *extra) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = ctx.guard.main(["--root", str(root), "--data-dir", str(root / "vnext" / "tools"), *extra])
    return code, buf.getvalue()


def sub(tmp: Path, name: str) -> Path:
    d = tmp / name
    d.mkdir()
    return d


# ── случаи ①–⑩: каждый возвращает (исход, подробности) ───────────────────────────

def case1(ctx: Ctx):
    root = mini(ctx.tmp, "c1", {"scripts/a.py": 'ROLE = "ZZQ"\n'}, ["scripts/a.py"])
    res, code, text = run_check(ctx, root)
    f = res.findings
    ok = (len(f) == 1 and f[0].name == "ZZQ" and f[0].kind == "code" and f[0].line == 1 and code == 1)
    return ok, f"находок {len(f)} (ждём 1: ZZQ · code · строка 1); код выхода {code} (ждём 1)"


def case2(ctx: Ctx):
    root = mini(ctx.tmp, "c2", {"scripts/a.py": 'print("зови ZZQ")\n'}, ["scripts/a.py"])
    res, code, text = run_check(ctx, root)
    f = res.findings
    ok = (len(f) == 1 and f[0].name == "ZZQ" and f[0].kind == "shown" and f[0].line == 1 and code == 1)
    return ok, f"находок {len(f)} (ждём 1: ZZQ · shown · строка 1); код выхода {code} (ждём 1)"


def case3(ctx: Ctx):
    src = ('"""Роль ZZQ в строке документации."""\n'
           "# роль ZZQ в комментарии\n"
           "X = 1  # ZZQ в хвосте строки\n")
    root = mini(ctx.tmp, "c3", {"scripts/a.py": src}, ["scripts/a.py"])
    res, code, text = run_check(ctx, root)
    kinds = sorted(h.kind for h in res.hits)
    ok = (not res.findings and kinds == ["comment", "comment", "docstring"] and code == 0)
    return ok, (f"находок {len(res.findings)} (ждём 0); движок литерал ВИДЕЛ: виды попаданий {kinds} "
                f"(ждём два comment и один docstring — проверка, не видевшая литерал, молчала бы по другой причине); код {code}")


def case4(ctx: Ctx):
    real = ctx.real_role
    both = f'X = "{real}"\nprint("{real}")\n'
    zzq = 'Y = "ZZQ"\nprint("ZZQ")\n'
    # файл имён с ZZQ: чужая роль молчит, ZZQ находится
    r1 = mini(ctx.tmp, "c4a", {"scripts/a.py": both, "scripts/b.py": zzq}, ["scripts/a.py", "scripts/b.py"])
    res1, _, _ = run_check(ctx, r1)
    foreign_1 = [h for h in res1.findings if h.file == "scripts/a.py"]
    zzq_1 = [h for h in res1.findings if h.file == "scripts/b.py" and h.name == "ZZQ"]
    # тот же код, файл имён другой — ответ обязан поменяться
    r2 = mini(ctx.tmp, "c4b", {"scripts/a.py": both, "scripts/b.py": zzq}, ["scripts/a.py", "scripts/b.py"],
              roles=(real,))
    res2, _, _ = run_check(ctx, r2)
    foreign_2 = [h for h in res2.findings if h.file == "scripts/a.py" and h.name == real]
    zzq_2 = [h for h in res2.findings if h.file == "scripts/b.py"]
    ok = (not foreign_1 and zzq_1 and foreign_2 and not zzq_2)
    return ok, (f"файл имён {{ZZQ, ZZW}}: чужая роль — находок {len(foreign_1)} (ждём 0), ZZQ — {len(zzq_1)} (ждём ≥1); "
                f"тот же код, файл имён {{чужая роль}}: она — {len(foreign_2)} (ждём ≥1), ZZQ — {len(zzq_2)} (ждём 0)")


def case5(ctx: Ctx):
    code_line = 'ROLE = "ZZQ"'
    print_line = 'print("зови ZZQ")'
    allowed = [("scripts/a.py", "ZZQ", "code", "fixture", code_line, "подставная строка стенда"),
               ("scripts/a.py", "ZZQ", "shown", "printed", print_line, "подставная печать стенда")]
    frozen = {("scripts/a.py", "ZZQ", "code", code_line): 1, ("scripts/a.py", "ZZQ", "shown", print_line): 2}
    if hasattr(ctx.guard, "FROZEN"):        # нарочная поломка «по номеру строки»: номера запоминаются при заведении
        ctx.guard.FROZEN.clear()
        ctx.guard.FROZEN.update(frozen)
    # (i) покрыто
    r1 = mini(ctx.tmp, "c5a", {"scripts/a.py": code_line + "\n" + print_line + "\n"}, ["scripts/a.py"], allowed=allowed)
    res1, code1, _ = run_check(ctx, r1)
    # (ii) правка текста обеих строк — находки и «исключение без попадания»
    r2 = mini(ctx.tmp, "c5b", {"scripts/a.py": code_line + "  # правка\n" + 'print("зови ZZQ!")\n'}, ["scripts/a.py"],
              allowed=allowed)
    res2, code2, text2 = run_check(ctx, r2)
    # (iii) сдвиг номеров (текст тот же) — по-прежнему покрыто
    r3 = mini(ctx.tmp, "c5c", {"scripts/a.py": "\n\n" + code_line + "\n" + print_line + "\n"}, ["scripts/a.py"],
              allowed=allowed)
    res3, code3, _ = run_check(ctx, r3)
    if hasattr(ctx.guard, "FROZEN"):
        ctx.guard.FROZEN.clear()
    # под поломками «код / печать не проверяется» одно из двух исключений законно остаётся без попадания,
    # поэтому здесь требуется «≥ 1 строки под исключением», а не «обе»
    ok1 = not res1.findings and res1.covered >= 1 and code1 == 0
    ok2 = (len(res2.findings) >= 1 and len(res2.unmatched) == 2 and text2.count("исключение без попадания") == 2 and code2 == 1)
    ok3 = not res3.findings and res3.covered >= 1 and code3 == 0
    return (ok1 and ok2 and ok3), (
        f"(i) покрытая строка: находок {len(res1.findings)} (ждём 0), строк под исключением {res1.covered} (ждём 2); "
        f"(ii) текст правлен: находок {len(res2.findings)} (ждём ≥1), исключений без попадания {len(res2.unmatched)} (ждём 2); "
        f"(iii) строки сдвинуты, текст тот же: находок {len(res3.findings)} (ждём 0), строк под исключением {res3.covered} (ждём 2)")


def case6(ctx: Ctx):
    src = 'ROLES = ["zzq"]\nprint("Zzq")\nX = "zzqrator"\nY = "ZZQ"\n'
    root = mini(ctx.tmp, "c6", {"scripts/a.py": src}, ["scripts/a.py"])
    res, code, _ = run_check(ctx, root)
    lower = [h for h in res.findings if h.group == "role_any_case" and h.line in (1, 2)]
    substring = [h for h in res.hits if h.line == 3]
    exact = [h for h in res.hits if h.line == 4]
    ok = (len(lower) >= 1 and not substring and len(exact) == 1 and exact[0].group == "role")
    return ok, (f"«zzq» / «Zzq» целой строкой — находок группы роли в ином регистре {len(lower)} (ждём ≥1); "
                f"«zzqrator» — попаданий {len(substring)} (ждём 0); точное «ZZQ» — записей {len(exact)} (ждём ровно 1, группа role)")


def case7(ctx: Ctx):
    files = {"scripts/a.py": "X = 1\n", "scripts/b.py": "X = 1\n", "scripts/c.py": "X = 1\n",
             "scripts/bite-x.py": "X = 1\n", "scripts/migrations/x.py": "X = 1\n", "vnext/prototype/z.py": "X = 1\n"}
    root = mini(ctx.tmp, "c7", files, ["scripts/a.py"], outside={"scripts/c.py": "стенд приёмки, не ядро"})
    res, code, text = run_check(ctx, root)
    ok = (res.unlisted == ["scripts/b.py"] and "файл ядра не в перечне: scripts/b.py" in text and code == 1)
    return ok, (f"файлов ядра не в перечне: {res.unlisted} (ждём ровно ['scripts/b.py']); "
                f"bite-x.py, migrations/x.py, файл «вне ядра» и файл вне scripts/ — не названы; код {code} (ждём 1)")


def case8(ctx: Ctx):
    notes = []
    ok = True

    def expect(label, got, want_code, words=(), no_words=()):
        nonlocal ok
        code, text = got
        good = code == want_code and all(w in text for w in words) and not any(w in text for w in no_words)
        ok &= good
        notes.append(f"{label}: код {code} (ждём {want_code}){'' if good else ' — НЕ ТО'}")

    clean = mini(ctx.tmp, "c8clean", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"])
    expect("чисто", run_main(ctx, clean), 0, ["проверка прошла"])
    # находка в обоих видах: поломки «код / печать не проверяется» её не гасят — под ними падает только свой случай
    dirty = mini(ctx.tmp, "c8dirty", {"scripts/a.py": 'ROLE = "ZZQ"\nprint("ZZQ")\n'}, ["scripts/a.py"])
    expect("находка", run_main(ctx, dirty), 1, ["проверка провалилась"])
    nolist = mini(ctx.tmp, "c8nolist", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"])
    (nolist / "vnext" / "tools" / "core-files.txt").unlink()
    expect("нет перечня файлов ядра", run_main(ctx, nolist), 2,
           ["нет файла перечня файлов ядра", "НЕ ПРОВЕРЕНО"], ["проверка прошла"])
    nonames = mini(ctx.tmp, "c8nonames", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"])
    (nonames / "vnext" / "tools" / "donor-names.json").unlink()
    expect("нет файла имён", run_main(ctx, nonames), 2, ["нет файла имён донора", "НЕ ПРОВЕРЕНО"], ["проверка прошла"])
    expect("--commit без репозитория", run_main(ctx, clean, "--commit", "no-such-commit"), 2,
           ["нет commit", "НЕ ПРОВЕРЕНО"], ["проверка прошла"])
    # git недоступен: --commit — 2 со словами про git; рабочее дерево проверяется обходом каталога
    saved_path = os.environ.get("PATH", "")
    empty = sub(ctx.tmp, "c8nogit")
    os.environ["PATH"] = str(empty)
    try:
        expect("--commit без git", run_main(ctx, clean, "--commit", "HEAD"), 2, ["git не найден", "НЕ ПРОВЕРЕНО"], ["проверка прошла"])
        expect("рабочее дерево без git, находка", run_main(ctx, dirty), 1, ["проверка провалилась"])
    finally:
        os.environ["PATH"] = saved_path
    # --strict: исключение без попадания — печатается; с ключом становится провалом
    stale = mini(ctx.tmp, "c8stale", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"],
                 allowed=[("scripts/a.py", "ZZQ", "code", "fixture", 'ROLE = "ZZQ"', "строка давно исправлена")])
    expect("исключение без попадания, без --strict", run_main(ctx, stale), 0, ["исключение без попадания"])
    expect("исключение без попадания, --strict", run_main(ctx, stale, "--strict"), 1, ["исключение без попадания"])
    return ok, "; ".join(notes)


def copy_goal(goal: Path, dest: Path) -> Path:
    for rel in ("e2/hits.tsv", "e2/metrics.json", "e3/count-core.py", "e3/core-list.txt",
                "e3/core-classes.tsv", "e3/core-additions.tsv"):
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(goal / rel, dest / rel)
    return dest


def edit_first_line(path: Path, accept: Callable, change: Callable) -> str:
    """Правит ПЕРВУЮ подходящую строку TSV; -> её начало для сообщения. Подходящей нет — ошибка стенда."""
    lines = path.read_bytes().decode("utf-8").split("\n")
    for i, line in enumerate(lines):
        if accept(line.rstrip("\r").split("\t")):
            lines[i] = change(line)
            path.write_bytes("\n".join(lines).encode("utf-8"))
            return "\t".join(line.split("\t")[:2])
    raise AssertionError(f"в {path.name} нет строки для искажения — каталог замеров изменился, случай надо пересмотреть")


def case9(ctx: Ctx):
    goal = ctx.goal
    if goal is None:
        return None, "каталог замеров не указан (--goal-dir): сверку не выполнить — это НЕ «прошла»"
    if not goal.is_dir():
        return None, f"каталога замеров нет: {goal} — НЕ ПРОВЕРЕНО"
    guard = ctx.guard
    notes = []

    def reconcile(g: Path, commit=None):
        lines = []
        code = guard.reconcile(g, PACK_ROOT, HERE, commit, out=lines.append)
        return code, "\n".join(lines)

    code, text = reconcile(goal)
    if code == 2:
        return None, "настоящая сверка вернула «не проверено»: " + text.strip().split("\n")[-1]
    first = next((l for l in text.split("\n") if l.startswith("(а)")), "")
    second = next((l for l in text.split("\n") if l.startswith("(б)")), "")
    m = re.search(r"совпало (\d+) из (\d+)", first)
    equal_a = bool(m) and m.group(1) == m.group(2) and int(m.group(2)) > 0
    hard_b = ("в счёте count-core.py есть, проверка не нашла" in text) or ("нашла проверка, в счёте count-core.py нет" in text)
    ok_real = code == 0 and equal_a and not hard_b
    notes.append(f"настоящая сверка: код {code} (ждём 0); {first}; {second.split(';')[0] if second else '(б) не напечатано'}; "
                 f"{'(б) сходится' if not hard_b else '(б) расходится'}")

    # искажённая копия 1: у одной строки кода сменена группа в замере Э2 — расхождение (а)
    d1 = copy_goal(goal, sub(ctx.tmp, "c9goal1"))
    core_files = {x.strip() for x in (d1 / "e3" / "core-list.txt").read_text(encoding="utf-8").split("\n") if x.strip()}
    edit_first_line(d1 / "e2" / "hits.tsv", lambda p: len(p) > 6 and p[2] == "role" and p[4] == "code" and p[0] in core_files,
                    lambda l: l.replace("\trole\t", "\tneighbor\t", 1))
    code1, text1 = reconcile(d1)
    ok_a = code1 == 1 and "есть в замере Э2, движок не нашёл" in text1 and "нашёл движок, в замере Э2 нет" in text1
    notes.append(f"копия с чужой группой в замере: код {code1} (ждём 1), расхождение (а) названо: {ok_a}")

    # искажённая копия 2: у одной строки счёта Э3 сменён класс behavior → printed — расхождение (б)
    d2 = copy_goal(goal, sub(ctx.tmp, "c9goal2"))
    edit_first_line(d2 / "e3" / "core-classes.tsv", lambda p: len(p) > 3 and p[2] == "behavior",
                    lambda l: l.replace("\tbehavior\t", "\tprinted\t", 1))
    code2, text2 = reconcile(d2)
    ok_b = code2 == 1 and "нашла проверка, в счёте count-core.py нет" in text2
    notes.append(f"копия с иным классом строки в счёте Э3: код {code2} (ждём 1), расхождение (б) названо: {ok_b}")

    # нет каталога замеров / нет такого commit — НЕ ПРОВЕРЕНО, код 2, не «сходятся»
    code3, text3 = reconcile(ctx.tmp / "нет-такого-каталога")
    code4, text4 = reconcile(goal, "no-such-commit")
    saved_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(sub(ctx.tmp, "c9nogit"))      # git недоступен
    try:
        code5, text5 = reconcile(goal)
    finally:
        os.environ["PATH"] = saved_path
    ok_n = (code3 == 2 and code4 == 2 and code5 == 2 and "НЕ ПРОВЕРЕНО" in text3 and "НЕ ПРОВЕРЕНО" in text4
            and "НЕ ПРОВЕРЕНО" in text5 and "git не найден" in text5 and "сходятся" not in text3 + text4 + text5)
    notes.append(f"нет каталога: код {code3}, нет commit: код {code4}, нет git: код {code5} "
                 f"(ждём 2, 2 и 2, слова «НЕ ПРОВЕРЕНО»; про git — «git не найден»)")
    return (ok_real and ok_a and ok_b and ok_n), "\n".join(notes)


def case10(ctx: Ctx):
    pack = ctx.tmp / "c10"
    tools = pack / "vnext" / "tools"
    live = ctx.tmp / "c10live"
    tools.mkdir(parents=True)
    sync_src = SYNC_PATH.read_text(encoding="utf-8")
    if ctx.sync_patch is not None:
        sync_src, n = ctx.sync_patch(sync_src)
        if n != 1:
            raise AssertionError(f"поломка нашла свою цель {n} раз(а) в sync-to-template.py, ждали ровно один")
    write(tools / "sync-to-template.py", sync_src)
    for p in (GUARD_PATH, SCAN_PATH):
        shutil.copyfile(p, tools / p.name)
    write(tools / "core-files.txt", "[ядро]\nscripts/write-message.py\n")
    write(tools / "donor-names.json", names_json(FICTIONAL))
    write(tools / "donor-literals-allowed.tsv", "file\tname\tkind\tclass\ttext\treason\n")
    # корни переноса выводятся из mezo_paths: подставной модуль указывает во временные каталоги
    write(pack / "vnext" / "prototype" / "mezo_paths.py",
          "from pathlib import Path\n"
          f"_C = Path({str(live)!r})\n"
          "def container_root(*a, **k):\n    return _C\n"
          "def live_scripts(*a, **k):\n    return _C / '.mezosync' / 'scripts'\n")
    live_file = live / ".mezosync" / "scripts" / "write-message.py"

    def go(*args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, str(tools / "sync-to-template.py"), *args], capture_output=True, env=env, cwd=str(pack))
        return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    notes = []
    write(live_file, 'ROLE = "ZZQ"\nprint("ZZQ")\n')
    c1, t1 = go("--apply")
    moved = (pack / "scripts" / "write-message.py").is_file()
    ok1 = c1 == 1 and "commit не делать" in t1 and "находка: scripts/write-message.py" in t1 and moved
    notes.append(f"--apply, в файле литерал: код {c1} (ждём 1), «commit не делать» есть: {'commit не делать' in t1}, перенос сделан: {moved}")
    c2, t2 = go()
    ok2 = c2 == 0 and "находка: scripts/write-message.py" in t2 and "commit не делать" not in t2
    notes.append(f"замер при уже сведённой паре: код {c2} (ждём 0 — код замера от находок не меняется), находки напечатаны: "
                 f"{'находка: scripts/write-message.py' in t2}")
    write(live_file, "ROLE = 1\n")
    c3, t3 = go("--apply")
    ok3 = c3 == 0 and "commit не делать" not in t3 and "проверка прошла" in t3
    notes.append(f"--apply, литерала нет: код {c3} (ждём 0), «commit не делать» нет: {'commit не делать' not in t3}")
    return (ok1 and ok2 and ok3), "\n".join(notes)


CASE_FUNCS = {1: case1, 2: case2, 3: case3, 4: case4, 5: case5, 6: case6, 7: case7, 8: case8, 9: case9, 10: case10}


# ── нарочные поломки: ожидание записано ЗАРАНЕЕ ──────────────────────────────────

class Break(NamedTuple):
    key: str
    title: str
    own: int              # случай, который поломка обязана провалить — и только он
    target: str           # что правится: guard · scan · sync
    patch: Callable       # patch(src) -> (новый текст, сколько раз нашлась цель)


def kinds_patch(new_value: str):
    return lambda s: replace_once(s, 'CHECKED_KINDS = ("code", "shown")', f"CHECKED_KINDS = {new_value}")


def names_in_code_patch(real_role: str):
    inject = ('    groups.setdefault("role", []).append(Rule("role", {"type": "words", "list": "_builtin"}, '
              f'"встроено в код", dict(lists, _builtin=[{real_role!r}])))\n    return Names(groups, lists)\n')
    return lambda s: replace_once(s, "    return Names(groups, lists)\n", inject)


def exception_by_line_patch(s: str):
    s, n1 = replace_once(s, "def exception_key(file, name, kind, text, line=None):",
                         "FROZEN = {}\n\n\ndef exception_key(file, name, kind, text, line=None):")
    s, n2 = replace_once(s, "    return (file, name, kind, text)\n",
                         "    if FROZEN:      # ПОЛОМКА: ключ — номер строки, запомненный при заведении исключения\n"
                         "        return (file, name, kind, FROZEN.get((file, name, kind, text)) if line is None else line)\n"
                         "    return (file, name, kind, text)\n")
    return s, min(n1, n2)


def make_breaks(real_role: str):
    return [
        Break("code-unchecked", "код не проверяется", 1, "guard", kinds_patch('("shown",)')),
        Break("print-unchecked", "печать не проверяется", 2, "guard", kinds_patch('("code",)')),
        Break("comment-counted", "комментарий считается", 3, "guard", kinds_patch('("code", "shown", "docstring", "comment")')),
        Break("names-in-code", "имена вписаны в код", 4, "scan", names_in_code_patch(real_role)),
        Break("exception-by-line", "исключение по номеру строки", 5, "guard", exception_by_line_patch),
        Break("no-role-literal-group", "нет группы роли целой строкой", 6, "scan",
              lambda s: replace_once(s, "        self.rules = [r for rules in groups.values() for r in rules]",
                                     '        self.rules = [r for rules in groups.values() for r in rules if r.kind != "whole_literal"]')),
        Break("file-list-unchecked", "перечень файлов не сверяется", 7, "guard",
              lambda s: replace_once(s, "    return sorted(p for p in paths if is_runtime_script(p) and p not in core_set and p not in outside)",
                                     "    return []")),
        Break("exit2-as-0", "код 2 подменён на 0", 8, "guard",
              lambda s: replace_once(s, "    return exit_code(res, args.strict)\n",
                                     "    return 0 if exit_code(res, args.strict) == 2 else exit_code(res, args.strict)\n")),
        Break("reconcile-skips-b", "сверка (б) пропускает расхождение", 9, "guard",
              lambda s: replace_once(s, "    only_cc = sorted(cc_rows - guard_rows)\n    only_guard = sorted(guard_rows - cc_rows)\n",
                                     "    only_cc = []\n    only_guard = []\n")),
        Break("sync-no-guard", "sync-to-template не зовёт проверку", 10, "sync",
              lambda s: replace_once(s, "    code = donor_literals_check()\n", "    code = 0\n")),
    ]


def run_case(number: int, scan, guard, goal, real_role, sync_patch=None):
    """Один случай в своём временном каталоге. -> (исход, подробности); неожиданная ошибка стенда — провал с текстом."""
    tmp = Path(tempfile.mkdtemp(prefix=f"bite-donor-literals-{number}-"))
    try:
        return CASE_FUNCS[number](Ctx(scan, guard, tmp, real_role, goal, sync_patch))
    except Exception as e:      # стенд сломался — это провал случая со словами, а не молчание
        return False, f"стенд случая упал: {type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_clean(goal, real_role) -> bool:
    scan, guard = load_pair()
    ok_all = True
    for n in range(1, 11):
        verdict, detail = run_case(n, scan, guard, goal, real_role)
        ok_all &= case(f"{CASE_MARKS[n]} {CASE_TITLES[n]}", verdict, detail)
    return ok_all


def run_breaks(keys, goal, real_role) -> bool:
    ok_all = True
    table = {b.key: b for b in make_breaks(real_role)}
    for key in keys:
        b = table[key]
        mark = CASE_MARKS[b.own]
        sync_patch = b.patch if b.target == "sync" else None
        try:
            if b.target == "sync":
                scan, guard = load_pair()
            else:
                scan, guard = load_pair(b.patch if b.target == "scan" else None,
                                        b.patch if b.target == "guard" else None)
        except AssertionError as e:
            ok_all &= case(f"поломка «{b.title}» поймана случаем {mark}", False, str(e))
            continue
        # свой случай — обязан провалиться
        verdict, detail = run_case(b.own, scan, guard, goal, real_role, sync_patch)
        if verdict is None:
            ok_all &= case(f"поломка «{b.title}» поймана случаем {mark}", None, "случай не проверен — поломку не судить; " + detail)
            continue
        caught = verdict is False
        # остальные случаи ①–⑧ — не должны пострадать (⑨ и ⑩ тяжёлые: гоняются, только когда свои)
        collateral = []
        if b.own <= 8:
            for n in range(1, 9):
                if n == b.own:
                    continue
                v, _ = run_case(n, scan, guard, goal, real_role)
                if v is False:
                    collateral.append(CASE_MARKS[n])
        exact = caught and not collateral
        tail = "больше ни один из случаев ①–⑧ не провалился" if not collateral else "заодно провалились: " + " ".join(collateral)
        if b.own > 8:
            tail = "остальные случаи под этой поломкой не гонялись (они её не касаются)"
        ok_all &= case(f"поломка «{b.title}» поймана случаем {mark}", exact,
                       f"под поломкой случай {mark} {'провалился' if caught else 'НЕ провалился (поломка не поймана)'}: {detail}\n{tail}")
    return ok_all


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Приёмка проверки guard-donor-literals.py: случаи на подставном мини-пакете и нарочные поломки.",
        epilog="Исход: 0 — принято; 1 — не принято; 2 — приёмку выполнить не удалось или случай ⑨ не проверен.")
    ap.add_argument("--goal-dir", metavar="КАТАЛОГ",
                    help="каталог goal-gordi-core с замером Э2 и счётом Э3 — нужен случаю ⑨; без него ⑨ «НЕ ПРОВЕРЕН»")
    ap.add_argument("--cases", action="store_true", help="только случаи, без нарочных поломок")
    ap.add_argument("--break", dest="brk", metavar="ИМЯ",
                    help="одна нарочная поломка или all — все; без чистого прогона. Имена: " +
                         ", ".join(["code-unchecked", "print-unchecked", "comment-counted", "names-in-code", "exception-by-line",
                                    "no-role-literal-group", "file-list-unchecked", "exit2-as-0", "reconcile-skips-b", "sync-no-guard"]))
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for p in (GUARD_PATH, SCAN_PATH, SYNC_PATH, NAMES_PATH):
        if not p.exists():
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого нет — {p}")
            return 2
    real_role = json.loads(NAMES_PATH.read_text(encoding="utf-8-sig"))["lists"]["roles"][0]
    goal = Path(args.goal_dir) if args.goal_dir else None
    names = [b.key for b in make_breaks(real_role)]
    if args.brk and args.brk != "all" and args.brk not in names:
        print(f"⛔ нет поломки «{args.brk}». Есть: {', '.join(names)}, all")
        return 2

    ok_all = True
    if args.brk:
        ok_all &= run_breaks(names if args.brk == "all" else [args.brk], goal, real_role)
    else:
        ok_all &= run_clean(goal, real_role)
        if not args.cases:
            ok_all &= run_breaks(names, goal, real_role)
    print()
    if not ok_all:
        print(f"🔴 НЕ ПРИНЯТО — проверено {CASES}, прошло {PASSED}, не проверено {UNCHECKED}")
        return 1
    if UNCHECKED:
        print(f"⚪ ПРИНЯТО НЕ ПОЛНОСТЬЮ — проверено {CASES}, прошло {PASSED}, НЕ ПРОВЕРЕНО {UNCHECKED} (нужен --goal-dir и git с нужным commit)")
        return 2
    print(f"✅ ПРИНЯТО — проверено {CASES}, прошло {PASSED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
