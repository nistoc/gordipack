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

ТАБЛИЦЫ = ("backlog", "backlog_events", "tracks", "roles", "role_rights",
           "role_skill", "rules", "role_status")

ДЕРЖИТ = "УЖЕ ДЕРЖИТ"
ГРАНИЦА = "запиской в ленте машина не читает"


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
    d = mezo_stand.new("claim2hand-")
    db = d / "stand.db"
    чистая_база(db)
    провалы: list[str] = []
    судов = 0   # живой счёт: записанная константа протухает молча

    def суд(имя: str, условие: bool, след: str = ""):
        nonlocal судов
        судов += 1
        print(f"{'✅' if условие else '🔴'} {имя}")
        if not условие:
            провалы.append(имя)
            if след:
                print(f"   след: {след[:400]}")

    def карточка(имя: str) -> int:
        rc, _ = зов(BACKLOG, "--db", str(db), "add", "--role", "STUB1",
                    "--title", имя, "--body", "тело", "--done-when", "критерий")
        if rc != 0:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: карточка «{имя}» не завелась")
        con = sqlite3.connect(str(db))
        bid = con.execute("SELECT MAX(id) FROM backlog").fetchone()[0]
        con.close()
        return bid

    # ── ① чужое живое взятие: имя + час, предупреждение не отказ, запись прошла ──
    к1 = карточка("проба-столкновение")
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к1), "--actor", "STUB1",
                  "--minutes", "60", "--note", "первая рука")
    if rc != 0 or ДЕРЖИТ in out:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: первое взятие не прошло чисто")
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к1), "--actor", "STUB2",
                  "--minutes", "30", "--note", "вторая рука")
    con = sqlite3.connect(str(db))
    клеймов = con.execute("SELECT COUNT(*) FROM backlog_events WHERE backlog_id=? "
                          "AND event_type='claim'", (к1,)).fetchone()[0]
    con.close()
    суд("① вторая рука: «УЖЕ ДЕРЖИТ STUB1» + час, код 0, взятие ЗАПИСАНО (2 события)",
        rc == 0 and f"{ДЕРЖИТ} STUB1" in out and "до 2026-" in out and клеймов == 2, out)

    # ── ② встречный (а): свободная карточка — тихо ───────────────────────────────
    к2 = карточка("проба-свободная")
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к2), "--actor", "STUB2",
                  "--minutes", "30", "--note", "свободную беру")
    суд("② свободная: предупреждения НЕТ (иначе признак горит всегда)",
        rc == 0 and ДЕРЖИТ not in out, out)
    суд("⑥ граница в тексте взятия: про комментарий и ленту сказано честно",
        ГРАНИЦА in out, out)

    # ── ③ встречный (б): чужой шаг ИСТЁК — тихо ─────────────────────────────────
    к3 = карточка("проба-истёкший")
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md)"
                " VALUES (?,?,?,?)",
                (к3, "STUB1", "claim", "до 2026-08-01 00:00:00 UTC · давно истёк"))
    con.commit()
    con.close()
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к3), "--actor", "STUB2",
                  "--minutes", "30", "--note", "после истёкшего")
    суд("③ чужой шаг ИСТЁК: тихо (иначе роль научится пролистывать)",
        rc == 0 and ДЕРЖИТ not in out, out)

    # ── ④ чужое взятие СНЯТО — тихо ──────────────────────────────────────────────
    к4 = карточка("проба-снятое")
    зов(BACKLOG, "--db", str(db), "claim", str(к4), "--actor", "STUB1",
        "--minutes", "60", "--note", "возьму и сниму")
    зов(BACKLOG, "--db", str(db), "claim", str(к4), "--actor", "STUB1",
        "--release", "--note", "снял: получилось")
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к4), "--actor", "STUB2",
                  "--minutes", "30", "--note", "после снятия")
    суд("④ чужое взятие СНЯТО: тихо (release гасит)",
        rc == 0 and ДЕРЖИТ not in out, out)

    # ── ⑤ СВОЁ повторное взятие — тихо ───────────────────────────────────────────
    к5 = карточка("проба-своё-повторно")
    зов(BACKLOG, "--db", str(db), "claim", str(к5), "--actor", "STUB1",
        "--minutes", "60", "--note", "первый шаг")
    rc, out = зов(BACKLOG, "--db", str(db), "claim", str(к5), "--actor", "STUB1",
                  "--minutes", "60", "--note", "продлеваю шаг")
    суд("⑤ СВОЁ повторное взятие: тихо (предупреждение — про ЧУЖУЮ руку)",
        rc == 0 and ДЕРЖИТ not in out, out)

    # ── Р1 обратный ход: условие срока ослеплено — ① гаснет на копии ────────────
    среда = {"PYTHONPATH": str(SCRIPTS)}
    к_р1 = ослабить(BACKLOG, d, "if m and m.group(1) > сейчас:", "if False:")
    к6 = карточка("проба-обратный-ход")
    зов(BACKLOG, "--db", str(db), "claim", str(к6), "--actor", "STUB1",
        "--minutes", "60", "--note", "держу для Р1")
    _, out_слеп = зов(к_р1, "--db", str(db), "claim", str(к6), "--actor", "STUB2",
                      "--minutes", "30", "--note", "вторая рука, слепая копия",
                      окружение=среда)
    _, out_жив = зов(BACKLOG, "--db", str(db), "claim", str(к6), "--actor", "STUB2",
                     "--minutes", "30", "--note", "вторая рука, живой")
    суд("Р1 условие ослеплено: копия МОЛЧИТ о чужом взятии, живой называет имя",
        ДЕРЖИТ not in out_слеп and f"{ДЕРЖИТ} STUB1" in out_жив,
        f"слепая: {out_слеп[:150]} · живой: {out_жив[:150]}")

    print("-" * 76)
    if провалы:
        print(f"🔴 ПРИЁМКА: {судов - len(провалы)} из {судов}, провалено: "
              + " · ".join(провалы))
        return 1
    print(f"✅ ПРИЁМКА: {судов} из {судов} — чужое живое взятие названо, встречные "
          f"тихи, граница про невидимые каналы напечатана, обратный ход роняет своё")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
