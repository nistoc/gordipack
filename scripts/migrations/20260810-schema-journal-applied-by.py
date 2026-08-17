# -*- coding: utf-8 -*-
"""20260810-schema-journal-applied-by — ЧЕМ ПРИМЕНЁН ШАГ СХЕМЫ (карточка #89, шаг 1).

ПОВОД. Сверка образца схемы v-next с живой базой (замер 2026-08-10 07:39 UTC): образец
знает `applied_by`, живая — нет. При ДВУХ руках в базе (PROTO и COORD) «кто внёс шаг» —
первое, что спрашивают, когда схема разошлась с ожиданием.

ЧТО ДЕЛАЕТ
  ① добавляет колонку `applied_by` (идемпотентно, через schema_journal.ensure_column);
  ② ВОССТАНАВЛИВАЕТ автора у уже записанных шагов — но только там, где это ФАКТ:
     файл-мигратор, объявляющий ровно эту версию, найден на диске. Не найден — остаётся
     пусто. Честное «не знаю» лучше правдоподобной догадки;
  ③ записывает себя в журнал (record_step) — в той же транзакции, что и правка схемы.

🪤 КАРТА «ШАГ → ЧЕМ ПРИМЕНЁН» НЕ ПИШЕТСЯ РУКОЙ — ОНА ВЫВОДИТСЯ ЗАМЕРОМ.
   Рукописный список я снял в карточке #156 ровно потому, что он протухает молча и
   расходится с диском. Здесь версия ищется в текстах самих файлов миграций: объявление
   `VERSION = "..."` или `record_step(conn, "...")`. Что диск не подтверждает — то пусто.

⚠️ ВОССТАНОВЛЕННОЕ ПОМЕЧАЕТСЯ СЛОВОМ «(восстановлено)». Значение, выведенное задним
   числом, и значение, записанное в момент шага, — разные по силе, и разница обязана
   быть видна в самих данных, а не в чьей-то памяти. Тот же приём, что `addressed_by`.
"""
import argparse
import glob
import io
import os
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import ensure_column, record_step, verify  # noqa: E402

VERSION = "20260810-schema-journal-applied-by"

# Где ищем файлы, наносившие шаги. Пути ВЫВОДЯТСЯ от расположения скрипта — впечатанный
# путь машины автора уже стрелял в чужой копии (грабля ② слепка PROTO, 10.08).
SEARCH_DIRS = [
    os.path.join(HERE, '*.py'),
    os.path.join(SCRIPTS, '*.py'),
    r'C:\github\gordipack\vnext\prototype\*.py',
]
DECL = re.compile(r'(?:VERSION\s*=\s*|record_step\s*\(\s*\w+\s*,\s*|MILESTONE\s*=\s*'
                  r'|STEP\d+\s*=\s*)["\']([^"\']+)["\']')


def build_map():
    """→ {версия: (имя файла, чем доказано)}. Строится ЧТЕНИЕМ ДИСКА, не памятью.

    ДВА ОСНОВАНИЯ, И ОНИ РАЗЛИЧАЮТСЯ В САМОМ ЗНАЧЕНИИ:
      ① «объявление» — файл сам называет эту версию в тексте. Сильное основание;
      ② «имя файла»  — версия совпадает с именем файла миграции. Слабее, но это ФАКТ
         диска, а не догадка.

    🪤 ПОЧЕМУ ВТОРОЕ ОСНОВАНИЕ ВООБЩЕ ПОНАДОБИЛОСЬ — и почему нельзя было пойти простым
       путём. Четыре шага (20260807-addressed-by-unset и три соседних) СТАРШЕ самого
       журнала: в него их вписал ЗАДНИМ ЧИСЛОМ файл-восстановитель из своего списка.
       Взять автора оттуда — значит записать восстановителя автором шага, которого он
       не наносил. «Кто записал в журнал» и «чем применён шаг» — разные факты, и слипшись
       они соврали бы уверенно: подпись стои́т, выглядит достоверно, проверять некому.
    """
    found = {}
    for pattern in SEARCH_DIRS:
        for path in glob.glob(pattern):
            name = os.path.basename(path)
            if name == os.path.basename(__file__):
                continue
            try:
                text = open(path, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for ver in DECL.findall(text):
                found.setdefault(ver, (name, 'объявление в файле'))
    # ② второй проход — слабее, поэтому НЕ перебивает уже найденное объявлением
    for pattern in SEARCH_DIRS:
        for path in glob.glob(pattern):
            name = os.path.basename(path)
            found.setdefault(name[:-3], (name, 'имя файла'))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true',
                    help='ничего не менять; напечатать РОВНО то, что было бы сделано')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    have = {r[1] for r in conn.execute("PRAGMA table_info(schema_migrations)")}
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY rowid").fetchall()
    known = build_map()

    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    print(f'колонка applied_by: {"уже есть" if "applied_by" in have else "БУДЕТ ДОБАВЛЕНА"}')
    print(f'версий объявлено в файлах на диске: {len(known)}')
    print(f'\nШАГОВ В ЖУРНАЛЕ: {len(rows)}')

    plan, unknown = [], []
    for (ver,) in rows:
        hit = known.get(ver)
        if hit:
            name, basis = hit
            plan.append((ver, f'tool:{name} (восстановлено: {basis})'))
            print(f'   ✅ {ver:42s} → tool:{name}  ⟨{basis}⟩')
        else:
            unknown.append(ver)
            print(f'   ⬜ {ver:42s} → ПУСТО (диск не подтверждает — не выдумываем)')

    print(f'\nвосстановим у {len(plan)} · оставим пустыми {len(unknown)}')
    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")            # явная транзакция — требование record_step
    ensure_column(conn)
    for ver, value in plan:
        conn.execute("UPDATE schema_migrations SET applied_by=? WHERE version=?",
                     (value, ver))
    fp = record_step(conn, VERSION,
                     "журнал схемы: applied_by — чем применён шаг; восстановлено замером "
                     "по диску, недоказуемое оставлено пустым", by='PROTO')
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')


if __name__ == '__main__':
    main()
