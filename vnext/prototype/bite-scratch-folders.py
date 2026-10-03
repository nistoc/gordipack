# -*- coding: utf-8 -*-
r"""ПРИЁМКА scratch-folders.py — правило «черновые папки роли» (решение владельца
≤2026-10-02 22:55 UTC «Без постоянного разрешения», записки #5438 · #5439).

ГДЕ ИДЁТ. ТОЛЬКО на песочнице: копия базы (mezo_stand.snapshot_db) с подставными ролями
и их transcript_id в role_sessions, подставной корень черновых папок MEZO_SCRATCH_ROOT
с деревом подпапок и подставная корзина MEZO_TRASH_DIR. Корзина Windows не используется
НИ В ОДНОМ вызове: каждый вызов инструмента получает MEZO_TRASH_DIR внутри песочницы, и
приёмка отказывается звать инструмент, если корень или подменная корзина вне песочницы.
Живая база не открывается на запись: снимок снимается строго на чтение. Для случаев
«в базе нет таблицы/колонки» (⑳ ㉑) строятся маленькие базы с нужной нехваткой — их
предмет именно нехватка, а не содержимое.

СЛУЧАИ (каждый — свой вызов на своём дереве, у каждого свой встречный):
  ① замер ничего не меняет: отпечаток дерева (пути · размеры · час правки) до и после
     равен; в дереве копия базы в режиме WAL — у неё открытие с одним mode=ro оставило бы
     рядом -shm/-wal (замер 2026-10-02 ~23:09 UTC)
  ② копия базы 8 суток назад при дереве меньше 2 ГБ → названа вторым порогом, «пора
     убрать» нет, назван действующий порог 2 ГБ; встречные: копия 6 суток назад считается
     копией, но не старой; порог, подменённый MEZO_SCRATCH_THRESHOLD_GB, называет «пора убрать»
  ③ ссылки ОТКРЫТЫХ карточек → «оставить» со ссылкой #N: комментарий (полный путь), тело
     («scratchpad/<имя>»), живые формы контура «scratchpad <имя>/» и «scratchpad <РОЛЬ>
     <имя>/» (карточка в статусе blocked); встречные: закрытая карточка (done, dropped) →
     «убрать»; имя вторым звеном пути («scratchpad <РОЛЬ> <имя>/<другое>/») → «убрать»
  ④ правка 10 и 50 минут назад → «оставить: правка за последний час»; правка файла в
     глубине (каталоги — 2 часа назад) и дописывание в открытый файл (запись каталога
     отстала на 2 часа) → тоже «оставить»; встречный: 2 часа назад → «убрать»
  ⑤ путь ровно 260 знаков и путь в 258 знаков Python, но 261 знак UTF-16 (эмодзи) →
     «отказ», назван с размером, при --apply не тронут; встречный: путь 259 знаков →
     убран; код 1 (ФС не даёт создать такой путь — «не проверено», код 2, без подделки)
  ⑥ --apply без --owner-word, с пустым, из пробелов и без часа UTC («.») → код 2, дерево не тронуто
  ⑦ --apply со словом владельца → «убрать» уехала в MEZO_TRASH_DIR, «оставить» на месте,
     подмена корзины сказана вслух, слово владельца повторено
  ⑧ --role чужой роли при MEZO_ROLE своей → «ЧУЖАЯ ПАПКА»; без MEZO_ROLE и без номера
     чата, а также с номером чата, которого нет в role_sessions → «НЕ ЗНАЮ, ЧЕЙ ЭТО ЧАТ»;
     всё — код 2, чужое дерево не тронуто; встречный: та же роль в MEZO_ROLE — уборка идёт
  ⑨ мусор с именем mezosync.db и SQLite без таблицы messages копиями базы не считаются
  ⑩ --brief — одна строка и код 0: с папкой (и порогом), без роли, без transcript_id, без папки
  ⑪ --contour: папка закрытого чата — «закрытый чат, роли нет» (с подсказкой из истории
     адресов), живого — с ролью; --contour --apply → код 2 словами, дерево не тронуто
  ⑫ записки 1 и 6 суток назад берегут подпапку; встречные — записка 8 суток назад и
     имя-приставка («…-n1» при ссылке на «…-n12»)
  ⑬ роль по номеру чата (CLAUDE_CODE_SESSION_ID → role_sessions): узнана замером и
     строкой; чужой номер → «роль не названа» (замер — код 2, строка — код 0); при --apply
     номер чата другой роли → отказ
  ⑭ папка больше свободного места корзины (подмена MEZO_TRASH_CAPACITY_MB) → «отказ: не
     влезает в корзину», сосед убран, код 1
  ⑮ папка занята процессом (файл внутри открыт) → пробное переименование называет её
     занятой, остановка ВСЕЙ уборки на ней, её файлы и следующая папка на месте, код 1
  ⑯ жёсткая ссылка: файл 20 МиБ под двумя именами — на диске 20.0 МБ, по именам 40.0 МБ
     (замер, итог и строка --brief); заодно размер меньше 0,1 ГБ печатается в МБ, а не
     «0.02 ГБ» (замечание приёмки OPSSRE, записка #5451)
  ⑰ копия базы в КОРНЕ папки (10 суток) — посчитана в итоге и строке --brief, названа
     списком отдельно, этим инструментом не убирается
  ⑱ номер чата в базе не похож на номер чата («..\esc18») и scratchpad — ссылка на чужой
     каталог → код 2, ничего за пределами контура не тронуто
  ⑲ ссылки внутри папки: ссылка верхнего уровня → «отказ: ссылка на другое место» и на
     месте; подпапка со ссылкой внутри убрана, а цели обеих ссылок целы
  ⑳ --contour при базе, где role_sessions без transcript_id → код 2 «не проверено», а не
     «все чаты закрытые»
  ㉑ --apply при базе без backlog_events (ссылки не прочитать) → код 2; --apply с --db не
     живой базы контура → код 2; дерево не тронуто
  ㉒ проверка прихода в корзину (та же функция судит настоящую корзину): выросли и
     предметы, и место → пришла; не выросло число предметов или место → «мимо корзины»

НАРОЧНЫЕ ПОЛОМКИ (--break <имя>) — словарь BREAKS, ожидаемые провалы каждой записаны ДО
прогона в BREAK_FAILS; прогон с --break печатает ожидание до случаев и сверяет с фактом
после. Строка ИТОГ считает покрытие случаев поломками из того же словаря.

⛔ ЧЕГО ЭТА ПРИЁМКА НЕ ПОКРЫВАЕТ — названо, чтобы молчание не читалось как «проверено»:
  · настоящая корзина Windows (send2trash и PowerShell с SendToRecycleBin), чтение её
    вместимости и занятости, проверка сеанса без рабочего стола и политик NoRecycleFiles /
    RecycleBinSize — в опытах корзина запрещена; путь проверен подменой MEZO_TRASH_DIR /
    MEZO_TRASH_CAPACITY_MB, а суждение о приходе — случаем ㉒ на той же функции;
  · отказ MEZO_TRASH_DIR при настоящем корне %TEMP%\claude — испытать его значило бы
    позвать --apply на настоящем корне, а это запрещено;
  · «отказ: нет доступа» — сделать папку недоступной без правки прав Windows нельзя,
    а права в опытах не трогаем;
  · подпапка, ставшая отказом между замером и уборкой (одна уборка — один процесс, вклиниться
    между ними снаружи нельзя без гонки);
  · «переименование, НЕ shutil.move» в подменной корзине: с пробным переименованием любое
    условие, при котором не прошёл бы перенос, раньше не даёт пройти пробе (открытый файл),
    а гонка между пробой и переносом не воспроизводится;
  · скорость --brief на настоящей папке роли (у песочницы дерево крошечное) и время
    --contour по всему контуру — меряются замером на живых папках, не здесь.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

CASES = DIFFER = GREENS = 0
RUN_IDS = []      # номера прогнанных случаев по порядку (первое слово заголовка)
FAILED = []       # номера провалившихся — для сверки с заранее названным ожиданием поломки
SKIPPED = []      # номера, которые мерить не удалось («не проверено»)
SANDBOX: Path | None = None
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
DAY = 86400
MIB = 1024 * 1024


def case(title, verdict, detail, differ=True):
    global CASES, DIFFER, GREENS
    CASES += 1
    DIFFER += bool(differ)
    GREENS += bool(verdict)
    number = title.split()[0]
    RUN_IDS.append(number)
    if not verdict:
        FAILED.append(number)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def unmeasured(title, reason):
    SKIPPED.append(title.split()[0])
    print(f"⚪ {title}")
    print(f"   не проверено: {reason}")


# 🧪 НАРОЧНЫЕ ПОЛОМКИ в КОПИИ инструмента. Искомое место обязано встретиться ровно один раз,
# иначе прогон отказывает кодом 2 «поломка не легла» — поправить приёмку, а не инструмент.
BREAKS = {
    "measure-changes-tree": (
        '"?mode=ro&immutable=1"',
        '"?mode=ro"',
        "«замер меняет дерево»: копия базы открывается одним mode=ro, без immutable=1 — у копии "
        "в режиме WAL рядом остаются -shm/-wal и сдвигается час правки каталога"),
    "copy-age-ignored": (
        "for m in scan.copies.values() if now - m > OLD_COPY_DAYS * 86400)",
        "for m in scan.copies.values() if now - m > OLD_COPY_DAYS * 86400 * 1000)",
        "возраст копии базы не мерится: старых копий не бывает никогда"),
    "copy-age-9": (
        "OLD_COPY_DAYS = 7 ",
        "OLD_COPY_DAYS = 9 ",
        "копия базы старая только с 9 суток вместо 7"),
    "threshold-200": (
        "THRESHOLD_GB = 2.0 ",
        "THRESHOLD_GB = 200.0 ",
        "порог «пора убрать» 200 ГБ вместо 2"),
    "card-ref-unread": (
        '"FROM backlog_events e JOIN backlog b ON b.id = e.backlog_id "',
        '"FROM backlog_events e JOIN backlog b ON 0 AND b.id = e.backlog_id "',
        "«ссылка карточки не читается»: комментарии открытых карточек не смотрятся"),
    "ref-live-forms": (
        "            window = text[m.end(): m.end() + REF_WINDOW]",
        r'            window = (re.match(r"[\\/]+[\w.\-]*", text[m.end():]) or re.match("", "")).group(0)',
        "ссылкой считается только «scratchpad/<имя>» вплотную — живые формы «scratchpad <имя>/» "
        "и «scratchpad <РОЛЬ> <имя>/» не видны"),
    "open-cards-narrow": (
        "    open_cards = f\"status NOT IN ({', '.join(repr(s) for s in CLOSED_STATUSES)})\"",
        "    open_cards = \"status IN ('open', 'in_progress')\"",
        "открытыми считаются только open и in_progress (blocked/in_review/awaiting_word — закрыты)"),
    "fresh-not-kept": (
        "    if now - scan.last_edit < FRESH_SECONDS:",
        "    if False and now - scan.last_edit < FRESH_SECONDS:",
        "«свежая правка не бережётся»: правка за последний час ничего не оставляет"),
    "fresh-15min": (
        "FRESH_SECONDS = 3600 ",
        "FRESH_SECONDS = 900 ",
        "свежесть 15 минут вместо часа"),
    "mtime-top-only": (
        "            if mtime > scan.last_edit:",
        "            if False and mtime > scan.last_edit:",
        "час правки — только у самой подпапки, правки в глубине не видны"),
    "dirent-mtime": (
        "            mtime = st.st_mtime",
        "            mtime = dst.st_mtime",
        "час правки из записи каталога: дописывание в открытый файл не видно"),
    "long-path-not-refused": (
        "    if scan.longest >= LONG_PATH:\n        return REFUSE",
        "    if False and scan.longest >= LONG_PATH:\n        return REFUSE",
        "«длинный путь не отказывает»: папка с путём от 260 знаков идёт в уборку"),
    "long-path-300": (
        "LONG_PATH = 260 ",
        "LONG_PATH = 300 ",
        "предел длины пути поднят до 300"),
    "long-path-gt": (
        "    if scan.longest >= LONG_PATH:\n        return REFUSE",
        "    if scan.longest > LONG_PATH:\n        return REFUSE",
        "отказ только с 261 знака: путь ровно 260 знаков идёт в уборку"),
    "utf16-ignored": (
        '    return len(s.encode("utf-16-le", "surrogatepass")) // 2',
        "    return len(s)",
        "длина пути в знаках Python, а не UTF-16: эмодзи считается за один знак"),
    "apply-without-word": (
        "        if refusal is not None:",
        "        if False:",
        "«--apply без слова владельца проходит»"),
    "owner-word-no-time": (
        "    if not OWNER_WORD_TIME.search(word):",
        "    if False:",
        "слово владельца без часа UTC проходит"),
    "trash-skipped": (
        "        os.rename(src, dest)",
        "        pass  # ПОЛОМКА: перенос не делается",
        "перенос в подменную корзину не делается (проверка после переноса это называет "
        "отказом среды и останавливает уборку)"),
    "foreign-role": (
        "            if foreign is not None:",
        "            if False and foreign is not None:",
        "«чужая роль проходит»: --apply не сверяет --role ни с MEZO_ROLE, ни с номером чата"),
    "unknown-chat-proceeds": (
        "            if not env_role and not session_role:",
        "            if False:",
        "--apply при неузнанной своей роли проходит: --role любой роли без MEZO_ROLE и номера чата"),
    "copy-by-name": (
        "    if size < MIN_DB_SIZE or size % DB_PAGE_MIN:",
        '    return Path(path).name.lower() == "mezosync.db"\n'
        "    if size < MIN_DB_SIZE or size % DB_PAGE_MIN:",
        "«копия базы по имени файла»: копией считается файл с именем mezosync.db"),
    "header-only": (
        "    return has_messages_table(path)",
        "    return True",
        "копия базы по одному заголовку SQLite, без таблицы messages"),
    "brief-multiline": (
        '    return mark + " " + " · ".join(parts)',
        '    return mark + " " + "\\n".join(parts)',
        "--brief печатает части строки отдельными строками"),
    "closed-chat-claimed": (
        '        owner = f"роль {role} (живой чат)" if role else CLOSED_CHAT',
        '        owner = f"роль {role or \'COORD\'} (живой чат)"',
        "сводка контура приписывает папку закрытого чата роли"),
    "note-ref-unread": (
        "\"SELECT id, body_md FROM messages WHERE timestamp >= datetime('now', ?)\"",
        "\"SELECT id, body_md FROM messages WHERE 0 AND timestamp >= datetime('now', ?)\"",
        "записки за 7 суток не смотрятся"),
    "prefix-match": (
        '                for cand in {token, token.rstrip(".")}:',
        "                for cand in [p for p in plain if token.startswith(p)]:",
        "имя подпапки сверяется приставкой, а не целиком"),
    "note-window-2": (
        "NOTE_WINDOW_DAYS = 7 ",
        "NOTE_WINDOW_DAYS = 2 ",
        "записки берегут только 2 суток вместо 7"),
    "session-role-unknown": (
        "    session_role = by_tid.get(session) if session else None",
        "    session_role = None",
        "номер живого чата не узнаёт роль"),
    "capacity-unchecked": (
        "        if room is not None and again.size * TRASH_MARGIN > room:",
        "        if False and room is not None and again.size * TRASH_MARGIN > room:",
        "свободное место корзины не сверяется"),
    "env-stop-continues": (
        "            stopped = (r, str(e))\n            break",
        "            stopped = (r, str(e))\n            continue",
        "отказ среды не останавливает уборку — следующие папки уезжают"),
    "busy-not-probed": (
        "            busy = busy_words(r.path)",
        "            busy = None",
        "занятость папки не проверяется пробным переименованием до переноса"),
    "hardlinks-twice": (
        "    if st.st_nlink > 1:",
        "    if False and st.st_nlink > 1:",
        "жёсткая ссылка считается по каждому имени: место на диске завышено"),
    "small-size-in-gb": (
        "    if size < GB // 10:",
        "    if False and size < GB // 10:",
        "размер меньше 0,1 ГБ печатается в ГБ («0.02 ГБ» — читается как «пусто»)"),
    "root-copies-dropped": (
        "+ old_copies(root_files, now)",
        "+ 0",
        "копии базы в корне папки не входят в итог"),
    "folder-unchecked": (
        "    if not UUID_RE.fullmatch(tid):",
        '    return contour / tid / "scratchpad", None\n    if not UUID_RE.fullmatch(tid):',
        "номер чата из базы не сверяется с видом номера, ссылки на месте папки не ловятся"),
    "links-followed": (
        '        return entry.is_symlink() or bool(getattr(entry, "is_junction", lambda: False)())',
        "        return False",
        "ссылки (junction/symlink) внутри папки проходятся как каталоги"),
    "contour-roles-silent": (
        '    if roles_err:\n        print(f"⚪ не проверено',
        '    if False:\n        print(f"⚪ не проверено',
        "роли не прочитались — сводка всё равно печатается, и все чаты в ней «закрытые»"),
    "ref-errors-apply-proceeds": (
        '        if args.apply:\n            print("⛔ без ссылок',
        '        if False:\n            print("⛔ без ссылок',
        "ссылки не прочитались — уборка всё равно идёт"),
    "apply-any-db": (
        "    if args.apply and args.db and not same_path(Path(args.db), live_db):",
        "    if False:",
        "--apply с любой базой (--db), а не только с живой базой контура"),
    "arrival-unchecked": (
        "    items0, size0 = before",
        "    return None\n    items0, size0 = before",
        "приход в корзину не проверяется: «мимо корзины» не замечается"),
}

# 📋 СПИСОК ПРОВАЛОВ КАЖДОЙ ПОЛОМКИ — ЗАПИСАН ДО ПРОГОНА (2026-10-03 ~00:20 UTC, до первого
# прогона этой редакции). Расхождение с прогоном не исправляется молча: запись остаётся,
# а рядом пишется, что дал прогон и почему.
BREAK_FAILS = {
    "measure-changes-tree": "①",
    "copy-age-ignored": "②⑰",
    "copy-age-9": "②",
    "threshold-200": "②",
    "card-ref-unread": "③",
    "ref-live-forms": "③",
    "open-cards-narrow": "③",
    "fresh-not-kept": "④⑦",
    "fresh-15min": "④",
    "mtime-top-only": "④",
    "dirent-mtime": "④",
    "long-path-not-refused": "⑤",
    "long-path-300": "⑤",
    "long-path-gt": "⑤",
    "utf16-ignored": "⑤",
    "apply-without-word": "⑥",
    "owner-word-no-time": "⑥",
    "trash-skipped": "⑤⑦⑧⑭⑲",
    "foreign-role": "⑧⑬",
    "unknown-chat-proceeds": "⑧",
    "copy-by-name": "①②⑨⑰",
    "header-only": "⑨",
    "brief-multiline": "⑩",
    "closed-chat-claimed": "⑪",
    "note-ref-unread": "⑫",
    "prefix-match": "⑫",
    "note-window-2": "⑫",
    "session-role-unknown": "⑬",
    "capacity-unchecked": "⑭",
    "env-stop-continues": "⑮",
    "busy-not-probed": "⑮",
    "hardlinks-twice": "⑯",
    "small-size-in-gb": "⑯",
    "root-copies-dropped": "⑰",
    "folder-unchecked": "⑱",
    "links-followed": "⑲",
    "contour-roles-silent": "⑳",
    "ref-errors-apply-proceeds": "㉑",
    "apply-any-db": "㉑",
    "arrival-unchecked": "㉒",
}


# ═══ ДЕРЕВЬЯ ════════════════════════════════════════════════════════════════════════════

def contour_dir_name(container: Path) -> str:
    """То же правило, что у инструмента: каждый знак, кроме латинских букв и цифр, — «-».
    Повторено здесь нарочно: приёмка строит дерево ПО ПРАВИЛУ, а не по ответу инструмента."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(container))


def u16(s: str) -> int:
    """Длина в знаках UTF-16 — по правилу Windows, а не по ответу инструмента."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def age(path: Path, seconds_ago: float) -> None:
    """Час правки всего дерева — снизу вверх, чтобы правка ребёнка не сдвинула родителя.
    ⚠️ os.walk проходит junction — звать ДО того, как в дереве появятся ссылки."""
    t = time.time() - seconds_ago
    for dirpath, _dirnames, filenames in os.walk(path, topdown=False):
        for n in filenames:
            os.utime(os.path.join(dirpath, n), (t, t))
        os.utime(dirpath, (t, t))


def touch(path: Path, seconds_ago: float) -> None:
    t = time.time() - seconds_ago
    os.utime(path, (t, t))


def folder(scratch: Path, name: str, seconds_ago: float = 2 * DAY, size: int = 4096) -> Path:
    d = scratch / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.bin").write_bytes(b"\0" * size)
    age(d, seconds_ago)
    return d


def path_of_length(top: Path, total: int, tail: str = "") -> Path:
    """Путь файла под top длиной ровно total знаков UTF-16 (каталоги по ≤ 100 знаков);
    tail — конец имени файла (например, эмодзи)."""
    cur = top
    while True:
        rest = total - u16(str(cur)) - 1
        if rest <= 120:
            break
        cur = cur / ("d" * min(100, rest - 20))
    if rest - u16(tail) < 1:
        raise OSError(f"корень песочницы слишком длинный для пути в {total} знаков")
    return cur / ("f" * (rest - u16(tail)) + tail)


def make_db(path: Path, with_messages: bool = True, wal: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, body_md TEXT)" if with_messages
                else "CREATE TABLE notes (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()


def tiny_contour_db(path: Path, role: str, tid: str, with_tid: bool = True,
                    with_events: bool = True) -> None:
    """Маленькая база контура с НАРОЧНОЙ нехваткой: без колонки transcript_id или без
    таблицы backlog_events. Предмет случаев ⑳ ㉑ — именно нехватка, а не содержимое."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    if with_tid:
        con.execute("CREATE TABLE role_sessions (role TEXT PRIMARY KEY, address TEXT, transcript_id TEXT)")
        con.execute("INSERT INTO role_sessions VALUES (?, 'acc', ?)", (role, tid))
    else:
        con.execute("CREATE TABLE role_sessions (role TEXT PRIMARY KEY, address TEXT)")
        con.execute("INSERT INTO role_sessions VALUES (?, 'acc')", (role,))
    con.execute("CREATE TABLE backlog (id INTEGER PRIMARY KEY, title TEXT, body_md TEXT, "
                "done_when TEXT, blocked_reason TEXT, status TEXT)")
    if with_events:
        con.execute("CREATE TABLE backlog_events (id INTEGER PRIMARY KEY, backlog_id INTEGER, body_md TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, timestamp TEXT, body_md TEXT)")
    con.commit()
    con.close()


def make_junction(target: Path, link: Path) -> None:
    import _winapi
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    _winapi.CreateJunction(str(target), str(link))


def unlink_junctions(root: Path) -> int:
    """Снять все ссылки-junction в песочнице (только саму ссылку, не цель) — до её уборки."""
    removed = 0
    stack = [str(root)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_junction() or e.is_symlink():
                    os.rmdir(e.path)
                    removed += 1
                elif e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
            except OSError:
                pass
    return removed


def fingerprint(root: Path) -> list:
    """Отпечаток дерева: относительный путь · размер файла · час правки (и у каталогов)."""
    rows = []
    for dirpath, _dirnames, filenames in os.walk(root):
        rows.append((os.path.relpath(dirpath, root), -1, os.stat(dirpath).st_mtime_ns))
        for n in filenames:
            p = os.path.join(dirpath, n)
            st = os.stat(p)
            rows.append((os.path.relpath(p, root), st.st_size, st.st_mtime_ns))
    return sorted(rows)


def fp_diff(a, b) -> str:
    sa, sb = set(a), set(b)
    gone = sorted({r[0] for r in sa - sb})
    new = sorted({r[0] for r in sb - sa})
    return f"изменились/пропали: {gone[:3]} · появились/изменились: {new[:3]}"


def inside(path, base) -> bool:
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


def run_tool(tool: Path, stand: Path, scr_root: Path, trash: Path, *args,
             role=None, session=None, extra=None):
    """Позвать КОПИЮ инструмента со средой стенда. MEZO_TRASH_DIR ставится ВСЕГДА — даже
    там, где ждём отказа: под нарочной поломкой отказ может не случиться, и тогда уборка
    обязана уехать в подменный каталог, а не в корзину Windows."""
    env = mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8",
                               MEZO_SCRATCH_ROOT=str(scr_root), MEZO_TRASH_DIR=str(trash))
    for name in ("MEZO_ROLE", SESSION_ENV, "MEZO_SCRATCH_THRESHOLD_GB", "MEZO_TRASH_CAPACITY_MB"):
        env.pop(name, None)
    if role:
        env["MEZO_ROLE"] = role
    if session:
        env[SESSION_ENV] = session
    if extra:
        env.update(extra)
    for what in ("MEZO_SCRATCH_ROOT", "MEZO_TRASH_DIR", "MEZO_CONTAINER"):
        if not inside(env[what], SANDBOX):
            raise SystemExit(f"⛔ НЕ ПРОВЕРЕНО: {what}={env[what]} вне песочницы {SANDBOX} — "
                             f"инструмент не позван")
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-B", str(tool), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or ""), time.monotonic() - t0


SUB_RE = re.compile(r"копий базы: (\d+) \(старше \d+ суток: (\d+)\) · (.*)$")


def sub_line(output: str, name: str) -> str:
    return next((line for line in output.splitlines() if f"📁 {name} ·" in line), "")


def decision(output: str, name: str) -> str:
    m = SUB_RE.search(sub_line(output, name))
    return m.group(3) if m else "(строки нет)"


def copies(output: str, name: str):
    m = SUB_RE.search(sub_line(output, name))
    return (int(m.group(1)), int(m.group(2))) if m else None


def itog_old(output: str):
    m = re.search(r"ИТОГ: всего .* · к уборке .* · копий базы старше \d+ суток: (\d+)", output)
    return int(m.group(1)) if m else None


def lines_of(output: str) -> list:
    return [line for line in output.splitlines() if line.strip()]


def refused_named(output: str, name: str, words: str) -> bool:
    tail = output.split("ИТОГ УБОРКИ", 1)[-1]
    return any(name in line and ("ГБ" in line or "МБ" in line) and words in line
               for line in tail.splitlines())


# ═══ ПРОГОН ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    global SANDBOX
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: чем испортить КОПИЮ инструмента перед прогоном")
    a = ap.parse_args()
    break_name = a.break_name

    live_tool = Path(__file__).resolve().parent / "scratch-folders.py"
    if not live_tool.is_file():
        print(f"⛔ НЕ ЗАПУСТИЛСЯ: инструмента нет: {live_tool}")
        return 2

    sandbox = mezo_stand.new("bite-scratch-")
    try:
        SANDBOX = sandbox.resolve()
        stand = SANDBOX / "ctr"
        (stand / ".mezosync").mkdir(parents=True)
        db = mezo_stand.snapshot_db(mezo_paths.live_db(__file__), stand / ".mezosync" / "mezosync.db")
        tool = mezo_stand.copy_tool(live_tool, SANDBOX / "tool")
        if break_name:
            before_text, after_text, expectation = BREAKS[break_name]
            text = tool.read_text(encoding="utf-8")
            if text.count(before_text) != 1:
                print(f"⛔ НЕ ПРОВЕРЕНО: поломка «{break_name}» НЕ ЛЕГЛА — искомое место "
                      f"встречается {text.count(before_text)} раз; поправь приёмку, а не инструмент")
                return 2
            # байтами, а не текстом: запись текстом на Windows сменила бы окончания строк копии
            tool.write_bytes(text.replace(before_text, after_text).encode("utf-8"))
            print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{break_name}»: {expectation}")
            print(f"   ждём провала РОВНО: {' '.join(BREAK_FAILS[break_name])} "
                  f"(записано в BREAK_FAILS до прогона)\n")

        token = uuid.uuid4().hex[:6]
        role, other, notid, nofolder = "ACCSCR", "ACCOTHER", "ACCNOTID", "ACCNOFLD"
        esc, jn = "ACCESC", "ACCJN"
        tid = f"{token}aa-1111-4222-8333-000000000001"
        tid_other = f"{token}aa-1111-4222-8333-000000000002"
        tid_closed = f"{token}aa-1111-4222-8333-000000000003"
        tid_nofolder = f"{token}aa-1111-4222-8333-000000000004"
        tid_jn = f"{token}aa-1111-4222-8333-000000000005"
        tid_esc = "..\\esc18"
        contour = contour_dir_name(stand)
        word = "«убери черновики» 2026-10-03 00:00 UTC (приёмка)"

        def n(suffix):
            return f"z{token}-{suffix}"

        def root(tag):
            return SANDBOX / f"s{tag}"

        def trash(tag):
            return SANDBOX / f"t{tag}"

        def scratch(tag, chat=tid, cont=contour):
            return root(tag) / cont / chat / "scratchpad"

        # 🩹 03.10.2026 (повторная приёмка карточки #657): деревья приёмки лежат ВНУТРИ имени каталога
        # контура, а оно строится из пути песочницы — длина путей растёт как УДВОЕННАЯ глубина
        # %TEMP%. В глубоком %TEMP% (песочница помощника, 143 знака) инструмент честно отказывал
        # «путь длиннее 260 знаков» в восьми случаях, и приёмка ложно проваливалась (13 из 21).
        # Замер 2026-10-03 ~02:40 UTC: при TEMP в 39 знаков самый длинный путь (кроме ⑤) — 203,
        # это файл в глубине подпапки случая ④. ⇒ слишком глубокий %TEMP% — «не проверено»
        # кодом 2 до всякой работы, а не провал случаев.
        deepest = scratch(4) / n("deep4") / "run1" / "log.txt"
        if u16(str(deepest)) >= 260:
            print(f"⚪ НЕ ПРОВЕРЕНО: временный каталог слишком глубок — самый длинный путь приёмки "
                  f"вышел бы {u16(str(deepest))} знаков (от 260 инструмент честно отказывает), "
                  f"путь песочницы {u16(str(SANDBOX))} знаков. Запусти с TEMP короче")
            return 2

        # ── копия базы: роли, карточки, записки ──
        con = sqlite3.connect(str(db))
        cols = {r[1] for r in con.execute("PRAGMA table_info(role_sessions)")}
        if "transcript_id" not in cols:
            con.close()
            print("⛔ НЕ ПРОВЕРЕНО: в role_sessions копии нет колонки transcript_id — у контура "
                  "не пройден шаг схемы 20260924-role-sessions-transcript-id.py")
            return 2
        for r_name, r_tid in ((role, tid), (other, tid_other), (notid, None), (nofolder, tid_nofolder),
                              (esc, tid_esc), (jn, tid_jn)):
            con.execute("INSERT OR REPLACE INTO role_sessions (role, address, noted_at, noted_by, "
                        "source, transcript_id) VALUES (?, ?, datetime('now'), ?, 'self', ?)",
                        (r_name, f"acc {r_name.lower()} [{token}]", r_name, r_tid))
        con.execute("INSERT INTO role_sessions_history (role, address, noted_at, noted_by, source, "
                    "transcript_id, superseded_by) VALUES ('ACCPAST', 'acc past', datetime('now', "
                    "'-3 days'), 'ACCPAST', 'self', ?, 'ACCPAST')", (tid_closed,))

        def add_card(status, body):
            return con.execute("INSERT INTO backlog (role, title, body_md, status, created_by) "
                               "VALUES (?, ?, ?, ?, ?)",
                               (role, f"приёмка черновых папок {token}", body, status, role)).lastrowid

        def add_comment(card, body):
            con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md) "
                        "VALUES (?, ?, 'comment', ?)", (card, role, body))

        def add_note(body, days_ago):
            return con.execute("INSERT INTO messages (writer_role, timestamp, body_md) "
                               "VALUES (?, datetime('now', ?), ?)",
                               (role, f"-{days_ago} days", body)).lastrowid

        card_open = add_card("open", "тело без ссылки на папку")
        add_comment(card_open, f"рабочая папка: {scratch(3) / n('copen')}")
        card_done = add_card("done", "тело без ссылки на папку")
        add_comment(card_done, f"рабочая папка: {scratch(3) / n('cdone')}")
        card_body = add_card("in_progress", f"песочница: scratchpad/{n('cbody')}/out.txt")
        card_live = add_card("open", f"песочница: scratchpad {n('clive')}/ (test1…test5)")
        card_blocked = add_card("blocked", f"вывод: scratchpad {role} {n('crole')}/{n('cdeep')}/full.txt")
        card_dropped = add_card("dropped", f"песочница: scratchpad {n('cdrop')}/ (вывод)")
        note_fresh = add_note(f"вывод лежит в scratchpad/{n('n12')}/вывод.txt", 1)
        note_6d = add_note(f"вывод лежит в scratchpad/{n('n6d')}/вывод.txt", 6)
        note_old = add_note(f"вывод лежит в scratchpad/{n('nold')}/вывод.txt", 8)
        con.commit()
        con.close()

        # ── ① замер ничего не меняет ──
        d = scratch(1) / n("wal")
        make_db(d / "snap.sqlite", wal=True)
        (d / "note.txt").write_text("x", encoding="utf-8")
        age(d, 2 * DAY)
        folder(scratch(1), n("plain1"))
        before = fingerprint(root(1))
        code, out, _t = run_tool(tool, stand, root(1), trash(1), "--role", role)
        after = fingerprint(root(1))
        same = before == after
        case("① замер ничего не меняет: отпечаток дерева (пути · размеры · час правки) до и после "
             "равен, копия базы в режиме WAL при этом прочитана",
             code == 0 and same and copies(out, n("wal")) == (1, 0),
             f"код {code} · отпечаток: {'равен' if same else 'ИЗМЕНИЛСЯ — ' + fp_diff(before, after)}"
             f" · копия WAL посчитана: {copies(out, n('wal'))} (ждём (1, 0))")

        # ── ② копия 8 суток назад при дереве меньше 2 ГБ ──
        make_db(scratch(2) / n("oldcopy") / "snap.sqlite")
        age(scratch(2) / n("oldcopy"), 8 * DAY)
        make_db(scratch(2) / n("newcopy") / "snap2.sqlite")
        age(scratch(2) / n("newcopy"), 6 * DAY)
        code, out, _t = run_tool(tool, stand, root(2), trash(2), "--role", role)
        code_t, out_t, _t = run_tool(tool, stand, root(2), trash(2), "--role", role,
                                     extra={"MEZO_SCRATCH_THRESHOLD_GB": "0.000001"})
        second = "⚠️ копий базы старше 7 суток: 1" in out
        no_first = "⚠️ пора убрать" not in out
        default_thr = "«пора убрать» — больше 2.00 ГБ на диске" in out
        first_sub = "⚠️ пора убрать:" in out_t
        case("② копия базы 8 суток назад при дереве меньше 2 ГБ → назван второй порог, «пора "
             "убрать» нет, назван порог 2 ГБ; копия 6 суток назад — копия, но не старая; "
             "подменённый порог по размеру называет «пора убрать»",
             code == 0 and second and no_first and default_thr and itog_old(out) == 1
             and copies(out, n("oldcopy")) == (1, 1) and copies(out, n("newcopy")) == (1, 0)
             and code_t == 0 and first_sub,
             f"код {code} · второй порог назван: {second} · «пора убрать» не названо: {no_first} · "
             f"порог 2.00 ГБ назван: {default_thr} · в итоге старых копий: {itog_old(out)} (ждём 1) "
             f"· 8 суток {copies(out, n('oldcopy'))} (ждём (1, 1)) · 6 суток "
             f"{copies(out, n('newcopy'))} (ждём (1, 0)) · с порогом 0.000001 ГБ: код {code_t}, "
             f"«пора убрать» названо: {first_sub}")

        # ── ③ ссылки открытых карточек ──
        for x in ("copen", "cdone", "cbody", "clive", "crole", "cdeep", "cdrop"):
            folder(scratch(3), n(x))
        code, out, _t = run_tool(tool, stand, root(3), trash(3), "--role", role)
        got = {x: decision(out, n(x)) for x in ("copen", "cdone", "cbody", "clive", "crole", "cdeep", "cdrop")}
        want = {"copen": f"оставить: упомянута в открытой карточке #{card_open}",
                "cbody": f"оставить: упомянута в открытой карточке #{card_body}",
                "clive": f"оставить: упомянута в открытой карточке #{card_live}",
                "crole": f"оставить: упомянута в открытой карточке #{card_blocked}",
                "cdone": "убрать", "cdeep": "убрать", "cdrop": "убрать"}
        bad3 = {x: got[x] for x in want if got[x] != want[x]}
        case("③ ссылки ОТКРЫТЫХ карточек → «оставить» со ссылкой: комментарий (полный путь), тело "
             "(«scratchpad/<имя>»), «scratchpad <имя>/», «scratchpad <РОЛЬ> <имя>/» в карточке "
             "blocked; встречные: закрытые (done, dropped) и имя вторым звеном пути → «убрать»",
             code == 0 and not bad3,
             f"код {code} · комментарий #{card_open}: «{got['copen']}» · тело #{card_body}: "
             f"«{got['cbody']}» · «scratchpad <имя>/» #{card_live}: «{got['clive']}» · blocked "
             f"#{card_blocked}: «{got['crole']}» · второе звено: «{got['cdeep']}» · done "
             f"#{card_done}: «{got['cdone']}» · dropped #{card_dropped}: «{got['cdrop']}»"
             + (f" · НЕ СОВПАЛО: {sorted(bad3)}" if bad3 else ""))

        # ── ④ свежая правка ──
        folder(scratch(4), n("fresh"), seconds_ago=600)
        folder(scratch(4), n("f50"), seconds_ago=50 * 60)
        folder(scratch(4), n("stale"), seconds_ago=7200)
        deep4 = scratch(4) / n("deep4")
        (deep4 / "run1").mkdir(parents=True)
        (deep4 / "run1" / "log.txt").write_text("x", encoding="utf-8")
        age(deep4, 7200)
        touch(deep4 / "run1" / "log.txt", 300)
        open4 = scratch(4) / n("open4")
        open4.mkdir(parents=True)
        (open4 / "log.txt").write_bytes(b"start\n")
        age(open4, 7200)
        held4 = open(open4 / "log.txt", "ab")
        try:
            held4.write(b"x" * 25000)
            held4.flush()
            stale_entry = next(e for e in os.scandir(open4) if e.name == "log.txt").stat().st_mtime
            stale = time.time() - stale_entry > 3600
            code, out, _t = run_tool(tool, stand, root(4), trash(4), "--role", role)
        finally:
            held4.close()
        got4 = {x: decision(out, n(x)) for x in ("fresh", "f50", "stale", "deep4", "open4")}
        keep_words = "оставить: правка за последний час"
        title4 = ("④ правка 10 и 50 минут назад, правка файла в глубине (каталоги — 2 часа назад) и "
                  "дописывание в открытый файл → «оставить: правка за последний час»; встречный: "
                  "2 часа назад → «убрать»")
        detail4 = (f"код {code} · 10 минут: «{got4['fresh']}» · 50 минут: «{got4['f50']}» · в глубине: "
                   f"«{got4['deep4']}» · открытый файл: «{got4['open4']}» (запись каталога отстала: "
                   f"{stale}) · 2 часа: «{got4['stale']}»")
        if not stale:
            unmeasured(title4, "запись каталога у открытого файла не отстала — дописывание "
                               "неотличимо от обычной правки; " + detail4)
        else:
            case(title4,
                 code == 0 and all(got4[x] == keep_words for x in ("fresh", "f50", "deep4", "open4"))
                 and got4["stale"] == "убрать", detail4)

        # ── ⑤ путь от 260 знаков UTF-16 ──
        made = True
        try:
            p260 = path_of_length(scratch(5) / n("p260"), 260)
            p259 = path_of_length(scratch(5) / n("p259"), 259)
            emo = path_of_length(scratch(5) / n("emo"), 261, tail="😀😀😀")
            for p in (p260, p259, emo):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"\0" * 4096)
            for x in ("p260", "p259", "emo"):
                age(scratch(5) / n(x), 2 * DAY)
        except OSError as e:
            made = False
            unmeasured("⑤ путь от 260 знаков → «отказ», при --apply не тронут",
                       f"ФС не дала создать путь ({e}) — случай не подделывается")
        if made:
            lens = (u16(str(p260)), u16(str(p259)), u16(str(emo)), len(str(emo)))
            code, out, _t = run_tool(tool, stand, root(5), trash(5), "--role", role, "--apply",
                                     "--owner-word", word, role=role)
            d260, d259, demo = decision(out, n("p260")), decision(out, n("p259")), decision(out, n("emo"))
            named = (refused_named(out, n("p260"), "путь длиннее 260 знаков")
                     and refused_named(out, n("emo"), "путь длиннее 260 знаков"))
            kept5 = p260.is_file() and emo.is_file()
            moved5 = not (scratch(5) / n("p259")).exists() and (trash(5) / n("p259")).is_dir()
            case("⑤ путь ровно 260 знаков и 261 знак UTF-16 при 258 знаках Python (эмодзи) → «отказ», "
                 "назван с размером, при --apply не тронут; встречный: 259 знаков → убран; код 1",
                 lens[:3] == (260, 259, 261) and lens[3] < 260 and code == 1
                 and d260.startswith("отказ: путь длиннее 260 знаков")
                 and demo.startswith("отказ: путь длиннее 260 знаков") and d259 == "убрать"
                 and named and kept5 and moved5,
                 f"длины UTF-16 {lens[:3]} (ждём (260, 259, 261)), эмодзи в знаках Python {lens[3]} · "
                 f"код {code} (ждём 1) · 260: «{d260}» · эмодзи: «{demo}» · 259: «{d259}» · отказы "
                 f"названы с размером: {named} · на месте: {kept5} · 259 в подменной корзине: {moved5}")

        # ── ⑥ --apply без слова владельца ──
        folder(scratch(6), n("x6"))
        before = fingerprint(root(6))
        results = []
        for word_args, expect in (([], "БЕЗ СЛОВА ВЛАДЕЛЬЦА"), (["--owner-word", ""], "БЕЗ СЛОВА ВЛАДЕЛЬЦА"),
                                  (["--owner-word", "   "], "БЕЗ СЛОВА ВЛАДЕЛЬЦА"),
                                  (["--owner-word", "."], "НЕТ ЧАСА UTC")):
            c6, o6, _t = run_tool(tool, stand, root(6), trash(6), "--role", role, "--apply",
                                  *word_args, role=role)
            results.append((c6, expect in o6))
        after = fingerprint(root(6))
        case("⑥ --apply без --owner-word, с пустым, из пробелов и без часа UTC («.») → код 2 словами, "
             "дерево не тронуто",
             all(c == 2 and w for c, w in results) and before == after,
             f"коды и слова: {results} (ждём четырежды (2, True)) · отпечаток: "
             f"{'равен' if before == after else 'ИЗМЕНИЛСЯ — ' + fp_diff(before, after)}")

        # ── ⑦ --apply со словом владельца ──
        folder(scratch(7), n("rm7"))
        folder(scratch(7), n("keep7"), seconds_ago=600)
        word7 = "«убери черновики» 2026-10-03 00:07 UTC (приёмка)"
        code, out, _t = run_tool(tool, stand, root(7), trash(7), "--role", role, "--apply",
                                 "--owner-word", word7, role=role)
        moved = (trash(7) / n("rm7")).is_dir() and not (scratch(7) / n("rm7")).exists()
        kept = (scratch(7) / n("keep7")).is_dir()
        aloud = "MEZO_TRASH_DIR" in out and "вместо корзины" in out
        case("⑦ --apply со словом владельца → «убрать» уехала в MEZO_TRASH_DIR, «оставить» на "
             "месте, подмена корзины сказана вслух, слово владельца повторено",
             code == 0 and moved and kept and aloud and word7 in out,
             f"код {code} · «убрать» в подменной корзине: {moved} · «оставить» на месте: {kept} · "
             f"подмена названа: {aloud} · слово повторено: {word7 in out}")

        # ── ⑧ чужая роль и неузнанная своя ──
        folder(scratch(8, tid_other), n("other8"))
        before = fingerprint(root(8))
        stranger = f"{token}ff-0000-4000-8000-000000000000"
        c_a, o_a, _t = run_tool(tool, stand, root(8), trash(8), "--role", other, "--apply",
                                "--owner-word", word, role=role)
        c_b, o_b, _t = run_tool(tool, stand, root(8), trash(8), "--role", other, "--apply",
                                "--owner-word", word)
        c_c, o_c, _t = run_tool(tool, stand, root(8), trash(8), "--role", other, "--apply",
                                "--owner-word", word, session=stranger)
        after = fingerprint(root(8))
        code_own, _out_own, _t = run_tool(tool, stand, root(8), trash(8), "--role", other, "--apply",
                                          "--owner-word", word, role=other)
        own_moved = (trash(8) / n("other8")).is_dir()
        ok_a = c_a == 2 and "ЧУЖАЯ ПАПКА" in o_a
        ok_b = c_b == 2 and "НЕ ЗНАЮ, ЧЕЙ ЭТО ЧАТ" in o_b
        ok_c = c_c == 2 and "НЕ ЗНАЮ, ЧЕЙ ЭТО ЧАТ" in o_c
        case("⑧ --role чужой роли при MEZO_ROLE своей → «ЧУЖАЯ ПАПКА»; без MEZO_ROLE и без номера "
             "чата, и с номером не из role_sessions → «НЕ ЗНАЮ, ЧЕЙ ЭТО ЧАТ»; всё — код 2, дерево "
             "не тронуто; встречный: та же роль в MEZO_ROLE — уборка идёт",
             ok_a and ok_b and ok_c and before == after and code_own == 0 and own_moved,
             f"MEZO_ROLE своя: код {c_a}, {ok_a} · ни MEZO_ROLE, ни номера: код {c_b}, {ok_b} · "
             f"номер не из реестра: код {c_c}, {ok_c} · отпечаток: "
             f"{'равен' if before == after else 'ИЗМЕНИЛСЯ — ' + fp_diff(before, after)} · "
             f"встречный: код {code_own}, папка уехала: {own_moved}")

        # ── ⑨ не копии базы ──
        junk = scratch(9) / n("junk")
        junk.mkdir(parents=True)
        (junk / "mezosync.db").write_bytes((b"not a database " * 200)[:2048])
        age(junk, 10 * DAY)
        make_db(scratch(9) / n("foreign") / "mezosync.db", with_messages=False)
        age(scratch(9) / n("foreign"), 10 * DAY)
        code, out, _t = run_tool(tool, stand, root(9), trash(9), "--role", role)
        c_junk, c_foreign = copies(out, n("junk")), copies(out, n("foreign"))
        case("⑨ мусор с именем mezosync.db и SQLite без таблицы messages копиями базы не считаются",
             code == 0 and c_junk == (0, 0) and c_foreign == (0, 0) and itog_old(out) == 0
             and "⚠️ копий базы" not in out,
             f"код {code} · мусор: {c_junk} · SQLite без messages: {c_foreign} (ждём (0, 0) оба) · "
             f"старых копий в итоге: {itog_old(out)} (ждём 0)")

        # ── ⑩ --brief ──
        folder(scratch(10), n("b10"))
        tiny = {"MEZO_SCRATCH_THRESHOLD_GB": "0.000001"}
        c_a, o_a, t_a = run_tool(tool, stand, root(10), trash(10), "--role", role, "--brief", extra=tiny)
        c_b, o_b, _t = run_tool(tool, stand, root(10), trash(10), "--brief")
        c_c, o_c, _t = run_tool(tool, stand, root(10), trash(10), "--role", notid, "--brief")
        c_d, o_d, _t = run_tool(tool, stand, root(10), trash(10), "--role", nofolder, "--brief")
        ok_a = (c_a == 0 and len(lines_of(o_a)) == 1 and f"черновая папка {role}:" in o_a
                and "ГБ" in o_a and "пора убрать:" in o_a and t_a < 15)
        ok_b = c_b == 0 and len(lines_of(o_b)) == 1 and "роль не названа" in o_b
        ok_c = c_c == 0 and len(lines_of(o_c)) == 1 and "transcript_id" in o_c
        ok_d = c_d == 0 and len(lines_of(o_d)) == 1 and "папки нет" in o_d
        case("⑩ --brief — одна строка и код 0: с папкой и порогом · без роли · без transcript_id · без папки",
             ok_a and ok_b and ok_c and ok_d,
             f"с папкой: код {c_a}, строк {len(lines_of(o_a))}, {t_a:.1f} с, «пора убрать»: "
             f"{'пора убрать:' in o_a} · без роли: код {c_b}, строк {len(lines_of(o_b))} · без "
             f"transcript_id: код {c_c}, строк {len(lines_of(o_c))} · без папки: код {c_d}, строк "
             f"{len(lines_of(o_d))}")

        # ── ⑪ --contour ──
        folder(scratch(11), n("live11"))
        folder(scratch(11, tid_closed), n("c11"))
        folder(scratch(11, tid_other), n("o11"))
        (root(11) / contour / "no-scratchpad-chat").mkdir(parents=True)
        before = fingerprint(root(11))
        code, out, _t = run_tool(tool, stand, root(11), trash(11), "--contour")
        code_ap, out_ap, _t = run_tool(tool, stand, root(11), trash(11), "--contour", "--apply",
                                       "--owner-word", word, role=role)
        after = fingerprint(root(11))
        line_closed = next((x for x in out.splitlines() if tid_closed in x), "")
        line_live = next((x for x in out.splitlines() if f" {tid} " in x), "")
        refused = code_ap == 2 and "уборка закрытых чатов — отдельной работой по слову владельца" in out_ap
        case("⑪ --contour: папка закрытого чата — «закрытый чат, роли нет» (с подсказкой истории "
             "адресов), живого — с ролью; --contour --apply → код 2 словами, дерево не тронуто",
             code == 0 and "закрытый чат, роли нет" in line_closed and "ACCPAST" in line_closed
             and f"роль {role}" in line_live and "ИТОГ: папок 3" in out and refused and before == after,
             f"код {code} · строка закрытого: «{line_closed.strip()}» · строка живого: "
             f"«{line_live.strip()}» · итог по трём папкам: {'ИТОГ: папок 3' in out} · --apply: код "
             f"{code_ap}, отказ словами: {refused} · отпечаток: {'равен' if before == after else 'ИЗМЕНИЛСЯ'}")

        # ── ⑫ записки ──
        for x in ("n12", "n1", "n6d", "nold"):
            folder(scratch(12), n(x))
        code, out, _t = run_tool(tool, stand, root(12), trash(12), "--role", role)
        d12, d1, d6, dold = (decision(out, n("n12")), decision(out, n("n1")), decision(out, n("n6d")),
                             decision(out, n("nold")))
        case("⑫ записки сутки и 6 суток назад → «оставить» со ссылкой; встречные: записка 8 суток "
             "назад → «убрать», имя-приставка → «убрать»",
             code == 0 and d12 == f"оставить: упомянута в записке #{note_fresh}"
             and d6 == f"оставить: упомянута в записке #{note_6d}"
             and d1 == "убрать" and dold == "убрать",
             f"код {code} · записка #{note_fresh} (сутки назад): «{d12}» · записка #{note_6d} "
             f"(6 суток назад): «{d6}» · приставка: «{d1}» · записка #{note_old} (8 суток назад): «{dold}»")

        # ── ⑬ роль по номеру чата ──
        folder(scratch(13), n("s13"))
        folder(scratch(13, tid_other), n("o13"))
        c_a, o_a, _t = run_tool(tool, stand, root(13), trash(13), "--brief", session=tid)
        c_b, o_b, _t = run_tool(tool, stand, root(13), trash(13), session=tid)
        c_c, o_c, _t = run_tool(tool, stand, root(13), trash(13), "--brief", session=stranger)
        c_d, o_d, _t = run_tool(tool, stand, root(13), trash(13), session=stranger)
        before = fingerprint(root(13))
        c_e, o_e, _t = run_tool(tool, stand, root(13), trash(13), "--role", other, "--apply",
                                "--owner-word", word, session=tid)
        after = fingerprint(root(13))
        ok_a = c_a == 0 and f"черновая папка {role}:" in o_a
        ok_b = c_b == 0 and f"черновая папка роли {role} (роль — номер чата" in o_b
        ok_c = c_c == 0 and "роль не названа" in o_c
        ok_d = c_d == 2 and "роль не названа" in o_d
        ok_e = c_e == 2 and "ЧУЖАЯ ПАПКА" in o_e and before == after
        case("⑬ роль по номеру чата (CLAUDE_CODE_SESSION_ID → role_sessions): узнана строкой и "
             "замером; чужой номер → «роль не названа»; --apply с номером чата другой роли → отказ",
             ok_a and ok_b and ok_c and ok_d and ok_e,
             f"строка: {ok_a} · замер: {ok_b} · чужой номер, строка (код 0): {ok_c} · чужой номер, "
             f"замер (код 2): {ok_d} (код {c_d}) · --apply чужой роли при номере своего чата: "
             f"код {c_e}, отпечаток {'равен' if before == after else 'ИЗМЕНИЛСЯ'}")

        # ── ⑭ вместимость корзины ──
        folder(scratch(14), n("big"), size=2 * MIB)
        folder(scratch(14), n("small"), size=10 * 1024)
        code, out, _t = run_tool(tool, stand, root(14), trash(14), "--role", role, "--apply",
                                 "--owner-word", word, role=role,
                                 extra={"MEZO_TRASH_CAPACITY_MB": "1"})
        named = refused_named(out, n("big"), "не влезает в корзину")
        case("⑭ папка больше свободного места корзины → «отказ: не влезает в корзину», названа с "
             "размером, не тронута; сосед убран; код 1",
             code == 1 and named and (scratch(14) / n("big")).is_dir()
             and (trash(14) / n("small")).is_dir(),
             f"код {code} (ждём 1) · отказ назван с размером: {named} · большая на месте: "
             f"{(scratch(14) / n('big')).is_dir()} · малая в подменной корзине: "
             f"{(trash(14) / n('small')).is_dir()}")

        # ── ⑮ папка занята процессом ──
        a15 = folder(scratch(15), n("a15"))
        (a15 / "second.bin").write_bytes(b"\1" * 4096)
        age(a15, 2 * DAY)
        folder(scratch(15), n("b15"))
        held = open(a15 / "data.bin", "rb")
        try:
            code, out, _t = run_tool(tool, stand, root(15), trash(15), "--role", role, "--apply",
                                     "--owner-word", word, role=role)
        finally:
            held.close()
        stop_line = next((x for x in out.splitlines() if "ОСТАНОВКА" in x and n("a15") in x), "")
        busy_named = "занята процессом" in stop_line
        a15_whole = (a15 / "data.bin").is_file() and (a15 / "second.bin").is_file()
        case("⑮ папка занята процессом (файл внутри открыт) → названа занятой до переноса, "
             "остановка всей уборки на ней, её файлы и следующая папка на месте, код 1",
             code == 1 and bool(stop_line) and busy_named and a15_whole
             and (scratch(15) / n("b15")).is_dir(),
             f"код {code} (ждём 1) · строка остановки: «{stop_line.strip()}» · «занята процессом»: "
             f"{busy_named} · оба файла первой на месте: {a15_whole} · следующая на месте: "
             f"{(scratch(15) / n('b15')).is_dir()}")

        # ── ⑯ жёсткая ссылка ──
        hl = scratch(16) / n("hl16")
        hl.mkdir(parents=True)
        (hl / "big.bin").write_bytes(b"\0" * (20 * MIB))
        os.link(hl / "big.bin", hl / "big-link.bin")
        age(hl, 2 * DAY)
        code, out, _t = run_tool(tool, stand, root(16), trash(16), "--role", role)
        c_br, o_br, _t = run_tool(tool, stand, root(16), trash(16), "--role", role, "--brief")
        sizes = "20.0 МБ на диске (по именам файлов 40.0 МБ"
        in_line = sizes in sub_line(out, n("hl16"))
        in_itog = any(x.startswith("ИТОГ: всего " + sizes) for x in out.splitlines())
        in_brief = ("≈" + sizes) in o_br
        case("⑯ жёсткая ссылка: файл 20 МиБ под двумя именами — на диске 20.0 МБ, по именам 40.0 МБ "
             "(строка подпапки, итог, строка --brief; меньше 0,1 ГБ — в МБ)",
             code == 0 and c_br == 0 and in_line and in_itog and in_brief,
             f"код {code}/{c_br} · строка подпапки: {in_line} · итог: {in_itog} · --brief: {in_brief} "
             f"· строка: «{sub_line(out, n('hl16')).strip()}»")

        # ── ⑰ копия базы в корне папки ──
        make_db(scratch(17) / "root-old.sqlite")
        touch(scratch(17) / "root-old.sqlite", 10 * DAY)
        folder(scratch(17), n("plain17"))
        code, out, _t = run_tool(tool, stand, root(17), trash(17), "--role", role)
        c_br, o_br, _t = run_tool(tool, stand, root(17), trash(17), "--role", role, "--brief")
        itog17 = itog_old(out) == 1 and "(из них в корне папки 1" in out
        # число суток в словах не сверяется: предмет случая — корень папки, а не граница 7 суток
        listed = (re.search(r"в корне папки копий базы: 1, из них старше \d+ суток: 1", out) is not None
                  and "🗄 root-old.sqlite" in out)
        brief17 = "из них в корне папки 1" in o_br
        case("⑰ копия базы в корне папки (10 суток) — посчитана в итоге и строке --brief, названа "
             "списком отдельно, этим инструментом не убирается",
             code == 0 and c_br == 0 and itog17 and listed and brief17,
             f"код {code}/{c_br} · итог: старых {itog_old(out)}, «из них в корне папки 1»: {itog17} · "
             f"названа списком: {listed} · строка --brief: {brief17}")

        # ── ⑱ папка за пределами контура ──
        junction_ok = True
        try:
            v18 = folder(root(18) / "esc18" / "scratchpad", "v18")
            core18 = folder(root(18) / "victimrepo", "core18")
            make_junction(root(18) / "victimrepo", scratch(18, tid_jn))
        except (OSError, ImportError, AttributeError) as e:
            junction_ok = False
            unmeasured("⑱ папка за пределами контура → код 2",
                       f"ссылку-junction создать не вышло ({e}) — случай не подделывается")
        if junction_ok:
            before = fingerprint(root(18))
            c_a, o_a, _t = run_tool(tool, stand, root(18), trash(18), "--role", esc, "--apply",
                                    "--owner-word", word, role=esc)
            c_b, o_b, _t = run_tool(tool, stand, root(18), trash(18), "--role", jn, "--apply",
                                    "--owner-word", word, role=jn)
            after = fingerprint(root(18))
            ok_a = c_a == 2 and "не похож на номер чата" in o_a and v18.is_dir()
            ok_b = c_b == 2 and "ссылка на другое место" in o_b and core18.is_dir()
            case("⑱ номер чата в базе «..\\esc18» и scratchpad — ссылка на чужой каталог → код 2, "
                 "за пределами контура ничего не тронуто",
                 ok_a and ok_b and before == after,
                 f"номер «..\\esc18»: код {c_a}, {ok_a} · scratchpad-ссылка: код {c_b}, {ok_b} · "
                 f"отпечаток: {'равен' if before == after else 'ИЗМЕНИЛСЯ — ' + fp_diff(before, after)}")

        # ── ⑲ ссылки внутри папки ──
        junction_ok = True
        try:
            tgt_top = root(19) / "tgt-top"
            tgt_in = root(19) / "tgt-in"
            for t in (tgt_top, tgt_in):
                t.mkdir(parents=True)
                (t / "keep.txt").write_text("цель", encoding="utf-8")
            withjn = folder(scratch(19), n("withjn"))
            make_junction(tgt_in, withjn / "inner")
            touch(withjn, 2 * DAY)                      # ссылка сдвинула час правки каталога
            make_junction(tgt_top, scratch(19) / n("jtop"))
        except (OSError, ImportError, AttributeError) as e:
            junction_ok = False
            unmeasured("⑲ ссылки внутри папки", f"ссылку-junction создать не вышло ({e})")
        if junction_ok:
            code, out, _t = run_tool(tool, stand, root(19), trash(19), "--role", role, "--apply",
                                     "--owner-word", word, role=role)
            d_top, d_with = decision(out, n("jtop")), decision(out, n("withjn"))
            top_left = os.path.isjunction(scratch(19) / n("jtop"))
            with_moved = (trash(19) / n("withjn")).is_dir() and not (scratch(19) / n("withjn")).exists()
            targets = (tgt_top / "keep.txt").is_file() and (tgt_in / "keep.txt").is_file()
            case("⑲ ссылка верхнего уровня → «отказ: ссылка на другое место» и на месте; подпапка со "
                 "ссылкой внутри убрана; цели обеих ссылок целы; код 1",
                 code == 1 and d_top == "отказ: ссылка на другое место" and d_with == "убрать"
                 and top_left and with_moved and targets,
                 f"код {code} (ждём 1) · верхняя ссылка: «{d_top}», на месте: {top_left} · подпапка "
                 f"со ссылкой: «{d_with}», в подменной корзине: {with_moved} · цели целы: {targets}")

        # ── ⑳ --contour при нечитаемых ролях ──
        ctr20 = SANDBOX / "ctr20"
        tiny_contour_db(ctr20 / ".mezosync" / "mezosync.db", role, tid, with_tid=False)
        folder(scratch(20, cont=contour_dir_name(ctr20)), n("x20"))
        code, out, _t = run_tool(tool, ctr20, root(20), trash(20), "--contour")
        case("⑳ --contour при базе, где role_sessions без transcript_id → код 2 «не проверено», "
             "сводка не печатается",
             code == 2 and "не проверено: роли не читаются" in out and "закрытый чат" not in out,
             f"код {code} (ждём 2) · «не проверено: роли не читаются»: "
             f"{'не проверено: роли не читаются' in out} · «закрытый чат» в выводе: {'закрытый чат' in out}")

        # ── ㉑ --apply без ссылок и с чужой базой ──
        ctr21 = SANDBOX / "ctr21"
        tiny_contour_db(ctr21 / ".mezosync" / "mezosync.db", role, tid, with_events=False)
        db21b = SANDBOX / "db21b" / "other.db"
        tiny_contour_db(db21b, role, tid)
        folder(scratch(21, cont=contour_dir_name(ctr21)), n("x21"))
        folder(scratch(21), n("y21"))
        before = fingerprint(root(21))
        c_a, o_a, _t = run_tool(tool, ctr21, root(21), trash(21), "--role", role, "--apply",
                                "--owner-word", word, role=role)
        c_b, o_b, _t = run_tool(tool, stand, root(21), trash(21), "--role", role, "--apply",
                                "--owner-word", word, "--db", str(db21b), role=role)
        after = fingerprint(root(21))
        ok_a = c_a == 2 and "без ссылок" in o_a
        ok_b = c_b == 2 and "только с живой базой" in o_b
        case("㉑ --apply при базе без backlog_events (ссылки не прочитать) → код 2; --apply с --db не "
             "живой базы → код 2; дерево не тронуто",
             ok_a and ok_b and before == after,
             f"без backlog_events: код {c_a}, {ok_a} · --db не живой: код {c_b}, {ok_b} · отпечаток: "
             f"{'равен' if before == after else 'ИЗМЕНИЛСЯ — ' + fp_diff(before, after)}")

        # ── ㉒ проверка прихода в корзину ──
        spec = importlib.util.spec_from_file_location(f"scratch_folders_copy_{token}", str(tool))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod          # dataclasses ищут свой модуль в sys.modules
        spec.loader.exec_module(mod)
        came = mod.arrived_words((5, 1000), (6, 1000 + 4096), 4096)
        no_item = mod.arrived_words((5, 1000), (5, 1000 + 4096), 4096)
        no_size = mod.arrived_words((5, 1000), (6, 1010), 4096)
        case("㉒ проверка прихода в корзину: выросли и предметы, и место → пришла; не выросло число "
             "предметов или место → «мимо корзины»",
             came is None and no_item is not None and no_size is not None,
             f"выросло всё: {came!r} (ждём None) · предметов столько же: {no_item!r} · место выросло "
             f"на 10 байт из 4096: {no_size!r}")

        # ═══ ИТОГ: счёт случаев и покрытие поломками — из словаря, а не числом в тексте ═══
        covered = set().union(*(set(v) for v in BREAK_FAILS.values()))
        covered_run = [x for x in RUN_IDS if x in covered]
        uncovered = [x for x in RUN_IDS if x not in covered]
        unknown = sorted(covered - set(RUN_IDS) - set(SKIPPED))
        print("")
        mismatch = False
        if break_name:
            expected_fail = set(BREAK_FAILS[break_name])
            actual_fail = set(FAILED)
            mismatch = expected_fail != actual_fail
            if not mismatch:
                print(f"🧪 ожидание поломки «{break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно "
                      f"{' '.join(x for x in RUN_IDS if x in actual_fail)}")
                # Поломка поймана как записано — стенд с копией живой базы хранить незачем;
                # код выхода прежний (карточка #657, пункт (3), записка #5437)
                mezo_stand.expected_break()
            else:
                print(f"⚠️ ожидание поломки «{break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
                      f"{' '.join(sorted(expected_fail)) or 'ничего'}, провалены "
                      f"{' '.join(x for x in RUN_IDS if x in actual_fail) or 'ничего'}")
        print(f"ИТОГ: {GREENS} из {CASES} · различающих {DIFFER}, из них покрыто нарочной поломкой "
              f"из словаря {len(covered_run)} (список провалов каждой поломки записан до прогона; "
              f"совпадение проверяет прогон с --break <имя>) · ни одной поломкой не покрыты: "
              f"{' '.join(uncovered) if uncovered else 'нет'}"
              + (f" · не проверены: {' '.join(SKIPPED)}" if SKIPPED else ""))
        if unknown:
            print(f"⚠️ словарь поломок расходится со случаями: номера без случая — {' '.join(unknown)}")
        if GREENS != CASES or mismatch:
            return 1
        return 2 if SKIPPED else 0
    finally:
        if SANDBOX is not None:
            unlink_junctions(SANDBOX)
        mezo_stand.release(sandbox)


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
