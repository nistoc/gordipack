"""
write-message.py — CLI для агента: записать сообщение в mezosync.db.

Использование агентом (из Bash tool):
    python write-message.py --db .mezosync/mezosync.db --role COORD --body "нота текст" --tags F-24,TRACK-NEWUX
    python write-message.py --db .mezosync/mezosync.db --role CORE --body "коммит abc1234" --priority high
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Записать сообщение в mezosync.db")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--role", required=True, help="Роль писателя (COORD, CORE, ...)")
    parser.add_argument("--body", required=True, help="Текст сообщения (markdown)")
    parser.add_argument("--tags", default="", help="Теги через запятую (F-24,TRACK-X)")
    parser.add_argument("--priority", default="normal", choices=["normal", "high", "critical"])
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    tags_json = json.dumps(tags_list, ensure_ascii=False)

    conn = sqlite3.connect(str(db_path), timeout=5)
    cur = conn.execute(
        "INSERT INTO messages (writer_role, body_md, tags, priority) VALUES (?, ?, ?, ?)",
        (args.role, args.body, tags_json, args.priority)
    )
    msg_id = cur.lastrowid
    conn.commit()
    conn.close()

    print(f"OK #{msg_id} [{args.role}] tags={tags_json} priority={args.priority}")


if __name__ == "__main__":
    main()
