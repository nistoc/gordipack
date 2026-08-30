#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: адресат записки стал ПОЛЕМ (миграция + ручки --to/--cc в живом write-message).

Испытывается ЖИВОЙ скрипт на КОПИИ живой базы. Копия проверяет копию — за эту разницу
контур платил вчера: «сдано у автора» не значит «доступно потребителю».

Свойства (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① имя из --to ЧИТАЕТСЯ ЗАПРОСОМ         контроль: механизм вообще пишет
  ② --cc кладёт имя с ДРУГИМ видом         РАЗЛИЧАЮЩИЙ: обращение ≠ копия
  ③ несколько имён через запятую            РАЗЛИЧАЮЩИЙ: разбор списка, а не одного
  ④ записка БЕЗ адресата не ломается        РАЗЛИЧАЮЩИЙ: строк не появляется
  ⑤ метка происхождения = 'field' и при одном --cc  РАЗЛИЧАЮЩИЙ
  ⑥ СТАРЫЕ записки не тронуты               РАЗЛИЧАЮЩИЙ: счёт до границы совпадает
  ⑦ номер записки — из СТРОКИ ПОДТВЕРЖДЕНИЯ  РАЗЛИЧАЮЩИЙ: часы сна адресата, напечатанные
     выше подтверждения, номер не подменяют (карточка #359)
  ⑧ происхождение — 'field', НЕ 'backfill': объявленное не выдаёт себя за разобранное

⛔ Живой базы не касается: работает на КОПИИ во временном каталоге.
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_paths  # пути машины выводятся, не впечатаны (#153)
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = str(mezo_target.scripts_root())
LIVE = str(mezo_paths.live_db())
WRITE = os.path.join(SCRIPTS, "write-message.py")
MIGRATION = os.path.join(SCRIPTS, "migrations", "20260808-message-addressee.py")

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def prepare():
    """Копия живой базы + миграция на ней. Инструмент ИЩЕТСЯ, а не предполагается."""
    for p in (WRITE, MIGRATION, LIVE):
        if not os.path.exists(p):
            raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: не найден {p} — приёмке нечего испытывать.")
    tmp = mezo_stand.new("bite-addressee-")
    db = os.path.join(tmp, "copy.db")
    shutil.copy(LIVE, db)
    r = subprocess.run([sys.executable, MIGRATION, "--db", db],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: миграция упала на копии\n{r.stdout}{r.stderr}")
    return db


def write(db, body, extra=()):
    r = subprocess.run([sys.executable, WRITE, "--db", db, "--role", "PROTO",
                        "--body", body, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "") + (r.stderr or "")
    # ═══ Карточка #359: номер — из СТРОКИ ПОДТВЕРЖДЕНИЯ «OK #NNNN», не «первое число
    # вывода». Прежний разбор брал первый числовой знак где угодно — а предупреждение
    # «адресат не подавал признаков жизни — N ч назад» печатается ВЫШЕ подтверждения
    # (намеренно: подтверждение держит место третьей строки с конца), и утром 29.08
    # четыре случая читали ЧАСЫ СНА адресата как номер записки — «в базе []» при
    # исправном продукте. Разбор по удобному признаку вместо нужного — тот же класс,
    # каким в тот же день промахнулся @CORE («голоса нет» из отбора по слову).
    m = re.search(r"^OK #(\d+)\b", out, re.M)
    mid = int(m.group(1)) if m else None
    return mid, out, r.returncode


def rows(db, mid):
    con = sqlite3.connect(db)
    got = con.execute("SELECT role, kind, linked_by FROM message_addressee "
                      "WHERE message_id=? ORDER BY kind, role", (mid,)).fetchall()
    stamp = con.execute("SELECT addressed_by FROM messages WHERE id=?", (mid,)).fetchone()
    con.close()
    return got, (stamp[0] if stamp else None)


def main() -> int:
    db = prepare()
    ok = True

    con = sqlite3.connect(db)
    border = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    before = con.execute("SELECT COUNT(*) FROM messages WHERE id <= ?", (border,)).fetchone()[0]
    # 🪤 СЧИТАЕМ ПРИРОСТ, А НЕ АБСОЛЮТ. Первая редакция требовала «адресатов у записок
    # до границы — НОЛЬ» и покраснела на ИСПРАВНОМ механизме: за минуту до прогона я
    # записал в живую базу настоящую записку с адресатами, она попала в копию и, будучи
    # свежее границы по времени, оказалась «до границы» по номеру.
    # ⇒ Свойство было сформулировано как утверждение о МИРЕ («адресатов быть не должно»),
    # а проверять надо утверждение о ДЕЙСТВИИ: приёмка не дорисовала чужого.
    addr_before = con.execute("SELECT COUNT(*) FROM message_addressee").fetchone()[0]
    con.close()

    # ① обращение именем
    mid, out, code = write(db, "проверка обращения", ["--to", "CORE"])
    got, stamp = rows(db, mid) if mid else ([], None)
    ok &= case("① имя из --to ЧИТАЕТСЯ ЗАПРОСОМ, а не только проставляет галочку",
               got == [("CORE", "to", "field")],
               f"код {code} · в базе {got} — прежняя редакция принимала имя и выбрасывала его")

    # ② копия — другой вид
    mid2, _, _ = write(db, "проверка копии", ["--cc", "STUD"])
    got2, stamp2 = rows(db, mid2) if mid2 else ([], None)
    ok &= case("② --cc кладёт имя с ВИДОМ «копия», отличным от обращения",
               got2 == [("STUD", "cc", "field")],
               f"в базе {got2} — различие обращения и копии и есть весь смысл затеи",
               differ=True)

    # ③ список
    mid3, _, _ = write(db, "список", ["--to", "CORE, STUD", "--cc", "@taxo,ING"])
    got3, _ = rows(db, mid3) if mid3 else ([], None)
    ok &= case("③ список имён разобран, регистр и «собака» нормализованы",
               got3 == [("ING", "cc", "field"), ("TAXO", "cc", "field"),
                        ("CORE", "to", "field"), ("STUD", "to", "field")],
               f"подано «CORE, STUD» и «@taxo,ING» → в базе {[g[0] for g in got3]}",
               differ=True)

    # ④ без адресата
    mid4, _, code4 = write(db, "записка без адресата вовсе")
    got4, stamp4 = rows(db, mid4) if mid4 else ([], None)
    ok &= case("④ записка БЕЗ адресата не ломается и строк не создаёт",
               code4 == 0 and got4 == [] and stamp4 in (None, "unset"),
               f"код {code4} · строк адресатов {len(got4)} · штамп {stamp4!r}",
               differ=True)

    # ⑤ штамп происхождения при ОДНОМ --cc
    ok &= case("⑤ штамп «адресат объявлен» ставится и когда назван только --cc",
               stamp2 == "field",
               f"штамп {stamp2!r} — прежняя строка смотрела только на --to, и записка "
               "с одними получателями копии числилась бы «адресат не объявлен»",
               differ=True)

    # ⑥ старые не тронуты
    con = sqlite3.connect(db)
    after = con.execute("SELECT COUNT(*) FROM messages WHERE id <= ?", (border,)).fetchone()[0]
    addr_after = con.execute("SELECT COUNT(*) FROM message_addressee").fetchone()[0]
    mine = con.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id > ?",
                       (border,)).fetchone()[0]
    con.close()
    grew = addr_after - addr_before
    ok &= case("⑥ СТАРЫЕ записки не переписаны, прирост адресатов = ровно свой",
               before == after and grew == mine,
               f"до границы #{border}: записок было {before}, стало {after} ✅ · "
               f"строк адресатов было {addr_before}, стало {addr_after} — прирост {grew}, "
               f"и все {mine} приписаны запискам, которые приёмка написала САМА "
               f"(обратное заполнение чужого — ОТДЕЛЬНЫЙ ход, здесь его быть не должно)",
               differ=True)

    # ⑦ КАРТОЧКА #359: разбор номера судится ПОДСАЖЕННЫМ ключом — спящим адресатом.
    # В копию кладётся живая роль с единственным следом 500-часовой давности: письмо
    # печатает «N ч назад» ВЫШЕ подтверждения, и прежний разбор взял бы часы за номер.
    con = sqlite3.connect(db)
    con.execute("INSERT INTO roles (role, lifecycle) VALUES ('ZZSONYA', 'alive')")
    con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority) "
                "VALUES ('ZZSONYA', datetime('now','-500 hours'), "
                "'старый след спящей роли — подсадка приёмки', '[]', 'normal')")
    con.commit()
    con.close()
    mid7, out7, code7 = write(db, "обращение к спящему адресату", ["--to", "ZZSONYA"])
    got7, _ = rows(db, mid7) if mid7 else ([], None)
    # ═══ Карточка #440 (STUD, второй укус приёмки #359): пояснение собирается ПО ФАКТАМ.
    # Прежняя строка утверждала «предупреждение в выводе есть» ПРИ ЛЮБОМ исходе — и при
    # падении из-за его отсутствия объясняла мир, в котором отказа нет: читающий шёл
    # чинить разбор номера, а чинить надо было предпосылку опыта.
    предупр7 = "ч назад" in out7
    ok &= case("⑦ номер записки взят из ПОДТВЕРЖДЕНИЯ — часы сна адресата его не подменяют",
               code7 == 0 and предупр7 and got7 == [("ZZSONYA", "to", "field")],
               f"запись rc={code7} (ждём 0) · предупреждение о спящем («ч назад» выше "
               f"подтверждения): {'НАПЕЧАТАНО' if предупр7 else 'ОТСУТСТВУЕТ — предпосылка опыта (старый след спящего) не состоялась'} · "
               f"разобран номер {mid7} · в базе {got7}", differ=True)

    # ⑧ происхождение объявленного
    ok &= case("⑧ объявленное помечено 'field', а не 'backfill'",
               all(g[2] == "field" for g in got + got2 + got3),
               "догадка из прозы не должна выдавать себя за объявленное ручкой")

    print()
    print(f"{'✅ АДРЕСАТ ПОЛЕМ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()} на копии живой базы")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
