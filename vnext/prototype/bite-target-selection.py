# -*- coding: utf-8 -*-
r"""ПРИЁМКА выбора испытуемой копии в общем наборе (bite-all.py --target).

Свойство: прогон по КОПИИ и прогон по ЖИВОМУ смотрят на РАЗНЫЕ механизмы, и перепутать их
нельзя. Доказывается нарочной поломкой копии — без неё «прогон по образцу» есть намерение,
а не механизм: он был бы неотличим от прогона по живому.

🪤 И главный случай ⑥ — оплаченный ошибкой постановки опыта. Первая поломка ломала механизм,
которого НЕ ЗОВЁТ НИКТО: набор напечатал «держится 36, сломано 0» при полностью убитом файле.
Вывод «выбор копии не работает» был бы НЕВЕРЕН — не работал мой опыт. Отсюда требование:
набор обязан САМ печатать границу — сколько механизмов он реально испытывает.

⛔ Живого контура не касается: копии строятся во временном каталоге.
⏱ Гоняет набор с --only на трёх приёмках, а не целиком: предмет здесь — выбор копии.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BITE_ALL = os.path.join(HERE, "bite-all.py")
LIVE = r"C:\guts\.atlas\.mezosync\scripts"
# приёмки, которые ТОЧНО зовут механизм через резолвер (замер: script("read-messages.py"))
ONLY = "to-me-empty"

CASES = 0
DIFFERENTIATING = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run(target=None, only=ONLY):
    cmd = [sys.executable, BITE_ALL, "--only", only]
    if target:
        cmd += ["--target", target]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def copy_scripts(tmp, name, break_files=()):
    dst = os.path.join(tmp, name, "scripts")
    shutil.copytree(LIVE, dst)
    for f in break_files:
        with open(os.path.join(dst, f), "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.exit('НАРОЧНО СЛОМАН В КОПИИ')\n")
    return dst


def main() -> int:
    if not os.path.isdir(LIVE):
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет живого каталога {LIVE} — строить копии не из чего")
        return 1
    tmp = tempfile.mkdtemp(prefix="bite-target-sel-")
    ok = True

    # ① ЦЕЛАЯ КОПИЯ — зелёное. Контроль: набор вообще умеет проходить по копии.
    whole = copy_scripts(tmp, "whole")
    out_whole, code_whole = run(whole)
    ok &= case("① целая копия — прогон зелёный (контроль: по копии вообще идём)",
               code_whole == 0 and "СЛОМАНО" not in out_whole,
               f"код {code_whole}; без этого случая краснота на сломанной ничего не значит")

    # ② НАРОЧНАЯ ПОЛОМКА КОПИИ — красное. Ломаем то, что набор ДЕЙСТВИТЕЛЬНО зовёт.
    broken = copy_scripts(tmp, "broken", break_files=("read-messages.py",))
    out_bad, code_bad = run(broken)
    ok &= case("② сломанный в копии механизм — прогон по копии КРАСНЕЕТ",
               code_bad == 1 and "СЛОМАНО" in out_bad,
               f"код {code_bad}; поломка копии обязана быть видна", differ=True)

    # ③ ВСТРЕЧНЫЙ и ГЛАВНЫЙ: та же поломка НЕ трогает прогон по живому.
    #    Без него нельзя утверждать, что копии РАЗНЫЕ, а не одна и та же.
    out_live, code_live = run(None)
    ok &= case("③ живой прогон при сломанной копии остаётся зелёным (встречный к ②)",
               code_live == 0 and "СЛОМАНО" not in out_live,
               "иначе доказано лишь «что-то покраснело», а не что копии различаются",
               differ=True)

    # ④ ПОДПИСЬ НАЗЫВАЕТ КОПИЮ И НЕ ЗАШИТА. Строка «испытан живой модуль» при работе
    #    по шаблону уже однажды соврала — подпись обязана СПРАШИВАТЬ.
    ok &= case("④ подпись называет ИМЕННО испытанную копию, а не общие слова",
               broken in out_bad and "ЖИВОЙ КОНТУР" in out_live and "ЖИВОЙ" not in out_bad,
               "путь копии печатается дословно; у живого прогона — своя пометка", differ=True)

    # ⑤ КОПИИ НЕТ ВОВСЕ — отказ мерить (код 2), не «зелено» и не «сломано».
    out_miss, code_miss = run(os.path.join(tmp, "нет-такого"))
    ok &= case("⑤ несуществующая копия — отказ мерить, отдельный код",
               code_miss == 2 and "НЕ ЗАПУСТИЛСЯ НАБОР" in out_miss,
               f"код {code_miss}; опечатка в пути обязана звучать иначе, чем чистота",
               differ=True)

    # ⑥ ГРАНИЦА НАБОРА ПЕЧАТАЕТСЯ. Оплачено ошибкой опыта: сломанный, но никем не
    #    вызываемый механизм оставляет прогон зелёным — и это ЗАКОННО. Незаконно молчать.
    unused = copy_scripts(tmp, "unused", break_files=("set-rule.py",))
    out_unused, code_unused = run(unused)
    ok &= case("⑥ поломка НИКЕМ не вызываемого механизма: зелёное, но граница названа",
               code_unused == 0 and "ГРАНИЦА НАБОРА" in out_unused
               and "испытано механизмов" in out_unused,
               "зелёное без границы читалось бы как «копия цела» — ложный ноль", differ=True)

    # ⑦ ВСТРЕЧНЫЙ к ⑥: у ЖИВОГО прогона границы копии нет — её печатать нечестно,
    #    живой контур и есть предмет, а не выборка из него.
    ok &= case("⑦ живой прогон не печатает границу копии (встречный к ⑥)",
               "ГРАНИЦА НАБОРА" not in out_live,
               "перенос чужой оговорки на другой случай — тоже способ соврать формой")

    print()
    print(f"✅ ВЫБОР КОПИИ ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 ВЫБОР КОПИИ НЕ ПРИНЯТ — числа из прогона по образцу нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
