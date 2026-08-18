#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-tool-lease — приёмка объявления о правке инструмента (карточка #204).

    python C:/guts/.atlas/vnext-tools/bite-tool-lease.py

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: объявлений нет — ничего не изменилось, инструменты работают молча
  ② чужое объявление, ПИШУЩИЙ инструмент → ОТКАЗ, и в отказе имя, причина, чем спросить  РАЗЛИЧАЮЩИЙ
  ③ чужое объявление, ЧИТАЮЩИЙ инструмент → предупреждение, но РАБОТА ИДЁТ               РАЗЛИЧАЮЩИЙ
  ④ СВОЁ объявление → не мешает вовсе: иначе правящая роль не смогла бы отлаживать своё        РАЗЛИЧАЮЩИЙ
  ⑤ ПРОСРОЧЕННОЕ объявление → не мешает никому, забытое не держит контур                     РАЗЛИЧАЮЩИЙ
  ⑥ снятое объявление → не мешает; чужое снять НЕЛЬЗЯ                                    РАЗЛИЧАЮЩИЙ
  ⑦ объявление без причины / на сутки → ОТКАЗ при взятии                                 РАЗЛИЧАЮЩИЙ
  ⑧ объявление закрывает СВЯЗАННУЮ ГРУППУ: одна запись — несколько имён                          РАЗЛИЧАЮЩИЙ
  ⑨ установка новой версии НЕДЕЛИМА и между томами ОТКАЗЫВАЕТ                        РАЗЛИЧАЮЩИЙ
  ⑩ объявление на САМ инструмент объявлений снимается (не запирает себя)          РАЗЛИЧАЮЩИЙ
  ⑪ объявление живого контура НЕ мешает работе на КОПИИ базы (приёмкам)          РАЗЛИЧАЮЩИЙ

⛔ Живого контура НЕ касается: копия базы и копия каталога инструментов во временном месте.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

LIVE_DB = mezo_paths.live_db()
LIVE_SCRIPTS = mezo_paths.live_scripts()
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def run(argv, role=None, cwd=None, testmode=True):
    env = dict(os.environ)
    env.pop("MEZO_LEASE_BYPASS", None)
    # Приёмка работает на КОПИИ базы, а объявления действуют в живом контуре — без этой
    # договорённости испытывать механизм было бы не на чем. testmode=False нужен случаю ⑪,
    # который проверяет ровно обратное: что на копии объявление молчит.
    if testmode:
        env["MEZO_LEASE_TEST"] = "1"
    else:
        env.pop("MEZO_LEASE_TEST", None)
    if role:
        env["MEZO_ROLE"] = role
    else:
        env.pop("MEZO_ROLE", None)
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                       encoding="utf-8", timeout=120, env=env, cwd=cwd)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="bite-lease-"))
    scripts = d / "scripts"
    shutil.copytree(LIVE_SCRIPTS, scripts)
    db = d / "copy.db"
    shutil.copyfile(LIVE_DB, db)
    LEASE = str(scripts / "lease.py")
    SAVE = str(scripts / "save-phoenix.py")          # пишущий
    READ = str(scripts / "read-phoenix.py")          # читающий
    # 🪤 ИЗОЛЯЦИЯ ОТ ЖИВЫХ ОБЪЯВЛЕНИЙ — найдено живым применением 17.08: копия базы приносит
    # объявления, действующие ПРЯМО СЕЙЧАС, и приёмка начинает зависеть от того, правит ли
    # кто-то что-то в эту минуту. Мой собственный случай «объявлений нет» падал не из-за
    # дефекта механизма, а из-за моей же работы в соседнем окне. ⇒ копия с чистого листа.
    _c = sqlite3.connect(db)
    _c.execute("DELETE FROM tool_leases")
    _c.commit()
    _c.close()
    body = d / "b.md"
    body.write_text("тело пробы объявления\n" + "x" * 400, encoding="utf-8")
    ok = True

    def write_try(role):
        return run([SAVE, "--db", str(db), "--role", "PROTO", "--section", "state",
                    "--file", str(body), "--allow-shrink"], role=role)

    def read_try(role):
        return run([READ, "--db", str(db), "--role", "PROTO", "--section", "state"], role=role)

    # ── ① КОНТРОЛЬ: объявлений нет ────────────────────────────────────────────────
    out_w, code_w = write_try("CORE")
    out_r, code_r = read_try("CORE")
    ok &= case("① контроль: объявлений нет — оба инструмента работают и молчат об объявлении",
               code_w == 0 and code_r == 0 and "В РАБОТЕ у роли" not in out_w + out_r,
               f"пишущий код {code_w}, читающий код {code_r} — без этого случая любая "
               f"краснота ниже ничего не доказывает")

    # ── ② ЧУЖОЕ ОБЪЯВЛЕНИЕ, ПИШУЩИЙ ──────────────────────────────────────────────
    out, code = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                     "--tools", "save-phoenix.py read-phoenix.py",
                     "--reason", "проба приёмки объявления", "--minutes", "30"])
    lease_id = "".join(c for c in out.split("ОБЪЯВЛЕНО #")[1].split()[0] if c.isdigit())
    out_w, code_w = write_try("CORE")
    ok &= case("② чужое объявление + ПИШУЩИЙ → отказ с именем, причиной и командой «спросить»",
               code_w == 3 and "PROTO" in out_w and "проба приёмки объявления" in out_w
               and "lease.py status" in out_w and "MEZO_ROLE=PROTO" in out_w,
               f"код {code_w}; в отказе есть правящая роль, причина, чем спросить И как "
               f"назваться, если объявление своё (17.08 механизм отказал собственному "
               f"автору: роль не названа в окружении) — иначе это тупик, а не сообщение",
               differ=True)

    # ── ③ ЧУЖОЕ ОБЪЯВЛЕНИЕ, ЧИТАЮЩИЙ ─────────────────────────────────────────────
    out_r, code_r = read_try("CORE")
    ok &= case("③ чужое объявление + ЧИТАЮЩИЙ → предупреждение, но работа ИДЁТ",
               code_r == 0 and "В РАБОТЕ у роли" in out_r and "ЧИТАЮЩИЙ" in out_r,
               f"код {code_r} — отняв чтение, мы отняли бы у роли способ узнать о работах",
               differ=True)

    # ── ④ СВОЁ ОБЪЯВЛЕНИЕ ────────────────────────────────────────────────────────
    out_w, code_w = write_try("PROTO")
    ok &= case("④ СВОЁ объявление не мешает правящей роли",
               code_w == 0,
               f"код {code_w} — иначе правящая роль не смогла бы отлаживать то, о чём объявила, "
               f"и механизм стал бы бессмысленным", differ=True)

    # ── ⑤ ПРОСРОЧЕННОЕ ОБЪЯВЛЕНИЕ ────────────────────────────────────────────────────
    con = sqlite3.connect(db)
    con.execute("UPDATE tool_leases SET until_utc = datetime('now', '-1 minute') WHERE id=?",
                (lease_id,))
    con.commit()
    con.close()
    out_w, code_w = write_try("CORE")
    ok &= case("⑤ ПРОСРОЧЕННОЕ объявление не держит контур (гаснет само)",
               code_w == 0 and "В РАБОТЕ у роли" not in out_w,
               f"код {code_w} — забытое объявление не имеет права остановить работу: вечный "
               f"запрет учит обходить запреты", differ=True)

    # ── ⑥ СНЯТИЕ: чужую нельзя, свою можно ───────────────────────────────────
    con = sqlite3.connect(db)
    con.execute("UPDATE tool_leases SET until_utc = datetime('now', '+30 minutes') WHERE id=?",
                (lease_id,))
    con.commit()
    con.close()
    out_a, code_a = run([LEASE, "release", "--db", str(db), "--role", "CORE", "--id", lease_id])
    out_b, code_b = run([LEASE, "release", "--db", str(db), "--role", "PROTO", "--id", lease_id,
                         "--note", "проба снята"])
    out_w, code_w = write_try("CORE")
    ok &= case("⑥ чужое объявление снять НЕЛЬЗЯ, своё — можно, после снятия свободно",
               code_a != 0 and "ОТКАЗ" in out_a and code_b == 0 and code_w == 0,
               f"чужое снятие код {code_a}, своё {code_b}, работа после {code_w}", differ=True)

    # ── ⑦ ОБЪЯВЛЕНИЕ БЕЗ ПРИЧИНЫ И НА СУТКИ — ОТКАЗ ──────────────────────────────
    out_n, code_n = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                         "--tools", "backlog.py", "--minutes", "30"])
    out_l, code_l = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                         "--tools", "backlog.py", "--reason", "долгая работа",
                         "--minutes", "1440"])
    ok &= case("⑦ без причины и на сутки — ОТКАЗ при взятии",
               code_n != 0 and code_l != 0 and "1–480" in out_l,
               "объявление без причины неоспоримо, объявление на сутки — это запрет, а запрет обходят",
               differ=True)

    # ── ⑧ СВЯЗАННЫЕ ОДНИМ ОБЪЯВЛЕНИЕМ ─────────────────────────────────────────────
    out, _ = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                  "--tools", "save-phoenix.py read-phoenix.py backlog.py",
                  "--reason", "связанная тройка правится вместе", "--minutes", "10"])
    pid = "".join(c for c in out.split("ОБЪЯВЛЕНО #")[1].split()[0] if c.isdigit())
    o1, c1 = write_try("CORE")
    # ⚠️ --db у этого инструмента объявлен в ОБЩЕМ разборщике и потому идёт ДО подкоманды.
    # Первый заход приёмки дал код 2 (ошибка разбора) и был принят за отказ по объявлению —
    # ровно тот класс, который приёмки и ловят: неверная форма вызова маскируется
    # под срабатывание механизма.
    o2, c2 = run([str(scripts / "backlog.py"), "--db", str(db), "list", "--role", "PROTO"],
                 role="CORE")
    ok &= case("⑧ одно объявление закрывает связанную группу из нескольких имён",
               c1 == 3 and c2 == 3,
               f"оба инструмента тройки отказали ({c1}, {c2}) — объявлять связанные порознь "
               f"значило бы дать зовущему половину правды", differ=True)
    run([LEASE, "release", "--db", str(db), "--role", "PROTO", "--id", pid])

    # ── ⑨ УСТАНОВКА НЕДЕЛИМА ─────────────────────────────────────────────────
    INSTALL = str(scripts / "atomic-install.py")
    target = d / "target.py"
    target.write_text("# старая версия\n" + "o" * 200, encoding="utf-8")
    newer = d / "newer.py"
    newer.write_text("# НОВАЯ версия\n" + "n" * 300, encoding="utf-8")
    out_i, code_i = run([INSTALL, str(newer), str(target)])
    installed = target.read_text(encoding="utf-8")
    bak_ok = (d / "target.py.bak").exists()
    empty = d / "empty.py"
    empty.write_text("   \n", encoding="utf-8")
    out_e, code_e = run([INSTALL, str(empty), str(target)])
    ok &= case("⑨ установка одним ходом: новая версия целиком, откат рядом, пустая — отказ",
               code_i == 0 and installed.startswith("# НОВАЯ") and bak_ok
               and code_e != 0 and "ПУСТ" in out_e,
               f"установка код {code_i}, копия для отката {'есть' if bak_ok else 'НЕТ'}, "
               f"пустая версия код {code_e} — половины файла не существует по построению",
               differ=True)

    # ── ⑩ МЕХАНИЗМ НЕ ЗАПИРАЕТ САМ СЕБЯ ──────────────────────────────────────
    # 🪤 Найдено ЖИВЫМ ПРИМЕНЕНИЕМ 17.08: я объявил правку самого lease.py — и снять это
    # объявление стало нечем: команда снятия отказывала сама себе, объявление становилось
    # необратимым до истечения срока. Случай различающий: без исключения тут был бы код 3.
    out_s, code_s = run([LEASE, "take", "--db", str(db), "--role", "CORE",
                         "--tools", "lease.py save-phoenix.py",
                         "--reason", "правится сам инструмент объявлений", "--minutes", "20"])
    sid = "".join(c for c in out_s.split("ОБЪЯВЛЕНО #")[1].split()[0] if c.isdigit())
    _, code_st = run([LEASE, "status", "--db", str(db)])                 # роль не названа вовсе
    out_rel, code_rel = run([LEASE, "release", "--db", str(db), "--role", "CORE", "--id", sid])
    out_w, code_w = write_try("PROTO")     # соседний инструмент той же записи — закрыт был честно
    ok &= case("⑩ объявление на сам инструмент объявлений снимается: механизм не запирает себя",
               code_st == 0 and code_rel == 0 and code_w == 0,
               f"спросить {code_st}, снять {code_rel}, работа после снятия {code_w} — "
               f"единственный выход не имеет права закрываться изнутри", differ=True)

    # ── ⑪ ЖИВОЕ ОБЪЯВЛЕНИЕ НЕ КРАСИТ ПЕСОЧНИЦУ ────────────────────────────────
    # 🪤 Найдено ЖИВЫМ ПРИМЕНЕНИЕМ 17.08: пока я держал объявление на 13 инструментах,
    # ШЕСТЬ приёмок контура покраснели — каждая копирует живую базу, и объявление ехало
    # в копию. Механизм наказывал за собственное правильное применение.
    run([LEASE, "take", "--db", str(db), "--role", "CORE", "--tools", "save-phoenix.py",
         "--reason", "правка в живом контуре, пока идут приёмки", "--minutes", "30"])
    out_sb, code_sb = run([SAVE, "--db", str(db), "--role", "PROTO", "--section", "state",
                           "--file", str(body), "--allow-shrink"], role="STUD", testmode=False)
    ok &= case("⑪ объявление живого контура НЕ мешает работе на КОПИИ базы",
               code_sb == 0 and "В РАБОТЕ у роли" not in out_sb,
               f"код {code_sb} — иначе одна честная правка красит все приёмки контура, "
               f"и механизм обходят первым же, кому он помешал", differ=True)

    shutil.rmtree(d, ignore_errors=True)
    print()
    if ok:
        print(f"✅ ОБЪЯВЛЕНИЕ О ПРАВКЕ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
