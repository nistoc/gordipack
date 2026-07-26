# -*- coding: utf-8 -*-
"""
init-group-vnext.py — завести НОВЫЙ контур коллег (Э-В ⑤).

ПОЧЕМУ ПЕРЕПИСАН. Замер 2026-07-26 (уточняет находку COORD):
  · `init-group.py` ЖИВ в репозитории gordipack (там есть schema/ и rules/),
    но КОПИЯ, лежащая в живом контуре `.mezosync/scripts/`, НЕРАБОЧАЯ:
        C:\\guts\\.atlas\\.mezosync\\schema   — НЕТ
        C:\\guts\\.atlas\\.mezosync\\rules    — НЕТ
    А роль видит первой именно её. Инструмент, которым контур переносят в другой
    проект (в частности в AIA), падает у того, кто откроет его штатным путём.
  · Он ссылается на `schema/mezosync_v1.sql`, хотя в репо давно лежит v2 ⇒ новый
    контур рождался бы СТАРЫМ. Это тот же класс, что meta.schema_version='1.0'
    при фактической v2: артефакт пережил решение и молча учит прошлому.
  · `input("Перезаписать? (y/N)")` — интерактивный вопрос. В headless-запуске
    (агент, cron, CI) stdin пуст: вызов падает EOF или, хуже, читает пустую строку
    как «нет» и молча выходит с кодом 0, отчитавшись «Отмена».
  · `--roles coord` по умолчанию заводит роль В НИЖНЕМ РЕГИСТРЕ — прямо тот класс
    расщепления курсор↔слепок, который контур лечил вручную (и след которого до сих
    пор виден в живой БД: 'opssre' в audit_log).

ЧТО ИЗМЕНЕНО ПО СУЩЕСТВУ:
  1. Схема ищется по НЕСКОЛЬКИМ известным местам ОТ РАСПОЛОЖЕНИЯ СКРИПТА и, если её
     нет ни в одном, инструмент падает с rc=2 и НАЗЫВАЕТ, где искал (а не «нет файла»).
  2. Никакого интерактива: перезапись — только явным `--force`.
  3. Роли нормализуются в ВЕРХНИЙ регистр и проверяются схемой (CHECK), а не памятью.
  4. Реестр миграций заполняется сразу — новый контур с первого дня знает свою версию.
  5. САМОПРОВЕРКА ПОСЛЕ СОЗДАНИЯ: инструмент не верит собственной записи, а перечитывает
     БД и сверяет состав (урок контура: «проверил ПОСЛЕ правки, а не поверил диффу»).

    python init-group-vnext.py --name atlas --path C:\\projects\\x\\.mezosync --roles COORD CORE
"""
import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Порядок поиска — от «рядом со мной» к «в репозитории». Ни одного пути от CWD:
# рабочий каталог уезжает, и относительный поиск либо падает, либо находит ЧУЖОЕ.
SCHEMA_CANDIDATES = (
    HERE / "schema_vnext.sql",
    HERE.parent / "prototype" / "schema_vnext.sql",
    HERE.parent.parent / "schema" / "mezosync_v2.sql",
)
RULES_CANDIDATES = (
    HERE.parent.parent / "rules" / "universal.sql",
)


def find(candidates, what):
    for p in candidates:
        if p.exists():
            return p
    print(f"⛔ НЕ ЗАВЕДЁН: не нашёл {what}. Искал:")
    for p in candidates:
        print(f"   · {p}")
    print("   ⇒ инструмент заведения контура обязан быть самодостаточным: положи файл "
          "рядом со скриптом либо укажи явным флагом.")
    sys.exit(2)


def verify(db: Path, roles, expect_rules: bool) -> int:
    """Перечитать созданное и сверить. Своей же записи не верим."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    problems = []
    tabs = {n for n, in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    for need in ("roles", "rules", "phoenix", "phoenix_sections", "schema_migrations"):
        if need not in tabs:
            problems.append(f"нет таблицы {need}")
    got = {r for r, in con.execute("SELECT role FROM roles")} if "roles" in tabs else set()
    if got != set(roles):
        problems.append(f"роли разошлись: ожидали {sorted(roles)}, в БД {sorted(got)}")
    if "schema_migrations" in tabs:
        n, = con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()
        if n == 0:
            problems.append("реестр миграций пуст — контур не знает своей версии")
    if expect_rules and "rules" in tabs:
        n, = con.execute("SELECT COUNT(*) FROM rules").fetchone()
        if n == 0:
            problems.append("правила не загрузились")
    ver = con.execute("SELECT version FROM schema_version").fetchone() \
        if "schema_migrations" in tabs else None
    con.close()
    if problems:
        print("🔴 САМОПРОВЕРКА ПРОВАЛЕНА:")
        for p in problems:
            print("   ·", p)
        return 1
    print(f"✅ самопроверка пройдена: {len(tabs)} таблиц · роли {sorted(got)} · "
          f"версия схемы {ver[0] if ver else '—'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Завести новый контур коллег (mezosync v-next)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--path", required=True, help="каталог .mezosync нового контура")
    ap.add_argument("--roles", nargs="+", default=["COORD"],
                    help="роли контура (регистр нормализуется в ВЕРХНИЙ)")
    ap.add_argument("--schema", default=None, help="явный путь к схеме")
    ap.add_argument("--rules", default=None, help="явный путь к universal.sql")
    ap.add_argument("--no-rules", action="store_true", help="без загрузки правил")
    ap.add_argument("--force", action="store_true",
                    help="перезаписать существующую БД (интерактивного вопроса НЕТ")
    a = ap.parse_args()

    schema = Path(a.schema) if a.schema else find(SCHEMA_CANDIDATES, "файл схемы")
    rules = None
    if not a.no_rules:
        rules = Path(a.rules) if a.rules else next((p for p in RULES_CANDIDATES if p.exists()), None)

    # Регистр — в ЯДРЕ: нормализуем здесь, а схема ещё и проверит CHECK'ом.
    roles = sorted({r.strip().upper() for r in a.roles if r.strip()})
    if not roles:
        print("⛔ НЕ ЗАВЕДЁН: список ролей пуст")
        return 2

    d = Path(a.path)
    db = d / "mezosync.db"
    if db.exists() and not a.force:
        # Никакого input(): в headless-запуске вопрос читается как «нет» и инструмент
        # молча отчитывается «Отмена» с кодом 0 — успех, которого не было.
        print(f"⛔ НЕ ЗАВЕДЁН: БД уже существует: {db}\n"
              f"   Перезаписать — явным флагом --force (вопросов инструмент не задаёт: "
              f"в headless-запуске ответить некому).")
        return 2
    d.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    con = sqlite3.connect(str(db))
    con.execute("PRAGMA foreign_keys = ON")     # иначе объявленные FK — украшение
    con.executescript(schema.read_text(encoding="utf-8"))
    con.execute("PRAGMA foreign_keys = ON")     # executescript мог сбросить соединение
    con.execute("UPDATE meta SET value = ? WHERE key = 'group_name'", (a.name,))
    for r in roles:
        con.execute("INSERT INTO roles (role) VALUES (?)", (r,))
        con.execute("INSERT INTO role_presence (role, rhythm) VALUES (?, 'unset')", (r,))
    if rules:
        con.executescript(rules.read_text(encoding="utf-8"))
    con.commit()
    con.close()

    print(f"📦 контур «{a.name}» создан: {db}")
    print(f"   схема:  {schema}")
    print(f"   правила: {rules if rules else '— (--no-rules)'}")
    print(f"   роли:   {', '.join(roles)}")
    return verify(db, roles, expect_rules=bool(rules))


if __name__ == "__main__":
    sys.exit(main())
