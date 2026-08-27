#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПЕРЕНОС ЖИВЫХ МЕХАНИЗМОВ В ШАБЛОН — И СТОРОЖ ТОЙ ЖЕ ПАРЫ.

🪤 ПОВОД (замер 2026-08-08 22:39 UTC). У пары `vnext-tools ↔ vnext/prototype` проверка дрейфа
ЕСТЬ, и она сходилась файл в файл. У пары `.mezosync/scripts ↔ scripts/` сторожа НЕ БЫЛО —
и она разошлась так, что `write-message.py` в шаблоне оказался В 26 РАЗ меньше живого
(1 830 байт против 48 483). Никто не заметил: **молчание неотличимо от правоты.**

⚖️ ПОЧЕМУ ПЕРЕНОС И ПРОВЕРКА — ОДИН ФАЙЛ, А НЕ ДВА.
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
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent / "prototype"))
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_scripts()
TEMPLATE = Path(__file__).resolve().parents[2] / "scripts"

# ⚰️ ЗДЕСЬ СТОЯЛИ ДВА РУКОПИСНЫХ СПИСКА — NEW и SHARED. Сняты 10.08 01:28 UTC (#145+).
# 🎯 ПОВОД НАЗВАЛ @COORD В ТОТ ЖЕ ДЕНЬ, И ЭТО ЛУЧШАЯ ФОРМУЛИРОВКА КЛАССА: механизм был
# взят в тулкит, врезан и проверен — и ОСТАЛСЯ НЕВИДИМ ДЛЯ РАСКАТКИ, потому что никто
# не дописал имя в список. Зависимости код считал сам (with_deps ниже), а КОРНИ переноса
# знала только рука. Список, писанный рукой, устаревает молча и выглядит полным.
# ⇒ Корни считаются ЗАМЕРОМ по живому контуру, а не перечисляются:
#     · SHARED — пересечение имён живого каталога и шаблона (что уже есть у потребителя);
#     · NEW    — живые файлы, ДОСТИЖИМЫЕ из точек входа контура (их зовут или импортируют),
#                которых в шаблоне ещё нет. Достижимость и есть «механизм нужен роли».
# ⚖️ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: замер видит вызовы ПО ИМЕНИ ФАЙЛА и импорты. Механизм,
# который зовут вычисленным именем, он не увидит — такой случай обязан быть назван руками,
# и лучше пусть это будет исключение с подписью, чем список без подписи.
ENTRY = ["guard-all.py", "read-messages.py", "write-message.py", "read-phoenix.py",
         "save-phoenix.py", "backlog.py", "set-rule.py"]
CALLS = re.compile(r"[\"']([a-z0-9_.-]+\.py)[\"']", re.I)


def reachable(live: Path) -> set:
    """Файлы живого контура, достижимые из точек входа: по вызовам и импортам."""
    seen, queue = set(), [n for n in ENTRY if (live / n).exists()]
    while queue:
        n = queue.pop()
        if n in seen or not (live / n).exists():
            continue
        seen.add(n)
        body = (live / n).read_text(encoding="utf-8", errors="replace")
        for cand in set(CALLS.findall(body)):
            if (live / cand).exists():
                queue.append(cand)
        for mod in set(IMPORT.findall(body)):
            if (live / f"{mod}.py").exists():
                queue.append(f"{mod}.py")
    return seen


def roots(live: Path, template: Path):
    """(NEW, SHARED) — замером, а не перечислением."""
    if not live.exists():
        return [], []
    live_names = {p.name for p in live.glob("*.py")}
    tpl_names = {p.name for p in template.glob("*.py")} if template.exists() else set()
    shared = sorted(live_names & tpl_names)
    new = sorted(n for n in reachable(live) if n not in tpl_names)
    return new, shared


# 🪤 ЗДЕСЬ СТОЯЛ ВПЕЧАТАННЫЙ ОБРАЗЕЦ С ИМЕНЕМ НАШЕГО КОНТЕЙНЕРА, и он был слеп вдвойне:
# ① у соседа переносчик не обезличил бы НИЧЕГО — его контейнер зовётся иначе, и чужие
#   пути ушли бы в публичный шаблон живьём; ② он видел только путь ПАПКИ СКРИПТОВ,
#   а пути того же контейнера в других местах (сама база, каталог-репо бэкапа, соседние
#   репозитории) не обезличивались вовсе. Их месяц чистила РУКА в шаблоне (врезка
#   7858d4d) — и каждая чистка рождала вечный «КОНФЛИКТ»: рука и переносчик тянули файл
#   в разные стороны. Найдено при закрытии карточки #208 — последний живой путь
#   в шаблоне пережил три чистки именно так.
# ⇒ Корень контейнера ВЫВОДИТСЯ и заменяется ЦЕЛИКОМ, в обоих видах косых.
_КОРЕНЬ = str(mezo_paths.container_root())


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
    """Единственное место, где описано отличие копии шаблона от живой копии.

    Вид косых сохраняется как в исходной строке: замена целиком не переписывает то,
    что идёт после корня, — иначе пример с обратными косыми стал бы смесью двух видов.
    """
    for real in (_КОРЕНЬ, _КОРЕНЬ.replace("\\", "/")):
        text = text.replace(real, "<КОНТУР>")
    return text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description="перенос живых механизмов в шаблон + сторож пары")
    ap.add_argument("--apply", action="store_true", help="ПЕРЕНЕСТИ. Без него — только замер")
    # ⚖️ Ключ ИМЕНУЕТ файлы поимённо, а не гасит проверку целиком: «перезаписать всё»
    # вернуло бы ровно ту молчаливую потерю, ради которой манифест и заведён.
    ap.add_argument("--take-live", nargs="+", metavar="ФАЙЛ", default=[],
                    help="перенести НАЗВАННЫЕ файлы поверх шаблонной правки. Цена печатается "
                         "числом потерянных строк — смотри её ДО, а не после")
    a = ap.parse_args()

    if not LIVE.exists():
        print(f"⚠️ живого каталога нет: {LIVE}")
        print("   Это НЕ «всё сведено» — это «сверять не с чем». В чужом контуре так и будет:")
        print("   сторож пары имеет смысл только там, где живой контур рядом с шаблоном.")
        return 0

    missing, differ, same = [], [], []
    NEW, SHARED = roots(LIVE, TEMPLATE)
    print(f"📏 корни ЗАМЕРОМ: новых {len(NEW)} · общих {len(SHARED)}"
          f" (списка от руки больше нет — #145+)")
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

    # ═══ МАНИФЕСТ ПЕРЕНОСА — ЗАТИРАНИЕ ЧУЖОЙ ПРАВКИ БОЛЬШЕ НЕ МОЛЧИТ (10.08 06:47 UTC) ═══
    # 🪤 ОПЛАЧЕНО ЧАСОМ РАНЬШЕ, МНОЙ ЖЕ: --apply молча перезаписал ПЯТЬ шаблонных файлов
    # с сегодняшними фиксами (#145: сборка с инструментами, выведенные пути, применимость
    # реестра) старыми живыми копиями. Я сам предсказал этот класс утром — и сам в него
    # шагнул: ЗНАНИЕ О КЛАССЕ НЕ ЗАЩИЩАЕТ, ЗАЩИЩАЕТ МЕХАНИЗМ. Спас только git.
    # ⇒ Манифест помнит отпечаток КАЖДОГО перенесённого файла. Если шаблонная копия
    # отличается и от манифеста, и от живой — её правили РУКОЙ после переноса, и затереть
    # её значит откатить чужую работу. Такой файл НЕ переносится: печатается КОНФЛИКТ
    # с обоими отпечатками, решает человек (обычно — донеся фикс до живой копии).
    import json
    manifest_p = TEMPLATE / ".sync-manifest.json"
    manifest = {}
    if manifest_p.exists():
        try:
            manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("⚠️ манифест переноса нечитаем — конфликтов НЕ вижу, переношу как впервые")

    TEMPLATE.mkdir(parents=True, exist_ok=True)
    conflicts, moved = [], 0
    for n, want, dst, *_ in [(m[0], m[1], m[2]) for m in missing] + \
                            [(d[0], d[1], d[2]) for d in differ]:
        if dst.exists() and n in manifest:
            have = digest(dst.read_text(encoding="utf-8"))
            if have != manifest[n] and have != digest(want):
                # 🩸 ЦЕНА КОНФЛИКТА НАЗЫВАЕТСЯ ЧИСЛОМ (27.08). Прежде отчёт говорил «правлен
                # в шаблоне» и предлагал «осознанно перезаписать рукой» — не сказав, ЧТО
                # при этом потеряется. Человек решал вслепую и выбирал по удобству.
                # Замер того же дня: у backlog.py уникального в шаблоне было НОЛЬ строк —
                # то есть «конфликт» ничего не стоил, а выглядел одинаково с настоящим.
                потеря = [l for l in dst.read_text(encoding="utf-8").splitlines()
                          if l.strip() and l not in want.splitlines()]
                conflicts.append((n, have, manifest[n], len(потеря)))
                if not (a.take_live and n in a.take_live):
                    continue
                print(f"  ⚠️ {n}: перенос ПО ЯВНОМУ СЛОВУ, теряется строк: {len(потеря)}")
        dst.parent.mkdir(parents=True, exist_ok=True)   # у шагов схемы свой подкаталог
        dst.write_text(want, encoding="utf-8", newline="\n")
        manifest[n] = digest(want)
        moved += 1
        print(f"  ✅ {n}")
    for name in same:
        manifest.setdefault(name, digest(sanitize((LIVE / name).read_text(encoding="utf-8"))))
    manifest_p.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")

    if conflicts:
        # ⚠️ Заголовок НЕ утверждает «не тронуты» безусловно: с --take-live часть из них
        # перенесена по явному слову, и прежняя формулировка стала бы ложью в собственном
        # отчёте — тем самым классом, который этот механизм и стережёт.
        взято = [n for n, *_ in conflicts if n in (a.take_live or [])]
        хвост = (f"; перенесено по явному слову: {len(взято)}" if взято else ", НЕ ТРОНУТЫ")
        print(f"\n⛔ КОНФЛИКТ — {len(conflicts)} файл(ов) правлены В ШАБЛОНЕ после переноса"
              f"{хвост}:")
        for n, have, saw, потеря in conflicts:
            цена = ("уникального в шаблоне НЕТ — перенос ничего не теряет" if потеря == 0
                    else f"в шаблоне {потеря} строк, которых в живой копии нет")
            print(f"     · {n}: шаблон {have} · последний перенос {saw}")
            print(f"       цена переноса: {цена}")
        print("   ⇒ решает человек: донести шаблонный фикс до ЖИВОЙ копии (тогда перенос"
              " сойдётся сам) либо перенести поимённо: --take-live <файл> [<файл>…]")
        print("   ⚖️ Цена названа ЧИСЛОМ выше: ноль значит, что терять нечего, и тогда"
              " конфликт — след прошлой ручной правки, а не чужая работа.")
    print(f"\n✅ Перенесено: {moved}. Дальше: собрать СВЕЖИЙ контур "
          "и прогнать приёмки НА НЁМ — приёмка на своей копии не доказывает ничего про чужую.")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
