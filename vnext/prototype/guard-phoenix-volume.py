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
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

LIMIT = 20_000          # знаков на раздел; порог назван ЧИСЛОМ и здесь, и в приёмке

# ── ПОРОГ РОЛИ — ИЗ ПРАВИЛА, А НЕ ЧИСЛОМ В КОДЕ (карточка 786) ───────────────────────────
# 🩸 ЗАМЕР @STUD (записка #6481): 199 792 знака на роль при цели правила около 28 000 и ноле
# раздутых разделов — проверка молчала полностью: она судит РАЗДЕЛ, а окно чтения платится за
# РОЛЬ (семь разделов подряд). Раздел 16 000 × шесть = 96 000, и признака нет ни одного.
# ⚖️ Число роли живёт в теле правила memory-hot-and-archive («роль около 28 000»), его хозяин —
# свод, а не этот файл: вписанное сюда число протухло бы молча при смене правила.
# Достаём ЗАПРОСОМ к таблице правил названным образцом ниже. Образец ловит только слова
# «роль около <число>»: «раздел около 4 000» его не касается, а «роль — около семи разделов»
# числа не несёт — это третий исход, а не молчаливое число по умолчанию.
ROLE_RULE_KEY = "memory-hot-and-archive"
ROLE_LIMIT_RE = re.compile(
    r"роль\s*[—–-]?\s*около\s+(\d{1,3}(?:[\s  ]\d{3})+|\d+)(?!\d)")


def role_limit(con):
    """(порог роли в знаках | None, причина). Причина непуста, только когда порога нет.

    Три исхода, и все три видны читающему: число найдено · правила нет (или оно не действует,
    или таблицы правил нет) · правило есть, но числа роли в нём нет. Беда чтения — тоже «не найден»."""
    try:
        row = con.execute("SELECT body FROM rules WHERE rule_key = ? AND status = 'active'",
                          (ROLE_RULE_KEY,)).fetchone()
    except sqlite3.Error as e:
        return None, f"таблица правил не читается ({e})"
    if not row or not row[0]:
        return None, f"действующего правила {ROLE_RULE_KEY} в базе нет"
    m = ROLE_LIMIT_RE.search(row[0])
    if not m:
        return None, f"в теле правила {ROLE_RULE_KEY} нет числа после слов «роль около»"
    return int(re.sub(r"\D", "", m.group(1))), ""


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
        rlimit, rwhy = role_limit(con)
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
    # СУММА ПО РОЛИ (карточка 786): окно чтения платится за роль целиком. Строка ℹ️, а не 🔴:
    # правило называет число ЦЕЛЬЮ («по этому числу никого не красят»), и общий прогон
    # (guard-all) от неё не краснеет — класс исхода тот же, что у раздутого раздела, не строже.
    sums: dict = {}
    for r, _s, n in rows:
        cnt, tot, big = sums.get(r, (0, 0, 0))
        sums[r] = (cnt + 1, tot + n, big + (1 if n > a.limit else 0))
    if rlimit is None:
        print(f"ℹ️ порог роли в правиле не найден — сумма по роли НЕ судится ({rwhy})")
    else:
        over = sorted(((t, r, c, b) for r, (c, t, b) in sums.items() if t > rlimit), reverse=True)
        print(f"ℹ️ порог роли из правила {ROLE_RULE_KEY}: {rlimit} знаков на все разделы роли · "
              f"ролей выше него: {len(over)} из {len(sums)}")
        for t, r, c, b in over:
            print(f"ℹ️ [{r}] сумма по роли {t} знаков при пороге роли {rlimit} "
                  f"(в {t / rlimit:.1f} раза выше) · разделов {c}, раздутых {b} — окно чтения "
                  f"платится за роль целиком; это цель правила, а не запрет")
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
