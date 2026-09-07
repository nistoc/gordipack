# -*- coding: utf-8 -*-
"""20260907-milestone-v6 — ОТМЕТКА ВЕРСИИ СХЕМЫ v6 («память роли ищется, а не читается целиком»).

ПОВОД. Слово владельца 2026-09-07 17:42 UTC, чат PROTO, дословно: «v6 для пакета» — ответ
на вопрос, вынесенный COORD (документ обновления UPGRADE-v5-to-2026-09-07.md говорил:
«Отметка версии v6 НЕ объявлена — решение владельца»). Выборка версии отвечала
«v5 · сверх отметки 11» — одиннадцать шагов жили без имени.
Отметка НАРОЧНО объявляется ПОСЛЕДНИМ шагом работ (прецедент v4, v5): поставленная до конца,
она назавтра снова читается как «объявлено не до конца».

Что накрывает v6 (истину спрашивай у журнала — он печатает сам; здесь иллюстрация):
  архив памяти роли отдельной таблицей (phoenix_archive) · память записями с полями
  (phoenix_records + autoincrement) + автопересборка при сохранении · полнотекстовый поиск
  по записям (phoenix_records_fts) · история версий памяти в архив (phoenix_history_archive)
  · архив ленты по возрасту (messages_archive) · реестр адресов сессий (role_sessions) ·
  ожидания занятого инструмента (lease waits) · доставка правил до подсказок полем
  (rule-skill-delivery) · подсказки один раз (hint_seen) · рецензент карточки (backlog reviewer).
Смысл имени: «ПАМЯТЬ ИЩЕТСЯ, НЕ ЧИТАЕТСЯ ЦЕЛИКОМ» — роль спрашивает свою память словами
(find-phoenix.py) вместо чтения 90–120 тыс. знаков за пробуждение.

Правки схемы здесь НЕТ — это запись-веха. Явный BEGIN обязателен: record_step
отказывает вне транзакции, и это его контракт, а не формальность.
Имена в коде — по-английски (слово владельца 07.09 15:47/15:57 UTC), комментарии — по-русски.
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
from schema_journal import record_step, verify, milestone_step_set  # noqa: E402

VERSION = "v6"
STEP_NAME = "20260907-milestone-v6"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    ver = conn.execute("SELECT * FROM schema_version").fetchone()
    print('=' * 78)
    print(f'{STEP_NAME}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    print(f'СЕЙЧАС выборка отвечает: версия {ver[0]} · шагов {ver[1]} · сверх отметки {ver[2]}')
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone():
        print(f'✅ отметка версии {VERSION} уже объявлена — делать нечего')
        return
    if ver[2] == 0:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: сверх отметки ноль шагов — объявлять нечего. '
                 'Отметка без шагов — украшение.')

    # 🔴 ВТОРАЯ ЗАЩИТА — НАБОР, а не число (карточка #509): счётчик слеп к дырке В СЕРЕДИНЕ.
    # Отказ ПОИМЁННЫЙ: имя пропавшего шага дороже числа.
    step_set = milestone_step_set(conn, __file__, VERSION)
    lo, hi = step_set['window']
    print(f"набор под отметкой: окно {lo or '(с начала)'}…{hi} по датам имён · "
          f"предыдущая отметка {step_set['prev'] or '—'} · "
          f"ожидается шагов {len(step_set['expected'])}")
    if step_set['ambiguous']:
        print('⚠️ хвост имени встречается у ДВУХ файлов (сверены по полному имени, из сверки '
              'НЕ исключены): ' + ', '.join(step_set['ambiguous']))
    if step_set['orphan']:
        print('⚠️ записаны в журнале, а файла в каталоге нет (замечание, НЕ отказ): '
              + ', '.join(step_set['orphan']))
    if step_set['missing']:
        print()
        print('⛔ НЕ ЗАПУСТИЛАСЬ: под отметкой не хватает шагов — '
              f"{len(step_set['missing'])} из {len(step_set['expected'])}:")
        for name in step_set['missing']:
            print(f'   🔴 {name}')
        sys.exit('   Отметка объявила бы версию, которой в базе нет. '
                 'Прогони недостающие шаги — или скажи вслух, почему их тут быть не должно.')
    print(f"✅ набор полон: все {len(step_set['expected'])} шагов окна записаны в журнале")
    print(f'СТАНЕТ: версия {VERSION} · сверх отметки 0 (отметка накрывает {ver[2]} шагов)')
    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута.')
        return

    conn.execute("BEGIN")
    fp = record_step(conn, VERSION,
                     "отметка версии v6 = память роли ищется, а не читается целиком — "
                     "архив памяти отдельной таблицей, записи с полями и автопересборка "
                     "при сохранении, полнотекстовый поиск по записям, история версий памяти "
                     "в архив, архив ленты по возрасту, реестр адресов сессий, ожидания "
                     "занятого инструмента, доставка правил до подсказок полем, подсказки "
                     "один раз, рецензент карточки (слово владельца 2026-09-07 17:42 UTC)")
    conn.commit()
    print(f'\n✅ ОБЪЯВЛЕНО. отпечаток: {fp}')
    ver2 = conn.execute("SELECT * FROM schema_version").fetchone()
    print(f'выборка теперь: версия {ver2[0]} · шагов {ver2[1]} · сверх отметки {ver2[2]}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')


if __name__ == '__main__':
    main()
