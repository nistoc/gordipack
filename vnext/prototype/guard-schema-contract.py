# -*- coding: utf-8 -*-
"""
guard-schema-contract.py — гард Э-В: СХЕМА ОБЯЗАНА ГОВОРИТЬ О СЕБЕ ПРАВДУ.

Проверяет пять утверждений, каждое из которых сегодня живёт в комментарии, в прозе
или в чужой памяти. Работает по ЛЮБОЙ координационной БД, ТОЛЬКО ЧТЕНИЕ (mode=ro):
живой контур можно проверять безопасно.

  ① версия схемы: объявленная == фактическая (и вообще существует ли реестр миграций)
  ② контракт секций phoenix: DDL/справочник == живые секции
  ③ статус правила: полем или прозой (и насколько проза неоднозначна — числом)
  ④ роль как сущность: таблица ролей, единое имя колонки, регистр, FK
  ⑤ присутствие/ритм: различимы ли «снят по слову» ⊥ «умер с сессией»

⚠️ Гард НЕ падает на «старой» БД молча и не краснеет вечно: у каждой проверки
   есть 🟡 (известный остаток, назван) и 🔴 (расхождение внутри собственных правил).
   Вечно-красный гард контур уже лечил однажды — второй такой не заводим.

    python guard-schema-contract.py --db <путь>          # по умолчанию живая
    python guard-schema-contract.py --db <путь> --strict # 🟡 тоже роняет (для v-next)
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
# Таблицы, которых не было в v1: их наличие означает, что схема ушла вперёд объявленной.
POST_V1 = ("read_batches", "role_status", "stats_log", "messages_history")
REVOKE_STRICT = re.compile(r"⛔\s*ОТОЗВАН", re.IGNORECASE)
REVOKE_LOOSE = re.compile(r"отозв|надгроб|устарел|ПРОТУХ|снят", re.IGNORECASE)


class Report:
    def __init__(self):
        self.red = self.yellow = self.green = 0

    def ok(self, title, detail=""):
        self.green += 1
        print(f"✅ {title}" + (f" — {detail}" if detail else ""))

    def warn(self, title, detail=""):
        self.yellow += 1
        print(f"🟡 {title}" + (f" — {detail}" if detail else ""))

    def bad(self, title, detail=""):
        self.red += 1
        print(f"🔴 {title}" + (f" — {detail}" if detail else ""))


def tables(con):
    return {n for n, in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def check_version(con, t, r):
    declared = None
    row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() \
        if "meta" in t else None
    if row:
        declared = row[0]
    has_reg = "schema_migrations" in t
    ahead = [x for x in POST_V1 if x in t]
    if has_reg:
        n, = con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()
        top, = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        if declared and declared != top:
            r.bad("① версия схемы", f"meta.schema_version='{declared}', "
                                    f"а реестр миграций на '{top}' — два источника, оба пишутся рукой")
        else:
            r.ok("① версия схемы", f"вычисляется из реестра: '{top}' ({n} миграций)")
    else:
        if declared and ahead:
            r.bad("① версия схемы",
                  f"объявлена '{declared}', но в БД живут таблицы после v1: {ahead}. "
                  f"Реестра миграций НЕТ — версию обновляют памятью, а память протекла")
        elif declared:
            r.warn("① версия схемы", f"объявлена '{declared}', реестра миграций нет — "
                                     f"проверить нечем, доверяем на слово")
        else:
            r.warn("① версия схемы", "не объявлена вовсе")


def check_sections(con, t, r):
    if "phoenix" not in t:
        r.warn("② контракт секций phoenix", "таблицы phoenix нет")
        return
    live = {s for s, in con.execute("SELECT DISTINCT section FROM phoenix")}
    if "phoenix_sections" in t:
        declared = {s for s, in con.execute("SELECT section FROM phoenix_sections")}
        extra = live - declared
        if extra:
            r.bad("② контракт секций phoenix", f"в данных есть секции вне справочника: {sorted(extra)}")
        else:
            r.ok("② контракт секций phoenix", f"справочник покрывает все {len(live)} живых секций")
        return
    ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='phoenix'").fetchone()[0] or ""
    m = re.search(r"section[^\n]*--([^\n]*)", ddl)
    named = set(re.findall(r"'([a-z_]+)'", m.group(1))) if m else set()
    if named and named != live:
        r.bad("② контракт секций phoenix",
              f"комментарий DDL объявляет {len(named)} {sorted(named)}, "
              f"фактических {len(live)} {sorted(live)} — недостающие: {sorted(live - named)}")
    elif not named:
        r.warn("② контракт секций phoenix", f"контракта нет нигде; фактических секций {len(live)}")
    else:
        r.ok("② контракт секций phoenix", "комментарий совпадает с данными (но он всё ещё комментарий)")


def check_rule_status(con, t, r):
    if "rules" not in t:
        r.warn("③ статус правила", "таблицы rules нет")
        return
    cols = {c[1] for c in con.execute("PRAGMA table_info(rules)")}
    if "status" in cols:
        rows = list(con.execute("SELECT status, COUNT(*) FROM rules GROUP BY status"))
        bad = con.execute(
            "SELECT COUNT(*) FROM rules WHERE status='revoked' AND "
            "(revoked_at IS NULL OR revoked_by IS NULL OR revoked_reason IS NULL)").fetchone()[0] \
            if {"revoked_at", "revoked_by", "revoked_reason"} <= cols else 0
        if bad:
            r.bad("③ статус правила", f"{bad} отозванных без обстоятельств отзыва")
        else:
            r.ok("③ статус правила", f"полем: {dict(rows)}")
        return
    rows = con.execute("SELECT rule_key, body FROM rules").fetchall()
    strict = [k for k, b in rows if REVOKE_STRICT.search("\n".join((b or "").splitlines()[:3]))]
    loose = [k for k, b in rows if REVOKE_LOOSE.search(b or "")]
    fp = len(loose) - len(strict)
    r.bad("③ статус правила",
          f"поля НЕТ, отзыв живёт прозой: всего {len(rows)}, строгий поиск находит "
          f"{len(strict)}, широкий {len(loose)} — расхождение {fp} "
          f"({100 * fp // max(len(loose), 1)} % ложных). Машинно отобрать действующие нельзя")


def check_role_entity(con, t, r):
    role_cols = []
    for tbl in sorted(t):
        for c in con.execute(f'PRAGMA table_info("{tbl}")'):
            if c[1].lower().endswith("role"):
                role_cols.append((tbl, c[1]))
    names = sorted({c for _, c in role_cols})
    fks = sum(1 for tbl in t for f in con.execute(f'PRAGMA foreign_key_list("{tbl}")')
              if f[2] == "roles")
    lower = set()
    for tbl, c in role_cols:
        try:
            for v, in con.execute(f'SELECT DISTINCT "{c}" FROM "{tbl}" WHERE "{c}" IS NOT NULL'):
                if v != v.upper():
                    lower.add(f"{v} ({tbl})")
        except sqlite3.Error:
            pass
    if "roles" not in t:
        r.bad("④ роль как сущность",
              f"таблицы roles НЕТ; роль хранится в {len(role_cols)} колонках под {len(names)} "
              f"именами {names}; FK на роли — 0; нормализация регистра лежит на каждом скрипте"
              + (f"; УЖЕ ПРОТЕКЛО: {sorted(lower)}" if lower else ""))
        return
    if lower:
        r.bad("④ роль как сущность", f"значения не в верхнем регистре: {sorted(lower)}")
    elif fks == 0:
        r.warn("④ роль как сущность", "таблица roles есть, но FK на неё не объявлены")
    else:
        r.ok("④ роль как сущность", f"{fks} FK на roles, регистр held CHECK'ом")


def check_presence(con, t, r):
    if "role_presence" in t:
        cols = {c[1] for c in con.execute("PRAGMA table_info(role_presence)")}
        if {"rhythm", "last_seen_at"} <= cols:
            r.ok("⑤ присутствие/ритм", "намерение (rhythm) и факт (last_seen_at) — разные поля")
            return
        r.bad("⑤ присутствие/ритм", "таблица есть, но намерение и факт не разведены")
        return
    if "role_status" not in t:
        r.warn("⑤ присутствие/ритм", "состояния ролей не хранится вовсе")
        return
    n, = con.execute("SELECT COUNT(*) FROM role_status").fetchone()
    drift = 0
    for role, st, upd in con.execute("SELECT role, status, updated_at FROM role_status"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", st or "")
        if m and upd and not (upd or "").startswith(m.group(1)):
            drift += 1
    r.bad("⑤ присутствие/ритм",
          f"одна строка свободного текста на роль ({n} ролей): «снят по слову» ⊥ "
          f"«умер с сессией» ⊥ «работает молча» машинно неразличимы; компенсатор — "
          f"вопрос владельцу"
          + (f". И ПРОИЗВОДНОЕ УЖЕ ЛЖЁТ: у {drift} ролей дата внутри текста "
             f"не совпадает с updated_at" if drift else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(LIVE))
    ap.add_argument("--strict", action="store_true", help="🟡 тоже считать провалом")
    a = ap.parse_args()
    db = Path(a.db)
    if not db.exists():
        print(f"⛔ ГАРД НЕ ПОСТАВЛЕН: БД не найдена: {db}")
        return 2
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    fk_on = con.execute("PRAGMA foreign_keys").fetchone()[0]
    print(f"[гард контракта схемы] {db}")
    # Гард читает — ему FK не нужны; печатаем факт как НАПОМИНАНИЕ о том, что в SQLite
    # ключи выключены по умолчанию, и ПИШУЩЕЕ соединение обязано включать их само.
    # Объявить FK в схеме и не включить в коде = снова контракт в комментарии.
    print(f"   PRAGMA foreign_keys по умолчанию: {'ON' if fk_on else 'OFF'}"
          + ("" if fk_on else "  ⚠️ пишущие соединения обязаны включать его САМИ\n"))
    t = tables(con)
    r = Report()
    for fn in (check_version, check_sections, check_rule_status, check_role_entity, check_presence):
        fn(con, t, r)
    con.close()
    print(f"\nитог: 🔴 {r.red} · 🟡 {r.yellow} · ✅ {r.green}")
    if r.red or (a.strict and r.yellow):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
