#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА защиты памяти роли в save-phoenix.py.

Случай @RCC 2026-08-07 16:56 UTC: секция слепка обнулилась при записи, инструмент принял
пустоту и отчитался «OK … (0 chars)». Проверка живости смотрит на ВРЕМЯ сохранения, а не на
РАЗМЕР ⇒ обнулённая секция выглядит свежайшей. Пустой слепок неотличим от идеально свежего.

ШЕСТЬ случаев, ЧЕТЫРЕ различающих. У каждого различающего — КОНТРОЛЬ: рядом стоит заведомо
законное сохранение, которое обязано пройти. Иначе «отказал» ничего не доказывает: инструмент
мог падать на чём угодно.
> Отказ засчитывается за верное поведение ТОЛЬКО когда доказано, что тот же прогон пропускает
> законное. Иначе мы проверили не различение, а поломку.

  ① пустое тело ................................. ОТКАЗ, тело в базе ЦЕЛО
  ② тело из пробелов и переводов строки ......... ОТКАЗ (пустота бывает невидимой)
  ③ обвал в разы без слова ...................... ОТКАЗ
  ④ обвал в разы СО словом --allow-shrink ....... проходит
  ⑤ короткая секция впервые (launcher, 1 строка)  проходит — порога «не меньше 200» тут НЕТ
  ⑥ обычное сохранение .......................... проходит, печатает ДВА числа

⛔ Живой базы не касается: своя временная база в песочнице.
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def find_save() -> str:
    """Найти save-phoenix.py и УПАСТЬ ГРОМКО, если его нет.

    🪤 Первая редакция шла жёстким «../../scripts/save-phoenix.py». У @COORD 2026-08-07
    17:09 UTC этот путь указал в пустоту: Python не нашёл файл, вернул код 2, и приёмка
    прочитала это как «инструмент отказал» — ВСЕ ШЕСТЬ СЛУЧАЕВ КРАСНЫЕ. Он едва не пошёл
    чинить исправный перенос.
    ⇒ Зеркало сегодняшнего зелёного по ложной причине, и оно опаснее: **ложное зелёное
    усыпляет, ложное красное посылает чинить исправное.**
    ⇒ Отсутствие инструмента обязано быть ТРЕТЬИМ исходом («не запустилась»), а не
    маскироваться под результат.
    """
    for rel in (("..", "..", "scripts"), ("..", "scripts"), (".mezosync", "scripts"),
                ("..", "..", "..", ".mezosync", "scripts")):
        p = os.path.normpath(os.path.join(HERE, *rel, "save-phoenix.py"))
        if os.path.exists(p):
            return p
    raise SystemExit(
        "⛔ НЕ ЗАПУСТИЛАСЬ: save-phoenix.py не найден рядом с приёмкой.\n"
        f"   искал от {HERE} в ../../scripts, ../scripts, .mezosync/scripts\n"
        "   Это НЕ «инструмент отказал» и НЕ красное свойство — приёмке нечего испытывать.")


SAVE = find_save()
LONG = "живой слепок роли. " * 40          # ~800 знаков


def build(path: str, seed=()):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
                   PRIMARY KEY (role, section))""")
    con.execute("""CREATE TABLE audit_log (id INTEGER PRIMARY KEY, timestamp TEXT
                   DEFAULT (datetime('now')), actor_role TEXT, action TEXT, target TEXT,
                   diff_md TEXT)""")
    for role, section, body in seed:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'))", (role, section, body))
    con.commit()
    con.close()


def save(path: str, section: str, body: str, extra=()):
    r = subprocess.run([sys.executable, SAVE, "--db", path, "--role", "RCC",
                        "--section", section, "--body", body, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def body_of(path: str, section: str) -> str:
    con = sqlite3.connect(path)
    row = con.execute("SELECT body FROM phoenix WHERE role='RCC' AND section=?",
                      (section,)).fetchone()
    con.close()
    return row[0] if row else ""


CASES = 0
DIFFERENTIATING = 0


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def fresh(tmp: str, name: str) -> str:
    """База с ДВУМЯ секциями: испытуемая state и контрольная plan."""
    path = os.path.join(tmp, f"{name}.db")
    build(path, [("RCC", "state", LONG), ("RCC", "plan", LONG)])
    return path


def control_passes(path: str) -> bool:
    """Контроль: законное сохранение в соседнюю секцию обязано пройти в том же прогоне."""
    out, code = save(path, "plan", LONG + " и ещё немного")
    return code == 0 and "OK" in out


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-phoenix-empty-")
    ok = True

    # ① пустое тело
    p = fresh(tmp, "a")
    out, code = save(p, "state", "")
    kept = body_of(p, "state") == LONG
    ok &= case("① пустое тело: ОТКАЗ, прежний текст цел",
               code != 0 and kept and control_passes(p),
               f"код возврата {code} · тело в базе {'цело' if kept else 'ПОТЕРЯНО'} · "
               f"контрольное сохранение прошло", differ=True)

    # ② невидимая пустота
    p = fresh(tmp, "b")
    out, code = save(p, "state", "   \n\n\t  \n")
    kept = body_of(p, "state") == LONG
    ok &= case("② пробелы и переводы строки — та же пустота",
               code != 0 and kept and control_passes(p),
               f"код возврата {code} · тело {'цело' if kept else 'ПОТЕРЯНО'} · "
               "пустота бывает невидимой глазом", differ=True)

    # ③ обвал в разы без слова
    p = fresh(tmp, "c")
    out, code = save(p, "state", "коротко")
    kept = body_of(p, "state") == LONG
    ok &= case("③ обвал в разы без слова: ОТКАЗ",
               code != 0 and kept and "allow-shrink" in out and control_passes(p),
               f"800 знаков → 7 · код {code} · инструмент НАЗВАЛ ручку, которой это разрешить",
               differ=True)

    # ④ обвал СО словом — проходит
    p = fresh(tmp, "d")
    out, code = save(p, "state", "коротко", extra=["--allow-shrink"])
    ok &= case("④ то же самое СО словом --allow-shrink: проходит",
               code == 0 and body_of(p, "state") == "коротко",
               f"код {code} · сознательная чистка не запрещена, она НАЗВАНА")

    # ⑤ короткая секция впервые — порога длины нет
    p = os.path.join(tmp, "e.db")
    build(p)
    out, code = save(p, "launcher", "Прочитай слепок роли RCC и работай по нему.")
    ok &= case("⑤ короткая секция ВПЕРВЫЕ проходит (launcher — законно одна строка)",
               code == 0 and body_of(p, "launcher").startswith("Прочитай"),
               f"код {code} · глухой порог «не меньше 200 знаков» убил бы эту секцию",
               differ=True)

    # ⑥ обычное сохранение печатает ДВА числа
    p = fresh(tmp, "f")
    out, code = save(p, "state", LONG + " дополнение")
    two = bool(re.search(r"было \d+ → стало \d+", out))
    ok &= case("⑥ обычное сохранение печатает «было → стало»",
               code == 0 and two,
               f"код {code} · два числа спорят сами: «10489 → 0» не прочитаешь как успех "
               f"{'' if two else '— НО ИХ НЕТ В ВЫВОДЕ'}")

    print()
    print(f"✅ ЗАЩИТА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}, "
          "у каждого различающего контроль" if ok
          else "🔴 ЗАЩИТА НЕ ПРИНЯТА")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
