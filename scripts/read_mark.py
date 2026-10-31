# -*- coding: utf-8 -*-
"""read_mark.py — ВОЗВРАТ ОТМЕТКИ ПРОЧИТАННОГО ПРИ НОВОМ ЧАТЕ РОЛИ (карточка #466, пункт ①).

БЕДА. Роль сохраняет память (раздел state), потом читает ленту и подтверждает прочитанное.
Чат закрылся — новый чат роли получает память, в которой прочитанного после сохранения НЕТ,
а отметка прочитанного уже стоит за ним. Эти записки новый чат не увидит никогда.

ЧТО ДЕЛАЕТ МОДУЛЬ.
  remember()    — сохраняя state своей рукой, роль той же транзакцией запоминает отметку
                  прочитанного (снимок, таблица phoenix_read_marks);
  first_touch() — когда НОВЫЙ чат роли впервые читает ленту или пишет память, отметка
                  опускается до последнего снимка, а неподтверждённые выдачи прежнего чата
                  выше новой отметки ГАСНУТ (таблица read_batch_voids): их ключи больше
                  не сдвинут отметку через возвращённое окно;
  forecast()    — только печать для машинного слоя памяти: «при первом чтении отметка вернётся».

КАК УЗНАЁТСЯ НОВЫЙ ЧАТ. Номер чата — переменная CLAUDE_CODE_SESSION_ID (её ставит приложение,
она же role_sessions.transcript_id; помощники чата несут тот же номер). Новый чат = пары
(роль, номер) нет в chat_seen, и номер не записан за другой ролью. Номера нет — возврата нет.

⚖️ ПОЧЕМУ ГАШЕНИЕ, А НЕ ОТКАЗ ПО ЧАСУ (третий круг, комментарий карточки 2026-10-31 10:08 UTC).
Второй круг отклонял ключ, выданный раньше последнего возврата, — перевыдача R16 отдавала
тот же ключ снова, и отметка запиралась до 7 суток. Погашенная выдача получает acked_at,
выходит из замка ux_batch_race и из перевыдачи — следующее чтение выдаёт НОВЫЙ ключ.
Цена — прежний чат, если ещё жив, перечитает окно; запирания нет по построению.

⛔ Модуль НЕ создаёт таблиц: их заводит шаг схемы migrations/20261031-read-mark-at-save.py.
Нет таблиц — функции молчат и ничего не трогают (forecast говорит, что шаг не сведён).
"""
import os
import sqlite3
from pathlib import Path

CHAT_ENV = "CLAUDE_CODE_SESSION_ID"
STEP = "20261031-read-mark-at-save"
TABLES = ("phoenix_read_marks", "chat_seen", "read_batch_voids")
# решение владельца 2026-10-03 13:33 UTC («принять как есть» со строкой о --wake)
BIG_WINDOW_NOTES = 50
BIG_WINDOW_BYTES = 200 * 1024

HERE = Path(__file__).resolve().parent


def chat_id():
    """→ номер чата в нижнем регистре или None."""
    value = (os.environ.get(CHAT_ENV) or "").strip().lower()
    return value or None


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def tables_ready(conn):
    have = _tables(conn)
    return all(t in have for t in TABLES)


def owner_of_chat(conn, chat):
    """→ роль, за которой записан чат, или None.

    Решение ② первого круга: текущая запись role_sessions решает; история — только последняя
    запись номера и только когда в role_sessions его нет (чат, переведённый к другой роли,
    не остаётся «чужим» навсегда)."""
    try:
        row = conn.execute("SELECT role FROM role_sessions WHERE lower(transcript_id) = ? "
                           "LIMIT 1", (chat,)).fetchone()
        if row:
            return row[0].upper()
        row = conn.execute("SELECT role FROM role_sessions_history WHERE lower(transcript_id) = ? "
                           "ORDER BY id DESC LIMIT 1", (chat,)).fetchone()
        return row[0].upper() if row else None
    except sqlite3.OperationalError:     # контур без колонки transcript_id или без истории
        return None


def _seen(conn, role, chat):
    return conn.execute("SELECT 1 FROM chat_seen WHERE role = ? AND chat_id = ?",
                        (role, chat)).fetchone() is not None


def _cursor(conn, role):
    row = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role = ?",
                       (role,)).fetchone()
    return row[0] if row else None


def latest_mark(conn, role):
    """→ (id, read_mark, at, how) последнего снимка роли или None."""
    return conn.execute("SELECT id, read_mark, at, how FROM phoenix_read_marks WHERE role = ? "
                        "ORDER BY id DESC LIMIT 1", (role,)).fetchone()


def window(conn, low, high):
    """→ (записок в ленте, байт в ленте, записок уже в архиве) для окна (low, high]."""
    n, size = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(length(CAST(body_md AS BLOB))), 0) FROM messages "
        "WHERE id > ? AND id <= ?", (low, high)).fetchone()
    try:
        archived = conn.execute("SELECT COUNT(*) FROM messages_archive WHERE id > ? AND id <= ?",
                                (low, high)).fetchone()[0]
    except sqlite3.OperationalError:
        archived = 0
    return n, size, archived


def _db_option(conn):
    """«--db <путь>» для печатаемых команд, если база не та, что рядом со скриптами."""
    try:
        path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    except (sqlite3.Error, TypeError, OSError):
        return ""
    default = (HERE.parent / "mezosync.db").resolve()
    return "" if path == default else f" --db {path.as_posix()}"


def _reader_cmd(conn, role, extra=""):
    return f"python {(HERE / 'read-messages.py').as_posix()} --role {role}{extra}{_db_option(conn)}"


def _window_lines(conn, role, low, high):
    n, size, archived = window(conn, low, high)
    lines = []
    if archived:
        dbq = (HERE / "db-q.py").as_posix()
        lines.append(f"   📦 из окна уже в архиве: {archived} — лента их не покажет, читать запросом:\n"
                     f"      python {dbq}{_db_option(conn)} \"SELECT id, writer_role, timestamp, body_md "
                     f"FROM messages_archive WHERE id > {low} AND id <= {high} ORDER BY id\"")
    if n > BIG_WINDOW_NOTES or size > BIG_WINDOW_BYTES:
        lines.append(f"   ⚠️ окно большое: {n} записок, {size // 1024} КБ — начни с обзора: "
                     f"{_reader_cmd(conn, role, ' --wake')}")
    return lines


def first_touch(conn, role, source):
    """Проверка нового чата роли. → строки для печати (пустой список — ничего не случилось).

    Зовут: read-messages.py (каждый вызов, кроме --ack и --register) и save-phoenix.py (своя
    рука, до записи). Своему новому чату строка chat_seen пишется ВСЕГДА, даже без снимка:
    без неё remember() не запишет снимок никогда (находка 5 второго круга)."""
    chat = chat_id()
    if chat is None or not tables_ready(conn):
        return []
    role = role.upper()
    if _seen(conn, role, chat):
        return []
    owner = owner_of_chat(conn, chat)
    if owner is not None and owner != role:
        return []                      # чужой чат: ни возврата, ни строки chat_seen
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # повторная проверка под замком: параллельные вызовы одного чата дают один возврат
        if _seen(conn, role, chat):
            conn.rollback()
            return []
        cur = _cursor(conn, role)
        if cur is None:                # роль не заведена — заводит только --register
            conn.rollback()
            return []
        mark = latest_mark(conn, role)
        new = min(cur, mark[1]) if mark else cur
        voided = 0
        if new < cur:
            conn.execute("UPDATE read_cursors SET last_read_id = ?, updated_at = datetime('now') "
                         "WHERE reader_role = ?", (new, role))
            if "read_batches" in _tables(conn):
                open_batches = conn.execute(
                    "SELECT token, last_id FROM read_batches WHERE role = ? AND acked_at IS NULL "
                    "AND last_id > ?", (role, new)).fetchall()
                for token, last_id in open_batches:
                    conn.execute("INSERT OR IGNORE INTO read_batch_voids (token, role, chat_id, "
                                 "cursor_before, cursor_after, batch_last_id) VALUES (?,?,?,?,?,?)",
                                 (token, role, chat, cur, new, last_id))
                    conn.execute("UPDATE read_batches SET acked_at = datetime('now') "
                                 "WHERE token = ?", (token,))
                voided = len(open_batches)
            conn.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) "
                         "VALUES (?, 'read_mark_return', ?, ?)",
                         (role, f"read_cursors.{role}",
                          f"новый чат {chat} ({source}): отметка #{cur} → #{new} по снимку "
                          f"id={mark[0]} ({mark[2]} UTC, {mark[3]}); погашено выдач: {voided}"))
        conn.execute("INSERT INTO chat_seen (role, chat_id, cursor_before, cursor_after, mark_id, "
                     "source) VALUES (?,?,?,?,?,?)",
                     (role, chat, cur, new, mark[0] if mark else None, source))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if mark is None:
        return [f"↩ новый чат роли {role} (номер {chat[:8]}…): снимка отметки прочитанного ещё нет — "
                f"он появится с первым сохранением раздела state"]
    if new == cur:
        return [f"↩ новый чат роли {role} (номер {chat[:8]}…): возвращать нечего — после сохранения "
                f"памяти ({mark[2]} UTC) прежний чат ленту дальше #{cur} не подтверждал"]
    lines = [f"↩ ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА #{cur} → #{new}: это новый чат роли {role} "
             f"(номер {chat[:8]}…), а прежний подтверждал ленту после сохранения памяти "
             f"({mark[2]} UTC).",
             f"   записки #{new + 1}…#{cur} придут снова — их читал прежний чат, этот их не видел"]
    if voided:
        lines.append(f"   погашено неподтверждённых выдач прежнего чата: {voided} — их ключи "
                     f"отметку больше не сдвинут")
    lines += _window_lines(conn, role, new, cur)
    if source != "read-messages":
        lines.append(f"   👉 прочитай ленту: {_reader_cmd(conn, role)}")
    return lines


def remember(conn, role, actor, how, at=None):
    """Снимок отметки прочитанного вместе с разделом state. Пишет В ТРАНЗАКЦИИ ВЫЗЫВАЮЩЕГО
    (коммит — его), → строки для печати.

    Не пишет: чужой рукой (--actor не равен роли или чат записан за другой ролью); при
    известном номере чата без строки chat_seen (решение ① первого круга: сбой проверки нового
    чата не должен записать снимок на НЕ возвращённой отметке). --restore и --dry-run
    отсекает вызывающий."""
    role = role.upper()
    if actor.upper() != role or not tables_ready(conn):
        return []
    chat = chat_id()
    if chat is not None:
        owner = owner_of_chat(conn, chat)
        if owner is not None and owner != role:
            return []
        if not _seen(conn, role, chat):
            return ["⚠️ снимок отметки прочитанного НЕ записан: проверка нового чата для этого "
                    "чата не прошла. Прочитай ленту, затем сохрани state снова: "
                    + _reader_cmd(conn, role)]
    cur = _cursor(conn, role)
    if cur is None:
        return []
    conn.execute("INSERT INTO phoenix_read_marks (role, at, read_mark, how, chat_id, actor) "
                 "VALUES (?, COALESCE(?, datetime('now')), ?, ?, ?, ?)",
                 (role, at, cur, how, chat, actor.upper()))
    return [f"📌 вместе с памятью запомнена отметка прочитанного #{cur}: новый чат роли вернётся к ней"]


def void_refusal(conn, role, token):
    """→ текст отказа для погашенного ключа или None."""
    if "read_batch_voids" not in _tables(conn):
        return None
    row = conn.execute("SELECT voided_at, chat_id, cursor_before, cursor_after FROM read_batch_voids "
                       "WHERE token = ? AND role = ?", (token, role)).fetchone()
    if not row:
        return None
    who = f"номер {row[1][:8]}…" if row[1] else "номер неизвестен"
    return (f"⛔ ACK ОТКЛОНЁН: ключ «{token}» погашен {row[0]} UTC — отметку прочитанного вернул "
            f"новый чат роли {role} (#{row[2]} → #{row[3]}, {who}). Отметка НЕ сдвинута:\n"
            f"   этот ключ перешагнул бы записки, которых новый чат ещё не видел.\n"
            f"   👉 перечитай ленту — выдача придёт с новым ключом: {_reader_cmd(conn, role)}")


def forecast(conn, role):
    """→ строки для машинного слоя памяти. Только чтение; при пустом прогнозе — пустой список."""
    role = role.upper()
    chat = chat_id()
    if not tables_ready(conn):
        return ([f"   ⚠️ возврат отметки прочитанного при новом чате НЕ работает: шаг схемы "
                 f"{STEP} не сведён"] if chat else [])
    mark = latest_mark(conn, role)
    cur = _cursor(conn, role)
    if mark is None or cur is None or mark[1] >= cur:
        return []
    if chat is None:
        return [f"   ⚠️ номер чата неизвестен (нет {CHAT_ENV}): при новом чате отметка "
                f"прочитанного #{cur} НЕ вернётся к снимку #{mark[1]}"]
    if _seen(conn, role, chat):
        return []
    owner = owner_of_chat(conn, chat)
    if owner is not None and owner != role:
        return []
    n, size, archived = window(conn, mark[1], cur)
    lines = [f"   ↩ это новый чат роли: при первом чтении ленты или записи памяти отметка вернётся "
             f"#{cur} → #{mark[1]} ({n} записок, {size // 1024} КБ"
             + (f", ещё {archived} в архиве" if archived else "") + ")"]
    if n > BIG_WINDOW_NOTES or size > BIG_WINDOW_BYTES:
        lines.append(f"      окно большое — начни с обзора: {_reader_cmd(conn, role, ' --wake')}")
    return lines
