r"""
guard-scripts-drift.py — рантайм тулкита против его версионированной копии в репо.

ЗАЧЕМ. До 2026-07-16 17:53 UTC тулкит НЕ БЫЛ ВЕРСИОНИРОВАН НИЧЕМ: 20 скриптов в
C:\guts\.atlas\.mezosync\scripts\ — вне любого git (контейнер .atlas не репо). Там живут
бэкап-механизм, оба гарда и read-phoenix.py, которым воскрешаются ВСЕ роли. Потеря каталога
уносила бы и БД, и средства её восстановления одним движением.
Владелец (17:52 UTC): «клади в atlas.agents-sync.db».

ПОЧЕМУ КОПИЯ, А НЕ ПЕРЕНОС: рантайм ОБЯЗАН остаться в .mezosync/scripts/ — оттуда его
достают все 8 ролей. Инвариант TOOLS-INSIDE-CONTAINER родился 2026-07-12 из отката Фазы 4:
скрипты лежали в C:\github\gordipack, песочница STUD (C:\guts) их не доставала, он был
МОЛЧА отрезан от SQLite. Перенести = повторить ту же беду.

ПОЧЕМУ ГАРД ОБЯЗАТЕЛЕН. Копия делает ТРЕТИЙ источник: gordipack (шаблон) → рантайм → репо.
Три копии одного кода — ровно та болезнь, которую весь день лечили («источник истины в двух
местах — это не „надо синхронизировать“, это сломанный источник»). Устранить копию нельзя,
но можно сделать расхождение ГРОМКИМ. Молчаливый дрейф — вот что опасно:
· STUD #1982 нашёл, что gordipack/scripts разошёлся с рантаймом; синхронизация шаблон→рантайм
  МОЛЧА снесла бы фикс ридера и гард хронологии;
· sync.rules.md ПЯТЬ ЧАСОВ держал отозванное правило как приказ — потому что расхождение
  никто не видел.
⇒ Этот гард не мешает дрейфу. Он не даёт дрейфу быть ТИХИМ.

⚠️ ПОРТАТИВНОСТЬ ШАБЛОНА. RUNTIME — это каталог самого скрипта (портативно). REPO —
версионированное ЗЕРКАЛО-репо, оно ВНЕШНЕЕ и Atlas-специфичное; в свежей системе его нет.
Путь к зеркалу задаётся env-переменной MEZOSYNC_MIRROR. Не задана или каталога нет — гард
НЕ ПАДАЕТ и не краснит, а no-op с пометкой: сравнивать не с чем, дрейф ещё не мог возникнуть.

ЗАПУСК:
    python guard-scripts-drift.py            # exit 1 при расхождении
    python guard-scripts-drift.py --sync     # рантайм → репо (рантайм ИСТОЧНИК)
    (зеркало: env MEZOSYNC_MIRROR=<путь к scripts-копии в версионированном репо>)
"""

import argparse
import filecmp
import hashlib
import os
import shutil
import sys
from pathlib import Path

# RUNTIME — каталог этого скрипта (портативно). REPO — внешнее версионированное зеркало,
# задаётся env MEZOSYNC_MIRROR; в свежей системе его нет — тогда гард no-op (см. main).
RUNTIME = Path(__file__).resolve().parent
REPO = Path(os.environ["MEZOSYNC_MIRROR"]) if os.environ.get("MEZOSYNC_MIRROR") else None


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true",
                    help="скопировать рантайм → репо. НАПРАВЛЕНИЕ ОДНО: рантайм — ИСТОЧНИК, "
                         "репо — версионированное зеркало. Обратно НЕ синкаем: репо может "
                         "отстать, а роли работают рантаймом.")
    args = ap.parse_args()

    # Зеркало не сконфигурировано или отсутствует — сравнивать не с чем. No-op, не крах:
    # свежая система ещё не завела версионированную копию, дрейф физически не мог возникнуть.
    if REPO is None:
        print("⏭️ зеркало не задано (env MEZOSYNC_MIRROR) — дрейф-гард пропущен (сравнивать не с чем)")
        return
    if not REPO.exists() and not args.sync:
        print(f"⏭️ зеркало не найдено: {REPO} — дрейф-гард пропущен (нечего сравнивать)")
        return

    REPO.mkdir(parents=True, exist_ok=True)
    rt = {p.name: p for p in RUNTIME.glob("*.py")}
    rp = {p.name: p for p in REPO.glob("*.py")}

    only_rt = sorted(set(rt) - set(rp))
    only_rp = sorted(set(rp) - set(rt))
    diff = sorted(n for n in set(rt) & set(rp) if not filecmp.cmp(rt[n], rp[n], shallow=False))

    print(f"рантайм: {len(rt)} скриптов ({RUNTIME})")
    print(f"репо   : {len(rp)} скриптов ({REPO})")

    if not (only_rt or only_rp or diff):
        print("\n✅ СОВПАДАЕТ: рантайм и версионированная копия идентичны.")
        return

    if only_rt:
        print(f"\n⛔ НЕТ В РЕПО ({len(only_rt)}) — не версионированы, потеряются вместе с каталогом:")
        for n in only_rt:
            print(f"   {n}")
    if diff:
        print(f"\n⛔ РАСХОДЯТСЯ ({len(diff)}) — репо держит УСТАРЕВШИЙ код:")
        for n in diff:
            print(f"   {n:26} рантайм {sha(rt[n])} ≠ репо {sha(rp[n])}")
    if only_rp:
        print(f"\n⚠️  ЕСТЬ В РЕПО, НЕТ В РАНТАЙМЕ ({len(only_rp)}) — удалён? переименован? Решай ГЛАЗАМИ:")
        for n in only_rp:
            print(f"   {n}")

    if not args.sync:
        print("\n   Синхронизировать: python guard-scripts-drift.py --sync   (затем commit+push)")
        sys.exit(1)

    for n in only_rt + diff:
        shutil.copy2(rt[n], REPO / n)
        print(f"   ✅ {n}")
    print(f"\n✅ Скопировано в репо: {len(only_rt) + len(diff)}. Дальше: commit + push "
          f"(стоячее разрешение владельца — ТОЛЬКО этот репо).")
    if only_rp:
        print("⚠️  Лишние в репо НЕ удалял: удаление — решение человека, не скрипта.")


if __name__ == "__main__":
    main()
