#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: ПРАВА РОЛИ ПОЛЯМИ (слово владельца 2026-08-08 22:33 UTC).

Предмет. Права ролей жили прозой в их памяти — в том самом виде, из которого утром пришлось
выкапывать основания правил (11 правил объявляли решение владельца, не помня когда).
Цена уже заплачена дважды за одну смену: снятие запрета на push жило в ТРЁХ местах, и разовое
разрешение я сам дважды спутал — потрачено оно или нет.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① право с полным источником записывается           контроль: механизм вообще работает
  ② без «кто разрешил» → ОТКАЗ, в базу НЕ попало                 РАЗЛИЧАЮЩИЙ
  ③ без «где сказано» → ОТКАЗ (источник — не роскошь)            РАЗЛИЧАЮЩИЙ
  ④ РАЗОВОЕ потрачено → уходит из живых, но ОСТАЁТСЯ в истории   РАЗЛИЧАЮЩИЙ
  ⑤ потратить дважды НЕЛЬЗЯ                                      РАЗЛИЧАЮЩИЙ
  ⑥ СТОЯЧЕЕ потратить нельзя вовсе                               РАЗЛИЧАЮЩИЙ
  ⑦ отзыв БЕЗ причины отвергается: отзыв без причины — пропажа   РАЗЛИЧАЮЩИЙ
  ⑧ отозванное уходит из живых, но НЕ удаляется                  РАЗЛИЧАЮЩИЙ
  ⑨ ДУБЛЬ живого права не заводится молча                        РАЗЛИЧАЮЩИЙ
  ⑩ пустой список говорит «поля никто не заполнял», а не «прав нет»

⚡ ДОБАВЛЕНО 2026-08-09 — ФОРМА «СПРОСИТЬ ПРО СЕБЯ». До этого дня приёмка звала `list` БЕЗ
имени роли, а промпт запуска роли и справка самого механизма зовут `list --role <РОЛЬ>`.
Эта форма падала ВСЕГДА (параметр готовился и терялся), и приёмка была зелёной, не увидев
ничего: она мерила не то место.
  ⑪ `list --role X` вообще отвечает                    контроль: форма из промпта запуска
  ⑫ фильтр не показывает ЧУЖИХ прав                              РАЗЛИЧАЮЩИЙ
  ⑬ ОБЩЕЕ право (role=ALL) ВИДНО спросившему про себя            РАЗЛИЧАЮЩИЙ
     иначе роль слышит «тебе ничего не разрешено» при живом стоячем разрешении на всех
  ⑭ «у ЭТОЙ роли нет» ≠ «полей никто не заполнял»                РАЗЛИЧАЮЩИЙ
     контрольная пара к ⑩: тот же вопрос к ПУСТОЙ базе обязан дать ДРУГОЙ ответ

⛔ Живой базы не касается: своя песочница.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile

CLI = r"C:\guts\.atlas\.mezosync\scripts\role-rights.py"
DDL = open(os.path.join(os.path.dirname(CLI), "migrations",
                        "20260808-role-rights.py"), encoding="utf-8").read()
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    db = os.path.join(tempfile.mkdtemp(prefix="bite-rights-"), "s.db")
    con = sqlite3.connect(db)
    ddl = DDL.split('DDL = """')[1].split('"""')[0]
    con.executescript(ddl)
    con.commit()
    con.close()
    return db


def run(db, *args):
    r = subprocess.run([sys.executable, CLI, "--db", db, *args],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def rows(db, live=True):
    con = sqlite3.connect(db)
    n = con.execute(f"SELECT COUNT(*) FROM {'role_rights_live' if live else 'role_rights'}"
                    ).fetchone()[0]
    con.close()
    return n


FULL = ["--authorized-by", "owner", "--granted-at", "2026-08-08 15:56 UTC",
        "--source-ref", "чат PROTO 2026-08-08 15:56 UTC"]


def main() -> int:
    ok = True
    db = build()

    out, code = run(db, "list")
    ok &= case("⑩ пустой список говорит «поля никто не заполнял», а не «прав нет»",
               "ПУСТО" in out and "НЕ «прав нет»" in out,
               "молчание тут прочлось бы как «роли ничего не разрешено»")

    out, code = run(db, "grant", "--role", "PROTO", "--right", "push",
                    "--kind", "standing", "--scope", "gordipack", *FULL)
    ok &= case("① право с полным источником записано (контроль: механизм работает)",
               code == 0 and rows(db) == 1, f"код {code} · живых прав {rows(db)}")

    out, code = run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once",
                    "--granted-at", "2026-08-08", "--source-ref", "чат")
    ok &= case("② без «кто разрешил» — ОТКАЗ, в базу НЕ попало",
               code != 0 and rows(db, live=False) == 1 and "НЕ ЗАПИСАНО" in out,
               f"код {code} · записей всего {rows(db, live=False)} — новых нет", differ=True)

    out, code = run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once",
                    "--authorized-by", "owner", "--granted-at", "2026-08-08")
    ok &= case("③ без «где сказано» — ОТКАЗ: источник не роскошь",
               code != 0 and rows(db, live=False) == 1,
               "право без источника нельзя ни проверить, ни отозвать безопасно", differ=True)

    run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once", *FULL)
    live_before, all_before = rows(db), rows(db, live=False)
    out, code = run(db, "spend", "--id", "2", "--on", "шаг 008")
    ok &= case("④ РАЗОВОЕ потрачено — ушло из живых, но ОСТАЛОСЬ в истории",
               code == 0 and rows(db) == live_before - 1 and rows(db, live=False) == all_before,
               f"живых {live_before} → {rows(db)} · всего {all_before} → "
               f"{rows(db, live=False)}", differ=True)

    out, code = run(db, "spend", "--id", "2")
    ok &= case("⑤ потратить ДВАЖДЫ нельзя",
               code != 0 and "УЖЕ потрачено" in out,
               "иначе разовое право становится стоячим явочным порядком", differ=True)

    out, code = run(db, "spend", "--id", "1")
    ok &= case("⑥ СТОЯЧЕЕ потратить нельзя вовсе",
               code != 0 and "СТОЯЧЕЕ" in out,
               "тратятся только разовые: у стоячего нет расхода по определению", differ=True)

    out, code = run(db, "revoke", "--id", "1")
    ok &= case("⑦ отзыв БЕЗ причины отвергнут",
               code != 0 and "пропажа" in out,
               "отозванное право спрашивают именно тогда, когда что-то пошло не так", differ=True)

    live_before, all_before = rows(db), rows(db, live=False)
    out, code = run(db, "revoke", "--id", "1", "--why", "слово владельца отозвано 09.08")
    ok &= case("⑧ отозванное ушло из живых, но НЕ удалено",
               code == 0 and rows(db) == live_before - 1 and rows(db, live=False) == all_before,
               f"живых {live_before} → {rows(db)} · всего {all_before} → {rows(db, live=False)}",
               differ=True)

    run(db, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
        "--scope", "phd1", *FULL)
    out, code = run(db, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
                    "--scope", "phd1", *FULL)
    ok &= case("⑨ ДУБЛЬ живого права не заводится молча",
               code != 0 and "УЖЕ ЕСТЬ" in out,
               "два одинаковых права раздваивают ответ на вопрос «а можно ли»", differ=True)

    # ── ФОРМА «СПРОСИТЬ ПРО СЕБЯ» — ровно та, что стоит в промпте запуска роли ──────────
    run(db, "grant", "--role", "ALL", "--right", "push-common", "--kind", "standing",
        "--scope", "любой репозиторий", *FULL)
    run(db, "grant", "--role", "CORE", "--right", "service-start", "--kind", "standing",
        "--scope", ":5300", *FULL)

    out, code = run(db, "list", "--role", "CORE")
    ok &= case("⑪ `list --role CORE` ОТВЕЧАЕТ (контроль: форма из промпта запуска работает)",
               code == 0 and "service-start" in out,
               f"код {code} · своё право роль видит")

    ok &= case("⑫ фильтр по роли НЕ показывает чужого",
               code == 0 and "seed" not in out,
               "право TAXO «seed» живо в базе, но в ответе роли CORE его быть не должно",
               differ=True)

    ok &= case("⑬ ОБЩЕЕ право (role=ALL) ВИДНО спросившему про себя",
               code == 0 and "push-common" in out,
               "иначе роль слышит «мне ничего не разрешено» при живом разрешении на ВСЕХ "
               "и отказывается от разрешённого", differ=True)

    # ⚠️ ТРЕТЬЯ база — БЕЗ общего права. В базе `db` общее право ЕСТЬ, поэтому спросивший
    # про себя никогда не попадёт в ветку «пусто», и случай зеленел бы, ничего не проверив.
    # Так и было при первом заходе 2026-08-09: нарочная поломка это и вскрыла.
    db3 = build()
    run(db3, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
        "--scope", "phd1", *FULL)
    out_none, code_none = run(db3, "list", "--role", "ING")
    out_empty, _ = run(build(), "list", "--role", "ING")
    ok &= case("⑭ «у ЭТОЙ роли нет» ≠ «полей никто не заполнял» (контрольная пара к ⑩)",
               code_none == 0 and "НЕ ПРО СВОД" not in out_none
               and "НЕТ НИ ОДНОГО" in out_none and "никто не заполнял" not in out_none
               and "ПУСТО" in out_empty and "НЕ «прав нет»" in out_empty,
               "у роли ING прав нет, но у TAXO есть ⇒ ответ про ЕЁ набор, а не про свод; "
               "в пустой базе тот же вопрос обязан дать ДРУГОЙ текст", differ=True)

    print()
    print(f"{'✅ ПРАВА ПОЛЯМИ ПРИНЯТЫ' if ok else '🔴 НЕ ПРИНЯТЫ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан ЖИВОЙ скрипт")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
