# -*- coding: utf-8 -*-
r"""
fix-phoenix-slashes.py — в КОМАНДАХ слепка `python C:\...` обратные слэши → прямые.

Зачем: Bash-инструмент съедает `\` как экранирование, и напечатанная команда у роли мертва
(`can't open file 'C:\\guts\\guts.atlas.mezosyncscriptsguard-all.py'`). Прямые слэши
принимают И Bash, И PowerShell, И cmd — это единственная форма, работающая везде.

⚠️ ПЕРЕПИСАН 2026-07-28 по находке @TAXO, подтверждённой @COORD по коду (#2880).
   Прежняя версия несла `WHERE role='PROTO'` ЗАХАРДКОЖЕННЫМ, а отдана была контуру со словами
   «подставьте свою роль» — параметра роли в ней не было вовсе. На чужой роли она давала
   пустой результат и `exit 0`, то есть **молчала вместо отказа**.
   📌 Класс (@TAXO): ИНСТРУМЕНТ УЧИТ ФОРМЕ, КОТОРОЙ НЕ УМЕЕТ. Тихий отказ хуже громкого:
   роль читает «готово» там, где не сделано ничего. Теперь роль — обязательный параметр,
   неизвестная роль — выход с кодом 2, а не тишина.

    python <абсолютный путь>/fix-phoenix-slashes.py --role TAXO          # что изменится
    python <абсолютный путь>/fix-phoenix-slashes.py --role TAXO --out D:/tmp
    python <абсолютный путь>/fix-phoenix-slashes.py --selftest

Файлы кладутся рядом, применяет их РОЛЬ своим `save-phoenix.py --section <имя> --file <файл>`:
инструмент живую БД НЕ пишет — правка чужого слепка не его дело.
"""
import argparse
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = Path(str(mezo_paths.live_db()))
# Путь ВНУТРИ КОМАНДЫ, а не любой путь в тексте: прозу про каталоги не трогаем.
PATH_IN_CMD = re.compile(r"(?<=python )([A-Za-z]:\\[^\s`'\"]+)")


def fix_line(line):
    if "python " not in line or ":\\" not in line:
        return line
    return PATH_IN_CMD.sub(lambda m: m.group(1).replace("\\", "/"), line)


def collect(db, role):
    """Секции роли и их починенный вид. Пустой список ⇒ роли нет: это ОТКАЗ, не «чисто»."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT section, body FROM phoenix WHERE UPPER(role)=UPPER(?)",
                       (role,)).fetchall()
    known = [r[0] for r in con.execute("SELECT DISTINCT role FROM phoenix ORDER BY role")]
    con.close()
    return rows, known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="ЧЬЯ роль правится (обязателен, кроме --selftest)")
    ap.add_argument("--db", default=str(LIVE_DB))
    ap.add_argument("--out", default=None, help="куда положить файлы (по умолчанию — временный)")
    ap.add_argument("--selftest", action="store_true",
                    help="доказать, что инструмент ОТКАЗЫВАЕТ на неизвестной роли, а не молчит")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.role:
        print("⛔ НЕ ЗАПУЩЕН: нужен --role. Роль НЕ угадывается: инструмент, молча взявший\n"
              "   чужую роль, и есть тот дефект, ради которого он переписан.")
        return 2

    rows, known = collect(a.db, a.role)
    if not rows:
        print(f"⛔ ОТКАЗ: роли «{a.role}» нет в phoenix ({a.db}).\n"
              f"   Есть: {', '.join(known) or '— пусто'}\n"
              f"   Это ОТКАЗ, а не «чисто»: пустой результат с exit 0 читался бы как «нечего чинить».")
        return 2

    out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix=f"phoenix-slash-{a.role}-"))
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for section, body in rows:
        lines = (body or "").splitlines()
        fixed = [fix_line(l) for l in lines]
        n = sum(1 for a_, b_ in zip(lines, fixed) if a_ != b_)
        if not n:
            continue
        total += n
        p = out / f"{a.role}.{section}.md"
        p.write_text("\n".join(fixed), encoding="utf-8")
        print(f"  {section:10} строк починено {n}")
        for a_, b_ in zip(lines, fixed):
            if a_ != b_:
                print(f"     было:  {a_.strip()[:88]}\n     стало: {b_.strip()[:88]}")
        # ⚠️ `.as_posix()` и здесь: первый прогон печатал `--file C:\Users\…` с обратными
        # слэшами — инструмент, чинящий этот класс, САМ учил ему в своей же подсказке.
        print(f"     ⇒ python {mezo_paths.live_scripts().as_posix()}/save-phoenix.py "
              f"--role {a.role} --section {section} --file {p.as_posix()}")
    print(f"\n{'✅ нечего чинить' if not total else f'🔧 {total} строк в {a.role}'} "
          f"— живая БД НЕ изменена, применяет роль сама")
    return 0


def selftest():
    """Главное свойство после находки @TAXO: на НЕИЗВЕСТНОЙ роли — громкий отказ (rc=2),
    а не пустой успех. Плюс сама замена работает."""
    tmp = Path(tempfile.mkdtemp(prefix="fix-slash-selftest-"))
    db = tmp / "m.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT)")
    con.execute("INSERT INTO phoenix VALUES ('SOMEROLE','rebirth',"
                r"'шаг 1: python C:\guts\.atlas\.mezosync\scripts\guard-all.py')")
    con.commit()
    con.close()
    ok = True

    rows, known = collect(db, "НЕТ-ТАКОЙ")
    good = not rows and known == ["SOMEROLE"]
    ok &= good
    print(f"{'✅' if good else '🔴'} неизвестная роль → пусто + список известных {known} (ждём отказ)")

    rows, _ = collect(db, "somerole")            # регистр не должен мешать
    good = len(rows) == 1
    ok &= good
    print(f"{'✅' if good else '🔴'} роль в нижнем регистре найдена: {len(rows)} секц. (ждём 1)")

    src = rows[0][1]
    got = fix_line(src)
    good = str(mezo_paths.live_scripts() / "guard-all.py") in got and "\\" not in got
    ok &= good
    print(f"{'✅' if good else '🔴'} замена слэшей: {got[:70]}")

    proza = r"каталог C:\guts\.atlas\.mezosync — тут python не зовут"
    good = fix_line(proza) == proza
    ok &= good
    print(f"{'✅' if good else '🔴'} проза без вызова python НЕ тронута")

    print(f"\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if ok else '🔴 ПРОВАЛЕНА'} — отказывает громко, "
          f"чинит команды, прозу не трогает")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
