"""
save-phoenix.py — CLI для агента: сохранить phoenix-память в mezosync.db.

Использование:
    python <КОНТУР>/.mezosync/scripts/save-phoenix.py --role COORD --section state --body "текст памяти"
    python <КОНТУР>/.mezosync/scripts/save-phoenix.py --role COORD --section state --file phoenix-state.md
"""

import argparse
import re
import sqlite3
import dryrun          # холостой прогон (13.08)
import sys
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD


# ═══════════════════════════════════════════════════════════════════════════════
# ПОРОГИ ПОТЕРИ. Числа НЕ из головы: посчитаны по audit_log 2026-08-23 — 1321 запись
# о сохранении памяти, 312 сокращений. Судить по всей истории нельзя: до 08.08 контур
# строился и крупные законные обвалы были нормой. Зрелый период (с 08.08), 88 сокращений:
#     порог −30% ... 23 сработки (1.5/сут)    порог −40% ... 13 (0.9/сут)  ← ВЫБРАНО
#     порог −50% ... 10 (0.7/сут)             порог −60% ...  5 (0.3/сут)
#     нынешний «в 4 раза» ... 0 за 15 дней и 10 за всё время
# 🔴 Он не сработал НИ РАЗУ за зрелый период, включая инцидент OPSSRE 21.08 22:28 UTC
#    (18808 → 7455, потеря 60.4%): «в 4 раза» требует 75%.
# ⚖️ ПОЧЕМУ 40, А НЕ 60: инцидент даёт 60.4%, и порог 60 сел бы НА САМУ ВЫБОРКУ — запас
#    в 0.4 процентного пункта это не порог, это совпадение. Мерка, подогнанная под
#    единственный случай, меряет этот случай, а не класс.
# ⚖️ И ПОЧЕМУ НЕ 30: защита, останавливающая роль по 4 раза в день, обучает добавлять
#    --allow-shrink не глядя. Такая защита ХУЖЕ отсутствующей: она создаёт видимость охраны.
SHRINK_FLOOR = 400      # ниже этого размера долями не судим
SHRINK_HARD = 0.40      # доля потери объёма — ОТКАЗ
KEEP_VERSIONS = 10      # сколько версий секции держим в истории (плюс самую длинную)

_HEAD_ANY = re.compile(r"^#{1,6}\s+\S")
_BOLD = re.compile(r"^\*\*.+\*\*$")


def blocks_of(text):
    """→ (имя признака, [подписи блоков]). Лестница: «## » → любой «#» → жирная строка.

    🪤 ЛЕСТНИЦА НУЖНА ПО ЗАМЕРУ, А НЕ ДЛЯ КРАСОТЫ (замер 23.08): у 16 из 63 ЖИВЫХ секций
    заголовков «## » НЕТ ВООБЩЕ — вся память COORD (6 секций), вся память RCC (6, включая
    plan на 17243 знака), ING/launcher, PROTO/launcher, OPSSRE/rebirth, OPSSRE/sources.
    Отчёт «по заголовкам» молчал бы на ЧЕТВЕРТИ контура, и молчание читалось бы как
    «ничего не исчезло». «Нечем сравнить» и «всё цело» не имеют права выглядеть одинаково.
    """
    h = [l.strip() for l in text.splitlines() if l.startswith("## ")]
    if h:
        return "заголовки ##", h
    h = [l.strip() for l in text.splitlines() if _HEAD_ANY.match(l)]
    if h:
        return "заголовки #", h
    h = [l.strip() for l in text.splitlines() if _BOLD.match(l.strip())]
    if h:
        return "жирные строки", h
    return None, []


_ПО_ПРИЗНАКУ = {
    "заголовки ##": lambda l: l.startswith("## "),
    "заголовки #": lambda l: bool(_HEAD_ANY.match(l)),
    "жирные строки": lambda l: bool(_BOLD.match(l.strip())),
}


def blocks_by(text, kind):
    """Блоки текста ПО НАЗВАННОМУ признаку — без выбора признака заново.

    🩸 ОПЛАЧЕНО @COORD (записка #3918 §②, 26.08): его отчёт сказал «ИСЧЕЗАЮТ БЛОКИ 2 из 2»
    и строкой ниже «исчезло дословно 0 (0%)» — на записи, где не потеряно НИЧЕГО.
    Причина не в том, где ищутся блоки, а в том, ЧЕМ они меряются: признак выбирался
    лестницей ОТДЕЛЬНО для старого и нового тела. Прежнее тело без «## » давало
    «жирные строки», дописанный сверху свежий раздел с «## » переключал новое тело на
    «заголовки ##» — и старые жирные строки сравнивались с новыми заголовками.
    Пересечение пусто ПО ПОСТРОЕНИЮ ⇒ «исчезает всё» на самом безопасном действии.
    🎯 Класс: величины, снятые РАЗНЫМИ мерками, сравнивать нельзя, а смена мерки молчит.
    ⚖️ Сторож, кричащий на исправном, учит не слышать крик — и следующая тревога,
    настоящая, будет пролистана.
    """
    подходит = _ПО_ПРИЗНАКУ.get(kind)
    if not подходит:
        return []
    return [l.strip() for l in text.splitlines() if подходит(l)]


def lines_of(text):
    """Содержательные строки. Порог 12 знаков отсекает разделители и «---», иначе доля
    исчезнувшего плавала бы на косметике."""
    return [l.strip() for l in text.splitlines() if len(l.strip()) >= 12]


def loss_report(prev_body, body, limit=6):
    """→ (доля исчезнувших СТРОК, [строки отчёта]).

    📏 Замер на живых телах (копия базы за 20.08 против базы 22.08, 11 изменившихся секций):
       законные правки — 0 исчезнувших блоков и 0–24% исчезнувших строк;
       инцидент OPSSRE — 11 блоков из 11 и 100% строк.
       ⇒ признак РАЗЛИЧАЕТ, а не краснеет на всё подряд.
    """
    kind, old_b = blocks_of(prev_body)
    # Новое тело меряется ТЕМ ЖЕ признаком, что и старое (см. blocks_by): выбор признака
    # заново и был причиной ложной тревоги. Вид признака нового тела нужен отдельно —
    # чтобы честно назвать СМЕНУ РАЗМЕТКИ, а не выдать её за потерю.
    new_b = blocks_by(body, kind) if kind else []
    kind_new, _ = blocks_of(body)
    new_bset = set(new_b)
    gone_b = [b for b in old_b if b not in new_bset]
    old_l, new_l = lines_of(prev_body), set(lines_of(body))
    gone_l = [l for l in old_l if l not in new_l]
    share = len(gone_l) / len(old_l) if old_l else 0.0

    rep = []
    if kind:
        if gone_b and not new_b and kind_new and kind_new != kind:
            # Разметку сменили целиком: прежним признаком в новом теле НЕТ НИ ОДНОГО блока,
            # зато есть блоки другого рода. «Сравнивать нечем» и «всё исчезло» — разные
            # вещи, и выдавать первое за второе значит обвинять без разбора. Настоящую
            # потерю здесь ловит доля СТРОК (строка ниже) и порог отказа по объёму.
            rep.append("   ⚠️ РАЗМЕТКА СМЕНИЛАСЬ: было «%s» (%d), стало «%s» — по блокам "
                       "СРАВНИВАТЬ НЕЧЕМ, это НЕ «всё исчезло». Суди по строкам ниже"
                       % (kind, len(old_b), kind_new))
        elif gone_b:
            rep.append("   ИСЧЕЗАЮТ БЛОКИ (%s): %d из %d" % (kind, len(gone_b), len(old_b)))
            rep += ["      · " + b[:100] for b in gone_b[:limit]]
            if len(gone_b) > limit:
                rep.append("      · … и ещё %d" % (len(gone_b) - limit))
        elif share >= 0.25:
            # 🪤 «Блоки целы» рядом с потерей двух третей текста — успокаивающая ложь.
            # Замер 23.08 на секции COORD/state: 0 исчезнувших блоков при 67 % исчезнувших
            # строк, потому что вся разметка секции — ОДНА жирная строка в самом верху.
            # Признак, который не может провалиться, ничего и не проверяет ⇒ здесь он
            # обязан сказать о СЕБЕ, а не о тексте.
            rep.append("   ⚠️ по блокам всё цело (было %d, %s) — но их всего %d на секцию, "
                       "и такой признак тут НИЧЕГО НЕ ЛОВИТ. Смотри строку ниже"
                       % (len(old_b), kind, len(old_b)))
        else:
            rep.append("   блоки целы: было %d (%s), исчезло 0" % (len(old_b), kind))
    else:
        rep.append("   разметки нет (ни заголовков, ни жирных строк) — сравниваю ПО СТРОКАМ. "
                   "Это НЕ «всё цело», это другой признак")
    rep.append("   содержательных строк было %d, исчезло дословно %d (%d%%)"
               % (len(old_l), len(gone_l), round(share * 100)))
    if gone_l and not gone_b:
        rep += ["      ✂ " + l[:100] for l in gone_l[:3]]
    return share, rep



def main():
    parser = argparse.ArgumentParser(description="Сохранить память роли (phoenix)")
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
                        help="Раздел памяти")
    parser.add_argument("--body", default=None, help="Текст раздела (или --file)")
    parser.add_argument("--file", default=None, help="Файл с текстом раздела")
    # ⚠️ ФЛАГ, КОТОРЫЙ ОБЯЗАН БЫТЬ ЯВНЫМ. Сокращение секции в разы бывает законным
    # (роль выбросила устаревшее), но должно быть НАЗВАНО, а не случиться молча.
    parser.add_argument("--allow-shrink", action="store_true",
                        help="разрешить сокращение секции в разы: сознательная чистка, "
                             "а не потеря. Пустое тело не разрешает и он")
    # ── КТО ПРАВИТ ≠ ЧЬЯ СЕКЦИЯ (карточка #164, 2026-08-13). Прежде в audit_log шло
    # значение --role — ВЛАДЕЛЕЦ памяти, а не исполнитель. Цена показана 10.08: владелец
    # спросил «что COORD правил за смену», и единственная запись по COORD оказалась правкой
    # PROTO (§7 — его зона). Проверка добросовестности роли получила бы ложную улику.
    # Форма — из backlog.py (--actor отдельным флагом от --role): она в контуре уже принята.
    # Образец честного авторства — applied_by в журнале схемы: ставится механизмом.
    parser.add_argument("--actor", default=None,
                        help="КТО правит, если не владелец секции (напр. --actor PROTO при "
                             "правке чужой памяти). Без флага журнал пишет владельца — "
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
    # ── ДОСТАТЬ ИЗ ИСТОРИИ. Без этих двух флагов история остаётся сырьём: она есть,
    # но роль, у которой снесло память, собирает запросы к базе руками — и делает это
    # в тот единственный момент, когда ей меньше всего до запросов.
    parser.add_argument("--history", action="store_true",
                        help="показать сохранённые версии секции: номер, час, размер, "
                             "чем записана, первая строка тела. Тело не нужно")
    parser.add_argument("--restore", default=None, metavar="ID",
                        help="вернуть тело версии с этим номером (см. --history). "
                             "Возврат создаёт НОВУЮ версию, а не подменяет прежние: "
                             "откат отката тоже возможен")
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

    if not args.confirm and not args.history and not args.restore \
            and not args.body and not args.file:
        print("ERR: укажите --body или --file (или --confirm / --history / --restore)",
              file=sys.stderr)
        sys.exit(1)

    body = (None if (args.confirm or args.history or args.restore)
            else (args.body if args.body else Path(args.file).read_text(encoding="utf-8")))

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
    # 🪤 Класс: «OK ≠ сохранено», родня контурного «200 ≠ работает». И хуже: проверка живости
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

    # ⚖️ Таблицы истории может не быть: база до миграции, песочница приёмки, свежий контур.
    # Сохранение при этом НЕ запрещается — один шаг схемы не вправе обездвижить память всех
    # ролей, — но отсутствие ГОВОРИТСЯ вслух И ЛОЖИТСЯ В ЖУРНАЛ. Тихая деградация была бы
    # худшим исходом: потеря снова стала бы необратимой, и никто бы об этом не узнал.
    has_history = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='phoenix_history'"
    ).fetchone())

    if (args.history or args.restore) and not has_history:
        conn.close()
        sys.exit("⛔ ОТКАЗ: таблицы phoenix_history в этой базе нет — истории не существует.\n"
                 "   Прогони migrations/20260823-phoenix-history.py")

    if args.history:
        rows = conn.execute(
            "SELECT id, saved_at, body_chars, actor, reason, body FROM phoenix_history "
            "WHERE role=? AND section=? ORDER BY id DESC", (role, args.section)).fetchall()
        conn.close()
        if not rows:
            sys.exit(f"⛔ У секции {role}/{args.section} версий НЕТ.\n"
                     f"   Это значит «механизм не работал», а НЕ «секцию не правили»: "
                     f"шаг схемы сеет по одной версии каждой живой секции.")
        print(f"ВЕРСИИ {role}/{args.section} — новейшая сверху ({len(rows)} шт.)")
        for i, (vid, ts, ch, act, why, b) in enumerate(rows):
            head = next((l.strip() for l in b.splitlines() if l.strip()), "")[:64]
            print(f"  {'→' if i == 0 else ' '} id={vid:<5} {ts}  {ch:>6} знаков  "
                  f"{act:<9} {why:<20} {head}")
        print("\n  → новейшая обязана совпадать с текущим телом секции. Если не совпала —")
        print("    текст правили мимо инструмента, и это стоит разобрать, а не сгладить.")
        return

    if args.restore:
        row = conn.execute(
            "SELECT body, body_chars, saved_at FROM phoenix_history "
            "WHERE id=? AND role=? AND section=?",
            (args.restore, role, args.section)).fetchone()
        if not row:
            conn.close()
            sys.exit(f"⛔ ОТКАЗ: версии id={args.restore} у {role}/{args.section} нет.\n"
                     f"   Номер берётся из --history. Чужую версию вернуть нельзя: "
                     f"проверяются и роль, и секция.")
        body = row[0]
        # ⚖️ Возврат ПОДРАЗУМЕВАЕТ разрешение на сокращение: он сознателен по построению,
        # а возвращаемое тело само лежит в истории и никуда из неё не денется.
        args.allow_shrink = True
        print(f"↩ ВОЗВРАТ версии id={args.restore} ({row[1]} знаков, записана {row[2]} UTC)")

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
                 f"   Пустых секций не бывает: память учит преемника, а пустота учит ничему —\n"
                 f"   и при этом выглядит свежайшей, потому что проверка смотрит на ВРЕМЯ.\n"
                 f"   👉 Проверь файл: скорее всего он обнулился при записи, а не опустел по смыслу.")

    lost = (was - now) / was if was else 0.0
    share, rep = loss_report(prev_body, body) if prev_body is not None else (0.0, [])

    if was >= SHRINK_FLOOR and lost >= SHRINK_HARD and not args.allow_shrink:
        conn.close()
        sys.exit("\n".join(
            ["⛔ ОТКАЗ: секция теряет %d%% объёма (%d → %d знаков, минус %d)."
             % (round(lost * 100), was, now, was - now)]
            + rep
            + ["   Это отчёт СОДЕРЖИМЫМ, а не счётчиком: «стало меньше» не отвечает на вопрос,",
               "   ЧТО исчезло, — а спрашивают всегда именно его.",
               "   👉 Если чистка СОЗНАТЕЛЬНАЯ, скажи это словом: --allow-shrink",
               ("   👉 Прежнее тело сохранится в истории: --history (вернуть: --restore <id>)"
                if has_history else
                "   🔴 ИСТОРИИ НЕТ: таблицы phoenix_history в этой базе нет — прежнее тело "
                "не сохранится.\n"
                "      Прогони migrations/20260823-phoenix-history.py")]))

    # 🎯 МЕРА ③ ВАРИАНТА А (слово владельца 2026-08-08 16:19 UTC): сравнивается СОДЕРЖИМОЕ,
    # а не время. Если текст не изменился НИ НА ЗНАК — время сохранения НЕ ТРОГАЕМ.
    # 🪤 Иначе «нажать сохранить, ничего не изменив» выглядит свежестью: ровно так гасился
    #    проверка ⑥ (замер 07.08). Пересохранение — это ДЕЙСТВИЕ, а свежесть — СВОЙСТВО ТЕКСТА,
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

    if has_history:
        conn.execute("""
            INSERT INTO phoenix_history
                (role, section, body, body_chars, saved_at, actor, reason, prev_chars)
            VALUES (?,?,?,?,datetime('now'),?,?,?)
        """, (role, args.section, body, now, actor,
              ("restore %s" % args.restore) if args.restore
              else ("save --allow-shrink" if args.allow_shrink else "save"),
              was if prev_body is not None else None))
        # ЧИСТКА ЗДЕСЬ, А НЕ ОТДЕЛЬНЫМ ИНСТРУМЕНТОМ. Урок messages_history: чистка, которую
        # надо не забыть позвать, не делается вовсе — та таблица лежит разовым срезом с июля.
        # Правило: последние KEEP_VERSIONS версий ПЛЮС самая длинная среди сохранённых.
        # ⚖️ «Плюс самая длинная» — потому что окно по свежести ПРОГОРАЕТ: замер 23.08 даёт
        # до 15 сохранений одной секции за сутки, и десяток поспешных правок вытеснил бы
        # именно то тело, ради которого история и заводится.
        conn.execute("""
            DELETE FROM phoenix_history
             WHERE role=? AND section=?
               AND id NOT IN (SELECT id FROM phoenix_history
                               WHERE role=? AND section=? ORDER BY id DESC LIMIT ?)
               AND id <> (SELECT id FROM phoenix_history
                           WHERE role=? AND section=? ORDER BY body_chars DESC, id DESC LIMIT 1)
        """, (role, args.section, role, args.section, KEEP_VERSIONS, role, args.section))
    else:
        print("⚠️ ИСТОРИИ НЕТ: таблицы phoenix_history в этой базе нет — прежнее тело "
              "НЕ СОХРАНЕНО,\n   и эта потеря необратима. "
              "Прогони migrations/20260823-phoenix-history.py", file=sys.stderr)

    # В actor_role — ИСПОЛНИТЕЛЬ; чья секция — уже в target. Прежде оба поля несли роль,
    # и вопрос «кто это сделал» получал уверенный неверный ответ (карточка #164).
    # ⚠️ Хвост «(N chars)» СОХРАНЁН НАРОЧНО: по нему считается калибровка порога.
    # Сломать форму — обнулить единственный ряд данных, по которому порог можно перемерить.
    # Прежний размер и разрешение ДОПИСАНЫ, а не подменили её.
    diff_note = (f"Updated {args.section} ({len(body)} chars"
                 + (f", было {was}" if was else "")
                 + (f", −{round(lost * 100)}%" if now < was else "")
                 + ")"
                 + (" [--allow-shrink: сокращение разрешено словом]" if args.allow_shrink else "")
                 + ("" if has_history else " [БЕЗ ИСТОРИИ: таблицы phoenix_history нет]")
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
    # Отчёт печатается ВСЕГДА, включая «исчезло 0». Молчания здесь нет намеренно:
    # отсутствие строки было бы неотличимо от «не считали». Замер 23.08: при законной
    # работе строка тихая (0 блоков, 0–9 % строк), шумом она не станет.
    for line in rep:
        print(line)



if __name__ == "__main__":
    main()
