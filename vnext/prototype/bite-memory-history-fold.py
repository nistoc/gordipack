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

🎯 ПОСЕВ НЕДОСТАЮЩЕГО МАТЕРИАЛА (карточка #634): в контуре, собранном из пакета, у роли история
версий памяти бедна — случаи ① · ② · ③-контроль · ③ · ③-е меряют свойства, которым не на чем
сработать (нечего уносить в архив, не перед чем стоять «последней», у чужой роли ни одной версии
вообще). Приёмка САМА досевает недостающее в СВОЮ копию — только когда материала не хватает
(на живой базе материала уже достаточно, посев не срабатывает, строки «засеяно» нет). Роли,
чьё имя ищет случай ②, — по одной версии через save-phoenix.py (дата не важна, только НЕ ПУСТО).
Своей роли (--role) — если нечему уехать в архив или не перед чем стоять «последней перед
пересозданием» — две версии ПРЯМОЙ ВСТАВКОЙ в копию (задним числом через save-phoenix.py не
встать — он всегда штампует «сейчас»): младшая X2 старше порога и обеих отметок, но новее X1 —
она становится «последней перед КАЖДОЙ отметкой»; X1 ничем не защищена — уезжает в архив. Отметки
пересоздания (role_rebirths) НЕ придумываются: если их у роли нет вовсе — случай ③ печатает
«⚪ ③ не поставлен: …», отдельный счёт, и итог не «ПРИНЯТА», пока счёт больше нуля.

🎯 ПОРЧА (--break seed-off, карточка #634): посев ВЫКЛЮЧЕН — там, где материала не хватало бы,
он и остаётся пустым. Проваливаются РОВНО случаи, для которых посев был нужен (① · ② ·
③-контроль · ③-е, и ③, если у роли есть отметки пересоздания — каждый своей проверкой, не общей
меткой), прочие ведут себя как обычно (в т.ч. случай ⑧, у которого свой отдельный засев на
save-phoenix.py, не задет — другой материал). Не патчит инструмент memory-history-fold.py (как
--break rebirth) и не трогает архив-снимок (как --break stale-archive) — отдельный, третий
механизм порчи.

    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py
    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py --break rebirth
    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py --break stale-archive
    python <КОНТУР>/vnext-tools/bite-memory-history-fold.py --break seed-off
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
# ⚡ КАРТОЧКА #634: третий механизм порчи — не патчит инструмент, не трогает архив-снимок,
# а выключает ПОСЕВ недостающего материала (ниже, блок «ПОСЕВ НЕДОСТАЮЩЕГО МАТЕРИАЛА» в main()).
SEED_OFF_BREAK = "seed-off"
RESULTS = []
NOT_STAGED = []  # карточка #634: случаи, которые честно не поставить (без выдуманных отметок)


def case(title, ok, detail=""):
    RESULTS.append(ok)
    print(("✅ " if ok else "🔴 ") + title + (f"\n   {detail}" if detail else ""))


def would_archive(history_rows, marks, threshold):
    """Мимика посчитать() инструмента (memory-history-fold.py) — ТОЛЬКО чтобы решить, хватает
    ли материала для посева (карточка #634). Проверку случаев это не подменяет: она как и
    раньше считает по СВОЕЙ копии этой же логики (③-а..③-е ниже) — здесь только предсказание.

    Возвращает (уедет, перед_отметками) — списки строк history_rows тем же порядком полей
    (id, section, saved_at, body).
    """
    by_section = {}
    for r in history_rows:
        by_section.setdefault(r[1], []).append(r)
    kept = set()
    before_marks = []
    for _section, vs in by_section.items():
        vs = sorted(vs, key=lambda r: (r[2], r[0]))
        kept.add(vs[-1][0])  # последняя вообще
        for t in marks:
            before = [v for v in vs if v[2] < t]
            if before:
                last = max(before, key=lambda r: (r[2], r[0]))
                kept.add(last[0])
                before_marks.append(last)
    would_leave = [r for r in history_rows if r[2] < threshold and r[0] not in kept]
    return would_leave, before_marks


def pick_section(conn, role, history_rows):
    """Раздел для посева: раздел САМОЙ НОВОЙ версии роли, если история уже есть; иначе —
    существующий раздел роли в phoenix; иначе 'identity' (реальное имя раздела схемы)."""
    if history_rows:
        return sorted(history_rows, key=lambda r: (r[2], r[0]))[-1][1]
    row = conn.execute("SELECT section FROM phoenix WHERE role=? ORDER BY section LIMIT 1", (role,)).fetchone()
    return row[0] if row else "identity"


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
                    choices=sorted(set(BREAKS) | {STALE_ARCHIVE_BREAK, SEED_OFF_BREAK}), default=None)
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
    save = mezo_paths.live_scripts() / "save-phoenix.py"  # нужен и посеву (ниже), и случаю ⑧
    seed_enabled = a.break_name != SEED_OFF_BREAK
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
    elif a.break_name == SEED_OFF_BREAK:
        print(f"⚠️ ПОРЧА «{SEED_OFF_BREAK}» ВЗВЕДЕНА — посев недостающего материала (карточка #634) "
              f"ВЫКЛЮЧЕН, ждём провала случаев ① · ② · ③-контроль · ③-е (и ③, если у роли есть "
              f"отметки пересоздания) — каждый своей проверкой, не общей меткой\n")
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

        # ⚡ КАРТОЧКА #634: ПОСЕВ НЕДОСТАЮЩЕГО МАТЕРИАЛА — ДО history_before/fp_before, чтобы
        # посеянное вошло в базовый отсчёт (как и очистка архива выше), а не в «то, что сделала
        # сама свёртка». На живой базе материала уже хватает — ветки ниже не сработают, строки
        # «засеяно» не будет (проверено прогоном на копии живой базы, PROTO 2026-09-14).
        other_role = "TAXO" if role != "TAXO" else "CORE"
        threshold = conn.execute("SELECT datetime('now','-7 days')").fetchone()[0]
        history_now = history_snapshot(conn, role)
        marks_now = [r[0] for r in conn.execute("SELECT at FROM role_rebirths WHERE role=? ORDER BY at", (role,))]
        would_leave_now, before_marks_now = would_archive(history_now, marks_now, threshold)
        role_short = (not would_leave_now) or (marks_now and not before_marks_now)
        if role_short and seed_enabled:
            section = pick_section(conn, role, history_now)
            boundary = min([threshold] + marks_now) if marks_now else threshold
            x1_at, x2_at = conn.execute("SELECT datetime(?, '-4 days'), datetime(?, '-2 days')",
                                        (boundary, boundary)).fetchone()
            body1 = f"# {role}\n\nсемя материала истории (карточка #634), версия X1 — старше порога и " \
                    f"обеих отметок, ничем не защищена, должна уехать в архив.\n"
            body2 = f"# {role}\n\nсемя материала истории (карточка #634), версия X2 — старше порога и " \
                    f"обеих отметок, но новее X1: становится «последней перед КАЖДОЙ отметкой».\n"
            conn.execute("INSERT INTO phoenix_history(role, section, body, body_chars, saved_at, actor, "
                        "reason, prev_chars) VALUES (?,?,?,?,?,?,?,?)",
                        (role, section, body1, len(body1), x1_at, "bite-memory-history-fold", "seed", None))
            conn.execute("INSERT INTO phoenix_history(role, section, body, body_chars, saved_at, actor, "
                        "reason, prev_chars) VALUES (?,?,?,?,?,?,?,?)",
                        (role, section, body2, len(body2), x2_at, "bite-memory-history-fold", "seed", None))
            conn.commit()
            print(f"ℹ️ засеяно в копию: роли {role} добавлены 2 версии раздела {section!r} прямой "
                  f"вставкой — X1 {x1_at}, X2 {x2_at} (обе старше порога {threshold} и всех отметок "
                  f"пересоздания); в копии не хватало материала для случаев ①/③-контроль/③-е"
                  + ("/③" if marks_now else ""))
        elif role_short and not seed_enabled:
            print(f"⚠️ порча «{SEED_OFF_BREAK}»: посев роли {role} пропущен нарочно — материала "
                  f"в копии не хватает (уехало бы {len(would_leave_now)}, перед отметками "
                  f"{len(before_marks_now)})")

        other_has = (conn.execute("SELECT 1 FROM phoenix_history WHERE role=? LIMIT 1", (other_role,)).fetchone()
                     or conn.execute("SELECT 1 FROM phoenix_history_archive WHERE role=? LIMIT 1",
                                     (other_role,)).fetchone())
        if not other_has and seed_enabled:
            other_section = pick_section(conn, other_role, [])
            seed_other = tmp / f"seed-{other_role}.md"
            seed_other.write_text(f"# {other_role}\n\nсемя случая ② (карточка #634): роли нужна хоть "
                                  f"одна версия истории, чтобы приёмка дошла до проверки «только "
                                  f"свою» — дата не важна.\n", encoding="utf-8")
            env_other = dict(stand_env); env_other["MEZO_ROLE"] = other_role
            rseed_other = subprocess.run([sys.executable, "-B", str(save), "--role", other_role, "--section",
                                          other_section, "--file", str(seed_other), "--db", str(db)],
                                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                                         env=env_other)
            conn = sqlite3.connect(str(db))
            print(f"ℹ️ засеяно в копию: роли {other_role} добавлена версия раздела {other_section!r} "
                  f"через save-phoenix.py (код {rseed_other.returncode}) — в копии не было ни одной "
                  f"версии этой роли для случая ②")
        elif not other_has and not seed_enabled:
            print(f"⚠️ порча «{SEED_OFF_BREAK}»: посев роли {other_role} пропущен нарочно — версий "
                  f"в копии нет ни одной")

        history_before = history_snapshot(conn, role)
        rebirth_marks = [r[0] for r in conn.execute("SELECT at FROM role_rebirths WHERE role=? ORDER BY at", (role,))]
        fp_before = file_fingerprint(db)

        # ① холостой прогон — ни байта
        code, output = run(["--role", role, "--dry-run"], db=db, tool=tool, stand_env=stand_env)
        case("① --dry-run считает и не пишет ни байта (отпечаток файла базы совпал)",
             code == 0 and "ВХОЛОСТУЮ" in output and file_fingerprint(db) == fp_before, output.strip().splitlines()[-1] if output.strip() else "")
        # ② чужая рука — отказ, база не тронута
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
        if not rebirth_marks:
            # ⚡ КАРТОЧКА #634: отметки пересоздания (role_rebirths) НЕ выдумываются посевом —
            # без них «перед КАЖДОЙ отметкой» испытывать не на чем, это не провал инструмента.
            print(f"⚪ ③ не поставлен: у роли {role} в копии базы нет ни одной отметки "
                  f"пересоздания (role_rebirths) — подделывать отметку нельзя, «перед каждой» "
                  f"испытывать не на чем")
            NOT_STAGED.append("③")
        else:
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
        # (save — уже определён выше, до посева: он нужен и посеву роли other_role, и здесь)
        conn = sqlite3.connect(str(db))
        # ⚡ КАРТОЧКА #628: в свежем контуре у роли может не быть раздела plan (а то и вовсе ни
        # одного раздела) — .fetchone()[0] на пустом результате давал TypeError. Раздел для
        # случая выбираем ДО замера total0/archived_save0, чтобы возможный засев вошёл в базовый
        # отсчёт, а не в «13» сохранений цикла ниже.
        section = "plan"
        row = conn.execute("SELECT body FROM phoenix WHERE role=? AND section='plan'", (role,)).fetchone()
        if row is not None:
            body = row[0]
        else:
            other = conn.execute("SELECT section, body FROM phoenix WHERE role=? ORDER BY section LIMIT 1",
                                 (role,)).fetchone()
            if other is not None:
                section, body = other
                print(f"ℹ️ ⑧: у роли {role} в копии базы нет раздела plan — веду случай на разделе {section!r}")
            else:
                seed = tmp / "seed-8.md"
                seed.write_text(f"# {role}\n\nсемя случая ⑧: у роли в копии базы не было ни одного раздела.\n",
                                encoding="utf-8")
                env_seed = dict(stand_env); env_seed["MEZO_ROLE"] = role
                rseed = subprocess.run([sys.executable, "-B", str(save), "--role", role, "--section", section,
                                        "--file", str(seed), "--db", str(db)], capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", env=env_seed)
                conn = sqlite3.connect(str(db))
                row = conn.execute("SELECT body FROM phoenix WHERE role=? AND section=?", (role, section)).fetchone()
                if rseed.returncode == 0 and row is not None:
                    body = row[0]
                    print(f"ℹ️ ⑧: у роли {role} в копии базы не было ни одного раздела — засеян {section!r} "
                          f"первым сохранением (код {rseed.returncode})")
                else:
                    body = None
        if body is None:
            print(f"⚪ ⑧ пропущен: у роли {role} в копии базы нет ни одного раздела — переносить нечего")
            RESULTS.append(False)
        else:
            total0 = conn.execute("SELECT (SELECT count(*) FROM phoenix_history)+(SELECT count(*) FROM phoenix_history_archive)").fetchone()[0]
            archived_save0 = conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=? AND rule LIKE 'save-phoenix%'", (role,)).fetchone()[0]
            f = tmp / "body.md"; codes = []
            # ⚡ КАРТОЧКА #613: та же среда стенда, что у run() — не os.environ вызывающего.
            env = dict(stand_env); env["MEZO_ROLE"] = role
            for i in range(13):
                f.write_text(body + f"\n\n<!-- проба приёмки {i}, копия базы -->", encoding="utf-8")
                r = subprocess.run([sys.executable, "-B", str(save), "--role", role, "--section", section, "--file", str(f),
                                    "--db", str(db)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
                codes.append(r.returncode)
            conn = sqlite3.connect(str(db))
            total1 = conn.execute("SELECT (SELECT count(*) FROM phoenix_history)+(SELECT count(*) FROM phoenix_history_archive)").fetchone()[0]
            in_history = {r[0] for r in conn.execute("SELECT id FROM phoenix_history WHERE role=? AND section=?", (role, section))}
            from_save = conn.execute("SELECT count(*) FROM phoenix_history_archive WHERE role=? AND rule LIKE 'save-phoenix%'", (role,)).fetchone()[0] - archived_save0
            # правило сохранения: 10 ПОСЛЕДНИХ по номеру + САМАЯ ДЛИННАЯ из всех (история ∪ архив) —
            # их и только их ждём в истории; 11 это или 10 — зависит от того, попала ли длинная в последние
            # ⚖️ считаем только то, что видело САМО сохранение: строки истории и то, что ОНО унесло;
            #    унесённое свёрткой (rule regl-538) сохранению не видно и в «самой длинной» не участвует
            union_save = conn.execute(
                "SELECT id, body_chars FROM phoenix_history WHERE role=? AND section=? UNION ALL "
                "SELECT id, body_chars FROM phoenix_history_archive WHERE role=? AND section=? "
                "AND rule LIKE 'save-phoenix%'", (role, section, role, section)).fetchall()
            latest10 = {i for i, _ in sorted(union_save, key=lambda x: -x[0])[:10]}
            longest = max(union_save, key=lambda x: (x[1], x[0]))[0]
            expected = latest10 | {longest}
            case("⑧ 13 сохранений раздела: в истории ровно 10 последних + самая длинная, лишнее ПЕРЕНЕСЕНО, потерь ноль",
                 all(k == 0 for k in codes) and in_history == expected and total1 == total0 + 13 and from_save > 0,
                 f"раздел {section!r} · коды {set(codes)} · в истории {len(in_history)} (ждали {len(expected)}) · всего было {total0} стало {total1} · перенесено save-phoenix {from_save}")
        case("⑦ живая база не тронута приёмкой (отпечаток файла совпал)", file_fingerprint(src) == live_fp)
    finally:
        if broken_copy and broken_copy.exists(): broken_copy.unlink()
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(RESULTS); ok = sum(RESULTS)
    staged_n = len(NOT_STAGED)
    if a.break_name:
        red_count = n - ok
        print(f"\n{'✅ так и надо' if red_count else '⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ЗЕЛЁНОЕ'}: под порчей красных {red_count} из {n}"
              + (f" · не поставлено {staged_n} ({', '.join(NOT_STAGED)})" if staged_n else ""))
        return 0 if red_count else 1
    if staged_n:
        # ⚡ КАРТОЧКА #634: итог НЕ «ПРИНЯТА», пока хоть один случай честно не поставлен.
        print(f"\n🔴 НЕ ПРИНЯТА — случаев {n}, пройденных {ok}, НЕ ПОСТАВЛЕНО {staged_n} "
              f"({', '.join(NOT_STAGED)})")
        return 1
    print(f"\n{'✅ ПРИНЯТА' if ok == n else '🔴 НЕ ПРИНЯТА'} — случаев {n}, зелёных {ok}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
