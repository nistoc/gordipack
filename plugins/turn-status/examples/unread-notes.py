# -*- coding: utf-8 -*-
"""Одна строка о состоянии общего журнала записей: сколько не прочитано и давно ли.

Зачем: правило «регулярно сверяйся с журналом» роль забывает, потому что вспоминать
о нём нужно ровно тогда, когда занят другим. Число, приходящее в каждый ход само,
заменяет правило, которое надо помнить.

Запуск (обычно его делает не человек, а расширение turn-status перед ходом):
  python onto-archs/tools/unread-notes.py --session-id local_<идентификатор чата>
  python onto-archs/tools/unread-notes.py --role COORD --explain

Что печатает: ровно одну строку или ничего. Молчит, когда сказать нечего:
непрочитанных нет, базы нет, база занята писателем. Ничего не пишет: соединение
открывается только на чтение.

Коды возврата:
  0 — напечатана строка ИЛИ сказать нечего (обычная работа);
  3 — база есть, но устроена не так, как ожидалось (нет таблицы или колонки).
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(HERE)), '.mezosync', 'mezosync.db')
READER = 'python C:/github/.onto/.mezosync/scripts/read-messages.py --role %s'
REGISTER = ('python C:/github/.onto/.mezosync/scripts/signal-templates.py '
            '--role <ТВОЯ РОЛЬ> --set-address "<твой адрес>" --session-id %s')


def notes_word(n):
    """Склонение: 1 непрочитанная записка, 2 непрочитанные записки, 5 непрочитанных записок."""
    if 11 <= (n % 100) <= 14:
        return 'непрочитанных записок'
    tail = n % 10
    if tail == 1:
        return 'непрочитанная записка'
    if tail in (2, 3, 4):
        return 'непрочитанные записки'
    return 'непрочитанных записок'


def age(minutes):
    """Возраст отметки словами, без склоняемых сокращений."""
    if minutes < 1:
        return 'меньше минуты'
    if minutes < 60:
        return '%d мин' % minutes
    hours, rest = divmod(minutes, 60)
    if hours < 24:
        return '%d ч' % hours if rest == 0 else '%d ч %02d мин' % (hours, rest)
    days, rest_h = divmod(hours, 24)
    return '%d сут' % days if rest_h == 0 else '%d сут %d ч' % (days, rest_h)


def normalize(value):
    value = (value or '').strip().lower()
    if value.startswith('local_'):
        value = value[len('local_'):]
    return value


def connect(db):
    """Только чтение: обычное соединение молча создало бы пустую базу на месте опечатки."""
    uri = 'file:%s?mode=ro' % Path(db).as_posix()
    con = sqlite3.connect(uri, uri=True, timeout=0.5)
    con.execute('PRAGMA busy_timeout=400')
    return con


def role_by_session(con, session_id):
    want = normalize(session_id)
    if not want:
        return None
    found = [r[0] for r in con.execute(
        'SELECT role, session_id FROM role_sessions WHERE session_id IS NOT NULL')
        if normalize(r[1]) == want]
    return found[0] if len(found) == 1 else None


def measure(con, role):
    row = con.execute(
        'SELECT last_read_id, updated_at FROM read_cursors WHERE reader_role = ?',
        (role,)).fetchone()
    last_read, marked_at = (row[0], row[1]) if row else (0, None)
    unread = con.execute(
        'SELECT COUNT(*) FROM messages WHERE id > ?', (last_read,)).fetchone()[0]
    others = con.execute(
        'SELECT COUNT(*) FROM messages WHERE id > ? AND writer_role <> ?',
        (last_read, role)).fetchone()[0]
    return unread, others, marked_at


def minutes_since(marked_at):
    if not marked_at:
        return None
    try:
        then = datetime.strptime(marked_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, int((datetime.now(timezone.utc) - then).total_seconds() // 60))


def main():
    ap = argparse.ArgumentParser(
        description='Строка о непрочитанных записках общего журнала для роли этого чата')
    ap.add_argument('--session-id', help='идентификатор чата; принимает и local_<uuid>, и голый uuid')
    ap.add_argument('--role', help='назвать роль прямо, минуя опознание по чату')
    ap.add_argument('--db', default=DEFAULT_DB, help='файл базы контура')
    ap.add_argument('--min', type=int, default=1, dest='minimum',
                    help='молчать, пока непрочитанных меньше этого числа')
    ap.add_argument('--explain', action='store_true',
                    help='сказать вслух, почему вышло молчание')
    args = ap.parse_args()

    def explain(why):
        if args.explain:
            sys.stderr.write(why + '\n')
        return 0

    if not os.path.exists(args.db):
        return explain('базы контура нет по пути %s — это дерево не контурное' % args.db)

    try:
        con = connect(args.db)
    except sqlite3.Error as err:
        return explain('база не открылась на чтение: %s' % err)

    try:
        role = (args.role or '').upper() or role_by_session(con, args.session_id)
    except sqlite3.OperationalError as err:
        sys.stderr.write('реестр ролей читается не так, как ожидалось: %s\n' % err)
        return 3

    if not role:
        # Молчание тут неотличимо от «всё прочитано», поэтому чат говорит о себе сам.
        print('Этот чат не записан в реестр ролей, поэтому счёт непрочитанных записок '
              'для него не ведётся. Если это чат роли — запиши себя: %s'
              % (REGISTER % (args.session_id or '<local_идентификатор этого чата>')))
        return 0

    try:
        unread, others, marked_at = measure(con, role)
    except sqlite3.OperationalError as err:
        if 'locked' in str(err) or 'busy' in str(err):
            return explain('база занята писателем, пропускаем один ход')
        sys.stderr.write('база устроена не так, как ожидалось: %s\n' % err)
        return 3

    if unread < args.minimum:
        return explain('непрочитанных %d при пороге %d — говорить не о чем' % (unread, args.minimum))

    mark = minutes_since(marked_at)
    parts = ['Общий журнал записей: %d %s' % (unread, notes_word(unread)),
             ' (из них чужих %d)' % others]
    if mark is None:
        parts.append(', отметки прочитанного ещё нет')
    else:
        parts.append(', отметка прочитанного не двигалась %s' % age(mark))
    parts.append(' — прочитать: %s' % (READER % role))
    print(''.join(parts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
