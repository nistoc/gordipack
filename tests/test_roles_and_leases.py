# -*- coding: utf-8 -*-
"""lease.py · role-rights.py · set-registry.py · track.py — контрактные тесты на свежем контуре.

Контракт — из докстрок, справки (--help) и комментариев самих скриптов:
  · lease.py — объявление о правке инструмента: `take` пишет объявление (гаснет само, срок
    1–480 минут), `release` снимает (только владелец) и называет ждущих, `status` показывает.
    Пишущему инструменту под ЧУЖИМ живым объявлением — отказ кодом 3 (имя, причина и готовый
    вопрос в тексте, ожидание записано в tool_lease_waits); читающему — предупреждение;
    своя роль (MEZO_ROLE), снятое и просроченное объявления не мешают; сам lease.py не
    закрывается никогда; MEZO_LEASE_BYPASS — громкий аварийный обход;
  · role-rights.py — права роли полями: право без «кто разрешил · когда · где сказано»
    не записывается (код 2); отзыв требует --why и --by и пишет руку в revoked_by; чужое
    право отзывает только координатор контура (из данных, по слову в причине живой роли)
    и только явно, с --foreign;
  · set-registry.py — писатель реестров (треки, инварианты, тесты карточек, шаблоны):
    без --apply холостой прогон; запись идёт в audit_log от руки (--actor → MEZO_ROLE →
    координатор из данных → отказ); чтение (list) и холостой прогон руки не требуют;
  · track.py — пул как рабочая единица: open · plan · view · verdict · close · triage;
    закрытие требует вердикты участников, триаж ничего не меняет.

Тексты по-русски проверяются только короткими стабильными кусками (имена, номера, флаги).
Все тесты — на копии контура из fixture `circuit`; живой контур и сеть не нужны.
"""

import pytest

LEASED = "set-registry.py"   # пишущий инструмент (не из списка «читающих»), на нём удобно ставить объявление
READER = "db-q.py"           # читающий инструмент: имя из списка READING в lease.py


# ── Общие помощники ──────────────────────────────────────────────────────────────


def ok(res):
    """Успех: код 0 и ни следа трассировки."""
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out, res.explain()
    return res


def refused(res, code=None):
    """Отказ словами: код не 0 (или ровно `code`) и это не падение с трассировкой."""
    if code is None:
        assert res.returncode != 0, res.explain()
    else:
        assert res.returncode == code, res.explain()
    assert "Traceback" not in res.out, res.explain()
    return res


def usage_error(res):
    """Ошибка разбора аргументов argparse: код 2 без трассировки."""
    return refused(res, 2)


def execute(circuit, sql, params=()):
    """Записать в базу контура напрямую (подготовка состояния для теста)."""
    conn = circuit.connect()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def set_coordinator_marks(circuit, marked):
    """Поставить слово «координатор» в причину ровно перечисленным ролям (у прочих — убрать).

    Кто в контуре координатор, скрипты берут ИЗ ДАННЫХ — по этому слову в причине живой роли.
    """
    for role in circuit.roles:
        reason = "координатор контура (тест)" if role in marked else "заведена тестом"
        execute(circuit, "UPDATE roles SET lifecycle_reason = ? WHERE role = ?", (reason, role))


# ══════════════════════════════════════════════════════════════════════════════════
# lease.py
# ══════════════════════════════════════════════════════════════════════════════════


def lease_take(circuit, role="CORE", tools=LEASED, reason="fixing-parser", minutes=None):
    """Взять объявление и вернуть его номер из базы."""
    args = ["take", "--role", role, "--tools", tools, "--reason", reason]
    if minutes is not None:
        args += ["--minutes", str(minutes)]
    ok(circuit.run("lease.py", *args))
    return circuit.scalar("SELECT MAX(id) FROM tool_leases")


def lease_release(circuit, lease_id, role="CORE", note=None):
    args = ["release", "--role", role, "--id", str(lease_id)]
    if note is not None:
        args += ["--note", note]
    return circuit.run("lease.py", *args)


def write_invariant(circuit, code="INV-T", actor="STUD", env_extra=None):
    """Пишущий вызов набора set-registry.py: пытается записать инвариант."""
    args = ["invariant", "--code", code, "--desc", "test invariant", "--apply"]
    if actor:
        args += ["--actor", actor]
    return circuit.run(LEASED, *args, env_extra=env_extra)


def invariant_rows(circuit, code="INV-T"):
    return circuit.query("SELECT code FROM invariants WHERE code = ?", (code,))


# ── Справка и разбор аргументов ──────────────────────────────────────────────────


def test_lease_help_lists_subcommands(circuit):
    res = ok(circuit.run("lease.py", "--help"))
    for word in ("take", "release", "status", "--role", "--tools", "--reason", "--minutes"):
        assert word in res.stdout, res.explain()


def test_lease_requires_subcommand(circuit):
    usage_error(circuit.run("lease.py"))


def test_lease_rejects_unknown_subcommand(circuit):
    usage_error(circuit.run("lease.py", "grab"))


def test_lease_non_integer_minutes_is_usage_error(circuit):
    usage_error(circuit.run("lease.py", "take", "--role", "CORE", "--tools", LEASED,
                            "--reason", "r", "--minutes", "soon"))
    assert circuit.scalar("SELECT COUNT(*) FROM tool_leases") == 0


def test_lease_actor_flag_gets_hint_and_exit_2(circuit):
    # Карточка #409: у lease.py роль зовётся --role; чужая форма --actor — отказ с подсказкой.
    res = usage_error(circuit.run("lease.py", "take", "--actor", "CORE", "--tools", LEASED,
                                  "--reason", "r"))
    assert "--role" in res.out and "--actor" in res.out, res.explain()
    assert circuit.scalar("SELECT COUNT(*) FROM tool_leases") == 0


# ── status ───────────────────────────────────────────────────────────────────────


def test_status_on_fresh_circuit_is_clean(circuit):
    ok(circuit.run("lease.py", "status"))
    assert circuit.scalar("SELECT COUNT(*) FROM tool_leases") == 0


def test_status_shows_live_lease(circuit):
    lease_id = lease_take(circuit, role="CORE", tools=LEASED, reason="reason-visible-in-status")
    res = ok(circuit.run("lease.py", "status"))
    for fragment in (f"#{lease_id}", "CORE", LEASED, "reason-visible-in-status"):
        assert fragment in res.stdout, res.explain()


# ── take ─────────────────────────────────────────────────────────────────────────


def test_take_records_lease_and_audit(circuit):
    res = ok(circuit.run("lease.py", "take", "--role", "core", "--tools", f"{LEASED} backlog.py",
                         "--reason", "fixing-parser", "--minutes", "30"))
    lease_id = circuit.scalar("SELECT MAX(id) FROM tool_leases")
    assert f"#{lease_id}" in res.stdout, res.explain()
    row = circuit.query("SELECT role, tools, reason, released_at, note FROM tool_leases WHERE id = ?",
                        (lease_id,))[0]
    assert row == ("CORE", f"{LEASED} backlog.py", "fixing-parser", None, None), "роль приводится к верхнему регистру"
    audit = circuit.query("SELECT actor_role, target FROM audit_log WHERE action = 'lease_take'")
    assert audit == [("CORE", f"{LEASED} backlog.py")]


@pytest.mark.parametrize("minutes, expected", [(None, 60), (1, 1), (480, 480)])
def test_take_duration_follows_minutes(circuit, minutes, expected):
    lease_id = lease_take(circuit, minutes=minutes)
    span = circuit.scalar(
        "SELECT (julianday(until_utc) - julianday(taken_at)) * 1440 FROM tool_leases WHERE id = ?",
        (lease_id,))
    assert abs(span - expected) < 1, f"объявление на {expected} мин, а срок вышел {span:.2f} мин"


@pytest.mark.parametrize("minutes", ["0", "-5", "481"])
def test_take_refuses_minutes_out_of_range(circuit, minutes):
    refused(circuit.run("lease.py", "take", "--role", "CORE", "--tools", LEASED,
                        "--reason", "r", "--minutes", minutes))
    assert circuit.scalar("SELECT COUNT(*) FROM tool_leases") == 0


@pytest.mark.parametrize("args, flag", [
    (["--tools", LEASED, "--reason", "r"], "--role"),
    (["--role", "CORE", "--reason", "r"], "--tools"),
    (["--role", "CORE", "--tools", LEASED], "--reason"),
], ids=["no-role", "no-tools", "no-reason"])
def test_take_refuses_missing_argument_and_names_it(circuit, args, flag):
    res = refused(circuit.run("lease.py", "take", *args))
    assert flag in res.out, res.explain()
    assert circuit.scalar("SELECT COUNT(*) FROM tool_leases") == 0


# ── release ──────────────────────────────────────────────────────────────────────


def test_release_frees_lease_and_keeps_note(circuit):
    lease_id = lease_take(circuit)
    res = ok(lease_release(circuit, lease_id, note="parser-fixed"))
    assert f"#{lease_id}" in res.stdout and "parser-fixed" in res.stdout, res.explain()
    released_at, note = circuit.query(
        "SELECT released_at, note FROM tool_leases WHERE id = ?", (lease_id,))[0]
    assert released_at is not None and note == "parser-fixed"
    audit = circuit.query("SELECT actor_role, target FROM audit_log WHERE action = 'lease_release'")
    assert audit == [("CORE", str(lease_id))]


def test_release_by_non_holder_is_refused(circuit):
    lease_id = lease_take(circuit, role="CORE")
    res = refused(lease_release(circuit, lease_id, role="STUD"))
    assert "CORE" in res.out and f"#{lease_id}" in res.out, "отказ называет владельца и номер"
    assert circuit.scalar("SELECT released_at FROM tool_leases WHERE id = ?", (lease_id,)) is None


def test_release_unknown_id_is_refused(circuit):
    res = refused(lease_release(circuit, 999))
    assert "999" in res.out, res.explain()
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'lease_release'") == 0


def test_release_twice_is_refused_and_keeps_first_release(circuit):
    lease_id = lease_take(circuit)
    ok(lease_release(circuit, lease_id, note="first"))
    refused(lease_release(circuit, lease_id, note="second"))
    assert circuit.scalar("SELECT note FROM tool_leases WHERE id = ?", (lease_id,)) == "first"


@pytest.mark.parametrize("args, flag", [
    (["--role", "CORE"], "--id"),
    (["--id", "1"], "--role"),
], ids=["no-id", "no-role"])
def test_release_refuses_missing_argument_and_names_it(circuit, args, flag):
    lease_take(circuit)
    res = refused(circuit.run("lease.py", "release", *args))
    assert flag in res.out, res.explain()
    assert circuit.scalar("SELECT released_at FROM tool_leases") is None


# ── Что делает объявление с чужими вызовами инструмента ─────────────────────────


def test_writer_under_foreign_lease_is_refused_with_exit_3(circuit):
    lease_id = lease_take(circuit, role="CORE", reason="fixing-parser")
    res = refused(write_invariant(circuit, actor="STUD"), code=3)
    # отказ несёт имя инструмента, номер, владельца, причину и готовый вопрос «освободилось ли»
    for fragment in (LEASED, f"#{lease_id}", "CORE", "fixing-parser", "lease.py", "status"):
        assert fragment in res.out, res.explain()
    assert "MEZO_ROLE=CORE" in res.out, "отказ говорит, как назваться владельцу, если объявление своё"
    assert invariant_rows(circuit) == [], "отказ случился ДО записи"


def test_refusal_records_named_waiter_once(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit, actor="STUD"), code=3)
    refused(write_invariant(circuit, actor="STUD"), code=3)
    waits = circuit.query("SELECT lease_id, role, tool FROM tool_lease_waits")
    assert waits == [(lease_id, "STUD", LEASED)], "ждущая роль названа по --actor; повтор не дублирует"


def test_refusal_names_waiter_from_environment_when_no_actor_flag(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit, actor=None, env_extra={"MEZO_ROLE": "stud"}), code=3)
    waits = circuit.query("SELECT lease_id, role, tool FROM tool_lease_waits")
    assert waits == [(lease_id, "STUD", LEASED)], "имя из MEZO_ROLE приводится к верхнему регистру"


# Было xfail до починки scripts/lease.py (_who_is_calling узнаёт и форму «--actor=STUD»).
def test_refusal_names_waiter_given_as_actor_equals_form(circuit):
    lease_id = lease_take(circuit)
    res = circuit.run(LEASED, "invariant", "--code", "INV-T", "--desc", "d", "--apply", "--actor=STUD")
    refused(res, code=3)
    waits = circuit.query("SELECT lease_id, role, tool FROM tool_lease_waits")
    assert waits == [(lease_id, "STUD", LEASED)], "имя роли стоит в её командной строке — в форме --actor=STUD"


def test_refusal_of_unnamed_caller_records_wait_without_role(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit, actor=None), code=3)
    waits = circuit.query("SELECT lease_id, role, tool FROM tool_lease_waits")
    assert waits == [(lease_id, None, LEASED)], "безымянный вызов записывается без выдуманного имени"


def test_holder_is_not_blocked_by_own_lease(circuit):
    lease_take(circuit, role="CORE")
    ok(write_invariant(circuit, actor=None, env_extra={"MEZO_ROLE": "CORE"}))
    assert invariant_rows(circuit) == [("INV-T",)]
    assert circuit.scalar("SELECT COUNT(*) FROM tool_lease_waits") == 0


def test_lease_covers_every_tool_in_its_list(circuit):
    lease_take(circuit, tools=f"first.py {LEASED}")
    refused(write_invariant(circuit), code=3)


def test_lease_matches_whole_tool_names_only(circuit):
    # «registry.py» — часть имени «set-registry.py», но не оно само: подстрока не закрывает чужой инструмент
    lease_take(circuit, tools="registry.py")
    ok(write_invariant(circuit))
    assert invariant_rows(circuit) == [("INV-T",)]


def test_tool_outside_lease_list_is_not_blocked(circuit):
    lease_take(circuit, tools=LEASED)
    ok(circuit.run("track.py", "open", "--id", "POOL-FREE", "--title", "free", "--actor", "STUD"))
    assert circuit.query("SELECT track_id FROM tracks") == [("POOL-FREE",)]


def test_reading_tool_gets_warning_not_refusal(circuit):
    lease_id = lease_take(circuit, role="CORE", tools=READER)
    res = ok(circuit.run(READER, "SELECT 1 AS probe"))
    assert "probe" in res.stdout, "читающий инструмент отработал"
    assert f"#{lease_id}" in res.stderr and "CORE" in res.stderr, "предупреждение назвало объявление"
    assert circuit.scalar("SELECT COUNT(*) FROM tool_lease_waits") == 0, "ожидание пишется только отказу"


def test_expired_lease_does_not_block(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit), code=3)
    # срок не ждём — сдвигаем его в прошлое: объявление обязано гаснуть само
    execute(circuit, "UPDATE tool_leases SET until_utc = datetime('now', '-1 minute') WHERE id = ?",
            (lease_id,))
    ok(write_invariant(circuit))
    assert invariant_rows(circuit) == [("INV-T",)]


def test_released_lease_does_not_block(circuit):
    lease_id = lease_take(circuit)
    ok(lease_release(circuit, lease_id))
    ok(write_invariant(circuit))
    assert invariant_rows(circuit) == [("INV-T",)]


def test_lease_tool_is_never_closed_by_lease(circuit):
    # Объявление на сам lease.py не должно запереть единственный выход — снятие.
    lease_id = lease_take(circuit, role="CORE", tools="lease.py")
    ok(circuit.run("lease.py", "status"))
    ok(lease_release(circuit, lease_id, role="CORE"))
    assert circuit.scalar("SELECT released_at FROM tool_leases WHERE id = ?", (lease_id,)) is not None


def test_bypass_variable_lets_writer_through_loudly(circuit):
    lease_take(circuit)
    res = ok(write_invariant(circuit, env_extra={"MEZO_LEASE_BYPASS": "1"}))
    assert "MEZO_LEASE_BYPASS" in res.out, "обход громкий: называет свою переменную"
    assert invariant_rows(circuit) == [("INV-T",)]


# ── Снятие называет ждущих ───────────────────────────────────────────────────────


def test_release_names_waiting_role_and_tool(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit, actor="STUD"), code=3)
    res = ok(lease_release(circuit, lease_id))
    assert "STUD" in res.stdout and LEASED in res.stdout, res.explain()


def test_release_without_waiters_names_nobody(circuit):
    lease_id = lease_take(circuit)
    res = ok(lease_release(circuit, lease_id))
    assert LEASED not in res.stdout and "STUD" not in res.stdout, res.explain()


def test_release_with_unnamed_waiter_succeeds_without_inventing_a_name(circuit):
    lease_id = lease_take(circuit)
    refused(write_invariant(circuit, actor=None), code=3)
    res = ok(lease_release(circuit, lease_id))
    assert "None" not in res.stdout, res.explain()


# ══════════════════════════════════════════════════════════════════════════════════
# role-rights.py
# ══════════════════════════════════════════════════════════════════════════════════


def grant(circuit, role="CORE", right="rk-push", kind="standing", scope="repo-x",
          authorized_by="owner", granted_at="2026-10-01 10:00",
          source_ref="chat CORE 2026-10-01 10:00 UTC", force=False):
    """Выдать право; значение None — флаг не передаётся вовсе."""
    args = ["grant", "--role", role, "--right", right, "--kind", kind]
    for flag, value in (("--scope", scope), ("--authorized-by", authorized_by),
                        ("--granted-at", granted_at), ("--source-ref", source_ref)):
        if value is not None:
            args += [flag, value]
    if force:
        args.append("--force")
    return circuit.run("role-rights.py", *args)


def granted(circuit, **kw):
    """Выдать право (обязано удаться) и вернуть его номер."""
    ok(grant(circuit, **kw))
    return circuit.scalar("SELECT MAX(id) FROM role_rights")


def revoke(circuit, right_id, by="CORE", why="no-longer-needed", foreign=False):
    args = ["revoke", "--id", str(right_id)]
    if by is not None:
        args += ["--by", by]
    if why is not None:
        args += ["--why", why]
    if foreign:
        args.append("--foreign")
    return circuit.run("role-rights.py", *args)


def revoked_state(circuit, right_id):
    """(revoked_at задан?, revoked_by, revoked_why) записи права."""
    at, by, why = circuit.query(
        "SELECT revoked_at, revoked_by, revoked_why FROM role_rights WHERE id = ?", (right_id,))[0]
    return at is not None, by, why


def live_ids(circuit):
    return [r[0] for r in circuit.query("SELECT id FROM role_rights_live ORDER BY id")]


# ── Справка и разбор аргументов ──────────────────────────────────────────────────


def test_role_rights_help_lists_subcommands(circuit):
    res = ok(circuit.run("role-rights.py", "--help"))
    for word in ("grant", "revoke", "list", "spend", "amend", "coordinator"):
        assert word in res.stdout, res.explain()


def test_role_rights_requires_subcommand(circuit):
    usage_error(circuit.run("role-rights.py"))


@pytest.mark.parametrize("bad", [
    ["grant", "--right", "k", "--kind", "standing"],                 # нет --role
    ["grant", "--role", "CORE", "--kind", "standing"],               # нет --right
    ["grant", "--role", "CORE", "--right", "k"],                     # нет --kind
    ["grant", "--role", "CORE", "--right", "k", "--kind", "forever"],  # --kind вне списка
    ["grant", "--role", "CORE", "--right", "k", "--kind", "once",
     "--declared-by", "guess"],                                      # --declared-by вне списка
    ["revoke", "--by", "CORE", "--why", "w"],                        # нет --id
    ["revoke", "--id", "abc", "--by", "CORE", "--why", "w"],         # --id не число
    ["spend"],                                                       # нет --id
], ids=["grant-no-role", "grant-no-right", "grant-no-kind", "grant-bad-kind",
        "grant-bad-declared-by", "revoke-no-id", "revoke-id-not-int", "spend-no-id"])
def test_role_rights_usage_errors(circuit, bad):
    usage_error(circuit.run("role-rights.py", *bad))
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 0


def test_role_rights_missing_database_is_refused_without_creating_it(circuit, tmp_path):
    ghost = tmp_path / "nope.db"
    refused(circuit.run("role-rights.py", "--db", str(ghost), "list"))
    assert not ghost.exists(), "фантомная пустая база не создаётся"


# ── grant ────────────────────────────────────────────────────────────────────────


def test_grant_writes_all_fields(circuit):
    res = ok(grant(circuit, role="core", right="rk-push", kind="once", scope="repo-x",
                   authorized_by="owner", granted_at="2026-10-01 10:00",
                   source_ref="chat CORE 2026-10-01 10:00 UTC"))
    assert "CORE" in res.stdout and "rk-push" in res.stdout, res.explain()
    row = circuit.query(
        "SELECT role, right_key, scope, kind, authorized_by, granted_at, source_ref, declared_by, "
        "spent_at, revoked_at FROM role_rights")
    assert row == [("CORE", "rk-push", "repo-x", "once", "owner", "2026-10-01 10:00",
                    "chat CORE 2026-10-01 10:00 UTC", "field", None, None)]


def test_grant_without_scope_is_allowed_but_stored_without_it(circuit):
    ok(grant(circuit, scope=None))
    assert circuit.scalar("SELECT scope FROM role_rights") is None


@pytest.mark.parametrize("missing, flag", [
    ("authorized_by", "--authorized-by"),
    ("granted_at", "--granted-at"),
    ("source_ref", "--source-ref"),
])
def test_grant_without_evidence_is_refused_with_exit_2(circuit, missing, flag):
    res = refused(grant(circuit, **{missing: None}), code=2)
    assert flag in res.out, "отказ называет недостающее поле флагом"
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 0, "право без источника не сохраняется"


def test_grant_without_any_evidence_names_all_missing_flags(circuit):
    res = refused(grant(circuit, authorized_by=None, granted_at=None, source_ref=None), code=2)
    for flag in ("--authorized-by", "--granted-at", "--source-ref"):
        assert flag in res.out, res.explain()


def test_grant_duplicate_is_refused_without_force(circuit):
    granted(circuit)
    refused(grant(circuit), code=1)
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 1


def test_grant_duplicate_is_allowed_with_force(circuit):
    granted(circuit)
    ok(grant(circuit, force=True))
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 2


def test_grant_same_right_in_other_scope_is_not_a_duplicate(circuit):
    granted(circuit, scope="repo-x")
    ok(grant(circuit, scope="repo-y"))
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 2


def test_grant_again_after_revoke_needs_no_force(circuit):
    first = granted(circuit)
    ok(revoke(circuit, first))
    ok(grant(circuit))
    assert len(live_ids(circuit)) == 1


# ── list ─────────────────────────────────────────────────────────────────────────


def test_list_on_empty_table_is_clean(circuit):
    ok(circuit.run("role-rights.py", "list"))


def test_list_shows_live_rights_of_all_roles(circuit):
    a = granted(circuit, role="CORE", right="rk-alpha")
    b = granted(circuit, role="STUD", right="rk-beta")
    res = ok(circuit.run("role-rights.py", "list"))
    for fragment in ("rk-alpha", "rk-beta", f"#{a}", f"#{b}", "CORE", "STUD"):
        assert fragment in res.stdout, res.explain()


def test_list_role_filter_includes_common_rights_and_excludes_foreign(circuit):
    granted(circuit, role="CORE", right="rk-alpha")
    granted(circuit, role="STUD", right="rk-beta")
    granted(circuit, role="ALL", right="rk-gamma")
    res = ok(circuit.run("role-rights.py", "list", "--role", "stud"))
    assert "rk-beta" in res.stdout and "rk-gamma" in res.stdout, "свои и общие (ALL)"
    assert "rk-alpha" not in res.stdout, res.explain()


def test_list_unknown_role_is_answered_not_crashed(circuit):
    granted(circuit, role="CORE", right="rk-alpha")
    res = ok(circuit.run("role-rights.py", "list", "--role", "ghost"))
    assert "GHOST" in res.stdout and "rk-alpha" not in res.stdout, res.explain()


def test_list_hides_revoked_and_all_shows_it(circuit):
    gone = granted(circuit, right="rk-gone")
    granted(circuit, role="STUD", right="rk-kept")
    ok(revoke(circuit, gone))
    live = ok(circuit.run("role-rights.py", "list"))
    assert "rk-kept" in live.stdout and "rk-gone" not in live.stdout, live.explain()
    everything = ok(circuit.run("role-rights.py", "list", "--all"))
    assert "rk-kept" in everything.stdout and "rk-gone" in everything.stdout, everything.explain()


# ── revoke: владелец записи ──────────────────────────────────────────────────────


def test_revoke_by_owner_records_who_and_why(circuit):
    right_id = granted(circuit, role="CORE")
    res = ok(revoke(circuit, right_id, by="core", why="task-finished"))
    assert f"#{right_id}" in res.stdout, res.explain()
    assert revoked_state(circuit, right_id) == (True, "CORE", "task-finished")
    assert live_ids(circuit) == [], "отозванное право ушло из живых"
    assert circuit.scalar("SELECT COUNT(*) FROM role_rights") == 1, "отозвать — не удалить"


def test_revoke_without_why_is_refused(circuit):
    right_id = granted(circuit)
    res = refused(revoke(circuit, right_id, why=None))
    assert "--why" in res.out, res.explain()
    assert revoked_state(circuit, right_id)[0] is False


def test_revoke_without_by_is_refused(circuit):
    right_id = granted(circuit)
    res = refused(revoke(circuit, right_id, by=None))
    assert "--by" in res.out, res.explain()
    assert revoked_state(circuit, right_id)[0] is False


def test_revoke_unknown_id_is_refused(circuit):
    granted(circuit)
    res = refused(revoke(circuit, 999))
    assert "999" in res.out, res.explain()
    assert live_ids(circuit) == [1]


def test_revoke_twice_fails_and_keeps_first_revoker(circuit):
    right_id = granted(circuit, role="CORE")
    ok(revoke(circuit, right_id, by="CORE", why="first"))
    refused(revoke(circuit, right_id, by="CORE", why="second"), code=1)
    assert revoked_state(circuit, right_id) == (True, "CORE", "first")


# ── revoke: чужое право ──────────────────────────────────────────────────────────


def test_revoke_foreign_by_non_coordinator_is_refused(circuit):
    right_id = granted(circuit, role="CORE")
    res = refused(revoke(circuit, right_id, by="STUD", foreign=True))
    assert "--foreign" in res.out, "отказ объясняет, кто и как вправе отозвать чужое"
    assert revoked_state(circuit, right_id)[0] is False


def test_revoke_foreign_by_coordinator_needs_explicit_flag(circuit):
    right_id = granted(circuit, role="CORE")
    res = refused(revoke(circuit, right_id, by="COORD", foreign=False))
    assert "--foreign" in res.out, res.explain()
    assert revoked_state(circuit, right_id)[0] is False


def test_revoke_foreign_by_coordinator_with_flag_records_coordinator(circuit):
    right_id = granted(circuit, role="CORE")
    ok(revoke(circuit, right_id, by="coord", why="reassigned", foreign=True))
    assert revoked_state(circuit, right_id) == (True, "COORD", "reassigned")


def test_coordinator_revokes_own_right_without_foreign_flag(circuit):
    right_id = granted(circuit, role="COORD")
    ok(revoke(circuit, right_id, by="COORD", foreign=False))
    assert revoked_state(circuit, right_id)[1] == "COORD"


def test_common_right_is_not_revoked_by_arbitrary_role(circuit):
    right_id = granted(circuit, role="ALL", right="rk-gamma")
    refused(revoke(circuit, right_id, by="STUD"))
    refused(revoke(circuit, right_id, by="STUD", foreign=True))
    assert revoked_state(circuit, right_id)[0] is False


@pytest.mark.parametrize("marked", [[], ["COORD", "CORE"]], ids=["nobody-marked", "two-marked"])
def test_foreign_revoke_is_refused_while_coordinator_is_undefined(circuit, marked):
    # Координатор — из данных: никто не помечен или помечено несколько — чужое не отзывает НИКТО.
    right_id = granted(circuit, role="STUD")
    set_coordinator_marks(circuit, marked)
    refused(revoke(circuit, right_id, by="COORD", foreign=True))
    assert revoked_state(circuit, right_id)[0] is False
    # а владелец записи по-прежнему отзывает своё
    ok(revoke(circuit, right_id, by="STUD"))
    assert revoked_state(circuit, right_id)[:2] == (True, "STUD")


def test_moved_coordinator_mark_moves_the_right_to_revoke(circuit):
    right_id = granted(circuit, role="STUD")
    set_coordinator_marks(circuit, ["CORE"])
    refused(revoke(circuit, right_id, by="COORD", foreign=True))
    ok(revoke(circuit, right_id, by="CORE", foreign=True))
    assert revoked_state(circuit, right_id)[:2] == (True, "CORE")


# ── spend · amend ────────────────────────────────────────────────────────────────


def test_spend_marks_one_time_right_spent_and_not_live(circuit):
    right_id = granted(circuit, kind="once")
    ok(circuit.run("role-rights.py", "spend", "--id", str(right_id), "--on", "migration-run"))
    assert circuit.scalar("SELECT spent_at FROM role_rights WHERE id = ?", (right_id,)) is not None
    assert live_ids(circuit) == [], "потраченное разовое право не живое"


def test_spend_twice_is_refused(circuit):
    right_id = granted(circuit, kind="once")
    ok(circuit.run("role-rights.py", "spend", "--id", str(right_id)))
    refused(circuit.run("role-rights.py", "spend", "--id", str(right_id)))


def test_spend_refuses_standing_and_unknown_right(circuit):
    right_id = granted(circuit, kind="standing")
    refused(circuit.run("role-rights.py", "spend", "--id", str(right_id)))
    refused(circuit.run("role-rights.py", "spend", "--id", "999"))
    assert circuit.scalar("SELECT spent_at FROM role_rights WHERE id = ?", (right_id,)) is None


def test_amend_fixes_evidence_and_leaves_action_untouched(circuit):
    right_id = granted(circuit, granted_at="2026-10-01 10:00")
    ok(revoke(circuit, right_id, by="CORE", why="done"))
    before = revoked_state(circuit, right_id)
    ok(circuit.run("role-rights.py", "amend", "--id", str(right_id), "--by", "core",
                   "--why", "re-measured", "--granted-at", "2026-10-02 09:00"))
    assert circuit.scalar("SELECT granted_at FROM role_rights WHERE id = ?", (right_id,)) == "2026-10-02 09:00"
    assert revoked_state(circuit, right_id) == before, "правка свидетельства не трогает отзыв"


@pytest.mark.parametrize("args", [
    ["--why", "w", "--granted-at", "2026-10-02"],       # нет --by
    ["--by", "CORE", "--granted-at", "2026-10-02"],     # нет --why
    ["--by", "CORE", "--why", "w"],                     # нечего исправлять
], ids=["no-by", "no-why", "nothing-to-fix"])
def test_amend_refuses_incomplete_call(circuit, args):
    right_id = granted(circuit, granted_at="2026-10-01 10:00")
    refused(circuit.run("role-rights.py", "amend", "--id", str(right_id), *args))
    assert circuit.scalar("SELECT granted_at FROM role_rights WHERE id = ?", (right_id,)) == "2026-10-01 10:00"


# ── coordinator ──────────────────────────────────────────────────────────────────


def test_coordinator_shows_marked_role(circuit):
    res = ok(circuit.run("role-rights.py", "coordinator"))
    assert circuit.coordinator in res.stdout, res.explain()


@pytest.mark.parametrize("marked", [[], ["COORD", "CORE"]], ids=["nobody-marked", "two-marked"])
def test_coordinator_show_survives_undefined_state(circuit, marked):
    set_coordinator_marks(circuit, marked)
    ok(circuit.run("role-rights.py", "coordinator"))


def test_coordinator_set_without_apply_changes_nothing(circuit):
    before = circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role")
    ok(circuit.run("role-rights.py", "coordinator", "--set", "CORE", "--actor", "owner",
                   "--word", "test-word"))
    assert circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role") == before


def test_coordinator_help_shows_flags(circuit):
    res = ok(circuit.run("role-rights.py", "coordinator", "--help"))
    for flag in ("--set", "--actor", "--word", "--apply"):
        assert flag in res.stdout, res.explain()


def test_coordinator_apply_moves_the_mark_and_leaves_a_trace(circuit):
    ok(circuit.run("role-rights.py", "coordinator", "--set", "core", "--actor", "owner",
                   "--word", "test-word", "--apply"))
    shown = ok(circuit.run("role-rights.py", "coordinator"))
    assert "CORE" in shown.stdout, "теперь координатор — CORE"
    reasons = dict(circuit.query("SELECT role, lifecycle_reason FROM roles"))
    assert "координатор" in reasons["CORE"]
    assert "координатор" not in reasons["COORD"], "прежняя пометка снята — координатор один"
    assert circuit.query("SELECT actor_role, target FROM audit_log WHERE action = 'set_coordinator'") == [
        ("owner", "CORE")]
    # и право отзывать чужое переехало вместе с пометкой
    right_id = granted(circuit, role="STUD")
    refused(revoke(circuit, right_id, by="COORD", foreign=True))
    ok(revoke(circuit, right_id, by="CORE", foreign=True))


def test_coordinator_set_current_coordinator_changes_nothing(circuit):
    before = circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role")
    refused(circuit.run("role-rights.py", "coordinator", "--set", "COORD", "--actor", "owner",
                        "--word", "test-word", "--apply"), code=1)
    assert circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role") == before
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'set_coordinator'") == 0


def test_coordinator_set_unknown_role_is_refused(circuit):
    before = circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role")
    res = refused(circuit.run("role-rights.py", "coordinator", "--set", "ghost", "--actor", "owner",
                              "--word", "test-word", "--apply"))
    assert "GHOST" in res.out, res.explain()
    assert circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role") == before


def test_coordinator_set_requires_actor_and_word(circuit):
    before = circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role")
    refused(circuit.run("role-rights.py", "coordinator", "--set", "CORE", "--apply"))
    assert circuit.query("SELECT role, lifecycle_reason FROM roles ORDER BY role") == before


# ══════════════════════════════════════════════════════════════════════════════════
# set-registry.py
# ══════════════════════════════════════════════════════════════════════════════════


def registry(circuit, *args, actor="COORD", apply=True, env_extra=None):
    """Позвать set-registry.py <подкоманда …> с рукой и (по умолчанию) --apply."""
    argv = list(args)
    if actor:
        argv += ["--actor", actor]
    if apply:
        argv.append("--apply")
    return circuit.run("set-registry.py", *argv, env_extra=env_extra)


def audit_rows(circuit, action):
    return circuit.query("SELECT actor_role, target FROM audit_log WHERE action = ? ORDER BY id", (action,))


def test_registry_help_lists_subcommands(circuit):
    res = ok(circuit.run("set-registry.py", "--help"))
    for word in ("track", "invariant", "test", "template", "list"):
        assert word in res.stdout, res.explain()


def test_registry_requires_subcommand(circuit):
    usage_error(circuit.run("set-registry.py"))


@pytest.mark.parametrize("bad", [
    ["track", "--title", "T"],                                # нет --id
    ["track", "--id", "TRACK-X"],                             # нет --title
    ["track", "--id", "TRACK-X", "--title", "T", "--status", "frozen"],   # статус вне списка
    ["invariant", "--desc", "d"],                             # нет --code
    ["invariant", "--code", "C"],                             # нет --desc
    ["test", "--title", "t", "--method", "m"],                # нет --backlog-id
    ["test", "--backlog-id", "abc", "--title", "t", "--method", "m"],     # --backlog-id не число
    ["template", "--name", "n"],                              # нет --role-type
    ["list", "everything"],                                   # вид списка вне перечня
], ids=["track-no-id", "track-no-title", "track-bad-status", "invariant-no-code",
        "invariant-no-desc", "test-no-backlog", "test-backlog-not-int", "template-no-role-type",
        "list-bad-kind"])
def test_registry_usage_errors(circuit, bad):
    usage_error(circuit.run("set-registry.py", *bad, "--actor", "COORD", "--apply"))
    for table in ("tracks", "invariants", "backlog_tests", "templates"):
        assert circuit.scalar(f"SELECT COUNT(*) FROM {table}") == 0, table


def test_registry_missing_database_is_refused_without_creating_it(circuit, tmp_path):
    ghost = tmp_path / "nope.db"
    refused(circuit.run("set-registry.py", "--db", str(ghost), "list"))
    assert not ghost.exists(), "фантомная пустая база не создаётся"


# ── Запись без --apply — холостой прогон ─────────────────────────────────────────


@pytest.mark.parametrize("args, table", [
    (["track", "--id", "TRACK-X", "--title", "Title"], "tracks"),
    (["invariant", "--code", "INV-X", "--desc", "Desc"], "invariants"),
    (["template", "--role-type", "coord", "--name", "Name", "--prompt", "p"], "templates"),
], ids=["track", "invariant", "template"])
def test_registry_without_apply_is_dry_run(circuit, args, table):
    audit_before = circuit.scalar("SELECT COUNT(*) FROM audit_log")
    res = ok(registry(circuit, *args, apply=False))
    assert "DRY-RUN" in res.out and "--apply" in res.out, res.explain()
    assert circuit.scalar(f"SELECT COUNT(*) FROM {table}") == 0
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log") == audit_before, "холостой прогон не пишет и в журнал"


# ── track: записать и прочитать обратно ──────────────────────────────────────────


def test_registry_track_write_then_read_back(circuit):
    res = ok(registry(circuit, "track", "--id", "TRACK-X", "--title", "First title", actor="CORE"))
    assert "TRACK-X" in res.stdout, res.explain()
    assert circuit.query("SELECT track_id, title, status FROM tracks") == [("TRACK-X", "First title", "active")]
    assert audit_rows(circuit, "create_track") == [("CORE", "TRACK-X")]
    listing = ok(circuit.run("set-registry.py", "list", "track"))
    assert "TRACK-X" in listing.stdout and "First title" in listing.stdout, listing.explain()
    assert "INVARIANTS" not in listing.stdout, "list track показывает только треки"


def test_registry_track_rewrite_updates_in_place(circuit):
    ok(registry(circuit, "track", "--id", "TRACK-X", "--title", "Old title"))
    ok(registry(circuit, "track", "--id", "TRACK-X", "--title", "New title", "--status", "paused"))
    assert circuit.query("SELECT track_id, title, status FROM tracks") == [("TRACK-X", "New title", "paused")]
    assert [r[1] for r in audit_rows(circuit, "create_track")] == ["TRACK-X"]
    assert [r[1] for r in audit_rows(circuit, "update_track")] == ["TRACK-X"]
    listing = ok(circuit.run("set-registry.py", "list", "track"))
    assert "New title" in listing.stdout and "Old title" not in listing.stdout, listing.explain()


def test_registry_track_keeps_plan_text(circuit):
    ok(registry(circuit, "track", "--id", "TRACK-X", "--title", "T", "--plan", "step one"))
    assert circuit.scalar("SELECT plan_md FROM tracks WHERE track_id = 'TRACK-X'") == "step one"


# ── invariant ────────────────────────────────────────────────────────────────────


def test_registry_invariant_write_then_read_back(circuit):
    ok(registry(circuit, "invariant", "--code", "VERIFY-AT-SOURCE", "--desc", "check at the source",
                actor="STUD"))
    assert circuit.query("SELECT code, description, established_by FROM invariants") == [
        ("VERIFY-AT-SOURCE", "check at the source", "STUD")]
    assert audit_rows(circuit, "create_invariant") == [("STUD", "VERIFY-AT-SOURCE")]
    listing = ok(circuit.run("set-registry.py", "list", "invariant"))
    assert "VERIFY-AT-SOURCE" in listing.stdout and "check at the source" in listing.stdout, listing.explain()
    assert "TRACKS" not in listing.stdout, "list invariant показывает только инварианты"


def test_registry_invariant_by_flag_names_the_establisher(circuit):
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", "--by", "owner", actor="STUD"))
    assert circuit.scalar("SELECT established_by FROM invariants WHERE code = 'INV-1'") == "owner"
    assert audit_rows(circuit, "create_invariant") == [("STUD", "INV-1")], "в журнале — рука, а не установивший"


def test_registry_invariant_rewrite_is_idempotent(circuit):
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "first"))
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "second"))
    assert circuit.query("SELECT code, description FROM invariants") == [("INV-1", "second")]
    assert [r[1] for r in audit_rows(circuit, "update_invariant")] == ["INV-1"]


def test_registry_list_all_prints_every_section(circuit):
    ok(registry(circuit, "track", "--id", "TRACK-X", "--title", "T"))
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d"))
    res = ok(circuit.run("set-registry.py", "list"))
    for fragment in ("TRACKS", "INVARIANTS", "BACKLOG_TESTS", "TEMPLATES", "TRACK-X", "INV-1"):
        assert fragment in res.stdout, res.explain()


# ── test (тест к карточке) · template ────────────────────────────────────────────


def test_registry_test_for_unknown_card_is_refused(circuit):
    res = refused(registry(circuit, "test", "--backlog-id", "999", "--title", "t", "--method", "m"), code=1)
    assert "999" in res.out, res.explain()
    assert circuit.scalar("SELECT COUNT(*) FROM backlog_tests") == 0


def test_registry_test_binds_to_existing_card(circuit):
    execute(circuit, "INSERT INTO backlog (role, title) VALUES ('CORE', 'card-for-test')")
    card = circuit.scalar("SELECT MAX(id) FROM backlog")
    ok(registry(circuit, "test", "--backlog-id", str(card), "--title", "check-it", "--method", "smoke",
                "--command", "run-it", "--expected", "green", actor="COORD"))
    assert circuit.query("SELECT backlog_id, title, method, command, expected, created_by FROM backlog_tests") == [
        (card, "check-it", "smoke", "run-it", "green", "COORD")]
    listing = ok(circuit.run("set-registry.py", "list", "test"))
    assert "check-it" in listing.stdout and f"backlog#{card}" in listing.stdout, listing.explain()


def test_registry_template_write_bumps_version(circuit):
    ok(registry(circuit, "template", "--role-type", "coord", "--name", "Name one", "--prompt", "p1"))
    ok(registry(circuit, "template", "--role-type", "coord", "--name", "Name two", "--prompt", "p2"))
    assert circuit.query("SELECT role_type, display_name, launcher_prompt, version FROM templates") == [
        ("coord", "Name two", "p2", 2)]
    listing = ok(circuit.run("set-registry.py", "list", "template"))
    assert "coord" in listing.stdout and "Name two" in listing.stdout, listing.explain()


# ── Чья рука пишет: --actor → MEZO_ROLE → координатор из данных → отказ ──────────


def test_registry_actor_flag_wins_over_environment(circuit):
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", actor="CORE",
                env_extra={"MEZO_ROLE": "STUD"}))
    assert audit_rows(circuit, "create_invariant") == [("CORE", "INV-1")]


def test_registry_actor_from_environment_is_uppercased(circuit):
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", actor=None,
                env_extra={"MEZO_ROLE": "stud"}))
    assert audit_rows(circuit, "create_invariant") == [("STUD", "INV-1")]


def test_registry_actor_falls_back_to_coordinator_from_data(circuit):
    res = ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", actor=None))
    assert circuit.coordinator in res.stdout, "выбранная рука печатается"
    assert audit_rows(circuit, "create_invariant") == [(circuit.coordinator, "INV-1")]


@pytest.mark.parametrize("marked", [[], ["COORD", "CORE"]], ids=["nobody-marked", "two-marked"])
def test_registry_apply_without_hand_is_refused_before_any_write(circuit, marked):
    set_coordinator_marks(circuit, marked)
    res = refused(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", actor=None))
    assert "--actor" in res.out and "MEZO_ROLE" in res.out, "отказ называет оба способа назвать руку"
    assert circuit.scalar("SELECT COUNT(*) FROM invariants") == 0
    assert audit_rows(circuit, "create_invariant") == []


@pytest.mark.parametrize("marked", [[], ["COORD", "CORE"]], ids=["nobody-marked", "two-marked"])
def test_registry_list_and_dry_run_need_no_hand(circuit, marked):
    set_coordinator_marks(circuit, marked)
    ok(circuit.run("set-registry.py", "list"))
    ok(registry(circuit, "invariant", "--code", "INV-1", "--desc", "d", actor=None, apply=False))


# ══════════════════════════════════════════════════════════════════════════════════
# track.py
# ══════════════════════════════════════════════════════════════════════════════════


def track(circuit, *args):
    return circuit.run("track.py", *args)


def open_pool(circuit, pool="POOL-A", title="Pool A", actor="core"):
    ok(track(circuit, "open", "--id", pool, "--title", title, "--actor", actor))


def add_card(circuit, pool, role="CORE", title="card-in-pool"):
    """Карточка в пуле (или вне него, если pool=None) — прямой записью в базу."""
    execute(circuit, "INSERT INTO backlog (role, title, parent_track) VALUES (?, ?, ?)",
            (role, title, pool))
    return circuit.scalar("SELECT MAX(id) FROM backlog")


def verdict(circuit, pool, role="CORE", kind="process", text="чисто"):
    return track(circuit, "verdict", "--id", pool, "--role", role, "--kind", kind, "--verdict", text)


def pool_status(circuit, pool="POOL-A"):
    return circuit.scalar("SELECT status FROM tracks WHERE track_id = ?", (pool,))


def test_track_help_lists_subcommands(circuit):
    res = ok(track(circuit, "--help"))
    for word in ("open", "plan", "view", "verdict", "close", "triage"):
        assert word in res.stdout, res.explain()


def test_track_requires_subcommand(circuit):
    usage_error(track(circuit))


@pytest.mark.parametrize("bad", [
    ["open", "--title", "T", "--actor", "CORE"],           # нет --id
    ["open", "--id", "P", "--actor", "CORE"],              # нет --title
    ["open", "--id", "P", "--title", "T"],                 # нет --actor
    ["plan", "--actor", "CORE"],                           # нет --file
    ["verdict", "--role", "CORE", "--kind", "process"],    # нет --verdict
    ["verdict", "--role", "CORE", "--kind", "style", "--verdict", "x"],   # --kind вне списка
    ["close"],                                             # нет --actor
], ids=["open-no-id", "open-no-title", "open-no-actor", "plan-no-file", "verdict-no-text",
        "verdict-bad-kind", "close-no-actor"])
def test_track_usage_errors(circuit, bad):
    usage_error(track(circuit, *bad))
    assert circuit.scalar("SELECT COUNT(*) FROM tracks") == 0


# ── open · view ──────────────────────────────────────────────────────────────────


def test_track_open_creates_active_pool_and_audit(circuit):
    res = ok(track(circuit, "open", "--id", "POOL-A", "--title", "Pool A", "--actor", "core"))
    assert "POOL-A" in res.stdout, res.explain()
    assert circuit.query("SELECT track_id, title, status FROM tracks") == [("POOL-A", "Pool A", "active")]
    assert circuit.query("SELECT actor_role, target FROM audit_log WHERE action = 'open_track'") == [
        ("CORE", "POOL-A")]


def test_track_open_dry_run_writes_nothing(circuit):
    ok(track(circuit, "open", "--id", "POOL-A", "--title", "Pool A", "--actor", "core", "--dry-run"))
    assert circuit.scalar("SELECT COUNT(*) FROM tracks") == 0
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'open_track'") == 0


def test_track_open_existing_id_is_refused(circuit):
    open_pool(circuit, title="Original")
    refused(track(circuit, "open", "--id", "POOL-A", "--title", "Other", "--actor", "core"))
    assert circuit.query("SELECT title FROM tracks") == [("Original",)]


def test_track_view_shows_the_only_active_pool(circuit):
    open_pool(circuit, title="Pool A title")
    for argv in (["view"], ["view", "--id", "POOL-A"]):
        res = ok(track(circuit, *argv))
        assert "POOL-A" in res.stdout and "Pool A title" in res.stdout, res.explain()


def test_track_view_without_any_pool_is_refused(circuit):
    refused(track(circuit, "view"))


def test_track_view_unknown_pool_is_refused_and_names_existing(circuit):
    open_pool(circuit)
    res = refused(track(circuit, "view", "--id", "NOPE"))
    assert "POOL-A" in res.out, "отказ подсказывает, какие пулы есть"


def test_track_view_with_two_active_pools_demands_explicit_id(circuit):
    open_pool(circuit, "POOL-A")
    open_pool(circuit, "POOL-B")
    res = refused(track(circuit, "view"))
    assert "POOL-A" in res.out and "POOL-B" in res.out and "--id" in res.out, res.explain()
    ok(track(circuit, "view", "--id", "POOL-B"))


def test_track_view_lists_cards_by_role(circuit):
    open_pool(circuit)
    card = add_card(circuit, "POOL-A", role="CORE", title="card-in-pool")
    res = ok(track(circuit, "view"))
    assert f"#{card}" in res.stdout and "card-in-pool" in res.stdout and "CORE" in res.stdout, res.explain()


# ── plan ─────────────────────────────────────────────────────────────────────────


def test_track_plan_writes_plan_from_file(circuit, tmp_path):
    open_pool(circuit)
    plan_file = tmp_path / "plan.md"
    plan_file.write_bytes("first-step-of-plan\nsecond step\n".encode("utf-8"))   # байтами: без правки концов строк на Windows
    ok(track(circuit, "plan", "--id", "POOL-A", "--actor", "core", "--file", str(plan_file)))
    assert circuit.scalar("SELECT plan_md FROM tracks WHERE track_id = 'POOL-A'") == \
        "first-step-of-plan\nsecond step\n"
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'update_track_plan'") == 1
    assert "first-step-of-plan" in ok(track(circuit, "view")).stdout


def test_track_plan_missing_file_is_refused_or_fails_without_changing_pool(circuit, tmp_path):
    open_pool(circuit)
    res = track(circuit, "plan", "--id", "POOL-A", "--actor", "core", "--file", str(tmp_path / "none.md"))
    assert res.returncode != 0, res.explain()
    assert circuit.scalar("SELECT plan_md FROM tracks WHERE track_id = 'POOL-A'") is None


# ── verdict ──────────────────────────────────────────────────────────────────────


def test_track_verdict_is_recorded(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    res = ok(verdict(circuit, "POOL-A", role="core", kind="process", text="clean-run"))
    assert "POOL-A" in res.stdout and "CORE" in res.stdout, res.explain()
    assert circuit.query("SELECT track_id, role, kind, verdict FROM track_verdicts") == [
        ("POOL-A", "CORE", "process", "clean-run")]
    assert "CORE/process" in ok(track(circuit, "view")).stdout, "вердикт виден при просмотре пула"


def test_track_verdict_empty_text_is_refused(circuit):
    open_pool(circuit)
    refused(verdict(circuit, "POOL-A", text="   "))
    assert circuit.scalar("SELECT COUNT(*) FROM track_verdicts") == 0


def test_track_verdict_unknown_pool_is_refused(circuit):
    open_pool(circuit)
    refused(verdict(circuit, "NOPE"))
    assert circuit.scalar("SELECT COUNT(*) FROM track_verdicts") == 0


def test_track_documentation_verdict_to_update_is_born_as_card(circuit):
    open_pool(circuit)
    ok(verdict(circuit, "POOL-A", kind="documentation", text="обновить README"))
    cards = circuit.query("SELECT role, status, parent_track FROM backlog")
    assert cards == [("CORE", "open", "POOL-A")], "вердикт «обновить …» рождает карточку тем же ходом"


# ── close ────────────────────────────────────────────────────────────────────────


def test_track_close_without_participant_verdicts_is_refused_by_name(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    res = refused(track(circuit, "close", "--id", "POOL-A", "--actor", "coord"), code=1)
    for fragment in ("CORE", "documentation", "process"):
        assert fragment in res.out, "отказ называет, чьих вердиктов и каких не хватает"
    assert pool_status(circuit) == "active"
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'close_track'") == 0


def test_track_close_with_all_verdicts_closes_pool(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    ok(verdict(circuit, "POOL-A", kind="documentation"))
    ok(verdict(circuit, "POOL-A", kind="process"))
    ok(track(circuit, "close", "--id", "POOL-A", "--actor", "coord"))
    assert pool_status(circuit) == "done"
    assert circuit.query("SELECT actor_role, target FROM audit_log WHERE action = 'close_track'") == [
        ("COORD", "POOL-A")]


def test_track_close_one_missing_verdict_still_blocks(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    ok(verdict(circuit, "POOL-A", kind="process"))
    res = refused(track(circuit, "close", "--id", "POOL-A", "--actor", "coord"), code=1)
    assert "documentation" in res.out, res.explain()
    assert pool_status(circuit) == "active"


def test_track_close_pool_without_cards_has_no_participants_to_wait_for(circuit):
    open_pool(circuit)
    ok(track(circuit, "close", "--actor", "coord"))
    assert pool_status(circuit) == "done"


def test_track_close_no_verdicts_loophole_needs_reason(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    refused(track(circuit, "close", "--id", "POOL-A", "--actor", "coord", "--no-verdicts"))
    assert pool_status(circuit) == "active"


def test_track_close_no_verdicts_with_reason_closes_and_leaves_trace(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE")
    ok(track(circuit, "close", "--id", "POOL-A", "--actor", "coord", "--no-verdicts",
             "--reason", "owner-said-so"))
    assert pool_status(circuit) == "done"
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'close_track_no_verdicts'") == 1


def test_track_close_already_closed_pool_is_refused(circuit):
    open_pool(circuit)
    ok(track(circuit, "close", "--id", "POOL-A", "--actor", "coord"))
    refused(track(circuit, "close", "--id", "POOL-A", "--actor", "coord"))
    assert circuit.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'close_track'") == 1


def test_track_close_without_active_pool_is_refused(circuit):
    refused(track(circuit, "close", "--actor", "coord"))


# ── triage ───────────────────────────────────────────────────────────────────────


def test_track_triage_without_active_pool_is_refused(circuit):
    refused(track(circuit, "triage"))


def test_track_triage_lists_leftovers_and_changes_nothing(circuit):
    open_pool(circuit)
    add_card(circuit, "POOL-A", role="CORE", title="inside-pool-card")
    outside = add_card(circuit, None, role="STUD", title="outside-pool-card")

    def snapshot():
        return (circuit.query("SELECT id, status, parent_track FROM backlog ORDER BY id"),
                circuit.query("SELECT track_id, status FROM tracks ORDER BY track_id"),
                circuit.scalar("SELECT COUNT(*) FROM audit_log"),
                circuit.scalar("SELECT COUNT(*) FROM backlog_events"))

    before = snapshot()
    res = ok(track(circuit, "triage"))
    assert f"#{outside}" in res.stdout and "outside-pool-card" in res.stdout, res.explain()
    assert "inside-pool-card" not in res.stdout, "карточки пула в остаток не попадают"
    assert snapshot() == before, "триаж ничего не меняет"
