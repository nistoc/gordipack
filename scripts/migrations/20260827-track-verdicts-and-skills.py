# -*- coding: utf-8 -*-
"""20260827-track-verdicts-and-skills — ВЕРДИКТЫ ЗАКРЫТИЯ ПУЛА + СКИЛЛЫ ПОД ЗАДАЧУ.

ПОВОД (план пула «Роли не забывают», части П④ и П⑥; слово владельца 27.08 18:33 UTC —
новый порядок: один пул на весь контур). Два замера, оба 27.08:
  · оценка документации, заведённая ПОЛЕМ НА КАЖДОЙ КАРТОЧКЕ, — гарантированный новый
    «пишется-не-читается»: у нас четыре механизма с нулём вызовов за 1724 записки.
    Оценка живёт ШАГОМ ЗАКРЫТИЯ пула — и ей нужна таблица вердиктов;
  · паёк новой сессии должен нести «скиллы под задачу» — полю негде жить, кроме пула.

ЧТО ЗАВОДИТ:
  · таблица track_verdicts: вердикт роли при закрытии пула. kind ∈ (documentation,
    process): первое — оценка документации по итогам задачи (П④), второе — сырьё канала
    проблем процесса → issues образца (П⑤). «Чисто» — тоже вердикт, явный: молчание
    роли и «нареканий нет» обязаны различаться (класс «одно ничего на две беды»);
  · столбец tracks.skills: скиллы под задачу пула, заполняет заводящий пул. Пустое
    поле паёк называет словами («скиллы под пул не названы»), а не молчит.

ЧЕГО НЕ ДЕЛАЕТ: не правит track.py/backlog.py — код идёт отдельной правкой тем же днём
(таблица без кода безвредна, код без таблицы мёртв ⇒ миграция ПЕРВОЙ). Ворота «закрытие
без полного набора вердиктов отказывает поимённо» живут в коде закрытия, не в схеме:
состав участников вычисляется ЗАМЕРОМ по карточкам и событиям, схеме он неизвестен.
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

VERSION = "20260827-track-verdicts-and-skills"

# DDL — СПИСОК операторов, не текст с разделителями (мина со split(";") оплачена
# шагом 20260823: точка с запятой в КОММЕНТАРИИ рвала оператор пополам).
DDL = [
    """
    CREATE TABLE IF NOT EXISTS track_verdicts (
        id          INTEGER PRIMARY KEY,
        track_id    TEXT NOT NULL REFERENCES tracks(track_id),
        role        TEXT NOT NULL,
        -- documentation: оценка документации по итогам задачи (П④)
        -- process: проблема процесса или «чисто» — сырьё канала issues (П⑤)
        kind        TEXT NOT NULL CHECK (kind IN ('documentation', 'process')),
        -- краткий вердикт: 'чисто' | 'обновить документацию X' | тело проблемы одной строкой
        verdict     TEXT NOT NULL CHECK (TRIM(verdict) <> ''),
        -- развёрнутое тело, если краткого мало (для process — замер и предложение)
        body        TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_track_verdicts
        ON track_verdicts(track_id, role, kind)
    """,
]
# ⛔ БЕЗ UNIQUE(track_id, role, kind) НАМЕРЕННО: роль вправе принести ДВА вердикта
# process (две разные проблемы). «Полный набор» меряет код закрытия по СОСТАВУ
# участников, а не схема по количеству строк.

ALTER_SKILLS = "ALTER TABLE tracks ADD COLUMN skills TEXT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    import mezo_paths
    db = mezo_paths.resolve_db(a.db, __file__)
    conn = sqlite3.connect(str(db))

    have_table = bool(conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='track_verdicts'"
    ).fetchone())
    have_col = any(r[1] == "skills" for r in conn.execute("PRAGMA table_info(tracks)"))
    print(f"база: {db}")
    print(f"таблица track_verdicts: {'УЖЕ ЕСТЬ' if have_table else 'нет — будет заведена'}")
    print(f"столбец tracks.skills:  {'УЖЕ ЕСТЬ' if have_col else 'нет — будет добавлен'}")

    if a.dry_run:
        print("\n⟨ВХОЛОСТУЮ⟩ база не тронута. Чтобы применить, прогони без --dry-run.")
        return

    logged = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone()

    if have_table and have_col and logged:
        print("\n⚖️ Всё есть и след в журнале есть — шаг ничего не меняет.")
        n = conn.execute("SELECT COUNT(*) FROM track_verdicts").fetchone()[0]
        print(f"вердиктов в таблице: {n}")
        return

    if have_table and have_col and not logged:
        print("\n🪤 Схема ЕСТЬ, а записи в журнале НЕТ — схема ушла вперёд журнала.")
        fp = record_step(
            conn, VERSION,
            "track_verdicts + tracks.skills: заведены ранее без записи в журнале; след "
            "восстановлен задним числом, не скрыт пересозданием",
            backdated=True)
        conn.commit()
        print(f"✅ След восстановлен задним числом. отпечаток схемы: {fp}")
        ok, why = verify(conn)
        print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
        return

    conn.execute("BEGIN")
    # НЕ executescript: неявный commit рвал бы транзакцию с журналом (оплачено 20.08).
    if not have_table:
        for stmt in DDL:
            conn.execute(stmt)
    if not have_col:
        conn.execute(ALTER_SKILLS)
    fp = record_step(
        conn, VERSION,
        "track_verdicts (вердикты закрытия пула: documentation/П④ + process/П⑤, «чисто» — "
        "явный вердикт) и tracks.skills (скиллы под задачу для пайка/П⑥). План пула "
        "«Роли не забывают», слово владельца 27.08 18:33 UTC. Полный набор вердиктов "
        "меряет КОД закрытия по составу участников (замером) — схеме состав неизвестен, "
        "потому UNIQUE нет намеренно")
    conn.commit()
    print(f"\n✅ ВРЕЗАНО. отпечаток схемы: {fp}")
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} проверка журнала: {why}')
    print("целостность:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    # приёмка запросами, не отчётом (норма UPGRADE ⑥):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(track_verdicts)")]
    print(f"✅ столбцы track_verdicts: {', '.join(cols)}")
    has_sk = any(r[1] == "skills" for r in conn.execute("PRAGMA table_info(tracks)"))
    print(f'{"✅" if has_sk else "🔴"} tracks.skills на месте')


if __name__ == '__main__':
    main()
