r"""
read-phoenix.py — предъявить роли её слепок ИЗ БД. Инструмент воскрешения (Фаза 3+).

ЗАЧЕМ: владелец 2026-07-16 13:45 UTC: «удобнее воскрешать из БД». До этого launcher роли
звучал «Прочитай ...\phoenix.<роль>.md и начни работать по нему» — то есть УКАЗЫВАЛ НА md.
На Фазе 4 (md-off) владелец вставил бы эту строку в новый чат, а роль прочитала бы пустоту.
МОЛЧА. Сломался бы ровно тот инструмент, которым чинят всё остальное.

И второе, найденное при проверке: таблицу `phoenix` ЧИТАЛ только stats.py — и то лишь
СЧИТАЛ строки для статистики. Читателя, предъявляющего слепок, НЕ БЫЛО ВООБЩЕ. Писатель
есть, читателя нет — тот же класс, что находка STUD #1959 про двойную запись и что 4 пустые
таблицы реестра. Инвариант INSTRUCTION-NEQ-EXECUTABILITY: прежде чем предписать действие,
проверь, что механизм для него существует.

ПОРЯДОК ВЫВОДА — не алфавит, а порядок ЧТЕНИЯ проснувшейся ролью:
    identity (кто я) → rebirth (что делаю ПЕРВЫМ) → sources (где правда)
    → state (где я сейчас) → plan (куда иду) → history (на чём не наступить)
Секция launcher печатается последней, справочно.

ЗАПУСК (это и есть содержимое launcher-строки владельца):
    python read-phoenix.py --db <path> --role CORE
    python read-phoenix.py --db <path> --role CORE --section state    # одна секция
    python read-phoenix.py --db <path> --list                         # кто вообще есть
"""

import argparse
import sqlite3
import sys

ORDER = ["identity", "rebirth", "sources", "state", "plan", "history", "launcher"]

TITLES = {
    "identity": "§1 ИДЕНТИЧНОСТЬ И ГРАНИЦЫ — кто ты и чего тебе НЕЛЬЗЯ",
    "rebirth":  "§2 REBIRTH — что сделать ПЕРВЫМ делом",
    "sources":  "§3 ИСТОЧНИКИ ПРАВДЫ — в порядке чтения",
    "state":    "§4 ТЕКУЩЕЕ СОСТОЯНИЕ — где ты сейчас",
    "plan":     "§5 ПЛАН — куда идёшь",
    "history":  "§6 ИСТОРИЯ И ГРАБЛИ — на чём не наступить",
    "launcher": "§7 LAUNCHER (справочно — строка, которой тебя разбудили)",
}

# ⚠️ ЭТА ШАПКА — ПЕРВОЕ, ЧТО ЧИТАЕТ ВОСКРЕШЁННАЯ РОЛЬ. Значит она обязана быть свежее всего
# остального в контуре. 2026-07-16 она НЕ БЫЛА: я объявил Фазу 4 в 16:58, а шапка ещё в 17:45
# говорила «Фаза 4 не объявлена». Поймал EYE (#2134). Третий за день случай
# ARTIFACT-OUTLIVES-DECISION у меня и худший по МЕСТУ: привет, который получает каждый
# новорождённый агент, был ЛОЖЬЮ — и звучал авторитетнее всего, что он прочтёт дальше.
# ⇒ МЕНЯЕШЬ ФАЗУ/ПРАВИЛО — ПРАВЬ ЭТУ ШАПКУ ТЕМ ЖЕ ХОДОМ. Она не «документация», она инструкция.
CANON = """
═══════════════════════════════════════════════════════════════════════════════
📌 КАНОН — ИСТОЧНИК ПРАВДЫ БД. ⛔ ФАЗА 4 (md-OFF) ДЕЙСТВУЕТ с 2026-07-16 16:58 UTC

  правила      python .mezosync/scripts/set-rule.py --db <db> --list
               ...--key <ключ> --show
  инварианты   python .mezosync/scripts/set-registry.py --db <db> list invariant
  лента        python .mezosync/scripts/read-messages.py --db <db> --role {role}
               ⚠️ КОНТРАКТ с 16.07 (v2 18:45 UTC): чтение НЕ двигает курсор. Токен
               РАЗРЕЗАН: первая половина — в ПЕРВОЙ строке вывода, вторая — в ПОСЛЕДНЕЙ;
               подтверди склейкой: ... --ack <первая>-<вторая>. head прячет вторую,
               tail — первую: обе даёт только ПОЛНЫЙ вывод. Токен одноразовый.
               Незнакомая роль — ошибка, не тихий курсор; новую заводит явный --register.
  broadcast    python .mezosync/scripts/read-broadcasts.py --db <db> --role {role}
  бэклог       python .mezosync/scripts/backlog.py --db <db> list --role {role}
  писать       python .mezosync/scripts/write-message.py --db <db> --role {role} --file <нота.md>
               (пишет ТОЛЬКО в БД — дефолт Ф4; длинное/бэктики — ТОЛЬКО --file, не --body;
               + --ack <id> тем же вызовом проставит ACK broadcast-ноты — ответ и след одним действием)
  heartbeat    ... write-message.py --db <db> --role {role} --poll "статус одной строкой"
               (одна строка на роль, перезапись — таблица role_status, НЕ лента; можно без ноты.
               Смотреть: SELECT * FROM role_status — или generated/sync.<роль>.md после терминатора)

⛔ md ЗАМОРОЖЕНЫ. sync.*.md и phoenix.*.md несут надгробие: НЕ читать, НЕ писать, НЕ править.
   Человекочитаемый ВИД — generated/sync.<роль>.md и sync.rules.md (генерируются из БД).
   История ленты — таблица messages_history + VIEW messages_all (сквозной поиск).
🚨 АВАРИЙНЫЙ ВЫХОД: сломается БД — пиши `write-message.py … --md` и ГРОМКО зови COORD.
   Ф4 обратима БЕЗ правки кода. Ровно этого не хватило 2026-07-12, когда Ф4 сгорела:
   STUD был МОЛЧА отрезан от SQLite, DWERR пропущен. Старый --no-md принимается как no-op.
⏱ ВРЕМЯ — UTC ВЕЗДЕ, суффикс обязателен: «2026-07-16 17:48 UTC». Хуки дают ЛОКАЛЬНОЕ
   с явным offset ⇒ конвертируй сам: UTC = локальное − offset. Offset БРАТЬ ИЗ ХУКА.
⚠️ При РАСХОЖДЕНИИ файла и БД — ВЕРЬ БД. sync.rules.md генерируется из неё; 2026-07-16
   он пять часов лгал, держа отозванное правило как приказ.
🔍 ПРОВЕРЯЯ СВОЙ СЛЕПОК — способ STUD: регексп по ВСЕМ 7 секциям, БЕЗ своих фильтров.
   Глазами по одной секции НЕ ЛОВИТ: TAXO объявила «чисто» и через 13 минут метод нашёл у неё
   2 живых указателя; у RCC — 5 секций из 7; у COORD — 4 лжи через 19 минут после того,
   как он сам объявил Фазу 4. Фильтр по соседним словам ловит СОСЕДНЮЮ фразу и врёт.
═══════════════════════════════════════════════════════════════════════════════
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--role")
    ap.add_argument("--section", choices=ORDER)
    ap.add_argument("--list", action="store_true", help="какие роли и секции есть")
    args = ap.parse_args()

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{args.db}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")

    if args.list:
        print("Слепки в БД:")
        for role, in conn.execute("SELECT DISTINCT role FROM phoenix ORDER BY role"):
            secs = {s: (n, t) for s, n, t in conn.execute(
                "SELECT section, LENGTH(body), saved_at FROM phoenix WHERE role=?", (role,))}
            miss = [s for s in ORDER if s not in secs]
            last = max((t for _, t in secs.values()), default="—")
            print(f"  {role:6} секций {len(secs)}/{len(ORDER)} · посл. сейв {last} UTC")
            for s in ORDER:
                if s in secs:
                    print(f"      ✅ {s:9} {secs[s][0]:6} симв.")
            if miss:
                print(f"      ⛔ НЕТ: {', '.join(miss)}")
        return

    if not args.role:
        print("ERR: нужен --role (или --list)", file=sys.stderr)
        sys.exit(1)

    role = args.role.upper()
    rows = {s: (b, t) for s, b, t in conn.execute(
        "SELECT section, body, saved_at FROM phoenix WHERE role=?", (role,))}
    if not rows:
        print(f"ERR: слепка роли {role} в БД нет. Есть: "
              f"{', '.join(r[0] for r in conn.execute('SELECT DISTINCT role FROM phoenix ORDER BY role'))}",
              file=sys.stderr)
        sys.exit(1)

    wanted = [args.section] if args.section else ORDER

    print(f"🔥 PHOENIX — слепок роли {role} (источник: mezosync.db, таблица phoenix)")
    if not args.section:
        print(CANON.replace("{role}", role))

    for s in wanted:
        if s not in rows:
            print(f"\n⛔ {TITLES[s]}\n   СЕКЦИИ НЕТ В БД. Это факт, а не пустяк: сообщи COORD.")
            continue
        body, saved = rows[s]
        print(f"\n{'─' * 79}\n## {TITLES[s]}   [сохранено {saved} UTC]\n")
        print(body.strip())

    if not args.section:
        miss = [s for s in ORDER if s not in rows]
        if miss:
            print(f"\n{'─' * 79}")
            print(f"⚠️ ОТСУТСТВУЮТ СЕКЦИИ: {', '.join(miss)} — сообщи COORD, не додумывай их содержание.")


if __name__ == "__main__":
    main()
