# -*- coding: utf-8 -*-
"""
bite-r16.py — R16: «пока батч не подтверждён, ридер отдаёт ТОТ ЖЕ батч и ТЕ ЖЕ половинки».

⚠️ ПЕРЕПИСАН 2026-07-26 09:xx UTC по находке COORD (#2748) и собственному замеру.
   Прежняя версия была НЕГОДНА как регрессия и молча давала ложно-зелёное. Два дефекта,
   оба — один класс («укус не проверяет своё предусловие», мой же класс из #2693):

   ① BASELINE-ЛОЖЬ. Секция «ДО» брала `<песочница>/scripts/read-messages.py` — копию ЖИВОГО
      ридера. После врезки R16 в живой контур (COORD, `fc0e9dd`) bootstrap копирует уже
      ПОЧИНЕННЫЙ скрипт ⇒ раздел «ДО» печатал «(тот же)» там, где ожидался «(ДРУГОЙ)».
      Укус честно печатал наблюдение — и оно означало «baseline не является ДО», а читалось
      как «боль не воспроизводится». Демонстрация, выданная за тест.
   ② СЛЕПОТА К НАКОПЛЕННОМУ СОСТОЯНИЮ. Первой же строкой стоял
      `DELETE FROM read_batches WHERE role = ?` — «чистая исходная позиция». Ровно этим
      стиралось состояние, в котором живёт класс ошибок. Замер 2026-07-26 09:05 UTC:
          живая БД   — 60 открытых батчей, из них 58 ПРОТУХШИХ (last_id <= курсора)
          песочница  — 59 открытых, 54 протухших   ⇒ снимок НЕ слеп, состояние в нём есть
          PROTO      — 3 открытых батча в живой, 0 в песочнице  ⇐ их стёр этот укус
      Именно на протухших батчах COORD поймал дефект первой версии R16 (перевыдала бы
      УКОРОЧЕННЫЙ старый диапазон = тихая потеря видимости). Укус этого показать не мог:
      он убирал предмет измерения до измерения.
      📌 Класс в карту: УКУС, НОРМАЛИЗУЮЩИЙ СОСТОЯНИЕ ПЕРЕД ЗАМЕРОМ, СЛЕП К ОШИБКАМ
         НАКОПЛЕННОГО СОСТОЯНИЯ. «Чистая исходная позиция» — не гигиена, а потеря условия.

РЕЖИМЫ РАЗВЕДЕНЫ НАРОЧНО (просьба COORD: «либо параметризовать ДО, либо назвать в шапке,
что это демонстрация, а не тест»). Здесь сделано и то и другое:

    verify  (по умолчанию) — РЕГРЕССИЯ на ЛЮБОЙ врезке. Проверяет свойства целевого ридера,
                             ничего не знает про «до». Годится для чужого кода.
    demo    --baseline P    — ДЕМОНСТРАЦИЯ боли на явно указанной ДО-версии.
                             Предусловие проверяется: если P уже несёт R16 — rc=2, а не рассказ.

Работает на ВРЕМЕННОЙ ПОЛНОЙ КОПИИ песочницы (накопленное состояние сохраняется).
Живой субстрат не открывается вовсе. Предусловие не выполнено — выход с кодом 2.

    python bite-r16.py                          # регрессия по копии живого ридера в песочнице
    python bite-r16.py --target <путь к ридеру>  # регрессия по чужой врезке
    python bite-r16.py demo --baseline <до-версия read-messages.py>
"""
import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROLE = "PROTO"


def run(script, args, cwd=None):
    p = subprocess.run([sys.executable, str(script), *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def halves(text):
    """Половинки разрезанного токена: первая — в первой строке, вторая — в последней."""
    # \w, а НЕ [0-9a-f]: настоящие токены шестнадцатеричны, но метки стендов — нет, и
    # узкий класс давал «свойство не поставлено» там, где ридер честно ответил.
    # Парсер, знающий об измеряемом больше, чем нужно, врёт про непонятный ему ответ.
    h1 = re.search(r"ПЕРВАЯ половина (\w+)", text)
    h2 = re.search(r"ack <первая>-(\w+)", text)
    return (h1.group(1) if h1 else None, h2.group(1) if h2 else None)


def die(reason, *details):
    """rc=2 — предусловие не выполнено. Укус, который не смог поставить опыт,
    обязан сказать это, а не напечатать наблюдение, читаемое как результат."""
    print(f"⛔ ПРИЁМКА НЕ ПОСТАВЛЕНА: {reason}")
    for d in details:
        print("   ·", d)
    sys.exit(2)


def state(db, role):
    """Контекст замера — печатаем ВСЕГДА. Накопленное состояние это условие опыта,
    а не грязь: именно в нём жил дефект, найденный COORD на живой БД."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                      (role,)).fetchone()
    cur = row[0] if row else None
    total = con.execute("SELECT COUNT(*) FROM read_batches WHERE role=?", (role,)).fetchone()[0]
    stale = con.execute("SELECT COUNT(*) FROM read_batches WHERE role=? AND last_id<=?",
                        (role, cur or 0)).fetchone()[0]
    head = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    unread = con.execute("SELECT COUNT(*) FROM messages WHERE id>?", (cur or 0,)).fetchone()[0]
    con.close()
    return cur, total, stale, head, unread


def workbench(sandbox):
    """Полная копия песочницы во временный каталог: опыт не портит песочницу
    и НЕ нормализует её состояние."""
    src_db = sandbox / "mezosync.db"
    if not src_db.exists():
        die(f"нет песочницы: {src_db}",
            "подними её: python vnext/sandbox/bootstrap.py")
    tmp = Path(tempfile.mkdtemp(prefix="bite-r16-"))
    shutil.copy2(src_db, tmp / "mezosync.db")
    for extra in ("mezosync.db-wal", "mezosync.db-shm"):
        if (sandbox / extra).exists():
            shutil.copy2(sandbox / extra, tmp / extra)
    return tmp


def with_deps(reader, tmp):
    """Ридер уезжает в стенд ВМЕСТЕ СО ВСЕМИ соседями-модулями, а не с перечнем руками.

    🪤 Прежде здесь лежал перечень из ОДНОГО имени (mezo_paths) — и он протух молча:
    читалка стала импортировать urgency и sync_backoff, стенд падал на импорте, и провал
    ЗАВИСИМОСТИ выглядел провалом СВОЙСТВА (⚠️ у шести свойств из девяти разом).
    Урок тот же, что у переноса шаблона (#148): «список писала рука, замыкание знает код».
    Считать замыкание импортов честнее, но соседних .py немного — копируем ВСЕХ:
    стенд, собранный целиком, не может отстать от читалки по построению."""
    dest = tmp / reader.name
    shutil.copy2(reader, dest)
    for dep in reader.parent.glob("*.py"):
        if dep.name != reader.name:
            shutil.copy2(dep, tmp / dep.name)
    return dest


def read_twice(reader, db, limit=3):
    _, o1 = run(reader, ["--db", str(db), "--role", ROLE, "--limit", str(limit)])
    _, o2 = run(reader, ["--db", str(db), "--role", ROLE, "--limit", str(limit)])
    return (o1, halves(o1)), (o2, halves(o2))


def readable(out, where):
    """Опыт поставлен? Возвращаем bool, а НЕ убиваем прогон: одно непоставленное свойство
    не должно скрывать три измеренных. Непоставленное ≠ выполненное — общий вердикт
    зелёным от этого не станет (см. all(v is True ...))."""
    if halves(out) == (None, None):
        print(f"⚠️ {where}: ридер не выдал токена — свойство НЕ ПОСТАВЛЕНО")
        for line in out.strip().splitlines()[:3]:
            print("     ", line)
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
def verify(target, sandbox):
    """РЕГРЕССИЯ: проверяем СВОЙСТВА целевого ридера. Про «до» ничего не знаем и не спрашиваем.

    ⚠️ Каждое свойство ставится на СВОЁМ стенде (своя копия песочницы). Иначе P2 тратит
    непрочитанные ноты и P3 нечем ставить — а проверка, которая не поставилась из-за
    предыдущей проверки, это связанность опытов, а не результат."""
    cur, total, stale, head, unread = state(sandbox / "mezosync.db", ROLE)
    if cur is None:
        die(f"роли {ROLE} нет в read_cursors песочницы")
    if unread < 1:
        # ⚠️ ПРИЁМКА НЕ ИМЕЕТ ПРАВА ЗАВИСЕТЬ ОТ МОМЕНТА СНИМКА (найдено 2026-08-09):
        # песочница v3 пересобирается из живой базы, и если роль в этот час дочитала
        # ленту до головы — долга нет, и прежний код отказывался ставиться. То есть
        # приёмка требовала, чтобы МИР оказался удобным. Различающий случай — предмет
        # приёмки, ей его и готовить: отматываем курсор В ПЕСОЧНИЦЕ (не в живой!) назад.
        if head < 5:
            die(f"в песочнице почти пуста лента (голова #{head}) — стендам не из чего строиться")
        back = min(40, head - 1)
        con = sqlite3.connect(str(sandbox / "mezosync.db"))
        con.execute("UPDATE read_cursors SET last_read_id = ? WHERE reader_role = ?",
                    (head - back, ROLE))
        con.commit()
        con.close()
        cur, total, stale, head, unread = state(sandbox / "mezosync.db", ROLE)
        print(f"⚠️ долга у {ROLE} не было — отметка прочитанного отмотана в ПЕСОЧНИЦЕ на {back} назад "
              f"(→ {cur}); живая база не тронута, песочница пересоздаётся строителем")
    print(f"[регрессия R16] цель: {target}")
    print(f"   состояние роли {ROLE}: отметка {cur} · голова #{head} · непрочитано {unread} · "
          f"открытых батчей {total} (из них ПРОТУХШИХ {stale}) — НЕ стираем\n")

    verdicts = []
    stands = []

    # P1 — идемпотентная выдача
    tmp1 = workbench(sandbox); stands.append(tmp1)
    db1, r1 = tmp1 / "mezosync.db", with_deps(target, tmp1)
    (o1, t1), (_, t2) = read_twice(r1, db1)
    ok1 = (t1 == t2 and None not in t1) if readable(o1, "P1") else None
    print(f"P1 идемпотентная выдача: вызов1 {t1[0]}-{t1[1]} · вызов2 {t2[0]}-{t2[1]} "
          f"→ {'✅ тот же' if ok1 else '🔴 РАЗНЫЕ (R16 нет)' if ok1 is False else '⚠️ не поставлено'}")
    verdicts.append(ok1)

    # P2 — гашение одноразовое (свой стенд: ack двигает курсор)
    tmp2 = workbench(sandbox); stands.append(tmp2)
    db2, r2 = tmp2 / "mezosync.db", with_deps(target, tmp2)
    _, o2 = run(r2, ["--db", str(db2), "--role", ROLE, "--limit", "3"])
    if readable(o2, "P2"):
        tok = halves(o2)
        rc_a, _ = run(r2, ["--db", str(db2), "--role", ROLE, "--ack", f"{tok[0]}-{tok[1]}"])
        rc_b, _ = run(r2, ["--db", str(db2), "--role", ROLE, "--ack", f"{tok[0]}-{tok[1]}"])
        ok2 = rc_a == 0 and rc_b != 0
        print(f"P2 гашение одноразовое: ack rc={rc_a} · повтор rc={rc_b} "
              f"→ {'✅ второй отклонён' if ok2 else '🔴 токен переиспользуем'}")
    else:
        ok2 = None
        print("P2 гашение одноразовое: ⚠️ не поставлено")
    verdicts.append(ok2)

    # P3 — протухший батч НЕ перевыдаётся. Регрессия на находку COORD (#2748), которую
    # прежняя версия укуса показать не могла: она стирала read_batches перед замером.
    tmp3 = workbench(sandbox); stands.append(tmp3)
    db3, r3 = tmp3 / "mezosync.db", with_deps(target, tmp3)
    con = sqlite3.connect(str(db3))
    con.execute("DELETE FROM read_batches WHERE role=? AND last_id>?", (ROLE, cur))
    con.execute("INSERT OR REPLACE INTO read_batches (token, role, last_id, issued_at) "
                "VALUES (?,?,?, datetime('now'))", ("dead01-dead02", ROLE, max(cur - 5, 1)))
    con.commit()
    con.close()
    print(f"   [P3 подготовка] в стенд добавлен ПРОТУХШИЙ батч last_id={max(cur-5,1)} "
          f"при отметке {cur} — условие опыта, названное вслух")
    _, o3 = run(r3, ["--db", str(db3), "--role", ROLE, "--limit", "3"])
    t3 = halves(o3)
    m = re.search(r"#(\d+)…#(\d+)", o3)
    span = f"{m.group(1)}…{m.group(2)}" if m else "?"
    ok3 = (t3 != ("dead01", "dead02") and (not m or int(m.group(2)) > cur)) \
        if readable(o3, "P3") else None
    print(f"P3 протухший батч не перевыдан: токен {t3[0]}-{t3[1]} · диапазон #{span} "
          f"→ {'✅ выдан новый, новее отметки' if ok3 else '🔴 ПЕРЕВЫДАН ДРЕВНИЙ (тихая потеря видимости)' if ok3 is False else '⚠️ не поставлено'}")
    verdicts.append(ok3)

    # P4 — из двух АКТУАЛЬНЫХ открытых батчей перевыдаётся САМЫЙ ПОЛНЫЙ, а не самый
    # свежий по времени. Найдено 2026-07-26 09:11 UTC, когда мутант M2 не покраснел:
    # выборка идёт `ORDER BY issued_at DESC`, то есть по ВРЕМЕНИ ВЫДАЧИ. Замер на стенде:
    # курсор 2713, непрочитано 40, открыты батчи A(last_id 2753, 09:00) и B(2723, 09:05) —
    # ридер отдал 10 нот из 40 И БЕЗ предупреждения «упёрлось в лимит» (rest_count считается
    # до урезания батча). Роль решила бы, что новых нот десять.
    # ⚠️ ГРАНИЦА, названная честно: в живой БД на момент находки таких ролей 0 — R16 сам
    # почти не даёт появиться второму актуальному батчу (повторный вызов перевыдаёт первый).
    # Это замечание к КОНСТРУКЦИИ, а не тревога о работающем контуре.
    tmp4 = workbench(sandbox); stands.append(tmp4)
    db4, r4 = tmp4 / "mezosync.db", with_deps(target, tmp4)
    con = sqlite3.connect(str(db4))
    hd = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    back = hd - 40
    ids = [r[0] for r in con.execute("SELECT id FROM messages WHERE id>? ORDER BY id", (back,))]
    if len(ids) < 12:
        die("на стенде мало нот для P4", f"нужно >=12 после {back}, есть {len(ids)}")
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (back, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.executemany(
        "INSERT INTO read_batches (token, role, last_id, issued_at) VALUES (?,?,?,?)",
        [("full01-full02", ROLE, ids[-1], "2026-07-26 09:00:00"),
         ("shrt01-shrt02", ROLE, ids[9], "2026-07-26 09:05:00")])
    con.commit()
    con.close()
    print(f"   [P4 подготовка] отметка отмотана на {back} (непрочитано {len(ids)}); открыты ДВА "
          f"актуальных батча: ПОЛНЫЙ last_id={ids[-1]} (09:00) и КОРОТКИЙ last_id={ids[9]} (09:05)")
    _, o4 = run(r4, ["--db", str(db4), "--role", ROLE, "--limit", "50"])
    t4 = halves(o4)
    m4 = re.search(r"#(\d+)…#(\d+)", o4)
    shown = int(m4.group(2)) - back if m4 else -1
    warned = "УПЁРСЯ В ЛИМИТ" in o4
    ok4 = (t4[0] != "shrt01") if readable(o4, "P4") else None
    print(f"P4 перевыдаётся самый ПОЛНЫЙ батч: токен {t4[0]}-{t4[1]} · показано {shown} "
          f"из {len(ids)} нот · предупреждение об укорочении {'есть' if warned else 'НЕТ'} "
          f"→ {'✅' if ok4 else '🔴 отдан КОРОТКИЙ (выбор по времени выдачи, не по полноте)' if ok4 is False else '⚠️ не поставлено'}")
    verdicts.append(ok4)

    # ── P5…P8: свойства, которые @TAXO назвала НЕПРОВЕРЕННЫМИ (#2752, #2759).
    # Она честно пометила, что про приход новых нот знает ИЗ КОДА, а не из замера.
    # Отвечаем не словом, а опытом.
    print("\n── свойства, названные непроверенными (@TAXO #2759)")

    # P5 — пустой батч: читать нечего ⇒ токен не выдаётся и батч не заводится
    tmp5 = workbench(sandbox); stands.append(tmp5)
    db5, r5 = tmp5 / "mezosync.db", with_deps(target, tmp5)
    con = sqlite3.connect(str(db5))
    hd5, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (hd5, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    _, o5 = run(r5, ["--db", str(db5), "--role", ROLE, "--limit", "5"])
    con = sqlite3.connect(f"file:{db5}?mode=ro", uri=True)
    n5, = con.execute("SELECT COUNT(*) FROM read_batches WHERE role=?", (ROLE,)).fetchone()
    con.close()
    ok5 = halves(o5) == (None, None) and n5 == 0
    print(f"P5 пустой батч: токена нет · батчей заведено {n5} "
          f"→ {'✅ ничего не выдано и не записано' if ok5 else '🔴 выдан токен/батч на пустоте'}")
    verdicts.append(ok5)

    # P6 — смена --limit между вызовами: перевыдача не зависит от лимита
    tmp6 = workbench(sandbox); stands.append(tmp6)
    db6, r6 = tmp6 / "mezosync.db", with_deps(target, tmp6)
    con = sqlite3.connect(str(db6))
    hd6, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (hd6 - 30, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    _, a6 = run(r6, ["--db", str(db6), "--role", ROLE, "--limit", "3"])
    _, b6 = run(r6, ["--db", str(db6), "--role", ROLE, "--limit", "30"])
    span_a = re.search(r"#(\d+)…#(\d+)", a6)
    span_b = re.search(r"#(\d+)…#(\d+)", b6)
    ok6 = (halves(a6) == halves(b6)) and (span_a and span_b and span_a.group(0) == span_b.group(0))
    print(f"P6 смена --limit между вызовами: limit3 {span_a.group(0) if span_a else '?'} · "
          f"limit30 {span_b.group(0) if span_b else '?'} · токен "
          f"{'тот же' if halves(a6) == halves(b6) else 'РАЗНЫЙ'} "
          f"→ {'✅ лимит не рвёт перевыдачу' if ok6 else '🔴 больший лимит порождает другой батч'}")
    verdicts.append(ok6)

    # P7 — два ПАРАЛЛЕЛЬНЫХ вызова из разных процессов: батч должен быть один
    tmp7 = workbench(sandbox); stands.append(tmp7)
    db7, r7 = tmp7 / "mezosync.db", with_deps(target, tmp7)
    con = sqlite3.connect(str(db7))
    hd7, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (hd7 - 20, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    procs = [subprocess.Popen(
        [sys.executable, str(r7), "--db", str(db7), "--role", ROLE, "--limit", "5"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace") for _ in range(2)]
    outs = [p.communicate()[0] for p in procs]
    con = sqlite3.connect(f"file:{db7}?mode=ro", uri=True)
    n7, = con.execute("SELECT COUNT(*) FROM read_batches WHERE role=?", (ROLE,)).fetchone()
    con.close()
    ok7 = n7 == 1 and halves(outs[0]) == halves(outs[1])
    print(f"P7 два ПАРАЛЛЕЛЬНЫХ вызова: батчей в БД {n7} · токены "
          f"{'совпали' if halves(outs[0]) == halves(outs[1]) else 'РАЗОШЛИСЬ'} "
          f"→ {'✅ гонка не плодит батчи' if ok7 else '🔴 параллельные вызовы разъезжаются'}")
    verdicts.append(ok7)

    # P8 — НОВЫЕ ноты, пришедшие между чтениями, в перевыданный батч не входят.
    # @TAXO знала это из кода (:259-264) и честно пометила как непроверенное. Меряем.
    tmp8 = workbench(sandbox); stands.append(tmp8)
    db8, r8 = tmp8 / "mezosync.db", with_deps(target, tmp8)
    con = sqlite3.connect(str(db8))
    hd8, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (hd8 - 6, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    _, a8 = run(r8, ["--db", str(db8), "--role", ROLE, "--limit", "10"])
    con = sqlite3.connect(str(db8))
    con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority, resolved) "
                "VALUES ('COORD', datetime('now'), 'нота, пришедшая МЕЖДУ чтениями', NULL, 'normal', 0)")
    con.commit()
    new_id, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.close()
    _, b8 = run(r8, ["--db", str(db8), "--role", ROLE, "--limit", "10"])
    sp_a = re.search(r"#(\d+)…#(\d+)", a8)
    sp_b = re.search(r"#(\d+)…#(\d+)", b8)
    ok8 = (halves(a8) == halves(b8)) and sp_b and int(sp_b.group(2)) < new_id
    print(f"P8 новая нота между чтениями (#{new_id}): было {sp_a.group(0) if sp_a else '?'} · "
          f"стало {sp_b.group(0) if sp_b else '?'} · токен "
          f"{'тот же' if halves(a8) == halves(b8) else 'РАЗНЫЙ'} "
          f"→ {'✅ новое НЕ втягивается, ждёт следующего батча' if ok8 else '🔴 набор нот батча поехал под ack'}")
    verdicts.append(ok8)

    # P9 — САМОЕ ЧАСТОЕ: разведка малым лимитом → совет инструмента → полный вызов.
    # Ридер сам печатает «Нужен весь хвост сразу — --limit K». Роль выполняет совет,
    # а перевыдача отдаёт ПРЕЖНИЙ короткий батч — и предупреждение об остатке при этом
    # ИСЧЕЗАЕТ (остаток считается от полной выборки ДО урезания: там хвоста уже нет).
    # ⇒ ответ выглядит как «всё прочитано». Это тихая потеря видимости по ШТАТНОМУ пути,
    # а не по редкому: «маленький вызов → полный → ack полного» — самый частый паттерн
    # контура (@STUD #2698). Свойство: после перевыдачи остаток обязан быть НАЗВАН.
    tmp9 = workbench(sandbox); stands.append(tmp9)
    db9, r9 = tmp9 / "mezosync.db", with_deps(target, tmp9)
    con = sqlite3.connect(str(db9))
    hd9, = con.execute("SELECT MAX(id) FROM messages").fetchone()
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (hd9 - 30, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    # ⚠️ РЕФАЙНМЕНТ 2026-07-27 (заявка COORD #2862, врезка `83e8882`). Ридер развёл подачу на две
    # ветки, и P9 стал ЛОЖНО-КРАСНЫМ: остаток теперь назван ЧЕСТНЕЕ прежнего («БАТЧ ПЕРЕВЫДАН
    # (R16) … За ним ещё 7 нот»), а укус краснел — потому что искал остаток ОДНОЙ строчной
    # формой `за ним ещё`. Тест знал ТИПОГРАФИКУ ответа, а не его СМЫСЛ, — мой же класс
    # «проверка знает форму, а не смысл». Текст под тест НЕ подгонялся (COORD прав: тест не
    # диктует формулировку) — расширен тест. Три правки: (а) регистронезависимо, (б) «ПЕРЕВЫДАН»
    # и форма у самой команды ack («за этим батчем ещё N») — валидные способы назвать остаток,
    # (в) при перевыдаче совет `--limit K` НЕ печатается НАМЕРЕННО: до ack он бесполезен, любой
    # лимит вернёт тот же батч. ⇒ этот совет в перевыдаче — теперь ДЕФЕКТ подачи, а не норма.
    _, a9 = run(r9, ["--db", str(db9), "--role", ROLE, "--limit", "3"])
    hint = re.search(r"Нужен весь хвост сразу — --limit (\d+)", a9)
    advised = hint.group(1) if hint else "30"
    _, b9 = run(r9, ["--db", str(db9), "--role", ROLE, "--limit", advised])
    got = len(re.findall(r"^--- #", b9, re.M))
    named = bool(re.search(r"за ним ещё \d+ нот|за этим батчем ещё \d+ нот|УПЁРСЯ В ЛИМИТ"
                          r"|ПЕРЕВЫДАН", b9, re.I))
    reissued = bool(re.search(r"ПЕРЕВЫДАН", b9, re.I))
    # роль зовут к ack — единственное, что РАБОТАЕТ в этом состоянии
    points_to_ack = bool(re.search(r"ack", b9, re.I)) and reissued
    useless = reissued and bool(re.search(r"Нужен весь хвост сразу — --limit", b9))
    full = got >= int(advised)
    ok9 = (full or (named and (points_to_ack or not reissued))) and not useless
    how = ("выдал весь хвост" if full else
           "перевыдал прежний батч, остаток назван, зовёт к ack" if reissued and ok9 else
           "остаток назван" if named and ok9 else
           "СОВЕТУЕТ --limit в перевыдаче — совет бесполезен до ack" if useless else
           "МОЛЧАЛИВЫЙ короткий ответ")
    print(f"P9 совет инструмента исполним: советовал --limit {advised} → выдал {got} нот · "
          f"{how} → {'✅' if ok9 else '🔴 роль выполнила совет и осталась без пути дальше'}")
    verdicts.append(ok9)

    print("\n   стенды оставлены для разбора:")
    for s in stands:
        print("   ·", s)
    names = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9")
    ok = all(v is True for v in verdicts)
    done = sum(1 for v in verdicts if v is True)
    unset = [n for n, v in zip(names, verdicts) if v is None]
    print(f"\n{'✅ R16 ДЕРЖИТСЯ' if ok else '🔴 R16 ДЕРЖИТСЯ НЕ ЦЕЛИКОМ'} — {len(names)} свойств, "
          f"выполнено {done}/{len(names)}"
          + (f" · НЕ ПОСТАВЛЕНО: {', '.join(unset)}" if unset else ""))
    verify.last = dict(zip(names, verdicts))
    return 0 if ok else 1


# ──────────────────────────────────────────────────────────────────────────────
# МУТАНТЫ — доказательство, что зелёное здесь что-то значит.
# Укус, который не умеет краснеть, — украшение. Прежняя версия этого укуса была
# зелёной на пропатченном baseline и читалась как «боль не воспроизводится»;
# лечим не обещанием, а проверкой: портим ридер известным способом и требуем красного.
MUTANTS = {
    # M1 — снять R16 целиком: перевыдачи нет, каждый вызов рождает новый токен.
    "M1-нет-перевыдачи": ([
        ("    reissue = None\n    if not args.all:",
         "    reissue = None\n    if False:"),
    ], "P1"),
    # M2 — ПЕРВАЯ версия R16 у COORD: перевыдаём самый свежий открытый батч БЕЗ проверки
    # «новее курсора». Именно это дало бы укороченный древний диапазон = тихую потерю видимости.
    # ⚠️ ЗАМЕНЫ ДВЕ, и это само по себе находка (2026-07-26 09:10 UTC): первая версия мутанта
    # снимала только условие `last_id > курсора` — и укус остался ЗЕЛЁНЫМ. Оказалось, ридер
    # защищён ДВАЖДЫ: второй раз — фолбэком «прежний батч вне окна выборки ⇒ выдаём новый».
    # Пока мутант не снимал обе защиты, самопроверка честно говорила «укус слеп» — она и
    # заставила это найти. Порча, которую нельзя навести, — не доказательство прочности,
    # пока не названа причина, по которой её нельзя навести.
    "M2-перевыдаёт-протухший": ([
        ("WHERE role = ? AND last_id > ? ", "WHERE role = ? AND last_id > ? - 100000 "),
        ("            if kept:\n                rows = kept\n            else:\n"
         "                reissue = None",
         "            if True:\n                rows = kept or rows\n            else:\n"
         "                reissue = None"),
    ], "P3"),
    # M3 — ОТКАТ ПОДАЧИ к дефекту, который COORD починил `83e8882`: ветка перевыдачи снята,
    # и роль снова получает «упёрся в лимит» + совет `--limit N`, БЕСПОЛЕЗНЫЙ до ack (любой
    # лимит вернёт тот же батч). Механика при этом честна — врёт ОДНА ветка подачи.
    # Заведён 2026-07-27 вместе с рефайнментом P9: расширяя тест, обязан доказать, что он
    # не расширен до всегда-зелёного. Свойство P9 краснеет по признаку `useless`.
    "M3-совет-бесполезен-в-перевыдаче": ([
        ('            if reissue:\n                print(f"⚠️  БАТЧ ПЕРЕВЫДАН (R16)',
         '            if False:\n                print(f"⚠️  БАТЧ ПЕРЕВЫДАН (R16)'),
    ], "P9"),
}


def selftest(target, sandbox):
    """Проверяем ЧУВСТВИТЕЛЬНОСТЬ укуса: на испорченном ридере он обязан краснеть,
    и краснеть ИМЕННО тем свойством, которое сломано."""
    src = target.read_text(encoding="utf-8")
    tmpdir = Path(tempfile.mkdtemp(prefix="bite-r16-mutants-"))
    dep = target.parent / "mezo_paths.py"
    if dep.exists():
        shutil.copy2(dep, tmpdir / "mezo_paths.py")
    all_ok = True
    for name, (edits, expect) in MUTANTS.items():
        print(f"\n{'='*72}\n[нарочная поломка {name}] ожидаем 🔴 по {expect}\n{'='*72}")
        mutated = src
        for needle, repl in edits:
            if needle not in mutated:
                die(f"мутант {name} не накладывается: якорь не найден в {target}",
                    "ридер изменился — мутанта надо перепривязать, иначе самопроверка лжёт",
                    f"якорь: {needle.strip()[:70]}")
            mutated = mutated.replace(needle, repl, 1)
        mpath = tmpdir / f"read-messages-{name}.py"
        mpath.write_text(mutated, encoding="utf-8")
        rc = verify(mpath, sandbox)
        got = getattr(verify, "last", {})
        good = rc != 0 and got.get(expect) is False
        all_ok &= good
        print(f"\n⇒ поломка {name}: rc={rc}, {expect}={'🔴' if got.get(expect) is False else '✅'} "
              f"— {'✅ приёмка ЧУВСТВИТЕЛЬНА' if good else '🔴 ПРИЁМКА СЛЕПА: порча не поймана'}")
    # ⚠️ число мутантов СЧИТАЕТСЯ, а не пишется словом: до 2026-07-27 здесь стояло «обе
    # известные порчи», и с приходом M3 строка стала врать в момент расширения самопроверки.
    print(f"\n{'='*72}\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if all_ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} "
          f"— приёмка {'ловит' if all_ok else 'НЕ ловит'} все {len(MUTANTS)} известные порчи "
          f"({', '.join(MUTANTS)})")
    return 0 if all_ok else 1


# ──────────────────────────────────────────────────────────────────────────────
def demo(baseline, target, sandbox):
    """ДЕМОНСТРАЦИЯ боли. Не тест: показывает «до» и «после» рядом.
    Предусловие «baseline действительно ДО» ПРОВЕРЯЕТСЯ — иначе rc=2."""
    tmp = workbench(sandbox)
    db = tmp / "mezosync.db"
    base = with_deps(baseline, tmp)
    cur, total, stale, head, unread = state(db, ROLE)
    if unread < 2:
        die(f"в песочнице нечего читать роли {ROLE} (непрочитанных {unread})")
    print(f"[демонстрация R16] baseline: {baseline}")
    print(f"   состояние {ROLE}: отметка {cur} · непрочитано {unread} · "
          f"открытых батчей {total} (протухших {stale})\n")

    (o1, t1), (o2, t2) = read_twice(base, db)
    require_readable(o1, "baseline")
    if t1 == t2:
        die("указанный baseline УЖЕ несёт R16 — это не «до»-версия",
            f"два вызова дали один токен {t1[0]}-{t1[1]}",
            "возьми версию ДО врезки, напр.: git show <коммит-до>:scripts/read-messages.py",
            "или гоняй регрессию вместо демонстрации: bite-r16.py verify")

    print("── ДО (baseline): два вызова подряд")
    print(f"   вызов 1 → {t1[0]}-{t1[1]}")
    print(f"   вызов 2 → {t2[0]}-{t2[1]}   (ДРУГОЙ — прежний батч обесценен)")
    rc, out = run(base, ["--db", str(db), "--role", ROLE, "--ack", f"{t1[0]}-{t2[1]}"])
    print(f"   ack СКЛЕЙКОЙ из разных вызовов → rc={rc}: {out.strip().splitlines()[0]}")
    print("   ⇒ роль всё делала аккуратно; половинки просто пришли из разных выводов.\n")

    tmp2 = workbench(sandbox)
    db2, tgt = tmp2 / "mezosync.db", with_deps(target, tmp2)
    (p1, c1), (p2, c2) = read_twice(tgt, db2)
    require_readable(p1, "target")
    print("── ПОСЛЕ (целевой ридер): два вызова подряд")
    print(f"   вызов 1 → {c1[0]}-{c1[1]}")
    print(f"   вызов 2 → {c2[0]}-{c2[1]}   {'(ТОТ ЖЕ ✅)' if c1 == c2 else '(другой 🔴)'}")
    print("\n📌 Это ДЕМОНСТРАЦИЯ, а не приёмка. Приёмка — `bite-r16.py verify`.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="verify",
                    choices=["verify", "demo", "selftest"])
    ap.add_argument("--sandbox", default=str(Path.home() / ".mezosync-sandbox"))
    ap.add_argument("--target", default=None,
                    help="проверяемый ридер (по умолчанию — копия живого в песочнице)")
    ap.add_argument("--baseline", default=None, help="ДО-версия ридера (только для demo)")
    a = ap.parse_args()

    sandbox = Path(a.sandbox).resolve()
    target = Path(a.target).resolve() if a.target else sandbox / "scripts" / "read-messages.py"
    if not target.exists():
        die(f"нет целевого ридера: {target}")

    if a.mode == "verify":
        return verify(target, sandbox)
    if a.mode == "selftest":
        return selftest(target, sandbox)
    if not a.baseline:
        die("demo требует --baseline <ДО-версия read-messages.py>",
            "именно этого не хватало прежней версии укуса: baseline брался молча "
            "из песочницы и после врезки оказывался уже почищенным (COORD #2748)")
    bp = Path(a.baseline).resolve()
    if not bp.exists():
        die(f"нет baseline: {bp}")
    return demo(bp, target, sandbox)


if __name__ == "__main__":
    sys.exit(main() or 0)
