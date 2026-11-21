#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-guard-verify-line.py — приёмка карточки #821: общий прогон проверок (guard-all.py) зовёт команду
scripts/verify-install.py и печатает её исход ОДНОЙ строкой, не меняя код выхода общего прогона.

ЗАЧЕМ. Команда сверяет тела установленных файлов с записью установки (карточка #819). Запись хранит
отпечаток версии ПАКЕТА, поэтому правка контура, принятая установщиком (--accept-merge), выглядит для сверки
как порча. Проваливающая проверка сразу сломала бы общий прогон соседям с такими правками — поэтому исход
сверки печатается строкой, а код выхода и число провалов остаются прежними.

СТЕНД. Приёмка собирает свой контур во временном каталоге: рабочие скрипты (копия испытуемых), второй каталог
установки (копия каталога приёмок), объявленный ключом prototype_install_dir файла путей, база с таблицей meta
и записью установки по всем файлам обоих каталогов. Живой контур не читается и не пишется; без стенда
(mezo_stand) приёмка отказывается работать.

КАК СУДИТСЯ РОВНО НОВАЯ СТРОКА. Каждое состояние контура гоняется ДВАЖДЫ: общий прогон со снятой проверкой
(--skip verify-install) и с включённой. Сличаются: код выхода равен; все остальные строки вывода равны; отличие —
одна строка сверки (в прогоне со снятой — одна строка «⏭️ verify-install — пропущен по --skip»), а число
проверок в итоге больше ровно на одну. Всё, что общий прогон печатает сам по себе, из сличения уходит равным.

СЛУЧАИ (имена держатся: по ним сверяется состав упавших при нарочных поломках)
  Г1 совпало: строка со словом «совпало» и числом файлов, равным числу пар записи
  Г2 расходится: один значащий байт в установленном файле; строка несёт признак предупреждения, в ней нет
     знака прохода и слов «совпало», «прошло»; код выхода общего прогона прежний
  Г3 нечем сверять: запись установки удалена; признак предупреждения, причина из вывода команды, ни знака
     прохода, ни слов «совпало», «прошло»
  Г4 команды нет рядом: строка «сверка тел НЕ ВЫПОЛНЕНА … это не ноль», без знака прохода
  Г5 код 0 при переименовании: команда вернула 0, но один файл лежит под другим именем — строка несёт признак
     предупреждения и число таких файлов, слова «совпало» без оговорки в ней нет
  Г6 код 0 без итога: файл команды пуст — он кончается кодом 0 и не печатает ничего; строка «сверка тел
     НЕ ВЫПОЛНЕНА … это не ноль», без знака прохода: код 0 сам по себе сверкой не считается
НАРОЧНЫЕ ПОЛОМКИ (в КОПИИ guard-all.py на стенде; якорь обязан найтись ровно один раз)
  ЛГ1 расхождение проваливает общий прогон (строка сверки идёт через check с провалом) → Г2
  ЛГ2 «нечем сверять» напечатано словом прохода                                       → Г3
  ЛГ3 переименование не названо в строке общего прогона                               → Г5
  ЛГ4 код 0 без итога команды напечатан знаком прохода и словом «совпало»             → Г6

    MEZO_SCRIPTS_ROOT=<клон пакета>/scripts python <клон пакета>/vnext/prototype/bite-guard-verify-line.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402
import mezo_stand  # noqa: E402

if not hasattr(mezo_stand, "stand_env"):
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет stand_env (общий помощник среды стенда) — "
             "приёмка работает только на стенде; возьми помощник из той же версии пакета. Код 2 — отказ.")

GUARD_ALL = mezo_target.script("guard-all.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

OK = FAIL = 0
CHECK_NAME = "verify-install"
SECOND_PREFIX = "prototype-dir::/"          # приставка ключа файла второго каталога (своя, независимая от команды)
# в обоих прогонах каждого состояния сняты проверки, которые долго идут и к предмету не относятся; «замороженные md»
# на стенде без каталога координации провалена, а нужен прошедший опорный прогон
COMMON_SKIP = ["drift", "память", "utc", "чтение ленты", "замороженные md"]


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail and not cond:
        for line in str(detail).splitlines():
            print(f"   {line}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def own_digest(data: bytes) -> str:
    """Независимая от команды сборка отпечатка для записи установки: опора приёмки, а не испытуемое."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


if not (GUARD_ALL.parent / "verify-install.py").is_file():
    print(f"🔴 команды нет: {GUARD_ALL.parent / 'verify-install.py'} не найден — случаи Г1–Г6 и поломки ЛГ1–ЛГ4 не пройдены, испытывать нечего")
    print("\n🔴 ИТОГ: 0 из 10")
    sys.exit(mezo_stand.finish(1))

STAND = mezo_stand.new("bite-guard-verify-line-")
live_mezo = mezo_paths.container_root(__file__) / ".mezosync"
c_root = STAND / "contour"
SCRIPTS = c_root / ".mezosync" / "scripts"
SECOND = c_root / "vnext-tools"
shutil.copytree(GUARD_ALL.parent, SCRIPTS, ignore=shutil.ignore_patterns("__pycache__"))
shutil.copytree(pathlib.Path(__file__).resolve().parent, SECOND, ignore=shutil.ignore_patterns("__pycache__"))
DB = mezo_stand.empty_db(live_mezo / "mezosync.db", c_root / ".mezosync" / "mezosync.db")
STAND_ROLES = ("COORD", "PROTO")
mezo_stand.seed_roles(DB, STAND_ROLES)
con = sqlite3.connect(str(DB))
with con:
    con.execute("DELETE FROM cross_links")      # копия не ходит к настоящим соседям
con.close()

# два своих файла: их правит и переименовывает приёмка, не трогая то, что исполняется
FIXTURE_A = SCRIPTS / "fixture-verify-a.py"
FIXTURE_B = SCRIPTS / "fixture-verify-b.py"
FIXTURE_A.write_bytes(b"# fixture a\nA = 1\n")
FIXTURE_B.write_bytes(b"# fixture b\nB = 1\n")
PATHS_FILE = c_root / ".mezosync" / "local" / "paths.json"
PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
PATHS_FILE.write_text(json.dumps({"prototype_install_dir": SECOND.resolve().as_posix()}), encoding="utf-8")


def record_of_disk() -> dict:
    """Запись установки по тому, что лежит на диске СЕЙЧАС: первый каталог рекурсивно, второй сверху."""
    rec = {}
    for p in sorted(SCRIPTS.rglob("*")):
        if p.is_file() and "__pycache__" not in p.relative_to(SCRIPTS).parts:
            rec[p.relative_to(SCRIPTS).as_posix()] = own_digest(p.read_bytes())
    for p in sorted(SECOND.glob("*")):
        if p.is_file():
            rec[SECOND_PREFIX + p.name] = own_digest(p.read_bytes())
    return rec


def db_exec(sql, args=()):
    c = sqlite3.connect(str(DB))
    with c:
        c.execute(sql, args)
    c.close()


def write_record(rec: dict) -> None:
    db_exec("INSERT OR REPLACE INTO meta (key, value) VALUES ('template_files_sha', ?)", (json.dumps(rec),))


write_record(record_of_disk())
PAIRS = len(record_of_disk())
C_GUARD = SCRIPTS / "guard-all.py"
C_GUARD_BYTES = C_GUARD.read_bytes()
COMMAND = SCRIPTS / "verify-install.py"
COMMAND_BYTES = COMMAND.read_bytes()


def full_run(skip_check: bool, guard_bytes: bytes | None = None) -> tuple[int, list[str], str]:
    """Общий прогон копии → (код, строки вывода, вывод целиком). guard_bytes — текст guard-all.py с нарочной поломкой."""
    saved_record = None
    if guard_bytes is not None:
        # Сам guard-all.py — файл записи установки: прогон с его поломанной копией сверка тел честно назвала бы расхождением.
        # Поэтому на время прогона в записи стоит отпечаток поломанной копии; остальные пары записи (в том числе изменённый
        # состоянием файл) не трогаются, после прогона запись возвращается как была.
        con = sqlite3.connect(str(DB))
        row = con.execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()
        con.close()
        if row is not None:                      # состояние «запись удалена» — править нечего
            saved_record = row[0]
            patched = json.loads(saved_record)
            patched["guard-all.py"] = own_digest(guard_bytes)
            db_exec("UPDATE meta SET value=? WHERE key='template_files_sha'", (json.dumps(patched),))
        C_GUARD.write_bytes(guard_bytes)
    try:
        skip = COMMON_SKIP + ([CHECK_NAME] if skip_check else [])
        r = subprocess.run([sys.executable, str(C_GUARD), "--skip", ",".join(skip)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900, cwd=str(c_root),
                           env=mezo_stand.stand_env(c_root, PYTHONIOENCODING="utf-8"))
    finally:
        if guard_bytes is not None:
            C_GUARD.write_bytes(C_GUARD_BYTES)
            if saved_record is not None:
                db_exec("UPDATE meta SET value=? WHERE key='template_files_sha'", (saved_record,))
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out.splitlines(), out


SUMMARY = re.compile(r"^(.*)\((\d+) проверок\)\s*$")


def split_summary(line: str):
    m = SUMMARY.match(line)
    return (m.group(1), int(m.group(2))) if m else (line, None)


def pair_compare(off: tuple, on: tuple) -> tuple[list[str], list[str]]:
    """Сличение двух прогонов одного состояния. Отдаёт (строки сверки из прогона с включённой, замечания).
    Замечание — всё, в чём прогоны отличаются кроме одной строки сверки."""
    rc_off, lines_off, _ = off
    rc_on, lines_on, _ = on
    notes = []
    if rc_on != rc_off:
        notes.append(f"код выхода общего прогона разный: со снятой проверкой {rc_off}, с включённой {rc_on}")
    mine = [l for l in lines_on if "сверка тел" in l]
    if len(mine) != 1:
        notes.append(f"в прогоне с включённой проверкой строк о сверке тел {len(mine)}, ждали одну")
    skip_line = f"⏭️ {CHECK_NAME} — пропущен по --skip"
    skips = [l for l in lines_off if l == skip_line]
    if len(skips) != 1:
        notes.append(f"в прогоне со снятой проверкой строк пропуска {len(skips)}, ждали одну")
    rest_off = [l for l in lines_off if l != skip_line]
    rest_on = [l for l in lines_on if "сверка тел" not in l]
    if len(rest_off) != len(rest_on):
        notes.append(f"число остальных строк разное: {len(rest_off)} и {len(rest_on)}")
    else:
        for a, b in zip(rest_off, rest_on):
            if a == b:
                continue
            ta, na = split_summary(a)
            tb, nb = split_summary(b)
            if na is not None and nb is not None and ta == tb and nb == na + 1:
                continue            # итог: число проверок больше ровно на одну, имена те же
            notes.append(f"остальная строка отличается: «{a[:90]}» и «{b[:90]}»")
            break
    return mine, notes


def no_pass_words(line: str) -> list[str]:
    bad = []
    if "✅" in line:
        bad.append("знак прохода")
    low = line.lower()
    for w in ("совпало", "прошло"):
        if w in low:
            bad.append(f"слово «{w}»")
    return bad


def judge(name: str, off: tuple, on: tuple) -> tuple[bool, str]:
    """Случай Г1–Г6 по двум прогонам состояния."""
    mine, notes = pair_compare(off, on)
    line = mine[0] if len(mine) == 1 else ""
    if line:
        if name == "Г1":
            m = re.search(r"сверено файлов:? (\d+)", line)
            if not line.lstrip().startswith("✅") or "совпало" not in line or not m or int(m.group(1)) != PAIRS:
                notes.append(f"ждали «✅ … совпало … {PAIRS}»: {line[:120]}")
        elif name == "Г2":
            if not line.lstrip().startswith("⚠️") or "РАСХОДИТСЯ" not in line:
                notes.append(f"ждали «⚠️ … РАСХОДИТСЯ»: {line[:120]}")
            notes += [f"в строке {w}" for w in no_pass_words(line)]
        elif name == "Г3":
            if not line.lstrip().startswith("⚠️") or "нечем сверять" not in line or "записи установки нет" not in line:
                notes.append(f"ждали «⚠️ … нечем сверять — … записи установки нет»: {line[:120]}")
            notes += [f"в строке {w}" for w in no_pass_words(line)]
        elif name == "Г4":
            if not line.lstrip().startswith("сверка тел НЕ ВЫПОЛНЕНА") or "это не ноль" not in line:
                notes.append(f"ждали «сверка тел НЕ ВЫПОЛНЕНА … это не ноль»: {line[:120]}")
            notes += [f"в строке {w}" for w in no_pass_words(line)]
        elif name == "Г5":
            m = re.search(r"но (\d+) файл", line)
            if (not line.lstrip().startswith("⚠️") or not m or int(m.group(1)) != 1 or "под другим именем" not in line
                    or "файла под именем записи нет" not in line):
                notes.append(f"ждали «⚠️ … тела совпали, но 1 файлов лежат под другим именем — файла под именем записи нет»: {line[:140]}")
            if "совпало" in line.lower() or "✅" in line:
                notes.append("в строке слово «совпало» или знак прохода без оговорки")
        elif name == "Г6":
            if not line.lstrip().startswith("сверка тел НЕ ВЫПОЛНЕНА") or "код 0" not in line or "это не ноль" not in line:
                notes.append(f"ждали «сверка тел НЕ ВЫПОЛНЕНА: команда вернула код 0 … это не ноль»: {line[:140]}")
            notes += [f"в строке {w}" for w in no_pass_words(line)]
    return not notes, f"строка: {line[:200]}\n" + "\n".join(notes)


# ═══ СОСТОЯНИЯ КОНТУРА: применить → прогнать → вернуть ═══
class State:
    def __init__(self, name):
        self.name = name

    def apply(self):
        pass

    def undo(self):
        pass


class StateG1(State):
    pass


class StateG2(State):
    def apply(self):
        data = FIXTURE_A.read_bytes()
        assert data.count(b"A = 1") == 1
        FIXTURE_A.write_bytes(data.replace(b"A = 1", b"A = 2"))

    def undo(self):
        FIXTURE_A.write_bytes(b"# fixture a\nA = 1\n")


class StateG3(State):
    def apply(self):
        self.saved = sqlite3.connect(str(DB)).execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()[0]
        db_exec("DELETE FROM meta WHERE key='template_files_sha'")

    def undo(self):
        db_exec("INSERT OR REPLACE INTO meta (key, value) VALUES ('template_files_sha', ?)", (self.saved,))


class StateG4(State):
    def apply(self):
        COMMAND.unlink()

    def undo(self):
        COMMAND.write_bytes(COMMAND_BYTES)


class StateG5(State):
    def apply(self):
        FIXTURE_B.rename(SCRIPTS / "fixture-verify-b-renamed.py")

    def undo(self):
        (SCRIPTS / "fixture-verify-b-renamed.py").rename(FIXTURE_B)


class StateG6(State):
    def apply(self):
        COMMAND.write_bytes(b"")          # пустой файл: интерпретатор кончает его кодом 0 и не печатает ничего

    def undo(self):
        COMMAND.write_bytes(COMMAND_BYTES)


STATES = [StateG1("Г1"), StateG2("Г2"), StateG3("Г3"), StateG4("Г4"), StateG5("Г5"), StateG6("Г6")]
TITLES = {
    "Г1": "совпало: строка со словом «совпало» и числом файлов, равным числу пар записи",
    "Г2": "расходится: один значащий байт — строка с признаком предупреждения, без знака прохода и слов «совпало», «прошло»; код выхода прежний",
    "Г3": "нечем сверять: запись установки удалена — признак предупреждения и причина команды, без знака прохода; код выхода прежний",
    "Г4": "команды нет рядом: «сверка тел НЕ ВЫПОЛНЕНА … это не ноль», без знака прохода; код выхода прежний",
    "Г5": "код 0 при переименовании: строка с признаком предупреждения и числом файлов под другим именем, без «совпало» без оговорки",
    "Г6": "код 0 без итога команды (файл команды пуст): «сверка тел НЕ ВЫПОЛНЕНА … это не ноль», без знака прохода; код выхода прежний",
}

# ═══ НАРОЧНЫЕ ПОЛОМКИ — в КОПИИ guard-all.py на стенде; якорь обязан найтись ровно один раз ═══
GUARD_TEXT = C_GUARD_BYTES.decode("utf-8").replace("\r\n", "\n")


def replaced(text: str, pairs, tag: str) -> str | None:
    for old, new in pairs:
        if text.count(old) != 1:
            print(f"⛔ поломка {tag} не наложилась: строка найдена {text.count(old)} раз(а), нужно ровно 1: {old!r}")
            return None
        text = text.replace(old, new)
    return text


BREAKS = {
    "ЛГ1": ("расхождение проваливает общий прогон", "Г2",
            [('            print(f"⚠️ сверка тел: РАСХОДИТСЯ — {tail}', '            check("verify-install", False, "расхождение")  # ПОЛОМКА ЛГ1\n            print(f"⚠️ сверка тел: РАСХОДИТСЯ — {tail}')]),
    "ЛГ2": ("«нечем сверять» напечатано словом прохода", "Г3",
            [('            print(f"⚠️ сверка тел: нечем сверять — {reason}")', '            print(f"✅ сверка тел: совпало — нечем сверять — {reason}")  # ПОЛОМКА ЛГ2')]),
    "ЛГ3": ("переименование не названо в строке общего прогона", "Г5",
            [("            if v_renamed:\n", "            if False:  # ПОЛОМКА ЛГ3\n")]),
    "ЛГ4": ("код 0 без итога команды напечатан знаком прохода", "Г6",
            [('                print(f"сверка тел НЕ ВЫПОЛНЕНА: команда вернула код 0,',
              '                print(f"✅ сверка тел установленных файлов: совпало — команда вернула код 0,')]),
}
BROKEN_TEXT = {}
for tag, (what, target, pairs) in BREAKS.items():
    patched = replaced(GUARD_TEXT, pairs, tag)
    BROKEN_TEXT[tag] = patched.encode("utf-8") if patched is not None else None

print("---- общие прогоны на копии контура (на каждое состояние: два прогона и четыре на поломках) ----")
base_ok = {}
broken_failed = {tag: set() for tag in BREAKS}
for st in STATES:
    st.apply()
    try:
        off = full_run(True)
        on = full_run(False)
        ok, detail = judge(st.name, off, on)
        base_ok[st.name] = (ok, detail)
        for tag, blob in BROKEN_TEXT.items():
            if blob is None:
                broken_failed[tag].add("не наложилась")
                continue
            on_b = full_run(False, guard_bytes=blob)
            # опорный прогон со снятой проверкой в КОПИИ с поломкой тот же, что в целой: поломка живёт только в ветке сверки
            ok_b, _ = judge(st.name, off, on_b)
            if not ok_b:
                broken_failed[tag].add(st.name)
    finally:
        st.undo()

for st in STATES:
    ok, detail = base_ok[st.name]
    case(f"{st.name} {TITLES[st.name]}", ok, detail)
for tag, (what, target, _) in BREAKS.items():
    failed = broken_failed[tag]
    case(f"{tag} ПОЛОМКА «{what}» валит ровно {target}", failed == {target},
         f"упали: {sorted(failed) or 'ни один'} · ждали: [{target!r}]")

total = len(STATES) + len(BREAKS)
print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {total}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
