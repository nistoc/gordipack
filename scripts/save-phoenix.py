"""
save-phoenix.py — CLI для агента: сохранить phoenix-слепок в mezosync.db.

Использование:
    python save-phoenix.py --db .mezosync/mezosync.db --role COORD --section state --body "текст слепка"
    python save-phoenix.py --db .mezosync/mezosync.db --role COORD --section state --file phoenix-state.md
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Сохранить phoenix-слепок")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--role", required=True, help="Роль (COORD, CORE, ...)")
    parser.add_argument("--section", required=True,
                        choices=["identity", "state", "plan", "history"],
                        help="Секция слепка")
    parser.add_argument("--body", default=None, help="Текст слепка (или --file)")
    parser.add_argument("--file", default=None, help="Файл с текстом слепка")
    args = parser.parse_args()

    if not args.body and not args.file:
        print("ERR: укажите --body или --file", file=sys.stderr)
        sys.exit(1)

    body = args.body if args.body else Path(args.file).read_text(encoding="utf-8")

    conn = sqlite3.connect(str(args.db), timeout=5)
    conn.execute("""
        INSERT INTO phoenix (role, section, body, saved_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(role, section) DO UPDATE SET body = excluded.body, saved_at = excluded.saved_at
    """, (args.role, args.section, body))

    conn.execute("""
        INSERT INTO audit_log (actor_role, action, target, diff_md)
        VALUES (?, 'save_phoenix', ?, ?)
    """, (args.role, f"phoenix.{args.role}.{args.section}", f"Updated {args.section} ({len(body)} chars)"))

    conn.commit()
    conn.close()
    print(f"OK phoenix/{args.role}/{args.section} ({len(body)} chars)")


if __name__ == "__main__":
    main()
