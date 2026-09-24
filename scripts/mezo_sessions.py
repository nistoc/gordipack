# -*- coding: utf-8 -*-
"""mezo_sessions.py — ЧТЕНИЕ хранилища сессий приложения (карточка #649).

ПРЕДМЕТ. Хранилище сессий приложения (по умолчанию `%APPDATA%/Claude/claude-code-sessions`,
переопределяется переменной среды MEZO_SESSION_STORE) держит по одному файлу
`<a>/<b>/local_<uuid>.json` на каждую сессию. Из него читаются:
    sessionId ..... = наш role_sessions.session_id — им ДОСТАВЛЯЮТСЯ сообщения
                      (mcp__ccd_session_mgmt__send_message(session_id=…))
    cliSessionId .. = наш role_sessions.transcript_id — имя файла записи разговора
                      (`~/.claude/projects/<проект>/<cliSessionId>.jsonl`); ИМЕННО это
                      значение хук получает на входе как «session_id» своего вызова —
                      другой предмет, чем sessionId выше, хотя слово то же самое
    title ......... заголовок чата — по договору «имя в адресе без «[…]»» совпадает
                      с именем, которое роль пишет в role_sessions.address
    isArchived .... архивная сессия НЕ живая: адресат её не откроет
    cwd ........... рабочий каталог, которым сессия была открыта — сверяется с каталогом
                      КОНТУРА (не с каталогом, откуда позван сам инструмент)
    lastActivityAt  час последней активности, миллисекунды эпохи (для чтения человеком,
                      сверка на нём не строится — час не входит ни в одно решение приёмки)

⛔ ЧЕГО ЭТОТ МОДУЛЬ НЕ ДЕЛАЕТ: не пишет в хранилище (оно принадлежит приложению, не
контуру), не решает, годится ли сессия для записи в role_sessions, — это решает вызывающий
(signal-templates.py / guard-role-sessions-live.py), этот модуль только читает и отдаёт факты.

РЯДОМ С ФАЙЛАМИ СЕССИЙ лежат `deleted_*` и `archived-sessions.idx` — их эта функция
НЕ ЧИТАЕТ (первые — не сессия, второй — не JSON одной сессии).

ТРИ ИСХОДА ЧТЕНИЯ, И ЭТО НЕ ОДИН СПИСОК:
    хранилище прочитано ......... SessionStore.found = True, sessions — список (может
                                   быть пустым, если сессий правда нет — это НЕ то же
                                   самое, что «хранилища нет»)
    хранилища нет / не читается . SessionStore.found = False, error — причина словами.
                                   Пустой список при found=False НЕ ВОЗВРАЩАЕТСЯ никогда:
                                   вызывающий обязан различить «сверить нечем» от
                                   «сверено, живых нет» — это разные слова в отказе.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ENV_OVERRIDE = "MEZO_SESSION_STORE"
DEFAULT_SUBPATH = ("Claude", "claude-code-sessions")


@dataclass(frozen=True)
class SessionRecord:
    """Один файл хранилища, разобранный в факты."""
    session_id: str                 # sessionId — доставка (role_sessions.session_id)
    transcript_id: str | None       # cliSessionId — опознание хуком (role_sessions.transcript_id)
    title: str | None
    archived: bool
    cwd: str | None
    last_activity: int | None       # мс эпохи, как записано полем lastActivityAt
    path: Path                      # откуда прочитано — для разбора беды рукой


@dataclass(frozen=True)
class SessionStore:
    """Итог чтения хранилища целиком. found=False — ОТДЕЛЬНЫЙ исход, не путать с пустым
    sessions: пустой список бывает у НАЙДЕННОГО, но пустого хранилища."""
    found: bool
    path: Path
    sessions: tuple[SessionRecord, ...]
    error: str | None = None


def default_store_path() -> Path:
    """Путь к хранилищу: переменная среды MEZO_SESSION_STORE — если задана, иначе
    %APPDATA%/Claude/claude-code-sessions. APPDATA пуст (не Windows / не задана) —
    возвращается путь всё равно, читатель ниже сам скажет «не найдено» словами."""
    override = os.environ.get(ENV_OVERRIDE, "").strip()
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA", "").strip()
    return Path(appdata, *DEFAULT_SUBPATH) if appdata else Path(*DEFAULT_SUBPATH)


def _parse_one(path: Path) -> SessionRecord | None:
    """Один файл → запись, либо None — нечитаемый/не тот формат файл молча пропускается
    (соседний мусор в каталоге сессий — не повод уронить чтение всего хранилища)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    session_id = data.get("sessionId")
    if not session_id:
        return None
    return SessionRecord(
        session_id=session_id,
        transcript_id=data.get("cliSessionId") or None,
        title=data.get("title"),
        archived=bool(data.get("isArchived")),
        cwd=data.get("cwd"),
        last_activity=data.get("lastActivityAt"),
        path=path,
    )


def read_store(path: str | Path | None = None) -> SessionStore:
    """Прочитать хранилище целиком. `path` — для проверок на подложном хранилище;
    без аргумента берётся default_store_path()."""
    store_path = Path(path) if path is not None else default_store_path()
    if not store_path.is_dir():
        return SessionStore(found=False, path=store_path, sessions=(),
                            error=f"хранилище сессий приложения не найдено ({store_path})")
    records: list[SessionRecord] = []
    try:
        candidates = sorted(store_path.rglob("local_*.json"))
    except OSError as e:
        return SessionStore(found=False, path=store_path, sessions=(),
                            error=f"хранилище сессий приложения не читается ({store_path}): {e}")
    for f in candidates:
        # deleted_* сюда не попадают по маске имени (та требует префикс local_); проверка
        # НАЗВАНА ЯВНО, чтобы будущая правка маски не открыла им дорогу молча.
        if f.name.startswith("deleted_"):
            continue
        rec = _parse_one(f)
        if rec is not None:
            records.append(rec)
    return SessionStore(found=True, path=store_path, sessions=tuple(records), error=None)


def find_by_session_id(store: SessionStore, session_id: str) -> SessionRecord | None:
    """Запись по session_id (sessionId, «local_…») — или None, её в хранилище нет."""
    for rec in store.sessions:
        if rec.session_id == session_id:
            return rec
    return None


def live_sessions_for_cwd(store: SessionStore, cwd: str) -> list[SessionRecord]:
    """Живые (не архивные) сессии с ТЕМ ЖЕ рабочим каталогом — сравнение путей НОРМАЛИЗУЕТ
    регистр и разделители (Windows не различает регистр пути, а разделители встречаются
    обеих форм в разных записях), но не более того: близкие, но разные пути не считаются
    одним и тем же контуром."""
    target = _normalize_path(cwd)
    return [r for r in store.sessions
            if not r.archived and r.cwd and _normalize_path(r.cwd) == target]


def _normalize_path(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))
