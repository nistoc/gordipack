#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Приёмка карточки #701 — сохранение памяти предупреждает, когда затирает чужую правку раздела.

ПРЕДМЕТ. Роль прочитала раздел, потом другая рука (COORD с --actor COORD) его поправила,
потом роль сохраняет СВОЙ текст, собранный до правки. Без проверки чужие строки исчезают
молча. Проверка в save-phoenix.py (foreign_edit_report) говорит об этом сразу под «OK»:
кто правил, час UTC, сколько строк уходит. Тело записывается всё равно — это предупреждение,
а не отказ (решение и замер — комментарий на карточке до кода).

ЧЕМ СУДИМ. Настоящие сохранения на СОГЛАСОВАННОЙ КОПИИ живой базы (mezo_stand.snapshot_db),
у особых ролей набора BITE701A / BITE701B — их историю пишет только этот набор, поэтому
«после прошлого сохранения» определено точно. Живая база не открывается на запись.

СЛУЧАИ (номера ①–③ — пункты критерия карточки):
  ①  COORD дописала раздел, роль сохраняет текст без её строк — предупреждение, имя COORD,
     час UTC, «уходит строк: 3»; код 0; в базе — текст роли (тело записано)
  ①а то же холостым прогоном (--dry-run) — предупреждение есть, база не тронута
  ②  чужой правки после прошлого сохранения роли не было — предупреждения нет
  ③  роль сама убрала строки, которые сама же и добавила (без --actor) — предупреждения нет
  ④  роль перечитала раздел после чужой правки и слила её строки — предупреждения нет
  ⑤  раздел ЗАВЕЛА другая рука (первая версия) — переписать его можно молча; а вторая
     чужая правка поверх — уже предупреждение
  ⑥  чужая рука, ни разу не писавшая раздел, сама сокращает его — предупреждения нет
     (её базы нет; судить её по всей истории значило бы шуметь на каждой правке)

НАРОЧНАЯ ПОЛОМКА (--break off): вызов проверки в копии инструмента заменён пустым ответом ⇒
① и ①а и вторая половина ⑤ обязаны провалиться, встречные ②③④⑥ — пройти. Поломка, валящая
всё подряд, не доказывала бы, что случаи смотрят на предмет.

Запуск:
  python <пакет>/vnext/prototype/bite-phoenix-foreign-edit.py               — обычный прогон
  python <пакет>/vnext/prototype/bite-phoenix-foreign-edit.py --break off   — ждём провалов ①, ①а, ⑤б
"""
import argparse
import os
import re
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

ROLE_A = "BITE701A"
ROLE_B = "BITE701B"
SECTION = "state"
WARN = "ЧУЖАЯ ПРАВКА УХОДИТ"
CALL = "        foreign_lines, foreign_note = (foreign_edit_report("
BROKEN = "        foreign_lines, foreign_note = (([], '') if True else foreign_edit_report("

# Строки ≥ 12 знаков: короче проверка их не считает (lines_of в save-phoenix.py).
BASE = ["# Состояние роли BITE701A на начало опыта",
        "строка роли номер один — её писала сама роль",
        "строка роли номер два — её писала сама роль"]
COORD_ADD = ["правка COORD: первая добавленная строка",
             "правка COORD: вторая добавленная строка",
             "правка COORD: третья добавленная строка"]


def text(lines):
    return "\n".join(lines) + "\n"


class Stand:
    def __init__(self, tool, db, workdir, env):
        self.tool, self.db, self.workdir, self.env = tool, db, Path(workdir), env
        self.n = 0

    def save(self, role, lines, actor=None, dry=False):
        """Сохранение раздела. Возвращает (код, весь вывод)."""
        self.n += 1
        f = self.workdir / f"body{self.n}.md"
        f.write_text(text(lines), encoding="utf-8")
        cmd = [sys.executable, str(self.tool), "--db", str(self.db), "--role", role,
               "--section", SECTION, "--file", str(f), "--allow-shrink"]
        if actor:
            cmd += ["--actor", actor]
        if dry:
            cmd += ["--dry-run"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self.env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def body(self, role):
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                          (role, SECTION)).fetchone()
        con.close()
        return row[0] if row else None


def verdict(results, mark, what, problems, output=""):
    ok = not problems
    results.append((mark, ok))
    print(f"  {'✅' if ok else '🔴'} {mark} {what}")
    if not ok:
        print(f"       {' · '.join(problems)}")
        for l in [l for l in output.splitlines() if l.strip()][:4]:
            print(f"       │ {l[:100]}")


def expect_warn(code, out, n_lines, who):
    problems = []
    if code != 0:
        problems.append(f"код {code}, ждали 0 (это предупреждение, а не отказ)")
    if WARN not in out:
        problems.append("предупреждения НЕТ")
        return problems
    if who not in out:
        problems.append(f"не назван правивший {who}")
    if not re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", out):
        problems.append("не назван час UTC")
    if f"уходит строк: {n_lines}" not in out:
        problems.append(f"не сказано «уходит строк: {n_lines}»")
    if out.find("OK phoenix/") < 0 or out.find(WARN) < out.find("OK phoenix/"):
        problems.append("предупреждение не под строкой «OK»")
    return problems


def expect_quiet(code, out):
    problems = []
    if code != 0:
        problems.append(f"код {code}, ждали 0")
    if "OK phoenix/" not in out:
        problems.append("строки «OK» нет")
    if WARN in out:
        problems.append("предупреждение сказано, а не должно")
    return problems


def run_cases(st):
    r = []
    # подготовка: два собственных сохранения роли A
    for lines in (BASE[:2], BASE):
        code, out = st.save(ROLE_A, lines)
        if code != 0:
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: подготовительное сохранение упало (код {code})")
            print(out)
            sys.exit(2)
    read_by_a = list(BASE)                       # роль A «прочитала» раздел

    # ① COORD дописывает, A сохраняет текст, собранный до правки
    st.save(ROLE_A, read_by_a + COORD_ADD, actor="COORD")
    mine = read_by_a + ["своя новая строка роли после чтения раздела"]
    code, out = st.save(ROLE_A, mine, dry=True)
    p = expect_warn(code, out, 3, "COORD")
    body_after_dry = st.body(ROLE_A)
    if body_after_dry != text(read_by_a + COORD_ADD):
        p.append("холостой прогон изменил тело в базе")
    verdict(r, "①а", "холостой прогон: предупреждение есть, база не тронута", p, out)
    code, out = st.save(ROLE_A, mine)
    p = expect_warn(code, out, 3, "COORD")
    if st.body(ROLE_A) != text(mine):
        p.append("в базе не текст роли — тело не записано")
    verdict(r, "① ", "чужая правка уходит — предупреждение, кто правил и час UTC; тело записано", p, out)

    # ② чужой правки после прошлого сохранения не было
    code, out = st.save(ROLE_A, mine + ["ещё одна строка роли, чужих правок не было"])
    verdict(r, "② ", "чужой правки после прошлого сохранения нет — без нового вывода",
            expect_quiet(code, out), out)

    # ③ роль сама убирает свои же строки (без --actor)
    code, out = st.save(ROLE_A, mine)
    verdict(r, "③ ", "роль убрала строки, которые добавила сама, — без предупреждения",
            expect_quiet(code, out), out)

    # ④ чужая правка, роль перечитала и слила её строки
    extra = ["правка COORD позже: строка для слияния ролью"]
    st.save(ROLE_A, mine + extra, actor="COORD")
    code, out = st.save(ROLE_A, mine + extra + ["строка роли поверх слитой правки"])
    verdict(r, "④ ", "роль перечитала и сохранила чужие строки — без предупреждения",
            expect_quiet(code, out), out)

    # ⑤ раздел завела другая рука
    first = ["# Раздел BITE701B завела COORD", "первая строка COORD в новом разделе роли",
             "вторая строка COORD в новом разделе роли"]
    st.save(ROLE_B, first, actor="COORD")
    code, out = st.save(ROLE_B, ["# Раздел BITE701B переписан самой ролью",
                                 "роль переписала заведённый за неё раздел целиком"])
    verdict(r, "⑤а", "первую версию завела другая рука — переписать её можно молча",
            expect_quiet(code, out), out)
    cur = ["# Раздел BITE701B переписан самой ролью",
           "роль переписала заведённый за неё раздел целиком"]
    st.save(ROLE_B, cur + ["вторая правка COORD поверх текста роли"], actor="COORD")
    code, out = st.save(ROLE_B, cur + ["строка роли без чужой второй правки"])
    verdict(r, "⑤б", "вторая чужая правка поверх — предупреждение",
            expect_warn(code, out, 1, "COORD"), out)

    # ⑥ чужая рука, ни разу не писавшая раздел A, сокращает его
    code, out = st.save(ROLE_A, BASE, actor="OPSSRE")
    verdict(r, "⑥ ", "чужая рука без своих версий раздела сокращает его — без предупреждения",
            expect_quiet(code, out), out)
    return r


def main():
    ap = argparse.ArgumentParser(description="Приёмка карточки #701: чужая правка памяти при сохранении")
    ap.add_argument("--tool", help="путь к save-phoenix.py (по умолчанию — испытуемая копия)")
    ap.add_argument("--db", help="путь к базе (по умолчанию — согласованная КОПИЯ живой)")
    ap.add_argument("--break", dest="breakage", choices=["off"],
                    help="нарочная поломка: off — вызов проверки в копии инструмента выключен")
    a = ap.parse_args()

    tool = Path(a.tool) if a.tool else mezo_target.script("save-phoenix.py")
    if not tool.exists():
        print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: инструмента нет — {tool}")
        return 2
    workdir = tempfile.mkdtemp(prefix="bite701-")
    env = mezo_stand.stand_env(workdir)

    if a.db:
        db = Path(a.db)
        if not db.exists():
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: базы нет — {db}")
            return 2
        db_kind = "названа явно --db"
    else:
        # Снимок — всегда с живой базы КОНТУРА (только чтение резервным копированием, запись —
        # в копию набора), а не «рядом с инструментом»: в клоне пакета рядом лежит свой
        # mezosync.db без таблиц памяти, и опыт падал бы не по своей причине.
        live_db = mezo_target.LIVE_SCRIPTS.parent / "mezosync.db"
        if not live_db.exists():
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: живой базы нет — {live_db}")
            return 2
        db = Path(workdir) / "mezosync.db"
        mezo_stand.snapshot_db(live_db, db)
        db_kind = "согласованная КОПИЯ живой"

    runner = tool
    if a.breakage == "off":
        # Поломка — в копии во временном каталоге; модули инструмента берутся из его каталога.
        src = tool.read_text(encoding="utf-8")
        if CALL not in src:
            print("⛔ ПОЛОМКА НЕ ВСТАЛА: строки вызова проверки в инструменте нет.\n"
                  "   Это отказ ОПЫТА: без поставленной поломки прошедшие случаи ничего не доказывают.")
            return 2
        runner = Path(workdir) / "save-phoenix.py"
        runner.write_text(src.replace(CALL, BROKEN), encoding="utf-8")
        env = dict(env, PYTHONPATH=str(tool.parent) + os.pathsep + env.get("PYTHONPATH", ""))

    print("═" * 92)
    print(f"ПРИЁМКА карточки #701 · инструмент: {tool} · база: {db.name} ({db_kind})"
          + (" · НАРОЧНАЯ ПОЛОМКА: проверка выключена" if a.breakage else ""))
    print("═" * 92)
    results = run_cases(Stand(runner, db, workdir, env))
    shutil.rmtree(workdir, ignore_errors=True)

    passed = sum(ok for _, ok in results)
    failed = [m.strip() for m, ok in results if not ok]
    print("─" * 92)
    print(f"прошло {passed} · провалилось {len(failed)}" + (f": {', '.join(failed)}" if failed else ""))
    if a.breakage:
        want = {"①", "①а", "⑤б"}
        if set(failed) == want:
            print("НАРОЧНАЯ ПОЛОМКА ПОЙМАНА: провалились ровно ①, ①а, ⑤б — случаи смотрят на предмет")
        else:
            print(f"⚠️ НАРОЧНАЯ ПОЛОМКА: ждали провалов ровно {sorted(want)}, вышло {failed or 'ни одного'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
