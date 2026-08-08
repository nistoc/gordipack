# -*- coding: utf-8 -*-
"""Собрать schema/mezosync_v3.sql ИЗ ЖИВОЙ БАЗЫ, а не переписать руками.

🪤 Рукописная схема — это вторая копия правды, и она расходится молча. Ровно поэтому
шаблон отстал: его v2 писалась руками 18.07, живая база ушла вперёд на пять сосудов,
и никто не заметил, потому что сверять было нечем.
⇒ Схема шаблона ГЕНЕРИРУЕТСЯ из структуры живой базы. Данные не берутся вовсе —
только CREATE-выражения.

⛔ Что НЕ попадает: сами данные, служебные таблицы sqlite, автоиндексы.
⚠️ Что попадает и это НАМЕРЕННО: ВСЕ таблицы контура, включая заведённые сегодня.
   Шаблон обязан уметь собрать контур, равный живому, — иначе он собирает вчерашний.
"""
import io
import sqlite3

LIVE = r"C:\guts\.atlas\.mezosync\mezosync.db"
OUT = r"C:\github\gordipack\schema\mezosync_v3.sql"

HEAD = """-- mezosync v3 — СХЕМА КОНТУРА. СОБРАНА ИЗ ЖИВОЙ БАЗЫ, НЕ НАПИСАНА РУКОЙ.
--
-- Повод (замер 2026-08-08 22:39 UTC): рукописная v2 отстала от живой базы на ПЯТЬ сосудов,
-- и заметить это было нечем — рукописная схема есть вторая копия правды, а вторая копия
-- расходится молча. Контур, собранный из v2 в этот день, не получал НИЧЕГО из сделанного
-- за смену и выглядел при этом исправным.
--
-- ⚖️ ПОЭТОМУ: этот файл ГЕНЕРИРУЕТСЯ (vnext/tools/gen-schema.py) из структуры живой базы.
--    Править его руками — значит завести расхождение заново.
--
-- ЧТО ДОБАВИЛОСЬ ПРОТИВ v2 (всё — работы 2026-08-07/08):
--   rules.basis / authorized / source_ref / expiry_kind / expiry_cond
--                              основание правила и УСЛОВИЕ ЕГО ОТМЕНЫ полями, а не прозой
--   phoenix.confirmed_at       возраст ВЗГЛЯДА отдельно от возраста ТЕКСТА
--   message_addressee          имена адресатов: обращение отдельно от копии
--   role_rights (+ витрина)    права роли полями; разовое право ТРАТИТСЯ и это видно
--   sync_backoff               разгон сна между синками — одно место на весь контур
--   cursor_segments · message_thread · message_task · roles · backlog_* и прочее из v3-наката
--
"""


def main():
    src = sqlite3.connect(f"file:{LIVE.replace(chr(92), '/')}?mode=ro", uri=True)
    src.execute("PRAGMA query_only=ON")
    rows = src.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, name").fetchall()
    src.close()

    parts, counts = [], {}
    for typ, name, sql in rows:
        counts[typ] = counts.get(typ, 0) + 1
        s = sql.strip()
        # Идемпотентность — требование правила migration-safety: сборка не должна падать
        # на повторе, иначе «собери контур ещё раз» станет разрушающим действием.
        for a, b in (("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "),
                     ("CREATE VIEW ", "CREATE VIEW IF NOT EXISTS "),
                     ("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS "),
                     ("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")):
            if s.upper().startswith(a) and "IF NOT EXISTS" not in s.upper()[:60]:
                s = b + s[len(a):]
                break
        parts.append(s.rstrip(";") + ";")

    body = HEAD + "-- собрано: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())) + "\n\n"
    body += "\n\n".join(parts) + "\n"
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(body)
    print(f"✅ {OUT}")
    print(f"   {counts} · {len(body)} знаков")


if __name__ == "__main__":
    main()
