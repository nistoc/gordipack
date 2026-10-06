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
  ⑨ настоящий пакет, только чтение: сверка версии замера Э2 ЕЁ перечнем исключений (donor-literals-allowed-<commit>.tsv
     рядом с проверкой: в самой версии замера перечня нет, он появился позже) даёт (а) и (б) сходящимися; на искажённой
     копии каталога замеров — расходящимися; нет каталога, commit или перечня версии — «НЕ ПРОВЕРЕНО» с кодом 2;
  ⑩ sync-to-template.py (его копия во временном мини-пакете, где корни указывают во временные
     каталоги): с --apply при находке — код 1 и строка «commit не делать»; без находки — код 0;
     в режиме замера код выхода от находок не меняется.
  ⑪ перехватчик git pre-commit (карточка #678, этап Э4, шаг Ш1, пункт д): commit файла ядра с литералом
     донора — отказ (код не 0, нового commit нет, файл остался в индексе; в тексте названы файл, роль,
     команда просмотра и файл исключений);
  ⑫ встречный: commit чистого файла ядра и commit файла вне перечня ядра с литералом — проходят;
  ⑬ граница «рабочее дерево, а не индекс»: (i) в индексе чисто, литерал лежит на диске в файле вне commit —
     отказ; (ii) литерал в индексе, на диске убран — перехватчик ПРОПУСКАЕТ (известная щель, она названа в
     комментарии перехватчика), а проверка уже сделанного commit (--commit HEAD) литерал находит;
  ⑭ сбой самой проверки — тоже отказ, не пропуск: нет файла проверки; проверка вернула код 2 (нет перечня
     файлов ядра). «Не проверено» не бывает «чисто».
  Случаи ⑪–⑭ гоняют НАСТОЯЩИЙ файл `.githooks/pre-commit` пакета и настоящие guard-donor-literals.py и
  donor_scan.py: их копии лежат в подставном git-репозитории во временном каталоге, а команда
  `git config core.hooksPath .githooks` выполняется ТОЛЬКО там. Настоящий репозиторий не читается и не
  правится. Нет git или нет файла перехватчика — «НЕ ПРОВЕРЕН», не «прошла».
  ⑮ сверка судит commit перечнем исключений ИЗ ЭТОГО ЖЕ commit, а не рабочего дерева: в судимом commit перечень
     покрывает печатную строку, в рабочем дереве перечень пуст — сверка сходится только если взят перечень commit;
  ⑯ встречный: в судимом commit перечня нет, а в рабочем дереве он есть — отказ словами (код 2, «НЕ ПРОВЕРЕНО»,
     названы commit и ключ --reconcile-allowed), без печати результата сверки: не пустой перечень и не перечень
     рабочего дерева;
  ⑰ встречный: перечень, названный ключом --reconcile-allowed, берёт верх над перечнем commit и годится commit без
     перечня; названный, но отсутствующий — отказ словами, не пустой перечень.
  Случаи ⑮–⑰ гоняют проверку на подставном git-репозитории во временном каталоге и подставном каталоге замеров
  (заглушка count-core.py печатает заданный счёт); настоящий пакет и настоящий каталог замеров не читаются.
  Нет git — «НЕ ПРОВЕРЕН».

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
Поломки перехватчика правят ТЕКСТ его копии в подставном репозитории (настоящий файл не трогается);
ожидание — НАБОР провалившихся случаев ⑪–⑭ — записано заранее (HookBreak.expect), все четыре гоняются
под каждой поломкой, провалиться обязаны ровно записанные:
Поломки сверки (случаи ⑮–⑰) правят ТЕКСТ проверки в памяти; ожидание — тоже НАБОР случаев, записан заранее
(ReconBreak.expect). Под каждой гоняются ①–⑧ и ⑮–⑰, провалиться обязаны ровно записанные:
  allowed-from-tree       перечень читается из рабочего дерева — как было до правки  → ⑮ ⑯
  absent-list-as-empty    в commit перечня нет — берётся тихий пустой перечень      → ⑯
  named-list-ignored      перечень, названный ключом, не читается                   → ⑰
  named-missing-as-empty  названного перечня нет — берётся пустой                    → ⑰
Поломки перехватчика (⑪–⑭), как и выше:
  hook-off                перехватчик выключен — выход сразу      → ⑪ ⑬ ⑭
  guard-not-called        перехватчик не зовёт проверку           → ⑪ ⑬ ⑭
  hooks-path-unset        команда core.hooksPath не выполнена     → ⑪ ⑬ ⑭
  hook-silent             отказ без списка находок                → ⑪
  fail-open-no-guard      нет файла проверки — commit пропущен    → ⑭
  fail-open-guard-error   проверка не удалась — commit пропущен   → ⑭
Исход каждого случая — один из трёх: прошёл · провалился · НЕ ПРОВЕРЕН (⑨ без каталога замеров или без перечня
версии замера; ⑪–⑭ без git или без файла перехватчика; ⑮–⑰ без git).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Callable, NamedTuple

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent.parent
GUARD_PATH = HERE / "guard-donor-literals.py"
SCAN_PATH = HERE / "donor_scan.py"
SYNC_PATH = HERE / "sync-to-template.py"
E2_ALLOWED_NAME = "donor-literals-allowed-{}.tsv"          # перечень исключений версии замера Э2: рядом с проверкой
NAMES_PATH = HERE / "donor-names.json"
HOOK_PATH = PACK_ROOT / ".githooks" / "pre-commit"      # перехватчик git pre-commit самого пакета

FICTIONAL = ("ZZQ", "ZZW")      # выдуманные роли подставного мини-пакета
CASE_MARKS = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨", 10: "⑩",
              11: "⑪", 12: "⑫", 13: "⑬", 14: "⑭", 15: "⑮", 16: "⑯", 17: "⑰"}
CASE_TITLES = {
    1: "литерал роли в коде — находка",
    2: "литерал в печати — находка",
    3: "встречный: тот же литерал в комментарии и строке документации — не находка",
    4: "имена берутся из файла данных, а не из кода проверки",
    5: "исключение держится за текст строки, а не за её номер",
    6: "роль целой строкой в любом регистре: «zzq» — находка, «zzqrator» — нет",
    7: "файл scripts/*.py вне перечня — находка; bite-*.py, migrations/ и «вне ядра» — нет",
    8: "коды выхода 0 / 1 / 2 — словами; «не проверено» не бывает «прошла»",
    9: "настоящий пакет: версия замера Э2 с её перечнем исключений сходится со счётом Э3; искажённую копию ловит; без каталога — НЕ ПРОВЕРЕНО",
    10: "sync-to-template.py: находка при --apply — код 1 и «commit не делать»",
    11: "перехватчик pre-commit: commit файла ядра с литералом донора — отказ, нового commit нет",
    12: "встречный: commit чистого файла ядра и файла вне ядра с литералом — проходят",
    13: "граница: перехватчик судит рабочее дерево, не индекс; сделанный commit проверяет --commit HEAD",
    14: "сбой самой проверки (нет файла, код 2) — отказ, а не пропуск",
    15: "сверка судит commit перечнем исключений из этого же commit, а не из рабочего дерева",
    16: "встречный: в судимом commit перечня нет — отказ словами, не пустой перечень и не перечень рабочего дерева",
    17: "встречный: перечень, названный ключом, берёт верх над перечнем commit; названного нет — отказ словами",
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
    hook_patch: Callable | None = None   # правка текста перехватчика (нарочная поломка ⑪–⑭)
    hook_enable: bool = True             # False — в стенде не выполнена команда core.hooksPath


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
    # Перечень исключений ВЕРСИИ замера: в самой версии своего перечня нет (он появился позже), он лежит рядом с
    # проверкой под именем версии. Основной перечень (нового кода) версию замера судит с ложными расхождениями.
    allowed = None
    try:
        head_id = str(json.loads((goal / "e2" / "metrics.json").read_text(encoding="utf-8")).get("head") or "")
    except (OSError, ValueError):
        head_id = ""
    if head_id:
        allowed = HERE / E2_ALLOWED_NAME.format(head_id)
        if not allowed.is_file():
            return None, f"нет перечня исключений версии замера Э2: {allowed} — сверку не выполнить: НЕ ПРОВЕРЕНО"

    def reconcile(g: Path, commit=None):
        lines = []
        code = guard.reconcile(g, PACK_ROOT, HERE, commit, out=lines.append, allowed_file=allowed)
        return code, "\n".join(lines)

    code, text = reconcile(goal)
    if code == 2:
        return None, "настоящая сверка вернула «не проверено»: " + text.strip().split("\n")[-1]
    first = next((l for l in text.split("\n") if l.startswith("(а)")), "")
    second = next((l for l in text.split("\n") if l.startswith("(б)")), "")
    source = next((l for l in text.split("\n") if l.startswith("перечень исключений:")), "")
    m = re.search(r"совпало (\d+) из (\d+)", first)
    equal_a = bool(m) and m.group(1) == m.group(2) and int(m.group(2)) > 0
    hard_b = ("в счёте count-core.py есть, проверка не нашла" in text) or ("нашла проверка, в счёте count-core.py нет" in text)
    ok_real = code == 0 and equal_a and not hard_b and "(назван при запуске)" in source
    notes.append(f"настоящая сверка: код {code} (ждём 0); {source}; {first}; {second.split(';')[0] if second else '(б) не напечатано'}; "
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

    # нет каталога замеров / нет такого commit — НЕ ПРОВЕРЕНО, код 2, не «сходятся»; причина названа ТОЙ, что есть
    # (перечень версии замера при этом назван, поэтому «нет commit» не может прикрыться «нет перечня»)
    code3, text3 = reconcile(ctx.tmp / "нет-такого-каталога")
    code4, text4 = reconcile(goal, "no-such-commit")
    saved_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(sub(ctx.tmp, "c9nogit"))      # git недоступен
    try:
        code5, text5 = reconcile(goal)
    finally:
        os.environ["PATH"] = saved_path
    ok_n = (code3 == 2 and code4 == 2 and code5 == 2 and "НЕ ПРОВЕРЕНО" in text3 and "НЕ ПРОВЕРЕНО" in text4
            and "НЕ ПРОВЕРЕНО" in text5 and "нет commit" in text4 and "git не найден" in text5
            and "сходятся" not in text3 + text4 + text5)
    notes.append(f"нет каталога: код {code3}, нет commit: код {code4}, нет git: код {code5} "
                 f"(ждём 2, 2 и 2, слова «НЕ ПРОВЕРЕНО»; про commit — «нет commit»; про git — «git не найден»)")
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


# ── случаи ⑪–⑭: перехватчик git pre-commit (.githooks/pre-commit) ───────────────────
# Гоняется НАСТОЯЩИЙ файл перехватчика и настоящие guard-donor-literals.py и donor_scan.py: их копии
# кладутся в подставной git-репозиторий во временном каталоге, а core.hooksPath ставится ТОЛЬКО там.
# Настоящий репозиторий пакета не читается и не правится. Нет git или нет файла перехватчика —
# случаи «НЕ ПРОВЕРЕН», а не «прошла».

def git_env() -> dict:
    """Среда для git на стенде: без переменных GIT_* вызывающего (иначе стенд писал бы в чужой репозиторий),
    python приёмки первым в PATH (перехватчик берёт «python» из PATH — берёт тот же), вывод по-русски."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def git(root: Path, *args) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, env=git_env())
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


def head(root: Path) -> str | None:
    code, out = git(root, "rev-parse", "HEAD")
    return out.strip() if code == 0 else None


def hook_unavailable() -> str | None:
    """Почему случаи перехватчика не выполнить (None — можно)."""
    if shutil.which("git") is None:
        return "git не найден — перехватчик исполнить нечем: НЕ ПРОВЕРЕНО"
    if not HOOK_PATH.is_file():
        return f"нет файла перехватчика {HOOK_PATH}: НЕ ПРОВЕРЕНО"
    return None


def hook_repo(ctx: Ctx, name: str, files: dict, core, outside=None, with_guard=True, no_core_list=False) -> Path:
    """Подставной git-репозиторий: файлы пакета, данные проверки, копия проверки и перехватчика, начальный commit.
    ctx.hook_patch правит ТЕКСТ перехватчика; ctx.hook_enable=False — стенд без команды core.hooksPath."""
    root = mini(ctx.tmp, name, files, core, outside=outside)
    tools = root / "vnext" / "tools"
    if with_guard:
        for p in (GUARD_PATH, SCAN_PATH):
            shutil.copyfile(p, tools / p.name)
    if no_core_list:
        (tools / "core-files.txt").unlink()
    text = HOOK_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    if ctx.hook_patch is not None:
        text, n = ctx.hook_patch(text)
        if n != 1:
            raise AssertionError(f"поломка нашла свою цель {n} раз(а) в перехватчике, ждали ровно один")
    hook = root / ".githooks" / "pre-commit"
    write(hook, text)
    os.chmod(hook, 0o755)
    for args in (("init", "-q"), ("config", "user.name", "приёмка"), ("config", "user.email", "bite@localhost.test"),
                 ("config", "core.autocrlf", "false"), ("config", "commit.gpgsign", "false")):
        git(root, *args)
    if ctx.hook_enable:
        git(root, "config", "core.hooksPath", ".githooks")
    git(root, "add", "-A")
    code, out = git(root, "commit", "-q", "--no-verify", "-m", "начальный")
    if code != 0:
        raise AssertionError(f"стенд: начальный commit не создался: {out.strip()}")
    return root


def trail(ok: bool, out: str, what: str = "git") -> str:
    """Хвост вывода (git или сверки) — только когда случай не прошёл: чтобы причину не приходилось гадать."""
    return "" if ok else f"\nвывод {what}: " + " ⏎ ".join(out.strip().splitlines())[-500:]


def commit(root: Path, message: str) -> tuple[int, str, str | None, str | None]:
    """git commit с перехватчиком. -> (код, вывод, HEAD до, HEAD после)."""
    before = head(root)
    code, out = git(root, "commit", "-m", message)
    return code, out, before, head(root)


def case11(ctx: Ctx):
    why = hook_unavailable()
    if why:
        return None, why
    root = hook_repo(ctx, "c11", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"])
    write(root / "scripts" / "a.py", 'ROLE = "ZZQ"\n')
    git(root, "add", "scripts/a.py")
    code, out, before, after = commit(root, "ядро с литералом донора")
    _, staged = git(root, "diff", "--cached", "--name-only")
    words = ["commit ОТМЕНЁН", "scripts/a.py", "ZZQ", "guard-donor-literals.py", "donor-literals-allowed.tsv"]
    missing = [w for w in words if w not in out]
    ok = code != 0 and after == before and not missing and staged.strip() == "scripts/a.py"
    return ok, (f"commit файла ядра с литералом: код {code} (ждём не 0); новый commit "
                f"{'НЕ создан' if after == before else 'СОЗДАН'} (ждём не создан); в индексе остался {staged.strip()!r}; "
                f"в тексте отказа нет слов: {missing or 'нет, всё названо'} (нужны: файл, роль, команда просмотра, файл исключений)"
                + trail(ok, out))


def case12(ctx: Ctx):
    why = hook_unavailable()
    if why:
        return None, why
    root = hook_repo(ctx, "c12", {"scripts/a.py": "X = 1\n", "scripts/c.py": "X = 1\n"}, ["scripts/a.py"],
                     outside={"scripts/c.py": "стенд приёмки, не ядро"})
    write(root / "scripts" / "a.py", "X = 2\n")
    git(root, "add", "scripts/a.py")
    code1, out1, before1, after1 = commit(root, "чистая правка ядра")
    # встречный-2: литерал в файле, которого перечень ядра не считает ядром («вне ядра») — перехватчик не придирается
    write(root / "scripts" / "c.py", 'ROLE = "ZZQ"\n')
    git(root, "add", "scripts/c.py")
    code2, out2, before2, after2 = commit(root, "файл вне ядра с литералом")
    ok = (code1 == 0 and after1 != before1 and "ОТМЕНЁН" not in out1
          and code2 == 0 and after2 != before2 and "ОТМЕНЁН" not in out2)
    return ok, (f"чистый файл ядра: код {code1} (ждём 0), commit {'создан' if after1 != before1 else 'НЕ создан'}; "
                f"файл вне ядра с литералом: код {code2} (ждём 0), commit {'создан' if after2 != before2 else 'НЕ создан'}"
                + trail(ok, out1 + "\n" + out2))


def case13(ctx: Ctx):
    why = hook_unavailable()
    if why:
        return None, why
    root = hook_repo(ctx, "c13", {"scripts/a.py": "X = 1\n", "scripts/b.py": "X = 1\n"}, ["scripts/a.py", "scripts/b.py"])
    # (i) в индексе чисто, литерал лежит на диске в файле, которого в commit нет — перехватчик видит диск и отказывает
    write(root / "scripts" / "a.py", "X = 2\n")
    git(root, "add", "scripts/a.py")
    write(root / "scripts" / "b.py", 'ROLE = "ZZQ"\n')
    code1, out1, before1, after1 = commit(root, "в индексе чисто, литерал на диске")
    refused = code1 != 0 and after1 == before1
    # (ii) литерал В ИНДЕКСЕ, на диске уже убран — перехватчик пропускает (известная щель: он не читает индекс)
    git(root, "add", "scripts/b.py")
    write(root / "scripts" / "b.py", "X = 1\n")
    code2, out2, before2, after2 = commit(root, "литерал в индексе, на диске чисто")
    _, blob = git(root, "show", "HEAD:scripts/b.py")
    passed = code2 == 0 and after2 != before2 and "ZZQ" in blob
    # щель закрывает проверка уже сделанного commit — так сказано в комментарии перехватчика, здесь это проверяется
    tools = root / "vnext" / "tools"
    cmd = [sys.executable, str(tools / "guard-donor-literals.py"), "--root", str(root), "--data-dir", str(tools),
           "--commit", "HEAD"]
    r = subprocess.run(cmd, capture_output=True, env=git_env(), cwd=str(root))   # env: caller — проверка литералов не читает MEZO_CONTAINER, среда очищена от GIT_*
    later = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    closed = r.returncode == 1 and "ZZQ" in later and "scripts/b.py" in later
    ok = refused and passed and closed
    return ok, (f"(i) в индексе чисто, литерал на диске вне commit: код {code1} (ждём не 0), commit "
                f"{'не создан' if after1 == before1 else 'СОЗДАН'} (ждём не создан); "
                f"(ii) литерал в индексе, на диске убран: код {code2} (ждём 0 — граница: перехватчик судит диск, не индекс), "
                f"литерал в commit {'есть' if 'ZZQ' in blob else 'НЕТ'} (ждём есть); "
                f"проверка сделанного commit (--commit HEAD): код {r.returncode} (ждём 1), литерал "
                f"{'найден' if closed else 'НЕ найден'}" + trail(ok, out1 + "\n" + out2 + "\n" + later))


def case14(ctx: Ctx):
    why = hook_unavailable()
    if why:
        return None, why
    # (i) нет файла проверки
    r1 = hook_repo(ctx, "c14a", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"], with_guard=False)
    write(r1 / "scripts" / "a.py", "X = 2\n")
    git(r1, "add", "scripts/a.py")
    code1, out1, before1, after1 = commit(r1, "правка без проверки")
    ok1 = code1 != 0 and after1 == before1 and "нет файла проверки" in out1
    # (ii) сама проверка не смогла (нет перечня файлов ядра — код 2): «не проверено» не пропускается
    r2 = hook_repo(ctx, "c14b", {"scripts/a.py": "X = 1\n"}, ["scripts/a.py"], no_core_list=True)
    write(r2 / "scripts" / "a.py", "X = 2\n")
    git(r2, "add", "scripts/a.py")
    code2, out2, before2, after2 = commit(r2, "правка при сбое проверки")
    ok2 = code2 != 0 and after2 == before2 and "НЕ ПРОВЕРЕНО" in out2 and "НЕ УДАЛОСЬ" in out2
    return (ok1 and ok2), (
        f"(i) нет файла проверки: код {code1} (ждём не 0), commit {'не создан' if after1 == before1 else 'СОЗДАН'}, "
        f"слова «нет файла проверки» {'есть' if 'нет файла проверки' in out1 else 'НЕТ'}; "
        f"(ii) проверка вернула код 2: код {code2} (ждём не 0), commit {'не создан' if after2 == before2 else 'СОЗДАН'}, "
        f"слова «НЕ ПРОВЕРЕНО» и «НЕ УДАЛОСЬ» {'есть' if ('НЕ ПРОВЕРЕНО' in out2 and 'НЕ УДАЛОСЬ' in out2) else 'НЕТ'}"
        + trail(ok1 and ok2, out1 + "\n" + out2))


# ── случаи ⑮–⑰: сверка судит версию перечнем исключений ТОЙ ЖЕ версии ─────────────────
# Подставной пакет под git (два commit) и подставной каталог замеров: заглушка count-core.py печатает заданный счёт.
# Настоящий пакет, настоящий каталог замеров и настоящий перечень исключений не читаются.

PRINT_LINE = 'print("зови ZZQ")'
PRINT_ROW = ("scripts/a.py", "ZZQ", "shown", "printed", PRINT_LINE, "подставная печать стенда")
ALLOWED_REL = "vnext/tools/donor-literals-allowed.tsv"


def git_missing() -> str | None:
    """Почему случаи на подставном репозитории не выполнить (None — можно)."""
    if shutil.which("git") is None:
        return "git не найден — подставной репозиторий создать нечем: НЕ ПРОВЕРЕНО"
    return None


def allowed_tsv(rows=()) -> str:
    return "file\tname\tkind\tclass\ttext\treason\n" + "".join("\t".join(r) + "\n" for r in rows)


def count_rows(text: str) -> int:
    """Записей в тексте перечня: без пояснений «#» и строки заголовка."""
    return sum(1 for l in text.split("\n") if l.strip() and not l.startswith(("#", "file\t")))


@contextmanager
def without_git_env():
    """Проверка в этом процессе зовёт git со средой процесса: переменные GIT_* вызывающего увели бы её в чужой репозиторий."""
    saved = {k: os.environ.pop(k) for k in [k for k in os.environ if k.startswith("GIT_")]}
    try:
        yield
    finally:
        os.environ.update(saved)


class Stand(NamedTuple):
    root: Path
    tools: Path
    ids: list            # полные хэши commit по порядку: [0] — судимая версия, [1] — «позже»
    goal: Path


def recon_stand(ctx: Ctx, name: str, first_has_list: bool) -> Stand:
    """Подставной пакет под git: commit [0] — судимая версия (с перечнем исключений, который покрывает печатную строку,
    или без перечня), commit [1] — «позже»: перечень рабочего дерева пуст. Каталог замеров: версия = commit [0],
    счёт Э3 — одна строка «управляет поведением» (строка 1), печатная строка 2 вне счёта."""
    root = ctx.tmp / name
    tools = root / "vnext" / "tools"
    tools.mkdir(parents=True)
    for args in (("init", "-q"), ("config", "user.name", "приёмка"), ("config", "user.email", "bite@localhost.test"),
                 ("config", "core.autocrlf", "false"), ("config", "commit.gpgsign", "false")):
        git(root, *args)
    first = {"scripts/a.py": 'ROLE = "ZZQ"\n' + PRINT_LINE + "\n",
             "vnext/tools/core-files.txt": "# подставной перечень\n[ядро]\nscripts/a.py\n[вне ядра]\n",
             "vnext/tools/donor-names.json": names_json(FICTIONAL)}
    if first_has_list:
        first[ALLOWED_REL] = allowed_tsv([PRINT_ROW])
    ids = []
    for message, files in (("версия замера", first), ("позже: перечень пуст", {ALLOWED_REL: allowed_tsv()})):
        for rel, text in files.items():
            write(root / rel, text)
        git(root, "add", "-A")
        code, out = git(root, "commit", "-q", "--no-verify", "-m", message)
        if code != 0:
            raise AssertionError(f"стенд: commit «{message}» не создался: {out.strip()}")
        ids.append(head(root))
    goal = ctx.tmp / (name + "-goal")
    hits = [("scripts/a.py", 1, "role", "ZZQ", "code", "script", 'ROLE = "ZZQ"'),
            ("scripts/a.py", 2, "role", "ZZQ", "shown", "script", PRINT_LINE)]
    write(goal / "e2" / "hits.tsv", "file\tline\tgroup\tname\tkind\tfile_role\texcerpt\n"
          + "".join("\t".join(str(c) for c in r) + "\n" for r in hits))
    write(goal / "e2" / "metrics.json", json.dumps({"head": ids[0]}))
    count = ["СЧЁТ Э3 (цель 0): строк списка 1 · различных строк файлов 1 · файлов 1", "scripts/a.py:1 · ZZQ · довод стенда"]
    write(goal / "e3" / "count-core.py", "print(%r)\n" % "\n".join(count))
    return Stand(root, tools, ids, goal)


def recon_run(ctx: Ctx, st: Stand, commit: str, allowed_file=None) -> tuple[int, str]:
    lines = []
    with without_git_env():
        code = ctx.guard.reconcile(st.goal, st.root, st.tools, commit, out=lines.append, allowed_file=allowed_file)
    return code, "\n".join(lines)


def source_line(text: str) -> str:
    return next((l for l in text.split("\n") if l.startswith("перечень исключений:")), "")


def case15(ctx: Ctx):
    why = git_missing()
    if why:
        return None, why
    st = recon_stand(ctx, "c15", first_has_list=True)
    rc_c, blob = git(st.root, "show", f"{st.ids[0]}:{ALLOWED_REL}")
    commit_rows = count_rows(blob)
    tree_rows = count_rows((st.root / ALLOWED_REL).read_text(encoding="utf-8"))
    code, text = recon_run(ctx, st, st.ids[0])
    source = source_line(text)
    wired = rc_c == 0 and commit_rows == 1 and tree_rows == 0       # без этого случай ничего бы не различал
    ok = (wired and code == 0 and "(а) и (б) сходятся" in text
          and f"commit {st.ids[0]}" in source and "записей 1" in source)
    return ok, (f"стенд: записей в перечне судимого commit {commit_rows} (ждём 1), в рабочем дереве {tree_rows} (ждём 0 — иначе случай "
                f"не различал бы источники); сверка commit {st.ids[0][:7]}: код {code} (ждём 0), «(а) и (б) сходятся» "
                f"{'есть' if '(а) и (б) сходятся' in text else 'НЕТ'}; источник перечня: «{source}» "
                f"(ждём: commit <судимый>, записей 1)" + trail(ok, text, "сверки"))


def case16(ctx: Ctx):
    why = git_missing()
    if why:
        return None, why
    st = recon_stand(ctx, "c16", first_has_list=False)
    rc_c, _ = git(st.root, "show", f"{st.ids[0]}:{ALLOWED_REL}")
    wired = rc_c != 0 and (st.root / ALLOWED_REL).is_file()       # в commit перечня нет, в рабочем дереве есть
    code, text = recon_run(ctx, st, st.ids[0])
    words = ["НЕ ПРОВЕРЕНО", f"в commit {st.ids[0]} нет перечня исключений", "--reconcile-allowed"]
    missing = [w for w in words if w not in text]
    printed = [l for l in text.split("\n") if l.startswith(("(а)", "(б)", "перечень исключений:"))]
    ok = wired and code == 2 and not missing and "сходятся" not in text and not printed
    return ok, (f"стенд: перечня в судимом commit {'нет' if rc_c != 0 else 'ЕСТЬ'} (ждём нет), в рабочем дереве "
                f"{'есть' if (st.root / ALLOWED_REL).is_file() else 'НЕТ'} (ждём есть); сверка: код {code} (ждём 2); "
                f"нет слов: {missing or 'нет, всё названо'} (нужны: НЕ ПРОВЕРЕНО, commit, ключ); "
                f"результат сверки напечатан: {'ДА' if printed else 'нет'} (ждём нет)" + trail(ok, text, "сверки"))


def case17(ctx: Ctx):
    why = git_missing()
    if why:
        return None, why
    st = recon_stand(ctx, "c17", first_has_list=False)
    named = ctx.tmp / "перечень-версии.tsv"
    write(named, allowed_tsv([PRINT_ROW]))
    # (i) commit без перечня, перечень назван — сверка идёт по названному
    code1, t1 = recon_run(ctx, st, st.ids[0], named)
    s1 = source_line(t1)
    ok1 = code1 == 0 and "(а) и (б) сходятся" in t1 and "(назван при запуске)" in s1 and str(named) in s1
    # (ii) назван файл, которого нет — отказ словами
    code2, t2 = recon_run(ctx, st, st.ids[0], ctx.tmp / "нет-такого-перечня.tsv")
    ok2 = code2 == 2 and "НЕ ПРОВЕРЕНО" in t2 and "нет файла перечня исключений" in t2 and "сходятся" not in t2
    # (iii) у судимого commit свой перечень (пустой): названный берёт верх; без названного — находка, сверка расходится
    code3, t3 = recon_run(ctx, st, st.ids[1], named)
    code4, t4 = recon_run(ctx, st, st.ids[1])
    ok3 = code3 == 0 and code4 == 1
    ok = ok1 and ok2 and ok3
    return ok, (f"(i) commit без перечня, перечень назван: код {code1} (ждём 0), источник «{s1}»; "
                f"(ii) названного файла нет: код {code2} (ждём 2), слова «НЕ ПРОВЕРЕНО» и «нет файла перечня исключений» "
                f"{'есть' if ('НЕ ПРОВЕРЕНО' in t2 and 'нет файла перечня исключений' in t2) else 'НЕТ'}; "
                f"(iii) у commit пустой свой перечень: с названным код {code3} (ждём 0), без названного код {code4} (ждём 1 — "
                f"перечень имеет значение)" + trail(ok, t1 + "\n" + t2 + "\n" + t3 + "\n" + t4, "сверки"))


CASE_FUNCS = {1: case1, 2: case2, 3: case3, 4: case4, 5: case5, 6: case6, 7: case7, 8: case8, 9: case9, 10: case10,
              11: case11, 12: case12, 13: case13, 14: case14, 15: case15, 16: case16, 17: case17}


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


class HookBreak(NamedTuple):
    key: str
    title: str
    expect: tuple         # какие случаи ⑪–⑭ обязаны провалиться — РОВНО они (записано заранее); остальные целы
    patch: Callable | None  # patch(текст перехватчика) -> (новый текст, сколько раз нашлась цель); None — правка стенда
    enable: bool = True   # False — в стенде не выполнена команда `git config core.hooksPath .githooks`


def hook_breaks():
    """Нарочные поломки перехватчика. Правится ТЕКСТ его копии в подставном репозитории; настоящий файл не трогается."""
    return [
        HookBreak("hook-off", "перехватчик выключен — выход сразу", (11, 13, 14),
                  lambda s: replace_once(s, "root=$(git rev-parse --show-toplevel) || exit 1\n",
                                         "root=$(git rev-parse --show-toplevel) || exit 1\nexit 0\n")),
        HookBreak("guard-not-called", "перехватчик не зовёт проверку", (11, 13, 14),
                  lambda s: replace_once(s, 'out=$("$py" "$guard" 2>&1)\n', "out=$(true 2>&1)\n")),
        HookBreak("hooks-path-unset", "команда core.hooksPath не выполнена", (11, 13, 14), None, enable=False),
        HookBreak("hook-silent", "отказ без списка находок", (11,),
                  lambda s: replace_once(s, "    1)\n        printf '%s\\n' \"$out\" >&2\n", "    1)\n")),
        HookBreak("fail-open-no-guard", "нет файла проверки — commit пропускается", (14,),
                  lambda s: replace_once(s, 'if [ ! -f "$guard" ]; then\n', 'if [ ! -f "$guard" ]; then\n    exit 0\n')),
        HookBreak("fail-open-guard-error", "проверка не удалась — commit пропускается", (14,),
                  lambda s: replace_once(s, '        echo "   Посмотреть: python $guard" >&2\n        exit 1\n',
                                         '        echo "   Посмотреть: python $guard" >&2\n        exit 0\n')),
    ]


class ReconBreak(NamedTuple):
    key: str
    title: str
    expect: tuple         # какие случаи ⑮–⑰ обязаны провалиться — РОВНО они (записано заранее)
    patch: Callable       # patch(текст проверки) -> (новый текст, сколько раз нашлась цель)


def recon_breaks():
    """Нарочные поломки сверки. Правится ТЕКСТ проверки в памяти; на диск ничего не пишется."""
    return [
        ReconBreak("allowed-from-tree", "перечень читается из рабочего дерева", (15, 16),
                   lambda s: replace_once(s, "            allowed = allowed_of_commit(root, data_dir, commit)\n",
                                          "            allowed = load_allowed(Path(data_dir) / ALLOWED_FILE)\n")),
        ReconBreak("absent-list-as-empty", "в commit перечня нет — берётся тихий пустой перечень", (16,),
                   lambda s: replace_once(s, '    rc, out, _ = run_git(root, "show", "%s:%s" % (commit, rel))\n    if rc != 0:\n',
                                          '    rc, out, _ = run_git(root, "show", "%s:%s" % (commit, rel))\n    if rc != 0:\n'
                                          '        return []\n    if rc != 0:\n')),
        ReconBreak("named-list-ignored", "перечень, названный при запуске, не читается", (17,),
                   lambda s: replace_once(s, "        if allowed_file is not None:\n            allowed = load_allowed(allowed_file)\n",
                                          "        if False:\n            allowed = load_allowed(allowed_file)\n")),
        ReconBreak("named-missing-as-empty", "названного перечня нет — берётся пустой", (17,),
                   lambda s: replace_once(s, "            allowed = load_allowed(allowed_file)\n",
                                          "            allowed = load_allowed(allowed_file) if Path(allowed_file).is_file() else []\n")),
    ]


def run_case(number: int, scan, guard, goal, real_role, sync_patch=None, hook_patch=None, hook_enable=True):
    """Один случай в своём временном каталоге. -> (исход, подробности); неожиданная ошибка стенда — провал с текстом."""
    tmp = Path(tempfile.mkdtemp(prefix=f"bite-donor-literals-{number}-"))
    try:
        return CASE_FUNCS[number](Ctx(scan, guard, tmp, real_role, goal, sync_patch, hook_patch, hook_enable))
    except Exception as e:      # стенд сломался — это провал случая со словами, а не молчание
        return False, f"стенд случая упал: {type(e).__name__}: {e}"
    finally:
        remove_stand(tmp)


def remove_stand(path: Path) -> None:
    """Убрать каталог стенда. Файлы объектов git лежат только для чтения — на Windows защиту снимают."""
    def unprotect(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    kw = {"onexc": unprotect} if sys.version_info >= (3, 12) else {"onerror": unprotect}
    shutil.rmtree(path, **kw)


def run_clean(goal, real_role) -> bool:
    scan, guard = load_pair()
    ok_all = True
    for n in range(1, 18):
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


def run_hook_breaks(keys) -> bool:
    """Каждая поломка перехватчика: гоняются все случаи ⑪–⑭, провалиться обязаны РОВНО записанные заранее."""
    ok_all = True
    table = {b.key: b for b in hook_breaks()}
    marks = lambda ns: " ".join(CASE_MARKS[n] for n in sorted(ns)) or "ни одного"      # noqa: E731
    for key in keys:
        b = table[key]
        title = f"поломка перехватчика «{b.title}» роняет ровно {marks(b.expect)}"
        if b.patch is not None and HOOK_PATH.is_file():
            _, found = b.patch(HOOK_PATH.read_text(encoding="utf-8").replace("\r\n", "\n"))
            if found != 1:
                ok_all &= case(title, False, f"поломка не легла: цель найдена {found} раз(а), ждали один — "
                                             f"перехватчик изменился, поломку надо пересмотреть")
                continue
        failed, unchecked, notes = set(), set(), []
        for n in range(11, 15):
            verdict, detail = run_case(n, None, None, None, "", hook_patch=b.patch, hook_enable=b.enable)
            if verdict is None:
                unchecked.add(n)
            elif verdict is False:
                failed.add(n)
            notes.append(f"{CASE_MARKS[n]} {'НЕ ПРОВЕРЕН' if verdict is None else ('провалился' if verdict is False else 'прошёл')}")
        if unchecked:
            ok_all &= case(title, None, "не выполнены случаи " + marks(unchecked) + " — поломку не судить")
            continue
        exact = failed == set(b.expect)
        ok_all &= case(title, exact, f"провалились: {marks(failed)} (ждали ровно {marks(b.expect)}); " + " · ".join(notes))
    return ok_all


def run_recon_breaks(keys, real_role) -> bool:
    """Каждая поломка сверки: гоняются ①–⑧ и ⑮–⑰, провалиться обязаны РОВНО записанные заранее."""
    ok_all = True
    table = {b.key: b for b in recon_breaks()}
    marks = lambda ns: " ".join(CASE_MARKS[n] for n in sorted(ns)) or "ни одного"      # noqa: E731
    for key in keys:
        b = table[key]
        title = f"поломка сверки «{b.title}» роняет ровно {marks(b.expect)}"
        try:
            scan, guard = load_pair(None, b.patch)
        except AssertionError as e:
            ok_all &= case(title, False, str(e))
            continue
        failed, unchecked = set(), set()
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 17):
            verdict, _ = run_case(n, scan, guard, None, real_role)
            if verdict is None:
                unchecked.add(n)
            elif verdict is False:
                failed.add(n)
        if unchecked & set(b.expect):
            ok_all &= case(title, None, "не выполнены случаи " + marks(unchecked & set(b.expect)) + " — поломку не судить")
            continue
        exact = failed == set(b.expect)
        ok_all &= case(title, exact, f"провалились: {marks(failed)} (ждали ровно {marks(b.expect)}); "
                                     f"остальные из ①–⑧ и ⑮–⑰ прошли" + (f"; не проверены: {marks(unchecked)}" if unchecked else ""))
    return ok_all


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Приёмка проверки guard-donor-literals.py: случаи на подставном мини-пакете и нарочные поломки.",
        epilog="Исход: 0 — принято; 1 — не принято; 2 — приёмку выполнить не удалось или случай ⑨ (⑪–⑭, ⑮–⑰) не проверен.")
    ap.add_argument("--goal-dir", metavar="КАТАЛОГ",
                    help="каталог goal-gordi-core с замером Э2 и счётом Э3 — нужен случаю ⑨; без него ⑨ «НЕ ПРОВЕРЕН»")
    ap.add_argument("--cases", action="store_true", help="только случаи, без нарочных поломок")
    ap.add_argument("--break", dest="brk", metavar="ИМЯ",
                    help="одна нарочная поломка или all — все; без чистого прогона. Имена: " +
                         ", ".join(["code-unchecked", "print-unchecked", "comment-counted", "names-in-code", "exception-by-line",
                                    "no-role-literal-group", "file-list-unchecked", "exit2-as-0", "reconcile-skips-b", "sync-no-guard"]
                                   + [b.key for b in recon_breaks()] + [b.key for b in hook_breaks()]))
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
    hook_names = [b.key for b in hook_breaks()]
    recon_names = [b.key for b in recon_breaks()]
    if args.brk and args.brk != "all" and args.brk not in names + recon_names + hook_names:
        print(f"⛔ нет поломки «{args.brk}». Есть: {', '.join(names + recon_names + hook_names)}, all")
        return 2

    ok_all = True
    if args.brk == "all":
        ok_all &= run_breaks(names, goal, real_role)
        ok_all &= run_recon_breaks(recon_names, real_role)
        ok_all &= run_hook_breaks(hook_names)
    elif args.brk in recon_names:
        ok_all &= run_recon_breaks([args.brk], real_role)
    elif args.brk in hook_names:
        ok_all &= run_hook_breaks([args.brk])
    elif args.brk:
        ok_all &= run_breaks([args.brk], goal, real_role)
    else:
        ok_all &= run_clean(goal, real_role)
        if not args.cases:
            ok_all &= run_breaks(names, goal, real_role)
            ok_all &= run_recon_breaks(recon_names, real_role)
            ok_all &= run_hook_breaks(hook_names)
    print()
    if not ok_all:
        print(f"🔴 НЕ ПРИНЯТО — проверено {CASES}, прошло {PASSED}, не проверено {UNCHECKED}")
        return 1
    if UNCHECKED:
        print(f"⚪ ПРИНЯТО НЕ ПОЛНОСТЬЮ — проверено {CASES}, прошло {PASSED}, НЕ ПРОВЕРЕНО {UNCHECKED} (⑨ — нужен --goal-dir, git с нужным commit и перечень версии замера рядом с проверкой; ⑪–⑭ — нужен git и файл перехватчика; ⑮–⑰ — нужен git)")
        return 2
    print(f"✅ ПРИНЯТО — проверено {CASES}, прошло {PASSED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
