#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: УКАЗАТЕЛЬ ленты называет свой охват и никогда не выдаёт обрезок за весь долг.

ПОВОД (карточка #194, заявка @opssre 2026-08-11 19:33 UTC, подтверждена прогоном @PROTO).
`--index` печатал «УКАЗАТЕЛЬ для CHROME: 50 записок» при долге 418 и обрывался на #3157,
ни словом не сказав про остальные 368.

🎯 ЧЕМ ЭТОТ ДЕФЕКТ ОСОБЕННО ДОРОГ, И ПОЧЕМУ ПРИЁМКА ИМЕННО ЗДЕСЬ.
Указатель заведён РАДИ большого долга: телами его не прочесть по арифметике (карточка #193,
замер 11.08 — заголовки в 30–46 раз дешевле тел). То есть молча обрезался ровно тот
инструмент, к которому идут, когда все прочие уже неприменимы, — и обрезался тем сильнее,
чем крупнее долг. Обычная читалка про свой предел ЧЕСТНА («упёрлось в лимит, за ним ещё N»);
неправда жила не в замысле, а в ПОРЯДКЕ КОДА: счёт остатка стои́т ниже, а ветка `--index`
возвращается раньше него. Второй инструмент об одном предмете сказал другое — так @opssre
дефект и нашёл.

⚖️ ПОЭТОМУ ПРОВЕРЯЕТСЯ СВОЙСТВО, А НЕ ОДНО ЧИСЛО: сколько бы сужений ни было (предел, тег,
витрина), напечатанный охват обязан считаться ТЕМ ЖЕ предикатом, что и выборка, и обрез
обязан НАЗЫВАТЬСЯ. Случай ⑤ стережёт именно предикат: он ловит подмену охвата «всем долгом».

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths    # пути машины ВЫВОДЯТСЯ, не впечатаны (#153 · #157 · #168)
import mezo_target   # какую копию испытываем: живую или шаблон (#146 · #148)

READER = mezo_target.script("read-messages.py")
LIVE_DB = mezo_paths.live_db()
ROLE = "ЗОНДОХВАТА"
DEBT = 60          # заведомо больше умолчания тел (50) — иначе обрез не воспроизводится
TAGGED = 7         # из них помеченных: подмножество для случая ⑤

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(READER), "--role", ROLE, "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def shown(out: str) -> int:
    """Сколько заголовков НАПЕЧАТАНО. Считаем строки списка, а не шапку: шапка — это
    ровно то, что проверяется, и верить ей при подсчёте значило бы спросить обвиняемого."""
    return sum(1 for ln in out.splitlines() if re.match(r"^  #\d+ ", ln))


def header(out: str) -> str:
    return next((ln for ln in out.splitlines() if ln.startswith("📇")), "")


def seed(db: Path) -> None:
    con = sqlite3.connect(db)
    head = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    for i in range(1, DEBT + 1):
        tags = '["ЗОНДТЕГ"]' if i <= TAGGED else "[]"
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority,"
                    " resolved, broadcast, addressed_by) VALUES (?,?,datetime('now'),?,?,?,0,1,?)",
                    (head + i, ROLE, f"проба охвата указателя {i}", tags, "normal", "field"))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?,?,datetime('now'))", (ROLE, head))
    con.commit()
    con.close()


def cursor_of(db: Path) -> int:
    con = sqlite3.connect(db)
    v = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?", (ROLE,)).fetchone()[0]
    con.close()
    return v


def main() -> int:
    for p in (READER, LIVE_DB):
        if not p.exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет по пути {p}")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        seed(db)
        before = cursor_of(db)

        # ① УМОЛЧАНИЕ УКАЗАТЕЛЯ — ВЕСЬ ДОЛГ. Заголовки дёшевы, и предел, унаследованный
        #    от режима тел, здесь был не бережливостью, а обрезкой правды.
        code, out = run(db, "--index")
        case(f"① без --limit указатель показывает ВЕСЬ долг ({DEBT})",
             shown(out) == DEBT and f"{DEBT} записок из {DEBT}" in header(out),
             f"напечатано строк: {shown(out)} · шапка: {header(out)[:80]}")

        # ② ФОРМА ИЗ ЗАЯВКИ: явный предел меньше долга. Уважается — но НАЗЫВАЕТСЯ.
        code, out = run(db, "--index", "--limit", "20")
        head20 = header(out)
        case("② явный --limit уважается, и обрез НАЗВАН вслух",
             shown(out) == 20 and f"20 записок из {DEBT}" in head20
             and "ПОКАЗАНЫ НЕ ВСЕ" in out and f"ещё {DEBT - 20} записок" in out,
             f"шапка: {head20[:80]}")

        # ③ КОНТРОЛЬНАЯ ПАРА: когда обреза НЕТ, крика быть не должно. Без этого случая
        #    приёмку прошёл бы инструмент, который предупреждает ВСЕГДА, — а предупреждение,
        #    звучащее всегда, перестают читать, и оно защищает только автора.
        code, out = run(db, "--index", "--limit", str(DEBT + 5))
        case("③ предел ШИРЕ долга — про обрез не сказано ни слова",
             shown(out) == DEBT and "ПОКАЗАНЫ НЕ ВСЕ" not in out)

        # ④ ЛОЖНЫЙ НОЛЬ СРОЧНОСТИ: при обрезе строка «срочных N» относится к ОКНУ.
        #    Не назвав окно, механизм отдал бы уверенный ответ про долг, которого не смотрел.
        code, out = run(db, "--index", "--limit", "20")
        urg = next((ln for ln in out.splitlines() if "срочных СЕЙЧАС" in ln), "")
        case("④ при обрезе счёт срочных объявляет, что он ПО ПОКАЗАННЫМ",
             "ПОКАЗАННЫХ" in urg and str(DEBT - 20) in urg,
             f"строка: {urg.strip()[:90]}")

        # ⑤ ОХВАТ СЧИТАЕТСЯ ТЕМ ЖЕ ПРЕДИКАТОМ, ЧТО И ВЫБОРКА — различающий случай.
        #    Подмена «долгом» выглядела бы правдоподобно и была бы неверна: с тегом
        #    в отборе 7 записок, а долг 60. Тот же урок, что в счёте остатка батча (#2264).
        code, out = run(db, "--index", "--tag", "ЗОНДТЕГ")
        case("⑤ с --tag охват — про ОТОБРАННОЕ, а не про весь долг",
             shown(out) == TAGGED and f"{TAGGED} записок из {TAGGED}" in header(out)
             and f"из {DEBT}" not in header(out),
             f"шапка: {header(out)[:80]}")

        # ⑥ РЕГРЕСС КОНТРАКТА: указатель курсор НЕ двигает и токена НЕ выдаёт.
        #    Правка охвата не смеет этого изменить — иначе «посмотрел заголовки» станет
        #    неотличимо от «прочитал ленту», а это и есть враньё бухгалтерии.
        case("⑥ указатель не сдвинул отметку прочитанного и не выдал ключа",
             cursor_of(db) == before and "[end-of-batch]" not in out,
             f"отметка прочитанного {before} → {cursor_of(db)}")

    # ⑦ ЖИВАЯ БАЗА ЦЕЛА: зонд остался в копии.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute("SELECT COUNT(*) FROM messages WHERE writer_role=?", (ROLE,)).fetchone()[0]
    con.close()
    case("⑦ живая база не тронута", leaked == 0, f"записей зонда в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 4 (①②④⑤)")
    print("⚖️ ГРАНИЦА: проверено, что охват НАЗВАН и посчитан тем же предикатом. Что заголовок")
    print("   ПОЛЕЗЕН — не проверяется вовсе: обрезка первой строки до 96 знаков может сделать")
    print("   его бессмысленным, и приёмка этого не заметит. Это мерят чтением, не прогоном.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
