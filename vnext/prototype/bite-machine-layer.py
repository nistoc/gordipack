#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА машинного слоя памяти роли (модуль machine_layer в живых скриптах).

Испытывается ЖИВОЙ модуль, не копия: копия проверяет копию, а за разницу между
«сдано у автора» и «доступно потребителю» контур уже платил.

Случаи (различающий = механизм обязан промолчать или ответить ИНАЧЕ):
  ① долг ленты назван ЧИСЛОМ и совпадает с подложенным     (контроль: блок не молчит)
  ② обращение ЛИЧНО отличается от списка «в копию»          РАЗЛИЧАЮЩИЙ
  ③ своя записка новее слепка — блок ТРЕБУЕТ читать её первой  РАЗЛИЧАЮЩИЙ
  ④ своя записка СТАРШЕ слепка — предупреждения НЕТ         РАЗЛИЧАЮЩИЙ
  ⑤ правила, правленные после слепка, названы поимённо      РАЗЛИЧАЮЩИЙ
  ⑥ у роли нет отметки чтения — сказано вслух, а не пропущено РАЗЛИЧАЮЩИЙ
  ⑦ база недоступна — блок ГОВОРИТ об этом, а не возвращает пустоту РАЗЛИЧАЮЩИЙ
  ⑧ граница («знает базу, не диск») печатается ВСЕГДА

⛔ Живой базы не касается: своя песочница.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

SCRIPTS = r"C:\guts\.atlas\.mezosync\scripts"


def load_live():
    path = os.path.join(SCRIPTS, "machine_layer.py")
    if not os.path.exists(path):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {path} не найден — приёмке нечего испытывать.")
    spec = importlib.util.spec_from_file_location("machine_layer_live", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(msgs, cursor=None, phoenix=(), rules=()):
    path = os.path.join(tempfile.mkdtemp(prefix="bite-machine-"), "s.db")
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT,
                   timestamp TEXT, body_md TEXT, tags TEXT, priority TEXT)""")
    con.execute("CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER)")
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    con.execute("""CREATE TABLE rules (rule_key TEXT PRIMARY KEY, body TEXT, locked_by TEXT,
                   version INTEGER, updated_at TEXT)""")
    for mid, role, ts, body in msgs:
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md) VALUES (?,?,?,?)",
                    (mid, role, ts, body))
    if cursor is not None:
        con.execute("INSERT INTO read_cursors VALUES ('PROTO', ?)", (cursor,))
    for sec, at in phoenix:
        con.execute("INSERT INTO phoenix VALUES ('PROTO', ?, 'тело', ?)", (sec, at))
    for k, v, at in rules:
        con.execute("INSERT INTO rules VALUES (?, 'текст', 'owner', ?, ?)", (k, v, at))
    con.commit()
    con.close()
    return path


CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def main() -> int:
    m = load_live()
    ok = True
    SNAP = "2026-08-08 09:00:00"

    # Базовая песочница: 4 записки после отметки, из них ОДНА с личным обращением,
    # ещё одна называет роль ТОЛЬКО в списке «в копию».
    msgs = [
        (100, "PROTO", "2026-08-08 08:00:00", "моя старая записка"),
        (101, "CORE", "2026-08-08 10:00:00", "@PROTO — вопрос лично тебе\nтекст"),
        (102, "STUD", "2026-08-08 10:05:00", "✅ @CORE — ответ. cc @TAXO @PROTO @ING"),
        (103, "TAXO", "2026-08-08 10:10:00", "разговор без имён"),
        (104, "ING", "2026-08-08 10:15:00", "ещё записка"),
    ]
    db = build(msgs, cursor=100, phoenix=[("state", SNAP), ("plan", SNAP)],
               rules=[("свежее-правило", 3, "2026-08-08 09:30:00"),
                      ("старое-правило", 1, "2026-08-01 09:00:00")])
    text = "\n".join(m.machine_block(db, "PROTO"))

    ok &= case("① долг ленты назван числом и совпадает с подложенным",
               "долг 4 записок" in text, f"подложено 4 записки после отметки → {text[:0]}"
               + [l for l in text.splitlines() if "ЛЕНТА" in l][0])

    ok &= case("② обращение ЛИЧНО отделено от списка «в копию»",
               "ЛИЧНО (не «в копию»): 1" in text,
               "подложено: одно обращение в шапке + одно упоминание только в копии → "
               "засчитано обязано быть ОДНО", differ=True)

    ok &= case("③ своя записка новее слепка — блок требует читать её первой",
               "ОНА НОВЕЕ СЛЕПКА" not in text,
               "своя записка (08:00) СТАРШЕ слепка (09:00) ⇒ предупреждения быть НЕ должно",
               differ=True)

    # ④ теперь своя записка НОВЕЕ слепка — предупреждение обязано появиться
    msgs2 = msgs + [(105, "PROTO", "2026-08-08 10:30:00", "моя свежая записка")]
    db2 = build(msgs2, cursor=100, phoenix=[("state", SNAP)],
                rules=[("свежее-правило", 3, "2026-08-08 09:30:00")])
    text2 = "\n".join(m.machine_block(db2, "PROTO"))
    ok &= case("④ своя записка НОВЕЕ слепка — предупреждение появляется",
               "ОНА НОВЕЕ СЛЕПКА" in text2 and "#105" in text2,
               "тот же блок на сдвинутых данных отвечает ИНАЧЕ — значит различает, "
               "а не печатает всегда одно", differ=True)

    ok &= case("⑤ правила после слепка названы поимённо, старое НЕ попало",
               "свежее-правило v3" in text and "старое-правило" not in text,
               "подложено два правила, одно правлено ПОСЛЕ слепка → назваться обязано одно",
               differ=True)

    db3 = build(msgs, cursor=None, phoenix=[("state", SNAP)])
    text3 = "\n".join(m.machine_block(db3, "PROTO"))
    ok &= case("⑥ отметки чтения нет — сказано вслух, а не пропущено молча",
               "отметки чтения у роли НЕТ" in text3,
               "отсутствие курсора обязано быть НАЗВАНО: молчание тут читается как «всё в порядке»",
               differ=True)

    text4 = "\n".join(m.machine_block(os.path.join(tempfile.mkdtemp(), "нет-такой.db"), "PROTO"))
    ok &= case("⑦ база недоступна — блок ГОВОРИТ об этом, а не возвращает пустоту",
               "НЕ СОБРАН" in text4 and "НЕ «всё в порядке»" in text4,
               "третий исход отдельно: «не собрано» слитое с «чисто» и есть ложный ноль",
               differ=True)

    ok &= case("⑧ граница «знает базу, не диск» печатается всегда",
               "не ДИСК" in text and "не ДИСК" in text2 and "не ДИСК" in text3,
               "во всех прогонах блок сам называет, чего он НЕ проверял")

    print()
    print(f"{'✅ МАШИННЫЙ СЛОЙ ПРИНЯТ' if ok else '🔴 МАШИННЫЙ СЛОЙ НЕ ПРИНЯТ'} — "
          f"случаев {CASES}, различающих {DIFFER}, испытан ЖИВОЙ модуль")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
