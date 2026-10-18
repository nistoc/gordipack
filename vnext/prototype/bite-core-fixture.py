# -*- coding: utf-8 -*-
r"""
bite-core-fixture.py — приёмка подставной базы приёмок ядра (этап Э6, карточка #680).

ЗАЧЕМ. Приёмки ядра судили инструмент на копии живой базы — на строках ЭТОГО контура.
Проба 17–18.10 (61 приёмка): итог зависел от ленты, памяти и карточек контура, а копия весила
≈96 МБ на стенд. Подставная база (mezo_stand.empty_db) — схема живой базы без строк; строки
сажает сама приёмка. План — atlas.archs/.mezosync/goal-gordi-core/e6/plan-proto.md, §3.
Эта приёмка судит три вещи: сам помощник (empty_db, seed_roles, traces), список приёмок ядра
(core-bites.txt) и — с флагом --run — что переведённые приёмки судят столько же, сколько до
перевода.

Случаи:
  ① подставная из живой: схема (sqlite_master целиком) — как у живой
  ② строк нет ни в одной таблице, кроме schema_migrations; там — столько же, сколько в живой
  ③ размер страницы, user_version, режим журнала — как у живой
  ④ стенд с подставной базой ≤ 2 МБ (критерий плана, §5)
  ⑤ keep: строки таблицы из keep — те же по содержимому, остальные пусты; новый номер строки
     идёт после прежних (счётчик AUTOINCREMENT перенесён)
  ⑥ поиск по таблице полнотекстового поиска находит скопированные строки, а триггер — новую;
     ВСТРЕЧНЫЙ: без keep поиск пуст; ОБРАТНЫЙ ХОД: в копии помощника без 'rebuild' поиск пуст
  ⑦ источник не тронут: байты файла базы и её журнала до и после — те же
  ⑧ keep с видом, виртуальной таблицей или опечаткой — отказ с именем, цель не создана
  ⑨ цель — существующая база: заменена целиком; цель — не база: отказ, файл не тронут
  ⑩ seed_roles: реестр ролей и отметка прочитанного; повтор не дублирует; имя не в верхнем
     регистре, короче 2 или длиннее 16 знаков — отказ, а не молчаливый пропуск
  ⑪ traces: своя метка в строке видна, та же метка внутри текста — нет (совпадение точное)
  ⑫ список core-bites.txt читается: у каждой строки имя существующего файла, группа, состояние
  ⑬ переведённые (done): нет ни snapshot_db с живой базой, ни копии backup(), есть empty_db;
     ОБРАТНЫЙ ХОД: копия переведённой приёмки с возвращённым snapshot_db — провал с её именем
  ⑭ переведённые: случай «живая база не тронута» не сличает размер и время файла живой базы
     (их меняет любая чужая запись, карточка #483)
  ⑮ (только --run) каждая переведённая приёмка: код, число ✅ и 🔴 — как «было» в списке
  ⑯ свои (own): копию живой базы не берут вовсе — ни snapshot_db с живой базой, ни backup()
  ⑰ bite-all.py --set core на подложенном каталоге (четыре строки списка, пятая приёмка вне списка):
     совпало 1 · разошлось 1 · не запустилось 2 (потолок времени, файла нет), код 1, приёмка вне
     списка не запущена; неверная строка списка — отказ кодом 2 с её номером;
     ОБРАТНЫЙ ХОД: копия bite-all.py без сверки с «было» — «разошлось 0», поломка видна

«С живой базой» — первый аргумент snapshot_db, в тексте которого есть «live» (любой регистр) или
это имя src. ⚖️ Граница: живая база под другим именем этой проверке не видна; snapshot_db со
своей базой (например, свежего контура) — законен и не считается.

Флаги: --run — прогнать переведённые приёмки по одной (долго: минуты на каждую); --list ФАЙЛ —
другой список (для проверки самой приёмки).
"""
import argparse
import ast
import hashlib
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
# mezo_stand — из каталога самой приёмки: судится помощник той же версии пакета, что и приёмка
# (scripts/ живого контура до установки выпуска — прежней версии, empty_db там нет)
import mezo_stand  # noqa: E402

LIVE_DB = mezo_paths.live_db()

ap = argparse.ArgumentParser(description="приёмка подставной базы приёмок ядра (Э6)")
ap.add_argument("--run", action="store_true", help="прогнать переведённые приёмки и сверить числа «было»")
ap.add_argument("--list", default=str(HERE / "core-bites.txt"), help="список приёмок ядра")
args = ap.parse_args()

OK = FAIL = 0
SIZE_LIMIT = 2 * 1024 * 1024


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def ro(db):
    return sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)


def refused(fn):
    """Отказ помощника — SystemExit с текстом; вернуть текст или None, если отказа не было."""
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


def file_hash(*paths):
    """Отпечаток байтов файлов. Нет файла — как пустой: чтение базы в режиме WAL само заводит
    пустой журнал рядом (проба 18.10 09:32 UTC: «нет» → 0 байт), и это не запись в источник."""
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes() if p.exists() else b"")
        h.update(b"\0")
    return h.hexdigest()


stand = mezo_stand.new("core-fixture-")

# ── ①–④ подставная из живой базы ────────────────────────────────────────────────────────
part = stand / "empty"
part.mkdir()
e = mezo_stand.empty_db(LIVE_DB, part / "mezosync.db")
lc = ro(LIVE_DB)
ec = ro(e)
live_schema = set(lc.execute("SELECT type, name, tbl_name, sql FROM sqlite_master"))
empty_schema = set(ec.execute("SELECT type, name, tbl_name, sql FROM sqlite_master"))
case("① схема подставной — как у живой (sqlite_master целиком)", live_schema == empty_schema,
     f"объектов в живой {len(live_schema)} · в подставной {len(empty_schema)} · "
     f"различий {len(live_schema ^ empty_schema)}")
with_rows = []
for (name,) in ec.execute("SELECT name FROM pragma_table_list WHERE type='table' "
                          "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
    n = ec.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    if n:
        with_rows.append((name, n))
live_steps = lc.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
case("② строк нет нигде, кроме schema_migrations; там — как в живой",
     [t for t, _ in with_rows] == ["schema_migrations"] and dict(with_rows)["schema_migrations"] == live_steps,
     f"таблицы со строками: {with_rows} · шагов в живой {live_steps}")
pr = ("page_size", "user_version", "journal_mode")
lp = {p: lc.execute(f"PRAGMA {p}").fetchone()[0] for p in pr}
ep = {p: ec.execute(f"PRAGMA {p}").fetchone()[0] for p in pr}
case("③ размер страницы, user_version, режим журнала — как у живой", lp == ep, f"живая {lp} · подставная {ep}")
lc.close()
ec.close()
size = mezo_stand.stand_size(part)
case("④ стенд с подставной базой ≤ 2 МБ", size <= SIZE_LIMIT, f"{size / 1024 / 1024:.2f} МБ (с журналом)")

# ── ⑤–⑨ на своём источнике: малая база со всеми видами объектов ────────────────────────────
src = stand / "src.db"
sc = sqlite3.connect(str(src))
sc.executescript("""
PRAGMA journal_mode = wal;
CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT);
CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, who TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE other (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX notes_who ON notes(who);
CREATE VIEW notes_view AS SELECT who, count(*) AS n FROM notes GROUP BY who;
CREATE VIRTUAL TABLE notes_fts USING fts5(body, content='notes', content_rowid='id');
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid, body) VALUES (new.id, new.body); END;
INSERT INTO schema_migrations VALUES ('s1', '2026-10-18'), ('s2', '2026-10-18');
INSERT INTO notes (who, body) VALUES ('ZZA', 'кларнет первый'), ('ZZB', 'кларнет второй'), ('ZZA', 'фагот');
DELETE FROM notes WHERE body = 'фагот';
INSERT INTO other VALUES ('a', 'b');
PRAGMA user_version = 7;
""")
sc.commit()
sc.close()
src_files = [src, src.with_name("src.db-wal")]
src_before = file_hash(*src_files)

k = mezo_stand.empty_db(src, stand / "keep.db", keep=("notes",))
kc = sqlite3.connect(str(k))
rows_src = ro(src).execute("SELECT id, who, body FROM notes ORDER BY id").fetchall()
rows_keep = kc.execute("SELECT id, who, body FROM notes ORDER BY id").fetchall()
other_n = kc.execute("SELECT count(*) FROM other").fetchone()[0]
new_id = kc.execute("INSERT INTO notes (who, body) VALUES ('ZZC', 'гобой')").lastrowid
kc.commit()
case("⑤ keep: строки те же по содержимому, прочие таблицы пусты, номер новой строки — после прежних",
     rows_keep == rows_src and other_n == 0 and new_id == 4,
     f"notes {len(rows_keep)} из {len(rows_src)} · other {other_n} · номер новой {new_id} (ждали 4: «фагот» был 3-м)")
hits_kept = kc.execute("SELECT count(*) FROM notes_fts WHERE notes_fts MATCH 'кларнет'").fetchone()[0]
hits_new = kc.execute("SELECT count(*) FROM notes_fts WHERE notes_fts MATCH 'гобой'").fetchone()[0]
kc.close()
bare = mezo_stand.empty_db(src, stand / "bare.db")
bc = ro(bare)
hits_bare = bc.execute("SELECT count(*) FROM notes_fts WHERE notes_fts MATCH 'кларнет'").fetchone()[0]
bc.close()
# обратный ход: копия помощника без перестройки поиска — скопированные строки поиску не видны
weak_dir = stand / "weak"
weak_dir.mkdir()
weak_src = (Path(mezo_stand.__file__)).read_text(encoding="utf-8")
ANCHOR = "mem.execute(f\"INSERT INTO {_q(name)}({_q(name)}) VALUES ('rebuild')\")"
if ANCHOR not in weak_src:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь перестройки поиска в mezo_stand.py не найден — "
                     "обратный ход ⑥ судил бы не тот код")
(weak_dir / "mezo_stand_weak.py").write_text(weak_src.replace(ANCHOR, "pass"), encoding="utf-8")
spec = importlib.util.spec_from_file_location("mezo_stand_weak", weak_dir / "mezo_stand_weak.py")
weak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weak)
wk = weak.empty_db(src, stand / "weak.db", keep=("notes",))
wc = ro(wk)
hits_weak = wc.execute("SELECT count(*) FROM notes_fts WHERE notes_fts MATCH 'кларнет'").fetchone()[0]
wc.close()
case("⑥ поиск находит скопированные строки (2) и новую через триггер (1); без keep — 0; "
     "обратный ход: без 'rebuild' — 0",
     (hits_kept, hits_new, hits_bare, hits_weak) == (2, 1, 0, 0),
     f"скопированные {hits_kept} · новая {hits_new} · без keep {hits_bare} · без 'rebuild' {hits_weak}")
case("⑦ источник не тронут: байты базы и её журнала те же", file_hash(*src_files) == src_before)

bad_keep = []
for name in ("notes_view", "notes_fts", "notess"):
    target = stand / f"bad-{name}.db"
    msg = refused(lambda: mezo_stand.empty_db(src, target, keep=(name,)))
    bad_keep.append((name, msg is not None and name in msg, target.exists()))
case("⑧ keep с видом, виртуальной таблицей или опечаткой — отказ с именем, цель не создана",
     all(r and not ex for _, r, ex in bad_keep), f"{bad_keep}")

old = stand / "old.db"
oc = sqlite3.connect(str(old))
oc.execute("CREATE TABLE stale (x)")
oc.execute("INSERT INTO stale VALUES (1)")
oc.commit()
oc.close()
mezo_stand.empty_db(src, old)
tables_old = {r[0] for r in ro(old).execute("SELECT name FROM sqlite_master WHERE type='table'")}
text = stand / "not-a-db.db"
text.write_text("это не база\n", encoding="utf-8")
text_before = text.read_bytes()
msg = refused(lambda: mezo_stand.empty_db(src, text))
case("⑨ цель-база заменена целиком (прежней таблицы нет); цель не база — отказ, файл не тронут",
     "stale" not in tables_old and "notes" in tables_old and msg is not None
     and text.read_bytes() == text_before,
     f"таблицы цели {sorted(tables_old)} · отказ: {(msg or 'НЕТ').splitlines()[0]}")

# ── ⑩ seed_roles ───────────────────────────────────────────────────────────────────────
mezo_stand.seed_roles(e, ["ZZA", "ZZB"])
mezo_stand.seed_roles(e, ["ZZA"])
rc = ro(e)
roles = rc.execute("SELECT role, lifecycle, in_roster FROM roles ORDER BY role").fetchall()
reads = rc.execute("SELECT reader_role, last_read_id FROM read_cursors ORDER BY reader_role").fetchall()
rc.close()
bad_names = [(n, refused(lambda: mezo_stand.seed_roles(e, [n])) is not None)
             for n in ("zzc", "Z", "ZZSEVENTEENCHARSX")]
case("⑩ seed_roles: роли в реестре и с отметкой 0; повтор не дублирует; неверные имена — отказ",
     roles == [("ZZA", "alive", 1), ("ZZB", "alive", 1)] and reads == [("ZZA", 0), ("ZZB", 0)]
     and all(r for _, r in bad_names),
     f"реестр {roles} · отметки {reads} · отказы {bad_names}")

# ── ⑪ traces ───────────────────────────────────────────────────────────────────────────
t_db = stand / "keep.db"
before = mezo_stand.traces(t_db, ["ZZMARK"])
tc = sqlite3.connect(str(t_db))
tc.execute("INSERT INTO other VALUES ('ZZMARK', 'x')")
tc.execute("INSERT INTO other VALUES ('inside', 'текст про ZZMARK внутри')")
tc.commit()
tc.close()
after = mezo_stand.traces(t_db, ["ZZMARK"])
case("⑪ traces: своя метка в значении видна (1), внутри текста — нет",
     before == {} and after == {"other.k": 1}, f"до {before} · после {after}")

# ── ⑫–⑭ список приёмок ядра ─────────────────────────────────────────────────────────────
LIST = Path(args.list)
GROUPS = {"Г1", "Г2", "Г3", "Г2+Г3", "Г4"}
STATES = {"done", "wait", "own"}
entries, broken = [], []
for i, line in enumerate(LIST.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    parts = line.split()
    if (len(parts) != 6 or parts[1] not in GROUPS or parts[2] not in STATES
            or not all(re.fullmatch(r"-?\d+", p) for p in parts[3:])
            or not (HERE / parts[0]).is_file()):
        broken.append(f"строка {i}: {line.strip()[:80]}")
        continue
    entries.append({"name": parts[0], "group": parts[1], "state": parts[2],
                    "was": tuple(int(p) for p in parts[3:])})
done = [x for x in entries if x["state"] == "done"]
case("⑫ список приёмок ядра читается: имя существующего файла, группа, состояние, числа «было»",
     entries and not broken,
     f"{LIST.name}: приёмок {len(entries)} · переведено {len(done)} из {len(entries)}"
     + (f" · неверных строк {len(broken)}: {broken[:3]}" if broken else ""))


def calls(path):
    """Что приёмка зовёт: имена функций; сколько раз snapshot_db с живой базой (первый аргумент
    с «live» или src); сколько копий backup(); обращения X.stat() к живой базе (имя с «live»)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names, live_stat, live_snap, backups = set(), 0, 0, 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            names.add(name)
            if (name == "stat" and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and "live" in f.value.id.lower()):
                live_stat += 1
            if name == "snapshot_db" and node.args:
                arg = ast.unparse(node.args[0])
                if "live" in arg.lower() or arg == "src":
                    live_snap += 1
            if name == "backup" and isinstance(f, ast.Attribute):
                backups += 1
    return names, live_stat, live_snap, backups


def judge_done(items, folder):
    still, no_empty, by_stat = [], [], []
    for x in items:
        names, live_stat, live_snap, backups = calls(folder / x["name"])
        if live_snap or backups:
            still.append(x["name"])
        if "empty_db" not in names:
            no_empty.append(x["name"])
        if live_stat:
            by_stat.append(x["name"])
    return still, no_empty, by_stat


still, no_empty, by_stat = judge_done(done, HERE)
# обратный ход: копия первой переведённой приёмки с возвращённым snapshot_db
reverse_ok, reverse_detail = False, "переведённых нет — обратный ход не на чем ставить"
if done:
    probe = done[0]["name"]
    text_b = (HERE / probe).read_text(encoding="utf-8")
    if "mezo_stand.empty_db(" not in text_b:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в {probe} нет «mezo_stand.empty_db(» — обратный ход ⑬ не поставить")
    back = stand / "back"
    back.mkdir()
    (back / probe).write_text(text_b.replace("mezo_stand.empty_db(", "mezo_stand.snapshot_db(", 1),
                              encoding="utf-8")
    b_still, _, _ = judge_done([done[0]], back)
    reverse_ok = b_still == [probe]
    reverse_detail = f"копия {probe} со snapshot_db → названа: {b_still}"
case("⑬ переведённые: копии живой базы нет, empty_db есть; обратный ход — провал с именем приёмки",
     bool(done) and not still and not no_empty and reverse_ok,
     f"с копией живой: {still or 'нет'} · без empty_db: {no_empty or 'нет'} · {reverse_detail}")
case("⑭ переведённые: «живая база не тронута» не по размеру и времени файла (X.stat() у живой базы)",
     bool(done) and not by_stat, f"сличают файл живой базы: {by_stat or 'нет'}")
own = [x for x in entries if x["state"] == "own"]
own_bad = [x["name"] for x in own if any(calls(HERE / x["name"])[2:])]
case("⑯ свои (own): копию живой базы не берут — ни snapshot_db с живой, ни backup()",
     not own_bad, f"своих {len(own)} · с копией живой: {own_bad or 'нет'}")

# ── ⑰ bite-all.py --set core: строка на приёмку против «было» ─────────────────────────────
RUNNER = HERE / "bite-all.py"
planted = stand / "core-set"
planted.mkdir()
for name, body in (("bite-zz-one.py", 'print("✅ a")\nprint("✅ b")\n'),
                   ("bite-zz-two.py", 'print("✅ a")\nprint("🔴 b")\nraise SystemExit(1)\n'),
                   ("bite-zz-slow.py", 'import time\ntime.sleep(30)\n'),
                   ("bite-zz-extra.py", 'print("✅ вне списка")\n')):
    (planted / name).write_text(body, encoding="utf-8")
(planted / "core-bites.txt").write_text(
    "# подложенный список ⑰\n"
    "bite-zz-one.py Г1 done 0 2 0\n"
    "bite-zz-two.py Г1 done 0 2 0\n"
    "bite-zz-slow.py Г1 done 0 1 0\n"
    "bite-zz-gone.py Г1 done 0 1 0\n", encoding="utf-8")
broken_dir = stand / "core-set-broken"
broken_dir.mkdir()
(broken_dir / "core-bites.txt").write_text("bite-zz-one.py Г1 done 0 2 0\nbite-zz-two.py Г9 done 0 2\n",
                                           encoding="utf-8")
set_env = {k: v for k, v in os.environ.items() if k != "MEZO_CONTAINER"}
set_env["PYTHONIOENCODING"] = "utf-8"
# полный вывод разошедшихся набор кладёт во временный каталог — пусть это будет стенд, а не общий %TEMP%
for var in ("TMPDIR", "TEMP", "TMP"):
    set_env[var] = str(stand)


def run_set(runner, folder):
    p = subprocess.run([sys.executable, str(runner), "--set", "core", "--dir", str(folder), "--timeout", "3"],  # env: caller — набор зовётся, как его зовёт человек: без MEZO_CONTAINER (документ выпуска, раздел 3, шаг 3); подложенные приёмки контура не читают
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=set_env,
                       cwd=str(HERE))
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out, {n: next((l for l in out.splitlines() if n in l), "")
                               for n in ("bite-zz-one", "bite-zz-two", "bite-zz-slow", "bite-zz-gone")}


real_code, real_out, real_lines = run_set(RUNNER, planted)
total_ok = "совпало 1 · разошлось 1 · не запустилось 2" in real_out
lines_ok = ("совпало" in real_lines["bite-zz-one"] and "РАЗОШЛОСЬ" in real_lines["bite-zz-two"]
            and "стало 1 · 1 · 1" in real_lines["bite-zz-two"] and "потолок 3 с" in real_lines["bite-zz-slow"]
            and "файла нет" in real_lines["bite-zz-gone"])
extra_run = "вне списка" in real_out or "bite-zz-extra" in real_out
br_code, br_out, _ = run_set(RUNNER, broken_dir)
SAME_ANCHOR = "same = got == want"
runner_text = RUNNER.read_text(encoding="utf-8")
if SAME_ANCHOR not in runner_text:
    raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в bite-all.py нет «{SAME_ANCHOR}» — обратный ход ⑰ не поставить")
weak_runner = planted.parent / "bite-all-weak.py"
weak_runner.write_text(runner_text.replace(SAME_ANCHOR, "same = True", 1), encoding="utf-8")
# копия зовётся из стенда: mezo_paths и mezo_stand — из каталога приёмки
set_env["PYTHONPATH"] = str(HERE) + os.pathsep + set_env.get("PYTHONPATH", "")
weak_code, weak_out, _ = run_set(weak_runner, planted)
del set_env["PYTHONPATH"]
weak_caught = "разошлось 0" in weak_out and weak_code != 1
case("⑰ bite-all.py --set core: совпало 1 · разошлось 1 · не запустилось 2, код 1, приёмка вне списка "
     "не запущена; неверная строка — код 2 с номером; обратный ход: без сверки — «разошлось 0»",
     real_code == 1 and total_ok and lines_ok and not extra_run
     and br_code == 2 and "строка 2" in br_out and weak_caught,
     f"код {real_code} · итог {'верен' if total_ok else 'НЕВЕРЕН'} · строки {'верны' if lines_ok else real_lines} · "
     f"вне списка {'ЗАПУЩЕНА' if extra_run else 'не запущена'} · неверный список: код {br_code} · "
     f"без сверки: код {weak_code}, {'«разошлось 0»' if 'разошлось 0' in weak_out else 'итог иной'}")

# ── ⑮ --run: переведённые судят столько же, сколько до перевода ───────────────────────────
if args.run:
    env = {k: v for k, v in os.environ.items() if k != "MEZO_CONTAINER"}
    env["PYTHONIOENCODING"] = "utf-8"
    for x in done:
        p = subprocess.run([sys.executable, str(HERE / x["name"])], capture_output=True, text=True,  # env: caller — ⑮ сличает с «было», снятым без MEZO_CONTAINER; свои стенды приёмка заводит сама
                           encoding="utf-8", errors="replace", env=env, cwd=str(HERE))
        got = (p.returncode, (p.stdout or "").count("✅"), (p.stdout or "").count("🔴"))
        case(f"⑮ {x['name']}: код, ✅, 🔴 — как «было»", got == x["was"],
             f"было {x['was']} · стало {got}")
else:
    print("ℹ️ ⑮ не гонялся: без --run переведённые приёмки не запускаются (каждая — минуты)")

print(f"\nИТОГ: {OK}/{OK + FAIL}" + ("" if FAIL == 0 else " — 🔴 ПОДСТАВНАЯ БАЗА НЕ ПРИНЯТА"))
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
