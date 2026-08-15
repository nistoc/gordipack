# -*- coding: utf-8 -*-
"""20260810-role-lifecycle — СОСТОЯНИЕ РОЛИ ПОЛЕМ, С ПРИЧИНОЙ И АВТОРОМ (карточка #89, шаг 2).

ПОВОД (замер 2026-08-10 07:39–08:00 UTC). Живая `roles` и образец схемы v-next описывают
состояние роли РАЗНЫМИ словарями: живая — `status` (unknown/active/dormant/closed),
образец — `lifecycle` (alive/dormant/closed). Два словаря одного понятия уже стоили
контуру месяца расхождения. При этом живая таблица МЕРТВА: у всех одиннадцати ролей
`unknown`, и ни один скрипт к ней не обращается (замер грепом — ноль обращений).

ЧТО БЕРЁТСЯ ОТ КОГО — «лучшее от обеих», а не выбор одной:
  · СЛОВАРЬ — от образца (`lifecycle`), И имя тоже от него. Рядом живёт таблица
    `role_status` с ДРУГИМ смыслом (рабочая заметка роли); два `status` рядом путали бы
    всякого читающего. Перископ оба имени уже понимает — цена переименования нулевая;
  · `unknown` — от ЖИВОЙ. Честное «не знаем» при переносе терять нельзя, иначе перенос
    начнёт выдумывать состояние там, где слова не было;
  · ПРИЧИНА, АВТОР И ЧАС перехода — от образца. Сегодня «почему EYE закрыт» живёт прозой
    в правиле-реестре, и его приходилось охранять строкой в чужих слепках;
  · `seen_in` / `in_roster` — от ЖИВОЙ. Это не статус, а следы ЗАМЕРА, и образец о них
    не знал зря: именно они отличают «роли не было» от «роль не объявлена»;
  · CHECK НА ВЕРХНИЙ РЕГИСТР — от образца. Расщепление «отметка чтения ↔ память» из-за
    регистра уже ловилось руками: дисциплина протекла, значит место конструкции.

⚠️ `lifecycle_at` СДЕЛАН НЕОБЯЗАТЕЛЬНЫМ, вопреки образцу (там NOT NULL DEFAULT now).
   У ролей, заведённых до журнала, часа перехода в живом реестре нет. Поставить им
   `datetime('now')` значило бы записать, что их перевели СЕГОДНЯ, — правдоподобная
   и полностью ложная запись. Пустое поле видно, а уверенный неверный ответ не проверяет
   никто. Для новых записей DEFAULT сохранён.

🪤 ПОЧЕМУ КАРТА СОСТОЯНИЙ НАПИСАНА РУКОЙ, ХОТЯ РУКОПИСНЫЕ СПИСКИ Я САМ СНИМАЛ (#156).
   Снимал те, что дублируют ДАННЫЕ, — их положено считать замером. Здесь предмет иной:
   это РЕШЕНИЯ ВЛАДЕЛЬЦА, а они и есть слова. Разбирать их регекспом из прозы реестра —
   ровно наш незакрытый класс «употребление против упоминания». Поэтому у каждой строки
   стои́т ОСНОВАНИЕ, и прогон вхолостую печатает его целиком: проверяется глазами, а не
   принимается на веру.

Источник оснований: правило `role-roster-and-zones` (живая база, читано 2026-08-10 08:17 UTC).
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

VERSION = "20260810-role-lifecycle"

# роль: (состояние, кто решил, когда, почему, зона)
ROSTER = {
    'COORD':  ('alive', 'owner', None, 'координатор контура; в живом реестре', 'atlas.archs + .mezosync'),
    'CORE':   ('alive', 'owner', None, 'в живом реестре', 'atlas.core'),
    'ING':    ('alive', 'owner', None, 'в живом реестре', 'atlas.ingestion'),
    'STUD':   ('alive', 'owner', None, 'в живом реестре', 'atlas.studio'),
    'TAXO':   ('alive', 'owner', None, 'в живом реестре', 'step03/fable5guess'),
    'OPSSRE': ('alive', 'owner', '2026-07-25', 'заведён по живому слову владельца', 'atlas.archs: раскатка и стоимость'),
    'PROTO':  ('alive', 'owner', '2026-07-25', 'заведён по живому слову владельца', 'gordipack + песочница v-next'),
    'CHROME': ('alive', 'owner', '2026-08-06', 'заведён по живому слову владельца', 'atlas.chrome.extension + guardrails'),
    'RCC':    ('alive', 'owner', '2026-08-05 20:44', 'пробуждён живым словом владельца после 7 недель дормана; '
                                                     'дормант 16.07→05.08 был по слову, НЕ апоптозом', 'C:\\guts\\.rcc (только чтение)'),
    'EYE':    ('closed', 'owner', '2026-07-16 18:03', 'апоптоз живым словом владельца в чате EYE (нота #2145); '
                                                      'диагноз владельца: «роль без предмета дрейфует в дублирование и чужие зоны»', 'мост к владельцу (закрыт)'),
    'GRF':    ('closed', 'owner', '2026-07-16 18:39', 'апоптоз живым словом владельца в чате GRF (нота #2164); '
                                                      'предмет был реален, закрыт за отсутствием загрузки. Зона graphify — в дежурное владение COORD', 'graphify (закрыт)'),
}

NEW_TABLE = """
CREATE TABLE roles_new (
    role        TEXT PRIMARY KEY
                CHECK (role = UPPER(role) AND LENGTH(role) BETWEEN 2 AND 16),
    -- 'unknown' — ДЕФОЛТ ПРИ ПЕРЕНОСЕ: след в данных не говорит о состоянии.
    -- Заполняется СЛОВОМ, а не выводом из наличия нот.
    lifecycle   TEXT NOT NULL DEFAULT 'unknown'
                CHECK (lifecycle IN ('unknown', 'alive', 'dormant', 'closed')),
    lifecycle_at     TEXT,                   -- час перехода; пусто = неизвестен (см. шапку)
    lifecycle_by     TEXT,                   -- 'owner' | роль
    lifecycle_reason TEXT,
    zone        TEXT,
    seen_in     TEXT,
    in_roster   INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

# старое значение → новое. 'active' живой базы и 'alive' образца — одно понятие.
DICT_MAP = {'unknown': 'unknown', 'active': 'alive', 'dormant': 'dormant', 'closed': 'closed'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    have = {r[1] for r in conn.execute("PRAGMA table_info(roles)")}
    rows = conn.execute("SELECT role, status, seen_in, in_roster, created_at FROM roles "
                        "ORDER BY role").fetchall() if 'status' in have else []

    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    if 'lifecycle' in have:
        print('✅ уже сведено (колонка lifecycle на месте) — делать нечего')
        return
    if 'status' not in have:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: у таблицы roles нет ни status, ни lifecycle — '
                 'это не та база, которую описывает шаг')

    print(f'колонок было {len(have)} → станет 9 · строк {len(rows)}\n')
    print('РОЛЬ      БЫЛО      СТАНЕТ    ЧАС                ОСНОВАНИЕ')
    print('─' * 78)
    plan, unlisted = [], []
    for role, status, seen_in, in_roster, created in rows:
        hit = ROSTER.get(role)
        if hit:
            life, by, at, why, zone = hit
        else:
            # роль есть в базе, но НЕ в реестре — состояние не выдумываем
            life, by, at, why, zone = DICT_MAP.get(status, 'unknown'), None, None, None, None
            unlisted.append(role)
        plan.append((role, life, at, by, why, zone, seen_in, in_roster, created))
        print(f'{role:9s} {status:9s} {life:9s} {(at or "—"):18s} {(why or "в реестре не найдена — состояние не выдумано")[:70]}')

    print('─' * 78)
    print(f'живых {sum(1 for p in plan if p[1] == "alive")} · '
          f'закрытых {sum(1 for p in plan if p[1] == "closed")} · '
          f'не в реестре {len(unlisted)}')
    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Для врезки прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    conn.executescript(NEW_TABLE)
    conn.executemany(
        "INSERT INTO roles_new (role, lifecycle, lifecycle_at, lifecycle_by, lifecycle_reason,"
        " zone, seen_in, in_roster, created_at) VALUES (?,?,?,?,?,?,?,?,?)", plan)
    conn.execute("DROP TABLE roles")
    conn.execute("ALTER TABLE roles_new RENAME TO roles")
    fp = record_step(conn, VERSION,
                     "roles: состояние полем (lifecycle) + причина/автор/час перехода + зона; "
                     "словарь сведён с образцом v-next, 'unknown' сохранён из живой, "
                     "CHECK на верхний регистр имени", by='PROTO')
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} сторож журнала: {why}')
    print('целостность:', conn.execute("PRAGMA integrity_check").fetchone()[0])


if __name__ == '__main__':
    main()
