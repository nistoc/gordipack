# -*- coding: utf-8 -*-
"""Память ролей и свод правил: save-phoenix.py · read-phoenix.py · set-rule.py ·
export-rules.py · rules-from-pack.py — каждый отдельным процессом в свежем контуре.

Контракт — из докстрок, справки (--help) и комментариев самих скриптов:
  · память роли: сохранённое читается назад; --dry-run не пишет ничего; пустое тело — отказ;
    обвал объёма (≥40 % при размере от 400 знаков) — отказ без --allow-shrink; --expect-version
    с устаревшим номером — отказ; --restore возвращает версию НОВОЙ версией; --confirm
    ставит время взгляда, не трогая тело; секция вне списка — отказ argparse (код 2);
  · правило: без --apply — холостой прогон; --apply пишет правило, журнал правок и ПЕРЕСОБИРАЕТ
    зеркало generated/sync.rules.md; при отказе и при сухом прогоне зеркало не трогается
    (README, «Почему пересборка файла с правилами — механизм»); база не живая — зеркало
    живого контура не трогается; --revoke и --skill-delivery — отдельные ветки;
  · export-rules.py: без --apply ничего не пишет, с --apply пишет зеркало из базы;
  · rules-from-pack.py: на свежем контуре расхождений с пакетом нет; код 2 у --summary
    при отказе поиска баз; пишущие режимы требуют --actor и --word.

Подход: код выхода, короткие устойчивые куски вывода (ключи, номера версий, имена ролей),
итоговое состояние базы и файла. Зеркало перед проверкой «не тронуто» заменяется
заведомо чужим текстом (SENTINEL): совпадение побайтно значит, что его не перезаписали.
"""

import itertools
import re
import sqlite3
from pathlib import Path

import pytest

from conftest import REPO_ROOT

PACK = REPO_ROOT                       # пакет, против которого сверяются правила контура
SENTINEL = "SENTINEL: этот файл не должен переписываться отказом или сухим прогоном\n"
NEW_KEY = "zz-contract-probe"          # правила, которых нет ни в контуре, ни в пакете
BASIS = ("--basis", "замер: проба контрактного теста", "--authorized-by", "owner",
         "--source-ref", "#test", "--expiry-kind", "forever")

_COUNTER = itertools.count(1)
STATE_WORDS = ("new", "pack-changed", "local-changed", "both-changed", "no-base",
               "removed", "retired-here", "skipped", "same")
SECTIONS = ("identity", "state", "plan", "history", "launcher", "rebirth", "sources")


# ═══ помощники ═══════════════════════════════════════════════════════════════════════


def put(circuit, text, suffix=".md"):
    """Положить текст файлом РЯДОМ с контуром (байтами, без перевода строк платформы)."""
    d = circuit.root.parent / "inputs"
    d.mkdir(exist_ok=True)
    p = d / f"in-{next(_COUNTER)}{suffix}"
    p.write_bytes(text.encode("utf-8"))
    return p


def body_of(tag, lines=20):
    """Многострочное тело, где каждая строка длиннее 12 знаков (так её видит отчёт о потере)."""
    return "\n".join(f"{tag} строка {i:03d}: содержательный текст про дело номер {i}"
                     for i in range(lines)) + "\n"


def save(circuit, role, section, text, *extra, env_extra=None):
    """save-phoenix.py с телом из файла — так роль передаёт длинное и многострочное."""
    return circuit.run("save-phoenix.py", "--role", role, "--section", section,
                       "--file", put(circuit, text), *extra, env_extra=env_extra)


def mem(circuit, role, section):
    """(тело, saved_at, confirmed_at) раздела или None."""
    rows = circuit.query("SELECT body, saved_at, confirmed_at FROM phoenix "
                         "WHERE role=? AND section=?", (role, section))
    return rows[0] if rows else None


def versions(circuit, role, section):
    """Версии раздела по возрастанию номера: (id, actor, reason, body_chars, body)."""
    return circuit.query("SELECT id, actor, reason, body_chars, body FROM phoenix_history "
                         "WHERE role=? AND section=? ORDER BY id", (role, section))


def dump_db(circuit):
    """Всё содержимое всех обычных таблиц — для проверки «база не изменилась»."""
    conn = circuit.connect()
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND COALESCE(sql, '') NOT LIKE 'CREATE VIRTUAL%' ORDER BY name")]
        return {n: sorted(map(repr, conn.execute(f'SELECT * FROM "{n}"').fetchall()))
                for n in names}
    finally:
        conn.close()


def sql(circuit, statement, params=()):
    """Подготовка состояния прямым SQL (то, что в живом контуре сделала бы чужая рука)."""
    conn = circuit.connect()
    try:
        conn.execute(statement, params)
        conn.commit()
    finally:
        conn.close()


def audit(circuit, action=None, target=None):
    """Строки audit_log по возрастанию номера, словарями."""
    conn = circuit.connect()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows
            if (action is None or r["action"] == action)
            and (target is None or r["target"] == target)]


def rule(circuit, key):
    conn = circuit.connect()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM rules WHERE rule_key=?", (key,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def rule_keys(circuit, where="1=1"):
    return [r[0] for r in circuit.query(f"SELECT rule_key FROM rules WHERE {where} "
                                        "ORDER BY rule_key")]


def set_rule(circuit, key, text, *extra, env_extra=None):
    return circuit.run("set-rule.py", "--key", key, "--body-file", put(circuit, text),
                       *extra, env_extra=env_extra)


def mirror_path(circuit):
    return circuit.mezosync / "generated" / "sync.rules.md"


def plant_sentinel(circuit):
    """Заменить зеркало чужим текстом: любая пересборка станет видна."""
    p = mirror_path(circuit)
    assert p.parent.is_dir(), "в свежем контуре нет каталога generated/ — нечем проверять зеркало"
    p.write_bytes(SENTINEL.encode("utf-8"))
    return p


def mirror_text(circuit):
    return mirror_path(circuit).read_bytes().decode("utf-8")


def mirror_untouched(circuit):
    return mirror_text(circuit) == SENTINEL


def mirror_keys(text):
    """Ключи правил в заголовках зеркала («### `ключ` 🔒владелец vN»)."""
    return re.findall(r"^### .*?`([^`]+)` 🔒", text, re.M)


def heading_of(text, key):
    m = re.search(rf"^### .*?`{re.escape(key)}` 🔒.*$", text, re.M)
    return m.group(0) if m else None


def active_key(circuit, locked_by=None):
    """Первый действующий ключ свода (при желании — с нужным замком)."""
    where = "status='active'" + (f" AND locked_by='{locked_by}'" if locked_by else "")
    keys = rule_keys(circuit, where)
    assert keys, f"в свежем контуре нет действующих правил ({where})"
    return keys[0]


def pack_run(circuit, *args):
    return circuit.run("rules-from-pack.py", "--source", str(PACK), *args)


def pack_counts(res):
    """Последняя строка списка — «итог: new 0 · pack-changed 0 · … · same 65 · only-yours 0»."""
    last = res.stdout.strip().splitlines()[-1]
    counts = {name: int(n) for name, n in re.findall(r"([a-z]+(?:-[a-z]+)?) (\d+)", last)}
    assert set(counts) == {*STATE_WORDS, "only-yours"}, res.explain()
    return counts


def pack_listed(res):
    """Строки списка: [(ключ, состояние)] — по слову состояния, а не по русскому пояснению."""
    pattern = re.compile(r"^  (?P<key>[a-z0-9._-]+)\s+(?P<set>\S+)\s+.*?\s"
                         r"(?P<state>" + "|".join(STATE_WORDS) + r")\s", re.M)
    return [(m["key"], m["state"]) for m in pattern.finditer(res.stdout)]


# ═══ save-phoenix.py и read-phoenix.py: сохранить и прочитать ═════════════════════════


def test_save_then_read_back(circuit):
    token = "ПАМЯТЬ-CORE-7f3a"
    body = body_of(token)
    res = save(circuit, "CORE", "state", body)
    assert res.returncode == 0, res.explain()
    assert "phoenix/CORE/state" in res.stdout, res.explain()
    assert mem(circuit, "CORE", "state")[0] == body

    back = circuit.run("read-phoenix.py", "--role", "CORE", "--section", "state")
    assert back.returncode == 0, back.explain()
    assert "CORE" in back.stdout and token in back.stdout, back.explain()
    assert body.strip() in back.stdout, "читалка обязана показать тело раздела целиком"


def test_body_flag_and_short_first_save(circuit):
    """Короткая секция впервые (launcher — законно одна строка): порога «не меньше N знаков» нет."""
    res = circuit.run("save-phoenix.py", "--role", "STUD", "--section", "launcher",
                      "--body", "Прочитай память из базы и начни работать.")
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "STUD", "launcher")[0] == "Прочитай память из базы и начни работать."
    back = circuit.run("read-phoenix.py", "--role", "STUD", "--section", "launcher")
    assert back.returncode == 0 and "Прочитай память из базы" in back.stdout, back.explain()


def test_file_with_windows_line_endings_is_stored_with_lf(circuit):
    """--file читается с приведением окончаний строк (карточка #707): «\\r» в тело не попадает."""
    text = "первая строка достаточной длины\r\nвторая строка достаточной длины\r\n"
    res = save(circuit, "CORE", "plan", text)
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "plan")[0] == text.replace("\r\n", "\n")


def test_role_name_is_normalised_to_upper_case(circuit):
    """Иначе `--role core` завёл бы вторую память рядом с CORE, а читалка вернула бы старую."""
    res = save(circuit, "core", "plan", body_of("РЕГИСТР"))
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "plan") is not None
    assert mem(circuit, "core", "plan") is None
    back = circuit.run("read-phoenix.py", "--role", "core", "--section", "plan")
    assert back.returncode == 0 and "РЕГИСТР" in back.stdout, back.explain()


@pytest.mark.parametrize("section", SECTIONS)
def test_every_documented_section_is_accepted(circuit, section):
    # identity засеяна сборкой контура: её замена короче прежней — только осознанно.
    extra = ("--allow-shrink",) if section == "identity" else ()
    res = save(circuit, "CORE", section, body_of(f"СЕКЦИЯ-{section}", lines=4), *extra)
    assert res.returncode == 0, res.explain()
    assert f"phoenix/CORE/{section}" in res.stdout
    assert f"СЕКЦИЯ-{section}" in mem(circuit, "CORE", section)[0]


# ── плохой ввод: отказ до записи ──────────────────────────────────────────────────────


def test_unknown_section_is_refused_by_argparse(circuit):
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "diary", "--body", "x")
    assert res.returncode == 2, res.explain()
    assert "--section" in res.stderr and "diary" in res.stderr, res.explain()
    assert dump_db(circuit) == before


@pytest.mark.parametrize("args", [
    pytest.param(("--section", "state", "--body", "текст"), id="без-role"),
    pytest.param(("--role", "CORE", "--body", "текст"), id="без-section"),
])
def test_missing_required_argument_is_exit_2(circuit, args):
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", *args)
    assert res.returncode == 2, res.explain()
    assert dump_db(circuit) == before


def test_no_body_and_no_mode_is_refused(circuit):
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state")
    assert res.returncode == 1, res.explain()
    assert "--body" in res.out and "--file" in res.out, res.explain()
    assert dump_db(circuit) == before


def test_missing_phoenix_body_file_writes_nothing(circuit):
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--file", str(circuit.root.parent / "net-takogo-fayla.md"))
    assert res.returncode != 0, res.explain()
    assert dump_db(circuit) == before


def test_missing_db_is_refused_and_not_created(circuit):
    ghost = circuit.root.parent / "ghost" / "mezosync.db"
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--body", "x", "--db", str(ghost))
    assert res.returncode == 1, res.explain()
    assert not ghost.exists() and not ghost.parent.exists(), \
        "опечатка в пути к базе не должна заводить пустую базу-фантом"


@pytest.mark.parametrize("extra", [
    pytest.param(("--body", "   "), id="body-из-пробелов"),
    pytest.param(("--file", "WHITESPACE"), id="file-из-пробелов-и-переводов-строк"),
    pytest.param(("--file", "EMPTY"), id="file-пустой"),
    pytest.param(("--file", "WHITESPACE", "--allow-shrink"), id="--allow-shrink-пустоту-не-разрешает"),
])
def test_empty_body_is_refused_and_memory_stays(circuit, extra):
    assert save(circuit, "CORE", "state", body_of("ЦЕЛОЕ")).returncode == 0
    files = {"WHITESPACE": put(circuit, " \n\t \n  "), "EMPTY": put(circuit, "")}
    args = tuple(str(files[a]) if a in files else a for a in extra)
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state", *args)
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before, "отказ обязан оставить память и историю нетронутыми"
    assert "ЦЕЛОЕ" in mem(circuit, "CORE", "state")[0]


def test_empty_body_does_not_create_a_new_section(circuit):
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "plan", "--body", " ")
    assert res.returncode == 1, res.explain()
    assert mem(circuit, "CORE", "plan") is None


# ── служебный блок читалки не сохраняется как память ──────────────────────────────────


def test_reader_service_block_heading_is_refused(circuit):
    text = "Своя строка достаточной длины.\n## §4½ ОТКРЫТЫЕ КАРТОЧКИ\nснимок чужого состояния\n"
    res = save(circuit, "CORE", "state", text)
    assert res.returncode == 1, res.explain()
    assert "§4½" in res.out, "отказ показывает строку служебного блока: " + res.explain()
    assert mem(circuit, "CORE", "state") is None


def test_writing_about_the_service_block_is_allowed(circuit):
    """Судится НАЧАЛО строки (заголовок), а не упоминание: писать О блоке можно."""
    text = "Не копируй блок §4½ из читалки в свою память: он собирается при каждом вызове.\n"
    res = save(circuit, "CORE", "state", text)
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == text


# ── --dry-run ─────────────────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing_on_every_path(circuit):
    assert save(circuit, "CORE", "state", body_of("БАЗА", 10)).returncode == 0
    old_id = versions(circuit, "CORE", "state")[-1][0]
    before = dump_db(circuit)

    runs = [
        ("новая секция", ("--section", "plan", "--body", "новый раздел памяти, строка из теста")),
        ("правка существующей", ("--section", "state", "--file", str(put(circuit, body_of("НОВОЕ", 10))))),
        ("--confirm", ("--section", "state", "--confirm")),
        ("--restore", ("--section", "state", "--restore", str(old_id))),
        ("--history", ("--section", "state", "--history")),
        ("--read", ("--section", "state", "--read")),
    ]
    for label, args in runs:
        res = circuit.run("save-phoenix.py", "--role", "CORE", "--dry-run", *args)
        assert res.returncode == 0, f"{label}: {res.explain()}"
        assert "ХОЛОСТОЙ ПРОГОН" in res.out, f"{label}: {res.explain()}"
        assert dump_db(circuit) == before, f"{label}: холостой прогон изменил базу"


def test_dry_run_matches_the_real_run(circuit):
    """Контроль к предыдущему: тот же вызов БЕЗ --dry-run пишет — значит холостой был честным."""
    assert save(circuit, "CORE", "state", body_of("ПРЕЖНЕЕ", 10)).returncode == 0
    new = body_of("ПОСЛЕДНЕЕ", 10)
    dry = save(circuit, "CORE", "state", new, "--dry-run")
    assert dry.returncode == 0, dry.explain()
    assert "ПРЕЖНЕЕ" in mem(circuit, "CORE", "state")[0]
    real = save(circuit, "CORE", "state", new)
    assert real.returncode == 0, real.explain()
    assert mem(circuit, "CORE", "state")[0] == new
    assert "phoenix/CORE/state" in dry.stdout and "phoenix/CORE/state" in real.stdout


def test_dry_run_still_shows_refusals(circuit):
    """Холостой прогон нужен, чтобы увидеть отказ без следа: он обязан отказывать так же."""
    assert save(circuit, "CORE", "state", body_of("БОЛЬШОЕ", 30)).returncode == 0
    before = dump_db(circuit)
    empty = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                        "--dry-run", "--body", "  ")
    shrink = save(circuit, "CORE", "state", "кратко и ёмко про всё сразу\n", "--dry-run")
    stale = save(circuit, "CORE", "state", body_of("БОЛЬШОЕ", 31), "--dry-run",
                 "--expect-version", "999999")
    for label, res in (("пустое тело", empty), ("обвал объёма", shrink), ("чужая версия", stale)):
        assert res.returncode == 1, f"{label}: {res.explain()}"
    assert dump_db(circuit) == before


# ── --history ─────────────────────────────────────────────────────────────────────────


def test_history_lists_versions_newest_first(circuit):
    for tag in ("ПЕРВАЯ", "ВТОРАЯ", "ТРЕТЬЯ"):
        assert save(circuit, "CORE", "state", body_of(tag, 10)).returncode == 0
    ids = [v[0] for v in versions(circuit, "CORE", "state")]
    assert len(ids) == 3
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "core", "--section", "state", "--history")
    assert res.returncode == 0, res.explain()
    assert "CORE/state" in res.stdout
    assert [int(n) for n in re.findall(r"\bid=(\d+)", res.stdout)] == ids[::-1], res.explain()
    assert dump_db(circuit) == before, "--history ничего не пишет"


def test_history_of_a_section_with_no_versions_is_refused(circuit):
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "plan", "--history")
    assert res.returncode == 1, res.explain()
    assert "CORE/plan" in res.out, res.explain()


def test_history_of_the_seeded_section_is_available(circuit):
    """Сборка контура сеет по одной версии каждой живой секции — история читается сразу."""
    seeded = versions(circuit, "CORE", "identity")
    assert len(seeded) >= 1, "у засеянной identity нет ни одной версии"
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "identity", "--history")
    assert res.returncode == 0, res.explain()
    assert f"id={seeded[-1][0]}" in res.stdout


def test_history_keeps_last_ten_plus_the_longest_and_archives_the_rest(circuit):
    """Чистка: 10 свежих версий ПЛЮС самая длинная; лишнее уходит в архив под своим номером."""
    bodies = [f"версия {i:02d} " + "х" * (700 if i == 0 else 560) for i in range(12)]
    for text in bodies:
        res = save(circuit, "CORE", "history", text)
        assert res.returncode == 0, res.explain()
    live = [v[0] for v in versions(circuit, "CORE", "history")]
    archived = [r[0] for r in circuit.query(
        "SELECT id FROM phoenix_history_archive WHERE role='CORE' AND section='history' "
        "ORDER BY id")]
    assert len(live) == 11 and len(archived) == 1, (live, archived)
    everything = sorted(live + archived)
    assert len(everything) == 12, "ни одна версия не удалена — только перенесена"
    assert everything[0] in live, "самая длинная (первая) версия обязана остаться в истории"
    assert archived == [everything[1]], "в архив уходит самая старая из прочих"
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "history", "--history")
    assert [int(n) for n in re.findall(r"\bid=(\d+)", res.stdout)] == live[::-1]


# ── --expect-version ──────────────────────────────────────────────────────────────────


def test_expect_version_with_stale_number_is_refused(circuit):
    assert save(circuit, "CORE", "state", body_of("А", 20)).returncode == 0
    v1 = versions(circuit, "CORE", "state")[-1][0]
    second = body_of("А", 20) + "строка, которую дописала роль после чтения\n"
    assert save(circuit, "CORE", "state", second).returncode == 0
    v2 = versions(circuit, "CORE", "state")[-1][0]
    assert v2 > v1
    before = dump_db(circuit)

    res = save(circuit, "CORE", "state", body_of("Б", 20), "--expect-version", str(v1))
    assert res.returncode == 1, res.explain()
    assert f"id={v2}" in res.out, "отказ называет новейшую версию: " + res.explain()
    assert dump_db(circuit) == before, "при отказе тело не пишется"
    assert mem(circuit, "CORE", "state")[0] == second


def test_expect_version_with_current_number_writes(circuit):
    assert save(circuit, "CORE", "state", body_of("А", 20)).returncode == 0
    v1 = versions(circuit, "CORE", "state")[-1][0]
    new = body_of("А", 20) + "правка рукой по свежему номеру\n"
    res = save(circuit, "CORE", "state", new, "--expect-version", str(v1))
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == new
    assert len(versions(circuit, "CORE", "state")) == 2


@pytest.mark.parametrize("number", ["999999", "1"], ids=["нет-такой-версии", "версия-другой-секции"])
def test_expect_version_must_belong_to_this_section(circuit, number):
    """Проверяются и роль, и раздел: чужой номер (id=1 — засеянная identity) — отказ."""
    assert save(circuit, "CORE", "state", body_of("А", 20)).returncode == 0
    before = dump_db(circuit)
    res = save(circuit, "CORE", "state", body_of("А", 20) + "ещё строка\n",
               "--expect-version", number)
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before


def test_expect_version_catches_a_text_edited_outside_the_tool(circuit):
    """Номер из --history равен новейшему, а тело правили мимо инструмента — запись с ним отказана."""
    assert save(circuit, "CORE", "state", body_of("А", 20)).returncode == 0
    latest = versions(circuit, "CORE", "state")[-1][0]
    sql(circuit, "UPDATE phoenix SET body = body || ? WHERE role='CORE' AND section='state'",
        ("строка, добавленная прямым SQL мимо инструмента\n",))
    before = dump_db(circuit)
    res = save(circuit, "CORE", "state", body_of("А", 20) + "моя правка\n",
               "--expect-version", str(latest))
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before


@pytest.mark.parametrize("mode", ["--confirm", "--history"])
def test_expect_version_does_not_combine_with_modes_without_a_body(circuit, mode):
    assert save(circuit, "CORE", "state", body_of("А", 10)).returncode == 0
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state", mode,
                      "--expect-version", "1")
    assert res.returncode == 1, res.explain()


# ── --read / --out ────────────────────────────────────────────────────────────────────


def test_read_gives_version_number_and_body_for_the_edit_loop(circuit):
    """--read --out → правка файла → --file … --expect-version <номер из того же вызова>."""
    original = body_of("ЧТЕНИЕ", 20)
    assert save(circuit, "CORE", "state", original).returncode == 0
    latest = versions(circuit, "CORE", "state")[-1][0]
    before = dump_db(circuit)

    shown = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state", "--read")
    assert shown.returncode == 0, shown.explain()
    assert f"--expect-version {latest}" in shown.stdout, shown.explain()
    assert original.strip() in shown.stdout

    out_file = circuit.root.parent / "inputs" / "read-out.md"
    out_file.parent.mkdir(exist_ok=True)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--read", "--out", str(out_file))
    assert res.returncode == 0, res.explain()
    assert f"--expect-version {latest}" in res.stdout
    assert out_file.read_bytes().decode("utf-8") == original, "--out пишет тело как есть"
    assert dump_db(circuit) == before, "--read ничего не пишет"

    edited = original + "строка, добавленная при правке файла\n"
    out_file.write_bytes(edited.encode("utf-8"))
    back = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                       "--file", str(out_file), "--expect-version", str(latest))
    assert back.returncode == 0, back.explain()
    assert mem(circuit, "CORE", "state")[0] == edited


@pytest.mark.parametrize("args", [
    pytest.param(("--section", "plan", "--read"), id="read-раздела-нет"),
    pytest.param(("--section", "state", "--out", "x.md"), id="out-без-read"),
    pytest.param(("--section", "state", "--read", "--body", "x"), id="read-с-body"),
    pytest.param(("--section", "state", "--read", "--history"), id="read-с-history"),
])
def test_read_flag_refusals(circuit, args):
    assert save(circuit, "CORE", "state", body_of("А", 10)).returncode == 0
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", *args)
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before
    assert not (circuit.root / "x.md").exists()


# ── обвал объёма: --allow-shrink ──────────────────────────────────────────────────────


def test_big_shrink_is_refused_without_allow_shrink(circuit):
    big = body_of("СТАРОЕ", 30)
    assert save(circuit, "CORE", "state", big).returncode == 0
    before = dump_db(circuit)
    res = save(circuit, "CORE", "state", body_of("НОВОЕ", 3))
    assert res.returncode == 1, res.explain()
    assert "--allow-shrink" in res.out, res.explain()
    assert dump_db(circuit) == before, "отказ: ни тела, ни версии, ни записи в журнале"
    assert mem(circuit, "CORE", "state")[0] == big


def test_big_shrink_with_allow_shrink_passes_and_keeps_old_text_in_history(circuit):
    big = body_of("СТАРОЕ", 30)
    assert save(circuit, "CORE", "state", big).returncode == 0
    small = body_of("НОВОЕ", 3)
    res = save(circuit, "CORE", "state", small, "--allow-shrink")
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == small
    history = versions(circuit, "CORE", "state")
    assert [v[4] for v in history] == [big, small], "прежнее тело лежит в истории дословно"
    assert "allow-shrink" in history[-1][2], "версия помнит, что сокращение разрешено словом"


def test_shrink_report_names_the_vanishing_blocks(circuit):
    blocks = {name: f"## {name}\n" + body_of(name, 8) for name in ("Блок-А", "Блок-Б", "Блок-В", "Блок-Г")}
    assert save(circuit, "CORE", "state", "".join(blocks.values())).returncode == 0
    res = save(circuit, "CORE", "state", blocks["Блок-А"])
    assert res.returncode == 1, res.explain()
    for gone in ("Блок-Б", "Блок-В", "Блок-Г"):
        assert gone in res.out, f"отказ обязан назвать исчезающий блок {gone}: " + res.explain()


def test_moderate_shrink_passes_without_the_flag(circuit):
    """Контроль к отказу: потеря около 30 % — законная правка, порог 40 %."""
    assert save(circuit, "CORE", "state", body_of("ПРАВКА", 30)).returncode == 0
    res = save(circuit, "CORE", "state", body_of("ПРАВКА", 21))
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == body_of("ПРАВКА", 21)


def test_small_section_is_not_judged_by_shares(circuit):
    """Ниже 400 знаков долями не судим: короткая секция может усохнуть до строки."""
    short = body_of("КОРОТКОЕ", 4)
    assert len(short) < 400
    assert save(circuit, "CORE", "state", short).returncode == 0
    res = save(circuit, "CORE", "state", "одна строка\n")
    assert res.returncode == 0, res.explain()


# ── --confirm и повторное сохранение того же текста ───────────────────────────────────


def test_confirm_marks_the_look_and_leaves_text_and_versions(circuit):
    assert save(circuit, "CORE", "state", body_of("ВЗГЛЯД", 10)).returncode == 0
    old = "2000-01-01 00:00:00"
    sql(circuit, "UPDATE phoenix SET saved_at=?, confirmed_at=? WHERE role='CORE' AND section='state'",
        (old, old))
    versions_before = versions(circuit, "CORE", "state")
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state", "--confirm")
    assert res.returncode == 0, res.explain()
    body, saved_at, confirmed_at = mem(circuit, "CORE", "state")
    assert body == body_of("ВЗГЛЯД", 10)
    assert saved_at == old, "возраст ТЕКСТА не сдвигается"
    assert confirmed_at and confirmed_at > old, "возраст ВЗГЛЯДА сдвинут"
    assert versions(circuit, "CORE", "state") == versions_before
    rows = audit(circuit, "confirm_phoenix", "phoenix.CORE.state")
    assert len(rows) == 1 and rows[0]["actor_role"] == "CORE"


def test_confirm_of_a_missing_section_is_refused(circuit):
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "plan", "--confirm")
    assert res.returncode == 1, res.explain()
    assert "CORE/plan" in res.out
    assert dump_db(circuit) == before
    assert mem(circuit, "CORE", "plan") is None


def test_confirm_does_not_accept_a_body(circuit):
    assert save(circuit, "CORE", "state", body_of("ВЗГЛЯД", 10)).returncode == 0
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--confirm", "--body", "новое тело")
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before


def test_saving_the_same_text_again_confirms_but_keeps_text_age_and_versions(circuit):
    text = body_of("ТОТ ЖЕ", 10)
    assert save(circuit, "CORE", "state", text).returncode == 0
    old = "2001-02-03 04:05:06"
    sql(circuit, "UPDATE phoenix SET saved_at=?, confirmed_at=? WHERE role='CORE' AND section='state'",
        (old, old))
    versions_before = versions(circuit, "CORE", "state")
    res = save(circuit, "CORE", "state", text)
    assert res.returncode == 0, res.explain()
    _, saved_at, confirmed_at = mem(circuit, "CORE", "state")
    assert saved_at == old, "пересохранение без правки не выдаётся за свежесть текста"
    assert confirmed_at > old
    assert versions(circuit, "CORE", "state") == versions_before


def test_real_save_sets_both_dates_and_adds_a_version(circuit):
    assert save(circuit, "CORE", "state", body_of("ПЕРВАЯ", 10)).returncode == 0
    old = "2001-02-03 04:05:06"
    sql(circuit, "UPDATE phoenix SET saved_at=?, confirmed_at=? WHERE role='CORE' AND section='state'",
        (old, old))
    assert save(circuit, "CORE", "state", body_of("ВТОРАЯ", 10)).returncode == 0
    _, saved_at, confirmed_at = mem(circuit, "CORE", "state")
    assert saved_at > old and confirmed_at == saved_at, "запись тела ставит обе даты"
    assert len(versions(circuit, "CORE", "state")) == 2


# ── --restore ─────────────────────────────────────────────────────────────────────────


def test_restore_brings_back_the_old_body_as_a_new_version(circuit):
    big = body_of("ПРЕЖНЕЕ", 30)
    assert save(circuit, "CORE", "state", big).returncode == 0
    small = body_of("СЖАТОЕ", 3)
    assert save(circuit, "CORE", "state", small, "--allow-shrink").returncode == 0
    old = versions(circuit, "CORE", "state")
    assert len(old) == 2

    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--restore", str(old[0][0]))
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == big, "возврат — тело побайтно, без --allow-shrink"
    now = versions(circuit, "CORE", "state")
    assert now[:2] == old, "прежние версии целы: возврат создаёт НОВУЮ, а не подменяет"
    assert len(now) == 3 and now[2][4] == big
    assert "restore" in now[2][2] and str(old[0][0]) in now[2][2]


def test_restore_of_a_much_smaller_version_needs_no_allow_shrink(circuit):
    """Возврат сознателен по построению: он подразумевает разрешение на сокращение."""
    small = body_of("МАЛАЯ", 3)
    big = body_of("БОЛЬШАЯ", 30)
    assert save(circuit, "CORE", "state", small).returncode == 0
    assert save(circuit, "CORE", "state", big).returncode == 0
    small_id = versions(circuit, "CORE", "state")[0][0]
    refused = save(circuit, "CORE", "state", small)
    assert refused.returncode == 1, "контроль: то же сокращение обычным сохранением — отказ"
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state",
                      "--restore", str(small_id))
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "CORE", "state")[0] == small


@pytest.mark.parametrize("target", ["999999", "abc", "OTHER"], ids=["нет-такого", "не-число", "чужая-роль"])
def test_restore_of_an_unknown_or_foreign_version_is_refused(circuit, target):
    assert save(circuit, "CORE", "state", body_of("СВОЁ", 10)).returncode == 0
    assert save(circuit, "STUD", "state", body_of("ЧУЖОЕ", 10)).returncode == 0
    if target == "OTHER":
        target = str(versions(circuit, "STUD", "state")[-1][0])
    before = dump_db(circuit)
    res = circuit.run("save-phoenix.py", "--role", "CORE", "--section", "state", "--restore", target)
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before
    assert "СВОЁ" in mem(circuit, "CORE", "state")[0]


# ── кто правит ────────────────────────────────────────────────────────────────────────


def test_actor_is_recorded_separately_from_the_owner_of_the_section(circuit):
    own = save(circuit, "STUD", "state", body_of("СВОЯ", 10))
    assert own.returncode == 0, own.explain()
    foreign = save(circuit, "STUD", "state", body_of("СВОЯ", 10) + "правка из чужих рук\n",
                   "--actor", "core")
    assert foreign.returncode == 0, foreign.explain()
    rows = audit(circuit, "save_phoenix", "phoenix.STUD.state")
    assert [r["actor_role"] for r in rows] == ["STUD", "CORE"]
    assert [v[1] for v in versions(circuit, "STUD", "state")] == ["STUD", "CORE"]


def test_foreign_edit_that_is_overwritten_is_reported_but_not_refused(circuit):
    """Карточка #701: сохранение роли, затирающее строки чужой правки, — предупреждение, не отказ."""
    base = body_of("ОСНОВА", 10)
    assert save(circuit, "STUD", "state", base).returncode == 0
    foreign = base + "ЧУЖАЯ-СТРОКА: добавлена рукой CORE после прошлого сохранения\n"
    assert save(circuit, "STUD", "state", foreign, "--actor", "CORE").returncode == 0
    foreign_id = versions(circuit, "STUD", "state")[-1][0]

    mine = base + "МОЯ-СТРОКА: роль дописала своё, не видя чужой правки\n"
    res = save(circuit, "STUD", "state", mine)
    assert res.returncode == 0, res.explain()
    assert mem(circuit, "STUD", "state")[0] == mine, "предупреждение не мешает записи"
    assert f"id={foreign_id}" in res.stdout, "предупреждение называет версию чужой правки"
    assert "CORE" in res.stdout


# ── порог объёма раздела — долг, а не отказ ───────────────────────────────────────────


def test_volume_threshold_is_spoken_not_enforced(circuit):
    guard = circuit.scripts / "guard-phoenix-volume.py"
    assert guard.is_file(), "в контуре нет guard-phoenix-volume.py — порог читать не у кого"
    limit = int(re.search(r"^LIMIT\s*=\s*([\d_]+)", guard.read_text(encoding="utf-8"),
                          re.M).group(1).replace("_", ""))

    small = save(circuit, "CORE", "state", body_of("МАЛО", 5))
    assert small.returncode == 0, small.explain()
    assert str(limit) not in small.out, "под порогом строки о нём нет"

    huge = body_of("МНОГО", limit // 60 + 40)
    assert len(huge) > limit
    res = save(circuit, "CORE", "state", huge)
    assert res.returncode == 0, "порог объёма говорит, но не останавливает запись: " + res.explain()
    assert mem(circuit, "CORE", "state")[0] == huge
    assert str(limit) in res.stdout, "сверх порога строка называет число порога: " + res.explain()


# ── read-phoenix.py ───────────────────────────────────────────────────────────────────


def test_read_unknown_role_is_refused_and_names_who_exists(circuit):
    before = dump_db(circuit)
    res = circuit.run("read-phoenix.py", "--role", "NOBODY")
    assert res.returncode == 1, res.explain()
    assert "NOBODY" in res.stderr and "COORD" in res.stderr, res.explain()
    assert dump_db(circuit) == before


def test_read_without_role_and_without_list_is_refused(circuit):
    res = circuit.run("read-phoenix.py")
    assert res.returncode == 1, res.explain()
    assert "--role" in res.stderr


def test_read_unknown_section_is_refused_by_argparse(circuit):
    res = circuit.run("read-phoenix.py", "--role", "CORE", "--section", "diary")
    assert res.returncode == 2, res.explain()
    assert "--section" in res.stderr


def test_read_of_a_missing_section_does_not_pass_for_an_empty_one(circuit):
    """Нет секции — это сказано (знак ⛔ у её заголовка), а не молчание «всё в порядке»."""
    res = circuit.run("read-phoenix.py", "--role", "CORE", "--section", "plan")
    assert res.returncode == 0, res.explain()
    assert re.search(r"⛔\s+§5", res.stdout), res.explain()
    assert not re.search(r"^## §5", res.stdout, re.M)


def test_read_prints_sections_in_the_order_of_waking_up(circuit):
    """identity → rebirth → sources → state → plan → history → launcher (докстрока читалки)."""
    order = ["rebirth", "sources", "state", "plan", "history", "launcher"]
    for section in order:
        res = save(circuit, "STUD", section, f"МЕТКА-{section.upper()} строка памяти раздела.\n")
        assert res.returncode == 0, res.explain()
    res = circuit.run("read-phoenix.py", "--role", "STUD")
    assert res.returncode == 0, res.explain()
    positions = [res.stdout.index(f"МЕТКА-{s.upper()}") for s in order]
    assert positions == sorted(positions), res.explain()


def test_read_list_shows_roles_sections_and_sizes(circuit):
    body = body_of("СПИСОК", 10)
    assert save(circuit, "CORE", "state", body).returncode == 0
    before = dump_db(circuit)
    res = circuit.run("read-phoenix.py", "--list")
    assert res.returncode == 0, res.explain()
    assert dump_db(circuit) == before

    sizes, role = {}, None
    for line in res.stdout.splitlines():
        head = re.match(r"^  (\S+)\s", line)
        if head and "✅" not in line and "⛔" not in line:
            role = head.group(1)
            sizes[role] = {}
        item = re.match(r"^\s+✅\s+(\w+)\s+(\d+)\s", line)
        if item and role:
            sizes[role][item.group(1)] = int(item.group(2))
    assert set(circuit.roles) <= set(sizes), res.explain()
    assert sizes["CORE"]["state"] == len(body)
    assert "identity" in sizes["CORE"], "засеянная сборкой identity видна в списке"
    assert "state" not in sizes["STUD"]


# ═══ set-rule.py ═════════════════════════════════════════════════════════════════════


def test_list_shows_every_rule_and_changes_nothing(circuit):
    before = dump_db(circuit)
    res = circuit.run("set-rule.py", "--list")
    assert res.returncode == 0, res.explain()
    for key in rule_keys(circuit):
        assert key in res.stdout, f"в списке нет правила {key}"
    assert dump_db(circuit) == before


def test_show_prints_header_and_text(circuit):
    key = active_key(circuit)
    row = rule(circuit, key)
    before = dump_db(circuit)
    res = circuit.run("set-rule.py", "--key", key, "--show")
    assert res.returncode == 0, res.explain()
    assert key in res.stdout
    assert f"locked_by={row['locked_by']}" in res.stdout and f"v{row['version']}" in res.stdout
    first = row["body"].strip().splitlines()[0].strip()
    assert first in res.stdout, "--show печатает текст правила"
    assert dump_db(circuit) == before


def test_show_unknown_key_and_missing_key(circuit):
    unknown = circuit.run("set-rule.py", "--key", "no-such-rule", "--show")
    assert unknown.returncode == 1 and "no-such-rule" in unknown.stderr, unknown.explain()
    missing = circuit.run("set-rule.py", "--show")
    assert missing.returncode == 1 and "--key" in missing.stderr, missing.explain()


def test_missing_db_is_refused(circuit):
    ghost = circuit.root.parent / "ghost.db"
    res = circuit.run("set-rule.py", "--db", str(ghost), "--list")
    assert res.returncode == 1, res.explain()
    assert not ghost.exists()


# ── запись правила: без --apply и с --apply ───────────────────────────────────────────


def test_write_without_apply_is_a_dry_run(circuit):
    plant_sentinel(circuit)
    before = dump_db(circuit)
    res = set_rule(circuit, NEW_KEY, "Проба: правило для сухого прогона.", *BASIS,
                   "--locked-by", "coord")
    assert res.returncode == 0, res.explain()
    assert "--apply" in res.stdout and "DRY-RUN" in res.stdout, res.explain()
    assert NEW_KEY in res.stdout
    assert dump_db(circuit) == before, "сухой прогон не пишет ни правило, ни журнал"
    assert mirror_untouched(circuit), "сухой прогон не трогает зеркало"


def test_apply_creates_the_rule_logs_it_and_rebuilds_the_mirror(circuit):
    plant_sentinel(circuit)
    text = "Проба: первая редакция правила.\nВторая строка правила.\n"
    res = set_rule(circuit, NEW_KEY, text, *BASIS, "--locked-by", "coord", "--apply")
    assert res.returncode == 0, res.explain()

    row = rule(circuit, NEW_KEY)
    assert row is not None
    assert row["body"] == text.strip(), "--body-file читается с обрезкой краёв"
    assert (row["locked_by"], row["version"], row["status"]) == ("coord", 1, "active")
    assert (row["basis"], row["authorized"], row["source_ref"], row["expiry_kind"]) == (
        "замер: проба контрактного теста", "owner", "#test", "forever")

    entries = audit(circuit, "create_rule", NEW_KEY)
    assert len(entries) == 1 and "Проба: первая редакция правила." in entries[0]["diff_md"]
    assert entries[0]["actor_role"] == circuit.coordinator, \
        "рука не названа — пишет координатор контура из данных"

    text_now = mirror_text(circuit)
    assert not mirror_untouched(circuit), "--apply пересобирает зеркало"
    assert NEW_KEY in mirror_keys(text_now) and "Вторая строка правила." in text_now
    assert set(mirror_keys(text_now)) == set(rule_keys(circuit)), \
        "зеркало собрано из той же базы: правила совпадают с таблицей rules"


def test_update_bumps_version_keeps_old_text_in_the_log_and_rebuilds_mirror(circuit):
    assert set_rule(circuit, NEW_KEY, "СТАРЫЙ-ТЕКСТ правила.", *BASIS, "--locked-by", "coord",
                    "--apply").returncode == 0
    plant_sentinel(circuit)
    res = set_rule(circuit, NEW_KEY, "НОВЫЙ-ТЕКСТ правила.", "--apply")
    assert res.returncode == 0, res.explain()
    row = rule(circuit, NEW_KEY)
    assert (row["body"], row["version"]) == ("НОВЫЙ-ТЕКСТ правила.", 2)
    entry = audit(circuit, "update_rule", NEW_KEY)[-1]
    assert "СТАРЫЙ-ТЕКСТ" in entry["diff_md"] and "НОВЫЙ-ТЕКСТ" in entry["diff_md"]
    text_now = mirror_text(circuit)
    assert "НОВЫЙ-ТЕКСТ" in text_now and "СТАРЫЙ-ТЕКСТ" not in text_now


def test_applying_the_same_rule_again_is_idempotent(circuit):
    args = (NEW_KEY, "Одно и то же.", *BASIS, "--locked-by", "coord", "--apply")
    assert set_rule(circuit, *args).returncode == 0
    log_before = audit(circuit)
    res = set_rule(circuit, *args)
    assert res.returncode == 0, res.explain()
    assert rule(circuit, NEW_KEY)["version"] == 1
    assert audit(circuit) == log_before


def test_update_without_new_text_inherits_the_basis(circuit):
    """Основание наследуется: правка опечатки в обоснованном правиле не требует его заново."""
    assert set_rule(circuit, NEW_KEY, "Первая.", *BASIS, "--locked-by", "coord",
                    "--apply").returncode == 0
    res = set_rule(circuit, NEW_KEY, "Вторая.", "--apply")
    assert res.returncode == 0, res.explain()
    assert rule(circuit, NEW_KEY)["basis"] == "замер: проба контрактного теста"


# ── отказы: база и зеркало не тронуты ─────────────────────────────────────────────────


@pytest.mark.parametrize("extra, key, code", [
    pytest.param((), NEW_KEY, 2, id="без-основания"),
    pytest.param(("--basis", "b", "--authorized-by", "owner", "--source-ref", "#1"),
                 NEW_KEY, 2, id="без-вида-условия-отмены"),
    pytest.param(("--basis", "b", "--authorized-by", "owner", "--source-ref", "#1",
                  "--expiry-kind", "until_date"), NEW_KEY, 2, id="until_date-без-даты"),
    pytest.param(("--basis", "b", "--authorized-by", "owner", "--source-ref", "#1",
                  "--expiry-kind", "until_event"), NEW_KEY, 2, id="until_event-без-события"),
    pytest.param((*BASIS[:-1], "sometimes"), NEW_KEY, 2, id="вид-условия-не-из-списка"),
    pytest.param((*BASIS, "--locked-by", "everyone"), NEW_KEY, 2, id="замок-не-из-списка"),
])
def test_write_refusals_leave_db_and_mirror_untouched(circuit, extra, key, code):
    plant_sentinel(circuit)
    before = dump_db(circuit)
    res = set_rule(circuit, key, "Правило, которое не должно лечь.", *extra, "--apply")
    assert res.returncode == code, res.explain()
    assert dump_db(circuit) == before, "отказ не пишет ни правило, ни журнал"
    assert mirror_untouched(circuit), "отказ не трогает зеркало"
    assert rule(circuit, key) is None


def test_write_without_key_and_without_body_is_refused(circuit):
    plant_sentinel(circuit)
    before = dump_db(circuit)
    no_key = circuit.run("set-rule.py", "--body", "текст", *BASIS, "--apply")
    no_body = circuit.run("set-rule.py", "--key", NEW_KEY, *BASIS, "--apply")
    blank = set_rule(circuit, NEW_KEY, "  \n ", *BASIS, "--apply")
    for label, res in (("без --key", no_key), ("без текста", no_body), ("пустой файл", blank)):
        assert res.returncode == 1, f"{label}: {res.explain()}"
    assert dump_db(circuit) == before and mirror_untouched(circuit)


def test_missing_rule_body_file_writes_nothing(circuit):
    plant_sentinel(circuit)
    before = dump_db(circuit)
    res = circuit.run("set-rule.py", "--key", NEW_KEY, "--body-file",
                      str(circuit.root.parent / "net-takogo.md"), *BASIS, "--apply")
    assert res.returncode != 0, res.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)


# ── чья рука пишет ────────────────────────────────────────────────────────────────────


def test_writer_hand_comes_from_flag_then_environment_then_coordinator(circuit):
    def write(key, *extra, env=None):
        res = set_rule(circuit, key, f"Правило {key}.", *BASIS, "--locked-by", "coord",
                       "--apply", *extra, env_extra=env)
        assert res.returncode == 0, res.explain()
        return audit(circuit, "create_rule", key)[0]["actor_role"]

    assert write("zz-hand-data") == circuit.coordinator
    assert write("zz-hand-env", env={"MEZO_ROLE": "stud"}) == "STUD"
    assert write("zz-hand-flag", "--actor", "CORE") == "CORE"
    assert write("zz-hand-both", "--actor", "CORE", env={"MEZO_ROLE": "STUD"}) == "CORE", \
        "флаг сильнее переменной среды"


@pytest.mark.parametrize("state", ["no-coordinator", "two-coordinators"])
def test_write_is_refused_when_no_hand_can_be_named(circuit, state):
    sql(circuit, "UPDATE roles SET lifecycle_reason = NULL")
    if state == "two-coordinators":
        sql(circuit, "UPDATE roles SET lifecycle_reason = 'координатор контура' "
                     "WHERE role IN ('COORD', 'CORE')")
    plant_sentinel(circuit)
    before = dump_db(circuit)
    args = (NEW_KEY, "Правило без руки.", *BASIS, "--locked-by", "coord")

    dry = set_rule(circuit, *args)
    assert dry.returncode == 0, "холостому прогону рука не нужна: " + dry.explain()

    res = set_rule(circuit, *args, "--apply")
    assert res.returncode == 2, res.explain()
    assert "--actor" in res.stderr and "MEZO_ROLE" in res.stderr, res.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)

    named = set_rule(circuit, *args, "--apply", "--actor", "CORE")
    assert named.returncode == 0, named.explain()
    assert audit(circuit, "create_rule", NEW_KEY)[0]["actor_role"] == "CORE"


# ── замок владельца ───────────────────────────────────────────────────────────────────


def test_owner_locked_rule_edit_warns_but_is_not_refused_and_keeps_the_lock(circuit):
    key = active_key(circuit, locked_by="owner")
    version = rule(circuit, key)["version"]
    res = set_rule(circuit, key, "Новая редакция правила владельца.", "--actor", "CORE", "--apply")
    assert res.returncode == 0, res.explain()
    assert "Rule 8" in res.stdout, "правка не от владельца — предупреждение о слове владельца"
    row = rule(circuit, key)
    assert (row["locked_by"], row["version"]) == ("owner", version + 1)


def test_owner_locked_rule_edit_by_the_owner_has_no_warning(circuit):
    key = active_key(circuit, locked_by="owner")
    res = set_rule(circuit, key, "Новая редакция по слову владельца.", "--actor", "owner", "--apply")
    assert res.returncode == 0, res.explain()
    assert "Rule 8" not in res.stdout, res.explain()


# ── зеркало не пересобирается из чужой базы ───────────────────────────────────────────


def test_write_to_a_non_live_db_does_not_touch_the_live_mirror(circuit):
    """Генератор читает ту же базу, куда писали; а зеркало живого контура из песочницы не собирают."""
    plant_sentinel(circuit)
    sandbox = circuit.root.parent / "sandbox.db"
    src = circuit.connect()
    dst = sqlite3.connect(str(sandbox))
    src.backup(dst)
    dst.close()
    src.close()
    live_before = dump_db(circuit)

    res = set_rule(circuit, NEW_KEY, "Правило из песочницы.", *BASIS, "--locked-by", "coord",
                   "--actor", "CORE", "--db", str(sandbox), "--apply")
    assert res.returncode == 0, res.explain()
    conn = sqlite3.connect(str(sandbox))
    try:
        assert conn.execute("SELECT COUNT(*) FROM rules WHERE rule_key=?", (NEW_KEY,)).fetchone()[0] == 1
    finally:
        conn.close()
    assert dump_db(circuit) == live_before, "живая база не тронута"
    assert mirror_untouched(circuit), "зеркало живого контура не пересобирается из песочницы"
    assert not (sandbox.parent / "generated").exists(), \
        "и рядом с чужой базой зеркало не собирается: производное живого репо из песочницы не берут"


# ── --revoke ──────────────────────────────────────────────────────────────────────────


REVOKE = ("--revoke", "--revoked-by", "owner", "--reason", "проба снятия правила")


def _fresh_rule(circuit, text="Правило, которое снимут.\n"):
    assert set_rule(circuit, NEW_KEY, text, *BASIS, "--locked-by", "coord",
                    "--apply").returncode == 0
    return text.strip()


def test_revoke_without_apply_is_a_dry_run(circuit):
    _fresh_rule(circuit)
    plant_sentinel(circuit)
    before = dump_db(circuit)
    res = circuit.run("set-rule.py", "--key", NEW_KEY, *REVOKE)
    assert res.returncode == 0, res.explain()
    assert "--apply" in res.stdout, res.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)
    assert rule(circuit, NEW_KEY)["status"] == "active"


def test_revoke_apply_marks_field_and_text_logs_and_rebuilds_mirror(circuit):
    old_text = _fresh_rule(circuit)
    plant_sentinel(circuit)
    res = circuit.run("set-rule.py", "--key", NEW_KEY, *REVOKE, "--revoked-at",
                      "2026-01-02 03:04 UTC", "--actor", "CORE", "--apply")
    assert res.returncode == 0, res.explain()

    row = rule(circuit, NEW_KEY)
    assert row["status"] == "revoked" and row["version"] == 2
    assert row["revoked_by"] == "owner" and row["revoked_at"] == "2026-01-02 03:04 UTC"
    assert "проба снятия правила" in row["revoked_reason"]
    assert row["body"].startswith("⛔ ОТОЗВАНО"), "пометка о снятии — первой строкой текста"
    assert row["body"].endswith(old_text), "прежний текст остаётся ниже как след"

    entries = audit(circuit, "revoke_rule", NEW_KEY)
    assert len(entries) == 1 and entries[0]["actor_role"] == "CORE"
    assert old_text in entries[0]["diff_md"]

    assert not mirror_untouched(circuit), "снятие пересобирает зеркало тем же вызовом"
    assert "ОТОЗВАНО" in heading_of(mirror_text(circuit), NEW_KEY)
    listed = circuit.run("set-rule.py", "--list")
    line = next(l for l in listed.stdout.splitlines() if NEW_KEY in l)
    assert "⚰" in line, "список помечает снятое правило надгробием"
    shown = circuit.run("set-rule.py", "--key", NEW_KEY, "--show")
    assert "СНЯТО" in shown.stdout, shown.explain()


def test_revoking_twice_changes_nothing(circuit):
    _fresh_rule(circuit)
    first = circuit.run("set-rule.py", "--key", NEW_KEY, *REVOKE, "--apply")
    assert first.returncode == 0, first.explain()
    before = dump_db(circuit)
    again = circuit.run("set-rule.py", "--key", NEW_KEY, *REVOKE, "--apply")
    assert again.returncode == 0, again.explain()
    assert dump_db(circuit) == before


@pytest.mark.parametrize("extra, key_present, code", [
    pytest.param(("--revoke", "--revoked-by", "owner"), True, 2, id="без-причины"),
    pytest.param(("--revoke", "--reason", "причина"), True, 2, id="без-кто-решил"),
    pytest.param((*REVOKE, "--revoked-at", "вчера"), True, 2, id="час-не-той-формы"),
    pytest.param((*REVOKE, "--body", "новый текст"), True, 2, id="вместе-с-body"),
    pytest.param((*REVOKE, "--skill-delivery", "yes"), True, 2, id="вместе-с-skill-delivery"),
    pytest.param(REVOKE, False, 1, id="неизвестный-ключ"),
])
def test_revoke_refusals_leave_the_rule_in_force(circuit, extra, key_present, code):
    _fresh_rule(circuit)
    plant_sentinel(circuit)
    before = dump_db(circuit)
    key = NEW_KEY if key_present else "no-such-rule"
    res = circuit.run("set-rule.py", "--key", key, *extra, "--apply")
    assert res.returncode == code, res.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)
    assert rule(circuit, NEW_KEY)["status"] == "active"


# ── --skill-delivery ──────────────────────────────────────────────────────────────────


def test_skill_delivery_changes_only_the_decision(circuit):
    key = active_key(circuit)
    base = rule(circuit, key)
    plant_sentinel(circuit)

    for value in ("unset", "yes", "no"):
        dry = circuit.run("set-rule.py", "--key", key, "--skill-delivery", value)
        assert dry.returncode == 0 and "--apply" in dry.stdout, dry.explain()
    assert rule(circuit, key) == base, "без --apply решение не записывается"

    for value, stored in (("unset", None), ("yes", "yes"), ("no", "no")):
        res = circuit.run("set-rule.py", "--key", key, "--skill-delivery", value, "--apply")
        assert res.returncode == 0, res.explain()
        row = rule(circuit, key)
        assert row["skill_delivery"] == stored
        for column in ("body", "version", "updated_at", "locked_by", "status"):
            assert row[column] == base[column], f"--skill-delivery трогает {column}"


def test_skill_delivery_refusals(circuit):
    key = active_key(circuit)
    before = dump_db(circuit)
    bad_value = circuit.run("set-rule.py", "--key", key, "--skill-delivery", "maybe", "--apply")
    assert bad_value.returncode == 2, bad_value.explain()
    unknown = circuit.run("set-rule.py", "--key", "no-such-rule", "--skill-delivery", "yes", "--apply")
    assert unknown.returncode == 1 and "no-such-rule" in unknown.out, unknown.explain()
    no_key = circuit.run("set-rule.py", "--skill-delivery", "yes", "--apply")
    assert no_key.returncode == 1, no_key.explain()
    assert dump_db(circuit) == before


# ── --annex ───────────────────────────────────────────────────────────────────────────


def test_annex_exit_codes_and_show_hint(circuit):
    annex_dir = circuit.mezosync / "rules-annex"
    files = sorted(annex_dir.glob("*.md"))
    assert files, "в свежем контуре нет приложений правил"
    with_annex = files[0].stem
    without = next(k for k in rule_keys(circuit) if not (annex_dir / f"{k}.md").is_file())

    ok = circuit.run("set-rule.py", "--key", with_annex, "--annex")
    assert ok.returncode == 0, ok.explain()
    first_line = files[0].read_text(encoding="utf-8").strip().splitlines()[0].strip()
    assert first_line in ok.stdout, "приложение напечатано"

    shown = circuit.run("set-rule.py", "--key", with_annex, "--show")
    assert f"--key {with_annex} --annex" in shown.stdout, "--show называет приложение, когда оно есть"
    plain = circuit.run("set-rule.py", "--key", without, "--show")
    assert "--annex" not in plain.stdout, "без приложения строки о нём нет"

    none = circuit.run("set-rule.py", "--key", without, "--annex")
    assert none.returncode == 3, "правило есть, приложения нет: " + none.explain()
    unknown = circuit.run("set-rule.py", "--key", "no-such-rule", "--annex")
    assert unknown.returncode == 1, unknown.explain()
    bad_form = circuit.run("set-rule.py", "--key", "NOT_A_KEY", "--annex")
    assert bad_form.returncode == 1, bad_form.explain()


# ═══ export-rules.py ═════════════════════════════════════════════════════════════════


def test_export_without_apply_writes_nothing(circuit):
    plant_sentinel(circuit)
    files_before = sorted(p.name for p in mirror_path(circuit).parent.iterdir())
    res = circuit.run("export-rules.py")
    assert res.returncode == 0, res.explain()
    assert "--apply" in res.stdout, res.explain()
    assert mirror_untouched(circuit)
    assert sorted(p.name for p in mirror_path(circuit).parent.iterdir()) == files_before


def test_export_without_apply_does_not_create_a_missing_mirror(circuit):
    mirror_path(circuit).unlink()
    res = circuit.run("export-rules.py")
    assert res.returncode == 0, res.explain()
    assert not mirror_path(circuit).exists()


def test_export_apply_builds_the_mirror_from_the_database(circuit):
    plant_sentinel(circuit)
    key = active_key(circuit)
    sql(circuit, "UPDATE rules SET body = body || ? WHERE rule_key = ?",
        ("\nМЕТКА-ПРЯМОЙ-ПРАВКИ в базе мимо set-rule.py\n", key))
    res = circuit.run("export-rules.py", "--apply")
    assert res.returncode == 0, res.explain()
    text = mirror_text(circuit)
    assert not mirror_untouched(circuit)
    assert set(mirror_keys(text)) == set(rule_keys(circuit)), "в зеркале ровно те правила, что в базе"
    assert "МЕТКА-ПРЯМОЙ-ПРАВКИ" in text, "зеркало собрано из ТЕКУЩЕЙ базы"


def test_export_marks_revoked_rules_and_only_them(circuit):
    # Посев рождает снятыми два правила «Прочих»; снимем ещё одно из разложенных по разделам.
    sectioned = "note-format"
    assert rule(circuit, sectioned)["status"] == "active", "в свежем контуре нет правила " + sectioned
    gone = circuit.run("set-rule.py", "--key", sectioned, *REVOKE, "--apply")
    assert gone.returncode == 0, gone.explain()
    revoked = set(rule_keys(circuit, "status <> 'active'"))
    assert sectioned in revoked and len(revoked) >= 3
    plant_sentinel(circuit)
    assert circuit.run("export-rules.py", "--apply").returncode == 0
    text = mirror_text(circuit)
    marked = {k for k in rule_keys(circuit) if "ОТОЗВАНО" in (heading_of(text, k) or "")}
    assert marked == revoked


def test_export_out_overrides_the_receiver(circuit):
    plant_sentinel(circuit)
    target = circuit.root.parent / "elsewhere" / "rules.md"
    target.parent.mkdir()
    res = circuit.run("export-rules.py", "--out", str(target), "--apply")
    assert res.returncode == 0, res.explain()
    assert set(mirror_keys(target.read_bytes().decode("utf-8"))) == set(rule_keys(circuit))
    assert mirror_untouched(circuit), "зеркало по умолчанию не тронуто, когда назван другой приёмник"


def test_export_follows_the_declared_coordination_dir(circuit):
    """Контур, держащий файл правил не рядом с базой, объявляет это ключом coordination_dir
    файла путей — и экспорт, и пересборка из set-rule.py идут туда, а не в generated/."""
    plant_sentinel(circuit)
    local = circuit.mezosync / "local"
    local.mkdir(exist_ok=True)
    (local / "paths.json").write_bytes(b'{"coordination_dir": "coordination"}')
    target = circuit.root / "coordination" / "sync.rules.md"

    res = circuit.run("export-rules.py", "--apply")
    assert res.returncode == 0, res.explain()
    assert set(mirror_keys(target.read_bytes().decode("utf-8"))) == set(rule_keys(circuit))
    assert mirror_untouched(circuit)

    written = set_rule(circuit, NEW_KEY, "Правило для объявленного каталога.", *BASIS,
                       "--locked-by", "coord", "--apply")
    assert written.returncode == 0, written.explain()
    assert NEW_KEY in mirror_keys(target.read_bytes().decode("utf-8"))
    assert mirror_untouched(circuit)


def test_export_missing_db_is_refused(circuit):
    ghost = circuit.root.parent / "ghost.db"
    res = circuit.run("export-rules.py", "--db", str(ghost), "--apply")
    assert res.returncode == 1, res.explain()
    assert not ghost.exists()


# ═══ rules-from-pack.py ══════════════════════════════════════════════════════════════


def test_fresh_circuit_has_no_drift_from_the_pack(circuit):
    res = pack_run(circuit)
    assert res.returncode == 0, res.explain()
    counts = pack_counts(res)
    drift = {k: v for k, v in counts.items() if k not in ("same", "retired-here")}
    assert all(v == 0 for v in drift.values()), f"свежий контур разошёлся с пакетом: {drift}"
    assert counts["same"] > 0
    revoked = rule_keys(circuit, "status <> 'active'")
    assert counts["retired-here"] == len(revoked), \
        "«снято у вас» — ровно правила, которые посев рождает снятыми"
    assert sorted(k for k, s in pack_listed(res) if s == "retired-here") == revoked


def test_state_filter_lists_only_that_state(circuit):
    res = pack_run(circuit, "--state", "retired-here")
    assert res.returncode == 0, res.explain()
    assert {s for _, s in pack_listed(res)} == {"retired-here"}
    assert sorted(k for k, _ in pack_listed(res)) == rule_keys(circuit, "status <> 'active'")
    empty = pack_run(circuit, "--state", "new")
    assert empty.returncode == 0 and pack_listed(empty) == [], empty.explain()


def test_summary_is_a_short_line_without_a_listing(circuit):
    res = pack_run(circuit, "--summary")
    assert res.returncode == 0, res.explain()
    lines = [l for l in res.stdout.splitlines() if l.strip()]
    assert 1 <= len(lines) <= 2, "одна строка итога (вторая — только про срок правил): " + res.explain()
    assert pack_listed(res) == [], "построчного списка в --summary нет"
    revoked = rule_keys(circuit, "status <> 'active'")
    assert sum(int(n) for n in re.findall(r"\d+", lines[0])) == len(revoked), \
        "в свежем контуре все числа итога нулевые, кроме снятых у вас"


def test_summary_and_list_do_not_write_to_the_circuit(circuit):
    before = dump_db(circuit)
    for args in ((), ("--summary",), ("--state", "same"), ("--show", active_key(circuit))):
        res = pack_run(circuit, *args)
        assert res.returncode == 0, res.explain()
    assert dump_db(circuit) == before


def test_local_edit_shows_up_as_drift(circuit):
    same = [k for k, s in pack_listed(pack_run(circuit)) if s == "same"]
    key = sorted(same)[0]
    res = set_rule(circuit, key, "Уточнено у нас: текст правила изменён контуром.",
                   "--actor", "CORE", "--apply")
    assert res.returncode == 0, res.explain()

    listing = pack_run(circuit)
    assert (key, "local-changed") in pack_listed(listing), listing.explain()
    counts = pack_counts(listing)
    assert counts["local-changed"] == 1 and counts["new"] == 0 and counts["pack-changed"] == 0
    only = pack_run(circuit, "--state", "local-changed")
    assert [k for k, _ in pack_listed(only)] == [key]

    revoked = len(rule_keys(circuit, "status <> 'active'"))
    summary = pack_run(circuit, "--summary")
    first = [l for l in summary.stdout.splitlines() if l.strip()][0]
    assert sum(int(n) for n in re.findall(r"\d+", first)) == revoked + 1, summary.explain()


def test_rule_that_exists_only_in_the_circuit_is_counted_not_listed(circuit):
    assert set_rule(circuit, NEW_KEY, "Есть только у контура.", *BASIS, "--locked-by", "coord",
                    "--apply").returncode == 0
    res = pack_run(circuit)
    assert res.returncode == 0, res.explain()
    assert pack_counts(res)["only-yours"] == 1
    assert NEW_KEY not in [k for k, _ in pack_listed(res)], "правила только у вас в списке не печатаются"


def test_show_known_and_unknown_key(circuit):
    key = active_key(circuit)
    ok = pack_run(circuit, "--show", key)
    assert ok.returncode == 0 and key in ok.stdout, ok.explain()
    unknown = pack_run(circuit, "--show", "no-such-key")
    assert unknown.returncode == 1 and "no-such-key" in unknown.out, unknown.explain()


def test_argparse_refusals(circuit):
    bad_state = pack_run(circuit, "--state", "bogus")
    assert bad_state.returncode == 2 and "--state" in bad_state.stderr, bad_state.explain()
    two_modes = pack_run(circuit, "--show", active_key(circuit), "--summary")
    assert two_modes.returncode == 2, two_modes.explain()


def test_bad_source_is_refused_with_a_reason(circuit, tmp_path):
    missing = tmp_path / "no-pack-here"
    empty = tmp_path / "pack-without-rules-db"
    empty.mkdir()
    for source in (missing, empty):
        listing = circuit.run("rules-from-pack.py", "--source", str(source))
        assert listing.returncode == 1, listing.explain()
        assert listing.out.strip(), "отказ называет причину словами"
        summary = circuit.run("rules-from-pack.py", "--source", str(source), "--summary")
        assert summary.returncode == 2, "--summary: отказ поиска баз — код 2: " + summary.explain()
        assert summary.stderr.strip() or summary.stdout.strip()
    assert "no-pack-here" in circuit.run("rules-from-pack.py", "--source", str(missing)).out


def test_missing_circuit_db_is_refused(circuit):
    ghost = circuit.root.parent / "ghost.db"
    listing = pack_run(circuit, "--db", str(ghost))
    summary = pack_run(circuit, "--db", str(ghost), "--summary")
    assert listing.returncode == 1, listing.explain()
    assert summary.returncode == 2, summary.explain()
    assert not ghost.exists()


@pytest.mark.parametrize("args", [
    pytest.param(("--adopt", "KEY", "--apply"), id="adopt-без-actor"),
    pytest.param(("--record-base", "--apply"), id="record-base-без-actor"),
    pytest.param(("--annexes", "--apply"), id="annexes-без-actor"),
    pytest.param(("--merge", "KEY"), id="merge-без-file"),
    pytest.param(("--propose", "KEY"), id="propose-без-why"),
    pytest.param(("--propose", "KEY", "--why", "класс ошибки"), id="propose-без-out"),
    pytest.param(("--expiry-from-pack",), id="expiry-from-pack-без-adopt"),
])
def test_write_modes_refuse_without_their_required_flags(circuit, args):
    key = active_key(circuit)
    args = tuple(key if a == "KEY" else a for a in args)
    plant_sentinel(circuit)
    before = dump_db(circuit)
    res = pack_run(circuit, *args)
    assert res.returncode == 1, res.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)


def test_adopt_needs_the_word_when_writing(circuit):
    key = sorted(k for k, s in pack_listed(pack_run(circuit)) if s == "same")[0]
    assert set_rule(circuit, key, "Уточнено у нас.", "--actor", "CORE", "--apply").returncode == 0
    before = dump_db(circuit)
    res = pack_run(circuit, "--adopt", key, "--apply", "--actor", "CORE")
    assert res.returncode == 1 and "--word" in res.out, res.explain()
    assert dump_db(circuit) == before


def test_adopt_dry_run_writes_nothing_and_apply_removes_the_drift(circuit):
    key = sorted(k for k, s in pack_listed(pack_run(circuit)) if s == "same")[0]
    pack_db = sqlite3.connect(f"file:{(PACK / 'rules' / 'pack-rules.db').as_posix()}?mode=ro", uri=True)
    try:
        pack_body = pack_db.execute("SELECT body FROM pack_rules WHERE rule_key=? "
                                    "AND removed_at IS NULL", (key,)).fetchone()[0]
    finally:
        pack_db.close()
    assert set_rule(circuit, key, "Уточнено у нас.", "--actor", "CORE", "--apply").returncode == 0
    assert (key, "local-changed") in pack_listed(pack_run(circuit))
    plant_sentinel(circuit)
    before = dump_db(circuit)

    word = ("--word", "владелец, чат контрактного теста, 2026-01-01")
    dry = pack_run(circuit, "--adopt", key, *word)
    assert dry.returncode == 0 and "--apply" in dry.stdout, dry.explain()
    assert dump_db(circuit) == before and mirror_untouched(circuit)

    done = pack_run(circuit, "--adopt", key, *word, "--apply", "--actor", "CORE")
    assert done.returncode == 0, done.explain()
    assert (key, "same") in pack_listed(pack_run(circuit)), "после взятия текст снова как в пакете"
    assert pack_counts(pack_run(circuit))["local-changed"] == 0
    assert rule(circuit, key)["body"].strip() == pack_body.strip()
    assert audit(circuit, "update_rule", key)[-1]["actor_role"] == "CORE"
    assert not mirror_untouched(circuit), "запись правила шла через set-rule.py — зеркало пересобрано"
