# -*- coding: utf-8 -*-
"""mezo_hints.py — «подсказка печатается роли один раз, дальше — строка-ссылка» (карточка #586).

ЗАЧЕМ. Инструменты координации печатают общие пояснения (границы механизма, порядок
вызова, куда смотреть при отказе) КАЖДЫЙ РАЗ — той же роли, тем же текстом, при каждом
вызове. Роль это уже прочитала, и с каждым повторением текст читают всё меньше внимательно:
тот же класс беды, что у предупреждения без срока годности (`warning-must-carry-expiry`) —
оно есть, его перестают замечать, а вместе с ним и то новое, что стоит рядом.

ЧТО ДЕЛАЕТ. `подсказка()` — один вызов на одном месте печати общего пояснения:
  · первый показ этой паре (роль, ключ) — печатает ПОЛНЫЙ текст, запоминает отпечаток
    текста и час показа;
  · тот же текст той же роли, срок (TTL) ещё не истёк — печатает ОДНУ строку-ссылку;
  · текст изменился, роль не названа, TTL истёк, вызывающий сам просит полный текст
    (`full=True`), ИЛИ база не открылась / таблицы нет / она занята — печатает ПОЛНЫЙ
    текст. Откат — ВСЕГДА в сторону полноты, никогда в сторону молчания: непоказанная
    подсказка дороже одной лишней строки.

ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ — чего этот помощник НЕ решает:
  · он НЕ решает, какая подсказка обязательна к прочтению, а какая нет, — это решает
    вызывающий код выбором ключа, текста и `ttl_hours`;
  · он НЕ сокращает `отказ()` и `итог()` — они печатают целиком ВСЕГДА. Сокращать
    там, где по определению читают один раз (отказ — про то, что случилось СЕЙЧАС;
    итог — короткая строка сама по себе), нечего;
  · он НЕ хранит историю показов — только последний факт: строка (role, hint_key)
    перезаписывается заново при каждом полном показе. Вопрос здесь только «видела ли
    роль ЭТОТ текст недавно», а не «когда были все разы».

Использование в инструменте координации:
    import sqlite3
    import mezo_hints

    conn = sqlite3.connect(db_path)
    mezo_hints.подсказка(conn, role, "guard-all-порядок", ТЕКСТ_ПОДСКАЗКИ, full=args.full)

Схема — таблица `hint_seen` (role, hint_key, content_hash, shown_at; PK role+hint_key),
заводится миграцией `migrations/20260907-hint-seen.py`.

Дата: 2026-09-06 23:20 UTC. Карточка #586.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone


def _час_сейчас_iso() -> str:
    """Текущий час UTC как naive ISO-строка (без смещения) — формат hint_seen.shown_at."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()


def _разобрать_час(текст):
    """→ datetime (naive) или None. Негодная строка в базе не роняет вызывающего —
    просто считается просроченной (см. подсказка())."""
    try:
        return datetime.fromisoformat(текст)
    except (ValueError, TypeError):
        return None


def _когда_человеку(iso_текст: str) -> str:
    """shown_at → «2026-09-07 01:17 UTC» для строки-ссылки. Не разобралось — печатаем
    как есть, лишь бы не падать на форматировании собственной подсказки."""
    час = _разобрать_час(iso_текст)
    if час is None:
        return f"{iso_текст} UTC"
    return час.strftime("%Y-%m-%d %H:%M") + " UTC"


def подсказка(conn, role, key: str, text: str, *, ttl_hours: float = 24, full: bool = False) -> bool:
    """Напечатать подсказку `text` под ключом `key` для роли `role`.

    Возвращает True, если напечатан ПОЛНЫЙ текст, False — если напечатана только
    строка-ссылка.

    full=True, `role` пустая/None или `conn` — None: печатаем целиком и БАЗУ НЕ ТРОГАЕМ.
    Сравнивать «уже видела» не с чем, когда роль не названа, — печатать сокращённо
    для «никого» нельзя.
    """
    if full or not role or conn is None:
        print(text)
        return True

    try:
        row = conn.execute(
            "SELECT content_hash, shown_at FROM hint_seen WHERE role = ? AND hint_key = ?",
            (role, key)).fetchone()

        свежая = False
        if row is not None:
            прежний_hash, прежний_shown_at = row
            текущий_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
            час = _разобрать_час(прежний_shown_at)
            не_протухла = (час is not None
                           and datetime.now(timezone.utc).replace(tzinfo=None) - час
                           <= timedelta(hours=ttl_hours))
            свежая = (прежний_hash == текущий_hash) and не_протухла

        if свежая:
            print(f"ℹ️ подсказка «{key}» показана {_когда_человеку(row[1])}; "
                  f"полный текст — добавь --full")
            return False

        # Записи нет, ИЛИ текст сменился, ИЛИ отметка старше TTL — показываем целиком
        # и заново запоминаем (role, key): и как отдельный INSERT, и как замену старой
        # отметки той же парой ключа — здесь это одно действие (INSERT OR REPLACE).
        print(text)
        conn.execute(
            "INSERT OR REPLACE INTO hint_seen (role, hint_key, content_hash, shown_at) "
            "VALUES (?, ?, ?, ?)",
            (role, key, hashlib.sha1(text.encode("utf-8")).hexdigest(), _час_сейчас_iso()))
        conn.commit()
        return True
    except Exception:  # noqa: BLE001 — ЛЮБАЯ беда БД откатывается в сторону ПОЛНОТЫ,
        # никогда в сторону молчания: нет таблицы, база только для чтения, занята другим
        # процессом — во всех случаях подсказка обязана быть напечатана.
        print(text)
        return True


def отказ(text: str) -> None:
    """Отказ — печатается ЦЕЛИКОМ ВСЕГДА, в stderr. Ничего не решает и не режет —
    только единообразное место печати для мест отказа, зовущих этот помощник."""
    print(text, file=sys.stderr)


def итог(text: str) -> None:
    """Итог (строки вида «OK #NNNN») — печатается ЦЕЛИКОМ ВСЕГДА, в stdout."""
    print(text)


def забыть(conn, role: str, key: str | None = None) -> int:
    """Удалить отметки роли — ОДНУ (по `key`) или ВСЕ (`key=None`). Возвращает число
    удалённых строк. Для приёмки и ручной проверки: без этого способа «подсказка
    показывается заново» проверить нельзя иначе, чем ждать истечения TTL."""
    if key is None:
        cur = conn.execute("DELETE FROM hint_seen WHERE role = ?", (role,))
    else:
        cur = conn.execute("DELETE FROM hint_seen WHERE role = ? AND hint_key = ?", (role, key))
    conn.commit()
    return cur.rowcount
