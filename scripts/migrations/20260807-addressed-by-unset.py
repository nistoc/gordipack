"""Шаг ① плана @PROTO: умолчание addressed_by 'backfill' → 'unset'.

Слово владельца: 2026-08-07 10:13 UTC, чат COORD — «разрешаю обработать запрос от proto».
Точка отката: scratchpad/pre-shown-field.db (12.6 МБ, integrity ok, снята 10:13 UTC).
Прогон на копии (try-unset.db) прошёл: 1724/1724 строк, VIEW жив, все три различающих
случая @PROTO (#3141) зелёные.

SQLite не умеет ALTER для DEFAULT и CHECK — таблица пересоздаётся. Порядок важен:
VIEW messages_all дропается ДО таблицы и восстанавливается ПОСЛЕ, иначе он повиснет
на несуществующей таблице. Индексы снимаются заранее и накатываются обратно.
"""
import sqlite3

DB = 'C:/guts/.atlas/.mezosync/mezosync.db'
c = sqlite3.connect(DB, timeout=15)
c.execute("PRAGMA foreign_keys=OFF")

old_sql = c.execute("SELECT sql FROM sqlite_master WHERE name='messages'").fetchone()[0]
view_sql = c.execute("SELECT sql FROM sqlite_master WHERE name='messages_all'").fetchone()[0]
idx = [r[0] for r in c.execute(
    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='messages' AND sql IS NOT NULL")]

new_sql = (old_sql
           .replace("CREATE TABLE messages", "CREATE TABLE messages_new", 1)
           .replace("DEFAULT 'backfill' CHECK (addressed_by IN ('field','backfill'))",
                    "DEFAULT 'unset' CHECK (addressed_by IN ('field','backfill','unset'))"))
# Страховка: если строка умолчания в схеме окажется другой, замена молча не сработает —
# и мы пересоздадим таблицу БЕЗ правки, потратив риск впустую. Падаем громко.
assert "'unset'" in new_sql, "замена умолчания не сработала — схема отличается от ожидаемой"

cols = [r[1] for r in c.execute("PRAGMA table_info(messages)")]
collist = ", ".join(cols)
before = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
before_field = c.execute("SELECT COUNT(*) FROM messages WHERE addressed_by='field'").fetchone()[0]

c.executescript(f"""BEGIN;
{new_sql};
INSERT INTO messages_new ({collist}) SELECT {collist} FROM messages;
DROP VIEW messages_all;
DROP TABLE messages;
ALTER TABLE messages_new RENAME TO messages;
COMMIT;""")
c.execute(view_sql)
for i in idx:
    c.execute(i)
c.commit()

after = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
after_field = c.execute("SELECT COUNT(*) FROM messages WHERE addressed_by='field'").fetchone()[0]
print("ЖИВАЯ БАЗА — числа до/после, а не слово «готово»:")
print("  строк ..........", before, "/", after, "OK" if before == after else "!! ПОТЕРЯ")
print("  field ..........", before_field, "/", after_field, "OK" if before_field == after_field else "!! СЪЕДЕНЫ")
print("  целостность ....", c.execute("PRAGMA integrity_check").fetchone()[0])
print("  addressed_by ...", dict(c.execute(
    "SELECT addressed_by, COUNT(*) FROM messages GROUP BY addressed_by").fetchall()))
print("  messages_all ...", c.execute("SELECT COUNT(*) FROM messages_all").fetchone()[0], "строк")
print("  индексов .......", len(idx), "восстановлено")
