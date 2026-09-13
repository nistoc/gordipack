#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PLANTS: skills
r"""ПРИЁМКА: состав навыков берётся ИЗ КОНТУРА, а не только из встроенного PACKAGES
(карточка #604 ①, заявка контура tapas).

ПОВОД. Встроенный словарь PACKAGES в rules-to-skills.py называет имена atlas-* и 58 ключей
правил конкретно свода Atlas. У чужого контура (tapas) свой свод — 26 из 58 ключей там нет
вовсе, а сборщик прежде отказывал на первом же отсутствующем, и имена atlas-* были бы чужим
словом для себя. Правка сделала три вещи разом:
    ① состав пакетов МОЖЕТ приезжать файлом `<каталог базы>/skill-packages.json`;
    ② без файла — встроенный PACKAGES, но префикс "atlas-" меняется на "<group_name>-"
       по `meta.group_name` базы контура;
    ③ отсутствующее правило больше не валит сборку целиком: навык собирается из того,
       что нашлось, отсутствующее названо поимённо; --strict возвращает прежний отказ.
Для контура Atlas (файла нет, group_name == "atlas" либо его нет вовсе) вывод НЕ МЕНЯЕТСЯ —
это отдельно проверено приёмкой rules-to-skills.py --out (карточка #604, шаг A) байт в байт;
здесь проверяется собственно НОВЫЙ контракт.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контур Atlas БЕЗ изменений: имя навыка не переименовано, «состав:» в выводе не
     печатается (та самая строка, что ломала бы байт-в-байт совместимость)      РАЗЛИЧАЮЩИЙ
  ② чужой контур: префикс имени навыка берётся ИЗ meta.group_name                РАЗЛИЧАЮЩИЙ
  ③ отсутствующие правила названы поимённо; навык без единого правила НЕ собран,
     и это тоже названо строкой, а не тихим пропуском                            РАЗЛИЧАЮЩИЙ
  ④ --strict отказывает на той же базе, где ③ собрал частично                    РАЗЛИЧАЮЩИЙ
  ⑤ файл состава контура `skill-packages.json` рядом с базой — имена и состав
     берутся ИЗ НЕГО, встроенный PACKAGES и префикс группы не участвуют          РАЗЛИЧАЮЩИЙ
  ⑥ САМОИСПЫТАНИЕ: нарочная поломка (group_name игнорируется сборщиком) красит
     РОВНО случай ②, остальные четыре остаются зелёными — иначе ② зеленел бы
     не потому, что проверяет префикс, а по любой другой причине                 РАЗЛИЧАЮЩИЙ

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


def case(title: str, verdict: bool, detail: str = "") -> bool:
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")
    return verdict


def corpus(rule_keys: list[str], group_name: str | None = "__absent__") -> pathlib.Path:
    """Копия свода: таблица rules (схема — как у живой базы) + опционально meta.group_name.

    group_name="__absent__" (по умолчанию) — таблицы meta вовсе нет: читающий её код
    обязан получить None молча (см. read_group_name), а не упасть — то же самое, что база
    старше поля. Явное None кладёт таблицу meta БЕЗ строки group_name; строка — со строкой.
    """
    d = mezo_stand.new("bite-foreign-")
    db = d / "mezosync.db"
    con = sqlite3.connect(str(db))
    con.execute("""CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT UNIQUE, body TEXT,
                   locked_by TEXT, version INT, status TEXT, updated_at TEXT)""")
    for i, key in enumerate(rule_keys, 1):
        con.execute("INSERT INTO rules (id, rule_key, body, locked_by, version, status, "
                    "updated_at) VALUES (?,?,?,?,?,?,?)",
                    (i, key, RULE_BODY, "owner", 1, "active", EDITED_AT))
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
    """Пять базовых случаев против ОДНОГО сборщика (живого или подсаженного).
    Возвращает {номер: verdict} — нужно и для счёта, и для самоиспытания ⑥, которое
    сверяет, КАКИЕ номера покраснели на поломке.

    record=False (прогон против ПОДСАЖЕННОГО сборщика) — печать идёт, а в общий счёт
    (CASES/OK) эти пять НЕ входят: для подсадки ожидаемый результат — что случай ②
    покраснеет, и это не поломка приёмки, а её доказательство. Настоящий приёмочный
    случай тут один — ⑥, он и сверяет состав красных номеров."""
    verdicts: dict[int, bool] = {}

    def c(title: str, verdict: bool, detail: str = "") -> bool:
        if record:
            return case(title, verdict, detail)
        mark = "✅" if verdict else "🔴"
        print(f"{mark} {title}  · диагностика самоиспытания, в счёт ⑥ не входит отдельной строкой")
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

    return verdicts


def main() -> int:
    if not GENERATOR.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет механизма — {GENERATOR}")

    # ── ①–⑤ против ЖИВОГО (неподсаженного) сборщика — идут в общий счёт ──
    live_results = run_cases(GENERATOR, "живой сборщик", record=True)

    # ── ⑥ САМОИСПЫТАНИЕ: сборщик, где group_name НАРОЧНО игнорируется. Копия ВМЕСТЕ
    # с соседями (mezo_stand.copy_tool) — иначе подсаженный файл падает «нет модуля
    # mezo_paths», что выглядело бы красным по чужой причине, а не по сути поломки.
    sandbox_dir = mezo_stand.new("bite-foreign-sabotage-")
    sabotaged = mezo_stand.copy_tool(GENERATOR, sandbox_dir)
    text = sabotaged.read_text(encoding="utf-8")
    original_line = 'if not group or group == "atlas":'
    if original_line not in text:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: точка поломки в rules-to-skills.py не найдена — "
                 "текст функции packages_with_group_prefix разошёлся с приёмкой.")
    sabotaged.write_text(text.replace(
        original_line,
        "if True:  # 🩸 НАРОЧНАЯ ПОЛОМКА bite-skills-foreign-contour.py: group_name "
        "игнорируется намеренно, чтобы доказать, что случай ② его и правда проверяет"
    ), encoding="utf-8")

    print()
    # record=False: печать идёт (для осмотра), но в CASES/OK эти пять НЕ входят — для
    # подсадки красное на ② ОЖИДАЕМО и доказывает приёмку, а не ломает её.
    sabotaged_results = run_cases(sabotaged, "ПОДСАЖЕННЫЙ сборщик", record=False)
    reddened = {n for n, ok in sabotaged_results.items() if not ok}
    case("⑥ нарочная поломка (group_name игнорируется) красит РОВНО случай ②",
         reddened == {2},
         f"покраснели номера: {sorted(reddened) or 'ни один'} — ждём ровно {{2}}; "
         "иначе случай ② зеленел бы не по сути (различитель этой же приёмки)")

    total_ok = sum(live_results.values()) + (1 if reddened == {2} else 0)
    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if OK else '🔴 ПРИЁМКА НЕ ПРИНЯТА'} — {total_ok} из {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
