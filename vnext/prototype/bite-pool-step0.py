# -*- coding: utf-8 -*-
r"""
bite-pool-step0.py — приёмка шага 0 пула: «карточки пула первыми, статус тем же вызовом»
(карточка #348, пул TRACK-ROLES-REMEMBER, план snuggly-sniffing-planet.md).

ЧТО СУДИТСЯ (на КОПИИ живой базы, mezo_stand):
  ① карточка пула стоит ПЕРВОЙ в `backlog.py list`, хотя срочность у неё НИЖЕ соседней
  ② то же в обзоре пробуждения (backlog_view.reminder_lines)                РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ: у роли без карточек пула — СЛОВА «в пуле … твоих карточек нет»,
     а не пустая секция (класс «молчащий отказ читается как успех»)
  ④ ВСТРЕЧНЫЙ-2: активного пула НЕТ вовсе — строки про пул НЕТ (вечный заголовок слепит),
     порядок прежний: срочность, номер
  ⑤ закрытие карточки пула (done) пишет role_status ТЕМ ЖЕ вызовом            РАЗЛИЧАЮЩИЙ
  ⑥ ВСТРЕЧНЫЙ: закрытие карточки ВНЕ пула role_status НЕ трогает
  ⑦ ВСТРЕЧНЫЙ-2: ПРОМЕЖУТОЧНАЯ смена (in_progress) карточки пула статус НЕ трогает
  ⑧ карточки вне пула НЕ перепривязаны: parent_track всех посторонних карточек
     после всех прогонов побайтно тот же
  ⑨ ОБРАТНЫЙ ХОД: в копии backlog.py пул-ветка ключа сортировки ослаблена —
     случай ① обязан ПОКРАСНЕТЬ (карточка пула тонет)                        РАЗЛИЧАЮЩИЙ
  ⑩ контроль: в живой базе НЕТ следов этой приёмки. Суд — ПО СВОИМ СЛЕДАМ ПОИМЁННО (строки с пробными
     именами: роли ZZR/ZZEMPTY, пул TRACK-ZZPROBE-POOL; вопрос — mezo_stand.traces, все столбцы всех
     таблиц, точное совпадение; судится ПРИБАВКА следов, прежние — чужая история), а не по разнице
     состояния файла: честная запись соседей в живую базу этот случай не краснит (карточка #483). Три встречных:
     ⑩-а чужая запись случай НЕ роняет · ⑩-б свой след роняет и назван поимённо ·
     ⑩-в база недоступна — третий исход «НЕ ПРОВЕРЕНО» (свои слова, код выхода 2)
     Встречные идут на копии живой базы внутри песочницы, настоящая живая база там не пишется.

СУД — ПО ПОДСАЖЕННОМУ КЛЮЧУ (роль ZZR, пул TRACK-ZZPROBE-POOL), не по общему исходу:
краснота от чужих карточек сюда не доедет (урок bite-launcher-forms 27.08).
Песочница НОРМАЛИЗУЕТСЯ: чужие пулы паузятся, аренды чистятся — приёмка меряет механизм,
а не текущее состояние контура. Живой инвариант «активный пул ровно один» этой приёмкой
НЕ судится: сегодня их два, и судьба TRACK-NEWUX — слово владельца; замер печатается
СПРАВКОЙ в конце, чтобы не красить механизм чужим решением.
"""
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

# Пути ВЫВОДЯТСЯ, не впечатаны (карточка #153): впечатанный путь — диск автора
# в публичном образце, у чужого механизм мёртв. Первый прогон гарда путей это
# пропустил ПО СЛЕПОТЕ: файл ещё не был в git ls-files — зелёное не по своей причине.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402 — испытуемое через общий выбор копии (карточка #682)

SCRIPTS = mezo_target.scripts_root()
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


def run(script, *args, db):
    # Среда стенда (карточка #613): MEZO_CONTAINER — корень стенда (каталог копии базы), номер
    # чата испытуемому не передаётся. Прежде backlog.py получал среду вызывающего: --db вёл в
    # копию, а то, что инструмент ищет по корню контура, — в живой контур. Копия лежит в корне
    # стенда (mezosync.db), а не в его .mezosync — живой базой она не становится.
    env = mezo_stand.stand_env(Path(db).parent, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(script), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def first_card_line(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith("🎯#"):
            return s
    return ""


# ═══ СУД ПО СВОИМ СЛЕДАМ (карточка #483) ═══════════════════════════════════════════════
# Пробные имена, которые эта приёмка сеет в копию: роли, пул. Карточки 9001–9004 живут под этими же
# ролями и пулом, поэтому числовых меток не нужно (число 9001 однажды станет чужим номером записки).
PROBE_MARKS = ("ZZR", "ZZEMPTY", "TRACK-ZZPROBE-POOL")


def ask_traces(path):
    """Спросить базу о своих следах: (словарь «таблица.столбец» → число строк, "") либо (None, причина).
    Общий вопрос — mezo_stand.traces: база открыта ТОЛЬКО на чтение (mode=ro), совпадение точное.
    Не открылась или не ответила — (None, причина): молчание базы нельзя читать как чистоту."""
    try:
        con = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        try:
            have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        lacking = {"backlog", "backlog_events", "role_status", "tracks"} - have
        if lacking:                      # пустой или чужой файл: вопрос о следах задать не на чем
            return None, "в базе нет таблиц: " + ", ".join(sorted(lacking))
        return mezo_stand.traces(path, PROBE_MARKS), ""
    except (sqlite3.Error, OSError) as e:
        return None, f"{type(e).__name__}: {e}"[:120]


def own_traces(before, after):
    """Три исхода: ("clean", [], "") · ("traces", [имена], "") · ("unknown", [], причина).
    Судится ПРИБАВКА своих следов между двумя вопросами (прежние строки — чужая история),
    а не разница состояния файла."""
    for found, why in (before, after):
        if found is None:
            return "unknown", [], why
    grown = sorted(f"{k} +{n - before[0].get(k, 0)}" for k, n in after[0].items() if n > before[0].get(k, 0))
    return ("traces" if grown else "clean"), grown, ""


def traces_words(outcome, names, why):
    """Слова каждого исхода — разные, чтобы третий не читался как первый."""
    if outcome == "clean":
        return "своих следов в базе нет"
    if outcome == "traces":
        return "СЛЕДЫ ЕСТЬ: " + ", ".join(names)
    return f"НЕ ПРОВЕРЕНО: база не ответила на вопрос о следах ({why})"


def exit_code(fail, unchecked):
    """Код выхода приёмки: провал — 1, часть не проверена — 2, иначе 0. Все три различны."""
    return 1 if fail else (2 if unchecked else 0)


# Первое обращение к базе контура — до стенда и до копии (карточка #804): база не читается вовсе
# (файла нет · файл не база · в файле нет ни одной таблицы) — третий исход своим кодом 2, ни один
# случай не судится. Без этой проверки пустой файл на месте базы давал трассировку «no such table»
# и код 1 (замер 22.11.2026): библиотека открывает его как базу без таблиц, и копия снималась.
blind = mezo_stand.base_unreadable(LIVE_DB)
if blind:
    print(f"⏳ НЕ ПРОВЕРЕНО: база контура недоступна с начала прогона ({blind})")
    print(f"   база: {LIVE_DB}")
    print("   стенд снять не с чего, ни один случай не судился; прогон выходит кодом 2, а не «прошёл»")
    raise SystemExit(mezo_stand.finish(2))

stand = mezo_stand.new("pool-step0-")
db = stand / "mezosync.db"
mezo_stand.snapshot_db(LIVE_DB, db)
# Чистая копия для встречных случаев ⑩-а/б/в: снимается ДО подсадок приёмки, из стенда, без
# обращения к живой базе во второй раз.
judge_db = stand / "judge.db"
shutil.copyfile(db, judge_db)
traces_before = ask_traces(LIVE_DB)

con = sqlite3.connect(str(db))
# НОРМАЛИЗАЦИЯ ПЕСОЧНИЦЫ: чужие пулы в паузу, аренды прочь (в копии живёт и моя аренда
# на backlog.py — писать через неё пришлось бы чужим именем, а приёмка не роль).
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status) VALUES "
            "('TRACK-ZZPROBE-POOL','подсаженный пул приёмки','active')")
try:
    con.execute("DELETE FROM leases")
except sqlite3.OperationalError:
    pass
# Подсадка: у ZZR карточка ПУЛА нарочно МЕНЕЕ срочная (normal) и МОЛОЖЕ (id больше),
# чем посторонняя critical, — старый порядок поставил бы её ВТОРОЙ.
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9001,'ZZR','посторонняя срочная','open','critical','есть',NULL)")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9002,'ZZR','карточка пула','open','normal','есть','TRACK-ZZPROBE-POOL')")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9003,'ZZEMPTY','вне пула','open','high','есть',NULL)")
con.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
            "VALUES (9004,'ZZR','вторая карточка пула на закрытие','open','low','есть',"
            "'TRACK-ZZPROBE-POOL')")
outside_before = con.execute(
    "SELECT id, COALESCE(parent_track,'') FROM backlog "
    "WHERE id NOT IN (9001,9002,9003,9004) ORDER BY id").fetchall()
con.commit()
con.close()

# ① пул первым в list — вопреки срочности
_, out = run(SCRIPTS / "backlog.py", "list", "--role", "ZZR", db=db)
case("① карточка пула первой в list, хотя срочность ниже",
     "#9002" in first_card_line(out), f"первая строка: {first_card_line(out)[:80]}")

# ② то же в обзоре пробуждения
import importlib  # noqa: E402
sys.path.insert(0, str(SCRIPTS))
import backlog_view  # noqa: E402
importlib.reload(backlog_view)
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
lines = backlog_view.reminder_lines(conn, "ZZR")
card_lines = [l for l in lines if l.strip().startswith(("#", "🎯#"))]
case("② карточка пула первой в обзоре пробуждения",
     card_lines and "#9002" in card_lines[0], f"первая: {card_lines[0][:80] if card_lines else '—'}")
case("② шапка называет пул словами",
     any("пул" in l and "TRACK-ZZPROBE-POOL" in l for l in lines))

# ③ роль без карточек пула — слова, не пустая секция
lines3 = backlog_view.reminder_lines(conn, "ZZEMPTY")
case("③ без карточек пула — слова «твоих карточек нет»",
     any("в пуле" in l and "нет" in l for l in lines3),
     " / ".join(l.strip() for l in lines3[:2]))
conn.close()
_, out3 = run(SCRIPTS / "backlog.py", "list", "--role", "ZZEMPTY", db=db)
case("③ то же в list", "твоих карточек нет" in out3)

# ④ встречный-2: пула нет вовсе — строки про пул нет, порядок прежний
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE track_id='TRACK-ZZPROBE-POOL'")
con.commit()
con.close()
_, out4 = run(SCRIPTS / "backlog.py", "list", "--role", "ZZR", db=db)
case("④ пула нет — строки про пул НЕТ (вечный заголовок слепил бы)",
     "в пуле" not in out4 and "пул TRACK" not in out4)
case("④ и порядок прежний: срочность первой", "#9001" in first_card_line(out4),
     f"первая строка: {first_card_line(out4)[:80]}")
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='active' WHERE track_id='TRACK-ZZPROBE-POOL'")
con.commit()
con.close()

# ⑤ закрытие карточки пула пишет role_status тем же вызовом
rc, out5 = run(SCRIPTS / "backlog.py", "status", "9004", "done",
               "--actor", "ZZR", "--note", "проба закрытия", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
row = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()
case("⑤ done по карточке пула → role_status записан тем же вызовом",
     rc == 0 and row and "#9004" in row[0] and "TRACK-ZZPROBE-POOL" in row[0],
     (row[0][:100] if row else f"строки нет; rc={rc}"))
case("⑤ и вызов сам сказал об этом", "тем же вызовом" in out5.lower() or "ТЕМ ЖЕ" in out5)

# ⑥ встречный (ПЕРЕПИСАН 28.08 заходом 2.2): закрытие ВНЕ пула теперь ТОЖЕ пишет
# статус (закрытие — событие «чем занята роль»), но БЕЗ пометки пула. Различие
# пул/не-пул живёт в ТЕКСТЕ статуса, а не в факте записи.
rc6, _ = run(SCRIPTS / "backlog.py", "status", "9003", "done", "--actor", "ZZEMPTY", db=db)
row6 = con.execute("SELECT status FROM role_status WHERE role='ZZEMPTY'").fetchone()
case("⑥ done вне пула → статус записан БЕЗ пометки пула (2.2)",
     rc6 == 0 and row6 and "#9003" in row6[0] and "(пул " not in row6[0],
     (row6[0][:90] if row6 else "записи нет"))

# ⑦ встречный-2: промежуточная смена карточки пула статус не трогает
before7 = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()[0]
con.close()
run(SCRIPTS / "backlog.py", "status", "9002", "in_progress", "--actor", "ZZR", db=db)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
after7 = con.execute("SELECT status FROM role_status WHERE role='ZZR'").fetchone()[0]
case("⑦ in_progress по карточке пула → role_status НЕ переписан", before7 == after7)

# ⑧ посторонние карточки не перепривязаны
outside_after = con.execute(
    "SELECT id, COALESCE(parent_track,'') FROM backlog "
    "WHERE id NOT IN (9001,9002,9003,9004) ORDER BY id").fetchall()
case("⑧ parent_track посторонних карточек не тронут прогоном",
     outside_before == outside_after, f"карточек сверено: {len(outside_after)}")
con.close()

# ⑨ ОБРАТНЫЙ ХОД: ослабить пул-ветку ключа в КОПИИ backlog.py → ① краснеет
weak_dir = stand / "weak"
weak_dir.mkdir()
for name in ("backlog.py", "mezo_paths.py", "dryrun.py", "refs_check.py", "backlog_view.py"):
    shutil.copy(SCRIPTS / name, weak_dir / name)
src = (weak_dir / "backlog.py").read_text(encoding="utf-8")
ANCHOR = "return (0 if (pools and r[-1] in pools) else 1,"
if ANCHOR not in src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь пул-ветки ключа не найден в backlog.py — "
                     "обратный ход ⑨ ослаблять нечего, случаи выше могли зеленеть не тем кодом")
(weak_dir / "backlog.py").write_text(src.replace(ANCHOR, "return (1,"), encoding="utf-8")
_, out9 = run(weak_dir / "backlog.py", "list", "--role", "ZZR", db=db)
case("⑨ обратный ход: ключ ослаблен → карточка пула БОЛЬШЕ НЕ первая (① краснеет)",
     "#9002" not in first_card_line(out9), f"первая строка: {first_card_line(out9)[:80]}")

# ⑩ в живой базе нет следов приёмки — суд ПО СВОИМ СЛЕДАМ поимённо (карточка #483).
# Разница состояния файла не судится: чужая честная запись в базу за время прогона её меняет.
# Прежние следы (до прогона) — чужая история: судится ПРИБАВКА между двумя вопросами к базе.
UNCHECKED = 0
outcome, names, why = own_traces(traces_before, ask_traces(LIVE_DB))
note = ""
if traces_before[0]:
    note = f" · следов до прогона (не в счёт): {sum(traces_before[0].values())}"
if outcome == "unknown":
    UNCHECKED += 1
    print("⏳ ⑩ живая база прогоном не тронута: НЕ ПРОВЕРЕНО")
    print(f"   способ: по своим следам — {traces_words(outcome, names, why)}; «следов нет» НЕ утверждается")
else:
    case("⑩ живая база прогоном не тронута", outcome == "clean",
         f"способ: по своим следам — {traces_words(outcome, names, why)}{note}")

# ⑩-а ВСТРЕЧНЫЙ, главный: чужая запись в базу между началом и концом прогона случай НЕ роняет.
# Подсадка — в копии (judge.db), а суд — те же правила: тот же вопрос о следах, другая база.
jbase = ask_traces(judge_db)
jcon = sqlite3.connect(str(judge_db))
jcon.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
             "VALUES (8999,'OTHERROLE','чужая записка о другом','open','normal','есть',NULL)")
jcon.execute("INSERT INTO role_status (role, status, updated_at) "
             "VALUES ('OTHERROLE','чужая работа','2026-01-01 00:00:00')")
jcon.commit()
foreign_rows = jcon.execute("SELECT (SELECT count(*) FROM backlog WHERE id=8999),"
                            "(SELECT count(*) FROM role_status WHERE role='OTHERROLE')").fetchone()
jcon.close()
o_a, n_a, w_a = own_traces(jbase, ask_traces(judge_db))
case("⑩-а чужая запись в «живую» базу между началом и концом прогона случай НЕ роняет",
     jbase[0] is not None and foreign_rows == (1, 1) and o_a == "clean",
     f"чужих строк записано (карточка, статус роли): {foreign_rows}; суд: {traces_words(o_a, n_a, w_a)}")

# ⑩-б ВСТРЕЧНЫЙ к ⑩-а: свой след роняет и назван поимённо. Следы добавляются по одному ПОВЕРХ
# чужой записи: каждый шаг называет ровно накопленное, чужая строка в имена не попадает.
jcon = sqlite3.connect(str(judge_db))
steps = []


def step(label, want):
    jcon.commit()
    o, n, _ = own_traces(jbase, ask_traces(judge_db))
    steps.append((label, o, n, want))


jcon.execute("INSERT INTO backlog (id, role, title, status, priority, done_when, parent_track) "
             "VALUES (9001,'ZZR','пробная карточка','open','critical','есть',NULL)")
step("карточка", {"backlog.role"})
jcon.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type) "
             "VALUES (9001,'2026-01-01 00:00:00','ZZR','status')")
step("событие", {"backlog.role", "backlog_events.actor_role"})
jcon.execute("INSERT INTO role_status (role, status, updated_at) VALUES ('ZZEMPTY','проба','2026-01-01 00:00:00')")
step("статус роли", {"backlog.role", "backlog_events.actor_role", "role_status.role"})
jcon.execute("INSERT INTO tracks (track_id, title, status) VALUES ('TRACK-ZZPROBE-POOL','проба','paused')")
step("пул", {"backlog.role", "backlog_events.actor_role", "role_status.role", "tracks.track_id"})
jcon.close()
bad = [lab for lab, o, n, want in steps if not (o == "traces" and {x.split(" +")[0] for x in n} == want)]
case("⑩-б свой след в «живой» базе случай РОНЯЕТ и назван поимённо",
     not bad, f"шагов {len(steps)}; на последнем: {traces_words('traces', steps[-1][2], '')}"
     + (f" · НЕ ТО на шагах: {bad}" if bad else ""))

# ⑩-в ТРЕТИЙ ИСХОД: база недоступна — не «следов нет», слова и код свои.
gone = stand / "нет-такой-базы.db"
garbage = stand / "битая-база.db"
garbage.write_bytes("это не база данных, а просто текст".encode("utf-8") * 8)
empty = stand / "пустая-база.db"
empty.write_bytes(b"")
unknown_runs = {p.name: own_traces(jbase, ask_traces(p)) for p in (gone, garbage, empty)}
clean_words = traces_words("clean", [], "")
trace_words = traces_words("traces", ["backlog.role +1"], "")
words_ok = all(
    r[0] == "unknown" and "НЕ ПРОВЕРЕНО" in traces_words(*r)
    and traces_words(*r) != clean_words and "нет" not in traces_words(*r).split("(")[0]
    for r in unknown_runs.values())
codes = (exit_code(0, 0), exit_code(1, 0), exit_code(0, 1))
case("⑩-в база недоступна — третий исход «НЕ ПРОВЕРЕНО»: свои слова и свой код, не «следов нет»",
     words_ok and "НЕ ПРОВЕРЕНО" not in clean_words and "НЕ ПРОВЕРЕНО" not in trace_words
     and len(set(codes)) == 3 and codes[2] == 2,
     "исходы: " + ", ".join(f"{k}→{v[0]}" for k, v in unknown_runs.items())
     + f"; коды (следов нет / следы есть / не проверено): {codes}")

if UNCHECKED:
    print(f"⏳ НЕ ПРОВЕРЕНО: {UNCHECKED} — база не ответила; прогон выходит кодом 2, а не «прошёл»")
print(f"\nИТОГ: {OK}/{OK + FAIL}")

# СПРАВКА (не случай): живой инвариант «активный пул ровно один» — решение владельца
try:
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    active_pools = [r[0] for r in con.execute("SELECT track_id FROM tracks WHERE status='active'")]
    con.close()
except sqlite3.Error:
    active_pools = None                      # база не ответила — справка пропускается, случаи это уже сказали
if active_pools is not None and len(active_pools) != 1:
    print(f"⏳ СПРАВКА: активных пулов в ЖИВОЙ базе {len(active_pools)} ({', '.join(active_pools)}) — "
          f"норма нового порядка: ОДИН; судьба лишнего — слово владельца, механизм это "
          f"печатает сам в каждом list")
raise SystemExit(mezo_stand.finish(exit_code(FAIL, UNCHECKED)))
