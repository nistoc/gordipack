#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-measure-yardstick — замер прежних слов обязан называть, ЧЕМ мерил.

ЗАЧЕМ (заявка @COORD, записка #3702; поддержана @CHROME, #3704, его собственным случаем).
20.08 вывод замера вырос со 131 до 181 за один час, и НИ ОДНА роль ничего не ухудшила:
в 06:39 UTC в словарь добавились два слова. Число было арифметически верным и по существу
ложным — читалось как «контур деградировал».

🎯 КЛАСС: ЧИСЛО БЕЗ СВОЕЙ МЕРКИ ЛЖЁТ, ОСТАВАЯСЬ ПРАВИЛЬНЫМ. Оговорка в записке его не
лечит: её пишет тот, кто и так помнит. Лечит то, что мерку печатает САМ замер.

    python <КОНТУР>/vnext-tools/bite-measure-yardstick.py
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

TOOL = Path(__file__).resolve().parent / "measure-old-words.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def стенд(tmp: Path, версия, есть_правило: bool = True) -> Path:
    """Копия живой базы с подменённой версией правила-словаря.

    Копия, а не живая база: приёмка, правящая живое, однажды и правит его насовсем.
    """
    db = tmp / f"c{версия}.db"
    shutil.copyfile(mezo_paths.live_db(), db)
    con = sqlite3.connect(str(db))
    if есть_правило:
        con.execute("UPDATE rules SET version = ? WHERE rule_key = 'plain-words'", (версия,))
    else:
        con.execute("DELETE FROM rules WHERE rule_key = 'plain-words'")
    con.commit()
    con.close()
    return db


def run(db: Path, *args):
    r = subprocess.run([sys.executable, str(TOOL), "--db", str(db), "--memories", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    ok = True
    if not TOOL.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого нет — {TOOL}")
        return 2

    tmp = mezo_stand.new("bite-yard-")
    try:
        out7, _ = run(стенд(tmp, 7))
        ok &= case("① мерка названа: версия правила-словаря взята ИЗ БАЗЫ",
                   "v7" in out7 and "МЕРЕНО" in out7,
                   "без версии два вывода несравнимы, а выглядят сравнимыми — ровно то, "
                   "на чём 20.08 число выросло со 131 до 181 без единой правки памятей",
                   differ=True)

        out9, _ = run(стенд(tmp, 9))
        ok &= case("② ВСТРЕЧНЫЙ: другая версия в базе — другая мерка в выводе",
                   "v9" in out9 and "v7" not in out9,
                   "без этого случая ① зеленел бы и на впечатанной строке: печатать «v7» "
                   "можно и не спрашивая базу", differ=True)

        outnone, _ = run(стенд(tmp, 0, есть_правило=False))
        ok &= case("③ правила нет в базе — СКАЗАНО вслух, а не молча пропущено",
                   "МЕРЕНО" in outnone and ("не прочиталось" in outnone or "?" in outnone),
                   "пропавшая мерка опаснее неверной: вывод выглядит полным и не даёт "
                   "повода усомниться", differ=True)

        ok &= case("④ число слов САМОГО признака названо рядом с версией правила",
                   "слов в признаке" in out7,
                   "правило и признак живут порознь и расходятся молча: «мерено v4» при "
                   "признаке, не знающем новых слов, соврало бы точнее прежнего", differ=True)

        short, _ = run(стенд(tmp, 7), "--short")
        ok &= case("⑤ короткая форма тоже несёт мерку — её встраивают в общий прогон",
                   "plain-words v7" in short,
                   "именно короткую строку роль видит при каждом пробуждении; мерка, "
                   "выпавшая из неё, не существует для читателя", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ МЕРКА НАЗВАНА — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
