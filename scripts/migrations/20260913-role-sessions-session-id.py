# -*- coding: utf-8 -*-
"""20260913-role-sessions-session-id — СТОЙКИЙ ИДЕНТИФИКАТОР СЕССИИ в role_sessions
(карточка A из пятёрки правок AIA, слово владельца 2026-09-13 10:07 UTC: «Сначала правка,
потом tapas»).

ПРЕДМЕТ. Адрес вида «atlas-56 [b4ca03]» (шаг 20260905-role-sessions.py) умирает при
ВОЗОБНОВЛЕНИИ чата: новое возобновление — новый разговор для интерфейса, у него другой
короткий адрес, а строка реестра продолжает выглядеть свежей. Стойкий идентификатор
«local_…» переживает возобновление: его принимает mcp__ccd_session_mgmt__send_message
(session_id=…), а сама сессия узнаёт его вызовом mcp__ccd_session_mgmt__get_session("self")
→ sessionId. Это ДРУГОЙ адрес, не замена короткому: короткий человеку читается легче
(«atlas-56 [b4ca03]»), стойкий переживает возобновление, но не выводится из имени и
не гадается — как и короткий, он ЗАПИСЫВАЕТСЯ ролью о себе самой.

ЧТО ДЕЛАЕТ ШАГ:
  ① добавляет НЕОБЯЗАТЕЛЬНУЮ колонку role_sessions.session_id (адрес по-прежнему NOT NULL —
     первая запись строки всё ещё требует --set-address; session_id добавляется тем же
     вызовом или отдельно, ОБНОВЛЯЯ уже существующую строку роли).
  ② заводит role_sessions_history — прежняя строка ролью НЕ ТЕРЯЕТСЯ при перезаписи.

⚖️ ПОЧЕМУ ИСТОРИЯ — ОТДЕЛЬНАЯ ТАБЛИЦА, А НЕ ПОЛЕ-ЖУРНАЛ (JSON в самой строке).
В контуре это уже устоявшийся приём для «перезаписываемых» реестров: у записок — пара
messages/messages_history (+ VIEW messages_all), у слепка памяти — phoenix/phoenix_history.
Отдельная таблица даёт то же самое, чего JSON-поле не даёт БЕСПЛАТНО:
    · читается запросом (WHERE role=…) без разбора текста;
    · растёт без верхней границы размера строки;
    · не требует читателю role_sessions знать формат поля-журнала, которого до сих пор
      в этой таблице не было ни у одного столбца.
Поле-журнал было бы ЧЕТВЁРТЫМ способом хранить историю рядом с уже двумя примерами —
третий разъехавшийся формат дороже, чем следование образцу.

СТОЛБЦЫ role_sessions_history — снимок строки ДО перезаписи плюс когда и кем перезаписана:
  role, address, session_id, noted_at, noted_by, source, note — прежние значения;
  superseded_at — час перезаписи (запросом к БД, не подсказкой среды);
  superseded_by — noted_by НОВОЙ строки (кто перезаписал).

ИДЕМПОТЕНТНА: если колонка и таблица уже на месте — «уже сведено», выхода нет.
Требует шаг 20260905-role-sessions.py (без role_sessions мигрировать нечего).
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

VERSION = "20260913-role-sessions-session-id"

STATEMENTS = (
    "ALTER TABLE role_sessions ADD COLUMN session_id TEXT",
    """CREATE TABLE role_sessions_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    role           TEXT NOT NULL,
    address        TEXT,
    session_id     TEXT,
    noted_at       TEXT,
    noted_by       TEXT,
    source         TEXT,
    note           TEXT,
    -- когда и кем ПЕРЕЗАПИСАНА эта прежняя строка (не когда она сама была записана —
    -- это уже несут noted_at/noted_by выше, скопированные как были).
    superseded_at  TEXT NOT NULL DEFAULT (datetime('now')),
    superseded_by  TEXT
)""",
    "CREATE INDEX idx_role_sessions_history_role ON role_sessions_history(role)",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    db = os.path.abspath(args.db)
    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if args.dry_run else ""}')
    print(f'📂 БАЗА: {db}')
    print('=' * 78)
    if not os.path.isfile(db):
        sys.exit(f'⛔ НЕ ЗАПУСТИЛСЯ: БД не найдена: {db}')

    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'role_sessions' not in tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы role_sessions нет — сначала шаг '
                 '20260905-role-sessions.py')

    columns = {r[1] for r in conn.execute("PRAGMA table_info(role_sessions)")}
    column_ready = 'session_id' in columns
    history_ready = 'role_sessions_history' in tables
    if column_ready and history_ready:
        n = conn.execute("SELECT COUNT(*) FROM role_sessions_history").fetchone()[0]
        print(f'✅ уже сведено — колонка session_id и таблица истории на месте, '
              f'записей истории {n}. Делать нечего')
        return

    role_count = conn.execute("SELECT COUNT(*) FROM role_sessions").fetchone()[0]
    print(f'РОЛЕЙ в реестре сейчас: {role_count} · session_id у них пока НЕТ (колонка новая, '
          f'заполнит каждая роль сама)')
    print('⚖️ Шаг НИЧЕГО не заполняет: свой session_id знает только сама роль '
          '(mcp__ccd_session_mgmt__get_session("self")).')

    if args.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    if not column_ready:
        conn.execute(STATEMENTS[0])
    if not history_ready:
        conn.execute(STATEMENTS[1])
        conn.execute(STATEMENTS[2])
    fp = record_step(conn, VERSION,
                     "role_sessions.session_id (стойкий идентификатор сессии, переживает "
                     "возобновление чата — принимает mcp__ccd_session_mgmt__send_message) "
                     "+ role_sessions_history (прежняя строка не теряется при перезаписи, "
                     "по образцу messages/messages_history и phoenix/phoenix_history). "
                     "AIA-правка A, слово владельца 2026-09-13 10:07 UTC")
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    print('👉 записать стойкий id: python <КОНТУР>/vnext-tools/signal-templates.py '
          '--role <СВОЯ> --session-id "local_…" --source self')


if __name__ == '__main__':
    main()
