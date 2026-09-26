#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""rules-from-pack.py — сверка правил контура с правилами пакета GORDI (карточка #608).

ЗАЧЕМ. Контур уже живёт своим сводом правил (таблица `rules`), а пакет GORDI ведёт свой —
и оба меняются независимо. Этот инструмент помогает роли узнать, что в пакете появилось
новое или изменённое, сравнить со своим текстом, выбрать ход и подготовить предложение
в пакет («обновить для всех»). БАЗУ ПРАВИЛ ПАКЕТА (`<пакет>/rules/pack-rules.db`) строит
ДРУГОЙ инструмент — здесь она только ЧИТАЕТСЯ, по контракту (см. ниже).

ПЕРЕЕЗД (карточка #608, шаг 3): инструмент родился в vnext-tools и оттуда переехал сюда,
в инструменты контура (.mezosync/scripts) — чтобы update-tools.py привозил его соседним
контурам вместе с остальными инструментами, а сборка нового контура (init-group.py) могла
позвать его сразу после посева стартовых правил. Приёмка (bite-rules-from-pack.py) осталась
в vnext-tools и находит эту копию через mezo_target.py — тем же приёмом, каким приёмки
находят у себя update-tools.py и другие инструменты контура.

КОНТРАКТ БАЗЫ ПРАВИЛ ПАКЕТА (файл `<пакет>/rules/pack-rules.db`, пишет чужой инструмент):
    pack_rules(rule_set, rule_key, body, locked_by, text_sha,
               pack_updated_at, pack_commit, removed_at)        PRIMARY KEY (rule_set, rule_key)
    pack_rules_history(rule_set, rule_key, text_sha, body, locked_by,
                        first_commit, first_seen_at, replaced_at)
                                                     PRIMARY KEY (rule_set, rule_key, text_sha)
    pack_rules_meta(key, value)   -- schema_version=1, built_at, head_commit, source_sha

ТРИ ТЕКСТА, А НЕ ДВА. Сравнить «ваш текст» с «текстом пакета» напрямую нельзя: при
расхождении не видно, кто менял — контур, пакет или оба сразу. Третья точка — ОПОРА:
версия пакета, от которой контур когда-то пошёл. Она хранится отпечатком текста (не
самим текстом) в meta контура, ключ `pack_rules_base`, JSON {"<набор>/<ключ>": "<sha>"}.
Отказы от текущей версии пакета — ключ `pack_rules_skipped`, тот же вид.
Если опоры нет, а ваш текст дословно совпадает с какой-то СТАРОЙ версией пакета — опора
находится по истории пакета (`pack_rules_history`) и печатается отдельной строкой.

ОТПЕЧАТОК ТЕКСТА — ОДИН НА ОБА ИНСТРУМЕНТА (контракт с bite-rules-from-pack.py и со
строителем базы пакета): sha256 текста, приведённого к \n и без хвостовых пробелов,
первые 16 знаков — см. `text_sha()`. Меняя формулу здесь, поменяй её и там.

СОСТОЯНИЯ (О — опора, В — ваш текст, П — текст пакета сейчас):
    same          В = П                              ход: —
    pack-changed  В = О ≠ П (пакет ушёл вперёд)       ход: взять
    local-changed В ≠ О = П (уточнили у себя)         ход: предложить в пакет
    both-changed  В ≠ О ≠ П (менялись оба)            ход: свести, затем предложить
    no-base       В ≠ П, опора неизвестна             ход: сравнить, решает роль
    new           ключа нет у контура (пакет активен) ход: взять или отказаться
    removed       снято В ПАКЕТЕ, у контура есть      ход: снять у себя либо остаться (--skip)
                  (карточка #614: было "—" — пустой совет; --skip теперь принимает и эту строку)
    retired-here  снято У ВАС (status≠active), пакет держит, при ЛЮБОМ соотношении
                  текстов — в «new» не попадает никогда   ход: оставить снятым или
                  предложить снять в пакете (--propose)
    skipped       отпечаток пакета уже отклонён       ход: —
    (только у вас — пакет ключа не знает вовсе — в списке НЕ печатается, только в итоге)

ВОЗВРАТ PROTO (карточка #608, повторная приёмка, 2026-09-14): «--state new» на живом
контуре показывал правила, которые контур САМ снял (status≠'active' в своей таблице
rules) — инструмент судил их по ТЕКСТУ пакета, не спросив статус у контура, и подталкивал
вернуть осознанно отключённое правило. retired-here читает статус контура НАПЕРЁД любого
сравнения текстов — эта проверка старше и «new», и «removed».

ГРАНИЦА, НАЗЫВАЕМАЯ ВСЛУХ: инструмент сравнивает ТЕКСТЫ дословно и не судит смысл. Опора
по истории находится, только если ваш текст СЕГОДНЯ совпадает дословно с какой-то версией
пакета из прошлого, — иначе опоры нет, и решение остаётся за ролью.

ЗАПУСК (примеры; «<инструменты контура>» — .mezosync/scripts РЯДОМ С ЖИВОЙ БАЗОЙ ТВОЕГО
контура, путь у каждого контура свой — сам инструмент печатает АБСОЛЮТНЫЙ, см. --help):
    python <инструменты контура>/rules-from-pack.py
    python <инструменты контура>/rules-from-pack.py --state pack-changed
    python <инструменты контура>/rules-from-pack.py --show acceptance-e2e
    python <инструменты контура>/rules-from-pack.py --adopt acceptance-e2e --word \
        "владелец, чат PROTO 2026-09-14 03:31:16 UTC" --apply
    python <инструменты контура>/rules-from-pack.py --merge acceptance-e2e \
        --file merged.txt --word "координатор, записка #608" --apply
    python <инструменты контура>/rules-from-pack.py --skip acceptance-e2e --word "..." --apply
    python <инструменты контура>/rules-from-pack.py --propose acceptance-e2e \
        --why "пакет требует числа в замере, у нас голословно" --out proposal.md
    python <инструменты контура>/rules-from-pack.py --record-base --apply --actor COORD
    python <инструменты контура>/rules-from-pack.py --annexes --apply --actor COORD
    python <инструменты контура>/rules-from-pack.py --summary

ЗАПИСЬ ПРАВИЛА — ТОЛЬКО ЧЕРЕЗ set-rule.py (подпроцессом, тем же --db, своё основание и
--apply); этот инструмент прямых UPDATE/INSERT в `rules` не делает НИКОГДА. Прямая запись
здесь — только в meta контура (`pack_rules_base` / `pack_rules_skipped`), и то лишь после
успешной записи через set-rule.py (--skip и --record-base в `rules` не пишут вовсе, только
в meta).

--word «дословно: кто разрешил · когда · где» ОБЯЗАТЕЛЕН при ЛЮБОЙ настоящей записи
(--apply у --adopt/--merge/--skip): решение взять/свести/отказаться от чужого текста —
решение владельца или координатора контура, а не самого инструмента. Инструмент НЕ МОЖЕТ
проверить, что слово подлинное, — и говорит об этом прямо, а не притворяется, что проверил.
Если правило залочено владельцем (locked_by='owner' — у контура ИЛИ у пакета), это
называется отдельной строкой: --word здесь обязан быть словом ИМЕННО владельца, а
подлинность инструмент по-прежнему проверить не может. --record-base --word НЕ спрашивает
(объяснение — в шапке над `record_base`): совпавший текст ничьего решения не меняет.

--actor <имя роли> ОБЯЗАТЕЛЕН вместе с --apply у --adopt/--merge/--record-base/--annexes —
пишущий в контуре всегда называет СЕБЯ (как `backlog.py --actor`, `lease.py --role`), а не
имя инструмента. Без --apply флаг не нужен. Пустой или отсутствующий --actor при --apply —
отказ ДО любого соединения с базой, ничего не тронуто.

БЕЗ --apply НИЧЕГО НЕ ЗАПИСЫВАЕТСЯ — только показ того, что было бы сделано (включая
команду set-rule.py, которая была бы вызвана).

--summary — ОДНА строка итога без построчного списка (для чужого вызова, например
инструмента обновления контура): код выхода 0 всегда, КРОМЕ отказа поиска баз (нет базы
пакета / нет базы контура) — там код 2 и причина в тексте, не молчание.

⚖️ ЕСЛИ КЛЮЧ ЕСТЬ У ПАКЕТА В НЕСКОЛЬКИХ НАБОРАХ: список и --show показывают ВСЕ; для
--adopt/--merge/--skip/--propose (им нужен ровно ОДИН текст) — если тексты в наборах
совпадают, набор не важен; если разные — назови --rule-set явно (расширение сверх
буквы контракта, понадобившееся для однозначной записи; см. отчёт).

ПРИЛОЖЕНИЯ ПРАВИЛ (карточка #652 этап 2, задача #651). У части ключей пакета текст
правила сокращён, а разбор случаев вынесен в `<пакет>/rules/annex/<ключ>.md` — норма
кончается строкой «…— приложение: set-rule.py --key X --annex». --adopt и --merge
кладут приложение ключа В КОНТУР тем же ходом, что и текст правила (--apply) или говорят,
куда положили бы (без --apply) — местом, что найдёт --annex (mezo_paths.annex_path,
общая функция с set-rule.py). Ключам, чей текст УЖЕ совпадает с пакетом (--adopt тут
взять нечего), — отдельный ход --annexes. Чужое ДРУГОЕ содержимое приложения молча не
переписывается НИКОГДА — только по явному --annex-force. --show печатает одну строку:
есть ли у ключа приложение в пакете вообще (доставлено оно уже в контур или нет — ответ
на этот вопрос печатает --annex у set-rule.py).

СРОК ПРАВИЛА (карточка #650). Вид и условие срока (expiry_kind/expiry_cond) пакет несёт в
строке правила своего посева (`<пакет>/rules/universal.sql`, `rules/domain-specific/*.sql`);
база правил пакета срока не хранит. --adopt берёт срок оттуда же, откуда его берёт сборка
нового контура: исполняет файл посева в памяти и берёт срок, только если текст правила в
посеве равен тексту из базы правил пакета (по отпечатку). Срок пакета ложится, когда у
контура срок пуст или стоит заготовка сборки («до пересмотра владельцем нового контура» —
её ставила сборка, а не решение контура). Свой срок контура --adopt не заменяет, а называет
рядом со сроком пакета; заменить — тот же вызов с --expiry-from-pack. Срока в посеве нет —
как прежде: новому ключу «бессрочно», у старого срок не трогаем. Список (режим по
умолчанию) называет ключи «same», у которых срок пакета можно взять (у вас пусто или
заготовка) или у вас свой, с готовой командой; --summary к своей строке добавляет вторую —
только когда такие ключи есть (иначе вывод прежний). --adopt по ключу «same» меняет срок и
основание — текст и версия правила остаются те же.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны
import mezo_stand  # noqa: E402 — временный клон источника (карточка #614) убирается штатно:
                    # решает finish() внизу файла, как у update-tools.py

HERE = Path(__file__).resolve().parent
# ⚖️ НЕ через mezo_paths.live_scripts(): та функция слушает MEZO_CONTAINER вызывающего
# ПЕРВЫМ делом, а нам нужно НАДЁЖНО найти РЕАЛЬНЫЙ set-rule.py рядом со своим контуром
# независимо от чужого окружения — та же забота, что решает subprocess_env() ниже.
# С переезда в .mezosync/scripts (карточка #608, шаг 3) set-rule.py — прямой сосед этого
# файла, поэтому путь больше не поднимается на уровень выше.
SET_RULE_PY = HERE / "set-rule.py"
# ВОЗВРАТ PROTO (карточка #608, повторная приёмка): подсказка --propose печатала путь к
# gordi-issue.py ВПЕЧАТАННЫМ («<КОНТУР>/...») — верно только у автора, у любого
# другого контура (песочница, клон в другом месте) подсказка вела бы в пустоту. Путь —
# от СВОЕГО расположения, как SET_RULE_PY выше.
GORDI_ISSUE_PY = HERE / "gordi-issue.py"
# КАРТОЧКА #614 ①: update-tools.py — рядом, тот же соглашение путей, что у SET_RULE_PY/
# GORDI_ISSUE_PY выше (от СВОЕГО расположения, не впечатано).
UPDATE_TOOLS_PY = HERE / "update-tools.py"

_update_tools_module = None  # кэш — грузим по требованию, не на каждый вызов


def _load_update_tools():
    """update-tools.py — переиспользуем его fetch() (временный клон источника: только
    чтение, убирается штатно через mezo_stand), а не пишем второй способ (карточка #614 ①,
    task-g3-614.md п.1). Имя файла с дефисом — обычный `import` его не берёт, грузим по пути,
    как это уже делают приёмки (см. bite-rules-from-pack.py: load_rfp)."""
    global _update_tools_module
    if _update_tools_module is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("update_tools_for_rfp", str(UPDATE_TOOLS_PY))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _update_tools_module = mod
    return _update_tools_module


STATE_NAMES = ("new", "pack-changed", "local-changed", "both-changed",
               "no-base", "removed", "retired-here", "skipped", "same")
MOVE_BY_STATE = {
    "new": "взять или отказаться",
    "pack-changed": "взять",
    "local-changed": "предложить в пакет",
    "both-changed": "свести, затем предложить",
    "no-base": "сравнить, решает роль",
    # КАРТОЧКА #614 ②: было "—" (пустой совет). Два пути, а не один: снять у себя (готовая
    # команда — см. render_retire_preview(), печатается в списке под строкой) или остаться
    # и записать отказ (--skip, теперь принимает и снятый пакетом ключ). По умолчанию —
    # ничего не делаем НИ С ОДНОЙ стороны, обе команды требуют --apply отдельно.
    "removed": "пакет его больше не несёт — снять у себя (set-rule.py, см. готовую команду "
              "ниже) или остаться и записать отказ (--skip); по умолчанию не трогаем",
    "retired-here": "у вас снято, пакет его держит — оставить снятым или предложить снять "
                    "в пакете (--propose)",
    "skipped": "—",
    "same": "—",
}
BOUNDARY_LINE = (
    "⚖️ Граница: инструмент сравнивает ТЕКСТЫ дословно, смысл он не судит. Опора по истории "
    "пакета находится, только если ваш текст СЕГОДНЯ дословно совпадает с какой-то прошлой "
    "версией пакета — иначе опоры нет, и решение остаётся за ролью."
)
# приметы путей одной машины — тот же род, что у gordi-issue.py, для обезличивания предложений
MACHINE_PATH = re.compile(r"[A-Za-z]:[\\/](?:guts|github|Users)[\\/][^\s\"'()]*", re.I)


def text_sha(body: str) -> str:
    """Отпечаток текста правила. ОДНА формула на весь контракт (см. шапку файла)."""
    normalized = (body or "").replace("\r\n", "\n").rstrip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ── ПУТИ И БАЗЫ ──────────────────────────────────────────────────────────────────────

def find_pack_source(arg_source, conn) -> Path:
    """Папка с клоном пакета: --source, meta.template_checkout (готовая папка на диске) —
    либо, когда контур знает только meta.template_source (карточка #614): АДРЕС УДАЛЁНКИ,
    как его пишет init-group.py (`git remote get-url origin`, а НЕ папка клона) — временный
    клон, ТЕМ ЖЕ приёмом, что update-tools.py берёт свежие инструменты (см. update-tools.py:
    fetch()) — только чтение, клон убирается штатно через mezo_stand (см. finish() внизу
    этого файла), код клонирования здесь НЕ повторён — вызван оттуда (task-g3-614.md п.1:
    «переиспользуй его код, не пиши второй способ»).

    ⚖️ fetch() сам решает, клонировать или нет: если значение template_source — уже папка
    НА ДИСКЕ (is_dir()), она берётся НАПРЯМУЮ, без сети; иначе — `git clone --depth 1`
    во временный каталог. Один вызов покрывает и адрес удалёнки, и путь одинаково —
    решение уже принято внутри fetch(), повторять его здесь не нужно.

    ГРАНИЦА (карточка #614 п.1, обязана остаться): «источника нет» (ни --source, ни
    template_checkout, ни template_source) — отказ ЗДЕСЬ, ниже. «Источник не читается»
    (значение есть, но клонировать/открыть не вышло — сеть недоступна, путь не git,
    внутри нет rules/pack-rules.db) — отказ ИЗ fetch() («⛔ НЕ ЗАБРАЛОСЬ из ...») либо
    позже из open_pack_db() («⛔ в пакете нет базы правил») — оба уже различают причину
    словами, второй способ здесь заводить не нужно.
    """
    if arg_source:
        p = Path(arg_source)
        if not p.is_dir():
            sys.exit(f"⛔ пакет не найден: папки «{p}» не существует. Укажи верный --source.")
        return p
    row = conn.execute("SELECT value FROM meta WHERE key='template_checkout'").fetchone()
    if row and row[0] and Path(row[0]).is_dir():
        return Path(row[0])
    src_row = conn.execute("SELECT value FROM meta WHERE key='template_source'").fetchone()
    source = ((src_row[0] if src_row else "") or "").strip()
    if source:
        # meta.template_source ЕСТЬ — берём тем же ходом, что update-tools.py (fetch()
        # сама решает: локальная папка — напрямую, иначе — временный клон).
        tools = _load_update_tools()
        try:
            tmp, _rev, _temporary = tools.fetch(source)
        except SystemExit as e:
            # ВОЗВРАТ COORD (карточка #614, ветка «а», 2026-09-14 17:58 UTC): адрес в meta
            # ЕСТЬ, но источник не читается (нет сети, форма ssh, опечатка) — fetch() уже
            # отказал СЛОВАМИ update-tools.py («⛔ НЕ ЗАБРАЛОСЬ ... источник недоступен»),
            # но не называет, что делать ДАЛЬШЕ роли ИМЕННО ЭТОГО инструмента. Готовая
            # команда — ПОСЛЕДНЕЙ строкой: у чужого вызывающего (update-tools.py:
            # print_pack_rules_summary) в вывод попадает только ПОСЛЕДНЯЯ строка причины
            # (reason_lines[-1]) — она обязана нести совет, а не только диагноз fetch().
            reason = e.code if isinstance(e.code, str) else str(e.code)
            sys.exit(
                f"{reason}\n"
                "   rules-from-pack.py: источник в meta.template_source не читается — "
                "укажи явно: --source <папка с клоном пакета GORDI>"
            )
        return tmp
    meta_note = f" (в meta записано «{row[0]}», но это не папка)" if row and row[0] else ""
    sys.exit(
        "⛔ источник пакета GORDI неизвестен: --source не задан, meta.template_checkout"
        f" контура{meta_note} не годится, а meta.template_source пусто.\n"
        "   Укажи явно: --source <папка с клоном пакета GORDI>"
    )


def open_pack_db(source: Path) -> sqlite3.Connection:
    db_path = source / "rules" / "pack-rules.db"
    if not db_path.exists():
        sys.exit(
            f"⛔ в пакете нет базы правил: пакет старее этой возможности или собран без "
            f"неё (ждал {db_path})."
        )
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def subprocess_env() -> dict:
    """Среда для запуска set-rule.py БЕЗ живого MEZO_CONTAINER вызывающего («руками» —
    записка #5096 про инструменты стенда, применена и здесь: явный --db не должен
    подменяться чужим контейнером из окружения)."""
    env = dict(os.environ)
    env.pop("MEZO_CONTAINER", None)
    return env


# ── ЧТЕНИЕ ДАННЫХ ────────────────────────────────────────────────────────────────────

def load_circuit_rules(conn) -> dict:
    """rule_key -> тело, ТОЛЬКО действующие правила контура (status='active')."""
    return {k: b for k, b in conn.execute(
        "SELECT rule_key, body FROM rules WHERE status='active'")}


def load_circuit_retired_keys(conn) -> set:
    """Ключи, у которых в контуре ЕСТЬ строка, но НИ ОДНОЙ действующей (status≠'active') —
    контур сам снял правило. Отдельно от load_circuit_rules(): нужно различить «ключа
    у контура нет вовсе» (состояние «new») от «есть, контур сам его отключил» (состояние
    «retired-here», карточка #608, возврат PROTO). Если у ключа ОДНОВРЕМЕННО есть
    действующая строка — сюда он не попадает: правило сейчас действует, независимо от
    того, снималось ли когда-то раньше."""
    active = {k for (k,) in conn.execute("SELECT rule_key FROM rules WHERE status='active'")}
    any_row = {k for (k,) in conn.execute("SELECT DISTINCT rule_key FROM rules")}
    return any_row - active


def circuit_is_retired(conn, key) -> bool:
    """То же самое, что load_circuit_retired_keys(), но для ОДНОГО ключа (используется там,
    где загружать весь набор ключей контура не нужно — например, у --adopt)."""
    active = conn.execute(
        "SELECT 1 FROM rules WHERE rule_key=? AND status='active' LIMIT 1", (key,)).fetchone()
    if active:
        return False
    any_row = conn.execute("SELECT 1 FROM rules WHERE rule_key=? LIMIT 1", (key,)).fetchone()
    return any_row is not None


def circuit_locked_by(conn, key):
    row = conn.execute(
        "SELECT locked_by FROM rules WHERE rule_key=? AND status='active'", (key,)).fetchone()
    return row[0] if row else None


def needs_expiry_kind(conn, key) -> bool:
    """True — set-rule.py потребует --expiry-kind явно и откажет без него: ключа у контура
    ЕЩЁ НЕТ, либо он есть, но старше этого требования (поле «условие отмены» пусто у
    самого правила — так уже бывает у живых правил, см. --list в set-rule.py, «основание
    не заполнено»). Если поле УЖЕ стоит — не трогаем его: --adopt/--merge меняют ТЕКСТ,
    а не молча стирают чей-то заранее выставленный срок годности."""
    row = conn.execute(
        "SELECT expiry_kind FROM rules WHERE rule_key=? AND status='active'", (key,)).fetchone()
    return row is None or not (row[0] or "").strip()


# ── СРОК ПРАВИЛА ИЗ ПОСЕВА ПАКЕТА (карточка #650) ──────────────────────────────────
# ПОВОД (замер 25.09): у контура, собранного из пакета, условный срок правил не совпадал со
# сводом контура-донора ни у одного правила — посев вставлял правила без срока, и заготовка
# сборки ставила всем «до пересмотра владельцем нового контура». --adopt срока не переносил
# вовсе: новому ключу — «бессрочно», у старого оставалась та же заготовка.
# ⚖ ОТКУДА СРОК: из посева пакета — того же файла, который исполняет сборка нового контура.
# База правил пакета срока не хранит, и второй копии здесь не заводим. Файл исполняется в
# памяти, как его исполняет сборка, но у строк правил основание непустое (значение по
# умолчанию в разборе) — блок «происхождение при посеве» их не трогает, и виден ровно
# ОБЪЯВЛЕННЫЙ срок. Заготовку сборки узнаём пробной строкой с пустым основанием: блок
# заполняет её так же, как заполнил бы правило нового контура.
SEED_EXPIRY_KNOWN = ("until_event", "до пересмотра владельцем нового контура")
EXPIRY_NEEDS_COND = ("until_date", "until_event", "while_measured")
SEED_PROBE_KEY = "zz-rules-from-pack-seed-probe"
# set-rule.py не стирает поле пустым значением (пустое наследует прежнее), а строку из одного
# пробела обрезает до пустоты и пишет NULL. Так вид «бессрочно» без условия ложится поверх
# заготовки сборки, не оставляя её условия. Держится приёмкой bite-pack-rule-expiry.py (②а).
CLEAR_COND = " "
PACK_PARSE_DDL = """CREATE TABLE rules (id INTEGER PRIMARY KEY AUTOINCREMENT,
 rule_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL, locked_by TEXT NOT NULL DEFAULT 'coord',
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT,
 basis TEXT DEFAULT 'объявлено строкой посева', authorized TEXT, source_ref TEXT,
 expiry_kind TEXT, expiry_cond TEXT, status TEXT NOT NULL DEFAULT 'active', revoked_at TEXT,
 revoked_by TEXT, revoked_reason TEXT, superseded_by INTEGER, skill_delivery TEXT)"""
_pack_expiry_cache: dict = {}


def pack_sql_path(source: Path, rule_set: str) -> Path:
    """Файл посева набора пакета: universal — rules/universal.sql, домен — rules/domain-specific/."""
    return (source / "rules" / "universal.sql" if rule_set == "universal"
            else source / "rules" / "domain-specific" / f"{rule_set}.sql")


def _field(value):
    value = (value or "").strip()
    return value or None


def load_pack_expiry(source: Path, rule_set: str):
    """→ (объявленный срок {ключ: (вид, условие, отпечаток текста)}, заготовка сборки
    (вид, условие) либо None, причина — почему срок не прочитан, либо None)."""
    cache_key = (str(source), rule_set)
    if cache_key in _pack_expiry_cache:
        return _pack_expiry_cache[cache_key]
    path = pack_sql_path(source, rule_set)
    if not path.is_file():
        result = ({}, None, f"в пакете нет файла посева {path.name}")
    else:
        mem = sqlite3.connect(":memory:")
        try:
            mem.execute(PACK_PARSE_DDL)
            mem.execute("INSERT INTO rules (rule_key, body, basis) VALUES (?, '', NULL)",
                        (SEED_PROBE_KEY,))
            mem.executescript(path.read_text(encoding="utf-8"))
            rows = mem.execute(
                "SELECT rule_key, body, expiry_kind, expiry_cond FROM rules").fetchall()
        except sqlite3.Error as e:
            result = ({}, None, f"посев {path.name} не исполнился в памяти: {e}")
        else:
            declared, seed = {}, None
            for key, body, kind, cond in rows:
                kind, cond = _field(kind), _field(cond)
                if key == SEED_PROBE_KEY:
                    seed = (kind, cond) if kind else None
                elif kind:
                    declared[key] = (kind, cond, text_sha(body))
            result = (declared, seed, None)
        finally:
            mem.close()
    _pack_expiry_cache[cache_key] = result
    return result


def pack_expiry_for(source, row):
    """Срок, который пакет несёт для ряда базы правил пакета: → ((вид, условие) | None,
    заготовка сборки | None, причина | None). source=None — вызов без пакета под рукой:
    срока нет и причины нет (прежнее поведение)."""
    if source is None:
        return None, None, None
    declared, seed, reason = load_pack_expiry(Path(source), row["rule_set"])
    if reason:
        return None, seed, reason
    got = declared.get(row["rule_key"])
    if got is None:
        return None, seed, "в посеве пакета срок этого правила не объявлен"
    kind, cond, sha = got
    if sha != row["text_sha"]:
        return None, seed, ("текст правила в посеве не равен тексту из базы правил пакета — "
                            "срок относится к другому тексту")
    if kind in EXPIRY_NEEDS_COND and not cond:
        return None, seed, f"в посеве у вида {kind} нет условия"
    return (kind, cond), seed, None


def contour_expiry(conn, key):
    """(вид, условие) действующего правила контура; None — действующего правила нет."""
    row = conn.execute("SELECT expiry_kind, expiry_cond FROM rules "
                       "WHERE rule_key=? AND status='active'", (key,)).fetchone()
    return None if row is None else (_field(row[0]), _field(row[1]))


def expiry_is_seed(expiry, seed) -> bool:
    """Срок контура пуст или это заготовка сборки из пакета — не решение самого контура."""
    if expiry is None or not expiry[0]:
        return True
    return expiry == SEED_EXPIRY_KNOWN or (seed is not None and expiry == seed)


def show_expiry(expiry) -> str:
    if expiry is None or not expiry[0]:
        return "пусто"
    return expiry[0] + (f" — «{expiry[1]}»" if expiry[1] else "")


def plan_adopt_expiry(conn, key, row, source, take_pack: bool = False):
    """Срок при --adopt: → (аргументы срока для set-rule.py, строка для роли либо None).
    take_pack (--expiry-from-pack) — срок пакета ложится и поверх СВОЕГО срока контура."""
    pack, seed, reason = pack_expiry_for(source, row)
    mine = contour_expiry(conn, key)
    if pack is not None:
        if mine == pack:
            return [], f"срок: {show_expiry(pack)} — уже как в пакете"
        take = ["--expiry-kind", pack[0], "--expiry-cond", pack[1] or CLEAR_COND]
        if expiry_is_seed(mine, seed):
            return take, f"срок: {show_expiry(pack)} — из пакета (у вас был: {show_expiry(mine)})"
        if take_pack:
            return take, (f"срок: {show_expiry(pack)} — из пакета по --expiry-from-pack "
                          f"(у вас был свой: {show_expiry(mine)})")
        return [], (f"📌 срок: у вас свой — {show_expiry(mine)}; пакет несёт {show_expiry(pack)}. "
                    f"--adopt ваш срок не заменяет; взять срок пакета — тот же вызов с "
                    f"--expiry-from-pack")
    why = f" ({reason})" if reason else ""
    extra = " · --expiry-from-pack: брать нечего" if take_pack else ""
    if needs_expiry_kind(conn, key):
        return ["--expiry-kind", "forever"], (
            f"срок: forever — в пакете не объявлен{why}, у вас пусто{extra}"
            if source is not None else None)
    return [], (f"срок: ваш, не трогаю — {show_expiry(mine)}; в пакете не объявлен{why}{extra}"
                if source is not None else None)


def render_expiry_args(expiry_args) -> str:
    """Аргументы срока для показа в команде set-rule.py (условие — строкой «срок» выше)."""
    out = ""
    i = 0
    while i < len(expiry_args):
        flag, value = expiry_args[i], expiry_args[i + 1]
        if flag == "--expiry-cond":
            value = '" "' if value == CLEAR_COND else "«условие пакета — строкой выше»"
        out += f" {flag} {value}"
        i += 2
    return out


def expiry_differences(conn, rows: list, source):
    """Ключи «same» (текст как в пакете), у которых пакет несёт срок, а у вас другой:
    → (можно взять — у вас пусто или заготовка сборки; у вас свой) — оба [(набор, ключ)]."""
    take, own = [], []
    if source is None:
        return take, own
    for r in rows:
        if r["state"] != "same":
            continue
        pack, seed, _reason = pack_expiry_for(source, r)
        if pack is None:
            continue
        mine = contour_expiry(conn, r["rule_key"])
        if mine == pack:
            continue
        (take if expiry_is_seed(mine, seed) else own).append((r["rule_set"], r["rule_key"]))
    return sorted(take), sorted(own)


def _adopt_commands(pairs: list, db_path, extra: str) -> None:
    for rule_set in sorted({s for s, _k in pairs}):
        keys = " ".join(k for s, k in pairs if s == rule_set)
        print(f"   python {Path(__file__).resolve()} --db {db_path} --adopt {keys} "
              f"--rule-set {rule_set}{extra} --word \"<дословно: кто разрешил·когда·где>\" "
              f"--actor <роль> --apply")


def print_expiry_differences(take: list, own: list, db_path) -> None:
    if take:
        print(f"\n⏳ срок пакета можно взять у {len(take)} правил (текст как в пакете, у вас срок "
              f"пуст или заготовка сборки): " + " · ".join(k for _s, k in take))
        print("   взять (текст и версия правила останутся те же, сменятся срок и основание):")
        _adopt_commands(take, db_path, "")
    if own:
        print(f"\n📌 срок у вас свой у {len(own)} правил (пакет несёт другой; --adopt свой не "
              f"заменяет): " + " · ".join(k for _s, k in own))
        print("   сравнить: тот же список ключей в --adopt без --apply; взять срок пакета поверх своего:")
        _adopt_commands(own, db_path, " --expiry-from-pack")


PACK_COLS = ("rule_set", "rule_key", "body", "locked_by", "text_sha",
             "pack_updated_at", "pack_commit", "removed_at")


def load_pack_rows(pack_conn) -> list:
    rows = pack_conn.execute(f"SELECT {', '.join(PACK_COLS)} FROM pack_rules").fetchall()
    return [dict(zip(PACK_COLS, r)) for r in rows]


def make_history_has(pack_conn):
    def history_has(rule_set, rule_key, sha) -> bool:
        return pack_conn.execute(
            "SELECT 1 FROM pack_rules_history WHERE rule_set=? AND rule_key=? AND text_sha=? "
            "LIMIT 1", (rule_set, rule_key, sha)).fetchone() is not None
    return history_has


def load_meta_map(conn, key: str) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    if not row or not (row[0] or "").strip():
        return {}
    try:
        data = json.loads(row[0])
    except (ValueError, TypeError):
        sys.exit(f"⛔ meta.{key} не разбирается как JSON — испорчено чужой рукой; "
                 f"чинить руками, не отсюда")
    return data if isinstance(data, dict) else {}


def save_meta_map(conn, key: str, mapping: dict) -> None:
    payload = json.dumps(mapping, ensure_ascii=False, sort_keys=True)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, payload))


# ── СРАВНЕНИЕ ────────────────────────────────────────────────────────────────────────

def classify_diff(v_sha, p_sha, base_sha):
    """Состояние правила, у которого В (ваш текст) и П (текст пакета) УЖЕ разные."""
    if base_sha is None:
        return "no-base"
    if base_sha == v_sha and base_sha != p_sha:
        return "pack-changed"
    if base_sha == p_sha and base_sha != v_sha:
        return "local-changed"
    return "both-changed"


def resolve_base(rule_set, rule_key, v_sha, base_map, history_has):
    """Отпечаток опоры и откуда он взят: (sha|None, 'meta'|'history'|None)."""
    k = f"{rule_set}/{rule_key}"
    if k in base_map:
        return base_map[k], "meta"
    if history_has(rule_set, rule_key, v_sha):
        return v_sha, "history"
    return None, None


# ── НАБОРЫ ПАКЕТА, КОТОРЫЕ КОНТУР РЕАЛЬНО ВЗЯЛ (карточка #608, возврат PROTO) ──────────
# ПОВОД. Инструмент сравнивал контур со ВСЕМИ наборами пакета разом — и печатал шум на
# КАЖДОМ обновлении: чужой (не взятый контуром) набор считался «новым», а доменное
# описание ключа, перекрывающее universal, читалось как расхождение с universal-версией,
# у которой законно нет опоры. Живой пример (замер PROTO): свежий контур с доменом
# data-platform показывал «новых 3 · опоры нет 3» вместо сплошного нуля.

def load_meta_list(conn, key: str):
    """JSON-список из meta.<key>. None — ключа НЕТ ВООБЩЕ (не путать с пустым списком:
    пустой список — это записанное решение «наборов нет», а None — «не записано никогда»)."""
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    if row is None or row[0] is None:
        return None
    try:
        data = json.loads(row[0])
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, list) else None


def resolve_contour_rule_sets(conn, circuit_rules: dict, pack_rows: list) -> tuple:
    """Наборы пакета, которые контур РЕАЛЬНО загрузил, в порядке загрузки (последний в
    списке побеждает при повторении ключа — тем же порядком грузит их сама сборка:
    universal, затем домен поверх неё). Возвращает (наборы, взято_из_meta: bool).

    ИСТОЧНИК ①: meta.pack_rule_sets — пишет init-group.py при сборке (карточка #608).
    ИСТОЧНИК ② (контур собран РАНЬШЕ этой записи — meta пуста): ВЫВОД ПО НАЛИЧИЮ.
    universal берётся всегда; доменный набор считается взятым, если у контура есть ХОТЯ БЫ
    ОДИН его ключ, которого нет в universal, — общий ключ (в обоих наборах сразу) отличить
    так нельзя, поэтому он в вывод не идёт: он и не нужен, взятость набора решают ключи,
    которые есть ТОЛЬКО в нём.
    """
    all_sets = sorted({row["rule_set"] for row in pack_rows})
    recorded = load_meta_list(conn, "pack_rule_sets")
    if recorded is not None:
        return [s for s in recorded if isinstance(s, str)], True
    universal_keys = {row["rule_key"] for row in pack_rows
                      if row["rule_set"] == "universal" and not row["removed_at"]}
    taken = ["universal"] if "universal" in all_sets else []
    for rs in all_sets:
        if rs == "universal":
            continue
        rs_keys = {row["rule_key"] for row in pack_rows
                  if row["rule_set"] == rs and not row["removed_at"]}
        if (rs_keys - universal_keys) & set(circuit_rules):
            taken.append(rs)
    return taken, False


def rule_sets_note(contour_sets: list, via_meta: bool):
    """Строка про источник наборов — печатается, ТОЛЬКО когда они выведены по наличию
    (не записаны контуром): роль обязана знать, что это вывод, а не факт."""
    if via_meta:
        return None
    return ("наборы контура не записаны — определены по наличию правил: "
            + ", ".join(contour_sets))


def governing_rows(pack_rows: list, contour_sets: list) -> dict:
    """Один ряд пакета на КЛЮЧ — из ПОСЛЕДНЕГО (по порядку contour_sets) взятого набора,
    где этот ключ встречается. Наборы, которые контур не взял, в сравнение не входят
    ВООБЩЕ — ни как «новое», ни как расхождение; ключ, повторённый в нескольких взятых
    наборах, сверяется ПО ПОБЕДИВШЕМУ описанию (домен перекрывает universal — тем же
    порядком, каким контур их загрузил и каким они лежат в его живой таблице rules)."""
    taken = set(contour_sets)
    rows_by_set: dict = {}
    for row in pack_rows:
        if row["rule_set"] in taken:
            rows_by_set.setdefault(row["rule_set"], {})[row["rule_key"]] = row
    governing: dict = {}
    for rs in contour_sets:
        governing.update(rows_by_set.get(rs, {}))
    return governing


def build_rows(circuit_rules: dict, pack_rows: list, base_map: dict, skip_map: dict,
               history_has, contour_sets: list, retired_keys: set) -> tuple:
    """Строки списка (ОДНА на ключ — см. governing_rows) + отдельно ключи «только у вас».

    retired_keys (карточка #608, возврат PROTO) — ключи, снятые САМИМ КОНТУРОМ
    (load_circuit_retired_keys). Проверяются РАНЬШЕ, чем «new»: контур, отключивший правило
    сам, — не тот же случай, что «ключа никогда не было», при ЛЮБОМ соотношении текстов.
    Но ПОЗЖЕ, чем снятие в пакете: ключ, снятый с обеих сторон, в список не идёт вовсе."""
    governing = governing_rows(pack_rows, contour_sets)

    out = []
    for key, row in governing.items():
        v_body = circuit_rules.get(key)
        v_sha = text_sha(v_body) if v_body is not None else None
        rule_set = row["rule_set"]
        base_src = None
        if v_sha is None:
            # Снятие в пакете проверяется РАНЬШЕ, чем снятие у контура: правило, снятое
            # С ОБЕИХ сторон, — не «снято у вас» (--propose звал бы снять в пакете то, что
            # пакет уже снял). Живой случай 26.09: у Atlas 6 правил сняты, у пакета 5 из них
            # сняты ещё 18.08 — список показывал все шесть как «снято у вас».
            if row["removed_at"]:
                continue  # ни у контура, ни в пакете (сейчас) его нет — обсуждать нечего
            elif key in retired_keys:
                state = "retired-here"
            else:
                state = "new"
        elif row["removed_at"]:
            # КАРТОЧКА #614 ②: --skip годится и здесь («пакет его больше не несёт, а я
            # держу и дальше») — тот же отпечаток-ключ, что и у живого текста пакета
            # (skip_map хранит sha ПОСЛЕДНЕЙ версии пакета перед снятием); отпустится
            # само, если этот отпечаток когда-нибудь перестанет совпадать (симметрично
            # обычному «skipped» ниже).
            if skip_map.get(f"{rule_set}/{key}") == row["text_sha"]:
                state = "skipped"
            else:
                state = "removed"
        else:
            p_sha = row["text_sha"]
            if v_sha == p_sha:
                state = "same"
            elif skip_map.get(f"{rule_set}/{key}") == p_sha:
                state = "skipped"
            else:
                base_sha, base_src = resolve_base(rule_set, key, v_sha, base_map, history_has)
                state = classify_diff(v_sha, p_sha, base_sha)
        out.append({
            "rule_key": key, "rule_set": rule_set, "state": state,
            "move": MOVE_BY_STATE[state],
            "pack_updated_at": row["pack_updated_at"], "removed_at": row["removed_at"],
            "locked_by": row["locked_by"], "text_sha": row["text_sha"],
            "base_source": base_src,
            # КАРТОЧКА #614 ②: нужен для готовой команды «снять у себя» под строкой
            # «removed» в print_listing() — комментарий-основание set-rule.py.
            "pack_commit": row["pack_commit"],
        })
    only_yours = sorted(k for k in circuit_rules if k not in governing)
    return out, only_yours


def summarize(rows: list, only_yours: list) -> dict:
    counts = {s: 0 for s in STATE_NAMES}
    for r in rows:
        counts[r["state"]] += 1
    counts["only-yours"] = len(only_yours)
    return counts


# ── ПЕЧАТЬ ───────────────────────────────────────────────────────────────────────────

def print_diff(title: str, a_text: str, b_text: str) -> None:
    print(f"\n--- различие: {title} ---")
    diff = list(difflib.unified_diff(
        a_text.splitlines(), b_text.splitlines(), lineterm=""))
    print("\n".join(diff) if diff else "(текст совпадает дословно)")


def render_retire_preview(db_path, key: str, basis: str) -> str:
    """Готовая команда «снять у себя» для разряда «снято в пакете» (карточка #614 ②).

    ⚖️ НИКАКОГО НОВОГО СПОСОБА ЗАПИСИ: тем же set-rule.py, что и у --adopt/--merge —
    правило «запись правила ТОЛЬКО через set-rule.py» (шапка файла) не нарушено.
    Тело по-прежнему решает роль — не выдумываем его за неё, печатаем плейсхолдер,
    начинающий с УЖЕ ПРИНЯТОЙ в своде отметки отзыва «⛔ ОТОЗВАНО» (см. rule_status.py,
    TOMBSTONE) — не новый жаргон, а существующий признак, который уже умеет читать
    свод (текстом — всегда; полем status — там, где UPDATE того же set-rule.py его
    касается; на базах, где поле status уже есть, отдельно от этого хода решает
    COORD/владелец — set-rule.py сегодня поле status не выставляет ни при каком флаге,
    и здесь это не обещано сверх того, что инструмент делает на самом деле)."""
    return (f'python {SET_RULE_PY} --db {db_path} --key {key} '
            f'--body-file <файл: тело начни с «⛔ ОТОЗВАНО — …»> '
            f'--basis "{basis}" --authorized-by "<кто разрешил>" '
            f'--source-ref "<где сказано>" --actor "<твоя роль>" --apply')


def print_listing(rows: list, only_yours: list, state_filter, db_path=None) -> None:
    shown = [r for r in rows if state_filter is None or r["state"] == state_filter]
    shown.sort(key=lambda r: (r["rule_key"], r["rule_set"]))
    if not shown:
        print("(строк по этому отбору нет)")
    for r in shown:
        when = r["pack_updated_at"] or "—"
        if r["state"] == "removed" and r["removed_at"]:
            when = f"{when} (снято {r['removed_at']})"
        print(f"  {r['rule_key']:<35} {r['rule_set']:<16} {when:<24} "
              f"{r['state']:<14} {r['move']}")
        # КАРТОЧКА #614 ②: было — ничего не печаталось под строкой «removed» (пустой
        # совет в MOVE_BY_STATE). Два ПОКАЗАННЫХ пути, db_path=None (например, --summary
        # печатает список не отсюда) — тихо пропускаем готовую команду, а не падаем.
        if r["state"] == "removed" and db_path is not None:
            basis = f"снято в пакете, коммит {r.get('pack_commit') or '?'}"
            print(f"      снять у себя:  {render_retire_preview(db_path, r['rule_key'], basis)}")
            print(f"      либо остаться: python {Path(__file__).resolve()} --db {db_path} "
                  f"--skip {r['rule_key']} --word \"<дословно: кто разрешил·когда·где>\" --apply")
    counts = summarize(rows, only_yours)
    print()
    print(BOUNDARY_LINE)
    print("итог: " + " · ".join(f"{name} {counts[name]}" for name in (*STATE_NAMES, "only-yours")))


# ── КООРДИНАТОР И ОБЕЗЛИЧИВАНИЕ (для --propose) ─────────────────────────────────────

def find_coordinator(conn):
    """Имя живой роли-координатора ИЗ ДАННЫХ (тот же приём, что у gordi-issue.py) —
    None, если не нашлась РОВНО одна такая роль."""
    try:
        rows = conn.execute(
            "SELECT role FROM roles WHERE lifecycle='alive' "
            "AND lifecycle_reason LIKE '%координатор%'").fetchall()
    except sqlite3.OperationalError:
        rows = []
    if len(rows) == 1:
        return rows[0][0].upper()
    return None


def redact_machine_paths(text: str):
    found = sorted({m.group(0) for m in MACHINE_PATH.finditer(text)})
    return MACHINE_PATH.sub("<машина>/...", text), found


# ── ЗАПИСЬ (общее для --adopt/--merge/--skip) ───────────────────────────────────────

def apply_gate(apply: bool) -> bool:
    """True — писать нельзя, показываем только предпросмотр (--apply не задан)."""
    return not apply


def require_word(word, why) -> None:
    if not (word or "").strip():
        sys.exit(
            f"⛔ ЗАПИСЬ НЕ СДЕЛАНА — нужен --word «дословно: кто разрешил · когда · где» "
            f"({why}). Инструмент не может проверить, что слово подлинное, — это остаётся "
            f"на совести вызывающего."
        )


def record_base_for(base_map: dict, pairs) -> None:
    """Обновить опору РОВНО у названных пар (rule_set, rule_key, sha) — и ни у каких других."""
    for rule_set, rule_key, sha in pairs:
        base_map[f"{rule_set}/{rule_key}"] = sha


# ── ПРИЛОЖЕНИЯ ПРАВИЛ (карточка #652 этап 2, задача #651) ───────────────────────────
# ПОВОД (записка #5337, находка COORD). 13 правил свода сократили текст, вынеся разбор
# случаев в rules-annex/<ключ>.md, и в самом тексте правила осталась строка «… —
# приложение: set-rule.py --key X --annex». У СОСЕДЕЙ (контур из init-group.py, контур,
# ни разу не бравший эти ключи через --adopt) файла нет — ссылка ведёт в пустоту. Эти
# правила уходят соседям через пакет; --adopt/--merge кладут приложение ключа ВМЕСТЕ
# с текстом правила — тем же ходом, а не отдельным напоминанием, которое легко забыть.
# ⚖️ МЕСТО — mezo_paths.annex_path(): ОДНА функция на set-rule.py (--annex/--show) и
# этот инструмент (раскладка «легаси» решена там один раз, см. её докстроку).

def place_annex(pack_root: Path, db_path, key: str, *, apply: bool, force: bool) -> str | None:
    """Кладёт приложение ОДНОГО ключа из пакета в контур. None — у пакета для этого ключа
    приложения нет вовсе (обычное дело — не у каждого правила оно есть): вызывающий тогда
    ничего не печатает, шума на пустом месте не будет.

    apply=False — ТОЛЬКО говорит, куда положил бы; возврат до первой строчки записи —
    холостой прогон не пишет НИЧЕГО, ни этот файл, ни любой другой.
    force=False и в контуре уже лежит ДРУГОЕ содержимое — не переписывает, называет
    флаг согласия (--annex-force) и молчит дальше; одинаковое содержимое не спрашивает
    ничего — там нечего терять.
    """
    src = pack_root / "rules" / "annex" / f"{key}.md"
    if not src.is_file():
        return None
    want = src.read_text(encoding="utf-8")
    dst = mezo_paths.annex_path(db_path, key)
    if dst.is_file():
        have = dst.read_text(encoding="utf-8")
        if have == want:
            return f"📎 приложение {key}: уже на месте, совпадает ({len(want)} зн.) — {dst}"
        if not force:
            return (f"⚠️ приложение {key}: В КОНТУРЕ ДРУГОЕ содержимое ({len(have)} зн. против "
                    f"{len(want)} в пакете) — НЕ ПЕРЕЗАПИСАНО. {dst}\n"
                    f"      Согласие поверх чужого текста — флагом --annex-force.")
    if not apply:
        return f"📎 приложение {key}: положил бы ({len(want)} зн.) → {dst}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(want, encoding="utf-8")
    return f"📎 приложение {key}: положено ({len(want)} зн.) → {dst}"


def pick_rule_set(rows_for_key: list, key: str, rule_set_hint):
    """Один действующий (removed_at пуст) ряд пакета для ключа. Наборов несколько с
    РАЗНЫМ текстом — нужен --rule-set; с ОДИНАКОВЫМ — набор не важен, берём любой."""
    current = [r for r in rows_for_key if not r["removed_at"]]
    if not current:
        sys.exit(f"⛔ у пакета нет ДЕЙСТВУЮЩЕГО текста «{key}» (снято либо не найдено вовсе)")
    if rule_set_hint:
        for r in current:
            if r["rule_set"] == rule_set_hint:
                return r
        sys.exit(f"⛔ в наборе «{rule_set_hint}» ключа «{key}» нет; есть в наборах: "
                 + ", ".join(sorted(r["rule_set"] for r in current)))
    if len(current) == 1:
        return current[0]
    if len({r["text_sha"] for r in current}) == 1:
        return current[0]  # тексты одинаковы во всех наборах — набор не важен
    sys.exit(
        f"⛔ ключ «{key}» есть в НЕСКОЛЬКИХ наборах пакета с РАЗНЫМ текстом ("
        + ", ".join(sorted(r["rule_set"] for r in current))
        + ") — назови --rule-set, какой набор брать"
    )


def pick_removed_rule_set(rows_for_key: list, key: str, rule_set_hint):
    """Тот же выбор набора, что у pick_rule_set(), но для СНЯТЫХ (removed_at непуст) строк.

    КАРТОЧКА #614 ②: pick_rule_set() отбрасывает снятые строки НАРОЧНО (ищет действующий
    текст — нужно --adopt/--merge/--propose). --skip у разряда «снято в пакете» ищет
    ОБРАТНОЕ — последний снятый текст, поэтому не переиспользует ту функцию целиком, а
    повторяет её же логику выбора набора на своём (уже отфильтрованном) списке строк."""
    if rule_set_hint:
        for r in rows_for_key:
            if r["rule_set"] == rule_set_hint:
                return r
        sys.exit(f"⛔ в наборе «{rule_set_hint}» снятого ключа «{key}» нет; снят в наборах: "
                 + ", ".join(sorted(r["rule_set"] for r in rows_for_key)))
    if len(rows_for_key) == 1:
        return rows_for_key[0]
    if len({r["text_sha"] for r in rows_for_key}) == 1:
        return rows_for_key[0]
    sys.exit(
        f"⛔ снятый ключ «{key}» есть в НЕСКОЛЬКИХ наборах пакета с РАЗНЫМ текстом ("
        + ", ".join(sorted(r["rule_set"] for r in rows_for_key))
        + ") — назови --rule-set, какой набор брать"
    )


def render_set_rule_preview(db_path, key, basis, word, actor, needs_expiry: bool,
                            body_file_label: str = "<тело правила пакета>",
                            expiry_args=None) -> str:
    """body_file_label — ЧТО именно ляжет в --body-file: у --adopt это текст пакета, у
    --merge — сведённый ВРУЧНУЮ текст из --file (возврат PROTO, замечание 2: холостой
    --merge звал его «телом правила пакета», хотя пишет он совсем не пакетный текст).
    expiry_args (карточка #650) — готовые аргументы срока (plan_adopt_expiry); при них
    needs_expiry не смотрится."""
    word_display = word if (word or "").strip() else "<--word не задан>"
    actor_display = actor if (actor or "").strip() else "<--actor не задан>"
    if expiry_args is not None:
        expiry = render_expiry_args(expiry_args)
    else:
        expiry = " --expiry-kind forever" if needs_expiry else ""
    return (f'python {SET_RULE_PY} --db {db_path} --key {key} --body-file {body_file_label} '
            f'--basis "{basis}" --authorized-by "{word_display}" --source-ref "{word_display}"'
            f'{expiry} --actor "{actor_display}" --apply')


def run_set_rule(db_path, key, body_file, basis, word, actor, needs_expiry: bool,
                 expiry_args=None):
    """needs_expiry=True — set-rule.py потребует условие отмены явно (нечего наследовать:
    ключа у контура ещё нет, либо поле у него пустое) — ставим «бессрочно», самое
    нейтральное. needs_expiry=False — условие отмены НЕ трогаем, оно наследуется само
    (иначе --adopt/--merge тихо стёрли бы уже поставленный кем-то срок годности).
    expiry_args (карточка #650) — готовые аргументы срока из plan_adopt_expiry (срок пакета
    либо прежнее правило); при них needs_expiry не смотрится."""
    cmd = [sys.executable, str(SET_RULE_PY), "--db", str(db_path), "--key", key,
           "--body-file", str(body_file), "--basis", basis,
           "--authorized-by", word, "--source-ref", word, "--actor", actor]
    if expiry_args is not None:
        cmd += list(expiry_args)
    elif needs_expiry:
        cmd += ["--expiry-kind", "forever"]
    cmd += ["--apply"]
    cp = subprocess.run(cmd, env=subprocess_env(), capture_output=True, text=True,
                        encoding="utf-8")
    sys.stdout.write(cp.stdout)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr)
        sys.exit(f"⛔ set-rule.py отказал на «{key}» (код {cp.returncode})")


# ── --show ───────────────────────────────────────────────────────────────────────────

def show_one(pack_conn, row, key, v_body, base_map, history_has) -> None:
    rule_set = row["rule_set"]
    print(f"\n═══ {key} · набор «{rule_set}» ═══")
    print(f"\n— текст пакета сейчас (обновлён {row['pack_updated_at']}, "
          f"коммит {row['pack_commit']}):")
    if row["removed_at"]:
        print(f"⛔ СНЯТО из пакета {row['removed_at']} — текущего текста в этом наборе нет")
    else:
        print(row["body"])
    print("\n— ваш текст:")
    print(v_body if v_body is not None else "(у контура нет действующего правила с этим ключом)")
    if v_body is None or row["removed_at"]:
        return
    v_sha = text_sha(v_body)
    p_sha = row["text_sha"]
    if v_sha == p_sha:
        print("\n(текст пакета и ваш текст совпадают дословно — сравнивать больше нечего)")
        return
    base_sha, base_src = resolve_base(rule_set, key, v_sha, base_map, history_has)
    if base_sha is None:
        print("\n⛔ опоры нет — неизвестно, с какой версии пакета контур начинал:")
        print_diff("пакет → ваш", row["body"], v_body)
        return
    # ВОЗВРАТ PROTO (карточка #608, замечание 1): «с обеих сторон» (both-changed) — тот
    # единственный случай, где ДВА diff'а (опора→пакет, опора→ваш) читаются сложнее, чем
    # три текста рядом целиком: ни один из двух diff'ов не сравнивает пакет с вашим
    # текстом напрямую. У остальных состояний, где опора найдена (pack-changed/
    # local-changed), одна сторона и так совпадает с опорой — двух diff'ов хватает.
    state = classify_diff(v_sha, p_sha, base_sha)
    hist = pack_conn.execute(
        "SELECT body, first_seen_at FROM pack_rules_history "
        "WHERE rule_set=? AND rule_key=? AND text_sha=?", (rule_set, key, base_sha)).fetchone()
    if base_src == "history":
        print(f"\nопора найдена по истории пакета, версия от "
              f"{hist[1] if hist else '(дата неизвестна)'}")
    if hist is None:
        print(f"\n⚠️ отпечаток опоры известен ({base_sha}), но текста этой версии в истории "
              f"пакета больше нет — показываю без диффа «опора → …»:")
        if state == "both-changed":
            # ЗАМЕЧАНИЕ COORD (карточка #608, повторная приёмка): текст пакета и ваш текст
            # УЖЕ напечатаны выше (в начале show_one, для ЛЮБОГО состояния) — второй раз их
            # здесь не повторяем, только называем состояние и то, чего выше не было (опору).
            print(f"\n⚖️ ИЗМЕНЕНО С ОБЕИХ СТОРОН — текст пакета и ваш текст см. ВЫШЕ; опора "
                  f"известна только отпечатком ({base_sha}), текста этой версии в истории "
                  f"больше нет.")
        print_diff("пакет → ваш", row["body"], v_body)
        return
    o_body = hist[0]
    if state == "both-changed":
        # ЗАМЕЧАНИЕ COORD: та же граница — пакет и ваш текст уже показаны выше, здесь
        # печатаем ТОЛЬКО опору (единственный из трёх текстов, которого выше не было).
        print(f"\n⚖️ ИЗМЕНЕНО С ОБЕИХ СТОРОН — текст пакета и ваш текст см. ВЫШЕ; опора "
              f"(версия, от которой контур начинал) целиком:\n{o_body}")
    print_diff("опора → пакет", o_body, row["body"])
    print_diff("опора → ваш", o_body, v_body)


def cmd_show(conn, pack_conn, key, base_map, rule_set_hint, source: Path | None = None) -> int:
    v_body = load_circuit_rules(conn).get(key)
    rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key
            and (rule_set_hint is None or r["rule_set"] == rule_set_hint)]
    if not rows:
        sys.exit(f"⛔ ключа «{key}» нет в пакете" +
                 (f" в наборе «{rule_set_hint}»" if rule_set_hint else ""))
    # КАРТОЧКА #652 этап 2, п.3: --show ОДНОЙ строкой говорит, есть ли у ключа приложение
    # в пакете — не доставлено ли оно уже (это скажет --adopt/--merge), а ЕСТЬ ЛИ вообще
    # что доставлять. source=None (вызов без пакета под рукой, например из старого теста)
    # — строка тихо пропускается, это не отказ.
    if source is not None:
        annex_src = source / "rules" / "annex" / f"{key}.md"
        if annex_src.is_file():
            print(f"📎 приложение в пакете: есть, "
                  f"{len(annex_src.read_text(encoding='utf-8'))} знаков — доставит "
                  f"--adopt/--merge/--annexes, покажет set-rule.py --key {key} --annex")
        else:
            print("📎 приложение в пакете: нет")
    history_has = make_history_has(pack_conn)
    for row in rows:
        show_one(pack_conn, row, key, v_body, base_map, history_has)
    return 0


# ── --adopt ──────────────────────────────────────────────────────────────────────────

def adopt_keys(conn, db_path, pack_conn, base_map, keys, rule_set_hint, word, apply, actor,
               source: Path | None = None, annex_force: bool = False,
               expiry_from_pack: bool = False) -> int:
    by_key: dict = {}
    for row in load_pack_rows(pack_conn):
        by_key.setdefault(row["rule_key"], []).append(row)

    plan = []
    for key in keys:
        rows = by_key.get(key)
        if not rows:
            sys.exit(f"⛔ ключа «{key}» нет в пакете вовсе")
        plan.append((key, pick_rule_set(rows, key, rule_set_hint)))

    owner_locked = sorted({key for key, row in plan if row["locked_by"] == "owner"}
                          | {key for key, row in plan if circuit_locked_by(conn, key) == "owner"})
    # ВОЗВРАТ PROTO (карточка #608): --adopt по ключу, который контур САМ отключил
    # (status≠'active'), — это возврат осознанно снятого правила, не обычное взятие.
    # --word здесь обязан явно называть это решение, а не быть общим словом про запись.
    retired_here = sorted(key for key in keys if circuit_is_retired(conn, key))
    # КАРТОЧКА #650: срок каждого ключа решается ОДИН раз, до записи — показ и запись видят
    # одно и то же решение (см. plan_adopt_expiry).
    expiry_plan = {key: plan_adopt_expiry(conn, key, row, source, take_pack=expiry_from_pack)
                   for key, row in plan}

    for key, row in plan:
        basis = (f"взято из пакета GORDI, коммит {row['pack_commit']}, "
                 f"версия от {row['pack_updated_at']}")
        tag = "ВЗЯЛ БЫ" if apply_gate(apply) else "БЕРУ"
        print(f"{tag}: {key} ← набор «{row['rule_set']}» · основание: {basis}")
        expiry_args, expiry_line = expiry_plan[key]
        if expiry_line:
            print("   " + expiry_line)
        if apply_gate(apply):
            print("   " + render_set_rule_preview(db_path, key, basis, word, actor,
                                                   needs_expiry=needs_expiry_kind(conn, key),
                                                   expiry_args=expiry_args))
            if source is not None:
                msg = place_annex(source, db_path, key, apply=False, force=annex_force)
                if msg:
                    print("   " + msg)
    if owner_locked:
        print(f"⚠️ ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ (в пакете или у контура): {', '.join(owner_locked)} — "
              f"--word обязан быть словом ИМЕННО владельца; инструмент подлинность не проверяет.")
    if retired_here:
        print(f"⚠️ У ВАС СНЯТО: {', '.join(retired_here)} — правило было отключено в контуре "
              f"самим контуром, пакет его по-прежнему держит; --word обязан явно подтверждать "
              f"решение вернуть его.")

    if apply_gate(apply):
        print("\n[ХОЛОСТОЙ ПРОГОН] Не записано. Для записи — флаг --apply (и --word).")
        return 0

    require_word(word, "; ".join(filter(None, [
        "правило залочено владельцем" if owner_locked else None,
        "правило у вас снято, возврат требует явного решения" if retired_here else None,
    ])) or "любая запись правила требует --word")

    for key, row in plan:
        basis = (f"взято из пакета GORDI, коммит {row['pack_commit']}, "
                 f"версия от {row['pack_updated_at']}")
        fd, body_file = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(row["body"])
            run_set_rule(db_path, key, body_file, basis, word, actor,
                        needs_expiry=needs_expiry_kind(conn, key),
                        expiry_args=expiry_plan[key][0])
        finally:
            os.unlink(body_file)
        if source is not None:
            msg = place_annex(source, db_path, key, apply=True, force=annex_force)
            if msg:
                print("   " + msg)

    # ⚡ ОПОРА ОБНОВЛЯЕТСЯ ТОЛЬКО У ВЗЯТЫХ КЛЮЧЕЙ — строка ниже единственная, кто это решает
    adopted_pairs = [(row["rule_set"], key, row["text_sha"]) for key, row in plan]
    record_base_for(base_map, adopted_pairs)
    save_meta_map(conn, "pack_rules_base", base_map)
    conn.commit()
    print(f"\n✅ взято: {', '.join(k for k, _ in plan)} — опора обновлена только у взятых ключей")
    return 0


# ── --merge ──────────────────────────────────────────────────────────────────────────

def merge_key(conn, db_path, pack_conn, base_map, key, rule_set_hint, file_path, word, apply,
              actor, source: Path | None = None, annex_force: bool = False) -> int:
    rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key]
    if not rows:
        sys.exit(f"⛔ ключа «{key}» нет в пакете вовсе — сводить не с чем")
    row = pick_rule_set(rows, key, rule_set_hint)
    if not Path(file_path).exists():
        sys.exit(f"⛔ файла со сведённым текстом нет: {file_path}")
    merged_text = Path(file_path).read_text(encoding="utf-8")
    if not merged_text.strip():
        sys.exit("⛔ файл со сведённым текстом пуст — сводить нечем")

    basis = f"сведено с пакетом GORDI, коммит {row['pack_commit']}"
    owner_locked = row["locked_by"] == "owner" or circuit_locked_by(conn, key) == "owner"
    tag = "СВЁЛ БЫ" if apply_gate(apply) else "СВОЖУ"
    print(f"{tag}: {key} ← набор «{row['rule_set']}» · основание: {basis}")
    if apply_gate(apply):
        # ЗАМЕЧАНИЕ COORD (карточка #608, повторная приёмка): холостой --merge печатал
        # подпись «<сведённый текст из --file>», а не САМ путь — роль не видела, какой
        # именно файл set-rule.py возьмёт. Печатаем file_path — он и есть настоящее
        # значение --body-file у НАСТОЯЩЕГО вызова set-rule.py (run_set_rule ниже).
        print("   " + render_set_rule_preview(db_path, key, basis, word, actor,
                                               needs_expiry=needs_expiry_kind(conn, key),
                                               body_file_label=str(file_path)))
        if source is not None:
            msg = place_annex(source, db_path, key, apply=False, force=annex_force)
            if msg:
                print("   " + msg)
    if owner_locked:
        print("⚠️ ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ — --word обязан быть словом ИМЕННО владельца; "
              "инструмент подлинность не проверяет.")

    if apply_gate(apply):
        print("\n[ХОЛОСТОЙ ПРОГОН] Не записано. Для записи — флаг --apply (и --word).")
        return 0

    require_word(word, "правило залочено владельцем" if owner_locked else
                        "любая запись правила требует --word")
    run_set_rule(db_path, key, file_path, basis, word, actor,
                needs_expiry=needs_expiry_kind(conn, key))
    if source is not None:
        msg = place_annex(source, db_path, key, apply=True, force=annex_force)
        if msg:
            print("   " + msg)

    record_base_for(base_map, [(row["rule_set"], key, row["text_sha"])])
    save_meta_map(conn, "pack_rules_base", base_map)
    conn.commit()
    print("\n✅ сведено — опора теперь равна текущей версии пакета")
    return 0


# ── --skip ───────────────────────────────────────────────────────────────────────────

def skip_key(conn, pack_conn, skip_map, key, rule_set_hint, word, apply) -> int:
    """⚖️ КАРТОЧКА #614 ②: --skip годится и для разряда «снято в пакете» (removed_at непуст) —
    «пакет его больше не несёт, а я держу и дальше». Сначала ищем ДЕЙСТВУЮЩИЙ текст (старое
    поведение, не тронуто); нет действующего — берём последний СНЯТЫЙ (pick_removed_rule_set,
    а не pick_rule_set — та НАРОЧНО отбрасывает снятые строки, см. её докстроку)."""
    active_rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and not r["removed_at"]]
    if active_rows:
        row = pick_rule_set(active_rows, key, rule_set_hint)
    else:
        removed_rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and r["removed_at"]]
        if not removed_rows:
            sys.exit(f"⛔ ключа «{key}» нет в пакете вовсе — отказываться не от чего")
        row = pick_removed_rule_set(removed_rows, key, rule_set_hint)

    tag = "ОТКАЗАЛСЯ БЫ" if apply_gate(apply) else "ОТКАЗЫВАЮСЬ"
    when = (f"снято {row['removed_at']}, коммит {row['pack_commit']}" if row["removed_at"]
           else f"версия от {row['pack_updated_at']}")
    print(f"{tag}: {key} ← набор «{row['rule_set']}» ({when})")
    if apply_gate(apply):
        print("\n[ХОЛОСТОЙ ПРОГОН] Не записано. Для записи — флаг --apply (и --word). "
              "⚖️ --skip НЕ вызывает set-rule.py — он пишет только в meta контура.")
        return 0

    require_word(word, "любая запись требует --word")
    skip_map[f"{row['rule_set']}/{key}"] = row["text_sha"]
    save_meta_map(conn, "pack_rules_skipped", skip_map)
    conn.commit()
    print("\n✅ отказ записан — вернётся к обычному сравнению, как только пакет сменит текст")
    return 0


# ── --annexes ────────────────────────────────────────────────────────────────────────
# КАРТОЧКА #652 этап 2, задача #651, п.3: путь для правил, чей ключ УЖЕ совпадает с
# пакетом (state=same) — --adopt здесь взять нечего (текст и так тот же), а приложения
# контур всё равно не увидит без этого хода: например, контур собран ДО того, как пакет
# обзавёлся приложениями, и с тех пор текст этих ключей не менялся ни у кого.
# ⚖️ --word НЕ СПРАШИВАЕМ — тем же доводом, что у --record-base чуть ниже: у ключа
# «same» ничьё решение не меняется, текст и так тот же, что в пакете. --actor по-прежнему
# нужен (кто клал приложения) — проверяется в main(), тем же местом, что у --record-base.

def cmd_annexes(conn, db_path, pack_conn, source: Path, base_map, skip_map, contour_sets,
                retired_keys, apply, actor, force) -> int:
    circuit_rules = load_circuit_rules(conn)
    pack_rows = load_pack_rows(pack_conn)
    rows, _ = build_rows(circuit_rules, pack_rows, base_map, skip_map,
                         make_history_has(pack_conn), contour_sets, retired_keys)
    same_keys = sorted(r["rule_key"] for r in rows if r["state"] == "same")
    if not same_keys:
        print("(ключей в состоянии «same» нет — класть приложения не для чего)")
        return 0
    printed = 0
    for key in same_keys:
        msg = place_annex(source, db_path, key, apply=apply, force=force)
        if msg:
            print(msg)
            printed += 1
    if not printed:
        print(f"(проверено ключей «same»: {len(same_keys)} — ни у одного из них в пакете "
              f"нет приложения)")
    if not apply:
        print("\n[ХОЛОСТОЙ ПРОГОН] Не записано. Для записи — флаг --apply (и --actor).")
    else:
        print(f"\n✅ приложения проверены (актёр: {actor}) — ключей «same» {len(same_keys)}, "
              f"строк напечатано {printed}")
    return 0


# ── --record-base ────────────────────────────────────────────────────────────────────
# ⚖️ --word ЗДЕСЬ НЕ СПРАШИВАЕМ (в отличие от --adopt/--merge/--skip). Эти три меняют
# судьбу правила — берут чужой текст, сводят или отказываются — и это решение владельца
# или координатора. Запись опоры у УЖЕ СОВПАВШЕГО текста ничьего решения не меняет:
# это чинит бухгалтерию по факту, который и так уже верен. Актёра по-прежнему называть
# нужно (кто свёл бухгалтерию) — это проверяется ДО вызова, в main().

def record_base(conn, pack_rows: list, base_map: dict, apply: bool, actor,
                contour_sets: list) -> int:
    """Опора — ВСЕМ ключам, где текст контура сейчас РАВЕН тексту пакета (по отпечатку),
    и только им. Несовпавших не трогаем вовсе — ни добавить, ни убрать у них запись.
    Сверяется ПО ПОБЕДИВШЕМУ описанию взятых контуром наборов (governing_rows) — не по
    каждому набору порознь: иначе universal-версия ключа, перекрытого доменом, ложно
    заявила бы себя опорой рядом с настоящей (карточка #608, возврат PROTO)."""
    circuit_rules = load_circuit_rules(conn)
    governing = governing_rows(pack_rows, contour_sets)
    matched = []
    for key, row in governing.items():
        if row["removed_at"]:
            continue
        v_body = circuit_rules.get(key)
        if v_body is None or text_sha(v_body) != row["text_sha"]:
            continue
        matched.append((row["rule_set"], key, row["text_sha"]))
    already = sum(1 for rs, rk, sha in matched if base_map.get(f"{rs}/{rk}") == sha)
    to_write = len(matched) - already

    tag = "ЗАПИСАЛ БЫ" if apply_gate(apply) else "ЗАПИСЫВАЮ"
    print(f"{tag} опору у совпадающих ключей: совпадает всего {len(matched)}, "
          f"уже верно записано {already}, {'будет изменено' if apply_gate(apply) else 'изменено'} "
          f"{to_write}")
    if apply_gate(apply):
        print("\n[ХОЛОСТОЙ ПРОГОН] Не записано. Для записи — флаг --apply (и --actor).")
        return 0

    record_base_for(base_map, matched)
    save_meta_map(conn, "pack_rules_base", base_map)
    conn.commit()
    print(f"\n✅ опора сверена (актёр: {actor}) — совпадающих ключей {len(matched)}, "
          f"изменено записей {to_write}")
    return 0


# ── --summary ────────────────────────────────────────────────────────────────────────
# Одна строка для ЧУЖОГО вызова (инструмент обновления контура и т.п.) — БЕЗ построчного
# списка. Отказ (нет базы пакета / нет базы контура) — код 2 и причина В ТЕКСТЕ, не
# молчание: чужой вызывающий обязан различить «всё чисто» от «сверка не состоялась».

def cmd_summary(args) -> int:
    try:
        db_path = mezo_paths.resolve_db(args.db, __file__, must_exist=True, readonly=True)
        conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
        source = find_pack_source(args.source, conn)
        pack_conn = open_pack_db(source)
    except SystemExit as e:
        msg = e.code if isinstance(e.code, str) else f"⛔ отказ при поиске баз (код {e.code})"
        print(msg, file=sys.stderr)
        return 2

    circuit_rules = load_circuit_rules(conn)
    pack_rows = load_pack_rows(pack_conn)
    contour_sets, via_meta = resolve_contour_rule_sets(conn, circuit_rules, pack_rows)
    note = rule_sets_note(contour_sets, via_meta)
    if note:
        print(note)
    rows, only_yours = build_rows(circuit_rules, pack_rows, load_meta_map(conn, "pack_rules_base"),
                                  load_meta_map(conn, "pack_rules_skipped"),
                                  make_history_has(pack_conn), contour_sets,
                                  load_circuit_retired_keys(conn))
    counts = summarize(rows, only_yours)
    print(f"правила пакета: новых {counts['new']} · изменено в пакете {counts['pack-changed']} · "
          f"уточнено у вас {counts['local-changed']} · с обеих сторон {counts['both-changed']} · "
          f"опоры нет {counts['no-base']} · снято в пакете {counts['removed']} · "
          f"снято у вас {counts['retired-here']} — "
          f"подробно: rules-from-pack.py")
    # КАРТОЧКА #650: вторая строка — только когда есть что сказать про срок (иначе вывод прежний)
    take, own = expiry_differences(conn, rows, source)
    if take or own:
        print(f"срок правил пакета: взять можно у {len(take)} · у вас свой у {len(own)} — "
              f"подробно: rules-from-pack.py")
    return 0


# ── --propose ────────────────────────────────────────────────────────────────────────

def describe_source_occurrences(source: Path, rule_set: str, rule_key: str):
    """ВОЗВРАТ PROTO (карточка #608, замечание 3): ключ может быть ОПИСАН НЕСКОЛЬКО РАЗ в
    исходном .sql пакета — несколько блоков `INSERT OR REPLACE`, SQL исполняет их по
    порядку файла, и действует ПОСЛЕДНЕЕ описание. pack_rules несёт только итог (одну
    строку на ключ) — не видно, что правка ПЕРВОГО описания ничего не изменит. Читаем
    САМ исходник (только чтение), называем число описаний и строку последнего.
    None — исходника .sql нет (например, собранная копия без него) или описание ровно одно
    (тогда говорить не о чем)."""
    sql_path = pack_sql_path(source, rule_set)
    if not sql_path.exists():
        return None
    text = sql_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^\(\s*'" + re.escape(rule_key) + r"'\s*,", re.M)
    lines_matched = [text.count("\n", 0, m.start()) + 1 for m in pattern.finditer(text)]
    if len(lines_matched) <= 1:
        return None
    return (f"⚠️ ключ описан в {sql_path.name} {len(lines_matched)} раз, действует "
            f"ПОСЛЕДНЕЕ описание (строка {lines_matched[-1]}) — правьте его.")


def write_proposal_letter(conn, title: str, body: str, out_path) -> int:
    """Хвост письма --propose, ОБЩИЙ для обеих причин письма (замена текста контуром /
    снятие ключа, который контур сам отключил): обезличивание путей машины, запись файла,
    подсказка на канал issues. Путь к gordi-issue.py — от СВОЕГО расположения (возврат
    PROTO, карточка #608: прежде был впечатан и годился только автору инструмента)."""
    body, found = redact_machine_paths(body)
    if not out_path:
        sys.exit("⛔ --propose требует --out <файл> — тело предложения без пути не пишется")
    Path(out_path).write_text(body, encoding="utf-8")
    print(f"✅ тело предложения записано: {out_path}")
    if found:
        print(f"⚠️ обезличены пути машины ({len(found)} шт.) — проверь текст глазами перед отправкой")

    coordinator = find_coordinator(conn)
    role_for_cmd = coordinator or "<координатор>"
    if coordinator is None:
        print("⚠️ не нашёл РОВНО ОДНУ живую роль-координатора в roles.lifecycle_reason — "
              "подставь имя координатора сам")
    print("👉 сначала холостой прогон канала issues, затем — по слову координатора:")
    print(f'   python {GORDI_ISSUE_PY} create '
          f'--role {role_for_cmd} --title "{title}" --body-file {out_path} --dry-run')
    return 0


def propose_retire(conn, pack_conn, source: Path, key, why, out_path, rule_set_hint) -> int:
    """ВОЗВРАТ PROTO (карточка #608, повторная приёмка): ключ, который контур САМ снял
    (retired-here) — раньше --propose по нему отказывал («предлагать нечего»), хотя
    предложить есть что: снять этот ключ в пакете ДЛЯ ВСЕХ, раз контур от него уже
    отказался. Письмо называет, ЧТО ИМЕННО снято у контура — по полям его же строки в
    `rules` (какие заполнены), а не только словом «снято»."""
    rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and not r["removed_at"]]
    if not rows:
        sys.exit(f"⛔ у пакета уже нет действующего текста «{key}» — снимать нечего, он и так снят")
    row = pick_rule_set(rows, key, rule_set_hint)
    p_body = row["body"]

    circuit_row = conn.execute(
        "SELECT status, basis, revoked_at, revoked_by, revoked_reason, superseded_by, "
        "updated_at FROM rules WHERE rule_key=?", (key,)).fetchone()
    (status, basis, revoked_at, revoked_by, revoked_reason, superseded_by, updated_at) = (
        circuit_row if circuit_row else (None, None, None, None, None, None, None))

    def show_field(label, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return f"{label}: (не заполнено)"
        return f"{label}: {value}"

    fields_block = "\n".join([
        show_field("статус", status),
        show_field("основание снятия (basis)", basis),
        show_field("отмена — когда (revoked_at)", revoked_at),
        show_field("отмена — кем (revoked_by)", revoked_by),
        show_field("отмена — причина (revoked_reason)", revoked_reason),
        show_field("заменено записью (superseded_by)", superseded_by),
        show_field("последняя правка (updated_at)", updated_at),
    ])

    dup_note = describe_source_occurrences(source, row["rule_set"], key)
    measure = (
        f"у контура ключ «{key}» СНЯТ (не действует):\n{fields_block}\n\n"
        f"текст пакета сейчас (набор «{row['rule_set']}», обновлён {row['pack_updated_at']}, "
        f"коммит {row['pack_commit']}):\n{p_body}"
        + (f"\n\n{dup_note}" if dup_note else "")
    )
    body = (
        f"## ЗАМЕР\n{measure}\n\n"
        f"## КЛАСС\n{why.strip()}\n\n"
        f"## ПРЕДЛОЖЕНИЕ\n"
        f"снять правило «{key}» в наборе «{row['rule_set']}» из пакета — контур больше его "
        f"не несёт (снятие описано выше), предложение просит убрать его для всех. "
        f"Цена: строк уберётся {len(p_body.splitlines())} (весь текущий текст правила).\n"
    )
    title = f"pack-rules: снять «{key}» в наборе «{row['rule_set']}»"
    return write_proposal_letter(conn, title, body, out_path)


def propose(conn, pack_conn, source: Path, key, why, out_path, rule_set_hint) -> int:
    v_body = load_circuit_rules(conn).get(key)
    if v_body is None:
        if circuit_is_retired(conn, key):
            return propose_retire(conn, pack_conn, source, key, why, out_path, rule_set_hint)
        sys.exit(f"⛔ у контура нет действующего правила «{key}» — предлагать нечего")
    rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and not r["removed_at"]]
    if not rows:
        sys.exit(f"⛔ у пакета нет действующего текста «{key}» — предлагать замену не на что")
    row = pick_rule_set(rows, key, rule_set_hint)
    p_body = row["body"]
    if text_sha(v_body) == text_sha(p_body):
        sys.exit(f"⛔ текст «{key}» у контура и у пакета УЖЕ совпадает дословно — предлагать нечего")

    diff_lines = list(difflib.unified_diff(
        p_body.splitlines(), v_body.splitlines(), lineterm=""))
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed_n = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    dup_note = describe_source_occurrences(source, row["rule_set"], key)
    measure = (
        f"пакет, набор «{row['rule_set']}», обновлено {row['pack_updated_at']} "
        f"(коммит {row['pack_commit']}):\n{p_body}\n\n"
        f"текст контура:\n{v_body}\n\n"
        f"различие (пакет → контур):\n" + "\n".join(diff_lines)
        + (f"\n\n{dup_note}" if dup_note else "")
    )
    body = (
        f"## ЗАМЕР\n{measure}\n\n"
        f"## КЛАСС\n{why.strip()}\n\n"
        f"## ПРЕДЛОЖЕНИЕ\n"
        f"заменить текст правила «{key}» в наборе «{row['rule_set']}» на текст контура. "
        f"Цена: строк добавится {added}, уберётся {removed_n} (по построчному различию).\n"
    )
    title = f"pack-rules: обновить «{key}» в наборе «{row['rule_set']}»"
    return write_proposal_letter(conn, title, body, out_path)


# ── main ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Правила пакета GORDI против правил контура: список расхождений, показ, "
                     "взятие, сведение, отказ, тело предложения в пакет (карточка #608).")
    ap.add_argument("--db", default=None,
                    help="БД контура (по умолчанию — живая, от расположения скрипта)")
    ap.add_argument("--source", default=None,
                    help="папка с клоном пакета (по умолчанию — meta.template_checkout контура)")
    ap.add_argument("--state", choices=STATE_NAMES, default=None,
                    help="показать только строки этого состояния")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--show", metavar="KEY")
    mode.add_argument("--adopt", nargs="+", metavar="KEY")
    mode.add_argument("--merge", metavar="KEY")
    mode.add_argument("--skip", metavar="KEY")
    mode.add_argument("--propose", metavar="KEY")
    mode.add_argument("--record-base", dest="record_base", action="store_true",
                      help="записать опору всем ключам, чей текст СЕЙЧАС равен тексту пакета")
    # КАРТОЧКА #652 этап 2, п.3: приложения для ключей «same» — --adopt тут взять нечего
    mode.add_argument("--annexes", action="store_true",
                      help="положить недостающие приложения ключам, чьё правило в контуре "
                           "УЖЕ совпадает с пакетом (state=same); без --apply — только "
                           "куда положил бы")
    mode.add_argument("--summary", action="store_true",
                      help="одна строка итога без списка, для чужого вызова")
    ap.add_argument("--file", default=None, help="файл со сведённым текстом (нужен с --merge)")
    ap.add_argument("--why", default=None, help="одно предложение класса ошибки (--propose)")
    ap.add_argument("--out", default=None, help="файл для тела предложения (--propose)")
    ap.add_argument("--rule-set", dest="rule_set", default=None,
                    help="какой набор пакета брать, если ключ есть в нескольких с разным текстом")
    ap.add_argument("--word", default=None,
                    help="дословно: кто разрешил · когда · где — обязателен при записи "
                         "(--adopt/--merge/--skip)")
    ap.add_argument("--actor", default=None,
                    help="кто пишет в audit_log контура — своё имя роли; ОБЯЗАТЕЛЕН вместе "
                         "с --apply у --adopt/--merge/--record-base/--annexes, без --apply "
                         "не нужен")
    ap.add_argument("--apply", action="store_true", help="без него — холостой прогон")
    ap.add_argument("--annex-force", dest="annex_force", action="store_true",
                    help="переписать чужое ДРУГОЕ содержимое приложения (по умолчанию — не "
                         "трогаем и говорим словами); касается --adopt/--merge/--annexes")
    # КАРТОЧКА #650: по умолчанию --adopt свой срок контура не трогает (берёт срок пакета, только
    # когда у контура пусто или заготовка сборки)
    ap.add_argument("--expiry-from-pack", dest="expiry_from_pack", action="store_true",
                    help="--adopt: взять срок (вид и условие) из посева пакета и тогда, когда "
                         "у контура стоит свой срок, а не заготовка сборки")
    return ap


def main() -> int:
    args = build_parser().parse_args()

    if args.merge and not args.file:
        sys.exit("⛔ --merge требует --file <файл со сведённым текстом>")
    if args.propose and not args.why:
        sys.exit("⛔ --propose требует --why <одно предложение: что уточнение исправляет>")
    if args.propose and not args.out:
        sys.exit("⛔ --propose требует --out <файл для тела предложения>")
    if args.expiry_from_pack and not args.adopt:
        sys.exit("⛔ --expiry-from-pack — только вместе с --adopt")

    # ⚖️ ПИШУЩИЙ В КОНТУРЕ ВСЕГДА НАЗЫВАЕТ СЕБЯ (как backlog.py --actor, lease.py --role) —
    # проверка ДО любого соединения с базой: отказ обязан быть нулевым по последствиям.
    if args.apply and (args.adopt or args.merge or args.record_base or args.annexes) \
            and not (args.actor or "").strip():
        sys.exit(
            "⛔ ЗАПИСЬ НЕ СДЕЛАНА — нужен --actor <имя роли>: пишущий в контуре всегда "
            "называет себя. Без --apply флаг не нужен."
        )

    if args.summary:
        return cmd_summary(args)

    is_write = bool(args.adopt or args.merge or args.skip or args.record_base or args.annexes)
    db_path = mezo_paths.resolve_db(args.db, __file__, must_exist=True, readonly=not is_write)
    conn = sqlite3.connect(
        f"file:{Path(db_path).as_posix()}?mode={'rw' if is_write else 'ro'}", uri=True)

    source = find_pack_source(args.source, conn)
    pack_conn = open_pack_db(source)

    if args.show:
        return cmd_show(conn, pack_conn, args.show, load_meta_map(conn, "pack_rules_base"),
                        args.rule_set, source=source)
    if args.adopt:
        return adopt_keys(conn, db_path, pack_conn, load_meta_map(conn, "pack_rules_base"),
                          args.adopt, args.rule_set, args.word, args.apply, args.actor,
                          source=source, annex_force=args.annex_force,
                          expiry_from_pack=args.expiry_from_pack)
    if args.merge:
        return merge_key(conn, db_path, pack_conn, load_meta_map(conn, "pack_rules_base"),
                         args.merge, args.rule_set, args.file, args.word, args.apply, args.actor,
                         source=source, annex_force=args.annex_force)
    if args.skip:
        return skip_key(conn, pack_conn, load_meta_map(conn, "pack_rules_skipped"),
                        args.skip, args.rule_set, args.word, args.apply)
    if args.record_base:
        pack_rows = load_pack_rows(pack_conn)
        contour_sets, via_meta = resolve_contour_rule_sets(conn, load_circuit_rules(conn), pack_rows)
        note = rule_sets_note(contour_sets, via_meta)
        if note:
            print(note)
        return record_base(conn, pack_rows, load_meta_map(conn, "pack_rules_base"),
                           args.apply, args.actor, contour_sets)
    if args.annexes:
        pack_rows = load_pack_rows(pack_conn)
        contour_sets, via_meta = resolve_contour_rule_sets(conn, load_circuit_rules(conn), pack_rows)
        note = rule_sets_note(contour_sets, via_meta)
        if note:
            print(note)
        return cmd_annexes(conn, db_path, pack_conn, source, load_meta_map(conn, "pack_rules_base"),
                           load_meta_map(conn, "pack_rules_skipped"), contour_sets,
                           load_circuit_retired_keys(conn), args.apply, args.actor,
                           args.annex_force)
    if args.propose:
        return propose(conn, pack_conn, source, args.propose, args.why, args.out, args.rule_set)

    # список — режим по умолчанию
    circuit_rules = load_circuit_rules(conn)
    pack_rows = load_pack_rows(pack_conn)
    contour_sets, via_meta = resolve_contour_rule_sets(conn, circuit_rules, pack_rows)
    note = rule_sets_note(contour_sets, via_meta)
    if note:
        print(note)
    rows, only_yours = build_rows(circuit_rules, pack_rows, load_meta_map(conn, "pack_rules_base"),
                                  load_meta_map(conn, "pack_rules_skipped"),
                                  make_history_has(pack_conn), contour_sets,
                                  load_circuit_retired_keys(conn))
    print_listing(rows, only_yours, args.state, db_path)
    # КАРТОЧКА #650: срок пакета у ключей, чей текст уже как в пакете (при отборе --state
    # другого состояния блок не печатается — он только про «same»)
    if args.state in (None, "same"):
        take, own = expiry_differences(conn, rows, source)
        print_expiry_differences(take, own, db_path)
    return 0


if __name__ == "__main__":
    # КАРТОЧКА #614 ①: find_pack_source() может завести временный клон через
    # update-tools.fetch() (mezo_stand.new() внутри неё уже поставил его на учёт) —
    # finish() решает, убрать его или сохранить, ТЕМ ЖЕ способом, что и update-tools.py.
    sys.exit(mezo_stand.finish(main()))
