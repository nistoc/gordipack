"""
broadcast.py — общий канал: любая роль объявляет что-то ВСЕМ.

Broadcast — это обычное сообщение в общей ленте `messages`, помеченное тегом `ALL`.
Все роли видят его одним запросом (read-broadcasts.py), не сканируя 8 хвостов.

Использование:
    # простое объявление всем (FYI)
    python broadcast.py --db mezosync.db --role ING --body "aia.llmgateway UP на http://localhost:5297"

    # призыв к действию (CTA): priority=high + требует ACK от ролей
    python broadcast.py --db mezosync.db --role COORD --body "всем сохранить phoenix" --cta

    # с дополнительными тегами
    python broadcast.py --db mezosync.db --role STUD --body "..." --tags "release,ui"
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Объявить broadcast всем ролям")
    p.add_argument("--db", required=True)
    p.add_argument("--role", required=True, help="Кто объявляет (writer_role)")
    p.add_argument("--body", required=True, help="Текст объявления")
    p.add_argument("--tags", default="", help="Доп. теги через запятую (ALL добавляется всегда)")
    p.add_argument("--cta", action="store_true",
                   help="Call-to-action: priority=high + тег CTA (ждёт ACK ролей)")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    tags = ["ALL"]
    if args.cta:
        tags.append("CTA")
    for t in args.tags.split(","):
        t = t.strip()
        if t and t not in tags:
            tags.append(t)

    priority = "high" if args.cta else "normal"

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    cur = conn.execute(
        "INSERT INTO messages (writer_role, body_md, tags, priority) VALUES (?,?,?,?)",
        (args.role, args.body, json.dumps(tags, ensure_ascii=False), priority),
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()

    kind = "CTA (ждёт ACK)" if args.cta else "FYI"
    print(f"📣 BROADCAST #{msg_id} [{args.role}] {kind} tags={tags}")
    if args.cta:
        print(f"   Роли увидят через read-broadcasts.py и ACK'нут; статус — read-broadcasts.py --status")


if __name__ == "__main__":
    main()
