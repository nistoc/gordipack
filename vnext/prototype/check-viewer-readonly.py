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
   доказывается НАРОЧНОЙ ПОЛОМКОЙ (подменить Mode в ReadOnlyDb.cs → этот скрипт обязан
   покраснеть на копии) — прогон поломки входит в приёмку, не в этот скрипт.

⬆️ ДОПИСАНО 26.08 (карточка #247, найдено контуром tapas, воспроизведено @COORD):
  0. ОЖИДАЕМАЯ БАЗА СВЕРЯЕТСЯ МАШИНОЙ, а не глазом. 🩸 Оплачено соседями: их служба
     не поднялась («порт занят»), запрос здоровья ответила НАША служба на том же порту,
     и проверка честно доказала read-only ЧУЖОЙ базы. Путь при этом ПЕЧАТАЛСЯ первой
     строкой — его видели и всё равно ошиблись: решение принимает читающий, а читающий
     читает ВЕРДИКТ. Напечатать ≠ проверить.
     Ожидание: --expect-db <путь>; без довода — живая база ЭТОГО контура (от
     расположения скрипта). Совпадение — по нормализованному пути.
  0б. ТРИ ИСХОДА, НЕ ДВА: 0 «доказано» · 1 «ОПРОВЕРГНУТО» (настоящая находка) ·
     2 «НЕ СМОГЛА ПРОВЕРИТЬ» (служба молчит · открыта не та база · база недоступна).
     🩸 Прежде «службы нет» падало трассировкой в 40 строк с тем же кодом 1, что
     настоящая находка, — «не смогла проверить» было слито с «опровергнуто».
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — ожидание по умолчанию выводится, не впечатано


def нормализованный(p) -> str:
    """Пути сравниваются нормализованными: регистр Windows и наклон косой не должны
    превращать ту же базу в «другую»."""
    return str(Path(p).resolve()).replace("\\", "/").lower()

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
    ap.add_argument("--expect-db", default=None,
                    help="какую базу служба ОБЯЗАНА держать открытой; без довода — "
                         "живая база этого контура. Несовпадение = код 2, не «зелёный»")
    a = ap.parse_args()
    ожидание = Path(a.expect_db) if a.expect_db else mezo_paths.live_db()

    # ИСХОД 2 «не смогла проверить» — служба молчит. Человеческой строкой, не трассировкой:
    # прежде 40 строк Python с кодом 1 были неотличимы от настоящей находки.
    try:
        code, raw = fetch(f"{a.api}/api/health")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба не ответила по адресу {a.api}")
        print(f"   причина: {exc.__class__.__name__}: {getattr(exc, 'reason', exc)}")
        print("   это НЕ «read-only нарушен» и НЕ «доказан» — проверять было нечего")
        return 2
    health = json.loads(raw)
    db = Path(health["activeDbPath"])
    print(f"служба: {a.api} · база: {db}")

    # ИСХОД 2 — открыта НЕ ТА база. 🩸 Ровно здесь соседи «доказали» read-only чужой
    # службы: порт был занят нашей, их службы не существовало. Сверка машиной, обе
    # стороны названы; «путь и так печатается» — запрещённый способ пройти (карточка #247).
    if нормализованный(db) != нормализованный(ожидание):
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба держит НЕ ТУ базу.")
        print(f"   открыта:   {db}")
        print(f"   ожидалась: {ожидание}")
        print("   Обычная причина: порт занят ЧУЖОЙ службой (свой просмотрщик не поднялся"
              " «address already in use», а health ответил сосед). Проверять её read-only"
              " — доказывать не тот предмет")
        return 2
    if not db.exists():
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба назвала базу, которой нет на диске: {db}")
        return 2

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
