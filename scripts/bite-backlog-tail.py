# -*- coding: utf-8 -*-
"""Различающие случаи для свёрнутой строки (карточка #237).

Каждый случай проверяет ОДНО и имеет встречный: без встречного зелёный мог бы значить
«признак ослеп», а не «работает».
"""
import sqlite3, sys, tempfile, pathlib, os

sys.path.insert(0, r"<КОНТУР>\.mezosync\scripts")
import backlog_view as bv  # noqa: E402

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(f"{'✅' if cond else '⛔'} {name}")
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1


db = mezo_stand.new("tail-") / "t.db"
con = sqlite3.connect(str(db))
con.executescript("""
CREATE TABLE backlog (id INTEGER PRIMARY KEY, role TEXT, title TEXT, status TEXT,
                      priority TEXT, done_when TEXT, created_at TEXT,
                      parent_track TEXT);
""")
# ↑ parent_track — как в живой схеме. Песочница БЕЗ него уже роняла витрину после
# шага 0 пула (27.08): продукт читает поле, которого в песочнице не было, — класс
# «испытываем не то, что чиним». Таблицы tracks тут НЕТ намеренно: витрина обязана
# жить и в базе без пулов (active_pool_tracks отвечает пустым множеством).


def add(bid, status, prio, days, crit="есть", role="R"):
    con.execute("INSERT INTO backlog VALUES (?,?,?,?,?,?,datetime('now',?),NULL)",
                (bid, role, f"задача {bid}", status, prio, crit, f"-{days} days"))


# ① ХВОСТА НЕТ, когда карточек ровно предел
for i in range(1, 6):
    add(i, "open", "normal", i)
con.commit()
lines = bv.reminder_lines(con, "R")
case("① ровно предел — свёрнутой строки нет вовсе",
     not any("и ещё" in l for l in lines), f"строк {len(lines)}")

# ② ВСТРЕЧНЫЙ: одна сверх предела — строка появляется
add(6, "open", "normal", 6)
con.commit()
lines = bv.reminder_lines(con, "R")
case("② одна сверх предела — свёрнутая строка появилась",
     any("и ещё 1" in l for l in lines), lines[-1].strip())

# ③ САМАЯ СТАРАЯ В ХВОСТЕ — названа номером и возрастом
con.execute("DELETE FROM backlog")
for i in range(1, 6):
    add(i, "open", "critical", 2)          # срочные и молодые — они и покажутся
add(90, "open", "low", 99)                 # старая, но низкой срочности ⇒ в хвосте
con.commit()
lines = bv.reminder_lines(con, "R")
case("③ самая старая лежит в хвосте — названа номером и возрастом",
     "#90" in lines[-1] and "99" in lines[-1], lines[-1].strip())

# ④ ВСТРЕЧНЫЙ к ③: самая старая ПОКАЗАНА ⇒ про неё в хвосте молчим
con.execute("DELETE FROM backlog")
add(1, "open", "critical", 99)             # старая И срочная ⇒ показана
for i in range(2, 8):
    add(i, "open", "low", 1)
con.commit()
lines = bv.reminder_lines(con, "R")
case("④ встречный: самая старая показана — в хвосте про неё НЕ говорим",
     "САМАЯ СТАРАЯ" not in lines[-1],
     lines[-1].strip() + "   ⇐ без этого случая ③ зеленел бы всегда")

# ⑤ СОСТОЯНИЯ спрятанного названы
con.execute("DELETE FROM backlog")
for i in range(1, 6):
    add(i, "open", "critical", 1)
add(20, "blocked", "low", 2)
add(21, "awaiting_word", "low", 2)
add(22, "in_review", "low", 2)
con.commit()
lines = bv.reminder_lines(con, "R")
t = lines[-1]
case("⑤ состояния спрятанного названы словами",
     "заблокированных 1" in t and "ждущих слова человека 1" in t and "на проверке 1" in t,
     t.strip())

# ⑥ ВСТРЕЧНЫЙ к ⑤: спрятаны только открытые ⇒ состояний не перечисляем
con.execute("DELETE FROM backlog")
for i in range(1, 9):
    add(i, "open", "normal", 1)
con.commit()
lines = bv.reminder_lines(con, "R")
case("⑥ встречный: в хвосте только открытые — лишних слов нет",
     "заблокированных" not in lines[-1] and "на проверке" not in lines[-1],
     lines[-1].strip() + "   ⇐ без этого случая ⑤ мог бы печатать всё подряд")

# ⑦ БЕЗ КРИТЕРИЯ в хвосте — сказано, что их не закрыть
con.execute("DELETE FROM backlog")
for i in range(1, 6):
    add(i, "open", "critical", 1)
add(30, "open", "low", 1, crit="")
con.commit()
lines = bv.reminder_lines(con, "R")
case("⑦ спрятанная без критерия приёмки — названа отдельно",
     "без критерия 1" in lines[-1], lines[-1].strip())

# ⑧ КОНТРОЛЬ: приёмке было на что смотреть
n = con.execute("SELECT COUNT(*) FROM backlog").fetchone()[0]
case("⑧ контроль: данные были", n > 0, f"карточек в пробной базе {n}")

con.close()
os.unlink(db)
print(f"\nИТОГ: {OK}/{OK + FAIL}")
sys.exit(mezo_stand.finish(0 if not FAIL else 1))
