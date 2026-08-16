# -*- coding: utf-8 -*-
"""lease.py — ОБЪЯВЛЕННАЯ АРЕНДА ИНСТРУМЕНТА НА ВРЕМЯ ПРАВКИ И ОТЛАДКИ (карточка #204).

Вопрос владельца 2026-08-16 09:59 UTC: пока роль правит инструмент, другие могут его звать
и не знать, что он в отладке; нужно уметь временно закрывать — и уметь СПРОСИТЬ, освободилось ли.

ЧТО ЭТОТ МОДУЛЬ ЗАКРЫВАЕТ И ЧЕГО НЕ ЗАКРЫВАЕТ — сказано до кода, чтобы не пришлось выяснять:
  ✅ закрывает окно «СМЫСЛ ИЗМЕНИЛСЯ, А ЗОВУЩИЙ НЕ ЗНАЕТ» — широкое и дорогое. Оплачено
     16.08 мной же: я менял смысл поля в живом инструменте, роли в это время могли его звать.
  ⛔ НЕ закрывает окно «файл записан наполовину» — оно узкое (миллисекунды) и закрывается
     не арендой, а атомарной установкой: `atomic-install.py` пишет рядом и ПЕРЕИМЕНОВЫВАЕТ.
  ⛔ НЕ блокирует файл средствами системы: наши инструменты — короткоживущие программы,
     они не держат файл открытым, и замок ОС им нечего защищать.

ТРИ СВОЙСТВА, БЕЗ КОТОРЫХ АРЕНДА ВРЕДНЕЕ ОТСУТСТВИЯ:
  ① ИСТЕКАЕТ САМА. Забытая аренда не имеет права держать контур: вечный запрет учит
     обходить запреты, и первым обойдёт тот, кому нужнее всего.
  ② ЧИТАЮЩЕМУ — ПРЕДУПРЕЖДЕНИЕ, НЕ ЗАПРЕТ. Отняв у роли чтение ленты и памяти, мы отнимаем
     ровно тот способ, которым она узнаёт о работах. Запрет — только пишущим.
  ③ ОТКАЗ НЕСЁТ ИМЯ, ПРИЧИНУ И ГОТОВЫЙ ВОПРОС. «Занято» без этого — тупик: ждать нечего,
     спросить некого. Поэтому в отказе печатается и команда, которой спрашивают статус.

Пишущим считается инструмент, чьё имя НЕ похоже на читающее (guard-/check-/read-/bite-/
измерители). Эвристика названа вслух: она может ошибиться в сторону лишней строгости
(читающий инструмент получит отказ вместо предупреждения) — и НЕ может ошибиться
в сторону тишины, а это верная сторона для механизма безопасности.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

# Имя читающего инструмента. Тот же словарь, что у проверки печатных форм, — намеренно:
# два разных списка «кто читает» разъедутся, и разъедутся молча.
READING = re.compile(
    r"^(guard-|check-|measure-|read-|bite-|stats\.|feed\.|unsaved\.|dashboard\.|export-|"
    r"refs_check|db-q|periscope|restore-verify|[a-z_]+_layer\.)", re.I)

# Роль, от чьего имени идёт вызов: своя аренда НЕ мешает работать (иначе арендатор
# не смог бы отлаживать то, что арендовал — это сделало бы аренду бессмысленной).
ROLE_ENV = "MEZO_ROLE"
# Аварийный обход, названный вслух: аренда — механизм координации, а не защита от врага.
# Если механизм сам сломается, у роли обязан быть ход. Обход ГРОМКИЙ: печатает предупреждение.
BYPASS_ENV = "MEZO_LEASE_BYPASS"


def _live(con, tool: str):
    """Живые аренды, накрывающие этот инструмент. Истёкшие не возвращаются — они мертвы."""
    try:
        rows = con.execute(
            "SELECT id, role, tools, reason, taken_at, until_utc FROM tool_leases "
            "WHERE released_at IS NULL AND until_utc > datetime('now') ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return []          # таблицы нет (контур старше шага) — это не отказ, это «аренд нет»
    return [r for r in rows if tool in (r[2] or "").split()]


def check(db, script_file, quiet: bool = False) -> None:
    """Проверка перед работой. Зовётся из ЕДИНОЙ точки (mezo_paths.resolve_db).

    Пишущему инструменту — отказ (код 3), читающему — предупреждение в stderr.
    Своя аренда и просроченная не мешают никому.
    """
    tool = Path(script_file).name
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
    except sqlite3.Error:
        return                                   # базы нет — об этом скажет сам инструмент
    try:
        live = _live(con, tool)
    finally:
        con.close()
    if not live:
        return

    caller = (os.environ.get(ROLE_ENV) or "").upper()
    mine = [r for r in live if (r[1] or "").upper() == caller and caller]
    if mine:
        return                                   # арендатор работает со своим — норма

    _id, role, tools, reason, taken_at, until = live[0]
    scripts = Path(script_file).resolve().parent
    ask = f"python {(scripts / 'lease.py').as_posix()} status"
    head = (f"🔒 {tool} В РАБОТЕ у роли {role} до {until} UTC\n"
            f"   причина ..... {reason}\n"
            f"   взято ....... {taken_at} UTC\n"
            f"   закрыто ..... {tools}\n"
            f"   спросить, освободилось ли: {ask}")

    if os.environ.get(BYPASS_ENV):
        print(head + "\n   ⚠️ ОБХОД ВКЛЮЧЁН переменной " + BYPASS_ENV
              + " — работаю, но арендатор об этом не знает.", file=sys.stderr)
        return

    if READING.match(tool):
        if not quiet:
            print(head + "\n   ⚖️ Инструмент ЧИТАЮЩИЙ — работаю дальше. Знай: поведение "
                         "может меняться прямо сейчас.", file=sys.stderr)
        return

    print(head + "\n   ⛔ Инструмент ПИШУЩИЙ — отказ: правка во время чужой отладки "
                 "смешала бы две работы.\n"
                 "   Дождись снятия (аренда истекает сама) или договорись с арендатором "
                 "запиской.", file=sys.stderr)
    sys.exit(3)


# ── командная часть: взять · снять · посмотреть ──────────────────────────────
def _cli() -> int:
    import argparse
    from mezo_paths import resolve_db

    ap = argparse.ArgumentParser(description="аренда инструмента на время правки (#204)")
    ap.add_argument("cmd", choices=["take", "release", "status"])
    ap.add_argument("--db", default=None)
    ap.add_argument("--role", help="кто берёт (для take/release)")
    ap.add_argument("--tools", help="имена файлов через пробел: пайплайн — одной арендой")
    ap.add_argument("--reason", help="зачем: без причины ждать нечего")
    ap.add_argument("--minutes", type=int, default=60,
                    help="на сколько минут (по умолчанию 60; аренда истекает САМА)")
    ap.add_argument("--id", type=int, help="какую аренду снять")
    ap.add_argument("--note", help="что изменилось — читает тот, кто ждал")
    a = ap.parse_args()

    db = resolve_db(a.db, __file__)
    con = sqlite3.connect(db, timeout=5)

    if a.cmd == "status":
        rows = con.execute(
            "SELECT id, role, tools, reason, taken_at, until_utc, released_at, note "
            "FROM tool_leases ORDER BY id DESC LIMIT 20").fetchall()
        live = [r for r in rows if r[6] is None]
        now = con.execute("SELECT datetime('now')").fetchone()[0]
        active = [r for r in live if r[5] > now]
        print(f"🔑 АРЕНДЫ на {now} UTC: живых {len(active)} "
              f"(показаны последние {len(rows)} записей всего)")
        if not active:
            print("   живых аренд НЕТ — инструменты свободны. "
                  "(Истёкшие не показаны живыми: аренда гаснет сама.)")
        for r in rows:
            state = ("🔓 снята " + r[6] if r[6] else
                     ("🔒 ЖИВА" if r[5] > now else "⌛ истекла сама"))
            print(f"  #{r[0]} {state} · {r[1]} · до {r[5]} UTC · {r[2]}")
            print(f"      причина: {r[3]}" + (f" · итог: {r[7]}" if r[7] else ""))
        con.close()
        return 0

    if not a.role:
        sys.exit("ERR: нужен --role")

    if a.cmd == "take":
        if not a.tools or not a.reason:
            sys.exit("ERR: нужны --tools и --reason. Аренда без причины неоспорима: "
                     "ждущий не может понять, чего ждёт.")
        if a.minutes <= 0 or a.minutes > 480:
            sys.exit("ERR: срок 1–480 минут. Аренда на сутки — это не аренда, а запрет; "
                     "запрет обходят.")
        cur = con.execute(
            "INSERT INTO tool_leases (role, tools, reason, until_utc) "
            "VALUES (?, ?, ?, datetime('now', ?))",
            (a.role.upper(), a.tools.strip(), a.reason.strip(), f"+{a.minutes} minutes"))
        con.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) "
                    "VALUES (?, 'lease_take', ?, ?)",
                    (a.role.upper(), a.tools.strip(),
                     f"{a.minutes} мин · {a.reason.strip()}"))
        con.commit()
        row = con.execute("SELECT until_utc FROM tool_leases WHERE id=?",
                          (cur.lastrowid,)).fetchone()
        print(f"🔒 АРЕНДА #{cur.lastrowid} взята ролью {a.role.upper()} до {row[0]} UTC")
        print(f"   закрыто: {a.tools.strip()}")
        print(f"   ⚖️ Читающим — предупреждение, пишущим — отказ. Истекает САМА: "
              f"забыть снять не страшно.")
        print(f"   снять: python {Path(__file__).resolve().as_posix()} release "
              f"--role {a.role.upper()} --id {cur.lastrowid} --note \"что изменилось\"")
        con.close()
        return 0

    # release
    if not a.id:
        sys.exit("ERR: нужен --id (посмотри: lease.py status)")
    row = con.execute("SELECT role, released_at FROM tool_leases WHERE id=?", (a.id,)).fetchone()
    if not row:
        sys.exit(f"ERR: аренды #{a.id} нет")
    if row[1]:
        sys.exit(f"ERR: аренда #{a.id} уже снята {row[1]}")
    if row[0].upper() != a.role.upper():
        sys.exit(f"⛔ ОТКАЗ: аренда #{a.id} взята ролью {row[0]}, а снять просит {a.role.upper()}.\n"
                 f"   Чужую аренду не снимают молча: договорись запиской. "
                 f"Она в любом случае истечёт сама.")
    con.execute("UPDATE tool_leases SET released_at = datetime('now'), note = ? WHERE id = ?",
                (a.note, a.id))
    con.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) "
                "VALUES (?, 'lease_release', ?, ?)",
                (a.role.upper(), str(a.id), a.note or "без пометки"))
    con.commit()
    con.close()
    print(f"🔓 АРЕНДА #{a.id} снята. Инструменты свободны."
          + (f"\n   итог: {a.note}" if a.note else ""))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
