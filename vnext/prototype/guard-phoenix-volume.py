# -*- coding: utf-8 -*-
# SURFACES: phoenix
"""guard-phoenix-volume.py — раздутый раздел памяти роли (заход 4 ⑨).

ЗАМЕР-ОСНОВАНИЕ (27.08): раздел «состояние» держал 340 КБ на девять ролей — свежее
тонет в старом, и роль, читающая свою память при пробуждении, тратит окно контекста
на прошлогодний жир. ПОРОГ — 20 000 знаков НА РАЗДЕЛ: больше — красное ПОИМЁННО.

⚖️ Сжатие НЕ теряет: save-phoenix при --allow-shrink кладёт прежнее тело
в phoenix_history (это его механизм, доказан его приёмкой) — сторож при красном
подсказывает ровно этот путь, а не «сотри».
⚖️ ЧУЖУЮ ПАМЯТЬ НЕ ЖМУ: сторож называет долг, рука — своя у каждой роли.
Свежая роль без разделов долга не получает: пустота — не раздутость.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

LIMIT = 20_000          # знаков на раздел; порог назван ЧИСЛОМ и здесь, и в приёмке


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--limit", type=int, default=LIMIT)
    a = ap.parse_args()
    db = Path(a.db) if a.db else mezo_paths.live_db()
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        rows = con.execute("SELECT role, section, LENGTH(body) AS n FROM phoenix "
                           "ORDER BY n DESC").fetchall()
        con.close()
    except sqlite3.Error as e:
        print(f"⛔ память не прочитана ({e}) — НЕ ПРОВЕРЕНО, это не «чисто»")
        return 2
    if not rows:
        print("⛔ в памяти НОЛЬ разделов — мерить нечего (это не «чисто»)")
        return 2
    fat = [(r, s, n) for r, s, n in rows if n > a.limit]
    total = sum(n for _r, _s, n in rows)
    print(f"разделов памяти: {len(rows)} · всего {total // 1024} КБ · "
          f"порог {a.limit} знаков на раздел · раздутых: {len(fat)}")
    for r, s, n in fat:
        print(f"🔴 [{r} · {s}] {n} знаков — свежее тонет; сожми СВОЕЙ рукой: "
              f"save-phoenix --allow-shrink (старое тело останется в phoenix_history)")
    if not fat:
        print("✅ раздутых разделов нет")
    else:
        # 🩸 04.09 (замер @ING записка #4720, подтверждён @RCC записка #4733 на четвёртой памяти):
        # «🔴 + код 1 + совет "сожми"» читается как ОТКАЗ ЗАПИСИ — роль четверо суток резала
        # слова, чтобы «влезть», хотя запись проходила всегда. Проверка выглядела запретом.
        # Ниже сказано прямо, что она есть и чего она НЕ делает.
        print("ℹ️ Это ПРОВЕРКА, а не запрет: сохранение в раздел ПРОХОДИТ при любом объёме "
              "(отказывает только УСУШКА — заметная потеря объёма без --allow-shrink; порог — в save-phoenix.py, не здесь). Код 1 красит общий прогон "
              "и называет долг — он не останавливает и не откатывает запись.")
    return 1 if fat else 0


if __name__ == "__main__":
    sys.exit(main())
