"""
broadcast.py — общий канал: любая роль объявляет что-то ВСЕМ.

Broadcast — это обычное сообщение в общей ленте `messages`, помеченное тегом `ALL`.
Все роли видят его одним запросом (read-broadcasts.py), не сканируя 8 хвостов.

Использование:
    # простое объявление всем (FYI)
    python <КОНТУР>/.mezosync/scripts/broadcast.py --role ING --body "aia.llmgateway UP на http://localhost:5297"

    # призыв к действию (CTA): priority=high + требует ACK от ролей
    python <КОНТУР>/.mezosync/scripts/broadcast.py --role COORD --body "всем сохранить phoenix" --cta

    # с дополнительными тегами
    python <КОНТУР>/.mezosync/scripts/broadcast.py --role STUD --body "..." --tags "release,ui"
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD


def main():
    p = argparse.ArgumentParser(description="Объявить broadcast всем ролям")
        # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать то, чего
    # механизм не умеет). Проверка готовности — ПРОГОН из чужого каталога.

    p.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    p.add_argument("--role", required=True, help="Кто объявляет (writer_role)")
    p.add_argument("--body", required=True, help="Текст объявления")
    p.add_argument("--tags", default="", help="Доп. теги через запятую (ALL добавляется всегда)")
    p.add_argument("--cta", action="store_true",
                   help="Call-to-action: priority=high + тег CTA (ждёт ACK ролей)")
    args = p.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта

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
