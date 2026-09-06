# -*- coding: utf-8 -*-
"""guard-stale-commands.py — признак «исполняемая строка старше правки инструмента».

ОТКУДА ВЗЯЛСЯ. Контур-потребитель прислал наблюдение (мост, 2026-08-06): у одной их роли
в памяти лежали девять протухших исполняемых инструкций, две из которых нарушали прямые
запреты владельца ПЕРВЫМ ЖЕ действием новой сессии. Механика:

    автор неделями правит КОНСТАТИРУЮЩИЕ абзацы и не трогает ИСПОЛНЯЕМЫЕ строки
    ⇒ автор своей поверхности систематически слеп к её исполняемой части

ЧТО ЭТО ПОДТВЕРДИЛОСЬ У НАС (замер живой БД 2026-08-06 14:52 UTC, до написания кода):
    исполняемых строк в памяти девяти ролей ......... 73
    форма вызова: абсолютная 57, относительных 0 .... канон соблюдают
    🔴 живой пример протухания: у роли OPSSRE в разделе «чем тебя разбудить» стоит
       «guard-all.py — 11 проверок», сохранено 27.07. Проверок сегодня 13.

⚠️ ЧЕМ МЕРЯЕТСЯ ДАТА ПРАВКИ — И ПОЧЕМУ НЕ mtime.
   mtime сбрасывает любое копирование, В ТОМ ЧИСЛЕ восстановление из бэкапа и `git checkout`.
   Ровно так 2026-07-26 сломался гард «замороженные md»: содержимое цело, mtime уехал,
   красное у всех навсегда по невиновной причине. ⇒ дата берётся из git-истории
   репозитория-бэкапа скриптов. Если копия в репо РАСХОДИТСЯ с живым файлом — это
   говорится вслух, а не проглатывается: тогда дата относится к другому содержимому.

⚠️ ПОДАЧА — РЕЛЯЦИЯ, А НЕ ПРИГОВОР (форма предложена STUD, #2784).
   Не «строка устарела» — такой вердикт роль заглушит пересохранением слепка, ничего
   не проверив. А «инструмент менялся тогда-то, ты записал строку тогда-то» — это факт,
   заглушить его нечем: пересохранение слепка сдвинет дату, но роль при этом ОБЯЗАНА
   перечитать строку, иначе сдвигать нечего.

    python guard-stale-commands.py --role PROTO
    python guard-stale-commands.py                 # все роли
    python guard-stale-commands.py --selftest      # доказать, что признак умеет краснеть
"""
import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

DB = mezo_paths.live_db()
LIVE_SCRIPTS = mezo_paths.live_scripts()
REPO = mezo_paths.container_root() / "atlas.agents-sync.db"   # git-история скриптов
REPO_SCRIPTS = REPO / "scripts"

EXEC = re.compile(r"^(python|py|git|dotnet|curl|npm|node|pwsh|powershell|bash|sh|cd)\b", re.I)
SCRIPT = re.compile(r"([\w\-]+\.py)")
PLACEHOLDER = re.compile(r"^<.*>$")


def git_changed_at(script_name: str):
    """Дата последней правки инструмента ПО ИСТОРИИ, а не по свойству файла.

    Возвращает (iso_date, note). note != None означает, что дате верить нельзя —
    и это ПЕЧАТАЕТСЯ, а не подавляется: молча принятая неверная дата хуже отсутствия
    признака, потому что даёт зелёное с видом проверенного.
    """
    live = LIVE_SCRIPTS / script_name
    inrepo = REPO_SCRIPTS / script_name
    if not live.exists():
        # Инструменты зоны v-next лежат отдельно от общих скриптов. Не искать их там —
        # значит объявить «дату взять неоткуда» у собственных же сторожей.
        alt = Path(__file__).resolve().parent / script_name
        if alt.exists():
            return None, ("инструмент зоны v-next: истории правок для него ещё нет "
                          "(лежит вне репозитория-бэкапа)")
        return None, f"файла нет в живых скриптах: {live}"
    if not inrepo.exists():
        return None, f"файла нет в репозитории-бэкапе — дату правки взять неоткуда"
    try:
        same = live.read_bytes() == inrepo.read_bytes()
    except OSError as e:
        return None, f"не прочитать: {e}"
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "log", "-1", "--format=%cI", "--", f"scripts/{script_name}"],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"git недоступен: {e}"
    if out.returncode != 0 or not out.stdout.strip():
        return None, "в git-истории файла нет"
    return out.stdout.strip(), (None if same else
                                "⚠️ копия в репозитории РАСХОДИТСЯ с живым файлом — "
                                "дата относится к другому содержимому")


def iso_to_utc(s: str) -> str:
    """'2026-08-06T16:09:26+02:00' -> '2026-08-06 14:09:26' (UTC).

    Смещение берётся ИЗ САМОЙ строки. Считать его константой — тот же класс, что
    сравнивать время БД с часами машины: две шкалы, выдаваемые за одну.
    """
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)([+-])(\d\d):(\d\d)", s)
    if not m:
        return s
    import datetime as dt
    y, mo, d, h, mi, sec, sign, oh, om = m.groups()
    t = dt.datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec))
    off = dt.timedelta(hours=int(oh), minutes=int(om))
    t = t - off if sign == "+" else t + off
    return t.strftime("%Y-%m-%d %H:%M:%S")


def collect(con, role=None):
    q = "SELECT role, section, body, saved_at FROM phoenix"
    args = []
    if role:
        q += " WHERE UPPER(role) = UPPER(?)"
        args.append(role)
    return list(con.execute(q, args))


def run(role=None, db_path=DB):
    if not Path(db_path).exists():
        print(f"⛔ ОТКАЗ: базы нет — {db_path}")
        return 2
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = collect(con, role)
    con.close()          # Windows держит файл открытым — самопроверка на временной базе иначе падает
    if not rows:
        print(f"⛔ ОТКАЗ: сохранённой памяти не найдено ({'роль ' + role if role else 'все роли'}). "
              f"Отсутствие данных — это отказ, а не зелёное.")
        return 2

    cache = {}
    findings, exec_lines, skipped = [], 0, []

    for r_role, section, body, saved_at in rows:
        for ln in (body or "").splitlines():
            s = ln.strip().lstrip(">").strip()
            s = re.sub(r"^[`*\-\d.)\s]+", "", s)
            if not EXEC.match(s):
                continue
            exec_lines += 1
            m = SCRIPT.search(s)
            if not m:
                continue
            name = m.group(1)
            if PLACEHOLDER.match(name) or "<" in name:
                continue                      # `<имя>.py` — шаблон, а не вызов
            if name not in cache:
                cache[name] = git_changed_at(name)
            changed, note = cache[name]
            if changed is None:
                skipped.append((name, note))
                continue
            changed_utc = iso_to_utc(changed)
            if changed_utc > (saved_at or ""):
                findings.append((r_role, section, name, changed_utc, saved_at, s[:90], note))

    # ── ОТЧЁТ ────────────────────────────────────────────────────────────────
    print(f"📏 охват: {'роль ' + role.upper() if role else f'все роли ({len(set(r[0] for r in rows))})'}"
          f" · секций {len(rows)} · исполняемых строк {exec_lines}")
    print(f"   дата правки инструмента — ИЗ GIT-ИСТОРИИ {REPO.name}, не из времени файла "
          f"(время файла сбрасывается копированием)")
    if skipped:
        uniq = {}
        for n, why in skipped:
            uniq[n] = why
        print(f"   ⚠️ БЕЗ ПРОВЕРКИ {len(uniq)} инструментов — дату взять неоткуда:")
        for n, why in sorted(uniq.items()):
            print(f"      · {n}: {why}")
        print(f"      это НЕ зелёное по ним — это отсутствие проверки, названное вслух")

    # ── ЖЁЛТОЕ: дата правки. Справочно, В EXIT-КОД НЕ ВХОДИТ ──────────────────
    # Замер 2026-08-06 14:57 UTC: 25 срабатываний на 9 ролях. Почти все — правка
    # ВНУТРЕННОСТЕЙ инструмента, от которой записанная команда не портится
    # (в guard-all добавили проверку — строка вызова та же). Оставить это красным
    # значило бы сделать прогон красным навсегда: ровно то, за что я сам ловил
    # сторож времени (19 красных без окна). Красное без срока годности за сутки
    # становится фоном, и первым спишут на фон НАСТОЯЩИЙ сигнал.
    if findings:
        print(f"\n🟡 {len(findings)} справочно: инструмент менялся ПОЗЖЕ, чем записана строка")
        print("   Это РЕЛЯЦИЯ, а не приговор, и в код возврата НЕ входит: правка внутренностей")
        print("   команду не ломает. Смотреть, когда разбираешься со своей памятью.")
        by_role = {}
        for r_role, section, name, changed, saved, line, note in findings:
            by_role.setdefault(r_role, set()).add(name)
        for r_role in sorted(by_role):
            print(f"      {r_role}: {', '.join(sorted(by_role[r_role]))}")

    # ── КРАСНОЕ: число рядом с командой РАСХОДИТСЯ С ФАКТОМ ───────────────────
    stale = check_claimed_numbers(rows)
    if not stale:
        print("\n✅ чисел, объявленных рядом с командой и разошедшихся с фактом, не найдено")
        return 0
    print(f"\n🔴 {len(stale)}: рядом с командой стоит число, которого уже нет")
    print("   Это НЕ мнение: факт получен вызовом самого инструмента, а не чтением кода.")
    for r_role, section, claimed, fact, line, saved in stale:
        print(f"\n   [{r_role}/{section}]  заявлено {claimed}, на самом деле {fact}")
        print(f"      записано: {saved} UTC")
        print(f"      строка: {line}")
    return 1


# ═════════════════════════════════════════════════════════════════════════════
# ЧИСЛО РЯДОМ С КОМАНДОЙ ПРОТИВ ФАКТА
#
# 🪤 ПОЧЕМУ ЗДЕСЬ ЕСТЬ САМОПРОВЕРКА ПАТТЕРНА, А НЕ ПРОСТО ПАТТЕРН.
#    Первый вариант этой проверки нашёл 0 срабатываний — при том, что нужная строка
#    в базе ЕСТЬ и найдена прямым поиском («11 проверок» у одной роли, факт 13).
#    Выражение молча не совпадало, и признак печатал успокаивающее «чисто».
#    ⇒ Паттерн прогоняется по ЭТАЛОННОЙ строке, ответ для которой известен заранее.
#      Не совпал на эталоне — это ОТКАЗ инструмента, а не зелёное по контуру.
#      Стоимость этой ошибки сегодня: шесть минут отладки и почти сданный ложный ноль.
# ═════════════════════════════════════════════════════════════════════════════

CLAIM = re.compile(r"(\d+)\s*проверок")
CLAIM_PROBE = "guard-all.py — 11 проверок (свежесть)"      # известный ответ: 11

# Инструменты, которые можно ВЫЗВАТЬ ради счёта: только читающие, без побочных действий.
# Список белый намеренно: запускать чужой инструмент вслепую — заводить сторожа,
# который сам меняет то, что охраняет.
COUNTABLE = {"guard-all.py": (r"\((\d+)\s+проверок\)", 180)}


def check_claimed_numbers(rows):
    m = CLAIM.search(CLAIM_PROBE)
    if not m or m.group(1) != "11":
        print("⛔ ОТКАЗ: выражение поиска не совпало на эталонной строке — "
              "признак сломан и МОЛЧАЛ БЫ вместо того, чтобы находить")
        return []

    facts = {}
    for name, (pat, timeout) in COUNTABLE.items():
        p = LIVE_SCRIPTS / name
        if not p.exists():
            continue
        try:
            out = subprocess.run([sys.executable, str(p)], capture_output=True,
                                 text=True, timeout=timeout)
            fm = re.search(pat, (out.stdout or "") + (out.stderr or ""))
            if fm:
                facts[name] = int(fm.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
    if not facts:
        print("   ⚠️ факт не получен ни у одного инструмента — проверки чисел НЕ БЫЛО")
        return []

    out = []
    for r_role, section, body, saved_at in rows:
        for ln in (body or "").splitlines():
            for name, fact in facts.items():
                if name.replace(".py", "") not in ln:
                    continue
                cm = CLAIM.search(ln)
                if cm and int(cm.group(1)) != fact:
                    out.append((r_role, section, int(cm.group(1)), fact,
                                ln.strip()[:100], saved_at))
    return out


# ═════════════════════════════════════════════════════════════════════════════

def selftest():
    """Признак обязан краснеть на подложенном случае и зеленеть на чистом.
    Проверка идёт на ВРЕМЕННОЙ базе — живая не трогается."""
    import tempfile
    # 🪤 СЧЁТ СЛУЧАЕВ — норма STUD (#2991): «прогон, не назвавший ЧИСЛО выполненных
    #    проверок, не считается прогоном». Он поймал у себя прогон, вернувший УСПЕХ
    #    при НУЛЕ выполненных тестов: «196 прошли» и «0 прошли» дают один код возврата.
    ok = True
    cases = 0
    CMD = f"python {mezo_paths.live_scripts().as_posix()}/guard-all.py"

    def db_with(tmp, fname, body, saved="2020-01-01 00:00:00"):
        p = Path(tmp) / fname
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
        if body is not None:
            con.execute("INSERT INTO phoenix VALUES ('TEST','rebirth',?,?)", (body, saved))
        con.commit(); con.close()
        return p

    with tempfile.TemporaryDirectory() as tmp:
        # ① ПРОТУХШЕЕ ЧИСЛО рядом с командой — обязано краснеть
        print("── ① протухшее число ─────────────────────────────────────────")
        cases += 1
        if run("TEST", db_with(tmp, "a.db", f"{CMD} — 11 проверок")) != 1:
            print("🔴 САМОПРОВЕРКА: не покраснел на заведомо неверном числе"); ok = False

        # ② ВЕРНОЕ число — обязано зеленеть. Это РАЗЛИЧАЮЩИЙ тест: без него
        #    признак, красящий всё подряд, прошёл бы ①.
        print("── ② верное число ────────────────────────────────────────────")
        cases += 1
        if run("TEST", db_with(tmp, "b.db", f"{CMD} — 13 проверок")) != 0:
            print("🔴 САМОПРОВЕРКА: краснеет на ВЕРНОМ числе — ложная тревога"); ok = False

        # ③ РАЗЛИЧАЮЩИЙ: очень старая строка БЕЗ числа даёт жёлтое, но НЕ красное.
        #    Ровно то разделение, ради которого дата выведена из кода возврата.
        print("── ③ старая строка без числа ─────────────────────────────────")
        cases += 1
        if run("TEST", db_with(tmp, "c.db", CMD)) != 0:
            print("🔴 САМОПРОВЕРКА: старая строка без числа даёт красное — "
                  "прогон станет красным навсегда"); ok = False

        # ④ РАЗЛИЧАЮЩИЙ: отсутствие данных = ОТКАЗ, а не зелёное
        print("── ④ пустая выборка ──────────────────────────────────────────")
        cases += 1
        if run("НЕТ_ТАКОЙ_РОЛИ", db_with(tmp, "d.db", None)) != 2:
            print("🔴 САМОПРОВЕРКА: пустая выборка прошла как зелёное"); ok = False

    if cases == 0:
        print("\n⛔ ОТКАЗ: самопроверка не выполнила НИ ОДНОГО случая — это не «чисто»")
        return 2
    print(f"\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} — "
          f"ВЫПОЛНЕНО {cases} случаев")
    print("   краснеет на неверном числе · молчит на верном · старую строку без числа "
          "держит жёлтой · на пустоте ОТКАЗЫВАЕТ")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="исполняемая строка старше правки инструмента")
    ap.add_argument("--role")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else run(a.role, a.db))
