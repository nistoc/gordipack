# -*- coding: utf-8 -*-
r"""bite-all-verdict.py — приёмка приговора общего прогона bite-all.py: «не запустилась»
ставится только по ПРИМЕТЕ ЦЕЛЫМ СЛОВОМ и только когда приёмка не напечатала ни одного
своего случая — а не по подстроке в тексте случаев.

═══ ЧТО БЫЛО (возврат карточки #659 по ①, находка COORD 26.09, записка #5398)
Примета «не найден» искалась подстрокой во всём выводе приёмки. Приёмка поиска по памяти
печатает обычные строки случаев «код 2 → не найдено (ждали …)» — и её настоящий провал
с кодом 1 общий прогон называл «не запустилась». Живой итог по сути был «сломано 2»,
а читался «сломано 1».

═══ ВТОРОЙ ВОЗВРАТ (находка COORD 26.09 21:28 UTC, записка #5403)
И ЦЕЛЫМ словом примета стоит в тексте случая: «ответ снова не найден» у
bite-bridge-own-letters.py — её провал случая ⑤ на новом контуре печатался «не запустилась».
Теперь примета судит только вывод, где приёмка не напечатала ни одного своего случая.

═══ СЛУЧАИ
    ① провал (код 1) со строкой случая «не найдено (ждали …)» — приговор «СЛОМАНО»
    ② ВСТРЕЧНЫЙ: провал со строкой «ERR: файл не найден», случаев нет — «не запустилась», как прежде
    ③ ВСТРЕЧНЫЙ: код 2 — отказ мерить, как прежде
    ④ ОБРАТНЫЙ ХОД: прежнее правило (подстрока) на выводе ① — снова «не запустилась»
    ⑤ провал с напечатанными случаями, где примета стоит ЦЕЛЫМ словом в тексте случая — «СЛОМАНО»
    ⑥ ОБРАТНЫЙ ХОД: правило «только целым словом» (без проверки случаев) на выводе ⑤ — «незапуск»
    ⑦ ВСТРЕЧНЫЙ: трасса падения до первого случая (ModuleNotFoundError) — «не запустилась»

═══ КАРТОЧКИ #759 И #760 (набор приёмок: код выхода, --verbose, принята с пропуском)
    ⑧  одна не запустившаяся и остальные прошедшие — код выхода набора 2 (карточка #759, пункт ①)
    ⑨  ВСТРЕЧНЫЙ: всё прошло — код 0
    ⑩  ВСТРЕЧНЫЙ: есть сломанная — код 1
    ⑪  ВСТРЕЧНЫЙ: сломанная вместе с не запустившейся — код 1 (сломанная сильнее)
    ⑫  ВСТРЕЧНЫЙ: настоящий отказ мерить (код 2) — «⚠️ … не запустилась», в «принято с пропуском» не идёт (#760 ④)
    ⑬  приёмка, принявшая себя с пропуском (код 2 как у bite-launcher-forms и код 0), — «✅ принята, пропущено N»,
        в «НЕ ПРОВЕРЕНО» не идёт, код набора 0, в итоге «принято с пропуском: K» (карточка #760, пункт ③)
    ⑭  ВСТРЕЧНЫЙ к ⑬: отказ с числом «не проверено» без слова «принята» и «НЕ ПРИНЯТ … пропущено» остаются отказом
    ⑮  --verbose печатает вывод приёмки ЦЕЛИКОМ, строка «ИТОГ: …» из середины вывода видна (карточка #760, пункт ①)
    ⑯  ВСТРЕЧНЫЙ к ⑮: без --verbose — прежний хвост из шести непустых строк, строки «ИТОГ: …» нет
    Случаи ⑧–⑪, ⑬, ⑮, ⑯ гоняют сам bite-all.py подложенным каталогом приёмок (--dir) и подложенной копией
    «лежащей контуром» (--target): код выхода и текст читаются у настоящего набора, а не у его функции.

═══ ГРАНИЦА
Судится функция приговора verdict() из самого bite-all.py (берётся из исходника, не
переписана здесь). Какие приметы вообще считать признаком незапуска — приёмка не судит.
Приёмки в подложенном каталоге — заглушки с заданным кодом и текстом, а не настоящие: что настоящая
bite-launcher-forms печатает именно так, видно из её строк 1165–1184, а не из этого прогона.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "bite-all.py"

results: list[tuple[str, bool, str]] = []


def record_case(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'✅' if ok else '🔴'} {name}")
    print(f"   {detail}")


def load_runner():
    """Загрузить bite-all.py как модуль (имя с дефисом — через importlib)."""
    spec = importlib.util.spec_from_file_location("bite_all_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HERE))
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if not RUNNER.exists():
        print(f"⚪ не проверено: рядом нет bite-all.py ({RUNNER})")
        return 2
    runner = load_runner()
    case_text = ("🔴 ③ встречный случай: найдено 0 из 5\n"
                 "   n1 «права на отправку кода» код 2 → не найдено (ждали «08.08»)\n")
    mark, word = runner.verdict(1, case_text)
    record_case("① провал со строкой случая «не найдено (ждали …)» — приговор «СЛОМАНО»",
                word == "СЛОМАНО", f"приговор: {mark} {word}")
    mark2, word2 = runner.verdict(1, "ERR: файл не найден: C:/x/y.py\n")
    record_case("② ВСТРЕЧНЫЙ: «файл не найден» — по-прежнему «не запустилась»",
                word2 == "не запустилась", f"приговор: {mark2} {word2}")
    mark3, word3 = runner.verdict(2, "⚪ не проверено: испытуемого нет\n")
    record_case("③ ВСТРЕЧНЫЙ: код 2 — отказ мерить, как прежде",
                word3.startswith("не запустилась (отказ мерить"), f"приговор: {mark3} {word3}")
    old_rule = any(m in case_text.lower() for m in runner.CANT_START)
    record_case("④ ОБРАТНЫЙ ХОД: прежнее правило (подстрока) видит в выводе ① «незапуск»",
                old_rule, "разница двух правил и есть починка; сойдись они — ① зеленел бы по другой причине")
    # ⑤ — живой вывод bite-bridge-own-letters.py на новом контуре (записка #5403), сокращён
    word_case_text = ("🔴 ⑤ писем в папках мостов больше нуля\n"
                      "   писем: 0\n"
                      "✅ ⑬ ОБРАТНЫЙ ХОД: без имени вопроса (прежнее сличение по темам) ответ снова не найден\n"
                      "   разница двух прогонов и есть починка\n")
    mark5, word5 = runner.verdict(1, word_case_text)
    record_case("⑤ провал с напечатанными случаями и приметой ЦЕЛЫМ словом в тексте случая — «СЛОМАНО»",
                word5 == "СЛОМАНО", f"приговор: {mark5} {word5}")
    word_rule_only = bool(runner.CANT_START_RE.search(word_case_text.lower()))
    record_case("⑥ ОБРАТНЫЙ ХОД: правило «только целым словом» видит в выводе ⑤ «незапуск»",
                word_rule_only, "без проверки напечатанных случаев вывод ⑤ снова читался бы «не запустилась»")
    mark7, word7 = runner.verdict(1, "Traceback (most recent call last):\n"
                                     "ModuleNotFoundError: No module named 'mezo_stand'\n")
    record_case("⑦ ВСТРЕЧНЫЙ: трасса падения до первого случая — «не запустилась»",
                word7 == "не запустилась", f"приговор: {mark7} {word7}")

    exit_code_and_skip_cases(runner)

    failed = [n for n, ok, _ in results if not ok]
    print("")
    print(f"{'🔴 НЕ ПРИНЯТО' if failed else '✅ ПРИГОВОР ОБЩЕГО ПРОГОНА — ПРИНЯТО'} — случаев {len(results)},"
          f" встречных 9, обратный ход 2")
    return 1 if failed else 0


# ═══ КАРТОЧКИ #759 И #760: код выхода набора, --verbose, «принята с пропуском» ═══
PASS_BITE = 'print("✅ случай")\n'
STUCK_BITE = 'import sys\nprint("⛔ НЕ ЗАПУСТИЛАСЬ: нужен контур")\nsys.exit(2)\n'
FAIL_BITE = 'import sys\nprint("🔴 случай")\nsys.exit(1)\n'
# как bite-launcher-forms.py:1165-1184: принята, часть случаев не проверена — код 2
SKIP_CODE2_BITE = ('import sys\nprint("✅ случай")\n'
                   'print("✅ ПРОВЕРКА ПРИНЯТА — случаев 35, различающих 34 · пропущено 2")\n'
                   'print("⚪ не проверено 2: первый · второй")\nsys.exit(2)\n')
SKIP_CODE0_BITE = ('print("✅ случай")\n'
                   'print("✅ ПРОВЕРКА ПРИНЯТА — случаев 4 · пропущено 3")\n')
# длинный вывод: строка «ИТОГ» стоит в СЕРЕДИНЕ, после неё ещё двенадцать строк (как «границы замера» у bite-find-owner-word)
LONG_LINES = (["🔴 случай"] + [f"строка {i}" for i in range(1, 9)] + ["ИТОГ: прошло 48 · пало 0"]
              + [f"граница замера {i}" for i in range(1, 13)])
LONG_BITE = ("import sys\n" + "".join(f"print({line!r})\n" for line in LONG_LINES) + "sys.exit(1)\n")
TAIL_PREFIX = " " * 8


def run_set(runner_path, files, extra=()):
    """Гонять НАСТОЯЩИЙ набор по подложенному каталогу приёмок (--dir) и копии, лежащей контуром (--target).
    (код выхода набора, весь вывод)."""
    with tempfile.TemporaryDirectory(prefix="bite-all-verdict-") as tmp:
        bites_dir = Path(tmp) / "bites"
        bites_dir.mkdir()
        target = Path(tmp) / "stand" / ".mezosync" / "scripts"
        target.mkdir(parents=True)
        (target.parent / "mezosync.db").write_bytes(b"x")   # непустая база рядом: копия «лежит контуром», раскладка не нужна
        for name, body in files.items():
            (bites_dir / name).write_text(body, encoding="utf-8")
        # копии провалов набор кладёт во временный каталог: пусть это будет наш, он уйдёт вместе с остальным
        own_temp = Path(tmp) / "own-temp"
        own_temp.mkdir()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", TEMP=str(own_temp), TMP=str(own_temp),
                   TMPDIR=str(own_temp))
        r = subprocess.run([sys.executable, str(runner_path), "--dir", str(bites_dir), "--target", str(target),
                            "--timeout", "60", *extra], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(HERE), env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def line_of(out: str, needle: str) -> str:
    return next((l for l in out.splitlines() if needle in l), "")


def tail_lines(out: str, name: str):
    """Строки с отступом из вывода набора, идущие после строки приёмки `name` до разделителя итога
    (без строки о сохранении полного вывода)."""
    lines, got, on = out.splitlines(), [], False
    for l in lines:
        if not on:
            on = name in l and not l.startswith(TAIL_PREFIX)
            continue
        if l.startswith("-" * 10):
            break
        if l.startswith(TAIL_PREFIX) and "📄" not in l:
            got.append(l[len(TAIL_PREFIX):])
    return got


def exit_code_and_skip_cases(runner) -> None:
    runner_path = RUNNER
    code8, out8 = run_set(runner_path, {"bite-zz-a.py": PASS_BITE, "bite-zz-b.py": PASS_BITE,
                                        "bite-zz-stuck.py": STUCK_BITE})
    record_case("⑧ карточка #759: одна не запустившаяся, остальные прошли — код выхода набора 2",
                code8 == 2 and "НЕ ПРОВЕРЕНО 1" in out8,
                f"код {code8}; итог: {line_of(out8, 'НЕ ПРОВЕРЕНО')!r}")
    code9, out9 = run_set(runner_path, {"bite-zz-a.py": PASS_BITE, "bite-zz-b.py": PASS_BITE})
    record_case("⑨ ВСТРЕЧНЫЙ: всё прошло — код 0",
                code9 == 0 and "держится 2 · сломано 0 · НЕ ПРОВЕРЕНО 0" in out9,
                f"код {code9}; итог: {line_of(out9, 'НЕ ПРОВЕРЕНО')!r}")
    code10, out10 = run_set(runner_path, {"bite-zz-a.py": PASS_BITE, "bite-zz-fail.py": FAIL_BITE})
    record_case("⑩ ВСТРЕЧНЫЙ: есть сломанная — код 1",
                code10 == 1 and "сломано 1" in out10,
                f"код {code10}; итог: {line_of(out10, 'НЕ ПРОВЕРЕНО')!r}")
    code11, out11 = run_set(runner_path, {"bite-zz-fail.py": FAIL_BITE, "bite-zz-stuck.py": STUCK_BITE,
                                          "bite-zz-a.py": PASS_BITE})
    record_case("⑪ ВСТРЕЧНЫЙ: сломанная вместе с не запустившейся — код 1 (сломанная сильнее)",
                code11 == 1 and "сломано 1" in out11 and "НЕ ПРОВЕРЕНО 1" in out11,
                f"код {code11}; итог: {line_of(out11, 'НЕ ПРОВЕРЕНО')!r}")

    stuck_line = line_of(out8, "bite-zz-stuck.py")
    record_case("⑫ ВСТРЕЧНЫЙ: настоящий отказ мерить (код 2) — «⚠️ … не запустилась», не «принята с пропуском»",
                stuck_line.startswith("⚠️") and "не запустилась (отказ мерить, код 2)" in stuck_line
                and "принято с пропуском: 0" in out8,
                f"строка приёмки: {stuck_line!r}")

    code13, out13 = run_set(runner_path, {"bite-zz-a.py": PASS_BITE, "bite-zz-skip2.py": SKIP_CODE2_BITE,
                                          "bite-zz-skip0.py": SKIP_CODE0_BITE})
    line2, line0 = line_of(out13, "bite-zz-skip2.py"), line_of(out13, "bite-zz-skip0.py")
    record_case("⑬ карточка #760: принятая с пропуском (код 2 и код 0) — «✅ принята, пропущено N», не «не запустилась», код набора 0",
                line2.startswith("✅") and "принята, пропущено 2" in line2
                and line0.startswith("✅") and "принята, пропущено 3" in line0
                and "НЕ ПРОВЕРЕНО 0" in out13 and "принято с пропуском: 2" in out13 and code13 == 0,
                f"код {code13}; строки: {line2!r} · {line0!r}; итог: {line_of(out13, 'НЕ ПРОВЕРЕНО')!r}")

    refusal_with_number = runner.verdict(2, "⚪ не проверено 3: первый · второй\n")
    not_accepted = runner.verdict(2, "🔴 НЕ ПРИНЯТ — случаев 5 · пропущено 1\n")
    record_case("⑭ ВСТРЕЧНЫЙ к ⑬: отказ с числом «не проверено» и «НЕ ПРИНЯТ … пропущено» остаются отказом (код 2)",
                refusal_with_number[0] == "⚠️" and not_accepted[0] == "⚠️",
                f"без слова «принята»: {refusal_with_number} · «НЕ ПРИНЯТ»: {not_accepted}")

    code15, out15 = run_set(runner_path, {"bite-zz-long.py": LONG_BITE}, ("--verbose",))
    got15 = tail_lines(out15, "bite-zz-long.py")
    record_case("⑮ карточка #760: --verbose печатает вывод приёмки ЦЕЛИКОМ — строка «ИТОГ: …» из середины видна",
                got15 == LONG_LINES, f"код {code15}; напечатано строк {len(got15)} из {len(LONG_LINES)}; "
                f"«ИТОГ» {'есть' if 'ИТОГ: прошло 48 · пало 0' in got15 else 'НЕТ'}")

    code16, out16 = run_set(runner_path, {"bite-zz-long.py": LONG_BITE})
    got16 = tail_lines(out16, "bite-zz-long.py")
    record_case("⑯ ВСТРЕЧНЫЙ к ⑮: без --verbose — ровно шесть последних непустых строк, строки «ИТОГ: …» нет",
                got16 == LONG_LINES[-6:] and "ИТОГ: прошло 48 · пало 0" not in got16,
                f"код {code16}; напечатано строк {len(got16)}, ждали 6")


if __name__ == "__main__":
    sys.exit(main())
