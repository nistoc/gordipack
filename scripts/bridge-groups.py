"""
bridge-groups.py — Устанавливает связь (cross_link) между двумя группами.

Использование:
    python bridge-groups.py \
        --source-db "C:\guts\.atlas\.mezosync\mezosync.db" \
        --target-db "C:\guts\.rcc\.mezosync\mezosync.db" \
        --description "Atlas ↔ RCC DWH bridge"
"""

import argparse
import sqlite3
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
    args = parser.parse_args()

    source_path = Path(args.source_db).resolve()
    target_path = Path(args.target_db).resolve()

    if not source_path.exists():
        print(f"❌ Не найдена source БД: {source_path}")
        return
    if not target_path.exists():
        print(f"❌ Не найдена target БД: {target_path}")
        return

    source_name = get_group_name(str(source_path))
    target_name = get_group_name(str(target_path))

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


if __name__ == "__main__":
    main()
