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

🎯 ПОРЧА (--break stale-archive, карточка #628): копия живой базы несёт РЕАЛЬНЫЙ архив роли —
свёртки save-phoenix.py по счёту версий (rule LIKE 'save-phoenix%') и прежние прогоны самого
fold (rule regl-538-②) уже унесли часть истории ДО этого опыта. Приёмка считает «archived» ==
«что унесла ОНА САМА», а для этого чистит архив роли на СВОЕЙ КОПИИ перед опытом (живую база
не трогает ни байтом — это отдельная копия). Порча снимает эту чистку: архив на копии остаётся
ЗАСОРЁН прежним содержимым — краснеют ③-в · ③-г · ③-д · ④ · ⑤ (все пять смотрят на архив или
на историю ЦЕЛИКОМ, а не на то, что унесла ИМЕННО эта свёртка). Живой случай 2026-09-14: у
PROTO в архиве 73 версии ДО опыта (в т.ч. saved_at всего суточной давности — их унёс СЧЁТ
save-phoenix.py, не возраст) — приёмка давала 14 из 19 одинаково до и после правки #505,
потому что беда была не в инструменте и не в снимке WAL, а в состоянии архива роли.

    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py
    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py --break rebirth
    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py --break stale-archive
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
import mezo_stand  # noqa: E402 — карточка #505/#624: согласованная копия живой базы

TOOL = HERE / "memory-history-fold.py"
MIGR = mezo_paths.live_scripts() / "migrations" / "20260905-phoenix-history-archive.py"
BREAKS = {
    "rebirth": ('            if before and before[-1][0] not in keep:\n',
                '            if False and before and before[-1][0] not in keep:\n'),
}
# ⚡ КАРТОЧКА #628: порча НЕ патчит инструмент (BREAKS — текстовые замены В НЁМ), а снимает
# собственную чистку приёмки (архив роли на копии перед опытом) — другой механизм порчи,
# поэтому имя держим ОТДЕЛЬНО от BREAKS, а не третьей записью в том же словаре.
STALE_ARCHIVE_BREAK = "stale-archive"
RESULTS = []


def case(title, ok, detail=""):
    RESULTS.append(ok)
    print(("✅ " if ok else "🔴 ") + title + (f"\n   {detail}" if detail else ""))


def run(args, env_role=None, db=None, tool=None, stand_env=None):
    # ⚡ КАРТОЧКА #613: база вызывающего (stand_env, если дан) — не os.environ вызывающего
    # напрямую: испытуемый инструмент не должен подхватить чужой MEZO_CONTAINER.
    env = dict(stand_env if stand_env is not None else os.environ); env.pop("MEZO_ROLE", None)
    if env_role: env["MEZO_ROLE"] = env_role
    cmd = [sys.executable, "-B", str(tool or TOOL)] + args + (["--db", str(db)] if db else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, r.stdout + r.stderr


def file_fingerprint(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]


def history_snapshot(conn, role):
    return conn.execute("SELECT id, section, saved_at, body FROM phoenix_history WHERE role=? ORDER BY id",
                        (role,)).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="база-образец; по умолчанию живая (копируется)")
    ap.add_argument("--role", default="PROTO", help="чью историю сворачивать в опыте")
    ap.add_argument("--break", dest="break_name",
                    choices=sorted(set(BREAKS) | {STALE_ARCHIVE_BREAK}), default=None)
    a = ap.parse_args()
    role = a.role.upper()
    src = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-fold-"))
    db = tmp / "copy.db"
    mezo_stand.snapshot_db(src, db)  # карточка #505/#624: согласованная копия, не shutil.copyfile
    # ⚡ КАРТОЧКА #613: испытуемые (инструмент, шаг схемы, save-phoenix.py в случае ⑧) зовём
    # средой СТЕНДА, не средой вызывающего — иначе MEZO_CONTAINER вызывающего доедет до них.
    stand_env = mezo_stand.stand_env(tmp)
    live_fp = file_fingerprint(src)
    tool = TOOL; broken_copy = None
    if a.break_name and a.break_name in BREAKS:
        was, became = BREAKS[a.break_name]
        text = TOOL.read_text(encoding="utf-8")
        if was not in text:
            print(f"⛔ порчу «{a.break_name}» навести не удалось: образец не найден в коде"); return 2
        broken_copy = HERE / f"memory-history-fold.__break_{a.break_name}__.py"
        broken_copy.write_text(text.replace(was, became, 1), encoding="utf-8")
        tool = broken_copy
        print(f"⚠️ ПОРЧА «{a.break_name}» ВЗВЕДЕНА — ждём красного в случаях ③ · ③-в · ③-г (одно свойство с двух сторон)\n")
    elif a.break_name == STALE_ARCHIVE_BREAK:
        print(f"⚠️ ПОРЧА «{STALE_ARCHIVE_BREAK}» ВЗВЕДЕНА — архив роли на копии НЕ чищен, "
              f"ждём красного в ③-в · ③-г · ③-д · ④ · ⑤ (архив/история целиком, а не то, "
              f"что унесла ЭТА свёртка)\n")
    try:
        # шаг схемы на копии
        r = subprocess.run([sys.executable, "-B", str(MIGR), "--db", str(db)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=stand_env)
        conn = sqlite3.connect(str(db))
        tables = {x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        in_journal = conn.execute("SELECT count(*) FROM schema_migrations WHERE version='20260905-phoenix-history-archive'").fetchone()[0]
        # ⚖️ шаг идемпотентен: на копии живой базы, где он уже сведён (07:08 UTC), он отвечает
        #    «уже сведено» — это тоже зелёное; красное — если таблиц нет или журнал молчит
        case("⓪ шаг схемы сведён на копии (врезан сейчас или уже был) и записан в журнал",
             r.returncode == 0 and ("ВРЕЗАНО" in r.stdout or "уже сведено" in r.stdout)
             and {"role_rebirths", "phoenix_history_archive"} <= tables and in_journal == 1,
             r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
        n_reb = conn.execute("SELECT count(*) FROM role_rebirths").fetchone()[0]
        case("⓪-бис отметки пересоздания засеяны (18, у 9 ролей, у каждой источник)",
             n_reb == 18 and conn.execute("SELECT count(DISTINCT role) FROM role_rebirths").fetchone()[0] == 9
             and conn.execute("SELECT count(*) FROM role_rebirths WHERE source NOT LIKE 'transcript:%'").fetchone()[0] == 0,
             f"отметок {n_reb}")
        # ⚡ КАРТОЧКА #628: копия живой базы несёт РЕАЛЬНЫЙ архив роли (save-phoenix.py —
        # по счёту версий, прежние прогоны fold — по возрасту): у PROTO 73 версии ДО этого
        # опыта. «archived» ниже обязан быть тем, что унесла ИМЕННО эта свёртка — чистим
        # архив роли на СВОЕЙ КОПИИ (живую не трогаем ни байтом, это отдельный файл), тогда
        # ③-в/③-г/③-д/④/⑤ судят свойство, для которого написаны, а не состояние снимка.
        # Не отдельный случай (счёт «19 из 19» карточки #628 — про сами свойства свёртки):
        # печатается фактом, а под порчей --break stale-archive пропускается нарочно.
        n_stale = conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=?", (role,)).fetchone()[0]
        if a.break_name != STALE_ARCHIVE_BREAK:
            if n_stale:
                conn.execute("DELETE FROM phoenix_history_archive WHERE role=?", (role,))
                conn.commit()
            print(f"ℹ️ архив роли {role} на КОПИИ очищен перед опытом (было чужого архива: {n_stale})")
        else:
            print(f"ℹ️ порча «{STALE_ARCHIVE_BREAK}»: архив роли НЕ чищен (в нём {n_stale} версий чужого архива)")
        history_before = history_snapshot(conn, role)
        threshold = conn.execute("SELECT datetime('now','-7 days')").fetchone()[0]
        rebirth_marks = [r[0] for r in conn.execute("SELECT at FROM role_rebirths WHERE role=? ORDER BY at", (role,))]
        fp_before = file_fingerprint(db)

        # ① холостой прогон — ни байта
        code, output = run(["--role", role, "--dry-run"], db=db, tool=tool, stand_env=stand_env)
        case("① --dry-run считает и не пишет ни байта (отпечаток файла базы совпал)",
             code == 0 and "ВХОЛОСТУЮ" in output and file_fingerprint(db) == fp_before, output.strip().splitlines()[-1] if output.strip() else "")
        # ② чужая рука — отказ, база не тронута
        other_role = "TAXO" if role != "TAXO" else "CORE"
        code, output = run(["--role", other_role], env_role=role, db=db, tool=tool, stand_env=stand_env)
        case("② чужую историю не сворачивает: отказ кодом 2, база не тронута",
             code == 2 and "ТОЛЬКО СВОЮ" in output and file_fingerprint(db) == fp_before, output.strip().splitlines()[-1])
        code, output = run(["--role", role], db=db, tool=tool, stand_env=stand_env)
        case("②-бис без MEZO_ROLE перенос отказан кодом 2", code == 2 and "ЧЬЯ РУКА" in output)

        # свёртка своей
        code, output = run(["--role", role], env_role=role, db=db, tool=tool, stand_env=stand_env)
        conn = sqlite3.connect(str(db))
        remaining = history_snapshot(conn, role)
        remaining_ids = {r[0] for r in remaining}
        archived = conn.execute("SELECT id, section, saved_at, body FROM phoenix_history_archive WHERE role=? ORDER BY id",
                           (role,)).fetchall()
        case(f"③-контроль свёртка прошла кодом 0 и что-то унесла ({len(archived)} версий)", code == 0 and len(archived) > 0,
             output.strip().splitlines()[-2] if len(output.strip().splitlines()) > 1 else output)
        # свойства ОСТАВШЕГОСЯ — другое определение предмета
        young = [r for r in history_before if r[2] >= threshold]
        case("③-а каждая версия моложе 7 суток на месте", all(r[0] in remaining_ids for r in young), f"молодых {len(young)}")
        sections = {}
        for r in history_before: sections.setdefault(r[1], []).append(r)
        latest = [max(vs, key=lambda r: (r[2], r[0])) for vs in sections.values()]
        case("③-б у каждого раздела последняя по часу версия на месте", all(r[0] in remaining_ids for r in latest))
        before_marks = []
        for vs in sections.values():
            for t in rebirth_marks:
                b = [r for r in vs if r[2] < t]
                if b: before_marks.append(max(b, key=lambda r: (r[2], r[0])))
        case(f"③ перед КАЖДОЙ отметкой пересоздания последняя версия на месте ({len(before_marks)} шт.)",
             bool(before_marks) and all(r[0] in remaining_ids for r in before_marks),
             "" if all(r[0] in remaining_ids for r in before_marks) else f"унесены: {[r[0] for r in before_marks if r[0] not in remaining_ids]}")
        kept = {r[0] for r in young} | {r[0] for r in latest} | {r[0] for r in before_marks}
        case("③-в всё унесённое — старше порога и не из хранимых",
             all(r[2] < threshold and r[0] not in kept for r in archived))
        case("③-г унесено РОВНО то, что старое и не хранимое (ничего не забыто)",
             {r[0] for r in history_before if r[2] < threshold and r[0] not in kept} == {r[0] for r in archived})
        union_rows = sorted(remaining + archived)
        case("③-д объединение история ∪ архив = прежняя история знак в знак", union_rows == sorted(history_before))
        case("③-е в летописи запись fold_history с числом унесённого",
             conn.execute("SELECT count(*) FROM audit_log WHERE action='fold_history' AND target=?",
                          (f"phoenix_history.{role}",)).fetchone()[0] == 1)
        # ④ возврат
        code, output = run(["--role", role, "--unfold"], env_role=role, db=db, tool=tool, stand_env=stand_env)
        conn = sqlite3.connect(str(db))
        case("④ --unfold возвращает историю знак в знак под прежними номерами, архив пуст",
             code == 0 and history_snapshot(conn, role) == history_before
             and conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=?", (role,)).fetchone()[0] == 0,
             output.strip().splitlines()[-1])
        # ⑤ повторная свёртка после возврата даёт то же множество (идемпотентность правила)
        code, output = run(["--role", role], env_role=role, db=db, tool=tool, stand_env=stand_env)
        conn = sqlite3.connect(str(db))
        archived2 = {r[0] for r in conn.execute("SELECT id FROM phoenix_history_archive WHERE role=?", (role,))}
        case("⑤ повторная свёртка уносит то же множество версий", archived2 == {r[0] for r in archived})
        code, output = run(["--role", role], env_role=role, db=db, tool=tool, stand_env=stand_env)
        case("⑤-бис третий вызов: «уносить нечего», код 0", code == 0 and "уносить нечего" in output)
        # ⑥ роль без отметок: предупреждение вслух, «перед пересозданием» не хранится
        conn.execute("DELETE FROM role_rebirths WHERE role=?", (role,)); conn.commit()
        code, output = run(["--role", role, "--dry-run"], db=db, tool=tool, stand_env=stand_env)
        case("⑥ у роли без отметок пересоздания инструмент говорит это вслух", "ОТМЕТОК ПЕРЕСОЗДАНИЯ У РОЛИ НЕТ" in output)
        # ⑧ ЧИСТКА ПРИ СОХРАНЕНИИ — ПЕРЕНОС, НЕ УДАЛЕНИЕ (save-phoenix.py держит 10 + самую длинную
        #    на раздел; до 05.09 лишнее УДАЛЯЛОСЬ: из 2270 сохранений в истории оставалась 441 версия)
        save = mezo_paths.live_scripts() / "save-phoenix.py"
        conn = sqlite3.connect(str(db))
        total0 = conn.execute("SELECT (SELECT count(*) FROM phoenix_history)+(SELECT count(*) FROM phoenix_history_archive)").fetchone()[0]
        archived_save0 = conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=? AND rule LIKE 'save-phoenix%'", (role,)).fetchone()[0]
        body = conn.execute("SELECT body FROM phoenix WHERE role=? AND section='plan'", (role,)).fetchone()[0]
        f = tmp / "body.md"; codes = []
        # ⚡ КАРТОЧКА #613: та же среда стенда, что у run() — не os.environ вызывающего.
        env = dict(stand_env); env["MEZO_ROLE"] = role
        for i in range(13):
            f.write_text(body + f"\n\n<!-- проба приёмки {i}, копия базы -->", encoding="utf-8")
            r = subprocess.run([sys.executable, "-B", str(save), "--role", role, "--section", "plan", "--file", str(f),
                                "--db", str(db)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            codes.append(r.returncode)
        conn = sqlite3.connect(str(db))
        total1 = conn.execute("SELECT (SELECT count(*) FROM phoenix_history)+(SELECT count(*) FROM phoenix_history_archive)").fetchone()[0]
        in_history = {r[0] for r in conn.execute("SELECT id FROM phoenix_history WHERE role=? AND section='plan'", (role,))}
        from_save = conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=? AND rule LIKE 'save-phoenix%'", (role,)).fetchone()[0] - archived_save0
        # правило сохранения: 10 ПОСЛЕДНИХ по номеру + САМАЯ ДЛИННАЯ из всех (история ∪ архив) —
        # их и только их ждём в истории; 11 это или 10 — зависит от того, попала ли длинная в последние
        # ⚖️ считаем только то, что видело САМО сохранение: строки истории и то, что ОНО унесло;
        #    унесённое свёрткой (rule regl-538) сохранению не видно и в «самой длинной» не участвует
        union_save = conn.execute(
            "SELECT id, body_chars FROM phoenix_history WHERE role=? AND section='plan' UNION ALL "
            "SELECT id, body_chars FROM phoenix_history_archive WHERE role=? AND section='plan' "
            "AND rule LIKE 'save-phoenix%'", (role, role)).fetchall()
        latest10 = {i for i, _ in sorted(union_save, key=lambda x: -x[0])[:10]}
        longest = max(union_save, key=lambda x: (x[1], x[0]))[0]
        expected = latest10 | {longest}
        case("⑧ 13 сохранений раздела: в истории ровно 10 последних + самая длинная, лишнее ПЕРЕНЕСЕНО, потерь ноль",
             all(k == 0 for k in codes) and in_history == expected and total1 == total0 + 13 and from_save > 0,
             f"коды {set(codes)} · в истории {len(in_history)} (ждали {len(expected)}) · всего было {total0} стало {total1} · перенесено save-phoenix {from_save}")
        case("⑦ живая база не тронута приёмкой (отпечаток файла совпал)", file_fingerprint(src) == live_fp)
    finally:
        if broken_copy and broken_copy.exists(): broken_copy.unlink()
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(RESULTS); ok = sum(RESULTS)
    if a.break_name:
        red_count = n - ok
        print(f"\n{'✅ так и надо' if red_count else '⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ЗЕЛЁНОЕ'}: под порчей красных {red_count} из {n}")
        return 0 if red_count else 1
    print(f"\n{'✅ ПРИНЯТА' if ok == n else '🔴 НЕ ПРИНЯТА'} — случаев {n}, зелёных {ok}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
