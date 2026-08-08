#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
МАШИННЫЙ СЛОЙ ПАМЯТИ РОЛИ — прототип (пункт 2.5, карточка #128).

Замысел. Слепок роли сегодня — смесь трёх сортов знания, и хуже всего стареет тот сорт,
который машина знает сама: номера карточек, положение в ленте, git-состояние. Гард находит
11 производных фактов, хранимых руками, — каждый врёт, как только мир сдвинулся.

    Этот блок НЕ ХРАНИТСЯ. Он собирается заново при каждом чтении слепка —
    и потому протухнуть не может ПО ПОСТРОЕНИЮ. Не дисциплиной. Устройством.

Что остаётся роли: намерения, границы, уроки, чего ждёт — то, чего машина не знает.
Слой роли от этого худеет и становится обозримым.

⛔ Живая база — ТОЛЬКО чтение (mode=ro + query_only). Прототип живёт в моей зоне;
врезка в живой read-phoenix — рука координатора и слово владельца (критерий ④).
"""
import argparse
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_DB = r"C:\guts\.atlas\.mezosync\mezosync.db"
CC = re.compile(r"\bcc\s+@.*", re.S)


def ro(db):
    con = sqlite3.connect(f"file:{db.replace(chr(92), '/')}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def main() -> int:
    ap = argparse.ArgumentParser(description="машинный слой памяти роли — собирается, не хранится")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=DEFAULT_DB)
    args = ap.parse_args()
    role = args.role.upper()
    con = ro(args.db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    print("=" * 74)
    print(f"МАШИННЫЙ СЛОЙ · {role} · собран {now:%Y-%m-%d %H:%M} UTC")
    print("  (не хранится нигде — пересобран этим вызовом; хранить его = дать ему врать)")
    print("=" * 74)

    # ── ЗАДАЧИ: то, что слепки хранят руками чаще всего ──────────────────────
    cards = con.execute(
        "SELECT id, status, priority, title, done_when FROM backlog "
        "WHERE role=? AND status NOT IN ('done','dropped') ORDER BY id", (role,)).fetchall()
    no_crit = [c for c in cards if not (c[4] or "").strip()]
    print(f"\n📋 ОТКРЫТЫЕ КАРТОЧКИ: {len(cards)}"
          + (f" · ⛔ БЕЗ КРИТЕРИЯ {len(no_crit)} — их не закрыть, пока не назван" if no_crit else ""))
    for cid, st, prio, title, dw in cards:
        mark = "⛔" if not (dw or "").strip() else "· "
        print(f"  {mark} #{cid:<4} [{st}] {title[:66]}")

    # ── ЛЕНТА: положение и долг ЧИСЛОМ ───────────────────────────────────────
    cur = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                      (role,)).fetchone()
    head = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    if cur:
        n, kb = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(length(body_md)),0)/1024 FROM messages WHERE id > ?",
            (cur[0],)).fetchone()
        print(f"\n📬 ЛЕНТА: отметка #{cur[0]} · голова #{head} · долг {n} записок ({kb} КБ)")
        # обращения лично к роли в непрочитанном — по шапке БЕЗ списка «в копию»
        hits = []
        for mid, w, b in con.execute(
                "SELECT id, writer_role, body_md FROM messages WHERE id > ? AND writer_role <> ?",
                (cur[0], role)):
            first = CC.sub(" ", b or "").split("\n")[0]
            if re.search(rf"@{role}\b", first):
                hits.append((mid, w))
        print(f"   обращений лично (не «в копию»): {len(hits)}"
              + ("  → " + " ".join(f"#{m}[{w}]" for m, w in hits[-8:]) if hits else ""))

    # ── СВОЙ СЛЕД: последняя записка и слепок ────────────────────────────────
    last = con.execute(
        "SELECT id, timestamp FROM messages WHERE writer_role=? ORDER BY id DESC LIMIT 1",
        (role,)).fetchone()
    if last:
        print(f"\n📝 ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА: #{last[0]} от {last[1][:16]} UTC"
              "  ← ЧИТАТЬ ПЕРВОЙ: слепок сохраняется ДО неё, отозванное там живёт как факт")
    for sec, ln, at in con.execute(
            "SELECT section, length(body), saved_at FROM phoenix WHERE role=? ORDER BY section",
            (role,)):
        print(f"   слепок §{sec:<9} {ln:>6} зн. · сохранён {at[:16]}")

    # ── ПРАВИЛА: что сдвинулось после сохранения слепка ──────────────────────
    saved = con.execute("SELECT MIN(saved_at) FROM phoenix WHERE role=?", (role,)).fetchone()[0]
    if saved:
        fresh = con.execute(
            "SELECT rule_key, version FROM rules WHERE updated_at > ? ORDER BY updated_at DESC",
            (saved,)).fetchall()
        print(f"\n📜 ПРАВИЛА, ПРАВЛЕНЫЕ ПОСЛЕ СТАРЕЙШЕЙ СЕКЦИИ СЛЕПКА: {len(fresh)}")
        for k, v in fresh[:10]:
            print(f"   {k} v{v}")
        if len(fresh) > 10:
            print(f"   … ещё {len(fresh) - 10}")

    print("\n" + "-" * 74)
    print("⚖️ ГРАНИЦА: блок знает БАЗУ, но не диск — git-состояние и живость сервисов")
    print("   сюда войдут отдельными сборщиками; пока их тут НЕТ, и это сказано, а не скрыто.")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
