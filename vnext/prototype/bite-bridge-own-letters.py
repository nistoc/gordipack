# -*- coding: utf-8 -*-
r"""bite-bridge-own-letters.py — приёмка карточки #573: проверка моста не требует разбора
с НАШИХ СОБСТВЕННЫХ писем.

═══ ЧТО БЫЛО
В каталоге обмена с соседними контурами лежат письма обеих сторон, а автор не различался
вовсе. Проверка требовала «жеста разбора» и с наших писем тоже. Замер 2026-09-05: из 104
файлов каталога наших 8, соседских 29, по первой строке не определить 67; наших свежих
было 7 — ровно они и горели.
🔴 И вот чем это доказано, а не предположено: ШЕСТЬ из семи уже были погашены жестом,
и погасили их роли НАШЕГО же контура. Жест, заведённый отличать «письмо соседа прочитано»
от «имя где-то упомянуто», стал ставиться на свои письма, лишь бы признак замолчал.

═══ ОЖИДАНИЯ ПОЛОМОК — НАЗВАНЫ ДО ПРОГОНА, И ОДНО ОКАЗАЛОСЬ УЖЕ ИСТИНЫ
    П1 признак всегда говорит «не наше»
       ждали ① ④ ⑤ ... вышло ① ④ ⑤ — точно
    П2 признак всегда говорит «наше»
       ждали ② ③ ..... вышло ② ③ И ЕЩЁ ④. Ожидание было у́же истины: случай ④ судит
                       ОБЕ половины сразу (наше письмо с чужим именем контура перестаёт
                       быть нашим, а чужое — становится), и вторая половина падает тоже.
                       Записано как было: ожидание, подогнанное задним числом, ничего
                       не проверяет.

═══ ГРАНИЦА ЭТОЙ ПРИЁМКИ, НАЗВАНА ПРЯМО
Судится ПРИЗНАК различения на подопытных файлах и его влияние на живой прогон.
⛔ Приёмка НЕ строит целый стенд контура (база + каталоги обмена) и потому не судит,
как список ведёт себя при других сочетаниях. Что признак применён именно к списку —
подтверждается живым прогоном: он печатает, сколько наших писем выведено из-под суда.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

GUARD_ALL = Path(mezo_paths.live_scripts(__file__)) / "guard-all.py"
SOURCE_TEXT = GUARD_ALL.read_text(encoding="utf-8")

results: list[tuple[str, bool, str]] = []


def record_case(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'✅' if ok else '🔴'} {name}: {detail}")


def own_letter_predicate(group_name: str):
    """Достать из живого прогона ТУ ЖЕ функцию различения, а не переписывать её здесь.

    ⚡ Переписанная копия признака — это своя транскрипция вместо предмета: она зелена
    к себе самой и ничего не говорит о том, что стои́т в инструменте.
    """
    namespace: dict = {"Path": Path}
    start = SOURCE_TEXT.index("    def _is_our_letter(file)")
    end = SOURCE_TEXT.index("    unannounced = []", start)
    body = "\n".join(ln[4:] if ln.startswith("    ") else ln
                     for ln in SOURCE_TEXT[start:end].splitlines())
    namespace["_own_name"] = group_name
    exec(body, namespace)                                  # noqa: S102 — свой же исходник
    return namespace["_is_our_letter"]


def main() -> int:
    stand = Path(tempfile.mkdtemp(prefix="bite-own-letters-"))
    mezo_stand.release(stand)

    ours = stand / "answer.tapas.проба.md"
    ours.write_text("2026-09-06 02:40 UTC · пишет **PROTO контура Atlas**. Все метки UTC.\n"
                    "тело письма\n", encoding="utf-8")
    theirs = stand / "ask.atlas.проба.md"
    theirs.write_text("2026-09-06 02:40 UTC · пишет **COORD контура Tapas**.\n"
                     "тело письма\n", encoding="utf-8")
    unnamed = stand / "status.проба.md"
    unnamed.write_text("# Просто заголовок без указания автора\n", encoding="utf-8")

    our_letter_fn = own_letter_predicate("atlas")

    record_case("① наше письмо опознано как наше", our_letter_fn(ours), "да")
    record_case("② ВСТРЕЧНЫЙ: письмо соседа НЕ опознано как наше",
           not our_letter_fn(theirs),
           "нет — значит признак различает автора, а не просто молчит про всё")
    record_case("③ ГРАНИЦА: письмо без указания автора судится ПО-ПРЕЖНЕМУ",
           not our_letter_fn(unnamed),
           "не наше — неизвестное авторство не считается нашим")

    # ④ имя контура берётся ИЗ БАЗЫ: с другим именем то же письмо перестаёт быть нашим
    other_predicate = own_letter_predicate("tapas")
    record_case("④ имя контура не впечатано: с чужим именем наше письмо уже не наше",
           not other_predicate(ours) and other_predicate(theirs),
           "признак следует за именем контура, а не за словом «Atlas» в коде")

    # ⑤ ЖИВОЙ ПРОГОН печатает, сколько наших писем выведено из-под суда — молчание
    #    об исключённых читалось бы как «проверено», а они не проверены, а ИСКЛЮЧЕНЫ.
    r = subprocess.run([sys.executable, str(GUARD_ALL)], capture_output=True, text=True,
                       encoding="utf-8", timeout=900)
    output = (r.stdout or "") + (r.stderr or "")
    match = re.search(r"📤 мост: наших собственных писем (\d+)", output)
    record_case("⑤ живой прогон НАЗЫВАЕТ число исключённых писем",
           match is not None and int(match.group(1)) > 0,
           f"сказано: {match.group(0)}" if match else "строки нет — исключение молчаливо")

    # ── ⑥ ГРАНИЦА, найденная @COORD (записка #4910) на трёх стендах: строка про исключённых
    #    обязана печататься и при НУЛЕ наших писем. Первая редакция печатала её только при
    #    ненуле, а пояснение над кодом обещало «ВСЕГДА» — обещание было шире кода.
    # ⚡ Читателю «исключённых ноль» и «проверка этого не делает» неразличимы: одно молчание
    #    на две разные беды. Судим условие печати ПРЯМО В ИСХОДНИКЕ: стенд с нулём наших
    #    писем эта приёмка не строит и того не обещает.
    condition_match = re.search(r"\n(\s*)if ([^\n]+):\n\s*print\(f\"📤 мост", SOURCE_TEXT)
    gated_by_count = bool(condition_match and "our_letters_count" in condition_match.group(2))
    record_case("⑥ строка про исключённых печатается и при НУЛЕ наших писем",
           condition_match is not None and not gated_by_count,
           f"условие печати: «{condition_match.group(2)}»" if condition_match else "условия печати не нашёл")

    failed = [case_name for case_name, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 2 (② и ③); ⑥ добавлен по границе @COORD")
    print("⚖️ Признак берётся ИЗ ЖИВОГО инструмента, а не переписан здесь: переписанная")
    print("   копия зелена к себе самой и о предмете не говорит ничего.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
