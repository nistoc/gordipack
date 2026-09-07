# -*- coding: utf-8 -*-
"""20260904-phoenix-records-autoincrement — НОМЕР ЗАПИСИ ПАМЯТИ НЕ ПЕРЕИСПОЛЬЗУЕТСЯ.

ПРЕДМЕТ. Карточка #532 (находка @TAXO 04.09 19:00 UTC): у таблицы `phoenix_records`
номер записи — `INTEGER PRIMARY KEY` БЕЗ `AUTOINCREMENT`. В SQLite это значит: после
удаления записи её номер выдаётся как max(id)+1 заново — и достаётся ДРУГОЙ записи.
Ссылка «см. запись #247», ручные поля, проставленные по номеру, — всё тихо указывает
не туда, и вызов проходит с ✅.

ЧТО УЖЕ СДЕЛАНО ДО ЭТОГО ШАГА — и чего он НЕ отменяет: инструмент пересборки держит
номер за ТЕЛОМ записи (дословное совпадение), и при обычном ходе подмены нет. Но это
лекарство от СЛЕДСТВИЯ: схема по-прежнему разрешает выдать «свободный» номер, и любая
правка мимо инструмента (или будущий инструмент, не знающий о правиле) вернёт беду.
⇒ Этот шаг лечит ПРИЧИНУ: `AUTOINCREMENT` — номер выдаётся из счётчика `sqlite_sequence`
и после удаления не повторяется никогда.

СЛОВО ВЛАДЕЛЬЦА. 2026-09-04 20:10 UTC, текстом: «1 + 2 + 3» — в ответ на три
предложения, где пункт 2 — «починить схему номеров по-настоящему: перенос данных
в общей базе». Час перемерен записью разговора, не взят с подсказки хода.

КАК. SQLite не умеет менять ключ на месте — только пересобрать таблицу:
  ① создать `phoenix_records_new` с тем же составом полей и `AUTOINCREMENT`;
  ② перелить строки ВСЕ, с сохранением номеров (INSERT … SELECT);
  ③ сверить ДО записи: число строк, сумма длин тел, отпечаток (id·role·section·body)
     по всем строкам — не сошлось ⇒ откат, ничего не тронуто;
  ④ снести старую, переименовать новую, пересоздать четыре указателя;
  ⑤ выставить счётчик `sqlite_sequence` НЕ НИЖЕ max(id): иначе первый же новый номер
     повторил бы уже выданный;
  ⑥ записать шаг в журнал схемы.
Всё — в одной транзакции. Слово «DROP» здесь стоит внутри пересборки с сохранением
каждой строки, а не как удаление данных; сверка ③ стоит ДО него.

⛔ ЧЕГО НЕ ДЕЛАЕТ: не трогает тело памяти (`phoenix`), не трогает архив, не меняет
ни одного поля записи, не переназначает номера. Ни одна роль не проснётся в сломанное:
пробуждение читает `phoenix.body`, к этой таблице оно не обращается.

🔬 ПРИЁМКА — `vnext-tools/bite-phoenix-records-autoincrement.py`: на КОПИИ базы —
холостой прогон ничего не меняет · применение сохраняет каждую строку · после
удаления последней записи новая получает ДРУГОЙ номер · на НЕмигрированной копии
тот же опыт даёт повтор номера (контроль, что опыт вообще различает).
"""
import argparse
import hashlib
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import record_step, verify, precheck  # noqa: E402

VERSION = "20260904-phoenix-records-autoincrement"

# Состав полей — ДОСЛОВНО тот же, что в шаге 20260904-phoenix-records; меняется одно
# слово в первой строке. Комментарии схемы тут не повторяю: они живут в том шаге и в
# самой базе (sqlite_master хранит текст CREATE), а два экземпляра разошлись бы.
СОЗДАТЬ = """CREATE TABLE phoenix_records_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    role            TEXT NOT NULL,
    section         TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    body_chars      INTEGER NOT NULL,
    happened_at     TEXT,
    source          TEXT,
    expiry_cond     TEXT,
    alive           TEXT NOT NULL DEFAULT 'active',
    revoked_at      TEXT,
    revoked_note    TEXT,
    ord             INTEGER NOT NULL DEFAULT 0,
    origin_chars    INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT NOT NULL
)"""
ПОЛЯ = ("id, role, section, subject, body, body_chars, happened_at, source, expiry_cond, "
        "alive, revoked_at, revoked_note, ord, origin_chars, created_at, created_by")
УКАЗАТЕЛИ = (
    "CREATE INDEX idx_phoenix_records_role    ON phoenix_records(role, section, ord)",
    "CREATE INDEX idx_phoenix_records_subject ON phoenix_records(role, subject)",
    "CREATE INDEX idx_phoenix_records_alive   ON phoenix_records(role, alive)",
    "CREATE INDEX idx_phoenix_records_when    ON phoenix_records(role, happened_at)",
)


def отпечаток(conn, таблица):
    """Число строк · сумма длин тел · хэш всех (id, role, section, body) по порядку id."""
    h = hashlib.sha256()
    n, s = 0, 0
    for id_, role, section, body in conn.execute(
            f"SELECT id, role, section, body FROM {таблица} ORDER BY id"):
        h.update(f"{id_}\x1f{role}\x1f{section}\x1f{body}\x1e".encode("utf-8"))
        n += 1
        s += len(body)
    return n, s, h.hexdigest()[:16]


def уже_с_счётчиком(conn) -> bool:
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='phoenix_records'"
                       ).fetchone()
    return bool(ddl) and "AUTOINCREMENT" in ddl[0].upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    db = os.path.abspath(a.db)
    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'📂 БАЗА: {db}')
    print('=' * 78)
    # ⛔ ПРЕДУСЛОВИЯ — СЛОВАМИ, одной формой со всеми шагами (schema_journal.precheck):
    # файл · база SQLite · журнал схемы. Тот же класс, что @STUD нашёл на карточке #380
    # за час до того, как я написала этот шаг с той же дырой.
    отказ = precheck(db)
    if отказ:
        print(отказ)
        return 1

    conn = sqlite3.connect(db)
    есть = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'phoenix_records' not in есть:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы phoenix_records нет — сначала шаг 20260904-phoenix-records')
    if уже_с_счётчиком(conn):
        print('✅ уже сведено (у phoenix_records стоит AUTOINCREMENT) — делать нечего')
        return
    if 'phoenix_records_new' in есть:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: осталась phoenix_records_new от прерванного прогона — '
                 'разберись рукой, шаг не угадывает')

    до = отпечаток(conn, 'phoenix_records')
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM phoenix_records").fetchone()[0]
    указателей = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
                              "AND tbl_name='phoenix_records' AND name LIKE 'idx_%'").fetchone()[0]
    print(f'записей {до[0]} · знаков тел {до[1]} · отпечаток {до[2]} · max id {max_id} · '
          f'указателей {указателей}')
    print('⚖️ Пересборка таблицы с сохранением КАЖДОЙ строки и номера; тело памяти (phoenix)')
    print('   не трогается вовсе. Сверка отпечатка стоит ДО сноса старой таблицы.')

    if a.dry_run:
        print()
        print('⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.isolation_level = None
    conn.execute("BEGIN")
    try:
        conn.execute(СОЗДАТЬ)
        conn.execute(f"INSERT INTO phoenix_records_new ({ПОЛЯ}) SELECT {ПОЛЯ} FROM phoenix_records")
        после = отпечаток(conn, 'phoenix_records_new')
        if после != до:
            conn.execute("ROLLBACK")
            sys.exit(f'🔴 НЕ СОШЛОСЬ ДО СНОСА — откат, ничего не тронуто: было {до}, стало {после}')
        conn.execute("DROP TABLE phoenix_records")
        conn.execute("ALTER TABLE phoenix_records_new RENAME TO phoenix_records")
        for з in УКАЗАТЕЛИ:
            conn.execute(з)
        # ⑤ счётчик НЕ НИЖЕ max(id): INSERT…SELECT с явными id двигает sqlite_sequence сам,
        # но полагаться на это молча — значит не проверять. Ставлю явно и сверяю.
        conn.execute("INSERT OR REPLACE INTO sqlite_sequence(name, seq) VALUES ('phoenix_records', ?)",
                     (max_id,))
        итог = отпечаток(conn, 'phoenix_records')
        if итог != до:
            conn.execute("ROLLBACK")
            sys.exit(f'🔴 НЕ СОШЛОСЬ ПОСЛЕ ПЕРЕИМЕНОВАНИЯ — откат: было {до}, стало {итог}')
        fp = record_step(conn, VERSION,
                         "phoenix_records: id → INTEGER PRIMARY KEY AUTOINCREMENT, номер записи "
                         "после удаления не переиспользуется (причина карточки #532; следствие "
                         "уже лечил инструмент — номер за телом). Пересборка таблицы с сохранением "
                         f"каждой строки и номера: {до[0]} записей, отпечаток {до[2]}, счётчик "
                         f"выставлен на {max_id}. Слово владельца 2026-09-04 20:10 UTC («1 + 2 + 3»)")
        conn.execute("COMMIT")
    except sqlite3.Error as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        sys.exit(f'🔴 ОТКАТ по ошибке базы: {e}')

    print()
    print(f'✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print('целостность:', conn.execute("PRAGMA integrity_check").fetchone()[0])
    seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='phoenix_records'").fetchone()
    n_idx = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
                         "AND tbl_name='phoenix_records' AND name LIKE 'idx_%'").fetchone()[0]
    print(f'контрольное чтение: записей {итог[0]} (было {до[0]}) · отпечаток {итог[2]} (был {до[2]}) · '
          f'счётчик {seq[0] if seq else "НЕТ"} (max id {max_id}) · указателей {n_idx} (было {указателей})')
    print('   AUTOINCREMENT в схеме:', '✅ есть' if уже_с_счётчиком(conn) else '🔴 НЕТ')


if __name__ == '__main__':
    sys.exit(main())
