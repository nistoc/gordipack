# -*- coding: utf-8 -*-
"""Собрать schema/mezosync_<версия>.sql ИЗ ЖИВОЙ БАЗЫ, а не переписать руками.

🪤 Рукописная схема — это вторая копия правды, и она расходится молча. Ровно поэтому
шаблон отстал: его v2 писалась руками 18.07, живая база ушла вперёд на пять сосудов,
и никто не заметил, потому что сверять было нечем.
⇒ Схема шаблона ГЕНЕРИРУЕТСЯ из структуры живой базы. Данные не берутся вовсе —
только CREATE-выражения.

⚡ НОМЕР ВЕРСИИ ТОЖЕ СПРАШИВАЕТСЯ У БАЗЫ, А НЕ ВПЕЧАТАН (правка 2026-08-10). Прежняя
   редакция держала «v3» строкой в пути и в шапке — и в день объявления рубежа v4 молча
   ПЕРЕЗАПИСАЛА исторический файл v3 содержимым v4-схемы (спас git). Класс мой же,
   записанный в собственный слепок: впечатанное число врёт уверенно — имя и число
   берутся из источника, а не пишутся рядом.

⛔ Что НЕ попадает: сами данные, служебные таблицы sqlite, автоиндексы.
⚠️ Что попадает и это НАМЕРЕННО: ВСЕ таблицы контура, включая заведённые сегодня.
   Шаблон обязан уметь собрать контур, равный живому, — иначе он собирает вчерашний.
"""
import io
import sqlite3
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent / "prototype"))
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = str(mezo_paths.live_db())
SCHEMA_DIR = _P(__file__).resolve().parent.parent.parent / "schema"

HEAD = """-- mezosync {ver} — СХЕМА КОНТУРА. СОБРАНА ИЗ ЖИВОЙ БАЗЫ, НЕ НАПИСАНА РУКОЙ.
--
-- ⚖️ Этот файл ГЕНЕРИРУЕТСЯ (vnext/tools/gen-schema.py) из структуры живой базы;
--    номер версии взят из её журнала шагов (витрина schema_version) в момент сборки.
--    Править файл руками — значит завести расхождение заново: рукописная v2 в своё
--    время отстала от живой базы на пять сосудов, и заметить это было нечем.
-- ⚠️ Если сверх рубежа есть шаги (steps_after_milestone > 0), сборка честно скажет
--    об этом здесь: схема тогда НОВЕЕ объявленной версии.
-- Что входит в версию — спрашивай журнал: SELECT * FROM schema_migrations.
--
{tail_note}"""


def main():
    src = sqlite3.connect(f"file:{LIVE.replace(chr(92), '/')}?mode=ro", uri=True)
    src.execute("PRAGMA query_only=ON")
    # версия — у БАЗЫ, не у автора. Витрины может не быть (старый контур) — тогда
    # честное 'v0-unversioned', а не выдуманный номер.
    try:
        ver, _steps, after = src.execute("SELECT * FROM schema_version").fetchone()
        ver = ver or "v0-unversioned"
    except sqlite3.OperationalError:
        ver, after = "v0-unversioned", 0
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

    out = SCHEMA_DIR / f"mezosync_{ver}.sql"
    tail = ("-- 🔴 ВНИМАНИЕ: сверх рубежа {n} шагов — схема НОВЕЕ объявленной версии.\n--\n"
            .format(n=after) if after else "")
    body = HEAD.format(ver=ver, tail_note=tail)
    body += "-- собрано: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())) + "\n\n"
    body += "\n\n".join(parts) + "\n"
    io.open(out, "w", encoding="utf-8", newline="\n").write(body)
    print(f"✅ {out}")
    print(f"   версия из базы: {ver} · сверх рубежа {after} · {counts} · {len(body)} знаков")


if __name__ == "__main__":
    main()
