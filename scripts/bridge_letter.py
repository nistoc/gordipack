# -*- coding: utf-8 -*-
r"""bridge_letter.py — шапка письма между контурами: разбор, адреса, имя файла.
Этап Э7 набора TRACK-GORDI-CORE, карточка #681.

═══ ЗАЧЕМ
До Э7 проверка писем угадывала автора, адресата и «на что это ответ» по имени файла и первой
строке. Каждая заплата чинила одно угадывание и оставляла остальные (карточки #221, #242, #665,
#673): второе слово имени значило то автора, то адресата; ответ связывался с вопросом по
подстроке темы; своё письмо узнавалось тремя признаками, и письмо соседа в нашей папке по ним
не отличить. Э7 даёт письму поля — и проверка читает поля, а не угадывает.

═══ ВИД ПИСЬМА (решения Р1–Р3, В3 — README набора, §2)
    2026-10-13 09:30 UTC · пишет PROTO контура atlas, адресат — COORD@onto     ← строка для человека
    ---
    id: atlas:atlas-onto/answer.onto.e4-update-doc.20261013-0930
    from: PROTO@atlas
    to: COORD@onto
    reply-to: onto:atlas-onto/2026-10-05-to-proto-e3-step0-stop
    kind: answer
    ---
    <текст письма>

Р1 блок стоит ВТОРЫМ: прежний разбор у соседа читает первую строку (своё письмо) и первые пять
   непустых (адресаты). Блок первым закрыл бы оба окна. Разбор ищет открывающую «---» в первых
   ТРЁХ непустых строках.
Р2 id = <контур-владелец места>:<папка>/<имя файла без .md> — одна форма для старых и новых
   писем: имя без папки не уникально (одно имя лежит в двух папках).
Р3 адрес = <РОЛЬ>@<контур>; всем ролям контура — all@<контур>.
В3 kind: ask (ждёт ответа) · answer · status (ответа не ждёт) · fix (поправка к своему письму).

═══ ЧЕГО МОДУЛЬ НЕ ДЕЛАЕТ
Письмо без шапки модуль не судит и ничего о нём не угадывает: он говорит «шапки нет», а судят
такое письмо прежние правила вызывающего (решение Р5 — старые письма не трогаем). Шапка, которую
начали, но заполнили неверно, — «шапка негодна» с перечнем причин: её не выдают ни за годную,
ни за отсутствующую.

ОДНО МЕСТО РАЗБОРА: модуль зовут guard-all.py и sync_backoff.py. Второй экземпляр разбора в одном
из них разошёлся бы с первым молча (довод карточки #242).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("ask", "answer", "status", "fix")
FIELDS = ("id", "from", "to", "reply-to", "kind", "due")
REQUIRED = ("id", "from", "to", "kind")
REPLY_KINDS = ("answer", "fix")           # у этих видов reply-to обязателен
ALL_ROLES = "all"
HEAD_WINDOW = 3                           # открывающая «---» — среди первых трёх непустых строк
BLOCK_MAX_LINES = 20                      # блок длиннее — не шапка, а текст
READ_CHARS = 8000

# Роль может начинаться с цифры: решение Р3 называет разнобой имён ролей «COORD, COORD-A, 9P» (у контура
# dominal роль 9P). Прежнее «первая — буква» делало шапку такой роли негодной (приёмка COORD, записка #5848).
_ADDRESS_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]{0,31})@\.?([A-Za-z0-9][A-Za-z0-9_-]{0,63})$")
_ID_RE = re.compile(r"^\.?([A-Za-z0-9][A-Za-z0-9_-]{0,63}):([^/\\:]+)/([^/\\]+)$")
DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOPIC_RE = re.compile(r"^[A-Za-z0-9А-Яа-яЁё][A-Za-z0-9А-Яа-яЁё_-]*$")
_FIELD_RE = re.compile(r"^([a-z][a-z-]*)\s*:\s*(.*)$")


def norm_contour(name: str) -> str:
    """Имя контура для сравнения: без точки впереди («.onto» = «onto»), без регистра."""
    return (name or "").strip().lstrip(".").lower()


def parse_address(text: str):
    """«PROTO@atlas» → ("PROTO", "atlas"); «all@onto» → ("all", "onto"); иначе None.
    Роль приводится к верхнему регистру (системные имена), кроме слова all."""
    m = _ADDRESS_RE.match((text or "").strip())
    if not m:
        return None
    role = m.group(1)
    role = ALL_ROLES if role.lower() == ALL_ROLES else role.upper()
    return role, norm_contour(m.group(2))


def format_address(role: str, contour: str) -> str:
    return f"{role}@{norm_contour(contour)}"


def place_id(owner_contour: str, folder: str, file_name: str) -> str:
    """id письма по его МЕСТУ (Р2): <контур-владелец места>:<папка>/<имя без .md>."""
    stem = file_name[:-3] if file_name.endswith(".md") else file_name
    return f"{norm_contour(owner_contour)}:{folder}/{stem}"


def split_id(text: str):
    """«onto:atlas-onto/2026-10-05-тема» → ("onto", "atlas-onto", "2026-10-05-тема"); иначе None."""
    m = _ID_RE.match((text or "").strip())
    if not m:
        return None
    stem = m.group(3)
    if stem.endswith(".md"):
        stem = stem[:-3]
    return norm_contour(m.group(1)), m.group(2), stem


def same_id(a: str, b: str) -> bool:
    """Два id об одном письме: контур без регистра и точки, «.md» в конце не различает."""
    pa, pb = split_id(a), split_id(b)
    return bool(pa and pb and pa == pb)


class Header:
    """Итог разбора шапки. Три состояния, и они не сводятся друг к другу:
    found=False — шапки нет (письмо судят прежние правила) · found=True и problems — шапка негодна ·
    found=True без problems — годна (valid)."""

    def __init__(self):
        self.found = False
        self.unreadable = ""
        self.fields: dict = {}
        self.problems: list = []
        self.notes: list = []
        self.sender = None                 # (роль, контур)
        self.to: list = []                 # [(роль, контур)]
        self.kind = ""
        self.letter_id = ""
        self.reply_to = ""
        self.due = ""
        self.block_line = 0                # номер непустой строки, где открыт блок (1 — первая)

    @property
    def valid(self) -> bool:
        return self.found and not self.problems

    def sender_contour(self) -> str:
        return self.sender[1] if self.sender else ""

    def to_contours(self) -> list:
        return list(dict.fromkeys(c for _, c in self.to))

    def addressed_to(self, contour: str) -> bool:
        return norm_contour(contour) in self.to_contours()

    def roles_for(self, contour: str) -> list:
        """Адресаты в ЭТОМ контуре: роли, ['всем'] (all@контур) или [] — контуру не адресовано."""
        own = norm_contour(contour)
        roles = [r for r, c in self.to if c == own]
        if ALL_ROLES in roles:
            return ["всем"]
        return list(dict.fromkeys(roles))

    def describe(self) -> str:
        if not self.found:
            return self.unreadable or "шапки нет"
        if self.problems:
            return "шапка негодна: " + "; ".join(self.problems)
        to = ", ".join(format_address(r, c) for r, c in self.to)
        return (f"{self.kind} · от {format_address(*self.sender)} · кому {to}"
                + (f" · ответ на {self.reply_to}" if self.reply_to else ""))


def parse_header(text: str) -> Header:
    """Разбор шапки из текста письма. Не бросает."""
    h = Header()
    lines = (text or "").splitlines()
    nonempty = [(i, ln.strip()) for i, ln in enumerate(lines) if ln.strip()]
    opening = None
    for pos, (i, ln) in enumerate(nonempty[:HEAD_WINDOW]):
        if ln == "---":
            opening = (pos, i)
            break
    if opening is None:
        return h
    pos, start = opening
    # 🪤 «---» в начале письма бывает и чертой markdown. Шапкой блок считается, только если
    #    первая строка после черты — поле из списка; иначе это текст, и письмо — без шапки.
    block, closed = [], False
    for ln in lines[start + 1:start + 1 + BLOCK_MAX_LINES + 1]:
        s = ln.strip()
        if s == "---":
            closed = True
            break
        if s:
            block.append(s)
    first = _FIELD_RE.match(block[0]) if block else None
    if not first or first.group(1) not in FIELDS:
        return h
    h.found = True
    h.block_line = pos + 1
    if h.block_line == 1:
        h.notes.append("блок стоит первым: прежний разбор у соседа читает первую строку и теряет "
                       "автора и адресата (решение Р1 — блок вторым)")
    if not closed:
        h.problems.append(f"блок не закрыт строкой «---» в пределах {BLOCK_MAX_LINES} строк")
    for s in block:
        m = _FIELD_RE.match(s)
        if not m:
            h.problems.append(f"строка «{s[:60]}» — не вида «имя: значение»")
            continue
        key, value = m.group(1), m.group(2).strip()
        if key not in FIELDS:
            h.notes.append(f"незнакомое поле «{key}» пропущено")
            continue
        if key in h.fields:
            h.problems.append(f"поле «{key}» дважды")
            continue
        h.fields[key] = value
    for key in REQUIRED:
        if not h.fields.get(key):
            h.problems.append(f"нет поля «{key}»")
    kind = h.fields.get("kind", "")
    if kind and kind not in KINDS:
        h.problems.append(f"kind «{kind}» не из {', '.join(KINDS)}")
    h.kind = kind if kind in KINDS else ""
    if h.fields.get("from"):
        sender = parse_address(h.fields["from"])
        if not sender:
            h.problems.append(f"from «{h.fields['from']}» — не вида РОЛЬ@контур")
        elif sender[0] == ALL_ROLES:
            h.problems.append("from — одна роль, не all")
        else:
            h.sender = sender
    if h.fields.get("to"):
        for part in [p for p in h.fields["to"].split(",") if p.strip()]:
            address = parse_address(part)
            if not address:
                h.problems.append(f"to «{part.strip()}» — не вида РОЛЬ@контур")
            else:
                h.to.append(address)
    if h.fields.get("id"):
        if not split_id(h.fields["id"]):
            h.problems.append(f"id «{h.fields['id']}» — не вида контур:папка/имя")
        else:
            h.letter_id = h.fields["id"]
    if h.fields.get("reply-to"):
        if not split_id(h.fields["reply-to"]):
            h.problems.append(f"reply-to «{h.fields['reply-to']}» — не вида контур:папка/имя")
        else:
            h.reply_to = h.fields["reply-to"]
    elif kind in REPLY_KINDS:
        h.problems.append(f"у письма вида {kind} нет поля «reply-to»")
    if h.fields.get("due"):
        if not DUE_RE.match(h.fields["due"]):
            h.problems.append(f"due «{h.fields['due']}» — не вида ГГГГ-ММ-ДД")
        else:
            h.due = h.fields["due"]
            if kind and kind != "ask":
                h.notes.append(f"due у письма вида {kind} — ответа оно не ждёт")
    return h


def read_header(path) -> Header:
    """Разбор шапки файла письма. Нечитаемый файл — found=False и причина в unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(READ_CHARS)
    except OSError as exc:
        h = Header()
        h.unreadable = f"файл не прочитан ({exc.__class__.__name__})"
        return h
    return parse_header(text)


def resolve_id(letter_id: str, places: dict) -> list:
    """Файлы, которые называет id. places — {папка: контур-владелец места}.
    Ровно один файл — id разрешён; ноль — письма не видно отсюда; больше одного быть не может
    по построению (папка + имя), и такой исход вызывающий называет как поломку."""
    parts = split_id(letter_id)
    if not parts:
        return []
    contour, folder, stem = parts
    found = []
    for place, owner in places.items():
        place = Path(place)
        if norm_contour(owner) == contour and place.name == folder:
            candidate = place / f"{stem}.md"
            if candidate.is_file():
                found.append(candidate)
    return found


def letter_name(kind: str, to_contour: str, topic: str, when: datetime) -> str:
    """Имя нового письма: <kind>.<контур-адресат>.<тема>.<ГГГГММДД-ЧЧММ>.md.
    Метка времени даёт уникальность: второй отвечающий больше не стирает первого. Точек четыре —
    сосед на прежнем пакете читает второе слово как адресата по своему «новому» правилу."""
    if kind not in KINDS:
        raise ValueError(f"kind «{kind}» не из {', '.join(KINDS)}")
    if not _TOPIC_RE.match(topic or ""):
        raise ValueError(f"тема «{topic}»: только буквы, цифры, «-» и «_», без точек и пробелов")
    stamp = when.astimezone(timezone.utc).strftime("%Y%m%d-%H%M")
    return f"{kind}.{norm_contour(to_contour)}.{topic}.{stamp}.md"


def human_line(when: datetime, role: str, contour: str, to: list) -> str:
    """Первая строка для человека. ⚠️ Адресат — «РОЛЬ@контур», не «РОЛЬ контура X»: прежний признак
    своего письма у соседа ищет «контура <он>» в первой строке и счёл бы наше письмо своим."""
    stamp = when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
    whom = []
    for r, c in to:
        whom.append(f"ВСЕ роли ({norm_contour(c)})" if r == ALL_ROLES else format_address(r, c))
    return f"{stamp} UTC · пишет {role} контура {norm_contour(contour)}, адресат — {', '.join(whom)}"


def compose(when: datetime, sender: tuple, to: list, kind: str, letter_id: str,
            reply_to: str = "", due: str = "", body: str = "") -> str:
    """Текст письма: строка для человека, блок полей вторым, пустая строка, текст."""
    head = ["---", f"id: {letter_id}", f"from: {format_address(*sender)}",
            "to: " + ", ".join(format_address(r, c) for r, c in to)]
    if reply_to:
        head.append(f"reply-to: {reply_to}")
    head.append(f"kind: {kind}")
    if due:
        head.append(f"due: {due}")
    head.append("---")
    text = human_line(when, sender[0], sender[1], to) + "\n" + "\n".join(head) + "\n\n" + body
    return text if text.endswith("\n") else text + "\n"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
