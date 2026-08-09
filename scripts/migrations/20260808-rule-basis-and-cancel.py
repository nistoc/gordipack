"""Пять полей у правила свода: ТРИ ОСНОВАНИЯ + ВИД И ДЕТАЛЬ УСЛОВИЯ ОТМЕНЫ.

Слово владельца: 2026-08-08 10:29 UTC (передано @PROTO запиской #3385) и подтверждено
ЖИВЫМ словом в чате COORD 2026-08-08 10:40 UTC — «Обе делаю» + «Одной правкой со всеми».
Точка отката: %TEMP%/mezosync.pre-rules-fields.db (20 963 328 б, снята 10:43 UTC).

ЧТО ЗАВОДИТСЯ И ПОЧЕМУ ИМЕННО ТАК
  basis .......... на каком основании правило существует (замер, инцидент, довод)
  authorized .. кто разрешил (owner / coord / имя роли)
  source_ref ..... ГДЕ это сказано: «#3385» или «чат COORD 2026-08-08 10:29 UTC»
  expiry_kind .... ВИД условия отмены, не проза. Свободный текст здесь выродится
                   в «бессрочно» у всех — а вид можно ПОСЧИТАТЬ и показать распределение:
                     forever ......... отменяется только словом
                     until_date ...... до даты — проверка механически спросит, не прошла ли
                     until_event ..... до НАБЛЮДАЕМОГО события
                     while_measured ... пока держится замер: число + чем мерено
  expiry_cond .. деталь вида (дата · событие · число и способ замера). Для forever пусто

⚠️ ПОЧЕМУ ПОЛЕЙ ПЯТЬ, А НЕ ЧЕТЫРЕ: у «условия отмены» обязан быть машинный читатель,
   иначе оно повторит судьбу четырёх механизмов, заведённых «по желанию» и не позванных
   ни разу (--task 0 из 1724 · parent_id 0 из 84 · «какой запиской» 0 из 9 · гашение
   срочности 0 из 546). Читатель есть только у ВИДА; проза читателя не имеет.

⛔ СТАРЫЕ ПРАВИЛА ЗАДНИМ ЧИСЛОМ НЕ ЗАПОЛНЯЮТСЯ: основание, восстановленное по памяти,
   выглядит доказательством, не будучи им. Поля заводятся пустыми и заполняются при
   СЛЕДУЮЩЕМ касании правила — отказом в set-rule.py, а не просьбой.

⚠️ ИМЕНА СВЕРЕНЫ С ОПУБЛИКОВАННЫМ КОНТРАКТОМ @PROTO (#3388, 10:44 UTC): первая редакция
несла мои имена (authorized_by · cancel_kind · cancel_detail), контур же читает его.
Переименовано ALTER TABLE RENAME COLUMN в 10:51 UTC, пока поля пусты и цена нулевая.
⛔ ОДНО ОТКЛОНЕНИЕ, НАЗЫВАЮ ГРОМКО: у него source_note INTEGER — номер записки. У меня
source_ref TEXT, и это возражение по существу: живое слово владельца в чате номера НЕ ИМЕЕТ.
INTEGER заставил бы либо оставить пустым, либо выдумать номер ровно у тех правил, которые
даны голосом, — то есть у самых сильных. Тип обязан вмещать «чат COORD 2026-08-08 10:40 UTC».

ALTER TABLE ADD COLUMN здесь достаточен: таблицу пересоздавать нечем — ни DEFAULT,
ни CHECK на существующих строках не меняем. Проверка вида живёт в set-rule.py, где
у отказа есть человеческий текст; CHECK в схеме дал бы роли невнятный SQL-срыв.
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else 'C:/guts/.atlas/.mezosync/mezosync.db'

NEW_COLS = [
    ("basis",         "TEXT"),
    ("authorized", "TEXT"),
    ("source_ref",    "TEXT"),
    ("expiry_kind",   "TEXT"),
    ("expiry_cond", "TEXT"),
]

c = sqlite3.connect(DB, timeout=15)

before_cols = [r[1] for r in c.execute("PRAGMA table_info(rules)")]
before_rows = c.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
before_keys = {r[0] for r in c.execute("SELECT rule_key FROM rules")}

added, already = [], []
for name, typ in NEW_COLS:
    if name in before_cols:
        already.append(name)          # идемпотентно: повтор не роняет и не врёт «добавил»
        continue
    c.execute(f"ALTER TABLE rules ADD COLUMN {name} {typ}")
    added.append(name)
c.commit()

after_cols = [r[1] for r in c.execute("PRAGMA table_info(rules)")]
after_rows = c.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
after_keys = {r[0] for r in c.execute("SELECT rule_key FROM rules")}

print(f"БАЗА: {DB}")
print("ЧИСЛА ДО/ПОСЛЕ — а не слово «готово»:")
print("  правил .........", before_rows, "/", after_rows,
      "OK" if before_rows == after_rows else "!! ПОТЕРЯ")
print("  ключи ..........", "все на месте" if before_keys == after_keys
      else f"!! РАЗОШЛИСЬ: пропало {sorted(before_keys - after_keys)}")
print("  колонок ........", len(before_cols), "→", len(after_cols))
print("  добавлено ......", ", ".join(added) or "(ничего)")
if already:
    print("  уже было .......", ", ".join(already), "— повтор безвреден")
print("  целостность ....", c.execute("PRAGMA integrity_check").fetchone()[0])
filled = c.execute("SELECT COUNT(*) FROM rules WHERE basis IS NOT NULL AND basis <> ''").fetchone()[0]
print(f"  с основанием ...  {filled} из {after_rows} — ожидаемо 0: задним числом не заполняем")
