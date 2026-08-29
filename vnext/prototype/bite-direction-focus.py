# -*- coding: utf-8 -*-
r"""ПРИЁМКА ступени А направления-фокуса — карточка #399 (слово владельца 29.08 14:39 UTC).

🎯 ПРЕДМЕТ: объявленное главное направление (ЕДИНСТВЕННЫЙ активный набор задач)
ограничивает взятие и заведение задач вне его — воротами инструмента, не дисциплиной.
Основание-замер 29.08: за 3 суток 71% новых карточек и 53% взятий — вне наборов,
при уже стоявших мягких механизмах (предупреждение при заведении, набор первым в списках).

Случаи:
  ① заведение БЕЗ набора при одном активном → карточка РОДИЛАСЬ ЗАМОРОЖЕННОЙ
    с условием разморозки в поле причины                                  РАЗЛИЧАЮЩИЙ
  ② встречный: заведение В набор → open, как прежде                       КОНТРОЛЬ
  ③ взятие карточки ВНЕ направления → ПРЕДУПРЕЖДЕНИЕ с живой долей,
    работа НЕ ломается (код 0)                                            РАЗЛИЧАЮЩИЙ
  ④ встречный: взятие карточки НАПРАВЛЕНИЯ → тихо                         КОНТРОЛЬ
  ⑤ лазейка --off-pool «причина» → событие в журнале, предупреждения нет  РАЗЛИЧАЮЩИЙ
  ⑥ встречный: --off-pool с ПУСТОЙ причиной → отказ                       КОНТРОЛЬ
  ⑦ граница: активных наборов ДВА → ворота НЕ судятся и говорят это
    вслух; заведение без набора рождает open (прежнее поведение)          КОНТРОЛЬ
  ⑧ перевод в in_progress вне направления → то же предупреждение          КОНТРОЛЬ
  ⑨ сводка роли при одном активном несёт строку НАПРАВЛЕНИЕ               КОНТРОЛЬ

⛔ Живой базы не касается: копия в песочнице; в копии второй активный набор ставится
на паузу, чтобы направление стало единственным (на живой это решает слово владельца).
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

СКРИПТЫ = mezo_paths.live_scripts()
BACKLOG = str(СКРИПТЫ / "backlog.py")
BRIEF = str(СКРИПТЫ / "role-brief.py")
LIVE_DB = mezo_paths.live_db()
НАПР = "TRACK-ROLES-REMEMBER"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run(tool, db, *args):
    env = dict(os.environ, MEZO_ROLE="PROTO", MEZO_LEASE_TEST="")
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    ok = True
    stand = mezo_stand.new("bite-focus-")
    db = stand / "copy.db"
    shutil.copy2(LIVE_DB, db)
    con = sqlite3.connect(db)
    # Направление в копии — ЕДИНСТВЕННОЕ: прочие активные ставятся на паузу.
    con.execute("UPDATE tracks SET status='paused' WHERE status='active' AND track_id<>?",
                (НАПР,))
    con.commit()
    con.close()

    # ① заведение без набора → карточка замороженная, условие разморозки в причине.
    rc, out = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                  "--title", "стендовая заявка вне направления",
                  "--body", "тело стендовой заявки для приёмки ступени А",
                  "--done-when", "стендовый критерий: не судится")
    bid1 = out.split("backlog #")[1].split(" ")[0] if "backlog #" in out else None
    con = sqlite3.connect(db)
    st, reason = con.execute("SELECT status, blocked_reason FROM backlog WHERE id=?",
                             (bid1,)).fetchone() if bid1 else (None, None)
    con.close()
    ok &= case("① заведение БЕЗ набора → карточка РОДИЛАСЬ ЗАМОРОЖЕННОЙ с условием",
               rc == 0 and st == "frozen" and "ЗАМОРОЖЕННОЙ" in out
               and reason and "разморозка" in reason,
               f"статус {st}, условие: {str(reason)[:70]}", differ=True)

    # ② встречный: заведение В набор → open.
    rc, out = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                  "--track", НАПР,
                  "--title", "стендовая карточка направления",
                  "--body", "тело стендовой карточки направления",
                  "--done-when", "стендовый критерий: не судится")
    bid2 = out.split("backlog #")[1].split(" ")[0] if "backlog #" in out else None
    con = sqlite3.connect(db)
    st2 = con.execute("SELECT status FROM backlog WHERE id=?", (bid2,)).fetchone()[0]
    con.close()
    ok &= case("② встречный: заведение В набор → open, как прежде",
               rc == 0 and st2 == "open" and "ЗАМОРОЖ" not in out,
               f"статус {st2} — направление не наказывает своих")

    # ③ взятие карточки вне направления (замороженную ①) → предупреждение с долей, код 0.
    rc, out = run(BACKLOG, db, "claim", bid1, "--actor", "PROTO",
                  "--note", "стендовое взятие вне направления")
    ok &= case("③ взятие ВНЕ направления → ПРЕДУПРЕЖДЕНИЕ с долей, работа не сломана",
               rc == 0 and "ВНЕ направления" in out and "из" in out and "ВЗЯТО В РАБОТУ" in out,
               "ступень А предупреждает и меряет, а не запрещает", differ=True)

    # ④ встречный: взятие карточки направления → тихо.
    rc, out = run(BACKLOG, db, "claim", bid2, "--actor", "PROTO",
                  "--note", "стендовое взятие в направлении")
    ok &= case("④ встречный: взятие карточки НАПРАВЛЕНИЯ → без предупреждения",
               rc == 0 and "ВНЕ направления" not in out,
               "тишина на своём — предупреждение не выгорает")

    # ⑤ лазейка: причина вслух → событие off_pool, предупреждения нет.
    rc, out = run(BACKLOG, db, "claim", bid1, "--actor", "PROTO",
                  "--note", "стендовое взятие с причиной",
                  "--off-pool", "слово владельца: стендовая причина")
    con = sqlite3.connect(db)
    ev = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                     "AND event_type='off_pool'", (bid1,)).fetchone()[0]
    con.close()
    ok &= case("⑤ лазейка --off-pool с причиной → событие в журнале, предупреждения нет",
               rc == 0 and ev == 1 and "причиной вслух" in out and "⚠️ карточка ВНЕ" not in out,
               f"событий off_pool: {ev} — причина видна задним числом поимённо", differ=True)

    # ⑥ встречный: пустая причина → отказ.
    rc, out = run(BACKLOG, db, "claim", bid1, "--actor", "PROTO",
                  "--note", "стендовое взятие", "--off-pool", "  ")
    ok &= case("⑥ встречный: --off-pool с ПУСТОЙ причиной → отказ",
               rc != 0 and "ПРИЧИНУ" in out,
               "пустая причина неотличима от её отсутствия")

    # ⑦ граница: активных ДВА → ворота молчат и говорят это вслух.
    con = sqlite3.connect(db)
    con.execute("UPDATE tracks SET status='active' WHERE track_id='TRACK-NEWUX'")
    con.commit()
    con.close()
    rc, out = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                  "--title", "стендовая заявка при двух активных",
                  "--body", "тело стендовой заявки при двух активных",
                  "--done-when", "стендовый критерий: не судится")
    bid3 = out.split("backlog #")[1].split(" ")[0] if "backlog #" in out else None
    con = sqlite3.connect(db)
    st3 = con.execute("SELECT status FROM backlog WHERE id=?", (bid3,)).fetchone()[0]
    con.close()
    rc2, out2 = run(BACKLOG, db, "claim", bid3, "--actor", "PROTO",
                    "--note", "стендовое взятие при двух активных")
    ok &= case("⑦ граница: активных ДВА → фокус не судится, и это сказано вслух",
               st3 == "open" and "фокус не судится" in out
               and rc2 == 0 and "ВНЕ направления" not in out2,
               "судить «вне направления» при двух направлениях значит красить всё")
    con = sqlite3.connect(db)
    con.execute("UPDATE tracks SET status='paused' WHERE track_id='TRACK-NEWUX'")
    con.commit()
    con.close()

    # ⑧ перевод в in_progress вне направления → предупреждение.
    con = sqlite3.connect(db)
    con.execute("UPDATE backlog SET status='open' WHERE id=?", (bid3,))
    con.commit()
    con.close()
    rc, out = run(BACKLOG, db, "status", bid3, "in_progress", "--actor", "PROTO",
                  "--note", "стендовый перевод в работу")
    ok &= case("⑧ перевод в in_progress вне направления → то же предупреждение",
               rc == 0 and "ВНЕ направления" in out,
               "второй вход в работу закрыт тем же предупреждением, что claim")

    # ⑨ сводка роли при одном активном несёт строку направления.
    rc, out = run(BRIEF, db, "--role", "PROTO")
    ok &= case("⑨ сводка роли называет НАПРАВЛЕНИЕ первой строкой секции набора",
               rc == 0 and "НАПРАВЛЕНИЕ КОНТУРА" in out and НАПР in out,
               "роль узнаёт направление из живой сводки, а не из чьей-то памяти")

    print()
    print(f"{'✅ СТУПЕНЬ А НАПРАВЛЕНИЯ-ФОКУСА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
