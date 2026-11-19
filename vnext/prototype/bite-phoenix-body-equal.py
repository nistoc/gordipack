# -*- coding: utf-8 -*-
r"""ПРИЁМКА сличения записанного тела памяти с поданным и отказа возврату прежней версии — карточка #792
(передана из #753; случай STUD, записка #6358 §②).

ПОВОД. Проверка целостности сохранения памяти судила «тело непустое и разбирается», а не «тело РАВНО
тому, что рука подала». Возврат старого тела для неё неотличим от успешной записи: старое тело непусто
и разбирается безупречно. 13.11 у STUD вторая команда цепочки выполнилась после падения первой, и раздел
молча вернулся к прежнему телу. Два места в save-phoenix.py:
  ① после записи тело читается из базы ЗАНОВО и сличается с поданным знак в знак (код выхода 6);
  ② подано тело, НЕ равное нынешнему, но РАВНОЕ одной из прежних версий раздела — отказ ДО записи
    (код выхода 5), в строке номер и час той версии и «--restore <id>».

⛔ ЖИВОЙ БАЗЫ НЕ КАСАЕТСЯ. Подставная база: схема основания БЕЗ его строк (mezo_stand.empty_db), роль
посажена seed_roles. Основание схемы — MEZO_LIVE_DB, если названа, иначе база рядом с испытуемым каталогом.
Какую копию инструмента испытываем — MEZO_SCRIPTS_ROOT (mezo_target).

Случаи (у каждого нового есть встречный):
  ①  после записи в базе ДРУГОЕ тело (в подставной базе стоит триггер, дописывающий к телу знаки):
     код 6, названы длины, номер первой отличной строки                          РАЗЛИЧАЮЩИЙ
  ①к ВСТРЕЧНЫЙ: обычная запись — код 0, строка «сличение после записи … равно поданному», тело в базе
     то, что подано                                                                КОНТРОЛЬ
  ⑤а --confirm («перечитал, правок нет») — код 0, тело и число версий те же       ЗАКОННОЕ
  ⑤б подано тело, РАВНОЕ нынешнему, — код 0, «СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ»            ЗАКОННОЕ
  ⑤в --restore <id> — возврат версии по явному слову: код 0, тело версии, новая версия в истории
     с причиной «restore <id>»                                                      ЗАКОННОЕ
  ②к ВСТРЕЧНЫЙ: тело, которого не было ни в одной версии, — код 0, записано         КОНТРОЛЬ
  ②  подано тело ПРЕЖНЕЙ версии (не нынешнее) — код 5, названы номер и час версии и «--restore <id>»,
     число версий раздела и тело в базе до и после отказа те же                     РАЗЛИЧАЮЩИЙ
  ②а то же холостым прогоном — тот же отказ, база не тронута                         РАЗЛИЧАЮЩИЙ
  ②б ВСТРЕЧНЫЙ: нынешнее тело с «\r\n», подан тот же текст с «\n» (круг --read --out → --file) —
     это не возврат: код 0                                                          КОНТРОЛЬ
  ③  отпечаток sha256 файла инструмента до и после прогона один и тот же (поломки ставятся только
     в КОПИИ внутри стенда)                                                          КОНТРОЛЬ

НАРОЧНЫЕ ПОЛОМКИ (в копии инструмента внутри стенда; поломка портит ПРЕДМЕТ, а не приёмку):
  --break blind  сличение после записи ослеплено (всегда «равно»)       ⇒ падает РОВНО ①
  --break noold  поиск прежней версии выключен                           ⇒ падает РОВНО ②, ②а

ЧЕГО ПРИЁМКА НЕ РАЗЛИЧАЕТ (названо, а не скрыто): подано тело, равное нынешнему, потому что рука не
правила, и потому что прошлая запись потерялась, — одно и то же (⑤б); возврат, задуманный рукой без
--restore (правка вручную дала ровно прежний текст), от случая STUD неотличим — отказ и подсказка.
"""
import argparse
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

ROLE = "BITE792"
SECTION = "plan"
BREAKS = {
    "blind": ("    mismatch = stored_body_mismatch(stored_row[0] if stored_row else None, body, role, args.section)",
              "    mismatch = None",
              {"①"}),
    "noold": ("    old_version = returned_old_version(conn, role, args.section, body, prev_body,",
              "    old_version = None and returned_old_version(conn, role, args.section, body, prev_body,",
              {"②", "②а"}),
}

ap = argparse.ArgumentParser(description="Приёмка карточки #792")
ap.add_argument("--break", dest="breakage", choices=sorted(BREAKS),
                help="нарочная поломка в копии инструмента: blind — сличение после записи ослеплено; "
                     "noold — поиск прежней версии выключен")
args = ap.parse_args()

print(f"⚖️ испытуется: {mezo_target.label()}")
tool = mezo_target.script("save-phoenix.py")
failures = []


def check(num, ok, said):
    """Исход случая. Печатает ВСЕГДА — и когда прошёл, и когда нет."""
    print(f"{'✅' if ok else '🔴'} {num} {said}")
    if not ok:
        failures.append(num)
    return ok


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_of(mark, n=10):
    """Тело опыта около 300 знаков: ниже порога сокращения (400), строки длиннее 12 знаков."""
    return f"# раздел опыта {mark}\n" + "".join(f"строка опыта {mark} номер {i}\n" for i in range(n))


class Stand:
    def __init__(self, runner, db, container, work):
        self.runner, self.db, self.container, self.work = runner, db, container, Path(work)
        self.n = 0

    def run(self, *extra):
        r = subprocess.run([sys.executable, "-X", "utf8", str(self.runner), "--db", str(self.db),
                            "--role", ROLE, "--section", SECTION, *extra],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(self.container, MEZO_ROLE=ROLE,
                                                    PYTHONIOENCODING="utf-8"))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def save(self, text, *extra):
        """Сохранение из СВЕЖЕГО файла (час файла новее записи — вопрос про старый файл не мешает)."""
        self.n += 1
        f = self.work / f"body{self.n}.md"
        f.write_text(text, encoding="utf-8", newline="")
        return self.run("--file", str(f), *extra)

    def sql(self, query, *params, write=False):
        conn = sqlite3.connect(str(self.db))
        try:
            rows = conn.execute(query, params).fetchall()
            if write:
                conn.commit()
            return rows
        finally:
            conn.close()

    def body(self):
        rows = self.sql("SELECT body FROM phoenix WHERE role=? AND section=?", ROLE, SECTION)
        return rows[0][0] if rows else None

    def versions(self):
        """Все версии раздела — история и архив — по номеру: (id, saved_at, body, reason)."""
        return self.sql(
            "SELECT id, saved_at, body, reason FROM (SELECT id, saved_at, body, reason FROM phoenix_history "
            "WHERE role=? AND section=? UNION ALL SELECT id, saved_at, body, reason "
            "FROM phoenix_history_archive WHERE role=? AND section=?) ORDER BY id",
            ROLE, SECTION, ROLE, SECTION)

    def id_of(self, text):
        found = [v for v in self.versions() if v[2] == text]
        return found[-1] if found else None


def run_cases(st, label):
    """Все случаи на одном стенде. Возвращает False, если опыт не поставлен."""
    # подготовка: четыре разные версии A, B, C, D
    texts = {name: body_of(name) for name in "ABCD"}
    for name in "ABCD":
        code, out = st.save(texts[name])
        if code != 0:
            print(f"⛔ ОПЫТ НЕ ПОСТАВЛЕН ({label}): подготовительное сохранение «{name}» упало (код {code})")
            print(out)
            return False
    print(f"   основание ({label}): версий в истории {len(st.versions())}, тело — версия D")

    # ①к ВСТРЕЧНЫЙ: обычная запись
    e_text = body_of("E")
    code, out = st.save(e_text)
    ok_line = "сличение после записи: тело в базе равно поданному"
    check("①к", code == 0 and ok_line in out and st.body() == e_text,
          f"обычная запись: код {code} (ждали 0) · строка сличения: {'да' if ok_line in out else 'НЕТ'} "
          f"· тело в базе — поданное: {'да' if st.body() == e_text else 'НЕТ'}")

    # ① после записи в базе другое тело: триггер дописывает к телу знаки
    st.sql("CREATE TRIGGER bite792_mangle AFTER UPDATE OF body ON phoenix BEGIN "
           "UPDATE phoenix SET body = body || 'ПОРЧА' WHERE role = NEW.role AND section = NEW.section; END",
           write=True)
    f_text = body_of("F")
    code, out = st.save(f_text)
    in_db = st.body()
    problems = []
    if code != 6:
        problems.append(f"код {code}, ждали 6")
    if "СЛИЧЕНИЕ ПОСЛЕ ЗАПИСИ НЕ СОШЛОСЬ" not in out:
        problems.append("отказа словами нет")
    if f"подано ... {len(f_text)} знаков" not in out or f"в базе ... {len(in_db or '')} знаков" not in out:
        problems.append("длины не названы")
    if "первая отличная строка" not in out:
        problems.append("номер первой отличной строки не назван")
    if ok_line in out:
        problems.append("строка «равно поданному» напечатана при расхождении")
    check("①", not problems,
          f"в базе после записи другое тело: код {code} (ждали 6) · подано {len(f_text)} → в базе "
          f"{len(in_db or '')} знаков" + ("" if not problems else " · " + "; ".join(problems)))
    st.sql("DROP TRIGGER bite792_mangle", write=True)

    # ⑤а --confirm
    before_body, before_n = st.body(), len(st.versions())
    code, out = st.run("--confirm")
    check("⑤а", code == 0 and "ВЗГЛЯД ОТМЕЧЕН" in out and st.body() == before_body
          and len(st.versions()) == before_n,
          f"--confirm: код {code} (ждали 0) · взгляд отмечен: {'да' if 'ВЗГЛЯД ОТМЕЧЕН' in out else 'НЕТ'} "
          f"· тело и число версий ({before_n}) те же: "
          f"{'да' if st.body() == before_body and len(st.versions()) == before_n else 'НЕТ'}")

    # ⑤б подано тело, равное нынешнему
    code, out = st.save(st.body())
    check("⑤б", code == 0 and "СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ" in out and len(st.versions()) == before_n,
          f"тело равно нынешнему: код {code} (ждали 0) · «СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ»: "
          f"{'да' if 'СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ' in out else 'НЕТ'} · число версий то же: "
          f"{'да' if len(st.versions()) == before_n else 'НЕТ'}")

    # ⑤в --restore <id>: возврат версии B по явному слову
    vb = st.id_of(texts["B"])
    n_before = len(st.versions())
    code, out = st.run("--restore", str(vb[0]))
    latest = st.versions()[-1]
    check("⑤в", code == 0 and st.body() == texts["B"] and len(st.versions()) == n_before + 1
          and latest[3] == f"restore {vb[0]}",
          f"--restore {vb[0]}: код {code} (ждали 0) · тело — версии B: {'да' if st.body() == texts['B'] else 'НЕТ'} "
          f"· версий {n_before} → {len(st.versions())} · причина новой «{latest[3]}»")

    # ②к ВСТРЕЧНЫЙ: тело, которого не было ни в одной версии
    g_text = body_of("G")
    code, out = st.save(g_text)
    check("②к", code == 0 and st.body() == g_text and "ОТКАЗ" not in out,
          f"новое тело, прежних версий с ним нет: код {code} (ждали 0) · записано: "
          f"{'да' if st.body() == g_text else 'НЕТ'}")

    # ② подано тело ПРЕЖНЕЙ версии C (нынешнее — G): отказ ДО записи
    vc = st.id_of(texts["C"])
    cur, n_before = st.body(), len(st.versions())
    code, out = st.save(texts["C"])
    problems = []
    if code != 5:
        problems.append(f"код {code}, ждали 5")
    if "ПРЕЖНЕЙ версии" not in out:
        problems.append("отказа словами нет")
    if f"id={vc[0]}" not in out or vc[1] not in out:
        problems.append(f"не названы номер {vc[0]} и час {vc[1]}")
    if f"--restore {vc[0]}" not in out:
        problems.append("нет подсказки --restore")
    if st.body() != cur:
        problems.append("тело в базе изменилось")
    if len(st.versions()) != n_before:
        problems.append(f"версий было {n_before}, стало {len(st.versions())}")
    check("②", not problems,
          f"подано тело версии C (id={vc[0]}, {vc[1]} UTC): код {code} (ждали 5) · версий {n_before} → "
          f"{len(st.versions())}" + ("" if not problems else " · " + "; ".join(problems)))

    # ②а то же холостым прогоном
    cur, n_before = st.body(), len(st.versions())
    code, out = st.save(texts["C"], "--dry-run")
    problems = []
    if code != 5 or "ПРЕЖНЕЙ версии" not in out:
        problems.append(f"код {code}, ждали 5 и слова об отказе")
    if st.body() != cur or len(st.versions()) != n_before:
        problems.append("база изменилась")
    check("②а", not problems,
          f"то же холостым прогоном: код {code} (ждали 5) · версий {n_before} → {len(st.versions())}"
          + ("" if not problems else " · " + "; ".join(problems)))

    # ②б ВСТРЕЧНЫЙ: нынешнее тело с «\r\n» (правка мимо инструмента), подан тот же текст с «\n» — это
    # круг --read --out → --file (карточка #707), а не возврат прежней версии: код 0, в базе текст с «\n»
    cur = st.body()
    st.sql("UPDATE phoenix SET body = ? WHERE role = ? AND section = ?",
           cur.replace("\n", "\r\n"), ROLE, SECTION, write=True)
    code, out = st.save(cur)
    check("②б", code == 0 and st.body() == cur and "ОТКАЗ" not in out,
          f"то же тело, но нынешнее с «\\r\\n»: код {code} (ждали 0) · в базе текст с «\\n»: "
          f"{'да' if st.body() == cur else 'НЕТ'}")
    return True


stand = mezo_stand.new("bite-body-equal")
tool_sha_before = sha(tool)
try:
    live = Path(os.environ["MEZO_LIVE_DB"]) if os.environ.get("MEZO_LIVE_DB") \
        else mezo_target.scripts_root().parent / "mezosync.db"
    if not live.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: схему подставной базы брать неоткуда — нет {live}")
        print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего. Назови MEZO_LIVE_DB=<база со схемой>.")
        sys.exit(mezo_stand.finish(2))
    container = stand / "contour"
    (container / ".mezosync").mkdir(parents=True)
    db = container / ".mezosync" / "mezosync.db"
    mezo_stand.empty_db(live, db)
    mezo_stand.seed_roles(db, [ROLE])
    work = stand / "files"
    work.mkdir()

    runner = tool
    if args.breakage:
        anchor, broken, expected = BREAKS[args.breakage]
        broken_dir = stand / "broken"
        broken_dir.mkdir()
        runner = mezo_stand.copy_tool(tool, broken_dir)
        text = runner.read_text(encoding="utf-8")
        hits = text.count(anchor)
        if hits != 1:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: место поломки «{args.breakage}» найдено {hits} раз, ждали ровно 1.")
            print("   Это отказ ОПЫТА: без поставленной поломки прошедшие случаи ничего не доказывают.")
            sys.exit(mezo_stand.finish(2))
        runner.write_text(text.replace(anchor, broken), encoding="utf-8")
        print(f"⚖️ НАРОЧНАЯ ПОЛОМКА «{args.breakage}» стоит в КОПИИ: {runner}")
    print("═" * 92)
    print(f"ПРИЁМКА карточки #792 · инструмент: {tool} · основание схемы: {live.name}"
          + (f" · ПОЛОМКА «{args.breakage}»" if args.breakage else ""))
    print("═" * 92)

    st = Stand(runner, db, container, work)
    if not run_cases(st, args.breakage or "без поломки"):
        sys.exit(mezo_stand.finish(2))

    tool_sha_after = sha(tool)
    check("③", tool_sha_before == tool_sha_after,
          f"отпечаток sha256 {tool.name} до {tool_sha_before} · после {tool_sha_after}: "
          f"{'один и тот же' if tool_sha_before == tool_sha_after else 'РАЗНЫЕ'}")

    print()
    total = 10
    if args.breakage:
        want = BREAKS[args.breakage][2]
        got = {f for f in failures if f != "③"}
        if got == want and "③" not in failures:
            print(f"ИТОГ: НАРОЧНАЯ ПОЛОМКА «{args.breakage}» ПОЙМАНА: упали ровно {', '.join(sorted(want))}; "
                  f"остальные случаи прошли (случаев {total})")
            mezo_stand.expected_break()
        else:
            print(f"ИТОГ: ⚠️ НАРОЧНАЯ ПОЛОМКА «{args.breakage}»: ждали падения ровно {sorted(want)}, "
                  f"упали {sorted(failures) or 'ни один'}")
        sys.exit(mezo_stand.finish(1))
    if failures:
        print(f"ИТОГ: 🔴 ПРОВАЛИЛОСЬ случаев: {len(failures)} из {total}: {', '.join(failures)}")
        sys.exit(mezo_stand.finish(1))
    print(f"ИТОГ: ✅ ВСЕ СЛУЧАИ ПРОШЛИ ({total}) — сличение после записи стоит, возврат прежней версии "
          f"отказан, три законных случая проходят.")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
