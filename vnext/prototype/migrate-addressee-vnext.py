# -*- coding: utf-8 -*-
r"""migrate-addressee-vnext.py — миграция Э-Б НА ПЕСОЧНИЦЕ: словарь адресатов приводится к канону.

Что делает (решения — в 08-addressee-dictionary.md, Р4/Р5):
  ① колонка messages.broadcast (0/1) — «всем» становится свойством ЗАПИСКИ;
  ② склейки «CHROME CORE STUD» в message_addressee разводятся по именам
    (kind и linked_by сохраняются; происхождение развода — 'backfill': это разбор
    машиной, а не слово руки писавшего);
  ③ строки role IN ('ALL','ВСЕ') → broadcast=1 у записки, строка адресата удаляется
    (ролей «ALL»/«ВСЕ» не существует — строка о них лгала о реестре; «ВСЕ» кладёт
    живой писатель, не знающий канона, — до его починки строки будут прибывать);
  ④ 'ВЛАДЕЛЕЦ' не трогается: законное спец-имя.

⛔ ЖИВУЮ БАЗУ НЕ ОТКРЫВАЕТ: --db обязателен и обязан НЕ совпадать с живой.
Отчёт — счётчиками ДО/ПОСЛЕ и поимённо: молчаливая миграция неотличима от несработавшей.

Запуск:  python <КОНТУР>/vnext-tools/migrate-addressee-vnext.py --db <песочница>
"""
import argparse
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="миграция Э-Б: канон адресатов (только песочница)")
    ap.add_argument("--db", required=True, help="песочница; живая база — отказ")
    a = ap.parse_args()
    db = pathlib.Path(a.db).resolve()
    if db == mezo_paths.live_db().resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Миграция Э-Б живёт в песочнице до слова владельца.")
    if not db.exists():
        sys.exit(f"⛔ ОТКАЗ: базы нет — {db}. Это не «мигрировать нечего», это неверный путь.")

    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = ON")

    # ① колонка broadcast — идемпотентно: повторный прогон не падает и не дублирует.
    cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    if "broadcast" not in cols:
        con.execute("ALTER TABLE messages ADD COLUMN broadcast INTEGER NOT NULL DEFAULT 0")
        print("① колонка messages.broadcast добавлена")
    else:
        print("① колонка messages.broadcast уже есть — не трогаю")

    # ② склейки: имя с пробелом = несколько имён одной строкой.
    склейки = con.execute(
        "SELECT message_id, role, kind, linked_by FROM message_addressee"
        " WHERE role LIKE '% %'").fetchall()
    for mid, ролька, kind, lb in склейки:
        имена = [x for x in ролька.split() if x]
        for имя in имена:
            con.execute(
                "INSERT OR REPLACE INTO message_addressee (message_id, role, kind, linked_by)"
                " VALUES (?, ?, ?, 'backfill')", (mid, имя, kind))
        con.execute("DELETE FROM message_addressee WHERE message_id=? AND role=? AND kind=?",
                    (mid, ролька, kind))
        print(f"② записка #{mid}: склейка «{ролька}» ({kind}) разведена на {len(имена)} имён")
    if not склейки:
        print("② склеек нет")

    # ③ ALL → свойство записки.
    строки_all = con.execute(
        "SELECT DISTINCT message_id FROM message_addressee WHERE role IN ('ALL','ВСЕ')").fetchall()
    for (mid,) in строки_all:
        con.execute("UPDATE messages SET broadcast=1 WHERE id=?", (mid,))
    n = con.execute("DELETE FROM message_addressee WHERE role IN ('ALL','ВСЕ')").rowcount
    print(f"③ ALL: записок помечено «всем» — {len(строки_all)}, строк адресата снято — {n}")

    con.commit()
    итог = con.execute("SELECT COUNT(*) FROM message_addressee WHERE role LIKE '% %'"
                       " OR role IN ('ALL','ВСЕ')").fetchone()[0]
    bc = con.execute("SELECT COUNT(*) FROM messages WHERE broadcast=1").fetchone()[0]
    con.close()
    print(f"ИТОГО ПОСЛЕ: склеек и ALL — {итог} (обязано быть 0) · записок «всем» — {bc}")
    return 0 if итог == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
