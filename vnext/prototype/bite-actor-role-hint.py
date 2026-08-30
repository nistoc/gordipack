#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: подсказка при чужом имени довода --role/--actor (карточка #409).

Предмет — путь ③: backlog.py при --role в командах исполнителя и lease.py при
--actor отказывают С ПОДСКАЗКОЙ верного имени, а не голым «unrecognized
arguments». Прежние верные вызовы обоих инструментов не тронуты.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (судов 6, красных жду 0):
  ①  backlog claim --role ..... ОТКАЗ, подсказка несёт «--actor» и «карточка #409»
  ②  lease take --actor ....... ОТКАЗ, подсказка несёт «--role» и «карточка #409»
  ③  встречный: backlog claim --actor на стенде — работает (rc 0)
  ④  встречный: lease take --role на стендовой базе — работает (rc 0)
  ⑤  встречный: backlog add --role на стенде — работает (там --role ЗАКОНЕН:
     владелец карточки; подсказка на add не распространяется)
  Р1 подсказка backlog ослеплена → ① на копии: отказ есть (argparse сам
     требует --actor и потому печатает это слово), но ПОДСКАЗКИ со ссылкой
     «карточка #409» нет — роль снова гадает. Судится исчезновение подсказки,
     не слова «--actor»: голый argparse-отказ его содержит (замер первого прогона)

Зовут так:
    python <КОНТУР>/vnext-tools/bite-actor-role-hint.py
⚠️ при живом объявлении о правке этих инструментов зови с MEZO_ROLE=<твоя роль>.
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

BACKLOG = mezo_target.script("backlog.py")
LEASE = mezo_target.script("lease.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

ТАБЛИЦЫ = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status", "tool_leases", "audit_log")


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
    d = mezo_stand.new("actor-role-")
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

    rc, _ = зов(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                "--title", "проба", "--body", "т", "--done-when", "к")
    if rc != 0:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка не завелась")
    con = sqlite3.connect(str(db))
    к1 = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
    con.close()

    # ── ① чужое имя у карточек: отказ с подсказкой ─────────────────────────────
    rc1, out1 = зов(BACKLOG, "--db", str(db), "claim", str(к1), "--role", "STUB1")
    суд("① backlog claim --role: ОТКАЗ, подсказка несёт --actor и карточку #409",
        rc1 != 0 and "--actor" in out1 and "карточка #409" in out1, out1)

    # ── ② чужое имя у объявлений: отказ с подсказкой ───────────────────────────
    rc2, out2 = зов(LEASE, "--db", str(db), "take", "--actor", "STUB1",
                    "--tools", "x.py", "--reason", "проба")
    суд("② lease take --actor: ОТКАЗ, подсказка несёт --role и карточку #409",
        rc2 != 0 and "--role" in out2 and "карточка #409" in out2, out2)

    # ── ③④⑤ встречные: прежние верные вызовы работают ─────────────────────────
    rc3, out3 = зов(BACKLOG, "--db", str(db), "claim", str(к1), "--actor", "STUB1",
                    "--note", "проба взятия")
    суд("③ backlog claim --actor: работает как прежде", rc3 == 0, out3)

    rc4, out4 = зов(LEASE, "--db", str(db), "take", "--role", "STUB1",
                    "--tools", "x.py", "--reason", "проба", "--minutes", "5")
    суд("④ lease take --role: работает как прежде", rc4 == 0, out4)

    rc5, out5 = зов(BACKLOG, "--db", str(db), "add", "--role", "STUB2",
                    "--title", "проба-два", "--body", "т", "--done-when", "к")
    суд("⑤ backlog add --role: законный --role (владелец) не тронут", rc5 == 0, out5)

    # ── Р1 обратный ход: подсказка ослеплена ───────────────────────────────────
    к_р1 = ослабить(BACKLOG, d,
                    'if _подкоманда in _КОМАНДЫ_ACTOR and "--role" in sys.argv:',
                    "if False:")
    rc_r1, out_r1 = зов(к_р1, "--db", str(db), "claim", str(к1), "--role", "STUB1",
                        окружение={"PYTHONPATH": str(BACKLOG.parent)})
    суд("Р1 подсказка ослеплена: отказ голый, ссылки на карточку #409 нет — ① пал бы",
        rc_r1 != 0 and "карточка #409" not in out_r1, out_r1)

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — чужое имя получает подсказку, "
          f"верные вызовы не тронуты")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
