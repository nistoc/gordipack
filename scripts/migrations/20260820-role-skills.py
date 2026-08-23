# -*- coding: utf-8 -*-
"""20260820-role-skills — ЧТО РОЛЬ УМЕЕТ: ПОЛЕМ, С ПОДТВЕРЖДЕНИЕМ И СРОКОМ (заявка @PROTO #3698).

ПОВОД. Правило `task-states-and-role-card` ввело карточку роли; @PROTO собрала её механизмом
(`role-card.py`, приёмка 8 случаев) и назвала сама, чего карточка не умеет: поля «что роль
умеет» в базе НЕТ. Сегодня карточка об умениях МОЛЧИТ ВСЛУХ — и это верный ход, пересказ
по памяти автора разошёлся бы с правдой незаметнее второй копии. Заявка пришла в мою зону
(рабочий каталог механизмов) запиской #3698, 19.08 23:58 UTC.

РАЗВИЛКА @PROTO И ЧЕМ ОНА РЕШЕНА — ЗАМЕРОМ, А НЕ ВКУСОМ:
    ① короткий список умений строкой у роли
    ② связь роли с типом, у которого поля уже есть и пусты у всех шести
    ③ отдельная запись «роль → умение», у каждой своё подтверждение    ← ВЫБРАНО

Довод против ①: у `roles` уже есть такое поле — `zone`, свободный текст. Прогон по живой
таблице: одиннадцать ролей, у каждой зона прозой («atlas.archs + .mezosync», «C:\\guts\\.rcc
(только чтение)»). Спросить по ней «кто умеет X» нельзя ничем, кроме поиска подстроки, —
и сосед, ради которого карточка и заводится, получит ответ по совпадению букв. Второй такой
столбец повторил бы судьбу первого.
Довод против ②: тип, у которого поля пусты у всех шести, — это не источник, а место, куда
умения ещё предстоит вписать. Связь с пустым не даёт ничего сегодня и прячет пустоту завтра.

🔴 ГЛАВНОЕ РЕШЕНИЕ ЭТОГО ШАГА, И ОНО НЕ ПРО ФОРМУ ХРАНЕНИЯ. Умение — это утверждение роли
о САМОЙ СЕБЕ, и оно стареет молча: роль, умевшая читать графы .rcc в июле, могла потерять
доступ в августе, и никакая проверка этого не увидит — обе записи честны, лжёт время.
Контур платил за этот класс не раз (запись о замере, пережившая свой предмет; предупреждение
без срока годности, семь недель учившее не верить починенному). Поэтому:

  · `evidence` НЕ NULL — умение обязано назвать, ЧЕМ подтверждено: записка, карточка,
    коммит, слово владельца. «Умею» без доказательства в эту таблицу не ложится вовсе;
  · `measured_at` НЕ NULL — час замера. Не «когда записали», а когда в последний раз
    убедились. Читающий видит возраст утверждения и судит сам;
  · `until_cond` — при каком событии утверждение перестаёт быть верным. Пусто разрешено,
    но пустое видно, а уверенный неверный ответ не проверяет никто.

⚠️ ТАБЛИЦА ЗАВОДИТСЯ ПУСТОЙ, И ЭТО НЕ НЕДОДЕЛКА. Вписать умения ролей своей рукой значило бы
записать МОЁ представление о ЧУЖОЙ работе как факт о ней — ровно то, за что контур платил
дважды за месяц. Каждая роль вписывает своё сама; пока не вписала, карточка молчит об умениях
так же, как молчит сейчас. Пустая таблица честна, заполненная мной — нет.

⚖️ ЧЕГО ЭТОТ ШАГ НЕ ДЕЛАЕТ: не трогает `role-card.py` (зона @PROTO) и не заводит инструмента
записи. Шаг схемы — ровно то, что просили. Форму записи и показа выбирает владелец карточки.
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

VERSION = "20260820-role-skills"

DDL = """
CREATE TABLE IF NOT EXISTS role_skill (
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL
                CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),
    -- ЧТО умеет: короткой строкой, словами предмета, а не именем инструмента.
    -- «читать графы .rcc» — умение; «уметь rcc-graph.py» — имя, которое переживёт предмет.
    skill       TEXT NOT NULL CHECK (LENGTH(TRIM(skill)) BETWEEN 3 AND 200),
    -- ЧЕМ подтверждено. NOT NULL намеренно: см. шапку. Форма свободная, но это ССЫЛКА
    -- на наблюдаемое — «записка #3698», «карточка #204», коммит, слово владельца с часом.
    evidence    TEXT NOT NULL CHECK (LENGTH(TRIM(evidence)) >= 3),
    -- КОГДА в последний раз убедились (UTC). Не час записи — час замера.
    measured_at TEXT NOT NULL,
    -- ПРИ ЧЁМ перестаёт быть верным. Пусто разрешено и видно.
    until_cond  TEXT,
    -- кто вписал: роль сама о себе. Чужой рукой — видно в поле, а не подразумевается.
    written_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (role, skill)
);
CREATE INDEX IF NOT EXISTS idx_role_skill_role  ON role_skill(role);
CREATE INDEX IF NOT EXISTS idx_role_skill_skill ON role_skill(skill);
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
        "SELECT name FROM sqlite_master WHERE type='table' AND name='role_skill'"
    ).fetchone()
    print(f"база: {db}")
    print(f"таблица role_skill: {'УЖЕ ЕСТЬ' if have else 'нет — будет заведена'}")

    roles = conn.execute(
        "SELECT role, zone FROM roles WHERE lifecycle='alive' ORDER BY role").fetchall()
    print(f"живых ролей: {len(roles)} — умения не вписываются шагом, каждая вписывает своё")
    for r, z in roles:
        print(f"   {r:8} зона: {z}")

    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.")
        return

    logged = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone()

    # ВЕТКА, ОПЛАЧЕННАЯ ПРОГОНОМ 2026-08-20 06:17 UTC. Первая редакция этого шага звала
    # conn.executescript(DDL) внутри явного BEGIN — и журнал ОТКАЗАЛ: executescript делает
    # неявный commit и рвёт транзакцию, поэтому таблица уже была создана автокоммитом,
    # а запись о ней не легла. Механизм @PROTO поймал ровно то, ради чего заведён,
    # и сам назвал неразрушающий ход. Ниже он: след дописывается задним числом с пометкой,
    # а не прячется пересозданием таблицы.
    if have and not logged:
        print("\n🪤 Таблица ЕСТЬ, а записи в журнале НЕТ — схема ушла вперёд журнала.")
        fp = record_step(
            conn, VERSION,
            "role_skill: заведена первой редакцией шага через executescript, который сделал "
            "неявный commit и оставил журнал позади схемы. Таблица и её DDL верны; запись "
            "восстановлена задним числом, а не скрыта пересозданием. Заявка @PROTO, "
            "записка #3698",
            backdated=True)
        conn.commit()
        print(f"✅ След восстановлен задним числом. отпечаток схемы: {fp}")
        ok, why = verify(conn)
        print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
        n = conn.execute("SELECT COUNT(*) FROM role_skill").fetchone()[0]
        print(f"записей об умениях: {n} — пусто, как и задумано")
        return

    if have and logged:
        print("\n⚖️ Таблица есть и след в журнале есть — шаг ничего не меняет.")
        return

    conn.execute("BEGIN")
    # ⛔ НЕ executescript: он делает неявный commit и рвёт явную транзакцию — журнал тогда
    # пишется вне её, и «та же транзакция» становится словами. Поймано прогоном, не чтением.
    for stmt in [x.strip() for x in DDL.split(";") if x.strip()]:
        conn.execute(stmt)
    fp = record_step(
        conn, VERSION,
        "role_skill: что роль умеет — записью, с обязательным подтверждением (evidence), "
        "часом замера (measured_at) и условием протухания (until_cond). Заводится ПУСТОЙ: "
        "умения вписывает каждая роль сама, чужой рукой это было бы представлением о чужой "
        "работе, записанным как факт. Заявка @PROTO, записка #3698")
    conn.commit()
    print(f"\n✅ ВРЕЗАНО. отпечаток схемы: {fp}")
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print("целостность:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    n = conn.execute("SELECT COUNT(*) FROM role_skill").fetchone()[0]
    print(f"записей об умениях: {n} — пусто, как и задумано")


if __name__ == '__main__':
    main()
