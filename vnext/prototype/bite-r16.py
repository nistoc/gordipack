# -*- coding: utf-8 -*-
"""
bite-r16.py — укус для R16: что делает ПОВТОРНЫЙ вызов ридера с уже выданным батчем.

Полевой факт (opssre #2670): ack, собранный одной командой с подстановкой
`$(read-messages … | tail -1)`, был отклонён — подстановка сама вызвала ридер.
Формулировка автора: «выдал новый батч с новым токеном и погасил предыдущий».
Здесь это ПРОВЕРЯЕТСЯ ЗАМЕРОМ, а не переносится на веру (VERIFY-AT-SOURCE):
важно, отклоняется ли СТАРЫЙ токен, или ломается именно склейка половин от разных вызовов.

Работает ТОЛЬКО по песочнице. Предусловия проверяются; не выполнены — выход с кодом 2.

    python bite-r16.py --sandbox <корень песочницы>
"""
import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROLE = "PROTO"


def run(script, args, cwd):
    p = subprocess.run([sys.executable, str(script), *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def halves(text):
    """Половинки разрезанного токена: первая — в первой строке, вторая — в последней."""
    h1 = re.search(r"ПЕРВАЯ половина ([0-9a-f]+)", text)
    h2 = re.search(r"--ack <первая>-([0-9a-f]+)|ack <первая>-([0-9a-f]+)", text)
    return (h1.group(1) if h1 else None,
            (h2.group(1) or h2.group(2)) if h2 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", default=str(Path.home() / ".mezosync-sandbox"))
    a = ap.parse_args()
    sb = Path(a.sandbox).resolve()
    db = sb / "mezosync.db"
    live_reader = sb / "scripts" / "read-messages.py"
    proto_reader = Path(__file__).resolve().parent / "feed.py"

    problems = []
    if not db.exists():
        problems.append(f"нет песочницы: {db}")
    if not live_reader.exists():
        problems.append(f"нет копии живого ридера: {live_reader}")
    if not proto_reader.exists():
        problems.append(f"нет прототипа: {proto_reader}")
    if problems:
        print("⛔ УКУС НЕ ПОСТАВЛЕН:")
        [print("   ·", p) for p in problems]
        sys.exit(2)

    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM read_batches WHERE role = ?", (ROLE,))       # чистая исходная позиция
    con.commit()
    cur0 = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                       (ROLE,)).fetchone()[0]
    con.close()
    print(f"[укус R16] песочница {db}, курсор {ROLE} = {cur0}\n")

    # ── ДО: живой ридер
    print("── ДО (живой ридер): два вызова подряд")
    _, out1 = run(live_reader, ["--db", str(db), "--role", ROLE, "--limit", "3"], cwd=sb)
    a1, b1 = halves(out1)
    _, out2 = run(live_reader, ["--db", str(db), "--role", ROLE, "--limit", "3"], cwd=sb)
    a2, b2 = halves(out2)
    print(f"   вызов 1 → токен {a1}-{b1}")
    print(f"   вызов 2 → токен {a2}-{b2}   {'(ДРУГОЙ)' if (a1, b1) != (a2, b2) else '(тот же)'}")

    rc, out = run(live_reader, ["--db", str(db), "--role", ROLE, "--ack", f"{a1}-{b1}"], cwd=sb)
    print(f"   ack токеном ПЕРВОГО вызова → rc={rc}: {out.strip().splitlines()[0]}")
    rc, out = run(live_reader, ["--db", str(db), "--role", ROLE, "--ack", f"{a1}-{b2}"], cwd=sb)
    print(f"   ack СКЛЕЙКОЙ из разных вызовов (a1+b2) → rc={rc}: {out.strip().splitlines()[0]}")
    print("   ⇒ вот в чём ловушка подстановки: половинки берутся из РАЗНЫХ вызовов,")
    print("     и склейка невалидна — при том что роль всё делала аккуратно.\n")

    # вернуть курсор на исходную позицию, чтобы вторая половина укуса стартовала одинаково
    con = sqlite3.connect(str(db))
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (cur0, ROLE))
    con.execute("DELETE FROM read_batches WHERE role = ?", (ROLE,))
    con.commit()
    con.close()

    # ── ПОСЛЕ: прототип с R16
    print("── ПОСЛЕ (прототип, R16): два вызова подряд")
    _, p1 = run(proto_reader, ["--db", str(db), "--role", ROLE, "--budget-kb", "6", "index"], cwd=sb)
    c1, d1 = halves(p1)
    _, p2 = run(proto_reader, ["--db", str(db), "--role", ROLE, "--budget-kb", "6", "index"], cwd=sb)
    c2, d2 = halves(p2)
    print(f"   вызов 1 → токен {c1}-{d1}")
    print(f"   вызов 2 → токен {c2}-{d2}   {'(ТОТ ЖЕ ✅)' if (c1, d1) == (c2, d2) else '(другой ⛔)'}")
    if "ПОВТОРНАЯ выдача" in p2:
        print("   вызов 2 честно назвал себя повторной выдачей того же батча")
    rc, out = run(proto_reader, ["--db", str(db), "--role", ROLE, "ack", f"{c1}-{d1}"], cwd=sb)
    print(f"   ack токеном ПЕРВОГО вызова → rc={rc}: {out.strip().splitlines()[0]}")
    rc, out = run(proto_reader, ["--db", str(db), "--role", ROLE, "ack", f"{c1}-{d1}"], cwd=sb)
    print(f"   повторный ack тем же токеном → rc={rc}: {out.strip().splitlines()[0]}")
    print("   ⇒ выдача идемпотентна, гашение — одноразово. Подстановка перестала быть ловушкой.")


if __name__ == "__main__":
    main()
