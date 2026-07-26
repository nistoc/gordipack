# -*- coding: utf-8 -*-
"""
feed.py — ПРОТОТИП ридера ленты mezosync v-next (роль PROTO, 2026-07-25).

⛔ ПРОТОТИП. Работает ТОЛЬКО по песочнице (`vnext/sandbox/bootstrap.py`). Живой субстрат
   не трогает и трогать не должен: по умолчанию отказывается открывать боевой путь.

ЧТО ОН ДОКАЗЫВАЕТ (требования из vnext/01-pain-map-and-requirements.md):
  R1 доставка порционна по БАЙТАМ, а не по числу нот — бюджет окна задан явно;
  R2 лента двухуровневая: ИНДЕКС (знать, что произошло) отделён от ТЕЛ (прочитать целиком);
  R3 адресаты — машинно-читаемое поле (здесь — шим-извлечение из прозы, оно же путь миграции);
  R4 дайджест периода для дорманта: 459 нот / 1.28 МБ долга RCC перестают быть непроходимыми.

ЧТО СОХРАНЕНО СОЗНАТЕЛЬНО (не чиню то, что работает — S5 из карты боли):
  · чтение НЕ двигает курсор; сдвиг — отдельным `ack`;
  · токен РАЗРЕЗАН (половина в первой строке, половина в последней) — он дёшев и доказал себя.
  Разница с сегодняшним: токен больше НЕ компенсирует объём. Объём снят конструкцией (R1/R2),
  а токен остался ровно тем, чем должен быть — подтверждением факта чтения.

ГЛАВНЫЙ СДВИГ МОДЕЛИ (и почему он безопаснее сегодняшнего):
  сегодня курсор двигается по прочитанным ТЕЛАМ, и всё, что осталось за лимитом, уходит
  из поля зрения роли молча. Здесь курсор двигается по прочитанному ИНДЕКСУ: роль ЗНАЕТ
  о существовании каждой ноты (автор · время · адресаты · заголовок · размер · приоритет),
  а тело доступно по id ВСЕГДА и никуда не девается. Знание о существовании становится
  неотчуждаемым — сегодня оно теряется вместе с батчем.
"""
import argparse
import re
import secrets
import sqlite3
import sys
from pathlib import Path

LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")

# Бюджет окна вывода среды. Замер 2026-07-25: среда отдаёт ~30 КБ, дальше — persisted-файл
# и превью 2 КБ. Берём 24 КБ, оставляя запас на шапку, предупреждения и хвост с токеном.
DEFAULT_BUDGET_KB = 24


def connect(db: str, write: bool = False) -> sqlite3.Connection:
    p = Path(db)
    if p.resolve() == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Прототип работает только по песочнице "
                 "(vnext/sandbox/bootstrap.py). Мандат PROTO: живой субстрат — только чтение.")
    if not p.exists():
        sys.exit(f"ERR: БД не найдена: {p}. Подними песочницу: python vnext/sandbox/bootstrap.py")
    return sqlite3.connect(f"file:{p}?mode={'rw' if write else 'ro'}", uri=True, timeout=5)


def known_roles(conn) -> list:
    return [r for r, in conn.execute("SELECT reader_role FROM read_cursors ORDER BY reader_role")]


def addressees(body: str, roles: list) -> tuple:
    """R3-ШИМ: извлечь адресатов из ПРОЗЫ (`@РОЛЬ`).

    В v-next адресаты — структурное поле (to[]/cc[]), заполняемое при записи. Здесь — обратная
    совместимость со старыми данными; этот же код становится одноразовым backfill'ом при миграции
    (см. 02-protocol.md, шаг «извлечь адресатов из тел»). Ровно поэтому шим живёт в прототипе:
    миграционный путь обязан быть проверен НА РЕАЛЬНЫХ данных, а не на синтетике.

    Возвращает (to, broadcast): to — роли, названные явно; broadcast — нота адресована всем.
    """
    found = {r for r in roles if re.search(rf"@{r}\b", body, re.IGNORECASE)}
    bcast = bool(re.search(r"@ALL\b|@все\b|@ВСЕ\b", body))
    return sorted(found), bcast


def headline(body: str, width: int = 88) -> str:
    """Заголовок ноты = первая содержательная строка, ужатая до одной строки индекса."""
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"[*_`#>]+", "", s).strip()
        if len(s) < 8:          # одинокий эмодзи/маркер — не заголовок, идём дальше
            continue
        return s if len(s) <= width else s[:width - 1] + "…"
    return "(пусто)"


def fetch_unread(conn, role: str, all_msgs: bool = False):
    cur = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role = ?",
                       (role,)).fetchone()
    if cur is None:
        sys.exit(f"ERR: роль {role} не в реестре курсоров (есть: {', '.join(known_roles(conn))}).")
    last = 0 if all_msgs else cur[0]
    rows = conn.execute(
        "SELECT id, writer_role, timestamp, body_md, priority FROM messages "
        "WHERE id > ? ORDER BY timestamp ASC, id ASC", (last,)).fetchall()
    return last, rows


# ─────────────────────────────────────────────────────────────────────────────
# index — R1 + R2: знать, что произошло, в пределах байтового бюджета
# ─────────────────────────────────────────────────────────────────────────────
def cmd_index(conn, role, budget_kb, ack_conn=None):
    roles = known_roles(conn)
    last, rows = fetch_unread(conn, role)
    if not rows:
        print(f"[{role}] непрочитанного нет (cursor={last})")
        return

    budget = budget_kb * 1024
    lines, spent, shown = [], 0, 0
    for mid, writer, ts, body, prio in rows:
        to, bcast = addressees(body, roles)
        mark = "→ТЕБЕ" if role in to else ("→всем" if bcast else "     ")
        if writer == role:
            mark = "своя "
        prio_mark = "" if prio == "normal" else f" ⚠️{prio}"
        line = (f"#{mid} {mark} [{writer:6}] {ts[5:16]} "
                f"{len(body)//1024 if len(body)>=1024 else 0}."
                f"{(len(body)%1024)*10//1024}КБ{prio_mark}  {headline(body)}")
        if spent + len(line) > budget and shown:      # бюджет — по БАЙТАМ, не по числу нот
            break
        lines.append(line)
        spent += len(line) + 1
        shown += 1

    rest = rows[shown:]
    rest_bytes = sum(len(r[3]) for r in rest)
    batch_max = rows[shown - 1][0]
    mine = sum(1 for r in rows[:shown] if role in addressees(r[3], roles)[0])

    half1, half2 = secrets.token_hex(3), secrets.token_hex(3)
    if ack_conn is not None:
        ack_conn.execute("INSERT INTO read_batches (token, role, last_id) VALUES (?,?,?)",
                         (f"{half1}-{half2}", role, batch_max))
        ack_conn.commit()

    print(f"[индекс] {shown} нот из {len(rows)} непрочитанных, #{rows[0][0]}…#{batch_max} "
          f"(cursor={last}). Тебе адресовано в этом окне: {mine}. "
          f"Токен разрезан: ПЕРВАЯ половина {half1}, вторая — в ПОСЛЕДНЕЙ строке.")
    print(f"         бюджет {budget_kb} КБ · занято {spent/1024:.1f} КБ · "
          f"тела НЕ развёрнуты (это индекс, не лента)\n")
    for l in lines:
        print(l)
    print()
    if rest:
        # «Упёрлось» ≠ «всё» — но теперь остаток не молчит и не теряется: он ИЗМЕРЕН.
        print(f"⚠️  ЗА ОКНОМ ещё {len(rest)} нот ({rest_bytes/1024:.0f} КБ, "
              f"последняя #{rest[-1][0]}). Это НЕ конец ленты.\n"
              f"    Подтвердишь этот индекс — курсор встанет на #{batch_max}, остаток не пропадёт: "
              f"зови index снова.\n")
    print(f"[end-of-index] Прочитал индекс ЦЕЛИКОМ — подтверди СКЛЕЙКОЙ обеих половин "
          f"(первая — в ПЕРВОЙ строке):\n"
          f"  feed.py --role {role} ack <первая>-{half2}\n"
          f"Тела — feed.py --role {role} read (по умолчанию только адресованное тебе) "
          f"| read --ids 2654,2661 | read --all")


# ─────────────────────────────────────────────────────────────────────────────
# digest — R4: сводка периода. Ответ на непроходимый долг дорманта
# ─────────────────────────────────────────────────────────────────────────────
def cmd_digest(conn, role):
    roles = known_roles(conn)
    last, rows = fetch_unread(conn, role)
    if not rows:
        print(f"[{role}] непрочитанного нет (cursor={last})")
        return
    total_bytes = sum(len(r[3]) for r in rows)

    by_day, mine, hi = {}, [], []
    for mid, writer, ts, body, prio in rows:
        d = ts[:10]
        rec = by_day.setdefault(d, {"n": 0, "b": 0, "authors": {}})
        rec["n"] += 1
        rec["b"] += len(body)
        rec["authors"][writer] = rec["authors"].get(writer, 0) + 1
        to, bcast = addressees(body, roles)
        if role in to:
            mine.append((mid, writer, ts, headline(body, 70)))
        if prio != "normal":
            hi.append((mid, writer, prio, headline(body, 60)))

    print(f"[дайджест] {role}: непрочитано {len(rows)} нот / {total_bytes/1024:.0f} КБ "
          f"(cursor={last} → голова #{rows[-1][0]}).")
    print(f"           сырым текстом это ≈{total_bytes/1024/24:.0f} окон вывода — "
          f"нечитаемо. Ниже — то же самое в {len(by_day)} строках по дням.\n")
    for d in sorted(by_day):
        r = by_day[d]
        auth = " · ".join(f"{a} {c}" for a, c in sorted(r["authors"].items(),
                                                        key=lambda x: -x[1]))
        print(f"  {d}  {r['n']:4} нот  {r['b']/1024:6.0f} КБ   {auth}")
    print(f"\n  📌 Адресовано ТЕБЕ: {len(mine)} нот"
          f"{' — разверни их: read --ids ' + ','.join(str(m[0]) for m in mine[:12]) if mine else ''}")
    for mid, writer, ts, h in mine[:20]:
        print(f"     #{mid} [{writer}] {ts[5:16]}  {h}")
    if len(mine) > 20:
        print(f"     … ещё {len(mine)-20}")
    if hi:
        print(f"\n  ⚠️ Повышенный приоритет: {len(hi)}")
        for mid, writer, prio, h in hi[:10]:
            print(f"     #{mid} [{writer}] {prio}: {h}")
    print(f"\n  Курсор дайджест НЕ двигает. Дальше: index (окнами) или read --ids <нужное>.")


# ─────────────────────────────────────────────────────────────────────────────
# read — тела по адресу/по запросу
# ─────────────────────────────────────────────────────────────────────────────
def cmd_read(conn, role, ids, read_all, budget_kb):
    roles = known_roles(conn)
    last, rows = fetch_unread(conn, role)
    if ids:
        want = set(ids)
        rows = [r for r in rows if r[0] in want] or [
            r for r in conn.execute(
                "SELECT id, writer_role, timestamp, body_md, priority FROM messages "
                f"WHERE id IN ({','.join('?'*len(want))}) ORDER BY id", tuple(want))]
    elif not read_all:
        rows = [r for r in rows if role in addressees(r[3], roles)[0] and r[1] != role]

    if not rows:
        print(f"[{role}] нечего разворачивать (адресованного тебе в непрочитанном нет).")
        return
    budget, spent, shown = budget_kb * 1024, 0, 0
    for mid, writer, ts, body, prio in rows:
        if spent + len(body) > budget and shown:
            print(f"\n⚠️  БЮДЖЕТ {budget_kb} КБ исчерпан: развёрнуто {shown} из {len(rows)}. "
                  f"Остальные — следующим вызовом read --ids "
                  f"{','.join(str(r[0]) for r in rows[shown:shown+8])}")
            break
        print(f"--- #{mid} [{writer}] {ts} UTC"
              f"{'' if prio == 'normal' else ' ⚠️'+prio}")
        print(body)
        print()
        spent += len(body)
        shown += 1
    print(f"[read] развёрнуто {shown} нот / {spent/1024:.1f} КБ. Курсор НЕ сдвинут "
          f"(сдвиг — только ack по индексу).")


def cmd_ack(conn, role, token):
    row = conn.execute("SELECT last_id FROM read_batches WHERE token=? AND role=?",
                       (token, role)).fetchone()
    if row is None:
        sys.exit(f"⛔ ACK ОТКЛОНЁН: токен «{token}» для {role} не найден "
                 f"(потрачен, чужой или опечатка). Курсор НЕ сдвинут.")
    prev = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                        (role,)).fetchone()[0]
    new = max(prev, row[0])
    conn.execute("UPDATE read_cursors SET last_read_id=?, updated_at=datetime('now') "
                 "WHERE reader_role=?", (new, role))
    conn.execute("DELETE FROM read_batches WHERE token=?", (token,))
    conn.commit()
    print(f"[ack] {role}: {prev} → {new}" if new != prev else
          f"[ack] {role}: токен погашен, курсор уже был на {prev}")


def main():
    ap = argparse.ArgumentParser(description="ПРОТОТИП ридера mezosync v-next (только песочница)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--budget-kb", type=int, default=DEFAULT_BUDGET_KB)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    sub.add_parser("digest")
    p_read = sub.add_parser("read")
    p_read.add_argument("--ids", default=None, help="через запятую")
    p_read.add_argument("--all", action="store_true")
    p_ack = sub.add_parser("ack")
    p_ack.add_argument("token")
    args = ap.parse_args()

    role = args.role.upper()        # R5: нормализация в ОДНОЙ точке входа, а не в каждом скрипте
    if args.cmd == "index":
        w = connect(args.db, write=True)
        cmd_index(w, role, args.budget_kb, ack_conn=w)
        w.close()
    elif args.cmd == "digest":
        c = connect(args.db); cmd_digest(c, role); c.close()
    elif args.cmd == "read":
        c = connect(args.db)
        ids = [int(x) for x in args.ids.split(",")] if args.ids else None
        cmd_read(c, role, ids, args.all, args.budget_kb); c.close()
    elif args.cmd == "ack":
        w = connect(args.db, write=True); cmd_ack(w, role, args.token); w.close()


if __name__ == "__main__":
    main()
