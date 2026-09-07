# -*- coding: utf-8 -*-
"""mezo_refs — ОДНО место, где номер записки «#N» превращается в строку ленты.

ЗАЧЕМ (карточка #538, шаг ③ регламента сжатия; правило history-compression-policy v2,
раздел ①: «пока хоть один читатель ссылку не находит — переноса нет»). Замер PROTO
2026-09-05 11:43 UTC: из 62 инструментов, читающих таблицы ленты, номер записки разрешают
15 — и каждый своим запросом к `messages`. Когда записки старше срока уедут в архивную
таблицу `messages_archive`, каждый из пятнадцати перестал бы находить старые номера ПО-СВОЕМУ
и молча. Лечится не пятнадцатью правками, а одной функцией: читатель спрашивает ЗДЕСЬ,
а где лежит записка — живая таблица, архив по возрасту или ретро-импорт — знает только
это место.

ТРИ ИСТОЧНИКА, порядок поиска — по вероятности:
    live     — `messages`          живая лента
    archive  — `messages_archive`  перенесено по возрасту (шаг 20260905-messages-archive);
                                   id ПРЕЖНИЙ, поэтому ссылка «#N» не протухает от переноса
    history  — `messages_history`  ретро-импорт разметки 02–12.07 (split-history-table.py);
                                   id там НЕ хронологичны

⚖️ ГРАНИЦЫ: функция отвечает «есть ли записка с таким номером и где», и только. Она не судит,
годна ли ссылка по смыслу, и не знает о карточках (у них своя таблица `backlog`).
Таблицы, которых в базе нет (контур старше шага схемы), пропускаются молча — так функция
годна и старой базе; но источник 'archive' тогда не проверяется, и об этом говорит
`sources(conn)`.

ВЫЗОВ:
    from mezo_refs import resolve, exists, sources
    row = resolve(conn, 4823)      # None либо dict(id, writer_role, timestamp, body_md, source)
    exists(conn, 4823)             # True/False
    sources(conn)                  # какие из трёх таблиц есть в этой базе
"""
from __future__ import annotations

import sqlite3

ИСТОЧНИКИ = (("live", "messages"), ("archive", "messages_archive"), ("history", "messages_history"))
ПОЛЯ = "id, writer_role, timestamp, body_md, tags, priority, resolved"


def sources(conn: sqlite3.Connection) -> dict:
    """Какие из трёх таблиц ленты есть в базе: {'live': True, 'archive': False, ...}."""
    есть = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {имя: (таблица in есть) for имя, таблица in ИСТОЧНИКИ}


def resolve(conn: sqlite3.Connection, n: int):
    """Строка записки #n из ЛЮБОГО источника или None. dict с полем source."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    имеющиеся = sources(conn)
    for имя, таблица in ИСТОЧНИКИ:
        if not имеющиеся[имя]:
            continue
        r = conn.execute(f"SELECT {ПОЛЯ} FROM {таблица} WHERE id=?", (n,)).fetchone()
        if r is not None:
            return {"id": r[0], "writer_role": r[1], "timestamp": r[2], "body_md": r[3],
                    "tags": r[4], "priority": r[5], "resolved": r[6], "source": имя}
    return None


def exists(conn: sqlite3.Connection, n: int) -> bool:
    return resolve(conn, n) is not None


def mark_resolved(conn: sqlite3.Connection, n: int) -> str | None:
    """Поставить resolved=1 записке #n ТАМ, ГДЕ ОНА ЛЕЖИТ. Возвращает источник или None.
    ⚡ Прежде write-message.py делал UPDATE messages — у унесённой записки это меняло ноль строк
    МОЛЧА, и «снято» не доходило до читателя старой записки."""
    row = resolve(conn, n)
    if row is None:
        return None
    таблица = dict(ИСТОЧНИКИ)[row["source"]]
    conn.execute(f"UPDATE {таблица} SET resolved = 1 WHERE id = ?", (n,))
    return row["source"]


def existing_ids(conn: sqlite3.Connection, ids) -> set:
    """Какие из номеров существуют — одним обходом источников (для проверок с сотнями ссылок)."""
    ids = {int(i) for i in ids}
    найдено: set = set()
    имеющиеся = sources(conn)
    for имя, таблица in ИСТОЧНИКИ:
        if not имеющиеся[имя] or not ids:
            continue
        остаток = list(ids - найдено)
        for i in range(0, len(остаток), 500):
            кусок = остаток[i:i + 500]
            q = f"SELECT id FROM {таблица} WHERE id IN ({','.join('?' * len(кусок))})"
            найдено.update(r[0] for r in conn.execute(q, кусок))
    return найдено
