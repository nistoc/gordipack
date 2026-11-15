# -*- coding: utf-8 -*-
r"""ПРИЁМКА отбора записей памяти по слову: регистр и исходы — карточка #784.

ПОВОД. Отбор `memory-records.py --отобрать <слово>` сворачивал регистр средствами базы,
а в SQLite этой сборки `lower()` и `LIKE` сворачивают его ТОЛЬКО для латиницы: русское слово
в другом написании давало ноль, и инструмент уверенно говорил, что искать было нечего.
Починено по карточке #784 (функция `fold`, регистр сворачивает Python); приёмка здесь —
для пакета: прежняя лежала в черновой папке чата и до пакета не доехала.

⛔ ЖИВОЙ БАЗЫ НЕ КАСАЕТСЯ ВОВСЕ. Работает на ПОДСТАВНОЙ базе: схема живого контура БЕЗ его
строк (mezo_stand.empty_db), свои записи `phoenix_records` вставляются SQL-ом. Отпечатка
живой базы здесь поэтому нет и быть не должно: измерять нечего.
📌 При РУЧНОЙ приёмке на копии живой базы «живая база не писана» доказывается ОТБОРОМ ЖУРНАЛА
ПО АВТОРУ И ЧАСУ, а не отпечатком всей базы: отпечаток на общей базе не отличает свою руку от
чужой, если в то же окно писал кто-то ещё.

Какую копию испытываем — тем же рычагом, что у соседних приёмок (карточка #148):
MEZO_SCRIPTS_ROOT (mezo_target.py). Схему берёт из базы, названной MEZO_LIVE_DB (только чтение).

Случаи:
  ① три написания русского слова (строчные · Прописная · ВСЕ ПРОПИСНЫЕ) дают ОДНО число,
    равное ИСТИНЕ, посчитанной в Python по строкам стенда; истина не пуста             РАЗЛИЧАЮЩИЙ
  ② нуль находок при живых записях: слова «значит» нет, и граница названа («ё» против «е»,
    латинская буква внутри русского слова)                                              КОНТРОЛЬ
  ③ три исхода — три кода выхода, взятые из самого инструмента: нашлось 0 · не нашлось при
    живых записях 2 · записей у роли нет вовсе 3                                        КОНТРОЛЬ
  ④ латиница: три написания — одно число, равное истине                                КОНТРОЛЬ
  ⑤ ОБРАТНЫЙ ХОД, ПРЕДВАРИТЕЛЬНЫЙ: копия с прежней строкой отбора ЗАПУСТИЛАСЬ — есть числа
  ⑥ ОБРАТНЫЙ ХОД: прежняя строка отбора возвращена → случай ① проваливается, и признак —
    «ТРИ ЧИСЛА РАЗОШЛИСЬ», а не «ноль на заглавном» (он случайный: зависит от того, лежит
    ли слово заглавными буквами в каком-нибудь теле). Валится РОВНО ①: ②–④ целы.
Якорь поломки ищется точной строкой и должен встретиться РОВНО ОДИН раз. Поломанная копия
лежит в каталоге стенда, а не пакета, ВМЕСТЕ с соседями (иначе она не запустится, и случай
провалится по чужой причине).

Зовут так:
    MEZO_SCRIPTS_ROOT=<каталог копии> MEZO_LIVE_DB=<живая база, схема> \
        python vnext/prototype/bite-memory-records-case.py
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

ROLE = "PROTO"
EMPTY_ROLE = "ALONE"         # роль, у которой записей нет вовсе
ANCHOR = 'clauses.append("(fold(subject) LIKE fold(?) OR fold(body) LIKE fold(?))")'
BROKEN = 'clauses.append("(subject LIKE ? OR lower(body) LIKE lower(?))")'

print(f"⚖️ испытуется: {mezo_target.label()}")
tool = mezo_target.script("memory-records.py")

# Строки стенда: (раздел, предмет, тело). Слово «владелец» лежит в предмете строчными с
# прописной и заглавными по-разному; есть записи без него и латиница.
ROWS = [
    ("plan", "Владелец сказал", "про права"),
    ("plan", "права", "Владелец и ВЛАДЕЛЕЦ"),
    ("plan", "пилот", "слово владельца"),
    ("plan", "ёлка", "Елка"),
    ("plan", "pilot", "Pilot flies"),
    ("plan", "другое", "ничего"),
]

failures = []


def check(num, ok, said):
    print(f"{'✅' if ok else '🔴'} {num} {said}")
    if not ok:
        failures.append(f"{num} {said}")
    return ok


def spellings(piece):
    return [piece.lower(), piece[:1].upper() + piece[1:].lower(), piece.upper()]


def fill(db):
    conn = sqlite3.connect(str(db))
    try:
        for n, (section, subject, body) in enumerate(ROWS):
            conn.execute(
                "INSERT INTO phoenix_records (role, section, subject, body, body_chars, ord, "
                "created_by) VALUES (?,?,?,?,?,?,?)",
                (ROLE, section, subject, body, len(body), n, "стенд приёмки"))
        conn.commit()
    finally:
        conn.close()


def truth(piece):
    """ИСТИНА в Python по строкам стенда: сколько записей роли несут кусок в предмете или теле."""
    key = piece.casefold()
    return sum(1 for _s, subj, body in ROWS
               if key in subj.casefold() or key in body.casefold())


def run(tool_path, container, db, role, *args):
    env = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-X", "utf8", str(tool_path), "--db", str(db),
                        "--role", role, *args],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def count_of(out):
    """Число записей из шапки отбора («→ записей N»); None — шапки нет вовсе (отказ)."""
    m = re.search(r"→ записей (\d+)", out)
    return int(m.group(1)) if m else None


def numbers(ctx, piece):
    got = []
    for sp in spellings(piece):
        code, out = run(ctx["tool"], ctx["container"], ctx["db"], ROLE, "--отобрать", sp)
        got.append((sp, count_of(out), code))
    return got


def fmt(got):
    return " · ".join(f"{sp}→{n if n is not None else 0} (код {c})" for sp, n, c in got)


def case_spellings(ctx):
    t = truth("владелец")
    got = numbers(ctx, "владелец")
    nums = {n if n is not None else 0 for _sp, n, _c in got}
    ok = t > 0 and nums == {t}
    return ok, f"«владелец»: {fmt(got)} · истина {t} · числа {sorted(nums)}", nums


def case_zero(ctx):
    code, out = run(ctx["tool"], ctx["container"], ctx["db"], ROLE, "--отобрать",
                    "такогословавпамятинет")
    ok = ("значит" not in out and "совпадений нет" in out and "«ё» и «е»" in out
          and "латинская буква внутри русского слова" in out)
    return ok, (f"ноль находок: код {code} · слова «значит» нет: "
                f"{'да' if 'значит' not in out else 'НЕТ'} · граница названа: "
                f"{'да' if '«ё» и «е»' in out else 'НЕТ'}"), None


def case_exits(ctx):
    # «нашлось» — по латинскому куску: строчное русское слово поломка регистра уже роняет
    # в «не нашлось», и случай ③ краснел бы по причине случая ①, а не по своей
    c_found, _ = run(ctx["tool"], ctx["container"], ctx["db"], ROLE, "--отобрать", "pilot")
    c_none, _ = run(ctx["tool"], ctx["container"], ctx["db"], ROLE, "--отобрать",
                    "такогословавпамятинет")
    c_norec, out = run(ctx["tool"], ctx["container"], ctx["db"], EMPTY_ROLE, "--отобрать",
                       "право")
    ok = (c_found, c_none, c_norec) == (0, 2, 3) and "НЕТ ВОВСЕ" in out
    return ok, (f"нашлось → {c_found} · не нашлось при живых записях → {c_none} · "
                f"записей у роли нет вовсе → {c_norec} (ждали 0 · 2 · 3)"), None


def case_latin(ctx):
    t = truth("pilot")
    got = numbers(ctx, "pilot")
    ok = t > 0 and all((n or 0) == t and c == 0 for _sp, n, c in got)
    return ok, f"латиница: {fmt(got)} · истина {t}", None


CASES = [("①", case_spellings), ("②", case_zero), ("③", case_exits), ("④", case_latin)]


def run_cases(ctx):
    return {num: fn(ctx) for num, fn in CASES}


stand = mezo_stand.new("bite-memory-records-case")
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
    mezo_stand.seed_roles(db, [ROLE, EMPTY_ROLE])
    fill(db)
    print(f"   стенд: {len(ROWS)} записей у роли {ROLE}, у роли {EMPTY_ROLE} записей нет")

    def make_copy(name, breaks=None):
        d = stand / name
        copy = mezo_stand.copy_tool(tool, d)
        # соседний инструмент подключается ПО ПУТИ файла, а не по имени — копируем его сами
        mezo_stand.copy_tool(tool.with_name("memory-archive.py"), d)
        if breaks:
            text = copy.read_text(encoding="utf-8")
            for anchor, replacement in breaks:
                text = text.replace(anchor, replacement)
            copy.write_text(text, encoding="utf-8")
        return copy

    healthy = make_copy("tool-healthy")
    ctx = {"tool": healthy, "container": container, "db": db}
    res = run_cases(ctx)
    for num, (ok, said, _x) in res.items():
        check(num, ok, said)

    # ══ ОБРАТНЫЙ ХОД: поломку строит сама приёмка рядом с соседями инструмента
    text = healthy.read_text(encoding="utf-8")
    hits = text.count(ANCHOR)
    if hits != 1:
        print(f"🔴 ⑤–⑥ ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ (нашлось {hits}) — поломка не построена.")
        print(f"   якорь: {ANCHOR}")
        print("   Это НЕ «защита цела»: без поломки обратный ход ничего не доказывает.")
        failures.append("⑤–⑥ якорь поломки не найден ровно один раз")
    else:
        broken = make_copy("tool-broken", [(ANCHOR, BROKEN)])
        bctx = {"tool": broken, "container": container, "db": db}
        bgot = numbers(bctx, "владелец")
        # ⑤ копия ЗАПУСТИЛАСЬ: у каждого вызова есть шапка отбора или честный ноль с кодом 2,
        # а не падение Python (у падения кода 1 и нет ни шапки, ни слов отбора)
        _c, probe = run(broken, container, db, ROLE, "--отобрать", "Владелец")
        started = all(c in (0, 2) for _sp, _n, c in bgot) and count_of(probe) is not None
        check("⑤", started, f"копия с прежней строкой отбора запустилась: {fmt(bgot)}")
        bnums = {n if n is not None else 0 for _sp, n, _c in bgot}
        check("⑥", started and len(bnums) > 1,
              f"ОБРАТНЫЙ ХОД: три числа РАЗОШЛИСЬ — {sorted(bnums)} (истина {truth('владелец')}) · "
              f"признак — расхождение чисел, а не «ноль на заглавном»")
        bres = run_cases(bctx)
        red = sorted(k for k, v in bres.items() if not v[0])
        for num, (ok, said, _x) in bres.items():
            print(f"   · на поломке {num}: {'прошёл' if ok else 'провалился'} — {said}")
        check("⑥-бис", red == ["①"],
              f"поломка валит РОВНО случай трёх написаний: провалились "
              f"{', '.join(red) or 'никто'} (ждали ①)")

    print()
    total = len(CASES) + 3
    failed = len(failures)
    print(f"ИТОГ: {max(total - failed, 0)} из {total}")
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {failed}")
        for f in failures:
            print(f"   · {f}")
        sys.exit(mezo_stand.finish(1))
    print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — регистр сворачивает Python, три исхода различимы кодом, "
          "поломка валит ровно свой случай.")
    print("⛔ Чего приёмка НЕ доказывает: «ё» против «е» и латинскую букву внутри русского "
          "слова (отбор их не лечит и говорит об этом), а также отбор по дате и по снятым.")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
