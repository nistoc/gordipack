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

⛔ Живой базы не касается: своя песочница.
"""
import os
import sqlite3
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом

sys.path.insert(0, str(mezo_target.scripts_root()))
import sync_backoff as sb  # noqa: E402

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    db = os.path.join(tempfile.mkdtemp(prefix="bite-backoff-"), "s.db")
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

    bad = sb.line(os.path.join(tempfile.mkdtemp(), "нет.db"), "PROTO")
    ok &= case("⑨ база недоступна — строка ГОВОРИТ об отказе, а не молчит",
               "НЕ ПОСЧИТАН" in bad and "НЕ «спи сколько хочешь»" in bad,
               "молчание тут прочлось бы как разрешение спать сколько угодно")

    print()
    print(f"{'✅ РАЗГОН СНА ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
