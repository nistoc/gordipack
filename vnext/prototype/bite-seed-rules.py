#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА проверки «посев правил не отстал от живого свода».

Проверка, стерегущая отставание, обязана быть испытана поломкой: иначе она зелена ровно
потому, что ничего не сравнивает. И у неё есть собственная ловушка, оплаченная при
рождении: ПЕРВАЯ РЕДАКЦИЯ СУДИЛА ПО ДЛИНЕ и объявила «отстали 30» сразу после честного
догона — посев короче живого НАМЕРЕННО, из него убраны случаи чужого контура.
⇒ Признак отставания здесь — ВРЕМЯ правки, а не объём текста, и случай ⑥ это стережёт.

Случаи (различающий = проверка обязана ответить ИНАЧЕ, а не одинаково):
  ① контроль: свод и посев согласованы — молчит, и видно, что смотрела
  ② правило изменено ПОСЛЕ догона → красное                        РАЗЛИЧАЮЩИЙ
  ③ то же правило изменено ДО догона → молчит                      ВСТРЕЧНЫЙ к ②
  ④ метки догона нет → сказано вслух, а не «чисто»                 РАЗЛИЧАЮЩИЙ
  ⑤ посев не применяется к чистой базе → отказ мерить кодом 2      РАЗЛИЧАЮЩИЙ
  ⑥ посев КОРОЧЕ живого, но не правленный после догона → молчит    РАЗЛИЧАЮЩИЙ
  ⑦ правило снято у нас, а в посеве живое → названо отдельно       РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: свод берётся из копии, посев — из временного файла.
"""
from __future__ import annotations

import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

TOOL = pathlib.Path(__file__).resolve().parent / "guard-seed-rules.py"
CATCHUP = "2026-08-20 23:05"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def stand(rules, mark=CATCHUP, seed_broken=False, duplicate=None):
    """Свод в копии базы + файл посева. Оба — во временном каталоге.

    дубль=(ключ, тело_второго_определения, объявлен) дописывает в посев ВТОРОЕ
    определение того же ключа (карточка #430 ③): в базу доедет оно, последнее.
    """
    d = mezo_stand.new("bite-seed-")
    db = d / "live.db"
    con = sqlite3.connect(str(db))
    con.execute("""CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT UNIQUE, body TEXT,
                   locked_by TEXT, version INT, status TEXT, updated_at TEXT)""")
    rows = []
    for i, (key, body, status, edited_at) in enumerate(rules, 1):
        con.execute("INSERT INTO rules (id, rule_key, body, locked_by, version, status,"
                    " updated_at) VALUES (?,?,?,?,?,?,?)",
                    (i, key, body, "owner", 1, status, edited_at))
    con.commit()
    con.close()
    # посев несёт КОРОТКУЮ редакцию тех же правил — как в жизни
    for key, body, status, _ in rules:
        short_body = body.split(".")[0].replace("'", "") + "."
        rows.append(f"('{key}',\n '{short_body}',\n 'owner', 1)")
    seed = d / "seed.sql"
    seed_text = ("-- посев\n"
                  + (f"-- ПОСЛЕДНИЙ ДОГОН ПОСЕВА: {mark}\n" if mark else "")
                  + "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
                  + ",\n".join(rows) + ";\n")
    if duplicate:
        dup_key, dup_body, declared = duplicate
        if declared:
            seed_text += (f"-- ⚠️ ВЫШЕ МЁРТВОЕ ОПРЕДЕЛЕНИЕ: тот же ключ '{dup_key}' "
                           f"определён ещё раз ниже, в базу доедет оно\n")
        seed_text += ("INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) "
                       f"VALUES\n('{dup_key}',\n '{dup_body}',\n 'owner', 1);\n")
    if seed_broken:
        seed_text += "INSERT INTO нет_такой_таблицы (a) VALUES (1);\n"
    seed.write_text(seed_text, encoding="utf-8")
    return seed, db


def run(seed, db):
    r = subprocess.run([sys.executable, str(TOOL), "--seed", str(seed), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


RULE = ("общее-правило", "НОРМА ЖИВЁТ ЗДЕСЬ. Дальше идёт разбор случая контура-донора, "
                            "который в посев не переносится", "active")

# Таблица rules той формы, что у настоящего контура (колонки и ограничения схемы v6):
# у неё проверка и берёт форму для посева — случаи ⑨ судят именно это.
FULL_RULES_DDL = """CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
    locked_by TEXT NOT NULL DEFAULT 'coord', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    basis TEXT, authorized TEXT, source_ref TEXT, expiry_kind TEXT, expiry_cond TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'superseded')),
    revoked_at TEXT, revoked_by TEXT, revoked_reason TEXT,
    superseded_by INTEGER REFERENCES rules(id) ON DELETE SET NULL, skill_delivery TEXT,
    CHECK (status <> 'revoked' OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
                                   AND revoked_reason IS NOT NULL)))"""
RHYTHM_KEY = "ритм-правило"
REVOKE_IN_SEED = ("UPDATE rules SET status = 'revoked', revoked_at = '2026-09-24 10:49 UTC', "
                  "revoked_by = 'owner', revoked_reason = 'снято в контуре-доноре' "
                  f"WHERE rule_key = '{RHYTHM_KEY}';\n")


def stand_full(live_status: str, revoke_line: str):
    """Живой свод с таблицей настоящей формы + посев, снимающий правило строкой UPDATE."""
    d = mezo_stand.new("bite-seed-revoked-")
    db = d / "live.db"
    con = sqlite3.connect(str(db))
    con.execute(FULL_RULES_DDL)
    if live_status == "revoked":
        con.execute("INSERT INTO rules (rule_key, body, locked_by, status, revoked_at, revoked_by,"
                    " revoked_reason, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (RHYTHM_KEY, "БУДИЛЬНИК ЗАВОДИТСЯ ПРИ ПРОБУЖДЕНИИ.", "owner", "revoked",
                     "2026-09-24 10:49 UTC", "owner", "снято словом владельца", "2026-08-01 10:00"))
    else:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, updated_at) VALUES (?,?,?,?)",
                    (RHYTHM_KEY, "БУДИЛЬНИК ЗАВОДИТСЯ ПРИ ПРОБУЖДЕНИИ.", "owner", "2026-08-01 10:00"))
    con.commit()
    con.close()
    seed = d / "seed.sql"
    seed.write_text("-- посев\n-- ПОСЛЕДНИЙ ДОГОН ПОСЕВА: " + CATCHUP + "\n"
                    "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
                    f"('{RHYTHM_KEY}',\n 'БУДИЛЬНИК ЗАВОДИТСЯ ПРИ ПРОБУЖДЕНИИ.',\n 'owner', 1);\n"
                    + revoke_line, encoding="utf-8")
    return seed, db


def check_revoked_in_seed() -> bool:
    ok = True
    # ⑨ снято и у нас, и в посеве: посев применяется, «в посеве живое» НЕ говорится
    seed9, db9 = stand_full("revoked", REVOKE_IN_SEED)
    out9, code9 = run(seed9, db9)
    ok &= case("⑨ посев снимает правило строкой UPDATE status — применяется; снятое у обоих "
               "названо «снято и у вас, и в посеве», а не «в посеве живое»",
               code9 == 0 and "НЕ ЗАПУСТИЛАСЬ" not in out9
               and "снято и у вас, и в посеве" in out9 and "а в посеве живое" not in out9,
               f"код {code9}; прежняя проверка падала здесь «no such column: status» — на своей "
               f"урезанной таблице, которой нет ни у одного контура", differ=True)

    # ⑨-бис снято только в посеве: названо отдельно — новый контур родится с ним снятым
    seed9b, db9b = stand_full("active", REVOKE_IN_SEED)
    out9b, code9b = run(seed9b, db9b)
    ok &= case("⑨-бис правило снято в посеве, а у нас живое — названо отдельно",
               "в посеве СНЯТО, а у вас живое" in out9b,
               f"код {code9b}; это решение человека, как и обратный случай ⑦", differ=True)

    # ⑨-тер ВСТРЕЧНЫЙ: снятие без причины настоящая схема не примет — и проверка тоже
    no_reason = REVOKE_IN_SEED.replace(", revoked_reason = 'снято в контуре-доноре'", "")
    seed9t, db9t = stand_full("revoked", no_reason)
    out9t, code9t = run(seed9t, db9t)
    # ⚖️ Отказ обязан быть ПО ОГРАНИЧЕНИЮ: прежняя проверка тоже давала здесь код 2, но по
    # чужой причине («no such column: status») — случай, судящий только код, зеленел бы на ней.
    ok &= case("⑨-тер ВСТРЕЧНЫЙ: снятие БЕЗ причины — отказ кодом 2 по ограничению схемы, "
               "как у сборки контура",
               code9t == 2 and "НЕ ЗАПУСТИЛАСЬ" in out9t and "CHECK constraint" in out9t,
               f"код {code9t}; форма таблицы взята у контура вместе с её ограничениями — "
               f"иначе посев прошёл бы проверку и уронил сборку", differ=True)
    return ok


def main() -> int:
    ok = True
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: проверки нет — {TOOL}")

    # ① КОНТРОЛЬ: правки старше догона — молчание. Без него краснота ничего не значит.
    seed, db = stand([(*RULE, "2026-08-01 10:00")])
    out1, code1 = run(seed, db)
    ok &= case("① контроль: правок после догона нет — молчит, и видно, что смотрела",
               code1 == 0 and "отставших правил нет" in out1 and "правил в посеве 1" in out1,
               f"код {code1}; «ничего не нашла» и «ничего не искала» обязаны различаться")

    # ② ПРАВКА ПОСЛЕ ДОГОНА — красное. Это и есть предмет проверки.
    seed2, db2 = stand([(*RULE, "2026-08-20 23:40")])
    out2, code2 = run(seed2, db2)
    ok &= case("② правило изменено ПОСЛЕ догона — красное",
               code2 == 1 and "ПОСЛЕ догона" in out2,
               "правка живого свода могла унести урок, которого в посеве нет", differ=True)

    # ③ ВСТРЕЧНЫЙ к ②: та же правка, но ДО догона — молчание.
    #    Без него ② зеленел бы и у проверки, которая красит ЛЮБОЕ различие тел.
    seed3, db3 = stand([(*RULE, "2026-08-19 08:00")])
    out3, code3 = run(seed3, db3)
    ok &= case("③ ВСТРЕЧНЫЙ: та же правка, но ДО догона — молчит",
               code3 == 0 and "ПОСЛЕ догона" not in out3,
               "иначе проверка кричала бы на всё расхождение тел, то есть всегда", differ=True)

    # ④ МЕТКИ ДОГОНА НЕТ — сказано вслух. Молчание здесь означало бы «свежо»,
    #    а на деле означает «сравнивать не с чем».
    seed4, db4 = stand([(*RULE, "2026-08-20 23:40")], mark=None)
    out4, code4 = run(seed4, db4)
    # 🩸 14.09 (PROTO): случай ждал строку «НЕ ОТМЕЧЕН» — её печатала ПРЕЖНЯЯ редакция проверки.
    #    05.09 проверку усилили: без метки она ОТКАЗЫВАЕТ кодом 2 («В ПОСЕВЕ НЕТ МЕТКИ»), до строки
    #    «НЕ ОТМЕЧЕН» не доходит — и случай провалился на ВЕРНОМ поведении. Приёмку не поправили
    #    вместе с проверкой; найдено исполнителем при переводе имён (провал и до перевода).
    ok &= case("④ метки догона нет — отказ кодом 2 со словами «нет метки», а не выдано за чистоту",
               # «✅ отставших правил нет» — строка УСПЕХА; голое «отставших нет» есть и в тексте
               # самого отказа («…это ОТКАЗ, а не «отставших нет»») — по нему судить нельзя
               code4 == 2 and "НЕТ МЕТКИ" in out4 and "✅ отставших правил нет" not in out4,
               f"код {code4}; «судить о свежести нечем» и «свежо» — разные ответы", differ=True)

    # ⑤ ПОСЕВ НЕ ПРИМЕНЯЕТСЯ — отказ мерить отдельным кодом. Это находка сама по себе:
    #    на таком посеве ляжет сборка нового контура.
    seed5, db5 = stand([(*RULE, "2026-08-01 10:00")], seed_broken=True)
    out5, code5 = run(seed5, db5)
    ok &= case("⑤ посев не применяется к чистой базе — отказ мерить кодом 2",
               code5 == 2 and "НЕ ЗАПУСТИЛАСЬ" in out5,
               f"код {code5}; сборка нового контура на таком посеве ляжет", differ=True)

    # ⑥ 🪤 ОПЛАЧЕНО ПРИ РОЖДЕНИИ: посев КОРОЧЕ живого в разы — и это НОРМА.
    #    Первая редакция судила по длине и объявила «отстали 30» сразу после честного догона.
    long_rule = ("общее-правило",
               "НОРМА ЖИВЁТ ЗДЕСЬ. " + "Разбор случая контура-донора. " * 40, "active")
    seed6, db6 = stand([(*long_rule, "2026-08-01 10:00")])
    out6, code6 = run(seed6, db6)
    ok &= case("⑥ посев КОРОЧЕ живого в разы, но правок после догона нет — молчит",
               code6 == 0 and "отставших правил нет" in out6,
               "посев короче намеренно: чужие случаи в него не переносятся, и длина "
               "мерилом быть не может", differ=True)

    # ⑦ СНЯТОЕ У НАС, ЖИВОЕ В ПОСЕВЕ — отдельный исход, а не «отстало» и не «чисто».
    seed7, db7 = stand([("снятое-правило", "ЗАПРЕТ, КОТОРЫЙ У НАС ОТМЕНЁН", "revoked",
                          "2026-08-08 15:56")])
    out7, code7 = run(seed7, db7)
    ok &= case("⑦ правило снято у нас, а в посеве живое — названо отдельно",
               "СНЯТО, а в посеве живое" in out7,
               "новый контур получит его как действующее: это решение человека, "
               "а не молчаливая ошибка", differ=True)

    # ── ⑧…⑧-тер КАРТОЧКА #430 ③: ключ, определённый в файле дважды ────────────
    # 🩸 Оплачено COORD 29.08: его правка легла в ПЕРВОЕ определение и не доехала —
    # в базу разворачивается ПОСЛЕДНЕЕ, проверка была зелёной, находку дал встречный
    # случай «развернуть посев в чистую базу и прочитать ОТТУДА».
    SHORT_BODY = RULE[1].split(".")[0] + "."
    seed8, db8 = stand([(*RULE, "2026-08-01 10:00")],
                        duplicate=("общее-правило", SHORT_BODY, False))
    out8, code8 = run(seed8, db8)
    ok &= case("⑧ НЕМОЙ дубль ключа → назван ⚠ поимённо (жёлтым: живой посев несёт 27 "
               "наслоений, красное на всех учило бы не верить)",
               code8 == 0 and "БЕЗ объявления" in out8 and "общее-правило" in out8,
               "правку кладут в текст, который не исполняется, — прежде проверка молчала",
               differ=True)

    seed8bis, db8bis = stand([(*RULE, "2026-08-01 10:00")],
                          duplicate=("общее-правило", SHORT_BODY, True))
    out8bis, code8bis = run(seed8bis, db8bis)
    ok &= case("⑧-бис ВСТРЕЧНЫЙ: дубль ОБЪЯВЛЕН маркером → назван без красноты",
               code8bis == 0 and "ОБЪЯВЛЕН" in out8bis and "БЕЗ объявления" not in out8bis,
               "удаление мёртвого блока — разрушающее, словом владельца; объявленный "
               "дубль — знание, а не находка", differ=True)

    # ⑧-тер ВСТРЕЧНЫЙ критерия: вердикт совпадает с тем, что ЧИТАЕТСЯ из развёрнутой
    # базы. Живой свод несёт тело ПОЗДНЕГО определения; в посеве раннее и позднее
    # РАЗНЫЕ — «совпадают дословно 1» возможно только если судится доезжающее.
    d8ter = mezo_stand.new("bite-seed-dup-")
    db8ter = d8ter / "live.db"
    con8 = sqlite3.connect(str(db8ter))
    con8.execute("""CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT UNIQUE,
                    body TEXT, locked_by TEXT, version INT, status TEXT, updated_at TEXT)""")
    con8.execute("INSERT INTO rules (rule_key, body, locked_by, version, status, updated_at)"
                 " VALUES ('к430','ПОЗДНЕЕ ТЕЛО.','owner',1,'active','2026-08-01 10:00')")
    con8.commit()
    con8.close()
    seed8ter = d8ter / "seed.sql"
    seed8ter.write_text(
        "-- посев\n-- ПОСЛЕДНИЙ ДОГОН ПОСЕВА: " + CATCHUP + "\n"
        "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
        "('к430',\n 'РАННЕЕ ТЕЛО.',\n 'owner', 1);\n"
        "-- ⚠️ ВЫШЕ МЁРТВОЕ ОПРЕДЕЛЕНИЕ: тот же ключ 'к430' определён ещё раз ниже\n"
        "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
        "('к430',\n 'ПОЗДНЕЕ ТЕЛО.',\n 'owner', 1);\n",
        encoding="utf-8")
    out8ter, code8ter = run(seed8ter, db8ter)
    ok &= case("⑧-тер вердикт совпадает с РАЗВЁРНУТОЙ базой: судится доезжающее",
               code8ter == 0 and "совпадают дословно 1" in out8ter,
               "тела раннего и позднего разные; «совпадают дословно 1» возможно, только "
               "если сличается ПОСЛЕДНЕЕ — то, что получит новый контур", differ=True)

    # ── ⑨…⑨-тер СНЯТИЕ В ПОСЕВЕ (25.09): посев несёт в новый контур снятое правило строкой
    # UPDATE rules SET status='revoked' … — слово владельца о двух правилах ритма.
    # 🩸 Прежняя проверка применяла посев к СВОЕЙ урезанной таблице без status и падала
    # «no such column», хотя настоящая сборка контура такой посев принимает.
    ok &= check_revoked_in_seed()

    print()
    print(f"{'✅ ПРОВЕРКА ПОСЕВА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
