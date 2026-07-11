"""
init-group.py — Создаёт новую группу агентов (mezosync.db) по шаблону.

Использование:
    python init-group.py --name "atlas" --path "C:\\guts\\.atlas\\.mezosync" --domain data-platform
    python init-group.py --name "webapp" --path "C:\\projects\\app\\.mezosync" --domain frontend-spa
"""

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMA_FILE = REPO_ROOT / "schema" / "mezosync_v1.sql"
UNIVERSAL_RULES = REPO_ROOT / "rules" / "universal.sql"
DOMAIN_RULES_DIR = REPO_ROOT / "rules" / "domain-specific"


def main():
    parser = argparse.ArgumentParser(description="Инициализация новой группы агентов Горди")
    parser.add_argument("--name", required=True, help="Имя группы (например: atlas, webapp)")
    parser.add_argument("--path", required=True, help="Путь к директории .mezosync")
    parser.add_argument("--domain", default=None,
                        help="Доменный пресет правил (data-platform, frontend-spa)")
    parser.add_argument("--roles", nargs="+", default=["coord"],
                        help="Роли для инициализации курсоров (по умолчанию: coord)")
    args = parser.parse_args()

    mezosync_dir = Path(args.path)
    mezosync_dir.mkdir(parents=True, exist_ok=True)
    db_path = mezosync_dir / "mezosync.db"

    if db_path.exists():
        print(f"⚠️  БД уже существует: {db_path}")
        resp = input("Перезаписать? (y/N): ").strip().lower()
        if resp != "y":
            print("Отмена.")
            sys.exit(0)
        db_path.unlink()

    print(f"📦 Создаю {db_path}...")
    conn = sqlite3.connect(str(db_path))

    # 1. Схема
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    print("  ✅ Схема v1 применена")

    # 2. Имя группы
    conn.execute("UPDATE meta SET value = ? WHERE key = 'group_name'", (args.name,))

    # 3. Универсальные правила
    rules_sql = UNIVERSAL_RULES.read_text(encoding="utf-8")
    conn.executescript(rules_sql)
    print("  ✅ Универсальные правила загружены")

    # 4. Доменные правила
    if args.domain:
        domain_file = DOMAIN_RULES_DIR / f"{args.domain}.sql"
        if domain_file.exists():
            domain_sql = domain_file.read_text(encoding="utf-8")
            conn.executescript(domain_sql)
            print(f"  ✅ Доменные правила [{args.domain}] загружены")
        else:
            print(f"  ⚠️  Доменный пресет '{args.domain}' не найден, пропускаю")

    # 5. Курсоры для ролей
    for role in args.roles:
        conn.execute(
            "INSERT OR IGNORE INTO read_cursors (reader_role, last_read_id) VALUES (?, 0)",
            (role,)
        )
    print(f"  ✅ Курсоры: {', '.join(args.roles)}")

    conn.commit()
    conn.close()
    print(f"\n🎉 Группа «{args.name}» готова: {db_path}")
    print(f"   Следующий шаг: запустить COORD с launcher-промптом из templates/coord.md")


if __name__ == "__main__":
    main()
