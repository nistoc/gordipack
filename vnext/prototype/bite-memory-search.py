#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bite-memory-search.py — приёмка карточки #525: поиск по памяти роли словами
(find-phoenix.py) вместо чтения раздела памяти целиком (read-phoenix.py).

ПРЕДМЕТЫ ПРИЁМКИ:
  · find-phoenix.py (.mezosync/scripts) — три ступени поиска (записи → тело раздела →
    архив), четыре исхода кодом (0/2/3/4), пятый (5) — нет индекса записей в базе;
  · хук в save-phoenix.py — после сохранения тела раздела слой записей памяти
    (phoenix_records) пересобирается ТЕМ ЖЕ ходом, без отдельной команды роли;
  · measure-memory-search.py (если сдан) — числовой замер экономии и попаданий;
  · слой phoenix_records и memory-records.py --собрать — сверка «записи ⇒ тело».

⚖️ ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
  · эта приёмка НЕ судит корректность самого разбора на записи (memory-records.py
    --разобрать/--пересобрать) — там своя приёмка;
  · НЕ судит числа экономии (это дело measure-memory-search.py) — случай ④ проверяет
    только форму его вывода (строка итога, файл --out), не сами цифры;
  · слова запросов и записи, за которые цепляются случаи а)/б)/в), приёмка ВЫБИРАЕТ
    САМА по живым данным копии на каждом прогоне (а не хранит готовый список) —
    иначе приёмка молчала бы, стоило конкретной записи уйти из памяти ролей;
  · случаи ①②③г) зовут find-phoenix.py БЕЗ --section (слово COORD 2026-09-07 к этой
    приёмке: поле section в наборе measurements/memory-search-coord-10.json угадано
    составителем набора и у части запросов неверно; case в) может передавать --section,
    её предмет — конкретный раздел).

⛔ ЖИВАЯ БАЗА (<КОНТУР>/.mezosync/mezosync.db) НЕ ИЗМЕНЯЕТСЯ НИ ОДНИМ ИЗ СЛУЧАЕВ:
все прогоны — на копии (mezo_stand.new + shutil.copy2), открытой на запись только
внутри временного рабочего каталога. Отпечаток живой базы (число записей памяти,
максимальный id ленты) снимается ДО и ПОСЛЕ всего прогона и печатается в итоге.

═══ СЛУЧАИ (10, жанр приёмки: случай(имя, ок, слово), итог «✅ принято N из N» либо
     «🔴 красных K из N», код возврата 0/1) ═══
  ① три запроса критерия («права», «остановка смены», «будильник») на роли COORD
     возвращают код 0, записи с id, строку «ОТВЕТ: N записей · M знаков · T с».
  ② словоформа «права на отправку кода» → громкая строка повтора по началу слова
     («точных слов нет — ищу по началу слов: ...») и код 0.
  ③ ВСТРЕЧНЫЙ случай карточки #525 (правило свода `counter-case-own-definition`
     — предмет здесь определён НЕ примерами из ①②, а отдельным набором с полем
     expect_word): пять утверждений из measurements/memory-search-coord-10.json
     с counter3=true. Для каждого — expect_word обязан найтись в теле первой или
     одной из первых трёх найденных записей (код 0), либо, при коде 3, в ЖИВОМ
     тексте раздела, который find-phoenix.py назвал «не разобран/отстают». Итог —
     «найдено a из 5», порог a ≥ 3 (назван в печати явно).
  ④ measure-memory-search.py (если сдан) печатает «первым N из 10» и сохраняет
     результат в JSON через --out. Файла нет — случай помечается «пропущен»,
     а не красным: судить отсутствующую чужую работу нечем.
  а) снятая запись: приёмка САМА находит в копии слово, которое встречается ровно
     в ОДНОЙ записи роли COORD, помечает эту запись alive='revoked' и ищет то же
     слово БЕЗ --revoked — запись обязана выйти в ответе с пометкой ⚰️ «снята».
  б) слово, которого нет в живой памяти НИ ОДНОЙ роли, но есть в архиве, — код 4
     и строка «в архиве». Слово — ОДНО (не фраза): при трёх и более словах
     запроса включается третья ступень поиска (по части слов), и архив, третий
     по счёту, может не понадобиться проверить вовсе.
  в) раздел без единой записи (роль, у которой phoenix_records пуст целиком, а
     тело раздела — нет; типично CORE/ING, но приёмка проверяет это ЗАПРОСОМ,
     а не по имени роли) → код 3 и пояснение «не разобран»/«отстают». Запасной
     ход, если вдруг такой роли не нашлось: очистить в копии
     phoenix_records role='PROTO' AND section='history' и работать по PROTO.
  в-бис) слова «xyzzyqwerty» нет нигде → код 2 и строка «может быть».
  г) регистр: «Права»/«права» и --role COORD/--role coord дают ОДНО множество id
     (роль — потому что регистр нормализуется к верхнему всегда; слово — потому
     что поиск по записям слепой к регистру буквы).
  д) ХУК save-phoenix.py: сохранение раздела печатает «🧩 записи раздела: ...» и
     memory-records.py --собрать после этого сходится знак в знак; повторное
     сохранение ТЕМ ЖЕ телом (ветка «СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ») строку «🧩» НЕ
     печатает — хук зовётся только когда тело действительно записано заново.

═══ НАРОЧНЫЕ ПОЛОМКИ (--break {case-fold,no-level2,no-hook}), каждая — своя ЛИЧНАЯ
     копия ОДНОГО инструмента в рабочем каталоге; живой файл не трогается ни разу.
     Копию строит mezo_stand.copy_tool (инструмент + модули-соседи по обычным
     import — транзитивно) — ПЛЮС read-phoenix.py вручную для find-phoenix.py:
     он подключается importlib-ом по прямому пути, обычный обход соседей его не
     видит, и без него загрузка сломанной копии падала бы на «нет такого файла»
     раньше, чем дойдёт до самой поломки. ═══
  · case-fold — в копии find-phoenix.py после ступени A (точный AND по записям)
    добавлен постфильтр: каждый токен запроса обязан войти В ТОЧНОМ РЕГИСТРЕ, КАК
    НАПЕЧАТАН, в subject+body найденной записи. На ЖИВОМ инструменте «Права» и
    «права» дают одно множество id (записи — не то же самое, что буквы регистра
    заглавные, но токен FTS5 регистр сворачивает); на СЛОМАННОЙ копии множества
    расходятся (проверено: «Права» и «права» на COORD дают РАЗНЫЕ id) → проваливается
    РОВНО случай г). Остальные случаи поломки не касаются: они всегда зовут ЖИВОЙ
    find-phoenix.py, только случай г) в этом прогоне получает сломанную копию.
  · no-level2 — в копии find-phoenix.py уровень 2 (тело раздела) отключён: строка
    `matched_sections = _level2_exact(...)` и повтор по началу слова заменены на
    `matched_sections = []` безусловно. Случай в) (CORE/ING без единой записи, слово
    есть только в тексте) на сломанной копии не находит уровень 2 и падает мимо
    кода 3 → проваливается РОВНО случай в). Остальные случаи по-прежнему зовут
    живой find-phoenix.py.
  · no-hook — в копии save-phoenix.py закомментирован единственный вызов
    `rebuild_records(args.db, role, args.section, actor)`. Случай д) на сломанной
    копии не получает строку «🧩 записи раздела» после сохранения → проваливается
    РОВНО случай д). memory-records.py и find-phoenix.py в этом прогоне не тронуты.
  Флаг --tool-dir подменяет каталог, откуда случаи БЕЗ поломки берут find-phoenix.py
  и save-phoenix.py (по умолчанию — живой .mezosync/scripts; нужен для ручной
  проверки другой копии инструментов). На нарочные поломки не влияет: у каждой из
  них своя копия строится ОТ ЖИВОГО инструмента намеренно — иначе поломка судила бы
  чужую, уже подменённую копию, а не тот код, который реально стоит в контуре.

Запуск:
    python <КОНТУР>/vnext-tools/bite-memory-search.py
    python <КОНТУР>/vnext-tools/bite-memory-search.py --break case-fold
    python <КОНТУР>/vnext-tools/bite-memory-search.py --break no-level2
    python <КОНТУР>/vnext-tools/bite-memory-search.py --break no-hook
    python <КОНТУР>/vnext-tools/bite-memory-search.py --keep

Карточка #525. Задание PROTO A5.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный рабочий каталог убирается при успехе, остаётся при провале

CONTAINER = mezo_paths.container_root(__file__)
LIVE_DB = mezo_paths.live_db(__file__)
LIVE_SCRIPTS = mezo_paths.live_scripts(__file__)          # .mezosync/scripts
TOOLS_DIR = Path(__file__).resolve().parent                # vnext-tools

FIND_PHOENIX_NAME = "find-phoenix.py"
READ_PHOENIX_NAME = "read-phoenix.py"
SAVE_PHOENIX_NAME = "save-phoenix.py"
MEMORY_RECORDS = TOOLS_DIR / "memory-records.py"
MEASURE_TOOL = TOOLS_DIR / "measure-memory-search.py"
QUERY_SET = TOOLS_DIR / "measurements" / "memory-search-coord-10.json"

ACTOR = "PROTO"                     # чья рука ищет (не то же самое, что --role — чья память)
RECORD_HEADER_RE = re.compile(r"^#(\d+)\s·", re.MULTILINE)
ANSWER_LINE_RE = re.compile(r"ОТВЕТ: \d+ записей · \d+ знаков · [\d.]+ с")

results: list[tuple[str, bool]] = []
skipped: list[tuple[str, str]] = []


def case_result(name: str, ok: bool, note: str) -> bool:
    results.append((name, ok))
    print(f"{'✅' if ok else '🔴'} {name}")
    for line in note.splitlines():
        print(f"   {line}")
    return ok


def case_skip(name: str, reason: str) -> None:
    skipped.append((name, reason))
    print(f"⚪ {name}")
    print(f"   пропущен: {reason}")


def run_tool(tool: Path, argv: list[str], env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(tool), *argv], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def run_find(tool: Path, db: Path, role: str, query: str, section: str | None = None,
            env: dict | None = None) -> tuple[int, str]:
    argv = ["--role", role, query, "--db", str(db), "--actor", ACTOR]
    if section:
        argv += ["--section", section]
    return run_tool(tool, argv, env=env)


def record_ids(output: str) -> list[str]:
    return RECORD_HEADER_RE.findall(output)


# ═══ СБОРКА СЛОМАННЫХ КОПИЙ ══════════════════════════════════════════════════════

def build_broken_find_phoenix(sandbox_name: str, anchor: str, replacement: str) -> tuple[Path, dict]:
    """Сломанная копия find-phoenix.py в СВОЁМ рабочем каталоге + read-phoenix.py
    рядом (importlib-загрузка по прямому пути, обычный обход соседей его не ловит).
    Возвращает (путь к копии, окружение подпроцесса с MEZO_CONTAINER — без него
    загрузка копии падает на поиске каталога группы для memory-archive.py раньше,
    чем дойдёт до самой поломки, см. mezo_paths.container_root)."""
    live_tool = LIVE_SCRIPTS / FIND_PHOENIX_NAME
    sandbox = mezo_stand.new(sandbox_name)
    broken = mezo_stand.copy_tool(live_tool, sandbox)
    read_phoenix_copy = sandbox / READ_PHOENIX_NAME
    if not read_phoenix_copy.exists():
        shutil.copy2(LIVE_SCRIPTS / READ_PHOENIX_NAME, read_phoenix_copy)
    text = broken.read_text(encoding="utf-8")
    if anchor not in text:
        raise SystemExit(
            f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь нарочной поломки не найден в {broken.name} "
            "(живой инструмент, видимо, поправили под рукой) — обратный ход ставить "
            "не на чем, зелёное было бы ложным. Перечитай find-phoenix.py и обнови якорь.")
    patched = text.replace(anchor, replacement, 1)
    if patched == text:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена нарочной поломки не сработала")
    broken.write_text(patched, encoding="utf-8")
    env = os.environ.copy()
    env["MEZO_CONTAINER"] = str(CONTAINER)
    return broken, env


CASE_FOLD_ANCHOR = (
    "    rows = _fetch_records(conn, role, match_query, args.section, args.revoked, args.limit)\n"
)
CASE_FOLD_REPLACEMENT = (
    "    rows = _fetch_records(conn, role, match_query, args.section, args.revoked, args.limit)\n"
    "    rows = [r for r in rows if all(t in (r[2] + r[8]) for t in tokens)]"
    "  # ПОЛОМКА case-fold: регистр запроса сравнивается буквально, без сворачивания\n"
)

NO_LEVEL2_ANCHOR = (
    "    matched_sections = _level2_exact(conn, role, tokens, args.phrase)\n"
    "    if not matched_sections and stemming_helps:\n"
    "        matched_sections = _level2_stemmed(conn, role, tokens, stems, args.phrase)\n"
)
NO_LEVEL2_REPLACEMENT = (
    "    matched_sections = []  # ПОЛОМКА no-level2: уровень 2 отключён нарочно, безусловно\n"
)


def build_broken_save_phoenix(sandbox_name: str) -> tuple[Path, dict]:
    """Сломанная копия save-phoenix.py: единственный вызов пересборки слоя записей
    закомментирован. Модули-соседи (mezo_paths, dryrun, а через mezo_paths —
    транзитивно lease) едут через mezo_stand.copy_tool — они подключены обычным
    import. Возвращает (путь к копии, окружение с MEZO_CONTAINER) — lease.check()
    внутри resolve_db() сам просит каталог группы (второй замок mezo_paths.py),
    и без переменной копия падает на этом раньше, чем дойдёт до самой поломки."""
    live_tool = LIVE_SCRIPTS / SAVE_PHOENIX_NAME
    sandbox = mezo_stand.new(sandbox_name)
    broken = mezo_stand.copy_tool(live_tool, sandbox)
    text = broken.read_text(encoding="utf-8")
    anchor = "    rebuild_records(args.db, role, args.section, actor)\n"
    if anchor not in text:
        raise SystemExit(
            f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь нарочной поломки не найден в {broken.name} "
            "(живой инструмент, видимо, поправили под рукой) — обратный ход ставить "
            "не на чем, зелёное было бы ложным. Перечитай save-phoenix.py и обнови якорь.")
    replacement = "    # rebuild_records(args.db, role, args.section, actor)  # ПОЛОМКА no-hook: вызов снят\n"
    patched = text.replace(anchor, replacement, 1)
    if patched == text:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена нарочной поломки no-hook не сработала")
    broken.write_text(patched, encoding="utf-8")
    env = os.environ.copy()
    env["MEZO_CONTAINER"] = str(CONTAINER)
    return broken, env


# ═══ ПОДБОР РАБОЧЕГО МАТЕРИАЛА ИЗ ЖИВЫХ ДАННЫХ КОПИИ ═════════════════════════════
# Слова и записи для случаев а)/б)/в) приёмка находит САМА на каждом прогоне —
# готовый список молчал бы, стоило конкретной записи уйти из памяти ролей.

def pick_unique_word(conn: sqlite3.Connection, role: str, min_len: int = 9) -> tuple[int, str] | None:
    """Запись и слово, которое встречается РОВНО в одной записи роли — материал
    случая а). Слово — от min_len знаков кириллицей, чтобы не задеть частые формы."""
    rows = conn.execute("SELECT id, body FROM phoenix_records WHERE role=?", (role,)).fetchall()
    owners: dict[str, set[int]] = {}
    for rid, body in rows:
        for token in set(re.findall(r"[а-яё]+", body.lower())):
            if len(token) >= min_len:
                owners.setdefault(token, set()).add(rid)
    for token in sorted(owners):
        if len(owners[token]) == 1:
            return next(iter(owners[token])), token
    return None


def _search_stem(token: str) -> str:
    """Тот же приём усечения, что у find-phoenix.py: начало слова от 5 знаков.
    Нужен здесь, чтобы не выбрать для случая б) слово, которое НЕ встречается
    буквально, но её начало совпадает с живым словом — тогда повтор по началу
    слова находит запись, и вместо кода 4 приёмка получает код 0 (найдено живой
    записью). Опыт первого прогона поймал это на слове «вернули» → живой «вернуть»."""
    if token.isdigit() or len(token) < 5:
        return token
    return token[:max(4, len(token) - 2)]


def pick_archive_only_word(conn: sqlite3.Connection, min_len: int = 7) -> tuple[str, str] | None:
    """Роль и ОДНОСЛОВНЫЙ (без пробела) токен, который есть в архиве роли, но НЕТ
    в живой памяти НИ ОДНОЙ роли — материал случая б). Однословность — по слову
    COORD к этой приёмке: при трёх и более словах включается третья ступень поиска
    (по части слов), а до архива очередь может не дойти вовсе.

    ⚠️ «НЕТ в живой памяти» проверяется не только дословно, но и НАЧАЛОМ слова:
    find-phoenix.py при пустом точном совпадении сам повторяет поиск по началу —
    словом, чьё начало совпало с ЖИВЫМ словом другой словоформы, код 4 не получить."""
    live_vocab: set[str] = set()
    for (body,) in conn.execute("SELECT body FROM phoenix"):
        live_vocab |= set(re.findall(r"[а-яё]+", body.lower()))
    live_stem_starts = {_search_stem(t) for t in live_vocab if len(t) >= 5}
    for role, body in conn.execute("SELECT role, body FROM phoenix_archive"):
        for token in set(re.findall(r"[а-яё]+", body.lower())):
            if len(token) < min_len or token in live_vocab:
                continue
            stem = _search_stem(token)
            if any(s.startswith(stem) or stem.startswith(s) for s in live_stem_starts):
                continue
            return role, token
    return None


def pick_role_without_records(conn: sqlite3.Connection) -> str | None:
    """Роль, у которой phoenix_records ПУСТ ЦЕЛИКОМ (по всем разделам) — типичный
    материал случая в). Проверено ЗАПРОСОМ, а не именем роли."""
    row = conn.execute(
        "SELECT role FROM phoenix WHERE role NOT IN "
        "(SELECT DISTINCT role FROM phoenix_records) LIMIT 1").fetchone()
    return row[0] if row else None


def pick_body_word(conn: sqlite3.Connection, role: str, min_len: int = 7) -> tuple[str, str] | None:
    """Раздел и слово из ЖИВОГО тела роли (то, что могло бы найтись только уровнем 2,
    не записями) — вторая половина материала случая в)."""
    for section, body in conn.execute("SELECT section, body FROM phoenix WHERE role=?", (role,)):
        tokens = sorted(t for t in set(re.findall(r"[а-яё]+", body.lower())) if len(t) >= min_len)
        if tokens:
            return section, tokens[0]
    return None


# ═══ СЛУЧАИ ═══════════════════════════════════════════════════════════════════════

def case_1(find_tool: Path, db: Path) -> bool:
    queries = ["права", "остановка смены", "будильник"]
    lines, ok = [], True
    for q in queries:
        code, out = run_find(find_tool, db, "COORD", q)
        ids = record_ids(out)
        answer_ok = bool(ANSWER_LINE_RE.search(out))
        q_ok = (code == 0) and bool(ids) and answer_ok
        ok = ok and q_ok
        lines.append(f"«{q}»: код {code} · записей {len(ids)} (id {', '.join(ids) or '—'}) "
                    f"· строка ОТВЕТ {'есть' if answer_ok else 'НЕТ'}")
    return case_result("① три запроса критерия на роли COORD → код 0, записи, строка ОТВЕТ",
                       ok, "\n".join(lines))


def case_2(find_tool: Path, db: Path) -> bool:
    code, out = run_find(find_tool, db, "COORD", "права на отправку кода")
    loud = "точных слов нет" in out
    ok = code == 0 and loud
    return case_result("② «права на отправку кода» → повтор по началу слова, код 0",
                       ok, f"код {code} · громкая строка повтора {'есть' if loud else 'НЕТ'}")


def load_counter3() -> list[dict]:
    data = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    return [q for q in data if q.get("counter3")]


def case_3(find_tool: Path, db: Path) -> bool:
    items = load_counter3()
    threshold = 3
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    found, lines = 0, []
    for q in items:
        role = str(q["role"]).upper()
        query = str(q["query"])
        expect = str(q["expect_word"]).lower()
        code, out = run_find(find_tool, db, role, query)      # БЕЗ --section (слово COORD)
        ids = record_ids(out)
        hit = False
        if code == 0 and ids:
            for rid in ids[:3]:
                row = conn.execute("SELECT body FROM phoenix_records WHERE id=?",
                                   (rid,)).fetchone()
                if row and expect in row[0].lower():
                    hit = True
                    break
        elif code == 3:
            rows = conn.execute("SELECT body FROM phoenix WHERE role=?", (role,)).fetchall()
            hit = any(expect in (b or "").lower() for (b,) in rows)
        found += int(hit)
        lines.append(f"n{q['n']} «{query}» код {code} → {'найдено' if hit else 'не найдено'} "
                    f"(ждали «{q['expect_word']}»)")
    conn.close()
    lines.append(f"порог: найдено ≥ {threshold} из {len(items)}")
    ok = found >= threshold
    return case_result(f"③ встречный случай карточки #525: найдено {found} из {len(items)}",
                       ok, "\n".join(lines))


def case_4(db: Path) -> bool | None:
    if not MEASURE_TOOL.exists():
        case_skip("④ измеритель печатает «первым N из 10» и даёт JSON через --out",
                  "измеритель не сдан (файла measure-memory-search.py нет)")
        return None
    out_dir = mezo_stand.new("bite-memory-search-measure-")
    out_path = out_dir / "measure-out.json"
    code, out = run_tool(MEASURE_TOOL,
                         ["--set", str(QUERY_SET), "--db", str(db), "--out", str(out_path)])
    loud = re.search(r"первым \d+ из \d+", out)
    json_ok = out_path.exists()
    summary_ok = False
    if json_ok:
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            summary_ok = isinstance(payload, dict) and "summary" in payload and "rows" in payload
        except (OSError, json.JSONDecodeError):
            summary_ok = False
    ok = (code == 0) and bool(loud) and json_ok and summary_ok
    return case_result("④ измеритель печатает «первым N из 10» и даёт JSON через --out",
                       ok, f"код {code} · строка итога {loud.group(0) if loud else 'НЕТ'} "
                       f"· файл --out {'создан' if json_ok else 'НЕТ'} "
                       f"· форма JSON {'верна' if summary_ok else 'НЕВЕРНА'}")


def case_a(find_tool: Path, db: Path) -> bool:
    conn = sqlite3.connect(str(db))
    picked = pick_unique_word(conn, "COORD")
    if not picked:
        conn.close()
        return case_result("а) снятая запись видна поиску с пометкой ⚰️ «снята»", False,
                           "не нашлось слова, единственного для одной записи COORD — "
                           "опыт не поставлен")
    record_id, word = picked
    revoked_note = "проба приёмки"
    conn.execute("UPDATE phoenix_records SET alive='revoked', revoked_at=datetime('now'), "
                "revoked_note=? WHERE id=?", (revoked_note, record_id))
    conn.commit()
    conn.close()
    code, out = run_find(find_tool, db, "COORD", word)
    ids = record_ids(out)
    shown = str(record_id) in ids
    marked = ("⚰️" in out) and ("снята" in out) and (revoked_note in out)
    ok = code == 0 and shown and marked
    return case_result("а) снятая запись видна поиску с пометкой ⚰️ «снята»", ok,
                       f"слово «{word}», запись #{record_id} помечена revoked "
                       f"(«{revoked_note}») · код {code} · запись в ответе={shown} "
                       f"· пометка снятия видна={marked}")


def case_b(find_tool: Path, db: Path) -> bool:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    picked = pick_archive_only_word(conn)
    conn.close()
    if not picked:
        return case_result("б) слово только в архиве → код 4 и «в архиве»", False,
                           "не нашлось слова, живущего только в архиве, — опыт не поставлен")
    role, word = picked
    code, out = run_find(find_tool, db, role, word)
    has_line = "в архиве" in out
    ok = code == 4 and has_line
    return case_result("б) слово только в архиве → код 4 и «в архиве»", ok,
                       f"роль {role}, слово «{word}» · код {code} "
                       f"· строка «в архиве» {'есть' if has_line else 'НЕТ'}")


def case_v(find_tool: Path, db: Path, env: dict | None = None) -> bool:
    conn = sqlite3.connect(str(db))
    role = pick_role_without_records(conn)
    fallback_used = False
    if not role:
        # запасной ход по слову задания: снять записи одного раздела PROTO/history
        conn.execute("DELETE FROM phoenix_records WHERE role='PROTO' AND section='history'")
        conn.commit()
        role, fallback_used = "PROTO", True
    picked = pick_body_word(conn, role)
    conn.close()
    if not picked:
        return case_result("в) раздел без записей → код 3 и «не разобран»/«отстают»", False,
                           f"для роли {role} не нашлось слова в теле раздела — опыт не поставлен")
    section, word = picked
    code, out = run_find(find_tool, db, role, word, section=section, env=env)
    named = ("не разобран" in out) or ("отстают" in out)
    ok = code == 3 and named
    return case_result("в) раздел без записей → код 3 и «не разобран»/«отстают»", ok,
                       f"роль {role}{' (запасной ход: PROTO/history очищен в копии)' if fallback_used else ''}"
                       f", раздел {section}, слово «{word}» · код {code} "
                       f"· пояснение названо={named}")


def case_v2(find_tool: Path, db: Path) -> bool:
    code, out = run_find(find_tool, db, "COORD", "xyzzyqwerty")
    ok = code == 2 and ("может быть" in out.lower())
    return case_result("в-бис) слова нет нигде → код 2 и «может быть»", ok,
                       f"код {code} · строка «может быть» "
                       f"{'есть' if 'может быть' in out.lower() else 'НЕТ'}")


def case_g(find_tool: Path, db: Path, env: dict | None = None) -> bool:
    code_a, out_a = run_find(find_tool, db, "COORD", "Права", env=env)
    code_b, out_b = run_find(find_tool, db, "COORD", "права", env=env)
    ids_a, ids_b = sorted(record_ids(out_a)), sorted(record_ids(out_b))
    word_case_equal = (code_a == 0 and code_b == 0) and ids_a == ids_b and bool(ids_a)

    code_c, out_c = run_find(find_tool, db, "COORD", "остановка смены", env=env)
    code_d, out_d = run_find(find_tool, db, "coord", "остановка смены", env=env)
    ids_c, ids_d = sorted(record_ids(out_c)), sorted(record_ids(out_d))
    role_case_equal = (code_c == 0 and code_d == 0) and ids_c == ids_d and bool(ids_c)

    ok = word_case_equal and role_case_equal
    return case_result("г) регистр слова и роли — одно множество id", ok,
                       f"«Права»→{ids_a} «права»→{ids_b}, равны={word_case_equal}\n"
                       f"--role COORD→{ids_c} --role coord→{ids_d}, равны={role_case_equal}")


def case_d(save_tool: Path, db: Path, env: dict | None = None) -> bool:
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT body FROM phoenix WHERE role='PROTO' AND section='state'").fetchone()
    conn.close()
    if not row:
        return case_result("д) хук: сохранение раздела пересобирает записи", False,
                           "у PROTO нет раздела state в копии — опыт не поставлен")
    body = row[0] + ("\n\nСтрока смены: приёмка карточки #525, случай д, "
                     "перемерена рабочим каталогом приёмки.\n")
    stand = mezo_stand.new("bite-memory-search-save-")
    file1, file2 = stand / "body1.md", stand / "body2.md"
    file1.write_text(body, encoding="utf-8")
    file2.write_text(body, encoding="utf-8")

    code1, out1 = run_tool(save_tool, ["--db", str(db), "--role", "PROTO", "--section", "state",
                                       "--file", str(file1), "--actor", "PROTO"], env=env)
    first_hook = "🧩" in out1

    code2, out2 = run_tool(MEMORY_RECORDS, ["--db", str(db), "--role", "PROTO",
                                            "--section", "state", "--собрать"])
    converges = "СОВПАДАЕТ ЗНАК В ЗНАК" in out2

    code3, out3 = run_tool(save_tool, ["--db", str(db), "--role", "PROTO", "--section", "state",
                                       "--file", str(file2), "--actor", "PROTO"], env=env)
    unchanged_note = "СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ" in out3
    second_hook = "🧩" in out3

    ok = (code1 == 0 and first_hook and code2 == 0 and converges
          and code3 == 0 and unchanged_note and not second_hook)
    return case_result("д) хук save-phoenix.py: пересборка записей после сохранения, "
                       "молчание при повторе", ok,
                       f"первое сохранение (тело изменилось): код {code1}, "
                       f"«🧩» {'есть' if first_hook else 'НЕТ'}\n"
                       f"memory-records.py --собрать: код {code2}, сходится={converges}\n"
                       f"повторное сохранение (то же тело): код {code3}, "
                       f"«содержимое не изменилось»={unchanged_note}, "
                       f"«🧩» {'напечатана — ОШИБКА' if second_hook else 'не напечатана — верно'}")


# ═══ ОТПЕЧАТОК ЖИВОЙ БАЗЫ (ДО/ПОСЛЕ, БЕЗ ЕДИНОЙ ЗАПИСИ) ═══════════════════════════

def live_db_fingerprint() -> tuple[int, int | None]:
    conn = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    records = conn.execute("SELECT COUNT(*) FROM phoenix_records").fetchone()[0]
    max_msg = conn.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    conn.close()
    return records, max_msg


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Приёмка карточки #525: поиск по памяти (find-phoenix.py) вместо "
                    "чтения раздела целиком; хук пересборки записей в save-phoenix.py")
    ap.add_argument("--break", dest="break_kind",
                    choices=["none", "case-fold", "no-level2", "no-hook"], default="none",
                    help="нарочная поломка — какой случай проверяем на красное")
    ap.add_argument("--tool-dir", default=None,
                    help="каталог с find-phoenix.py/save-phoenix.py вместо живого "
                        ".mezosync/scripts, для случаев БЕЗ поломки (ручная проверка "
                        "другой копии); на сами поломки не влияет — их копии строятся "
                        "от ЖИВОГО инструмента намеренно")
    ap.add_argument("--keep", action="store_true",
                    help="не убирать рабочие каталоги приёмки (для разбора вручную)")
    args = ap.parse_args()
    if args.keep:
        os.environ.setdefault("MEZO_KEEP_STANDS", "1")

    scripts_dir = Path(args.tool_dir) if args.tool_dir else LIVE_SCRIPTS
    find_tool_live = scripts_dir / FIND_PHOENIX_NAME
    save_tool_live = scripts_dir / SAVE_PHOENIX_NAME

    print("=" * 92)
    print("ПРИЁМКА КАРТОЧКИ #525 — поиск по памяти вместо чтения раздела целиком"
         + (f" · НАРОЧНАЯ ПОЛОМКА: {args.break_kind}" if args.break_kind != "none" else ""))
    print("живая база (только чтение, копируется): " + str(LIVE_DB))
    print("=" * 92)

    before_records, before_max_msg = live_db_fingerprint()

    stand = mezo_stand.new("bite-memory-search-")
    db = stand / "copy.db"
    shutil.copy2(LIVE_DB, db)

    find_tool_for_v, env_for_v = find_tool_live, None
    find_tool_for_g, env_for_g = find_tool_live, None
    save_tool_for_d, env_for_d = save_tool_live, None

    if args.break_kind == "case-fold":
        find_tool_for_g, env_for_g = build_broken_find_phoenix(
            "bite-memory-search-break-cf-", CASE_FOLD_ANCHOR, CASE_FOLD_REPLACEMENT)
    elif args.break_kind == "no-level2":
        find_tool_for_v, env_for_v = build_broken_find_phoenix(
            "bite-memory-search-break-nl2-", NO_LEVEL2_ANCHOR, NO_LEVEL2_REPLACEMENT)
    elif args.break_kind == "no-hook":
        save_tool_for_d, env_for_d = build_broken_save_phoenix("bite-memory-search-break-nh-")

    case_1(find_tool_live, db)
    case_2(find_tool_live, db)
    case_3(find_tool_live, db)
    case_4(db)
    case_a(find_tool_live, db)
    case_b(find_tool_live, db)
    case_v(find_tool_for_v, db, env=env_for_v)
    case_v2(find_tool_live, db)
    case_g(find_tool_for_g, db, env=env_for_g)
    case_d(save_tool_for_d, db, env=env_for_d)

    after_records, after_max_msg = live_db_fingerprint()
    # ⚖️ ДВА ЧИСЛА — И СУДЯТ ПО-РАЗНОМУ. phoenix_records — предмет ЭТОЙ приёмки: если он
    # сдвинулся, значит писала ОНА (все её случаи адресуются к копии, но отпечаток снят
    # для проверки, что ни один по ошибке не забыл --db). max(messages.id) — ЧУЖОЙ след:
    # лента живая, её пишут девять ролей одновременно, и рост номера за минуты прогона —
    # обычное дело чужой работы, а не улика против этой приёмки (проверено: #5003 живой
    # базы на этом прогоне оказалась запиской роли ING, время внутри — её, не моё).
    # Гасить прогон по чужому счётчику значило бы получать случайное красное почти
    # в каждом запуске — родня классу «проверка спрашивает не тем адресом, каким ходит
    # человек»: адрес спрашивал не тот предмет.
    records_untouched = before_records == after_records
    msg_note = "не менялся" if before_max_msg == after_max_msg else "менялся — чужая рука (лента общая)"

    print("")
    print("=" * 92)
    failed = [name for name, ok in results if not ok]
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}"
         + (f" · пропущено {len(skipped)}" if skipped else ""))
    print(f"живая база: phoenix_records {before_records}→{after_records} "
         f"({'не тронута' if records_untouched else '🔴 ИЗМЕНИЛАСЬ — предмет этой приёмки, отказ'}); "
         f"max(messages.id) {before_max_msg}→{after_max_msg} — {msg_note}, справочно, "
         f"на вердикт не влияет")
    if failed:
        print(f"🔴 красных {len(failed)} из {len(results)}: {' · '.join(failed)}")
        code = 1
    else:
        print(f"✅ принято {len(results)} из {len(results)}")
        code = 0
    if not records_untouched:
        code = 1
    print("=" * 92)

    mezo_stand.release(stand)
    return code


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
