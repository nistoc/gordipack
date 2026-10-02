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

═══ ПУСТОЙ НОВЫЙ КОНТУР (карточка #667) ═══
Свежесобранный из пакета контур несёт одну роль COORD и пустой список задач. Прежде
случаи ①④⑤ стояли на ЖИВЫХ ролях контура Atlas (PROTO — ①, STUD с десятками ожиданий —
④⑤) и там краснели, хотя механизм цел: ждать роль было некому.
  · ④⑤ теперь судят роль-пробу ZZMANY: приёмка сама заводит на копии 13 чужих карточек,
    называющих её, — больше порога в 10, на ЛЮБОМ контуре одинаково (живые данные «уедут
    под руками» — тот же довод, по которому заведены ZZW и ZZQ).
  · ① по-прежнему судит роль PROTO на живых данных, если её кто-то ждёт; если не ждёт
    никто (пустой контур) — ту же роль-пробу ZZMANY, где среди 13 подходящих карточек
    подсажены и три НЕподходящие (закрытая · своя · имя внутри другого слова), чтобы
    сверка с прямым запросом что-то различала, а не сходилась на нуле.
  · ①-бис стои́т на КОНКРЕТНОЙ исторической карточке #124 живого контура — её нельзя
    подделать без потери предмета (подставная повторила бы уже измеренный случай ②).
    Нет карточки или она больше не ждёт PROTO — честное «⚪ не проверено» с причиной,
    итоговый код 2, если других провалов нет.
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

TARGET_TOOL = mezo_target.script("role-brief.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OPEN = ("open", "in_progress", "blocked", "awaiting_word", "in_review")
OK = FAIL = 0
SKIPPED = []


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def skip(name, reason):
    """Случай не мерится: предмета нет в контуре. Не провал и не «чисто» — третий исход."""
    SKIPPED.append(name)
    print(f"⚪ {name}")
    print(f"   пропущен: не проверено: {reason}")


def brief(db, role, waiting=False):
    # 🩸 MEZO_CONTAINER передаётся НАМЕРЕННО (найдено прогоном 30.08 10:27 UTC).
    # Без него испытуемая копия, лежащая ВНЕ контейнера, не находит маркер базы вверх
    # по дереву и падает ДО первой строки наказа. Приёмка тогда краснеет 12 случаями
    # из 15 — и краснеет НЕ ПО СВОЕЙ ПРИЧИНЕ: контрольная пара (та же копия без поломки)
    # даёт ровно тот же результат. Такая приёмка «доказала» бы, что умеет краснеть,
    # ничего на самом деле не проверив.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_ROLE="PROTO",
               MEZO_CONTAINER=str(mezo_paths.container_root()))
    cmd = [sys.executable, str(TARGET_TOOL), "--role", role, "--db", str(db)]
    if waiting:
        cmd.append("--waiting")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def header_count(out):
    """Число из шапки раздела — то, что роль ЧИТАЕТ, а не то, что мы предполагаем."""
    m = re.search(r"🫱 ТЕБЯ ЖДУТ: (\d+) ", out)
    return int(m.group(1)) if m else None


def shown_count(out):
    """Сколько карточек напечатано поимённо ВНУТРИ раздела (не во всём выводе)."""
    parts = out.split("🫱 ТЕБЯ ЖДУТ:", 1)
    if len(parts) < 2:
        return 0
    body = parts[1].split("⚖️ мерка ШИРОКАЯ", 1)[0]
    return len(re.findall(r"^   карточка #", body, re.M))


def remainder_count(out):
    m = re.search(r"… ещё (\d+) — python", out)
    return int(m.group(1)) if m else None


def mentions(role, text):
    return re.search(rf"(?<![A-Za-z]){re.escape(role)}(?![A-Za-z])", text) is not None


def direct_count(conn, role):
    """Мерка, НЕЗАВИСИМАЯ от испытуемого: тот же предмет, посчитанный своей рукой."""
    ph = ",".join("?" * len(OPEN))
    rows = conn.execute(
        f"SELECT title, COALESCE(body_md,''), COALESCE(done_when,'') FROM backlog "
        f"WHERE status IN ({ph}) AND role <> ?", (*OPEN, role)).fetchall()
    return sum(1 for t, b, d in rows if mentions(role, f"{t}\n{b}\n{d}"))


stand = mezo_stand.new("waiting-on-you-")
db = stand / "mezosync.db"
mezo_stand.snapshot_db(LIVE_DB, db)
con = sqlite3.connect(str(db))

# ⚪ ①-бис: предусловие снимается ДО любой подсадки — иначе своя карточка могла бы занять номер.
CARD124 = con.execute("SELECT role, status, title, COALESCE(body_md,''), COALESCE(done_when,'') "
                      "FROM backlog WHERE id=124").fetchone()
if CARD124 is None:
    CARD124_REASON = ("в контуре нет карточки #124 (пустой/свежий контур, карточка #667) — "
                      "случай стоит на исторической карточке живого контура Atlas")
elif CARD124[0] != "STUD" or CARD124[1] not in OPEN or not mentions("PROTO", "\n".join(CARD124[2:])):
    CARD124_REASON = (f"живой случай перекрыт законной работой ролей: карточка #124 сейчас "
                      f"[{CARD124[0]} · {CARD124[1]}] и роль PROTO не ждёт — по ней ждать больше некого")
else:
    CARD124_REASON = None

# ⚖️ ZZW — роль-проба, чтобы не судить о механизме по живым данным, которые уедут
# под руками. ZZQ — роль, которую НЕ НАЗЫВАЕТ НИКТО (случай ③).
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZW','alive','проба ожиданий')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZQ','alive','проба пустоты')")
# 🩹 ДОГОН (карточка #667): ZZMANY — роль-проба порога (④⑤ и запасная для ①), ZZV — автор
# её карточек. Отдельный автор, а не ZZW: карточки ZZW случай ② удаляет целиком.
MANY, MANY_WRITER, MANY_TOTAL = "ZZMANY", "ZZV", 13
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','проба порога')", (MANY,))
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES (?,'alive','автор проб порога')",
            (MANY_WRITER,))


def add_card(role, title, body, status, done_when):
    con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, created_by, "
                "done_when) VALUES (?,?,?,?,'normal','[]','PROTO',?)",
                (role, title, body, status, done_when))


for n in range(MANY_TOTAL):
    # имя роли — по очереди в заголовке, в теле и в критерии; статусы — все пять незакрытых
    where = n % 3
    add_card(MANY_WRITER,
             f"подсадная №{n + 1}" + (f": ждёт руки {MANY}" if where == 0 else ""),
             "тело подсадной" + (f", нужен ответ {MANY}" if where == 1 else ""),
             OPEN[n % len(OPEN)],
             "критерий" + (f": {MANY} подтвердила" if where == 2 else ""))
# три НЕподходящие: закрытая · своя карточка роли · имя внутри другого слова
add_card(MANY_WRITER, f"закрытая подсадная: ждала {MANY}", "тело", "done", "критерий")
add_card(MANY, f"своя карточка {MANY} про себя", "тело", "open", "критерий")
add_card(MANY_WRITER, f"подсадная про {MANY}X — другое имя", "тело", "open", "критерий")
con.commit()


# ═══ ① число сходится с прямым запросом — на роли живого контура, если её кто-то ждёт
live_expected = direct_count(con, "PROTO")
role1 = "PROTO" if live_expected > 0 else MANY
rc, out = brief(db, role1)
expected = live_expected if role1 == "PROTO" else direct_count(con, MANY)
case("① раздел собрался и число сходится с прямым запросом",
     rc == 0 and header_count(out) == expected and expected > 0
     and (role1 == "PROTO" or expected == MANY_TOTAL),
     f"роль {role1} ({'живые данные' if role1 == 'PROTO' else 'своя подсадка: PROTO не ждёт никто'})"
     f" · в разделе {header_count(out)} · прямым запросом {expected}")
if CARD124_REASON is None:
    out_proto = out if role1 == "PROTO" else brief(db, "PROTO")[1]
    case("①-бис карточка #124 видна поимённо (та, что стоила 19 суток)",
         "карточка #124 [STUD" in out_proto)
else:
    skip("①-бис карточка #124 видна поимённо (та, что стоила 19 суток)",
         CARD124_REASON + "; подделывать её нельзя: подставная повторила бы уже измеренный "
         "случай ②, а не сам исторический случай")

# ═══ ② ВСТРЕЧНЫЙ: подсадка появляется, снятие убирает
before_count = header_count(out)
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, "
            "created_by, done_when) VALUES ('ZZW','подсадная: ждёт руки ZZWTARGET',"
            "'тело подсадной','open','normal','[]','PROTO','критерий')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZWTARGET','alive','мишень')")
con.commit()
rc2, out2 = brief(db, "ZZWTARGET")
case("② ВСТРЕЧНЫЙ: подсаженная чужая карточка ПОЯВИЛАСЬ в разделе мишени",
     rc2 == 0 and header_count(out2) == 1 and "ZZW ·" in out2,
     f"в разделе мишени: {header_count(out2)}")
con.execute("DELETE FROM backlog WHERE role='ZZW'")
con.commit()
rc3, out3 = brief(db, "ZZWTARGET")
case("② ВСТРЕЧНЫЙ (обратный ход): подсадку убрали — раздел её больше НЕ показывает",
     rc3 == 0 and header_count(out3) is None and "ТЕБЯ НЕ ЖДЁТ НИКТО" in out3)
rc4, out4 = brief(db, role1)
case("②-бис соседняя роль от подсадки и снятия НЕ изменилась",
     header_count(out4) == before_count,
     f"роль {role1}: было {before_count} · стало {header_count(out4)}")

# ═══ ③ ВСТРЕЧНЫЙ: роль, которую не называет никто → СЛОВО, а не молчание
rc5, out5 = brief(db, "ZZQ")
case("③ ВСТРЕЧНЫЙ: никто не ждёт → сказано СЛОВОМ, молчания нет",
     rc5 == 0 and "ТЕБЯ НЕ ЖДЁТ НИКТО" in out5 and "это НЕ «раздел не собрался»" in out5)

# ═══ ④ порог: показанное + остаток = всего
# 🩹 ДОГОН (карточка #667): прежде здесь стояла живая роль STUD (60 ожиданий на живом
# контуре, ноль — на пустом). Роль-проба ZZMANY несёт 13 подсадных при пороге 10 на любом контуре.
rc6, out6 = brief(db, MANY)
total, shown, rest = header_count(out6), shown_count(out6), remainder_count(out6)
case("④ порог: показано + остаток = ВСЕГО (молчаливого усечения нет)",
     total == MANY_TOTAL and shown == 10 and rest is not None and shown + rest == total,
     f"роль {MANY}: всего {total} из подсаженных {MANY_TOTAL} · поимённо {shown} · остаток {rest}")
case("④-бис остаток называет КОМАНДУ, и она существует (не имя без пути)",
     "--waiting" in out6 and str(SCRIPTS.as_posix()) in out6)

# ═══ ⑤ --waiting печатает всё
rc7, out7 = brief(db, MANY, waiting=True)
case("⑤ --waiting: список ЦЕЛИКОМ, строки остатка НЕТ",
     rc7 == 0 and shown_count(out7) == total and remainder_count(out7) is None,
     f"поимённо {shown_count(out7)} из {total}")

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
body8 = out8.split("🫱 ТЕБЯ ЖДУТ:", 1)[1] if "🫱 ТЕБЯ ЖДУТ:" in out8 else ""
first_row = re.search(r"^   карточка #\d+ \[ZZW · (\w+)", body8, re.M)
case("⑥ на приёмке — ПЕРВОЙ, хотя открытая старше на 40 суток",
     first_row is not None and first_row.group(1) == "in_review",
     f"первая строка: {first_row.group(1) if first_row else 'НЕТ'}")

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
live_conn = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
traces = live_conn.execute(
    "SELECT COUNT(*) FROM roles WHERE role IN ('ZZW','ZZQ','ZZWTARGET','ZZMANY','ZZV')").fetchone()[0]
traces += live_conn.execute(
    "SELECT COUNT(*) FROM backlog WHERE role IN ('ZZW','ZZQ','ZZMANY','ZZV')").fetchone()[0]
live_conn.close()
case("⑨ контроль: СВОИХ следов в живой базе нет", traces == 0, f"найдено следов: {traces}")

if FAIL:
    print(f"\n🔴 ИТОГ: {OK} из {OK + FAIL}")
    code = 1
elif SKIPPED:
    # ⚖️ ТРИ ИСХОДА, НЕ ДВА: непроверенное — не провал, но и не «всё чисто».
    print(f"\n⚪ ИТОГ: {OK} из {OK} проверенных · не проверено {len(SKIPPED)}: " + " · ".join(SKIPPED))
    code = 2
else:
    print(f"\n✅ ИТОГ: {OK} из {OK}")
    code = 0
sys.exit(mezo_stand.finish(code))
