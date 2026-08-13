#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: журнал правок памяти называет ИСПОЛНИТЕЛЯ, а не владельца секции.

ПОВОД (карточка #164, замер 2026-08-10 14:57 UTC). save-phoenix писал в audit_log.actor_role
значение --role — ЧЬЯ секция, а не КТО правил. Владелец спросил «что COORD правил за смену»,
и единственная запись по COORD оказалась правкой PROTO (§7 — его зона с 12:47). Проверка
добросовестности роли получила бы ложную улику против неё.

🎯 КЛАСС: журнал называет не того, кто действовал, — и делает это уверенно, без пометки
о неполноте. Форма починки — из backlog.py (--actor отдельным флагом), образец честного
авторства — applied_by журнала схемы.

⚖️ ЧИТАТЕЛИ audit_log ПРОВЕРЕНЫ ГРЕПОМ ДО ПРАВКИ (критерий карточки): приёмки создают таблицу
в фикстурах и семантику actor_role не судят; перископ перечисляет имя таблицы в списке;
set-rule/set-registry пишут свои действия. На «actor_role == владелец секции» не опирался
никто — расширение набора значений никого не выключает.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

SAVER = mezo_target.script("save-phoenix.py")
LIVE_DB = mezo_paths.live_db()
МЕТКА = "ЗОНД-АВТОРСТВА"

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(SAVER), "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def last_audit(db: Path) -> tuple:
    con = sqlite3.connect(db)
    row = con.execute("SELECT actor_role, target, diff_md FROM audit_log "
                      "WHERE action='save_phoenix' ORDER BY rowid DESC LIMIT 1").fetchone()
    con.close()
    return row or ("—", "—", "—")


def body_of(db: Path, role: str, section: str) -> str:
    con = sqlite3.connect(db)
    r = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                    (role, section)).fetchone()
    con.close()
    return r[0] if r else ""


def main() -> int:
    for p in (SAVER, LIVE_DB):
        if not p.exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет по пути {p}")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        f = Path(tmp) / "s.md"

        # ① ПРАВКА ЧУЖОЙ СЕКЦИИ С --actor: журнал называет ИСПОЛНИТЕЛЯ, цель — роль/секция.
        #    Главный случай: ради него карточка и заведена.
        prev = body_of(db, "CORE", "state")
        f.write_text(prev + f"\n{МЕТКА} правка чужого ①", encoding="utf-8")
        code, out = run(db, "--role", "CORE", "--section", "state",
                        "--file", str(f), "--actor", "PROTO")
        actor, target, diff = last_audit(db)
        case("① чужая секция с --actor: журнал называет исполнителя и цель",
             code == 0 and actor == "PROTO" and target == "phoenix.CORE.state"
             and "чужая секция" in diff,
             f"actor={actor} · target={target} · diff={diff[:60]}")

        # ② КОНТРОЛЬНАЯ ПАРА: своя секция БЕЗ флага — прежнее поведение, журнал однозначен.
        #    Без неё приёмку прошёл бы инструмент, пишущий PROTO ВСЕГДА.
        prev = body_of(db, "TAXO", "state")
        f.write_text(prev + f"\n{МЕТКА} своя секция ②", encoding="utf-8")
        run(db, "--role", "TAXO", "--section", "state", "--file", str(f))
        actor, target, diff = last_audit(db)
        case("② своя секция без флага: журнал пишет владельца, пометки о чужом нет",
             actor == "TAXO" and target == "phoenix.TAXO.state" and "чужая" not in diff,
             f"actor={actor} · target={target}")

        # ③ РЕГИСТР ИСПОЛНИТЕЛЯ НОРМАЛИЗУЕТСЯ — иначе расщепление proto/PROTO, класс,
        #    оплаченный на курсорах (регистрозависимые save/read при аплкейсящем ридере).
        prev = body_of(db, "CORE", "state")
        f.write_text(prev + f"\n{МЕТКА} регистр ③", encoding="utf-8")
        run(db, "--role", "CORE", "--section", "state", "--file", str(f), "--actor", "proto")
        actor, _, _ = last_audit(db)
        case("③ --actor proto нормализован к PROTO", actor == "PROTO", f"actor={actor}")

        # ④ ВИДИМОСТЬ В ВЫВОДЕ: правка чужого объявляется В ТОЙ ЖЕ СТРОКЕ, что и OK, —
        #    исполнителю видно, что журнал знает. Молчаливое верное поведение — полповедения.
        case("④ вывод называет чужую правку рядом с OK",
             "правил PROTO" in out or "чужая секция" in out, f"хвост: {out.strip()[-90:]}")

    # ⑤ ЖИВАЯ БАЗА ЦЕЛА.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute("SELECT COUNT(*) FROM phoenix WHERE body LIKE ?",
                         (f"%{МЕТКА}%",)).fetchone()[0]
    con.close()
    case("⑤ живая база не тронута", leaked == 0, f"следов зонда: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 3 (①②③)")
    print("⚖️ ГРАНИЦА: журнал знает, ЧТО ему сказали. Правку чужого БЕЗ --actor он по-прежнему")
    print("   припишет владельцу — механизм не умеет узнать исполнителя сам, это честно названо")
    print("   в подсказке флага. Дисциплину «ставь --actor на чужом» приёмка не проверяет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
