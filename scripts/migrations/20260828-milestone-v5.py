# -*- coding: utf-8 -*-
"""20260828-milestone-v5 — РУБЕЖ ВЕРСИИ СХЕМЫ v5 (план «Один пул», последний шаг — карточка #347).

ПОВОД. Витрина версии отвечала «v4 · сверх рубежа 7» — семь шагов жили без имени.
Рубеж НАРОЧНО объявляется ПОСЛЕДНИМ шагом работ (прецедент v4): рубеж, поставленный
до конца, назавтра снова читается как «объявлено не до конца».

Что накрывает v5 (истину спрашивай у журнала — он печатает сам; здесь иллюстрация):
  аренды инструментов (tool_leases) · умения ролей (role_skill) + их протухание полем ·
  мост сна к соседям · история версий памяти (phoenix_history) ·
  вердикты закрытия пула (track_verdicts) + скиллы пула (tracks.skills).
Смысл имени: «ОДИН ПУЛ НА ВЕСЬ КОНТУР» — пулы живые (план · вердикты · паёк),
статус роли пишется тем же вызовом, память с историей и порогом объёма.

Правки схемы здесь НЕТ — это запись-веха. Явный BEGIN обязателен: record_step
отказывает вне транзакции, и это его контракт, а не формальность.
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
from schema_journal import record_step, verify  # noqa: E402

VERSION = "v5"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    ver = conn.execute("SELECT * FROM schema_version").fetchone()
    print('=' * 78)
    print(f'20260828-milestone-v5{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    print(f'СЕЙЧАС выборка отвечает: версия {ver[0]} · шагов {ver[1]} · сверх отметки {ver[2]}')
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version='v5'").fetchone():
        print('✅ отметка версии v5 уже объявлена — делать нечего')
        return
    if ver[2] == 0:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: сверх отметки ноль шагов — объявлять нечего. '
                 'Рубеж без шагов — украшение.')
    print(f'СТАНЕТ: версия v5 · сверх отметки 0 (отметка накрывает {ver[2]} шагов)')
    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута.')
        return

    conn.execute("BEGIN")
    fp = record_step(conn, VERSION,
                     "рубеж: версия v5 = один пул на весь контур — треки живые "
                     "(вердикты закрытия + скиллы пула + паёк), статус роли тем же "
                     "вызовом, аренды инструментов, умения ролей с протуханием полем, "
                     "память с историей версий и порогом объёма, мост сна к соседям")
    conn.commit()
    print(f'\n✅ ОБЪЯВЛЕНО. отпечаток: {fp}')
    ver2 = conn.execute("SELECT * FROM schema_version").fetchone()
    print(f'выборка теперь: версия {ver2[0]} · шагов {ver2[1]} · сверх отметки {ver2[2]}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')


if __name__ == '__main__':
    main()
