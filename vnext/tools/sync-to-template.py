#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПЕРЕНОС ЖИВЫХ МЕХАНИЗМОВ В ШАБЛОН — И СТОРОЖ ТОЙ ЖЕ ПАРЫ.

🪤 ПОВОД (замер 2026-08-08 22:39 UTC). У пары `vnext-tools ↔ vnext/prototype` сторож дрейфа
ЕСТЬ, и она сходилась файл в файл. У пары `.mezosync/scripts ↔ scripts/` сторожа НЕ БЫЛО —
и она разошлась так, что `write-message.py` в шаблоне оказался В 26 РАЗ меньше живого
(1 830 байт против 48 483). Никто не заметил: **молчание неотличимо от правоты.**

⚖️ ПОЧЕМУ ПЕРЕНОС И СТОРОЖ — ОДИН ФАЙЛ, А НЕ ДВА.
Копии нельзя сравнивать побайтно: в шаблоне путь контура обязан быть ОБЩИМ (`<КОНТУР>`),
а в живом — конкретным, иначе роли скопируют чужой путь. Значит сравнение идёт ПОСЛЕ
приведения. Живи приведение в переносе, а сравнение — отдельно, они разошлись бы первыми,
и сторож стал бы вечно-красным (то есть его перестали бы читать).
⇒ Приведение описано ОДИН раз, ниже. Им пользуются оба режима.

    python vnext/tools/sync-to-template.py            замер: что разошлось
    python vnext/tools/sync-to-template.py --apply    перенести

⛔ Шаблон ПУБЛИЧЕН: имена коллег сюда не едут, только обозначения ролей. Приведение
   вырезает путь контейнера — единственное, что привязывает файл к машине владельца.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

LIVE = Path(r"C:\guts\.atlas\.mezosync\scripts")
TEMPLATE = Path(__file__).resolve().parents[2] / "scripts"

# Механизмы, которых в шаблоне не было ВОВСЕ (замер 08.08): контур, собранный из шаблона,
# не получал ни одного из них и выглядел при этом исправным.
NEW = ["machine_layer.py", "urgency.py", "schema_journal.py", "sync_backoff.py",
       "role-rights.py"]
# Общие скрипты, разошедшиеся молча.
SHARED = ["write-message.py", "read-messages.py", "set-rule.py", "save-phoenix.py",
          "read-phoenix.py", "backlog.py", "guard-all.py"]

# Путь контейнера в примерах вызова → общий вид. В РАБОЧЕМ выводе путь берётся из
# Path(__file__) и приведения не требует: правится только текст для человека.
CONTAINER = re.compile(r"C:[\\/]guts[\\/]\.atlas[\\/]\.mezosync[\\/]scripts")


IMPORT = re.compile(r"^\s*(?:import|from)\s+([a-z_][a-z0-9_]*)", re.M)


def with_deps(names, live: Path):
    """Список + ВСЁ, что он импортирует из соседних файлов, рекурсивно.

    🪤 Класс, пойманный на первой же сборке 2026-08-08: перенос выглядел полным (12 файлов,
    повторный замер зелёный), а на СВЕЖЕМ контуре `write-message.py` не запустился —
    не хватило `mezo_paths.py`, которого не было в списке. Список писала рука, а зависимости
    знает только код.
    ⇒ Список — это НАЧАЛО, а не ответ. Замыкание считает механизм.
    ⚖️ И это ровно тот третий исход: «не запустилась» — не «сломано» и НЕ «зелено».
    """
    seen, queue = set(), list(names)
    while queue:
        n = queue.pop()
        if n in seen:
            continue
        seen.add(n)
        f = live / n
        if not f.exists():
            continue
        for mod in set(IMPORT.findall(f.read_text(encoding="utf-8"))):
            cand = f"{mod}.py"
            if (live / cand).exists() and cand not in seen:
                queue.append(cand)
    return sorted(seen)


def sanitize(text: str) -> str:
    """Единственное место, где описано отличие копии шаблона от живой копии."""
    return CONTAINER.sub("<КОНТУР>/.mezosync/scripts", text)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description="перенос живых механизмов в шаблон + сторож пары")
    ap.add_argument("--apply", action="store_true", help="ПЕРЕНЕСТИ. Без него — только замер")
    a = ap.parse_args()

    if not LIVE.exists():
        print(f"⚠️ живого каталога нет: {LIVE}")
        print("   Это НЕ «всё сведено» — это «сверять не с чем». В чужом контуре так и будет:")
        print("   сторож пары имеет смысл только там, где живой контур рядом с шаблоном.")
        return 0

    missing, differ, same = [], [], []
    plan = with_deps(NEW + SHARED, LIVE)
    # ⚡ ШАГИ СХЕМЫ (migrations/) — тоже механизм, а не архив. Замер 2026-08-09: в шаблоне
    # каталога не было ВОВСЕ при семи шагах в живом. Собранный контур это переживал (конечная
    # схема лежит в schema/), а вот приёмка прав — нет: она читает описание таблицы из файла
    # шага рядом со скриптом и, идя по шаблону, МОЛЧА брала его из живого контура.
    plan += sorted(f"migrations/{p.name}" for p in (LIVE / "migrations").glob("*.py"))
    extra = [n for n in plan if n not in NEW + SHARED]
    if extra:
        print(f"📎 добавлено по зависимостям (список их не знал): {' · '.join(extra)}")
    for name in plan:
        src = LIVE / name
        dst = TEMPLATE / name
        if not src.exists():
            print(f"⚠️ в живом контуре нет {name} — пропускаю (это не «сведено»)")
            continue
        want = sanitize(src.read_text(encoding="utf-8"))
        if not dst.exists():
            missing.append((name, want, dst))
        elif digest(dst.read_text(encoding="utf-8")) != digest(want):
            differ.append((name, want, dst, len(dst.read_text(encoding='utf-8')), len(want)))
        else:
            same.append(name)

    print("=" * 78)
    print("ЖИВЫЕ СКРИПТЫ ↔ ШАБЛОН")
    print("=" * 78)
    print(f"✅ совпадают ......... {len(same)}")
    if missing:
        print(f"🔴 НЕТ В ШАБЛОНЕ ..... {len(missing)}  — контур из шаблона их не получит")
        for n, _, _ in missing:
            print(f"     {n}")
    if differ:
        print(f"🔴 РАЗОШЛИСЬ ......... {len(differ)}")
        for n, _, _, was, now in differ:
            print(f"     {n:22} шаблон {was} б → живой {now} б")
    if not missing and not differ:
        print("\n✅ СВЕДЕНО. Пара сходится после приведения путей.")
        return 0

    if not a.apply:
        print("\n🔍 ЗАМЕР, ШАБЛОН НЕ ТРОНУТ. Перенести — тем же вызовом с --apply.")
        return 1

    TEMPLATE.mkdir(parents=True, exist_ok=True)
    for n, want, dst, *_ in [(m[0], m[1], m[2]) for m in missing] + \
                            [(d[0], d[1], d[2]) for d in differ]:
        dst.parent.mkdir(parents=True, exist_ok=True)   # у шагов схемы свой подкаталог
        dst.write_text(want, encoding="utf-8", newline="\n")
        print(f"  ✅ {n}")
    print(f"\n✅ Перенесено: {len(missing) + len(differ)}. Дальше: собрать СВЕЖИЙ контур "
          "и прогнать приёмки НА НЁМ — приёмка на своей копии не доказывает ничего про чужую.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
