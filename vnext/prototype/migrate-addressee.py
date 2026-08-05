# -*- coding: utf-8 -*-
"""
migrate-addressee.py — backfill адресата ПОЛЕМ из прозы (Э-Б, R3, F6).

⛔ ПРОТОТИП. Источник — ТОЛЬКО песочница (`vnext/sandbox/bootstrap.py`), живой субстрат
   не трогает: по умолчанию отказывается открывать боевой путь (тот же гард, что в
   feed.py). Цель — вторая половина «покажи адресованное мне», доказанная НА РЕАЛЬНЫХ
   данных, а не на синтетике.

ЧТО ДЕЛАЕТ:
  1. Применяет schema_vnext.sql к НОВОЙ (или --force пересозданной) целевой БД.
  2. Копирует роли (объединение writer_role из messages + reader_role из read_cursors
     песочницы) в target.roles — источник состава честнее, чем список в комментарии.
  3. Копирует КАЖДУЮ ноту messages в target как есть (id/writer_role/timestamp/body_md/
     tags/priority/resolved), addressed_by='backfill'.
  4. Разбирает прозу тела на (to, cc, broadcast) и заполняет message_addressee —
     СМ. `parse_addressee()` ниже, там же граница метода.
  5. Печатает ЗАМЕР, не рапорт: сколько нот всего, сколько адресовано каждой роли,
     сколько broadcast, сколько «долг адресации» (messages_unaddressed).

ГРАНИЦА ЧЕСТНО (урок AIA §3.1, «детектор не отличает употребление от упоминания» —
и он живёт ЗДЕСЬ, в моём же парсере, а не только у них):
  · `to` берётся из ЗАГОЛОВКА первой строки — паттерн `[ПИШЕТ→КОМУ · …]`, ровно та
    форма, которой контур пишет девятый месяц. Нет заголовка ⇒ `to` пуст, нота уходит
    в messages_unaddressed (честный долг, не угаданный адресат).
  · `cc` — явные `@РОЛЬ` ПОСЛЕ слова «cc» (регистронезависимо) до конца строки/абзаца.
  · Любое ДРУГОЕ упоминание `@РОЛЬ` в теле (обращение по ходу текста, а не в шапке
    и не после cc) НЕ считается адресатом. Это заведомо теряет часть адресации —
    отмечено числом `loose_mentions` в замере, не молчанием.
  · `@ALL` / `@все` / `@ВСЕ` где угодно в теле ⇒ broadcast=1 (это уже проверенный
    шим из feed.py, менять не стал — он работал на реальных данных).

    python migrate-addressee.py --sandbox C:\\Users\\<user>\\.mezosync-sandbox\\mezosync.db
                                 --target  C:\\Users\\<user>\\.mezosync-sandbox\\vnext-demo.db --force
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "schema_vnext.sql"
LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")

# ФОРМА A: «[ПИШЕТ→КОМУ · FYI …]» — шапка со стрелкой.
HEADER_RE = re.compile(r"^\W*\[?\s*(\w+)\s*→\s*([^\]·\n]+)", re.MULTILINE)
# ФОРМА B: «<эмодзи> @КОМУ [@КОМУ…] — текст» в ПЕРВОЙ строке. Добавлена 2026-08-05
# по вопросу владельца «корректно ли коллеги заполняют адресата»: на свежих нотах
# парсер давал 8 «долгов» из 18 — и ВСЕ восемь несли совершенно явный `@РОЛЬ` сразу
# после эмодзи. Конвенций живых ДВЕ, а знал я одну. Класс мой же, оплаченный дважды
# за сутки: **измеритель проверяет свою модель предмета, а не предмет**.
FORM_B_RE = re.compile(r"^[^\n@]{0,12}((?:@\w+[\s,/]*)+)[—\-–]")
CC_RE = re.compile(r"\bcc\b[^\n]*", re.IGNORECASE)
AT_ROLE_RE = re.compile(r"@(\w+)\b")
BROADCAST_RE = re.compile(r"@ALL\b|@все\b|@ВСЕ\b")


def parse_addressee(body: str, known_roles: set) -> tuple:
    """Возвращает (to: set[str], cc: set[str], broadcast: bool, loose: set[str]).

    loose — роли, упомянутые `@РОЛЬ` вне шапки и вне «cc»-хвоста: НЕ адресат,
    только материал для замера потерь метода.
    """
    to, cc = set(), set()
    m = HEADER_RE.search(body)
    header_span = m.span() if m else None
    if m:
        for tok in re.split(r"[\/,·\s]+", m.group(2)):
            tok = tok.strip().upper()
            if tok in known_roles:
                to.add(tok)

    # ФОРМА B — равноправная живая конвенция, не запасной вариант: проверяется всегда,
    # а не «если A не сработала». Нота может нести обе (замер 05.08: пересечений 0,
    # но конструкция не должна на это опираться — конвенции живут независимо).
    first_line = body.splitlines()[0] if body else ""
    mb = FORM_B_RE.match(first_line)
    if mb:
        b_span = (0, mb.end(1))
        for role in re.findall(r"@(\w+)", mb.group(1)):
            role = role.upper()
            if role in known_roles:
                to.add(role)
        if header_span is None:
            header_span = b_span

    cc_span = None
    cm = CC_RE.search(body)
    if cm:
        cc_span = cm.span()
        for role in AT_ROLE_RE.findall(cm.group(0)):
            role = role.upper()
            if role in known_roles:
                cc.add(role)

    loose = set()
    for mm in AT_ROLE_RE.finditer(body):
        role = mm.group(1).upper()
        if role not in known_roles or role in to or role in cc:
            continue
        inside_header = header_span and header_span[0] <= mm.start() < header_span[1]
        inside_cc = cc_span and cc_span[0] <= mm.start() < cc_span[1]
        if not inside_header and not inside_cc:
            loose.add(role)

    broadcast = bool(BROADCAST_RE.search(body))
    return to, cc, broadcast, loose


def connect_source(path: Path) -> sqlite3.Connection:
    if path.resolve() == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: источник — ЖИВАЯ mezosync.db. Только песочница "
                 "(vnext/sandbox/bootstrap.py). Мандат PROTO: живой субстрат — только чтение.")
    if not path.exists():
        sys.exit(f"ERR: источник не найден: {path}. Подними песочницу: python vnext/sandbox/bootstrap.py")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def build_target(path: Path, force: bool) -> sqlite3.Connection:
    if path.exists():
        if not force:
            sys.exit(f"ERR: {path} уже существует. --force для пересоздания (это НЕ живая БД).")
        path.unlink()
    if not SCHEMA_FILE.exists():
        sys.exit(f"ERR: схема не найдена: {SCHEMA_FILE}")
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    return con


def migrate(src: sqlite3.Connection, dst: sqlite3.Connection) -> dict:
    roles = {r for r, in src.execute(
        "SELECT DISTINCT writer_role FROM messages "
        "UNION SELECT DISTINCT reader_role FROM read_cursors")}
    for role in sorted(roles):
        dst.execute("INSERT OR IGNORE INTO roles (role) VALUES (?)", (role,))

    rows = src.execute(
        "SELECT id, writer_role, timestamp, body_md, tags, priority, resolved "
        "FROM messages ORDER BY id").fetchall()

    stats = {"total": len(rows), "to": 0, "cc": 0, "broadcast": 0, "loose_total": 0,
              "loose_hist": {}, "per_role_to": {}, "per_role_cc": {}}

    for mid, writer, ts, body, tags, prio, resolved in rows:
        to, cc, bcast, loose = parse_addressee(body or "", roles)
        dst.execute(
            "INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority, "
            "resolved, broadcast, addressed_by) VALUES (?,?,?,?,?,?,?,?, 'backfill')",
            (mid, writer, ts, body, tags, prio, resolved, int(bcast)))
        for role in to:
            dst.execute("INSERT OR IGNORE INTO message_addressee (message_id, role, kind) "
                        "VALUES (?,?,'to')", (mid, role))
            stats["per_role_to"][role] = stats["per_role_to"].get(role, 0) + 1
        for role in cc:
            dst.execute("INSERT OR IGNORE INTO message_addressee (message_id, role, kind) "
                        "VALUES (?,?,'cc')", (mid, role))
            stats["per_role_cc"][role] = stats["per_role_cc"].get(role, 0) + 1
        if to:
            stats["to"] += 1
        if cc:
            stats["cc"] += 1
        if bcast:
            stats["broadcast"] += 1
        if loose:
            stats["loose_total"] += 1
            for role in loose:
                stats["loose_hist"][role] = stats["loose_hist"].get(role, 0) + 1
    dst.commit()
    return stats


def report(dst: sqlite3.Connection, stats: dict) -> None:
    total = stats["total"]
    unaddressed = dst.execute("SELECT COUNT(*) FROM messages_unaddressed").fetchone()[0]
    print(f"── ЗАМЕР ПОСЛЕ BACKFILL (не оценка, SELECT по target) ──")
    print(f"всего нот ................ {total}")
    print(f"хотя бы один to .......... {stats['to']} ({100*stats['to']/total:.1f}%)")
    print(f"хотя бы один cc .......... {stats['cc']} ({100*stats['cc']/total:.1f}%)")
    print(f"broadcast ................ {stats['broadcast']} ({100*stats['broadcast']/total:.1f}%)")
    print(f"ДОЛГ (ни to/cc, ни broadcast, messages_unaddressed) ... "
          f"{unaddressed} ({100*unaddressed/total:.1f}%)")
    print(f"loose-упоминания (не адресат, потеря метода) .......... "
          f"{stats['loose_total']} нот несут хотя бы одно")
    print()
    print("── АДРЕСОВАНО РОЛИ (to+cc), топ по факту — вот ради чего всё ──")
    all_roles = set(stats["per_role_to"]) | set(stats["per_role_cc"])
    for role in sorted(all_roles):
        n_to = stats["per_role_to"].get(role, 0)
        n_cc = stats["per_role_cc"].get(role, 0)
        n = n_to + n_cc
        pct = 100 * n / total
        print(f"  {role:8s} to={n_to:5d} cc={n_cc:5d} итого={n:5d} ({pct:5.1f}% ленты — "
              f"столько ей НЕ обязательно читать по умолчанию)")


def main():
    ap = argparse.ArgumentParser(description="Backfill адресата полем на реальных данных (Э-Б)")
    ap.add_argument("--sandbox", required=True, help="источник — БД песочницы (read-only)")
    ap.add_argument("--target", required=True, help="целевая БД v-next (создаётся заново)")
    ap.add_argument("--force", action="store_true", help="пересоздать target, если существует")
    args = ap.parse_args()

    src = connect_source(Path(args.sandbox))
    dst = build_target(Path(args.target), args.force)
    stats = migrate(src, dst)
    report(dst, stats)
    src.close()
    dst.close()


if __name__ == "__main__":
    main()
