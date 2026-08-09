# -*- coding: utf-8 -*-
r"""sync-vnext-pair.py — СТРОИТЕЛЬ пары «рабочий каталог ↔ шаблон» (зона PROTO).

═══ ПОЧЕМУ НЕ ЗЕРКАЛО — ЭТО ОПЛАЧЕНО ОШИБКОЙ, А НЕ ВЫВЕДЕНО ИЗ ГОЛОВЫ ═══
2026-08-09 пара разошлась на 27 файлов. Первое, что просится, — сделать каталоги
одинаковыми. Сделал — и прогон опроверг через две минуты:
```
bite-all из ШАБЛОНА .... держится 34 · сломано 0 · не проверено 1
bite-all из РАБОЧЕГО ... держится 26 · сломано 2 · НЕ ПРОВЕРЕНО 7   ← при ТЕХ ЖЕ файлах
```
Девять из четырнадцати в рабочем каталоге не работают вовсе: они строят стенд из схемы,
лежащей рядом с ШАБЛОНОМ. Замер запуском (17:43 UTC): из десяти приёмок шаблона переносимы
ДВЕ, остальные восемь привязаны к нему по построению.
⇒ **Зеркало ради зелёного сторожа кладёт потребителю падающие инструменты.**

═══ ЧТО ДЕЛАЕТ СТРОИТЕЛЬ — И ЧЕГО ОН НАМЕРЕННО НЕ ДЕЛАЕТ ═══
```
① рабочий → шаблон .... ВСЁ, чего в шаблоне нет или что разошлось. Это направление
                        обязательно: чего нет в шаблоне, того НЕ БУДЕТ У ПОТРЕБИТЕЛЯ,
                        и он об этом не узнает — сверка молчит (@RCC #3338)
② шаблон → рабочий .... НИЧЕГО не тянет автоматически. Вместо переноса — ПРОВЕРКА:
                        всё, что живой контур ЗОВЁТ, обязано в рабочем быть
⛔ приведение путей ... НЕ делает — и с 09.08 20:43 UTC оно НЕ НУЖНО: пути машины больше
                        не впечатаны в файлы, они ВЫВОДЯТСЯ (mezo_paths: среда → маркер →
                        local.paths → громкий отказ). Файлы из шаблона запускаются как есть;
                        заглушка «<КОНТУР>» сломала бы общий прогон, а выведенный путь — нет
```
🎯 СПИСОК ВЫЗЫВАЕМОГО БЕРЁТСЯ ЗАМЕРОМ, А НЕ РУКОЙ. Грепом по живым скриптам: что они
зовут из рабочего каталога. Список, писанный рукой, устаревает молча — этим контур уже
платил (стенд копировал зависимости списком из ОДНОГО имени).

    python sync-vnext-pair.py            замер: что разошлось
    python sync-vnext-pair.py --apply    перенести рабочий → шаблон
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

RUNTIME = mezo_paths.container_root() / "vnext-tools"
TEMPLATE = Path(__file__).resolve().parents[1] / "prototype"
LIVE_SCRIPTS = mezo_paths.live_scripts()

# «vnext-tools» / "vnext-tools" ... "имя.py" — как живой скрипт зовёт файл из рабочего каталога
CALLS = re.compile(r"vnext-tools[\"'\s/\\]+[^\n]{0,40}?[\"']([a-z0-9_.-]+\.py)[\"']", re.I)
IMPORT = re.compile(r"^\s*(?:import|from)\s+([a-z_][a-z0-9_]*)", re.M)
FILEREF = re.compile(r"[\"']([a-z0-9_.-]+\.py)[\"']", re.I)


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def called_by_live() -> set:
    """Что живой контур зовёт из рабочего каталога — ЗАМЕРОМ по его коду."""
    names = set()
    if not LIVE_SCRIPTS.is_dir():
        return names
    for p in LIVE_SCRIPTS.glob("*.py"):
        names |= set(CALLS.findall(p.read_text(encoding="utf-8", errors="replace")))
    return names


def closure(name: str, pool: dict, seen=None) -> set:
    """Файл ВМЕСТЕ с тем, что он зовёт. Единица переноса — замыкание, а не файл.

    🪤 Оплачено в тот же час: судил переносимость, копируя приёмку БЕЗ её проверки,
    и получил «непереносима» у файла, написанного часом раньше и заведомо переносимого.
    """
    seen = seen if seen is not None else set()
    if name in seen or name not in pool:
        return seen
    seen.add(name)
    text = pool[name].read_text(encoding="utf-8", errors="replace")
    for m in IMPORT.findall(text):
        closure(m + ".py", pool, seen)
    for r in FILEREF.findall(text):
        closure(r, pool, seen)
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="перенести рабочий → шаблон")
    ap.add_argument("--runtime", default=None)
    ap.add_argument("--template", default=None)
    ap.add_argument("--live", default=None, help="каталог живых скриптов (для проверки вызовов)")
    a = ap.parse_args()

    global LIVE_SCRIPTS
    rt = Path(a.runtime) if a.runtime else RUNTIME
    tpl = Path(a.template) if a.template else TEMPLATE
    if a.live:
        LIVE_SCRIPTS = Path(a.live)

    for d, label in ((rt, "рабочий"), (tpl, "шаблон")):
        if not d.is_dir():
            print(f"⛔ {label} каталог не найден: {d} — строить нечего (это НЕ «совпадают»)")
            return 2

    r = {p.name: p for p in rt.glob("*.py")}
    t = {p.name: p for p in tpl.glob("*.py")}
    if not r:
        print(f"⛔ рабочий каталог пуст: {rt} — переносить нечего. Это НЕ «всё сведено»")
        return 2

    missing = sorted(set(r) - set(t))
    drift = sorted(n for n in set(r) & set(t) if digest(r[n]) != digest(t[n]))
    # замыкание: файл тянет то, что зовёт (иначе у потребителя окажется половина связки)
    plan = set(missing) | set(drift)
    for n in list(plan):
        plan |= {d for d in closure(n, r) if d in r and (d not in t or digest(r[d]) != digest(t[d]))}
    plan = sorted(plan)

    # ── направление ②: не переносим, а ПРОВЕРЯЕМ доступность вызываемого
    called = called_by_live()
    lost = sorted(n for n in called if n not in r)

    print(f"📏 рабочий {len(r)} · шаблон {len(t)} · общих {len(set(r) & set(t))}")
    if plan:
        print(f"\n🔴 НЕ ДОЕДЕТ ДО ПОТРЕБИТЕЛЯ — {len(plan)} (нет в шаблоне или разошлось):")
        for n in plan:
            why = "нет в шаблоне" if n not in t else "разошлось"
            pulled = " (тянется замыканием)" if n not in missing and n not in drift else ""
            print(f"   · {n:40} {why}{pulled}")
    else:
        print("✅ всё, что есть в рабочем, доехало до шаблона")

    if lost:
        print(f"\n🔴 ЖИВОЙ КОНТУР ЗОВЁТ, А В РАБОЧЕМ НЕТ — {len(lost)}:")
        for n in lost:
            print(f"   · {n}")
    elif called:
        print(f"✅ живой контур зовёт {len(called)} — все на месте")
    else:
        print("⚠️ вызовов из живых скриптов НЕ НАЙДЕНО — это может значить и «их нет»,"
              " и «замер не сработал». Проверь, тот ли каталог живых скриптов")

    if a.apply and plan:
        for n in plan:
            (tpl / n).write_bytes(r[n].read_bytes())
        print(f"\n✅ перенесено рабочий → шаблон: {len(plan)}")
    elif plan:
        print("\n⚖️ это ЗАМЕР. Перенести: --apply")

    print("⚖️ ГРАНИЦА: сведены ФАЙЛЫ. Совпадение байтов НЕ означает, что копии равносильны:"
          " инструмент зависит от того, что лежит рядом. Обратное направление НЕ переносится"
          " намеренно — из десяти приёмок шаблона переносимы две (замер 09.08).")
    return 1 if (plan or lost) else 0


if __name__ == "__main__":
    sys.exit(main())
