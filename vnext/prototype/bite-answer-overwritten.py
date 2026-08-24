#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА: проверка моста говорит, СКОЛЬКО РАЗ записан ответ (карточка #245).

🎯 КЛАСС. Имя файла ответа задано ТЕМОЙ вопроса ⇒ второй отвечающий физически пишет туда
же, куда первый, и его запись неотличима от правки. Живой случай 22.08: два ответа на один
вопрос легли под одним именем с разницей в три с половиной часа, второй затёр первый,
а проверка обе минуты говорила «отвечен» — и оба раза ПРАВДУ: она сверяет имена тем, имя
после перезаписи то же. Ни до, ни после ничего не покраснело.

⚖️ ЛЕЧИМ МОЛЧАНИЕ, А НЕ ДОПОЛНЕНИЕ: запрет перезаписи отказал бы в законной работе.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: ответ записан ОДИН раз — лишней строки нет, и видно, что смотрели
  ② ответ переписан → названы число записей и оба часа                     РАЗЛИЧАЮЩИЙ
  ③ часы в UTC, а не в зоне машины                                          РАЗЛИЧАЮЩИЙ
  ④ папка моста вне репозитория → «НЕ ЗНАЮ», а не «записан однажды»         РАЗЛИЧАЮЩИЙ
  ⑤ история не читается → та же честность, с причиной                       РАЗЛИЧАЮЩИЙ
  ⑥ ВСТРЕЧНЫЙ: вопрос СОСЕДА, лежащий в ЕГО репозитории, историю не получает РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: контур, сосед и репозиторий — во временном каталоге.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def git(корень, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="проба", GIT_AUTHOR_EMAIL="p@p",
               GIT_COMMITTER_NAME="проба", GIT_COMMITTER_EMAIL="p@p")
    if when:                    # час записи задаём явно: приёмка не должна зависеть от «сейчас»
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(["git", "-C", str(корень), *args], capture_output=True,
                          text=True, encoding="utf-8", timeout=120, env=env)


def стенд(tmp: pathlib.Path, с_репозиторием=True) -> tuple:
    """Наш контур + сосед со своей исходящей. → (guard-all, наша папка, папка соседа)."""
    live = mezo_paths.container_root(__file__) / ".mezosync"
    наш = tmp / "atlas"
    shutil.copytree(live / "scripts", наш / ".mezosync" / "scripts")
    shutil.copy(live / "mezosync.db", наш / ".mezosync" / "mezosync.db")
    архив = наш / "atlas.archs"
    наша_папка = архив / ".mezosync" / "bridges" / "atlas-neigh"
    наша_папка.mkdir(parents=True)

    сосед = tmp / "neigh"
    (сосед / ".mezosync").mkdir(parents=True)
    sqlite3.connect(сосед / ".mezosync" / "mezosync.db").close()
    их_папка = сосед / "neigh.archs" / ".mezosync" / "bridges" / "neigh-atlas"
    их_папка.mkdir(parents=True)

    con = sqlite3.connect(наш / ".mezosync" / "mezosync.db")
    con.execute("DELETE FROM cross_links")
    con.execute("INSERT INTO cross_links (source_group, target_group, target_db_path,"
                " description) VALUES ('atlas','neigh',?,'проба')",
                (str(сосед / ".mezosync" / "mezosync.db"),))
    con.commit()
    con.close()
    if с_репозиторием:
        git(архив, "init", "-q")
    return наш / ".mezosync" / "scripts" / "guard-all.py", наша_папка, их_папка


def записать(папка, имя, текст, when=None):
    (папка / имя).write_text(текст, encoding="utf-8")
    корень = папка.parents[2]
    if (корень / ".git").exists():
        git(корень, "add", "-A")
        git(корень, "commit", "-q", "-m", f"запись {имя}", when=when)


def run(guard) -> str:
    r = subprocess.run([sys.executable, str(guard), "--skip", "drift,память,ленты"],
                       capture_output=True, text=True, encoding="utf-8", timeout=600)
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    tmp = mezo_stand.new("bite-answer-over-")
    try:
        # ① КОНТРОЛЬ: один ответ — лишней строки нет. Без него краснота ниже ничего
        #    не значит: молчать можно и от того, что проверка не смотрит вовсе.
        guard, наша, их = стенд(tmp / "a")
        записать(их, "ask.atlas.тема.md", "вопрос", when="2026-08-20T10:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "ответ", when="2026-08-20T11:00:00+0000")
        out = run(guard)
        ok &= case("① контроль: ответ записан ОДИН раз — лишней строки нет",
                   "отвечен НАШИМ ответом" in out and "ПЕРЕПИСЫВАЛСЯ" not in out,
                   "«ничего не нашёл» и «ничего не искал» обязаны различаться: вопрос "
                   "при этом назван отвеченным")

        # ② ПЕРЕЗАПИСЬ — та самая молчаливая потеря.
        guard, наша, их = стенд(tmp / "b")
        записать(их, "ask.atlas.тема.md", "вопрос", when="2026-08-20T10:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "первый ответ", when="2026-08-20T11:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "второй ответ", when="2026-08-20T14:30:00+0000")
        out = run(guard)
        ok &= case("② ответ переписан — названы число записей и оба часа",
                   "ПЕРЕПИСЫВАЛСЯ" in out and "записей 2" in out
                   and "20.08 14:30" in out and "20.08 11:00" in out,
                   "иначе потеря чужого ответа происходит без отказа и без красного",
                   differ=True)

        # ③ ЧАСЫ В UTC. 🪤 Найдено на СВОЁМ выводе через минуту после первой печати:
        #    строка называла локальное время автора записи без зоны — ровно тот дефект,
        #    за который в этом же прогоне краснеет соседняя проверка.
        guard, наша, их = стенд(tmp / "c")
        записать(их, "ask.atlas.тема.md", "вопрос", when="2026-08-20T10:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "раз", when="2026-08-20T12:00:00+0500")
        записать(наша, "answer.neigh.тема.md", "два", when="2026-08-20T20:00:00-0700")
        out = run(guard)
        ok &= case("③ часы в UTC, а не в зоне записи",
                   "20.08 07:00 UTC" in out and "21.08 03:00 UTC" in out,
                   "записи сделаны в зонах +05:00 и −07:00; строка обязана называть "
                   "07:00 и 03:00 UTC, иначе она сама несёт дефект «время под UTC»",
                   differ=True)

        # ④ ВНЕ РЕПОЗИТОРИЯ — «не знаю» вместо «однажды». Сводить их значило бы
        #    объявить единственной запись, которой никто не считал.
        guard, наша, их = стенд(tmp / "d", с_репозиторием=False)
        записать(их, "ask.atlas.тема.md", "вопрос")
        записать(наша, "answer.neigh.тема.md", "ответ")
        out = run(guard)
        ok &= case("④ папка моста вне репозитория — сказано «НЕ ЗНАЮ»",
                   "НЕ ЗНАЮ" in out and "не «записан однажды»" in out,
                   "«не смог посчитать» и «посчитал: один» — разные факты; молчание "
                   "выдало бы второе за первое", differ=True)

        # ⑤ ИСТОРИЯ НЕ ЧИТАЕТСЯ: каталог .git есть, а репозиторий сломан.
        guard, наша, их = стенд(tmp / "e")
        записать(их, "ask.atlas.тема.md", "вопрос", when="2026-08-20T10:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "ответ", when="2026-08-20T11:00:00+0000")
        shutil.rmtree(наша.parents[2] / ".git" / "refs")
        (наша.parents[2] / ".git" / "HEAD").write_text("сломано", encoding="utf-8")
        out = run(guard)
        ok &= case("⑤ история не читается — та же честность, с причиной",
                   "НЕ ЗНАЮ" in out and "код" in out,
                   "неудачное чтение не имеет права выглядеть как удачное с ответом «один»",
                   differ=True)

        # ⑥ ВСТРЕЧНЫЙ: у СОСЕДА своя история, и мы в неё не ходим (no-scan-external-contours).
        #    Его вопрос переписан дважды — числа записей у него мы не называем.
        guard, наша, их = стенд(tmp / "f")
        git(их.parents[2], "init", "-q")
        записать(их, "ask.atlas.тема.md", "вопрос", when="2026-08-20T10:00:00+0000")
        записать(их, "ask.atlas.тема.md", "вопрос переписан", when="2026-08-20T15:00:00+0000")
        записать(наша, "answer.neigh.тема.md", "ответ", when="2026-08-20T16:00:00+0000")
        out = run(guard)
        ok &= case("⑥ ВСТРЕЧНЫЙ: история ЧУЖОГО репозитория не читается",
                   "ПЕРЕПИСЫВАЛСЯ" not in out and "отвечен НАШИМ ответом" in out,
                   "у соседа мы вправе прочесть файлы его исходящей папки, но не его "
                   "историю; без этого случая ② зеленел бы у проверки, лезущей к соседу",
                   differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ СКОЛЬКО РАЗ ОТВЕЧЕНО — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
