#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА: ритм синхронизации считает новостью и письмо соседа, а не только ленту.

🎯 КЛАСС, РАДИ КОТОРОГО ЗАВЕДЕНА (карточка #242). Разгон сна мерил тишину ТОЛЬКО по ленте
записок. Сосед пишет ФАЙЛОМ в мост — и его вопрос тишину не сбрасывал: роль объявляла
тишину через три минуты после письма и уходила спать, наращивая сон к потолку в 50 минут.
Изнутри это неотличимо от честной тишины: лента и правда пуста, механизм не врёт — он
отвечает на другой вопрос, чем тот, который роль ему задаёт.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: ни ленты, ни моста — тишина, сон растёт                (иначе краснота ничего не значит)
  ② файл соседа в его исходящей → НЕ тишина, сброс к началу           РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ к ②: тот же файл, но уже виденный → снова тишина        РАЗЛИЧАЮЩИЙ
  ④ файл в НАШЕЙ исходящей → тишина (своё письмо себя не будит)       РАЗЛИЧАЮЩИЙ
  ⑤ файл в общей папке старого вида → НЕ тишина                       РАЗЛИЧАЮЩИЙ
  ⑥ причина сброса НАЗЫВАЕТ мост, а не только число записок           РАЗЛИЧАЮЩИЙ
  ⑦ путь соседа недостижим → сон НЕ разгоняется и сказано вслух       РАЗЛИЧАЮЩИЙ
  ⑧ столбец отметки заводится в СУЩЕСТВУЮЩЕЙ таблице                  РАЗЛИЧАЮЩИЙ
  ⑨ неудачное чтение НЕ стирает прежнюю отметку                       РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: база и мосты собираются во временном каталоге.
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

sys.path.insert(0, str(mezo_paths.live_scripts()))
import sync_backoff  # noqa: E402 — испытываем ЖИВОЙ механизм, а не копию рядом

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def стенд(tmp: pathlib.Path, сосед_есть=True) -> tuple:
    """Наш контур + сосед. → (путь к базе, наша исходящая, общая папка, исходящая соседа)."""
    наш = tmp / "atlas"
    (наш / ".mezosync").mkdir(parents=True)
    db = наш / ".mezosync" / "mezosync.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT, body TEXT)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('group_name','atlas')")
    con.execute("CREATE TABLE cross_links (source_group TEXT, target_group TEXT, "
                "target_db_path TEXT, description TEXT)")
    сосед = tmp / "neigh"
    (сосед / ".mezosync").mkdir(parents=True)
    sqlite3.connect(str(сосед / ".mezosync" / "mezosync.db")).close()
    путь = str(сосед / ".mezosync" / "mezosync.db") if сосед_есть else str(
        tmp / "нет-такого" / ".mezosync" / "mezosync.db")
    con.execute("INSERT INTO cross_links VALUES ('atlas','neigh',?,'проба')", (путь,))
    con.commit()
    con.close()

    своя = наш / "atlas.archs" / ".mezosync" / "bridges" / "atlas-neigh"
    общая = наш / "atlas.archs" / ".mezosync" / "bridges" / "neigh-stud-exchange"
    чужая = сосед / "neigh.archs" / ".mezosync" / "bridges" / "neigh-atlas"
    for d in (своя, общая, чужая):
        d.mkdir(parents=True)
    return db, своя, общая, чужая


def дважды(db, писать=None) -> dict:
    """Первый вызов заводит запись роли (он НЕ тишина по построению), второй — судит."""
    sync_backoff.next_sleep(db, "PROTO")
    if писать is not None:
        писать()
    return sync_backoff.next_sleep(db, "PROTO")


def main() -> int:
    ok = True
    tmp = mezo_stand.new("bite-sync-bridge-")
    try:
        # ① КОНТРОЛЬ. Без него всё дальнейшее ничего не значит: молчать можно и от слепоты.
        db, своя, общая, чужая = стенд(tmp / "a")
        r = дважды(db)
        ok &= case("① контроль: ни ленты, ни моста — тишина, сон растёт",
                   r["quiet"] and r["minutes"] == 10,
                   f"сон {r['minutes']} мин, тишина={r['quiet']} — «нашёл» и «не искал» "
                   "обязаны различаться")

        # ② ПИСЬМО СОСЕДА В ЕГО ИСХОДЯЩЕЙ — новость такая же, как записка в ленте.
        db, своя, общая, чужая = стенд(tmp / "b")
        r = дважды(db, lambda: (чужая / "ask.atlas.срочное.md").write_text("?", encoding="utf-8"))
        ok &= case("② файл соседа в его исходящей — НЕ тишина, сброс к началу",
                   not r["quiet"] and r["minutes"] == 5,
                   "иначе роль спит до 50 минут, а вопрос соседа ждёт всё это время",
                   differ=True)

        # ③ ВСТРЕЧНЫЙ: тот же файл, уже виденный. Без него ② зеленел бы у механизма,
        #    который считает новостью ЛЮБОЕ наличие файлов, — и тишины не будет никогда.
        r = sync_backoff.next_sleep(db, "PROTO")
        ok &= case("③ ВСТРЕЧНЫЙ: тот же файл, уже виденный — снова тишина",
                   r["quiet"],
                   "новость — это ИЗМЕНЕНИЕ, а не наличие: иначе сон не разгонится никогда",
                   differ=True)

        # ④ СВОЁ ПИСЬМО СЕБЯ НЕ БУДИТ — тот же довод, по которому лента считает чужие записки.
        db, своя, общая, чужая = стенд(tmp / "c")
        r = дважды(db, lambda: (своя / "ask.neigh.наше.md").write_text("!", encoding="utf-8"))
        ok &= case("④ файл в НАШЕЙ исходящей — тишина: своё письмо себя не будит",
                   r["quiet"],
                   "иначе роль будит себя каждым собственным ответом соседу", differ=True)

        # ⑤ ОБЩАЯ ПАПКА СТАРОГО ВИДА: туда писали обе стороны, и письмо соседа приходит сюда.
        db, своя, общая, чужая = стенд(tmp / "d")
        r = дважды(db, lambda: (общая / "ask.atlas-старое.md").write_text("?", encoding="utf-8"))
        ok &= case("⑤ файл в общей папке старого вида — НЕ тишина",
                   not r["quiet"],
                   "обмен, который старше договора о своих папках, тоже приносит вопросы",
                   differ=True)

        # ⑥ ПРИЧИНА НАЗЫВАЕТ МОСТ. Сброс при пустой ленте без объяснения читается как сбой,
        #    и роль перестаёт верить механизму — цена та же, что у ложной тревоги.
        ok &= case("⑥ причина сброса называет МОСТ, а не только число записок",
                   "мост" in r["reason"].lower(),
                   f"«{r['reason']}» — иначе роль решит, что механизм врёт: лента-то пуста",
                   differ=True)

        # ⑦ ПУТЬ СОСЕДА НЕДОСТИЖИМ — это НЕ «там пусто». Разгонять сон здесь значит
        #    объявить тишину оттого, что не сумели посмотреть.
        db, своя, общая, чужая = стенд(tmp / "e", сосед_есть=False)
        shutil.rmtree(своя.parent)                     # своих папок тоже нет: смотреть нечем
        r = дважды(db)
        ok &= case("⑦ мост недостижим — сон НЕ разгоняется и об этом сказано",
                   not r["quiet"] and "НЕ ПРОЧИТАН" in r["reason"] and r["minutes"] == 5,
                   f"«{r['reason']}» — молчаливый разгон здесь неотличим от честной тишины",
                   differ=True)

        # ⑧ СТОЛБЕЦ В СУЩЕСТВУЮЩЕЙ ТАБЛИЦЕ. 🪤 `CREATE TABLE IF NOT EXISTS` на живой базе —
        #    пустое место: столбец, дописанный в его текст, не появится НИКОГДА и молча.
        db, своя, общая, чужая = стенд(tmp / "f")
        con = sqlite3.connect(str(db))
        con.execute("""CREATE TABLE sync_backoff (role TEXT PRIMARY KEY,
                       sleep_sec INTEGER NOT NULL, quiet_streak INTEGER NOT NULL DEFAULT 0,
                       last_seen_id INTEGER NOT NULL DEFAULT 0, updated_at TEXT)""")
        con.execute("INSERT INTO sync_backoff VALUES ('PROTO', 600, 2, 0, '2026-08-22')")
        con.commit()
        con.close()
        r = sync_backoff.next_sleep(db, "PROTO")
        con = sqlite3.connect(str(db))
        столбцы = {x[1] for x in con.execute("PRAGMA table_info(sync_backoff)")}
        con.close()
        ok &= case("⑧ столбец отметки заводится в УЖЕ СУЩЕСТВУЮЩЕЙ таблице",
                   "last_bridge_mtime" in столбцы,
                   "у живого контура таблица есть — правка её описания не доедет ни до кого",
                   differ=True)

        # ⑨ НЕУДАЧНОЕ ЧТЕНИЕ НЕ СТИРАЕТ ОТМЕТКУ. Иначе следующий опрос счёл бы новым
        #    весь мост целиком — ложная тревога вместо ложной тишины, обмен той же монетой.
        db, своя, общая, чужая = стенд(tmp / "g")
        (чужая / "ask.atlas.первое.md").write_text("?", encoding="utf-8")
        дважды(db)
        con = sqlite3.connect(str(db))
        было = con.execute("SELECT last_bridge_mtime FROM sync_backoff "
                           "WHERE role='PROTO'").fetchone()[0]
        con.execute("UPDATE cross_links SET target_db_path = ?",
                    (str(tmp / "g" / "пусто" / ".mezosync" / "mezosync.db"),))
        con.commit()
        con.close()
        shutil.rmtree(своя.parent)                     # своих папок нет ⇒ читать нечего
        sync_backoff.next_sleep(db, "PROTO")
        con = sqlite3.connect(str(db))
        стало = con.execute("SELECT last_bridge_mtime FROM sync_backoff "
                            "WHERE role='PROTO'").fetchone()[0]
        con.close()
        ok &= case("⑨ неудачное чтение НЕ стирает прежнюю отметку",
                   было and стало == было,
                   f"было {было}, стало {стало} — обнулив её, механизм объявил бы новым "
                   "весь мост при следующем удачном чтении", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ РИТМ И МОСТ — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
