r"""
export-markdown.py — Экспорт содержимого mezosync.db в читаемый Markdown.

Для владельца: быстрый обзор без SQLite-клиента.

Использование:
    python <КОНТУР>/.mezosync/scripts/export-markdown.py --out report.md
    python <КОНТУР>/.mezosync/scripts/export-markdown.py --last 50  # только последние 50 сообщений
"""

import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
import rule_status as RS            # отзыв правила — ОДИН признак на контур (карточка #89)


def main():
    parser = argparse.ArgumentParser(description="Экспорт mezosync.db → Markdown")
    # R15a (26.07): --db НЕ обязателен, резолвится от расположения скрипта. Последний инструмент
    # контура, где он оставался required — нашёл признак @PROTO (#3167, находка «В»).
    # ⚠️ И зазор был виден в этом же файле: примеры использования в шапке (строки 7–8) вызывают
    # скрипт БЕЗ --db с 26.07, а argparse его требовал. Роль, поверившая примеру, получала отказ.
    # Тот же класс «врёт не код, а текст рядом с ним» — только здесь текст был прав, а код отстал.
    parser.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    parser.add_argument("--out", default=None, help="Выходной .md файл (по умолчанию stdout)")
    parser.add_argument("--last", type=int, default=100, help="Сколько последних сообщений")
    args = parser.parse_args()

    db = resolve_db(args.db, __file__)
    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{db}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        raise SystemExit(f"ERR: БД не найдена: {db}")
    lines = []

    # Header
    group = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    group_name = group[0] if group else "?"
    lines.append(f"# 🐉 Горди — дамп группы «{group_name}»")
    # UTC, явным суффиксом — правило timestamp-utc-in-sqlite v2 (владелец 2026-07-16):
    # контур живёт в ОДНОЙ шкале. Метка без зоны неотличима от локальной.
    lines.append(f"> Экспорт: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n")

    # Rules
    # ⚡ ОТОЗВАННЫЕ ПОМЕЧАЮТСЯ (карточка #89, шаг 3). До 2026-08-10 эта выгрузка не
    #    различала отзыв ВООБЩЕ и печатала все десять отозванных правил вровень с
    #    действующими — то есть свод, выгруженный отсюда, приказывал отменённое.
    #    Признак берётся из общего модуля: три места контура держали три разных признака,
    #    и на различающих написаниях они расходились все четыре раза (замер 08:28 UTC).
    lines.append("## 📋 Правила\n")
    for r in RS.read_rules(conn):
        mark = "⛔ **ОТОЗВАНО** " if r["revoked"] else ""
        lines.append(f"- {mark}**{r['rule_key']}** (🔒{r['locked_by']}): {r['body']}")
    lines.append("")

    # Tracks
    lines.append("## 🎯 Треки\n")
    for row in conn.execute("SELECT track_id, title, status FROM tracks ORDER BY status"):
        emoji = {"active": "🟢", "paused": "🟡", "done": "⚪"}.get(row[2], "❓")
        lines.append(f"- {emoji} **{row[0]}** — {row[1]} [{row[2]}]")
    lines.append("")

    # Invariants
    lines.append("## 🛡️ Инварианты\n")
    for row in conn.execute("SELECT code, description FROM invariants ORDER BY code"):
        lines.append(f"- **{row[0]}**: {row[1]}")
    lines.append("")

    # Messages
    lines.append(f"## 💬 Сообщения (последние {args.last})\n")
    rows = conn.execute(
        "SELECT id, writer_role, timestamp, body_md, tags, priority FROM messages ORDER BY id DESC LIMIT ?",
        (args.last,)
    ).fetchall()
    for row in reversed(rows):
        id_, role, ts, body, tags, priority = row
        tag_list = json.loads(tags) if tags else []
        tags_str = " ".join(f"`{t}`" for t in tag_list)
        prio = f" ⚠️{priority}" if priority and priority != "normal" else ""
        lines.append(f"### #{id_} [{role}] {ts}{prio}")
        if tags_str:
            lines.append(f"Tags: {tags_str}")
        lines.append(f"\n{body}\n")

    conn.close()

    output = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Экспорт → {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
