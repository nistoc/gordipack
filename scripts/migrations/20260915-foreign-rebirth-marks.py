# -*- coding: utf-8 -*-
"""20260915-foreign-rebirth-marks — УБОРКА ЧУЖИХ ОТМЕТОК ПЕРЕСОЗДАНИЯ КОНТУРА ATLAS
(карточка #640 ②, парный шаг к правке различителя в 20260905-phoenix-history-archive.py
той же карточки).

ПРЕДМЕТ. До правки 2026-09-15 шаг `20260905-phoenix-history-archive.py` засевал 18 отметок
пересоздания ролей КОНТУРА ATLAS в ЛЮБУЮ базу, где есть `phoenix_history` и ещё нет
`role_rebirths`, — без разбора контура. Соседи, применившие шаг ДО этой правки, уже несут
эти 18 строк под своими же именами ролей (замер: tapas — 18 строк, AIA — 18 строк, причём
у AIA роль COORD (которой у них нет) переведена их собственным нормализатором имён в
COORD-A — «перевод» имени соседа не спасает от находки: различитель ниже ловит ОБА случая,
потому что судит не имя роли, а автора и источник записи).

ЧТО ДЕЛАЕТ ШАГ
  · заводит `role_rebirths_foreign` (поля `role_rebirths` + `moved_at` · `moved_by` · `reason`);
  · в контуре НЕ Atlas переносит в неё строки `role_rebirths`, у которых
    `noted_by = 'tool:20260905-phoenix-history-archive'` И `source LIKE 'transcript:%'`
    (различитель — по АВТОРУ И ИСТОЧНИКУ записи, НЕ по имени роли: так ловятся и чужие
    имена, и переведённые на свои — случай AIA, COORD → COORD-A);
  · в контуре Atlas таблицу заводит, но НЕ переносит НИЧЕГО — те же строки там СВОИ
    (контур Atlas — отметки свои, переносить нечего);
  · строки НЕ УДАЛЯЮТСЯ безвозвратно — переносятся: лежат в `role_rebirths_foreign` знак
    в знак, перенос — одной транзакцией;
  · записывает себя в журнал схемы В ЛЮБОМ контуре; текст записи называет, сколько
    перенесено НА ДЕЛЕ, а не число из докстроки.

⛔ ЧЕГО НЕ ДЕЛАЕТ. Не трогает отметки, поставленные САМИМ контуром (`rebirth-mark.py`:
`source='rebirth-mark'`, `noted_by`=имя роли) — встречный случай, у них другой автор,
различитель их не видит по построению. Не решает, что делать со строками ДАЛЬШЕ
(показывать владельцу соседа / когда-нибудь убрать) — это решение владельца контура-соседа;
здесь только перенос без потери, разрушающего своей рукой шаг не делает.

    python <КОНТУР>/.mezosync/scripts/migrations/20260915-foreign-rebirth-marks.py --dry-run
    python <КОНТУР>/.mezosync/scripts/migrations/20260915-foreign-rebirth-marks.py
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

VERSION = "20260915-foreign-rebirth-marks"
# Тот же различитель контура, что у 20260905-phoenix-history-archive.py (карточка #640).
ATLAS_GROUP_NAME = "atlas"
# Различитель ЧУЖОЙ ОТМЕТКИ — по АВТОРУ ЗАПИСИ и ИСТОЧНИКУ, не по имени роли (карточка #640,
# просьба AIA: их нормализатор переводит имя соседа COORD → COORD-A, а автор и источник —
# нет; отметки САМОГО контура, source='rebirth-mark', под этот различитель не попадают).
FOREIGN_NOTED_BY = "tool:20260905-phoenix-history-archive"
FOREIGN_SOURCE_LIKE = "transcript:%"

SCHEMA_QUERIES = (
    """CREATE TABLE role_rebirths_foreign (
    -- id ТОТ ЖЕ, что был в role_rebirths: ссылка «отметка #N» в чужой записке не протухает.
    id        INTEGER PRIMARY KEY,
    role      TEXT NOT NULL,
    at        TEXT NOT NULL,
    source    TEXT NOT NULL,
    noted_by  TEXT NOT NULL,
    noted_at  TEXT NOT NULL,
    -- ЧТО ДОБАВЛЯЕТ ПЕРЕНОС: когда, чьей рукой и почему унесено.
    moved_at  TEXT NOT NULL DEFAULT (datetime('now')),
    moved_by  TEXT NOT NULL,
    reason    TEXT NOT NULL
)""",
    "CREATE INDEX idx_role_rebirths_foreign_role ON role_rebirths_foreign(role, at)",
)


def group_name_of(conn):
    """Имя контура из meta.group_name — None, если таблицы meta нет или строки в ней нет."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'meta' not in tables:
        return None
    row = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    return row[0] if row else None


def actor_of():
    """Чья рука. MEZO_ROLE, если роль назвалась; иначе — инструмент, не выдуманная роль."""
    role = (os.environ.get("MEZO_ROLE") or "").strip()
    return role.upper() if role else f"tool:{VERSION}"


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
    if not os.path.isfile(db):
        sys.exit(f'⛔ НЕ ЗАПУСТИЛСЯ: БД не найдена: {db}')

    conn = sqlite3.connect(db)
    existing_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'role_rebirths' not in existing_tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы role_rebirths нет — прогони сперва '
                 'migrations/20260905-phoenix-history-archive.py')
    if 'role_rebirths_foreign' in existing_tables:
        print('✅ уже сведено (таблица role_rebirths_foreign на месте) — делать нечего')
        return

    group_name = group_name_of(conn)
    is_atlas = group_name == ATLAS_GROUP_NAME

    candidates = conn.execute(
        "SELECT id, role, at, source, noted_by, noted_at FROM role_rebirths "
        "WHERE noted_by = ? AND source LIKE ? ORDER BY role, at",
        (FOREIGN_NOTED_BY, FOREIGN_SOURCE_LIKE)).fetchall()
    own_marks_n = conn.execute(
        "SELECT count(*) FROM role_rebirths WHERE source = 'rebirth-mark'").fetchone()[0]

    to_move = [] if is_atlas else list(candidates)
    by_role = {}
    for row in to_move:
        by_role[row[1]] = by_role.get(row[1], 0) + 1
    by_role_text = (', '.join(f'{r} {n}' for r, n in sorted(by_role.items())) if by_role else '(нет)')

    if is_atlas:
        print(f'   контур Atlas — отметки свои, переносить нечего (совпадений по автору и '
              f'источнику: {len(candidates)}, перенос 0)')
    elif group_name:
        print(f'   контур «{group_name}» — не Atlas: чужих отметок (автор {FOREIGN_NOTED_BY!r}, '
              f'source LIKE {FOREIGN_SOURCE_LIKE!r}) — {len(to_move)}, по ролям: {by_role_text}')
    else:
        print(f'   в meta нет group_name — контур считается НЕ Atlas: чужих отметок — '
              f'{len(to_move)}, по ролям: {by_role_text}')
    print(f'   своих отметок контура (source=\'rebirth-mark\', встречный случай) — '
          f'{own_marks_n} — не трогаются')

    if a.dry_run:
        ids = ", ".join(str(r[0]) for r in to_move) or "—"
        print(f'\n⟨ВХОЛОСТУЮ⟩ перенеслось бы {len(to_move)} строк(и) (id: {ids}). База не тронута.')
        print('   Запрос, которым владелец увидит их ПОСЛЕ переноса:')
        print("   SELECT role, at, source, noted_by, moved_at, moved_by, reason "
              "FROM role_rebirths_foreign ORDER BY role, at;")
        return

    conn.execute("BEGIN")
    # 🪤 НЕ executescript — он делает неявный коммит и рвёт транзакцию (тот же урок 04.09,
    # что и у соседнего шага 20260905-phoenix-history-archive.py).
    for query in SCHEMA_QUERIES:
        conn.execute(query)
    actor = actor_of()
    reason = ("карточка #640: отметка пересоздания контура Atlas, засеянная соседу шагом "
              "20260905-phoenix-history-archive.py ДО правки различителя по контуру "
              "(2026-09-15) — перенесена, не удалена")
    for row_id, role, at, source, noted_by, noted_at in to_move:
        conn.execute(
            "INSERT INTO role_rebirths_foreign(id, role, at, source, noted_by, noted_at, "
            "moved_by, reason) VALUES (?,?,?,?,?,?,?,?)",
            (row_id, role, at, source, noted_by, noted_at, actor, reason))
    if to_move:
        ids = [r[0] for r in to_move]
        conn.execute(f"DELETE FROM role_rebirths WHERE id IN ({','.join('?' * len(ids))})", ids)

    if is_atlas:
        note = (f"Контур Atlas — отметки свои: {len(candidates)} строк(и) совпали по автору "
                f"и источнику, но перенесено 0 (карточка #640).")
    else:
        note = (f"Контур «{group_name or '?'}» — не Atlas: перенесено {len(to_move)} чужих "
                f"отметок пересоздания контура Atlas (автор {FOREIGN_NOTED_BY!r}, source LIKE "
                f"{FOREIGN_SOURCE_LIKE!r}) в role_rebirths_foreign знак в знак, ничего не "
                f"удалено безвозвратно; по ролям: {by_role_text}. Свои отметки контура "
                f"(source='rebirth-mark') — {own_marks_n} — не тронуты.")
    fp = record_step(conn, VERSION,
                     "role_rebirths_foreign: перенос чужих отметок пересоздания контура Atlas, "
                     "засеянных соседям шагом 20260905-phoenix-history-archive.py ДО различителя "
                     "по контуру (карточка #640 ②). Различитель — по автору записи "
                     f"(noted_by={FOREIGN_NOTED_BY!r}) и источнику (source LIKE "
                     f"{FOREIGN_SOURCE_LIKE!r}), НЕ по имени роли — ловит и чужие имена, и "
                     "переведённые на свои (случай AIA, COORD → COORD-A). " + note)
    conn.commit()
    print(f'\n✅ ПРИМЕНЕНО. отпечаток схемы: {fp} · перенесено: {len(to_move)}')


if __name__ == '__main__':
    main()
