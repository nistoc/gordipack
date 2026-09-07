#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Приёмка карточки #519 — сохранение памяти отказывает на служебных блоках читалки.

ПРЕДМЕТ. Читалка памяти печатает рядом с телом раздела СВОИ блоки («## §4½ ОТКРЫТЫЕ
КАРТОЧКИ», «## §4¾ МАШИННЫЙ СЛОЙ», «## §4⅞ СЛОЙ ДИСКА»). Они собираются при каждом
вызове и нигде не хранятся. Роль, собравшая текст для сохранения ИЗ ВЫВОДА читалки,
записывает их в память как своё знание — и через сутки снимок ленты неотличим от знания.

ЧЕМ СУДИМ. Прогоняем сохранение ХОЛОСТЫМ прогоном (--dry-run): проверка стоит ДО записи,
поэтому все случаи меряются, а копия базы не меняется ни одним из них. Это проверено
случаем ⑪ (отпечаток базы до и после всего набора).

⚖️ КОНТРОЛЬ СТОИТ ПЕРВЫМ. Пока неиспорченный текст не сохранился без единого слова об этой
проверке, красное остальных случаев не значит ничего: оно может прийти по посторонней
причине (усушка, пустота, занятость инструмента).

⚖️ ВСТРЕЧНЫЕ СЛУЧАИ ОБЯЗАТЕЛЬНЫ И С ДРУГИМ ОПРЕДЕЛЕНИЕМ ПРЕДМЕТА (правило
`counter-case-own-definition`). Опыт определяет предмет как «строка НАЧИНАЕТСЯ заголовком
служебного блока». Встречные определяют иначе:
  ④⑤ — по СЛОВАМ блока («нигде не хранится», «собран этим вызовом») в тексте роли;
  ⑥  — по ЗНАКУ блока внутри строки роли;
  ⑦  — по заголовку РАЗДЕЛА (§4 без дроби), который критерий не называет;
  ⑨  — живой образец: тело настоящей записки контура, где эти слова стоят по делу.
Без них «отказ сработал» неотличимо от «отказывает на всём подряд», а лечение немотой
хуже болезни.

ПОРЧА (--break none): проверка снимается ⇒ случаи ①②③ и ⑧ обязаны покраснеть, а встречные
④–⑨ остаться зелёными. Порча, красящая ВСЁ, не доказывает, что случаи смотрят на предмет.
"""
import argparse
import hashlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROLE = "STUD"
# 🩸 ЧЕЙ СЛЕД. Все прогоны набора подписываются ОСОБЫМ актором: живую базу пишут девять
# рук, и «база изменилась» без имени руки ничего не значит — @TAXO поймала это на первом
# же чужом прогоне (записка #4811), причём писал в тот миг автор набора.
SUITE_ACTOR = "BITE519"

# Знаки, которые проверка ЗНАЕТ. Случай ⑫ сверяет их с тем, что печатают живые файлы:
# закрытый список в одном файле и рождение заголовков в другом — это и есть беда,
# которую нашёл @COORD. Появился новый — впиши сюда И в save-phoenix.py.
EXPECTED_SERVICE_MARKS = ("§4½", "§4¾", "§4⅞")

SECTION = "state"

# Заголовки, которые печатают читалка памяти и сборщик слоя диска — дословно из их кода.
BLOCK_CARDS = "## §4½ ОТКРЫТЫЕ КАРТОЧКИ   [живой запрос к базе, НЕ из сохранённого текста]"
BLOCK_MACHINE = "## §4¾ МАШИННЫЙ СЛОЙ   [собран этим вызовом, нигде не хранится]"
BLOCK_DISK = "## §4⅞ СЛОЙ ДИСКА   [собран этим вызовом, нигде не хранится · замер 2026-09-05T06:00:00Z]"


def fingerprint(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def body_from_db(db, role=ROLE, section=SECTION):
    con = sqlite3.connect(db)
    row = con.execute("SELECT body FROM phoenix WHERE role=? AND section=?", (role, section)).fetchone()
    con.close()
    if not row:
        sys.exit(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: в базе нет {role}/{section} — судить нечего.\n"
                 f"   Это отказ ОПЫТА, а не находка: без исходного тела любой вердикт был бы выдуман.")
    return row[0]


def note_body(db, number):
    """Живой образец из ленты — тело настоящей записки контура."""
    con = sqlite3.connect(db)
    row = con.execute("SELECT body_md FROM messages_all WHERE id=?", (number,)).fetchone()
    con.close()
    return row[0] if row else None



def suite_traces(db, since_hour):
    """Сколько записей в историю версий памяти оставил САМ НАБОР за время прогона.

    ⚖️ Спрашиваем не «изменился ли файл», а «есть ли ТАМ МОЯ РУКА». Разница несущая:
    файл общей базы меняют девять рук, и его отпечаток отвечает на чужой вопрос.
    Возвращает (число, строки для показа).
    """
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, role, section, saved_at FROM phoenix_history "
        "WHERE actor=? AND saved_at>=? ORDER BY id", (SUITE_ACTOR, since_hour)).fetchall()
    con.close()
    return len(rows), rows


def signs_at_printers():
    """Какие служебные знаки печатают ЖИВЫЕ файлы читалки памяти и сборщика слоя диска.

    ⚖️ Смысл случая ⑫ (находка @COORD, записка #4810): список примет закрыт прямо здесь,
    а заголовки рождаются в ДРУГОМ месте. Строка-напоминание «допиши сюда» забывается —
    поэтому спрашиваем сами: появится четвёртый блок, и набор покраснеет, а не промолчит.
    Возвращает (найденные знаки, файлы, которых нет).
    """
    container_root = Path(__file__).resolve().parent.parent
    printers = [
        container_root / ".mezosync" / "scripts" / "read-phoenix.py",
        container_root / "atlas.archs" / "step04_opssre" / "tools" / "disk_layer.py",
    ]
    found, missing_files = set(), []
    for p in printers:
        if not p.exists():
            missing_files.append(p.name)
            continue
        for m in re.finditer(r"#+\s*(§\d[½¾⅞⅓⅔¼⅛])", p.read_text(encoding="utf-8")):
            found.add(m.group(1))
    return found, missing_files


def _hour_now(db):
    """Час по мерке САМОЙ базы: сравнивать её saved_at с часом чужой машины нельзя."""
    con = sqlite3.connect(db)
    hour = con.execute("SELECT strftime('%Y-%m-%d %H:%M:%S','now')").fetchone()[0]
    con.close()
    return hour


def run_case(tool, db, text, workdir):
    """Холостой прогон сохранения. Возвращает (код, весь вывод одной строкой)."""
    f = Path(workdir) / "тело.md"
    f.write_text(text, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(tool), "--db", str(db), "--role", ROLE,
         "--section", SECTION, "--file", str(f), "--dry-run", "--allow-shrink",
         "--actor", SUITE_ACTOR],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def cases(db):
    """Каждый случай: (номер, что проверяем, текст, ожидание).

    Ожидание — словарь: код · есть ли слова отказа · номер строки, который обязан быть назван.
    """
    base = body_from_db(db)
    base_line_count = len(base.splitlines())
    result = []

    # ⓪ КОНТРОЛЬ ПЕРВЫМ — неиспорченный текст роли
    result.append(("⓪", "контроль: обычный текст роли сохраняется и о проверке НЕ говорит",
              base + "\n\nСтрока смены: перемерил стенд, все шесть служб отвечают.\n",
              {"code": 0, "reject": False}))

    # ①②③ ПРЕДМЕТ — три служебных блока, каждый своей строкой
    for mark, block, name in (("①", BLOCK_CARDS, "§4½ открытые карточки"),
                            ("②", BLOCK_MACHINE, "§4¾ машинный слой"),
                            ("③", BLOCK_DISK, "§4⅞ слой диска")):
        text = base + "\n\n" + "─" * 79 + "\n" + block + "\n\n   строка снимка: 24 карточки\n"
        result.append((mark, f"служебный блок читалки ({name}) ⇒ ОТКАЗ с номером строки", text,
                  {"code": 1, "reject": True, "line": base_line_count + 4}))

    # ④⑤ ВСТРЕЧНЫЕ ИЗ КРИТЕРИЯ — слова блока, употреблённые РОЛЬЮ по делу
    result.append(("④", "встречный: роль ЦИТИРУЕТ «нигде не хранится» по делу ⇒ ПРОПУСК",
              base + "\n\n⚠️ Машинный слой нигде не хранится — не переписывай его в память.\n",
              {"code": 0, "reject": False}))
    result.append(("⑤", "встречный: роль ЦИТИРУЕТ «собран этим вызовом» по делу ⇒ ПРОПУСК",
              base + "\n\n📌 Список карточек собран этим вызовом, а не взят из памяти.\n",
              {"code": 0, "reject": False}))

    # ⑥ ВСТРЕЧНЫЙ С ДРУГИМ ОПРЕДЕЛЕНИЕМ ПРЕДМЕТА (пожелание PROTO, записка #4793)
    result.append(("⑥", "встречный: знак §4½ ВНУТРИ строки роли ⇒ ПРОПУСК (пишем о блоке, не блоком)",
              base + "\n\n⛔ Не копируй §4½ и §4¾ из вывода читалки — это не твой текст.\n",
              {"code": 0, "reject": False}))

    # ⑦ ВСТРЕЧНЫЙ: заголовок РАЗДЕЛА, который критерий не называет
    result.append(("⑦", "встречный: заголовок раздела «## §4 …» (без дроби) ⇒ ПРОПУСК, он вне критерия",
              base + "\n\n## §4 ТЕКУЩЕЕ СОСТОЯНИЕ — где ты сейчас\n",
              {"code": 0, "reject": False}))

    # ⑧ ОТКАЗ НАЗЫВАЕТ СТРОКУ ВЕРНО — блок в СЕРЕДИНЕ, а не в конце
    head = "\n".join(base.splitlines()[:5])
    tail = "\n".join(base.splitlines()[5:])
    result.append(("⑧", "номер строки в отказе ВЕРЕН: блок в СЕРЕДИНЕ текста, не в конце",
              head + "\n" + BLOCK_MACHINE + "\n" + tail,
              {"code": 1, "reject": True, "line": 6}))

    # ⑨ ЖИВОЙ ОБРАЗЕЦ ИЗ КРИТЕРИЯ — тело настоящей записки контура
    sample = note_body(db, 4619)
    if sample:
        result.append(("⑨", "встречный ЖИВОЙ: тело записки #4619 (автор TAXO) ⇒ ПРОПУСК",
                  sample, {"code": 0, "reject": False}))
    else:
        result.append(("⑨", "встречный ЖИВОЙ: записки #4619 в этой базе НЕТ", None,
                  {"skipped": "записки #4619 нет в базе — случай не поставлен, и это сказано, "
                               "а не скрыто зелёным"}))

    # ⑩ БЛОК ПЕРВОЙ СТРОКОЙ — крайний случай отбора
    result.append(("⑩", "служебный блок ПЕРВОЙ строкой ⇒ ОТКАЗ, строка 1",
              BLOCK_CARDS + "\n\n" + base,
              {"code": 1, "reject": True, "line": 1}))

    return result


def main():
    ap = argparse.ArgumentParser(description="Приёмка карточки #519: служебные блоки читалки в памяти")
    ap.add_argument("--tool", "--инструмент", dest="tool", help="путь к save-phoenix.py (по умолчанию — живой)")
    ap.add_argument("--db", help="путь к базе (по умолчанию — живая)")
    ap.add_argument("--break", dest="corruption", choices=["none"],
                    help="нарочная поломка: none — снять проверку служебных блоков")
    a = ap.parse_args()

    here = Path(__file__).resolve()
    tool = Path(a.tool) if a.tool else \
        here.parent.parent / ".mezosync" / "scripts" / "save-phoenix.py"
    if not tool.exists():
        sys.exit(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: инструмента нет — {tool}")
    db = Path(a.db) if a.db else tool.parent.parent / "mezosync.db"
    if not db.exists():
        sys.exit(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН: базы нет — {db}")

    workdir = tempfile.mkdtemp(prefix="bite519-")
    runner = Path(workdir) / "save-phoenix.py"
    shutil.copy(tool, runner)
    # модули лежат рядом с инструментом — зовём копию ОТТУДА же, а не из временного места
    runner = tool

    if a.corruption == "none":
        # ⚠️ Порча ставится на КОПИИ инструмента в его же каталоге: модули рядом.
        corrupted = tool.with_name("_порча_519_save-phoenix.py")
        t = tool.read_text(encoding="utf-8")
        original = t
        t = t.replace("    line_num, block_line = service_block(body)",
                      "    line_num, block_line = (None, None)  # ПОРЧА")
        if t == original:
            sys.exit("⛔ ПОРЧА НЕ ВСТАЛА: строки вызова проверки в инструменте нет.\n"
                     "   Это отказ ОПЫТА: без поставленной поломки зелёное ничего не доказывает.")
        corrupted.write_text(t, encoding="utf-8")
        runner = corrupted

    before_fingerprint = fingerprint(db)
    start_hour = _hour_now(db)
    suite = cases(db)
    passed = failed = skipped = 0
    print("═" * 92)
    print(f"ПРИЁМКА карточки #519 · инструмент: {runner.name} · база: {db.name}"
          + (" · ПОРЧА: проверка снята" if a.corruption else ""))
    print("═" * 92)

    for mark, what, text, expect in suite:
        if "skipped" in expect:
            print(f"  ⚪ {mark} {what}\n       {expect['skipped']}")
            skipped += 1
            continue
        code, output = run_case(runner, db, text, workdir)
        said_reject = "СЛУЖЕБНЫЙ БЛОК ЧИТАЛКИ" in output
        problems = []
        if code != expect["code"]:
            problems.append(f"код {code}, ждали {expect['code']}")
        if said_reject != expect["reject"]:
            problems.append("отказ сказан" if said_reject else "отказа НЕ сказано")
        if expect.get("line") is not None and said_reject:
            m = re.search(r"строка (\d+):", output)
            named = int(m.group(1)) if m else None
            if named != expect["line"]:
                problems.append(f"названа строка {named}, верна {expect['line']}")
        if problems:
            failed += 1
            print(f"  🔴 {mark} {what}\n       {' · '.join(problems)}")
            tail = [l for l in output.splitlines() if l.strip()][:3]
            for l in tail:
                print(f"       │ {l[:100]}")
        else:
            passed += 1
            print(f"  ✅ {mark} {what}")

    # ⑪ НАБОР НЕ ПИСАЛ — судим СВОЙ след поимённо, а не отпечаток общего файла
    count, rows = suite_traces(db, start_hour)
    if count == 0:
        passed += 1
        print(f"  ✅ ⑪ набор НЕ ПИСАЛ в память: записей с актором {SUITE_ACTOR} за прогон — ноль")
    else:
        failed += 1
        print(f"  🔴 ⑪ набор ЗАПИСАЛ в память {count} раз — холостой прогон писать не должен")
        for id_, role, section, hour in rows[:5]:
            print(f"       │ #{id_} {role}/{section} {hour}")
    if before_fingerprint != fingerprint(db):
        print("       ⚪ файл базы за это время менялся — ЧУЖОЙ рукой; на вердикт не влияет")

    # ⑫ СПИСОК ПРИМЕТ НЕ ОТСТАЁТ ОТ ТЕХ, КТО ЭТИ БЛОКИ ПЕЧАТАЕТ (находка @COORD, #4810)
    live, missing_files = signs_at_printers()
    if missing_files:
        skipped += 1
        print("  ⚪ ⑫ сверка списка примет с печатающими файлами ПРОПУЩЕНА: нет "
              + ", ".join(missing_files) + " — молчать об этом нельзя, судить нечем")
    else:
        extra = live - set(EXPECTED_SERVICE_MARKS)
        if not extra:
            passed += 1
            print(f"  ✅ ⑫ список примет полон: печатающие файлы дают {len(live)} знака, "
                  "новых нет")
        else:
            failed += 1
            print("  🔴 ⑫ У ЧИТАЛКИ ПОЯВИЛСЯ БЛОК, КОТОРОГО ПРОВЕРКА НЕ ЗНАЕТ: "
                  + " ".join(sorted(extra)))
            print("       │ допиши знак в СЛУЖЕБНЫЕ_ЗНАКИ инструмента save-phoenix.py")
            print("       │ и в EXPECTED_SERVICE_MARKS здесь — иначе блок поедет в память молча")

    if a.corruption == "none":
        try:
            (tool.with_name("_порча_519_save-phoenix.py")).unlink()
        except OSError:
            pass
    shutil.rmtree(workdir, ignore_errors=True)

    print("─" * 92)
    summary = f"прошло {passed} · пало {failed}"
    if skipped:
        summary += f" · не поставлено {skipped} (причина названа выше)"
    print(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
