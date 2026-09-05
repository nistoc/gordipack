#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА сворачивания истории версий памяти (memory-history-fold.py, карточка #538 шаг ②).

Всё на КОПИИ живой базы (или названной --db); живую не трогает ни одним байтом.
Случаи судят ПРЕДМЕТ другим определением, чем инструмент (иначе мерка повторяла бы отсев):
инструмент считает «что уедет», приёмка проверяет «что ОСТАЛОСЬ» по свойствам —
каждая молодая на месте · у каждого раздела максимум часа на месте · перед каждой отметкой
пересоздания последняя на месте · всё унесённое — старое и ни одно из хранимых · объединение
не изменилось · возврат даёт прежнюю таблицу знак в знак.

🎯 ПОРЧА (--break rebirth): из инструмента снято хранение «последней перед пересозданием» —
краснеют случаи ③ · ③-в · ③-г (три взгляда на ОДНО свойство: с хранимой стороны и с унесённой),
остальные зелёные — в том числе ③-д «объединение не изменилось»: потерь ноль даже под порчей.
⚖️ Первый прогноз был «ровно ③» и не сошёлся: ③-в и ③-г судят то же свойство по унесённому,
и молчать под порчей они не могли. Прогноз поправлен по замеру, не наоборот (05.09 07:07 UTC).
Порченая копия кладётся РЯДОМ с оригиналом
и снимается в finally (копия в стороннем каталоге не запускается — урок TAXO, карточка #545).

    python C:/guts/.atlas/vnext-tools/bite-memory-history-fold.py
    python C:/guts/.atlas/vnext-tools/bite-memory-history-fold.py --break rebirth
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402

TOOL = HERE / "memory-history-fold.py"
MIGR = mezo_paths.live_scripts() / "migrations" / "20260905-phoenix-history-archive.py"
ПОРЧИ = {
    "rebirth": ('            if before and before[-1][0] not in keep:\n',
                '            if False and before and before[-1][0] not in keep:\n'),
}
ИТОГ = []


def case(title, ok, detail=""):
    ИТОГ.append(ok)
    print(("✅ " if ok else "🔴 ") + title + (f"\n   {detail}" if detail else ""))


def run(args, env_role=None, db=None, tool=None):
    env = dict(os.environ); env.pop("MEZO_ROLE", None)
    if env_role: env["MEZO_ROLE"] = env_role
    cmd = [sys.executable, "-B", str(tool or TOOL)] + args + (["--db", str(db)] if db else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, r.stdout + r.stderr


def файл_отпечаток(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]


def снимок(conn, роль):
    return conn.execute("SELECT id, section, saved_at, body FROM phoenix_history WHERE role=? ORDER BY id",
                        (роль,)).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="база-образец; по умолчанию живая (копируется)")
    ap.add_argument("--role", default="PROTO", help="чью историю сворачивать в опыте")
    ap.add_argument("--break", dest="слом", choices=sorted(ПОРЧИ), default=None)
    a = ap.parse_args()
    роль = a.role.upper()
    src = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-fold-"))
    db = tmp / "copy.db"
    shutil.copyfile(src, db)
    live_fp = файл_отпечаток(src)
    tool = TOOL; копия = None
    if a.слом:
        было, стало = ПОРЧИ[a.слом]
        текст = TOOL.read_text(encoding="utf-8")
        if было not in текст:
            print(f"⛔ порчу «{a.слом}» навести не удалось: образец не найден в коде"); return 2
        копия = HERE / f"memory-history-fold.__break_{a.слом}__.py"
        копия.write_text(текст.replace(было, стало, 1), encoding="utf-8")
        tool = копия
        print(f"⚠️ ПОРЧА «{a.слом}» ВЗВЕДЕНА — ждём красного РОВНО в случае ③\n")
    try:
        # шаг схемы на копии
        r = subprocess.run([sys.executable, "-B", str(MIGR), "--db", str(db)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        case("⓪ шаг схемы сводится на копии и пишет себя в журнал", r.returncode == 0 and "ВРЕЗАНО" in r.stdout,
             r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
        conn = sqlite3.connect(str(db))
        n_reb = conn.execute("SELECT count(*) FROM role_rebirths").fetchone()[0]
        case("⓪-бис отметки пересоздания засеяны (18, у 9 ролей, у каждой источник)",
             n_reb == 18 and conn.execute("SELECT count(DISTINCT role) FROM role_rebirths").fetchone()[0] == 9
             and conn.execute("SELECT count(*) FROM role_rebirths WHERE source NOT LIKE 'transcript:%'").fetchone()[0] == 0,
             f"отметок {n_reb}")
        до_снимок = снимок(conn, роль)
        порог = conn.execute("SELECT datetime('now','-7 days')").fetchone()[0]
        отметки = [r[0] for r in conn.execute("SELECT at FROM role_rebirths WHERE role=? ORDER BY at", (роль,))]
        fp_before = файл_отпечаток(db)

        # ① холостой прогон — ни байта
        код, вывод = run(["--role", роль, "--dry-run"], db=db, tool=tool)
        case("① --dry-run считает и не пишет ни байта (отпечаток файла базы совпал)",
             код == 0 and "ВХОЛОСТУЮ" in вывод and файл_отпечаток(db) == fp_before, вывод.strip().splitlines()[-1] if вывод.strip() else "")
        # ② чужая рука — отказ, база не тронута
        другая = "TAXO" if роль != "TAXO" else "CORE"
        код, вывод = run(["--role", другая], env_role=роль, db=db, tool=tool)
        case("② чужую историю не сворачивает: отказ кодом 2, база не тронута",
             код == 2 and "ТОЛЬКО СВОЮ" in вывод and файл_отпечаток(db) == fp_before, вывод.strip().splitlines()[-1])
        код, вывод = run(["--role", роль], db=db, tool=tool)
        case("②-бис без MEZO_ROLE перенос отказан кодом 2", код == 2 and "ЧЬЯ РУКА" in вывод)

        # свёртка своей
        код, вывод = run(["--role", роль], env_role=роль, db=db, tool=tool)
        conn = sqlite3.connect(str(db))
        осталось = снимок(conn, роль)
        ост_ids = {r[0] for r in осталось}
        арх = conn.execute("SELECT id, section, saved_at, body FROM phoenix_history_archive WHERE role=? ORDER BY id",
                           (роль,)).fetchall()
        case(f"③-контроль свёртка прошла кодом 0 и что-то унесла ({len(арх)} версий)", код == 0 and len(арх) > 0,
             вывод.strip().splitlines()[-2] if len(вывод.strip().splitlines()) > 1 else вывод)
        # свойства ОСТАВШЕГОСЯ — другое определение предмета
        молодые = [r for r in до_снимок if r[2] >= порог]
        case("③-а каждая версия моложе 7 суток на месте", all(r[0] in ост_ids for r in молодые), f"молодых {len(молодые)}")
        разделы = {}
        for r in до_снимок: разделы.setdefault(r[1], []).append(r)
        последние = [max(vs, key=lambda r: (r[2], r[0])) for vs in разделы.values()]
        case("③-б у каждого раздела последняя по часу версия на месте", all(r[0] in ост_ids for r in последние))
        перед = []
        for vs in разделы.values():
            for t in отметки:
                b = [r for r in vs if r[2] < t]
                if b: перед.append(max(b, key=lambda r: (r[2], r[0])))
        case(f"③ перед КАЖДОЙ отметкой пересоздания последняя версия на месте ({len(перед)} шт.)",
             bool(перед) and all(r[0] in ост_ids for r in перед),
             "" if all(r[0] in ост_ids for r in перед) else f"унесены: {[r[0] for r in перед if r[0] not in ост_ids]}")
        хранимые = {r[0] for r in молодые} | {r[0] for r in последние} | {r[0] for r in перед}
        case("③-в всё унесённое — старше порога и не из хранимых",
             all(r[2] < порог and r[0] not in хранимые for r in арх))
        case("③-г унесено РОВНО то, что старое и не хранимое (ничего не забыто)",
             {r[0] for r in до_снимок if r[2] < порог and r[0] not in хранимые} == {r[0] for r in арх})
        объед = sorted(осталось + арх)
        case("③-д объединение история ∪ архив = прежняя история знак в знак", объед == sorted(до_снимок))
        case("③-е в летописи запись fold_history с числом унесённого",
             conn.execute("SELECT count(*) FROM audit_log WHERE action='fold_history' AND target=?",
                          (f"phoenix_history.{роль}",)).fetchone()[0] == 1)
        # ④ возврат
        код, вывод = run(["--role", роль, "--unfold"], env_role=роль, db=db, tool=tool)
        conn = sqlite3.connect(str(db))
        case("④ --unfold возвращает историю знак в знак под прежними номерами, архив пуст",
             код == 0 and снимок(conn, роль) == до_снимок
             and conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=?", (роль,)).fetchone()[0] == 0,
             вывод.strip().splitlines()[-1])
        # ⑤ повторная свёртка после возврата даёт то же множество (идемпотентность правила)
        код, вывод = run(["--role", роль], env_role=роль, db=db, tool=tool)
        conn = sqlite3.connect(str(db))
        арх2 = {r[0] for r in conn.execute("SELECT id FROM phoenix_history_archive WHERE role=?", (роль,))}
        case("⑤ повторная свёртка уносит то же множество версий", арх2 == {r[0] for r in арх})
        код, вывод = run(["--role", роль], env_role=роль, db=db, tool=tool)
        case("⑤-бис третий вызов: «уносить нечего», код 0", код == 0 and "уносить нечего" in вывод)
        # ⑥ роль без отметок: предупреждение вслух, «перед пересозданием» не хранится
        conn.execute("DELETE FROM role_rebirths WHERE role=?", (роль,)); conn.commit()
        код, вывод = run(["--role", роль, "--dry-run"], db=db, tool=tool)
        case("⑥ у роли без отметок пересоздания инструмент говорит это вслух", "ОТМЕТОК ПЕРЕСОЗДАНИЯ У РОЛИ НЕТ" in вывод)
        case("⑦ живая база не тронута приёмкой (отпечаток файла совпал)", файл_отпечаток(src) == live_fp)
    finally:
        if копия and копия.exists(): копия.unlink()
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(ИТОГ); ok = sum(ИТОГ)
    if a.слом:
        красных = n - ok
        print(f"\n{'✅ так и надо' if красных else '⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ЗЕЛЁНОЕ'}: под порчей красных {красных} из {n}")
        return 0 if красных else 1
    print(f"\n{'✅ ПРИНЯТА' if ok == n else '🔴 НЕ ПРИНЯТА'} — случаев {n}, зелёных {ok}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
