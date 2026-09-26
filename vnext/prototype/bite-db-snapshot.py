#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-db-snapshot.py — приёмка карточки #505: копия живой базы для опыта снимается
СОГЛАСОВАННО (штатным способом sqlite3, переносящим хвост журнала), в ОДНОМ общем месте
(mezo_stand.snapshot_db), а не копированием файла в каждой приёмке своей рукой.

БЕДА, ПРОТИВ КОТОРОЙ ЭТО ПИШЕТСЯ (два живых случая — 30.08 и 13.09, разобраны в карточке):
живая база работает в режиме WAL — свежие записи лежат в mezosync.db-wal РЯДОМ с основным
файлом. `shutil.copy(живая_база, копия)` копирует ТОЛЬКО основной файл: то, что ещё не
перенесено из журнала, в копию не попадает. Копия при этом НЕ отказывает и не портится —
она открывается, отвечает на запросы и молча даёт СТАРОЕ состояние. Проверка, построенная
на такой копии, краснеет по ПОСТОРОННЕЙ причине, и её красное неотличимо от настоящей
находки — 30.08 bite-phoenix-truncation-named.py дал 5 из 7 сразу после чужой записи
в живую базу и 7 из 7 через 6 минут, без единой правки кода.

Случаи (различающий = обязан ответить ИНАЧЕ прежнему способу, а не одинаково с ним):
  ① класс СУЩЕСТВУЕТ: своя песочная база в WAL, запись A, сброс журнала, держащий
     читатель, запись B — ПРЕЖНИЙ способ (копия одного основного файла) не видит B.
     ТРЕТИЙ ИСХОД: если прежний способ B всё же увидел — гипотеза карточки не
     подтвердилась НА ЭТОМ опыте, и приёмка обязана сказать это словом, а не подогнать.
  ② НОВЫЙ способ (mezo_stand.snapshot_db) на ТОМ ЖЕ опыте видит B.
  ③ ЖИВОЙ СЛУЧАЙ COORD на НАСТОЯЩЕЙ схеме: копия базы стенда через snapshot_db,
     lease.py стенда take/release на write-message.py (MEZO_ROLE=COORD) при держащем
     читателе — прежний способ видит released_at=None, новый видит время снятия.
  ④ ОДНО ОБЩЕЕ МЕСТО: разбор деревом (ast) обоих каталогов — ни одна приёмка не
     копирует живую базу иначе, чем через mezo_stand.snapshot_db.
  ⑤ НАРОЧНАЯ ПОЛОМКА (а), на КОПИИ КОПИИ mezo_stand.py: тело snapshot_db заменено
     копированием файла → под этой испорченной копией ② и ③ обязаны провалиться, ① —
     устоять (он прежний способ вообще не через snapshot_db зовёт).
  ⑥ НАРОЧНАЯ ПОЛОМКА (б), на КОПИИ КОПИИ каталога приёмок: подложена приёмка со
     СТАРЫМ копированием живой базы → разбор ④ обязан её найти.
  ⑦ ВОЗВРАТ PROTO по карточке #505 (ошибка была в самой заявке п.2 — «если цель
     уже есть, отказ»): цель УЖЕ СУЩЕСТВУЕТ, это база SQLite СО СВОИМ СТАРЫМ содержимым
     (и свой -wal с незаписанным хвостом) → snapshot_db пишет ПОВЕРХ согласованно: после
     снимка в цели РОВНО состояние источника — новая строка есть, старые строки цели ушли.
  ⑧ ВСТРЕЧНЫЙ к ⑦: цель существует, но НЕ база SQLite (текстовый файл) → громкий отказ
     с путём, файл НЕ ТРОНУТ (без ⑦ отказ на "не-базе" мог бы значить и "нельзя писать
     поверх вообще", а не именно "это не база").

Живая база и живые scripts НЕ ТРОГАЮТСЯ: весь опыт — на собственных однодневных базах
и на стенде; база контура (найденного обычным способом — MEZO_CONTAINER или подъём
от расположения) только читается снимком, чтобы у стенда была настоящая схема.

ВОЗВРАТ COORD 14.09 (карточка #505 → заведена #624): разбор ④ не видел ЧЕТЫРЕ формы,
которыми 4 приёмки вычисляли путь к живой базе, — они не подпадали ни под одну названную
границу (не shell, не имя на лету, не параметр извне, не exec), а тем не менее ускользали:
  ⑥-а IfExp: `pathlib.Path(a.db) if a.db else mezo_paths.live_db()` — жив, если ХОТЬ ОДНА ветка живая
  ⑥-б Subscript: `Path(__file__).resolve().parents[N]` — след берётся у значения, не у индекса
  ⑥-в атрибутная форма `pathlib.Path(__file__)` (через import pathlib) — как бы `Path(__file__)`
  ⑥-г след, полученный ВНУТРИ if/try/with/for/while (например, `live = Path(mezo_paths.live_db())`
      под try, за которым идёт `shutil.copy2(live, …)` уже ПОСЛЕ блока) — раньше ветки сканировались
      на КОПИИ среды присвоений, и след терялся на выходе из блока (пропущен bite-empty-data-reasons)
  ⑥-д присвоение кортежем `a, b = X, Y` — попарно, а не как единое значение
Случаи ⑨ и ⑩ ниже — на КАЖДУЮ из этих форм подложенный файл, который разбор ④ обязан найти,
и нарочная поломка, снимающая РОВНО эту способность (переключателем NEW_FORM_TOGGLES,
на копии копии этого файла) — она обязана провалить ровно подложенный случай своей формы.

    python <абсолютный путь>/bite-db-snapshot.py
"""
from __future__ import annotations

import ast
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

CASES = DIFFER = 0
NL = chr(10)


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def old_copy(src, dst) -> Path:
    """ПРЕЖНИЙ способ — тот самый, из-за которого заведена карточка #505:
    копирование ОДНОГО основного файла, без переноса хвоста журнала."""
    dst = Path(dst)
    shutil.copy(Path(src), dst)
    return dst


# ═══════════════════════════════ опыт с держащим читателем ═══════════════════════════════

def build_wal_db(path: Path) -> None:
    """Свежая однодневная база в режиме WAL с одной табличкой — для опытов ①②."""
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (k TEXT PRIMARY KEY, v TEXT)")
    con.commit()
    con.close()


def checkpoint(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def run_wal_tail_experiment(db_path: Path, snapshot_fn):
    """Опыт из критерия карточки: запись A → сброс журнала → держащий читатель →
    запись B → сравнить, что видит ПРЕЖНИЙ способ и что видит snapshot_fn.

    Возвращает (wal_size_before_copy, old_sees_b, new_sees_b).
    snapshot_fn(src, dst) -> Path — подменяемая функция (для случая ⑤ передают испорченную копию).
    """
    build_wal_db(db_path)
    con_w = sqlite3.connect(str(db_path))
    con_w.execute("INSERT INTO t VALUES ('a', 'запись A')")
    con_w.commit()
    checkpoint(db_path)                         # журнал чист — запись A уже в основном файле

    # держащий читатель: снимок ДО записи B; держит его открытым, пока не закончим сравнение
    holder = sqlite3.connect(str(db_path))
    holder.execute("BEGIN")
    holder.execute("SELECT COUNT(*) FROM t").fetchone()

    con_w.execute("INSERT INTO t VALUES ('b', 'запись B')")
    con_w.commit()                              # уходит в -wal; держащий читатель не даёт её
    con_w.close()                                # доехать до основного файла

    wal_path = Path(str(db_path) + "-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    old_dst = db_path.with_name(db_path.stem + "-old.db")
    new_dst = db_path.with_name(db_path.stem + "-new.db")
    old_copy(db_path, old_dst)
    snapshot_fn(db_path, new_dst)

    def sees_b(p: Path) -> bool:
        c = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        row = c.execute("SELECT COUNT(*) FROM t WHERE k='b'").fetchone()
        c.close()
        return row[0] == 1

    old_sees_b = sees_b(old_dst)
    new_sees_b = sees_b(new_dst)

    holder.execute("ROLLBACK")
    holder.close()
    return wal_size, old_sees_b, new_sees_b


def cases_1_2(stand: Path, snapshot_fn=mezo_stand.snapshot_db, label=""):
    """Случаи ①② (или их повтор под испорченной копией ⑤). Возвращает (ok1, ok2, third_outcome)."""
    db_path = stand / "wal-tail.db"
    wal_size, old_sees_b, new_sees_b = run_wal_tail_experiment(db_path, snapshot_fn)
    suf = f" {label}" if label else ""

    print(f"   контроль «было на что смотреть»{suf}: размер -wal перед копированием = "
          f"{wal_size} байт")
    third_outcome = False
    if old_sees_b:
        third_outcome = True
        print("   🟡 ТРЕТИЙ ИСХОД: гипотеза карточки #505 НЕ ПОДТВЕРДИЛАСЬ на этом опыте — "
              "прежний способ увидел запись B. Причина не в хвосте журнала; искать заново, "
              "не подгонять зелёное.")
    ok1 = case(f"① класс СУЩЕСТВУЕТ{suf}: прежний способ НЕ видит запись, оставшуюся в -wal",
               (not old_sees_b) if not third_outcome else False,
               ("третий исход — см. строку выше" if third_outcome else
                "прежний способ скопировал только основной файл и не увидел запись B — "
                "ровно та беда, из-за которой заведена карточка #505"),
               differ=True)
    ok2 = case(f"② НОВЫЙ способ (mezo_stand.snapshot_db"
               f"{' — ИСПОРЧЕННАЯ КОПИЯ' if label else ''}){suf}: видит запись B",
               new_sees_b,
               "snapshot_db снимает согласованный снимок через sqlite3 backup API — "
               "хвост журнала переносится в цель" if not label else
               "под испорченной копией (тело = копирование файла) снимок должен быть "
               "ТАКИМ ЖЕ неполным, как у прежнего способа",
               differ=True)
    return ok1, ok2, third_outcome


# ═══════════════════════════════ случай ③: живой сценарий COORD ═══════════════════════════

def stage_case3(snapshot_fn=mezo_stand.snapshot_db, label=""):
    """Стенд с НАСТОЯЩЕЙ схемой (копия песочной базы контура) + lease.py и его соседи.

    Возвращает (wal_size, old_released_at, new_released_at).
    """
    root = mezo_stand.new("bite-db-snapshot-c3-")
    mezo = root / ".mezosync"
    (mezo / "scripts").mkdir(parents=True)

    live_scripts = mezo_paths.live_scripts(__file__)     # scripts КОНТУРА, на который
    lease_py = live_scripts / "lease.py"                  # указывает MEZO_CONTAINER (песок)
    mezo_stand.copy_tool(lease_py, mezo / "scripts")

    db_path = mezo / "mezosync.db"
    snapshot_fn(mezo_paths.live_db(__file__), db_path)     # семя стенда — уже ЧЕРЕЗ snapshot_db
    # ⚡ ПРАВКА (карточка #659). Опыт целиком стоит на «живая база работает в режиме WAL»
    # (см. докстринг файла) — держащий читатель ниже (BEGIN + SELECT, без commit) в
    # НЕ-WAL (rollback-journal) базе честно берёт разделяемую блокировку и НЕ отпускает
    # её до конца опыта, а release лизинга (отдельный процесс, lease.py, timeout=5) тогда
    # обязан упасть «database is locked» — не по вине lease.py и не по вине снимка, а
    # потому что сам стенд оказался не в том режиме, который весь опыт предполагает.
    # Замерено впрямую: schema/mezosync_v3.sql и новее (файл СОБИРАЕТСЯ из живой базы,
    # vnext/tools/gen-schema.py) не несут «PRAGMA journal_mode = WAL» — она была только
    # в рукописных v1/v2 и потерялась при переходе на автосборку; свежий контур пакета
    # (в отличие от давно живого контура Atlas) рождается НЕ в WAL. Чинить это в
    # init-group.py/gen-schema.py — вопрос ЗА пределами этой приёмки (общий для ВСЕХ
    # контуров, не только для стенда case③); здесь опыт делает СВОЙ стенд WAL сам —
    # ровно тем способом, каким это и раньше делала schema v1/v2, — и перестаёт зависеть
    # от режима источника.
    _wal_con = sqlite3.connect(str(db_path))
    _wal_con.execute("PRAGMA journal_mode=WAL")
    _wal_con.close()
    checkpoint(db_path)                                    # чистое состояние перед опытом

    env = mezo_stand.stand_env(root, MEZO_ROLE="COORD")

    take = subprocess.run(
        [sys.executable, str(mezo / "scripts" / "lease.py"), "take",
         "--role", "COORD", "--tools", "write-message.py",
         "--reason", "приёмка карточки #505: живой случай COORD (13.09), реплей на стенде",
         "--minutes", "60", "--db", str(db_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env)
    if take.returncode != 0:
        raise RuntimeError(f"take не удался: {(take.stdout or '') + (take.stderr or '')}")
    lease_id = None
    for tok in take.stdout.split():
        if tok.startswith("#"):
            lease_id = tok.lstrip("#")
            break
    if not lease_id:
        raise RuntimeError(f"не нашёл номер объявления в выводе take: {take.stdout}")
    checkpoint(db_path)                                    # take уже в основном файле

    holder = sqlite3.connect(str(db_path))
    holder.execute("BEGIN")
    holder.execute("SELECT COUNT(*) FROM tool_leases").fetchone()

    release = subprocess.run(
        [sys.executable, str(mezo / "scripts" / "lease.py"), "release",
         "--role", "COORD", "--id", lease_id,
         "--note", "приёмка карточки #505 — реплей на стенде, не в ленту",
         "--db", str(db_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env)
    if release.returncode != 0:
        holder.execute("ROLLBACK"); holder.close()
        raise RuntimeError(f"release не удался: {(release.stdout or '') + (release.stderr or '')}")

    wal_path = Path(str(db_path) + "-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    old_dst = mezo / "old-copy.db"
    new_dst = mezo / "new-copy.db"
    old_copy(db_path, old_dst)
    snapshot_fn(db_path, new_dst)

    def released_at(p: Path):
        c = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        v = c.execute("SELECT released_at FROM tool_leases WHERE id=?", (lease_id,)).fetchone()[0]
        c.close()
        return v

    old_val = released_at(old_dst)
    new_val = released_at(new_dst)

    holder.execute("ROLLBACK")
    holder.close()
    mezo_stand.release(root)
    return wal_size, old_val, new_val, lease_id


def case_3(snapshot_fn=mezo_stand.snapshot_db, label=""):
    """Оценивается ВСЕГДА против ПРАВИЛЬНОГО ожидания (old=None, new=время снятия) —
    и под испорченной копией (label), и без неё. Под испорченной копией эта оценка
    ЗАКОНОМЕРНО красная (new тоже остаётся None) — это и есть демонстрация, которую
    собирает case_5; подстраивать критерий под label было бы «подгонкой», которую
    запрещает карточка."""
    suf = f" {label}" if label else ""
    wal_size, old_val, new_val, lease_id = stage_case3(snapshot_fn, label)
    print(f"   контроль «было на что смотреть»{suf}: размер -wal перед копированием = "
          f"{wal_size} байт · объявление #{lease_id}")
    ok = (old_val is None) and (new_val is not None)
    return case(
        f"③ ЖИВОЙ СЛУЧАЙ COORD на настоящей схеме{suf}: прежний способ released_at="
        f"{old_val!r}, новый released_at={new_val!r}",
        ok,
        ("прежний способ видит released_at=None (снятие осталось в -wal), новый видит "
         "время снятия — ровно картина 13.09" if not label else
         "под испорченной копией (тело snapshot_db = копирование файла) новый способ "
         "ТОЖЕ отстал и видит released_at=None — здесь это ОЖИДАЕМО красное: так и "
         "должно провалиться"),
        differ=True)


# ═══════════════════════════════ случай ④: разбор деревом обоих каталогов ═════════════════

DIRECT_LIVE_FUNCS = {"live_db", "default_db", "resolve_db"}
WEAK_ROOT_FUNCS = {"mezo_root", "container_root"}
DB_LITERAL = "mezosync.db"
COPY_FUNCS = {"copy", "copy2", "copyfile", "copyfileobj"}

# ═══ ВОЗВРАТ COORD (карточка #505 → #624): пять способностей разбора ④, добавленных
# 14.09, — КАЖДАЯ переключаема ОТДЕЛЬНО, чтобы нарочная поломка могла снять ровно одну,
# не задевая соседние (case_10 ниже гоняет разбор с одним False за раз на копии копии
# этого файла — текстовая замена ОДНОГО "True" на "False", не переписывание тела функции).
NEW_FORM_TOGGLES = {
    "ifexp": True,          # ⑥-а: IfExp — живая хотя бы в одной ветке
    "subscript": True,      # ⑥-б: след Subscript берётся у значения (.parents[N] и подобные)
    "path_attr": True,      # ⑥-в: pathlib.Path(__file__) — атрибутная форма Path
    "branch_merge": True,   # ⑥-г: след из if/try/with/for/while выходит НАРУЖУ блока
    "tuple_assign": True,   # ⑥-д: присвоение кортежем a, b = X, Y — попарно
}
_TAINT_RANK = {"WEAK": 1, "LIVE": 2}


def _mezo_alias(tree):
    # ⚡ ПРАВКА (карточка #659): следим за алиасом ОБОИХ модулей (mezo_paths И
    # mezo_stand), не только mezo_paths — см. довод у "snapshot_db" в _taint() ниже.
    # Имена функций двух модулей не пересекаются (DIRECT_LIVE_FUNCS/WEAK_ROOT_FUNCS —
    # только mezo_paths, "snapshot_db" — только mezo_stand), поэтому один плоский набор
    # алиасов и один плоский словарь `imported` безопасны для обоих сразу.
    alias, imported = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in ("mezo_paths", "mezo_stand"):
                    alias.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module in ("mezo_paths", "mezo_stand"):
            for a in node.names:
                imported[a.asname or a.name] = a.name
    return alias, imported


def _taint(node, env, alias, imported):
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.Call):
        f = node.func
        fname = None
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in alias:
            fname = f.attr
        elif isinstance(f, ast.Name) and f.id in imported:
            fname = imported[f.id]
        # ⚡ ПРАВКА (карточка #659, ложная находка bite-save-alongside.py:59 — единственная
        # общая находка живого контура и пакета). mezo_stand.snapshot_db(...) — тот самый
        # ОДНИМ ОБЩИЙ способ снять живую базу, который эта же приёмка требует ото ВСЕХ
        # (карточка #505/#624); его РЕЗУЛЬТАТ — новый обособленный файл, а не живая база,
        # и читать его read_bytes()/etc — ровно то, ради чего snapshot_db заведён. Разбор
        # раньше НЕ отслеживал алиас mezo_stand вовсе и падал в общий разбор по аргументам
        # ниже — а там живой ПЕРВЫЙ аргумент (src) красил и РЕЗУЛЬТАТ вызова, будто это
        # тоже живая база. Замерено впрямую: без этой строки любой корректный вызов
        # snapshot_db(LIVE, …) остаётся ложно "LIVE".
        if fname == "snapshot_db":
            return None
        if fname in DIRECT_LIVE_FUNCS:
            return "LIVE"
        if fname in WEAK_ROOT_FUNCS:
            return "WEAK"
        # ⑥-в: pathlib.Path(__file__) — атрибутная форма (import pathlib; pathlib.Path(...)),
        # не только голое имя Path(...) (from pathlib import Path). Пример живой: ЗДЕСЬ/HERE в
        # bite-phoenix-records-autoincrement.py = pathlib.Path(__file__).resolve().parent.
        is_path_name = isinstance(f, ast.Name) and f.id == "Path"
        is_path_attr = (NEW_FORM_TOGGLES["path_attr"] and isinstance(f, ast.Attribute)
                        and f.attr == "Path")
        if ((is_path_name or is_path_attr) and node.args
                and isinstance(node.args[0], ast.Name) and node.args[0].id == "__file__"):
            return "WEAK"
        base = _taint(f, env, alias, imported)
        if base:
            return base
        for a in node.args:
            t = _taint(a, env, alias, imported)
            if t:
                return t
        return None
    if isinstance(node, ast.Attribute):
        return _taint(node.value, env, alias, imported)
    # ⑥-б: Subscript (Path(__file__).resolve().parents[1], список/кортеж по индексу) — след
    # берётся у ЗНАЧЕНИЯ, индекс/срез разбору не важен: он не решает, живая база или нет.
    if isinstance(node, ast.Subscript) and NEW_FORM_TOGGLES["subscript"]:
        return _taint(node.value, env, alias, imported)
    # ⑥-а: IfExp (`X if cond else Y`) — живая, если ХОТЬ ОДНА из веток живая: опыт не знает,
    # какая ветка исполнится, и осторожная сторона — считать выражение живым уже по одной.
    if isinstance(node, ast.IfExp) and NEW_FORM_TOGGLES["ifexp"]:
        t_body = _taint(node.body, env, alias, imported)
        t_orelse = _taint(node.orelse, env, alias, imported)
        if "LIVE" in (t_body, t_orelse):
            return "LIVE"
        return t_body or t_orelse
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        lt = _taint(node.left, env, alias, imported)
        if lt is None:
            return None
        if lt == "LIVE":
            return "LIVE"
        rs = node.right.value if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str) else None
        if rs == DB_LITERAL:
            return "LIVE"
        if rs is not None and rs.endswith(".py"):
            return None
        return "WEAK"
    return None


def _merge_branches(env, *branch_envs):
    """⑥-г: след, попавший в ЖИВУЮ базу хоть в ОДНОЙ ветке (if/try/with/for/while), живой
    и ПОСЛЕ блока — а не только внутри неё. Каждый branch_env — своя КОПИЯ среды на входе
    в ветку (наследует всё, что было ДО неё); объединение здесь — по приоритету LIVE > WEAK >
    ничего, и оно ЗАМЕНЯЕТ содержимое env целиком (а не только добавляет ключи), иначе имя,
    которое КАЖДАЯ ветка честно расчистила, осталось бы тронутым старым следом снаружи."""
    if not NEW_FORM_TOGGLES["branch_merge"]:
        return   # прежнее поведение: ветки не меняют внешнюю среду — след теряется на выходе
    merged = {}
    for be in branch_envs:
        for k, v in be.items():
            if v and _TAINT_RANK.get(v, 0) >= _TAINT_RANK.get(merged.get(k), 0):
                merged[k] = v
    env.clear()
    env.update(merged)


def _assign_one(tgt, value_node, env, alias, imported):
    t = _taint(value_node, env, alias, imported)
    if isinstance(tgt, ast.Name):
        if t:
            env[tgt.id] = t
        elif tgt.id in env:
            del env[tgt.id]


def _scan_assign(stmt, env, alias, imported, violations, relpath):
    # ⑥-д: `a, b = X, Y` — попарно: taint(a) от X, taint(b) от Y, а не общий taint кортежа
    # (которого у Tuple/List и не бывает). Без этого `live, why_not = None, "…"` не трогал
    # env ВООБЩЕ (targets[0] — Tuple, не Name), и старый след `live` мог остаться неверным.
    for tgt in stmt.targets:
        if (NEW_FORM_TOGGLES["tuple_assign"] and isinstance(tgt, (ast.Tuple, ast.List))
                and isinstance(stmt.value, (ast.Tuple, ast.List))
                and len(tgt.elts) == len(stmt.value.elts)):
            for sub_tgt, sub_val in zip(tgt.elts, stmt.value.elts):
                _assign_one(sub_tgt, sub_val, env, alias, imported)
        else:
            _assign_one(tgt, stmt.value, env, alias, imported)
    _scan_expr(stmt.value, env, alias, imported, violations, relpath)


def _scan_stmts(body, env, alias, imported, violations, relpath):
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            _scan_assign(stmt, env, alias, imported, violations, relpath)
        elif isinstance(stmt, ast.Expr):
            _scan_expr(stmt.value, env, alias, imported, violations, relpath)
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                t = _taint(item.context_expr, env, alias, imported)
                if isinstance(item.optional_vars, ast.Name) and t:
                    env[item.optional_vars.id] = t
                _scan_expr(item.context_expr, env, alias, imported, violations, relpath)
            _scan_stmts(stmt.body, env, alias, imported, violations, relpath)
        elif isinstance(stmt, ast.If):
            # ⑥-г: ветки сканируются на КОПИЯХ (входное состояние сохранено на случай, если
            # условие ложно/истинно) — но результат объединяется ОБРАТНО в env, а не теряется.
            body_env = dict(env)
            _scan_stmts(stmt.body, body_env, alias, imported, violations, relpath)
            else_env = dict(env)
            _scan_stmts(stmt.orelse, else_env, alias, imported, violations, relpath)
            _merge_branches(env, body_env, else_env)
        elif isinstance(stmt, (ast.For, ast.While)):
            body_env = dict(env)
            _scan_stmts(stmt.body, body_env, alias, imported, violations, relpath)
            else_env = dict(env)
            _scan_stmts(stmt.orelse, else_env, alias, imported, violations, relpath)
            _merge_branches(env, body_env, else_env)
        elif isinstance(stmt, ast.Try):
            body_env = dict(env)
            _scan_stmts(stmt.body, body_env, alias, imported, violations, relpath)
            handler_envs = []
            for h in stmt.handlers:
                h_env = dict(env)
                _scan_stmts(h.body, h_env, alias, imported, violations, relpath)
                handler_envs.append(h_env)
            # orelse исполняется только ПОСЛЕ успешного body — начинаем от его состояния
            orelse_env = dict(body_env)
            _scan_stmts(stmt.orelse, orelse_env, alias, imported, violations, relpath)
            combined = dict(env)
            _merge_branches(combined, body_env, orelse_env, *handler_envs)
            # finally исполняется ВСЕГДА, поверх того, что осталось после body/handlers/orelse
            final_env = dict(combined)
            _scan_stmts(stmt.finalbody, final_env, alias, imported, violations, relpath)
            _merge_branches(env, final_env)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _scan_stmts(stmt.body, dict(env), alias, imported, violations, relpath)


def _scan_expr(node, env, alias, imported, violations, relpath):
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        f = sub.func
        if (isinstance(f, ast.Attribute) and f.attr in COPY_FUNCS
                and isinstance(f.value, ast.Name) and f.value.id == "shutil"):
            src = sub.args[0] if sub.args else None
            if _taint(src, env, alias, imported) == "LIVE":
                violations.append((relpath, sub.lineno, f"shutil.{f.attr}"))
        elif isinstance(f, ast.Attribute) and f.attr == "read_bytes":
            if _taint(f.value, env, alias, imported) == "LIVE":
                violations.append((relpath, sub.lineno, "read_bytes"))


def scan_for_live_copies(roots) -> list[tuple[str, int, str]]:
    """Разбор деревом: список (файл, строка, вид) мест, копирующих ЖИВУЮ базу МИМО
    mezo_stand.snapshot_db. Пусто — значит ни одна найденная приёмка так не делает.
    """
    violations = []
    for root in roots:
        root = Path(root)
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                tree = ast.parse(text)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            alias, imported = _mezo_alias(tree)
            try:
                relpath = str(path.relative_to(root.parent))
            except ValueError:
                relpath = str(path)
            _scan_stmts(tree.body, {}, alias, imported, violations, relpath)
    return violations


SCAN_BOUNDARY = (
    "   ⛔ ГРАНИЦА (чего разбор НЕ умеет, названо прямо — как у mezo_paths._нужен_каталог_группы):\n"
    "      копирование через shell-команду (os.system/subprocess cp/copy), имя функции,\n"
    "      собранное на лету (getattr(mezo_paths, 'live_'+'db')), источник, переданный ПАРАМЕТРОМ\n"
    "      функции извне модуля (межпроцедурный след внутри одного файла разбирается, между\n"
    "      файлами — нет), и код, не являющийся статическим текстом (exec/eval).\n"
    "   ⛔ ВОЗВРАТ COORD 14.09 (карточка #624): атрибут аргумента argparse (`a.db`, `args.db`),\n"
    "      чьё значение по умолчанию — живая база (`default=str(LIVE_DB)` или функция вроде\n"
    "      resolve_db внутри самого argparse-объявления) — разбор НЕ отслеживает: цель\n"
    "      присвоения `args.db = …` не простое имя (ast.Attribute, не ast.Name), и связь\n"
    "      «--db по умолчанию живая» живёт внутри вызова add_argument, а не в дереве присвоений,\n"
    "      которое строит разбор. Ровно так остаётся невидимым guard-launcher-forms.py:243\n"
    "      (`shutil.copy(a.db, db_copy)` ← `--db` default=str(LIVE_DB)) — этот файл переведён\n"
    "      на mezo_stand.snapshot_db РУКОЙ, разбор ④ его правку не подтверждает и не обязан."
)


def case_4(roots, label=""):
    violations = scan_for_live_copies(roots)
    print(SCAN_BOUNDARY)
    if violations:
        print(f"   найдено нарушений: {len(violations)}")
        for relpath, line, kind in violations[:20]:
            print(f"      {relpath}:{line} {kind}")
    ok = (len(violations) == 0) if not label else (len(violations) > 0)
    suf = f" {label}" if label else ""
    return case(
        f"④ ОДНО ОБЩЕЕ МЕСТО{suf}: разбор деревом обоих каталогов",
        ok,
        (f"находок живой базы мимо snapshot_db: {len(violations)}" if not label else
         f"под нарочно подложенной старой приёмкой разбор обязан найти хотя бы одну "
         f"находку — нашёл {len(violations)}"),
        differ=True)


# ═══════════════════════════════ ⑤ нарочная поломка (а): испорченная копия mezo_stand.py ═

def make_mutant_snapshot_fn(stand: Path):
    """Копия КОПИИ mezo_stand.py, где тело snapshot_db заменено на копирование файла
    (прежний способ). Возвращает вызываемую snapshot_fn из ЭТОЙ ИСПОРЧЕННОЙ КОПИИ, а не
    из настоящего модуля — так случай ② и ③, вызванные под ней, обязаны провалиться."""
    real_src = Path(__file__).resolve().parent / "mezo_stand.py"
    text = real_src.read_text(encoding="utf-8")
    marker_start = "def snapshot_db(src, dst) -> Path:"
    marker_end = "\ndef finish(code: int) -> int:"
    i = text.index(marker_start)
    j = text.index(marker_end, i)
    mutant_body = (
        "def snapshot_db(src, dst) -> Path:\n"
        "    \"\"\"ИСПОРЧЕННАЯ КОПИЯ ⑤ карточки #505: тело нарочно заменено на ПРЕЖНИЙ "
        "способ (копирование файла), чтобы доказать, что случаи ②③ различают исправный "
        "и неисправный snapshot_db, а не всегда зеленеют.\"\"\"\n"
        "    src = Path(src); dst = Path(dst)\n"
        "    if dst.exists():\n"
        "        raise SystemExit(f'ERR: цель уже существует: {dst}')\n"
        "    shutil.copy(src, dst)\n"
        "    return dst\n"
    )
    mutated_text = text[:i] + mutant_body + text[j:]
    mutant_path = stand / "mezo_stand_mutant.py"
    mutant_path.write_text(mutated_text, encoding="utf-8")

    import importlib.util
    spec = importlib.util.spec_from_file_location("mezo_stand_mutant_505", mutant_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.snapshot_db, mutant_path


def case_5():
    stand = mezo_stand.new("bite-db-snapshot-c5-")
    mutant_fn, mutant_path = make_mutant_snapshot_fn(stand)
    print(f"   испорченная копия (копия копии): {mutant_path}")
    print("   реплей ①②③ под этой испорченной копией (тело snapshot_db = копирование файла):")
    ok1, ok2, third = cases_1_2(stand, snapshot_fn=mutant_fn, label="[⑤ порча]")
    ok3 = case_3(snapshot_fn=mutant_fn, label="[⑤ порча]")
    predicted = (ok1 is True) and (ok2 is False) and (ok3 is False) and (not third)
    mezo_stand.release(stand)
    return case(
        "⑤ НАРОЧНАЯ ПОЛОМКА (а): под испорченной копией snapshot_db картина ровно "
        "предсказанная",
        predicted,
        f"① {'✅' if ok1 else '🔴'} (обязан устоять) · ② {'✅' if ok2 else '🔴'} "
        f"(обязан провалиться) · ③ {'✅' if ok3 else '🔴'} (обязан провалиться)",
        differ=True)


# ═══════════════════════════════ ⑥ нарочная поломка (б): подложенная старая приёмка ═══════

BAD_TOOL_TEXT = '''# -*- coding: utf-8 -*-
"""bite-MUTANT-old-copy.py — НАРОЧНО подложенный файл (карточка #505, случай ⑥ приёмки
bite-db-snapshot.py). Не рабочий инструмент: существует только для проверки, что разбор
④ ловит старый способ копирования живой базы."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

LIVE_DB = mezo_paths.live_db(__file__)


def demo(dst):
    shutil.copy(LIVE_DB, dst)   # старый способ — ровно то, что должен найти разбор ④
'''


def case_6():
    stand = mezo_stand.new("bite-db-snapshot-c6-")
    mutant_dir = stand / "vnext-tools-mutant"
    real_dir = Path(__file__).resolve().parent
    shutil.copytree(real_dir, mutant_dir, ignore=shutil.ignore_patterns("__pycache__"))
    (mutant_dir / "bite-MUTANT-old-copy.py").write_text(BAD_TOOL_TEXT, encoding="utf-8")
    print(f"   испорченная копия каталога (копия копии): {mutant_dir}")
    ok = case_4([mutant_dir], label="[⑥ порча]")
    mezo_stand.release(stand)
    return ok


# ═══ ⑦⑧ возврат координатора: цель УЖЕ СУЩЕСТВУЕТ — снимок пишет поверх, а отказ ═══════════
# только когда цель не база SQLite (карточка #505, правка п.2 после возврата) ═══════════════

def case_7():
    """Цель — УЖЕ база SQLite со своим СТАРЫМ содержимым (и своим незаписанным хвостом
    в -wal). snapshot_db обязан снять снимок ПОВЕРХ: после него в цели ровно источник."""
    stand = mezo_stand.new("bite-db-snapshot-c7-")
    src = stand / "src.db"
    build_wal_db(src)
    con = sqlite3.connect(str(src))
    con.execute("INSERT INTO t VALUES ('b', 'запись B')")
    con.commit()
    con.close()
    checkpoint(src)   # источник чист и целиком содержит B

    dst = stand / "dst.db"
    build_wal_db(dst)
    con = sqlite3.connect(str(dst))
    con.execute("INSERT INTO t VALUES ('old1', 'старая запись 1')")
    con.commit()
    checkpoint(dst)                              # старая-1 в основном файле цели
    holder = sqlite3.connect(str(dst))            # держащий читатель — снимок ДО старой-2
    holder.execute("BEGIN")
    holder.execute("SELECT COUNT(*) FROM t").fetchone()
    con.execute("INSERT INTO t VALUES ('old2', 'старая запись 2, незаписанный хвост цели')")
    con.commit()
    con.close()
    dst_wal = Path(str(dst) + "-wal")
    dst_wal_size = dst_wal.stat().st_size if dst_wal.exists() else 0
    print(f"   контроль «было на что смотреть»: свой -wal ЦЕЛИ перед снимком = "
          f"{dst_wal_size} байт")

    mezo_stand.snapshot_db(src, dst)              # снимок ПОВЕРХ существующей цели
    holder.execute("ROLLBACK")
    holder.close()

    c = sqlite3.connect(f"file:{dst.as_posix()}?mode=ro", uri=True)
    rows = sorted(r[0] for r in c.execute("SELECT k FROM t").fetchall())
    c.close()
    mezo_stand.release(stand)

    ok = rows == ["b"]
    return case(
        "⑦ ВОЗВРАТ: цель уже база со старым содержимым — snapshot_db пишет ПОВЕРХ",
        ok,
        f"строки цели после снимка: {rows!r} — ожидается ['b'] (источник), без 'old1'/'old2'",
        differ=True)


def case_8():
    """ВСТРЕЧНЫЙ к ⑦: цель существует, но НЕ база SQLite — громкий отказ, файл НЕ ТРОНУТ."""
    stand = mezo_stand.new("bite-db-snapshot-c8-")
    src = stand / "src.db"
    build_wal_db(src)

    bad = stand / "not-a-db.db"
    text = "это обычный текстовый файл, не база SQLite — карточка #505, случай ⑧"
    bad.write_text(text, encoding="utf-8")
    before = bad.read_bytes()

    refused = False
    refusal_text = ""
    try:
        mezo_stand.snapshot_db(src, bad)
    except SystemExit as e:
        refused = True
        refusal_text = str(e)
    after = bad.read_bytes()
    mezo_stand.release(stand)

    ok = refused and (before == after) and ("не открывается как база" in refusal_text)
    return case(
        "⑧ ВСТРЕЧНЫЙ: цель существует, но НЕ база SQLite — отказ, файл не тронут",
        ok,
        f"отказ печатался: {refused} · файл не изменился: {before == after} · "
        f"текст отказа называет причину: {'не открывается как база' in refusal_text}",
        differ=True)


# ═══ ⑨⑩ ВОЗВРАТ COORD (карточка #505 → #624): пять новых форм, каждая — подложенный файл ══

NEW_FORM_SAMPLES = {
    "ifexp": (
        "bite-MUTANT-ifexp.py",
        '''# -*- coding: utf-8 -*-
"""bite-MUTANT-ifexp.py — НАРОЧНО подложенный файл (карточка #624, разбор ④, форма ⑥-а
IfExp): условное выражение, где ОДНА из веток — живая база. Не рабочий инструмент."""
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

DB_ARG = None
SRC = pathlib.Path(DB_ARG) if DB_ARG else mezo_paths.live_db(__file__)


def demo(dst):
    shutil.copyfile(SRC, dst)   # ветка else IfExp — живая; разбор ④ обязан найти
'''
    ),
    "subscript": (
        "bite-MUTANT-subscript.py",
        '''# -*- coding: utf-8 -*-
"""bite-MUTANT-subscript.py — НАРОЧНО подложенный файл (карточка #624, разбор ④, форма ⑥-б
Subscript): след живой базы берётся у ЗНАЧЕНИЯ Path(__file__).resolve().parents[N], не у
индекса. Не рабочий инструмент."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / ".mezosync" / "mezosync.db"


def demo(dst):
    shutil.copy2(LIVE, dst)   # корень из Subscript; разбор ④ обязан найти
'''
    ),
    "path_attr": (
        "bite-MUTANT-pathlib-attr.py",
        '''# -*- coding: utf-8 -*-
"""bite-MUTANT-pathlib-attr.py — НАРОЧНО подложенный файл (карточка #624, разбор ④, форма
⑥-в): pathlib.Path(__file__) атрибутной формой (import pathlib), а не Path(__file__) через
`from pathlib import Path`. Не рабочий инструмент."""
import pathlib
import shutil

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
LIVE = ROOT / ".mezosync" / "mezosync.db"


def demo(dst):
    shutil.copy2(LIVE, dst)   # HERE — атрибутная форма Path; разбор ④ обязан найти
'''
    ),
    "branch_merge": (
        "bite-MUTANT-branch-out.py",
        '''# -*- coding: utf-8 -*-
"""bite-MUTANT-branch-out.py — НАРОЧНО подложенный файл (карточка #624, разбор ④, форма
⑥-г): след живой базы, полученный ВНУТРИ try/if, используется ПОСЛЕ блока — разбор обязан
пронести его наружу. Не рабочий инструмент."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402


def demo(dst):
    live = None
    try:
        live = Path(mezo_paths.live_db())
        if not live.exists():
            live, reason = None, "нет файла"
    except Exception as e:
        reason = str(e)
    if live is not None:
        shutil.copy2(live, dst)   # след из try/if, живёт ПОСЛЕ блока; разбор ④ обязан найти
'''
    ),
    "tuple_assign": (
        "bite-MUTANT-tuple-assign.py",
        '''# -*- coding: utf-8 -*-
"""bite-MUTANT-tuple-assign.py — НАРОЧНО подложенный файл (карточка #624, разбор ④, форма
⑥-д): присвоение кортежем `a, b = X, Y` — попарно. Не рабочий инструмент."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

src, note = mezo_paths.live_db(), "источник — живая база"


def demo(dst):
    shutil.copyfile(src, dst)   # taint из присвоения кортежем; разбор ④ обязан найти
'''
    ),
}


def _plant_new_forms(dir_path: Path, only=None):
    """Положить подложенные файлы новых форм (все или один по ключу only) в каталог."""
    for key, (fname, text) in NEW_FORM_SAMPLES.items():
        if only is not None and key != only:
            continue
        (dir_path / fname).write_text(text, encoding="utf-8")


def case_9():
    """⑨ НОВЫЕ ФОРМЫ (карточка #624): на КАЖДУЮ из пяти — подложенный файл; разбор ④ ПОЛНЫМ
    составом (живой NEW_FORM_TOGGLES, не испорченная копия) обязан найти КАЖДЫЙ."""
    stand = mezo_stand.new("bite-db-snapshot-c9-")
    forms_dir = stand / "new-forms"
    forms_dir.mkdir()
    _plant_new_forms(forms_dir)
    violations = scan_for_live_copies([forms_dir])
    found_files = {Path(relpath).name for relpath, _, _ in violations}
    print(f"   подложено форм: {len(NEW_FORM_SAMPLES)} · разбор нашёл нарушений: {len(violations)}")
    ok = True
    for key, (fname, _) in NEW_FORM_SAMPLES.items():
        seen = fname in found_files
        ok = case(f"⑨ форма «{key}» ({fname}): разбор ④ находит", seen,
                   "" if seen else f"⛔ разбор НЕ нашёл {fname} среди {sorted(found_files)}",
                   differ=True) and ok
    mezo_stand.release(stand)
    return ok


def make_mutant_analyzer(stand: Path, disable_key: str):
    """Копия КОПИИ bite-db-snapshot.py, где ОДНА способность разбора ④ выключена
    ПЕРЕКЛЮЧАТЕЛЕМ (замена одного "True" на "False" в NEW_FORM_TOGGLES) — не переписыванием
    тела функции, чтобы поломка задевала РОВНО одну способность, а не соседние. mezo_paths и
    mezo_stand уже загружены в ЭТОМ процессе (sys.modules): мутанту не нужны их файлы рядом,
    import переиспользует то, что уже загружено — как у case_5 с mezo_stand.py."""
    import importlib.util
    real_src = Path(__file__).resolve()
    text = real_src.read_text(encoding="utf-8")
    marker = f'"{disable_key}": True,'
    if marker not in text:
        raise RuntimeError(f"переключатель «{disable_key}» не найден в тексте разбора")
    mutated = text.replace(marker, f'"{disable_key}": False,', 1)
    mutant_path = stand / f"bite_db_snapshot_mutant_{disable_key}.py"
    mutant_path.write_text(mutated, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"bite_db_snapshot_mutant_{disable_key}", mutant_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case_10():
    """⑩ ПОЛОМКА НА КАЖДУЮ НОВУЮ ВОЗМОЖНОСТЬ (карточка #624, на копии копии этого файла):
    снять способность по одной → проваливается РОВНО подложенный случай этой формы, четыре
    остальных остаются найдены — иначе поломка красила бы соседние формы за компанию."""
    stand = mezo_stand.new("bite-db-snapshot-c10-")
    forms_dir = stand / "new-forms"
    forms_dir.mkdir()
    _plant_new_forms(forms_dir)
    ok = True
    for key in NEW_FORM_TOGGLES:
        mutant_stand = stand / f"mutant-{key}"
        mutant_stand.mkdir()
        mod = make_mutant_analyzer(mutant_stand, key)
        violations = mod.scan_for_live_copies([forms_dir])
        found_files = {Path(relpath).name for relpath, _, _ in violations}
        all_files = {fname for fname, _ in NEW_FORM_SAMPLES.values()}
        expected_missing = NEW_FORM_SAMPLES[key][0]
        missing = all_files - found_files
        exact = missing == {expected_missing}
        ok = case(f"⑩ поломка «{key}»: провален РОВНО подложенный случай этой формы",
                   exact,
                   f"пропали: {sorted(missing) or '(ничего)'} — ожидали ровно {{{expected_missing!r}}}",
                   differ=True) and ok
    mezo_stand.release(stand)
    return ok


# ═══════════════════════════════ main ══════════════════════════════════════════════════

def main() -> int:
    # ⚖️ РЕШАЮЩИЙ ПРОГОН PROTO: здесь был отказ «MEZO_CONTAINER не задан … (песочный, не боевой)».
    # Отказ лишний: база контура в этой приёмке только ЧИТАЕТСЯ снимком (случай ③ сеет свой стенд
    # и пишет объявления в копию, случай ④ читает исходники), а соседние приёмки находят контур
    # обычным способом. Слова «не боевой» учили не гонять приёмку на живом — там её место.
    container = mezo_paths.container_root(__file__)
    print("ПРИЁМКА карточки #505: согласованная копия живой базы (mezo_stand.snapshot_db)")
    print(f"контур опыта: {container} — его база только читается снимком, "
          f"всё остальное — во временных каталогах\n")

    stand12 = mezo_stand.new("bite-db-snapshot-c12-")
    ok1, ok2, third = cases_1_2(stand12)
    mezo_stand.release(stand12)

    ok3 = case_3()
    roots = [Path(__file__).resolve().parent, mezo_paths.live_scripts(__file__)]
    # ВОЗВРАТ COORD (карточка #624): «корни разбора ④ — проверь, что туда входят оба каталога
    # ЦЕЛИКОМ, включая .mezosync/scripts/migrations». rglob("*.py") в scan_for_live_copies уже
    # рекурсивен — migrations лежит ВНУТРИ live_scripts() и никогда не исключался; печатаем
    # число найденных там файлов, чтобы это было утверждением, а не молчаливой надеждой.
    migrations_dir = roots[1] / "migrations"
    migrations_files = sorted(migrations_dir.rglob("*.py")) if migrations_dir.is_dir() else []
    print(f"   разбор ④: корень {roots[1]} включает migrations/ ЦЕЛИКОМ рекурсией (rglob) — "
          f"там {len(migrations_files)} файлов (карточка #624, возврат COORD)\n")
    ok4 = case_4(roots)
    ok5 = case_5()
    ok6 = case_6()
    ok7 = case_7()
    ok8 = case_8()
    ok9 = case_9()
    ok10 = case_10()

    ok = (ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7 and ok8 and ok9 and ok10
          and bool(migrations_files) and not third)

    print()
    print((f"✅ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok else
           f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
