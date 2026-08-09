#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ОБРАТНОЕ ЗАПОЛНЕНИЕ АДРЕСАТОВ ИЗ ТЕЛ — РАЗБОР ПРОЗЫ, А НЕ ОБЪЯВЛЕННОЕ.

СЛОВО ВЛАДЕЛЬЦА 2026-08-08 14:29 UTC: «да, делать обратное заполнение адресатов
из тысячи девятисот старых записок».

⛔ ГЛАВНОЕ СВОЙСТВО: всё, что кладёт этот скрипт, помечается `linked_by='backfill'`.
Объявленное ручкой (`'field'`) он НЕ ТРОГАЕТ и НЕ ПЕРЕЗАПИСЫВАЕТ. Смешать их значило бы
дать догадке выдать себя за сказанное человеком — а разбор прозы ошибается, и его ошибка
обязана быть отличима от объявленного.

ПРАВИЛО РАЗБОРА, ВЫВЕДЕННОЕ ИЗ ЖИВОЙ ПРАКТИКИ КОНТУРА:
    ОБРАЩЕНИЕ  = роли, названные в ПЕРВОЙ строке ДО слова «cc @…»
    КОПИЯ      = роли, названные в хвосте, начинающемся с «cc @…»
Замер, на котором это стоит (08.08): из 145 чужих записок роль названа в 132, а обращаются
к ней в 24 — то есть без отсечения хвоста «в копию» признак показывал бы 83 % ленты
и не был бы фильтром вовсе.

⚖️ ПОТОЛОК, ПЕЧАТАЕТСЯ ВСЕГДА И ПЕРВЫМ: половина ленты не разбирается НИКАК — там
адресация выражена прозой без «собаки», или её нет вовсе. Эти записки не получат адресата,
и витрина их не покажет. Молчание витрины по ним значит «механизму нечем отбирать»,
а НЕ «вам не писали».

⛔ Таблицу `messages` НЕ ТРОГАЕТ ВОВСЕ: ни одной строки не переписывается. Пишет только
в `message_addressee`. Идемпотентен: повторный прогон ничего не портит и не удваивает.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

CC_TAIL = re.compile(r"\bcc\s+@", re.I)
# Строки-цитаты не несут АДРЕСАЦИИ: пересказ чужой шапки адресует не тебе, а в прошлое.
QUOTE = re.compile(r"^\s*>")


def split_head_tail(body: str):
    """→ (шапка ДО «cc @», хвост «в копию»). Цитаты из шапки вырезаны."""
    body = body or ""
    m = CC_TAIL.search(body)
    head, tail = (body[:m.start()], body[m.start():]) if m else (body, "")
    first = next((ln for ln in head.splitlines() if not QUOTE.match(ln) and ln.strip()), "")
    return first, tail


def parse(body: str, roles):
    first, tail = split_head_tail(body)
    to = {r for r in roles if re.search(rf"@{r}\b", first, re.I)}
    cc = {r for r in roles if re.search(rf"@{r}\b", tail, re.I)} - to
    return to, cc


def main() -> int:
    ap = argparse.ArgumentParser(description="адресаты из тел — помеченные как разбор прозы")
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="ЗАПИСАТЬ. Без него — только замер, база не трогается")
    args = ap.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f"⛔ базы нет: {db}")

    mode = "rw" if args.apply else "ro"
    conn = sqlite3.connect(f"file:{str(db).replace(chr(92), '/')}?mode={mode}", uri=True, timeout=10)
    if not args.apply:
        conn.execute("PRAGMA query_only=ON")

    roles = [r[0] for r in conn.execute("SELECT DISTINCT reader_role FROM read_cursors")]
    if not roles:
        sys.exit("⛔ ролей в базе НЕТ — разбирать не по чему. Это НЕ «чисто».")

    # Уже объявленное ручкой — НЕПРИКОСНОВЕННО.
    declared = {m for m, in conn.execute(
        "SELECT DISTINCT message_id FROM message_addressee WHERE linked_by='field'")}

    rows = conn.execute("SELECT id, writer_role, body_md FROM messages ORDER BY id").fetchall()
    plan, skipped_declared, blind, all_hits = [], 0, 0, 0
    for mid, writer, body in rows:
        if mid in declared:
            skipped_declared += 1
            continue
        to, cc = parse(body, roles)
        to.discard(writer)          # автор себе не адресат
        cc.discard(writer)
        if re.search(r"@ALL\b", (body or ""), re.I):
            all_hits += 1
        if not to and not cc:
            blind += 1
            continue
        for r in sorted(to):
            plan.append((mid, r, "to"))
        for r in sorted(cc):
            plan.append((mid, r, "cc"))

    print("=" * 74)
    print("ОБРАТНОЕ ЗАПОЛНЕНИЕ АДРЕСАТОВ — РАЗБОР ПРОЗЫ")
    print("=" * 74)
    print("⚖️ ПОТОЛОК ПЕРВЫМ, А НЕ В КОНЦЕ:")
    print(f"   записок всего .............................. {len(rows)}")
    print(f"   🔴 НЕ РАЗБИРАЮТСЯ НИКАК .................... {blind}"
          f"  ({100.0 * blind / len(rows):.0f} %)")
    print("      — адресация прозой без «собаки» либо её нет вовсе. Витрина их НЕ покажет,")
    print("        и её молчание по ним значит «нечем отбирать», а не «вам не писали».")
    print(f"   объявлено ручкой, НЕ ТРОГАЕМ ............... {skipped_declared}")
    print(f"   записок с «@ALL» ........................... {all_hits}"
          "  — общие; в адресаты НЕ разворачиваются (это отдельное решение)")
    print()
    print(f"будет записано строк ......................... {len(plan)}")
    print(f"   из них обращений ........................... {sum(1 for p in plan if p[2] == 'to')}")
    print(f"   из них копий ............................... {sum(1 for p in plan if p[2] == 'cc')}")
    print(f"   затронуто записок .......................... {len({p[0] for p in plan})}")

    if not args.apply:
        print()
        print("🔍 ЗАМЕР, БАЗА НЕ ТРОНУТА. Записать — тем же вызовом с --apply.")
        conn.close()
        return 0

    msgs_before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    field_before = conn.execute(
        "SELECT COUNT(*) FROM message_addressee WHERE linked_by='field'").fetchone()[0]

    conn.executemany(
        "INSERT OR IGNORE INTO message_addressee (message_id, role, kind, linked_by) "
        "VALUES (?, ?, ?, 'backfill')", plan)
    conn.commit()

    msgs_after = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    field_after = conn.execute(
        "SELECT COUNT(*) FROM message_addressee WHERE linked_by='field'").fetchone()[0]
    back = conn.execute(
        "SELECT COUNT(*) FROM message_addressee WHERE linked_by='backfill'").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    print()
    print(f"записок в таблице messages ... {msgs_before} → {msgs_after}"
          f"   {'✅ НЕ ТРОНУТЫ' if msgs_before == msgs_after else '🔴 ИЗМЕНИЛИСЬ'}")
    print(f"объявленных ручкой .......... {field_before} → {field_after}"
          f"   {'✅ не перезаписаны' if field_before == field_after else '🔴 ПОСТРАДАЛИ'}")
    print(f"разобранных из прозы ........ {back}")
    print(f"целостность ................. {integrity}")
    ok = msgs_before == msgs_after and field_before == field_after and integrity == "ok"
    print()
    print("✅ ЗАПИСАНО" if ok else "🔴 НЕ ПРОШЛО — откатывай из точки отката")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
