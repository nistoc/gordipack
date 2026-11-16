#!/usr/bin/env python
# SURFACES: memory
# -*- coding: utf-8 -*-
r"""ПАМЯТЬ ЗАПИСЯМИ С ПОЛЯМИ: завести · отобрать · собрать тело обратно · сверить.

ЗАЧЕМ (карточка #524). Память роли — сплошной текст без единого поля. Отсюда три беды:
владелец не может ПОСМОТРЕТЬ, что в ней лежит (только прочитать двадцать тысяч знаков);
проверки вынуждены угадывать протухшее ОБРАЗЦАМИ ПО ТЕКСТУ и промахиваются в обе стороны
(замер @CORE: 16 ложных на 1 верную); сжатие режет вслепую.

ЧТО ЗДЕСЬ ЕСТЬ
    --разобрать   разложить свой раздел на записи (по блокам), поля проставить
    --пересобрать разобрать ЗАНОВО после того, как тело изменилось (то есть после
                  каждого сохранения памяти), СОХРАНИВ ручные поля там, где текст
                  блока совпал дословно; потерянные поля называются поимённо
    --показать    что лежит: список записей с полями, а не кусок текста
    --отобрать    по предмету · по часу · по живости — ОТВЕТ СПИСКОМ
    --собрать     сложить записи обратно в сплошное тело и СВЕРИТЬ с живым
    --снять       пометить запись снятой: чем и когда (живость не удаляется)
    --поля        дописать полям запись: источник · условие снятия · предмет
    --сжать       унести из слоя hot в слой warm столько записей, чтобы слой уложился
                  в порог раздела (карточка #781, этап Э2); --dry-run — только показать
    --перенести   перенести ОДНУ запись в другой слой рукой: --перенести ID --слой X
    --слой        отбор для --показать и --отобрать (hot · warm · permanent)

🔑 ПОРОГ СЖАТИЯ НЕ ПЕРЕДАЁТСЯ ПРИЗНАКОМ ВОВСЕ. Он читается из соседнего
guard-phoenix-volume.py (то же число, что судит объём раздела при сохранении памяти):
роль, которой порог можно назвать в вызове, назвала бы его под давлением числа.
Сжатие трогает ТОЛЬКО слой hot: warm и permanent остаются как есть, а текст записей и
сплошной текст раздела не меняются ни на знак — меняется лишь поле слоя.

⚖️ ЗАПИСИ ЛЕЖАТ РЯДОМ С ТЕЛОМ, А НЕ ВМЕСТО НЕГО. Пробуждение роли читает то же тело,
что и вчера, — этот слой сломать его не может. Цена выбора названа прямо: два места
об одном предмете МОГУТ РАЗОЙТИСЬ, и потому здесь есть `--собрать`, который складывает
записи обратно и показывает расхождение ЧИСЛОМ. Молча расходиться им нечем.

⛔ РОЛЬ РАЗБИРАЕТ СВОЮ ПАМЯТЬ САМА (слово владельца 2026-09-04 13:41 UTC: «только свою,
остальные сами»). Чужую можно ПОКАЗАТЬ и ОТОБРАТЬ, разобрать и править — нет.

Зовут так:
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --section state --разобрать
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --показать
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --отобрать права
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --section state --собрать
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --section state --сжать --dry-run
    python <КОНТУР>/vnext-tools/memory-records.py --role PROTO --перенести 12 --слой permanent
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import os
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

# ⚖️ РЕЗКА НА БЛОКИ БЕРЁТСЯ У СОСЕДНЕГО ИНСТРУМЕНТА, А НЕ ПИШЕТСЯ ЗАНОВО. Две копии
# одного разбора разъехались бы молча, и тогда «собрать обратно» перестало бы сходиться
# ровно в тех разделах, где резали по-разному. Это тот же довод, что и у правила
# «полный текст живёт в одном месте», только про код.
_spec = importlib.util.spec_from_file_location(
    "ma", pathlib.Path(__file__).with_name("memory-archive.py"))
_ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ma)

# ── ПРЕДМЕТЫ ЗАПИСЕЙ ───────────────────────────────────────────────────────────────
# ⚖️ Список ОТКРЫТ: инструмент принимает любой предмет, а эти лишь предлагает и печатает.
# Закрытый список состарился бы молча — ровно то, за что контур платил в перечне
# слов-типов (карточка #497). Здесь он стареет ВИДИМО: печатается при разборе.
SUBJECTS = {
    "право": ("право", "разрешено", "запрещено", "⛔", "мандат", "слово владельца",
              "слова владельца", "решения владельца"),
    "позиция": ("позиция", "сейчас", "в работе", "остановил", "сделано"),
    "план": ("план", "следующий шаг", "очередь", "首"),
    "урок": ("класс:", "⚡ класс", "урок", "оплачено", "👉 форма", "примета",
             "классы", "грабли", "чему меня научил"),
    "ошибка": ("ошиб", "🩸", "против себя", "поймал"),
    "замер": ("замер", "померил", "числом", "📏"),
    "инвариант": ("инвариант", "не переучиваться", "🔁"),
    "надгробие": ("⚰️", "надгробие", "отозван", "снято"),
    "указатель": ("бери запросом", "смотри", "живое:", "role-brief"),
}
DATE_PATTERNS = (
    re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b"),
    re.compile(r"\b(\d\d)\.(\d\d)\.(20\d\d)\b"),
    re.compile(r"\b(\d\d)\.(\d\d)\b(?!\.)"),
)


def _scores(text: str) -> dict:
    low = text.lower()
    return {name: sum(1 for mark in marks if mark.lower() in low)
            for name, marks in SUBJECTS.items()}


def subject_and_dispute(body: str) -> tuple[str, str | None]:
    """(предмет, спор). Спор — строка «кто с кем и с каким счётом» или None.

    ⚡ ПРАВИЛО С 2026-09-04 20:27 UTC — карточка #534, замеры @TAXO (3 промаха из 10)
    и @CHROME (блок «🪤 УРОКИ — ОНИ ДОРОЖЕ СДЕЛАННОГО» получил «надгробие»).
    Прежде предмет считался ЧИСЛОМ совпавших слов по всему телу, а при равенстве
    побеждал первый в списке — молча. Замер «до» на живой памяти: у 135 записей из 233
    второй предмет отставал на одно слово, и выбор между ними делал порядок словаря.
    🩸 Случай @CHROME вес заголовка ×2 НЕ лечил: в теле три слова про отзыв. Отсюда:

      ① ЗАГОЛОВОК НАЗЫВАЕТ ПРЕДМЕТ. Автор сам подписал блок — это его слово, а не
         статистика. Если заголовок называет РОВНО ОДИН предмет — он и есть предмет.
      ② Заголовок молчит — считает тело. Второй отстаёт не больше чем на слово —
         это СПОР, и он ПОМЕЧЕН, а не решён порядком словаря.
      ③ Заголовок называет ДВА и больше — спор между НИМИ, решает тело; помечен.

    ⚖️ Это по-прежнему подсказка по СЛОВАМ, а предмет — смысл. Ноль промахов недостижим;
    цель — верно чаще И спорное видно. Правится рукой: --поля <id> --предмет.
    """
    lines = body.strip().splitlines() or [""]
    heading = lines[0]
    in_head = {name: n for name, n in _scores(heading).items() if n}
    in_body = _scores(body)
    if len(in_head) == 1:
        return next(iter(in_head)), None
    if len(in_head) >= 2:
        candidates = sorted(in_head, key=lambda k: (-in_body[k], -in_head[k]))
        c1, c2 = candidates[0], candidates[1]
        return c1, f"заголовок называет и «{c2}» (тело {in_body[c1]}:{in_body[c2]})"
    ranked = sorted(in_body.items(), key=lambda kv: -kv[1])
    (c1, s1), (c2, s2) = ranked[0], ranked[1]
    if s1 == 0:
        return "разное", None
    if s2 > 0 and s1 - s2 <= 1:
        return c1, f"«{c2}» отстаёт на {s1 - s2} ({s1}:{s2}) — заголовок молчит"
    return c1, None


def subject_of_block(body: str) -> str:
    """Какой предмет вероятнее. ⚖️ ПОДСКАЗКА, а не приговор — правится ключом --поля."""
    return subject_and_dispute(body)[0]


def time_of_block(body: str, today: datetime.date):
    """Самая свежая дата в блоке, НО НЕ ИЗ БУДУЩЕГО. None — дат нет.

    🩸 ОПЛАЧЕНО ПЕРВЫМ ЖЕ РАЗБОРОМ СВОЕЙ ПАМЯТИ (2026-09-04 15:04 UTC): признак взял
    самую свежую дату и получил 2026-09-09 — СРОК, назначенный соседями, а не час
    события. Запись о вчерашней работе оказалась помечена будущим.
    ⚡ КЛАСС: «САМАЯ СВЕЖАЯ ДАТА В ТЕКСТЕ» И «КОГДА ЭТО ПРОИЗОШЛО» — РАЗНЫЕ ВЕЩИ.
    В наших текстах даты бывают трёх родов: час события · срок в будущем · чужая дата
    в цитате. Признак различал их никак и молчал бы об этом: отбор «что записано вчера»
    просто не показал бы запись, и никто не узнал бы почему.
    ⚖️ Будущее отбрасывается целиком: часом события оно быть не может по определению.
    Остальные два рода признак по-прежнему не различает — сказано прямо, а не умолчано.
    """
    found = []
    for n, pat in enumerate(DATE_PATTERNS):
        for m in pat.finditer(body):
            try:
                if n == 0:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif n == 1:
                    d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    d = datetime.date(today.year, int(m.group(2)), int(m.group(1)))
                    if d > today:
                        d = d.replace(year=today.year - 1)
            except ValueError:
                continue
            if d <= today:          # ⛔ будущее часом события быть не может
                found.append(d)
    return max(found).isoformat() if found else None


def has_table(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='phoenix_records'").fetchone())


# слой памяти записи: значение по умолчанию — живой слой (карточка #781, этап Э2)
LAYER_DEFAULT = "hot"


def has_layer(conn) -> bool:
    """Сведён ли шаг схемы, заводящий поле слоя (20261115-phoenix-records-layer).

    ⚖️ ПОЧЕМУ ПРОВЕРКА, А НЕ ТРЕБОВАНИЕ. Эти инструменты уезжают в другие контуры
    пакетом, и там шаг схемы может быть не сведён. Запрос с несведённым полем падал бы
    «no such column» на ровном месте, а падение инструмента памяти роль читает как
    поломку памяти. Поэтому: поля нет — работаем без него и ГОВОРИМ об этом вслух
    один раз, с точной командой. Молчать нельзя: тогда роль решит, что слой у записей
    есть, и будет ждать переноса, которого не будет.
    """
    return any(r[1] == "layer" for r in conn.execute("PRAGMA table_info(phoenix_records)"))


LAYERS = ("hot", "warm", "permanent")
LAYER_STEP = "20261115-phoenix-records-layer.py"
VOLUME_GUARD = "guard-phoenix-volume.py"


def refuse_no_layer(what):
    """Отказ кодом 1: поля слоя в базе нет, а вызов без него смысла не имеет."""
    sys.exit(f"⛔ ОТКАЗ: {what} требует поля СЛОЯ памяти у записей, а в этой базе его нет — "
             "шаг схемы не сведён. Ничего не записано.\n"
             f"   Свести: python <КОНТУР>/.mezosync/scripts/migrations/{LAYER_STEP}")


def volume_limit():
    """→ (порог, имя источника) либо (None, причина). Читается так же, как у save-phoenix.py.

    ⚖️ ЧИСЛО НЕ ВПИСАНО СЮДА И НЕ ПРИНИМАЕТСЯ ПРИЗНАКОМ. Порог раздела живёт в одном месте —
    в LIMIT соседнего guard-phoenix-volume.py, — и сжатие обязано мерить тем же числом, каким
    судится объём при сохранении памяти. «Не прочитан» не схлопывается в «порога нет»:
    иначе поломка соседнего файла дала бы вечное «уносить нечего».
    """
    here = pathlib.Path(__file__).resolve().parent
    candidates = [here / VOLUME_GUARD, here.parent.parent / "vnext-tools" / VOLUME_GUARD,
                  here.parent.parent / "vnext" / "prototype" / VOLUME_GUARD]
    try:   # корень контура — четвёртый кандидат; не найден — не беда, три прежних уже названы
        candidates.append(mezo_paths.container_root(__file__) / "vnext-tools" / VOLUME_GUARD)
    except SystemExit:
        pass
    file = next((c for c in candidates if c.exists()), candidates[0])
    if not file.exists():
        return None, f"файла нет: {file.name} (искал рядом с инструментом и в vnext-tools)"
    try:
        spec = importlib.util.spec_from_file_location("guard_phoenix_volume_for_compact", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        limit = getattr(module, "LIMIT", None)
    except Exception as e:                    # noqa: BLE001 — причина важнее вида беды
        return None, f"{file.name} не прочитан ({type(e).__name__}: {e})"
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        return None, f"в {file.name} нет годного LIMIT (получено {limit!r})"
    return limit, file.name


def removal_order(rows):
    """Порядок ухода записей слоя hot. rows — (id, subject, body_chars, happened_at, alive, ord).

    ① снятые с хода · ② с часом, старшие первыми · ③ без часа, снизу раздела вверх
    (больший ord раньше). Внутри ① — тем же правилом: сперва с часом по возрасту, потом без часа
    снизу вверх. Возвращает список (запись, причина).
    """
    def key(row):
        return (row[3] is None, row[3] or "", -row[5])

    revoked = sorted((r for r in rows if r[4] != "active"), key=key)
    dated = sorted((r for r in rows if r[4] == "active" and r[3]), key=key)
    undated = sorted((r for r in rows if r[4] == "active" and not r[3]), key=key)
    out = [(r, "снята с хода") for r in revoked]
    out += [(r, f"старшая по часу: {r[3]}") for r in dated]
    out += [(r, f"без часа, место в разделе {r[5]}") for r in undated]
    return out


def compact(conn, role, section, actor, dry_run):
    """Сжатие слоя hot: записи уходят в warm, пока слой не уложится в порог раздела.

    Исходы: 0 — уложилось либо уносить нечего · 3 — унесено что можно, порог НЕ достигнут.
    Одна транзакция на весь вызов; текст записей и тело раздела не трогаются.
    """
    limit, source = volume_limit()
    if limit is None:
        sys.exit(f"⛔ ОТКАЗ: порог раздела не прочитан — {source}. Ничего не записано.\n"
                 "   Порога признаком не назвать: он читается из guard-phoenix-volume.py.")
    sections = [section] if section else [r[0] for r in conn.execute(
        "SELECT DISTINCT section FROM phoenix_records WHERE role=? ORDER BY section", (role,))]
    has_any = conn.execute(
        "SELECT 1 FROM phoenix_records WHERE role=?" + (" AND section=?" if section else ""),
        (role, section) if section else (role,)).fetchone()
    if not sections or not has_any:
        sys.exit(f"⛔ ОТКАЗ: у {role}" + (f"·{section}" if section else "") +
                 " записей нет — сжимать нечего. Разобрать: --section <раздел> --разобрать")
    print("=" * 96)
    print(f"СЖАТИЕ СЛОЯ hot у {role}" + (f"·{section}" if section else " (все разделы)") +
          ("  ⟨ХОЛОСТОЙ ПРОГОН⟩" if dry_run else ""))
    print("=" * 96)
    moved_total, chars_total, short = [], 0, False
    plan = []
    for sect in sections:
        rows = conn.execute(
            "SELECT id, subject, body_chars, happened_at, alive, ord FROM phoenix_records "
            "WHERE role=? AND section=? AND layer='hot' ORDER BY ord", (role, sect)).fetchall()
        before_chars, before_n = sum(r[2] for r in rows), len(rows)
        if before_chars <= limit:
            print(f"· {sect}: слой hot {before_n} записей, {before_chars} знаков при пороге "
                  f"{limit} ({source}) — уносить нечего")
            continue
        order = removal_order(rows)
        left, taken = before_chars, []
        # последняя по порядку ухода запись остаётся всегда
        for rec, why in order[:-1]:
            if left <= limit:
                break
            taken.append((rec, why))
            left -= rec[2]
        print(f"· {sect}: слой hot было {before_chars} знаков в {before_n} записях → стало "
              f"{left} в {before_n - len(taken)} · порог {limit} ({source})")
        for rec, why in taken:
            print(f"    #{rec[0]} · {rec[1]} · {rec[2]} знаков · hot → warm · {why}")
        if left > limit:
            short = True
            reason = ("в слое одна запись, и она сама больше порога" if before_n == 1 else
                      "унесены все записи, кроме последней по порядку ухода (она остаётся "
                      "всегда), и остаток всё равно больше порога")
            print(f"    ⚠️ порог НЕ достигнут: осталось {left} знаков при пороге {limit} — {reason}")
        plan += [(sect, rec) for rec, _w in taken]
        moved_total += [rec for rec, _w in taken]
        chars_total += sum(rec[2] for rec, _w in taken)
    print("-" * 96)
    print(f"ИТОГ ВЫЗОВА: унесено {len(moved_total)} записей, {chars_total} знаков (hot → warm)" +
          (" · порог достигнут не везде" if short else ""))
    if dry_run:
        print("⚪ ХОЛОСТОЙ ПРОГОН: база не тронута — это перечень того, что унесёт настоящий вызов")
    elif plan:
        conn.execute("BEGIN")
        for _sect, rec in plan:
            conn.execute("UPDATE phoenix_records SET layer='warm', "
                         "layer_moved_at=datetime('now'), layer_moved_by=? WHERE id=? AND role=?",
                         (actor, rec[0], role))
        conn.commit()
        print("✅ записано одной транзакцией; текст записей и тело разделов не менялись")
    return 3 if short else 0


def move_layer(conn, role, record_id, layer, actor, why):
    """Перенос одной записи рукой роли. Тот же слой — «менять нечего», код 0."""
    row = conn.execute("SELECT layer FROM phoenix_records WHERE id=? AND role=?",
                       (record_id, role)).fetchone()
    if not row:
        other = conn.execute("SELECT role FROM phoenix_records WHERE id=?", (record_id,)).fetchone()
        sys.exit(f"🔴 НЕ ПЕРЕНЕСЕНО: записи #{record_id} у роли {role} нет — " +
                 (f"она принадлежит роли {other[0]}, а чужую память не правят" if other
                  else "записи с таким номером нет вовсе"))
    if row[0] == layer:
        print(f"⚪ запись #{record_id}: уже в слое {layer} — менять нечего")
        return 0
    conn.execute("BEGIN")
    conn.execute("UPDATE phoenix_records SET layer=?, layer_moved_at=datetime('now'), "
                 "layer_moved_by=? WHERE id=? AND role=?", (layer, actor, record_id, role))
    conn.commit()
    print(f"✅ запись #{record_id}: слой {row[0]} → {layer}")
    if why:
        print(f"   причина (в печати; в базе не хранится): {why}")
    return 0


def rebuild(conn, role, section, actor):
    """Разобрать раздел ЗАНОВО после того, как тело изменилось, СОХРАНИВ ручные поля.

    ⚡ ЗАЧЕМ ЭТО ЕСТЬ — зазор нашёлся на первом же живом применении, через час после
    того, как разбор заработал. Роль сохраняет память КАЖДЫЙ ДЕНЬ; тело меняется, записи
    остаются от прежнего, и `--собрать` честно краснеет расхождением. А снять расхождение
    было нечем: повторный разбор ОТКАЗЫВАЕТ, защищая проставленные рукой поля.
    ⇒ Инструмент оказывался ОДНОРАЗОВЫМ: работал ровно до первого сохранения памяти.

    ⚖️ ЧТО ЗДЕСЬ ГЛАВНОЕ, И ЭТО НЕ ПЕРЕНОС ПОЛЕЙ, А ЕГО ЧЕСТНОСТЬ. Поля переезжают
    только на записи, чьё ТЕЛО СОВПАЛО ДОСЛОВНО. Там, где текст правился, поля НЕ
    угадываются — они теряются, и потеря печатается ЧИСЛОМ И ПОИМЁННО.
    Молча перенесённое «условие снятия» на изменившийся текст — это утверждение о том,
    чего никто не проверял; оно хуже пустоты, потому что выглядит проверенным.
    """
    r = conn.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                     (role, section)).fetchone()
    if not r:
        sys.exit(f"⛔ У роли {role} нет раздела «{section}»")
    body = r[0]
    layer_known = has_layer(conn)
    if not layer_known:
        print("⚪ поля СЛОЯ памяти у записей в этой базе нет — шаг схемы не сведён.")
        print("   Работаю без слоя; перенос по слоям в этой базе не действует.")
        # ⚠️ ПУТЬ ЗАМЕНЁН НА ОБРАЗЕЦ. В правке Э2 здесь стоял путь ЭТОЙ машины
        # (C:/guts/.atlas/…), а файл уезжает пакетом в чужие контуры, где его нет.
        # Форма <КОНТУР> — своя же в шапке этого файла, строка 33.
        print("   Свести: python <КОНТУР>/.mezosync/scripts/migrations/"
              "20261115-phoenix-records-layer.py")
    previous = conn.execute(
        "SELECT body, subject, happened_at, source, expiry_cond, alive, revoked_at, "
        "revoked_note" + (", layer" if layer_known else "") +
        " FROM phoenix_records WHERE role=? AND section=?",
        (role, section)).fetchall()
    if not previous:
        sys.exit(f"⛔ У {role}·{section} записей нет — это первый разбор, зови --разобрать")
    # ручные поля прежних записей, ключ — ТЕЛО дословно
    # ⚡ СЛОЙ ВХОДИТ В ЭТОТ ОТБОР НАРАВНЕ С ИСТОЧНИКОМ И СРОКОМ ГОДНОСТИ (карточка #781, Э2).
    # Прежде условие знало только источник, срок и снятие с хода — и запись, у которой есть
    # ТОЛЬКО слой, в отбор не попадала ВОВСЕ. Её слой при правке текста уходил в значение
    # по умолчанию МОЛЧА: ни переноса, ни строки о потере. Это и есть класс, ради которого
    # этап заведён: поле исчезает без признака, а счёт потерь о нём не знает.
    had_fields = {}
    for row in previous:
        rec_body, subj, when, src, cond, alive, rev_at, rev_note = row[:8]
        layer = row[8] if layer_known else LAYER_DEFAULT
        if src or cond or alive != "active" or layer != LAYER_DEFAULT:
            had_fields[rec_body] = (subj, when, src, cond, alive, rev_at, rev_note, layer)

    chunks, method = _ma.блоки(body)
    today = datetime.datetime.now(datetime.UTC).date()
    new_bodies = {chunk["тело"] for chunk in chunks}
    orphaned = [rec_body for rec_body in had_fields if rec_body not in new_bodies]

    print("=" * 88)
    print(f"ПЕРЕСБОРКА {role}·{section}: {len(previous)} записей → {len(chunks)}")
    print(f"РЕЗАНО: {method}")
    print("=" * 88)

    conn.execute("BEGIN")
    # ⚡ АДРЕС ЗАПИСИ ДЕРЖИТСЯ ЗА ЕЁ ТЕЛО, А НЕ ЗА ПОРЯДОК. Здесь стояло DELETE всех
    # записей раздела и вставка заново — и номера ПЕРЕИСПОЛЬЗОВАЛИСЬ (id без
    # AUTOINCREMENT выдаётся как max+1). Правка тела ВЫШЕ по тексту сдвигала все записи
    # на единицу, и обращение по прежнему номеру молча попадало в СОСЕДНЮЮ запись —
    # с зелёным ответом.
    # 🩸 Найдено @TAXO опытом на копии (задача #532, 04.09 19:00 UTC). Опасно потому,
    # что инструмент САМ печатает «--поля <id>»: роль смотрит список → сохраняет память
    # (ежедневно) → проставляет условие снятия ЧУЖОЙ записи и получает ✅.
    # ⚖️ И почему это не ловилось проверкой: у @TAXO дважды подряд номера НЕ менялись —
    # её записи лежали последними в таблице. ⇒ ПРИЗНАК УСТОЙЧИВОСТИ УПРАВЛЯЛСЯ ЧУЖИМИ
    # ДЕЙСТВИЯМИ: стои́т другой роли записать между двумя вызовами — и номера уедут.
    # 👉 Чиним ПРИЧИНУ: запись, чьё тело совпало дословно, СОХРАНЯЕТ свой номер
    # (обновляются только порядок и длина источника). Новые куски вставляются, исчезнувшие
    # удаляются. Тогда правка выше по тексту не трогает адреса неизменённых записей.
    previous_by_body = {}
    for row in conn.execute(
            "SELECT id, body FROM phoenix_records WHERE role=? AND section=?",
            (role, section)):
        previous_by_body.setdefault(row[1], []).append(row[0])

    fields_kept, ids_kept, new_count = 0, 0, 0
    used_ids = set()
    for n, chunk in enumerate(chunks, 1):
        free_ids = previous_by_body.get(chunk["тело"], [])
        old_id = next((i for i in free_ids if i not in used_ids), None)
        manual_fields = had_fields.get(chunk["тело"])
        if manual_fields:
            subj, when, src, cond, alive, rev_at, rev_note, layer = manual_fields
            fields_kept += 1
        else:
            subj, when, src, cond, alive, rev_at, rev_note, layer = (
                subject_of_block(chunk["тело"]), time_of_block(chunk["тело"], today),
                None, None, "active", None, None, LAYER_DEFAULT)
        if old_id is not None:
            used_ids.add(old_id)
            ids_kept += 1
            # ⚖️ СЛОЯ В ЭТОМ ОБНОВЛЕНИИ НЕТ НАМЕРЕННО, И ЭТО НЕ ЗАБЫВЧИВОСТЬ.
            # Запись найдена по НОМЕРУ, и слой уже лежит на этой самой строке — не трогая
            # его, мы сохраняем его ТОЧНО. А перенос из отбора ручных полей ключуется ТЕЛОМ,
            # и у двух записей с дословно одинаковыми телами он мог бы их перепутать.
            # Правило: что можно сохранить по номеру — сохраняем по номеру, не по телу.
            conn.execute(
                "UPDATE phoenix_records SET subject=?, body_chars=?, happened_at=?, "
                "source=?, expiry_cond=?, alive=?, revoked_at=?, revoked_note=?, "
                "ord=?, origin_chars=? WHERE id=?",
                (subj, chunk["знаков"], when, src, cond, alive, rev_at, rev_note, n, len(body),
                 old_id))
        else:
            new_count += 1
            # у новой записи слой ставится явно — чтобы редкий случай «тел-двойников
            # больше, чем свободных номеров» не уронил слой в значение по умолчанию молча
            conn.execute(
                "INSERT INTO phoenix_records (role, section, subject, body, body_chars, "
                "happened_at, source, expiry_cond, alive, revoked_at, revoked_note, "
                "ord, origin_chars, created_by" + (", layer" if layer_known else "") +
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?" + (",?" if layer_known else "") + ")",
                (role, section, subj, chunk["тело"], chunk["знаков"], when, src, cond, alive, rev_at,
                 rev_note, n, len(body), actor) + ((layer,) if layer_known else ()))
    # исчезнувшие: их тела больше нет в разделе
    all_previous_ids = {i for id_list in previous_by_body.values() for i in id_list}
    to_remove = all_previous_ids - used_ids
    for i in to_remove:
        conn.execute("DELETE FROM phoenix_records WHERE id=?", (i,))
    conn.commit()

    assembled = "".join(chunk["тело"] for chunk in chunks)
    print(f"  🔗 НОМЕРА СОХРАНЕНЫ у {ids_kept} записей · новых {new_count} · "
          f"удалено {len(to_remove)}")
    print("     ⚖️ номер держится за ТЕЛО: правка выше по тексту больше не сдвигает")
    print("        адреса неизменённых записей (задача #532, находка @TAXO)")
    # ⚖️ СТРОКА ОБЯЗАНА РАЗЛИЧАТЬ «ПЕРЕНОСИТЬ БЫЛО НЕЧЕГО» И «НИЧЕГО НЕ СОВПАЛО».
    # Прежде обе давали «уцелели у 0» — одинаково при исправной работе роли без ручных
    # полей и при полном несовпадении границ (пункт ④ задачи #532).
    had_fields_count = len(had_fields)
    if not had_fields_count:
        print("  ⚪ ручных полей не было ни у одной записи — переносить было НЕЧЕГО")
        print("     (это не то же, что «ничего не совпало»: там поля были и пропали)")
    else:
        print(f"  ✅ ручные поля уцелели у {fields_kept} из {had_fields_count} записей, "
              f"что их несли (тело совпало дословно)")
    if orphaned:
        # ⛔ ПОТЕРЯ НАЗЫВАЕТСЯ ПОИМЁННО, А НЕ ЧИСЛОМ: число сообщает, что что-то пропало,
        # имя — ЧТО ИМЕННО переставить рукой. Без имён роль не знает, куда смотреть.
        print(f"  ⚠️ ПОЛЯ ПОТЕРЯНЫ у {len(orphaned)} записей — их текст изменился, "
              f"и переносить поля было бы утверждением о непроверенном:")
        layers_lost = 0
        for rec_body in orphaned:
            first_line = rec_body.strip().splitlines()[0] if rec_body.strip() else ""
            lost_layer = had_fields[rec_body][7]
            mark = ""
            if lost_layer != LAYER_DEFAULT:
                layers_lost += 1
                mark = f"  [слой был: {lost_layer}]"
            print(f"       🔸 «{first_line[:70]}»{mark}")
        print("     👉 проставь заново: --поля <id> --источник … --условие …")
        if layers_lost:
            # ⚡ СЛОЙ НАЗЫВАЕТСЯ ОТДЕЛЬНОЙ СТРОКОЙ, А НЕ ТОНЕТ В ОБЩЕМ ЧИСЛЕ ПОЛЕЙ:
            # он один решает, читается запись при пробуждении или нет. Потеряв его молча,
            # роль получила бы обратно в живой слой то, что сама оттуда унесла.
            print(f"     ⚠️ из них СЛОЙ ПАМЯТИ потерян у {layers_lost} записей — они вернулись "
                  f"в живой слой «{LAYER_DEFAULT}». Перенеси заново, если унос был намеренным")
    else:
        print("  ✅ осиротевших полей нет — ни одна запись с полями не изменилась")
    print(f"  сборка: {len(assembled)} = тело {len(body)}  "
          f"{'✅ сходится знак в знак' if assembled == body else '🔴 РАСХОЖДЕНИЕ'}")
    return 0 if assembled == body else 1


def parse(conn, role, section, actor):
    r = conn.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                     (role, section)).fetchone()
    if not r:
        sys.exit(f"⛔ У роли {role} нет раздела «{section}»")
    body = r[0]
    existing_count = conn.execute(
        "SELECT COUNT(*) FROM phoenix_records WHERE role=? AND section=?",
        (role, section)).fetchone()[0]
    if existing_count:
        # ⚖️ ОТКАЗ, А НЕ ПЕРЕЗАПИСЬ. Повторный разбор затёр бы поля, проставленные рукой
        # (источник, условие снятия) — то есть самую дорогую часть работы. Молчаливая
        # потеря ручного труда хуже отказа: она выглядит успехом.
        sys.exit(f"⛔ НЕ РАЗОБРАНО: у {role}·{section} уже {existing_count} записей. Повторный "
                 "разбор затёр бы поля, проставленные рукой.\n"
                 "   👉 ТЕЛО ИЗМЕНИЛОСЬ — обычное дело после сохранения памяти? "
                 "зови --пересобрать:\n"
                 "      разберёт заново и ПЕРЕНЕСЁТ ручные поля на записи, чьё тело "
                 "совпало дословно,\n"
                 "      а те, у кого текст правился, назовёт ПОИМЁННО — их проставишь "
                 "заново.\n"
                 "   Посмотреть: --показать · снять запись: --снять <id> · "
                 "дописать поля: --поля <id>")
    chunks, method = _ma.блоки(body)
    today = datetime.datetime.now(datetime.UTC).date()
    print("=" * 84)
    print(f"РАЗБОР {role}·{section}: {len(body)} знаков → {len(chunks)} записей")
    print(f"РЕЗАНО: {method}")
    print("=" * 84)
    conn.execute("BEGIN")
    total = 0
    subject_counts = {}
    for n, chunk in enumerate(chunks, 1):
        subj = subject_of_block(chunk["тело"])
        when = time_of_block(chunk["тело"], today)
        subject_counts[subj] = subject_counts.get(subj, 0) + 1
        total += chunk["знаков"]
        conn.execute(
            "INSERT INTO phoenix_records (role, section, subject, body, body_chars, "
            "happened_at, source, expiry_cond, alive, ord, origin_chars, created_by) "
            "VALUES (?,?,?,?,?,?,?,?,'active',?,?,?)",
            (role, section, subj, chunk["тело"], chunk["знаков"], when, None, None, n, len(body), actor))
        print(f"  {n:3}. {subj:12} {chunk['знаков']:>6}б  {when or 'часа нет':10}  {chunk['тема'][:44]}")
    conn.commit()
    print("-" * 84)
    print(f"предметы: " + " · ".join(f"{k} {v}" for k, v in sorted(subject_counts.items())))
    print(f"сумма знаков записей {total} · длина тела {len(body)} · "
          f"{'✅ сходится' if total == len(body) else '🔴 РАСХОЖДЕНИЕ ' + str(len(body)-total)}")
    print("⚠️ ПОЛЯ «источник» и «условие снятия» ПУСТЫ у всех записей — их не из чего")
    print("   вывести из сплошного текста. Это не недоделка, а честное состояние:")
    print("   пустота ОТЛИЧИМА запросом (--отобрать без-условия) и не молчит.")
    print("👉 дописать рукой: --поля <id> --источник «…» --условие «…» --предмет «…»")


# Особое значение поля «условие снятия»: решено, что условия нет вовсе (замер о прошлом,
# надгробие, провенанс). ⛔ Пишется ВМЕСТЕ С ПРИЧИНОЙ — «никогда: ...», иначе это отписка,
# неотличимая от нерешённого.
NO_CONDITION = "никогда"


def show(conn, role, layer=None):
    layer_known = has_layer(conn)
    rows = conn.execute(
        "SELECT id, section, subject, body_chars, COALESCE(happened_at,'—'), "
        "COALESCE(source,'—'), COALESCE(expiry_cond,'—'), alive, "
        "substr(replace(body, char(10), ' '), 1, 52), body"
        + (", layer" if layer_known else "") +
        " FROM phoenix_records WHERE role=?" + (" AND layer=?" if layer else "") +
        " ORDER BY section, ord", (role, layer) if layer else (role,)).fetchall()
    if not rows and layer:
        print(f"⚪ у роли {role} записей в слое {layer} нет")
        return
    if not rows:
        print(f"⚪ у роли {role} записей нет. Разобрать раздел: "
              f"--section <раздел> --разобрать")
        return
    summary = conn.execute(
        "SELECT COUNT(*), SUM(body_chars), SUM(alive='revoked'), "
        "SUM(source IS NULL), SUM(expiry_cond IS NULL), "
        f"SUM(expiry_cond LIKE '{NO_CONDITION}%') "
        "FROM phoenix_records WHERE role=?", (role,)).fetchone()
    decided_none, total = summary[5] or 0, summary[0]
    with_condition = total - (summary[4] or 0) - decided_none
    print("=" * 100)
    print(f"ПАМЯТЬ {role} ЗАПИСЯМИ: {total} записей · {summary[1]} знаков · "
          f"снятых {summary[2]}")
    print(f"  без источника: {summary[3]}")
    # ⚡ ТРИ СОСТОЯНИЯ У ПОЛЯ «УСЛОВИЕ СНЯТИЯ», А НЕ ДВА. Сложи «не решено» с «условия
    # нет по природе записи» — и счётчик НИКОГДА не дойдёт до нуля: у замера о прошлом
    # условия устаревания не бывает вовсе. А вечно ненулевой счётчик перестают смотреть,
    # и поле снова замолкает — ровно то, против чего заведён критерий ⑥ карточки #524.
    print(f"  условие снятия: назначено {with_condition} · "
          f"решено «условия нет» {decided_none} · ⚠️ НЕ РЕШЕНО {summary[4]}")
    print("=" * 100)
    print(f"{'id':>4} {'раздел':9} {'предмет':12} {'знаков':>7} {'час':11} "
          f"{'жив':4} " + (f"{'слой':9} " if layer_known else "") + "начало")
    print("-" * 100)
    disputed, manual = 0, 0
    for id_, sect, subj, chars, when, src, cond, alive, started, body, *layer_cell in rows:
        mark = "✅" if alive == "active" else "⚰️"
        # ⚖️ СПОР ПЕЧАТАЕТСЯ, А НЕ ГЛОТАЕТСЯ (карточка #534). Предмет, назначенный не по
        # примете (рукой через --поля или прежним правилом), помечен ✍ и споров не несёт:
        # у него уже есть автор. Различаю по расхождению с тем, что дала бы примета.
        by_hint, dispute = subject_and_dispute(body)
        if subj != by_hint:
            tag, manual = "✍", manual + 1
        elif dispute:
            tag, disputed = "?", disputed + 1
        else:
            tag = ""
        print(f"{id_:>4} {sect:9} {(subj + tag):12} {chars:>7} {when:11} {mark:4} "
              + (f"{layer_cell[0]:9} " if layer_cell else "") + started)
        if tag == "?":
            print(f"{'':4} {'':9} └ спор: {dispute}")
    print("-" * 100)
    if disputed or manual:
        print(f"⚖️ предмет: споров {disputed} (помечены «?», соперник назван строкой ниже) · "
              f"назначен рукой или прежним правилом {manual} («✍»)")
        print("   спор — это НЕ ошибка, это честное «по словам не решить»; реши --поля <id> --предмет")
    print("👉 отобрать: --отобрать <предмет|слово> · за день: --за 2026-09-04 · "
          "снятые: --снятые · НЕ решено про условие: --без-условия")
    print(f"👉 проставить: --поля <id> --источник <чем добыто> --условие <при чём снимается>")
    print(f"   у записи, которой условие не положено (замер о прошлом, надгробие,")
    print(f"   провенанс), условие пишется словом «{NO_CONDITION}: <почему>» — "
          f"это РЕШЕНИЕ, а не пустота")


def _fold(text):
    """Свернуть регистр СРЕДСТВАМИ PYTHON, а не базы.

    ⚖️ ПОЧЕМУ НЕ lower() БАЗЫ. Встроенные функции регистра SQLite работают только
    с латиницей: lower('ПЕРИСКОП') возвращает 'ПЕРИСКОП' БЕЗ ИЗМЕНЕНИЯ, и отбор
    по русскому слову в другом написании МОЛЧА давал ноль. Перемерено 2026-11-15
    16:36 UTC на SQLite 3.50.4; на моих же записях «владелец» → 10, «ВЛАДЕЛЕЦ» → 0,
    и код выхода у обоих был 0. Нашла COORD, карточка #784.
    ⛔ ЧЕГО ЭТА ФУНКЦИЯ НЕ ДЕЛАЕТ, и инструмент говорит это вслух при нуле находок:
    не сближает «ё» с «е» и «й» с «и» — это РАЗНЫЕ буквы; не ловит латинскую букву
    внутри русского слова («budить» вместо «будить»). Оба вида — отдельные предметы
    той же карточки, и молчать о них нельзя: роль прочтёт «не нашлось» как «такого нет».
    """
    return (text or "").casefold()


def select(conn, role, query=None, on_date=None, revoked=False, no_condition=False,
             full=False, layer=None):
    clauses, params = ["role=?"], [role]
    heading = []
    layer_known = has_layer(conn)
    if layer:
        clauses.append("layer=?")
        params.append(layer)
        heading.append(f"слой {layer}")
    if query:
        # регистр сворачивает Python, а не база: см. _fold и карточку #784
        conn.create_function("fold", 1, _fold, deterministic=True)
        clauses.append("(fold(subject) LIKE fold(?) OR fold(body) LIKE fold(?))")
        params += [f"%{query}%", f"%{query}%"]
        heading.append(f"предмет или слово «{query}»")
        # ⚖️ Запись, у которой «{что}» — ПРОИГРАВШИЙ соперник спора, в выборку тоже
        # попадает: слово-примета лежит в её теле, и второе условие её берёт. Это не
        # случайность, а то, ради чего спор вообще считается по словам тела.
    if on_date:
        clauses.append("happened_at=?")
        params.append(on_date)
        heading.append(f"час события {on_date}")
    if revoked:
        clauses.append("alive='revoked'")
        heading.append("только снятые")
    if no_condition:
        clauses.append("expiry_cond IS NULL")
        heading.append("без условия снятия")
    rows = conn.execute(
        "SELECT id, section, subject, body_chars, COALESCE(happened_at,'—'), alive, "
        "COALESCE(source,'—'), COALESCE(expiry_cond,'—'), body"
        + (", layer" if layer_known else "") + " FROM phoenix_records "
        f"WHERE {' AND '.join(clauses)} ORDER BY section, ord", params).fetchall()
    print("=" * 96)
    print(f"ОТБОР по памяти {role}: {' · '.join(heading) or 'всё'} → записей {len(rows)}")
    print("=" * 96)
    if not rows:
        # ⚖️ Пустой ответ обязан отличать «не нашлось» от «искать негде»: одно «ничего»
        # на две беды заставляет спрашивающего гадать, и гадает он неверно.
        total = conn.execute("SELECT COUNT(*) FROM phoenix_records WHERE role=?",
                             (role,)).fetchone()[0]
        if not total:
            print(f"⚪ записей у роли {role} НЕТ ВОВСЕ — память на записи не разобрана,")
            print(f"   то есть искать было НЕГДЕ. Разобрать: --role {role} "
                  f"--section <раздел> --разобрать")
            return 3
        # ⛔ ПРИЧИНУ НУЛЯ ЗДЕСЬ НЕ НАЗЫВАЕМ, И ЭТО НЕ СКУПОСТЬ НА СЛОВА.
        # Прежде стояло «значит под отбор ничего не подошло» — вывод о ПРЕДМЕТЕ,
        # сделанный из собственного молчания. Пока регистр сворачивала база, строка
        # была прямой ложью: русское слово в другом написании давало ноль, а инструмент
        # УВЕРЕННО объявлял, что искать было нечего. Поэтому говорим, что отбор сделал
        # и чего он не умеет, а вывод оставляем спрашивающему.
        print(f"⚪ совпадений нет. Записи у роли {role} ЕСТЬ ({total}) — "
              f"под этот отбор не подошла ни одна")
        print("   чем свёрнут регистр: средствами Python ⇒ «ВЛАДЕЛЕЦ» и «владелец» "
              "для отбора одно и то же")
        print("   ⛔ чего отбор НЕ умеет: «ё» и «е» — РАЗНЫЕ буквы (как «й» и «и»); "
              "латинская буква внутри русского слова («budить») не ловится ничем")
        print("   👉 то же слово в архиве роли: memory-archive.py --role <РОЛЬ> "
              "--find <слово>")
        return 2
    # ⚖️ ОТВЕТ — СПИСОК ЗАПИСЕЙ, А НЕ ПОТОК ТЕКСТА. Ровно затем задача и заводилась:
    # владелец спрашивает «покажи всё про права» ЧТОБЫ НЕ ЧИТАТЬ двадцать тысяч знаков.
    # Отбор, отвечающий телами, возвращает его в ту же беду, только с фильтром
    # (критерий ② карточки #524 говорит дословно: «списком записей, а не куском текста»).
    # Тело — по --целиком, и это ВТОРОЙ ход, сделанный осознанно.
    if not full:
        print(f"{'id':>4} {'раздел':9} {'предмет':11} {'знаков':>7} {'час':11} "
              f"{'жив':9} {'усл':4} " + (f"{'слой':9} " if layer_known else "") + "начало")
        print("-" * 96)
        for id_, sect, subj, chars, when, alive, src, cond, body, *layer_cell in rows:
            mark = "✅" if alive == "active" else "⚰️СНЯТА"
            cond_flag = "—" if cond == "—" else ("нет" if cond.startswith(NO_CONDITION) else "да")
            first_line = body.strip().splitlines()[0] if body.strip() else ""
            print(f"{id_:>4} {sect:9} {subj:11} {chars:>7} {when:11} {mark:9} {cond_flag:4} "
                  + (f"{layer_cell[0]:9} " if layer_cell else "") + first_line[:40])
        print("-" * 96)
        # ⚖️ ВОПРОС ВЛАДЕЛЬЦА ЗВУЧИТ «ЧТО СНЯТО И ЧЕМ» — ДВЕ ПОЛОВИНЫ, И ВТОРАЯ ДОРОЖЕ.
        # Список, отвечающий только первой, оставляет снятое без причины: а снятое без
        # причины неотличимо от потерянного, и через месяц никто не скажет, отзывали
        # запись или она пропала. Потому «чем» печатается ЦЕЛИКОМ, без усечения.
        revoked_rows = [line_ for line_ in rows if line_[5] != "active"]
        if revoked_rows:
            print(f"⚰️ СНЯТЫХ В ЭТОМ ОТБОРЕ: {len(revoked_rows)} — чем снята каждая:")
            for id_, *_ in revoked_rows:
                when_, why_ = conn.execute(
                    "SELECT COALESCE(revoked_at,'—'), COALESCE(revoked_note,'—') "
                    "FROM phoenix_records WHERE id=?", (id_,)).fetchone()
                print(f"\n   ⚰️ #{id_} · снята {when_} UTC")
                for line_ in why_.splitlines():
                    print(f"      {line_}")
            print("-" * 96)
        print("👉 тела записей целиком — тем же отбором с ключом --целиком")
        return 0
    for id_, sect, subj, chars, when, alive, src, cond, body, *layer_cell in rows:
        mark = "✅" if alive == "active" else "⚰️ СНЯТА"
        print(f"\n📄 #{id_} · {sect} · предмет «{subj}» · {chars}б · час {when} · {mark}"
              + (f" · слой {layer_cell[0]}" if layer_cell else ""))
        print(f"   источник: {src}")
        print(f"   условие снятия: {cond}")
        print("   " + "─" * 88)
        for line_ in body.splitlines():
            print(f"   {line_}")
    return 0


def assemble(conn, role, section):
    """Сложить записи обратно в сплошное тело и СВЕРИТЬ с живым (критерий ④)."""
    rows = conn.execute(
        "SELECT body FROM phoenix_records WHERE role=? AND section=? ORDER BY ord",
        (role, section)).fetchall()
    if not rows:
        sys.exit(f"⛔ У {role}·{section} записей нет — собирать нечего")
    assembled = "".join(r[0] for r in rows)
    live_body = conn.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                         (role, section)).fetchone()
    live_body = live_body[0] if live_body else ""
    print("=" * 84)
    print(f"СБОРКА {role}·{section} ИЗ ЗАПИСЕЙ — встречный критерий карточки #524 ④")
    print("=" * 84)
    print(f"  записей .......... {len(rows)}")
    print(f"  собрано знаков ... {len(assembled)}")
    print(f"  живое тело ....... {len(live_body)}")
    if assembled == live_body:
        print("  ✅ СОВПАДАЕТ ЗНАК В ЗНАК — из записей собирается ровно прежнее тело,")
        print("     значит откат к сплошному тексту возможен в любой момент")
        return 0
    print("  🔴 РАСХОЖДЕНИЕ — слои разошлись. Это не мелочь: значит одно из двух мест")
    print("     изменилось без другого, и дальше они будут спорить молча.")
    n = min(len(assembled), len(live_body))
    i = next((k for k in range(n) if assembled[k] != live_body[k]), n)
    print(f"     первое различие на знаке {i}:")
    print(f"       записи: {assembled[max(0,i-40):i+40]!r}")
    print(f"       тело:   {live_body[max(0,i-40):i+40]!r}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--role", required=True)
    ap.add_argument("--section")
    ap.add_argument("--parse", "--разобрать", dest="parse", action="store_true")
    ap.add_argument("--rebuild", "--пересобрать", dest="rebuild", action="store_true",
                    help="разобрать заново после правки тела, сохранив ручные поля")
    ap.add_argument("--show", "--показать", dest="show", action="store_true")
    ap.add_argument("--select", "--отобрать", dest="select", metavar="СЛОВО")
    ap.add_argument("--on-date", "--за", dest="on_date", metavar="ГГГГ-ММ-ДД")
    ap.add_argument("--revoked", "--снятые", dest="revoked", action="store_true")
    ap.add_argument("--no-condition", "--без-условия", dest="no_condition", action="store_true")
    ap.add_argument("--full", "--целиком", dest="full", action="store_true",
                    help="печатать тела записей, а не список")
    ap.add_argument("--assemble", "--собрать", dest="assemble", action="store_true")
    ap.add_argument("--revoke", "--снять", dest="revoke", type=int, metavar="ID")
    ap.add_argument("--why", "--чем", dest="why", help="чем снята запись (для --revoke)")
    ap.add_argument("--fields", "--поля", dest="fields", type=int, metavar="ID")
    ap.add_argument("--source", "--источник", dest="source")
    ap.add_argument("--condition", "--условие", dest="condition")
    ap.add_argument("--subject", "--предмет", dest="subject")
    ap.add_argument("--compact", "--сжать", dest="compact", action="store_true",
                    help="унести записи слоя hot в warm, пока слой не уложится в порог раздела "
                         "(порог читается из guard-phoenix-volume.py и признаком не задаётся)")
    ap.add_argument("--dry-run", "--вхолостую", dest="dry_run", action="store_true",
                    help="с --сжать: показать перечень и ничего не записывать")
    ap.add_argument("--move", "--перенести", dest="move", type=int, metavar="ID",
                    help="перенести одну запись в слой, названный ключом --layer")
    ap.add_argument("--layer", "--слой", dest="layer", choices=LAYERS,
                    help="слой: цель для --move; отбор для --show и --select")
    a = ap.parse_args()

    db = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    conn = sqlite3.connect(str(db))
    if not has_table(conn):
        step = mezo_paths.live_scripts(__file__) / "migrations" / "20260904-phoenix-records.py"
        sys.exit("⛔ В этой базе нет записей памяти. Накати шаг:\n"
                 f"   python {step.as_posix()}")

    role = a.role.upper()
    env_actor = (os.environ.get("MEZO_ROLE") or "").strip().upper()
    # ⚖️ Рука берётся из среды, а не из флага: запрет, обходимый забытым флагом,
    # защищает только добросовестного (оплачено на соседнем инструменте 04.09).
    actor = env_actor

    # ⚡ КАРТОЧКА #600 (найдено контуром AIA, подтверждено в нашем коде): --пересобрать
    # ЗДЕСЬ НЕ СЧИТАЛСЯ пишущей операцией и обходил проверку «роль правит СВОЮ память
    # сама» — чужая роль могла пересобрать разбор чужого раздела, не назвавшись.
    is_write = a.parse or a.rebuild or a.revoke or a.fields or a.compact or a.move is not None
    if is_write:
        if not actor:
            sys.exit("⛔ НЕ ЗНАЮ, ЧЬЯ РУКА. Назовись: MEZO_ROLE=<ТВОЯ РОЛЬ>")
        if actor != role:
            sys.exit(f"⛔ ОТКАЗ: {actor} правит память роли {role}. Роль разбирает СВОЮ "
                     "память сама (слово владельца 2026-09-04 13:41 UTC).\n"
                     "   Смотреть и отбирать чужую можно: --показать · --отобрать")

    if a.compact and a.move is not None:
        sys.exit("⛔ --сжать и --перенести — два разных вызова, вместе не зовутся")
    if a.compact:
        if a.layer:
            sys.exit("⛔ --слой не сочетается с --сжать: сжатие само уносит hot → warm")
        if not has_layer(conn):
            refuse_no_layer("сжатие")
        return compact(conn, role, a.section, actor, a.dry_run)
    if a.move is not None:
        if not a.layer:
            sys.exit("⛔ --перенести называет запись, а КУДА — ключ --слой {hot,warm,permanent}")
        if not has_layer(conn):
            refuse_no_layer("перенос по слоям")
        return move_layer(conn, role, a.move, a.layer, actor, a.why)
    if a.dry_run:
        sys.exit("⛔ --dry-run работает только с --сжать")
    if a.layer and not has_layer(conn):
        refuse_no_layer("отбор по слою")
    if a.rebuild:
        if not a.section:
            sys.exit("⛔ нужен --section")
        return rebuild(conn, role, a.section, actor)
    if a.parse:
        if not a.section:
            sys.exit("⛔ нужен --section")
        parse(conn, role, a.section, actor)
        return 0
    if a.revoke is not None:
        cur = conn.execute("UPDATE phoenix_records SET alive='revoked', "
                           "revoked_at=datetime('now'), revoked_note=? "
                           "WHERE id=? AND role=?",
                           (a.why or "снято рукой роли", a.revoke, role))
        # ⚡ НЕ ТРОНУТО ≠ СДЕЛАНО. Без этой проверки чужой или несуществующий номер даёт
        # зелёную строку и ноль изменений: молчащий отказ читается как успех, и роль
        # уходит уверенная, что запись снята. Отвечает ПОИМЁННО, чем именно не сошлось.
        if cur.rowcount == 0:
            existing = conn.execute("SELECT role FROM phoenix_records WHERE id=?",
                                (a.revoke,)).fetchone()
            conn.rollback()
            sys.exit(f"🔴 НЕ СНЯТО: записи #{a.revoke} у роли {role} нет — " +
                     (f"она принадлежит роли {existing[0]}, а чужую память не правят "
                      f"(слово владельца 2026-09-04 13:41 UTC)" if existing
                      else "записи с таким номером нет вовсе"))
        conn.commit()
        print(f"⚰️ запись #{a.revoke} помечена снятой. Тело НЕ удалено: снятое читается "
              "отбором --снятые, потому что «чем снято» дороже самого снятия")
        return 0
    if a.fields is not None:
        updates, values = [], []
        for attr_name, column in (("source", "source"), ("condition", "expiry_cond"),
                             ("subject", "subject")):
            v = getattr(a, attr_name, None)
            if v:
                updates.append(f"{column}=?")
                values.append(v)
        if not updates:
            sys.exit("⛔ нечего дописывать: назови --источник, --условие или --предмет")
        values += [a.fields, role]
        cur = conn.execute(f"UPDATE phoenix_records SET {', '.join(updates)} "
                           "WHERE id=? AND role=?", values)
        if cur.rowcount == 0:  # тот же класс, что и у --снять: см. комментарий выше
            existing = conn.execute("SELECT role FROM phoenix_records WHERE id=?",
                                (a.fields,)).fetchone()
            conn.rollback()
            sys.exit(f"🔴 НЕ ДОПИСАНО: записи #{a.fields} у роли {role} нет — " +
                     (f"она принадлежит роли {existing[0]}, а чужую память не правят "
                      f"(слово владельца 2026-09-04 13:41 UTC)" if existing
                      else "записи с таким номером нет вовсе"))
        conn.commit()
        print(f"✅ запись #{a.fields}: дописано полей {len(updates)}")
        return 0
    if a.assemble:
        if not a.section:
            sys.exit("⛔ нужен --section")
        return assemble(conn, role, a.section)
    if a.select or a.on_date or a.revoked or a.no_condition:
        # исход отбора НЕСЁТСЯ кодом выхода: нашлось 0 · не нашлось при живых
        # записях 2 · записей нет вовсе 3 (карточка #784, критерий ④)
        return select(conn, role, a.select, a.on_date, a.revoked, a.no_condition, a.full,
                      a.layer)
    show(conn, role, a.layer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
