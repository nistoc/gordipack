# -*- coding: utf-8 -*-
"""
bite-task.py — приёмка критерия «готово» и связи записки с задачей (Ш5, пункт 2.7).

Замер живой БД 2026-08-06 14:43 UTC: карточек 72 (открытых 40), колонок под критерий
закрытия — НИ ОДНОЙ; 348 записок упоминают несколько номеров карточек против 399 с одним.

Проверяется не «пишется ли строка», а четыре вещи, ради которых шаг делается:
  ① одна записка связывается с НЕСКОЛЬКИМИ карточками — иначе шаг бессмыслен;
  ② долг («открыто без критерия») виден ЗАПРОСОМ, а не чтением;
  ③ проверка закрытия не принимает пустую строку за критерий — иначе он украшение;
  ④ сторож НЕ мешает всему остальному: правкам карточки и повторному сохранению.

    python bite-task.py            # свойства
    python bite-task.py --selftest # доказать, что укус умеет краснеть
"""
import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "schema_vnext.sql"


def fresh():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    for r in ("COORD", "PROTO", "CORE"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (r,))
    return con


def card(con, cid, role="PROTO", title="t", status="open", done_when=None):
    con.execute("INSERT INTO backlog (id, role, title, status, done_when) VALUES (?,?,?,?,?)",
                (cid, role, title, status, done_when))
    return cid


def msg(con, mid, who="PROTO", body="x"):
    con.execute("INSERT INTO messages (id, writer_role, body_md) VALUES (?,?,?)", (mid, who, body))
    return mid


def rejects(fn) -> bool:
    """Отказ — это ФАКТ отказа, не текст: текст меняется, контракт нет."""
    try:
        fn()
        return False
    except sqlite3.Error:
        return True


def run():
    res = []
    def check(name, cond): res.append((name, bool(cond)))

    # ── ① СВЯЗЬ «МНОГИЕ КО МНОГИМ» — ГЛАВНОЕ СВОЙСТВО ШАГА ───────────────────
    con = fresh()
    for cid in (69, 70, 71, 72):
        card(con, cid, title=f"карточка {cid}")
    note = msg(con, 900, "CORE", "очередь: #69 #70 #71 #72")
    for cid in (69, 70, 71, 72):
        con.execute("INSERT INTO message_task (message_id, task_id) VALUES (?,?)", (note, cid))

    linked = [r[0] for r in con.execute(
        "SELECT task_id FROM message_task WHERE message_id=? ORDER BY task_id", (note,))]
    check("P1 ОДНА записка связана с ЧЕТЫРЬМЯ карточками "
          "(колонка task_id заставила бы выбрать одну)", linked == [69, 70, 71, 72])

    hist = [r[0] for r in con.execute(
        "SELECT message_id FROM task_history WHERE task_id=71")]
    check("P2 история карточки собирается ОДНИМ запросом (сегодня не собирается вовсе)",
          hist == [900])

    check("P3 ⛔ связь с несуществующей карточкой не пишется",
          rejects(lambda: con.execute(
              "INSERT INTO message_task (message_id, task_id) VALUES (?, 999)", (note,))))
    check("P4 ⛔ та же связь дважды не пишется (иначе история карточки задвоится)",
          rejects(lambda: con.execute(
              "INSERT INTO message_task (message_id, task_id) VALUES (?, 69)", (note,))))
    check("P5 ⛔ третьего происхождения связи не бывает "
          "(«примерно указано» — способ вернуть прозу)",
          rejects(lambda: con.execute(
              "INSERT INTO message_task (message_id, task_id, linked_by) VALUES (?,?,'maybe')",
              (msg(con, 901), 70))))

    # ── ② ДОЛГ ВИДЕН ЗАПРОСОМ ────────────────────────────────────────────────
    con2 = fresh()
    card(con2, 1, title="без критерия")
    card(con2, 2, title="с критерием", done_when="гейт зелёный, 684/684")
    card(con2, 3, title="критерий из пробелов", done_when="   ")
    card(con2, 4, title="закрытая без критерия", status="done")
    card(con2, 5, title="критерий из табуляции", done_when="\t\t")

    debt = sorted(r[0] for r in con2.execute("SELECT id FROM backlog_without_criterion"))
    check("P6 открытая без критерия — в долге", 1 in debt)
    check("P7 открытая С критерием — из долга ушла", 2 not in debt)
    check("P8 критерий из одних пробелов НЕ считается критерием "
          "(иначе долг гасится пробелом)", 3 in debt)
    check("P9 закрытая карточка в долг открытых не попадает", 4 not in debt)
    check("P9b критерий из ТАБУЛЯЦИИ тоже не критерий "
          "(голый TRIM в SQLite снимает только пробел — поймано укусом)", 5 in debt)

    # ── ③ ПРОВЕРКА ЗАКРЫТИЯ ────────────────────────────────────────────────────
    con3 = fresh()
    card(con3, 10, title="закрываю без критерия")
    check("P10 ⛔ закрыть карточку БЕЗ критерия нельзя",
          rejects(lambda: con3.execute("UPDATE backlog SET status='done' WHERE id=10")))

    card(con3, 11, title="пустой критерий", done_when="")
    check("P11 ⛔ пустая строка критерием не считается",
          rejects(lambda: con3.execute("UPDATE backlog SET status='done' WHERE id=11")))
    card(con3, 12, title="критерий из пробелов", done_when="  \t ")
    check("P12 ⛔ пробелы критерием не считаются (различающий: сторож смотрит В строку, "
          "а не на её наличие)",
          rejects(lambda: con3.execute("UPDATE backlog SET status='done' WHERE id=12")))

    card(con3, 13, title="с критерием", done_when="укус 15/15 и 6 нарочных поломок поймано")
    con3.execute("UPDATE backlog SET status='done' WHERE id=13")
    check("P13 закрыть С критерием — проходит (сторож не запрещает работу)",
          con3.execute("SELECT status FROM backlog WHERE id=13").fetchone()[0] == "done")

    # ④ Сторож не мешает остальному — граница, которую называю сам
    con3.execute("UPDATE backlog SET title='переименована' WHERE id=10")
    check("P14 правка ДРУГИХ полей открытой карточки без критерия — свободна",
          con3.execute("SELECT title FROM backlog WHERE id=10").fetchone()[0] == "переименована")

    con3.execute("UPDATE backlog SET status='done' WHERE id=13")
    check("P15 повторное сохранение УЖЕ закрытой карточки не падает "
          "(сторож ловит ПЕРЕХОД, а не состояние)",
          con3.execute("SELECT status FROM backlog WHERE id=13").fetchone()[0] == "done")

    # 🔴 РАЗЛИЧАЮЩИЙ ТЕСТ, добавленный после выжившего мутанта. Прежний P15 ничего не
    # доказывал: карточка была закрыта И с критерием, поэтому сторож молчал в обоих
    # случаях. Настоящий случай — в живой базе: 32 карточки УЖЕ закрыты и критерия
    # у них нет (переносим как есть). Если сторож ловит СОСТОЯНИЕ, а не ПЕРЕХОД, весь
    # закрытый бэклог станет неправимым — и узнаем мы об этом на первой же правке.
    card(con3, 15, title="перенесённая: закрыта, критерия нет", status="done")
    con3.execute("UPDATE backlog SET status='done' WHERE id=15")
    check("P15b УЖЕ закрытую карточку БЕЗ критерия можно сохранить снова "
          "(32 такие переезжают из рабочей базы)",
          con3.execute("SELECT status FROM backlog WHERE id=15").fetchone()[0] == "done")

    card(con3, 14, title="в блок", done_when=None)
    con3.execute("UPDATE backlog SET status='blocked' WHERE id=14")
    check("P16 перевод в другие статусы критерия не требует",
          con3.execute("SELECT status FROM backlog WHERE id=14").fetchone()[0] == "blocked")

    return res


# ═════════════════════════════════════════════════════════════════════════════
# МУТАНТЫ. Не вставший мутант считается ВЫЖИВШИМ.
# ═════════════════════════════════════════════════════════════════════════════

MUTANTS = {
    # Сторож смотрит только на NULL — и пустая строка становится «критерием».
    # Ровно тот способ, которым живое поле превращается в украшение.
    "M1-сторож-не-видит-пустую-строку": (SCHEMA_FILE, lambda s: s.replace(
        "     AND (NEW.done_when IS NULL\n"
        "          OR TRIM(NEW.done_when, ' ' || char(9) || char(10) || char(13)) = '')",
        "     AND NEW.done_when IS NULL")),
    # Голый TRIM снимает только пробел — критерий из ОДНОЙ ТАБУЛЯЦИИ снова пройдёт
    # за настоящий. Это не выдуманная мутация: ровно так и было до 14:46 UTC.
    "M2-сторож-верит-табуляции": (SCHEMA_FILE, lambda s: s.replace(
        "          OR TRIM(NEW.done_when, ' ' || char(9) || char(10) || char(13)) = '')",
        "          OR TRIM(NEW.done_when) = '')")),
    # То же в витрине долга: долг гасится табуляцией.
    "M3-витрина-долга-верит-табуляции": (SCHEMA_FILE, lambda s: s.replace(
        "       OR TRIM(done_when, ' ' || char(9) || char(10) || char(13)) = '');",
        "       OR TRIM(done_when) = '');")),
    # Витрина берёт и закрытые — долг раздувается и перестаёт быть списком работы.
    "M3b-в-долг-попадают-закрытые": (SCHEMA_FILE, lambda s: s.replace(
        "WHERE status = 'open'\n  AND (done_when IS NULL",
        "WHERE status IN ('open','done')\n  AND (done_when IS NULL")),
    # Сторож срабатывает на любое сохранение закрытой карточки — работа встаёт.
    "M4-сторож-ловит-состояние-а-не-переход": (SCHEMA_FILE, lambda s: s.replace(
        "WHEN NEW.status = 'done' AND OLD.status <> 'done'",
        "WHEN NEW.status = 'done'")),
    # Ключ только по записке — одна записка не сможет ссылаться на несколько карточек.
    "M5-одна-записка-одна-карточка": (SCHEMA_FILE, lambda s: s.replace(
        "    PRIMARY KEY (message_id, task_id)\n);",
        "    PRIMARY KEY (message_id)\n);")),
}


def selftest():
    clean = run()
    red = sum(1 for _, ok in clean if not ok)
    print(f"ЧИСТО: {len(clean)-red}/{len(clean)}")
    if red:
        print("🔴 ПРИЁМКА КРАСНАЯ НА ЧИСТОМ — самопроверка невозможна")
        for n, ok in clean:
            if not ok:
                print(f"   🔴 {n}")
        return 1
    survived = 0
    for name, (target, mut) in MUTANTS.items():
        orig = target.read_text(encoding="utf-8")
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден в {target.name} — нарочная поломка НЕ ВСТАЛА, "
                  f"считаю ВЫЖИВШИМ (не вставший мутант ничего не доказывает)")
            survived += 1
            continue
        target.write_text(bad, encoding="utf-8")
        try:
            try:
                r = run()
                nred = sum(1 for _, ok in r if not ok)
            except sqlite3.Error as e:
                nred, r = 1, [("схема не собралась: " + str(e)[:60], False)]
            caught = nred > 0
            print(f"{'✅' if caught else '🔴'} {name}: "
                  f"{'поймал' if caught else 'НЕ ПОЙМАЛ'} ({nred}/{len(r)} красных)")
            if not caught:
                survived += 1
        finally:
            target.write_text(orig, encoding="utf-8")
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано "
          f"(число из len(MUTANTS))")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    rs = run()
    bad = 0
    for n, ok in rs:
        print(f"{'✅' if ok else '🔴'} {n}")
        bad += 0 if ok else 1
    print(f"\n{len(rs)-bad}/{len(rs)}, rc={0 if bad==0 else 1}")
    sys.exit(0 if bad == 0 else 1)
