#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
scratch-folders.py — черновая папка роли: замер каждое пробуждение, уборка только по слову
владельца, сводка по контуру для COORD.

ПРАВИЛО (решение владельца ≤2026-10-02 22:55 UTC «Без постоянного разрешения», записки
#5438 · #5439; договорились COORD, OPSSRE, PROTO — записки #5427 · #5428 · #5431 · #5432):
черновые папки НАБЛЮДАЮТСЯ каждое пробуждение, а УБИРАЮТСЯ только словом владельца в
собственном чате роли, каждый раз заново. Постоянного разрешения нет. Удаление — только в
корзину Windows; корзину очищает только владелец; чужую черновую папку роль не трогает.
Правило исключения из rule8-destructive НЕ делает: уборка — разрушающее действие.

ЧТО ТАКОЕ ЧЕРНОВАЯ ПАПКА РОЛИ. Папка scratchpad живого чата роли под корнем %TEMP%\claude.
  Приложение раскладывало её двумя способами, и у одного номера чата бывают ОБЕ папки:
    прежняя раскладка   %TEMP%\claude\<каталог контура>\<номер чата>\scratchpad
    новая раскладка     %TEMP%\claude\<16 шестнадцатеричных знаков>\<номер чата>\scratchpad
  · <каталог контура> — путь контейнера, где КАЖДЫЙ знак, кроме латинских букв и цифр,
    заменён на «-»: <КОНТУР> → C--guts--atlas. Так называло каталоги само приложение
    (сверено чтением %TEMP%\claude 2026-10-02 ~23:30 UTC).
  · каталог из 16 шестнадцатеричных знаков — сверено чтением %TEMP%\claude 2026-11-22
    ~19:50 UTC (карточка #807): таких каталогов у эталона 29, старейший создан 2026-11-04;
    у семи ролей из десяти папки чата лежат по ОБЕИМ раскладкам, у трёх — только по
    прежней. Живой чат пишет в новую, прежняя папка того же чата лежит рядом и больше не
    растёт. ПРАВИЛО, ПО КОТОРОМУ ПРИЛОЖЕНИЕ СТРОИТ ЭТИ 16 ЗНАКОВ, НЕ
    ВЫЯСНЕНО — и инструменту оно не нужно: папка ищется по НОМЕРУ ЧАТА в каталоге прежней
    раскладки и в каждом каталоге из 16 знаков. Нашлось несколько — меряются ВСЕ, каждая
    названа своей строкой с путём, итог роли — СУММА, и об этом сказано в выводе.
  · номер чата (transcript_id) — из role_sessions базы контура (одна строка на роль). Обязан
    иметь вид номера чата (8-4-4-4-12 шестнадцатеричных знаков), а папка — лежать ВНУТРИ
    своего каталога первого уровня, и ни каталог чата, ни scratchpad не могут быть ссылкой:
    иначе отказ кодом 2 (запись «..\x» в базе или ссылка увели бы уборку за пределы корня).
  · папка этого же чата в каталоге с ДРУГИМ именем (раскладка, которой инструмент не знает)
    или в каталоге-ссылке не меряется и не убирается, но НАЗЫВАЕТСЯ строкой: следующая
    раскладка не должна снова стать молчащим нулём.

РЕЖИМЫ.
  (по умолчанию)   ЗАМЕР своей папки — ничего не меняет. По каждой подпапке верхнего
                   уровня: место на диске · час последней правки внутри · копии базы
                   координации (сколько и сколько из них старше 7 суток) · решение. Код 0.
  --apply --owner-word "<дословно и час UTC вида 2026-10-03 09:00 UTC>"
                   подпапки с решением «убрать» — В КОРЗИНУ. Только своя папка, только живая
                   база контура (без --db или --db, равный живой). Код 0 — всё убрано; 1 —
                   были отказы или уборку остановил отказ среды.
  --contour        сводка по папкам контура (для COORD, раз в неделю): размер, чья
                   (роль по transcript_id или «закрытый чат, роли нет»), старые копии базы.
                   Каталог прежней раскладки — ВСЕ чаты. Каталоги из 16 знаков — только
                   чаты, которые знает база контура (живые роли и история адресов): чей
                   каталог из 16 знаков, по имени не узнать, и чужие чаты в сводку не идут.
                   Сколько рядом с чатами контура лежит папок чатов, которых база не знает,
                   названо числом — они не мерены. Только замер; --apply с ним НЕ
                   поддерживается. Роли не прочитались — код 2 «не проверено», а не «все
                   чаты закрытые».
  --brief          одна строка для общего прогона проверок. Код 0 ВСЕГДА — это замер, а не
                   провал. Обход только своих папок и не дольше BRIEF_BUDGET_S секунд на все.

РАЗМЕР. «На диске» — каждый файл один раз по (st_dev, st_ino): жёсткая ссылка с другим
  именем места не занимает (замер проверки 2026-10-02 ~23:47 UTC: в папке PROTO 132 214
  файлов с несколькими именами, сумма по именам 30,48 ГБ, на диске ≈23,4 ГБ — как у du).
  Полный замер и уборка берут номер файла у КАЖДОГО файла через os.stat (папка PROTO —
  62 с, замер 2026-10-03 ~00:30 UTC); --brief и --contour — только у файлов от DEDUPE_MIN (у PROTO 1 591 файл, ≈0,3 с,
  сверено 6,47 из 7,11 ГБ повторов; замер 2026-10-03 ~00:00 UTC) и пишут «≈». Сверка с
  местом в корзине берёт сумму ПО ИМЕНАМ: корзина записывает длину каждого имени, и
  меньшая оценка грозила бы вытеснением.

РЕШЕНИЕ ПО ПОДПАПКЕ (порядок важен — первое подошедшее):
  «оставить: упомянута в открытой карточке #N / записке #N» — имя подпапки отдельным словом
       в REF_WINDOW знаках после слова «scratchpad» и ПЕРВЫМ звеном пути: «…\scratchpad\<имя>»,
       «scratchpad/<имя>», а также живые формы контура «scratchpad <имя>/» и «scratchpad
       PROTO <имя>/» (замер по снимку 2026-10-02 ~23:46 UTC: открытые карточки #622, #651,
       #667 ссылаются именно так). Ищется в заголовке, теле, сроке, причине блокировки и
       комментариях ОТКРЫТОЙ карточки (статус не done/dropped) и в записках за 7 суток. Имя
       сверяется ЦЕЛИКОМ («w12» не бережёт «w1»), а в «scratchpad w12/d1002/full/» упомянута
       только w12. Одноимённая папка другого чата тоже бережёт — ошибка в безопасную сторону.
  «оставить: правка за последний час» — ею пользуются (работающий помощник, идущий прогон).
       Час правки — по os.stat каждого файла и каталога: запись каталога у файла, в который
       дописывают через открытый дескриптор, отстаёт до закрытия файла (замер 2026-10-03
       ~00:09 UTC: в записи каталога 2 часа назад, у os.stat — сейчас).
  «отказ: ссылка на другое место» · «отказ: путь длиннее 260 знаков» · «отказ: нет
       доступа» · «отказ: не читается» — НЕ обходятся: называются списком с размером.
       Путь от 260 знаков корзина не берёт, и Windows стёр бы его насовсем (260 — предел
       MAX_PATH вместе с завершающим нулём, поэтому отказ уже с 260 знаков ровно). Длина —
       в знаках UTF-16, как считает Windows: знак вне BMP (например, эмодзи) — два.
  «убрать» — всё остальное.

КОПИЯ БАЗЫ КООРДИНАЦИИ — файл с заголовком «SQLite format 3» И таблицей messages.
  Не по имени файла: мусор с именем mezosync.db копией не считается, а снимок с любым
  именем — считается. Открывается СТРОГО на чтение: mode=ro И immutable=1.
  🩸 Почему не просто mode=ro (замер 2026-10-02 ~23:09 UTC перед написанием): у копии в режиме WAL
  открытие с одним mode=ro ОСТАВЛЯЕТ рядом файлы -shm и -wal и сдвигает час правки
  каталога — замер менял бы дерево и делал подпапку «свежей» на час вперёд. immutable=1
  запрещает библиотеке создавать что-либо рядом с файлом.
  Копии в КОРНЕ папки считаются в итоге, называются списком отдельно и этим инструментом
  НЕ убираются (его предмет — подпапки); что с ними делать, решает владелец.

КОРЗИНА. send2trash, если пакет установлен; иначе PowerShell —
  [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(путь, OnlyErrorDialogs,
  SendToRecycleBin). Сам этот инструмент shutil.rmtree и os.remove не зовёт. Но и
  оболочка Windows может удалить мимо корзины: DeleteDirectory в сеансе без рабочего стола
  (Environment.UserInteractive = false) зовёт Directory.Delete — насовсем (разбор кода
  сборки 2026-10-02 ~23:40 UTC), а с OnlyErrorDialogs оболочка без вопроса стирает то,
  чего корзина не берёт. Поэтому гарантия держится на проверках, и они названы целиком:
  ДО уборки — отказ кодом 2, ничего не тронуто, если: нет ни send2trash, ни PowerShell со
       сборкой Microsoft.VisualBasic · сеанс без рабочего стола · задана политика
       NoRecycleFiles или RecycleBinSize (HKCU/HKLM …\Policies\Explorer) · корзина тома
       выключена (NukeOnDelete) или её вместимость не узнать (BitBucket\Volume\{GUID},
       SHQueryRecycleBinW) · MEZO_TRASH_DIR задан при настоящем корне черновых папок;
  ПЕРЕД каждой папкой — перемер (ожила — оставлена; стала отказом — в список отказов);
       сверка места (сумма по именам × TRASH_MARGIN больше свободного — «отказ: не влезает
       в корзину»); пробное переименование рядом и обратно (не прошло — папка занята
       процессом: оболочке её не отдаём, ОСТАНОВКА всей уборки, код 1);
  ПОСЛЕ каждой папки — её нет на месте, а корзина выросла хотя бы на один предмет и не
       меньше чем на ARRIVAL_SHARE места папки на диске; иначе «⛔ ПОХОЖЕ, УШЛА МИМО
       КОРЗИНЫ», ОСТАНОВКА всей уборки, код 1.
  Чего это НЕ даёт: если оболочка всё же стёрла папку насовсем по причине, которой нет в
  списке выше, это видно только ПОСЛЕ — проверка прихода останавливает уборку на этой
  папке, но саму её не вернуть. Настоящая корзина приёмкой не испытана (в опытах
  запрещена); испытаны подменный каталог и сама проверка прихода.

ПЕРЕМЕННЫЕ СРЕДЫ.
  MEZO_ROLE                 своя роль; при --apply обязана совпасть с --role.
  CLAUDE_CODE_SESSION_ID    номер живого чата (ставит само приложение). Роль не названа —
                            ищется по нему в role_sessions.transcript_id; при --apply
                            сверяется с --role так же, как MEZO_ROLE. При --apply своя роль
                            ОБЯЗАНА узнаться хотя бы одним из двух — иначе отказ «не знаю,
                            чей это чат»: --role любой роли без них прошёл бы.
  MEZO_SCRATCH_ROOT         корень вместо %TEMP%\claude (опыты).
  MEZO_SCRATCH_THRESHOLD_GB порог «пора убрать» вместо 2 ГБ (опыты).
  MEZO_TRASH_DIR            ⚠️ ТОЛЬКО ДЛЯ ОПЫТОВ: переносить в этот каталог ВМЕСТО корзины.
                            Принимается только вместе с MEZO_SCRATCH_ROOT, не равным
                            настоящему %TEMP%\claude.
  MEZO_TRASH_CAPACITY_MB    ⚠️ ТОЛЬКО ДЛЯ ОПЫТОВ: вместимость подменного каталога.
  MEZO_CONTAINER            контейнер контура (как у всех инструментов контура).

ЧЕГО ИНСТРУМЕНТ НЕ ДЕЛАЕТ — названо прямо:
  · не убирает папки прежних и закрытых чатов (--contour их только меряет; уборка
    закрытых чатов — отдельной работой по слову владельца, рукой COORD);
  · не трогает файлы в корне своей папки — только подпапки верхнего уровня;
  · не очищает корзину и не пишет в базу контура (база открывается mode=ro).
  · стенды приёмок в корне %TEMP% (bite-* — карточка #657) не его предмет.

    python <КОНТУР>/vnext-tools/scratch-folders.py --role PROTO
    python <КОНТУР>/vnext-tools/scratch-folders.py --role PROTO --brief
    python <КОНТУР>/vnext-tools/scratch-folders.py --contour
    MEZO_ROLE=PROTO python <КОНТУР>/vnext-tools/scratch-folders.py --role PROTO --apply --owner-word "«…» 2026-10-03 09:00 UTC"
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

GB = 1024 ** 3
MB = 1024 ** 2
KB = 1024
THRESHOLD_GB = 2.0             # «пора убрать», когда на диске больше
OLD_COPY_DAYS = 7              # копия базы старше — второй порог
NOTE_WINDOW_DAYS = 7           # записки за столько суток бережут подпапку
FRESH_SECONDS = 3600           # правка за последний час бережёт подпапку
LONG_PATH = 260                # предел MAX_PATH вместе с завершающим нулём, в знаках UTF-16
BRIEF_BUDGET_S = 10.0          # --brief не дольше: он стоит в общем прогоне проверок
TRASH_MARGIN = 1.10            # запас на округление до кластеров при сверке с корзиной
ARRIVAL_SHARE = 0.5            # корзина обязана вырасти хотя бы на такую долю места папки
DEDUPE_MIN = MB                # быстрый замер сверяет жёсткие ссылки у файлов от этого размера
REF_WINDOW = 40                # имя подпапки ищется в стольких знаках после слова scratchpad
SQLITE_MAGIC = b"SQLite format 3\x00"
MIN_DB_SIZE = 1024             # меньше двух страниц по 512 таблицы не бывает
DB_PAGE_MIN = 512              # размер файла базы — целое число страниц от 512
CLOSED_STATUSES = ("done", "dropped")
CLOSED_CHAT = "закрытый чат, роли нет"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
SELF = Path(__file__).resolve()

KEEP, REFUSE, REMOVE = "keep", "refuse", "remove"
SCRATCH_WORD = re.compile(r"scratchpad", re.IGNORECASE)
REF_TOKEN = re.compile(r"(?<![\w.\-\\/])[\w.\-]+")
PLAIN_NAME = re.compile(r"[\w.\-]+")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
HEX16_RE = re.compile(r"[0-9a-f]{16}", re.IGNORECASE)   # имя каталога новой раскладки
OLD_LAYOUT = "прежняя раскладка"   # %TEMP%\claude\<каталог контура>\<номер чата>\scratchpad
NEW_LAYOUT = "новая раскладка"     # %TEMP%\claude\<16 шестнадцатеричных знаков>\<номер чата>\scratchpad
UNKNOWN_LAYOUT = "раскладка инструменту неизвестна"
LINKED_TOP = "каталог — ссылка на другое место"
OWNER_WORD_TIME = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?\s*UTC")
POLICY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"

NOT_INTERACTIVE = "MEZO-NOT-INTERACTIVE"
# ⚠️ Первая строка обоих сценариев: в сеансе без рабочего стола DeleteDirectory удаляет
# НАСОВСЕМ (Directory.Delete), не глядя на SendToRecycleBin. Проверяем в том же процессе,
# который будет удалять.
PS_GUARD = (f"if (-not [Environment]::UserInteractive) {{ Write-Output '{NOT_INTERACTIVE}'; "
            f"exit 3 }}; $ErrorActionPreference = 'Stop'; ")
PS_PROBE = (PS_GUARD + "Add-Type -AssemblyName Microsoft.VisualBasic; "
            "[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin")
PS_RECYCLE = (PS_GUARD + "Add-Type -AssemblyName Microsoft.VisualBasic; "
              "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
              "$env:MEZO_RECYCLE_TARGET, 'OnlyErrorDialogs', 'SendToRecycleBin')")


# ═══ ОБХОД ДЕРЕВА ═══════════════════════════════════════════════════════════════════════

@dataclass
class TreeScan:
    """Итог обхода одного дерева. Ссылки (symlink/junction) не проходятся."""
    size: int = 0                                     # сумма длин по ИМЕНАМ файлов
    single: int = 0                                   # файлы с одним именем
    multi: dict = field(default_factory=dict)         # (том, номер файла) → длина: несколько имён
    files: int = 0
    last_edit: float = 0.0
    copies: dict = field(default_factory=dict)        # копия базы (номер файла или путь) → час правки
    root_copies: dict = field(default_factory=dict)   # копии прямо в корне обхода → (имя, длина, час)
    longest: int = 0                                  # в знаках UTF-16
    longest_path: str = ""
    denied: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)    # (путь, причина)
    is_link: bool = False
    truncated: bool = False                           # обход оборван по времени (--brief)

    @property
    def disk(self) -> int:
        return disk_size([self])


def disk_size(scans) -> int:
    """Место на диске нескольких деревьев вместе: файл с несколькими именами — один раз."""
    multi: dict = {}
    for s in scans:
        multi.update(s.multi)
    return sum(s.single for s in scans) + sum(multi.values())


def merged(scans) -> TreeScan:
    """Сумма нескольких обходов — папки одного чата по разным раскладкам. Файл с несколькими
    именами считается один раз и между папками; копии базы держатся по пути или номеру
    файла, поэтому одноимённые файлы разных папок друг друга не затирают."""
    total = TreeScan()
    for s in scans:
        total.size += s.size
        total.single += s.single
        total.multi.update(s.multi)
        total.files += s.files
        total.last_edit = max(total.last_edit, s.last_edit)
        total.copies.update(s.copies)
        total.root_copies.update(s.root_copies)
        if s.longest > total.longest:
            total.longest, total.longest_path = s.longest, s.longest_path
        total.denied.extend(s.denied)
        total.unreadable.extend(s.unreadable)
        total.truncated = total.truncated or s.truncated
    return total


def gb(size: int) -> str:
    # Меньше 0,1 ГБ — в МБ: «0.00 ГБ» у папки в несколько мегабайт читалось как «пусто»
    # (замечание приёмки OPSSRE, записка #5451, 2026-10-03).
    if size < GB // 10:
        return f"{size / MB:.1f} МБ"
    return f"{size / GB:.2f} ГБ"


def size_words(by_names: int, disk: int, approx: bool = False) -> str:
    mark = "≈" if approx else ""
    if gb(by_names) == gb(disk):
        return f"{mark}{gb(disk)}"
    return f"{mark}{gb(disk)} на диске (по именам файлов {gb(by_names)} — жёсткие ссылки)"


def utc(ts: float) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def u16len(s: str) -> int:
    """Длина пути в знаках UTF-16 — так меряет предел MAX_PATH Windows (знак вне BMP — два)."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def is_link_entry(entry) -> bool:
    try:
        return entry.is_symlink() or bool(getattr(entry, "is_junction", lambda: False)())
    except OSError:
        return False


def is_link_path(p: Path) -> bool:
    try:
        return os.path.islink(p) or bool(getattr(os.path, "isjunction", lambda _x: False)(p))
    except OSError:
        return False


def has_messages_table(path: str) -> bool:
    """Таблица messages в базе SQLite. СТРОГО на чтение: mode=ro И immutable=1 (см. шапку)."""
    uri = "file:" + urllib.parse.quote(Path(path).as_posix(), safe="/:") + "?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            row = con.execute("SELECT 1 FROM sqlite_master "
                              "WHERE type = 'table' AND name = 'messages'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return row is not None


def is_db_copy(path: str, size: int) -> bool:
    """Копия базы координации: заголовок SQLite И таблица messages — не по имени файла."""
    if size < MIN_DB_SIZE or size % DB_PAGE_MIN:
        return False
    try:
        with open(path, "rb") as fh:
            if fh.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
                return False
    except OSError:
        return False
    return has_messages_table(path)


def add_file(scan: TreeScan, path: str, st, at_root: bool) -> None:
    scan.size += st.st_size
    scan.files += 1
    key = path
    if st.st_nlink > 1:
        key = (st.st_dev, st.st_ino)
        scan.multi[key] = st.st_size
    else:
        scan.single += st.st_size
    if is_db_copy(path, st.st_size):
        scan.copies[key] = st.st_mtime
        if at_root:
            scan.root_copies[key] = (os.path.basename(path), st.st_size, st.st_mtime)


def scan_tree(top: Path, deadline: float | None = None, exact: bool = True) -> TreeScan:
    """Размер, час последней правки, копии базы, самый длинный путь, отказы доступа.

    exact — час правки, длина и номер файла берутся у КАЖДОГО файла и каталога через
    os.stat (запись каталога у открытого файла отстаёт, см. шапку). Без exact — из записи
    каталога, а номер файла (жёсткие ссылки) — только у файлов от DEDUPE_MIN."""
    scan = TreeScan()
    top_s = str(top)
    try:
        st = os.stat(top_s, follow_symlinks=False)
    except PermissionError:
        scan.denied.append(top_s)
        return scan
    except OSError as e:
        scan.unreadable.append((top_s, e.strerror or str(e)))
        return scan
    scan.last_edit = st.st_mtime
    scan.longest, scan.longest_path = u16len(top_s), top_s
    stack = [top_s]
    while stack:
        if deadline is not None and time.monotonic() > deadline:
            scan.truncated = True
            break
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except FileNotFoundError:
            scan.last_edit = max(scan.last_edit, time.time())   # исчез во время обхода — им пользуются
            continue
        except PermissionError:
            scan.denied.append(folder)
            continue
        except OSError as e:
            scan.unreadable.append((folder, e.strerror or str(e)))
            continue
        for entry in entries:
            path = entry.path
            length = u16len(path)
            if length > scan.longest:
                scan.longest, scan.longest_path = length, path
            if is_link_entry(entry):
                # ссылку не проходим (она ведёт за пределы папки) и её собственный час не
                # берём: её появление уже сдвинуло час правки каталога, где она лежит
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                dst = entry.stat(follow_symlinks=False)        # из записи каталога: дёшево
                if exact or (not is_dir and dst.st_size >= DEDUPE_MIN):
                    st = os.stat(path, follow_symlinks=False)
                else:
                    st = dst
            except FileNotFoundError:
                scan.last_edit = max(scan.last_edit, time.time())
                continue
            except PermissionError:
                scan.denied.append(path)
                continue
            except OSError as e:
                scan.unreadable.append((path, e.strerror or str(e)))
                continue
            mtime = st.st_mtime
            if mtime > scan.last_edit:
                scan.last_edit = mtime
            if is_dir:
                stack.append(path)
                continue
            add_file(scan, path, st, at_root=(folder == top_s))
    return scan


def old_copies(scan: TreeScan, now: float) -> int:
    return sum(1 for m in scan.copies.values() if now - m > OLD_COPY_DAYS * 86400)


def old_root_copies(scan: TreeScan, now: float) -> int:
    return sum(1 for _n, _s, m in scan.root_copies.values() if now - m > OLD_COPY_DAYS * 86400)


# ═══ БАЗА КОНТУРА: роли и ссылки ═══════════════════════════════════════════════════════

def open_db(db: Path) -> sqlite3.Connection:
    uri = "file:" + urllib.parse.quote(Path(db).as_posix(), safe="/:") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def roles_by_transcript(con):
    """→ (transcript_id (нижним регистром) → роль, ошибка чтения словами или None).
    Ошибка НЕ превращается в пустой словарь молча: пустой словарь значил бы «все чаты
    закрытые», и сводка подтолкнула бы к уборке папок живых ролей."""
    try:
        rows = con.execute("SELECT role, transcript_id FROM role_sessions "
                           "WHERE transcript_id IS NOT NULL AND transcript_id <> ''").fetchall()
    except sqlite3.Error as e:
        return {}, f"role_sessions не читается ({e})"
    return {tid.strip().lower(): (role or "").strip().upper() for role, tid in rows}, None


def history_by_transcript(con) -> dict:
    """transcript_id → роль по ИСТОРИИ адресов: подсказка «прежде был чатом X», не хозяин."""
    try:
        rows = con.execute("SELECT role, transcript_id FROM role_sessions_history "
                           "WHERE transcript_id IS NOT NULL AND transcript_id <> '' "
                           "ORDER BY id").fetchall()
    except sqlite3.Error:
        return {}
    return {tid.strip().lower(): (role or "").strip().upper() for role, tid in rows}


def transcript_of(con, role: str):
    """→ (transcript_id или None, причина словами или None)."""
    try:
        row = con.execute("SELECT transcript_id FROM role_sessions WHERE upper(role) = ?",
                          (role,)).fetchone()
    except sqlite3.Error as e:
        return None, f"role_sessions не читается ({e})"
    if row is None:
        return None, f"роли {role} нет в role_sessions"
    if not (row[0] or "").strip():
        return None, f"номер чата роли {role} (transcript_id) в role_sessions не записан"
    return row[0].strip(), None


@dataclass
class Found:
    """Одна черновая папка чата: по какой раскладке и в каком каталоге первого уровня."""
    layout: str
    top: Path
    folder: Path


def top_level_dirs(root: Path):
    """Каталоги первого уровня корня черновых папок → [(имя, путь, ссылка ли)], по имени.
    Корень не читается — пусто: есть ли корень вообще, вызывающий проверяет сам."""
    try:
        with os.scandir(root) as it:
            entries = sorted(it, key=lambda e: e.name.lower())
    except OSError:
        return []
    out = []
    for entry in entries:
        path = Path(entry.path)
        link = is_link_path(path)
        try:
            if not link and not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        out.append((entry.name, path, link))
    return out


def own_folders(root: Path, old_name: str, tid: str):
    """→ (папки [Found], не мерено [(каталог, причина)], None) или (None, None, причина отказа).

    Папка чата ищется по НОМЕРУ ЧАТА в каталогах первого уровня корня: в каталоге прежней
    раскладки (имя из пути контура) и в каждом каталоге новой (16 шестнадцатеричных
    знаков). Правило построения этих 16 знаков не нужно: номер чата у обеих раскладок один.
    Номер чата из базы — данные, а не путь: вид номера сверяется, каталог чата и scratchpad
    не могут быть ссылкой, папка обязана лежать ВНУТРИ своего каталога первого уровня.
    Каталог с другим именем и каталог-ссылка, где папка этого чата есть, не меряются и не
    убираются — они возвращаются вторым списком, чтобы вызывающий их НАЗВАЛ."""
    if not UUID_RE.fullmatch(tid):
        return None, None, f"номер чата в role_sessions не похож на номер чата: «{tid}»"
    found, skipped = [], []
    old_key = os.path.normcase(old_name)
    for name, top, link in top_level_dirs(root):
        chat = top / tid
        folder = chat / "scratchpad"
        is_old = os.path.normcase(name) == old_key
        known = is_old or bool(HEX16_RE.fullmatch(name))
        if not known or (link and not is_old):
            if folder.is_dir():
                skipped.append((name, LINKED_TOP if link else UNKNOWN_LAYOUT))
            continue
        if not os.path.lexists(chat):
            continue
        for p in (chat, folder):
            if is_link_path(p):
                return None, None, f"{p} — ссылка на другое место; по ссылке не меряю и не убираю"
        if not folder.is_dir():
            continue
        try:
            folder.resolve().relative_to(top.resolve())
        except (ValueError, OSError):
            return None, None, f"папка {folder} выходит за пределы своего каталога {top}"
        found.append(Found(OLD_LAYOUT if is_old else NEW_LAYOUT, top, folder))
    found.sort(key=lambda f: (f.layout != OLD_LAYOUT, f.top.name.lower()))
    return found, skipped, None


def searched_words(root: Path, old_name: str) -> str:
    return (f"искал по номеру чата в {root}: каталог прежней раскладки {old_name} и каталоги "
            f"новой — из 16 шестнадцатеричных знаков")


def skipped_words(skipped) -> str:
    """Папки этого чата, которые НЕ мерены, — одной фразой; пусто, если таких нет."""
    if not skipped:
        return ""
    return ("папка этого чата есть ещё в " + ", ".join(f"{name} ({why})" for name, why in skipped)
            + " — не мерена и не убирается")


def load_reference_texts(con):
    """→ ([(вид, номер, текст)], [ошибки чтения]). Вид: card — открытая карточка, note — записка."""
    texts, errors = [], []
    open_cards = f"status NOT IN ({', '.join(repr(s) for s in CLOSED_STATUSES)})"
    try:
        for cid, title, body, done_when, blocked in con.execute(
                "SELECT id, title, body_md, done_when, blocked_reason FROM backlog "
                f"WHERE {open_cards}"):
            texts.append(("card", cid, "\n".join(x or "" for x in (title, body, done_when, blocked))))
    except sqlite3.Error as e:
        errors.append(f"карточки: {e}")
    try:
        for cid, body in con.execute(
                "SELECT e.backlog_id, e.body_md "
                "FROM backlog_events e JOIN backlog b ON b.id = e.backlog_id "
                f"WHERE b.{open_cards}"):
            texts.append(("card", cid, body or ""))
    except sqlite3.Error as e:
        errors.append(f"комментарии карточек: {e}")
    try:
        for mid, body in con.execute(
                "SELECT id, body_md FROM messages WHERE timestamp >= datetime('now', ?)",
                (f"-{NOTE_WINDOW_DAYS} days",)):
            texts.append(("note", mid, body or ""))
    except sqlite3.Error as e:
        errors.append(f"записки: {e}")
    return texts, errors


def reference_index(texts, names) -> dict:
    """имя подпапки (нижним регистром) → {(вид, номер)}. Правило ссылки — в шапке."""
    index: dict = {}
    plain = {n.lower() for n in names if PLAIN_NAME.fullmatch(n)}
    odd = [(n, re.compile(r"(?<![\w.\-\\/])" + re.escape(n) + r"(?![\w\-]|\.[\w\-])", re.IGNORECASE))
           for n in names if not PLAIN_NAME.fullmatch(n)]
    for kind, num, text in texts:
        for m in SCRATCH_WORD.finditer(text):
            window = text[m.end(): m.end() + REF_WINDOW]
            # «scratchpad/<имя>» и «…\scratchpad\<имя>»: звено сразу за словом — первое звено
            window = re.sub(r"^[\\/]+", " ", window)
            for t in REF_TOKEN.finditer(window):
                token = t.group(0).lower()
                for cand in {token, token.rstrip(".")}:
                    if cand in plain:
                        index.setdefault(cand, set()).add((kind, num))
            for n, rx in odd:
                if rx.search(window):
                    index.setdefault(n.lower(), set()).add((kind, num))
    return index


def refs_words(refs) -> str:
    def few(nums):
        nums = sorted(nums)
        head = ", ".join(f"#{n}" for n in nums[:3])
        return head + (f" и ещё {len(nums) - 3}" if len(nums) > 3 else "")
    cards = [n for k, n in refs if k == "card"]
    notes = [n for k, n in refs if k == "note"]
    parts = []
    if cards:
        parts.append(f"открытой карточке {few(cards)}")
    if notes:
        parts.append(f"записке {few(notes)}")
    return "упомянута в " + " · ".join(parts)


# ═══ РЕШЕНИЕ ПО ПОДПАПКЕ ═══════════════════════════════════════════════════════════════

@dataclass
class SubReport:
    name: str
    path: Path
    scan: TreeScan
    kind: str
    words: str


def decide(scan: TreeScan, refs, now: float):
    """→ (вид, слова). Сначала «оставить», потом отказы, остальное — «убрать»."""
    keep = []
    if refs:
        keep.append(refs_words(refs))
    if now - scan.last_edit < FRESH_SECONDS:
        keep.append("правка за последний час")
    if keep:
        return KEEP, "оставить: " + " · ".join(keep)
    if scan.is_link:
        return REFUSE, "отказ: ссылка на другое место"
    if scan.longest >= LONG_PATH:
        return REFUSE, (f"отказ: путь длиннее 260 знаков (самый длинный — {scan.longest} знаков "
                        f"UTF-16; предел Windows — 259 и завершающий ноль)")
    if scan.denied:
        return REFUSE, "отказ: нет доступа"
    if scan.unreadable:
        return REFUSE, f"отказ: не читается ({scan.unreadable[0][1]})"
    return REMOVE, "убрать"


def measure_folder(scratch: Path, index: dict, now: float):
    """→ (подпапки [SubReport], файлы корня TreeScan)."""
    reports = []
    root_files = TreeScan()
    with os.scandir(scratch) as it:
        entries = sorted(it, key=lambda e: e.name.lower())
    for entry in entries:
        path = Path(entry.path)
        if is_link_entry(entry):
            # ссылка верхнего уровня не мерится и не убирается никогда — свежесть ей не нужна
            scan = TreeScan(is_link=True, longest=u16len(entry.path))
        elif entry.is_dir(follow_symlinks=False):
            scan = scan_tree(path)
        else:
            try:
                st = os.stat(entry.path, follow_symlinks=False)
            except OSError:
                continue
            add_file(root_files, entry.path, st, at_root=True)
            continue
        kind, words = decide(scan, index.get(entry.name.lower(), set()), now)
        reports.append(SubReport(entry.name, path, scan, kind, words))
    return reports, root_files


def print_report(r: SubReport, now: float) -> None:
    print(f"  📁 {r.name} · {size_words(r.scan.size, r.scan.disk)} · правка {utc(r.scan.last_edit)} · "
          f"копий базы: {len(r.scan.copies)} (старше {OLD_COPY_DAYS} суток: {old_copies(r.scan, now)}) "
          f"· {r.words}")


# ═══ ПУТИ ═══════════════════════════════════════════════════════════════════════════════

def contour_dir_name(container: Path) -> str:
    """C:\\guts\\.atlas → C--guts--atlas: каждый знак, кроме латинских букв и цифр, — «-»."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(container))


def real_scratch_root() -> Path:
    return Path(tempfile.gettempdir()) / "claude"


def same_path(a: Path, b: Path) -> bool:
    def norm(p: Path) -> str:
        try:
            p = p.resolve()
        except OSError:
            pass
        return os.path.normcase(os.path.normpath(str(p)))
    return norm(a) == norm(b)


def scratch_root() -> Path:
    env = os.environ.get("MEZO_SCRATCH_ROOT")
    base = Path(env) if env else real_scratch_root()
    try:
        return base.resolve()
    except OSError:
        return base


def container_path() -> Path:
    c = Path(mezo_paths.container_root(__file__))
    try:
        return c.resolve()
    except OSError:
        return c


def threshold_bytes() -> float:
    raw = (os.environ.get("MEZO_SCRATCH_THRESHOLD_GB") or "").strip()
    if not raw:
        return THRESHOLD_GB * GB
    return float(raw.replace(",", ".")) * GB


def threshold_words() -> str:
    return f"порог «пора убрать» — больше {threshold_bytes() / GB:.2f} ГБ на диске"


# ═══ КОРЗИНА ════════════════════════════════════════════════════════════════════════════

@dataclass
class Trash:
    kind: str                 # experiment · send2trash · powershell
    words: str
    room: float | None        # свободно байт; None — без предела (опыт без вместимости)
    target: Path | None = None
    exe: str | None = None
    drive: str = ""


class RecycleInfo:
    """SHQUERYRBINFO — собирается при первом обращении: ctypes есть не везде."""
    cls = None

    @classmethod
    def make(cls):
        import ctypes
        from ctypes import wintypes
        if cls.cls is None:
            class Info(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_int64),
                            ("i64NumItems", ctypes.c_int64)]
            cls.cls = Info
        info = cls.cls()
        info.cbSize = ctypes.sizeof(info)
        return info


def bin_state(drive: str):
    """→ (предметов, байт) в корзине тома. Не узнать — исключение."""
    import ctypes
    info = RecycleInfo.make()
    hr = ctypes.windll.shell32.SHQueryRecycleBinW(drive, ctypes.byref(info))
    if hr != 0:
        raise OSError(f"занятость корзины тома {drive} не узнать (код {hr & 0xFFFFFFFF:#x})")
    return int(info.i64NumItems), int(info.i64Size)


def recycle_room(folder: Path):
    """Свободное место корзины тома папки → (байт, None) или (None, причина словами)."""
    try:
        import ctypes
        import winreg
    except ImportError as e:
        return None, f"не Windows ({e})"
    for hive_name, hive in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        try:
            with winreg.OpenKey(hive, POLICY_KEY) as k:
                for value in ("NoRecycleFiles", "RecycleBinSize"):
                    try:
                        v = winreg.QueryValueEx(k, value)[0]
                    except FileNotFoundError:
                        continue
                    if value == "NoRecycleFiles" and str(v).strip() in ("0", ""):
                        continue
                    return None, (f"задана политика {hive_name}\\…\\Policies\\Explorer {value}={v} — "
                                  f"корзина работает не по настройкам тома, и куда уйдёт папка, "
                                  f"не проверить")
        except FileNotFoundError:
            continue
        except OSError as e:
            return None, f"политики корзины ({hive_name}) не прочитаны ({e})"
    drive = folder.drive + "\\"
    buf = ctypes.create_unicode_buffer(64)
    if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive, buf, 64):
        return None, f"том {drive} не опознан"
    value = buf.value
    if "{" not in value or "}" not in value:
        return None, f"у тома {drive} нет опознавателя ({value})"
    guid = value[value.index("{"): value.index("}") + 1]
    key = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume\{guid}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            max_mb = int(winreg.QueryValueEx(k, "MaxCapacity")[0])
            try:
                nuke = int(winreg.QueryValueEx(k, "NukeOnDelete")[0])
            except FileNotFoundError:
                nuke = 0
    except OSError as e:
        return None, f"настройки корзины тома {drive} не прочитаны ({e})"
    if nuke:
        return None, f"корзина тома {drive} выключена (NukeOnDelete=1) — Windows стёр бы насовсем"
    try:
        _items, used = bin_state(drive)
    except OSError as e:
        return None, str(e)
    return max_mb * MB - used, None


def choose_trash(folder: Path):
    """→ (Trash, None) или (None, причина отказа). Мимо корзины — никогда."""
    trial = (os.environ.get("MEZO_TRASH_DIR") or "").strip()
    if trial:
        root_env = (os.environ.get("MEZO_SCRATCH_ROOT") or "").strip()
        if not root_env or same_path(Path(root_env), real_scratch_root()):
            return None, ("MEZO_TRASH_DIR задан, а корень черновых папок — настоящий "
                          f"({real_scratch_root()}): подмена корзины — только для опытов на "
                          "подменном корне MEZO_SCRATCH_ROOT; настоящие папки уехали бы мимо корзины")
        target = Path(trial).resolve()
        cap_raw = (os.environ.get("MEZO_TRASH_CAPACITY_MB") or "").strip()
        room = float(cap_raw.replace(",", ".")) * MB if cap_raw else None
        words = (f"🧪 ОПЫТ: вместо корзины Windows — каталог MEZO_TRASH_DIR={target} "
                 f"(только для опытов; корзина не используется)"
                 + (f" · вместимость подмены {cap_raw} МБ" if cap_raw else ""))
        return Trash("experiment", words, room, target=target), None
    room, why = recycle_room(folder)
    if room is None:
        return None, f"корзина не проверена: {why}"
    drive = folder.drive + "\\"
    try:
        import send2trash  # noqa: F401
        return Trash("send2trash", f"🗑 корзина Windows через send2trash · свободно {gb(room)}",
                     room, drive=drive), None
    except ImportError:
        pass
    for exe_name in ("powershell", "pwsh"):
        exe = shutil.which(exe_name)
        if not exe:
            continue
        try:
            r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", PS_PROBE],
                               capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            continue
        if NOT_INTERACTIVE in (r.stdout or ""):
            return None, (f"сеанс без рабочего стола ({exe_name}: Environment.UserInteractive = "
                          f"false) — DeleteDirectory удалил бы НАСОВСЕМ, мимо корзины")
        if r.returncode == 0 and "SendToRecycleBin" in (r.stdout or ""):
            return Trash("powershell", f"🗑 корзина Windows через {exe_name} "
                                       f"(Microsoft.VisualBasic, SendToRecycleBin) · свободно {gb(room)}",
                         room, exe=exe, drive=drive), None
    return None, ("ни один путь в корзину недоступен: нет пакета send2trash и нет PowerShell "
                  "со сборкой Microsoft.VisualBasic")


def trash_state(trash: Trash):
    """→ (предметов, байт на диске) в корзине — до и после переноса: папка обязана ДОЙТИ."""
    if trash.kind == "experiment":
        trash.target.mkdir(parents=True, exist_ok=True)
        with os.scandir(trash.target) as it:
            items = sum(1 for _ in it)
        return items, scan_tree(trash.target).disk
    return bin_state(trash.drive)


def arrived_words(before, after, disk: int):
    """None — папка дошла до корзины; иначе слова, почему похоже, что нет."""
    items0, size0 = before
    items1, size1 = after
    if items1 < items0 + 1:
        return f"предметов в корзине было {items0}, стало {items1}"
    if disk > 0 and size1 - size0 < disk * ARRIVAL_SHARE:
        return f"корзина выросла на {size1 - size0} байт, а папка занимала на диске {disk} байт"
    return None


def busy_words(src: Path):
    """Пробное переименование рядом и обратно. → None — папка свободна; иначе слова.

    Каталог не переименовывается, пока внутри открыт хоть один файл (замер проверки
    2026-10-02 ~23:44 UTC: отказ даже при общем доступе на чтение, запись и удаление).
    Оболочке такую папку отдавать нельзя: окно ошибки и частичный перенос."""
    probe = src.with_name(f"{src.name}.probe-{os.getpid()}")
    if os.path.lexists(probe):
        return f"рядом уже есть {probe.name} — пробное переименование не сделать"
    try:
        os.rename(src, probe)
    except OSError as e:
        return f"занята процессом (пробное переименование не прошло: {e.strerror or e})"
    try:
        os.rename(probe, src)
    except OSError as e:
        raise OSError(f"пробное переименование НЕ ВЕРНУЛОСЬ: папка сейчас называется "
                      f"{probe.name} — верни имя руками ({e})") from e
    return None


def move_to_trash(src: Path, trash: Trash) -> None:
    """Перенести папку в корзину (или в подменный каталог опыта). Не вышло — исключение."""
    if trash.kind == "experiment":
        trash.target.mkdir(parents=True, exist_ok=True)
        dest = trash.target / src.name
        n = 2
        while os.path.lexists(dest):
            dest = trash.target / f"{src.name}-{n}"
            n += 1
        # ⚖️ Только переименование, НЕ shutil.move: при отказе переименования (файл внутри
        # открыт, другой том) shutil.move молча переходит на «скопировать и стереть
        # исходник» — и стирает мимо всякой корзины то, что удалось стереть. Здесь отказ
        # переименования — отказ среды: уборка останавливается, папка остаётся на месте.
        os.rename(src, dest)
        if not dest.exists():
            raise OSError(f"в подменном каталоге папки нет: {dest}")
    elif trash.kind == "send2trash":
        from send2trash import send2trash
        send2trash(str(src))
    else:
        env = dict(os.environ, MEZO_RECYCLE_TARGET=str(src))
        r = subprocess.run([trash.exe, "-NoProfile", "-NonInteractive", "-Command", PS_RECYCLE],
                           capture_output=True, text=True, timeout=3600, env=env)
        if NOT_INTERACTIVE in (r.stdout or ""):
            raise OSError("сеанс без рабочего стола — DeleteDirectory удалил бы насовсем; не позван")
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout or "").strip() or f"код {r.returncode}")
    if src.exists():
        raise OSError("папка осталась на месте после переноса")


# ═══ РОЛЬ ══════════════════════════════════════════════════════════════════════════════

def role_sources(arg_role, con):
    """→ (роль или None, откуда, роль из MEZO_ROLE, роль по номеру чата, ошибка чтения ролей)."""
    env_role = (os.environ.get("MEZO_ROLE") or "").strip().upper() or None
    session = (os.environ.get(SESSION_ENV) or "").strip().lower()
    by_tid, err = roles_by_transcript(con)
    session_role = by_tid.get(session) if session else None
    if arg_role and arg_role.strip():
        return arg_role.strip().upper(), "--role", env_role, session_role, err
    if env_role:
        return env_role, "MEZO_ROLE", env_role, session_role, err
    if session_role:
        return session_role, f"номер чата {SESSION_ENV} в role_sessions", env_role, session_role, err
    return None, "", env_role, session_role, err


def foreign_role_words(role, env_role, session_role):
    for source, own in (("MEZO_ROLE", env_role),
                        (f"номер живого чата ({SESSION_ENV}) в role_sessions", session_role)):
        if own and own != role:
            return (f"⛔ ЧУЖАЯ ПАПКА: --role {role}, а {source} — {own}. Роль убирает только "
                    f"СВОЮ черновую папку; чужую не трогает никогда. Ничего не тронуто.")
    return None


NO_ROLE_WORDS = (f"роль не названа: нет --role, нет MEZO_ROLE, и номер чата {SESSION_ENV} "
                 f"в role_sessions не найден")


def owner_word_refusal(word):
    """→ None — слово владельца названо; иначе слова отказа."""
    word = (word or "").strip()
    if not word:
        return ("⛔ УБОРКА БЕЗ СЛОВА ВЛАДЕЛЬЦА НЕ ДЕЛАЕТСЯ: нужен --owner-word \"<дословно и час UTC "
                "слова владельца в этом чате>\". Постоянного разрешения нет — перед КАЖДОЙ уборкой "
                "вопрос с числами. Ничего не тронуто.")
    if not OWNER_WORD_TIME.search(word):
        return (f"⛔ В СЛОВЕ ВЛАДЕЛЬЦА НЕТ ЧАСА UTC: «{word}». Нужны дословный текст И час вида "
                f"«2026-10-03 09:00 UTC» — по нему слово сверяется с записью разговора. "
                f"Ничего не тронуто.")
    return None


# ═══ РЕЖИМЫ ════════════════════════════════════════════════════════════════════════════

def run_brief(args) -> int:
    """Одна строка, код 0 всегда. Любая беда — словами в той же строке."""
    try:
        line = brief_line(args)
    except SystemExit as e:
        text = str(e.code if e.code is not None else "").strip().splitlines()
        line = f"ℹ️ черновая папка: замер не сделан — {text[0] if text else 'отказ без слов'}"
    except Exception as e:  # noqa: BLE001 — строка общего прогона не вправе падать
        line = f"ℹ️ черновая папка: замер не сделан — {type(e).__name__}: {e}"
    print(line)
    return 0


def brief_line(args) -> str:
    db = Path(args.db) if args.db else mezo_paths.live_db(__file__)
    con = open_db(db)
    try:
        role, _src, _env, _sess, err = role_sources(args.role, con)
        if not role:
            return (f"ℹ️ черновая папка: {NO_ROLE_WORDS}" + (f" ({err})" if err else "")
                    + " — замер не сделан")
        tid, why = transcript_of(con, role)
    finally:
        con.close()
    if not tid:
        return f"ℹ️ черновая папка {role}: {why} — замер не сделан"
    root, old_name = scratch_root(), contour_dir_name(container_path())
    found, skipped, why = own_folders(root, old_name, tid)
    if found is None:
        return f"ℹ️ черновая папка {role}: {why} — замер не сделан"
    unmeasured = skipped_words(skipped)
    if not found:
        return (f"ℹ️ черновая папка {role}: папки нет ({searched_words(root, old_name)}) — "
                f"убирать нечего" + (f" · {unmeasured}" if unmeasured else ""))
    now = time.time()
    # время обхода делится между папками: каждой — равная доля ОСТАТКА, так что вторая не
    # остаётся без замера оттого, что первая велика, а недобранное первой достаётся второй
    t_end = time.monotonic() + BRIEF_BUDGET_S
    scans = []
    for i, f in enumerate(found):
        share = max(0.0, t_end - time.monotonic()) / (len(found) - i)
        scans.append(scan_tree(f.folder, deadline=time.monotonic() + share, exact=False))
    scan = merged(scans)
    old = old_copies(scan, now)
    root_old = old_root_copies(scan, now)
    more = "не меньше " if scan.truncated else ""
    parts = [f"черновая папка {role}: {more}{size_words(scan.size, scan.disk, approx=True)}"]
    if len(found) > 1:
        parts.append(f"СУММА по {len(found)} папкам чата: " + " + ".join(
            f"{f.layout} {size_words(s.size, s.disk, approx=True)}" for f, s in zip(found, scans)))
    else:
        parts.append(found[0].layout)
    parts.append(f"копий базы старше {OLD_COPY_DAYS} суток: {more}{old}"
                 + (f", из них в корне папки {root_old} (их этот инструмент не убирает)" if root_old else ""))
    if unmeasured:
        parts.append(unmeasured)
    alarm = False
    if scan.disk > threshold_bytes():
        parts.append(f"пора убрать: {more}≈{gb(scan.disk)} ({threshold_words()})")
        alarm = True
    if old:
        parts.append(f"копии базы старше {OLD_COPY_DAYS} суток лежат (в записках ленты пароли)")
        alarm = True
    if scan.truncated:
        parts.append(f"замер оборван через {BRIEF_BUDGET_S:.0f} с — папка велика")
    if alarm or scan.truncated or unmeasured:
        parts.append(f"разбор и уборка по слову владельца: python {SELF.as_posix()} --role {role}")
    mark = "⚠️" if alarm else "ℹ️"
    return mark + " " + " · ".join(parts)


def run_contour(args) -> int:
    t0 = time.monotonic()
    db = Path(args.db) if args.db else mezo_paths.live_db(__file__)
    con = open_db(db)
    try:
        owners, roles_err = roles_by_transcript(con)
        history = history_by_transcript(con)
    finally:
        con.close()
    if roles_err:
        print(f"⚪ не проверено: роли не читаются ({roles_err}) — без них каждый чат вышел бы "
              f"«закрытым», и сводка звала бы убирать папки живых ролей. Сводка не печатается.")
        return 2
    root, old_name = scratch_root(), contour_dir_name(container_path())
    if not root.is_dir():
        print(f"⛔ корня черновых папок нет: {root} — его даёт TEMP или MEZO_SCRATCH_ROOT: "
              f"приложение здесь папок ещё не создавало, либо путь неверен")
        return 2
    contour = root / old_name
    now = time.time()
    rows, links = [], []
    empty = 0

    def take(chat_dir: Path, layout: str) -> None:
        nonlocal empty
        sp = chat_dir / "scratchpad"
        if is_link_path(chat_dir) or is_link_path(sp):
            links.append(f"{chat_dir.parent.name}\\{chat_dir.name}")
            return
        if not sp.is_dir():
            return
        scan = scan_tree(sp, exact=False)
        if scan.size == 0 and not scan.files and not scan.denied and not scan.unreadable:
            empty += 1
            return
        rows.append((scan, chat_dir.name, owners.get(chat_dir.name.lower()), layout))

    # прежняя раскладка: каталог назван по пути контура — в нём ВСЕ чаты контура
    if contour.is_dir():
        for d in sorted(contour.iterdir(), key=lambda p: p.name.lower()):
            take(d, OLD_LAYOUT)
    # новая раскладка: чей каталог из 16 знаков, по имени не узнать — берём только чаты,
    # которые знает база контура, а папки остальных чатов рядом с ними называем числом
    known_ids = {k for k in list(owners) + list(history) if UUID_RE.fullmatch(k)}
    new_tops, strangers = [], 0
    for top_name, top, link in top_level_dirs(root):
        if link or not HEX16_RE.fullmatch(top_name):
            continue
        try:
            with os.scandir(top) as it:
                chats = sorted((e.name for e in it), key=str.lower)
        except OSError:
            continue
        ours = [c for c in chats if c.lower() in known_ids]
        if not ours:
            continue
        new_tops.append(top_name)
        for c in ours:
            take(top / c, NEW_LAYOUT)
        strangers += sum(1 for c in chats if c.lower() not in known_ids
                         and (top / c / "scratchpad").is_dir())
    print(f"🗂 СВОДКА ЧЕРНОВЫХ ПАПОК КОНТУРА — только замер, ничего не меняет")
    print(f"   корень: {root}")
    print(f"   {OLD_LAYOUT} — каталог {old_name}: "
          + ("все чаты" if contour.is_dir() else "каталога нет"))
    print(f"   {NEW_LAYOUT} — каталоги из 16 шестнадцатеричных знаков: только чаты, которые знает "
          f"база контура (живые роли и история адресов); найдены в: "
          f"{', '.join(new_tops) if new_tops else 'нигде'}")
    print(f"   размеры ≈: жёсткие ссылки сверены у файлов от {DEDUPE_MIN / MB:g} МБ")
    live, closed = [], []
    old_total = 0
    for scan, name, role, layout in sorted(rows, key=lambda r: -r[0].disk):
        old = old_copies(scan, now)
        owner = f"роль {role} (живой чат)" if role else CLOSED_CHAT
        if not role and history.get(name.lower()):
            owner += f" · прежде был чатом {history[name.lower()]} (история адресов)"
        notes = []
        if scan.longest >= LONG_PATH:
            notes.append(f"есть путь длиннее 260 знаков ({scan.longest})")
        if scan.denied:
            notes.append(f"нет доступа: {len(scan.denied)}")
        print(f"  {size_words(scan.size, scan.disk, approx=True):>10} · {name} · {layout} · {owner} · "
              f"копий базы старше {OLD_COPY_DAYS} суток: {old}"
              + (" · " + " · ".join(notes) if notes else ""))
        old_total += old
        (live if role else closed).append(scan)
    if links:
        print(f"   не мерены — каталог чата или scratchpad сами ссылка на другое место: {', '.join(links)}")
    if new_tops:
        print(f"   в каталогах новой раскладки рядом с чатами контура лежит папок чатов, которых "
              f"база не знает: {strangers} — не мерены: чьи они, по имени каталога не узнать")
    print(f"ИТОГ: папок {len(rows)} · всего ≈{gb(disk_size(live + closed))} · у живых чатов ролей "
          f"≈{gb(disk_size(live))} · у закрытых чатов ≈{gb(disk_size(closed))} · копий базы старше "
          f"{OLD_COPY_DAYS} суток: {old_total} · пустых папок не перечислено: {empty} · замер "
          f"{time.monotonic() - t0:.0f} с")
    print("   уборка закрытых чатов — отдельной работой по слову владельца (рукой COORD); "
          "свою папку каждая роль убирает сама — тоже только по слову владельца")
    return 0


def run_folder(args) -> int:
    """Замер своей папки, а с --apply — уборка «убрать» в корзину."""
    t0 = time.monotonic()
    live_db = mezo_paths.live_db(__file__)
    if args.apply and args.db and not same_path(Path(args.db), live_db):
        print(f"⛔ --apply — только с живой базой контура ({live_db}), а названа {args.db}: ссылки "
              f"и номер чата из другой базы не про этот контур. Ничего не тронуто.")
        return 2
    db = Path(args.db) if args.db else live_db
    con = open_db(db)
    try:
        role, source, env_role, session_role, roles_err = role_sources(args.role, con)
        if not role:
            print(f"⛔ {NO_ROLE_WORDS}" + (f" ({roles_err})" if roles_err else "")
                  + ". Назови: --role <РОЛЬ> или MEZO_ROLE=<РОЛЬ>")
            return 2
        if args.apply:
            foreign = foreign_role_words(role, env_role, session_role)
            if foreign is not None:
                print(foreign)
                return 2
            if not env_role and not session_role:
                print(f"⛔ НЕ ЗНАЮ, ЧЕЙ ЭТО ЧАТ: нет MEZO_ROLE, и номер живого чата ({SESSION_ENV}) "
                      f"в role_sessions не найден" + (f" ({roles_err})" if roles_err else "")
                      + f". Убирается только СВОЯ папка, а свою я не узнал — --role {role} один "
                      f"этого не доказывает. Назови MEZO_ROLE={role} в своём чате. Ничего не тронуто.")
                return 2
        tid, why = transcript_of(con, role)
        if not tid:
            print(f"⛔ {why} — папку роли не найти")
            return 2
        texts, ref_errors = load_reference_texts(con)
    finally:
        con.close()

    root, old_name = scratch_root(), contour_dir_name(container_path())
    found, skipped, why = own_folders(root, old_name, tid)
    if found is None:
        print(f"⛔ черновая папка роли {role}: {why}. Ничего не тронуто.")
        return 2
    if len(found) == 1:
        head = str(found[0].folder)
    elif found:
        head = f"папок {len(found)} — меряю каждую, итог — СУММА"
    else:
        head = "папки нет"
    print(f"🗂 черновая папка роли {role} (роль — {source}): {head}")
    print(f"   номер живого чата (transcript_id из role_sessions): {tid}")
    if not root.is_dir():
        print(f"⛔ корня черновых папок нет: {root} — его даёт TEMP или MEZO_SCRATCH_ROOT: "
              f"приложение здесь папок ещё не создавало, либо путь неверен")
        return 2
    for f in found:
        print(f"   📂 {f.layout}: {f.folder}")
    if skipped:
        print(f"ℹ️ {skipped_words(skipped)}")
    if not found:
        print(f"   {searched_words(root, old_name)}")
        print("   папки нет — убирать нечего (чат ещё ничего не клал в черновую папку)")
        return 0
    if ref_errors:
        print("⚠️ ссылки не прочитаны: " + " · ".join(ref_errors))
        if args.apply:
            print("⛔ без ссылок не знаю, что нужно живому делу — уборка не начата, ничего не тронуто")
            return 2

    now = time.time()
    names = sorted({e.name for f in found for e in os.scandir(f.folder)})
    index = reference_index(texts, names)
    # каждая папка меряется отдельно; дальше всё — по ВСЕМ папкам чата вместе
    measured = [(f, *measure_folder(f.folder, index, now)) for f in found]
    reports = [r for _f, reps, _rf in measured for r in reps]
    root_files = merged([rf for _f, _reps, rf in measured])

    cards = {n for k, n, _t in texts if k == "card"}
    notes = sum(1 for k, _n, _t in texts if k == "note")
    mentioned = sorted(r.name for r in reports if r.name.lower() in index)
    print(f"   ссылки искались: открытых карточек {len(cards)} (заголовок, тело, срок, причина "
          f"блокировки, комментарии) · записок за {NOTE_WINDOW_DAYS} суток {notes} · упомянуты "
          f"подпапки: {', '.join(mentioned) if mentioned else 'нет'}")

    all_scans = [r.scan for r in reports] + [root_files]
    total_names = sum(s.size for s in all_scans)
    total_disk = disk_size(all_scans)
    rm = [r.scan for r in reports if r.kind == REMOVE]
    root_old = old_root_copies(root_files, now)
    old_total = sum(old_copies(r.scan, now) for r in reports) + old_copies(root_files, now)
    refusals = [r for r in reports if r.kind == REFUSE]
    print(f"   размер: {size_words(total_names, total_disk)} · подпапок: {len(reports)} · файлов в "
          f"корне: {root_files.files} ({gb(root_files.disk)}; файлы корня не убираются)")
    if not args.apply:
        print("   это ЗАМЕР — ничего не меняет; уборка только по слову владельца в этом чате: "
              "--apply --owner-word \"<дословно и час UTC>\"")
    print("")
    parts_words = []
    for f, reps, rf in measured:
        own = [r.scan for r in reps] + [rf]
        own_words = size_words(sum(s.size for s in own), disk_size(own))
        parts_words.append(f"{f.layout} {own_words}")
        if len(found) > 1:
            print(f"  ── {f.layout}: {own_words} · подпапок: {len(reps)} · файлов в корне: "
                  f"{rf.files} · {f.folder}")
        for r in sorted(reps, key=lambda x: (-x.scan.disk, x.name.lower())):
            print_report(r, now)
    print("")
    print(f"ИТОГ: всего {size_words(total_names, total_disk)} · к уборке "
          f"{size_words(sum(s.size for s in rm), disk_size(rm))} · копий базы старше "
          f"{OLD_COPY_DAYS} суток: {old_total}"
          + (f" (из них в корне папки {root_old} — их этот инструмент не убирает)" if root_old else ""))
    if len(found) > 1:
        print(f"   итог — СУММА по {len(found)} папкам чата: " + " + ".join(parts_words))
    print(f"   {threshold_words()} · копия базы старше {OLD_COPY_DAYS} суток — второй порог")
    if root_files.root_copies:
        print(f"   в корне папки копий базы: {len(root_files.root_copies)}, из них старше "
              f"{OLD_COPY_DAYS} суток: {root_old} — этот инструмент их НЕ убирает (только "
              f"подпапки); назови владельцу:")
        for name, size, mtime in sorted(root_files.root_copies.values(), key=lambda x: x[0].lower()):
            print(f"     🗄 {name} · {gb(size)} · правка {utc(mtime)}")
    if total_disk > threshold_bytes():
        print(f"⚠️ пора убрать: {gb(total_disk)}")
    if old_total:
        print(f"⚠️ копий базы старше {OLD_COPY_DAYS} суток: {old_total}")
    if refusals:
        print(f"⛔ отказы — не уберутся, не обходятся ({len(refusals)}):")
        for r in refusals:
            print(f"   {r.name} · {gb(r.scan.disk)} · {r.words}")

    if not args.apply:
        if total_disk > threshold_bytes() or old_total:
            print("👉 уборка — только по слову владельца в этом чате, перед КАЖДОЙ уборкой: "
                  "вопрос с числами (что убираю · сколько ГБ · что оставляю)")
        print(f"   замер {time.monotonic() - t0:.1f} с")
        return 0
    return apply_cleanup(args, reports, [f.folder for f in found], now)


def apply_cleanup(args, reports, folders, now: float) -> int:
    drives = sorted({f.drive.lower() for f in folders})
    if len(drives) > 1:
        print(f"⛔ УБОРКА НЕ НАЧАТА: папки чата лежат на разных томах ({', '.join(drives)}) — "
              f"корзина у каждого тома своя, и место одной сверкой не проверить. Ничего не тронуто.")
        return 2
    trash, why = choose_trash(folders[0])
    if trash is None:
        print(f"⛔ УБОРКА НЕ НАЧАТА: {why}. Ничего не тронуто.")
        return 2
    print("")
    print(trash.words)
    print(f"   слово владельца: «{(args.owner_word or '').strip()}»")
    room = trash.room
    moved, refused, stopped = [], [r for r in reports if r.kind == REFUSE], None
    for r in [x for x in reports if x.kind == REMOVE]:
        # перед переносом — перемер: подпапка могла ожить или стать отказом за время уборки
        again = scan_tree(r.path)
        kind, words = decide(again, set(), time.time())
        if kind == KEEP:
            print(f"   ↩ {r.name}: перед переносом — {words}; оставлена")
            continue
        if kind == REFUSE:
            r.words = f"перед переносом — {words}"
            refused.append(r)
            continue
        if room is not None and again.size * TRASH_MARGIN > room:
            r.words = (f"отказ: не влезает в корзину (свободно {gb(max(room, 0))}) — Windows "
                       f"стёр бы её насовсем или вытеснил старое из корзины")
            refused.append(r)
            continue
        try:
            busy = busy_words(r.path)
            if busy is not None:
                raise OSError(busy)
            before = trash_state(trash)
            move_to_trash(r.path, trash)
            after = trash_state(trash)
        except Exception as e:  # noqa: BLE001 — отказ среды: остановка, а не обход
            stopped = (r, str(e))
            break
        lost = arrived_words(before, after, again.disk)
        if lost is not None:
            stopped = (r, f"⛔ ПОХОЖЕ, УШЛА МИМО КОРЗИНЫ: на месте её нет, а {lost}. Проверь "
                          f"корзину руками и скажи владельцу немедленно")
            break
        if room is not None:
            room -= again.size
        moved.append((r, again))
        print(f"   ➜ в корзину: {r.name} · {size_words(again.size, again.disk)}")
    print("")
    print(f"ИТОГ УБОРКИ: перенесено {len(moved)} папок, "
          f"{size_words(sum(a.size for _r, a in moved), disk_size([a for _r, a in moved]))} · "
          f"оставлено {sum(1 for r in reports if r.kind == KEEP)} · отказов {len(refused)}"
          + (" · УБОРКА ОСТАНОВЛЕНА отказом среды" if stopped else ""))
    if refused:
        print("⛔ отказы — не тронуты, назови владельцу:")
        for r in refused:
            print(f"   {r.name} · {gb(r.scan.disk)} · {r.words}")
    if stopped:
        r, e = stopped
        print(f"⛔ ОСТАНОВКА: отказ среды на папке {r.name} · {gb(r.scan.disk)} — {e}")
        print("   остальные папки не тронуты; разберись с причиной и спроси владельца заново")
    print("   корзину очищает только владелец")
    return 1 if (refused or stopped) else 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        description="Черновая папка роли: замер (по умолчанию), уборка в корзину по слову "
                    "владельца (--apply --owner-word), сводка по контуру (--contour), "
                    "строка для общего прогона (--brief).")
    ap.add_argument("--role", help="роль (по умолчанию MEZO_ROLE, затем номер чата в role_sessions)")
    ap.add_argument("--db", help="база контура (по умолчанию живая); открывается только на чтение; "
                                 "с --apply — только живая")
    ap.add_argument("--apply", action="store_true",
                    help="убрать подпапки с решением «убрать» в корзину — только со словом владельца")
    ap.add_argument("--owner-word", help="дословно и час UTC (вида 2026-10-03 09:00 UTC) слова "
                                         "владельца в своём чате")
    ap.add_argument("--contour", action="store_true",
                    help="сводка по всем черновым папкам контура (для COORD), только замер")
    ap.add_argument("--brief", action="store_true",
                    help="одна строка для общего прогона проверок, код 0 всегда")
    args = ap.parse_args()

    if args.contour and args.apply:
        print("⛔ --apply с --contour не поддерживается: уборка закрытых чатов — отдельной работой "
              "по слову владельца. Ничего не тронуто.")
        return 2
    if args.brief and (args.apply or args.contour):
        print("⛔ --brief — только замер своей папки; с --apply и --contour не сочетается")
        return 2
    if args.apply:
        refusal = owner_word_refusal(args.owner_word)
        if refusal is not None:
            print(refusal)
            return 2
    if args.brief:
        return run_brief(args)
    try:
        threshold_bytes()
    except ValueError:
        print(f"⛔ MEZO_SCRATCH_THRESHOLD_GB не число: {os.environ.get('MEZO_SCRATCH_THRESHOLD_GB')!r}")
        return 2
    if args.contour:
        return run_contour(args)
    return run_folder(args)


if __name__ == "__main__":
    sys.exit(main())
