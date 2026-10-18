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
ПОДСТАВНОЙ базе (mezo_stand.empty_db: схема живой без строк — этап Э6, карточка #680); роль
PROTO, два правила свода, от которых зависит форма хвостов role-brief.py, и набор задач для
блока пула приёмка сажает сама (seed_stand). Соседей для сводки моста (⑩) guard-all.py берёт
из таблицы cross_links — её строки подставная база guard-all.py берёт из живой (keep): письма
соседей лежат на диске контура, подделать их дороже самого случая. ⚖️ Граница: на контуре без
соседей ⑩ судит ветку «вопросов нет вовсе». Копия каталога инструментов для нарочных поломок —
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

results: list[tuple[str, bool]] = []


def case(name: str, ok: bool, word: str) -> None:
    results.append((name, ok))
    print(f"{'✅' if ok else '🔴'} {name}")
    print(f"   {word}")


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


def card_id(output: str) -> str | None:
    return output.split("backlog #")[1].split(" ")[0] if "backlog #" in output else None


def forget_keys(db: Path, role: str, keys: list[str]) -> None:
    c = sqlite3.connect(str(db))
    for k in keys:
        c.execute("DELETE FROM hint_seen WHERE role=? AND hint_key=?", (role, k))
    c.commit()
    c.close()


# ═══ ИЗВЛЕЧЕНИЕ КУСКОВ ВЫВОДА backlog.py list — ОДНИ И ТЕ ЖЕ ПРАВИЛА ДЛЯ ВСЕХ СЛУЧАЕВ ═══
CARD_RE = re.compile(r"^  (?:🎯)?#\d+ ")            # первая строка карточки: "  #123 ..." / "  🎯#123 ..."
DIGEST_RE = re.compile(r"^\s+🎯 ")                   # срез критерия: "        🎯 ..." (8 пробелов + ПРОБЕЛ после 🎯 — это и отличает от "🎯#" карточки)
REASON_RE = re.compile(r"^\s+(?:✗ причина:|🧊 )")     # причина dropped / условие frozen


def find_header(output: str) -> str | None:
    return next((line for line in output.splitlines() if line.startswith("📋 backlog ")), None)


def find_cards(output: str) -> list[str]:
    return [line for line in output.splitlines() if CARD_RE.match(line)]


def find_slices(output: str) -> list[str]:
    return [line for line in output.splitlines() if DIGEST_RE.match(line)]


def find_reasons(output: str) -> list[str]:
    return [line for line in output.splitlines() if REASON_RE.match(line)]


def pool_block(output: str) -> str | None:
    lines = output.splitlines()
    idx_card = next((i for i, line in enumerate(lines) if CARD_RE.match(line)), len(lines))
    scope = lines[:idx_card]
    idx_pool = next((i for i, line in enumerate(scope) if "пул" in line), None)
    if idx_pool is None:
        return None
    return "\n".join(scope[idx_pool:idx_card])


# Правила свода, от которых зависит ФОРМА хвостов role-brief.py (случай ⑪): «ответы владельцу»
# печатается под подсказкой, только если owner-reply-format действует; у «ритма» три формы по
# состоянию sync-alarm-in-chat. До Э6 их брали из свода ЭТОГО контура; на подставной базе свода
# нет вовсе, и ⑪ судил бы форму «правила нет» у обоих. Сажаем состояние живого свода на 18.10:
# owner-reply-format действует, sync-alarm-in-chat снято (решение владельца 24.09, записка #5312).
STAND_RULES = [
    ("owner-reply-format", "форма ответа владельцу (посажено приёмкой #593.7 на подставную базу)",
     "active", None, None, None),
    ("sync-alarm-in-chat", "ритм сверок будильником в чате (посажено приёмкой #593.7 на подставную базу)",
     "revoked", "2026-09-24 00:00:00", "PROTO", "посажено снятым: так стоит в живом своде (записка #5312)"),
]


# Набор задач (пул) для случая ⑤: до Э6 блок пула в выводе backlog.py list давали живые наборы
# контура; на подставной базе наборов нет, и ⑤ судил бы ветку «пула нет». Один живой набор —
# норма нового порядка; карточки приёмки идут с --track вне его и потому не замерзают (cmd_add).
STAND_POOL = ("ZZPOOL-BRIEF", "набор подставной базы приёмки #593.7: блок пула для случая ⑤")


def seed_stand(db: Path) -> None:
    c = sqlite3.connect(str(db))
    with c:
        c.executemany("INSERT INTO rules (rule_key, body, status, revoked_at, revoked_by, revoked_reason)"
                      " VALUES (?, ?, ?, ?, ?, ?)", STAND_RULES)
        c.execute("INSERT INTO tracks (track_id, title, status) VALUES (?, ?, 'active')", STAND_POOL)
    c.close()


def main() -> int:
    print("=" * 78)
    print("ПРИЁМКА КАРТОЧКИ #593 ЗАДАНИЕ 7 — краткий/полный вид: backlog list · guard-all · role-brief")
    print("живая база (только чтение, берётся схема): " + str(LIVE_DB))
    print("=" * 78)

    stand = mezo_stand.new("bite-brief-views-")
    db = stand / "copy.db"
    mezo_stand.empty_db(LIVE_DB, db)
    mezo_stand.seed_roles(db, ["PROTO"])
    seed_stand(db)

    # ═══ ПОДГОТОВКА: 3 стендовые карточки роли PROTO ═══════════════════════════════
    # --track на заведомо НЕ-пуловое значение: если в базе окажется активный
    # пул, заведение БЕЗ --track увело бы новую карточку сразу в frozen (см. cmd_add) —
    # это сломало бы ожидание «одна карточка остаётся open». --track снимает эту
    # зависимость от текущего состояния живого пула целиком.
    TRACK = "bite-brief-views-stand"

    def file(name: str, note_text: str) -> str:
        p = stand / name
        p.write_text(note_text, encoding="utf-8")
        return str(p)

    _, out_o = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка открыта, с критерием",
                   "--body-file", file("open_body.md", "тело стендовой карточки — остаётся open, есть критерий"),
                   "--done-when-file", file("open_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_open = card_id(out_o)

    _, out_d = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка на dropped",
                   "--body-file", file("dropped_body.md", "тело стендовой карточки — уйдёт в dropped"),
                   "--done-when-file", file("dropped_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_dropped = card_id(out_d)
    rc_ds, out_ds = run(BACKLOG, db, "status", bid_dropped or "0", "dropped", "--actor", "PROTO",
                        "--note", "проба причины: стендовая отмена ради приёмки #593.7")

    _, out_f = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--track", TRACK,
                   "--title", "приёмка 593.7: карточка на frozen",
                   "--body-file", file("frozen_body.md", "тело стендовой карточки — уйдёт в frozen"),
                   "--done-when-file", file("frozen_done.md", "стендовый критерий приёмки: сам не судится"))
    bid_frozen = card_id(out_f)
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
    forget_keys(db, "PROTO", ["backlog-list-full"])
    rc_b1, out_b1 = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO")
    rc_b2, out_b2 = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO")
    rc_bf, out_bf = run(BACKLOG, db, "list", "--role", "PROTO", "--status", "all", "--actor", "PROTO", "--full")

    if rc_b1 != 0 or rc_b2 != 0 or rc_bf != 0:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: backlog.py list вернул код ≠0 — "
                         f"{rc_b1}/{rc_b2}/{rc_bf}")

    out_brief, out_full = out_b1, out_bf   # общие ссылки для случаев ①-⑤

    header_brief, header_full = find_header(out_brief), find_header(out_full)
    case("① строка шапки «📋 backlog …» дословно одна и та же",
           header_brief is not None and header_brief == header_full,
           f"кратко={header_brief!r} полно={header_full!r}")

    cards_brief, cards_full = find_cards(out_brief), find_cards(out_full)
    case("② число и текст первых строк карточек равны попарно",
           len(cards_brief) > 0 and cards_brief == cards_full,
           f"кратко {len(cards_brief)} шт, полно {len(cards_full)} шт"
           + ("" if cards_brief == cards_full else "; тексты разошлись"))

    slices_brief, slices_full = find_slices(out_brief), find_slices(out_full)
    case("③ срез критерия («🎯 …» второй строкой) отсутствует в кратком, есть в --full",
           len(slices_brief) == 0 and len(slices_full) > 0,
           f"кратко {len(slices_brief)} строк среза, полно {len(slices_full)} строк среза")

    reasons_brief, reasons_full = find_reasons(out_brief), find_reasons(out_full)
    case("④ ВСТРЕЧНЫЙ: строки «✗ причина: …» / «🧊 …» дословно те же в обоих видах",
           len(reasons_brief) >= 2 and reasons_brief == reasons_full,
           f"кратко {reasons_brief!r} полно {reasons_full!r}")

    pool_brief, pool_full = pool_block(out_brief), pool_block(out_full)
    if pool_brief is None and pool_full is None:
        case("⑤ блок пула — пула в копии нет, проверено отсутствие строки в обоих видах",
               True, "ни в кратком, ни в полном виде строки со словом «пул» нет")
    else:
        case("⑤ блок пула (от строки со словом «пул» до первой карточки) дословно тот же",
               pool_brief == pool_full, f"кратко={pool_brief!r} полно={pool_full!r}")

    FULL_TAIL_LIST = "ℹ️ срез критерия у карточек скрыт"
    LINK_LIST = "ℹ️ подсказка «backlog-list-full» показана"
    full_1, link_1 = FULL_TAIL_LIST in out_b1, LINK_LIST in out_b1
    full_2, link_2 = FULL_TAIL_LIST in out_b2, LINK_LIST in out_b2
    full_3, link_3 = FULL_TAIL_LIST in out_bf, LINK_LIST in out_bf
    case("⑫ подсказка о --full: 1-й краткий вызов — текст целиком, 2-й — строка-ссылка, "
           "--full — ни того ни другого",
           full_1 and not link_1 and link_2 and not full_2
           and not full_3 and not link_3,
           f"1й: целиком={full_1}/ссылка={link_1}; 2й: целиком={full_2}/ссылка={link_2}; "
           f"--full: целиком={full_3}/ссылка={link_3}")

    # ═══ ⑪ — role-brief.py: три вызова (кратко/кратко/--full), четыре постоянных хвоста ═
    # ⚡ ПРАВКА (карточка #659, приёмка отстала от продукта — не продукт сломан). «Ритм» —
    # ЕДИНСТВЕННЫЙ из четырёх хвостов, чья ФОРМА зависит от правила sync-alarm-in-chat,
    # а не только от того, видел ли его role-brief.py раньше: владелец снял это правило
    # решением 2026-09-24 («Весь план», записка #5312, см. функцию ритм() в role-brief.py) —
    # эта приёмка написана 2026-09-07, раньше того решения. Пока правило снято (или его
    # вовсе нет в своде), role-brief.py возвращается РАНЬШЕ строки с _HINT_ и печатает ОДНУ
    # строку НАПРЯМУЮ — без hint-механизма вовсе, никогда не сжимая её в ссылку. Старый
    # якорь «РИТМ (слово владельца 29.08)…» тогда не появляется НИ В ОДНОМ из трёх вызовов —
    # это не потеря хвоста, а другая, тоже проверяемая форма. Три формы взаимно исключают
    # друг друга — какая из них в силе, эта приёмка узнаёт по ФАКТИЧЕСКОМУ тексту 1-го
    # вызова (то же самое видит и живой владелец), а не гадает по имени правила в базе.
    TAIL_KEYS = ["role-brief-порядок-пробуждения", "role-brief-ритм",
                   "role-brief-свод-целиком", "role-brief-ответы-владельцу"]
    STANDING_ANCHORS = {
        "role-brief-порядок-пробуждения": "порядок пробуждения: гарды → наказ → память → лента → ПЕРВЫЙ",
        "role-brief-свод-целиком": "в стартовую сводку не режется (граница в шапке)",
        "role-brief-ответы-владельцу": "ОТВЕТЫ ВЛАДЕЛЬЦУ: перед КАЖДЫМ ответом владельцу перечитай правило",
    }
    RHYTHM_ACTIVE = "РИТМ (слово владельца 29.08): будильник ВНУТРИ чата"
    RHYTHM_REVOKED = "будильника сверок нет — правило sync-alarm-in-chat снято"
    RHYTHM_NOT_IN_RULES = "правила sync-alarm-in-chat в своде НЕТ"
    RHYTHM_TEXTS = (RHYTHM_ACTIVE, RHYTHM_REVOKED, RHYTHM_NOT_IN_RULES)

    forget_keys(db, "PROTO", TAIL_KEYS)
    rc_r1, out_r1 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO")
    rc_r2, out_r2 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO")
    rc_r3, out_r3 = run(ROLE_BRIEF, db, "--role", "PROTO", "--actor", "PROTO", "--full")
    if rc_r1 != 0 or rc_r2 != 0 or rc_r3 != 0:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: role-brief.py вернул код ≠0 — "
                         f"{rc_r1}/{rc_r2}/{rc_r3}")

    def tail_keys(output: str) -> list[str]:
        return re.findall(r"ℹ️ подсказка «([^»]+)» показана", output)

    are_full_1 = {k: a in out_r1 for k, a in STANDING_ANCHORS.items()}
    are_full_2 = {k: a in out_r2 for k, a in STANDING_ANCHORS.items()}
    are_full_3 = {k: a in out_r3 for k, a in STANDING_ANCHORS.items()}
    links_1, links_2, links_3 = tail_keys(out_r1), tail_keys(out_r2), tail_keys(out_r3)
    plain_links_1 = set(links_1) & set(STANDING_ANCHORS)
    plain_links_2 = set(links_2) & set(STANDING_ANCHORS)
    plain_links_3 = set(links_3) & set(STANDING_ANCHORS)

    rhythm_text_1 = next((text_item for text_item in RHYTHM_TEXTS if text_item in out_r1), None)
    if rhythm_text_1 == RHYTHM_ACTIVE:
        # старое поведение: тот же hint-цикл, что и у трёх других постоянных хвостов
        rhythm_ok = (RHYTHM_ACTIVE in out_r1 and "role-brief-ритм" not in links_1
                   and RHYTHM_ACTIVE not in out_r2 and "role-brief-ритм" in links_2
                   and RHYTHM_ACTIVE in out_r3 and "role-brief-ритм" not in links_3)
        expect_link_2 = {"role-brief-ритм"}
        rhythm_word = "ритм: правило активно — хвост под hint, как и три других"
    elif rhythm_text_1 in (RHYTHM_REVOKED, RHYTHM_NOT_IN_RULES):
        # ⚖️ У этой формы hint не заводится СОВСЕМ — строка обязана быть ОДИНАКОВОЙ во
        # ВСЕХ трёх вызовах и НИКОГДА не сжиматься в ссылку: сжатие того, что сжиматься
        # не должно, было бы равносильно «съеданием причины» (граница из шапки приёмки).
        rhythm_ok = (rhythm_text_1 in out_r1 and rhythm_text_1 in out_r2 and rhythm_text_1 in out_r3
                   and "role-brief-ритм" not in links_1
                   and "role-brief-ритм" not in links_2
                   and "role-brief-ритм" not in links_3)
        expect_link_2 = set()
        rhythm_word = (f"ритм: правило {'снято' if rhythm_text_1 == RHYTHM_REVOKED else 'не в своде'} — "
                      "строка прямая, без hint, обязана быть в КАЖДОМ из трёх вызовов")
    else:
        rhythm_ok = False
        expect_link_2 = set()
        rhythm_word = ("⛔ ни одна из трёх известных форм раздела «ритм» не найдена в 1-м "
                      "вызове — role-brief.py менялся, правь приёмку")

    def without_tails(output: str) -> list[str]:
        """Строки БЕЗ четырёх хвостов (целиком или ссылкой) — для построчного сравнения
        1-го и 2-го вызовов (остальное у них обязано совпасть дословно)."""
        exclude = lambda line: (any(a in line for a in STANDING_ANCHORS.values())
                               or any(text_item in line for text_item in RHYTHM_TEXTS)
                               or "ℹ️ подсказка «" in line)
        return [line for line in output.splitlines() if not exclude(line)]

    rest_matches = without_tails(out_r1) == without_tails(out_r2)
    case("⑪ role-brief: 1-й вызов — постоянные хвосты целиком, 2-й — строками-ссылками "
           "(кроме «ритм», если его правило снято — тогда он прямой во всех трёх), "
           "3-й (--full) — снова целиком; остальной вывод 1-го и 2-го совпадает построчно",
           all(are_full_1.values()) and not plain_links_1
           and not any(are_full_2.values()) and plain_links_2 == set(STANDING_ANCHORS)
           and all(are_full_3.values()) and not plain_links_3
           and rhythm_ok and rest_matches
           and (set(links_2) & {"role-brief-ритм"}) == expect_link_2,
           f"1й целиком: {sum(are_full_1.values())}/3 (+ритм: {rhythm_text_1 == RHYTHM_ACTIVE}), "
           f"ссылок обычных: {len(plain_links_1)}; "
           f"2й целиком: {sum(are_full_2.values())}/3, ссылок обычных: {sorted(plain_links_2)}; "
           f"3й (--full) целиком: {sum(are_full_3.values())}/3, ссылок обычных: {len(plain_links_3)}; "
           f"{rhythm_word}; остальной вывод совпадает: {rest_matches}")

    # ═══ ⑥⑦⑧⑨⑩ — guard-all.py: кратко/полно с ЖИВОГО каталога <s>, на копии базы ═════
    # guard-all.py открывает базу mode=ro (см. его же --db в справке) — даже случайное
    # указание на живую базу не привело бы к записи, но копия здесь и не нужна как
    # предохранитель, а нужна как СТАБИЛЬНОЕ состояние: между кратким и полным вызовом
    # база не должна сама измениться (в живой она меняется постоянно).
    db_guard = stand / "guard.db"
    mezo_stand.empty_db(LIVE_DB, db_guard, keep=("cross_links",))
    mezo_stand.seed_roles(db_guard, ["PROTO"])
    seed_stand(db_guard)

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

    def last_line(output: str) -> str:
        for line in reversed(output.splitlines()):
            if line.strip():
                return line.strip()
        return ""

    # ⚡ Возраст письма соседа в конце строки моста («… — 1255 ч») считается от «сейчас» при КАЖДОМ
    # вызове: краткий и полный вызов по разные стороны смены часа дали 1255 и 1256 ч, и ⑦ провалился
    # без всякой разницы видов (набор ядра Р4, 2026-10-18 18:05 UTC, карточка #680). Число часов
    # в конце строки сравнивается как «N ч»; остальной текст строки — дословно.
    AGE_TAIL = re.compile(r"(— )\d+( ч)$")

    def set_with(output: str, *marks: str) -> set[str]:
        return {AGE_TAIL.sub(r"\1N\2", line) for line in output.splitlines() if any(m in line for m in marks)}

    def compare_failed(output_brief: str, output_full: str) -> tuple[bool, set[str], set[str]]:
        a, b = set_with(output_brief, "⛔"), set_with(output_full, "⛔")
        return a == b, a, b

    last_brief, last_full = last_line(out_g_brief), last_line(out_g_full)
    m1 = re.search(r"\((\d+) проверок\)", last_brief)
    m2 = re.search(r"\((\d+) проверок\)", last_full)
    case("⑥ последняя строка итога дословно одна и та же, с тем же «(N проверок)»",
           bool(last_brief) and last_brief == last_full and bool(m1) and bool(m2)
           and m1.group(1) == m2.group(1),
           f"кратко={last_brief!r} полно={last_full!r}")

    matched_7, failed_brief, failed_full = compare_failed(out_g_brief, out_g_full)
    case("⑦ множество строк с «⛔» одинаково между кратким и полным видом",
           matched_7,
           f"кратко {len(failed_brief)} строк, полно {len(failed_full)} строк"
           + ("" if matched_7 else f"; разница {failed_brief ^ failed_full}"))

    warn_brief = set_with(out_g_brief, "⚠️", "ℹ️")
    warn_full = set_with(out_g_full, "⚠️", "ℹ️")
    case("⑧ множество строк с «⚠️» или «ℹ️» одинаково между кратким и полным видом",
           warn_brief == warn_full,
           f"кратко {len(warn_brief)} строк, полно {len(warn_full)} строк"
           + ("" if warn_brief == warn_full else f"; разница {warn_brief ^ warn_full}"))

    PASSED_RE = re.compile(r"^✅ прошли (\d+): (.+)$")

    def passed_line(output: str):
        for line in output.splitlines():
            m = PASSED_RE.match(line.strip())
            if m:
                return int(m.group(1)), [item.strip() for item in m.group(2).split(" · ")]
        return None

    def passed_at_once(output: str) -> list[str]:
        names = []
        for line in output.splitlines():
            if (line.startswith("✅ ") and not line.startswith("✅ мост соседей")
                    and not line.startswith("✅ прошли") and not line.startswith("✅ ВСЕ ГАРДЫ")):
                names.append(line[2:].strip())
        return names

    passed = passed_line(out_g_brief)
    at_once_brief = passed_at_once(out_g_brief)
    at_once_full = passed_at_once(out_g_full)
    union = (set(passed[1]) if passed else set()) | set(at_once_brief)
    n_passed = passed[0] if passed else None
    case("⑨ «✅ прошли N: …» ∪ имена сразу-зелёных строк (кратко, без строк моста) = "
           "имена сразу-зелёных строк (полно, без строк моста); N = числу имён",
           passed is not None and n_passed == len(passed[1])
           and union == set(at_once_full),
           f"строка «прошли» есть: {passed is not None}"
           + (f", N={n_passed}, имён в ней {len(passed[1]) if passed else 0}" if passed else "")
           + f"; объединение (кратко) {len(union)} имён, сразу-зелёных (полно) {len(at_once_full)} имён"
           + ("" if union == set(at_once_full) else f"; разница {union ^ set(at_once_full)}"))

    BRIDGE_SUMMARY_RE = re.compile(r"^✅ мост соседей: (\d+) вопросов отвечены \(соседей (\d+)\)$")

    def bridge_summary(output: str):
        for line in output.splitlines():
            m = BRIDGE_SUMMARY_RE.match(line.strip())
            if m:
                return int(m.group(1)), int(m.group(2))
        return None

    def bridge_answered_lines(output: str) -> int:
        return sum(1 for line in output.splitlines() if "отвечен НАШИМ ответом" in line)

    summary10 = bridge_summary(out_g_brief)
    answered_full10 = bridge_answered_lines(out_g_full)
    if summary10 is None and answered_full10 == 0:
        case("⑩ мост соседей — вопросов нет вовсе, равенство «нет в обоих видах»",
               True, "ни сводной строки в кратком, ни строк «отвечен НАШИМ ответом» в полном")
    else:
        N10 = summary10[0] if summary10 else None
        case("⑩ «✅ мост соседей: N вопросов отвечены» — N равно числу строк «отвечен "
               "НАШИМ ответом» в --full",
               summary10 is not None and N10 == answered_full10,
               f"N в кратком={N10 if summary10 else 'строки нет'}, строк «отвечен» в полном="
               f"{answered_full10}")

    # ═══ ПОЛОМКА (а) — guard-all.py: check() без учёта `ok` в кратком виде ═════════════
    # Копия ЖИВЁТ ВНЕ КОНТЕЙНЕРА (%TEMP%), а `SCRIPTS = Path(__file__).resolve().parent`
    # внутри guard-all.py — жёсткий путь ОТ РАСПОЛОЖЕНИЯ ФАЙЛА: соседние guard-*.py рядом
    # с копией не лежат, и sub_guard() честно отвечает «гард не найден» — то есть
    # РЕАЛЬНЫМИ красными проверками (RESULTS с ok=False), а не подставными. Это и даёт
    # случаю ⑦ на что краснеть, без изменения базы. MEZO_CONTAINER чинит остальное
    # (mezo_paths.container_root/default_db резолвятся по нему, а не подъёмом по дереву,
    # которого от копии в %TEMP% и быть не может) — без него сама копия падает на
    # импорте раньше первой проверки.
    broken_stand_a = mezo_stand.new("bite-brief-views-broken-guard-")
    broken_a = mezo_stand.copy_tool(Path(GUARD_ALL), broken_stand_a)
    text_a = broken_a.read_text(encoding="utf-8")
    ANCHOR_A = "    if ok and not FULL and not force_print:"
    if ANCHOR_A not in text_a:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь строки check() не найден в "
                         "guard-all.py — поломку (а) ставить не на чем")
    spoiled_a = text_a.replace(ANCHOR_A, "    if not FULL and not force_print:", 1)
    if spoiled_a == text_a:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена (а) не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    broken_a.write_text(spoiled_a, encoding="utf-8")

    env_a = os.environ.copy()
    env_a["MEZO_CONTAINER"] = str(CONTAINER)
    rc_a1, out_a_brief = run_guard(str(broken_a), db_guard, full=False, env=env_a)
    rc_a2, out_a_full = run_guard(str(broken_a), db_guard, full=True, env=env_a)
    matched_a, set_a1, set_a2 = compare_failed(out_a_brief, out_a_full)
    flagged_a = not matched_a
    case("поломка (а): check() без учёта ok в кратком виде → случай ⑦ на этой копии "
           "ОБЯЗАН покраснеть",
           flagged_a,
           ("поломка (а) покрасила: да — " if flagged_a else
            "🔴 поломка (а) покрасила: нет — приёмка не ловит эту беду; ")
           + f"кратко {len(set_a1)} красных строк, полно {len(set_a2)}")
    mezo_stand.release(broken_stand_a)

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
    broken_stand_b = mezo_stand.new("bite-brief-views-broken-backlog-")
    broken_b = mezo_stand.copy_tool(Path(BACKLOG), broken_stand_b)
    text_b = broken_b.read_text(encoding="utf-8")
    ANCHOR_B = '        print(f"  {pool_mark}#{bid} {icon.get(status,\'?\')} {pr}{mark} {title}{shared}  {tg}")'
    if ANCHOR_B not in text_b:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь строки печати карточки не найден в "
                         "backlog.py — поломку (б) ставить не на чем")
    spoiled_b = text_b.replace(
        ANCHOR_B,
        '        if not a.full and status == "frozen":\n            continue\n' + ANCHOR_B, 1)
    if spoiled_b == text_b:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена (б) не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    broken_b.write_text(spoiled_b, encoding="utf-8")

    env_b = os.environ.copy()
    env_b["MEZO_CONTAINER"] = str(CONTAINER)
    rc_b_brief, out_b_brief_broken = run_env(str(broken_b), db, env_b, "list", "--role", "PROTO",
                                             "--status", "all", "--actor", "PROTO")
    rc_b_full, out_b_full_broken = run_env(str(broken_b), db, env_b, "list", "--role", "PROTO",
                                           "--status", "all", "--actor", "PROTO", "--full")
    cards_b_brief = find_cards(out_b_brief_broken)
    cards_b_full = find_cards(out_b_full_broken)
    if not cards_b_brief and not cards_b_full:
        raise SystemExit(
            "ПРИЁМКА НЕ СОСТОЯЛАСЬ: копия backlog.py с поломкой (б) не напечатала НИ ОДНОЙ "
            "карточки ни в кратком, ни в полном виде — это отказ ЗАПУСКА (окружение/путь), "
            "а не сигнал поломки; исход неотличим от «не поймала». Вывод кратко: "
            f"{out_b_brief_broken[:300]!r}")
    flagged_b = cards_b_brief != cards_b_full
    case("поломка (б): cmd_list пропускает frozen-карточку в кратком виде → случай ② "
           "на этой копии ОБЯЗАН покраснеть",
           flagged_b,
           ("поломка (б) покрасила: да — " if flagged_b else
            "🔴 поломка (б) покрасила: нет — приёмка не ловит эту беду; ")
           + f"кратко {len(cards_b_brief)} карточек, полно {len(cards_b_full)}")
    mezo_stand.release(broken_stand_b)

    mezo_stand.release(stand)

    print("")
    print("=" * 78)
    failed = [item for item, ok in results if not ok]
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)} (①…⑫ + поломки (а) и (б))")
    print("⚖️ ГРАНИЦА: дословный текст подсказок mezo_hints, содержание отдельных гардов "
          "guard-all.py и динамические разделы role-brief.py этой приёмкой НЕ проверяются.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
