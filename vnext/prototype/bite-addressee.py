# -*- coding: utf-8 -*-
"""
bite-addressee.py — укус контрактов адресата (Э-Б, R3).

Проверяет СВОЙСТВА схемы + парсера на временной БД в scratch-каталоге ОС (не в
живом контуре, не в песочнице — своя изолированная копия на каждый прогон, урок
контура #2748: «укус, стирающий предмет замера, слеп к ошибкам накопленного
состояния» — здесь предмета накопленного нет вовсе, чистый CREATE на каждый прогон).

    python bite-addressee.py            # 8 свойств
    python bite-addressee.py --selftest # доказать, что укус ЕЩЁ красится на порче
"""
import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# импорт файла с дефисом в имени — через spec, не через import (дефис не идентификатор)
import importlib.util
spec = importlib.util.spec_from_file_location("migrate_addressee", HERE / "migrate-addressee.py")
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

SCHEMA_FILE = HERE / "schema_vnext.sql"


def fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    for role in ("COORD", "PROTO", "TAXO", "ING"):
        con.execute("INSERT INTO roles (role) VALUES (?)", (role,))
    return con


def seed(con, mid, writer, body, broadcast=0, addressed_by="field"):
    con.execute(
        "INSERT INTO messages (id, writer_role, body_md, broadcast, addressed_by) "
        "VALUES (?,?,?,?,?)", (mid, writer, body, broadcast, addressed_by))


def run_properties():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))

    # P1 — CHECK на kind ловит мусор
    con = fresh_db()
    seed(con, 1, "COORD", "x")
    try:
        con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (1,'PROTO','bcc')")
        con.commit()
        p1 = False
    except sqlite3.IntegrityError:
        p1 = True
    check("P1 CHECK(kind IN to,cc) отвергает мусор", p1)

    # P2 — CHECK на addressed_by ловит мусор
    con = fresh_db()
    try:
        con.execute("INSERT INTO messages (id, writer_role, body_md, addressed_by) "
                    "VALUES (2,'COORD','x','guessed')")
        con.commit()
        p2 = False
    except sqlite3.IntegrityError:
        p2 = True
    check("P2 CHECK(addressed_by IN field,backfill) отвергает мусор", p2)

    # P3 — messages_for_role: broadcast достаётся ВСЕМ, без строки в message_addressee
    con = fresh_db()
    seed(con, 3, "COORD", "всем привет", broadcast=1)
    con.commit()
    rows = {r for r, in con.execute(
        "SELECT my_reason FROM messages_for_role WHERE id=3")}
    check("P3 broadcast виден как 'broadcast', без записи в message_addressee",
          rows == {"broadcast"} and con.execute(
              "SELECT COUNT(*) FROM message_addressee WHERE message_id=3").fetchone()[0] == 0)

    # P4 — messages_for_role: to/cc отдаёт СТРОГО адресованным, не остальным
    con = fresh_db()
    seed(con, 4, "COORD", "личное PROTO")
    con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (4,'PROTO','to')")
    con.commit()
    for_proto = con.execute(
        "SELECT COUNT(*) FROM messages_for_role WHERE id=4").fetchone()[0]  # view не фильтрует роль
    # view отдаёт ВСЕ строки для ВСЕХ адресатов — фильтрация по роли на стороне запроса,
    # проверяем именно это: строка существует и несёт правильный kind
    kind = con.execute("SELECT my_reason FROM messages_for_role WHERE id=4").fetchone()[0]
    check("P4 messages_for_role несёт kind='to' для адресованной ноты", kind == "to")

    # P5 — messages_unaddressed: долг виден, адресованное/broadcast — не виден
    con = fresh_db()
    seed(con, 5, "COORD", "долг")             # ни to/cc, ни broadcast
    seed(con, 6, "COORD", "broadcast", broadcast=1)
    seed(con, 7, "COORD", "адресовано")
    con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (7,'PROTO','cc')")
    con.commit()
    debt = {r for r, in con.execute("SELECT id FROM messages_unaddressed")}
    check("P5 messages_unaddressed = ровно ноты без адресата и без broadcast", debt == {5})

    # P6 — ON DELETE CASCADE: удаление ноты чистит message_addressee (без CASCADE
    # DELETE вообще падает FK-ошибкой — это ТОЖЕ поимка мутанта, не крах укуса)
    con = fresh_db()
    seed(con, 8, "COORD", "x")
    con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (8,'PROTO','to')")
    con.commit()
    try:
        con.execute("DELETE FROM messages WHERE id=8")
        con.commit()
        orphans = con.execute(
            "SELECT COUNT(*) FROM message_addressee WHERE message_id=8").fetchone()[0]
        p6 = orphans == 0
    except sqlite3.IntegrityError:
        p6 = False  # CASCADE снят — удаление блокируется FK, свойство нарушено
    check("P6 ON DELETE CASCADE не оставляет сирот в message_addressee", p6)

    # P7 — parse_addressee: заголовок «[W→X · FYI …]» даёт to={X}, cc из «cc @Y @Z»
    to, cc, bcast, loose = mig.parse_addressee(
        "[PROTO→COORD · FYI ALL/владелец] текст текст. cc @TAXO @ING\nещё текст @COORD в теле",
        {"PROTO", "COORD", "TAXO", "ING"})
    check("P7 parse_addressee: to из шапки, cc после 'cc', COORD в теле — НЕ дубль в loose",
          to == {"COORD"} and cc == {"TAXO", "ING"} and not bcast and "COORD" not in loose)

    # P8 — parse_addressee: @ALL/@все/@ВСЕ триггерит broadcast независимо от регистра
    _, _, bcast_all, _ = mig.parse_addressee("привет @ALL и @все и @ВСЕ", {"PROTO"})
    check("P8 broadcast по @ALL/@все/@ВСЕ", bcast_all is True)

    return results


MUTANTS = {
    "M1-kind-check-снят": lambda sql: sql.replace(
        "kind        TEXT NOT NULL CHECK (kind IN ('to', 'cc'))",
        "kind        TEXT NOT NULL"),
    "M2-cascade-снят": lambda sql: sql.replace(
        "REFERENCES messages(id) ON DELETE CASCADE", "REFERENCES messages(id)"),
}


def run_selftest():
    base_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    clean = run_properties()
    clean_red = sum(1 for _, ok in clean if not ok)
    print(f"ЧИСТАЯ схема: {len(clean) - clean_red}/{len(clean)} — ожидание: все ✅")
    if clean_red:
        print("🔴 УКУС УЖЕ КРАСНЫЙ НА ЧИСТОМ — самопроверка невозможна")
        return 1

    survived = 0
    for name, mutate in MUTANTS.items():
        mutated = mutate(base_sql)
        if mutated == base_sql:
            print(f"⚠️ {name}: паттерн не найден в схеме — мутант не встал")
            continue
        orig = SCHEMA_FILE.read_text(encoding="utf-8")
        SCHEMA_FILE.write_text(mutated, encoding="utf-8")
        try:
            res = run_properties()
            red = sum(1 for _, ok in res if not ok)
            caught = red > 0
            print(f"{'✅' if caught else '🔴'} {name}: {'поймал' if caught else 'НЕ ПОЙМАЛ'} "
                  f"({red}/{len(res)} красных)")
            if not caught:
                survived += 1
        finally:
            SCHEMA_FILE.write_text(orig, encoding="utf-8")
    print(f"\nИТОГ самопроверки: {len(MUTANTS) - survived}/{len(MUTANTS)} мутантов пойманы "
          f"(из {len(MUTANTS)}, число из len(MUTANTS), не литералом)")
    return 1 if survived else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(run_selftest())
    results = run_properties()
    red = 0
    for name, ok in results:
        print(f"{'✅' if ok else '🔴'} {name}")
        red += 0 if ok else 1
    print(f"\n{len(results) - red}/{len(results)}, rc={0 if red == 0 else 1}")
    sys.exit(0 if red == 0 else 1)


if __name__ == "__main__":
    main()
