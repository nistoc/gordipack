#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: имена флагов и справка backlog.py; подсказка при чужом имени довода --role/--actor.

Предмет 1 (карточка #409) — путь ③: backlog.py при --role в командах исполнителя и lease.py
при --actor отказывают С ПОДСКАЗКОЙ верного имени, а не голым «unrecognized
arguments». Прежние верные вызовы обоих инструментов не тронуты.

Предмет 2 (набор TRACK-GORDI-CORE, этап Э3, работа Р6; заявка пакета №26) — справка
`backlog.py --help`: у каждой из девяти подкоманд есть описание; в печатаемой справке нет
номеров карточек контура-донора; флаг одного смысла с разными именами у разных подкоманд
принимает оба имени, и второе даёт тот же результат, что прежнее.

Предмет 3 (набор TRACK-GORDI-CORE, этап Э3, заявка пакета №26, п. в) — подкоманда
`backlog.py show` при роли вместо номера, при номере-не-числе и без номера отказывает СЛОВАМИ
(что ожидалось, что получено, как сделать то, что, вероятно, хотели), а не голым отказом
разбора аргументов «invalid int value». Верный вызов (show <номер>), справка show и другие
подкоманды не тронуты.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (судов 29, падений жду 0):
  ①  backlog claim --role ..... ОТКАЗ, подсказка несёт «--actor» и «карточка #409»
  ②  lease take --actor ....... ОТКАЗ, подсказка несёт «--role» и «карточка #409»
  ③  встречный: backlog claim --actor на стенде — работает (rc 0)
  ④  встречный: lease take --role на стендовой базе — работает (rc 0)
  ⑤  встречный: backlog add --role на стенде — работает (там --role ЗАКОНЕН:
     владелец карточки; подсказка на add не распространяется)
  Р1 подсказка backlog ослеплена → ① на копии: отказ есть (argparse сам
     требует --actor и потому печатает это слово), но ПОДСКАЗКИ со ссылкой
     «карточка #409» нет — роль снова гадает. Судится исчезновение подсказки,
     не слова «--actor»: голый argparse-отказ его содержит (замер первого прогона)
  ⑥  у каждой из 9 подкоманд есть справка: строка в общем списке `--help` И описание
     в собственной справке (`<подкоманда> --help`)
  ⑦  в печатаемой справке (общей и девяти подкоманд) нет «#цифры», «П②» и кружочных цифр
  ⑧  каждое ВТОРОЕ имя флага одного смысла (criterion: --done-when, --done-when-file)
     принимается и даёт тот же результат, что прежнее (--text, --text-file): код возврата,
     печать, значение в базе и событие в истории совпадают
  Р2  у подкоманды comment убрана строка help= → падает РОВНО ⑥ (не ⑦, не ⑧)
  Р2б у подкоманды show описание превращено в эпилог → падает РОВНО ⑥
  Р3  в справку edit возвращён «(карточка #452)» → падает РОВНО ⑦ (⑥ держится: справка есть)
  Р4  у criterion убрано имя --done-when → падает РОВНО ⑧, и называет именно его
  Р4б у criterion убрано имя --done-when-file → падает РОВНО ⑧, и называет именно его
  ⑨  show --role X ............ ОТКАЗ словами: «нет роли», «Получено: --role X», подсказка list --role X
  ⑩  show <номер> --role X .... ОТКАЗ словами: роль лишняя, номер назван верным, подсказка show <номер>
  ⑪  show abc ................. ОТКАЗ словами: «не число», подсказка list --role abc
  ⑫  show (без номера) ........ ОТКАЗ словами: «не указан номер», подсказка list --role <РОЛЬ>
      во всех четырёх: код не ноль и нет слов голого отказа разбора аргументов
      («invalid int value», «usage:», «error:», «arguments are required»)
  ⑬  встречный: show <настоящий номер> на стенде работает (код 0, карточка напечатана)
  ⑭  встречный: show --help печатает справку, а не отказ
  ⑮  встречный: list --role X (там --role законен) работает как прежде
  Р5  снят перехват (прежний разбор без слов) → падают РОВНО ⑨⑩⑪⑫; встречные ⑬⑭⑮ держатся
  Р5а в подсказке отказа ⑨ потеряна роль → РОВНО ⑨
  Р5б в отказе ⑩ нет слов «номер верный» → РОВНО ⑩
  Р5в в подсказке отказа ⑪ потеряно слово пользователя → РОВНО ⑪
  Р5г вызов без номера пропущен к голому отказу → РОВНО ⑫
  Р5д верный номер больше не пропускается → РОВНО ⑬ (встречный)
  Р5е справка show больше не пропускается → РОВНО ⑭ (встречный)
  Р5ж перехват распространён на все подкоманды → РОВНО ⑮ (встречный)
  Каждая нарочная поломка делается на КОПИИ backlog.py в каталоге стенда; живой файл не
  трогается. «Ровно» значит: из трёх проверок ⑥⑦⑧ на сломанной копии падает одна, та, что названа.

Зовут так:
    python <КОНТУР>/vnext-tools/bite-actor-role-hint.py
⚠️ при живом объявлении о правке этих инструментов зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import os
import pathlib
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

import mezo_stand

BACKLOG = mezo_target.script("backlog.py")
LEASE = mezo_target.script("lease.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

TABLES = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status", "tool_leases", "audit_log",
           "backlog_tests")   # backlog_tests читает show (тесты карточки): без неё show на стенде падает

# Девять подкоманд backlog.py (порядок как в справке).
SUBCOMMANDS = ("add", "criterion", "list", "show", "status", "claim", "comment", "edit", "queue")

# Ссылка на внутренний пункт контура в печатаемой справке: «#123», «П②», одиночная
# кружочная цифра. Читатель справки этих пунктов не имеет.
NUMBER_MARK = re.compile(r"#\s?\d|П[①-⑳]|[①-⑳]")

# Флаги ОДНОГО смысла с разными именами: (подкоманда, прежнее имя, второе имя, «строка» | «файл»).
# Смысл у пары один — «текст критерия приёмки» (у add он зовётся --done-when). Пара --role/--actor
# сюда НЕ входит: --role — ЧЬЯ карточка, --actor — КТО делает вызов, смыслы разные.
SYNONYMS = (
    ("criterion", "--text", "--done-when", "строка"),
    ("criterion", "--text-file", "--done-when-file", "файл"),
)

# Справка печатается в ширину строки, не зависящую от окна; кодировка вывода закреплена.
BASE_ENV = {"PYTHONIOENCODING": "utf-8", "COLUMNS": "100"}


def clean_db(path: pathlib.Path) -> None:
    live_con = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    ddl = [r[0] for r in live_con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name IN "
        f"({','.join('?' * len(TABLES))})", TABLES)]
    live_con.close()
    if len(ddl) != len(TABLES):
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: {len(ddl)} таблиц из {len(TABLES)}")
    con = sqlite3.connect(str(path))
    for s in ddl:
        con.execute(s)
    con.commit()
    con.close()


def call_tool(tool: pathlib.Path, *args: str, extra_env=None) -> tuple[int, str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([sys.executable, str(tool), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def weaken(live_path, out_dir, anchor, replacement):
    text = live_path.read_bytes().decode("utf-8")
    if text.count(anchor) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь найден {text.count(anchor)} раз")
    copy_path = out_dir / live_path.name
    copy_path.write_bytes(text.replace(anchor, replacement).encode("utf-8"))
    return copy_path


def fetch_help(tool, extra_env=None) -> dict:
    """Печатная справка: общая и девяти подкоманд → {метка: (код возврата, текст)}."""
    env = dict(BASE_ENV)
    if extra_env:
        env.update(extra_env)
    pages = {}
    for label, names in [("общая", ())] + [(name, (name,)) for name in SUBCOMMANDS]:
        rc, out = call_tool(tool, *names, "--help", extra_env=env)
        pages[label] = (rc, out.replace("\r\n", "\n"))
    return pages


def check_help_present(pages: dict) -> tuple[bool, str, list]:
    """⑥: у каждой подкоманды есть строка в общем списке И описание в своей справке."""
    bad = []
    rc_top, top = pages["общая"]
    if rc_top != 0:
        return False, f"общая справка не напечаталась (код {rc_top}): {top[:200]}", ["общая"]
    for name in SUBCOMMANDS:
        if not re.search(rf"(?m)^\s+{name}\s{{2,}}\S", top):
            bad.append(f"{name}: нет строки в общем списке")
        rc_own, own = pages[name]
        parts = own.split("\n\n")
        second = parts[1].strip() if len(parts) > 1 else ""
        has_description = (rc_own == 0 and len(second) >= 20 and not re.match(
            r"(positional arguments|options|optional arguments):", second))
        if not has_description:
            bad.append(f"{name}: нет описания в своей справке")
    detail = (f"справка на месте у всех {len(SUBCOMMANDS)} подкоманд" if not bad
              else "; ".join(bad))
    return not bad, detail, bad


def check_no_numbers(pages: dict) -> tuple[bool, str, list]:
    """⑦: в печатаемой справке нет номеров карточек и кружочных цифр."""
    found = []
    for label, (rc, out) in pages.items():
        if rc != 0:
            found.append(f"{label}: справка не напечаталась (код {rc})")
        for m in NUMBER_MARK.finditer(out):
            found.append(f"{label}: …{out[max(0, m.start() - 25):m.end() + 10]!r}…".replace("\n", " "))
    detail = (f"в {len(pages)} печатных справках номеров нет" if not found
              else "; ".join(found))
    return not found, detail, found


def check_synonyms(tool, db: pathlib.Path, folder: pathlib.Path,
                   extra_env=None) -> tuple[bool, str, list]:
    """⑧: второе имя флага принимается и даёт тот же результат, что прежнее.

    Две одинаковые карточки заводятся ШТАТНЫМ инструментом (живым); испытуется только вызов
    подкоманды с прежним и со вторым именем флага. Сравниваются: код возврата, печать (с
    номером карточки, заменённым на метку), значение в базе и события критерия в истории."""
    env = dict(BASE_ENV)
    if extra_env:
        env.update(extra_env)
    value = "проверочный критерий для синонима: первое предложение. Второе предложение."
    bad: list = []
    notes: list = []
    for sub, old, new, kind in SYNONYMS:
        seen = {}
        for flag in (old, new):
            rc, out = call_tool(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                                "--title", "проба синонима", "--body", "т",
                                "--done-when", "исходный критерий")
            if rc != 0:
                raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка для пробы синонима не завелась: {out[:200]}")
            con = sqlite3.connect(str(db))
            bid = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
            con.close()
            if kind == "файл":
                path = folder / f"критерий-{bid}.md"
                path.write_text(value, encoding="utf-8")
                arg = str(path)
            else:
                arg = value
            rc, out = call_tool(tool, "--db", str(db), sub, str(bid), "--actor", "STUB1",
                                flag, arg, extra_env=env)
            con = sqlite3.connect(str(db))
            stored = con.execute("SELECT done_when FROM backlog WHERE id=?", (bid,)).fetchone()[0]
            events = [r[0] for r in con.execute(
                "SELECT body_md FROM backlog_events WHERE backlog_id=? AND event_type='criterion_set' "
                "ORDER BY id", (bid,))]
            con.close()
            seen[flag] = (rc, out.replace(f"#{bid}", "#N"), stored, events)
        if seen[old][0] != 0:
            bad.append(old)
            notes.append(f"{sub} {old}: прежнее имя не сработало (код {seen[old][0]}): {seen[old][1][:160]!r}")
        elif seen[new] != seen[old] or seen[new][2] != value:
            bad.append(new)
            notes.append(f"{sub} {new}: код {seen[new][0]} против {seen[old][0]}, "
                         f"в базе {seen[new][2]!r}, печать {seen[new][1][:160]!r}")
        else:
            notes.append(f"{sub} {new} = {old}: код, печать, значение и событие совпали")
    return not bad, "; ".join(notes), bad


# Слова голого отказа разбора аргументов — так show отказывал прежде. В отказе СЛОВАМИ их быть не должно.
RAW_REFUSAL_WORDS = ("invalid int value", "usage:", "error:", "arguments are required")

# Случаи ⑨–⑮: подкоманда show и встречные к ней (заголовок печатается в строке случая).
SHOW_CASES = (
    ("⑨", "show --role X: отказ словами — «нет роли», что получено, подсказка list --role X"),
    ("⑩", "show <номер> --role X: отказ словами — роль лишняя, номер назван верным"),
    ("⑪", "show abc: отказ словами — «не число», подсказка list --role abc"),
    ("⑫", "show без номера: отказ словами — «не указан номер», подсказка list --role <РОЛЬ>"),
    ("⑬", "встречный: show <настоящий номер> работает — код 0, карточка напечатана"),
    ("⑭", "встречный: show --help печатает справку, а не отказ"),
    ("⑮", "встречный: list --role X работает как прежде (там --role законен)"),
)


def check_show_forms(tool, db: pathlib.Path, bid: int, extra_env=None) -> dict:
    """⑨–⑮: подкоманда show отказывает словами; верный вызов, справка и list не тронуты.

    Возвращает {метка: (прошёл ли случай, подробность)}. Зовётся и для настоящего backlog.py,
    и для его копий с нарочной поломкой — поэтому инструмент и среда приходят параметрами."""
    env = dict(BASE_ENV)
    if extra_env:
        env.update(extra_env)

    def run(*args):
        return call_tool(tool, "--db", str(db), *args, extra_env=env)

    res: dict = {}

    def refusal(mark, args, must):
        """Отказ словами: код не ноль, голых слов разбора аргументов нет, нужные слова есть."""
        rc, out = run(*args)
        problems = []
        if rc == 0:
            problems.append("код возврата 0 — отказа нет")
        for raw in RAW_REFUSAL_WORDS:
            if raw in out:
                problems.append(f"в печати голый отказ разбора аргументов: «{raw}»")
        for word in must:
            if word not in out:
                problems.append(f"нет слов «{word}»")
        detail = (f"код {rc}, все нужные слова на месте, голых слов разбора нет" if not problems
                  else "; ".join(problems) + f" | печать: {out[:260]!r}")
        res[mark] = (not problems, detail)

    refusal("⑨", ("show", "--role", "STUB1"),
            ["нет роли", "Ожидалось: номер карточки — число", "Получено: --role STUB1",
             "list --role STUB1", "show <номер>"])
    refusal("⑩", ("show", str(bid), "--role", "STUB1"),
            ["нет роли", f"номер {bid} верный", f"show {bid}"])
    refusal("⑪", ("show", "abc"),
            ["должен быть числом", "Получено: «abc» — не число", "list --role abc", "show <номер>"])
    refusal("⑫", ("show",),
            ["не указан номер", "Получено: ничего", "list --role <РОЛЬ>", "show <номер>"])

    rc, out = run("show", str(bid))
    res["⑬"] = (rc == 0 and f"# backlog #{bid}" in out and "проба" in out and "⛔" not in out,
                f"код {rc}, печать: {out[:160]!r}")
    rc, out = run("show", "--help")
    res["⑭"] = (rc == 0 and "Принимает только номер карточки" in out and "⛔" not in out,
                f"код {rc}, печать: {out[:160]!r}")
    rc, out = run("list", "--role", "STUB1", "--status", "all")
    res["⑮"] = (rc == 0 and "проба" in out and "нет роли" not in out,
                f"код {rc}, печать: {out[:160]!r}")
    return res


def main() -> int:
    d = mezo_stand.new("actor-role-")
    db = d / "stand.db"
    clean_db(db)
    failures: list[str] = []
    cases = 0

    def case(name, condition, trace=""):
        nonlocal cases
        cases += 1
        print(f"{'✅' if condition else '🔴'} {name}")
        if not condition:
            failures.append(name)
            if trace:
                print(f"   след: {trace[:400]}")

    rc, _ = call_tool(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                "--title", "проба", "--body", "т", "--done-when", "к")
    if rc != 0:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка не завелась")
    con = sqlite3.connect(str(db))
    bid1 = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
    con.close()

    # ── ① чужое имя у карточек: отказ с подсказкой ─────────────────────────────
    rc1, out1 = call_tool(BACKLOG, "--db", str(db), "claim", str(bid1), "--role", "STUB1")
    case("① backlog claim --role: ОТКАЗ, подсказка несёт --actor и карточку #409",
        rc1 != 0 and "--actor" in out1 and "карточка #409" in out1, out1)

    # ── ② чужое имя у объявлений: отказ с подсказкой ───────────────────────────
    rc2, out2 = call_tool(LEASE, "--db", str(db), "take", "--actor", "STUB1",
                    "--tools", "x.py", "--reason", "проба")
    case("② lease take --actor: ОТКАЗ, подсказка несёт --role и карточку #409",
        rc2 != 0 and "--role" in out2 and "карточка #409" in out2, out2)

    # ── ③④⑤ встречные: прежние верные вызовы работают ─────────────────────────
    rc3, out3 = call_tool(BACKLOG, "--db", str(db), "claim", str(bid1), "--actor", "STUB1",
                    "--note", "проба взятия")
    case("③ backlog claim --actor: работает как прежде", rc3 == 0, out3)

    rc4, out4 = call_tool(LEASE, "--db", str(db), "take", "--role", "STUB1",
                    "--tools", "x.py", "--reason", "проба", "--minutes", "5")
    case("④ lease take --role: работает как прежде", rc4 == 0, out4)

    rc5, out5 = call_tool(BACKLOG, "--db", str(db), "add", "--role", "STUB2",
                    "--title", "проба-два", "--body", "т", "--done-when", "к")
    case("⑤ backlog add --role: законный --role (владелец) не тронут", rc5 == 0, out5)

    # ── Р1 обратный ход: подсказка ослеплена ───────────────────────────────────
    weak_rev1 = weaken(BACKLOG, d,
                    'if _subcommand in _ACTOR_COMMANDS and "--role" in sys.argv:',
                    "if False:")
    rc_r1, out_r1 = call_tool(weak_rev1, "--db", str(db), "claim", str(bid1), "--role", "STUB1",
                        extra_env={"PYTHONPATH": str(BACKLOG.parent)})
    case("Р1 подсказка ослеплена: отказ голый, ссылки на карточку #409 нет — ① пал бы",
        rc_r1 != 0 and "карточка #409" not in out_r1, out_r1)

    # ── ⑥⑦⑧ справка backlog.py и флаги одного смысла (заявка пакета №26) ───────
    pages = fetch_help(BACKLOG)
    ok6, det6, _ = check_help_present(pages)
    case("⑥ у каждой из 9 подкоманд есть справка: строка в общем списке и описание в своей",
        ok6, det6)
    ok7, det7, _ = check_no_numbers(pages)
    case("⑦ в печатаемой справке (общей и девяти подкоманд) нет номеров карточек",
        ok7, det7)
    ok8, det8, _ = check_synonyms(BACKLOG, db, d)
    case("⑧ второе имя флага одного смысла принимается и даёт тот же результат, что прежнее",
        ok8, det8)

    # ── ⑨–⑮ show: отказ словами и встречные случаи (заявка пакета №26, п. в) ────
    show_res = check_show_forms(BACKLOG, db, bid1)
    for mark, title in SHOW_CASES:
        case(f"{mark} {title}", show_res[mark][0], show_res[mark][1])

    # ── нарочные поломки на КОПИЯХ backlog.py: падает РОВНО названная проверка ──
    def broken_copy(tag: str, anchor: str, replacement: str) -> pathlib.Path:
        folder = d / tag
        folder.mkdir()
        return weaken(BACKLOG, folder, anchor, replacement)

    def run_all(copy_path: pathlib.Path):
        # Соседи копии лежат рядом с живым файлом. Корень контура задан явно: копия лежит вне
        # его, и без этого инструмент ищет контур вверх от каталога стенда и не находит
        # («второй замок» в mezo_paths.py); база при этом всё равно только стендовая — --db.
        env = {"PYTHONPATH": str(BACKLOG.parent),
               "MEZO_CONTAINER": str(mezo_paths.container_root(__file__))}
        copy_pages = fetch_help(copy_path, extra_env=env)
        return (check_help_present(copy_pages), check_no_numbers(copy_pages),
                check_synonyms(copy_path, db, d, extra_env=env))

    def failed_names(res) -> list:
        return [mark for mark, part in zip(("⑥", "⑦", "⑧"), res) if not part[0]]

    # Р2: у подкоманды comment убрана строка help= → из общего списка она пропала
    res = run_all(broken_copy("break-2", 'help="добавить комментарий к карточке",', ""))
    case("Р2 у comment убрана строка help=: падает РОВНО ⑥, и называет comment",
        failed_names(res) == ["⑥"] and res[0][2] == ["comment: нет строки в общем списке"],
        f"упали {failed_names(res)}; ⑥: {res[0][2]}")

    # Р2б: у подкоманды show описание превращено в эпилог → в своей справке описания нет
    res = run_all(broken_copy(
        "break-2b",
        r'description="Показать одну карточку целиком: тело, критерий приёмки, связи, историю.\n"',
        r'epilog="Показать одну карточку целиком: тело, критерий приёмки, связи, историю.\n"'))
    case("Р2б у show описание убрано из своей справки: падает РОВНО ⑥, и называет show",
        failed_names(res) == ["⑥"] and res[0][2] == ["show: нет описания в своей справке"],
        f"упали {failed_names(res)}; ⑥: {res[0][2]}")

    # Р3: в справку edit возвращён номер карточки → ⑥ держится (справка есть), падает ⑦
    res = run_all(broken_copy(
        "break-3",
        'help="править заголовок и/или набор заведённой карточки; прежнее значение сохраняется в истории",',
        'help="править заголовок и/или набор заведённой карточки — со следом-событием (карточка #452)",'))
    case("Р3 в справку edit возвращён номер карточки: падает РОВНО ⑦, и называет #452",
        failed_names(res) == ["⑦"] and any("#452" in item for item in res[1][2]),
        f"упали {failed_names(res)}; ⑦: {res[1][2]}")

    # Р4: у criterion убрано имя --done-when → второе имя больше не принимается
    res = run_all(broken_copy(
        "break-4",
        'pk.add_argument("--text", "--done-when", dest="text", default="",',
        'pk.add_argument("--text", dest="text", default="",'))
    case("Р4 у criterion убрано имя --done-when: падает РОВНО ⑧, и называет именно его",
        failed_names(res) == ["⑧"] and res[2][2] == ["--done-when"],
        f"упали {failed_names(res)}; ⑧: {res[2][2]}")

    # Р4б: у criterion убрано имя --done-when-file
    res = run_all(broken_copy(
        "break-4b",
        'pk.add_argument("--text-file", "--done-when-file", dest="text_file",',
        'pk.add_argument("--text-file", dest="text_file",'))
    case("Р4б у criterion убрано имя --done-when-file: падает РОВНО ⑧, и называет именно его",
        failed_names(res) == ["⑧"] and res[2][2] == ["--done-when-file"],
        f"упали {failed_names(res)}; ⑧: {res[2][2]}")

    # ── нарочные поломки show на КОПИЯХ backlog.py: падает РОВНО названное из ⑨–⑮ ──
    def broken_copy_pairs(tag: str, pairs) -> pathlib.Path:
        """Копия backlog.py с несколькими испорченными местами (каждое — одна строка-якорь)."""
        folder = d / tag
        folder.mkdir()
        path = BACKLOG
        for anchor, replacement in pairs:
            path = weaken(path, folder, anchor, replacement)
        return path

    def failed_show(copy_path: pathlib.Path) -> tuple[list, dict]:
        env = {"PYTHONPATH": str(BACKLOG.parent),
               "MEZO_CONTAINER": str(mezo_paths.container_root(__file__))}
        got = check_show_forms(copy_path, db, bid1, extra_env=env)
        return [mark for mark, _ in SHOW_CASES if not got[mark][0]], got

    show_breaks = (
        ("Р5", "снят перехват (прежний разбор): падают РОВНО четыре отказа ⑨⑩⑪⑫, встречные держатся",
         [("if _show_refusal:", "if False:")], ["⑨", "⑩", "⑪", "⑫"]),
        ("Р5а", "в подсказке отказа ⑨ потеряна роль: падает РОВНО ⑨",
         [("maybe_role = role", 'maybe_role = ""')], ["⑨"]),
        ("Р5б", "в отказе ⑩ убраны слова «номер верный»: падает РОВНО ⑩",
         [('got += f"; номер {number} верный, лишнее только --role"', 'got += ""')], ["⑩"]),
        ("Р5в", "в подсказке отказа ⑪ потеряно слово пользователя: падает РОВНО ⑪",
         [("maybe_role = positional[0]", 'maybe_role = ""')], ["⑪"]),
        ("Р5г", "вызов без номера пропущен к голому отказу: падает РОВНО ⑫",
         [("if role is None and number is not None:",
           "if role is None and (number is not None or not positional):")], ["⑫"]),
        ("Р5д", "верный номер больше не пропускается: падает РОВНО встречный ⑬",
         [("if role is None and number is not None:", "if False:")], ["⑬"]),
        ("Р5е", "справка show больше не пропускается: падает РОВНО встречный ⑭",
         [('if "-h" in tail or "--help" in tail:', "if False:")], ["⑭"]),
        ("Р5ж", "перехват распространён на все подкоманды: падает РОВНО встречный ⑮",
         [('if _subcommand == "show":', "if _subcommand:"),
          ('sys.argv.index("show")', "sys.argv.index(_subcommand)")], ["⑮"]),
    )
    for n, (tag, title, pairs, expected) in enumerate(show_breaks):
        failed, got = failed_show(broken_copy_pairs(f"break-show-{n}", pairs))
        case(f"{tag} {title}", failed == expected,
             f"упали {failed}, ждали {expected}; "
             + "; ".join(f"{m}: {got[m][1][:200]}" for m in failed if m not in expected))

    print("-" * 76)
    if failures:
        print(f"🔴 ПРИЁМКА: {cases - len(failures)} из {cases}, провалено: "
              + " · ".join(failures))
        return 1
    print(f"✅ ПРИЁМКА: {cases} из {cases} — чужое имя получает подсказку, верные вызовы "
          f"не тронуты, справка backlog.py полна, вторые имена флагов работают, show отказывает "
          f"словами, поломки ловятся")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
