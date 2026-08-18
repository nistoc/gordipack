"""Шаг ① плана @PROTO: умолчание addressed_by 'backfill' → 'unset'.

Слово владельца: 2026-08-07 10:13 UTC, чат COORD — «разрешаю обработать запрос от proto».
Точка отката: scratchpad/pre-shown-field.db (12.6 МБ, integrity ok, снята 10:13 UTC).
Прогон на копии (try-unset.db) прошёл: 1724/1724 строк, VIEW жив, все три различающих
случая @PROTO (#3141) зелёные.

SQLite не умеет ALTER для DEFAULT и CHECK — таблица пересоздаётся. Порядок важен:
VIEW messages_all дропается ДО таблицы и восстанавливается ПОСЛЕ, иначе он повиснет
на несуществующей таблице. Индексы снимаются заранее и накатываются обратно.

ИДЕМПОТЕНТНОСТЬ (починено 2026-08-09, находка @PROTO #3463 пересборкой песочницы).
v1 падала на повторном прогоне «table messages already exists», нарушая моё же правило
migration-safety. Причина НЕ в отсутствии гарда как такового, а тоньше: после
`ALTER TABLE ... RENAME TO messages` SQLite хранит схему как CREATE TABLE "messages"
— В КАВЫЧКАХ. Замена имени искала форму без кавычек, молча не срабатывала, и шаг пытался
создать уже существующую таблицу. То есть первый же прогон делал схему непохожей на ту,
которую ожидал второй: шаг ломал сам себя своим успехом.
"""
import re
import sqlite3
import pathlib
import sys

# Путь к базе — первым аргументом; без него живая. Нужен НЕ для удобства: без него
# рабочую ветку шага невозможно прогнать иначе как по живой базе, то есть проверка
# идемпотентности требовала бы того самого риска, от которого защищает.
# ДЕФОЛТ БЕРЁТСЯ ОТ РАСПОЛОЖЕНИЯ ЭТОГО ФАЙЛА, А НЕ ВПИСАН ПУТЁМ КОНТУРА-ДОНОРА.
# Найдено 18.08 при подготовке запуска второго проекта: шаг схемы без аргумента правил бы
# ЧУЖУЮ живую базу, а save-phoenix прямо велит роли «прогони migrations/…». Роль исполнила
# бы приказ буквально и попала бы не в свою базу — молча и с успешным итогом на экране.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import mezo_paths  # noqa: E402
DB = sys.argv[1] if len(sys.argv) > 1 else str(mezo_paths.live_db(__file__))
c = sqlite3.connect(DB, timeout=15)
c.execute("PRAGMA foreign_keys=OFF")

old_sql = c.execute("SELECT sql FROM sqlite_master WHERE name='messages'").fetchone()[0]

# ГАРД ИДЕМПОТЕНТНОСТИ: спрашиваем СХЕМУ, а не журнал — журнал говорит «шаг записан»,
# схема говорит «работа сделана». Второе и есть предмет проверки.
if "'unset'" in old_sql:
    print("✅ уже применено: умолчание addressed_by = 'unset' стоит в схеме. Ничего не делаю.")
    sys.exit(0)
view_sql = c.execute("SELECT sql FROM sqlite_master WHERE name='messages_all'").fetchone()[0]
idx = [r[0] for r in c.execute(
    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='messages' AND sql IS NOT NULL")]

# Имя заменяем регуляркой: SQLite пишет его и голым, и в двойных кавычках, и в квадратных
# скобках — в зависимости от того, как таблица родилась. Форма зависит от истории объекта,
# а не от нашего намерения, поэтому перечисляем все три.
# ⚠️ Граница слова \b стои́т ТОЛЬКО у голой формы: после закрывающей кавычки её нет вовсе
# (кавычка и пробел оба не-словесные), и общий \b в конце молча отбрасывал вариант
# в кавычках — ровно тот, ради которого правка и делалась. Поймано приёмкой, не глазами.
new_sql, n_renamed = re.subn(r'CREATE\s+TABLE\s+(?:"messages"|\[messages\]|messages\b)',
                             "CREATE TABLE messages_new", old_sql, count=1)
assert n_renamed == 1, f"имя таблицы не найдено в схеме — шаг остановлен: {old_sql[:80]}"
new_sql = new_sql.replace("DEFAULT 'backfill' CHECK (addressed_by IN ('field','backfill'))",
                          "DEFAULT 'unset' CHECK (addressed_by IN ('field','backfill','unset'))")
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
