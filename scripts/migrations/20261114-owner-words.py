# -*- coding: utf-8 -*-
"""20261114-owner-words — ХРАНИЛИЩЕ СЛОВ ВЛАДЕЛЬЦА: у дословной речи появляется НОМЕР
(карточка #554, часть ① «СХЕМА»).

ПРЕДМЕТ. Правило `history-compression-policy` (замок владельца) велит перед сносом файла
записи разговора ВЫЖАТЬ из него дословную речь владельца — но адреса у выжимки нет.
Замер по карточке: в базе координации не было ни одной таблицы под слова владельца
(искали по именам owner/word/quote); сводки ленты ложатся в саму ленту, старые версии
памяти — в phoenix_archive, а выжимке речи владельца лечь НЕКУДА. Следствие: пока
хранилища нет, правило запрещает сносить файлы вовсе.
🩸 Цена уже заплачена и это не гипотеза: ДВА слова владельца, на которых стои́т работа
роли STUD, утрачены сжатием разговора (30.08 ≈09:47 и 04.09 ≈20:35 UTC) — сплошной обход
620 файлов находит на их месте только пересказы.

ЧТО ДЕЛАЕТ ШАГ. Заводит таблицу `owner_words`: у каждого слова владельца есть номер,
час UTC, чат, ДОСЛОВНЫЙ текст, ссылка на файл-источник с номером строки, чем перемерено
и кто услышал. Три указателя — по часу, по чату и по роли, услышавшей слово.

🔑 ПОЧЕМУ ДОСЛОВНЫЙ ТЕКСТ И ПОЯСНЕНИЕ — РАЗНЫЕ ПОЛЯ, А НЕ ОДНО. Предмет хранилища —
дословность, а не смысл (критерий карточки, пункт ③: пересказ вместо дословного текста
не проходит). Одно поле на оба назначения сделало бы пересказ неотличимым от речи
СРЕДСТВАМИ БАЗЫ: читающий видел бы текст и не знал, цитата это или чьё-то изложение.
Поэтому `text_verbatim` несёт ТОЛЬКО то, что сказано, а всё объяснение роли — в `note`,
и смешать их нельзя даже по небрежности.

🔑 ПОЧЕМУ ПОЛЕ `verified_by` ОБЯЗАТЕЛЬНО, А НЕ ЖЕЛАТЕЛЬНО. Дословность, подтверждённая
обещанием роли, не подтверждена ничем: роль, записывающая слово по памяти, искренне
уверена, что цитирует. Поле требует НАЗВАТЬ, чем сверено — исход и час прогона
`find-owner-word.py`, который ищет текст в самих записях разговоров. Инструмент записи
(часть ② карточки) без такой сверки запись не делает; схема держит требование на уровне
базы, чтобы обойти его было нельзя и голым оператором INSERT.
⚖️ Чего это НЕ доказывает, названо вслух: сверка подтверждает, что текст В ЗАПИСИ ЕСТЬ.
Что он принадлежит владельцу, а не вставлен в его реплику цитатой, она не доказывает —
это различает сам `find-owner-word.py` своими исходами (набрано текстом · выбрано кнопкой ·
свой текст в поле «другое»), и его исход ложится в то же поле.

ПОЧЕМУ УНИКАЛЬНОСТЬ ПО ТРОЙКЕ (чат · час · текст), А НЕ ПО ТЕКСТУ. Владелец говорит одно
и то же слово в разных чатах и в разные часы — и это РАЗНЫЕ слова с разной областью
действия (правило `word-carries-its-scope`: у слова есть область, и она не подразумевается).
Уникальность по одному тексту слила бы их в одно и стёрла бы ровно то, что различает
приказ, сказанный одной роли, от общего.

⚖️ ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ, ЧТОБЫ ШАГ НЕ ПРОЧЛИ ШИРЕ СКАЗАННОГО:
  · полнотекстового индекса шаг НЕ заводит: слов владельца сотни, не десятки тысяч, и поиск
    по тексту здесь обходится обычным отбором. Индекс нужен там, где перечисление дорого, —
    заводить его «на будущее» значит кормить вторую правду о том же тексте;
  · шаг ничего НЕ удаляет и не предлагает удалять: хранилище заводится ДО того, как хоть
    один файл записи разговора будет предложен к сносу;
  · таблица хранит ТОЛЬКО слова владельца. Это не перенос ленты и не замена карточек.

Карточка #554 · родитель #538 · трек TRACK-ROLES-REMEMBER · зона PROTO, рука COORD по слову
владельца 2026-11-14 15:52 UTC (чат COORD, дословно: «Делай #554»).
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

VERSION = "20261114-owner-words"

OBJECTS = ('owner_words', 'owner_words_said_at', 'owner_words_chat', 'owner_words_heard_by')

QUERIES = (
    """CREATE TABLE owner_words (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    said_at        TEXT    NOT NULL,
    chat           TEXT    NOT NULL,
    text_verbatim  TEXT    NOT NULL CHECK (length(trim(text_verbatim)) > 0),
    source_file    TEXT,
    source_line    INTEGER,
    verified_by    TEXT    NOT NULL CHECK (length(trim(verified_by)) > 0),
    heard_by       TEXT    NOT NULL,
    noted_at       TEXT    NOT NULL,
    note           TEXT,
    UNIQUE (chat, said_at, text_verbatim)
)""",
    "CREATE INDEX owner_words_said_at ON owner_words (said_at)",
    "CREATE INDEX owner_words_chat ON owner_words (chat)",
    "CREATE INDEX owner_words_heard_by ON owner_words (heard_by)",
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
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index') AND name IN "
        f"({','.join('?' * len(OBJECTS))})", OBJECTS)}

    # ⚡ ПОВТОРНЫЙ ПРОГОН НЕ ПОРТИТ ДАННЫХ И НЕ ВРЁТ: «всё на месте» — довод делать нечего,
    # «часть на месте» — ОТКАЗ, а не достройка. Шаг, достраивающий половину прерванного
    # прогона, тем самым решает за человека, какая половина верна (правило о шаге схемы,
    # записывающем себя).
    if existing == set(OBJECTS):
        n = conn.execute("SELECT COUNT(*) FROM owner_words").fetchone()[0]
        print(f'✅ уже сведено — таблица owner_words и все три указателя на месте: '
              f'слов владельца записано {n}. Делать нечего')
        return
    if existing:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: часть объектов уже есть, часть — нет (похоже на '
                 f'прерванный прогон): на месте {sorted(existing)}, не хватает '
                 f'{sorted(set(OBJECTS) - existing)}. Разберись рукой, шаг не угадывает.')

    print('⚖️ Заводим таблицу owner_words (номер · час UTC · чат · ДОСЛОВНЫЙ текст ·')
    print('   файл-источник и строка · чем сверено · кто услышал · когда записано · пояснение)')
    print('   и три указателя: по часу, по чату, по услышавшей роли.')
    print('   Дословный текст и пояснение — РАЗНЫЕ поля: иначе пересказ неотличим от речи.')
    print('   Поле «чем сверено» обязательно: дословность по обещанию роли не подтверждена ничем.')
    print('   Ни одна существующая таблица не трогается, ничего не удаляется.')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.isolation_level = None
    conn.execute("BEGIN")
    try:
        for query in QUERIES:
            conn.execute(query)
        fp = record_step(conn, VERSION,
                         "owner_words: хранилище слов владельца — номер (id), час UTC (said_at), "
                         "чат (chat), ДОСЛОВНЫЙ текст (text_verbatim, непустой по CHECK), "
                         "файл-источник и строка (source_file, source_line), чем сверена "
                         "дословность (verified_by, непустое по CHECK — исход и час прогона "
                         "find-owner-word.py по записям разговоров), кто услышал (heard_by), "
                         "когда записано (noted_at), пояснение роли (note — ОТДЕЛЬНО от "
                         "дословного текста, чтобы пересказ не был неотличим от речи). "
                         "Уникальность по тройке чат+час+текст: одно и то же слово в разных "
                         "чатах и часах — РАЗНЫЕ слова с разной областью действия. Три "
                         "указателя: said_at, chat, heard_by. Полнотекстового индекса нет "
                         "намеренно (слов сотни, отбор по тексту дешёв). Карточка #554, "
                         "часть ①; слово владельца 2026-11-14 15:52 UTC, чат COORD")
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
    cols = [r[1] for r in conn.execute("PRAGMA table_info(owner_words)")]
    idx = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='owner_words' "
        "AND name NOT LIKE 'sqlite_%'"))
    print(f'контрольное чтение: поля {cols}')
    print(f'                    указатели {idx}')
    print(f'                    слов записано {conn.execute("SELECT COUNT(*) FROM owner_words").fetchone()[0]}')


if __name__ == '__main__':
    main()
