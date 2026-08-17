#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: решето отличает УРОК, ЦИТАТУ и ПРОВЕНАНС от живого протухающего утверждения.

ПОВОД (карточка #185 + таблица вердиктов 2026-08-13). Поимённый разбор всех 49 кандидатов
по девяти ролям: 44 оказались уроками, надгробиями, цитатами в «ёлочках» и записями
о сделанном (хэш коммита неизменяем). Роль получала красное за ПРАВИЛЬНО записанный урок —
класс карточки #50 вторым заходом; STUD письменно отказался подгонять текст под прибор.

⚖️ ЧТО ЗДЕСЬ ОХРАНЯЕТСЯ С ДВУХ СТОРОН СРАЗУ:
  · прибор ПРОЩАЕТ формы рассказа/цитаты/провенанса (иначе учит портить верный текст);
  · прибор НЕ СЛЕПНЕТ на живых утверждениях («дерево чисто», «ahead 0», голый GUID
    в инструкции) — контр-примеры обязаны остаться красными.
Формы взяты ИЗ ТАБЛИЦЫ ВЕРДИКТОВ (карточка #185), не из головы; фикстуры ниже — обезличенные
копии реальных строк из памяти ролей.

⚠️ ЖИВАЯ БАЗА НЕ ЧИТАЕТСЯ ВОВСЕ: решето натравливается на фикстурную базу во временном
каталоге. Решето берётся СОСЕДНЕЕ (эта пара каталогов сверяется сторожем дрейфа).
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SIEVE = Path(__file__).resolve().parent / "sieve-role-memory.py"
ROLE = "ЗОНДФОРМ"

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


# Фикстура: (секция, строка, ждём-кандидатом?)  — обезличенные копии реальных вердиктов.
FIXTURE: list[tuple[str, str, bool]] = [
    # ── ДОЛЖНЫ БЫТЬ ПРОЩЕНЫ ─────────────────────────────────────────────
    ("launcher", "① Здесь стояло: «1) ПОДНЯТЬ ТАКТ СИНКА первым ходом, 10–20 минут»", False),
    ("identity", "смотреть НЕ ТОТ индикатор: `ahead 0` говорит «отправлено», а НЕ «всё сохранено»", False),
    ("identity", "с «ролей 8» две недели после появления девятой, и оговорка рядом её не спасла.", False),
    ("state",    "пять призывов опознаны СТУХШИМИ — в том числе «ALL SYNC каждые 2–15 мин», перекрыт словом", False),
    ("identity", "бери запросом (за паузу сменились владелец механизма и правило про push):", False),
    ("plan",     "пока инструкции нет, единоличное владение механизмом = единственная точка отказа.", False),
    ("history",  "- **починка гейта** `07e9152` (гейт 560) — зонд БД+схемы, 503, AllowAnonymous.", False),
    ("history",  "попытки — довольно. Записал ahead 1 + «push при возврате сети» в план. Коммит переживёт;", False),
    ("state",    "0d606b8  признак поиска у метки ЧИТАЕТСЯ из Atlas, а не решается у нас", False),
    ("state",    "Починено (`b869337`), приёмка (`14290e1`) проверена ДВУМЯ нарочными поломками.", False),
    ("state",    "черновик «Академия» (2b983db5-…) НЕ УДАЛЯТЬ (просьба соседа, записка #2473 ⑤)", False),
    ("sources",  "токен-механизм: скоупы, enforcement RequireScope (фаза 1, `1df544d`)", False),
    ("history",  "запись перекрёстного чтения: слепок соседа (#2800, зеркало «9 проверок»→12).", False),
    ("state",    "· спросил «сколько записок без тегов» проверкой на пустую строку → уверенные 0 %", False),
    # ── ОБЯЗАНЫ ОСТАТЬСЯ КАНДИДАТАМИ (живые утверждения о настоящем) ────
    ("state",    "atlas.core `a1f2bdc`, дерево чисто, неотправленного нет · метки: full 671.", True),
    ("state",    "git ingestion .......... cd8fa47 · дерево чисто · неотправленного нет", True),
    ("plan",     'TENANT  = "5902eaa7-cc00-4417-92f2-27c27e42f25b"   # phd1', True),
    ("state",    "ahead 0, всё отправлено — можно закрывать смену", True),
    # Датированное состояние — ВСЁ РАВНО кандидат: канон запрещает хранить состояние диска
    # вовсе (его печатает машинный слой), дата лишь маскирует. Эта строка — различающая
    # для правила «состояние не прощается провенансом»: без него дата+«коммит» простили бы её.
    ("state",    "замер 2026-08-13 10:00 UTC: дерево чисто, неотправленного нет (коммит cd8fa47)", True),
    ("plan",     "push только по слову владельца (см. «правило»)", True),
    ("rebirth",  "спроси владельца, прежде чем запускать guard — молча не гоняй проверки", True),
]


def build_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    by_sec: dict[str, list[str]] = {}
    for sec, line, _ in FIXTURE:
        by_sec.setdefault(sec, []).append(line)
    for sec, lines in by_sec.items():
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'))",
                    (ROLE, sec, "\n".join(lines)))
    con.commit()
    con.close()


def run_sieve(db: Path) -> tuple[set[str], int, str]:
    r = subprocess.run([sys.executable, str(SIEVE), "--role", ROLE, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    flagged = set()
    for ln in out.splitlines():
        m = re.match(r"^\s+\[(\w+):\s*(\d+)\]\s+(.*)", ln)
        if m and "прощено" not in ln:
            flagged.add(m.group(3)[:60])
    m = re.search(r"ИТОГО кандидатов: (\d+)", out)
    return flagged, int(m.group(1)) if m else -1, out


def main() -> int:
    if not SIEVE.exists():
        print(f"🔴 НЕ ЗАПУСТИЛАСЬ: проверки памяти нет рядом ({SIEVE})")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "fixture.db"
        build_db(db)
        flagged, hits, out = run_sieve(db)

        want_red = [line for _, line, red in FIXTURE if red]
        want_ok = [line for _, line, red in FIXTURE if not red]

        # ① НИ ОДИН УРОК/ЦИТАТА/ПРОВЕНАНС НЕ КАНДИДАТ — построчно, не итоговым числом.
        wrongly = [l[:60] for l in want_ok if any(l[:60].startswith(f[:40]) or f.startswith(l[:40])
                                                  for f in flagged)]
        case(f"① все {len(want_ok)} прощаемых форм прощены", not wrongly,
             f"ложно покраснели: {wrongly or '—'}")

        # ② КАЖДОЕ ЖИВОЕ УТВЕРЖДЕНИЕ ОСТАЛОСЬ КРАСНЫМ — прибор не ослеп. Различающий случай:
        #    без него приёмку прошло бы решето, прощающее ВСЁ.
        missed = [l[:60] for l in want_red if not any(l[:60].startswith(f[:40]) or f.startswith(l[:40])
                                                      for f in flagged)]
        case(f"② все {len(want_red)} живых утверждений остались кандидатами", not missed,
             f"замолчаны: {missed or '—'}")

        # ③ СЧЁТ СХОДИТСЯ: кандидатов ровно столько, сколько живых в фикстуре.
        case("③ счёт кандидатов равен числу живых строк", hits == len(want_red),
             f"кандидатов {hits}, живых в фикстуре {len(want_red)}")

        # ④ ПРИЧИНА ПРОЩЕНИЯ ПЕЧАТАЕТСЯ СЛОВОМ (--show-excused): «прощено» без причины
        #    не проверить глазами — а прощённые роль ОБЯЗАНА просматривать.
        r = subprocess.run([sys.executable, str(SIEVE), "--role", ROLE, "--db", str(db),
                            "--show-excused"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        o = r.stdout or ""
        case("④ причины прощения названы словами (провенанс · цитата · урок)",
             "провенанс" in o and "цитата" in o and ("хоронит" in o or "предостерег" in o),
             "в выводе --show-excused должны быть все три причины")

        # ⑤ ГРАНИЦА ОСТАЛАСЬ НАПЕЧАТАННОЙ: пустой вывод ≠ чистая память.
        case("⑤ решето по-прежнему называет свою границу",
             "не «память чиста»" in out or "не «память чиста»" in o)

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 3 (①②③)")
    print("⚖️ ГРАНИЦА: фикстура списана с 49 реальных вердиктов ОДНОГО дня. Живой приказ,")
    print("   спрятанный В КАВЫЧКАХ, правило цитаты замолчит — это названо в самом решете,")
    print("   и потому прощённые печатаются с --show-excused: их просмотр — обязанность роли.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
