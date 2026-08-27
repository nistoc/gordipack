# -*- coding: utf-8 -*-
# PLANTS: phoenix
"""ПРИЁМКА сторожа объёма памяти (guard-phoenix-volume.py, заход 4 ⑨).

Порог назван ЧИСЛОМ здесь же: 20 000 знаков на раздел. Судим по ПОДСАЖЕННОМУ
разделу в песочной базе, не по живому жиру: живой замер меняется чужими руками.
"""
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "guard-phoenix-volume.py"
LIMIT = 20_000

CASES, OK = 0, True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")


def stand(tmp, name, sections):
    db = Path(tmp) / f"{name}.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, "
                "saved_at TEXT, confirmed_at TEXT)")
    con.execute("CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, role TEXT, "
                "section TEXT, body TEXT, body_chars INT, saved_at TEXT, actor TEXT, "
                "reason TEXT, prev_chars INT)")
    for role, sec, n in sections:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'),NULL)",
                    (role, sec, "ж" * n))
    con.commit()
    con.close()
    return db


def run(db):
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-pvol-")

    db = stand(tmp, "fat", [("ZZFAT", "state", LIMIT + 5000), ("ZZOK", "state", 900)])
    out, code = run(db)
    case("① раздел толще порога (20000) → красное ПОИМЁННО (роль · раздел · размер)",
         code == 1 and "ZZFAT" in out and "state" in out and str(LIMIT + 5000) in out)
    case("② встречный: тонкий раздел соседа НЕ обвинён",
         "ZZOK" not in out.split("🔴")[-1] if "🔴" in out else False,
         "долг поимённый, не облавой")

    db = stand(tmp, "thin", [("ZZAA", "state", 900), ("ZZBB", "plan", 1500)])
    out, code = run(db)
    case("③ встречный: все разделы под порогом → 0 долга, код 0",
         code == 0 and "раздутых: 0" in out)

    db = stand(tmp, "empty", [])
    out, code = run(db)
    case("④ свежая база БЕЗ разделов → «мерить нечего» кодом 2, не «чисто»",
         code == 2 and "НОЛЬ разделов" in out,
         "пустота — не раздутость, но и не зелёное")

    db = stand(tmp, "hint", [("ZZFAT", "state", LIMIT + 1)])
    out, code = run(db)
    case("⑤ красное несёт ПУТЬ СЖАТИЯ, не «сотри»: allow-shrink + phoenix_history",
         "allow-shrink" in out and "phoenix_history" in out,
         "вынесенное не теряется — прежнее тело кладёт в историю сам save-phoenix "
         "(его механизм, его приёмка)")

    out, code = run(Path(tmp) / "нет-такой.db")
    case("⑥ базы нет → «НЕ ПРОВЕРЕНО» кодом 2, а не «чисто»", code == 2)

    print()
    print(f"{'✅ СТОРОЖ ОБЪЁМА ПРИНЯТ' if OK else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}")
    if OK:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"📂 стенд сохранён: {tmp}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
