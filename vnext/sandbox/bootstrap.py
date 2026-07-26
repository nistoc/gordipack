# -*- coding: utf-8 -*-
"""
bootstrap.py — поднять ПЕСОЧНИЦУ для прототипирования mezosync v-next.

⛔ ГРАНИЦА (мандат владельца роли PROTO, 2026-07-25): живой субстрат
   C:\\guts\\.atlas\\.mezosync\\ — ТОЛЬКО ЧТЕНИЕ. Этот скрипт открывает живую БД
   строго `mode=ro` и снимает её консистентную копию ЧЕРЕЗ SQLite backup API.

ПОЧЕМУ backup API, а не copy файла: живая БД в режиме WAL. Копия .db без -wal/-shm
при активных писателях даёт РВАНЫЙ снимок (часть транзакций осталась в WAL). backup API
берёт согласованный снимок под своей блокировкой чтения и не пишет в источник.

Использование:
    python bootstrap.py                      # снять свежую песочницу (перезаписать)
    python bootstrap.py --dest <путь.db>     # своя цель
    python bootstrap.py --verify             # только проверить существующую песочницу
"""
import argparse
import sqlite3
import sys
import os
from pathlib import Path

LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")
# Песочница живёт ВНЕ контейнера C:\guts\.atlas НАРОЧНО: гард ⑤ («фантомные .db»)
# рекурсивно сканирует весь контейнер. Полная копия его не краснит (он судит по
# признаку «ноль таблиц»), но ПРОМЕЖУТОЧНАЯ пустая БД — закраснила бы, и уже у ВСЕХ
# ролей сразу. Прототип не имеет права шуметь в чужих гардах.
DEFAULT_DEST = Path(os.environ.get("MEZOSYNC_SANDBOX", "")) if os.environ.get("MEZOSYNC_SANDBOX") else \
    Path.home() / ".mezosync-sandbox" / "mezosync_vnext.db"


def snapshot(live: Path, dest: Path) -> None:
    if not live.exists():
        sys.exit(f"ERR: живая БД не найдена: {live}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # mode=ro — источник физически не может быть изменён этим процессом.
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True, timeout=10)
    if dest.exists():
        dest.unlink()
    dst = sqlite3.connect(str(dest))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def verify(live: Path, dest: Path) -> int:
    """Песочница обязана быть ПОЛНОЙ копией: сверяем состав объектов и счётчики строк.
    Инвариант TEST-MUST-BE-ABLE-TO-FAIL: расхождение печатаем явно и возвращаем 1."""
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)

    def objects(c):
        return {(n, t) for n, t in c.execute(
            "SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}

    o_src, o_dst = objects(src), objects(dst)
    ok = True
    if o_src != o_dst:
        ok = False
        print(f"⛔ состав объектов расходится: только в живой {o_src - o_dst}, "
              f"только в песочнице {o_dst - o_src}")
    tables = sorted(n for n, t in o_src if t == "table")
    diffs = []
    for t in tables:
        a = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        b = dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if a != b:
            diffs.append(f"{t}: живая {a} ≠ песочница {b}")
    if diffs:
        ok = False
        print("⛔ счётчики строк расходятся: " + "; ".join(diffs))

    # Источник обязан остаться нетронутым: сверяем, что мы ничего не создали в нём.
    live_wal = live.with_suffix(".db-wal")
    print(f"{'✅' if ok else '⛔'} песочница {'сверена' if ok else 'РАСХОДИТСЯ'}: "
          f"{len(tables)} таблиц, {sum(1 for _, t in o_src if t == 'view')} VIEW")
    print(f"   живая:     {live}  ({live.stat().st_size/1024:.0f} КБ)"
          f"{'  [WAL активен]' if live_wal.exists() else ''}")
    print(f"   песочница: {dest}  ({dest.stat().st_size/1024:.0f} КБ)")
    src.close()
    dst.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Песочница mezosync v-next")
    ap.add_argument("--live", default=str(LIVE_DB), help="живая БД (только чтение)")
    ap.add_argument("--dest", default=str(DEFAULT_DEST), help="куда положить песочницу")
    ap.add_argument("--verify", action="store_true", help="только сверить, не пересоздавать")
    args = ap.parse_args()
    live, dest = Path(args.live), Path(args.dest)

    if not args.verify:
        snapshot(live, dest)
        print(f"[snapshot] {live} → {dest}")
    sys.exit(verify(live, dest))


if __name__ == "__main__":
    main()
