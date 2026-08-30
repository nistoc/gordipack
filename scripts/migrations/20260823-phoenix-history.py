# -*- coding: utf-8 -*-
"""20260823-phoenix-history — ВЕРСИИ ТЕЛ СОХРАНЁННОЙ ПАМЯТИ РОЛЕЙ (заявка @OPSSRE).

ПОВОД, замером. 2026-08-21 22:28 UTC `save-phoenix.py` перезаписал секцию OPSSRE/state
18808 → 7455 знаков (потеря 60 %) и отчитался УСПЕХОМ: «было 18808 → стало 7455».
Вернуть было неоткуда — прежнее тело нигде не сохраняется.

🔴 ЭТО НЕ ЕДИНИЧНАЯ ОПЛОШНОСТЬ, А ШТАТНОЕ ПОВЕДЕНИЕ. Замер по audit_log (1321 запись
о сохранении памяти, 12.07–21.08):
    сокращений ................................. 312 из 1321 (24 % всех сохранений)
    из них ловит нынешняя защита ............... 10 (3 %) — порог «сокращение в 4 раза»
    крупных (>30 %) с известным продолжением ... 112
    🔴 из них СЛЕДОМ РЕЗКО ОТЫГРАНО НАЗАД ...... 30 (27 %)
Последняя строка и есть довод: примерно каждое четвёртое крупное сокращение выглядит
как потеря, которую заметили и чинили руками. За зрелый период (с 08.08) нынешний
порог не сработал НИ РАЗУ — включая сам инцидент, где нужно было 75 %, а вышло 60.4 %.

ЧТО ХРАНИМ — ВЕРСИЮ, А НЕ «ЗАМЕЩЁННОЕ ТЕЛО». Разница не косметическая: при хранении
версий возникает проверяемый инвариант — НОВЕЙШАЯ строка истории по каждой секции
дословно равна `phoenix.body`. Из него следуют три вещи разом:
  · пустая история однозначно значит «механизм не работал», а не «секцию не правили»;
  · правка мимо инструмента становится ВИДИМОЙ (новейшая версия разойдётся с телом);
  · приёмке есть что сличать.
Хранение «замещённого» такого инварианта не даёт: оно молчало бы одинаково и при
исправной работе, и при мёртвом механизме.

⚠️ ПОЧЕМУ ШАГ СЕЕТ, А НЕ ЗАВОДИТ ПУСТУЮ ТАБЛИЦУ (в отличие от 20260820-role-skills).
Там пустота была честной: умения — утверждение роли о себе, чужой рукой их вписывать
нельзя. Здесь наоборот: тело секции уже лежит в `phoenix`, посев ничего не выдумывает,
а переносит существующее. И без посева ПЕРВОЕ ЖЕ сохранение после шага прошло бы
без защиты — ровно тот случай, ради которого шаг и делается.
Час берётся из `phoenix.saved_at`, а не из времени миграции: иначе история соврала бы
о возрасте тел в первый же день.

ЧЕГО ЭТОТ ШАГ НЕ ДЕЛАЕТ. Не правит `save-phoenix.py` — запись версий, чистка и пороги
идут отдельной правкой того же владельца. Шаг схемы — ровно то, что нужно, чтобы
правке было куда писать. До неё таблица останется засеянной и неподвижной, и это
видно запросом, а не подразумевается.
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

VERSION = "20260823-phoenix-history"

# 🪤 DDL — СПИСОК ОПЕРАТОРОВ, А НЕ ОДНА СТРОКА С РАЗДЕЛИТЕЛЯМИ. Так сделано по оплаченной
# ошибке: образец (20260820-role-skills.py) хранит DDL текстом и режет его на операторы
# через DDL.split(";"). Первый же мой комментарий со словами «...ПРЕЖНЕГО тела; NULL —
# первая версия» РАЗОРВАЛ оператор пополам, и SQLite сказал «incomplete input».
# ⚠️ Мина лежит и в образце: там приём работает не потому, что верен, а потому, что
# в его комментариях пока не встретилось точки с запятой. Знак препинания в пояснении
# ломает схему — и ломает в момент применения, а не при чтении кода.
# ⇒ Списком разбирать нечего: сколько элементов, столько операторов.
DDL = [
    """
    CREATE TABLE IF NOT EXISTS phoenix_history (
        id          INTEGER PRIMARY KEY,
        role        TEXT NOT NULL,
        section     TEXT NOT NULL,
        -- ТЕЛО ВЕРСИИ ДОСЛОВНО, а не разница с предыдущей. Возврат обязан быть
        -- КОПИРОВАНИЕМ: восстановление по частям добавляет шаг, на котором
        -- «не смог собрать» превращается в «данных нет», и происходит это
        -- в худший для роли момент.
        body        TEXT NOT NULL,
        body_chars  INTEGER NOT NULL,
        -- КОГДА это тело стало текущим. У посева — час из phoenix.saved_at,
        -- а не час миграции: иначе история соврала бы о возрасте всех тел разом.
        saved_at    TEXT NOT NULL,
        -- КТО записал: исполнитель (--actor), а не владелец секции. Форма из audit_log.
        actor       TEXT NOT NULL,
        -- 'seed' | 'save' | 'save --allow-shrink' | 'restore <id>'.
        -- ⚠️ Сокращение, разрешённое словом, обязано быть видно В САМОЙ ИСТОРИИ:
        -- в audit_log записей со словом shrink сегодня НОЛЬ, то есть журнал о нём
        -- не знает вовсе, и злоупотребление флагом нечем измерить.
        reason      TEXT NOT NULL,
        -- каким был размер ПРЕЖНЕГО тела. NULL значит «первая версия секции»
        prev_chars  INTEGER
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phoenix_history
        ON phoenix_history(role, section, id DESC)
    """,
]

# ⛔ БЕЗ UNIQUE(role, section, saved_at) НАМЕРЕННО: datetime('now') имеет секундную
# точность, два сохранения в одну секунду дали бы IntegrityError — то есть ОТКАЗ ЗАПИСИ
# ПАМЯТИ по календарной случайности. Защита памяти, роняющая запись памяти, — не защита.

SEED = """
INSERT INTO phoenix_history (role, section, body, body_chars, saved_at, actor, reason, prev_chars)
SELECT role, section, body, LENGTH(body), saved_at, 'migration', 'seed', NULL FROM phoenix
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, SCRIPTS)
    import mezo_paths
    db = mezo_paths.resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))

    have = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='phoenix_history'"
    ).fetchone()
    print(f"база: {db}")
    print(f"таблица phoenix_history: {'УЖЕ ЕСТЬ' if have else 'нет — будет заведена'}")

    secs = conn.execute("SELECT COUNT(*), SUM(LENGTH(body)) FROM phoenix").fetchone()
    print(f"секций памяти к посеву: {secs[0]}, суммарно {secs[1]} знаков "
          f"(≈{secs[1]/1024/1024:.1f} МБ прироста базы разово)")

    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.")
        return

    logged = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone()

    # Ветка, оплаченная прогоном шага role-skills 20.08 06:17 UTC: если таблица уже есть,
    # а записи в журнале нет — схема ушла вперёд журнала. След дописывается задним числом
    # с пометкой, а не прячется пересозданием таблицы (пересоздание стёрло бы версии).
    if have and not logged:
        print("\n🪤 Таблица ЕСТЬ, а записи в журнале НЕТ — схема ушла вперёд журнала.")
        fp = record_step(
            conn, VERSION,
            "phoenix_history: заведена ранее без записи в журнале. Таблица и её DDL верны; "
            "след восстановлен задним числом, а не скрыт пересозданием — пересоздание "
            "стёрло бы уже накопленные версии тел",
            backdated=True)
        conn.commit()
        print(f"✅ След восстановлен задним числом. отпечаток схемы: {fp}")
        ok, why = verify(conn)
        print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
        return

    if have and logged:
        print("\n⚖️ Таблица есть и след в журнале есть — шаг ничего не меняет.")
        n = conn.execute("SELECT COUNT(*) FROM phoenix_history").fetchone()[0]
        print(f"версий в истории: {n}")
        return

    conn.execute("BEGIN")
    # ⛔ НЕ executescript: он делает неявный commit и рвёт явную транзакцию — журнал тогда
    # пишется вне её, и «та же транзакция» становится словами. Поймано прогоном, не чтением
    # (шаг role-skills, 20.08 06:17 UTC).
    for stmt in DDL:
        conn.execute(stmt)
    conn.execute(SEED)
    seeded = conn.execute("SELECT COUNT(*) FROM phoenix_history").fetchone()[0]
    fp = record_step(
        conn, VERSION,
        "phoenix_history: версии тел сохранённой памяти. Повод — 21.08 22:28 UTC "
        "save-phoenix перезаписал OPSSRE/state 18808 → 7455 знаков (потеря 60 %) "
        "и отчитался успехом; вернуть было неоткуда. Замер по audit_log: сокращения — "
        "24 % всех сохранений памяти, каждое четвёртое крупное следом отыгрывалось назад. "
        "Строка = ВЕРСИЯ, новейшая равна phoenix.body — из этого инварианта следует "
        "и проверяемость механизма, и видимость правок мимо инструмента. Посев по живым "
        "секциям: без него первое же сохранение после шага прошло бы без защиты")
    conn.commit()
    print(f"\n✅ ВРЕЗАНО. отпечаток схемы: {fp}")
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print("целостность:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print(f"засеяно версий: {seeded} (по одной на живую секцию)")
    inv = conn.execute("""
        SELECT COUNT(*) FROM phoenix p
         WHERE NOT EXISTS (SELECT 1 FROM phoenix_history h
                            WHERE h.role=p.role AND h.section=p.section AND h.body=p.body)
    """).fetchone()[0]
    print(f'{"✅" if inv == 0 else "🔴"} инвариант «у каждой секции есть версия, равная её телу»: '
          f'{"держится" if inv == 0 else f"НАРУШЕН у {inv} секций"}')


if __name__ == '__main__':
    main()
