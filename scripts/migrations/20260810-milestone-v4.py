# -*- coding: utf-8 -*-
"""20260810-milestone-v4 — РУБЕЖ ВЕРСИИ СХЕМЫ v4 (карточка #89, шаг 5 — последний).

ПОВОД. Витрина версии отвечала «v3, сверх рубежа 8» — версия была объявлена не до конца
с 08.08. Рубеж НАРОЧНО объявляется ПОСЛЕДНИМ шагом сведения (перенесён из шага 1 плана):
рубеж, поставленный до конца работы, назавтра снова читается как «объявлено не до конца» —
ровно та ложь, от которой рубежи заводят.

Что вошло в v4 (шаги сверх рубежа v3, все в журнале с отпечатком и автором):
  20260807-addressed-by-unset · 20260808-rule-basis-and-cancel · 20260808-message-addressee ·
  20260808-backfill-addressee · 008-schema-journal-fingerprint · 008-phoenix-confirmed-at ·
  009-role-rights · 20260809-batch-race-lock · 20260810-schema-journal-applied-by ·
  20260810-role-lifecycle · 20260810-rule-status-field
  (список — иллюстрация на момент написания; ИСТИНУ спрашивай у журнала: он печатает сам)

Правки схемы здесь НЕТ — это запись-веха. Явный BEGIN всё равно обязателен: record_step
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
from schema_journal import record_step, verify, milestone_step_set  # noqa: E402

VERSION = "v4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    ver = conn.execute("SELECT * FROM schema_version").fetchone()
    print('=' * 78)
    print(f'20260810-milestone-v4{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    print(f'СЕЙЧАС выборка отвечает: версия {ver[0]} · шагов {ver[1]} · сверх отметки {ver[2]}')
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version='v4'").fetchone():
        print('✅ отметка версии v4 уже объявлена — делать нечего')
        return
    if ver[2] == 0:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: сверх отметки ноль шагов — объявлять нечего. '
                 'Рубеж без шагов — украшение.')

    # 🔴 ВТОРАЯ ЗАЩИТА — НАБОР, а не число (карточка #509). Прежняя строка выше ловит
    # пустой ХВОСТ и слепа к дырке В СЕРЕДИНЕ: «7 из 7» и «7 из 9» для счётчика одно
    # и то же. Найдено вторым потребителем нашего набора шагов (соседний контур AIA),
    # воспроизведено на копии: удалили рубеж и два шага из середины — веха объявила
    # версию молча. Отказ ПОИМЁННЫЙ: имя пропавшего шага дороже числа.
    набор = milestone_step_set(conn, __file__, VERSION)
    н, в = набор['window']
    print(f"набор под рубежом: окно {н or '(с начала)'}…{в} по датам имён · "
          f"предыдущий рубеж {набор['prev'] or '—'} · "
          f"ожидается шагов {len(набор['expected'])}")
    if набор['ambiguous']:
        print('⚠️ из сверки исключены неоднозначные хвосты имён: '
              + ', '.join(набор['ambiguous']))
    if набор['orphan']:
        print('⚠️ записаны в журнале, а файла в каталоге нет (замечание, НЕ отказ): '
              + ', '.join(набор['orphan']))
    if набор['missing']:
        print()
        print('⛔ НЕ ЗАПУСТИЛАСЬ: под рубежом не хватает шагов — '
              f"{len(набор['missing'])} из {len(набор['expected'])}:")
        for имя in набор['missing']:
            print(f'   🔴 {имя}')
        sys.exit('   Рубеж объявил бы версию, которой в базе нет. '
                 'Прогони недостающие шаги — или скажи вслух, почему их тут быть не должно.')
    print(f"✅ набор полон: все {len(набор['expected'])} шагов окна записаны в журнале")
    print(f'СТАНЕТ: версия v4 · сверх отметки 0 (отметка накрывает {ver[2]} шагов)')
    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута.')
        return

    conn.execute("BEGIN")
    fp = record_step(conn, VERSION,
                     "рубеж: версия v4 = адресат полем + основание правил + журнал с "
                     "отпечатком и автором + права роли + замок гонки + сведение с образцом "
                     "v-next (#89: lifecycle ролей, статус правил полем)")
    conn.commit()
    print(f'\n✅ ОБЪЯВЛЕНО. отпечаток: {fp}')
    ver2 = conn.execute("SELECT * FROM schema_version").fetchone()
    print(f'выборка теперь: версия {ver2[0]} · шагов {ver2[1]} · сверх отметки {ver2[2]}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')


if __name__ == '__main__':
    main()
