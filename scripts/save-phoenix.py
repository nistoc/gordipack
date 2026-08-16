"""
save-phoenix.py — CLI для агента: сохранить phoenix-слепок в mezosync.db.

Использование:
    python <КОНТУР>/.mezosync/scripts/save-phoenix.py --role COORD --section state --body "текст слепка"
    python <КОНТУР>/.mezosync/scripts/save-phoenix.py --role COORD --section state --file phoenix-state.md
"""

import argparse
import sqlite3
import dryrun          # холостой прогон (13.08)
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD


def main():
    parser = argparse.ArgumentParser(description="Сохранить phoenix-слепок")
    # R15a: --db не обязателен, резолвится от расположения СКРИПТА (не от CWD).
    dryrun.add_argument(parser)
    parser.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
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
    # ── КТО ПРАВИТ ≠ ЧЬЯ СЕКЦИЯ (карточка #164, 2026-08-13). Прежде в audit_log шло
    # значение --role — ВЛАДЕЛЕЦ слепка, а не исполнитель. Цена показана 10.08: владелец
    # спросил «что COORD правил за смену», и единственная запись по COORD оказалась правкой
    # PROTO (§7 — его зона). Проверка добросовестности роли получила бы ложную улику.
    # Форма — из backlog.py (--actor отдельным флагом от --role): она в контуре уже принята.
    # Образец честного авторства — applied_by в журнале схемы: ставится механизмом.
    parser.add_argument("--actor", default=None,
                        help="КТО правит, если не владелец секции (напр. --actor PROTO при "
                             "правке чужого слепка). Без флага журнал пишет владельца — "
                             "прежнее поведение, для правки СВОЕЙ секции оно верно")
    # ── ОТМЕТКА «СМОТРЕЛ, ПРАВОК НЕТ» (карточка #160) ────────────────────────────
    # 🪤 Класс: снаружи ВЗГЛЯД БЕЗ ПРАВКИ НЕОТЛИЧИМ ОТ ПРОПУСКА. Роль честно говорит
    # «прошёл все семь секций», а у одной дата сохранения недельной давности — и оба
    # утверждения верны одновременно. Протез словом в теле («🔎 ВЗГЛЯД БЫЛ, ПРАВОК НЕТ
    # — <дата>») заводит вторую ложь того же рода: строка переживёт следующую правку
    # и начнёт утверждать взгляд, которого не было.
    # ⚖️ Почему НЕ отдельная команда «сбросить отметку»: отметка обязана гаснуть САМИМ
    # изменением текста — иначе её сброс становится дисциплиной, а дисциплина и есть то,
    # что мы чиним механизмом.
    parser.add_argument("--confirm", action="store_true",
                        help="отметить «секцию перечитал, правок не нашлось»: ставит время "
                             "ВЗГЛЯДА, не трогая ни тело, ни время текста. Тело при этом "
                             "не нужно. Правка тела сдвигает обе даты — и взгляд снова "
                             "равен записи, то есть «после правки не перечитано»")
    args = parser.parse_args()

    # Регистр роли НОРМАЛИЗУЕТСЯ к верхнему (как в read-messages.py/read-phoenix.py): иначе
    # `save-phoenix --role stud` завёл бы ВТОРОЙ слепок (role='stud' ≠ 'STUD' по UNIQUE(role,section)),
    # а `read-phoenix --role STUD` вернул бы старый — роль МОЛЧА теряет свёртку, гарды зелёные.
    # Латентная мина: найдена PROTO 2026-07-25 (#2665), подтверждена COORD замером, починка по слову владельца.
    role = args.role.upper()
    # Регистр исполнителя — та же нормализация, что у роли (иначе расщепление PROTO/proto).
    actor = args.actor.upper() if args.actor else role
    # Путь к БД — та же нормализация входа, что регистр роли (R15a).
    args.db = str(resolve_db(args.db, __file__))

    if args.confirm and (args.body or args.file):
        print("ERR: --confirm отмечает ВЗГЛЯД и потому НЕ принимает тело. Если правки есть — "
              "сохраняй тело обычным вызовом (он сам погасит прежнюю отметку).", file=sys.stderr)
        sys.exit(1)

    if not args.confirm and not args.body and not args.file:
        print("ERR: укажите --body или --file (или --confirm — «смотрел, правок нет»)",
              file=sys.stderr)
        sys.exit(1)

    body = None if args.confirm else (args.body if args.body
                                      else Path(args.file).read_text(encoding="utf-8"))

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = dryrun.connect(f"file:{args.db}?mode=rw", args.dry_run,
                              uri=True, timeout=5)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")
    # ── 🩸 ЗАЩИТА ПАМЯТИ РОЛИ. Правка @PROTO в шаблоне gordipack (17:02 UTC), перенесена
    # в живой инструмент моей рукой — граница зон: шаблон его, `.mezosync/scripts` мои.
    # Случай @RCC 07.08 16:56 UTC дословно: правил секцию скриптом, тот упал ПОСЛЕ открытия
    # файла на запись, файл обнулился, инструмент принял пустоту и отчитался
    # «OK phoenix/RCC/rebirth (0 chars)». Секция, которая учит преемника порядку
    # пробуждения, пролежала пустой четыре минуты.
    # 🪤 Класс: «OK ≠ сохранено», родня контурного «200 ≠ работает». И хуже: сторож живости
    # слепков смотрит на ВРЕМЯ сохранения, а не на РАЗМЕР ⇒ обнулённая секция выглядит
    # свежайшей. Пустой слепок неотличим от идеально свежего.
    # ⚖️ Порога «не меньше 200 знаков», как предлагал @RCC, здесь НЕТ намеренно: секция
    # launcher — законно ОДНА СТРОКА, и такой порог убил бы её. Поэтому два правила разных
    # сортов: пустота запрещена ВСЕГДА, а обвал в разы — только против ПРЕЖНЕГО размера.
    prev = conn.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                        (role, args.section)).fetchone()
    prev_body = prev[0] if prev else None
    was = len(prev_body) if prev_body is not None else 0

    has_confirmed_col = "confirmed_at" in {r[1] for r in conn.execute("PRAGMA table_info(phoenix)")}

    if args.confirm:
        # Подтверждать НЕЧЕГО, если секции нет: «смотрел» без предмета — пустое утверждение.
        if prev_body is None:
            conn.close()
            sys.exit(f"⛔ ОТКАЗ: секции {role}/{args.section} в базе НЕТ — подтверждать нечего.\n"
                     f"   «Смотрел, правок нет» о несуществующем тексте было бы утверждением "
                     f"ни о чём.\n   👉 Сперва сохрани тело: --file <файл>")
        if not has_confirmed_col:
            conn.close()
            sys.exit("⛔ ОТКАЗ: в этой базе нет колонки confirmed_at — отметке негде лечь.\n"
                     "   Прогони migrations/20260808-phoenix-confirmed-at.py и повтори.")
        conn.execute("UPDATE phoenix SET confirmed_at = datetime('now') "
                     "WHERE role=? AND section=?", (role, args.section))
        conn.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) "
                     "VALUES (?, 'confirm_phoenix', ?, ?)",
                     (actor, f"phoenix.{role}.{args.section}",
                      f"взгляд без правки ({was} знаков, тело не тронуто)"
                      + (f" [чужая секция: смотрел {actor}]" if actor != role else "")))
        conn.commit()
        conn.close()
        print(f"👁 phoenix/{role}/{args.section} — ВЗГЛЯД ОТМЕЧЕН ({was} знаков, тело не тронуто).")
        print("  Возраст ТЕКСТА не сдвинут — сдвинут возраст ВЗГЛЯДА: это разные факты.")
        print("  Отметка ПОГАСНЕТ сама при следующей записи тела — сбрасывать её командой не нужно.")
        return

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

    # 🎯 МЕРА ③ ВАРИАНТА А (слово владельца 2026-08-08 16:19 UTC): сравнивается СОДЕРЖИМОЕ,
    # а не время. Если текст не изменился НИ НА ЗНАК — время сохранения НЕ ТРОГАЕМ.
    # 🪤 Иначе «нажать сохранить, ничего не изменив» выглядит свежестью: ровно так гасился
    #    сторож ⑥ (замер 07.08). Пересохранение — это ДЕЙСТВИЕ, а свежесть — СВОЙСТВО ТЕКСТА,
    #    и подменять второе первым значит дать механизму способ врать без единой ошибки.
    # ⚖️ Обратную половину (нетронутое, но по-прежнему верное, выглядит протухшим) чинит
    #    сторож: он объявляет отставание только если роль РАБОТАЛА после сохранения.
    has_confirmed = has_confirmed_col

    if prev_body is not None and body == prev_body:
        # Текст не изменился ⇒ возраст ТЕКСТА остаётся прежним. Но роль на него СМОТРЕЛА
        # и подтвердила — это второй, отдельный факт, и он свежий.
        if has_confirmed:
            conn.execute("UPDATE phoenix SET confirmed_at = datetime('now') "
                         "WHERE role=? AND section=?", (role, args.section))
            conn.commit()
        conn.close()
        print(f"= phoenix/{role}/{args.section} — СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ ({now} знаков).")
        print("  Возраст ТЕКСТА не сдвинут: иначе пересохранение вслепую выглядело бы свежестью.")
        print("  Возраст ВЗГЛЯДА обновлён: роль текст перечитала и подтвердила."
              if has_confirmed else
              "  ⚠️ колонки confirmed_at нет — прогони migrations/20260808-phoenix-confirmed-at.py")
        return

    if has_confirmed:
        # ⚖️ ЗАПИСЬ ТЕЛА СТАВИТ ОБЕ ДАТЫ — это МЕРА ③ ВАРИАНТА А, слово владельца
        # 2026-08-08 16:19 UTC, и у неё есть своя приёмка (bite-phoenix-confirmed,
        # случаи ①②). Смысл: автор, записавший текст, на него СМОТРЕЛ — взгляд был.
        # 🪤 16.08 я едва не отменил эту меру молча: чиня карточку #160, поставил здесь
        # confirmed_at = NULL, не проверив, нет ли по этому полю УЖЕ принятого решения.
        # Поймала общая приёмка (bite-all), а не я сам. Класс записан вслух: правя поле,
        # спроси сперва, чьё решение в нём живёт, — иначе починка одной карточки
        # отменяет чужую меру, и обе стороны выглядят добросовестными.
        # ⇒ Три состояния различает ВИТРИНА, а не гашение: confirmed == saved — «текст
        # только записан, после правки не перечитан»; confirmed > saved — «перечитан
        # и признан верным»; confirmed < saved — правка мимо инструмента.
        conn.execute("""
            INSERT INTO phoenix (role, section, body, saved_at, confirmed_at)
            VALUES (?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(role, section) DO UPDATE SET body = excluded.body,
                saved_at = excluded.saved_at, confirmed_at = datetime('now')
        """, (role, args.section, body))
    else:
        conn.execute("""
            INSERT INTO phoenix (role, section, body, saved_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(role, section) DO UPDATE SET body = excluded.body,
                saved_at = excluded.saved_at
        """, (role, args.section, body))

    # В actor_role — ИСПОЛНИТЕЛЬ; чья секция — уже в target. Прежде оба поля несли роль,
    # и вопрос «кто это сделал» получал уверенный неверный ответ (карточка #164).
    diff_note = (f"Updated {args.section} ({len(body)} chars)"
                 + (f" [чужая секция: правил {actor}]" if actor != role else ""))
    conn.execute("""
        INSERT INTO audit_log (actor_role, action, target, diff_md)
        VALUES (?, 'save_phoenix', ?, ?)
    """, (actor, f"phoenix.{role}.{args.section}", diff_note))

    conn.commit()
    conn.close()
    # 🎯 Размер печатается ДВУМЯ числами, «было → стало». Прежняя строка «OK … (0 chars)»
    # читалась глазом как подтверждение: ноль стоял в той же строке, что и «OK», и не
    # спорил с ним. Два числа спорят сами: 10489 → 0 не прочитаешь как успех.
    delta = "первое сохранение" if was == 0 else f"было {was} → стало {now} знаков"
    print(f"OK phoenix/{role}/{args.section} — {delta}"
          + ("   ⚠️ сокращение разрешено словом --allow-shrink"
             if args.allow_shrink and was > now else "")
          + (f"   ✍️ правил {actor} (чужая секция, журнал знает)" if actor != role else ""))


if __name__ == "__main__":
    main()
