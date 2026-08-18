#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: проверка «формы вызова из памяти ролей» ВИДИТ поломку, а не рапортует зелёным.

Повод — проба-канарейка 2026-08-09: `role-rights.py list --role <РОЛЬ>` падала у каждой роли,
а приёмка была зелёной, потому что звала форму БЕЗ имени роли. Прибор, который ловит такое,
сам обязан быть испытан ПОЛОМКОЙ: иначе он ровно та же зелёная бумажка, только больше.

Случаи (различающий = прибор обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: неиспорченная копия — прибор молчит (зелёный)
  ② у скрипта СЛОМАН РАЗБОР ПАРАМЕТРА → прибор краснеет            РАЗЛИЧАЮЩИЙ
     ровно дефект 09.08: без флага работает, с флагом падает
  ③ скрипт ИСЧЕЗ из каталога → прибор краснеет и говорит «файла нет» РАЗЛИЧАЮЩИЙ
  ④ прибор идёт по УКАЗАННОМУ каталогу, а не по живому                РАЗЛИЧАЮЩИЙ
     без этого зелёный прогон доказывал бы исправность ОРИГИНАЛА, а не копии
  ⑤ упоминание в пояснении НЕ считается командой                      РАЗЛИЧАЮЩИЙ
     у ING в памяти лежит `.mezosync\\scripts\\x.py` — пример опасной формы, а не вызов
  ⑥ мутирующая форма НЕ запускается на живой базе (--ack не гасит ключ) РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: работает на копии каталога скриптов и копии базы.
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

TOOL = Path(__file__).resolve().parent / "guard-launcher-forms.py"
LIVE_SCRIPTS = mezo_target.scripts_root()
LIVE_DB = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def sandbox():
    """Копия каталога скриптов + копия базы, где память переписана на этот каталог."""
    d = Path(tempfile.mkdtemp(prefix="bite-forms-"))
    scripts = d / "scripts"
    shutil.copytree(LIVE_SCRIPTS, scripts)
    db = d / "copy.db"
    shutil.copy(LIVE_DB, db)
    return d, scripts, db


def run(scripts, db, *extra):
    r = subprocess.run([sys.executable, str(TOOL), "--scripts-root", str(scripts),
                        "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", timeout=600)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    ok = True
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {TOOL}")

    # ── ① контроль ────────────────────────────────────────────────────────────
    d, scripts, db = sandbox()
    out, code = run(scripts, db, "--only", "role-rights")
    ok &= case("① контроль: неиспорченная копия — прибор зелёный",
               code == 0 and "🔴 ПАДАЮТ ИЛИ НЕТ ФАЙЛА 0" in out,
               f"код {code} · без этого краснота дальше ничего не доказывает")

    # ── ② сломан разбор параметра (дефект 09.08 дословно) ─────────────────────
    d2, scripts2, db2 = sandbox()
    target = scripts2 / "role-rights.py"
    src = target.read_text(encoding="utf-8")
    broken = src.replace('sql + " ORDER BY role, right_key", par',
                         'sql + " ORDER BY role, right_key"')
    if broken == src:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: место для поломки не найдено — инструмент менялся, правь приёмку")
    target.write_text(broken, encoding="utf-8")
    out, code = run(scripts2, db2, "--only", "role-rights")
    ok &= case("② сломан разбор параметра — прибор КРАСНЕЕТ",
               code != 0 and "ПАДАЕТ" in out,
               "форма без флага работает, с флагом падает: ровно то, что прожило незамеченным",
               differ=True)

    # ── ③ скрипт исчез ────────────────────────────────────────────────────────
    d3, scripts3, db3 = sandbox()
    (scripts3 / "read-phoenix.py").unlink()
    out, code = run(scripts3, db3, "--only", "read-phoenix")
    ok &= case("③ скрипт ИСЧЕЗ — прибор краснеет и называет это «файла нет»",
               code != 0 and ("ФАЙЛА НЕТ" in out or "НЕТ ПО НАЗВАННОМУ" in out),
               "роль получила бы «can't open file» в первую же секунду жизни", differ=True)

    # ── ④ прибор идёт по УКАЗАННОМУ каталогу, а не по живому ──────────────────
    # живой role-rights.py исправен; в копии он сломан. Если бы прибор ходил по пути
    # из памяти (абсолютному), он остался бы зелёным — и доказывал бы исправность ОРИГИНАЛА
    ok &= case("④ испытан УКАЗАННЫЙ каталог, а не живой",
               code != 0,
               "живой каталог цел; краснота пришла из копии ⇒ прибор смотрел именно на копию",
               differ=True)

    # ── ⑤ упоминание ≠ команда ────────────────────────────────────────────────
    out, code = run(scripts, db, "--only", "x.py")
    ok &= case("⑤ пример в пояснении НЕ считается командой",
               code == 0 and "🔴 ПАДАЮТ ИЛИ НЕТ ФАЙЛА 0" in out,
               "у ING это строка про ОПАСНОСТЬ относительного пути — прибор обвинял её зря",
               differ=True)

    # ── ⑥ мутирующая форма не запускается ─────────────────────────────────────
    # ⚠️ Память СЕГОДНЯ может не содержать ни одной такой формы (у RCC она записана прозой,
    # а не командой). Случай, зависящий от чужого текста, зеленел бы «по отсутствию предмета»,
    # поэтому предмет кладём в копию памяти САМИ.
    d6, scripts6, db6 = sandbox()
    con = sqlite3.connect(db6)
    con.execute("UPDATE phoenix SET body = body || ? WHERE role='PROTO' AND section='sources'",
                ("\n```\npython " + str(LIVE_SCRIPTS).replace("\\", "/")
                 + "/read-messages.py --role PROTO --ack КЛЮЧ\n```\n",))
    con.commit()
    con.close()
    out, code = run(scripts6, db6, "--only", "read-messages")
    ok &= case("⑥ форма с гашением ключа НЕ запущена, и сказано почему",
               "гасит ОДНОРАЗОВЫЙ ключ" in out,
               "запуск съел бы у роли её батч — молчаливый пропуск скрыл бы это", differ=True)

    # ── ⑦ СПЛОШНАЯ ПОЛОМКА: КАЖДЫЙ механизм по очереди ────────────────────────
    # Критерий карточки #147 дословно: «сломать разбор параметра у каждой такой команды
    # по очереди, прогон обязан покраснеть на каждой». Одна поломка на одном скрипте
    # доказывает, что прибор видит ЭТОТ скрипт, а не что он видит вообще.
    # Ломаем ОБЪЯВЛЕНИЕ флага: механизм перестаёт знать «--role», и вызов из памяти
    # отвечает «unrecognized arguments» — без падения. Прибор обязан счесть это отказом.
    print()
    print("⑦ СПЛОШНАЯ ПОЛОМКА — по одному механизму за раз:")
    d7, scripts7, db7 = sandbox()
    # ⚠️ Цель — скрипты, ОБЪЯВЛЯЮЩИЕ --role своим флагом, а не любое упоминание строки:
    # 13.08 guard-all получил "--role" как аргумент ПОДПРОЦЕССА (замер памяти зовёт
    # проверка памяти по ролям), и отбор по упоминанию записал его в цели. Поломка упоминания
    # контракта guard-all не рушит (его зовут без аргументов) — приёмка объявила прибор
    # «слепым» на поломке, которую роль не может встретить. Это случай ⑤ («упоминание ≠
    # команда») в самой приёмке — тем же классом, которым она судит других.
    targets = sorted({p.name for p in scripts7.glob("*.py")
                      if 'add_argument("--role"' in p.read_text(encoding="utf-8", errors="ignore")})
    blind, seen = [], 0
    for name in targets:
        d_i, scripts_i, db_i = sandbox()
        f = scripts_i / name
        src = f.read_text(encoding="utf-8")
        f.write_text(src.replace('"--role"', '"--rolezz"'), encoding="utf-8")
        out_i, code_i = run(scripts_i, db_i, "--only", name.replace(".py", ""))
        # прибор мог вовсе не проверять этот механизм (нет форм) — это НЕ «увидел»
        checked = "отвечают 0 · 🔴 ПАДАЮТ ИЛИ НЕТ ФАЙЛА 0 · ⚠️ не проверены 0" not in out_i
        caught = code_i != 0
        if checked:
            seen += 1
            mark = "✅ увидел" if caught else "🔴 СЛЕП"
            if not caught:
                blind.append(name)
        else:
            mark = "⚪ форм этого механизма в памяти нет — ломать нечего"
        print(f"   {mark:52} {name}")
    ok &= case(f"⑦ сплошная поломка: прибор увидел все {seen} проверяемых механизмов",
               not blind and seen > 0,
               f"механизмов с формами в памяти {seen} из {len(targets)} · "
               f"слепых {len(blind)}{': ' + ', '.join(blind) if blind else ''}", differ=True)

    print()
    print(f"{'✅ ПРОВЕРКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
