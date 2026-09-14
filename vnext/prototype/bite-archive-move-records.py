#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-archive-move-records — приёмка карточки #627: перенос памяти в архив
(memory-archive.py --move) пересобирает слой записей (phoenix_records) ТЕМ ЖЕ ВЫЗОВОМ.

БЕДА (нашла PROTO 2026-09-14 15:20 UTC на своей памяти, backlog #627). move_to_archive()
укорачивает тело раздела в phoenix, кладёт унесённые куски в phoenix_archive и пишет
строку phoenix_history — всё одной транзакцией. Таблицу phoenix_records инструмент до
этой правки не трогал вовсе: записи оставались разобраны из ПРЕЖНЕГО (более длинного)
тела до следующего save-phoenix.py. Пока роль не сохранит память снова, записи несут
унесённый текст как «живой», и find-phoenix.py (ищет по phoenix_records) находит
в «живой памяти» то, что уже унесено в архив — ровно та путаница, для которой у поиска
есть отдельный исход «в живой памяти нет, в архиве есть» (код 4).

КРИТЕРИЙ (карточка #627, дословно): после memory-archive.py --move записи раздела
сходятся с телом знак в знак тем же вызовом (memory-records.py --собрать: сборка = тело),
без ручной пересборки; find-phoenix.py по слову, жившему только в унесённом куске, даёт
код 4 сразу после переноса. Отказ пересборки не отменяет перенос — громкое предупреждение.

Случаи:
  ① число записей раздела ПОСЛЕ --move = числу блоков ОСТАВШЕГОСЯ тела    РАЗЛИЧАЮЩИЙ
  ② memory-records.py --собрать сходится знак в знак (без ручной --пересобрать)
                                                                            РАЗЛИЧАЮЩИЙ
  ③ find-phoenix.py по слову из УНЕСЁННОГО куска → код 4, «в живой памяти нет,
     в архиве есть»                                                       РАЗЛИЧАЮЩИЙ
  ④ ВСТРЕЧНЫЙ: первый перенос раздела БЕЗ предшествующих записей (первый разбор,
     а не rebuild) — пересборка сама различает ветки и не отказывает            РАЗЛИЧАЮЩИЙ
  ⑤ НАРОЧНАЯ ПОЛОМКА «пересборку из переноса убрать» (на копии копии
     memory-archive.py): записи снова отстают числом — случай ① проваливается
     на поломанном инструменте                                            РАЗЛИЧАЮЩИЙ
  ⑥ НАРОЧНАЯ ПОЛОМКА «memory-records.py бросает исключение при пересборке»:
     перенос всё равно записан (✅ ПЕРЕНЕСЕНО в выводе, блок лёг в архив БД),
     предупреждение напечатано громко, код выхода --move — 0 (перенос не
     проваливается из-за долга вторичного слоя)                          РАЗЛИЧАЮЩИЙ
  контроль: живая база НЕ ТРОНУТА этим прогоном

⚖️ ПОЧЕМУ ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ НОВЫЙ СЛУЧАЙ В bite-archive-move-look.py: та приёмка
судит ДРУГОЙ слой (archive_move_look() в read-phoenix.py — согласование confirmed_at/
saved_at), и её якоря (ARCHIVE_HISTORY_BLOCK и др.) уже держат тонкий баланс десятка
нарочных поломок. Предмет карточки #627 — phoenix_records, слой, которого та приёмка
вообще не касается. Смешивание в один файл усложнило бы обе приёмки без выгоды.

⛔ Живого контура НЕ касается: save-phoenix / memory-archive / memory-records /
   find-phoenix зовутся ТОЛЬКО на КОПИЯХ базы (sqlite3 backup API из режима
   только-чтения), с явным --db на копию. Живая mezosync.db читается напрямую
   (mode=ro) лишь для контрольного числа до/после.

⚠️ Случаи ⑤ и ⑥ проверяют НАЛИЧИЕ починки карточки #627 (анкер REBUILD_CALL_LINE и
   сам приём с memory-records.py-соседом) — на версии memory-archive.py ДО этой
   починки они честно ОБРЫВАЮТ прогон (⛔ НЕ ЗАПУСТИЛАСЬ), а не красятся: ловить им
   там нечего, предмета (вызова пересборки) ещё нет. Случаи ①–④ на версии ДО починки
   красятся (🔴) как обычные различающие случаи — именно они и доказывают, что новые
   случаи различают.

    python <КОНТУР>/vnext-tools/bite-archive-move-records.py
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — импорт из vnext-tools (своя копия), как велит карточка

SCRIPTS = mezo_paths.live_scripts()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402 — стенд из S (.mezosync/scripts), как велит карточка

LIVE_DB = mezo_paths.live_db()
CONTAINER_ROOT = mezo_paths.container_root(__file__)  # для find_env() — см. её докстринг
SAVE = SCRIPTS / "save-phoenix.py"
FIND = SCRIPTS / "find-phoenix.py"
ARCHIVE = pathlib.Path(__file__).resolve().parent / "memory-archive.py"
RECORDS = pathlib.Path(__file__).resolve().parent / "memory-records.py"

for _tool in (SAVE, FIND, ARCHIVE, RECORDS):
    if not _tool.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {_tool}")

ROLE = "BITE627"
SECTION = "state"

OK = FAIL = 0


def case(title, ok, detail=""):
    global OK, FAIL
    print(("✅" if ok else "🔴"), title)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if ok else 0), FAIL + (0 if ok else 1)
    return ok


def live_control_state():
    """Контрольное число живой базы — ТОЛЬКО ЧТЕНИЕ, для проверки «не тронуто» (тот же
    приём, что и bite-archive-move-look.py: значение СНИМАЕТСЯ, а не вписано числом —
    иначе законная работа ДРУГОЙ роли между прогонами красила бы контроль не по своей
    причине).

    None — в ЭТОЙ живой базе нет слоя записей (таблицы phoenix_records): карточка #632,
    находка COORD 2026-09-14 — контур, собранный init-group из клона пакета, до шага
    20260904-phoenix-records.py ещё не дорос, и голый SELECT ронял ЗАГРУЗКУ ЭТОГО ФАЙЛА
    трассировкой sqlite3.OperationalError на любом прогоне. Таблицы нет — не отказ
    приёмки, а факт о контуре; отказ печатает вызывающий, словами, а не трассировкой."""
    con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    try:
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='phoenix_records'"
        ).fetchone():
            return None
        return con.execute("SELECT COUNT(*) FROM phoenix_records").fetchone()[0]
    finally:
        con.close()


LIVE_BEFORE = live_control_state()
if LIVE_BEFORE is None:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в живой базе этого контура нет слоя записей (таблицы "
             f"phoenix_records) — контрольное число «живая база не тронута» снять не с "
             f"чего.\n   База: {LIVE_DB}\n   Накати шаг схемы 20260904-phoenix-records.py "
             f"и повтори.")


def find_env() -> dict:
    """Среда для find-phoenix.py: ей нужен MEZO_CONTAINER на РЕАЛЬНЫЙ контейнер, а не
    на каталог случая. Данные идут через явный --db на КОПИЮ (это по-прежнему только
    чтение живой базы) — а вот своего соседа memory-archive.py find-phoenix.py находит
    ПО КОНТЕЙНЕРУ (CONTAINER_ROOT вычисляется у неё при загрузке модуля, до разбора
    --db) — правилу свода это и есть «приёмке, ищущей контур только для ЧТЕНИЯ, нужен
    MEZO_CONTAINER=<КОНТУР>» (helper-rules.md). CONTAINER_ROOT вычислен один раз
    ниже (см. переменную), а не впечатан литералом машины."""
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_CONTAINER=str(CONTAINER_ROOT))


def stand_env(container: pathlib.Path) -> dict:
    """Среда для всего, что запускается на стенде: контейнер — САМ стенд, а не
    унаследованный от вызывающего (урок 13.09: унаследованная MEZO_CONTAINER заставила
    стенд писать в живой контур)."""
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_CONTAINER=str(container))


def fresh_case_db(case_dir: pathlib.Path) -> pathlib.Path:
    """Копия живой базы В ЭТОТ каталог случая — через sqlite3 backup API, источник
    открыт ТОЛЬКО ДЛЯ ЧТЕНИЯ. Живого файла эта функция не пишет ни при каких путях."""
    mezosync_dir = case_dir / ".mezosync"
    mezosync_dir.mkdir(parents=True, exist_ok=True)
    db = mezosync_dir / "mezosync.db"
    mezo_stand.snapshot_db(LIVE_DB, db)
    return db


def run(tool: pathlib.Path, *args, env: dict, timeout=60):
    r = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ⚖️ слово, живущее ТОЛЬКО в блоке два (тот, что унесём) — по нему судим find-phoenix.py.
# Придумано, а не взято из словаря: не должно случайно встретиться в чужой живой памяти.
ONLY_ARCHIVED_WORD = "жаборазметчик627"


def make_body(tag: str) -> str:
    """Тело с ТРЕМЯ заголовками «## » — резка по заголовкам детерминирована (заголовков
    ⩾ 2), --move 2 всегда переносит РОВНО второй блок, где живёт ONLY_ARCHIVED_WORD."""
    return (
        f"## Блок один {tag}\n"
        + ("Текст первого блока, довольно длинный, чтобы не сработала защита от "
           "обвала объёма. " * 6) + "\n\n"
        + f"## Блок два {tag}\n"
        + f"Слово, которое встретится ТОЛЬКО тут: {ONLY_ARCHIVED_WORD}.\n"
        + ("Текст второго блока — тоже длинный, унесём его в архив. " * 6) + "\n\n"
        + f"## Блок три {tag}\n"
        + ("Текст третьего блока для полноты картины памяти. " * 6)
    )


def records_count(db: pathlib.Path, role=ROLE, section=SECTION) -> int:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM phoenix_records WHERE role=? AND section=?",
                           (role, section)).fetchone()[0]
    finally:
        con.close()


def blocks_in_body(db: pathlib.Path, role=ROLE, section=SECTION) -> int:
    """Число блоков, на которые режет ОСТАВШЕЕСЯ тело раздела резак ИСПЫТУЕМОГО
    memory-archive.py (ARCHIVE) — тем же приёмом (блоки/blocks), каким это делает
    memory-records.py, а не отдельным подсчётом на глаз."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        body = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                           (role, section)).fetchone()[0]
    finally:
        con.close()
    spec = importlib.util.spec_from_file_location("ma_records_count", ARCHIVE)
    ma = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ma)
    chunks, _ = ma.blocks(body)
    return len(chunks)


# ═══════════════════════════════════════════════════════════════════════════════
stand = mezo_stand.new("bite-627-archive-move-records-")

# ── ①②③ ЖИВОЙ ПУТЬ: сохранить → перенести блок два → судить ────────────────────
dir1 = stand / "case1"
db1 = fresh_case_db(dir1)
env1 = stand_env(dir1)
body1 = dir1 / "body1.md"
body1.write_text(make_body("①②③"), encoding="utf-8")

rc, out_save = run(SAVE, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                   "--file", str(body1), env=env1)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: save-phoenix не сохранил тело случая ①②③:\n{out_save}")

rc, out_move1 = run(ARCHIVE, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                    "--move", "2", "--actor", ROLE, env=env1)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ①②③:\n{out_move1}")

case("① пересборка сама, БЕЗ ручной --пересобрать: вывод переноса несёт строку-итог «записи раздела»",
     "записи раздела:" in out_move1,
     f"вывод переноса:\n{out_move1}")

n_blocks1 = blocks_in_body(db1)
n_records1 = records_count(db1)
case(f"① число записей раздела ПОСЛЕ --move = числу блоков оставшегося тела "
     f"({n_records1} = {n_blocks1})",
     n_records1 == n_blocks1,
     f"блоков в теле {n_blocks1} · записей в phoenix_records {n_records1}")

rc, out_assemble1 = run(RECORDS, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                        "--собрать", env=env1)
case("② memory-records.py --собрать сходится знак в знак, БЕЗ ручной --пересобрать",
     rc == 0 and "СОВПАДАЕТ ЗНАК В ЗНАК" in out_assemble1,
     f"код {rc}:\n{out_assemble1}")

rc, out_find1 = run(FIND, "--db", str(db1), "--role", ROLE, ONLY_ARCHIVED_WORD, env=find_env())
case("③ find-phoenix по слову из УНЕСЁННОГО куска: код 4, «в живой памяти нет, в архиве есть»",
     rc == 4 and "в живой памяти нет, в архиве есть" in out_find1,
     f"код {rc}:\n{out_find1}")

# ── ④ ВСТРЕЧНЫЙ: первый перенос раздела БЕЗ предшествующих записей ──────────
# ⚖️ save-phoenix.py сама зовёт --разобрать первым сохранением (карточка #525) — чтобы
# честно поставить «записей ещё не было», стираем их рукой ПОСЛЕ сохранения (прямой SQL,
# как поступает bite-memory-records.py при порче на КОПИИ). Без этого случая не видно,
# что _rebuild_records_after_move() сама различает «первый разбор» и rebuild — если бы
# она ошибочно звала ТОЛЬКО rebuild() (который отказывает при нуле прежних записей —
# см. parse()/rebuild() memory-records.py), первый перенос в жизни роли ломал бы
# пересборку систематически, и об этом узнавали бы только через сутки.
dir4 = stand / "case4"
db4 = fresh_case_db(dir4)
env4 = stand_env(dir4)
ROLE4 = "BITE627B"
body4 = dir4 / "body4.md"
body4.write_text(make_body("④"), encoding="utf-8")
rc, out_save4 = run(SAVE, "--db", str(db4), "--role", ROLE4, "--section", SECTION,
                    "--file", str(body4), env=env4)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: save-phoenix не сохранил тело случая ④:\n{out_save4}")
con4 = sqlite3.connect(str(db4))
con4.execute("DELETE FROM phoenix_records WHERE role=? AND section=?", (ROLE4, SECTION))
con4.commit()
con4.close()
rc, out_move4 = run(ARCHIVE, "--db", str(db4), "--role", ROLE4, "--section", SECTION,
                    "--move", "2", "--actor", ROLE4, env=env4)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ④:\n{out_move4}")
case("④ первый перенос БЕЗ предшествующих записей: пересборка сама различает "
     "первый разбор и rebuild (строка «первый разбор» есть, отказа нет)",
     "записи раздела:" in out_move4 and "первый разбор" in out_move4
     and "НЕ ПЕРЕСОБРАНЫ" not in out_move4,
     f"вывод переноса:\n{out_move4}")
n_blocks4 = blocks_in_body(db4, ROLE4, SECTION)
n_records4 = records_count(db4, ROLE4, SECTION)
case(f"④ и здесь число записей = числу блоков ({n_records4} = {n_blocks4})",
     n_records4 == n_blocks4)

# ── ⑤ НАРОЧНАЯ ПОЛОМКА: «пересборку из переноса убрать» (на копии копии) ────
broken_dir = stand / "broken-no-rebuild"
broken_tool = mezo_stand.copy_tool(ARCHIVE, broken_dir)
original_text = broken_tool.read_text(encoding="utf-8")
REBUILD_CALL_LINE = "    _rebuild_records_after_move(db_path, role, section, actor)\n"
if REBUILD_CALL_LINE not in original_text:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка вызова пересборки после переноса не найдена в "
             "испытуемом memory-archive.py — переименовали, поломка ⑤ бьёт мимо "
             "(это ожидаемо на версии ДО починки карточки #627 — предмета ещё нет)")
broken_text = original_text.replace(
    REBUILD_CALL_LINE,
    "    pass  # ПОРЧА bite-archive-move-records (⑤): пересборку из переноса убрали\n")
broken_tool.write_text(broken_text, encoding="utf-8")

dir5 = stand / "case5"
db5 = fresh_case_db(dir5)
env5 = stand_env(dir5)
body5 = dir5 / "body5.md"
body5.write_text(make_body("⑤"), encoding="utf-8")
run(SAVE, "--db", str(db5), "--role", ROLE, "--section", SECTION, "--file", str(body5), env=env5)
rc, out_move5 = run(broken_tool, "--db", str(db5), "--role", ROLE, "--section", SECTION,
                    "--move", "2", "--actor", ROLE, env=env5)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломанный memory-archive --move не перенёс блок "
             f"в случае ⑤:\n{out_move5}")
n_blocks5 = blocks_in_body(db5)
n_records5 = records_count(db5)
case(f"⑤ ПОЛОМКА «пересборку из переноса убрать» КРАСИТ случай ①: записи снова "
     f"ОТСТАЮТ ({n_records5} записей ≠ {n_blocks5} блоков оставшегося тела)",
     n_records5 != n_blocks5,
     "без нарочной поломки здесь стояло бы равенство; поломка вернула долечебное "
     "поведение — записи несут ПРЕЖНЕЕ (более длинное) тело")
case("⑤ поломка НЕ ТРОГАЕТ сам перенос: «✅ ПЕРЕНЕСЕНО» в выводе есть, строки-итога "
     "о записях — НЕТ (пересборка не звалась вовсе)",
     "✅ ПЕРЕНЕСЕНО" in out_move5 and "записи раздела:" not in out_move5)

# ── ⑥ НАРОЧНАЯ ПОЛОМКА: memory-records.py бросает исключение при пересборке ──
# Подкладываем ЧИСТУЮ (не порченную ⑤) копию ARCHIVE рядом с ПОДМЕНЁННЫМ
# memory-records.py в НОВЫЙ каталог: испытуемый memory-archive.py грузит соседа
# ИЗ СВОЕГО каталога (Path(__file__).with_name("memory-records.py")), значит в
# песочнице возьмёт песочный — приёмом bite-memory-archive.py против «испытываем
# не то, что чиним».
raise_dir = stand / "broken-records-raises"
raise_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(ARCHIVE, raise_dir / "memory-archive.py")
shutil.copy2(pathlib.Path(mezo_paths.__file__), raise_dir / "mezo_paths.py")
raising_records = (
    "def has_table(conn):\n"
    "    return True\n"
    "\n"
    "def rebuild(conn, role, section, actor):\n"
    "    raise RuntimeError('ПОРЧА bite-archive-move-records (⑥): memory-records.py "
    "бросает исключение нарочно')\n"
    "\n"
    "def parse(conn, role, section, actor):\n"
    "    raise RuntimeError('ПОРЧА bite-archive-move-records (⑥): memory-records.py "
    "бросает исключение нарочно')\n"
)
(raise_dir / "memory-records.py").write_text(raising_records, encoding="utf-8")
raising_archive = raise_dir / "memory-archive.py"

dir6 = stand / "case6"
db6 = fresh_case_db(dir6)
env6 = stand_env(dir6)
body6 = dir6 / "body6.md"
body6.write_text(make_body("⑥"), encoding="utf-8")
run(SAVE, "--db", str(db6), "--role", ROLE, "--section", SECTION, "--file", str(body6), env=env6)
rc, out_move6 = run(raising_archive, "--db", str(db6), "--role", ROLE, "--section", SECTION,
                    "--move", "2", "--actor", ROLE, env=env6)
case("⑥ ПОЛОМКА «пересборка бросает исключение»: перенос ВСЁ РАВНО записан "
     "(строка «✅ ПЕРЕНЕСЕНО» в выводе)",
     "✅ ПЕРЕНЕСЕНО" in out_move6, f"вывод:\n{out_move6}")
case("⑥ и предупреждение НАПЕЧАТАНО громко (не проглочено молча)",
     "НЕ ПЕРЕСОБРАНЫ" in out_move6 and "ПОРЧА bite-archive-move-records" in out_move6)
case("⑥ код выхода --move ОСТАЁТСЯ 0: отказ вторичного слоя не проваливает уже "
     "состоявшийся перенос (решение по образцу save-phoenix.py::rebuild_records — "
     "она тоже не влияет на код выхода)",
     rc == 0, f"код выхода {rc}")
con6 = sqlite3.connect(f"file:{db6.as_posix()}?mode=ro", uri=True)
try:
    archived6 = con6.execute(
        "SELECT COUNT(*) FROM phoenix_archive WHERE role=? AND section=?",
        (ROLE, SECTION)).fetchone()[0]
finally:
    con6.close()
case(f"⑥ блок ДЕЙСТВИТЕЛЬНО унесён в phoenix_archive БД, несмотря на поломку "
     f"записей (кусков в архиве: {archived6})",
     archived6 == 1)

# ── КОНТРОЛЬ: живая база НЕ ТРОНУТА ЭТИМ ПРОГОНОМ ────────────────────────────
LIVE_AFTER = live_control_state()
case("контроль: живая база НЕ ТРОНУТА (число записей phoenix_records то же, что до прогона)",
     LIVE_AFTER == LIVE_BEFORE,
     f"было {LIVE_BEFORE}; стало {LIVE_AFTER}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
