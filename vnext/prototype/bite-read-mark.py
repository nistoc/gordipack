#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: возврат отметки прочитанного при новом чате роли (карточка #466, пункт ①, третий круг;
план — комментарий карточки 2026-10-31 10:08 UTC).

Предмет: scripts/read_mark.py, его вызовы в read-messages.py, save-phoenix.py, machine_layer.py,
шаг схемы migrations/20261031-read-mark-at-save.py и mezo_stand.stand_env (номер чата стенду не
передаётся).

СТЕНД «B» (синтетический, empty_db + seed_roles; данных живого контура в нём нет):
  записки #4401…#4422 · раздел state роли PROTO сохранён своей рукой в 12:00 · до сохранения
  подтверждено до #4418, после — до #4422 · отметка #4422 · живой чат PROTO и чат COORD
  записаны в role_sessions. Посев шага даёт снимок #4418. Новый чат PROTO обязан получить
  #4419…#4422 снова.
Номер чата ставится явно поверх mezo_stand.stand_env; без номера — вынут.

Запуск:
    python bite-read-mark.py                  # все случаи на испытуемой копии (mezo_target)
    python bite-read-mark.py --list-breaks    # перечень нарочных поломок и ожидаемых провалов
    python bite-read-mark.py --break ИМЯ      # поломка в копиях стенда; ждём провала ровно своих
Коды: 0 — все случаи прошли · 1 — провал (у --break: и тогда, когда поломка поймана; итог
называет строка «ПОЛОМКА ПОЙМАНА РОВНО СВОИМИ СЛУЧАЯМИ») · 2 — приёмка не поставлена или
кончился свой бюджет времени (остаток случаев — «не запустился», стенды убраны).

⛔ Живую базу не пишет: она открывается только на чтение — за схемой (empty_db).
⚖️ НЕ ЛОВИТ (известно): гонку «подтверждение прежнего чата в миллисекунды между возвратом и
выдачей новому» (не воспроизводится надёжно; закрыта замком BEGIN IMMEDIATE в do_ack) ·
незаписанные сессии вне этого стенда · приёмки, копирующие базу мимо mezo_stand.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — где живая база (только за схемой)
import mezo_stand  # noqa: E402 — стенды убираются при успехе, сохраняются при провале
import mezo_target  # noqa: E402 — какую копию испытываем

SCRIPTS = Path(mezo_target.scripts_root())
PACK_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
STEP = "20261031-read-mark-at-save"
CHAT_ENV = "CLAUDE_CODE_SESSION_ID"
ROLE = "PROTO"
BUDGET_S = 240

H = "2026-10-01 12:00:00"          # час сохранения state своей рукой
BEFORE = "2026-10-01 11:00:00"
AFTER = "2026-10-01 13:00:00"
OLD = "a0000000-0000-4000-8000-00000000000a"      # живой чат PROTO, записан в role_sessions
NEW = "b0000000-0000-4000-8000-00000000000b"      # новый чат PROTO
NEW2 = "c0000000-0000-4000-8000-00000000000c"
NEW3 = "d0000000-0000-4000-8000-00000000000d"
COORDCHAT = "e0000000-0000-4000-8000-00000000000e"  # чат COORD
STRAY = "f0000000-0000-4000-8000-00000000000f"      # незаписанная сессия
HIST = "90000000-0000-4000-8000-000000000009"       # чат PROTO только в истории реестра
HISTC = "91000000-0000-4000-8000-000000000091"      # чат COORD только в истории реестра
MOVED = "92000000-0000-4000-8000-000000000092"      # чат, переведённый от COORD к PROTO
ZCHAT = "93000000-0000-4000-8000-000000000093"      # чат роли ZETA, у которой нет отметки прочитанного
LATE = "2026-10-01 13:30:00"                        # после чтения окна (AFTER)
TOKEN = "aaaaaa-bbbbbb"                             # неподтверждённая выдача прежнего чата
WINDOW = [4419, 4420, 4421, 4422]
OWN_BODY = "память PROTO: раздел state стенда B"

TOOLS = ("read-messages.py", "save-phoenix.py", "read-phoenix.py")

# ── НАРОЧНЫЕ ПОЛОМКИ: файл копии · правки (было → стало) · случаи, которые обязаны провалиться
# · (необязательно) случаи, которые МОГУТ провалиться: гонка ловится вероятностно, а порядок строк
# в выдаче без ключа зависит от ветки — такие случаи названы заранее, а не прощены задним числом.
# Ожидания записаны ДО прогона; поломка, поймавшая не те случаи, — находка, а не успех.
BREAKS = {
    "seen-lookup": ("нет поиска в chat_seen и ключа таблицы: известный чат возвращает отметку снова", [
        ("read_mark.py", "    role = role.upper()\n    if _seen(conn, role, chat):\n        return []\n",
         "    role = role.upper()\n"),
        ("read_mark.py", "        if _seen(conn, role, chat):\n            conn.rollback()\n            return []\n", ""),
        ("migration", "        source        TEXT NOT NULL,\n        PRIMARY KEY (role, chat_id))",
         "        source        TEXT NOT NULL)"),
    # K10 и K10b проверяют и отметку: живой чат, зовущий --restore, под этой поломкой считается
    # новым и получает возврат (ожидание дописано после первого прогона поломок 31.10 — проверку
    # отметки в K10 и K10b добавила позже, чем записала ожидания)
    ], {"K2", "K3", "K4", "K10", "K10b", "K11a", "K11b", "K21", "K21b", "KS", "K16", "D2a"}),
    "foreign-chat": ("first_touch не смотрит, за кем записан чат", [
        ("read_mark.py", "    if foreign:                        # чужой чат",
         "    if False:                        # чужой чат"),
    ], {"K6", "K9b", "D2b", "K6b"}),
    "save-no-touch": ("save-phoenix не зовёт проверку нового чата", [
        ("save-phoenix.py", 'read_mark_call("first_touch", conn, role, "save-phoenix")', "[]"),
    ], {"K8", "K50"}),
    "remember-actor": ("снимок пишется и чужой рукой (--actor)", [
        ("read_mark.py", "    if actor.upper() != role or not tables_ready(conn):", "    if not tables_ready(conn):"),
    ], {"K9a"}),
    "remember-owner": ("снимок не смотрит, за кем записан чат", [
        ("read_mark.py", "        foreign, mine_too = foreign_owners(conn, chat, role)\n        if foreign:\n"
                         "            return _shared_lines(chat, role, foreign, \"снимок отметки прочитанного не записан\") if mine_too else []\n"
                         "        if not _seen",
         "        if not _seen"),
    ], {"K9c", "K9d"}),
    "restore-moves": ("--restore пишет снимок", [
        ("save-phoenix.py", '(["↩ снимок отметки прочитанного не сдвинут: это возврат версии (--restore)"]\n                      if args.restore else\n                      read_mark_call("remember", conn, role, actor, "save", at=action_time))',
         'read_mark_call("remember", conn, role, actor, "save", at=action_time)'),
        ("save-phoenix.py", '(["↩ снимок отметки прочитанного не сдвинут: это возврат версии (--restore)"]\n                          if args.restore else\n                          read_mark_call("remember", conn, role, actor, "same-body"))',
         'read_mark_call("remember", conn, role, actor, "same-body")'),
    ], {"K10", "K10b"}),
    "confirm-silent": ("--confirm не пишет снимок", [
        ("save-phoenix.py", 'read_mark_call("remember", conn, role, actor, "confirm")', "[]"),
    ], {"K11a", "K8"}),
    "seed-all-kinds": ("посев берёт отрезки всех видов", [
        ("migration", "AND {MOVING_SEGMENT} AND at < ?", "AND at < ?"),
    ], {"K14b"}),
    "seed-le": ("посев с «не позже» вместо «строго раньше»", [
        ("migration", "AND {MOVING_SEGMENT} AND at < ?", "AND {MOVING_SEGMENT} AND at <= ?"),
    ], {"K15"}),
    "lines-above": ("строки возврата над первой строкой выдачи с ключом", [
        ("read-messages.py", "    if return_lines and (args.all or args.to_me or args.index):",
         "    if return_lines:"),
    ], {"K1"}),
    "forecast-silent": ("машинный слой молчит о возврате", [
        ("machine_layer.py", "            out.extend(_read_mark_forecast(conn, role))\n", ""),
    ], {"K7", "K17", "K18"}),
    "archive-silent": ("строка об архиве молчит", [
        ("read_mark.py", "    if archived:\n        dbq", "    if False:\n        dbq"),
    ], {"K13", "K13c"}),
    "nowhere-silent": ("окна нет ни в ленте, ни в архиве — строка об этом молчит", [
        ("read_mark.py", "    if not n and not archived:", "    if False:"),
    ], {"K13b"}),
    "promise-always": ("«придут снова» и тогда, когда в ленте окна нет", [
        ("read_mark.py", "    if n:\n        tail", "    if True:\n        tail"),
    ], {"K13b", "K13c"}),
    "seed-no-chats": ("посев без известных чатов", [
        ("migration", "    chats = known_chats(conn)\n", "    chats = set()\n"),
    ], {"K3", "K10", "K10b", "K11a", "K11b", "K17", "K21", "K21b"}),
    "no-lock": ("без BEGIN IMMEDIATE и повторной проверки (ловится вероятностно)", [
        ("read_mark.py", '    conn.execute("BEGIN IMMEDIATE")\n    try:\n        # повторная', '    try:\n        # повторная'),
        ("read_mark.py", "        if _seen(conn, role, chat):\n            conn.rollback()\n            return []\n", ""),
        ("migration", "        source        TEXT NOT NULL,\n        PRIMARY KEY (role, chat_id))",
         "        source        TEXT NOT NULL)"),
    ], {"K5b"}, {"K5"}),
    "no-chat-is-new": ("«номера нет — значит новый чат»", [
        ("read_mark.py", '    value = (os.environ.get(CHAT_ENV) or "").strip().lower()\n    return value or None',
         '    value = (os.environ.get(CHAT_ENV) or "").strip().lower()\n    return value or "чат-без-номера"'),
    ], {"K7"}),
    "no-void": ("возврат не гасит выдачи прежнего чата", [
        ("read_mark.py", '            if "read_batches" in _tables(conn):', '            if False:'),
    ], {"K16", "K16b", "K50", "KS"}),
    "void-no-acked": ("гашение без acked_at: перевыдача отдаёт погашенный ключ — запирание", [
        ("read_mark.py", "                    conn.execute(\"UPDATE read_batches SET acked_at = datetime('now') \"\n                                 \"WHERE token = ?\", (token,))\n", ""),
    ], {"K16", "K16b", "KS"}),
    "refusal-text": ("отказ погашенному ключу без команды выхода", [
        ("read-messages.py", "            refusal = read_mark.void_refusal(conn, role, token)", "            refusal = None"),
    ], {"K16b", "KS"}),
    "remember-unseen": ("снимок пишется и без строки chat_seen (решение ①)", [
        ("read_mark.py", "        if not _seen(conn, role, chat):\n            return [", "        if False:\n            return ["),
    ], {"D1"}),
    "owner-history-first": ("история реестра решает раньше текущей записи (решение ②)", [
        ("read_mark.py", '        rows = conn.execute("SELECT DISTINCT upper(role) FROM role_sessions "\n                            "WHERE lower(trim(transcript_id)) = ? ORDER BY 1", (chat,)).fetchall()\n        if rows:\n            return [r[0] for r in rows]\n',
         '        row = conn.execute("SELECT role FROM role_sessions_history WHERE lower(trim(transcript_id)) = ? "\n                           "ORDER BY id DESC LIMIT 1", (chat,)).fetchone()\n        if row:\n            return [row[0].upper()]\n'
         '        rows = conn.execute("SELECT DISTINCT upper(role) FROM role_sessions "\n                            "WHERE lower(trim(transcript_id)) = ? ORDER BY 1", (chat,)).fetchall()\n        if rows:\n            return [r[0] for r in rows]\n'),
    ], {"D2a", "K9c"}),
    "no-seen-without-mark": ("без снимка строка chat_seen не пишется (находка 5)", [
        ("read_mark.py", "        mark = latest_mark(conn, role)\n        new = min(cur, mark[1]) if mark else cur\n",
         "        mark = latest_mark(conn, role)\n        if mark is None:\n            conn.rollback()\n            return []\n        new = min(cur, mark[1]) if mark else cur\n"),
    ], {"F5"}),
    "seed-foreign-hand": ("час посева — confirmed_at/saved_at раздела, кто бы ни писал", [
        ("migration", "    if last_save is None or last_save[0].upper() == role:\n        base = saved_at\n    else:\n        base = own_save",
         "    base = saved_at\n    own_confirm = conn.execute(\"SELECT confirmed_at FROM phoenix WHERE role = ? AND section = 'state'\", (role,)).fetchone()[0]"),
    ], {"K15b"}),
    "big-silent": ("строка «окно большое — начни с --wake» молчит", [
        ("read_mark.py", "    if n > BIG_WINDOW_NOTES or size > BIG_WINDOW_BYTES:\n        lines.append(f\"   ⚠️ окно большое",
         "    if False:\n        lines.append(f\"   ⚠️ окно большое"),
    ], {"KB"}),
    "no-audit": ("возврат не пишется в журнал", [
        ("read_mark.py", "            conn.execute(\"INSERT INTO audit_log (actor_role, action, target, diff_md) \"\n                         \"VALUES (?, 'read_mark_return', ?, ?)\",",
         "            (lambda *a: None)(\"INSERT INTO audit_log (actor_role, action, target, diff_md) \"\n                         \"VALUES (?, 'read_mark_return', ?, ?)\","),
    ], {"KA", "K5", "K4"}),
    "nokey-lines-late": ("в выдачах без ключа строки возврата не первыми", [
        ("read-messages.py", "    if return_lines and (args.all or args.to_me or args.index):\n        for line in return_lines:\n            print(line)\n        return_lines = []\n", ""),
    ], {"KS", "KB"}, {"KC", "K20"}),
    "forecast-foreign": ("прогноз и для чужого чата", [
        ("read_mark.py", "    foreign, _ = foreign_owners(conn, chat, role)\n    if foreign:\n        return []\n    n, size, archived",
         "    n, size, archived"),
    ], {"K17b"}),
    # ── находки противника 31.10 (R1–R3, M1, M2): ожидания записаны до прогона
    "seed-any-reason": ("посев: причина записи в истории не судится (возврат версии и перенос в архив — в счёт)", [
        ("migration", 'f"AND upper(actor) = ? AND {OWN_SAVE_REASONS}"', 'f"AND upper(actor) = ?"'),
    ], {"K14c", "K14d"}),
    "seed-history-foreign": ("посев: рука в истории не судится", [
        ("migration", 'f"AND upper(actor) = ? AND {OWN_SAVE_REASONS}"', 'f"AND ? IS NOT NULL AND {OWN_SAVE_REASONS}"'),
    ], {"K15c"}),
    "seed-no-history": ("посев не смотрит историю разделов — прежний путь по saved_at", [
        ("migration", "    from_history = own_body_save(conn, role)\n", "    from_history = None\n"),
    ], {"K14c", "K14d"}),
    "seed-history-min": ("посев берёт первую свою запись вместо последней", [
        ("migration", 'f"SELECT MAX(saved_at) FROM {table}', 'f"SELECT MIN(saved_at) FROM {table}'),
    ], {"K14e"}),
    "shared-first-row": ("номер за двумя ролями: решает первый ряд реестра", [
        ("read_mark.py", "    owners = owners_of_chat(conn, chat)\n    return [o for o in owners if o != role], role in owners",
         "    owners = owners_of_chat(conn, chat)[:1]\n    return [o for o in owners if o != role], role in owners"),
    ], {"K6b", "K9d"}),
    "remember-cursor-late": ("снимок: отметка прочитанного проверяется после проверки чата", [
        ("read_mark.py", "    cur = _cursor(conn, role)\n    if cur is None:\n        return []\n    chat = chat_id()\n",
         "    cur = _cursor(conn, role)\n    chat = chat_id()\n"),
        ("read_mark.py", "            + _reader_cmd(conn, role)]\n    conn.execute(",
         "            + _reader_cmd(conn, role)]\n    if cur is None:\n        return []\n    conn.execute("),
    ], {"F6"}),
    "index-note-stale": ("указатель после возврата пишет «отметка НЕ сдвинута»", [
        ("read-messages.py", '                     if mark_returned else "отметка прочитанного НЕ сдвинута")',
         '                     if False else "отметка прочитанного НЕ сдвинута")'),
    ], {"K20"}),
    "wake-footer-stale": ("подвал обзора --wake после возврата пишет «НЕ двинута»", [
        ("read-messages.py", '    if _returned_in_run:\n        print("  ⚖️ ЭТО ОБЗОР', '    if False:\n        print("  ⚖️ ЭТО ОБЗОР'),
    ], {"K20"}),
    "stand-env-leak": ("mezo_stand.stand_env передаёт номер чата стенду", [
        ("mezo_stand", "", ""),
    ], {"KE"}),
}

CASES = []
BREAK = None
STARTED = time.monotonic()


def case(cid, title):
    def deco(fn):
        CASES.append((cid, title, fn))
        return fn
    return deco


class NotSet(Exception):
    """Опыт не поставлен (не провал предмета)."""


# ── СТЕНД ──────────────────────────────────────────────────────────────────────────────────
def step_file():
    for root in (SCRIPTS, PACK_SCRIPTS):
        p = root / "migrations" / f"{STEP}.py"
        if p.exists():
            return p
    raise NotSet(f"шага {STEP}.py нет ни в {SCRIPTS}, ни в {PACK_SCRIPTS}")


def patch(path, kind):
    """Поломка в КОПИИ стенда. Образец «было» обязан найтись — иначе поломка не поставлена."""
    if BREAK is None:
        return
    for where, old, new in BREAKS[BREAK][1]:
        if where != kind:
            continue
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise NotSet(f"поломка {BREAK}: образец не найден в {path.name}: {old[:60]!r}")
        path.write_text(text.replace(old, new), encoding="utf-8", newline="")


class Stand:
    def __init__(self, prefix):
        self.root = mezo_stand.new(f"bite-read-mark-{prefix}-")
        self.scripts = self.root / ".mezosync" / "scripts"
        self.db = self.root / ".mezosync" / "mezosync.db"
        for name in TOOLS:
            src = SCRIPTS / name
            if not src.exists():
                raise NotSet(f"в испытуемом каталоге нет {name}")
            mezo_stand.copy_tool(src, self.scripts)
        for name in ("read_mark.py", "machine_layer.py"):
            p = self.scripts / name
            if p.exists():
                patch(p, name)
        for name in TOOLS:
            patch(self.scripts / name, name)
        mig = self.scripts / "migrations"
        mig.mkdir(parents=True, exist_ok=True)
        src_step = step_file()
        shutil.copy2(src_step, mig / src_step.name)
        if not (self.scripts / "schema_journal.py").exists():
            shutil.copy2(src_step.parent.parent / "schema_journal.py", self.scripts / "schema_journal.py")
        patch(mig / src_step.name, "migration")
        self.step = mig / src_step.name

    def env(self, chat):
        env = mezo_stand.stand_env(self.root, PYTHONIOENCODING="utf-8")
        env.pop("MEZO_ROLE", None)
        env.pop(CHAT_ENV, None)
        if chat:
            env[CHAT_ENV] = chat
        return env

    def run(self, tool, args, chat, timeout=60):
        p = subprocess.run([sys.executable, str(self.scripts / tool), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=self.env(chat),
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def rm(self, chat, *args, role=ROLE):
        return self.run("read-messages.py", ["--db", str(self.db), "--role", role, *args], chat)

    def sp(self, chat, *args, role=ROLE):
        return self.run("save-phoenix.py", ["--db", str(self.db), "--role", role, "--section", "state",
                                            *args], chat)

    def rp(self, chat, role=ROLE):
        return self.run("read-phoenix.py", ["--db", str(self.db), "--role", role, "--section", "state"],
                        chat)

    def apply_step(self):
        rc, out = self.run(self.step.relative_to(self.scripts).as_posix(), ["--db", str(self.db)], None)
        if rc != 0:
            raise NotSet(f"шаг схемы не применился (код {rc}): {out[-300:]}")
        return out

    def q(self, sql, args=()):
        con = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()

    def x(self, *statements):
        con = sqlite3.connect(self.db)
        try:
            for sql in statements:
                if isinstance(sql, tuple):
                    con.execute(*sql)
                else:
                    con.execute(sql)
            con.commit()
        finally:
            con.close()

    def mark(self, role=ROLE):
        return self.q("SELECT last_read_id FROM read_cursors WHERE reader_role = ?", (role,))[0][0]

    def latest(self, role=ROLE):
        rows = self.q("SELECT read_mark, how, chat_id FROM phoenix_read_marks WHERE role = ? "
                      "ORDER BY id DESC LIMIT 1", (role,))
        return rows[0] if rows else None

    def ack(self, chat, out, role=ROLE):
        h1, h2 = halves(out)
        if not h1 or not h2:
            # Ключ не выдал ИСПЫТУЕМЫЙ код — это провал предмета, а не неготовый опыт.
            raise AssertionError(f"в выдаче нет ключа: {out[:200]!r}")
        return self.rm(chat, "--ack", f"{h1}-{h2}", role=role)


_TEMPLATE = {}


def blank_db(dst):
    """Пустая база со схемой живой, без таблиц предмета и без записи шага — один раз на прогон."""
    if "path" not in _TEMPLATE:
        tmp = mezo_stand.new("bite-read-mark-template-")
        path = tmp / "blank.db"
        mezo_stand.empty_db(mezo_paths.live_db(), path)
        con = sqlite3.connect(path)
        for t in ("phoenix_read_marks", "chat_seen", "read_batch_voids"):
            con.execute(f"DROP TABLE IF EXISTS {t}")
        con.execute("DELETE FROM schema_migrations WHERE version = ?", (STEP,))
        con.commit()
        con.close()
        _TEMPLATE["path"] = path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_TEMPLATE["path"], dst)


BASE_SEGMENTS = [(1, 4410, "declared", "посев стенда B", "2026-10-01 09:00:00"),
                 (4411, 4418, "read", None, BEFORE),
                 (4419, 4422, "read", None, AFTER)]


def build(prefix, *, mark=4422, segments=None, top=4422, pre=(), post=(), step=True):
    s = Stand(prefix)
    blank_db(s.db)
    mezo_stand.seed_roles(s.db, ["PROTO", "COORD", "SEPA"])
    rows = [("INSERT INTO messages (id, writer_role, timestamp, body_md) VALUES (?, 'COORD', ?, ?)",
             (i, f"2026-10-01 08:{(i - 4400) % 60:02d}:00", f"записка стенда #{i}"))
            for i in range(4401, top + 1)]
    seg = [("INSERT INTO cursor_segments (role, from_id, to_id, kind, basis, authorized, at) "
            "VALUES ('PROTO', ?, ?, ?, ?, ?, ?)", (a, b, k, basis, None if k == "read" else "стенд", at))
           for a, b, k, basis, at in (BASE_SEGMENTS if segments is None else segments)]
    s.x(*rows, *seg,
        ("UPDATE read_cursors SET last_read_id = ? WHERE reader_role = 'PROTO'", (mark,)),
        "UPDATE read_cursors SET last_read_id = 4422 WHERE reader_role IN ('COORD', 'SEPA')",
        ("INSERT INTO phoenix (role, section, body, saved_at, confirmed_at) VALUES ('PROTO', 'state', ?, ?, ?)",
         (OWN_BODY, H, H)),
        ("INSERT INTO phoenix (role, section, body, saved_at, confirmed_at) VALUES ('COORD', 'state', "
         "'память COORD', ?, ?)", (H, H)),
        ("INSERT INTO audit_log (timestamp, actor_role, action, target, diff_md) VALUES "
         "(?, 'PROTO', 'save_phoenix', 'phoenix.PROTO.state', 'Updated state (стенд)')", (H,)),
        ("INSERT INTO role_sessions (role, address, noted_by, source, transcript_id) "
         "VALUES ('PROTO', 'стенд [old]', 'стенд', 'self', ?)", (OLD,)),
        ("INSERT INTO role_sessions (role, address, noted_by, source, transcript_id) "
         "VALUES ('COORD', 'стенд [coord]', 'стенд', 'self', ?)", (COORDCHAT,)),
        *pre)
    if step:
        s.apply_step()
    if post:
        s.x(*post)
    return s


def halves(text):
    h1 = re.search(r"ПЕРВАЯ половина (\w+)", text)
    h2 = re.search(r"ack <первая>-(\w+)", text)
    return (h1.group(1) if h1 else None, h2.group(1) if h2 else None)


def shown(text):
    return [int(m) for m in re.findall(r"^--- #(\d+) ", text, re.M)]


def returned(text, a, b):
    return f"ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА #{a} → #{b}" in text


def returns(s, role=ROLE):
    return s.q("SELECT COUNT(*) FROM audit_log WHERE action = 'read_mark_return' AND target = ?",
               (f"read_cursors.{role}",))[0][0]


OPEN_BATCH = ("INSERT INTO read_batches (token, role, last_id, shown_max) VALUES (?, 'PROTO', 4422, 4422)",
              (TOKEN,))


def need(cond, detail):
    if not cond:
        raise AssertionError(detail)


# ── СЛУЧАИ ─────────────────────────────────────────────────────────────────────────────────
@case("K1", "новый чат: окно приходит, строка возврата сразу под первой строкой с ключом")
def k1():
    s = build("k1")
    rc, out = s.rm(NEW)
    lines = out.splitlines()
    need(rc == 0 and lines and lines[0].startswith("[begin-of-batch]") and "(cursor=4418)" in lines[0],
         f"первая строка: {lines[:1]}")
    need(len(lines) > 1 and returned(lines[1], 4422, 4418), f"вторая строка: {lines[1:2]}")
    need(shown(out) == WINDOW, f"показаны {shown(out)}")
    rc, a = s.ack(NEW, out)
    need(rc == 0 and s.mark() == 4422, f"подтверждение: код {rc}, отметка {s.mark()}")
    return "окно #4419…#4422, строка возврата второй, подтверждение до #4422"


@case("K2", "роль ушла без чтения после сохранения: «возвращать нечего», окно обычным порядком")
def k2():
    s = build("k2", mark=4418, segments=BASE_SEGMENTS[:2])
    _, out = s.rm(NEW)
    need("возвращать нечего" in out, "нет строки «возвращать нечего»")
    need(shown(out) == WINDOW, f"показаны {shown(out)}")
    _, again = s.rm(NEW)
    need("↩" not in again, "второй вызов того же чата снова печатает строку нового чата")
    return "строка один раз, показаны #4419…#4422"


@case("K3", "дочитала и сохранила state своей рукой: новый чат получает пусто")
def k3():
    s = build("k3")
    rc, out = s.sp(OLD, "--body", OWN_BODY + " · дополнено")
    need(rc == 0 and "запомнена отметка прочитанного #4422" in out, f"сохранение: {out[-300:]}")
    _, r = s.rm(NEW)
    need("Нет непрочитанных" in r and "(cursor=4422)" in r and "возвращать нечего" in r, r[:300])
    return "снимок #4422, новый чат — «возвращать нечего» и пусто"


@case("K4", "тот же чат после подтверждения — второго возврата нет")
def k4():
    s = build("k4")
    _, out = s.rm(NEW)
    s.ack(NEW, out)
    _, again = s.rm(NEW)
    need("Нет непрочитанных" in again and "↩" not in again, again[:300])
    need(s.q("SELECT COUNT(*) FROM chat_seen WHERE role='PROTO' AND chat_id=?", (NEW,))[0][0] == 1, "строк chat_seen ≠ 1")
    need(returns(s) == 1, f"возвратов в журнале {returns(s)}")
    return "одна строка chat_seen, один возврат"


@case("K5", "четыре одновременных вызова нового чата, 15 повторов: один возврат, один ключ")
def k5():
    base = build("k5")
    bad = []
    for rep in range(15):
        s = Stand(f"k5r{rep}")
        shutil.copy2(base.db, s.db)
        procs = [subprocess.Popen([sys.executable, str(s.scripts / "read-messages.py"), "--db", str(s.db),
                                   "--role", ROLE], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", env=s.env(NEW))
                 for _ in range(4)]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        # Выдача, столкнувшаяся с соседней, честно отказывает «НЕ ВЫДАНО» (замок ux_batch_race) —
        # это не второй ключ; второй ключ — это два РАЗНЫХ ключа на один хвост.
        firsts = {halves(o)[0] for o in outs} - {None}
        keyless = [o for o in outs if halves(o)[0] is None and "НЕ ВЫДАНО" not in o]
        if returns(s) != 1 or len(firsts) != 1 or keyless:
            bad.append(f"повтор {rep}: возвратов {returns(s)}, ключей {sorted(firsts)}, "
                       f"выдач без ключа и без отказа {len(keyless)}")
    need(not bad, "; ".join(bad[:3]))
    return "15 из 15: один возврат и один ключ на четыре вызова"


@case("K5b", "восемь потоков разом зовут first_touch (барьер перед вызовом), 20 повторов: один возврат")
def k5b():
    import importlib.util
    import threading
    base = build("k5b")
    spec = importlib.util.spec_from_file_location("read_mark_k5b", base.scripts / "read_mark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = os.environ.get(CHAT_ENV)
    os.environ[CHAT_ENV] = NEW
    bad = []
    try:
        for rep in range(20):
            db = base.root / f"k5b-{rep}.db"
            shutil.copy2(base.db, db)
            barrier = threading.Barrier(8)
            got, errors = [], []

            def worker():
                conn = sqlite3.connect(db, timeout=30)
                try:
                    barrier.wait()
                    got.append(module.first_touch(conn, ROLE, "bite-read-mark"))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{type(e).__name__}: {e}")
                finally:
                    conn.close()
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
            n = sum(1 for lines in got if lines and "ВОЗВРАЩЕНА" in lines[0])
            if n != 1 or errors:
                bad.append(f"повтор {rep}: возвратов {n}, сбоев {len(errors)} {errors[:1]}")
    finally:
        if saved is None:
            os.environ.pop(CHAT_ENV, None)
        else:
            os.environ[CHAT_ENV] = saved
    need(not bad, "; ".join(bad[:3]))
    return "20 из 20: восемь одновременных вызовов дали один возврат"


@case("K6", "чат, записанный за COORD, читает ленту PROTO: отметка не тронута")
def k6():
    s = build("k6")
    _, out = s.rm(COORDCHAT)
    need(s.mark() == 4422 and "Нет непрочитанных" in out, f"отметка {s.mark()}")
    need(not s.q("SELECT 1 FROM chat_seen WHERE role='PROTO' AND chat_id=?", (COORDCHAT,)), "строка chat_seen за PROTO")
    return "отметка #4422, строки chat_seen за PROTO нет"


# номер NEW записан после шага и за PROTO, и за COORD (находка противника 31.10, R3)
DUAL = [("UPDATE role_sessions SET transcript_id = ? WHERE role IN ('PROTO', 'COORD')", (NEW,))]


@case("K6b", "номер чата записан за двумя ролями: чужой для обеих, строка об этом у каждой")
def k6b():
    s = build("k6b", post=DUAL)
    _, out = s.rm(NEW)
    need("записан в реестре чатов и за PROTO, и за COORD" in out, out[:300])
    need(s.mark() == 4422 and returns(s) == 0, f"отметка {s.mark()}, возвратов {returns(s)}")
    _, out_c = s.rm(NEW, role="COORD")
    need("записан в реестре чатов и за COORD, и за PROTO" in out_c, out_c[:300])
    need(not s.q("SELECT 1 FROM chat_seen WHERE chat_id = ?", (NEW,)), "строка chat_seen за номером двух ролей")
    return "PROTO и COORD: возврата нет, строка есть, chat_seen пуст"


@case("K7", "номера чата нет: возврата нет, прогноз говорит «номер чата неизвестен»")
def k7():
    s = build("k7")
    _, out = s.rm(None)
    need(s.mark() == 4422 and "Нет непрочитанных" in out, f"отметка {s.mark()}")
    _, p = s.rp(None)
    need("номер чата неизвестен" in p, "прогноз молчит")
    return "отметка #4422, строка прогноза есть"


@case("K8", "новый чат сначала отмечает взгляд на state (--confirm), потом читает ленту")
def k8():
    s = build("k8")
    rc, out = s.sp(NEW, "--confirm")
    need(rc == 0 and returned(out, 4422, 4418) and "прочитай ленту" in out, out[:400])
    need(s.latest() == (4418, "confirm", NEW), f"снимок {s.latest()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "возврат при --confirm, снимок #4418, окно пришло"


@case("K9a", "чужая рука --actor COORD --confirm без номера чата: снимок не двигается, окно цело")
def k9a():
    # Без номера чата: иначе снимок отсекла бы проверка «чей чат», и проверка руки осталась бы
    # без испытания (поломка remember-actor прошла бы незамеченной).
    s = build("k9a")
    rc, out = s.sp(None, "--confirm", "--actor", "COORD")
    need(rc == 0 and s.latest()[1] == "seed", f"снимок {s.latest()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "снимок посева, окно пришло"


@case("K9b", "чат COORD пишет тело PROTO без --actor: отметка и снимок не двигаются, окно цело")
def k9b():
    s = build("k9b")
    rc, out = s.sp(COORDCHAT, "--body", OWN_BODY + " · рука COORD")
    need(rc == 0 and s.latest()[1] == "seed", f"снимок {s.latest()}")
    need(s.mark() == 4422, f"чужой чат сдвинул отметку PROTO: #{s.mark()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "отметка #4422, снимок посева, окно пришло"


@case("K9c", "чат, бывший у PROTO (история), теперь записан за COORD: его запись тела снимок не двигает")
def k9c():
    s = build("k9c", pre=[(HIST_ROW, ("PROTO", HIST))],
              post=[("UPDATE role_sessions SET transcript_id = ? WHERE role = 'COORD'", (HIST,))])
    rc, out = s.sp(HIST, "--body", OWN_BODY + " · рука COORD через прежний чат PROTO")
    need(rc == 0 and s.latest()[1] == "seed", f"снимок {s.latest()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "снимок посева, окно пришло"


@case("K9d", "сохранение state из чата, записанного за двумя ролями: снимок не пишется, строка об этом есть")
def k9d():
    s = build("k9d", post=DUAL)
    rc, out = s.sp(NEW, "--body", OWN_BODY + " · из чата за двумя ролями")
    need(rc == 0 and s.latest() == (4418, "seed", None), f"код {rc}, снимок {s.latest()}")
    need("снимок отметки прочитанного не записан: номер чата" in out, out[-400:])
    return "снимок посева, строка о номере за двумя ролями"


HISTORY_ROW = ("INSERT INTO phoenix_history (id, role, section, body, body_chars, saved_at, actor, reason) "
               "VALUES (?, 'PROTO', 'state', ?, ?, '2026-10-01 07:00:00', 'PROTO', 'save')")


@case("K10", "возврат версии (--restore) не двигает снимок")
def k10():
    s = build("k10", post=[(HISTORY_ROW, (1, "прежняя версия state", 20))])
    rc, out = s.sp(OLD, "--restore", "1")
    need(rc == 0 and "не сдвинут" in out, out[-300:])
    need(s.latest()[1] == "seed", f"снимок {s.latest()}")
    need(s.mark() == 4422, f"возврат версии живым чатом сдвинул отметку: #{s.mark()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "снимок посева, окно пришло"


@case("K10b", "--restore версии, равной нынешнему тексту (ветка «тот же текст»), снимок не двигает")
def k10b():
    s = build("k10b", post=[(HISTORY_ROW, (2, OWN_BODY, len(OWN_BODY)))])
    rc, out = s.sp(OLD, "--restore", "2")
    need(rc == 0 and "СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ" in out and "не сдвинут" in out, out[-300:])
    need(s.latest()[1] == "seed", f"снимок {s.latest()}")
    need(s.mark() == 4422, f"возврат версии живым чатом сдвинул отметку: #{s.mark()}")
    return "ветка «тот же текст», снимок посева"


@case("K11a", "своя --confirm после чтения двигает снимок: новый чат получает пусто")
def k11a():
    s = build("k11a")
    s.sp(OLD, "--confirm")
    need(s.latest() == (4422, "confirm", OLD), f"снимок {s.latest()}")
    _, r = s.rm(NEW)
    need("Нет непрочитанных" in r, r[:300])
    return "снимок #4422"


@case("K11b", "своё пересохранение того же текста двигает снимок")
def k11b():
    s = build("k11b")
    s.sp(OLD, "--body", OWN_BODY)
    need(s.latest() == (4422, "same-body", OLD), f"снимок {s.latest()}")
    _, r = s.rm(NEW)
    need("Нет непрочитанных" in r, r[:300])
    return "снимок #4422"


@case("K12", "двойное пересоздание: чат Б отметил взгляд, прочёл, подтвердил; чат В получает окно снова")
def k12():
    s = build("k12")
    s.sp(NEW, "--confirm")
    _, r = s.rm(NEW)
    s.ack(NEW, r)
    need(s.mark() == 4422, f"после чата Б отметка {s.mark()}")
    _, r2 = s.rm(NEW2)
    need(returned(r2, 4422, 4418) and shown(r2) == WINDOW, f"чат В: {shown(r2)}")
    return "чат В получил #4419…#4422"


@case("K13", "записка окна в архиве: лента показывает остальные, строка называет архив и запрос")
def k13():
    s = build("k13", post=[
        "INSERT INTO messages_archive (id, writer_role, timestamp, body_md, moved_by, rule) "
        "SELECT id, writer_role, timestamp, body_md, 'messages-fold.py', 'приёмка' FROM messages WHERE id = 4420",
        "DELETE FROM messages WHERE id = 4420"])
    _, out = s.rm(NEW)
    need(shown(out) == [4419, 4421, 4422], f"показаны {shown(out)}")
    need("из окна уже в архиве: 1" in out and "messages_archive WHERE id > 4418 AND id <= 4422" in out, "нет строки архива")
    return "показаны #4419, #4421, #4422 и строка архива"


@case("K13b", "окна нет ни в ленте, ни в архиве: строка говорит это, «придут снова» не обещано")
def k13b():
    s = build("k13b", post=["DELETE FROM messages WHERE id BETWEEN 4419 AND 4422"])
    _, out = s.rm(NEW)
    need(returned(out, 4422, 4418) and out.count("ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА") == 1, out[:300])
    need("нет ни в ленте, ни в архиве" in out, "нет строки «нигде»")
    need("придут снова" not in out, "обещано «придут снова», а показывать нечего")
    need(shown(out) == [] and s.mark() == 4418, f"показаны {shown(out)}, отметка {s.mark()}")
    return "строка «нигде», обещания нет, отметка #4418"


@case("K13c", "всё окно в архиве: строка архива есть, «придут снова» не обещано")
def k13c():
    s = build("k13c", post=[
        "INSERT INTO messages_archive (id, writer_role, timestamp, body_md, moved_by, rule) "
        "SELECT id, writer_role, timestamp, body_md, 'messages-fold.py', 'приёмка' FROM messages "
        "WHERE id BETWEEN 4419 AND 4422",
        "DELETE FROM messages WHERE id BETWEEN 4419 AND 4422"])
    _, out = s.rm(NEW)
    need(returned(out, 4422, 4418), out[:300])
    need("из окна уже в архиве: 4" in out, "нет строки архива")
    need("придут снова" not in out and "нет ни в ленте, ни в архиве" not in out, out[:600])
    return "строка архива, обещания нет"


@case("K14a", "посев стенда B — снимок #4418 часом сохранения state")
def k14a():
    s = build("k14a")
    row = s.q("SELECT read_mark, how, at FROM phoenix_read_marks WHERE role='PROTO'")
    need(row == [(4418, "seed", H)], f"посев {row}")
    return "снимок #4418, 12:00"


@case("K14b", "одиночный отрезок «тело показано отбором --to-me» до часа памяти в посев не входит")
def k14b():
    seg = BASE_SEGMENTS + [(4421, 4421, "read", "тело показано отбором --to-me", "2026-10-01 11:30:00")]
    s = build("k14b", segments=seg)
    need(s.latest()[0] == 4418, f"посев {s.latest()}")
    _, out = s.rm(NEW)
    need(shown(out) == WINDOW, f"показаны {shown(out)}")
    return "посев #4418, пришли все четыре"


# История разделов до шага: своя запись тела state в 12:00 и ещё один ход в 13:30 — после чтения окна.
HIST_SAVE = ("INSERT INTO phoenix_history (role, section, body, body_chars, saved_at, actor, reason) "
             "VALUES ('PROTO', 'state', ?, ?, ?, ?, ?)")
OWN_AT_H = (HIST_SAVE, (OWN_BODY, len(OWN_BODY), H, "PROTO", "save"))
BODY_LATE = ("UPDATE phoenix SET saved_at = ? WHERE role = 'PROTO' AND section = 'state'", (LATE,))


def audit_save(actor):
    return ("INSERT INTO audit_log (timestamp, actor_role, action, target, diff_md) VALUES "
            "(?, ?, 'save_phoenix', 'phoenix.PROTO.state', 'Updated state (стенд)')", (LATE, actor))


def seed_then_read(s, expect):
    need(s.latest() == (expect, "seed", None), f"посев {s.latest()}")
    _, out = s.rm(NEW)
    return out


@case("K14c", "возврат версии (--restore) до шага, после чтения окна: посев по своей записи 12:00")
def k14c():
    s = build("k14c", pre=[OWN_AT_H, (HIST_SAVE, ("прежняя версия", 14, LATE, "PROTO", "restore 1")),
                           BODY_LATE, audit_save("PROTO")])
    out = seed_then_read(s, 4418)
    need(returned(out, 4422, 4418) and shown(out) == WINDOW, f"показаны {shown(out)}")
    return "посев #4418, окно пришло"


@case("K14d", "перенос в архив памяти до шага, после чтения окна: посев по своей записи 12:00")
def k14d():
    s = build("k14d", pre=[OWN_AT_H, (HIST_SAVE, ("горячее", 7, LATE, "PROTO", "archive-move: унесено 1 кусков, 9 знаков")),
                           BODY_LATE])
    out = seed_then_read(s, 4418)
    need(returned(out, 4422, 4418) and shown(out) == WINDOW, f"показаны {shown(out)}")
    return "посев #4418, окно пришло"


@case("K14e", "своя запись тела после чтения окна: посев #4422, новый чат получает пусто")
def k14e():
    s = build("k14e", pre=[OWN_AT_H, (HIST_SAVE, (OWN_BODY + " · позже", len(OWN_BODY) + 8, LATE, "PROTO", "save")),
                           BODY_LATE, audit_save("PROTO")])
    out = seed_then_read(s, 4422)
    need("Нет непрочитанных" in out and not returned(out, 4422, 4418), out[:300])
    return "посев #4422, возврата нет"


@case("K15","подтверждение в ту же секунду, что сохранение state: считается сделанным после")
def k15():
    seg = BASE_SEGMENTS[:2] + [(4419, 4422, "read", None, H)]
    s = build("k15", segments=seg)
    need(s.latest()[0] == 4418, f"посев {s.latest()}")
    return "посев #4418"


@case("K15b", "час посева — по своей руке: чужая запись тела и чужой взгляд позже его не сдвигают")
def k15b():
    s = build("k15b", pre=[
        "UPDATE phoenix SET saved_at = '2026-10-01 14:00:00', confirmed_at = '2026-10-01 14:30:00' "
        "WHERE role = 'PROTO' AND section = 'state'",
        "INSERT INTO audit_log (timestamp, actor_role, action, target, diff_md) VALUES "
        "('2026-10-01 14:00:00', 'COORD', 'save_phoenix', 'phoenix.PROTO.state', 'Updated state [чужая]')"])
    need(s.latest()[0] == 4418, f"посев {s.latest()}")
    return "посев #4418 (час своей записи 12:00)"


@case("K15c", "чужая запись тела в истории после чтения окна посев не сдвигает")
def k15c():
    s = build("k15c", pre=[OWN_AT_H, (HIST_SAVE, (OWN_BODY + " · рука COORD", len(OWN_BODY) + 12, LATE, "COORD", "save")),
                           BODY_LATE, audit_save("COORD")])
    out = seed_then_read(s, 4418)
    need(returned(out, 4422, 4418) and shown(out) == WINDOW, f"показаны {shown(out)}")
    return "посев #4418, окно пришло"


@case("K16", "неподтверждённая выдача прежнего чата: новый чат получает окно НОВЫМ ключом, прежняя гаснет")
def k16():
    s = build("k16", post=[OPEN_BATCH])
    _, out = s.rm(NEW)
    h1, _ = halves(out)
    need(shown(out) == WINDOW and h1 and h1 != TOKEN.split("-")[0], f"ключ {h1}, показаны {shown(out)}")
    need(s.q("SELECT acked_at IS NOT NULL FROM read_batches WHERE token=?", (TOKEN,)) == [(1,)], "старая выдача не погашена")
    need(s.q("SELECT cursor_before, cursor_after FROM read_batch_voids WHERE token=?", (TOKEN,)) == [(4422, 4418)], "нет строки гашения")
    _, again = s.rm(NEW)
    need(halves(again)[0] == h1 and "↩" not in again, "перевыдача R16 нового чата дала другой ключ")
    rc, _ = s.ack(NEW, again)
    need(rc == 0 and s.mark() == 4422, f"подтверждение: код {rc}, отметка {s.mark()}")
    return "новый ключ, старая выдача погашена, R16 у нового чата цела"


@case("K16b", "прежний чат подтверждает погашенный ключ: отказ с командой; новое чтение даёт новый ключ")
def k16b():
    s = build("k16b", post=[OPEN_BATCH])
    s.rm(NEW)
    rc, out = s.rm(OLD, "--ack", TOKEN)
    need(rc == 1 and "погашен" in out and "read-messages.py --role PROTO" in out, out[:400])
    need(s.mark() == 4418, f"отметка {s.mark()}")
    _, r = s.rm(OLD)
    h1, _ = halves(r)
    need(h1 and h1 != TOKEN.split("-")[0] and shown(r) == WINDOW, f"ключ {h1}")
    rc, _ = s.ack(OLD, r)
    need(rc == 0 and s.mark() == 4422, f"подтверждение: код {rc}")
    return "отказ с командой, затем новый ключ и подтверждение — запирания нет"


@case("K49", "после двух возвратов ключ третьего чата подтверждается")
def k49():
    s = build("k49")
    for chat in (NEW, NEW2, NEW3):
        _, out = s.rm(chat)
        need(returned(out, 4422, 4418), f"чат {chat[:2]}: возврата нет")
        rc, _ = s.ack(chat, out)
        need(rc == 0 and s.mark() == 4422, f"чат {chat[:2]}: код {rc}, отметка {s.mark()}")
    return "три чата подряд: возврат и подтверждение каждый раз"


@case("K50", "новый чат коснулся только --confirm; прежний подтверждает старый ключ — отказ, окно цело")
def k50():
    s = build("k50", post=[OPEN_BATCH])
    s.sp(NEW, "--confirm")
    rc, out = s.rm(OLD, "--ack", TOKEN)
    need(rc == 1 and s.mark() == 4418, f"код {rc}, отметка {s.mark()}")
    _, r = s.rm(NEW)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    return "отказ прежнему, окно у нового"


@case("KS", "незаписанная сессия коснулась указателем: живой чат роли перечитывает окно, запирания нет")
def ks():
    s = build("ks", post=[OPEN_BATCH])
    _, idx = s.rm(STRAY, "--index")
    need(idx.splitlines()[0].startswith("↩ ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА"), idx[:200])
    rc, out = s.rm(OLD, "--ack", TOKEN)
    need(rc == 1 and "погашен" in out and "read-messages.py --role PROTO" in out, out[:300])
    _, r = s.rm(OLD)
    need(shown(r) == WINDOW, f"показаны {shown(r)}")
    rc, _ = s.ack(OLD, r)
    _, last = s.rm(OLD)
    need(rc == 0 and "Нет непрочитанных" in last, last[:200])
    return "одно перечитывание окна, затем лента дочитана"


@case("K17", "прогноз в новом чате: «вернётся #4422 → #4418», база не меняется; в прежнем чате молчит")
def k17():
    s = build("k17")
    _, p = s.rp(NEW)
    need("вернётся #4422 → #4418" in p, "прогноза нет")
    need(s.mark() == 4422 and not s.q("SELECT 1 FROM chat_seen WHERE chat_id=?", (NEW,)), "база изменилась")
    _, p2 = s.rp(OLD)
    need("вернётся" not in p2, "в прежнем чате прогноз есть")
    return "прогноз есть, база цела, в прежнем чате строки нет"


@case("K17b", "прогноз для чужого чата молчит")
def k17b():
    s = build("k17b")
    _, p = s.rp(COORDCHAT)
    need("вернётся" not in p, "прогноз для чата COORD")
    return "строки нет"


@case("K18", "шаг схемы не сведён: чтение и сохранение работают, прогноз говорит об этом")
def k18():
    s = build("k18", step=False)
    rc1, r = s.rm(NEW)
    rc2, w = s.sp(NEW, "--body", OWN_BODY + " · без шага")
    need(rc1 == 0 and "Нет непрочитанных" in r, r[:200])
    need(rc2 == 0 and "OK phoenix/PROTO/state" in w, w[-300:])
    _, p = s.rp(NEW)
    need("не сведён" in p, "прогноз молчит о шаге")
    return "чтение и запись — код 0, прогноз называет шаг"


@case("K19", "шаг схемы повторно: «уже сведено», запись шага одна")
def k19():
    s = build("k19")
    out = s.apply_step()
    need("уже сведено" in out, out[-200:])
    need(s.q("SELECT COUNT(*) FROM schema_migrations WHERE version=?", (STEP,))[0][0] == 1, "записей шага ≠ 1")
    return "«уже сведено», одна запись"


@case("K20", "первый вызов — обзор --wake: возврат в первой половине, указатель показывает окно")
def k20():
    s = build("k20")
    _, out = s.rm(NEW, "--wake")
    i_ret = out.find("ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА")
    i_idx = out.find("УКАЗАТЕЛЬ ПО ВСЕМУ ОСТАЛЬНОМУ ДОЛГУ")
    need(0 <= i_ret < i_idx, f"возврат {i_ret}, указатель {i_idx}")
    tail = out[i_idx:]
    need(all(f"#{i} " in tail for i in WINDOW) and s.mark() == 4418, "в указателе нет окна")
    # находка противника 31.10, M2: под строкой возврата указатель не пишет «НЕ сдвинута»
    need("её вернула строка возврата выше" in out and "отметка прочитанного НЕ сдвинута" not in out,
         "строка указателя спорит с возвратом")
    need("назад её" in out and "Отметка прочитанного НЕ двинута" not in out, "подвал обзора спорит с возвратом")
    return "возврат в первой половине, в указателе #4419…#4422"


@case("K21", "живой чат роли, записанный при установке, новым не считается")
def k21():
    s = build("k21")
    _, out = s.rm(OLD)
    need("Нет непрочитанных" in out and returns(s) == 0, out[:200])
    return "возврата нет"


HIST_ROW = ("INSERT INTO role_sessions_history (role, address, noted_by, source, transcript_id) "
            "VALUES (?, 'стенд [история]', 'стенд', 'self', ?)")


@case("K21b", "чат роли из истории реестра, записанный при установке, новым не считается")
def k21b():
    s = build("k21b", pre=[(HIST_ROW, ("PROTO", HIST))])
    _, out = s.rm(HIST)
    need("Нет непрочитанных" in out and returns(s) == 0, out[:200])
    return "возврата нет"


@case("D2a", "чат, переведённый к роли после установки (в истории — за COORD), свой: окно и снимок")
def d2a():
    s = build("d2a", pre=[(HIST_ROW, ("COORD", MOVED))],
              post=[("UPDATE role_sessions SET transcript_id = ? WHERE role = 'PROTO'", (MOVED,))])
    _, out = s.rm(MOVED)
    need(returned(out, 4422, 4418) and shown(out) == WINDOW, f"показаны {shown(out)}")
    s.ack(MOVED, out)
    s.sp(MOVED, "--body", OWN_BODY + " · переведённый чат")
    need(s.latest() == (4422, "save", MOVED), f"снимок {s.latest()}")
    return "окно пришло, снимок записан"


@case("D2b", "чат только в истории реестра за COORD — для PROTO чужой")
def d2b():
    s = build("d2b", pre=[(HIST_ROW, ("COORD", HISTC))])
    s.rm(HISTC)
    need(s.mark() == 4422 and returns(s) == 0, f"отметка {s.mark()}")
    return "отметка #4422"


@case("D1", "сбой проверки нового чата в save-phoenix: снимок не пишется, окно не теряется")
def d1():
    s = build("d1", post=["CREATE TRIGGER bite_fail BEFORE INSERT ON chat_seen "
                          "BEGIN SELECT RAISE(ABORT, 'нарочный сбой приёмки'); END"])
    rc, out = s.sp(NEW, "--body", OWN_BODY + " · сбой проверки")
    need(rc == 0 and "OK phoenix/PROTO/state" in out and "НЕ записан" in out, out[-400:])
    need(s.latest()[1] == "seed", f"снимок {s.latest()}")
    s.x("DROP TRIGGER bite_fail")
    _, r = s.rm(NEW)
    need(returned(r, 4422, 4418) and shown(r) == WINDOW, f"показаны {shown(r)}")
    return "сохранение прошло без снимка, окно пришло позже"


@case("F5", "роль без снимка: строка chat_seen пишется, первое сохранение state заводит снимок")
def f5():
    s = build("f5")
    _, out = s.rm(NEW, role="SEPA")
    need("снимка отметки прочитанного ещё нет" in out, out[:300])
    need(s.q("SELECT 1 FROM chat_seen WHERE role='SEPA' AND chat_id=?", (NEW,)), "строки chat_seen нет")
    s.sp(NEW, "--body", "память SEPA", role="SEPA")
    need(s.latest("SEPA") == (4422, "save", NEW), f"снимок {s.latest('SEPA')}")
    return "строка chat_seen есть, снимок заведён"


@case("F6", "роль без отметки прочитанного сохраняет state: ни снимка, ни неисполнимого совета")
def f6():
    s = build("f6")
    rc, out = s.sp(ZCHAT, "--body", "память ZETA: стенд", role="ZETA")
    need(rc == 0, f"код {rc}: {out[-300:]}")
    need("НЕ записан" not in out and "read-messages.py --role ZETA" not in out, out[-400:])
    need(s.latest("ZETA") is None, f"снимок {s.latest('ZETA')}")
    return "сохранение прошло, строки о снимке нет"


@case("KA", "возврат записан в журнал")
def ka():
    s = build("ka")
    s.rm(NEW)
    rows = s.q("SELECT diff_md FROM audit_log WHERE action='read_mark_return'")
    need(len(rows) == 1 and "#4422 → #4418" in rows[0][0], f"журнал {rows}")
    return "одна запись «#4422 → #4418»"


@case("KB", "большое окно: строка «начни с обзора --wake»")
def kb():
    seg = BASE_SEGMENTS[:2] + [(4419, 4482, "read", None, AFTER)]
    s = build("kb", mark=4482, top=4482, segments=seg)
    _, out = s.rm(NEW, "--index")
    need("окно большое" in out and "--wake" in out, out[:400])
    return "строка есть"


@case("KC", "выдача без ключа (--to-me): строка возврата первой")
def kc():
    s = build("kc")
    _, out = s.rm(NEW, "--to-me")
    need(out.splitlines()[0].startswith("↩ ОТМЕТКА ПРОЧИТАННОГО ВОЗВРАЩЕНА"), out[:200])
    return "первая строка — возврат"


@case("KE", "mezo_stand.stand_env не передаёт номер чата стенду")
def ke():
    saved = os.environ.get(CHAT_ENV)
    os.environ[CHAT_ENV] = STRAY
    try:
        fn = mezo_stand.stand_env
        if BREAK == "stand-env-leak":
            def fn(container, **extra):
                return dict(os.environ, MEZO_CONTAINER=str(container), **extra)
        env = fn(Path("."))
    finally:
        if saved is None:
            os.environ.pop(CHAT_ENV, None)
        else:
            os.environ[CHAT_ENV] = saved
    need(CHAT_ENV not in env, "номер чата вызывающего уехал в среду стенда")
    return "номера в среде стенда нет"


# ── ПРОГОН ─────────────────────────────────────────────────────────────────────────────────
def main():
    global BREAK
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--break", dest="brk", default=None, metavar="ИМЯ")
    ap.add_argument("--list-breaks", action="store_true")
    args = ap.parse_args()
    if args.list_breaks:
        for name, (why, _, want, *maybe) in BREAKS.items():
            extra = f" · может ещё: {', '.join(sorted(maybe[0]))}" if maybe else ""
            print(f"{name:<22} {why} → {', '.join(sorted(want))}{extra}")
        return 0
    if args.brk and args.brk not in BREAKS:
        print(f"⛔ нет такой поломки: {args.brk} (перечень — --list-breaks)")
        return 2
    BREAK = args.brk
    print(f"испытан: {mezo_target.label()}" + (f" · ПОЛОМКА {BREAK}: {BREAKS[BREAK][0]}" if BREAK else ""))
    failed, unset, skipped = [], [], []
    for cid, title, fn in CASES:
        if time.monotonic() - STARTED > BUDGET_S:
            skipped.append(cid)
            continue
        try:
            detail = fn()
            print(f"✅ {cid} {title}\n   {detail}")
        except AssertionError as e:
            failed.append(cid)
            print(f"🔴 {cid} {title}\n   {e}")
        except NotSet as e:
            unset.append(cid)
            print(f"⛔ {cid} {title}\n   опыт не поставлен: {e}")
        except Exception as e:  # noqa: BLE001
            failed.append(cid)
            print(f"🔴 {cid} {title}\n   сбой: {type(e).__name__}: {e}")
    total = len(CASES)
    spent = time.monotonic() - STARTED
    print(f"\nИТОГ: прошло {total - len(failed) - len(unset) - len(skipped)} из {total} · провал "
          f"{len(failed)} · не поставлено {len(unset)} · не запустилось по бюджету {len(skipped)} · "
          f"{spent:.0f} с")
    if skipped:
        print(f"⛔ БЮДЖЕТ {BUDGET_S} с ИСЧЕРПАН: не запустились {', '.join(skipped)} — это НЕ «прошли»")
        return 2
    if unset:
        return 2
    if BREAK:
        want = BREAKS[BREAK][2]
        maybe = BREAKS[BREAK][3] if len(BREAKS[BREAK]) > 3 else set()
        got = set(failed)
        if want <= got <= want | maybe:
            extra = (f" (из названных заранее «может ещё»: {', '.join(sorted(got & maybe))})"
                     if got & maybe else "")
            print(f"✅ ПОЛОМКА ПОЙМАНА РОВНО СВОИМИ СЛУЧАЯМИ: {', '.join(sorted(got))}{extra}")
            mezo_stand.expected_break()
        else:
            print(f"🔴 ПОЛОМКА ПОЙМАНА НЕ ТЕМИ СЛУЧАЯМИ: ждали {sorted(want)}"
                  + (f" (может ещё {sorted(maybe)})" if maybe else "")
                  + f", провалились {sorted(got)} · не поймано {sorted(want - got)} · "
                    f"лишние {sorted(got - want - maybe)}")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
