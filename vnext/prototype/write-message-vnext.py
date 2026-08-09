# -*- coding: utf-8 -*-
"""
write-message-vnext.py — ПРОТОТИП записи ноты в v-next: R15a + адресат полем + закрытие вопроса.

Доказывает ТРИ свойства (все — из оплаченных фрикций, ни одно не из головы):
  · R15a  — путь к БД не зависит от CWD (было: роль звала из чужого каталога и молча
            попадала в другую живую БД — F20);
  · R3/Э-Б — адресат ПОЛЕМ при записи (`--to`/`--cc`/`--broadcast`), а не прозой в теле.
            Замер 05.08: конвенция уже сложилась сама (0 % нот без адресата за последние
            200), поле её УЗАКОНИВАЕТ, а не навязывает — и `addressed_by='field'` отличает
            заявленное от восстановленного регекспом;
  · Э-Г/B — `--closes <id>`: закрытие вопроса гасит срочность исходной ноты.

⛔ ГЛАВНОЕ ПРО `--closes` — ПОЧЕМУ ЭТО НЕ ОТДЕЛЬНАЯ КОМАНДА:
   прежнее поле `resolved` не заполнялось (1 нота из 1483), и я объяснил это дисциплиной —
   ошибочно. Замер 05.08: его НЕЧЕМ поставить, единственный писатель `check-errors.py --resolve`
   бьёт по `WHERE tags LIKE '%"DWERR"%'`. Отдельная команда «пометь закрытым» повторила бы ту же
   судьбу: лишний ход не делают не из лени — его не делают. Поэтому закрытие прицеплено к тому,
   что роль УЖЕ делает, отвечая: пишет ответную ноту и добавляет одно слово.

⛔ Живую БД не открывает: прототип пишет только в песочницу.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # хелпер лежит рядом со скриптом
from mezo_paths import resolve_db                           # noqa: E402
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()


def known_roles(con) -> set:
    return {r for r, in con.execute("SELECT role FROM roles")}


def write(con, role, body, tags_json, priority, to, cc, broadcast, closes):
    """Возвращает (ok, message). Все отказы — ДО записи: частичная нота хуже ненаписанной."""
    roles = known_roles(con)
    for r in list(to) + list(cc):
        if r not in roles:
            return False, (f"⛔ ОТКАЗ: роль {r} не в реестре (есть: {', '.join(sorted(roles))}). "
                           f"Адресат опечаткой = нота-призрак: отправлена и не дошла никому.")
    if closes is not None:
        row = con.execute("SELECT writer_role, priority FROM messages WHERE id = ?",
                          (closes,)).fetchone()
        if row is None:
            return False, f"⛔ ОТКАЗ: закрываемой ноты #{closes} нет в ленте."
        if con.execute("SELECT 1 FROM message_closure WHERE message_id = ?", (closes,)).fetchone():
            return False, (f"⛔ ОТКАЗ: #{closes} уже закрыта. Повторное закрытие затёрло бы "
                           f"того, кто закрыл первым — это стирание факта.")

    # Защита ДВОЙНАЯ: проверки выше + контракт схемы (PK/FK/CHECK). Второй слой не
    # избыточность: проверку в CLI обходит любой второй писатель — этот класс контур уже
    # оплачивал (`.upper()` жил в одном скрипте, расщепление заводил любой другой).
    # Отказ схемы обязан выглядеть как отказ, а не как падение стектрейсом на роль.
    try:
        cur = con.execute(
            "INSERT INTO messages (writer_role, body_md, tags, priority, broadcast, addressed_by) "
            "VALUES (?,?,?,?,?, 'field')", (role, body, tags_json, priority, int(broadcast)))
        mid = cur.lastrowid
        for r in to:
            con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (?,?,'to')",
                        (mid, r))
        for r in cc:
            con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (?,?,'cc')",
                        (mid, r))
        note = ""
        if closes is not None:
            con.execute("INSERT INTO message_closure (message_id, closed_by, closed_role) "
                        "VALUES (?,?,?)", (closes, mid, role))
            was = con.execute("SELECT priority FROM messages WHERE id = ?", (closes,)).fetchone()[0]
            note = (f"\n   🔻 #{closes} закрыта этой нотой: срочность {was} → normal "
                    f"(priority в ноте НЕ переписан — гаснет производная urgency, история цела)")
        con.commit()
    except sqlite3.IntegrityError as e:
        con.rollback()
        return False, (f"⛔ ОТКАЗ СХЕМЫ (второй слой защиты сработал, значит проверка выше "
                       f"была обойдена или неполна): {e}")
    addr = (f"to={sorted(to) or '—'} cc={sorted(cc) or '—'}"
            f"{' broadcast' if broadcast else ''}")
    return True, f"OK #{mid} [{role}] {addr} priority={priority}{note}"


def main():
    ap = argparse.ArgumentParser(description="Записать ноту (прототип v-next)")
    ap.add_argument("--db", default=None,
                    help="необязателен: по умолчанию — БД рядом со скриптом (см. mezo_paths)")
    ap.add_argument("--role", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--priority", default="normal", choices=["normal", "high", "critical"])
    ap.add_argument("--to", default="", help="адресаты через запятую (требуют действия)")
    ap.add_argument("--cc", default="", help="в копию через запятую (для сведения)")
    ap.add_argument("--broadcast", action="store_true", help="касается всех — ЯВНО, а не молчанием")
    ap.add_argument("--closes", type=int, default=None,
                    help="id ноты, вопрос которой эта нота закрывает (гасит её срочность)")
    args = ap.parse_args()

    db = resolve_db(args.db, __file__)
    if db == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Прототип работает только по песочнице.")

    role = args.role.upper()          # R5: нормализация в одной точке входа
    split = lambda s: {x.strip().upper() for x in s.split(",") if x.strip()}
    tags = json.dumps([t.strip() for t in args.tags.split(",") if t.strip()], ensure_ascii=False)

    con = sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=5)
    con.execute("PRAGMA foreign_keys = ON")
    ok, msg = write(con, role, args.body, tags, args.priority,
                    split(args.to), split(args.cc), args.broadcast, args.closes)
    con.close()
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
