#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PLANTS: messages_archive
r"""ПРИЁМКА шага схемы «архив ленты по возрасту» + функции разрешения номера «#N».
Карточка #538, шаг ③ регламента сжатия (правило history-compression-policy v2, раздел ①:
«проверка ссылок обязана существовать ДО переноса; пока хоть один читатель ссылку не находит —
переноса нет»). Слово COORD по правилу — записка #4855.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ⓪ КОНТРОЛЬ: шаг схемы на копии живой базы — «ВРЕЗАНО» (или «уже сведено»), таблица · вид с
     третьим источником · журнал схемы; отпечаток вида ДО == ПОСЛЕ при пустом архиве
     (самый дешёвый встречный, назван COORD)
  ① повтор шага — «уже сведено», ничего не меняет                                РАЗЛИЧАЮЩИЙ
  ② функция: живая записка → 'live' · ретро-импорт → 'history' · чужой номер → None
  ③ перенос ОДНОЙ старой записки С АДРЕСАТАМИ в архив копии → функция находит её как 'archive',
     вид отдаёт source='archive', строки адресатов на месте                       РАЗЛИЧАЮЩИЙ
  ④ ОБРАТНЫЙ ВСТРЕЧНЫЙ (просьба COORD Ⓑ): несуществующий номер по-прежнему НЕ находится —
     и после переноса; иначе «разрешается в архив» станет «разрешается всё»    РАЗЛИЧАЮЩИЙ
  ⑤ первый читатель — write-message.py: --ack на унесённую записку НЕ отвечает «такой ноты нет»,
     а --reply-to --resolves ставит resolved у цели В АРХИВЕ (прежде UPDATE messages менял ноль
     строк молча)                                                                 РАЗЛИЧАЮЩИЙ
  ⑥ граница внешнего ключа НАЗВАНА ВСЛУХ: у унесённой записки адресаты остаются, но JOIN messages
     их теряет, JOIN messages_all — нет (это условие для инструмента переноса)   РАЗЛИЧАЮЩИЙ

ПОРЧА (рядом с оригиналом, живой файл не тронут): у функции отнимают источник 'archive' —
ожидание: красны ③ и ⑤ (ack унесённой — «нет»), ④ и ② целы.
    python <КОНТУР>/vnext-tools/bite-messages-archive.py --porcha no-archive

⛔ Живого контура не касается: всё — на копии базы во временном каталоге; write-message.py
зовётся с --db <копия>.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

SCRIPTS = pathlib.Path(mezo_paths.live_scripts(__file__))
LIVE = pathlib.Path(mezo_paths.live_db(__file__))
STEP = SCRIPTS / "migrations" / "20260905-messages-archive.py"
WRITER = SCRIPTS / "write-message.py"

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def copy_db(stand: pathlib.Path) -> pathlib.Path:
    db = stand / "mezosync.db"
    src = sqlite3.connect(f"file:{LIVE.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close(); dst.close()
    return db


def run_tool(script: pathlib.Path, *args, env=None):
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                       encoding="utf-8", timeout=300, env=env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def view_fingerprint(conn) -> str:
    h = hashlib.sha256()
    for row in conn.execute("SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, source "
                            "FROM messages_all ORDER BY source, id"):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()[:16]


def seed_if_needed(db: pathlib.Path) -> list[str]:
    """На пустом контуре (пакет без истории) ленты нет вовсе — ни живой, ни ретро-импорта,
    ни старой записки с адресатами. Случаи ②③⑤ ставить не на чем: живая = MAX(id) FROM
    messages даёт NULL, mezo_refs.resolve(conn, None) падает на int(None) и возвращает
    None, а бул-цепочка `r_live and ...` рушит ok &= TypeError'ом (пойман прогоном пакета,
    карточка #667). Сеем СВОЁ, и только то, чего не хватает — на живом контуре, где всё
    это уже есть, функция не трогает ничего.
    """
    added = []
    con = sqlite3.connect(str(db))
    con.execute("INSERT OR IGNORE INTO roles (role, lifecycle) VALUES ('PROTO', 'alive')")
    if con.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0:
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                    " VALUES ('PROTO', datetime('now'), ?, '[]', 'normal')",
                    ("посев приёмки #538 bite-messages-archive: своя живая запись (live)",))
        added.append("live")
    if con.execute("SELECT COUNT(*) FROM messages_history").fetchone()[0] == 0:
        con.execute("INSERT INTO messages_history (id, writer_role, timestamp, body_md)"
                    " VALUES (900000001, 'PROTO', datetime('now','-400 days'), ?)",
                    ("посев приёмки #538 bite-messages-archive: своя ретро-импортная запись",))
        added.append("history")
    old_with_addressee = con.execute(
        "SELECT 1 FROM messages m WHERE m.timestamp < datetime('now','-7 days') AND EXISTS"
        " (SELECT 1 FROM message_addressee a WHERE a.message_id=m.id) LIMIT 1").fetchone()
    if not old_with_addressee:
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                    " VALUES ('PROTO', datetime('now','-10 days'), ?, '[]', 'normal')",
                    ("посев приёмки #538 bite-messages-archive: своя старая запись с адресатом",))
        old_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO message_addressee (message_id, role, kind, linked_by)"
                    " VALUES (?, 'PROTO', 'to', 'field')", (old_id,))
        added.append("старая-с-адресатом")
    con.commit()
    con.close()
    return added


def move_to_archive(conn, mid: int):
    row = conn.execute("SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, broadcast, "
                       "addressed_by FROM messages WHERE id=?", (mid,)).fetchone()
    conn.execute("INSERT INTO messages_archive (id, writer_role, timestamp, body_md, tags, priority, resolved, "
                 "broadcast, addressed_by, moved_by, rule) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 row + ("bite", "history-compression-policy v2"))
    conn.execute("DELETE FROM messages WHERE id=?", (mid,))
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["no-archive"], default=None,
                    help="нарочная поломка функции разрешения (копия модуля рядом с оригиналом)")
    a = ap.parse_args()
    for f in (STEP, WRITER, SCRIPTS / "mezo_refs.py"):
        if not f.exists():
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет механизма — {f}")

    stand = mezo_stand.new("bite-msg-archive-")
    # Копия каталога скриптов: порча кладётся В КОПИЮ, живой файл не тронут; write-message.py
    # зовётся из копии, чтобы читал ту же (порченую или целую) функцию, что и приёмка.
    scripts_copy = stand / "scripts"
    shutil.copytree(SCRIPTS, scripts_copy, ignore=shutil.ignore_patterns("__pycache__"))
    if a.porcha == "no-archive":
        p = scripts_copy / "mezo_refs.py"
        s = p.read_text(encoding="utf-8")
        assert 'ИСТОЧНИКИ = (("live", "messages"), ("archive", "messages_archive"), ("history", "messages_history"))' in s
        s = s.replace('("archive", "messages_archive"), ', "")
        p.write_text(s, encoding="utf-8")
        print("💥 ПОРЧА no-archive: у функции отнят источник 'archive' (копия модуля). Ожидание: красны ③ ⑤, целы ② ④")
    sys.path.insert(0, str(scripts_copy))
    import mezo_refs  # noqa: E402  — из КОПИИ

    ok = True
    db = copy_db(stand)
    seeded = seed_if_needed(db)
    if seeded:
        print(f"🌱 посев приёмки (на пустом контуре не хватало): {', '.join(seeded)}")
    conn0 = sqlite3.connect(str(db))
    fp_before = view_fingerprint(conn0) if conn0.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='messages_all'").fetchone() else None
    conn0.close()

    # ⓪ КОНТРОЛЬ
    out0, code0 = run_tool(scripts_copy / "migrations" / "20260905-messages-archive.py", "--db", str(db))
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    vsql = (conn.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='messages_all'").fetchone() or [""])[0]
    journal = conn.execute("SELECT 1 FROM schema_migrations WHERE version='20260905-messages-archive'").fetchone()
    fp_after = view_fingerprint(conn)
    ok &= case("⓪ контроль: шаг схемы на копии — таблица, вид с 'archive', журнал; вид отдаёт то же при пустом архиве",
               code0 == 0 and ("ВРЕЗАНО" in out0 or "уже сведено" in out0) and "messages_archive" in tables
               and "'archive'" in vsql and journal is not None and (fp_before is None or fp_before == fp_after),
               f"код {code0}; отпечаток вида до {fp_before} · после {fp_after}")

    # ① ПОВТОР
    out1, code1 = run_tool(scripts_copy / "migrations" / "20260905-messages-archive.py", "--db", str(db))
    ok &= case("① повтор шага — «уже сведено», отпечаток вида не меняется",
               code1 == 0 and "уже сведено" in out1 and view_fingerprint(conn) == fp_after,
               "шаг обязан быть идемпотентным: второй прогон не имеет права трогать базу", differ=True)

    # ② ФУНКЦИЯ — три источника
    live_id = conn.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    import_id = conn.execute("SELECT MIN(id) FROM messages_history").fetchone()[0]
    r_live = mezo_refs.resolve(conn, live_id)
    r_hist = mezo_refs.resolve(conn, import_id) if import_id else {"source": "history"}
    r_none = mezo_refs.resolve(conn, 99_999_999)
    ok &= case("② функция: живая → 'live' · ретро-импорт → 'history' · чужой номер → None",
               r_live and r_live["source"] == "live" and r_hist and r_hist["source"] == "history" and r_none is None,
               f"live #{live_id} → {r_live and r_live['source']} · history #{import_id} → {r_hist and r_hist['source']} · 99999999 → {r_none}")

    # ③ ПЕРЕНОС ОДНОЙ СТАРОЙ ЗАПИСКИ С АДРЕСАТАМИ
    row = conn.execute("SELECT m.id FROM messages m WHERE m.timestamp < datetime('now','-7 days') AND EXISTS "
                       "(SELECT 1 FROM message_addressee a WHERE a.message_id=m.id) ORDER BY m.id DESC LIMIT 1").fetchone()
    mid = row[0]
    addressees_before = conn.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?", (mid,)).fetchone()[0]
    move_to_archive(conn, mid)
    r_arc = mezo_refs.resolve(conn, mid)
    src_view = conn.execute("SELECT source FROM messages_all WHERE id=?", (mid,)).fetchone()
    addressees_after = conn.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?", (mid,)).fetchone()[0]
    ok &= case("③ унесённая записка: функция → 'archive', вид → 'archive', адресаты на месте",
               r_arc is not None and r_arc["source"] == "archive" and src_view and src_view[0] == "archive"
               and addressees_after == addressees_before > 0,
               f"#{mid}: функция → {r_arc and r_arc['source']} · вид → {src_view and src_view[0]} · адресатов {addressees_before}→{addressees_after}",
               differ=True)

    # ④ ОБРАТНЫЙ ВСТРЕЧНЫЙ — несуществующий номер и после переноса не находится
    ids = mezo_refs.existing_ids(conn, [mid, 99_999_999, live_id])
    ok &= case("④ ОБРАТНЫЙ встречный: несуществующий номер не находится и после переноса",
               mezo_refs.resolve(conn, 99_999_999) is None and 99_999_999 not in ids and live_id in ids,
               "иначе «разрешается в архив» незаметно станет «разрешается всё» (COORD, записка #4855 Ⓑ)", differ=True)

    # ⑤ ПЕРВЫЙ ЧИТАТЕЛЬ — write-message.py из копии, на копии базы
    # ⚠️ Копия скриптов лежит ВНЕ контейнера — mezo_paths не найдёт маркер .mezosync/mezosync.db
    #    вверх по дереву и откажет. Контейнер называем средой (та же форма, что у других приёмок
    #    на копиях: MEZO_CONTAINER); база — явным --db на копию, живая не тронута.
    env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)))
    out5, code5 = run_tool(scripts_copy / "write-message.py", "--db", str(db), "--role", "PROTO",
                         "--body", "проба приёмки архива ленты: ack на унесённую записку", "--ack", str(mid),
                         "--reply-to", str(mid), "--resolves", "--to", "PROTO", env=env)
    resolved_arc = conn.execute("SELECT resolved FROM messages_archive WHERE id=?", (mid,)).fetchone()
    ok &= case("⑤ первый читатель: --ack на унесённую не отвечает «такой ноты нет»; --resolves ставит resolved В АРХИВЕ",
               code5 == 0 and "такой ноты нет" not in out5 and resolved_arc is not None and resolved_arc[0] == 1,
               f"код {code5}; «такой ноты нет» в выводе: {'такой ноты нет' in out5}; resolved в архиве: {resolved_arc and resolved_arc[0]}",
               differ=True)

    # ⑥ ГРАНИЦА ВНЕШНЕГО КЛЮЧА — названа, не спрятана
    via_messages = conn.execute("SELECT COUNT(*) FROM message_addressee a JOIN messages m ON m.id=a.message_id WHERE a.message_id=?", (mid,)).fetchone()[0]
    via_view = conn.execute("SELECT COUNT(*) FROM message_addressee a JOIN messages_all m ON m.id=a.message_id WHERE a.message_id=?", (mid,)).fetchone()[0]
    ok &= case("⑥ граница: адресаты унесённой через JOIN messages теряются, через JOIN messages_all — нет",
               via_messages == 0 and via_view == addressees_before,
               f"JOIN messages → {via_messages} · JOIN messages_all → {via_view} ⇒ читатели адресатов обязаны идти через вид (условие для инструмента переноса)",
               differ=True)
    conn.close()

    print()
    print(f"{'✅ АРХИВ ЛЕНТЫ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
