#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: взятие карточки видит чужое живое взятие (карточка #441).

Предмет — врезка в cmd_claim: взятие карточки, которую УЖЕ держит другая роль,
называет её имя и час окончания шага — ПРЕДУПРЕЖДЕНИЕМ, не отказом (двое на одной
карточке иногда законны: сдающий и приёмщик). Живое чужое взятие = последний claim
роли без более позднего claim_release, срок не истёк. Плюс граница ЧЕСТНО названа
в тексте каждого взятия: машина видит только взятия инструментом — комментарий
и записку в ленте она не читает (третий встречный из карточки, случай TAXO).

Всё на СТЕНДЕ (чистая база из живой схемы); живая база не открывается вовсе.
Роли стенда выдуманные (STUB1/STUB2) — «называться чужой ролью нельзя» про живой
контур, песочницы это не касается (ровно та граница, из-за которой автор карточки
свою вторую половину не мерил).

ПРОГНОЗЫ, НАЗВАННЫЕ ДО ПРОГОНОВ (несошедшееся — находка, не повод переписать):
  ①  STUB1 взял → STUB2 берёт ту же ... «УЖЕ ДЕРЖИТ STUB1» + «до …UTC» · код 0 ·
                                        взятие STUB2 ЗАПИСАНО (событий claim станет 2)
  ②  встречный (а): свободная ........ «УЖЕ ДЕРЖИТ» НЕ печатается
  ③  встречный (б): чужой шаг ИСТЁК .. тихо — иначе роль научится пролистывать
  ④  чужое взятие СНЯТО (release) .... тихо
  ⑤  СВОЁ повторное взятие ........... тихо («УЖЕ ДЕРЖИТ» — про ЧУЖУЮ руку)
  ⑥  граница в тексте КАЖДОГО взятия . «запиской в ленте машина не читает»
  Р1 условие срока ослеплено ......... ① на копии молчит, живой предупреждает
  ⑧  карточка #451: снятие БЕЗ итога . совет прежний + «НЕ снято» · события claim_release
                                       НЕТ · подстановки «работа окончена…» НЕТ ·
                                       взятие ЖИВОЕ (вторая рука предупреждена)
  ⑨  ВСТРЕЧНЫЙ: снятие С итогом ...... тихо, ход прежний, тело события ДОСЛОВНО
  ⑩  итог из одних пробелов .......... как отсутствие: события не прибавилось
  Р2 лечение снято ................... копия ПИШЕТ событие при пустом итоге

Зовут так:
    python <КОНТУР>/vnext-tools/bite-claim-second-hand.py
⚠️ при живом объявлении о правке backlog.py зови с MEZO_ROLE=<твоя роль>.
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = mezo_paths.live_scripts()
BACKLOG = SCRIPTS / "backlog.py"

TABLES = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status")

HOLDS = "УЖЕ ДЕРЖИТ"
BOUNDARY = "запиской в ленте машина не читает"


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
    d = mezo_stand.new("claim2hand-")
    db = d / "stand.db"
    clean_db(db)
    failures: list[str] = []
    cases = 0   # живой счёт: записанная константа протухает молча

    def case(name: str, condition: bool, trace: str = ""):
        nonlocal cases
        cases += 1
        print(f"{'✅' if condition else '🔴'} {name}")
        if not condition:
            failures.append(name)
            if trace:
                print(f"   след: {trace[:400]}")

    def card(name: str) -> int:
        rc, _ = call_tool(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                    "--title", name, "--body", "тело", "--done-when", "критерий")
        if rc != 0:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка «{name}» не завелась")
        con = sqlite3.connect(str(db))
        bid = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
        con.close()
        return bid

    # ── ① чужое живое взятие: имя + час, предупреждение не отказ, запись прошла ──
    bid1 = card("проба-столкновение")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid1), "--actor", "STUB1",
                  "--minutes", "60", "--note", "первая рука")
    if rc != 0 or HOLDS in out:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: первое взятие не прошло чисто")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid1), "--actor", "STUB2",
                  "--minutes", "30", "--note", "вторая рука")
    con = sqlite3.connect(str(db))
    claims_count = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                          "AND event_type='claim'", (bid1,)).fetchone()[0]
    con.close()
    case("① вторая рука: «УЖЕ ДЕРЖИТ STUB1» + час, код 0, взятие ЗАПИСАНО (2 события)",
        rc == 0 and f"{HOLDS} STUB1" in out and "до 2026-" in out and claims_count == 2, out)

    # ── ② встречный (а): свободная карточка — тихо ───────────────────────────────
    bid2 = card("проба-свободная")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid2), "--actor", "STUB2",
                  "--minutes", "30", "--note", "свободную беру")
    case("② свободная: предупреждения НЕТ (иначе признак горит всегда)",
        rc == 0 and HOLDS not in out, out)
    case("⑥ граница в тексте взятия: про комментарий и ленту сказано честно",
        BOUNDARY in out, out)

    # ── ③ встречный (б): чужой шаг ИСТЁК — тихо ─────────────────────────────────
    bid3 = card("проба-истёкший")
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md)"
                " VALUES (?,?,?,?)",
                (bid3, "STUB1", "claim", "до 2026-08-01 00:00:00 UTC · давно истёк"))
    con.commit()
    con.close()
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid3), "--actor", "STUB2",
                  "--minutes", "30", "--note", "после истёкшего")
    case("③ чужой шаг ИСТЁК: тихо (иначе роль научится пролистывать)",
        rc == 0 and HOLDS not in out, out)

    # ── ④ чужое взятие СНЯТО — тихо ──────────────────────────────────────────────
    bid4 = card("проба-снятое")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid4), "--actor", "STUB1",
        "--minutes", "60", "--note", "возьму и сниму")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid4), "--actor", "STUB1",
        "--release", "--note", "снял: получилось")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid4), "--actor", "STUB2",
                  "--minutes", "30", "--note", "после снятия")
    case("④ чужое взятие СНЯТО: тихо (release гасит)",
        rc == 0 and HOLDS not in out, out)

    # ── ⑤ СВОЁ повторное взятие — тихо ───────────────────────────────────────────
    bid5 = card("проба-своё-повторно")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid5), "--actor", "STUB1",
        "--minutes", "60", "--note", "первый шаг")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid5), "--actor", "STUB1",
                  "--minutes", "60", "--note", "продлеваю шаг")
    case("⑤ СВОЁ повторное взятие: тихо (предупреждение — про ЧУЖУЮ руку)",
        rc == 0 and HOLDS not in out, out)

    # ── карточка #451: совет о пустом итоге ДО записи ───────────────────────────
    # ⑧ снятие БЕЗ итога: совет прежний + «НЕ снято», события в журнале НЕТ,
    #    взятие остаётся ЖИВЫМ (вторая рука по-прежнему предупреждена)
    bid7 = card("проба-пустой-итог")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid7), "--actor", "STUB1",
        "--minutes", "60", "--note", "держу для случая 451")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid7), "--actor", "STUB1",
                  "--release")
    con = sqlite3.connect(str(db))
    releases7 = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                           "AND event_type='claim_release'", (bid7,)).fetchone()[0]
    substitutions_count = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                              "AND body_md='работа окончена или отложена'",
                              (bid7,)).fetchone()[0]
    con.close()
    case("⑧ снятие БЕЗ итога: совет прежний + «НЕ снято», события НЕТ, подстановки НЕТ "
        "(прогноз: релизов 0)",
        rc == 0 and "БЕЗ итога" in out and "объявление НЕ снято" in out
        and releases7 == 0 and substitutions_count == 0, out)
    _, out2 = call_tool(BACKLOG, "--db", str(db), "claim", str(bid7), "--actor", "STUB2",
                  "--minutes", "30", "--note", "вторая рука после пустого снятия")
    case("⑧-бис взятие ОСТАЛОСЬ живым: вторая рука предупреждена «УЖЕ ДЕРЖИТ»",
        f"{HOLDS} STUB1" in out2, out2)

    # ⑨ ВСТРЕЧНЫЙ (критерий ②): снятие С итогом — тихо, тело дословно
    bid8 = card("проба-итог-словами")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid8), "--actor", "STUB1",
        "--minutes", "60", "--note", "держу")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid8), "--actor", "STUB1",
                  "--release", "--note", "итог: сделано ровно это")
    con = sqlite3.connect(str(db))
    body8 = con.execute("SELECT body_md FROM backlog_events WHERE backlog_id=? "
                        "AND event_type='claim_release'", (bid8,)).fetchone()
    con.close()
    case("⑨ ВСТРЕЧНЫЙ: снятие С итогом — тихо, ход прежний, тело ДОСЛОВНО",
        rc == 0 and "БЕЗ итога" not in out and "🔓" in out
        and body8 == ("итог: сделано ровно это",), out)

    # ⑩ РАЗЛИЧАЮЩИЙ (критерий ③): итог из одних пробелов = отсутствие итога
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid8), "--actor", "STUB1",
                  "--minutes", "60", "--note", "держу снова")
    rc, out = call_tool(BACKLOG, "--db", str(db), "claim", str(bid8), "--actor", "STUB1",
                  "--release", "--note", "   ")
    con = sqlite3.connect(str(db))
    releases8 = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                           "AND event_type='claim_release'", (bid8,)).fetchone()[0]
    con.close()
    case("⑩ итог из одних пробелов = ОТСУТСТВИЕ: события не прибавилось (прогноз: 1)",
        rc == 0 and "объявление НЕ снято" in out and releases8 == 1, out)

    # Р2 ОБРАТНЫЙ ХОД (критерий ④): лечение снято — пустое снятие снова пишет событие
    weak_rev2 = weaken(BACKLOG, d, "return  # 451: пустое снятие не записывается",
                    "pass  # 451 ослаблено приёмкой")
    bid9 = card("проба-Р2")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid9), "--actor", "STUB1",
        "--minutes", "60", "--note", "держу для Р2")
    _, out_blind2 = call_tool(weak_rev2, "--db", str(db), "claim", str(bid9), "--actor", "STUB1",
                       "--release", extra_env={"PYTHONPATH": str(SCRIPTS)})
    con = sqlite3.connect(str(db))
    releases9 = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                           "AND event_type='claim_release'", (bid9,)).fetchone()[0]
    con.close()
    case("Р2 лечение снято: копия ПИШЕТ событие при пустом итоге (случай ⑧ на ней упал бы)",
        releases9 == 1, out_blind2)

    # ── Р1 обратный ход: условие срока ослеплено — ① гаснет на копии ────────────
    env_vars = {"PYTHONPATH": str(SCRIPTS)}
    weak_rev1 = weaken(BACKLOG, d, "if m and m.group(1) > now_text:", "if False:")
    bid6 = card("проба-обратный-ход")
    call_tool(BACKLOG, "--db", str(db), "claim", str(bid6), "--actor", "STUB1",
        "--minutes", "60", "--note", "держу для Р1")
    _, out_blind = call_tool(weak_rev1, "--db", str(db), "claim", str(bid6), "--actor", "STUB2",
                      "--minutes", "30", "--note", "вторая рука, слепая копия",
                      extra_env=env_vars)
    _, out_live = call_tool(BACKLOG, "--db", str(db), "claim", str(bid6), "--actor", "STUB2",
                     "--minutes", "30", "--note", "вторая рука, живой")
    case("Р1 условие ослеплено: копия МОЛЧИТ о чужом взятии, живой называет имя",
        HOLDS not in out_blind and f"{HOLDS} STUB1" in out_live,
        f"слепая: {out_blind[:150]} · живой: {out_live[:150]}")

    print("-" * 76)
    if failures:
        print(f"🔴 ПРИЁМКА: {cases - len(failures)} из {cases}, провалено: "
              + " · ".join(failures))
        return 1
    print(f"✅ ПРИЁМКА: {cases} из {cases} — чужое живое взятие названо, встречные "
          f"тихи, граница про невидимые каналы напечатана, обратный ход роняет своё")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
