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

КАРТОЧКА #705 — второе направление: рука называет прочитанную версию (--expect-version),
роли набора BITE705C / BITE705D:
  ⑦  рука прочитала версию N, роль сохранила новую, рука пишет с --expect-version N — ОТКАЗ,
     код ≠ 0, тело роли на месте; в выводе роль, час UTC, «новых строк: 2»
  ⑦а то же холостым прогоном — тот же отказ, база не тронута
  ⑧  встречный: названа новейшая версия — запись проходит, строки о номере нет
  ⑨  номер версии другого раздела и несуществующий номер — отказ «версии … нет»
  ⑩  рука без --expect-version — запись проходит и строка «НОМЕР ПРОЧИТАННОЙ ВЕРСИИ НЕ НАЗВАН»;
     роль сама без флага — такой строки нет
  ⑪  строки разметки таблицы («|---|---|») чужой правкой не считаются и в показ не попадают
  (замечание CORE б: ①а — «Тело было бы записано», ① — «Тело записано»)

НАРОЧНЫЕ ПОЛОМКИ (в копии инструмента, во временном каталоге). Поломка, валящая всё подряд,
не доказывала бы, что случаи смотрят на предмет, поэтому у каждой — точный набор провалов:
  --break off     вызов проверки карточки #701 заменён пустым ответом ⇒ ①, ①а, ⑤б, ⑪
  --break expect  проверка новых версий карточки #705 выключена ⇒ ⑦, ⑦а

Запуск:
  python <пакет>/vnext/prototype/bite-phoenix-foreign-edit.py                  — обычный прогон
  python <пакет>/vnext/prototype/bite-phoenix-foreign-edit.py --break off      — ждём провалов ①, ①а, ⑤б, ⑪
  python <пакет>/vnext/prototype/bite-phoenix-foreign-edit.py --break expect   — ждём провалов ⑦, ⑦а
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
ROLE_C = "BITE705C"
ROLE_D = "BITE705D"
SECTION = "state"
WARN = "ЧУЖАЯ ПРАВКА УХОДИТ"
REFUSE = "⛔ ОТКАЗ"
NO_NUMBER = "НОМЕР ПРОЧИТАННОЙ ВЕРСИИ НЕ НАЗВАН"
# поломка → (что заменить, чем, какие случаи обязаны провалиться)
BREAKS = {
    "off": ("        foreign_lines, foreign_note = (foreign_edit_report(",
            "        foreign_lines, foreign_note = (([], '') if True else foreign_edit_report(",
            {"①", "①а", "⑤б", "⑪"}),
    "expect": ("    if not newer:\n        return None",
               "    if True:\n        return None",
               {"⑦", "⑦а"}),
}

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

    def save(self, role, lines, actor=None, dry=False, expect=None):
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
        if expect is not None:
            cmd += ["--expect-version", str(expect)]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self.env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def body(self, role):
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                          (role, SECTION)).fetchone()
        con.close()
        return row[0] if row else None

    def latest(self, role):
        """Номер новейшей версии раздела — то, что рука видит первой строкой --history."""
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT max(id) FROM phoenix_history WHERE role=? AND section=?",
                          (role, SECTION)).fetchone()
        con.close()
        return row[0]


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
    if WARN in out and ("Тело было бы записано" not in out or "Тело записано" in out):
        p.append("холостой прогон говорит «Тело записано», а ничего не записал (замечание CORE б)")
    verdict(r, "①а", "холостой прогон: предупреждение есть, база не тронута", p, out)
    code, out = st.save(ROLE_A, mine)
    p = expect_warn(code, out, 3, "COORD")
    if st.body(ROLE_A) != text(mine):
        p.append("в базе не текст роли — тело не записано")
    if WARN in out and "Тело записано" not in out:
        p.append("нет слов «Тело записано»")
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


def expect_refusal(code, out, words):
    problems = []
    if code == 0:
        problems.append("код 0, ждали отказ")
    if REFUSE not in out:
        problems.append("слова «ОТКАЗ» нет")
    if "OK phoenix/" in out:
        problems.append("строка «OK» есть — запись прошла")
    for w in words:
        if w not in out:
            problems.append(f"нет «{w}»")
    return problems


def run_cases_705(st, r):
    """Карточка #705: рука называет версию, которую читала."""
    c_base = ["# Раздел BITE705C — текст самой роли",
              "строка роли C номер один, до чтения руки",
              "строка роли C номер два, до чтения руки"]
    for lines in (c_base[:2], c_base):
        code, out = st.save(ROLE_C, lines)
        if code != 0:
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: подготовительное сохранение упало (код {code})")
            print(out)
            sys.exit(2)
    read_id = st.latest(ROLE_C)                      # рука COORD прочитала эту версию
    role_new = c_base + ["роль C дописала после чтения руки — строка один",
                         "роль C дописала после чтения руки — строка два"]
    st.save(ROLE_C, role_new)                        # роль тем временем сохранилась
    hand = c_base + ["правка COORD поверх прочитанного раздела роли C"]

    # ⑦а холостой прогон — тот же отказ, база не тронута
    code, out = st.save(ROLE_C, hand, actor="COORD", dry=True, expect=read_id)
    p = expect_refusal(code, out, [ROLE_C, "новых строк: 2"])
    if not re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", out):
        p.append("не назван час UTC")
    if st.body(ROLE_C) != text(role_new):
        p.append("тело роли в базе изменилось")
    verdict(r, "⑦а", "холостой прогон: тот же отказ, база не тронута", p, out)

    # ⑦ настоящая запись — отказ, тело роли на месте
    code, out = st.save(ROLE_C, hand, actor="COORD", expect=read_id)
    p = expect_refusal(code, out, [ROLE_C, "новых строк: 2", f"--expect-version {st.latest(ROLE_C)}"])
    if not re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", out):
        p.append("не назван час UTC")
    if st.body(ROLE_C) != text(role_new):
        p.append("тело роли затёрто — отказ не остановил запись")
    verdict(r, "⑦ ", "раздел менялся после прочитанной версии — отказ, роль, час, число строк; тело цело",
            p, out)

    # ⑧ встречный: рука перечитала, названа новейшая версия
    merged = role_new + ["правка COORD поверх перечитанного раздела роли C"]
    code, out = st.save(ROLE_C, merged, actor="COORD", expect=st.latest(ROLE_C))
    p = expect_quiet(code, out)
    if REFUSE in out:
        p.append("отказ при новейшей версии")
    if NO_NUMBER in out:
        p.append("строка «номер не назван» при названном номере")
    if st.body(ROLE_C) != text(merged):
        p.append("тело не записано")
    verdict(r, "⑧ ", "названа новейшая версия — запись проходит молча", p, out)

    # ⑨ номер версии другого раздела и несуществующий номер
    p = []
    code, out = st.save(ROLE_C, merged + ["попытка с чужим номером"], actor="COORD",
                        expect=st.latest(ROLE_A))
    p += [f"чужой номер: {x}" for x in expect_refusal(code, out, ["версии id=", "нет"])]
    code2, out2 = st.save(ROLE_C, merged + ["попытка с несуществующим номером"], actor="COORD",
                          expect=999999999)
    p += [f"несуществующий: {x}" for x in expect_refusal(code2, out2, ["версии id=999999999", "нет"])]
    if st.body(ROLE_C) != text(merged):
        p.append("тело изменилось")
    verdict(r, "⑨ ", "номер чужого раздела и несуществующий номер — отказ", p, out + out2)

    # ⑩ рука без флага — строка; роль сама без флага — строки нет
    code, out = st.save(ROLE_C, merged + ["правка OPSSRE без номера версии"], actor="OPSSRE")
    p = expect_quiet(code, out)
    if NO_NUMBER not in out:
        p.append("у руки без --expect-version строки «номер не назван» нет")
    elif out.find(NO_NUMBER) < out.find("OK phoenix/"):
        p.append("строка «номер не назван» не под «OK»")
    code2, out2 = st.save(ROLE_C, merged + ["роль C сохраняет сама, флаг ей не нужен"])
    if NO_NUMBER in out2:
        p.append("строка «номер не назван» у самой роли")
    verdict(r, "⑩ ", "рука без номера — строка под «OK»; сама роль — без неё", p, out + out2)

    # ⑪ разметка таблицы чужой правкой не считается и в показ не попадает
    d_base = ["# Раздел BITE705D — текст самой роли",
              "строка роли D, которую она писала сама"]
    st.save(ROLE_D, d_base)
    table = ["| поле таблицы COORD | значение поля |", "|---|---|",
             "| строка данных COORD | её значение |"]
    st.save(ROLE_D, d_base + table, actor="COORD")
    code, out = st.save(ROLE_D, d_base + ["роль D сохраняет текст без таблицы COORD"])
    p = expect_warn(code, out, 2, "COORD")
    if "|---|---|" in out:
        p.append("строка разметки таблицы показана как чужая правка")
    verdict(r, "⑪ ", "разметка таблицы не считается: «уходит строк: 2», «|---|» не показана", p, out)
    return r


def main():
    ap = argparse.ArgumentParser(description="Приёмка карточки #701: чужая правка памяти при сохранении")
    ap.add_argument("--tool", help="путь к save-phoenix.py (по умолчанию — испытуемая копия)")
    ap.add_argument("--db", help="путь к базе (по умолчанию — согласованная КОПИЯ живой)")
    ap.add_argument("--break", dest="breakage", choices=sorted(BREAKS),
                    help="нарочная поломка: off — вызов проверки карточки #701 выключен; "
                         "expect — проверка новых версий карточки #705 выключена")
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
    if a.breakage:
        # Поломка — в копии во временном каталоге; модули инструмента берутся из его каталога.
        anchor, broken, _ = BREAKS[a.breakage]
        src = tool.read_text(encoding="utf-8")
        if src.count(anchor) != 1:
            print(f"⛔ ПОЛОМКА НЕ ВСТАЛА: место поломки «{a.breakage}» в инструменте найдено "
                  f"{src.count(anchor)} раз, ждали ровно 1.\n"
                  "   Это отказ ОПЫТА: без поставленной поломки прошедшие случаи ничего не доказывают.")
            return 2
        runner = Path(workdir) / "save-phoenix.py"
        runner.write_text(src.replace(anchor, broken), encoding="utf-8")
        env = dict(env, PYTHONPATH=str(tool.parent) + os.pathsep + env.get("PYTHONPATH", ""))

    print("═" * 92)
    print(f"ПРИЁМКА карточки #701 и карточки #705 · инструмент: {tool} · база: {db.name} ({db_kind})"
          + (f" · НАРОЧНАЯ ПОЛОМКА «{a.breakage}»" if a.breakage else ""))
    print("═" * 92)
    st = Stand(runner, db, workdir, env)
    results = run_cases_705(st, run_cases(st))
    shutil.rmtree(workdir, ignore_errors=True)

    passed = sum(ok for _, ok in results)
    failed = [m.strip() for m, ok in results if not ok]
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
