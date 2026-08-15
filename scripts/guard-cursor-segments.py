# -*- coding: utf-8 -*-
"""guard-cursor-segments — УЧЁТ ОТРЕЗКОВ ПИТАЕТСЯ, а не стои́т засеянным и мёртвым.

ПОВОД (замер @PROTO 2026-08-11 20:09 UTC, карточка #193). Шаг схемы `003-cursor-segments`
раскатали в живую базу 06.08: девять строк, по одной на роль. И ПЯТЬ СУТОК в таблицу
не писал ни один инструмент — счёт грепом по живым скриптам дал ноль.
🎯 Класс: **сосуд заведён, засеян и не питается.** Он выглядит живым (таблица есть, строки
есть, шаг миграции записан честно) и отвечает данными дня посева. Пустой сосуд заметили бы:
его молчание видно. Засеянный-и-мёртвый отвечает уверенно и неверно.

⚖️ ПОЭТОМУ СУДИМ НЕ «ЕСТЬ ЛИ СТРОКИ», А СХОДИТСЯ ЛИ УЧЁТ С ЖИЗНЬЮ: у каждой роли отметка
прочитанного обязана быть ПОКРЫТА отрезками. Проверка на непустоту была бы зелёной все пять
суток, пока сосуд стоял мёртвым, — она и есть тот дефект, который здесь ловится.

⚠️ ЧЕГО ГАРД НЕ ЛОВИТ, И ЭТО НАЗВАНО ВСЛУХ:
  · правдивость основания у отрезков вида 'declared' — это слово роли, проверить нечем;
  · что отрезок 'read' поставлен за ДЕЙСТВИТЕЛЬНО прочитанное: гард видит учёт, а не глаза;
  · роли, у которой нет отметки вовсе (не заведена) — ей нечего покрывать, она не судится.
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(os.path.dirname(HERE), 'mezosync.db')


def uncovered(conn, role, cursor):
    """Непокрытые участки роли ниже её отметки. Дыра ищется С ОБОИХ КОНЦОВ.

    🪤 Первая редакция миграции искала только хвост (от верха отрезков до отметки) и
    пропускала дыру В СЕРЕДИНЕ — у ролей, подтвердивших чтение уже после врезки питания,
    свежий отрезок наверху уводил «верх» за провал. Поймано чтением напечатанных чисел.
    """
    segs = conn.execute("SELECT from_id, to_id FROM cursor_segments WHERE role = ?"
                        " ORDER BY from_id", (role,)).fetchall()
    holes, pos = [], 1
    for lo, hi in segs:
        if lo > pos:
            top = min(lo - 1, cursor)
            if top >= pos:
                holes.append((pos, top))
        pos = max(pos, hi + 1)
    if cursor >= pos:
        holes.append((pos, cursor))
    return holes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=DEFAULT_DB)
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f'⛔ НЕ ЗАПУСТИЛСЯ: базы нет по пути {a.db}')
        return 2
    conn = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'cursor_segments' not in tables:
        # ⚖️ ТРЕТИЙ ИСХОД, А НЕ ЗЕЛЁНЫЙ: таблицы нет — судить нечем. Молчаливое «чисто»
        # здесь было бы ровно той неправдой, ради которой гард и написан.
        print('⛔ НЕ ЗАПУСТИЛСЯ: в базе нет cursor_segments — учёт отрезков не раскатан. '
              'Это НЕ «всё хорошо», это «проверять нечего».')
        return 2

    rows = conn.execute("SELECT reader_role, last_read_id FROM read_cursors "
                        "ORDER BY reader_role").fetchall()
    bad, total_holes = [], 0
    for role, cur in rows:
        holes = uncovered(conn, role, cur)
        if holes:
            n = sum(hi - lo + 1 for lo, hi in holes)
            total_holes += n
            bad.append((role, cur, holes, n))

    if bad:
        print(f'⛔ УЧЁТ ОТСТАЁТ ОТ ЖИЗНИ: у {len(bad)} ролей из {len(rows)} отметка '
              f'не покрыта отрезками ({total_holes} записок)')
        for role, cur, holes, n in bad:
            куски = ' · '.join(f'{lo}..{hi}' for lo, hi in holes[:4])
            print(f'   {role:8} отметка #{cur} · без записи {n}: {куски}'
                  f'{" …" if len(holes) > 4 else ""}')
        print('   ⇒ Значит либо кто-то двигает отметку мимо подтверждения чтения, либо '
              'питание учёта сломано.\n'
              '     Витрина «что до роли не дошло» с такими дырами отвечает неверно '
              'и уверенно.')
        return 1

    покрыто = conn.execute("SELECT COUNT(*) FROM cursor_segments").fetchone()[0]
    print(f'✅ учёт отрезков сходится с отметками у всех {len(rows)} ролей '
          f'(отрезков {покрыто})')
    print('   ⚖️ проверено ПОКРЫТИЕ, а не правдивость: основание у заявленных участков — '
          'слово роли, и гард его не судит')
    return 0


if __name__ == '__main__':
    sys.exit(main())
