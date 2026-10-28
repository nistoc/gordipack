r"""
md-phase.py — фаза перехода md → база в ЭТОМ контуре: показать и записать (признак meta.md_phase).

ЗАЧЕМ (issue #37 пакета, 2026-10-28). Шапка read-phoenix.py выбирала блок про md по одному
НАЛИЧИЮ правила md-to-sqlite-phased-cutover и всегда печатала «источник правды — БД» и «при
расхождении верь БД». Контур-потребитель с этим правилом на Фазе 1 (двойная запись, md главный)
получал в одном выводе состояние Фазы 4 — противоположное своему. Теперь фаза — явный признак
в таблице meta: шапка read-phoenix.py читает его (функция md_phase() там же), а пишет его
только этот инструмент. Что значит каждая фаза в контуре — в самом правиле; инструмент значений
не толкует, он хранит число и показывает, что из него напечатает шапка.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/md-phase.py                         # показать
    python <КОНТУР>/.mezosync/scripts/md-phase.py --set 4 --actor COORD   # записать фазу 1–4
    python <КОНТУР>/.mezosync/scripts/md-phase.py --clear --actor COORD   # убрать признак
    --dry-run — выполнить всё и НЕ сохранить.

Запись — строкой в meta и строкой в audit_log (action md_phase_set или md_phase_clear,
target meta.md_phase, diff «было → стало»). Рука — флаг --actor или MEZO_ROLE; умолчания нет:
фаза меняет первый экран каждой роли, и запись без имени в журнале правок не объяснить.

КОДЫ: 0 — показано или записано (в том числе «уже записано, менять нечего») · 2 — отказ
словами, база не тронута: фаза не из 1–4 · правила перехода в базе нет или оно снято (фаза без
правила шапке не нужна, и запись учила бы, что переход идёт) · рука не названа · нет таблицы meta.
"""

import argparse
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
import dryrun

HERE = Path(__file__).resolve().parent

# Признак и его толкование для шапки — ИЗ read-phoenix.py, а не переписаны здесь: два места
# с одним и тем же разбором разъехались бы молча при первой правке. main() у него под
# `if __name__ == "__main__"`, импорт только заводит имена (тот же приём, что в find-phoenix.py).
_spec = importlib.util.spec_from_file_location("_md_phase_read_phoenix", HERE / "read-phoenix.py")
_read_phoenix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_read_phoenix)
MD_RULE = _read_phoenix.MD_RULE
MD_PHASE_KEY = _read_phoenix.MD_PHASE_KEY
PHASES = ("1", "2", "3", "4")

# Что шапка read-phoenix.py напечатает при каждой фазе — одной строкой для человека.
HEADER_SAYS = {
    1: "фаза 1: md-файлы главные, база — второй экземпляр; при расхождении верь md",
    2: "фаза 2: md-файлы главные, база — второй экземпляр; при расхождении верь md",
    3: "фаза 3: база главная, md-файлы ещё пишутся вторым экземпляром; при расхождении верь БД",
    4: "фаза 4: «md ЗАМОРОЖЕНЫ», база — единственный источник; при расхождении верь БД",
    "unknown": "«ФАЗА НЕ ЗАПИСАНА» — сверься с правилом; кому верить при расхождении, шапка не говорит",
}


def refuse(text: str):
    # код 2, а не 1: sys.exit(строка) выходит единицей, и отказ сливался бы с поломкой
    print(f"⛔ ЗАПИСЬ НЕ СДЕЛАНА — {text}\n   База не тронута.", file=sys.stderr)
    sys.exit(2)


def rule_state(conn) -> str:
    """'active' · 'нет' · иное значение status (снято) — у ЭТОЙ базы, не из памяти."""
    try:
        row = conn.execute("SELECT status FROM rules WHERE rule_key = ?", (MD_RULE,)).fetchone()
    except sqlite3.OperationalError:
        return "нет"
    if not row:
        return "нет"
    return row[0] or "active"


def stored_value(conn):
    """Значение meta.md_phase как оно лежит в базе; None — строки нет; False — таблицы meta нет."""
    try:
        got = conn.execute("SELECT value FROM meta WHERE key = ?", (MD_PHASE_KEY,)).fetchone()
    except sqlite3.OperationalError:
        return False
    return got[0] if got else None


def header_line(conn) -> str:
    phase, why = _read_phoenix.md_phase(conn)
    if phase is None:
        state = rule_state(conn)
        if state == "нет":
            return "строки про md нет: правила перехода в этой базе нет, фаза шапке не нужна"
        return f"строки про md нет: правило перехода снято (status = {state})"
    text = HEADER_SAYS[phase]
    return f"{text} ({why})" if why else text


def pick_actor(flag) -> str:
    name = (flag or "").strip() or (os.environ.get("MEZO_ROLE") or "").strip()
    if not name:
        refuse("не названа рука: от чьего имени запись попадёт в журнал правок.\n"
               "   Назови её флагом --actor <РОЛЬ> или переменной среды MEZO_ROLE=<РОЛЬ>.")
    return name.upper()


def show(conn, db):
    state = rule_state(conn)
    value = stored_value(conn)
    rule_text = {"active": "действует", "нет": "в базе нет"}.get(state, f"снято (status = {state})")
    if value is False:
        value_text = "таблицы meta в базе нет"
    elif value is None:
        value_text = "не записан"
    else:
        value_text = str(value)
    print(f"📝 фаза перехода md → база (признак meta.{MD_PHASE_KEY}) · база: {db}")
    print(f"   правило {MD_RULE} ... {rule_text}")
    print(f"   признак meta.{MD_PHASE_KEY} ... {value_text}")
    print(f"   шапка read-phoenix.py печатает: {header_line(conn)}")
    if state == "active" and value in (None, False, ""):
        print(f"   👉 записать: python {HERE.as_posix()}/md-phase.py --set <1–4> --actor <РОЛЬ>")


def audit(conn, actor, action, diff):
    cur = conn.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                       (actor, action, f"meta.{MD_PHASE_KEY}", diff))
    return cur.lastrowid


def set_phase(conn, raw, actor_flag):
    value = (raw or "").strip()
    if value not in PHASES:
        refuse(f"фаза «{raw}» не из 1, 2, 3, 4.")
    state = rule_state(conn)
    if state != "active":
        why = "в базе нет" if state == "нет" else f"снято (status = {state})"
        refuse(f"правило {MD_RULE} {why}: фаза без правила шапке не нужна, а запись учила бы,\n"
               "   что переход идёт. Сначала правило (set-rule.py), потом фаза.")
    old = stored_value(conn)
    if old is False:
        refuse("таблицы meta в базе нет — признак хранить негде (база не по схеме пакета?).")
    actor = pick_actor(actor_flag)
    if old is not None and str(old).strip() == value:
        print(f"✅ уже записано: meta.{MD_PHASE_KEY} = {value} — менять нечего, журнал правок не тронут")
        print(f"   шапка read-phoenix.py печатает: {header_line(conn)}")
        return
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (MD_PHASE_KEY, value))
    was = "—" if old is None else str(old)
    row = audit(conn, actor, "md_phase_set", f"{was} → {value}")
    conn.commit()
    print(f"✅ записано: meta.{MD_PHASE_KEY} = {value} (было: {was}) · рука: {actor} · "
          f"строка журнала правок {row}")
    print(f"   шапка read-phoenix.py печатает: {header_line(conn)}")
    print("   Текст шапки сменился — каждая роль увидит её целиком при следующем чтении своей памяти.")


def clear_phase(conn, actor_flag):
    old = stored_value(conn)
    if old is False:
        refuse("таблицы meta в базе нет — убирать нечего и негде.")
    if old is None:
        print(f"✅ признака meta.{MD_PHASE_KEY} в базе нет — убирать нечего, журнал правок не тронут")
        return
    actor = pick_actor(actor_flag)
    conn.execute("DELETE FROM meta WHERE key = ?", (MD_PHASE_KEY,))
    row = audit(conn, actor, "md_phase_clear", f"{old} → —")
    conn.commit()
    print(f"✅ убрано: meta.{MD_PHASE_KEY} (было: {old}) · рука: {actor} · строка журнала правок {row}")
    print(f"   шапка read-phoenix.py печатает: {header_line(conn)}")


def main():
    ap = argparse.ArgumentParser(
        description="Фаза перехода md → база в этом контуре (признак meta.md_phase): показать, "
                    "записать, убрать. Её читает шапка read-phoenix.py.")
    ap.add_argument("--db", default=None, help="путь к mezosync.db (по умолчанию — рядом со скриптом)")
    what = ap.add_mutually_exclusive_group()
    what.add_argument("--set", dest="set_to", metavar="ФАЗА", help="записать фазу: 1, 2, 3 или 4")
    what.add_argument("--clear", action="store_true", help="убрать признак фазы")
    ap.add_argument("--actor", default=None, help="кто пишет (для --set и --clear); иначе MEZO_ROLE")
    dryrun.add_argument(ap)
    args = ap.parse_args()

    db = str(resolve_db(args.db, __file__))
    writes = args.set_to is not None or args.clear
    try:  # mode=rw: connect НЕ создаёт пустую базу при опечатке пути
        conn = dryrun.connect(f"file:{db}?mode=rw" if writes else f"file:{db}?mode=ro",
                              args.dry_run and writes, uri=True)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {db}")
    if args.set_to is not None:
        set_phase(conn, args.set_to, args.actor)
    elif args.clear:
        clear_phase(conn, args.actor)
    else:
        show(conn, db)


if __name__ == "__main__":
    main()
