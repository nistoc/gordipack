# -*- coding: utf-8 -*-
"""
bite-r15a.py — воспроизводимый УКУС для R15a: инструмент координации × сменившийся рабочий каталог.

ПОЧЕМУ УКУС ОФОРМЛЕН СКРИПТОМ, А НЕ КОМАНДАМИ В ОБОЛОЧКЕ (оплачено 2026-07-26 06:27 UTC):
первая попытка ставилась командами PowerShell — смена каталога УПАЛА (короткое имя пути),
а остальные шаги выполнились как ни в чём не бывало и «показали» успех там, где ожидался отказ.
Мусорная нота ушла в боевую ленту (#2691, надгробие — #2693).
⇒ Инвариант, встроенный здесь: **укус обязан ПАДАТЬ, когда не выполнено его предусловие,
   а не молча мерить не то.** Проверка предусловия — первое, что делает этот скрипт.

    python bite-r15a.py --sandbox <корень песочницы> [--foreign-cwd <каталог>]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

CONTAINER = Path(r"C:\guts\.atlas")


def run(cmd, cwd):
    p = subprocess.run([sys.executable, *cmd], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "").strip().splitlines()
    err = (p.stderr or "").strip().splitlines()
    first = (out or err or ["(пусто)"])[0]
    return p.returncode, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", default=str(Path.home() / ".mezosync-sandbox"))
    ap.add_argument("--foreign-cwd", default=str(CONTAINER / "atlas.core"),
                    help="каталог, куда «прыгнул» CWD рабочей командой роли")
    a = ap.parse_args()

    sb = Path(a.sandbox).resolve()
    scripts = sb / "scripts"
    foreign = Path(a.foreign_cwd).resolve()

    # ── ПРЕДУСЛОВИЯ: любое непройденное — стоп с кодом 2 («укус не поставлен»), не «зелено»
    problems = []
    if not (sb / "mezosync.db").exists():
        problems.append(f"нет песочницы: {sb / 'mezosync.db'} (подними bootstrap.py)")
    if not (scripts / "write-message.py").exists():
        problems.append(f"нет копий скриптов в {scripts}")
    if not (scripts / "write-message-vnext.py").exists():
        problems.append("нет прототипа write-message-vnext.py рядом с песочницей")
    if not foreign.is_dir():
        problems.append(f"чужой каталог не существует: {foreign}")
    if foreign == CONTAINER:
        problems.append("чужой каталог совпал с корнем контейнера — укус выродится в успех")
    if problems:
        print("⛔ УКУС НЕ ПОСТАВЛЕН — предусловия не выполнены:")
        for p in problems:
            print(f"   · {p}")
        sys.exit(2)

    print(f"[укус R15a] рабочий каталог эксперимента: {foreign}")
    print(f"            (роль «прыгнула» сюда своей работой; скрипты и БД — в {sb})\n")

    print("── ДО: живой скрипт, относительный путь К СКРИПТУ (боль CORE #2669 / ING #2673 / COORD #2683)")
    rc, line = run([".mezosync/scripts/write-message.py", "--db", str(sb / "mezosync.db"),
                    "--role", "PROTO", "--body", "укус"], cwd=foreign)
    print(f"   rc={rc}  {line}")
    print("   ⇒ интерпретатор ищет ФАЙЛ СКРИПТА от CWD — падает до того, как код начнёт работать.")
    print("     Изнутри скрипта это не чинится НИКАК; лечит только источник формы (R15b, гард).\n")

    print("── ДО: абсолютный скрипт, но относительный --db")
    rc, line = run([str(scripts / "write-message.py"), "--db", ".mezosync/mezosync.db",
                    "--role", "PROTO", "--body", "укус"], cwd=foreign)
    print(f"   rc={rc}  {line}")
    print("   ⇒ путь резолвится ОТ CWD. Здесь он не нашёлся — но если бы случайно совпал,")
    print("     нота ушла бы в ЧУЖУЮ живую БД молча и с честным «OK» (F20, оплачено #2691).\n")

    print("── ПОСЛЕ: прототип R15a, --db вообще не передан")
    rc, line = run([str(scripts / "write-message-vnext.py"),
                    "--role", "proto", "--body", "[укус R15a] запись из чужого каталога без --db"],
                   cwd=foreign)
    print(f"   rc={rc}  {line}")

    print("\n── ПОСЛЕ: относительный --db резолвится ОТ КОРНЯ МЕЗОСИНКА, не от CWD")
    rc, line = run([str(scripts / "write-message-vnext.py"), "--db", "mezosync.db",
                    "--role", "PROTO", "--body", "[укус R15a] относительный --db от корня"],
                   cwd=foreign)
    print(f"   rc={rc}  {line}")

    print("\n── ПОСЛЕ: несуществующая БД — ГРОМКАЯ ошибка с названной причиной, не тихий фантом")
    rc, line = run([str(scripts / "write-message-vnext.py"), "--db", "нет-такой.db",
                    "--role", "PROTO", "--body", "x"], cwd=foreign)
    print(f"   rc={rc}  {line}")


if __name__ == "__main__":
    main()
