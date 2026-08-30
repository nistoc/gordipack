#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: очередь приёмок одной командой (карточка #422).

Предмет — подкоманда queue: очередь in_review по всем ролям, час замера
МЕХАНИЗМОМ, «пусто» ≠ «не смотрел» (число просмотренных ролей), --since
помечает сданное после прошлого запроса. Всё на СТЕНДЕ из живой схемы.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (судов 6, красных жду 0):
  ①  две карточки in_review → обе в выводе, «итого 2», номера = запросу к стенду
  ②  сдана третья МЕЖДУ вызовами → второй вызов «итого 3» (встречный ② критерия)
  ③  час замера: строка «замер YYYY-MM-DD HH:MM:SS UTC» есть и лежит в ±120 сек
     от настоящего UTC — печатает механизм, не роль
  ④  пустая очередь → «ПУСТА» И «ролей просмотрено 2» (в стенде две alive-роли)
  ⑤  --since <час между сдачами> → поздняя помечена 🆕, ранняя — нет
  Р1 ветка пустоты ослеплена → ④ на копии: слова «ПУСТА» нет — «пусто»
     снова неотличимо от «не смотрел»

Зовут так:
    python <КОНТУР>/vnext-tools/bite-review-queue.py
⚠️ при живом объявлении о правке backlog.py зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

import mezo_stand

# Класс карточки #454: испытуемый через ВЫБОР КОПИИ, не жёстко из живого.
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
    d = mezo_stand.new("review-queue-")
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

    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('STUB1','alive','а')")
    con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('STUB2','alive','б')")
    con.commit()
    con.close()
    for роль, имя in [("STUB1", "первая на приёмке"), ("STUB2", "вторая на приёмке"),
                      ("STUB1", "ещё открытая")]:
        rc, _ = зов(BACKLOG, "--db", str(db), "add", "--role", роль,
                    "--title", имя, "--body", "т", "--done-when", "к")
        if rc != 0:
            raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка не завелась")
    con = sqlite3.connect(str(db))
    к1, к2, к3 = [r[0] for r in con.execute("SELECT id FROM backlog ORDER BY id")]
    con.close()
    for к in (к1, к2):
        rc, _ = зов(BACKLOG, "--db", str(db), "status", str(к), "in_review",
                    "--actor", "STUB1" if к == к1 else "STUB2", "--note", "на приёмку")
        if rc != 0:
            raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: перевод в in_review не прошёл")

    # ── ① очередь одной командой = запросу к стенду ────────────────────────────
    rc, out1 = зов(BACKLOG, "--db", str(db), "queue")
    номера1 = sorted(int(m) for m in re.findall(r"карточка #(\d+)", out1))
    суд("① две на приёмке: обе в выводе, «итого 2», номера = запросу",
        rc == 0 and номера1 == [к1, к2] and "итого 2" in out1, out1)

    # ── ③ час замера механизмом ────────────────────────────────────────────────
    м = re.search(r"замер (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC", out1)
    сдвиг = None
    if м:
        т = datetime.strptime(м.group(1), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc)
        сдвиг = abs((datetime.now(timezone.utc) - т).total_seconds())
    суд("③ час замера: строка «замер … UTC» есть и в ±120 сек от настоящего UTC",
        м is not None and сдвиг is not None and сдвиг < 120,
        f"сдвиг {сдвиг} сек" if сдвиг is not None else out1)

    # ── ② сдана третья МЕЖДУ вызовами → прибавка видна ─────────────────────────
    час1 = м.group(1) if м else ""
    # Пауза больше секунды: час замера и час сдачи различимы с точностью до секунды,
    # и без паузы оба ложатся в ОДНУ — первый прогон это показал (сдача не была
    # «позже» часа). Живая роль зовёт --since через минуты, не миллисекунды;
    # граница точности — секунда — названа в сдаче словами.
    time.sleep(1.2)
    rc, _ = зов(BACKLOG, "--db", str(db), "status", str(к3), "in_review",
                "--actor", "STUB1", "--note", "сдана между вызовами")
    rc2, out2 = зов(BACKLOG, "--db", str(db), "queue")
    суд("② сданная между вызовами появилась: «итого 3» (встречный ② критерия)",
        rc2 == 0 and "итого 3" in out2 and f"#{к3}" in out2, out2)

    # ── ⑤ --since: поздняя помечена, ранняя нет ────────────────────────────────
    rc5, out5 = зов(BACKLOG, "--db", str(db), "queue", "--since", час1)
    стр5 = {int(m.group(1)): m.group(0)[:4]
            for m in re.finditer(r"(?:🆕 )?карточка #(\d+)",
                                 out5)} if rc5 == 0 else {}
    поздняя = next((s for s in out5.splitlines() if f"#{к3}" in s), "")
    ранняя = next((s for s in out5.splitlines() if f"#{к1}" in s), "")
    суд("⑤ --since: сданная после часа помечена 🆕, сданная до — нет",
        rc5 == 0 and "🆕" in поздняя and "🆕" not in ранняя,
        f"поздняя: {поздняя!r} · ранняя: {ранняя!r}")

    # ── ④ пустая очередь ≠ «не смотрел» ────────────────────────────────────────
    db0 = d / "stand-empty.db"
    чистая_база(db0)
    con = sqlite3.connect(str(db0))
    con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('STUB1','alive','а')")
    con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('STUB2','alive','б')")
    con.commit()
    con.close()
    rc4, out4 = зов(BACKLOG, "--db", str(db0), "queue")
    суд("④ пустая очередь: «ПУСТА» И «ролей просмотрено 2» — не «не смотрел»",
        rc4 == 0 and "ПУСТА" in out4 and "ролей просмотрено 2" in out4, out4)

    # ── Р1 обратный ход: ветка пустоты ослеплена ───────────────────────────────
    к_р1 = ослабить(BACKLOG, d,
                    'print("   очередь приёмок ПУСТА: карточек на приёмке (in_review) — 0")',
                    "pass  # ослаблено приёмкой")
    rc_r1, out_r1 = зов(к_р1, "--db", str(db0), "queue",
                        окружение={"PYTHONPATH": str(BACKLOG.parent)})
    суд("Р1 ветка пустоты ослеплена: слова «ПУСТА» нет — ④ пал бы, «пусто» снова "
        "неотличимо от «не смотрел»",
        rc_r1 == 0 and "ПУСТА" not in out_r1, out_r1)

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — очередь одной командой, час механизмом, "
          f"пусто ≠ не смотрел")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
