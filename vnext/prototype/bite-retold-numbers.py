# -*- coding: utf-8 -*-
r"""ПРИЁМКА признака «пересказ измеримого» (check-retold-numbers.py, карточка #154).

Главное свойство: признак ПЕРЕМЕРЯЕТ, а не требует пометки, и МОЛЧИТ на совпавшем —
кроме числа ролей, которое канон запрещает держать текстом даже верным.

🪤 Первая редакция признака дала 8 ложных из 8 на живом (регекспы из головы). Приёмка
стережёт обе стороны: находит подложенные жертвы И молчит на всех видах шума, которые
живой материал уже предъявил (цитаты-«ёлочки» · доли «X из Y» · идентификаторы · истории).

⛔ Живой базы не касается: стенд — временная БД в песочнице.
⛔ Число случаев печатает прогон.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check-retold-numbers.py")
if not os.path.exists(CHECK):
    print(f"⛔ ИСПЫТУЕМОГО НЕТ: {CHECK} — отказ мерить, не «чисто»")
    sys.exit(2)

CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand(tmp, name, body, open_cards=3):
    db = os.path.join(tmp, f"{name}.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, saved_at TEXT, body TEXT)")
    con.execute("CREATE TABLE backlog (id INTEGER PRIMARY KEY, role TEXT, status TEXT)")
    con.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)")
    con.execute("INSERT INTO phoenix VALUES ('T','state','2026-08-09 12:00', ?)", (body,))
    for _ in range(open_cards):
        con.execute("INSERT INTO backlog (role, status) VALUES ('T','open')")
    for i in range(5):
        con.execute("INSERT INTO rules (body) VALUES ('живое правило')")
    con.execute("INSERT INTO rules (body) VALUES ('⛔ ОТОЗВАНО владельцем')")
    for i in range(4):
        con.execute("INSERT INTO schema_migrations VALUES (?)", (f"s{i}",))
    con.commit()
    con.close()
    r = subprocess.run([sys.executable, CHECK, "--db", db],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-retold-num-")
    ok = True
    # стендовая правда: карточек открытых 3 · правил живых 5, всего 6 · шагов 4

    # ① РАСХОЖДЕНИЕ ПО КАРТОЧКАМ — красное, ОБЕ стрелки
    out, code = stand(tmp, "a", "открытых карточек 7 — разбирать по одной")
    ok &= case("① «открытых карточек 7» при трёх в базе — красное с обеими стрелками",
               code == 1 and "7" in out and "СЕЙЧАС: 3" in out,
               "реляция, не приговор: обе стрелки печатаются рядом", differ=True)

    # ② ВСТРЕЧНЫЙ: совпадение МОЛЧИТ — красить верное значит шуметь
    out, code = stand(tmp, "b", "открытых карточек 3 — разбирать по одной")
    ok &= case("② совпавшее число карточек — МОЛЧИТ (встречный к ①)",
               code == 0, f"код {code}; шумный признак умирает непрочитанным", differ=True)

    # ③ «РОЛЕЙ N» — красное И ПРИ ВЕРНОМ ЧИСЛЕ: канон запрещает держать его текстом
    out, code = stand(tmp, "c", "ролей 9, работаем дальше")
    ok &= case("③ «ролей 9» — красное даже без сверки (канон: число не держим)",
               code == 1 and "РОЛЕЙ ТЕКСТОМ" in out,
               "число ролей протухает молча и учит отвергать правду", differ=True)

    # ④ ВСТРЕЧНЫЙ к ③: надгробие ЧИСЛУ в той же строке — гасит
    out, code = stand(tmp, "d", "⚰️ было «ролей 8» — число НЕ ДЕРЖИМ, спрашивай реестр")
    ok &= case("④ надгробие числу ролей в той же строке — гасит (встречный к ③)",
               code == 0, f"код {code}; иначе признак запретил бы объяснять сам запрет",
               differ=True)

    # ⑤ ЦИТАТА В «ЁЛОЧКАХ» — не утверждение (живой ложняк первой редакции)
    out, code = stand(tmp, "e", "урок: «11 правил» при четырёх — впечатанное число врёт")
    ok &= case("⑤ число в «ёлочках»-цитате — молчит (ложняк первой редакции)",
               code == 0, f"код {code}; цитата урока — не факт о сегодня", differ=True)

    # ⑥ ДОЛЯ «X из Y» — замер о наборе, не пересказ состояния (второй живой ложняк)
    out, code = stand(tmp, "f", "у 32 правил из 38 основания не найти — долг шаблона")
    ok &= case("⑥ «32 правил из 38» — молчит: доля-замер, не пересказ (ложняк №2)",
               code == 0, f"код {code}", differ=True)

    # ⑦ РАСХОЖДЕНИЕ ПО ПРАВИЛАМ: ни с живыми, ни со всеми
    out, code = stand(tmp, "g", "правил 11 — сверить свод")
    ok &= case("⑦ «правил 11» при 5 живых / 6 всего — красное, обе величины названы",
               code == 1 and "живых 5" in out and "всего 6" in out,
               "двусмысленность живые/всего решается показом ОБОИХ", differ=True)

    # ⑧ ВСТРЕЧНЫЙ к ⑦: совпадение с ЛЮБОЙ из двух величин — молчит
    out, code = stand(tmp, "h", "правил 5 — сверить свод")
    ok &= case("⑧ «правил 5» совпало с живыми — молчит (встречный к ⑦)",
               code == 0, f"код {code}; полусовпадение — граница, не находка", differ=True)

    # ⑨ ПУСТЫЕ СЛЕПКИ — отказ мерить (код 2), не «чисто»
    db9 = os.path.join(tmp, "i.db")
    con = sqlite3.connect(db9)
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, saved_at TEXT, body TEXT)")
    con.commit(); con.close()
    r = subprocess.run([sys.executable, CHECK, "--db", db9],
                       capture_output=True, text=True, encoding="utf-8")
    ok &= case("⑨ слепков нет — отказ мерить, отдельный код",
               r.returncode == 2 and "нечего" in r.stdout,
               f"код {r.returncode}", differ=True)

    print()
    print(f"{'✅ ПРИЗНАК ПРИНЯТ' if ok else '🔴 ПРИЗНАК НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, у каждого различающего встречный")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
