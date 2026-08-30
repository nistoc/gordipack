# -*- coding: utf-8 -*-
"""20260828-role-skill-expiry — НАСТУПЛЕНИЕ условия протухания умения СТАНОВИТСЯ ПОЛЕМ.

ПОВОД (П⑥ пула «Роли не забывают»). Паёк новой сессии несёт умения роли, «у которых
условие протухания не наступило». Условие (until_cond) — свободный текст, машиной
не вычисляется; НАСТУПЛЕНИЕ фиксирует рука (роли или проверки сроков годности, заход
2.3) — а фиксировать некуда: поля нет. Напоминание о протухшем умении вреднее
отсутствия — паёк обязан уметь фильтровать.

ЧТО ДОБАВЛЯЕТ: role_skill.expired_at (час наступления, UTC) + expired_why (чем
подтверждено). Протухшее умение НЕ удаляется — история остаётся видимой, фильтруют
читатели (WHERE expired_at IS NULL).
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import record_step, verify  # noqa: E402

VERSION = "20260828-role-skill-expiry"
ALTERS = ["ALTER TABLE role_skill ADD COLUMN expired_at TEXT",
          "ALTER TABLE role_skill ADD COLUMN expired_why TEXT"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import mezo_paths
    db = mezo_paths.resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(role_skill)")]
    have = "expired_at" in cols and "expired_why" in cols
    print(f"база: {db}")
    print(f"столбцы expired_at/expired_why: {'УЖЕ ЕСТЬ' if have else 'нет — будут добавлены'}")
    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута.")
        return
    logged = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?",
                          (VERSION,)).fetchone()
    if have and logged:
        print("\n⚖️ Всё есть и след есть — шаг ничего не меняет.")
        return
    if have and not logged:
        fp = record_step(conn, VERSION, "role_skill.expired_at/expired_why: заведены ранее "
                         "без журнала; след восстановлен задним числом", backdated=True)
        conn.commit()
        print(f"✅ След восстановлен. отпечаток: {fp}")
        return
    conn.execute("BEGIN")
    for i, stmt in enumerate(ALTERS):
        col = stmt.rsplit(" ", 2)[-2]
        if col not in cols:
            conn.execute(stmt)
    fp = record_step(
        conn, VERSION,
        "role_skill.expired_at + expired_why: наступление условия протухания умения — "
        "ПОЛЕМ, не прозой (П⑥ пула: паёк фильтрует протухшее; напоминание о протухшем "
        "умении вреднее отсутствия). Умение не удаляется — история видима")
    conn.commit()
    print(f"\n✅ ВРЕЗАНО. отпечаток схемы: {fp}")
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print("целостность:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    cols2 = [r[1] for r in conn.execute("PRAGMA table_info(role_skill)")]
    print(f'{"✅" if "expired_at" in cols2 and "expired_why" in cols2 else "🔴"} '
          f'столбцы на месте: {", ".join(cols2)}')


if __name__ == '__main__':
    main()
