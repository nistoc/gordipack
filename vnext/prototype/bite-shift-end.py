#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Приёмка карточки #702: проверка блока «КОНЕЦ СМЕНЫ» в state и строки «сверен с state» в plan.

ЧТО СУДИМ — критерий карточки #702 по пунктам:
  ①  блок найден, каждая недостающая часть названа по имени; разные формы строк узнаются
  ①б в части «последним» нет номера записки или карточки — находка; номер есть — нет
  ②  plan «сверен с state» старше блока — находка с ОБОИМИ часами; свежий — нет; строки нет — находка
  ③  встречный: блока нет (и «конец смены» в обычной речи) — не находка, ни строки
  ④  нарочные поломки (--break): каждая проваливает ровно свои случаи
  ⑤  save-phoenix.py: строки под «OK», не отказ; «👉 следующим — plan»; «✅» на полном блоке;
     без блока — тишина; сбой самой проверки — «НЕ выполнена», тело записано
  ⑥  общий прогон: записка роли после блока — находка; «смена закрыта» и записка той же минуты — нет;
     --soft — код 0 и строки «⚠️»

ЧЕМ СУДИМ. Функции — из guard-shift-end.py рядом с приёмкой (или --guard). Сохранения —
настоящим save-phoenix.py (испытуемая копия mezo_target) на СОГЛАСОВАННОЙ КОПИИ живой базы
(mezo_stand.snapshot_db); живую базу приёмка не открывает на запись. Роли набора BITE702A…D
живут только в копии; записки случая ⑥ вставляются тоже только в копию.

Запуск:
  python bite-shift-end.py                    все случаи
  python bite-shift-end.py --break part       часть «ошибалась» убрана из проверки → ①, ⑤а
  python bite-shift-end.py --break plan       сравнение часов plan выключено → ②, ⑤б
  python bite-shift-end.py --break closed     исключение «смена закрыта» выключено → ⑥
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand   # noqa: E402 — судим согласованную копию, не живую базу (карточка #629)
import mezo_target  # noqa: E402 — какую копию инструмента испытываем (карточка #148)

print(f"⚖️ испытуется: {mezo_target.label()}")

# поломка → (что заменить в guard-shift-end.py, чем, какие случаи обязаны провалиться)
BREAKS = {
    "part": ('    ("ошибалась", re.compile(LINE_START + r"ошиб\\w*", re.I | re.M)),\n', "",
             {"①", "⑤а"}),
    "plan": ("        elif mark < when:", "        elif False:", {"②", "⑤б"}),
    "closed": ("if not CLOSED.search(", "if not False and (", {"⑥"}),
}

FULL = """# Состояние роли

## Работа смены
- что-то делала

## КОНЕЦ СМЕНЫ 2026-10-11 10:00 UTC
- последним: проверка блока конца смены, записка #5726
- не доделано: приёмка чужой рукой — CORE занята
- жду: вердикт CORE по карточке #705
- ошибалась: обрезала вывод инструмента

## Прочее
- строка после блока
"""
# Разные формы строк: жирный, «*», ждём, «не сделано», мужской род «ошибся», заголовок третьего уровня.
VARIANT = """### **КОНЕЦ СМЕНЫ 2026-10-11T10:00 UTC**
* **Последним** занимался карточкой #702
* **Не сделано:** приёмка — и почему
* Ждём: слова владельца
- Ошибся: в часе записки
"""
NO_WAIT_NO_ERR = """## КОНЕЦ СМЕНЫ 2026-10-11 10:00 UTC
- последним: записка #5726
- не доделано: приёмка
"""
NO_NUMBER = FULL.replace("записка #5726", "проверка без номера")
PROSE = """# Состояние
Владелец просил: по команде «конец смены» писать блок. Сегодня смену не закрывала.
## План
- КОНЕЦ СМЕНЫ — в разделе state, не здесь
"""
PLAN_FRESH = "# План роли · сверен с state 2026-10-11 10:00 UTC\n- пункт\n"
PLAN_OLD = "# План роли · сверен с state 2026-10-11 09:15 UTC\n- пункт\n"
PLAN_NONE = "# План роли\n- пункт\n"
PLAN_DEEP = "# План\n- а\n- б\n- в\n- г\n- д\n- сверен с state 2026-10-11 10:00 UTC\n"


def load_guard(path):
    spec = importlib.util.spec_from_file_location("guard_shift_end_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(results, mark, what, problems, output=""):
    ok = not problems
    results.append((mark, ok))
    print(f"  {'✅' if ok else '🔴'} {mark} {what}")
    if not ok:
        print(f"       {' · '.join(problems)}")
        for l in [l for l in output.splitlines() if l.strip()][:6]:
            print(f"       │ {l[:110]}")


def cases_direct(g, results):
    """①, ①б, ②, ③ — прямо на функции block_findings()."""
    print("── ① части блока по имени")
    problems = []
    when, f, _ = g.block_findings(NO_WAIT_NO_ERR, PLAN_FRESH)
    named = {x for x in f if x.startswith("нет части")}
    if when != "2026-10-11 10:00:00":
        problems.append(f"час блока {when!r}, ждали 2026-10-11 10:00:00")
    for name in ("жду", "ошибалась"):
        if f"нет части «{name}»" not in named:
            problems.append(f"не названа недостающая часть «{name}»")
    for name in ("последним", "не доделано"):
        if f"нет части «{name}»" in named:
            problems.append(f"названа как недостающая часть «{name}», а она есть")
    when2, f2, _ = g.block_findings(VARIANT, PLAN_FRESH)
    if when2 is None or any(x.startswith("нет части") for x in f2):
        problems.append(f"разные формы строк не узнаны: {f2}")
    when3, f3, _ = g.block_findings(FULL, PLAN_FRESH)
    if f3:
        problems.append(f"полный блок дал находки: {f3}")
    verdict(results, "①", "недостающие «жду» и «ошибалась» названы; жирный, «*», «ждём», «ошибся» узнаны; "
            "полный блок — без находок", problems, "\n".join(f + f2 + f3))

    print("── ①б номер в части «последним»")
    _, f, _ = g.block_findings(NO_NUMBER, PLAN_FRESH)
    problems = [] if any("нет номера" in x for x in f) else ["нет находки о номере"]
    verdict(results, "①б", "«последним» без номера записки или карточки — находка", problems, "\n".join(f))

    print("── ② plan против блока")
    problems = []
    _, _, p_old = g.block_findings(FULL, PLAN_OLD)
    if not p_old or "09:15" not in p_old or "10:00" not in p_old:
        problems.append(f"plan старше блока: ждали находку с обоими часами, вышло {p_old!r}")
    _, _, p_fresh = g.block_findings(FULL, PLAN_FRESH)
    if p_fresh:
        problems.append(f"свежий plan дал находку: {p_fresh!r}")
    _, _, p_none = g.block_findings(FULL, PLAN_NONE)
    if not p_none or "сверен с state" not in p_none:
        problems.append(f"plan без строки: ждали находку, вышло {p_none!r}")
    _, _, p_deep = g.block_findings(FULL, PLAN_DEEP)
    if not p_deep:
        problems.append("строка «сверен с state» ниже пятой непустой засчитана")
    verdict(results, "②", "plan 09:15 при блоке 10:00 — находка с обоими часами; свежий — нет; "
            "без строки и строка глубже пятой — находка", problems, f"{p_old}\n{p_none}\n{p_deep}")

    print("── ③ встречный: блока нет")
    problems = []
    for name, body in (("пустой state", ""), ("нет state", None), ("«конец смены» в обычной речи", PROSE)):
        res = g.block_findings(body, PLAN_NONE)
        if res != (None, [], None):
            problems.append(f"{name}: {res}")
        if g.save_lines(body, PLAN_NONE, "state"):
            problems.append(f"{name}: save_lines не пуст")
    verdict(results, "③", "без блока — ни находки, ни строки (в т.ч. слова «конец смены» в прозе)", problems)


class Stand:
    def __init__(self, tool, db, workdir, env):
        self.tool, self.db, self.workdir, self.env = tool, db, Path(workdir), env
        self.n = 0

    def save(self, role, section, body, tool=None):
        self.n += 1
        f = self.workdir / f"body{self.n}.md"
        f.write_text(body, encoding="utf-8")
        cmd = [sys.executable, str(tool or self.tool), "--db", str(self.db), "--role", role,
               "--section", section, "--file", str(f), "--allow-shrink"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self.env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def body(self, role, section):
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?", (role, section)).fetchone()
        con.close()
        return row[0] if row else None


def after_ok(out, needle):
    """Есть ли строка с needle ПОСЛЕ строки «OK phoenix/…»."""
    lines = out.splitlines()
    ok = next((i for i, l in enumerate(lines) if l.startswith("OK phoenix/")), None)
    return ok is not None and any(needle in l for l in lines[ok + 1:])


def cases_save(st, results, broken_dir):
    """⑤ — настоящим save-phoenix.py на копии базы."""
    print("── ⑤ save-phoenix.py: строки под «OK»")
    role = "BITE702A"
    code, out = st.save(role, "state", NO_WAIT_NO_ERR.replace("последним: записка #5726",
                                                               "последним: записка #5726 и карточка #702"))
    problems = []
    if code != 0 or not out.startswith("OK phoenix/") and "OK phoenix/" not in out:
        problems.append(f"сохранение не прошло, код {code}")
    if not after_ok(out, "нет части «ошибалась»"):
        problems.append("под «OK» нет строки «нет части «ошибалась»»")
    if not after_ok(out, "👉") or not after_ok(out, "следующим — plan"):
        problems.append("нет строки «👉 … следующим — plan»")
    if "⛔" in out:
        problems.append("в выводе отказ «⛔»")
    verdict(results, "⑤а", "блок без двух частей: «OK», под ним названные части и «следующим — plan», "
            "код 0", problems, out)

    code, out = st.save(role, "state", FULL)
    problems = []
    if code != 0 or "нет части" in out:
        problems.append(f"полный блок: код {code} или есть «нет части»")
    if not after_ok(out, "следующим — plan"):
        problems.append("нет «следующим — plan» при plan без строки сверки")
    code2, out2 = st.save(role, "plan", PLAN_FRESH)
    if code2 != 0 or not after_ok(out2, "✅ блок «КОНЕЦ СМЕНЫ 2026-10-11 10:00 UTC»"):
        problems.append(f"plan со строкой сверки: ждали «✅ блок …», код {code2}")
    code3, out3 = st.save(role, "plan", PLAN_OLD)
    if code3 != 0 or not after_ok(out3, "09:15") or not after_ok(out3, "⚠️"):
        problems.append(f"plan старше блока при сохранении plan: ждали «⚠️ … 09:15 …», код {code3}")
    verdict(results, "⑤б", "полный блок → «следующим — plan»; plan сверен → «✅»; plan старше → «⚠️» "
            "с часом", problems, out + out2 + out3)

    code, out = st.save("BITE702B", "state", PROSE)
    problems = []
    if code != 0 or "КОНЕЦ СМЕНЫ" in out:
        problems.append(f"без блока есть строка о блоке, код {code}")
    verdict(results, "⑤в", "без блока — ни одной строки о блоке", problems, out)

    # Сбой проверки: копия save-phoenix.py рядом с испорченным guard-shift-end.py.
    lone = broken_dir / "lone"
    lone.mkdir()
    runner = lone / "save-phoenix.py"
    shutil.copyfile(st.tool, runner)
    (lone / "guard-shift-end.py").write_text("def (:\n", encoding="utf-8")
    code, out = st.save("BITE702B", "state", FULL, tool=runner)
    problems = []
    if code != 0:
        problems.append(f"сохранение упало, код {code}")
    if not after_ok(out, "НЕ выполнена"):
        problems.append("нет строки «НЕ выполнена»")
    if st.body("BITE702B", "state") != FULL:
        problems.append("тело не записано")
    verdict(results, "⑤г", "проверка сломана — «НЕ выполнена», код 0, тело записано", problems, out)


def cases_guard(st, results, guard_path):
    """⑥ — общий прогон: guard-shift-end.py по копии базы."""
    print("── ⑥ общий прогон: записки после блока")
    con = sqlite3.connect(st.db)
    for role in ("BITE702C", "BITE702D"):
        for section, body in (("state", FULL), ("plan", PLAN_FRESH)):
            con.execute("INSERT INTO phoenix (role, section, body) VALUES (?,?,?) "
                        "ON CONFLICT(role, section) DO UPDATE SET body=excluded.body", (role, section, body))
    rows = [("BITE702C", "2026-10-11 10:00:30", "записка той же минуты, что и блок"),
            ("BITE702C", "2026-10-11 10:30:00", "обычная записка после блока"),
            ("BITE702C", "2026-10-11 10:40:00", "# @COORD — смена закрыта"),
            ("BITE702D", "2026-10-11 10:40:00", "# @COORD — смена закрыта")]
    ids = []
    for r in rows:
        ids.append(con.execute("INSERT INTO messages (writer_role, timestamp, body_md) VALUES (?,?,?)", r).lastrowid)
    con.commit()
    con.close()

    def run(role, *extra):
        p = subprocess.run([sys.executable, str(guard_path), "--db", str(st.db), "--role", role, *extra],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=st.env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    problems = []
    code, out = run("BITE702C")
    if code != 1:
        problems.append(f"BITE702C: код {code}, ждали 1")
    if f"записка #{ids[1]}" not in out:
        problems.append(f"не названа записка #{ids[1]} (после блока)")
    for i in (ids[0], ids[2]):
        if f"записка #{i}" in out:
            problems.append(f"названа записка #{i} (той же минуты или «смена закрыта»)")
    code2, out2 = run("BITE702D")
    if code2 != 0 or "✅ BITE702D" not in out2:
        problems.append(f"BITE702D (только «смена закрыта»): код {code2}, ждали 0 и «✅»")
    code3, out3 = run("BITE702C", "--soft")
    if code3 != 0 or "⚠️ BITE702C" not in out3:
        problems.append(f"--soft: код {code3}, ждали 0 и строку «⚠️ BITE702C»")
    verdict(results, "⑥", "записка после блока — находка; той же минуты и «смена закрыта» — нет; "
            "--soft — код 0 и «⚠️»", problems, out + out2 + out3)


def main():
    ap = argparse.ArgumentParser(description="Приёмка карточки #702: блок «КОНЕЦ СМЕНЫ» в памяти роли")
    ap.add_argument("--guard", help="путь к guard-shift-end.py (по умолчанию — рядом с приёмкой)")
    ap.add_argument("--tool", help="путь к save-phoenix.py (по умолчанию — испытуемая копия)")
    ap.add_argument("--db", help="путь к базе (по умолчанию — согласованная КОПИЯ живой)")
    ap.add_argument("--break", dest="breakage", choices=sorted(BREAKS),
                    help="нарочная поломка: part — часть «ошибалась» убрана; plan — сравнение часов "
                         "plan выключено; closed — исключение «смена закрыта» выключено")
    a = ap.parse_args()

    guard = Path(a.guard) if a.guard else Path(__file__).resolve().parent / "guard-shift-end.py"
    tool = Path(a.tool) if a.tool else mezo_target.script("save-phoenix.py")
    for what, p in (("проверки", guard), ("инструмента", tool)):
        if not p.exists():
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: {what} нет — {p}")
            return 2
    workdir = Path(tempfile.mkdtemp(prefix="bite702-"))
    env = mezo_stand.stand_env(str(workdir))

    if a.db:
        db = Path(a.db)
        if not db.exists():
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: базы нет — {db}")
            return 2
        db_kind = "названа явно --db"
    else:
        # Снимок — всегда с живой базы КОНТУРА, а не «рядом с инструментом»: в клоне пакета
        # рядом лежит свой mezosync.db без таблиц памяти.
        live_db = mezo_target.LIVE_SCRIPTS.parent / "mezosync.db"
        if not live_db.exists():
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: живой базы нет — {live_db}")
            return 2
        db = workdir / "mezosync.db"
        mezo_stand.snapshot_db(live_db, db)
        db_kind = "согласованная КОПИЯ живой"

    runner, guard_run = tool, guard
    if a.breakage:
        # Поломка — в копии проверки; копия save-phoenix.py кладётся РЯДОМ с ней, чтобы
        # сохранение нашло именно сломанную (vnext_tool ищет и в своём каталоге).
        anchor, broken, _ = BREAKS[a.breakage]
        src = guard.read_text(encoding="utf-8")
        if src.count(anchor) != 1:
            print(f"⛔ ПОЛОМКА НЕ ВСТАЛА: место поломки «{a.breakage}» в проверке найдено "
                  f"{src.count(anchor)} раз, ждали ровно 1.\n"
                  "   Это отказ ОПЫТА: без поставленной поломки прошедшие случаи ничего не доказывают.")
            return 2
        bdir = workdir / "scripts"
        bdir.mkdir()
        guard_run = bdir / "guard-shift-end.py"
        guard_run.write_text(src.replace(anchor, broken), encoding="utf-8")
        runner = bdir / "save-phoenix.py"
        shutil.copyfile(tool, runner)
        env = dict(env, PYTHONPATH=str(tool.parent) + os.pathsep + env.get("PYTHONPATH", ""))
    else:
        env = dict(env, PYTHONPATH=str(tool.parent) + os.pathsep + env.get("PYTHONPATH", ""))

    print("═" * 92)
    print(f"ПРИЁМКА карточки #702 · проверка: {guard} · сохранение: {tool} · база: {db.name} ({db_kind})"
          + (f" · НАРОЧНАЯ ПОЛОМКА «{a.breakage}»" if a.breakage else ""))
    print("═" * 92)
    results = []
    try:
        cases_direct(load_guard(guard_run), results)
        st = Stand(runner, db, workdir, env)
        cases_save(st, results, workdir)
        cases_guard(st, results, guard_run)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    passed = sum(ok for _, ok in results)
    failed = [m for m, ok in results if not ok]
    print("─" * 92)
    print(f"прошло {passed} · провалилось {len(failed)}" + (f": {', '.join(failed)}" if failed else ""))
    if a.breakage:
        want = BREAKS[a.breakage][2]
        if set(failed) == want:
            print(f"НАРОЧНАЯ ПОЛОМКА ПОЙМАНА: провалились ровно {', '.join(sorted(want))} — "
                  "случаи смотрят на предмет")
        else:
            print(f"⚠️ НАРОЧНАЯ ПОЛОМКА: ждали провалов ровно {sorted(want)}, вышло {failed or 'ни одного'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
