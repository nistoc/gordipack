"""
stats.py — снимок статистики mezosync.db для COORD (периодический сбор).

Использование:
    python <КОНТУР>/.mezosync/scripts/stats.py
    python <КОНТУР>/.mezosync/scripts/stats.py --since-min 50   # активность за окно
    python <КОНТУР>/.mezosync/scripts/stats.py --json           # машинный вывод
    python <КОНТУР>/.mezosync/scripts/stats.py --record         # + записать снимок в stats_log

Ничего не мутирует в messages/rules/phoenix. С --record добавляет строку в
служебную таблицу stats_log (создаётся при первом вызове) — чтобы видеть динамику.
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD


def utc_to_local(s):
    """UTC → UTC. Имя оставлено ради совместимости вызовов; конвертации БОЛЬШЕ НЕТ.

    Правило timestamp-utc-in-sqlite v2 (владелец 2026-07-16 12:12 UTC): контур живёт в
    ОДНОЙ шкале — UTC. Суффикс UTC печатаем явно: метка без зоны неотличима от локальной.

    NB ДЛЯ ПРЕЕМНИКА — ЭТУ ФУНКЦИЮ ГАРД ПРОПУСТИЛ, и вот почему (обе ошибки мои, COORD):
    ① искал места конвертации грепом с `head -12` — вывод обрезался, stats.py по алфавиту
       шёл после read-*, и в список правки НЕ ПОПАЛ. Прямое нарушение собственного же
       инварианта VERIFY-AT-SOURCE: «грепнул — читай ВСЕ попадания, не первое».
    ② гард отсеивал ложняки через `grep -v "timezone.utc"` — а прежняя строка содержала
       И astimezone(), И timezone.utc (в dt.replace(tzinfo=...)). Фильтр выбросил ровно
       ту строку, которую гард искал ⇒ ГАРД, КОТОРЫЙ НЕ МОЖЕТ СРАБОТАТЬ (класс STUD).
    Итог: гард отрапортовал «чисто», а локальное время жило дальше и всплыло только
    потому, что человек ГЛАЗАМИ увидел 14:18 при стенных 12:33. Исключающий фильтр в
    гарде опаснее отсутствия гарда: он даёт ложное спокойствие.
    """
    return f"{s} UTC" if s else "—"


def main():
    p = argparse.ArgumentParser(description="Снимок статистики mezosync.db")
        # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать то, чего
    # механизм не умеет). Проверка готовности — ПРОГОН из чужого каталога.

    p.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    p.add_argument("--since-min", type=int, default=50, help="Окно активности, минут")
    p.add_argument("--json", action="store_true", help="Машинный JSON вместо таблицы")
    p.add_argument("--record", action="store_true", help="Записать снимок в stats_log")
    args = p.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")

    s = collect(conn, args.since_min)

    if args.record:
        _record(conn, s)

    conn.close()

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        _print_human(s, args.since_min)


def _q1(conn, sql, params=()):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def collect(conn, since_min):
    win = f"-{int(since_min)} minutes"

    group = _q1(conn, "SELECT value FROM meta WHERE key='group_name'") or "?"
    total_msg = _q1(conn, "SELECT COUNT(*) FROM messages") or 0
    roles = _q1(conn, "SELECT COUNT(DISTINCT writer_role) FROM messages") or 0
    rules = _q1(conn, "SELECT COUNT(*) FROM rules") or 0

    recent = _q1(conn,
        "SELECT COUNT(*) FROM messages WHERE timestamp >= datetime('now', ?)", (win,)) or 0

    # per-role: всего сообщений + время последней ноты (liveness)
    per_role = {}
    try:
        for role, cnt, last in conn.execute(
            "SELECT writer_role, COUNT(*), MAX(timestamp) FROM messages GROUP BY writer_role ORDER BY writer_role"):
            per_role[role] = {"messages": cnt, "last": last}
    except sqlite3.OperationalError:
        pass

    # ошибки двойной записи
    dwerr_open = _q1(conn,
        "SELECT COUNT(*) FROM messages WHERE tags LIKE '%\"DWERR\"%' AND (resolved IS NULL OR resolved=0)") or 0
    dwerr_total = _q1(conn, "SELECT COUNT(*) FROM messages WHERE tags LIKE '%\"DWERR\"%'") or 0

    # phoenix-слепки
    phoenix_cnt = _q1(conn, "SELECT COUNT(*) FROM phoenix") or 0

    # курсоры чтения — отставание ролей
    cursors = {}
    try:
        max_id = _q1(conn, "SELECT MAX(id) FROM messages") or 0
        # В read_cursors живут ДУБЛИ ПО РЕГИСТРУ: живые 'COORD'/'ING'… и мёртвые
        # 'coord'/'ing'… (last_read_id=0, реликт инициализации 2026-07-11 20:59).
        # SQLite сортирует BINARY ⇒ uppercase раньше lowercase ('C'=67 < 'c'=99), и при
        # слиянии через {k.upper(): v} мёртвый ноль ПЕРЕЗАТИРАЛ живой курсор ⇒ у всех
        # behind = max_id − 0. Метрика, по которой решают о продвижении фазы, показывала
        # ОБРАТНОЕ истине: скрывала и тех, кто уже перешёл, и тех, кто отстал.
        # Нашёл ING (#2029) живым фактом: догнал курсор до 0 — метрика не заметила.
        # ЛЕЧИМ КОРЕНЬ, А НЕ ДАННЫЕ (его же довод): удалить дубли — дисциплина, они
        # вернутся при следующей инициализации и метрика снова тихо соврёт. Агрегируем
        # в SQL по регистр-независимому ключу и берём МАКСИМУМ: ноль-дубль проигрывает
        # живому курсору, а не затирает его.
        for role, lr in conn.execute(
                "SELECT UPPER(reader_role), MAX(last_read_id) FROM read_cursors "
                "GROUP BY UPPER(reader_role) ORDER BY 1"):
            cursors[role] = {"read": lr, "behind": max_id - lr}
    except sqlite3.OperationalError:
        pass

    return {
        "group": group,
        "totals": {"messages": total_msg, "roles": roles, "rules": rules, "phoenix": phoenix_cnt},
        "recent_messages": recent,
        "per_role": per_role,
        "dwerr": {"open": dwerr_open, "total": dwerr_total},
        "cursors": cursors,
    }


def _record(conn, s):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL DEFAULT (datetime('now')),
            snapshot_json TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO stats_log (snapshot_json) VALUES (?)",
                 (json.dumps(s, ensure_ascii=False),))
    conn.commit()


def _print_human(s, since_min):
    t = s["totals"]
    print(f"📊 Группа: {s['group']}")
    print(f"   Сообщений: {t['messages']}  ·  Ролей: {t['roles']}  ·  Правил: {t['rules']}  ·  Phoenix: {t['phoenix']}")
    print(f"   Новых за {since_min} мин: {s['recent_messages']}")
    d = s["dwerr"]
    mark = "⚠️" if d["open"] else "✅"
    print(f"   Ошибки DWERR: {mark} open={d['open']} / total={d['total']}")
    print()
    print(f"   {'Роль':<8} {'Сообщ':>6} {'Отставание':>11}  Последняя нота (локальное)")
    print("   " + "-" * 56)
    # writer_role бывает в верхнем регистре, reader_role — в нижнем; сливаем по UPPER.
    per_role = {k.upper(): v for k, v in s["per_role"].items()}
    cursors = {k.upper(): v for k, v in s["cursors"].items()}
    for r in sorted(set(per_role) | set(cursors)):
        pr = per_role.get(r, {})
        cur = cursors.get(r, {})
        msgs = pr.get("messages", 0)
        last = utc_to_local(pr.get("last"))
        behind = cur.get("behind", "—")
        print(f"   {r:<8} {msgs:>6} {str(behind):>11}  {last}")
    print("   (метки БД хранятся в UTC; показаны в локальном времени)")


if __name__ == "__main__":
    main()
