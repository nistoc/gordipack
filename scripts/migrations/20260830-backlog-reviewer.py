# -*- coding: utf-8 -*-
"""20260830-backlog-reviewer — КТО ПРИНИМАЕТ РАБОТУ, СТАНОВИТСЯ ПОЛЕМ.

ПОВОД (карточка #482, слово владельца 2026-08-30 11:02 UTC). Правило требует: приёмку
даёт роль, НЕ делавшая работу. Но КТО ИМЕННО — не назначает никто. Замер @COORD
(записка #4436): когда карточку завела другая роль, приёмщик получается сам собой
(медиана ожидания 0.6 ч); когда роль завела карточку себе — рук не назначено ничем
(медиана 2.1 ч, худший случай 264 ч), и таких в очереди две трети.

ЧТО ДОБАВЛЯЕТ: backlog.reviewer — кто принимает. Поле принимает ДВЕ законные формы:
имя роли («TAXO») и ПРАВИЛО словами («любая, не писавшая правку»). Обе видны, обе
не врут: попытка уместить правило в поле для имени заставила бы роли писать туда
ложные имена, а это хуже пустоты.

⚖️ ПОЧЕМУ ПОЛЕ, А НЕ ПРИМЕЧАНИЕ ПЕРЕВОДА. Замер 2026-08-30 11:04 UTC по всей истории:
переводов на приёмку 97, имя чужой роли встречается в примечании у 34 (35%) — и это
ВЕРХНЯЯ граница, потому что имя могло стоять по любому поводу. Из текста примечания
приёмщика нельзя ни показать в сводке роли, ни посчитать проверкой.

⛔ ЧЕГО ЭТОТ ШАГ НЕ ДЕЛАЕТ: не назначает приёмщика сам и не запрещает сдавать работу
без него. Сдача важнее опрятности — инструмент, не давший роли сдать работу, толкает
её сдавать мимо механизма.
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import record_step, verify  # noqa: E402

VERSION = "20260830-backlog-reviewer"
COLUMN = "reviewer"
ALTER = f"ALTER TABLE backlog ADD COLUMN {COLUMN} TEXT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import mezo_paths
    db = mezo_paths.resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(backlog)")]
    have = COLUMN in cols
    print(f"база: {db}")
    print(f"столбец backlog.{COLUMN}: {'УЖЕ ЕСТЬ' if have else 'нет — будет добавлен'}")
    сейчас_на_приёмке = conn.execute(
        "SELECT COUNT(*) FROM backlog WHERE status='in_review'").fetchone()[0]
    print(f"карточек на приёмке сейчас: {сейчас_на_приёмке} — у всех приёмщик будет ПУСТ, "
          f"и это честно: его и не было")
    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута.")
        return
    logged = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?",
                          (VERSION,)).fetchone()
    if have and logged:
        print("\n⚖️ Всё есть и след есть — шаг ничего не меняет.")
        return
    if have and not logged:
        fp = record_step(conn, VERSION, f"backlog.{COLUMN}: заведён ранее без журнала; "
                         f"след восстановлен задним числом", backdated=True)
        conn.commit()
        print(f"✅ След восстановлен. отпечаток: {fp}")
        return
    conn.execute("BEGIN")
    conn.execute(ALTER)
    fp = record_step(
        conn, VERSION,
        "backlog.reviewer: КТО ПРИНИМАЕТ работу — полем, а не текстом примечания "
        "(карточка #482, слово владельца 11:02 UTC). Две законные формы: имя роли "
        "и правило словами. Замер @COORD: своя заявка ждёт приёмки втрое дольше, "
        "потому что рук ей не назначает никто. Поле НЕ обязательно: сдача важнее "
        "опрятности, инструмент только говорит вслух, когда приёмщик не назван")
    conn.commit()
    print(f"\n✅ ВРЕЗАНО. отпечаток схемы: {fp}")
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print("целостность:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    cols2 = [r[1] for r in conn.execute("PRAGMA table_info(backlog)")]
    print(f'{"✅" if COLUMN in cols2 else "🔴"} столбец на месте · всего столбцов {len(cols2)}')


if __name__ == '__main__':
    main()
