#!/usr/bin/env python
# SURFACES: memory
# -*- coding: utf-8 -*-
r"""СВЕРНУТЬ ИСТОРИЮ ВЕРСИЙ СВОЕЙ ПАМЯТИ: старое — в архивную таблицу, ничего не удаляя.

ПРЕДМЕТ (карточка #538, шаг ② регламента сжатия; слово владельца 2026-09-05 06:02 UTC
«делаем C … неразрушительно»). История версий памяти хранит каждое сохранение каждого
раздела дословно — 440 версий · 6,92 млн знаков на 05.09 07:01 UTC, и растёт с каждым
сохранением. Читают её редко (возврат версии, проверка инвариантов, сборка v-next), а место
и дамп она занимает всегда.

ПРАВИЛО — из текста регламента (COORD, карточка #538), инструмент его не придумывает:
    из версий СТАРШЕ порога (7 суток) остаются
       · последняя версия ПЕРЕД КАЖДЫМ пересозданием роли (таблица role_rebirths),
       · последняя версия вообще (по каждому разделу);
    всё моложе порога остаётся как есть;
    прочие ПЕРЕНОСЯТСЯ в phoenix_history_archive под своим же номером — не удаляются.

⛔ РОЛЬ СВОРАЧИВАЕТ ТОЛЬКО СВОЮ ИСТОРИЮ. Слово владельца 2026-09-04 13:41 UTC: «только свою,
остальные сами». Чужую можно посчитать (--dry-run), перенести — нет.

ПОТЕРЬ НОЛЬ ПО ПОСТРОЕНИЮ И ПО ОТПЕЧАТКУ: перенос — INSERT в архив и DELETE из истории
в ОДНОЙ транзакции; до и после считается отпечаток ОБЪЕДИНЕНИЯ (история ∪ архив) по роли,
и если он разошёлся — транзакция откатывается и инструмент падает словами. --unfold
возвращает все унесённые версии роли под прежними номерами.

⚠️ ГДЕ ПРАВИЛО МОЛЧИТ: если у роли нет ни одной отметки пересоздания, «последняя перед
пересозданием» не хранится вовсе — инструмент говорит это вслух числом, а не молча.

Зовут так:
    MEZO_ROLE=PROTO python C:/guts/.atlas/vnext-tools/memory-history-fold.py --role PROTO --dry-run
    MEZO_ROLE=PROTO python C:/guts/.atlas/vnext-tools/memory-history-fold.py --role PROTO
    MEZO_ROLE=PROTO python C:/guts/.atlas/vnext-tools/memory-history-fold.py --role PROTO --unfold
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны

ПОРОГ_СУТОК = 7
ПРАВИЛО = "regl-538-②: старше 7 сут, не последняя перед пересозданием, не последняя вообще"


def отпечаток(conn, роль: str) -> str:
    """Отпечаток ОБЪЕДИНЕНИЯ история ∪ архив по роли: id · раздел · час · тело."""
    h = hashlib.sha256()
    rows = conn.execute(
        "SELECT id, section, saved_at, body FROM phoenix_history WHERE role=? "
        "UNION ALL SELECT id, section, saved_at, body FROM phoenix_history_archive WHERE role=? "
        "ORDER BY 1", (роль, роль)).fetchall()
    for i, s, t, b in rows:
        h.update(f"{i}\x1f{s}\x1f{t}\x1f".encode("utf-8")); h.update(b.encode("utf-8")); h.update(b"\x1e")
    return h.hexdigest()[:16]


def посчитать(conn, роль: str):
    """Что хранится и что уедет — списками id, по правилу регламента."""
    порог = conn.execute(f"SELECT datetime('now','-{ПОРОГ_СУТОК} days')").fetchone()[0]
    отметки = [r[0] for r in conn.execute(
        "SELECT at FROM role_rebirths WHERE role=? ORDER BY at", (роль,))]
    rows = conn.execute(
        "SELECT id, section, saved_at, body_chars FROM phoenix_history WHERE role=? "
        "ORDER BY section, saved_at, id", (роль,)).fetchall()
    по_разделу: dict[str, list] = {}
    for r in rows:
        по_разделу.setdefault(r[1], []).append(r)
    молодые, хранимые_последняя, хранимые_перед, уедет = [], [], [], []
    for раздел, vs in по_разделу.items():
        keep = {vs[-1][0]: "последняя вообще"}
        for t in отметки:
            before = [v for v in vs if v[2] < t]
            if before and before[-1][0] not in keep:
                keep[before[-1][0]] = f"последняя перед пересозданием {t}"
        for v in vs:
            if v[2] >= порог:
                молодые.append(v)
            elif v[0] in keep:
                (хранимые_последняя if keep[v[0]] == "последняя вообще" else хранимые_перед).append(v)
            else:
                уедет.append(v)
    return порог, отметки, rows, молодые, хранимые_последняя, хранимые_перед, уедет


def печать_счёта(роль, порог, отметки, rows, молодые, посл, перед, уедет):
    print(f"📊 {роль}: версий {len(rows)} · порог {порог} UTC · отметок пересоздания {len(отметки)}")
    print(f"   моложе {ПОРОГ_СУТОК} суток ............ {len(молодые)}  (не трогаются)")
    print(f"   старые, последняя вообще ..... {len(посл)}  (хранятся)")
    print(f"   старые, перед пересозданием .. {len(перед)}  (хранятся)")
    print(f"   УЕДЕТ В АРХИВ ................ {len(уедет)}  · {sum(v[3] for v in уедет)} знаков")
    if not отметки:
        print("   ⚠️ ОТМЕТОК ПЕРЕСОЗДАНИЯ У РОЛИ НЕТ: «последняя перед пересозданием» не хранится "
              "вовсе — не потому, что правило так велит, а потому, что базе нечем его исполнить. "
              "Заведи отметку (role_rebirths) прежде, чем сворачивать.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Свернуть историю версий СВОЕЙ памяти в архивную таблицу")
    ap.add_argument("--role", required=True, help="чья история; только своя (MEZO_ROLE)")
    ap.add_argument("--db", default=None, help="необязателен: по умолчанию живая база")
    ap.add_argument("--dry-run", action="store_true", help="только посчитать, ни байта не писать")
    ap.add_argument("--unfold", action="store_true", help="вернуть ВСЕ унесённые версии роли обратно")
    a = ap.parse_args()
    роль = a.role.strip().upper()
    db = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    if not db.exists():
        print(f"⛔ базы нет: {db}", file=sys.stderr); return 2

    conn = sqlite3.connect(str(db))
    есть = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "phoenix_history_archive" not in есть or "role_rebirths" not in есть:
        print("⛔ шаг схемы не сведён: нет phoenix_history_archive / role_rebirths — прогони "
              "scripts/migrations/20260905-phoenix-history-archive.py", file=sys.stderr); return 2
    if not conn.execute("SELECT 1 FROM phoenix_history WHERE role=? LIMIT 1", (роль,)).fetchone() and \
       not conn.execute("SELECT 1 FROM phoenix_history_archive WHERE role=? LIMIT 1", (роль,)).fetchone():
        print(f"⛔ у роли {роль} нет ни одной версии ни в истории, ни в архиве — сворачивать нечего "
              "(проверь имя роли: регистр ВЕРХНИЙ)", file=sys.stderr); return 2

    # ⚖️ ЧЬЯ РУКА. MEZO_ROLE можно подменить — граница названа честно; но подмена оставляет
    # след в летописи под чужим именем, а не «само собой».
    из_среды = (os.environ.get("MEZO_ROLE") or "").strip().upper()
    if not a.dry_run:
        if not из_среды:
            print("⛔ НЕ ЗНАЮ, ЧЬЯ РУКА. Назовись: MEZO_ROLE=<ТВОЯ РОЛЬ> перед вызовом; "
                  "посчитать без имени можно (--dry-run), перенести — нет", file=sys.stderr); return 2
        if из_среды != роль:
            print(f"⛔ ТОЛЬКО СВОЮ: ты {из_среды}, а история — {роль}. Слово владельца 2026-09-04 "
                  "13:41 UTC «только свою, остальные сами». Чужую можно посчитать: --dry-run",
                  file=sys.stderr); return 2

    до = отпечаток(conn, роль)

    if a.unfold:
        rows = conn.execute("SELECT id FROM phoenix_history_archive WHERE role=?", (роль,)).fetchall()
        if not rows:
            print(f"ℹ️ в архиве у {роль} ничего нет — возвращать нечего"); return 0
        ids = [r[0] for r in rows]
        занято = conn.execute(
            f"SELECT id FROM phoenix_history WHERE id IN ({','.join('?'*len(ids))})", ids).fetchall()
        if занято:
            print(f"⛔ ВЕРНУТЬ НЕЛЬЗЯ БЕЗ РАЗБОРА: номера {[r[0] for r in занято][:5]}… уже заняты "
                  "в истории другой версией — номер переиспользован. Разбирать рукой", file=sys.stderr)
            return 3
        if a.dry_run:
            print(f"⟨ВХОЛОСТУЮ⟩ вернулось бы {len(ids)} версий {роль}; база не тронута"); return 0
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO phoenix_history(id, role, section, body, body_chars, saved_at, actor, reason, prev_chars) "
            "SELECT id, role, section, body, body_chars, saved_at, actor, reason, prev_chars "
            "FROM phoenix_history_archive WHERE role=?", (роль,))
        conn.execute("DELETE FROM phoenix_history_archive WHERE role=?", (роль,))
        conn.execute("INSERT INTO audit_log(actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                     (из_среды, "unfold_history", f"phoenix_history.{роль}",
                      f"возвращено из архива {len(ids)} версий; отпечаток объединения {до}"))
        после = отпечаток(conn, роль)
        if после != до:
            conn.rollback()
            print(f"⛔ ОТПЕЧАТОК РАЗОШЁЛСЯ ({до} → {после}) — ОТКАЧЕНО, ни байта не изменено", file=sys.stderr)
            return 4
        conn.commit()
        print(f"✅ возвращено {len(ids)} версий {роль} под прежними номерами · отпечаток {до} совпал")
        return 0

    порог, отметки, rows, молодые, посл, перед, уедет = посчитать(conn, роль)
    печать_счёта(роль, порог, отметки, rows, молодые, посл, перед, уедет)
    if not уедет:
        print("ℹ️ уносить нечего"); return 0
    if a.dry_run:
        print(f"⟨ВХОЛОСТУЮ⟩ база не тронута; отпечаток объединения {до}"); return 0

    ids = [v[0] for v in уедет]
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO phoenix_history_archive(id, role, section, body, body_chars, saved_at, actor, reason, "
        "prev_chars, moved_by, rule) SELECT id, role, section, body, body_chars, saved_at, actor, reason, "
        f"prev_chars, ?, ? FROM phoenix_history WHERE id IN ({','.join('?'*len(ids))})",
        [из_среды, ПРАВИЛО] + ids)
    conn.execute(f"DELETE FROM phoenix_history WHERE id IN ({','.join('?'*len(ids))})", ids)
    conn.execute("INSERT INTO audit_log(actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                 (из_среды, "fold_history", f"phoenix_history.{роль}",
                  f"унесено в архив {len(ids)} версий · {sum(v[3] for v in уедет)} знаков; хранимых старых "
                  f"{len(посл)+len(перед)}, молодых {len(молодые)}; отпечаток объединения {до}"))
    после = отпечаток(conn, роль)
    if после != до:
        conn.rollback()
        print(f"⛔ ОТПЕЧАТОК РАЗОШЁЛСЯ ({до} → {после}) — ОТКАЧЕНО, ни байта не изменено", file=sys.stderr)
        return 4
    conn.commit()
    ост = conn.execute("SELECT COUNT(*) FROM phoenix_history WHERE role=?", (роль,)).fetchone()[0]
    арх = conn.execute("SELECT COUNT(*) FROM phoenix_history_archive WHERE role=?", (роль,)).fetchone()[0]
    print(f"✅ унесено {len(ids)} версий {роль} · в истории осталось {ост} · в архиве {арх} · "
          f"отпечаток объединения {до} совпал (потерь ноль)")
    print("   вернуть всё: тот же вызов с --unfold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
