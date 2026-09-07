# -*- coding: utf-8 -*-
"""20260907-phoenix-records-fts — ПОЛНОТЕКСТОВЫЙ ПОИСК ПО ЗАПИСЯМ ПАМЯТИ (карточка #525,
часть А, пункт 1 плана).

ПРЕДМЕТ. У `phoenix_records` (шаг 20260904-phoenix-records, поля — карточка #524) уже есть
предмет, раздел и живость, но НЕТ способа найти запись ПО ТЕКСТУ тела и заголовка иначе,
чем прочитать все записи подряд. Роль, которой нужно «что уже известно про права доступа»,
вынуждена читать всё тело памяти целиком — ровно ту беду, ради которой заводились сами
`phoenix_records` (карточка #524, пункт ①: «владелец не может посмотреть, что в памяти
лежит»). Полнотекстовый поиск закрывает её для текста: `MATCH '"права"'` вместо чтения
двадцати тысяч знаков.

ЧТО ДЕЛАЕТ ШАГ. Заводит виртуальную таблицу `phoenix_records_fts` (движок FTS5) над полями
`subject` и `body`, и три триггера, которые держат её в согласии с `phoenix_records` при
любой записи.

ПОЧЕМУ ВНЕШНЕЕ СОДЕРЖИМОЕ (`content='phoenix_records'`) И ТРИГГЕРЫ, А НЕ ОБЫЧНАЯ ТАБЛИЦА
СО СВОИМ ТЕКСТОМ. Инструмент, который позже будет разбирать тело памяти на записи (в задании
он назван `memory-records.py`), пишет ГОЛЫМИ операторами `INSERT`/`UPDATE`/`DELETE` в саму
`phoenix_records` — без всякого понятия об индексе поиска. Если бы индекс хранил текст сам
по себе, каждое место, что пишет в `phoenix_records`, была бы обязано ЗНАТЬ о нём и обновлять
его отдельным вызовом — а забытое место тихо расходится с правдой (ровно тот класс, за
который контур уже платил не раз: производное, требующее «не забыть», умирает первым).
Внешнее содержимое снимает это требование ПОСТРОЕНИЕМ: `content_rowid='id'` говорит FTS5
не хранить текст у себя, а тянуть его из `phoenix_records` по `id`, а три триггера
(после INSERT/UPDATE/DELETE) обновляют индекс САМИ, на уровне базы — их видит любой
писатель, даже тот, что о существовании индекса не подозревает.

ПОЧЕМУ REBUILD В КОНЦЕ ЭТОГО ЖЕ ШАГА. Триггеры ловят запись, случившуюся ПОСЛЕ их
заведения. Строки, уже лежащие в `phoenix_records` на момент этого шага, ни один триггер
не увидит — команда `INSERT INTO phoenix_records_fts(phoenix_records_fts) VALUES('rebuild')`
наполняет индекс из них один раз, синхронно с созданием таблиц и триггеров, в той же
проводке. Без неё индекс завёлся бы пустым, а первое чтение сочло бы память моложе, чем
она есть.

⚖️ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: индекс покрывает ТОЛЬКО `subject` и `body`. Отбор по роли,
разделу, живости и часу — по-прежнему обычными столбцами `phoenix_records` (у них уже есть
указатели из шага 20260904-phoenix-records); эта таблица ничего в них не меняет и не
дублирует.

Регистр и раскладка: `tokenize='unicode61 remove_diacritics 2'` сворачивает регистр и
у кириллицы, и у латиницы — слово, записанное как «COORD», находится запросом строчными
буквами, и наоборот.
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

VERSION = "20260907-phoenix-records-fts"

# ⚡ СПИСОК ЗАПРОСОВ, А НЕ ОДИН ТЕКСТ С «;»: разделителя тут нет вовсе — границы заданы
# самим списком (тот же приём, что и в 20260904-phoenix-records — точка с запятой внутри
# CREATE TRIGGER…BEGIN…END сама по себе не разделитель ОПЕРАТОРОВ, но резать текст руками
# по ней всё равно не стоит, раз есть способ обойтись без резки вообще).
OBJECTS = ('phoenix_records_fts', 'phoenix_records_ai', 'phoenix_records_ad', 'phoenix_records_au')

QUERIES = (
    """CREATE VIRTUAL TABLE phoenix_records_fts USING fts5(
    subject, body,
    content='phoenix_records', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
)""",
    """CREATE TRIGGER phoenix_records_ai AFTER INSERT ON phoenix_records BEGIN
  INSERT INTO phoenix_records_fts(rowid, subject, body) VALUES (new.id, new.subject, new.body);
END""",
    """CREATE TRIGGER phoenix_records_ad AFTER DELETE ON phoenix_records BEGIN
  INSERT INTO phoenix_records_fts(phoenix_records_fts, rowid, subject, body) VALUES ('delete', old.id, old.subject, old.body);
END""",
    """CREATE TRIGGER phoenix_records_au AFTER UPDATE ON phoenix_records BEGIN
  INSERT INTO phoenix_records_fts(phoenix_records_fts, rowid, subject, body) VALUES ('delete', old.id, old.subject, old.body);
  INSERT INTO phoenix_records_fts(rowid, subject, body) VALUES (new.id, new.subject, new.body);
END""",
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
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'phoenix_records' not in tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы phoenix_records нет — сначала шаг '
                  '20260904-phoenix-records.py (заводит таблицу; следом по потребности '
                  '20260904-phoenix-records-autoincrement.py). Шаг ничего не менял.')

    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','trigger') AND name IN "
        f"({','.join('?' * len(OBJECTS))})", OBJECTS)}

    if existing == set(OBJECTS):
        n1 = conn.execute("SELECT COUNT(*) FROM phoenix_records").fetchone()[0]
        n2 = conn.execute("SELECT COUNT(*) FROM phoenix_records_fts").fetchone()[0]
        print(f'✅ уже сведено — индекс phoenix_records_fts и все три триггера на месте: '
              f'записей {n1} · в индексе {n2}. Делать нечего')
        return
    if existing:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: часть объектов индекса уже есть, часть — нет (похоже на '
                  f'прерванный прогон): на месте {sorted(existing)}, не хватает '
                  f'{sorted(set(OBJECTS) - existing)}. Разберись рукой, шаг не угадывает.')

    n0 = conn.execute("SELECT COUNT(*) FROM phoenix_records").fetchone()[0]
    print(f'записей в phoenix_records сейчас: {n0}')
    print('⚖️ Заводим phoenix_records_fts (FTS5, внешнее содержимое над phoenix_records) и три')
    print('   триггера (после INSERT/UPDATE/DELETE), затем ОДИН раз наполняем индекс командой')
    print('   rebuild — из строк, уже лежащих в таблице. Само тело phoenix_records не трогается.')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.isolation_level = None
    conn.execute("BEGIN")
    try:
        for query in QUERIES:
            conn.execute(query)
        conn.execute("INSERT INTO phoenix_records_fts(phoenix_records_fts) VALUES('rebuild')")
        fp = record_step(conn, VERSION,
                          "phoenix_records_fts: полнотекстовый индекс FTS5 (внешнее содержимое "
                          "content=phoenix_records, content_rowid=id, tokenize=unicode61 "
                          "remove_diacritics 2) над полями subject и body таблицы phoenix_records; "
                          "три триггера (после INSERT/UPDATE/DELETE) держат индекс в согласии "
                          "с любым способом записи в phoenix_records — включая будущий разбор "
                          "тела памяти на записи голыми операторами, который об индексе знать "
                          "не обязан. Индекс наполнен из уже лежавших строк командой rebuild "
                          f"в той же проводке. Записей на момент шага: {n0}. Карточка #525, "
                          "часть А, пункт 1")
        conn.execute("COMMIT")
    except sqlite3.Error as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        sys.exit(f'🔴 ОТКАТ по ошибке базы: {e}')

    print(f'\n✅ ПРИМЕНЕНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print('целостность:', conn.execute("PRAGMA integrity_check").fetchone()[0])
    n1 = conn.execute("SELECT COUNT(*) FROM phoenix_records").fetchone()[0]
    n2 = conn.execute("SELECT COUNT(*) FROM phoenix_records_fts").fetchone()[0]
    print(f'контрольное чтение: записей в phoenix_records {n1} · записей в индексе {n2}'
          + (' — совпало' if n1 == n2 else ' — 🔴 НЕ СОВПАЛО, разберись рукой'))


if __name__ == '__main__':
    main()
