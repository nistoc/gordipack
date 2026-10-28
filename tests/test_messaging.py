# -*- coding: utf-8 -*-
"""Лента сообщений: write-message.py, read-messages.py, broadcast.py, read-broadcasts.py.

Контракт — из докстрок, argparse и комментариев самих скриптов; судим по коду выхода,
коротким устойчивым фрагментам вывода (номера, имена ролей, имена флагов) и итоговому
состоянию базы, а не по длинным русским фразам.

write-message.py (запись ноты в ленту):
  · нужна роль (--role) и ровно одно из --body / --file; приоритет — normal|high|critical;
  · critical без --basis (не короче 12 знаков) отклоняется ДО записи, с основанием —
    оно ложится первой строкой тела;
  · адресаты --to/--cc ложатся в message_addressee; имена через запятую ИЛИ пробел,
    регистр и «@» не значимы; «все» — свойство записки (messages.broadcast);
    опечатка и закрытая роль — отказ кодом 5 ДО записи; без адресата — только предупреждение;
  · та же нота того же автора в окне 30 минут — отказ кодом 3, обойти можно --again;
  · подпись «— РОЛЬ дата UTC» ставит и исправляет сам механизм;
  · --dry-run ничего не пишет; --reply-to/--resolves/--task/--poll/--ack/--reviewed
    пишут свои связи тем же вызовом; отказ сохранить память (--save-state) — код 4,
    но нота при этом записана.

read-messages.py (чтение не двигает отметку прочитанного):
  · чтение печатает батч и выдаёт токен из ДВУХ половин (первая — в первой строке вывода,
    вторая — в последней); отметку двигает только --ack <первая>-<вторая>, один раз;
  · пока батч не подтверждён, ридер перевыдаёт тот же батч и тот же токен;
  · --all, --index, --to-me, --wake токена не выдают и отметку не двигают;
  · незнакомая роль — ошибка, новая роль заводится только явным --register;
  · --limit 0 и отрицательный — отказ кодом 2.

broadcast.py / read-broadcasts.py:
  · broadcast — обычная нота с тегом ALL (priority normal) либо ALL+CTA (priority high);
  · инбокс — чужие объявления без моего ACK; --ack ID… пишет broadcast_acks;
    --status — кто из ролей подтвердил CTA, снятые роли в круг ожидаемых не входят.
"""

import json
import re
import sys

import pytest

from conftest import row_counts

# ── Помощники ────────────────────────────────────────────────────────────────────

SIGNATURE_RE = re.compile(r"^— (?P<role>[A-Z]+) (?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC$")
ID_RE = re.compile(r"#(\d+)")


def write(circuit, role, body=None, *extra):
    """write-message.py --role ROLE [--body BODY] ...extra → Result."""
    argv = ["--role", role]
    if body is not None:
        argv += ["--body", body]
    return circuit.run("write-message.py", *argv, *extra)


def note_id(res):
    """Номер записанной ноты из строки подтверждения «OK #N …»."""
    m = re.search(r"OK #(\d+)", res.stdout)
    assert m, "в выводе нет строки «OK #N»:\n" + res.explain()
    return int(m.group(1))


def post(circuit, role, body, *extra):
    """Записать ноту через CLI и вернуть её номер (код выхода обязан быть 0)."""
    res = write(circuit, role, body, *extra)
    assert res.returncode == 0, res.explain()
    nid = note_id(res)
    assert nid == circuit.scalar("SELECT MAX(id) FROM messages"), res.explain()
    return nid


def seed(circuit, writer, body, tags=None, to=(), cc=(), priority="normal"):
    """Положить ноту в messages прямо SQL-ом (быстро) — для тестов ЧТЕНИЯ."""
    conn = circuit.connect()
    try:
        cur = conn.execute(
            "INSERT INTO messages (writer_role, body_md, tags, priority, addressed_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (writer, body, json.dumps(tags or []), priority,
             "field" if (to or cc) else "unset"))
        mid = cur.lastrowid
        for kind, names in (("to", to), ("cc", cc)):
            for name in names:
                conn.execute(
                    "INSERT INTO message_addressee (message_id, role, kind, linked_by) "
                    "VALUES (?, ?, ?, 'field')", (mid, name, kind))
        conn.commit()
    finally:
        conn.close()
    return mid


def sql(circuit, statement, params=()):
    """Выполнить правку состояния базы (подготовка теста)."""
    conn = circuit.connect()
    try:
        conn.execute(statement, params)
        conn.commit()
    finally:
        conn.close()


def count(circuit, table):
    return circuit.scalar(f"SELECT COUNT(*) FROM {table}")


def cursor(circuit, role):
    return circuit.scalar("SELECT last_read_id FROM read_cursors WHERE reader_role = ?", (role,))


def batch_token(res):
    """Токен батча из ВЫВОДА: первая половина — в первой строке, вторая — в последней."""
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    assert lines, "вывод ридера пуст:\n" + res.explain()
    first = re.findall(r"\b([0-9a-f]{6})\b", lines[0])
    last = re.search(r"--ack\s+\S*-([0-9a-f]+)\s*$", lines[-1])
    assert first and last, "в выводе нет двух половин токена:\n" + res.explain()
    return f"{first[-1]}-{last.group(1)}"


def read_batch(circuit, role, *extra):
    """Прочитать батч; вернуть (Result, токен). Код выхода обязан быть 0."""
    res = circuit.run("read-messages.py", "--role", role, *extra)
    assert res.returncode == 0, res.explain()
    return res, batch_token(res)


def ack(circuit, role, token):
    return circuit.run("read-messages.py", "--role", role, "--ack", token)


def shown_ids(res):
    """Номера нот в указателе и инбоксе: строки вида «  #12 …»."""
    return [int(i) for i in re.findall(r"^\s*#(\d+)\b", res.stdout, re.M)]


def broadcast(circuit, role, body, *extra):
    res = circuit.run("broadcast.py", "--role", role, "--body", body, *extra)
    assert res.returncode == 0, res.explain()
    m = re.search(r"#(\d+)", res.stdout)
    assert m, res.explain()
    return int(m.group(1))


def status_line(res, mid):
    """Строка --status про CTA #mid (или None)."""
    for line in res.stdout.splitlines():
        if re.search(rf"CTA #{mid}\b", line):
            return line
    return None


def pending_roles(line):
    """Роли из хвоста «… · <статус>» строки --status (латинские имена тестовых ролей)."""
    tail = line.rsplit(" · ", 1)[-1]
    return set(re.findall(r"\b[A-Z]{2,}\b", tail))


# ══ write-message.py ═════════════════════════════════════════════════════════════
# ── Аргументы и отказы до записи ─────────────────────────────────────────────────


def test_write_minimal_note_is_recorded(circuit):
    res = write(circuit, "COORD", "plain note for the feed")
    assert res.returncode == 0, res.explain()
    nid = note_id(res)
    rows = circuit.query(
        "SELECT id, writer_role, body_md, tags, priority, timestamp FROM messages")
    assert len(rows) == 1
    mid, writer, body, tags, priority, ts = rows[0]
    assert (mid, writer, priority) == (nid, "COORD", "normal")
    assert "plain note for the feed" in body
    assert json.loads(tags) == []
    assert ts, "timestamp ноты не проставлен"


def test_write_missing_role_is_argparse_error(circuit):
    res = circuit.run("write-message.py", "--body", "no role")
    assert res.returncode == 2, res.explain()
    assert "--role" in res.out
    assert count(circuit, "messages") == 0


def test_write_requires_body_or_file(circuit):
    res = circuit.run("write-message.py", "--role", "COORD")
    assert res.returncode == 1, res.explain()
    assert "--body" in res.out and "--file" in res.out
    assert count(circuit, "messages") == 0


def test_write_body_and_file_together_refused(circuit, tmp_path):
    note = tmp_path / "note.md"
    note.write_text("from file", encoding="utf-8")
    res = write(circuit, "COORD", "from body", "--file", str(note))
    assert res.returncode == 1, res.explain()
    assert count(circuit, "messages") == 0


def test_write_missing_file_refused(circuit, tmp_path):
    missing = tmp_path / "no-such-note.md"
    res = write(circuit, "COORD", None, "--file", str(missing))
    assert res.returncode == 1, res.explain()
    assert "no-such-note.md" in res.out
    assert count(circuit, "messages") == 0


def test_write_invalid_priority_is_argparse_error(circuit):
    res = write(circuit, "COORD", "x", "--priority", "urgent")
    assert res.returncode == 2, res.explain()
    assert "--priority" in res.out
    assert count(circuit, "messages") == 0


def test_write_file_keeps_shell_special_characters(circuit, tmp_path):
    text = "Заголовок с `бэктиками`\n\nвторая строка: $(echo no) и \"кавычки\" и 'апострофы'\n"
    note = tmp_path / "note.md"
    note.write_text(text, encoding="utf-8")
    res = write(circuit, "COORD", None, "--file", str(note))
    assert res.returncode == 0, res.explain()
    body = circuit.scalar("SELECT body_md FROM messages")
    assert "`бэктиками`" in body
    assert "$(echo no)" in body
    assert '"кавычки"' in body


def test_write_role_case_is_normalised(circuit):
    post(circuit, "core", "lowercase role writes as upper")
    assert circuit.query("SELECT DISTINCT writer_role FROM messages") == [("CORE",)]


def test_write_priority_and_tags_are_stored(circuit):
    post(circuit, "COORD", "tagged high note", "--priority", "high", "--tags", "F-24, TRACK-X")
    priority, tags = circuit.query("SELECT priority, tags FROM messages")[0]
    assert priority == "high"
    assert json.loads(tags) == ["F-24", "TRACK-X"]


def test_note_updates_writer_status(circuit):
    nid = post(circuit, "COORD", "status via note")
    status = circuit.scalar("SELECT status FROM role_status WHERE role = 'COORD'")
    assert status and f"#{nid}" in status


# ── Подпись времени ──────────────────────────────────────────────────────────────


def test_write_stamps_signature_matching_timestamp(circuit):
    post(circuit, "COORD", "unsigned note")
    body, ts = circuit.query("SELECT body_md, timestamp FROM messages")[0]
    last = [ln for ln in body.splitlines() if ln.strip()][-1]
    m = SIGNATURE_RE.match(last)
    assert m, f"последняя строка не подпись: {last!r}"
    assert m.group("role") == "COORD"
    # подпись и колонка timestamp берутся из ОДНОГО значения — разойтись не могут
    assert m.group("stamp") == ts[:16]


def test_write_corrects_wrong_signature_time(circuit, tmp_path):
    note = tmp_path / "signed.md"
    note.write_text("Текст записки\n\n— COORD 2001-02-03 04:05 UTC\n", encoding="utf-8")
    res = write(circuit, "COORD", None, "--file", str(note))
    assert res.returncode == 0, res.explain()
    body, ts = circuit.query("SELECT body_md, timestamp FROM messages")[0]
    assert "2001-02-03" not in body, "чужое время подписи осталось в теле"
    signatures = [ln for ln in body.splitlines() if SIGNATURE_RE.match(ln)]
    assert len(signatures) == 1, "подпись должна остаться одна"
    assert SIGNATURE_RE.match(signatures[0]).group("stamp") == ts[:16]


# ── critical и основание ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("basis", [None, "short"])
def test_critical_without_enough_basis_refused_before_write(circuit, basis):
    extra = ["--priority", "critical"] + (["--basis", basis] if basis else [])
    res = write(circuit, "COORD", "critical claim", *extra)
    assert res.returncode != 0, res.explain()
    assert "--basis" in res.out
    assert count(circuit, "messages") == 0


def test_critical_with_basis_puts_it_on_first_line(circuit):
    basis = "owner word 2026-08-26 18:05 UTC"
    post(circuit, "COORD", "critical claim", "--priority", "critical", "--basis", basis)
    priority, body = circuit.query("SELECT priority, body_md FROM messages")[0]
    assert priority == "critical"
    assert basis in body.splitlines()[0]
    assert "critical claim" in body


def test_high_priority_needs_no_basis(circuit):
    res = write(circuit, "COORD", "high claim", "--priority", "high")
    assert res.returncode == 0, res.explain()


# ── Холостой прогон ──────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing(circuit):
    conn = circuit.connect()
    try:
        before = row_counts(conn)
    finally:
        conn.close()
    res = write(circuit, "COORD", "dry run note", "--to", "CORE", "--dry-run")
    assert res.returncode == 0, res.explain()
    dry_id = note_id(res)
    conn = circuit.connect()
    try:
        assert row_counts(conn) == before
    finally:
        conn.close()
    # «номера выше — то, что получилось бы»: настоящая запись получает тот же номер
    assert post(circuit, "COORD", "dry run note", "--to", "CORE") == dry_id


# ── Адресаты ─────────────────────────────────────────────────────────────────────


def test_to_and_cc_land_in_addressee_table(circuit):
    nid = post(circuit, "STUD", "addressed note", "--to", "core coord", "--cc", "@stud")
    rows = circuit.query(
        "SELECT role, kind FROM message_addressee WHERE message_id = ?", (nid,))
    assert sorted(rows) == [("COORD", "to"), ("CORE", "to"), ("STUD", "cc")]
    assert circuit.scalar("SELECT addressed_by FROM messages WHERE id = ?", (nid,)) == "field"


def test_to_accepts_comma_and_space_separators_equally(circuit):
    a = post(circuit, "STUD", "comma separated", "--to", "COORD,CORE")
    b = post(circuit, "STUD", "space separated", "--to", "COORD CORE")
    names = lambda mid: sorted(circuit.query(  # noqa: E731
        "SELECT role FROM message_addressee WHERE message_id = ?", (mid,)))
    assert names(a) == names(b) == [("COORD",), ("CORE",)]


@pytest.mark.parametrize("word", ["все", "ALL"])
def test_to_all_sets_broadcast_flag(circuit, word):
    nid = post(circuit, "COORD", f"note for {word}", "--to", word)
    assert circuit.scalar("SELECT broadcast FROM messages WHERE id = ?", (nid,)) == 1
    assert circuit.scalar("SELECT addressed_by FROM messages WHERE id = ?", (nid,)) == "field"
    assert count(circuit, "message_addressee") == 0, "«все» — не роль, строки адресата нет"


def test_to_owner_is_accepted(circuit):
    nid = post(circuit, "COORD", "note for the owner", "--to", "owner")
    rows = circuit.query("SELECT kind FROM message_addressee WHERE message_id = ?", (nid,))
    assert rows == [("to",)]


@pytest.mark.parametrize("flag", ["--to", "--cc"])
def test_unknown_addressee_refused_before_write(circuit, flag):
    res = write(circuit, "COORD", "ghost addressee", flag, "COORD,GHOST")
    assert res.returncode == 5, res.explain()
    assert "GHOST" in res.out
    assert count(circuit, "messages") == 0
    assert count(circuit, "message_addressee") == 0


@pytest.mark.parametrize("flag", ["--to", "--cc"])
def test_closed_role_addressee_refused(circuit, flag):
    sql(circuit, "UPDATE roles SET lifecycle = 'closed' WHERE role = 'STUD'")
    res = write(circuit, "COORD", "to a closed role", flag, "STUD")
    assert res.returncode == 5, res.explain()
    assert "STUD" in res.out
    assert count(circuit, "messages") == 0


def test_no_addressee_is_warning_not_refusal(circuit):
    res = write(circuit, "COORD", "note without addressee")
    assert res.returncode == 0, res.explain()
    assert "--to" in res.out, "предупреждение называет флаг --to"
    nid = note_id(res)
    assert circuit.scalar("SELECT addressed_by FROM messages WHERE id = ?", (nid,)) == "unset"
    assert count(circuit, "message_addressee") == 0


# ── Повтор той же ноты ───────────────────────────────────────────────────────────


def test_duplicate_note_refused_and_names_the_first(circuit):
    first = post(circuit, "COORD", "exactly the same text")
    res = write(circuit, "COORD", "exactly the same text")
    assert res.returncode == 3, res.explain()
    assert f"#{first}" in res.out
    assert "--again" in res.out
    assert count(circuit, "messages") == 1


def test_again_allows_deliberate_repeat(circuit):
    first = post(circuit, "COORD", "exactly the same text")
    res = write(circuit, "COORD", "exactly the same text", "--again", "nobody answered yet")
    assert res.returncode == 0, res.explain()
    assert count(circuit, "messages") == 2
    body = circuit.scalar("SELECT body_md FROM messages WHERE id = ?", (note_id(res),))
    assert f"#{first}" in body and "nobody answered yet" in body


def test_same_text_from_another_author_is_not_duplicate(circuit):
    post(circuit, "COORD", "exactly the same text")
    post(circuit, "CORE", "exactly the same text")
    assert count(circuit, "messages") == 2


def test_duplicate_outside_thirty_minute_window_is_allowed(circuit):
    first = post(circuit, "COORD", "exactly the same text")
    sql(circuit, "UPDATE messages SET timestamp = datetime('now', '-40 minutes') WHERE id = ?",
        (first,))
    post(circuit, "COORD", "exactly the same text")
    assert count(circuit, "messages") == 2


# ── Ответ, отмена, задача ────────────────────────────────────────────────────────


def test_reply_to_links_thread_and_keeps_root(circuit):
    a = post(circuit, "COORD", "question")
    b = post(circuit, "CORE", "answer", "--reply-to", str(a))
    c = post(circuit, "COORD", "follow-up", "--reply-to", str(b))
    rows = {r[0]: r[1:] for r in circuit.query(
        "SELECT message_id, reply_to, thread_id, kind FROM message_thread")}
    assert rows[b] == (a, a, "answer")
    assert rows[c][0] == b
    assert rows[c][1] == a, "тред держится за корень, а не за ближайшего родителя"


def test_resolves_marks_the_replied_note_resolved(circuit):
    a = post(circuit, "COORD", "old claim")
    b = post(circuit, "CORE", "withdrawn", "--reply-to", str(a), "--resolves")
    resolved = dict(circuit.query("SELECT id, resolved FROM messages"))
    assert resolved[a] == 1
    assert not resolved[b]


def test_task_link_is_stored(circuit):
    nid = post(circuit, "COORD", "note about card", "--task", "42")
    assert circuit.query("SELECT message_id, task_id FROM message_task") == [(nid, 42)]


# ── Heartbeat без ноты ───────────────────────────────────────────────────────────


def test_poll_without_note_updates_heartbeat_only(circuit):
    res = circuit.run("write-message.py", "--role", "CORE", "--poll", "working")
    assert res.returncode == 0, res.explain()
    assert count(circuit, "messages") == 0
    res = circuit.run("write-message.py", "--role", "CORE", "--poll", "idle")
    assert res.returncode == 0, res.explain()
    assert circuit.query("SELECT role, status FROM role_status") == [("CORE", "idle")]


# ── ACK вместе с запиской ────────────────────────────────────────────────────────


def test_ack_with_note_confirms_broadcast(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    nid = post(circuit, "CORE", "done", "--ack", str(cta))
    assert circuit.query("SELECT message_id, role FROM broadcast_acks") == [(cta, "CORE")]
    assert nid != cta


def test_ack_twice_does_not_duplicate_row(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    post(circuit, "CORE", "done", "--ack", str(cta))
    post(circuit, "CORE", "done again, different text", "--ack", str(cta))
    assert count(circuit, "broadcast_acks") == 1


def test_ack_requires_a_note(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    res = circuit.run("write-message.py", "--role", "CORE", "--ack", str(cta))
    assert res.returncode == 1, res.explain()
    assert count(circuit, "broadcast_acks") == 0


def test_ack_of_missing_note_warns_but_keeps_the_note(circuit):
    res = write(circuit, "CORE", "ack to nowhere", "--ack", "99999")
    assert res.returncode == 0, res.explain()
    assert "99999" in res.out
    assert count(circuit, "messages") == 1
    assert count(circuit, "broadcast_acks") == 0


# ── Жест разбора записки моста ───────────────────────────────────────────────────


def test_reviewed_needs_a_note(circuit):
    res = circuit.run("write-message.py", "--role", "STUD", "--poll", "x", "--reviewed", "a.md")
    assert res.returncode == 1, res.explain()
    assert "--reviewed" in res.out


def test_reviewed_accepts_repeated_flag_and_comma_list(circuit):
    nid = post(circuit, "STUD", "reviewed letters", "--reviewed", "a.md,b.md", "--reviewed", "c.md")
    rows = circuit.query("SELECT file_name, role, note_id FROM bridge_reviewed ORDER BY file_name")
    assert rows == [("a.md", "STUD", nid), ("b.md", "STUD", nid), ("c.md", "STUD", nid)]


# ── Снятый --md и память ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("flag", ["--md", "--no-md"])
def test_legacy_md_flags_do_not_break_the_write(circuit, flag):
    res = write(circuit, "COORD", "note with legacy flag", flag)
    assert res.returncode == 0, res.explain()
    assert count(circuit, "messages") == 1
    if flag == "--md":
        assert "--md" in res.out, "снятый флаг объясняет отказ, а не молчит"


def test_save_state_stores_memory_in_same_call(circuit, tmp_path):
    state = tmp_path / "state.md"
    state.write_text("Позиция: проверка сохранения памяти\n", encoding="utf-8")
    res = write(circuit, "CORE", "note with memory", "--save-state", str(state))
    assert res.returncode == 0, res.explain()
    body = circuit.scalar("SELECT body FROM phoenix WHERE role = 'CORE' AND section = 'state'")
    assert body and "проверка сохранения памяти" in body
    assert count(circuit, "messages") == 1


def test_save_state_refusal_is_exit_4_but_note_is_recorded(circuit, tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    res = write(circuit, "CORE", "note whose memory is refused", "--save-state", str(empty))
    assert res.returncode == 4, res.explain()
    assert count(circuit, "messages") == 1, "записка записана, повторять её не надо"
    assert circuit.scalar(
        "SELECT COUNT(*) FROM phoenix WHERE role = 'CORE' AND section = 'state'") == 0


# ══ read-messages.py ═════════════════════════════════════════════════════════════
# ── Чтение, токен, подтверждение ─────────────────────────────────────────────────


def test_read_missing_role_is_argparse_error(circuit):
    res = circuit.run("read-messages.py")
    assert res.returncode == 2, res.explain()
    assert "--role" in res.out


def test_read_empty_feed_reports_nothing_and_issues_no_token(circuit):
    res = circuit.run("read-messages.py", "--role", "STUD")
    assert res.returncode == 0, res.explain()
    assert "cursor=0" in res.stdout
    assert count(circuit, "read_batches") == 0
    assert cursor(circuit, "STUD") == 0


def test_read_prints_notes_in_order_and_does_not_move_cursor(circuit):
    ids = [seed(circuit, "COORD", f"first-note-{i}") for i in range(3)]
    res, token = read_batch(circuit, "STUD")
    positions = [res.stdout.index(f"first-note-{i}") for i in range(3)]
    assert positions == sorted(positions)
    assert cursor(circuit, "STUD") == 0, "чтение не двигает отметку прочитанного"
    row = circuit.query(
        "SELECT token, last_id, acked_at FROM read_batches WHERE role = 'STUD'")
    assert row == [(token, ids[-1], None)], "токен из вывода совпадает с записанным в базе"


def test_ack_moves_cursor_to_top_of_shown_batch(circuit):
    ids = [seed(circuit, "COORD", f"batch-note-{i}") for i in range(3)]
    _, token = read_batch(circuit, "STUD")
    res = ack(circuit, "STUD", token)
    assert res.returncode == 0, res.explain()
    assert cursor(circuit, "STUD") == ids[-1]
    assert circuit.scalar("SELECT acked_at FROM read_batches WHERE token = ?", (token,))
    # другие роли не затронуты
    assert cursor(circuit, "CORE") == 0
    again = circuit.run("read-messages.py", "--role", "STUD")
    assert again.returncode == 0, again.explain()
    assert "batch-note-0" not in again.stdout


def test_ack_token_is_one_shot(circuit):
    ids = [seed(circuit, "COORD", f"one-shot-{i}") for i in range(2)]
    _, token = read_batch(circuit, "STUD")
    assert ack(circuit, "STUD", token).returncode == 0
    seed(circuit, "COORD", "arrived after the ack")
    res = ack(circuit, "STUD", token)
    assert res.returncode == 1, res.explain()
    assert cursor(circuit, "STUD") == ids[-1]


@pytest.mark.parametrize("bad", ["deadbe-ef0000", ""])
def test_ack_with_unknown_token_refused(circuit, bad):
    seed(circuit, "COORD", "unread note")
    read_batch(circuit, "STUD")
    res = ack(circuit, "STUD", bad)
    assert res.returncode == 1, res.explain()
    assert cursor(circuit, "STUD") == 0


def test_ack_with_half_token_refused(circuit):
    seed(circuit, "COORD", "unread note")
    _, token = read_batch(circuit, "STUD")
    for half in token.split("-"):
        res = ack(circuit, "STUD", half)
        assert res.returncode == 1, res.explain()
    assert cursor(circuit, "STUD") == 0


def test_ack_token_of_another_role_refused(circuit):
    seed(circuit, "COORD", "unread note")
    _, token = read_batch(circuit, "STUD")
    res = ack(circuit, "CORE", token)
    assert res.returncode == 1, res.explain()
    assert cursor(circuit, "CORE") == 0 and cursor(circuit, "STUD") == 0


def test_unconfirmed_batch_is_reissued_with_same_token(circuit):
    first = seed(circuit, "COORD", "early note")
    _, token1 = read_batch(circuit, "STUD")
    late = seed(circuit, "COORD", "late-arrival-note")
    res2, token2 = read_batch(circuit, "STUD")
    assert token2 == token1
    assert "late-arrival-note" not in res2.stdout, "пришедшее позже ждёт следующего батча"
    assert count(circuit, "read_batches") == 1
    assert ack(circuit, "STUD", token2).returncode == 0
    assert cursor(circuit, "STUD") == first
    res3, token3 = read_batch(circuit, "STUD")
    assert "late-arrival-note" in res3.stdout
    assert token3 != token1
    assert ack(circuit, "STUD", token3).returncode == 0
    assert cursor(circuit, "STUD") == late


def test_limit_truncates_batch_and_ack_leaves_the_rest(circuit):
    ids = [seed(circuit, "COORD", f"limited-note-{i}") for i in range(3)]
    res, token = read_batch(circuit, "STUD", "--limit", "2")
    assert "limited-note-0" in res.stdout and "limited-note-1" in res.stdout
    assert "limited-note-2" not in res.stdout
    assert "--limit" in res.stdout, "обрезка названа вслух"
    assert ack(circuit, "STUD", token).returncode == 0
    assert cursor(circuit, "STUD") == ids[1]
    res2, _ = read_batch(circuit, "STUD")
    assert "limited-note-2" in res2.stdout and "limited-note-0" not in res2.stdout


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_limit_zero_or_negative_refused(circuit, limit):
    seed(circuit, "COORD", "unread note")
    res = circuit.run("read-messages.py", "--role", "STUD", "--limit", limit)
    assert res.returncode == 2, res.explain()
    assert count(circuit, "read_batches") == 0
    assert cursor(circuit, "STUD") == 0


def test_limit_not_a_number_is_argparse_error(circuit):
    res = circuit.run("read-messages.py", "--role", "STUD", "--limit", "many")
    assert res.returncode == 2, res.explain()


# ── Режимы без токена: --all, --index, --to-me, --wake ───────────────────────────


def test_all_lists_everything_without_token_or_cursor_move(circuit):
    ids = [seed(circuit, "COORD", f"history-note-{i}") for i in range(2)]
    _, token = read_batch(circuit, "STUD")
    assert ack(circuit, "STUD", token).returncode == 0
    batches_before = count(circuit, "read_batches")
    res = circuit.run("read-messages.py", "--role", "STUD", "--all")
    assert res.returncode == 0, res.explain()
    assert "history-note-0" in res.stdout and "history-note-1" in res.stdout
    assert count(circuit, "read_batches") == batches_before
    assert cursor(circuit, "STUD") == ids[-1]


def test_index_lists_ids_without_token_or_cursor_move(circuit):
    ids = [seed(circuit, "COORD", f"headline-{i}\nsecond line of the body") for i in range(3)]
    res = circuit.run("read-messages.py", "--role", "STUD", "--index")
    assert res.returncode == 0, res.explain()
    assert shown_ids(res) == ids
    assert "headline-1" in res.stdout
    assert "second line of the body" not in res.stdout, "указатель — заголовки, не тела"
    assert count(circuit, "read_batches") == 0
    assert cursor(circuit, "STUD") == 0


def test_index_with_limit_names_the_cut(circuit):
    ids = [seed(circuit, "COORD", f"headline-{i}") for i in range(3)]
    res = circuit.run("read-messages.py", "--role", "STUD", "--index", "--limit", "2")
    assert res.returncode == 0, res.explain()
    assert shown_ids(res) == ids[:2]
    assert "--limit" in res.stdout


def test_to_me_selects_only_notes_addressed_to_the_role(circuit):
    seed(circuit, "COORD", "to-me-direct", to=["CORE"])
    seed(circuit, "COORD", "to-me-copy-only", to=["COORD"], cc=["CORE"])
    seed(circuit, "COORD", "to-me-nobody")
    seed(circuit, "COORD", "to-me-other-role", to=["STUD"])
    res = circuit.run("read-messages.py", "--role", "CORE", "--to-me")
    assert res.returncode == 0, res.explain()
    assert "to-me-direct" in res.stdout
    for other in ("to-me-copy-only", "to-me-nobody", "to-me-other-role"):
        assert other not in res.stdout
    assert count(circuit, "read_batches") == 0, "отбор --to-me токена не выдаёт"
    assert cursor(circuit, "CORE") == 0


def test_tag_filter_shows_only_tagged_notes(circuit):
    seed(circuit, "COORD", "untagged-note")
    seed(circuit, "COORD", "tagged-note", tags=["TRACK-X"])
    res = circuit.run("read-messages.py", "--role", "STUD", "--tag", "TRACK-X")
    assert res.returncode == 0, res.explain()
    assert "tagged-note" in res.stdout and "untagged-note" not in res.stdout


@pytest.mark.xfail(strict=True, reason=(
    "scripts/read-messages.py:731 — токен выдаётся и для выборки --tag (подмножество ленты), "
    "и --ack двигает отметку на верх ПОКАЗАННОГО: непоказанная ранняя нота без тега "
    "молча выпадает из непрочитанных, а cursor_segments записывает отрезок как «read». "
    "Для --to-me это закрыто (issue = ... and not args.to_me), для --tag — нет."))
def test_ack_of_tag_filtered_batch_must_not_swallow_unshown_notes(circuit):
    skipped = seed(circuit, "COORD", "untagged-early-note")
    seed(circuit, "COORD", "tagged-note", tags=["TRACK-X"])
    _, token = read_batch(circuit, "STUD", "--tag", "TRACK-X")
    assert ack(circuit, "STUD", token).returncode == 0
    rest = circuit.run("read-messages.py", "--role", "STUD", "--index")
    assert skipped in shown_ids(rest), (
        "нота, которой не показывали, исчезла из непрочитанных:\n" + rest.explain())


def test_wake_overview_does_not_move_cursor_or_issue_token(circuit):
    seed(circuit, "CORE", "wake-personal-note", to=["COORD"])
    seed(circuit, "CORE", "wake-general-note")
    res = circuit.run("read-messages.py", "--role", "COORD", "--wake")
    assert res.returncode == 0, res.explain()
    assert "wake-personal-note" in res.stdout
    assert count(circuit, "read_batches") == 0
    assert cursor(circuit, "COORD") == 0


# ── Роли ─────────────────────────────────────────────────────────────────────────


def test_unknown_role_is_error_without_register(circuit):
    seed(circuit, "COORD", "unread note")
    res = circuit.run("read-messages.py", "--role", "GHOST")
    assert res.returncode == 1, res.explain()
    assert "--register" in res.out
    assert "GHOST" in res.out
    assert cursor(circuit, "GHOST") is None, "опечатка в --role не заводит призрака"
    assert count(circuit, "read_batches") == 0


def test_register_creates_cursor_for_new_role(circuit):
    seed(circuit, "COORD", "unread note")
    res = circuit.run("read-messages.py", "--role", "NEWBIE", "--register")
    assert res.returncode == 0, res.explain()
    assert cursor(circuit, "NEWBIE") == 0
    assert "unread note" in res.stdout


def test_register_does_not_reset_existing_cursor(circuit):
    seed(circuit, "COORD", "unread note")
    _, token = read_batch(circuit, "STUD")
    assert ack(circuit, "STUD", token).returncode == 0
    moved = cursor(circuit, "STUD")
    assert moved > 0
    res = circuit.run("read-messages.py", "--role", "STUD", "--register")
    assert res.returncode == 0, res.explain()
    assert cursor(circuit, "STUD") == moved


def test_reader_role_case_is_normalised(circuit):
    top = seed(circuit, "COORD", "lowercase reader note")
    res, token = read_batch(circuit, "stud")
    assert "lowercase reader note" in res.stdout
    assert ack(circuit, "stud", token).returncode == 0
    assert cursor(circuit, "STUD") == top
    roles = {r[0] for r in circuit.query("SELECT reader_role FROM read_cursors")}
    assert roles == {"COORD", "CORE", "STUD"}, "строки в нижнем регистре не заводятся"


# ── Проход заголовками ───────────────────────────────────────────────────────────


def test_pass_by_index_requires_basis(circuit):
    seed(circuit, "COORD", "pass-note")
    res = circuit.run("read-messages.py", "--role", "STUD", "--pass-by-index")
    assert res.returncode == 2, res.explain()
    assert "--basis" in res.out
    assert cursor(circuit, "STUD") == 0


def test_pass_by_index_with_basis_moves_cursor_and_records_it(circuit):
    top = [seed(circuit, "COORD", f"pass-note-{i}") for i in range(2)][-1]
    basis = "headers only, bodies are not needed"
    res = circuit.run("read-messages.py", "--role", "STUD", "--pass-by-index", "--basis", basis)
    assert res.returncode == 0, res.explain()
    assert cursor(circuit, "STUD") == top
    segments = circuit.query(
        "SELECT from_id, to_id, kind, basis FROM cursor_segments WHERE role = 'STUD'")
    assert segments == [(1, top, "declared", basis)]


def test_to_me_records_shown_bodies_and_pass_by_index_cuts_around_them(circuit):
    first = seed(circuit, "COORD", "personal-one", to=["STUD"])
    middle = seed(circuit, "COORD", "general-two")
    last = seed(circuit, "COORD", "personal-three", to=["STUD"])
    res = circuit.run("read-messages.py", "--role", "STUD", "--to-me")
    assert res.returncode == 0, res.explain()
    assert cursor(circuit, "STUD") == 0
    marks = circuit.query(
        "SELECT from_id, to_id FROM cursor_segments WHERE role = 'STUD' AND kind = 'read' "
        "ORDER BY from_id")
    assert marks == [(first, first), (last, last)], "показанные тела записаны по одной"
    res = circuit.run("read-messages.py", "--role", "STUD", "--pass-by-index",
                      "--basis", "headers only, bodies are not needed")
    assert res.returncode == 0, res.explain()
    declared = circuit.query(
        "SELECT from_id, to_id FROM cursor_segments WHERE role = 'STUD' AND kind = 'declared'")
    assert declared == [(middle, middle)], "прочитанное телами в «не дошло» не попадает"
    assert cursor(circuit, "STUD") == last


# ══ broadcast.py ═════════════════════════════════════════════════════════════════


def test_broadcast_fyi_is_note_with_all_tag(circuit):
    res = circuit.run("broadcast.py", "--role", "COORD", "--body", "service is up")
    assert res.returncode == 0, res.explain()
    rows = circuit.query("SELECT id, writer_role, body_md, tags, priority FROM messages")
    assert len(rows) == 1
    mid, writer, body, tags, priority = rows[0]
    assert f"#{mid}" in res.stdout
    assert (writer, body, priority) == ("COORD", "service is up", "normal")
    assert json.loads(tags) == ["ALL"]


def test_broadcast_cta_is_high_priority_with_cta_tag(circuit):
    res = circuit.run("broadcast.py", "--role", "COORD", "--body", "save your memory", "--cta")
    assert res.returncode == 0, res.explain()
    priority, tags = circuit.query("SELECT priority, tags FROM messages")[0]
    assert priority == "high"
    assert json.loads(tags) == ["ALL", "CTA"]
    assert "--status" in res.stdout, "после CTA сказано, где смотреть статус"


def test_broadcast_extra_tags_do_not_duplicate_all(circuit):
    broadcast(circuit, "COORD", "tagged announcement", "--tags", "release, ui,ALL")
    tags = json.loads(circuit.scalar("SELECT tags FROM messages"))
    assert tags == ["ALL", "release", "ui"]


@pytest.mark.parametrize("argv, missing", [
    (["--role", "COORD"], "--body"),
    (["--body", "no role"], "--role"),
])
def test_broadcast_missing_required_is_argparse_error(circuit, argv, missing):
    res = circuit.run("broadcast.py", *argv)
    assert res.returncode == 2, res.explain()
    assert missing in res.out
    assert count(circuit, "messages") == 0


# Было xfail до починки scripts/broadcast.py (имя роли — верхним регистром на входе).
def test_broadcast_role_case_is_normalised(circuit):
    broadcast(circuit, "coord", "lowercase author")
    assert circuit.scalar("SELECT writer_role FROM messages") == "COORD"


# ══ read-broadcasts.py ═══════════════════════════════════════════════════════════
# ── Инбокс ───────────────────────────────────────────────────────────────────────


def test_inbox_without_role_or_status_refused(circuit):
    res = circuit.run("read-broadcasts.py")
    assert res.returncode == 1, res.explain()
    assert "--role" in res.out


def test_inbox_shows_foreign_broadcasts_only(circuit):
    foreign = broadcast(circuit, "COORD", "announcement from coord")
    own = broadcast(circuit, "CORE", "announcement from core")
    plain = post(circuit, "COORD", "ordinary note, not a broadcast", "--to", "CORE")
    res = circuit.run("read-broadcasts.py", "--role", "CORE")
    assert res.returncode == 0, res.explain()
    assert shown_ids(res) == [foreign]
    assert own not in shown_ids(res) and plain not in shown_ids(res)
    assert "announcement from coord" in res.stdout


def test_inbox_of_cta_prompts_to_ack_with_ids(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    res = circuit.run("read-broadcasts.py", "--role", "CORE")
    assert res.returncode == 0, res.explain()
    assert shown_ids(res) == [cta]
    assert "--ack" in res.stdout and f"--ack {cta}" in res.stdout


def test_ack_hides_broadcast_from_inbox_but_all_still_lists_it(circuit):
    bid = broadcast(circuit, "COORD", "announcement")
    res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", str(bid))
    assert res.returncode == 0, res.explain()
    assert circuit.query("SELECT message_id, role FROM broadcast_acks") == [(bid, "CORE")]
    assert shown_ids(circuit.run("read-broadcasts.py", "--role", "CORE")) == []
    listing = circuit.run("read-broadcasts.py", "--role", "CORE", "--all")
    assert shown_ids(listing) == [bid]
    # чужой ACK инбокс другой роли не гасит
    assert shown_ids(circuit.run("read-broadcasts.py", "--role", "STUD")) == [bid]


def test_ack_requires_role(circuit):
    bid = broadcast(circuit, "COORD", "announcement")
    res = circuit.run("read-broadcasts.py", "--ack", str(bid))
    assert res.returncode == 1, res.explain()
    assert "--role" in res.out
    assert count(circuit, "broadcast_acks") == 0


def test_ack_several_ids_and_repeat_is_idempotent(circuit):
    a = broadcast(circuit, "COORD", "first announcement")
    b = broadcast(circuit, "COORD", "second announcement", "--cta")
    for _ in range(2):
        res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", str(a), str(b))
        assert res.returncode == 0, res.explain()
    assert sorted(circuit.query("SELECT message_id, role FROM broadcast_acks")) == [
        (a, "CORE"), (b, "CORE")]


def test_ack_of_plain_note_or_missing_id_is_skipped(circuit):
    plain = post(circuit, "COORD", "ordinary note", "--to", "CORE")
    res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", str(plain), "99999")
    assert res.returncode == 0, res.explain()
    assert count(circuit, "broadcast_acks") == 0


def test_ack_with_non_numeric_id_is_argparse_error(circuit):
    res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", "abc")
    assert res.returncode == 2, res.explain()
    assert count(circuit, "broadcast_acks") == 0


def test_ack_role_is_stored_in_upper_case(circuit):
    bid = broadcast(circuit, "COORD", "announcement")
    res = circuit.run("read-broadcasts.py", "--role", "core", "--ack", str(bid))
    assert res.returncode == 0, res.explain()
    assert circuit.query("SELECT role FROM broadcast_acks") == [("CORE",)]


@pytest.mark.xfail(strict=True, reason=(
    "scripts/read-broadcasts.py:124 — инбокс сверяет ACK по роли КАК НАБРАНО, а --ack пишет "
    "role.upper() (строка 167): подтвердив как --role core, роль в этом же регистре снова видит "
    "то же объявление непрочитанным, хотя в broadcast_acks лежит 'CORE'. --status при этом "
    "нормализует регистр, и два отчёта расходятся."))
def test_inbox_after_ack_with_lowercase_role_is_empty(circuit):
    bid = broadcast(circuit, "COORD", "announcement")
    assert circuit.run("read-broadcasts.py", "--role", "core", "--ack", str(bid)).returncode == 0
    res = circuit.run("read-broadcasts.py", "--role", "core")
    assert shown_ids(res) == [], "подтверждённое объявление снова в инбоксе:\n" + res.explain()


def test_cta_tag_without_all_is_still_ackable(circuit):
    cta = post(circuit, "COORD", "call to action without ALL tag", "--tags", "CTA",
               "--to", "CORE")
    res = circuit.run("read-broadcasts.py", "--role", "CORE")
    assert shown_ids(res) == [cta], res.explain()
    res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", str(cta))
    assert res.returncode == 0, res.explain()
    assert circuit.query("SELECT message_id, role FROM broadcast_acks") == [(cta, "CORE")]


def test_archived_broadcast_is_still_visible_and_ackable(circuit):
    sql(circuit,
        "INSERT INTO messages_archive (id, writer_role, timestamp, body_md, tags, priority, "
        "moved_by, rule) VALUES (900, 'COORD', '2026-01-01 00:00:00', 'archived call', "
        "'[\"ALL\", \"CTA\"]', 'high', 'test', 'test')")
    assert shown_ids(circuit.run("read-broadcasts.py", "--role", "CORE")) == [900]
    res = circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", "900")
    assert res.returncode == 0, res.explain()
    assert circuit.query("SELECT message_id, role FROM broadcast_acks") == [(900, "CORE")]
    status = circuit.run("read-broadcasts.py", "--status")
    assert status_line(status, 900), status.explain()


# ── Статус CTA ───────────────────────────────────────────────────────────────────


def test_status_without_cta_lists_nothing(circuit):
    broadcast(circuit, "COORD", "only an fyi")
    res = circuit.run("read-broadcasts.py", "--status")
    assert res.returncode == 0, res.explain()
    assert "CTA #" not in res.stdout


def test_status_tracks_pending_roles_until_all_acked(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    res = circuit.run("read-broadcasts.py", "--status")
    assert res.returncode == 0, res.explain()
    line = status_line(res, cta)
    assert line, res.explain()
    assert pending_roles(line) == {"CORE", "STUD"}, "автор себя не подтверждает"

    circuit.run("read-broadcasts.py", "--role", "CORE", "--ack", str(cta))
    line = status_line(circuit.run("read-broadcasts.py", "--status"), cta)
    assert pending_roles(line) == {"STUD"}

    circuit.run("read-broadcasts.py", "--role", "STUD", "--ack", str(cta))
    line = status_line(circuit.run("read-broadcasts.py", "--status"), cta)
    assert pending_roles(line) == set(), line


def test_status_excludes_closed_roles_from_waiting(circuit):
    cta = broadcast(circuit, "COORD", "do the thing", "--cta")
    sql(circuit, "UPDATE roles SET lifecycle = 'closed' WHERE role = 'STUD'")
    res = circuit.run("read-broadcasts.py", "--status")
    assert res.returncode == 0, res.explain()
    assert pending_roles(status_line(res, cta)) == {"CORE"}


# ══ Общее для четырёх скриптов ═══════════════════════════════════════════════════

ALL_SCRIPTS = [
    ("write-message.py", ["--role", "COORD", "--body", "common check"]),
    ("read-messages.py", ["--role", "COORD"]),
    ("broadcast.py", ["--role", "COORD", "--body", "common check"]),
    ("read-broadcasts.py", ["--role", "COORD"]),
]


@pytest.mark.parametrize("script", [s for s, _ in ALL_SCRIPTS])
def test_help_exits_zero(circuit, script):
    res = circuit.run(script, "--help")
    assert res.returncode == 0, res.explain()
    assert "usage" in res.stdout.lower()


@pytest.mark.parametrize("script, argv", ALL_SCRIPTS)
def test_missing_db_is_refused_without_creating_it(circuit, tmp_path, script, argv):
    missing = tmp_path / "nowhere" / "none.db"
    res = circuit.run(script, *argv, "--db", str(missing))
    assert res.returncode == 1, res.explain()
    assert not missing.exists()
    assert count(circuit, "messages") == 0


@pytest.mark.parametrize("script, argv", ALL_SCRIPTS)
def test_explicit_absolute_db_works_like_default(circuit, script, argv):
    res = circuit.run(script, *argv, "--db", str(circuit.db))
    assert res.returncode == 0, res.explain()
    if script in ("write-message.py", "broadcast.py"):
        assert count(circuit, "messages") == 1


if __name__ == "__main__":  # запуск файла напрямую — через pytest, как и все тесты пакета
    sys.exit(pytest.main([__file__, "-q"]))
