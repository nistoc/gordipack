#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gordi — ОДИН ОБЩИЙ ЗАПУСК инструментов контура (карточка #205).

    python <КОНТУР>/.mezosync/scripts/gordi.py                      # что вообще есть
    python <КОНТУР>/.mezosync/scripts/gordi.py backlog list --role PROTO
    python <КОНТУР>/.mezosync/scripts/gordi.py --доктор             # что мешает работе

ВОПРОС ВЛАДЕЛЬЦА 2026-08-16 09:59 UTC: не заменить ли отдельные скрипты службами. Замер
того же дня: инструментов 44 · строк 9284 · свой разбор аргументов у 33 · свой флаг базы
у 30 · общие модули зовут 24. Ответ по замеру: отдельные файлы ОСТАЮТСЯ (правятся по
одному, падение одного не роняет остальные, отказ воспроизводится одной командой), а эта
общий запуск даёт то единственное, чего у 44 отдельных вызовов быть не может —
ОДНО МЕСТО ДЛЯ ОБЩИХ ПРОВЕРОК.

⚖️ ЧЕМ ЭТОТ ОБЩИЙ ЗАПУСК НЕ ЯВЛЯЕТСЯ — сказано первым, чтобы не выяснилось потом:
  ⛔ он НЕ единственный. Прямой вызов инструмента законен НАВСЕГДА и остаётся нормой;
     если он сломается, контур работает — это условие его существования, а не оговорка.
  ⛔ он НЕ переписывает инструменты и ничего в них не знает: запускает тот же файл тем же
     интерпретатором и отдаёт его код возврата как свой.
  ⛔ он НЕ служба: ничего не поднимается и не слушает порт. Постоянно работающая служба
     ради девяти ролей, работающих в разное время, — единая точка отказа за удобство.

ЧТО ОН ДАЁТ:
  · СПИСОК ИНСТРУМЕНТОВ ЗАМЕРОМ КАТАЛОГА, а не впечатанный: новый инструмент виден в тот
    же миг. Впечатанный список молча отстаёт — этот класс контур оплатил трижды.
  · ПОДСКАЗКУ ПРИ ОПЕЧАТКЕ: «backlgo» → «ты имел в виду backlog?».
  · ОДНО МЕСТО ДЛЯ ОБЩИХ ПРОВЕРОК (объявление о правке #204 — уже там, через слой путей).
  · `--доктор`: что сейчас мешает работать — действующие объявления о правке инструментов
    и не пройденные проверки, одной командой.
"""
from __future__ import annotations

import difflib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELF = Path(__file__).name

# Что не является подкомандой: общие модули (их импортируют, а не зовут) и сам вход.
# 🪤 lease.py СЮДА НЕ ВХОДИТ, хотя импортируется: он И модуль, И команда. Первая редакция
# спрятала его как «библиотеку» — и список перестал показывать ровно тот инструмент,
# которым спрашивают «освободилось ли». Поймала проба на трёх инструментах.
# ⇒ Признак библиотеки — «не имеет своего запуска», а не «кто-то её импортирует».
LIBS = {"mezo_paths.py", "dryrun.py", "rule_status.py", "backlog_view.py", "machine_layer.py",
        "urgency.py", "schema_journal.py", "mezo_target.py", SELF}


def tools() -> dict[str, Path]:
    """Инструменты ЗАМЕРОМ каталога. Имя подкоманды = имя файла без .py."""
    out = {}
    for p in sorted(HERE.glob("*.py")):
        if p.name in LIBS or p.name.startswith("_"):
            continue
        out[p.stem] = p
    return out


def listing() -> int:
    t = tools()
    groups: dict[str, list[str]] = {}
    for name in t:
        head = ("проверки" if name.startswith(("guard-", "check-", "bite-"))
                else "лента и память" if name.startswith(("read-", "save-", "write-", "broadcast"))
                else "задачи и правила" if name.startswith(("backlog", "set-", "role-"))
                else "прочее")
        groups.setdefault(head, []).append(name)
    print(f"🚪 gordi — общий запуск инструментов контура. Найдено ЗАМЕРОМ каталога: {len(t)}")
    print(f"   каталог: {HERE.as_posix()}")
    for head in ("лента и память", "задачи и правила", "проверки", "прочее"):
        if head in groups:
            print(f"\n  {head}:")
            for name in groups[head]:
                print(f"    {name}")
    print("\n  Зови так:  gordi.py <имя> <аргументы инструмента>")
    print("  ⚖️ Прямой вызов инструмента законен навсегда: это удобство, "
          "а не единственный способ.")
    print("  Что мешает работать прямо сейчас:  gordi.py --доктор")
    return 0


def doctor() -> int:
    """Одной командой: что сейчас мешает работе. Объявления о правке + проверки."""
    print("🩺 ЧТО СЕЙЧАС МЕШАЕТ РАБОТЕ\n")
    rc_lease = subprocess.run([sys.executable, str(HERE / "lease.py"), "status"]).returncode
    print()
    g = HERE / "guard-all.py"
    if g.exists():
        r = subprocess.run([sys.executable, str(g)], capture_output=True, text=True,
                           encoding="utf-8")
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-1:]
        red = [l for l in (r.stdout or "").splitlines() if l.startswith("⛔")]
        print("🛡 ПРОВЕРКИ: " + (tail[0] if tail else "нет вывода"))
        for l in red[:5]:
            print("   " + l)
    else:
        print("🛡 ПРОВЕРКИ: guard-all.py не найден — проверить нечем, и это НЕ «всё хорошо»")
    return 0 if rc_lease == 0 else rc_lease


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help", "список"):
        return listing()
    if argv[0] in ("--доктор", "--doctor", "доктор"):
        return doctor()

    name, rest = argv[0], argv[1:]
    t = tools()
    if name not in t:
        near = difflib.get_close_matches(name, t, n=3, cutoff=0.6)
        print(f"⛔ инструмента «{name}» нет среди {len(t)} найденных в каталоге.", file=sys.stderr)
        if near:
            print(f"   Ты имел в виду: {' · '.join(near)} ?", file=sys.stderr)
        print(f"   Полный список: python {Path(__file__).as_posix()}", file=sys.stderr)
        return 2

    # Роль в окружении — чтобы проверка объявлений отличала своего от чужого.
    env = dict(os.environ)
    # Запускаем ТОТ ЖЕ файл: общий запуск ничего не знает об инструменте и не толкует
    # его аргументы.
    r = subprocess.run([sys.executable, str(t[name]), *rest], env=env)
    return r.returncode      # код инструмента отдаётся как есть: он не «улучшается» по пути


if __name__ == "__main__":
    sys.exit(main())
