# -*- coding: utf-8 -*-
"""
bootstrap.py — поднять ПЕСОЧНИЦУ для прототипирования mezosync v-next.

⛔ ГРАНИЦА (мандат владельца роли PROTO, 2026-07-25): живой субстрат
   C:\\guts\\.atlas\\.mezosync\\ — ТОЛЬКО ЧТЕНИЕ. Этот скрипт открывает живую БД
   строго `mode=ro` и снимает её консистентную копию ЧЕРЕЗ SQLite backup API.

ПОЧЕМУ backup API, а не copy файла: живая БД в режиме WAL. Копия .db без -wal/-shm
при активных писателях даёт РВАНЫЙ снимок (часть транзакций осталась в WAL). backup API
берёт согласованный снимок под своей блокировкой чтения и не пишет в источник.

v2 (2026-07-26): песочница воспроизводит СТРУКТУРУ живого контейнера —
    <sandbox>/mezosync.db  +  <sandbox>/scripts/*.py
Это не косметика: этап Э-Ж (устойчивость инструментов) проверяет поиск БД ОТ РАСПОЛОЖЕНИЯ
СКРИПТА. На плоской копии такой укус нечестен — он прошёл бы по случайности.

v3 (2026-08-09, карточка #150): песочница строится ТЕМИ ЖЕ ШАГАМИ СХЕМЫ, что живая база,
и СВЕРЯЕТСЯ ПО ЖУРНАЛУ ШАГОВ, а не только по счётчикам строк.
🪤 Цена, из-за которой это заведено: песочница-снимок от 26.07 прожила ДВЕ НЕДЕЛИ, отстав
от живой схемы на несколько шагов (не было acked_at/shown_max у батчей, адресатов, прав
ролей, журнала шагов ВООБЩЕ) — и приёмка bite-r16 честно краснела на гонке, которую замок
в живой базе уже запрещал. **Испытывали механизм в условиях, которых больше нет.** Третий
за день экземпляр класса «испытываем не то, что чиним»: копия инструмента видна глазами,
отставшая копия СХЕМЫ выглядит рабочей базой.
⇒ Три меры, каждая закрывает свой отказ:
    ① copy_scripts копирует и scripts/migrations/ — шаги схемы едут ВМЕСТЕ со скриптами;
    ② apply_migrations прогоняет каждый шаг по песочнице (шаги идемпотентны — на свежем
      снимке это но-оп, на старом — ЛЕЧЕНИЕ);
    ③ verify сверяет ЖУРНАЛ ШАГОВ песочницы с живым: расхождение — красное, а не молчание.
      Счётчики строк дрейфуют законно (лента живёт), журнал шагов — НЕТ.

Использование:
    python bootstrap.py                 # снять свежую песочницу (БД + скрипты + шаги схемы)
    python bootstrap.py --verify        # только сверить существующую
    python bootstrap.py --no-scripts    # только БД
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)

import argparse
import shutil
import sqlite3
import subprocess
import sys
import os
from pathlib import Path

LIVE_MEZO = mezo_paths.container_root() / ".mezosync"
LIVE_DB = LIVE_MEZO / "mezosync.db"
# Песочница живёт ВНЕ контейнера C:\guts\.atlas НАРОЧНО: гард ⑤ («фантомные .db»)
# рекурсивно сканирует весь контейнер. Полная копия его не краснит (он судит по признаку
# «ноль таблиц»), но ПРОМЕЖУТОЧНАЯ пустая БД — закраснила бы, и уже у ВСЕХ ролей сразу.
# Прототип не имеет права шуметь в чужих гардах.
DEFAULT_ROOT = Path(os.environ.get("MEZOSYNC_SANDBOX") or (Path.home() / ".mezosync-sandbox"))


def snapshot(live: Path, dest: Path) -> None:
    if not live.exists():
        sys.exit(f"ERR: живая БД не найдена: {live}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True, timeout=10)   # источник неизменяем
    if dest.exists():
        dest.unlink()
    dst = sqlite3.connect(str(dest))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def copy_scripts(live_scripts: Path, dest_scripts: Path) -> int:
    """Копии рабочих скриптов — ИСХОДНЫЕ, без правок. Прототипы кладутся рядом отдельными
    именами (*-vnext.py), чтобы сравнение «до/после» всегда было доступно в одном месте."""
    dest_scripts.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(live_scripts.glob("*.py")):
        shutil.copy2(p, dest_scripts / p.name)
        n += 1
    # v3: шаги схемы едут ВМЕСТЕ со скриптами. Урок карточки #148 в ту же сторону:
    # без своей копии шагов песочница «лечится» только из живого — то есть не лечится.
    mig_src = live_scripts / "migrations"
    if mig_src.exists():
        mig_dst = dest_scripts / "migrations"
        mig_dst.mkdir(parents=True, exist_ok=True)
        for p in sorted(mig_src.glob("*.py")):
            shutil.copy2(p, mig_dst / p.name)
            n += 1
    return n


def apply_migrations(root: Path, dest: Path) -> int:
    """Прогнать шаги схемы из КОПИИ ПЕСОЧНИЦЫ по базе песочницы, в порядке имён.

    Шаги идемпотентны (норма migration-safety): на свежем снимке это но-оп,
    на старом — приведение к живой схеме. Зовём копию, а не живой каталог, —
    иначе песочница «самодостаточна» только на словах.
    ⚖️ Отказ шага — ГРОМКИЙ и останавливает сборку: песочница с половиной схемы
    хуже отсутствующей, она выглядит рабочей."""
    mig_dir = root / "scripts" / "migrations"
    if not mig_dir.exists():
        print("⚠️ шагов схемы в песочнице НЕТ — прогонять нечего (старая копия скриптов?)")
        return 0

    # УЖЕ ЗАПИСАННЫЕ шаги пропускаем ПО ЖУРНАЛУ, а не прогоняем повторно.
    # 🪤 Найдено первым же прогоном v3: шаг 20260807-addressed-by-unset НЕ идемпотентен
    #    (пересборка таблицы падает на «already exists») — нарушение нормы migration-safety,
    #    но файл в чужой зоне, и чинить применение честнее, чем молча править чужой шаг.
    # ⚖️ Имя в журнале НЕ всегда равно имени файла (20260808-role-rights.py → 009-role-rights),
    #    поэтому сравниваем ХВОСТ после числового префикса — он совпадает у всех восьми.
    import re as _re

    def tail(s):
        return _re.sub(r"^[0-9]+-", "", s)

    con = sqlite3.connect(str(dest))
    try:
        applied = {tail(v) for v, in con.execute("SELECT version FROM schema_migrations")}
    except sqlite3.OperationalError:
        applied = set()                     # журнала нет — применяем всё
    con.close()

    n = skipped = 0
    for step in sorted(mig_dir.glob("*.py")):
        if tail(step.stem) in applied:
            skipped += 1
            continue
        r = subprocess.run([sys.executable, str(step), "--db", str(dest)],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            tail_out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-6:]
            sys.exit(f"⛔ шаг {step.name} НЕ ПРОШЁЛ по песочнице:\n   " + "\n   ".join(tail_out))
        n += 1
    if skipped:
        print(f"[schema]   пропущено по журналу (уже применены): {skipped}")
    return n


def verify(live: Path, dest: Path, root: Path) -> int:
    """Песочница обязана быть ПОЛНОЙ копией: сверяем состав объектов и счётчики строк.
    Инвариант TEST-MUST-BE-ABLE-TO-FAIL: расхождение печатаем явно и возвращаем 1."""
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)

    def objects(c):
        return {(n, t) for n, t in c.execute(
            "SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}

    o_src, o_dst = objects(src), objects(dst)
    ok = True
    if o_src != o_dst:
        ok = False
        print(f"⛔ состав объектов расходится: только в живой {o_src - o_dst}, "
              f"только в песочнице {o_dst - o_src}")
    tables = sorted(n for n, t in o_src if t == "table")
    diffs = []
    for t in tables:
        a = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        b = dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if a != b:
            diffs.append(f"{t}: живая {a} ≠ песочница {b}")
    if diffs:
        ok = False
        print("⛔ счётчики строк расходятся: " + "; ".join(diffs))

    # v3: ЖУРНАЛ ШАГОВ — главная сверка. Счётчики строк дрейфуют законно (лента живёт
    # между снимком и сверкой), журнал шагов — НЕТ: расхождение значит, что песочница
    # испытывает механизм в ДРУГОЙ схеме, и всё красное/зелёное на ней — о прошлом.
    def steps(c):
        try:
            return {v for v, in c.execute("SELECT version FROM schema_migrations")}
        except sqlite3.OperationalError:
            return None                     # журнала нет вовсе — это тоже ответ

    s_src, s_dst = steps(src), steps(dst)
    if s_src is None:
        print("⚠️ в ЖИВОЙ базе нет журнала шагов — сверять не с чем (это не «чисто»)")
    elif s_dst is None:
        ok = False
        print("⛔ в ПЕСОЧНИЦЕ нет журнала шагов ВООБЩЕ — она из эпохи до журнала. "
              "Пересними: python bootstrap.py")
    elif s_src - s_dst:
        ok = False
        print(f"⛔ песочница ОТСТАЛА от живой схемы на {len(s_src - s_dst)} шаг(ов): "
              + ", ".join(sorted(s_src - s_dst)))
    else:
        extra = f" (+{len(s_dst - s_src)} своих)" if s_dst - s_src else ""
        print(f"✅ журнал шагов: песочница несёт все {len(s_src)} шагов живой{extra}")

    live_wal = live.with_suffix(".db-wal")
    n_scripts = len(list((root / "scripts").glob("*.py"))) if (root / "scripts").exists() else 0
    print(f"{'✅' if ok else '⛔'} песочница {'сверена' if ok else 'РАСХОДИТСЯ'}: "
          f"{len(tables)} таблиц, {sum(1 for _, t in o_src if t == 'view')} VIEW, "
          f"{n_scripts} скриптов")
    print(f"   живая:     {live}  ({live.stat().st_size/1024:.0f} КБ)"
          f"{'  [WAL активен]' if live_wal.exists() else ''}")
    print(f"   песочница: {dest}  ({dest.stat().st_size/1024:.0f} КБ)")
    src.close()
    dst.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Песочница mezosync v-next")
    ap.add_argument("--live", default=str(LIVE_DB), help="живая БД (только чтение)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="корень песочницы")
    ap.add_argument("--verify", action="store_true", help="только сверить, не пересоздавать")
    ap.add_argument("--no-scripts", action="store_true", help="не копировать скрипты")
    args = ap.parse_args()
    live, root = Path(args.live), Path(args.root)
    dest = root / "mezosync.db"          # имя как в живом: прототипы ищут БД по имени

    if not args.verify:
        snapshot(live, dest)
        print(f"[snapshot] {live} → {dest}")
        if not args.no_scripts:
            n = copy_scripts(LIVE_MEZO / "scripts", root / "scripts")
            print(f"[scripts]  скопировано {n} шт. (вкл. шаги схемы) → {root / 'scripts'}")
            m = apply_migrations(root, dest)
            print(f"[schema]   прогнано шагов схемы по песочнице: {m} "
                  f"(на свежем снимке — но-оп, на старом — лечение)")
    sys.exit(verify(live, dest, root))


if __name__ == "__main__":
    main()
