# -*- coding: utf-8 -*-
"""20260905-messages-archive — АРХИВНАЯ ТАБЛИЦА ЛЕНТЫ ПО ВОЗРАСТУ + общий вид с третьим источником
(карточка #538, шаг ③ регламента сжатия; слово владельца 2026-09-05 06:02 UTC «делаем C …
неразрушительно»; слово COORD по правилу history-compression-policy v2 — записка #4855,
2026-09-05 15:38 UTC: «возражений по правилу нет: отдельная таблица архива — буква правила»).

ПРЕДМЕТ. Живая лента `messages`: 3420 записок на 2026-09-05 14:44 UTC, из них старше 7 суток —
2759 (81 %). Правило велит переносить записки старше срока в АРХИВНУЮ таблицу, не удаляя
ни байта, и только когда доказано, что ссылка «#N» разрешается в архив у ВСЕХ читателей.

⚡ ПОЧЕМУ НЕ `messages_history`. Она уже есть, но это ДРУГОЙ предмет: ретро-импорт разметки
02–12.07 (1428 записок, id 523..1950, вынесен split-history-table.py после аварии 16.07),
и id там не хронологичны. Смешав два предмета, мы получили бы место, где «перенесено по
возрасту» неотличимо от «импортировано», а обратимость (раздел ④ правила) проверять нечем.

ЧТО ДЕЛАЕТ ШАГ
  · заводит `messages_archive` — те же поля, что у `messages` (id ПРЕЖНИЙ: ссылка «#N»
    не протухает от переноса), + moved_at · moved_by · rule (ключ И редакция правила —
    просьба COORD Ⓐ: «час переживает цитату», редакция правила сменится, а строка останется);
  · пересоздаёт вид `messages_all` = live ∪ history ∪ ARCHIVE — семь читателей вида получают
    архив без правки;
  · печатает отпечаток вывода вида ДО и ПОСЛЕ: пока архив пуст, вид обязан отдавать РОВНО
    то же (самый дешёвый встречный случай, названный COORD);
  · записывает себя в журнал схемы.

⛔ ЧЕГО НЕ ДЕЛАЕТ: ничего не переносит. Перенос — отдельный инструмент (messages-fold.py),
и он появится только после того, как все читатели номера переведены на mezo_refs.resolve
и прогнаны на копии с перенесёнными записками (правило v2, раздел ①).

⚠️ message_addressee ссылается на messages(id) внешним ключом. SQLite не проверяет внешние
ключи, пока их не включат PRAGMA'ой; в инструментах ленты PRAGMA foreign_keys не включается
(проверено 05.09: ни в одном из 62 читателей), поэтому строки адресатов у перенесённой записки
остаются на месте и читаются как прежде. Инструмент переноса обязан это перепроверить на копии.
"""
import argparse
import hashlib
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import record_step  # noqa: E402

VERSION = "20260905-messages-archive"

ВИД = """CREATE VIEW messages_all AS
    SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, 'live'    AS source FROM messages
    UNION ALL
    SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, 'history' AS source FROM messages_history
    UNION ALL
    SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, 'archive' AS source FROM messages_archive"""

# ⚡ Схема — СПИСОК запросов, не один текст (оплачено шагом 20260904-phoenix-archive).
ЗАПРОСЫ = (
    """CREATE TABLE messages_archive (
    -- id ТОТ ЖЕ, что был в messages: ссылка «#N» разрешается в архив под прежним номером.
    id           INTEGER PRIMARY KEY,
    writer_role  TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    body_md      TEXT NOT NULL,
    tags         TEXT DEFAULT '[]',
    priority     TEXT DEFAULT 'normal',
    resolved     INTEGER DEFAULT 0,
    broadcast    INTEGER NOT NULL DEFAULT 0,
    addressed_by TEXT NOT NULL DEFAULT 'unset',
    -- ЧТО ДОБАВЛЯЕТ ПЕРЕНОС: когда, чьей рукой и по какому правилу (КЛЮЧ И РЕДАКЦИЯ) унесено.
    moved_at     TEXT NOT NULL DEFAULT (datetime('now')),
    moved_by     TEXT NOT NULL,
    rule         TEXT NOT NULL
)""",
    "CREATE INDEX idx_messages_archive_ts ON messages_archive(timestamp)",
    "CREATE INDEX idx_messages_archive_role ON messages_archive(writer_role, timestamp)",
    "DROP VIEW IF EXISTS messages_all",
    ВИД,
)


def отпечаток_вида(conn) -> str:
    h = hashlib.sha256()
    for row in conn.execute("SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, source "
                            "FROM messages_all ORDER BY source, id"):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()[:16]


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
    таблицы = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    виды = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    if 'messages' not in таблицы or 'messages_history' not in таблицы:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: нет messages / messages_history — этот шаг стои́т на них')
    вид_знает_архив = False
    if 'messages_all' in виды:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='messages_all'").fetchone()[0]
        вид_знает_архив = 'messages_archive' in sql
    if 'messages_archive' in таблицы and вид_знает_архив:
        print('✅ уже сведено (таблица и вид на месте) — делать нечего')
        return
    if 'messages_archive' in таблицы and not вид_знает_архив:
        sys.exit('⛔ ПОЛОВИНА ШАГА НА МЕСТЕ: таблица есть, вид без архива — разбирать рукой, '
                 'не досоздавать молча')

    n, старых = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN timestamp < datetime('now','-7 days') THEN 1 ELSE 0 END) "
        "FROM messages").fetchone()
    ист = conn.execute("SELECT COUNT(*) FROM messages_history").fetchone()[0]
    до = отпечаток_вида(conn) if 'messages_all' in виды else '(вида не было)'
    print('ЛЕНТА СЕЙЧАС — замер ДО:')
    print(f'   живых {n} · старше 7 суток {старых} · ретро-импорт (messages_history) {ист}')
    print(f'   отпечаток вида messages_all ДО: {до}')
    print('⚖️ Шаг ничего не переносит: после него лента ровно та же, архив пуст, вид отдаёт то же.')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    # 🪤 НЕ executescript — он делает неявный коммит и рвёт транзакцию (оплачено 04.09).
    for запрос in ЗАПРОСЫ:
        conn.execute(запрос)
    после = отпечаток_вида(conn)
    if до != '(вида не было)' and после != до:
        conn.rollback()
        sys.exit(f'⛔ ОТКАЧЕНО: вид после применения отдаёт ДРУГОЕ при пустом архиве ({до} → {после}) — '
                 'схема вида расходится с прежней, разбирать рукой')
    fp = record_step(conn, VERSION,
                     "messages_archive: архив ленты по возрасту ОТДЕЛЬНОЙ таблицей (те же поля + "
                     "moved_at · moved_by · rule «ключ vN», id прежний) и вид messages_all = live ∪ "
                     "history ∪ archive. messages_history — ретро-импорт 02–12.07, другой предмет, "
                     "не смешивать (слово COORD по правилу v2, записка #4855). Ничего не переносит; "
                     "перенос — messages-fold.py после перевода всех читателей номера на "
                     f"mezo_refs.resolve. Карточка #538 шаг ③. Замер ДО: живых {n}, старше 7 суток "
                     f"{старых}, ретро-импорт {ист}; отпечаток вида до/после {до} = {после}")
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp} · отпечаток вида ПОСЛЕ: {после} (совпал с ДО)')


if __name__ == '__main__':
    main()
