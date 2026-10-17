#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА замера «понятна ли карточка без чата» (measure-card-selfcontained.py), графа «зона».

Карточка #686 (2026-10-17): приписка «@РОЛЬ» в графе «зона» засчитывается только с именами из
таблицы roles той же базы, а не с девятью именами Atlas. У каждого различающего случая — две
контрольные карточки: «рука названа словом» (графа обязана быть ✅) и «руки нет» (обязана быть ·).
Без них молчание графы ничего не доказывает: графа, ставящая всем одно и то же, прошла бы любой
случай с одним ожиданием.

⛔ ЧИСЛО СЛУЧАЕВ ЗДЕСЬ НЕ ПИШЕТСЯ СЛОВОМ — его печатает прогон.

  ⓪ замер запускается и печатает таблицу (с 09.08 по 17.10 он падал NameError на первой строке)
  ① контур с ролями Atlas: «@COORD» засчитан
  ①-бис тот же контур: «@COORDу» (русское окончание) засчитан, как при прежнем образце
  ② ВСТРЕЧНЫЙ: контур с ролями COORD-A и ZETA — «@ZETA» засчитан
  ③ ВСТРЕЧНЫЙ: тот же контур — «@COORD» (такой роли в нём нет) не засчитан
  ④ нарочная поломка «вернуть литерал» (девять имён Atlas) проваливает ② и ③
  ⑤ таблицы ролей нет — «@COORD» не засчитан, и это сказано вслух
  ③-бис ВСТРЕЧНЫЙ, обратная сторона ③: контур с ролями COORD и ZETA — «@COORD-B» (имя соседа,
        в контуре такой роли нет) не засчитан
  ⑥ нарочная поломка «дефис не часть имени» проваливает ③-бис

🪤 ③-бис и ⑥ — записка #5913, поломка B4 (2026-10-17). Шапка zone_pattern обещает «COORD-A ≠ COORD»,
а ③ испытывал это только в одну сторону: в контуре COORD-A, в карточке @COORD. Карточка, пришедшая
от соседа с @COORD-B, в контуре с COORD не охранялась — без дефиса в запрете за именем она
засчитывалась как рука COORD.

⛔ Живой базы не касается: свои временные базы в песочнице.
"""
import os
import re
import sqlite3
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале
import mezo_paths  # noqa: E402 — контейнер для копии замера под нарочной поломкой

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURE = os.path.join(HERE, "measure-card-selfcontained.py")

ATLAS_ROLES = ("COORD", "CORE", "ING", "STUD", "TAXO", "RCC", "OPSSRE", "PROTO", "CHROME")
# ZETA не начинается ни с одного имени Atlas (иначе прежний образец без границы слова засчитал бы
# её по совпадению начала, как COORD-A по COORD).
FOREIGN_ROLES = ("COORD-A", "ZETA")

# Контрольные карточки: номера 2 и 3 в каждой базе. Испытуемая — номер 1.
HAND_WORD = "Правку вносит дежурный. Дата 2026-10-17."
NO_HAND = "Просто текст карточки без приписки, кто делает. Дата 2026-10-17."

# Нарочная поломка «вернуть литерал»: образец графы снова из девяти имён Atlas, без границы слова,
# и «имена известны» всегда — ровно образец до карточки #686.
LITERAL_ANCHOR = '    return re.compile("|".join([ZONE_WORDS] + alts), re.I), bool(names)\n'
LITERAL_BROKEN = ('    return re.compile(ZONE_WORDS + '
                  r'r"|@(?:COORD|CORE|STUD|ING|TAXO|RCC|OPSSRE|PROTO|CHROME)", re.I), True'
                  "\n")
# Контур, где есть COORD, а в карточке — имя соседа COORD-B (обратная сторона FOREIGN_ROLES).
NEAR_ROLES = ("COORD", "ZETA")
# Нарочная поломка «дефис не часть имени»: за именем снова запрещены только буква, цифра и «_».
HYPHEN_ANCHOR = 'alts = [rf"@{re.escape(n)}(?![A-Za-z0-9_-])" for n in'
HYPHEN_BROKEN = 'alts = [rf"@{re.escape(n)}(?![A-Za-z0-9_])" for n in'

ROW = re.compile(r"^\s*#(\d+)\s+\S+\s+(.+?)\s+(\d+)\s+(\d+)\s*$")
ZONE_COL = 4  # повод · числа · граница · проверка · ЗОНА · цена · срок


def build(path: str, subject: str, roles=ATLAS_ROLES):
    """Три карточки: испытуемая (subject), «рука названа словом», «руки нет».
    roles: имена таблицы roles; None — таблицы нет вовсе."""
    con = sqlite3.connect(path)
    if roles is not None:
        con.execute("CREATE TABLE roles (role TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO roles (role) VALUES (?)", [(r,) for r in roles])
    con.execute("""CREATE TABLE backlog (id INTEGER PRIMARY KEY, role TEXT, status TEXT,
                   title TEXT, body_md TEXT, done_when TEXT, created_at TEXT)""")
    for i, body in enumerate((subject, HAND_WORD, NO_HAND), 1):
        con.execute("INSERT INTO backlog VALUES (?, 'PROTO', 'open', ?, ?, '', '2026-10-17')",
                    (i, f"пробная карточка {i}", body))
    con.commit()
    con.close()


def run(path: str, measure=MEASURE):
    r = subprocess.run([sys.executable, measure, "--db", path, "--full", "--last", "10"],
                       capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "MEZO_CONTAINER": os.environ.get(
                           "MEZO_CONTAINER") or str(mezo_paths.container_root())})
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def zones(out: str) -> dict:
    """Номер карточки → засчитана ли графа «зона»."""
    got = {}
    for line in out.splitlines():
        m = ROW.match(line)
        if m:
            marks = m.group(2).split()
            if len(marks) == 7:
                got[int(m.group(1))] = marks[ZONE_COL] == "✅"
    return got


def broken_copy(tmp: str, sub: str, anchor: str, replacement: str):
    """Копия замера с нарочной поломкой в tmp/<sub>; не легла — (None, причина).
    Своя папка на каждую поломку: в общей вторая копия затёрла бы первую."""
    d = os.path.join(tmp, sub)
    os.makedirs(d, exist_ok=True)
    text = open(MEASURE, encoding="utf-8").read()
    if text.count(anchor) != 1:
        return None, f"поломка не легла: якорь найден {text.count(anchor)} раз"
    with open(os.path.join(d, os.path.basename(MEASURE)), "w", encoding="utf-8") as f:
        f.write(text.replace(anchor, replacement))
    # замер подключает соседей: разбор ссылок, пути машины и подсказки — копия без них не встанет
    for name in ("check-dangling-refs.py", "mezo_paths.py", "mezo_hints.py"):
        with open(os.path.join(HERE, name), encoding="utf-8") as src, \
                open(os.path.join(d, name), "w", encoding="utf-8") as dst:
            dst.write(src.read())
    return os.path.join(d, os.path.basename(MEASURE)), ""


def literal_copy(tmp: str):
    """Копия замера с нарочной поломкой «вернуть литерал»."""
    return broken_copy(tmp, "measure-copy", LITERAL_ANCHOR, LITERAL_BROKEN)


CASES = 0
DIFFERENTIATING = 0


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    """Число случаев СЧИТАЕТСЯ, а не пишется словом в подписи."""
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def judged(out: str, expect: bool):
    """(годен ли случай, подпись): испытуемая карточка дала expect, контроли — ✅ и ·."""
    z = zones(out)
    subject, hand, none = z.get(1), z.get(2), z.get(3)
    controls = hand is True and none is False
    ok = subject is expect and controls
    sign = {True: "✅", False: "·", None: "строки нет"}
    return ok, (f"испытуемая {sign[subject]} (ждём {sign[expect]}) · контроли: «рука словом» "
                f"{sign[hand]}, «руки нет» {sign[none]}"
                + ("" if controls else " — контроль НЕ сошёлся, случай не зачитывается"))


def main() -> int:
    tmp = str(mezo_stand.new("bite-card-selfcontained-"))
    ok = True

    # ⓪ + ① контур с ролями Atlas
    p1 = os.path.join(tmp, "atlas.db")
    build(p1, "Правку сделает @COORD. Дата 2026-10-17.")
    out1, code1 = run(p1)
    started = code1 == 0 and "ЗАМЕР:" in out1 and len(zones(out1)) == 3
    ok &= case("⓪ замер запускается и печатает таблицу", started,
               f"код {code1} · строк таблицы {len(zones(out1))} из 3"
               + ("" if started else f" · вывод: {out1.strip()[-200:]}"))
    good, sign = judged(out1, True)
    ok &= case("① контур с ролями Atlas: «@COORD» засчитан в графе «зона»", good, sign)

    p1b = os.path.join(tmp, "atlas-suffix.db")
    build(p1b, "Это решение @COORDу на подпись. Дата 2026-10-17.")
    good, sign = judged(run(p1b)[0], True)
    ok &= case("①-бис тот же контур: «@COORDу» (русское окончание) засчитан, как при прежнем "
               "образце", good, sign)

    # ② ③ контур, где имён Atlas нет
    p2 = os.path.join(tmp, "zeta.db")
    build(p2, "Правку сделает @ZETA. Дата 2026-10-17.", roles=FOREIGN_ROLES)
    p3 = os.path.join(tmp, "coord-absent.db")
    build(p3, "Правку сделает @COORD. Дата 2026-10-17.", roles=FOREIGN_ROLES)
    good, sign = judged(run(p2)[0], True)
    ok &= case("② ВСТРЕЧНЫЙ: контур с ролями COORD-A и ZETA — «@ZETA» засчитан", good, sign,
               differ=True)
    good, sign = judged(run(p3)[0], False)
    ok &= case("③ ВСТРЕЧНЫЙ: тот же контур — «@COORD» (такой роли в нём нет) не засчитан",
               good, sign, differ=True)

    # ④ нарочная поломка «вернуть литерал»
    broken, why = literal_copy(tmp)
    if broken is None:
        ok &= case("④ поломка «вернуть литерал» проваливает ② и ③", False,
                   f"⛔ НЕ ЗАПУСТИЛАСЬ: {why}", differ=True)
    else:
        z2, z3 = zones(run(p2, broken)[0]), zones(run(p3, broken)[0])
        caught = z2.get(1) is False and z3.get(1) is True
        ok &= case("④ поломка «вернуть литерал» (девять имён Atlas) проваливает ② и ③", caught,
                   f"под поломкой: «@ZETA» {'✅' if z2.get(1) else '·'} (под верным кодом ✅), "
                   f"«@COORD» {'✅' if z3.get(1) else '·'} (под верным кодом ·)", differ=True)

    # ③-бис ⑥ обратная сторона ③: в контуре COORD, в карточке — имя соседа @COORD-B
    p3b = os.path.join(tmp, "coord-near.db")
    build(p3b, "Правку сделает @COORD-B. Дата 2026-10-17.", roles=NEAR_ROLES)
    good, sign = judged(run(p3b)[0], False)
    ok &= case("③-бис ВСТРЕЧНЫЙ: контур с ролями COORD и ZETA — «@COORD-B» (имя соседа) не засчитан",
               good, sign, differ=True)

    broken6, why6 = broken_copy(tmp, "measure-copy-hyphen", HYPHEN_ANCHOR, HYPHEN_BROKEN)
    if broken6 is None:
        ok &= case("⑥ поломка «дефис не часть имени» проваливает ③-бис", False,
                   f"⛔ НЕ ЗАПУСТИЛАСЬ: {why6}", differ=True)
    else:
        z3b = zones(run(p3b, broken6)[0])
        ok &= case("⑥ поломка «дефис не часть имени» проваливает ③-бис", z3b.get(1) is True,
                   f"под поломкой: «@COORD-B» {'✅' if z3b.get(1) else '·'} (под верным кодом ·) — "
                   "засчитан как рука COORD", differ=True)

    # ⑤ таблицы ролей нет
    p5 = os.path.join(tmp, "no-roles.db")
    build(p5, "Правку сделает @COORD. Дата 2026-10-17.", roles=None)
    out5, _ = run(p5)
    good, sign = judged(out5, False)
    warned = "таблицы ролей в базе нет" in out5
    ok &= case("⑤ таблицы ролей нет — «@COORD» не засчитан, и это сказано вслух", good and warned,
               f"{sign} · предупреждение {'напечатано' if warned else 'НЕ напечатано'}",
               differ=True)

    print()
    print(f"✅ ПРОВЕРКА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}, "
          "у каждого контроль" if ok
          else "🔴 ПРОВЕРКА НЕ ПРИНЯТА — числа из неё нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
