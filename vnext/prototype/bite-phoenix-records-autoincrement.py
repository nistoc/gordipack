# -*- coding: utf-8 -*-
"""ПРИЁМКА шага схемы 20260904-phoenix-records-autoincrement — карточка #532 (причина).

Всё на КОПИИ живой базы; живая не открывается на запись ни одним случаем.

СЛУЧАИ:
  ① КОНТРОЛЬ на НЕмигрированной копии: удалить последнюю запись → вставить новую →
     номер ПОВТОРИЛСЯ. Это беда карточки, воспроизведённая опытом, а не прочитанная
     в коде. Не воспроизвелась — опыт не различает, и всё ниже не значит ничего.
  ② холостой прогон: отпечаток базы (все таблицы) НЕ изменился.
  ③ применение: каждая строка на месте — число, сумма длин, отпечаток (id·role·section·body).
  ④ AUTOINCREMENT в схеме · счётчик ≥ max(id) · четыре указателя на месте · журнал верен.
  ⑤ ГЛАВНЫЙ: тот же опыт, что ①, на мигрированной копии → номер НЕ повторился.
  ⑥ повторный запуск шага — «уже сведено», база не тронута (отпечаток тот же).
  ⑦ ВСТРЕЧНЫЙ: инструмент памяти на мигрированной копии собирает тело знак в знак
     (пересборка не сломана сменой ключа).
  ⑧ ПОРЧА: подменить в копии шага сверку «до сноса» на ложь → шаг обязан ОТКАТИТЬ
     и оставить базу нетронутой (отпечаток тот же, phoenix_records_new не осталась).
"""
import argparse
import hashlib
import io
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
LIVE = ROOT / ".mezosync" / "mezosync.db"
STEP = ROOT / ".mezosync" / "scripts" / "migrations" / "20260904-phoenix-records-autoincrement.py"
MEMORY_TOOL = HERE / "memory-records.py"

sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402 — карточка #505/#624: согласованная копия живой базы

passed: list[str] = []
failed: list[str] = []
# ⚡ КАРТОЧКА #613: среда для subprocess.run внутри run() — выставляется main() ДО первого
# вызова (mezo_stand.stand_env(sandbox)), чтобы испытуемые (STEP/MEMORY_TOOL) не подхватили
# MEZO_CONTAINER вызывающего. Ни STEP, ни MEMORY_TOOL её не читают (проверено grep'ом по
# обоим файлам) — переменная здесь для единообразия с остальными приёмками, а не по нужде.
STAND_ENV: dict | None = None


def case(title: str, ok: bool, detail: str = "") -> None:
    (passed if ok else failed).append(title)
    print(f"  {'✅' if ok else '🔴'} {title}")
    if not ok and detail:
        for line in detail.strip().splitlines()[:8]:
            print(f"       {line}")


def run(*args, env=None):
    base = dict(STAND_ENV) if STAND_ENV is not None else dict(os.environ)
    p = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", env=dict(base, PYTHONIOENCODING="utf-8", **(env or {})))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def db_fingerprint(path) -> str:
    """Хэш ВСЕХ строк всех таблиц — чтобы «база не тронута» было утверждением, а не надеждой."""
    c = sqlite3.connect(path)
    h = hashlib.sha256()
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        h.update(t.encode())
        for row in c.execute(f"SELECT * FROM {t} ORDER BY 1"):
            h.update(repr(row).encode("utf-8"))
    c.close()
    return h.hexdigest()[:16]


def records_fingerprint(path):
    c = sqlite3.connect(path)
    h = hashlib.sha256(); n = 0; s = 0
    for id_, role, section, body in c.execute(
            "SELECT id, role, section, body FROM phoenix_records ORDER BY id"):
        h.update(f"{id_}\x1f{role}\x1f{section}\x1f{body}\x1e".encode("utf-8")); n += 1; s += len(body)
    c.close()
    return n, s, h.hexdigest()[:16]


def strip_counter(path) -> None:
    """Изготовить состояние «ДО шага» на копии: пересобрать таблицу БЕЗ AUTOINCREMENT,
    убрать счётчик и запись шага из журнала.

    🩸 ПОЙМАНО 04.09 20:43 UTC, через шесть минут после применения шага к живой: приёмка
    покраснела 4 из 8 — контроль ① «без счётчика номер повторяется» перестал воспроизводиться,
    потому что живая база УЖЕ со счётчиком, и копия с неё — тоже. Приёмка судила состояние,
    которого больше нет.
    ⚡ КЛАСС: ПРИЁМКА ШАГА СХЕМЫ ЖИВЁТ ОДИН ПРОГОН — после применения к живой её контроль
    исчезает, и она либо краснеет навсегда (эту красноту перестанут читать), либо, что хуже,
    судит «уже сведено» как успех. Лечится тем, что приёмка ИЗГОТАВЛИВАЕТ «до» сама и
    проверяет, что изготовила (случай ⓪), а не надеется застать его в живой базе.
    """
    c = sqlite3.connect(path)
    ddl = c.execute("SELECT sql FROM sqlite_master WHERE name='phoenix_records'").fetchone()[0]
    if "AUTOINCREMENT" not in ddl.upper():
        c.close(); return
    fields = ("id, role, section, subject, body, body_chars, happened_at, source, expiry_cond, "
            "alive, revoked_at, revoked_note, ord, origin_chars, created_at, created_by")
    c.execute("BEGIN")
    c.execute(ddl.replace("AUTOINCREMENT", "").replace("phoenix_records", "phoenix_records_old", 1))
    c.execute(f"INSERT INTO phoenix_records_old ({fields}) SELECT {fields} FROM phoenix_records")
    c.execute("DROP TABLE phoenix_records")
    c.execute("ALTER TABLE phoenix_records_old RENAME TO phoenix_records")
    for stmt in ("CREATE INDEX idx_phoenix_records_role    ON phoenix_records(role, section, ord)",
              "CREATE INDEX idx_phoenix_records_subject ON phoenix_records(role, subject)",
              "CREATE INDEX idx_phoenix_records_alive   ON phoenix_records(role, alive)",
              "CREATE INDEX idx_phoenix_records_when    ON phoenix_records(role, happened_at)"):
        c.execute(stmt)
    c.execute("DELETE FROM sqlite_sequence WHERE name='phoenix_records'")
    c.execute("DELETE FROM schema_migrations WHERE version='20260904-phoenix-records-autoincrement'")
    c.execute("COMMIT")
    c.close()


def _insert_probe(c) -> int:
    cur = c.execute("INSERT INTO phoenix_records (role, section, subject, body, body_chars, created_by) "
                    "VALUES ('ПРОБА', 'state', 'разное', 'подсадка приёмки', 16, 'bite')")
    return cur.lastrowid


def id_reuse_experiment(path, old_check: bool = False) -> tuple[int, int]:
    """Удалить запись, вставить новую. Вернуть (удалённый, новый).

    ⚡ КАРТОЧКА #631: прежний опыт удалял запись с MAX(id) ХВОСТА, КАКИМ ОН ЗАСТАЛ базу
    (живой или изготовленной из неё), и ждал ТОТ ЖЕ номер обратно — верно только когда
    прямо ПЕРЕД удаляемым номером нет пропуска. У живой базы 14.09 хвост 910·911·913
    (912 выдан и удалён РАНЕЕ, этим опытом никак не тронут): опыт сносил 913, текущий
    MAX совмещался с 911, и SQLite (без AUTOINCREMENT) выдавал новой записи 912 — номер
    уже бывший в ходу (беда карточки #532 живая), но НЕ РАВНЫЙ удалённому — старая формула
    «==» её не видела и приёмка считала «повтора нет» ошибочно.
    ⇒ ОПЫТ ГОТОВИТ СВОЁ УСЛОВИЕ САМ: две свои пробные записи ПОДРЯД гарантированно смежны
    (SQLite без AUTOINCREMENT отдаёт «текущий MAX(rowid)+1», а сразу после первой вставки
    текущий MAX — она сама), и удаление ВТОРОЙ снова совмещает MAX с ПЕРВОЙ — своей же,
    БЕЗ зависимости от пропусков глубже в хвосте живой базы (проверено случаем ①-бис на
    копии с нарочно устроенным пропуском вплотную под максимумом — том же классе, что живой).

    old_check — карточка #631③, нарочная поломка: вернуть ПРЕЖНЮЮ (полагающуюся на
    существующий хвост) формулу, чтобы встречный случай ①-бис на копии с пропуском провалился.
    """
    c = sqlite3.connect(path)
    if old_check:
        mx = c.execute("SELECT MAX(id) FROM phoenix_records").fetchone()[0]
        c.execute("DELETE FROM phoenix_records WHERE id=?", (mx,))
        new_id = _insert_probe(c)
        c.commit(); c.close()
        return mx, new_id
    first_id = _insert_probe(c)
    second_id = _insert_probe(c)
    c.execute("DELETE FROM phoenix_records WHERE id=?", (second_id,))
    new_id = _insert_probe(c)
    c.commit(); c.close()
    return second_id, new_id


def make_gap_before_max(path) -> None:
    """Устроить на копии пропуск ВПЛОТНУЮ под максимумом — тот же рисунок хвоста, что
    у живой базы 14.09 (910 · 911 · 913, 912 выдан и снесён РАНЕЕ). Для встречного случая
    ①-бис (карточка #631②): вставить две свои записи подряд и снести ПЕРВУЮ — остаётся
    ВТОРАЯ (новый максимум) с пропуском ровно под ней, независимо от того, что было в
    хвосте копии ДО этого вызова.
    """
    c = sqlite3.connect(path)
    lower_id = _insert_probe(c)
    _insert_probe(c)
    c.execute("DELETE FROM phoenix_records WHERE id=?", (lower_id,))
    c.commit(); c.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_name", choices=["old-check"], default=None,
                    help="нарочная поломка (карточка #631): old-check — вернуть прежнюю "
                         "формулу опыта id_reuse_experiment (зависит от хвоста живой)")
    args = ap.parse_args()
    old_check = args.break_name == "old-check"

    print("=" * 88)
    print("ПРИЁМКА шага 20260904-phoenix-records-autoincrement — карточка #532 (причина)")
    print(f"шаг: {STEP}")
    print(f"живая база (только копируется): {LIVE}")
    if old_check:
        print("⚠️ ПОРЧА «old-check» ВЗВЕДЕНА — id_reuse_experiment судит по MAX(id) хвоста, "
              "не по своей паре записей; ждём красного в ①-бис (копия с пропуском)")
    print("=" * 88)
    for f in (STEP, LIVE, MEMORY_TOOL):
        if not f.is_file():
            sys.exit(f"⛔ ОТКАЗ МЕРИТЬ: нет файла {f}")

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = pathlib.Path(tmp)
        (sandbox / "scripts").mkdir()
        global STAND_ENV
        STAND_ENV = mezo_stand.stand_env(sandbox)          # карточка #613
        # копия базы лежит так, чтобы шаг с --db её нашёл; журнал схемы — рядом со скриптами
        control_copy = sandbox / "control.db"
        step_db = sandbox / "step.db"
        mezo_stand.snapshot_db(LIVE, control_copy)  # карточка #505/#624: согласованная копия, не shutil.copy2
        mezo_stand.snapshot_db(LIVE, step_db)

        print()
        print("── ⓪ ИЗГОТОВЛЕНИЕ «ДО»: копии приводятся к состоянию без счётчика ────")
        live_records_fp = records_fingerprint(step_db)
        for copy_path in (control_copy, step_db):
            strip_counter(copy_path)
        c = sqlite3.connect(step_db)
        ddl0 = c.execute("SELECT sql FROM sqlite_master WHERE name='phoenix_records'").fetchone()[0]
        journal0 = c.execute("SELECT 1 FROM schema_migrations WHERE version='20260904-phoenix-records-autoincrement'").fetchone()
        c.close()
        case("⓪ копия приведена к «до»: AUTOINCREMENT снят, записи целы, шага в журнале нет",
               "AUTOINCREMENT" not in ddl0.upper() and records_fingerprint(step_db) == live_records_fp and not journal0,
               f"AUTOINCREMENT={'AUTOINCREMENT' in ddl0.upper()} записи={records_fingerprint(step_db)==live_records_fp} журнал={bool(journal0)}")

        print()
        print("── ① КОНТРОЛЬ: беда воспроизводится на НЕмигрированной копии ─────────")
        deleted_id, new_id = id_reuse_experiment(control_copy)
        case("① без счётчика: удалённый номер ВЫДАН ЗАНОВО (беда карточки видна опытом)",
               deleted_id == new_id, f"удалён {deleted_id}, новый {new_id} — повтора нет, опыт не различает")

        # ①-бис ВСТРЕЧНЫЙ (карточка #631②③): та же беда, на копии с пропуском ВПЛОТНУЮ
        # под максимумом — рисунок хвоста живой базы 14.09 (910·911·913). Контроль ①
        # обязан увидеть беду НЕЗАВИСИМО от того, есть ли такой пропуск: опыт готовит
        # СВОЮ пару записей и потому не зависит от чужого хвоста (см. id_reuse_experiment).
        # Под порчей --break old-check (прежняя формула «удалённый == MAX(id) хвоста»)
        # этот случай обязан провалиться — ровно то, что произошло у COORD 14.09 17:25 UTC.
        gap_copy = sandbox / "gap.db"
        mezo_stand.snapshot_db(LIVE, gap_copy)
        strip_counter(gap_copy)
        make_gap_before_max(gap_copy)
        gap_deleted, gap_new = id_reuse_experiment(gap_copy, old_check=old_check)
        case("①-бис ВСТРЕЧНЫЙ: беда видна и на копии с пропуском вплотную под максимумом "
               "(рисунок хвоста живой 14.09: 910·911·913)",
               gap_deleted == gap_new,
               f"удалён {gap_deleted}, новый {gap_new} — повтора нет, опыт не различает "
               f"(тот же класс беды, что нашёл COORD 14.09 17:25 UTC на живом хвосте)")

        print()
        print("── ②–⑥ ШАГ на копии ──────────────────────────────────────────────────")
        before = db_fingerprint(step_db)
        code, output = run(STEP, "--db", step_db, "--dry-run")
        case("② холостой прогон: код 0, база НЕ тронута (отпечаток всех таблиц тот же)",
               code == 0 and "ВХОЛОСТУЮ" in output and db_fingerprint(step_db) == before, output)

        records_before = records_fingerprint(step_db)
        code, output = run(STEP, "--db", step_db)
        records_after = records_fingerprint(step_db)
        case("③ применение: каждая запись на месте (число · сумма длин · отпечаток совпали)",
               code == 0 and records_before == records_after and "ВРЕЗАНО" in output,
               f"код {code} · до {records_before} · после {records_after}" + chr(10) + output)

        c = sqlite3.connect(step_db)
        ddl = c.execute("SELECT sql FROM sqlite_master WHERE name='phoenix_records'").fetchone()[0]
        seq = c.execute("SELECT seq FROM sqlite_sequence WHERE name='phoenix_records'").fetchone()
        mx = c.execute("SELECT MAX(id) FROM phoenix_records").fetchone()[0]
        idx = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='phoenix_records' "
                        "AND name LIKE 'idx_%'").fetchone()[0]
        leftover = c.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_records_new'").fetchone()
        c.close()
        case("④ AUTOINCREMENT в схеме · счётчик ≥ max(id) · 4 указателя · хвоста _new нет · журнал верен",
               "AUTOINCREMENT" in ddl and seq and seq[0] >= mx and idx == 4 and not leftover
               and "✅ проверка журнала" in output,
               f"AUTOINCREMENT={'AUTOINCREMENT' in ddl} seq={seq} max={mx} idx={idx} хвост={bool(leftover)}")

        deleted_id, new_id = id_reuse_experiment(step_db)
        case("⑤ ГЛАВНЫЙ: после шага удалённый номер НЕ повторяется",
               new_id != deleted_id and new_id > deleted_id, f"удалён {deleted_id}, новый {new_id}")

        before2 = db_fingerprint(step_db)
        code, output = run(STEP, "--db", step_db)
        case("⑥ повторный запуск: «уже сведено», база не тронута",
               code == 0 and "уже сведено" in output and db_fingerprint(step_db) == before2, output)

        # ⑦ инструмент памяти: исход сборки КАЖДОЙ пары роль·раздел на мигрированной копии
        # обязан быть ТЕМ ЖЕ, что на немигрированной. 🩸 Первая редакция требовала «сходится» —
        # и покраснела на COORD·state, где слои разошлись В ЖИВОЙ базе ещё до шага (роль
        # сохранила память после разбора). Шаг за чужое расхождение не отвечает; отвечает
        # за то, чтобы НИЧЕГО не изменить — и это здесь и судится.
        c = sqlite3.connect(control_copy)
        pairs = c.execute("SELECT role, section FROM phoenix_records WHERE role<>'ПРОБА' "
                         "GROUP BY role, section ORDER BY 1, 2").fetchall()
        c.close()
        def outcome(db, role, section):
            code, out = run(MEMORY_TOOL, "--db", db, "--role", role, "--section", section, "--собрать")
            lines = [line.strip() for line in out.splitlines() if 'собрано знаков' in line or 'живое тело' in line
                      or 'сходится' in line or 'РАСХОЖДЕНИЕ' in line]
            return (code, tuple(lines))
        diff = [(role, section) for role, section in pairs if outcome(control_copy, role, section) != outcome(step_db, role, section)]
        matching = sum(1 for role, section in pairs if outcome(step_db, role, section)[0] == 0)
        case(f"⑦ ВСТРЕЧНЫЙ: исход сборки всех {len(pairs)} пар роль·раздел ОДИНАКОВ до и после шага "
               f"(сходятся {matching}, расходятся в живой базе {len(pairs)-matching} — не предмет шага)",
               not diff, f"исход отличается у: {diff}")

        print()
        print("── ⑧ ПОРЧА копии шага: сверка «до сноса» солгала → обязан откатить ─────")
        corrupt_db = sandbox / "porcha.db"
        mezo_stand.snapshot_db(LIVE, corrupt_db)  # карточка #505/#624: согласованная копия, не shutil.copy2
        strip_counter(corrupt_db)
        original_text = STEP.read_text(encoding="utf-8")
        # ⚠️ строка ниже — образец из ЧУЖОГО файла (самого шага STEP), его имена «после»/«до»
        # там его собственные и переводу этого правила не подлежат (не наш идентификатор)
        corrupted_text = original_text.replace("        if после != до:", "        if после == до:")
        if corrupted_text == original_text:
            case("⑧ ПОРЧА: образец не найден — ОПЫТ НЕ ПОСТАВЛЕН", False, "порча не легла")
        else:
            corrupt_copy = STEP.parent / "_porcha_autoincrement_bite.py"   # рядом: шаг ищет журнал от своего места
            try:
                corrupt_copy.write_text(corrupted_text, encoding="utf-8")
                before3 = db_fingerprint(corrupt_db)
                code, output = run(corrupt_copy, "--db", corrupt_db)
                c = sqlite3.connect(corrupt_db)
                leftover = c.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_records_new'").fetchone()
                c.close()
                case("⑧ порченый шаг ОТКАТИЛ: код ≠ 0, «откат» в выводе, база нетронута, хвоста нет",
                       code != 0 and "откат" in output.lower() and db_fingerprint(corrupt_db) == before3 and not leftover,
                       f"код {code} · хвост={bool(leftover)}" + chr(10) + output)
            finally:
                if corrupt_copy.exists():
                    corrupt_copy.unlink()

        print()
        print("── ⑨⑩ ПРЕДУСЛОВИЯ СЛОВАМИ (приёмка @STUD карточки #380 — тот же класс) ─")
        nojournal_db = sandbox / "nojournal.db"
        mezo_stand.snapshot_db(LIVE, nojournal_db)  # карточка #505/#624: согласованная копия, не shutil.copy2
        c = sqlite3.connect(nojournal_db); c.execute("DROP TABLE schema_migrations"); c.commit(); c.close()
        before9 = db_fingerprint(nojournal_db)
        code, output = run(STEP, "--db", nojournal_db)
        case("⑨ база БЕЗ журнала схемы → отказ СЛОВАМИ (назван журнал и что сделать), код 1, без стека, база не тронута",
               code == 1 and "НЕТ ЖУРНАЛА СХЕМЫ" in output and "migrate-live.py" in output
               and "Traceback" not in output and db_fingerprint(nojournal_db) == before9, f"код {code}" + chr(10) + output)
        notadb_db = sandbox / "notadb.db"
        notadb_db.write_text("просто текст, не база", encoding="utf-8")
        code, output = run(STEP, "--db", notadb_db)
        case("⑩ файл-не-база → отказ СЛОВАМИ («не база SQLite»), код 1, без стека",
               code == 1 and "не база SQLite" in output and "Traceback" not in output, f"код {code}" + chr(10) + output)

    print()
    print("=" * 88)
    print(f"ИТОГ: прошло {len(passed)} · пало {len(failed)}")
    for name in failed:
        print(f"   🔴 {name}")
    print("=" * 88)
    print("⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ: поведение ЖИВОЙ базы под живой нагрузкой —")
    print("   всё здесь на копии. Что копия и живая равносильны, доказывает не совпадение")
    print("   файлов, а прогон инструментов памяти ПОСЛЕ применения к живой (сделать рукой).")
    print("   И состояние «до» здесь ИЗГОТОВЛЕНО (случай ⓪), а не застигнуто: после 04.09")
    print("   20:37 UTC живой базы без счётчика нет. Обратная пересборка — мой же код, и")
    print("   если она врёт так же, как шаг, оба зелёные разом. Отдельного судьи у этого нет.")
    if old_check:
        # ⚡ КАРТОЧКА #631③: порча «old-check» обязана ровно ①-бис (встречный на копии
        # с пропуском) — остальные случаи её не видят: ① не различает старую/новую формулу
        # на СЕГОДНЯШНЕМ хвосте живой (в нём пропуск уже есть — см. беду карточки), а ⑤
        # защищён AUTOINCREMENT независимо от формулы опыта.
        expected = {"①-бис ВСТРЕЧНЫЙ: беда видна и на копии с пропуском вплотную под максимумом "
                   "(рисунок хвоста живой 14.09: 910·911·913)"}
        if set(failed) == expected:
            print(f"\n✅ так и надо: под порчей «old-check» провалился ровно {sorted(expected)}")
            return 0
        print(f"\n⚠️ ПОРЧА «old-check» ВЗВЕДЕНА, А ПРОВАЛИЛОСЬ НЕ ТО: ждали ровно {sorted(expected)}, "
              f"получили {sorted(failed)}")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
