#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PLANTS: skills
r"""ПРИЁМКА: состав навыков берётся ИЗ КОНТУРА, а не только из встроенного PACKAGES
(карточка #604 ①, заявка контура tapas; карточка #607 — две беды на том же месте).

ПОВОД. Встроенный словарь PACKAGES в rules-to-skills.py называет имена atlas-* и 58 ключей
правил конкретно свода Atlas. У чужого контура (tapas) свой свод — 26 из 58 ключей там нет
вовсе, а сборщик прежде отказывал на первом же отсутствующем, и имена atlas-* были бы чужим
словом для себя. Правка карточки #604 сделала три вещи разом:
    ① состав пакетов МОЖЕТ приезжать файлом `<каталог базы>/skill-packages.json`;
    ② без файла — встроенный PACKAGES, но префикс "atlas-" меняется на "<group_name>-"
       по `meta.group_name` базы контура;
    ③ отсутствующее правило больше не валит сборку целиком: навык собирается из того,
       что нашлось, отсутствующее названо поимённо; --strict возвращает прежний отказ.
Для контура Atlas (файла нет, group_name == "atlas" либо его нет вовсе) вывод НЕ МЕНЯЕТСЯ —
это отдельно проверено приёмкой rules-to-skills.py --out (карточка #604, шаг A) байт в байт;
здесь проверяется собственно контракт.

КАРТОЧКА #607 добавила сюда две беды того же механизма, найденные у чужого контура:
    ⑦⑧ префикс имени меняется на "<group>-", а ТЕКСТЫ навыка ("описание"/"когда") у
       чужого контура всё ещё звали читателя «Atlas» — слово чужого контура для себя;
    ⑨⑩ сборка нескольких навыков зараз писала файл каждого навыка СРАЗУ по ходу цикла;
       отказ на ВТОРОМ (или позже) навыке оставлял на диске уже записанные файлы ПЕРВЫХ,
       хотя сообщение гласило «НЕ ЗАПУСТИЛСЯ» — отказ обязан быть ДО первой записи.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контур Atlas БЕЗ изменений: имя навыка не переименовано, «состав:» в выводе не
     печатается (та самая строка, что ломала бы byte-for-byte совместимость)     РАЗЛИЧАЮЩИЙ
  ② чужой контур: префикс имени навыка берётся ИЗ meta.group_name                РАЗЛИЧАЮЩИЙ
  ③ отсутствующие правила названы поимённо; навык без единого правила НЕ собран,
     и это тоже названо строкой, а не тихим пропуском                            РАЗЛИЧАЮЩИЙ
  ④ --strict отказывает на той же базе, где ③ собрал частично                    РАЗЛИЧАЮЩИЙ
  ⑤ файл состава контура `skill-packages.json` рядом с базой — имена и состав
     берутся ИЗ НЕГО, встроенный PACKAGES и префикс группы не участвуют          РАЗЛИЧАЮЩИЙ
  ⑥ САМОИСПЫТАНИЕ: нарочная поломка (group_name игнорируется сборщиком целиком)
     красит ② И ⑦ разом — обе висят на ОДНОМ и том же раннем возврате PACKAGES;
     остальные (①③④⑤⑧⑨⑩) остаются зелёными                                     РАЗЛИЧАЮЩИЙ

  ── карточка #607: слово «Atlas» в текстах чужого контура · отказ ДО первой записи ──
  ⑦ чужой контур: слово «Atlas» (ЦЕЛЫМ словом) в «описание»/«когда» навыка ответа
     владельцу заменено на имя группы                                            РАЗЛИЧАЮЩИЙ
  ⑧ ВСТРЕЧНЫЙ ⑦: контур Atlas — «владельцу Atlas» осталось нетронутым (подстановка
     не срабатывает вовсе для своего контура)                                    РАЗЛИЧАЮЩИЙ
  ⑨ --strict, у ВТОРОГО по порядку навыка не хватает одного правила, --write в
     пустой --out: код отказа, ни одного SKILL.md на диске И вывод говорит «ни один
     навык не записан» (строка «✍️» первого навыка напечатана при сборе)           РАЗЛИЧАЮЩИЙ
  ⑩ то же самое для СНЯТОГО правила второго навыка, БЕЗ --strict (снятое отказывает
     всегда, флаг тут ни при чём)                                                РАЗЛИЧАЮЩИЙ
  ⑪ САМОИСПЫТАНИЕ: нарочная поломка (подстановка имени снята, переименование цело)
     красит РОВНО случай ⑦                                                       РАЗЛИЧАЮЩИЙ
  ⑫ САМОИСПЫТАНИЕ: нарочная поломка (запись вернули внутрь первого прохода) красит
     РОВНО случаи ⑨ и ⑩                                                          РАЗЛИЧАЮЩИЙ
  ⑬ САМОИСПЫТАНИЕ: нарочная поломка (строка «ни один навык не записан» снята) красит
     РОВНО случаи ⑨ и ⑩ — выводом, а не состоянием диска                         РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: своя копия базы (через mezo_stand) на каждый случай,
свои временные каталоги вывода. Живую mezosync.db и живой .claude/skills не трогает.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)
import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = pathlib.Path(__file__).resolve().parent
GENERATOR = HERE / "rules-to-skills.py"
CASES = 0
OK = True

RULE_BODY = "НОРМА ЖИВЁТ ЗДЕСЬ, дальше — разбор случаев (проба карточки #604)."
EDITED_AT = "2026-08-01 10:00"

# ── карточка #607: составы двух пакетов, которыми играют случаи ⑦–⑩. Хардкод, а не
# импорт из rules-to-skills.py — этот файл проверяет ЧЁРНЫМ ЯЩИКОМ (subprocess), как и
# остальные случаи здесь; список должен совпадать с package["правила"] в PACKAGES.
OWNER_REPLY_RULES = ["owner-reply-format", "plain-words", "questions-via-interface",
                      "proactive-next-steps", "remeasure-before-ask",
                      "interview-before-recommend"]
ACCEPTANCE_RULES = ["acceptance-e2e", "gate-before-commit", "bytes-are-not-content",
                     "contract-shape-from-live-call", "read-failure-blocks-write",
                     "finding-covers-only-your-branch", "name-is-a-claim-not-a-property",
                     "services-self-raise", "counter-case-own-definition"]


def case(title: str, verdict: bool, detail: str = "") -> bool:
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")
    return verdict


def corpus(rule_keys: list[str], group_name: str | None = "__absent__",
           statuses: dict[str, str] | None = None) -> pathlib.Path:
    """Копия свода: таблица rules (схема — как у живой базы) + опционально meta.group_name.

    group_name="__absent__" (по умолчанию) — таблицы meta вовсе нет: читающий её код
    обязан получить None молча (см. read_group_name), а не упасть — то же самое, что база
    старше поля. Явное None кладёт таблицу meta БЕЗ строки group_name; строка — со строкой.

    statuses — карточка #607 ⑩: карта {ключ_правила: статус} для ключей, чей статус
    должен быть НЕ "active" (снятое правило). Для ключа без записи в этой карте — статус
    "active", как было раньше; параметр добавлен, старые вызовы corpus() не меняются.
    """
    d = mezo_stand.new("bite-foreign-")
    db = d / "mezosync.db"
    con = sqlite3.connect(str(db))
    con.execute("""CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT UNIQUE, body TEXT,
                   locked_by TEXT, version INT, status TEXT, updated_at TEXT)""")
    for i, key in enumerate(rule_keys, 1):
        status = (statuses or {}).get(key, "active")
        con.execute("INSERT INTO rules (id, rule_key, body, locked_by, version, status, "
                    "updated_at) VALUES (?,?,?,?,?,?,?)",
                    (i, key, RULE_BODY, "owner", 1, status, EDITED_AT))
    if group_name != "__absent__":
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        if group_name is not None:
            con.execute("INSERT INTO meta (key, value) VALUES ('group_name', ?)", (group_name,))
    con.commit()
    con.close()
    return db


def run(tool: pathlib.Path, db: pathlib.Path, out: pathlib.Path, only=None, strict=False):
    cmd = [sys.executable, str(tool), "--db", str(db), "--out", str(out), "--write"]
    if only:
        cmd += ["--only", only]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def run_cases(tool: pathlib.Path, label: str, record: bool) -> dict[int, bool]:
    """Девять базовых случаев против ОДНОГО сборщика (живого или подсаженного): ①–⑤
    (карточка #604) и ⑦–⑩ (карточка #607). Возвращает {номер: verdict} — нужно и для
    счёта, и для самоиспытаний ⑥/⑪/⑫, которые сверяют, КАКИЕ номера покраснели.

    record=False (прогон против ПОДСАЖЕННОГО сборщика) — печать идёт, а в общий счёт
    (CASES/OK) эти случаи НЕ входят: для подсадки ожидаемый результат — что РОВНО
    названный номер (или пара) покраснеет, и это не поломка приёмки, а её доказательство.
    Настоящий приёмочный случай на каждую подсадку — один: ⑥, ⑪ или ⑫."""
    verdicts: dict[int, bool] = {}

    def c(title: str, verdict: bool, detail: str = "") -> bool:
        if record:
            return case(title, verdict, detail)
        mark = "✅" if verdict else "🔴"
        print(f"{mark} {title}  · диагностика самоиспытания, в счёт отдельной строкой не входит")
        if detail:
            print(f"   {detail}")
        return verdict

    # ① Atlas без изменений: meta вовсе нет (как у базы старше поля) — имя навыка
    # НЕ переименовано (atlas-secrets как было), строки «состав:» в выводе НЕТ.
    db1 = corpus(["secrets-never-in-command-line"], group_name="__absent__")
    out1, code1 = run(tool, db1, mezo_stand.new("bite-foreign-out-"), only="atlas-secrets")
    verdicts[1] = c(
        f"① [{label}] контур Atlas без изменений — имя не тронуто, «состав:» отсутствует",
        code1 == 0 and "atlas-secrets" in out1 and "состав:" not in out1,
        f"код {code1}; печать лишней строки источника сломала бы byte-for-byte сравнение шага A")

    # ② чужой контур: meta.group_name='probe' — имя "atlas-secrets" становится
    # "probe-secrets", и строка «состав:» это называет.
    db2 = corpus(["secrets-never-in-command-line"], group_name="probe")
    out2, code2 = run(tool, db2, mezo_stand.new("bite-foreign-out-"), only="probe-secrets")
    verdicts[2] = c(
        f"② [{label}] чужой контур: префикс навыка — ИЗ meta.group_name",
        code2 == 0 and "probe-secrets" in out2 and "atlas-secrets" not in out2
        and "префикс «probe-»" in out2,
        f"код {code2}; ждём имя probe-secrets (не atlas-secrets) — meta.group_name='probe'")

    # ③ отсутствующие правила названы поимённо; навык без единого правила не собран.
    # Пакет atlas-commit-push (4 ключа): в своде — только 2 из 4, остальные ДВА
    # отсутствуют. Пакет atlas-secrets (1 ключ): в своде нет вовсе ни одного.
    # Проверки НЕ завязаны на префикс имени — иначе ⑥ покрасило бы этот случай тоже.
    db3 = corpus(["gate-before-commit", "rule8-destructive"], group_name="probe")
    out3, code3 = run(tool, db3, mezo_stand.new("bite-foreign-out-"))
    verdicts[3] = c(
        f"③ [{label}] без --strict: отсутствующее правило названо, навык без правил не собран",
        code3 == 0
        and "в своде контура нет: coord-commits-coordination, command-picks-target-by-position"
        in out3
        and "не собран: ни одного его правила в своде нет" in out3,
        f"код {code3}; тихий пропуск неотличим от забытого навыка")

    # ④ --strict на ТОЙ ЖЕ базе — отказ, а не терпимая сборка.
    out4, code4 = run(tool, db3, mezo_stand.new("bite-foreign-out-"), strict=True)
    verdicts[4] = c(
        f"④ [{label}] --strict отказывает на той же базе, где ③ собрал частично",
        code4 != 0 and "НЕ ЗАПУСТИЛСЯ" in out4,
        f"код {code4}; --strict обязан вернуть исходное поведение — отказ, не терпимость")

    # ⑤ файл состава `skill-packages.json` РЯДОМ С БАЗОЙ — берётся ОН; встроенный
    # PACKAGES и префикс группы (здесь group_name='другая-группа') не участвуют.
    db5 = corpus(["plain-words"], group_name="другая-группа")
    (db5.parent / "skill-packages.json").write_text(json.dumps({
        "из-файла-навык": {"описание": "проба состава из файла контура", "когда": "проба",
                           "правила": ["plain-words"]},
    }, ensure_ascii=False), encoding="utf-8")
    out5, code5 = run(tool, db5, mezo_stand.new("bite-foreign-out-"))
    verdicts[5] = c(
        f"⑤ [{label}] файл состава рядом с базой — имена и состав ИЗ НЕГО",
        code5 == 0 and "из-файла-навык" in out5 and "другая-группа-" not in out5
        and "файл контура" in out5,
        f"код {code5}; файл рядом с базой обязан перекрыть встроенный набор и префикс группы")

    # ⑦ карточка #607 ①: чужой контур — слово «Atlas» в «описание»/«когда» навыка
    # ответа владельцу заменено ЦЕЛЫМ словом на имя группы. Печать сводки называет
    # только ДЛИНУ описания, не сам текст — подстановку видно лишь в самом SKILL.md,
    # поэтому здесь --write и читаем готовый файл.
    db7 = corpus(OWNER_REPLY_RULES, group_name="tapas")
    out7 = mezo_stand.new("bite-foreign-out-")
    _, code7 = run(tool, db7, out7, only="tapas-owner-reply")
    skill7_path = out7 / "tapas-owner-reply" / "SKILL.md"
    skill7 = skill7_path.read_text(encoding="utf-8") if skill7_path.exists() else ""
    verdicts[7] = c(
        f"⑦ [{label}] чужой контур: «Atlas» в текстах навыка ответа владельцу — имя группы",
        code7 == 0 and skill7_path.exists() and "tapas" in skill7 and "Atlas" not in skill7,
        f"код {code7}; файл {'есть' if skill7_path.exists() else 'НЕ СОЗДАН'}; ждём «tapas» "
        "и ни одного «Atlas» — иначе чужой контур продолжает читать чужое слово как своё")

    # ⑧ ВСТРЕЧНЫЙ ⑦: контур Atlas (group_name="atlas") — «владельцу Atlas» остаётся
    # нетронутым: подстановка не смеет сработать для СВОЕГО контура.
    db8 = corpus(OWNER_REPLY_RULES, group_name="atlas")
    out8 = mezo_stand.new("bite-foreign-out-")
    _, code8 = run(tool, db8, out8, only="atlas-owner-reply")
    skill8_path = out8 / "atlas-owner-reply" / "SKILL.md"
    skill8 = skill8_path.read_text(encoding="utf-8") if skill8_path.exists() else ""
    verdicts[8] = c(
        f"⑧ [{label}] встречный ⑦: контур Atlas — «владельцу Atlas» осталось нетронутым",
        code8 == 0 and skill8_path.exists() and "владельцу Atlas" in skill8,
        f"код {code8}; своя группа не смеет попасть под замену — иначе ⑦ зеленел бы не по сути")

    # ⑨ карточка #607 ②: --strict, у ВТОРОГО по порядку навыка (atlas-acceptance) не
    # хватает ОДНОГО правила ("counter-case-own-definition") — первый навык (atlas-
    # owner-reply) собрался бы полностью. Отказ обязан прийти ДО первой записи: --out
    # остаётся пустым целиком, а не «первый навык уже на диске».
    db9 = corpus(OWNER_REPLY_RULES + ACCEPTANCE_RULES[:-1], group_name="__absent__")
    out9 = mezo_stand.new("bite-foreign-out-")
    out9_text, code9 = run(tool, db9, out9, strict=True)
    wrote9 = any(out9.rglob("SKILL.md"))
    # и ВЫВОД говорит это вслух: строка «✍️» первого навыка напечатана при сборе, без
    # «ни один навык не записан» она читалась бы как «первый навык лёг на диск»
    said9 = "ни один навык не записан" in out9_text
    verdicts[9] = c(
        f"⑨ [{label}] --strict: у второго навыка не хватает правила — отказ ДО первой записи",
        code9 != 0 and not wrote9 and said9,
        f"код {code9}; SKILL.md в --out: {'ЕСТЬ — БЕДА' if wrote9 else 'нет, как и должно быть'}; "
        f"«ни один навык не записан» в выводе: {said9}")

    # ⑩ то же самое, только правило второго навыка НЕ отсутствует, а СНЯТО (status
    # != active) — отказывает ВСЕГДА, независимо от --strict (поэтому здесь его нет).
    db10 = corpus(OWNER_REPLY_RULES + ACCEPTANCE_RULES, group_name="__absent__",
                  statuses={"counter-case-own-definition": "retired"})
    out10 = mezo_stand.new("bite-foreign-out-")
    out10_text, code10 = run(tool, db10, out10)
    wrote10 = any(out10.rglob("SKILL.md"))
    said10 = "ни один навык не записан" in out10_text
    verdicts[10] = c(
        f"⑩ [{label}] снятое правило второго навыка (без --strict) — тот же отказ до записи",
        code10 != 0 and not wrote10 and said10,
        f"код {code10}; SKILL.md в --out: {'ЕСТЬ — БЕДА' if wrote10 else 'нет, как и должно быть'}; "
        f"«ни один навык не записан» в выводе: {said10}")

    return verdicts


def main() -> int:
    if not GENERATOR.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет механизма — {GENERATOR}")

    # ── ①–⑤,⑦–⑩ против ЖИВОГО (неподсаженного) сборщика — идут в общий счёт ──
    live_results = run_cases(GENERATOR, "живой сборщик", record=True)

    # ── ⑥ САМОИСПЫТАНИЕ: сборщик, где group_name НАРОЧНО игнорируется целиком. Копия
    # ВМЕСТЕ с соседями (mezo_stand.copy_tool) — иначе подсаженный файл падает «нет
    # модуля mezo_paths», что выглядело бы красным по чужой причине, а не по сути
    # поломки. ⚖️ Эта же поломка теперь красит и ⑦: переименование и подстановка имени
    # (карточка #607 ①) сидят ЗА ОДНИМ и тем же ранним возвратом PACKAGES — ломая вход
    # в ветку целиком, поломка валит оба следствия разом, и это честно, а не потеря
    # различительности: ⑪ ниже ломает РОВНО подстановку, доказывая, что она отдельная.
    sandbox_dir6 = mezo_stand.new("bite-foreign-sabotage-")
    sabotaged6 = mezo_stand.copy_tool(GENERATOR, sandbox_dir6)
    text6 = sabotaged6.read_text(encoding="utf-8")
    original_line6 = 'if not group or group == "atlas":'
    if original_line6 not in text6:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: точка поломки (ранний возврат) в rules-to-skills.py "
                 "не найдена — текст функции packages_with_group_prefix разошёлся с приёмкой.")
    sabotaged6.write_text(text6.replace(
        original_line6,
        "if True:  # 🩸 НАРОЧНАЯ ПОЛОМКА bite-skills-foreign-contour.py: group_name "
        "игнорируется намеренно, чтобы доказать, что случаи ②/⑦ его и правда проверяют"
    ), encoding="utf-8")

    print()
    sabotaged6_results = run_cases(sabotaged6, "ПОДСАЖЕННЫЙ сборщик (ранний возврат)",
                                    record=False)
    reddened6 = {n for n, ok in sabotaged6_results.items() if not ok}
    case("⑥ нарочная поломка (group_name игнорируется целиком) красит РОВНО ② и ⑦",
         reddened6 == {2, 7},
         f"покраснели номера: {sorted(reddened6) or 'ни один'} — ждём ровно {{2, 7}}; "
         "обе висят на одном и том же раннем возврате PACKAGES (различитель этой же приёмки)")

    # ── ⑪ САМОИСПЫТАНИЕ отдельно от ⑥: сборщик, где переименование ЦЕЛО, а подстановка
    # слова «Atlas» на имя группы снята — доказывает, что случай ⑦ проверяет именно
    # ПОДСТАНОВКУ ТЕКСТА, а не переименование (которое уже проверяет ②/⑥).
    sandbox_dir11 = mezo_stand.new("bite-foreign-sabotage-")
    sabotaged11 = mezo_stand.copy_tool(GENERATOR, sandbox_dir11)
    text11 = sabotaged11.read_text(encoding="utf-8")
    original_line11 = "                new_package[field] = _ATLAS_WORD_RE.sub(group, new_package[field])"
    if original_line11 not in text11:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: точка поломки (подстановка имени) в rules-to-skills.py "
                 "не найдена — текст функции packages_with_group_prefix разошёлся с приёмкой.")
    sabotaged11.write_text(text11.replace(
        original_line11,
        "                new_package[field] = new_package[field]  # 🩸 НАРОЧНАЯ ПОЛОМКА "
        "bite-skills-foreign-contour.py: подстановка имени снята намеренно, чтобы доказать, "
        "что случай ⑦ её и правда проверяет"
    ), encoding="utf-8")

    print()
    sabotaged11_results = run_cases(sabotaged11, "ПОДСАЖЕННЫЙ сборщик (без подстановки)",
                                     record=False)
    reddened11 = {n for n, ok in sabotaged11_results.items() if not ok}
    case("⑪ нарочная поломка (подстановка имени снята) красит РОВНО случай ⑦",
         reddened11 == {7},
         f"покраснели номера: {sorted(reddened11) or 'ни один'} — ждём ровно {{7}}; "
         "переименование (② и ⑥) эта поломка не трогает — только тексты описание/когда")

    # ── ⑫ САМОИСПЫТАНИЕ: сборщик, где запись файла вернули ВНУТРЬ первого прохода
    # (отмена карточки #607 ②) — первый навык из списка успевает лечь на диск раньше,
    # чем второй навык оборвёт сборку целиком. Должна красить РОВНО ⑨ и ⑩: только они
    # проверяют состояние диска ПОСЛЕ отказа на нескольких навыках зараз.
    sandbox_dir12 = mezo_stand.new("bite-foreign-sabotage-")
    sabotaged12 = mezo_stand.copy_tool(GENERATOR, sandbox_dir12)
    text12 = sabotaged12.read_text(encoding="utf-8")
    original_line12 = "        collected.append((name, text))"
    if original_line12 not in text12:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: точка поломки (два прохода) в rules-to-skills.py не "
                 "найдена — текст main() разошёлся с приёмкой.")
    sabotaged12.write_text(text12.replace(
        original_line12,
        "        collected.append((name, text))\n"
        "        if a.write:  # 🩸 НАРОЧНАЯ ПОЛОМКА bite-skills-foreign-contour.py: запись\n"
        "            # вернули в цикл намеренно, чтобы доказать, что случаи ⑨/⑩ её и\n"
        "            # правда проверяют — навык пишется раньше, чем откажет следующий\n"
        "            path = root / name / \"SKILL.md\"\n"
        "            path.parent.mkdir(parents=True, exist_ok=True)\n"
        "            path.write_text(text, encoding=\"utf-8\")"
    ), encoding="utf-8")

    print()
    sabotaged12_results = run_cases(sabotaged12, "ПОДСАЖЕННЫЙ сборщик (запись в цикле)",
                                     record=False)
    reddened12 = {n for n, ok in sabotaged12_results.items() if not ok}
    case("⑫ нарочная поломка (запись вернули в цикл) красит РОВНО случаи ⑨ и ⑩",
         reddened12 == {9, 10},
         f"покраснели номера: {sorted(reddened12) or 'ни один'} — ждём ровно {{9, 10}}; "
         "остальные случаи состояние диска ПОСЛЕ отказа не проверяют")

    # ── ⑬ САМОИСПЫТАНИЕ (решающий прогон PROTO): снята строка «ни один навык не записан» —
    # файлы по-прежнему не пишутся, но вывод снова читается как «первый навык лёг на диск».
    # Должна красить РОВНО ⑨ и ⑩ — и уже не состоянием диска, а выводом.
    sandbox_dir13 = mezo_stand.new("bite-foreign-sabotage-")
    sabotaged13 = mezo_stand.copy_tool(GENERATOR, sandbox_dir13)
    text13 = sabotaged13.read_text(encoding="utf-8")
    original_line13 = "            if a.write and collected:"
    if original_line13 not in text13:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: точка поломки (строка об отказе до записи) в "
                 "rules-to-skills.py не найдена — текст main() разошёлся с приёмкой.")
    sabotaged13.write_text(text13.replace(
        original_line13,
        "            if False:  # 🩸 НАРОЧНАЯ ПОЛОМКА bite-skills-foreign-contour.py ⑬"),
        encoding="utf-8")
    print()
    sabotaged13_results = run_cases(sabotaged13, "ПОДСАЖЕННЫЙ сборщик (строка об отказе снята)",
                                     record=False)
    reddened13 = {n for n, ok in sabotaged13_results.items() if not ok}
    case("⑬ нарочная поломка (строка «ни один навык не записан» снята) красит РОВНО ⑨ и ⑩",
         reddened13 == {9, 10},
         f"покраснели номера: {sorted(reddened13) or 'ни один'} — ждём ровно {{9, 10}}")

    total_ok = (sum(live_results.values())
                + (1 if reddened6 == {2, 7} else 0)
                + (1 if reddened11 == {7} else 0)
                + (1 if reddened12 == {9, 10} else 0)
                + (1 if reddened13 == {9, 10} else 0))
    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if OK else '🔴 ПРИЁМКА НЕ ПРИНЯТА'} — {total_ok} из {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
