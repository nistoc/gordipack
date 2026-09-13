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

TABLES = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status")

REQUIRED_QUESTION = "НА ЧЕЙ ВОПРОС"
RULE_QUESTIONS = ["кому это сказано", "когда и чем это протухнет", "чем держится"]
WARNING = "БЕЗ объявленного разбора"
SUMMARY_BLOCK = "ЖДУТ СЛОВА ВЛАДЕЛЬЦА"
SECTION_BROKEN = "вопросы владельцу: ИСТОЧНИК НЕ ПРОЧИТАН"


def clean_db(path: pathlib.Path) -> None:
    live_con = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    ddl = [r[0] for r in live_con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name IN "
        f"({','.join('?' * len(TABLES))})", TABLES)]
    live_con.close()
    if len(ddl) != len(TABLES):
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в живой схеме нашлось {len(ddl)} "
                         f"таблиц из {len(TABLES)} — стенд не собрать")
    con = sqlite3.connect(str(path))
    for s in ddl:
        con.execute(s)
    con.commit()
    con.close()


def call_tool(tool: pathlib.Path, *args: str, extra_env=None) -> tuple[int, str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([sys.executable, str(tool), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def weaken(live_path: pathlib.Path, out_dir: pathlib.Path, anchor: str, replacement: str) -> pathlib.Path:
    text = live_path.read_bytes().decode("utf-8")
    if text.count(anchor) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{anchor}» найден "
                         f"{text.count(anchor)} раз в {live_path.name} (нужен ровно 1)")
    copy_path = out_dir / live_path.name
    copy_path.write_bytes(text.replace(anchor, replacement).encode("utf-8"))
    return copy_path


def main() -> int:
    d = mezo_stand.new("interview-")
    db = d / "stand.db"
    clean_db(db)
    failures: list[str] = []
    cases = 0   # живой счёт: константа «всего N» уже соврала на первом же прогоне

    def case(name: str, condition: bool, trace: str = ""):
        nonlocal cases
        cases += 1
        print(f"{'✅' if condition else '🔴'} {name}")
        if not condition:
            failures.append(name)
            if trace:
                print(f"   след: {trace[:400]}")

    # ── заведение трёх карточек разных видов ─────────────────────────────────
    rc1, out1 = call_tool(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-правило", "--tags", "rules",
                    "--body", "тело", "--done-when", "критерий")
    case("① add rules: код 0 и «вид: правило/норма»",
        rc1 == 0 and "вид: правило/норма" in out1, out1)
    case("①а add rules: все 3 вопроса вида напечатаны",
        all(q in out1 for q in RULE_QUESTIONS), out1)

    rc2, out2 = call_tool(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-инструмент", "--tags", "tools",
                    "--body", "тело", "--done-when", "критерий")
    case("② add tools: «вид: инструмент/проверка» и НИ ОДНОГО вопроса вида ①",
        rc2 == 0 and "вид: инструмент/проверка" in out2
        and not any(q in out2 for q in RULE_QUESTIONS), out2)

    rc3, out3 = call_tool(BACKLOG, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-прочее", "--tags", "",
                    "--body", "тело", "--done-when", "критерий")
    case("③ add без тегов: «вид: прочее»", rc3 == 0 and "вид: прочее" in out3, out3)

    con = sqlite3.connect(str(db))
    ids = [r[0] for r in con.execute("SELECT id FROM backlog ORDER BY id")]
    con.close()
    if len(ids) != 3:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в стенде {len(ids)} карточек из 3")
    bid1, bid2, bid3 = ids

    # ── вынос владельцу: предупреждение против тишины ────────────────────────
    rc4, out4 = call_tool(BACKLOG, "--db", str(db), "status", str(bid1), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос владельцу: как решим?")
    con = sqlite3.connect(str(db))
    status1 = con.execute("SELECT status FROM backlog WHERE id=?", (bid1,)).fetchone()[0]
    con.close()
    case("④ вынос без флага: предупреждение с именем вопроса, вид по тегам",
        rc4 == 0 and WARNING in out4 and REQUIRED_QUESTION in out4
        and "вид: правило/норма" in out4, out4)
    case("④а перевод НЕ задержан (разбор замысла не запирает)", status1 == "awaiting_word")

    rc5, out5 = call_tool(BACKLOG, "--db", str(db), "status", str(bid2), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос владельцу", "--interviewed")
    con = sqlite3.connect(str(db))
    status2 = con.execute("SELECT status FROM backlog WHERE id=?", (bid2,)).fetchone()[0]
    con.close()
    case("⑤ вынос с --interviewed: ТИХО и переведён (встречный①)",
        rc5 == 0 and WARNING not in out5 and status2 == "awaiting_word", out5)

    rc6, out6 = call_tool(BACKLOG, "--db", str(db), "status", str(bid3), "in_review",
                    "--actor", "TEST", "--note", "на приёмку")
    case("⑥ не-вынос (in_review): разбор замысла молчит",
        rc6 == 0 and "разбора замысла" not in out6, out6)

    # ── доставка в сводке: старое первым, ноль — молчание ────────────────────
    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog_events SET at='2026-08-18 12:00:00' "
                "WHERE backlog_id=? AND to_status='awaiting_word'", (bid1,))
    con.commit()
    con.close()
    rc7, out7 = call_tool(BRIEF, "--role", "TEST", "--db", str(db))
    lines7 = [s for s in out7.splitlines() if "карточка #" in s]
    case("⑦ сводка: «ЖДУТ СЛОВА ВЛАДЕЛЬЦА: 2», старая карточка ПЕРВОЙ",
        rc7 == 0 and f"{SUMMARY_BLOCK}: 2" in out7 and len(lines7) >= 2
        and f"#{bid1}" in lines7[0] and f"#{bid2}" in lines7[1], out7)

    # ═══ Карточка #448 (TAXO): порядок ОДИНАКОВ в обоих мирах по построению —
    # различает только ВОЗРАСТ. Суд ⑦ был зелен и на сломанном подзапросе (возраст
    # падал на updated_at ⇒ «0 ч»), потому что читал счёт и порядок, а возраст —
    # единственную ценность ступени — не читал вовсе.
    age7 = re.search(r"\((\w+), (\d+)\s*дн\)", lines7[0]) if lines7 else None
    case("⑦-бис возраст старой — от часа ПОСТАНОВКИ: «N дн», N≥10 (карточка #448)",
        age7 is not None and int(age7.group(2)) >= 10,
        lines7[0] if lines7 else out7)

    db0 = d / "stand-empty.db"
    clean_db(db0)
    rc8, out8 = call_tool(BRIEF, "--role", "TEST", "--db", str(db0))
    case("⑧ сводка на нуле ждущих: ни строки блока, ни поломки секции (встречный①)",
        rc8 == 0 and SUMMARY_BLOCK not in out8 and SECTION_BROKEN not in out8, out8)

    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog SET status='done' WHERE id=?", (bid1,))
    con.commit()
    con.close()
    rc9, out9 = call_tool(BRIEF, "--role", "TEST", "--db", str(db))
    case("⑨ отвеченный исчез немедленно: «: 1», старого номера нет (встречный②)",
        rc9 == 0 and f"{SUMMARY_BLOCK}: 1" in out9
        and not any(f"#{bid1}" in s for s in out9.splitlines() if "карточка #" in s), out9)

    # ── обратные ходы: ослабление одной ветки роняет ровно свой случай ───────
    env_vars = {"PYTHONPATH": str(SCRIPTS)}

    weak_rev1 = weaken(BACKLOG, d, "if tag_set & kind_keys:", "if False:")
    _, out_r1 = call_tool(weak_rev1, "--db", str(db), "add", "--role", "TEST",
                    "--title", "проба-Р1", "--tags", "rules",
                    "--body", "тело", "--done-when", "критерий", extra_env=env_vars)
    case("Р1 вид выключен: rules-карточка потеряла «вид: правило/норма»",
        "вид: правило/норма" not in out_r1 and "вид: прочее" in out_r1, out_r1)

    weak_rev2 = weaken(BACKLOG, d, "and not a.interviewed:", "and True:")
    _, out_r2 = call_tool(weak_rev2, "--db", str(db), "status", str(bid3), "awaiting_word",
                    "--actor", "TEST", "--note", "вопрос", "--interviewed",
                    extra_env=env_vars)
    case("Р2 тишина флага снята: --interviewed получает предупреждение (⑤ бы упал)",
        WARNING in out_r2, out_r2)

    # якорь с контекстом: голое «if not rows:» в файле встречается трижды (права, умения)
    weak_rev3 = weaken(BRIEF, d,
                    "ORDER BY 4 DESC\").fetchall()\n        if not rows:",
                    "ORDER BY 4 DESC\").fetchall()\n        if rows is None:")
    _, out_r3 = call_tool(weak_rev3, "--role", "TEST", "--db", str(db0), extra_env=env_vars)
    case("Р3 «ноль → молчание» снят: пустой стенд оставляет след секции (⑧ бы упал)",
        SUMMARY_BLOCK in out_r3 or SECTION_BROKEN in out_r3, out_r3)

    # ═══ Р4 (карточка #448, сценарий критерия ДОСЛОВНО): подзапрос события выключен ⇒
    # COALESCE падает на updated_at ⇒ возраст старой рушится до часов. Роняет РОВНО
    # чтение возраста (⑦-бис): счёт цел; порядок при обнулённых возрастах не определён
    # по построению — потому здесь и не судится (чинить порядком запрещено критерием).
    con = sqlite3.connect(str(db))
    con.execute("UPDATE backlog SET status='awaiting_word' WHERE id=?", (bid1,))
    con.commit()
    # Счёт ждущих — ЗАПРОСОМ, не константой: обратный ход Р2 уже перевёл третью
    # карточку в «жду слова», и вписанное «: 2» пало бы от истории соседних судов
    # (первый прогон это и показал — приёмка поймала свой суд, не код).
    waiting_count = con.execute(
        "SELECT COUNT(*) FROM backlog WHERE status='awaiting_word'").fetchone()[0]
    con.close()
    weak_rev4 = weaken(BRIEF, d, "e.to_status = 'awaiting_word'",
                    "e.to_status = 'no-such-status'")
    _, out_r4 = call_tool(weak_rev4, "--role", "TEST", "--db", str(db), extra_env=env_vars)
    lines_r4 = [s for s in out_r4.splitlines() if "карточка #" in s]
    line_bid1 = next((s for s in lines_r4 if f"#{bid1}" in s), "")
    case("Р4 подзапрос события выключен: возраст старой пал с «дн» на часы — ⑦-бис "
        "пал бы; счёт цел (роняет РОВНО возраст)",
        f"{SUMMARY_BLOCK}: {waiting_count}" in out_r4 and line_bid1 != "" and " дн)" not in line_bid1,
        line_bid1 or out_r4)

    print("-" * 76)
    if failures:
        print(f"🔴 ПРИЁМКА: {cases - len(failures)} из {cases}, провалено: "
              + " · ".join(failures))
        return 1
    print(f"✅ ПРИЁМКА: {cases} из {cases} — обе ступени держатся, обратные ходы роняют своё")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
