# -*- coding: utf-8 -*-
"""20260822-sync-backoff-bridge-mtime — отметка «что из моста уже видели» (карточка #242).

ПОВОД. Ритм синхронизации мерил тишину только по ленте записок, а сосед пишет ФАЙЛОМ
в папку обмена: его вопрос тишину не сбрасывал, и роль наращивала сон до потолка через
три минуты после чужого письма. Починка требует помнить, какой самый свежий чужой файл
обмена роль уже видела, — это и есть новый столбец.

⚖️ БЕЗ NOT NULL НАМЕРЕННО: пустое значение означает «обмен ещё не читали», и оно обязано
ОТЛИЧАТЬСЯ от нуля, который значил бы «читали, там пусто». Свести их — значит объявить
разобранным то, чего никто не видел.

🪤 ЧЕМУ ЭТОТ ШАГ ОБЯЗАН СВОИМ РОЖДЕНИЕМ. Первая редакция починки добавляла столбец
НА ХОДУ (ALTER при обращении) и не записывала шаг в журнал схемы. Сторож журнала честно
закричал «схему меняли мимо журнала» — на свежесобранном контуре при приёмке сборки,
а затем то же подтвердилось на живом. Ровно класс правила `migrations-under-watch`:
изменение схемы от того, что кто-то позвал функцию, — без решения и без следа.
Правка на ходу ОСТАВЛЕНА в sync_backoff._table() как страховка для контура, который
обновил инструменты раньше, чем прогнал шаги, — но теперь она записывает себя в журнал
тем же общим модулем, что и этот шаг.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mezo_paths  # noqa: E402
import schema_journal  # noqa: E402

VERSION = "20260822-sync-backoff-bridge-mtime"


def main() -> int:
    # ⚠️ ПУТЬ К БАЗЕ — ДОВОДОМ, см. разбор в соседнем шаге 20260816: прежняя редакция
    # звала live_db() и молча игнорировала --db, отвечая успехом о ЖИВОЙ базе.
    ap = argparse.ArgumentParser(description="шаг схемы: мост сна к соседям по времени правки")
    ap.add_argument("--db", default=None, help="путь к базе; без него — живая база контура")
    ap.add_argument("--dry-run", action="store_true", help="ХОЛОСТОЙ прогон: ничего не менять")
    a = ap.parse_args()
    db = mezo_paths.resolve_db(a.db, __file__)
    print(f"📂 БАЗА: {db}")
    con = sqlite3.connect(db)
    есть_таблица = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_backoff'").fetchone()
    столбцы = ({r[1] for r in con.execute("PRAGMA table_info(sync_backoff)")}
               if есть_таблица else set())
    уже = con.execute("SELECT 1 FROM schema_migrations WHERE version=?",
                      (VERSION,)).fetchone()

    if a.dry_run:
        print(f"⟨ВХОЛОСТУЮ⟩ таблица sync_backoff: {'есть' if есть_таблица else 'НЕТ'} · "
              f"столбец last_bridge_mtime: "
              f"{'есть' if 'last_bridge_mtime' in столбцы else 'НЕТ'} · "
              f"запись в журнале: {'есть' if уже else 'НЕТ'}")
        print("⟨ВХОЛОСТУЮ⟩ база НЕ тронута.")
        con.close()
        return 0

    if есть_таблица and "last_bridge_mtime" in столбцы:
        if уже:
            print("шаг уже применён и записан — делать нечего")
            con.close()
            return 0
        # Столбец есть, записи нет: он добавлен правкой на ходу ДО того, как та научилась
        # записывать себя. Восстанавливаем след задним числом — честно помеченным.
        schema_journal.record_step(
            con, VERSION,
            "отметка последнего виденного чужого файла обмена (карточка #242); "
            "столбец был добавлен правкой на ходу, запись восстановлена",
            backdated=True)
        con.commit()
        print("столбец уже был — запись о нём восстановлена задним числом, "
              "отпечаток схемы сверен заново")
        con.close()
        return 0

    con.execute("BEGIN")
    if not есть_таблица:
        # Контур старше схемы v3: таблицу ритма заводит этот же шаг, одной транзакцией.
        con.execute("""CREATE TABLE sync_backoff (
                           role TEXT PRIMARY KEY,
                           sleep_sec INTEGER NOT NULL,
                           quiet_streak INTEGER NOT NULL DEFAULT 0,
                           last_seen_id INTEGER NOT NULL DEFAULT 0,
                           updated_at TEXT)""")
    con.execute("ALTER TABLE sync_backoff ADD COLUMN last_bridge_mtime REAL")
    schema_journal.record_step(
        con, VERSION,
        "отметка последнего виденного чужого файла обмена: письмо соседа сбрасывает "
        "разгон сна так же, как записка в ленте (карточка #242)")
    con.commit()
    con.close()
    print("столбец last_bridge_mtime добавлен, шаг записан в журнал той же транзакцией")
    return 0


if __name__ == "__main__":
    sys.exit(main())
