# -*- coding: utf-8 -*-
"""
bite-ev.py — укус этапа Э-В: РАБОТАЮТ ЛИ КОНТРАКТЫ НОВОЙ СХЕМЫ, или это опять текст.

Проверяет в ОБЕ СТОРОНЫ: запрещённое обязано ОТКАЗАТЬСЯ, разрешённое — пройти.
Отдельно доказывается, что FK без `PRAGMA foreign_keys = ON` — украшение, а не контракт
(в SQLite ключи выключены по умолчанию; объявленный и не включённый FK ведёт себя как
комментарий — ровно та болезнь, которую этот этап и лечит).

Стенд — временная БД в памяти/во временном файле. Живой субстрат не открывается вовсе.
Предусловие не выполнено (нет файла схемы) — выход rc=2.

    python bite-ev.py
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent / "schema_vnext.sql"


def fresh(fk_on=True):
    db = Path(tempfile.mkdtemp(prefix="bite-ev-")) / "m.db"
    con = sqlite3.connect(str(db))
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.close()
    con = sqlite3.connect(str(db))
    con.execute(f"PRAGMA foreign_keys = {'ON' if fk_on else 'OFF'}")
    con.execute("INSERT INTO roles (role, zone) VALUES ('PROTO','протокол')")
    con.execute("INSERT INTO roles (role, zone) VALUES ('COORD','координация')")
    con.commit()
    return db, con


def case(title, con, sql, params=(), expect="deny"):
    """expect='deny' — операция ОБЯЗАНА упасть; 'allow' — обязана пройти."""
    try:
        con.execute(sql, params)
        con.commit()
        got = "allow"
        err = ""
    except sqlite3.Error as e:
        con.rollback()
        got = "deny"
        err = str(e).split("\n")[0]
    ok = got == expect
    mark = "✅" if ok else "🔴"
    tail = f"  ({err})" if err else ""
    print(f"  {mark} {title}: ожидали {expect}, получили {got}{tail}")
    return ok


def main():
    if not SCHEMA.exists():
        print(f"⛔ ПРИЁМКА НЕ ПОСТАВЛЕНА: нет схемы {SCHEMA}")
        return 2
    v = []

    print("── ④ РОЛЬ КАК СУЩНОСТЬ: регистр держит ЯДРО, а не каждый скрипт")
    db, con = fresh()
    v.append(case("роль в нижнем регистре", con,
                  "INSERT INTO roles (role) VALUES ('opssre')"))
    v.append(case("роль в верхнем регистре", con,
                  "INSERT INTO roles (role) VALUES ('OPSSRE')", expect="allow"))
    v.append(case("ссылка на несуществующую роль (phoenix)", con,
                  "INSERT INTO phoenix (role, section, body) VALUES ('GHOST','state','x')"))

    print("\n── ① СТАТУС ПРАВИЛА: отзыв обязан нести обстоятельства")
    v.append(case("правило активно", con,
                  "INSERT INTO rules (rule_key, body) VALUES ('r-live','тело')",
                  expect="allow"))
    v.append(case("отзыв БЕЗ причины/автора/времени", con,
                  "INSERT INTO rules (rule_key, body, status) VALUES ('r-bad','тело','revoked')"))
    v.append(case("отзыв С обстоятельствами", con,
                  "INSERT INTO rules (rule_key, body, status, revoked_at, revoked_by, "
                  "revoked_reason) VALUES ('r-rev','тело','revoked',datetime('now'),'owner','слово 18.07')",
                  expect="allow"))
    v.append(case("superseded без указания замены", con,
                  "INSERT INTO rules (rule_key, body, status) VALUES ('r-sup','тело','superseded')"))
    # ⚠️ Преемник — НОМЕРОМ, не именем (сведение 10.08, карточка #89): переименование
    #    правила не должно рвать ссылку молча. Стенд ссылается так же, как схема велит.
    v.append(case("superseded на несуществующее правило", con,
                  "INSERT INTO rules (rule_key, body, status, superseded_by) "
                  "VALUES ('r-sup','тело','superseded',99999)"))
    v.append(case("superseded на живое правило", con,
                  "INSERT INTO rules (rule_key, body, status, superseded_by) "
                  "VALUES ('r-sup','тело','superseded',"
                  "(SELECT id FROM rules WHERE rule_key='r-live'))", expect="allow"))
    n, = con.execute("SELECT COUNT(*) FROM rules_active").fetchone()
    ok = n == 1
    v.append(ok)
    print(f"  {'✅' if ok else '🔴'} действующие отбираются ПОЛЕМ: rules_active = {n} "
           f"(из 3 правил; текстом это дало бы 53 % ложных — замер живой БД)")

    print("\n── ⑥ КОНТРАКТ СЕКЦИЙ: список секций — таблица, а не комментарий")
    v.append(case("секция вне справочника", con,
                  "INSERT INTO phoenix (role, section, body) VALUES ('PROTO','выдумка','x')"))
    v.append(case("секция из справочника", con,
                  "INSERT INTO phoenix (role, section, body) VALUES ('PROTO','state','x')",
                  expect="allow"))
    gaps = con.execute("SELECT COUNT(*) FROM phoenix_gaps WHERE role='PROTO'").fetchone()[0]
    ok = gaps == 5
    v.append(ok)
    print(f"  {'✅' if ok else '🔴'} неполная память ВИДНА строкой: у PROTO не хватает "
           f"{gaps} обязательных секций (ожидали 5)")

    print("\n── ② ПРИСУТСТВИЕ: три состояния РАЗЛИЧИМЫ (сегодня — нет вовсе)")
    con.execute("INSERT INTO role_presence (role, rhythm, rhythm_by, rhythm_reason, last_seen_at) "
                "VALUES ('PROTO','paused_by_owner','owner','слово владельца', datetime('now'))")
    con.execute("INSERT INTO role_presence (role, rhythm, rhythm_by, last_seen_at) "
                "VALUES ('COORD','running','COORD', datetime('now','-3 hours'))")
    con.commit()
    seen = {r[0]: r[1] for r in con.execute("SELECT role, presence FROM role_presence_read")}
    ok = "СЛОВОМ ВЛАДЕЛЬЦА" in seen.get("PROTO", "") and "умерла с сессией" in seen.get("COORD", "")
    v.append(ok)
    for role, p in seen.items():
        print(f"     {role:6} → {p}")
    print(f"  {'✅' if ok else '🔴'} «снят по слову» ⊥ «умер с сессией» различены БЕЗ вопроса владельцу")
    v.append(case("пауза «по слову владельца», но автор не владелец", con,
                  "UPDATE role_presence SET rhythm='paused_by_owner', rhythm_by='STUD' "
                  "WHERE role='COORD'"))

    print("\n── ③ ВЕРСИЯ СХЕМЫ: вычисляется, а не хранится")
    # 🪤 ЗДЕСЬ БЫЛО `applied == 5` — ЧИСЛО МИГРАЦИЙ ЗНАЧЕНИЕМ. Миграций стало 9, и укус
    #    краснел молча, пока я не прогнал его по другому поводу (2026-08-06 14:41 UTC).
    #    Это ровно тот класс, который сам укус и охраняет — «производное значением
    #    протухает молча» — только в стороже, а не в схеме. Второй раз за сутки: сторож
    #    у автора остаётся украшением, пока автор не станет его потребителем.
    # ⇒ Проверяется не РАВЕНСТВО ЧИСЛУ, а СВОЙСТВО: версия вычисляется из журнала
    #   (новая строка видна витрине СРАЗУ) и нигде не хранится копией.
    ver, applied, after = con.execute(
        "SELECT version, steps_total, steps_after_milestone FROM schema_version").fetchone()
    stored = con.execute("SELECT COUNT(*) FROM meta WHERE key='schema_version'").fetchone()[0]
    con.execute("INSERT INTO schema_migrations (version, applied_by) VALUES ('999_probe','BITE')")
    ver2, applied2, after2 = con.execute(
        "SELECT version, steps_total, steps_after_milestone FROM schema_version").fetchone()
    con.execute("DELETE FROM schema_migrations WHERE version='999_probe'")
    # ⚠️ Проверяется НЕ равенство числу (оно протухает — этот укус уже так падал молча),
    #    а СВОЙСТВА: версия не хранится копией · новый шаг виден витрине сразу ·
    #    номер ВЕРСИИ не подменяется номером ШАГА · шаг сверх рубежа СТАНОВИТСЯ ВИДЕН.
    ok = (stored == 0 and applied > 0
          and applied2 == applied + 1        # журнал виден витрине немедленно
          and ver2 == ver                    # номер версии НЕ съехал на номер шага
          and after2 == after + 1)           # шаг сверх рубежа виден сам, без сверки
    v.append(ok)
    print(f"  {'✅' if ok else '🔴'} версия '{ver}' из {applied} шагов, сверх отметки {after}; "
          f"хранимых копий в meta: {stored} (нужен 0); после чужого шага: "
          f"шагов {applied}→{applied2}, сверх отметки {after}→{after2}, версия '{ver2}' (не съехала)")
    con.close()

    print("\n── 🔴 КОНТРОЛЬНЫЙ: FK БЕЗ `PRAGMA foreign_keys=ON` — УКРАШЕНИЕ")
    db2, con2 = fresh(fk_on=False)
    passed = case("ссылка на несуществующую роль при FK=OFF", con2,
                  "INSERT INTO phoenix (role, section, body) VALUES ('GHOST','state','x')",
                  expect="allow")
    v.append(passed)
    chk = case("CHECK регистра при FK=OFF", con2,
               "INSERT INTO roles (role) VALUES ('ghost')")
    v.append(chk)
    print("  ⇒ CHECK действует всегда, FK — только при включённом PRAGMA. Значит контракт")
    print("    ссылочной целостности обязан держаться КОДОМ КАЖДОГО СОЕДИНЕНИЯ, и это")
    print("    проверяет гард, а не надежда. Объявить FK и не включить = снова комментарий.")
    con2.close()

    ok = all(v)
    print(f"\n{'✅ КОНТРАКТЫ Э-В ДЕРЖАТСЯ' if ok else '🔴 ЕСТЬ ПРОВАЛЫ'} — "
          f"{sum(1 for x in v if x)}/{len(v)} проверок")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
