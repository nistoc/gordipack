#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: пройти долг ЗАГОЛОВКАМИ можно — но только назвав способ, и долг не исчезает из мира.

ПОВОД. Карточка #193 @CHROME: при долге в сотни записок телами не пройти по арифметике
(замер 11.08: 2,4 МБ тел против памяти чата), и у роли оставался выбор между невозможным
и ничем. Решение владельца 2026-08-12 11:07 UTC: «да, со записью способа».

⚖️ ЧТО ИМЕННО ЗДЕСЬ ОХРАНЯЕТСЯ — НЕ УДОБСТВО, А ЧЕСТНОСТЬ:
  · роль УТВЕРЖДАЕТ ровно то, что было: заголовки видены, тела нет (вид отрезка `declared`);
  · основание ОБЯЗАТЕЛЬНО и содержательно — оно единственное, что отличает честный проход
    от молчаливого пропуска, и читать его будут те, чьи записки прошли мимо;
  · писавшим это ВИДНО через витрину `cursor_gaps` — долг уходит из виду, но не из мира.
🪤 Отдельный флаг, а не поведение `--index` по умолчанию: посмотреть заголовки для справки
   и погасить долг — разные действия. Случай ⑥ стережёт, что их не спутали.

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
ROLE = "ЗОНДПРОХОДА"
DEBT = 40

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(READER), "--role", ROLE, "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def state(db: Path) -> tuple[int, list[tuple]]:
    con = sqlite3.connect(db)
    cur = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                      (ROLE,)).fetchone()[0]
    segs = con.execute("SELECT from_id, to_id, kind, basis, authorized FROM cursor_segments"
                       " WHERE role=? ORDER BY from_id", (ROLE,)).fetchall()
    con.close()
    return cur, segs


def seed(db: Path) -> int:
    con = sqlite3.connect(db)
    con.execute("INSERT OR IGNORE INTO roles (role, lifecycle, lifecycle_by, zone, in_roster,"
                " created_at) VALUES (?,'alive','проба','приёмка',0,datetime('now'))", (ROLE,))
    head = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    for i in range(1, DEBT + 1):
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority,"
                    " resolved, broadcast, addressed_by) VALUES (?,?,datetime('now'),?,'[]',"
                    "'normal',0,1,'field')", (head + i, ROLE, f"проба прохода {i}"))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?,?,datetime('now'))", (ROLE, head))
    con.commit()
    con.close()
    return head


def main() -> int:
    for p in (READER, LIVE_DB):
        if not p.exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет по пути {p}")
            return 2
    probe = sqlite3.connect(LIVE_DB)
    views = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    probe.close()
    if "cursor_gaps" not in views:
        print("🔴 НЕ ЗАПУСТИЛАСЬ: в базе нет готовой выборки cursor_gaps — судить о видимости нечем")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        base = seed(db)

        # ① БЕЗ ОСНОВАНИЯ — ОТКАЗ, И ОТКАЗ ВИДЕН КОДОМ ВОЗВРАТА. Молчаливый проход и есть
        #    то, что лечится; разрешить его «пока некогда придумать основание» значило бы
        #    выдать ключ от чёрного хода вместе с замком.
        code, out = run(db, "--pass-by-index")
        cur, segs = state(db)
        case("① без --basis проход отклонён, отметка прочитанного не тронута",
             code == 2 and cur == base and segs == [], f"код {code} (ждали 2), отметка прочитанного {cur}")

        # ② КОРОТКАЯ ОТПИСКА — ТОЖЕ ОТКАЗ. Основание из трёх букв формально есть и по сути
        #    отсутствует; порог низкий, но он отсекает «.» и «нет».
        code, out = run(db, "--pass-by-index", "--basis", "лень")
        cur, _ = state(db)
        case("② отписка вместо основания отклонена", code == 2 and cur == base)

        # ③ ЧЕСТНЫЙ ПРОХОД: отрезок 'declared' на весь долг, основание и автор записаны,
        #    курсор доехал до головы.
        code, out = run(db, "--pass-by-index", "--basis",
                        "долг 40 записок, тела не помещаются в чат; разобрано заголовками")
        cur, segs = state(db)
        mine = [s for s in segs if s[2] == 'declared']
        ok3 = (cur == base + DEBT and len(mine) == 1
               and mine[0][0] == base + 1 and mine[0][1] == base + DEBT
               and "заголовками" in (mine[0][3] or "") and "owner" in (mine[0][4] or ""))
        case("③ проход записан видом 'declared' с основанием и автором", ok3,
             f"отметка прочитанного {cur} (ждали {base + DEBT}) · отрезки: {segs}")

        # ④ ВИДНО ПИСАВШИМ: витрина «что не дошло» показывает этот участок. Без этого
        #    случая проход был бы просто тихим способом обнулить долг.
        con = sqlite3.connect(db)
        gap = con.execute("SELECT notes, basis FROM cursor_gaps WHERE role=?", (ROLE,)).fetchall()
        con.close()
        case("④ экран cursor_gaps показывает пройденное как НЕ ДОШЕДШЕЕ",
             len(gap) == 1 and gap[0][0] == DEBT, f"экран: {gap}")

        # ⑤ ЗАГОЛОВКИ ПОКАЗАНЫ ПЕРЕД ПРОХОДОМ — роль проходит то, что ВИДЕЛА, а не вслепую.
        case("⑤ перед проходом напечатан указатель",
             "📇 УКАЗАТЕЛЬ" in out and out.count("\n  #") >= DEBT,
             f"строк указателя в выводе: {out.count(chr(10) + '  #')}")

        # ⑥ КОНТРОЛЬНАЯ ПАРА, РАЗЛИЧАЮЩАЯ: ОБЫЧНЫЙ --index НИЧЕГО НЕ ГАСИТ. Если бы проход
        #    стал поведением по умолчанию, справочный взгляд на заголовки молча съедал бы долг.
        base2 = seed(db)
        cur_before, segs_before = state(db)
        run(db, "--index")
        cur_after, segs_after = state(db)
        case("⑥ обычный --index отметку прочитанного не двигает и отрезков не пишет",
             cur_after == cur_before and segs_after == segs_before,
             f"отметка прочитанного {cur_before} → {cur_after}")

    # ⑦ ЖИВАЯ БАЗА ЦЕЛА.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute("SELECT COUNT(*) FROM cursor_segments WHERE role=?", (ROLE,)).fetchone()[0]
    con.close()
    case("⑦ живая база не тронута", leaked == 0, f"отрезков зонда в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 5 (①②③④⑥)")
    print("⚖️ ГРАНИЦА: проверено, что способ ЗАПИСАН и ВИДЕН. Что основание ПРАВДИВО —")
    print("   не проверяется ничем и проверено быть не может: это слово роли. Механизм")
    print("   отвечает за то, чтобы слово было сказано, названо автором и показано другим.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
