#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРАВА РОЛИ — ПОЛЯМИ, А НЕ ПРОЗОЙ В ЕЁ ПАМЯТИ.

СЛОВО ВЛАДЕЛЬЦА 2026-08-08 22:33 UTC: «① Сделать права роли полями, как у правил:
что разрешено, кто разрешил, когда, разовое или стоячее».

🪤 ПОВОД — ЗАМЕР ЭТОГО ЖЕ ДНЯ, А НЕ АНАЛОГИЯ.
У правил основание стало полями утром — и сразу выяснилось, что ОДИННАДЦАТЬ правил объявляют
решение владельца, не помня, когда он его принял. Права ролей живут ровно в том виде, из
которого это выкапывалось: прозой, в памяти каждой роли, своими словами.
Цена уже заплачена дважды за одну смену:
  · снятие запрета на отправку жило в ТРЁХ местах, и два нашлись только потому, что искали;
  · разовое разрешение на push я сам дважды спутал — потрачено оно или ещё нет.

🎯 ЧЕТЫРЕ ПОЛЯ ВЛАДЕЛЬЦА + ДВА, БЕЗ КОТОРЫХ ОНИ НЕ РАБОТАЮТ:
    role · right_key ..... КОМУ и ЧТО разрешено
    authorized_by ........ КТО разрешил
    granted_at ........... КОГДА
    kind ................. РАЗОВОЕ или СТОЯЧЕЕ
  + source_ref ........... ГДЕ это сказано. Без него право нельзя ни проверить, ни отозвать
                           безопасно: отзывающий не знает, отменяет живое слово или пересказ
  + scope ................ ОБЛАСТЬ: репозиторий, база, зона. Класс сегодняшнего дня, пойманный
                           ТРИЖДЫ на разных правилах: разрешение или запрет БЕЗ названной
                           области расползается и начинает значить не то

⚡ И ОДНО, ЧЕГО В ЗАМЫСЛЕ НЕ БЫЛО: РАЗОВОЕ ПРАВО УМЕЕТ ТРАТИТЬСЯ (`spent_at`).
Разовое разрешение без следа расхода — это стоячее разрешение, которым пользуются, пока
не постесняются. Пока расход жил в памяти роли, я сам за одну смену дважды не смог ответить,
потрачено ли слово. Теперь ответ даёт запрос, а не воспоминание.

⛔ ОТЗЫВ — НЕ УДАЛЕНИЕ: `revoked_at` + `revoked_why`. Удалённое право нельзя даже назвать,
а история прав — это ровно то, что спрашивают, когда что-то пошло не так.

📌 ДОБАВЛЯЕТ ТОЛЬКО ТАБЛИЦУ. Ни одной существующей строки не трогает.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema_journal import record_step  # noqa: E402

VERSION = "009-role-rights"

DDL = """
CREATE TABLE IF NOT EXISTS role_rights (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    role          TEXT NOT NULL,
    right_key     TEXT NOT NULL,
    scope         TEXT,
    kind          TEXT NOT NULL CHECK (kind IN ('standing','once')),
    authorized_by TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    source_ref    TEXT NOT NULL,
    spent_at      TEXT,
    revoked_at    TEXT,
    revoked_why   TEXT,
    declared_by   TEXT NOT NULL DEFAULT 'field' CHECK (declared_by IN ('field','backfill')),
    note          TEXT
);
CREATE INDEX IF NOT EXISTS ix_role_rights_role ON role_rights (role);
CREATE VIEW IF NOT EXISTS role_rights_live AS
    SELECT * FROM role_rights
     WHERE revoked_at IS NULL
       AND NOT (kind = 'once' AND spent_at IS NOT NULL);
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="права роли полями, а не прозой")
    ap.add_argument("--db", default=str(Path(__file__).resolve().parents[2] / "mezosync.db"))
    ap.add_argument("--apply", action="store_true",
                    help="ЗАПИСАТЬ. Без него — только замер, база не трогается")
    args = ap.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f"⛔ базы нет: {db}")

    conn = sqlite3.connect(str(db), timeout=10)
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    print("=" * 74)
    print("ПРАВА РОЛИ — ПОЛЯМИ")
    print("=" * 74)
    print(f"таблица role_rights ........... {'УЖЕ ЕСТЬ' if 'role_rights' in have else 'нет, будет создана'}")
    print(f"витрина role_rights_live ...... {'УЖЕ ЕСТЬ' if 'role_rights_live' in have else 'нет, будет создана'}")

    if not args.apply:
        print()
        print("🔍 ЗАМЕР, БАЗА НЕ ТРОНУТА. Записать — тем же вызовом с --apply.")
        conn.close()
        return 0

    counts_before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ("messages", "rules", "phoenix")}
    conn.executescript(DDL)
    fp = record_step(conn, VERSION, "role_rights: права роли полями (что · кто · когда · "
                                    "разовое/стоячее · где сказано · область)")
    conn.commit()

    counts_after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in counts_before}
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    ver = conn.execute("SELECT * FROM schema_version").fetchone()
    conn.close()

    print()
    for t, was in counts_before.items():
        mark = "✅ НЕ ТРОНУТА" if was == counts_after[t] else "🔴 ИЗМЕНИЛАСЬ"
        print(f"{t:10} {was} → {counts_after[t]}   {mark}")
    print(f"целостность ................... {integrity}")
    print(f"журнал схемы .................. шаг {VERSION}, отпечаток {fp}")
    print(f"база о себе ................... {ver}")
    ok = counts_before == counts_after and integrity == "ok"
    print()
    print("✅ ЗАПИСАНО" if ok else "🔴 НЕ ПРОШЛО — откатывай из точки отката")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
