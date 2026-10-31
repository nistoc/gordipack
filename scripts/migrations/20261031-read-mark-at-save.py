# -*- coding: utf-8 -*-
"""20261031-read-mark-at-save — СНИМОК ОТМЕТКИ ПРОЧИТАННОГО ПРИ СОХРАНЕНИИ ПАМЯТИ
(карточка #466, пункт ①, третий круг; план — комментарий карточки 2026-10-31 10:08 UTC).

ЧТО ДЕЛАЕТ ШАГ: заводит три таблицы модуля scripts/read_mark.py и засевает их.
  phoenix_read_marks .. снимок отметки прочитанного, записанный вместе с разделом state
                        (how: save · confirm · same-body · seed)
  chat_seen ........... какие чаты роли уже сверены с лентой; новый чат = строки нет
  read_batch_voids .... выдачи ленты, погашенные возвратом отметки: их ключ отклоняется
                        с исполнимым выходом, а не молча
Существующие таблицы не меняются.

ПОСЕВ (один раз, при применении):
  · снимок роли: час = последний СВОЙ ход по разделу state — saved_at, если последнюю запись
    тела сделала сама роль (иначе час её последней записи по audit_log), и не раньше её
    последнего своего confirm по audit_log (решение ⑤ первого круга: confirmed_at сдвигает
    и чужая рука пересохранением того же текста);
    число = MAX(to_id) только тех отрезков cursor_segments, что ДВИГАЛИ отметку (kind='declared',
    kind='born' или kind='read' без основания), с часом СТРОГО раньше; не выше текущей отметки. Отрезки
    «тело показано отбором --to-me» отметку не двигали и в посев не входят;
  · известные чаты: номера из role_sessions и role_sessions_history — живые чаты ролей при
    применении новыми не считаются.

ИДЕМПОТЕНТЕН: все три таблицы на месте — «уже сведено», выхода нет. --dry-run ничего не пишет.
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

VERSION = "20261031-read-mark-at-save"

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS phoenix_read_marks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        role       TEXT NOT NULL,
        at         TEXT NOT NULL,
        read_mark  INTEGER NOT NULL,
        how        TEXT NOT NULL CHECK (how IN ('save', 'confirm', 'same-body', 'seed')),
        chat_id    TEXT,
        actor      TEXT,
        noted_at   TEXT NOT NULL DEFAULT (datetime('now')))""",
    "CREATE INDEX IF NOT EXISTS idx_phoenix_read_marks_role ON phoenix_read_marks(role, id)",
    """CREATE TABLE IF NOT EXISTS chat_seen (
        role          TEXT NOT NULL,
        chat_id       TEXT NOT NULL,
        first_at      TEXT NOT NULL DEFAULT (datetime('now')),
        cursor_before INTEGER,
        cursor_after  INTEGER,
        mark_id       INTEGER,
        source        TEXT NOT NULL,
        PRIMARY KEY (role, chat_id))""",
    """CREATE TABLE IF NOT EXISTS read_batch_voids (
        token         TEXT PRIMARY KEY,
        role          TEXT NOT NULL,
        voided_at     TEXT NOT NULL DEFAULT (datetime('now')),
        chat_id       TEXT,
        cursor_before INTEGER NOT NULL,
        cursor_after  INTEGER NOT NULL,
        batch_last_id INTEGER)""",
)
TABLES = ("phoenix_read_marks", "chat_seen", "read_batch_voids")

# 'born' — отметка новой роли при её заведении: тоже двигает отметку, как и объявленный проход.
MOVING_SEGMENT = "(kind IN ('declared', 'born') OR (kind = 'read' AND basis IS NULL))"


def seed_hour(conn, role):
    """→ час последнего СВОЕГО хода по разделу state или None."""
    row = conn.execute("SELECT saved_at FROM phoenix WHERE role = ? AND section = 'state'",
                       (role,)).fetchone()
    if row is None:
        return None
    saved_at = row[0]
    target = f"phoenix.{role}.state"
    try:
        last_save = conn.execute(
            "SELECT actor_role FROM audit_log WHERE target = ? AND action = 'save_phoenix' "
            "ORDER BY id DESC LIMIT 1", (target,)).fetchone()
        own_save = conn.execute(
            "SELECT MAX(timestamp) FROM audit_log WHERE target = ? AND action = 'save_phoenix' "
            "AND upper(actor_role) = ?", (target, role)).fetchone()[0]
        own_confirm = conn.execute(
            "SELECT MAX(timestamp) FROM audit_log WHERE target = ? AND action = 'confirm_phoenix' "
            "AND upper(actor_role) = ?", (target, role)).fetchone()[0]
    except sqlite3.OperationalError:          # журнала нет — судим по самому разделу
        return saved_at
    if last_save is None or last_save[0].upper() == role:
        base = saved_at
    else:
        base = own_save                        # последнюю запись тела сделала чужая рука
    hours = [h for h in (base, own_confirm) if h]
    return max(hours) if hours else None


def plan_seed(conn):
    """→ список (роль, час, число, отметка) и список пропущенных (роль, причина)."""
    seeds, skipped = [], []
    for role, cur in conn.execute("SELECT upper(reader_role), last_read_id FROM read_cursors "
                                  "ORDER BY reader_role").fetchall():
        hour = seed_hour(conn, role)
        if hour is None:
            skipped.append((role, "раздела state нет"))
            continue
        top = conn.execute(f"SELECT MAX(to_id) FROM cursor_segments WHERE upper(role) = ? "
                           f"AND {MOVING_SEGMENT} AND at < ?", (role, hour)).fetchone()[0]
        if top is None:
            skipped.append((role, f"до часа памяти {hour} UTC отметку не двигал ни один отрезок"))
            continue
        seeds.append((role, hour, min(top, cur), cur))
    return seeds, skipped


def known_chats(conn):
    """→ множество (роль, номер чата) из реестра чатов и его истории."""
    chats = set()
    for table in ("role_sessions", "role_sessions_history"):
        try:
            for role, chat in conn.execute(f"SELECT upper(role), lower(trim(transcript_id)) "
                                           f"FROM {table} WHERE transcript_id IS NOT NULL "
                                           f"AND trim(transcript_id) <> ''"):
                chats.add((role, chat))
        except sqlite3.OperationalError:
            pass                               # таблицы или колонки нет — нечего сеять
    return chats


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
    for need in ("read_cursors", "cursor_segments", "phoenix"):
        if need not in tables:
            sys.exit(f'⛔ НЕ ЗАПУСТИЛСЯ: таблицы {need} нет — база старше нужных шагов')
    if all(t in tables for t in TABLES):
        print('✅ уже сведено — таблицы phoenix_read_marks, chat_seen и read_batch_voids на месте. '
              'Делать нечего')
        return

    seeds, skipped = plan_seed(conn)
    chats = known_chats(conn)
    print(f'СНИМКИ ПОСЕВА — ролей {len(seeds)}:')
    for role, hour, mark, cur in seeds:
        print(f'  {role:<8} память {hour} UTC → снимок #{mark} (отметка сейчас #{cur}; '
              f'новый чат вернётся на {cur - mark} записок)')
    for role, why in skipped:
        print(f'  {role:<8} снимка нет: {why}')
    print(f'ИЗВЕСТНЫХ ЧАТОВ к посеву: {len(chats)} (живые и прежние чаты ролей новыми не считаются)')

    if args.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    for sql in STATEMENTS:
        conn.execute(sql)
    for role, hour, mark, _cur in seeds:
        conn.execute("INSERT INTO phoenix_read_marks (role, at, read_mark, how, actor) "
                     "VALUES (?, ?, ?, 'seed', ?)", (role, hour, mark, VERSION))
    for role, chat in sorted(chats):
        conn.execute("INSERT OR IGNORE INTO chat_seen (role, chat_id, source) VALUES (?, ?, 'seed')",
                     (role, chat))
    fp = record_step(conn, VERSION,
                     "phoenix_read_marks + chat_seen + read_batch_voids: снимок отметки прочитанного "
                     "при сохранении state и её возврат при новом чате роли; посев снимков "
                     f"({len(seeds)}) и известных чатов ({len(chats)}). Карточка #466, пункт ①")
    conn.commit()
    print(f'\n✅ ПРИМЕНЕНО. отпечаток схемы: {fp}')


if __name__ == '__main__':
    main()
