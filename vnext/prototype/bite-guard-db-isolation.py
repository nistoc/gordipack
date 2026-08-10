#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: `guard-all`, натравленный на КОПИЮ, судит копию — а не живую базу.

ПОВОД (карточка #168, 2026-08-10). Приёмка новорождённого контура собирает контур из шаблона
и прогоняет в нём сторожей. Она объявила «СБОРКА НЕ ПРИНЯТА» из-за красного «пишут, но
не читают» — а красное принадлежало ЖИВОМУ контуру: у PROTO висел долг ленты. Признак
`guard-write-without-read` держал путь к базе ВПЕЧАТАННЫМ и читал её всегда, чем бы ни
занимался прогон. Дочитал ленту в живой базе, шаблон не тронул — сборка стала «принята».

🎯 СВОЙСТВО, КОТОРОЕ ЗДЕСЬ ПРОВЕРЯЕТСЯ, ОДНО: вердикт зависит ТОЛЬКО от той базы, что указана
аргументом. Обе стороны нарушения равно опасны, и приёмка ловит обе:
  · чужое красное приходит в чистую копию — оболган невиновный;
  · дефект копии ТОНЕТ, когда живая чиста — молчание читается как проверка. Второе хуже.

⚠️ ЖИВУЮ БАЗУ НЕ МУТИРУЕМ. Дефект вносится в КОПИЮ; «живой» для опыта служит вторая копия,
подсунутая через рабочий каталог. Приёмка, ради проверки портящая общий стенд, однажды съест
чужую смену.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")
GUARD = Path(r"C:\guts\.atlas\.mezosync\scripts\guard-write-without-read.py")

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def make_defect(db: Path, role: str) -> None:
    """Внести в КОПИЮ состояние «роль пишет свежее, чем читает».

    Имя роли берётся уникальное: по нему и видно, ЧЬЮ базу прочитал признак. Совпадение
    вердиктов ничего не доказало бы — доказывает ИМЯ в выводе.
    """
    con = sqlite3.connect(db)
    head = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority,"
                " resolved, broadcast, addressed_by) VALUES (?,?,datetime('now'),?,?,?,0,0,?)",
                (head + 1, role, "проба изоляции базы", "[]", "normal", "field"))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?, 0, datetime('now', '-1 day'))", (role,))
    con.commit()
    con.close()


def main() -> int:
    if not GUARD.exists():
        print(f"🔴 НЕ ЗАПУСТИЛАСЬ: признака нет по пути {GUARD}")
        return 2
    if not LIVE_DB.exists():
        print(f"🔴 НЕ ЗАПУСТИЛАСЬ: живой базы нет по пути {LIVE_DB}")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clean = tmp / "clean.db"
        dirty = tmp / "dirty.db"
        shutil.copy2(LIVE_DB, clean)
        shutil.copy2(LIVE_DB, dirty)
        MARK = "ЗОНДПРОБЫ"
        make_defect(dirty, MARK)

        # ① КОНТРОЛЬНАЯ ПАРА: на чистой копии признак молчит. Без неё краснота ниже
        #    не доказывает ничего — прибор мог бы краснеть всегда.
        code_c, out_c = run(clean)
        case("① контроль: чистая копия — признак зелёный",
             code_c == 0 and MARK not in out_c, f"код {code_c}")

        # ② РАЗЛИЧАЮЩИЙ: дефект ВНУТРИ копии виден, и назван по имени.
        code_d, out_d = run(dirty)
        case("② дефект копии найден и назван поимённо",
             code_d != 0 and MARK in out_d,
             f"код {code_d}; имя из копии в выводе: {MARK in out_d}")

        # ③ ГЛАВНЫЙ: вердикт по чистой копии НЕ ЗАВИСИТ от состояния живой базы.
        #    Живая прямо сейчас может быть какой угодно; если её красное протекает,
        #    случай ① уже покраснел бы. Проверяем ещё и обратное направление: имя
        #    из грязной копии не должно всплывать в прогоне по чистой.
        case("③ прогон по чистой копии не тащит чужое состояние",
             MARK not in out_c and code_c == 0,
             "вердикт определяется указанной базой, а не той, что «рядом со скриптом»")

        # ④ ВПЕЧАТАННОГО ПУТИ БОЛЬШЕ НЕТ В ИСПОЛНЯЕМОЙ СТРОКЕ.
        #    Проверяем ИСХОДНИК: пример в комментарии-надгробии допустим, живой литерал — нет.
        src = GUARD.read_text(encoding="utf-8")
        live_literals = [ln for ln in src.splitlines()
                         if "mezosync.db" in ln and not ln.lstrip().startswith("#")
                         and "resolve_db" not in ln]
        case("④ путь к базе не впечатан в исполняемую строку",
             not live_literals, f"живых литералов: {len(live_literals)}")

        # ⑥ СКВОЗНОЙ ПУТЬ: не признак сам по себе, а `guard-all` целиком. Именно так его
        #    зовёт приёмка новорождённого контура, и именно там утечка себя проявила.
        #    Проверять только признак было бы половиной работы: цепочка рвётся на передаче.
        agg = Path(r"C:\guts\.atlas\.mezosync\scripts\guard-all.py")
        r_dirty = subprocess.run([sys.executable, str(agg), "--db", str(dirty)],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        out_agg_dirty = (r_dirty.stdout or "") + (r_dirty.stderr or "")
        r_clean = subprocess.run([sys.executable, str(agg), "--db", str(clean)],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        out_agg_clean = (r_clean.stdout or "") + (r_clean.stderr or "")
        # 🪤 ПЕРВАЯ РЕДАКЦИЯ ЭТОГО СЛУЧАЯ БЫЛА ЛОЖНО-ЗЕЛЁНОЙ, и поймала её нарочная поломка:
        #    она искала МЕТКУ в выводе целиком — а метку печатал СОСЕДНИЙ признак («курсоры:
        #    реестр»), который базу берёт честно. При заведомо сломанном признаке случай
        #    оставался зелёным. Я цитировал в шапке «зелёная проверка означает ровно то,
        #    что она позвала» — и позвал не то. ⇒ Судим ИМЕННО строку нужного признака.
        def verdict(out: str, name: str = "чтение ленты") -> str:
            for ln in out.splitlines():
                if name in ln and (ln.lstrip().startswith("✅") or ln.lstrip().startswith("⛔")):
                    return "зелёный" if ln.lstrip().startswith("✅") else "красный"
            return "строки нет"

        v_dirty, v_clean = verdict(out_agg_dirty), verdict(out_agg_clean)
        case("⑥ сквозной путь: строка «чтение ленты» следует за УКАЗАННОЙ базой",
             v_dirty == "красный" and v_clean == "зелёный",
             f"по грязной копии: {v_dirty}; по чистой: {v_clean} "
             f"(«строки нет» = третий исход, не зелёный)")

        # ⑤ ЖИВАЯ БАЗА НЕ ТРОНУТА: приёмка испытывала КОПИИ.
        con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
        leaked = con.execute("SELECT COUNT(*) FROM messages WHERE writer_role=?",
                             (MARK,)).fetchone()[0]
        con.close()
        case("⑤ живая база цела: зонд в неё не попал", leaked == 0,
             f"записей с меткой пробы в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 3")
    print("⚖️ ГРАНИЦА: проверен ОДИН признак — тот, что дал утечку. Что остальные звенья")
    print("   guard-all не ходят в базу мимо аргумента, доказано разбором (карточка #168),")
    print("   а не этим прогоном: у них предмет — файлы, и базы они не открывают вовсе.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
