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
    previous = conn.execute(
        "SELECT body, subject, happened_at, source, expiry_cond, alive, revoked_at, "
        "revoked_note FROM phoenix_records WHERE role=? AND section=?",
        (role, section)).fetchall()
    if not previous:
        sys.exit(f"⛔ У {role}·{section} записей нет — это первый разбор, зови --разобрать")
    # ручные поля прежних записей, ключ — ТЕЛО дословно
    had_fields = {}
    for rec_body, subj, when, src, cond, alive, rev_at, rev_note in previous:
        if src or cond or alive != "active":
            had_fields[rec_body] = (subj, when, src, cond, alive, rev_at, rev_note)

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
            subj, when, src, cond, alive, rev_at, rev_note = manual_fields
            fields_kept += 1
        else:
            subj, when, src, cond, alive, rev_at, rev_note = (
                subject_of_block(chunk["тело"]), time_of_block(chunk["тело"], today),
                None, None, "active", None, None)
        if old_id is not None:
            used_ids.add(old_id)
            ids_kept += 1
            conn.execute(
                "UPDATE phoenix_records SET subject=?, body_chars=?, happened_at=?, "
                "source=?, expiry_cond=?, alive=?, revoked_at=?, revoked_note=?, "
                "ord=?, origin_chars=? WHERE id=?",
                (subj, chunk["знаков"], when, src, cond, alive, rev_at, rev_note, n, len(body),
                 old_id))
        else:
            new_count += 1
            conn.execute(
                "INSERT INTO phoenix_records (role, section, subject, body, body_chars, "
                "happened_at, source, expiry_cond, alive, revoked_at, revoked_note, "
                "ord, origin_chars, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (role, section, subj, chunk["тело"], chunk["знаков"], when, src, cond, alive, rev_at,
                 rev_note, n, len(body), actor))
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
        for rec_body in orphaned:
            first_line = rec_body.strip().splitlines()[0] if rec_body.strip() else ""
            print(f"       🔸 «{first_line[:70]}»")
        print("     👉 проставь заново: --поля <id> --источник … --условие …")
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


def show(conn, role):
    rows = conn.execute(
        "SELECT id, section, subject, body_chars, COALESCE(happened_at,'—'), "
        "COALESCE(source,'—'), COALESCE(expiry_cond,'—'), alive, "
        "substr(replace(body, char(10), ' '), 1, 52), body "
        "FROM phoenix_records WHERE role=? ORDER BY section, ord", (role,)).fetchall()
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
          f"{'жив':4} начало")
    print("-" * 100)
    disputed, manual = 0, 0
    for id_, sect, subj, chars, when, src, cond, alive, started, body in rows:
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
        print(f"{id_:>4} {sect:9} {(subj + tag):12} {chars:>7} {when:11} {mark:4} {started}")
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


def select(conn, role, query=None, on_date=None, revoked=False, no_condition=False,
             full=False):
    clauses, params = ["role=?"], [role]
    heading = []
    if query:
        clauses.append("(subject LIKE ? OR lower(body) LIKE lower(?))")
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
        "COALESCE(source,'—'), COALESCE(expiry_cond,'—'), body FROM phoenix_records "
        f"WHERE {' AND '.join(clauses)} ORDER BY section, ord", params).fetchall()
    print("=" * 96)
    print(f"ОТБОР по памяти {role}: {' · '.join(heading) or 'всё'} → записей {len(rows)}")
    print("=" * 96)
    if not rows:
        # ⚖️ Пустой ответ обязан отличать «не нашлось» от «искать негде»: одно «ничего»
        # на две беды заставляет спрашивающего гадать, и гадает он неверно.
        total = conn.execute("SELECT COUNT(*) FROM phoenix_records WHERE role=?",
                             (role,)).fetchone()[0]
        print(f"⚪ совпадений нет. Записей у роли {total} — "
              + ("значит под отбор ничего не подошло."
                 if total else "память ещё НЕ РАЗОБРАНА, то есть искать было негде."))
        return
    # ⚖️ ОТВЕТ — СПИСОК ЗАПИСЕЙ, А НЕ ПОТОК ТЕКСТА. Ровно затем задача и заводилась:
    # владелец спрашивает «покажи всё про права» ЧТОБЫ НЕ ЧИТАТЬ двадцать тысяч знаков.
    # Отбор, отвечающий телами, возвращает его в ту же беду, только с фильтром
    # (критерий ② карточки #524 говорит дословно: «списком записей, а не куском текста»).
    # Тело — по --целиком, и это ВТОРОЙ ход, сделанный осознанно.
    if not full:
        print(f"{'id':>4} {'раздел':9} {'предмет':11} {'знаков':>7} {'час':11} "
              f"{'жив':9} {'усл':4} начало")
        print("-" * 96)
        for id_, sect, subj, chars, when, alive, src, cond, body in rows:
            mark = "✅" if alive == "active" else "⚰️СНЯТА"
            cond_flag = "—" if cond == "—" else ("нет" if cond.startswith(NO_CONDITION) else "да")
            first_line = body.strip().splitlines()[0] if body.strip() else ""
            print(f"{id_:>4} {sect:9} {subj:11} {chars:>7} {when:11} {mark:9} {cond_flag:4} {first_line[:40]}")
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
        return
    for id_, sect, subj, chars, when, alive, src, cond, body in rows:
        mark = "✅" if alive == "active" else "⚰️ СНЯТА"
        print(f"\n📄 #{id_} · {sect} · предмет «{subj}» · {chars}б · час {when} · {mark}")
        print(f"   источник: {src}")
        print(f"   условие снятия: {cond}")
        print("   " + "─" * 88)
        for line_ in body.splitlines():
            print(f"   {line_}")


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
    is_write = a.parse or a.rebuild or a.revoke or a.fields
    if is_write:
        if not actor:
            sys.exit("⛔ НЕ ЗНАЮ, ЧЬЯ РУКА. Назовись: MEZO_ROLE=<ТВОЯ РОЛЬ>")
        if actor != role:
            sys.exit(f"⛔ ОТКАЗ: {actor} правит память роли {role}. Роль разбирает СВОЮ "
                     "память сама (слово владельца 2026-09-04 13:41 UTC).\n"
                     "   Смотреть и отбирать чужую можно: --показать · --отобрать")

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
        select(conn, role, a.select, a.on_date, a.revoked, a.no_condition, a.full)
        return 0
    show(conn, role)
    return 0


if __name__ == "__main__":
    sys.exit(main())
