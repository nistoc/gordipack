# -*- coding: utf-8 -*-
"""20260905-role-sessions — РЕЕСТР «РОЛЬ → АДРЕС СЕССИИ» для сигнала соседу
(карточка #564, подзадача #548; слово владельца 2026-09-05 17:54 UTC: «принимаю выбор
В1. ТОЛЬКО СИГНАЛ. Реализовываем его»).

ПРЕДМЕТ. Сообщение соседней сессии адресуется НЕ именем роли, а адресом сессии
(«atlas-dd [245891]»). Роль своего соседа по имени не найдёт: связь «роль → адрес»
не выводится ниоткуда — её кто-то должен записать.

⚡ ПОЧЕМУ У ЗАПИСИ ЕСТЬ СРОК ГОДНОСТИ, И ПОЧЕМУ ОН В САМОЙ СХЕМЕ. Адрес закрепляется
ПРИ РОЖДЕНИИ сессии и переименованием живого чата НЕ меняется (проба PROTO 05.09: заголовок
сменён на «atlas proto 09.05 проба имени», адрес остался «atlas-dd»). Значит адрес умирает
вместе с чатом — а строка о нём переживает чат и продолжает выглядеть свежей. Это класс,
за который контур уже платил: «производный факт лжёт первым, когда источник меняется»
(признак ④ стандарта перехода роли). Поэтому здесь ОБЯЗАТЕЛЬНЫ noted_at и noted_by:
читатель обязан видеть ЧАС записи и решать сам, а печатник — отказываться от старого адреса
вслух, а не подставлять его молча.

⚖️ ГРАНИЦЫ. Таблица НЕ доставляет и не отправляет: средство отправки доступно только роли,
скрипт может лишь напечатать готовый вызов. Она и не заменяет ленту: сигнал — звонок в дверь,
тело записки лежит в ленте (правило signal-not-carrier).

⚰️ КОГДА ОНА ОТОМРЁТ, сказано сразу, чтобы не жила вечно по инерции: у соседнего контура
адрес несёт имя роли («tapas coord 08.27»), потому что чат родился с именем. Как только все
чаты контура будут рождаться с именем вида «atlas <роль> <дата>», реестр станет лишним —
адрес будет читаться из имени. До тех пор он нужен: живые чаты переименованием не чинятся.
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

VERSION = "20260905-role-sessions"

ЗАПРОСЫ = (
    """CREATE TABLE role_sessions (
    role       TEXT PRIMARY KEY,          -- ВЕРХНИЙ регистр, как везде в контуре
    address    TEXT NOT NULL,             -- адрес доставки целиком: «atlas-dd [245891]»
    -- ⏰ Час записи и рука. БЕЗ них строка выглядит вечной, а адрес умирает вместе с чатом.
    noted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    noted_by   TEXT NOT NULL,
    -- ЧЕМ ДОБЫТ адрес: 'self' — роль назвала свой сама (единственный надёжный путь),
    -- 'listing' — взят из перечня сессий чужой рукой, 'owner' — сказан владельцем.
    source     TEXT NOT NULL DEFAULT 'self',
    note       TEXT
)""",
    "CREATE INDEX idx_role_sessions_noted ON role_sessions(noted_at)",
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
    таблицы = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'role_sessions' in таблицы:
        n = conn.execute("SELECT COUNT(*) FROM role_sessions").fetchone()[0]
        print(f'✅ уже сведено — таблица на месте, записей {n}. Делать нечего')
        return

    роли = conn.execute("SELECT COUNT(DISTINCT writer_role) FROM messages").fetchone()[0]
    print(f'РОЛЕЙ, писавших в ленту: {роли} · адресов записано будет: 0 (заполняет каждая роль сама)')
    print('⚖️ Шаг НИЧЕГО не заполняет: адрес своей сессии знает только сама роль, и придумать')
    print('   его за неё — значит завести правдоподобную ложь в место, куда смотрит печатник.')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    for запрос in ЗАПРОСЫ:
        conn.execute(запрос)
    fp = record_step(conn, VERSION,
                     "role_sessions: реестр «роль → адрес сессии» для сигнала соседу (вариант В1 "
                     "карточки #548, слово владельца 05.09 17:54 UTC). Адрес закрепляется при "
                     "рождении сессии и умирает вместе с чатом ⇒ noted_at/noted_by обязательны, "
                     "печатник отказывается от старого адреса вслух. Заполняет каждая роль сама: "
                     "свой адрес знает только она. Отомрёт, когда все чаты будут рождаться с именем "
                     "роли в адресе. Карточка #564")
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    print('👉 каждая роль первым ходом: python <КОНТУР>/vnext-tools/signal-templates.py '
          '--role <СВОЯ> --set-address "<адрес из перечня сессий>"')


if __name__ == '__main__':
    main()
