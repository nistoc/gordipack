r"""
bridge-groups.py — Устанавливает связь (cross_link) между двумя группами.

Использование:
    python <КОНТУР>/.mezosync/scripts/bridge-groups.py \
        --source-db "<КОНТУР>\.mezosync\mezosync.db" \
        --target-db "<контейнер соседа>\.mezosync\mezosync.db" \
        --description "Atlas ↔ RCC DWH bridge"

Сосед, чью базу открывать нельзя (правило no-scan-external-contours), — имя группы рукой:
    python <КОНТУР>/.mezosync/scripts/bridge-groups.py \
        --source-db "<КОНТУР>/.mezosync/mezosync.db" \
        --target-db "<контейнер соседа>/.mezosync/mezosync.db" --target-group <имя> \
        --description "<откуда известно имя и путь: письмо соседа, час UTC>"
    Базу соседа инструмент тогда не открывает; нужен только существующий каталог его контейнера —
    по нему обход писем ищет папки моста (sync_backoff.py). --bidirectional с ним не сочетается:
    это запись в чужую базу.
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def get_group_name(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
    conn.close()
    return row[0] if row else "unknown"


def main():
    parser = argparse.ArgumentParser(description="Связать две группы Горди")
    parser.add_argument("--source-db", required=True, help="Путь к БД источника")
    parser.add_argument("--target-db", required=True, help="Путь к БД цели")
    parser.add_argument("--description", default="", help="Описание связи")
    parser.add_argument("--bidirectional", action="store_true",
                        help="Создать связь в обе стороны")
    parser.add_argument("--target-group", default="",
                        help="имя группы соседа рукой — его базу тогда не открываем (карточка #684)")
    args = parser.parse_args()

    source_path = Path(args.source_db).resolve()
    target_path = Path(args.target_db).resolve()

    if not source_path.exists():
        print(f"❌ Не найдена source БД: {source_path}")
        return 2
    # Карточка #684: соседа onto нельзя было завести вовсе — инструмент читал имя группы из ЕГО базы,
    # а открывать чужую базу запрещает правило no-scan-external-contours. Имя рукой — без чтения.
    if args.target_group:
        if args.bidirectional:
            print("❌ --bidirectional с --target-group не сочетается: это запись в базу соседа")
            return 2
        if not target_path.parent.parent.is_dir():
            print(f"❌ Нет каталога контейнера соседа: {target_path.parent.parent}")
            return 2
        target_name = args.target_group
    else:
        if not target_path.exists():
            print(f"❌ Не найдена target БД: {target_path}")
            return 2
        target_name = get_group_name(str(target_path))

    source_name = get_group_name(str(source_path))

    # Добавляем ссылку в source → target
    conn = sqlite3.connect(str(source_path))
    conn.execute("""
        INSERT OR REPLACE INTO cross_links (source_group, target_group, target_db_path, description)
        VALUES (?, ?, ?, ?)
    """, (source_name, target_name, str(target_path), args.description))
    conn.commit()
    conn.close()
    print(f"✅ {source_name} → {target_name} (в {source_path})")

    if args.bidirectional:
        conn = sqlite3.connect(str(target_path))
        conn.execute("""
            INSERT OR REPLACE INTO cross_links (source_group, target_group, target_db_path, description)
            VALUES (?, ?, ?, ?)
        """, (target_name, source_name, str(source_path), args.description))
        conn.commit()
        conn.close()
        print(f"✅ {target_name} → {source_name} (в {target_path})")

    print(f"\n🔗 Связь установлена: {source_name} ↔ {target_name}")
    return 0


if __name__ == "__main__":
    # Карточка #684: отказ «❌» прежде выходил кодом 0 — вызывающий скрипт принимал его за связь
    sys.exit(main())
