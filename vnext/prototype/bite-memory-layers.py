# -*- coding: utf-8 -*-
r"""ПРИЁМКА СЛОЁВ ПАМЯТИ: сжатие по слоям, поиск по трём слоям, сверка версии и часа файла —
карточка #781, этап Э2 (критерии ② ③ ④ ⑥); порядок ухода при сжатии — карточка #796.

ЗАЧЕМ. Прежде слой записи памяти не был записан нигде, и «унести старое» значило вырезать
текст рукой. Теперь у записи есть поле слоя (hot · warm · permanent), а работа вокруг него
стоит на трёх инструментах: сжатие (`memory-records.py --сжать`), поиск по всем слоям
(`find-phoenix.py`) и защита записи раздела (`save-phoenix.py`: ожидаемая версия, час файла).
Приёмка судит ИХ ЖЕ запуском на подставной базе, а не чтением кода.

⛔ ЖИВОЙ БАЗЫ НЕ КАСАЕТСЯ. Подставная база — схема живого контура БЕЗ его строк
(mezo_stand.empty_db), роль посажена seed_roles. Первая база — «со слоем»: на неё наводится шаг
схемы запуском файла шага из ИСПЫТУЕМОГО дерева. Вторая — «без слоя»: шаг не наведён
(так выглядит живая база, пока шаг на неё не наведён). С живой базы берётся только схема
(переменная MEZO_LIVE_DB, на чтение). Каждый вызов инструмента идёт через ОДИН помощник,
который ПАДАЕТ, если путь --db лежит вне стенда.

Какую копию испытываем: переменная MEZO_SCRIPTS_ROOT (каталог scripts дерева ИЛИ
vnext/prototype того же дерева) — остальные каталоги выводятся от него. Не вышло — код 2
и название нужного каталога.

Исходы: 0 — все случаи прошли · 1 — есть не прошедшие · 2 — не запустилась (нет стенда,
не найден якорь поломки, инструмент не стартовал).

Случаи (РАЗЛИЧАЮЩИЙ — обязан ответить ИНАЧЕ на поломанном инструменте; КОНТРОЛЬ — не даёт
ложной тревоги и не прячет поломку):
  ④-1 … ④-16  сжатие слоя hot (память записей роли); ④-12 — без --section называет разделы
               с текстом и без записей; ④-13 — свежие записи не уходят, пока есть старше, запись
               без часа уходит раньше них; ④-14 — два раздела с противоположным направлением
               времени, в обоих первым уходит старое; ④-15 — свежие сами больше порога: уходят все
               несвежие, свежие остаются, код 3; ④-16 — запись без часа, появившаяся в слое сегодня,
               свежая
  ⑥-1 … ⑥-6    поиск по трём слоям одним вызовом; ⑥-6 — запрос из трёх слов, которые вместе
               не встречаются (ступень частичного совпадения), с --layer warm
  ②-1, ②-2     запись раздела с устаревшей и со свежей ожидаемой версией
  ③-1, ③-2     файл старше последней записи раздела и свежий файл
Поломки строит сама приёмка заменой текста в КОПИИ инструмента; якорь обязан найтись РОВНО
один раз, иначе код 2. Перед каждой — случай «поломанная копия ЗАПУСТИЛАСЬ» (числа, а не падение):
  П1 снята сверка ожидаемой версии ... не проходит ②-1; проходят ③-1, ④-1, ⑥-1
  П2 не сверяется час файла .......... не проходит ③-1; проходит ②-1
  П3 у поиска отнят один слой ........ не проходит ⑥-1; проходит ②-1
  П4 сжатие печатает, но не пишет .... не проходит ④-1; проходит ⑥-1
  П5 у ступени частичного совпадения
     снят отбор по слою .............. не проходит ⑥-6; проходят ⑥-1, ②-1
  П6 свежих записей нет вовсе ........ не проходит ④-13; проходят ④-14, ④-10, ④-1
  П7 порядок ухода не видит, куда
     идёт время в разделе ............ не проходит ④-14; проходят ④-13, ④-10, ④-1
  П8 свежие уходят последними,
     а не никогда .................... не проходит ④-15; проходят ④-13, ④-16, ④-1
  П9 свежесть записи без часа по
     появлению не судится ............ не проходит ④-16; проходят ④-15, ④-13, ④-1

Зовут так:
    MEZO_SCRIPTS_ROOT=<дерево>/scripts MEZO_LIVE_DB=<живая база, схема> \
        MEZO_CONTAINER=<каталог контура> \
        python -u -X utf8 <дерево>/vnext/prototype/bite-memory-layers.py
MEZO_CONTAINER нужна, когда дерево лежит вне контура (клон): без неё инструменты отвечают
«контейнер группы НЕ НАЙДЕН», и приёмка честно кончается кодом 2.
"""
import contextlib
import hashlib
import itertools
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

ROLE = "PROTO"
OTHER_HAND = "COORD"
LAYER_STEP = "20261115-phoenix-records-layer.py"
SAFE_ENV = {"PYTHONIOENCODING": "utf-8"}

# ── якоря нарочных поломок: текст КОПИИ инструмента, должен встретиться РОВНО один раз ──────
BREAKS = {
    "П1": ("save-phoenix.py",
           "        refusal = expected_version_refusal(conn, role, args.section, args.expect_version, prev_body)",
           "        refusal = None"),
    "П2": ("save-phoenix.py",
           "    if args.file:\n        verdict = file_time_question(args.file, conn, role, args.section, body)",
           "    if False:\n        verdict = file_time_question(args.file, conn, role, args.section, body)"),
    "П3": ("find-phoenix.py",
           "    params.append(limit)\n    sql = (",
           "    where_clauses.append(\"pr.layer <> 'permanent'\")\n    params.append(limit)\n    sql = ("),
    "П4": ("memory-records.py",
           "    elif plan:\n",
           "    elif False:\n"),
    # у ступени частичного совпадения (_fetch_records_or) снят отбор по слою; якорь уникален за счёт cap
    "П5": ("find-phoenix.py",
           "    if layer:\n        where_clauses.append(\"pr.layer = ?\")\n        params.append(layer)\n"
           "    params.append(cap)",
           "    params.append(cap)"),
    # карточка #796: свежих записей нет вовсе — ни по часу, ни по появлению
    "П6": ("memory-records.py",
           "def is_fresh(row, edge):\n",
           "def is_fresh(row, edge):\n    return False\n\n\ndef _was_is_fresh(row, edge):\n"),
    # карточка #796: при равном часе всегда уходит нижняя, куда бы ни шло время в разделе
    "П7": ("memory-records.py",
           "    step = 1 if direction == \"свежее снизу\" else -1",
           "    step = -1"),
    # карточка #796: свежие уходят последними, а не никогда (первая редакция этой карточки)
    "П8": ("memory-records.py",
           "        movable = order if fresh else order[:-1]",
           "        movable = (order + [(r, \"свежая\") for r in fresh])[:-1]"),
    # карточка #796: свежесть записи без часа по её появлению в слое не судится
    "П9": ("memory-records.py",
           "    seen = _day(row[6])\n    return bool(seen and seen >= edge)",
           "    return False"),
}

print(f"⚖️ испытуется: {mezo_target.label()}")


def locate_tree():
    """Корень дерева: в нём лежат и scripts/save-phoenix.py, и vnext/prototype/memory-records.py."""
    root = mezo_target.scripts_root()
    for base in (root, root.parent, root.parent.parent):
        if (base / "scripts" / "save-phoenix.py").is_file() and \
                (base / "vnext" / "prototype" / "memory-records.py").is_file():
            return base
    print(f"⛔ НЕ ЗАПУСТИЛАСЬ: от MEZO_SCRIPTS_ROOT={root.as_posix()} не нашлось дерево пакета.")
    print("   Нужен каталог scripts либо vnext/prototype дерева, где рядом лежат обе половины:")
    print("   scripts/save-phoenix.py и vnext/prototype/memory-records.py.")
    print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего.")
    sys.exit(mezo_stand.finish(2))


TREE = locate_tree()
TOOLS = {
    "save": TREE / "scripts" / "save-phoenix.py",
    "find": TREE / "scripts" / "find-phoenix.py",
    "records": TREE / "vnext" / "prototype" / "memory-records.py",
}
MIGRATION = TREE / "scripts" / "migrations" / LAYER_STEP
GUARD = TREE / "vnext" / "prototype" / "guard-phoenix-volume.py"
for _p in list(TOOLS.values()) + [MIGRATION, GUARD]:
    if not _p.is_file():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в дереве нет {_p.as_posix()} — испытывать нечего.")
        sys.exit(mezo_stand.finish(2))

STAND = mezo_stand.new("bite-memory-layers")
STAND_REAL = STAND.resolve()
COUNTER = itertools.count(1)


def call(tool, db, *args, role=ROLE, hand=ROLE, timeout=180):
    """ЕДИНСТВЕННЫЙ вход в испытуемые инструменты. Падает, если база не внутри стенда."""
    db_real = Path(db).resolve()
    if not db_real.is_relative_to(STAND_REAL):
        raise AssertionError(f"вызов вне стенда: --db {db_real} лежит не внутри {STAND_REAL}")
    container = db_real.parent.parent
    r = subprocess.run([sys.executable, "-u", "-X", "utf8", str(tool), "--db", str(db_real),
                        "--role", role, *[str(a) for a in args]],
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                       env=mezo_stand.stand_env(container, MEZO_ROLE=hand, **SAFE_ENV))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_plain(*cmd):
    """Запуск шага схемы (не инструмента памяти): путь базы тоже обязан лежать в стенде."""
    r = subprocess.run([sys.executable, "-u", "-X", "utf8", *[str(c) for c in cmd]],
                       capture_output=True, text=True, encoding="utf-8", timeout=180,
                       env=dict(os.environ, **SAFE_ENV))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ── подставные базы ─────────────────────────────────────────────────────────────────────────
def build_templates():
    live = Path(os.environ["MEZO_LIVE_DB"]) if os.environ.get("MEZO_LIVE_DB") else \
        mezo_target.scripts_root().parent / "mezosync.db"
    if not live.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: схему подставной базы брать неоткуда — нет {live}")
        print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего. Назови MEZO_LIVE_DB.")
        sys.exit(mezo_stand.finish(2))
    tdir = STAND / "templates"
    (tdir / "plain").mkdir(parents=True)
    plain = tdir / "plain" / "mezosync.db"
    mezo_stand.empty_db(live, plain)
    mezo_stand.seed_roles(plain, [ROLE])
    with contextlib.closing(sqlite3.connect(str(plain))) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(phoenix_records)")}
    if "layer" in cols:
        print("⛔ НЕ ЗАПУСТИЛАСЬ: в схеме, взятой с MEZO_LIVE_DB, поле слоя УЖЕ есть — база «без слоя»"
              " не получается. Назови другую MEZO_LIVE_DB (схема до шага слоя).")
        sys.exit(mezo_stand.finish(2))
    layered = tdir / "layered" / "mezosync.db"
    layered.parent.mkdir(parents=True)
    shutil.copy2(plain, layered)
    code, out = run_plain(MIGRATION, "--db", layered)
    with contextlib.closing(sqlite3.connect(str(layered))) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(phoenix_records)")}
    if code != 0 or not {"layer", "layer_moved_at", "layer_moved_by"} <= cols:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: шаг схемы слоя на подставной базе не навёлся (код {code}):\n{out}")
        sys.exit(mezo_stand.finish(2))
    return {"plain": plain, "layered": layered}


def new_db(kind):
    d = STAND / "cases" / f"c{next(COUNTER):03d}"
    (d / ".mezosync").mkdir(parents=True)
    dst = d / ".mezosync" / "mezosync.db"
    shutil.copy2(TEMPLATES[kind], dst)
    return dst


# ── посадка данных SQL-ом (текст раздела = склейка записей, как у разбора) ───────────────────
def filler(size, head):
    """Тело ровно `size` знаков: заголовок и строки без редких слов, кончается переводом строки."""
    text = head + "\n"
    line = "служебная строка опыта про ничего\n"
    while len(text) < size - 1:
        text += line
    return text[:size - 1] + "\n"


def rec(size=2000, head="## Запись", **kw):
    # created_at — когда запись появилась в слое; None — давно (400 дней назад). Запись без часа,
    # появившаяся за последние сутки, свежая, и сжатие её не уносит (карточка #796)
    r = {"body": filler(size, head), "subject": "разное", "happened_at": None,
         "alive": "active", "layer": "hot", "moved_at": None, "moved_by": None, "created_at": None}
    r.update(kw)
    return r


def plant(db, section, recs):
    """Посадить раздел и его записи. Вернуть номера записей по порядку."""
    ids = []
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        has_layer = any(r[1] == "layer" for r in c.execute("PRAGMA table_info(phoenix_records)"))
        whole = "".join(r["body"] for r in recs)
        c.execute("DELETE FROM phoenix WHERE role=? AND section=?", (ROLE, section))
        c.execute("INSERT INTO phoenix (role, section, body) VALUES (?,?,?)", (ROLE, section, whole))
        for n, r in enumerate(recs, 1):
            cols = ["role", "section", "subject", "body", "body_chars", "happened_at", "alive",
                    "ord", "origin_chars", "created_by", "created_at"]
            vals = [ROLE, section, r["subject"], r["body"], len(r["body"]), r["happened_at"],
                    r["alive"], n, len(whole), "стенд приёмки",
                    r["created_at"] or f"{days_ago(400)} 00:00:00"]
            if has_layer:
                cols += ["layer", "layer_moved_at", "layer_moved_by"]
                vals += [r["layer"], r["moved_at"], r["moved_by"]]
            cur = c.execute(f"INSERT INTO phoenix_records ({', '.join(cols)}) "
                            f"VALUES ({', '.join('?' * len(cols))})", vals)
            ids.append(cur.lastrowid)
        c.commit()
    return ids


def file_fp(db):
    return hashlib.sha256(Path(db).read_bytes()).hexdigest()[:16]


def text_fp(db):
    """Отпечаток ТЕКСТА: тела разделов и тела записей (слой в него не входит)."""
    h = hashlib.sha256()
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        for row in c.execute("SELECT role, section, body FROM phoenix ORDER BY role, section"):
            h.update(repr(row).encode())
        for row in c.execute("SELECT id, body FROM phoenix_records ORDER BY id"):
            h.update(repr(row).encode())
    return h.hexdigest()[:16]


def layer_rows(db, section=None):
    """{id: (layer, moved_at, moved_by)} — слой записей."""
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        q = "SELECT id, layer, layer_moved_at, layer_moved_by FROM phoenix_records"
        rows = c.execute(q + (" WHERE section=?" if section else "") + " ORDER BY id",
                         (section,) if section else ()).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def hot_chars(db, section):
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        return c.execute("SELECT COALESCE(SUM(body_chars),0) FROM phoenix_records "
                         "WHERE section=? AND layer='hot'", (section,)).fetchone()[0]


def printed_moves(out):
    """Номера унесённых из ПЕЧАТИ сжатия — по порядку строк «#N · … · hot → warm · …»."""
    return [int(m.group(1)) for m in re.finditer(r"^\s*#(\d+) · .* · hot → warm · ", out, re.M)]


def volume_limit():
    """Порог — ТЕМ ЖЕ чтением LIMIT из guard-phoenix-volume.py, что у сжатия; числа здесь нет."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard_volume_probe", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    limit = getattr(module, "LIMIT", None)
    if not isinstance(limit, int) or limit <= 0:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {GUARD.name} нет годного LIMIT ({limit!r})")
        sys.exit(mezo_stand.finish(2))
    return limit


# ── данные для сжатия: раздел выше порога ───────────────────────────────────────────────────
def over_threshold_records(limit):
    """14 записей по 2000 знаков (больше порога у любого LIMIT до 28 000), плюс одна warm и одна
    permanent с пометкой переноса. Снятая одна, датированных три, остальные без часа."""
    recs = []
    for n in range(1, 15):
        kw = {}
        if n == 3:
            kw = {"alive": "revoked"}
        if n in (6, 9, 12):
            kw = {"happened_at": f"2026-0{n // 3}-1{n % 3}"}
        recs.append(rec(2000, f"## Запись {n}", **kw))
    recs.append(rec(2000, "## Унесена раньше", layer="warm",
                    moved_at="2026-01-01 00:00:00", moved_by="СТЕНД"))
    recs.append(rec(2000, "## Вечная запись", layer="permanent",
                    moved_at="2026-01-02 00:00:00", moved_by="СТЕНД"))
    return recs


def need_over(limit, recs):
    hot = sum(len(r["body"]) for r in recs if r["layer"] == "hot")
    return hot > limit


# ── случаи ──────────────────────────────────────────────────────────────────────────────────
class Ctx:
    def __init__(self, tools):
        self.t = tools


def case_4_1(T):
    limit = volume_limit()
    recs = over_threshold_records(limit)
    if not need_over(limit, recs):
        return False, f"данные опыта не выше порога {limit}: случай не поставлен"
    db = new_db("layered")
    ids = plant(db, "state", recs)
    before = layer_rows(db)
    hot_before = hot_chars(db, "state")
    n_before = sum(1 for v in before.values() if v[0] == "hot")
    fp = text_fp(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    after = layer_rows(db)
    moved_db = sorted(i for i in after if after[i][0] == "warm" and after[i][2] == ROLE)
    moved_out = printed_moves(out)
    hot_after = hot_chars(db, "state")
    n_after = sum(1 for v in after.values() if v[0] == "hot")
    stamped = bool(moved_db) and all(
        re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", after[i][1] or "") for i in moved_db)
    numbers = f"было {hot_before} знаков в {n_before} записях → стало {hot_after} в {n_after}" in out
    same_set = sorted(moved_out) == moved_db and len(moved_out) == len(set(moved_out))
    ok = (code == 0 and same_set and bool(moved_db) and stamped and numbers and fp == text_fp(db)
          and hot_after <= limit and "hot → warm" in out)
    return ok, (f"код {code} (ждали 0) · в печати унесено {len(moved_out)}, в базе {len(moved_db)}, "
                f"номера совпали: {'да' if same_set else 'НЕТ'} · знаки до/после напечатаны верно: "
                f"{'да' if numbers else 'НЕТ'} ({hot_before} → {hot_after}, порог {limit}) · час и рука "
                f"записаны: {'да' if stamped else 'НЕТ'} · текст не менялся: "
                f"{'да' if fp == text_fp(db) else 'НЕТ'}")


def case_4_2(T):
    db = new_db("layered")
    plant(db, "state", [rec(1500, f"## Малая {n}") for n in range(1, 4)])
    before = layer_rows(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    ok = code == 0 and "уносить нечего" in out and layer_rows(db) == before
    return ok, (f"раздел ниже порога: код {code} (ждали 0) · «уносить нечего»: "
                f"{'да' if 'уносить нечего' in out else 'НЕТ'} · слои не менялись: "
                f"{'да' if layer_rows(db) == before else 'НЕТ'}")


def case_4_3(T):
    db = new_db("layered")
    limit = volume_limit()
    plant(db, "state", over_threshold_records(limit))
    fp0 = file_fp(db)
    got = []
    for flag in ("--threshold", "--порог"):
        code, out = call(T.t["records"], db, "--section", "state", "--сжать", flag, "100")
        got.append((flag, code, "unrecognized arguments" in out))
    ok = all(c == 2 and u for _f, c, u in got) and file_fp(db) == fp0
    return ok, ("выдуманный признак порога: " + " · ".join(
        f"{f} → код {c}, разбор аргументов отклонил: {'да' if u else 'НЕТ'}" for f, c, u in got)
        + f" · база не тронута: {'да' if file_fp(db) == fp0 else 'НЕТ'}")


def case_4_4(T):
    limit = volume_limit()
    db = new_db("layered")
    plant(db, "state", over_threshold_records(limit))
    fp0 = file_fp(db)
    code, dry = call(T.t["records"], db, "--section", "state", "--сжать", "--dry-run")
    fp1 = file_fp(db)
    dry_ids = printed_moves(dry)
    code2, real = call(T.t["records"], db, "--section", "state", "--сжать")
    ok = (code == 0 and fp0 == fp1 and bool(dry_ids) and dry_ids == printed_moves(real)
          and "база не тронута" in dry)
    return ok, (f"холостой прогон: код {code} (ждали 0) · в перечне {len(dry_ids)} записей · "
                f"отпечаток базы {fp0} → {fp1} · тот же перечень, что у настоящего вызова: "
                f"{'да' if dry_ids == printed_moves(real) else 'НЕТ'} (код {code2})")


def case_4_5(T):
    limit = volume_limit()
    db = new_db("layered")
    ids = plant(db, "state", over_threshold_records(limit))
    warm_id, perm_id = ids[-2], ids[-1]
    before = layer_rows(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    after = layer_rows(db)
    untouched = after[warm_id] == before[warm_id] and after[perm_id] == before[perm_id]
    moved_any = any(after[i][0] != before[i][0] for i in ids[:-2])
    return (code == 0 and untouched and moved_any,
            f"warm и permanent сжатием не тронуты: {'да' if untouched else 'НЕТ'} "
            f"(warm {before[warm_id][1:]} → {after[warm_id][1:]}, "
            f"permanent {before[perm_id][1:]} → {after[perm_id][1:]}) · сжатие что-то унесло: "
            f"{'да' if moved_any else 'НЕТ'} · код {code}")


def case_4_6(T):
    limit = volume_limit()
    db = new_db("layered")
    plant(db, "state", over_threshold_records(limit))
    code1, out1 = call(T.t["records"], db, "--section", "state", "--сжать")
    mid = layer_rows(db)
    fp_mid = file_fp(db)
    code2, out2 = call(T.t["records"], db, "--section", "state", "--сжать")
    ok = (code1 == 0 and bool(printed_moves(out1)) and code2 == 0 and not printed_moves(out2)
          and "уносить нечего" in out2 and layer_rows(db) == mid and file_fp(db) == fp_mid)
    return ok, (f"повтор после сжатия: первый унёс {len(printed_moves(out1))}, второй "
                f"{len(printed_moves(out2))} (код {code2}, ждали 0) · «уносить нечего»: "
                f"{'да' if 'уносить нечего' in out2 else 'НЕТ'} · база не менялась: "
                f"{'да' if file_fp(db) == fp_mid else 'НЕТ'}")


def case_4_7(T):
    limit = volume_limit()
    db = new_db("layered")
    plant(db, "state", over_threshold_records(limit))
    fp0 = file_fp(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать", hand=OTHER_HAND)
    ok = code == 1 and "ОТКАЗ" in out and file_fp(db) == fp0
    return ok, (f"чужая рука ({OTHER_HAND} → {ROLE}): код {code} (ждали 1) · отказ назван: "
                f"{'да' if 'ОТКАЗ' in out else 'НЕТ'} · база не тронута: "
                f"{'да' if file_fp(db) == fp0 else 'НЕТ'}")


def case_4_8(T):
    limit = volume_limit()
    db = new_db("plain")
    plant(db, "state", over_threshold_records(limit))
    fp0 = file_fp(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    named = LAYER_STEP.removesuffix(".py") in out
    ok = code == 1 and named and file_fp(db) == fp0
    return ok, (f"база без поля слоя: код {code} (ждали 1) · шаг схемы назван: "
                f"{'да' if named else 'НЕТ'} · база не тронута: {'да' if file_fp(db) == fp0 else 'НЕТ'}")


def case_4_9(T):
    limit = volume_limit()
    db = new_db("layered")
    ids = plant(db, "state", [rec(limit + 1500, "## Одна огромная")])
    fp0 = file_fp(db)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    stays = layer_rows(db)[ids[0]][0] == "hot"
    ok = (code == 3 and "порог НЕ достигнут" in out and "сама больше порога" in out and stays
          and file_fp(db) == fp0)
    return ok, (f"одна запись больше порога: код {code} (ждали 3) · сказано, что порог не достигнут и "
                f"почему: {'да' if 'сама больше порога' in out else 'НЕТ'} · запись на месте: "
                f"{'да' if stays else 'НЕТ'}")


def case_4_10(T):
    limit = volume_limit()
    size = limit // 5
    # 10 записей по size знаков: уходить должны ровно 5 (остаток 5·size ≤ порога, а 6·size — больше)
    recs = [rec(size, f"## Порядок {n}") for n in range(1, 11)]
    recs[3]["alive"] = "revoked"                      # №4 снята, час у неё НОВЕЕ всех датированных
    recs[3]["happened_at"] = "2026-12-01"
    for n, day in ((2, "2026-03-01"), (7, "2026-01-01"), (9, "2026-02-01")):   # №2 №7 №9 датированы
        recs[n - 1]["happened_at"] = day
    # без часа: №1 №3 №5 №6 №8 №10 — час берут у ближайшей записи с часом (карточка #796):
    # №5 и №6 — у №7 (01-01), №8 и №10 — у №9 (02-01; №8 стоит между №7 и №9 — берётся свежая),
    # №1 и №3 — у №2 (03-01). Время в разделе идёт «свежее сверху»: при равном часе раньше нижняя
    db = new_db("layered")
    ids = plant(db, "state", recs)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    expected = [ids[3], ids[6], ids[5], ids[4], ids[9]]
    got = printed_moves(out)
    ok = code == 0 and got == expected
    names = lambda lst: [ids.index(i) + 1 for i in lst]
    return ok, (f"порядок ухода по номерам записей: напечатано {names(got)} (ждали {names(expected)}: "
                f"снятая №4 · час 01-01: №7 и без часа рядом с ней №6, №5 · затем 02-01: №10) · код {code}")


def utc_today():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).date()


def days_ago(n):
    import datetime
    return (utc_today() - datetime.timedelta(days=n)).isoformat()


def case_4_13(T):
    limit = volume_limit()
    size = limit // 2
    # 10 записей по size знаков: уходят ровно 8 (остаток 2·size ≤ порога, 3·size — больше).
    # Время идёт «свежее сверху». С часом: №2 и №3 — сегодня, №4 — 30 дней назад, №6 — 60, №9 — 90;
    # без часа — №1 (сосед №2, сегодня), №5, №7, №8, №10
    days = {2: 0, 3: 0, 4: 30, 6: 60, 9: 90}
    recs = [rec(size, f"## Свежесть {n}", happened_at=days_ago(days[n]) if n in days else None)
            for n in range(1, 11)]
    db = new_db("layered")
    ids = plant(db, "state", recs)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    got = printed_moves(out)
    expected = [ids[n - 1] for n in (10, 9, 8, 7, 6, 5, 4, 1)]
    names = lambda lst: [ids.index(i) + 1 for i in lst]
    gone_fresh = sorted(names([i for i in got if i in (ids[1], ids[2])]))
    said_dir = "время в разделе — свежее сверху" in out
    ok = code == 0 and got == expected and not gone_fresh and said_dir
    return ok, (f"свежие не уходят, пока есть старше: напечатано {names(got)} (ждали {names(expected)}: от старших; без "
                f"часа — по соседней записи с часом; №1 без часа уходит раньше свежих №2 и №3) · свежих "
                f"унесено: {gone_fresh or 'ни одной'} · строка «свежее сверху» напечатана: "
                f"{'да' if said_dir else 'НЕТ'} · код {code}")


def case_4_14(T):
    limit = volume_limit()
    size = limit // 5
    # два раздела по 10 записей, в каждом уходят ровно 5. «plan» — свежее снизу: с часом №1 (90 дней
    # назад), №4 (60), №6 (30), №9 (вчера), №10 (сегодня); «state» — то же зеркально, свежее сверху
    below = {1: 90, 4: 60, 6: 30, 9: 1, 10: 0}
    above = {11 - n: d for n, d in below.items()}
    db = new_db("layered")
    planted = {}
    for sect, days in (("plan", below), ("state", above)):
        recs = [rec(size, f"## {sect} {n}", happened_at=days_ago(days[n]) if n in days else None)
                for n in range(1, 11)]
        planted[sect] = plant(db, sect, recs)
    code, out = call(T.t["records"], db, "--сжать")
    moved = printed_moves(out)
    want = {"plan": [1, 2, 3, 4, 5], "state": [10, 9, 8, 7, 6]}
    ok, parts = code == 0, []
    for sect in ("plan", "state"):
        ids = planted[sect]
        got = [ids.index(i) + 1 for i in moved if i in ids]
        ok = ok and got == want[sect]
        parts.append(f"{sect}: напечатано {got} (ждали {want[sect]})")
    both = "время в разделе — свежее снизу" in out and "время в разделе — свежее сверху" in out
    ok = ok and both
    return ok, (" · ".join(parts) + f" · оба направления напечатаны: {'да' if both else 'НЕТ'} · код {code}")


def case_4_15(T):
    limit = volume_limit()
    big, small = limit * 3 // 5, limit // 5
    # свежие сами больше порога (так у COORD 23.11: одна свежая запись state — 45 226 знаков).
    # С часом: №1 — сегодня, №2 — вчера (оба по big), №3 — 30 дней назад, №5 — 60; без часа и давние
    # по появлению — №4, №6. Уйти обязаны все четыре несвежие и ни одна свежая: код 3
    days = {1: 0, 2: 1, 3: 30, 5: 60}
    recs = [rec(big if n <= 2 else small, f"## Свежие больше порога {n}",
                happened_at=days_ago(days[n]) if n in days else None) for n in range(1, 7)]
    db = new_db("layered")
    ids = plant(db, "state", recs)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    got = printed_moves(out)
    names = lambda lst: [ids.index(i) + 1 for i in lst]
    expected = [ids[n - 1] for n in (6, 5, 4, 3)]
    gone_fresh = sorted(names([i for i in got if i in (ids[0], ids[1])]))
    hot = [i for i, v in layer_rows(db).items() if v[0] == "hot"]
    said_rest = "в слое остались только свежие записи — 2" in out
    ok = code == 3 and got == expected and not gone_fresh and sorted(hot) == sorted(ids[:2]) and said_rest
    return ok, (f"свежие сами больше порога: напечатано {names(got)} (ждали {names(expected)}: все несвежие, "
                f"от старших) · свежих унесено: {gone_fresh or 'ни одной'} · в hot остались "
                f"{sorted(names(hot))} (ждали [1, 2]) · сказано «остались только свежие записи — 2»: "
                f"{'да' if said_rest else 'НЕТ'} · код {code} (ждали 3)")


def case_4_16(T):
    limit = volume_limit()
    size = limit // 2
    # свежесть записи без часа — по появлению в слое. №1 — с часом 60 дней назад; №2 и №3 без часа,
    # появились 30 дней назад; №4 без часа, появилась сегодня — свежая. Уходят ровно две: №3, №2
    seen = {2: f"{days_ago(30)} 12:00:00", 3: f"{days_ago(30)} 12:00:00", 4: f"{days_ago(0)} 00:00:00"}
    recs = [rec(size, f"## Появление {n}", happened_at=days_ago(60) if n == 1 else None,
                created_at=seen.get(n)) for n in range(1, 5)]
    db = new_db("layered")
    ids = plant(db, "state", recs)
    code, out = call(T.t["records"], db, "--section", "state", "--сжать")
    got = printed_moves(out)
    names = lambda lst: [ids.index(i) + 1 for i in lst]
    expected = [ids[2], ids[1]]
    gone_new = ids[3] in got
    counted = f"свежих с {days_ago(1)}: 1," in out
    ok = code == 0 and got == expected and not gone_new and counted
    return ok, (f"запись без часа, появившаяся сегодня: напечатано {names(got)} (ждали {names(expected)}) · "
                f"№4 унесена: {'ДА' if gone_new else 'нет'} · в строке порядка ухода свежих 1: "
                f"{'да' if counted else 'НЕТ'} · код {code}")


def case_4_11(T):
    limit = volume_limit()
    db = new_db("layered")
    ids = plant(db, "state", over_threshold_records(limit))
    code1, _o1 = call(T.t["records"], db, "--section", "state", "--сжать")
    after1 = layer_rows(db)
    warm_set = sorted(i for i in after1 if after1[i][0] == "warm")
    code2, out2 = call(T.t["records"], db, "--section", "state", "--пересобрать")
    after2 = layer_rows(db)
    ok = (code1 == 0 and code2 == 0 and bool(warm_set) and after2 == after1
          and "ПОЛЯ ПОТЕРЯНЫ" not in out2)
    return ok, (f"пересборка без правки текста: код {code2} (ждали 0) · слой warm цел у "
                f"{sum(1 for i in warm_set if after2.get(i, ('',))[0] == 'warm')} из {len(warm_set)} "
                f"унесённых · потерь полей не названо: {'да' if 'ПОЛЯ ПОТЕРЯНЫ' not in out2 else 'НЕТ'}")


LAYERS3 = ("hot", "warm", "permanent")


def plant_three(db, word, extra=""):
    recs = [rec(300, f"## Находка про {word} {layer}", layer=layer,
                body=f"## Находка про {word} {layer}\nпро {word} здесь сказано слово {extra}\n")
            for layer in LAYERS3]
    recs.append(rec(300, "## Посторонняя"))
    ids = plant(db, "state", recs)
    return dict(zip(LAYERS3, ids[:3]))


def headers(out):
    """{id: слой} по строкам заголовков найденных записей."""
    return {int(m.group(1)): m.group(2)
            for m in re.finditer(r"^#(\d+) · .* · слой (\w+)", out, re.M)}


def case_6_1(T):
    db = new_db("layered")
    planted = plant_three(db, "хризолит")
    code, out = call(T.t["find"], db, "хризолит")
    got = headers(out)
    want = {i: layer for layer, i in planted.items()}
    counts = "по слоям: hot 1 · warm 1 · permanent 1" in out
    ok = code == 0 and got == want and counts
    return ok, (f"три слоя одним вызовом: код {code} (ждали 0) · найдено {sorted(got.values())} "
                f"(ждали все три) · у каждой свой слой названа верно: {'да' if got == want else 'НЕТ'} "
                f"· счёт по слоям: {'да' if counts else 'НЕТ'}")


def case_6_2(T):
    db = new_db("layered")
    texts = {"hot": "ПРАВО на правку", "warm": "право владельца", "permanent": "Право роли"}
    recs = [rec(300, f"## О праве {layer}", layer=layer,
                body=f"## О праве {layer}\n{texts[layer]} записано здесь\n") for layer in LAYERS3]
    ids = plant(db, "state", recs)
    sets = {}
    for q in ("ПРАВО", "право"):
        code, out = call(T.t["find"], db, q)
        sets[q] = (code, headers(out))
    same = set(sets["ПРАВО"][1]) == set(sets["право"][1]) == set(ids)
    layers_found = set(sets["право"][1].values())
    ok = all(c == 0 for c, _h in sets.values()) and same and len(layers_found) == 3
    return ok, (f"«ПРАВО» и «право»: коды {[c for c, _h in sets.values()]} · одно множество номеров: "
                f"{'да' if same else 'НЕТ'} ({sorted(sets['ПРАВО'][1])} против {sorted(sets['право'][1])}) "
                f"· слоёв в нём {len(layers_found)} (ждали 3)")


def case_6_3(T):
    db = new_db("layered")
    recs = [rec(300, "## Про карточку", layer="permanent",
                body="## Про карточку\nрешено в карточка #462 и больше не трогаем\n"),
            rec(300, "## Соседняя карточка", layer="warm",
                body="## Соседняя карточка\nа тут карточка #463 про другое\n")]
    ids = plant(db, "state", recs)
    code, out = call(T.t["find"], db, "#462")
    got = headers(out)
    ok = code == 0 and ids[0] in got and ids[1] not in got
    return ok, (f"«#462»: код {code} (ждали 0) · найдена запись с «карточка #462»: "
                f"{'да' if ids[0] in got else 'НЕТ'} · соседняя «#463» не подмешана: "
                f"{'да' if ids[1] not in got else 'НЕТ'}")


def case_6_4(T):
    db = new_db("layered")
    planted = plant_three(db, "хризолит")
    code, out = call(T.t["find"], db, "хризолит", "--layer", "warm")
    got = headers(out)
    ok = code == 0 and got == {planted["warm"]: "warm"} and "по слоям: warm 1" in out
    return ok, (f"--layer warm: код {code} (ждали 0) · найдено слоёв {sorted(got.values())} "
                f"(ждали только warm) · ровно запись warm: {'да' if got == {planted['warm']: 'warm'} else 'НЕТ'}")


def case_6_5(T):
    db = new_db("plain")
    recs = [rec(300, "## Про хризолит", body="## Про хризолит\nпро хризолит здесь слово\n")]
    ids = plant(db, "state", recs)
    code, out = call(T.t["find"], db, "хризолит")
    said = out.count("слоя памяти в этой базе нет")
    found = f"#{ids[0]} · " in out
    code2, out2 = call(T.t["find"], db, "хризолит", "--layer", "warm")
    ok = code == 0 and said == 1 and found and code2 == 1 and "нет поля слоя" in out2
    return ok, (f"база без поля слоя: поиск код {code} (ждали 0) · запись найдена: "
                f"{'да' if found else 'НЕТ'} · «слоя нет» сказано раз: {said} (ждали 1) · "
                f"--layer: код {code2} (ждали 1), причина названа: {'да' if 'нет поля слоя' in out2 else 'НЕТ'}")


def case_6_6(T):
    """Три слова, которые ВМЕСТЕ не встречаются ни в одной записи: поиск доходит до ступени
    частичного совпадения. Каждая запись несёт по два слова из трёх, слои у них разные."""
    db = new_db("layered")
    pairs = {"hot": ("хризолит", "гранат"), "warm": ("гранат", "аметист"),
             "permanent": ("хризолит", "аметист")}
    recs = [rec(300, f"## Пара {layer}", layer=layer,
                body=f"## Пара {layer}\nздесь сказано про {a} и про {b}\n")
            for layer, (a, b) in pairs.items()]
    recs.append(rec(300, "## Посторонняя"))
    ids = plant(db, "state", recs)
    warm_id = ids[1]
    code, out = call(T.t["find"], db, "хризолит гранат аметист", "--layer", "warm")
    got = headers(out)
    partial = "все слова вместе не встречаются" in out
    ok = (code == 0 and bool(got) and set(got.values()) == {"warm"} and warm_id in got
          and not (set(got) & {ids[0], ids[2]}) and partial)
    return ok, (f"три слова врозь, --layer warm: код {code} (ждали 0) · найдено слоёв "
                f"{sorted(got.values())} (ждали только warm, хотя бы одну запись) · записей hot в ответе: "
                f"{'НЕТ' if ids[0] not in got else 'ЕСТЬ'} · дошло до частичного совпадения: "
                f"{'да' if partial else 'НЕТ'}")


def case_4_12(T):
    db = new_db("layered")
    plant(db, "state", [rec(1500, f"## Малая {n}") for n in range(1, 4)])
    bare_text = save_body(500, "без записей")
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        c.execute("INSERT INTO phoenix (role, section, body) VALUES (?,?,?)", (ROLE, "plan", bare_text))
        c.commit()
    fp0 = file_fp(db)
    code, out = call(T.t["records"], db, "--сжать", "--dry-run")
    named = "разделы без записей" in out and f"plan ({len(bare_text)} знаков)" in out
    # встречная половина: записи есть у всех разделов роли — строки нет
    db2 = new_db("layered")
    plant(db2, "state", [rec(1500, f"## Малая {n}") for n in range(1, 4)])
    plant(db2, "plan", [rec(500, "## Плановая")])
    code2, out2 = call(T.t["records"], db2, "--сжать", "--dry-run")
    absent = "разделы без записей" not in out2
    ok = code == 0 and code2 == 0 and named and absent and file_fp(db) == fp0
    return ok, (f"раздел с текстом и без записей: код {code} (ждали 0) · назван вместе с числом знаков "
                f"({len(bare_text)}): {'да' if named else 'НЕТ'} · база не тронута: "
                f"{'да' if file_fp(db) == fp0 else 'НЕТ'} · встречная половина (записи у всех "
                f"разделов): код {code2} (ждали 0), строки нет: {'да' if absent else 'НЕТ'}")


def save_body(size, mark):
    head = f"# раздел опыта {mark}\n"
    return head + ("строка опыта\n" * max(1, (size - len(head)) // 13))


def history_ids(db, section):
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        return [r[0] for r in c.execute(
            "SELECT id FROM phoenix_history WHERE role=? AND section=? ORDER BY id", (ROLE, section))]


def body_hash(db, section):
    with contextlib.closing(sqlite3.connect(str(db))) as c:
        row = c.execute("SELECT body FROM phoenix WHERE role=? AND section=?", (ROLE, section)).fetchone()
    return hashlib.sha256(row[0].encode()).hexdigest()[:12] if row else None


def save_file(T, db, section, text, name, age=0):
    f = STAND / "files" / f"{name}-{next(COUNTER)}.md"
    f.parent.mkdir(exist_ok=True)
    f.write_text(text, encoding="utf-8")
    if age:
        t = time.time() - age
        os.utime(f, (t, t))
    return call(T.t["save"], db, "--section", section, "--file", f, "--actor", ROLE)


def two_versions(T):
    """База со слоем и разделом, записанным дважды; вернуть (база, номера версий)."""
    db = new_db("layered")
    for size, mark in ((500, "первая"), (600, "вторая")):
        code, out = save_file(T, db, "plan", save_body(size, mark), "v")
        if code != 0:
            return db, None, out
    return db, history_ids(db, "plan"), ""


def case_2_1(T):
    db, ids, why = two_versions(T)
    if not ids or len(ids) < 2:
        return False, f"опыт не поставлен: версий {ids}, {why}"
    h0 = body_hash(db, "plan")
    f = STAND / "files" / "stale-version.md"
    f.write_text(save_body(700, "поверх устаревшей"), encoding="utf-8")
    code, out = call(T.t["save"], db, "--section", "plan", "--file", f, "--actor", ROLE,
                     "--expect-version", ids[0])
    kept = body_hash(db, "plan") == h0
    ok = code == 1 and "ОТКАЗ" in out and kept
    return ok, (f"устаревшая ожидаемая версия (id={ids[0]}, новейшая id={ids[-1]}): код {code} (ждали 1) "
                f"· отказ напечатан: {'да' if 'ОТКАЗ' in out else 'НЕТ'} · тело не записано: "
                f"{'да' if kept else 'НЕТ'}")


def case_2_2(T):
    db, ids, why = two_versions(T)
    if not ids or len(ids) < 2:
        return False, f"опыт не поставлен: версий {ids}, {why}"
    h0 = body_hash(db, "plan")
    f = STAND / "files" / "fresh-version.md"
    f.write_text(save_body(700, "поверх свежей"), encoding="utf-8")
    code, out = call(T.t["save"], db, "--section", "plan", "--file", f, "--actor", ROLE,
                     "--expect-version", ids[-1])
    wrote = body_hash(db, "plan") != h0
    ok = code == 0 and wrote
    return ok, (f"свежая ожидаемая версия (id={ids[-1]}): код {code} (ждали 0) · записано: "
                f"{'да' if wrote else 'НЕТ'}")


def case_3_1(T):
    db, ids, why = two_versions(T)
    if not ids:
        return False, f"опыт не поставлен: {why}"
    h0 = body_hash(db, "plan")
    code, out = save_file(T, db, "plan", save_body(520, "старый файл"), "stale", age=29 * 60)
    kept = body_hash(db, "plan") == h0
    ok = code == 4 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" in out and kept
    return ok, (f"файл на 29 минут старше записи раздела: код {code} (ждали 4) · вопрос напечатан: "
                f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' in out else 'НЕТ'} · тело не записано: "
                f"{'да' if kept else 'НЕТ'}")


def case_3_2(T):
    db, ids, why = two_versions(T)
    if not ids:
        return False, f"опыт не поставлен: {why}"
    h0 = body_hash(db, "plan")
    code, out = save_file(T, db, "plan", save_body(540, "свежий файл"), "fresh")
    wrote = body_hash(db, "plan") != h0
    ok = code == 0 and wrote and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out
    return ok, (f"свежий файл: код {code} (ждали 0) · вопроса нет: "
                f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'} · записано: "
                f"{'да' if wrote else 'НЕТ'}")


CASES = [
    ("④-1", "РАЗЛ.", case_4_1, "раздел выше порога → сжатие: печать и база сходятся"),
    ("④-2", "РАЗЛ.", case_4_2, "раздел ниже порога → уносить нечего"),
    ("④-3", "КОНТР.", case_4_3, "признака порога нет"),
    ("④-4", "РАЗЛ.", case_4_4, "холостой прогон"),
    ("④-5", "РАЗЛ.", case_4_5, "permanent и warm не тронуты"),
    ("④-6", "КОНТР.", case_4_6, "повтор сжатия"),
    ("④-7", "КОНТР.", case_4_7, "чужая рука"),
    ("④-8", "РАЗЛ.", case_4_8, "база без поля слоя"),
    ("④-9", "РАЗЛ.", case_4_9, "одна запись больше порога"),
    ("④-10", "РАЗЛ.", case_4_10, "порядок ухода"),
    ("④-11", "КОНТР.", case_4_11, "пересборка без правки текста"),
    ("④-12", "РАЗЛ.", case_4_12, "разделы без записей названы"),
    ("④-13", "РАЗЛ.", case_4_13, "свежие записи не уходят, пока есть старше"),
    ("④-14", "РАЗЛ.", case_4_14, "два раздела с противоположным направлением времени"),
    ("④-15", "РАЗЛ.", case_4_15, "свежие сами больше порога — не уходят вовсе"),
    ("④-16", "РАЗЛ.", case_4_16, "запись без часа, появившаяся сегодня, свежая"),
    ("⑥-1", "РАЗЛ.", case_6_1, "три слоя одним вызовом"),
    ("⑥-2", "РАЗЛ.", case_6_2, "ПРАВО и право"),
    ("⑥-3", "РАЗЛ.", case_6_3, "карточка #462"),
    ("⑥-4", "КОНТР.", case_6_4, "--layer warm"),
    ("⑥-5", "КОНТР.", case_6_5, "база без поля слоя: поиск"),
    ("⑥-6", "РАЗЛ.", case_6_6, "три слова врозь + --layer warm (частичное совпадение)"),
    ("②-1", "РАЗЛ.", case_2_1, "устаревшая ожидаемая версия"),
    ("②-2", "РАЗЛ.", case_2_2, "свежая ожидаемая версия"),
    ("③-1", "РАЗЛ.", case_3_1, "файл старше записи раздела"),
    ("③-2", "РАЗЛ.", case_3_2, "свежий файл"),
]
BY_NUM = {c[0]: c[2] for c in CASES}

failures = []


def check(num, ok, said, kind=""):
    tag = f"[{kind}] " if kind else ""
    print(f"{'✅' if ok else '🔴'} {num} {tag}{said}")
    if not ok:
        failures.append(f"{num} {said}")
    return ok


def safe(fn, T):
    """Случай, упавший исключением, — провал с причиной, а не обрыв всей приёмки."""
    try:
        return fn(T)
    except AssertionError:
        raise                       # вызов вне стенда — не провал случая, а сорванная приёмка
    except Exception as e:          # noqa: BLE001
        return False, f"случай упал: {type(e).__name__}: {e}"


try:
    TEMPLATES = build_templates()
    print(f"   стенд: подставные базы «со слоем» и «без слоя» готовы; шаг схемы наведён файлом "
          f"{MIGRATION.name} из испытуемого дерева")

    # предварительно: инструменты стартуют
    for key, tool in TOOLS.items():
        code, out = run_plain(tool, "--help")
        if code != 0:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: {tool.name} не стартовал (код {code}):\n{out[:600]}")
            sys.exit(mezo_stand.finish(2))

    healthy = Ctx(dict(TOOLS))
    results = {}
    for num, kind, fn, _name in CASES:
        ok, said = safe(fn, healthy)
        results[num] = ok
        check(num, ok, said, kind)

    # ══ ОБРАТНЫЙ ХОД: пять нарочных поломок в КОПИЯХ инструментов ═════════════════════════
    print()
    print("── нарочные поломки: приёмка сама правит КОПИЮ инструмента на стенде ──")
    breaks_ok = 0
    # (поломка → какой инструмент подменён; случай, который обязан не пройти; те, что обязаны пройти)
    PLAN = {"П1": ("②-1", ["③-1", "④-1", "⑥-1"]), "П2": ("③-1", ["②-1"]),
            "П3": ("⑥-1", ["②-1"]), "П4": ("④-1", ["⑥-1"]),
            "П5": ("⑥-6", ["⑥-1", "②-1"]),
            "П6": ("④-13", ["④-14", "④-10", "④-1"]),
            "П7": ("④-14", ["④-13", "④-10", "④-1"]),
            "П8": ("④-15", ["④-13", "④-16", "④-1"]),
            "П9": ("④-16", ["④-15", "④-13", "④-1"])}
    for label, (tool_name, anchor, replacement) in BREAKS.items():
        src = next(p for p in TOOLS.values() if p.name == tool_name)
        bdir = STAND / f"broken-{label}"
        copy = mezo_stand.copy_tool(src, bdir)
        # соседи, подключаемые по пути файла, а не по имени, копируются отдельно
        if tool_name == "find-phoenix.py":
            mezo_stand.copy_tool(TREE / "scripts" / "read-phoenix.py", bdir)
            mezo_stand.copy_tool(TREE / "vnext" / "prototype" / "memory-archive.py", bdir)
        if tool_name == "memory-records.py":
            mezo_stand.copy_tool(TREE / "vnext" / "prototype" / "memory-archive.py", bdir)
            mezo_stand.copy_tool(GUARD, bdir)
        text = copy.read_text(encoding="utf-8")
        hits = text.count(anchor)
        if hits != 1:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: якорь поломки {label} нашёлся {hits} раз (ждали ровно один) в "
                  f"{tool_name}. Это НЕ «защита цела»: без поломки обратный ход ничего не доказывает.")
            print(f"   якорь: {anchor.strip()[:120]}")
            sys.exit(mezo_stand.finish(2))
        copy.write_text(text.replace(anchor, replacement), encoding="utf-8")
        tools = dict(TOOLS)
        key = {"save-phoenix.py": "save", "find-phoenix.py": "find", "memory-records.py": "records"}[tool_name]
        tools[key] = copy
        broken = Ctx(tools)

        # «поломанная копия ЗАПУСТИЛАСЬ»: числа, а не падение
        if label in ("П1", "П2"):
            db = new_db("layered")
            code, out = save_file(broken, db, "plan", save_body(500, "проба поломки"), "probe")
            started = code == 0 and "OK phoenix/" in out
            said = f"поломанная копия запустилась: код {code} (ждали 0) · строка записи есть: " \
                   f"{'да' if 'OK phoenix/' in out else 'НЕТ'}"
        elif label in ("П3", "П5"):
            db = new_db("layered")
            if label == "П3":
                plant_three(db, "хризолит")
                code, out = call(broken.t["find"], db, "хризолит")
            else:
                plant(db, "state", [rec(300, "## Пара", body="## Пара\nздесь про хризолит и про гранат\n")])
                code, out = call(broken.t["find"], db, "хризолит гранат аметист", "--layer", "warm")
            m = re.search(r"ОТВЕТ: (\d+) записей", out)
            started = code == 0 and m is not None and int(m.group(1)) >= 1
            said = f"поломанная копия запустилась: код {code} (ждали 0) · записей в ответе " \
                   f"{m.group(1) if m else 'нет строки ответа'}"
        else:
            limit = volume_limit()
            db = new_db("layered")
            plant(db, "state", over_threshold_records(limit))
            code, out = call(broken.t["records"], db, "--section", "state", "--сжать")
            m = re.search(r"унесено (\d+) записей", out)
            started = code == 0 and m is not None and int(m.group(1)) > 0
            said = f"поломанная копия запустилась: код {code} (ждали 0) · в печати унесено " \
                   f"{m.group(1) if m else 'строки итога нет'}"
        check(f"{label}-0", started, said, "КОНТР.")

        own, others = PLAN[label]
        own_ok, own_said = safe(BY_NUM[own], broken)
        other_res = [(n,) + safe(BY_NUM[n], broken) for n in others]
        good = started and (not own_ok) and all(r[1] for r in other_res)
        print(f"   · на поломке {label}: {own} {'ПРОШЁЛ' if own_ok else 'не прошёл'} — {own_said}")
        for n, ok_n, said_n in other_res:
            print(f"   · на поломке {label}: {n} {'прошёл' if ok_n else 'НЕ ПРОШЁЛ'} — {said_n}")
        check(label, good,
              f"поломка валит РОВНО свой случай: не прошёл {own if not own_ok else 'никто (ждали ' + own + ')'}"
              f" · прошли {', '.join(n for n, ok_n, _s in other_res if ok_n) or 'никто'}"
              f" (ждали {', '.join(others)})", "РАЗЛ.")
        breaks_ok += 1 if good else 0

    def part(prefix):
        nums = [c[0] for c in CASES if c[0].startswith(prefix)]
        return sum(1 for n in nums if results.get(n)), len(nums)

    a, an = part("④")
    b, bn = part("⑥")
    k_nums = [c[0] for c in CASES if c[0][0] in "②③"]
    k = sum(1 for n in k_nums if results.get(n))
    print()
    print(f"ИТОГ: ④ {a} из {an} · ⑥ {b} из {bn} · ② ③ {k} из {len(k_nums)} · поломки {breaks_ok} из {len(BREAKS)}")
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {len(failures)}")
        for f in failures:
            print(f"   · {f}")
    else:
        print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — сжатие пишет то, что печатает, свежие записи не уносит, "
              "поиск видит три слоя, защита записи раздела держит, каждая поломка валит ровно свой случай.")
    print("⛔ Чего приёмка НЕ доказывает: она не гонит инструменты на живой базе и на её объёме "
          "(порог и слои судятся на посаженных записях); не судит, КАКИЕ записи роль захочет унести "
          "(порядок ухода проверен по номерам, а не по смыслу; час соседней записи на настоящей памяти "
          "ролей, день появления записей, переживших пересборку, и границу «вчера» у полуночи UTC она "
          "не судит — это прогон на копиях памяти, карточка #796, пункт ③); не проверяет поиск на записях из слов "
          "с «ё» и на словах, написанных иным корнем; причину переноса (--why) в базе не хранит и "
          "потому не проверяет.")
    sys.exit(mezo_stand.finish(1 if failures else 0))
finally:
    mezo_stand.release(STAND)
