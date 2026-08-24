# -*- coding: utf-8 -*-
"""
janitor-stands.py — убрать старые временные рабочие каталоги проверок.

ЗАЧЕМ. Проверки контура создают временные каталоги с копиями рабочей базы и не убирают
их. Помощник mezo_stand.py лечит будущие прогоны; эта утилита убирает то, что уже
накопилось, и то, что сохранено намеренно после провалов и давно осмотрено.

ПО УМОЛЧАНИЮ НИЧЕГО НЕ УДАЛЯЕТ — только показывает. Удаление включается указанием --apply.

⚠️ ПОРОГ ЗАДАЁТСЯ В ЧАСАХ, А НЕ В ДНЯХ, И ЭТО НЕ МЕЛОЧЬ. Замер 24.08.2026: самому старому
каталогу было 6 дней, поэтому порог «старше 7 дней» удалил бы РОВНО НОЛЬ, отчитавшись
«готово». Утилита, которая ничего не сделала, но отчиталась успехом, хуже отсутствующей:
её запускают и считают вопрос закрытым. Поэтому здесь ноль печатается словом «НОЛЬ».

НАЧАЛА ИМЁН НЕ ВПЕЧАТАНЫ — они ВЫЧИТЫВАЮТСЯ ИЗ ИСХОДНИКОВ проверок (как это уже принято
в mezo_paths.py). Появится новая проверка со своим началом имени — утилита узнает о нём
сама, без правки. Список впечатанных начал протух бы молча.

ПРИМЕРЫ:
    python janitor-stands.py                       # показать, что старше суток
    python janitor-stands.py --older-than-hours 6  # показать, что старше шести часов
    python janitor-stands.py --apply               # удалить то, что старше суток
    python janitor-stands.py --all --apply         # удалить всё, включая сегодняшнее
"""
import argparse
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
# tempfile.mkdtemp(prefix="…") и mezo_stand.new("…") — оба способа завести каталог
PREFIX_RE = re.compile(r'(?:mkdtemp\s*\(\s*prefix\s*=|mezo_stand\.new\s*\(\s*)["\']([^"\']+)["\']')


def каталоги_инструментов() -> list[Path]:
    """Все каталоги контура, где живут инструменты, — ПО ПРИЗНАКУ, а не одним путём.

    🩸 Первая редакция брала ОДИН каталог (свой) и знала 72 начала имён. Каталогов
    оказалось два: инструменты роли и инструменты согласования, и во втором лежали
    ещё 7 начал — среди них `gordi-src-`, по которому накопилось 245 каталогов
    (замер PROTO 2026-08-24 16:43 UTC, 0.31 ГБ).
    ⚖️ Указать второй можно было и руками (`--tools-dir`), но тогда полнота уборки
    держалась бы ПАМЯТЬЮ зовущего: забыл про второй каталог — утилита честно скажет
    «убрано», умолчав, что смотрела в половину мест. Ровно то, вместо чего строятся
    механизмы.
    """
    свой = TOOLS_DIR
    места = [свой]
    корень = свой.parent
    for кандидат in (корень / ".mezosync" / "scripts", корень.parent / ".mezosync" / "scripts",
                     свой.parent / "scripts"):
        if кандидат.is_dir() and кандидат.resolve() != свой.resolve():
            места.append(кандидат)
    # + инструменты соседних репозиториев контура, если контур так разложен
    try:
        for d in sorted(корень.iterdir()):
            к = d / ".mezosync" / "scripts"
            if к.is_dir() and all(к.resolve() != m.resolve() for m in места):
                места.append(к)
    except OSError:
        pass
    return места


def prefixes_from_sources(tools_dirs) -> tuple[set[str], int]:
    """Собрать начала имён из исходников проверок. Возвращает (начала, сколько файлов прочитано)."""
    if isinstance(tools_dirs, Path):
        tools_dirs = [tools_dirs]
    found, read = set(), 0
    for каталог in tools_dirs:
        for f in sorted(Path(каталог).glob("*.py")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            read += 1
            found.update(PREFIX_RE.findall(text))
    return found, read


def _force_writable(func, path, _exc):
    """Windows не даёт удалить файл, помеченный только для чтения. Снять метку и повторить."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def size_of(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda _e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="убрать старые временные каталоги проверок")
    ap.add_argument("--older-than-hours", type=float, default=24.0,
                    help="порог возраста в ЧАСАХ (по умолчанию 24)")
    ap.add_argument("--all", action="store_true",
                    help="не смотреть на возраст — взять все найденные")
    ap.add_argument("--apply", action="store_true",
                    help="действительно удалить; без этого указания утилита только показывает")
    ap.add_argument("--temp-dir", default=tempfile.gettempdir(),
                    help="где искать (по умолчанию — временный каталог этой машины)")
    ap.add_argument("--tools-dir", nargs="*", default=None,
                    help="откуда вычитывать начала имён. По умолчанию — ВСЕ каталоги "
                         "инструментов контура, найденные по признаку (их обычно два)")
    a = ap.parse_args()

    места = [Path(x) for x in a.tools_dir] if a.tools_dir else каталоги_инструментов()
    нет = [м for м in места if not м.is_dir()]
    if нет:
        print("⛔ НЕ ЗАПУСТИЛАСЬ: нет каталога с исходниками проверок — "
              + " · ".join(str(м) for м in нет))
        return 2
    tools = места[0]
    prefixes, n_files = prefixes_from_sources(места)
    if not prefixes:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {n_files} файлах каталогов "
              + " · ".join(str(м) for м in места) + " не нашлось ни одного")
        print("   начала имени временного каталога. Либо каталог не тот, либо способ")
        print("   заводить каталоги сменился и образец поиска надо перепривязать —")
        print("   молча удалять по пустому списку утилита не станет.")
        return 2

    temp = Path(a.temp_dir)
    now = time.time()
    limit = a.older_than_hours * 3600

    found, aged = [], []
    for d in temp.iterdir() if temp.is_dir() else []:
        if not d.is_dir() or not any(d.name.startswith(p) for p in prefixes):
            continue
        try:
            age = now - d.stat().st_mtime
        except OSError:
            continue
        found.append(d)
        if a.all or age > limit:
            aged.append((d, age))

    порог = "все, независимо от возраста" if a.all else f"старше {a.older_than_hours:g} ч"
    print("=" * 78)
    print("СТАРЫЕ ВРЕМЕННЫЕ КАТАЛОГИ ПРОВЕРОК")
    print(f"  где ищу ............ {temp}")
    # ⚠️ Перечисляем ВСЕ каталоги, а не первый: строка «вычитаны из … в vnext-tools»
    #    при двух просмотренных каталогах — надпись, которая у́же дела. Читающий решит,
    #    что вторая половина не смотрена, и пойдёт звать утилиту второй раз.
    print(f"  начал имён ......... {len(prefixes)} (вычитаны из {n_files} файлов)")
    for м in места:
        print(f"     · {м}")
    print(f"  порог .............. {порог}")
    print("=" * 78)

    if not found:
        print("НОЛЬ — временных каталогов проверок не найдено вовсе. Убирать нечего.")
        return 0

    total_bytes = sum(size_of(d) for d, _ in aged)
    гб = total_bytes / 1024 ** 3
    print(f"найдено всего: {len(found)} · под порог подпадает: "
          + (f"{len(aged)} ({гб:.2f} ГБ)" if aged else "НОЛЬ"))

    if not aged:
        youngest = min(now - d.stat().st_mtime for d in found) / 3600
        print(f"⚠️ Ни один каталог не старше порога. Самому молодому {youngest:.1f} ч,")
        print("   самому старому " +
              f"{max(now - d.stat().st_mtime for d in found) / 3600:.1f} ч. "
              "Понизьте порог или укажите --all.")
        return 0

    for d, age in sorted(aged, key=lambda x: -x[1])[:10]:
        print(f"   {age / 3600:7.1f} ч  {d.name}")
    if len(aged) > 10:
        print(f"   … и ещё {len(aged) - 10}")

    if not a.apply:
        print(f"\n👀 ПОКАЗ, НЕ УДАЛЕНИЕ. Удалит {len(aged)} каталогов и освободит {гб:.2f} ГБ.")
        print("   Чтобы удалить — добавьте --apply.")
        return 0

    removed = failed = 0
    for d, _ in aged:
        try:
            shutil.rmtree(d, onerror=_force_writable)
            removed += 1
        except OSError as e:
            failed += 1
            print(f"⚠️ не удалось убрать {d}: {e}")
    print(f"\n🧹 УДАЛЕНО: {removed if removed else 'НОЛЬ'} каталогов · "
          f"освобождено {гб:.2f} ГБ"
          + (f" · НЕ УДАЛОСЬ: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
