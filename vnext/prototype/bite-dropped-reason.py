#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: устаревание карточки требует ПРИЧИНЫ, причина видна В СПИСКЕ, цепочка связей — в show.

ПОВОД (карточка #86 ⑤⑥, замер 2026-08-14 09:34 UTC). Ворота «done без критерия» стояли,
а `dropped` проходил МОЛЧА — и подсказка отказа done сама направляла в эту дверь
(«Отменяешь? Это dropped — там критерий не нужен»). Слово владельца 07.08: объявлять
устаревшими — С ОБЪЯСНЕНИЕМ. Вторая половина: show печатал только ближайшего родителя,
потомков не печатал вовсе — «связи читаются одним запросом» не держалось.

⚖️ С ДВУХ СТОРОН СРАЗУ:
  · dropped БЕЗ причины — отказ, статус в базе не двигается;
  · dropped С причиной — проходит, и причина видна в СПИСКЕ, не только в истории;
  · старые dropped без причины печатают «НЕ ЗАПИСАНА» — честность, не молчание;
  · соседние ворота (done без критерия) и свободные переходы (blocked) НЕ сломаны.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ. Скрипт — живой, через mezo_target.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

BACKLOG = mezo_target.script("backlog.py")
LIVE_DB = mezo_paths.live_db()

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(BACKLOG), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def status_of(db: Path, cid: int) -> str:
    con = sqlite3.connect(db)
    row = con.execute("SELECT status FROM backlog WHERE id=?", (cid,)).fetchone()
    con.close()
    return row[0] if row else "—"


def main() -> int:
    CASES.clear()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "copy.db"
        shutil.copy(LIVE_DB, db)

        # Фикстурная карточка — своя, а не живой номер: живые номера закрываются этапами
        # и приёмка, впечатавшая номер, начала бы падать от чужой работы.
        rc, out = run(db, "add", "--role", "PROTO", "--title", "ЗОНД: устаревание с причиной",
                      "--body", "фикстура приёмки", "--done-when", "прогон этой же приёмки")
        m = re.search(r"backlog #(\d+)", out)
        if not m:
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: фикстурная карточка не завелась\n{out[:400]}")
            return 2
        cid = int(m.group(1))

        # ① БЕЗ причины — отказ, статус не двигается.
        rc, out = run(db, "status", str(cid), "dropped", "--actor", "PROTO")
        case("① dropped БЕЗ причины — ОТКАЗ", rc != 0 and "ПРИЧИНЫ НЕТ" in out,
             f"rc={rc}")
        case("①b статус в базе НЕ сдвинулся (отказ — не только текст)",
             status_of(db, cid) == "open", f"статус: {status_of(db, cid)}")

        # ② С причиной — проходит.
        rc, out = run(db, "status", str(cid), "dropped", "--actor", "PROTO",
                      "--note", "ЗОНД-ПРИЧИНА: предмет заменён прогоном приёмки")
        case("② dropped С причиной — проходит", rc == 0 and status_of(db, cid) == "dropped")

        # ③ Причина видна В СПИСКЕ, не только в истории.
        rc, out = run(db, "list", "--role", "PROTO", "--status", "dropped")
        case("③ причина напечатана в СПИСКЕ", "ЗОНД-ПРИЧИНА" in out)

        # ④ Старый dropped без причины честно говорит «НЕ ЗАПИСАНА».
        con = sqlite3.connect(db)
        con.execute("INSERT INTO backlog (role, title, status) "
                    "VALUES ('PROTO', 'ЗОНД: старое устаревание без причины', 'dropped')")
        con.commit(); con.close()
        rc, out = run(db, "list", "--role", "PROTO", "--status", "dropped")
        case("④ старый dropped без причины печатает «НЕ ЗАПИСАНА», а не молчит",
             "НЕ ЗАПИСАНА" in out)

        # ⑤ Соседние ворота НЕ сломаны: done без критерия по-прежнему отказ.
        con = sqlite3.connect(db)
        cur = con.execute("INSERT INTO backlog (role, title, status) "
                          "VALUES ('PROTO', 'ЗОНД: без критерия', 'open')")
        bare = cur.lastrowid
        con.commit(); con.close()
        rc, out = run(db, "status", str(bare), "done", "--actor", "PROTO")
        case("⑤ сосед цел: done без критерия — отказ по-прежнему",
             rc != 0 and "КРИТЕРИЯ ПРИЁМКИ НЕТ" in out)

        # ⑥ Свободный переход цел: blocked без note проходит (границу не расширили молча).
        rc, out = run(db, "status", str(bare), "blocked", "--actor", "PROTO")
        case("⑥ сосед цел: blocked БЕЗ note по-прежнему проходит", rc == 0)

        # ⑦ Цепочка связей в show: предки ЦЕПОЧКОЙ, потомки строкой.
        con = sqlite3.connect(db)
        g = con.execute("INSERT INTO backlog (role, title, status) VALUES ('PROTO','ЗОНД-дед','open')").lastrowid
        p = con.execute("INSERT INTO backlog (role, title, status, parent_id) VALUES ('PROTO','ЗОНД-отец','open',?)", (g,)).lastrowid
        c = con.execute("INSERT INTO backlog (role, title, status, parent_id) VALUES ('PROTO','ЗОНД-сын','open',?)", (p,)).lastrowid
        con.commit(); con.close()
        rc, out = run(db, "show", str(c))
        case("⑦ show печатает предков ЦЕПОЧКОЙ (отец → дед)",
             f"родитель: #{p} → #{g}" in out)
        rc, out = run(db, "show", str(p))
        case("⑦b show печатает потомков", f"потомки: #{c}" in out)

        # ⑧ Подпись списка называет ФАКТИЧЕСКИЙ состав (карточка #188) — обе стороны:
        #    смесь статусов названа по числам, единственный статус — как прежде.
        con = sqlite3.connect(db)
        con.execute("UPDATE backlog SET status='blocked', blocked_reason='ЗОНД' WHERE id=?", (c,))
        con.commit(); con.close()
        rc, out = run(db, "list", "--role", "PROTO", "--only-mine")
        head = out.splitlines()[0] if out else ""
        case("⑧ подпись при смеси статусов называет состав по числам",
             "open " in head and "blocked " in head and "status=open" not in head, head[:100])
        rc, out = run(db, "list", "--role", "PROTO", "--status", "blocked", "--only-mine")
        head = out.splitlines()[0] if out else ""
        case("⑧b подпись при ЕДИНСТВЕННОМ статусе — как прежде (не врёт в другую сторону)",
             "status=blocked" in head, head[:100])

        # ⑨ Отбор «старше N суток» (карточка #86 ⑧): свежее скрыто, и подпись это говорит.
        rc, out = run(db, "list", "--role", "PROTO", "--only-mine", "--older-than-days", "1")
        case("⑨ свежая фикстурная карточка скрыта отбором «старше суток»",
             f"#{cid} " not in out and f"#{c} " not in out)
        case("⑨b подпись сама говорит «свежие скрыты»", "свежие скрыты" in out)

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}")
    return 0


# ══ МУТАНТЫ: нарочные поломки живого скрипта (с откатом). Не вставший = ВЫЖИВШИЙ. ══
MUTANTS = {
    "M1-ворота-dropped-сняты": lambda s: s.replace(
        'if a.new_status == "dropped" and not note.strip():',
        'if False:'),
    "M2-причина-ушла-из-списка": lambda s: s.replace(
        'if status == "dropped":\n            why', 'if False:\n            why'),
    "M3-потомки-не-печатаются": lambda s: s.replace(
        'if children:', 'if False:'),
    "M4-подпись-снова-врёт-составом": lambda s: s.replace(
        'if len(состав) > 1:', 'if False:'),
    "M5-старше-суток-не-фильтрует": lambda s: s.replace(
        'if getattr(a, "older_than_days", None) is not None:', 'if False:'),
}


def selftest() -> int:
    print("═══ чистый прогон ═══")
    if main() != 0:
        print("🔴 ПРИЁМКА КРАСНАЯ НА ЧИСТОМ — самопроверка невозможна")
        return 1
    survived = 0
    orig = BACKLOG.read_text(encoding="utf-8")
    for name, mut in MUTANTS.items():
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден — нарочная поломка НЕ ВСТАЛА, считаю ВЫЖИВШИМ")
            survived += 1
            continue
        BACKLOG.write_text(bad, encoding="utf-8")
        try:
            print(f"═══ нарочная поломка {name} ═══")
            caught = main() != 0
        finally:
            BACKLOG.write_text(orig, encoding="utf-8")
        print(f"{'✅ поймал' if caught else '🔴 НЕ ПОЙМАЛ'}: {name}")
        survived += 0 if caught else 1
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        sys.exit(selftest())
    sys.exit(main())
