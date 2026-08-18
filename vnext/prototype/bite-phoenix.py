# -*- coding: utf-8 -*-
"""
bite-phoenix.py — приёмки для Э-А: смерть без свёртки (R6) и неубиваемая история (R7).

Сценарии (оба — на песочнице, живое не трогается):
  ① СМЕРТЬ БЕЗ СВЁРТКИ. Роль работает, пишет ноты, двигает курсор — и обрывается, НЕ сохранив
     слепок. Сравниваем, что увидит следующая инкарнация: старый ручной слепок против derived.
  ② ЗАТЁРТЫЙ СЛЕПОК. Сегодня `save-phoenix` перезаписывает секцию без следа. Проверяем:
     старое тело восстановимо? (до R7 — нет; после — да, и откат сам становится новой версией).

Предусловия проверяются; не выполнены — выход rc=2 (укус не поставлен, а не «зелено»).
"""
import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

PROTO = Path(__file__).resolve().parent / "phoenix-vnext.py"
ROLE = "STUD"          # роль, которая 2026-07-25 реально умерла без свёртки


def run(args, **kw):
    p = subprocess.run([sys.executable, str(PROTO), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", default=str(Path.home() / ".mezosync-sandbox"))
    a = ap.parse_args()
    db = (Path(a.sandbox) / "mezosync.db").resolve()

    if not db.exists():
        print(f"⛔ ПРИЁМКА НЕ ПОСТАВЛЕНА: нет песочницы {db}")
        sys.exit(2)
    con = sqlite3.connect(str(db))
    if not con.execute("SELECT 1 FROM phoenix WHERE role=? LIMIT 1", (ROLE,)).fetchone():
        print(f"⛔ ПРИЁМКА НЕ ПОСТАВЛЕНА: в песочнице нет сохранённой памяти роли {ROLE}")
        sys.exit(2)

    print("═" * 78)
    print("① СМЕРТЬ БЕЗ СВЁРТКИ — что увидит следующая инкарнация")
    print("═" * 78)
    saved_at, n = con.execute(
        "SELECT saved_at, LENGTH(body) FROM phoenix WHERE role=? AND section='state'",
        (ROLE,)).fetchone()
    last_note = con.execute(
        "SELECT MAX(timestamp) FROM messages WHERE writer_role=?", (ROLE,)).fetchone()[0]
    n_after = con.execute(
        "SELECT COUNT(*) FROM messages WHERE writer_role=? AND timestamp > ?",
        (ROLE, saved_at)).fetchone()[0]
    print(f"  РУЧНАЯ запись памяти {ROLE}/state:  сохранена {saved_at} UTC, {n} симв.")
    print(f"  последняя нота роли:        {last_note} UTC")
    print(f"  ⇒ после сохранения памяти роль дала ещё {n_after} нот — в памяти их НЕТ.")
    print(f"     Это и есть дрейф: память честна о себе и молчит о мире.\n")
    rc, out = run(["--db", str(db), "derive", "--role", ROLE])
    body = [l for l in out.splitlines() if l.strip()]
    print(f"  DERIVED (rc={rc}) — собран сейчас, {len(out)} симв., ничего не переписывалось руками:")
    for line in body[3:14]:
        print("    " + line)
    print(f"    … всего {len(body)} строк\n")

    print("═" * 78)
    print("② ЗАТЁРТАЯ ПАМЯТЬ — восстановимо ли прежнее")
    print("═" * 78)
    tmp = Path(a.sandbox) / "_bite_state.md"

    # ДО: как сегодня — прямой ON CONFLICT DO UPDATE, без истории
    before = con.execute("SELECT body FROM phoenix WHERE role=? AND section='plan'",
                         (ROLE,)).fetchone()[0]
    con.execute("""INSERT INTO phoenix (role, section, body, saved_at)
                   VALUES (?,?,?,datetime('now'))
                   ON CONFLICT(role, section) DO UPDATE SET body=excluded.body""",
                (ROLE, "plan", "ЗАТЁРТО (имитация неаккуратного сохранения)"))
    con.commit()
    has_hist = con.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='phoenix_history'"
    ).fetchone()[0]
    print(f"  ДО (сегодняшний save-phoenix): секция затёрта. Прежнее тело ({len(before)} симв.) "
          f"восстановимо? {'нет — истории не существует' if not has_hist else 'см. ниже'}")
    print(f"     в audit_log попадает только длина — расследовать нечем\n")

    # ПОСЛЕ: возвращаем прежнее через версионируемое сохранение и проверяем историю
    tmp.write_text(before, encoding="utf-8")
    rc, out = run(["--db", str(db), "save", "--role", ROLE, "--section", "plan",
                   "--file", str(tmp), "--reason", "восстановление после укуса"])
    print(f"  ПОСЛЕ (версионируемое сохранение) rc={rc}: {out.strip()}")
    rc, out = run(["--db", str(db), "history", "--role", ROLE, "--section", "plan"])
    print("  история секции:")
    for line in out.strip().splitlines():
        print("    " + line)

    v1 = con.execute("SELECT MIN(version) FROM phoenix_history WHERE role=? AND section='plan'",
                     (ROLE,)).fetchone()[0]
    if v1:
        rc, out = run(["--db", str(db), "restore", "--role", ROLE, "--section", "plan",
                       "--version", str(v1)])
        print(f"  откат к v{v1} rc={rc}: {out.strip()}")
        rc, out = run(["--db", str(db), "history", "--role", ROLE, "--section", "plan"])
        print(f"  ⇒ история после отката (откат — НОВАЯ версия, прошлое не переписано):")
        for line in out.strip().splitlines()[-3:]:
            print("    " + line)
    tmp.unlink(missing_ok=True)
    con.close()


if __name__ == "__main__":
    main()
