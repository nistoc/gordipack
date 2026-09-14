#!/usr/bin/env python
# SURFACES: memory
# -*- coding: utf-8 -*-
r"""ГОРЯЧАЯ ПАМЯТЬ И АРХИВ: унести из раздела то, что роль не читает при пробуждении.

ПРЕДМЕТ (карточка #523). Память роли читается ЦЕЛИКОМ при каждом пробуждении, и замер
2026-09-04 13:25 UTC говорит, сколько это стои́т: 65 938 … 123 980 знаков на роль, семь
разделов у каждой. Порог 20 000 стои́т на РАЗДЕЛЕ, то есть разрешает 140 000 на роль —
ограничение поставлено не на тот предмет, что расходуется.

⚖️ ЧТО ЗДЕСЬ ГОРЯЧЕЕ, А ЧТО В АРХИВ — правило свода `memory-hot-and-archive`. Инструмент
его НЕ придумывает и не подменяет: он показывает блоки, предлагает разметку ПО ПРАВИЛУ
и переносит то, что назвала рука. Решение остаётся за ролью — но правило одно на всех,
иначе через неделю у девяти ролей девять разных устройств памяти.

⛔ РОЛЬ ЖМЁТ СВОЮ ПАМЯТЬ САМА. Слово владельца 2026-09-04 13:41 UTC: «только свою,
остальные сами». Чужую можно ПОКАЗАТЬ (--preview), но не перенести: у переноса чужой
памяти нет способа узнать, что в ней важно её владельцу.

ПОТЕРЬ НОЛЬ ПО ПОСТРОЕНИЮ: перенос — это INSERT в архив и только ПОТОМ укорачивание
горячего тела, обе правки в ОДНОЙ транзакции, и прежнее тело раздела целиком остаётся
в истории разделов. Ни один путь этого инструмента не удаляет текст.

🎯 КАРТОЧКА #627: перенос ТЕМ ЖЕ ВЫЗОВОМ пересобирает слой записей (`phoenix_records`,
инструмент memory-records.py) раздела, из которого унесли куски — тем же приёмом, каким
это уже делает save-phoenix.py после сохранения тела (карточка #525, часть А, пункт 2).
До этой правки перенос трогал только phoenix/phoenix_archive/phoenix_history, а записи
оставались от ПРЕЖНЕГО (более длинного) тела до следующего сохранения памяти — и поиск
по памяти (find-phoenix.py) находил в «живой памяти» то, что уже унесено в архив.

Зовут так:
    python <КОНТУР>/vnext-tools/memory-archive.py --role PROTO --section state --preview
    python <КОНТУР>/vnext-tools/memory-archive.py --role PROTO --section state --move 3 7 9
    python <КОНТУР>/vnext-tools/memory-archive.py --role PROTO --find "будильник"
    python <КОНТУР>/vnext-tools/memory-archive.py --role PROTO --list
"""
from __future__ import annotations

import argparse
import contextlib      # #627: захват вывода memory-records.py при пересборке после переноса
import datetime
import importlib.util  # #627: memory-records.py грузится тем же приёмом, что и save-phoenix.py
import io              # #627: буфер для contextlib.redirect_stdout
import os
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
HOT_TARGET_CHARS = 4000        # знаков на раздел — цель карточки #523, не запрет

# ── ПРИМЕТЫ ПРАВИЛА ПЕРЕНОСА ───────────────────────────────────────────────────────
# ⚖️ Это ПОДСКАЗКА, а не приговор: приметы ищут слова, а решает смысл. Инструмент
# говорит «похоже на архивное» и «похоже на горячее», и обе стороны показывает
# ЧЕСТНО — молчание приметы не значит «можно уносить».
HOT_MARKERS = ("действует", "право", "разрешено", "запрещено", "⛔", "🔑",
               "инвариант", "слово владельца", "сейчас", "в работе", "план",
               "следующий шаг", "не отозван", "ЗАПРЕТ", "ОБЯЗАН")
# ⚖️ АРХИВНЫЕ ПРИМЕТЫ ДЕЛЯТСЯ НА ДВЕ ГРУППЫ, И ЭТО НЕ ОФОРМЛЕНИЕ. Правило
# memory-hot-and-archive ставит порог в семь суток НЕ ВСЕМУ: закрытым работам,
# прежним редакциям и подробностям замеров возраст не назначен вовсе, а разборам
# уроков и надгробиям — назначен. Один список на обе группы врал бы в обе стороны.
ARCHIVE_MARKERS_AGELESS = ("закрыт", "завершён", "завершен", "сделано", "прежн",
                      "было:", "история")
ARCHIVE_MARKERS_BY_AGE = ("⚰️", "надгробие", "отозван", "снято", "оплачено", "урок")
ARCHIVE_MARKERS = ARCHIVE_MARKERS_AGELESS + ARCHIVE_MARKERS_BY_AGE


RULE_LINE_RE = re.compile(r"^\s*[─═━=*-]{6,}\s*$")
# ⚡ ЧЕРТА С ТЕКСТОМ ВНУТРИ — «═══ §ПРАВА — ЧТО РАЗРЕШЕНО ═══». Нашёл @RCC 04.09 20:13 UTC
# (записка #4707): его разметка ВСЯ такая — 0 строк ловил образец выше, 52 такие. Раздел
# резался «по абзацам» механически, и на кусок, начатый посреди мысли, навешивались предмет
# и условие снятия. Число кусков при этом почти не менялось (5 против 7) — потому беда
# невидима любой проверке по количеству. Такая черта — ЗАГОЛОВОК: с неё блок НАЧИНАЕТСЯ.
# 🩸 И половина против неё, которую @RCC назвал сам (записка #4717): 2 из 6 его черт лежат
# ВНУТРИ огороженных «```» блоков — резать там нельзя, иначе блок кода разъедется пополам,
# а сумма знаков сойдётся и проверка смолчит. ⇒ обе черты не режут внутри ограды.
RULE_LINE_TEXT_RE = re.compile(r"^\s*[─═━]{3,}\s*(.+?)\s*[─═━]{3,}\s*$")
FENCE_RE = re.compile(r"^\s*```")
PARAGRAPH_TARGET_CHARS = 2000          # знаков — во что склеивать абзацы, когда разметки нет


def _by_headings(lines):
    chunks, current = [], {"тема": "⟨шапка раздела⟩", "уровень": 0, "строки": []}
    for line in lines:
        m = HEADING_RE.match(line.rstrip("\n"))
        if m:
            if current["строки"]:
                chunks.append(current)
            current = {"тема": m.group(2), "уровень": len(m.group(1)), "строки": [line]}
        else:
            current["строки"].append(line)
    if current["строки"]:
        chunks.append(current)
    return chunks


def _rule_lines_outside_fences(lines) -> int:
    """Сколько черт-разделителей (обоих видов) стоит ВНЕ огороженных блоков кода."""
    n, in_fence = 0, False
    for line in lines:
        s = line.rstrip("\n")
        if FENCE_RE.match(s):
            in_fence = not in_fence
            continue
        if not in_fence and (RULE_LINE_RE.match(s) or RULE_LINE_TEXT_RE.match(s)):
            n += 1
    return n


def _by_rule_lines(lines):
    chunks, current = [], {"тема": "⟨до первой черты⟩", "уровень": 1, "строки": []}
    in_fence = False
    for line in lines:
        s = line.rstrip("\n")
        if FENCE_RE.match(s):
            in_fence = not in_fence          # внутри ограды ни одна черта не режет
        # 🩸 ЧИСТАЯ ЧЕРТА ПРОВЕРЯЕТСЯ ПЕРВОЙ: «──────────» подходит и под образец «черта с
        # текстом» (три чёрточки · «текст» из чёрточек · три чёрточки) — контроль ③ приёмки
        # покраснел на первом же прогоне: темы «─». Порядок проверок здесь несущий.
        m = None if in_fence or FENCE_RE.match(s) or RULE_LINE_RE.match(s) else RULE_LINE_TEXT_RE.match(s)
        if m:                            # черта с текстом — заголовок: блок НАЧИНАЕТСЯ с неё
            if current["строки"]:
                chunks.append(current)
            current = {"тема": m.group(1)[:70], "уровень": 1, "строки": [line]}
            continue
        current["строки"].append(line)
        if not in_fence and RULE_LINE_RE.match(s) and current["строки"]:
            chunks.append(current)        # чистая черта — блок ЗАКРЫВАЕТСЯ ею, как и прежде
            current = {"тема": "⟨после черты⟩", "уровень": 1, "строки": []}
    if current["строки"]:
        chunks.append(current)
    for chunk in chunks:                       # тема — первая содержательная строка куска
        if not chunk["тема"].startswith("⟨"):  # черта с текстом уже дала тему — не затирать
            continue
        for line in chunk["строки"]:
            stripped = line.strip()
            if stripped and not RULE_LINE_RE.match(stripped):
                chunk["тема"] = stripped[:70]
                break
    return chunks


def _by_paragraphs(lines):
    """Склеить абзацы (группы строк между пустыми) в куски около PARAGRAPH_TARGET_CHARS знаков.

    🩸 ВТОРАЯ ДВЕРЬ (карточка #541, находка @RCC записка #4735, 04.09 21:30 UTC): резка по
    черте ограду уже уважала, а ЭТА — нет. Пустая строка ВНУТРИ блока «```» считалась
    границей абзаца, и до-резка крупного куска ставила границу посреди кода: кусок 2/3
    начинался с открывающей ограды без закрывающей, кусок 3/3 — наоборот. Сумма знаков
    при этом сходилась знак в знак — проверка по числам эту беду не покрасит НИКОГДА.
    ⚡ КЛАСС (его): починка одного представителя класса оставляет класс живым; предмет
    один (ограда), механизмы разные (черта · абзац). И его же встречный случай «черта
    внутри ограды не режет» был зелен ПО ПОСТРОЕНИЮ — определял предмет разметкой, а беда
    пришла длиной. Верный встречный — ПО ДЛИНЕ: блок кода длиннее порога до-резки, границы
    не попадают внутрь ограды (в приёмке).
    ⇒ Пустая строка внутри ограды абзац НЕ закрывает. Непарная ограда (нечётное число «```»
    в разделе) держит «в коде» до конца — тогда хвост уйдёт одним куском, и это честнее,
    чем разрезать то, чью границу мы не знаем.
    """
    paragraphs, current, in_fence = [], [], False
    for line in lines:
        current.append(line)
        if FENCE_RE.match(line.rstrip("\n")):
            in_fence = not in_fence
            continue
        if not line.strip() and not in_fence:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    chunks, accumulator = [], []
    for paragraph in paragraphs:
        accumulator.extend(paragraph)
        if len("".join(accumulator)) >= PARAGRAPH_TARGET_CHARS:
            chunks.append(accumulator)
            accumulator = []
    if accumulator:
        chunks.append(accumulator)
    ready = []
    for chunk_lines in chunks:
        # тема — первая содержательная строка, но НЕ сама ограда: кусок, начатый с «```»,
        # звался бы «```» и по предмету его было бы не спросить
        topic = next((line.strip()[:70] for line in chunk_lines
                     if line.strip() and not FENCE_RE.match(line.rstrip("\n"))),
                    "⟨без первой строки⟩")
        ready.append({"тема": topic, "уровень": 1, "строки": chunk_lines})
    return ready


def blocks(text: str) -> tuple[list[dict], str]:
    """Разбить тело раздела на блоки. ВОЗВРАЩАЕТ И СПОСОБ, которым разрезано.

    🩸 ПОЧЕМУ СПОСОБОВ ТРИ, А НЕ ОДИН — замер 2026-09-04 13:31 UTC по всем 63 разделам
    девяти ролей: заголовков «#» нет ВОВСЕ у RCC во всех её разделах, и ещё у четырёх
    ролей часть разделов без разметки — 16 из 63. Инструмент с одним способом работал
    бы у трёх четвертей контура и МОЛЧА не работал бы у RCC целиком, выдавая её память
    одним нерезаемым куском.
    ⚡ Класс: «работает на моих данных» — это своя ветка, и она молчит о чужих.

    ⚖️ И СПОСОБ ПЕЧАТАЕТСЯ ВСЛУХ. Резка по абзацам даёт куски, границы которых выбрал
    механизм, а не автор памяти, — читающий обязан это знать, иначе примет случайную
    границу за смысловую.

    ⚖️ КЛЮЧИ СЛОВАРЯ КУСКА («тема» · «уровень» · «строки» · «тело» · «знаков») ОСТАВЛЕНЫ
    ПО-РУССКИ НАРОЧНО (карточка #627, перевод имён memory-archive.py): их читает ЧУЖОЙ
    файл, memory-records.py (`_ma.блоки(body)[...]["тело"]`, `["знаков"]`, `["тема"]`),
    который эта правка не трогает — «ключи словарей, уходящие в чужой файл» не переводятся.
    """
    lines = text.splitlines(keepends=True)
    heading_count = sum(1 for line in lines if HEADING_RE.match(line.rstrip("\n")))
    if heading_count >= 2:
        chunks, method = _by_headings(lines), "по заголовкам («#»)"
    elif _rule_lines_outside_fences(lines) >= 2:
        chunks, method = _by_rule_lines(lines), "по чертам-разделителям (в т.ч. с текстом внутри; внутри «```» не режет)"
    else:
        chunks, method = _by_paragraphs(lines), (
            f"ПО АБЗАЦАМ (~{PARAGRAPH_TARGET_CHARS}б) — разметки в разделе нет, границы выбрал "
            "механизм, а не автор памяти")
    # ── ДО-РЕЗКА КРУПНЫХ КУСКОВ ────────────────────────────────────────────────
    # 🩸 ОПЛАЧЕНО СВОЕЙ ЖЕ ПАМЯТЬЮ: у PROTO·state ДВА заголовка на 19 709 знаков —
    # признак «заголовки есть» срабатывал, а резка давала кусок в 17 810 знаков,
    # то есть не давала ничего. ⚡ КЛАСС: признак проверял НАЛИЧИЕ разметки, а нужен
    # был ЕЁ РЕЗУЛЬТАТ. Проверка наличия зеленеет там, где толку нет.
    large_threshold = 2 * PARAGRAPH_TARGET_CHARS
    was_recut = False
    smaller = []
    for chunk in chunks:
        body = "".join(chunk["строки"])
        if len(body) <= large_threshold:
            smaller.append(chunk)
            continue
        was_recut = True
        parts = _by_paragraphs(chunk["строки"])
        for n, part in enumerate(parts, 1):
            # 🩸 ТЕМА КУСКА — ЕГО ПЕРВАЯ СОДЕРЖАТЕЛЬНАЯ СТРОКА, А НЕ «часть N ИЗ M».
            # Первая редакция звала до-резанные куски «⟨шапка раздела⟩ · часть 2/7» —
            # и такой архив НЕЛЬЗЯ СПРОСИТЬ ПО ПРЕДМЕТУ: номер части не предмет.
            # ⚡ Класс: механическая резка даёт механические имена, и вместе с ними
            # уходит ровно то, ради чего архив заводили. Поймано на своей же памяти
            # через минуту после первого переноса (2026-09-04 13:36 UTC).
            own_parts = _by_paragraphs(part["строки"])  # тема уже вычислена внутри
            part["тема"] = (own_parts[0]["тема"] if own_parts else chunk["тема"])[:70]
            if len(parts) > 1:
                part["тема"] += f"  ⟨{n}/{len(parts)} из «{chunk['тема'][:28]}»⟩"
            part["уровень"] = chunk["уровень"]
            smaller.append(part)
    chunks = smaller
    if was_recut:
        method += f" + крупные куски (>{large_threshold}б) до-резаны по абзацам"

    for chunk in chunks:
        chunk["тело"] = "".join(chunk["строки"])
        chunk["знаков"] = len(chunk["тело"])
    return chunks, method


# ⚖️ ПСЕВДОНИМ, А НЕ ПЕРЕИМЕНОВАНИЕ ЗВОНЯЩИХ (карточка #627, ловушка ②): функцию зовут
# СНАРУЖИ по этому имени — memory-records.py (`_ma.блоки(body)`, файл трогать запрещено)
# и приёмки bite-memory-archive.py / bite-memory-archive-nodate.py (`m.блоки(...)`,
# импорт через importlib, тоже по имени). Оставляем прежнее имя рабочим псевдонимом —
# правка вызывающих здесь либо запрещена, либо не входит в это задание.
блоки = blocks


AGE_THRESHOLD_DAYS = 7            # правило memory-hot-and-archive: разборы моложе — НЕ уносят
DATE_PATTERNS = (
    re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b"),          # 2026-09-04
    re.compile(r"\b(\d\d)\.(\d\d)\.(20\d\d)\b"),        # 04.09.2026
    re.compile(r"\b(\d\d)\.(\d\d)\b(?!\.)"),            # 04.09 — год подразумевается текущий
)


def freshness(body: str, today: datetime.date):
    """Сколько суток самой СВЕЖЕЙ дате в блоке. None — дат нет вовсе.

    🩸 ЗАЧЕМ — находка @COORD при приёмке карточки #523 (записка #4679): примета судила
    по СЛОВУ в тексте («закрыт», «снято», «оплачено»), а правило судит по ВОЗРАСТУ.
    Слово в тексте есть почти всегда, возраст — отдельная вещь, и они разошлись:
    блоку четверо суток, примета звала унести, правило запрещало.
    ⚡ КЛАСС: ПОДСКАЗКА И ПРАВИЛО ОТВЕЧАЮТ НА РАЗНЫЕ ВОПРОСЫ, А ЧИТАЮТСЯ КАК ОДИН.
    Роль, послушавшая подсказку, унесла бы запрещённое — и проверки на это нет ни одной.
    """
    found = []
    for n, pattern in enumerate(DATE_PATTERNS):
        for m in pattern.finditer(body):
            try:
                if n == 0:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif n == 1:
                    d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    d = datetime.date(today.year, int(m.group(2)), int(m.group(1)))
                    # ⚖️ «04.09» без года: если вышло будущее — значит это прошлый год.
                    # Иначе декабрьские записи в январе выглядели бы свежими на год вперёд.
                    if d > today:
                        d = d.replace(year=today.year - 1)
            except ValueError:
                continue                      # 32.13 и подобное — не дата, молча мимо
            found.append(d)
    if not found:
        return None
    return (today - max(found)).days


def advise(body: str, today=None) -> tuple[str, str, bool]:
    """Что приметы говорят об этом блоке.

    Возвращает (знак, пояснение, держится_без_даты).
    Третье — ПРАВДА только для блока, который держат ИМЕННО за то, что возраст
    мерить нечем. По нему считается итог «блоков без даты: N» (карточка #556):
    такой приговор не изменится сам НИКОГДА, и это надо видеть числом.
    """
    today = today or datetime.datetime.now(datetime.UTC).date()
    lowered = body.lower()
    hot_hits = [marker for marker in HOT_MARKERS if marker.lower() in lowered]
    archive_hits = [marker for marker in ARCHIVE_MARKERS if marker.lower() in lowered]
    age_days = freshness(body, today)
    # ⛔ ВОЗРАСТ СИЛЬНЕЕ СЛОВА — НО ТОЛЬКО ТАМ, ГДЕ ПРАВИЛО ЕГО НАЗНАЧИЛО.
    # 🩸 Первая редакция этой починки держала ВСЁ моложе семи суток и была ШИРЕ правила:
    # она запретила бы перенос закрытых работ, у которых возрастного условия нет вовсе —
    # то есть мой же законный перенос двумя часами ранее. ⚡ Тот самый класс, о котором
    # я пишу в записках: признак, взятый в одиночку, гасит и то, что ищет. Поймано
    # прогоном на живой памяти через минуту после написания.
    is_young = age_days is not None and age_days < AGE_THRESHOLD_DAYS
    archive_by_age = [marker for marker in archive_hits if marker in ARCHIVE_MARKERS_BY_AGE]
    if archive_by_age and is_young:
        return "🔒", (f"слова зовут в архив ({', '.join(archive_by_age[:2])}), НО свежей дате "
                      f"{age_days} сут — правило держит разборы и надгробия до {AGE_THRESHOLD_DAYS}"), False
    # ⚡ ТРЕТЬЕ СОСТОЯНИЕ ЗАМКА, найдено @CHROME 2026-09-04 и признано с ходу.
    # 🩸 Строка выше меряет так: «молодой = дата есть И она свежая». Когда дат в блоке
    # НЕТ ВОВСЕ, «молодой» получается ЛОЖЬЮ — и замок пропускает блок дальше, к 📦.
    # То есть замок молчит ровно там, где мерить НЕЧЕМ, а его молчание неотличимо от
    # «проверил и разрешаю». Блок, написанный СЕГОДНЯ, но без даты внутри, звался
    # в архив уверенным знаком; оговорка «дат в блоке НЕТ» стояла в пояснении, куда
    # смотрят после знака, а не вместо него.
    # ⚖️ Почему НЕ 🔒: держать блок только за отсутствие даты — тот же перегиб, что уже
    # был здесь однажды (см. разбор выше про закрытые работы). Неизвестность — это
    # СПОР, а не запрет: знак ⚖️ и причина названа словом «нечем».
    if archive_by_age and age_days is None:
        # 🔴 ПОСЛЕДСТВИЕ НАЗЫВАЕТСЯ ВСЛУХ (карточка #556, находка @OPSSRE 05.09 06:37 UTC).
        # Прежде тут стояла только ПРИЧИНА — «возраст мерить нечем, смотри сам», — и она
        # читалась как оговорка осторожного механизма. А означает она другое: без даты
        # блок НЕ СТАНЕТ старше порога ни через неделю, ни через год, и этот приговор
        # не изменится САМ НИКОГДА. Ждать его смены бессмысленно, а именно так его и читают.
        # ⚡ КЛАСС: честное «я не знаю» и ВЕЧНЫЙ отказ выглядят одинаково. Первое ждут,
        # второе чинят — а строка одна и та же.
        return "⚖️", (f"слова зовут в архив ({', '.join(archive_by_age[:2])}), но ВОЗРАСТ "
                      f"МЕРИТЬ НЕЧЕМ — дат в блоке нет. "
                      f"🔴 ЭТОТ ПРИГОВОР НЕ ИЗМЕНИТСЯ САМ НИКОГДА: без даты блок не станет "
                      f"старше {AGE_THRESHOLD_DAYS} сут ни через неделю, ни через год. "
                      f"Хочешь, чтобы механизм звал его в архив, — ПРОСТАВЬ ДАТУ в заголовке"), True
    if hot_hits and not archive_hits:
        return "🔥", f"горячее: {', '.join(hot_hits[:3])}", False
    if archive_hits and not hot_hits:
        # сюда доходят приметы ВНЕ возрастной группы (закрытые работы и подобное):
        # у них возрастного условия нет по правилу, и отсутствие дат им не помеха.
        age_text = (f"свежей дате {age_days} сут" if age_days is not None
                   else "дат в блоке нет, но этим приметам возраст и не нужен")
        return "📦", f"похоже на архивное: {', '.join(archive_hits[:3])} · {age_text}", False
    if hot_hits and archive_hits:
        tail = (f" · свежей дате {age_days} сут" if age_days is not None
                 else " · дат в блоке НЕТ — возраст неизвестен")
        return "⚖️", (f"и то и другое ({', '.join(hot_hits[:2])} / {', '.join(archive_hits[:2])})"
                      f"{tail} — решай сам"), False
    # ⚖️ ГРАНИЦА, названная нарочно: «дат нет» ЗДЕСЬ не считается бедой. Этот блок
    # никто не держит — у него просто нет примет, и решает глаз, а не порог. Считать
    # его в число «не разгрузятся сами» значило бы завести признак, горящий почти
    # всегда, — ровно то, от чего эта правка и лечит.
    return "⚪", ("примет нет — смотри глазами" if age_days is None
                 else f"примет нет · свежей дате {age_days} сут"), False


# ⚖️ ПСЕВДОНИМ (карточка #627, ловушка ②): приёмки bite-memory-archive.py и
# bite-memory-archive-nodate.py держат имя `совет` снаружи через importlib (`m.совет(...)`).
совет = advise


def read_section(conn, role, section):
    r = conn.execute("SELECT body, saved_at FROM phoenix WHERE role=? AND section=?",
                     (role, section)).fetchone()
    if not r:
        sys.exit(f"⛔ У роли {role} нет раздела «{section}». "
                 "Разделы: identity · state · plan · history · launcher · rebirth · sources")
    return r


def show(conn, role, section):
    body, saved = read_section(conn, role, section)
    chunks, method = blocks(body)
    print("=" * 84)
    print(f"{role} · {section} — {len(body)} знаков, {len(chunks)} блоков "
          f"(сохранено {saved[:16]} UTC)")
    print(f"РЕЗАНО: {method}")
    print(f"цель горячей части: {HOT_TARGET_CHARS} знаков ⇒ унести надо "
          f"{max(0, len(body) - HOT_TARGET_CHARS)}")
    print("=" * 84)
    no_date_count, no_date_chars = 0, 0
    for i, chunk in enumerate(chunks, 1):
        mark, why, holds_without_date = advise(chunk["тело"])
        if holds_without_date:
            no_date_count += 1
            no_date_chars += chunk["знаков"]
        indent = "  " * max(0, chunk["уровень"] - 1)
        print(f"{i:3}. {mark} {chunk['знаков']:>6}б  {indent}{chunk['тема'][:60]}")
        print(f"          └ {why}")
    print("-" * 84)
    # 🔴 ИТОГ ЧИСЛОМ (карточка #556). Одна строка на блок теряется среди тридцати:
    # роль видит её, кивает и идёт дальше. Число собирает беду в одно место.
    # ⚖️ При нуле строка НЕ печатается вовсе — признак, который горит всегда,
    # перестаёт что-либо значить, а «блоков без даты: 0» именно так бы и горел.
    if no_date_count:
        print(f"🔴 БЛОКОВ БЕЗ ДАТЫ: {no_date_count} · суммарно {no_date_chars} знаков — "
              f"ОНИ НЕ РАЗГРУЗЯТСЯ САМИ НИКОГДА.")
        print(f"   Их приговор не изменится со временем: без даты в тексте блок не станет "
              f"старше {AGE_THRESHOLD_DAYS} сут. Проставь дату в заголовке — и механизм")
        print("   начнёт считать их возраст сам.")
        print("-" * 84)
    print("👉 Унести: --move <номера через пробел>. Номера — из ЭТОГО вывода;")
    print("   он пересчитывается после каждого переноса, поэтому уноси за один вызов.")
    print("⚖️ Приметы — подсказка, не приговор. Что горячее, а что нет, говорит правило:")
    print("   python <КОНТУР>/.mezosync/scripts/set-rule.py "
          "--key memory-hot-and-archive --show")


# ⚖️ ПСЕВДОНИМ (карточка #627, ловушка ②): bite-memory-archive-nodate.py держит имя
# `показать` снаружи через importlib (`m.показать(c, "X", "state")`).
показать = show


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 КАРТОЧКА #627 — ПЕРЕСБОРКА СЛОЯ ЗАПИСЕЙ ПОСЛЕ ПЕРЕНОСА В АРХИВ.
#
# ОБРАЗЕЦ: save-phoenix.py::rebuild_records() (карточка #525, часть А, пункт 2) —
# тот же приём переносится сюда почти дословно, только для действия «перенос» вместо
# «сохранение тела». ЗАЧЕМ: слой `phoenix_records` — ПРОИЗВОДНОЕ от тела раздела
# phoenix, а не второй источник правды. move_to_archive() укорачивает тело раздела
# (переносит куски в phoenix_archive), и записи, разобранные из ПРЕЖНЕГО (более
# длинного) тела, начинают нести унесённый текст как «живой» — до следующего
# save-phoenix.py. find-phoenix.py ищет по phoenix_records и находит в «живой памяти»
# то, что уже унесено в архив — ровно та путаница, против которой у find-phoenix.py
# есть отдельный исход «в живой памяти нет, в архиве есть» (код 4).
#
# ПОЧЕМУ ОТКАЗ ЗДЕСЬ НЕ ОТМЕНЯЕТ ПЕРЕНОС: к моменту вызова перенос УЖЕ ЗАПИСАН и
# закоммичен (строка «✅ ПЕРЕНЕСЕНО» уже напечатана) — это состоявшийся факт. Слой
# записей — вторичная выборка того же текста, полезная, но не обязательная для того,
# чтобы память была цела. Отказавший слой — это ДОЛГ (пересобрать рукой), а не повод
# откатывать уже состоявшийся перенос: отката тут и нет технически (перенос — отдельная
# закоммиченная транзакция), а откатывать её задним числом опаснее, чем оставить долг.
#
# ПОЧЕМУ ЛОВИТСЯ И SystemExit: обе функции memory-records.py, rebuild() и parse(),
# на ВСЕХ отказных ветках зовут именно sys.exit(текст), а не возвращают код ошибки, —
# это подняло бы SystemExit наружу. Поймай здесь только Exception — и sys.exit() внутри
# вызванной функции прошёл бы МИМО этого try, прервал бы весь процесс memory-archive.py
# ПОСЛЕ того, как тот уже напечатал «✅ ПЕРЕНЕСЕНО» и объявил об успехе, — роль увидела
# бы трассировку вместо честного предупреждения и решила бы, что перенос сломан целиком,
# хотя сломан лишь вторичный слой.
#
# 🔑 КОД ВЫХОДА --move: отказ пересборки НЕ меняет код возврата memory-archive.py —
# main() не смотрит на исход этой функции вовсе, она зовётся ради побочного эффекта
# и печати, тем же приёмом, что и save-phoenix.py (там rebuild_records() тоже не влияет
# на код выхода). Перенос — состоявшееся действие, и оно не обязано провалиться из-за
# долга вторичного слоя.
# ═══════════════════════════════════════════════════════════════════════════════

_RECORDS_NUMBERS_RE = re.compile(
    r"НОМЕРА СОХРАНЕНЫ у (\d+) записей · новых (\d+) · удалено (\d+)")
_RECORDS_LOST_RE = re.compile(r"ПОЛЯ ПОТЕРЯНЫ у (\d+) записей")
_RECORDS_FIRST_RE = re.compile(r"→ (\d+) записей")
_RECORDS_ORPHAN_RE = re.compile(r"^\s*🔸 (.+)$")


def _one_line(e):
    """Текст исключения ОДНОЙ строкой: sys.exit(текст) из memory-records.py часто несёт
    многострочное объяснение (пустые строки, отступы «👉») — оно годится в лог целиком,
    но не в одну строку предупреждения. Переносы схлопываются в пробелы."""
    return " ".join(str(e).split())


def _records_summary_line(text, first_parse):
    """Собрать ОДНУ строку-итог из захваченного вывода mr.rebuild()/mr.parse() —
    те печатают много (сама пересборка, номера, отчёт об осиротевших полях), а здесь
    нужна одна строка рядом с «✅ ПЕРЕНЕСЕНО», не полный отчёт при каждом переносе.
    → строка или None, если ожидаемый узор в тексте не нашёлся (тогда зовущий код
    печатает полный текст — см. full_needed ниже, молчания тут нет)."""
    if first_parse:
        m = _RECORDS_FIRST_RE.search(text)
        if not m:
            return None
        return f"🧩 записи раздела: разобрано {m.group(1)} записей (первый разбор)"
    m = _RECORDS_NUMBERS_RE.search(text)
    if not m:
        return None
    n, k, d = m.group(1), m.group(2), m.group(3)
    mj = _RECORDS_LOST_RE.search(text)
    j = mj.group(1) if mj else "0"
    lines = [f"🧩 записи раздела: сохранили номер {n} · новых {k} · удалено {d} · "
              f"осиротевших полей {j}"]
    if mj and int(j) > 0:
        for line in text.splitlines():
            mm = _RECORDS_ORPHAN_RE.match(line)
            if mm:
                lines.append(f"   🔸 {mm.group(1)}")
    return "\n".join(lines)


def _rebuild_records_after_move(db_path, role, section, actor):
    """Пересобрать слой `phoenix_records` раздела role/section ПОСЛЕ того, как перенос
    в архив уже записан и закоммичен (карточка #627). См. пояснение блоком выше файла
    функции. Открывает СВОЁ соединение к db_path (то же, что использовал move_to_archive()
    для переноса, — то соединение к этому моменту уже отработало свою транзакцию).
    Отказ печатает громкое предупреждение и НЕ бросает исключение наружу: caller
    (move_to_archive()) не смотрит на исход этой функции вообще, она вызывается ради
    побочного эффекта и печати.
    """
    tool = pathlib.Path(__file__).with_name("memory-records.py")
    if not tool.exists():
        print(f"⚠️ ЗАПИСИ РАЗДЕЛА НЕ ПЕРЕСОБРАНЫ: файла нет: {tool} — перенос УЖЕ ЗАПИСАН, "
              f"это не отменяется. Пересобери рукой (когда файл появится): "
              f"python {tool.as_posix()} --role {role} --section {section} --rebuild")
        return

    conn2 = None
    buffer = io.StringIO()
    first_parse = False
    outcome = None
    try:
        # Тот же приём, каким memory-records.py сама грузит memory-archive.py: importlib.
        spec = importlib.util.spec_from_file_location("memory_records_after_move", tool)
        mr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mr)

        conn2 = sqlite3.connect(str(db_path))
        if not mr.has_table(conn2):
            print("ℹ️ слой записей памяти не заведён (шаг схемы 20260904-phoenix-records)"
                  " — пересборка пропущена")
            return

        prior_count = conn2.execute(
            "SELECT COUNT(*) FROM phoenix_records WHERE role=? AND section=?",
            (role, section)).fetchone()[0]
        first_parse = (prior_count == 0)
        with contextlib.redirect_stdout(buffer):
            if prior_count:
                outcome = mr.rebuild(conn2, role, section, actor)
            else:
                mr.parse(conn2, role, section, actor)
    except (Exception, SystemExit) as e:
        print(f"⚠️ ЗАПИСИ РАЗДЕЛА НЕ ПЕРЕСОБРАНЫ: {_one_line(e)} — перенос УЖЕ ЗАПИСАН, "
              f"это не отменяется. Пересобери рукой: python {tool.as_posix()} "
              f"--role {role} --section {section} --rebuild")
        return
    finally:
        if conn2 is not None:
            conn2.close()

    text = buffer.getvalue()
    summary = _records_summary_line(text, first_parse)
    if summary:
        print(summary)
    # Полный захваченный текст — когда сборка НЕ сходится (итог=1 у rebuild(), либо
    # «РАСХОЖДЕНИЕ» в тексте parse()) или по явному слову MEZO_VERBOSE_RECORDS=1.
    # Под этими условиями молчания нет: строка-итог одна ВСЕГДА, кроме случая, когда
    # узор в тексте не нашёлся вовсе, — тогда полный текст печатается взамен неё.
    full_needed = ((outcome not in (None, 0)) or ("РАСХОЖДЕНИЕ" in text)
                    or summary is None
                    or os.environ.get("MEZO_VERBOSE_RECORDS") == "1")
    if full_needed:
        print(text)


def move_to_archive(conn, db_path, role, section, numbers, actor):
    body, saved = read_section(conn, role, section)
    chunks, method = blocks(body)
    bad = [n for n in numbers if not (1 <= n <= len(chunks))]
    if bad:
        sys.exit(f"⛔ НЕ ПЕРЕНЕСЕНО НИЧЕГО: блоков {len(chunks)}, а названы {bad}. "
                 "Отказ целиком, а не частично: перенос половины названного роль "
                 "прочла бы как перенос всего.")
    taken = sorted(set(numbers))
    remaining = [chunk for i, chunk in enumerate(chunks, 1) if i not in taken]
    new_body = "".join(chunk["тело"] for chunk in remaining)
    moved_chars = sum(chunks[i - 1]["знаков"] for i in taken)

    print(f"РОЛЬ {role} · РАЗДЕЛ {section} · резано {method}")
    print(f"  горячее: {len(body)} → {len(new_body)} знаков (унесено {moved_chars})")
    print(f"  блоков:  {len(chunks)} → {len(remaining)}")
    print("  уносим:")
    for i in taken:
        print(f"    📦 {chunks[i-1]['знаков']:>6}б  {chunks[i-1]['тема'][:64]}")
    # ⚖️ ВСТРЕЧНАЯ ПРОВЕРКА ЗДЕСЬ, А НЕ В ПРИЁМКЕ: сумма обязана сойтись ДО записи.
    # Приёмка проверяет то, что уже случилось; здесь мы отказываемся случаться.
    if len(new_body) + moved_chars != len(body):
        sys.exit(f"⛔ НЕ ЗАПИСАНО: {len(new_body)} + {moved_chars} ≠ {len(body)}. "
                 "Знаки не сошлись — значит разбор на блоки потерял текст. "
                 "Это отказ по построению: память не место для «почти сошлось».")
    print("  ✅ сумма сошлась: горячее + унесённое = прежнее тело, знак в знак")

    conn.execute("BEGIN")
    # 🕐 ОДНА МЕТКА ВРЕМЕНИ НА ДЕЙСТВИЕ (возврат COORD, карточка #605, вариант «б»).
    # Это ОДНО действие («штатный перенос») пишет ВРЕМЯ в ТРИ места: moved_at КАЖДОГО
    # унесённого блока в phoenix_archive, saved_at раздела в phoenix и saved_at строки
    # phoenix_history. До этой правки каждое место звало СВОЙ datetime('now') СВОЕЙ
    # отдельной командой SQL (phoenix_archive — DEFAULT схемы, остальные — inline) —
    # а SQLite держит 'now' одинаковым только ВНУТРИ одной команды, не между отдельными
    # командами одной транзакции: секунда между ними МОГЛА перещёлкнуть. read-phoenix.py
    # (archive_move_look) сравнивает эти поля СТРОКАМИ — расхождение читалось бы им как
    # разрыв цепочки переносов. ⇒ время берётся у ИСТОЧНИКА (самой базы, той же
    # транзакцией) ОДИН раз и подставляется ПАРАМЕТРОМ во все три места.
    move_time = conn.execute("SELECT datetime('now')").fetchone()[0]
    for i in taken:
        chunk = chunks[i - 1]
        conn.execute(
            "INSERT INTO phoenix_archive (role, section, topic, body, body_chars, "
            "moved_at, moved_by, origin_saved_at) VALUES (?,?,?,?,?,?,?,?)",
            (role, section, chunk["тема"], chunk["тело"], chunk["знаков"], move_time, actor, saved))
    conn.execute("UPDATE phoenix SET body=?, saved_at=? "
                 "WHERE role=? AND section=?", (new_body, move_time, role, section))
    # 🩸 ЗАПИСЬ В ИСТОРИЮ РАЗДЕЛОВ — ОБЯЗАТЕЛЬНА, И ВОТ ЧЕМ ЭТО ОПЛАЧЕНО.
    # Первая редакция меняла горячее тело напрямую и историю не трогала. Общий прогон
    # тем же часом покраснел: «память: правка мимо инструмента, расхождений 1» — и был
    # прав. Прежнее тело уцелело (его положило последнее обычное сохранение), но НОВОЕ
    # в историю не попало, то есть след правки оборвался ровно на ней.
    # ⚡ КЛАСС: ИНСТРУМЕНТ, ПИШУЩИЙ В ОБЩЕЕ ХРАНИЛИЩЕ МИМО ШТАТНОГО ПУТИ, ЛОМАЕТ НЕ СВОЮ
    # РАБОТУ, А ЧУЖУЮ ПРОВЕРКУ — и краснеет она у ВСЕХ ролей каждый прогон, указывая
    # не на автора. Свой обход стои́т дороже своей же ошибки.
    #
    # ⚠️ ЭТИ ДВЕ СТРОКИ (SQL-текст INSERT) — ЯКОРЬ ПОЛОМКИ ③д ПРИЁМКИ
    # bite-archive-move-look.py (ARCHIVE_HISTORY_BLOCK): приёмка ищет их БУКВАЛЬНО
    # в тексте ЭТОГО файла, чтобы подложить нарочную порчу «второй источник времени».
    # Меняя структуру ЭТОГО вызова — не меняй эти две строки SQL-литерала: сместится
    # якорь, и поломка ③д начнёт биться мимо (карточка #627, ловушка ②).
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_history'").fetchone():
        conn.execute(
            "INSERT INTO phoenix_history (role, section, body, body_chars, saved_at, "
            "actor, reason, prev_chars) VALUES (?,?,?,?,?,?,?,?)",
            (role, section, new_body, len(new_body), move_time, actor,
             f"archive-move: унесено {len(taken)} кусков, {moved_chars} знаков", len(body)))
    else:
        print("⚠️ ИСТОРИИ РАЗДЕЛОВ В ЭТОЙ БАЗЕ НЕТ — перенос НЕобратим штатным путём. "
              "Это сказано вслух, а не пропущено молча.")
    conn.commit()
    archive_totals = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(body_chars),0) FROM phoenix_archive "
        "WHERE role=? AND section=?", (role, section)).fetchone()
    print(f"✅ ПЕРЕНЕСЕНО. В архиве этого раздела: {archive_totals[0]} кусков, "
          f"{archive_totals[1]} знаков")
    print("⚠️ Прежнее тело раздела ЦЕЛИКОМ осталось в истории разделов — "
          "перенос обратим: save-phoenix --history / --restore <номер>")
    # 🎯 КАРТОЧКА #627, ПУНКТ 1: слой `phoenix_records` пересобирается ТЕМ ЖЕ ВЫЗОВОМ,
    # СРАЗУ после того, как перенос напечатал «✅ ПЕРЕНЕСЕНО» и закоммитился — а не ждёт
    # следующего save-phoenix.py. Строка о записях — ПОСЛЕ «✅ ПЕРЕНЕСЕНО» (это отдельный,
    # вторичный шаг над уже состоявшимся переносом, а не условие его успеха). См. разбор
    # над _rebuild_records_after_move() — тот же приём, что и в save-phoenix.py.
    _rebuild_records_after_move(db_path, role, section, actor)


def find_in_archive(conn, role, word):
    # 🩸 ОТБОР ИДЁТ В PYTHON, А НЕ ЧЕРЕЗ LIKE — и это не вкус, а оплаченная находка.
    # LIKE в SQLite регистронезависим ТОЛЬКО ДЛЯ ЛАТИНИЦЫ: кириллица сравнивается
    # строго. Поиск «выдуманный час» не нашёл куска, где стои́т «ВЫДУМАН», и ответил
    # «совпадений нет» — уверенно и неверно.
    # ⚡ КЛАСС: МОЛЧАЩИЙ ОТКАЗ ЧИТАЕТСЯ КАК ОТВЕТ. Пустой ответ поиска неотличим от
    # «такого в архиве нет», и роль пойдёт восстанавливать то, что у неё уже есть.
    # ⚖️ Цена честного пути — чтение всего архива роли в память. Архив измеряется
    # тысячами знаков, а не мегабайтами; когда перестанет — это предмет карточки #525
    # (поиск), и там ему место, а не здесь в виде тихой неправоты.
    lowered = word.lower()
    rows = [r for r in conn.execute(
        "SELECT id, section, topic, body_chars, substr(moved_at,1,16), body "
        "FROM phoenix_archive WHERE role=? ORDER BY id", (role,)).fetchall()
        if lowered in r[2].lower() or lowered in r[5].lower()]
    print("=" * 84)
    print(f"АРХИВ {role} — поиск «{word}»: найдено кусков {len(rows)}")
    print("=" * 84)
    if not rows:
        # ⚖️ Пустой ответ обязан отличать «не нашлось» от «искать негде»: одно «ничего»
        # на две разные беды заставляет спрашивающего гадать, и гадает он неверно.
        total = conn.execute("SELECT COUNT(*) FROM phoenix_archive WHERE role=?",
                             (role,)).fetchone()[0]
        print(f"⚪ совпадений нет. В архиве роли {total} кусков — "
              + ("значит слово не встречается." if total else
                 "архив ПУСТ, то есть искать было негде: это не «нет такого», "
                 "а «ещё ничего не унесено»."))
        return
    for id_, section, topic, chars, when, body in rows:
        print(f"\n📦 #{id_} · {section} · {chars}б · унесено {when} UTC")
        print(f"   ТЕМА: {topic}")
        print("   " + "─" * 78)
        for line in body.splitlines():
            print(f"   {line}")
    print("\n" + "-" * 84)
    print("⚖️ Показаны ТЕЛА целиком, а не выдержки: обрезанный архив равен удалению.")


# ⚖️ ПСЕВДОНИМ (карточка #627, ловушка ②): find-phoenix.py держит имя `найти` снаружи
# через importlib (`_memory_archive.найти(conn, role, args.query)`, .mezosync/scripts —
# правка этого файла не входит в это задание).
найти = find_in_archive


def list_archive(conn, role):
    rows = conn.execute(
        "SELECT section, topic, body_chars, substr(moved_at,1,16), id "
        "FROM phoenix_archive WHERE role=? ORDER BY section, id", (role,)).fetchall()
    hot_chars = conn.execute(
        "SELECT COALESCE(SUM(LENGTH(body)),0) FROM phoenix WHERE role=?",
        (role,)).fetchone()[0]
    archive_chars = sum(r[2] for r in rows)
    print("=" * 84)
    print(f"ПАМЯТЬ {role}: горячее {hot_chars} знаков · архив {archive_chars} знаков "
          f"({len(rows)} кусков)")
    print(f"  читается при пробуждении: {hot_chars}. Архив НЕ читается — он спрашивается.")
    print("=" * 84)
    if not rows:
        print("⚪ архив пуст — ничего не уносилось")
        return
    section = None
    for s, topic, chars, when, id_ in rows:
        if s != section:
            section = s
            print(f"\n── {s} ──")
        print(f"  #{id_:<4} {chars:>6}б  {when} UTC  {topic[:56]}")
    print("\n👉 Достать кусок: --find «слово из темы или тела»")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--role", required=True, help="чья память (ВЕРХНИМ регистром)")
    ap.add_argument("--section", help="раздел: state · plan · identity · history · "
                                      "launcher · rebirth · sources")
    ap.add_argument("--preview", action="store_true", help="показать блоки раздела")
    ap.add_argument("--move", nargs="+", type=int, metavar="N",
                    help="унести блоки с этими номерами (из --preview) в архив")
    ap.add_argument("--find", metavar="СЛОВО", help="искать в архиве по теме и телу")
    ap.add_argument("--list", action="store_true", help="что лежит в архиве роли")
    ap.add_argument("--actor", help="чья РУКА переносит (по умолчанию — сама роль)")
    a = ap.parse_args()

    db = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    conn = sqlite3.connect(str(db))
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_archive'"
                        ).fetchone():
        # путь шага — ОТ РАСПОЛОЖЕНИЯ ЭТОГО СКРИПТА (как у memory-records.py), а не от
        # --db (карточка #632, находка COORD 2026-09-14): «от --db» верно, только пока
        # db лежит рядом со scripts/ по формуле .mezosync/mezosync.db — а --db на КОПИЮ
        # базы (приёмка, песочница) этой формуле не подчиняется и печатал tmp/scripts/…,
        # несуществующий путь на вид правильным текстом. mezo_paths.live_scripts(__file__)
        # ищет корень контейнера ПО ПРИЗНАКУ (.mezosync/mezosync.db), не по соседству с db.
        migration = mezo_paths.live_scripts(__file__) / "migrations" / "20260904-phoenix-archive.py"
        sys.exit("⛔ В этой базе нет архива памяти. Накати шаг:\n"
                 f"   python {migration.as_posix()}")

    role = a.role.upper()      # токен роли регистрозависим — приводим сразу
    # 🪤 РУКА БЕРЁТСЯ ИЗ СРЕДЫ, А НЕ ИЗ АРГУМЕНТА — и вот почему это не придирка.
    # Первая редакция ставила руку по умолчанию равной ВЛАДЕЛЬЦУ памяти: «--actor
    # или сама роль». Тогда запрет на чужую руку обходился тем, что флаг просто
    # НЕ НАЗЫВАЛИ — то есть защита срабатывала лишь у того, кто и так назвался честно.
    # ⚡ Класс: ЗАПРЕТ, КОТОРЫЙ ОБХОДИТСЯ НЕУКАЗАНИЕМ ФЛАГА, защищает только
    # добросовестного. Поймано своей же проверкой через минуту после написания.
    # ⚖️ ГРАНИЦА НАЗЫВАЕТСЯ ЧЕСТНО: MEZO_ROLE тоже можно подменить. Но подмена среды —
    # сознательный обход, а забытый флаг — случайность; механизм отделяет одно от другого
    # и большего обещать не вправе.
    env_actor = (os.environ.get("MEZO_ROLE") or "").strip().upper()
    actor = (env_actor or (a.actor or "").upper())
    # 📌 Имя руки нужно ПЕРЕНОСУ (--move), а не чтению: --list / --find / --preview ничего не
    # пишут. Первая редакция отказывала и чтению — словами про перенос («без имени руки
    # ПЕРЕНОС памяти не делается»): читающему сообщали про запись, и он искал, что же он
    # переносит. Нашёл @RCC (записка #4737 §④), правлено 2026-09-05 (карточка #541).
    if a.move and not actor:
        sys.exit("⛔ НЕ ЗНАЮ, ЧЬЯ РУКА. Назовись: MEZO_ROLE=<ТВОЯ РОЛЬ> перед вызовом "
                 "(или --actor). Без имени руки перенос памяти не делается: "
                 "у переноса обязан быть автор.")

    if a.list:
        list_archive(conn, role)
        return 0
    if a.find:
        find_in_archive(conn, role, a.find)
        return 0
    if not a.section:
        sys.exit("⛔ нужен --section (или --list / --find)")
    if a.move:
        if actor != role:
            # ⚖️ Отказ, а не предупреждение. Слово владельца 2026-09-04 13:41 UTC:
            # «только свою, остальные сами». У чужой руки нет способа узнать, что
            # в памяти важно её владельцу, — а перенос выглядит аккуратной уборкой.
            sys.exit(f"⛔ НЕ ПЕРЕНЕСЕНО: {actor} жмёт память роли {role}. Роль жмёт "
                     "СВОЮ память сама (слово владельца 2026-09-04 13:41 UTC).\n"
                     "   Показать чужую память можно: --preview. Унести — нет.")
        move_to_archive(conn, db, role, a.section, a.move, actor)
        return 0
    show(conn, role, a.section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
