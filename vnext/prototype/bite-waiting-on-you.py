# -*- coding: utf-8 -*-
r"""
bite-waiting-on-you.py — приёмка карточки #471: раздел «ТЕБЯ ЖДУТ» и его встречная
половина «ТЫ СДАЛ» в стартовой сводке роли (role-brief.py). На КОПИИ живой базы
(mezo_stand); живая база только читается.

ПОЧЕМУ ЭТА ПРИЁМКА СУЩЕСТВУЕТ ОТДЕЛЬНО ОТ bite-pool-brief: та судит СБОРКУ наказа
(целы ли источники, называется ли поломка). Эта судит ОТБОР — то, чего сборка не видит:
раздел, честно собравшийся и показавший не то, зелен у неё и лжёт роли.

Случаи:
  ① роль с чужими упоминаниями → раздел есть, число сходится с прямым запросом к базе
  ② ВСТРЕЧНЫЙ (обязателен): подсадить чужую карточку, называющую роль → она ПОЯВЛЯЕТСЯ;
     убрать → ИСЧЕЗАЕТ. Раздел, печатающий одно и то же независимо от данных, зелен
     как ничего не нашедший
  ③ ВСТРЕЧНЫЙ: роль, которую не называет НИКТО → «ТЕБЯ НЕ ЖДЁТ НИКТО» СЛОВОМ.
     Молчание неотличимо от несобравшегося раздела — ровно класс, ради которого раздел заведён
  ④ порог: свыше 10 — строка остатка, и показанное + остаток = ВСЕГО (нет молчаливого усечения)
  ⑤ --waiting печатает ВЕСЬ список, строки остатка НЕТ
  ⑥ на приёмке — ПЕРВЫМИ: порядок по полю карточки, а не по номеру и не по алфавиту
  ⑦ «ТЫ СДАЛ»: своя карточка на приёмке видна; своих сдач нет → секции нет ВОВСЕ
     (ноль здесь норма дня, вечная строка была бы шумом — в отличие от ③)
  ⑧ ТРЕТИЙ ИСХОД: источник сломан (нет таблицы) → раздел НАЗЫВАЕТ поломку, не молчит
     и не роняет остальные секции. «НЕ СОБРАЛСЯ» обязан быть отличим от «не нашёл»
  ⑨ контроль: своих следов в ЖИВОЙ базе не оставлено — судится состоянием живой базы
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

ИСПЫТУЕМЫЙ = mezo_target.script("role-brief.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def brief(db, role, waiting=False):
    # 🩸 MEZO_CONTAINER передаётся НАМЕРЕННО (найдено прогоном 30.08 10:27 UTC).
    # Без него испытуемая копия, лежащая ВНЕ контейнера, не находит маркер базы вверх
    # по дереву и падает ДО первой строки наказа. Приёмка тогда краснеет 12 случаями
    # из 15 — и краснеет НЕ ПО СВОЕЙ ПРИЧИНЕ: контрольная пара (та же копия без поломки)
    # даёт ровно тот же результат. Такая приёмка «доказала» бы, что умеет краснеть,
    # ничего на самом деле не проверив.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
               MEZO_CONTAINER=str(mezo_paths.container_root()))
    cmd = [sys.executable, str(ИСПЫТУЕМЫЙ), "--role", role, "--db", str(db)]
    if waiting:
        cmd.append("--waiting")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def головное_число(out):
    """Число из шапки раздела — то, что роль ЧИТАЕТ, а не то, что мы предполагаем."""
    m = re.search(r"🫱 ТЕБЯ ЖДУТ: (\d+) ", out)
    return int(m.group(1)) if m else None


def показано(out):
    """Сколько карточек напечатано поимённо ВНУТРИ раздела (не во всём выводе)."""
    блок = out.split("🫱 ТЕБЯ ЖДУТ:", 1)
    if len(блок) < 2:
        return 0
    тело = блок[1].split("⚖️ мерка ШИРОКАЯ", 1)[0]
    return len(re.findall(r"^   карточка #", тело, re.M))


def остаток(out):
    m = re.search(r"… ещё (\d+) — python", out)
    return int(m.group(1)) if m else None


stand = mezo_stand.new("waiting-on-you-")
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)
con = sqlite3.connect(str(db))
# ⚖️ ZZW — роль-проба, чтобы не судить о механизме по живым данным, которые уедут
# под руками. ZZQ — роль, которую НЕ НАЗЫВАЕТ НИКТО (случай ③).
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZW','alive','проба ожиданий')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZQ','alive','проба пустоты')")
con.commit()


def прямой_запрос(конн, роль):
    """Мерка, НЕЗАВИСИМАЯ от испытуемого: тот же предмет, посчитанный своей рукой."""
    OPEN = ("open", "in_progress", "blocked", "awaiting_word", "in_review")
    ph = ",".join("?" * len(OPEN))
    строки = конн.execute(
        f"SELECT title, COALESCE(body_md,''), COALESCE(done_when,'') FROM backlog "
        f"WHERE status IN ({ph}) AND role <> ?", (*OPEN, роль)).fetchall()
    обо = re.compile(rf"(?<![A-Za-z]){re.escape(роль)}(?![A-Za-z])")
    return sum(1 for t, b, d in строки if обо.search(f"{t}\n{b}\n{d}"))


# ═══ ① число сходится с прямым запросом — на роли живого контура
rc, out = brief(db, "PROTO")
ожидалось = прямой_запрос(con, "PROTO")
case("① раздел собрался и число сходится с прямым запросом",
     rc == 0 and головное_число(out) == ожидалось and ожидалось > 0,
     f"в разделе {головное_число(out)} · прямым запросом {ожидалось}")
case("①-бис карточка #124 видна поимённо (та, что стоила 19 суток)",
     "карточка #124 [STUD" in out)

# ═══ ② ВСТРЕЧНЫЙ: подсадка появляется, снятие убирает
до = головное_число(out)
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
            "created_by, done_when) VALUES ('ZZW','подсадная: ждёт руки ZZWTARGET',"
            "'тело подсадной','open','normal','[]','PROTO','критерий')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZWTARGET','alive','мишень')")
con.commit()
rc2, out2 = brief(db, "ZZWTARGET")
case("② ВСТРЕЧНЫЙ: подсаженная чужая карточка ПОЯВИЛАСЬ в разделе мишени",
     rc2 == 0 and головное_число(out2) == 1 and "ZZW ·" in out2,
     f"в разделе мишени: {головное_число(out2)}")
con.execute("DELETE FROM backlog WHERE role='ZZW'")
con.commit()
rc3, out3 = brief(db, "ZZWTARGET")
case("② ВСТРЕЧНЫЙ (обратный ход): подсадку убрали — раздел её больше НЕ показывает",
     rc3 == 0 and головное_число(out3) is None and "ТЕБЯ НЕ ЖДЁТ НИКТО" in out3)
rc4, out4 = brief(db, "PROTO")
case("②-бис соседняя роль от подсадки и снятия НЕ изменилась",
     головное_число(out4) == до, f"было {до} · стало {головное_число(out4)}")

# ═══ ③ ВСТРЕЧНЫЙ: роль, которую не называет никто → СЛОВО, а не молчание
rc5, out5 = brief(db, "ZZQ")
case("③ ВСТРЕЧНЫЙ: никто не ждёт → сказано СЛОВОМ, молчания нет",
     rc5 == 0 and "ТЕБЯ НЕ ЖДЁТ НИКТО" in out5 and "это НЕ «раздел не собрался»" in out5)

# ═══ ④ порог: показанное + остаток = всего
rc6, out6 = brief(db, "STUD")
всего, пок, ост = головное_число(out6), показано(out6), остаток(out6)
case("④ порог: показано + остаток = ВСЕГО (молчаливого усечения нет)",
     всего is not None and пок == 10 and ост is not None and пок + ост == всего,
     f"всего {всего} · поимённо {пок} · остаток {ост}")
case("④-бис остаток называет КОМАНДУ, и она существует (не имя без пути)",
     "--waiting" in out6 and str(SCRIPTS.as_posix()) in out6)

# ═══ ⑤ --waiting печатает всё
rc7, out7 = brief(db, "STUD", waiting=True)
case("⑤ --waiting: список ЦЕЛИКОМ, строки остатка НЕТ",
     rc7 == 0 and показано(out7) == всего and остаток(out7) is None,
     f"поимённо {показано(out7)} из {всего}")

# ═══ ⑥ порядок: на приёмке — первыми
# 🩸 ПОРЯДОК ВСТАВКИ ЗДЕСЬ ЗНАЧИМ, и первая редакция этого случая НИЧЕГО НЕ РАЗЛИЧАЛА
# (поймано нарочной поломкой 30.08 10:28 UTC): сдача вставлялась ПЕРВОЙ и получала
# МЕНЬШИЙ номер, поэтому и верный отбор, и поломка «сортировать по номеру» давали
# один и тот же порядок. Случай был зелен при сломанном механизме.
# ⇒ древняя открытая идёт ПЕРВОЙ (меньший номер), сдача — ВТОРОЙ. Теперь отбор по полю
# и отбор по номеру дают РАЗНЫЙ ответ, и случай наконец различает.
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by,"
            " done_when, created_at) VALUES ('ZZW','древняя открытая про ZZQ','тело','open',"
            "'normal','[]','PROTO','критерий', datetime('now','-40 days'))")
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by,"
            " done_when, created_at) VALUES ('ZZW','свежая сдача про ZZQ','тело','in_review',"
            "'normal','[]','PROTO','критерий', datetime('now'))")
con.commit()
rc8, out8 = brief(db, "ZZQ")
тело8 = out8.split("🫱 ТЕБЯ ЖДУТ:", 1)[1] if "🫱 ТЕБЯ ЖДУТ:" in out8 else ""
первая = re.search(r"^   карточка #\d+ \[ZZW · (\w+)", тело8, re.M)
case("⑥ на приёмке — ПЕРВОЙ, хотя открытая старше на 40 суток",
     первая is not None and первая.group(1) == "in_review",
     f"первая строка: {первая.group(1) if первая else 'НЕТ'}")

# ═══ ⑦ «ТЫ СДАЛ»: есть — видно; нет — секции нет вовсе
rc9, out9 = brief(db, "ZZW")
case("⑦ «ТЫ СДАЛ»: своя карточка на приёмке видна",
     "📤 ТЫ СДАЛ, ЖДЁТ ЧУЖОЙ РУКИ: 1" in out9)
case("⑦-бис своих сдач нет → секции «ТЫ СДАЛ» НЕТ ВОВСЕ (ноль здесь норма, не редкость)",
     "📤 ТЫ СДАЛ" not in out5)

# ═══ ⑧ ТРЕТИЙ ИСХОД: источник сломан → назван, остальное живо
con.close()
db2 = stand / "broken.db"
shutil.copy(db, db2)
con2 = sqlite3.connect(str(db2))
con2.execute("DROP TABLE backlog")
con2.commit()
con2.close()
rc10, out10 = brief(db2, "PROTO")
case("⑧ ТРЕТИЙ ИСХОД: таблицы нет → «ИСТОЧНИК НЕ ПРОЧИТАН», а не пустой раздел",
     "тебя ждут: ИСТОЧНИК НЕ ПРОЧИТАН" in out10 and "🫱" not in out10)
case("⑧-бис остальные секции при этом ЖИВЫ (поломка одной не роняет наказ)",
     "ФОРМЫ ВЫЗОВА" in out10 and "СВОД" in out10)

# ═══ ⑨ контроль: живая база не тронута
живой = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы = живой.execute(
    "SELECT COUNT(*) FROM roles WHERE role IN ('ZZW','ZZQ','ZZWTARGET')").fetchone()[0]
следы += живой.execute("SELECT COUNT(*) FROM backlog WHERE role IN ('ZZW','ZZQ')").fetchone()[0]
живой.close()
case("⑨ контроль: СВОИХ следов в живой базе нет", следы == 0, f"найдено следов: {следы}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
