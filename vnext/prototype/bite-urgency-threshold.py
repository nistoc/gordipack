#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА замера порога срочности (measure-urgency-threshold.py).

Программа считает число, которое ляжет в решение владельца о том, как устроена срочность
у всех девяти ролей. Значит она обязана быть проверена на данных, где правильный ответ
известен ЗАРАНЕЕ — иначе это гипотеза с уверенным лицом.

🪤 ПЕРВАЯ РЕДАКЦИЯ ЭТОЙ ПРИЁМКИ БЫЛА ЗЕЛЁНОЙ ПО ЛОЖНОЙ ПРИЧИНЕ.
Номера записок в песочнице были однозначными (#1, #2), а замер ищет ссылки от трёх цифр.
Различающие случаи «промолчали» не потому, что замер верно их отбросил, а потому, что он
не увидел НИЧЕГО. ⇒ В каждом различающем случае теперь лежит КОНТРОЛЬНАЯ пара — заведомо
законный отклик, который обязан быть найден. Если контроль не найден, случай не зачитывается,
даже когда «промолчал» ровно там, где надо.
> Молчание засчитывается за верный ответ ТОЛЬКО когда доказано, что программа не молчит вообще.

  ① ответы разложены по известным часам        → порог обязан совпасть с подложенным
  ② ответ РАНЬШЕ вопроса (испорченные метки)   → не считать откликом
  ③ ответ от ТОЙ ЖЕ роли (сам себе)            → не считать откликом
  ④ упоминание номера, которого нет в ленте    → не считать откликом

⛔ Живой базы не касается вовсе: своя временная база в песочнице.
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURE = os.path.join(HERE, "measure-urgency-threshold.py")
BASE = datetime(2026, 7, 1, 0, 0, 0)
# Номера как в живой ленте: замер ищет ссылки «#N» от трёх цифр, и на однозначных
# номерах он слеп. Песочница обязана быть похожей на настоящее в этом самом месте.
FIRST_ID = 1000


def stamp(hours: float) -> str:
    return (BASE + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def build(path: str, rows, links=()):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT,
                   timestamp TEXT, body_md TEXT, tags TEXT, priority TEXT,
                   resolved INTEGER, broadcast INTEGER, addressed_by TEXT)""")
    con.execute("""CREATE TABLE message_thread (message_id INTEGER, reply_to INTEGER,
                   thread_id INTEGER, kind TEXT, linked_by TEXT)""")
    for mid, role, hours, prio, body in rows:
        con.execute("INSERT INTO messages (id, writer_role, timestamp, priority, body_md)"
                    " VALUES (?,?,?,?,?)", (mid, role, stamp(hours), prio, body))
    for mid, reply_to in links:
        con.execute("INSERT INTO message_thread (message_id, reply_to) VALUES (?,?)",
                    (mid, reply_to))
    con.commit()
    con.close()


def run(path: str, cover: str = "95"):
    out = subprocess.run([sys.executable, MEASURE, "--db", path, "--cover", cover],
                         capture_output=True, text=True, encoding="utf-8")
    return out.stdout + out.stderr


def num(text: str, pattern: str):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


CASES = 0                # считается прогоном, а не пишется словом в подписи
DIFFERENTIATING = 0      # случай, где механизм ОБЯЗАН промолчать или ответить иначе


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def differentiating(tmp: str, name: str, bogus_rows, what: str) -> bool:
    """Случай с КОНТРОЛЬНОЙ парой: законный отклик обязан найтись, поддельный — нет."""
    rows = [
        # контроль: срочный вопрос и законный ответ через 2 ч от ДРУГОЙ роли
        (FIRST_ID, "COORD", 0.0, "high", "контрольный вопрос"),
        (FIRST_ID + 1, "STUD", 2.0, "normal", f"отвечаю на #{FIRST_ID}"),
        # хвост, чтобы «моложе 6 ч не судим» не съело выборку
        (FIRST_ID + 90, "TAXO", 500.0, "normal", "поздняя записка, ничей ответ"),
    ] + list(bogus_rows)
    path = os.path.join(tmp, f"{name}.db")
    build(path, rows)
    out = run(path)
    found = num(out, r"откликов найдено \.+ (\d+)")
    silent = num(out, r"без отклика, срочных \.+ (\d+)")
    control_ok = found == 1                 # найден ровно контрольный
    bogus_ignored = silent == 1             # поддельный вопрос остался без отклика
    return case(
        f"{name} {what}",
        bool(control_ok and bogus_ignored),
        f"контрольный отклик найден: {'да' if control_ok else 'НЕТ — случай не зачитывается'} · "
        f"поддельный отброшен: {'да' if bogus_ignored else 'НЕТ'} "
        f"(откликов {found}, срочных без отклика {silent})",
        differ=True)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-urgency-")
    ok = True
    global CASES, DIFFERENTIATING
    CASES = DIFFERENTIATING = 0

    # ── ① ПОДЛОЖЕННЫЙ ПОРОГ ────────────────────────────────────────────────
    # 20 срочных вопросов; ответы через 1 ч, кроме одного — через 40 ч.
    # При покрытии 95 % (19 из 20) порог обязан выйти 1 ч, а не 40.
    rows = []
    mid = FIRST_ID
    for i in range(20):
        q = mid; mid += 1
        rows.append((q, "COORD", i * 0.01, "high", f"вопрос {i}"))
        rows.append((mid, "PROTO", i * 0.01 + (40.0 if i == 0 else 1.0), "normal",
                     f"отвечаю на #{q}"))
        mid += 1
    rows.append((mid, "STUD", 500.0, "normal", "поздняя записка, ничей ответ"))
    build(os.path.join(tmp, "a.db"), rows)
    out = run(os.path.join(tmp, "a.db"))
    thr = num(out, r"ПОРОГ: ([\d.]+) ч")
    found = num(out, r"откликов найдено \.+ (\d+)")
    ok &= case("① порог совпадает с подложенным",
               thr is not None and abs(thr - 1.0) < 0.35 and found == 20,
               f"подложено 1 ч у 19 из 20 ответов, выброс 40 ч → замер сказал {thr} ч "
               f"(откликов найдено {found} из 20)")

    # ── ②③④ РАЗЛИЧАЮЩИЕ, каждый с контрольной парой ────────────────────────
    ok &= differentiating(
        tmp, "②", [(FIRST_ID + 10, "COORD", 10.0, "high", "вопрос из будущего"),
                   (FIRST_ID + 11, "PROTO", 2.0, "normal", f"ссылаюсь на #{FIRST_ID + 10}")],
        "ответ РАНЬШЕ вопроса откликом не считается")

    ok &= differentiating(
        tmp, "③", [(FIRST_ID + 20, "CORE", 0.0, "high", "вопрос"),
                   (FIRST_ID + 21, "CORE", 3.0, "normal", f"дополняю свою же #{FIRST_ID + 20}")],
        "ссылка на СВОЮ ЖЕ записку откликом не считается")

    ok &= differentiating(
        tmp, "④", [(FIRST_ID + 30, "CORE", 0.0, "high", "вопрос"),
                   (FIRST_ID + 31, "PROTO", 3.0, "normal", "смотри #9999 — такой записки нет")],
        "ссылка на несуществующий номер откликом не считается")

    # ── ⑤ ТРИ ПОЛОСЫ: цитата не есть разговор ──────────────────────────────
    # Три срочных вопроса от CORE, и три разных отклика на них от PROTO:
    #   жест (связь) · обращение (@CORE + ссылка вне цитаты) · цитата внутри «кавычек»
    # Узкая обязана взять 1, средняя 2, широкая 3. Если полосы совпали — различения нет.
    q1, q2, q3 = FIRST_ID + 40, FIRST_ID + 41, FIRST_ID + 42
    rows = [(q1, "CORE", 0.0, "high", "вопрос один"),
            (q2, "CORE", 0.0, "high", "вопрос два"),
            (q3, "CORE", 0.0, "high", "вопрос три"),
            (FIRST_ID + 43, "PROTO", 1.0, "normal", "отвечаю связью, без номера в теле"),
            (FIRST_ID + 44, "PROTO", 1.0, "normal", f"@CORE — отвечаю на #{q2} по существу"),
            (FIRST_ID + 45, "STUD", 1.0, "normal", f"кстати, «как сказано в #{q3}» — это цитата"),
            (FIRST_ID + 95, "TAXO", 500.0, "normal", "поздняя записка, ничей ответ")]
    path = os.path.join(tmp, "e.db")
    build(path, rows, links=[(FIRST_ID + 43, q1)])
    out = run(path)
    narrow = num(out, r"узкая  \(только проставленная связь\) \.+ +(\d+)")
    middle = num(out, r"и автор вопроса назван в ответе\) \. +(\d+)")
    wide = num(out, r"широкая \(любое «#N», включая цитаты\) \.+ +(\d+)")
    ok &= case("⑤ три полосы РАЗЛИЧАЮТСЯ: цитата не засчитана разговором",
               (narrow, middle, wide) == (1, 2, 3),
               f"подложено по одному отклику каждой силы → узкая {narrow}, средняя {middle}, "
               f"широкая {wide}; ждали 1 · 2 · 3 "
               f"{'' if (narrow, middle, wide) == (1, 2, 3) else '— полосы не различают'}",
               differ=True)

    # 🪤 Число случаев считаем, а не пишем словом: подпись «четыре случая» пережила
    # добавление пятого и соврала в зелёном выводе. Свой же признак ложных надписей.
    print()
    print(f"✅ ЗАМЕР ПРИНЯТ — случаев {CASES}, из них различающих {DIFFERENTIATING}, "
          "у каждого различающего контрольная пара" if ok
          else "🔴 ЗАМЕР НЕ ПРИНЯТ — число из него нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
