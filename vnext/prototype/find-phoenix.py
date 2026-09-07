# -*- coding: utf-8 -*-
r"""find-phoenix.py — ПОИСК ПО ЗАПИСЯМ ПАМЯТИ РОЛИ СЛОВАМИ, а не чтением раздела целиком
(карточка #525, часть А, пункт 3 плана).

ПРЕДМЕТ. read-phoenix.py показывает раздел памяти ЦЕЛИКОМ — 5 000…20 000 знаков за один
раздел. Роли (и владельцу), которым нужно «что уже известно про права доступа», приходится
читать всё подряд, чтобы найти абзац. У phoenix_records (шаг 20260904-phoenix-records) уже
есть память ЗАПИСЯМИ, а у phoenix_records_fts (шаг 20260907-phoenix-records-fts) — индекс
полнотекстового поиска по ним. Этот инструмент — тонкий слой НАД индексом: слова → записи.

ТРИ УРОВНЯ, В ПОРЯДКЕ ПОПЫТКИ:
  1. ЗАПИСИ (phoenix_records через FTS-индекс) — точный поиск по словам; не нашлось —
     повтор по НАЧАЛУ слова (без стеммера точных совпадений мало, а начало слова ловит
     падежные формы не хуже, и об этом сказано вслух отдельной строкой).
  2. ТЕЛО РАЗДЕЛА — только когда уровень 1 пуст. Слово может быть в тексте, а записи
     памяти — либо ещё не разобраны на этот раздел, либо разобраны из СТАРОГО текста
     (раздел правили, записи не пересобирали). Отличить это от «слова вообще нет» важно:
     иначе роль решит, что искомого не было, хотя оно есть — просто не в индексе.
  3. АРХИВ (phoenix_archive, через найти() из memory-archive.py) — то, что унесено из
     горячей памяти, но не удалено.

ЧЕТЫРЕ ИСХОДА, И КАЖДЫЙ — СВОИМИ СЛОВАМИ (не «ничего не найдено» на все случаи разом —
см. правило «одно „ничего“ на две разные беды заставляет спрашивающего гадать»):
  · найдено в записях — список, код 0;
  · нет нигде — код 2, с ближайшими по написанию словами из памяти роли (не гипотеза,
    а честное «может, вот это»);
  · есть в тексте раздела, но не в записях — код 3, с точной командой пересборки;
  · есть только в архиве — код 4, с числом кусков и первой строкой темы.

ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
  · РУССКОГО СТЕММЕРА ЗДЕСЬ НЕТ. «Права», «правами», «праву» — разные токены для индекса;
    отказ уровня 1 лечится ПРЕФИКСОМ («прав*»), а не разбором словоформ, и это накрывает
    падежи только СЛУЧАЙНО, общим началом слова. Слово, о котором писали ИНАЧЕ (не тем
    корнем — «мандат» вместо «право»), этот инструмент не найдёт вообще: он ищет буквы,
    а не смысл;
  · индекс покрывает `subject` и `body` записи — не тело всего раздела напрямую (для
    этого уровень 2 читает `phoenix.body` отдельным путём, а не через индекс);
  · подсказка о том, что «раздел отстаёт», следует из `origin_chars` записей против
    текущей длины `phoenix.body` — это ФАКТ рассинхронизации, а не догадка.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/find-phoenix.py --role COORD "остановка смены"
    python <КОНТУР>/.mezosync/scripts/find-phoenix.py --role COORD "права" --section identity
    python <КОНТУР>/.mezosync/scripts/find-phoenix.py --role COORD "остановка смены" --phrase
    python <КОНТУР>/.mezosync/scripts/find-phoenix.py --role COORD "слово" --revoked --full-body
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import importlib.util
import io
import math
import re
import sqlite3
import sys
import time
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
import mezo_paths
import mezo_hints                   # #586: общая подсказка печатается роли один раз

HERE = Path(__file__).resolve().parent
# ⚖️ КОРЕНЬ КОНТЕЙНЕРА — ВЫЧИСЛЕН, А НЕ ВПИСАН ЛИТЕРАЛОМ МАШИНЫ. Тот же приём и та
# же причина, что в save-phoenix.py::volume_limit() (карточка #525, слово COORD
# 2026-09-07 UTC, находка при переносе в образец): литерал «<КОНТУР>/…» верен
# на ЭТОЙ машине, но копия инструмента (guard-scripts-drift.py --to-template, другой
# клон контейнера) поедет на другой диск/корень — и литерал начнёт печатать
# несуществующий путь молча правильным на вид текстом. mezo_paths.container_root
# сама ищет корень от расположения ЭТОГО файла (плюс переменная среды / local.paths
# как запасные пути) — ей и считается ОДИН РАЗ здесь, дальше переиспользуется.
CONTAINER_ROOT = mezo_paths.container_root(__file__)

# ── РУССКИЕ НАЗВАНИЯ РАЗДЕЛОВ — ВЫВЕДЕНЫ ИЗ read-phoenix.py, НЕ ПЕРЕПИСАНЫ ЗАНОВО ──
# Тот же приём, каким memory-records.py берёт разбор на блоки у memory-archive.py:
# два места с одним и тем же именованием разъехались бы молча при первой же правке
# заголовков там. read-phoenix.py лежит рядом (тот же каталог), main() у него под
# `if __name__ == "__main__"`, так что импорт только ЗАВОДИТ имена и ничего не печатает.
_read_phoenix_spec = importlib.util.spec_from_file_location(
    "_find_phoenix_read_phoenix", HERE / "read-phoenix.py")
_read_phoenix = importlib.util.module_from_spec(_read_phoenix_spec)
_read_phoenix_spec.loader.exec_module(_read_phoenix)
SECTION_ORDER = _read_phoenix.ORDER


def _section_label(section: str) -> str:
    """Из «§1 ИДЕНТИЧНОСТЬ И ГРАНИЦЫ — кто ты и чего тебе НЕЛЬЗЯ» — «ИДЕНТИЧНОСТЬ И
    ГРАНИЦЫ»: убрать номер параграфа и пояснение после тире, оставить то, чем сам
    read-phoenix.py называет раздел человеку."""
    head = _read_phoenix.TITLES[section].split(" — ", 1)[0]
    parts = head.split(" ", 1)
    return parts[1] if len(parts) > 1 else head


SECTION_LABELS = {s: _section_label(s) for s in SECTION_ORDER}

# ── АРХИВ ПАМЯТИ — найти() ИЗ memory-archive.py, ТЕМ ЖЕ ПРИЁМОМ, ЧТО У memory-records.py ──
# memory-archive.py лежит в другом каталоге контейнера (vnext-tools), поэтому путь строится
# от CONTAINER_ROOT, а не как HERE / "имя" — путь ищется от РАСПОЛОЖЕНИЯ ЭТОГО ФАЙЛА
# на диске, а не от --db, и переживёт запуск инструмента из копии-песочницы.
_memory_archive_path = CONTAINER_ROOT / "vnext-tools" / "memory-archive.py"
_memory_archive_spec = importlib.util.spec_from_file_location(
    "_find_phoenix_memory_archive", _memory_archive_path)
_memory_archive = importlib.util.module_from_spec(_memory_archive_spec)
_memory_archive_spec.loader.exec_module(_memory_archive)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text)


def _stem(token: str) -> str:
    """Начало слова для повтора по префиксу (план предусматривал его именно так:
    «при нуле — автоматический повтор с началом слова»). ЧИСЛА и токены короче
    5 знаков возвращаются БЕЗ ИЗМЕНЕНИЙ: усечение короткого/числового токена только
    расширило бы ложные совпадения — тот же класс, что «20» внутри чужой «2026»,
    уже пойманный и вылеченный на уровне 2 (см. _level2_exact); здесь та же
    осторожность на уровне 1. Для токенов от 5 знаков — первые max(4, длина−2)
    знаков: «отправку»(8)→«отправ»(6), «права»(5)→«прав»(4), «запрещён»(8)→«запрещ»(6)."""
    if token.isdigit() or len(token) < 5:
        return token
    return token[:max(4, len(token) - 2)]


def _match_query(tokens: list[str]) -> str:
    """FTS5-запрос ТОЧНЫМИ токенами. КАЖДЫЙ токен — в двойных кавычках: «#» и
    служебные слова FTS5 (AND/OR/NOT/NEAR) внутри кавычек не ломают синтаксис MATCH."""
    return " ".join(f'"{t}"' for t in tokens)


def _fts_term(token: str, stem: str) -> str:
    """Один член FTS5-запроса: ПРЕФИКС («"отправ"*»), если стемминг реально укоротил
    слово, иначе ТОЧНЫЙ токен — та же осторожность, что и на уровне 2 (короткие/
    числовые токены префиксом не пускаем, они и так самого себя короче не станут)."""
    return f'"{stem}"*' if stem != token else f'"{token}"'


def _match_query_stemmed(tokens: list[str], stems: list[str]) -> str:
    """Ступень B уровня 1 — токены СМЕЖНЫ через AND (implicit), каждый — своим
    членом _fts_term. Нужна ВСЯ строка целиком в одной записи, просто с прощением
    окончаний у длинных слов."""
    return " ".join(_fts_term(t, s) for t, s in zip(tokens, stems))


def _match_query_or(tokens: list[str], stems: list[str]) -> str | None:
    """Ступень C уровня 1 — токены ЧЕРЕЗ OR: запись не обязана нести ВСЕ слова
    запроса, только хотя бы одно (дальше _partial_matches отбирает и ранжирует по
    тому, СКОЛЬКО их совпало, и отдельно требует ВСЕ числовые — см. её докстринг).
    Токены короче 4 знаков в OR-запрос НЕ идут — КРОМЕ ЧИСЕЛ: короткое СЛОВО через
    OR подобрало бы кандидатами едва ли не все записи раздела (тот же класс ложной
    широты, что уже лечился на уровне 2, только через OR он бьёт сильнее AND), а
    короткое ЧИСЛО — самый точный признак изо всех (решение координатора, карточка
    #525, доработка после находки про «карточка #462»): исключать его значило бы
    прятать от OR-кандидатов ИМЕННО те записи, ради которых числа и нужны. Слова
    короче 4 знаков не теряются вовсе — их совпадение всё равно считает
    _partial_matches по самому телу записи, просто не через SQL-кандидатов.
    None — вернуть нечего (все токены короче 4 знаков и ни одного числа)."""
    parts = [_fts_term(t, s) for t, s in zip(tokens, stems) if len(t) >= 4 or t.isdigit()]
    return " OR ".join(parts) if parts else None


def _match_query_phrase(tokens: list[str]) -> str:
    return '"' + " ".join(tokens) + '"'


def _match_query_phrase_prefix(tokens: list[str], stems: list[str]) -> str:
    """ФРАЗА с префиксом на ПОСЛЕДНЕМ слове: синтаксис FTS5 `"фраза"*` делает
    префиксным ровно последний токен внутри кавычек, остальные остаются точными
    и смежными. Это единственный вид префикса, который FTS5 разрешает ВНУТРИ
    фразового запроса — префикса у слова в СЕРЕДИНЕ фразы синтаксис не даёт вовсе,
    поэтому выбор здесь не вкус, а то, что вообще есть у движка (см. докстринг
    модуля и отчёт: другой вариант, «фразовый поиск без повтора», обсуждён и отвергнут)."""
    parts = list(tokens[:-1]) + [stems[-1]]
    return '"' + " ".join(parts) + '"*'


def _fetch_records(conn, role, match_query, section, revoked_only, limit):
    where_clauses = ["phoenix_records_fts MATCH ?", "pr.role = ?"]
    params: list = [match_query, role]
    if section:
        where_clauses.append("pr.section = ?")
        params.append(section)
    if revoked_only:
        where_clauses.append("pr.alive = 'revoked'")
    params.append(limit)
    sql = (
        "SELECT pr.id, pr.section, pr.subject, pr.happened_at, pr.alive, pr.revoked_at, "
        "pr.revoked_note, pr.source, pr.body, "
        "snippet(phoenix_records_fts, 1, '[', ']', '…', 24) "
        "FROM phoenix_records_fts JOIN phoenix_records pr "
        "  ON pr.id = phoenix_records_fts.rowid "
        f"WHERE {' AND '.join(where_clauses)} ORDER BY rank LIMIT ?"
    )
    return conn.execute(sql, params).fetchall()


def _fetch_records_or(conn, role, or_query, section, revoked_only, cap):
    """Кандидаты ступени C: любая запись, несущая ХОТЯ БЫ ОДИН OR-член. Тянем
    `phoenix_records_fts.rank` отдельным столбцом — он нужен как ВТОРОЙ ключ
    сортировки в Python (первый — число совпавших токенов запроса, его SQL не
    считает, это не то же самое, что «сколько OR-членов сработало»)."""
    where_clauses = ["phoenix_records_fts MATCH ?", "pr.role = ?"]
    params: list = [or_query, role]
    if section:
        where_clauses.append("pr.section = ?")
        params.append(section)
    if revoked_only:
        where_clauses.append("pr.alive = 'revoked'")
    params.append(cap)
    sql = (
        "SELECT pr.id, pr.section, pr.subject, pr.happened_at, pr.alive, pr.revoked_at, "
        "pr.revoked_note, pr.source, pr.body, "
        "snippet(phoenix_records_fts, 1, '[', ']', '…', 24), "
        "phoenix_records_fts.rank "
        "FROM phoenix_records_fts JOIN phoenix_records pr "
        "  ON pr.id = phoenix_records_fts.rowid "
        f"WHERE {' AND '.join(where_clauses)} ORDER BY rank LIMIT ?"
    )
    return conn.execute(sql, params).fetchall()


def _partial_matches(candidates, tokens, stems, limit):
    """Из кандидатов ступени C — отобрать и отранжировать по числу совпавших
    токенов ЗАПРОСА (не только OR-членов: короткие токены здесь тоже считаются,
    сравнением по началу слова против СВОЕГО набора токенов тела записи — тот же
    приём, что у _level2_stemmed, только по телу ОДНОЙ записи, а не раздела).

    ⛔ ЧИСЛОВЫЕ ТОКЕНЫ ЗАПРОСА — ОБЯЗАТЕЛЬНЫ, А НЕ ПРОСТО ЗАСЧИТЫВАЮТСЯ (решение
    координатора после находки на «карточка #462», карточка #525): запись, в
    которой нет хотя бы ОДНОГО числа из запроса, ступень C не показывает ВООБЩЕ —
    даже если по словам она набрала порог. Число — самый точный признак («карточка»
    — общее слово почти у всех записей раздела, «462» — нет), и терять его ради
    более длинного списка значило бы прятать именно ту запись, ради которой число
    искали. Это отдельный отбор ДО порога, а не часть счёта K.

    Порядок: сначала БОЛЬШЕ совпавших токенов, при равенстве — лучший bm25 (числа
    FTS5: чем МЕНЬШЕ rank, тем лучше совпадение, ORDER BY rank без DESC — то же
    правило, что и у обычного `rank`-сорта в остальном инструменте).

    Порог показа — `max(2, ceil(N/2))`: запись должна нести хотя бы половину слов
    запроса (не меньше двух), иначе список превратится в «что угодно, где
    встретилось одно слово». Возвращает (строки БЕЗ хвостового rank, готовые для
    _print_record, список пар (K, N) с тем же порядком — подпись «слов K из N»
    на печати)."""
    numeric_tokens = {t.lower() for t in tokens if t.isdigit()}
    threshold = max(2, math.ceil(len(tokens) / 2))
    scored = []
    for row in candidates:
        *fields, rank_value = row
        body = fields[8]
        body_tokens = {t.lower() for t in _tokenize(body)}
        if numeric_tokens and not numeric_tokens <= body_tokens:
            continue                     # числа запроса не все на месте — не показываем
        matched = sum(
            1 for t, s in zip(tokens, stems)
            if (t.lower() in body_tokens if s == t
               else any(bt.startswith(s.lower()) for bt in body_tokens))
        )
        if matched >= threshold:
            scored.append((matched, rank_value, tuple(fields)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    scored = scored[:limit]
    rows = [item[2] for item in scored]
    counts = [item[0] for item in scored]
    return rows, counts


def _section_is_stale(conn, role, section):
    """Записи раздела ОТСТАЮТ, когда ни у одной из них origin_chars не равен текущей
    длине phoenix.body — то есть они разобраны из текста, которого уже нет."""
    row = conn.execute("SELECT LENGTH(body) FROM phoenix WHERE role=? AND section=?",
                       (role, section)).fetchone()
    if not row:
        return False, None
    current_len = row[0]
    origins = {r[0] for r in conn.execute(
        "SELECT DISTINCT origin_chars FROM phoenix_records WHERE role=? AND section=?",
        (role, section))}
    return origins != {current_len}, current_len


def _rebuild_command(conn, role, section) -> str:
    count = conn.execute("SELECT COUNT(*) FROM phoenix_records WHERE role=? AND section=?",
                         (role, section)).fetchone()[0]
    flag = "--разобрать" if count == 0 else "--пересобрать"
    memory_records = (CONTAINER_ROOT / "vnext-tools" / "memory-records.py").as_posix()
    return f"python {memory_records} --role {role} --section {section} {flag}"


def _print_record(row, *, full_body: bool, match_note: str | None = None):
    (record_id, section, subject, happened_at, alive, revoked_at, revoked_note,
     source, body, snippet) = row
    header = f"#{record_id} · {SECTION_LABELS.get(section, section)} · {happened_at or '—'} · {subject}"
    if match_note:
        header += f" · {match_note}"
    if alive == "revoked":
        header += f" ⚰️ снята {revoked_at}: {revoked_note}"
    print(header)
    print(f"   {body if full_body else snippet}")
    if source:
        print(f"   источник: {source}")


def _nearest_words(conn, role, tokens) -> list[str]:
    """Словарь роли — токены длиной от 4 знаков из тел ВСЕХ её разделов (не отдельная
    таблица: соединение только для чтения, а словарь нужен ровно этому одному ответу)."""
    vocabulary: set[str] = set()
    for (body,) in conn.execute("SELECT body FROM phoenix WHERE role=?", (role,)):
        vocabulary |= {t for t in _tokenize(body) if len(t) >= 4}
    nearest: list[str] = []
    for token in tokens:
        for match in difflib.get_close_matches(token, vocabulary, n=3, cutoff=0.6):
            if match not in nearest:
                nearest.append(match)
    return nearest[:3]


def _level2_exact(conn, role, tokens, phrase) -> list[tuple[str, int]]:
    """Первый проход уровня 2: слово(а) буквально, целыми токенами раздела."""
    matched = []
    for section, body in conn.execute("SELECT section, body FROM phoenix WHERE role=?", (role,)):
        if phrase:
            # Фраза — это буквально соседство слов, поэтому здесь честна именно
            # проверка вхождения подстроки.
            hit = " ".join(tokens).lower() in body.lower()
        else:
            # ⚠️ Целыми словами, а не подстрокой. Простое «t in body.lower()» пустило
            # бы короткий/числовой токен вроде «20» внутрь чужой «2026» в любой дате,
            # или «000» — внутрь любого другого трёхнулевого числа: почти любой раздел
            # стал бы ложным совпадением. Сверка по СВОЕМУ набору токенов раздела
            # держит этот уровень таким же точным, как точный поиск уровня 1, — просто
            # без индекса.
            body_tokens = {t.lower() for t in _tokenize(body)}
            hit = all(t.lower() in body_tokens for t in tokens)
        if hit:
            matched.append((section, len(body)))
    return matched


def _level2_stemmed(conn, role, tokens, stems, phrase) -> list[tuple[str, int]]:
    """Второй проход уровня 2 — ПО НАЧАЛУ СЛОВ, чтобы код 3 не терялся там, где
    раздел держит другую словоформу того же слова. Числа и короткие токены (стем
    равен самому токену) по-прежнему сверяются ТОЧНО, а не startswith по всему
    словарю раздела: иначе «на» стало бы префиксом половины текста и вернуло бы
    именно тот класс ложных срабатываний, что уже вылечен в _level2_exact —
    только с другой стороны (не число внутри числа, а короткое слово внутри
    произвольных длинных)."""
    matched = []
    for section, body in conn.execute("SELECT section, body FROM phoenix WHERE role=?", (role,)):
        if phrase:
            pattern = (r"\b" + r"\s+".join(re.escape(t) for t in tokens[:-1] + [stems[-1]])
                      + r"\w*")
            hit = re.search(pattern, body, re.IGNORECASE) is not None
        else:
            body_tokens = {t.lower() for t in _tokenize(body)}

            def _covers(token: str, stem: str) -> bool:
                if stem == token:
                    return token.lower() in body_tokens
                return any(bt.startswith(stem.lower()) for bt in body_tokens)

            hit = all(_covers(t, s) for t, s in zip(tokens, stems))
        if hit:
            matched.append((section, len(body)))
    return matched


def _search(conn, role, args, tokens) -> tuple[int, int]:
    """Возвращает (код исхода, N найденных ЗАПИСЕЙ — 0 при исходах 2/3/4)."""
    header = f"ПОИСК ПО ПАМЯТИ {role}: «{args.query}»"
    if args.section:
        header += f" · раздел {SECTION_LABELS.get(args.section, args.section)}"
    if args.revoked:
        header += " · только снятые"
    if args.phrase:
        header += " · фразой"
    print("=" * 84)
    print(header)
    print("=" * 84)

    stems = [_stem(t) for t in tokens]
    # Стемминг СМЕНИЛ хотя бы один токен? Если нет (все токены короче 5 знаков
    # или числа), повтор дал бы тот же нулевой ответ, что и точный запрос —
    # его не зовём и не печатаем громкую строку впустую.
    stemming_helps = ((stems[-1] != tokens[-1]) if args.phrase
                      else any(s != t for s, t in zip(stems, tokens)))

    # ── УРОВЕНЬ 1, ступень A: ЗАПИСИ, точный AND ────────────────────────────────
    match_query = _match_query_phrase(tokens) if args.phrase else _match_query(tokens)
    rows = _fetch_records(conn, role, match_query, args.section, args.revoked, args.limit)
    match_notes: list[str | None] = [None] * len(rows)

    # ── УРОВЕНЬ 1, ступень B: ЗАПИСИ, тот же AND, но префиксом ──────────────────
    if not rows and stemming_helps:
        # ⚖️ ГРОМКАЯ СТРОКА, А НЕ ТИХАЯ ПОДМЕНА: точных слов нет — это ДРУГОЙ факт,
        # чем «слово точно есть», и роль обязана видеть разницу, а не догадываться
        # о ней по одинаковому на вид списку записей.
        if args.phrase:
            shown = " ".join(tokens[:-1] + [f"{stems[-1]}*"])
            print(f"⚠️ точной фразы нет — ищу с началом последнего слова: «{shown}»")
            rows = _fetch_records(conn, role, _match_query_phrase_prefix(tokens, stems),
                                  args.section, args.revoked, args.limit)
        else:
            shown = " ".join(f"{s}*" if s != t else t for t, s in zip(tokens, stems))
            print(f"⚠️ точных слов нет — ищу по началу слов: {shown}")
            rows = _fetch_records(conn, role, _match_query_stemmed(tokens, stems),
                                  args.section, args.revoked, args.limit)
        match_notes = [None] * len(rows)

    # ── УРОВЕНЬ 1, ступень C: ЗАПИСИ, OR по префиксам + порог совпадений ────────
    # ⚖️ ТОЛЬКО НЕ-ФРАЗОВЫЙ РЕЖИМ: «фраза» по смыслу требует смежности слов, а OR
    # по отдельным токенам эту смежность сразу стирает — ступень C для --phrase
    # не имеет смысла, режим фразы остаётся на ступенях A/B.
    # ⛔ ТОЛЬКО ПРИ N ≥ 3 (решение координатора после находки на «карточка #462»,
    # карточка #525): при двух токенах порог показа max(2, ceil(2/2))=2 требует
    # ОБА — то есть ступень C выродилась бы в тот же AND, что уже провалился на
    # ступенях A/B, но БЕЗ порога уровня записи как предмета (архив за ней не
    # видно). Проще и честнее: при N ≤ 2 ступени C нет вовсе, короткий запрос идёт
    # на уровень 2/3, как раньше, и «карточка #462» снова дойдёт до архива.
    if not rows and not args.phrase and len(tokens) >= 3:
        or_query = _match_query_or(tokens, stems)
        if or_query:
            cap = max(args.limit * 5, 50)
            candidates = _fetch_records_or(conn, role, or_query, args.section,
                                           args.revoked, cap)
            partial_rows, counts = _partial_matches(candidates, tokens, stems, args.limit)
            if partial_rows:
                print("⚠️ все слова вместе не встречаются — показываю записи с частью слов")
                rows = partial_rows
                match_notes = [f"слов {k} из {len(tokens)}" for k in counts]

    if rows:
        for row, note in zip(rows, match_notes):
            _print_record(row, full_body=args.full_body, match_note=note)
        for section in sorted({row[1] for row in rows}):
            stale, current_len = _section_is_stale(conn, role, section)
            if stale:
                print(f"⚠️ записи раздела {section} отстают от текста (сейчас "
                      f"{current_len} знаков) — пересобери: "
                      f"{_rebuild_command(conn, role, section)}")
        return 0, len(rows)

    # ── УРОВЕНЬ 2: ТЕЛО РАЗДЕЛА (только когда уровень 1 пуст целиком) ───────────
    matched_sections = _level2_exact(conn, role, tokens, args.phrase)
    if not matched_sections and stemming_helps:
        matched_sections = _level2_stemmed(conn, role, tokens, stems, args.phrase)

    if matched_sections:
        # ⚖️ КОД 3 ТЕПЕРЬ ДВУХ РОДОВ, И ТЕКСТ ГОВОРИТ КОТОРЫЙ (карточка #525,
        # доработка): слово есть в тексте раздела, а записи об этом молчат —
        # но ПОЧЕМУ молчат, разное. Если записей нет вовсе или они отстают
        # (это ЖЕ и есть смысл _section_is_stale — пустой набор origin_chars
        # тоже не равен текущей длине тела) — раздел ещё не разобран инструментом,
        # и есть точная команда почини́ть это. Если записи свежие, а половины слов
        # запроса не несёт НИ ОДНА (ступень C уже это проверила и не нашла) —
        # чинить нечего: слова просто рассеяны по разным записям, и это не
        # отставание, а свойство самого запроса — сузить его или читать раздел глазами.
        for section, char_count in matched_sections:
            label = SECTION_LABELS.get(section, section)
            stale, _ = _section_is_stale(conn, role, section)
            if stale:
                print(f"🟡 в тексте раздела {label} слово есть ({char_count} знаков), "
                      f"но раздел на записи не разобран / записи отстают — "
                      f"пересобери: {_rebuild_command(conn, role, section)}")
            else:
                read_phoenix = (HERE / "read-phoenix.py").as_posix()
                print(f"🟡 записи раздела {label} свежие, слово есть в тексте, но ни "
                      f"одна запись не несёт и половины слов запроса — сузь запрос "
                      f"или читай раздел: python {read_phoenix} "
                      f"--role {role} --section {section}")
        return 3, 0

    # ── УРОВЕНЬ 3: АРХИВ (когда 1 и 2 пусты) ──────────────────────────────────
    archive_buf = io.StringIO()
    with contextlib.redirect_stdout(archive_buf):
        _memory_archive.найти(conn, role, args.query)
    archive_text = archive_buf.getvalue()
    chunks_match = re.search(r"найдено кусков (\d+)", archive_text)
    chunks_found = int(chunks_match.group(1)) if chunks_match else 0
    if chunks_found:
        print(archive_text, end="" if archive_text.endswith("\n") else "\n")
        topic_match = re.search(r"ТЕМА: (.+)", archive_text)
        first_line = topic_match.group(1).strip() if topic_match else "(тема не разобрана)"
        print(f"⚪ в живой памяти нет, в архиве есть: {chunks_found} кусков, "
              f"первые строки: «{first_line[:120]}»")
        return 4, 0

    # ── ИСХОД 2: нет нигде ────────────────────────────────────────────────────
    nearest = _nearest_words(conn, role, tokens)
    nearest_text = ", ".join(nearest) if nearest else "(похожих слов в памяти роли не нашлось)"
    print(f"⚪ нет ни в одном разделе, ни в архиве. Может быть: {nearest_text}")
    return 2, 0


HINT_TEXT = (
    "🔎 find-phoenix ищет по ЗАПИСЯМ слоя памяти (phoenix_records), а не по всему телу "
    "раздела: быстрее полного чтения, но записи пересобираются только КАЖДЫМ сохранением "
    "памяти — если результат старше текста, инструмент сам скажет об этом строкой. Точных "
    "слов нет — ищет по началу слова (без разбора русских падежей: «права», записанные "
    "другими словами, найдены не будут). Три уровня: записи → тело раздела → архив. Полное "
    "чтение памяти целиком — read-phoenix.py."
)


def main() -> int:
    start_time = time.perf_counter()

    ap = argparse.ArgumentParser(
        description="Поиск по сохранённой памяти роли словами — без чтения раздела "
                    "целиком (карточка #525, часть А, пункт 3)")
    ap.add_argument("--role", required=True, help="чья память (ВЕРХНИМ регистром)")
    ap.add_argument("query", help="слова запроса (одна строка, можно несколько слов)")
    ap.add_argument("--section", choices=SECTION_ORDER, help="сузить до одного раздела")
    ap.add_argument("--limit", type=int, default=20,
                    help="сколько записей показать (по умолчанию 20)")
    ap.add_argument("--full-body", dest="full_body", action="store_true",
                    help="печатать тело записи целиком, а не кусок текста вокруг слова")
    ap.add_argument("--revoked", dest="revoked", action="store_true",
                    help="искать только среди снятых (alive='revoked') записей")
    ap.add_argument("--phrase", dest="phrase", action="store_true",
                    help="искать слова ОДНОЙ фразой подряд, а не по отдельности")
    ap.add_argument("--actor", help="кто читает (роль руки); без него показ подсказки "
                    "засчитывается роли из --role")
    ap.add_argument("--full", action="store_true",
                    help="печатать общую подсказку полностью, даже если уже показывалась")
    ap.add_argument("--db", default=None,
                    help="путь к mezosync.db (по умолчанию — рядом со скриптом)")
    args = ap.parse_args()

    role = args.role.upper()
    tokens = _tokenize(args.query)
    if not tokens:
        sys.exit("⛔ запрос не содержит ни одного слова для поиска")

    try:
        db = Path(resolve_db(args.db, __file__, readonly=True))
    except SystemExit as e:
        sys.exit(f"⛔ ПОИСК НЕ ВЫПОЛНЕН: {e}")
    # ⚖️ Соединение ТОЛЬКО ДЛЯ ЧТЕНИЯ — инструмент ничего в память не пишет.
    # Подсказка ниже пишет отметку показа СВОИМ отдельным соединением (db_path),
    # как и role-brief.py; на это соединение это правило не распространяется.
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "phoenix_records_fts" not in tables:
        fts_step = (HERE / "migrations" / "20260907-phoenix-records-fts.py").as_posix()
        print("⛔ В этой базе нет полнотекстового индекса записей памяти (таблицы "
              f"phoenix_records_fts). Накати шаг схемы:\n   python {fts_step}",
              file=sys.stderr)
        return 5

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code, n_found = _search(conn, role, args, tokens)
        # mezo_hints — общий помощник контура; его публичные функции носят свои
        # существующие (русские) имена — подсказка()/кто_читает() — звать их иначе
        # значило бы переименовывать чужой общий инструмент, а не писать свой.
        mezo_hints.подсказка(conn, mezo_hints.кто_читает(args.actor, role),
                             "find-phoenix-canon", HINT_TEXT, ttl_hours=24,
                             full=args.full, db_path=db.as_posix())
    text = buf.getvalue()
    sys.stdout.write(text)
    elapsed = time.perf_counter() - start_time
    print(f"ОТВЕТ: {n_found} записей · {len(text)} знаков · {elapsed:.3f} с")
    return code


if __name__ == "__main__":
    sys.exit(main())
