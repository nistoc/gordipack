# -*- coding: utf-8 -*-
"""bite-phoenix-dry-run.py — приёмка карточки #656: холостой прогон save-phoenix.py не пишет
записи памяти в базу и показывает их честно.

ЗАЧЕМ. Находка ING (записка #5349, 2026-09-24 12:17 UTC): в холостом прогоне тело писалось на
холостом соединении, а пересборка записей памяти (phoenix_records) — на СВОЁМ обычном
соединении с настоящим commit. Холостой прогон писал таблицу базы по ПРЕЖНЕМУ телу, печатал
«новых 0» (шесть пар из шести) и объявлял «НИЧЕГО НЕ ЗАПИСАНО».

Случаи (стенд — копия базы контура; подставная роль BITE656, раздел state, тело из четырёх
блоков «##» засевается настоящим сохранением — ни одна настоящая роль не нужна, поэтому
приёмка идёт и в свежем контуре из пакета):
  ①  холостой прогон тела с ДОБАВЛЕННЫМ блоком «##» показывает «новых 1» (случай ING
      12:15 UTC) — предпросмотр видит НОВОЕ тело, а не прежнее
  ②  настоящий прогон того же файла печатает ту же строку «записи раздела», что холостой
  ③  после холостого прогона phoenix_records, audit_log и phoenix копии не изменились
      (перед прогоном одна запись нарочно рассогласована с телом: пересборка на базе её
      поправила бы — сличению есть на что смотреть)
  ④  встречный к ③: настоящий прогон те же таблицы меняет
  ⑤  предпросмотр невозможен (рядом нет memory-records.py): предупреждение говорит «живая база
      не тронута», а не «сохранение прошло», и таблицы копии не изменились
  ⑥  первый разбор (у раздела записей нет): холостой прогон печатает ту же строку «первый разбор»,
      что настоящий, и записей не заводит; настоящий — заводит столько, сколько назвал

Нарочные поломки (--break; --porcha — синоним), каждая на своей копии save-phoenix.py:
  own-connection ... пересборка в холостом прогоне на своём соединении, как до #656 → ① ② ③ ⑤ ⑥
  dry-says-saved ... нет ветки холостого прогона, когда memory-records.py не найден  → ⑤

Живой базы не касается: копия базы (mezo_stand.snapshot_db), инструменты — копиями в стенде,
среда — mezo_stand.stand_env. Объявления о правке в КОПИИ гасятся: чужое объявление о правке
save-phoenix.py отказало бы настоящему прогону не по причине, которую здесь судят.
⚖️ Чего НЕ проверяет: ожидание занятой базы при снятии копии для предпросмотра (предел 10 с) —
занятость на стенде надёжно не воспроизводится.
"""
import argparse
import hashlib
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("save-phoenix.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

ROLE, SECTION = "BITE656", "state"
RECORDS_LINE = "🧩 записи раздела"
# Тело подставной роли: четыре блока «##», пустая строка в конце — добавленный пятый блок
# не меняет текст четвёртого, и пересборка обязана назвать ровно одну новую запись.
BODY0 = ("# ПОЗИЦИЯ (проба приёмки карточки #656)\n\n"
         "## БЛОК 1 — состояние\nсделано: посев подставной роли\nдальше: холостой прогон\n\n"
         "## БЛОК 2 — права\nправо: только проба на копии базы\n\n"
         "## БЛОК 3 — уроки\nурок: холостой прогон не пишет в базу\n\n"
         "## БЛОК 4 — замеры\nзамер: одна запись на блок\n\n")
DRY_TAIL = "живая база не тронута"
WATCHED = ("phoenix_records", "audit_log", "phoenix")

BREAKS = {
    "own-connection": ([(
        "    rebuild_records(args.db, role, args.section, actor, dry=args.dry_run, preview=preview)\n",
        "    rebuild_records(args.db, role, args.section, actor)\n")],
        {"①", "②", "③", "⑤", "⑥"}),
    "dry-says-saved": ([("    if not file.exists() and dry:\n", "    if False:\n")], {"⑤"}),
}

OK = FAIL = 0
RED = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)


def records_line(out):
    """Первая строка итога о записях раздела в выводе save-phoenix.py (или None)."""
    return next((line for line in out.splitlines() if line.startswith(RECORDS_LINE)), None)


def fingerprint(db, table):
    con = sqlite3.connect(str(db))
    rows = con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    con.close()
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest(), len(rows)


def watched(db):
    """Отпечатки таблиц критерия: записи памяти, журнал, тела памяти."""
    return {table: fingerprint(db, table) for table in WATCHED}


def table_counts(db):
    """Число строк во всех таблицах — для сведения, какие ЕЩЁ таблицы трогает прогон."""
    con = sqlite3.connect(str(db))
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    counts = {}
    for name in names:
        try:
            counts[name] = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except sqlite3.Error:
            pass
    con.close()
    return counts


def count_records(db):
    con = sqlite3.connect(str(db))
    n = con.execute("SELECT COUNT(*) FROM phoenix_records WHERE role=? AND section=?",
                    (ROLE, SECTION)).fetchone()[0]
    con.close()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(BREAKS))
    ap.add_argument("--show-output", action="store_true",
                    help="напечатать полный вывод каждого прогона save-phoenix.py")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-phoenix-dry-run-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.snapshot_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")

    con = sqlite3.connect(str(db))
    for table in ("phoenix", "phoenix_records", "phoenix_history"):
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (table,)).fetchone():
            con.execute(f"DELETE FROM {table} WHERE role=?", (ROLE,))
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='tool_leases'").fetchone():
        con.execute("UPDATE tool_leases SET until_utc='2000-01-01 00:00:00' "
                    "WHERE released_at IS NULL")
    con.commit()
    con.close()

    tools = stand / "tools"
    tool = mezo_stand.copy_tool(TARGET, tools)
    for helper in ("memory-records.py", "memory-archive.py"):
        source = HERE / helper
        if not source.exists():
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: рядом с приёмкой нет {helper} ({source})")
        mezo_stand.copy_tool(source, tools)
    if a.break_name:
        text = tool.read_text(encoding="utf-8")
        for old, new in BREAKS[a.break_name][0]:
            if text.count(old) != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                         f"(образец найден {text.count(old)} раз)")
            text = text.replace(old, new)
        tool.write_text(text, encoding="utf-8")
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")
    # второй набор — та же копия инструмента, но БЕЗ memory-records.py рядом (для ⑤)
    bare_tool = mezo_stand.copy_tool(tool, stand / "tools-bare")

    runs = []

    def save(tool_path, text, dry):
        body_file = stand / f"body-{len(runs)}.md"
        body_file.write_text(text, encoding="utf-8", newline="")
        cmd = [sys.executable, str(tool_path), "--db", str(db), "--role", ROLE,
               "--section", SECTION, "--file", str(body_file)]
        if dry:
            cmd.append("--dry-run")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
        out = (r.stdout or "") + (r.stderr or "")
        runs.append((("холостой" if dry else "настоящий") + f" · {tool_path.parent.name}", out))
        return r.returncode, out

    # посев: настоящее сохранение тела из четырёх блоков — первый разбор заводит записи
    rc_seed, out_seed = save(tool, BODY0, dry=False)
    if rc_seed != 0 or count_records(db) == 0:
        print(out_seed)
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: посев подставной роли {ROLE} не удался "
                 f"(код {rc_seed}, записей {count_records(db)})")
    # рассогласовать одну запись с телом: пересборка НА БАЗЕ её поправила бы (для ③)
    con = sqlite3.connect(str(db))
    probe = con.execute("SELECT id FROM phoenix_records WHERE role=? AND section=? "
                        "ORDER BY id LIMIT 1", (ROLE, SECTION)).fetchone()
    con.execute("UPDATE phoenix_records SET subject='проба-656' WHERE id=?", (probe[0],))
    con.commit()
    con.close()

    # ① ③ — холостой прогон тела с добавленным блоком
    body_a = BODY0 + "## БЛОК 5 — добавлен\nдобавленный блок: предпросмотр обязан его увидеть\n\n"
    before, counts_before = watched(db), table_counts(db)
    rc_dry, out_dry = save(tool, body_a, dry=True)
    after, counts_after = watched(db), table_counts(db)
    line_dry = records_line(out_dry)
    m = re.search(r"новых (\d+)", line_dry or "")
    case("①", "холостой прогон видит НОВОЕ тело: «новых 1» за добавленный блок",
         rc_dry == 0 and m is not None and int(m.group(1)) == 1,
         f"код {rc_dry} · «{line_dry}»")
    changed = [t for t in WATCHED if before[t] != after[t]]
    case("③", "после холостого прогона phoenix_records, audit_log и phoenix копии не изменились",
         not changed, "изменились: " + (", ".join(changed) or "ничего"))
    other = sorted(t for t in counts_after if counts_after.get(t) != counts_before.get(t))
    print("   ℹ️ прочие таблицы после холостого прогона (по числу строк): "
          + ("без изменений" if not other else "изменились " + ", ".join(other)))

    # ② ④ — настоящий прогон того же тела
    rc_real, out_real = save(tool, body_a, dry=False)
    line_real = records_line(out_real)
    case("②", "настоящий прогон печатает ту же строку «записи раздела», что холостой",
         rc_real == 0 and line_real is not None and line_real == line_dry,
         f"холостой «{line_dry}» · настоящий «{line_real}» · код {rc_real}")
    after_real = watched(db)
    changed_real = [t for t in WATCHED if after[t] != after_real[t]]
    case("④", "встречный к ③: настоящий прогон те же таблицы меняет",
         "phoenix_records" in changed_real and "phoenix" in changed_real,
         "изменились: " + (", ".join(changed_real) or "ничего"))

    # ⑤ — предпросмотр невозможен: рядом с копией инструмента нет memory-records.py
    body_b = body_a + "## БЛОК 6 — без помощника\nблок для прогона без memory-records.py\n\n"
    before_bare = watched(db)
    rc5, out5 = save(bare_tool, body_b, dry=True)
    warn = next((line for line in out5.splitlines()
                 if "записи раздела" in line and "⚠️" in line), "")
    case("⑤", "предпросмотр невозможен: «живая база не тронута», а не «сохранение прошло»; "
              "таблицы целы",
         rc5 == 0 and DRY_TAIL in warn and "сохранение прошло" not in warn
         and watched(db) == before_bare,
         f"код {rc5} · «{warn}»")

    # ⑥ — первый разбор: у раздела записей нет
    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM phoenix_records WHERE role=? AND section=?", (ROLE, SECTION))
    con.commit()
    con.close()
    body_c = body_a + "## БЛОК 7 — первый разбор\nблок для первого разбора\n\n"
    rc6d, out6d = save(tool, body_c, dry=True)
    n_after_dry = count_records(db)
    rc6r, out6r = save(tool, body_c, dry=False)
    n_after_real = count_records(db)
    l6d, l6r = records_line(out6d), records_line(out6r)
    m6 = re.search(r"разобрано (\d+) записей \(первый разбор\)", l6d or "")
    case("⑥", "первый разбор: холостой — та же строка, что у настоящего, и записей не заводит",
         rc6d == 0 and rc6r == 0 and m6 is not None and l6d == l6r and n_after_dry == 0
         and n_after_real == int(m6.group(1)),
         f"холостой «{l6d}» (записей после него {n_after_dry}) · "
         f"настоящий «{l6r}» (записей {n_after_real})")

    if a.show_output or (FAIL and not a.break_name):
        for title, out in runs:
            print(f"\n──── вывод save-phoenix.py: {title} ────\n{out}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'✅' if exact else '🔴'} поломка «{a.break_name}»: провалились "
              f"{' '.join(sorted(RED)) or 'никто'} · ждали {' '.join(sorted(expected))}")
        return mezo_stand.finish(0 if exact else 1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
