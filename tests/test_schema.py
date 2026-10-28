# -*- coding: utf-8 -*-
"""Схема базы: самый свежий schema/mezosync_v<N>.sql + шаги сверх него.

Контракт (README, schema_step_order.py): свежая база строится из самого свежего файла
schema/, затем шаги migrations/ накатываются в порядке schema_step_order.STEPS.
Проверяем: все шаги накатываются; повторный прогон ничего не меняет и не дублирует;
итоговый набор таблиц и колонок совпадает со snapshot-файлом.

Snapshot обновляется осознанно, когда схема меняется намеренно:
    python -m pytest tests/test_schema.py --update-snapshots
"""

import json
import sqlite3

import pytest

from conftest import (MIGRATIONS, SNAPSHOTS, clean_env, latest_schema_file, load_module,
                      row_counts, run_python, schema_milestone, schema_shape,
                      schema_sql_dump)

SNAPSHOT_FILE = SNAPSHOTS / "schema.json"

step_order = load_module("schema_step_order")
schema_journal = load_module("schema_journal")


def _fresh_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(latest_schema_file().read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _apply_steps(db, home):
    """Прогнать все STEPS по порядку; вернуть [(шаг, Result)]."""
    env = clean_env(home)
    results = []
    for step in step_order.STEPS:
        res = run_python(MIGRATIONS / f"{step}.py", "--db", db, env=env, cwd=db.parent)
        results.append((step, res))
    return results


@pytest.fixture(scope="module")
def stepped_db(tmp_path_factory):
    """База из свежей схемы + все шаги один раз. Возвращает путь и результаты шагов."""
    base = tmp_path_factory.mktemp("schema")
    db = base / "mezosync.db"
    _fresh_db(db)
    results = _apply_steps(db, base / "home")
    return {"db": db, "home": base / "home", "results": results}


# ── Список шагов ─────────────────────────────────────────────────────────────────


def test_steps_list_is_not_empty_and_unique():
    assert step_order.STEPS, "schema_step_order.STEPS пуст"
    assert len(set(step_order.STEPS)) == len(step_order.STEPS), "в STEPS есть повторы"


@pytest.mark.parametrize("step", step_order.STEPS)
def test_every_listed_step_has_a_file(step):
    assert (MIGRATIONS / f"{step}.py").is_file(), f"шаг {step} назван в STEPS, а файла нет"


def test_not_schema_steps_have_files_and_are_not_in_steps():
    for step in getattr(step_order, "NOT_SCHEMA_STEPS", ()):
        assert (MIGRATIONS / f"{step}.py").is_file(), f"{step}: файла нет в migrations/"
        assert step not in step_order.STEPS, f"{step} одновременно в STEPS и NOT_SCHEMA_STEPS"


def test_step_list_covers_all_migrations_after_base_milestone():
    """Каждый файл migrations/ новее вехи базовой схемы — в STEPS или NOT_SCHEMA_STEPS.

    Тот же контракт init-group.py печатает как «schema_step_order.py отстал от migrations/».
    """
    milestone = schema_milestone(latest_schema_file())
    milestone_files = sorted(MIGRATIONS.glob(f"*-milestone-{milestone}.py"))
    assert milestone_files, f"нет файла шага-вехи *-milestone-{milestone}.py в migrations/"
    base_date = milestone_files[0].name[:8]
    newer = {p.stem for p in MIGRATIONS.glob("*.py") if p.stem[:8].isdigit()
             and p.stem[:8] > base_date}
    known = set(step_order.STEPS) | set(getattr(step_order, "NOT_SCHEMA_STEPS", ()))
    assert newer - known == set(), "шаги без места в schema_step_order.py"


def test_journal_version_of_milestone_and_plain_step():
    assert step_order.journal_version("20260907-milestone-v6") == "v6"
    assert step_order.journal_version("20260913-role-rights-revoked-by") == \
        "20260913-role-rights-revoked-by"


# ── Накатка ─────────────────────────────────────────────────────────────────────


def test_latest_schema_file_builds_a_database(tmp_path):
    db = tmp_path / "base.db"
    _fresh_db(db)
    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "schema_migrations" in names, "в схеме нет журнала шагов schema_migrations"
    finally:
        conn.close()


@pytest.mark.parametrize("index", range(len(step_order.STEPS)),
                         ids=list(step_order.STEPS))
def test_each_step_applies(stepped_db, index):
    step, res = stepped_db["results"][index]
    assert res.returncode == 0, f"шаг {step} отказал\n" + res.explain()
    assert "Traceback" not in res.out, res.explain()


def test_each_step_is_journaled_once(stepped_db):
    conn = sqlite3.connect(str(stepped_db["db"]))
    try:
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    finally:
        conn.close()
    for step in step_order.STEPS:
        name = step_order.journal_version(step)
        assert versions.count(name) == 1, f"{name} в журнале {versions.count(name)} раз"


def test_journal_matches_schema_after_steps(stepped_db):
    """Отпечаток последнего шага в журнале совпадает со структурой базы."""
    conn = sqlite3.connect(str(stepped_db["db"]))
    try:
        ok, why = schema_journal.verify(conn)
    finally:
        conn.close()
    assert ok, why


def test_rerun_of_all_steps_changes_nothing(stepped_db, tmp_path):
    """Повторный прогон: каждый шаг выходит с кодом 0, структура и данные те же."""
    db = tmp_path / "rerun.db"
    src = sqlite3.connect(str(stepped_db["db"]))
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close()
    before_schema = schema_sql_dump(dst)
    before_rows = row_counts(dst)
    dst.close()

    for step, res in _apply_steps(db, tmp_path / "home"):
        assert res.returncode == 0, f"повторный прогон шага {step} отказал\n" + res.explain()
        assert "Traceback" not in res.out, res.explain()

    conn = sqlite3.connect(str(db))
    try:
        assert schema_sql_dump(conn) == before_schema, "повторный прогон изменил структуру"
        assert row_counts(conn) == before_rows, "повторный прогон добавил или удалил строки"
    finally:
        conn.close()


# ── Snapshot итоговой схемы ─────────────────────────────────────────────────────


def _snapshot_payload(db):
    conn = sqlite3.connect(str(db))
    try:
        shape = schema_shape(conn)
    finally:
        conn.close()
    return {
        "_comment": "Итоговая схема свежего контура: файл схемы + шаги STEPS. "
                    "Обновить: python -m pytest tests/test_schema.py --update-snapshots",
        "schema_file": latest_schema_file().name,
        "steps": list(step_order.STEPS),
        **shape,
    }


def test_final_schema_matches_snapshot(stepped_db, update_snapshots):
    actual = _snapshot_payload(stepped_db["db"])
    if update_snapshots or not SNAPSHOT_FILE.exists():
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(json.dumps(actual, ensure_ascii=False, indent=1,
                                            sort_keys=True) + "\n", encoding="utf-8")
        if not update_snapshots:
            pytest.fail(f"snapshot не было — записан {SNAPSHOT_FILE}; проверь и закоммить")
        return
    expected = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    hint = ("\nЕсли схема изменена намеренно — обнови snapshot: "
            "python -m pytest tests/test_schema.py --update-snapshots")
    assert actual["schema_file"] == expected["schema_file"], "сменился файл схемы" + hint
    assert actual["steps"] == expected["steps"], "сменился список шагов" + hint
    missing = sorted(set(expected["tables"]) - set(actual["tables"]))
    added = sorted(set(actual["tables"]) - set(expected["tables"]))
    assert not missing and not added, \
        f"таблицы: пропали {missing}, появились {added}" + hint
    for table, cols in expected["tables"].items():
        assert actual["tables"][table] == cols, f"колонки таблицы {table} разошлись" + hint
    assert actual["views"] == expected["views"], "сменился набор view" + hint
