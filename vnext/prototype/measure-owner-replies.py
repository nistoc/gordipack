#!/usr/bin/env python
# -*- coding: utf-8 -*-
# plain-words: файл ОБСУЖДАЕТ прежние слова — упоминания законны (перечень запретных слов — предмет замера, проба 4)
"""
Замер качества ответов ролей владельцу — ТОЛЬКО ЧТЕНИЕ.

ЗАЧЕМ: владелец 24.09.2026 10:31 UTC велел сократить правила свода под основную
модель так, чтобы качество ответов заметно не ухудшилось (сокращено 13 правил на
72%). Этот инструмент снимает ЧЕТЫРЕ пробы качества за фиксированное окно времени,
чтобы через две недели прогнать ТЕМ ЖЕ файлом («после», другое окно) и сравнить
с сегодняшними числами («до»).

СПОСОБ ФИКСИРОВАН — см. константы CORRECTION_MARKERS / ROLLBACK_MARKERS /
STEM_FORMS ниже и функцию describe_method(). Между прогонами «до» и «после» этот
файл не переписывается, меняется только --since/--until.

ВХОД. Верхнеуровневые файлы записей разговоров (*.jsonl) в каталогах проектов
Claude Code, отвечающих контуру C:\\guts\\.atlas и его подкаталогам — каталог
называется "C--guts--atlas" или начинается на "C--guts--atlas-" (так Claude Code
превращает путь в имя каталога: ':' '\\' '.' -> '-'). Вложенные каталоги сеансов
помощников (под-агенты) НЕ читаются — они лежат рядом с *.jsonl как одноимённые
каталоги той же UUID, и это НАРОЧНОЕ сужение охвата по прямому наказу задачи.

РАЗЛИЧЕНИЕ «слово, набранное владельцем» ПРОТИВ «вставка среды» — ИМПОРТОМ модуля
<КОНТУР>/vnext-tools/find-owner-word.py (не копией куска кода). Переиспользованы
его функции происхождение() и служебное(), и константа ОБЁРТКА_БУДИЛЬНИКА_СТАРАЯ.
Причина импорта, а не копии: у образца это живой, уже проверенный на граничных
случаях разбор (см. историю правок в его докстринге) — копия неизбежно разошлась бы
с ним при следующей находке новой ложной формы, импорт расходиться не может.

РОЛЬ ЧАТА определяется тремя попытками по порядку:
  1) таблицы role_sessions / role_sessions_history живой БД mezosync (mode=ro) —
     ищем UUID этого файла в столбце transcript_id;
  2) иначе — самая частая роль, найденная в вызовах `--role X` инструментов
     .mezosync/scripts внутри ЭТОГО чата (только в командах Bash/PowerShell);
  3) иначе — «не определена».

Только чтение: mezosync.db открывается ИСКЛЮЧИТЕЛЬНО как file:...?mode=ro (uri=True).
В ленту, карточки, базу, память ролей этот инструмент не пишет НИЧЕГО и не зовёт
ни одного из пишущих инструментов .mezosync/scripts.

ЗОВУТ ТАК:
    python measure-owner-replies.py --since "2026-09-17 10:31" --until "2026-09-24 10:31" --out before.json
Время --since/--until — UTC, без смещения, форма "ГГГГ-ММ-ДД ЧЧ:ММ" (секунды необязательны).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import io
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

# ─────────────────────────── пути по умолчанию (переопределяются флагами) ─────────
# ⚖️ Пути ВЫВОДЯТСЯ, а не впечатаны (#153): контур — от расположения файла через
# mezo_paths (или MEZO_CONTAINER), записи разговоров — от домашнего каталога. Имя каталога
# записей Claude Code строит из пути контура, заменяя каждый знак, кроме латинских букв и
# цифр, на '-' (путь контура <КОНТУР> даёт C--guts--atlas); выводим тем же правилом,
# иначе в соседнем контуре инструмент молча мерил бы чужие чаты или не нашёл бы своих
# (правка PROTO при установке, 24.09.2026).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
CONTAINER = mezo_paths.container_root(__file__)
DEFAULT_PROJECTS_ROOT = Path.home() / ".claude" / "projects"
DEFAULT_DB_PATH = mezo_paths.live_db(__file__)
DEFAULT_FIND_OWNER_WORD = HERE / "find-owner-word.py"
DEFAULT_CLAUDE_MD = CONTAINER / "CLAUDE.md"
PROJECT_DIR_PREFIX = re.sub(r"[^A-Za-z0-9]", "-", str(CONTAINER))

EXAMPLE_LIMIT_CHARS = 80          # требование задачи: примеры «≤ 80 знаков»
EXAMPLES_PER_ROLE = 2             # проба 3 и проба 4: по 2 примера на роль
DIAGNOSTIC_EXAMPLES_CAP = 3       # проба 1/2: доп. примеры для ручной проверки (не требование задачи, для отчёта)
LONG_REPLY_CHARS = 800            # порог «длинного» ответа
STALE_GAP_DAYS = 2.0              # см. STALE_GAP_NOTE ниже

# ═════════════════════════ переиспользование find-owner-word.py ═══════════════════


def load_find_owner_word(path: Path):
    """Импортировать find-owner-word.py как модуль (не копия куска кода).

    Файл лежит с дефисом в имени, поэтому обычный `import` не годится —
    грузим по пути через importlib. Модуль на верхнем уровне сам настраивает
    UTF-8 stdout (безвредно перевызвать ещё раз) и не исполняет main() при
    импорте (он под `if __name__ == "__main__"`).
    """
    if not path.is_file():
        sys.exit(f"⛔ ОТКАЗ: не нашёл образец разбора «слово владельца vs вставка среды» — {path}")
    spec = importlib.util.spec_from_file_location("find_owner_word", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    for needed in ("происхождение", "служебное", "ОБЁРТКА_БУДИЛЬНИКА_СТАРАЯ"):
        if not hasattr(module, needed):
            sys.exit(f"⛔ ОТКАЗ: в образце {path} не нашёл {needed} — он мог измениться несовместимо.")
    return module


# ═════════════════════════════ проба 1 / проба 2 — метки ══════════════════════════
# Списки ДОСЛОВНО из наказа задачи ("список признаков — постоянной в коде и в выводе").
# Не расширяю сам: расширение не проверено этим же способом на прогоне «после» и
# сломало бы сравнимость чисел «до»/«после».
CORRECTION_MARKERS = [
    "не понимаю", "что такое", "что значит", "я же", "опять", "неправильно",
    "не то", "ошибк", "забыл", "почему не", "перемерь", "перепроверь", "просил",
]
ROLLBACK_MARKERS = [
    "отмен", "откат", "верни", "передумал", "не надо было",
]

# ═════════════════════════════ проба 4 — словарь запрещённых слов ═════════════════
# Формы для поиска ПО ОСНОВЕ СЛОВА (словоформы) — подобраны вручную под особенности
# русской морфологии (бегущие гласные и т.п.), чтобы не ловить случайные соседние
# слова короткой общей приставкой (напр. «ворот» ловит «ворота», но не «поворот» —
# перед формой всегда требуется граница слова \b, а не «содержит где угодно»).
# Текст уже нормализован (нижний регистр, ё→е) ДО сравнения — см. normalize_text().
STEM_FORMS: dict[str, list[str]] = {
    "сторож": ["сторож"],
    "решето": ["решет"],
    "градусник": ["градусник"],
    "рубеж": ["рубеж"],
    "витрина": ["витрин"],
    "слепок": ["слепок", "слепка", "слепку", "слепком", "слепке", "слепки", "слепков"],
    "курсор": ["курсор"],
    "мутант": ["мутант"],
    "укус": ["укус"],
    "прибор": ["прибор"],
    "врезка": ["врезк"],
    "аренда": ["аренд"],
    "дверь": ["двер"],
    "гейт": ["гейт"],
    "ворота": ["ворот"],
    "ведро": ["ведр"],
    "хребет": ["хреб"],
    "паёк": ["паек", "пайк"],           # после ё→е: "паёк"->"паек"; "пайка/пайку/…" -> "пайк"
    "заход": ["заход"],
    "синк": ["синк"],
    "надгробие": ["надгроб"],
    "дормант": ["дормант"],
    "могила": ["могил"],                # доп. слово из БД (rules.plain-words), не в списке CLAUDE.md
    "единый вход": ["единый вход"],     # доп. фраза из БД — синоним «двери» в правиле
    "красное/зелёное (о проверках)": ["красн", "зелен"],  # особый режим ниже
}
# Слово владельца 2026-08-29: «красное/зелёное» запрещены ТОЛЬКО рядом со словом
# «проверк» (окно 40 знаков) — иначе это обычная речь про цвета/светофоры/RAG-статусы.
PROXIMITY_REQUIRED: dict[str, str] = {
    "красное/зелёное (о проверках)": "проверк",
}
PROXIMITY_WINDOW = 40


def normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е")


def strip_code_fences(text: str) -> str:
    """Убрать содержимое ```тройных блоков кода``` — проба 4 считает вне них.

    Метод грубый (разбор по чётности вхождений ```), но безопасный: при нечётном
    числе меток (незакрытый блок) последний кусок останется отнесён к «внутри
    кода» — то есть скорее НЕДОсчитает запрещённое слово, чем перепишет владельцу
    находку, которой не было. Для этой пробы недосчёт безопаснее перебора.
    """
    parts = text.split("```")
    return " ".join(parts[i] for i in range(0, len(parts), 2))


def forbidden_word_hits(reply_text: str) -> list[str]:
    """Какие подписи словаря пробы 4 нашлись в тексте ответа (вне блоков кода)."""
    visible = strip_code_fences(reply_text)
    norm = normalize_text(visible)
    hits: list[str] = []
    for label, forms in STEM_FORMS.items():
        proximity = PROXIMITY_REQUIRED.get(label)
        found = False
        for form in forms:
            for m in re.finditer(r"\b" + re.escape(form), norm):
                if proximity is None:
                    found = True
                    break
                window = norm[max(0, m.start() - PROXIMITY_WINDOW): m.end() + PROXIMITY_WINDOW]
                if proximity in window:
                    found = True
                    break
            if found:
                break
        if found:
            hits.append(label)
    return hits


def fetch_plain_words_rule_body(con: sqlite3.Connection) -> str:
    cur = con.cursor()
    cur.execute(
        "SELECT body FROM rules WHERE rule_key='plain-words' ORDER BY version DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else ""


def fetch_claude_md_local_words(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Местные запретные слова[^:]*:\s*(.*?)\.\s*Замены", text, re.S)
    if not m:
        return []
    words = [re.sub(r"\s+", " ", w).strip() for w in m.group(1).split("·")]
    return [w for w in words if w]


DICT_ENTRY_RE = re.compile(r"([^·\n]+?)\s*→\s*([^·\n]+)")


def extract_db_dictionary_labels(rule_body: str) -> list[str]:
    """Левые (запрещённые) слова из тела правила plain-words — для сверки охвата."""
    labels = []
    for left, _right in DICT_ENTRY_RE.findall(rule_body):
        left_no_paren = re.sub(r"\([^)]*\)", "", left).strip()
        for part in left_no_paren.split(","):
            part = part.strip()
            if part:
                labels.append(part)
    return labels


def check_dictionary_coverage(labels: list[str]) -> list[str]:
    """Диагностика: какие слова из БД/CLAUDE.md наш STEM_FORMS явно не покрывает.

    Не идеальный разбор (см. комментарий внутри) — проверяет, есть ли хоть один
    токен подписи, чья форма пересекается (по приставке в любую сторону) хоть с
    одной заготовленной формой. Нужен, чтобы человек заметил, если словарь
    правила вырос словом, для которого никто не подобрал словоформы.
    """
    all_forms = [f for forms in STEM_FORMS.values() for f in forms]
    unmatched = []
    for label in labels:
        norm_label = normalize_text(label)
        tokens = norm_label.split() or [norm_label]
        covered = False
        for tok in tokens:
            for form in all_forms:
                if tok.startswith(form) or form.startswith(tok):
                    covered = True
                    break
            if covered:
                break
        if not covered:
            unmatched.append(label)
    return unmatched


# ═════════════════════════════ разбор одного файла записи ═════════════════════════

NEEDS_PARSE_MARKERS = ('"type":"user"', '"type": "user"', '"type":"assistant"', '"type": "assistant"')
ROLE_FLAG_RE = re.compile(r"--role[= ]+([A-Z][A-Z0-9_]{1,15})\b")
COMMAND_NAME_RE = re.compile(r"<command-name>(.*?)</command-name>", re.S)
COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.S)


@dataclass
class OwnerEvent:
    line_no: int
    ts: str
    text: str


@dataclass
class ReplyPair:
    reply_line_no: int
    reply_text: str
    reply_ts: str
    owner_line_no: int
    owner_ts: str


@dataclass
class ChatScan:
    owner_events: list[OwnerEvent] = field(default_factory=list)
    reply_pairs: list[ReplyPair] = field(default_factory=list)
    role_tally: Counter = field(default_factory=Counter)
    lines_total: int = 0


def extract_owner_text(fow, raw_text: str) -> Optional[str]:
    """Текст владельца из одного блока — либо None (пропустить блок).

    Повторяет классификацию «человек»+«текст» из find-owner-word.py: отсекает
    старую ложную обёртку будильника, разворачивает косую команду, набранную
    руками, отсекает пустое и служебные вставки среды (fow.служебное).
    """
    stripped = raw_text.lstrip()
    if stripped.startswith(fow.ОБЁРТКА_БУДИЛЬНИКА_СТАРАЯ):
        return None
    if stripped.startswith("<command-"):
        name_m = COMMAND_NAME_RE.search(raw_text)
        args_m = COMMAND_ARGS_RE.search(raw_text)
        plain = ((name_m.group(1).strip() if name_m else "") + " " +
                 (args_m.group(1).strip() if args_m else "")).strip()
        return plain or None
    if not raw_text.strip():
        return None
    if fow.служебное(raw_text):
        return None
    return raw_text


def assistant_reply_text(rec: dict) -> str:
    """Видимый владельцу текст одной assistant-записи (только текстовые блоки)."""
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n\n".join(p for p in parts if p).strip()


def scan_chat_file(path: Path, fow) -> ChatScan:
    """Один линейный проход файла: реплики владельца, пары «ответ→реплика»,
    частота --role в вызовах инструментов. Окно времени здесь НЕ применяется —
    фильтрация по --since/--until происходит после, при подсчёте (иначе первая
    в окне реплика владельца потеряла бы контекст «последний ответ ассистента»,
    если тот пришёл до границы окна).
    """
    scan = ChatScan()
    pending_reply: Optional[tuple[str, int, str]] = None  # (текст, номер_строки, timestamp)
    line_no = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line_no += 1
            if not any(marker in raw for marker in NEEDS_PARSE_MARKERS):
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            rtype = rec.get("type")

            if rtype == "assistant":
                if rec.get("isSidechain"):
                    continue
                content = rec.get("message", {}).get("content")
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        if block.get("name") not in ("Bash", "PowerShell"):
                            continue
                        blob = json.dumps(block.get("input", ""), ensure_ascii=False)
                        for m in ROLE_FLAG_RE.finditer(blob):
                            scan.role_tally[m.group(1)] += 1
                text = assistant_reply_text(rec)
                if text:
                    pending_reply = (text, line_no, rec.get("timestamp", ""))
                continue

            if rtype != "user" or rec.get("isSidechain"):
                continue
            origin_kind = fow.происхождение(rec)
            if origin_kind != "человек":
                continue
            ts = rec.get("timestamp", "")
            body = rec.get("message", {}).get("content")
            raw_texts: list[str] = []
            if isinstance(body, str):
                raw_texts = [body]
            elif isinstance(body, list):
                for block in body:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t:
                            raw_texts.append(t)
            for raw_text in raw_texts:
                owner_text = extract_owner_text(fow, raw_text)
                if owner_text is None:
                    continue
                scan.owner_events.append(OwnerEvent(line_no, ts, owner_text))
                if pending_reply is not None:
                    reply_text, reply_line_no, reply_ts = pending_reply
                    scan.reply_pairs.append(
                        ReplyPair(reply_line_no, reply_text, reply_ts, line_no, ts)
                    )
                pending_reply = None  # начинается новый ход
    scan.lines_total = line_no
    return scan


# ═════════════════════════════ время окна ══════════════════════════════════════════

def parse_ts(ts: str) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            return d
        return d.astimezone(dt.timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def parse_window_arg(value: str) -> dt.datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    sys.exit(f"⛔ ОТКАЗ: не разобрать время «{value}» — нужна форма ГГГГ-ММ-ДД ЧЧ:ММ (UTC).")


def in_window(ts: str, since: dt.datetime, until: dt.datetime) -> bool:
    t = parse_ts(ts)
    return t is not None and since <= t < until


# ═════════════════════════════ роль чата ═══════════════════════════════════════════

def load_role_map(con: sqlite3.Connection) -> dict[str, str]:
    """transcript_id -> роль, из role_sessions и role_sessions_history (mode=ro)."""
    mapping: dict[str, str] = {}
    cur = con.cursor()
    for table in ("role_sessions", "role_sessions_history"):
        cur.execute(
            f"SELECT role, transcript_id FROM {table} "
            f"WHERE transcript_id IS NOT NULL AND transcript_id <> ''"
        )
        for role, tid in cur.fetchall():
            mapping.setdefault(tid, role)
    return mapping


def resolve_role(transcript_id: str, role_tally: Counter, role_map: dict[str, str]) -> tuple[str, str]:
    if transcript_id in role_map:
        return role_map[transcript_id], "role_sessions.transcript_id"
    if role_tally:
        role, count = role_tally.most_common(1)[0]
        return role, f"частота --role в инструментах ({count} из {sum(role_tally.values())})"
    return "не определена", "нет признаков"


# ═════════════════════════════ обнаружение каталогов проекта ══════════════════════

def discover_project_dirs(projects_root: Path) -> list[Path]:
    if not projects_root.is_dir():
        sys.exit(f"⛔ ОТКАЗ МЕРИТЬ: каталога записей разговоров нет — {projects_root}")
    found = []
    for child in sorted(projects_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name == PROJECT_DIR_PREFIX or child.name.startswith(PROJECT_DIR_PREFIX + "-"):
            found.append(child)
    return found


def list_top_level_chats(project_dir: Path) -> list[Path]:
    """Только верхние файлы чатов — вложенные каталоги сеансов помощников НЕ трогаем."""
    return sorted(p for p in project_dir.iterdir() if p.is_file() and p.suffix == ".jsonl")


# ═════════════════════════════ агрегация по ролям ══════════════════════════════════

def snippet(text: str, limit: int = EXAMPLE_LIMIT_CHARS) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= limit else one_line[: limit - 1] + "…"


@dataclass
class RoleStats:
    role: str
    chats: set = field(default_factory=set)
    owner_msgs: int = 0
    corrections: int = 0
    rollbacks: int = 0
    revoke_rule_by_actor: int = 0
    replies: int = 0
    replies_long: int = 0
    replies_3parts: int = 0
    replies_3parts_long: int = 0
    replies_forbidden: int = 0
    replies_stale_gap: int = 0   # ответ отстоит от реакции владельца более чем на STALE_GAP_DAYS
    word_hit_replies: Counter = field(default_factory=Counter)
    examples_corrections: list = field(default_factory=list)
    examples_rollbacks: list = field(default_factory=list)
    examples_3parts: list = field(default_factory=list)
    examples_forbidden: list = field(default_factory=list)


def new_role_stats(role: str) -> RoleStats:
    return RoleStats(role=role)


def run_measurement(
    projects_root: Path,
    db_path: Path,
    fow_path: Path,
    claude_md_path: Path,
    since: dt.datetime,
    until: dt.datetime,
) -> dict:
    fow = load_find_owner_word(fow_path)

    if not db_path.is_file():
        sys.exit(f"⛔ ОТКАЗ МЕРИТЬ: базы mezosync нет по пути — {db_path}")
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        role_map = load_role_map(con)
        plain_words_body = fetch_plain_words_rule_body(con)
        db_labels = extract_db_dictionary_labels(plain_words_body)
        claude_md_labels = fetch_claude_md_local_words(claude_md_path)
        all_labels_seen = sorted(set(db_labels) | set(claude_md_labels))
        unmatched_labels = check_dictionary_coverage(all_labels_seen)

        window_days = (until - since).total_seconds() / 86400.0
        cur = con.cursor()
        since_s = since.strftime("%Y-%m-%d %H:%M:%S")
        until_s = until.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='revoke_rule' AND timestamp>=? AND timestamp<?",
            (since_s, until_s),
        )
        revoke_rule_total = cur.fetchone()[0]
        cur.execute(
            "SELECT actor_role, COUNT(*) FROM audit_log WHERE action='revoke_rule' "
            "AND timestamp>=? AND timestamp<? GROUP BY actor_role",
            (since_s, until_s),
        )
        revoke_rule_by_actor = dict(cur.fetchall())
        cur.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")
        all_audit_actions = [r[0] for r in cur.fetchall()]
    finally:
        con.close()

    project_dirs = discover_project_dirs(projects_root)
    if not project_dirs:
        sys.exit(f"⛔ ОТКАЗ МЕРИТЬ: под {projects_root} не нашёл ни одного каталога контура {CONTAINER} (ждал имя {PROJECT_DIR_PREFIX}).")

    roles: dict[str, RoleStats] = {}
    chat_lines: list[str] = []          # «роль каждого чата» — печатается в отчёте
    diag_examples = {"corrections": [], "rollbacks": []}

    chats_scanned = 0
    chats_with_data = 0
    role_method_tally = Counter()

    for project_dir in project_dirs:
        for chat_path in list_top_level_chats(project_dir):
            chats_scanned += 1
            transcript_id = chat_path.stem
            scan = scan_chat_file(chat_path, fow)
            role, method = resolve_role(transcript_id, scan.role_tally, role_map)
            role_method_tally[method.split("(")[0].split(".")[0]] += 1

            owner_in_window = [e for e in scan.owner_events if in_window(e.ts, since, until)]
            replies_in_window = [p for p in scan.reply_pairs if in_window(p.owner_ts, since, until)]

            if not owner_in_window and not replies_in_window:
                continue
            chats_with_data += 1
            chat_lines.append(
                f"  {transcript_id[:8]}… [{project_dir.name}] роль={role:<14} способ={method:<38} "
                f"реплик_владельца={len(owner_in_window):<4} ответов={len(replies_in_window)}"
            )

            rs = roles.setdefault(role, new_role_stats(role))
            rs.chats.add(transcript_id)
            rs.owner_msgs += len(owner_in_window)

            for ev in owner_in_window:
                low = ev.text.lower()
                corr_hits = [mark for mark in CORRECTION_MARKERS if mark in low]
                if corr_hits:
                    rs.corrections += 1
                    if len(rs.examples_corrections) < EXAMPLES_PER_ROLE:
                        rs.examples_corrections.append(
                            {"role": role, "chat": transcript_id[:8], "line": ev.line_no,
                             "ts": ev.ts, "markers": corr_hits, "text": snippet(ev.text)}
                        )
                    if len(diag_examples["corrections"]) < DIAGNOSTIC_EXAMPLES_CAP * 4:
                        diag_examples["corrections"].append(
                            {"role": role, "chat": transcript_id[:8], "line": ev.line_no,
                             "ts": ev.ts, "markers": corr_hits, "text": snippet(ev.text)}
                        )
                roll_hits = [mark for mark in ROLLBACK_MARKERS if mark in low]
                if roll_hits:
                    rs.rollbacks += 1
                    if len(rs.examples_rollbacks) < EXAMPLES_PER_ROLE:
                        rs.examples_rollbacks.append(
                            {"role": role, "chat": transcript_id[:8], "line": ev.line_no,
                             "ts": ev.ts, "markers": roll_hits, "text": snippet(ev.text)}
                        )
                    if len(diag_examples["rollbacks"]) < DIAGNOSTIC_EXAMPLES_CAP * 4:
                        diag_examples["rollbacks"].append(
                            {"role": role, "chat": transcript_id[:8], "line": ev.line_no,
                             "ts": ev.ts, "markers": roll_hits, "text": snippet(ev.text)}
                        )

            rs.revoke_rule_by_actor += revoke_rule_by_actor.get(role, 0)

            for p in replies_in_window:
                rs.replies += 1
                text = p.reply_text
                length = len(text)
                is_long = length >= LONG_REPLY_CHARS
                if is_long:
                    rs.replies_long += 1
                reply_dt, owner_dt = parse_ts(p.reply_ts), parse_ts(p.owner_ts)
                gap_days = ((owner_dt - reply_dt).total_seconds() / 86400.0
                            if reply_dt and owner_dt else None)
                is_stale = gap_days is not None and gap_days > STALE_GAP_DAYS
                if is_stale:
                    rs.replies_stale_gap += 1
                low = text.lower()
                has_done = "сделано" in low
                has_not_done = "не сделано" in low
                has_variant = ("вариант" in low) or ("на выбор" in low)
                three = has_done and has_not_done and has_variant
                if three:
                    rs.replies_3parts += 1
                    if is_long:
                        rs.replies_3parts_long += 1
                    if len(rs.examples_3parts) < EXAMPLES_PER_ROLE:
                        rs.examples_3parts.append(
                            {"role": role, "chat": transcript_id[:8], "line": p.reply_line_no,
                             "reply_ts": p.reply_ts, "owner_ts": p.owner_ts,
                             "gap_days": round(gap_days, 1) if gap_days is not None else None,
                             "length": length, "text": snippet(text)}
                        )
                hits = forbidden_word_hits(text)
                if hits:
                    rs.replies_forbidden += 1
                    for h in hits:
                        rs.word_hit_replies[h] += 1
                    if len(rs.examples_forbidden) < EXAMPLES_PER_ROLE:
                        rs.examples_forbidden.append(
                            {"role": role, "chat": transcript_id[:8], "line": p.reply_line_no,
                             "reply_ts": p.reply_ts, "owner_ts": p.owner_ts,
                             "gap_days": round(gap_days, 1) if gap_days is not None else None,
                             "words": hits, "text": snippet(text)}
                        )

    return {
        "since": since, "until": until, "window_days": window_days,
        "project_dirs": [str(p) for p in project_dirs],
        "chats_scanned": chats_scanned, "chats_with_data": chats_with_data,
        "role_method_tally": dict(role_method_tally),
        "chat_lines": chat_lines,
        "roles": roles,
        "revoke_rule_total": revoke_rule_total,
        "revoke_rule_by_actor": revoke_rule_by_actor,
        "all_audit_actions": all_audit_actions,
        "db_labels": db_labels,
        "claude_md_labels": claude_md_labels,
        "all_labels_seen": all_labels_seen,
        "unmatched_labels": unmatched_labels,
        "diag_examples": diag_examples,
        "fow_path": str(fow_path),
        "db_path": str(db_path),
    }


# ═════════════════════════════ печать отчёта ═══════════════════════════════════════

def describe_method() -> list[str]:
    return [
        "Проба 1 ПОПРАВКИ — сообщение владельца содержит (без учёта регистра) хотя бы одну метку: "
        + " · ".join(CORRECTION_MARKERS)
        + ". Считаются реплики происхождения «человек» (поле origin, см. find-owner-word.py); "
          "число за окно и в пересчёте на 7 суток, по ролям.",
        "Проба 2 ОТКАТЫ — метки: " + " · ".join(ROLLBACK_MARKERS)
        + ". Плюс отдельно из mezosync.db (mode=ro): audit_log.action='revoke_rule' за окно "
          "(другого действия «снятия правила» в audit_log нет — проверено списком DISTINCT action).",
        "Проба 3 ИТОГ ИЗ ТРЁХ ЧАСТЕЙ — ответ роли владельцу = текст последней assistant-записи "
        "(только текстовые блоки, без thinking/tool_use) перед следующей репликой владельца. "
        "Три части (без учёта регистра, простое вхождение подстроки): «сделано», «не сделано», "
        "«вариант» или «на выбор». Длинный ответ — от "
        f"{LONG_REPLY_CHARS} знаков.",
        "Проба 4 СЛОВА СЛОВАРЯ — та же выборка ответов, что и проба 3. Ищем вне ```блоков кода```, "
        "по основе слова (см. STEM_FORMS в коде), «красн/зелён» — только в пределах "
        f"{PROXIMITY_WINDOW} знаков от «проверк», иначе это обычная речь.",
        "СЛАБОЕ МЕСТО проб 3–4, названо вслух (не чинится этим прогоном, только считается): "
        "если роль ничего не писала текстом долго, а потом владелец просто написал снова, "
        "«ответом» становится СТАРЫЙ текст, ближайший по времени назад — он может быть не "
        f"связан с новым сообщением владельца по смыслу. Помечаю как «разрыв» ответы, где между "
        f"ответом и следующей репликой владельца прошло больше {STALE_GAP_DAYS:.0f} суток; их доля "
        "печатается отдельной строкой и не исключается из процентов проб 3–4 (исключение не было "
        "заказано, а придумывать порог отсева задним числом — значит менять способ между «до» и «после»).",
    ]


def fmt_pct(numer: int, denom: int) -> str:
    if denom == 0:
        return "—"
    return f"{100.0 * numer / denom:.0f}%"


def print_report(result: dict, out) -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    since, until = result["since"], result["until"]

    def p(*a):
        print(*a, file=out)

    p("=" * 100)
    p("ЗАМЕР КАЧЕСТВА ОТВЕТОВ РОЛЕЙ ВЛАДЕЛЬЦУ (только чтение) — способ фиксирован, см. ниже")
    p("=" * 100)
    p(f"Запущено: {now} UTC")
    p(f"Окно: --since {since:%Y-%m-%d %H:%M} UTC  --until {until:%Y-%m-%d %H:%M} UTC "
      f"({result['window_days']:.2f} суток)")
    p(f"БД координации (mode=ro): {result['db_path']}")
    p(f"Образец разбора слова владельца (импорт): {result['fow_path']}")
    p(f"Каталоги контура (найдены по имени '{PROJECT_DIR_PREFIX}' и '{PROJECT_DIR_PREFIX}-*'):")
    for d in result["project_dirs"]:
        p(f"  {d}")
    p(f"Чатов просмотрено (верхнеуровневых *.jsonl): {result['chats_scanned']} · "
      f"с данными в этом окне: {result['chats_with_data']}")
    p(f"Роль определена по способу: {result['role_method_tally']}")
    if result["unmatched_labels"]:
        p(f"⚠️ слова словаря без заготовленных словоформ (считаются грубо, по всей подписи целиком): "
          f"{result['unmatched_labels']}")
    p(f"Действия audit_log (для справки, все, что вообще бывают): {result['all_audit_actions']}")
    p("")
    p("СПОСОБ (фиксирован — при прогоне «после» не менять):")
    for line in describe_method():
        p(f"  · {line}")
    p("")
    p("Список слов пробы 4 (из mezosync.db rules.plain-words ∪ CLAUDE.md, объединено):")
    p("  " + " · ".join(STEM_FORMS.keys()))
    p("")
    p("-" * 100)
    p(f"РОЛИ ЧАТОВ — только чаты с данными в этом окне ({result['chats_with_data']} из {result['chats_scanned']}):")
    if result["chat_lines"]:
        for line in result["chat_lines"]:
            p(line)
    else:
        p("  (ни одного чата с данными в этом окне)")
    p("")
    p("-" * 100)
    p("ТАБЛИЦА: роль × 4 пробы")
    col = ("{role:<11}{chats:>6}{owner:>10} |{corr:>17} |{roll:>13}{revoke:>10} |"
           "{replies:>8}{p3:>9}{p3l:>15}{p4:>9}{stale:>9}")
    header = col.format(role="роль", chats="чатов", owner="реплик_вл",
                         corr="поправки ок/нед", roll="откат ок/нед", revoke="откат_БД",
                         replies="ответов", p3="3части%", p3l="3части%(long)", p4="forbid%",
                         stale="разрыв>2д")
    p(header)
    p("-" * len(header))

    roles = result["roles"]
    order = sorted(k for k in roles if k not in ("не определена",))
    if "не определена" in roles:
        order.append("не определена")

    totals = new_role_stats("ИТОГО")
    for role_key in order:
        rs = roles[role_key]
        wd = result["window_days"] or 1.0
        corr_week = rs.corrections * 7.0 / wd
        roll_week = rs.rollbacks * 7.0 / wd
        row = col.format(
            role=role_key, chats=len(rs.chats), owner=rs.owner_msgs,
            corr=f"{rs.corrections}/{corr_week:.1f}", roll=f"{rs.rollbacks}/{roll_week:.1f}",
            revoke=rs.revoke_rule_by_actor,
            replies=rs.replies, p3=fmt_pct(rs.replies_3parts, rs.replies),
            p3l=fmt_pct(rs.replies_3parts_long, rs.replies_long),
            p4=fmt_pct(rs.replies_forbidden, rs.replies),
            stale=f"{rs.replies_stale_gap}/{rs.replies}",
        )
        p(row)
        totals.chats |= rs.chats
        totals.owner_msgs += rs.owner_msgs
        totals.corrections += rs.corrections
        totals.rollbacks += rs.rollbacks
        totals.revoke_rule_by_actor += rs.revoke_rule_by_actor
        totals.replies += rs.replies
        totals.replies_long += rs.replies_long
        totals.replies_3parts += rs.replies_3parts
        totals.replies_3parts_long += rs.replies_3parts_long
        totals.replies_forbidden += rs.replies_forbidden
        totals.replies_stale_gap += rs.replies_stale_gap
        totals.word_hit_replies.update(rs.word_hit_replies)

    wd = result["window_days"] or 1.0
    p("-" * len(header))
    p(col.format(
        role="ИТОГО", chats=len(totals.chats), owner=totals.owner_msgs,
        corr=f"{totals.corrections}/{totals.corrections*7.0/wd:.1f}",
        roll=f"{totals.rollbacks}/{totals.rollbacks*7.0/wd:.1f}",
        revoke=totals.revoke_rule_by_actor,
        replies=totals.replies, p3=fmt_pct(totals.replies_3parts, totals.replies),
        p3l=fmt_pct(totals.replies_3parts_long, totals.replies_long),
        p4=fmt_pct(totals.replies_forbidden, totals.replies),
        stale=f"{totals.replies_stale_gap}/{totals.replies}",
    ))
    p("")
    p(f"«разрыв>2д» = «сколько из столбца „ответов“ / всего ответов»: у скольких между текстом "
      f"ответа и следующей репликой владельца прошло больше {STALE_GAP_DAYS:.0f} суток (см. СПОСОБ выше).")
    p("")
    p(f"audit_log revoke_rule всего в окне: {result['revoke_rule_total']} "
      f"(по исполнителям: {result['revoke_rule_by_actor'] or '—'})")

    p("")
    p("-" * 100)
    p("ПРИМЕРЫ пробы 3 (итог из трёх частей) — по 2 на роль, ≤80 знаков:")
    any_ex = False
    for role_key in order:
        for ex in roles[role_key].examples_3parts:
            any_ex = True
            gap_note = f" · РАЗРЫВ {ex['gap_days']:.1f} сут" if (ex['gap_days'] or 0) > STALE_GAP_DAYS else ""
            p(f"  {ex['role']:<10} · ответ {ex['reply_ts']} → реакция владельца {ex['owner_ts']} · "
              f"чат {ex['chat']}… строка {ex['line']} · длина {ex['length']}{gap_note}")
            p(f"    │ {ex['text']}")
    if not any_ex:
        p("  (в этом окне ни одного ответа со всеми тремя частями)")

    p("")
    p("ПРИМЕРЫ пробы 4 (слова словаря) — по 2 на роль, ≤80 знаков:")
    any_ex = False
    for role_key in order:
        for ex in roles[role_key].examples_forbidden:
            any_ex = True
            gap_note = f" · РАЗРЫВ {ex['gap_days']:.1f} сут" if (ex['gap_days'] or 0) > STALE_GAP_DAYS else ""
            p(f"  {ex['role']:<10} · ответ {ex['reply_ts']} → реакция владельца {ex['owner_ts']} · "
              f"чат {ex['chat']}… строка {ex['line']} · слова: {ex['words']}{gap_note}")
            p(f"    │ {ex['text']}")
    if not any_ex:
        p("  (в этом окне ни одного ответа со словом из словаря)")

    p("")
    p("Слова пробы 4 — сколько ОТВЕТОВ задели (по всем ролям вместе, это окно):")
    for label in STEM_FORMS.keys():
        p(f"  {label}: {totals.word_hit_replies.get(label, 0)}")

    p("")
    p("-" * 100)
    p("ДОПОЛНИТЕЛЬНЫЕ примеры проб 1–2 (не входят в обязательный вывод задачи — для ручной "
      "проверки ложных срабатываний; тоже ≤80 знаков):")
    p("  ПОПРАВКИ:")
    for ex in result["diag_examples"]["corrections"][: DIAGNOSTIC_EXAMPLES_CAP * 4]:
        p(f"    {ex['role']:<10} · {ex['ts']} · чат {ex['chat']}… строка {ex['line']} · метка: {ex['markers']}")
        p(f"      │ {ex['text']}")
    p("  ОТКАТЫ:")
    for ex in result["diag_examples"]["rollbacks"][: DIAGNOSTIC_EXAMPLES_CAP * 4]:
        p(f"    {ex['role']:<10} · {ex['ts']} · чат {ex['chat']}… строка {ex['line']} · метка: {ex['markers']}")
        p(f"      │ {ex['text']}")

    p("")
    p("=" * 100)
    end_now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    p(f"ГОТОВО. {end_now} UTC")


def result_to_json(result: dict) -> dict:
    roles_json = {}
    for role_key, rs in result["roles"].items():
        roles_json[role_key] = {
            "chats": len(rs.chats),
            "owner_msgs": rs.owner_msgs,
            "corrections": rs.corrections,
            "corrections_per_week": rs.corrections * 7.0 / (result["window_days"] or 1.0),
            "rollbacks": rs.rollbacks,
            "rollbacks_per_week": rs.rollbacks * 7.0 / (result["window_days"] or 1.0),
            "revoke_rule_by_actor": rs.revoke_rule_by_actor,
            "replies": rs.replies,
            "replies_long": rs.replies_long,
            "replies_3parts": rs.replies_3parts,
            "replies_3parts_share": (rs.replies_3parts / rs.replies) if rs.replies else None,
            "replies_3parts_long": rs.replies_3parts_long,
            "replies_3parts_long_share": (rs.replies_3parts_long / rs.replies_long) if rs.replies_long else None,
            "replies_forbidden": rs.replies_forbidden,
            "replies_forbidden_share": (rs.replies_forbidden / rs.replies) if rs.replies else None,
            "replies_stale_gap_over_2d": rs.replies_stale_gap,
            "word_hit_replies": dict(rs.word_hit_replies),
            "examples_corrections": rs.examples_corrections,
            "examples_rollbacks": rs.examples_rollbacks,
            "examples_3parts": rs.examples_3parts,
            "examples_forbidden": rs.examples_forbidden,
        }
    return {
        "since_utc": result["since"].strftime("%Y-%m-%d %H:%M:%S"),
        "until_utc": result["until"].strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": result["window_days"],
        "project_dirs": result["project_dirs"],
        "chats_scanned": result["chats_scanned"],
        "chats_with_data": result["chats_with_data"],
        "role_method_tally": result["role_method_tally"],
        "revoke_rule_total_in_window": result["revoke_rule_total"],
        "revoke_rule_by_actor_in_window": result["revoke_rule_by_actor"],
        "all_audit_actions_known": result["all_audit_actions"],
        "dictionary_labels_db": result["db_labels"],
        "dictionary_labels_claude_md": result["claude_md_labels"],
        "dictionary_labels_unmatched_by_stems": result["unmatched_labels"],
        "correction_markers": CORRECTION_MARKERS,
        "rollback_markers": ROLLBACK_MARKERS,
        "long_reply_threshold_chars": LONG_REPLY_CHARS,
        "stale_gap_threshold_days": STALE_GAP_DAYS,
        "roles": roles_json,
        "diagnostic_examples_probes_1_2": result["diag_examples"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", required=True, help="начало окна, UTC, 'ГГГГ-ММ-ДД ЧЧ:ММ'")
    ap.add_argument("--until", required=True, help="конец окна (не включая), UTC, 'ГГГГ-ММ-ДД ЧЧ:ММ'")
    ap.add_argument("--out", default=None, help="куда записать JSON (необязательно)")
    ap.add_argument("--projects-root", default=str(DEFAULT_PROJECTS_ROOT))
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--find-owner-word", default=str(DEFAULT_FIND_OWNER_WORD))
    ap.add_argument("--claude-md", default=str(DEFAULT_CLAUDE_MD))
    a = ap.parse_args()

    since = parse_window_arg(a.since)
    until = parse_window_arg(a.until)
    if until <= since:
        sys.exit("⛔ ОТКАЗ: --until должен быть позже --since.")

    result = run_measurement(
        projects_root=Path(a.projects_root),
        db_path=Path(a.db),
        fow_path=Path(a.find_owner_word),
        claude_md_path=Path(a.claude_md),
        since=since,
        until=until,
    )

    print_report(result, sys.stdout)

    if a.out:
        out_path = Path(a.out)
        out_path.write_text(
            json.dumps(result_to_json(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n(JSON записан: {out_path})", file=sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
