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
    # launcher/rebirth/sources добавлены 2026-07-16: замер показал, что МЕХАНИЗМУ
    # ВОСКРЕШЕНИЯ РОЛИ НЕГДЕ ЖИТЬ В БД. У COORD/CORE/ING/STUD launcher'а в БД не было
    # ВООБЩЕ; у TAXO/RCC/EYE/GRF он попал в `identity` СЛУЧАЙНО, прозой. При этом сам
    # текст launcher'а звучит «Прочитай ...\phoenix.<роль>.md и начни работать по нему»
    # — то есть УКАЗЫВАЕТ НА md. Отключи md на Фазе 4 — и владелец вставит эту строку в
    # новый чат, а роль прочитает пустоту. МОЛЧА. Сломался бы ровно тот инструмент,
    # которым чинят всё остальное.
    # Схема правки НЕ требует: phoenix.section — свободный TEXT, ограничение жило
    # только здесь, в choices.
    #   launcher — одна строка, которую владелец копирует в новый чат роли
    #   rebirth  — что роль делает ПЕРВЫМ делом, проснувшись (порядок чтения, границы)
    #   sources  — источники правды роли в порядке чтения
    parser.add_argument("--section", required=True,
                        choices=["identity", "state", "plan", "history",
                                 "launcher", "rebirth", "sources"],
                        help="Секция слепка")
    parser.add_argument("--body", default=None, help="Текст слепка (или --file)")
    parser.add_argument("--file", default=None, help="Файл с текстом слепка")
    args = parser.parse_args()

    if not args.body and not args.file:
        print("ERR: укажите --body или --file", file=sys.stderr)
        sys.exit(1)

    body = args.body if args.body else Path(args.file).read_text(encoding="utf-8")

    # Регистр роли нормализуется ЗДЕСЬ ТОЖЕ. read-messages и read-phoenix уже приводят
    # роль к UPPER; save-phoenix — НЕТ, и это «расщепление роли»: слепок, сохранённый как
    # «core», не находится читателем, ищущим «CORE» (phoenix.role — часть PRIMARY KEY без
    # COLLATE NOCASE, тот же класс, что 8 lowercase-курсоров-призраков EYE #2063).
    # Нормализуем на входе — один регистр во всём контуре.
    role = args.role.upper()

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{args.db}?mode=rw", uri=True, timeout=5)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")
    conn.execute("""
        INSERT INTO phoenix (role, section, body, saved_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(role, section) DO UPDATE SET body = excluded.body, saved_at = excluded.saved_at
    """, (role, args.section, body))

    conn.execute("""
        INSERT INTO audit_log (actor_role, action, target, diff_md)
        VALUES (?, 'save_phoenix', ?, ?)
    """, (role, f"phoenix.{role}.{args.section}", f"Updated {args.section} ({len(body)} chars)"))

    conn.commit()
    conn.close()
    print(f"OK phoenix/{role}/{args.section} ({len(body)} chars)")


if __name__ == "__main__":
    main()
