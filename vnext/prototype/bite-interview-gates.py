#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: ворота разбора замысла (карточка #430 ступени ② и ④).

Предмет — три врезки по правилу interview-before-recommend:
  · заведение карточки печатает ТРИ вопроса разбора ПОДСКАЗКОЙ, и тройки РАЗНЫЕ
    для разных видов работы (вид — по тегам);
  · перевод в «жду слова» БЕЗ флага --interviewed печатает предупреждение
    С ИМЕНЕМ незаданного вопроса и НЕ задерживает перевод; с флагом — ТИХО;
  · стартовая сводка роли доставляет ждущие слова владельца вопросы:
    старое первым, ноль ждущих — НИ ОДНОЙ строки.

Всё на СТЕНДЕ (чистая база из живой схемы); живая база не открывается вовсе.
Обратные ходы — на КОПИЯХ инструментов в каталоге стенда: ослабление одной
ветки роняет ровно свой случай. Якорь не нашёлся — ПРИЁМКА НЕ СОСТОЯЛАСЬ,
а не молчание.

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (несошедшееся — находка, не повод переписать):
  ①  add тег rules ......... «вид: правило/норма» + все 3 вопроса вида · код 0
  ②  add тег tools ......... «вид: инструмент/проверка», ни одного вопроса из ①
  ③  add без тегов ......... «вид: прочее»
  ④  → awaiting_word ....... предупреждение с «НА ЧЕЙ ВОПРОС» и видом; статус
                             в базе ПЕРЕВЕДЁН (ворота не запирают) · код 0
  ⑤  то же с --interviewed . предупреждения НЕТ; статус переведён (встречный①)
  ⑥  → in_review ........... предупреждения разбора НЕТ (ворота только на выносе)
  ⑦  сводка: 2 ждущих ...... «ЖДУТ СЛОВА ВЛАДЕЛЬЦА: 2», СТАРАЯ карточка первой
  ⑧  сводка: 0 ждущих ...... ни строки блока, ни поломки секции (встречный①)
  ⑨  отвеченный исчез ...... «: 1», номер отвеченной карточки отсутствует
  Р1 вид выключен .......... ① на копии теряет «вид: правило/норма»
  Р2 тишина флага снята .... ⑤ на копии получает предупреждение при --interviewed
  Р3 «ноль → молчание» снят  ⑧ на копии оставляет след секции

Зовут так:
    python <КОНТУР>/vnext-tools/bite-interview-gates.py
⚠️ при живом объявлении о правке этих инструментов зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import os
import pathlib
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = mezo_paths.live_scripts()
BACKLOG = SCRIPTS / "backlog.py"
BRIEF = SCRIPTS / "role-brief.py"

ТАБЛИЦЫ = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status")

ВОПРОС_ОБЯЗАТЕЛЬНЫЙ = "НА ЧЕЙ ВОПРОС"
ВОПРОСЫ_ПРАВИЛА = ["кому это сказано", "когда и чем это протухнет", "чем держится"]
ПРЕДУПРЕЖДЕНИЕ = "БЕЗ объявленного разбора"
БЛОК_СВОДКИ = "ЖДУТ СЛОВА ВЛАДЕЛЬЦА"
СЕКЦИЯ_СЛОМАНА = "вопросы владельцу: ИСТОЧНИК НЕ ПРОЧИТАН"


def чистая_база(путь: pathlib.Path) -> None:
    живая = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    ддл = [r[0] for r in живая.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name IN "
        f"({','.join('?' * len(ТАБЛИЦЫ))})", ТАБЛИЦЫ)]
    живая.close()
    if len(ддл) != len(ТАБЛИЦЫ):
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в живой схеме нашлось {len(ддл)} "
                         f"таблиц из {len(ТАБЛИЦЫ)} — стенд не собрать")
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


def ослабить(живой: pathlib.Path, каталог: pathlib.Path, якорь: str, замена: str) -> pathlib.Path:
    текст = живой.read_bytes().decode("utf-8")
    if текст.count(якорь) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{якорь}» найден "
                         f"{текст.count(якорь)} раз в {живой.name} (нужен ровно 1)")
    копия = каталог / живой.name
    копия.write_bytes(текст.replace(якорь, замена).encode("utf-8"))
    return копия


def main() -> int:
    d = mezo_stand.new("interview-")
    db = d / "stand.db"
    чистая_база(db)
    провалы: list[str] = []
    судов = 0   # живой счёт: константа «всего N» уже соврала на первом же прогоне

    def суд(имя: str, условие: bool, след: str = ""):
        nonlocal судов
        судов += 1
        print(f"{'✅' if условие else '🔴'} {имя}")
        if not условие:
            провалы.append(имя)
            if след:
                print(f"   след: {след[:400]}")

    # ── заведение трёх карточек разных видов ─────────────────────────────────
    rc1, out1 = зов(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-правило", "--tags", "rules",
                    "--body", "тело", "--done-when", "критерий")
    суд("① add rules: код 0 и «вид: правило/норма»",
        rc1 == 0 and "вид: правило/норма" in out1, out1)
    суд("①а add rules: все 3 вопроса вида напечатаны",
        all(в in out1 for в in ВОПРОСЫ_ПРАВИЛА), out1)

    rc2, out2 = зов(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-инструмент", "--tags", "tools",
                    "--body", "тело", "--done-when", "критерий")
    суд("② add tools: «вид: инструмент/проверка» и НИ ОДНОГО вопроса вида ①",
        rc2 == 0 and "вид: инструмент/проверка" in out2
        and not any(в in out2 for в in ВОПРОСЫ_ПРАВИЛА), out2)

    rc3, out3 = зов(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-прочее", "--tags", "",
                    "--body", "тело", "--done-when", "критерий")
    суд("③ add без тегов: «вид: прочее»", rc3 == 0 and "вид: прочее" in out3, out3)

    con = sqlite3.connect(str(db))
    номера = [r[0] for r in con.execute("SELECT id FROM backlog ORDER BY id")]
    con.close()
    if len(номера) != 3:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в стенде {len(номера)} карточек из 3")
    к1, к2, к3 = номера

    # ── вынос владельцу: предупреждение против тишины ────────────────────────
    rc4, out4 = зов(BACKLOG, "--db", str(db), "status", str(к1), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос владельцу: как решим?")
    con = sqlite3.connect(str(db))
    ст1 = con.execute("SELECT status FROM backlog WHERE id=?", (к1,)).fetchone()[0]
    con.close()
    суд("④ вынос без флага: предупреждение с именем вопроса, вид по тегам",
        rc4 == 0 and ПРЕДУПРЕЖДЕНИЕ in out4 and ВОПРОС_ОБЯЗАТЕЛЬНЫЙ in out4
        and "вид: правило/норма" in out4, out4)
    суд("④а перевод НЕ задержан (ворота не запирают)", ст1 == "awaiting_word")

    rc5, out5 = зов(BACKLOG, "--db", str(db), "status", str(к2), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос владельцу", "--interviewed")
    con = sqlite3.connect(str(db))
    ст2 = con.execute("SELECT status FROM backlog WHERE id=?", (к2,)).fetchone()[0]
    con.close()
    суд("⑤ вынос с --interviewed: ТИХО и переведён (встречный①)",
        rc5 == 0 and ПРЕДУПРЕЖДЕНИЕ not in out5 and ст2 == "awaiting_word", out5)

    rc6, out6 = зов(BACKLOG, "--db", str(db), "status", str(к3), "in_review",
                    "--actor", "TEST", "--note", "на приёмку")
    суд("⑥ не-вынос (in_review): ворота молчат",
        rc6 == 0 and "разбора замысла" not in out6, out6)

    # ── доставка в сводке: старое первым, ноль — молчание ────────────────────
    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog_events SET at='2026-08-18 12:00:00' "
                "WHERE backlog_id=? AND to_status='awaiting_word'", (к1,))
    con.commit()
    con.close()
    rc7, out7 = зов(BRIEF, "--role", "TEST", "--db", str(db))
    строки7 = [s for s in out7.splitlines() if "карточка #" in s]
    суд("⑦ сводка: «ЖДУТ СЛОВА ВЛАДЕЛЬЦА: 2», старая карточка ПЕРВОЙ",
        rc7 == 0 and f"{БЛОК_СВОДКИ}: 2" in out7 and len(строки7) >= 2
        and f"#{к1}" in строки7[0] and f"#{к2}" in строки7[1], out7)

    # ═══ Карточка #448 (TAXO): порядок ОДИНАКОВ в обоих мирах по построению —
    # различает только ВОЗРАСТ. Суд ⑦ был зелен и на сломанном подзапросе (возраст
    # падал на updated_at ⇒ «0 ч»), потому что читал счёт и порядок, а возраст —
    # единственную ценность ступени — не читал вовсе.
    возраст7 = re.search(r"\((\w+), (\d+)\s*дн\)", строки7[0]) if строки7 else None
    суд("⑦-бис возраст старой — от часа ПОСТАНОВКИ: «N дн», N≥10 (карточка #448)",
        возраст7 is not None and int(возраст7.group(2)) >= 10,
        строки7[0] if строки7 else out7)

    db0 = d / "stand-empty.db"
    чистая_база(db0)
    rc8, out8 = зов(BRIEF, "--role", "TEST", "--db", str(db0))
    суд("⑧ сводка на нуле ждущих: ни строки блока, ни поломки секции (встречный①)",
        rc8 == 0 and БЛОК_СВОДКИ not in out8 and СЕКЦИЯ_СЛОМАНА not in out8, out8)

    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog SET status='done' WHERE id=?", (к1,))
    con.commit()
    con.close()
    rc9, out9 = зов(BRIEF, "--role", "TEST", "--db", str(db))
    суд("⑨ отвеченный исчез немедленно: «: 1», старого номера нет (встречный②)",
        rc9 == 0 and f"{БЛОК_СВОДКИ}: 1" in out9
        and not any(f"#{к1}" in s for s in out9.splitlines() if "карточка #" in s), out9)

    # ── обратные ходы: ослабление одной ветки роняет ровно свой случай ───────
    среда = {"PYTHONPATH": str(SCRIPTS)}

    к_р1 = ослабить(BACKLOG, d, "if теги & ключи:", "if False:")
    _, out_r1 = зов(к_р1, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-Р1", "--tags", "rules",
                    "--body", "тело", "--done-when", "критерий", окружение=среда)
    суд("Р1 вид выключен: rules-карточка потеряла «вид: правило/норма»",
        "вид: правило/норма" not in out_r1 and "вид: прочее" in out_r1, out_r1)

    к_р2 = ослабить(BACKLOG, d, "and not a.interviewed:", "and True:")
    _, out_r2 = зов(к_р2, "--db", str(db), "status", str(к3), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос", "--interviewed",
                    окружение=среда)
    суд("Р2 тишина флага снята: --interviewed получает предупреждение (⑤ бы упал)",
        ПРЕДУПРЕЖДЕНИЕ in out_r2, out_r2)

    # якорь с контекстом: голое «if not rows:» в файле встречается трижды (права, умения)
    к_р3 = ослабить(BRIEF, d,
                    "ORDER BY 4 DESC\").fetchall()\n        if not rows:",
                    "ORDER BY 4 DESC\").fetchall()\n        if rows is None:")
    _, out_r3 = зов(к_р3, "--role", "TEST", "--db", str(db0), окружение=среда)
    суд("Р3 «ноль → молчание» снят: пустой стенд оставляет след секции (⑧ бы упал)",
        БЛОК_СВОДКИ in out_r3 or СЕКЦИЯ_СЛОМАНА in out_r3, out_r3)

    # ═══ Р4 (карточка #448, сценарий критерия ДОСЛОВНО): подзапрос события выключен ⇒
    # COALESCE падает на updated_at ⇒ возраст старой рушится до часов. Роняет РОВНО
    # чтение возраста (⑦-бис): счёт цел; порядок при обнулённых возрастах не определён
    # по построению — потому здесь и не судится (чинить порядком запрещено критерием).
    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog SET status='awaiting_word' WHERE id=?", (к1,))
    con.commit()
    # Счёт ждущих — ЗАПРОСОМ, не константой: обратный ход Р2 уже перевёл третью
    # карточку в «жду слова», и вписанное «: 2» пало бы от истории соседних судов
    # (первый прогон это и показал — приёмка поймала свой суд, не код).
    ждущих = con.execute(
        "SELECT COUNT(*) FROM backlog WHERE status='awaiting_word'").fetchone()[0]
    con.close()
    к_р4 = ослабить(BRIEF, d, "e.to_status = 'awaiting_word'",
                    "e.to_status = 'no-such-status'")
    _, out_r4 = зов(к_р4, "--role", "TEST", "--db", str(db), окружение=среда)
    строки_р4 = [s for s in out_r4.splitlines() if "карточка #" in s]
    стр_к1 = next((s for s in строки_р4 if f"#{к1}" in s), "")
    суд("Р4 подзапрос события выключен: возраст старой пал с «дн» на часы — ⑦-бис "
        "пал бы; счёт цел (роняет РОВНО возраст)",
        f"{БЛОК_СВОДКИ}: {ждущих}" in out_r4 and стр_к1 != "" and " дн)" not in стр_к1,
        стр_к1 or out_r4)

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — обе ступени держатся, обратные ходы роняют своё")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
