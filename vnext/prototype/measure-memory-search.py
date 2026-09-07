# -*- coding: utf-8 -*-
"""measure-memory-search.py — критерий ② карточки #525: поиск по памяти вместо чтения
раздела целиком. Сколько ЗНАКОВ экономит find-phoenix.py против read-phoenix.py и
находит ли он ожидаемое слово — по фиксированному набору запросов (JSON, форма —
measurements/memory-search-coord-10.json: n/query/role/section/expect_word/counter3/note).

ЗАЧЕМ. find-phoenix.py (карточка #525, часть А, пункт 3) обещает: искать словами
дешевле, чем читать раздел памяти целиком. Обещание не проверено числом. Этот файл —
измеритель ЖАНРА measure-tool-brevity.py / measure-context-cost.py: НЕ приёмка (нет
различающих случаев и нарочной поломки), а замер — печатает то, что есть, включая
провал отдельного запроса как ДАННЫЕ, а не сбой этого файла.

МЕТОД, ЧЕСТНО ПРО ДВЕ ПОЛОВИНЫ (иначе число легко принять за больше, чем оно есть):
  · ЭКОНОМИЯ считается по ОБЫЧНОМУ выводу find-phoenix.py (без --full-body) — тому,
    что роль вправду читает при поиске. «ДО» — длина ПОЛНОГО вывода read-phoenix.py
    для той же роли (--role R --db <база>, БЕЗ --section — целиком, как читает
    проснувшаяся роль), один раз на роль, дальше берётся из памяти процесса.
  · ПОПАДАНИЕ (нашёлся ли expect_word) проверяется ПО ТЕЛУ записи из таблицы
    phoenix_records — отдельным чтением по id первых до трёх найденных записей,
    а НЕ по обычному выводу (там — обрезанный кусок текста вокруг слова). Смешать
    два вопроса в одно число значило бы солгать про экономию: --full-body раздул бы
    «ПОСЛЕ» ровно тем же текстом, ради которого выгоднее было бы читать раздел целиком.

ПОЛЕ «section» В НАБОРЕ — ДОГАДКА СОСТАВИТЕЛЯ, НЕ ПРИКАЗ (правка по слову COORD).
По умолчанию --section в find-phoenix.py НЕ передаётся: живая роль ищет по ВСЕЙ
памяти, а не по разделу, который угадал составитель набора (у трёх запросов из
десяти факт лежит в ДРУГОМ разделе). Флаг --use-section включает прежнее
поведение (раздел из набора уходит в find-phoenix.py как фильтр) — для сравнения
«с фильтром / без фильтра». В таблице печатаются РЯДОМ «раздел найденной записи»
и «ожидался» (из набора), с меткой ≠ при расхождении — граница честно названа:
раздел найденной записи берётся из phoenix_records (SELECT section ...), поэтому
заполняется ТОЛЬКО когда find-phoenix.py вернул хотя бы одну запись (код 0);
у кода 3 (слово есть в тексте раздела, записи не разобраны — записей ВООБЩЕ нет)
раздел найденной записи не печатается, это ДРУГОЙ факт, показанный отдельной
графой исхода «в тексте», а не подмена.

ИСХОД «в тексте» — ОТДЕЛЬНАЯ ГРАФА, НЕ «нет» (правка по слову COORD). Код 3
find-phoenix.py означает «слово есть в сыром тексте раздела, но записи ещё не
разобраны/отстают» — это не то же самое, что «нигде нет», и смешивать их в
одно число значило бы врать про то, чего не хватает: не самого факта, а его
разбора на записи.

ИСХОД «в архиве» — ТОЖЕ ОТДЕЛЬНАЯ ГРАФА, НЕ «нет» (находка приёмщицы COORD,
записка #5005). Код 4 find-phoenix.py означает «в живой памяти нет нигде, но
в АРХИВЕ есть» — до этой правки такой запрос считался тем же «не нашёл», что
и код 2 («нет вообще, даже в архиве»), и итог врал про то, чего не хватает:
не самого факта, а его присутствия в ГОРЯЧЕЙ памяти.

ЧЕГО ЭТО НЕ СУДИТ (замер, не приёмка — границы названы вслух):
  · не проверяет корректность самого find-phoenix.py (уровни записи/тело/архив,
    префиксный поиск, подсказку кто-читает) — это дело его собственной приёмки;
  · не покрывает роли и разделы вне набора --set;
  · холодный/тёплый диск не различает — один прогон, время диска не усреднено;
  · код возврата 0 означает «прогон состоялся», а не «результат хороший» — числа
    в таблице и итоге судит тот, кто их читает, не этот код.

ЗАПУСК:
    python measure-memory-search.py --set <КОНТУР>/vnext-tools/measurements/memory-search-coord-10.json --db <копия>
    python measure-memory-search.py --set <json> --db <копия> --out <результат.json>
    python measure-memory-search.py --set <json> --db <копия> --use-section    # прежнее поведение, для сравнения
    python measure-memory-search.py --set <json> --role COORD
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402 — своя копия рядом (vnext-tools), как у measure-tool-brevity.py

# Абсолютные пути от расположения ЭТОГО файла, а не от текущего каталога (R15a) —
# тот же класс, из-за которого относительный вызов инструментов контура запрещён.
FIND_PHOENIX = HERE.parent / ".mezosync" / "scripts" / "find-phoenix.py"
READ_PHOENIX = FIND_PHOENIX.parent / "read-phoenix.py"
LIVE_DB = mezo_paths.live_db()   # дефолт --db, как у measure-context-cost.py

ACTOR = "PROTO"                  # кто ищет (роль руки) — отдельно от --role (чья память)
TIMEOUT_S = 60

RESPONSE_LINE = re.compile(
    r"ОТВЕТ:\s*(\d+)\s*записей\s*·\s*(\d+)\s*знаков\s*·\s*([0-9.]+)\s*с")
RECORD_HEADER = re.compile(r"^#(\d+)\s*·", re.MULTILINE)

STATUS_FIRST = "первой"
STATUS_TOP3 = "в трёх"
STATUS_SECTION_TEXT = "в тексте"   # код 3: слово в сыром тексте раздела, записей нет вовсе
STATUS_ARCHIVE = "в архиве"        # код 4: в живой памяти нет, есть в архиве — не «нет нигде»
STATUS_NONE = "нет"


def fmt_num(n: int) -> str:
    """1234 → «1 234» — та же разрядка, что у соседних измерителей."""
    return f"{n:,}".replace(",", " ")


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def run_subprocess(argv: list[str]) -> tuple[str, str, int | None, float, str | None]:
    """Один вызов подпроцесса. Возвращает (stdout, stderr, код, время_с, ошибка_запуска)."""
    start = time.perf_counter()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=TIMEOUT_S)
        elapsed = time.perf_counter() - start
        return r.stdout or "", r.stderr or "", r.returncode, elapsed, None
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start
        return "", "", 124, elapsed, f"превышен предел ожидания {TIMEOUT_S} с"
    except OSError as e:
        elapsed = time.perf_counter() - start
        return "", "", None, elapsed, str(e)


def run_find_phoenix(role: str, query: str, section: str | None,
                      db_arg: str) -> tuple[str, str, int | None, float, str | None]:
    argv = [sys.executable, str(FIND_PHOENIX), "--role", role, query]
    if section:
        argv += ["--section", section]
    argv += ["--db", db_arg, "--actor", ACTOR]
    return run_subprocess(argv)


def run_read_phoenix(role: str, db_arg: str) -> tuple[str, str, int | None, float, str | None]:
    # ⚠️ ФОРМА ВЫЗОВА ДОСЛОВНО ИЗ ЗАДАНИЯ: --role R --db <база>, БЕЗ --section и
    # БЕЗ --actor — приёмка сверяет число «ДО» независимым прогоном ЭТОЙ ЖЕ строки.
    argv = [sys.executable, str(READ_PHOENIX), "--role", role, "--db", db_arg]
    return run_subprocess(argv)


def chars_before(role: str, db_arg: str, cache: dict[str, int]) -> int:
    """Длина ПОЛНОГО вывода read-phoenix.py для роли — раз на роль, дальше из cache."""
    if role in cache:
        return cache[role]
    out, err, code, _elapsed, error = run_read_phoenix(role, db_arg)
    text = out + err
    if error or code != 0:
        print(f"⚠️ read-phoenix.py для роли {role} вернул код {code}"
              f"{' · ' + error if error else ''} — число ДО всё равно взято по факту "
              f"вывода ({len(text)} знаков)", file=sys.stderr)
    cache[role] = len(text)
    return cache[role]


def record_info(conn: sqlite3.Connection, record_id: int) -> tuple[str, str] | None:
    """(раздел, тело) записи по id — прямо из phoenix_records, не из вывода поиска."""
    try:
        row = conn.execute("SELECT section, body FROM phoenix_records WHERE id=?",
                            (record_id,)).fetchone()
    except sqlite3.Error:
        return None
    return (row[0], row[1]) if row else None


def match_status(conn: sqlite3.Connection, record_ids: list[str],
                  expect_word: str) -> tuple[str, int | None, str | None]:
    """(исход, номер записи 1..3 где нашлось — либо None, раздел ЭТОЙ записи).

    Судит ТЕЛО, не сниппет. Если expect_word не в теле ни одной из первых трёх,
    раздел всё равно берётся у ПЕРВОЙ найденной записи — это честная видимость
    того, ЧТО поиск вернул, а не подтверждение попадания (статус останется «нет»,
    раздел — просто соседняя графа для сверки с ожиданием составителя набора).
    """
    needle = (expect_word or "").lower()
    records: list[tuple[str, str, str]] = []
    for rid in record_ids[:3]:
        info = record_info(conn, int(rid))
        if info is not None:
            records.append((rid, info[0], info[1]))
    if needle:
        for rank, (_rid, section, body) in enumerate(records, start=1):
            if body and needle in body.lower():
                return (STATUS_FIRST if rank == 1 else STATUS_TOP3), rank, section
    fallback_section = records[0][1] if records else None
    return STATUS_NONE, None, fallback_section


def measure_one(q: dict, db_arg: str, before_cache: dict[str, int],
                 conn: sqlite3.Connection, use_section: bool) -> dict:
    role = str(q["role"]).upper()
    query_text = str(q["query"])
    expected_section = q.get("section")
    section_arg = expected_section if use_section else None
    expect_word = str(q.get("expect_word", ""))

    before = chars_before(role, db_arg, before_cache)
    out, err, code, elapsed, error = run_find_phoenix(role, query_text, section_arg, db_arg)
    text = out + err

    m = RESPONSE_LINE.search(text)
    n_records = int(m.group(1)) if m else 0
    after = int(m.group(2)) if m else len(text)
    tool_elapsed = float(m.group(3)) if m else None

    found_section = None
    if error is not None:
        status, rank = STATUS_NONE, None
    elif code == 0 and n_records > 0:
        ids = RECORD_HEADER.findall(out)
        status, rank, found_section = match_status(conn, ids, expect_word)
    elif code == 3:
        # Слово есть в сыром тексте раздела, но find-phoenix.py вернул НОЛЬ записей —
        # у нас нет id, значит и раздела ИМЕННО НАЙДЕННОЙ ЗАПИСИ нет: честная пустота,
        # не подмена (см. шапку файла). Исход — своя графа, не «нет» (слово COORD).
        status, rank = STATUS_SECTION_TEXT, None
    elif code == 4:
        # В живой памяти нигде нет, но в АРХИВЕ есть — это ДРУГОЙ факт, чем «нет нигде»
        # (находка приёмщицы COORD, записка #5005): «не нашёл» до этой правки сливал
        # код 2 (нет нигде) и код 4 (есть в архиве) в одно число, и число врало про то,
        # чего не хватает — не факта вообще, а его присутствия в ГОРЯЧЕЙ памяти.
        status, rank = STATUS_ARCHIVE, None
    else:
        status, rank = STATUS_NONE, None

    mismatch = bool(found_section and expected_section and found_section != expected_section)
    savings_pct = ((before - after) / before * 100) if before else None

    return dict(
        n=q.get("n"), query=query_text, role=role,
        expected_section=expected_section, found_section=found_section,
        section_mismatch=mismatch, use_section=use_section,
        expect_word=expect_word, counter3=bool(q.get("counter3", False)),
        note=q.get("note", ""), occurrences=q.get("occurrences"),
        exit_code=code, launch_error=error, n_records=n_records,
        chars_before=before, chars_after=after,
        savings_pct=(round(savings_pct, 1) if savings_pct is not None else None),
        match_status=status, match_rank=rank,
        elapsed_s=round(elapsed, 3),
        tool_elapsed_s=tool_elapsed,
    )


def print_table(rows: list[dict]) -> None:
    use_section = bool(rows) and rows[0]["use_section"]
    width = 128
    print("=" * width)
    print(f"ЗАМЕР КРИТЕРИЯ ② КАРТОЧКИ #525 — поиск (find-phoenix.py) против полного "
          f"чтения (read-phoenix.py), {len(rows)} запросов "
          f"({'с --section из набора' if use_section else 'без --section — по всей памяти'})")
    print("=" * width)
    print(f"{'n':>3} {'запрос':26} {'код':>4} {'исход':9} "
          f"{'раздел':9} {'ожидался':9} {'≠':^2} "
          f"{'знаков ДО':>10} {'→':^3} {'ПОСЛЕ':>7} {'T, с':>7}")
    for r in rows:
        code_s = str(r["exit_code"]) if r["exit_code"] is not None else "—"
        found_s = r["found_section"] or "—"
        expect_s = r["expected_section"] or "—"
        flag = "≠" if r["section_mismatch"] else ""
        print(f"{str(r['n']):>3} {truncate(r['query'], 26):26} {code_s:>4} "
              f"{r['match_status']:9} {found_s:9} {expect_s:9} {flag:^2} "
              f"{fmt_num(r['chars_before']):>10} "
              f"{'→':^3} {fmt_num(r['chars_after']):>7} {r['elapsed_s']:>7.3f}")
        if r["launch_error"]:
            print(f"     ⚠️ поиск не запустился: {r['launch_error']}")
    print("-" * width)


def print_summary(rows: list[dict]) -> dict:
    total = len(rows)
    n_first = sum(1 for r in rows if r["match_status"] == STATUS_FIRST)
    n_top3 = sum(1 for r in rows if r["match_status"] == STATUS_TOP3)
    n_section_text = sum(1 for r in rows if r["match_status"] == STATUS_SECTION_TEXT)
    n_archive = sum(1 for r in rows if r["match_status"] == STATUS_ARCHIVE)
    n_none = sum(1 for r in rows if r["match_status"] == STATUS_NONE)
    n_mismatch = sum(1 for r in rows if r["section_mismatch"])
    avg_before = sum(r["chars_before"] for r in rows) / total if total else 0
    avg_after = sum(r["chars_after"] for r in rows) / total if total else 0
    savings_pct = ((avg_before - avg_after) / avg_before * 100) if avg_before else 0.0

    print(f"ИТОГ: первым {n_first} из {total} · в первых трёх {n_top3} · "
          f"в тексте раздела {n_section_text} · в архиве {n_archive} · "
          f"не нашёл {n_none} · знаков ДО (полное чтение) {fmt_num(round(avg_before))} · "
          f"среднее ПОСЛЕ {fmt_num(round(avg_after))} · экономия {savings_pct:.1f} %")
    print(f"раздел найденной записи разошёлся с ожиданием набора: {n_mismatch} из {total}")

    total3 = sum(1 for r in rows if r["counter3"])
    found3 = sum(1 for r in rows if r["counter3"]
                 and r["match_status"] in (STATUS_FIRST, STATUS_TOP3))
    print(f"утверждений для встречного ③: найдено {found3} из {total3}")
    print("=" * 128)

    return dict(
        total_queries=total, found_first=n_first, found_top3=n_top3,
        found_section_text=n_section_text, found_archive=n_archive,
        not_found=n_none, section_mismatch=n_mismatch,
        chars_before_avg=round(avg_before, 1), chars_after_avg=round(avg_after, 1),
        savings_pct=round(savings_pct, 1),
        counter3_total=total3, counter3_found=found3,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Замер критерия ② карточки #525: поиск по памяти (find-phoenix.py) "
                     "вместо чтения раздела целиком (read-phoenix.py) — сколько знаков "
                     "экономит и находит ли ожидаемое слово, по набору запросов из --set.")
    ap.add_argument("--set", required=True,
                     help="путь к JSON-набору запросов (список словарей n/query/role/"
                          "section/expect_word/counter3/note)")
    ap.add_argument("--db", default=str(LIVE_DB),
                     help="путь к mezosync.db для замера (по умолчанию — живая база, "
                          "ищется от расположения инструментов); для прогона на копии "
                          "передай сюда путь к копии")
    ap.add_argument("--out", default=None, help="куда сохранить результаты замера в JSON")
    ap.add_argument("--role", default=None,
                     help="сузить набор до одной роли (регистр не важен)")
    ap.add_argument("--use-section", dest="use_section", action="store_true",
                     help="передавать find-phoenix.py раздел из набора как фильтр "
                          "--section (прежнее поведение); по умолчанию ВЫКЛЮЧЕНО — "
                          "поиск идёт по всей памяти роли, раздел из набора только "
                          "печатается рядом как ожидание составителя")
    args = ap.parse_args()

    if not FIND_PHOENIX.exists():
        print(f"⛔ поиск не запускается: инструмент не найден: {FIND_PHOENIX}", file=sys.stderr)
        return 1
    if not READ_PHOENIX.exists():
        print(f"⛔ поиск не запускается: инструмент не найден: {READ_PHOENIX}", file=sys.stderr)
        return 1

    set_path = Path(args.set)
    try:
        raw = set_path.read_text(encoding="utf-8")
        queries = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"⛔ набор не прочитан: {set_path} — {e}", file=sys.stderr)
        return 1
    if not isinstance(queries, list) or not queries:
        print(f"⛔ набор не прочитан: {set_path} — ожидался непустой список запросов",
              file=sys.stderr)
        return 1

    if args.role:
        role_filter = args.role.upper()
        queries = [q for q in queries if str(q.get("role", "")).upper() == role_filter]
        if not queries:
            print(f"⛔ набор не прочитан: после сужения по роли {role_filter} "
                  f"запросов не осталось", file=sys.stderr)
            return 1

    db_path = Path(args.db).resolve()
    db_arg = str(db_path)
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM phoenix_records LIMIT 1")
    except sqlite3.Error as e:
        print(f"⛔ поиск не запускается: база {db_path} недоступна для чтения "
              f"записей памяти — {e}", file=sys.stderr)
        return 1

    before_cache: dict[str, int] = {}
    rows = [measure_one(q, db_arg, before_cache, conn, args.use_section) for q in queries]
    conn.close()

    print_table(rows)
    summary = print_summary(rows)

    launch_failures = sum(1 for r in rows if r["launch_error"])
    if launch_failures == len(rows):
        print(f"⛔ поиск не запускается: все {len(rows)} вызовов find-phoenix.py "
              f"упали до запуска — см. launch_error по каждой строке", file=sys.stderr)
        return 1
    if launch_failures:
        print(f"⚠️ вызовов, не запустившихся вовсе: {launch_failures} из {len(rows)} — "
              f"это ДАННЫЕ замера (см. таблицу), не отказ измерителя", file=sys.stderr)

    if args.out:
        set_version = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        payload = dict(
            measured_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            set_path=str(set_path.resolve()),
            set_version=set_version,
            db=str(db_path),
            use_section=args.use_section,
            rows=rows,
            summary=summary,
        )
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"сохранено: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
