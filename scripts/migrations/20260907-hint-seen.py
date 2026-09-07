# -*- coding: utf-8 -*-
"""20260907-hint-seen — ОТМЕТКИ «ПОДСКАЗКА X ПОКАЗАНА РОЛИ R» (карточка #586).

ПРЕДМЕТ. Инструменты координации печатают общие пояснения (границы механизма, порядок
вызова, куда смотреть при отказе) КАЖДЫЙ РАЗ, при каждом вызове — одной и той же ролью,
без всякой пользы после первого раза: роль это уже прочитала. Длинный текст, знакомый
роли наизусть, — тот же класс шума, что и предупреждение без срока годности: он есть,
и его перестают читать, а вместе с ним — то новое, что стоит рядом.

ЧТО ДЕЛАЕТ ШАГ. Заводит таблицу `hint_seen` — по одной строке на пару (роль, ключ
подсказки): какой текст (по отпечатку) и когда показан. Помощник `mezo_hints.py`
(<КОНТУР>/.mezosync/scripts/mezo_hints.py) читает и пишет эту таблицу: подсказку,
которую роль уже видела недавно и текстом без изменений, печатает ОДНОЙ строкой-ссылкой
вместо полного текста; новую, изменившуюся или просроченную по возрасту — печатает
целиком и обновляет отметку.

⚖️ ГРАНИЦА: ЭТА ТАБЛИЦА НЕ РЕШАЕТ, какая подсказка обязательна, а какая нет, — это
решает вызывающий код. Она хранит только ФАКТ показа, а не право его пропустить.

Столбцы:
  role          — роль, которой показана подсказка (ВЕРХНИЙ регистр, как везде в контуре).
  hint_key      — ключ подсказки (свой у каждого места печати).
  content_hash  — отпечаток (sha1) показанного текста: сменился текст ⇒ показывать заново,
                  не полагаясь на то, что роль перечитает СТАРОЕ предупреждение как новое.
  shown_at      — час последнего полного показа, UTC ISO без смещения (как везде в контуре).
Первичный ключ (role, hint_key): у одной роли на один ключ — одна текущая отметка,
повторный показ ОБНОВЛЯЕТ её, а не копит историю (история показов здесь не нужна —
нужен только факт «видела/не видела»).
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

VERSION = "20260907-hint-seen"

ЗАПРОСЫ = (
    """CREATE TABLE hint_seen (
    role          TEXT NOT NULL,
    hint_key      TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    shown_at      TEXT NOT NULL,
    PRIMARY KEY (role, hint_key)
)""",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    db = os.path.abspath(a.db)
    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'📂 БАЗА: {db}')
    print('=' * 78)
    if not os.path.isfile(db):
        sys.exit(f'⛔ НЕ ЗАПУСТИЛСЯ: БД не найдена: {db}')

    conn = sqlite3.connect(db)
    есть = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'hint_seen' in есть:
        n = conn.execute("SELECT COUNT(*) FROM hint_seen").fetchone()[0]
        print(f'✅ уже сведено — таблица на месте, записей {n}. Делать нечего')
        return

    print('ТАБЛИЦЫ hint_seen ПОКА НЕТ — заведём: role · hint_key · content_hash · shown_at, '
          'первичный ключ (role, hint_key).')
    print('⚖️ Шаг ничего не заполняет: отметки появятся по мере вызовов mezo_hints.подсказка().')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    for запрос in ЗАПРОСЫ:
        conn.execute(запрос)
    fp = record_step(conn, VERSION,
                     "hint_seen: отметки «подсказка X показана роли R» (role, hint_key, "
                     "content_hash, shown_at; PK role+hint_key), чтобы общие пояснения "
                     "инструментов координации печатались роли один раз текстом, а при "
                     "повторных вызовах — строкой-ссылкой. Таблица хранит только ФАКТ "
                     "показа; что считать обязательным для печати — решает вызывающий код, "
                     "не эта таблица. Читает и пишет помощник mezo_hints.py. Карточка #586")
    conn.commit()
    print(f'\n✅ ПРИМЕНЕНО. отпечаток схемы: {fp}')


if __name__ == '__main__':
    main()
