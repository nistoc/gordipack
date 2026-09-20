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
  ⑤ ⑤-бис РЕГИСТР КИРИЛЛИЦЫ: причина роли написана с заглавной и прописными —
     слово всё равно найдено (возврат COORD 2026-09-15: запрос LIKE сворачивает
     регистр только у латиницы и такую причину не видел вовсе)                   РАЗЛИЧАЮЩИЙ

НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-literal): _writer_gate возвращён к литералу «COORD» —
ждём красным РОВНО ④ (роль-координатор из данных «TAXO» перестаёт писать, а «COORD» —
роль, переставшая быть координатором — снова пишет); ① ② ③ целы, потому что в них
координатор данных СОВПАДАЕТ с «COORD» и литерал их не различает.
ВТОРАЯ НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-like): слово ищется запросом LIKE вместо
casefold() — ждём красным РОВНО ⑤ и ⑤-бис; ①–④ целы (там причина записана строчными).

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
    ap.add_argument("--porcha", choices=["revert-to-literal", "revert-to-like"],
                    help="нарочная поломка: revert-to-literal — вернуть проверку писателя "
                         "к литералу «COORD»; revert-to-like — вернуть отбор слова запросом "
                         "LIKE, слепым к заглавной кириллице")
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
            # 🎯 Порча возвращает ИМЕННО литерал карточки #645: отказ при неоднозначном
            # координаторе заменён на безусловный запасной «COORD» — сам поиск в данных
            # (roles.lifecycle_reason) остаётся исправным. ①②④ целы: там ровно ОДНА
            # живая роль-координатор, путь через None не задействован вовсе.
            # ③ и ③-бис — единственные, где найдено НЕ РОВНО ОДНА роль: под порчей
            # они молча получают «COORD» вместо отказа — вот они и краснеют.
            text = tool.read_text(encoding="utf-8")
            old = ('    if coordinator is None:\n'
                   '        sys.exit(f"⛔ координатор контура НЕ ОПРЕДЕЛЁН ОДНОЗНАЧНО: {source}")')
            new = '    if coordinator is None:\n        coordinator = "COORD"  # литерал (поломка карточки #645)'
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-literal»: без ровно одной роли-координатора "
                  "снова подставляется литерал «COORD» БЕЗ отказа. Ждём красным РОВНО ③ и "
                  "③-бис; ①②④ целы (там всегда ровно одна роль, путь через литерал не "
                  "задействован)\n")

        if a.porcha == "revert-to-like":
            # 🎯 Порча возвращает ВТОРУЮ половину карточки #645: регистр слова больше
            # не сворачивается — ровно так вела себя прежняя выборка запросом LIKE
            # (в SQLite он сворачивает регистр только у латиницы). Краснеют РОВНО
            # ⑤ и ⑤-бис (причина с заглавной кириллицы); ①–④ целы: там причина
            # записана строчными, и слепой к регистру поиск её находит.
            text = tool.read_text(encoding="utf-8")
            old = '\n'.join([
                '    names = sorted(role.upper() for role, reason in rows',
                '                   if "координатор" in (reason or "").casefold())'])
            new = '\n'.join([
                '    names = sorted(role.upper() for role, reason in rows',
                '                   if "координатор" in (reason or ""))'])
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-like»: регистр слова больше не сворачивается. "
                  "Ждём красным РОВНО ⑤ и ⑤-бис; ①–④ целы\n")

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

        # ③ данные НЕ НАЗЫВАЮТ НИ ОДНОЙ роли-координатора (карточка #645, критерий ①):
        # НЕ подставляем литерал — ОТКАЗ словами, называющий, что найдено (0 ролей),
        # и как назвать координатора в контуре (готовая команда/запрос).
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='в живом реестре' WHERE role='COORD'")
        con.commit()
        con.close()
        code3, out3 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("③ данные не называют НИ ОДНОЙ роли-координатора → ОТКАЗ (не литерал), "
             "названо «найдено 0» и готовая команда проверки",
             code3 != 0 and "найдено 0" in out3 and "set-rule.py" in out3
             and "COORD" not in out3.split("⛔")[-1].split("найдено")[0],
             f"код {code3} · вывод: {out3.strip()[:250]}", differ=True)

        # ③-бис данные называют ДВЕ роли-координатора разом → ОТКАЗ, названы ОБЕ
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='координатор (проба множественности)' "
                    "WHERE role IN ('CORE', 'STUD')")
        con.commit()
        con.close()
        code3b, out3b = call_tool(tool, container, "--role", "CORE", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        case("③-бис данные называют ДВЕ роли-координатора разом → ОТКАЗ, названы ОБЕ",
             code3b != 0 and "найдено 2" in out3b and "CORE" in out3b and "STUD" in out3b,
             f"код {code3b} · вывод: {out3b.strip()[:250]}", differ=True)

        # снять пробу множественности перед случаем ④ — иначе у него окажется НЕ ОДНА роль.
        # ⚠️ Текст сброса НЕ ДОЛЖЕН нести подстроку «координатор» ни в каком виде (даже
        # отрицанием) — LIKE '%координатор%' слеп к смыслу слова, судит только буквы.
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='рядовая зона контура' "
                    "WHERE role IN ('CORE', 'STUD')")
        con.commit()
        con.close()

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

        # ⑤ и ⑤-бис РЕГИСТР КИРИЛЛИЦЫ (возврат COORD по карточке #645, 2026-09-15):
        # причина роли начинается с заглавной — обычное начало фразы. Запрос LIKE такую
        # причину НЕ находил, и координатор становился «не найден» на ровном месте.
        for mark, reason in (("⑤", "Координатор контура; проба заглавной"),
                             ("⑤-бис", "КООРДИНАТОР КОНТУРА; ПРОБА ПРОПИСНЫХ")):
            con = sqlite3.connect(str(db))
            con.execute("UPDATE roles SET lifecycle_reason='рядовая зона контура' "
                        "WHERE role='TAXO'")
            con.execute("UPDATE roles SET lifecycle_reason=? WHERE role='COORD'", (reason,))
            con.commit()
            con.close()
            code5, out5 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                    "--body-file", str(body_file), "--dry-run")
            case(f"{mark} причина «{reason[:28]}…» — слово найдено, писатель пропущен",
                 code5 == 0 and "⟨ВХОЛОСТУЮ⟩" in out5,
                 f"код {code5} · отказ: {'нет' if code5 == 0 else out5.strip()[:120]}",
                 differ=True)

        print("")
        print(f"ИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
        return 0 if PASSED == CASES else 1
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
