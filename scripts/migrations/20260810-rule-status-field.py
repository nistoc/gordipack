# -*- coding: utf-8 -*-
"""20260810-rule-status-field — СТАТУС ПРАВИЛА ПОЛЕМ (карточка #89, шаг 4 — ЛОМАЮЩИЙ).

СЛОВО ВЛАДЕЛЬЦА ПОЛУЧЕНО 2026-08-10 08:56 UTC: «продолжай, шаг 4 разрешаю» (чат PROTO).
Ломающий шаг нёсся отдельно, с ценой, — критерий ③ карточки #89 выполнен.

ПОВОД. Сегодня отзыв правила живёт ПРОЗОЙ — надгробием в шапке тела. Запросом отличить
отозванное от действующего нельзя: широкий текстовый поиск даёт 14 при 10 настоящих
(4 ложных, 28 %). Цена уже заплачена: 16.07 зеркало правил пять часов держало отозванное
правило как приказ.

ЧТО ДЕЛАЕТ
  ① ПЕРЕСТРАИВАЕТ таблицу `rules`: + status ('active'|'revoked'|'superseded') +
     revoked_at / revoked_by / revoked_reason + superseded_by + CHECK-контракт
     «отозванное обязано нести обстоятельства отзыва». Все живые колонки сохраняются;
  ② ЗАПОЛНЯЕТ десять отозванных — ПО КАРТЕ, СОБРАННОЙ ГЛАЗАМИ (см. ниже);
  ③ записывает себя в журнал схемы (record_step, та же транзакция).

⚠️ `superseded_by` ССЫЛАЕТСЯ НА НОМЕР (id), А НЕ НА ИМЯ — единственная правка образца
   по существу: правило опознаётся номером, переименование не рвёт ссылку молча.

🪤 ПОЧЕМУ КАРТА ОТЗЫВОВ НАПИСАНА РУКОЙ, А НЕ РЕГЕКСПОМ ИЗ НАДГРОБИЙ. Регексп-разбор прозы
   ошибается в 28 % — это наш класс «употребление против упоминания», оплачен дважды.
   Карта — это РЕШЕНИЯ ВЛАДЕЛЬЦА, прочитанные глазами из десяти надгробий 2026-08-10
   08:58 UTC; у каждой строки — дата, автор и причина ИЗ САМОГО надгробия. Прогон
   вхолостую печатает карту целиком: проверяется глазами, а не принимается на веру.

⚖️ ПРЕЕМНИК (superseded_by) ставится ТОЛЬКО там, где надгробие называет преемника-ПРАВИЛО
   явно («ДЕЙСТВУЕТ ВМЕСТО НЕГО: <правило>», «ВЛИТА в <правило>», «записать отдельным
   правилом» + правило существует). Где вместо правила назван механизм или broadcast —
   поле пусто, причина в revoked_reason. Выдумывать связь хуже, чем не иметь её.
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
import rule_status as RS                        # noqa: E402 — единый признак надгробия

VERSION = "20260810-rule-status-field"

# rule_key: (когда UTC, кто, причина — из надгробия, ключ преемника | None)
# Источник каждой строки — надгробие, прочитанное глазами 2026-08-10 08:58 UTC.
REVOKED = {
    'timestamp-in-replies': (
        '2026-07-16 12:52', 'owner',
        'живое слово, чат COORD: «правило timestamp-in-replies v1 — отзываю». '
        'Вместо него UTC везде и только UTC', 'timestamp-utc-in-sqlite'),
    'busy-retry': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». Инструкция КОДУ, а не ролям: ретраи SQLITE_BUSY '
        'живут в самом тулките; падение по BUSY — баг скрипта, не дисциплина вызывающего', None),
    'context-depth': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». «Последние 50 messages» — эвристика до-курсорной '
        'эпохи; пробуждение теперь phoenix-слепок + чтение с персистентного курсора', None),
    'timers-always-on': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». Эпоха постоянных таймеров кончилась: сессии живут '
        'окнами, always-on стал неисполнимым обещанием. Вместо — ритм 2–15 мин (broadcast #2309)', None),
    'wip-pulse': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». Двухминутный пульс в замороженный md-канал никем '
        'не исполнялся; практика — heartbeat в role_status + ноты [START]/[DONE]', 'poll-format'),
    'read-full-channels': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». Дубль: два правила об одном — сломанный источник '
        'истины; суть ВЛИТА в full-scan-every-tick v4 тем же ходом', 'full-scan-every-tick'),
    'channel-rotation': (
        '2026-07-18 14:09', 'owner',
        'пакет «отозвать 6 зомби-правил». Ротировало рукописные md-каналы, замороженные '
        'Фазой 4, — ротировать нечего; история ленты живёт в messages_history', None),
    'no-push-without-owner': (
        '2026-08-08 15:56', 'owner',
        'живое слово в чате PROTO: «пушить можно». Отправка разрешена без вопроса во всех '
        'репозиториях; разрушающее (force push, drop, reset --hard) НЕ затронуто — rule8', None),
    'core-standing-permissions': (
        '2026-08-08 16:39', 'owner',
        'слово владельца: правило склеивало ДВА решения. Push-половина поглощена общим '
        'снятием запрета (15:56), половина про запуск сервиса вынесена отдельным правилом', 'core-service-start-and-migrations'),
    'ing-standing-permissions': (
        '2026-08-08 16:39', 'owner',
        'слово владельца: поглощено общим снятием запрета на отправку. Стоячее разрешение '
        'по одному репозиторию было обходом общего запрета; запрета нет — обход не нужен', None),
}

NEW_TABLE = """
CREATE TABLE rules_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key    TEXT NOT NULL UNIQUE,
    body        TEXT NOT NULL,
    locked_by   TEXT NOT NULL DEFAULT 'coord',
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    basis       TEXT, authorized TEXT, source_ref TEXT,
    expiry_kind TEXT, expiry_cond TEXT,
    -- ⚡ карточка #89 шаг 4: состояние правила ПОЛЕМ, а не прозой.
    -- ⚠️ status и expiry_* — НЕ дубль: expiry говорит, ПРИ КАКОМ УСЛОВИИ правило
    --    отменится в будущем; status — отменено ли УЖЕ. Условие и свершившийся факт.
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'revoked', 'superseded')),
    revoked_at      TEXT,
    revoked_by      TEXT,
    revoked_reason  TEXT,
    -- на НОМЕР, не на имя: переименование правила не должно рвать ссылку молча
    superseded_by   INTEGER REFERENCES rules(id) ON DELETE SET NULL,
    -- КОНТРАКТ: отзыв без обстоятельств через месяц неотличим от потери
    CHECK (status <> 'revoked'
           OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
               AND revoked_reason IS NOT NULL)),
    CHECK (status <> 'superseded' OR superseded_by IS NOT NULL),
    CHECK (superseded_by IS NULL OR superseded_by <> id)
)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    have = {r[1] for r in conn.execute("PRAGMA table_info(rules)")}

    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)
    if 'status' in have:
        print('✅ уже сведено (колонка status на месте) — делать нечего')
        return

    # ── сверка карты с ЕДИНЫМ признаком: карта и признак обязаны сойтись до буквы ──
    rows = {r['rule_key']: r for r in RS.read_rules(conn)}
    by_tomb = {k for k, r in rows.items() if r['revoked']}
    map_keys = set(REVOKED)
    if by_tomb != map_keys:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: карта отзывов разошлась с надгробиями.\n'
                 f'   в надгробиях, но не в карте: {sorted(by_tomb - map_keys) or "—"}\n'
                 f'   в карте, но без надгробия:  {sorted(map_keys - by_tomb) or "—"}\n'
                 '   Свод менялся после сборки карты — перечитать глазами, не досыпать.')
    print(f'правил: {len(rows)} · отозванных по надгробиям: {len(by_tomb)} · '
          f'карта сошлась с признаком до буквы\n')

    # ── план заполнения, целиком, для глаз ──
    print('КАРТА ОТЗЫВОВ (глазами из надгробий 2026-08-10 08:58 UTC):')
    print('─' * 78)
    ids = {k: rows[k]['id'] for k in rows}
    for key in sorted(REVOKED):
        at, by, reason, succ = REVOKED[key]
        print(f'⛔ {key}  (id {ids[key]})')
        print(f'   отозвано {at} UTC · {by}')
        print(f'   причина: {reason[:150]}')
        print(f'   преемник: {succ + " (id " + str(ids[succ]) + ")" if succ else "— (в надгробии назван не-правилом либо не назван)"}')
    print('─' * 78)
    n_succ = sum(1 for v in REVOKED.values() if v[3])
    print(f'отзывов {len(REVOKED)} · с преемником-правилом {n_succ} · '
          f'остальных {len(rows) - len(REVOKED)} остаются active')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    conn.executescript(NEW_TABLE)
    cols = "id, rule_key, body, locked_by, version, created_at, updated_at, " \
           "basis, authorized, source_ref, expiry_kind, expiry_cond"
    conn.execute(f"INSERT INTO rules_new ({cols}) SELECT {cols} FROM rules")
    for key, (at, by, reason, succ) in REVOKED.items():
        conn.execute(
            "UPDATE rules_new SET status='revoked', revoked_at=?, revoked_by=?, "
            "revoked_reason=?, superseded_by=?, updated_at=updated_at WHERE rule_key=?",
            (at + ' UTC', by, reason, ids[succ] if succ else None, key))
    conn.execute("DROP TABLE rules")
    conn.execute("ALTER TABLE rules_new RENAME TO rules")
    fp = record_step(conn, VERSION,
                     "rules: статус полем (active/revoked/superseded) + обстоятельства "
                     "отзыва + преемник НОМЕРОМ; 10 отзывов заполнены картой, собранной "
                     "глазами; слово владельца 08:56 UTC", by='PROTO')
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print('целостность:', conn.execute("PRAGMA integrity_check").fetchone()[0])
    # контрольное чтение ПОЛЕМ — тем же модулем, что читают роли
    n = sum(1 for r in RS.read_rules(conn) if r['revoked'])
    src = RS.read_rules(conn)[0]['status_source']
    print(f'единый признак после применения: отозванных {n}, источник «{src}»')


if __name__ == '__main__':
    main()
