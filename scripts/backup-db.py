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

ВОССТАНОВЛЕНИЕ (два шага — база и файл путей):
    sqlite3 mezosync-restored.db < <зеркало>/mezosync.dump.sql
    и положить <зеркало>/local-paths.json как <контейнер>/.mezosync/local/paths.json —
    без этого файла восстановленный контур не знает, где его зеркало, образец и каталоги
    раскладки (карточка #677, Э3-Р5: файл путей едет в копию вместе с базой).
    Свои проверки и настройки контура (карточка #679, Э5): положить <зеркало>/local-copy/ как
    <контейнер>/.mezosync/local/ — в нём весь каталог местного, файл путей тоже.

КУДА ПИШЕТ. Папка зеркала — ключ mirror_repo файла путей контура (.mezosync/local/paths.json;
относительный путь считается от контейнера). Ключ не объявлен либо каталога по нему нет —
выгрузка идёт в <каталог базы>/backups, и об этом сказано строкой. --out называет файл прямо.
Рядом с выгрузкой кладётся копия файла путей под именем local-paths.json; файла путей нет —
строка «файла путей нет — в копию не попал», это не отказ.

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

import mezo_paths
from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD

# 🪤 ПУТЬ В ЗЕРКАЛО БЕРЁТСЯ ИЗ ФАЙЛА ПУТЕЙ, А НЕ ВПЕЧАТАН (карточка #677, Э3-Р5). Здесь стоял
# путь в наш репозиторий-зеркало (его имя — литералом), прежде найденный пробной сборкой нового
# проекта 18.08: свежий контур клал бы свой дамп В ЧУЖОЙ репозиторий. Имя выводилось от своего
# контейнера, а запасным оставалось наше. Теперь имени в коде нет вовсе: ключ mirror_repo
# файла путей (.mezosync/local/paths.json) называет папку, не объявлен — запасное место
# <каталог базы>/backups и строка об этом. Функция default_out() ниже — единственное место.
PATHS_COPY_NAME = "local-paths.json"    # имя копии файла путей рядом с выгрузкой


def default_out(db_path: Path):
    """→ (файл выгрузки по умолчанию, строка о том, откуда взято место).

    Зеркало — ключ mirror_repo файла путей ЭТОЙ базы (каталог .mezosync базы), а не контейнера
    вызывающего: бэкап песочницы идёт за песочницей, как annex_dir. Не объявлен, нет каталога
    по объявленному либо файл не читается — выгрузка идёт в <каталог базы>/backups, и строка
    называет причину. Литерала с именем зеркала здесь нет.
    """
    fallback = db_path.parent / "backups" / "mezosync.dump.sql"
    res = mezo_paths.local_path("mirror_repo", __file__, mezo_dir=db_path.parent)
    if res.outcome == mezo_paths.LOCAL_DECLARED and res.exists:
        return res.path / "mezosync.dump.sql", f"зеркало из файла путей: {res.path.as_posix()}"
    if res.outcome == mezo_paths.LOCAL_DECLARED:
        why = f"зеркало объявлено, но каталога нет: {res.path.as_posix()}"
    else:
        why = res.words
    note = f"{why} — выгрузка идёт в запасное место {fallback.parent.as_posix()}"
    if res.hint:
        note += f"\n   ⚠️ {res.hint}"
    return fallback, note


def paths_file_line(db_path: Path, out: Path, apply: bool) -> str:
    """Копия файла путей рядом с выгрузкой (при записи) либо строка, почему её нет.

    Берётся тот же файл, что читал default_out(): файл ЭТОЙ базы. Нет файла — строка
    «файла путей нет — в копию не попал», не отказ. Файл есть, но не читается — всё равно
    копируется как есть (его байты — улика для восстановления), и это сказано.
    """
    res = mezo_paths.local_path("mirror_repo", __file__, mezo_dir=db_path.parent)
    if res.outcome == mezo_paths.LOCAL_NO_FILE or res.file is None or not res.file.exists():
        return "файла путей нет — в копию не попал"
    dst = out.parent / PATHS_COPY_NAME
    if not apply:
        return f"файл путей {res.file.as_posix()} попадёт в копию как {dst.as_posix()}"
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_bytes(res.file.read_bytes())
    os.replace(tmp, dst)
    note = " (файл не читается как JSON — скопирован как есть)" \
        if res.outcome == mezo_paths.LOCAL_UNREADABLE else ""
    return f"файл путей скопирован: {dst.as_posix()}{note}"


# ═══ КАТАЛОГ МЕСТНОГО ЦЕЛИКОМ (карточка #679, этап Э5) ═══════════════════════════════════════
# 🪤 С Э5 в <каталог базы>/local/ живут не только пути, но и свои проверки общего прогона, их
# скрипты и местные настройки — то, что прежде было правкой файлов пакета и хранилось вместе
# с ними. Копия брала из local/ только файл путей ⇒ перенос местного в local/ ухудшил бы его
# сохранность: при восстановлении из копии свои проверки пропали бы МОЛЧА.
# ⇒ Каталог едет в копию целиком, под именем local-copy/ рядом с выгрузкой; файл, исчезнувший
# из local/, исчезает и из копии (иначе восстановление воскресило бы снятую проверку).
# Копия файла путей local-paths.json остаётся как была — по ней написано восстановление.
# Кэш байт-кода (__pycache__) не копируется: это след запуска местных скриптов, а не местное;
# в git-репозитории зеркала он был бы шумом при каждом прогоне.
# ⚖️ Выгрузку положили ВНУТРЬ local/ (--out) — копия не делается: она легла бы в сам local/ и при
# следующем прогоне копировала бы саму себя, вкладываясь глубже с каждым разом.
# ⚖️ Убирается из копии ТОЛЬКО то, что положил туда прошлый прогон: перечень положенного лежит
# рядом, в local-copy.list (вне самой копии — восстановление переносит каталог как есть). Чужой
# файл в local-copy/ не трогается и называется числом (находка приёмки чужой рукой Н4).
# ⚖️ local/ есть, но пуст, а прошлая копия не пуста — копия НЕ трогается: пустой каталог чаще сбой
# (пересоздан, очищен по ошибке), чем снятие всего своего разом, и последняя хорошая копия иначе
# стёрлась бы с кодом 0 (Н5). Снять копию в этом случае — рукой.
LOCAL_COPY_NAME = "local-copy"
LOCAL_COPY_LIST = "local-copy.list"
LOCAL_COPY_SKIP = frozenset({"__pycache__"})


def local_dir_line(db_path: Path, out: Path, apply: bool) -> str:
    """Копия каталога местного рядом с выгрузкой (при записи) либо строка, почему её нет."""
    local = getattr(mezo_paths, "local_dir", lambda d: Path(d).resolve().parent / "local")(db_path)
    dst = out.parent / LOCAL_COPY_NAME
    if not local.is_dir():
        return f"каталога местного нет ({local.as_posix()}) — в копию не попал"
    try:
        dst.resolve().relative_to(local.resolve())
        return (f"⚠️ каталог местного в копию НЕ попал: копия легла бы внутрь него самого "
                f"({dst.as_posix()}) — выгрузку класть вне {local.as_posix()}")
    except ValueError:
        pass
    files = sorted(p for p in local.rglob("*")
                   if p.is_file() and not LOCAL_COPY_SKIP.intersection(p.relative_to(local).parts))
    listing = out.parent / LOCAL_COPY_LIST
    prev = (set(listing.read_text(encoding="utf-8").splitlines()) - {""}
            if listing.is_file() else set())
    if not files and prev:
        return (f"⚠️ каталог местного {local.as_posix()} пуст, а в прошлой копии файлов {len(prev)} — "
                f"копию НЕ трогаю: пустой каталог чаще сбой, чем снятие всего своего; снять копию "
                f"{dst.as_posix()}/ — рукой")
    if not apply:
        return (f"каталог местного {local.as_posix()} (файлов {len(files)}) попадёт в копию "
                f"как {dst.as_posix()}/")
    kept = set()
    for f in files:
        rel = f.relative_to(local)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = f.read_bytes()
        if not target.is_file() or target.read_bytes() != data:
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
        kept.add(rel.as_posix())
    gone = [dst / r for r in sorted(prev - kept) if (dst / r).is_file()]
    for p in gone:
        p.unlink()
    foreign = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*")
                     if p.is_file() and p.relative_to(dst).as_posix() not in kept)
    tmp = listing.with_name(listing.name + ".tmp")
    tmp.write_text("".join(r + "\n" for r in sorted(kept)), encoding="utf-8")
    os.replace(tmp, listing)
    return (f"каталог местного скопирован: {dst.as_posix()}/ — файлов {len(files)}"
            + (f", из копии убрано исчезнувших из local/: {len(gone)}" if gone else "")
            + (f"; в копии лежат файлы не из local/: {len(foreign)} ({', '.join(foreign[:3])}"
               f"{', …' if len(foreign) > 3 else ''}) — не тронуты" if foreign else ""))

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

# 🩸 КАРТОЧКА #683 (находка контура onto на приёмке Э3, 05.10: «phoenix_records −15 —
# удалять из неё никто не должен», код 1, стоп на шаге 0). Пересборка записей памяти при
# КАЖДОМ сохранении раздела (save-phoenix.py → memory-records.py, карточка #525) штатно
# удаляет записи, чьих тел в разделе больше нет; журнала у этих удалений нет. Механизм
# родился ПОСЛЕ замера 26.08 и в перечень выше не попал.
# ⚖️ В LEGAL_SHRINK таблицу НЕ вносим: тогда и удаление руками прошло бы молча. Различитель —
# по самим строкам: какие записи пропали (номер, роль, раздел — из ПРЕЖНЕЙ выгрузки) и
# сохранён ли КАЖДЫЙ такой раздел (phoenix.saved_at) не раньше часа прежней выгрузки.
# Граница, названа сразу: пересборка рукой (memory-records.py без сохранения раздела)
# журнала не пишет — её убыль останется тревогой.
RECORDS_TABLE = "phoenix_records"
# Первая строка записи в выгрузке: INSERT INTO "phoenix_records" VALUES(18,'PROTO','identity',…
# Номер, роль и раздел — первые три столбца (порядок сверяется с таблицей перед разбором).
_RECORD_HEAD_RE = re.compile(
    r"^INSERT INTO \"?phoenix_records\"? VALUES\((\d+),'([^']*)','([^']*)',")
RECORDS_SHOWN = 6   # сколько разделов назвать поимённо в строке объяснения или тревоги

# Переезды строк из таблицы в таблицу ПОД ТЕМИ ЖЕ НОМЕРАМИ (карточка #683, замер по коду
# пакета 08.10: поиск DELETE FROM / DROP TABLE / REPLACE по инструментам, не приёмкам).
# Убыль первой законна, только если КАЖДЫЙ пропавший номер (из прежней выгрузки) есть сейчас
# в таблице-цели. Счёт «цель выросла не меньше» тут не годится: лента растёт новыми записками
# каждый день и прикрыла бы любую потерю архива меньше суточного прироста.
#   messages → messages_archive .......... свёртка ленты (messages-fold.py) — ветка messages ниже
#   messages_archive → messages .......... обратный ход свёртки (messages-fold.py)
#   phoenix_history_archive → phoenix_history .. возврат версий памяти (memory-history-fold.py)
#   role_rebirths → role_rebirths_foreign .. шаг схемы 20260915-foreign-rebirth-marks уносит
#                                          отметки чужих ролей (находка AIA ④-7, карточка #685)
# Тревога у остальных найденных мест верна: hint_seen худеет только от mezo_hints.забыть(),
# который зовут лишь приёмки на своих стендах; message_addressee — разовый шаг
# migrate-addressee-vnext.py (август); DROP TABLE в шагах схемы — пересборка таблицы с тем же
# числом строк; INSERT OR REPLACE числа строк не меняет.
MOVES = {
    "messages_archive": (("messages",), "обратный ход свёртки ленты (messages-fold.py)"),
    "phoenix_history_archive": (("phoenix_history",),
                                "возврат версий памяти из архива (memory-history-fold.py)"),
    "role_rebirths": (("role_rebirths_foreign",),
                      "перенос отметок чужих ролей (шаг схемы 20260915-foreign-rebirth-marks)"),
}
MESSAGES_MOVE_TARGETS = ("messages_archive", "messages_history")

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


# 🩸 КАРТОЧКА #612 ②. Час ПРЕЖНЕЙ выгрузки — граница окна, в котором запись
# remove_rows журнала (audit_log) засчитывается в объяснение ТЕКУЩЕЙ убыли. Без
# границы одна и та же старая запись объясняла бы убыль повторно на КАЖДОМ
# следующем прогоне (карточка #612, сомнение исполнителя: «журнал старше прежней
# выгрузки» — запись ДО этой границы уже объяснила убыль на ПРЕЖНЕМ прогоне и не
# имеет права объяснить её ещё раз здесь). Строка «-- снят: …» пишется этим же
# файлом (см. main): формат YYYY-MM-DD HH:MM:SS, тот же порядок сравнения, что и
# у audit_log.timestamp (SQLite datetime('now') — тоже UTC, без метки часового пояса).
_PREVIOUS_SNAPSHOT_AT_RE = re.compile(r"^-- снят: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC")


def previous_snapshot_at(out: Path):
    """Час прежней выгрузки (текстом «YYYY-MM-DD HH:MM:SS», как у audit_log.timestamp)
    из шапки прежнего дампа. None — строки нет/не читается: окно неизвестно, и
    сверка с журналом ниже это называет, а не гадает час."""
    if not out.exists():
        return None
    try:
        with out.open(encoding="utf-8") as f:
            for _ in range(12):
                line = f.readline()
                m = _PREVIOUS_SNAPSHOT_AT_RE.match(line)
                if m:
                    return m.group(1)
    except OSError:
        return None
    return None


_NAMED_REMOVED_RE = re.compile(r"^снято строк: (\d+)")


def named_removals(conn, table: str, since):
    """→ (сумма_снятого_по_журналу, [строки-пояснения]) — записи remove_rows
    (действие инструмента remove-rows.py, карточка #612 ①) для ЭТОЙ таблицы НЕ
    РАНЬШЕ часа прежней выгрузки (since, включительно — секундная точность часа
    роднит запись и дамп, случившиеся подряд, см. примечание у SQL-запроса ниже).
    since=None — окно неизвестно (шапки со часом нет, например прежний дамп снят
    версией до карточки #612, или час не распознан) — тогда ни одна запись не
    засчитывается: неизвестное окно не повод доверять журналу вслепую, лучше
    назвать убыль неназванной, чем один раз случайно объяснить её дважды.

    ⚖️ Таблицы audit_log в базе может не быть вовсе (учебные/проверочные базы без
    полной схемы координации, включая стенды bite-backup-shrink.py) — это НЕ беда
    этой функции: отсутствие журнала не отличается от отсутствия записей в нём,
    отвечаем (0, []), а не падаем.
    """
    if since is None:
        return 0, []
    try:
        # ⚠️ ГРАНИЦА ВКЛЮЧИТЕЛЬНА (>=, не >). audit_log.timestamp — секундная точность
        # (SQLite datetime('now') без долей секунды); прежняя выгрузка и запись
        # remove_rows, случившаяся сразу следом, легко попадают В ОДНУ И ТУ ЖЕ
        # секунду — строгое «после» теряло бы её (поймано прогоном приёмки
        # bite-remove-rows-shrink.py, случай 4, а не рассуждением). Ценой — редкий
        # теоретический повторный счёт, если И запись, И следующий дамп совпадут по
        # секунде ДВАЖДЫ подряд; дешевле этой редкости, чем терять запись, снятую
        # секунда в секунду с выгрузкой, — а так теряло каждый второй живой прогон.
        rows = conn.execute(
            "SELECT actor_role, timestamp, diff_md FROM audit_log "
            "WHERE action='remove_rows' AND target=? AND timestamp >= ? ORDER BY timestamp",
            (table, since)).fetchall()
    except sqlite3.Error:
        return 0, []   # audit_log нет вовсе, либо схема иная — не наша забота здесь
    total = 0
    notes = []
    for actor, ts, diff_md in rows:
        m = _NAMED_REMOVED_RE.match(diff_md or "")
        if not m:
            continue      # запись есть, но формы «снято строк: N» в ней нет — не считаем
        n = int(m.group(1))
        total += n
        notes.append(f"{actor} {ts} UTC −{n}")
    return total, notes


def previous_record_keys(out: Path, conn):
    """→ {номер записи: (роль, раздел)} из ПРЕЖНЕЙ выгрузки, или None — разобрать нельзя.

    Карточка #683. Читается только первая строка каждой записи (номер, роль и раздел стоят
    в ней первыми); тело записи не нужно. None — если выгрузки нет, она не читается или
    у таблицы в текущей базе первые три столбца не (id, role, section): тогда порядок
    в строке выгрузки неизвестен, и лучше тревога, чем угаданное объяснение."""
    try:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{RECORDS_TABLE}")')]
    except sqlite3.Error:
        return None
    if cols[:3] != ["id", "role", "section"] or not out.exists():
        return None
    keys = {}
    try:
        with out.open(encoding="utf-8") as f:
            for line in f:
                m = _RECORD_HEAD_RE.match(line)
                if m:
                    keys[int(m.group(1))] = (m.group(2), m.group(3))
    except (OSError, UnicodeDecodeError):
        return None
    return keys


def previous_ids(out: Path, conn, table: str):
    """→ множество номеров строк таблицы из ПРЕЖНЕЙ выгрузки, или None — разобрать нельзя.

    Карточка #683. Номер — первый столбец строки INSERT; если в текущей базе первый столбец
    таблицы не id, порядок неизвестен — None, и убыль остаётся тревогой."""
    try:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
    except sqlite3.Error:
        return None
    if cols[:1] != ["id"] or not out.exists():
        return None
    head = re.compile(r'^INSERT INTO "?' + re.escape(table) + r'"? VALUES\((\d+),')
    ids = set()
    try:
        with out.open(encoding="utf-8") as f:
            for line in f:
                m = head.match(line)
                if m:
                    ids.add(int(m.group(1)))
    except (OSError, UnicodeDecodeError):
        return None
    return ids


def moved_under_same_ids(conn, gone_ids: set, targets) -> set:
    """→ те из пропавших номеров, что есть сейчас хотя бы в одной таблице-цели."""
    found = set()
    for target in targets:
        try:
            present = {r[0] for r in conn.execute(f'SELECT id FROM "{target}"')}
        except sqlite3.Error:
            continue
        found |= gone_ids & present
    return found


def move_verdict(conn, table: str, prev_ids, was: int, now: int, targets, mechanism: str):
    """→ (объяснение, None) или (None, тревога): убыль table — переезд под теми же номерами?"""
    shrink = was - now
    if prev_ids is None or len(prev_ids) != was:
        return None, (f"{table} −{shrink} — записи прежней выгрузки разобрать не удалось,"
                      " переносом НЕ объяснено")
    current = {r[0] for r in conn.execute(f'SELECT id FROM "{table}"')}
    gone = prev_ids - current
    moved = moved_under_same_ids(conn, gone, targets)
    if moved == gone:
        return (f"{table} −{shrink} → {' / '.join(targets)} под теми же номерами ({len(gone)})"
                f" — {mechanism}"), None
    return None, (f"{table} −{shrink}, а в {' / '.join(targets)} нашлось лишь {len(moved)}"
                  f" из {len(gone)} пропавших номеров — переносом НЕ объяснено")


def records_shrink_verdict(conn, previous_keys, was: int, now: int, since):
    """→ (объяснение, None) или (None, тревога) для убыли phoenix_records (карточка #683).

    Законна, только если КАЖДАЯ пропавшая запись принадлежит разделу, сохранённому
    (phoenix.saved_at) не раньше часа прежней выгрузки: такую запись удалила пересборка
    при сохранении. Иначе — тревога с поимённым перечнем разделов, которых сохранение
    не объясняет."""
    shrink = was - now
    if previous_keys is None or since is None:
        why = ("час прежней выгрузки неизвестен" if since is None
               else "записи прежней выгрузки разобрать не удалось")
        return None, (f"{RECORDS_TABLE} −{shrink} строк — {why}, пересборкой при сохранении"
                      " памяти не объяснено")
    if len(previous_keys) != was:
        return None, (f"{RECORDS_TABLE} −{shrink} строк — в прежней выгрузке записей"
                      f" {len(previous_keys)}, а в её шапке {was}: разбор не сходится,"
                      " пересборкой при сохранении памяти не объяснено")
    current = {r[0] for r in conn.execute(f'SELECT id FROM "{RECORDS_TABLE}"')}
    gone = {}
    for rid, key in previous_keys.items():
        if rid not in current:
            gone[key] = gone.get(key, 0) + 1
    try:
        saved = {(r, s): at for r, s, at in conn.execute("SELECT role, section, saved_at FROM phoenix")}
    except sqlite3.Error:
        saved = {}
    named = sorted((k for k in gone if saved.get(k) is not None and saved[k] >= since))
    unnamed = sorted(k for k in gone if k not in named)

    def listing(keys):
        shown = " · ".join(f"{r}/{s} −{gone[(r, s)]}" for r, s in keys[:RECORDS_SHOWN])
        rest = len(keys) - RECORDS_SHOWN
        return shown + (f" · и ещё разделов {rest}" if rest > 0 else "")

    if unnamed:
        return None, (f"{RECORDS_TABLE} −{shrink} строк — записи пропали у разделов, не"
                      f" сохранённых после прежней выгрузки: {listing(unnamed)}; пересборкой"
                      " при сохранении памяти НЕ объяснено")
    removed = sum(gone.values())
    return (f"{RECORDS_TABLE} −{shrink} — пересборка записей при сохранении памяти"
            f" (save-phoenix.py): ушло записей {removed}, новых {removed - shrink}; разделы"
            f" сохранены после прежней выгрузки — {listing(named)}"), None


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


def check_row_shrink(previous: dict, counts: dict, search_related_names: set = frozenset(),
                     conn=None, since=None, previous_keys=None, previous_ids_of=None):
    """→ (тревоги, объяснения, заметка_о_поиске): убыль строк против прежнего дампа.

    🩸 КАРТОЧКА #612 ②. Убыль в ОБЫЧНОЙ таблице, не объяснённая ни чисткой истории,
    ни переездом messages→messages_history, теперь сверяется с audit_log ДО того,
    как стать тревогой: если записи remove_rows (действие remove-rows.py, карточка
    #612 ①) для этой таблицы НЕ РАНЬШЕ часа прежней выгрузки (`since`, см.
    previous_snapshot_at) в СУММЕ дают РОВНО ту же убыль — это не тревога, а строка
    «убыль названа журналом: …». Сумма МЕНЬШЕ убыли (часть снята без следа) или
    БОЛЬШЕ (названо больше, чем в самом деле пропало — тоже расхождение, а не повод
    молчать) — тревога, как и раньше, с добавкой того, что журнал всё же назвал.
    `conn`/`since` не даны (вызов без них, например старым кодом) — ветка ведёт
    себя ТОЧНО как до карточки #612: журнал не спрашивается вовсе.

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
                # Карточка #683: свёртка ленты (messages-fold.py) уносит записки в
                # messages_archive под теми же номерами — счёт роста messages_history её
                # не видит. Номера спрашиваются, только если счёт не объяснил убыль.
                fold = (move_verdict(conn, t, previous_ids_of(t), was, now,
                                     MESSAGES_MOVE_TARGETS, "свёртка ленты (messages-fold.py)")
                        if growth < was - now and conn is not None and previous_ids_of
                        else (None, None))
                if growth >= was - now:
                    explanations.append(f"messages −{was - now} → messages_history +{growth} — переезд")
                elif fold[0]:
                    explanations.append(fold[0])
                else:
                    alerts.append(f"messages −{was - now}, а messages_history выросла лишь"
                                  f" на {growth} — переездом НЕ объяснено")
            elif t in MOVES:
                # Карточка #683: переезд строк под теми же номерами (находка AIA ④-7 и обход
                # мест удаления по коду пакета). Без выгрузки и базы судить нечем — тревога.
                targets, mechanism = MOVES[t]
                if conn is None or previous_ids_of is None:
                    alerts.append(f"{t} −{was - now} — номера строк сверить нечем,"
                                  " переносом НЕ объяснено")
                else:
                    explanation, alert = move_verdict(conn, t, previous_ids_of(t), was, now,
                                                      targets, mechanism)
                    if explanation:
                        explanations.append(explanation)
                    else:
                        alerts.append(alert)
            elif t == RECORDS_TABLE and conn is not None:
                # Карточка #683: убыль записей памяти судится по самим пропавшим записям.
                explanation, alert = records_shrink_verdict(conn, previous_keys, was, now, since)
                if explanation:
                    explanations.append(explanation)
                else:
                    alerts.append(alert)
            else:
                # 🪤 КАРТОЧКА #612, ЛОВУШКА ②. Финальная строка тревоги ниже — тот же
                # литерал, что и ДО карточки #612 («удалять из неё никто не должен»,
                # закрыто скобкой сразу за ним): за него держится якорь обратного хода
                # ⑩ в bite-backup-shrink.py (weaken() ищет ЭТУ строку буквально). Меняя
                # текст — правь якорь тем же ходом (поиск файла в vnext-tools). Строка
                # частичного схождения ниже НАРОЧНО не повторяет тот же хвост слово
                # в слово — иначе .replace(anchor, ..., 1) мог бы попасть не в ту ветку.
                named, notes = named_removals(conn, t, since) if conn is not None else (0, [])
                if named and named == (was - now):
                    explanations.append(
                        f"{t} −{was - now} — убыль названа журналом: " + "; ".join(notes))
                elif named and named > (was - now):
                    # Замечание OPSSRE Н1 (приёмка карточки #612, 2026-09-14): журнал называет
                    # БОЛЬШЕ, чем убыло (сняли 7, 4 вставили обратно). Тревога верна — счёт не
                    # сходится, — но прежний текст «часть снята без следа» говорил обратное.
                    alerts.append(f"{t} −{was - now} строк, а журнал называет больше — {named}:"
                                  f" часть снятого вернули или добавили новые строки, сверь по журналу")
                elif named:
                    alerts.append(f"{t} −{was - now} строк, журналом названо лишь {named} —"
                                  f" с убылью не сходится, часть снята без следа")
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
def next_step_hint(out: Path) -> str:
    """Что делать с записанной выгрузкой — про ФАКТИЧЕСКУЮ папку, а не про наш контур.

    🩸 Находка tapas 2026-09-14 11:24 UTC (письмо answer.atlas.package-1eb322d-installed-
    backup-fixed-hint-names-atlas.md): строка называла atlas.agents-sync.db и наше право
    отправки «без отдельного слова» — у tapas такого хранилища нет, а право отправки
    поимённое. Инструмент едет в пакет: подсказка говорит о том, что видит сама (папка
    выгрузки и её git-репозиторий), а права контура не пересказывает — они у каждого свои.
    """
    folder = out.resolve().parent
    repo = next((p for p in (folder, *folder.parents) if (p / ".git").exists()), None)
    if repo is None:
        return (f"Дальше: {folder} не в git-репозитории — копия есть только на этой машине;"
                " куда её отправлять, решают правила вашего контура")
    return (f"Дальше: закоммить {out.name} в репозитории {repo} поимённо; отправлять — по"
            " правилам отправки вашего контура (сверь состав ВЕТКИ перед отправкой)")


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

        # 🩸 КАРТОЧКА #617 ③ (находка COORD Н2). Нуль сверенных слов раньше печатался ТОЙ ЖЕ
        # строкой, что и настоящая сверка («поиск сверен по 0 словам») — на новорождённом
        # контуре (таблиц поиска нет вовсе) это звучало как ПРОЙДЕННАЯ проверка, когда
        # проверять было нечего. Различаем ДВЕ разные причины нуля, а не одну:
        #   · таблиц поиска нет вовсе (search_tables пуст) — это законно, не тревога;
        #   · таблицы есть, а слов для сверки не набралось (пустой словарь) — это МОЛЧАНИЕ
        #     там, где сверка ожидалась, и её нельзя выдавать за пройденную.
        if not search_tables:
            search_summary = "поиск: таблиц поиска нет"
        elif words_checked == 0:
            search_summary = "поиск: слов для сверки нет — не проверен"
        else:
            search_summary = f"поиск сверен по {words_checked} словам"
        return True, (f"копия разворачивается: таблиц {len(real_counts)} · "
                      f"строк {sum(real_counts.values())} · " + search_summary)
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
    ap = argparse.ArgumentParser(
        description="текстовая выгрузка базы контура в папку зеркала (ключ mirror_repo файла путей "
                    ".mezosync/local/paths.json) и копия файла путей рядом с ней. Восстановление: "
                    "sqlite3 новая.db < mezosync.dump.sql, затем local-paths.json положить как "
                    "<контейнер>/.mezosync/local/paths.json. Без --apply ничего не пишет.")
        # R15a довезён 27.07 (замер PROTO #2867: справка не может обещать то, чего
    # механизм не умеет). Проверка готовности — ПРОГОН из чужого каталога.

    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--out", default=None,
                    help="файл выгрузки; без него — папка зеркала из файла путей (ключ "
                         "mirror_repo), а если ключа нет — <каталог базы>/backups")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="ничего не меняет: разворот теперь проверяется ВСЕГДА, "
                         "с этим флагом и без него — оставлен для прежних вызовов")
    args = ap.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта
    # Карточка #677 (Э3-Р5): место выгрузки по умолчанию — из файла путей ЭТОЙ базы.
    out_note = None
    if args.out is None:
        default_file, out_note = default_out(Path(args.db))
        args.out = str(default_file)

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
    # 🩸 КАРТОЧКА #617 (замечание COORD). --out, указывающий на СУЩЕСТВУЮЩИЙ КАТАЛОГ,
    # раньше долетал до os.replace(tmp_sql, out) в write_and_verify и падал непойманной
    # трассировкой (PermissionError на Windows / IsADirectoryError на POSIX) — вместо
    # отказа словами. Гард — ДО записи чего бы то ни было (тот же принцип, что у
    # гарда невосстановимой таблицы поиска выше): называет, что не так, и какой путь
    # дать, кодом ≠ 0.
    if out.exists() and out.is_dir():
        print(f"⛔ --out указывает на СУЩЕСТВУЮЩИЙ КАТАЛОГ, а не на файл: {out}")
        print(f"   выгрузка НЕ ЗАПИСАНА: дай путь к ФАЙЛУ, например {out / 'mezosync.dump.sql'}")
        raise SystemExit(1)
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
    since = previous_snapshot_at(out)   # карточка #612 ②: граница окна для audit_log
    search_related_names = set(virtual_sql) | shadow_names
    # Карточка #683: записи прежней выгрузки разбираются, только если их таблица убыла —
    # иначе живой прогон читал бы всю выгрузку зря.
    previous_keys = (previous_record_keys(out, conn)
                     if previous and RECORDS_TABLE in previous and RECORDS_TABLE in counts
                     and counts[RECORDS_TABLE] < previous[RECORDS_TABLE] else None)
    # Карточка #683: номера строк прежней выгрузки — по требованию и один раз на таблицу.
    ids_cache = {}

    def previous_ids_of(table):
        if table not in ids_cache:
            ids_cache[table] = previous_ids(out, conn, table)
        return ids_cache[table]

    alerts, explanations, search_note = (
        check_row_shrink(previous, counts, search_related_names, conn=conn, since=since,
                         previous_keys=previous_keys, previous_ids_of=previous_ids_of)
        if previous else ([], [], None))
    if alerts:
        print("  🔴 СТРОКИ ПРОПАЛИ БЕЗ ЗАКОННОЙ ПРИЧИНЫ — проверь, не потеряна ли часть БД,"
              " ПРЕЖДЕ чем коммитить:")
        for a in alerts:
            print(f"     · {a}")
        if explanations:
            print("     (законная часть убыли, к тревоге не относится: "
                  + " · ".join(explanations) + ")")
    elif explanations:
        # 🩸 КАРТОЧКА #612: условие «and delta < 0» СНЯТО. Запись audit_log сама добавляет
        # байты (диф с БЫЛО-JSON) — она может перекрыть убыль своей же таблицы в
        # байтах дампа, и тогда «убыль названа журналом» не печаталась бы никогда
        # (поймано прогоном bite-remove-rows-shrink.py, случай 4, не рассуждением).
        # Объяснение убыли — факт про СТРОКИ, а не про байты; печатать его безусловно,
        # раз оно есть и тревог нет, — тот же принцип, что уже давно у ветки alerts.
        print("  ✅ дамп уменьшился ЗАКОННО: " + " · ".join(explanations)
              if delta < 0 else "  ✅ убыль объяснена: " + " · ".join(explanations))
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
    if out_note:
        print(f"  ℹ️  {out_note}")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")

    ok, outcome = write_and_verify(conn, dump, counts, virtual_sql, out, args.apply)

    # Карточка #677 (Э3-Р5): файл путей едет в копию вместе с базой — рядом с выгрузкой, под
    # именем local-paths.json. Нет файла — строка, не отказ. Выгрузка не удалась — файл путей
    # не копируется (копия без базы ничего не восстанавливает).
    if ok:
        print(f"  📄 {paths_file_line(Path(args.db), out, args.apply)}")
        print(f"  📁 {local_dir_line(Path(args.db), out, args.apply)}")

    if args.apply and ok:
        print(f"\n✅ Дамп записан: {out.name}")
        # ⚰️ Здесь стояло «push — только по слову владельца». Запрет СНЯТ владельцем
        # 2026-08-08 15:58:46 UTC («пушить можно»); строка пережила свою причину и учила
        # роль отказываться от разрешённого. Разрушающее (force push, reset --hard)
        # словом по-прежнему защищено — rule8-destructive не отозвано.
        # 🩸 Карточка #610 ④: выгрузка едет в atlas.agents-sync.db, не в atlas.archs —
        # прежняя строка называла не тот репозиторий и не того, кто коммитит.
        # 🩸 И эта строка оказалась про НАШ контур: см. next_step_hint.
        print("\n" + next_step_hint(out))

    # Исход разворота — ПОСЛЕДНЯЯ строка вывода (карточка #610): не уборка временной
    # базы, а именно он. Печатается после всего остального, каким бы ни был исход.
    print(outcome)

    if not ok:
        raise SystemExit(1)
    raise SystemExit(1 if alerts else 0)


if __name__ == "__main__":
    main()
