#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: подтверждение чтения ПИТАЕТ таблицу отрезков, а не только двигает курсор.

ПОВОД (замер @PROTO 2026-08-11 20:09 UTC, карточка #193). Шаг схемы `003-cursor-segments`
применён к ЖИВОЙ базе 06.08: девять строк, по одной на роль, все вида `declared`
(«перенос плоского курсора»). И с тех пор таблица не пополнялась НИ РАЗУ — живых скриптов,
которые в неё пишут, ноль.

🎯 КЛАСС, РАДИ КОТОРОГО ЭТА ПРИЁМКА: **сосуд заведён, засеян и не питается.** Он выглядит
живым — таблица есть, строки есть, шаг миграции записан честно, — и отвечает данными,
застывшими в день посева. Пустой сосуд заметили бы (его молчание видно); засеянный-и-мёртвый
отвечает уверенно и неверно. Родня «ложного ноля» и «непоказанного репозитория».

⚖️ ПОЧЕМУ СВОЙСТВО ФОРМУЛИРУЕТСЯ КАК «ПИТАЕТСЯ», А НЕ «ЕСТЬ СТРОКИ»: проверка на непустоту
прошла бы ЗЕЛЁНОЙ все пять суток, пока сосуд был мёртв. Поэтому судим по ПРИРОСТУ после
действия, которое обязано его дать.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

READER = mezo_target.script("read-messages.py")
LIVE_DB = mezo_paths.live_db()
ROLE = "ЗОНДОТРЕЗКА"

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(READER), "--role", ROLE, "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def seed(db: Path, unread: int) -> int:
    con = sqlite3.connect(db)
    con.execute("INSERT OR IGNORE INTO roles (role, lifecycle, lifecycle_by, zone, in_roster,"
                " created_at) VALUES (?,'alive','проба','приёмка',0,datetime('now'))", (ROLE,))
    head = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    for i in range(1, unread + 1):
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority,"
                    " resolved, broadcast, addressed_by) VALUES (?,?,datetime('now'),?,'[]',"
                    "'normal',0,1,'field')", (head + i, ROLE, f"проба питания отрезков {i}"))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?,?,datetime('now'))", (ROLE, head))
    con.commit()
    con.close()
    return head


def segments(db: Path) -> list[tuple]:
    con = sqlite3.connect(db)
    rows = con.execute("SELECT from_id, to_id, kind FROM cursor_segments WHERE role=?"
                       " ORDER BY from_id", (ROLE,)).fetchall()
    con.close()
    return rows


def live_token(db: Path) -> str:
    con = sqlite3.connect(db)
    tok = con.execute("SELECT token FROM read_batches WHERE role=? AND acked_at IS NULL"
                      " ORDER BY rowid DESC LIMIT 1", (ROLE,)).fetchone()
    con.close()
    return tok[0] if tok else ""


def main() -> int:
    for p in (READER, LIVE_DB):
        if not p.exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет по пути {p}")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        # ⚠️ Соединение ЗАКРЫВАЕМ явно: на Windows открытая ручка не даёт снести временный
        # каталог, и приёмка падает уборкой — исход «НЕ ЗАПУСТИЛАСЬ», который легко принять
        # за поломку испытуемого. Поймано первым же прогоном этого файла.
        probe = sqlite3.connect(db)
        tables = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        probe.close()
        if "cursor_segments" not in tables:
            print("🔴 НЕ ЗАПУСТИЛАСЬ: в базе нет таблицы cursor_segments — судить нечего")
            return 2
        base = seed(db, unread=6)

        # ① ЧТЕНИЕ БЕЗ ПОДТВЕРЖДЕНИЯ НИЧЕГО НЕ ПИШЕТ. Контрольная пара к ②: отрезок —
        #    след ПОДТВЕРЖДЁННОГО чтения, а не показа. Иначе «посмотрел» стало бы «прочитал».
        run(db, "--limit", "3")
        case("① чтение без ack отрезков не создаёт", segments(db) == [],
             f"отрезков после чтения: {len(segments(db))}")

        # ② ЧЕСТНЫЙ ACK ПИТАЕТ СОСУД — ровно на прочитанное телом, видом 'read'.
        tok = live_token(db)
        code, out = run(db, "--ack", tok) if tok else (1, "токен не найден")
        segs = segments(db)
        case("② после ack появился отрезок 'read' ровно на прочитанное",
             segs == [(base + 1, base + 3, "read")],
             f"токен: {tok or '—'} · отрезки: {segs} (ждали [({base+1}, {base+3}, 'read')])")

        # ③ ПОВТОРНЫЙ ACK ТОГО ЖЕ ТОКЕНА ОТРЕЗКА НЕ ДОБАВЛЯЕТ: он отвергается целиком,
        #    и сосуд не должен получать след от отвергнутого действия.
        run(db, "--ack", tok)
        case("③ повторный ack отрезка не добавил", segments(db) == segs,
             f"отрезков: {len(segments(db))}")

        # ④ ПРОДОЛЖЕНИЕ ЧТЕНИЯ ДАЁТ СЛЕДУЮЩИЙ ОТРЕЗОК, НЕ ПЕРЕКРЫВАЯ ПРЕЖНИЙ.
        #    Перекрытие — отказ ④ замысла: одна записка не может быть пройдена дважды.
        run(db, "--limit", "3")
        tok2 = live_token(db)
        run(db, "--ack", tok2)
        segs2 = segments(db)
        overlap = any(a[1] >= b[0] for a, b in zip(segs2, segs2[1:]))
        case("④ второй ack продолжил ленту без перекрытия",
             len(segs2) == 2 and segs2[1] == (base + 4, base + 6, "read") and not overlap,
             f"отрезки: {segs2}")

        # ⑤ ЦЕЛОСТНОСТЬ ГЛАВНОГО ПУТИ: курсор всё так же доехал до головы. Питание сосуда
        #    не смеет сломать то, ради чего ack существует, — это регресс-страж.
        con = sqlite3.connect(db)
        cursor = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                             (ROLE,)).fetchone()[0]
        con.close()
        case("⑤ отметка прочитанного доехала до головы — главный путь цел", cursor == base + 6,
             f"отметка прочитанного {cursor}, ждали {base + 6}")

    # ⑥ ЖИВАЯ БАЗА ЦЕЛА.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute("SELECT COUNT(*) FROM cursor_segments WHERE role=?", (ROLE,)).fetchone()[0]
    con.close()
    case("⑥ живая база не тронута", leaked == 0, f"отрезков зонда в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 4 (①②③④)")
    print("⚖️ ГРАНИЦА: проверено ПИТАНИЕ сосуда чтением. Что засеянные 06.08 отрезки 'declared'")
    print("   говорят правду про прошлое — НЕ проверяется здесь и неправда: они утверждают,")
    print("   что до 06.08 глазами не читал никто. Это разбирается по одной роли, руками.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
