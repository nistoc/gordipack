#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: ВИТРИНА «ТОЛЬКО ОБРАЩЁННОЕ КО МНЕ» ОТВЕЧАЕТ ПРО СВОЁ ПОДМНОЖЕСТВО, А НЕ ПРО ЛЕНТУ.

Предмет. Находка @opssre (записка #3442, 2026-08-08 16:52 UTC): в ПУСТОЙ ветке витрина
печатала «Нет непрочитанных сообщений» — утверждение о ВСЕЙ ЛЕНТЕ, глядя в узкий отбор.
У него в тот момент непрочитанных было ДВЕ, курсор в обеих витринах одинаковый.
🎯 Ветка, где механизм молчит ПО ДЕЛУ, — единственная, где он говорил неправду, и приходит
она ровно тогда, когда роль склонна решить, что дочитала.
⚖️ И она спорила с правилом `full-scan-every-tick` v5 («витрина задаёт лишь ПОРЯДОК чтения»),
записанным за восемь минут до находки: свод и механизм разошлись, а роль верит механизму —
он отвечает ей лично и сейчас, а правило надо пойти и спросить.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① витрина вообще отвечает, когда обращённое ЕСТЬ       контроль: механизм работает
  ② обращённого НЕТ, а в ленте непрочитанное ЕСТЬ:
     сказано И «лично тебе не писали», И «в ленте N»                 РАЗЛИЧАЮЩИЙ
  ③ строка про ЛЕНТУ стоит ПОСЛЕ строки про обращённое              РАЗЛИЧАЮЩИЙ
     (решение «читать дальше» роль принимает по ПОСЛЕДНЕЙ строке — класс @CORE #3436)
  ④ ложного «Нет непрочитанных сообщений» в этой ветке НЕТ ВОВСЕ    РАЗЛИЧАЮЩИЙ
  ⑤ курсор У ГОЛОВЫ: «непрочитанного нет» ЗАКОННО и не исчезло      РАЗЛИЧАЮЩИЙ
     ⚖️ второе плечо: починка первого не имеет права съесть эту правду
  ⑥ витрина НЕ выдаёт ключа подтверждения и НЕ двигает курсор       РАЗЛИЧАЮЩИЙ
  ⑦ ОБЫЧНОЕ чтение (без витрины) на пустой ленте говорит по-прежнему РАЗЛИЧАЮЩИЙ
     ⛔ ЗАПРЕЩЁННЫЙ способ пройти приёмку (назван @opssre в #3442): проверить только
        на роли, у которой обращённое ЕСТЬ. Там дефекта нет ПО ПОСТРОЕНИЮ.

⛔ Живой базы не касается: своя песочница. Структура таблиц зафиксирована ЗДЕСЬ, а не
   считывается из живого контура — иначе приёмка шаблона молча испытывала бы оригинал
   (карточка #148).
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402  — какую копию испытываем, решается ОДНИМ местом

CLI = str(mezo_target.script("read-messages.py"))
CASES = DIFFER = 0

DDL = """
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    writer_role TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    body_md TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    priority TEXT DEFAULT 'normal',
    resolved INTEGER DEFAULT 0,
    broadcast INTEGER NOT NULL DEFAULT 0,
    addressed_by TEXT NOT NULL DEFAULT 'unset'
        CHECK (addressed_by IN ('field','backfill','unset')));
CREATE TABLE read_cursors (
    reader_role TEXT PRIMARY KEY,
    last_read_id INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE read_batches (
    token TEXT PRIMARY KEY, role TEXT NOT NULL, last_id INTEGER NOT NULL,
    issued_at TEXT NOT NULL DEFAULT (datetime('now')), shown_max INTEGER, acked_at TEXT);
CREATE TABLE message_addressee (
    message_id INTEGER NOT NULL REFERENCES messages(id),
    role TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('to','cc')),
    linked_by TEXT NOT NULL DEFAULT 'field' CHECK (linked_by IN ('field','backfill')),
    PRIMARY KEY (message_id, role, kind));
"""


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build(cursor_at, to_whom=None):
    """Песочница: три записки; курсор роли — на cursor_at. to_whom — кому адресована #3."""
    db = os.path.join(tempfile.mkdtemp(prefix="bite-tome-"), "s.db")
    con = sqlite3.connect(db)
    con.executescript(DDL)
    for i in (1, 2, 3):
        con.execute("INSERT INTO messages (id, writer_role, body_md, timestamp) "
                    "VALUES (?, 'COORD', ?, '2026-08-09 10:0" + str(i) + ":00')",
                    (i, f"тело записки {i}"))
    if to_whom:
        con.execute("INSERT INTO message_addressee (message_id, role, kind) VALUES (3, ?, 'to')",
                    (to_whom,))
    con.execute("INSERT INTO read_cursors (reader_role, last_read_id) VALUES ('PROTO', ?)",
                (cursor_at,))
    con.commit()
    con.close()
    return db


def run(db, *args):
    r = subprocess.run([sys.executable, CLI, "--db", db, *args],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or "")


def main():
    ok = True

    # ① КОНТРОЛЬ: обращённое ЕСТЬ — витрина показывает тела
    db = build(cursor_at=1, to_whom="PROTO")
    out = run(db, "--role", "PROTO", "--to-me")
    ok &= case("① витрина отвечает, когда обращённое есть",
               "тело записки 3" in out,
               f"показано тело адресованной записки: {'да' if 'тело записки 3' in out else 'НЕТ'}")

    # ②③④ ГЛАВНЫЙ СЛУЧАЙ: обращённого нет, а лента НЕ пуста
    db = build(cursor_at=1, to_whom="CORE")   # #3 адресована ЧУЖОЙ роли
    out = run(db, "--role", "PROTO", "--to-me")
    said_mine = "Обращённого ЛИЧНО к тебе среди непрочитанных НЕТ" in out
    said_feed = "В ЛЕНТЕ непрочитанных: 2" in out
    ok &= case("② сказано И про подмножество, И про ленту (непрочитанных 2)",
               said_mine and said_feed,
               f"про подмножество: {said_mine} · про ленту: {said_feed}", differ=True)

    order_ok = said_mine and said_feed and out.index("В ЛЕНТЕ непрочитанных") > out.index(
        "Обращённого ЛИЧНО к тебе")
    ok &= case("③ строка про ЛЕНТУ стоит ПОСЛЕ строки про обращённое",
               order_ok,
               "решение «читать дальше» роль принимает по последней строке", differ=True)

    ok &= case("④ ложного «Нет непрочитанных сообщений» нет вовсе",
               "Нет непрочитанных сообщений" not in out,
               "именно эта строка и была неправдой о ленте", differ=True)

    # ⑤ ВТОРОЕ ПЛЕЧО: отметка прочитанного у головы — «непрочитанного нет» ЗАКОННО
    db = build(cursor_at=3, to_whom="CORE")
    out5 = run(db, "--role", "PROTO", "--to-me")
    ok &= case("⑤ курсор у головы: сказано, что и в ленте пусто",
               "в самой ленте непрочитанного нет" in out5 and "В ЛЕНТЕ непрочитанных" not in out5,
               "починка первого плеча не съела законную правду второго", differ=True)

    # ⑥ витрина не выдаёт ключа и не двигает курсор
    db = build(cursor_at=1, to_whom="PROTO")
    out6 = run(db, "--role", "PROTO", "--to-me")
    con = sqlite3.connect(db)
    moved = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role='PROTO'"
                        ).fetchone()[0]
    con.close()
    ok &= case("⑥ курсор НЕ двинут и ключа подтверждения нет",
               moved == 1 and "--ack" not in out6,
               f"курсор остался {moved}; ключ в выводе: {'есть' if '--ack' in out6 else 'нет'}",
               differ=True)

    # ⑦ ОБЫЧНОЕ чтение на пустой ленте — прежний текст, он верен по существу
    db = build(cursor_at=3)
    out7 = run(db, "--role", "PROTO")
    ok &= case("⑦ обычное чтение на пустой ленте говорит «Нет непрочитанных сообщений»",
               "Нет непрочитанных сообщений" in out7,
               "правка витрины не тронула обычное чтение — предметы разные", differ=True)

    print("-" * 78)
    print(f"случаев {CASES} · различающих {DIFFER} · "
          f"{'ДЕРЖИТСЯ' if ok else '🔴 СЛОМАНО'}")
    which = "ЖИВОЙ контур" if str(mezo_target.scripts_root()) == str(mezo_target.LIVE_SCRIPTS) \
        else f"копия: {mezo_target.scripts_root()}"
    print(f"испытан: {which}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
