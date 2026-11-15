# -*- coding: utf-8 -*-
r"""ПРИЁМКА поиска по хранилищу слов владельца: регистр и пути по умолчанию —
карточки #785 (поиск теряет слова из-за регистра) и #780 (пути по умолчанию).

ПОВОД. В SQLite этой сборки `lower()`, `LIKE` и `COLLATE NOCASE` сворачивают регистр
только для латиницы: `'ПЕРИСКОП' LIKE '%периск%'` даёт 0. Живой замер: `find «стена»` → 1,
`find «Стена»` → ничего; `find «рекоменд»` → ничего, `find «Рекоменд»` → 5 из 6. Поиск идёт
по двум полям (дословный текст и пояснение роли), и находка одним полем была неотличима
в выводе от находки обоими. Отдельно: умолчания `--db` и `--finder` вели мимо.

⛔ ЖИВОЙ БАЗЫ НЕ КАСАЕТСЯ. Работает на ПОДСТАВНОЙ базе — схема живого контура БЕЗ его
строк (mezo_stand.empty_db); строки `owner_words` приёмка вставляет сама SQL-ом: подкоманда
`add` сверяет текст с записями разговоров, и в стенде эта сверка не нужна. Схему берёт
из базы, названной MEZO_LIVE_DB (только чтение), либо из соседней с испытуемым каталогом.
Искатель записей разговоров приёмка запускает с подставным домашним каталогом, поэтому
настоящие записи разговоров не читаются вовсе.

Какую копию испытываем — тем же рычагом, что у соседних приёмок (карточка #148):
MEZO_SCRIPTS_ROOT (mezo_target.py).

Случаи (различающий = обязан ответить ИНАЧЕ на поломанной копии):
  ① три написания куска (строчные · Прописная · ВСЕ ПРОПИСНЫЕ) дают ОДНО число, и оно
    равно ИСТИНЕ, посчитанной в Python по всем строкам стенда; истина не пуста — иначе
    «одно и то же число» могло бы быть одинаково пустым                    РАЗЛИЧАЮЩИЙ
  ② у каждой находки названо поле совпадения («дословный текст» · «пояснение» · «оба»),
    и название равно истине по строке; в стенде есть строки всех трёх видов  РАЗЛИЧАЮЩИЙ
  ③ нуль находок при непустом хранилище: код 1, сказано «совпадений нет» и число слов
    в хранилище, названа граница («ё» против «е», латиница внутри слова), и НЕТ слов
    «не записано» и «значит» — вывода о предмете                              КОНТРОЛЬ
  ④ пустое хранилище: код 4, «хранилище пусто» — отличается от ③            КОНТРОЛЬ
  ⑤ пути по умолчанию: копия инструмента запущена из ТРЁХ чужих рабочих каталогов без
    --db и без --finder: база стенда найдена (штатной подменой контейнера), а искатель —
    файл рядом с копией (не «искатель не найден»)                            КОНТРОЛЬ
  ⑩ УСТАНОВЛЕННАЯ РАСКЛАДКА БЕЗ ПОДМЕНЫ СРЕДОЙ (карточка #780): копия лежит в
    `<контейнер>/vnext-tools/`, база — в `<контейнер>/.mezosync/`; запуск из ТРЁХ рабочих
    каталогов без --db и без --finder, в окружении, из которого УБРАНЫ все MEZO_*. База стенда
    найдена, искатель найден. Случай ⑤ доказывает подмену средой, а этот — расчёт от скрипта;
    печатается, каким путём найдена база (общий выбор или запасной уровнем выше)   КОНТРОЛЬ
  ⑩-б то же, но рядом с копией НЕТ `mezo_paths.py`: запасной путь сам находит базу   КОНТРОЛЬ
  ⑩-в та же раскладка, но контейнер НАЗВАН средой (MEZO_CONTAINER) и базы по нему нет: отказ
    кодом 3 с именем переменной и её путём, а НЕ база рядом со скриптом — названное сильнее
    запасного пути, иначе `add` записал бы слово не в тот контур             РАЗЛИЧАЮЩИЙ
  ⑥ явные пути по-прежнему отказывают: --db на несуществующий файл — отказ с путём;
    --finder на несуществующий файл — «сверить дословность нечем», слово НЕ записано  КОНТРОЛЬ
  ⑦ латиница: `PILOT`, `pilot`, `Pilot` — одно число, равное истине (SQLite и так её
    сворачивает, поэтому на поломанной копии случай обязан остаться целым)    КОНТРОЛЬ
  ⑧ ОБРАТНЫЙ ХОД, ПРЕДВАРИТЕЛЬНЫЙ: поломанная копия ЗАПУСТИЛАСЬ — есть числа, а не падение
  ⑨ ОБРАТНЫЙ ХОД 1 (регистр): в копии сворачивание регистра возвращено базе (функция
    регистра заменена встроенной `lower`) — провалиться обязаны РОВНО ① и ②; остальные целы
  ⑪ ОБРАТНЫЙ ХОД 2 (пути), ПРЕДВАРИТЕЛЬНЫЙ: копия с прежним расчётом путей ЗАПУСТИЛАСЬ
  ⑫ ОБРАТНЫЙ ХОД 2 (пути): в копии возвращён прежний расчёт (база — каталог уровнем выше
    скрипта + `mezosync.db`; искатель — два уровня выше + `vnext-tools/…`) — провалиться
    обязаны ⑤, ⑩, ⑩-б и ⑩-в, причём ⑩ — во ВСЕХ ТРЁХ рабочих каталогах (промах от рабочего
    каталога не зависит: прежний код считал уровни от скрипта в расчёте на установку
    в `.mezosync/scripts`); ①–④, ⑥, ⑦ целы. ⑤ краснеет здесь потому, что копия стенда лежит
    вне контейнера: прежний расчёт не видит и подмену. ⑩-в краснеет потому, что прежний
    расчёт отвечает «базы нет» кодом 1 по своему пути, а не отказом кодом 3 по названному.
  ⑬ ОБРАТНЫЙ ХОД 3 (названный контейнер), ПРЕДВАРИТЕЛЬНЫЙ: копия ЗАПУСТИЛАСЬ
  ⑭ ОБРАТНЫЙ ХОД 3 (названный контейнер): в копии запасной путь берётся и при названном
    контейнере — провалиться обязан РОВНО ⑩-в; остальные целы.
    Якоря всех трёх поломок ищутся точной строкой и встречаются РОВНО ОДИН раз.

Зовут так (пример; MEZO_LIVE_DB — только источник схемы):
    MEZO_SCRIPTS_ROOT=<каталог испытуемой копии> MEZO_LIVE_DB=<живая база> \
        python vnext/prototype/bite-owner-word-case.py
"""
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

# Поломка из двух правок, обе ищутся точной строкой и обе обязаны встретиться РОВНО ОДИН раз:
# имя функции регистра в запросе становится встроенной `lower` базы, а регистрация
# собственной функции снята (иначе собственная `lower` перекрыла бы встроенную, и поломки
# не было бы вовсе: первый прогон этой приёмки так и показал).
BREAK_CASE = [("FOLD = 'fold'", "FOLD = 'lower'"),
              ("    conn.create_function(FOLD, 1, fold_text, deterministic=True)",
               "    pass  # поломка: сворачивание регистра возвращено базе")]
# Поломка путей: прежний расчёт — от скрипта, в расчёте на установку в `.mezosync/scripts`.
BREAK_PATHS = [
    ("DEFAULT_FINDER = os.path.join(HERE, 'find-owner-word.py')",
     "DEFAULT_FINDER = os.path.join(os.path.dirname(os.path.dirname(HERE)), "
     "'vnext-tools', 'find-owner-word.py')"),
    ("        a.db = default_db()",
     "        a.db = os.path.join(os.path.dirname(HERE), 'mezosync.db')")]
# Поломка названного контейнера: запасной путь берётся, даже когда контейнер назван средой.
BREAK_NAMED = [("    if not named and os.path.isfile(beside):",
                "    if os.path.isfile(beside):")]

IN_TEXT, IN_NOTE, IN_BOTH = "дословный текст", "пояснение", "оба"

print(f"⚖️ испытуется: {mezo_target.label()}")
tool = mezo_target.script("owner-word.py")
finder = mezo_target.script("find-owner-word.py")

# Строки стенда: (said_at, text_verbatim, note). Подобраны так, чтобы были находки
# ТОЛЬКО текстом, ТОЛЬКО пояснением и ОБОИМИ, и чтобы регистр в них лежал по-разному.
ROWS = [
    ("2026-11-01 10:00:00 UTC", "Установить пилот сегодня", None),
    ("2026-11-02 10:00:00 UTC", "ВЕЛИКИЙ ПЕРИСКОП", "пояснение: перископ нужен"),
    ("2026-11-03 10:00:00 UTC", "Рекомендую шаг один", "роль рекомендовала шаг"),
    ("2026-11-04 10:00:00 UTC", "просто слова", "Рекомендация роли"),
    ("2026-11-05 10:00:00 UTC", "ничего особого", "ПИЛОТ упомянут"),
    ("2026-11-06 10:00:00 UTC", "Елка и палка", None),
    ("2026-11-07 10:00:00 UTC", "ящерица бежит", None),
    ("2026-11-08 10:00:00 UTC", "Pilot flies", None),
]

failures = []


def check(num, ok, said):
    """Записать исход случая. Печатает ВСЕГДА — и когда прошёл, и когда нет."""
    print(f"{'✅' if ok else '🔴'} {num} {said}")
    if not ok:
        failures.append(f"{num} {said}")
    return ok


def spellings(piece):
    """Три написания куска: строчные · Прописная первая · ВСЕ ПРОПИСНЫЕ."""
    return [piece.lower(), piece[:1].upper() + piece[1:].lower(), piece.upper()]


def fill(db, rows):
    conn = sqlite3.connect(str(db))
    try:
        for said_at, text, note in rows:
            conn.execute(
                "INSERT INTO owner_words (said_at, chat, text_verbatim, source_file, "
                "source_line, verified_by, heard_by, noted_at, note) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (said_at, "ОПЫТ", text, None, None, "стенд приёмки", "ОПЫТ", said_at, note))
        conn.commit()
    finally:
        conn.close()


def table_rows(db):
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT id, text_verbatim, note FROM owner_words").fetchall()
    finally:
        conn.close()


def count_words(db):
    return len(table_rows(db))


def truth(db, piece):
    """ИСТИНА, посчитанная в Python по ВСЕМ строкам стенда: {номер: поле совпадения}."""
    key = piece.casefold()
    out = {}
    for rid, text, note in table_rows(db):
        in_text = key in (text or "").casefold()
        in_note = key in (note or "").casefold()
        if in_text or in_note:
            out[rid] = IN_BOTH if (in_text and in_note) else (IN_TEXT if in_text else IN_NOTE)
    return out


def parse(out):
    """Из вывода инструмента: (число из «найдено слов: N» или None, {номер: поле})."""
    m = re.search(r"найдено слов: (\d+)", out)
    fields = {}
    for block in out.split("-" * 70):
        n = re.search(r"слово #(\d+)", block)
        f = re.search(r"совпало в \.+ (.+)", block)
        if n:
            raw = f.group(1).strip() if f else None
            fields[int(n.group(1))] = (IN_BOTH if raw and raw.startswith("оба")
                                       else raw)
    return (int(m.group(1)) if m else None), fields


def run(tool_path, cwd, container, *args, home=None, bare=False, extra=None):
    """Запуск копии инструмента на стенде. Возвращает (код, весь вывод).

    Домашний каталог подменён пустым: искатель записей разговоров ищет под ним, и настоящие
    записи не читаются."""
    env = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8")
    if bare:
        # ⛔ НИ ОДНОЙ переменной MEZO_* (и номера чата): иначе доказывалась бы подмена
        # средой, а не расчёт от расположения скрипта.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("MEZO_") and k != "CLAUDE_CODE_SESSION_ID"}
        env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        # Переменные, названные случаем ПОВЕРХ очищенного окружения (случай ⑩-в).
        env.update(extra)
    if home is not None:
        env["USERPROFILE"] = str(home)
        env["HOME"] = str(home)
    r = subprocess.run([sys.executable, "-X", "utf8", str(tool_path), *args],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(cwd),
                       env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def case_spelling_count(ctx):
    """① три написания → одно число = истина."""
    said, ok = [], True
    for piece in ("рекоменд", "пилот"):
        t = truth(ctx["db"], piece)
        nums = []
        for sp in spellings(piece):
            code, out = run(ctx["tool"], ctx["cwd"], ctx["container"],
                            "--db", str(ctx["db"]), "find", sp)
            n, fields = parse(out)
            nums.append((sp, code, n, set(fields)))
        want = len(t)
        same = len({x[2] for x in nums}) == 1
        ok &= (want > 0 and same and all(x[2] == want and x[1] == 0
                                         and x[3] == set(t) for x in nums))
        said.append(f"«{piece}»: " + " · ".join(f"{sp}→{n} (код {c})" for sp, c, n, _ in nums)
                    + f" · истина {want}")
    return ok, "; ".join(said)


def case_fields(ctx):
    """② у каждой находки названо поле, и оно равно истине; стенд знает все три вида."""
    seen_kinds, ok, bad = set(), True, []
    for piece in ("рекоменд", "пилот"):
        t = truth(ctx["db"], piece)
        seen_kinds |= set(t.values())
        for sp in spellings(piece):
            code, out = run(ctx["tool"], ctx["cwd"], ctx["container"],
                            "--db", str(ctx["db"]), "find", sp)
            _, fields = parse(out)
            if fields != t:
                ok = False
                bad.append(f"{sp}: напечатано {fields}, истина {t}")
    covered = seen_kinds == {IN_TEXT, IN_NOTE, IN_BOTH}
    return ok and covered, (f"поле совпадения у каждой находки равно истине: "
                            f"{'да' if ok else 'НЕТ'} · в стенде все три вида: "
                            f"{'да' if covered else 'НЕТ (' + ', '.join(sorted(seen_kinds)) + ')'}"
                            + ("" if ok else " · " + " | ".join(bad)))


def case_zero(ctx):
    """③ нуль при непустом хранилище: причина не выдумана."""
    piece = "ёлка"       # в строке «Елка»: «ё» и «е» — разные буквы, истина — ноль
    t = truth(ctx["db"], piece)
    code, out = run(ctx["tool"], ctx["cwd"], ctx["container"], "--db", str(ctx["db"]),
                    "find", piece)
    low = out.lower()
    total = count_words(ctx["db"])
    ok = (len(t) == 0 and code == 1 and "совпадений нет" in out
          and f"Слов в хранилище: {total}" in out
          and "«ё» против «е»" in out and "латинская буква внутри русского слова" in out
          and "не записано" not in low and "значит" not in low)
    return ok, (f"ноль находок: код {code} (ждали 1) · истина {len(t)} · число слов в хранилище "
                f"названо ({total}): {'да' if f'Слов в хранилище: {total}' in out else 'НЕТ'} "
                f"· граница названа: {'да' if '«ё» против «е»' in out else 'НЕТ'} "
                f"· слов «не записано»/«значит» нет: "
                f"{'да' if ('не записано' not in low and 'значит' not in low) else 'НЕТ'}")


def case_empty(ctx):
    """④ пустое хранилище — свой код."""
    code, out = run(ctx["tool"], ctx["cwd"], ctx["container"], "--db", str(ctx["empty_db"]),
                    "find", "что-угодно")
    return code == 4 and "хранилище пусто" in out, (
        f"пустое хранилище: код {code} (ждали 4) · «хранилище пусто» напечатано: "
        f"{'да' if 'хранилище пусто' in out else 'НЕТ'}")


def case_defaults(ctx):
    """⑤ пути по умолчанию из трёх чужих рабочих каталогов."""
    ok, said = True, []
    before = count_words(ctx["db"])
    for label, cwd in ctx["foreign_cwds"]:
        c1, o1 = run(ctx["copy"], cwd, ctx["container"], "find", "ящерица")
        n, _ = parse(o1)
        c2, o2 = run(ctx["copy"], cwd, ctx["container"], "add",
                     "--said-at", "2026-11-09 10:00:00 UTC", "--chat", "ОПЫТ",
                     "--text", "зззз такого текста в записях нет", "--heard-by", "ОПЫТ",
                     home=ctx["home"])
        finder_found = ("искатель не найден" not in o2) and ("→ код" in o2)
        good = (c1 == 0 and n == 1 and "базы нет" not in o1 and finder_found
                and count_words(ctx["db"]) == before)
        ok &= good
        said.append(f"{label}: база {'найдена' if (c1 == 0 and n == 1) else 'НЕ найдена'} (найдено {n}, код {c1}) · искатель найден: "
                    f"{'да' if finder_found else 'НЕТ'} (код {c2})")
    return ok, "; ".join(said)


def case_explicit(ctx):
    """⑥ явные пути: несуществующий отказывает, ничего не подставляется."""
    nodb = ctx["stand"] / "нет-такой.db"
    c1, o1 = run(ctx["copy"], ctx["cwd"], ctx["container"], "--db", str(nodb), "find", "x")
    before = count_words(ctx["db"])
    nofinder = ctx["stand"] / "нет-искателя.py"
    c2, o2 = run(ctx["copy"], ctx["cwd"], ctx["container"], "--db", str(ctx["db"]),
                 "--finder", str(nofinder), "add", "--said-at", "2026-11-09 10:00:00 UTC",
                 "--chat", "ОПЫТ", "--text", "зззз другой текст", "--heard-by", "ОПЫТ")
    ok1 = c1 != 0 and "базы нет" in o1 and str(nodb) in o1
    ok2 = (c2 == 2 and "сверить дословность нечем" in o2 and str(nofinder) in o2
           and count_words(ctx["db"]) == before)
    return ok1 and ok2, (f"--db на несуществующий: код {c1} · путь назван: "
                         f"{'да' if str(nodb) in o1 else 'НЕТ'}; --finder на несуществующий: "
                         f"код {c2} (ждали 2) · «сверить дословность нечем»: "
                         f"{'да' if 'сверить дословность нечем' in o2 else 'НЕТ'} · "
                         f"слово не записано: {'да' if count_words(ctx['db']) == before else 'НЕТ'}")


def case_latin(ctx):
    """⑦ латиница: три написания — одно число = истина."""
    t = truth(ctx["db"], "pilot")
    nums = []
    for sp in spellings("pilot"):
        code, out = run(ctx["tool"], ctx["cwd"], ctx["container"], "--db", str(ctx["db"]),
                        "find", sp)
        n, _ = parse(out)
        nums.append((sp, code, n))
    ok = len(t) > 0 and all(c == 0 and n == len(t) for _, c, n in nums)
    return ok, ("латиница: " + " · ".join(f"{sp}→{n} (код {c})" for sp, c, n in nums)
                + f" · истина {len(t)}")


def probe_shared_choice(script, cwd):
    """Каким путём найдена база: отвечает ли общий выбор (mezo_paths) из этого расположения.
    Зовётся тем же окружением без MEZO_*; возвращает короткую строку."""
    code = ("import sys, os\n"
            "sys.path.insert(0, os.path.dirname(sys.argv[1]))\n"
            "try:\n    import mezo_paths\nexcept ImportError:\n"
            "    print('рядом нет mezo_paths: запасной путь'); sys.exit(0)\n"
            "try:\n    print('общий выбор нашёл ' + str(mezo_paths.default_db(sys.argv[1])))\n"
            "except SystemExit:\n    print('общий выбор отказал: найдено запасным путём')\n")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("MEZO_") and k != "CLAUDE_CODE_SESSION_ID"}
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(script)],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(cwd), env=env)
    return (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "?"


def installed_case(ctx, variant):
    """⑩ / ⑩-б: установленная раскладка, окружение без MEZO_*, три чужих каталога.

    Возвращает (ok, said, flags): flags — по одному признаку на рабочий каталог."""
    copy = ctx["install"][variant]
    flags, said = [], []
    before = count_words(ctx["db"])
    for label, cwd in ctx["foreign_cwds"]:
        c1, o1 = run(copy, cwd, ctx["container"], "find", "ящерица", bare=True)
        n, _ = parse(o1)
        c2, o2 = run(copy, cwd, ctx["container"], "add",
                     "--said-at", "2026-11-09 10:00:00 UTC", "--chat", "ОПЫТ",
                     "--text", "зззз такого текста в записях нет", "--heard-by", "ОПЫТ",
                     home=ctx["home"], bare=True)
        finder_found = ("искатель не найден" not in o2) and ("→ код" in o2)
        good = (c1 == 0 and n == 1 and finder_found and count_words(ctx["db"]) == before)
        flags.append(good)
        said.append(f"{label}: " + (f"найдено {n} (код {c1}) · искатель "
                                    f"{'найден' if finder_found else 'НЕ найден'}"))
    via = probe_shared_choice(copy, ctx["foreign_cwds"][0][1])
    return all(flags), "; ".join(said) + f" · путь к базе: {via}", flags


def case_installed_a(ctx):
    return installed_case(ctx, "A")


def case_installed_b(ctx):
    return installed_case(ctx, "B")


def case_named_wrong(ctx):
    """⑩-в: контейнер НАЗВАН средой, а базы по нему нет — отказ, а не база рядом со скриптом.

    Копия в установленной раскладке: база стенда лежит ровно там, где её берёт запасной
    путь. Здоровая копия обязана отказать кодом 3 и назвать переменную с её путём."""
    wrong = ctx["stand"] / "no-such-container"
    said, ok = [], True
    for variant in ("A", "B"):
        code, out = run(ctx["install"][variant], ctx["foreign_cwds"][2][1], ctx["container"],
                        "find", "ящерица", bare=True, extra={"MEZO_CONTAINER": str(wrong)})
        n, _ = parse(out)
        named = "MEZO_CONTAINER" in out and str(wrong) in out
        ok &= (code == 3 and n is None and named)
        said.append(f"{'с mezo_paths' if variant == 'A' else 'без mezo_paths'}: код {code} "
                    f"(ждали 3) · находок {'нет' if n is None else n} (ждали: нет) · "
                    f"переменная и её путь названы: {'да' if named else 'НЕТ'}")
    return ok, "; ".join(said)


CASES = [("①", case_spelling_count), ("②", case_fields), ("③", case_zero),
         ("④", case_empty), ("⑤", case_defaults), ("⑥", case_explicit),
         ("⑦", case_latin), ("⑩", case_installed_a), ("⑩-б", case_installed_b),
         ("⑩-в", case_named_wrong)]
TITLES = {"⑤": "подмена средой (контейнер назван через MEZO_CONTAINER): ",
          "⑩": "установленная раскладка vnext-tools, без MEZO_*: ",
          "⑩-б": "то же без mezo_paths.py рядом: ",
          "⑩-в": "контейнер назван средой, базы по нему нет: "}


def run_cases(ctx):
    """Все случаи на одной копии: {номер: (ok, said, flags|None)}."""
    out = {}
    for num, fn in CASES:
        r = fn(ctx)
        out[num] = (r[0], TITLES.get(num, "") + r[1], r[2] if len(r) > 2 else None)
    return out


def patch(text, breaks):
    for anchor, replacement in breaks:
        text = text.replace(anchor, replacement)
    return text


stand = mezo_stand.new("bite-owner-word-case")
try:
    container = stand / "contour"
    (container / ".mezosync").mkdir(parents=True)
    db = container / ".mezosync" / "mezosync.db"
    live = mezo_target.scripts_root().parent / "mezosync.db"
    if os.environ.get("MEZO_LIVE_DB"):
        live = Path(os.environ["MEZO_LIVE_DB"])
    if not live.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: схему подставной базы брать неоткуда — нет {live}")
        print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего. Назови MEZO_LIVE_DB.")
        sys.exit(mezo_stand.finish(2))
    mezo_stand.empty_db(live, db)
    fill(db, ROWS)

    empty_container = stand / "contour-empty"
    (empty_container / ".mezosync").mkdir(parents=True)
    empty_db = empty_container / ".mezosync" / "mezosync.db"
    mezo_stand.empty_db(live, empty_db)

    home = stand / "home-empty"
    home.mkdir()
    sub = container / "sub"
    sub.mkdir()
    elsewhere = stand / "elsewhere"
    elsewhere.mkdir()

    def make_copy(dest, breaks=None, with_paths=True):
        """Копия инструмента ВМЕСТЕ с соседями и искателем в каталог стенда."""
        d = Path(dest)
        copy = mezo_stand.copy_tool(tool, d)
        mezo_stand.copy_tool(finder, d)
        if breaks:
            copy.write_text(patch(copy.read_text(encoding="utf-8"), breaks), encoding="utf-8")
        if not with_paths and (d / "mezo_paths.py").exists():
            (d / "mezo_paths.py").unlink()
        return copy

    def context(kind, breaks=None):
        """Копия для подмены средой (вне контейнера) и две установленные раскладки."""
        copy = make_copy(stand / f"tool-{kind}", breaks)
        inst_a = make_copy(container / f"vnext-tools-{kind}", breaks)
        inst_b = make_copy(container / f"vnext-tools-nopaths-{kind}", breaks, with_paths=False)
        return {"tool": copy, "copy": copy, "db": db, "empty_db": empty_db,
                "container": container, "cwd": elsewhere, "stand": stand, "home": home,
                "install": {"A": inst_a, "B": inst_b},
                "foreign_cwds": [("корень контейнера", container), ("подкаталог", sub),
                                 ("несвязанный каталог", elsewhere)]}

    print(f"   стенд: {len(ROWS)} слов в подставной базе; живая база только источник схемы")

    # ── здоровая копия
    healthy_ctx = context("healthy")
    healthy = healthy_ctx["copy"]
    for num, (ok, said, _f) in run_cases(healthy_ctx).items():
        check(num, ok, said)

    # ══ ОБРАТНЫЕ ХОДЫ: приёмка САМА строит поломки рядом с соседями инструмента
    text = healthy.read_text(encoding="utf-8")
    anchors_ok = True
    for label, breaks in (("РЕГИСТР", BREAK_CASE), ("ПУТИ", BREAK_PATHS),
                          ("НАЗВАННЫЙ КОНТЕЙНЕР", BREAK_NAMED)):
        bad_anchor = [(a, text.count(a)) for a, _ in breaks if text.count(a) != 1]
        if bad_anchor:
            print(f"🔴 ОБРАТНЫЙ ХОД {label}: ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ "
                  f"(нашлось {bad_anchor[0][1]}) — поломка не построена.")
            print(f"   якорь: {bad_anchor[0][0].strip()}")
            print("   Это НЕ «защита цела»: без поломки обратный ход ничего не доказывает.")
            failures.append(f"обратный ход {label}: якорь не найден ровно один раз")
            anchors_ok = False

    if anchors_ok:
        # ── ОБРАТНЫЙ ХОД 1: регистр
        rctx = context("reg", BREAK_CASE)
        code, out = run(rctx["copy"], elsewhere, container, "--db", str(db), "find", "пилот")
        n, _ = parse(out)
        started = code == 0 and n == 1
        check("⑧", started,
              f"копия с поломкой регистра запустилась: код {code} (ждали 0) · найдено {n} "
              "(ждали 1: строчное написание сходится с текстом даже у поломки)")
        broke = run_cases(rctx)
        for num, (ok, said, _f) in broke.items():
            print(f"   · регистр, на поломке {num}: {'прошёл' if ok else 'провалился'} — {said}")
        red = sorted(k for k, v in broke.items() if not v[0])
        check("⑨", started and red == ["①", "②"],
              f"ОБРАТНЫЙ ХОД 1 (регистр): провалились {', '.join(red) or 'никто'} "
              f"(ждали ровно ①, ②) · ⑩ на поломке регистра цел: "
              f"{'да' if broke['⑩'][0] else 'НЕТ'} · копия запустилась: "
              f"{'да' if started else 'НЕТ'}")

        # ── ОБРАТНЫЙ ХОД 2: пути
        pctx = context("paths", BREAK_PATHS)
        code, out = run(pctx["copy"], elsewhere, container, "--db", str(db), "find", "пилот")
        n, _ = parse(out)
        started_p = code == 0 and n == 2
        check("⑪", started_p,
              f"копия с прежним расчётом путей запустилась: код {code} (ждали 0) · найдено {n} "
              "(ждали 2: явный --db поломку путей не задевает)")
        pbroke = run_cases(pctx)
        for num, (ok, said, _f) in pbroke.items():
            print(f"   · пути, на поломке {num}: {'прошёл' if ok else 'провалился'} — {said}")
        pred = sorted(k for k, v in pbroke.items() if not v[0])
        flags_a = pbroke["⑩"][2] or []
        flags_b = pbroke["⑩-б"][2] or []
        all_three = len(flags_a) == 3 and not any(flags_a)
        check("⑫", started_p and pred == ["⑤", "⑩", "⑩-б", "⑩-в"] and all_three,
              f"ОБРАТНЫЙ ХОД 2 (пути): провалились {', '.join(pred) or 'никто'} "
              f"(ждали ровно ⑤, ⑩, ⑩-б, ⑩-в) · ⑩ провалился в каталогах "
              f"{[('корень', 'подкаталог', 'чужой')[i] for i, f in enumerate(flags_a) if not f]} "
              f"из трёх (ждали все три) · ⑩-б по каталогам: "
              f"{['прошёл' if f else 'провалился' for f in flags_b]} · "
              f"копия запустилась: {'да' if started_p else 'НЕТ'}")

        # ── ОБРАТНЫЙ ХОД 3: названный контейнер
        nctx = context("named", BREAK_NAMED)
        code, out = run(nctx["copy"], elsewhere, container, "--db", str(db), "find", "пилот")
        n, _ = parse(out)
        started_n = code == 0 and n == 2
        check("⑬", started_n,
              f"копия с запасным путём при названном контейнере запустилась: код {code} "
              f"(ждали 0) · найдено {n} (ждали 2: явный --db эту поломку не задевает)")
        nbroke = run_cases(nctx)
        for num, (ok, said, _f) in nbroke.items():
            print(f"   · названный контейнер, на поломке {num}: "
                  f"{'прошёл' if ok else 'провалился'} — {said}")
        nred = sorted(k for k, v in nbroke.items() if not v[0])
        check("⑭", started_n and nred == ["⑩-в"],
              f"ОБРАТНЫЙ ХОД 3 (названный контейнер): провалились {', '.join(nred) or 'никто'} "
              f"(ждали ровно ⑩-в) · копия запустилась: {'да' if started_n else 'НЕТ'}")

    print()
    total = len(CASES) + 6
    failed = len(failures)
    print(f"ИТОГ: {max(total - failed, 0)} из {total}")
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {failed}")
        for f in failures:
            print(f"   · {f}")
        sys.exit(mezo_stand.finish(1))
    print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — регистр свёрнут с обеих сторон, поле совпадения названо, "
          "пути по умолчанию верны в обеих раскладках, названный средой контейнер не "
          "подменяется базой рядом, каждая из трёх поломок валит ровно свои случаи.")
    print("⛔ Чего приёмка НЕ доказывает: «ё» против «е» и латинскую букву внутри русского "
          "слова (поиск их не лечит и говорит об этом); подкоманду `add` на настоящих записях "
          "разговоров; метки «%» и «_» внутри куска (они остаются шаблонными знаками LIKE).")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
