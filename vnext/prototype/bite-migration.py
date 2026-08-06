# -*- coding: utf-8 -*-
"""
bite-migration.py — укус на РАСХОЖДЕНИЕ ЭТАЛОНА И МИГРАЦИИ.

🪤 ПОЧЕМУ ЭТОТ УКУС СУЩЕСТВУЕТ — ОН ОПЛАЧЕН ЖИВЫМ СЛУЧАЕМ 2026-08-06.
В эталонной схеме рядом с полем «критерий готовности» лежала витрина «открытые задачи
без критерия». В шаг переноса она НЕ ПОПАЛА. При этом три роли подряд — я первым —
писали в общий канал, что витрина показывает долг, и строили на ней предложения владельцу.
Проверялось ОДНИМ запросом к списку витрин; его не сделал никто.

> **Механизм, существующий в эталоне, пересказывается как существующий в системе.**
> Не ловится ни укусом поведения, ни счётом выполненных проверок: нечего запускать,
> чтобы обнаружить отсутствие. Ловится ПЕРЕЧИСЛЕНИЕМ, а не обращением.

⇒ Этот укус и есть перечисление, сделанное механизмом: он строит базу ДВУМЯ путями —
эталонной схемой и миграцией со старой версии — и сверяет, что новые объекты совпадают.
Расхождение больше не может прожить незамеченным до чьей-то ссылки на него в разговоре.

    python bite-migration.py            # свойства
    python bite-migration.py --selftest # доказать, что укус умеет краснеть
"""
import argparse
import importlib.util
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "schema_vnext.sql"
MIGRATE_FILE = HERE / "migrate-live.py"

_spec = importlib.util.spec_from_file_location("migrate_live", MIGRATE_FILE)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)

# Объекты, которые ОБЯЗАНЫ появиться в v3 обоими путями. Список явный, а не выведенный:
# выведенный список молча сократился бы вместе с ошибкой, которую должен ловить.
V3_TABLES = ["roles", "cursor_segments", "message_thread", "message_task"]
V3_VIEWS = ["schema_version", "backlog_without_criterion"]
V3_COLUMNS = [("messages", "broadcast"), ("messages", "addressed_by"),
              ("backlog", "done_when")]


def norm(sql: str) -> str:
    """Определение объекта без пробелов и комментариев: сравниваем СМЫСЛ, а не вёрстку."""
    s = re.sub(r"--[^\n]*", " ", sql or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def build_reference():
    """Путь A: база, собранная ЭТАЛОННОЙ схемой."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    return con


def build_migrated(tmpdir):
    """Путь B: база v2, проведённая ЧЕРЕЗ МИГРАЦИЮ.

    Старая база строится минимально, но по образцу живой: те таблицы, на которые
    миграция опирается. Если миграция начнёт опираться на что-то ещё — она упадёт
    здесь, а не на чужой рабочей базе.
    """
    p = Path(tmpdir) / "v2.db"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')), body_md TEXT NOT NULL,
            tags TEXT DEFAULT '[]', priority TEXT DEFAULT 'normal', resolved INTEGER DEFAULT 0);
        CREATE TABLE read_cursors (reader_role TEXT, last_read_id INTEGER);
        CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT);
        CREATE TABLE backlog (id INTEGER PRIMARY KEY, role TEXT NOT NULL, title TEXT NOT NULL,
            body_md TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'normal', tags TEXT DEFAULT '[]',
            created_by TEXT NOT NULL DEFAULT 'coord',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE rules (rule_key TEXT, body TEXT, id INTEGER);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO meta VALUES ('schema_version','1.0');
        INSERT INTO messages (writer_role, body_md) VALUES ('A','нота');
        INSERT INTO read_cursors VALUES ('A', 1);
        INSERT INTO phoenix VALUES ('A','state','тело','2026-01-01 00:00:00');
        INSERT INTO backlog (id, role, title) VALUES (1,'A','задача без критерия');
    """)
    con.commit()
    con.close()

    con = sqlite3.connect(p)
    con.execute("PRAGMA foreign_keys = ON")
    mig.ensure_journal(con)
    for ver, _title, fn in mig.STEPS:
        fn(con, False)
        mig.mark_done(con, ver, "bite")
    mig.declare_milestone(con)
    return con


def objects(con):
    tabs, views = {}, {}
    for typ, name, sql in con.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE type IN ('table','view')"):
        (tabs if typ == "table" else views)[name] = sql
    return tabs, views


def columns(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def run():
    res = []
    def check(name, cond): res.append((name, bool(cond)))

    ref = build_reference()
    with tempfile.TemporaryDirectory() as tmp:
        mgr = build_migrated(tmp)

        ref_t, ref_v = objects(ref)
        mgr_t, mgr_v = objects(mgr)

        # ── ① ТАБЛИЦЫ v3 ЕСТЬ ОБОИМИ ПУТЯМИ ──────────────────────────────────
        for t in V3_TABLES:
            check(f"P-таблица «{t}» есть в эталоне И после миграции",
                  t in ref_t and t in mgr_t)

        # ── ② ВИТРИНЫ v3 ЕСТЬ ОБОИМИ ПУТЯМИ — ЭТО И ЕСТЬ ОПЛАЧЕННЫЙ СЛУЧАЙ ───
        for v in V3_VIEWS:
            in_ref, in_mgr = v in ref_v, v in mgr_v
            check(f"🔴 витрина «{v}» есть в эталоне И после миграции "
                  f"(эталон={in_ref}, миграция={in_mgr})", in_ref and in_mgr)

        # ── ③ ОПРЕДЕЛЕНИЯ ВИТРИН СОВПАДАЮТ ПО СМЫСЛУ ─────────────────────────
        # Мало, чтобы витрина была: она должна означать ТО ЖЕ. Иначе разойдутся
        # молча — ровно как разошлись два места одного механизма 15:26 UTC,
        # когда я починил сравнение в сценарии и не тронул схему.
        for v in V3_VIEWS:
            if v in ref_v and v in mgr_v:
                check(f"определение витрины «{v}» совпадает по смыслу",
                      norm(ref_v[v]) == norm(mgr_v[v]))

        # ── ④ КОЛОНКИ v3 ─────────────────────────────────────────────────────
        for tbl, col in V3_COLUMNS:
            check(f"колонка {tbl}.{col} есть обоими путями",
                  col in columns(ref, tbl) and col in columns(mgr, tbl))

        # ── ⑤ РАЗЛИЧАЮЩИЙ: витрины РАБОТАЮТ, а не только объявлены ───────────
        n = mgr.execute("SELECT COUNT(*) FROM backlog_without_criterion").fetchone()[0]
        check("витрина подсветки после миграции ОТВЕЧАЕТ и видит задачу без критерия", n == 1)
        ver = mgr.execute("SELECT version, steps_after_milestone FROM schema_version").fetchone()
        check(f"витрина версии после миграции отвечает: версия={ver[0]}, "
              f"сверх рубежа={ver[1]}", ver[0] == "v3" and ver[1] == 0)

        # ── ⑥ РАЗЛИЧАЮЩИЙ: старое значение версии СНЯТО НАДГРОБИЕМ, не стёрто ─
        old = mgr.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        check("прежний номер версии не удалён, а помечен надгробием с причиной",
              old is not None and old[0].startswith("⛔") and "1.0" in old[0])

        mgr.close()
    ref.close()
    return res


# ═════════════════════════════════════════════════════════════════════════════

MUTANTS = {
    # Ровно оплаченный случай: витрина есть в эталоне, из шага миграции убрана.
    # Раньше это прожило до чьей-то ссылки на неё в разговоре.
    "M1-витрина-подсветки-выпала-из-миграции": (MIGRATE_FILE, lambda s: s.replace(
        "            CREATE VIEW backlog_without_criterion AS",
        "            CREATE VIEW IF NOT EXISTS unused_stub AS SELECT 1 AS x; -- ")),
    # Витрина есть обоими путями, но означает РАЗНОЕ: расхождение двух копий механизма.
    "M2-витрина-версии-разошлась-по-смыслу": (MIGRATE_FILE, lambda s: s.replace(
        "                (SELECT COUNT(*) FROM schema_migrations WHERE version NOT GLOB 'v[0-9]*') AS steps_total,",
        "                (SELECT COUNT(*) FROM schema_migrations) AS steps_total,")),
    # Колонка критерия не добавлена — подсветке нечего показывать.
    "M3-колонка-критерия-не-добавлена": (MIGRATE_FILE, lambda s: s.replace(
        '            con.execute("ALTER TABLE backlog ADD COLUMN done_when TEXT")',
        "            pass")),
    # Старый номер версии затирается молча вместо надгробия.
    "M4-старый-номер-стёрт-молча": (MIGRATE_FILE, lambda s: s.replace(
        '            con.execute("UPDATE meta SET value=? WHERE key=\'schema_version\'", (tombstone,))',
        '            con.execute("UPDATE meta SET value=\'3.0\' WHERE key=\'schema_version\'")')),
}


def selftest():
    clean = run()
    red = sum(1 for _, ok in clean if not ok)
    print(f"ЧИСТО: {len(clean)-red}/{len(clean)} случаев")
    if red:
        print("🔴 УКУС КРАСНЫЙ НА ЧИСТОМ — самопроверка невозможна")
        for n, ok in clean:
            if not ok:
                print(f"   🔴 {n}")
        return 1
    survived = 0
    for name, (target, mut) in MUTANTS.items():
        orig = target.read_text(encoding="utf-8")
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден в {target.name} — мутант НЕ ВСТАЛ, "
                  f"считаю ВЫЖИВШИМ")
            survived += 1
            continue
        target.write_text(bad, encoding="utf-8")
        try:
            _s = importlib.util.spec_from_file_location("mig_mut", MIGRATE_FILE)
            m = importlib.util.module_from_spec(_s)
            try:
                _s.loader.exec_module(m)
                globals()["mig"] = m
                r = run()
                nred = sum(1 for _, ok in r if not ok)
            except Exception as e:
                nred, r = 1, [("сценарий не собрался: " + str(e)[:60], False)]
            caught = nred > 0
            print(f"{'✅' if caught else '🔴'} {name}: "
                  f"{'поймал' if caught else 'НЕ ПОЙМАЛ'} ({nred}/{len(r)} красных)")
            if not caught:
                survived += 1
        finally:
            target.write_text(orig, encoding="utf-8")
            _s = importlib.util.spec_from_file_location("mig_restore", MIGRATE_FILE)
            m = importlib.util.module_from_spec(_s); _s.loader.exec_module(m)
            globals()["mig"] = m
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} мутантов пойманы")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    rs = run()
    bad = sum(1 for _, ok in rs if not ok)
    for n, ok in rs:
        print(f"{'✅' if ok else '🔴'} {n}")
    print(f"\nВЫПОЛНЕНО {len(rs)} случаев, провалено {bad}")
    sys.exit(0 if bad == 0 else 1)
