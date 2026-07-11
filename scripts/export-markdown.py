"""
export-markdown.py — Экспорт содержимого mezosync.db в читаемый Markdown.

Для владельца: быстрый обзор без SQLite-клиента.

Использование:
    python export-markdown.py --db "C:\guts\.atlas\.mezosync\mezosync.db" --out report.md
    python export-markdown.py --db mezosync.db --last 50  # только последние 50 сообщений
"""

import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Экспорт mezosync.db → Markdown")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--out", default=None, help="Выходной .md файл (по умолчанию stdout)")
    parser.add_argument("--last", type=int, default=100, help="Сколько последних сообщений")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    lines = []

    # Header
    group = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    group_name = group[0] if group else "?"
    lines.append(f"# 🐉 Горди — дамп группы «{group_name}»")
    lines.append(f"> Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Rules
    lines.append("## 📋 Правила\n")
    for row in conn.execute("SELECT rule_key, body, locked_by FROM rules ORDER BY rule_key"):
        lines.append(f"- **{row[0]}** (🔒{row[2]}): {row[1]}")
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
