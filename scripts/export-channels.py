r"""
export-channels.py — генерирует sync.<роль>.md из mezosync.db (Фаза 3).

ЗАЧЕМ: правило md-to-sqlite-phased-cutover обещало «md генерируется export-markdown.py».
Находка STUD #1959 (проверена по коду): это было НЕИСПОЛНИМО — export-markdown.py
сваливает ВСЮ базу (rules+tracks+invariants+последние N сообщений всех ролей) в один
произвольный --out файл, для владельца. Дописать канал конкретной роли он физически
не умеет. Механизма двойной записи не было НИ У КОГО: write-message.py делает один
INSERT в SQLite и в md не пишет ничего.

Следствие: «двойная запись» 4 дня держалась на РУЧНОЙ дисциплине и отказала МОЛЧА
у STUD (sync.stud.md мёртв с 12.07, 13 нот в SQLite и 0 в md). Дисциплина не
масштабируется — механизм масштабируется. Этот скрипт и есть механизм.

ЧТО ДЕЛАЕТ: на каждую роль рендерит generated/sync.<роль>.md из messages_all
(live + history), ORDER BY timestamp, в человекочитаемом формате. Рукописные
sync.*.md НЕ ТРОГАЕТ — они замораживаются историческим пластом.

ВРЕМЯ: UTC ВЕЗДЕ (правило timestamp-utc-in-sqlite v2, владелец 2026-07-16). Конвертации
НЕТ ВООБЩЕ — в БД UTC, в канале UTC. Две шкалы брали налог вниманием и породили фантом
«синк умер 2 часа назад» (разница ровно 2ч была ЗОНОЙ, не лагом). Конвертация, которой
нет, не может быть забыта. Суффикс UTC печатаем явно.

⚠️ ПОРТАТИВНОСТЬ ШАБЛОНА. OUT_DIR по умолчанию — <контур>/.mezosync/generated (из расположения
скрипта), а не хардкод на atlas.archs; переопредели --out-dir. Рендер идёт из VIEW `messages_all`
(live+history) модели мезосинка. Если в схеме её ещё нет — генератор НЕ ПАДАЕТ опакой ошибкой,
а сообщает о недостающей VIEW и выходит (skip-not-crash). Появится messages_all — заработает.

ЗАПУСК:
    python export-channels.py --db <path>            # dry-run
    python export-channels.py --db <path> --apply
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

# OUT_DIR по умолчанию — <контур>/.mezosync/generated (портативно). Переопредели --out-dir
# на версионированное зеркало конкретного контура (в Atlas — atlas.archs/.mezosync/coordination/generated).
OUT_DIR = Path(__file__).resolve().parent.parent / "generated"

HEADER = """# sync.{role}.md — канал роли {role}

> ⚠️ **СГЕНЕРИРОВАНО ИЗ `mezosync.db` — НЕ РЕДАКТИРОВАТЬ.**
> Любая правка здесь будет затёрта следующим экспортом. Источник правды — БД.
> Писать в канал: `python .mezosync/scripts/write-message.py --db <db> --role {role} --body "..."`
>
> Сообщений: **{n}** · диапазон: {lo} .. {hi}
> Сгенерировано: {now} · генератор: `export-channels.py`
> ⏱ Все метки времени — **UTC** (правило `timestamp-utc-in-sqlite` v2).

---

"""

# ⛔ ТЕРМИНАТОР. Без него последней строкой файла оставался ХВОСТ СЛУЧАЙНОЙ НОТЫ — и у CORE
# он буквально начинался со слова «Статус:» и нёс HEAD/ahead/стенд, то есть ВЫГЛЯДЕЛ как POLL,
# ЧИТАЛСЯ как POLL и ВРАЛ как POLL (находка CORE #2104; TAXO #2060 предсказала это словами
# «похожий на статус хвост случайной ноты» — CORE предъявил, что уже так).
# Хуже того: наивный тест `'[РОЛЬ POLL]' in generated` давал TRUE — в sync.core.md 134 вхождения
# «[CORE POLL]», ВСЕ внутри ТЕЛ нот (цитаты, разборы). Роль отчиталась бы ЗЕЛЁНЫМ, не имея
# heartbeat'а вовсе. Живого POLL в выгрузке нет и быть не может: POLL — не нота, он не в ленте.
# Терминатор снимает двусмысленность СТРУКТУРНО: последняя строка теперь всегда наша и говорит,
# что heartbeat'а тут нет. Ложное «похоже на статус» больше не может оказаться последним.
FOOTER = """

---

⛔ **КОНЕЦ ВЫГРУЗКИ. ЖИВОГО HEARTBEAT (`[{role} POLL]`) ЗДЕСЬ НЕТ И БЫТЬ НЕ МОЖЕТ.**

POLL — не нота: он не лежит в ленте, а правится точечно последней строкой РУКОПИСНОГО канала.
Эта выгрузка строится из нот ⇒ heartbeat в неё не попадает **by design**.

⚠️ Строки вида `[{role} POLL] …` выше — это **ЦИТАТЫ внутри тел нот**, а не статус. Проверка
`'[{role} POLL]' in файл` даёт **ложный зелёный**: в одном канале таких вхождений бывает 130+.
**Актуальный статус роли — в БД**, не здесь:
`python .mezosync/scripts/read-messages.py --db <db> --role {role}`
{heartbeat}"""

# 🫀 Живой heartbeat — ЕДИНСТВЕННОЕ живое ниже терминатора, из таблицы role_status
# (write-message.py --poll, слово владельца 16.07 19:23 UTC). Он НЕ нота и не из ленты —
# потому терминатор выше остаётся правдой: «из НОТ heartbeat в выгрузку не попадает».
HEARTBEAT = """
---

🫀 **ЖИВОЙ HEARTBEAT** (таблица `role_status`, обновляется `write-message.py --poll`):

`[{role} POLL] {updated_at} UTC` — {status}
"""


def stamp_utc(s):
    """Метка БД (UTC) → метка канала (UTC). Конвертации НЕТ — правило
    timestamp-utc-in-sqlite v2. Обрезаем до минут: секунды в канале — шум."""
    return (s or "?")[:16]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    out_dir = Path(args.out_dir)

    # messages_all — VIEW модели мезосинка (live+history). В свежей схеме её может не быть:
    # сообщаем и выходим, а не падаем опакой OperationalError (skip-not-crash).
    if not conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='messages_all'").fetchone()[0]:
        print("⏭️ VIEW messages_all в схеме нет — генерировать каналы не из чего "
              "(докати схему до messages_all live+history). Выход без ошибки.")
        return

    roles = [r[0] for r in conn.execute(
        "SELECT DISTINCT writer_role FROM messages_all ORDER BY writer_role")]
    # role_status может не существовать на старых копиях БД — тогда heartbeat'ов просто нет.
    try:
        polls = {r: (s, t) for r, s, t in conn.execute(
            "SELECT role, status, updated_at FROM role_status")}
    except sqlite3.OperationalError:
        polls = {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"Ролей: {len(roles)} · цель: {out_dir}")
    total = 0

    for role in roles:
        rows = conn.execute(
            "SELECT timestamp, body_md, tags, priority, source FROM messages_all "
            "WHERE writer_role = ? ORDER BY timestamp ASC, id ASC", (role,)).fetchall()
        if not rows:
            continue

        body_parts = []
        for ts, body, tags, priority, source in rows:
            stamp = stamp_utc(ts)
            tag_list = json.loads(tags) if tags else []
            marks = []
            if priority and priority != "normal":
                marks.append(f"⚠️{priority}")
            if source == "history":
                marks.append("📚история")
            marks += [f"`{t}`" for t in tag_list if t != "md-migration"]
            mark_s = (" " + " ".join(marks)) if marks else ""
            body_parts.append(f"### [{stamp} UTC] ({role}){mark_s}\n\n{body.strip()}\n")

        hb = ""
        if role in polls:
            status, upd = polls[role]
            hb = HEARTBEAT.format(role=role, status=status, updated_at=stamp_utc(upd))
        text = HEADER.format(
            role=role, n=len(rows), now=now,
            lo=stamp_utc(rows[0][0]), hi=stamp_utc(rows[-1][0]),
        ) + "\n".join(body_parts) + FOOTER.format(role=role, heartbeat=hb)

        dest = out_dir / f"sync.{role.lower()}.md"
        old = dest.stat().st_size if dest.exists() else 0
        print(f"  {role:6} {len(rows):5} нот → {len(text)/1024:6.0f} КБ" +
              (f"  (было {old/1024:.0f} КБ)" if old else "  (новый)"))
        total += len(rows)

        if args.apply:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

    print(f"\nВсего нот отрендерено: {total}")
    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
    else:
        print(f"✅ Записано в {out_dir}")
        print("Дальше: COORD коммитит generated/ в версионированный репо (push — только по слову владельца)")


if __name__ == "__main__":
    main()
