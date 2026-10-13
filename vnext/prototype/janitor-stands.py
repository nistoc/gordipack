# -*- coding: utf-8 -*-
"""
janitor-stands.py — убрать старые временные рабочие каталоги проверок.

ЗАЧЕМ. Проверки контура создают временные каталоги с копиями рабочей базы и не убирают
их. Помощник mezo_stand.py лечит будущие прогоны; эта утилита убирает то, что уже
накопилось, и то, что сохранено намеренно после провалов и давно осмотрено.

ПО УМОЛЧАНИЮ НИЧЕГО НЕ УДАЛЯЕТ — только показывает. Удаление включается указанием --apply.
⚠️ Удаление — НАВСЕГДА, мимо Корзины (shutil.rmtree): десятки гигабайт копий базы
Корзина не вместила бы. Поэтому --apply запускает рука человека, а не роль.
С этапа Э6 (карточка #680) стенды старше срока (MEZO_STAND_MAX_AGE_H, по умолчанию 48 ч) переносит
в Корзину сам mezo_stand.py — первый за час верхний прогон любой проверки. Эта утилита остаётся для
того, что моложе срока, и для уборки мимо Корзины рукой человека; показ называет срок автоуборки.

СПИСОК НАЧАЛ ИМЁН И РАЗМЕР СТЕНДА — ИЗ mezo_stand.py (решение В2 плана Э6, записка #5832): у
автоуборки и у этой утилиты одно правило, какой каталог наш и сколько он весит. Утилита поэтому
работает только рядом со своим mezo_stand.py — как и лежит в vnext-tools и в пакете.

⚠️ ПОРОГ ЗАДАЁТСЯ В ЧАСАХ, А НЕ В ДНЯХ, И ЭТО НЕ МЕЛОЧЬ. Замер 24.08.2026: самому старому
каталогу было 6 дней, поэтому порог «старше 7 дней» удалил бы РОВНО НОЛЬ, отчитавшись
«готово». Утилита, которая ничего не сделала, но отчиталась успехом, хуже отсутствующей:
её запускают и считают вопрос закрытым. Поэтому здесь ноль печатается словом «НОЛЬ».

НАЧАЛА ИМЁН НЕ ВПЕЧАТАНЫ — они ВЫЧИТЫВАЮТСЯ ИЗ ИСХОДНИКОВ проверок (как это уже принято
в mezo_paths.py). Появится новая проверка со своим началом имени — утилита узнает о нём
сама, без правки. Список впечатанных начал протух бы молча.
Чего вычитать нельзя — начало, которое проверка передаёт ПЕРЕМЕННОЙ (bite-milestone-step-set.py
зовёт mezo_stand.new(label) с «m509-…» и «m536-…»), и начала проверок, лежащих вне
каталогов контура (bite-target-selection.py живёт только в пакете), — называется руками:
--prefix. Замер карточки #657 (04.10.2026): таких каталогов 402, ≈13,5 ГБ, и прежняя
редакция их не видела вовсе.

ЧЕГО УТИЛИТА НЕ ТРОГАЕТ НИКОГДА:
  · каталог gordi в корне временной папки — общий корень стендов (замысел карточки #657);
    у него старая дата изменения, и первое же короткое начало имени снесло бы его вместе
    с живыми прогонами;
  · начала короче 4 знаков — такое начало подходит к чужим каталогам; утилита его
    называет и не берёт;
  · комментарии в исходниках: пример вызова в комментарии — не начало имени.
    Прежняя редакция брала из собственного комментария начало «…» (многоточие).

ПРИМЕРЫ:
    python janitor-stands.py                       # показать, что старше суток
    python janitor-stands.py --older-than-hours 6  # показать, что старше шести часов
    python janitor-stands.py --prefix m509- --prefix m536-   # плюс названные руками начала
    python janitor-stands.py --apply               # удалить то, что старше суток
    python janitor-stands.py --all --apply         # удалить всё, включая сегодняшнее
"""
import argparse
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

import mezo_stand
from mezo_stand import (MIN_PREFIX_LEN, PREFIX_RE, RESERVED_NAMES,  # noqa: F401 — прежние имена утилиты
                        code_without_comments, prefixes_from_sources, split_short)

TOOLS_DIR = Path(__file__).resolve().parent


def tool_dirs() -> list[Path]:
    """Все каталоги контура, где живут инструменты, — ПО ПРИЗНАКУ, а не одним путём (поиск — mezo_stand.tool_dirs).

    🩸 Первая редакция брала ОДИН каталог (свой) и знала 72 начала имён. Каталогов
    оказалось два: инструменты роли и инструменты согласования, и во втором лежали
    ещё 7 начал — среди них `gordi-src-`, по которому накопилось 245 каталогов
    (замер PROTO 2026-08-24 16:43 UTC, 0.31 ГБ).
    ⚖️ Указать второй можно было и руками (`--tools-dir`), но тогда полнота уборки
    держалась бы ПАМЯТЬЮ зовущего: забыл про второй каталог — утилита честно скажет
    «убрано», умолчав, что смотрела в половину мест. Ровно то, вместо чего строятся
    механизмы.
    """
    return mezo_stand.tool_dirs(TOOLS_DIR)


# прежнее имя — переходный синоним (слово владельца 07.09: имена кода по-английски при касании)
каталоги_инструментов = tool_dirs


def _force_writable(func, path, _exc):
    """Windows не даёт удалить файл, помеченный только для чтения. Снять метку и повторить."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


# Размер — тем же счётом, что у автоуборки: os.lstat, за соединения каталогов не ходит
size_of = mezo_stand.stand_size


def main() -> int:
    ap = argparse.ArgumentParser(description="убрать старые временные каталоги проверок")
    ap.add_argument("--older-than-hours", type=float, default=24.0,
                    help="порог возраста в ЧАСАХ (по умолчанию 24)")
    ap.add_argument("--all", action="store_true",
                    help="не смотреть на возраст — взять все найденные")
    ap.add_argument("--apply", action="store_true",
                    help="действительно удалить — НАВСЕГДА, мимо Корзины; без этого "
                         "указания утилита только показывает")
    ap.add_argument("--temp-dir", default=tempfile.gettempdir(),
                    help="где искать (по умолчанию — временный каталог этой машины)")
    ap.add_argument("--tools-dir", nargs="*", default=None,
                    help="откуда вычитывать начала имён. По умолчанию — ВСЕ каталоги "
                         "инструментов контура, найденные по признаку (их обычно два)")
    ap.add_argument("--prefix", action="append", default=[], metavar="НАЧАЛО",
                    help="добавить начало имени к вычитанным из исходников; можно повторять. "
                         "Для каталогов, которые проверка заводит через переменную "
                         "(m509- и m536- у bite-milestone-step-set.py), и для проверок вне "
                         "каталогов контура (bite-target-sel- у bite-target-selection.py в пакете)")
    a = ap.parse_args()

    dirs = [Path(x) for x in a.tools_dir] if a.tools_dir else tool_dirs()
    missing = [m for m in dirs if not m.is_dir()]
    if missing:
        print("⛔ НЕ ЗАПУСТИЛАСЬ: нет каталога с исходниками проверок — "
              + " · ".join(str(m) for m in missing))
        return 2
    read_prefixes, n_files = prefixes_from_sources(dirs)
    named = set(a.prefix)
    prefixes, too_short = split_short(read_prefixes | named)
    if not prefixes:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {n_files} файлах каталогов "
              + " · ".join(str(m) for m in dirs) + " не нашлось ни одного")
        print("   начала имени временного каталога. Либо каталог не тот, либо способ")
        print("   заводить каталоги сменился и образец поиска надо перепривязать —")
        print("   молча удалять по пустому списку утилита не станет.")
        if too_short:
            print("   (короткие начала не взяты: " + " · ".join(sorted(too_short)) + ")")
        return 2

    temp = Path(a.temp_dir)
    now = time.time()
    limit = a.older_than_hours * 3600

    found, aged, reserved = [], [], []
    for d in temp.iterdir() if temp.is_dir() else []:
        if not d.is_dir() or not any(d.name.startswith(p) for p in prefixes):
            continue
        if d.name.lower() in RESERVED_NAMES:
            reserved.append(d)
            continue
        try:
            age = max(0.0, now - d.stat().st_mtime)   # дата из будущего — не «-0.0 ч», а ноль
        except OSError:
            continue
        found.append(d)
        if a.all or age > limit:
            aged.append((d, age))

    threshold = "все, независимо от возраста" if a.all else f"старше {a.older_than_hours:g} ч"
    print("=" * 78)
    print("СТАРЫЕ ВРЕМЕННЫЕ КАТАЛОГИ ПРОВЕРОК")
    print(f"  где ищу ............ {temp}")
    # ⚠️ Перечисляем ВСЕ каталоги, а не первый: строка «вычитаны из … в vnext-tools»
    #    при двух просмотренных каталогах — надпись, которая у́же дела. Читающий решит,
    #    что вторая половина не смотрена, и пойдёт звать утилиту второй раз.
    print(f"  начал имён ......... {len(prefixes)} (вычитаны из {n_files} файлов)")
    for m in dirs:
        print(f"     · {m}")
    if named:
        print("  названо руками ..... " + " · ".join(sorted(named)))
    if too_short:
        print(f"  НЕ взяты (короче {MIN_PREFIX_LEN} знаков, подошли бы к чужим каталогам): "
              + " · ".join(sorted(too_short)))
    print(f"  порог .............. {threshold}")
    auto = mezo_stand.max_age_hours()
    print("  автоуборка ......... " + (
        f"старше {auto:g} ч переносит в Корзину сам mezo_stand.py, не чаще раза в час "
        f"({mezo_stand.MAX_AGE_ENV})" if auto is not None else
        f"выключена ({mezo_stand.MAX_AGE_ENV}={os.environ.get(mezo_stand.MAX_AGE_ENV, '')!r})"))
    print("=" * 78)
    for d in reserved:
        print(f"🔒 не трогаю {d.name}: общий корень стендов, утилита его не берёт ни при каком начале")

    if not found:
        print("НОЛЬ — временных каталогов проверок не найдено вовсе. Убирать нечего.")
        return 0

    sizes = {d: size_of(d) for d, _ in aged}
    gb = sum(sizes.values()) / 1024 ** 3
    print(f"найдено всего: {len(found)} · под порог подпадает: "
          + (f"{len(aged)} ({gb:.2f} ГБ)" if aged else "НОЛЬ"))

    if not aged:
        youngest = max(0.0, min(now - d.stat().st_mtime for d in found)) / 3600
        print(f"⚠️ Ни один каталог не старше порога. Самому молодому {youngest:.1f} ч,")
        print("   самому старому " +
              f"{max(0.0, max(now - d.stat().st_mtime for d in found)) / 3600:.1f} ч. "
              "Понизьте порог или укажите --all.")
        return 0

    for d, age in sorted(aged, key=lambda x: -x[1])[:10]:
        print(f"   {age / 3600:7.1f} ч  {d.name}")
    if len(aged) > 10:
        print(f"   … и ещё {len(aged) - 10}")

    if not a.apply:
        print(f"\n👀 ПОКАЗ, НЕ УДАЛЕНИЕ. Удалит {len(aged)} каталогов и освободит {gb:.2f} ГБ.")
        print("   Чтобы удалить — добавьте --apply. Удаление НАВСЕГДА, мимо Корзины.")
        return 0

    removed = failed = 0
    freed = 0  # только удалённые целиком: у неудалённого часть файлов могла остаться
    for d, _ in aged:
        try:
            shutil.rmtree(d, onerror=_force_writable)
            removed += 1
            freed += sizes[d]
        except OSError as e:
            failed += 1
            print(f"⚠️ не удалось убрать {d}: {e}")
    print(f"\n🧹 УДАЛЕНО: {removed if removed else 'НОЛЬ'} каталогов · "
          f"освобождено {freed / 1024 ** 3:.2f} ГБ"
          + (f" · НЕ УДАЛОСЬ: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
