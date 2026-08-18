# -*- coding: utf-8 -*-
"""
bite-cursor.py — укус курьерского курсора (Э-З).

9 свойств: пять отказов (три от AIA + два мои) + запись сегментов + витрины.
Приёмка идёт НА РЕАЛЬНОМ случае @RCC 2026-08-05, а не на выдуманных числах:
отметка прочитанного 2204 → 2896 заявлением (692 ноты), затем честное чтение хвоста.

    python bite-cursor.py            # свойства
    python bite-cursor.py --selftest # доказать, что укус умеет краснеть
"""
import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "schema_vnext.sql"
CA_FILE = HERE / "cursor-advance.py"

_spec = importlib.util.spec_from_file_location("cursor_advance", CA_FILE)
ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ca)


def fresh():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    for r in ("RCC", "COORD", "PROTO", "CHROME", "STUD"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (r,))
    # лента-заглушка до #2909 (голова как в живой БД на момент замера)
    for i in (1, 2204, 2500, 2896, 2897, 2909):
        con.execute("INSERT INTO messages (id, writer_role, body_md) VALUES (?, 'COORD', 'x')", (i,))
    return con


def run():
    res = []
    def check(name, cond): res.append((name, bool(cond)))

    # ── РЕАЛЬНЫЙ СЛУЧАЙ @RCC как приёмка ──────────────────────────────────────
    con = fresh()
    ca.advance(con, "RCC", 2204, "read", None, None)          # что реально прочитал до дормана
    ok, _ = ca.advance(con, "RCC", 2896, "declared",
                       "сводка COORD за 7 недель дормана вместо ленты; 692 ноты не читаны",
                       "owner", 2898)
    check("P1 заявленный сдвиг с основанием — принят", ok)

    t = con.execute("SELECT cursor_at, notes_read, notes_declared FROM cursor_truth "
                    "WHERE role='RCC'").fetchone()
    check("P2 cursor_truth различает прочитанное и заявленное (не «курсор = N»)",
          t == (2896, 2204, 692))

    # ── ПЯТЬ ОТКАЗОВ ──────────────────────────────────────────────────────────
    ok1, m1 = ca.advance(con, "RCC", 2897, "declared", None, None)
    check("P3 ① отказ: заявленный сдвиг БЕЗ основания", not ok1 and "ОТКАЗ ①" in m1)

    ok2, m2 = ca.advance(con, "RCC", 2500, "read")
    check("P4 ② отказ: назад (стирание факта чтения)", not ok2 and "ОТКАЗ ②" in m2)

    ok3, m3 = ca.advance(con, "RCC", 99999, "read")
    check("P5 ③ отказ: за горизонт ленты", not ok3 and "ОТКАЗ ③" in m3)

    # ④ перекрытие: пробуем вписать сегмент внутрь уже пройденного — через прямой вызов
    ok4, m4 = ca.advance(con, "COORD", 2909, "read")           # COORD с нуля до головы
    ok4b, m4b = ca.advance(con, "COORD", 2500, "read")         # назад-в-середину
    check("P6 ④/② перекрытие уже пройденного не проходит", ok4 and not ok4b)

    # ── ГЛАВНОЕ СВОЙСТВО: основание НЕ ЗАТИРАЕТСЯ следующим честным чтением ────
    ok5, _ = ca.advance(con, "RCC", 2909, "read")               # честно дочитал хвост
    t2 = con.execute("SELECT notes_read, notes_declared FROM cursor_truth "
                     "WHERE role='RCC'").fetchone()
    check("P7 после честного чтения хвоста заявленный участок ЖИВ (не затёрт)",
          ok5 and t2[1] == 692)

    gaps = con.execute("SELECT from_id, to_id, basis FROM cursor_gaps WHERE role='RCC'").fetchall()
    check("P8 cursor_gaps отвечает «что до роли НЕ дошло» запросом, а не устной просьбой",
          len(gaps) == 1 and gaps[0][0] == 2205 and gaps[0][1] == 2896)

    # ── СХЕМА держит контракт даже в обход CLI (второй писатель) ──────────────
    try:
        con.execute("INSERT INTO cursor_segments (role, from_id, to_id, kind) "
                    "VALUES ('PROTO', 1, 5, 'declared')")
        con.commit()
        p9 = False
    except sqlite3.IntegrityError:
        p9 = True
    check("P9 CHECK не даёт записать declared без основания В ОБХОД CLI", p9)

    # ── 🆕 ТРЕТИЙ ВИД 'born': РОЖДЕНИЕ РОЛИ ≠ ДОЛГ ────────────────────────────
    # Живой повод: 06.08 завели роль CHROME (нота #2934), курсор сдвинули с нуля на
    # голову. Двумя видами это записывалось только как 'declared' — и механизм
    # печатал «2909 нот НЕ ДОШЛИ, повторите запрос» тем, кто ей никогда не писал.
    con2 = fresh()
    okb, mb = ca.advance(con2, "CHROME", 2909, "born",
                         "роль заведена по слову владельца 06.08", "owner", 2934)
    check("P10 рождение роли записывается видом 'born'", okb and "ДО ЗАВЕДЕНИЯ" in mb)

    tb = con2.execute("SELECT notes_read, notes_declared, notes_before_birth "
                      "FROM cursor_truth WHERE role='CHROME'").fetchone()
    check("P11 'born' НЕ попадает в notes_declared — небывшее не складывается с пропущенным",
          tb[1] is None and tb[2] == 2909)

    gaps_c = con2.execute("SELECT COUNT(*) FROM cursor_gaps WHERE role='CHROME'").fetchone()[0]
    check("P12 витрина «что не дошло» МОЛЧИТ о новорождённой (повторять некому и нечего)",
          gaps_c == 0)

    # Различающий тест: витрина не онемела вообще — на реальном долге она обязана говорить.
    ca.advance(con2, "RCC", 2204, "read", None, None)
    ca.advance(con2, "RCC", 2896, "declared", "сводка вместо ленты", "owner", 2898)
    gaps_r = con2.execute("SELECT COUNT(*) FROM cursor_gaps WHERE role='RCC'").fetchone()[0]
    check("P13 та же витрина ГОВОРИТ о реальном долге (P12 — различение, а не немота)",
          gaps_r == 1)

    okb2, mb2 = ca.advance(con2, "STUD", 100, "born", None, None)
    check("P14 'born' без основания тоже отвергнут: рождение роли — решение, у него есть автор",
          not okb2 and "ОТКАЗ ①" in mb2)

    return res


MUTANTS = {
    "M1-CHECK-основания-снят": (SCHEMA_FILE, lambda s: s.replace(
        "    CHECK (kind = 'read' OR (basis IS NOT NULL AND authorized IS NOT NULL))",
        "    CHECK (1)")),
    "M2-отказ-назад-снят": (CA_FILE, lambda s: s.replace(
        "    if to_id <= cur:", "    if False:")),
    "M3-отказ-за-горизонт-снят": (CA_FILE, lambda s: s.replace(
        "    if to_id > h:", "    if False:")),
    # 🆕 Главный мутант третьего вида: если 'born' попадёт в витрину «что не дошло»,
    # механизм снова начнёт требовать невыполнимого у тех, кто роли не писал.
    "M4-born-включён-в-витрину-долга": (SCHEMA_FILE, lambda s: s.replace(
        "FROM cursor_segments WHERE kind = 'declared';",
        "FROM cursor_segments WHERE kind IN ('declared', 'born');")),
    # 🆕 И обратный: если 'born' сложить с 'declared' в одну колонку, новорождённая
    # роль получит долг вчетверо больше, чем роль, реально не читавшая ленту.
    "M5-born-сложен-с-declared": (SCHEMA_FILE, lambda s: s.replace(
        "       SUM(CASE WHEN kind = 'declared' THEN to_id - from_id + 1 END) AS notes_declared,",
        "       SUM(CASE WHEN kind IN ('declared','born') THEN to_id - from_id + 1 END) "
        "AS notes_declared,")),
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
                  f"считаю ВЫЖИВШИМ (не вставший мутант ничего не доказывает)")
            survived += 1
            continue
        target.write_text(bad, encoding="utf-8")
        try:
            importlib.util.spec_from_file_location("cursor_advance", CA_FILE)
            _s = importlib.util.spec_from_file_location("ca2", CA_FILE)
            m = importlib.util.module_from_spec(_s); _s.loader.exec_module(m)
            globals()["ca"] = m
            r = run()
            nred = sum(1 for _, ok in r if not ok)
            caught = nred > 0
            print(f"{'✅' if caught else '🔴'} {name} [{target.name}]: "
                  f"{'поймал' if caught else 'НЕ ПОЙМАЛ'} ({nred}/{len(r)} красных)")
            if not caught:
                survived += 1
        finally:
            target.write_text(orig, encoding="utf-8")
            _s = importlib.util.spec_from_file_location("ca_restore", CA_FILE)
            m = importlib.util.module_from_spec(_s); _s.loader.exec_module(m)
            globals()["ca"] = m
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано "
          f"(число из len(MUTANTS))")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    rs = run()
    bad = 0
    for n, ok in rs:
        print(f"{'✅' if ok else '🔴'} {n}")
        bad += 0 if ok else 1
    print(f"\n{len(rs)-bad}/{len(rs)}, rc={0 if bad==0 else 1}")
    sys.exit(0 if bad == 0 else 1)
