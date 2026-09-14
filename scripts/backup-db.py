r"""
backup-db.py — восстановимость mezosync.db через git.

ПРОБЛЕМА (найдена 16.07): <КОНТУР>\.mezosync\mezosync.db лежит ВНЕ любого
git-репозитория — контейнер .atlas это не репо, а папка с независимыми репо внутри.
При этом sync.*.md версионируются в atlas.archs. То есть на 16.07 md были ЕДИНСТВЕННОЙ
восстановимой копией истории координации, а БД — одним файлом на одной машине.
Отключить md, не закрыв это, значило бы масштабировать беду STUD (4 дня без фолбэка)
на весь контур.

РЕШЕНИЕ: `.dump` базы в ТЕКСТОВЫЙ .sql внутрь atlas.archs (репо) + коммит.
Почему дамп, а не копия .db:
  · git версионирует текст дельтами; бинарь пришлось бы хранить целиком каждый тик
  · дамп человекочитаем и diff-абелен — видно, ЧТО изменилось между тиками
  · восстановление точное: sqlite3 new.db < dump.sql
  · бинарная копия .db в git дала бы конфликты, которые нечем разрешать

КУДА (решение владельца 16.07 13:25, принёс EYE #1989): выделенный репозиторий
<КОНТУР>\atlas.agents-sync.db — ЭТО КАТАЛОГ-РЕПО, а не файл (суффикс .db в
имени обманчив, не перепутать с mezosync.db). У него есть УДАЛЁНКА на корпоративный
GitLab — единственное во всём контуре, что переживает потерю машины.

ПОЧЕМУ ТЕКСТОВЫЙ ДАМП, А НЕ БИНАРНАЯ КОПИЯ .db ЧЕРЕЗ git-lfs (lfs 3.7.1 в системе есть):
  · git версионирует текст дельтами; бинарь лёг бы целиком на каждой ноте
  · ДАМП ДИФФ-АБЕЛЕН — и это не эстетика. 16.07 TAXO доказала инцидент с хронологией
    ИМЕННО сравнением двух срезов БД (#1952): бэкап работал как ИНСТРУМЕНТ
    РАССЛЕДОВАНИЯ, а не только как страховка. Бинарь такого не даёт.
  · восстановление точное и проверяется здесь же — теперь ВСЕГДА, см. ниже
  · lfs добавил бы зависимость там, где она не нужна

🩸 КАРТОЧКА #610 (2026-09-14). Таблица полнотекстового поиска phoenix_records_fts
(FTS5, внешнее содержимое) сломала прежнюю выгрузку: iterdump на Python 3.14.6 пишет
её через PRAGMA writable_schema + INSERT INTO sqlite_master, следующая же строка
INSERT INTO "phoenix_records_fts" падает — таблицы ещё нет. Не полагаемся на то, КАК
именно iterdump обходится с виртуальными таблицами (это меняется от версии Python):
их строки и строки их служебных таблиц исключаются из потока ПО СПИСКУ ИМЁН
(взятому из sqlite_master), а перед завершающим COMMIT дописывается настоящий
CREATE VIRTUAL TABLE из sqlite_master и команда перестройки индекса. Заодно
починен порядок: раньше файл выгрузки перезаписывался ДО проверки разворотом,
а исход проверки было не увидеть — печаталась только уборка временной базы.
Теперь: пишем во временный файл рядом с целью → разворачиваем ИЗ НЕГО в проверочную
базу → только при успехе меняем местами с целью; проверка происходит ВСЕГДА
(--apply и без него), временной базы после любого исхода не остаётся.

ВОССТАНОВЛЕНИЕ:
    sqlite3 mezosync-restored.db < atlas.agents-sync.db/mezosync.dump.sql

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/backup-db.py            # dry-run: покажет размер/дельту
    python <КОНТУР>/.mezosync/scripts/backup-db.py --apply
    (--verify принимается для прежних вызовов и ничего не меняет: разворот проверяется
     всегда, с этим флагом и без него)
"""

import argparse
import os
import random
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD

# 🪤 ЗДЕСЬ СТОЯЛ ПУТЬ В НАШ РЕПОЗИТОРИЙ-ЗЕРКАЛО. Найдено пробной сборкой нового проекта
# 18.08: свежий контур клал бы свой дамп В ЧУЖОЙ репозиторий — и владелец нового проекта
# увидел бы это не скоро. Путь выводится от своего контейнера; прежний остаётся запасным
# для нашего контура, где такой репозиторий действительно есть.
_own = Path(__file__).resolve().parent.parent.parent
_mirror = _own / "atlas.agents-sync.db"
OUT = (_mirror / "mezosync.dump.sql" if _mirror.is_dir()
       else _own / ".mezosync" / "backups" / "mezosync.dump.sql")

# ⚰️ Здесь стояла посылка «данные append-only ⇒ дамп уменьшаться не должен». Она умерла
# 24.08 с защитой сохранённой памяти: чистка истории версий ШТАТНО УДАЛЯЕТ строки
# (карточка #250). Убыль теперь бывает законной — но только та, чей механизм НАЗВАН.
# Замер по коду контура 26.08 (grep «DELETE FROM» по живым инструментам, не приёмкам):
#   save-phoenix.py ........ phoenix_history — чистка версий (держим 10 + самую длинную)
#   read-messages.py ....... read_batches — батч подтверждения гаснет после ack
#   split-history-table.py . messages → messages_history — переезд (сумма сохраняется)
# Любая ДРУГАЯ убыль строк — тревога, даже если дамп в байтах ВЫРОС: рост соседних
# таблиц маскирует потерю, и байтовый замер её не видел вовсе.
# ⚠️ Служебные таблицы поиска (см. SHADOW_SUFFIXES ниже) в эту сверку не попадают
# ВООБЩЕ — их не включают в счётчики строк с самого начала (карточка #610, случай С7):
# их число строк меняется законно при каждой перестройке и слиянии индекса, а сам
# поиск сверяется отдельно, выдачей (см. check_search_table).
LEGAL_SHRINK = {
    "phoenix_history": "чистка истории версий (10 + самая длинная, save-phoenix.py)",
    "read_batches": "батчи чтения гаснут после подтверждения (read-messages.py)",
}

# Служебные таблицы FTS5 у виртуальной таблицы <имя>: <имя>_data/_idx/_content/
# _docsize/_config. Список — источник СУФФИКСОВ, а не готовых имён: настоящий список
# имён строится ТОЛЬКО из реально существующих виртуальных таблиц (find_shadow_tables),
# чтобы не задеть случайно обычную таблицу с похожим именем.
SHADOW_SUFFIXES = ("_data", "_idx", "_content", "_docsize", "_config")

# Имя таблицы в начале SQL-выражения дампа — CREATE (VIRTUAL) TABLE / INSERT INTO /
# DELETE FROM / UPDATE, в кавычках любого вида или без них.
_STMT_NAME_RE = re.compile(
    r"^\s*(?:CREATE\s+(?:VIRTUAL\s+)?TABLE(?:\s+IF\s+NOT\s+EXISTS)?"
    r"|INSERT\s+INTO|DELETE\s+FROM|UPDATE)\s+[\"']?([A-Za-z0-9_]+)[\"']?",
    re.IGNORECASE,
)

_CONTENT_OPTION_RE = re.compile(r"content\s*=\s*['\"]([^'\"]*)['\"]", re.IGNORECASE)

# Фиксированное зерно — приёмка и живой прогон выбирают ОДНИ И ТЕ ЖЕ два случайных
# слова словаря поиска при сверке (карточка #610, случай С1).
WORD_SEED = 20260914


def previous_counts(out: Path):
    """Счётчики строк по таблицам из шапки ПРЕЖНЕГО дампа. None — шапки нет/не читается."""
    if not out.exists():
        return None
    try:
        with out.open(encoding="utf-8") as f:
            for _ in range(12):   # шапка живёт в первых строках, дальше не ходим
                line = f.readline()
                if line.startswith("-- строк по таблицам: "):
                    pairs = line[len("-- строк по таблицам: "):].strip().split(", ")
                    return {p.split("=")[0]: int(p.split("=")[1]) for p in pairs if "=" in p}
    except (OSError, ValueError):
        return None
    return None


SEARCH_HEADER_NOTE = ("таблицы поиска в прежней шапке — теперь сверяются выдачей,"
                      " не числом строк")
# 🩸 ВТОРОЙ СЛЕД ТОГО ЖЕ ПЕРЕХОДА (находка PROTO, карточка #610). Прежняя выгрузка
# старой версии писала строки таблицы поиска и её служебных построчно — новая этого
# не делает (решение 1 выше), и новый дамп оттого МЕНЬШЕ в байтах, хотя строк нигде
# не убыло. Без этой поправки байтовый гард (ниже, «ДАМП УМЕНЬШИЛСЯ...записи стали
# короче») кричал бы на исправном переходе тем же текстом, что и на настоящей потере.
SEARCH_SIZE_SHRINK_NOTE = ("выгрузка меньше: таблицы поиска больше не пишутся"
                          " построчно — при восстановлении перестраиваются; строк"
                          " в обычных таблицах не убыло")


def check_row_shrink(previous: dict, counts: dict, search_related_names: set = frozenset()):
    """→ (тревоги, объяснения, заметка_о_поиске): убыль строк против прежнего дампа.

    🩸 ПЕРЕХОД (находка COORD, карточка #610). Прежняя выгрузка, снятая СТАРОЙ версией,
    несёт в шапке счётчиков таблицу поиска и её служебные — они там ЕСТЬ, а в счётчиках
    ТЕКУЩЕГО прогона их больше нет (см. решение 5/7 выше). Без этой поправки первый же
    прогон новой версии против такой шапки объявлял бы их ИСЧЕЗНУВШИМИ — ложно, число
    строк там просто больше не считаем. Имя из прежней шапки не судим по счёту, если
    оно — ИМЕННО ТЕКУЩАЯ таблица поиска или её служебная (search_related_names, тем же
    find_virtual_tables/find_shadow_tables, что и выше). Если таблица поиска, названная
    в прежней шапке, из ТЕКУЩЕЙ базы пропала совсем (со служебными) — это смена схемы,
    и её кто-то должен объяснить: тревога остаётся.
    """
    alerts, explanations = [], []
    search_note = None
    for t, was in previous.items():
        if t in search_related_names:
            search_note = SEARCH_HEADER_NOTE
            continue
        now = counts.get(t)
        if now is None:
            alerts.append(f"таблица {t} ИСЧЕЗЛА (было {was} строк)")
        elif now < was:
            if t in LEGAL_SHRINK:
                explanations.append(f"{t} −{was - now} — {LEGAL_SHRINK[t]}")
            elif t == "messages":
                growth = counts.get("messages_history", 0) - previous.get("messages_history", 0)
                if growth >= was - now:
                    explanations.append(f"messages −{was - now} → messages_history +{growth} — переезд")
                else:
                    alerts.append(f"messages −{was - now}, а messages_history выросла лишь"
                                  f" на {growth} — переездом НЕ объяснено")
            else:
                alerts.append(f"{t} −{was - now} строк — удалять из неё никто не должен")
    return alerts, explanations, search_note


def find_virtual_tables(conn) -> dict:
    """Виртуальные таблицы источника: имя → их CREATE-строка из sqlite_master."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    return {name: sql for name, sql in rows if sql.strip().upper().startswith("CREATE VIRTUAL TABLE")}


def find_shadow_tables(conn, virtual_names) -> set:
    """Служебные таблицы виртуальных — только те, что реально есть в sqlite_master."""
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    shadow = set()
    for name in virtual_names:
        for suffix in SHADOW_SUFFIXES:
            candidate = name + suffix
            if candidate in existing:
                shadow.add(candidate)
    return shadow


def check_restorable(name: str, create_sql: str):
    """→ (можно ли восстановить эту виртуальную таблицу, причина отказа или None).

    Восстановимы только таблицы поиска FTS5 с ВНЕШНИМ содержимым (content=имя_таблицы,
    непустое): их индекс перестраивается из содержимого обычной таблицы, которая
    выгружается как обычно. Таблица, чей текст хранится в ней самой (FTS5 без content=
    либо content=''), и любая другая виртуальная таблица — восстанавливать не умеем:
    их служебные таблицы в выгрузку не попадают (см. SHADOW_SUFFIXES), а значит
    и содержимое такой таблицы попало бы в разряд «нечем перестроить».
    """
    if "fts5" not in create_sql.lower():
        return False, f"{name}: виртуальная таблица не FTS5 — восстановление не умеем"
    m = _CONTENT_OPTION_RE.search(create_sql)
    if not m or m.group(1) == "":
        return False, f"{name}: содержимое в самой таблице поиска — перестроить нечем"
    return True, None


def statement_table_name(stmt: str):
    m = _STMT_NAME_RE.match(stmt)
    return m.group(1) if m else None


# 🩸 НАХОДКА PROTO 2026-09-14 09:40 UTC (карточка #610), при первой живой выгрузке новой
# версией: в atlas.agents-sync.db стоит `*.sql text eol=lf`, и git при коммите заменяет
# CRLF на LF ВО ВСЁМ файле — и внутри значений тоже. Один комментарий карточки в живой
# базе несёт 37 знаков CR; в git-объекте выгрузки их 0 — и в прежней выгрузке 05.09 тоже 0.
# Проверка разворотом этого не видит: она читает рабочий файл, а удалёнка хранит другое.
# Лечится в самой выгрузке, а не настройкой одного хранилища: инструмент едет в пакет,
# и чужое хранилище может нормализовать так же. В INSERT от iterdump знак CR бывает
# только внутри строкового значения ('…') — там он заменяется выражением char(13),
# и сырых CR в файле не остаётся вовсе.
CARRIAGE_RETURN_SQL = "'||char(13)||'"


def escape_carriage_returns(stmt: str) -> str:
    """INSERT со знаком CR в значении → то же значение через char(13), без сырого CR."""
    if "\r" in stmt and stmt.startswith("INSERT INTO "):
        return stmt.replace("\r", CARRIAGE_RETURN_SQL)
    return stmt


def filter_dump_statements(conn, virtual_sql: dict, shadow_names: set):
    """Выражения iterdump без того, что относится к виртуальным и служебным таблицам,
    плюс настоящее восстановление таблиц поиска перед COMMIT.

    Фильтр опирается на ИМЕНА из sqlite_master (virtual_sql/shadow_names), а не на
    форму конкретного выражения — она меняется от версии Python (карточка #610).
    """
    excluded = set(virtual_sql) | set(shadow_names) | {"sqlite_master"}
    kept = []
    for stmt in conn.iterdump():
        if stmt.lstrip().upper().startswith("PRAGMA WRITABLE_SCHEMA"):
            continue
        name = statement_table_name(stmt)
        if name and name in excluded:
            continue
        kept.append(escape_carriage_returns(stmt))

    tail = []
    for name in sorted(virtual_sql):
        create_sql = virtual_sql[name].rstrip()
        if not create_sql.endswith(";"):
            create_sql += ";"
        tail.append(create_sql)
        tail.append(f'INSERT INTO "{name}"("{name}") VALUES(\'rebuild\');')
    if tail:
        if kept and kept[-1].strip().upper().startswith("COMMIT"):
            kept[-1:-1] = tail
        else:
            kept.extend(tail)
    return kept


def read_vocabulary(conn, name: str):
    """Словарь таблицы поиска (fts5vocab, вид 'row'): [(слово, число_записей, …), …].

    Схема таблицы поиска названа явно ('main') — vocab создаётся в temp, и без этого
    fts5vocab ищет исходную таблицу ТОЖЕ в temp и не находит её (проверено прогоном).
    """
    vocab = f"{name}__vocab_tmp"
    conn.execute(f"CREATE VIRTUAL TABLE temp.\"{vocab}\" USING fts5vocab('main', '{name}', 'row')")
    try:
        return conn.execute(f'SELECT term, cnt FROM temp."{vocab}"').fetchall()
    finally:
        conn.execute(f'DROP TABLE temp."{vocab}"')


def pick_words(vocab_rows):
    """Слова для сверки: самое частое · самое редкое · кириллица · латиница ·
    слово с «ё» · два случайных с фиксированным зерном (карточка #610, случай С1)."""
    if not vocab_rows:
        return []
    terms_sorted = sorted(t for t, _ in vocab_rows)
    by_count = sorted(vocab_rows, key=lambda r: r[1])
    picked = {by_count[0][0], by_count[-1][0]}
    cyrillic = next((t for t in terms_sorted if re.search(r"[а-яА-ЯёЁ]", t)), None)
    latin = next((t for t in terms_sorted if re.search(r"[a-zA-Z]", t)), None)
    yo_word = next((t for t in terms_sorted if "ё" in t.lower()), None)
    for w in (cyrillic, latin, yo_word):
        if w:
            picked.add(w)
    pool = [t for t, _ in vocab_rows]
    picked.update(random.Random(WORD_SEED).sample(pool, k=min(2, len(pool))))
    return sorted(picked)


def check_search_table(source_conn, verify_conn, name: str):
    """→ (сошлось ли, сколько слов сверено, причина расхождения или None).

    Число строк служебных таблиц поиска не показатель (карточка #610, случай С7) —
    сверяем ВЫДАЧЕЙ: набор номеров записей на выбранные слова обязан совпасть
    на источнике и на развёрнутой копии.
    """
    try:
        vocab = read_vocabulary(source_conn, name)
    except sqlite3.Error as exc:
        return False, 0, f"словарь не читается — {exc}"
    words = pick_words(vocab)
    for word in words:
        try:
            src_rows = {r[0] for r in source_conn.execute(
                f'SELECT rowid FROM "{name}" WHERE "{name}" MATCH ?', (word,))}
            dst_rows = {r[0] for r in verify_conn.execute(
                f'SELECT rowid FROM "{name}" WHERE "{name}" MATCH ?', (word,))}
        except sqlite3.Error as exc:
            return False, 0, f"поиск по «{word}» не выполнился — {exc}"
        if src_rows != dst_rows:
            return False, 0, (f"поиск по «{word}»: источник {sorted(src_rows)} "
                              f"≠ копия {sorted(dst_rows)}")
    return True, len(words), None


def restore_and_check(source_conn, dump_text: str, real_counts: dict,
                      search_tables: dict, verify_db: Path):
    """Развернуть выгрузку во временную базу и сверить. → (годится ли, строка исхода).

    Временная база и соединение с ней не переживают эту функцию ни при каком исходе
    (карточка #610, случаи С3/С6): закрываем в finally ДО удаления файла — Windows
    держит файл, пока соединение открыто.
    """
    if verify_db.exists():
        verify_db.unlink()
    v = sqlite3.connect(str(verify_db))
    try:
        try:
            v.executescript(dump_text)
        except sqlite3.Error as exc:
            return False, f"копия негодна: разворот не выполнился — {exc}"

        mismatches = []
        for t, n in real_counts.items():
            try:
                got = v.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except sqlite3.Error as exc:
                mismatches.append(f"{t}: таблицы нет в копии ({exc})")
                continue
            if got != n:
                mismatches.append(f"{t}: было {n}, в копии {got}")
        if mismatches:
            return False, "копия негодна: " + "; ".join(mismatches)

        words_checked = 0
        for name in sorted(search_tables):
            ok, n_words, reason = check_search_table(source_conn, v, name)
            if not ok:
                return False, f"копия негодна: поиск «{name}» — {reason}"
            words_checked += n_words
            try:
                v.execute(f'INSERT INTO "{name}"("{name}") VALUES(\'integrity-check\')')
            except sqlite3.Error as exc:
                return False, f"копия негодна: integrity-check «{name}» — {exc}"

        return True, (f"копия разворачивается: таблиц {len(real_counts)} · "
                      f"строк {sum(real_counts.values())} · "
                      f"поиск сверен по {words_checked} словам")
    finally:
        v.close()
        verify_db.unlink(missing_ok=True)


def write_and_verify(source_conn, dump_text: str, real_counts: dict,
                     search_tables: dict, out: Path, apply: bool):
    """Проверка разворотом происходит ВСЕГДА (карточка #610, случай С5).

    apply=True: выгрузка сперва пишется во временный файл РЯДОМ с целью, проверяется
    ИЗ НЕГО, и только при успехе меняется местами с целью (os.replace) — прежний файл
    при неудаче остаётся байт в байт тем же. apply=False (пробный прогон): проверка
    всё равно происходит, но во временном каталоге СИСТЕМЫ, не рядом с целью, и цель
    не трогается вовсе.

    🩸 ЗАМЕЧАНИЕ COORD (приёмка карточки #610). restore_and_check ловит только
    sqlite3.Error — сбой ИНОГО рода (память, диск, что угодно) раньше пролетал мимо:
    временный файл рядом с целью оставался НАВСЕГДА, а вместо обычного исхода роль
    видела чужую трассировку. Любой сбой здесь превращается в тот же вид исхода
    («копия негодна: <тип>: <текст>»), и временный файл убирается ПРИ ЛЮБОМ исходе —
    finally, а не только на ветке «известная неудача».
    """
    if apply:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp_sql = out.parent / (out.name + ".tmp")
        tmp_sql.write_text(dump_text, encoding="utf-8", newline="\n")
        verify_db = out.parent / "_verify.db"
        ok = False
        try:
            # newline="" — читать ровно те байты, что записаны: чтение по умолчанию
            # само сворачивает CRLF в LF и проверяло бы не тот текст, что лежит в файле.
            with open(tmp_sql, encoding="utf-8", newline="") as fh:
                restored_text = fh.read()
            ok, outcome = restore_and_check(source_conn, restored_text, real_counts,
                                            search_tables, verify_db)
        except Exception as exc:                       # noqa: BLE001 — см. докстрока
            ok, outcome = False, f"копия негодна: {type(exc).__name__}: {exc}"
        finally:
            if not ok:
                tmp_sql.unlink(missing_ok=True)
        if not ok:
            return False, outcome
        os.replace(tmp_sql, out)
        return True, outcome
    else:
        with tempfile.TemporaryDirectory(prefix="backup-db-dryrun-") as td:
            verify_db = Path(td) / "_verify.db"
            try:
                return restore_and_check(source_conn, dump_text, real_counts,
                                         search_tables, verify_db)
            except Exception as exc:                   # noqa: BLE001 — см. докстрока
                return False, f"копия негодна: {type(exc).__name__}: {exc}"


def open_snapshot(db_path: str) -> sqlite3.Connection:
    """Атомарный срез источника в память (находка PROTO, карточка #610).

    Живую базу пишут все роли контура. Без среза проверка вида таблиц, счётчики строк
    и сама выгрузка (iterdump) читали бы источник РАЗНЫМИ чтениями без общего среза —
    запись, случившаяся МЕЖДУ ними, давала бы «копия негодна» (счёт шапки не сошёлся
    с развёрнутым) на совершенно здоровой базе, и роль впустую повторяла бы прогон.
    Источник открывается mode=ro и ОДИН РАЗ, закрывается сразу после среза; вся
    дальнейшая работа этого файла — по копии в памяти (snap), не по источнику.
    """
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    snap = sqlite3.connect(":memory:")
    try:
        src.backup(snap)
    finally:
        src.close()
    return snap


def main():
    ap = argparse.ArgumentParser()
        # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать то, чего
    # механизм не умеет). Проверка готовности — ПРОГОН из чужого каталога.

    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="ничего не меняет: разворот теперь проверяется ВСЕГДА, "
                         "с этим флагом и без него — оставлен для прежних вызовов")
    args = ap.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта

    conn = open_snapshot(args.db)   # источник открыт mode=ro один раз; дальше — по срезу

    # ГАРД: виртуальную таблицу, которую выгрузка не умеет восстановить, — отказ ДО
    # записи файла (карточка #610, случай С4). Прежний файл выгрузки не трогается.
    virtual_sql = find_virtual_tables(conn)
    refusals = []
    for name, sql in sorted(virtual_sql.items()):
        ok, reason = check_restorable(name, sql)
        if not ok:
            refusals.append(reason)
    if refusals:
        for reason in refusals:
            print(f"⛔ {reason}")
        print("⛔ выгрузка НЕ ЗАПИСАНА: такую таблицу поиска восстановить не умеем")
        raise SystemExit(1)

    shadow_names = find_shadow_tables(conn, virtual_sql)
    all_tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    real_tables = [t for t in all_tables if t not in virtual_sql and t not in shadow_names]
    counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in real_tables}

    out = Path(args.out)
    old_size = out.stat().st_size if out.exists() else 0

    lines = ["-- mezosync.db — текстовый дамп для git-восстановимости",
             f"-- снят: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
             f"-- источник: {args.db}",
             "-- восстановление: sqlite3 new.db < этот_файл",
             "-- строк по таблицам: " + ", ".join(f"{t}={n}" for t, n in counts.items()),
             ""]
    lines.extend(filter_dump_statements(conn, virtual_sql, shadow_names))
    dump = "\n".join(lines) + "\n"

    # ⚠️ МЕРЯЕМ В БАЙТАХ, А НЕ В СИМВОЛАХ. len(dump) — символы; файл на диске — UTF-8,
    # где кириллица занимает 2 байта. Сравнение len(dump) с old_size (байты) давало
    # «дамп усох на треть» при выросшей БД — ложная тревога о потере данных, а в обратную
    # сторону такая шкала замаскировала бы РЕАЛЬНУЮ потерю. Инструмент бэкапа, врущий
    # числом, хуже отсутствующего.
    new_size = len(dump.encode("utf-8"))
    delta = new_size - old_size
    print(f"Таблиц: {len(real_tables)} · строк всего: {sum(counts.values())}"
          + (f" · таблиц поиска: {len(virtual_sql)} (сверяются отдельно, выдачей)"
             if virtual_sql else ""))
    print(f"Дамп: {new_size/1024:.0f} КБ" + (
        f"  (был {old_size/1024:.0f} КБ, {'+' if delta >= 0 else ''}{delta/1024:.1f} КБ)"
        if old_size else "  (первый снимок)"))
    # Сверка СТРОК ПО ТАБЛИЦАМ против шапки прежнего дампа — главный замер.
    # Байтовая дельта выше — только справка: она и врёт в обе стороны (карточка #250).
    previous = previous_counts(out)
    search_related_names = set(virtual_sql) | shadow_names
    alerts, explanations, search_note = (
        check_row_shrink(previous, counts, search_related_names) if previous else ([], [], None))
    if alerts:
        print("  🔴 СТРОКИ ПРОПАЛИ БЕЗ ЗАКОННОЙ ПРИЧИНЫ — проверь, не потеряна ли часть БД,"
              " ПРЕЖДЕ чем коммитить:")
        for a in alerts:
            print(f"     · {a}")
        if explanations:
            print("     (законная часть убыли, к тревоге не относится: "
                  + " · ".join(explanations) + ")")
    elif explanations and delta < 0:
        print("  ✅ дамп уменьшился ЗАКОННО: " + " · ".join(explanations))
    elif search_note and delta < 0:
        # см. SEARCH_SIZE_SHRINK_NOTE выше: та же причина, что у search_note,
        # объясняет и байтовую убыль — «взгляни глазами» здесь была бы ложной тревогой.
        print(f"  ℹ️  {SEARCH_SIZE_SHRINK_NOTE}")
    elif old_size and delta < 0:
        if previous is None:
            print("  ⚠️  ДАМП УМЕНЬШИЛСЯ, а шапки со счётчиками у прежнего дампа нет —"
                  " сверить по таблицам нечем. Взгляни глазами, ПРЕЖДЕ чем коммитить.")
        else:
            print("  ⚠️  ДАМП УМЕНЬШИЛСЯ, хотя строк нигде не убыло: записи стали короче."
                  " Для rules/phoenix правка по месту законна, но чисткой истории это НЕ"
                  " объяснено — взгляни глазами, ПРЕЖДЕ чем коммитить.")
    elif search_note:
        print(f"  ℹ️  {search_note}")
    # CR вне значений (в тексте схемы) заменить нечем без риска исказить её — называем.
    leftover_cr = dump.count("\r")
    if leftover_cr:
        print(f"  ⚠️  в выгрузке остались знаки CR вне значений ({leftover_cr}) — хранилище"
              " с eol=lf заменит их при коммите, и копия разойдётся с базой в этих местах")
    print(f"Цель: {out}")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")

    ok, outcome = write_and_verify(conn, dump, counts, virtual_sql, out, args.apply)

    if args.apply and ok:
        print(f"\n✅ Дамп записан: {out.name}")
        # ⚰️ Здесь стояло «push — только по слову владельца». Запрет СНЯТ владельцем
        # 2026-08-08 15:58:46 UTC («пушить можно»); строка пережила свою причину и учила
        # роль отказываться от разрешённого. Разрушающее (force push, reset --hard)
        # словом по-прежнему защищено — rule8-destructive не отозвано.
        # 🩸 Карточка #610 ④: выгрузка едет в atlas.agents-sync.db, не в atlas.archs —
        # прежняя строка называла не тот репозиторий и не того, кто коммитит.
        print("\nДальше: закоммить выгрузку в atlas.agents-sync.db поимённо и отправить"
              " (push разрешён без отдельного слова; сверь состав ВЕТКИ перед отправкой)")

    # Исход разворота — ПОСЛЕДНЯЯ строка вывода (карточка #610): не уборка временной
    # базы, а именно он. Печатается после всего остального, каким бы ни был исход.
    print(outcome)

    if not ok:
        raise SystemExit(1)
    raise SystemExit(1 if alerts else 0)


if __name__ == "__main__":
    main()
