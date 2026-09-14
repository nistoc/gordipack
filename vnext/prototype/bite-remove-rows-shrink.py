# -*- coding: utf-8 -*-
r"""ПРИЁМКА remove-rows.py + сверки убыли строк с audit_log в backup-db.py — карточка #612.

БЕДА, которую закрывают эти два инструмента (см. докстроки remove-rows.py и
check_row_shrink в backup-db.py): ручное снятие строк из общей базы можно сделать
так, что в audit_log не остаётся ничего, и тогда законная убыль (по слову
владельца) неотличима от пропажи. remove-rows.py — единственный путь снятия,
который пишет след ОДНОЙ транзакцией со снятием; backup-db.py сверяет убыль с
этим следом и различает названную и неназванную.

🩸 ВОЗВРАТ COORD (2026-09-14, разбор границ по карточке #612). Инструмент по умолчанию
(без --apply) должен ТОЛЬКО ПОКАЗЫВАТЬ, что снялось бы — таблицу, число строк, первые
строки, основание — кодом 0 и последней строкой «ничего не снято: для снятия добавь
--apply»; настоящее снятие — только с --apply. --dry-run остаётся синонимом показа
(совместимость с dryrun.py). Случай 2b и поломка 10 — ровно про эту границу.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  1  remove-rows.py --apply: снимает строки, пишет ОДНУ запись audit_log           РАЗЛИЧАЮЩИЙ
  2  remove-rows.py --dry-run: НИ строки нигде (проверено по ВСЕМ таблицам стенда) РАЗЛИЧАЮЩИЙ
  2b remove-rows.py БЕЗ --apply (и без --dry-run — как позовёт роль по умолчанию): РАЗЛИЧАЮЩИЙ
     НИ строки нигде, код 0, последняя строка «для снятия добавь --apply»
  3  remove-rows.py без --basis (пустая строка) — отказ ДО записи                  РАЗЛИЧАЮЩИЙ
  4  названная убыль (через remove-rows.py --apply) → backup-db.py НЕ тревожит,    РАЗЛИЧАЮЩИЙ
     «убыль названа журналом»
  5  НЕназванная убыль (ручной DELETE мимо remove-rows.py) → тревожит, как раньше  РАЗЛИЧАЮЩИЙ
  6  названо 3, а фактически снято 5 (часть — без следа) → тревога, НЕ молчание    РАЗЛИЧАЮЩИЙ
  7  запись remove_rows СТАРШЕ прежней выгрузки — окно её не считает; НОВАЯ        РАЗЛИЧАЮЩИЙ
     убыль (уже после той выгрузки) тревожит как неназванная (сомнение из задания
     карточки #612: «если журнал старше прошлой выгрузки» — старую запись нельзя
     засчитать дважды, она уже объяснила предыдущую выгрузку)
  8  прежняя выгрузка в CRLF (Windows) — час и счётчики читаются как обычно,       РАЗЛИЧАЮЩИЙ
     названная убыль по-прежнему признаётся (чужая форма записи, п. приёмок helper-rules)
  9  обратный ход: сверка с audit_log в backup-db.py отключена → случай 4          РАЗЛИЧАЮЩИЙ
     (названная) ПРОВАЛИВАЕТСЯ (встречный случай для check_row_shrink, карточка ③)
  10 обратный ход: remove-rows.py снимает --apply ПО УМОЛЧАНИЮ (нарочная поломка   РАЗЛИЧАЮЩИЙ
     write_mode) → случай 2b ПРОВАЛИВАЕТСЯ (строки снялись без --apply)
  11 запись в audit_log не удалась (журнал закрыт на запись триггером стенда) →    РАЗЛИЧАЮЩИЙ
     отказ, и строки НА МЕСТЕ: снятие без следа невозможно, это одна транзакция
  12 обратный ход: снятие сохраняется ОТДЕЛЬНОЙ транзакцией до записи журнала      РАЗЛИЧАЮЩИЙ
     (нарочная поломка) → случай 11 ПРОВАЛИВАЕТСЯ (строки сняты, следа нет).
     Добавлено PROTO 2026-09-14: чужая поломка «две транзакции» проходила все 10.
  13 значение текстом в --where («message_id < 3») — отказ до записи              РАЗЛИЧАЮЩИЙ
  14 условие под ВСЕ строки таблицы без --all-rows — отказ, строки на месте;      РАЗЛИЧАЮЩИЙ
     показ без --apply предупреждает отдельной строкой, последняя строка прежняя
  15 то же условие с --all-rows — снимает все строки, одна запись журнала         РАЗЛИЧАЮЩИЙ
  16 обратный ход: проверка значения текстом выключена → случай 13 ПРОВАЛИВАЕТСЯ   РАЗЛИЧАЮЩИЙ
  17 обратный ход: проверка «все строки» выключена → случай 14 ПРОВАЛИВАЕТСЯ       РАЗЛИЧАЮЩИЙ
  18 журнал называет БОЛЬШЕ, чем убыло (сняли 7, 4 вернули) → тревога словами    РАЗЛИЧАЮЩИЙ
     «журнал называет больше», а не «часть снята без следа»
  19 обратный ход: ветка «называет больше» выключена → случай 18 ПРОВАЛИВАЕТСЯ   РАЗЛИЧАЮЩИЙ
     Случаи 13–19 — замечания OPSSRE Н1 и Н2 по приёмке карточки #612.
  20 число в чужой записи в --where («0x3», «3e0») — отказ, ничего не снято         РАЗЛИЧАЮЩИЙ
  21 имя колонки в двойных кавычках — отказ с подсказкой «имя без кавычек»        РАЗЛИЧАЮЩИЙ
  22 обратный ход: прежний образец числа (\b\d+(?:\.\d+)?\b) → случай 20           РАЗЛИЧАЮЩИЙ
     ПРОВАЛИВАЕТСЯ («0x3» проходит, строки сняты). Случаи 20–22 — границы OPSSRE Н3, Н5.
     Граница Н4 («все, кроме одной» снимается без --all-rows) названа, не закрыта:
     защита — только от условия под ВСЕ строки.

⛔ Живой базы не касается: каждый случай строит СВОЙ стенд; испытуемые remove-rows.py и
   backup-db.py — из .mezosync/scripts контура, найденного mezo_paths.container_root
   (MEZO_CONTAINER или расположение приёмки); запуск — со средой, закреплённой за стендом.
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

SCRIPTS = mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
BACKUP_TOOL = SCRIPTS / "backup-db.py"
REMOVE_TOOL = SCRIPTS / "remove-rows.py"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


AUDIT_LOG_DDL = """CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    actor_role  TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL,
    diff_md     TEXT
)"""


def build_stand(d: pathlib.Path) -> pathlib.Path:
    """Мини-база: bridge_reviewed (случай карточки #612) + rules/messages рядом +
    audit_log НАСТОЯЩЕЙ формы (та же, что в живой базе — сверено sqlite_master)."""
    d.mkdir(parents=True, exist_ok=True)
    db = d / "stand.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE bridge_reviewed (id INTEGER PRIMARY KEY, message_id INTEGER,"
               " reviewed_by TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("CREATE TABLE rules (k TEXT, v TEXT)")
    con.execute(AUDIT_LOG_DDL)
    con.executemany("INSERT INTO bridge_reviewed (message_id, reviewed_by) VALUES (?, ?)",
                    [(i, "COORD") for i in range(8)])
    con.executemany("INSERT INTO messages (body) VALUES (?)",
                    [(f"записка {i} " + "х" * 20,) for i in range(10)])
    con.executemany("INSERT INTO rules VALUES (?, ?)",
                    [(f"ключ{i}", f"значение{i}") for i in range(4)])
    con.commit()
    con.close()
    return db


def build_closed_audit_stand(d: pathlib.Path) -> pathlib.Path:
    """Тот же стенд, но журнал закрыт на запись: триггер отказывает любой вставке в
    audit_log. Так снятие упирается в запись следа — ровно то место, где одна
    транзакция отличается от двух (случаи 11 и 12)."""
    db = build_stand(d)
    con = sqlite3.connect(db)
    con.execute("CREATE TRIGGER audit_closed BEFORE INSERT ON audit_log"
                " BEGIN SELECT RAISE(ABORT, 'журнал закрыт на запись'); END")
    con.commit()
    con.close()
    return db


def run_backup(db, out, *flags, script=BACKUP_TOOL):
    r = subprocess.run([sys.executable, str(script), "--db", str(db), "--out", str(out), *flags],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       env=mezo_stand.stand_env(pathlib.Path(db).parent))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_remove(db, table, where, params, actor, basis, *flags, script=REMOVE_TOOL):
    cmd = [sys.executable, str(script), "--db", str(db), "--table", table, "--where", where,
          "--actor", actor, "--basis", basis]
    for p in params:
        cmd += ["--param", str(p)]
    cmd += list(flags)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       env=mezo_stand.stand_env(pathlib.Path(db).parent))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def table_counts(db, tables):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    con.close()
    return out


def fresh_stand(pref):
    """Стенд + базовый (первый) дамп — точка отсчёта, от которой считается убыль."""
    d = pathlib.Path(tempfile.mkdtemp(prefix=pref))
    db = build_stand(d)
    out = d / "stand.sql"
    code, output = run_backup(db, out, "--apply")
    if code != 0:
        sys.exit(f"⛔ базовый дамп стенда не снялся (код {code})\n{output}")
    return d, db, out


def must(code, output, what):
    if code != 0:
        sys.exit(f"⛔ подготовка случая не удалась ({what}, код {code}):\n{output}")


def weaken(d: pathlib.Path, anchor: str, replacement: str) -> pathlib.Path:
    """Копия backup-db.py с ослабленной веткой сверки журнала. None — якорь не найден."""
    original = BACKUP_TOOL.read_text(encoding="utf-8")
    broken = original.replace(anchor, replacement, 1)
    if broken == original:
        return None
    weak_path = d / "prior.py"
    weak_path.write_text(broken, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    return weak_path


def weaken_remove_tool(d: pathlib.Path, anchor: str, replacement: str) -> pathlib.Path:
    """Копия remove-rows.py с ослабленной веткой. None — якорь не найден (инструмент менялся)."""
    original = REMOVE_TOOL.read_text(encoding="utf-8")
    broken = original.replace(anchor, replacement, 1)
    if broken == original:
        return None
    weak_path = d / "weak-remove-rows.py"
    weak_path.write_text(broken, encoding="utf-8")
    shutil.copy(SCRIPTS / "mezo_paths.py", d / "mezo_paths.py")
    shutil.copy(SCRIPTS / "dryrun.py", d / "dryrun.py")
    return weak_path


def main() -> int:
    ok = True
    cleanup_dirs = []
    try:
        # ── 1: remove-rows.py --apply — снимает, пишет ОДНУ запись audit_log ──
        d1 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-1-")); cleanup_dirs.append(d1)
        db1 = build_stand(d1)
        before1 = table_counts(db1, ["bridge_reviewed", "audit_log"])
        code1, output1 = run_remove(db1, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                    "слово владельца, чат COORD 2026-09-07 09:12 UTC", "--apply")
        after1 = table_counts(db1, ["bridge_reviewed", "audit_log"])
        con = sqlite3.connect(db1)
        row = con.execute("SELECT actor_role, action, target, diff_md FROM audit_log"
                          " ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        ok &= case("1 remove-rows.py --apply снимает строки и пишет ОДНУ запись audit_log"
                   " (действие remove_rows, старые строки JSON, основание)",
                   code1 == 0 and after1["bridge_reviewed"] == before1["bridge_reviewed"] - 3
                   and after1["audit_log"] == before1["audit_log"] + 1
                   and row is not None and row[0] == "COORD" and row[1] == "remove_rows"
                   and row[2] == "bridge_reviewed" and "снято строк: 3" in row[3]
                   and "основание:" in row[3] and "БЫЛО (JSON)" in row[3]
                   and '"reviewed_by": "COORD"' in row[3],
                   f"код {code1}; было {before1}, стало {after1}; запись: actor={row[0] if row else None},"
                   f" action={row[1] if row else None}, target={row[2] if row else None}", differ=True)

        # ── 2: --dry-run — НИ строки нигде ──
        d2 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-2-")); cleanup_dirs.append(d2)
        db2 = build_stand(d2)
        before2 = table_counts(db2, ["bridge_reviewed", "audit_log", "messages", "rules"])
        code2, output2 = run_remove(db2, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                    "испытание холостого прогона", "--dry-run")
        after2 = table_counts(db2, ["bridge_reviewed", "audit_log", "messages", "rules"])
        last_line2 = output2.strip().splitlines()[-1] if output2.strip() else ""
        ok &= case("2 remove-rows.py --dry-run: ни строки ни в какой таблице (проверено по всем),"
                   " --dry-run — СИНОНИМ показа (та же последняя строка)",
                   code2 == 0 and before2 == after2
                   and "для снятия добавь --apply" in last_line2,
                   f"код {code2}; было {before2}, стало {after2}; последняя строка: {last_line2!r}",
                   differ=True)

        # ── 2b: БЕЗ --apply (и без --dry-run — как позовёт роль по умолчанию) —
        #        возврат COORD: снятие ТОЛЬКО с --apply, иначе только показ ──
        d2b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-2b-")); cleanup_dirs.append(d2b)
        db2b = build_stand(d2b)
        before2b = table_counts(db2b, ["bridge_reviewed", "audit_log", "messages", "rules"])
        code2b, output2b = run_remove(db2b, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                      "испытание показа по умолчанию")   # ни --apply, ни --dry-run
        after2b = table_counts(db2b, ["bridge_reviewed", "audit_log", "messages", "rules"])
        last_line2b = output2b.strip().splitlines()[-1] if output2b.strip() else ""
        ok &= case("2b БЕЗ --apply (по умолчанию, без флагов вовсе) — ни строки ни в какой"
                   " таблице, код 0, последняя строка «для снятия добавь --apply»",
                   code2b == 0 and before2b == after2b
                   and "для снятия добавь --apply" in last_line2b,
                   f"код {code2b}; было {before2b}, стало {after2b}; последняя строка:"
                   f" {last_line2b!r}", differ=True)

        # ── 3: --basis пустой — отказ ДО записи ──
        d3 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-3-")); cleanup_dirs.append(d3)
        db3 = build_stand(d3)
        before3 = table_counts(db3, ["bridge_reviewed", "audit_log"])
        code3, output3 = run_remove(db3, "bridge_reviewed", "message_id < ?", [3], "COORD", "   ")
        after3 = table_counts(db3, ["bridge_reviewed", "audit_log"])
        ok &= case("3 remove-rows.py с пустым --basis — отказ, ничего не записано",
                   code3 != 0 and before3 == after3 and "--basis" in output3,
                   f"код {code3}; было {before3}, стало {after3}", differ=True)

        # ── 4: НАЗВАННАЯ убыль (через remove-rows.py) → backup-db.py НЕ тревожит ──
        d4, db4, out4 = fresh_stand("bite-rr-4-")
        cleanup_dirs.append(d4)
        c4r, o4r = run_remove(db4, "bridge_reviewed", "message_id < ?", [3], "COORD",
                              "слово владельца, чат COORD 2026-09-07 09:12 UTC", "--apply")
        must(c4r, o4r, "снятие для случая 4")
        code4, output4 = run_backup(db4, out4, "--apply")
        ok &= case("4 названная убыль (remove-rows.py) → backup-db.py НЕ тревожит,"
                   " строка «убыль названа журналом»",
                   code4 == 0 and "🔴" not in output4 and "убыль названа журналом" in output4
                   and "bridge_reviewed" in output4,
                   f"код {code4}; вывод содержит «убыль названа журналом»:"
                   f" {'убыль названа журналом' in output4}", differ=True)

        # ── 5: НЕназванная убыль (ручной DELETE мимо remove-rows.py) → тревога, как раньше ──
        d5, db5, out5 = fresh_stand("bite-rr-5-")
        cleanup_dirs.append(d5)
        con5 = sqlite3.connect(db5)
        con5.execute("DELETE FROM bridge_reviewed WHERE message_id < 3")
        con5.commit(); con5.close()
        code5, output5 = run_backup(db5, out5, "--apply")
        ok &= case("5 НЕназванная убыль (ручной DELETE, без remove-rows.py) → тревожит, как раньше",
                   code5 == 1 and "🔴" in output5 and "bridge_reviewed −3" in output5
                   and "удалять из неё никто не должен" in output5,
                   f"код {code5}", differ=True)

        # ── 6: названо 3, а фактически снято 5 → тревога (несходится), не «ЗАКОННО» ──
        d6, db6, out6 = fresh_stand("bite-rr-6-")
        cleanup_dirs.append(d6)
        c6r, o6r = run_remove(db6, "bridge_reviewed", "message_id < ?", [3], "COORD",
                              "слово владельца — только три из пяти", "--apply")
        must(c6r, o6r, "снятие для случая 6")
        con6 = sqlite3.connect(db6)
        con6.execute("DELETE FROM bridge_reviewed WHERE message_id IN (3, 4)")   # ещё 2, БЕЗ следа
        con6.commit(); con6.close()
        code6, output6 = run_backup(db6, out6, "--apply")
        ok &= case("6 названо 3, а фактически снято 5 (2 — без следа) → тревога, НЕ «ЗАКОННО»",
                   code6 == 1 and "🔴" in output6 and "bridge_reviewed −5" in output6
                   and "журналом названо лишь 3" in output6,
                   f"код {code6}", differ=True)

        # ── 7: запись remove_rows СТАРШЕ прежней выгрузки — окно её не засчитывает ──
        d7, db7, out7 = fresh_stand("bite-rr-7-")
        cleanup_dirs.append(d7)
        con7 = sqlite3.connect(db7)
        # имитация СТАРОГО следа — запись легла ДО базового дампа этого стенда
        con7.execute(
            "INSERT INTO audit_log (timestamp, actor_role, action, target, diff_md) VALUES"
            " (datetime('now', '-2 days'), 'COORD', 'remove_rows', 'bridge_reviewed',"
            " 'снято строк: 3\nусловие: старое, из прошлого прогона\nоснование: старое основание')")
        con7.commit(); con7.close()
        # НОВАЯ убыль — ПОСЛЕ базового дампа этого стенда, без следа
        con7 = sqlite3.connect(db7)
        con7.execute("DELETE FROM bridge_reviewed WHERE message_id < 3")
        con7.commit(); con7.close()
        code7, output7 = run_backup(db7, out7, "--apply")
        ok &= case("7 запись remove_rows СТАРШЕ прежней выгрузки не засчитывается — новая убыль"
                   " тревожит как неназванная (не перекрыта старым следом)",
                   code7 == 1 and "🔴" in output7 and "bridge_reviewed −3" in output7
                   and "журналом названо" not in output7,
                   f"код {code7}; старая запись из прошлого прогона не имеет права объяснить"
                   " НОВУЮ убыль дважды", differ=True)

        # ── 8: прежняя выгрузка в CRLF (Windows) — час/счётчики читаются как обычно ──
        d8, db8, out8 = fresh_stand("bite-rr-8-")
        cleanup_dirs.append(d8)
        raw8 = out8.read_bytes()
        out8.write_bytes(raw8.replace(b"\n", b"\r\n"))
        c8r, o8r = run_remove(db8, "bridge_reviewed", "message_id < ?", [3], "COORD",
                              "слово владельца — проверка формы CRLF", "--apply")
        must(c8r, o8r, "снятие для случая 8")
        code8, output8 = run_backup(db8, out8, "--apply")
        ok &= case("8 прежняя выгрузка в CRLF (Windows) — час читается, названная убыль признана",
                   code8 == 0 and "убыль названа журналом" in output8,
                   f"код {code8}", differ=True)

        # ── 9: ОБРАТНЫЙ ХОД — сверка с журналом отключена → случай 4 ПРОВАЛИВАЕТСЯ ──
        d9 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-9-")); cleanup_dirs.append(d9)
        weak = weaken(
            d9,
            "                named, notes = named_removals(conn, t, since) if conn is not None else (0, [])",
            "                named, notes = (0, [])  # П-#612: сверка с журналом отключена")
        if weak is None:
            ok &= case("9 ОБРАТНЫЙ ХОД: сверка с журналом отключена", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь не найден — backup-db.py менялся, правь приёмку")
        else:
            d9b, db9b, out9b = fresh_stand("bite-rr-9b-")
            cleanup_dirs.append(d9b)
            c9r, o9r = run_remove(db9b, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                  "слово владельца, чат COORD 2026-09-07 09:12 UTC", "--apply")
            must(c9r, o9r, "снятие для случая 9")
            code9, output9 = run_backup(db9b, out9b, "--apply", script=weak)
            ok &= case("9 ОБРАТНЫЙ ХОД: без сверки с журналом случай «названная» (4) ПРОВАЛИВАЕТСЯ"
                       " — тревожит, хотя убыль была названа",
                       code9 == 1 and "🔴" in output9 and "убыль названа журналом" not in output9,
                       f"код {code9}; слабая копия красит ровно случай 4, как и требует карточка ③",
                       differ=True)

        # ── 10: ОБРАТНЫЙ ХОД — remove-rows.py снимает --apply ПО УМОЛЧАНИЮ
        #        (возврат COORD: границу держит ровно write_mode) → случай 2b ПРОВАЛИВАЕТСЯ ──
        d10 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-10-")); cleanup_dirs.append(d10)
        weak_rr = weaken_remove_tool(
            d10,
            "    write_mode = args.apply and not args.dry_run",
            "    write_mode = True  # П-#612 возврат: --apply по умолчанию")
        if weak_rr is None:
            ok &= case("10 ОБРАТНЫЙ ХОД: --apply по умолчанию", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь write_mode не найден — remove-rows.py"
                       " менялся, правь приёмку")
        else:
            d10b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-10b-")); cleanup_dirs.append(d10b)
            db10b = build_stand(d10b)
            before10 = table_counts(db10b, ["bridge_reviewed", "audit_log"])
            code10, output10 = run_remove(db10b, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                          "испытание поломки — БЕЗ --apply", script=weak_rr)
            after10 = table_counts(db10b, ["bridge_reviewed", "audit_log"])
            ok &= case("10 ОБРАТНЫЙ ХОД: без границы write_mode случай 2b ПРОВАЛИВАЕТСЯ"
                       " — строки снялись БЕЗ --apply",
                       code10 == 0 and before10 != after10
                       and after10["bridge_reviewed"] == before10["bridge_reviewed"] - 3,
                       f"код {code10}; было {before10}, стало {after10} — ослабленная копия"
                       " снимает без --apply, как и требует поломка карточки", differ=True)

        # ── 11: запись в audit_log не удалась → отказ, и строки НА МЕСТЕ ──
        d11 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-11-")); cleanup_dirs.append(d11)
        db11 = build_closed_audit_stand(d11)
        before11 = table_counts(db11, ["bridge_reviewed", "audit_log"])
        code11, output11 = run_remove(db11, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                      "испытание: журнал закрыт на запись", "--apply")
        after11 = table_counts(db11, ["bridge_reviewed", "audit_log"])
        ok &= case("11 запись в audit_log не удалась → отказ, строки на месте (снятие и след —"
                   " одна транзакция)",
                   code11 != 0 and before11 == after11 and "ничего не сохранено" in output11,
                   f"код {code11}; было {before11}, стало {after11}", differ=True)

        # ── 12: ОБРАТНЫЙ ХОД — снятие сохранено ОТДЕЛЬНОЙ транзакцией до записи журнала
        #        → случай 11 ПРОВАЛИВАЕТСЯ: строки сняты, следа нет ──
        d12 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-12-")); cleanup_dirs.append(d12)
        weak_tx = weaken_remove_tool(
            d12,
            "    removed = cur.rowcount",
            "    conn.commit()  # П-#612: снятие сохранено отдельной транзакцией\n"
            "    removed = cur.rowcount")
        if weak_tx is None:
            ok &= case("12 ОБРАТНЫЙ ХОД: две транзакции", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь «removed = cur.rowcount» не найден — remove-rows.py"
                       " менялся, правь приёмку")
        else:
            d12b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-12b-")); cleanup_dirs.append(d12b)
            db12 = build_closed_audit_stand(d12b)
            before12 = table_counts(db12, ["bridge_reviewed", "audit_log"])
            code12, output12 = run_remove(db12, "bridge_reviewed", "message_id < ?", [3], "COORD",
                                          "испытание поломки — две транзакции", "--apply",
                                          script=weak_tx)
            after12 = table_counts(db12, ["bridge_reviewed", "audit_log"])
            ok &= case("12 ОБРАТНЫЙ ХОД: снятие отдельной транзакцией — случай 11 ПРОВАЛИВАЕТСЯ:"
                       " строки сняты, следа в журнале нет",
                       after12["bridge_reviewed"] == before12["bridge_reviewed"] - 3
                       and after12["audit_log"] == before12["audit_log"],
                       f"код {code12}; было {before12}, стало {after12} — ослабленная копия"
                       " теряет след, как и требует поломка", differ=True)

        # ── 13: значение текстом в --where — отказ до записи ──
        d13 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-13-")); cleanup_dirs.append(d13)
        db13 = build_stand(d13)
        before13 = table_counts(db13, ["bridge_reviewed", "audit_log"])
        code13, output13 = run_remove(db13, "bridge_reviewed", "message_id < 3", [], "COORD",
                                      "испытание: значение текстом", "--apply")
        after13 = table_counts(db13, ["bridge_reviewed", "audit_log"])
        ok &= case("13 значение текстом в --where («message_id < 3») — отказ, ничего не снято",
                   code13 != 0 and before13 == after13 and "плейсхолдер" in output13,
                   f"код {code13}; было {before13}, стало {after13}", differ=True)

        # ── 14: условие под ВСЕ строки без --all-rows — отказ; показ предупреждает ──
        d14 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-14-")); cleanup_dirs.append(d14)
        db14 = build_stand(d14)
        before14 = table_counts(db14, ["bridge_reviewed", "audit_log"])
        code14p, output14p = run_remove(db14, "bridge_reviewed", "message_id >= ?", [0], "COORD",
                                        "испытание: все строки, показ")
        code14, output14 = run_remove(db14, "bridge_reviewed", "message_id >= ?", [0], "COORD",
                                      "испытание: все строки", "--apply")
        after14 = table_counts(db14, ["bridge_reviewed", "audit_log"])
        last14p = output14p.strip().splitlines()[-1] if output14p.strip() else ""
        ok &= case("14 условие под ВСЕ строки без --all-rows — отказ, строки на месте; показ"
                   " предупреждает, последняя строка показа прежняя",
                   code14 != 0 and before14 == after14 and "--all-rows" in output14
                   and code14p == 0 and "ВСЕ 8 строк" in output14p
                   and "для снятия добавь --apply" in last14p,
                   f"код {code14}; было {before14}, стало {after14}; показ: код {code14p},"
                   f" последняя строка {last14p!r}", differ=True)

        # ── 15: то же условие с --all-rows — снимает все, одна запись журнала ──
        code15, output15 = run_remove(db14, "bridge_reviewed", "message_id >= ?", [0], "COORD",
                                      "испытание: все строки по явному флагу", "--apply",
                                      "--all-rows")
        after15 = table_counts(db14, ["bridge_reviewed", "audit_log"])
        ok &= case("15 то же условие с --all-rows — снято 8, запись журнала одна",
                   code15 == 0 and after15["bridge_reviewed"] == 0
                   and after15["audit_log"] == before14["audit_log"] + 1,
                   f"код {code15}; стало {after15}", differ=True)

        # ── 16: ОБРАТНЫЙ ХОД — проверка значения текстом выключена → случай 13 проваливается ──
        d16 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-16-")); cleanup_dirs.append(d16)
        weak16 = weaken_remove_tool(d16, "    if LITERAL_IN_WHERE.search(where):",
                                    "    if False:  # П-Н2: проверка значения текстом выключена")
        if weak16 is None:
            ok &= case("16 ОБРАТНЫЙ ХОД: без проверки значения текстом", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь LITERAL_IN_WHERE не найден — remove-rows.py менялся,"
                       " правь приёмку")
        else:
            d16b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-16b-")); cleanup_dirs.append(d16b)
            db16 = build_stand(d16b)
            code16, output16 = run_remove(db16, "bridge_reviewed", "message_id < 3", [], "COORD",
                                          "испытание поломки Н2", "--apply", script=weak16)
            after16 = table_counts(db16, ["bridge_reviewed", "audit_log"])
            ok &= case("16 ОБРАТНЫЙ ХОД: без проверки значения текстом случай 13 ПРОВАЛИВАЕТСЯ —"
                       " строки сняты",
                       after16["bridge_reviewed"] == 5,
                       f"код {code16}; стало {after16}", differ=True)

        # ── 17: ОБРАТНЫЙ ХОД — проверка «все строки» выключена → случай 14 проваливается ──
        d17 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-17-")); cleanup_dirs.append(d17)
        weak17 = weaken_remove_tool(d17, "    if len(old_rows) == total and not allow_all_rows:",
                                    "    if False:  # П-Н2: проверка «все строки» выключена")
        if weak17 is None:
            ok &= case("17 ОБРАТНЫЙ ХОД: без проверки «все строки»", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь allow_all_rows не найден — remove-rows.py менялся,"
                       " правь приёмку")
        else:
            d17b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-17b-")); cleanup_dirs.append(d17b)
            db17 = build_stand(d17b)
            code17, output17 = run_remove(db17, "bridge_reviewed", "message_id >= ?", [0], "COORD",
                                          "испытание поломки Н2", "--apply", script=weak17)
            after17 = table_counts(db17, ["bridge_reviewed", "audit_log"])
            ok &= case("17 ОБРАТНЫЙ ХОД: без проверки «все строки» случай 14 ПРОВАЛИВАЕТСЯ —"
                       " снята вся таблица",
                       after17["bridge_reviewed"] == 0,
                       f"код {code17}; стало {after17}", differ=True)

        # ── 18: журнал называет БОЛЬШЕ, чем убыло — тревога своими словами ──
        d18, db18, out18 = fresh_stand("bite-rr-18-")
        cleanup_dirs.append(d18)
        c18r, o18r = run_remove(db18, "bridge_reviewed", "message_id < ?", [7], "COORD",
                                "слово владельца — снять семь", "--apply")
        must(c18r, o18r, "снятие для случая 18")
        con18 = sqlite3.connect(db18)
        con18.executemany("INSERT INTO bridge_reviewed (message_id, reviewed_by) VALUES (?, ?)",
                          [(100 + i, "COORD") for i in range(4)])   # четыре вернули обратно
        con18.commit(); con18.close()
        code18, output18 = run_backup(db18, out18, "--apply")
        ok &= case("18 журнал называет БОЛЬШЕ, чем убыло (сняли 7, вернули 4) → тревога"
                   " «журнал называет больше», не «часть снята без следа»",
                   code18 == 1 and "bridge_reviewed −3" in output18
                   and "журнал называет больше" in output18 and "без следа" not in output18,
                   f"код {code18}", differ=True)

        # ── 19: ОБРАТНЫЙ ХОД — ветка «называет больше» выключена → случай 18 проваливается ──
        d19 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-19-")); cleanup_dirs.append(d19)
        weak19 = weaken(d19, "                elif named and named > (was - now):",
                        "                elif False:  # П-Н1: ветка «называет больше» выключена")
        if weak19 is None:
            ok &= case("19 ОБРАТНЫЙ ХОД: без ветки «называет больше»", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь ветки не найден — backup-db.py менялся, правь приёмку")
        else:
            d19b, db19, out19 = fresh_stand("bite-rr-19b-")
            cleanup_dirs.append(d19b)
            c19r, o19r = run_remove(db19, "bridge_reviewed", "message_id < ?", [7], "COORD",
                                    "слово владельца — снять семь", "--apply")
            must(c19r, o19r, "снятие для случая 19")
            con19 = sqlite3.connect(db19)
            con19.executemany("INSERT INTO bridge_reviewed (message_id, reviewed_by) VALUES (?, ?)",
                              [(100 + i, "COORD") for i in range(4)])
            con19.commit(); con19.close()
            code19, output19 = run_backup(db19, out19, "--apply", script=weak19)
            ok &= case("19 ОБРАТНЫЙ ХОД: без ветки «называет больше» случай 18 ПРОВАЛИВАЕТСЯ —"
                       " снова «часть снята без следа»",
                       "журнал называет больше" not in output19 and "без следа" in output19,
                       f"код {code19}", differ=True)

        # ── 20: число в чужой записи — отказ до записи (граница OPSSRE Н3) ──
        d20 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-20-")); cleanup_dirs.append(d20)
        db20 = build_stand(d20)
        before20 = table_counts(db20, ["bridge_reviewed", "audit_log"])
        code20a, output20a = run_remove(db20, "bridge_reviewed", "message_id < 0x3", [], "COORD",
                                        "испытание: число шестнадцатеричной записью", "--apply")
        code20b, output20b = run_remove(db20, "bridge_reviewed", "message_id < 3e0", [], "COORD",
                                        "испытание: число с порядком", "--apply")
        after20 = table_counts(db20, ["bridge_reviewed", "audit_log"])
        ok &= case("20 число в чужой записи в --where («0x3», «3e0») — отказ, ничего не снято",
                   code20a != 0 and code20b != 0 and before20 == after20
                   and "плейсхолдер" in output20a and "плейсхолдер" in output20b,
                   f"коды {code20a}, {code20b}; было {before20}, стало {after20}", differ=True)

        # ── 21: имя колонки в двойных кавычках — отказ с подсказкой (граница OPSSRE Н5) ──
        code21, output21 = run_remove(db20, "bridge_reviewed", '"message_id" < ?', [3], "COORD",
                                      "испытание: имя в кавычках", "--apply")
        after21 = table_counts(db20, ["bridge_reviewed", "audit_log"])
        ok &= case("21 имя колонки в двойных кавычках — отказ с подсказкой «имя без кавычек»",
                   code21 != 0 and after21 == before20 and "без кавычек" in output21,
                   f"код {code21}; стало {after21}", differ=True)

        # ── 22: ОБРАТНЫЙ ХОД — прежний образец числа → случай 20 проваливается ──
        d22 = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-22-")); cleanup_dirs.append(d22)
        weak22 = weaken_remove_tool(d22, 'LITERAL_IN_WHERE = re.compile(r"""[\'"]|\\b\\d[\\w.]*""")',
                                    'LITERAL_IN_WHERE = re.compile(r"""[\'"]|\\b\\d+(?:\\.\\d+)?\\b""")'
                                    '  # П-Н3: прежний образец числа')
        if weak22 is None:
            ok &= case("22 ОБРАТНЫЙ ХОД: прежний образец числа", False,
                       "⛔ НЕ ЗАПУСТИЛАСЬ: якорь LITERAL_IN_WHERE не найден — remove-rows.py менялся,"
                       " правь приёмку")
        else:
            d22b = pathlib.Path(tempfile.mkdtemp(prefix="bite-rr-22b-")); cleanup_dirs.append(d22b)
            db22 = build_stand(d22b)
            code22, output22 = run_remove(db22, "bridge_reviewed", "message_id < 0x3", [], "COORD",
                                          "испытание поломки Н3", "--apply", script=weak22)
            after22 = table_counts(db22, ["bridge_reviewed", "audit_log"])
            ok &= case("22 ОБРАТНЫЙ ХОД: прежний образец числа — случай 20 ПРОВАЛИВАЕТСЯ,"
                       " «0x3» проходит и строки сняты",
                       after22["bridge_reviewed"] == 5,
                       f"код {code22}; стало {after22}", differ=True)
    finally:
        for d in cleanup_dirs:
            shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
