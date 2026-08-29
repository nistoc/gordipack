# -*- coding: utf-8 -*-
"""
track.py — ПУЛ КАК РАБОЧАЯ ЕДИНИЦА (П③ плана «Роли не забывают», слово владельца
27.08 18:33 UTC: все роли работают над ОДНИМ пулом связанных задач за раз).

Пул = существующая таблица tracks; этот инструмент оживляет её мёртвые поля
(plan_md — 7 записей, ни одна не читалась; owner_decision — то же) и даёт пулу
вид, закрытие с вердиктами и триаж остатка.

    python <КОНТУР>/.mezosync/scripts/track.py view                # витрина активного пула
    python <КОНТУР>/.mezosync/scripts/track.py open --id TRACK-X --title "..." --actor РОЛЬ
    python <КОНТУР>/.mezosync/scripts/track.py plan --id TRACK-X --actor РОЛЬ --file план.md
    python <КОНТУР>/.mezosync/scripts/track.py verdict --id TRACK-X --role РОЛЬ --kind process --verdict "чисто"
    python <КОНТУР>/.mezosync/scripts/track.py close --id TRACK-X --actor РОЛЬ
    python <КОНТУР>/.mezosync/scripts/track.py triage                # три корзины остатка вне пула

ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
  · триаж НИЧЕГО НЕ МЕНЯЕТ — он печатает корзины и ГОТОВЫЕ команды; решение
    исполняет РУКА РОЛИ-ХОЗЯИНА (слово владельца: заморозка/закрытие — не скопом);
  · план пула ПИШЕТ роль-инициатор, СУДИТ координатор — инструмент записывает
    и журналирует, оценки не выносит;
  · закрытие требует вердикты у КАЖДОГО участника (состав — ЗАМЕРОМ по карточкам
    и событиям пула, не списком в коде); лазейка --no-verdicts требует причину
    и оставляет след в журнале действий.
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db
import dryrun

S = Path(__file__).resolve().parent

OPEN_STATUSES = ["open", "in_progress", "blocked", "awaiting_word", "in_review"]
CLOSED = ("done", "failed", "dropped")


def _conn(db, dry=False):
    p = Path(db)
    if not p.exists():
        sys.exit(f"ERR: БД не найдена: {p}")
    c = dryrun.connect(str(p), dry, timeout=5)
    c.execute("PRAGMA busy_timeout=5000")
    return c


def _audit(conn, actor, action, target, diff=""):
    conn.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                 (actor.upper(), action, target, diff))


def _active(conn):
    return [r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE status='active'")]


def _pick(conn, a):
    """Пул для команды: --id, иначе единственный активный. Несколько активных —
    назвать все и потребовать выбора: угаданный пул хуже отказа."""
    if getattr(a, "id", None):
        row = conn.execute("SELECT track_id FROM tracks WHERE track_id=?", (a.id,)).fetchone()
        if not row:
            sys.exit(f"⛔ пула {a.id} нет. Какие есть: "
                     + ", ".join(r[0] for r in conn.execute("SELECT track_id FROM tracks")))
        return a.id
    act = _active(conn)
    if len(act) == 1:
        return act[0]
    if not act:
        sys.exit("⛔ активного пула нет — назови --id или открой пул (track.py open)")
    sys.exit(f"⛔ активных пулов {len(act)} ({', '.join(act)}) — норма ОДИН; назови --id")


# Предикат живых/просроченных объявлений живёт в backlog.py (П②, 27.08) — единственный
# источник: его же зовут список карточек, обзор пробуждения и механизм сна. Своя копия
# разошлась бы молча при первой правке.
from backlog import live_and_overdue as _live_claims  # noqa: E402


def cmd_open(conn, a):
    if conn.execute("SELECT 1 FROM tracks WHERE track_id=?", (a.id,)).fetchone():
        sys.exit(f"⛔ пул {a.id} уже есть — открыть повторно нельзя, смотри: track.py view --id {a.id}")
    act = _active(conn)
    plan = Path(a.plan_file).read_text(encoding="utf-8") if a.plan_file else None
    conn.execute("INSERT INTO tracks (track_id, title, status, plan_md, owner_decision, skills) "
                 "VALUES (?,?,'active',?,?,?)",
                 (a.id, a.title, plan, a.word, a.skills))
    _audit(conn, a.actor, "open_track", a.id,
           f"открыт пул «{a.title}»" + (f"; слово: {a.word[:120]}" if a.word else ""))
    conn.commit()
    print(f"✅ пул {a.id} открыт: «{a.title}»")
    if act:
        print(f"⚠️ активных пулов теперь {len(act) + 1} ({', '.join(act)} + новый) — "
              f"норма нового порядка: ОДИН. Судьба прежнего — слово владельца.")
    if not a.word:
        print("✎ слово, которым пул открыт (с часом UTC), не записано — запиши: "
              "track.py open …  --word \"…\" (или обнови поле решения позже)")
    if not a.skills:
        print("✎ скиллы под задачу не названы — стартовая сводка новой сессии скажет это словами")
    # П⑥: порядок пересоздания чатов — печатается при ОТКРЫТИИ пула, принуждения нет
    print("📖 порядок для участниц (принуждения нет, свежесть меряется):")
    print("   1) сохранить память (save-phoenix) — сохранение старше открытия пула видно при просмотре пула")
    print("   2) пересоздать чат   3) начать со стартовой сводки: role-brief + выжимка пула + скиллы")


def cmd_plan(conn, a):
    tid = _pick(conn, a)
    body = Path(a.file).read_text(encoding="utf-8")
    old = conn.execute("SELECT COALESCE(LENGTH(plan_md),0) FROM tracks WHERE track_id=?",
                       (tid,)).fetchone()[0]
    conn.execute("UPDATE tracks SET plan_md=?, updated_at=datetime('now') WHERE track_id=?",
                 (body, tid))
    _audit(conn, a.actor, "update_track_plan", tid, f"план {old} → {len(body)} знаков")
    conn.commit()
    print(f"✅ план пула {tid} записан ({len(body)} знаков; было {old})")
    print("⚖️ план ПИШЕТ инициатор, СУДИТ координатор — чужую работу чужая рука")


def cmd_view(conn, a):
    tid = _pick(conn, a)
    title, status, plan, word, skills = conn.execute(
        "SELECT title, status, plan_md, owner_decision, skills FROM tracks WHERE track_id=?",
        (tid,)).fetchone()
    print(f"═══ ПУЛ {tid} [{status}] — {title}")
    if word:
        print(f"🗣 слово открытия: {word[:160]}{'…' if len(word) > 160 else ''}")
    print(f"🧰 скиллы под задачу: {skills if skills else '— НЕ НАЗВАНЫ (стартовая сводка скажет это словами)'}")
    if plan:
        head = plan.strip().splitlines()
        print("📋 план (голова):")
        for line in head[:8]:
            print(f"   {line[:110]}")
        if len(head) > 8:
            print(f"   … и ещё {len(head) - 8} строк (полностью — в поле plan_md)")
    else:
        print("📋 план: ⚠️ НЕ ЗАПИСАН — замысел живёт только в головах")

    cards = conn.execute(
        "SELECT id, role, title, status, priority, done_when FROM backlog "
        "WHERE parent_track=? ORDER BY role, id", (tid,)).fetchall()
    if not cards:
        print("🃏 карточек в пуле НЕТ — пул без частей, розданность мерить нечем")
        return
    open_cards = [c for c in cards if c[3] in OPEN_STATUSES]
    closed = [c for c in cards if c[3] in CLOSED]
    icon = {"open": "○", "in_progress": "◐", "blocked": "⛔", "awaiting_word": "🙋",
            "in_review": "👀", "done": "✅", "failed": "💥", "dropped": "✗", "frozen": "🧊"}
    print(f"🃏 части по ролям ({len(cards)} карточек, открыто {len(open_cards)}):")
    by_role = {}
    for c in cards:
        by_role.setdefault(c[1], []).append(c)
    for role in sorted(by_role):
        mark = " ⚠️ БЕЗ ХОЗЯИНА" if role == "SHARED" else ""
        rows = by_role[role]
        print(f"   {role}{mark}:")
        for bid, _r, t, st, prio, dw in rows:
            print(f"      #{bid} {icon.get(st, '?')} {t[:80]}")

    alive, overdue = _live_claims(conn, [c[0] for c in open_cards])
    if alive:
        print("🔧 живые объявления (кто где):")
        for bid, actor, until, note in alive:
            print(f"   {actor} над #{bid} до {until[11:16]} UTC: {note[:80]}")
    if overdue:
        print("⏰ ПРОСРОЧЕННЫЕ объявления (истекло, и от роли ни события — предикат вычислен сейчас):")
        for bid, actor, until, note, hours in overdue:
            print(f"   ⚠️ {actor} молчит над #{bid}, шаг истёк {hours} ч назад ({note[:60]})")
    stuck = [c for c in open_cards if c[3] in ("blocked", "awaiting_word")]
    if stuck:
        print("🚧 застрявшее (розданность и движение — разные предикаты):")
        for bid, role, t, st, _p, _dw in stuck:
            why = conn.execute("SELECT blocked_reason FROM backlog WHERE id=?", (bid,)).fetchone()[0]
            print(f"   #{bid} [{role}] {icon[st]} {t[:60]} — {why or 'причина не записана'}")
    print(f"📈 прогресс: закрыто {len(closed)} из {len(cards)} "
          f"({', '.join(f'{s} {n}' for s, n in sorted(__import__('collections').Counter(c[3] for c in cards).items()))})")
    v = conn.execute("SELECT role, kind, COUNT(*) FROM track_verdicts WHERE track_id=? "
                     "GROUP BY role, kind", (tid,)).fetchall()
    if v:
        print("⚖️ вердикты: " + " · ".join(f"{r}/{k}×{n}" for r, k, n in v))


def cmd_verdict(conn, a):
    tid = _pick(conn, a)
    body = Path(a.body_file).read_text(encoding="utf-8") if a.body_file else None
    if not a.verdict.strip():
        sys.exit("⛔ пустой вердикт не вердикт: «чисто» — тоже слово, скажи его явно")
    conn.execute("INSERT INTO track_verdicts (track_id, role, kind, verdict, body) "
                 "VALUES (?,?,?,?,?)", (tid, a.role.upper(), a.kind, a.verdict, body))
    born = None
    # Вердикт «обновить …» РОЖДАЕТ КАРТОЧКУ ТЕМ ЖЕ ХОДОМ — оценка не умирает прозой (П④)
    if a.kind == "documentation" and re.match(r"\s*обновить", a.verdict, re.I):
        cur = conn.execute(
            "INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
            "created_by, done_when) VALUES (?,?,?,?,?,?,?,?,?)",
            (a.role.upper(), a.verdict.strip()[:140],
             (body or a.verdict) + f"\n\nРождена вердиктом закрытия пула {tid} (kind=documentation).",
             "open", "normal", json.dumps(["doc-verdict"], ensure_ascii=False), tid,
             a.role.upper(),
             "Названный документ обновлён; правка показана строкой/коммитом; вердикт пула погашен ссылкой"))
        born = cur.lastrowid
    _audit(conn, a.role, "track_verdict", tid, f"{a.kind}: {a.verdict[:120]}")
    conn.commit()
    print(f"✅ вердикт записан: {tid} · {a.role.upper()} · {a.kind}: {a.verdict[:90]}")
    if born:
        print(f"🃏 рождена карточка #{born} — оценка не умирает прозой")


def _participants(conn, tid):
    """Состав участников — ЗАМЕРОМ: хозяева карточек пула + роли, оставившие события
    на карточках пула. Роль, НЕ участвовавшая, в обязанных не появляется — иначе шаг
    станет налогом на всех, и он умрёт (встречный случай П④)."""
    owners = {r[0].upper() for r in conn.execute(
        "SELECT DISTINCT role FROM backlog WHERE parent_track=?", (tid,)) if r[0] != "SHARED"}
    actors = {r[0].upper() for r in conn.execute(
        "SELECT DISTINCT e.actor_role FROM backlog_events e JOIN backlog b ON b.id=e.backlog_id "
        "WHERE b.parent_track=?", (tid,))}
    alive = {r[0].upper() for r in conn.execute(
        "SELECT role FROM roles WHERE COALESCE(lifecycle,'alive')='alive'")}
    return (owners | actors) & alive if alive else (owners | actors)


def cmd_close(conn, a):
    tid = _pick(conn, a)
    st = conn.execute("SELECT status FROM tracks WHERE track_id=?", (tid,)).fetchone()[0]
    if st == "done":
        sys.exit(f"⚖️ пул {tid} уже закрыт")
    who = sorted(_participants(conn, tid))
    have = {(r, k) for r, k in conn.execute(
        "SELECT DISTINCT role, kind FROM track_verdicts WHERE track_id=?", (tid,))}
    missing = [(r, k) for r in who for k in ("documentation", "process")
               if (r, k) not in have]
    if missing and not a.no_verdicts:
        print(f"⛔ пул {tid} НЕ закрыт: вердиктов не хватает ПОИМЁННО "
              f"(участие и есть назначение — состав замерен по карточкам и событиям):",
              file=sys.stderr)
        for r, k in missing:
            print(f"   {r}: нет вердикта «{k}» — "
                  f"track.py verdict --id {tid} --role {r} --kind {k} --verdict \"чисто\" "
                  f"(или тело проблемы)", file=sys.stderr)
        print("   Лазейка: --no-verdicts --reason \"…\" — причина обязательна, след в журнале",
              file=sys.stderr)
        sys.exit(1)
    if a.no_verdicts:
        if not (a.reason or "").strip():
            sys.exit("⛔ --no-verdicts без причины не бывает: недособранные вердикты — "
                     "решение, у решения есть почему")
        _audit(conn, a.actor, "close_track_no_verdicts", tid,
               f"закрыт БЕЗ полного набора вердиктов: {a.reason}; не хватало: "
               + ", ".join(f"{r}/{k}" for r, k in missing))
    conn.execute("UPDATE tracks SET status='done', updated_at=datetime('now') WHERE track_id=?",
                 (tid,))
    _audit(conn, a.actor, "close_track", tid, f"закрыт рукой {a.actor}")
    conn.commit()
    print(f"✅ пул {tid} закрыт")
    probs = conn.execute("SELECT role, verdict FROM track_verdicts WHERE track_id=? "
                         "AND kind='process' AND TRIM(LOWER(verdict))<>'чисто'", (tid,)).fetchall()
    if probs:
        print(f"📮 вердиктов «процесс» с проблемами: {len(probs)} — сырьё канала issues; "
              f"писатель канала ОДИН — координатор (П⑤):")
        for r, v in probs:
            print(f"   {r}: {v[:100]}")
    else:
        print("📮 проблем процесса не названо — канал issues не шумит («чисто» — явные)")


def cmd_triage(conn, a):
    pools = _active(conn)
    if not pools:
        sys.exit("⛔ активного пула нет — триаж меряет остаток ОТНОСИТЕЛЬНО пула")
    ph = ",".join("?" * len(pools))
    rows = conn.execute(
        f"SELECT id, role, title, status, "
        f"  COALESCE((SELECT MAX(at) FROM backlog_events e WHERE e.backlog_id=backlog.id), created_at) "
        f"FROM backlog WHERE status IN ({','.join('?' * len(OPEN_STATUSES))}) "
        f"AND (parent_track IS NULL OR parent_track NOT IN ({ph})) ORDER BY role, id",
        OPEN_STATUSES + pools).fetchall()
    now = conn.execute("SELECT datetime('now', '-21 days')").fetchone()[0]
    доделать = [r for r in rows if r[3] in ("in_progress", "in_review", "awaiting_word", "blocked")]
    закрыть = [r for r in rows if r[3] == "open" and r[4] <= now]
    заморозить = [r for r in rows if r not in доделать and r not in закрыть]
    total = len(rows)
    print(f"═══ ТРИАЖ остатка вне пула ({', '.join(pools)}) — открытых вне пула: {total}")
    if len(доделать) + len(закрыть) + len(заморозить) != total:
        sys.exit(f"🔴 корзины не сходятся с числом открытых дня "
                 f"({len(доделать)}+{len(закрыть)}+{len(заморозить)} ≠ {total}) — триаж НЕ ЗАКОНЧЕН, "
                 f"свод владельцу не уходит")
    print(f"   ДОДЕЛАТЬ {len(доделать)} · ЗАКРЫТЬ {len(закрыть)} · ЗАМОРОЗИТЬ {len(заморозить)} "
          f"(сумма = {total} ✅)")
    print("⚖️ триаж НИЧЕГО НЕ МЕНЯЕТ: ниже — корзины и ГОТОВЫЕ команды, решение рукой "
          "роли-хозяина за одну переходную сверку; свод — COORD владельцу")
    def block(name, items, cmd_of):
        if not items:
            return
        print(f"\n── {name} ({len(items)}):")
        by = {}
        for r in items:
            by.setdefault(r[1], []).append(r)
        for role in sorted(by):
            print(f"   [{role}]")
            for bid, _r, title, st, last in by[role]:
                print(f"      #{bid} ({st}, последнее событие {last[:10]}) {title[:70]}")
                c = cmd_of(bid, role)
                if c:
                    print(f"         {c}")
    block("ДОДЕЛАТЬ — до критерия приёмки или ближайшей записанной точки", доделать,
          lambda b, r: None)
    # Печатаемые команды — ПРЯМЫМИ косыми (as_posix): смешанные `C:\…\scripts/имя.py`
    # в bash-инструменте мертвы — ровно класс E сторожа печатных форм, пойман смоком.
    block("ЗАКРЫТЬ — открыта без событий >21 суток («отпала», с причиной)", закрыть,
          lambda b, r: f"python {S.as_posix()}/backlog.py status {b} dropped --actor {r} --note \"отпала: <почему>\"")
    block("ЗАМОРОЗИТЬ — вне пула, с ОБЯЗАТЕЛЬНЫМ условием разморозки", заморозить,
          lambda b, r: f"python {S.as_posix()}/backlog.py status {b} frozen --actor {r} --note \"условие разморозки: <какое>\"")


def main():
    ap = argparse.ArgumentParser(description="Пул как рабочая единица (П③)")
    ap.add_argument("--db", default=None, help="необязателен: путь резолвится от скрипта (R15a)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open", help="открыть пул")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--plan-file")
    p.add_argument("--skills", help="скиллы под задачу (П⑥, стартовая сводка)")
    p.add_argument("--word", help="слово владельца, которым пул открыт, С ЧАСОМ UTC")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("plan", help="записать словесный слой плана")
    p.add_argument("--id")
    p.add_argument("--actor", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("view", help="просмотр пула: план, части по ролям, кто над чем, застрявшее")
    p.add_argument("--id")

    p = sub.add_parser("verdict", help="вердикт закрытия (documentation | process)")
    p.add_argument("--id")
    p.add_argument("--role", required=True)
    p.add_argument("--kind", required=True, choices=["documentation", "process"])
    p.add_argument("--verdict", required=True, help="«чисто» — тоже вердикт, явный")
    p.add_argument("--body-file")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("close", help="закрыть пул (не закроется без вердиктов участников)")
    p.add_argument("--id")
    p.add_argument("--actor", required=True)
    p.add_argument("--no-verdicts", action="store_true")
    p.add_argument("--reason")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("triage", help="три корзины остатка вне пула (П①); ничего не меняет")

    a = ap.parse_args()
    conn = _conn(resolve_db(a.db, __file__), getattr(a, "dry_run", False))
    try:
        {"open": cmd_open, "plan": cmd_plan, "view": cmd_view,
         "verdict": cmd_verdict, "close": cmd_close, "triage": cmd_triage}[a.cmd](conn, a)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
