#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-neighbour-asks — приёмка проверки «вопросы соседей без нашего ответа».

ЗАЧЕМ. 18.08 первый живой обмен с контуром tapas показал: проверка моста смотрела ТОЛЬКО
в наш репозиторий, а сосед пишет в СВОЮ исходящую папку — в своём. Его вопрос был для нас
невидим, и всё это время у нас было зелено. Здесь испытывается починка: видит ли проверка
чужую исходящую, молчит ли она, когда ответ уже положен, и говорит ли вслух, когда сосед
записан, а смотреть некуда.

    python C:/guts/.atlas/vnext-tools/bite-neighbour-asks.py
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def build(tmp: pathlib.Path, with_ask: bool, with_answer: bool, with_box: bool):
    """Собирает две стороны: наш контур и соседа. Возвращает путь к нашему guard-all."""
    live = pathlib.Path(__file__).resolve().parent.parent / ".mezosync"
    ours = tmp / "atlas"
    shutil.copytree(live / "scripts", ours / ".mezosync" / "scripts")
    shutil.copy(live / "mezosync.db", ours / ".mezosync" / "mezosync.db")
    ourbox = ours / "atlas.archs" / ".mezosync" / "bridges" / "atlas-neigh"
    ourbox.mkdir(parents=True)
    if with_answer:
        # ⚠️ ИМЕНА РАЗНЫЕ НАМЕРЕННО: второе слово — КОМУ файл адресован, у вопроса
        # это мы, у ответа — сосед. Первая редакция ждала «answer.atlas.…»,
        # которого не бывает по построению, и не видела готовых ответов.
        (ourbox / "answer.neigh.thing.md").write_text("ответ", encoding="utf-8")

    theirs = tmp / "neigh"
    (theirs / ".mezosync").mkdir(parents=True)
    sqlite3.connect(theirs / ".mezosync" / "mezosync.db").close()
    if with_box:
        box = theirs / "neigh.archs" / ".mezosync" / "bridges" / "neigh-atlas"
        box.mkdir(parents=True)
        if with_ask:
            (box / "ask.atlas.thing.md").write_text("вопрос", encoding="utf-8")

    con = sqlite3.connect(ours / ".mezosync" / "mezosync.db")
    con.execute("DELETE FROM cross_links")
    con.execute("INSERT INTO cross_links (source_group, target_group, target_db_path, description)"
                " VALUES ('atlas','neigh',?,'проба')",
                (str(theirs / ".mezosync" / "mezosync.db"),))
    con.commit()
    con.close()
    return ours / ".mezosync" / "scripts" / "guard-all.py"


def run(guard) -> str:
    r = subprocess.run([sys.executable, str(guard), "--skip", "drift,память,ленты"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-neigh-"))
    try:
        out = run(build(tmp / "a", with_ask=True, with_answer=False, with_box=True))
        ok &= case("① вопрос в ИСХОДЯЩЕЙ СОСЕДА виден, хотя лежит в чужом репозитории",
                   "ask.atlas.thing.md" in out,
                   "именно этого проверка не умела до 18.08: сосед пишет у себя, "
                   "а у нас всё зелено — вопрос мог пролежать сколько угодно", differ=True)

        out = run(build(tmp / "b", with_ask=True, with_answer=True, with_box=True))
        ok &= case("② ответ с ДРУГИМ адресатом в имени всё равно считается ответом",
                   "отвечен" in out,
                   "замер 18.08: четыре ответа лежали готовыми (29 и 39 КБ), а признак "
                   "показывал вопросы неотвеченными — и через 48 ч покрасил бы контур на "
                   "СДЕЛАННОЙ работе. Худший вид тревоги: он учит не верить красному", differ=True)

        # ⑤ ОДИН ВОПРОС, ОТВЕЧЕННЫЙ ВДВОЁМ более узкими темами.
        d5 = tmp / "e"
        guard5 = build(d5, with_ask=True, with_answer=False, with_box=True)
        (d5 / "atlas" / "atlas.archs" / ".mezosync" / "bridges" / "atlas-neigh"
         / "answer.neigh.thing-first-half.md").write_text("половина", encoding="utf-8")
        out = run(guard5)
        ok &= case("⑤ вопрос, отвечённый файлом с более УЗКОЙ темой, не держится красным",
                   "отвечен" in out,
                   "вопрос про две роли отвечают двое, каждый про свою: требовать дословного",
                   differ=True)

        out = run(build(tmp / "c", with_ask=False, with_answer=False, with_box=True))
        ok &= case("③ на пустой папке проверка не выдумывает вопросов",
                   "вопросов без ответа нет" in out,
                   "контроль: если бы она краснела на пустом месте, красное перестали бы читать",
                   differ=True)

        out = run(build(tmp / "d", with_ask=True, with_answer=False, with_box=False))
        ok &= case("④ сосед записан, а папки обмена нет — сказано вслух, а не молчанием",
                   "исходящей папки не нашлось" in out,
                   "молчание здесь неотличимо от «вопросов нет», а это разные вещи: "
                   "во втором случае мы просто не туда смотрим", differ=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print((f"✅ ВОПРОСЫ СОСЕДЕЙ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
