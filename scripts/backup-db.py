r"""
backup-db.py — восстановимость mezosync.db через git.

ПРОБЛЕМА (найдена 16.07): C:\guts\.atlas\.mezosync\mezosync.db лежит ВНЕ любого
git-репозитория — контейнер .atlas это не репо, а папка с независимыми репо внутри.
При этом sync.*.md версионируются в atlas.archs. То есть на 16.07 md были ЕДИНСТВЕННОЙ
восстановимой копией истории координации, а БД — одним файлом на одной машине.
Отключить md, не закрыв это, значило бы масштабировать беду STUD (4 дня без фолбэка)
на весь контур.

РЕШЕНИЕ: `.dump` базы в ТЕКСТОВЫЙ .sql внутрь atlas.archs (репо) + коммит.
Почему дамп, а не копия .db:
  · git версионирует текст дельтами; бинарь пришлось бы хранить целиком каждый тик
  · дамп человекочитаем и diff-абелен — видно, ЧТО изменилось между тиками
  · восстановление точное: sqlite3 new.db < dump.sql
  · бинарная копия .db в git дала бы конфликты, которые нечем разрешать

КУДА (решение владельца 16.07 13:25, принёс EYE #1989): выделенный репозиторий
C:\guts\.atlas\atlas.agents-sync.db — ЭТО КАТАЛОГ-РЕПО, а не файл (суффикс .db в
имени обманчив, не перепутать с mezosync.db). У него есть УДАЛЁНКА на корпоративный
GitLab — единственное во всём контуре, что переживает потерю машины.

ПОЧЕМУ ТЕКСТОВЫЙ ДАМП, А НЕ БИНАРНАЯ КОПИЯ .db ЧЕРЕЗ git-lfs (lfs 3.7.1 в системе есть):
  · git версионирует текст дельтами; бинарь лёг бы целиком на каждой ноте
  · ДАМП ДИФФ-АБЕЛЕН — и это не эстетика. 16.07 TAXO доказала инцидент с хронологией
    ИМЕННО сравнением двух срезов БД (#1952): бэкап работал как ИНСТРУМЕНТ
    РАССЛЕДОВАНИЯ, а не только как страховка. Бинарь такого не даёт.
  · восстановление точное и проверяется здесь же флагом --verify
  · lfs добавил бы зависимость там, где она не нужна

⚠️ ПОРТАТИВНОСТЬ ШАБЛОНА. Цель дампа по умолчанию выводится из расположения скрипта
(<контур>/.mezosync/mezosync.dump.sql), а не хардкодится на atlas.agents-sync.db. Куда
именно версионировать дамп — решает конкретный контур; переопредели путь флагом --out
на каталог-репо с удалёнкой (в Atlas это atlas.agents-sync.db).

ВОССТАНОВЛЕНИЕ:
    sqlite3 mezosync-restored.db < <out>/mezosync.dump.sql

ЗАПУСК:
    python backup-db.py --db <path>            # dry-run: покажет размер/дельту
    python backup-db.py --db <path> --apply --verify
"""

import argparse
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Цель дампа по умолчанию — рядом с БД (<контур>/.mezosync/mezosync.dump.sql). Портативно;
# для версионирования на удалёнку переопредели --out на каталог-репо конкретного контура.
OUT = Path(__file__).resolve().parent.parent / "mezosync.dump.sql"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="восстановить дамп во временную БД и сверить счётчики")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

    out = Path(args.out)
    old_size = out.stat().st_size if out.exists() else 0

    lines = ["-- mezosync.db — текстовый дамп для git-восстановимости",
             f"-- снят: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
             f"-- источник: {args.db}",
             "-- восстановление: sqlite3 new.db < этот_файл",
             "-- строк по таблицам: " + ", ".join(f"{t}={n}" for t, n in counts.items()),
             ""]
    lines.extend(conn.iterdump())
    dump = "\n".join(lines) + "\n"

    # ⚠️ МЕРЯЕМ В БАЙТАХ, А НЕ В СИМВОЛАХ. len(dump) — символы; файл на диске — UTF-8,
    # где кириллица занимает 2 байта. Сравнение len(dump) с old_size (байты) давало
    # «дамп усох на треть» при выросшей БД — ложная тревога о потере данных, а в обратную
    # сторону такая шкала замаскировала бы РЕАЛЬНУЮ потерю. Инструмент бэкапа, врущий
    # числом, хуже отсутствующего.
    new_size = len(dump.encode("utf-8"))
    delta = new_size - old_size
    print(f"Таблиц: {len(tables)} · строк всего: {sum(counts.values())}")
    print(f"Дамп: {new_size/1024:.0f} КБ" + (
        f"  (был {old_size/1024:.0f} КБ, {'+' if delta >= 0 else ''}{delta/1024:.1f} КБ)"
        if old_size else "  (первый снимок)"))
    if old_size and delta < 0:
        print("  ⚠️  ДАМП УМЕНЬШИЛСЯ. Данные append-only ⇒ такого быть не должно. "
              "Проверь, не потеряна ли часть БД, ПРЕЖДЕ чем коммитить.")
    print(f"Цель: {out}")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" ОБЯЗАТЕЛЕН: без него write_text на Windows разворачивает \n в \r\n,
    # и файл на диске становится больше строки в памяти на ~1 байт/строку (~5 КБ на
    # 5300 строк). Тогда сравнение «новый (память) vs старый (диск)» опять меряет разное
    # и гард усушки кричит на пустом месте. Плюс .gitattributes требует eol=lf.
    out.write_text(dump, encoding="utf-8", newline="\n")
    print(f"\n✅ Дамп записан: {out.name}")

    if args.verify:
        # ГАРД: дамп, который не восстанавливается, — не бэкап, а иллюзия бэкапа.
        tmp = out.parent / "_verify.db"
        tmp.unlink(missing_ok=True)
        try:
            v = sqlite3.connect(str(tmp))
            v.executescript(dump)
            bad = []
            for t, n in counts.items():
                got = v.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                if got != n:
                    bad.append(f"{t}: было {n}, восстановилось {got}")
            v.close()
            if bad:
                print("⛔ ВОССТАНОВЛЕНИЕ РАСХОДИТСЯ:")
                for b in bad:
                    print("   ", b)
                raise SystemExit(1)
            print(f"✅ ВЕРИФИКАЦИЯ: дамп восстановлен во временную БД, все {len(counts)} таблиц сошлись по счётчикам")
        finally:
            tmp.unlink(missing_ok=True)

    print("\nДальше: COORD коммитит дамп в версионированный репо (push — только по слову владельца)")


if __name__ == "__main__":
    main()
