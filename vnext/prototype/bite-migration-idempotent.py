# -*- coding: utf-8 -*-
"""ПРИЁМКА: шаг схемы 20260807-addressed-by-unset ИДЕМПОТЕНТЕН.

Повод — находка @PROTO (#3463, 2026-08-09): повторный прогон падал «table messages already
exists», нарушая правило migration-safety, которое я же и обосновывал накануне.

⚠️ ЧТО ЗДЕСЬ ГЛАВНОЕ И ПОЧЕМУ ПРОВЕРКА ИМЕННО ТАКАЯ.
Дефект был НЕВИДИМ по построению: первый прогон делал схему непохожей на ту, которую ждал
второй (SQLite после RENAME хранит имя в кавычках). ⇒ Проверять надо не «шаг отработал»,
а «шаг отработал ДВАЖДЫ по одной базе». Один прогон здесь зелен всегда — и ничего не значит.

Испытуемая база СТРОИТСЯ ЗАНОВО со СТАРОЙ схемой, а не берётся снимком: снимок стареет молча
и через две недели испытывает условия, которых больше нет (класс @PROTO того же дня).
Живая база не открывается вовсе — путь передаётся шагу аргументом.
"""
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

STEP = pathlib.Path(r"C:\guts\.atlas\.mezosync\scripts\migrations\20260807-addressed-by-unset.py")

OLD_SCHEMA = """
CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  writer_role TEXT NOT NULL,
  body TEXT NOT NULL,
  ts TEXT,
  addressed_by TEXT NOT NULL DEFAULT 'backfill' CHECK (addressed_by IN ('field','backfill'))
);
CREATE INDEX ix_messages_writer ON messages(writer_role);
CREATE VIEW messages_all AS SELECT id, writer_role, body, ts, addressed_by FROM messages;
INSERT INTO messages (id, writer_role, body, ts, addressed_by) VALUES
  (1,'COORD','раз','2026-08-07 10:00:00','field'),
  (2,'PROTO','два','2026-08-07 10:01:00','backfill'),
  (3,'CORE','три','2026-08-07 10:02:00','backfill');
"""

cases, failed = [], 0


def check(name, ok, detail=""):
    global failed
    cases.append((name, ok, detail))
    if not ok:
        failed += 1


def build(path):
    c = sqlite3.connect(path)
    c.executescript(OLD_SCHEMA)
    c.commit()
    c.close()


def run(path):
    return subprocess.run([sys.executable, str(STEP), str(path)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def schema_of(path, name="messages"):
    c = sqlite3.connect(path)
    sql = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
    c.close()
    return sql[0] if sql else ""


tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-idem-"))
db = tmp / "probe.db"
build(db)

# ① ПЕРВЫЙ ПРОГОН — рабочая ветка
r1 = run(db)
check("① первый прогон завершился без падения", r1.returncode == 0,
      (r1.stderr or "").strip()[-200:])
check("① умолчание переехало на 'unset'", "'unset'" in schema_of(db),
      schema_of(db)[:120])
check("① строки на месте (3)",
      sqlite3.connect(db).execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 3)
check("① VIEW messages_all жив",
      sqlite3.connect(db).execute("SELECT COUNT(*) FROM messages_all").fetchone()[0] == 3)
check("① индекс восстановлен", bool(schema_of(db, "ix_messages_writer")))

# ② ВТОРОЙ ПРОГОН ПО ТОЙ ЖЕ БАЗЕ — ради него всё и написано
r2 = run(db)
check("② повторный прогон НЕ упал (это и есть идемпотентность)", r2.returncode == 0,
      (r2.stderr or "").strip()[-200:])
check("② повторный сказал «уже применено», а не сделал работу молча",
      "уже применено" in (r2.stdout or ""), (r2.stdout or "").strip()[:120])
check("② данные после второго прогона целы (3 строки)",
      sqlite3.connect(db).execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 3)

# ③ РАЗЛИЧАЮЩИЙ СЛУЧАЙ — тот, на котором v1 и падала: имя таблицы в КАВЫЧКАХ.
# Без него приёмка зеленела бы, не проверив причину дефекта, а только его следствие.
db2 = tmp / "quoted.db"
build(db2)
c = sqlite3.connect(db2)
c.executescript("""BEGIN;
ALTER TABLE messages RENAME TO messages_tmp;
ALTER TABLE messages_tmp RENAME TO messages;
COMMIT;""")
c.close()
check("③ подготовка: схема действительно хранит имя В КАВЫЧКАХ",
      '"messages"' in schema_of(db2), schema_of(db2)[:80])
r3 = run(db2)
check("③ шаг справляется с именем в кавычках", r3.returncode == 0,
      (r3.stderr or "").strip()[-200:])
check("③ и умолчание всё равно переехало", "'unset'" in schema_of(db2))

# ④ ГРОМКИЙ ОТКАЗ вместо тихой порчи, если схема ВООБЩЕ не та
db3 = tmp / "alien.db"
c = sqlite3.connect(db3)
c.executescript("CREATE TABLE messages (id INTEGER PRIMARY KEY, x TEXT);"
                "CREATE VIEW messages_all AS SELECT id FROM messages;")
c.commit()
c.close()
r4 = run(db3)
check("④ на чужой схеме шаг ПАДАЕТ ГРОМКО, а не портит молча", r4.returncode != 0,
      f"код {r4.returncode}")

print("🔬 ПРИЁМКА ИДЕМПОТЕНТНОСТИ ШАГА 20260807-addressed-by-unset")
print(f"   испытана СВЕЖЕПОСТРОЕННАЯ база: {tmp} (живая не открывалась)")
for name, ok, detail in cases:
    print(f"   {'✅' if ok else '🔴'} {name}" + (f"   ← {detail}" if detail and not ok else ""))
print(f"   ИТОГ: {len(cases) - failed}/{len(cases)}")
sys.exit(1 if failed else 0)
