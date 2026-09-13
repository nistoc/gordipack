# -*- coding: utf-8 -*-
r"""bite-gordi-issue.py — приёмка гейта писателя канала «process → issues» (gordi-issue.py).

🩸 ПОВОД (найдено контуром AIA, подтверждено в нашем коде, 2026-09-13): `_writer_gate`
принимал ТОЛЬКО литерал «COORD» — координатор контура был константой кода, а не фактом
контура. Смени владелец координатора словом (как уже переходили зоны CHROME/OPSSRE/PROTO
по `migrations/roster.json`), литерал остался бы верен вчера и молча ошибался бы сегодня:
отказывал бы НАСТОЯЩЕМУ координатору и пропускал бы самозванца с именем «COORD», если оно
освободится. Правка: координатор ищется в данных контура (`roles.lifecycle_reason`),
литерал «COORD» остаётся ТОЛЬКО запасным путём — и печатает, откуда взять верное.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① координатор из данных пишет — гейт пропускает                              контроль
  ② НЕ координатор (по данным) отказан, отказ НАЗЫВАЕТ настоящего координатора  РАЗЛИЧАЮЩИЙ
  ③ данные не называют РОВНО ОДНУ роль-координатора → запасной литерал «COORD»,
     печатается ПРЕДУПРЕЖДЕНИЕ, откуда брать верное                            РАЗЛИЧАЮЩИЙ
  ④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор в данных — ДРУГАЯ роль (не «COORD») → эта
     роль пишет, а буквальный «COORD» — уже НЕТ (доказывает, что источник данных
     ДЕЙСТВУЕТ, а не разбор данных ради проформы поверх старого литерала)          РАЗЛИЧАЮЩИЙ

НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-literal): _writer_gate возвращён к литералу «COORD» —
ждём красным РОВНО ④ (роль-координатор из данных «TAXO» перестаёт писать, а «COORD» —
роль, переставшая быть координатором — снова пишет); ① ② ③ целы, потому что в них
координатор данных СОВПАДАЕТ с «COORD» и литерал их не различает.

⛔ Живой базы не касается: работает на КОПИИ (backup API) в своём временном контейнере
(структура `<конт>/.mezosync/mezosync.db`, опознаётся `MEZO_CONTAINER`). Сеть (`gh`) не
зовётся — все прогоны с `--dry-run`.
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

CASES = DIFFER = PASSED = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, PASSED
    CASES += 1
    DIFFER += bool(differ)
    PASSED += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


BODY = "## ЗАМЕР\nтест\n## КЛАСС\nтест\n## ПРЕДЛОЖЕНИЕ\nтест\n"


def call_tool(tool: Path, container: Path, *args):
    r = subprocess.run(
        [sys.executable, "-B", str(tool), "create", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "MEZO_CONTAINER": str(container)})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["revert-to-literal"],
                    help="нарочная поломка: вернуть проверку писателя к литералу «COORD»")
    a = ap.parse_args()

    live_tool = Path(__file__).resolve().parent.parent / ".mezosync" / "scripts" / "gordi-issue.py"
    if not live_tool.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: gordi-issue.py нет: {live_tool}")

    stand = Path(tempfile.mkdtemp(prefix="bite-gordi-issue-"))
    try:
        container = stand / "container"
        (container / ".mezosync" / "scripts").mkdir(parents=True, exist_ok=True)
        db = container / ".mezosync" / "mezosync.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        # копия скриптов рядом — gordi-issue.py лениво импортирует mezo_paths из своего
        # каталога через sys.path.insert(parent); кладём инструмент и mezo_paths РЯДОМ
        scripts_dir = stand
        tool = scripts_dir / "gordi-issue.py"
        shutil.copy2(live_tool, tool)
        shutil.copy2(mezo_paths.__file__, scripts_dir / "mezo_paths.py")

        body_file = stand / "issue.md"
        body_file.write_text(BODY, encoding="utf-8")

        if a.porcha == "revert-to-literal":
            # 🎯 Порча делает поиск в данных ВСЕГДА пустым — функционально РОВНО то же,
            # что откат к литералу «COORD»: запасной путь срабатывает на КАЖДОМ вызове.
            # ①②③ целы: в них искомый ответ и так «COORD» (запасной путь его и даёт).
            # ④ единственный, где данные называют ДРУГУЮ роль (TAXO) — вот он и краснеет.
            text = tool.read_text(encoding="utf-8")
            old = "AND lifecycle_reason LIKE '%координатор%'"
            new = "AND lifecycle_reason LIKE '%никогда-не-совпадёт-xyz%'"
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-literal»: поиск координатора в данных "
                  "никогда не находит совпадения — равносильно откату на литерал «COORD» "
                  "на КАЖДОМ вызове. Ждём красным РОВНО ④; ①②③ целы (искомый ответ там и "
                  "так «COORD», запасной путь его и даёт)\n")

        # ① координатор из данных (сейчас — COORD) пишет
        code1, out1 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("① координатор из данных (COORD) пишет — проверка писателя пропускает (контроль)",
             code1 == 0 and "⟨ВХОЛОСТУЮ⟩" in out1,
             f"код {code1}")

        # ② НЕ координатор отказан, отказ называет НАСТОЯЩЕГО координатора
        code2, out2 = call_tool(tool, container, "--role", "PROTO", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("② не координатор отказан, отказ НАЗЫВАЕТ настоящего координатора",
             code2 != 0 and "координатор COORD" in out2,
             f"код {code2} · координатор назван: {'да' if 'координатор COORD' in out2 else 'НЕТ'}",
             differ=True)

        # ③ данные не называют РОВНО ОДНУ роль → запасной литерал + предупреждение
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='в живом реестре' WHERE role='COORD'")
        con.commit()
        con.close()
        code3, out3 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("③ данные не называют РОВНО ОДНУ роль-координатора → запасной литерал, "
             "предупреждение печатается",
             code3 == 0 and "ЗАПАСНОЙ ЛИТЕРАЛ" in out3 and "role-roster-and-zones" in out3,
             f"код {code3} · предупреждение есть: "
             f"{'да' if 'ЗАПАСНОЙ ЛИТЕРАЛ' in out3 else 'НЕТ'}", differ=True)

        # ④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор данных — ДРУГАЯ роль (TAXO), не «COORD».
        # Без этого случая правка неотличима от разбора данных «для галочки»: если бы
        # источник данных не влиял на решение, ①②③ остались бы теми же, а этот — нет.
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='координатор контура; проба' "
                    "WHERE role='TAXO'")
        con.commit()
        con.close()
        code4a, out4a = call_tool(tool, container, "--role", "TAXO", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        code4b, out4b = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        case("④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор в данных — TAXO → TAXO пишет, буквальный "
             "«COORD» — уже НЕТ",
             code4a == 0 and code4b != 0 and "координатор TAXO" in out4b,
             f"TAXO код {code4a} · COORD код {code4b} · координатор назван TAXO в отказе: "
             f"{'да' if 'координатор TAXO' in out4b else 'НЕТ'}", differ=True)

        print("")
        print(f"ИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
        return 0 if PASSED == CASES else 1
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
