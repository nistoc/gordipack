#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-neighbour-asks — приёмка проверки «вопросы соседей без нашего ответа».

ЗАЧЕМ. 18.08 первый живой обмен с контуром tapas показал: проверка моста смотрела ТОЛЬКО
в наш репозиторий, а сосед пишет в СВОЮ исходящую папку — в своём. Его вопрос был для нас
невидим, и всё это время у нас было зелено. Здесь испытывается починка: видит ли проверка
чужую исходящую, молчит ли она, когда ответ уже положен, и говорит ли вслух, когда сосед
записан, а смотреть некуда.

    python <КОНТУР>/vnext-tools/bite-neighbour-asks.py
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

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
    # Каталог группы ищется ПОДЪЁМОМ ПО ПРИЗНАКУ, а не угадыванием глубины:
    # у копии в публичном образце «два уровня вверх» указывают в пустоту,
    # и приёмка падала ещё до первого случая (замер 2026-08-19 16:34 UTC).
    live = mezo_paths.container_root(__file__) / ".mezosync"
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

        # ⑥ ОБМЕН СТАРОГО ВИДА: у соседа своей папки нет, его вопрос лежит в НАШЕЙ.
        # 🪤 Замер 18.08: у соседа, с которым обмен идёт с июля, папки в его контуре нет —
        # и проверка говорила «смотреть некуда», успокаиваясь на этом. А в нашей папке лежал
        # его вопрос от 13.08 с ЕГО ЖЕ сроком 03.09, никем не разобранный 126 часов.
        d6 = tmp / "f"
        guard6 = build(d6, with_ask=False, with_answer=False, with_box=False)
        (d6 / "atlas" / "atlas.archs" / ".mezosync" / "bridges" / "atlas-neigh"
         / "ask.neigh-old-shape-topic.md").write_text("вопрос старого вида", encoding="utf-8")
        out = run(guard6)
        ok &= case("⑥ вопрос соседа в НАШЕЙ папке (обмен старого вида) виден, а не списан",
                   "old-shape-topic" in out,
                   "«у соседа нет папки» не значит «он не спрашивал»: 126 часов молчания "
                   "выглядели порядком именно из-за этого", differ=True)

        # ⑦ ОБМЕН СТАРОГО ВИДА, ВОПРОС ОТВЕЧЕН — вердикт обязан быть ОПРЕДЕЛЁННЫМ.
        # 🪤 Заявка @OPSSRE #221 (19.08 09:00 UTC), поданная сразу после его же ответа соседям:
        # оба вопроса AIA были отвечены и лежали на месте, а прогон печатал ровно одну строку —
        # «исходящей папки не нашлось». Отвеченный вопрос старого вида не печатался НИКАК:
        # ветка сличения тем жила только у соседа со своей папкой, здесь стоял молчаливый
        # `continue`. Роль не могла узнать из прогона ни «отвечено», ни «ждёт» — а это две
        # разные вещи, и молчание похоже на вторую.
        d7 = tmp / "g"
        guard7 = build(d7, with_ask=False, with_answer=False, with_box=False)
        box7 = d7 / "atlas" / "atlas.archs" / ".mezosync" / "bridges" / "atlas-neigh"
        (box7 / "ask.neigh-old-shape-topic.md").write_text("вопрос старого вида", encoding="utf-8")
        (box7 / "answer.neigh.old-shape-topic.md").write_text("ответ", encoding="utf-8")
        out = run(guard7)
        ok &= case("⑦ вопрос старого вида, на который ОТВЕТИЛИ, назван отвеченным поимённо",
                   "«ask.neigh-old-shape-topic.md» отвечен" in out,
                   "различающий против ⑥: там тот же вопрос БЕЗ ответа назван ждущим. "
                   "Если бы обе ветки молчали одинаково, сделанная работа и несделанная "
                   "выглядели бы одним и тем же", differ=True)
        ok &= case("⑧ при этом строка про обмен старого вида НЕ ИСЧЕЗЛА",
                   "обмен СТАРОГО ВИДА" in out and "отвечено 1" in out,
                   "⛔ запрещённый способ закрыть заявку #221 — убрать предупреждение, "
                   "не научив сличать: тогда молчание стало бы выглядеть зелёным. "
                   "Здесь проверяется, что чинили сличение, а не глушили строку", differ=True)

        # ⑨ ВОПРОС, АДРЕСОВАННЫЙ ТРЕТЬЕЙ СТОРОНЕ, НАС НЕ КАСАЕТСЯ.
        # 🪤 Найдено соседом 19.08 11:48 UTC на себе: наша проверка смотрит ВСЕ папки обмена
        # в чужом контейнере, включая мосты, к которым читатель не сторона. У контура tapas
        # это дало шесть чужих вопросов (наш обмен с третьим контуром) и КРАСНОЕ, которое
        # нельзя погасить никаким своим действием: ответить нельзя — вопросы не их, удалить
        # нельзя — файлы чужие, ждать бесполезно — им 578 часов. И оно держало закрытыми
        # их ворота перед отправкой.
        d9 = tmp / "h"
        guard9 = build(d9, with_ask=True, with_answer=False, with_box=True)
        (d9 / "neigh" / "neigh.archs" / ".mezosync" / "bridges" / "neigh-atlas"
         / "ask.third.not-our-business.md").write_text("вопрос третьей стороне",
                                                       encoding="utf-8")
        out = run(guard9)
        ok &= case("⑨ вопрос, адресованный ТРЕТЬЕЙ стороне, не вменяется нам",
                   "not-our-business" not in out and "ask.atlas.thing.md" in out,
                   "различающий: в той же папке лежат наш вопрос и чужой — первый виден, "
                   "второй не вменяется. Иначе контур краснеет вечно по долгу, который "
                   "не его и который он не может закрыть ничем", differ=True)

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
