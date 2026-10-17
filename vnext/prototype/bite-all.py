#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ОДНА КОМАНДА НА ВСЕ ПРИЁМКИ: зовёт каждый bite-*.py рядом с собой и печатает таблицу.

Зачем. Приёмка, которую надо вспомнить и позвать поимённо, не зовётся. Замер контура:
ручка `--task` существовала всегда и не была позвана НИ РАЗУ за 1724 записки. У постоянных
проверок такой запускатель есть (`guard-all.py`), у приёмок не было — и потому в паке
пролежала СТАРАЯ редакция одной из них, красневшая на верном коде, пока её не сверили руками.

⚖️ ТРИ ИСХОДА, А НЕ ДВА — и это главное свойство этой программы.
  ✅ зелёный ...... свойство держится
  🔴 красный ...... свойство сломано
  ⚠️ НЕ ЗАПУСТИЛАСЬ  приёмке нужен контур/база/аргументы, которых здесь нет
«Не запустилась» НЕ ЕСТЬ «зелёная». Сваливать их вместе — значит печатать «всё чисто» там,
где не проверено ничего: это ложный ноль, самый дорогой сорт вранья механизма.

⛔ Живую базу приёмки открывают сами и по своим правилам; эта программа только зовёт их.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

HERE = os.path.dirname(os.path.abspath(__file__))

# ═══ ВЫБОР ИСПЫТУЕМОЙ КОПИИ (карточка #146) ═══
# 🪤 ПОВОД. Приёмки испытывали ЖИВЫЕ механизмы, а зелёный прогон читался как «шаблон цел».
# Рычаг у приёмок был (mezo_target + переменные среды), но набор про него НЕ ЗНАЛ: прогон
# «по шаблону» набирался рукой, то есть существовал как намерение, а не как механизм.
# ⚖️ Умолчание — ЖИВОЙ контур: тот, кто просто позвал набор, получает привычное поведение.
LIVE_SCRIPTS = str(mezo_paths.live_scripts())
TEMPLATE_SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "scripts"))


def resolve_target(word: str) -> str:
    return {"live": LIVE_SCRIPTS, "template": TEMPLATE_SCRIPTS}.get(word, word)


def env_for(target: str, laid_out: bool = False) -> dict:
    """Окружение прогона. ⛔ Для НЕ-живой копии ставится запрет молчаливого займа:
    без него приёмка, не нашедшая файл в шаблоне, тихо возьмёт его из живого — и прогон
    «по шаблону» на деле проверит оригинал (ровно дефект, ради которого всё заведено).
    laid_out — копию разложил контуром сам набор (lay_out_contour): MEZO_CONTAINER вызывающего
    снимается, контур испытуемые находят по признаку, как на живом."""
    env = dict(os.environ)
    env["MEZO_SCRIPTS_ROOT"] = target
    if os.path.normcase(os.path.abspath(target)) != os.path.normcase(os.path.abspath(LIVE_SCRIPTS)):
        env["MEZO_FORBID_LIVE"] = "1"
    else:
        env.pop("MEZO_FORBID_LIVE", None)
    if laid_out:
        # Урок 13.09 (mezo_paths.mezo_root): копия с MEZO_CONTAINER живого записала meta Atlas.
        # Среда стоит ПЕРВОЙ в container_root — унаследованная увела бы испытуемых мимо стенда.
        env.pop("MEZO_CONTAINER", None)
    return env


# ═══ КОПИЯ БЕЗ СВОЕГО КОНТУРА (находка PROTO, записка #5838; карточка #680) ═══
# 🪤 ПОВОД. Прогон «--target template» по клону пакета 12.10 17:19–17:49 UTC: держится 170 · сломано 23 ·
# не проверено 6 из 199, и у тех же 29 приёмок исход тот же на прежнем коде. Скрипты клона лежат
# в <клон>/scripts, а не в <контейнер>/.mezosync/scripts рядом с базой: испытуемые не находят контур
# («контейнер группы НЕ НАЙДЕН»), а приёмки, берущие базу рядом с испытуемыми (<скрипты>/../mezosync.db),
# брали пустой файл корня клона. Набор красил это «СЛОМАНО» — не поломки, а нечем мерить.
# ⇒ Копию без своего контура набор раскладывает контуром сам, во временном каталоге:
#     <стенд>/.mezosync/scripts ......... копия испытуемых (байт в байт, без __pycache__)
#     <стенд>/.mezosync/mezosync.db ..... согласованная копия живой базы (резервное копирование sqlite3)
#     <стенд>/.mezosync/local/paths.json  файл путей живого БЕЗ ключа container
# Живой контур не трогается: испытуемые находят стенд по признаку .mezosync/mezosync.db и пишут в копию.
# ⚖️ Испытуется по-прежнему код копии — подпись называет и копию, и стенд.


def own_contour(target: str) -> bool:
    """Лежит ли испытуемый каталог контуром: <контейнер>/.mezosync/scripts рядом с НЕпустой базой."""
    parent = os.path.dirname(os.path.abspath(target))
    db = os.path.join(parent, "mezosync.db")
    return os.path.basename(parent) == ".mezosync" and os.path.isfile(db) and os.path.getsize(db) > 0


def lay_out_contour(target: str):
    """Разложить копию испытуемых контуром во временном каталоге. (стенд, его скрипты, что сделано)."""
    import json
    import shutil
    import mezo_stand  # согласованная копия базы (карточка #505)
    stand = tempfile.mkdtemp(prefix="bite-all-contour-")
    mz = os.path.join(stand, ".mezosync")
    scripts = os.path.join(mz, "scripts")
    shutil.copytree(target, scripts, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    live_db = mezo_paths.live_db()
    mezo_stand.snapshot_db(live_db, os.path.join(mz, "mezosync.db"))
    words = [f"скрипты — копия {target}", f"база — копия {live_db}"]
    # 🪤 17.10 (разбор провала bite-shift-end.py под раскладкой): save-phoenix.py и соседи ищут
    # проверки (guard-shift-end.py, guard-phoenix-volume.py, memory-records.py) относительно СВОЕГО
    # файла — vnext_tool(), четыре места. В клоне их находит <клон>/vnext/prototype; перенесённые
    # в <стенд>/.mezosync/scripts скрипты соседей теряли, и шесть случаев падали «файла нет».
    # ⇒ Соседей копии кладём туда же, где их ищет четвёртое место: <стенд>/vnext/prototype.
    # local.paths не берём: старый файл путей увёл бы испытуемых в живой контур.
    proto = os.path.join(os.path.dirname(os.path.abspath(target)), "vnext", "prototype")
    if os.path.isdir(proto):
        shutil.copytree(proto, os.path.join(stand, "vnext", "prototype"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "local.paths"))
        words.append(f"соседние проверки — копия {proto}")
    paths_file = mezo_paths.local_dir(live_db) / "paths.json"
    if paths_file.is_file():
        data = json.loads(paths_file.read_text(encoding="utf-8-sig"))
        data.pop("container", None)
        os.makedirs(os.path.join(mz, "local"))
        with open(os.path.join(mz, "local", "paths.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        words.append(f"файл путей — {paths_file.as_posix()} без ключа container")
    return stand, scripts, words
# Приметы того, что приёмка не сломана, а не смогла начаться. Ищем в выводе.
CANT_START = (
    "no such file", "не найден", "unable to open database", "no such table",
    "usage:", "the following arguments are required", "modulenotfounderror",
    "нет базы", "не найдена база", "can't open file",
)
# 🪤 ПРИМЕТА ЦЕЛЫМ СЛОВОМ (возврат карточки #659 по ①, находка COORD 26.09, записка #5398).
# Подстрока «не найден» совпадала с «не найдено (ждали …)» — обычной строкой СЛУЧАЯ приёмки
# поиска по памяти, — и настоящий провал с кодом 1 печатался как «не запустилась»: живой
# итог по сути был «сломано 2», а читался «сломано 1». ⇒ За приметой не может идти буква.
CANT_START_RE = re.compile(
    "|".join(re.escape(m) + r"(?![a-zа-яё])" for m in CANT_START), re.IGNORECASE)
# 🪤 ВТОРОЙ ВОЗВРАТ (находка COORD 26.09 21:28 UTC, записка #5403): и целым словом примета
# стоит в тексте СЛУЧАЯ — «ответ снова не найден» у bite-bridge-own-letters.py, — и провал
# её случая ⑤ на новом контуре печатался «не запустилась». Замер на выводах провалов свежего
# контура: из 7 «не запустилась» у 6 были напечатанные случаи. ⇒ Примета судит только вывод,
# где приёмка НЕ напечатала ни одного своего случая (строка, начатая ✅ или 🔴): напечатала —
# значит, запустилась и мерила, и код 1 — провал, а не незапуск.
CASE_LINE_RE = re.compile(r"^\s*(?:✅|🔴)\s", re.MULTILINE)


def exercised(where: str, names) -> set:
    """Какие МЕХАНИЗМЫ набор реально испытывает — ЗАМЕРОМ по коду приёмок, не списком.

    🪤 ПОВОД, найденный при первой же нарочной поломке (09.08 20:00 UTC). Я сломал в копии
    `set-rule.py` и получил «держится 36, сломано 0» — прогон по копии выглядел зелёным
    при полностью убитом механизме. Причина не в наборе: этот механизм не испытывает
    НИКТО. Через резолвер зовутся четыре из сорока пяти.
    🎯 ⇒ Зелёный прогон «по образцу» без этой строки читается как «образец цел», а значит
    ровно то, чего мы избегаем: ложный ноль. Граница набора обязана печататься рядом с числом.
    """
    import re
    pat = re.compile(r'script\(\s*["\']([a-z0-9_.-]+\.py)["\']', re.I)
    found = set()
    for n in names:
        try:
            found |= set(pat.findall(
                open(os.path.join(where, n), encoding="utf-8", errors="replace").read()))
        except OSError:
            pass
    return found


def bites(where: str, only: str):
    names = sorted(f for f in os.listdir(where)
                   if f.startswith("bite-") and f.endswith(".py") and f != os.path.basename(__file__))
    return [n for n in names if not only or only in n]


def verdict(code: int, out: str):
    low = out.lower()
    # Код 2 — ОТКАЗ МЕРИТЬ (дисциплина трёх исходов): «испытуемого нет» не есть «сломано».
    # Поймано 09.08 20:10: приёмка честно сказала «испытуемого нет» кодом 2, а набор
    # покрасил её «СЛОМАНО» — то есть перевёл отказ мерить в приговор механизму.
    if code == 2:
        return "⚠️", "не запустилась (отказ мерить, код 2)"
    if code != 0 and CANT_START_RE.search(low) and not CASE_LINE_RE.search(out):
        return "⚠️", "не запустилась"
    return ("✅", "свойство держится") if code == 0 else ("🔴", "СЛОМАНО")


def main() -> int:
    ap = argparse.ArgumentParser(description="прогнать все приёмки рядом с этим файлом")
    ap.add_argument("--only", default="", help="подстрока имени: прогнать лишь совпавшие")
    ap.add_argument("--timeout", type=int, default=300, help="потолок на одну приёмку, сек")
    ap.add_argument("--verbose", action="store_true", help="печатать вывод каждой приёмки целиком")
    ap.add_argument("--dir", default=HERE,
                    help="каталог с приёмками (по умолчанию — рядом с этим файлом). "
                         "Нужен, чтобы САМ запускатель можно было проверить на подложенных случаях")
    ap.add_argument("--target", default="live", metavar="live|template|ПУТЬ",
                    help="какую копию МЕХАНИЗМОВ испытывать (по умолчанию живой контур). "
                         "Для не-живой копии автоматически запрещается заём из живого")
    args = ap.parse_args()

    where = os.path.abspath(args.dir)
    target = resolve_target(args.target)
    names = bites(where, args.only)
    if not names:
        print("⛔ приёмок не найдено — проверь каталог и --only")
        return 1
    if not os.path.isdir(target):
        # ⚖️ Отсутствие испытуемой копии — ОТКАЗ МЕРИТЬ, а не «сломано» и не «чисто».
        print(f"⛔ НЕ ЗАПУСТИЛСЯ НАБОР: испытуемого каталога нет — {target}\n"
              "   Проверять нечего. Это НЕ «всё зелено».")
        return 2

    live = os.path.normcase(os.path.abspath(target)) == os.path.normcase(
        os.path.abspath(LIVE_SCRIPTS))
    # 🎯 Подпись СПРАШИВАЕТ, что испытано, и печатается ДО прогона и ПОСЛЕ него.
    #    Зашитая строка «испытан живой модуль» уже однажды соврала при работе по шаблону.
    banner = f"{'⚡ ЖИВОЙ КОНТУР' if live else '📦 КОПИЯ'}: {target}"
    stand, laid = None, []
    if not live and not own_contour(target):
        try:
            stand, target, laid = lay_out_contour(target)
        except Exception as e:  # noqa: BLE001 — нечем мерить: отказ, а не «сломано» у каждой приёмки
            print(f"⛔ НЕ ЗАПУСТИЛСЯ НАБОР: копию {target} не удалось разложить контуром — "
                  f"{type(e).__name__}: {e}\n   Проверять нечего. Это НЕ «всё зелено».")
            return 2
    print("=" * 78)
    print(f"ПРИЁМКИ: {len(names)} шт. в {where}")
    print(f"ИСПЫТУЕМЫЕ МЕХАНИЗМЫ — {banner}")
    if stand:
        print(f"🧱 копия не лежит контуром — разложена во временном каталоге {stand}:")
        for w in laid:
            print(f"   · {w}")
    if not live:
        print("⛔ заём из живого контура ЗАПРЕЩЁН на этот прогон (MEZO_FORBID_LIVE=1)")
    print("=" * 78)

    green = red = stuck = 0
    for name in names:
        try:
            r = subprocess.run([sys.executable, os.path.join(where, name)],
                               capture_output=True, text=True, encoding="utf-8",
                               timeout=args.timeout, env=env_for(target, laid_out=bool(stand)))
            out, code = (r.stdout or "") + (r.stderr or ""), r.returncode
        except subprocess.TimeoutExpired:
            out, code = f"потолок {args.timeout} с исчерпан", 1
            print(f"⚠️  {name:32} не запустилась — потолок времени")
            stuck += 1
            continue

        mark, word = verdict(code, out)
        print(f"{mark}  {name:32} {word}")
        if args.verbose or mark == "🔴":
            tail = [l for l in out.strip().splitlines() if l.strip()][-6:]
            for line in tail:
                print(f"        {line}")
        # 🪤 ПОЛНЫЙ ВЫВОД УПАВШЕЙ ПРИЁМКИ СОХРАНЯЕТСЯ, А НЕ ОБРЕЗАЕТСЯ ДО ХВОСТА.
        # Повод — карточка #150, замер 2026-08-09: общий набор даёт редкий отказ (1 из 7
        # прогонов) на НЕИЗМЕННОМ коде, а в одиночку тот же укус зелёный 8 из 8.
        # Хвоста в шесть строк хватает, чтобы УВИДЕТЬ отказ, и не хватает, чтобы РАЗОБРАТЬ:
        # какое из свойств не выполнилось, видно только в теле вывода.
        # ⇒ Редкое событие нельзя ловить руками: к моменту, когда оно случится, окно
        #   вывода уже уедет. Механизм обязан его ЗАПОМНИТЬ — иначе разбор стоит ожидания.
        if mark in ("🔴", "⚠️"):
            try:
                fail_dir = os.path.join(tempfile.gettempdir(), "bite-all-failures")
                os.makedirs(fail_dir, exist_ok=True)
                stamp = str(int(time.time()))
                path = os.path.join(fail_dir, f"{name}.{stamp}.txt")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(out)
                print(f"        📄 полный вывод сохранён: {path}")
            except OSError as e:
                # ⚖️ Отказ сохранения НЕ роняет прогон и НЕ молчит: молчащая страховка
                #    неотличима от сработавшей.
                print(f"        ⚠️ вывод сохранить не удалось: {e}")
        green += mark == "✅"
        red += mark == "🔴"
        stuck += mark == "⚠️"

    print("-" * 78)
    print(f"держится {green} · сломано {red} · НЕ ПРОВЕРЕНО {stuck}")
    # 🎯 Итог повторяет, ЧТО испытано. Числа без этой строки читаются как «всё цело»
    #    независимо от того, какую копию гоняли, — а копии дают разные числа (замер 09.08).
    print(f"ИСПЫТАНО — {banner}")
    if not live:
        touched = sorted(exercised(where, names))
        total = len([f for f in os.listdir(target) if f.endswith(".py")])
        print(f"⚖️ ГРАНИЦА НАБОРА: испытано механизмов {len(touched)} из {total} в копии — "
              f"{', '.join(touched) if touched else 'НИ ОДНОГО'}")
        print("   Остальные копия содержит, но НИКТО их не зовёт: сломай их — прогон "
              "останется зелёным (доказано поломкой 09.08).")
        print("⚖️ И про живой контур этот прогон не говорит ничего.")
    if stuck:
        print("⚠️  «не проверено» — это НЕ «в порядке». Пока такие есть, «всё чисто» сказать нельзя.")
    if stand:
        if red or stuck:
            print(f"📂 контур копии сохранён для осмотра: {stand} — уберёт срок хранения стендов")
        else:
            import shutil
            shutil.rmtree(stand, ignore_errors=True)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
