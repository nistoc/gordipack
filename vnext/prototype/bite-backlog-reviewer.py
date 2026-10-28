# -*- coding: utf-8 -*-
"""bite-backlog-reviewer.py — приёмка: `backlog.py show` и `queue` печатают приёмщика, история его
хранит (issue #41 пакета, от контура-потребителя).

ЗАЧЕМ. Поле `reviewer` карточки пишет только `status … --reviewer X`, а читала его прежде одна
подсказка при сдаче. `show` поля не выбирал и строки о приёмщике не печатал вовсе: роль прочла
молчание как «приёмщика нет» и позвала принять другую руку, хотя приёмщик был назначен. `queue`
приёмщика тоже не печатал, а событие смены статуса имени не хранило.

Случаи:
  ① show карточки, сданной с --reviewer, — строка «🫱 приёмщик: <имя>», ровно одна
  ② ВСТРЕЧНЫЙ: show карточки без приёмщика — «🫱 приёмщик: не назначен», ровно одна: молчание о
     пустом поле неотличимо от «поля нет»
  ③ queue: у сданной с приёмщиком — его имя в её строке
  ④ ВСТРЕЧНЫЙ: queue у сданной без приёмщика — «приёмщик: не назначен» в её строке
  ⑤ смена приёмщика: show называет нового; первое событие reviewer_set — первый приёмщик,
     последнее — новый с «прежде: <первый>»
  ⑥ ВСТРЕЧНЫЙ к ⑤: тело события смены статуса — ровно --note, имени приёмщика в нём нет; тот же
     приёмщик повторно нового события не пишет (двух событий подряд с одним именем нет)
  ⑦ queue --role <приёмщик>: его карточка первой и помечена 👉, помечена ровно одна, строка
     «первыми — где приёмщик ты (<роль>): 1»
  ⑧ queue --role в нижнем регистре — то же, что ⑦
  ⑨ ВСТРЕЧНЫЙ к ⑦: без --role — порядок по часу сдачи и 👉 нет; --role прежнего приёмщика — «: 0»
     и 👉 нет (считается нынешний приёмщик, а не любой из истории); приёмщик-правило словами
     («любая, не писавшая правку») своим не считается
  ⑩ холостой прогон status --dry-run --reviewer — ни поля, ни событий не прибавилось

Нарочные поломки (--break), каждая на своей копии backlog.py:
  show-silent ............ show печатает приёмщика только назначенного         → ②
  queue-no-reviewer ...... в строке очереди приёмщика нет                       → ③ ④
  no-reviewer-event ...... смена приёмщика события не пишет                     → ⑤
  reviewer-in-status-body  имя приёмщика дописано в тело события смены статуса  → ⑥
  event-on-repeat ........ тот же приёмщик повторно пишет событие               → ⑥
  no-mine-first .......... свои приёмки не поднимаются наверх                   → ⑦ ⑧
  case-sensitive ......... роль сравнивается с учётом регистра                  → ⑧

Живой базы не касается: подставная база (схема живой без строк, mezo_stand.empty_db) и свои
роли. Испытуемый backlog.py — по MEZO_SCRIPTS_ROOT (mezo_target), по умолчанию — установленный.
Запуск:  python <каталог приёмок>/bite-backlog-reviewer.py [--break <имя>]
"""
import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("backlog.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
sys.path.insert(0, str(mezo_paths.live_scripts()))
# mezo_stand — из каталога самой приёмки, той же версии пакета; вставка снимается сразу.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
sys.path.pop(0)

SHOW_LINE = "    print(f\"🫱 приёмщик: {(reviewer or '').strip() or 'не назначен'}\")\n"
QUEUE_PART = "f\"{age_text(age_hours)} · приёмщик: {(reviewer or '').strip() or 'не назначен'} · \"\n"
EVENT_IF = "    if reviewer_name and reviewer_name != previous_reviewer:\n"
STATUS_EVENT = "    _event(conn, a.id, a.actor, \"status_change\", note, old, a.new_status)\n"
MINE_SORT = "        rows = sorted(rows, key=lambda r: 0 if is_mine(r[6]) else 1)\n"
MINE_CMP = "        return bool(asker) and (reviewer or \"\").strip().upper() == asker\n"

BREAKS = {
    "show-silent": (
        [(SHOW_LINE, "    if reviewer:\n        print(f\"🫱 приёмщик: {reviewer}\")\n")], {"②"}),
    "queue-no-reviewer": (
        [(QUEUE_PART, "f\"{age_text(age_hours)} · \"\n")], {"③", "④"}),
    "no-reviewer-event": ([(EVENT_IF, "    if False:\n")], {"⑤"}),
    "reviewer-in-status-body": (
        [(STATUS_EVENT,
          "    _event(conn, a.id, a.actor, \"status_change\", "
          "(note + f\" · приёмщик: {reviewer_name}\") if reviewer_name else note, old, a.new_status)\n")],
        {"⑥"}),
    "event-on-repeat": ([(EVENT_IF, "    if reviewer_name:\n")], {"⑥"}),
    "no-mine-first": ([(MINE_SORT, "        rows = list(rows)\n")], {"⑦", "⑧"}),
    "case-sensitive": (
        [(MINE_CMP,
          "        return bool(asker) and (reviewer or \"\").strip() == "
          "(getattr(a, \"role\", None) or \"\").strip()\n")],
        {"⑧"}),
}

OWNER = "ZZOWNER"
REVIEWER = "ZZREVW"     # первый приёмщик карточки A
OTHER = "ZZOTHER"       # второй приёмщик карточки A — после смены
BY_RULE = "любая, не писавшая правку"

OK = FAIL = 0
RED = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: приёмщик в show, queue и истории карточки")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии backlog.py")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-backlog-reviewer-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.empty_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    mezo_stand.seed_roles(db, [OWNER, REVIEWER, OTHER])

    tool = mezo_stand.copy_tool(TARGET, stand / "tools")
    if a.break_name:
        text = tool.read_bytes().decode("utf-8").replace("\r\n", "\n")
        for old, new in BREAKS[a.break_name][0]:
            if text.count(old) != 1:
                print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                      f"(образец найден {text.count(old)} раз): {old.strip()[:70]}")
                return mezo_stand.finish(2)
            text = text.replace(old, new)
        # байтами: запись текстом на Windows сменила бы окончания строк копии
        tool.write_bytes(text.encode("utf-8"))
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    def run(*args):
        # --db — флаг всего инструмента, а не подкоманды: стоит ДО неё
        r = subprocess.run([sys.executable, str(tool), "--db", str(db), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def query(sql, params=()):
        c = sqlite3.connect(str(db))
        try:
            return c.execute(sql, params).fetchall()
        finally:
            c.close()

    def add(title):
        rc, out = run("add", "--role", OWNER, "--actor", OWNER, "--title", title,
                      "--body", "заведена приёмкой bite-backlog-reviewer.py на подставной базе",
                      "--done-when", "существует до конца прогона приёмки")
        rows = query("SELECT max(id) FROM backlog WHERE title = ?", (title,))
        if rc != 0 or not rows or rows[0][0] is None:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: карточка «{title}» не завелась (код {rc}):\n{out[-600:]}")
            sys.exit(mezo_stand.finish(2))
        return rows[0][0]

    def status(cid, new, *extra):
        rc, out = run("status", str(cid), new, "--actor", OWNER, *extra)
        if rc != 0:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: status {cid} {new} {' '.join(extra)} — код {rc}:\n{out[-600:]}")
            sys.exit(mezo_stand.finish(2))
        return out

    def reviewer_lines(out):
        return [ln for ln in out.splitlines() if ln.startswith("🫱 приёмщик:")]

    def queue_row(out, cid):
        return next((ln for ln in out.splitlines() if f"карточка #{cid} " in ln), "")

    def queue_order(out, ids):
        return [cid for ln in out.splitlines() for cid in ids if f"карточка #{cid} " in ln]

    card_a = add("ПРИЁМКА issue 41: A — приёмщик меняется")
    card_b = add("ПРИЁМКА issue 41: B — без приёмщика")
    card_c = add("ПРИЁМКА issue 41: C — приёмщик правилом словами")
    ids = [card_a, card_b, card_c]

    status(card_a, "in_review", "--reviewer", REVIEWER, "--note", "сдано: первый приёмщик")
    status(card_b, "in_review", "--note", "сдано без приёмщика")
    status(card_c, "in_review", "--reviewer", BY_RULE, "--note", "сдано правилу")

    # ① ② — show до смены
    _rc, out_a = run("show", str(card_a))
    lines_a = reviewer_lines(out_a)
    case("①", "show с приёмщиком — «🫱 приёмщик: <имя>», строка одна",
         lines_a == [f"🫱 приёмщик: {REVIEWER}"], f"строки: {lines_a or 'нет'}")
    _rc, out_b = run("show", str(card_b))
    lines_b = reviewer_lines(out_b)
    case("②", "ВСТРЕЧНЫЙ: show без приёмщика — «🫱 приёмщик: не назначен», строка одна",
         lines_b == ["🫱 приёмщик: не назначен"], f"строки: {lines_b or 'нет'}")

    # ③ ④ — queue до смены
    _rc, out_q = run("queue")
    row_a, row_b = queue_row(out_q, card_a), queue_row(out_q, card_b)
    case("③", "queue: у сданной с приёмщиком — его имя в её строке",
         f"приёмщик: {REVIEWER} ·" in row_a, row_a.strip()[:120] or "строки нет")
    case("④", "ВСТРЕЧНЫЙ: queue у сданной без приёмщика — «не назначен» в её строке",
         "приёмщик: не назначен ·" in row_b, row_b.strip()[:120] or "строки нет")

    # смена: тот же приёмщик повторно, затем другой
    status(card_a, "blocked", "--note", "вернули на доработку")
    status(card_a, "in_review", "--reviewer", REVIEWER, "--note", "сдано повторно тому же")
    status(card_a, "blocked", "--note", "вернули ещё раз")
    status(card_a, "in_review", "--reviewer", OTHER, "--note", "сдано другому приёмщику")

    # ⑤ ⑥ — show и история после смены
    _rc, out_a2 = run("show", str(card_a))
    lines_a2 = reviewer_lines(out_a2)
    set_events = [r[0] for r in query("SELECT body_md FROM backlog_events WHERE backlog_id = ? "
                                      "AND event_type = 'reviewer_set' ORDER BY id", (card_a,))]
    # ⑤ судит смену (первое и последнее событие), ⑥ — повтор; число событий ⑤ не судит, иначе
    # поломка повтора проваливала бы оба случая
    case("⑤", "смена приёмщика: show называет нового; первое событие — первый приёмщик, последнее — "
         "новый с «прежде»",
         lines_a2 == [f"🫱 приёмщик: {OTHER}"] and set_events[:1] == [f"приёмщик: {REVIEWER}"]
         and set_events[-1:] == [f"приёмщик: {OTHER} (прежде: {REVIEWER})"],
         f"show: {lines_a2 or 'нет'} · события: {set_events or 'нет'}")
    named = [m.group(1) for m in (re.match(r"приёмщик: (.+?)(?: \(прежде: .+\))?$", b)
                                  for b in set_events) if m]
    repeats = [n for n, prev in zip(named[1:], named) if n == prev]
    bodies = [r[0] for r in query("SELECT body_md FROM backlog_events WHERE backlog_id = ? "
                                  "AND event_type = 'status_change' ORDER BY id", (card_a,))]
    want_bodies = ["сдано: первый приёмщик", "вернули на доработку", "сдано повторно тому же",
                   "вернули ещё раз", "сдано другому приёмщику"]
    case("⑥", "ВСТРЕЧНЫЙ: тело смены статуса — ровно --note; повтор того же приёмщика события не пишет",
         bodies == want_bodies and len(named) == len(set_events) and not repeats,
         f"тела: {bodies} · имена событий reviewer_set: {named} · повторов подряд: {len(repeats)}")

    # час сдачи — свой у каждой карточки: иначе все сданы в одну секунду, и порядок очереди
    # решал бы случай, а не код (A сдана последней — после B и C)
    c = sqlite3.connect(str(db))
    for cid, when in ((card_b, "2026-01-01 00:02:00"), (card_c, "2026-01-01 00:03:00")):
        c.execute("UPDATE backlog_events SET at = ? WHERE backlog_id = ? AND to_status = 'in_review'",
                  (when, cid))
    for n, (eid,) in enumerate(c.execute("SELECT id FROM backlog_events WHERE backlog_id = ? AND "
                                         "to_status = 'in_review' ORDER BY id", (card_a,)).fetchall()):
        c.execute("UPDATE backlog_events SET at = ? WHERE id = ?", (f"2026-01-01 00:0{4 + n}:00", eid))
    c.commit()
    c.close()

    # ⑦ ⑧ — свои первыми
    _rc, out_mine = run("queue", "--role", OTHER)
    order_mine = queue_order(out_mine, ids)
    marked = [ln for ln in out_mine.splitlines() if "👉 карточка #" in ln]
    case("⑦", "queue --role <приёмщик>: его карточка первой и с 👉, помечена одна, «…: 1»",
         order_mine[:1] == [card_a] and len(marked) == 1 and f"карточка #{card_a} " in marked[0]
         and f"где приёмщик ты ({OTHER}): 1" in out_mine,
         f"порядок {order_mine} · помечено {len(marked)}")
    _rc, out_low = run("queue", "--role", OTHER.lower())
    order_low = queue_order(out_low, ids)
    marked_low = [ln for ln in out_low.splitlines() if "👉 карточка #" in ln]
    case("⑧", "queue --role в нижнем регистре — то же, что ⑦",
         order_low[:1] == [card_a] and len(marked_low) == 1
         and f"где приёмщик ты ({OTHER}): 1" in out_low,
         f"порядок {order_low} · помечено {len(marked_low)}")

    # ⑨ — встречный: без --role и с прежним приёмщиком
    _rc, out_plain = run("queue")
    order_plain = queue_order(out_plain, ids)
    _rc, out_old = run("queue", "--role", REVIEWER)
    case("⑨", "ВСТРЕЧНЫЙ: без --role — по часу сдачи и без 👉; прежний приёмщик — «: 0»; правило не своё",
         order_plain == [card_b, card_c, card_a] and "👉" not in out_plain
         and f"где приёмщик ты ({REVIEWER}): 0" in out_old and "👉 карточка" not in out_old
         and "👉 карточка" not in queue_row(out_mine, card_c),
         f"порядок без --role {order_plain} (ждали {[card_b, card_c, card_a]})")

    # ⑩ — холостой прогон
    before = query("SELECT (SELECT reviewer FROM backlog WHERE id = ?), "
                   "(SELECT COUNT(*) FROM backlog_events)", (card_b,))[0]
    rc10, out10 = run("status", str(card_b), "blocked", "--actor", OWNER, "--note", "холостой",
                      "--dry-run")
    rc10b, out10b = run("status", str(card_b), "in_review", "--actor", OWNER, "--reviewer", OTHER,
                        "--dry-run")
    after = query("SELECT (SELECT reviewer FROM backlog WHERE id = ?), "
                  "(SELECT COUNT(*) FROM backlog_events)", (card_b,))[0]
    case("⑩", "холостой прогон status --dry-run --reviewer — ни поля, ни событий не прибавилось",
         rc10 == 0 and rc10b == 0 and before == after,
         f"коды {rc10}, {rc10b} · приёмщик и событий: {before} → {after}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL} · испытан {mezo_target.label()}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'🧪' if exact else '⚠️'} поломка «{a.break_name}»: провалились "
              f"{' '.join(RED) or 'никто'} · ждали {' '.join(sorted(expected))} — "
              f"{'ожидание ПОДТВЕРДИЛОСЬ' if exact else 'ожидание НЕ ПОДТВЕРДИЛОСЬ'}")
        if exact:
            # поломка поймана, как записано, — стенд хранить незачем; код выхода прежний (1)
            mezo_stand.expected_break()
        return mezo_stand.finish(1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
