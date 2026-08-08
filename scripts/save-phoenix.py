"""
save-phoenix.py — CLI для агента: сохранить phoenix-слепок в mezosync.db.

Использование:
    python save-phoenix.py --db .mezosync/mezosync.db --role COORD --section state --body "текст слепка"
    python save-phoenix.py --db .mezosync/mezosync.db --role COORD --section state --file phoenix-state.md
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Сохранить phoenix-слепок")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--role", required=True, help="Роль (COORD, CORE, ...)")
    # launcher/rebirth/sources добавлены 2026-07-16: замер показал, что МЕХАНИЗМУ
    # ВОСКРЕШЕНИЯ РОЛИ НЕГДЕ ЖИТЬ В БД. У COORD/CORE/ING/STUD launcher'а в БД не было
    # ВООБЩЕ; у TAXO/RCC/EYE/GRF он попал в `identity` СЛУЧАЙНО, прозой. При этом сам
    # текст launcher'а звучит «Прочитай ...\phoenix.<роль>.md и начни работать по нему»
    # — то есть УКАЗЫВАЕТ НА md. Отключи md на Фазе 4 — и владелец вставит эту строку в
    # новый чат, а роль прочитает пустоту. МОЛЧА. Сломался бы ровно тот инструмент,
    # которым чинят всё остальное.
    # Схема правки НЕ требует: phoenix.section — свободный TEXT, ограничение жило
    # только здесь, в choices.
    #   launcher — одна строка, которую владелец копирует в новый чат роли
    #   rebirth  — что роль делает ПЕРВЫМ делом, проснувшись (порядок чтения, границы)
    #   sources  — источники правды роли в порядке чтения
    parser.add_argument("--section", required=True,
                        choices=["identity", "state", "plan", "history",
                                 "launcher", "rebirth", "sources"],
                        help="Секция слепка")
    parser.add_argument("--body", default=None, help="Текст слепка (или --file)")
    parser.add_argument("--file", default=None, help="Файл с текстом слепка")
    # ⚠️ ФЛАГ, КОТОРЫЙ ОБЯЗАН БЫТЬ ЯВНЫМ. Сокращение секции в разы бывает законным
    # (роль выбросила устаревшее), но должно быть НАЗВАНО, а не случиться молча.
    parser.add_argument("--allow-shrink", action="store_true",
                        help="разрешить сокращение секции в разы: сознательная чистка, "
                             "а не потеря. Пустое тело не разрешает и он")
    args = parser.parse_args()

    if not args.body and not args.file:
        print("ERR: укажите --body или --file", file=sys.stderr)
        sys.exit(1)

    body = args.body if args.body else Path(args.file).read_text(encoding="utf-8")

    # Регистр роли нормализуется ЗДЕСЬ ТОЖЕ. read-messages и read-phoenix уже приводят
    # роль к UPPER; save-phoenix — НЕТ, и это «расщепление роли»: слепок, сохранённый как
    # «core», не находится читателем, ищущим «CORE» (phoenix.role — часть PRIMARY KEY без
    # COLLATE NOCASE, тот же класс, что 8 lowercase-курсоров-призраков EYE #2063).
    # Нормализуем на входе — один регистр во всём контуре.
    role = args.role.upper()

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{args.db}?mode=rw", uri=True, timeout=5)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")
    # ── 🩸 ЗАЩИТА ПАМЯТИ РОЛИ. Случай @RCC 2026-08-07 16:56 UTC, дословно: правил секцию
    # скриптом, тот упал ПОСЛЕ открытия файла на запись, файл обнулился, инструмент принял
    # пустоту и отчитался «OK phoenix/RCC/rebirth (0 chars)». Секция, которая учит преемника
    # порядку пробуждения, пролежала пустой четыре минуты.
    # 🪤 Класс: «OK ≠ сохранено», родня контурного «200 ≠ работает». И хуже: сторож живости
    # слепков смотрит на ВРЕМЯ сохранения, а не на РАЗМЕР ⇒ обнулённая секция выглядит
    # свежайшей. Пустой слепок неотличим от идеально свежего.
    # ⚖️ Порога «не меньше 200 знаков», как предлагал @RCC, здесь НЕТ намеренно: секция
    # launcher — законно ОДНА СТРОКА, и такой порог убил бы её. Поэтому два правила разных
    # сортов: пустота запрещена ВСЕГДА, а обвал в разы — только против ПРЕЖНЕГО размера.
    prev = conn.execute("SELECT length(body) FROM phoenix WHERE role=? AND section=?",
                        (role, args.section)).fetchone()
    was = prev[0] if prev else 0
    now = len(body)

    if not body.strip():
        conn.close()
        sys.exit(f"⛔ ОТКАЗ: тело секции ПУСТО (было {was} знаков).\n"
                 f"   Пустых секций не бывает: слепок учит преемника, а пустота учит ничему —\n"
                 f"   и при этом выглядит свежайшей, потому что сторож смотрит на ВРЕМЯ.\n"
                 f"   👉 Проверь файл: скорее всего он обнулился при записи, а не опустел по смыслу.")

    if was >= 400 and now * 4 < was and not args.allow_shrink:
        conn.close()
        sys.exit(f"⛔ ОТКАЗ: секция ужимается в {was / max(now, 1):.1f} раза "
                 f"({was} → {now} знаков).\n"
                 f"   Перезапись в разы — почти всегда авария записи, а не намерение.\n"
                 f"   👉 Если чистка СОЗНАТЕЛЬНАЯ, скажи это словом: --allow-shrink")

    conn.execute("""
        INSERT INTO phoenix (role, section, body, saved_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(role, section) DO UPDATE SET body = excluded.body, saved_at = excluded.saved_at
    """, (role, args.section, body))

    conn.execute("""
        INSERT INTO audit_log (actor_role, action, target, diff_md)
        VALUES (?, 'save_phoenix', ?, ?)
    """, (role, f"phoenix.{role}.{args.section}", f"Updated {args.section} ({len(body)} chars)"))

    conn.commit()
    conn.close()
    # 🎯 Размер печатается ДВУМЯ числами, «было → стало». Прежняя строка «OK … (0 chars)»
    # читалась глазом как подтверждение: ноль стоял в той же строке, что и «OK», и не
    # спорил с ним. Два числа спорят сами: 10489 → 0 не прочитаешь как успех.
    delta = "первое сохранение" if was == 0 else f"было {was} → стало {now} знаков"
    print(f"OK phoenix/{role}/{args.section} — {delta}"
          + ("   ⚠️ сокращение разрешено словом --allow-shrink"
             if args.allow_shrink and was > now else ""))


if __name__ == "__main__":
    main()
