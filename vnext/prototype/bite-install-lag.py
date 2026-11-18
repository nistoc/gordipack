#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""ПРИЁМКА guard-install-lag.py — проверки отставания установки второго набора (карточка #758).

Судит не «печатает ли что-нибудь», а четыре свойства, ради которых проверка заведена:
  ① отставание НАХОДИТСЯ и краснеет кодом 1, называя имя;
  ② законное отсутствие с причиной красное НЕ даёт — иначе перечень бесполезен;
  ③ имя, установленное в ПЕРВОМ наборе, отставанием не считается (одно имя, два места:
     guard-shift-end.py стои́т именно так, и без этого он читался бы отсутствующим);
  ④ протухшее оправдание и оправдание без причины — дефекты перечня, а не тихое гашение;
  ⑤ «сверять нечем» говорится СЛОВАМИ и не выдаётся за «отставания нет»;
  ⑥ граница суждения (карточка #771): на обоих исходах названо, что сличены ИМЕНА, и кто
     сличает ТЕЛА; при «сверять нечем» этой строки нет.

Все случаи идут на каталогах-пустышках в своей временной папке: приёмка, судящая установку
по живому контуру, меняла бы вердикт от чужой работы, а не от своего предмета.

    python bite-install-lag.py            # случаи
    python bite-install-lag.py --selftest # доказать, что приёмка умеет краснеть
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "guard-install-lag.py"

PASSED = []
FAILED = []


def check(name, expect_code, expect_in, forbid_in, pack, install, container, tool=None):
    """Один случай: прогон проверки на пустышках и суд по коду и словам вывода."""
    run = subprocess.run(  # env: caller — стенда нет вовсе: оба корня и контейнер даны
                          # доводами, файл путей и база не читаются (ветвь resolve_paths
                          # при --pack-dir и --install-dir не вызывается)
        [sys.executable, str(tool or TOOL),
         "--pack-dir", str(pack), "--install-dir", str(install), "--container", str(container)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (run.stdout or "") + (run.stderr or "")
    problems = []
    if expect_code is not None and run.returncode != expect_code:
        problems.append(f"код {run.returncode}, ждали {expect_code}")
    for needle in expect_in:
        if needle not in out:
            problems.append(f"в выводе НЕТ «{needle}»")
    for needle in forbid_in:
        if needle in out:
            problems.append(f"в выводе ЕСТЬ запрещённое «{needle}»")
    if problems:
        FAILED.append((name, problems, out))
        print(f"⛔ {name}")
        for p in problems:
            print(f"     {p}")
    else:
        PASSED.append(name)
        print(f"✅ {name}")
    return run


def stand(root, pack_names, install_names, first_names=()):
    """Три каталога-пустышки: второй набор пакета, установка у контура, первый набор."""
    pack = root / "pack"
    install = root / "install"
    container = root / "container"
    scripts = container / ".mezosync" / "scripts"
    migrations = scripts / "migrations"
    for d in (pack, install, migrations):
        d.mkdir(parents=True, exist_ok=True)
    for name in pack_names:
        (pack / name).write_text("# пустышка пакета\n", encoding="utf-8")
    for name in install_names:
        (install / name).write_text("# пустышка установки\n", encoding="utf-8")
    for name in first_names:
        (scripts / name).write_text("# пустышка первого набора\n", encoding="utf-8")
    return pack, install, container


def run_cases(tool=None):
    root = Path(tempfile.mkdtemp(prefix="bite-install-lag-"))
    try:
        # ① отставание находится и краснеет, называя имя
        pack, install, container = stand(root / "c1", ["a.py", "b.py"], ["a.py"])
        check("① отставание найдено, названо именем, код 1",
              1, ["ОТСТАВАНИЕ УСТАНОВКИ: 1", "b.py"], [], pack, install, container, tool)

        # ② ВСТРЕЧНЫЙ: полная установка — зелёное и код 0. Без него ① прошёл бы
        #    и на проверке, которая краснеет всегда.
        pack, install, container = stand(root / "c2", ["a.py", "b.py"], ["a.py", "b.py"])
        check("② встречный: установлено всё — код 0, «отставания установки нет»",
              0, ["отставания установки нет"], ["ОТСТАВАНИЕ УСТАНОВКИ"],
              pack, install, container, tool)

        # ③ законное отсутствие: берём настоящее имя из перечня проверки
        pack, install, container = stand(root / "c3", ["feed-index.py", "a.py"], ["a.py"])
        check("③ законное отсутствие не краснеет и печатается с причиной",
              0, ["законных отсутствий 1", "feed-index.py", "2026-08-27"],
              ["ОТСТАВАНИЕ УСТАНОВКИ"], pack, install, container, tool)

        # ④ одно имя, два места: установлено в ПЕРВОМ наборе — не отставание
        pack, install, container = stand(root / "c4", ["x.py"], [], first_names=["x.py"])
        check("④ установленное в первом наборе отставанием не считается",
              0, ["отставания установки нет"], ["x.py"], pack, install, container, tool)

        # ⑤ протухшее оправдание: имя из перечня УСТАНОВЛЕНО
        pack, install, container = stand(root / "c5", ["feed-index.py"], ["feed-index.py"])
        check("⑤ протухшее оправдание: установленное объявлено отсутствующим — красное",
              1, ["перечень законных отсутствий ПРОТУХ", "feed-index.py"], [],
              pack, install, container, tool)

        # ⑥ сверять нечем: каталога пакета нет — слова, и НЕ «отставания нет»
        pack, install, container = stand(root / "c6", ["a.py"], ["a.py"])
        check("⑥ каталога пакета нет — слова «СВЕРИТЬ НЕЧЕМ», не «чисто»",
              0, ["СВЕРИТЬ НЕЧЕМ"], ["отставания установки нет"],
              root / "c6" / "нет-такого-каталога", install, container, tool)

        # ⑦ ВСТРЕЧНЫЙ на границе разрядов: имя пакета, которого нет ни в установке, ни
        #    в первом наборе, и которого НЕТ в перечне — обязано попасть в красное,
        #    даже когда рядом есть законные. Иначе перечень гасил бы соседей.
        pack, install, container = stand(root / "c7",
                                         ["feed-index.py", "лишний.py"], [])
        check("⑦ законное рядом с отставшим не гасит отставшего",
              1, ["ОТСТАВАНИЕ УСТАНОВКИ: 1", "лишний.py", "законных отсутствий 1"], [],
              pack, install, container, tool)

        # ⑧ граница суждения (карточка #771): на ОБОИХ исходах печатается строка, что сличены
        #    ИМЕНА, а тела сличает другая проверка — с её именем и названием раздела её вывода.
        #    Проверка тел здесь НЕ заводится: второй судья одному предмету расходится молча.
        boundary = ["ГРАНИЦА СУЖДЕНИЯ", "ИМЕНА файлов", "guard-scripts-drift.py",
                    "vnext-tools ↔ образец"]
        pack, install, container = stand(root / "c8a", ["a.py", "b.py"], ["a.py"])
        check("⑧ граница суждения напечатана, когда отставшие ЕСТЬ",
              None, boundary, [], pack, install, container, tool)
        pack, install, container = stand(root / "c8b", ["a.py"], ["a.py"])
        check("⑧ граница суждения напечатана, когда отставших НЕТ",
              None, boundary, [], pack, install, container, tool)
        # ⚖️ код и слова самого исхода здесь НЕ судятся: их судят ① и ②. Иначе поломка отбора
        #    отставших роняла бы и ⑧, и случаи переставали быть независимыми.

        # ⑨ ВСТРЕЧНЫЙ к ⑧: когда сличать было нечем, строка «сличены ИМЕНА» была бы ложью —
        #    имена не сличались вовсе. Без него ⑧ прошёл бы и на проверке, которая печатает
        #    границу всегда, даже поверх «СВЕРИТЬ НЕЧЕМ».
        pack, install, container = stand(root / "c9", ["a.py"], ["a.py"])
        check("⑨ встречный: сверять нечем — границы «сличены имена» НЕТ",
              0, ["СВЕРИТЬ НЕЧЕМ"], ["ГРАНИЦА СУЖДЕНИЯ"],
              root / "c9" / "нет-такого-каталога", install, container, tool)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def selftest():
    """ДВЕ нарочные поломки В КОПИИ проверки, каждая валит СВОИ случаи и только их.

    ⚖️ Почему две, а не одна: одна поломка доказывает, что приёмка умеет краснеть, но не
    доказывает, что случаи НЕЗАВИСИМЫ. Первая гасит отбор отставших, вторая — проверку
    перечня; если бы один случай краснел от любой поломки, он судил бы не своё свойство.
    🩸 И первое ожидание здесь было МОИМ промахом: я ждала, что гашение отбора отставших
    уронит и случай ⑤ (протухшее оправдание). Он остался зелёным — и правильно, он смотрит
    перечень, а не отбор. Исправлено ОЖИДАНИЕ, не код: случай обязан судить своё.

    Копия, а не живой файл: приёмка, портящая свой предмет на месте, оставляет контур
    со сломанной проверкой, если прогон прервётся.
    """
    # Поломки адресные — ПО СТРОКЕ КОДА, а не по её значению: совпадение по значению
    # уже заводило правку в чужую запись (карточка #769).
    breaks = [
        ("гашение отбора отставших",
         "    lagging = sorted(n for n in missing if n not in absences)",
         "    lagging = []  # НАРОЧНАЯ ПОЛОМКА: гасим всё",
         ["①", "⑦"]),
        ("гашение проверки протухшего перечня",
         "    stale = sorted(n for n in absences if n in installed or n in first)",
         "    stale = []  # НАРОЧНАЯ ПОЛОМКА: протухшее оправдание не ищем",
         ["⑤"]),
        # карточка #771: убрать строку границы из вывода — краснеет РОВНО ⑧ (оба исхода);
        # ⑨ встречный остаётся зелёным, остальные случаи про границу не говорят
        ("снятие строки границы суждения",
         "print(BODY_BOUNDARY_LINE)",
         "pass  # НАРОЧНАЯ ПОЛОМКА: границу суждения не печатаем",
         ["⑧"]),
        # встречный к предыдущей: границу печатают ВСЕГДА, и поверх «СВЕРИТЬ НЕЧЕМ» — краснеет РОВНО ⑨;
        # ⑧ остаётся зелёным (на его исходах граница и так обязана стоять)
        ("граница суждения напечатана и там, где сверять было нечем",
         '        print(f"⚠️ СВЕРИТЬ НЕЧЕМ: {note}")',
         '        print(f"⚠️ СВЕРИТЬ НЕЧЕМ: {note}"); print(BODY_BOUNDARY_LINE)  # НАРОЧНАЯ ПОЛОМКА',
         ["⑨"]),
    ]
    all_ok = True
    for title, needle, replacement, expected in breaks:
        root = Path(tempfile.mkdtemp(prefix="bite-install-lag-break-"))
        try:
            broken = root / "guard-install-lag.py"
            text = TOOL.read_text(encoding="utf-8")
            if needle not in text:
                print(f"⛔ поломку «{title}» сделать нечем: строка не найдена — проверка "
                      f"переписана, и эта приёмка судит не то, что думает")
                return 2
            broken.write_text(text.replace(needle, replacement), encoding="utf-8")
            for helper in ("mezo_paths.py",):
                src = TOOL.parent / helper
                if src.is_file():
                    shutil.copy2(src, root / helper)

            print(f"── поломка «{title}»: красными обязаны стать {expected} ──")
            before_failed = len(FAILED)
            run_cases(tool=broken)
            broke = [name for name, _, _ in FAILED[before_failed:]]
            got_marks = sorted({name[0] for name in broke})
            if sorted(expected) == got_marks:
                print(f"   ✅ валит РОВНО свои: {' · '.join(broke)}")
            else:
                all_ok = False
                print(f"   ⛔ ждали красными {expected}, получили {got_marks}")
            print("")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("✅ все четыре поломки валят ровно свои случаи — случаи независимы"
          if all_ok else "⛔ САМОПРОВЕРКА ПРОВАЛИЛАСЬ")
    return 0 if all_ok else 1


def main():
    parser = argparse.ArgumentParser(description="приёмка проверки отставания установки")
    parser.add_argument("--selftest", action="store_true",
                        help="сломать копию проверки и показать, что случаи краснеют")
    args = parser.parse_args()

    if not TOOL.is_file():
        print(f"⛔ предмета приёмки нет рядом: {TOOL}")
        return 2

    if args.selftest:
        return selftest()

    run_cases()
    print("")
    print(f"ИТОГ: прошло {len(PASSED)} · провалилось {len(FAILED)}")
    if FAILED:
        for name, problems, out in FAILED:
            print("")
            print(f"── {name} ──")
            for p in problems:
                print(f"   {p}")
            print(out)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
