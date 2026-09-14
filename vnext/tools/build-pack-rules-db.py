#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build-pack-rules-db.py — сборщик базы правил пакета GORDI (карточка #608).

Строит из rules/universal.sql и rules/domain-specific/*.sql базу с ДЕЙСТВУЮЩИМИ
правилами пакета (pack_rules) и ИСТОРИЕЙ каждой версии каждого правила по коммитам
git (pack_rules_history) — чтобы уже собранный контур мог узнать, какие правила
пакета новые или изменились, и когда именно.

⚠️ База описывает ЗАКОММИЧЕННОЕ состояние (HEAD), а НЕ рабочую копию. Первая редакция
брала действующие правила с диска и метила версию, которой ещё нет в истории, временем
СБОРКИ — а время сборки меняется на каждом прогоне, и повторная сборка при незакоммиченной
правке правил переписывала файл заново и заново. Порядок публикации теперь: коммит
правил -> сборка базы -> коммит базы (два коммита; база у HEAD всегда описывает правила
HEAD). Если рабочая копия разошлась с HEAD, сборщик печатает об этом строку, но правила
рабочей копии в базу НЕ попадают и код выхода не меняется — это не отказ.

Файлы правил разбираются НЕ регулярными выражениями, а тем же способом, каким их
исполняет сборка контура (scripts/init-group.py): всё содержимое файла целиком
отдаётся SQLite (executescript) на таблицу rules — так «последнее описание
побеждает» (INSERT OR REPLACE) считает сам SQLite, а не догадка по тексту.

Использование:
    python vnext/tools/build-pack-rules-db.py [--pack-root DIR] [--out FILE] [--check]

--pack-root  корень клона пакета (по умолчанию — вычисляется от расположения
             ЭТОГО файла: vnext/tools -> два уровня вверх).
--out        куда писать базу (по умолчанию <pack-root>/rules/pack-rules.db).
--check      ничего не пишет: сверяет ДЕЙСТВУЮЩИЕ правила HEAD (не рабочей копии)
             с уже собранным файлом --out; код выхода 1 при расхождении.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
PACK_ROOT_DEFAULT = HERE.parent.parent
RULES_DIR_NAME = "rules"
UNIVERSAL_FILE_NAME = "universal.sql"
DOMAIN_SUBDIR_NAME = "domain-specific"
SCHEMA_VERSION = "1"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

# Таблица для разбора .sql-файлов правил СРЕДСТВАМИ SQLite — набор колонок как у
# самой полной живой схемы (mezosync v5 + миграция skill_delivery), но БЕЗ
# CHECK-ограничений: старая версия файла из истории обязана разбираться, даже если
# её содержимое не прошло бы сегодняшние ограничения живого контура.
PARSE_TABLE_DDL = """
CREATE TABLE rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key       TEXT NOT NULL UNIQUE,
    body           TEXT NOT NULL,
    locked_by      TEXT NOT NULL DEFAULT 'coord',
    version        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    basis          TEXT,
    authorized     TEXT,
    source_ref     TEXT,
    expiry_kind    TEXT,
    expiry_cond    TEXT,
    status         TEXT NOT NULL DEFAULT 'active',
    revoked_at     TEXT,
    revoked_by     TEXT,
    revoked_reason TEXT,
    superseded_by  INTEGER,
    skill_delivery TEXT
);
"""

# КОНТРАКТ выходной базы — второй инструмент (bite-pack-rules-db.py и любой другой
# читатель) ждёт ровно эти имена таблиц и колонок.
OUTPUT_SCHEMA_DDL = """
CREATE TABLE pack_rules (
    rule_set        TEXT,
    rule_key        TEXT,
    body            TEXT,
    locked_by       TEXT,
    text_sha        TEXT,
    pack_updated_at TEXT,
    pack_commit     TEXT,
    removed_at      TEXT,
    PRIMARY KEY (rule_set, rule_key)
);
CREATE TABLE pack_rules_history (
    rule_set      TEXT,
    rule_key      TEXT,
    text_sha      TEXT,
    body          TEXT,
    locked_by     TEXT,
    first_commit  TEXT,
    first_seen_at TEXT,
    replaced_at   TEXT,
    PRIMARY KEY (rule_set, rule_key, text_sha)
);
CREATE TABLE pack_rules_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def text_sha(body: str) -> str:
    """КОНТРАКТ отпечатка текста правила — второй инструмент считает ровно так же."""
    normalized = body.replace("\r\n", "\n").rstrip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def normalize_source(data: bytes) -> str:
    """Приводит сырые байты файла правил к тому же виду, в котором их видит SQLite
    при сборке контура (init-group.py читает файл в текстовом режиме — переносы
    строк уже приведены к \\n до того, как текст попадает в executescript)."""
    text = data.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class ParseResult:
    ok: bool
    rules: Dict[str, Tuple[str, str]]  # rule_key -> (body, locked_by)
    error: Optional[str]


def parse_rules_sql(sql_text: str) -> ParseResult:
    """Исполняет текст файла правил СРЕДСТВАМИ SQLite на временной таблице — тем же
    способом, каким его исполняет scripts/init-group.py (conn.executescript). Так
    «последнее описание побеждает» (INSERT OR REPLACE) считает сам SQLite, а не
    разбор текста."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(PARSE_TABLE_DDL)
        conn.executescript(sql_text)
    except sqlite3.Error as exc:
        conn.close()
        return ParseResult(ok=False, rules={}, error=str(exc))
    rows = conn.execute("SELECT rule_key, body, locked_by FROM rules").fetchall()
    conn.close()
    return ParseResult(ok=True, rules={k: (b, l) for k, b, l in rows}, error=None)


def rule_set_for(rel_path: str) -> str:
    p = Path(rel_path)
    if p.name == UNIVERSAL_FILE_NAME and p.parent.name == RULES_DIR_NAME:
        return "universal"
    return p.stem


def run_git(pack_root: Path, args: List[str]) -> bytes:
    proc = subprocess.run(["git", "-C", str(pack_root)] + args,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + " -> " +
                            proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout


def show_file_at(pack_root: Path, commit: str, rel_path: str) -> Optional[str]:
    """Содержимое файла В ЭТОМ коммите; None — файла там ещё не было (или уже не
    стало) — это НЕ ошибка разбора, а обычное отсутствие."""
    proc = subprocess.run(["git", "-C", str(pack_root), "show", f"{commit}:{rel_path}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    return normalize_source(proc.stdout)


def commit_date_utc(pack_root: Path, commit: str) -> str:
    out = run_git(pack_root, ["show", "-s", "--format=%cI", commit]).decode("utf-8").strip()
    dt = datetime.fromisoformat(out)
    return dt.astimezone(timezone.utc).strftime(TIME_FORMAT)


def discover_current_files(pack_root: Path) -> List[str]:
    """Файлы правил, которые есть на диске ПРЯМО СЕЙЧАС (рабочая копия) —
    POSIX-путями относительно pack_root."""
    rules_dir = pack_root / RULES_DIR_NAME
    out: List[str] = []
    universal = rules_dir / UNIVERSAL_FILE_NAME
    if universal.exists():
        out.append(universal.relative_to(pack_root).as_posix())
    domain_dir = rules_dir / DOMAIN_SUBDIR_NAME
    if domain_dir.exists():
        for f in sorted(domain_dir.glob("*.sql")):
            out.append(f.relative_to(pack_root).as_posix())
    return out


def head_files(pack_root: Path) -> List[str]:
    """Файлы правил, как их видит HEAD (git ls-tree) — а НЕ рабочая копия. Это и
    есть источник «действующих сейчас» правил: незакоммиченная правка на состояние
    базы не влияет."""
    try:
        raw = run_git(pack_root, ["ls-tree", "-r", "--name-only", "HEAD", "--",
                                   RULES_DIR_NAME]).decode("utf-8", errors="replace")
    except RuntimeError:
        raw = ""
    out: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        p = Path(line)
        if p.name == UNIVERSAL_FILE_NAME and p.parent.name == RULES_DIR_NAME:
            out.append(p.as_posix())
        elif p.parent.name == DOMAIN_SUBDIR_NAME and p.suffix == ".sql":
            out.append(p.as_posix())
    return sorted(out)


def pending_changes(pack_root: Path) -> List[str]:
    """Пути файлов правил, где рабочая копия РАСХОДИТСЯ с HEAD по содержимому (не
    по времени изменения) — используется ТОЛЬКО для строки-предупреждения, не для
    состояния базы: сравнение стабильно между прогонами, пока никто не коммитит и
    не правит файлы заново, и потому не рушит «база не изменилась»."""
    paths = sorted(set(head_files(pack_root)) | set(discover_current_files(pack_root)))
    diffs = []
    for rel_path in paths:
        abs_path = pack_root / rel_path
        disk = normalize_source(abs_path.read_bytes()) if abs_path.exists() else None
        head = show_file_at(pack_root, "HEAD", rel_path)
        if disk != head:
            diffs.append(rel_path)
    return diffs


def pending_changes_message(files: List[str]) -> str:
    return ("в рабочей копии есть неотправленные правки правил: " + ", ".join(files) +
            " — база их НЕ включает; закоммить правила и собери базу заново")


def discover_all_ever_paths(pack_root: Path) -> List[str]:
    """Объединение файлов правил, которые есть у HEAD, с файлами правил, которые
    КОГДА-ЛИБО существовали (по логу git) — чтобы история не потеряла файл, снятый
    уже из HEAD (сейчас в пакете таких нет, но сборщик обязан не падать, если
    такой появится). Рабочая копия здесь намеренно НЕ участвует — состояние базы
    определяет только HEAD."""
    paths = set(head_files(pack_root))
    try:
        raw = run_git(pack_root, ["log", "--name-only", "--pretty=format:", "--",
                                   RULES_DIR_NAME]).decode("utf-8", errors="replace")
    except RuntimeError:
        raw = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        p = Path(line)
        if p.name == UNIVERSAL_FILE_NAME and p.parent.name == RULES_DIR_NAME:
            paths.add(p.as_posix())
        elif p.parent.name == DOMAIN_SUBDIR_NAME and p.suffix == ".sql":
            paths.add(p.as_posix())
    return sorted(paths)


@dataclass
class HistoryEntry:
    body: str
    locked_by: str
    first_commit: Optional[str]
    first_seen_at: str
    replaced_at: Optional[str] = None


@dataclass
class PackRuleRow:
    body: str
    locked_by: str
    text_sha: str
    pack_updated_at: str
    pack_commit: Optional[str]
    removed_at: Optional[str] = None


class RulesTimeline:
    """Копит действующее состояние (pack_rules) и историю версий
    (pack_rules_history) по мере обхода снимков файлов правил от старого к
    новому. Снимок — это состояние ОДНОГО rule_set (одного файла) в один момент
    (коммит git); рабочая копия сюда не попадает — см. pending_changes()."""

    def __init__(self) -> None:
        self.active: Dict[str, Dict[str, str]] = {}  # rule_set -> {rule_key: text_sha}
        self.history: Dict[Tuple[str, str, str], HistoryEntry] = {}
        self.pack_rules: Dict[Tuple[str, str], PackRuleRow] = {}

    def apply_snapshot(self, rule_set: str, new_rules: Dict[str, Tuple[str, str]],
                        commit: Optional[str], when: str) -> None:
        active_for_set = self.active.setdefault(rule_set, {})
        seen_keys = set(new_rules.keys())

        for rule_key, (body, locked_by) in new_rules.items():
            sha = text_sha(body)
            prev_sha = active_for_set.get(rule_key)
            hist_key = (rule_set, rule_key, sha)

            if prev_sha != sha:
                if hist_key not in self.history:
                    self.history[hist_key] = HistoryEntry(
                        body=body, locked_by=locked_by,
                        first_commit=commit, first_seen_at=when)
                else:
                    self.history[hist_key].replaced_at = None  # снова действует
                if prev_sha is not None:
                    prev_entry = self.history.get((rule_set, rule_key, prev_sha))
                    if prev_entry is not None and prev_entry.replaced_at is None:
                        prev_entry.replaced_at = when
                active_for_set[rule_key] = sha

            entry = self.history[(rule_set, rule_key, sha)]
            self.pack_rules[(rule_set, rule_key)] = PackRuleRow(
                body=body, locked_by=locked_by, text_sha=sha,
                pack_updated_at=entry.first_seen_at, pack_commit=entry.first_commit,
                removed_at=None)

        for rule_key in list(active_for_set.keys()):
            if rule_key in seen_keys:
                continue
            prev_sha = active_for_set.pop(rule_key)
            prev_entry = self.history.get((rule_set, rule_key, prev_sha))
            if prev_entry is not None and prev_entry.replaced_at is None:
                prev_entry.replaced_at = when
            row = self.pack_rules.get((rule_set, rule_key))
            if row is not None and row.removed_at is None:
                row.removed_at = when


def build_timeline(pack_root: Path) -> Tuple[RulesTimeline, List[str], List[dict]]:
    """Полный обход: все коммиты git от старого к новому (по каждому файлу правил —
    тем же способом, каким его исполняет сборка контура), заканчивая последним
    коммитом, что касался правил, — а он и есть HEAD по содержимому файлов правил
    (коммиты ПОСЛЕ него, если такие есть, правил не меняли). Рабочая копия сюда не
    подмешивается — если она разошлась с HEAD, это видно из pending_changes(), а не
    отсюда. Возвращает (таймлайн, список коммитов старого-к-новому, список
    НЕразобранных версий)."""
    all_paths = discover_all_ever_paths(pack_root)
    if not all_paths:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {pack_root / RULES_DIR_NAME} "
                          f"не нашлось ни одного файла правил")

    try:
        commits_raw = run_git(pack_root, ["log", "--reverse", "--pretty=format:%H", "--"]
                               + all_paths)
    except RuntimeError as exc:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: git log не выполнился — {exc}")
    commits = [c for c in commits_raw.decode("utf-8", errors="replace").splitlines() if c.strip()]

    timeline = RulesTimeline()
    unparsed: List[dict] = []

    for commit in commits:
        when = commit_date_utc(pack_root, commit)
        for rel_path in all_paths:
            content = show_file_at(pack_root, commit, rel_path)
            if content is None:
                continue  # файла в этом коммите ещё/уже нет — не ошибка
            result = parse_rules_sql(content)
            rs = rule_set_for(rel_path)
            if not result.ok:
                unparsed.append({"commit": commit, "path": rel_path, "rule_set": rs,
                                  "reason": result.error})
                continue
            timeline.apply_snapshot(rs, result.rules, commit, when)

    return timeline, commits, unparsed


def compute_source_sha(pack_root: Path) -> str:
    """Отпечаток набора файлов правил НА HEAD — только для meta (не входит в
    контракт сравнения «изменилась/нет»). Намеренно не с диска: иначе отпечаток
    менялся бы при каждой незакоммиченной правке, хотя база её не несёт."""
    parts = []
    for rel_path in head_files(pack_root):
        content = show_file_at(pack_root, "HEAD", rel_path) or ""
        parts.append(f"{rel_path}:{hashlib.sha256(content.encode('utf-8')).hexdigest()}")
    return hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:16]


def write_db(path: Path, timeline: RulesTimeline, head_commit: Optional[str],
             source_sha: str, built_at: str) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.executescript(OUTPUT_SCHEMA_DDL)
    for (rs, rk), row in sorted(timeline.pack_rules.items()):
        conn.execute(
            "INSERT INTO pack_rules (rule_set, rule_key, body, locked_by, text_sha, "
            "pack_updated_at, pack_commit, removed_at) VALUES (?,?,?,?,?,?,?,?)",
            (rs, rk, row.body, row.locked_by, row.text_sha, row.pack_updated_at,
             row.pack_commit, row.removed_at))
    for (rs, rk, sha), entry in sorted(timeline.history.items()):
        conn.execute(
            "INSERT INTO pack_rules_history (rule_set, rule_key, text_sha, body, "
            "locked_by, first_commit, first_seen_at, replaced_at) VALUES (?,?,?,?,?,?,?,?)",
            (rs, rk, sha, entry.body, entry.locked_by, entry.first_commit,
             entry.first_seen_at, entry.replaced_at))
    meta = {"schema_version": SCHEMA_VERSION, "built_at": built_at,
            "head_commit": head_commit or "", "source_sha": source_sha}
    for k, v in meta.items():
        conn.execute("INSERT INTO pack_rules_meta (key, value) VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()


def dump_comparable(path: Path):
    """Содержимое pack_rules + pack_rules_history, отсортированное — ЭТО и есть
    контракт «изменилась/нет» (built_at и прочая meta сюда намеренно не входят)."""
    conn = sqlite3.connect(str(path))
    try:
        pr = conn.execute(
            "SELECT rule_set, rule_key, body, locked_by, text_sha, pack_updated_at, "
            "pack_commit, removed_at FROM pack_rules ORDER BY rule_set, rule_key"
        ).fetchall()
        ph = conn.execute(
            "SELECT rule_set, rule_key, text_sha, body, locked_by, first_commit, "
            "first_seen_at, replaced_at FROM pack_rules_history "
            "ORDER BY rule_set, rule_key, text_sha"
        ).fetchall()
        return pr, ph
    finally:
        conn.close()


def diff_summary(old_dump, new_dump) -> Tuple[int, int, int, int]:
    """Действующих новых · пришедших УЖЕ снятыми (ключа не было в старой базе, но в
    новой он сразу с removed_at — отменён ДО этой сборки, просто раньше не входил в
    базу вовсе) · изменённых (текст разошёлся, оба варианта действующие) · снятых
    ИМЕННО этой сборкой (был действующим, стал снят).

    ⚠️ «Новых» и «снятых уже раньше» — РАЗНЫЕ числа: на первой сборке пакета в
    pack_rules сразу оказываются и действующие ключи, и ключи, снятые ЕЩЁ ДО HEAD
    (removed_at из истории) — раньше строка итога звала оба «новыми», и приёмщик
    читал вслух число, которое не сходилось со строкой «правил сейчас по наборам»."""
    old_pr = {(r[0], r[1]): r for r in (old_dump[0] if old_dump else [])}
    new_pr = {(r[0], r[1]): r for r in new_dump[0]}
    added_active = added_removed = changed = newly_removed = 0
    for key, row in new_pr.items():
        old_row = old_pr.get(key)
        new_sha, new_removed = row[4], row[7]
        if old_row is None:
            if new_removed is not None:
                added_removed += 1
            else:
                added_active += 1
            continue
        old_sha, old_removed = old_row[4], old_row[7]
        if new_removed is not None and old_removed is None:
            newly_removed += 1
        elif new_removed is None and new_sha != old_sha:
            changed += 1
    return added_active, added_removed, changed, newly_removed


def compute_universal_domain_overlaps(timeline: RulesTimeline) -> List[Tuple[str, str]]:
    """Ключи, действующие ОДНОВРЕМЕННО в universal и в доменном наборе — реальная
    сборка контура (init-group.py) грузит их ПОСЛЕДОВАТЕЛЬНО в одну таблицу, и
    доменное описание там побеждает; здесь оба набора разобраны ИЗОЛИРОВАННО и
    показаны раздельно (см. rule_set в задании) — стоит назвать вслух, где именно
    это расхождение реально есть."""
    universal_keys = {rk for (rs, rk), row in timeline.pack_rules.items()
                       if rs == "universal" and row.removed_at is None}
    out = []
    for (rs, rk), row in timeline.pack_rules.items():
        if rs != "universal" and row.removed_at is None and rk in universal_keys:
            out.append((rs, rk))
    return sorted(out)


def do_check(pack_root: Path, out_path: Path) -> int:
    if not out_path.exists():
        print(f"⛔ проверка не пройдена: файла базы нет — {out_path}")
        return 1

    current: Dict[Tuple[str, str], str] = {}
    verdict = 0
    for rel_path in head_files(pack_root):
        content = show_file_at(pack_root, "HEAD", rel_path)
        if content is None:
            continue
        result = parse_rules_sql(content)
        rs = rule_set_for(rel_path)
        if not result.ok:
            print(f"⛔ проверка не пройдена: {rel_path} (HEAD) не разобран — {result.error}")
            return 1
        for rk, (body, _locked_by) in result.rules.items():
            current[(rs, rk)] = text_sha(body)

    try:
        conn = sqlite3.connect(str(out_path))
        rows = conn.execute(
            "SELECT rule_set, rule_key, text_sha FROM pack_rules WHERE removed_at IS NULL"
        ).fetchall()
        conn.close()
    except sqlite3.Error as exc:
        print(f"⛔ проверка не пройдена: не читается {out_path} — {exc}")
        return 1
    recorded = {(rs, rk): sha for rs, rk, sha in rows}

    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(k for k in (set(current) & set(recorded)) if current[k] != recorded[k])

    if not added and not removed and not changed:
        print(f"✅ проверка прошла: действующие правила HEAD совпадают с {out_path}")
    else:
        print(f"🔴 проверка нашла ошибку: действующие правила HEAD разошлись с {out_path}")
        for rs, rk in added:
            print(f"  + новое на HEAD, нет в базе: {rs}/{rk}")
        for rs, rk in removed:
            print(f"  - есть в базе, нет на HEAD: {rs}/{rk}")
        for rs, rk in changed:
            print(f"  ~ текст разошёлся: {rs}/{rk}")
        verdict = 1

    pending = pending_changes(pack_root)
    if pending:
        print(pending_changes_message(pending))
    return verdict


def do_build(pack_root: Path, out_path: Path) -> int:
    timeline, commits, unparsed = build_timeline(pack_root)
    head_commit = commits[-1] if commits else None
    source_sha = compute_source_sha(pack_root)
    build_time = datetime.now(timezone.utc).strftime(TIME_FORMAT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.parent / (out_path.name + ".building")
    if tmp_path.exists():
        tmp_path.unlink()
    write_db(tmp_path, timeline, head_commit, source_sha, build_time)

    old_dump = dump_comparable(out_path) if out_path.exists() else None
    new_dump = dump_comparable(tmp_path)
    unchanged = old_dump is not None and old_dump == new_dump

    active_counts: Dict[str, int] = {}
    for (rs, _rk), row in timeline.pack_rules.items():
        if row.removed_at is None:
            active_counts[rs] = active_counts.get(rs, 0) + 1

    if unchanged:
        tmp_path.unlink()
        print(f"база правил не изменилась: {out_path}")
    else:
        added_active, added_removed, changed_n, newly_removed = diff_summary(old_dump, new_dump)
        if out_path.exists():
            out_path.unlink()
        os.replace(str(tmp_path), str(out_path))
        print(f"база правил обновлена: {out_path}")
        print(f"  действующих новых: {added_active} · пришли уже снятыми (сняты раньше "
              f"этой сборки): {added_removed} · изменённых: {changed_n} · снятых этой "
              f"сборкой: {newly_removed} · версий в истории всего: {len(timeline.history)}")

    print()
    print("правил сейчас по наборам:")
    for rs in sorted(active_counts):
        print(f"  {rs}: {active_counts[rs]}")
    print(f"версий в истории: {len(timeline.history)}")
    print(f"коммитов пройдено: {len(commits)}")

    if unparsed:
        print(f"не разобранных версий: {len(unparsed)}")
        for item in unparsed:
            print(f"  коммит {item['commit']}, файл {item['path']}: {item['reason']}")
    else:
        print("не разобранных версий: 0")

    pending = pending_changes(pack_root)
    if pending:
        print(pending_changes_message(pending))

    overlaps = compute_universal_domain_overlaps(timeline)
    if overlaps:
        print("ключи действуют и в universal, и в доменном наборе (в реально собранном "
              "контуре доменное описание побеждает при загрузке следом; здесь оба видны "
              "раздельно, под своим набором):")
        for rs, rk in overlaps:
            print(f"  {rk} — universal и {rs}")

    print()
    print("границы (что сборщик НЕ проверяет): действующие правила (pack_rules) берутся "
          "С HEAD, а не с диска — незакоммиченная правка правил в базу не попадает (см. "
          "строку выше, если она есть). Смотрит только на rule_key/body/locked_by таблицы "
          "rules — остальные её колонки (basis, status, expiry_*, superseded_by и т.п.) не "
          "хранятся и не сверяются. История идёт только по текущей ветке (HEAD) этого "
          "клона — другие ветки, stash и reflog не читаются. Переименование файла правил "
          "не отслеживается как перенос истории — новое имя означает новый rule_set. "
          "Каждый файл правил разбирается ИЗОЛИРОВАННО от остальных: если ключ описан и в "
          "universal.sql, и в доменном файле, реальная сборка контура (init-group.py) "
          "применяет их ПОСЛЕДОВАТЕЛЬНО в одну таблицу, и доменное описание побеждает — "
          "здесь оба показаны раздельно, под своим rule_set (список пересечений — выше, "
          "если он не пуст).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборщик базы правил пакета GORDI (карточка #608)")
    parser.add_argument("--pack-root", type=Path, default=PACK_ROOT_DEFAULT,
                         help="корень клона пакета (по умолчанию — вычисляется от расположения файла)")
    parser.add_argument("--out", type=Path, default=None,
                         help="куда писать базу (по умолчанию <pack-root>/rules/pack-rules.db)")
    parser.add_argument("--check", action="store_true",
                         help="ничего не пишет: сверяет действующие правила рабочей копии с --out")
    args = parser.parse_args()

    pack_root = args.pack_root.resolve()
    out_path = (args.out if args.out is not None
                else pack_root / RULES_DIR_NAME / "pack-rules.db").resolve()

    try:
        run_git(pack_root, ["rev-parse", "--is-inside-work-tree"])
    except RuntimeError as exc:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: {pack_root} — не git-репозиторий ({exc})")
        return 2

    if args.check:
        return do_check(pack_root, out_path)
    return do_build(pack_root, out_path)


if __name__ == "__main__":
    sys.exit(main())
