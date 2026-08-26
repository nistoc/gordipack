r"""
backup-db.py — восстановимость mezosync.db через git.

ПРОБЛЕМА (найдена 16.07): <КОНТУР>\.mezosync\mezosync.db лежит ВНЕ любого
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
<КОНТУР>\atlas.agents-sync.db — ЭТО КАТАЛОГ-РЕПО, а не файл (суффикс .db в
имени обманчив, не перепутать с mezosync.db). У него есть УДАЛЁНКА на корпоративный
GitLab — единственное во всём контуре, что переживает потерю машины.

ПОЧЕМУ ТЕКСТОВЫЙ ДАМП, А НЕ БИНАРНАЯ КОПИЯ .db ЧЕРЕЗ git-lfs (lfs 3.7.1 в системе есть):
  · git версионирует текст дельтами; бинарь лёг бы целиком на каждой ноте
  · ДАМП ДИФФ-АБЕЛЕН — и это не эстетика. 16.07 TAXO доказала инцидент с хронологией
    ИМЕННО сравнением двух срезов БД (#1952): бэкап работал как ИНСТРУМЕНТ
    РАССЛЕДОВАНИЯ, а не только как страховка. Бинарь такого не даёт.
  · восстановление точное и проверяется здесь же флагом --verify
  · lfs добавил бы зависимость там, где она не нужна

ВОССТАНОВЛЕНИЕ:
    sqlite3 mezosync-restored.db < atlas.agents-sync.db/mezosync.dump.sql

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/backup-db.py            # dry-run: покажет размер/дельту
    python <КОНТУР>/.mezosync/scripts/backup-db.py --apply --verify
"""

import argparse
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD

# 🪤 ЗДЕСЬ СТОЯЛ ПУТЬ В НАШ РЕПОЗИТОРИЙ-ЗЕРКАЛО. Найдено пробной сборкой нового проекта
# 18.08: свежий контур клал бы свой дамп В ЧУЖОЙ репозиторий — и владелец нового проекта
# увидел бы это не скоро. Путь выводится от своего контейнера; прежний остаётся запасным
# для нашего контура, где такой репозиторий действительно есть.
_own = Path(__file__).resolve().parent.parent.parent
_mirror = _own / "atlas.agents-sync.db"
OUT = (_mirror / "mezosync.dump.sql" if _mirror.is_dir()
       else _own / ".mezosync" / "backups" / "mezosync.dump.sql")

# ⚰️ Здесь стояла посылка «данные append-only ⇒ дамп уменьшаться не должен». Она умерла
# 24.08 с защитой сохранённой памяти: чистка истории версий ШТАТНО УДАЛЯЕТ строки
# (карточка #250). Убыль теперь бывает законной — но только та, чей механизм НАЗВАН.
# Замер по коду контура 26.08 (grep «DELETE FROM» по живым инструментам, не приёмкам):
#   save-phoenix.py ........ phoenix_history — чистка версий (держим 10 + самую длинную)
#   read-messages.py ....... read_batches — батч подтверждения гаснет после ack
#   split-history-table.py . messages → messages_history — переезд (сумма сохраняется)
# Любая ДРУГАЯ убыль строк — тревога, даже если дамп в байтах ВЫРОС: рост соседних
# таблиц маскирует потерю, и байтовый замер её не видел вовсе.
УБЫЛЬ_ЗАКОННА = {
    "phoenix_history": "чистка истории версий (10 + самая длинная, save-phoenix.py)",
    "read_batches": "батчи чтения гаснут после подтверждения (read-messages.py)",
}


def прежние_счётчики(out: Path):
    """Счётчики строк по таблицам из шапки ПРЕЖНЕГО дампа. None — шапки нет/не читается."""
    if not out.exists():
        return None
    try:
        with out.open(encoding="utf-8") as f:
            for _ in range(12):   # шапка живёт в первых строках, дальше не ходим
                line = f.readline()
                if line.startswith("-- строк по таблицам: "):
                    пары = line[len("-- строк по таблицам: "):].strip().split(", ")
                    return {p.split("=")[0]: int(p.split("=")[1]) for p in пары if "=" in p}
    except (OSError, ValueError):
        return None
    return None


def сверка_строк(прежние: dict, counts: dict):
    """→ (тревоги, объяснения): убыль строк против прежнего дампа, по таблицам."""
    тревоги, объяснения = [], []
    for t, was in прежние.items():
        now = counts.get(t)
        if now is None:
            тревоги.append(f"таблица {t} ИСЧЕЗЛА (было {was} строк)")
        elif now < was:
            if t in УБЫЛЬ_ЗАКОННА:
                объяснения.append(f"{t} −{was - now} — {УБЫЛЬ_ЗАКОННА[t]}")
            elif t == "messages":
                рост = counts.get("messages_history", 0) - прежние.get("messages_history", 0)
                if рост >= was - now:
                    объяснения.append(f"messages −{was - now} → messages_history +{рост} — переезд")
                else:
                    тревоги.append(f"messages −{was - now}, а messages_history выросла лишь"
                                   f" на {рост} — переездом НЕ объяснено")
            else:
                тревоги.append(f"{t} −{was - now} строк — удалять из неё никто не должен")
    return тревоги, объяснения


def main():
    ap = argparse.ArgumentParser()
        # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать то, чего
    # механизм не умеет). Проверка готовности — ПРОГОН из чужого каталога.

    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="восстановить дамп во временную БД и сверить счётчики")
    args = ap.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта

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
    # Сверка СТРОК ПО ТАБЛИЦАМ против шапки прежнего дампа — главный замер.
    # Байтовая дельта выше — только справка: она и врёт в обе стороны (карточка #250).
    прежние = прежние_счётчики(out)
    тревоги, объяснения = сверка_строк(прежние, counts) if прежние else ([], [])
    if тревоги:
        print("  🔴 СТРОКИ ПРОПАЛИ БЕЗ ЗАКОННОЙ ПРИЧИНЫ — проверь, не потеряна ли часть БД,"
              " ПРЕЖДЕ чем коммитить:")
        for т in тревоги:
            print(f"     · {т}")
        if объяснения:
            print("     (законная часть убыли, к тревоге не относится: "
                  + " · ".join(объяснения) + ")")
    elif объяснения and delta < 0:
        print("  ✅ дамп уменьшился ЗАКОННО: " + " · ".join(объяснения))
    elif old_size and delta < 0:
        if прежние is None:
            print("  ⚠️  ДАМП УМЕНЬШИЛСЯ, а шапки со счётчиками у прежнего дампа нет —"
                  " сверить по таблицам нечем. Взгляни глазами, ПРЕЖДЕ чем коммитить.")
        else:
            print("  ⚠️  ДАМП УМЕНЬШИЛСЯ, хотя строк нигде не убыло: записи стали короче."
                  " Для rules/phoenix правка по месту законна, но чисткой истории это НЕ"
                  " объяснено — взгляни глазами, ПРЕЖДЕ чем коммитить.")
    print(f"Цель: {out}")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        # Код 1 и в dry-run: тревога, которую видно только глазом, в связке команд
        # молчит — а молчащий отказ читается как успех.
        raise SystemExit(1 if тревоги else 0)

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

    # ⚰️ Здесь стояло «push — только по слову владельца». Запрет СНЯТ владельцем
    # 2026-08-08 15:56 UTC («пушить можно»); строка пережила свою причину и учила
    # роль отказываться от разрешённого. Разрушающее (force push, reset --hard)
    # словом по-прежнему защищено — rule8-destructive не отозвано.
    print("\nДальше: COORD коммитит generated/ в atlas.archs и отправляет "
          "(push разрешён без отдельного слова; сверь состав ВЕТКИ перед отправкой)")
    if тревоги:
        # Дамп при этом ЗАПИСАН: бэкап с тревогой ценнее отсутствующего — git хранит
        # прежний, терять нечего. Код 1 останавливает ровно КОММИТ в связке, как и
        # просит сама тревога.
        raise SystemExit(1)


if __name__ == "__main__":
    main()
