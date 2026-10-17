#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА шага схемы 20260812-cursor-segments-truth: правка посевных отрезков — только в Atlas.

Карточка #686, место 4 (2026-10-17). Шаг переводит посевные отрезки отметок прочитанного
в «прочитано» по слову владельца Atlas 12.08 и делит отрезок роли RCC по записке Atlas #2898.
UPGRADE-v4-to-v5.md велит запускать шаг и соседям — и прежде он делал это в ЛЮБОМ контуре.
Теперь различитель — meta.group_name, как у шага 20260905 (карточка #640).

⛔ ЧИСЛО СЛУЧАЕВ ЗДЕСЬ НЕ ПИШЕТСЯ СЛОВОМ — его печатает прогон.

  ① контур Atlas: отрезок RCC делится на 2204, ZETA — «прочитано», хвост дописан (поведение прежнее)
  ①-бис повторный прогон в Atlas отрезков не меняет
  ② ВСТРЕЧНЫЙ: контур не Atlas — посевные отрезки не тронуты, RCC не делится, хвост дописан,
     выборки и запись в журнале есть, и это сказано словами
  ③ ВСТРЕЧНЫЙ: в meta нет group_name — так же, как ②, со своими словами
  ④ нарочная поломка «вернуть литерал» (контур всегда Atlas) проваливает ②
  ⑤ ВСТРЕЧНЫЙ: --dry-run в контуре не Atlas — план говорит «не трогаем» у обеих ролей и
     «меняем отрезков: 0 из 2», база не тронута
  ⑥ нарочная поломка «план без проверки контура» (проверка «не Atlas» снята в plan_for, цикл
     записи цел) проваливает ⑤

🪤 ⑤ и ⑥ — записка #5913, поломка B2 (2026-10-17). Проверка «не Atlas» стоит в шаге ДВАЖДЫ:
в plan_for и в цикле записи. ② судит только запись — и под поломкой плана проходил: запись
не трогает ничего, а --dry-run обещает соседу разделить отрезок RCC и перевести ZETA
в «прочитано» по слову владельца Atlas. Именно этот экран сосед видит первым:
UPGRADE-v4-to-v5.md велит запускать шаг сначала с --dry-run.

Испытуемый шаг берётся через mezo_target (MEZO_SCRIPTS_ROOT): из клона пакета —
MEZO_SCRIPTS_ROOT=<клон>/scripts. ⛔ Живой базы не касается: свои временные базы в песочнице.
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале
import mezo_target  # noqa: E402 — какую копию шага испытываем

STEP_NAME = "20260812-cursor-segments-truth.py"
STEP = mezo_target.migration(STEP_NAME)
SEED_BASIS = "перенос плоского курсора (проба приёмки bite-cursor-segments-step)"
SEED_TO, CURSOR = 3000, 3100            # посев до 3000, отметка прочитанного 3100 ⇒ хвост 3001..3100
RCC_READ_TO = 2204

LITERAL_ANCHOR = "    is_atlas = group_name == ATLAS_GROUP_NAME\n"
LITERAL_BROKEN = "    is_atlas = True\n"
# Нарочная поломка «план без проверки контура»: из plan_for убрана ветка «не Atlas», цикл записи цел.
PLAN_ANCHOR = ("        if not is_atlas:\n"
               "            acts.append((role, f\"{a}..{b} declared\", \"не трогаем\", NOT_ATLAS_REASON))\n"
               "            continue\n")
PLAN_BROKEN = ""


def build(path: str, group_name):
    """Две роли (RCC, ZETA), у каждой посевной отрезок 1..3000 и отметка 3100.
    group_name: значение meta.group_name; None — строки нет."""
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE roles (role TEXT PRIMARY KEY);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY,
            last_read_id INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE schema_migrations (version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')), note TEXT,
            fingerprint TEXT, applied_by TEXT);
        CREATE TABLE cursor_segments (
            id INTEGER PRIMARY KEY,
            role TEXT NOT NULL REFERENCES roles(role) ON DELETE CASCADE,
            from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('read','declared','born')),
            basis TEXT, authorized TEXT, note_id INTEGER,
            at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (to_id >= from_id),
            CHECK (kind = 'read' OR (basis IS NOT NULL AND authorized IS NOT NULL)));
    """)
    if group_name is not None:
        con.execute("INSERT INTO meta (key, value) VALUES ('group_name', ?)", (group_name,))
    for role in ("RCC", "ZETA"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (role,))
        con.execute("INSERT INTO read_cursors (reader_role, last_read_id) VALUES (?, ?)",
                    (role, CURSOR))
        con.execute("INSERT INTO cursor_segments (role, from_id, to_id, kind, basis, authorized)"
                    " VALUES (?, 1, ?, 'declared', ?, 'owner')", (role, SEED_TO, SEED_BASIS))
    con.commit()
    con.close()


def run(path: str, step=STEP, extra=()):
    r = subprocess.run([sys.executable, str(step), "--db", path, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def segments(path: str) -> dict:
    """Роль → кортеж отрезков (from, to, kind)."""
    con = sqlite3.connect(path)
    got = {}
    for role, a, b, kind in con.execute(
            "SELECT role, from_id, to_id, kind FROM cursor_segments ORDER BY role, from_id"):
        got.setdefault(role, []).append((a, b, kind))
    views = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    journal = con.execute("SELECT count(*) FROM schema_migrations WHERE version = ?",
                          (STEP_NAME[:-3],)).fetchone()[0]
    con.close()
    return {r: tuple(s) for r, s in got.items()}, views, journal


ATLAS_EXPECT = {"RCC": ((1, RCC_READ_TO, "read"), (RCC_READ_TO + 1, SEED_TO, "declared"),
                        (SEED_TO + 1, CURSOR, "read")),
                "ZETA": ((1, SEED_TO, "read"), (SEED_TO + 1, CURSOR, "read"))}
OTHER_EXPECT = {"RCC": ((1, SEED_TO, "declared"), (SEED_TO + 1, CURSOR, "read")),
                "ZETA": ((1, SEED_TO, "declared"), (SEED_TO + 1, CURSOR, "read"))}
SEEDED = {"RCC": ((1, SEED_TO, "declared"),), "ZETA": ((1, SEED_TO, "declared"),)}


def broken_copy(tmp: str, sub: str, anchor: str, replacement: str):
    """Копия шага с нарочной поломкой в tmp/<sub>; не легла — (None, причина).
    Раскладка копии — как у пакета: <копия>/scripts/migrations/<шаг> и schema_journal.py рядом.
    Своя папка на каждую поломку: в общей вторая копия затёрла бы первую."""
    text = STEP.read_text(encoding="utf-8")
    if text.count(anchor) != 1:
        return None, f"поломка не легла: якорь найден {text.count(anchor)} раз"
    mig = os.path.join(tmp, sub, "scripts", "migrations")
    os.makedirs(mig, exist_ok=True)
    with open(os.path.join(mig, STEP_NAME), "w", encoding="utf-8") as f:
        f.write(text.replace(anchor, replacement))
    shutil.copy2(STEP.parent.parent / "schema_journal.py",
                 os.path.join(tmp, sub, "scripts", "schema_journal.py"))
    return os.path.join(mig, STEP_NAME), ""


def literal_copy(tmp: str):
    """Копия шага с нарочной поломкой «вернуть литерал»."""
    return broken_copy(tmp, "step-copy", LITERAL_ANCHOR, LITERAL_BROKEN)


def dry_run_view(path: str, step=STEP):
    """--dry-run шага: (вывод, код, строки плана, «меняем отрезков: N из M», база не тронута).
    Строка плана начинается именем роли с первого знака; строки хвоста идут с отступом."""
    out, code = run(path, step, ("--dry-run",))
    segs, views, journal = segments(path)
    rows = [line for line in out.splitlines() if line.startswith(("RCC ", "ZETA "))]
    m = re.search(r"меняем отрезков: (\d+) из (\d+)", out)
    touched = (int(m.group(1)), int(m.group(2))) if m else None
    untouched = segs == SEEDED and not ({"cursor_truth", "cursor_gaps"} & views) and journal == 0
    return out, code, rows, touched, untouched


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


def shown(segs: dict) -> str:
    return " · ".join(f"{r}: " + ", ".join(f"{a}..{b} {k}" for a, b, k in s)
                      for r, s in sorted(segs.items()))


def main() -> int:
    print(f"испытан шаг: {mezo_target.label()} · {STEP}")
    tmp = str(mezo_stand.new("bite-cursor-segments-step-"))
    ok = True

    # ① контур Atlas — поведение прежнее
    p1 = os.path.join(tmp, "atlas.db")
    build(p1, "atlas")
    out1, code1 = run(p1)
    segs1, views1, journal1 = segments(p1)
    good = (code1 == 0 and segs1 == ATLAS_EXPECT and {"cursor_truth", "cursor_gaps"} <= views1
            and journal1 == 1 and "это Atlas" in out1)
    ok &= case("① контур Atlas: RCC делится на 2204, ZETA — «прочитано», хвост дописан", good,
               f"код {code1} · {shown(segs1)}" + ("" if good else f" · вывод: {out1.strip()[-300:]}"))

    out1b, code1b = run(p1)
    segs1b, _, journal1b = segments(p1)
    ok &= case("①-бис повторный прогон в Atlas отрезков не меняет",
               code1b == 0 and segs1b == ATLAS_EXPECT and journal1b == 1,
               f"код {code1b} · {shown(segs1b)}")

    # ② контур не Atlas
    p2 = os.path.join(tmp, "zeta.db")
    build(p2, "zeta-contour")
    out2, code2 = run(p2)
    segs2, views2, journal2 = segments(p2)
    good = (code2 == 0 and segs2 == OTHER_EXPECT and {"cursor_truth", "cursor_gaps"} <= views2
            and journal2 == 1 and "не Atlas" in out2)
    ok &= case("② ВСТРЕЧНЫЙ: контур не Atlas — посевные отрезки не тронуты, RCC не делится, "
               "хвост дописан, сказано словами", good,
               f"код {code2} · {shown(segs2)}" + ("" if good else f" · вывод: {out2.strip()[-300:]}"),
               differ=True)

    # ③ group_name нет
    p3 = os.path.join(tmp, "nameless.db")
    build(p3, None)
    out3, code3 = run(p3)
    segs3, _, journal3 = segments(p3)
    good = (code3 == 0 and segs3 == OTHER_EXPECT and journal3 == 1
            and "в meta нет group_name" in out3)
    ok &= case("③ ВСТРЕЧНЫЙ: в meta нет group_name — посевные отрезки не тронуты, сказано словами",
               good, f"код {code3} · {shown(segs3)}", differ=True)

    # ④ нарочная поломка «вернуть литерал»
    broken, why = literal_copy(tmp)
    if broken is None:
        ok &= case("④ поломка «вернуть литерал» проваливает ②", False, f"⛔ НЕ ЗАПУСТИЛАСЬ: {why}",
                   differ=True)
    else:
        p4 = os.path.join(tmp, "zeta-broken.db")
        build(p4, "zeta-contour")
        out4, code4 = run(p4, broken)
        segs4, _, _ = segments(p4)
        ok &= case("④ поломка «вернуть литерал» (контур всегда Atlas) проваливает ②",
                   code4 == 0 and segs4 == ATLAS_EXPECT,
                   f"под поломкой в контуре не Atlas: {shown(segs4)} — отрезок RCC разделён по "
                   "записке Atlas, как до карточки #686", differ=True)

    # ⑤ --dry-run в контуре не Atlas: план обязан сказать то же, что сделает запись
    p5 = os.path.join(tmp, "zeta-dry.db")
    build(p5, "zeta-contour")
    out5, code5, rows5, touched5, untouched5 = dry_run_view(p5)
    kept5 = len(rows5) == 2 and all("не трогаем" in r for r in rows5)
    good = (code5 == 0 and kept5 and touched5 == (0, 2) and untouched5
            and "РАЗДЕЛИТЬ" not in out5 and "не Atlas" in out5)
    ok &= case("⑤ ВСТРЕЧНЫЙ: --dry-run в контуре не Atlas — план «не трогаем» у обеих ролей, "
               "«меняем отрезков: 0 из 2», база не тронута", good,
               f"код {code5} · строк плана {len(rows5)}, «не трогаем» у "
               f"{sum('не трогаем' in r for r in rows5)} · меняем {touched5} · база "
               f"{'не тронута' if untouched5 else 'ТРОНУТА'}"
               + ("" if good else f" · вывод: {out5.strip()[-300:]}"), differ=True)

    # ⑥ нарочная поломка «план без проверки контура»
    broken6, why6 = broken_copy(tmp, "step-copy-plan", PLAN_ANCHOR, PLAN_BROKEN)
    if broken6 is None:
        ok &= case("⑥ поломка «план без проверки контура» проваливает ⑤", False,
                   f"⛔ НЕ ЗАПУСТИЛАСЬ: {why6}", differ=True)
    else:
        p6 = os.path.join(tmp, "zeta-dry-broken.db")
        build(p6, "zeta-contour")
        out6, code6, rows6, touched6, untouched6 = dry_run_view(p6, broken6)
        ok &= case("⑥ поломка «план без проверки контура» (запись цела) проваливает ⑤",
                   code6 == 0 and touched6 == (2, 2) and "РАЗДЕЛИТЬ" in out6 and untouched6,
                   f"под поломкой в контуре не Atlas план обещает: меняем {touched6}, "
                   f"{'РАЗДЕЛИТЬ у RCC' if 'РАЗДЕЛИТЬ' in out6 else 'RCC не делится'}; база "
                   f"{'не тронута' if untouched6 else 'ТРОНУТА'} (под верным кодом: меняем (0, 2))",
                   differ=True)

    print()
    print(f"✅ ПРОВЕРКА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}" if ok
          else "🔴 ПРОВЕРКА НЕ ПРИНЯТА — числа из неё нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
