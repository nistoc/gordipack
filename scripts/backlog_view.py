r"""
backlog_view.py — ОДНО место, откуда берётся ответ «что у роли открыто и сколько оно висит».

ЗАЧЕМ (карточка #112, пункты ② и ④; правило task-discipline, замок владельца 07.08):
роль после перезапуска о своих задачах не узнавала НИЧЕМ, кроме чужого напоминания —
слов «карточка»/«бэклог» в слепках было НОЛЬ. А список незакрытых с возрастом (23 штуки
старше суток, старшей 26 дней) не показывал никто: он существовал только в команде,
которую надо ВСПОМНИТЬ и позвать. Замер @PROTO по соседнему сосуду: ручка `--task`
существовала всегда и не была позвана НИ РАЗУ за 1724 записки.
🎯 ⇒ Витрину, которую надо позвать, надо помнить. Здесь она встраивается в ДВА вывода,
которые роль и так читает: ленту (каждый синк) и слепок (каждое пробуждение).

⚠️ ПОЧЕМУ ОТДЕЛЬНЫЙ МОДУЛЬ, А НЕ ДВЕ КОПИИ ЗАПРОСА. Предикат «открытые карточки роли»
уже живёт в backlog.py (`list`). Скопировав его в читалку и в слепок, я получил бы ТРИ
правды об одном: критерий #112 ② требует, чтобы список в слепке СОВПАДАЛ с `backlog.py
list --role <та же роль>`, а разошлись бы они молча — при первой же правке предиката
в одном месте из трёх. Константы поэтому импортируются ИЗ backlog.py, а не повторяются.

Зовут: read-messages.py (хвост батча) · read-phoenix.py (§4½) — оба через try/except:
отсутствие витрины не вправе отказывать сильнее, чем сама витрина (норма @TAXO 13:18 UTC).
"""

import sqlite3

from backlog import OPEN_STATUSES, PRIORITY_ORDER   # ЕДИНСТВЕННЫЙ источник предиката

PRIO_MARK = {"critical": "‼️", "high": "⬆️", "normal": " ·", "low": "⬇️"}
STATUS_ICON = {"open": "○", "in_progress": "◐", "blocked": "⛔", "in_review": "👀"}


def open_cards(conn, role):
    """Открытые карточки роли + SHARED — ТЕМ ЖЕ предикатом, что `backlog.py list --role X`.

    Возвращает список кортежей (id, role, title, status, priority, done_when, age_days),
    отсортированный как в backlog.py: сначала срочность, потом номер.
    age_days считает SQLite (julianday) — не питон: смешивать две шкалы времени в контуре
    уже стоило фантома «синк умер 2 часа назад».
    """
    roles = [role.upper(), "SHARED"]
    params = roles + list(OPEN_STATUSES)
    rows = conn.execute(
        "SELECT id, role, title, status, priority, done_when, "
        "       CAST(julianday('now') - julianday(created_at) AS INTEGER) "
        f"FROM backlog WHERE role IN ({','.join('?' * len(roles))}) "
        f"AND status IN ({','.join('?' * len(OPEN_STATUSES))})", params).fetchall()
    return sorted(rows, key=lambda r: (PRIORITY_ORDER.get(r[4], 9), r[0]))


def reminder_lines(conn, role, top=5):
    """Строки напоминания. Пустой список = у роли ничего не открыто (и тогда МОЛЧИМ).

    ⚠️ Печатается НЕ весь список, а сводка + `top` самых срочных. Довод замерный:
    у @CORE открытых 23, у @PROTO 12 — полный список в КАЖДОМ синке роль научится
    пролистывать, и витрина умрёт ровно так же, как умирает вечно-красная проверка.
    Полная форма названа последней строкой — одной командой, которую видно тут же.
    """
    rows = open_cards(conn, role)
    if not rows:
        return []
    no_crit = sum(1 for r in rows if not (r[5] or "").strip())
    oldest = max(r[6] or 0 for r in rows)
    head = (f"📋 ТВОИХ НЕЗАКРЫТЫХ КАРТОЧЕК: {len(rows)} · старшей {oldest} дн"
            + (f" · без критерия {no_crit} ⛔ их НЕЛЬЗЯ закрыть" if no_crit else ""))
    out = [head]
    for bid, _r, title, status, prio, done_when, age in rows[:top]:
        mark = "  " if (done_when or "").strip() else " ✎"
        out.append(f"   #{bid} {STATUS_ICON.get(status, '?')} {PRIO_MARK.get(prio, ' ·')}{mark} "
                   f"{(age or 0):>3}дн  {title[:72]}")
    if len(rows) > top:
        out.append(f"   … и ещё {len(rows) - top}")
    return out


def reminder_block(db_path, role, top=5):
    """То же, но своим соединением и НИКОГДА не роняя вызывающего.

    ⚖️ Граница названа вслух: витрина задач не вправе сломать чтение ленты или
    предъявление слепка. Поломка здесь печатает строку и уходит — «напоминания нет»
    видно, и это честнее тихого пропуска.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return reminder_lines(conn, role, top)
        finally:
            conn.close()
    except Exception as e:                       # noqa: BLE001
        return [f"⚠️ список открытых карточек НЕ ПОКАЗАН ({type(e).__name__}) — зови backlog.py list сам"]
