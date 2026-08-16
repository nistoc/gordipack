#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-tool-lease — приёмка объявленной аренды инструмента (карточка #204).

    python C:/guts/.atlas/vnext-tools/bite-tool-lease.py

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: аренд нет — ничего не изменилось, инструменты работают молча
  ② чужая аренда, ПИШУЩИЙ инструмент → ОТКАЗ, и в отказе имя, причина, чем спросить  РАЗЛИЧАЮЩИЙ
  ③ чужая аренда, ЧИТАЮЩИЙ инструмент → предупреждение, но РАБОТА ИДЁТ               РАЗЛИЧАЮЩИЙ
  ④ СВОЯ аренда → не мешает вовсе: иначе арендатор не смог бы отлаживать своё        РАЗЛИЧАЮЩИЙ
  ⑤ ИСТЁКШАЯ аренда → не мешает никому, забытая не держит контур                     РАЗЛИЧАЮЩИЙ
  ⑥ снятая аренда → не мешает; чужую снять НЕЛЬЗЯ                                    РАЗЛИЧАЮЩИЙ
  ⑦ аренда без причины / на сутки → ОТКАЗ при взятии                                 РАЗЛИЧАЮЩИЙ
  ⑧ аренда закрывает ПАЙПЛАЙН: одна запись — несколько имён                          РАЗЛИЧАЮЩИЙ
  ⑨ установка новой версии НЕДЕЛИМА и между томами ОТКАЗЫВАЕТ                        РАЗЛИЧАЮЩИЙ

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


def run(argv, role=None, cwd=None):
    env = dict(os.environ)
    env.pop("MEZO_LEASE_BYPASS", None)
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
    body = d / "b.md"
    body.write_text("тело пробы аренды\n" + "x" * 400, encoding="utf-8")
    ok = True

    def write_try(role):
        return run([SAVE, "--db", str(db), "--role", "PROTO", "--section", "state",
                    "--file", str(body), "--allow-shrink"], role=role)

    def read_try(role):
        return run([READ, "--db", str(db), "--role", "PROTO", "--section", "state"], role=role)

    # ── ① КОНТРОЛЬ: аренд нет ────────────────────────────────────────────────
    out_w, code_w = write_try("CORE")
    out_r, code_r = read_try("CORE")
    ok &= case("① контроль: аренд нет — оба инструмента работают и молчат об аренде",
               code_w == 0 and code_r == 0 and "В РАБОТЕ у роли" not in out_w + out_r,
               f"пишущий код {code_w}, читающий код {code_r} — без этого случая любая "
               f"краснота ниже ничего не доказывает")

    # ── ② ЧУЖАЯ АРЕНДА, ПИШУЩИЙ ──────────────────────────────────────────────
    out, code = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                     "--tools", "save-phoenix.py read-phoenix.py",
                     "--reason", "проба приёмки аренды", "--minutes", "30"])
    lease_id = "".join(c for c in out.split("АРЕНДА #")[1].split()[0] if c.isdigit())
    out_w, code_w = write_try("CORE")
    ok &= case("② чужая аренда + ПИШУЩИЙ → отказ с именем, причиной и командой «спросить»",
               code_w == 3 and "PROTO" in out_w and "проба приёмки аренды" in out_w
               and "lease.py status" in out_w,
               f"код {code_w}; в отказе есть арендатор, причина и чем спросить — иначе "
               f"«занято» это тупик, а не сообщение", differ=True)

    # ── ③ ЧУЖАЯ АРЕНДА, ЧИТАЮЩИЙ ─────────────────────────────────────────────
    out_r, code_r = read_try("CORE")
    ok &= case("③ чужая аренда + ЧИТАЮЩИЙ → предупреждение, но работа ИДЁТ",
               code_r == 0 and "В РАБОТЕ у роли" in out_r and "ЧИТАЮЩИЙ" in out_r,
               f"код {code_r} — отняв чтение, мы отняли бы у роли способ узнать о работах",
               differ=True)

    # ── ④ СВОЯ АРЕНДА ────────────────────────────────────────────────────────
    out_w, code_w = write_try("PROTO")
    ok &= case("④ СВОЯ аренда не мешает арендатору",
               code_w == 0,
               f"код {code_w} — иначе арендатор не смог бы отлаживать то, что арендовал, "
               f"и аренда стала бы бессмысленной", differ=True)

    # ── ⑤ ИСТЁКШАЯ АРЕНДА ────────────────────────────────────────────────────
    con = sqlite3.connect(db)
    con.execute("UPDATE tool_leases SET until_utc = datetime('now', '-1 minute') WHERE id=?",
                (lease_id,))
    con.commit()
    con.close()
    out_w, code_w = write_try("CORE")
    ok &= case("⑤ ИСТЁКШАЯ аренда не держит контур (гаснет сама)",
               code_w == 0 and "В РАБОТЕ у роли" not in out_w,
               f"код {code_w} — забытая аренда не имеет права остановить работу: вечный "
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
    ok &= case("⑥ чужую аренду снять НЕЛЬЗЯ, свою — можно, после снятия свободно",
               code_a != 0 and "ОТКАЗ" in out_a and code_b == 0 and code_w == 0,
               f"чужое снятие код {code_a}, своё {code_b}, работа после {code_w}", differ=True)

    # ── ⑦ АРЕНДА БЕЗ ПРИЧИНЫ И НА СУТКИ — ОТКАЗ ──────────────────────────────
    out_n, code_n = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                         "--tools", "backlog.py", "--minutes", "30"])
    out_l, code_l = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                         "--tools", "backlog.py", "--reason", "долгая работа",
                         "--minutes", "1440"])
    ok &= case("⑦ без причины и на сутки — ОТКАЗ при взятии",
               code_n != 0 and code_l != 0 and "1–480" in out_l,
               "аренда без причины неоспорима, аренда на сутки — это запрет, а запрет обходят",
               differ=True)

    # ── ⑧ ПАЙПЛАЙН ОДНОЙ АРЕНДОЙ ─────────────────────────────────────────────
    out, _ = run([LEASE, "take", "--db", str(db), "--role", "PROTO",
                  "--tools", "save-phoenix.py read-phoenix.py backlog.py",
                  "--reason", "связанная тройка правится вместе", "--minutes", "10"])
    pid = "".join(c for c in out.split("АРЕНДА #")[1].split()[0] if c.isdigit())
    o1, c1 = write_try("CORE")
    # ⚠️ --db у этого инструмента объявлен в ОБЩЕМ разборщике и потому идёт ДО подкоманды.
    # Первый заход приёмки дал код 2 (ошибка разбора) и был принят за отказ аренды —
    # ровно тот класс, который приёмки и ловят: неверная форма вызова маскируется
    # под срабатывание механизма.
    o2, c2 = run([str(scripts / "backlog.py"), "--db", str(db), "list", "--role", "PROTO"],
                 role="CORE")
    ok &= case("⑧ одна аренда закрывает ПАЙПЛАЙН из нескольких имён",
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

    shutil.rmtree(d, ignore_errors=True)
    print()
    if ok:
        print(f"✅ АРЕНДА ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
