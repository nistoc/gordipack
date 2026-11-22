# -*- coding: utf-8 -*-
# PLANTS: rules
r"""
bite-rule-expiry.py — приёмка захода 2.3: наступление сроков годности правил.
На КОПИИ живой базы (mezo_stand); суд по подсаженным правилам zzexp-*.

Случаи:
  ① until_event «карточка #N», карточка ЗАКРЫТА → 🔴 «событие наступило»
  ② ВСТРЕЧНЫЙ: карточка открыта → тихо
  ③ срок «до YYYY-MM-DD» прошёл → 🔴          ④ ВСТРЕЧНЫЙ: срок впереди → тихо
  ⑤ ГОЛАЯ дата-происхождение («На 2026-08-08 доля…») → НЕ красное: судим
     по происхождению, а не по виду (первый прогон дал 4 ложных из 4 на живом)
  ⑥ немашинное условие, правило не трогали дольше порога → 🟡 «перечитай рукой»
  ⑦ отозванное правило с наступившим условием → НЕ судится (история)
  ⑧ ОБРАТНЫЙ ХОД: ветка карточек отключена в копии → ① гаснет
  ⑨ контроль: живая база прогоном не изменилась. Суд — ПО СВОИМ СЛЕДАМ ПОИМЁННО (роль ZZE и семь
     ключей правил zzexp-*: вопрос mezo_stand.ask_traces, судится ПРИБАВКА следов), а не по размеру
     и времени правки файла: те меняет любая честная запись соседей за время прогона (карточка #804).
     Встречные на подставной базе стенда: ⑨-а чужая запись случай НЕ роняет · ⑨-б свой след
     роняет и назван поимённо · ⑨-в база недоступна — третий исход «НЕ ПРОВЕРЕНО», код выхода 2 ·
     ⑨-г все пробные имена на стенде находятся (иначе вопрос к живой базе слеп)
"""
import importlib.util
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402

LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

GUARD = HERE / "guard-rule-expiry.py"
OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Свои следы приёмки (карточка #804): роль подсаженных карточек и ключи подсаженных правил. По ним ⑨
# судит, не попали ли записи в живую базу; таблицы NEED — куда эти имена сеются.
MARKS = ("ZZE", "zzexp-card-closed", "zzexp-card-open", "zzexp-deadline-past", "zzexp-deadline-future",
         "zzexp-origin-date", "zzexp-stale-hand", "zzexp-revoked")
NEED = ("backlog", "rules")
# Первый вопрос — до стенда и до копии: база контура не читается вовсе — «НЕ ПРОВЕРЕНО», код 2.
live_before = mezo_stand.first_traces(LIVE_DB, MARKS, NEED)
mod = load(GUARD, "gre_live")
stand = mezo_stand.new("rule-expiry-")
db = stand / "mezosync.db"
mezo_stand.snapshot_db(LIVE_DB, db)
# Подставная база для встречных ⑨-а/б/в: схема копии без строк, снята из стенда — живая база
# второй раз не открывается.
judge_db = mezo_stand.empty_db(db, stand / "judge.db")

con = sqlite3.connect(str(db))
cur = con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
                  "created_by, done_when) VALUES ('ZZE','закрытая','т','done','normal','[]',"
                  "'PROTO','к')")
closed_id = cur.lastrowid
cur = con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
                  "created_by, done_when) VALUES ('ZZE','открытая','т','open','normal','[]',"
                  "'PROTO','к')")
open_id = cur.lastrowid


def add_rule(key, kind, cond, status="active", old=False):
    con.execute("INSERT INTO rules (rule_key, body, status, expiry_kind, expiry_cond"
                + (", revoked_at, revoked_by, revoked_reason" if status == "revoked" else "")
                + ") VALUES (?,?,?,?,?" + (",datetime('now'),'bite','проба'" if status == "revoked" else "") + ")",
                (key, "тело пробы", status, kind, cond))
    if old:
        con.execute("UPDATE rules SET updated_at=datetime('now','-45 days') WHERE rule_key=?",
                    (key,))


add_rule("zzexp-card-closed", "until_event", f"снимается, когда карточка #{closed_id} закрыта")
add_rule("zzexp-card-open", "until_event", f"снимается, когда карточка #{open_id} закрыта")
add_rule("zzexp-deadline-past", "until_event", "держится до 2026-01-01, дальше пересмотр")
add_rule("zzexp-deadline-future", "until_event", "держится до 2099-01-01, дальше пересмотр")
add_rule("zzexp-origin-date", "while_measured",
         "порог предложен PROTO; смягчается при доле 9 из 10 — вчерашний замер", old=False)
con.execute("UPDATE rules SET expiry_cond='доля объявленных дойдёт до 9 из 10; "
            "На 2026-06-01 объявляют три роли' WHERE rule_key='zzexp-origin-date'")
add_rule("zzexp-stale-hand", "while_measured", "пересмотр, если разгон станет дороже экономии",
         old=True)
add_rule("zzexp-revoked", "until_event", "снимается, когда карточка "
         f"#{closed_id} закрыта", status="revoked")
con.commit()
con.close()

conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
red, yellow, skipped, total = mod.judge(conn, 30)
conn.close()
rk = {k for k, _ in red}
yk = {k for k, _ in yellow}

case("① карточка условия закрыта → 🔴 «событие наступило»", "zzexp-card-closed" in rk,
     next((w for k, w in red if k == "zzexp-card-closed"), "—"))
case("② встречный: карточка открыта → тихо",
     "zzexp-card-open" not in rk and "zzexp-card-open" not in yk)
case("③ «до 2026-01-01» прошло → 🔴", "zzexp-deadline-past" in rk)
case("④ встречный: «до 2099-01-01» → тихо",
     "zzexp-deadline-future" not in rk and "zzexp-deadline-future" not in yk)
case("⑤ голая дата-происхождение («На 2026-06-01…») → НЕ красное, 🟡 по возрасту замера",
     "zzexp-origin-date" not in rk and "zzexp-origin-date" in yk,
     next((w for k, w in yellow if k == "zzexp-origin-date"), "—"))
case("⑥ немашинное условие + 45 дн без касания → 🟡 «перечитай рукой»",
     "zzexp-stale-hand" in yk)
case("⑦ отозванное с наступившим условием → не судится",
     "zzexp-revoked" not in rk and "zzexp-revoked" not in yk)

# ⑧ обратный ход
src = GUARD.read_text(encoding="utf-8")
ANCHOR = "m = CARD.search(cond)"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь ветки карточек не найден")
weak = stand / "weak-guard.py"
weak.write_text(src.replace(ANCHOR, "m = None"), encoding="utf-8")
wmod = load(weak, "gre_weak")
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
red2, _, _, _ = wmod.judge(conn, 30)
conn.close()
case("⑧ обратный ход: ветка карточек снята → ① гаснет",
     "zzexp-card-closed" not in {k for k, _ in red2})

# ⑨ живая база прогоном не изменилась — суд ПО СВОИМ СЛЕДАМ поимённо (карточка #804). Разница состояния
# файла не судится: чужая честная запись за время прогона её меняет, а свой след она может и пропустить.
UNCHECKED = 0
outcome, names, why = mezo_stand.traces_verdict(live_before, mezo_stand.ask_traces(LIVE_DB, MARKS, NEED))
said = "способ: по своим следам — " + mezo_stand.traces_words(outcome, names, why)
if outcome == "unknown":
    UNCHECKED += 1
    print("⏳ ⑨ живая база прогоном не изменилась: НЕ ПРОВЕРЕНО")
    print(f"   {said}; «следов нет» НЕ утверждается")
else:
    case("⑨ живая база прогоном не изменилась", outcome == "clean", said)

# ⑨-а/б/в/г ВСТРЕЧНЫЕ: тот же суд на подставной базе стенда — чужая запись, свои следы по одному, база
# недоступна; и пробные имена на самом стенде находятся все.
CARD = ("INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, done_when) "
        "VALUES (?,?,'т','open','normal','[]',?,'к')")
RULE = "INSERT INTO rules (rule_key, body, status, expiry_kind, expiry_cond) VALUES (?,'тело','active','until_event',?)"
for letter, title, ok, detail in mezo_stand.traces_counter_cases(
        judge_db, MARKS, NEED,
        foreign=[(CARD, ("OTHERROLE", "чужая карточка о другом", "OTHERROLE")),
                 (RULE, ("other-rule-of-a-neighbour", "чужое условие"))],
        own=[("карточка", CARD, ("ZZE", "пробная", "PROTO"), {"backlog.role"}),
             ("правило", RULE, ("zzexp-card-closed", "условие пробы"), {"backlog.role", "rules.rule_key"})],
        planted=db):
    case(f"⑨-{letter} {title}", ok, detail)

if UNCHECKED:
    print(f"⏳ НЕ ПРОВЕРЕНО: {UNCHECKED} — база не ответила; прогон выходит кодом 2, а не «прошёл»")
print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(mezo_stand.exit_code3(FAIL, UNCHECKED)))
