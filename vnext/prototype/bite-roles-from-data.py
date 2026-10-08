#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: имена ролей берутся из данных контура, а не из текста инструментов
(набор TRACK-GORDI-CORE, этап Э3, работа Р2; карточка #677).

ПРЕДМЕТ. Первая часть (случаи ①–⑨): в пяти инструментах контура имя роли было впечатано
литералом — у контура-соседа такой роли может не быть, а инструмент молча читал чужую память,
судил по чужому имени навыка или писал замер от чужого лица. Вторая часть (случаи ⑩–⑲, этап Э3
работа Р2, решение владельца 2026-10-05 10:53 UTC, чат COORD): то же в девяти инструментах
механизма со-работы — табло, сборка контура, перенос записок, писатели правил и реестра,
печатные подсказки, перечень снятого. Роль берётся из вызова (флаг, затем переменная среды
MEZO_ROLE), затем — из данных (координатор контура, таблица roles), а где ни там ни там имени
нет — инструмент отказывает словами либо говорит «не проверено» / печатает заполнитель.
Приёмка доказывает, что в КАЖДОМ месте подстановка литерала различима.

Каждый случай строит СВОЙ стенд: контур с ролями ZZX, QQR и координатором COORD-A (ни одно из
этих имён не совпадает с прежними литералами PROTO/COORD, иначе возврат литерала не краснел бы).
Живая база и живые записи разговоров не читаются; инструменты запускаются КОПИЯМИ на стенде
со средой стенда (MEZO_CONTAINER = стенд, MEZO_ROLE снята). Чтение памяти и поиск по ней
подменены заготовками, которые лишь записывают, с какой ролью их позвали. Базы второй части
строятся из СХЕМЫ ПАКЕТА (schema/mezosync_v*.sql образца), а не снимаются с живой: данные —
подставные, схема — настоящая. Файл базы стенда НИКОГДА не лежит там, где set-rule.py считает
базу «живой»: иначе правка правила пересобрала бы настоящее зеркало правил подставными данными.

СЛУЧАИ (все различающие: ответ обязан быть ИНЫМ, а не одинаковым, если литерал вернуть):
  ①  init-group-vnext.py: без --roles — отказ словами с примером, база не создана;
      с --roles zzx qqr — роли ZZX и QQR, а не COORD
  ②  guard-printed-forms.py, observe(): роль не передана — read-phoenix НЕ запускается
  ③  guard-printed-forms.py, run(): роль не передана — печатается «не проверено: роль не названа»,
      read-phoenix НЕ запускается
  ④  guard-printed-forms.py, флаг --role: нет флага и MEZO_ROLE — роль берётся из данных
      (координатор COORD-A); MEZO_ROLE=zzx — ZZX; флаг побеждает среду; координатора нет — «не проверено»
  ⑤  guard-printed-forms.py, имя навыка ответов владельцу: «<имя контура из meta>-owner-reply»;
      имя чужого контура наказ не спасает; имя не читается — судим только по ключу правила
  ⑥  measure-memory-search.py: нет ни --actor, ни MEZO_ROLE — отказ словами, поиск не запускался
  ⑦  measure-tool-brevity.py: то же для --role; название роли попадает в набор вызовов и в тело пробы
  ⑧  measure-rhythm.py: имена ролей — из таблицы roles (в том числе закрытая роль); база не
      читается — образец с печатью строки об этом
  ⑨  контроль: приёмке было на что смотреть (стенд непуст, имена стенда не совпадают с литералами)
  ⑩  dashboard.py: карточки — из таблицы roles (живые, не снятые с реестра), координатор первым,
      затем по имени, подпись — короткая зона; координатора нет — по имени; живых ролей нет — слово
  ⑪  init-group.py: без --roles и с голым --roles — отказ словами с примером, база не создана;
      с --roles zzx qqr — координатор первая из них (строка об этом), заготовки по роли;
      --coordinator qqr — другая; --coordinator вне --roles — отказ; раскладка Atlas (coord core) — как прежде
  ⑫  messages-fold.py: --apply без руки (ни флага, ни MEZO_ROLE) — отказ, записки на месте; холостой
      прогон — «рука не названа»; MEZO_ROLE=zzx — в архиве ZZX; флаг побеждает среду
  ⑬  set-rule.py: запись — флаг → MEZO_ROLE → координатор из данных (строка «пишет: …») → отказ;
      снятие тем же порядком; чтение и холостой прогон руки не ищут; раскладка Atlas пишет как COORD
  ⑭  set-registry.py: то же для track/invariant; «кто установил» инварианта — рука, а не «coord»
  ⑮  backlog.py, подсказка про закрытие issue: «--role <координатор из данных>», а нет его — «<координатор>»
  ⑯  gordi-issue.py poll: подсказка «завести» несёт роль ЭТОГО вызова, а не PROTO
  ⑰  save-phoenix.py --help: пример «--actor <РОЛЬ>», а не «--actor PROTO»
  ⑱  check-retired-mechanism.py: чужие имена (de-live · db_falcon · DE/DWH) не гасят находку;
      общее «только чтение» гасит по-прежнему
  ⑲  контроль второй части: схема пакета найдена, инструменты найдены, имена стенда не совпадают
      с литералами, у случаев было что считать

НАРОЧНЫЕ ПОЛОМКИ (--break <имя>): на КОПИИ инструмента в стенде возвращается прежний литерал;
ждём провала РОВНО названного случая (список записан ниже ДО прогона, в BREAK_FAILS).
  init-roles ......... ① (--roles снова по умолчанию COORD)
  guard-observe ...... ② (observe снова по умолчанию читает память PROTO)
  guard-run .......... ③ (run снова по умолчанию читает память PROTO)
  guard-role-flag .... ④ (--role снова по умолчанию PROTO)
  guard-skill-name ... ⑤ (имя навыка снова atlas-owner-reply)
  memory-actor ....... ⑥ (замер без роли снова идёт от имени PROTO)
  brevity-role ....... ⑦ (замер без роли снова идёт от имени PROTO; тело пробы с именем PROTO)
  rhythm-names ....... ⑧ (имена ролей снова впечатаны списком)
  dashboard-roles-literal ... ⑩ (карточки снова по списку из шести имён)
  init-group-roles-default .. ⑪ (--roles снова по умолчанию coord)
  init-group-coordinator-literal ... ⑪ (координатор снова всегда COORD)
  fold-hand-literal ......... ⑫ (рука переноса снова по умолчанию PROTO)
  rule-actor-literal ........ ⑬ (--actor у set-rule снова по умолчанию COORD)
  registry-actor-literal .... ⑭ (--actor у set-registry снова по умолчанию COORD)
  backlog-hint-literal ...... ⑮ (подсказка снова называет COORD)
  gordi-hint-literal ........ ⑯ (подсказка снова называет PROTO)
  phoenix-help-literal ...... ⑰ (справка снова называет PROTO)
  retired-pattern-restored .. ⑱ (в образец возвращены три чужих имени)
  --break all ........ все подряд, итог «поломок N, ожидание подтвердилось N»

Зовут так:
    python <КОНТУР>/vnext-tools/bite-roles-from-data.py
    python <КОНТУР>/vnext-tools/bite-roles-from-data.py --break guard-observe
    python <КОНТУР>/vnext-tools/bite-roles-from-data.py --break all
    python <КОНТУР>/vnext-tools/bite-roles-from-data.py --tools-dir <каталог с инструментами vnext-tools>
    python <КОНТУР>/vnext-tools/bite-roles-from-data.py --scripts-dir <каталог с инструментами механизма>
      (по умолчанию — испытуемый каталог mezo_target: MEZO_SCRIPTS_ROOT либо живой .mezosync/scripts)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402 — где лежит образец пакета (схема для баз второй части)
import mezo_stand  # noqa: E402 — стенд убирается при успехе, сохраняется при провале
import mezo_target  # noqa: E402 — какой каталог механизма испытываем (живой или копия)

TOOLS = {
    "init": "init-group-vnext.py",
    "guard": "guard-printed-forms.py",
    "memory": "measure-memory-search.py",
    "brevity": "measure-tool-brevity.py",
    "rhythm": "measure-rhythm.py",
}

# Вторая часть (этап Э3, работа Р2): инструменты механизма со-работы, которые испытываются
# КОПИЯМИ из каталога механизма (--scripts-dir либо mezo_target), а не из vnext-tools.
SUT = {
    "dash": "dashboard.py",
    "initg": "init-group.py",
    "fold": "messages-fold.py",
    "rule": "set-rule.py",
    "registry": "set-registry.py",
    "backlog": "backlog.py",
    "gissue": "gordi-issue.py",
    "phoenix": "save-phoenix.py",
    "retired": "check-retired-mechanism.py",
}

# Роли стенда. Ни одно имя не совпадает с прежними литералами (PROTO, COORD, список токенов).
COORD_NAME = "COORD-A"      # координатор контура стенда — только из данных (lifecycle_reason)
ROLE_ENV = "zzx"            # имя из переменной среды, регистр нарочно нижний
ROLE_FLAG = "qqr"           # имя из флага, регистр нарочно нижний
OLD_LITERALS = ("PROTO", "COORD", "CORE", "ING", "STUD", "TAXO", "OPSSRE", "RCC", "CHROME")
GROUP = "zzx"               # имя контура стенда (meta.group_name)
ARCHIVE_STEP = "20260905-messages-archive"   # шаг, заводящий архив ленты (случай ⑫)

# Нарочные поломки: имя → (номер случая, [(ключ инструмента, якорь, замена)], что ломаем).
# Якорь обязан найтись в копии РОВНО ОДИН раз — иначе поломка «не легла» и прогон не засчитывается.
BREAKS = {
    "init-roles": ("①", [("init",
                          'ap.add_argument("--roles", nargs="*", default=None,',
                          'ap.add_argument("--roles", nargs="*", default=["COORD"],')],
                   "--roles снова по умолчанию COORD"),
    "guard-observe": ("②", [("guard",
                             "def observe(scripts, role=None, timeout=25):",
                             'def observe(scripts, role="PROTO", timeout=25):')],
                      "observe() снова по умолчанию читает память PROTO"),
    "guard-run": ("③", [("guard",
                         'def run(scripts, artifacts, quiet=False, do_run=True, role=None, role_note=""):',
                         'def run(scripts, artifacts, quiet=False, do_run=True, role="PROTO", role_note=""):')],
                  "run() снова по умолчанию читает память PROTO"),
    "guard-role-flag": ("④", [("guard",
                               '    ap.add_argument("--role", default=None,',
                               '    ap.add_argument("--role", default="PROTO",')],
                        "--role снова по умолчанию PROTO"),
    "guard-skill-name": ("⑤", [("guard",
                                '"owner-reply-format" not in _tb and not (skill_name and skill_name in _tb):',
                                '"owner-reply-format" not in _tb and "atlas-owner-reply" not in _tb:')],
                         "имя навыка снова atlas-owner-reply"),
    "memory-actor": ("⑥", [("memory",
                            "return actor or None",
                            'return actor or "PROTO"')],
                     "замер без роли снова идёт от имени PROTO"),
    "brevity-role": ("⑦", [("brevity",
                            "return role or None",
                            'return role or "PROTO"'),
                           ("brevity",
                            "(measure-tool-brevity.py, роль {role}).",
                            "(measure-tool-brevity.py, роль PROTO).")],
                     "замер без роли снова идёт от имени PROTO, тело пробы с именем PROTO"),
    "rhythm-names": ("⑧", [("rhythm",
                            "if t in names:",
                            'if t in ("COORD", "CORE", "ING", "STUD", "TAXO", "OPSSRE", "PROTO", "RCC", "CHROME"):')],
                     "имена ролей снова впечатаны списком"),
    # ── вторая часть: якоря — в КОПИЯХ из каталога механизма (ключи — из SUT)
    "dashboard-roles-literal": ("⑩", [("dash",
                                       "    for role, title in roles_from_data(con):",
                                       '    for role, title in [("COORD", "координатор"), ("CORE", "ядро"), '
                                       '("ING", "ингест"), ("STUD", "портал"), ("TAXO", "таксономия"), '
                                       '("RCC", "мост DWH")]:')],
                                "карточки табло снова по впечатанному списку из шести имён"),
    "init-group-roles-default": ("⑪", [("initg",
                                        'parser.add_argument("--roles", nargs="*", default=None,',
                                        'parser.add_argument("--roles", nargs="*", default=["coord"],')],
                                 "--roles у сборки контура снова по умолчанию coord"),
    "init-group-coordinator-literal": ("⑪", [("initg",
                                              "coordinator = roles[0]",
                                              'coordinator = "COORD"')],
                                       "координатор нового контура снова всегда COORD"),
    "fold-hand-literal": ("⑫", [("fold",
                                 'hand = (a.role or os.environ.get("MEZO_ROLE") or "").strip().upper() or None',
                                 'hand = (a.role or os.environ.get("MEZO_ROLE") or "PROTO").strip().upper() or None')],
                          "рука переноса записок снова по умолчанию PROTO"),
    "rule-actor-literal": ("⑬", [("rule",
                                  '    ap.add_argument("--actor", default=None,',
                                  '    ap.add_argument("--actor", default="COORD",')],
                           "--actor у set-rule снова по умолчанию COORD"),
    "registry-actor-literal": ("⑭", [("registry",
                                      '        p.add_argument("--actor", default=None,',
                                      '        p.add_argument("--actor", default="COORD",')],
                               "--actor у set-registry снова по умолчанию COORD"),
    "backlog-hint-literal": ("⑮", [("backlog",
                                    'closer = find_coordinator(conn).name or "<координатор>"',
                                    'closer = "COORD"')],
                             "подсказка про закрытие issue снова называет COORD"),
    "gordi-hint-literal": ("⑯", [("gissue",
                                  'f"add --role {_card_owner(a, conn)} --title ',
                                  'f"add --role PROTO --title ')],
                           "подсказка «завести» в опросе снова называет PROTO"),
    "phoenix-help-literal": ("⑰", [("phoenix",
                                    "напр. --actor <РОЛЬ> при",
                                    "напр. --actor PROTO при")],
                             "справка save-phoenix снова называет --actor PROTO"),
    "retired-pattern-restored": ("⑱", [("retired",
                                        'r"|только\\s+чтение"),',
                                        'r"|de-live|db_falcon|DE/DWH|только\\s+чтение"),')],
                                 "в образец перечня снятого возвращены три чужих имени"),
}
# 📋 СПИСОК ПРОВАЛОВ КАЖДОЙ ПОЛОМКИ — записан ДО прогона. Прогон с --break сверяет с ним.
BREAK_FAILS = {name: [spec[0]] for name, spec in BREAKS.items()}

CASES = DIFFER = 0
FAILED: list[str] = []
EVIDENCE: dict[str, int] = {}

# ── заготовки инструментов контура на стенде ──────────────────────────────────
# Пишут в журнал рядом, с какой ролью их позвали; сами ничего не читают из базы.
# 🪤 Флаги заготовки повторяют форму вызова ИСПЫТУЕМОГО: с c4221fa (карточка #685, находка AIA ④-2)
# guard-printed-forms.py зовёт read-phoenix.py с --full. Заготовка без этого флага выходила кодом 2
# ошибкой разбора, в журнал ничего не писала — и случаи ②③④ проваливались на исправном инструменте.
READ_STUB = '''# -*- coding: utf-8 -*-
import argparse
import pathlib

ap = argparse.ArgumentParser()
ap.add_argument("--role")
ap.add_argument("--db")
ap.add_argument("--full", action="store_true")
a = ap.parse_args()
with pathlib.Path(__file__).with_name("read-phoenix.calls.log").open("a", encoding="utf-8") as fh:
    fh.write("--role " + str(a.role))
    fh.write(chr(10))
print("память роли " + str(a.role) + ": заготовка стенда")
'''

FIND_STUB = '''# -*- coding: utf-8 -*-
import argparse
import pathlib
import sys

ap = argparse.ArgumentParser()
ap.add_argument("query", nargs="?")
ap.add_argument("--role")
ap.add_argument("--section")
ap.add_argument("--db")
ap.add_argument("--actor")
a = ap.parse_args()
with pathlib.Path(__file__).with_name("find-phoenix.calls.log").open("a", encoding="utf-8") as fh:
    fh.write("--actor " + str(a.actor) + " --role " + str(a.role))
    fh.write(chr(10))
print("ОТВЕТ: 0 записей · 12 знаков · 0.01 с")
sys.exit(2)
'''

# Вызов функций охраняющего инструмента напрямую: подгружается КОПИЯ со стенда.
GUARD_DRIVER = '''# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve().parent))   # соседи копии лежат рядом
spec = importlib.util.spec_from_file_location("gpf_roles_stand", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
scripts = pathlib.Path(sys.argv[2])
what = sys.argv[3]
role = sys.argv[4] if len(sys.argv) > 4 else None
if what == "observe":
    hits, n, skipped = mod.observe(scripts, role) if role else mod.observe(scripts)
    print("ИТОГ-ДРАЙВЕРА команд " + str(n))
else:
    nothing = scripts / "нет-такого-каталога"
    rc = mod.run(scripts, nothing, quiet=True, do_run=True, **({"role": role} if role else {}))
    print("ИТОГ-ДРАЙВЕРА код " + str(rc))
'''

BREVITY_DRIVER = '''# -*- coding: utf-8 -*-
import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve().parent))   # соседи копии лежат рядом
spec = importlib.util.spec_from_file_location("brevity_roles_stand", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.save_body_text(sys.argv[2]))
'''


# Заготовки для переноса записок (messages-fold.py ищет их рядом с собой и судит по тексту):
# читателю номера важно лишь знать слово «messages_all» (показ) и «mezo_refs» (разрешение номера).
FOLD_READ_STUB = "# заготовка стенда: показ идёт через вид messages_all\n"
FOLD_WRITE_STUB = "# заготовка стенда: номера разрешает mezo_refs\n"

# Подпись зоны длиннее предела табло (60 знаков) и без точки внутри: её обязаны обрезать с «…».
ZONE_LONG = "Длинное описание зоны стенда без точки внутри " * 2
ZONE_LABEL_LIMIT = 60


class NotRun(Exception):
    """Приёмка не смогла начаться (нет инструмента, схемы, поломка не легла): это отказ мерить, не провал."""


class Stand:
    """Каталоги стенда."""

    def __init__(self, root: Path):
        self.root = root
        self.tools = root / "vnext-tools"
        self.meza = root / ".mezosync"
        self.scripts = self.meza / "scripts"
        self.db = self.meza / "mezosync.db"
        self.nocoord_db = root / "nocoord.db"
        self.rhythm_db = root / "rhythm.db"
        self.chats = root / "chats"
        self.tasks = root / "tasks"
        self.canon = root / "CLAUDE.md"
        # вторая часть (Э3, Р2): копии инструментов механизма, образец пакета, базы из схемы пакета
        self.sut = root / "sut"
        self.pack = root / "pack"
        self.dbs = root / "dbs"             # ⛔ не там, где set-rule.py ищет «живую» базу
        self.contours = root / "contours"
        self.paths: dict[str, Path] = {}
        self.schema_text = ""
        self.schema_name = ""


def case(label: str, subs: list[tuple[str, bool, str]], differ: bool = True) -> bool:
    """Печатает случай. Различающий — построен так, что возврат литерала даёт ИНОЙ ответ."""
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    ok = bool(subs) and all(s[1] for s in subs)
    print(f"{'✅' if ok else '🔴'} {label}")
    for name, sub_ok, detail in subs:
        print(f"   {'·' if sub_ok else '✗'} {name}: {detail}")
    if not ok:
        FAILED.append(label.split()[0])
    return ok


def safe_case(label: str, body, differ: bool = True) -> bool:
    """Случай, упавший исключением, — провал ЭТОГО случая, а не всей приёмки."""
    try:
        return case(label, body(), differ)
    except Exception as e:  # noqa: BLE001 — причина печатается, соседние случаи идут дальше
        return case(label, [("исключение в самой приёмке", False, f"{type(e).__name__}: {e}")], differ)


def call(stand: Stand, args: list[str], extra: dict | None = None, timeout: int = 180) -> tuple[int, str]:
    """Один запуск инструмента со СРЕДОЙ СТЕНДА; переменная MEZO_ROLE снята, если не задана явно."""
    env = mezo_stand.stand_env(stand.root, PYTHONIOENCODING="utf-8")
    env.pop("MEZO_ROLE", None)
    if extra:
        env.update(extra)
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def read_log(stand: Stand, name: str) -> list[str]:
    p = stand.scripts / name
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def clear_logs(stand: Stand) -> None:
    for name in ("read-phoenix.calls.log", "find-phoenix.calls.log"):
        p = stand.scripts / name
        if p.exists():
            p.unlink()


def roles_of(lines: list[str]) -> list[str]:
    return [ln.split()[1] for ln in lines if ln.startswith("--role ")]


def make_roles_db(path: Path, roles: list[tuple[str, str, str | None]], group: str | None,
                  with_records: bool = False) -> None:
    con = sqlite3.connect(str(path))
    con.executescript(
        "CREATE TABLE roles (role TEXT PRIMARY KEY CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),"
        " lifecycle TEXT NOT NULL DEFAULT 'unknown' CHECK (lifecycle IN ('unknown','alive','dormant','closed')),"
        " lifecycle_reason TEXT);"
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
    con.executemany("INSERT INTO roles (role, lifecycle, lifecycle_reason) VALUES (?, ?, ?)", roles)
    if group:
        con.execute("INSERT INTO meta (key, value) VALUES ('group_name', ?)", (group,))
    if with_records:
        con.execute("CREATE TABLE phoenix_records (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, "
                    "section TEXT, subject TEXT, body TEXT)")
    con.commit()
    con.close()


def template_roots() -> list[Path]:
    """Где искать образец пакета: сперва MEZO_TEMPLATE, затем то, что знает mezo_paths."""
    roots: list[Path] = []
    if os.environ.get("MEZO_TEMPLATE"):
        roots.append(Path(os.environ["MEZO_TEMPLATE"]))
    try:
        roots.append(mezo_paths.template_root())
    except SystemExit:
        pass
    return roots


# Сборщик контура в собранный контур не копируется (init-group.py: «сборщик живёт в шаблоне,
# а не в контуре»). ⚡ Найдено 2026-10-05 полным прогоном на свежем контуре (карточка #677,
# этап Э3): приёмка искала его только в каталоге механизма контура и отказывала мерить; на
# живом контуре он лежит рядом, поэтому прежде это не было видно.
TEMPLATE_ONLY = {"init-group.py"}


def sut_file(scripts_dir: Path, fname: str) -> Path:
    """Файл испытуемого инструмента механизма: из каталога механизма, сборщик — ещё и из образца."""
    path = scripts_dir / fname
    if path.exists() or fname not in TEMPLATE_ONLY:
        return path
    for root in template_roots():
        if (root / "scripts" / fname).exists():
            return root / "scripts" / fname
    return path


def find_pack_schema() -> Path:
    """Схема пакета (образец контура): из неё строятся базы второй части — настоящая схема, подставные данные."""
    for root in template_roots():
        found = sorted((root / "schema").glob("mezosync_v*.sql"),
                       key=lambda p: int(re.search(r"_v(\d+)", p.name).group(1)))
        if found:
            return found[-1]
    raise NotRun("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: схемы пакета (schema/mezosync_v*.sql образца) нет — "
                 "базы второй части строить не из чего")


def build_stand(tools_dir: Path, scripts_dir: Path, break_name: str | None) -> Stand:
    # Сначала проверяем, что есть из чего строить, и только потом заводим стенд: отказ мерить не
    # должен оставлять за собой пустой каталог.
    for fname in TOOLS.values():
        if not (tools_dir / fname).exists():
            raise NotRun(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: инструмента нет — {tools_dir / fname}")
    if not (tools_dir / "schema_vnext.sql").exists():
        raise NotRun(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: схемы нового контура нет — {tools_dir / 'schema_vnext.sql'}")
    for fname in SUT.values():
        if not sut_file(scripts_dir, fname).exists():
            raise NotRun(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: инструмента механизма нет — {scripts_dir / fname}")
    schema = find_pack_schema()
    st = Stand(mezo_stand.new("bite-roles-from-data-"))
    st.scripts.mkdir(parents=True)
    st.tools.mkdir(parents=True)
    for fname in TOOLS.values():
        mezo_stand.copy_tool(tools_dir / fname, st.tools)
    (st.scripts / "read-phoenix.py").write_text(READ_STUB, encoding="utf-8")
    (st.scripts / "find-phoenix.py").write_text(FIND_STUB, encoding="utf-8")
    (st.root / "drive_guard.py").write_text(GUARD_DRIVER, encoding="utf-8")
    (st.root / "drive_brevity.py").write_text(BREVITY_DRIVER, encoding="utf-8")
    st.canon.write_text("Канон стенда: сокращение `<s>` = `C:/zzx/.mezosync/scripts`\n", encoding="utf-8")
    roles = [(COORD_NAME, "alive", "координатор контура (стенд)"),
             (ROLE_ENV.upper(), "alive", "в реестре стенда"),
             (ROLE_FLAG.upper(), "closed", "закрыта в стенде")]
    make_roles_db(st.db, roles, GROUP, with_records=True)
    make_roles_db(st.nocoord_db, [(ROLE_ENV.upper(), "alive", "в реестре стенда"),
                                  (ROLE_FLAG.upper(), "closed", "закрыта в стенде")], None)
    make_roles_db(st.rhythm_db, [(ROLE_ENV.upper(), "alive", "в реестре стенда"),
                                 (ROLE_FLAG.upper(), "closed", "закрыта в стенде")], GROUP)
    # ── вторая часть: инструменты механизма — копиями ВМЕСТЕ с соседями, образец пакета для сборки контура
    st.schema_text = schema.read_text(encoding="utf-8")
    st.schema_name = schema.name
    st.sut.mkdir(parents=True)
    for key, fname in SUT.items():
        if key != "initg":
            st.paths[key] = mezo_stand.copy_tool(scripts_dir / fname, st.sut)
    (st.sut / "read-broadcasts.py").write_text(FOLD_READ_STUB, encoding="utf-8")
    (st.sut / "write-message.py").write_text(FOLD_WRITE_STUB, encoding="utf-8")
    (st.pack / "scripts").mkdir(parents=True)
    for src in scripts_dir.glob("*.py"):
        shutil.copy2(src, st.pack / "scripts" / src.name)
    for fname in TEMPLATE_ONLY & set(SUT.values()):
        if not (st.pack / "scripts" / fname).exists():
            shutil.copy2(sut_file(scripts_dir, fname), st.pack / "scripts" / fname)
    if (scripts_dir / "migrations").is_dir():
        shutil.copytree(scripts_dir / "migrations", st.pack / "scripts" / "migrations")
    (st.pack / "schema").mkdir()
    shutil.copy2(schema, st.pack / "schema" / schema.name)
    (st.pack / "rules").mkdir()
    (st.pack / "rules" / "universal.sql").write_text("", encoding="utf-8")
    (st.pack / "templates").mkdir()
    (st.pack / "templates" / "coordinator.md").write_text("МАРКЕР-КООРДИНАТОР\n", encoding="utf-8")
    (st.pack / "templates" / "repo-dev.md").write_text("МАРКЕР-РАЗРАБОТЧИК\n", encoding="utf-8")
    st.paths["initg"] = st.pack / "scripts" / SUT["initg"]
    st.dbs.mkdir()
    st.contours.mkdir()
    if break_name:
        _num, edits, _what = BREAKS[break_name]
        for key, anchor, replacement in edits:
            target = st.tools / TOOLS[key] if key in TOOLS else st.paths[key]
            text = target.read_bytes().decode("utf-8")
            found = text.count(anchor)
            if found != 1:
                raise NotRun(f"⛔ НЕ ПРОВЕРЕНО: поломка «{break_name}» НЕ ЛЕГЛА — якорь найден {found} раз "
                             f"(нужен ровно один) в {target.name}")
            target.write_bytes(text.replace(anchor, replacement).encode("utf-8"))
    return st


# ── случаи ────────────────────────────────────────────────────────────────────
def case_init(st: Stand, tools_dir: Path) -> list[tuple[str, bool, str]]:
    tool = str(st.tools / TOOLS["init"])
    schema = str(tools_dir / "schema_vnext.sql")
    subs: list[tuple[str, bool, str]] = []
    target_a = st.root / "contour-a"
    rc, out = call(st, [tool, "--name", "zzx-contour", "--path", str(target_a), "--schema", schema, "--no-rules"])
    refused = rc == 2 and "--roles" in out and "Пример вызова" in out and "usage:" not in out.lower()
    subs.append(("а) без --roles — отказ словами с примером", refused,
                 f"код {rc}; слово «Пример вызова» {'есть' if 'Пример вызова' in out else 'НЕТ'}; "
                 f"английского usage {'нет' if 'usage:' not in out.lower() else 'ЕСТЬ'}"))
    subs.append(("б) база при отказе не создана", not (target_a / "mezosync.db").exists(),
                 f"файл базы {'не создан' if not (target_a / 'mezosync.db').exists() else 'СОЗДАН'}"))
    target_b = st.root / "contour-b"
    rc, out = call(st, [tool, "--name", "zzx-contour", "--path", str(target_b), "--schema", schema,
                        "--no-rules", "--roles"])
    subs.append(("в) голый --roles без значений — тот же отказ", rc == 2 and not (target_b / "mezosync.db").exists(),
                 f"код {rc}; база {'не создана' if not (target_b / 'mezosync.db').exists() else 'СОЗДАНА'}"))
    target_c = st.root / "contour-c"
    rc, out = call(st, [tool, "--name", "zzx-contour", "--path", str(target_c), "--schema", schema,
                        "--no-rules", "--roles", ROLE_ENV, ROLE_FLAG])
    got: set[str] = set()
    db_c = target_c / "mezosync.db"
    if db_c.exists():
        con = sqlite3.connect(f"file:{db_c.as_posix()}?mode=ro", uri=True)
        got = {r for (r,) in con.execute("SELECT role FROM roles")}
        con.close()
    EVIDENCE["init_roles"] = len(got)
    subs.append(("г) с --roles zzx qqr — ровно эти две роли, в верхнем регистре, без COORD",
                 rc == 0 and got == {ROLE_ENV.upper(), ROLE_FLAG.upper()},
                 f"код {rc}; роли в базе {sorted(got)}"))
    return subs


def case_guard_observe(st: Stand) -> list[tuple[str, bool, str]]:
    drv = str(st.root / "drive_guard.py")
    tool = str(st.tools / TOOLS["guard"])
    subs: list[tuple[str, bool, str]] = []
    clear_logs(st)
    rc, out = call(st, [drv, tool, str(st.scripts), "observe"])
    m = re.search(r"ИТОГ-ДРАЙВЕРА команд (\d+)", out)
    n_cmds = int(m.group(1)) if m else -1
    EVIDENCE["help_cmds"] = n_cmds
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    subs.append(("а) роль не передана — read-phoenix не запускается", m is not None and not logged,
                 f"прогнано команд {n_cmds}; запусков read-phoenix с ролью: {logged or 'нет'}"))
    clear_logs(st)
    rc, out = call(st, [drv, tool, str(st.scripts), "observe", ROLE_ENV.upper()])
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    subs.append(("б) встречный: роль названа — read-phoenix запускается именно с ней",
                 logged == [ROLE_ENV.upper()], f"запуски: {logged or 'нет'}"))
    return subs


def case_guard_run(st: Stand) -> list[tuple[str, bool, str]]:
    drv = str(st.root / "drive_guard.py")
    tool = str(st.tools / TOOLS["guard"])
    subs: list[tuple[str, bool, str]] = []
    clear_logs(st)
    rc, out = call(st, [drv, tool, str(st.scripts), "run"])
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    said = "не проверено: роль не названа" in out
    subs.append(("а) роль не передана — сказано «не проверено», read-phoenix не запускается",
                 said and not logged and "ИТОГ-ДРАЙВЕРА" in out,
                 f"фраза «не проверено» {'есть' if said else 'НЕТ'}; запуски: {logged or 'нет'}"))
    clear_logs(st)
    rc, out = call(st, [drv, tool, str(st.scripts), "run", ROLE_ENV.upper()])
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    said = "не проверено: роль не названа" in out
    subs.append(("б) встречный: роль названа — read-phoenix запускается с ней, «не проверено» нет",
                 logged == [ROLE_ENV.upper()] and not said,
                 f"запуски: {logged or 'нет'}; фраза «не проверено» {'есть' if said else 'нет'}"))
    return subs


def guard_main(st: Stand, db: Path, tasks: Path, extra_args: list[str] | None = None,
               extra_env: dict | None = None) -> tuple[int, str]:
    args = [str(st.tools / TOOLS["guard"]), "--scripts", str(st.scripts),
            "--artifacts", str(st.root / "нет-каталога-файлов"), "--canon", str(st.canon),
            "--db", str(db), "--tasks-dir", str(tasks), "--no-rules", *(extra_args or [])]
    return call(st, args, extra=extra_env)


def case_guard_role_flag(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    empty_tasks = st.root / "нет-наказов"
    clear_logs(st)
    rc, out = guard_main(st, st.db, empty_tasks)
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    subs.append(("а) ни флага, ни среды — роль из данных (координатор контура)",
                 logged == [COORD_NAME] and "прогнано" in out,
                 f"запуски read-phoenix: {logged or 'нет'}; ждали [{COORD_NAME}]"))
    clear_logs(st)
    rc, out = guard_main(st, st.db, empty_tasks, extra_env={"MEZO_ROLE": ROLE_ENV})
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    subs.append(("б) MEZO_ROLE=zzx — роль из среды, регистр приведён", logged == [ROLE_ENV.upper()],
                 f"запуски: {logged or 'нет'}"))
    clear_logs(st)
    rc, out = guard_main(st, st.db, empty_tasks, extra_args=["--role", ROLE_FLAG],
                         extra_env={"MEZO_ROLE": ROLE_ENV})
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    subs.append(("в) флаг --role побеждает среду", logged == [ROLE_FLAG.upper()], f"запуски: {logged or 'нет'}"))
    clear_logs(st)
    rc, out = guard_main(st, st.nocoord_db, empty_tasks)
    logged = roles_of(read_log(st, "read-phoenix.calls.log"))
    said = "не проверено: роль не названа" in out
    subs.append(("г) координатора в данных нет и роль не названа — «не проверено», read-phoenix не запускается",
                 said and not logged, f"фраза {'есть' if said else 'НЕТ'}; запуски: {logged or 'нет'}"))
    return subs


def flagged_tasks(out: str) -> set[str]:
    return set(re.findall(r"── НАКАЗ ([\w-]+)/SKILL\.md: ссылки на правило ответов НЕТ", out))


def case_guard_skill(st: Stand) -> list[tuple[str, bool, str]]:
    for name, text in (
        ("by-contour-name", f"Ответ владельцу веди по навыку {GROUP}-owner-reply."),
        ("by-foreign-name", "Ответ владельцу веди по навыку atlas-owner-reply."),
        ("by-key", "Форма ответа задана ключом правила owner-reply-format."),
        ("no-link", "Просто выполни порученное и напиши итог."),
    ):
        folder = st.tasks / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(text + "\n", encoding="utf-8")
    subs: list[tuple[str, bool, str]] = []
    rc, out = guard_main(st, st.db, st.tasks, extra_env={"MEZO_ROLE": ROLE_ENV})
    got = flagged_tasks(out)
    want = {"by-foreign-name", "no-link"}
    subs.append(("а) имя из данных (zzx-owner-reply) принимается; чужое имя и отсутствие ссылки — находка",
                 got == want and "наказы-файлы" in out, f"отмечены {sorted(got)}; ждали {sorted(want)}"))
    rc, out = guard_main(st, st.nocoord_db, st.tasks, extra_env={"MEZO_ROLE": ROLE_ENV})
    got = flagged_tasks(out)
    want = {"by-contour-name", "by-foreign-name", "no-link"}
    said = "имя навыка ответов владельцу не прочитано" in out
    subs.append(("б) имя контура не читается — сказано словами, судим только по ключу правила",
                 got == want and said,
                 f"отмечены {sorted(got)}; ждали {sorted(want)}; фраза об имени {'есть' if said else 'НЕТ'}"))
    return subs


def case_memory(st: Stand) -> list[tuple[str, bool, str]]:
    tool = str(st.tools / TOOLS["memory"])
    qset = st.root / "memory-set.json"
    qset.write_text(json.dumps([{"n": 1, "query": "альфа", "role": ROLE_ENV.upper(), "expect_word": "альфа"}],
                               ensure_ascii=False), encoding="utf-8")
    base = [tool, "--set", str(qset), "--db", str(st.db)]
    subs: list[tuple[str, bool, str]] = []
    clear_logs(st)
    rc, out = call(st, base)
    calls = read_log(st, "find-phoenix.calls.log")
    subs.append(("а) ни --actor, ни MEZO_ROLE — отказ словами, ни один поиск не запускался",
                 rc == 2 and "не названа роль руки" in out and not calls,
                 f"код {rc}; фраза об отказе {'есть' if 'не названа роль руки' in out else 'НЕТ'}; "
                 f"запусков поиска {len(calls)}"))
    clear_logs(st)
    rc, out = call(st, base, extra={"MEZO_ROLE": ROLE_ENV})
    calls = read_log(st, "find-phoenix.calls.log")
    EVIDENCE["memory_calls"] = len(calls)
    subs.append(("б) MEZO_ROLE=zzx — поиск идёт от имени ZZX",
                 any(c.startswith(f"--actor {ROLE_ENV.upper()} ") for c in calls) and len(calls) >= 1,
                 f"журнал поиска: {calls or 'пуст'}"))
    clear_logs(st)
    rc, out = call(st, base + ["--actor", ROLE_FLAG], extra={"MEZO_ROLE": ROLE_ENV})
    calls = read_log(st, "find-phoenix.calls.log")
    subs.append(("в) флаг --actor побеждает среду",
                 len(calls) >= 1 and all(c.startswith(f"--actor {ROLE_FLAG.upper()} ") for c in calls),
                 f"журнал поиска: {calls or 'пуст'}"))
    return subs


def case_brevity(st: Stand) -> list[tuple[str, bool, str]]:
    tool = str(st.tools / TOOLS["brevity"])
    subs: list[tuple[str, bool, str]] = []
    rc, out = call(st, [tool, "--list"])
    subs.append(("а) ни --role, ни MEZO_ROLE — отказ словами, набор вызовов не печатается",
                 rc == 2 and "не названа роль" in out and "ФИКСИРОВАННЫЙ НАБОР" not in out,
                 f"код {rc}; фраза об отказе {'есть' if 'не названа роль' in out else 'НЕТ'}"))
    rc, out = call(st, [tool, "--list"], extra={"MEZO_ROLE": ROLE_ENV})
    with_role = len(re.findall(rf"--role {ROLE_ENV.upper()}\b", out))
    EVIDENCE["brevity_lines"] = with_role
    subs.append(("б) MEZO_ROLE=zzx — в наборе вызовов роль ZZX, прежних имён нет",
                 rc == 0 and with_role >= 10 and not any(w in out for w in ("PROTO", "COORD")),
                 f"код {rc}; вызовов с ролью ZZX {with_role}"))
    rc, out = call(st, [tool, "--list", "--role", ROLE_FLAG], extra={"MEZO_ROLE": ROLE_ENV})
    subs.append(("в) флаг --role побеждает среду",
                 rc == 0 and f"роль {ROLE_FLAG.upper()}" in out and f"--role {ROLE_ENV.upper()}" not in out,
                 f"код {rc}"))
    rc, out = call(st, [str(st.root / "drive_brevity.py"), str(st.tools / TOOLS["brevity"]), ROLE_ENV.upper()])
    subs.append(("г) тело пробы сохранения несёт имя названной роли, а не прежнее",
                 f"роль {ROLE_ENV.upper()}" in out and "PROTO" not in out, f"код {rc}"))
    return subs


def write_chat(path: Path, token_flag: str, token: str) -> int:
    """Один чат: вызов с названной ролью и шесть ударов механизма через 30 минут."""
    import datetime as dt
    start = dt.datetime(2026, 9, 1, 0, 0, tzinfo=dt.timezone.utc)
    lines = [json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": f"python read-messages.py {token_flag} {token}"}]}}, ensure_ascii=False)]
    for i in range(6):
        stamp = (start + dt.timedelta(minutes=30 * i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        lines.append(json.dumps({"type": "user", "promptSource": "sdk", "isMeta": True, "timestamp": stamp,
                                 "message": {"role": "user", "content": [
                                     {"type": "text", "text": "исполни наказ-файл"}]}}, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def case_rhythm(st: Stand) -> list[tuple[str, bool, str]]:
    st.chats.mkdir(parents=True, exist_ok=True)
    records = 0
    records += write_chat(st.chats / "z0000001.jsonl", "--роль", ROLE_ENV.upper())
    records += write_chat(st.chats / "q0000002.jsonl", "--role", ROLE_FLAG.upper())   # роль закрыта — всё равно имя
    records += write_chat(st.chats / "w0000003.jsonl", "--роль", "WWW")               # в таблице roles её нет
    EVIDENCE["chat_records"] = records
    tool = str(st.tools / TOOLS["rhythm"])
    judge_at = "2026-09-01T02:50:00"
    subs: list[tuple[str, bool, str]] = []
    rc, out = call(st, [tool, "--каталог", str(st.chats), "--на", judge_at, "--db", str(st.rhythm_db)])
    seen = {r for r in (ROLE_ENV.upper(), ROLE_FLAG.upper(), "WWW") if f"━━ {r} ·" in out}
    subs.append(("а) имена из таблицы roles: опознаны ZZX и закрытая QQR, постороннее WWW — нет",
                 seen == {ROLE_ENV.upper(), ROLE_FLAG.upper()} and "таблица roles, 2 шт." in out
                 and "ОБРАЗЦОМ" not in out,
                 f"опознаны {sorted(seen)}; строка об источнике {'из таблицы' if 'таблица roles' in out else 'НЕТ'}"))
    rc, out = call(st, [tool, "--каталог", str(st.chats), "--на", judge_at,
                        "--db", str(st.root / "нет-такой-базы.db")])
    seen = {r for r in (ROLE_ENV.upper(), ROLE_FLAG.upper(), "WWW") if f"━━ {r} ·" in out}
    subs.append(("б) базы нет — имена взяты образцом, и строка об этом напечатана",
                 "ОБРАЗЦОМ" in out and seen == {ROLE_ENV.upper(), ROLE_FLAG.upper(), "WWW"},
                 f"опознаны {sorted(seen)}; строка об образце {'есть' if 'ОБРАЗЦОМ' in out else 'НЕТ'}"))
    return subs


def case_control(st: Stand, tools_dir: Path) -> list[tuple[str, bool, str]]:
    sizes = {k: (tools_dir / f).stat().st_size for k, f in TOOLS.items()}
    names = {COORD_NAME, ROLE_ENV.upper(), ROLE_FLAG.upper(), "WWW"}
    clash = names & set(OLD_LITERALS)
    return [
        ("а) все пять инструментов найдены и непусты", all(v > 1000 for v in sizes.values()),
         ", ".join(f"{k} {v} байт" for k, v in sizes.items())),
        ("б) имена стенда не совпадают с прежними литералами — возврат литерала различим", not clash,
         f"пересечение {sorted(clash) or 'пусто'}"),
        ("в) прогнано команд наблюдения охраняющим инструментом ≥ 2", EVIDENCE.get("help_cmds", 0) >= 2,
         f"{EVIDENCE.get('help_cmds', 0)}"),
        ("г) записей в чатах стенда ≥ 18", EVIDENCE.get("chat_records", 0) >= 18,
         f"{EVIDENCE.get('chat_records', 0)}"),
    ]


# ── вторая часть (Э3, Р2): базы из схемы пакета и случаи ⑩–⑲ ─────────────────────
def pack_db(st: Stand, name: str, roles: list[tuple], rows: list[tuple[str, tuple]] | None = None) -> Path:
    """База из СХЕМЫ ПАКЕТА с подставными ролями: roles — [(роль, жизнь, причина, зона, в_реестре)];
    rows — дополнительные строки [(запрос, параметры)]. Файл лежит в st.dbs, не в «живом» месте стенда."""
    path = st.dbs / f"{name}.db"
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    con.executescript(st.schema_text)
    con.executemany("INSERT INTO roles (role, lifecycle, lifecycle_reason, zone, in_roster) VALUES (?,?,?,?,?)",
                    roles)
    for sql, params in (rows or []):
        con.execute(sql, params)
    con.commit()
    con.close()
    return path


def roles_with_coordinator() -> list[tuple]:
    """Контур стенда с координатором из данных: COORD-A, живые ZZX и AAA, снятая с реестра QQR, спящая и закрытая."""
    return [(COORD_NAME, "alive", "координатор контура (стенд)", "Зона координатора. Вторая фраза в подпись не идёт.", 1),
            (ROLE_ENV.upper(), "alive", "в реестре стенда", ZONE_LONG, 1),
            ("AAA", "alive", "в реестре стенда", "Первая зона. Хвост", 1),
            (ROLE_FLAG.upper(), "alive", "в реестре стенда", "Снята с реестра", 0),
            ("DDD", "dormant", "спит", "Спящая", 1),
            ("CCC", "closed", "закрыта", "Закрытая", 1)]


def roles_without_coordinator() -> list[tuple]:
    """То же без координатора: слова «координатор» нет ни в одной причине."""
    return [r for r in roles_with_coordinator() if r[0] != COORD_NAME]


def roles_atlas_like() -> list[tuple]:
    """Раскладка Atlas: координатор — роль COORD (имя прежнего литерала, но теперь ИЗ ДАННЫХ)."""
    return [("COORD", "alive", "координатор контура", "atlas.archs", 1),
            (ROLE_ENV.upper(), "alive", "в реестре стенда", "зона стенда", 1)]


def sut(st: Stand, key: str, args: list[str], extra: dict | None = None, timeout: int = 180) -> tuple[int, str]:
    return call(st, [str(st.paths[key]), *args], extra=extra, timeout=timeout)


def audit_of(db: Path, target: str) -> list[tuple[str, str]]:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return [(a, b) for a, b in con.execute(
            "SELECT actor_role, action FROM audit_log WHERE target=? ORDER BY id", (target,))]
    finally:
        con.close()


def scalar(db: Path, sql: str, params: tuple = ()):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


# ⑩ dashboard.py ──────────────────────────────────────────────────────────────
def dash_cards(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<h3>([^<]*?) <span class="role-sub">([^<]*)</span></h3>', html)


def case_dashboard(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    long_label = " ".join(ZONE_LONG.split())[:ZONE_LABEL_LIMIT].rstrip() + "…"

    def render(db: Path, name: str) -> tuple[int, str, list[tuple[str, str]], str]:
        out = st.root / f"dash-{name}.html"
        rc, text = sut(st, "dash", ["--db", str(db), "--out", str(out)])
        html = out.read_text(encoding="utf-8") if out.exists() else ""
        return rc, text, dash_cards(html), html

    rc, text, cards, _ = render(pack_db(st, "dash-a", roles_with_coordinator()), "a")
    want = [(COORD_NAME, "Зона координатора"), ("AAA", "Первая зона"), (ROLE_ENV.upper(), long_label)]
    EVIDENCE["dash_cards"] = len(cards)
    subs.append(("а) карточки — из таблицы roles: живые и не снятые с реестра, координатор первым, затем по имени; "
                 "подпись — первое предложение зоны либо 60 знаков с «…»",
                 rc == 0 and cards == want, f"код {rc}; карточки {cards}; ждали {want}"))
    rc, text, cards, _ = render(pack_db(st, "dash-b", roles_without_coordinator()), "b")
    want = [("AAA", "Первая зона"), (ROLE_ENV.upper(), long_label)]
    subs.append(("б) координатора в данных нет — просто по имени", rc == 0 and cards == want,
                 f"код {rc}; карточки {cards}; ждали {want}"))
    rc, text, cards, html = render(pack_db(st, "dash-c", [("CCC", "closed", "закрыта", "Закрытая", 1)]), "c")
    subs.append(("в) живых ролей нет — карточек нет и страница об этом говорит словами",
                 rc == 0 and cards == [] and "нет живых ролей" in html,
                 f"код {rc}; карточки {cards}; фраза {'есть' if 'нет живых ролей' in html else 'НЕТ'}"))
    return subs


# ⑪ init-group.py ─────────────────────────────────────────────────────────────
def init_run(st: Stand, tag: str, *args: str) -> tuple[int, str, Path, Path]:
    target = st.contours / tag / ".mezosync"
    rc, out = sut(st, "initg", ["--name", "zzx-contour", "--path", str(target), *args], timeout=600)
    return rc, out, target, target / "mezosync.db"


def contour_state(db: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Роли контура с причинами и тексты заготовок памяти (§identity) по ролям."""
    if not db.exists():
        return {}, {}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        reasons = {r: (why or "") for r, why in con.execute("SELECT role, lifecycle_reason FROM roles")}
        bodies = {r: b for r, b in con.execute("SELECT role, body FROM phoenix WHERE section='identity'")}
    finally:
        con.close()
    return reasons, bodies


def case_init_group(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    rc, out, target, db = init_run(st, "a")
    subs.append(("а) без --roles — отказ словами с примером, база и каталог не созданы",
                 rc == 2 and "--roles" in out and "Пример вызова" in out and "usage:" not in out.lower()
                 and not db.exists() and not target.exists(),
                 f"код {rc}; «Пример вызова» {'есть' if 'Пример вызова' in out else 'НЕТ'}; "
                 f"база {'СОЗДАНА' if db.exists() else 'не создана'}"))
    rc, out, target, db = init_run(st, "b", "--roles")
    subs.append(("б) голый --roles без значений — тот же отказ", rc == 2 and not db.exists() and not target.exists(),
                 f"код {rc}; база {'СОЗДАНА' if db.exists() else 'не создана'}"))
    rc, out, target, db = init_run(st, "c", "--roles", ROLE_ENV, ROLE_FLAG)
    reasons, bodies = contour_state(db)
    line = "координатор — ZZX (первая из --roles; другой — флаг --coordinator)"
    EVIDENCE["init_group_roles"] = len(reasons)
    subs.append(("в) --roles zzx qqr — координатор первая (ZZX), строка об этом, заготовки по роли, COORD нет",
                 rc == 0 and set(reasons) == {"ZZX", "QQR"} and "координатор" in reasons.get("ZZX", "")
                 and "координатор" not in reasons.get("QQR", "") and line in out
                 and "МАРКЕР-КООРДИНАТОР" in bodies.get("ZZX", "") and "МАРКЕР-РАЗРАБОТЧИК" in bodies.get("QQR", ""),
                 f"код {rc}; роли {sorted(reasons)}; строка {'есть' if line in out else 'НЕТ'}; "
                 f"заготовка ZZX {'координатора' if 'МАРКЕР-КООРДИНАТОР' in bodies.get('ZZX', '') else 'другая'}"))
    rc, out, target, db = init_run(st, "d", "--roles", ROLE_ENV, ROLE_FLAG, "--coordinator", ROLE_FLAG)
    reasons, bodies = contour_state(db)
    subs.append(("г) --coordinator qqr — координатор другая, строка называет флаг",
                 rc == 0 and "координатор" in reasons.get("QQR", "") and "координатор" not in reasons.get("ZZX", "")
                 and "координатор — QQR (по флагу --coordinator)" in out
                 and "МАРКЕР-КООРДИНАТОР" in bodies.get("QQR", "") and "МАРКЕР-РАЗРАБОТЧИК" in bodies.get("ZZX", ""),
                 f"код {rc}; роли {sorted(reasons)}"))
    rc, out, target, db = init_run(st, "e", "--roles", ROLE_ENV, ROLE_FLAG, "--coordinator", "www")
    subs.append(("д) --coordinator вне --roles — отказ словами, база не создана",
                 rc == 2 and "не назван среди --roles" in out and not db.exists(),
                 f"код {rc}; фраза {'есть' if 'не назван среди --roles' in out else 'НЕТ'}"))
    rc, out, target, db = init_run(st, "f", "--roles", "coord", "core")
    reasons, bodies = contour_state(db)
    subs.append(("е) раскладка Atlas (--roles coord core): координатор COORD, как прежде",
                 rc == 0 and set(reasons) == {"COORD", "CORE"} and "координатор" in reasons.get("COORD", "")
                 and "координатор" not in reasons.get("CORE", "")
                 and "координатор — COORD (первая из --roles" in out,
                 f"код {rc}; роли {sorted(reasons)}"))
    return subs


# ⑫ messages-fold.py ──────────────────────────────────────────────────────────
def fold_db(st: Stand, name: str) -> Path:
    rows: list[tuple[str, tuple]] = [
        ("INSERT INTO messages (id, writer_role, timestamp, body_md) VALUES (?,?,?,?)",
         (i, ROLE_ENV.upper(), "2026-01-01 00:00:00", f"старая записка {i}")) for i in (1, 2, 3)]
    rows += [("INSERT INTO read_cursors (reader_role, last_read_id) VALUES (?,?)", (r, 3))
             for r in (ROLE_ENV.upper(), ROLE_FLAG.upper())]
    db = pack_db(st, name, roles_without_coordinator(), rows)
    # Таблицы архива ленты нет в файле схемы пакета до v6: её заводит шаг 20260905-messages-archive,
    # и у живого контура она есть потому, что шаг применён (сборкой или обновлением). Стенд делает
    # то же — штатным шагом из копии механизма, а не своей таблицей.
    # ⚡ Найдено 2026-10-05 проверкой документа обновления (Р9) на ВЫГРУЗКЕ пакета: в клоне автора лежала
    # незакоммиченная schema/mezosync_v6.sql (коммитить её нельзя — слово владельца 14.09), и случай ⑫
    # проходил только на этой машине; на чистом пакете — «no such table: messages_archive».
    if not scalar(db, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='messages_archive'"):
        step = st.pack / "scripts" / "migrations" / f"{ARCHIVE_STEP}.py"
        if not step.exists():
            raise NotRun(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в схеме пакета нет таблицы messages_archive, а шага "
                         f"{ARCHIVE_STEP} среди шагов механизма нет — {step}")
        rc, out = call(st, [str(step), "--db", str(db)])
        if rc != 0 or not scalar(db, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                                     "AND name='messages_archive'"):
            raise NotRun(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: шаг {ARCHIVE_STEP} на базе стенда не завёл архив ленты "
                         f"(код {rc}): {out.strip()[-300:]}")
    return db


def fold_state(db: Path) -> tuple[int, int, list[str]]:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        live = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        arch = con.execute("SELECT COUNT(*) FROM messages_archive").fetchone()[0]
        hands = sorted({h for (h,) in con.execute("SELECT moved_by FROM messages_archive")})
    finally:
        con.close()
    return live, arch, hands


def case_fold(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    db = fold_db(st, "fold-a")
    rc, out = sut(st, "fold", ["--apply", "--db", str(db)])
    live, arch, hands = fold_state(db)
    subs.append(("а) --apply без руки (ни флага, ни MEZO_ROLE) — отказ словами, записки на месте",
                 rc == 2 and "не названа рука" in out and (live, arch) == (3, 0),
                 f"код {rc}; фраза {'есть' if 'не названа рука' in out else 'НЕТ'}; живых {live}, в архиве {arch}, "
                 f"рука в архиве {hands or '—'}"))
    rc, out = sut(st, "fold", ["--db", str(db)])
    live, arch, hands = fold_state(db)
    subs.append(("б) холостой прогон без руки — работает и говорит «рука не названа»",
                 rc == 0 and "рука не названа" in out and (live, arch) == (3, 0),
                 f"код {rc}; фраза {'есть' if 'рука не названа' in out else 'НЕТ'}; живых {live}, в архиве {arch}"))
    db = fold_db(st, "fold-b")
    rc, out = sut(st, "fold", ["--apply", "--db", str(db)], extra={"MEZO_ROLE": ROLE_ENV})
    live, arch, hands = fold_state(db)
    EVIDENCE["fold_moved"] = arch
    subs.append(("в) MEZO_ROLE=zzx — унесено, в архиве рука ZZX", rc == 0 and (live, arch) == (0, 3) and hands == ["ZZX"],
                 f"код {rc}; живых {live}, в архиве {arch}; рука {hands or '—'}"))
    db = fold_db(st, "fold-c")
    rc, out = sut(st, "fold", ["--apply", "--role", ROLE_FLAG, "--db", str(db)], extra={"MEZO_ROLE": ROLE_ENV})
    live, arch, hands = fold_state(db)
    subs.append(("г) флаг --role побеждает среду — в архиве рука QQR", rc == 0 and (live, arch) == (0, 3) and hands == ["QQR"],
                 f"код {rc}; живых {live}, в архиве {arch}; рука {hands or '—'}"))
    return subs


# ⑬ set-rule.py ───────────────────────────────────────────────────────────────
def rule_args(db: Path, key: str, *extra: str, apply: bool = True) -> list[str]:
    return ["--db", str(db), "--key", key, "--body", f"текст правила {key}", "--basis", "замер стенда",
            "--authorized-by", "стенд", "--source-ref", "чат стенда", "--expiry-kind", "forever",
            *extra, *(["--apply"] if apply else [])]


def case_set_rule(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    coord_db = pack_db(st, "rule-coord", roles_with_coordinator())
    rc, out = sut(st, "rule", rule_args(coord_db, "zz-flag", "--actor", ROLE_FLAG), extra={"MEZO_ROLE": ROLE_ENV})
    got = audit_of(coord_db, "zz-flag")
    subs.append(("а) флаг --actor побеждает среду; строки «пишет:» нет",
                 rc == 0 and [a.upper() for a, _ in got] == [ROLE_FLAG.upper()] and "пишет:" not in out,
                 f"код {rc}; журнал правок {got}"))
    rc, out = sut(st, "rule", rule_args(coord_db, "zz-env"), extra={"MEZO_ROLE": ROLE_ENV})
    got = audit_of(coord_db, "zz-env")
    subs.append(("б) без флага — рука из MEZO_ROLE (в верхнем регистре); строки «пишет:» нет",
                 rc == 0 and got == [(ROLE_ENV.upper(), "create_rule")] and "пишет:" not in out,
                 f"код {rc}; журнал правок {got}"))
    rc, out = sut(st, "rule", rule_args(coord_db, "zz-coord"))
    got = audit_of(coord_db, "zz-coord")
    line = f"пишет: {COORD_NAME} (координатор контура; --actor не дан)"
    subs.append(("в) ни флага, ни среды — рука координатор из данных, одна печатная строка «пишет: …»; зеркало живого не тронуто",
                 rc == 0 and got == [(COORD_NAME, "create_rule")] and line in out and "БАЗА НЕ ЖИВАЯ" in out,
                 f"код {rc}; журнал правок {got}; строка {'есть' if line in out else 'НЕТ'}; "
                 f"«БАЗА НЕ ЖИВАЯ» {'есть' if 'БАЗА НЕ ЖИВАЯ' in out else 'НЕТ'}"))
    plain_db = pack_db(st, "rule-plain", roles_without_coordinator(),
                       [("INSERT INTO rules (rule_key, body, locked_by) VALUES (?,?,?)",
                         ("zz-seen", "видимый текст", "coord"))])
    rc, out = sut(st, "rule", rule_args(plain_db, "zz-none"))
    had = scalar(plain_db, "SELECT COUNT(*) FROM rules WHERE rule_key='zz-none'")
    logged = scalar(plain_db, "SELECT COUNT(*) FROM audit_log WHERE target='zz-none'")
    subs.append(("г) координатора нет и рука не названа — отказ словами, правило и журнал не тронуты",
                 rc == 2 and "ЗАПИСЬ НЕ СДЕЛАНА" in out and had == 0 and logged == 0,
                 f"код {rc}; фраза {'есть' if 'ЗАПИСЬ НЕ СДЕЛАНА' in out else 'НЕТ'}; правил с ключом {had}; журнал {logged}"))
    rc1, out1 = sut(st, "rule", ["--db", str(plain_db), "--list"])
    rc2, out2 = sut(st, "rule", ["--db", str(plain_db), "--show", "--key", "zz-seen"])
    rc3, out3 = sut(st, "rule", rule_args(plain_db, "zz-dry", apply=False))
    rc4, out4 = sut(st, "rule", ["--db", str(plain_db), "--key", "zz-seen", "--annex"])
    bad = "ЗАПИСЬ НЕ СДЕЛАНА" in (out1 + out2 + out3 + out4) or "Traceback" in (out1 + out2 + out3 + out4)
    subs.append(("д) чтение (--list · --show · --annex) и холостой прогон руки не ищут и не требуют — без координатора работают",
                 rc1 == 0 and "zz-seen" in out1 and rc2 == 0 and "видимый текст" in out2
                 and rc3 == 0 and "[DRY-RUN]" in out3 and not bad,
                 f"коды {rc1}/{rc2}/{rc3}/{rc4}; отказа о руке {'нет' if not bad else 'ЕСТЬ'}"))
    rc, out = sut(st, "rule", ["--db", str(coord_db), "--key", "zz-env", "--revoke", "--reason", "стенд",
                               "--revoked-by", "owner", "--apply"])
    got = audit_of(coord_db, "zz-env")
    subs.append(("е) снятие правила тем же порядком: без флага и среды — рука координатор из данных",
                 rc == 0 and got[-1:] == [(COORD_NAME, "revoke_rule")] and f"пишет: {COORD_NAME}" in out,
                 f"код {rc}; журнал правок {got}"))
    atlas_db = pack_db(st, "rule-atlas", roles_atlas_like())
    rc, out = sut(st, "rule", rule_args(atlas_db, "zz-atlas"))
    got = audit_of(atlas_db, "zz-atlas")
    subs.append(("ж) раскладка Atlas (координатор в данных — COORD): запись без --actor идёт от COORD, как прежде",
                 rc == 0 and got == [("COORD", "create_rule")]
                 and "пишет: COORD (координатор контура; --actor не дан)" in out,
                 f"код {rc}; журнал правок {got}"))
    return subs


# ⑭ set-registry.py ───────────────────────────────────────────────────────────
def case_set_registry(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    coord_db = pack_db(st, "reg-coord", roles_with_coordinator())

    def inv(db: Path, code: str, *extra: str, env: dict | None = None, apply: bool = True):
        return sut(st, "registry", ["--db", str(db), "invariant", "--code", code, "--desc", f"инвариант {code}",
                                    *extra, *(["--apply"] if apply else [])], extra=env)

    rc, out = inv(coord_db, "ZZ-INV-A", "--actor", ROLE_FLAG, env={"MEZO_ROLE": ROLE_ENV})
    got = audit_of(coord_db, "ZZ-INV-A")
    who = scalar(coord_db, "SELECT established_by FROM invariants WHERE code='ZZ-INV-A'")
    subs.append(("а) флаг --actor побеждает среду; «кто установил» инварианта — рука, а не «coord»",
                 rc == 0 and [a.upper() for a, _ in got] == [ROLE_FLAG.upper()]
                 and (who or "").upper() == ROLE_FLAG.upper() and "пишет:" not in out,
                 f"код {rc}; журнал {got}; установил {who}"))
    rc, out = inv(coord_db, "ZZ-INV-B", env={"MEZO_ROLE": ROLE_ENV})
    got = audit_of(coord_db, "ZZ-INV-B")
    who = scalar(coord_db, "SELECT established_by FROM invariants WHERE code='ZZ-INV-B'")
    subs.append(("б) без флага — рука из MEZO_ROLE", rc == 0 and got == [(ROLE_ENV.upper(), "create_invariant")]
                 and who == ROLE_ENV.upper(), f"код {rc}; журнал {got}; установил {who}"))
    rc, out = inv(coord_db, "ZZ-INV-C")
    got = audit_of(coord_db, "ZZ-INV-C")
    who = scalar(coord_db, "SELECT established_by FROM invariants WHERE code='ZZ-INV-C'")
    line = f"пишет: {COORD_NAME} (координатор контура; --actor не дан)"
    subs.append(("в) ни флага, ни среды — рука координатор из данных, строка «пишет: …»",
                 rc == 0 and got == [(COORD_NAME, "create_invariant")] and who == COORD_NAME and line in out,
                 f"код {rc}; журнал {got}; установил {who}; строка {'есть' if line in out else 'НЕТ'}"))
    rc, out = sut(st, "registry", ["--db", str(coord_db), "track", "--id", "ZZ-T-1", "--title", "трек стенда",
                                   "--apply"])
    got = audit_of(coord_db, "ZZ-T-1")
    subs.append(("г) второй путь записи (track) — тот же порядок", rc == 0 and got == [(COORD_NAME, "create_track")],
                 f"код {rc}; журнал {got}"))
    plain_db = pack_db(st, "reg-plain", roles_without_coordinator())
    rc, out = inv(plain_db, "ZZ-INV-D")
    had = scalar(plain_db, "SELECT COUNT(*) FROM invariants WHERE code='ZZ-INV-D'")
    subs.append(("д) координатора нет и рука не названа — отказ словами, ничего не записано",
                 rc != 0 and "ЗАПИСЬ НЕ СДЕЛАНА" in out and had == 0,
                 f"код {rc}; фраза {'есть' if 'ЗАПИСЬ НЕ СДЕЛАНА' in out else 'НЕТ'}; строк {had}"))
    rc1, out1 = inv(plain_db, "ZZ-INV-E", apply=False)
    rc2, out2 = sut(st, "registry", ["--db", str(plain_db), "list"])
    subs.append(("е) холостой прогон и list руки не ищут и не требуют",
                 rc1 == 0 and "[DRY-RUN]" in out1 and rc2 == 0 and "ЗАПИСЬ НЕ СДЕЛАНА" not in out1 + out2,
                 f"коды {rc1}/{rc2}"))
    return subs


# ⑮ backlog.py ────────────────────────────────────────────────────────────────
def backlog_hint(st: Stand, name: str, roles: list[tuple]) -> tuple[int, str]:
    db = pack_db(st, name, roles,
                 [("INSERT INTO backlog (id, role, title, tags, status) VALUES (?,?,?,?,?)",
                   (1, ROLE_ENV.upper(), "карточка стенда", '["gordi-issue #12"]', "open"))])
    return sut(st, "backlog", ["--db", str(db), "status", "1", "dropped", "--actor", ROLE_ENV.upper(),
                               "--note", "причина: стенд"])


def hint_line(out: str, marker: str) -> str:
    return next((ln.strip() for ln in out.splitlines() if marker in ln), "НЕТ")[:150]


def case_backlog_hint(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    rc, out = backlog_hint(st, "backlog-coord", roles_with_coordinator())
    subs.append(("а) подсказка про закрытие issue называет координатора ИЗ ДАННЫХ",
                 rc == 0 and f"gordi-issue.py close --role {COORD_NAME} " in out and f"(рукой {COORD_NAME})" in out
                 and "--role COORD " not in out,
                 f"код {rc}; строка {hint_line(out, 'gordi-issue.py close')}"))
    rc, out = backlog_hint(st, "backlog-plain", roles_without_coordinator())
    subs.append(("б) координатор не определился — заполнитель «<координатор>», а не чужое имя",
                 rc == 0 and "gordi-issue.py close --role <координатор> " in out and "(рукой <координатор>)" in out,
                 f"код {rc}; строка {hint_line(out, 'gordi-issue.py close')}"))
    return subs


# ⑯ gordi-issue.py ────────────────────────────────────────────────────────────
def hint_add(out: str) -> str:
    found = re.search(r"add --role \S+", out)
    return found.group(0) if found else "НЕТ"


def case_gordi_poll(st: Stand) -> list[tuple[str, bool, str]]:
    subs: list[tuple[str, bool, str]] = []
    db = pack_db(st, "gissue", roles_with_coordinator())
    fixture = st.root / "issues.json"
    fixture.write_text(json.dumps([{"number": 77, "title": "заявка стенда", "createdAt": "2026-01-01T00:00:00Z",
                                    "comments": []}], ensure_ascii=False), encoding="utf-8")
    base = ["poll", "--role", ROLE_ENV.upper(), "--db", str(db), "--fixture", str(fixture)]
    rc, out = sut(st, "gissue", base)
    subs.append(("а) подсказка «завести» несёт роль ЭТОГО вызова (--role), а не PROTO",
                 rc == 0 and f"add --role {ROLE_ENV.upper()} " in out and "--role PROTO" not in out,
                 f"код {rc}; команда в подсказке: {hint_add(out)}"))
    rc, out = sut(st, "gissue", base, extra={"MEZO_ROLE": ROLE_FLAG})
    subs.append(("б) среда не перебивает названную вызовом роль", rc == 0 and f"add --role {ROLE_ENV.upper()} " in out,
                 f"код {rc}"))
    return subs


# ⑰ save-phoenix.py ───────────────────────────────────────────────────────────
def case_phoenix_help(st: Stand) -> list[tuple[str, bool, str]]:
    rc, out = sut(st, "phoenix", ["--help"])
    flat = " ".join(out.split())
    return [("а) справка: пример «--actor <РОЛЬ>», имени PROTO нет",
             rc == 0 and "напр. --actor <РОЛЬ> при" in flat and "--actor PROTO" not in flat,
             f"код {rc}; пример {'с заполнителем' if 'напр. --actor <РОЛЬ> при' in flat else 'ИНОЙ'}")]


# ⑱ check-retired-mechanism.py ────────────────────────────────────────────────
RETIRED_SOURCES = ("read-phoenix.py", "write-message.py", "unsaved.py", "backup-db.py", "export-channels.py",
                   "guard-scripts-drift.py", "guard-all.py", "read-messages.py", "save-phoenix.py")


def case_retired(st: Stand) -> list[tuple[str, bool, str]]:
    root = st.root / "retired-src"
    root.mkdir(parents=True, exist_ok=True)
    for name in RETIRED_SOURCES:
        (root / name).write_text("# источник без предписаний\n", encoding="utf-8")
    (root / "read-phoenix.py").write_text(
        "# de-live: push нельзя без слова владельца\n"
        "# db_falcon: push нельзя без слова владельца\n"
        "# DE/DWH: push нельзя без слова владельца\n"
        "# только чтение: push нельзя без слова владельца\n", encoding="utf-8")
    db = pack_db(st, "retired", roles_without_coordinator(),
                 [("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                   ("no-push-without-owner", "правило стенда", "coord", 4))])
    rc, out = sut(st, "retired", ["--db", str(db), "--root", str(root), "--only", "no-push-without-owner"])
    reported = sorted(int(n) for n in re.findall(r"read-phoenix\.py:(\d+)", out))
    return [("а) чужие имена (de-live · db_falcon · DE/DWH) находку НЕ гасят: строки 1–3 названы, код 1",
             rc == 1 and reported == [1, 2, 3] and "УЧАТ СНЯТОМУ" in out,
             f"код {rc}; названы строки {reported}"),
            ("б) общее «только чтение» гасит по-прежнему: строка 4 не названа",
             4 not in reported and rc in (0, 1), f"названы строки {reported}")]


# ⑲ контроль второй части ─────────────────────────────────────────────────────
def case_control_two(st: Stand, scripts_dir: Path) -> list[tuple[str, bool, str]]:
    sizes = {k: sut_file(scripts_dir, f).stat().st_size for k, f in SUT.items()}
    names = {COORD_NAME, ROLE_ENV.upper(), ROLE_FLAG.upper(), "AAA", "DDD", "CCC"}
    clash = names & set(OLD_LITERALS)
    return [
        ("а) все девять инструментов механизма найдены и непусты", all(v > 500 for v in sizes.values()),
         ", ".join(f"{k} {v} байт" for k, v in sizes.items())),
        ("б) схема пакета найдена, базы стенда строятся из неё",
         bool(st.schema_text) and "CREATE TABLE" in st.schema_text,
         f"{st.schema_name}, {len(st.schema_text)} знаков"),
        ("в) имена стенда не совпадают с прежними литералами — возврат литерала различим", not clash,
         f"пересечение {sorted(clash) or 'пусто'}"),
        ("г) у случаев было что считать: карточек табло ≥ 3, ролей новой сборки = 2, унесено записок = 3",
         EVIDENCE.get("dash_cards", 0) >= 3 and EVIDENCE.get("init_group_roles", 0) == 2
         and EVIDENCE.get("fold_moved", 0) == 3,
         f"карточек {EVIDENCE.get('dash_cards', 0)}; ролей сборки {EVIDENCE.get('init_group_roles', 0)}; "
         f"унесено {EVIDENCE.get('fold_moved', 0)}"),
    ]


def run_cases(tools_dir: Path, scripts_dir: Path, break_name: str | None) -> int:
    st = build_stand(tools_dir, scripts_dir, break_name)
    if break_name:
        num, _edits, what = BREAKS[break_name]
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{break_name}»: {what}")
        print(f"   ждём провала РОВНО: {' '.join(BREAK_FAILS[break_name])}")
    print(f"⚖️ испытываются инструменты из: {tools_dir}")
    print(f"⚖️ механизм со-работы (вторая часть) испытывается из: {scripts_dir}")
    for fname in sorted(TEMPLATE_ONLY & set(SUT.values())):
        src = sut_file(scripts_dir, fname)
        if src.parent != scripts_dir:
            print(f"   сборщик {fname} в контур не копируется — взят из образца: {src}")
    safe_case("① init-group-vnext.py: роли названы вызовом, умолчания нет", lambda: case_init(st, tools_dir))
    safe_case("② guard-printed-forms.py, observe(): без роли память не читается",
              lambda: case_guard_observe(st))
    safe_case("③ guard-printed-forms.py, run(): без роли — «не проверено», память не читается",
              lambda: case_guard_run(st))
    safe_case("④ guard-printed-forms.py, флаг --role: флаг → среда → координатор из данных → «не проверено»",
              lambda: case_guard_role_flag(st))
    safe_case("⑤ guard-printed-forms.py: имя навыка ответов — из данных контура",
              lambda: case_guard_skill(st))
    safe_case("⑥ measure-memory-search.py: роль руки — из вызова, без неё отказ",
              lambda: case_memory(st))
    safe_case("⑦ measure-tool-brevity.py: роль замера — из вызова, без неё отказ",
              lambda: case_brevity(st))
    safe_case("⑧ measure-rhythm.py: имена ролей — из таблицы roles, без базы образец с печатью",
              lambda: case_rhythm(st))
    # Девятый случай — контроль, а не различающий: он не отвечает ни на какую подстановку.
    safe_case("⑨ контроль: приёмке было на что смотреть", lambda: case_control(st, tools_dir), differ=False)
    # Вторая часть (Э3, Р2): имена ролей в инструментах механизма со-работы.
    safe_case("⑩ dashboard.py: карточки — из таблицы roles, координатор первым",
              lambda: case_dashboard(st))
    safe_case("⑪ init-group.py: роли и координатор называет вызов, умолчания нет",
              lambda: case_init_group(st))
    safe_case("⑫ messages-fold.py: рука переноса — из вызова, без неё для --apply отказ",
              lambda: case_fold(st))
    safe_case("⑬ set-rule.py: рука записи — флаг → среда → координатор из данных → отказ",
              lambda: case_set_rule(st))
    safe_case("⑭ set-registry.py: рука записи — тем же порядком; «кто установил» — рука",
              lambda: case_set_registry(st))
    safe_case("⑮ backlog.py: подсказка про закрытие issue называет координатора из данных",
              lambda: case_backlog_hint(st))
    safe_case("⑯ gordi-issue.py poll: подсказка «завести» несёт роль этого вызова",
              lambda: case_gordi_poll(st))
    safe_case("⑰ save-phoenix.py --help: пример руки — «<РОЛЬ>», а не PROTO",
              lambda: case_phoenix_help(st))
    safe_case("⑱ check-retired-mechanism.py: чужие имена не гасят находку",
              lambda: case_retired(st))
    safe_case("⑲ контроль второй части: приёмке было на что смотреть",
              lambda: case_control_two(st, scripts_dir), differ=False)
    print()
    if break_name:
        expected = set(BREAK_FAILS[break_name])
        actual = set(FAILED)
        if actual == expected:
            print(f"🧪 ожидание поломки «{break_name}» ПОДТВЕРДИЛОСЬ: провален ровно {' '.join(sorted(actual))}")
            mezo_stand.expected_break()
        else:
            print(f"⚠️ ожидание поломки «{break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали {' '.join(sorted(expected))}, "
                  f"провалено {' '.join(sorted(actual)) or 'ничего'}")
        print(f"🔴 НАРОЧНАЯ ПОЛОМКА — случаев {CASES}, различающих {DIFFER}, провалено {len(FAILED)}")
        return 1
    if FAILED:
        print(f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}; провалены: {' '.join(FAILED)}")
        return 1
    print(f"✅ РОЛИ ИЗ ДАННЫХ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}")
    return 0


def run_all_breaks(tools_dir: Path, scripts_dir: Path) -> int:
    root = mezo_stand.new("bite-roles-from-data-all-")
    env = mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8")
    confirmed = 0
    for name in BREAKS:
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--break", name,
                            "--tools-dir", str(tools_dir), "--scripts-dir", str(scripts_dir)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=900, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        ok = f"ожидание поломки «{name}» ПОДТВЕРДИЛОСЬ" in out
        confirmed += ok
        line = next((ln for ln in out.splitlines() if "ожидание поломки" in ln), "строки об ожидании нет")
        print(f"{'✅' if ok else '🔴'} {name}: {line.strip()}")
    print(f"поломок {len(BREAKS)}, ожидание подтвердилось {confirmed}")
    return 0 if confirmed == len(BREAKS) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Приёмка: имена ролей — из данных контура")
    ap.add_argument("--tools-dir", default=str(HERE), help="каталог с испытуемыми инструментами")
    ap.add_argument("--scripts-dir", default=None,
                    help="каталог с испытуемыми инструментами механизма со-работы (вторая часть); "
                         "по умолчанию — испытуемый каталог mezo_target (MEZO_SCRIPTS_ROOT или живой)")
    ap.add_argument("--break", dest="break_name", default=None, choices=[*BREAKS, "all"],
                    help="нарочная поломка на копии инструмента (all — все подряд)")
    a = ap.parse_args()
    tools_dir = Path(a.tools_dir).resolve()
    scripts_dir = Path(a.scripts_dir).resolve() if a.scripts_dir else mezo_target.scripts_root().resolve()
    try:
        if a.break_name == "all":
            return run_all_breaks(tools_dir, scripts_dir)
        return run_cases(tools_dir, scripts_dir, a.break_name)
    except NotRun as e:
        print(e)
        return 2        # отказ мерить: стенд сохраняется, но называется своими словами


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
