# -*- coding: utf-8 -*-
"""Контрактные тесты инструментов scripts/: guard-all, backlog, db-q, backup-db,
bridge-groups, update-tools.

Каждый инструмент зовётся ТАК, КАК ЕГО ЗОВЁТ РОЛЬ: копией из контура (circuit.run),
отдельным процессом, во временной папке. Судится контракт из докстроки и справки:
код выхода, короткие устойчивые куски вывода (номера, имена флагов, имена проверок),
итоговое состояние базы и файлов. Длинные русские фразы не сверяются: их переформулируют.

Контракты по группам:
  · guard-all.py — свежий контур зелёный (код 0); поломка, которую гард описывает
    (строчная роль в отметках прочитанного; схема, изменённая мимо журнала схемы), красит
    прогон (код 1); --skip снимает названную проверку и честно называет незнакомое имя;
  · backlog.py — add → list → show → claim → status → comment; обязательные аргументы
    (argparse, код 2); --actor у claim/status/comment/criterion; незнакомый номер — код 1;
    отказы НИЧЕГО не пишут в базу;
  · db-q.py — читает; пишущий запрос отказан и база не меняется; промах по имени
    таблицы/колонки подсказывает настоящие имена; обрезание по --limit названо вслух;
  · backup-db.py — без --apply не пишет ничего; с --apply пишет текстовый дамп, который
    разворачивается в новую базу с теми же таблицами и числом строк; --out-каталог отказан;
  · bridge-groups.py — связь двух контуров в cross_links, --bidirectional, --target-group
    (база соседа не открывается), отказы кодом 2;
  · update-tools.py — ТОЛЬКО по локальному пакету (--source <REPO_ROOT>), без сети:
    план ничего не пишет; своя правка не затирается; --apply кладёт недостающее;
    разовый --source не становится записью контура.
"""

import hashlib
import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from conftest import REPO_ROOT, Circuit, row_counts, schema_shape, schema_sql_dump

# ── Общие помощники ──────────────────────────────────────────────────────────────


def _db_state(circuit):
    """Весь снимок базы: структура + все строки всех таблиц — для проверки «не изменилась»."""
    conn = circuit.connect()
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows = {n: sorted(repr(r) for r in conn.execute(f'SELECT * FROM "{n}"'))
                for n in names}
        return {"schema": schema_sql_dump(conn), "rows": rows}
    finally:
        conn.close()


def _exec(circuit, sql, params=()):
    """Правка базы мимо инструментов — так готовится поломка, которую ловит гард."""
    conn = circuit.connect()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _copy_db(src_db, dst):
    """Согласованная копия базы (в режиме WAL простое копирование файла теряет хвост)."""
    src = sqlite3.connect(str(src_db))
    out = sqlite3.connect(str(dst))
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    return dst


def _group_name(circuit):
    return circuit.scalar("SELECT value FROM meta WHERE key='group_name'")


# ── --help: каждый инструмент отвечает справкой и кодом 0 ────────────────────────


@pytest.mark.parametrize("script", [
    "guard-all.py", "backlog.py", "db-q.py", "backup-db.py", "bridge-groups.py",
    "update-tools.py"])
def test_help_exits_zero(circuit, script):
    res = circuit.run(script, "--help")
    assert res.returncode == 0, res.explain()
    assert "usage" in res.stdout.lower(), res.explain()


@pytest.mark.parametrize("sub", ["add", "list", "show", "status", "claim", "comment"])
def test_backlog_subcommand_help_exits_zero(circuit, sub):
    res = circuit.run("backlog.py", sub, "--help")
    assert res.returncode == 0, res.explain()
    assert "usage" in res.stdout.lower(), res.explain()


# ═════════════════════════════════════════════════════════════════════════════════
# guard-all.py
# ═════════════════════════════════════════════════════════════════════════════════

# Имена проверок — то, чем их снимает --skip (докстрока: «имена — как их печатает прогон»).
CHECK_CURSOR_CASE = "отметки прочитанного: регистр"
CHECK_CURSOR_REGISTRY = "отметки прочитанного: реестр"
CHECK_SCHEMA_JOURNAL = "журнал схемы"


def _guard(circuit, *args):
    return circuit.run("guard-all.py", *args)


def test_guard_all_green_on_fresh_circuit(circuit):
    res = _guard(circuit)
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out, res.explain()
    assert "КРАСНЫХ" not in res.out, res.explain()
    # --full — тот же вердикт, но каждая зелёная проверка отдельной строкой
    full = _guard(circuit, "--full")
    assert full.returncode == 0, full.explain()
    assert len(full.stdout.splitlines()) > len(res.stdout.splitlines()), (
        "--full обязан печатать каждую зелёную проверку отдельной строкой")


def test_guard_all_red_on_lowercase_read_cursor(circuit):
    # Строчная роль в отметках прочитанного — «призрак» (EYE #2063); гард красит прогон.
    _exec(circuit, "INSERT INTO read_cursors (reader_role, last_read_id) VALUES ('core', 0)")
    res = _guard(circuit)
    assert res.returncode == 1, res.explain()
    assert "КРАСНЫХ" in res.out, res.explain()
    assert CHECK_CURSOR_CASE in res.out, res.explain()


def test_guard_all_skip_silences_named_red_checks_and_names_unknown_ones(circuit):
    _exec(circuit, "INSERT INTO read_cursors (reader_role, last_read_id) VALUES ('core', 0)")
    skip = f"{CHECK_CURSOR_CASE},{CHECK_CURSOR_REGISTRY},no-such-check-name"
    res = _guard(circuit, "--skip", skip)
    assert res.returncode == 0, "названные красные сняты, опечатка кода выхода не меняет\n" + res.explain()
    assert "КРАСНЫХ" not in res.out, res.explain()
    # снятая проверка не молчит: строка называет и проверку, и флаг
    skipped_lines = [ln for ln in res.stdout.splitlines()
                     if CHECK_CURSOR_CASE in ln and "--skip" in ln]
    assert skipped_lines, res.explain()
    # незнакомое имя называется строкой, а не проходит молча (карточка #691)
    unknown = [ln for ln in res.stdout.splitlines()
               if "no-such-check-name" in ln and "--skip" in ln]
    assert unknown, res.explain()


def test_guard_all_red_on_schema_changed_bypassing_journal(circuit):
    # Схему поменяли мимо шага схемы: отпечаток структуры расходится с журналом.
    _exec(circuit, "CREATE TABLE sneaky_table (x TEXT)")
    res = _guard(circuit)
    assert res.returncode == 1, res.explain()
    assert CHECK_SCHEMA_JOURNAL in res.out, res.explain()
    assert "КРАСНЫХ" in res.out, res.explain()


def test_guard_all_missing_db_is_refused(circuit, tmp_path):
    missing = tmp_path / "no-such.db"
    res = _guard(circuit, "--db", str(missing))
    assert res.returncode == 1, res.explain()
    assert str(missing) in res.out, res.explain()
    assert not missing.exists(), "гард не вправе создавать пустую базу по опечатке пути"


def test_guard_all_db_flag_judges_the_given_copy(circuit, tmp_path):
    # --db: прогон по копии. Сломанная копия — красная, живая база контура при этом зелёная.
    broken = _copy_db(circuit.db, tmp_path / "copy.db")
    conn = sqlite3.connect(str(broken))
    conn.execute("INSERT INTO read_cursors (reader_role, last_read_id) VALUES ('core', 0)")
    conn.commit()
    conn.close()
    on_copy = _guard(circuit, "--db", str(broken))
    assert on_copy.returncode == 1, on_copy.explain()
    assert CHECK_CURSOR_CASE in on_copy.out, on_copy.explain()
    # базу контура сломанная копия не затронула
    assert circuit.scalar("SELECT COUNT(*) FROM read_cursors WHERE reader_role = 'core'") == 0


# ═════════════════════════════════════════════════════════════════════════════════
# backlog.py
# ═════════════════════════════════════════════════════════════════════════════════


def _bl(circuit, *args, **kw):
    return circuit.run("backlog.py", *[str(a) for a in args], **kw)


def _new_card(circuit, role="CORE", title="card-title", body="тело карточки",
              done="прогнать X и увидеть Y", *extra):
    res = _bl(circuit, "add", "--role", role, "--title", title, "--body", body,
              "--done-when", done, *extra)
    assert res.returncode == 0, res.explain()
    return circuit.scalar("SELECT MAX(id) FROM backlog")


def _events(circuit, cid):
    return circuit.query(
        "SELECT event_type, actor_role, from_status, to_status, body_md "
        "FROM backlog_events WHERE backlog_id = ? ORDER BY id", (cid,))


def _card(circuit, cid):
    return circuit.query(
        "SELECT role, title, body_md, status, priority, tags, done_when, created_by, "
        "blocked_reason FROM backlog WHERE id = ?", (cid,))[0]


def _card_count(circuit):
    return circuit.scalar("SELECT COUNT(*) FROM backlog")


# ── add ──────────────────────────────────────────────────────────────────────────


def test_backlog_add_creates_open_card_with_events(circuit):
    res = _bl(circuit, "add", "--role", "core", "--title", "first-card",
              "--body", "тело", "--done-when", "критерий приёмки",
              "--priority", "high", "--tags", "a,b")
    assert res.returncode == 0, res.explain()
    assert "#1" in res.out, res.explain()
    role, title, body, status, priority, tags, done_when, created_by, _ = _card(circuit, 1)
    assert (role, title, body, status, priority) == ("CORE", "first-card", "тело", "open", "high")
    assert tags == '["a", "b"]'
    assert done_when == "критерий приёмки"
    assert created_by == "CORE", "без --actor карточку заводит владелец"
    kinds = [e[0] for e in _events(circuit, 1)]
    assert kinds == ["created", "criterion_set"]


def test_backlog_add_actor_is_recorded_as_creator(circuit):
    res = _bl(circuit, "add", "--role", "CORE", "--actor", "stud", "--title", "t",
              "--body", "b", "--done-when", "d")
    assert res.returncode == 0, res.explain()
    assert _card(circuit, 1)[7] == "STUD"
    assert _card(circuit, 1)[0] == "CORE", "владелец — из --role, а не из --actor"


def test_backlog_add_reads_body_and_criterion_from_files(circuit, tmp_path):
    body = tmp_path / "body.md"
    crit = tmp_path / "crit.md"
    body.write_text("Описание предмета — кириллица.\nвторая строка", encoding="utf-8")
    crit.write_text("Прогнать проверку и увидеть зелёное", encoding="utf-8")
    res = _bl(circuit, "add", "--role", "CORE", "--title", "from-files",
              "--body-file", body, "--done-when-file", crit)
    assert res.returncode == 0, res.explain()
    stored = _card(circuit, 1)
    assert stored[2] == "Описание предмета — кириллица.\nвторая строка"
    assert stored[6] == "Прогнать проверку и увидеть зелёное"


@pytest.mark.parametrize("extra, named_flag", [
    (["--body", "тело"], "--done-when"),            # нет критерия
    (["--done-when", "критерий"], "--body"),        # нет тела
    (["--body", "   ", "--done-when", "критерий"], "--body"),   # пробелы — не тело
    ([], "--done-when"),                            # нет обоих
])
def test_backlog_add_refuses_without_body_or_criterion(circuit, extra, named_flag):
    res = _bl(circuit, "add", "--role", "CORE", "--title", "t", *extra)
    assert res.returncode == 1, res.explain()
    assert named_flag in res.out, "отказ называет флаг, которого не хватает\n" + res.explain()
    assert _card_count(circuit) == 0, "отказ не должен заводить карточку"


@pytest.mark.parametrize("missing", ["--role", "--title"])
def test_backlog_add_missing_required_arg_exits_2(circuit, missing):
    args = {"--role": "CORE", "--title": "t", "--body": "b", "--done-when": "d"}
    del args[missing]
    argv = [x for kv in args.items() for x in kv]
    res = _bl(circuit, "add", *argv)
    assert res.returncode == 2, res.explain()
    assert missing in res.out, res.explain()
    assert _card_count(circuit) == 0


def test_backlog_add_rejects_unknown_priority(circuit):
    res = _bl(circuit, "add", "--role", "CORE", "--title", "t", "--body", "b",
              "--done-when", "d", "--priority", "urgent")
    assert res.returncode == 2, res.explain()
    assert _card_count(circuit) == 0


@pytest.mark.parametrize("tags", ['["a","b"]', "a,,b"])
def test_backlog_add_refuses_malformed_tags(circuit, tags):
    # единственная форма меток — через запятую; JSON и пустая метка отказаны со словом
    res = _bl(circuit, "add", "--role", "CORE", "--title", "t", "--body", "b",
              "--done-when", "d", "--tags", tags)
    assert res.returncode == 1, res.explain()
    assert "--tags" in res.out, res.explain()
    assert _card_count(circuit) == 0


def test_backlog_add_dry_run_writes_nothing(circuit):
    before = _db_state(circuit)
    res = _bl(circuit, "add", "--role", "CORE", "--title", "t", "--body", "b",
              "--done-when", "d", "--dry-run")
    assert res.returncode == 0, res.explain()
    assert _db_state(circuit) == before, "холостой прогон не вправе менять базу"


# ── list ─────────────────────────────────────────────────────────────────────────


def test_backlog_list_shows_own_and_shared_but_not_other_roles(circuit):
    _new_card(circuit, "CORE", "corecard")
    _new_card(circuit, "STUD", "studcard")
    _new_card(circuit, "SHARED", "sharedcard")
    res = _bl(circuit, "list", "--role", "CORE")
    assert res.returncode == 0, res.explain()
    assert "corecard" in res.stdout and "sharedcard" in res.stdout, res.explain()
    assert "studcard" not in res.stdout, res.explain()


def test_backlog_list_only_mine_hides_shared(circuit):
    _new_card(circuit, "CORE", "corecard")
    _new_card(circuit, "SHARED", "sharedcard")
    res = _bl(circuit, "list", "--role", "CORE", "--only-mine")
    assert res.returncode == 0, res.explain()
    assert "corecard" in res.stdout, res.explain()
    assert "sharedcard" not in res.stdout, res.explain()


def test_backlog_list_hides_closed_unless_status_all(circuit):
    cid = _new_card(circuit, "CORE", "donecard")
    _new_card(circuit, "CORE", "livecard")
    assert _bl(circuit, "status", cid, "done", "--actor", "CORE").returncode == 0
    default = _bl(circuit, "list", "--role", "CORE")
    assert "livecard" in default.stdout and "donecard" not in default.stdout, default.explain()
    everything = _bl(circuit, "list", "--role", "CORE", "--status", "all")
    assert "livecard" in everything.stdout and "donecard" in everything.stdout, everything.explain()
    only_done = _bl(circuit, "list", "--role", "CORE", "--status", "done")
    assert "donecard" in only_done.stdout and "livecard" not in only_done.stdout, only_done.explain()


def test_backlog_list_on_empty_backlog_exits_zero(circuit):
    res = _bl(circuit, "list", "--role", "CORE")
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out


def test_backlog_list_requires_role(circuit):
    res = _bl(circuit, "list")
    assert res.returncode == 2, res.explain()
    assert "--role" in res.out, res.explain()


# ── show ─────────────────────────────────────────────────────────────────────────


def test_backlog_show_prints_card_with_history(circuit):
    cid = _new_card(circuit, "CORE", "showcard", "Тело-для-показа", "Критерий-для-показа")
    res = _bl(circuit, "show", cid)
    assert res.returncode == 0, res.explain()
    for fragment in ("showcard", "Тело-для-показа", "Критерий-для-показа", "created"):
        assert fragment in res.stdout, f"{fragment!r} не показан\n" + res.explain()


def test_backlog_show_unknown_card_exits_1(circuit):
    res = _bl(circuit, "show", 99)
    assert res.returncode == 1, res.explain()
    assert "99" in res.out, res.explain()


@pytest.mark.parametrize("argv", [["abc"], [], ["1", "--role", "CORE"]])
def test_backlog_show_bad_form_exits_2(circuit, argv):
    # show принимает только число-номер; роль у него не нужна вовсе
    _new_card(circuit)
    res = _bl(circuit, "show", *argv)
    assert res.returncode == 2, res.explain()


# ── claim ────────────────────────────────────────────────────────────────────────


def test_backlog_claim_records_announcement_and_takes_card(circuit):
    cid = _new_card(circuit, "CORE", "claimcard")
    res = _bl(circuit, "claim", cid, "--actor", "CORE", "--note", "делаю-шаг-один")
    assert res.returncode == 0, res.explain()
    claims = [e for e in _events(circuit, cid) if e[0] == "claim"]
    assert len(claims) == 1 and "делаю-шаг-один" in claims[0][4]
    assert _card(circuit, cid)[3] == "in_progress", "claim берёт открытую карточку в работу"
    status = circuit.scalar("SELECT status FROM role_status WHERE role = 'CORE'")
    assert status and f"#{cid}" in status, "claim же и ставит «чем занята роль»"


def test_backlog_claim_requires_a_note(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "claim", cid, "--actor", "CORE")
    assert res.returncode == 1, res.explain()
    assert not [e for e in _events(circuit, cid) if e[0] == "claim"]
    assert _card(circuit, cid)[3] == "open"


def test_backlog_claim_requires_actor(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "claim", cid, "--note", "x")
    assert res.returncode == 2, res.explain()
    assert "--actor" in res.out, res.explain()


def test_backlog_claim_with_role_flag_is_redirected_to_actor(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "claim", cid, "--role", "CORE", "--note", "x")
    assert res.returncode == 2, res.explain()
    assert "--actor" in res.out, "отказ учит верному флагу\n" + res.explain()


def test_backlog_claim_unknown_card_exits_1(circuit):
    res = _bl(circuit, "claim", 99, "--actor", "CORE", "--note", "x")
    assert res.returncode == 1, res.explain()
    assert "99" in res.out, res.explain()


def test_backlog_claim_release_needs_a_result_note(circuit):
    cid = _new_card(circuit)
    assert _bl(circuit, "claim", cid, "--actor", "CORE", "--note", "взял").returncode == 0
    bare = _bl(circuit, "claim", cid, "--actor", "CORE", "--release")
    assert bare.returncode == 0, bare.explain()
    assert not [e for e in _events(circuit, cid) if e[0] == "claim_release"], (
        "снятие без итога не записывается (карточка #451)")
    with_note = _bl(circuit, "claim", cid, "--actor", "CORE", "--release", "--note", "получилось")
    assert with_note.returncode == 0, with_note.explain()
    released = [e for e in _events(circuit, cid) if e[0] == "claim_release"]
    assert len(released) == 1 and released[0][4] == "получилось"


# ── status ───────────────────────────────────────────────────────────────────────


def test_backlog_status_walks_card_through_states_and_logs_each_step(circuit):
    cid = _new_card(circuit)
    for new in ("in_progress", "in_review", "done"):
        res = _bl(circuit, "status", cid, new, "--actor", "CORE")
        assert res.returncode == 0, res.explain()
        assert _card(circuit, cid)[3] == new
    steps = [(e[2], e[3]) for e in _events(circuit, cid) if e[0] == "status_change"]
    assert steps == [("open", "in_progress"), ("in_progress", "in_review"),
                     ("in_review", "done")]


@pytest.mark.parametrize("new_status", ["dropped", "failed", "frozen", "awaiting_word"])
def test_backlog_status_requires_note_for_these_states(circuit, new_status):
    cid = _new_card(circuit)
    bare = _bl(circuit, "status", cid, new_status, "--actor", "CORE")
    assert bare.returncode == 1, bare.explain()
    if new_status != "awaiting_word":   # у отказа «жду слова» команды-образца с флагом нет
        assert "--note" in bare.out, bare.explain()
    assert _card(circuit, cid)[3] == "open", "отказ не меняет состояние"
    ok = _bl(circuit, "status", cid, new_status, "--actor", "CORE", "--note", "причина-словами")
    assert ok.returncode == 0, ok.explain()
    assert _card(circuit, cid)[3] == new_status


@pytest.mark.parametrize("new_status", ["blocked", "frozen", "awaiting_word"])
def test_backlog_status_keeps_note_as_blocked_reason(circuit, new_status):
    cid = _new_card(circuit)
    res = _bl(circuit, "status", cid, new_status, "--actor", "CORE", "--note", "ждём-чужую-работу")
    assert res.returncode == 0, res.explain()
    assert _card(circuit, cid)[8] == "ждём-чужую-работу"


def test_backlog_status_unknown_state_is_refused(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "status", cid, "bogus", "--actor", "CORE")
    assert res.returncode == 1, res.explain()
    assert _card(circuit, cid)[3] == "open"


def test_backlog_status_unknown_card_exits_1(circuit):
    res = _bl(circuit, "status", 99, "blocked", "--actor", "CORE")
    assert res.returncode == 1, res.explain()
    assert "99" in res.out, res.explain()


def test_backlog_status_requires_actor(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "status", cid, "in_progress")
    assert res.returncode == 2, res.explain()
    assert "--actor" in res.out, res.explain()


def test_backlog_status_foreign_card_needs_its_owner_named(circuit):
    cid = _new_card(circuit, "CORE")
    bare = _bl(circuit, "status", cid, "blocked", "--actor", "STUD")
    assert bare.returncode == 1, bare.explain()
    assert "--foreign" in bare.out, "отказ называет флаг, которым чужую карточку двигают"
    wrong = _bl(circuit, "status", cid, "blocked", "--actor", "STUD", "--foreign", "STUD")
    assert wrong.returncode == 1, wrong.explain()
    assert _card(circuit, cid)[3] == "open", "оба отказа ничего не меняют"
    right = _bl(circuit, "status", cid, "blocked", "--actor", "STUD", "--foreign", "CORE")
    assert right.returncode == 0, right.explain()
    assert _card(circuit, cid)[3] == "blocked"
    last = [e for e in _events(circuit, cid) if e[0] == "status_change"][-1]
    assert last[1] == "STUD", "в событии — тот, кто двинул, а не владелец"


def test_backlog_done_needs_criterion_and_criterion_command_provides_it(circuit):
    # Карточка без критерия (старая, до обязательности критерия при add) не закрывается как done.
    _exec(circuit,
          "INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by) "
          "VALUES ('CORE', 'legacy', 'тело', 'open', 'normal', '[]', 'CORE')")
    cid = circuit.scalar("SELECT MAX(id) FROM backlog")
    refused = _bl(circuit, "status", cid, "done", "--actor", "CORE")
    assert refused.returncode == 1, refused.explain()
    assert "criterion" in refused.out, "отказ называет путь записи критерия\n" + refused.explain()
    assert _card(circuit, cid)[3] == "open"
    empty = _bl(circuit, "criterion", cid, "--actor", "CORE", "--text", "  ")
    assert empty.returncode == 1, "пустой критерий не записывается\n" + empty.explain()
    ok = _bl(circuit, "criterion", cid, "--actor", "CORE", "--text", "прогнать и увидеть")
    assert ok.returncode == 0, ok.explain()
    assert _card(circuit, cid)[6] == "прогнать и увидеть"
    assert _bl(circuit, "status", cid, "done", "--actor", "CORE").returncode == 0
    assert _card(circuit, cid)[3] == "done"


def test_backlog_criterion_unknown_card_and_missing_actor(circuit):
    unknown = _bl(circuit, "criterion", 99, "--actor", "CORE", "--text", "x")
    assert unknown.returncode == 1, unknown.explain()
    cid = _new_card(circuit)
    no_actor = _bl(circuit, "criterion", cid, "--text", "x")
    assert no_actor.returncode == 2, no_actor.explain()


# ── comment ──────────────────────────────────────────────────────────────────────


def test_backlog_comment_adds_event_with_text(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "comment", cid, "--actor", "stud", "--body", "текст-комментария")
    assert res.returncode == 0, res.explain()
    comments = [e for e in _events(circuit, cid) if e[0] == "comment"]
    assert len(comments) == 1
    assert comments[0][1] == "STUD" and comments[0][4] == "текст-комментария"
    assert "текст-комментария" in _bl(circuit, "show", cid).stdout


def test_backlog_comment_reads_body_from_file(circuit, tmp_path):
    cid = _new_card(circuit)
    note = tmp_path / "update.md"
    note.write_text("Обновление из файла — кириллица", encoding="utf-8")
    res = _bl(circuit, "comment", cid, "--actor", "CORE", "--body-file", note)
    assert res.returncode == 0, res.explain()
    comments = [e for e in _events(circuit, cid) if e[0] == "comment"]
    assert comments[0][4] == "Обновление из файла — кириллица"


def test_backlog_comment_refuses_empty_text(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "comment", cid, "--actor", "CORE", "--body", "   ")
    assert res.returncode == 1, res.explain()
    assert not [e for e in _events(circuit, cid) if e[0] == "comment"]


def test_backlog_comment_unknown_card_exits_1(circuit):
    res = _bl(circuit, "comment", 99, "--actor", "CORE", "--body", "x")
    assert res.returncode == 1, res.explain()
    assert "99" in res.out, res.explain()


def test_backlog_comment_requires_actor(circuit):
    cid = _new_card(circuit)
    res = _bl(circuit, "comment", cid, "--body", "x")
    assert res.returncode == 2, res.explain()
    assert "--actor" in res.out, res.explain()


# ── --db ─────────────────────────────────────────────────────────────────────────


def test_backlog_db_flag_before_subcommand_targets_that_database(circuit, tmp_path):
    other = _copy_db(circuit.db, tmp_path / "other.db")
    res = _bl(circuit, "--db", other, "add", "--role", "CORE", "--title", "t",
              "--body", "b", "--done-when", "d")
    assert res.returncode == 0, res.explain()
    assert sqlite3.connect(str(other)).execute("SELECT COUNT(*) FROM backlog").fetchone()[0] == 1
    assert _card_count(circuit) == 0, "карточка ушла в названную базу, а не в базу контура"


def test_backlog_missing_db_is_refused_and_not_created(circuit, tmp_path):
    missing = tmp_path / "ghost.db"
    res = _bl(circuit, "--db", missing, "list", "--role", "CORE")
    assert res.returncode == 1, res.explain()
    assert not missing.exists(), "опечатка в пути не вправе рождать пустую базу"


# ═════════════════════════════════════════════════════════════════════════════════
# db-q.py
# ═════════════════════════════════════════════════════════════════════════════════


def _q(circuit, sql, *args):
    return circuit.run("db-q.py", sql, *[str(a) for a in args])


def test_dbq_select_prints_header_and_rows(circuit):
    res = _q(circuit, "SELECT role, lifecycle FROM roles ORDER BY role")
    assert res.returncode == 0, res.explain()
    lines = res.stdout.splitlines()
    assert lines[0].split("\t") == ["role", "lifecycle"]
    assert [ln.split("\t")[0] for ln in lines[1:]] == sorted(circuit.roles)


@pytest.mark.parametrize("sql", [
    "VALUES (1), (2)",
    "EXPLAIN SELECT 1",
    "PRAGMA table_info(roles)",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
])
def test_dbq_other_read_heads_work(circuit, sql):
    res = _q(circuit, sql)
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out


@pytest.mark.parametrize("sql", [
    "INSERT INTO meta (key, value) VALUES ('k', 'v')",
    "UPDATE roles SET lifecycle = 'dead'",
    "DELETE FROM roles",
    "DROP TABLE roles",
    "CREATE TABLE zzz (x)",
    "ALTER TABLE roles ADD COLUMN zzz TEXT",
    "  delete from roles",
])
def test_dbq_refuses_write_statements_and_database_is_unchanged(circuit, sql):
    before = _db_state(circuit)
    res = _q(circuit, sql)
    assert res.returncode != 0, res.explain()
    assert res.stdout.strip() == "", "пишущий запрос ничего не печатает как результат"
    assert _db_state(circuit) == before, "база обязана остаться прежней"


@pytest.mark.parametrize("sql", [
    "WITH t AS (SELECT 1 AS x) INSERT INTO meta (key, value) SELECT 'k', x FROM t",
    "SELECT 1; DELETE FROM roles",
    "PRAGMA user_version = 7",
])
def test_dbq_write_hidden_behind_a_read_head_is_stopped_by_second_lock(circuit, sql):
    # Первый затвор смотрит на первое слово; второй — база открыта только на чтение.
    before = _db_state(circuit)
    version_before = circuit.scalar("PRAGMA user_version")
    res = _q(circuit, sql)
    assert res.returncode != 0, res.explain()
    assert _db_state(circuit) == before
    assert circuit.scalar("PRAGMA user_version") == version_before


def test_dbq_unknown_table_refusal_hints_real_table_names(circuit):
    res = _q(circuit, "SELECT * FROM no_such_table")
    assert res.returncode == 1, res.explain()
    for name in ("roles", "backlog", "messages", "meta"):
        assert name in res.stderr, f"подсказка не назвала таблицу {name}\n" + res.explain()
    assert "Traceback" not in res.out


def test_dbq_unknown_column_refusal_hints_real_columns(circuit):
    res = _q(circuit, "SELECT no_such_column FROM roles")
    assert res.returncode == 1, res.explain()
    for column in ("role", "lifecycle", "zone"):
        assert column in res.stderr, f"подсказка не назвала колонку {column}\n" + res.explain()
    assert "Traceback" not in res.out


@pytest.mark.xfail(strict=True, reason=(
    "scripts/db-q.py:66 — «голова» запроса берётся первым словом до пробела "
    "(split(None, 1)[0].rstrip('(')), поэтому чтения без пробела после первого слова — "
    "SELECT*FROM roles, VALUES(1),(2), SELECT(1) — отказаны как «ПИШУЩИЙ запрос» (код 2), "
    "хотя это SELECT/VALUES; rstrip('(') рассчитан именно на такую форму, но не срабатывает."))
@pytest.mark.parametrize("sql", ["SELECT*FROM roles", "VALUES(1),(2)", "SELECT(1)"])
def test_dbq_reads_written_without_a_space_after_the_first_word(circuit, sql):
    res = _q(circuit, sql)
    assert res.returncode == 0, res.explain()


def test_dbq_syntax_error_is_refused_without_traceback(circuit):
    res = _q(circuit, "SELECT FROM WHERE")
    assert res.returncode == 1, res.explain()
    assert "Traceback" not in res.out


def test_dbq_limit_truncation_is_named_aloud(circuit):
    res = _q(circuit, "SELECT role FROM roles ORDER BY role", "--limit", 2)
    assert res.returncode == 0, res.explain()
    assert res.stdout.splitlines() == ["role", "COORD", "CORE"]
    assert "--limit" in res.stderr, "обрезание названо вслух\n" + res.explain()


def test_dbq_within_limit_prints_everything_without_warning(circuit):
    res = _q(circuit, "SELECT role FROM roles ORDER BY role", "--limit", 3)
    assert res.returncode == 0, res.explain()
    assert res.stdout.splitlines() == ["role", "COORD", "CORE", "STUD"]
    assert "--limit" not in res.stderr, res.explain()


def test_dbq_requires_a_query_argument(circuit):
    res = circuit.run("db-q.py")
    assert res.returncode == 2, res.explain()


def test_dbq_blank_query_is_refused(circuit):
    res = circuit.run("db-q.py", "   ")
    assert res.returncode != 0, res.explain()
    assert "Traceback" not in res.out, res.explain()


def test_dbq_db_flag_reads_the_named_database(circuit, tmp_path):
    other = _copy_db(circuit.db, tmp_path / "other.db")
    conn = sqlite3.connect(str(other))
    conn.execute("UPDATE meta SET value = 'copy-group' WHERE key = 'group_name'")
    conn.commit()
    conn.close()
    res = _q(circuit, "SELECT value FROM meta WHERE key = 'group_name'", "--db", other)
    assert res.returncode == 0, res.explain()
    assert "copy-group" in res.stdout
    assert _group_name(circuit) != "copy-group"


def test_dbq_relative_db_is_resolved_from_mezosync_root_not_from_cwd(circuit):
    # Процесс идёт из каталога контейнера, где базы с таким именем нет: от CWD путь не найти бы.
    assert not (circuit.root / "mezosync.db").exists(), "предусловие теста"
    res = _q(circuit, "SELECT value FROM meta WHERE key = 'group_name'", "--db", "mezosync.db")
    assert res.returncode == 0, res.explain()
    assert _group_name(circuit) in res.stdout, res.explain()


def test_dbq_missing_db_is_refused_and_not_created(circuit, tmp_path):
    missing = tmp_path / "ghost.db"
    res = _q(circuit, "SELECT 1", "--db", missing)
    assert res.returncode == 1, res.explain()
    assert not missing.exists()


# ═════════════════════════════════════════════════════════════════════════════════
# backup-db.py
# ═════════════════════════════════════════════════════════════════════════════════

# Таблицы поиска (FTS5) и их служебные таблицы: их содержимое — производное, не сверяем построчно.
FTS_PREFIX = "phoenix_records_fts"


def _backup(circuit, *args):
    return circuit.run("backup-db.py", *[str(a) for a in args])


def _restore(dump_file, target):
    """Развернуть текстовый дамп в новую базу — так его восстанавливают (sqlite3 new.db < dump)."""
    conn = sqlite3.connect(str(target))
    conn.executescript(dump_file.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def _seed_some_rows(circuit):
    cid = _new_card(circuit, "CORE", "backup-card")
    assert _bl(circuit, "comment", cid, "--actor", "CORE", "--body", "заметка").returncode == 0


def test_backup_dry_run_writes_nothing(circuit, tmp_path):
    out_dir = tmp_path / "mirror"
    out_dir.mkdir()
    out = out_dir / "dump.sql"
    before = _db_state(circuit)
    sql_files = set(circuit.root.rglob("*.sql"))
    res = _backup(circuit, "--out", out)
    assert res.returncode == 0, res.explain()
    assert "--apply" in res.out, "без --apply инструмент говорит, чем записать\n" + res.explain()
    assert not out.exists()
    assert list(out_dir.iterdir()) == [], "ни дампа, ни временных остатков"
    assert set(circuit.root.rglob("*.sql")) == sql_files, "и в самом контуре дампов не появилось"
    assert _db_state(circuit) == before
    # цель в несуществующей папке: без --apply не создаётся даже папка
    deep = tmp_path / "not-yet" / "sub" / "dump.sql"
    again = _backup(circuit, "--out", deep)
    assert again.returncode == 0, again.explain()
    assert not deep.parent.exists()


def test_backup_verify_flag_is_accepted_and_still_writes_nothing(circuit, tmp_path):
    out = tmp_path / "dump.sql"
    res = _backup(circuit, "--out", out, "--verify")
    assert res.returncode == 0, res.explain()
    assert not out.exists()


def test_backup_apply_writes_text_dump(circuit, tmp_path):
    out = tmp_path / "mirror" / "dump.sql"
    out.parent.mkdir()
    res = _backup(circuit, "--apply", "--out", out)
    assert res.returncode == 0, res.explain()
    text = out.read_text(encoding="utf-8")
    assert "CREATE TABLE" in text and "INSERT INTO" in text
    assert text.lstrip().startswith("--"), "дамп начинается комментарием-шапкой"
    leftovers = {p.name for p in out.parent.iterdir()} - {
        out.name, "local-paths.json", "local-copy", "local-copy.list"}
    assert not leftovers, f"временные остатки рядом с дампом: {leftovers}"


def test_backup_dump_restores_same_tables_and_row_counts(circuit, tmp_path):
    _seed_some_rows(circuit)
    out = tmp_path / "dump.sql"
    res = _backup(circuit, "--apply", "--out", out)
    assert res.returncode == 0, res.explain()

    restored = _restore(out, tmp_path / "restored.db")
    try:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        source = circuit.connect()
        try:
            assert schema_shape(restored) == schema_shape(source)
            want = {k: v for k, v in row_counts(source).items() if not k.startswith(FTS_PREFIX)}
        finally:
            source.close()
        got = {k: v for k, v in row_counts(restored).items() if not k.startswith(FTS_PREFIX)}
        assert got == want
        assert want["backlog"] == 1 and want["backlog_events"] >= 2, "дамп не пустой"
        assert restored.execute("SELECT title FROM backlog").fetchone()[0] == "backup-card"
        assert FTS_PREFIX in {r[0] for r in restored.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}, "таблица поиска восстановлена"
    finally:
        restored.close()


def test_backup_apply_twice_over_existing_dump_is_clean(circuit, tmp_path):
    out = tmp_path / "dump.sql"
    assert _backup(circuit, "--apply", "--out", out).returncode == 0
    again = _backup(circuit, "--apply", "--out", out)
    assert again.returncode == 0, again.explain()
    restored = _restore(out, tmp_path / "restored.db")
    restored.close()


def test_backup_flags_rows_that_vanished_from_the_database(circuit, tmp_path):
    # Строка исчезла мимо инструментов (прямая правка): сравнение с прежней выгрузкой краснеет.
    out = tmp_path / "dump.sql"
    assert _backup(circuit, "--apply", "--out", out).returncode == 0
    _exec(circuit, "DELETE FROM read_cursors WHERE reader_role = 'STUD'")
    before = out.read_bytes()
    res = _backup(circuit, "--out", out)
    assert res.returncode == 1, res.explain()
    assert "read_cursors" in res.out, "тревога называет таблицу\n" + res.explain()
    assert out.read_bytes() == before, "без --apply прежний дамп не тронут"


def test_backup_refuses_out_that_is_an_existing_directory(circuit, tmp_path):
    target_dir = tmp_path / "somedir"
    target_dir.mkdir()
    res = _backup(circuit, "--apply", "--out", target_dir)
    assert res.returncode == 1, res.explain()
    assert "Traceback" not in res.out, "отказ словами, а не трассировкой"
    assert list(target_dir.iterdir()) == [], "в каталог ничего не записано"


def test_backup_missing_db_is_refused(circuit, tmp_path):
    out = tmp_path / "dump.sql"
    res = _backup(circuit, "--apply", "--db", tmp_path / "ghost.db", "--out", out)
    assert res.returncode == 1, res.explain()
    assert not out.exists()


def test_backup_goes_to_mirror_repo_from_paths_file(circuit, tmp_path):
    # Без --out папка зеркала берётся из файла путей контура (ключ mirror_repo; относительный
    # путь — от контейнера). Файл путей лежит ВО временном контуре, наружу ничего не пишется.
    mirror = circuit.root / "mirror"
    mirror.mkdir()
    paths_file = circuit.mezosync / "local" / "paths.json"
    paths_file.parent.mkdir()
    paths_file.write_text('{"mirror_repo": "mirror"}', encoding="utf-8")
    res = _backup(circuit, "--apply")
    assert res.returncode == 0, res.explain()
    assert (mirror / "mezosync.dump.sql").is_file()
    copy = mirror / "local-paths.json"
    assert copy.is_file(), "рядом с дампом — копия файла путей"
    assert copy.read_bytes() == paths_file.read_bytes()


def test_backup_without_mirror_key_falls_back_to_backups_next_to_database(circuit):
    assert not (circuit.mezosync / "local" / "paths.json").exists(), "предусловие теста"
    res = _backup(circuit, "--apply")
    assert res.returncode == 0, res.explain()
    assert (circuit.mezosync / "backups" / "mezosync.dump.sql").is_file()


# ═════════════════════════════════════════════════════════════════════════════════
# bridge-groups.py
# ═════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def neighbour(circuit, tmp_path):
    """Второй контур: копия первого с другим именем группы (в своей временной папке)."""
    root = tmp_path / "neighbour"
    shutil.copytree(circuit.root, root)
    home = tmp_path / "neighbour-home"
    home.mkdir()
    twin = Circuit(root=root, home=home)
    _exec(twin, "UPDATE meta SET value = 'neighbour' WHERE key = 'group_name'")
    return twin


def _bridge(circuit, *args):
    return circuit.run("bridge-groups.py", *[str(a) for a in args])


def _links(circuit):
    return circuit.query(
        "SELECT source_group, target_group, target_db_path, description FROM cross_links "
        "ORDER BY id")


def test_bridge_links_source_to_target_one_way(circuit, neighbour):
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", neighbour.db,
                  "--description", "link-one")
    assert res.returncode == 0, res.explain()
    own = _group_name(circuit)
    assert own in res.out and "neighbour" in res.out, "вывод называет обе группы\n" + res.explain()
    rows = _links(circuit)
    assert len(rows) == 1
    source, target, target_path, description = rows[0]
    assert (source, target, description) == (own, "neighbour", "link-one")
    assert target_path and Path(target_path).resolve() == neighbour.db.resolve()
    assert _links(neighbour) == [], "без --bidirectional база соседа не тронута"


def test_bridge_relinking_the_same_pair_replaces_not_duplicates(circuit, neighbour):
    for text in ("first", "second"):
        res = _bridge(circuit, "--source-db", circuit.db, "--target-db", neighbour.db,
                      "--description", text)
        assert res.returncode == 0, res.explain()
    rows = _links(circuit)
    assert len(rows) == 1 and rows[0][3] == "second"


def test_bridge_bidirectional_writes_both_databases(circuit, neighbour):
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", neighbour.db,
                  "--description", "both-ways", "--bidirectional")
    assert res.returncode == 0, res.explain()
    own = _group_name(circuit)
    assert [(r[0], r[1]) for r in _links(circuit)] == [(own, "neighbour")]
    assert [(r[0], r[1]) for r in _links(neighbour)] == [("neighbour", own)]


def test_bridge_target_group_by_hand_does_not_open_neighbours_database(circuit, neighbour):
    # Сосед, чью базу открывать нельзя: имя группы называют рукой, его база не читается и не пишется.
    neighbour_before = _db_state(neighbour)
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", neighbour.db,
                  "--target-group", "named-by-hand", "--description", "from a letter")
    assert res.returncode == 0, res.explain()
    rows = _links(circuit)
    assert len(rows) == 1 and rows[0][1] == "named-by-hand", (
        "имя соседа — то, что назвали рукой, а не прочитанное из его базы")
    assert _db_state(neighbour) == neighbour_before


def test_bridge_target_group_needs_only_the_neighbours_container_dir(circuit, tmp_path):
    container = tmp_path / "far-neighbour"
    (container / ".mezosync").mkdir(parents=True)
    ghost_db = container / ".mezosync" / "mezosync.db"
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", ghost_db,
                  "--target-group", "far")
    assert res.returncode == 0, res.explain()
    assert _links(circuit)[0][1] == "far"
    assert not ghost_db.exists(), "чужую базу инструмент не создаёт"


def test_bridge_target_group_with_missing_container_is_refused(circuit, tmp_path):
    ghost_db = tmp_path / "no-container" / ".mezosync" / "mezosync.db"
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", ghost_db,
                  "--target-group", "far")
    assert res.returncode == 2, res.explain()
    assert _links(circuit) == []


def test_bridge_target_group_conflicts_with_bidirectional(circuit, neighbour):
    # --bidirectional с названным рукой соседом — это запись в чужую базу: отказ до записи.
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", neighbour.db,
                  "--target-group", "x", "--bidirectional")
    assert res.returncode == 2, res.explain()
    assert _links(circuit) == [] and _links(neighbour) == []


def test_bridge_missing_source_db_exits_2(circuit, neighbour, tmp_path):
    ghost = tmp_path / "ghost-source.db"
    res = _bridge(circuit, "--source-db", ghost, "--target-db", neighbour.db)
    assert res.returncode == 2, "отказ «❌» не должен выходить кодом 0 (карточка #684)\n" + res.explain()
    assert not ghost.exists()
    assert _links(neighbour) == []


def test_bridge_missing_target_db_exits_2(circuit, tmp_path):
    ghost = tmp_path / "ghost-target" / ".mezosync" / "mezosync.db"
    res = _bridge(circuit, "--source-db", circuit.db, "--target-db", ghost)
    assert res.returncode == 2, res.explain()
    assert _links(circuit) == [], "связь с несуществующей целью не записывается"
    assert not ghost.exists()


@pytest.mark.parametrize("missing", ["--source-db", "--target-db"])
def test_bridge_missing_required_arg_exits_2(circuit, neighbour, missing):
    args = {"--source-db": str(circuit.db), "--target-db": str(neighbour.db)}
    del args[missing]
    res = _bridge(circuit, *[x for kv in args.items() for x in kv])
    assert res.returncode == 2, res.explain()
    assert missing in res.out, res.explain()


# ═════════════════════════════════════════════════════════════════════════════════
# update-tools.py — только по локальному пакету (--source <REPO_ROOT>), без сети
# ═════════════════════════════════════════════════════════════════════════════════
#
# Без --source инструмент берёт источник из meta.template_source контура, а у контура,
# собранного из клона, это адрес общего репозитория — то есть сеть. Поэтому КАЖДЫЙ вызов
# ниже называет --source явно; временные каталоги инструмента уводятся в папку теста.

HAS_GIT = shutil.which("git") is not None
PACK_SCRIPTS = REPO_ROOT / "scripts"
# строки плана: «   ≠ имя …», «   ✋ имя …», «   ❓ имя …» — файл разошёлся с пакетом
DIVERGED_LINE = re.compile(r"^\s+(≠|✋|❓)\s", re.M)
NEW_FILE_LINE = re.compile(r"^\s+\+\s+\S", re.M)


def _update(circuit, tmp_path, *args, source=str(REPO_ROOT)):
    """update-tools.py по локальному источнику; временные каталоги — в папке теста."""
    if not HAS_GIT:
        pytest.skip("update-tools.py сличается с пакетом через git")
    scratch = tmp_path / "update-tmp"
    scratch.mkdir(exist_ok=True)
    env_extra = {"TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)}
    argv = ["--source", str(source)] + [str(a) for a in args]
    return circuit.run("update-tools.py", *argv, env_extra=env_extra)


def _scripts_hashes(circuit):
    return {p.relative_to(circuit.scripts).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(circuit.scripts.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def _meta(circuit):
    return dict(circuit.query("SELECT key, value FROM meta"))


def _lf(data):
    return data.replace(b"\r\n", b"\n")


def test_update_tools_plan_changes_nothing(circuit, tmp_path):
    scripts_before, db_before = _scripts_hashes(circuit), _db_state(circuit)
    res = _update(circuit, tmp_path)
    assert res.returncode == 0, res.explain()
    assert "Traceback" not in res.out, res.explain()
    assert _scripts_hashes(circuit) == scripts_before
    assert _db_state(circuit) == db_before, "без --apply не пишется ничего, и в базу тоже"
    assert not (circuit.mezosync / "released").exists()


def test_update_tools_fresh_circuit_has_no_diverged_tools(circuit, tmp_path):
    # Контур, только что собранный из этого же пакета, не отстал и не правлен ни в одном файле.
    res = _update(circuit, tmp_path)
    assert res.returncode == 0, res.explain()
    found = DIVERGED_LINE.findall(res.stdout)
    assert not found, f"отличающиеся/правленые файлы у свежего контура: {found}\n" + res.explain()


@pytest.mark.xfail(strict=True, reason=(
    "scripts/update-tools.py:953,1018 — план для свежесобранного контура из того же пакета "
    "предлагает «+ init-group.py … появится»: обход scripts/ источника не исключает сборщика, "
    "а scripts/init-group.py:309 нарочно НЕ кладёт его в контур («сборщик живёт в шаблоне, "
    "а не в контуре»; так же UPGRADE-2026-10-05). Ожидали «забирать нечего»."))
def test_update_tools_fresh_circuit_has_nothing_to_install(circuit, tmp_path):
    res = _update(circuit, tmp_path)
    assert res.returncode == 0, res.explain()
    assert not NEW_FILE_LINE.findall(res.stdout), res.explain()


def test_update_tools_plan_names_a_missing_tool_and_apply_restores_it(circuit, tmp_path):
    victim = circuit.scripts / "stats.py"
    victim.unlink()
    plan = _update(circuit, tmp_path)
    assert plan.returncode == 0, plan.explain()
    assert re.search(r"^\s+\+\s+stats\.py", plan.stdout, re.M), plan.explain()
    assert not victim.exists(), "план ничего не кладёт"

    applied = _update(circuit, tmp_path, "--apply")
    assert applied.returncode == 0, applied.explain()
    assert victim.is_file()
    assert _lf(victim.read_bytes()) == _lf((PACK_SCRIPTS / "stats.py").read_bytes())


def test_update_tools_own_edit_is_named_and_survives_apply(circuit, tmp_path):
    edited = circuit.scripts / "stats.py"
    edited.write_bytes(edited.read_bytes() + b"\n# local edit of this circuit\n")
    mine = edited.read_bytes()

    plan = _update(circuit, tmp_path)
    assert plan.returncode == 0, plan.explain()
    assert re.search(r"^\s+✋\s+stats\.py", plan.stdout, re.M), plan.explain()
    assert edited.read_bytes() == mine

    applied = _update(circuit, tmp_path, "--apply")
    assert applied.returncode == 0, applied.explain()
    assert edited.read_bytes() == mine, "файл, правленый у себя, не затирается"


def test_update_tools_one_off_source_does_not_become_the_recorded_source(circuit, tmp_path):
    recorded = _meta(circuit)["template_source"]
    res = _update(circuit, tmp_path, "--apply")
    assert res.returncode == 0, res.explain()
    assert _meta(circuit)["template_source"] == recorded, (
        "разовый --source не превращается в запись контура (карточка #604 ②)")


def test_update_tools_record_source_flag_records_it(circuit, tmp_path):
    res = _update(circuit, tmp_path, "--apply", "--record-source")
    assert res.returncode == 0, res.explain()
    assert _meta(circuit)["template_source"] == str(REPO_ROOT)


def test_update_tools_record_only_records_origin_and_touches_no_files(circuit, tmp_path):
    scripts_before = _scripts_hashes(circuit)
    res = _update(circuit, tmp_path, "--record-only")
    assert res.returncode == 0, res.explain()
    assert _scripts_hashes(circuit) == scripts_before, "режим записи файлов не трогает"
    meta = _meta(circuit)
    assert meta["template_source"] == str(REPO_ROOT)
    assert meta.get("template_files_sha"), "отпечатки установки записаны"


@pytest.mark.parametrize("flags", [
    ["--record-only", "--merge", "stats.py"],
    ["--release", "stats.py", "--record-only"],
])
def test_update_tools_conflicting_modes_are_refused_before_any_work(circuit, tmp_path, flags):
    scripts_before, db_before = _scripts_hashes(circuit), _db_state(circuit)
    res = _update(circuit, tmp_path, *flags)
    assert res.returncode == 1, res.explain()
    assert "--record-only" in res.out, res.explain()
    assert _scripts_hashes(circuit) == scripts_before and _db_state(circuit) == db_before


def test_update_tools_accept_merge_without_draft_is_refused(circuit, tmp_path):
    scripts_before = _scripts_hashes(circuit)
    res = _update(circuit, tmp_path, "--accept-merge", "stats.py", "--apply")
    assert res.returncode == 1, res.explain()
    assert "--merge" in res.out, "отказ называет шаг, которого не хватает\n" + res.explain()
    assert _scripts_hashes(circuit) == scripts_before


def test_update_tools_release_of_unknown_file_is_refused(circuit, tmp_path):
    scripts_before = _scripts_hashes(circuit)
    res = _update(circuit, tmp_path, "--release", "no-such-tool.py", "--apply")
    assert res.returncode == 1, res.explain()
    assert "no-such-tool.py" in res.out, res.explain()
    assert _scripts_hashes(circuit) == scripts_before


def test_update_tools_unreachable_local_source_is_refused_without_changes(circuit, tmp_path):
    ghost = tmp_path / "no-such-pack"      # нет такой папки: инструмент пробует git clone и отказывает
    scripts_before, db_before = _scripts_hashes(circuit), _db_state(circuit)
    res = _update(circuit, tmp_path, "--apply", source=ghost)
    assert res.returncode == 1, res.explain()
    assert str(ghost) in res.out, "отказ называет источник\n" + res.explain()
    assert _scripts_hashes(circuit) == scripts_before and _db_state(circuit) == db_before
