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
    python C:/guts/.atlas/vnext-tools/bite-messages-archive.py --porcha no-archive

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
ШАГ = SCRIPTS / "migrations" / "20260905-messages-archive.py"
ПИСАТЕЛЬ = SCRIPTS / "write-message.py"

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def копия(stand: pathlib.Path) -> pathlib.Path:
    db = stand / "mezosync.db"
    src = sqlite3.connect(f"file:{LIVE.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close(); dst.close()
    return db


def прогон(script: pathlib.Path, *args, env=None):
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                       encoding="utf-8", timeout=300, env=env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def отпечаток_вида(conn) -> str:
    h = hashlib.sha256()
    for row in conn.execute("SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, source "
                            "FROM messages_all ORDER BY source, id"):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()[:16]


def перенести(conn, mid: int):
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
    for f in (ШАГ, ПИСАТЕЛЬ, SCRIPTS / "mezo_refs.py"):
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
    db = копия(stand)
    conn0 = sqlite3.connect(str(db))
    до = отпечаток_вида(conn0) if conn0.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='messages_all'").fetchone() else None
    conn0.close()

    # ⓪ КОНТРОЛЬ
    out0, code0 = прогон(scripts_copy / "migrations" / "20260905-messages-archive.py", "--db", str(db))
    conn = sqlite3.connect(str(db))
    таблицы = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    vsql = (conn.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='messages_all'").fetchone() or [""])[0]
    журнал = conn.execute("SELECT 1 FROM schema_migrations WHERE version='20260905-messages-archive'").fetchone()
    после = отпечаток_вида(conn)
    ok &= case("⓪ контроль: шаг схемы на копии — таблица, вид с 'archive', журнал; вид отдаёт то же при пустом архиве",
               code0 == 0 and ("ВРЕЗАНО" in out0 or "уже сведено" in out0) and "messages_archive" in таблицы
               and "'archive'" in vsql and журнал is not None and (до is None or до == после),
               f"код {code0}; отпечаток вида до {до} · после {после}")

    # ① ПОВТОР
    out1, code1 = прогон(scripts_copy / "migrations" / "20260905-messages-archive.py", "--db", str(db))
    ok &= case("① повтор шага — «уже сведено», отпечаток вида не меняется",
               code1 == 0 and "уже сведено" in out1 and отпечаток_вида(conn) == после,
               "шаг обязан быть идемпотентным: второй прогон не имеет права трогать базу", differ=True)

    # ② ФУНКЦИЯ — три источника
    живая = conn.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    импорт = conn.execute("SELECT MIN(id) FROM messages_history").fetchone()[0]
    r_live = mezo_refs.resolve(conn, живая)
    r_hist = mezo_refs.resolve(conn, импорт) if импорт else {"source": "history"}
    r_none = mezo_refs.resolve(conn, 99_999_999)
    ok &= case("② функция: живая → 'live' · ретро-импорт → 'history' · чужой номер → None",
               r_live and r_live["source"] == "live" and r_hist and r_hist["source"] == "history" and r_none is None,
               f"live #{живая} → {r_live and r_live['source']} · history #{импорт} → {r_hist and r_hist['source']} · 99999999 → {r_none}")

    # ③ ПЕРЕНОС ОДНОЙ СТАРОЙ ЗАПИСКИ С АДРЕСАТАМИ
    row = conn.execute("SELECT m.id FROM messages m WHERE m.timestamp < datetime('now','-7 days') AND EXISTS "
                       "(SELECT 1 FROM message_addressee a WHERE a.message_id=m.id) ORDER BY m.id DESC LIMIT 1").fetchone()
    mid = row[0]
    адресатов_до = conn.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?", (mid,)).fetchone()[0]
    перенести(conn, mid)
    r_arc = mezo_refs.resolve(conn, mid)
    src_view = conn.execute("SELECT source FROM messages_all WHERE id=?", (mid,)).fetchone()
    адресатов_после = conn.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?", (mid,)).fetchone()[0]
    ok &= case("③ унесённая записка: функция → 'archive', вид → 'archive', адресаты на месте",
               r_arc is not None and r_arc["source"] == "archive" and src_view and src_view[0] == "archive"
               and адресатов_после == адресатов_до > 0,
               f"#{mid}: функция → {r_arc and r_arc['source']} · вид → {src_view and src_view[0]} · адресатов {адресатов_до}→{адресатов_после}",
               differ=True)

    # ④ ОБРАТНЫЙ ВСТРЕЧНЫЙ — несуществующий номер и после переноса не находится
    ids = mezo_refs.existing_ids(conn, [mid, 99_999_999, живая])
    ok &= case("④ ОБРАТНЫЙ встречный: несуществующий номер не находится и после переноса",
               mezo_refs.resolve(conn, 99_999_999) is None and 99_999_999 not in ids and живая in ids,
               "иначе «разрешается в архив» незаметно станет «разрешается всё» (COORD, записка #4855 Ⓑ)", differ=True)

    # ⑤ ПЕРВЫЙ ЧИТАТЕЛЬ — write-message.py из копии, на копии базы
    # ⚠️ Копия скриптов лежит ВНЕ контейнера — mezo_paths не найдёт маркер .mezosync/mezosync.db
    #    вверх по дереву и откажет. Контейнер называем средой (та же форма, что у других приёмок
    #    на копиях: MEZO_CONTAINER); база — явным --db на копию, живая не тронута.
    env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)))
    out5, code5 = прогон(scripts_copy / "write-message.py", "--db", str(db), "--role", "PROTO",
                         "--body", "проба приёмки архива ленты: ack на унесённую записку", "--ack", str(mid),
                         "--reply-to", str(mid), "--resolves", "--to", "PROTO", env=env)
    resolved_arc = conn.execute("SELECT resolved FROM messages_archive WHERE id=?", (mid,)).fetchone()
    ok &= case("⑤ первый читатель: --ack на унесённую не отвечает «такой ноты нет»; --resolves ставит resolved В АРХИВЕ",
               code5 == 0 and "такой ноты нет" not in out5 and resolved_arc is not None and resolved_arc[0] == 1,
               f"код {code5}; «такой ноты нет» в выводе: {'такой ноты нет' in out5}; resolved в архиве: {resolved_arc and resolved_arc[0]}",
               differ=True)

    # ⑥ ГРАНИЦА ВНЕШНЕГО КЛЮЧА — названа, не спрятана
    через_messages = conn.execute("SELECT COUNT(*) FROM message_addressee a JOIN messages m ON m.id=a.message_id WHERE a.message_id=?", (mid,)).fetchone()[0]
    через_вид = conn.execute("SELECT COUNT(*) FROM message_addressee a JOIN messages_all m ON m.id=a.message_id WHERE a.message_id=?", (mid,)).fetchone()[0]
    ok &= case("⑥ граница: адресаты унесённой через JOIN messages теряются, через JOIN messages_all — нет",
               через_messages == 0 and через_вид == адресатов_до,
               f"JOIN messages → {через_messages} · JOIN messages_all → {через_вид} ⇒ читатели адресатов обязаны идти через вид (условие для инструмента переноса)",
               differ=True)
    conn.close()

    print()
    print(f"{'✅ АРХИВ ЛЕНТЫ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
