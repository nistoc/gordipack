# -*- coding: utf-8 -*-
r"""bite-brief-views.py — приёмка карточки #593, задание 7: три инструмента координации
(`backlog.py list`, `guard-all.py`, `role-brief.py`) печатают КРАТКО по умолчанию и
ПОЛНОСТЬЮ под флагом `--full`. Эта приёмка держит инварианты, ради которых краткий вид
вообще разрешили заводить:

  · краткий вид НЕ СЪЕДАЕТ ПРИЧИНЫ — строки, объясняющие ПОЧЕМУ карточка устарела или
    заморожена, печатаются одинаково что в кратком, что в полном виде;
  · краткий вид НЕ СЪЕДАЕТ КРАСНОЕ — упавшая проверка видна В КРАТКОМ ВИДЕ так же, как
    в полном (сжимается только ЗЕЛЁНОЕ);
  · краткий вид НЕ СЪЕДАЕТ ПРЕДУПРЕЖДЕНИЯ — строки со знаком ⚠️/ℹ️ печатаются одинаково
    в обоих видах;
  · краткий вид НЕ ВРЁТ ЧИСЛАМИ — сводная строка («прошли N: …», «мост соседей: N …»)
    называет ровно то число, что можно пересчитать по полному виду.

═══ ЧТО ПРОВЕРЯЕТ (12 случаев + 2 нарочные поломки) ═══
  ①…⑤, ⑫  backlog.py list --status all --actor PROTO: шапка, первые строки карточек,
           срез критерия («🎯 …», второй строкой) виден только под --full, причины
           dropped/frozen видны В ОБОИХ видах, блок пула дословно тот же, подсказка
           о --full показывается по правилам mezo_hints (карточка #586).
  ⑥…⑩      guard-all.py: последняя строка итога, множество красных («⛔»), множество
           предупреждений («⚠️»/«ℹ️»), сводка «прошли N: …», сводка моста соседей.
  ⑪        role-brief.py: четыре постоянных хвоста (порядок пробуждения, ритм, свод,
           ответы владельцу) — та же подсказка mezo_hints, три вызова подряд.
  (а)      НАРОЧНАЯ ПОЛОМКА guard-all.py: check() без учёта `ok` в кратком виде глотает
           КРАСНОЕ — случай ⑦ на такой копии обязан покраснеть.
  (б)      НАРОЧНАЯ ПОЛОМКА backlog.py: cmd_list пропускает замороженную карточку в
           кратком виде — случай ② на такой копии обязан покраснеть.

═══ ГРАНИЦЫ — чего эта приёмка НЕ проверяет (сказано вслух, а не скрыто) ═══
  · дословный текст подсказок mezo_hints — эта приёмка проверена отдельно (bite-tool-
    brevity.py); здесь подсказки только КОРОТКИЕ ЯКОРЯ, чтобы не дублировать чужую работу;
  · содержание отдельных гардов guard-all.py (это их собственные приёмки, если есть);
    здесь важно ТОЛЬКО то, что краткий/полный вид ОДИНАКОВО честны про их исход;
  · «пул», «тебя ждут», «ты сдал» и прочие ДИНАМИЧЕСКИЕ разделы role-brief.py по
    содержанию — они читаются живыми данными контура, а не флагом --full;
  · конкурентную запись во временную копию базы (два процесса разом).

⛔ Живая база (<КОНТУР>/.mezosync/mezosync.db) НЕ изменяется: все прогоны — на
КОПИИ (mezo_stand.new + shutil.copy2). Копия каталога инструментов для нарочных поломок —
через mezo_stand.copy_tool (со всеми соседями по import), поломка (а) зовётся ВНЕ
контейнера и потому с переменной среды MEZO_CONTAINER (тот же приём, что у случая ⑱-бис
в bite-tool-brevity.py) — без неё модуль mezo_paths при запуске из копии не находит
mezosync.db и падает на самом импорте, до первой же проверки.

Флаг --keep — не убирать временные рабочие каталоги (для разбора вручную).
Без аргументов — полный прогон.

Дата: 2026-09-07 08:30 UTC. Карточка #593, задание 7.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

if "--keep" in sys.argv:
    os.environ.setdefault("MEZO_KEEP_STANDS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

SCRIPTS = mezo_paths.live_scripts(__file__)          # .mezosync/scripts (живой, только на чтение)
CONTAINER = mezo_paths.container_root(__file__)      # <КОНТУР>
LIVE_DB = mezo_paths.live_db(__file__)

BACKLOG = str(SCRIPTS / "backlog.py")
GUARD_ALL = str(SCRIPTS / "guard-all.py")
ROLE_BRIEF = str(SCRIPTS / "role-brief.py")

итог: list[tuple[str, bool]] = []


def случай(имя: str, ок: bool, слово: str) -> None:
    итог.append((имя, ок))
    print(f"{'✅' if ок else '🔴'} {имя}")
    print(f"   {слово}")


def run(tool: str, db: Path, *args: str, timeout: int = 180) -> tuple[int, str]:
    """Позвать инструмент с --db КОПИИ. Порядок «--db, затем подкоманда» — как у backlog.py."""
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_env(tool: str, db: Path, env: dict, *args: str, timeout: int = 180) -> tuple[int, str]:
    """Как run(), но с ЯВНЫМ окружением подпроцесса — нужен поломке (а): копия guard-all.py
    живёт ВНЕ контейнера, и mezo_paths внутри неё находит контейнер только по MEZO_CONTAINER."""
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def id_карточки(вывод: str) -> str | None:
    return вывод.split("backlog #")[1].split(" ")[0] if "backlog #" in вывод else None


def забыть_ключи(db: Path, role: str, keys: list[str]) -> None:
    c = sqlite3.connect(str(db))
    for k in keys:
        c.execute("DELETE FROM hint_seen WHERE role=? AND hint_key=?", (role, k))
    c.commit()
    c.close()


# ═══ ИЗВЛЕЧЕНИЕ КУСКОВ ВЫВОДА backlog.py list — ОДНИ И ТЕ ЖЕ ПРАВИЛА ДЛЯ ВСЕХ СЛУЧАЕВ ═══
CARD_RE = re.compile(r"^  (?:🎯)?#\d+ ")            # первая строка карточки: "  #123 ..." / "  🎯#123 ..."
DIGEST_RE = re.compile(r"^\s+🎯 ")                   # срез критерия: "        🎯 ..." (8 пробелов + ПРОБЕЛ после 🎯 — это и отличает от "🎯#" карточки)
REASON_RE = re.compile(r"^\s+(?:✗ причина:|🧊 )")     # причина dropped / условие frozen


def найти_шапку(вывод: str) -> str | None:
    return next((л for л in вывод.splitlines() if л.startswith("📋 backlog ")), None)


def найти_карточки(вывод: str) -> list[str]:
    return [л for л in вывод.splitlines() if CARD_RE.match(л)]


def найти_срезы(вывод: str) -> list[str]:
    return [л for л in вывод.splitlines() if DIGEST_RE.match(л)]


def найти_причины(вывод: str) -> list[str]:
    return [л for л in вывод.splitlines() if REASON_RE.match(л)]


def блок_пула(вывод: str) -> str | None:
    строки = вывод.splitlines()
    idx_карточка = next((i for i, л in enumerate(строки) if CARD_RE.match(л)), len(строки))
    область = строки[:idx_карточка]
    idx_пул = next((i for i, л in enumerate(область) if "пул" in л), None)
    if idx_пул is None:
        return None
    return "\n".join(область[idx_пул:idx_карточка])


def main() -> int:
    print("=" * 78)
    print("ПРИЁМКА КАРТОЧКИ #593 ЗАДАНИЕ 7 — краткий/полный вид: backlog list · guard-all · role-brief")
    print("живая база (только чтение, копируется): " + str(LIVE_DB))
    print("=" * 78)

    стенд = mezo_stand.new("bite-brief-views-")
    db = стенд / "copy.db"
    shutil.copy2(LIVE_DB, db)

    # ═══ ПОДГОТОВКА: 3 стендовые карточки роли PROTO ═══════════════════════════════
    # --track на заведомо НЕ-пуловое значение: если в копии живой базы окажется активный
    # пул, заведение БЕЗ --track увело бы новую карточку сразу в frozen (см. cmd_add) —
    # это сломало бы ожидание «одна карточка остаётся open». --track снимает эту
    # зависимость от текущего состояния живого пула целиком.
    TRACK = "bite-brief-views-stand"

    def файл(имя: str, текст: str) -> str:
        p = стенд / имя
        p.write_text(текст, encoding="utf-8")
        return str(p)

    _, out_o = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка открыта, с критерием",
                   "--body-file", файл("open_body.md", "тело стендовой карточки — остаётся open, есть критерий"),
                   "--done-when-file", файл("open_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_open = id_карточки(out_o)

    _, out_d = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка на dropped",
                   "--body-file", файл("dropped_body.md", "тело стендовой карточки — уйдёт в dropped"),
                   "--done-when-file", файл("dropped_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_dropped = id_карточки(out_d)
    rc_ds, out_ds = run(BACKLOG, db, "status", bid_dropped or "0", "dropped", "--actor", "PROTO",
                        "--note", "проба причины: стендовая отмена ради приёмки #593.7")

    _, out_f = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка на frozen",
                   "--body-file", файл("frozen_body.md", "тело стендовой карточки — уйдёт в frozen"),
                   "--done-when-file", файл("frozen_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_frozen = id_карточки(out_f)
    rc_fs, out_fs = run(BACKLOG, db, "status", bid_frozen or "0", "frozen", "--actor", "PROTO",
                        "--note", "разморозить: после закрытия стендовой приёмки #593.7")

    if not (bid_open and bid_dropped and bid_frozen) or rc_ds != 0 or rc_fs != 0:
        raise SystemExit(
            "ПРИЁМКА НЕ СОСТОЯЛАСЬ: подготовка стендовых карточек не удалась — "
            f"open={bid_open} dropped={bid_dropped}(rc={rc_ds}) frozen={bid_frozen}(rc={rc_fs})")

    # ═══ ①②③④⑤⑫ — backlog.py list: три вызова (кратко/кратко/--full) ═══════════════
    # Первый краткий вызов — ОН ЖЕ «краткий» для структурных случаев ①-⑤ (подсказка о
    # --full там показывается ЦЕЛИКОМ — case ⑫ проверяет это отдельно, случаям ①-⑤ до
    # содержимого хвоста дела нет). --full вызов — ОН ЖЕ «полный» для случаев ①-⑤ И
    # третий вызов case ⑫.
    забыть_ключи(db, "PROTO", ["backlog-list-full"])
    rc_b1, out_b1 = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO")
    rc_b2, out_b2 = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO")
    rc_bf, out_bf = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO", "--full")

    if rc_b1 != 0 or rc_b2 != 0 or rc_bf != 0:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: backlog.py list вернул код ≠0 — "
                         f"{rc_b1}/{rc_b2}/{rc_bf}")

    out_brief, out_full = out_b1, out_bf   # общие ссылки для случаев ①-⑤

    шапка_кратко, шапка_полно = найти_шапку(out_brief), найти_шапку(out_full)
    случай("① строка шапки «📋 backlog …» дословно одна и та же",
           шапка_кратко is not None and шапка_кратко == шапка_полно,
           f"кратко={шапка_кратко!r} полно={шапка_полно!r}")

    карточки_кратко, карточки_полно = найти_карточки(out_brief), найти_карточки(out_full)
    случай("② число и текст первых строк карточек равны попарно",
           len(карточки_кратко) > 0 and карточки_кратко == карточки_полно,
           f"кратко {len(карточки_кратко)} шт, полно {len(карточки_полно)} шт"
           + ("" if карточки_кратко == карточки_полно else "; тексты разошлись"))

    срезы_кратко, срезы_полно = найти_срезы(out_brief), найти_срезы(out_full)
    случай("③ срез критерия («🎯 …» второй строкой) отсутствует в кратком, есть в --full",
           len(срезы_кратко) == 0 and len(срезы_полно) > 0,
           f"кратко {len(срезы_кратко)} строк среза, полно {len(срезы_полно)} строк среза")

    причины_кратко, причины_полно = найти_причины(out_brief), найти_причины(out_full)
    случай("④ ВСТРЕЧНЫЙ: строки «✗ причина: …» / «🧊 …» дословно те же в обоих видах",
           len(причины_кратко) >= 2 and причины_кратко == причины_полно,
           f"кратко {причины_кратко!r} полно {причины_полно!r}")

    пул_кратко, пул_полно = блок_пула(out_brief), блок_пула(out_full)
    if пул_кратко is None and пул_полно is None:
        случай("⑤ блок пула — пула в копии нет, проверено отсутствие строки в обоих видах",
               True, "ни в кратком, ни в полном виде строки со словом «пул» нет")
    else:
        случай("⑤ блок пула (от строки со словом «пул» до первой карточки) дословно тот же",
               пул_кратко == пул_полно, f"кратко={пул_кратко!r} полно={пул_полно!r}")

    ПОЛНЫЙ_ХВОСТ_LIST = "ℹ️ срез критерия у карточек скрыт"
    ССЫЛКА_LIST = "ℹ️ подсказка «backlog-list-full» показана"
    полный_1, ссылка_1 = ПОЛНЫЙ_ХВОСТ_LIST in out_b1, ССЫЛКА_LIST in out_b1
    полный_2, ссылка_2 = ПОЛНЫЙ_ХВОСТ_LIST in out_b2, ССЫЛКА_LIST in out_b2
    полный_3, ссылка_3 = ПОЛНЫЙ_ХВОСТ_LIST in out_bf, ССЫЛКА_LIST in out_bf
    случай("⑫ подсказка о --full: 1-й краткий вызов — текст целиком, 2-й — строка-ссылка, "
           "--full — ни того ни другого",
           полный_1 and not ссылка_1 and ссылка_2 and not полный_2
           and not полный_3 and not ссылка_3,
           f"1й: целиком={полный_1}/ссылка={ссылка_1}; 2й: целиком={полный_2}/ссылка={ссылка_2}; "
           f"--full: целиком={полный_3}/ссылка={ссылка_3}")

    # ═══ ⑪ — role-brief.py: три вызова (кратко/кратко/--full), четыре постоянных хвоста ═
    ХВОСТ_КЛЮЧИ = ["role-brief-порядок-пробуждения", "role-brief-ритм",
                   "role-brief-свод-целиком", "role-brief-ответы-владельцу"]
    ХВОСТ_ЯКОРЯ = {
        "role-brief-порядок-пробуждения": "порядок пробуждения: гарды → наказ → память → лента → ПЕРВЫЙ",
        "role-brief-ритм": "РИТМ (слово владельца 29.08): будильник ВНУТРИ чата",
        "role-brief-свод-целиком": "в стартовую сводку не режется (граница в шапке)",
        "role-brief-ответы-владельцу": "ОТВЕТЫ ВЛАДЕЛЬЦУ: перед КАЖДЫМ ответом владельцу перечитай правило",
    }
    забыть_ключи(db, "PROTO", ХВОСТ_КЛЮЧИ)
    rc_r1, out_r1 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO")
    rc_r2, out_r2 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO")
    rc_r3, out_r3 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO", "--full")
    if rc_r1 != 0 or rc_r2 != 0 or rc_r3 != 0:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: role-brief.py вернул код ≠0 — "
                         f"{rc_r1}/{rc_r2}/{rc_r3}")

    def хвостовые_ключи(вывод: str) -> list[str]:
        return re.findall(r"ℹ️ подсказка «([^»]+)» показана", вывод)

    полны_1 = {k: a in out_r1 for k, a in ХВОСТ_ЯКОРЯ.items()}
    полны_2 = {k: a in out_r2 for k, a in ХВОСТ_ЯКОРЯ.items()}
    полны_3 = {k: a in out_r3 for k, a in ХВОСТ_ЯКОРЯ.items()}
    ссылки_1, ссылки_2, ссылки_3 = хвостовые_ключи(out_r1), хвостовые_ключи(out_r2), хвостовые_ключи(out_r3)

    def без_хвостов(вывод: str) -> list[str]:
        """Строки БЕЗ четырёх хвостов (целиком или ссылкой) — для построчного сравнения
        1-го и 2-го вызовов (остальное у них обязано совпасть дословно)."""
        исключить = lambda л: (any(a in л for a in ХВОСТ_ЯКОРЯ.values())
                               or "ℹ️ подсказка «" in л)
        return [л for л in вывод.splitlines() if not исключить(л)]

    остальное_совпадает = без_хвостов(out_r1) == без_хвостов(out_r2)
    случай("⑪ role-brief: 1-й вызов — четыре хвоста целиком, 2-й — четыре строки-ссылки, "
           "3-й (--full) — снова целиком; остальной вывод 1-го и 2-го совпадает построчно",
           all(полны_1.values()) and not ссылки_1
           and not any(полны_2.values()) and set(ссылки_2) == set(ХВОСТ_КЛЮЧИ) and len(ссылки_2) == 4
           and all(полны_3.values()) and not ссылки_3
           and остальное_совпадает,
           f"1й целиком: {sum(полны_1.values())}/4, ссылок: {len(ссылки_1)}; "
           f"2й целиком: {sum(полны_2.values())}/4, ссылок: {sorted(ссылки_2)}; "
           f"3й (--full) целиком: {sum(полны_3.values())}/4, ссылок: {len(ссылки_3)}; "
           f"остальной вывод совпадает: {остальное_совпадает}")

    # ═══ ⑥⑦⑧⑨⑩ — guard-all.py: кратко/полно с ЖИВОГО каталога <s>, на копии базы ═════
    # guard-all.py открывает базу mode=ro (см. его же --db в справке) — даже случайное
    # указание на живую базу не привело бы к записи, но копия здесь и не нужна как
    # предохранитель, а нужна как СТАБИЛЬНОЕ состояние: между кратким и полным вызовом
    # база не должна сама измениться (в живой она меняется постоянно).
    db_guard = стенд / "guard.db"
    shutil.copy2(LIVE_DB, db_guard)

    def run_guard(tool: str, db_: Path, full: bool, env: dict | None = None) -> tuple[int, str]:
        args = ["--db", str(db_)] + (["--full"] if full else [])
        p = subprocess.run([sys.executable, tool, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    rc_g1, out_g_brief = run_guard(GUARD_ALL, db_guard, full=False)
    rc_g2, out_g_full = run_guard(GUARD_ALL, db_guard, full=True)
    # rc может быть 1 (есть красное) — это НЕ провал приёмки, сказано в задании прямо.
    if rc_g1 not in (0, 1) or rc_g2 not in (0, 1):
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: guard-all.py вернул неожиданный код — "
                         f"{rc_g1}/{rc_g2}")

    def последняя_строка(вывод: str) -> str:
        for л in reversed(вывод.splitlines()):
            if л.strip():
                return л.strip()
        return ""

    def множество_с(вывод: str, *marks: str) -> set[str]:
        return {л for л in вывод.splitlines() if any(m in л for m in marks)}

    def сравнить_красные(вывод_кратко: str, вывод_полно: str) -> tuple[bool, set[str], set[str]]:
        a, b = множество_с(вывод_кратко, "⛔"), множество_с(вывод_полно, "⛔")
        return a == b, a, b

    посл_кратко, посл_полно = последняя_строка(out_g_brief), последняя_строка(out_g_full)
    m1 = re.search(r"\((\d+) проверок\)", посл_кратко)
    m2 = re.search(r"\((\d+) проверок\)", посл_полно)
    случай("⑥ последняя строка итога дословно одна и та же, с тем же «(N проверок)»",
           bool(посл_кратко) and посл_кратко == посл_полно and bool(m1) and bool(m2)
           and m1.group(1) == m2.group(1),
           f"кратко={посл_кратко!r} полно={посл_полно!r}")

    совпало_7, красные_кратко, красные_полно = сравнить_красные(out_g_brief, out_g_full)
    случай("⑦ множество строк с «⛔» одинаково между кратким и полным видом",
           совпало_7,
           f"кратко {len(красные_кратко)} строк, полно {len(красные_полно)} строк"
           + ("" if совпало_7 else f"; разница {красные_кратко ^ красные_полно}"))

    предупр_кратко = множество_с(out_g_brief, "⚠️", "ℹ️")
    предупр_полно = множество_с(out_g_full, "⚠️", "ℹ️")
    случай("⑧ множество строк с «⚠️» или «ℹ️» одинаково между кратким и полным видом",
           предупр_кратко == предупр_полно,
           f"кратко {len(предупр_кратко)} строк, полно {len(предупр_полно)} строк"
           + ("" if предупр_кратко == предупр_полно else f"; разница {предупр_кратко ^ предупр_полно}"))

    ПРОШЛИ_RE = re.compile(r"^✅ прошли (\d+): (.+)$")

    def строка_прошли(вывод: str):
        for л in вывод.splitlines():
            m = ПРОШЛИ_RE.match(л.strip())
            if m:
                return int(m.group(1)), [и.strip() for и in m.group(2).split(" · ")]
        return None

    def зелёные_сразу(вывод: str) -> list[str]:
        имена = []
        for л in вывод.splitlines():
            if (л.startswith("✅ ") and not л.startswith("✅ мост соседей")
                    and not л.startswith("✅ прошли") and not л.startswith("✅ ВСЕ ГАРДЫ")):
                имена.append(л[2:].strip())
        return имена

    прошли = строка_прошли(out_g_brief)
    сразу_кратко = зелёные_сразу(out_g_brief)
    сразу_полно = зелёные_сразу(out_g_full)
    объединение = (set(прошли[1]) if прошли else set()) | set(сразу_кратко)
    N_прошли = прошли[0] if прошли else None
    случай("⑨ «✅ прошли N: …» ∪ имена сразу-зелёных строк (кратко, без строк моста) = "
           "имена сразу-зелёных строк (полно, без строк моста); N = числу имён",
           прошли is not None and N_прошли == len(прошли[1])
           and объединение == set(сразу_полно),
           f"строка «прошли» есть: {прошли is not None}"
           + (f", N={N_прошли}, имён в ней {len(прошли[1]) if прошли else 0}" if прошли else "")
           + f"; объединение (кратко) {len(объединение)} имён, сразу-зелёных (полно) {len(сразу_полно)} имён"
           + ("" if объединение == set(сразу_полно) else f"; разница {объединение ^ set(сразу_полно)}"))

    МОСТ_СВОДКА_RE = re.compile(r"^✅ мост соседей: (\d+) вопросов отвечены \(соседей (\d+)\)$")

    def мост_сводка(вывод: str):
        for л in вывод.splitlines():
            m = МОСТ_СВОДКА_RE.match(л.strip())
            if m:
                return int(m.group(1)), int(m.group(2))
        return None

    def мост_отвечено_строк(вывод: str) -> int:
        return sum(1 for л in вывод.splitlines() if "отвечен НАШИМ ответом" in л)

    сводка10 = мост_сводка(out_g_brief)
    отвечено_полно10 = мост_отвечено_строк(out_g_full)
    if сводка10 is None and отвечено_полно10 == 0:
        случай("⑩ мост соседей — вопросов нет вовсе, равенство «нет в обоих видах»",
               True, "ни сводной строки в кратком, ни строк «отвечен НАШИМ ответом» в полном")
    else:
        N10 = сводка10[0] if сводка10 else None
        случай("⑩ «✅ мост соседей: N вопросов отвечены» — N равно числу строк «отвечен "
               "НАШИМ ответом» в --full",
               сводка10 is not None and N10 == отвечено_полно10,
               f"N в кратком={N10 if сводка10 else 'строки нет'}, строк «отвечен» в полном="
               f"{отвечено_полно10}")

    # ═══ ПОЛОМКА (а) — guard-all.py: check() без учёта `ok` в кратком виде ═════════════
    # Копия ЖИВЁТ ВНЕ КОНТЕЙНЕРА (%TEMP%), а `SCRIPTS = Path(__file__).resolve().parent`
    # внутри guard-all.py — жёсткий путь ОТ РАСПОЛОЖЕНИЯ ФАЙЛА: соседние guard-*.py рядом
    # с копией не лежат, и sub_guard() честно отвечает «гард не найден» — то есть
    # РЕАЛЬНЫМИ красными проверками (RESULTS с ok=False), а не подставными. Это и даёт
    # случаю ⑦ на что краснеть, без изменения базы. MEZO_CONTAINER чинит остальное
    # (mezo_paths.container_root/default_db резолвятся по нему, а не подъёмом по дереву,
    # которого от копии в %TEMP% и быть не может) — без него сама копия падает на
    # импорте раньше первой проверки.
    сломанный_стенд_a = mezo_stand.new("bite-brief-views-broken-guard-")
    сломанный_a = mezo_stand.copy_tool(Path(GUARD_ALL), сломанный_стенд_a)
    текст_a = сломанный_a.read_text(encoding="utf-8")
    АНКОР_A = "    if ok and not FULL and not force_print:"
    if АНКОР_A not in текст_a:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь строки check() не найден в "
                         "guard-all.py — поломку (а) ставить не на чем")
    испорченный_a = текст_a.replace(АНКОР_A, "    if not FULL and not force_print:", 1)
    if испорченный_a == текст_a:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена (а) не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    сломанный_a.write_text(испорченный_a, encoding="utf-8")

    env_a = os.environ.copy()
    env_a["MEZO_CONTAINER"] = str(CONTAINER)
    rc_a1, out_a_brief = run_guard(str(сломанный_a), db_guard, full=False, env=env_a)
    rc_a2, out_a_full = run_guard(str(сломанный_a), db_guard, full=True, env=env_a)
    совпало_a, набор_a1, набор_a2 = сравнить_красные(out_a_brief, out_a_full)
    покрасила_a = not совпало_a
    случай("поломка (а): check() без учёта ok в кратком виде → случай ⑦ на этой копии "
           "ОБЯЗАН покраснеть",
           покрасила_a,
           ("поломка (а) покрасила: да — " if покрасила_a else
            "🔴 поломка (а) покрасила: нет — приёмка не ловит эту беду; ")
           + f"кратко {len(набор_a1)} красных строк, полно {len(набор_a2)}")
    mezo_stand.release(сломанный_стенд_a)

    # ═══ ПОЛОМКА (б) — backlog.py: cmd_list пропускает frozen-карточку в кратком виде ═══
    # 🪤 ПЕРЕМЕРЕНО ПЕРЕД ПРАВКОЙ, А НЕ ДОГАДКОЙ: --db у нас АБСОЛЮТНЫЙ, и resolve_db
    # с абсолютным --db корень контейнера НЕ ищет — но resolve_db всё равно БЕЗУСЛОВНО
    # зовёт `lease.check(db, script_file, ...)`, а тот сам просит каталог группы (через
    # mezo_paths.live_db() БЕЗ script_file — см. докстринг mezo_paths.py, «каталог
    # вызывающего идёт первым»). Отказ lease — SystemExit, и resolve_db его явно
    # ПЕРЕПРОБРАСЫВАЕТ (`except SystemExit: raise`), а не глотает. Живой прогон это
    # подтвердил: копия backlog.py list БЕЗ MEZO_CONTAINER падает на «контейнер группы
    # НЕ НАЙДЕН» ДО первой печатаемой строки — картотека карточек тут ни при чём, и без
    # починки поломка (б) была бы неотличима от «инструмент вообще не запустился».
    сломанный_стенд_b = mezo_stand.new("bite-brief-views-broken-backlog-")
    сломанный_b = mezo_stand.copy_tool(Path(BACKLOG), сломанный_стенд_b)
    текст_b = сломанный_b.read_text(encoding="utf-8")
    АНКОР_B = '        print(f"  {pool_mark}#{bid} {icon.get(status,\'?\')} {pr}{mark} {title}{shared}  {tg}")'
    if АНКОР_B not in текст_b:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь строки печати карточки не найден в "
                         "backlog.py — поломку (б) ставить не на чем")
    испорченный_b = текст_b.replace(
        АНКОР_B,
        '        if not a.full and status == "frozen":\n            continue\n' + АНКОР_B, 1)
    if испорченный_b == текст_b:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена (б) не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    сломанный_b.write_text(испорченный_b, encoding="utf-8")

    env_b = os.environ.copy()
    env_b["MEZO_CONTAINER"] = str(CONTAINER)
    rc_b_brief, out_b_brief_broken = run_env(str(сломанный_b), db, env_b, "list", "--role", "PROTO",
                                             "--status", "all", "--actor", "PROTO")
    rc_b_full, out_b_full_broken = run_env(str(сломанный_b), db, env_b, "list", "--role", "PROTO",
                                           "--status", "all", "--actor", "PROTO", "--full")
    карточки_b_кратко = найти_карточки(out_b_brief_broken)
    карточки_b_полно = найти_карточки(out_b_full_broken)
    if not карточки_b_кратко and not карточки_b_полно:
        raise SystemExit(
            "ПРИЁМКА НЕ СОСТОЯЛАСЬ: копия backlog.py с поломкой (б) не напечатала НИ ОДНОЙ "
            "карточки ни в кратком, ни в полном виде — это отказ ЗАПУСКА (окружение/путь), "
            "а не сигнал поломки; исход неотличим от «не поймала». Вывод кратко: "
            f"{out_b_brief_broken[:300]!r}")
    покрасила_b = карточки_b_кратко != карточки_b_полно
    случай("поломка (б): cmd_list пропускает frozen-карточку в кратком виде → случай ② "
           "на этой копии ОБЯЗАН покраснеть",
           покрасила_b,
           ("поломка (б) покрасила: да — " if покрасила_b else
            "🔴 поломка (б) покрасила: нет — приёмка не ловит эту беду; ")
           + f"кратко {len(карточки_b_кратко)} карточек, полно {len(карточки_b_полно)}")
    mezo_stand.release(сломанный_стенд_b)

    mezo_stand.release(стенд)

    print("")
    print("=" * 78)
    красных = [и for и, ок in итог if not ок]
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(итог)} (①…⑫ + поломки (а) и (б))")
    print("⚖️ ГРАНИЦА: дословный текст подсказок mezo_hints, содержание отдельных гардов "
          "guard-all.py и динамические разделы role-brief.py этой приёмкой НЕ проверяются.")
    if красных:
        print(f"🔴 ПРОВАЛЕНО {len(красных)}: {' · '.join(красных)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
