#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-archive-move-look — приёмка карточки #605: «взгляд» секции ПОСЛЕ штатного
переноса части памяти в архив (memory-archive.py --move) не красится ложным 🔴.

БЕДА. memory-archive.py --move (карточка #523) обновляет phoenix.saved_at и пишет
в phoenix_history строку с reason «archive-move: …», но confirmed_at НЕ трогает.
После переноса confirmed_at < saved_at, и read-phoenix.py читал это как «текст
менялся мимо инструмента» (🔴) — хотя роль сделала ПРАВИЛЬНОЕ штатное действие.
Живой случай: ING/plan (перенос 2026-09-07 16:47:18, подтверждение 16:36:29).

ЧТО ИСПЫТУЕТСЯ: функция archive_move_look() в read-phoenix.py (карточка #605) —
она обязана ПЕРЕОБЪЯСНИТЬ 🔴 в мирную строку, когда расхождение ЦЕЛИКОМ объяснено
цепочкой штатных переносов, и ОСТАВИТЬ 🔴, если между переносами текст правили
мимо инструмента (перенос не отмывает обход).

Случаи (различающий = read-phoenix обязан ответить ИНАЧЕ, а не одинаково):
  ① штатный перенос, взгляда до него не было → «после записи НЕ перечитывалось …;
     затем части унесены в архив штатным переносом …»                    РАЗЛИЧАЮЩИЙ
  ② «признано верным» ДО переноса → «перечитано и признано верным …; затем
     части унесены в архив штатным переносом …»                          РАЗЛИЧАЮЩИЙ
  ③ КОНТРОЛЬ ГРАНИЦЫ: правка тела мимо инструмента, переноса НЕ было → прежнее
     🔴 «СТАРШЕ текста» — как и до этой карточки                          РАЗЛИЧАЮЩИЙ
  ③б ВОЗВРАТ COORD (карточка #605 ③): обход ТОЙ ЖЕ ДЛИНЫ (слово на слово той же
     длины) в блоке, который переносом НЕ УНОСИТСЯ, ПОТОМ штатный перенос →
     🔴 остаётся: одной длины (prev_chars = body_chars соседа) мало, штатный
     перенос поверх такого обхода его тоже НЕ ОТМЫВАЕТ                    РАЗЛИЧАЮЩИЙ
  ③в ВОЗВРАТ COORD (карточка #605, случай E4c): обход ТОЙ ЖЕ ДЛИНЫ ВНУТРИ блока,
     который ТУТ ЖЕ уносится штатным переносом → 🔴 остаётся: тело раздела
     после переноса ЧИСТОЕ (подмена уехала целиком со своим блоком — ни длина,
     ни подпоследовательность строк ОСТАВШЕГОСЯ тела её не видят), но унесённый
     архивный блок несёт ЧУЖОЕ origin_saved_at — это и ловит сверка ОКНОМ
     унесённых блоков                                                     РАЗЛИЧАЮЩИЙ
  ③г ВТОРОЙ ВОЗВРАТ COORD: ЗАКОННЫЙ перенос, но между ДВУМЯ командами SQL
     ОДНОГО вызова --move (INSERT в архив, потом отдельным вызовом INSERT
     в историю) секунда МОГЛА перещёлкнуть — имитация сдвигом saved_at строки
     истории на +1 сек → ОБЯЗАН остаться «перенос»: сверка ОКНОМ по всей
     цепочке (а не равенством одному звену — прежняя редакция ③в) держит эту
     секунду                                                              РАЗЛИЧАЮЩИЙ
  ④ правка мимо инструмента (меняющая и длину), ПОТОМ штатный перенос поверх
     неё → 🔴 остаётся: перенос НЕ ОТМЫВАЕТ обход, случившийся ДО него     РАЗЛИЧАЮЩИЙ
  ⑤ ЖИВОЙ случай: копия живой базы, ING/plan → нет «СТАРШЕ текста», есть
     «унесены в архив штатным переносом»                                  РАЗЛИЧАЮЩИЙ
  ⑥ НАРОЧНАЯ ПОЛОМКА, полная (archive_move_look() отключена целиком в копии
     инструмента): красятся РОВНО ①②⑤③г (там, где правку спасала функция),
     а ③③б③в④ остаются как были — 🔴 у них не от функции, поломка их не
     касается                                                             РАЗЛИЧАЮЩИЙ
  ⑥б НАРОЧНАЯ ПОЛОМКА, частичная («сверять только ДЛИНУ» — из цепочки убрана
     ИМЕННО проверка содержимого, длина и сверка окном унесённых блоков
     по-прежнему на месте): красится РОВНО ③б (обход той же длины больше
     некому ловить), а ①②③в③г④⑤ остаются как были — ③в ловит НЕ содержимое,
     а окно унесённых блоков, эта дыра его не касается                   РАЗЛИЧАЮЩИЙ
  ⑥в НАРОЧНАЯ ПОЛОМКА, частичная («не сверять ОКНОМ унесённые блоки» — из
     цепочки убрана ИМЕННО сверка _archived_blocks_window_matches, длина и
     содержимое по-прежнему на месте): красится РОВНО ③в (обход внутри
     архивируемого блока больше некому ловить), а ①②③б③г④⑤ остаются как
     были — их ловят длина и содержимое ОСТАВШЕГОСЯ тела (③г у неё и так
     не был красным — поломка тут ничего не меняет)                      РАЗЛИЧАЮЩИЙ
  контроль: живая база НЕ ТРОНУТА этим прогоном (ING/plan — тот же верхний
  ряд истории до и после)

⛔ Живого контура НЕ касается: read-phoenix/save-phoenix/memory-archive зовутся
   ТОЛЬКО на копиях базы (sqlite3 backup API из режима только-чтения), с явным
   --db на копию. Живая mezosync.db читается напрямую (mode=ro) лишь для
   контрольных чисел до/после и для построения копии случая ⑤.

    python <КОНТУР>/vnext-tools/bite-archive-move-look.py
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — импорт из vnext-tools (своя копия), как велит карточка

SCRIPTS = mezo_paths.live_scripts()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402 — стенд из S (.mezosync/scripts), как велит карточка

LIVE_DB = mezo_paths.live_db()
READ = SCRIPTS / "read-phoenix.py"
SAVE = SCRIPTS / "save-phoenix.py"
ARCHIVE = pathlib.Path(__file__).resolve().parent / "memory-archive.py"

for _tool in (READ, SAVE, ARCHIVE):
    if not _tool.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {_tool}")

ROLE = "BITE605"
SECTION = "state"


def live_ing_plan_state():
    """Верхняя строка истории и штамп ING/plan — ТОЛЬКО ЧТЕНИЕ, для контроля «не тронуто».

    🪤 Значения СНИМАЮТСЯ, а не вписаны числом: вписанный снимок протухнет, как только
    живая ING/plan сдвинется законной работой ДРУГОЙ роли между прогонами приёмки —
    и контроль начал бы краснеть не по своей причине (тот же класс, что и вписанный
    коммит в bite-update-tools-rev.py: PACK_BEFORE/pack_after сравниваются, а не
    сверяются с константой)."""
    con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    try:
        top = con.execute(
            "SELECT id, saved_at, reason FROM phoenix_history WHERE role='ING' AND section='plan' "
            "ORDER BY id DESC LIMIT 1").fetchone()
        stamp = con.execute(
            "SELECT saved_at, confirmed_at FROM phoenix WHERE role='ING' AND section='plan'").fetchone()
        return top, stamp
    finally:
        con.close()


LIVE_ING_PLAN_BEFORE = live_ing_plan_state()

OK = FAIL = 0


def case(title, ok, detail=""):
    global OK, FAIL
    print(("✅" if ok else "🔴"), title)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if ok else 0), FAIL + (0 if ok else 1)
    return ok


def stand_env(container: pathlib.Path) -> dict:
    """Среда для всего, что запускается на стенде: контейнер — САМ стенд, а не
    унаследованный от вызывающего (образец — stand_env() в bite-update-tools-rev.py;
    урок 13.09: унаследованная MEZO_CONTAINER заставила стенд писать в живую базу).
    """
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_CONTAINER=str(container))


def fresh_case_db(case_dir: pathlib.Path) -> pathlib.Path:
    """Копия живой базы В ЭТОТ каталог случая — через sqlite3 backup API, источник
    открыт ТОЛЬКО ДЛЯ ЧТЕНИЯ. Живого файла эта функция не пишет ни при каких путях."""
    mezosync_dir = case_dir / ".mezosync"
    mezosync_dir.mkdir(parents=True, exist_ok=True)
    db = mezosync_dir / "mezosync.db"
    src = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(str(db))
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    return db


def run(tool: pathlib.Path, *args, env: dict, timeout=60):
    r = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def make_body(tag: str) -> str:
    """Тело с ТРЕМЯ заголовками «## » — блочная резка memory-archive.py идёт
    «по заголовкам» детерминированно (заголовков ⩾ 2), и --move 1 всегда валиден."""
    return (
        f"## Блок один {tag}\n"
        + ("Текст первого блока, довольно длинный, чтобы не сработала защита от "
           "обвала объёма. " * 6) + "\n\n"
        + f"## Блок два {tag}\n"
        + ("Текст второго блока — тоже длинный, останется в горячей части. " * 6) + "\n\n"
        + f"## Блок три {tag}\n"
        + ("Текст третьего блока для полноты картины памяти. " * 6)
    )


def tamp(db: pathlib.Path, sql: str, params: tuple) -> None:
    """Прямой UPDATE мимо инструментов, любой таблицей: обычно phoenix (правка тела
    мимо save-phoenix.py), но и phoenix_history тоже — им в случае ③г (карточка #605,
    возврат COORD) имитируется секунда, перещёлкнувшая МЕЖДУ ДВУМЯ КОМАНДАМИ SQL
    одного вызова memory-archive.py --move, а не правка мимо инструмента ролью."""
    con = sqlite3.connect(str(db))
    con.execute(sql, params)
    con.commit()
    con.close()


# ⚖️ МЕТКИ ДЛЯ СЛУЧАЯ ③б — «слово на слово ТОЙ ЖЕ длины». Длина сверяется ЗАПУСКОМ
# (assert ниже), а не на глаз: разъехавшиеся по буквам метки сделали бы случай ③б
# неразличающим — «обход той же длины» перестал бы быть тем, чем назван.
MARK_BEFORE = "ОТМЕТКА-ДА-НЕИЗМЕННО"
MARK_AFTER = "ОТМЕТКА-НЕ-НЕИЗМЕННО"
if len(MARK_BEFORE) != len(MARK_AFTER):
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: метки случая ③б разной длины — подмена не «той же длины»")


def make_body_with_mark(tag: str, mark: str) -> str:
    """Тело с меткой ВНУТРИ ВТОРОГО блока — блок два переносом (--move 1) НЕ уносится,
    и метка остаётся видна в горячей части ПОСЛЕ переноса. Иначе обход, спрятанный
    в уносимом блоке, вместе с блоком и уехал бы в архив — случай перестал бы
    что-либо доказывать про содержимое ОСТАВШЕГОСЯ текста."""
    return (
        f"## Блок один {tag}\n"
        + ("Текст первого блока, довольно длинный, чтобы не сработала защита от "
           "обвала объёма. " * 6) + "\n\n"
        + f"## Блок два {tag}\n"
        + f"Строка с меткой: {mark}\n"
        + ("Текст второго блока — тоже длинный, останется в горячей части. " * 6) + "\n\n"
        + f"## Блок три {tag}\n"
        + ("Текст третьего блока для полноты картины памяти. " * 6)
    )


# ═══════════════════════════════════════════════════════════════════════════════
stand = mezo_stand.new("bite-605-archive-move-look-")

# ── ① ШТАТНЫЙ ПЕРЕНОС, взгляда до него не было ──────────────────────────────
dir1 = stand / "case1"
db1 = fresh_case_db(dir1)
env1 = stand_env(dir1)
body1 = dir1 / "body1.md"
body1.write_text(make_body("①"), encoding="utf-8")

rc, out = run(SAVE, "--db", str(db1), "--role", ROLE, "--section", SECTION,
             "--file", str(body1), env=env1)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: save-phoenix не сохранил тело для случая ①:\n{out}")
time.sleep(1.1)
rc, out_move1 = run(ARCHIVE, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                    "--move", "1", "--actor", ROLE, env=env1)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ①:\n{out_move1}")
rc, out1 = run(READ, "--db", str(db1), "--role", ROLE, "--section", SECTION,
              "--actor", "PROTO", env=env1)
case("① штатный перенос: «после записи НЕ перечитывалось …; затем … штатным переносом»",
     "после записи НЕ перечитывалось" in out1
     and "унесены в архив штатным переносом" in out1
     and "СТАРШЕ текста" not in out1,
     f"взгляд читалки:\n   {[l for l in out1.splitlines() if 'взгляд' in l or 'сохранено' in l]}")

# ── ② «ПРИЗНАНО ВЕРНЫМ» до переноса ──────────────────────────────────────────
dir2 = stand / "case2"
db2 = fresh_case_db(dir2)
env2 = stand_env(dir2)
body2 = dir2 / "body2.md"
body2.write_text(make_body("②"), encoding="utf-8")

run(SAVE, "--db", str(db2), "--role", ROLE, "--section", SECTION, "--file", str(body2), env=env2)
time.sleep(1.1)
rc, out_conf = run(SAVE, "--db", str(db2), "--role", ROLE, "--section", SECTION, "--confirm", env=env2)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: --confirm не сработал в случае ②:\n{out_conf}")
time.sleep(1.1)
rc, out_move2 = run(ARCHIVE, "--db", str(db2), "--role", ROLE, "--section", SECTION,
                    "--move", "1", "--actor", ROLE, env=env2)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ②:\n{out_move2}")
rc, out2 = run(READ, "--db", str(db2), "--role", ROLE, "--section", SECTION,
              "--actor", "PROTO", env=env2)
case("② «признано верным» до переноса: «перечитано и признано верным …; затем … переносом»",
     "перечитано и признано верным" in out2
     and "унесены в архив штатным переносом" in out2
     and "СТАРШЕ текста" not in out2)

# ── ③ КОНТРОЛЬ ГРАНИЦЫ: правка мимо инструмента БЕЗ переноса → прежнее 🔴 ───
dir3 = stand / "case3"
db3 = fresh_case_db(dir3)
env3 = stand_env(dir3)
body3 = dir3 / "body3.md"
body3.write_text(make_body("③"), encoding="utf-8")

run(SAVE, "--db", str(db3), "--role", ROLE, "--section", SECTION, "--file", str(body3), env=env3)
tamp(db3, "UPDATE phoenix SET saved_at = datetime('now', '+1 hour') "
         "WHERE role=? AND section=?", (ROLE, SECTION))
rc, out3 = run(READ, "--db", str(db3), "--role", ROLE, "--section", SECTION,
              "--actor", "PROTO", env=env3)
case("③ встречный: правка мимо инструмента БЕЗ переноса — прежнее 🔴 «СТАРШЕ текста»",
     "СТАРШЕ текста" in out3 and "унесены в архив штатным переносом" not in out3)

# ── ③б ВОЗВРАТ COORD: обход ТОЙ ЖЕ ДЛИНЫ в блоке, который НЕ уносится, ПОТОМ
#     штатный перенос поверх него — длина цепочки сходится, содержимое НЕТ ────
dir3b = stand / "case3b"
db3b = fresh_case_db(dir3b)
env3b = stand_env(dir3b)
body3b = dir3b / "body3b.md"
body3b.write_text(make_body_with_mark("③б", MARK_BEFORE), encoding="utf-8")

run(SAVE, "--db", str(db3b), "--role", ROLE, "--section", SECTION, "--file", str(body3b), env=env3b)
time.sleep(1.1)
# Обход: МЕТКА заменена на метку ТОЙ ЖЕ длины — REPLACE() не трогает общую длину тела
# ни на знак, только содержимое строки внутри блока, который переносом не уносится.
# ⚠️ saved_at НАРОЧНО НЕ ТРОГАЕМ (в отличие от tamp() в случаях ③/④): этот случай обязан
# остаться ЧИСТЫМ сигналом «содержимое разошлось» — единственным, что его ловит, —
# и не задевать сверку origin_saved_at (#605 ③в, ниже): архивируемый блок «один» здесь
# самим обходом не тронут, и её звено обязано сойтись честно. Троньсь мы saved_at,
# origin_saved_at унесённого блока тоже разошёлся бы с ожидаемым — и ⑥б (см. ниже)
# перестала бы что-либо доказывать про НЕОБХОДИМОСТЬ именно проверки содержимого:
# сверка времени поймала бы случай сама, и разрыв в цепочке перестал бы быть
# различающим для содержимого. Перенос всё равно позже сам поставит НОВЫЙ saved_at —
# confirmed < saved для входа в archive_move_look этим не отменяется.
tamp(db3b, "UPDATE phoenix SET body = REPLACE(body, ?, ?) "
          "WHERE role=? AND section=?", (MARK_BEFORE, MARK_AFTER, ROLE, SECTION))
time.sleep(1.1)
rc, out_move3b = run(ARCHIVE, "--db", str(db3b), "--role", ROLE, "--section", SECTION,
                     "--move", "1", "--actor", ROLE, env=env3b)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ③б:\n{out_move3b}")
rc, out3b = run(READ, "--db", str(db3b), "--role", ROLE, "--section", SECTION,
               "--actor", "PROTO", env=env3b)
case("③б обход ТОЙ ЖЕ длины, ПОТОМ штатный перенос — 🔴 остаётся: длина не спасает",
     "СТАРШЕ текста" in out3b and "унесены в архив штатным переносом" not in out3b)

# ── ③в ВОЗВРАТ COORD (карточка #605, случай E4c): обход ТОЙ ЖЕ ДЛИНЫ ВНУТРИ блока,
#     который ТУТ ЖЕ уносится штатным переносом — в отличие от ③б (метка в блоке,
#     который ОСТАЁТСЯ), здесь метка в блоке, который УХОДИТ. Тело раздела после
#     переноса ЧИСТОЕ (подмена уехала целиком со своим блоком — ни длина, ни
#     подпоследовательность строк ОСТАВШЕГОСЯ тела её не видят), а унесённый архивный
#     кусок несёт ЧУЖОЕ origin_saved_at: живой пример COORD — 17:57:09 ≠ 17:57:08 ──
dir3v = stand / "case3v"
db3v = fresh_case_db(dir3v)
env3v = stand_env(dir3v)
body3v = dir3v / "body3v.md"
body3v.write_text(make_body_with_mark("③в", MARK_BEFORE), encoding="utf-8")

run(SAVE, "--db", str(db3v), "--role", ROLE, "--section", SECTION, "--file", str(body3v), env=env3v)
time.sleep(1.1)
# Обход: та же подмена ТОЙ ЖЕ длины, что и в ③б, но здесь — КАК В ЖИВОМ ВОЗВРАТЕ
# COORD — saved_at ТРОГАЕМ нарочно («прямой UPDATE тела И saved_at»): это и ставит
# унесённому позже блоку ЧУЖОЕ origin_saved_at вместо часа настоящего сохранения.
tamp(db3v, "UPDATE phoenix SET body = REPLACE(body, ?, ?), saved_at = datetime('now') "
          "WHERE role=? AND section=?", (MARK_BEFORE, MARK_AFTER, ROLE, SECTION))
time.sleep(1.1)
# Уносим ИМЕННО блок «два» — тот, где лежит метка (у ③б уносился блок БЕЗ метки).
rc, out_move3v = run(ARCHIVE, "--db", str(db3v), "--role", ROLE, "--section", SECTION,
                     "--move", "2", "--actor", ROLE, env=env3v)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ③в:\n{out_move3v}")
rc, out3v = run(READ, "--db", str(db3v), "--role", ROLE, "--section", SECTION,
               "--actor", "PROTO", env=env3v)
case("③в возврат COORD (E4c): обход ТОЙ ЖЕ длины ВНУТРИ блока, который ТУТ ЖЕ "
     "архивируется — 🔴 остаётся: origin_saved_at унесённого блока не совпал",
     "СТАРШЕ текста" in out3v and "унесены в архив штатным переносом" not in out3v)

# ── ③г ВТОРОЙ ВОЗВРАТ COORD: ЗАКОННЫЙ перенос, но между ДВУМЯ командами базы
#     (INSERT в phoenix_archive и, следующим отдельным вызовом, INSERT в
#     phoenix_history) секунда МОГЛА перещёлкнуть — прежняя редакция ③в сверяла
#     РАВЕНСТВОМ (moved_at строки архива == saved_at строки истории) и на таком
#     перещёлкивании дала бы ложный 🔴. Имитируем сдвигом saved_at строки истории
#     'archive-move' на +1 секунду (как если бы её INSERT прошёл на секунду позже
#     INSERT-а в архив) — ДОЛЖЕН остаться «перенос» ────────────────────────────
dir3g = stand / "case3g"
db3g = fresh_case_db(dir3g)
env3g = stand_env(dir3g)
body3g = dir3g / "body3g.md"
body3g.write_text(make_body("③г"), encoding="utf-8")

run(SAVE, "--db", str(db3g), "--role", ROLE, "--section", SECTION, "--file", str(body3g), env=env3g)
time.sleep(1.1)
rc, out_move3g = run(ARCHIVE, "--db", str(db3g), "--role", ROLE, "--section", SECTION,
                     "--move", "1", "--actor", ROLE, env=env3g)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ③г:\n{out_move3g}")
# Имитация перещёлкнувшей секунды МЕЖДУ ДВУМЯ КОМАНДАМИ ОДНОГО ВЫЗОВА --move:
# сдвигаем ТОЛЬКО saved_at строки истории 'archive-move' на +1 сек — moved_at
# уже унесённого блока в phoenix_archive остаётся ПРЕЖНИМ, ровно как если бы
# сама секунда истории сдвинулась позже секунды архивной вставки.
tamp(db3g, "UPDATE phoenix_history SET saved_at = datetime(saved_at, '+1 second') "
          "WHERE role=? AND section=? AND reason LIKE 'archive-move:%'", (ROLE, SECTION))
rc, out3g = run(READ, "--db", str(db3g), "--role", ROLE, "--section", SECTION,
               "--actor", "PROTO", env=env3g)
case("③г возврат COORD: секунда МЕЖДУ КОМАНДАМИ перещёлкнула (имитация) — ОСТАЁТСЯ "
     "«перенос», не 🔴: окно по всей цепочке шире равенства одному звену",
     "СТАРШЕ текста" not in out3g and "унесены в архив штатным переносом" in out3g)

# ── ③д ТРЕТИЙ ВОЗВРАТ COORD (карточка #605, вариант «б»): у ИСТОЧНИКА (memory-
#     archive.py) ОДНА метка времени на ДЕЙСТВИЕ --move — moved_at КАЖДОГО
#     унесённого блока, saved_at раздела в phoenix и saved_at строки истории
#     ЭТОГО переноса обязаны быть ОДНОЙ И ТОЙ ЖЕ строкой (а не совпадать по
#     секундному разрешению случайно) ─────────────────────────────────────────
dir3d = stand / "case3d"
db3d = fresh_case_db(dir3d)
env3d = stand_env(dir3d)
body3d = dir3d / "body3d.md"
body3d.write_text(make_body("③д"), encoding="utf-8")

run(SAVE, "--db", str(db3d), "--role", ROLE, "--section", SECTION, "--file", str(body3d), env=env3d)
time.sleep(1.1)
rc, out_move3d = run(ARCHIVE, "--db", str(db3d), "--role", ROLE, "--section", SECTION,
                     "--move", "1", "--actor", ROLE, env=env3d)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ③д:\n{out_move3d}")

con3d = sqlite3.connect(f"file:{db3d.as_posix()}?mode=ro", uri=True)
try:
    archived_times = [r[0] for r in con3d.execute(
        "SELECT moved_at FROM phoenix_archive WHERE role=? AND section=?", (ROLE, SECTION))]
    section_saved3d = con3d.execute(
        "SELECT saved_at FROM phoenix WHERE role=? AND section=?", (ROLE, SECTION)).fetchone()[0]
    history_saved3d = con3d.execute(
        "SELECT saved_at FROM phoenix_history WHERE role=? AND section=? "
        "ORDER BY id DESC LIMIT 1", (ROLE, SECTION)).fetchone()[0]
finally:
    con3d.close()
case("③д одна метка времени на действие --move: moved_at унесённых блоков, "
     "saved_at раздела и saved_at строки истории — ОДНА И ТА ЖЕ строка",
     len(archived_times) >= 1 and all(t == section_saved3d for t in archived_times)
     and history_saved3d == section_saved3d,
     f"moved_at унесённых блоков={set(archived_times)} · phoenix.saved_at={section_saved3d} · "
     f"phoenix_history.saved_at={history_saved3d} — три разных вызова datetime('now') "
     f"тремя разными командами SQL заменены ОДНИМ значением move_time")

# ── ③д-поломка: у ИСТОЧНИКА (memory-archive.py) saved_at строки истории СНОВА
#     берёт время ОТДЕЛЬНЫМ вызовом — детерминированным сдвигом +1 сек, чтобы
#     поломка ловилась КАЖДЫЙ прогон, а не редкой удачей перещёлкнувшей секунды ─
broken_archive_dir = stand / "broken-archive-source-time"
broken_archive_tool = mezo_stand.copy_tool(ARCHIVE, broken_archive_dir)
archive_original_text = broken_archive_tool.read_text(encoding="utf-8")
ARCHIVE_HISTORY_BLOCK = (
    '            "INSERT INTO phoenix_history (role, section, body, body_chars, saved_at, "\n'
    '            "actor, reason, prev_chars) VALUES (?,?,?,?,?,?,?,?)",\n'
)
if ARCHIVE_HISTORY_BLOCK not in archive_original_text:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка записи истории переноса не найдена в "
             "испытуемом memory-archive.py — переименовали, поломка ③д бьёт мимо")
archive_broken_text = archive_original_text.replace(
    ARCHIVE_HISTORY_BLOCK,
    # ПОРЧА: saved_at строки истории переноса детерминированно сдвинут на +1 сек
    # относительно move_time, использованного для phoenix_archive.moved_at и
    # phoenix.saved_at — имитация «секунда перещёлкнула между отдельными командами».
    '            "INSERT INTO phoenix_history (role, section, body, body_chars, saved_at, "\n'
    '            "actor, reason, prev_chars) VALUES (?,?,?,?,datetime(?, \'+1 second\'),?,?,?)",\n')
broken_archive_tool.write_text(archive_broken_text, encoding="utf-8")

dir3d_broken = stand / "case3d-broken"
db3d_broken = fresh_case_db(dir3d_broken)
env3d_broken = stand_env(dir3d_broken)
body3d_broken = dir3d_broken / "body3d-broken.md"
body3d_broken.write_text(make_body("③д-поломка"), encoding="utf-8")
run(SAVE, "--db", str(db3d_broken), "--role", ROLE, "--section", SECTION,
    "--file", str(body3d_broken), env=env3d_broken)
time.sleep(1.1)
rc, out_move3d_broken = run(broken_archive_tool, "--db", str(db3d_broken), "--role", ROLE,
                            "--section", SECTION, "--move", "1", "--actor", ROLE, env=env3d_broken)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломанный memory-archive --move не перенёс блок "
             f"в случае ③д-поломка:\n{out_move3d_broken}")
con3d_broken = sqlite3.connect(f"file:{db3d_broken.as_posix()}?mode=ro", uri=True)
try:
    section_saved3d_b = con3d_broken.execute(
        "SELECT saved_at FROM phoenix WHERE role=? AND section=?", (ROLE, SECTION)).fetchone()[0]
    history_saved3d_b = con3d_broken.execute(
        "SELECT saved_at FROM phoenix_history WHERE role=? AND section=? "
        "ORDER BY id DESC LIMIT 1", (ROLE, SECTION)).fetchone()[0]
finally:
    con3d_broken.close()
case("③д-поломка (детерминированный сдвиг +1 сек у ИСТОЧНИКА) КРАСИТ: вернувшийся "
     "второй источник времени рвёт равенство меток переноса",
     section_saved3d_b != history_saved3d_b,
     f"phoenix.saved_at={section_saved3d_b} · phoenix_history.saved_at={history_saved3d_b} — "
     f"строка истории детерминированно отстаёт на секунду; без этой поломки случай ③д "
     f"ничего не доказывал бы")

# ── ④ ПРАВКА МИМО ИНСТРУМЕНТА, ПОТОМ штатный перенос — перенос НЕ ОТМЫВАЕТ ──
dir4 = stand / "case4"
db4 = fresh_case_db(dir4)
env4 = stand_env(dir4)
body4 = dir4 / "body4.md"
body4.write_text(make_body("④"), encoding="utf-8")

run(SAVE, "--db", str(db4), "--role", ROLE, "--section", SECTION, "--file", str(body4), env=env4)
time.sleep(1.1)
# ⚠️ ОБХОД МЕНЯЕТ ДЛИНУ ТЕЛА, А НЕ ТОЛЬКО ЧАС: цепочка archive_move_look() сверяет
# prev_chars архивной строки с body_chars СОСЕДНЕЙ — обход, не тронувший длину,
# этой проверкой не поймать. Обход мимо инструмента меняет и то, и другое, как
# и настоящая ручная правка тела.
tamp(db4, "UPDATE phoenix SET body = body || ?, saved_at = datetime('now') "
         "WHERE role=? AND section=?",
     ("\n\nПОРЧА МИМО ИНСТРУМЕНТА — добавлено в обход save-phoenix.py, "
      "заведомо другая длина тела.", ROLE, SECTION))
time.sleep(1.1)
rc, out_move4 = run(ARCHIVE, "--db", str(db4), "--role", ROLE, "--section", SECTION,
                    "--move", "1", "--actor", ROLE, env=env4)
if rc != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: memory-archive --move не перенёс блок в случае ④:\n{out_move4}")
rc, out4 = run(READ, "--db", str(db4), "--role", ROLE, "--section", SECTION,
              "--actor", "PROTO", env=env4)
case("④ правка мимо инструмента, ПОТОМ штатный перенос — 🔴 остаётся: перенос не отмывает обход",
     "СТАРШЕ текста" in out4 and "унесены в архив штатным переносом" not in out4)

# ── ⑤ ЖИВОЙ СЛУЧАЙ: копия живой базы, ING/plan ───────────────────────────────
dir5 = stand / "case5"
db5 = fresh_case_db(dir5)
env5 = stand_env(dir5)
rc, out5 = run(READ, "--db", str(db5), "--role", "ING", "--section", "plan",
              "--actor", "PROTO", env=env5)
case("⑤ живой случай ING/plan (копия): нет «СТАРШЕ текста», есть «унесены в архив штатным переносом»",
     "СТАРШЕ текста" not in out5 and "унесены в архив штатным переносом" in out5)

# ── ⑥ НАРОЧНАЯ ПОЛОМКА: archive_move_look() отключена в копии инструмента ───
broken_dir = stand / "broken"
broken_tool = mezo_stand.copy_tool(READ, broken_dir)
original_text = broken_tool.read_text(encoding="utf-8")
TARGET_LINE = "            look = archive_move_look(conn, role, s, body, saved, confirmed)\n"
if TARGET_LINE not in original_text:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка вызова archive_move_look() не найдена в "
             "испытуемом read-phoenix.py — переименовали, поломка бьёт мимо")
broken_text = original_text.replace(
    TARGET_LINE, "            look = None  # ПОРЧА bite-archive-move-look: проверка нарочно выключена\n")
broken_tool.write_text(broken_text, encoding="utf-8")

rc, b_out1 = run(broken_tool, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env1)
rc, b_out2 = run(broken_tool, "--db", str(db2), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env2)
rc, b_out5 = run(broken_tool, "--db", str(db5), "--role", "ING", "--section", "plan",
                "--actor", "PROTO", env=env5)
rc, b_out3 = run(broken_tool, "--db", str(db3), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env3)
rc, b_out4 = run(broken_tool, "--db", str(db4), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env4)

rc, b_out3b = run(broken_tool, "--db", str(db3b), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3b)
rc, b_out3v = run(broken_tool, "--db", str(db3v), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3v)
rc, b_out3g = run(broken_tool, "--db", str(db3g), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3g)

case("⑥ поломка (полная) КРАСИТ случай ① (раньше его спасала функция)", "СТАРШЕ текста" in b_out1)
case("⑥ поломка (полная) КРАСИТ случай ② (раньше его спасала функция)", "СТАРШЕ текста" in b_out2)
case("⑥ поломка (полная) КРАСИТ случай ⑤ (живой ING/plan, раньше спасала функция)", "СТАРШЕ текста" in b_out5)
case("⑥ поломка (полная) КРАСИТ случай ③г (законный, но раньше его тоже спасала функция)",
     "СТАРШЕ текста" in b_out3g)
case("⑥ поломка (полная) НЕ ТРОГАЕТ случай ③ (он и без функции был 🔴)", "СТАРШЕ текста" in b_out3)
case("⑥ поломка (полная) НЕ ТРОГАЕТ случай ③б (он был 🔴 и без поломки — функция и сама его красит)",
     "СТАРШЕ текста" in b_out3b)
case("⑥ поломка (полная) НЕ ТРОГАЕТ случай ③в (он был 🔴 и без поломки — функция и сама его красит)",
     "СТАРШЕ текста" in b_out3v)
case("⑥ поломка (полная) НЕ ТРОГАЕТ случай ④ (он и без функции был 🔴)", "СТАРШЕ текста" in b_out4)

# ── ⑥б НАРОЧНАЯ ПОЛОМКА, ЧАСТИЧНАЯ: из цепочки убрана ТОЛЬКО проверка СОДЕРЖИМОГО,
#     проверка ДЛИНЫ (prev_chars = body_chars соседа) остаётся на месте — это и есть
#     возврат к состоянию ДО правки COORD. Обязана красить РОВНО ③б: там длина
#     цепочки сходится, а содержимое — нет, и без проверки содержимого её некому ловить.
broken_len_dir = stand / "broken-length-only"
broken_len_tool = mezo_stand.copy_tool(READ, broken_len_dir)
len_only_original = broken_len_tool.read_text(encoding="utf-8")
CONTENT_CHECK_BLOCK = (
    "        if not _lines_are_ordered_subsequence(rows[i][0].splitlines(), rows[i + 1][0].splitlines()):\n"
    "            return None                     # разрыв цепочки: содержимое разошлось\n"
)
if CONTENT_CHECK_BLOCK not in len_only_original:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок проверки содержимого не найден в испытуемом "
             "read-phoenix.py — переименовали, частичная поломка бьёт мимо")
len_only_broken = len_only_original.replace(
    CONTENT_CHECK_BLOCK,
    "        # ПОРЧА bite-archive-move-look (⑥б): проверка СОДЕРЖИМОГО нарочно выключена, "
    "сверяется только ДЛИНА\n")
broken_len_tool.write_text(len_only_broken, encoding="utf-8")

rc, l_out1 = run(broken_len_tool, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env1)
rc, l_out2 = run(broken_len_tool, "--db", str(db2), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env2)
rc, l_out3b = run(broken_len_tool, "--db", str(db3b), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3b)
rc, l_out4 = run(broken_len_tool, "--db", str(db4), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env4)
rc, l_out5 = run(broken_len_tool, "--db", str(db5), "--role", "ING", "--section", "plan",
                "--actor", "PROTO", env=env5)
rc, l_out3v = run(broken_len_tool, "--db", str(db3v), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3v)
rc, l_out3g = run(broken_len_tool, "--db", str(db3g), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3g)

case("⑥б поломка (частичная, только длина) КРАСИТ РОВНО случай ③б "
     "(обход той же длины больше некому ловить)",
     "СТАРШЕ текста" not in l_out3b and "унесены в архив штатным переносом" in l_out3b,
     "длина сходится, содержимое проверкой уже не сверяется ⇒ обход проходит как мирный перенос")
case("⑥б поломка НЕ ТРОГАЕТ случай ① (там длина и без содержимого совпадала честно)",
     "после записи НЕ перечитывалось" in l_out1 and "СТАРШЕ текста" not in l_out1)
case("⑥б поломка НЕ ТРОГАЕТ случай ② (там длина и без содержимого совпадала честно)",
     "перечитано и признано верным" in l_out2 and "СТАРШЕ текста" not in l_out2)
case("⑥б поломка НЕ ТРОГАЕТ случай ④ (там уже ДЛИНА не совпала — ловится первой же проверкой)",
     "СТАРШЕ текста" in l_out4)
case("⑥б поломка НЕ ТРОГАЕТ случай ⑤ (живой ING/plan — длина без содержимого совпадала честно)",
     "СТАРШЕ текста" not in l_out5 and "унесены в архив штатным переносом" in l_out5)
case("⑥б поломка НЕ ТРОГАЕТ случай ③в (его ловит сверка ВРЕМЕНИ унесённых блоков, "
     "не проверка содержимого — она тут ни при чём)",
     "СТАРШЕ текста" in l_out3v and "унесены в архив штатным переносом" not in l_out3v)
case("⑥б поломка НЕ ТРОГАЕТ случай ③г (законный, содержимое там не при чём вовсе)",
     "СТАРШЕ текста" not in l_out3g and "унесены в архив штатным переносом" in l_out3g)

# ── ⑥в НАРОЧНАЯ ПОЛОМКА, ЧАСТИЧНАЯ: из цепочки убрана ТОЛЬКО сверка ОКНОМ
#     унесённых блоков (_archived_blocks_window_matches), проверки ДЛИНЫ и
#     СОДЕРЖИМОГО остаются на месте — это и есть состояние ДО правки COORD ③в/③г.
#     Обязана красить РОВНО ③в: там длина и содержимое ОСТАВШЕГОСЯ тела чисты,
#     и без сверки окном подмену больше некому ловить.
broken_origin_dir = stand / "broken-origin-only"
broken_origin_tool = mezo_stand.copy_tool(READ, broken_origin_dir)
origin_only_original = broken_origin_tool.read_text(encoding="utf-8")
ORIGIN_CHECK_BLOCK = (
    "    if not _archived_blocks_window_matches(conn, role, section, rows, i):\n"
    "        return None                         # разрыв цепочки: унесённые блоки не сошлись с окном (#605 ③в/③г)\n"
)
if ORIGIN_CHECK_BLOCK not in origin_only_original:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок сверки окном унесённых блоков не найден в "
             "испытуемом read-phoenix.py — переименовали, частичная поломка ⑥в бьёт мимо")
origin_only_broken = origin_only_original.replace(
    ORIGIN_CHECK_BLOCK,
    "    # ПОРЧА bite-archive-move-look (⑥в): сверка ОКНОМ унесённых блоков "
    "нарочно выключена\n")
broken_origin_tool.write_text(origin_only_broken, encoding="utf-8")

rc, o_out1 = run(broken_origin_tool, "--db", str(db1), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env1)
rc, o_out2 = run(broken_origin_tool, "--db", str(db2), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env2)
rc, o_out3b = run(broken_origin_tool, "--db", str(db3b), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3b)
rc, o_out3v = run(broken_origin_tool, "--db", str(db3v), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3v)
rc, o_out3g = run(broken_origin_tool, "--db", str(db3g), "--role", ROLE, "--section", SECTION,
                 "--actor", "PROTO", env=env3g)
rc, o_out4 = run(broken_origin_tool, "--db", str(db4), "--role", ROLE, "--section", SECTION,
                "--actor", "PROTO", env=env4)
rc, o_out5 = run(broken_origin_tool, "--db", str(db5), "--role", "ING", "--section", "plan",
                "--actor", "PROTO", env=env5)

case("⑥в поломка (частичная, только сверка окном унесённых блоков) КРАСИТ РОВНО "
     "случай ③в (обход внутри архивируемого блока больше некому ловить)",
     "СТАРШЕ текста" not in o_out3v and "унесены в архив штатным переносом" in o_out3v,
     "длина и содержимое ОСТАВШЕГОСЯ тела чисты, окно унесённых блоков проверкой уже не сверяется")
case("⑥в поломка НЕ ТРОГАЕТ случай ① (окно унесённого блока и без сверки совпадало честно)",
     "после записи НЕ перечитывалось" in o_out1 and "СТАРШЕ текста" not in o_out1)
case("⑥в поломка НЕ ТРОГАЕТ случай ② (окно унесённого блока и без сверки совпадало честно)",
     "перечитано и признано верным" in o_out2 and "СТАРШЕ текста" not in o_out2)
case("⑥в поломка НЕ ТРОГАЕТ случай ③б (его по-прежнему ловит проверка СОДЕРЖИМОГО)",
     "СТАРШЕ текста" in o_out3b and "унесены в архив штатным переносом" not in o_out3b)
case("⑥в поломка НЕ ТРОГАЕТ случай ③г (у него и без сверки не было беды — окно тут "
     "просто ничего не находит нарушенным, поломка совпадает со здоровым исходом)",
     "СТАРШЕ текста" not in o_out3g and "унесены в архив штатным переносом" in o_out3g)
case("⑥в поломка НЕ ТРОГАЕТ случай ④ (там уже ДЛИНА не совпала — ловится первой же проверкой)",
     "СТАРШЕ текста" in o_out4)
case("⑥в поломка НЕ ТРОГАЕТ случай ⑤ (живой ING/plan — окно унесённых блоков совпадало честно)",
     "СТАРШЕ текста" not in o_out5 and "унесены в архив штатным переносом" in o_out5)

# ── КОНТРОЛЬ: живая база НЕ ТРОНУТА ЭТИМ ПРОГОНОМ ────────────────────────────
top_after, live_after = live_ing_plan_state()
case("контроль: живая база НЕ ТРОНУТА (верхняя строка истории ING/plan и её штамп те же, что до прогона)",
     (top_after, live_after) == LIVE_ING_PLAN_BEFORE,
     f"было {LIVE_ING_PLAN_BEFORE}; стало {(top_after, live_after)}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
