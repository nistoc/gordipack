# -*- coding: utf-8 -*-
"""init-group.py целиком во временной папке: код выхода, база, файлы, повторный запуск.

Контракт — из докстроки и комментариев init-group.py:
  · без --roles и с координатором не из --roles — отказ кодом 2 ДО записи на диск;
  · свежая сборка — код 0, последняя строка итога «🎉 Группа «<имя>» готова»;
  · база: схема свежего файла + шаги STEPS, вехa и журнал, роли в реестре и отметках;
  · рядом: копии scripts/ и migrations/, заготовки, зеркало правил, приложения правил,
    каталоги coordination/ и bridges/;
  · повторный запуск по существующей базе спрашивает «Перезаписать? (y/N)»:
    не «y» — «Отмена.» и код 0, база не тронута; «y» — база собирается заново.
"""

import hashlib
import json
import sqlite3

import pytest

from conftest import (DEFAULT_ROLES, REPO_ROOT, SCRIPTS, SNAPSHOTS, latest_schema_file,
                      load_module, run_init_group, schema_milestone, schema_shape)

step_order = load_module("schema_step_order")
schema_journal = load_module("schema_journal")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connect(container):
    return sqlite3.connect(str(container / ".mezosync" / "mezosync.db"))


def _universal_rule_keys():
    """Ключи правил, которые кладёт rules/universal.sql на свежую схему."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(latest_schema_file().read_text(encoding="utf-8"))
        conn.executescript((REPO_ROOT / "rules" / "universal.sql").read_text(encoding="utf-8"))
        return {r[0] for r in conn.execute("SELECT rule_key FROM rules")}
    finally:
        conn.close()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Одна свежая сборка на модуль: (папка контура, Result)."""
    base = tmp_path_factory.mktemp("init")
    container = base / "circuit"
    container.mkdir()
    res = run_init_group(container, name="alpha", home=base / "home")
    return container, res


# ── Отказы до записи на диск ─────────────────────────────────────────────────────


def test_refuses_without_roles(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, roles=None, cwd=tmp_path, home=tmp_path / "home")
    assert res.returncode == 2, res.explain()
    assert "--roles" in res.out
    assert not container.exists(), "отказ обязан случиться до создания каталога"


def test_refuses_bare_roles_flag(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, roles=(), cwd=tmp_path, home=tmp_path / "home")
    assert res.returncode == 2, res.explain()
    assert not container.exists()


def test_refuses_coordinator_outside_roles(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, "--coordinator", "ghost", roles=("a", "b"),
                         cwd=tmp_path, home=tmp_path / "home")
    assert res.returncode == 2, res.explain()
    assert "GHOST" in res.out, "отказ называет координатора, приведённого к верхнему регистру"
    assert not container.exists()


# ── Свежая сборка: вывод и код выхода ────────────────────────────────────────────


def test_fresh_build_exit_code_and_verdict(built):
    _, res = built
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out, res.explain()
    assert "🎉 Группа «alpha» готова" in res.stdout, res.explain()
    assert "собрана с отказами" not in res.stdout, res.explain()
    assert "СБОРКА НЕ ПРИНЯТА" not in res.stdout, res.explain()


def test_fresh_build_names_latest_schema_file(built):
    _, res = built
    assert f"Схема применена: {latest_schema_file().name}" in res.stdout


# ── Свежая сборка: база ──────────────────────────────────────────────────────────


def test_database_is_healthy_and_in_wal_mode(built):
    container, _ = built
    conn = _connect(container)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_meta_records_name_and_rule_sets(built):
    container, _ = built
    conn = _connect(container)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    finally:
        conn.close()
    assert meta.get("group_name") == "alpha"
    assert json.loads(meta["pack_rule_sets"]) == ["universal"]
    for key in ("template_source", "template_commit", "template_copied_at",
                "template_files_sha"):
        assert meta.get(key), f"meta.{key} пуст"
    sha = json.loads(meta["template_files_sha"])
    assert "write-message.py" in sha
    assert any(k.startswith("migrations/") for k in sha), "нет отпечатков шагов схемы"


def test_roles_registered_alive_with_cursors(built):
    container, _ = built
    conn = _connect(container)
    try:
        roles = {r[0]: r[1:] for r in conn.execute(
            "SELECT role, lifecycle, in_roster, lifecycle_reason FROM roles")}
        cursors = dict(conn.execute("SELECT reader_role, last_read_id FROM read_cursors"))
    finally:
        conn.close()
    assert set(roles) == set(DEFAULT_ROLES)
    assert cursors == {r: 0 for r in DEFAULT_ROLES}
    for role, (lifecycle, in_roster, reason) in roles.items():
        assert lifecycle == "alive" and in_roster == 1, role
        is_coord = "координатор" in (reason or "")
        assert is_coord == (role == DEFAULT_ROLES[0]), \
            f"слово «координатор» в причине должно быть ровно у первой роли, а у {role}: {reason}"


def test_schema_version_is_base_milestone_plus_all_steps(built):
    container, _ = built
    conn = _connect(container)
    try:
        version, after = conn.execute(
            "SELECT version, steps_after_milestone FROM schema_version").fetchone()
        journal = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        ok, why = schema_journal.verify(conn)
    finally:
        conn.close()
    assert version == schema_milestone(latest_schema_file())
    assert after == len(step_order.STEPS)
    for step in step_order.STEPS:
        assert journal.count(step_order.journal_version(step)) == 1, step
    assert ok, why


def test_schema_matches_snapshot(built):
    """init-group.py строит ту же схему, что закреплена в tests/snapshots/schema.json."""
    container, _ = built
    expected = json.loads((SNAPSHOTS / "schema.json").read_text(encoding="utf-8"))
    conn = _connect(container)
    try:
        actual = schema_shape(conn)
    finally:
        conn.close()
    assert actual["tables"] == expected["tables"]
    assert actual["views"] == expected["views"]


def test_universal_rules_loaded(built):
    container, _ = built
    conn = _connect(container)
    try:
        keys = {r[0] for r in conn.execute("SELECT rule_key FROM rules")}
    finally:
        conn.close()
    missing = _universal_rule_keys() - keys
    assert not missing, f"правила universal.sql не попали в базу: {sorted(missing)}"


def test_identity_memory_seeded_for_every_role(built):
    container, _ = built
    conn = _connect(container)
    try:
        seeded = {r[0] for r in conn.execute(
            "SELECT role FROM phoenix WHERE section='identity' AND length(body) > 0")}
    finally:
        conn.close()
    assert seeded == set(DEFAULT_ROLES)


# ── Свежая сборка: файлы рядом с базой ───────────────────────────────────────────


def test_tools_copied_byte_for_byte(built):
    container, _ = built
    tools = container / ".mezosync" / "scripts"
    for src in SCRIPTS.glob("*.py"):
        dst = tools / src.name
        if src.name == "init-group.py":
            assert not dst.exists(), "сборщик не должен ехать в контур"
            continue
        assert dst.is_file(), f"нет {src.name} в контуре"
        assert _sha(dst) == _sha(src), f"{src.name} в контуре отличается от пакета"
    for src in (SCRIPTS / "migrations").glob("*.py"):
        assert (tools / "migrations" / src.name).is_file(), f"нет шага {src.name}"


def test_templates_mirror_annex_and_dirs_created(built):
    container, _ = built
    mz = container / ".mezosync"
    tpl = {p.name for p in (REPO_ROOT / "templates").glob("*.md")}
    assert {p.name for p in (mz / "templates").glob("*.md")} == tpl
    mirror = mz / "generated" / "sync.rules.md"
    assert mirror.is_file() and mirror.stat().st_size > 0, "зеркало правил не собрано"
    annex = {p.name for p in (REPO_ROOT / "rules" / "annex").glob("*.md")}
    assert {p.name for p in (mz / "rules-annex").glob("*.md")} == annex
    assert (container / "coordination").is_dir()
    assert (container / "bridges").is_dir()


# ── Флаги ─────────────────────────────────────────────────────────────────────────


def test_roles_are_uppercased_and_deduplicated(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, roles=("lead", "dev", "LEAD"), cwd=tmp_path,
                         home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    conn = _connect(container)
    try:
        roles = sorted(r[0] for r in conn.execute("SELECT role FROM roles"))
    finally:
        conn.close()
    assert roles == ["DEV", "LEAD"]


def test_coordinator_flag_picks_the_coordinator(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, "--coordinator", "dev", roles=("lead", "dev"),
                         cwd=tmp_path, home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    conn = _connect(container)
    try:
        reasons = dict(conn.execute("SELECT role, lifecycle_reason FROM roles"))
    finally:
        conn.close()
    assert "координатор" in reasons["DEV"]
    assert "координатор" not in reasons["LEAD"]


def test_domain_preset_is_loaded_and_recorded(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, "--domain", "data-platform", cwd=tmp_path,
                         home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    conn = _connect(container)
    try:
        sets = json.loads(conn.execute(
            "SELECT value FROM meta WHERE key='pack_rule_sets'").fetchone()[0])
    finally:
        conn.close()
    assert sets == ["universal", "data-platform"]


def test_unknown_domain_is_skipped_not_fatal(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, "--domain", "no-such-domain", cwd=tmp_path,
                         home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    assert "no-such-domain" in res.stdout
    conn = _connect(container)
    try:
        sets = json.loads(conn.execute(
            "SELECT value FROM meta WHERE key='pack_rule_sets'").fetchone()[0])
    finally:
        conn.close()
    assert sets == ["universal"]


def test_relative_path_resolves_against_cwd(tmp_path):
    """Относительный --path — от текущего каталога вызова (карточка #608 в init-group.py)."""
    from conftest import INIT_GROUP, run_python
    work = tmp_path / "work"
    work.mkdir()
    res = run_python(INIT_GROUP, "--name", "rel", "--path", "proj/.mezosync",
                     "--roles", "coord", cwd=work, home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    db = work / "proj" / ".mezosync" / "mezosync.db"
    assert db.is_file()
    assert "собрана с отказами" not in res.stdout, res.explain()
    conn = sqlite3.connect(str(db))
    try:
        base = conn.execute("SELECT value FROM meta WHERE key='pack_rules_base'").fetchone()
    finally:
        conn.close()
    assert base and base[0], "опора правил пакета не записана при относительном --path"


# ── Повторный запуск по существующей базе ────────────────────────────────────────


@pytest.fixture
def existing(tmp_path):
    container = tmp_path / "c"
    res = run_init_group(container, name="first", cwd=tmp_path, home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    return container


def test_rerun_answer_no_cancels_and_keeps_database(existing, tmp_path):
    db = existing / ".mezosync" / "mezosync.db"
    before = _sha(db)
    res = run_init_group(existing, name="second", cwd=tmp_path, input="n\n",
                         home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    assert "Перезаписать?" in res.stdout
    assert "Отмена." in res.stdout
    assert _sha(db) == before, "при отказе от перезаписи база изменилась"


def test_rerun_answer_yes_rebuilds(existing, tmp_path):
    res = run_init_group(existing, name="second", cwd=tmp_path, input="y\n",
                         home=tmp_path / "home")
    assert res.returncode == 0, res.explain()
    assert "🎉 Группа «second» готова" in res.stdout, res.explain()
    conn = _connect(existing)
    try:
        name = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()[0]
        journal = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    finally:
        conn.close()
    assert name == "second"
    assert len(journal) == len(set(journal)), "после пересборки журнал шагов задвоился"


# Было xfail до починки scripts/init-group.py (нет ответа без терминала — «Отмена.» и код 0).
def test_rerun_without_terminal_cancels_cleanly(existing, tmp_path):
    res = run_init_group(existing, name="second", cwd=tmp_path, input="",
                         home=tmp_path / "home")
    assert "Traceback" not in res.out, res.explain()
    assert res.returncode == 0, res.explain()
    assert "Отмена." in res.stdout
