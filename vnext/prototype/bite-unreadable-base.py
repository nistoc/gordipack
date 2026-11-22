#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-unreadable-base.py — приёмка карточки #804: база контура недоступна С НАЧАЛА прогона.

ЗАЧЕМ. Приёмки, которые судят «база контура прогоном не тронута» по своим следам, обещают третий исход
«НЕ ПРОВЕРЕНО» своим кодом выхода 2, когда база не ответила. Замер STUD 22.11.2026 при повторной приёмке: исход
наступал, только если база переставала отвечать на ВТОРОМ вопросе о следах. Не читалась с начала — семь приёмок
из девяти выходили кодом 1: четыре трассировкой библиотеки, три отказом помощника, который винил копию во
временной папке, а не базу контура. Общий прогон приёмок читал это как «сломано», а не как «отказ мерить».
Теперь первый вопрос о следах задаёт mezo_stand.first_traces(): база не читается вовсе — «НЕ ПРОВЕРЕНО», код 2,
до стенда и до любого другого чтения; а помощник называет нечитаемый ИСТОЧНИК копии источником.

ЧТО ИСПЫТЫВАЕТСЯ. Приёмки этого каталога, задающие первый вопрос через first_traces(), и две приёмки со своей
проверкой (bite-correction-target.py, bite-pool-step0.py) — в ДОЧЕРНИХ процессах, на КОПИИ каталога приёмок
и в СВОЁМ контуре на стенде, где на месте базы по очереди лежит: текст вместо базы · ничего · пустой файл.
Настоящая база контура этой приёмкой не открывается и не ищется.

СЛУЧАИ (имена держатся: по ним сверяется состав упавших при нарочной поломке)
  Н0 перечень не слеп: каждая приёмка каталога, спрашивающая базу о следах через помощник, задаёт ПЕРВЫЙ вопрос
     через first_traces(); таких приёмок найдено не меньше одной; приёмка со СВОЕЙ функцией вопроса о следах
     обязана стоять в перечне своей проверки (OWN_CHECK) — иначе она здесь не испытывается и об этом молчит
  Н1 на месте базы текст        ⎫ у каждой испытуемой: код выхода 2, в выводе «НЕ ПРОВЕРЕНО», трассировки нет,
  Н2 файла базы нет             ⎬ ни одной строки случая (✅ или 🔴) — она не судила ничего
  Н3 файл базы пуст (0 байт)    ⎭
  Н4 ВСТРЕЧНЫЙ: читаемую базу ранний выход не останавливает — ни когда нужные таблицы есть, ни когда их нет
     (второе — вопрос ask_traces(), и что делать дальше, решает сама приёмка)
  Н5 помощник, источник копии не читается (текст вместо базы · файла нет): snapshot_db() и empty_db() отказывают
     кодом 2, отказ называет ИСТОЧНИК и его путь, цель не создана
  Н6 ВСТРЕЧНЫЙ к Н5: не база — ЦЕЛЬ: отказ называет цель, кодом 2 НЕ выходит, файл цели не тронут
НАРОЧНАЯ ПОЛОМКА (в КОПИЯХ mezo_stand.py на стенде; образец обязан найтись ровно один раз)
  ЛН1 ранний выход отключён — первый вопрос снова не останавливает прогон → третий исход теряют ровно приёмки,
      задающие вопрос через first_traces(); две приёмки со своей проверкой свой держат
ГРАНИЦА. Контур назван стенду переменной MEZO_CONTAINER. Когда она не названа, а файла базы нет или он пуст,
mezo_paths не находит самого контура и отказывает раньше любой приёмки («контейнер группы НЕ НАЙДЕН») — это
другой отказ, здесь он не судится. bite-update-tools-merge.py здесь не запускается: код 2 при недоступной базе
у неё наступает в конце прогона, после её собственных случаев, — мерка «ни одной строки случая» к ней неприменима.

    python <клон пакета>/vnext/prototype/bite-unreadable-base.py
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402 — из каталога самой приёмки: испытуется он же
import mezo_target  # noqa: E402 — каталог scripts берётся через общий выбор копии (карточка #682)

SELF = pathlib.Path(__file__).name
HELPER = HERE / "mezo_stand.py"
SCRIPTS = mezo_target.scripts_root()
# Иглы поиска собраны из частей: текст самой этой приёмки под них не попадает.
ASK = "mezo_stand." + "ask_traces("
FIRST = "mezo_stand." + "first_traces("
OWN_ASK = "def " + "ask_traces("             # своя функция вопроса о следах в теле приёмки
# Третий исход своей проверкой, без first_traces(): первая читает базу своим соединением, вторая судит
# своими функциями (карточка #483) и спрашивает mezo_stand.base_unreadable() до стенда.
OWN_CHECK = ("bite-correction-target.py", "bite-pool-step0.py")
CASE_LINE = re.compile(r"^\s*(?:✅|🔴)\s", re.MULTILINE)
EARLY_INTACT = "    why = base_unreadable(db)\n"
EARLY_BROKEN = '    why = ""\n'
GARBAGE = "это не база данных, а просто текст\n".encode("utf-8") * 64
BASE_FILES = (".db", ".db-wal", ".db-shm")
CHILD_LIMIT_S = 180
CRLF = chr(13) + chr(10)
OK = FAIL = 0


def case(name, ok, detail=""):
    global OK, FAIL
    print(("✅" if ok else "🔴"), name)
    for line in str(detail).splitlines():
        print(f"   {line}")
    OK, FAIL = OK + (1 if ok else 0), FAIL + (0 if ok else 1)
    return ok


def sources() -> dict:
    """Тексты приёмок каталога, кроме этой: {имя файла: текст}."""
    return {p.name: p.read_bytes().decode("utf-8", errors="replace")
            for p in sorted(HERE.glob("bite-*.py")) if p.name != SELF}


def lay_contour(stand, tag, helper_text=None):
    """Свой контур и копия каталога приёмок в каталоге стенда. Вернуть (контур, каталог приёмок, путь базы).

    Копируются каталог scripts (испытуемый) и файлы каталога приёмок; файлы баз не копируются. helper_text —
    текст помощника, который кладётся в ОБЕ копии вместо целого: так ставится нарочная поломка.
    """
    root = stand / tag
    contour = root / "contour"
    scripts = contour / ".mezosync" / "scripts"
    shutil.copytree(SCRIPTS, scripts, ignore=shutil.ignore_patterns("__pycache__", *("*" + s for s in BASE_FILES)))
    tools = root / "tools"
    tools.mkdir()
    for p in HERE.iterdir():
        if p.is_file() and not p.name.endswith(BASE_FILES):
            shutil.copy2(p, tools / p.name)
    if helper_text is not None:
        for place in (scripts / "mezo_stand.py", tools / "mezo_stand.py"):
            place.write_bytes(helper_text.encode("utf-8"))
    (root / "tmp").mkdir()
    return contour, tools, contour / ".mezosync" / "mezosync.db"


def lay_base(db, kind) -> None:
    """Положить на место базы контура: текст (garbage) · ничего (missing) · пустой файл (empty)."""
    for p in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        if p.exists():
            p.unlink()
    if kind == "garbage":
        db.write_bytes(GARBAGE)
    elif kind == "empty":
        db.write_bytes(b"")


def run_child(contour, tools, name):
    """Запустить приёмку-копию со средой стенда; вернуть (код выхода либо None, вывод целиком)."""
    tmp = str(contour.parent / "tmp")
    env = mezo_stand.stand_env(contour, PYTHONIOENCODING="utf-8", TEMP=tmp, TMP=tmp, TMPDIR=tmp,
                               MEZO_SCRIPTS_ROOT=str(contour / ".mezosync" / "scripts"))
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", str(tools / name)], env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=CHILD_LIMIT_S,
                           cwd=str(contour))
    except subprocess.TimeoutExpired:
        return None, f"(не кончилась за {CHILD_LIMIT_S} с)"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def judge(code, out) -> str:
    """Чего не хватило до третьего исхода с начала прогона; пустая строка — исход держится."""
    lacks = []
    if code != 2:
        lacks.append(f"код {code}, а не 2")
    if "НЕ ПРОВЕРЕНО" not in out:
        lacks.append("слов «НЕ ПРОВЕРЕНО» нет")
    if "Traceback" in out:
        lacks.append("трассировка")
    judged = len(CASE_LINE.findall(out))
    if judged:
        lacks.append(f"напечатано случаев: {judged}")
    return "; ".join(lacks)


def round_of(contour, tools, db, kind, names) -> dict:
    """Один круг: база заданного вида, приёмки по одной. Вернуть {имя: (чего не хватило, последняя строка)}."""
    lay_base(db, kind)
    got = {}
    for name in names:
        code, out = run_child(contour, tools, name)
        lines = [s for s in out.splitlines() if s.strip()]
        got[name] = (judge(code, out), (lines[-1] if lines else "(вывода нет)")[:200])
    return got


def refusal(func, src, dst):
    """Позвать функцию копии помощника; вернуть (код отказа, напечатанное).

    Код — то, с чем функция вышла: число или текст отказа; None — отказа не было вовсе; исключение
    библиотеки вместо отказа возвращается текстом «ИСКЛЮЧЕНИЕ …» — случай его называет, а не падает на нём.
    """
    said = io.StringIO()
    try:
        with contextlib.redirect_stdout(said):
            func(src, dst)
    except SystemExit as e:
        return e.code, said.getvalue()
    except Exception as e:  # noqa: BLE001 — трассировка вместо отказа и есть то, что случай обязан назвать
        return f"ИСКЛЮЧЕНИЕ {type(e).__name__}: {e}", said.getvalue()
    return None, said.getvalue()


def main() -> int:
    print("=" * 100)
    print("ПРИЁМКА: база контура недоступна с начала прогона — «НЕ ПРОВЕРЕНО» кодом 2, а не провал — карточка #804")
    print(f"⚖️ испытуется: помощник {HELPER} и приёмки каталога {HERE}")
    print("=" * 100)
    lacking = [f for f in ("first_traces", "base_unreadable") if not hasattr(mezo_stand, f)]
    if lacking:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет {', '.join(lacking)} — испытывать нечего")
        return 2

    texts = sources()
    askers = sorted(n for n, t in texts.items() if ASK in t)
    firsts = sorted(n for n, t in texts.items() if FIRST in t)
    late = [n for n in askers if n not in firsts]
    own_askers = sorted(n for n, t in texts.items() if OWN_ASK in t)
    unlisted = [n for n in own_askers if n not in OWN_CHECK]
    case("Н0 перечень не слеп: кто спрашивает базу о следах, первый вопрос задаёт через first_traces()",
         bool(firsts) and not late and not unlisted,
         f"спрашивают о следах через помощник: {len(askers)} · через first_traces(): {len(firsts)} · "
         f"со своей функцией вопроса: {len(own_askers)}"
         + (f"\nБЕЗ раннего выхода: {', '.join(late)}" if late else "")
         + (f"\nсо своей функцией вопроса, но НЕ в перечне своей проверки: {', '.join(unlisted)}" if unlisted else ""))
    tested = firsts + [n for n in OWN_CHECK if n in texts and n not in firsts]
    if not tested:
        print("\n🔴 ИТОГ: испытывать некого — ни одной приёмки с first_traces() в каталоге не найдено")
        return 1

    stand = mezo_stand.new("bite-unreadable-base-")
    contour, tools, db = lay_contour(stand, "whole")
    for tag, kind, title in (("Н1", "garbage", "на месте базы текст"),
                             ("Н2", "missing", "файла базы нет"),
                             ("Н3", "empty", "файл базы пуст (0 байт)")):
        got = round_of(contour, tools, db, kind, tested)
        bad = {n: v for n, v in got.items() if v[0]}
        case(f"{tag} {title}: у каждой испытуемой «НЕ ПРОВЕРЕНО», код 2, без трассировки, ни одного случая",
             not bad, f"испытуемых {len(tested)}, третий исход держат {len(tested) - len(bad)}"
             + "".join(f"\n{n}: {lacks} · последняя строка: {last}" for n, (lacks, last) in bad.items()))
    lay_base(db, "missing")

    # Н4 — встречный: читаемая база раннего выхода не вызывает.
    good = stand / "good.db"
    con = sqlite3.connect(str(good))
    con.execute("CREATE TABLE backlog (role TEXT)")
    con.commit()
    con.close()
    answers, stopped = [], []
    for need in (("backlog",), ("no_such_table",)):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                answers.append(mezo_stand.first_traces(good, ("ZZNOSUCHMARK",), need))
        except SystemExit:
            stopped.append(need[0])
    reads = mezo_stand.base_unreadable(good) == ""
    case("Н4 ВСТРЕЧНЫЙ: читаемую базу ранний выход не останавливает — и когда нужных таблиц в ней нет",
         not stopped and reads and len(answers) == 2 and answers[0] == ({}, "")
         and answers[1][0] is None and "no_such_table" in answers[1][1],
         f"остановлено на: {stopped or 'ничём'} · база названа читаемой: {'да' if reads else 'НЕТ'} · "
         f"ответы: {answers}")

    # Н5 — источник копии не читается: отказ об источнике, код 2, цель не создана.
    broken = stand / "source-is-text.db"
    broken.write_bytes(GARBAGE)
    absent = stand / "source-is-absent.db"
    wrong = []
    for func in (mezo_stand.snapshot_db, mezo_stand.empty_db):
        for src in (broken, absent):
            dst = stand / f"copy-{func.__name__}-{src.stem}.db"
            code, said = refusal(func, src, dst)
            lacks = []
            if code != 2:
                lacks.append(f"код {code!r}, а не 2")
            if "ИСТОЧНИК" not in said or str(src) not in said:
                lacks.append("источник и его путь не названы")
            if "цель существует" in said:
                lacks.append("обвинена цель")
            if dst.exists():
                lacks.append("цель создана")
            if lacks:
                wrong.append(f"{func.__name__}, {src.name}: {'; '.join(lacks)}")
    case("Н5 источник копии не читается: snapshot_db() и empty_db() называют ИСТОЧНИК, код 2, цель не создана",
         not wrong, "опытов 4 (две функции × текст вместо базы и файла нет)"
         + "".join(f"\n{w}" for w in wrong))

    # Н6 — встречный: не база ЦЕЛЬ. Отказ о цели прежний: текстом, не кодом 2; файл цели не тронут.
    wrong = []
    for func in (mezo_stand.snapshot_db, mezo_stand.empty_db):
        dst = stand / f"target-is-text-{func.__name__}.db"
        dst.write_bytes(GARBAGE)
        code, said = refusal(func, good, dst)
        lacks = []
        if not isinstance(code, str) or "цель существует" not in code or str(dst) not in code:
            lacks.append(f"отказ о цели не тот: {str(code)[:120]!r}")
        if "ИСТОЧНИК не открывается" in said + str(code):
            lacks.append("обвинён источник")
        if dst.read_bytes() != GARBAGE:
            lacks.append("файл цели изменён")
        if lacks:
            wrong.append(f"{func.__name__}: {'; '.join(lacks)}")
    case("Н6 ВСТРЕЧНЫЙ: не база ЦЕЛЬ — отказ называет цель, кодом 2 не выходит, файл цели не тронут",
         not wrong, "опытов 2 (две функции)" + "".join(f"\n{w}" for w in wrong))

    # ЛН1 — нарочная поломка в копиях помощника: ранний выход отключён.
    title = "ЛН1 ПОЛОМКА «ранний выход отключён» лишает третьего исхода ровно тех, кто спрашивает через first_traces()"
    text = HELPER.read_bytes().decode("utf-8").replace(CRLF, "\n")
    if text.count(EARLY_INTACT) != 1:
        case(title, False, "образец поломки не найден ровно один раз — помощник менялся, правь приёмку")
    else:
        b_contour, b_tools, b_db = lay_contour(stand, "break1", text.replace(EARLY_INTACT, EARLY_BROKEN, 1))
        got = round_of(b_contour, b_tools, b_db, "garbage", tested)
        lay_base(b_db, "missing")
        fell = sorted(n for n, v in got.items() if v[0])
        case(title, fell == firsts, f"потеряли: {fell or 'ни одна'}\nждали:    {firsts}"
             + "".join(f"\n{n}: {got[n][0] or 'третий исход держит'}" for n in sorted(set(fell) ^ set(firsts))))

    total = OK + FAIL
    print()
    if FAIL:
        print(f"🔴 ИТОГ: прошло {OK} из {total}")
        return 1
    print(f"✅ ИТОГ: {OK} из {total}")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
