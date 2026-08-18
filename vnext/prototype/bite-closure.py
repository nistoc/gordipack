# -*- coding: utf-8 -*-
"""
bite-closure.py — приёмка закрытия вопроса (Э-Г, вариант B: срочность гаснет закрытием).

8 свойств. Главное — P4: закрытие гасит ПРОИЗВОДНУЮ срочность, а объявленный автором
priority остаётся нетронутым. Иначе получилась бы правка чужой ноты задним числом,
то есть ровно «стирание факта», которое мы лечили в курсоре (Э-З).

    python bite-closure.py            # свойства
    python bite-closure.py --selftest # доказать, что укус умеет краснеть
"""
import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "schema_vnext.sql"
WM_FILE = HERE / "write-message-vnext.py"

_s = importlib.util.spec_from_file_location("wm", WM_FILE)
wm = importlib.util.module_from_spec(_s)
_s.loader.exec_module(wm)


def fresh():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    for r in ("COORD", "PROTO", "TAXO"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (r,))
    return con


def run():
    res = []
    def check(n, c): res.append((n, bool(c)))

    # ── Сценарий: COORD пишет PROTO срочное, PROTO отвечает и закрывает ──────────
    con = fresh()
    ok, _ = wm.write(con, "COORD", "@PROTO — разморожен, приступай", "[]", "high",
                     {"PROTO"}, {"TAXO"}, False, None)
    check("P1 запись с адресатом полем (to/cc) — принята", ok)

    q = con.execute("SELECT id FROM messages").fetchone()[0]
    kinds = dict(con.execute("SELECT role, kind FROM message_addressee WHERE message_id=?", (q,)))
    check("P2 to/cc легли РАЗНЫМИ видами, не свалены в один", kinds == {"PROTO": "to", "TAXO": "cc"})

    u = con.execute("SELECT urgency FROM message_urgency WHERE id=?", (q,)).fetchone()[0]
    check("P3 до закрытия urgency = high (пометка действует)", u == "high")

    ok2, msg2 = wm.write(con, "PROTO", "@COORD — принял, сделано", "[]", "normal",
                         {"COORD"}, set(), False, q)
    row = con.execute("SELECT priority, urgency FROM message_urgency WHERE id=?", (q,)).fetchone()
    check("P4 ГЛАВНОЕ: закрытие гасит urgency, но priority автора НЕ переписан",
          ok2 and row == ("high", "normal"))

    c = con.execute("SELECT closed_by, closed_role FROM message_closure WHERE message_id=?",
                    (q,)).fetchone()
    check("P5 видно ЧЕМ и КЕМ закрыто (связь, а не булево)",
          c is not None and c[1] == "PROTO")

    # ── Отказы ──────────────────────────────────────────────────────────────────
    ok3, m3 = wm.write(con, "TAXO", "закрою ещё раз", "[]", "normal", set(), set(), False, q)
    check("P6 отказ: повторное закрытие (стирание того, кто закрыл первым)",
          not ok3 and "уже закрыта" in m3)

    ok4, m4 = wm.write(con, "COORD", "закрою несуществующее", "[]", "normal",
                       set(), set(), False, 99999)
    check("P7 отказ: закрытие несуществующей ноты", not ok4 and "нет в ленте" in m4)

    ok5, m5 = wm.write(con, "COORD", "адресат с опечаткой", "[]", "normal",
                       {"PROTOO"}, set(), False, None)
    check("P8 отказ: адресат не из реестра (нота-призрак)", not ok5 and "не в реестре" in m5)

    return res


MUTANTS = {
    "M1-повторное-закрытие-разрешено": (WM_FILE, lambda s: s.replace(
        'if con.execute("SELECT 1 FROM message_closure WHERE message_id = ?", (closes,)).fetchone():',
        "if False:")),
    "M2-urgency-игнорирует-закрытие": (SCHEMA_FILE, lambda s: s.replace(
        "       CASE WHEN c.message_id IS NOT NULL THEN 'normal' ELSE m.priority END AS urgency,",
        "       m.priority AS urgency,")),
    "M3-адресат-без-проверки-реестра": (WM_FILE, lambda s: s.replace(
        "        if r not in roles:", "        if False:")),
}


def selftest():
    clean = run()
    red = sum(1 for _, ok in clean if not ok)
    print(f"ЧИСТО: {len(clean)-red}/{len(clean)}")
    if red:
        print("🔴 ПРИЁМКА КРАСНАЯ НА ЧИСТОМ — самопроверка невозможна")
        return 1
    survived = 0
    for name, (target, mut) in MUTANTS.items():
        orig = target.read_text(encoding="utf-8")
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден в {target.name} — нарочная поломка НЕ ВСТАЛА, "
                  f"считаю ВЫЖИВШИМ")
            survived += 1
            continue
        target.write_text(bad, encoding="utf-8")
        try:
            sp = importlib.util.spec_from_file_location("wm2", WM_FILE)
            m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
            globals()["wm"] = m
            r = run()
            nred = sum(1 for _, ok in r if not ok)
            print(f"{'✅' if nred else '🔴'} {name} [{target.name}]: "
                  f"{'поймал' if nred else 'НЕ ПОЙМАЛ'} ({nred}/{len(r)} красных)")
            if not nred:
                survived += 1
        finally:
            target.write_text(orig, encoding="utf-8")
            sp = importlib.util.spec_from_file_location("wm_r", WM_FILE)
            m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
            globals()["wm"] = m
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано (число из len(MUTANTS))")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        sys.exit(selftest())
    rs = run()
    bad = 0
    for n, ok in rs:
        print(f"{'✅' if ok else '🔴'} {n}")
        bad += 0 if ok else 1
    print(f"\n{len(rs)-bad}/{len(rs)}, rc={0 if bad==0 else 1}")
    sys.exit(0 if bad == 0 else 1)
