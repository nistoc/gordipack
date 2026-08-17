# -*- coding: utf-8 -*-
"""
bite-thread.py — укус тредов (Ш4, пункт 2.6).

Конструкция пришла от AIA, нужда подтверждена НАШИМ замером: 83 % нот ссылаются
на другие прозой (1413 ссылок, окно #2500…#2956). Здесь проверяется не «работает ли
INSERT», а три вещи, ради которых треды и заводятся:

  ① ответ без вопроса записать НЕЛЬЗЯ — иначе тред снова станет прозой в полях;
  ② «отвечено» и «закрыто» РАЗЛИЧАЮТСЯ — иначе первый же ответ погасит живой вопрос;
  ③ витрина молчит там, где данных нет, и НЕ притворяется, что вопросов не осталось.

    python bite-thread.py            # свойства
    python bite-thread.py --selftest # доказать, что укус умеет краснеть
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
    for r in ("COORD", "PROTO", "CORE", "STUD"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (r,))
    return con


def msg(con, mid, who="COORD", body="x"):
    con.execute("INSERT INTO messages (id, writer_role, body_md) VALUES (?,?,?)", (mid, who, body))
    return mid


def to(con, mid, role, kind="to"):
    con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (?,?,?)",
                (mid, role, kind))


def thread(con, mid, reply_to=None, thread_id=None, kind=None, linked_by="field"):
    con.execute("INSERT INTO message_thread (message_id, reply_to, thread_id, kind, linked_by) "
                "VALUES (?,?,?,?,?)", (mid, reply_to, thread_id, kind, linked_by))


def rejects(fn) -> bool:
    """Отказ схемы — это ФАКТ отказа, а не текст сообщения: текст меняется, контракт нет."""
    try:
        fn()
        return False
    except sqlite3.IntegrityError:
        return True


def run():
    res = []
    def check(name, cond): res.append((name, bool(cond)))

    # ── ① СТРУКТУРА РАЗГОВОРА СОБИРАЕТСЯ ЗАПРОСОМ ────────────────────────────
    con = fresh()
    q = msg(con, 100, "CORE", "какое право нужно для поиска?")
    to(con, q, "PROTO")
    thread(con, q, kind="question")

    a1 = msg(con, 101, "PROTO", "search:read")
    thread(con, a1, reply_to=q, thread_id=q, kind="answer")

    a2 = msg(con, 102, "STUD", "подтверждаю замером")
    thread(con, a2, reply_to=a1, thread_id=q, kind="answer")

    root_of_q = con.execute("SELECT root_id FROM thread_view WHERE id=?", (q,)).fetchone()[0]
    check("P1 корень с thread_id=NULL вычисляется как свой id (не сирота)", root_of_q == q)

    whole = [r[0] for r in con.execute(
        "SELECT id FROM thread_view WHERE root_id=? ORDER BY id", (q,))]
    check("P2 весь разговор — ОДИН запрос, не чтение глазами", whole == [100, 101, 102])

    # ── ② КОНТРАКТЫ: ЧЕГО СХЕМА НЕ ДАЁТ ЗАПИСАТЬ ─────────────────────────────
    orphan = msg(con, 200, "STUD")
    check("P3 ⛔ ответ БЕЗ вопроса не записывается (kind='answer' требует reply_to)",
          rejects(lambda: thread(con, orphan, kind="answer")))

    self_ref = msg(con, 201, "STUD")
    check("P4 ⛔ нота не отвечает сама себе",
          rejects(lambda: thread(con, self_ref, reply_to=self_ref, kind="answer")))
    check("P5 ⛔ нота не объявляет корнем саму себя (два способа записать одно состояние)",
          rejects(lambda: thread(con, self_ref, thread_id=self_ref, kind="status")))

    # ── ③ ВИТРИНА «ВОПРОСЫ КО МНЕ» — ГЛАВНОЕ, РАДИ ЧЕГО ВСЁ ──────────────────
    con2 = fresh()
    hang = msg(con2, 300, "CORE", "висящий вопрос")
    to(con2, hang, "PROTO"); thread(con2, hang, kind="question")

    answered = msg(con2, 310, "CORE", "вопрос, на который ответили")
    to(con2, answered, "PROTO"); thread(con2, answered, kind="question")
    ans = msg(con2, 311, "PROTO", "ответ")
    thread(con2, ans, reply_to=answered, thread_id=answered, kind="answer")

    closed = msg(con2, 320, "CORE", "вопрос, который закрыли")
    to(con2, closed, "PROTO"); thread(con2, closed, kind="question")
    cl = msg(con2, 321, "PROTO", "закрывающая нота")
    thread(con2, cl, reply_to=closed, thread_id=closed, kind="answer")
    con2.execute("INSERT INTO message_closure (message_id, closed_by, closed_role) VALUES (?,?,?)",
                 (closed, cl, "PROTO"))

    mine = dict(con2.execute(
        "SELECT id, state FROM open_questions_for_role WHERE role='PROTO'").fetchall())
    check("P6 висящий вопрос виден", mine.get(300) == "висит")
    check("P7 'отвечено, не закрыто' ОТЛИЧАЕТСЯ от 'висит' "
          "(ответ сам по себе вопрос не гасит)", mine.get(310) == "отвечено, не закрыто")
    check("P8 закрытый вопрос из витрины ИСЧЕЗАЕТ", 320 not in mine)

    # чужое в мою витрину не попадает
    other = msg(con2, 330, "CORE", "вопрос к CORE, не ко мне")
    to(con2, other, "STUD"); thread(con2, other, kind="question")
    mine2 = [r[0] for r in con2.execute(
        "SELECT id FROM open_questions_for_role WHERE role='PROTO'")]
    check("P9 вопрос, адресованный ДРУГОЙ роли, в мою витрину не попадает", 330 not in mine2)

    # cc — не «спросили тебя». Граница названа, потому что она неочевидна.
    ccq = msg(con2, 340, "CORE", "вопрос к STUD, я в копии")
    to(con2, ccq, "STUD"); to(con2, ccq, "PROTO", kind="cc"); thread(con2, ccq, kind="question")
    mine3 = [r[0] for r in con2.execute(
        "SELECT id FROM open_questions_for_role WHERE role='PROTO'")]
    check("P10 копия (cc) — не «спросили тебя»: в личную витрину не идёт", 340 not in mine3)

    # ── ④ РАЗЛИЧАЮЩИЕ ТЕСТЫ: МОЛЧАНИЕ ДОЛЖНО БЫТЬ ЧЕСТНЫМ ───────────────────
    # Проверяем не «витрина пуста», а что пустота ОТЛИЧАЕТСЯ от «связей нет вовсе».
    con3 = fresh()
    old = msg(con3, 400, "COORD", "старая нота, ссылается прозой на #2775")
    to(con3, old, "PROTO")
    empty = con3.execute("SELECT COUNT(*) FROM open_questions_for_role").fetchone()[0]
    cand = [r[0] for r in con3.execute("SELECT id FROM thread_backfill_candidates")]
    check("P11 старая нота без треда: витрина вопросов ПУСТА (вид неизвестен, не выдуман)",
          empty == 0)
    check("P12 …и та же нота ВИДНА как кандидат на ручную сшивку — молчание не съело связь",
          400 in cand)

    # linked_by различает объявленное и восстановленное — иначе backfill сойдёт за правду
    guess = msg(con3, 401, "COORD")
    thread(con3, guess, reply_to=400, thread_id=400, kind="answer", linked_by="backfill")
    kinds = dict(con3.execute("SELECT id, linked_by FROM thread_view WHERE linked_by IS NOT NULL"))
    check("P13 восстановленная связь помечена 'backfill' и отличима от объявленной",
          kinds.get(401) == "backfill")
    check("P14 ⛔ третьего значения linked_by не существует "
          "(«примерно поле» — способ вернуть прозу)",
          rejects(lambda: thread(con3, msg(con3, 402, "COORD"), kind="status", linked_by="maybe")))

    # ── ⑤ ГРАНИЦА, КОТОРУЮ Я НАЗЫВАЮ САМ ─────────────────────────────────────
    # Витрина опирается на kind='question'. Если вид не проставлен, вопрос НЕ ВИДЕН —
    # и это не дефект витрины, а отсутствие данных. Проверяю, что оно именно такое.
    con4 = fresh()
    silent = msg(con4, 500, "CORE", "вопрос без объявленного вида")
    to(con4, silent, "PROTO"); thread(con4, silent, kind=None)
    n = con4.execute("SELECT COUNT(*) FROM open_questions_for_role WHERE role='PROTO'").fetchone()[0]
    check("P15 нота без вида в витрину вопросов не попадает "
          "(граница: витрина знает объявленное, а не угаданное)", n == 0)

    return res


# ═════════════════════════════════════════════════════════════════════════════
# МУТАНТЫ. Не вставший мутант считается ВЫЖИВШИМ — иначе укус хвалит себя за
# паттерн, которого в файле уже нет.
# ═════════════════════════════════════════════════════════════════════════════

MUTANTS = {
    # Снять контракт «ответ требует вопроса» — и тред снова станет прозой в полях.
    "M1-ответ-без-вопроса-разрешён": (SCHEMA_FILE, lambda s: s.replace(
        "    CHECK (kind <> 'answer' OR reply_to IS NOT NULL)",
        "    CHECK (kind <> 'answer' OR 1)")),
    # Самый опасный: первый же ответ гасит живой вопрос. Ровно та ошибка, из-за которой
    # мы отказались от булева resolved.
    "M2-ответ-считается-закрытием": (SCHEMA_FILE, lambda s: s.replace(
        "WHERE c.message_id IS NULL;",
        "WHERE c.message_id IS NULL AND COALESCE(a.n,0) = 0;")),
    # Обратный: закрытые не уходят — витрина превращается в фон, и настоящее теряется.
    "M3-закрытые-остаются-в-витрине": (SCHEMA_FILE, lambda s: s.replace(
        "LEFT JOIN message_closure c ON c.message_id = m.id\nLEFT JOIN (SELECT reply_to",
        "LEFT JOIN message_closure c ON c.message_id = m.id AND 0\nLEFT JOIN (SELECT reply_to")),
    # Корень без COALESCE: нота-корень становится сиротой с root_id=NULL и выпадает
    # из собственного разговора.
    "M4-корень-без-COALESCE": (SCHEMA_FILE, lambda s: s.replace(
        "SELECT COALESCE(t.thread_id, m.id) AS root_id,",
        "SELECT t.thread_id AS root_id,")),
    # Адресат перестаёт фильтровать — роль видит чужие вопросы как свои.
    "M5-витрина-игнорирует-адресата": (SCHEMA_FILE, lambda s: s.replace(
        "JOIN message_addressee ma ON ma.message_id = m.id AND ma.kind = 'to'",
        "JOIN message_addressee ma ON ma.message_id = m.id")),
    # Кандидаты на сшивку исчезают — «пусто» станет неотличимо от «связей нет».
    "M6-кандидаты-backfill-скрыты": (SCHEMA_FILE, lambda s: s.replace(
        "WHERE t.message_id IS NULL AND INSTR(m.body_md, '#') > 0;",
        "WHERE t.message_id IS NULL AND 0;")),
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
                # Схема, сломавшаяся насмерть, — тоже пойманный мутант, но говорим об этом
                # вслух: иначе «поймал» скроет, что поймано не свойство, а синтаксис.
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
