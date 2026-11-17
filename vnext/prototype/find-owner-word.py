#!/usr/bin/env python
# SURFACES: memory, owner-words
# -*- coding: utf-8 -*-
r"""НАЙТИ СЛОВО ВЛАДЕЛЬЦА В ЗАПИСЯХ РАЗГОВОРОВ И НАЗВАТЬ ЕГО ЧАС — карточка #521.

🩸 ЗАЧЕМ (заявка @OPSSRE, найдено делом 2026-08-31 11:14–11:19 UTC). Правило контура велит
брать час слова владельца ЗАМЕРОМ. Роль искала слово по всем записям разговоров и НЕ НАШЛА —
и была в шаге от того, чтобы объявить настоящую цитату владельца выдуманной и снять его
решение. Слово было сказано ИНТЕРФЕЙСОМ ВЫБОРА (нажат вариант, а не набран текст).

    ⚡ ДВА ИСХОДА ВЫГЛЯДЕЛИ ОДИНАКОВО: «слова не было» и «слово пришло выбором» давали
      ОДНО И ТО ЖЕ — пусто. Различить было нечем, а цена ошибки несимметрична: объявив
      верную цитату выдуманной, роль снимает настоящее решение владельца, и он получает
      вопрос, на который уже отвечал.

✅ СПОСОБ НАЙДЕН 2026-09-04 в живом деле (расхождение двух слов по карточке #474). Ответ
интерфейса выбора сохраняется в записи разговора ЦЕЛИКОМ, отдельной записью:

    Your questions have been answered: "<текст вопроса>"="<выбранный вариант>".

⇒ у него есть и вопрос, и выбор, и ЧАС с точностью до миллисекунды. Различение работает
БЕЗ авто-сводок разговора, как и требовал критерий карточки.

ЧТО ЭТОТ ИНСТРУМЕНТ ОТВЕЧАЕТ — ТРИ ИСХОДА, А НЕ ДВА:
    📝 НАЙДЕНО ТЕКСТОМ ......... владелец набрал это сам; час — час его реплики
    🔘 НАЙДЕНО ВЫБОРОМ ......... владелец нажал вариант; час — приход ответа в чат,
                                 то есть ВЕРХНЯЯ граница (сколько он думал до нажатия,
                                 запись не знает и знать не может)
    ✍ СВОИМ ТЕКСТОМ В ОКНЕ .... владелец набрал ответ сам в поле «другое» окна вопросов —
                                 его слово, а не вариант из предложенных; час — как у выбора
    ⚪ НЕ НАЙДЕНО .............. и здесь инструмент НЕ говорит «выдумано»: см. ниже

🔢 КОДЫ ВОЗВРАТА (различимы МАШИНОЙ, а не только в тексте вывода):
    0 — нашли с происхождением «человек» или выбором · 1 — не нашли ничего
    2 — ОТКАЗ МЕРИТЬ (искать было негде)
    3 — совпадения есть, но у всех происхождение не записано или машинное
    4 — ИСКАЛ НЕ ВЕЗДЕ: в прочитанном не нашли (или только спорное), а часть файлов не прочитана

✍ ПРОИСХОЖДЕНИЕ СУДИТСЯ ПО ПОЛЮ ЗАПИСИ, А НЕ ПО ВИДУ ТЕКСТА (с 2026-09-04 20:15 UTC,
  признак нашёл @CHROME, исключение и встречный случай — перемер PROTO; подробно в
  origin_of()). Примета текста осталась ПОДСКАЗКОЙ и решает только там, где поля нет.

═══ КАРТОЧКА #635 (2026-10-31): ОКНО ВОПРОСОВ И ПРИШЕДШЕЕ ПОСРЕДИ ХОДА ═══
Четыре ответа владельца в одном окне (чат PROTO, 2026-09-14T21:03:21Z) — «не найдено» по куску
каждого. Причины, по замеру 31.10 на всех 2325 файлах записей:
    · у ответа ДВЕ формы начала: 757 «Your questions have been answered:», 110 «The user
      answered:» — вторую инструмент не знал (CHOICE_PREFIXES);
    · ответ делился по первой паре «вопрос»="ответ": при нескольких вопросах печатался ПЕРВЫЙ,
      а слово стояло в третьем (замер COORD и OPSSRE 11.10). Теперь — поле записи
      toolUseResult (questions + answers + annotations), ПО ОДНОМУ ответу на вопрос
      (window_answers); текст разбирается, только когда поля нет (parse_choice_text);
    · свой текст из поля «другое» — ответ, не совпадающий ни с одним вариантом, — подписан как
      слово человека; заметка к выбору (annotations) — тоже;
    · пришедшее ПОСРЕДИ хода лежит вложением queued_command, а не репликой «user»: 767 набраны
      человеком, 751 из них больше нигде нет (midturn_items);
    · охват печатается ДВУМЯ счётами раздельно — реплик текстом и ответов в окне (предложение
      RCC 11.10): сведённые в один ноль, они прятали бы, что окна инструмент не читал.
Имена в коде — по-английски (слово владельца 07.09); прежние русские флаги приняты синонимами.

═══ КАРТОЧКА #797 (2026-11-17): ЧТЕНИЕ, КОТОРОЕ НЕ ВОЗВРАЩАЕТСЯ ═══
16–17.11 искатель трижды за сутки повис молча на чтении записи разговора, которую в это время
дописывала среда: ни байта за минуты, процессор стоит, поток один — и процесс не снимался даже
принудительно (запись о нём оставалась в списке процессов). Вызывающий owner-word.py ждал без
предела; запись адресов словам владельца (карточка #795) встала на 50 минут без единой строки.
    · зависший поток снять нельзя ⇒ записи читает ОТДЕЛЬНЫЙ читающий процесс (scan_worker), один
      на прогон, а не на файл (цена запуска); искатель ждёт его, глядя на его файл хода;
    · файл хода растёт раз в секунду, пока номер строки меняется. Тишина дольше предела
      (--read-timeout, 30 с) — чтение не вернулось: файл в «не прочитан», процессу kill без
      ожидания, остальные файлы — новому читающему процессу. Упал читающий процесс — так же;
    · к брошенному процессу у искателя нет каналов: его вывод — в файлы, описатели наследуются
      только явно названные; вызывающий получает вывод искателя, не дожидаясь брошенного;
    · ИСХОД: всё прочитано — вывод и коды прежние. Есть непрочитанные — у итога их число и полные
      пути строками «не прочитан: <путь> — <причина>»; «не найдено» и «только спорное» при них —
      код 4 «искал не везде», а не 1 и не 3; найдено — код 0, непрочитанное названо рядом;
    · СЛЕД БРОШЕННОГО: каталог хода find-owner-word-* его прогон убрать не может — повисший
      процесс держит свои файлы. Процесс потом исчезает, а каталог оставался НАВСЕГДА (замер TAXO
      и COORD 17.11 13:46 UTC: 25 каталогов, живых процессов 0; прежде здесь и в документе выпуска
      было неверно «остаётся, пока процесс жив»). Поэтому каждый прогон при старте убирает
      каталоги хода, где ни в каталоге, ни в его файлах час нет записи (sweep_stale); файлы,
      которые ещё держит живой процесс, пропускаются;
    · КОНТЕЙНЕР: каталоги хода лежат в <Temp>/find-owner-word/, и уборка обходит ТОЛЬКО его.
      17.11 в редакции без контейнера нарочная поломка проверки имени удалила ≈58 тыс. чужих
      каталогов системного Temp (записка #6608) — удаление ограничено местом, а не строкой;
    · предел --read-timeout — от 2 до 600 с: живой прогон пишет в свой каталог не реже раза
      в предел, и уборка соседнего прогона не примет его за брошенный.

⛔ ЧЕГО ЭТОТ ИНСТРУМЕНТ НЕ ДОКАЗЫВАЕТ, СКАЗАНО ПРЯМО. Пустой ответ НЕ доказывает, что
слова не было. Записи разговоров могут быть удалены, усечены при сжатии, лежать в другом
каталоге проектов или относиться к сеансу, чей файл не сохранён. ⇒ «не найдено» означает
«в этих файлах нет», и инструмент печатает, СКОЛЬКО файлов просмотрел — чтобы охват
был виден, а не подразумевался.

Зовут так:
    python <КОНТУР>/vnext-tools/find-owner-word.py --word "ступенчато"
    python <КОНТУР>/vnext-tools/find-owner-word.py --word "пушить можно" --date 2026-08-08
    python <КОНТУР>/vnext-tools/find-owner-word.py --word "различать агентов" --verbose
(прежние имена флагов --слово · --за · --корень · --подробно · --все-файлы принимаются)
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── ЧТЕНИЕ В ОТДЕЛЬНОМ ПРОЦЕССЕ (карточка #797) ──────────────────────────────────────────
# Ключ, которым искатель зовёт сам себя читающим процессом. Человеку он не нужен.
WORKER_FLAG = "--scan-worker"
# Предел тишины: столько секунд без единой новой строки — чтение считается не вернувшимся.
# ⚖️ Число не из замера скорости, а из замера зависания: живое чтение двигает номер строки
# много раз в секунду, а повисшее 16–17.11 стояло минутами. 30 с — с запасом в обе стороны.
DEFAULT_READ_TIMEOUT = 30.0
BEAT_SECONDS = 1.0     # как часто читающий процесс отмечает ход в своём файле
POLL_SECONDS = 0.2     # как часто искатель смотрит на файл хода
MAX_READ_TIMEOUT = 600.0   # верхняя граница --read-timeout: см. STALE_SECONDS
# Каталоги хода лежат в СВОЁМ каталоге-контейнере внутри временного каталога системы, а не
# прямо в нём; имя каждого начинается с WORK_PREFIX.
# 🩸 17.11 14:56–15:02 UTC: в редакции, где каталоги хода лежали прямо в Temp, а уборку держала
# одна проверка имени, нарочная поломка этой проверки удалила в системном Temp ≈58 тыс. чужих
# каталогов (записка #6608, карточка #797). Контейнер ограничивает удаление местом, а не строкой:
# без проверки имени уборка всё равно не выходит за свой каталог.
WORK_HOME = "find-owner-word"
WORK_PREFIX = "find-owner-word-"
# Каталог хода, где ни сам он, ни один его файл не менялись дольше этого, — след брошенного
# прогона. ⚖️ Живой прогон пишет в свой каталог не реже раза в предел тишины (отметка хода или
# новый файл задания после брошенного процесса), а предел не больше MAX_READ_TIMEOUT, —
# поэтому часа тишины у живого не бывает.
STALE_SECONDS = 3600.0

# Каталог записей разговоров. ⚖️ Выводится от домашнего каталога, а не впечатан:
# впечатанный путь сделал бы инструмент непереносимым на другую машину, а молчал бы
# он при этом так же убедительно, как работал.
DEFAULT_ROOT = pathlib.Path.home() / ".claude" / "projects"

# Признак ответа, пришедшего интерфейсом выбора. Форма проверена на живых записях 04.09.
CHOICE_MARK = "questions have been answered"

# 🩸 КАРТОЧКА #635: у того же ответа ДВЕ формы начала. Замер 2026-10-31 по 2325 файлам записей:
# 757 начинаются с «Your questions have been answered:», 110 — с «The user answered:». Вторую
# инструмент не знал, и ответ 2026-09-14T21:03:21Z чата PROTO был «не найден» по каждому куску.
CHOICE_PREFIXES = ("Your " + CHOICE_MARK, "The user answered")

# Особые ответы окна вопросов: варианта владелец не выбрал. Это не слово, но и не пустота —
# у каждого свой следующий шаг читателя, и он назван словами.
NO_ANSWER_MARKS = (
    ("[User did not answer this question",
     "в окне не ответил — ответ пришёл отдельной репликой, ищи её рядом по часу"),
    ("[No preference]", "отметил «без предпочтения»"),
)

# Пришедшее ПОСРЕДИ хода ложится в запись не репликой «user», а вложением queued_command
# (карточка #635, находка COORD 12.10). Замер 31.10: 767 таких набраны человеком, и 751 из них
# нигде больше в записи нет — поиск, не читающий вложений, их не видит вовсе.
MIDTURN_TAG = "   ⟨пришло посреди хода — вложение queued_command⟩"

# 🩸 ПОЙМАНО НА ПЕРВОМ ЖЕ ПРОГОНЕ ЭТОГО ИНСТРУМЕНТА (2026-09-04 16:41 UTC).
# ⚡ КЛАСС: ПОИСК НАХОДИТ СОБСТВЕННОЕ ЭХО. Инструмент читает записи разговоров — и его
# СОБСТВЕННЫЙ вывод ложится в ту же запись. На следующем прогоне он видит там искомые
# слова и объявляет их словом владельца. Два моих разведочных прогона дали два ложных
# «владелец выбрал» с часами 16:36 и 16:37 — через минуту после того, как я их напечатала.
# ⇒ загрязнение РАСТЁТ с каждым прогоном, и чем чаще мерят, тем грязнее замер.
# 👉 Различитель: НАСТОЯЩИЙ ответ интерфейса — это ВЕСЬ текст записи, он с этой метки
#    НАЧИНАЕТСЯ. Эхо несёт её в середине вывода команды. Привязка к началу, не к вхождению.
#
# И вторая половина того же: служебные вставки системы лежат в записи РОЛИ «user» —
# там же, где реплики владельца. Сводка сжатия разговора, вставка навыка, напоминание
# среды: позиция одна, а автор разный. Отсеиваются по началу текста.
SERVICE_PREFIXES = (
    "This session is being continued",
    "Caveat:",
    "<system-reminder>",
    "Base directory for this skill:",
    "<command-name>",
    "<command-message>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "<task-notification>",
    "Another Claude session sent",
    "[Request interrupted",
)

# ⚡ ГЛАВНАЯ ПРАВКА 2026-09-04 19:41 UTC, и она НЕ про перечень.
# 🩸 Три роли за час нашли одно и то же с разных сторон:
#   @OPSSRE — в улове первым стоя́л блок автозадания, чьё тело САМО объявляет
#             «пользователь не присутствует», и он нёс пометку «час ТОЧЕН»;
#   @CHROME — из 11 находок настоящих реплик 2, остальные 9 — вызовы будильников;
#   @COORD  — взял различитель по образцу и отсеял 1 из 10 вместо 9: он искал
#             «Сверка COORD», а в записях стои́т «СВЕРКА COORD» и «Заход сверки COORD».
#             ⇒ РАЗЛИЧИТЕЛЬ ПО ОБРАЗЦУ ТЕКСТА НЕ ГОДИТСЯ В ПРИНЦИПЕ: написаний
#             столько, сколько ролей и смен.
#
# ⚰️ ЗДЕСЬ СТОЯЛО (19:41 UTC): «признака АВТОРА в записи НЕТ ВОВСЕ. У вызова
# будильника и у живой реплики владельца поле происхождения одинаково». ЭТО БЫЛО
# НЕВЕРНО и снято в 20:12 UTC тем же днём: «вызовом будильника» я назвала запись,
# которую владелец вставил руками (текст рождения роли — в нём слова «сверка» и
# «порядок хода»). Поверила словам, а не полю. Признак есть, нашёл @CHROME; счёт
# и исключение — в origin_of(). Надгробие оставлено, чтобы преемник не
# «переоткрыл» ту же ложь тем же путём: она правдоподобна и легко воспроизводится.
#
# ⇒ ЛЕЧИМ НЕ УГАДЫВАНИЕ, А ЛОЖНУЮ УВЕРЕННОСТЬ. Пометка «час ТОЧЕН: это час самой
#   реплики владельца» утверждала ДВА факта, а знала ОДИН: час записи точен — да;
#   что это реплика ВЛАДЕЛЬЦА — инструмент не знает и знать не может.
#   Перечень ниже остаётся, но он — фильтр ИЗВЕСТНЫХ форм, стареющий и неполный,
#   и инструмент говорит это вслух вместо того, чтобы притворяться полным.
MACHINE_HINTS = (
    "исполни наказ-файл",
    "scheduled-tasks",
    "сверка",
    "заход сверки",
    "цикл all-sync",
    "порядок хода",
    "sync-тик",
    "[s2s тик]",
    "ты — роль",
    "ты - роль",
    "автоматическ",
    "the user is not present",
    "automated run",
)


def is_service_insert(text: str) -> bool:
    """Служебная вставка системы, лежащая в позиции реплики владельца."""
    stripped = text.lstrip()
    return any(stripped.startswith(p) for p in SERVICE_PREFIXES)


def machine_hint_of(text: str) -> str | None:
    """Какая примета машинного вызова сработала. None — ни одна.

    ⚖️ РЕГИСТР НЕ ВАЖЕН — оплачено замером @COORD: он искал «Сверка COORD», а в записях
    лежит «СВЕРКА COORD» и «Заход сверки COORD», и отсев поймал 1 из 10 вместо 9.
    ⛔ И перечень всё равно НЕПОЛОН: это фильтр известных форм, а не знание автора.
    Потому находки не выбрасываются, а ОТДЕЛЯЮТСЯ — решает читатель, а не список.
    """
    lowered = text.lower()
    for p in MACHINE_HINTS:
        if p in lowered:
            return p
    return None


OLD_ALARM_WRAPPER = "<scheduled-task"


def origin_of(rec: dict) -> str:
    """Кто ЗАПИСАЛ реплику — по полю записи, а не по виду текста.

    🔑 ПРИЗНАК НАШЁЛ @CHROME (записка #4702, 2026-09-04 19:40 UTC): у набранного
    человеком стои́т поле origin = {"kind": "human"}, у машинных строк поля нет.
    Его замер: 6 из 6 настоящих с полем · 283 вызова будильника — ноль с полем.

    🩸 МОЙ ПЕРЕМЕР 2026-09-04 20:12 UTC — поимённо, потому что часом раньше я
    утверждала владельцу ОБРАТНОЕ («признака автора нет вовсе»), взяв за вызов
    будильника запись, которую владелец вставил РУКАМИ (текст моего рождения —
    в нём есть слова «сверка» и «порядок хода», и я поверила словам, а не полю).
    ⚡ КЛАСС: судила по ВИДУ там, где была запись о ПРОИСХОЖДЕНИИ.
    Счётом по всем 620 файлам:
        поле «human» ЕСТЬ ....... 2240 человеческих реплик
        поля НЕТ ................ 899 машинных строк по примете  (@CHROME прав)
        НО: поля нет и у ........ 559 человеческих на вид — чаты 09–15.08 в
                                  ДРУГОМ проекте (тот клиент поля не писал) и
                                  наказы ролей помощникам (автор — роль, не человек)
        ИСКЛЮЧЕНИЕ .............. 38 вызовов будильника старой обёртки
                                  «<scheduled-task …» 27–31.08 несут «human»
    ⇒ три исхода, а не два, и каждый назван ниже своим словом.
    """
    o = rec.get("origin")
    if o is None:
        return "не записано"
    kind = o.get("kind") if isinstance(o, dict) else None
    return "человек" if kind == "human" else f"иное: {kind}"


def user_turns(file_name: pathlib.Path, where: dict | None = None):
    """Выдать (час, вид, текст, происхождение, служебные_метки, ответ_окна) для реплик роли
    «user» и для вложений queued_command (пришедшее посреди хода).

    вид: 'текст' — лежит в позиции набранного · 'выбор' — ответ в окне вопросов, ПО ОДНОМУ на
    вопрос (карточка #635) · 'посреди-хода' — вложение с полем «человек» · 'посреди-хода-механизм'
    — то же вложение от механизма · 'команда-механизма' · 'сводка'.
    ответ_окна: у вида 'выбор' — словарь из window_answers() либо parse_choice_text(), иначе None.
    происхождение: 'человек' · 'не записано' · 'иное: <вид>' — см. origin_of().
    служебные_метки: подсадка навыка (isMeta) и сводка сжатия (isCompactSummary) —
    у них поля нет ЗАКОННО, и в «не записано» им не место.
    where: словарь, в который пишется номер строки файла (с 1), разбираемой сейчас, —
    адрес источника находки (карточка #795). Форма выдачи не меняется: строки yield служат
    образцами нарочных поломок приёмки bite-find-owner-word.py.
    """
    try:
        fh = open(file_name, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for lineno, line in enumerate(fh, 1):
            if where is not None:
                where["line"] = lineno
            if ('"type":"user"' not in line and '"type": "user"' not in line
                    and "queued_command" not in line):
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") == "attachment":
                yield from midturn_items(rec)
                continue
            if rec.get("type") != "user":
                continue
            ts = rec.get("timestamp", "")
            # ⚡ ДВЕ РАЗНЫЕ МЕТКИ, и слить их — значит спрятать будильник (поймано 20:17 UTC:
            # нынешние вызовы будильника приходят как подсадка механизма, isMeta=True).
            marks = ("подсадка" if rec.get("isMeta") else
                     "сводка" if rec.get("isCompactSummary") else None)
            origin = origin_of(rec)
            body = rec.get("message", {}).get("content")
            if isinstance(body, str) and origin == "человек" and body.lstrip().startswith("<command-"):
                # ⚡ КОСАЯ КОМАНДА ВЛАДЕЛЬЦА («/loop 2h sync …») хранится в служебной обёртке
                # <command-name>…<command-args>…</command-args> — и отсеивалась как служебное,
                # хотя поле говорит «человек». Найдено на живом случае @CORE 04.09 20:55 UTC:
                # его основание для работы весь вечер — эта команда — было невидимо поиску.
                # Поле сильнее обёртки: вынимаем имя команды и её слова, показываем как реплику.
                name_m = re.search(r"<command-name>(.*?)</command-name>", body, re.S)
                arg_m = re.search(r"<command-args>(.*?)</command-args>", body, re.S)
                text = ((name_m.group(1).strip() if name_m else "") + " " + (arg_m.group(1).strip() if arg_m else "")).strip()
                if text:
                    yield ts, "текст", text + "   ⟨косая команда, набрана владельцем⟩", origin, marks, None
                continue
            if isinstance(body, str) and body.lstrip().startswith("<command-"):
                # 🔑 ТА ЖЕ ОБЁРТКА БЕЗ ПОЛЯ «ЧЕЛОВЕК» — подача механизма: перенос пробуждения
                # (ScheduleWakeup) кладёт в чат ту же команду «/loop …» повторно, и запись несёт
                # НИ поля, НИ метки isMeta — по форме она неотличима от набранной человеком.
                # Материал @CORE (карточка #544 ④): 19:36:00 · 20:46:19 · 21:50:00 UTC 04.09, у каждой
                # свой перенос часом раньше; по всем файлам 181 запись формы «<command-name>» без
                # единой метки (перемер PROTO 05.09; у CORE 96 — он считал только «/loop»).
                # До 05.09 они отсеивались МОЛЧА как служебное. Молчаливый отсев неотличим от
                # «слова не было» — показываем их в 🤖, чтобы читатель видел, что слово в чат
                # ПРИХОДИЛО, но не от владельца. Судится ВИДОМ записи, не приметой текста.
                name_m = re.search(r"<command-name>(.*?)</command-name>", body, re.S)
                arg_m = re.search(r"<command-args>(.*?)</command-args>", body, re.S)
                text = ((name_m.group(1).strip() if name_m else "") + " " + (arg_m.group(1).strip() if arg_m else "")).strip()
                if text:
                    yield ts, "команда-механизма", text, origin, marks, None
                continue
            if isinstance(body, str):
                if marks == "сводка":
                    # сводка сжатия отдаётся ОТДЕЛЬНЫМ видом: её не показывают как слово,
                    # но и не прячут число — одно событие лежит и в записи, и в пересказе
                    yield ts, "сводка", body, origin, marks, None
                elif body.strip() and not is_service_insert(body):
                    yield ts, "текст", body, origin, marks, None
                continue
            if not isinstance(body, list):
                continue
            for item in body:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and item.get("text", "").strip():
                    if not is_service_insert(item["text"]):
                        yield ts, "текст", item["text"], origin, marks, None
                elif item.get("type") == "tool_result":
                    c = item.get("content")
                    s = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                    # ⛔ НАЧИНАЕТСЯ, а не «содержит»: см. разбор про эхо выше. Обе формы начала.
                    if not s.lstrip().startswith(CHOICE_PREFIXES):
                        continue
                    # Поле записи сильнее текста (карточка #635): в нём каждый вопрос со своими
                    # вариантами. Текст разбирается, только когда поля нет.
                    answers = window_answers(rec.get("toolUseResult"))
                    if answers is None:
                        answers = parse_choice_text(s)
                    for ans in answers:
                        yield ts, "выбор", ans["match"], origin, marks, ans


def midturn_items(rec: dict):
    """Вложение queued_command — то, что пришло ПОСРЕДИ хода (карточка #635).

    Происхождение лежит не в записи, а во вложении: attachment.origin.kind. «human» — набрал
    человек; «peer» — записка другой сессии; «task-notification» — извещение о задаче;
    «coordinator» — сообщение координатора; поля нет — подача механизма (замер 31.10: это
    извещения о задачах и одно событие CI). Текст — attachment.prompt: строка либо список
    кусков {"type": "text"} (46 из 767 человеческих — списком).
    """
    att = rec.get("attachment")
    if not isinstance(att, dict) or att.get("type") != "queued_command":
        return
    prompt = att.get("prompt")
    if isinstance(prompt, list):
        prompt = "\n".join(p.get("text", "") for p in prompt
                           if isinstance(p, dict) and p.get("type") == "text")
    if not isinstance(prompt, str) or not prompt.strip():
        return
    ts = rec.get("timestamp") or att.get("timestamp", "")
    o = att.get("origin")
    who = o.get("kind") if isinstance(o, dict) else None
    if who == "human":
        yield ts, "посреди-хода", prompt + MIDTURN_TAG, "человек", None, None
    else:
        # пятым элементом — вид вложения (commandMode): он идёт в причину строки 🤖
        yield (ts, "посреди-хода-механизм", prompt,
               f"происхождение «{who}»" if who else "происхождение не записано",
               att.get("commandMode"), None)


def special_answer(s: str):
    """Особый ответ окна (владелец не выбрал) — его описание словами; иначе None."""
    return next((words for prefix, words in NO_ANSWER_MARKS if s.startswith(prefix)), None)


def split_answer(raw, labels: list) -> tuple:
    """Ответ одного вопроса → (выбранные варианты, свой текст, особый ответ).

    Несколько выбранных приходят списком либо строкой через запятую — а запятая бывает и внутри
    варианта (ответ 14.09 «…,mezosync_v6.sql — оставить,…»). Поэтому строку не режем по запятым,
    а вынимаем из неё известные варианты целыми кусками между запятыми, длинные первыми; что
    осталось — свой текст из поля «другое», набранный человеком.
    """
    items = raw if isinstance(raw, list) else [raw]
    picked, own, special = [], [], None
    for it in items:
        s = (it if isinstance(it, str) else json.dumps(it, ensure_ascii=False)).strip()
        mark = special_answer(s)
        if mark:
            special = mark
            continue
        rest = s
        for label in sorted({x for x in labels if x}, key=len, reverse=True):
            pat = re.compile(r"(^|,)\s*" + re.escape(label) + r"\s*(?=,|$)")
            if pat.search(rest):
                picked.append(label)
                rest = pat.sub(r"\1", rest, count=1)
        rest = re.sub(r"(\s*,\s*){2,}", ", ", rest).strip(" ,")
        if rest:
            own.append(rest)
    whole = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    picked.sort(key=whole.find)
    return picked, ("; ".join(own) or None), special


def window_answers(tur) -> list | None:
    """Ответы окна вопросов по полю записи toolUseResult — ПО ОДНОМУ на вопрос (карточка #635).

    Поле несёт questions (текст вопроса и его варианты) и answers — словарь «вопрос → ответ»;
    у части записей ещё annotations — «вопрос → {notes: заметка владельца к выбору}».
    🩸 Прежде ответ разбирался по ТЕКСТУ и делился по первой паре «вопрос»="ответ": при
    нескольких вопросах печатался первый, а слово стояло в третьем (замер COORD и OPSSRE 11.10).
    None — поля нет или оно не той формы: тогда разбирается текст (parse_choice_text).
    """
    if not isinstance(tur, dict):
        return None
    answers, questions = tur.get("answers"), tur.get("questions")
    if not isinstance(answers, dict) or not isinstance(questions, list):
        return None
    labels = {}
    for q in questions:
        if isinstance(q, dict) and isinstance(q.get("question"), str):
            labels[q["question"]] = [o.get("label", "") for o in (q.get("options") or [])
                                     if isinstance(o, dict)]
    notes = tur.get("annotations") if isinstance(tur.get("annotations"), dict) else {}
    result = []
    for i, (question, raw) in enumerate(answers.items(), 1):
        picked, own, special = split_answer(raw, labels.get(question, []))
        ann = notes.get(question)
        note = ann.get("notes") if isinstance(ann, dict) else None
        note = note.strip() if isinstance(note, str) and note.strip() else None
        answer_text = "\n".join(picked + [own or "", note or ""])
        result.append({"question": question, "picked": picked, "own": own, "note": note,
                       "special": special, "of": (i, len(answers)), "source": "поле записи",
                       "answer_text": answer_text, "match": question + "\n" + answer_text})
    return result


def parse_choice_text(s: str) -> list:
    """Запасной путь, когда поля toolUseResult нет: пары «вопрос»="ответ" из ТЕКСТА результата.

    ⚖️ Разбор нарочно грубый и НЕ падает: если форма изменится, инструмент отдаст строку
    целиком, а не соврёт пустотой. Молчаливый разбор хуже грубого — он выглядит успехом.
    ⚠️ Без поля вариант от своего текста не отличить: варианты знает только поле.
    """
    body = s.lstrip()
    for prefix in CHOICE_PREFIXES:
        if body.startswith(prefix):
            body = body[len(prefix):]
            break
    body = body.lstrip(": ").strip()
    for tail in (" You can now continue", " Read the answers carefully"):
        if tail in body:
            body = body.split(tail, 1)[0]
    body = body.rstrip(" .")
    pairs = [seg.split('"="', 1) for seg in body.split('", "') if '"="' in seg]
    if not pairs:
        pairs = [(None, body)]
    result = []
    for i, (question, answer) in enumerate(pairs, 1):
        q = question.strip('"') if question is not None else None
        a = answer.strip('"')
        special = special_answer(a)
        result.append({"question": q, "picked": [] if special else [a], "own": None,
                       "note": None, "special": special, "of": (i, len(pairs)),
                       "source": "текст результата (поля нет — вариант от своего текста не отличить)",
                       "answer_text": "" if special else a, "match": (q or "") + "\n" + a})
    return result


def scan_worker(job_path: str, out_path: str) -> int:
    """ЧИТАЮЩИЙ ПРОЦЕСС (карточка #797): читает файлы задания по порядку и пишет в свой файл хода
    строки JSON — {"start": i} перед файлом, {"tick": i, "line": n} раз в секунду, пока номер
    строки меняется, {"done": i, "seen": …, "hits": […]} по концу файла, {"end": true} в конце.

    hits — то, что прежде отбиралось прямо в цикле main(): записи искомой даты с искомым куском,
    вместе с номером строки (адрес источника, карточка #795). seen — счёт охвата файла.
    ⚖️ Отметку хода ставит ОТДЕЛЬНЫЙ поток по номеру строки, а не сам цикл чтения: повисшее чтение
    отпускает остальные потоки, и тишина в файле хода значит «номер строки не двигался»."""
    job = json.loads(pathlib.Path(job_path).read_text(encoding="utf-8"))
    date, needle = job.get("date"), job["needle"]
    lock = threading.Lock()
    out = open(out_path, "a", encoding="utf-8")
    state = {"i": None, "where": None, "mark": None, "stop": False}

    def emit(rec: dict) -> None:
        with lock:
            if not out.closed:
                out.write(json.dumps(rec, ensure_ascii=True) + "\n")
                out.flush()

    def beat() -> None:
        while not state["stop"]:
            time.sleep(BEAT_SECONDS)
            cur = state["where"]
            mark = (state["i"], cur.get("line") if cur is not None else None)
            if mark != state["mark"]:
                state["mark"] = mark
                emit({"tick": mark[0], "line": mark[1]})

    threading.Thread(target=beat, daemon=True).start()
    for i, name in enumerate(job["files"]):
        where: dict = {}
        state["i"], state["where"] = i, where
        emit({"start": i})
        seen = {"текст": 0, "выбор": 0, "посреди-хода": 0}
        hits = []
        for ts, kind, text, origin, marks, window in user_turns(pathlib.Path(name), where):
            if date and not ts.startswith(date):
                continue
            if kind in ("выбор", "посреди-хода"):
                seen[kind] += 1
            elif kind == "текст" and origin == "человек":
                seen["текст"] += 1
            if needle not in text.lower():
                continue
            hits.append([ts, kind, text, origin, marks, window, where.get("line")])
        emit({"done": i, "seen": seen, "hits": hits})
    emit({"end": True})
    state["stop"] = True
    with lock:
        out.close()
    return 0


def read_records(path: pathlib.Path) -> list:
    """Строки файла хода читающего процесса. Недописанная последняя строка не берётся."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    recs = []
    for ln in raw.splitlines(keepends=True):
        if not ln.endswith("\n"):
            break
        try:
            recs.append(json.loads(ln))
        except ValueError:
            continue
    return recs


def is_link(path: str) -> bool:
    """Ссылка или точка соединения: обходить и удалять сквозь неё нельзя — за ней чужое место."""
    if os.path.islink(path):
        return True
    return hasattr(os.path, "isjunction") and os.path.isjunction(path)


def work_home() -> pathlib.Path:
    """Свой каталог-контейнер для каталогов хода: <Temp>/find-owner-word (создаётся при нужде)."""
    home = pathlib.Path(tempfile.gettempdir()) / WORK_HOME
    home.mkdir(exist_ok=True)
    return home


def sweep_stale(home: pathlib.Path, now: float) -> int:
    """Убрать свои каталоги хода, брошенные прежними прогонами (карточка #797, заметка TAXO 3).

    Прогон, бросивший повисший читающий процесс, свой каталог убрать не может: повисший процесс
    держит свои файлы, и rmtree их пропускает. Процесс потом исчезает, а каталог остаётся навсегда.
    Поэтому убирает каждый следующий прогон — каталоги хода, где ни в каталоге, ни в одном его
    файле нет записи дольше STALE_SECONDS. Не удалось судить о свежести (нет прав, файл исчез
    посреди обхода) — каталог не трогается. Файлы, которые ещё держит живой процесс, rmtree
    пропускает: такой каталог останется до следующего раза.
    ⛔ Обходит ТОЛЬКО свой контейнер home (work_home), а не весь Temp: удаление ограничено местом.
    Проверка имени WORK_PREFIX — вторая защита внутри контейнера, а не единственная. Контейнер —
    ссылка или точка соединения — уборки нет вовсе. Ссылки и точки соединения внутри не трогаются.
    Возвращает число убранных каталогов."""
    removed = 0
    if is_link(str(home)):
        return 0
    try:
        entries = list(os.scandir(home))
    except OSError:
        return 0
    for e in entries:
        if not e.name.startswith(WORK_PREFIX):
            continue
        try:
            # ⚠️ у точки соединения is_dir(follow_symlinks=False) — True (замер TAXO 17.11):
            # держит только is_link
            if e.is_symlink() or not e.is_dir(follow_symlinks=False) or is_link(e.path):
                continue
            # os.stat, а не кэш обхода: у файла, который держит открытым другой процесс, кэш
            # каталога в Windows отстаёт от настоящего времени записи
            newest = os.stat(e.path, follow_symlinks=False).st_mtime
            for f in os.scandir(e.path):
                newest = max(newest, os.stat(f.path, follow_symlinks=False).st_mtime)
        except OSError:
            continue
        if now - newest <= STALE_SECONDS:
            continue
        shutil.rmtree(e.path, ignore_errors=True)
        if not os.path.exists(e.path):
            removed += 1
    return removed


def scan_files(files: list, date, needle: str, limit: float):
    """Прочитать файлы читающим процессом с пределом тишины (карточка #797).

    Возвращает (прочитанные, непрочитанные): [(файл, seen, hits)] в порядке файлов и
    [(файл, причина)]. Файл, на котором читающий процесс замолчал дольше предела или упал,
    пропускается; остальные читает новый читающий процесс.
    ⛔ Брошенный процесс НЕ ждём ни wait, ни чтением его вывода: процесс, повисший в чтении,
    не снимается и принудительно (16–17.11, три случая), и любое ожидание повисло бы вместе с ним.
    Его вывод идёт в файлы, а не в каналы искателя, и наследует он только три названных
    описателя — поэтому и вызывающий искатель (owner-word.py) своего вывода дождётся."""
    scanned, unread = [], []
    if not files:
        return scanned, unread
    # сперва убрать следы прежних брошенных прогонов, потом завести свой каталог — оба в контейнере
    home = work_home()
    sweep_stale(home, time.time())
    work = pathlib.Path(tempfile.mkdtemp(prefix=WORK_PREFIX, dir=home))
    me = str(pathlib.Path(__file__).resolve())
    start, n = 0, 0
    try:
        while start < len(files):
            n += 1
            batch = files[start:]
            job, out, err = work / f"job-{n}.json", work / f"out-{n}.jsonl", work / f"err-{n}.txt"
            job.write_text(json.dumps({"files": [str(p) for p in batch], "date": date,
                                       "needle": needle}, ensure_ascii=True), encoding="utf-8")
            out.write_bytes(b"")
            with open(err, "wb") as err_fh:
                proc = subprocess.Popen([sys.executable, me, WORKER_FLAG, str(job), str(out)],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=err_fh)
            size, moved, code = -1, time.monotonic(), None
            while True:
                try:
                    code = proc.wait(timeout=POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    code = None
                try:
                    now_size = out.stat().st_size
                except OSError:
                    now_size = size
                if now_size != size:
                    size, moved = now_size, time.monotonic()
                if code is not None or time.monotonic() - moved > limit:
                    break
            recs = read_records(out)
            done = [r for r in recs if "done" in r]
            for r in done:
                scanned.append((batch[r["done"]], r["seen"], r["hits"]))
            if any("end" in r for r in recs) or len(done) >= len(batch):
                if code is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                break
            cur = len(done)
            if code is None:
                try:
                    proc.kill()     # не ждём: снимется ли он, искателю неважно
                except OSError:
                    pass
                started = any(r.get("start") == cur for r in recs)
                why = (f"чтение не вернулось за {limit:g} с (ни одной новой строки) — файл пропущен, "
                       f"читающий процесс {proc.pid} брошен без ожидания" if started else
                       f"читающий процесс {proc.pid} не начал этот файл за {limit:g} с — брошен без ожидания")
            else:
                try:
                    tail = err.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                except OSError:
                    tail = []
                why = (f"читающий процесс упал на этом файле, код {code}"
                       + (f": {tail[-1][:240]}" if tail else ""))
            unread.append((batch[cur], why))
            start += cur + 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return scanned, unread


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == WORKER_FLAG:
        return scan_worker(sys.argv[2], sys.argv[3])
    ap = argparse.ArgumentParser()
    # Флаги по-английски (слово владельца 07.09 о коде); прежние русские имена — синонимы:
    # ими инструмент зовут свод правил, карточки и память ролей.
    ap.add_argument("--word", "--слово", dest="word", required=True,
                    help="искомый кусок текста (регистр не важен); прежнее имя --слово")
    ap.add_argument("--date", "--за", dest="date", default=None,
                    help="только за эту дату, ГГГГ-ММ-ДД; прежнее имя --за")
    ap.add_argument("--root", "--корень", dest="root", default=str(DEFAULT_ROOT),
                    help="каталог записей разговоров; прежнее имя --корень")
    ap.add_argument("--verbose", "--подробно", dest="verbose", action="store_true",
                    help="печатать текст найденного целиком, а не первые 200 знаков; "
                         "прежнее имя --подробно")
    ap.add_argument("--all-files", "--все-файлы", dest="all_files", action="store_true",
                    help="читать ВСЕ записи, даже правленные до искомой даты "
                         "(отключает отбор по времени правки — см. разбор ниже); "
                         "прежнее имя --все-файлы")
    ap.add_argument("--read-timeout", dest="read_timeout", type=float, default=DEFAULT_READ_TIMEOUT,
                    help="предел тишины чтения в секундах: файл, в котором за это время не прочитано "
                         f"ни одной новой строки, пропускается и называется у итога (по умолчанию "
                         f"{DEFAULT_READ_TIMEOUT:g}; от 2 — отметка хода ставится раз в секунду — "
                         f"до {MAX_READ_TIMEOUT:g}: дольше уборка соседнего прогона приняла бы живой "
                         "каталог хода за брошенный)")
    a = ap.parse_args()
    if a.read_timeout < 2 * BEAT_SECONDS:
        print(f"⛔ ОТКАЗ МЕРИТЬ: предел --read-timeout {a.read_timeout:g} с меньше {2 * BEAT_SECONDS:g} с — "
              "читающий процесс отмечает ход раз в секунду, и живое чтение было бы названо повисшим.")
        return 2
    if a.read_timeout > MAX_READ_TIMEOUT:
        print(f"⛔ ОТКАЗ МЕРИТЬ: предел --read-timeout {a.read_timeout:g} с больше {MAX_READ_TIMEOUT:g} с — "
              "каталог хода такого прогона мог бы молчать час, и уборка соседнего прогона приняла бы его "
              "за брошенный.")
        return 2

    root = pathlib.Path(a.root)
    if not root.is_dir():
        # ⛔ Отказ мерить, а не «ничего не нашлось»: пустой ответ от несуществующего
        # каталога неотличим от честного «нет такого слова» — ровно та беда, которую
        # эта карточка и лечит.
        # 🩸 ПОЙМАНО СВОЕЙ ЖЕ ПРИЁМКОЙ, первым её прогоном (04.09 17:44 UTC). Здесь
        # стояло `sys.exit("текст")` — оно печатает верные слова и возвращает код 1,
        # ТОТ ЖЕ, что «искал и не нашёл».
        # ⚡ КЛАСС: ЧЕЛОВЕК РАЗЛИЧАЕТ, МАШИНА — НЕТ. Различение, живущее только в тексте
        # вывода, недоступно вызывающему: сценарий, приёмка и общий прогон видят ОДНО
        # число. Это ровно та беда, ради которой заведена эта задача, — воспроизведённая
        # мной внутри лекарства от неё.
        print(f"⛔ ОТКАЗ МЕРИТЬ: каталога записей разговоров нет — {root}")
        print("   Это НЕ «слова не было»: искать было негде. Укажи --root.")
        return 2

    needle = a.word.lower()
    files_read = 0
    # четыре корзины, и это НЕ оформление — у каждой свой следующий шаг читателя
    by_human, by_choice, no_origin, machine = [], [], [], []
    # 📍 АДРЕС ИСТОЧНИКА НАХОДКИ (карточка #795): (час, имя файла, текст) → (полный путь, номер строки).
    # Отдельным словарём, а не полем записи: записи корзин разбираются по местам в пяти местах ниже.
    addr: dict = {}
    summaries = 0
    # ДВА СЧЁТА ОХВАТА РАЗДЕЛЬНО (карточка #635, предложение RCC 11.10): сколько реплик, набранных
    # текстом, и сколько ответов в окне вопросов просмотрено за отбор — независимо от искомого
    # слова. Сведённые в один ноль, они прятали бы, что окна инструмент не читал.
    seen = {"текст": 0, "выбор": 0, "посреди-хода": 0}

    # ── ОТБОР ФАЙЛОВ ПО ВРЕМЕНИ ПРАВКИ (карточка #530) ──────────────────────────────
    # 📏 ЗАМЕР 2026-09-04 22:50 UTC, роль OPSSRE, 620 файлов / 1 862 МБ:
    #      обход каталогов 0,03 с · чтение строк 4,63 с · разбор JSON 1,88 с
    #      весь прогон инструмента ......... 10,3 с (не «больше трёх минут»)
    #   ⇒ дорого НЕ разбор, а ЧТЕНИЕ ПОЛУТОРА ГИГАБАЙТ. Разбор json — 1,9 с из 10,3,
    #     и «грубый отбор по подстроке до разбора» (догадка (а) карточки) купил бы
    #     секунды ценой ложного «не найдено» на экранированной кириллице. НЕ СДЕЛАНО
    #     НАРОЧНО: измерено, что там не время.
    # 🎯 Сделано (б): при --date <дата> файл, правленный ДО начала этой даты, не читается.
    #      --date 2026-09-04 ⇒ 25 файлов из 620, 486 МБ вместо 1 862 — НЕ ЧИТАЕМ 74%
    # ⚠️ ЧТО ЭТОТ ОТБОР МОЖЕТ ПРОПУСТИТЬ, названо ДО починки: файл, чьё время правки
    #    старше искомой даты, но внутри лежит запись этой даты. Обычной дописью такого
    #    не бывает (дописал ⇒ время правки новее записи), но так ведёт себя ВОССТАНОВЛЕНИЕ
    #    ИЗ КОПИИ со старым временем. ⇒ отбор ОТКЛЮЧАЕМ (--all-files) и НАЗЫВАЕТСЯ ВСЛУХ
    #    в строке охвата: сужение, о котором читатель не знает, — это ложное «не найдено».
    skipped = 0
    threshold = None
    if a.date and not a.all_files:
        try:
            # 🔎 Приёмка @PROTO 05.09 (карточка #530): порог — ПОЛНОЧЬ UTC искомой даты, не местная.
            # Даты записей — UTC («…Z»), и отбор записей по --date идёт по UTC; «наивная» полночь
            # через .timestamp() — местная: при смещении +02 порог уезжал на 2 ч РАНЬШЕ (лишние
            # два часа читаем — безвредно), а при отрицательном смещении уехал бы ПОЗЖЕ — и файл,
            # дописанный последний раз между полночью UTC и местной, был бы пропущен вместе
            # с записями искомой даты: ложное «не найдено» на машине западнее Гринвича.
            # Здесь смещение +02 — беда не воспроизводилась; названа по построению, не замером.
            threshold = dt.datetime.fromisoformat(a.date).replace(tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            print(f"⛔ ОТКАЗ МЕРИТЬ: дату «{a.date}» не разобрать, нужна форма ГГГГ-ММ-ДД.")
            return 2

    to_read = []
    for f in root.rglob("*.jsonl"):
        if threshold is not None:
            try:
                if f.stat().st_mtime < threshold:
                    skipped += 1
                    continue
            except OSError:
                pass          # не смогли узнать время правки — читаем, а не пропускаем
        to_read.append(f)
    # ⏱ ЧИТАЕТ ОТДЕЛЬНЫЙ ПРОЦЕСС С ПРЕДЕЛОМ (карточка #797): отбор по дате и по искомому куску —
    # там же, где прежде, только в читающем процессе (scan_worker); суждение о находках — здесь.
    scanned, unread = scan_files(to_read, a.date, needle, a.read_timeout)
    files_read = len(scanned)
    for f, seen_f, hits in scanned:
        for k in seen:
            seen[k] += seen_f.get(k, 0)
        for ts, kind, text, origin, marks, window, line in hits:
            # номер строки — тем же словарём, что до карточки #797: строка addr.setdefault ниже —
            # образец нарочной поломки МД приёмки bite-owner-word-source.py
            where = {"line": line}
            if kind == "сводка":
                summaries += 1
                continue
            entry = (ts, f.parent.name, f.name, text)
            addr.setdefault((ts, f.name, text), (f.resolve().as_posix(), where.get("line")))
            if kind == "выбор":
                by_choice.append(entry + (window,))
                continue
            if kind == "посреди-хода-механизм":
                machine.append(entry + (f"пришло посреди хода (вложение queued_command, вид "
                                        f"«{marks or '—'}»), {origin}: не набрано человеком",))
                continue
            if kind == "команда-механизма":
                machine.append(entry + ("косая команда в обёртке БЕЗ поля «человек» — повтор "
                                          "механизма (перенос пробуждения); слово владельца — "
                                          "та же команда С полем, ищи её в 📝",))
                continue
            hint = machine_hint_of(text)
            if origin == "человек":
                # ⚠️ ИСКЛЮЧЕНИЕ, найденное перемером 04.09 20:12 UTC: старая обёртка
                # будильника (27–31.08) записывалась С полем «человек». Судим по ней.
                if text.lstrip().startswith(OLD_ALARM_WRAPPER):
                    machine.append(entry + ("обёртка будильника 27–31.08, поле «человек» ложное",))
                else:
                    by_human.append(entry + (hint,))
            elif origin == "не записано":
                # 🔑 ПОДАЧА МЕХАНИЗМА (isMeta) ⇒ 🤖. История этой ветки — за одни сутки ТРИ редакции:
                #   20:17 UTC 04.09 — «isMeta ⇒ машинное» (как здесь);
                #   20:55 UTC 04.09 — снято по находке @CORE (записка #4716): «в моём чате повтор
                #     слова владельца из /loop приходит с isMeta — 2 из 6»;
                #   05.09 — @CORE ОТОЗВАЛ находку (записка #4760): те «2 из 6» были ударами задания,
                #     заведённого ЕГО рукой (CronCreate 18:03:48 UTC, шаг «13 */2 * * *»). Замер по
                #     ВСЕМ записям разговоров, CORE и PROTO независимо: реплик с полем «человек»
                #     И меткой isMeta — НОЛЬ (из ~130 тыс.). Основания у снятия не осталось ни одного.
                # ⚡ Метку isMeta ставит клиент на то, что подал САМ: тело навыка, удар будильника,
                # напоминание среды. Текст под ней может быть словом владельца (аргумент его /loop),
                # но ЗАПИСЬ — не его новое слово: он сказал это ОДИН раз, там, где стоит поле «человек».
                # ⇒ Такая запись идёт в 🤖 с причиной, а в ⚪ («чей голос — не узнать») ей не место:
                # чей голос, известно — механизма. Кто перечитает эту ветку и захочет снова снять
                # суждение — сперва перемерь: `человек И isMeta` по всем файлам должно стать > 0.
                if marks == "подсадка":
                    machine.append(entry + ("подано механизмом (isMeta): тело навыка, удар будильника "
                                              "или напоминание среды — не новое слово владельца",))
                elif hint:
                    machine.append(entry + (f"поля нет + примета «{hint}»",))
                else:
                    no_origin.append(entry + (None,))
            else:
                machine.append(entry + (f"происхождение {origin}",))

    print("=" * 92)
    print(f"ПОИСК СЛОВА ВЛАДЕЛЬЦА: «{a.word}»"
          + (f" · только за {a.date}" if a.date else ""))
    print(f"охват: файлов записей просмотрено {files_read} · корень {root}")
    print(f"       за отбор РАЗДЕЛЬНО: реплик текстом (поле «человек») {seen['текст']} · "
          f"ответов в окне вопросов {seen['выбор']} · пришедших посреди хода {seen['посреди-хода']}")
    if skipped:
        # ⛔ СУЖЕНИЕ ГОВОРИТСЯ ВСЛУХ. Молчаливое сужение охвата неотличимо от честного
        # «слова не было» — тот самый класс, ради которого весь инструмент и написан.
        print(f"       ⚠️ ПРОПУЩЕНО {skipped} файлов: время их правки старше {a.date}, "
              f"записи этой даты в них взяться неоткуда.")
        print(f"       Читать всё равно ВСЕ: добавь --all-files")
    if unread:
        print(f"       ⛔ НЕ ПРОЧИТАНО {len(unread)} файлов: чтение не вернулось за {a.read_timeout:g} с "
              "или читающий процесс упал — пути у итога")
    print("=" * 92)

    def print_unread() -> None:
        """Непрочитанные файлы — у итога, полными путями (owner-word.py берёт их отсюда)."""
        print(f"⛔ ИСКАЛ НЕ ВЕЗДЕ: не прочитано файлов {len(unread)} из {len(unread) + files_read} "
              f"(предел тишины чтения {a.read_timeout:g} с):")
        for uf, why in unread:
            print(f"   не прочитан: {uf.resolve().as_posix()} — {why}")
        print("   счёт и вывод выше — только по прочитанным файлам; непрочитанное могло нести то же слово")

    def print_source(src) -> None:
        """Строка «файл:» — СРАЗУ под строкой «чат:»: owner-word.py берёт из неё адрес слова.
        Полный путь и номер строки (с 1) записи разговора, где лежит найденная реплика."""
        if src and src[1]:
            print(f"   файл: {src[0]}:{src[1]}")

    for ts, project, file_name, text, hint in sorted(by_human):
        shown = text.strip() if a.verbose else text.strip()[:200]
        print()
        print(f"📝 НАБРАНО ЧЕЛОВЕКОМ · {ts}")
        print(f"   чат: {project} / {file_name[:8]}…")
        print_source(addr.get((ts, file_name, text)))
        print(f"   ⏱ час записи ТОЧЕН (до миллисекунды) — час, когда текст лёг в чат")
        print(f"   ✍ происхождение ЗАПИСАНО в самой записи: «человек» (поле origin).")
        print(f"      Кто именно из людей — запись не знает; в этих чатах человек один.")
        if hint:
            print(f"   ⚠️ по тексту похоже на машинный вызов (примета «{hint}»), но поле")
            print(f"      говорит «человек»: владелец мог вставить наказ руками. Верю полю.")
        for ln in shown.splitlines():
            print(f"   │ {ln}")

    def cut(s: str, n: int = 180) -> str:
        return s if a.verbose else s[:n]

    # ключ сортировки — без словаря ответа: два одинаковых начала иначе сравнили бы словари
    for ts, project, file_name, text, w in sorted(by_choice, key=lambda e: e[:4]):
        print()
        if w["own"]:
            # ✍ свой текст — слово человека, а не вариант из предложенных ролью (карточка #635)
            print(f"✍ НАЙДЕНО СВОИМ ТЕКСТОМ В ОКНЕ ВОПРОСОВ — набрано человеком · {ts}")
        elif w["special"] and not w["picked"]:
            print(f"⚪ НАЙДЕНО В ОКНЕ ВОПРОСОВ — вариант не выбран · {ts}")
        else:
            print(f"🔘 НАЙДЕНО ВЫБОРОМ (интерфейс вариантов) · {ts}")
        print(f"   чат: {project} / {file_name[:8]}…")
        print_source(addr.get((ts, file_name, text)))
        print(f"   ⚖️ час — ВЕРХНЯЯ ГРАНИЦА: это приход ответа в чат. Сколько владелец")
        print(f"      держал выбор открытым до нажатия, запись не знает и знать не может")
        i, n = w["of"]
        if w["question"] is not None:
            print(f"   ❓ спрашивали (вопрос {i} из {n}): {cut(w['question'])}")
        if w["picked"]:
            print(f"   ✅ ВЫБРАНО: {cut(' · '.join(w['picked']))}")
        if w["own"]:
            print(f"   ✍ СВОИМ ТЕКСТОМ (поле «другое»): {cut(w['own'])}")
            print(f"      это слово человека, набранное им самим, а не вариант из предложенных")
        if w["note"]:
            print(f"   📝 заметка к выбору, набрана человеком: {cut(w['note'])}")
        if w["special"]:
            print(f"   ⚪ особый ответ: {w['special']}")
        where = ("в ответе" if needle in w["answer_text"].lower() else
                 "ТОЛЬКО в тексте вопроса — его писала роль, это не слово владельца; ответ выше")
        print(f"   🔎 слово найдено: {where}")
        print(f"   📎 разобрано по: {w['source']}")

    if no_origin:
        print()
        print("·" * 92)
        print(f"⚪ ПРОИСХОЖДЕНИЕ НЕ ЗАПИСАНО — {len(no_origin)} шт. Это НЕ «машина»:")
        print("   поле появилось не у всех клиентов сразу (чаты 09–15.08 в другом проекте")
        print("   его не писали, а там владелец говорил сам), и его нет у наказов, которые")
        print("   роли пишут помощникам. Кто автор — из записи не узнать. Смотри текст.")
        # ⚰️ Здесь стояла строка «„подано механизмом (isMeta)“ — это может быть и повтор слова
        # владельца … замер @CORE 04.09, 2 из 6 таких — его». Снята 05.09: находка отозвана
        # автором (записка #4760), верное число — 0 из 6; подачи механизма теперь лежат в 🤖.
        for ts, project, file_name, text, note in sorted(no_origin):
            p = (text.strip().splitlines() or [""])[0][:104]
            print(f"   ─ {ts} · {project[:24]:24}" + (f" · {note}" if note else ""))
            print(f"     │ {p}")

    if machine:
        print()
        print("·" * 92)
        print(f"🤖 МАШИННОЕ — {len(machine)} шт. Судилось по ПРОИСХОЖДЕНИЮ (поле записи),")
        print("   примета текста лишь дополняет; причина названа у каждой строки.")
        for ts, project, file_name, text, reason in sorted(machine):
            p = (text.strip().splitlines() or [""])[0][:96]
            print(f"   ─ {ts} · {project[:24]:24} · {reason}")
            print(f"     │ {p}")

    if summaries:
        print()
        print(f"📎 сводок сжатия с этим словом: {summaries} — не показаны: это ПЕРЕСКАЗ разговора,")
        print("   а не слово; их час — час сжатия, а не речи. Слово ищи среди записей выше.")

    print()
    print("-" * 92)
    found = by_human or by_choice
    if found:
        # ⚖️ СЧЁТ И ПО ЧАТАМ, не только по строкам — заявка @TAXO: одна и та же речь лежит
        # и в записи разговора, и в её копии (продолжение чата, сжатие), и «найдено 4 раза»
        # читается как четыре независимых свидетельства там, где событие ОДНО.
        # ⛔ НО «ОДНО СОБЫТИЕ» — ЭТО ВЫВОД, А НЕ ОФОРМЛЕНИЕ, И ОН ТРЕБУЕТ ДОКАЗАТЕЛЬСТВА.
        #    До 13.11 строка ниже печаталась БЕЗ ВСЯКОГО УСЛОВИЯ — на любом числе строк и чатов.
        #    Чем оплачено: два РАЗНЫХ слова владельца, сказанных двум ролям с разницей 9 мин 16 с,
        #    названы одним событием (замер RCC 11.10, карточка #700); три разных ответа в двух
        #    чатах — то же (замер COORD 31.10, карточка #737). Роль, перемерив СВОЁ слово,
        #    взяла бы час ЧУЖОГО, и час подменился бы молча.
        #    РАЗЛИЧИТЕЛЬ — ЧАС ЗАПИСИ ВМЕСТЕ С ТЕКСТОМ: одна речь, скопированная при продолжении
        #    или сжатии чата, несёт тот же час до миллисекунды и тот же текст; разные ответы
        #    несут разные часы, даже когда владелец повторил формулу дословно.
        chats = len({(p, fname) for _, p, fname, _, _ in by_human + by_choice})
        events = {(ts, text) for ts, _, _, text, _ in by_human + by_choice}
        rows = len(by_human) + len(by_choice)
        print(f"ИТОГ: человеком {len(by_human)} · выбором {len(by_choice)}"
              + (f" · без признака {len(no_origin)}" if no_origin else "")
              + (f" · машинных {len(machine)}" if machine else ""))
        if len(events) == 1 and rows > 1:
            print(f"      строк {rows}, а СОБЫТИЕ ОДНО (час записи и текст совпадают во всех): "
                  f"это одна речь, разных файлов {chats} — чат продолжен или сжат")
        elif len(events) > 1:
            print(f"      строк {rows}, а РАЗНЫХ ОТВЕТОВ {len(events)}, разных чатов {chats}"
                  + (f" (копий одной речи {rows - len(events)})" if rows > len(events) else "")
                  + ": у каждого ответа СВОЙ час — одним событием их НЕ считать;"
                  + " бери час того ответа, который ищешь")
        own_n = sum(1 for e in by_choice if e[4]["own"])
        midturn_n = sum(1 for e in by_human if MIDTURN_TAG in e[3])
        if own_n or midturn_n:
            print(f"      из них: своим текстом в окне вопросов {own_n} · пришло посреди хода {midturn_n}")
        if by_choice and not by_human:
            print("⚡ ВАЖНО: слово найдено ТОЛЬКО в окне вопросов (выбором или своим текстом). Поиск")
            print("   по тексту реплик его НЕ находит — и роль, ищущая текстом, решила бы, что цитата")
            print("   выдумана. Ровно этот случай и завёл карточку #521.")
        if unread:
            # найдено — код 0, как прежде: находка в прочитанном файле настоящая. Непрочитанное
            # названо рядом, чтобы счёт «разных ответов» не читался полным (карточка #797)
            print_unread()
        return 0
    if unread:
        # ⛔ «НЕ НАЙДЕНО» ПРИ НЕПРОЧИТАННЫХ ФАЙЛАХ — НЕ ЧЕСТНОЕ (карточка #797, критерий ②): слово
        # могло лежать ровно в том файле, чтение которого не вернулось. Отдельный код, чтобы это
        # видел и вызывающий, а не только читатель: 1 и 3 здесь были бы ложью о полноте.
        print(f"⛔ ИСКАЛ НЕ ВЕЗДЕ — в прочитанных файлах ({files_read}) слова с происхождением «человек» "
              "и среди выборов нет,")
        print("   но часть файлов не прочитана: «не найдено» здесь НЕ ЧЕСТНОЕ, вывода о слове не делай.")
        if no_origin or machine:
            print(f"   совпадения в прочитанном: без признака {len(no_origin)} · машинных {len(machine)}"
                  " (напечатаны выше)")
        print(f"   прочитано РАЗДЕЛЬНО: реплик текстом {seen['текст']} · ответов в окне вопросов "
              f"{seen['выбор']} · пришедших посреди хода {seen['посреди-хода']}")
        print_unread()
        print("   👉 повтори поиск: зависание чтения перемежающееся (карточка #797)")
        return 4
    # ⛔ САМОЕ ВАЖНОЕ МЕСТО ЭТОГО ИНСТРУМЕНТА: чего пустой ответ НЕ значит.
    print("⚪ НЕ НАЙДЕНО среди реплик с записанным происхождением «человек» и среди выборов.")
    if no_origin:
        print(f"⚠️ НО совпадения ЕСТЬ: без признака {len(no_origin)} · машинных {len(machine)}")
        print("   (напечатаны выше). Слово владельца могло лечь в чат, чей клиент поле не")
        print("   писал, — тогда оно среди «без признака». Прочти их, прежде чем судить.")
        # ⚡ ОТДЕЛЬНЫЙ КОД — тот же урок, что «отказ мерить» (2): «не нашли ничего» и
        # «нашли, но происхождение не «человек»» требуют РАЗНОГО следующего шага, а
        # вызывающий видит число. Коды: 0 нашли · 1 ничего · 2 отказ · 3 только спорное.
        return 3
    if machine:
        # 05.09: совпадения ТОЛЬКО машинные — это не «спорное» (3), а «слова владельца нет» (1)
        # с оговоркой: до 05.09 подачи механизма лежали в ⚪ и тянули за собой код 3 и совет
        # «прочти, прежде чем судить» — совет о записях, чей автор известен. Теперь автор назван
        # у каждой строки, а код говорит то же, что и текст.
        print(f"⚠️ НО совпадения ЕСТЬ — все МАШИННЫЕ ({len(machine)}, напечатаны выше): слово в чат")
        print("   ПРИХОДИЛО, но не от владельца (подачи механизма, удары будильника, повторы команд).")
        print("   Слово владельца, если оно было, лежит там, где стоит поле «человек»; здесь его нет.")
    print(f"⚖️ ЭТО НЕ ДОКАЗАТЕЛЬСТВО, ЧТО СЛОВА НЕ БЫЛО. Просмотрено файлов: {files_read}.")
    print(f"   Просмотрено РАЗДЕЛЬНО: реплик текстом {seen['текст']} · ответов в окне вопросов "
          f"{seen['выбор']} · пришедших посреди хода {seen['посреди-хода']} — ноль в одном счёте")
    print("   не значит ноль в другом.")
    if skipped:
        # 🔑 САМОЕ ДОРОГОЕ МЕСТО СУЖЕНИЯ — именно здесь, а не в строке охвата: роль,
        # получившая «не найдено», делает из него ВЫВОД. Число пропущенных обязано
        # стоять рядом с выводом, а не только в шапке, которую уже пролистали.
        print(f"   ⚠️ И ЕЩЁ {skipped} файлов НЕ ЧИТАНЫ ВОВСЕ: их время правки старше "
              f"{a.date}. Если запись могла приехать из копии со старым временем —")
        print(f"      перепроверь с --all-files, прежде чем делать вывод.")
    print("   Записи могли быть удалены, усечены при сжатии разговора, лежать в другом")
    print("   каталоге проектов или относиться к сеансу, чей файл не сохранён.")
    print("   👉 прежде чем звать цитату выдуманной: попробуй другой кусок фразы")
    print("      (владелец пишет короче, чем мы его пересказываем), сними --date,")
    print("      проверь --root. И спроси владельца, а не объявляй за него.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
