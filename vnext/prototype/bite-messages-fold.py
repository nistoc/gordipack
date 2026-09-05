# -*- coding: utf-8 -*-
r"""ПРИЁМКА переноса записок в архив — карточка #538 шаг ③ часть ③.

🩸 ЧЕМ ОПЛАЧЕНЫ СЛУЧАИ (оба дефекта поймал первый прогон на копии, до всякой живой базы):
```
① проверка ссылок краснела на числах, которых в базе НЕ БЫЛО НИКОГДА («15803», «263238»
   в текстах — просто числа). Перенос был ни при чём: красное горело по ПОСТОРОННЕЙ причине,
   а такой отказ учат обходить ⇒ судим РАЗНИЦУ «разрешалось до / после», не факт
② мерка неизменности включала В СЕБЯ предмет изменения: отпечаток считался по «источник, номер»,
   а перенос источник и меняет («живая лента» → «архив»). Инструмент честно откатил ВЕРНЫЙ
   перенос. Откат сработал, мерка — нет
```
⚡ КЛАСС второго: защита, запрещающая работу, выглядит как сработавшая защита. Отличить можно
только спросив, ЧТО именно мерка обязана считать неизменным.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① холостой прогон НИЧЕГО не меняет: счёт и отпечаток до = после          РАЗЛИЧАЮЩИЙ
  ② перенос → возврат возвращает ленту в исходное состояние (обратимость)  РАЗЛИЧАЮЩИЙ
  ③ речь владельца не уносится ни при каком возрасте                       РАЗЛИЧАЮЩИЙ
  ④ срочное незакрытое не уносится                                        РАЗЛИЧАЮЩИЙ
  ⑤ записка, на которую ссылается свежая, остаётся (разговор жив)          РАЗЛИЧАЮЩИЙ
  ⑥ читатель, не видящий архив ⇒ ОТКАЗ переносить (условие ① правила)      РАЗЛИЧАЮЩИЙ
  ⑦ адресаты унесённых: живая таблица теряет, вид видит                    РАЗЛИЧАЮЩИЙ
  ⑧ контроль: ни одна запись не пропала — сумма живых и архива постоянна

ПОРЧА (--porcha мерка-с-источником): отпечатку возвращают источник и порядок по нему.
ОЖИДАНИЕ, НАЗВАННОЕ ДО ПРОГОНА (и УТОЧНЁННОЕ после первого прогона — честно, вслух):
краснеют ДВА случая, ② и ⑦.
```
② обратимость ....... перенос откатывается сам, проверять обратимость не на чем
⑦ адресаты .......... стои́т НА СОСТОЯВШЕМСЯ переносе: если унесено ноль, живая таблица
                      и вид дают одно число, и разница исчезает
```
🩸 Первая редакция ожидания говорила «краснеет РОВНО ②», и прогон её опроверг. Записано
как есть, а не подогнано: ожидание было неточным, потому что автор держал в голове предмет
случая ⑦ («адресаты теряются») и забыл, что у случая есть УСЛОВИЕ — перенос должен произойти.
⚡ КЛАСС: случай, стоящий на результате другого случая, краснеет вместе с ним — и это не шум,
а зависимость, которую надо назвать. Не назвав её, автор объявляет порчу «не сошедшейся»
и идёт чинить исправное.

⛔ Живой базы не касается: работает на КОПИИ во временном каталоге.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CASES = DIFFER = ЗЕЛЁНЫХ = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, ЗЕЛЁНЫХ
    CASES += 1
    DIFFER += bool(differ)
    ЗЕЛЁНЫХ += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def зови(инструмент, db, *args):
    r = subprocess.run([sys.executable, "-B", str(инструмент), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def метки_точно(строка) -> list:
    """Метки записки СПИСКОМ, а не подстрокой: «WAITING-OWNER-WORD» и «owner-word» — разные метки."""
    import json
    try:
        return json.loads(строка or "[]")
    except Exception:
        return []


def снимок(db):
    con = sqlite3.connect(str(db))
    живых = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    архив = con.execute("SELECT COUNT(*) FROM messages_archive").fetchone()[0]
    тела = con.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(body_md)),0) FROM messages_all").fetchone()
    con.close()
    return {"живых": живых, "архив": архив, "всего": тела[0], "знаков": тела[1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["мерка-с-источником"])
    a = ap.parse_args()

    живой = mezo_paths.live_scripts(__file__) / "messages-fold.py"
    if not живой.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: инструмента переноса нет: {живой}")

    стенд = pathlib.Path(tempfile.mkdtemp(prefix="bite-fold-"))
    try:
        db = стенд / "copy.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        # копия инструмента и его соседей рядом (он читает mezo_refs из своего каталога)
        инструмент = стенд / "messages-fold.py"
        shutil.copy2(живой, инструмент)
        shutil.copy2(mezo_paths.live_scripts(__file__) / "mezo_refs.py", стенд / "mezo_refs.py")
        for имя in ("read-broadcasts.py", "write-message.py"):
            и = mezo_paths.live_scripts(__file__) / имя
            if и.is_file():
                shutil.copy2(и, стенд / имя)

        if a.porcha == "мерка-с-источником":
            т = инструмент.read_text(encoding="utf-8")
            до = т
            т = т.replace('"FROM messages_all ORDER BY id"',
                          '"FROM messages_all ORDER BY source, id"')
            т = т.replace('"SELECT id, writer_role, timestamp, body_md, tags, priority, resolved "',
                          '"SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, source "')
            assert т != до, "порча не легла — строка мерки изменилась, поправь приёмку"
            инструмент.write_text(т, encoding="utf-8")
            print("🧪 ПОРЧА «мерка-с-источником»: ждём красным РОВНО ② (обратимость), остальные целы\n")

        было = снимок(db)

        # ── ① холостой прогон ничего не меняет
        код1, вывод1 = зови(инструмент, db)
        после_холостого = снимок(db)
        case("① холостой прогон НИЧЕГО не меняет",
             код1 == 0 and после_холостого == было,
             f"код {код1} · до {было['живых']}/{было['архив']} · "
             f"после {после_холостого['живых']}/{после_холостого['архив']}", differ=True)

        # ── что инструмент собирался унести (для случаев ③④⑤)
        con = sqlite3.connect(str(db))
        # 🪤 МЕТКУ СРАВНИВАЕМ ТОЧНО, А НЕ ПОДСТРОКОЙ — оплачено первым прогоном этой приёмки.
        # Подстрока «owner-word» ловит метку «WAITING-OWNER-WORD» («ждём слова владельца»),
        # а это не речь владельца, а ожидание её. Приёмка покраснела на ВЕРНОМ инструменте.
        # ⚡ КЛАСС: приёмка и инструмент определяли предмет РАЗНЫМИ мерками, и грубее оказалась
        # мерка приёмки. Свойство, которое мы судим, — «среди точных меток есть owner-word».
        владелец = len([1 for (t,) in con.execute(
            "SELECT tags FROM messages WHERE timestamp < datetime('now','-7 days')")
            if "owner-word" in метки_точно(t)])
        срочные = con.execute(
            "SELECT COUNT(*) FROM messages WHERE timestamp < datetime('now','-7 days') "
            "AND (priority = 'critical' OR (priority = 'high' AND COALESCE(resolved,0) = 0))"
        ).fetchone()[0]
        con.close()

        # ── ② перенос и возврат
        код2, вывод2 = зови(инструмент, db, "--apply")
        после_переноса = снимок(db)
        код3, вывод3 = зови(инструмент, db, "--unfold", "--apply")
        после_возврата = снимок(db)
        case("② перенос → возврат возвращает ленту в исходное состояние",
             код2 == 0 and код3 == 0 and после_переноса["архив"] > 0
             and после_возврата == было,
             f"перенесено {после_переноса['архив']} · после возврата "
             f"{после_возврата['живых']}/{после_возврата['архив']} "
             f"(ждали {было['живых']}/{было['архив']})", differ=True)

        # ── повторный перенос для проверок содержимого архива
        зови(инструмент, db, "--apply")
        con = sqlite3.connect(str(db))
        в_архиве_владельца = len([1 for (t,) in con.execute(
            "SELECT tags FROM messages_archive") if "owner-word" in метки_точно(t)])
        в_архиве_срочных = con.execute(
            "SELECT COUNT(*) FROM messages_archive WHERE priority = 'critical' "
            "OR (priority = 'high' AND COALESCE(resolved,0) = 0)").fetchone()[0]
        # ⑤ на кого ссылается свежая записка
        свежие_ссылки = set()
        import re as _re
        for (тело,) in con.execute("SELECT body_md FROM messages_all "
                                   "WHERE timestamp >= datetime('now','-7 days')"):
            свежие_ссылки.update(int(n) for n in _re.findall(r"#(\d{2,6})", тело or ""))
        унесённые = {r[0] for r in con.execute("SELECT id FROM messages_archive")}
        задето_живых = свежие_ссылки & унесённые
        # ⑦ адресаты
        живой_join = con.execute("SELECT COUNT(*) FROM message_addressee a "
                                 "JOIN messages m ON m.id = a.message_id").fetchone()[0]
        вид_join = con.execute("SELECT COUNT(*) FROM message_addressee a "
                               "JOIN messages_all m ON m.id = a.message_id").fetchone()[0]
        итог = снимок(db)
        con.close()

        case("③ речь владельца не уносится ни при каком возрасте",
             в_архиве_владельца == 0,
             f"старше срока с меткой владельца было {владелец}, в архиве {в_архиве_владельца}",
             differ=True)
        case("④ срочное незакрытое не уносится",
             в_архиве_срочных == 0,
             f"старше срока срочных незакрытых {срочные}, в архиве {в_архиве_срочных}", differ=True)
        case("⑤ записка, на которую ссылается свежая, остаётся (разговор жив)",
             not задето_живых,
             f"унесённых, на которые ссылается свежее: {len(задето_живых)}", differ=True)

        # ── ⑥ читатель, не видящий архив ⇒ отказ
        зови(инструмент, db, "--unfold", "--apply")
        слепой = стенд / "read-broadcasts.py"
        сохранён = слепой.read_text(encoding="utf-8") if слепой.is_file() else None
        if сохранён is not None:
            слепой.write_text(сохранён.replace("messages_all", "messages"), encoding="utf-8")
        код6, вывод6 = зови(инструмент, db, "--apply")
        if сохранён is not None:
            слепой.write_text(сохранён, encoding="utf-8")
        case("⑥ читатель, не видящий архив ⇒ ОТКАЗ переносить (условие ① правила)",
             код6 == 2 and "условие ①" in вывод6,
             f"код {код6} · отказ назван условием: {'да' if 'условие ①' in вывод6 else 'НЕТ'}",
             differ=True)

        case("⑦ адресаты унесённых: живая таблица теряет, вид видит",
             вид_join > живой_join,
             f"через живую таблицу {живой_join} · через вид {вид_join} "
             f"(разница {вид_join - живой_join} — они и потерялись бы у читателя «только моё»)",
             differ=True)

        case("⑧ контроль: ни одна запись не пропала",
             итог["всего"] == было["всего"] and итог["знаков"] == было["знаков"],
             f"записей {итог['всего']} (было {было['всего']}) · "
             f"знаков {итог['знаков']} (было {было['знаков']})")

        print("")
        print(f"ИТОГ: {ЗЕЛЁНЫХ} из {CASES} · различающих {DIFFER}")
        return 0 if ЗЕЛЁНЫХ == CASES else 1
    finally:
        shutil.rmtree(стенд, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
