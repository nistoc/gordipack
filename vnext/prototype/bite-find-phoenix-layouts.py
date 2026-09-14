#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-find-phoenix-layouts — приёмка карточки #632: find-phoenix.py находит своих
соседей (memory-archive.py, memory-records.py) в ОБЕИХ раскладках контура, не только
в нашей.

БЕДА (нашла COORD 2026-09-14 на контуре, собранном init-group из клона пакета). У НАШЕГО
контейнера соседи звеньев лежат в `<контейнер>/vnext-tools`; у контура, СОБРАННОГО init-group
из пакета, каталога vnext-tools нет вовсе — звенья (memory-archive.py, memory-records.py)
лежат РЯДОМ со скриптами (механизм §7б в init-group.py: список звеньев берётся замером
кода, а не пишется рукой). Жёсткий путь «CONTAINER_ROOT / vnext-tools / имя» ронял ЗАГРУЗКУ
МОДУЛЯ find-phoenix.py — FileNotFoundError на импорте, ДО main() — то есть падал трассировкой
на ЛЮБОМ запросе к этому инструменту в такой раскладке. Починка — приём save-phoenix.py::
vnext_tool() (донесён 13.09 для role-prompts.py/save-phoenix.py, сюда — карточкой #632):
четыре кандидата по очереди, не нашли ни одного — берём первый, дальнейший отказ (уже НЕ на
загрузке модуля, а в теле программы) называет ОЖИДАЕМОЕ место, а не роняет трассировку.

Случаи:
  ① раскладка Atlas (.mezosync/scripts + vnext-tools отдельно): find-phoenix.py грузится и
     отвечает БЕЗ трассировки — починка не ломает ШТАТНУЮ раскладку                РЕГРЕССИЯ
  ② раскладка пакета (звенья РЯДОМ со скриптами, vnext-tools нет вовсе): find-phoenix.py
     грузится и отвечает БЕЗ трассировки — это и есть критерий карточки #632         РАЗЛИЧАЮЩИЙ
  ③ НАРОЧНАЯ ПОЛОМКА «путь только в vnext-tools» (копия find-phoenix.py, где _vnext_tool
     всегда возвращает CONTAINER_ROOT/vnext-tools/имя — добёлочное поведение): на раскладке
     ПАКЕТА проваливает случай ② — трассировка FileNotFoundError на импорте            РАЗЛИЧАЮЩИЙ
  ④ ВСТРЕЧНЫЙ на поломку ③: ТА ЖЕ поломанная копия на раскладке ATLAS (там vnext-tools
     реально существует) отказа НЕ ловит — грузится и отвечает как обычно, доказывая,
     что поломка бьёт РОВНО по раскладке пакета, а не по всему сразу                РАЗЛИЧАЮЩИЙ
  ⑤ контроль «было на что смотреть»: словесный ответ случая ② — не пустая строка, несёт
     узнаваемый текст («⛔» + слово из текста отказа find-phoenix.py)

⚖️ ПОЧЕМУ ОБА СТЕНДА СО СХЕМОЙ-ПУСТЫШКОЙ, А НЕ СО СНИМКОМ ЖИВОЙ БАЗЫ: предмет этой приёмки —
ЗАГРУЗКА МОДУЛЯ (находит ли find-phoenix.py своих соседей на диске), а не содержимое памяти.
Пустая (но НАСТОЯЩАЯ, валидная) sqlite-база даёт мезосинку признак существования файла для
container_root()/mezo_root() и сама по себе НЕ несёт машинных данных — приёмка остаётся
самодостаточной и способной запуститься из vnext/prototype пакета так же, как из vnext-tools
контейнера (ни одного вписанного пути машины в исполняемых строках, только в докстринге).
Пустая база к тому же ДЕТЕРМИНИРОВАННО не несёт таблицы phoenix_records_fts — сама by that
даёт «словами, без трассировки» уже ПОСЛЕ успешной загрузки модуля, тем же прогоном.

⛔ Живого контура НЕ касается: оба стенда — временные каталоги с копиями инструментов и
пустой sqlite-базой (mezo_stand.new), испытуемые файлы копируются mezo_stand.copy_tool
(обычные import-соседи) и вручную (read-phoenix.py/memory-archive.py/memory-records.py —
find-phoenix.py грузит их importlib'ом по вычисленному пути, copy_tool такие связи не видит).
Поломка ③ делается на КОПИИ КОПИИ (copy_tool в отдельный каталог), не в испытуемом файле.

    python <КОНТУР>/vnext-tools/bite-find-phoenix-layouts.py
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — своя копия (own-каталог), как у bite-archive-move-records.py

SCRIPTS = mezo_paths.live_scripts()
FIND = SCRIPTS / "find-phoenix.py"
READ = SCRIPTS / "read-phoenix.py"
ARCHIVE = pathlib.Path(__file__).resolve().parent / "memory-archive.py"
RECORDS = pathlib.Path(__file__).resolve().parent / "memory-records.py"

for _tool in (FIND, READ, ARCHIVE, RECORDS):
    if not _tool.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {_tool}")

sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402 — стенд из S (.mezosync/scripts), как велит карточка

OK = FAIL = 0


def case(title, ok, detail=""):
    global OK, FAIL
    print(("✅" if ok else "🔴"), title)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if ok else 0), FAIL + (0 if ok else 1)
    return ok


def empty_db(path: pathlib.Path) -> None:
    """Настоящая, но ПУСТАЯ sqlite-база — только признак существования файла для
    container_root()/mezo_root(); схему сознательно не несёт (см. докстринг модуля)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(path)).close()


def build_stand(label: str, layout: str) -> pathlib.Path:
    """layout: 'atlas' — .mezosync/scripts + vnext-tools РЯДОМ с контейнером (наша раскладка);
               'pack'  — .mezosync/scripts, звенья ЛЕЖАТ В НЁМ ЖЕ (раскладка контура из пакета,
               vnext-tools не заводится вовсе — тем же приёмом, каким init-group.py §7б кладёт
               звенья РЯДОМ со скриптами)."""
    stand = mezo_stand.new(f"bite-find-phoenix-layouts-{label}-")
    scripts_dir = stand / ".mezosync" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    empty_db(stand / ".mezosync" / "mezosync.db")

    # find-phoenix.py + его ОБЫЧНЫЕ import-соседи (mezo_paths, mezo_hints) — copy_tool видит
    # только `import X`/`from X import Y`, не importlib.
    mezo_stand.copy_tool(FIND, scripts_dir)
    # read-phoenix.py find-phoenix.py грузит importlib'ом (HERE / "read-phoenix.py") —
    # copy_tool такую связь не находит, кладём рукой.
    shutil.copy2(READ, scripts_dir / "read-phoenix.py")

    companions_dir = (stand / "vnext-tools") if layout == "atlas" else scripts_dir
    companions_dir.mkdir(parents=True, exist_ok=True)
    # memory-archive.py и memory-records.py — тоже importlib-соседи find-phoenix.py,
    # copy_tool на них зовём ОТДЕЛЬНО (это и приносит их обычных соседей вроде mezo_paths
    # в companions_dir, когда он не совпадает со scripts_dir).
    mezo_stand.copy_tool(ARCHIVE, companions_dir)
    mezo_stand.copy_tool(RECORDS, companions_dir)
    return stand


def run_find(stand: pathlib.Path, finder: pathlib.Path, query="жаборазметчик632") -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(finder), "--role", "BITE632", query],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=mezo_stand.stand_env(stand), timeout=30)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def make_broken_finder(src_scripts_dir: pathlib.Path) -> pathlib.Path:
    """Нарочная поломка «путь только в vnext-tools» — НА КОПИИ КОПИИ найденного find-phoenix.py
    (copy_tool в отдельный каталог), а не в испытуемом файле. _vnext_tool() заменяется на
    добёлочное поведение: всегда CONTAINER_ROOT/vnext-tools/имя, без остальных кандидатов."""
    broken_dir = mezo_stand.new("bite-find-phoenix-layouts-broken-")
    broken_tool = mezo_stand.copy_tool(FIND, broken_dir)
    # read-phoenix.py — тоже importlib-сосед (HERE / "read-phoenix.py"), copy_tool его не
    # видит; без него модуль падал бы НА ЭТОЙ строке ВСЕГДА, в обеих раскладках, и поломка
    # ③ проверяла бы не то, что задумано (случай ④ не различал бы «раскладка пакета» —
    # найдено прогоном сразу после первой редакции).
    shutil.copy2(READ, broken_dir / "read-phoenix.py")
    original = broken_tool.read_text(encoding="utf-8")
    ANCHOR = (
        "def _vnext_tool(name):\n"
        '    """Путь к звену-помощнику в ОБЕИХ раскладках — приём save-phoenix.py::vnext_tool()."""\n'
        "    candidates = [CONTAINER_ROOT / \"vnext-tools\" / name,               # наш контейнер (зона PROTO)\n"
        "                  HERE / name,                                          # собранный контур: звенья рядом\n"
        "                  HERE.parent / \"vnext\" / \"prototype\" / name,           # шаблон: scripts/ и vnext/ — соседи\n"
        "                  CONTAINER_ROOT / \"vnext\" / \"prototype\" / name]\n"
        "    return next((c for c in candidates if c.exists()), candidates[0])\n"
    )
    if ANCHOR not in original:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: якорь _vnext_tool() не найден в испытуемом find-phoenix.py — "
                 "переименовали, поломка ③ бьёт мимо (ожидаемо на версии ДО починки карточки #632: "
                 "предмета — самой функции — там ещё нет)")
    broken = original.replace(
        ANCHOR,
        "def _vnext_tool(name):\n"
        "    # ПОРЧА bite-find-phoenix-layouts (③): путь ТОЛЬКО в vnext-tools, добёлочное поведение\n"
        "    return CONTAINER_ROOT / \"vnext-tools\" / name\n")
    broken_tool.write_text(broken, encoding="utf-8")
    # соседей (mezo_paths/mezo_hints) copy_tool уже положил рядом с broken_tool — достаточно
    # для того, чтобы модуль дошёл до строки, которую мы портим, а не упал раньше по другой причине.
    return broken_tool


# ═══════════════════════════════════════════════════════════════════════════════
stand_atlas = build_stand("atlas", "atlas")
stand_pack = build_stand("pack", "pack")

# ── ① раскладка Atlas — регрессия ────────────────────────────────────────────
rc1, out1 = run_find(stand_atlas, stand_atlas / ".mezosync" / "scripts" / "find-phoenix.py")
case("① раскладка Atlas: find-phoenix.py грузится и отвечает БЕЗ трассировки",
     "Traceback" not in out1,
     f"код {rc1}:\n{out1}")

# ── ② раскладка пакета — критерий карточки #632 ──────────────────────────────
rc2, out2 = run_find(stand_pack, stand_pack / ".mezosync" / "scripts" / "find-phoenix.py")
case("② раскладка пакета (звенья рядом со скриптами, vnext-tools нет): find-phoenix.py "
     "грузится и отвечает БЕЗ трассировки",
     "Traceback" not in out2 and rc2 != 1,
     f"код {rc2}:\n{out2}")

# ── ⑤ контроль «было на что смотреть» ────────────────────────────────────────
case("⑤ контроль: ответ случая ② — словами, не пустая строка (несёт «⛔»)",
     bool(out2.strip()) and "⛔" in out2,
     f"длина ответа {len(out2)} знаков")

# ── ③ нарочная поломка проваливает РОВНО раскладку пакета ────────────────────
broken_finder = make_broken_finder(SCRIPTS)
rc3, out3 = run_find(stand_pack, broken_finder)
case("③ ПОЛОМКА «путь только в vnext-tools» на раскладке ПАКЕТА: трассировка "
     "FileNotFoundError на загрузке модуля (случай ② без починки выглядел бы так же)",
     "Traceback" in out3 and "FileNotFoundError" in out3,
     f"код {rc3}:\n{out3}")

# ── ④ встречный: та же поломка НЕ бьёт по раскладке Atlas ────────────────────
rc4, out4 = run_find(stand_atlas, broken_finder)
case("④ ВСТРЕЧНЫЙ: ТА ЖЕ поломка на раскладке ATLAS отказа не ловит (vnext-tools там есть) "
     "— поломка ③ различает РОВНО раскладку пакета, не всё подряд",
     "Traceback" not in out4,
     f"код {rc4}:\n{out4}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
