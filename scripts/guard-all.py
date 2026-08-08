r"""
guard-all.py — ВСЕ гарды контура одним вызовом. exit 0 — чисто, exit 1 — есть красное.

ЗАЧЕМ (П4, слово владельца 16.07 18:07 UTC). До этого каждый гард запускался ДИСЦИПЛИНОЙ:
guard-utc, guard-scripts-drift, гард хронологии — работали, только если кто-то вспомнил.
Ровно так sync.rules.md пять часов лгал отозванным правилом, шапка read-phoenix.py 47 минут
отрицала объявленную Фазу 4, а 8 lowercase-курсоров-призраков прожили 5 суток: расхождение
не прятали — на него просто никто не смотрел. «Дисциплина не масштабируется — механизм
масштабируется» работает, только если сам механизм не заперт за дисциплиной его запуска.
⇒ ОДИН вызов в протоколе: COORD гоняет его каждый all sync, роль — при пробуждении.

ЧТО ПРОВЕРЯЕТ (каждая проверка — оплаченный урок 16.07):
  ① guard-utc            — локальное время в коде тулкита (subprocess, returncode)
  ② guard-scripts-drift  — рантайм тулкита ≠ версионированное зеркало (subprocess)
  ③ хронология id        — «id растёт ⇒ время растёт», иначе курсор прыгает (ретро-импорт)
  ④ гигиена курсоров     — lowercase/призраки (EYE #2063) и курсор без слепка phoenix:
                           мёртвая роль воскресла или опечатка завела фантома (EYE #2149)
  ⑤ фантомные .db        — sqlite3.connect с опечаткой пути создавал пустую БД молча
  ⑥ фаза в шапке CANON   — read-phoenix.py обязан называть ТУ ЖЕ фазу, что правило
                           md-to-sqlite-phased-cutover (шапка уже лгала раз — EYE #2134)
  ⑦ замороженные md      — ни один не тронут после объявления Ф4 (16:58 UTC 16.07)
  ⑧ чтение ленты         — пишет, но не читает: невзведённый таймер синка (subprocess)
  ⑨ заглушки             — заглушка, обещающая действие (subprocess)
  ⑩ зеркало правил       — человекочитаемый файл отстал от таблицы `rules` (subprocess).
                           Заслон для путей мимо set-rule.py; называет расхождение поимённо

🪤 ПОЧЕМУ ЭТОТ СПИСОК ДОПИСАН 2026-08-07: он перечислял СЕМЬ проверок, а код запускал ДЕВЯТЬ.
Ровно тот класс, против которого заведена проверка ⑩: **врёт не код, а надпись, которую
код печатает.** Читающий шапку был уверен, что знает состав набора, и ошибался в двух
позициях из девяти. Меняешь состав — правь список ТЕМ ЖЕ ходом.

⚠️ ПОРТАТИВНОСТЬ ШАБЛОНА. Пути выводятся ИЗ РАСПОЛОЖЕНИЯ СКРИПТА (SCRIPTS/MEZO/DB/CONTAINER),
а не хардкодятся: скрипт живёт в <контур>/.mezosync/scripts/, БД — в <контур>/.mezosync/.
Проверки ⑥ и ⑦ зависят от Atlas-специфики (правило-фаза и каталог сгенерённых md-зеркал):
в свежей системе их может не быть — тогда проверка ПРОПУСКАЕТСЯ С ПОМЕТКОЙ, а не падает и
не краснит. Каталог COORDINATION задаётся env-переменной MEZOSYNC_COORDINATION (если каталога
нет — ⑦ пропускается). Так гард на новой системе остаётся зелёным по существу, а не по случаю.

ВЫВОД — БЕЗ ПАЙПОВ ЧИТАТЬ: печатает мало строк нарочно, чтобы не резать head'ом
(ловушка PIPESTATUS/head уже била и COORD, и CORE — итог гарда смотри по exit-коду).

ЗАПУСК:
    python guard-all.py                  # все проверки
    python guard-all.py --skip drift     # пропустить медленную/несрочную (через запятую)
"""

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Пути — из расположения скрипта, не хардкод (портативный шаблон):
#   SCRIPTS = <контур>/.mezosync/scripts,  MEZO = <контур>/.mezosync,  DB = MEZO/mezosync.db.
SCRIPTS = Path(__file__).resolve().parent
MEZO = SCRIPTS.parent
DB = MEZO / "mezosync.db"
CONTAINER = MEZO.parent
# COORDINATION (зеркала генерённых md) — Atlas-специфично, свежая система его не имеет.
# Берём из env; нет переменной или каталога — проверка ⑦ пропускается, а не падает.
COORDINATION = Path(os.environ["MEZOSYNC_COORDINATION"]) if os.environ.get("MEZOSYNC_COORDINATION") else None
# Отсечка неприкосновенности md. Ф4 ОБЪЯВЛЕНА в 16:58, но сами надгробия дописывались
# в файлы до 16:59:05 — отсечка по 16:58 краснела на легитимных записях самой заморозки
# (поймано первым же прогоном). Всё позже 17:00 — уже правка надгробия.
FREEZE_UTC = datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc).timestamp()

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    mark = "✅" if ok else "⛔"
    print(f"{mark} {name}" + (f" — {detail}" if detail and not ok else ""))


def sub_guard(name, script, skip):
    if name in skip:
        print(f"⏭️ {name} — пропущен по --skip")
        return
    # returncode напрямую, НИКАКИХ пайпов: `guard | head; echo $?` возвращает код head —
    # на этой ловушке гард UTC уже один раз отрапортовал «чисто» сквозь красное.
    r = subprocess.run([sys.executable, str(SCRIPTS / script)],
                       capture_output=True, text=True)
    tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
    check(name, r.returncode == 0, tail[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="имена проверок через запятую (utc,drift)")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    if not DB.exists():
        print(f"⛔ БД не найдена: {DB}")
        sys.exit(1)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    # ① ② подпроцессные гарды
    sub_guard("utc", "guard-utc.py", skip)
    sub_guard("drift", "guard-scripts-drift.py", skip)
    # ⑩ пишет-но-не-читает — подпись невзведённого таймера синка (оплачено 23.07: ING стоял
    # три цикла, STUD #2488 и CORE #2490 независимо признались в одном и том же).
    sub_guard("чтение ленты", "guard-write-without-read.py", skip)
    # ⑪ заглушка, обещающая действие — включён 23.07 15:40 UTC, когда STUD расставил подписи
    # (до этого держался вне набора: привычное красное хуже отсутствующего).
    sub_guard("заглушки", "guard-stub-expectations.py", skip)
    # ⑫ зеркало правил отстало от базы. Заслон для путей МИМО set-rule.py: прямой SQL,
    # восстановление базы, чужая рука. set-rule зовёт генератор сам — но это закрывает ОДИН
    # путь, а вопрос «сошлось ли на самом деле» задаётся здесь. Проверка называет расхождение
    # ПОИМЁННО: «файл устарел» без перечня равно молчанию. На свежей системе, где правил нет
    # и файла нет, пропускается с пометкой, а не краснит.
    sub_guard("зеркало правил", "check-rules-mirror.py", skip)

    # ③ хронология id
    chk = conn.execute(
        "SELECT COUNT(*) FROM (SELECT timestamp, LAG(timestamp) OVER (ORDER BY id) AS prev "
        "FROM messages) WHERE prev IS NOT NULL AND timestamp < prev").fetchone()[0]
    check("хронология id", chk == 0, f"{chk} разрывов — курсор может прыгать")

    # ④ гигиена курсоров: регистр + каждый курсор подтверждён слепком phoenix
    bad_case = [r for r, in conn.execute(
        "SELECT reader_role FROM read_cursors WHERE reader_role != UPPER(reader_role)")]
    check("курсоры: регистр", not bad_case, f"lowercase-призраки: {bad_case}")
    ghosts = [r for r, in conn.execute(
        "SELECT reader_role FROM read_cursors WHERE reader_role NOT IN "
        "(SELECT DISTINCT role FROM phoenix)")]
    check("курсоры: реестр", not ghosts,
          f"курсор без слепка phoenix (воскресший мертвец/фантом): {ghosts}")

    # ⑤ фантомные .db вне канона (канон — ровно один файл: .mezosync/mezosync.db)
    # ⚠️ v2 23.07: раньше смотрели ТОЛЬКО в scripts/ и coordination/ — там фантомы появлялись
    # прошлый раз. Гард ловил вчерашнее место, а не класс: пустая БД легла в
    # atlas.archs/.mezosync/mezosync.db (CWD смещался `cd` в PowerShell-команде) и прожила
    # незамеченной, при зелёном гарде. Теперь ищем по ВСЕМУ контейнеру и судим по ПРИЗНАКУ —
    # ноль таблиц: живую БД так не спутать, а фантом иначе не отличить от легитимной.
    container = CONTAINER
    skip_parts = {"node_modules", "obj", "bin", ".git", "graphify-out"}
    strays = []
    for p in container.rglob("*.db"):
        if p.resolve() == DB.resolve() or any(s in p.parts for s in skip_parts):
            continue
        if p.is_dir():                       # atlas.agents-sync.db — каталог-репо, не файл
            continue
        try:
            if p.stat().st_size == 0:
                strays.append(p)
                continue
            c2 = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            n = c2.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            c2.close()
            if n == 0:
                strays.append(p)
        except sqlite3.Error:
            pass                              # нечитаемое — не наш класс, молчим
    check("фантомные .db", not strays,
          f"{[str(p) for p in strays]} — пустая БД: sqlite3.connect по относительному пути "
          f"при смещённом CWD создаёт её МОЛЧА")

    # ⑥ фаза в CANON-шапке read-phoenix.py == фаза в правиле
    # Atlas-специфично: свежая система может не иметь этого правила — тогда пропускаем,
    # а не падаем на .fetchone()[0] по None (skip-not-crash — та же доктрина, что у ⑦).
    rule_row = conn.execute(
        "SELECT body FROM rules WHERE rule_key='md-to-sqlite-phased-cutover'").fetchone()
    if rule_row is None:
        print("⏭️ фаза в шапке CANON — правило md-to-sqlite-phased-cutover не заведено, проверка пропущена")
    else:
        rule_body = rule_row[0]
        m = re.search(r"ФАЗА \d+", rule_body)
        canon_src = (SCRIPTS / "read-phoenix.py").read_text(encoding="utf-8")
        check("фаза в шапке CANON", bool(m) and m.group(0) in canon_src,
              f"правило объявляет «{m.group(0) if m else '?'}», шапка read-phoenix её не несёт")

    # ⑦ замороженные md не тронуты после 16:58 UTC (generated/ и archive/ — живые, не смотрим)
    # Atlas-специфично: каталог COORDINATION задаётся env MEZOSYNC_COORDINATION. Нет его —
    # свежая система без зеркал md; проверка пропускается с пометкой, а не краснит.
    if COORDINATION is None or not COORDINATION.exists():
        print("⏭️ замороженные md — каталог COORDINATION не задан (env MEZOSYNC_COORDINATION) "
              "или отсутствует, проверка пропущена")
    else:
        touched = []
        for p in list(COORDINATION.glob("sync.*.md")) + list((COORDINATION / "phoenix").glob("*.md")):
            if p.name == "sync.rules.md":  # генерируется из БД — живой
                continue
            if p.stat().st_mtime > FREEZE_UTC:
                touched.append(f"{p.name} (mtime {datetime.fromtimestamp(p.stat().st_mtime, timezone.utc):%H:%M:%S} UTC)")
        check("замороженные md", not touched, "; ".join(touched))

    # ⑧ СВЕЖЕСТЬ СЛЕПКОВ: слепок роли не должен отставать от её последней ноты.
    #
    # ЗАЧЕМ (17.07 13:47 UTC): слепок — ЕДИНСТВЕННОЕ, что переживает чат. Лента расскажет
    # новорождённому, что роль СКАЗАЛА, но не то, что у неё в рабочем дереве, в долгах и в
    # голове. Замер: STUD отставал на 18.8 ч, ING на 16.8 ч — слепок STUD обещал «Открытых
    # пунктов у меня НЕТ» при 11 несведённых потоках, HEAD на 3 коммита назад, и ждал
    # nonce-ридер, сделанный сутки назад. Ни слова про cutover и смену курса.
    # И это НЕ гипотеза: сессия STUD закрылась в 13:22 (#2252), слепок не сохранив.
    #
    # ПОЧЕМУ ЭТА ПРОВЕРКА ЗДЕСЬ, А НЕ В ГОЛОВЕ РОЛИ: тот же класс, что ловит весь контур —
    # артефакт переживает решение. Но здесь он в ИНСТРУМЕНТЕ ВОСКРЕШЕНИЯ: слепок читается
    # первым и авторитетнее всего, что роль прочтёт дальше. Дыру вскрыл ВОПРОС ВЛАДЕЛЬЦА,
    # а не гард — у guard-all было 8 проверок, и ни одна не смотрела на то, ради чего вся
    # конструкция существует. Урок в код: гарды строятся на то, что ломается ГРОМКО, и не
    # строятся на то, что ломается ТИХО. Это — тихое.
    #
    # ПОРОГ 3 ч — не догма: роль пишет ноты чаще, чем сохраняется, и это нормально. 3 часа
    # ловит «сутки назад», не крича на «полчаса назад». Сравниваем с ПОСЛЕДНЕЙ НОТОЙ, а не с
    # now(): дормантная роль (RCC) молчит по слову владельца — её слепок совпал с её нотой и
    # честен. Уснувшую роль будить нечем, и гард не должен на неё лаять.
    STALE_HOURS = 3
    # ⑧-Б (идея TAXO #2270): часы — не единственная мера свежести. «saved_at не может быть
    # неверным — и потому ничего не сообщает»: свежий слепок при потоке нот ПОСЛЕ него всё
    # равно протух СОДЕРЖАНИЕМ — активная роль наговаривает на новый слепок и за полчаса.
    # Жёлтый, не красный: exit-код не трогаем; порог 5 — первый укус, тюнить по ложным.
    NOTES_AFTER_SNAP = 5
    stale, drifted = [], []
    for role, snap in conn.execute("SELECT role, MAX(saved_at) FROM phoenix GROUP BY role"):
        note = conn.execute(
            "SELECT MAX(timestamp) FROM messages WHERE writer_role = ?", (role,)).fetchone()[0]
        if not (snap and note):
            continue
        lag_h = (datetime.fromisoformat(note) - datetime.fromisoformat(snap)).total_seconds() / 3600
        if lag_h > STALE_HOURS:
            stale.append(f"{role} +{lag_h:.1f} ч (слепок {snap}, нота {note})")
            continue
        n_after = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE writer_role = ? AND timestamp > ?",
            (role, snap)).fetchone()[0]
        if n_after >= NOTES_AFTER_SNAP:
            drifted.append(f"{role} — {n_after} нот после слепка {snap}")
    check("свежесть слепков phoenix", not stale,
          "; ".join(stale) + " — save-phoenix ДО закрытия чата: слепок переживает чат, лента не заменит")
    if drifted:
        print(f"⚠️ слепки: содержание отстаёт (нот после слепка ≥ {NOTES_AFTER_SNAP}): "
              + "; ".join(drifted) + " — часы зелёные, содержание — нет")

    conn.close()
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{'⛔ КРАСНЫХ: ' + str(len(bad)) + ' — ' + ', '.join(bad) if bad else '✅ ВСЕ ГАРДЫ ЗЕЛЁНЫЕ'}"
          f" ({len(RESULTS)} проверок)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
