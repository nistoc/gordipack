#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: форма меток карточки проверяется на входе (карточка #447).

Предмет — разбор --tags в подкоманде add инструмента карточек: единственная форма
«a,b,c»; JSON и мусор отклоняются СО СЛОВОМ (не оборачиваются второй раз); пустые
метки отклоняются; пробел у запятой обрезается с предупреждением. Всё на СТЕНДЕ
из живой схемы; живая база не открывается на запись.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (судов 8, красных жду 0):
  ①  'a,b' ............. rc 0 · в базе ["a","b"] · предупреждения НЕТ (встречный ①)
  ②  '["a", "b"]' ...... ОТКАЗ со словом «похож на JSON» · карточка НЕ заведена
  ③  '[[[' ............. ОТКАЗ со словом · карточка НЕ заведена (мусор)
  ④  'a, b' ............ rc 0 · в базе ["a","b"] · СЛОВО «пробелы… обрезаны»
  ⑤  'один тег' ........ rc 0 · в базе ["один тег"] (пробел ВНУТРИ метки законен)
  ⑥  'a,,b' ............ ОТКАЗ со словом «пустая метка»
  ⑦  без --tags ........ rc 0 · в базе [] — отсутствие меток законно
  Р1 обратный ход ...... проверка JSON ослеплена → случай ② на копии ПАДАЕТ:
                         JSON снова принят и обёрнут второй раз — беда вернулась

Зовут так:
    python <КОНТУР>/vnext-tools/bite-card-tags.py
⚠️ при живом объявлении о правке backlog.py зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

import mezo_stand

SCRIPTS = mezo_paths.live_scripts()
BACKLOG = SCRIPTS / "backlog.py"

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
    d = mezo_stand.new("card-tags-")
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

    def добавить(теги, инструмент=BACKLOG, окружение=None):
        args = ["--db", str(db), "add", "--role", "STUB1", "--title", "проба меток",
                "--body", "т", "--done-when", "к"]
        if теги is not None:
            args += ["--tags", теги]
        return зов(инструмент, *args, окружение=окружение)

    def последние_метки():
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT tags FROM backlog ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        return json.loads(row[0]) if row else None

    def счёт():
        con = sqlite3.connect(str(db))
        n = con.execute("SELECT COUNT(*) FROM backlog").fetchone()[0]
        con.close()
        return n

    # ── ① обычные метки: как раньше, без слова ─────────────────────────────────
    rc, out = добавить("a,b")
    суд("① 'a,b': принято, в базе [\"a\",\"b\"], предупреждения нет",
        rc == 0 and последние_метки() == ["a", "b"] and "обрезаны" not in out, out)

    # ── ② JSON: отказ со словом, карточка НЕ заведена ──────────────────────────
    было = счёт()
    rc, out = добавить('["a", "b"]')
    суд("② JSON-форма: ОТКАЗ со словом «похож на JSON», карточка не заведена",
        rc != 0 and "похож на JSON" in out and "a,b,c" in out and счёт() == было, out)

    # ── ③ мусор '[[[': отказ со словом ─────────────────────────────────────────
    было = счёт()
    rc, out = добавить("[[[")
    суд("③ мусор '[[[': ОТКАЗ со словом, карточка не заведена",
        rc != 0 and "похож на JSON" in out and счёт() == было, out)

    # ── ④ пробел у запятой: принято, обрезано, СО СЛОВОМ ───────────────────────
    rc, out = добавить("a, b")
    суд("④ 'a, b': принято, пробел обрезан, слово «обрезаны» напечатано",
        rc == 0 and последние_метки() == ["a", "b"] and "обрезаны" in out, out)

    # ── ⑤ пробел ВНУТРИ метки законен ──────────────────────────────────────────
    rc, out = добавить("один тег")
    суд("⑤ 'один тег': принято одной меткой, слова нет",
        rc == 0 and последние_метки() == ["один тег"] and "обрезаны" not in out, out)

    # ── ⑥ пустая метка между запятыми: отказ со словом ─────────────────────────
    было = счёт()
    rc, out = добавить("a,,b")
    суд("⑥ 'a,,b': ОТКАЗ со словом «пустая метка», карточка не заведена",
        rc != 0 and "пустая метка" in out and счёт() == было, out)

    # ── ⑦ без --tags: законно, метки пустые ────────────────────────────────────
    rc, out = добавить(None)
    суд("⑦ без --tags: принято, в базе []",
        rc == 0 and последние_метки() == [], out)

    # ── Р1 обратный ход: проверка JSON ослеплена — порча возвращается ──────────
    к_р1 = ослабить(BACKLOG, d, 'if raw[0] in "[{":', "if False:")
    rc, out = добавить('["a", "b"]', инструмент=к_р1,
                       окружение={"PYTHONPATH": str(SCRIPTS)})
    метки_р1 = последние_метки()
    суд("Р1 проверка ослеплена: JSON снова принят и обёрнут — беда карточки #447 вернулась",
        rc == 0 and метки_р1 and метки_р1[0].startswith("["),
        f"rc={rc} метки={метки_р1}")

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — форма меток судится на входе, отказ говорит "
          f"словом, обратный ход возвращает порчу")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
