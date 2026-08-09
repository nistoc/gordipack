# -*- coding: utf-8 -*-
"""feed-index.py — УКАЗАТЕЛЬ ВМЕСТО ПОЛНЫХ ТЕЛ ПРИ ПРОБУЖДЕНИИ (2.4).

ЗАМЕР 2026-08-06 15:09 UTC по живой базе (перемерено, старое число не бралось):
    нот 1564 · медиана тела 2113 знаков · максимум 10938
    указатель плотнее тел в 17.6 – 28.5 раза (на любом окне)
    непрочитанное СЕЙЧАС:  ING 102 нот = 407 КБ · RCC 95 = 379 КБ · TAXO 87 = 349 КБ
    ИТОГО по контуру: 1229.6 КБ тел  →  43.0 КБ указателя, экономия 97 %
    заголовок пригоден у 100 % нот (без заголовка — 0, короче 25 знаков — 1)

🔴 ГЛАВНОЕ РЕШЕНИЕ, И ОНО НЕ ПРО ЭКОНОМИЮ: ЧТЕНИЕ УКАЗАТЕЛЯ НЕ ДВИГАЕТ КУРСОР.
   Без этого правила указатель — не облегчение, а способ молча пропустить ленту:
   роль «прошла» 102 ноты, ничего не прочитав, и субстрат считает их прочитанными.
   Это ровно тот дефект, который лечит честный курсор (Ш3): участок, пройденный
   не глазами, обязан быть помечен как заявленный, а не выдан за чтение.
   ⇒ Указатель СТЫКУЕТСЯ с курсором, а не обходит его:
       прочитал тела  ⇒ ack, отрезок 'read'
       прошёл указателем ⇒ отрезок 'declared', основание «читан указатель, тела не читаны»
   Поэтому здесь нет и не будет флага «подтвердить всё из указателя».

    python feed-index.py --role PROTO                  # указатель непрочитанного
    python feed-index.py --role PROTO --body 2993      # тело одной ноты
    python feed-index.py --role PROTO --bodies 2990,2991
    python feed-index.py --selftest
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

DB_DEFAULT = str(mezo_paths.live_db())


def table_exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (name,)).fetchone() is not None


def headline(body: str, width: int = 96) -> str:
    """Заголовок = первая непустая строка без разметки.

    ⚠️ Граница названа замером, а не обещанием: пригоден у 100 % наших нот, но это
    свойство НАШЕЙ традиции писать шапку первой строкой, а не свойство механизма.
    Контур с другой традицией получит бесполезный указатель — и увидит это сразу,
    потому что доля пригодных печатается.
    """
    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        s = re.sub(r"[*_`#]", "", s).strip()
        if s:
            return s[:width]
    return ""


def cursor_of(con, role):
    if not table_exists(con, "read_cursors"):
        return 0
    r = con.execute("SELECT last_read_id FROM read_cursors WHERE UPPER(reader_role)=UPPER(?)",
                    (role,)).fetchone()
    return (r[0] if r and r[0] else 0)


def addressees(con, ids):
    """Кому адресовано — ПОЛЕМ, если поле уже есть (Ш2/Ш4). Если таблицы нет — молчим
    об адресате ВСЛУХ, а не подставляем догадку разбором прозы."""
    if not ids or not table_exists(con, "message_addressee"):
        return None
    out = {}
    qs = ",".join("?" * len(ids))
    for mid, role, kind in con.execute(
            f"SELECT message_id, role, kind FROM message_addressee WHERE message_id IN ({qs})",
            list(ids)):
        out.setdefault(mid, []).append((role, kind))
    return out


def build_index(con, role, limit=None):
    cur = cursor_of(con, role)
    q = "SELECT id, writer_role, timestamp, body_md, priority FROM messages WHERE id > ? ORDER BY id"
    rows = list(con.execute(q, (cur,)))
    if limit:
        rows = rows[:limit]
    return cur, rows


def run(role, db_path, limit=None, body_ids=None):
    p = Path(db_path)
    print(f"📂 БАЗА: {p.resolve() if p.exists() else p}")
    if not p.exists():
        print("⛔ ОТКАЗ: базы нет")
        return 2
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)

    # ── ТЕЛА ПО ЗАПРОСУ ──────────────────────────────────────────────────────
    if body_ids:
        qs = ",".join("?" * len(body_ids))
        got = list(con.execute(
            f"SELECT id, writer_role, timestamp, body_md FROM messages WHERE id IN ({qs}) ORDER BY id",
            body_ids))
        missing = set(body_ids) - {r[0] for r in got}
        for mid, w, ts, body in got:
            print(f"\n{'─'*78}\n--- #{mid} [{w}] {ts} ---\n{body}")
        print(f"\n{'─'*78}")
        # Норма: прогон обязан назвать ЧИСЛО. «Запросил 3, получил 2» иначе неотличимо.
        print(f"ВЫДАНО ТЕЛ: {len(got)} из {len(body_ids)} запрошенных")
        if missing:
            print(f"🔴 НЕ НАЙДЕНЫ: {sorted(missing)} — это отказ, а не пустота")
        print("⚠️ Курсор НЕ сдвинут: выдача тела — не подтверждение прочтения ленты.")
        con.close()
        return 0 if not missing else 1

    # ── УКАЗАТЕЛЬ ────────────────────────────────────────────────────────────
    cur, rows = build_index(con, role, limit)
    if not rows:
        print(f"📏 охват: роль {role.upper()} · курсор {cur} · непрочитанного НЕТ")
        con.close()
        return 0

    ids = [r[0] for r in rows]
    addr = addressees(con, ids)
    idx_bytes = 0
    body_bytes = sum(len(r[3] or "") for r in rows)
    usable = 0

    print(f"📏 охват: роль {role.upper()} · курсор {cur} · непрочитано {len(rows)} "
          f"(#{ids[0]}…#{ids[-1]})")
    if addr is None:
        print("   ⚠️ адресат НЕ показан: поля адресата в этой базе ещё нет "
              "(шаг перевода 002/004). Это отсутствие данных, а не «всё broadcast»")
    print()

    for mid, writer, ts, body, prio in rows:
        h = headline(body)
        if len(h) >= 25:
            usable += 1
        mark = "⚠️" if prio in ("high", "critical") else "  "
        me = ""
        if addr is not None:
            mine = [k for r, k in addr.get(mid, []) if r.upper() == role.upper()]
            me = "👤" if "to" in mine else ("👥" if "cc" in mine else "  ")
        line = f"#{mid:<5} [{writer:<7}] {ts[:16]} {mark}{me} {h}"
        idx_bytes += len(line) + 1
        print(line)

    print()
    print(f"ВЫВЕДЕНО СТРОК: {len(rows)}   (норма: прогон обязан назвать число, "
          f"иначе ноль неотличим от успеха)")
    print(f"указатель {idx_bytes/1024:.1f} КБ  ·  те же ноты телами {body_bytes/1024:.1f} КБ  "
          f"·  плотнее в {body_bytes/max(idx_bytes,1):.1f} раза")
    print(f"заголовок пригоден (≥25 знаков): {usable}/{len(rows)} = {usable/len(rows):.0%}")
    print()
    print("🔴 КУРСОР НЕ СДВИНУТ И НЕ СДВИНЕТСЯ ЭТОЙ КОМАНДОЙ.")
    print("   Прочитал тела  → ack, отрезок 'read'")
    print("   Прошёл указателем → отрезок 'declared', основание «читан указатель, тела нет»")
    print(f"   Тела: feed-index.py --role {role} --bodies <id,id,…>")
    con.close()
    return 0


# ═════════════════════════════════════════════════════════════════════════════

def selftest():
    import tempfile
    ok, cases = True, 0
    tmp = Path(tempfile.mkdtemp(prefix="feed-idx-")) / "t.db"
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT, "
                "timestamp TEXT, body_md TEXT, priority TEXT DEFAULT 'normal')")
    con.execute("CREATE TABLE read_cursors (reader_role TEXT, last_read_id INTEGER)")
    con.execute("INSERT INTO read_cursors VALUES ('X', 2)")
    con.executemany(
        "INSERT INTO messages (id, writer_role, timestamp, body_md, priority) VALUES (?,?,?,?,?)",
        [(1, "A", "2026-08-06 10:00:00", "старая, прочитана", "normal"),
         (2, "A", "2026-08-06 10:01:00", "тоже прочитана", "normal"),
         (3, "B", "2026-08-06 10:02:00",
          "**Заголовок ноты, достаточно длинный для решения**\n\nтело ноты", "high")])
    con.commit(); con.close()

    # ① указатель отдаёт ТОЛЬКО непрочитанное
    cases += 1
    con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    cur, rows = build_index(con, "X")
    if cur != 2 or [r[0] for r in rows] != [3]:
        print(f"🔴 ① указатель взял не то: курсор={cur}, ноты={[r[0] for r in rows]}"); ok = False

    # ② РАЗЛИЧАЮЩИЙ: курсор ПОСЛЕ показа указателя не изменился
    cases += 1
    con.close()
    run("X", tmp)
    con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    if cursor_of(con, "X") != 2:
        print("🔴 ② УКАЗАТЕЛЬ СДВИНУЛ КУРСОР — он стал способом молча пропустить ленту")
        ok = False

    # ③ РАЗЛИЧАЮЩИЙ: выдача тела тоже не двигает курсор
    cases += 1
    con.close()
    run("X", tmp, body_ids=[3])
    con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    if cursor_of(con, "X") != 2:
        print("🔴 ③ выдача тела сдвинула курсор"); ok = False

    # ④ заголовок берётся из первой непустой строки и чистится от разметки
    cases += 1
    got_head = headline("\n\n**Шапка** ноты\nвторая строка")
    if got_head != "Шапка ноты":
        print(f"🔴 ④ заголовок разобран неверно: {got_head!r}")
        ok = False

    # ⑤ РАЗЛИЧАЮЩИЙ: запрос несуществующего тела — ОТКАЗ, а не тишина
    cases += 1
    con.close()
    if run("X", tmp, body_ids=[999]) != 1:
        print("🔴 ⑤ запрос несуществующей ноты прошёл как успех"); ok = False

    if cases == 0:
        print("⛔ ОТКАЗ: ни одного случая не выполнено")
        return 2
    print(f"\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} — "
          f"ВЫПОЛНЕНО {cases} случаев")
    print("   указатель берёт только непрочитанное · НЕ двигает курсор (дважды) · "
          "чистит заголовок · отказывает на несуществующем теле")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="указатель ленты вместо полных тел")
    ap.add_argument("--role")
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--body", type=int)
    ap.add_argument("--bodies")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.role:
        sys.exit("⛔ нужна --role")
    ids = None
    if a.body:
        ids = [a.body]
    elif a.bodies:
        ids = [int(x) for x in a.bodies.replace(" ", "").split(",") if x]
    sys.exit(run(a.role, a.db, a.limit, ids))
