#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-pack-rules-db — приёмка build-pack-rules-db.py (карточка #608).

    python <КОНТУР>/vnext/tools/bite-pack-rules-db.py

ПРЕДМЕТ: build-pack-rules-db.py читает rules/universal.sql и rules/domain-specific/*.sql
ТЕМ ЖЕ способом, каким их исполняет сборка контура (SQLite executescript на таблице
rules — «последнее описание побеждает»), и копит две вещи: действующие правила
(pack_rules) и историю каждой версии каждого правила по коммитам git
(pack_rules_history). База описывает ЗАКОММИЧЕННОЕ состояние (HEAD) — НЕ рабочую
копию: первая редакция метила версию из рабочей копии временем сборки, и повторная
сборка при незакоммиченной правке правил переписывала файл заново на каждом прогоне
(поймано на решающем прогоне: приёмка на чистом дереве этого не видела, а на клоне с
чужой незакоммиченной правкой — увидела). Эта приёмка проверяет: число и тела
действующих правил на настоящем пакете (только чтение, по HEAD), поведение на
дублирующемся ключе, появление/изменение/снятие правила по коммитам подставного
git-репозитория с фиксированными датами, что повторная сборка не трогает файл — ОБА
варианта: чистое дерево и дерево с незакоммиченной правкой правил, — что --check
ловит расхождение с HEAD, и что правка только в рабочей копии в базу не попадает
(и печатается строка об этом).

Подставные git-репозитории — только во временных каталогах (tempfile); настоящий
клон пакета читается ТОЛЬКО на чтение (pack-rules.db в нём НЕ создаётся).

Нарочные поломки (А/Б/В/Г) применяются К ТЕКСТУ сборщика В ПАМЯТИ (compile+exec с
настоящим __file__) — на диск ничего не пишется; под каждой поломкой прогоняется
только тот случай, который она обязана провалить.
"""
from __future__ import annotations

import io
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_TOOL_PATH = HERE / "build-pack-rules-db.py"
PACK_ROOT = HERE.parent.parent  # vnext/tools -> корень клона

CASES = 0
PASSED = 0


def case(title: str, verdict: bool, detail: str) -> bool:
    global CASES, PASSED
    CASES += 1
    PASSED += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def load_build_tool(patch=None, name="build_tool_bite"):
    """Гружает build-pack-rules-db.py как модуль. `patch(src) -> (новый_текст, число)`
    правит ИСХОДНИК В ПАМЯТИ (нарочная поломка) — на диск ничего не пишется.
    __file__ остаётся настоящим путём, чтобы PACK_ROOT_DEFAULT считался верно."""
    src = BUILD_TOOL_PATH.read_text(encoding="utf-8")
    if patch is not None:
        new_src, n = patch(src)
        if n < 1:
            raise AssertionError("поломка не нашла свою цель в исходнике — "
                                  "сборщик мог измениться, поломку надо пересмотреть")
        src = new_src
    spec = importlib.util.spec_from_file_location(name, str(BUILD_TOOL_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    code = compile(src, str(BUILD_TOOL_PATH), "exec")
    exec(code, mod.__dict__)
    return mod


# ── стенд: подставной git-репозиторий с фиксированными датами коммитов ──────────

def git_run(repo: Path, args, env=None) -> bytes:
    cmd = ["git", "-C", str(repo), "-c", "user.name=bite-fixture",
           "-c", "user.email=bite-fixture@invalid", "-c", "commit.gpgsign=false"] + args
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if proc.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + " -> " +
                            proc.stderr.decode("utf-8", errors="replace"))
    return proc.stdout


def git_commit(repo: Path, message: str, when_iso: str) -> str:
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "bite-fixture"
    env["GIT_AUTHOR_EMAIL"] = "bite-fixture@invalid"
    env["GIT_AUTHOR_DATE"] = when_iso
    env["GIT_COMMITTER_DATE"] = when_iso
    git_run(repo, ["add", "-A"])
    git_run(repo, ["commit", "-m", message], env=env)
    return git_run(repo, ["rev-parse", "HEAD"]).decode("utf-8").strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def date_utc_str(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


UNIVERSAL_V1 = ("INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
                "('rule-a', 'body A v1', 'owner', 1),\n"
                "('rule-b', 'body B', 'owner', 1);\n")
UNIVERSAL_V2 = ("INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
                "('rule-a', 'body A v2', 'owner', 1),\n"
                "('rule-b', 'body B', 'owner', 1);\n")
UNIVERSAL_V3 = ("INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
                "('rule-a', 'body A v2', 'owner', 1);\n")

D1 = "2026-01-01T00:00:00+00:00"
D2 = "2026-01-02T00:00:00+00:00"
D3 = "2026-01-03T00:00:00+00:00"


def build_case3_fixture(tmp: Path):
    """Три коммита с фиксированными датами: rule-a заведено и изменено, rule-b
    заведено и снято. После третьего коммита рабочая копия ЧИСТАЯ (без незакоммиченных
    правок) — этот же стенд служит «чистым деревом» для случая ④ (вариант 1)."""
    repo = tmp / "repo3"
    repo.mkdir()
    git_run(repo, ["init"])
    write_text(repo / "rules" / "universal.sql", UNIVERSAL_V1)
    c1 = git_commit(repo, "рабочая версия 1: rule-a, rule-b", D1)
    write_text(repo / "rules" / "universal.sql", UNIVERSAL_V2)
    c2 = git_commit(repo, "рабочая версия 2: rule-a изменено", D2)
    write_text(repo / "rules" / "universal.sql", UNIVERSAL_V3)
    c3 = git_commit(repo, "рабочая версия 3: rule-b снято", D3)
    return repo, c1, c2, c3


def run_case3_checks(mod, repo: Path, c1: str, c2: str, c3: str):
    timeline, _commits, _unparsed = mod.build_timeline(repo)
    ha1, ha2, hb = mod.text_sha("body A v1"), mod.text_sha("body A v2"), mod.text_sha("body B")

    checks = []
    ea1 = timeline.history.get(("universal", "rule-a", ha1))
    checks.append(("rule-a v1 first_commit=коммит 1", ea1 is not None and ea1.first_commit == c1))
    checks.append(("rule-a v1 first_seen_at=дата коммита 1", ea1 is not None and ea1.first_seen_at == date_utc_str(D1)))
    checks.append(("rule-a v1 replaced_at=дата коммита 2", ea1 is not None and ea1.replaced_at == date_utc_str(D2)))

    ea2 = timeline.history.get(("universal", "rule-a", ha2))
    checks.append(("rule-a v2 first_commit=коммит 2", ea2 is not None and ea2.first_commit == c2))
    checks.append(("rule-a v2 first_seen_at=дата коммита 2", ea2 is not None and ea2.first_seen_at == date_utc_str(D2)))
    checks.append(("rule-a v2 всё ещё действует (replaced_at пуст)", ea2 is not None and ea2.replaced_at is None))

    eb = timeline.history.get(("universal", "rule-b", hb))
    checks.append(("rule-b first_commit=коммит 1", eb is not None and eb.first_commit == c1))
    checks.append(("rule-b first_seen_at=дата коммита 1", eb is not None and eb.first_seen_at == date_utc_str(D1)))
    checks.append(("rule-b replaced_at=дата коммита 3 (снятие)", eb is not None and eb.replaced_at == date_utc_str(D3)))

    row_a = timeline.pack_rules.get(("universal", "rule-a"))
    checks.append(("pack_rules rule-a: текущий текст — версия 2", row_a is not None and row_a.text_sha == ha2))
    checks.append(("pack_rules rule-a: не снята", row_a is not None and row_a.removed_at is None))

    row_b = timeline.pack_rules.get(("universal", "rule-b"))
    checks.append(("pack_rules rule-b: снята датой коммита 3", row_b is not None and row_b.removed_at == date_utc_str(D3)))

    versions_a = [k for k in timeline.history if k[0] == "universal" and k[1] == "rule-a"]
    checks.append(("у rule-a две версии в истории", len(versions_a) == 2))

    ok = all(v for _, v in checks)
    detail = "; ".join(f"{name}" for name, v in checks if not v) if not ok else \
        f"все {len(checks)} утверждений совпали"
    return ok, detail


# ── стенд: правка только в рабочей копии (без коммита) — служит и случаю ⑥,
#    и «грязному дереву» случая ④ (вариант 2) ────────────────────────────────

def build_dirty_fixture(tmp: Path, subdir: str = "repo_dirty"):
    repo = tmp / subdir
    repo.mkdir()
    git_run(repo, ["init"])
    write_text(repo / "rules" / "universal.sql",
               "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
               "('rule-c', 'body C v1', 'owner', 1);\n")
    c1 = git_commit(repo, "rule-c заведено", "2026-02-01T00:00:00+00:00")
    write_text(repo / "rules" / "universal.sql",
               "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
               "('rule-c', 'body C v2 — только в рабочей копии, без коммита', 'owner', 1);\n")
    return repo, c1


def run_case6_checks(mod, repo: Path, c1: str, out_path: Path):
    """Случай ⑥: правка ТОЛЬКО в рабочей копии (без коммита) → в базе её нет
    (текст правила = версии HEAD), история несёт ОДНУ версию, и печатается строка
    о неотправленных правках."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.do_build(repo, out_path)
    printed = buf.getvalue()

    conn = sqlite3.connect(str(out_path))
    row = conn.execute("SELECT body, text_sha, pack_commit, removed_at FROM pack_rules "
                        "WHERE rule_set='universal' AND rule_key='rule-c'").fetchone()
    hist = conn.execute("SELECT text_sha, first_commit FROM pack_rules_history "
                         "WHERE rule_set='universal' AND rule_key='rule-c'").fetchall()
    conn.close()

    sha_v1 = mod.text_sha("body C v1")
    body_ok = row is not None and row[0] == "body C v1"
    ok = (rc == 0 and body_ok and row[1] == sha_v1 and row[2] == c1 and row[3] is None
          and len(hist) == 1 and hist[0][0] == sha_v1 and hist[0][1] == c1
          and "неотправленные правки" in printed and "universal.sql" in printed)
    detail = (f"тело в базе: {'версия HEAD (верно)' if body_ok else (row[0] if row else 'строки нет')}; "
              f"версий истории у rule-c: {len(hist)} (ждём 1); "
              f"строка о неотправленных правках: {'неотправленные правки' in printed}")
    return ok, detail


# ── стенд: ключ, снятый ЕЩЁ ДО первой сборки базы (не путать с «снят ЭТОЙ
#    сборкой») — служит случаю ⑦ ─────────────────────────────────────────────

def build_case7_fixture(tmp: Path):
    repo = tmp / "repo7"
    repo.mkdir()
    git_run(repo, ["init"])
    write_text(repo / "rules" / "universal.sql",
               "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
               "('rule-x', 'body X', 'owner', 1),\n"
               "('rule-y', 'body Y', 'owner', 1);\n")
    git_commit(repo, "rule-x, rule-y заведены", "2026-03-01T00:00:00+00:00")
    write_text(repo / "rules" / "universal.sql",
               "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
               "('rule-x', 'body X', 'owner', 1);\n")
    git_commit(repo, "rule-y снято", "2026-03-02T00:00:00+00:00")
    return repo


def run_case7_checks(mod, repo: Path, out_path: Path):
    """Случай ⑦: на ПЕРВОЙ сборке базы rule-y уже снят (сняли ДО того, как база
    вообще существовала) — итоговая строка обязана назвать его «пришедшим уже
    снятым», а НЕ «новым» (в старой редакции оба попадали в одно число «новых
    ключей», и приёмщик прочёл его как счёт действующих правил)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.do_build(repo, out_path)
    printed = buf.getvalue()

    conn = sqlite3.connect(str(out_path))
    row_x = conn.execute("SELECT removed_at FROM pack_rules "
                          "WHERE rule_set='universal' AND rule_key='rule-x'").fetchone()
    row_y = conn.execute("SELECT removed_at FROM pack_rules "
                          "WHERE rule_set='universal' AND rule_key='rule-y'").fetchone()
    conn.close()

    active_line = "действующих новых: 1" in printed
    removed_line = "пришли уже снятыми (сняты раньше этой сборки): 1" in printed
    ok = (rc == 0 and row_x is not None and row_x[0] is None
          and row_y is not None and row_y[0] is not None
          and active_line and removed_line)
    detail = (f"rule-x (действующий) removed_at={row_x[0] if row_x else 'строки нет'} (ждём None); "
              f"rule-y (снят ДО сборки) removed_at={row_y[0] if row_y else 'строки нет'} (ждём не пусто); "
              f"строка «действующих новых: 1»: {active_line}; "
              f"строка «пришли уже снятыми …: 1»: {removed_line}")
    return ok, detail


def run_rebuild_twice(mod, pack_root: Path, out_path: Path):
    """Общая логика случая ④: два прогона сборки подряд без НОВЫХ изменений
    источника — второй обязан не тронуть файл и напечатать «не изменилась»,
    ЧТО БЫ ни было в рабочей копии (чистой или с незакоммиченной правкой) —
    строка о неотправленных правках стабильна между прогонами."""
    rc1 = mod.do_build(pack_root, out_path)
    bytes1 = out_path.read_bytes()
    mtime1 = out_path.stat().st_mtime
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc2 = mod.do_build(pack_root, out_path)
    bytes2 = out_path.read_bytes()
    mtime2 = out_path.stat().st_mtime
    printed = buf.getvalue()
    ok = (rc1 == 0 and rc2 == 0 and "не изменилась" in printed
          and bytes1 == bytes2 and mtime1 == mtime2)
    return ok, printed


# ── поломка (А): дублирующийся ключ — первое описание вместо последнего ─────────

def patch_a(src: str):
    old_ddl = "    rule_key       TEXT NOT NULL UNIQUE,\n"
    new_ddl = "    rule_key       TEXT NOT NULL,\n"  # ПОЛОМКА (А): без UNIQUE, OR REPLACE не схлопывает дубли
    n1 = src.count(old_ddl)
    src2 = src.replace(old_ddl, new_ddl)

    old_dict = ("    rows = conn.execute(\"SELECT rule_key, body, locked_by FROM rules\").fetchall()\n"
                "    conn.close()\n"
                "    return ParseResult(ok=True, rules={k: (b, l) for k, b, l in rows}, error=None)\n")
    new_dict = ("    rows = conn.execute(\"SELECT rule_key, body, locked_by FROM rules\").fetchall()\n"
                "    conn.close()\n"
                "    first_wins = {}\n"
                "    for k, b, l in rows:\n"
                "        first_wins.setdefault(k, (b, l))  # ПОЛОМКА (А): первое описание побеждает\n"
                "    return ParseResult(ok=True, rules=first_wins, error=None)\n")
    n2 = src2.count(old_dict)
    src3 = src2.replace(old_dict, new_dict)
    return src3, min(n1, n2)


def find_duplicate_key(source: str) -> str:
    keys = re.findall(r"^\('([a-z0-9-]+)',", source, re.M)
    counts = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1
    candidates = [k for k, c in counts.items() if c >= 2]
    if not candidates:
        raise AssertionError("в universal.sql не нашлось ключа с несколькими описаниями — "
                              "стенд для случая ② не годится, файл мог измениться")
    return "timestamp-utc-in-sqlite" if "timestamp-utc-in-sqlite" in candidates else candidates[0]


def statement_start_lines(lines):
    return [i for i, line in enumerate(lines)
            if line.startswith("INSERT OR REPLACE INTO rules") or line.startswith("UPDATE rules SET")]


def prefix_before_last_occurrence(source: str, rule_key: str):
    lines = source.split("\n")
    marker = f"('{rule_key}',"
    key_lines = [i for i, line in enumerate(lines) if line.strip() == marker]
    if len(key_lines) < 2:
        return None
    starts = statement_start_lines(lines)
    last_key_line = key_lines[-1]
    containing = max(i for i in starts if i <= last_key_line)
    return "\n".join(lines[:containing])


def run_duplicate_key_check(mod, source: str):
    """Случай ② (часть 2): ключ, описанный НЕСКОЛЬКО раз, — действующее тело обязано
    быть телом ПОСЛЕДНЕГО описания, а не более раннего."""
    dup_key = find_duplicate_key(source)
    full_result = mod.parse_rules_sql(source)
    prefix = prefix_before_last_occurrence(source, dup_key)
    if prefix is None:
        raise AssertionError(f"не нашёл вторую строку ключа {dup_key} — стенд не годится")
    partial_result = mod.parse_rules_sql(prefix)
    body_full = full_result.rules.get(dup_key, ("", ""))[0]
    body_partial = partial_result.rules.get(dup_key, ("", ""))[0]
    ok = full_result.ok and partial_result.ok and body_partial != "" and body_partial != body_full
    detail = (f"ключ «{dup_key}»: тело до последнего описания и тело после — "
              f"{'разные' if body_partial != body_full else 'СОВПАЛИ (ждём разные)'}")
    return ok, detail, dup_key


# ── поломка (Б): даты сборки вместо дат коммитов ────────────────────────────────

def patch_b(src: str):
    old = "        when = commit_date_utc(pack_root, commit)\n"
    new = ("        when = datetime.now(timezone.utc).strftime(TIME_FORMAT)  "
           "# ПОЛОМКА (Б): дата сборки вместо даты коммита\n")
    return src.replace(old, new), src.count(old)


# ── поломка (В): база переписывается всегда, даже без изменений ────────────────

def patch_v(src: str):
    old = "    unchanged = old_dump is not None and old_dump == new_dump\n"
    new = "    unchanged = False  # ПОЛОМКА (В): всегда считать базу изменившейся\n"
    return src.replace(old, new), src.count(old)


# ── поломка (Г): действующие правила берутся с диска, а не с HEAD ──────────────

def patch_g(src: str):
    old = "    return timeline, commits, unparsed\n"
    new = (
        "    _bug_time = datetime.now(timezone.utc).strftime(TIME_FORMAT)  # ПОЛОМКА (Г)\n"
        "    _bug_sets = {}\n"
        "    for _p in all_paths:\n"
        "        _bug_sets[rule_set_for(_p)] = _p\n"
        "    for _rs, _rel in _bug_sets.items():\n"
        "        _abs = pack_root / _rel\n"
        "        if _abs.exists():\n"
        "            _content = normalize_source(_abs.read_bytes())\n"
        "            _result = parse_rules_sql(_content)\n"
        "            if _result.ok:\n"
        "                timeline.apply_snapshot(_rs, _result.rules, None, _bug_time)  "
        "# ПОЛОМКА (Г): правила с диска вместо HEAD\n"
        "    return timeline, commits, unparsed\n"
    )
    return src.replace(old, new), src.count(old)


def main() -> int:
    if not BUILD_TOOL_PATH.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого нет — {BUILD_TOOL_PATH}")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="bite-pack-rules-db-"))
    ok_all = True
    try:
        bt = load_build_tool()

        # ── ①②: настоящий пакет, ТОЛЬКО ЧТЕНИЕ, ПО HEAD (не по диску) ────────
        timeline, commits, unparsed = bt.build_timeline(PACK_ROOT)
        universal_source = bt.show_file_at(PACK_ROOT, "HEAD", "rules/universal.sql")
        full_result = bt.parse_rules_sql(universal_source)

        active_universal = {rk: row for (rs, rk), row in timeline.pack_rules.items()
                             if rs == "universal" and row.removed_at is None}
        n_timeline = len(active_universal)
        n_direct = len(full_result.rules)
        ok_all &= case(
            "① число действующих правил universal = числу ключей после исполнения "
            "universal.sql (HEAD) средствами SQLite",
            full_result.ok and n_timeline == n_direct and n_direct > 0,
            f"из полного обхода истории (до HEAD): {n_timeline}; из прямого исполнения "
            f"файла на HEAD: {n_direct} (число берётся из самого исполнения, не вписано в код)")

        mismatches = [rk for rk, row in active_universal.items()
                      if full_result.rules.get(rk) != (row.body, row.locked_by)]
        dup_ok, dup_detail, dup_key = run_duplicate_key_check(bt, universal_source)
        ok_all &= case(
            "② тело каждого действующего правила = телу после исполнения файла HEAD "
            "(последнее описание побеждает), включая дублирующийся ключ",
            not mismatches and dup_ok,
            f"разошедшихся тел: {len(mismatches)} (ждём 0); дублирующийся ключ, "
            f"найденный сам: «{dup_key}» — {dup_detail}")

        # ── ③: подставной git-репозиторий с фиксированными датами ──────────
        repo3, c1, c2, c3 = build_case3_fixture(tmp_root)
        ok3, detail3 = run_case3_checks(bt, repo3, c1, c2, c3)
        ok_all &= case(
            "③ на подставном репозитории: появление · изменение · снятие правила "
            "по трём коммитам с фиксированными датами",
            ok3, detail3)

        # ── ④: повторная сборка без изменений не трогает файл — ДВА варианта ─
        out4a = tmp_root / "out4a" / "pack-rules.db"
        ok4a, printed4a = run_rebuild_twice(bt, repo3, out4a)

        repo_dirty, c_dirty = build_dirty_fixture(tmp_root, "repo_dirty_case4")
        out4b = tmp_root / "out4b" / "pack-rules.db"
        ok4b, printed4b = run_rebuild_twice(bt, repo_dirty, out4b)

        ok_all &= case(
            "④ повторная сборка без изменений не трогает файл и печатает «не изменилась» "
            "— на чистом дереве И на дереве с незакоммиченной правкой правил",
            ok4a and ok4b,
            f"чистое дерево: {'не изменилась' in printed4a}; дерево с незакоммиченной "
            f"правкой: {'не изменилась' in printed4b} (решающий прогон провалился именно "
            f"на втором варианте — версия из рабочей копии метилась временем сборки)")

        # ── ⑤: --check ловит расхождение с HEAD ─────────────────────────────
        out5 = tmp_root / "out5" / "pack-rules.db"
        rc5_build = bt.do_build(PACK_ROOT, out5)
        buf_ok = io.StringIO()
        with redirect_stdout(buf_ok):
            rc_check_ok = bt.do_check(PACK_ROOT, out5)
        row = ("universal", next(iter(active_universal)))
        bad_path = tmp_root / "out5" / "pack-rules-bad.db"
        shutil.copy(out5, bad_path)
        conn = sqlite3.connect(str(bad_path))
        conn.execute("UPDATE pack_rules SET text_sha='0000000000000000' "
                     "WHERE rule_set=? AND rule_key=?", row)
        conn.commit()
        conn.close()
        buf_bad = io.StringIO()
        with redirect_stdout(buf_bad):
            rc_check_bad = bt.do_check(PACK_ROOT, bad_path)
        printed_bad = buf_bad.getvalue()
        ok_all &= case(
            "⑤ --check: код 0 на свежей базе (сверка с HEAD), код 1 и имя ключа — "
            "на подменённом отпечатке",
            rc5_build == 0 and rc_check_ok == 0 and rc_check_bad == 1 and row[1] in printed_bad,
            f"код на свежей: {rc_check_ok} (ждём 0); код на подменённой: {rc_check_bad} "
            f"(ждём 1); ключ «{row[1]}» в выводе подменённой: {row[1] in printed_bad}")

        # ── ⑥: правка только в рабочей копии → в базе её нет ─────────────────
        repo6, c6_1 = build_dirty_fixture(tmp_root, "repo6")
        out6 = tmp_root / "out6" / "pack-rules.db"
        ok6, detail6 = run_case6_checks(bt, repo6, c6_1, out6)
        ok_all &= case(
            "⑥ правка только в рабочей копии (без коммита): в базе — версия HEAD, "
            "не рабочей копии, + строка о неотправленных правках",
            ok6, detail6)

        # ── ⑦: строка итога первой сборки различает «новых» и «пришедших уже снятыми» ──
        repo7 = build_case7_fixture(tmp_root)
        out7 = tmp_root / "out7" / "pack-rules.db"
        ok7, detail7 = run_case7_checks(bt, repo7, out7)
        ok_all &= case(
            "⑦ итог первой сборки: ключ, снятый ДО того как база вообще существовала, "
            "назван «пришедшим уже снятым», а не «новым»",
            ok7, detail7)

        # ── поломка (А): первое описание вместо последнего -> должен провалиться ② ──
        bt_a = load_build_tool(patch=patch_a, name="build_tool_bite_a")
        dup_ok_a, dup_detail_a, dup_key_a = run_duplicate_key_check(bt_a, universal_source)
        caught_a = not dup_ok_a
        ok_all &= case(
            "поломка (А) «первое описание побеждает» поймана случаем ②",
            caught_a,
            f"под поломкой: {dup_detail_a} — случай ② {'провалился' if caught_a else 'НЕ провалился (поломка не поймана)'}")

        # ── поломка (Б): даты сборки вместо дат коммитов -> должен провалиться ③ ──
        bt_b = load_build_tool(patch=patch_b, name="build_tool_bite_b")
        ok3_b, detail3_b = run_case3_checks(bt_b, repo3, c1, c2, c3)
        caught_b = not ok3_b
        ok_all &= case(
            "поломка (Б) «дата сборки вместо даты коммита» поймана случаем ③",
            caught_b,
            f"под поломкой: {detail3_b} — случай ③ {'провалился' if caught_b else 'НЕ провалился (поломка не поймана)'}")

        # ── поломка (В): база переписывается всегда -> должен провалиться ④ ──
        bt_v = load_build_tool(patch=patch_v, name="build_tool_bite_v")
        out_v = tmp_root / "out_v" / "pack-rules.db"
        ok4_v, printed4_v = run_rebuild_twice(bt_v, repo3, out_v)
        caught_v = not ok4_v
        ok_all &= case(
            "поломка (В) «база переписывается всегда» поймана случаем ④",
            caught_v,
            f"под поломкой строка «не изменилась» во втором прогоне: "
            f"{'не изменилась' in printed4_v} (ждём False) — случай ④ "
            f"{'провалился' if caught_v else 'НЕ провалился (поломка не поймана)'}")

        # ── поломка (Г): правила с диска вместо HEAD -> должен провалиться ⑥ ──
        bt_g = load_build_tool(patch=patch_g, name="build_tool_bite_g")
        out6_g = tmp_root / "out6_g" / "pack-rules.db"
        ok6_g, detail6_g = run_case6_checks(bt_g, repo6, c6_1, out6_g)
        caught_g = not ok6_g
        ok_all &= case(
            "поломка (Г) «правила с диска вместо HEAD» поймана случаем ⑥",
            caught_g,
            f"под поломкой: {detail6_g} — случай ⑥ {'провалился' if caught_g else 'НЕ провалился (поломка не поймана)'}")

        if unparsed:
            print(f"ℹ️  на настоящем пакете не разобралось версий: {len(unparsed)} "
                  f"(не входит в приёмку, но названо вслух)")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print()
    print(f"{'✅ ПРИНЯТО' if ok_all else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, прошло {PASSED}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
