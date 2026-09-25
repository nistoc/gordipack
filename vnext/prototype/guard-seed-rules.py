#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРОВЕРКА: свод правил в посеве не отстал от живого свода контура.

Повод — замер 20.08: из 39 правил посева дословно совпадало с живым ОДНО, и никто этого
не видел месяц. Причина невидимости названа отдельно, потому что она и есть главное:

  🪤 НОМЕР ВЕРСИИ В ПОСЕВЕ СТАВИТ ТОТ, КТО ПЕРЕНОСИТ, — о возрасте текста в живом своде он не говорит.
     По нему свежесть проверить НЕЛЬЗЯ, а выглядит он как обычная версия — и потому
     молча отвечает «всё в порядке» на вопрос, который ему не задавали.

⚖️ СЛИЧАЕМ ТЕМ ЖЕ СПОСОБОМ, КАКИМ ПРАВИЛА ПОПАДАЮТ В БАЗУ: файл посева применяется
   к чистой базе целиком. Читать его построчно нельзя — один ключ может встречаться
   несколько раз, и в базу попадает ПОСЛЕДНЕЕ определение. Разбор образцом поиска здесь
   отвечал бы про другую редакцию, чем получит новый контур.

ТРИ РАЗНЫХ ИСХОДА, И ИХ НЕЛЬЗЯ СЛИВАТЬ:
  🔴 живое правило менялось ПОСЛЕ догона — посмотреть, не унесло ли оно урок;
  🟡 посев БОГАЧЕ живого — НЕ долг: копировать живое поверх значило бы ухудшить шаблон;
  ⚪ правила нет в посеве вовсе — решение человека: общее оно или про ваш продукт.
     Механизм этого не знает и не притворяется, что знает.

Зовут так:
    python <КОНТУР>/vnext-tools/guard-seed-rules.py
    python <КОНТУР>/vnext-tools/guard-seed-rules.py --show <ключ>   # тела рядом
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

# 🪤 ПЕРВАЯ РЕДАКЦИЯ СУДИЛА ПО ДЛИНЕ — и была неправа по существу: посев КОРОЧЕ живого
# НАМЕРЕННО, из него убраны случаи контура-донора. По длине выходило «отстали 30» сразу
# после честного догона: проверка кричала на саму починку.
# ⚖️ Честный признак отставания — ВРЕМЯ: правило, изменённое в живом своде ПОСЛЕ последнего
# догона посева, могло унести с собой урок, которого в посеве нет. Это не доказывает долг —
# это называет, что человеку надо посмотреть. Длина остаётся справкой, а не приговором.
CATCHUP_MARK = "ПОСЛЕДНИЙ ДОГОН ПОСЕВА:"


# 🩸 ОПЛАЧЕНО 25.09 (находка помощника PROTO по догону посева): таблица, к которой применялся
# посев, была СВОЯ, урезанная — десять колонок, без status и revoked_*. Посев, несущий снятие
# правила в новый контур (UPDATE rules SET status='revoked' …), ронял проверку «no such column»,
# хотя настоящая сборка контура его принимает: у настоящей таблицы эти колонки есть.
# ⚡ КЛАСС «испытываем не то, что чиним»: проверка сличала посев с таблицей, которой нет ни у
# одного контура. Теперь форма таблицы берётся у сверяемой базы (она и есть образец формы:
# схема пакета растёт из схемы контура-донора); своя форма — только если у той нет rules.
RULES_TABLE_FALLBACK = """CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
    locked_by TEXT NOT NULL DEFAULT 'coord', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    basis TEXT, authorized TEXT, source_ref TEXT, expiry_kind TEXT, expiry_cond TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'superseded')),
    revoked_at TEXT, revoked_by TEXT, revoked_reason TEXT,
    superseded_by INTEGER REFERENCES rules(id) ON DELETE SET NULL, skill_delivery TEXT,
    CHECK (status <> 'revoked' OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
                                   AND revoked_reason IS NOT NULL)))"""


def rules_table_ddl(compare_db: pathlib.Path) -> str:
    """CREATE TABLE rules сверяемой базы — только чтением; нет базы или таблицы — своя форма."""
    try:
        con = sqlite3.connect(f"file:{compare_db.as_posix()}?mode=ro", uri=True)
        row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rules'").fetchone()
        con.close()
    except sqlite3.Error:
        row = None
    return row[0] if row and row[0] else RULES_TABLE_FALLBACK


def seed_as_database(seed_file: pathlib.Path, compare_db: pathlib.Path) -> dict[str, tuple[str, str]]:
    """Применяем файл посева так же, как это делает сборка контура: к таблице rules той же
    формы, что у контура. → {ключ: (тело, статус)} — статус нужен, чтобы снятое в посеве
    не называлось «в посеве живое»."""
    d = mezo_stand.new("seed-check-")
    con = sqlite3.connect(str(d / "seed.db"))
    con.execute(rules_table_ddl(compare_db))
    con.executescript(seed_file.read_text(encoding="utf-8"))
    has_status = "status" in {r[1] for r in con.execute("PRAGMA table_info(rules)")}
    # Пустой статус — действующее: у настоящей таблицы status NOT NULL DEFAULT 'active', пусто
    # бывает только у формы без значения по умолчанию, и там оно значит «не снимали».
    rows = {r[0]: (r[1], r[2]) for r in con.execute(
        "SELECT rule_key, body, "
        + ("COALESCE(status, 'active')" if has_status else "'active'") + " FROM rules")}
    con.close()
    return rows


def duplicates_in_seed(seed_file: pathlib.Path) -> list[tuple[str, int, bool]]:
    """→ [(ключ, сколько определений, объявлен ли дубль)] для ключей с >1 определением.

    ═══ Карточка #430 ③ (находка COORD 29.08): его правка легла в ПЕРВОЕ определение
    ключа и НЕ доехала — в базу разворачивается ПОСЛЕДНЕЕ, а эта проверка была зелёной.
    Файл читают глазами сверху, исполняется низ — две правды об одном. Дубль считается
    ОБЪЯВЛЕННЫМ, если в файле стоит комментарий «МЁРТВОЕ ОПРЕДЕЛЕНИЕ» с именем ключа
    (маркер COORD над мёртвым блоком). Необъявленный дубль — красный; объявленный
    назван без красноты: удаление дубля — разрушающее, словом владельца.
    """
    text = seed_file.read_text(encoding="utf-8")
    count: dict[str, int] = {}
    for k in re.findall(r"^\s*\('([\w-]+)',\s*" + chr(36) + "", text, re.M):
        count[k] = count.get(k, 0) + 1
    result = []
    for k, n in sorted(count.items()):
        if n > 1:
            declared = bool(re.search(r"МЁРТВОЕ ОПРЕДЕЛЕНИЕ[^\n]*'" + re.escape(k) + "'",
                                      text))
            result.append((k, n, declared))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", help="файл посева (по умолчанию — rules/universal.sql образца)")
    ap.add_argument("--show", help="показать тела этого правила рядом")
    ap.add_argument("--db", help="какой свод считать живым (по умолчанию — база контура). "
                                 "Нужен приёмке: испытывать проверку на живой базе нельзя")
    a = ap.parse_args()

    seed_file = pathlib.Path(a.seed) if a.seed else mezo_paths.template_root() / "rules" / "universal.sql"
    if not seed_file.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: посева нет — {seed_file}")
        return 2
    compare_db = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    try:
        seed = seed_as_database(seed_file, compare_db)
    except sqlite3.Error as e:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: посев не применяется к чистой базе — {e}")
        print("   Это само по себе находка: сборка нового контура на нём ляжет.")
        return 2

    con = sqlite3.connect(str(compare_db))
    live_rules = {r[0]: (r[1], r[2], (r[3] or "")[:16]) for r in
             con.execute("SELECT rule_key, body, status, updated_at FROM rules")}
    con.close()

    if a.show:
        k = a.show
        seed_body, seed_status = seed.get(k, ("(нет)", ""))
        print(f"── ПОСЕВ ({len(seed_body) if k in seed else 0} знаков"
              + (f", в новом контуре — {seed_status}" if seed_status not in ("", "active") else "")
              + f")\n{seed_body}")
        print(f"\n── ЖИВОЕ ({len(live_rules.get(k, ('',''))[0])} знаков)\n{live_rules.get(k, ('(нет)', ''))[0]}")
        return 0

    catchup = ""  # 🔴 пусто = метки в посеве НЕТ. Ниже это КРАСНОЕ, а не «нечего сравнивать»
    for line in seed_file.read_text(encoding="utf-8").splitlines():
        if CATCHUP_MARK in line:
            catchup = line.split(CATCHUP_MARK, 1)[1].strip()
            break

    if not catchup:
        # 🩸 ОПЛАЧЕНО 05.09: метку в посеве переименовали («ПОСЛЕДНИЙ ПОЛНЫЙ ДОГОН») из добрых
        # побуждений — отличить полный догон от частичного. Проверка ищет строку ДОСЛОВНО,
        # не нашла, и вместо «отстали 14» напечатала «отстали 0». Ослепла МОЛЧА: признак
        # отставания держится на одной этой строке, и её отсутствие выглядело как порядок.
        # ⚡ КЛАСС: переименование учащей строки гасит проверку без единого красного.
        print("=" * 84)
        print(f"🔴 В ПОСЕВЕ НЕТ МЕТКИ «{CATCHUP_MARK}» — сравнивать не с чем, и это ОТКАЗ,")
        print("   а не «отставших нет». Признак отставания держится на этой строке и только")
        print("   на ней: без неё проверка молча объявит порядок при любом расхождении.")
        print(f"   👉 верни строку в шапку {seed_file} ДОСЛОВНО, с часом последнего полного догона.")
        return 2

    poorer, richer, revoked, matched = [], [], [], 0
    revoked_both, revoked_in_seed = [], []   # снятое посевом: у обоих · только в посеве
    for k, (body, seed_status) in sorted(seed.items()):
        entry = live_rules.get(k)
        if not entry:
            continue
        live_body, status, edited_at = entry
        if status != "active":
            (revoked_both if seed_status != "active" else revoked).append(k)
            continue
        if seed_status != "active":
            revoked_in_seed.append(k)
            continue
        if body.strip() == live_body.strip():
            matched += 1
            continue
        if catchup and (edited_at or "") > catchup:
            poorer.append((k, edited_at or "?", len(body), len(live_body)))
        elif len(body) > len(live_body):
            richer.append((k, len(body), len(live_body)))
    missing_from_seed = sorted(k for k, (_, st, _u) in live_rules.items()
                          if st == "active" and k not in seed)

    print("=" * 84)
    print("СВОД ПРАВИЛ: ПОСЕВ ПРОТИВ ЖИВОГО")
    print(f"  посев: {seed_file}")
    print(f"  правил в посеве {len(seed)} · живых активных "
          f"{sum(1 for _, (_, s, _u) in live_rules.items() if s == 'active')}")
    print(f"  последний догон посева: {catchup or 'НЕ ОТМЕЧЕН — судить о свежести нечем'}")
    print("=" * 84)

    for k, edited_at, a_, b in poorer:
        print(f"🔴 {k:30} правлено {edited_at} ПОСЛЕ догона · посев {a_:5} · живое {b:5}")
    for k, a_, b in richer:
        print(f"🟡 {k:30} посев {a_:5} · живое {b:5} — посев БОГАЧЕ, копировать живое нельзя")
    for k in revoked:
        print(f"⚠️ {k:30} у вас СНЯТО, а в посеве живое — решите, умолчание это или долг")
    for k in revoked_in_seed:
        print(f"⚠️ {k:30} в посеве СНЯТО, а у вас живое — новый контур родится с ним снятым; "
              f"решите, умолчание это или долг")
    if revoked_both:
        print(f"ℹ️ снято и у вас, и в посеве (новый контур родится с ними снятыми): "
              f"{len(revoked_both)} — " + " · ".join(revoked_both))
    if missing_from_seed:
        print(f"⚪ нет в посеве вовсе: {len(missing_from_seed)} — общее ли это, решает человек:")
        print("   " + " · ".join(missing_from_seed[:12]) + ("…" if len(missing_from_seed) > 12 else ""))

    # ═══ Карточка #430 ③: ключ, определённый в файле дважды, называется ВСЛУХ.
    # ⚖️ ЖЁЛТЫМ, а не красным, и это решение с замером: живой посев несёт 27 наслоений
    # (файл рос семью волнами дозаливок «INSERT OR REPLACE») — красное на всех до
    # большого сведения было бы вечно-красным и учило не верить проверке. Ловушка
    # от этого не тише: правка в НЕ-последнее определение умирает молча (COORD 29.08).
    duplicates = duplicates_in_seed(seed_file)
    silent_duplicates = [(k, n) for k, n, declared in duplicates if not declared]
    for k, n in silent_duplicates:
        print(f"⚠️ {k:30} определён {n} раз БЕЗ объявления — в базу доедет ПОСЛЕДНЕЕ, "
              f"правка в верхнее умрёт молча. Правь ПОСЛЕДНЕЕ вхождение")
    for k, n, declared in duplicates:
        if declared:
            print(f"ℹ️ {k:30} определён {n} раз, дубль ОБЪЯВЛЕН в файле — исполняется "
                  f"последнее; удаление мёртвого блока — словом владельца")

    print("-" * 84)
    print(f"совпадают дословно {matched} · 🔴 отстали {len(poorer)} · 🟡 богаче {len(richer)} "
          f"· ⚠️ снятых у нас {len(revoked)} · снятых только в посеве {len(revoked_in_seed)}"
          f" · снятых у обоих {len(revoked_both)} · ⚪ вне посева {len(missing_from_seed)}"
          f" · дубли ключей: немых {len(silent_duplicates)} / объявленных "
          f"{len(duplicates) - len(silent_duplicates)}")
    if poorer:
        print("⛔ Эти правила менялись в живом своде ПОСЛЕ последнего догона — посмотри, "
              "не унесли ли они с собой урок, которого в посеве нет.")
        print("   Отставание НЕ ВИДНО по номеру версии: в посеве его ставит тот, кто переносит, и о возрасте текста в живом своде он не говорит.")
    else:
        print("✅ отставших правил нет.")
    if silent_duplicates:
        print("⚠️ Наслоения посева: правку кладут в текст, который НЕ исполняется, "
              "и никто не скажет (оплачено COORD 29.08, карточка #430). Сведение "
              "наслоений — отдельное решение владельца, до него правь ПОСЛЕДНЕЕ вхождение.")
    return 1 if poorer else 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
