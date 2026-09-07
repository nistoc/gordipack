# -*- coding: utf-8 -*-
"""20260830-lease-waits — ОЖИДАНИЕ ИНСТРУМЕНТА СТАНОВИТСЯ ЗАПИСЬЮ, А НЕ ПАМЯТЬЮ ЖДУЩЕГО.

ПОВОД (карточка #488, слово владельца 2026-08-30 11:55 UTC «1 + 2»). Взятие инструмента
расходится само — кто упёрся, тот увидел. СНЯТИЕ не расходится никак: механизм не знает,
что кто-то ждёт, и сказать ему некому.

📏 ЗАМЕР 2026-08-30 11:36 UTC по всей истории объявлений:
    объявлений всего ................... 127, снятых 127
    снято ДО объявленного срока ........ 126 = 99%
    зазор «снято → срок» ............... медиана 36.7 мин · среднее 39.7 · max 271.7
    сумма «числится занятым, а свободен» 83.5 часа
⚖️ 83.5 часа — НЕ потерянное время, а окно, в котором инструмент числился занятым,
будучи свободным. Потеря случается только тогда, когда в этом окне кто-то в него упёрся.

🔴 И ГЛАВНОЕ, ПОЧЕМУ ЭТОГО МАЛО СКАЗАТЬ СЛОВАМИ. Слова УЖЕ СТОЯТ: после замера @OPSSRE
(29.08, записка #4183 — четыре объявления из четырёх сняты досрочно, четверо ждали зря)
в текст отказа вписана строка «срок — верхняя граница: не жди срока, спроси состояние».
Она была на месте 30.08, и ДВЕ роли, прочитав отказ, всё равно написали в ленте, что
дождутся срока (@STUD 11:10, @CHROME 11:23; объявление снято в 11:28:56, срок стоял 12:36).
⇒ Предупреждение на пути не сработало, потому что оно требует ЛИШНЕГО ДЕЙСТВИЯ — пойти
и спросить. Механизм, о котором надо ВСПОМНИТЬ, умирает: четыре таких в контуре имеют
НОЛЬ вызовов на тысячах записей.

ЧТО ДОБАВЛЯЕТ ШАГ: таблицу tool_lease_waits — след отказа. Она пишется САМИМ отказом,
без отдельного действия ждущего: он уже позвал инструмент, и это и есть его заявка.

⛔ ЧЕГО ЭТОТ ШАГ НЕ ДЕЛАЕТ: ничего не запрещает и никого ни к чему не обязывает.
Снятие объявления без оповещения ждущих ПРОХОДИТ — инструмент, не давший роли снять
своё объявление, хуже молчания.
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

VERSION = "20260830-lease-waits"
TABLE = "tool_lease_waits"

CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id          INTEGER PRIMARY KEY,
    lease_id    INTEGER NOT NULL,
    role        TEXT,                -- ⚖️ может быть NULL: имя ждущего не всегда узнаваемо,
                                     -- см. lease.py::_who_is_calling. Пустое имя честнее
                                     -- выдуманного — по нему ждущему просто нечего показать
    tool        TEXT    NOT NULL,
    refused_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""
# Отбор идёт по «чьё объявление» и «кому показать» — оба столбца в указателе.
INDEX = (f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_lease_role "
         f"ON {TABLE} (lease_id, role)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import mezo_paths
    db = mezo_paths.resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))
    есть = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone()
    print(f"база: {db}")
    print(f"таблица {TABLE}: {'УЖЕ ЕСТЬ' if есть else 'нет — будет создана'}")
    живых = conn.execute(
        "SELECT COUNT(*) FROM tool_leases "
        "WHERE released_at IS NULL AND until_utc > datetime('now')").fetchone()[0]
    print(f"живых объявлений сейчас: {живых} — их прошлые отказы в след НЕ попадут, "
          f"и это честно: следа не было")
    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута.")
        return
    записан = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?",
                           (VERSION,)).fetchone()
    if есть and записан:
        print("\n⚖️ Всё есть и след есть — шаг ничего не меняет.")
        return
    if есть and not записан:
        fp = record_step(conn, VERSION, f"{TABLE}: заведена ранее без журнала; "
                         f"след восстановлен задним числом", backdated=True)
        conn.commit()
        print(f"✅ След восстановлен. отпечаток: {fp}")
        return
    conn.execute("BEGIN")
    conn.execute(CREATE)
    conn.execute(INDEX)
    fp = record_step(
        conn, VERSION,
        "tool_lease_waits: отказ при взятии занятого инструмента САМ записывает ожидание "
        "(карточка #488). Повод: снятие объявления не доходит до ждущих — 126 объявлений "
        "из 127 сняты раньше срока, медиана зазора 36.7 мин. Предупреждение словами в тексте "
        "отказа уже стояло с 29.08 и не помогло: две роли 30.08, прочитав его, всё равно "
        "ждали срока. Ожидание перестаёт быть памятью ждущего и становится записью")
    conn.commit()
    print(f"\n✅ Таблица {TABLE} создана, шаг записан в журнал. отпечаток: {fp}")


if __name__ == "__main__":
    main()
