#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
МИГРАЦИЯ: ЗАМОК ПРОТИВ ГОНКИ ПРИ ВЫДАЧЕ БАТЧА ЛЕНТЫ.

СЛОВО ВЛАДЕЛЬЦА 2026-08-09 12:49 UTC: «замок в базе + транзакция».

ЧТО БОЛЕЛО (замер 2026-08-09 12:46 UTC, карточка #150).
Читалка ленты сначала СПРАШИВАЕТ, есть ли у роли неподтверждённый батч (тогда перевыдаёт
его), и только потом ВСТАВЛЯЕТ новый. Между вопросом и вставкой нет исключающей транзакции:
два процесса, стартовавшие одновременно, ОБА видят «батча нет» и ОБА вставляют.
    приёмка bite-r16.py, свойство P7 (два параллельных вызова):
       «батчей в БД 2 · токены РАЗОШЛИСЬ» — 4 отказа из 13 прогонов набора,
       и 0 отказов из 8 у того же укуса В ОДИНОЧКУ
⇒ Гонка была всегда; видно её только под нагрузкой, когда вызовы накладываются по времени.
🎯 Цена не теоретическая: роль, позвавшая читалку дважды почти одновременно (разведочный
   вызов + боевой — наша же штатная практика), получает ПОЛОВИНКИ ТОКЕНА ОТ РАЗНЫХ ВЫВОДОВ
   и не может подтвердить прочитанное.

ПОЧЕМУ ЗАМОК ИМЕННО ТАКОЙ — ЗАМЕР ДО КОДА, НЕ ВКУС (12:54 UTC, на копии живой базы):
    ① UNIQUE(role) WHERE acked_at IS NULL ...... 🔴 НЕ ВСТАЛ на живых данных
       Он запретил бы ЗАКОННОЕ: у роли CHROME лежат батч от 06.08 (last_id=50, брошен)
       и батч от 07.08 (last_id=3097). Это не гонка — это неподтверждённый батч,
       переживший сутки. Строгий замок объявил бы нарушением обычную жизнь.
    ② UNIQUE(role, last_id) WHERE acked_at IS NULL ... ✅ ВСТАЛ
       Он запрещает ровно то, что делает ГОНКА: два батча одной роли НА ОДИН И ТОТ ЖЕ
       хвост. Разные хвосты — законны и не задеты.
⚖️ Разница между ① и ② найдена ЗАМЕРОМ, а не рассуждением. Первый вариант выглядел строже
   и правильнее — и сломал бы работу ролям в тот же день.

ЧТО ДЕЛАЕТ МИГРАЦИЯ — ТОЛЬКО ДОБАВЛЯЕТ ИНДЕКС:
    CREATE UNIQUE INDEX IF NOT EXISTS ux_batch_race
        ON read_batches(role, last_id) WHERE acked_at IS NULL;
⛔ Строк не удаляет и не правит. Ни одной существующей записи не трогает.
⛔ Брошенные батчи НЕ убирает: их гигиена (7 суток) живёт в читалке и это отдельный предмет.

ИДЕМПОТЕНТНА: IF NOT EXISTS, повторный прогон ничего не портит.
ЗАПИСЫВАЕТ СЕБЯ В ЖУРНАЛ САМА (правило `schema-step-records-itself`).
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema_journal import record_step  # noqa: E402

DDL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_batch_race
    ON read_batches(role, last_id) WHERE acked_at IS NULL;
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="замок против гонки при выдаче батча")
    ap.add_argument("--db", required=True, help="путь к базе; на живой — только после копии")
    args = ap.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f"⛔ базы нет: {db}")

    conn = sqlite3.connect(f"file:{str(db).replace(chr(92), '/')}?mode=rw", uri=True, timeout=10)

    idx_before = {n for n, in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    batches_before = conn.execute("SELECT COUNT(*) FROM read_batches").fetchone()[0]
    unacked_before = conn.execute(
        "SELECT COUNT(*) FROM read_batches WHERE acked_at IS NULL").fetchone()[0]

    try:
        conn.executescript(DDL)
        conn.commit()
    except sqlite3.IntegrityError as e:
        # ⚖️ Отказ ГРОМКИЙ и с предметом: в базе уже лежат два батча одной роли на один
        #    хвост, то есть гонка успела сработать. Молча «почистить» их нельзя — это
        #    чужое непрочитанное, и решение о нём принимает владелец, а не миграция.
        conn.close()
        print(f"⛔ ЗАМОК НЕ ВСТАЛ: {e}")
        print("   В базе УЖЕ есть два неподтверждённых батча одной роли на ОДИН хвост.")
        print("   Это след сработавшей гонки. Разбирать их — отдельный ход и отдельное")
        print("   слово: за ними стоит чужое непрочитанное, а не мусор.")
        return 1

    idx_after = {n for n, in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    batches_after = conn.execute("SELECT COUNT(*) FROM read_batches").fetchone()[0]
    unacked_after = conn.execute(
        "SELECT COUNT(*) FROM read_batches WHERE acked_at IS NULL").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    ok = (batches_before == batches_after and unacked_before == unacked_after
          and integrity == "ok" and "ux_batch_race" in idx_after)
    if ok:
        record_step(conn, "20260809-batch-race-lock",
                    "замок против гонки выдачи батча: UNIQUE(role,last_id) WHERE acked_at IS NULL")
        conn.commit()
    conn.close()

    print("=" * 70)
    print("МИГРАЦИЯ: замок против гонки при выдаче батча")
    print("=" * 70)
    print(f"индексов было ....... {len(idx_before)}   стало {len(idx_after)}")
    print(f"добавлено ........... {', '.join(sorted(idx_after - idx_before)) or '— (уже было)'}")
    print(f"удалено ............. {', '.join(sorted(idx_before - idx_after)) or 'ничего ✅'}")
    print(f"батчей .............. {batches_before} → {batches_after}"
          f"   {'✅ не тронуты' if batches_before == batches_after else '🔴 ИЗМЕНИЛОСЬ'}")
    print(f"неподтверждённых .... {unacked_before} → {unacked_after}"
          f"   {'✅ не тронуты' if unacked_before == unacked_after else '🔴 ИЗМЕНИЛОСЬ'}")
    print(f"целостность ......... {integrity}")
    print()
    print("✅ ПРОШЛА (шаг записал себя в журнал)" if ok
          else "🔴 НЕ ПРОШЛА — откатывай из точки отката")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
