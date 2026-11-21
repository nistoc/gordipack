#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-install — сверка тел установленных файлов с записью установки (карточка #819).

    python <контур>/.mezosync/scripts/verify-install.py              # сверить, ничего не пишет
    python <контур>/.mezosync/scripts/verify-install.py --db <путь>  # сверить по другой базе

ЗАЧЕМ. Установщик (update-tools.py) пишет в хранилище запись установки — meta.template_files_sha:
пары «ключ файла → отпечаток тела». Служба отдаёт свёртку записи и число файлов, но тела не
перечитывает; сверка имён (guard-install-lag.py) тела тоже не читает. Эта команда делает то, чего
нет нигде: берёт каждую пару записи, находит файл на диске, считает отпечаток его тела и сравнивает
с записанным. Работает без службы, хранилище открывает только на чтение, ни одного файла не пишет
(даже байт-код: sys.dont_write_bytecode).

ТОТ ЖЕ КОД, ЧТО У УСТАНОВЩИКА. Отпечаток (digest), ключ записи (fingerprint_key), признак второго
каталога, сам второй каталог (second_install_dir), путь файла по ключу (install_path) и каталог
рабочих скриптов команда берёт из update-tools.py, лежащего рядом, — загрузкой модуля. Своего
отпечатка и своей сборки ключа здесь нет: два места со своей арифметикой разошлись бы молча.

ДВА КАТАЛОГА УСТАНОВКИ. Первый — рабочие скрипты контура (просматривается рекурсивно, кроме
каталогов __pycache__). Второй — каталог файлов vnext/prototype, объявленный ключом
prototype_install_dir файла путей контура (просматривается только верхний уровень).

ЧТО ЗНАЧАТ СТРОКИ ВЫВОДА
  тело изменено ........... файл записи на месте, но отпечаток его тела другой
  тела нет на диске ....... файла записи под его именем нет, и тела с его отпечатком нет ни под каким
                            именем ВНЕ записи. То же тело у другой пары записи (одно имя в обоих
                            каталогах) — её собственный файл: переименованием это не считается
  имя другое, тело то же .. файла записи под его именем нет, но то же тело лежит под именем, которого
                            в записи нет (переименование); расхождением НЕ считается
  второе имя того же тела . файл вне записи с телом из записи (копия без правки); расхождением НЕ считается
  лишнее тело ............. файл вне записи, отпечатка которого в записи нет (например, копия .bak
                            с правкой); исход не меняет, но называется
  Списки печатаются целиком, с числом в заголовке блока; ничего не обрезается.

ИСХОДЫ И КОДЫ (старшинство сверху вниз)
  расходится ...... 1  есть пара записи с изменённым телом или с телом, которого нет на диске
  нечем сверять ... 3  записи нет · хранилище не читается · запись не разбирается · второй каталог
                       не объявлен или не найден (сказано, сколько пар не сверено)
  совпало ......... 0  все пары записи сверены и равны; названо число сверенных файлов
  4 — отказ по аргументам. Если что-то не сверено, а что-то расходится, исход «расходится», и
  несверенное всё равно названо.

ЧТО СВЕРЯЕТСЯ. В любом исходе, до чтения записи, печатается ОДНА строка «сверяется: база … · каталог скриптов … ·
второй каталог — …» (второй каталог — путь, «не объявлен» или «нет (причина)»). База берётся по --db или боевая; каталог
скриптов всегда из контура группы; второй каталог — по файлу путей рядом с базой. По копии базы вне контура строка
показывает и копию, и каталоги контура: так видно, что сверено с чем.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sqlite3
import sys

sys.dont_write_bytecode = True      # команда ничего не пишет — и кэш байт-кода тоже
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

EXIT_MATCH, EXIT_DIVERGES, EXIT_NOCHECK, EXIT_ARGS = 0, 1, 3, 4
RECORD_KEY = "template_files_sha"
TITLE = "verify-install — сверка тел установленных файлов с записью установки"
BOUNDARY = ("Граница отпечатка: он считается по содержимому с приведёнными окончаниями строк и без "
            "хвостовых пробелов в конце файла; смена одних окончаний строк расхождением не считается.")
RECORD_BOUNDARY = ("Граница записи: запись хранит отпечаток версии ПАКЕТА. Правка контура, принятая установщиком "
                   "(update-tools.py --accept-merge; в его плане файл помечен «ПРАВЛЕН У ТЕБЯ»), оставляет в записи "
                   "отпечаток версии пакета, с которой сводили, и здесь даёт ту же строку «тело изменено», что и "
                   "порча файла: отличить одно от другого команде нечем.")
WAL_BOUNDARY = ("База в режиме WAL: читающее соединение оставляет рядом два служебных файла (-shm и -wal); сам файл базы при "
                "этом не меняется ни байтом. Параметра immutable команда не ставит: такая база читалась бы без учёта записей, "
                "ещё не слитых в неё.")
HELP = (__doc__ or "").rstrip() + "\n\n" + BOUNDARY + "\n" + RECORD_BOUNDARY + "\n" + WAL_BOUNDARY + "\n"


def nothing_to_check(reason: str) -> int:
    print(f"ИТОГ: НЕЧЕМ СВЕРЯТЬ — {reason}")
    return EXIT_NOCHECK


def load_installer():
    """update-tools.py рядом с командой — загрузкой модуля (имя файла с дефисом: import не подходит)."""
    spec = importlib.util.spec_from_file_location("update_tools_installer", HERE / "update-tools.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_record(db: pathlib.Path) -> tuple[str | None, str | None]:
    """(значение записи, причина-слова). Хранилище открывается только на чтение."""
    try:
        con = sqlite3.connect(pathlib.Path(db).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            con.execute("PRAGMA query_only=ON")
            row = con.execute("SELECT value FROM meta WHERE key=?", (RECORD_KEY,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error as e:
        return None, f"хранилище не читается ({db}): {e}"
    if row is None or row[0] is None or not str(row[0]).strip():
        return None, ("записи установки нет: в хранилище нет ключа meta." + RECORD_KEY + " или значение пусто")
    return str(row[0]), None


def parse_record(raw: str) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(raw)
    except ValueError as e:
        return None, f"запись не разбирается: это не JSON ({e})"
    if not isinstance(data, dict):
        return None, f"запись не разбирается: нужен объект «ключ → отпечаток», а лежит {type(data).__name__}"
    bad = [k for k, v in data.items() if not isinstance(v, str)]
    if bad:
        return None, f"запись не разбирается: отпечаток не строка у {len(bad)} ключей (первый: {bad[0]})"
    if not data:
        return None, "записи установки нет: запись пуста (пар 0)"
    return data, None


def scan_files(upd, tools: pathlib.Path, second_dir: pathlib.Path | None) -> list[tuple[str, pathlib.Path]]:
    """Все файлы обоих каталогов под ключами записи: первый — рекурсивно без __pycache__, второй — сверху."""
    found = []
    for p in sorted(tools.rglob("*")):
        rel = p.relative_to(tools)
        if p.is_file() and "__pycache__" not in rel.parts:
            found.append((upd.fingerprint_key(rel), p))
    if second_dir is not None:
        for p in sorted(second_dir.glob("*")):
            if p.is_file():
                found.append((upd.fingerprint_key(upd.second_rel(p.name)), p))
    return found


def judge_pair(on_disk, recorded: str, holders: list) -> str:
    """Исход одной пары записи: ok · changed · renamed · gone."""
    if on_disk == recorded:
        return "ok"
    if on_disk is None:
        return "renamed" if holders else "gone"
    return "changed"


def outside_kind(fp: str, gone_fps: set, present_fps: set):
    """Вид файла вне записи по отпечатку его тела."""
    if fp in gone_fps:
        return "переименован"
    if fp in present_fps:
        return "второе имя"
    return "лишнее"


def main(argv: list[str]) -> int:
    db_arg = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--help", "-h"):
            print(HELP, end="")
            return EXIT_MATCH
        if arg == "--db":
            if i + 1 >= len(argv):
                print("⛔ у --db нет значения: нужен путь к хранилищу. Справка: --help")
                return EXIT_ARGS
            db_arg, i = argv[i + 1], i + 2
        elif arg.startswith("--db="):
            db_arg, i = arg[len("--db="):], i + 1
        else:
            print(f"⛔ незнакомый аргумент: {arg}. Команда понимает только --db <путь> и --help.")
            return EXIT_ARGS

    print(TITLE)
    print(BOUNDARY)
    try:
        upd = load_installer()
    except Exception as e:          # noqa: BLE001 — любая беда загрузки названа словами
        return nothing_to_check(f"установщик update-tools.py рядом с командой не загрузился ({type(e).__name__}: {e})")

    try:
        db = pathlib.Path(db_arg) if db_arg else pathlib.Path(upd.mezo_paths.live_db())
        tools = pathlib.Path(upd.mezo_paths.live_scripts())
    except SystemExit as e:         # контейнер не найден: mezo_paths отказывает текстом
        why = str(e.code).strip().splitlines()[0] if e.code else "контейнер группы не найден"
        return nothing_to_check(f"хранилище не читается: путь к нему не определён ({why})")
    # Что сверяется — ОДНА строка в любом исходе, до чтения записи: база — какую назвали (или боевая), каталоги — как они есть.
    # База с --db может лежать вне контура, а каталог скриптов всегда берётся из контура: строка называет оба места, чтобы
    # сверка по чужой копии базы не читалась как сверка своего контура.
    second_dir, second_note = upd.second_install_dir(db)
    if second_dir is not None and second_dir.resolve() == tools.resolve():
        second_dir, second_note = None, "ключ второго каталога указывает на каталог рабочих скриптов"
    elif second_dir is not None and upd.inside(second_dir, upd.local_dir_of(db)):
        second_dir, second_note = None, "ключ второго каталога указывает внутрь каталога местного"
    second_text = str(second_dir) if second_dir is not None else ("не объявлен" if not second_note else f"нет ({second_note})")
    print(f"сверяется: база {db} · каталог скриптов {tools} · второй каталог — {second_text}")

    raw, why = read_record(db)
    if why:
        return nothing_to_check(why)
    pairs, why = parse_record(raw)
    if why:
        return nothing_to_check(why)

    second_keys = [k for k in pairs if upd.is_second_rel(pathlib.Path(k))]
    print(f"запись ...... пар {len(pairs)} (рабочие скрипты — {len(pairs) - len(second_keys)}, "
          f"второй каталог — {len(second_keys)})")

    scanned = scan_files(upd, tools, second_dir)
    prints, unread = {}, []
    for key, path in scanned:
        try:
            prints[key] = upd.digest(path.read_bytes())
        except OSError:
            unread.append(key)
    holders_by_fp: dict[str, list[str]] = {}
    for key, fp in prints.items():
        holders_by_fp.setdefault(fp, []).append(key)

    states: dict[str, str] = {}
    detail: dict[str, tuple] = {}
    unverified: list[tuple[str, str]] = []
    gone_fps: set[str] = set()
    present_fps: dict[str, list[str]] = {}
    for key, recorded in pairs.items():
        rel = pathlib.Path(key)
        if upd.is_second_rel(rel) and second_dir is None:
            unverified.append((key, "второй каталог недоступен"))
            continue
        path = upd.install_path(rel, tools, second_dir)
        try:
            on_disk = upd.digest(path.read_bytes()) if path.is_file() else None
        except OSError as e:
            unverified.append((key, f"файл не читается ({e.__class__.__name__})"))
            continue
        same_body = [k for k in holders_by_fp.get(recorded, []) if k != key] if on_disk is None else []
        holders = [k for k in same_body if k not in pairs]      # переименование — только имя ВНЕ записи
        twins = [k for k in same_body if k in pairs]            # то же тело у другой пары записи — её файл
        state = judge_pair(on_disk, recorded, holders)
        states[key] = state
        detail[key] = (recorded, on_disk, path, holders, twins)
        if on_disk is None:
            gone_fps.add(recorded)
        else:
            present_fps.setdefault(recorded, []).append(key)

    changed = [k for k, s in states.items() if s == "changed"]
    gone = [k for k, s in states.items() if s == "gone"]
    renamed = [k for k, s in states.items() if s == "renamed"]
    ok_keys = [k for k, s in states.items() if s == "ok"]
    verified = len(ok_keys) + len(renamed)

    buckets: dict = {}
    for key, fp in sorted(prints.items()):
        if key in pairs:
            continue
        buckets.setdefault(outside_kind(fp, gone_fps, set(present_fps)), []).append((key, fp))
    second_names, extras = buckets.get("второе имя", []), buckets.get("лишнее", [])

    print()
    if unverified:
        print(f"Не сверено: {len(unverified)} пар")
        for key, why_k in unverified:
            print(f"    не сверено: {key}  [{why_k}]")
    print(f"Расходятся с записью: {len(changed) + len(gone)}")
    for key in changed:
        recorded, on_disk, path, _, _ = detail[key]
        print(f"    тело изменено: {key}  [записано {recorded} · на диске {on_disk} · {path}]")
    if changed:
        print(f"    {RECORD_BOUNDARY}")
    for key in gone:
        recorded, _, path, _, twins = detail[key]
        where = (f"то же тело есть только у других пар записи ({', '.join(twins)}) — это их собственные "
                 f"файлы, переименованием не считается" if twins else
                 "и тела с таким отпечатком нет ни под каким именем")
        print(f"    тела нет на диске: {key}  [записано {recorded} · файла {path} нет, {where}]")
    n_rename = sum(len(detail[k][3]) for k in renamed)
    print(f"Под другим именем (расхождением не считается): {n_rename}")
    for key in renamed:
        for holder in detail[key][3]:
            print(f"    имя другое, тело то же: {key} → {holder}  [тело {detail[key][0]}; под своим именем файла нет]")
    print(f"Вторые имена тела из записи (расхождением не считается): {len(second_names)}")
    for key, fp in second_names:
        owners = ", ".join(present_fps.get(fp, []))
        print(f"    второе имя того же тела: {key} = {owners}  [тело {fp}]")
    print(f"Лишние тела (файлы вне записи, отпечатка которых в записи нет): {len(extras)}")
    for key, fp in extras:
        print(f"    лишнее тело: {key}  [{fp}]")
    if unread:
        print(f"Не прочитано (файл вне записи не открылся): {len(unread)}")
        for key in unread:
            print(f"    не прочитано: {key}")
    print()

    if changed or gone:
        parts = [f"тело изменено: {len(changed)}", f"тела нет на диске: {len(gone)}",
                 f"сверено и равно: {verified} из {len(pairs)} пар"]
        if unverified:
            parts.append(f"не сверено пар: {len(unverified)}")
        print("ИТОГ: РАСХОДИТСЯ — " + " · ".join(parts))
        return EXIT_DIVERGES
    if unverified:
        if second_dir is None and any(upd.is_second_rel(pathlib.Path(k)) for k, _ in unverified):
            reason = (f"второй каталог не найден ({second_note})" if second_note else
                      f"второй каталог не объявлен (в файле путей контура нет ключа {upd.PROTOTYPE_DIR_KEY})")
        else:
            reason = "файлы записи не читаются"
        return nothing_to_check(f"{reason} — не сверено пар: {len(unverified)}, сверено и равно: {verified}")
    print(f"ИТОГ: СОВПАЛО — сверено файлов: {verified} (число пар записи: {len(pairs)})")
    return EXIT_MATCH


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
