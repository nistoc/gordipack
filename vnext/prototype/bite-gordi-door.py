#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-gordi-door — приёмка вспомогательного запуска инструментов (карточка #205).

    python <КОНТУР>/vnext-tools/bite-gordi-door.py

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① вспомогательный запуск и прямой вызов дают ОДНО И ТО ЖЕ на трёх инструментах   РАЗЛИЧАЮЩИЙ
  ② код возврата инструмента становится его кодом, а не «улучшается»          РАЗЛИЧАЮЩИЙ
  ③ список подкоманд собран ЗАМЕРОМ: новый файл виден сразу, удалённый исчез    РАЗЛИЧАЮЩИЙ
  ④ библиотека (нет своего запуска) подкомандой НЕ становится                   РАЗЛИЧАЮЩИЙ
  ⑤ опечатка получает подсказку, а не молчаливый отказ                          РАЗЛИЧАЮЩИЙ
  ⑥ общая проверка (объявление о правке) срабатывает через него на ЛЮБОМ инструменте        РАЗЛИЧАЮЩИЙ
  ⑦ КОНТРОЛЬ ГЛАВНОГО УСЛОВИЯ: вспомогательный запуск сломан — прямой вызов работает            РАЗЛИЧАЮЩИЙ
  ⑧ контроль: без объявлений вспомогательный запуск ничего не добавляет к выводу инструмента

⚖️ Случай ⑦ важнее прочих: вспомогательный запуск имеет право существовать ТОЛЬКО пока
   его поломка не останавливает контур. Приёмка ломает его нарочно и проверяет работу.

⛔ Живого контура НЕ касается: копия каталога инструментов и копия базы.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

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
    # Приёмка идёт на КОПИИ базы, а объявления о правке действуют в живом контуре —
    # без этой договорённости случай ⑥ проверял бы не механизм, а собственную песочницу.
    env["MEZO_LEASE_TEST"] = "1"
    if role:
        env["MEZO_ROLE"] = role
    else:
        env.pop("MEZO_ROLE", None)
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                       encoding="utf-8", timeout=180, env=env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    d = mezo_stand.new("bite-door-")
    # Стенд — НАСТОЯЩАЯ раскладка контура: .mezosync/scripts рядом с .mezosync/mezosync.db.
    # Иначе механизмы не находят корень и отказывают (громкая редакция помощника, 20.08).
    контур = d / ".mezosync"
    scripts = контур / "scripts"
    shutil.copytree(LIVE_SCRIPTS, scripts)
    db = контур / "mezosync.db"
    shutil.copyfile(LIVE_DB, db)
    DOOR = str(scripts / "gordi.py")
    # Изоляция от объявлений, действующих в живом контуре прямо сейчас (см. ту же правку
    # в приёмке объявлений): иначе исход зависит от чужой работы в соседнем окне.
    import sqlite3
    _c = sqlite3.connect(db)
    _c.execute("DELETE FROM tool_leases")
    _c.commit()
    _c.close()
    ok = True

    # ── ① ТРИ ИНСТРУМЕНТА: ВСПОМОГАТЕЛЬНЫЙ ЗАПУСК == ПРЯМОЙ ВЫЗОВ ─────────────────────────────
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
    ok &= case("① вспомогательный запуск и прямой вызов дают одно и то же на трёх инструментах",
               same, " · ".join(report) + " — живые метки замера стёрты перед сравнением",
               differ=True)

    # ── ② КОД ВОЗВРАТА НЕ «УЛУЧШАЕТСЯ» ───────────────────────────────────────
    o1, c1 = run([str(scripts / "backlog.py"), "--db", str(db), "status", "999999", "done",
                  "--actor", "PROTO", "--note", "нет такой карточки"])
    o2, c2 = run([DOOR, "backlog", "--db", str(db), "status", "999999", "done",
                  "--actor", "PROTO", "--note", "нет такой карточки"])
    ok &= case("② отказ инструмента доезжает кодом, а не глохнет в нём",
               c1 == c2 and c1 != 0,
               f"прямой {c1}, через него {c2} — запуск, «улучшающий» код, скрыл бы отказ",
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
               "первая редакция спрятала так сам инструмент объявлений", differ=True)

    # ── ⑤ ОПЕЧАТКА ───────────────────────────────────────────────────────────
    out_t, code_t = run([DOOR, "backlgo", "list"])
    ok &= case("⑤ опечатка получает подсказку, а не молчаливый отказ",
               code_t == 2 and "backlog" in out_t,
               f"код {code_t}, в тексте названо близкое имя", differ=True)

    # ── ⑥ ОБЩАЯ ПРОВЕРКА РАБОТАЕТ ЧЕРЕЗ НЕГО ────────────────────────────────
    out, _ = run([str(scripts / "lease.py"), "take", "--db", str(db), "--role", "PROTO",
                  "--tools", "save-phoenix.py", "--reason", "проба вспомогательного запуска", "--minutes", "10"])
    lid = "".join(c for c in out.split("ОБЪЯВЛЕНО #")[1].split()[0] if c.isdigit())
    probe = d / "b.md"
    probe.write_text("проба\n" + "x" * 300, encoding="utf-8")
    out_d, code_d = run([DOOR, "save-phoenix", "--db", str(db), "--role", "PROTO",
                         "--section", "state", "--file", str(probe), "--allow-shrink"],
                        role="CORE")
    ok &= case("⑥ объявление срабатывает и через него (общее место работает для всех)",
               code_d == 3 and "В РАБОТЕ у роли" in out_d,
               f"код {code_d} — иначе он стал бы обходом собственных правил контура",
               differ=True)

    # ── ⑦ ГЛАВНОЕ УСЛОВИЕ: ЗАПУСК СЛОМАН — КОНТУР РАБОТАЕТ ───────────────────
    broken = scripts / "gordi.py"
    keep = broken.read_text(encoding="utf-8")
    broken.write_text("import sys\nraise RuntimeError('вспомогательный запуск сломан нарочно')\n",
                      encoding="utf-8")
    out_b, code_b = run([DOOR, "lease", "status", "--db", str(db)])
    out_direct, code_direct = run([str(scripts / "lease.py"), "status", "--db", str(db)])
    broken.write_text(keep, encoding="utf-8")
    ok &= case("⑦ вспомогательный запуск сломан — ПРЯМОЙ вызов работает (условие его существования)",
               code_b != 0 and code_direct == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out_direct,
               f"вспомогательный запуск {code_b}, прямой вызов {code_direct} — удобство не имеет права стать "
               f"единой точкой отказа", differ=True)

    run([str(scripts / "lease.py"), "release", "--db", str(db), "--role", "PROTO", "--id", lid])

    # ── ⑧ КОНТРОЛЬ: БЕЗ ОБЪЯВЛЕНИЙ ОН НИЧЕГО НЕ ДОБАВЛЯЕТ ──────────────────────
    o1, c1 = run([str(scripts / "backlog.py"), "--db", str(db), "list", "--role", "CORE"])
    o2, c2 = run([DOOR, "backlog", "--db", str(db), "list", "--role", "CORE"])
    ok &= case("⑧ контроль: без объявлений вывод через него совпадает знак в знак",
               o1 == o2 and c1 == c2 == 0,
               "без этого случая совпадения выше могли бы держаться на случайности")

    mezo_stand.release(d)  # уборка отложена до исхода прогона
    print()
    if ok:
        print(f"✅ ВСПОМОГАТЕЛЬНЫЙ ЗАПУСК — ПРИНЯТ — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
