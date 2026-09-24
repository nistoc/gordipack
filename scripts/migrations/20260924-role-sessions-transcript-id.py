# -*- coding: utf-8 -*-
"""20260924-role-sessions-transcript-id — ОПОЗНАНИЕ РОЛИ ПО ЗАПИСИ РАЗГОВОРА в role_sessions
(карточка #649, замер PROTO 24.09 09:22 UTC).

ПРЕДМЕТ. У строки роли в role_sessions уже есть ДВА идентификатора чата:
  · address (шаг 20260905-role-sessions.py) — короткое имя «atlas-56 [b4ca03]», человеку
    легко читается, но умирает при возобновлении чата (новое возобновление — новый разговор
    для интерфейса, у него другой короткий адрес).
  · session_id (шаг 20260913-role-sessions-session-id.py) — стойкий «local_…», переживает
    возобновление, ДОСТАВЛЯЕТ сообщения (mcp__ccd_session_mgmt__send_message(session_id=…)).
Обоим есть общий потребитель, которого у контура не было: хук, получающий на входе
ТОЛЬКО имя файла записи разговора (`~/.claude/projects/<проект>/<cliSessionId>.jsonl`) —
это ДРУГОЕ значение, чем session_id (в хранилище сессий приложения оно лежит полем
`cliSessionId`, рядом с `sessionId` = наш session_id). Хук не может опознать по нему роль,
пока это значение нигде не записано.

ЧТО ДЕЛАЕТ ШАГ: добавляет НЕОБЯЗАТЕЛЬНУЮ колонку role_sessions.transcript_id (адрес
по-прежнему NOT NULL — первая запись строки всё ещё требует --set-address; transcript_id
заполняется ОТДЕЛЬНО, автоматически, сверкой с хранилищем сессий приложения — см. правку
signal-templates.py той же карточки) и такую же колонку в role_sessions_history (она несёт
строку ЦЕЛИКОМ на момент перезаписи, по образцу столбца session_id того же шага 20260913).

⚖️ ДВА ИДЕНТИФИКАТОРА, ДВА РАЗНЫХ ДЕЛА — не дублирование:
    session_id ..... ДОСТАВКА сообщений соседней роли (send_message(session_id=…))
    transcript_id ... ОПОЗНАНИЕ роли ХУКОМ по имени файла записи разговора, которое хук
                      получает на входе КАК session_id своего вызова — то же слово,
                      другой предмет; путать их значит доставлять не туда или опознавать
                      не то.
Оба значения СЕГОДНЯ живут в одной записи хранилища сессий приложения (`sessionId` и
`cliSessionId` рядом), но записываются в role_sessions РАЗНЫМИ путями: session_id — по
слову роли о себе (--session-id), transcript_id — сверкой, автоматически, инструмент
не спрашивает его явно ни у кого (см. правку signal-templates.py карточки #649).

ИДЕМПОТЕНТНА: если обе колонки уже на месте — «уже сведено», выхода нет.
Требует шаг 20260913-role-sessions-session-id.py (без role_sessions_history и её колонки
session_id — переносить исторический снимок transcript_id уже некуда).
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

VERSION = "20260924-role-sessions-transcript-id"

STATEMENTS = (
    "ALTER TABLE role_sessions ADD COLUMN transcript_id TEXT",
    "ALTER TABLE role_sessions_history ADD COLUMN transcript_id TEXT",
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
    if 'role_sessions_history' not in tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы role_sessions_history нет — сначала шаг '
                 '20260913-role-sessions-session-id.py')

    columns = {r[1] for r in conn.execute("PRAGMA table_info(role_sessions)")}
    history_columns = {r[1] for r in conn.execute("PRAGMA table_info(role_sessions_history)")}
    column_ready = 'transcript_id' in columns
    history_column_ready = 'transcript_id' in history_columns
    if column_ready and history_column_ready:
        print('✅ уже сведено — колонка transcript_id есть и в role_sessions, и в '
              'role_sessions_history. Делать нечего')
        return

    role_count = conn.execute("SELECT COUNT(*) FROM role_sessions").fetchone()[0]
    print(f'РОЛЕЙ в реестре сейчас: {role_count} · transcript_id у них пока НЕТ (колонка новая)')
    print('⚖️ Шаг НИЧЕГО не заполняет: значение приходит СВЕРКОЙ с хранилищем сессий '
          'приложения (signal-templates.py --session-id/--set-address, карточка #649), '
          'не вводом руками.')

    if args.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    if not column_ready:
        conn.execute(STATEMENTS[0])
    if not history_column_ready:
        conn.execute(STATEMENTS[1])
    fp = record_step(conn, VERSION,
                     "role_sessions.transcript_id (имя файла записи разговора, каким его "
                     "получает хук на входе как session_id своего вызова — ОПОЗНАНИЕ роли, "
                     "не путать с role_sessions.session_id, которым доставляются сообщения) "
                     "+ такая же колонка в role_sessions_history. Карточка #649, замер PROTO "
                     "2026-09-24 09:22 UTC")
    conn.commit()
    print(f'\n✅ ПРИМЕНЕНО. отпечаток схемы: {fp}')
    print('👉 значение заполняется автоматически сверкой с хранилищем сессий приложения: '
          'python <КОНТУР>/vnext-tools/signal-templates.py --role <СВОЯ> '
          '--session-id "local_…" --source self')


if __name__ == '__main__':
    main()
