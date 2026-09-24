#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА РАЗГОНА СНА МЕЖДУ СИНКАМИ (слово владельца 2026-08-08 19:06 UTC).

Замысел: тишина → спим на 5 минут дольше, до потолка 50. Появилось новое → сброс.
Одно место на весь контур, чтобы шаг и потолок правились централизованно.

⚖️ Опаснее всего здесь не арифметика, а ДВА молчаливых исхода:
    · роль объявила тишину, не посмотрев ⇒ разгон растёт при живой ленте;
    · разгон обнулился при перезапуске чата ⇒ правило есть, а эффекта нет.
Поэтому различающие случаи проверяют не «5+5=10», а ЧТО СЧИТАЕТСЯ тишиной и ПЕРЕЖИВАЕТ ли
состояние перезапуск.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① первый опрос — НЕ тишина: начинаем с начала        контроль: функция вообще работает
  ② тишина → +5 мин, и так подряд                                  РАЗЛИЧАЮЩИЙ
  ③ ПОТОЛОК 50 держится, сколько бы тишин ни было                  РАЗЛИЧАЮЩИЙ
  ④ появилась ЧУЖАЯ записка → СБРОС к началу                       РАЗЛИЧАЮЩИЙ
  ⑤ появилась СВОЯ записка → это НЕ повод будить себя, разгон идёт РАЗЛИЧАЮЩИЙ
  ⑥ состояние ПЕРЕЖИВАЕТ перезапуск (лежит в базе, не в памяти)    РАЗЛИЧАЮЩИЙ
  ⑦ у РАЗНЫХ ролей разгон СВОЙ, они не мешают друг другу           РАЗЛИЧАЮЩИЙ
  ⑧ параметры печатаются в строке — их нельзя пересказать по памяти неверно
  ⑨ база недоступна → строка ГОВОРИТ об отказе, а не молчит

📌 24.09 (план «убрать будильники», записка #5312): чтение ленты печатает строку сна, только
пока правило sync-sleep-backoff действует; иначе — счёт нового с прошлого чтения.
  ⑩ счёт нового: первое чтение названо первым, а не «нового ноль»
  ⑪ счёт нового: чужие записки считаются, свои — нет; второе чтение подряд — ноль   РАЗЛИЧАЮЩИЙ
  ⑫ счёт нового сон НЕ трогает: разгон роли прежний                               РАЗЛИЧАЮЩИЙ
  ⑬ правило ритма действует → строка сна; снято → только счёт нового                 РАЗЛИЧАЮЩИЙ
  ⑭ правил в базе нет вовсе → счёт нового: ритма без правила не бывает
  ⑮ база недоступна → строка счёта ГОВОРИТ об отказе

⛔ Живой базы не касается: своя песочница.
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

sys.path.insert(0, str(mezo_target.scripts_root()))
import sync_backoff as sb  # noqa: E402

CASES = DIFFER = 0
# Образцы поиска прежней строки сна в выводе механизма — не текст для человека.
SLEEP_LINE_RE = re.compile(r"СЛЕДУЮЩИЙ\s+СИНК")
SLEEP_WORD_RE = re.compile(r"СИНК")


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    db = os.path.join(mezo_stand.new("bite-backoff-"), "s.db")
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   writer_role TEXT, body_md TEXT)""")
    con.commit()
    con.close()
    return db


def add(db, role):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO messages (writer_role, body_md) VALUES (?, 'тело')", (role,))
    con.commit()
    con.close()


def main() -> int:
    ok = True
    db = build()
    add(db, "COORD")                       # в ленте уже что-то есть

    r1 = sb.next_sleep(db, "PROTO")
    ok &= case("① первый опрос — НЕ тишина, начинаем с начала (контроль: функция работает)",
               r1["minutes"] == sb.START_SEC // 60 and r1["quiet"] is False,
               f"{r1['minutes']} мин · {r1['reason']}")

    r2 = sb.next_sleep(db, "PROTO")
    r3 = sb.next_sleep(db, "PROTO")
    ok &= case("② тишина подряд — сон растёт шагом",
               r2["minutes"] == 10 and r3["minutes"] == 15 and r3["streak"] == 2,
               f"{r1['minutes']} → {r2['minutes']} → {r3['minutes']} мин, тишин подряд "
               f"{r3['streak']}", differ=True)

    for _ in range(20):
        rc = sb.next_sleep(db, "PROTO")
    ok &= case("③ ПОТОЛОК держится, сколько бы тишин ни было",
               rc["minutes"] == sb.MAX_SEC // 60 and "ПОТОЛОК" in rc["reason"],
               f"после 20 тишин подряд — {rc['minutes']} мин, потолок {sb.MAX_SEC // 60}",
               differ=True)

    add(db, "CORE")
    r4 = sb.next_sleep(db, "PROTO")
    ok &= case("④ появилась ЧУЖАЯ записка — СБРОС к началу",
               r4["minutes"] == sb.START_SEC // 60 and r4["quiet"] is False
               and r4["new_count"] == 1,
               f"{rc['minutes']} → {r4['minutes']} мин · чужих новых {r4['new_count']}",
               differ=True)

    add(db, "PROTO")                       # СВОЯ записка
    r5 = sb.next_sleep(db, "PROTO")
    ok &= case("⑤ СВОЯ записка тишину НЕ отменяет — иначе роль будила бы себя сама",
               r5["quiet"] is True and r5["minutes"] == 10,
               f"{r4['minutes']} → {r5['minutes']} мин, тишина={r5['quiet']}", differ=True)

    # ⑥ перезапуск: новый процесс, та же база — состояние обязано лежать в базе
    import importlib
    importlib.reload(sb)
    r6 = sb.next_sleep(db, "PROTO")
    ok &= case("⑥ состояние ПЕРЕЖИВАЕТ перезапуск — оно в базе, а не в памяти чата",
               r6["minutes"] == 15,
               f"после перезагрузки модуля продолжили с {r5['minutes']} → {r6['minutes']} мин, "
               "а не с начала", differ=True)

    r7 = sb.next_sleep(db, "TAXO")
    ok &= case("⑦ у другой роли разгон СВОЙ",
               r7["minutes"] == sb.START_SEC // 60 and
               sb.next_sleep(db, "PROTO")["minutes"] == 20,
               f"TAXO {r7['minutes']} мин (её первый опрос), PROTO продолжает свой разгон",
               differ=True)

    ln = sb.line(db, "PROTO")
    ok &= case("⑧ параметры печатаются в строке, а не живут в чьей-то памяти",
               all(x in ln for x in ("начало", "шаг", "потолок")),
               ln[:120])

    bad = sb.line(os.path.join(mezo_stand.new("bite-sync-backoff-"), "нет.db"), "PROTO")
    ok &= case("⑨ база недоступна — строка ГОВОРИТ об отказе, а не молчит",
               "НЕ ПОСЧИТАН" in bad and "НЕ «спи сколько хочешь»" in bad,
               "молчание тут прочлось бы как разрешение спать сколько угодно")

    # ═══ ⑩–⑮ счёт нового без сна (24.09) — на своей базе, чтобы не путать с разгоном выше
    db2 = build()
    add(db2, "COORD")
    n1 = sb.news(db2, "ING")
    first_line = sb.news_line(build(), "ING")
    ok &= case("⑩ первое чтение названо первым, а не «нового ноль»",
               n1["first"] is True and "первое чтение" in first_line,
               first_line[:100])

    add(db2, "COORD")
    add(db2, "CORE")
    add(db2, "ING")                        # СВОЯ записка — не новость
    n2 = sb.news(db2, "ING")
    n3 = sb.news(db2, "ING")
    ok &= case("⑪ чужие записки считаются, свои — нет; второе чтение подряд — ноль",
               n2["new_count"] == 2 and n3["new_count"] == 0,
               f"после 2 чужих и 1 своей: {n2['new_count']}; сразу снова: {n3['new_count']}",
               differ=True)

    before = sb.next_sleep(db2, "ING")["minutes"]
    for _ in range(3):
        sb.news(db2, "ING")
    con = sqlite3.connect(db2)
    sleep_after = con.execute("SELECT sleep_sec FROM sync_backoff WHERE role='ING'").fetchone()[0]
    con.close()
    ok &= case("⑫ счёт нового сон НЕ трогает — разгон роли остаётся прежним",
               sleep_after // 60 == before,
               f"сон до трёх счётов {before} мин, после {sleep_after // 60} мин", differ=True)

    con = sqlite3.connect(db2)
    con.execute("CREATE TABLE rules (rule_key TEXT PRIMARY KEY, status TEXT)")
    con.execute("INSERT INTO rules VALUES ('sync-sleep-backoff', 'active')")
    con.commit()
    con.close()
    active_line = sb.reader_line(db2, "ING")
    con = sqlite3.connect(db2)
    con.execute("UPDATE rules SET status='revoked' WHERE rule_key='sync-sleep-backoff'")
    con.commit()
    con.close()
    retired_line = sb.reader_line(db2, "ING")
    ok &= case("⑬ правило ритма действует → строка сна; снято → только счёт нового",
               bool(SLEEP_LINE_RE.search(active_line)) and not SLEEP_WORD_RE.search(retired_line)
               and "с прошлого чтения" in retired_line,
               f"действует: {active_line[:50]}… · снято: {retired_line[:70]}", differ=True)

    no_rules_line = sb.reader_line(db, "PROTO")      # в первой базе таблицы правил нет
    ok &= case("⑭ правил в базе нет вовсе → счёт нового: ритма без правила не бывает",
               not SLEEP_WORD_RE.search(no_rules_line) and "с прошлого чтения" in no_rules_line,
               no_rules_line[:100])

    bad_news = sb.news_line(os.path.join(mezo_stand.new("bite-sync-backoff-"), "нет.db"), "PROTO")
    ok &= case("⑮ база недоступна — строка счёта ГОВОРИТ об отказе",
               "НЕ ПОСЧИТАНО" in bad_news, bad_news[:100])

    print()
    print(f"{'✅ РАЗГОН СНА ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
