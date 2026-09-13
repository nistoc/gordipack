#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ОТМЕТИТЬ ПЕРЕСОЗДАНИЕ СВОЕЙ РОЛИ — одна строка в role_rebirths (карточка #538, шаг ②).

ЗАЧЕМ. Регламент сжатия хранит «последнюю версию памяти перед КАЖДЫМ пересозданием роли»,
а события «пересоздание» в базе не было вовсе (замер 2026-09-05 07:00 UTC): 18 прошлых отметок
засеяны шагом схемы из записей разговоров. Впредь отметку ставит САМА пересозданная роль
первым делом в новом чате — тогда час отметки равен часу рождения чата, а не часу сборки
промптов (та бывает за часы до того).

⛔ ТОЛЬКО СВОЮ РОЛЬ: имя берётся из MEZO_ROLE и обязано совпасть с --role. Отметка чужой рукой
записала бы событие, которого не видел никто.

⚖️ ЧТО ЭТО НЕ ДЕЛАЕТ: не сворачивает историю (это memory-history-fold.py, отдельным решением
роли), не правит память, не трогает ленту. Повторный вызов в том же чате безвреден: две отметки
ближе часа друг к другу считаются одной (вторая не пишется, инструмент говорит об этом).

    MEZO_ROLE=PROTO python <КОНТУР>/.mezosync/scripts/rebirth-mark.py --role PROTO
    python <КОНТУР>/.mezosync/scripts/rebirth-mark.py --role PROTO --list
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mezo_paths import resolve_db  # noqa: E402
from pathlib import Path  # noqa: E402


# 🪤 13.09 (перед обновлением tapas): файл уходит в пакет — подсказка печатала путь нашей машины.
# У собранного контура звенья образца лежат рядом со скриптами; ищем в тех же четырёх местах,
# что tool() в guard-all.py. Не нашли — первый кандидат: печать назовёт путь, а не промолчит.
def vnext_tool(name):
    here = Path(__file__).resolve().parent
    candidates = [here.parent.parent / "vnext-tools" / name, here / name,
                  here.parent / "vnext" / "prototype" / name,
                  here.parent.parent / "vnext" / "prototype" / name]
    return next((c for c in candidates if c.exists()), candidates[0])


def main() -> int:
    ap = argparse.ArgumentParser(description="Отметить пересоздание СВОЕЙ роли")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None, help="необязателен (R15a): по умолчанию живая база")
    ap.add_argument("--list", action="store_true", help="показать отметки роли, ничего не писать")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    role = a.role.strip().upper()
    db = resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "role_rebirths" not in tables:
        print("⛔ шаг схемы не сведён: таблицы role_rebirths нет — прогони "
              "scripts/migrations/20260905-phoenix-history-archive.py", file=sys.stderr); return 2
    if not conn.execute("SELECT 1 FROM roles WHERE role=?", (role,)).fetchone():
        print(f"⛔ роли {role} нет в реестре — отметку ставить некому (регистр ВЕРХНИЙ)", file=sys.stderr); return 2

    marks = conn.execute("SELECT at, source, noted_by FROM role_rebirths WHERE role=? ORDER BY at", (role,)).fetchall()
    if a.list:
        print(f"📜 отметок пересоздания {role}: {len(marks)}")
        for at, src, by in marks:
            print(f"   {at} UTC · {src} · записал {by}")
        return 0

    env_actor = (os.environ.get("MEZO_ROLE") or "").strip().upper()
    if not env_actor:
        print("⛔ НЕ ЗНАЮ, ЧЬЯ РУКА. Назовись: MEZO_ROLE=<ТВОЯ РОЛЬ> перед вызовом", file=sys.stderr); return 2
    if env_actor != role:
        print(f"⛔ ТОЛЬКО СВОЮ: ты {env_actor}, а отметка — для {role}. Чужое пересоздание видел не ты",
              file=sys.stderr); return 2

    now = conn.execute("SELECT datetime('now')").fetchone()[0]
    recent = conn.execute("SELECT at FROM role_rebirths WHERE role=? AND at >= datetime('now','-1 hour') "
                          "ORDER BY at DESC LIMIT 1", (role,)).fetchone()
    if recent:
        print(f"ℹ️ отметка уже есть: {recent[0]} UTC (меньше часа назад) — вторую не ставлю; "
              f"всего отметок {len(marks)}")
        return 0
    if a.dry_run:
        print(f"⟨ВХОЛОСТУЮ⟩ поставилась бы отметка {role} {now} UTC (источник rebirth-mark); база не тронута")
        return 0
    conn.execute("BEGIN")
    conn.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                 (role, now, "rebirth-mark", env_actor))
    conn.execute("INSERT INTO audit_log(actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                 (env_actor, "rebirth", f"role_rebirths.{role}", f"пересоздание отмечено {now} UTC самой ролью"))
    conn.commit()
    print(f"✅ отмечено пересоздание {role} {now} UTC · всего отметок {len(marks) + 1}")
    print("   свернуть старую историю памяти по регламенту (когда правило встанет в свод):")
    print(f"   MEZO_ROLE={role} python {vnext_tool('memory-history-fold.py').as_posix()} --role {role} --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
