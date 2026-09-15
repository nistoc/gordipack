# -*- coding: utf-8 -*-
"""guard-memory-section-refs.py — ссылка на раздел памяти БЕЗ АДРЕСАТА (карточка #643 ⑥).

ПРЕДМЕТ. Роли пишут в своей памяти указатели трёх форм: «§ИМЯ», «блок «ИМЯ»» / «раздел
ИМЯ», «см. раздел ИМЯ». С 04.09 роли уносят блоки памяти в архив (memory-archive.py) —
указатель может вести в унесённое или в никуда, и роль идёт по нему молча.

ПРИЁМ ВЗЯТ у AIA (wake-check.py, find_pointer_defects, ⑨) — целиком инструмент НЕ брали
(их модель «файл памяти = база» и сателлиты у нас не годятся, контур на md-OFF с 16.07),
взят только сам приём различения трёх исходов.

ИСПРАВЛЕННЫЙ КЛАСС (найден card #643, комментарий владельца по разбору AIA): исходный
приём знал имена разделов ТОЛЬКО латиницей (wake-check.py:133, SECTION_NAMES) — ссылка
«в разделе ВОСКРЕШЕНИЯ» (русское имя раздела rebirth, родительный падеж) читалась им как
сирота. Здесь имена разделов узнаются И латиницей, И по-русски, в любом падеже (через
корень слова, а не точную форму).

ЗАМЕР ДО КОДА (снимок живой базы, 2026-09-15, 63 строки phoenix, 9 ролей) — САМИ формы
и русские имена взяты ОТСЮДА, не придуманы:
    §ИМЯ (любой регистр, чаще строчными — 227 вхождений против 27 заглавными у нас в
         замере) · «блок «ИМЯ»» / «раздел ИМЯ» (заглавными, как пишут роли) · «см. раздел/
         блок ИМЯ». Русские имена разделов, реально встреченные: §состояние (state),
         §источники/§источник (sources), §история (history), §план (plan), §пробуждение
         И §воскрешения (rebirth — ДВА разных русских имени у разных ролей), §кто я
         (identity, CHROME ×3 — «кто я» как раздел ЦЕЛИКОМ, не заголовок внутри него),
         §строка запуска (launcher, CHROME ×1). Живой встречный случай архива: STUD/state:190
         «Разбор — в архиве, блок «РЕЖИМ»» — проверено: РЕЖИМ РЕАЛЬНО в phoenix_archive
         роли STUD (4 куска) — сама роль обычными словами НАЗЫВАЕТ исход «в архиве».
    Числа и примеры целиком — в комментарии карточки #643
    (замер 2026-09-15 на снимке живой базы)
    (песочница разбора; здесь — только вывод замера в код, без путей песочницы).

ТРИ ИСХОДА на каждый указатель:
    найден ......... раздел (латиница или русское имя, любой падеж — по корню) ИЛИ
                      заголовок блока (## …) где-то в горячей памяти ЭТОЙ РОЛИ
    в архиве ....... цели нет в горячей памяти, но топик/тело куска в phoenix_archive
                      ЭТОЙ РОЛИ содержит имя — печатается команда, как достать
    без адресата ... нет нигде — настоящая находка: роль · раздел:строка · текст

Строки с пометкой о снятии НЕ судятся (число печатается отдельно): комбинация меток
⚰️/📦/🪦 (wake-check.py TOMB_MARKS), слов «~~»/УБРАН/СНЯТО/БОЛЬШЕ НЕ ХРАН
(guard-role-standard.py TOMBSTONE) и корня «УНЕС» — штатное слово ЭТОГО контура для
«перенесено в архив» (та же лексика, что в печати memory-archive.py: «уносим:»,
«унесено N знаков»). Живой повод (карточка #643 ⑥, круг доделки): STUD/state:10
«Прежний блок «ТИШИНА до особой задачи» УНЕСЁН — он пережил свою правду… верь этой
строке» — строка САМА объявляет цель мёртвой рядом с указателем, роль предупреждена
в том же предложении, а не находит пустоту молча — то, ради чего эта проверка
существует. Плюс табличная форма «было → чем заменено» без самих меток (форма
wake-check.py: ячейка с именем, следом непустая ячейка замены — мёртвое имя,
названное НАМЕРЕННО, сиротой быть не может).

МЯГКИЙ РЕЖИМ `--soft` (по заявке PROTO, встраивание в guard-all.py — её ход, не этот
файл): код возврата ВСЕГДА 0, находки «без адресата» печатаются строками с ведущим
«⚠️» — так `sub_guard()` пробрасывает их в общий прогон БЕЗ покраски (тот же приём,
каким «жёлтые строки зелёного прогона доезжают до общего вывода»). Без флага —
поведение прежнее (код 1 при находках). Довод: замер качества (2 находки на живом
снимке, 1 из них ложная) пока не такой, как у предшественников (guard-section-lag,
guard-rights-registry) перед их включением КРАСНЫМ — красить общий прогон чужой роли
по непроверенному сигналу значило бы обвинять её виной за пробел словаря инструмента.

«Раздел» в обычной речи БЕЗ заглавного имени цели («раздел памяти», «этот раздел») —
не указатель вовсе: регулярное выражение требует имя с заглавной буквы сразу после
слова «блок»/«раздел» — так это фильтруется СТРУКТУРНО, без отдельного словаря-стоп-листа.

ГРАНИЦА (сказано вслух, не молчанием — по норме guard-role-standard §W): корни русских
имён — СТЕМ-СОВПАДЕНИЕ (подстрока), не полный морфологический разбор; риск ложного
found на слове, случайно содержащем чужой корень (напр. «ЗАПУСК» внутри «перезапуск»),
признан и не лечится здесь — цена ошибки низкая (found вместо возможной orphan), а
морфологический разбор — отдельная, куда более дорогая работа. Список русских имён и
двух устойчивых словосочетаний («кто я» → identity, «строка запуска» → launcher) —
ЗАМЕРЕННЫЙ, не исчерпывающий: новая форма потребует нового замера, как и здесь.

READ-ONLY. Живую БД открывает `mode=ro`, ничего не пишет.

    python guard-memory-section-refs.py                  # все роли
    python guard-memory-section-refs.py --role CORE      # одна роль
    python guard-memory-section-refs.py --db <путь>      # своя база (приёмка/песочница)
    python guard-memory-section-refs.py --soft           # код 0 всегда, находки — «⚠️»
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны

ORDER = ("identity", "rebirth", "sources", "state", "plan", "history", "launcher")
LATIN_UPPER = {s.upper(): s for s in ORDER}

# ⚡ КОРНИ РУССКИХ ИМЁН — измерено на живой базе 2026-09-15 (см. шапку файла). Подстрока,
# не точная форма: ловит «ВОСКРЕШЕНИЯ» (родительный), «ВОСКРЕШЕНИИ» (предложный) и т.д.
RU_STEMS = {
    "rebirth":  ("ВОСКРЕШЕНИ", "ПРОБУЖДЕНИ"),   # CORE «раздел ВОСКРЕШЕНИЯ» · CHROME §пробуждение
    "sources":  ("ИСТОЧНИК",),                   # CHROME §источники / §источник
    "state":    ("СОСТОЯНИ",),                   # COORD §СОСТОЯНИЕ · CHROME §состояние
    "history":  ("ИСТОРИ",),                     # CHROME §ИСТОРИЯ / §история
    "plan":     ("ПЛАН",),                       # CHROME §план
    "identity": ("ИДЕНТИЧНОСТ",),                # канон TITLES; живьём как ССЫЛКА не встретилось —
                                                  # задел, граница названа в отчёте задания
    "launcher": ("ЗАПУСК",),                     # корень словосочетания «строка запуска», см. ниже
}
# Устойчивые двусловные разговорные имена — измерены, не общий стем (см. риск «КТО» отдельно
# ниже в докстринге _canon_section): «§кто я» держит адресатом identity ЦЕЛИКОМ (CHROME,
# launcher:107 · plan:287 · state:116), «§строка запуска» — launcher (CHROME state:116).
PHRASE_CANON = {"КТО Я": "identity", "СТРОКА ЗАПУСКА": "launcher"}

# ── ФОРМЫ УКАЗАТЕЛЕЙ ────────────────────────────────────────────────────────────────
# §ИМЯ: любой регистр (живой замер: 227 строчных против 27 заглавных — строчные ПРЕОБЛАДАЮТ,
# исходный приём AIA такие вовсе не видел). Известные двусловные фразы — ПЕРВОЙ веткой
# альтернативы (жадный выбор слева направо), иначе однословный, до пробела/пунктуации.
SECTION_REF = re.compile(
    r"§\s*(кто\s+я|строка\s+запуска|[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9\-]{1,30})",
    re.IGNORECASE)

# блок/раздел ИМЯ (ИМЯ — заглавными, как пишут роли; может быть из нескольких слов).
# Суффиксы «блок»/«раздел» — ИМЕННО русские падежные окончания, а не любые буквы: без
# этого «блокер COORD снят» (ING/state:31, живая находка замера) читался бы указателем
# на «COORD» — «ер» не падежное окончание «блока», это другое слово.
BLOCK_OR_SECTION = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё])(?:блок(?:е|а|ом|ов|ах|ами)?|раздел(?:е|а|ом|ов|ах|ами)?)\s+"
    r"«?([A-ZА-ЯЁ][A-ZА-ЯЁ0-9\-]{1,}(?:\s[A-ZА-ЯЁ][A-ZА-ЯЁ0-9\-]{1,})*)»?",
    re.UNICODE)

# Пометка о снятии — объединение TOMB_MARKS (wake-check.py) и TOMBSTONE (guard-role-standard.py)
# плюс корень «УНЕС» — штатное слово ЭТОГО контура для «перенесено в архив» (живой повод:
# STUD/state:10, «Прежний блок «ТИШИНА…» УНЕСЁН» — карточка #643 ⑥, круг доделки, см. шапку).
# знаки ⚰️/📦/🪦, зачёркивание «~~», слова УБРАН/СНЯТО/БОЛЬШЕ НЕ ХРАН/УНЕС(ён/ено/ли/лась…).
TOMB_RX = re.compile(r"⚰️|📦|🪦|~~|УБРАН|СНЯТО|БОЛЬШЕ НЕ ХРАН|УНЕС", re.IGNORECASE)
# Табличная форма «было → чем заменено» БЕЗ самого знака снятия (форма wake-check.py
# is_tomb): ячейка с именем указателя, следом непустая ячейка описания замены.
NAME_IN_CELL = re.compile(r"§|блок|раздел", re.IGNORECASE)

_HEAD_RX = re.compile(r"^#{1,3} [^\n]*$", re.M)


def _headers(text: str) -> list[str]:
    return _HEAD_RX.findall(text or "")


def _head_key(h: str) -> str:
    """Заголовок к ОДНОЙ форме сравнения: без решёток и знака параграфа, ВЕРХНИМ регистром."""
    return re.sub(r"^#{1,3}\s*", "", h).lstrip("§ ").upper()


def _canon_section(name: str) -> str | None:
    """Разрешить ИМЯ в канонический раздел (identity…launcher) или None.

    ⚠️ ПОЧЕМУ «КТО» НЕ СТЕМ, А «КТО Я» — ЦЕЛАЯ ФРАЗА. §NAME однословный (стоп на первом
    пробеле — так же поступает wake-check.py, у него `first = name.split()[0]`), значит
    «§кто я» дал бы «кто» ОДНИМ словом. «кто» — обычное местоимение («кто-то», «никто
    не» и т.п.), стем на нём поймал бы ЛЮБОЕ упоминание, не только ссылку на identity.
    Поэтому «кто я» ловится ДО этого — целой фразой в самом SECTION_REF (см. выше),
    сюда попадает уже готовая строка «КТО Я» из PHRASE_CANON.
    """
    up = re.sub(r"\s+", " ", name.strip()).upper()
    if up in PHRASE_CANON:
        return PHRASE_CANON[up]
    if up in LATIN_UPPER:
        return LATIN_UPPER[up]
    first = up.split()[0] if up.split() else up
    if first in LATIN_UPPER:
        return LATIN_UPPER[first]
    for canon, stems in RU_STEMS.items():
        if any(stem in up for stem in stems):
            return canon
    return None


def _is_tomb(line: str) -> bool:
    if TOMB_RX.search(line):
        return True
    stripped = line.strip()
    if stripped.startswith("|") and NAME_IN_CELL.search(line):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        for i, c in enumerate(cells[:-1]):
            if NAME_IN_CELL.search(c) and cells[i + 1]:
                return True
    return False


def find_defects(sections: dict[str, str], archive_rows: list[tuple]):
    """По словарю {раздел: тело} и списку кусков архива роли — (found, archive, orphans, tomb_skipped).

    found/archive/orphans — списки строк «[раздел:строка] форма ИМЯ → …», tomb_skipped — число.
    """
    heads = set()
    for body in sections.values():
        for h in _headers(body):
            heads.add(_head_key(h))
    heads_join = "\n".join(heads)
    filled = {s for s, b in sections.items() if (b or "").strip()}

    found, archive, orphans = [], [], []
    tomb_skipped = 0

    def resolve(name: str, kind: str, where: str, line: str):
        canon = _canon_section(name)
        if canon:
            if canon in filled:
                found.append(f"{where} {kind}«{name[:30]}» → раздел {canon}")
            else:
                orphans.append(f"{where} {kind}«{name[:30]}» → раздел {canon} "
                                f"признан, но пуст/отсутствует у этой роли")
            return
        first = name.split()[0] if name.split() else name
        if len(first) < 3:
            return  # короткий обрывок — не имя (та же граница, что в wake-check.py)
        if first.upper() in heads_join or name.upper() in heads_join:
            found.append(f"{where} {kind}«{name[:30]}» → заголовок блока в памяти")
            return
        needle = name.upper()
        for _id, sec, topic, body in archive_rows:
            if needle in (topic or "").upper() or needle in (body or "").upper():
                archive.append(
                    f"{where} {kind}«{name[:30]}» → в архиве ({sec}); достать: "
                    f"python memory-archive.py --role <РОЛЬ> --find \"{name}\"")
                return
        orphans.append(f"{where} {kind}«{name[:30]}» — нет нигде: {line.strip()[:90]}")

    for sec, body in sections.items():
        for ln, line in enumerate((body or "").split("\n"), 1):
            if _is_tomb(line):
                tomb_skipped += 1
                continue
            where = f"[{sec}:{ln}]"
            for m in SECTION_REF.finditer(line):
                resolve(m.group(1).strip(), "§", where, line)
            for m in BLOCK_OR_SECTION.finditer(line):
                resolve(m.group(1).strip(), "блок/раздел ", where, line)
    return found, archive, orphans, tomb_skipped


def check_role(con, role: str, verbose: bool = True, soft: bool = False):
    rows = con.execute(
        "SELECT section, body FROM phoenix WHERE role=? ORDER BY section", (role,)
    ).fetchall()
    if not rows:
        print(f"⚪ {role}: разделов памяти нет — судить нечем")
        return None
    sections = {s: b for s, b in rows}
    try:
        archive_rows = con.execute(
            "SELECT id, section, topic, body FROM phoenix_archive WHERE role=?", (role,)
        ).fetchall()
    except sqlite3.OperationalError:
        archive_rows = []  # таблицы архива в этой базе нет — не отказ, архивный исход просто недостижим

    found, archive, orphans, tomb = find_defects(sections, archive_rows)
    mark = "🔴" if orphans else "✅"
    print(f"{mark} {role}: найден {len(found)} · в архиве {len(archive)} · "
          f"без адресата {len(orphans)} · пометок о снятии пропущено {tomb}")
    if verbose:
        # ⚠️-ПРЕФИКС ТОЛЬКО В --soft: guard-all.py::sub_guard() пробрасывает в общий
        # прогон СТРОКИ, начатые «⚠️»/«ℹ️», НЕ КРАСЯ его (subprocess вернёт 0) — так
        # долг остаётся видимым, а вызывающая роль не отвечает за ЧУЖУЮ память.
        for line in orphans:
            prefix = "⚠️ " if soft else "   "
            print(f"{prefix}без адресата · {line}")
        for line in archive:
            print(f"   в архиве     · {line}")
    return len(found), len(archive), len(orphans), tomb


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None)
    ap.add_argument("--role", default=None, help="одна роль (ВЕРХНИМ регистром); без флага — все")
    ap.add_argument("--quiet", action="store_true", help="без построчных находок, только числа")
    ap.add_argument("--soft", action="store_true",
                    help="код 0 всегда; находки «без адресата» — строками с ⚠️ (для общего прогона)")
    a = ap.parse_args()
    db = Path(a.db) if a.db else mezo_paths.live_db()
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        con.execute("SELECT 1 FROM phoenix LIMIT 1")
    except sqlite3.Error as e:
        print(f"⛔ память не прочитана ({e}) — НЕ ПРОВЕРЕНО, это не «чисто»")
        return 2

    if a.role:
        roles = [a.role]
    else:
        roles = [r for (r,) in con.execute("SELECT DISTINCT role FROM phoenix ORDER BY role")]

    if not roles:
        print("⚪ памяти ролей в этой базе нет вовсе — судить нечем")
        con.close()
        return 0

    totals = [0, 0, 0, 0]
    judged_any = False
    for role in roles:
        res = check_role(con, role, verbose=not a.quiet, soft=a.soft)
        if res is not None:
            judged_any = True
            for i, v in enumerate(res):
                totals[i] += v
    con.close()

    if not judged_any:
        print("⚪ ни у одной из запрошенных ролей памяти нет — судить нечем")
        return 0

    f, a_, o, t = totals
    print(f"\nИТОГ: ролей {len(roles)} · найдено {f} · в архиве {a_} · "
          f"без адресата {o} · пометок о снятии пропущено {t}")
    if a.soft:
        print("мягкий режим: общий прогон не проваливается")
        return 0
    return 1 if o else 0


if __name__ == "__main__":
    sys.exit(main())
