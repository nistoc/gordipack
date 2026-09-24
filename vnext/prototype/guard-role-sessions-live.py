# -*- coding: utf-8 -*-
"""guard-role-sessions-live.py — session_id роли ЖИВ ЛИ ОН в хранилище сессий приложения
(карточка #649).

ПРЕДМЕТ. role_sessions.session_id пишется один раз и переживает возобновление чата —
но сама СЕССИЯ может уйти в архив или пропасть из хранилища (переустановка, чистка), и
запись в реестре продолжает выглядеть годной. Этот гард читает БАЗУ (mode=ro, --db —
без него не запускается: угадывать «живую» базу тут опаснее, чем у команд с известным
дефолтом) и ХРАНИЛИЩЕ (mezo_sessions.py) и называет ролей, у которых session_id либо
не найден в хранилище, либо найден, но сессия АРХИВНАЯ — поимённо, с готовой командой,
какой записью это чинится.

ТРИ ИСХОДА, и они РАЗНЫЕ строки, а не один и тот же цвет:
    чисто ............ у всех ролей с записанным session_id сессия живая — ✅, одна строка
    находки ........... поимённо: роль · session_id · причина (не найден / в архиве) ·
                        команда записи нового
    сверить нечем ..... хранилища нет — строка ТАК И ГОВОРИТ «сверить нечем», а не «всё
                        хорошо»: молчаливое поведение здесь неотличимо от «все живы»,
                        а разница между «проверено и чисто» и «нечем проверить» —
                        ровно то, ради чего гард заведён.

МЯГКИЙ РЕЖИМ `--soft` (по образцу guard-memory-section-refs.py — своей заявки на
встраивание в guard-all.py): код возврата ВСЕГДА 0, каждая строка находки/«сверить
нечем» напечатана с ведущим «⚠️» — тем же приёмом, каким `sub_guard()` в guard-all.py
пробрасывает предупреждающие строки в общий прогон БЕЗ покраски. Без флага — находка
И «сверить нечем» оба красят прогон (код 1): второе — тоже не «чисто», в общем прогоне
молчаливое «нечем проверить» неотличимо от настоящей чистоты.

⛔ Живой базы НЕ КАСАЕТСЯ никаким письмом: соединение открывается mode=ro, вставки
адресов эта проверка не делает — их делает сама роль (signal-templates.py).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_sessions  # noqa: E402

# Команду записи печатаем полным путём — от расположения ЭТОГО файла, не путём машины.
SIGNAL_TOOL = (Path(__file__).resolve().parent / "signal-templates.py").as_posix()


def rows_with_session_id(db_path: str):
    """(role, session_id) — только роли, у кого session_id ЗАПИСАН (не пуст)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT role, session_id FROM role_sessions "
            "WHERE session_id IS NOT NULL AND trim(session_id) != '' "
            "ORDER BY role").fetchall()
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None,
                    help="путь к базе координации, открывается mode=ro; по умолчанию — живая "
                         "база контура от расположения инструмента (норма R15a)")
    ap.add_argument("--session-store", default=None,
                    help="путь к хранилищу сессий приложения (по умолчанию — переменная "
                         "среды MEZO_SESSION_STORE, иначе %%APPDATA%%/Claude/"
                         "claude-code-sessions). Для приёмки на подложном хранилище")
    ap.add_argument("--soft", action="store_true",
                    help="код возврата ВСЕГДА 0, находки печатаются строками «⚠️» "
                         "(так guard-all.py пробрасывает их без покраски прогона)")
    a = ap.parse_args()

    if a.db is None:
        a.db = str(mezo_paths.live_db(__file__))
    prefix = "⚠️ " if a.soft else "🔴 "

    if not os.path.isfile(a.db):
        print(f"⛔ БАЗА НЕ НАЙДЕНА: {a.db}")
        return 0 if a.soft else 1

    try:
        rows = rows_with_session_id(a.db)
    except sqlite3.OperationalError as e:
        print(f"⛔ БАЗА НЕ ОТКРЫВАЕТСЯ ИЛИ В НЕЙ НЕТ role_sessions: {a.db} ({e})")
        return 0 if a.soft else 1

    store = mezo_sessions.read_store(a.session_store)
    if not store.found:
        print(f"{prefix}СВЕРИТЬ НЕЧЕМ: {store.error} — session_id {len(rows)} ролей "
              f"НЕ ПРОВЕРЕНЫ (это не «всё хорошо», а «нечем проверить»)")
        return 0 if a.soft else 1

    findings = []
    for role, sid in rows:
        record = mezo_sessions.find_by_session_id(store, sid)
        if record is None:
            findings.append((role, sid, "НЕ НАЙДЕН в хранилище сессий приложения"))
        elif record.archived:
            findings.append((role, sid, "сессия В АРХИВЕ"))

    if not findings:
        print(f"✅ session_id живы у всех {len(rows)} ролей, у кого он записан "
              f"(хранилище: {store.path})")
        return 0

    for role, sid, why in findings:
        print(f"{prefix}роль {role}: session_id «{sid}» — {why}")
        print(f"   👉 запись нового: python {SIGNAL_TOOL} "
              f"--role {role} --session-id \"local_…\"")
    print(f"ИТОГ: находок {len(findings)} из {len(rows)} ролей с записанным session_id")
    return 0 if a.soft else 1


if __name__ == "__main__":
    sys.exit(main())
