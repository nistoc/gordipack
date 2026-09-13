# -*- coding: utf-8 -*-
"""20260913-role-rights-revoked-by — КОЛОНКА revoked_by В role_rights
(карточка B из пятёрки правок AIA, слово владельца 2026-09-13 10:07 UTC: «Сначала правка,
потом tapas»).

ПРЕДМЕТ. `role-rights.py revoke` записывал `revoked_at` и `revoked_why`, но НЕ записывал,
ЧЬЕЙ рукой отозвано. Найдено контуром AIA и подтверждено в нашем коде: отозвать чужое право
могла ЛЮБАЯ роль, назвав чужой `--id` — отзыв не проверял ни руку, ни владельца записи.
Тот же класс, за который уже платили у `amend` (правка без руки неотличима от «так и было»):
здесь без руки отзыв неотличим от анонимного вмешательства в чужое разрешение.

ЧТО ДЕЛАЕТ ШАГ: добавляет НЕОБЯЗАТЕЛЬНУЮ колонку role_rights.revoked_by (TEXT). Существующие
отозванные записи ЭТИМ ШАГОМ не заполняются — восстанавливать заднюю руку по памяти значило
бы завести правдоподобную, а не настоящую подпись; отсутствие в старых записях остаётся
честно пустым.

ИДЕМПОТЕНТНА: колонка уже есть — «уже сведено», выхода нет.
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
from schema_journal import record_step  # noqa: E402

VERSION = "20260913-role-rights-revoked-by"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    db = os.path.abspath(args.db)
    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if args.dry_run else ""}')
    print(f'📂 БАЗА: {db}')
    print('=' * 78)
    if not os.path.isfile(db):
        sys.exit(f'⛔ НЕ ЗАПУСТИЛСЯ: БД не найдена: {db}')

    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'role_rights' not in tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы role_rights нет — сначала шаг '
                 '20260808-role-rights.py')

    columns = {r[1] for r in conn.execute("PRAGMA table_info(role_rights)")}
    if 'revoked_by' in columns:
        n = conn.execute("SELECT COUNT(*) FROM role_rights WHERE revoked_at IS NOT NULL"
                         ).fetchone()[0]
        print(f'✅ уже сведено — колонка revoked_by на месте, отозванных записей {n} '
              f'(руку старых шаг не восстанавливает). Делать нечего')
        return

    revoked_without_actor = conn.execute(
        "SELECT COUNT(*) FROM role_rights WHERE revoked_at IS NOT NULL").fetchone()[0]
    print(f'ЗАПИСЕЙ, УЖЕ ОТОЗВАННЫХ БЕЗ РУКИ: {revoked_without_actor} — шаг колонку добавит, '
          f'но их НЕ ЗАПОЛНИТ (задняя подпись была бы правдоподобной, а не настоящей)')

    if args.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    conn.execute("ALTER TABLE role_rights ADD COLUMN revoked_by TEXT")
    fp = record_step(conn, VERSION,
                     "role_rights.revoked_by: чья рука отозвала право. Найдено контуром "
                     "AIA — revoke не проверял владельца записи и не писал руку; отзывать "
                     "теперь вправе роль-владелец либо координатор ЯВНО (--foreign), "
                     "--by обязателен, как у amend. Старые отозванные записи не заполнены "
                     "(рука не восстанавливается по памяти). AIA-правка B, слово владельца "
                     "2026-09-13 10:07 UTC")
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')


if __name__ == '__main__':
    main()
