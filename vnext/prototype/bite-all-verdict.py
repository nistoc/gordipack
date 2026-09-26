# -*- coding: utf-8 -*-
r"""bite-all-verdict.py — приёмка приговора общего прогона bite-all.py: «не запустилась»
ставится только по ПРИМЕТЕ ЦЕЛЫМ СЛОВОМ, а не по подстроке в тексте случаев.

═══ ЧТО БЫЛО (возврат карточки #659 по ①, находка COORD 26.09, записка #5398)
Примета «не найден» искалась подстрокой во всём выводе приёмки. Приёмка поиска по памяти
печатает обычные строки случаев «код 2 → не найдено (ждали …)» — и её настоящий провал
с кодом 1 общий прогон называл «не запустилась». Живой итог по сути был «сломано 2»,
а читался «сломано 1».

═══ СЛУЧАИ
    ① провал (код 1) со строкой случая «не найдено (ждали …)» — приговор «СЛОМАНО»
    ② ВСТРЕЧНЫЙ: провал со строкой «ERR: файл не найден» — «не запустилась», как прежде
    ③ ВСТРЕЧНЫЙ: код 2 — отказ мерить, как прежде
    ④ ОБРАТНЫЙ ХОД: прежнее правило (подстрока) на выводе ① — снова «не запустилась»

═══ ГРАНИЦА
Судится функция приговора verdict() из самого bite-all.py (берётся из исходника, не
переписана здесь). Какие приметы вообще считать признаком незапуска — приёмка не судит.
"""
import importlib.util
import sys
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

    failed = [n for n, ok, _ in results if not ok]
    print("")
    print(f"{'🔴 НЕ ПРИНЯТО' if failed else '✅ ПРИГОВОР ОБЩЕГО ПРОГОНА — ПРИНЯТО'} — случаев {len(results)},"
          f" встречных 2, обратный ход 1")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
