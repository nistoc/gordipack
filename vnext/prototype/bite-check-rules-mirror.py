# -*- coding: utf-8 -*-
r"""bite-check-rules-mirror.py — приёмка разбора ЗАМКА в заголовке правила зеркала.

🩸 ПОВОД (найдено контуром AIA, подтверждено в нашем коде, 2026-09-13). Заголовок правила
в файле-зеркале — `### \`ключ\` 🔒замок vN`. Замок печатает `export-rules.py` как значение
`locked_by` БЕЗ ОБРАБОТКИ, а `locked_by` бывает ДАТИРОВАННЫМ («owner-2026-07-29» — такой
встречался в живом своде). Прежний образец `🔒(\w+)` брал только буквы/цифры/подчёркивание:
дефис в `\w` не входит, и заголовок с датированным замком НЕ РАСПОЗНАВАЛСЯ ВООБЩЕ.
Правило с таким замком проверка объявляла «ЕСТЬ В БАЗЕ, НЕТ В ФАЙЛЕ» — ложное красное на
исправном файле, у AIA поймано именно так.

Правка: `🔒(\w+)` → `🔒([\w:.-]+)` — берёт дефис, точку, двоеточие; обычные замки
(`owner`, `coord`) распознаёт как прежде.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① ВСТРЕЧНЫЙ (контроль): обычный замок «coord» — распознаётся и сходится, как и раньше
  ② ГЛАВНЫЙ: датированный замок «owner-2026-07-29» — распознаётся, файл СОШЁЛСЯ с базой
  ③ ВСТРЕЧНЫЙ к ②: датированный замок с ИЗМЕНЁННЫМ телом — расхождение по-прежнему ловится
     (правка не превратила разбор в «всегда зелёно», замок читается, тело всё ещё сверяется)

НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-\\w): образец возвращён к `🔒(\\w+)` — ждём красным
РОВНО ②③ (датированный замок снова не распознаётся, правило «пропадает» из файла); ①
остаётся зелёным — обычный замок «coord» распознаётся и старым образцом тоже.

⛔ Живой базы не касается: своя временная БД (только колонки rule_key/body/version,
которых from_db() и просит) и свой временный файл-зеркало.
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


def build_db(path: Path, rules: dict):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE rules (rule_key TEXT, body TEXT, version INTEGER)")
    for key, (body, ver) in rules.items():
        con.execute("INSERT INTO rules (rule_key, body, version) VALUES (?,?,?)",
                    (key, body, ver))
    con.commit()
    con.close()


def write_mirror(path: Path, entries: list):
    """entries: [(key, lock, ver, body)] — форма заголовка ТА ЖЕ, что печатает export-rules.py."""
    parts = []
    for key, lock, ver, body in entries:
        parts.append(f"### `{key}` 🔒{lock} v{ver}\n\n{body.strip()}\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def call_tool(tool: Path, db: Path, mirror_file: Path):
    # ⚖️ MEZO_CONTAINER — ТОЛЬКО чтобы модуль импортировался (он резолвит LIVE/MIRROR по
    # умолчанию НА ВЕРХНЕМ УРОВНЕ, до argparse); --db и --file ниже перебивают оба дефолта,
    # так что чей это контейнер — не имеет значения для самого испытания.
    env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)))
    r = subprocess.run([sys.executable, "-B", str(tool), "--db", str(db),
                        "--file", str(mirror_file)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["revert-to-\\w"],
                    help="нарочная поломка: вернуть образец замка к 🔒(\\w+)")
    a = ap.parse_args()

    # 🩸 ИСПЫТЫВАТЬ НАДО И ТУ КОПИЮ, КОТОРУЮ ЗОВЁТ ОБЩИЙ ПРОГОН (13.09, в тот же день): guard-all
    # ищет звено РЯДОМ СО СКРИПТАМИ первым, а утренняя правка легла только в копию vnext-tools —
    # приёмка была зелёной, а ложное красное у AIA оставалось. Одинаковые пути (у собранного
    # контура звенья лежат рядом со скриптами) испытываются один раз.
    here = Path(__file__).resolve().parent
    targets = {}
    for label, path in (("копия vnext-tools", here / "check-rules-mirror.py"),
                        ("копия рядом со скриптами — её зовёт общий прогон",
                         mezo_paths.live_scripts(__file__) / "check-rules-mirror.py")):
        if not path.is_file():
            sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: check-rules-mirror.py нет: {path} ({label})")
        targets.setdefault(path.resolve(), label)
    for live_tool, label in targets.items():
        print(f"━━ испытуется: {label} — {live_tool}")
        run_cases(live_tool, a.porcha)
        print("")
    print(f"ИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
    return 0 if PASSED == CASES else 1


def run_cases(live_tool: Path, porcha) -> None:
    stand = Path(tempfile.mkdtemp(prefix="bite-rules-lock-"))
    try:
        tool = stand / "check-rules-mirror.py"
        shutil.copy2(live_tool, tool)
        # mezo_paths импортируется модулем на верхнем уровне (для LIVE/MIRROR по умолчанию,
        # оба перебиваются явными --db/--file) — копируем рядом, как и другие bite-*.
        shutil.copy2(Path(__file__).resolve().parent / "mezo_paths.py", stand / "mezo_paths.py")

        if porcha == "revert-to-\\w":
            text = tool.read_text(encoding="utf-8")
            old = r'🔒([\w:.-]+)\s*v(\d+)\s*$'
            new = r'🔒(\w+)\s*v(\d+)\s*$'
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-\\w»: образец замка возвращён к 🔒(\\w+). "
                  "Ждём красным РОВНО ②③ (датированный замок вновь не распознаётся); "
                  "① цел (замок «coord» — обычные буквы, \\w его и так брал)\n")

        # ① ВСТРЕЧНЫЙ/контроль: обычный замок «coord»
        db1 = stand / "s1.db"
        build_db(db1, {"test-plain": ("тело правила без даты в замке", 1)})
        mirror1 = stand / "m1.md"
        write_mirror(mirror1, [("test-plain", "coord", 1, "тело правила без даты в замке")])
        code1, out1 = call_tool(tool, db1, mirror1)
        case("① ВСТРЕЧНЫЙ: обычный замок «coord» — распознаётся и сходится, как и раньше",
             # две копии говорят «сошлось» разным регистром — судим по коду и корню слова
             code1 == 0 and "сошл" in out1.lower(),
             f"код {code1}")

        # ② ГЛАВНЫЙ: датированный замок «owner-2026-07-29»
        db2 = stand / "s2.db"
        build_db(db2, {"test-dated": ("тело правила с датированным замком", 1)})
        mirror2 = stand / "m2.md"
        write_mirror(mirror2, [("test-dated", "owner-2026-07-29", 1,
                                "тело правила с датированным замком")])
        code2, out2 = call_tool(tool, db2, mirror2)
        case("② ГЛАВНЫЙ: датированный замок «owner-2026-07-29» распознаётся, файл СОШЁЛСЯ",
             code2 == 0 and "сошл" in out2.lower() and "НЕТ В ФАЙЛЕ" not in out2,
             f"код {code2} · «НЕТ В ФАЙЛЕ» (ложное красное): "
             f"{'ЕСТЬ — дефис в замке всё ещё не берётся' if 'НЕТ В ФАЙЛЕ' in out2 else 'нет'}",
             differ=True)

        # ③ ВСТРЕЧНЫЙ к ②: то же самое, но тело в файле ИЗМЕНЕНО — расхождение обязано
        # ловиться по-прежнему (замок распознаётся, но это не значит «теперь всё зелено»)
        mirror3 = stand / "m3.md"
        write_mirror(mirror3, [("test-dated", "owner-2026-07-29", 1,
                                "ДРУГОЕ тело — правка мимо номера версии")])
        code3, out3 = call_tool(tool, db2, mirror3)
        case("③ ВСТРЕЧНЫЙ к ②: тело изменено при том же датированном замке — расхождение "
             "ловится (правка не превратила разбор в «всегда зелено»)",
             code3 == 1 and "ВЕРСИИ РАВНЫ, А ТЕКСТ РАЗНЫЙ" in out3,
             f"код {code3}", differ=True)
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
