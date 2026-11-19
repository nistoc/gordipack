#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Приёмка карточки #761: файл путей у КОПИИ ПАКЕТА вне контура — один на оба каталога инструментов,
а отказ «контейнер группы НЕ НАЙДЕН» называет, что создать.

ПРЕДМЕТ. Приёмщик ветки берёт копию пакета в свою папку. У копии два каталога инструментов —
scripts/ и vnext/prototype/, — и каждый искал файл путей «рядом с собой»: <копия>/local/paths.json
и <копия>/vnext/local/paths.json. Файл клали в одно место; инструменты второго каталога отказывали
«НЕ НАЙДЕН», а приёмки читали отказ как провал ветки (карточка #761; замер COORD — записка #6646).
Сам отказ советовал первым «задай MEZO_CONTAINER» — в общем прогоне приёмок по копии эта переменная
снимается нарочно, и совет невыполним.

ЧТО СУДИМ — копия пакета в стенде (в обоих каталогах лежит только mezo_paths.py), контуры — рядом:
  ①  файла путей нет, MEZO_CONTAINER не задан, спрашивает scripts/: отказ называет файл
     <копия>/vnext/local/paths.json, ключ container с образцом содержимого, говорит, что общий прогон
     приёмок по копии MEZO_CONTAINER снимает и что файл один на оба каталога
  ①б то же, спрашивает vnext/prototype/: назван тот же файл и те же слова
  ②  файл ТОЛЬКО в <копия>/vnext/local/: контур находят оба каталога (container_root и mezo_root)
  ③  файл ТОЛЬКО в <копия>/local/: контур находят оба каталога
  ④  ВСТРЕЧНЫЙ: оба файла есть и называют РАЗНЫЕ контуры — каждый каталог берёт своё место (как прежде)
  ⑤  ВСТРЕЧНЫЙ: каталог, который копией пакета НЕ является (есть scripts/, нет vnext/prototype/), место
     vnext/local/ не читает — отказ; а своё место <каталог>/local/ читает, как прежде
  ⑥  ВСТРЕЧНЫЙ: MEZO_CONTAINER задан — берётся он, файл не нужен (как прежде)

ЧЕМ СУДИМ. Функции container_root() и mezo_root() из mezo_paths.py (по умолчанию — файл рядом с
приёмкой; --paths-module называет другой) зовутся отдельным процессом из копии в стенде. Живой
контур не читается и не нужен: контуры стенда — каталоги с непустым файлом-признаком.

НАРОЧНЫЕ ПОЛОМКИ (в копии испытуемого файла; каждая обязана уронить ровно названное):
  П1 место соседнего каталога не смотрится ........................ ② ③
  П2 в отказе советуется своё место, а не общее ................... ①
  П3 в отказе нет образца содержимого файла ....................... ① ①б
  П4 в отказе не сказано, что общий прогон снимает MEZO_CONTAINER . ① ①б
  П5 признак копии пакета — один каталог scripts/ ................. ⑤
  П6 своё место не первое ......................................... ④

ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ
  · сам общий прогон bite-all.py по копии: судится отказ, который он показал бы, а не его прогон;
  · остальные ключи файла путей и его чтение — их судит bite-local-paths.py;
  · равенство двух копий mezo_paths.py (scripts/ и vnext/prototype/): в стенд кладётся ОДИН файл в оба
    каталога — равенство копий судит проверка пар пакета.

Три исхода: код 0 — принята · код 1 — случай или поломка не сошлись · код 2 — опыт не поставлен.

Запуск:
  python bite-pack-copy-paths.py                         все случаи и все поломки
  python bite-pack-copy-paths.py --no-breaks             только случаи
  python bite-pack-copy-paths.py --paths-module ФАЙЛ     испытать другой mezo_paths.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — стенд во временной папке; уборка — по объявленному исходу

DB_MARK = b"marker of a contour for bite-pack-copy-paths\n"
SAMPLE = '{"container": "'
PROBE = '''import sys
sys.path.insert(0, sys.argv[1])
import mezo_paths
try:
    print("OK " + str(getattr(mezo_paths, sys.argv[2])(sys.argv[3])))
except SystemExit as e:
    print("EXIT " + str(e.code))
'''

# поломка → (что заменить в mezo_paths.py, чем, какие случаи обязаны упасть, что она значит)
BREAKS = {
    "П1": ("    if pack is not None:\n        for p in _pack_paths_files(pack):",
           "    if False:\n        for p in _pack_paths_files(pack):",
           {"②", "③"}, "место соседнего каталога не смотрится"),
    "П2": ("    if pack is not None and (res.file is None or res.outcome == LOCAL_NO_FILE):",
           "    if False:",
           {"①"}, "в отказе советуется своё место, а не общее"),
    "П3": ("""             '       {"container": "<каталог, ВНУТРИ которого лежит .mezosync/mezosync.db>"}\\n'\n""",
           "             ''\n",
           {"①", "①б"}, "в отказе нет образца содержимого файла"),
    "П4": ("""             "(bite-all.py) эту переменную снимает нарочно — там нужен именно файл.\\n"\n""",
           """             "\\n"\n""",
           {"①", "①б"}, "в отказе не сказано, что общий прогон снимает MEZO_CONTAINER"),
    "П5": ("""        if (root / "scripts").is_dir() and (root / "vnext" / "prototype").is_dir():""",
           """        if (root / "scripts").is_dir():""",
           {"⑤"}, "признак копии пакета — один каталог scripts/"),
    "П6": ("    found = [start.parent / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]]\n    # ①-бис",
           "    found = [start.parent / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]]\n"
           "    found = list(_pack_paths_files(_pack_copy_root(start))) if _pack_copy_root(start) else found\n"
           "    # ①-бис",
           {"④"}, "своё место не первое"),
}


class NotStarted(Exception):
    """Опыт не поставлен: исход — код 2, а не провал."""


def same_dir(a, b) -> bool:
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))
    except OSError:
        return False


class Stand:
    """Один набор случаев на одной редакции mezo_paths.py: своя копия пакета и свои контуры."""

    def __init__(self, root: Path, module_text: str):
        self.root = root
        self.pack = root / "pk"
        self.dirs = {"scripts": self.pack / "scripts", "prototype": self.pack / "vnext" / "prototype"}
        for d in self.dirs.values():
            d.mkdir(parents=True)
            (d / "mezo_paths.py").write_text(module_text, encoding="utf-8")
        self.cont = {}
        for name in ("contA", "contB"):
            c = root / name
            (c / ".mezosync").mkdir(parents=True)
            (c / ".mezosync" / "mezosync.db").write_bytes(DB_MARK)
            self.cont[name] = c.resolve()
        # ⑤: каталог, который копией пакета не является — scripts/ есть, vnext/prototype/ нет
        self.solo = root / "solo"
        (self.solo / "scripts").mkdir(parents=True)
        (self.solo / "scripts" / "mezo_paths.py").write_text(module_text, encoding="utf-8")
        self.probe = root / "probe.py"
        self.probe.write_text(PROBE, encoding="utf-8")
        self.shared = self.pack / "vnext" / "local" / "paths.json"   # общее место, его и советуем
        self.own = self.pack / "local" / "paths.json"                # своё место каталога scripts/

    def env(self, container=None) -> dict:
        e = dict(os.environ)
        for key in ("MEZO_CONTAINER", "MEZO_SCRIPTS_ROOT", "MEZO_LIVE_DB", "MEZO_TEMPLATE",
                    "MEZO_FORBID_LIVE", "CLAUDE_CODE_SESSION_ID"):
            e.pop(key, None)
        e["PYTHONDONTWRITEBYTECODE"] = "1"
        e["PYTHONIOENCODING"] = "utf-8"
        if container is not None:
            e["MEZO_CONTAINER"] = str(container)
        return e

    def ask(self, tool_dir: Path, func: str, container=None) -> str:
        """Ответ функции одной строкой: «OK <путь>» или «EXIT <текст отказа>»."""
        p = subprocess.run([sys.executable, "-X", "utf8", str(self.probe), str(tool_dir), func,
                            str(tool_dir / "x.py")], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self.env(container), cwd=str(self.root), timeout=60)
        return ((p.stdout or "") + (p.stderr or "")).strip()

    def put(self, where: Path, container: Path) -> None:
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(json.dumps({"container": container.as_posix()}), encoding="utf-8")

    def clear(self) -> None:
        for d in (self.pack / "vnext" / "local", self.pack / "local",
                  self.solo / "vnext" / "local", self.solo / "local"):
            shutil.rmtree(d, ignore_errors=True)

    def premise(self) -> None:
        """Посылка: над стендом нет чужого контура — иначе отказа ① не получить вовсе."""
        for cand in (self.pack, *self.pack.resolve().parents):
            if (cand / ".mezosync" / "mezosync.db").exists() or (cand / "mezosync.db").exists():
                raise NotStarted(f"стенд лежит внутри контура {cand} — признак найдётся раньше отказа; "
                                 "задай временную папку вне контуров")


def run_cases(st: Stand, say) -> set:
    """Все случаи на одном стенде → множество упавших."""
    failed = set()

    def verdict(mark, what, problems, shown=""):
        if problems:
            failed.add(mark)
        say(f"  {'✅' if not problems else '🔴'} {mark} {what}")
        if problems:
            say("       " + " · ".join(problems))
            for line in [l for l in shown.splitlines() if l.strip()][:8]:
                say(f"       │ {line[:150]}")

    scripts, proto = st.dirs["scripts"], st.dirs["prototype"]
    cont_a, cont_b = st.cont["contA"], st.cont["contB"]
    shared = st.shared.resolve().as_posix()

    # ① и ①б — отказ без файла и без переменной
    for mark, tool_dir, who in (("①", scripts, "scripts/"), ("①б", proto, "vnext/prototype/")):
        st.clear()
        out = st.ask(tool_dir, "container_root")
        problems = []
        if not out.startswith("EXIT") or "контейнер группы НЕ НАЙДЕН" not in out:
            problems.append("ждали отказ «контейнер группы НЕ НАЙДЕН»")
        if shared not in out.replace("\\", "/"):
            problems.append(f"не назван общий файл {shared}")
        if SAMPLE not in out:
            problems.append("нет образца содержимого с ключом container")
        if "bite-all.py" not in out or "снимает" not in out:
            problems.append("не сказано, что общий прогон приёмок по копии снимает MEZO_CONTAINER")
        if "Файл один на оба каталога" not in out:
            problems.append("не сказано, что файл один на оба каталога инструментов")
        verdict(mark, f"файла нет, MEZO_CONTAINER нет, спрашивает {who}: отказ называет общий файл, образец "
                "содержимого и снятую переменную", problems, out)

    # ② и ③ — один файл, оба каталога
    for mark, where, name in (("②", st.shared, "<копия>/vnext/local/"), ("③", st.own, "<копия>/local/")):
        st.clear()
        st.put(where, cont_a)
        problems, shown = [], []
        for tool_dir, who in ((scripts, "scripts/"), (proto, "vnext/prototype/")):
            got = st.ask(tool_dir, "container_root")
            shown.append(f"{who} container_root: {got}")
            if not got.startswith("OK ") or not same_dir(got[3:], cont_a):
                problems.append(f"{who}: container_root не нашёл контур по файлу в {name}")
            got = st.ask(tool_dir, "mezo_root")
            shown.append(f"{who} mezo_root: {got}")
            if not got.startswith("OK ") or not same_dir(got[3:], cont_a / ".mezosync"):
                problems.append(f"{who}: mezo_root не нашёл каталог базы по файлу в {name}")
        verdict(mark, f"файл только в {name}: контур находят оба каталога инструментов", problems,
                "\n".join(shown))

    # ④ — оба файла, разные контуры: каждый берёт своё место
    st.clear()
    st.put(st.shared, cont_a)
    st.put(st.own, cont_b)
    got_s, got_p = st.ask(scripts, "container_root"), st.ask(proto, "container_root")
    problems = []
    if not got_s.startswith("OK ") or not same_dir(got_s[3:], cont_b):
        problems.append("scripts/ взял не своё место (<копия>/local/)")
    if not got_p.startswith("OK ") or not same_dir(got_p[3:], cont_a):
        problems.append("vnext/prototype/ взял не своё место (<копия>/vnext/local/)")
    verdict("④", "оба файла есть и называют разные контуры: каждый каталог берёт своё место", problems,
            f"scripts/: {got_s}\nvnext/prototype/: {got_p}")

    # ⑤ — не копия пакета: место vnext/local/ не читается, своё — читается
    st.clear()
    solo = st.solo / "scripts"
    st.put(st.solo / "vnext" / "local" / "paths.json", cont_a)
    got_far = st.ask(solo, "container_root")
    st.clear()
    st.put(st.solo / "local" / "paths.json", cont_a)
    got_own = st.ask(solo, "container_root")
    problems = []
    if not got_far.startswith("EXIT") or "НЕ НАЙДЕН" not in got_far:
        problems.append("каталог без vnext/prototype/ прочёл файл из vnext/local/ — признак копии пакета не судится")
    if not got_own.startswith("OK ") or not same_dir(got_own[3:], cont_a):
        problems.append("своё место <каталог>/local/ не прочитано")
    verdict("⑤", "каталог без vnext/prototype/ место vnext/local/ не читает (отказ), своё место — читает",
            problems, f"vnext/local/: {got_far[:200]}\nlocal/: {got_own}")

    # ⑥ — переменная задана: берётся она
    st.clear()
    problems, shown = [], []
    for tool_dir, who in ((scripts, "scripts/"), (proto, "vnext/prototype/")):
        got = st.ask(tool_dir, "container_root", container=cont_b)
        shown.append(f"{who}: {got}")
        if not got.startswith("OK ") or not same_dir(got[3:], cont_b):
            problems.append(f"{who}: MEZO_CONTAINER задан, а контур взят не по нему")
    verdict("⑥", "MEZO_CONTAINER задан — берётся он, файла не нужно", problems, "\n".join(shown))
    st.clear()
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Приёмка карточки #761: файл путей у копии пакета вне контура")
    ap.add_argument("--paths-module", help="какой mezo_paths.py испытать (по умолчанию — рядом с приёмкой)")
    ap.add_argument("--no-breaks", action="store_true", help="только случаи, без нарочных поломок")
    a = ap.parse_args()

    module = Path(a.paths_module) if a.paths_module else Path(__file__).resolve().parent / "mezo_paths.py"
    if not module.is_file():
        print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: испытуемого файла нет — {module}")
        return 2
    text = module.read_text(encoding="utf-8")
    print("═" * 100)
    print(f"ПРИЁМКА карточки #761 · испытуется: {module}")
    print("═" * 100)

    work = mezo_stand.new("copypaths-")
    code = 0
    try:
        whole = Stand(Path(work) / "whole", text)
        try:
            whole.premise()
        except NotStarted as e:
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: {e}")
            return mezo_stand.finish(2)
        print("── случаи на целом коде")
        failed = run_cases(whole, print)
        total = 7
        print(f"   прошло {total - len(failed)} из {total}" + (f" · упали: {', '.join(sorted(failed))}" if failed else ""))
        if failed:
            code = 1
        caught = 0
        if not a.no_breaks:
            print("── нарочные поломки: каждая обязана уронить ровно названное")
            for name, (anchor, broken, want, meaning) in BREAKS.items():
                if text.count(anchor) != 1:
                    print(f"  ⛔ {name} НЕ ВСТАЛА: место поломки найдено {text.count(anchor)} раз, ждали ровно 1 — "
                          f"{meaning}")
                    print("     Это отказ ОПЫТА: без поставленной поломки прошедшие случаи ничего не доказывают.")
                    return mezo_stand.finish(2)
                st = Stand(Path(work) / f"brk-{list(BREAKS).index(name) + 1}", text.replace(anchor, broken))
                lines = []
                got = run_cases(st, lines.append)
                if got == want:
                    caught += 1
                    print(f"  ✅ {name} {meaning}: упали ровно {', '.join(sorted(want))}")
                else:
                    code = 1
                    print(f"  🔴 {name} {meaning}: ждали ровно {', '.join(sorted(want))}, упали "
                          f"{', '.join(sorted(got)) or 'ни одного'}")
                    for l in lines:
                        print("   " + l)
        print("─" * 100)
        tail = "" if a.no_breaks else f" · нарочных поломок {caught} из {len(BREAKS)} уронили ровно своё"
        print(("ИТОГ: ✅ ПРИНЯТА" if code == 0 else "ИТОГ: 🔴 НЕ ПРИНЯТА")
              + f" — случаев прошло {total - len(failed)} из {total}{tail}")
        return mezo_stand.finish(code)
    except BaseException:
        mezo_stand.finish(1)      # падение самой приёмки — каталоги стенда остаются для разбора
        raise


if __name__ == "__main__":
    sys.exit(main())
