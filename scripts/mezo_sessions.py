# -*- coding: utf-8 -*-
"""mezo_sessions.py — ЧТЕНИЕ хранилища сессий приложения (карточка #649).

ПРЕДМЕТ. Хранилище сессий приложения держит по одному файлу `<a>/<b>/local_<uuid>.json`
на каждую сессию. Где оно лежит — раздел «ОТКУДА БЕРЁТСЯ ПУТЬ» ниже. Из него читаются:
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

ОТКУДА БЕРЁТСЯ ПУТЬ (issue 34 пакета, карточка #833). Порядок, первое подходящее:
    задан вызовом ............... read_store(path) — приёмки на подложном хранилище, --session-store
    переменная MEZO_SESSION_STORE  явная настройка сильнее догадки
    рядом с копией приложения ... каталоги `claude-code-sessions` выше исполняемого файла из
                                   CLAUDE_CODE_EXECPATH (ближайший первым). Приложение, запущенное
                                   ВТОРОЙ копией с отдельным каталогом данных, держит сессии там,
                                   а не в стандартном месте (замер 23.11: на четыре уровня выше файла)
    запасной стандартный путь ... %APPDATA%/Claude/claude-code-sessions — последним
Из нескольких найденных кандидатов берётся тот, в котором есть ТЕКУЩАЯ сессия
(CLAUDE_CODE_HOST_SESSION_ID); её нет ни в одном — первый по порядку, и это сказано словами.
Источник пути печатает вызывающий (SessionStore.describe()): при двух носителях расхождение
видно, только когда источник назван.

КОНТРОЛЬНОЕ СЛОВО (issue 34, п. 1). Хранилище «найдено» — каталог есть и читается, — но это
не доказывает, что оно НАШЕ: чужое хранилище даёт «не найден» у каждой роли, и такой ответ
неотличим от «все наши сессии мертвы». Поэтому после чтения проверяется, есть ли в нём
текущая сессия:
    current_found = True ..... есть — хранилище наше
    current_found = False .... нет — хранилище, ВЕРОЯТНО, ЧУЖОЕ (SessionStore.foreign); судить по
                               нему о ролях нельзя, trusted() превращает его в «сверить нечем»
    current_found = None ..... сверять не с чем: переменная не задана (терминал, стенд приёмки)
                               или её значение не вида «local_…» (сессия не из этого хранилища)

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
К первому исходу добавлен признак foreign (см. «КОНТРОЛЬНОЕ СЛОВО»): прочитано, но не наше.
"""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from pathlib import Path

ENV_OVERRIDE = "MEZO_SESSION_STORE"
ENV_HOST_SESSION = "CLAUDE_CODE_HOST_SESSION_ID"   # sessionId текущей сессии, вида «local_…»
ENV_APP_EXEC = "CLAUDE_CODE_EXECPATH"               # исполняемый файл ЭТОЙ копии приложения
DEFAULT_SUBPATH = ("Claude", "claude-code-sessions")
STORE_DIRNAME = "claude-code-sessions"
# Сколько каталогов вверх от файла копии приложения смотреть. Замер 23.11: хранилище —
# на четвёртом (<каталог данных>/claude-code/<версия>/<сборка>/claude.exe); запас — на смену раскладки.
APP_COPY_LEVELS = 6

SOURCE_ARGUMENT = "задан вызовом"
SOURCE_ENV = f"переменная {ENV_OVERRIDE}"
SOURCE_APP_COPY = f"рядом с копией приложения ({ENV_APP_EXEC})"
SOURCE_FALLBACK = "запасной стандартный путь (APPDATA)"


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
    source: str | None = None           # откуда взят путь — одна из SOURCE_* выше
    choice_note: str | None = None      # как выбран путь, когда кандидатов было несколько
    current_session: str | None = None  # текущая сессия (переменная) — или None, не задана
    current_found: bool | None = None   # контрольное слово: True · False · None (сверять не с чем)

    @property
    def foreign(self) -> bool:
        """Прочитано, но текущей сессии в нём нет — хранилище, вероятно, не наше."""
        return self.found and self.current_found is False

    def describe(self) -> str:
        """Путь и источник одной строкой — для печати рядом с любым выводом по хранилищу."""
        text = f"{self.path} — {self.source or 'источник не назван'}"
        if self.choice_note:
            text += f"; {self.choice_note}"
        return text

    def control_note(self) -> str:
        """Контрольное слово словами — для строки рядом с итогом проверки."""
        if self.current_found is True:
            return "текущая сессия в нём есть"
        if self.current_found is False:
            return f"текущей сессии «{self.current_session}» в нём НЕТ"
        if self.current_session:
            return (f"своё ли оно — не проверено: {ENV_HOST_SESSION} не вида «local_…»")
        return f"своё ли оно — не проверено: переменная {ENV_HOST_SESSION} не задана"


def current_session_id() -> str | None:
    """sessionId текущей сессии из переменной приложения — или None, не задана."""
    value = os.environ.get(ENV_HOST_SESSION, "").strip()
    return value or None


def _checkable(session_id: str | None) -> bool:
    """Сверять ли контрольное слово: хранилище держит только сессии вида «local_…»."""
    return bool(session_id) and session_id.startswith("local_")


def fallback_store_path() -> Path:
    """%APPDATA%/Claude/claude-code-sessions. APPDATA пуст (не Windows / не задана) —
    путь возвращается всё равно, читатель ниже сам скажет «не найдено» словами."""
    appdata = os.environ.get("APPDATA", "").strip()
    return Path(appdata, *DEFAULT_SUBPATH) if appdata else Path(*DEFAULT_SUBPATH)


def app_copy_candidates() -> list[Path]:
    """Каталоги `claude-code-sessions`, СУЩЕСТВУЮЩИЕ выше файла копии приложения, ближайший первым."""
    exe = os.environ.get(ENV_APP_EXEC, "").strip()
    if not exe:
        return []
    found = []
    for parent in list(Path(exe).parents)[:APP_COPY_LEVELS]:
        candidate = parent / STORE_DIRNAME
        try:
            if candidate.is_dir():
                found.append(candidate)
        except OSError:
            continue
    return found


def _same_dir(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _holds_session(store_path: Path, session_id: str) -> bool:
    """Есть ли в каталоге файл этой сессии — по имени файла, без разбора содержимого
    (выбор кандидата; само контрольное слово судит разобранные записи в read_store)."""
    wanted = f"{session_id}.json"
    try:
        return any(f.name == wanted for f in store_path.rglob("local_*.json"))
    except OSError:
        return False


def choose_store() -> tuple[Path, str, str | None]:
    """→ (путь, источник, пояснение выбора) по порядку из шапки модуля."""
    override = os.environ.get(ENV_OVERRIDE, "").strip()
    if override:
        return Path(override), SOURCE_ENV, None
    candidates = [(p, SOURCE_APP_COPY) for p in app_copy_candidates()]
    fallback = fallback_store_path()
    if fallback.is_dir() and not any(_same_dir(fallback, p) for p, _ in candidates):
        candidates.append((fallback, SOURCE_FALLBACK))
    if not candidates:
        note = ("рядом с копией приложения каталога сессий нет"
                if os.environ.get(ENV_APP_EXEC, "").strip() else None)
        return fallback, SOURCE_FALLBACK, note
    current = current_session_id()
    if _checkable(current):
        for path, source in candidates:
            if _holds_session(path, current):
                note = (f"кандидатов {len(candidates)}, текущая сессия — в этом"
                        if len(candidates) > 1 else None)
                return path, source, note
        path, source = candidates[0]
        note = (f"текущей сессии нет ни в одном из {len(candidates)} кандидатов — взят первый"
                if len(candidates) > 1 else None)
        return path, source, note
    path, source = candidates[0]
    note = (f"кандидатов {len(candidates)}, текущая сессия неизвестна — взят первый"
            if len(candidates) > 1 else None)
    return path, source, note


def default_store_path() -> Path:
    """Путь к хранилищу по порядку из шапки модуля (без чтения содержимого)."""
    return choose_store()[0]


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


def _read_store_at(store_path: Path) -> SessionStore:
    """Прочитать хранилище по готовому пути — без выбора пути и без контрольного слова."""
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


def read_store(path: str | Path | None = None) -> SessionStore:
    """Прочитать хранилище целиком. `path` — для проверок на подложном хранилище;
    без аргумента путь выбирает choose_store(). Контрольное слово считается в обоих случаях:
    и подложный путь, и настройка могут указать на чужое хранилище."""
    if path is not None:
        store_path, source, note = Path(path), SOURCE_ARGUMENT, None
    else:
        store_path, source, note = choose_store()
    store = _read_store_at(store_path)
    current = current_session_id()
    current_found = None
    if store.found and _checkable(current):
        current_found = any(r.session_id == current for r in store.sessions)
    error = store.error
    if not store.found:
        # Н3 приёмки COORD (карточка #833): «не найдено» называет, ОТКУДА взят путь и что
        # показал поиск, — иначе «искала рядом с копией приложения — пусто» не отличить от
        # «не искала». Одно место на всех вызывающих: проверку ролей, записку, запись адреса.
        error = f"{error}; путь — {source}" + (f"; {note}" if note else "")
    return dataclasses.replace(store, source=source, choice_note=note, error=error,
                               current_session=current, current_found=current_found)


def foreign_words(store: SessionStore) -> str:
    """Почему по хранилищу нельзя судить — одной фразой, одинаковой у всех вызывающих."""
    return (f"хранилище сессий приложения, вероятно, НЕ НАШЕ: текущей сессии "
            f"«{store.current_session}» в нём нет ({store.describe()})")


def trusted(store: SessionStore) -> SessionStore:
    """Хранилище, по которому можно судить о ролях: прочитанное ЧУЖОЕ превращается
    в «сверить нечем» (found=False) с причиной словами; остальное возвращается как есть."""
    if not store.foreign:
        return store
    return dataclasses.replace(store, found=False, sessions=(), error=foreign_words(store))


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
