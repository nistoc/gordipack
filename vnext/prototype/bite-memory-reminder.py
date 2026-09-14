#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА НАПОМИНАНИЯ «ПАМЯТЬ РОЛИ НЕ ПОДТВЕРЖДАЛАСЬ N ч» — оно говорит ПРАВДУ и его совет ИСПОЛНИМ.

Заказ PROTO, записка #5189 ① (по разбору OPSSRE, записка #5188; слово владельца OPSSRE 14.09 10:00 UTC —
обсудить механизм против долгого несохранения памяти).

Предмет. 14.09 роль OPSSRE трижды получила это напоминание при записке и трижды отложила запись памяти:
считала, что раздел упёрся в порог объёма и сперва надо резать или уносить в архив. Порог запись
НЕ останавливает (карточка #478) — та же ложная причина у ING 31.08 и RCC. Совет в напоминании об этом
молчал и вёл только к полной перезаписи раздела; короткий честный путь «правок нет» (--confirm,
карточка #160) не назывался вовсе.

Случаи (различающий = прежняя редакция отвечает ИНАЧЕ):
  ① память старше 3 ч → напоминание звучит                                  контроль
  ② в напоминании правда о пороге: запись он НЕ останавливает                РАЗЛИЧАЮЩИЙ
  ③ назван путь «правок нет»: save-phoenix.py рядом с испытуемым, файл есть  РАЗЛИЧАЮЩИЙ
  ④ совет ИСПОЛНИМ как напечатан: несёт --db песочницы (иначе метил бы       РАЗЛИЧАЮЩИЙ
     в память рядом со скриптом — у живого это ЖИВАЯ память), отметка
     ставится, и следующая записка уже без напоминания
  ⑤ числа порога в напоминании нет: оно живёт в guard-phoenix-volume.py      контроль
  ⑥ память свежа → напоминание молчит                                        контроль

⛔ Живой базы не касается: своя песочница; напечатанную команду БЕЗ --db песочницы приёмка не исполняет.
"""
import os
import re
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

WRITE = mezo_target.script("write-message.py")
SAVE = WRITE.parent / "save-phoenix.py"
ROLE = "PROTO"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build(hours_ago):
    d = mezo_stand.new("bite-reminder-")
    db = d / "s.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
            priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
            addressed_by TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
        CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
            confirmed_at TEXT, PRIMARY KEY (role, section));
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor_role TEXT, action TEXT,
            target TEXT, diff_md TEXT);
        CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
            linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
        CREATE TABLE roles (role TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
    """)
    con.execute("INSERT INTO read_cursors VALUES (?, 0)", (ROLE,))
    con.execute("INSERT INTO roles VALUES (?, 'active')", (ROLE,))
    stamp = f"-{hours_ago} hours"
    con.execute("INSERT INTO phoenix VALUES (?, 'state', 'СОСТОЯНИЕ РОЛИ, записанное давно.',"
                " datetime('now', ?), datetime('now', ?))", (ROLE, stamp, stamp))
    con.commit()
    con.close()
    return d, db


def write(d, db, body):
    f = d / "note.md"
    f.write_text(body, encoding="utf-8")
    r = subprocess.run([sys.executable, str(WRITE), "--db", str(db), "--role", ROLE, "--file", str(f)],
                       capture_output=True, text=True, encoding="utf-8", cwd=d,
                       env=mezo_stand.stand_env(d))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def reminder_block(out):
    """Строки напоминания: от «⏳ ПАМЯТЬ РОЛИ» до конца вывода."""
    lines = out.splitlines()
    start = next((i for i, l in enumerate(lines) if "НЕ ПОДТВЕРЖДАЛАСЬ" in l), None)
    return lines[start:] if start is not None else []


def main() -> int:
    if not WRITE.exists():
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    ok = True
    d, db = build(hours_ago=5)
    out, code = write(d, db, "записка при памяти, записанной пять часов назад")
    block = reminder_block(out)
    ok &= case("① память старше 3 ч → напоминание звучит (контроль)",
               code == 0 and bool(block), f"код {code} · строк напоминания {len(block)}")

    truth = [l for l in block if "НЕ останавливает" in l and "Порог" in l]
    ok &= case("② в напоминании правда о пороге: запись он НЕ останавливает",
               bool(truth), truth[0].strip() if truth else "строки о пороге нет", differ=True)

    cmd_line = next((l.strip() for l in block if "--confirm" in l and "save-phoenix.py" in l), "")
    tokens = shlex.split(cmd_line) if cmd_line else []
    named = next((Path(t) for t in tokens if t.endswith("save-phoenix.py")), None)
    same = named is not None and named.is_absolute() and named.exists() \
        and named.resolve() == SAVE.resolve()
    ok &= case("③ назван путь «правок нет»: save-phoenix.py рядом с испытуемым, файл есть",
               same, f"в совете: {named} · ждали: {SAVE}", differ=True)

    has_db = False
    if "--db" in tokens:
        i = tokens.index("--db")
        has_db = i + 1 < len(tokens) and Path(tokens[i + 1]).resolve() == db.resolve()
    confirmed = silent_after = False
    detail = "команды в совете нет" if not tokens else "в совете нет --db песочницы — НЕ исполняю"
    if tokens and has_db:
        run_tokens = [sys.executable if t == "python" else t.replace("<раздел>", "state") for t in tokens]
        r = subprocess.run(run_tokens, capture_output=True, text=True, encoding="utf-8", cwd=d,
                           env=mezo_stand.stand_env(d))
        confirmed = r.returncode == 0 and "ВЗГЛЯД ОТМЕЧЕН" in (r.stdout or "")
        out2, _ = write(d, db, "записка сразу после отметки взгляда")
        silent_after = "НЕ ПОДТВЕРЖДАЛАСЬ" not in out2
        detail = (f"команда как напечатана: код {r.returncode} · отметка поставлена: {confirmed} · "
                  f"следующая записка без напоминания: {silent_after}")
    ok &= case("④ совет ИСПОЛНИМ как напечатан: --db песочницы · отметка встала · напоминание стихло",
               has_db and confirmed and silent_after, detail, differ=True)

    numbers = [l.strip() for l in block if re.search(r"\b20[\s ]?000\b", l)]
    ok &= case("⑤ числа порога в напоминании нет — оно живёт в одном месте (контроль)",
               not numbers, numbers[0] if numbers else "число не повторено")

    d2, db2 = build(hours_ago=1)
    out3, _ = write(d2, db2, "записка при свежей памяти")
    ok &= case("⑥ память свежа → напоминание молчит (контроль)",
               "НЕ ПОДТВЕРЖДАЛАСЬ" not in out3, "признак, который горит всегда, перестаёт значить что-либо")

    print()
    print(f"{'✅ НАПОМИНАНИЕ ГОВОРИТ ПРАВДУ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
