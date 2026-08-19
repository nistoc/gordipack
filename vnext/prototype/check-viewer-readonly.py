#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-viewer-readonly — приёмка ② просмотрщика: служба доказанно НЕ ПИШЕТ в базу.

    python <КОНТУР>/vnext-tools/check-viewer-readonly.py [--api http://127.0.0.1:5177]

Что делает (всё — прогоном, не чтением кода):
  1. PRAGMA integrity_check по базе, которую служба объявила активной, — ДО;
  2. отпечаток файлов базы (.db/-wal/-shm: размер + sha256) — ДО;
  3. прогон ВСЕХ эндпоинтов службы, дважды (второй раз — после паузы, чтобы
     захватить и фоновый пересчёт);
  4. integrity_check и отпечаток — ПОСЛЕ: байт в байт совпали;
  5. /api/health.readOnly — ЗАМЕР самой службы по живому соединению (три замка:
     Mode, query_only, канарейка записи). false = КРАСНЫЙ.

⚖️ ГРАНИЦА: пункт 5 верит замеру службы. Что замер не подделан константой,
   доказывается МУТАЦИЕЙ (подменить Mode в ReadOnlyDb.cs → этот скрипт обязан
   покраснеть на копии) — прогон мутанта входит в приёмку, не в этот скрипт.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINTS = ["health", "sources", "overview", "schema", "roles", "rules",
             "tasks", "messages", "writers"]


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read()


def fingerprint(db: Path) -> str:
    parts = []
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            parts.append(f"{p.name}:{p.stat().st_size}:{h}")
        else:
            parts.append(f"{p.name}:-")
    return " | ".join(parts)


def integrity(db: Path) -> str:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:5177")
    a = ap.parse_args()

    code, raw = fetch(f"{a.api}/api/health")
    health = json.loads(raw)
    db = Path(health["activeDbPath"])
    print(f"служба: {a.api} · база: {db}")

    before_ic, before_fp = integrity(db), fingerprint(db)
    print(f"integrity ДО:  {before_ic}")
    print(f"отпечаток ДО:  {before_fp}")

    ok = 0
    for round_ in (1, 2):
        for ep in ENDPOINTS:
            c, _ = fetch(f"{a.api}/api/{ep}")
            ok += (c == 200)
        if round_ == 1:
            time.sleep(2)
    print(f"эндпоинтов отвечено 200: {ok} из {2 * len(ENDPOINTS)} (два прохода)")

    after_ic, after_fp = integrity(db), fingerprint(db)
    print(f"integrity ПОСЛЕ: {after_ic}")
    print(f"отпечаток ПОСЛЕ: {after_fp}")

    red = []
    if before_ic != "ok" or after_ic != "ok":
        red.append("integrity_check не ok")
    if before_fp != after_fp:
        red.append("ОТПЕЧАТОК БАЗЫ ИЗМЕНИЛСЯ за время прогона — кто-то писал")
    if ok != 2 * len(ENDPOINTS):
        red.append(f"эндпоинты: {ok} из {2 * len(ENDPOINTS)}")
    if health.get("readOnly") is not True:
        red.append(f"health.readOnly = {health.get('readOnly')!r} — ЗАМОК СНЯТ или замер сломан")

    if red:
        print("⛔ КРАСНЫЙ: " + " · ".join(red))
        return 1
    print("✅ read-only доказан: integrity ok до/после · отпечаток не изменился · "
          "health.readOnly=true (замер трёх замков живым соединением)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
