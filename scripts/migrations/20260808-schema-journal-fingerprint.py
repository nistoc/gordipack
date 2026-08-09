"""Шаг 008: журнал изменений схемы оживает — отпечаток + четыре пропущенные записи.

ПОВОД: замер @PROTO #3419 (08.08 14:51 UTC), перемерен моей рукой 15:02 UTC.
База отвечала «рубеж v3, шагов 7, сверх рубежа 0» при ЧЕТЫРЁХ применённых с тех пор шагах.
Кода, пишущего в `schema_migrations`, в scripts/ не было вообще: журнал заполнили один раз
06.08 и с тех пор он мёртв.

ПОРЯДОК ВАЖЕН И ОН НЕ МОЙ — его назвал @PROTO, и он прав:
    ① сперва МЕХАНИЗМ (шаг пишет себя сам + отпечаток),
    ② сторож,
    ③ только потом дописать пропущенное.
Допиши мы строки первыми — журнал стал бы верным на один день и снова начал врать,
а мы бы считали вопрос закрытым.

⚠️ ЧЕТЫРЕ ЗАПИСИ ВОССТАНАВЛИВАЮТСЯ ЗАДНИМ ЧИСЛОМ И ПОМЕЧЕНЫ КАК ТАКИЕ. Их отпечаток
снят СЕГОДНЯ, а не в момент шага, — выдавать его за современный факту нельзя. Помета
стоит в самой записи, а не в этом файле: файл читают реже, чем базу.

⛔ Точка отката: %TEMP%/mezosync.pre-schema-journal.db
"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema_journal import ensure_column, fingerprint, record_step   # noqa: E402

DB = sys.argv[1] if len(sys.argv) > 1 else r"C:\guts\.atlas\.mezosync\mezosync.db"

# Четыре шага, применённые мимо журнала. Даты — по следам в схеме и по запискам ленты,
# не по памяти: две миграции мои и @PROTO, обе названы в ленте с номерами.
MISSED = [
    ("20260807-addressed-by-unset",
     "умолчание addressed_by 'backfill' → 'unset' (@PROTO, записка #3141)"),
    ("20260808-rule-basis-and-cancel",
     "пять полей у правила: основание · кто разрешил · где сказано · вид и условие отмены (COORD, #3390)"),
    ("20260808-message-addressee",
     "адресат стал полем: таблица message_addressee, витрина --to-me (@PROTO, #3408)"),
    ("20260808-backfill-addressee",
     "обратное заполнение адресатов из тел, 5603 строки, помечены backfill (@PROTO, #3416)"),
]

conn = sqlite3.connect(DB, timeout=15)

if len(sys.argv) <= 1:                       # живая база — точка отката обязательна
    backup = Path(tempfile.gettempdir()) / "mezosync.pre-schema-journal.db"
    shutil.copy(DB, backup)
    print(f"точка отката: {backup} ({backup.stat().st_size} б)")

before_rows = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
before_ver = conn.execute("SELECT * FROM schema_version").fetchone()
added_col = ensure_column(conn)

# ③ пропущенное — ПОСЛЕ того, как механизм ① существует (см. schema_journal.record_step)
added = []
have = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
for version, note in MISSED:
    if version in have:
        continue
    conn.execute(
        "INSERT INTO schema_migrations (version, note, fingerprint) VALUES (?,?,?)",
        (version, note + " [ЗАПИСАНО ЗАДНИМ ЧИСЛОМ: отпечаток снят позже шага]", None))
    added.append(version)

# Сам шаг 008 записывает СЕБЯ — первым же применением нового механизма. Если механизм
# не работает, это выяснится здесь, а не через неделю на чужой миграции.
record_step(conn, "008-schema-journal-fingerprint",
            "журнал оживает: шаг пишет себя сам, у записи есть отпечаток схемы; "
            "сторож сверяет отпечаток текущей схемы с последним записанным")
conn.commit()

after_rows = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
after_ver = conn.execute("SELECT * FROM schema_version").fetchone()
print("ЧИСЛА ДО/ПОСЛЕ — а не слово «готово»:")
print("  записей в журнале ...", before_rows, "→", after_rows)
print("  колонка отпечатка ...", "добавлена" if added_col else "уже была")
print("  дописано задним числом", len(added), ":", ", ".join(added) or "(нечего)")
print("  версия ..............", before_ver, "→", after_ver)
print("  отпечаток сейчас ....", fingerprint(conn))
print("  целостность .........", conn.execute("PRAGMA integrity_check").fetchone()[0])
