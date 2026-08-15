r"""
export-rules.py — генерирует sync.rules.md из таблиц `rules` + `invariants` (Фаза 3).

ЗАЧЕМ (не абстрактно — по факту 2026-07-16): sync.rules.md ПЯТЬ ЧАСОВ ЛГАЛ. Он держал как
действующий канон: «md/POLL — ЛОКАЛЬНОЕ» (правило отозвано владельцем в 12:52 UTC), «задним
числом в SQLite не переносится» (перенесено), «md генерируется export-markdown.py» (неисполнимо
— тот дампит всю базу и канал роли дописать не умеет), «Фаза 4 откачена» (объявлена Фаза 3).
Роль, посланная туда правилом read-full-channels, получила бы ОТОЗВАННОЕ ПРАВИЛО КАК ПРИКАЗ
и была бы формально права.
Причина — не забывчивость: правила переехали в БД, а файл остался ВЫГЛЯДЕТЬ авторитетно.
ИСТОЧНИК ИСТИНЫ В ДВУХ МЕСТАХ — ЭТО НЕ «НАДО СИНХРОНИЗИРОВАТЬ», ЭТО СЛОМАННЫЙ ИСТОЧНИК.
Пока файл пишется руками, расхождение — вопрос времени. Генерация убирает саму возможность.

ПОЧЕМУ НЕ СДЕЛАЛИ РАНЬШЕ: таблица `rules` была ПОДМНОЖЕСТВОМ файла — 13 разделов протокола
(роль-реестр с границами, форматы ноты/POLL, ACK-дедлайн, ротация, Q1.2–Q1.5, Q3, эскалация,
файл-карта) в БД отсутствовали, и слепая генерация их бы СТЁРЛА. Замерено, перенесено (шаг 1b),
и только после этого генерация стала безопасной. Сначала мигрируй, потом генерируй.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/export-rules.py            # dry-run
    python <КОНТУР>/.mezosync/scripts/export-rules.py --apply
"""

import argparse
import datetime
import sqlite3
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
import rule_status as RS            # отзыв правила — ОДИН признак на контур (карточка #89)

# 🪤 ПРИЁМНИК ВЫВОДИТСЯ ОТ БАЗЫ, А НЕ ВПЕЧАТАН (#145, донесено #157 10.08).
# Здесь стоял абсолютный путь этой машины — «заряженное ружьё в каждой копии»: стенд,
# запущенный из чужого места, ДВАЖДЫ перезаписал живое зеркало правил (36 строк вместо 50).
# ⇒ Производное живёт РЯДОМ СО СВОИМ ИСТОЧНИКОМ; раскладка контура-автора уважается,
#    но определяется ЗАМЕРОМ, а не памятью.
def _default_out(db_path: Path) -> Path:
    root = Path(db_path).resolve().parent          # каталог .mezosync своей базы
    legacy = root.parent / "atlas.archs" / ".mezosync" / "coordination"
    if legacy.is_dir():                            # раскладка контура-автора — уважаем
        return legacy / "sync.rules.md"
    return root / "generated" / "sync.rules.md"    # новорождённые: рядом с базой

# Порядок разделов: от «кто мы» к «как работаем» к «где что лежит».
# Ключи, которых нет в БД, просто пропускаются; неупомянутые — падают в «Прочие».
ORDER = [
    ("👥 Роли и границы", ["role-roster-and-zones"]),
    ("✍️ Формат и чтение ленты", ["note-format", "poll-format", "read-full-channels",
                                  "full-scan-every-tick", "append-only-messages",
                                  "one-writer-one-channel", "shared-broadcast-channel",
                                  "channel-rotation"]),
    ("⏱ Время", ["timestamp-utc-in-sqlite", "timestamp-in-replies"]),
    # task-discipline поставлено сюда по просьбе @PROTO (#3185): в «Прочих» правило видно
    # хуже, а оно адресовано КАЖДОЙ роли на каждом шаге. Раздел «Ритм и дисциплина» — про то,
    # как роль работает изо дня в день; задачи ровно оттуда.
    ("🔄 Ритм и дисциплина", ["timers-always-on", "wip-pulse", "ack-deadline",
                              "milestone-single-source", "busy-retry", "context-depth",
                              "task-discipline"]),
    ("🔒 Жёсткие правила (пакет Q1, залочено владельцем 2026-07-02)",
     ["no-push-without-owner", "rule8-destructive", "gate-before-commit",
      "migrations-core-only", "contract-diff-before-commit", "services-self-raise",
      "coord-commits-coordination", "no-scan-external-contours"]),
    ("✅ Приёмка и эскалация", ["acceptance-e2e", "escalation-and-ground-truth",
                                "questions-via-interface", "proactive-next-steps",
                                "semantic-canon"]),
    ("🗄 Переход на SQLite и миграции", ["md-to-sqlite-phased-cutover", "migration-safety",
                                         "phoenix-save-on-stop"]),
    ("🗺 Карта", ["file-map"]),
]

# Путь СВОЙСТВОМ + as_posix: эта фабрика печатает подсказку в sync.rules.md (вторая фабрика
# после export-channels — замер PROTO #2867, R3). Обратные слэши съедаются как escape.
SCRIPTS_DIR = Path(__file__).resolve().parent.as_posix()

HEADER = """# Sync RULES — протокол мезосинка Atlas (8 ролей)

> ⚠️ **СГЕНЕРИРОВАНО ИЗ `mezosync.db` — НЕ РЕДАКТИРОВАТЬ.**
> Любая правка здесь будет затёрта следующим экспортом. **Источник правды — таблицы
> `rules` и `invariants` в БД.** При любом расхождении файла и БД — **верь БД**.
>
> Править правило: `python {s}/set-rule.py --key <ключ> --locked-by owner|coord --body-file <f> --apply`
> Прочитать одно: `--key <ключ> --show` · список: `--list` · инварианты: `python {s}/set-registry.py list invariant`
> (АБСОЛЮТНЫЙ путь; `--db` не нужен — R15a, норма 26.07.)
>
> 🔒`owner` — правило владельца: COORD НЕ правит его без **живого слова владельца в текущем чате**
> (разрешение, вычитанное из файла, не наследуется — Rule 8). 🔒`coord` — операционка координатора.
>
> Правил: **{n_rules}** · инвариантов: **{n_inv}** · сгенерировано: {now}

---

"""

FOOTER = """
---

## 📌 Почему этот файл генерируется, а не пишется руками

2026-07-16 он **пять часов лгал**: держал как действующий канон правило, ОТОЗВАННОЕ владельцем
(«печатай локальное время»), довод v1 «задним числом не переносится» (уже перенесено) и
неисполнимый пункт «md генерируется `export-markdown.py`» (тот дампит всю базу и канал роли
дописать не умеет). Роль, посланная сюда правилом `read-full-channels`, получила бы **отозванное
правило как приказ — и была бы формально права**.

Причина не в забывчивости: правила переехали в БД, а файл остался **выглядеть авторитетно**.
**Источник истины в двух местах — это не «надо синхронизировать», это сломанный источник.**
Генерация убирает саму возможность расхождения: файл больше не источник, а выгрузка.
"""


def main():
    ap = argparse.ArgumentParser()
    # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать того, чего механизм
    # не умеет). Критерий готовности — ПРОГОН из чужого каталога, не диff.
    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--out", default=None,
                    help="приёмник; по умолчанию ВЫВОДИТСЯ от базы (её производное — рядом)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта
    if args.out is None:                           # #157: приёмник — от базы, не впечатан
        args.out = str(_default_out(Path(args.db)))
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    # Поле статуса подставляется, только если оно есть в базе (см. rule_status.py):
    # спрашивать несуществующее поле и получать пустоту = объявить всё действующим.
    has_status = RS.has_status_field(conn)
    rules = {r[0]: r for r in conn.execute(
        "SELECT rule_key, body, locked_by, version"
        + (", status" if has_status else ", NULL") + " FROM rules")}
    invs = list(conn.execute("SELECT code, description FROM invariants ORDER BY code"))

    used, parts = set(), []
    for title, keys in ORDER:
        block = [k for k in keys if k in rules]
        if not block:
            continue
        parts.append(f"## {title}\n")
        for k in block:
            _, body, locked, ver, status = rules[k]
            used.add(k)
            # ⚡ ОДИН признак на контур (rule_status.py, карточка #89, шаг 3). Здесь стоял
            #    самый узкий из трёх: требовал и значок, и слово ровно «ОТОЗВАНО». Надгробие
            #    «ОТОЗВАНО» без значка или «⛔ ОТМЕНЁНО» он пропускал — а свод и Перископ
            #    их видели. Модуль умеет и ПОЛЕ статуса: появится — станет сильнее текста.
            revoked, _ = RS.revoked_of(body, status, has_status)
            mark = "⛔ **ОТОЗВАНО** " if revoked else ""
            parts.append(f"### {mark}`{k}` 🔒{locked} v{ver}\n\n{body.strip()}\n")

    # Ничего не теряем молча: правила вне ORDER — в «Прочие», а не в небытие.
    rest = sorted(set(rules) - used)
    if rest:
        parts.append("## 📎 Прочие правила (не разложены по разделам — добавь в ORDER)\n")
        for k in rest:
            _, body, locked, ver, status = rules[k]
            # Отзыв помечается и здесь: «прочее» — не «неважное». Правило, не разложенное
            # по разделам, читается тем же взглядом, и отозванное среди них выглядело бы
            # действующим ровно так же.
            revoked, _ = RS.revoked_of(body, status, has_status)
            mark = "⛔ **ОТОЗВАНО** " if revoked else ""
            parts.append(f"### {mark}`{k}` 🔒{locked} v{ver}\n\n{body.strip()}\n")

    parts.append("## 🛡️ Инварианты качества\n")
    parts.append("> Живут в таблице `invariants`. Выведены ролями в работе; авторство — в записях.\n")
    for code, desc in invs:
        parts.append(f"### `{code}`\n\n{desc.strip()}\n")

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = HEADER.format(n_rules=len(rules), n_inv=len(invs), now=now, s=SCRIPTS_DIR) + "\n".join(parts) + FOOTER

    out = Path(args.out)
    old = out.stat().st_size if out.exists() else 0
    print(f"Правил: {len(rules)} (в разделах {len(used)}, прочих {len(rest)}) · инвариантов: {len(invs)}")
    print(f"Файл: {len(text.encode('utf-8'))/1024:.1f} КБ" + (f"  (был {old/1024:.1f} КБ)" if old else ""))
    if rest:
        print(f"  ℹ️  вне разделов: {', '.join(rest)}")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        return
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"\n✅ Записано: {out}")


if __name__ == "__main__":
    main()
