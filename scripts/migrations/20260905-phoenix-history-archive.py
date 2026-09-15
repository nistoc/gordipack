# -*- coding: utf-8 -*-
"""20260905-phoenix-history-archive — АРХИВ ИСТОРИИ ВЕРСИЙ ПАМЯТИ + ОТМЕТКИ ПЕРЕСОЗДАНИЯ РОЛЕЙ
(карточка #538, шаг ② регламента сжатия; слово владельца 2026-09-05 06:02 UTC «делаем C …
неразрушительно»).

ПРЕДМЕТ. История версий памяти (`phoenix_history`) хранит КАЖДОЕ сохранение каждого раздела
дословно: 440 версий · 6,92 млн знаков на 2026-09-05 07:01 UTC. Регламент (текст COORD на
карточке #538) говорит: из версий старше 7 суток остаются ПОСЛЕДНЯЯ перед КАЖДЫМ пересозданием
роли и последняя вообще; прочие ПЕРЕНОСЯТСЯ в архивную таблицу, а не удаляются.

⚡ НАХОДКА, РАДИ КОТОРОЙ ЗДЕСЬ ДВЕ ТАБЛИЦЫ, А НЕ ОДНА. В базе НЕТ СОБЫТИЯ «ПЕРЕСОЗДАНИЕ РОЛИ».
Летопись знает сохранения (save_phoenix) и «взгляд без правки» (confirm_phoenix), таблица ролей —
только состояние. Правило «последняя перед пересозданием» неисполнимо из базы, пока событие
не записано. Моменты пересоздания живут в записях разговоров клиента: первая реплика нового
чата «Ты — роль X контура … Чат свежий после пересоздания» (шаблон role-prompts.py).
Снято сплошным обходом файлов контура Atlas 2026-09-05 07:00 UTC — 18 отметок у 9 ролей.
⇒ `role_rebirths` засевается этими отметками ЗДЕСЬ (с именем файла-источника у каждой),
а впредь отметку ставит сборщик промптов пересоздания в момент своего вызова.

⚖️ ПОЧЕМУ ОТДЕЛЬНАЯ ТАБЛИЦА, А НЕ ПРИЗНАК В ИСТОРИИ. `phoenix_history` читают 9 инструментов
(save-phoenix --history/--restore, проверка инвариантов памяти, сборка v-next, приёмки).
Признак «в архиве» внутри таблицы был бы виден каждому и каждый счёл бы архив живой историей.
Отдельная таблица невидима для них по построению — тот же довод, что у phoenix_archive
(шаг 20260904-phoenix-archive).

ЧТО ДЕЛАЕТ ШАГ
  · заводит `role_rebirths` — отметки пересоздания (роль · час · источник · кем записано);
  · засевает 18 отметок из записей разговоров — ТОЛЬКО В КОНТУРЕ ATLAS (ниже);
  · заводит `phoenix_history_archive` — те же поля, что у истории, + moved_at · moved_by · rule;
  · записывает себя в журнал схемы.

⛔ ЧЕГО НЕ ДЕЛАЕТ: ничего не переносит. Перенос — рука роли и ТОЛЬКО своей истории
(инструмент memory-history-fold.py; слово владельца 2026-09-04 13:41 UTC «только свою»).

⚡ ПРАВКА 2026-09-15 (карточка #640, находка COORD при приёмке карточки #634). Отметки
пересоздания ниже — это СОБЫТИЯ ИМЕННО КОНТУРА ATLAS: сняты сплошным обходом ЕГО ЖЕ записей
разговоров. Шаг писал их в ЛЮБУЮ базу, где есть `phoenix_history` и ещё нет `role_rebirths`,
без разбора контура — сосед, применивший шаг у себя, получал 18 чужих «пересозданий» под
своими же именами ролей (замер: у tapas и у AIA — по 18 строк каждому; у AIA роль COORD при
этом переведена их нормализатором имён в COORD-A).
⇒ Засев различает контур по `meta.group_name` (его пишет init-group.py при сборке): значение
'atlas' — засевает все 18 отметок, как и прежде; любое другое значение или отсутствующая
строка — заводит ОБЕ таблицы как обычно, но НЕ засевает ни одной отметки Atlas, и говорит
об этом печатью словами (не молчанием). Запись в журнал схемы идёт в ЛЮБОМ контуре; текст
записи называет, сколько отметок засеяно НА ДЕЛЕ, а не число из докстроки.
⚖️ Уборка уже засеянного у соседей, применивших шаг ДО этой правки, — ОТДЕЛЬНЫЙ шаг
`20260915-foreign-rebirth-marks.py` (карточка #640 ②); этот шаг чужого не убирает.
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

VERSION = "20260905-phoenix-history-archive"
# Контур, ЧЬИ отметки пересоздания несёт список ниже — засев работает ТОЛЬКО для него
# (карточка #640): имя проверяется по meta.group_name живой базы, не впечатывается угадыванием.
ATLAS_GROUP_NAME = "atlas"

# ⚡ Схема — СПИСОК запросов, не один текст: точка с запятой встречается внутри комментариев
# (оплачено шагом 20260904-phoenix-archive).
SCHEMA_QUERIES = (
    """CREATE TABLE role_rebirths (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    role      TEXT NOT NULL,
    -- ЧАС пересоздания (UTC): первая реплика нового чата роли. Не час сохранения памяти
    -- и не час сборки промптов — те бывают за минуты и часы до того, как чат родился.
    at        TEXT NOT NULL,
    -- ОТКУДА известно: 'transcript:<файл>' — снято с записи разговора; 'role-prompts' —
    -- поставлено сборщиком промптов в момент вызова. Отметка без источника — догадка.
    source    TEXT NOT NULL,
    noted_by  TEXT NOT NULL,
    noted_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (role, at)
)""",
    "CREATE INDEX idx_role_rebirths_role ON role_rebirths(role, at)",
    """CREATE TABLE phoenix_history_archive (
    -- id ТОТ ЖЕ, что был в phoenix_history: возврат кладёт версию под её прежним номером,
    -- и ссылка «версия #N» в чужой записке не протухает от переноса.
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL,
    section     TEXT NOT NULL,
    body        TEXT NOT NULL,
    body_chars  INTEGER NOT NULL,
    saved_at    TEXT NOT NULL,
    actor       TEXT NOT NULL,
    reason      TEXT NOT NULL,
    prev_chars  INTEGER,
    -- ЧТО ДОБАВЛЯЕТ ПЕРЕНОС: когда, чьей рукой и по какому правилу унесено.
    moved_at    TEXT NOT NULL DEFAULT (datetime('now')),
    moved_by    TEXT NOT NULL,
    rule        TEXT NOT NULL
)""",
    "CREATE INDEX idx_phoenix_history_archive_role ON phoenix_history_archive(role, section, saved_at)",
)

# ОТМЕТКИ ПЕРЕСОЗДАНИЯ КОНТУРА ATLAS — замер 2026-09-05 07:00 UTC по первым репликам записей
# разговоров контура Atlas (C:\Users\…\.claude\projects\C--guts--atlas\<файл>.jsonl): первая
# реплика человека, содержащая «Ты — роль X контура» и «пересозда»/«свежий». Файл назван
# первыми восемью знаками имени. Пара одинаковых часов у CHROME/TAXO 29.08 — один и тот же
# промпт, поданный в два чата; отметка одна на (роль, час).
# ⚠️ ЭТИ ОТМЕТКИ — СОБЫТИЯ ИМЕННО КОНТУРА ATLAS (карточка #640): засеваются только туда,
# см. ATLAS_GROUP_NAME и main() ниже.
ATLAS_REBIRTH_MARKS = (
    ("CHROME", "2026-08-29 09:39:08", "transcript:a14b4fd3,a858f3e1"),
    ("CHROME", "2026-08-29 09:59:21", "transcript:a14b4fd3,a858f3e1"),
    ("CHROME", "2026-08-30 21:59:37", "transcript:df02fced"),
    ("COORD",  "2026-08-30 21:56:08", "transcript:dda670f7"),
    ("COORD",  "2026-08-30 21:58:38", "transcript:f3fd7500"),
    ("CORE",   "2026-08-29 10:43:06", "transcript:8b6773a1"),
    ("CORE",   "2026-08-30 21:59:08", "transcript:cbdc58bc"),
    ("ING",    "2026-08-30 22:04:47", "transcript:cc1a427f"),
    ("OPSSRE", "2026-08-29 09:30:41", "transcript:1a607d6e"),
    ("OPSSRE", "2026-08-30 22:05:32", "transcript:99b6be2c"),
    ("PROTO",  "2026-08-30 09:54:19", "transcript:8c3e6dbf"),
    ("PROTO",  "2026-08-30 22:33:19", "transcript:c0812f28"),
    ("RCC",    "2026-08-30 22:01:49", "transcript:fe80973c"),
    ("STUD",   "2026-08-29 09:31:50", "transcript:90ac9a6f"),
    ("STUD",   "2026-08-30 22:41:00", "transcript:83ea29c6"),
    ("TAXO",   "2026-08-29 09:38:19", "transcript:b7dded1a"),
    ("TAXO",   "2026-08-29 09:50:34", "transcript:b7dded1a"),
    ("TAXO",   "2026-08-30 22:03:26", "transcript:8b0a270e"),
)


def group_name_of(conn) -> str | None:
    """Имя контура из meta.group_name — None, если таблицы meta нет или строки в ней нет."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'meta' not in tables:
        return None
    row = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    return row[0] if row else None


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
    if 'phoenix_history' not in existing_tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛСЯ: таблицы phoenix_history нет — этот шаг стои́т на ней')
    if 'phoenix_history_archive' in existing_tables and 'role_rebirths' in existing_tables:
        print('✅ уже сведено (обе таблицы на месте) — делать нечего')
        return
    if ('phoenix_history_archive' in existing_tables) != ('role_rebirths' in existing_tables):
        sys.exit('⛔ ПОЛОВИНА ШАГА НА МЕСТЕ: одна таблица есть, другой нет — разбирать рукой, '
                 'не досоздавать молча')

    group_name = group_name_of(conn)
    is_atlas = group_name == ATLAS_GROUP_NAME
    marks_to_seed = ATLAS_REBIRTH_MARKS if is_atlas else ()

    n, total_chars = conn.execute("SELECT COUNT(*), COALESCE(SUM(body_chars),0) FROM phoenix_history").fetchone()
    old_n, old_chars = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(body_chars),0) FROM phoenix_history "
        "WHERE saved_at < datetime('now','-7 days')").fetchone()
    print('ИСТОРИЯ ВЕРСИЙ ПАМЯТИ СЕЙЧАС — замер ДО:')
    print(f'   версий {n} · {total_chars} знаков · старше 7 суток {old_n} · {old_chars} знаков')
    if is_atlas:
        roles_n = len({r for r, _at, _src in marks_to_seed})
        print(f'   контур «{group_name}» — это Atlas: отметок пересоздания к засеву '
              f'{len(marks_to_seed)} у {roles_n} ролей')
    elif group_name:
        print(f'   ⚠️ отметки пересоздания ролей контура Atlas не засеяны: контур «{group_name}» '
              f'— не Atlas (отметок 0)')
    else:
        print('   ⚠️ отметки пересоздания ролей контура Atlas не засеяны: в meta нет '
              'group_name — имя контура неизвестно (отметок 0)')
    print('⚖️ Шаг ничего не переносит: после него история ровно та же, архив пуст.')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    # 🪤 НЕ executescript — он делает неявный коммит и рвёт транзакцию (оплачено 04.09).
    for query in SCHEMA_QUERIES:
        conn.execute(query)
    for role, at, source in marks_to_seed:
        conn.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                     (role, at, source, f"tool:{VERSION}"))
    if is_atlas:
        seeded_note = (f"Засеяно {len(marks_to_seed)} отметок из записей разговоров контура "
                       f"Atlas (замер 2026-09-05 07:00 UTC).")
    else:
        seeded_note = (f"Контур «{group_name or '?'}» — НЕ Atlas: отметки пересоздания ролей контура "
                       f"Atlas НЕ засеяны (0); таблицы заведены как обычно (карточка #640).")
    fp = record_step(conn, VERSION,
                     "phoenix_history_archive + role_rebirths: архив истории версий памяти "
                     "ОТДЕЛЬНОЙ таблицей (те же поля + moved_at · moved_by · rule, id прежний) "
                     "и отметки пересоздания ролей (роль · час · источник) — события "
                     "«пересоздание» в базе не было вовсе, правило «последняя версия перед "
                     f"пересозданием» без него неисполнимо. {seeded_note} Ничего не переносит — "
                     "перенос рука роли (memory-history-fold.py), только своей истории. "
                     "Карточка #538 шаг ②, слово владельца 2026-09-05 06:02 UTC; различитель "
                     "контура по meta.group_name добавлен карточкой #640, правка 2026-09-15. "
                     f"Замер ДО: {n} версий, {total_chars} знаков, старше 7 суток "
                     f"{old_n}/{old_chars}")
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp} · отметок засеяно: {len(marks_to_seed)}')


if __name__ == '__main__':
    main()
