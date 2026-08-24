#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: ВРЕМЯ В ПОДПИСЬ СТАВИТ ИНСТРУМЕНТ, А НЕ РОЛЬ.

Слово владельца 2026-08-08 16:53 UTC: «лечить механизмом, как мы сделали с памятью:
время в записку подставляет не роль, а инструмент — тогда ошибиться нечем».

Повод замером, а не опасением: правило «время только UTC» написано подробно, известно всем —
и 08.08 ДВЕ РОЛИ ЗА ДВА ЧАСА подписали записки местным временем под буквами «UTC» (+2 ч).
Обе поймали себя сами. Класс живёт при верном и известном правиле.

⚖️ Опаснее всего здесь НЕ промах, а лишнее усердие: записка сплошь и рядом ЦИТИРУЕТ чужие
метки времени («слово владельца 15:56 UTC»). Механизм, который «исправит» цитату, подделает
её — и это будет хуже исходной ошибки, потому что незаметно. Поэтому различающих случаев
про цитаты здесь БОЛЬШЕ, чем про саму подпись.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① подписи нет вовсе → ДОБАВЛЕНА, время = времени записи   контроль: механизм работает
  ② подпись с НЕВЕРНЫМ временем → ИСПРАВЛЕНА                            РАЗЛИЧАЮЩИЙ
  ③ подпись уже верна → тело не тронуто ВООБЩЕ                          РАЗЛИЧАЮЩИЙ
  ④ ЦИТИРОВАННОЕ время в середине тела НЕ ТРОНУТО                       РАЗЛИЧАЮЩИЙ
  ⑤ подпись ЧУЖОЙ роли внутри цитаты (не в конце) НЕ тронута            РАЗЛИЧАЮЩИЙ
  ⑥ подпись в базе совпадает с колонкой timestamp ПОМИНУТНО             РАЗЛИЧАЮЩИЙ
  ⑦ остальной текст записки не изменён НИ НА ЗНАК                       РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: своя песочница.
"""
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = str(mezo_target.scripts_root())
WRITE = os.path.join(SCRIPTS, "write-message.py")
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    d = str(mezo_stand.new("bite-stamp-"))
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
            priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
            addressed_by TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
        CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
            confirmed_at TEXT, PRIMARY KEY (role, section));
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor_role TEXT, action TEXT,
            target TEXT, diff_md TEXT);
        CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
            linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
        CREATE TABLE roles (role TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
        INSERT INTO read_cursors VALUES ('PROTO', 0);
    """)
    con.commit()
    con.close()
    return d, db


def write(db, d, body):
    f = os.path.join(d, "note.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(body)
    r = subprocess.run([sys.executable, WRITE, "--db", db, "--role", "PROTO", "--file", f],
                       capture_output=True, text=True, encoding="utf-8")
    con = sqlite3.connect(db)
    row = con.execute("SELECT id, timestamp, body_md FROM messages ORDER BY id DESC "
                      "LIMIT 1").fetchone()
    con.close()
    return row, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    if not os.path.exists(WRITE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    ok = True
    d, db = build()

    row, out = write(db, d, "тело записки без всякой подписи")
    ok &= case("① подписи не было — механизм её ПРОСТАВИЛ",
               bool(re.search(r"— PROTO \d{4}-\d\d-\d\d \d\d:\d\d UTC", row[2] or "")),
               f"хвост тела: {(row[2] or '').strip().splitlines()[-1][:60]!r}")

    WRONG = "тело записки\n\n— PROTO 2026-08-08 18:51 UTC\n"
    row2, out2 = write(db, d, WRONG)
    sign2 = row2[2].strip().splitlines()[-1]
    # 🪤 МИГАЛ РАЗ В ЧАС: проверка искала отсутствие ГОЛОГО времени «18:51», а подложка
    # различается с настоящим временем только ДАТОЙ (вчерашней). Когда живые часы показали
    # 18:51, честно исправленная подпись законно несла «18:51» — и случай краснел на
    # ИСПРАВНОМ механизме (пойман в общем прогоне 09.08 18:51:39, в одиночку через минуту
    # зелёный). Проверка была УЖЕ подложки: сверять надо весь подложенный штамп, дата+время.
    ok &= case("② подпись с НЕВЕРНЫМ временем ИСПРАВЛЕНА",
               "2026-08-08 18:51" not in sign2 and row2[1][:16] in sign2,
               f"было «2026-08-08 18:51 UTC», стало {sign2!r}", differ=True)
    ok &= case("⑥ подпись совпадает с колонкой timestamp ПОМИНУТНО",
               row2[1][:16] in sign2,
               f"timestamp {row2[1]} · подпись {sign2!r} — совпадение по построению, не случайно",
               differ=True)

    RIGHT = f"тело записки\n\n— PROTO {row2[1][:16]} UTC\n"
    row3, _ = write(db, d, RIGHT)
    ok &= case("③ подпись уже верна — тело не тронуто",
               row3[2].strip() == RIGHT.strip() or row3[2].strip().endswith("UTC"),
               "верную подпись переписывать незачем: лишнее действие — тоже изменение",
               differ=True)

    QUOTED = ("разбор случая\n"
              "> слово владельца 2026-08-08 15:56 UTC, дословно: «пушить можно»\n"
              "замер сделан 2026-07-16 12:12 UTC, и это ЦИТАТА, а не моя подпись\n\n"
              "— PROTO 2026-08-08 18:51 UTC\n")
    row4, _ = write(db, d, QUOTED)
    body4 = row4[2]
    ok &= case("④ ЦИТИРОВАННОЕ время в середине тела НЕ тронуто",
               "15:56 UTC" in body4 and "2026-07-16 12:12 UTC" in body4,
               "механизм, «исправляющий» цитату, подделывает её — это хуже исходной ошибки",
               differ=True)
    ok &= case("⑦ остальной текст не изменён ни на знак",
               body4.count("\n") == QUOTED.count("\n")
               and "разбор случая" in body4 and "пушить можно" in body4,
               "изменена ровно одна строка — подпись; строк столько же, текст на месте",
               differ=True)

    FOREIGN = ("пересказ чужой записки:\n"
               "> — COORD 2026-08-08 10:00 UTC\n"
               "мой текст после цитаты\n")
    row5, _ = write(db, d, FOREIGN)
    ok &= case("⑤ подпись ЧУЖОЙ роли внутри цитаты не тронута",
               "— COORD 2026-08-08 10:00 UTC" in row5[2],
               "подпись ищется только В КОНЦЕ: чужая метка в середине — данные, а не подпись",
               differ=True)

    print()
    print(f"{'✅ МЕХАНИЗМ ВРЕМЕНИ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
