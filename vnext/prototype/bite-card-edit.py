#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: правка заголовка/набора карточки со следом (карточка #452).

Предмет — подкоманда edit в инструменте карточек: заголовок и набор УЖЕ заведённой
карточки правятся, правка оставляет СЛЕД-событие с ПРЕЖНИМ значением и именем
правившей роли. Всё на СТЕНДЕ из живой схемы; живая база не открывается.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ:
  ①  retitle своей ......... заголовок сменён · событие retitle несёт ПРЕЖНЕЕ имя
                             ДОСЛОВНО (читаем запросом, не верим печати)
  ②  retrack ............... набор сменён, отбор по пулу находит · событие с прежним
  ③  чужая БЕЗ --foreign ... ОТКАЗ, заголовок цел; с ВЕРНЫМ --foreign — проходит;
                             с НЕВЕРНЫМ — отказ
  ④  пустое --title ........ ОТКАЗ, заголовок цел (встречный ③ критерия)
  ⑤  edit без полей ........ ОТКАЗ «скажи, ЧТО правишь» — не тихая запись
  Р1 след ослеплён ......... копия пишет событие БЕЗ прежнего имени — случай ①
                             на ней падает, живой держит

Зовут так:
    python <КОНТУР>/vnext-tools/bite-card-edit.py
⚠️ при живом объявлении о правке backlog.py зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

import mezo_stand

# ═══ Класс карточки #454 (TAXO, второй случай — записка #4367 §③ про ЭТОТ файл):
# испытуемый механизм через ВЫБОР КОПИИ, не жёстко из живого. MEZO_SCRIPTS_ROOT
# действует; MEZO_FORBID_LIVE=1 без подмены — отказ «НЕ ЗАПУСТИЛАСЬ» до стенда.
# ⚖️ ГРАНИЦА: испытуемый — backlog.py; стенд и схема живой базы (mode=ro) — опыт.
BACKLOG = mezo_target.script("backlog.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

ТАБЛИЦЫ = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status")


def чистая_база(путь: pathlib.Path) -> None:
    живая = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    ддл = [r[0] for r in живая.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name IN "
        f"({','.join('?' * len(ТАБЛИЦЫ))})", ТАБЛИЦЫ)]
    живая.close()
    if len(ддл) != len(ТАБЛИЦЫ):
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: {len(ддл)} таблиц из {len(ТАБЛИЦЫ)}")
    con = sqlite3.connect(str(путь))
    for s in ддл:
        con.execute(s)
    con.commit()
    con.close()


def зов(инструмент: pathlib.Path, *args: str, окружение=None) -> tuple[int, str]:
    env = dict(os.environ)
    if окружение:
        env.update(окружение)
    p = subprocess.run([sys.executable, str(инструмент), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ослабить(живой, каталог, якорь, замена):
    текст = живой.read_bytes().decode("utf-8")
    if текст.count(якорь) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь найден {текст.count(якорь)} раз")
    копия = каталог / живой.name
    копия.write_bytes(текст.replace(якорь, замена).encode("utf-8"))
    return копия


def main() -> int:
    d = mezo_stand.new("card-edit-")
    db = d / "stand.db"
    чистая_база(db)
    провалы: list[str] = []
    судов = 0

    def суд(имя, условие, след=""):
        nonlocal судов
        судов += 1
        print(f"{'✅' if условие else '🔴'} {имя}")
        if not условие:
            провалы.append(имя)
            if след:
                print(f"   след: {след[:400]}")

    def поле(bid, что):
        con = sqlite3.connect(str(db))
        v = con.execute(f"SELECT {что} FROM backlog WHERE id=?", (bid,)).fetchone()[0]
        con.close()
        return v

    def события(bid, тип):
        con = sqlite3.connect(str(db))
        r = [x[0] for x in con.execute(
            "SELECT body_md FROM backlog_events WHERE backlog_id=? AND event_type=?",
            (bid, тип))]
        con.close()
        return r

    rc, _ = зов(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                "--title", "старое имя пробы", "--body", "т", "--done-when", "к")
    if rc != 0:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка не завелась")
    con = sqlite3.connect(str(db))
    к1 = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
    con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
                "('TRACK-ZZED','пул пробы','active')")
    con.commit()
    con.close()

    # ── ① retitle своей: имя сменено, ПРЕЖНЕЕ дословно в событии ────────────────
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB1",
                  "--title", "новое имя пробы", "--note", "примета не различала")
    следы1 = события(к1, "retitle")
    суд("① retitle: имя сменено, ПРЕЖНЕЕ дословно в событии (читано запросом)",
        rc == 0 and поле(к1, "title") == "новое имя пробы" and len(следы1) == 1
        and "«старое имя пробы»" in следы1[0] and "примета не различала" in следы1[0], out)

    # ── ② retrack: набор сменён, прежний в событии ─────────────────────────────
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB1",
                  "--track", "TRACK-ZZED")
    следы2 = события(к1, "retrack")
    суд("② retrack: набор сменён, прежний «—» в событии",
        rc == 0 and поле(к1, "parent_track") == "TRACK-ZZED" and len(следы2) == 1
        and "«—»" in следы2[0] and "TRACK-ZZED" in следы2[0], out)

    # ── ③ чужая: без имени владельца отказ · с верным проходит · с неверным отказ ─
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB2",
                  "--title", "угнанное имя")
    суд("③ чужая БЕЗ --foreign: ОТКАЗ, имя цело",
        rc != 0 and поле(к1, "title") == "новое имя пробы", out)
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB2",
                  "--title", "правка второй руки", "--foreign", "STUB1")
    суд("③-бис чужая с ВЕРНЫМ --foreign: проходит, след несёт имя правившей",
        rc == 0 and поле(к1, "title") == "правка второй руки", out)
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB2",
                  "--title", "х", "--foreign", "STUB9")
    суд("③-тер чужая с НЕВЕРНЫМ --foreign: отказ («не совпало с базой»)",
        rc != 0 and "не совпало" in out, out)

    # ── ④ пустое имя: отказ, встречный ③ критерия ──────────────────────────────
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB1",
                  "--title", "   ")
    суд("④ пустое имя: ОТКАЗ («невидима вернее, чем с неверным»), имя цело",
        rc != 0 and "невидима" in out and поле(к1, "title") == "правка второй руки", out)

    # ── ⑤ edit без полей: отказ, не тихая запись ───────────────────────────────
    rc, out = зов(BACKLOG, "--db", str(db), "edit", str(к1), "--actor", "STUB1")
    суд("⑤ edit без полей: ОТКАЗ «скажи, ЧТО правишь»",
        rc != 0 and "ЧТО правишь" in out, out)

    # ── Р1 обратный ход: след ослеплён — прежнее имя пропадает из события ──────
    к_р1 = ослабить(BACKLOG, d,
                    'f"ПРЕЖНЕЕ имя: «{old_title}» → новое: «{a.title.strip()}»"',
                    'f"имя обновлено"')
    rc, out = зов(к_р1, "--db", str(db), "edit", str(к1), "--actor", "STUB1",
                  "--title", "имя после ослепления",
                  окружение={"PYTHONPATH": str(BACKLOG.parent)})
    следы_р1 = события(к1, "retitle")
    # Событий retitle к этому суду ТРИ: случай ①, случай ③-бис и ход слепой копии.
    # Судится ПОСЛЕДНИЙ: слепая копия обязана оставить след без прежнего имени.
    суд("Р1 след ослеплён: копия пишет событие БЕЗ прежнего имени — случай ① пал бы",
        rc == 0 and len(следы_р1) == 3 and следы_р1[-1] == "имя обновлено"
        and "правка второй руки" not in следы_р1[-1],
        " | ".join(следы_р1))

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — правка со следом, ворота чужого и пустого "
          f"держат, обратный ход роняет своё")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
