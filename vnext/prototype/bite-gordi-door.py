#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-gordi-door — приёмка единой двери к инструментам (карточка #205).

    python C:/guts/.atlas/vnext-tools/bite-gordi-door.py

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① дверь и прямой вызов дают ОДНО И ТО ЖЕ на трёх инструментах                РАЗЛИЧАЮЩИЙ
  ② код возврата инструмента становится кодом двери, а не «улучшается»          РАЗЛИЧАЮЩИЙ
  ③ список подкоманд собран ЗАМЕРОМ: новый файл виден сразу, удалённый исчез    РАЗЛИЧАЮЩИЙ
  ④ библиотека (нет своего запуска) подкомандой НЕ становится                   РАЗЛИЧАЮЩИЙ
  ⑤ опечатка получает подсказку, а не молчаливый отказ                          РАЗЛИЧАЮЩИЙ
  ⑥ общая проверка (аренда) срабатывает через дверь на ЛЮБОМ инструменте        РАЗЛИЧАЮЩИЙ
  ⑦ КОНТРОЛЬ ГЛАВНОГО УСЛОВИЯ: дверь сломана — прямой вызов работает            РАЗЛИЧАЮЩИЙ
  ⑧ контроль: без аренд дверь ничего не добавляет к выводу инструмента

⚖️ Случай ⑦ важнее прочих: дверь имеет право существовать ТОЛЬКО пока её поломка
   не останавливает контур. Приёмка ломает её нарочно и проверяет, что работа идёт.

⛔ Живого контура НЕ касается: копия каталога инструментов и копия базы.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

LIVE_DB = mezo_paths.live_db()
LIVE_SCRIPTS = mezo_paths.live_scripts()
CASES = DIFFER = 0
# Живые метки замера: время и длительность отличаются между двумя вызовами по природе.
# Стираем их перед сравнением — иначе приёмка требовала бы от механизма остановить время.
NOISE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|за \d+(?:\.\d+)? с|\d+\.\d+ с")


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def run(argv, role=None):
    env = dict(os.environ)
    env.pop("MEZO_LEASE_BYPASS", None)
    if role:
        env["MEZO_ROLE"] = role
    else:
        env.pop("MEZO_ROLE", None)
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                       encoding="utf-8", timeout=180, env=env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="bite-door-"))
    scripts = d / "scripts"
    shutil.copytree(LIVE_SCRIPTS, scripts)
    db = d / "copy.db"
    shutil.copyfile(LIVE_DB, db)
    DOOR = str(scripts / "gordi.py")
    ok = True

    # ── ① ТРИ ИНСТРУМЕНТА: ДВЕРЬ == ПРЯМОЙ ВЫЗОВ ─────────────────────────────
    probes = [("backlog", ["--db", str(db), "list", "--role", "PROTO"]),
              ("lease", ["status", "--db", str(db)]),
              ("read-phoenix", ["--db", str(db), "--role", "PROTO", "--section", "state"])]
    same, report = True, []
    for name, args in probes:
        o1, c1 = run([str(scripts / f"{name}.py"), *args])
        o2, c2 = run([DOOR, name, *args])
        equal = NOISE.sub("~", o1) == NOISE.sub("~", o2) and c1 == c2
        same &= equal
        report.append(f"{name}:{'=' if equal else '≠'}({c1}/{c2})")
    ok &= case("① дверь и прямой вызов дают одно и то же на трёх инструментах",
               same, " · ".join(report) + " — живые метки замера стёрты перед сравнением",
               differ=True)

    # ── ② КОД ВОЗВРАТА НЕ «УЛУЧШАЕТСЯ» ───────────────────────────────────────
    o1, c1 = run([str(scripts / "backlog.py"), "--db", str(db), "status", "999999", "done",
                  "--actor", "PROTO", "--note", "нет такой карточки"])
    o2, c2 = run([DOOR, "backlog", "--db", str(db), "status", "999999", "done",
                  "--actor", "PROTO", "--note", "нет такой карточки"])
    ok &= case("② отказ инструмента доезжает кодом, а не глохнет в двери",
               c1 == c2 and c1 != 0,
               f"прямой {c1}, через дверь {c2} — дверь, «улучшающая» код, скрыла бы отказ",
               differ=True)

    # ── ③ СПИСОК — ЗАМЕРОМ КАТАЛОГА ──────────────────────────────────────────
    out_before, _ = run([DOOR])
    (scripts / "zzz-probe-tool.py").write_text(
        "import sys\nprint('я новый инструмент')\nsys.exit(0)\n", encoding="utf-8")
    out_after, _ = run([DOOR])
    (scripts / "zzz-probe-tool.py").unlink()
    out_gone, _ = run([DOOR])
    ok &= case("③ список собран ЗАМЕРОМ: новый виден сразу, удалённый исчезает",
               "zzz-probe-tool" not in out_before and "zzz-probe-tool" in out_after
               and "zzz-probe-tool" not in out_gone,
               "впечатанный список отстаёт молча — этот класс контур уже оплачивал",
               differ=True)

    # ── ④ БИБЛИОТЕКА НЕ ПОДКОМАНДА ───────────────────────────────────────────
    out_l, _ = run([DOOR])
    ok &= case("④ общая библиотека подкомандой не становится, а lease — становится",
               "mezo_paths" not in out_l and "lease" in out_l,
               "признак библиотеки — «нет своего запуска», а не «её кто-то импортирует»: "
               "первая редакция спрятала так сам инструмент аренды", differ=True)

    # ── ⑤ ОПЕЧАТКА ───────────────────────────────────────────────────────────
    out_t, code_t = run([DOOR, "backlgo", "list"])
    ok &= case("⑤ опечатка получает подсказку, а не молчаливый отказ",
               code_t == 2 and "backlog" in out_t,
               f"код {code_t}, в тексте названо близкое имя", differ=True)

    # ── ⑥ ОБЩАЯ ПРОВЕРКА РАБОТАЕТ ЧЕРЕЗ ДВЕРЬ ────────────────────────────────
    out, _ = run([str(scripts / "lease.py"), "take", "--db", str(db), "--role", "PROTO",
                  "--tools", "save-phoenix.py", "--reason", "проба двери", "--minutes", "10"])
    lid = "".join(c for c in out.split("АРЕНДА #")[1].split()[0] if c.isdigit())
    probe = d / "b.md"
    probe.write_text("проба\n" + "x" * 300, encoding="utf-8")
    out_d, code_d = run([DOOR, "save-phoenix", "--db", str(db), "--role", "PROTO",
                         "--section", "state", "--file", str(probe), "--allow-shrink"],
                        role="CORE")
    ok &= case("⑥ аренда срабатывает и через дверь (общее место работает для всех)",
               code_d == 3 and "В РАБОТЕ у роли" in out_d,
               f"код {code_d} — иначе дверь стала бы обходом собственных правил контура",
               differ=True)

    # ── ⑦ ГЛАВНОЕ УСЛОВИЕ: ДВЕРЬ СЛОМАНА — КОНТУР РАБОТАЕТ ───────────────────
    broken = scripts / "gordi.py"
    keep = broken.read_text(encoding="utf-8")
    broken.write_text("import sys\nraise RuntimeError('дверь нарочно сломана')\n",
                      encoding="utf-8")
    out_b, code_b = run([DOOR, "lease", "status", "--db", str(db)])
    out_direct, code_direct = run([str(scripts / "lease.py"), "status", "--db", str(db)])
    broken.write_text(keep, encoding="utf-8")
    ok &= case("⑦ дверь сломана — ПРЯМОЙ вызов работает (условие её существования)",
               code_b != 0 and code_direct == 0 and "АРЕНДЫ" in out_direct,
               f"дверь {code_b}, прямой вызов {code_direct} — удобство не имеет права стать "
               f"единой точкой отказа", differ=True)

    run([str(scripts / "lease.py"), "release", "--db", str(db), "--role", "PROTO", "--id", lid])

    # ── ⑧ КОНТРОЛЬ: БЕЗ АРЕНД ДВЕРЬ НИЧЕГО НЕ ДОБАВЛЯЕТ ──────────────────────
    o1, c1 = run([str(scripts / "backlog.py"), "--db", str(db), "list", "--role", "CORE"])
    o2, c2 = run([DOOR, "backlog", "--db", str(db), "list", "--role", "CORE"])
    ok &= case("⑧ контроль: без аренд вывод через дверь совпадает знак в знак",
               o1 == o2 and c1 == c2 == 0,
               "без этого случая совпадения выше могли бы держаться на случайности")

    shutil.rmtree(d, ignore_errors=True)
    print()
    if ok:
        print(f"✅ ДВЕРЬ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
