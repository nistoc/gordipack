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

═══ ⑦–⑬ — КАРТОЧКА #665 (26.09, находка контура tapas)
Первая строка «контура <мы>» есть только у писем с 25.08; у нас 110 из 142 писем
«исторического хвоста» оказались своими. Признаков стало три: ① «контура <мы>» · ② «пишет
РОЛЬ (<мы>)» · ③ наша исходящая папка «<мы>-<сосед>» (считается отдельно: письмо соседа,
положенное в нашу папку, так не отличить). Встречные ⑧ ⑩ — чужой контур и смешанная папка
старого обмена; обратный ход ⑪. ⑫–⑬ — ответ под другим именем темы засчитывается по
ссылке на файл вопроса в первой строке (вопрос tapas 13 суток висел «311 ч без ответа»).

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
    return own_letter_namespace(group_name)["_is_our_letter"]


def own_letter_namespace(group_name: str, source: str = "") -> dict:
    """Обе функции различения (_our_letter_sign и _is_our_letter) из исходника проверки.
    source — подменённый текст для обратного хода; по умолчанию живой исходник."""
    text = source or SOURCE_TEXT
    namespace: dict = {"Path": Path}
    start = text.index("    def _our_letter_sign(file)")
    end = text.index("    unannounced = []", start)
    body = "\n".join(ln[4:] if ln.startswith("    ") else ln
                     for ln in text[start:end].splitlines())
    namespace["_own_name"] = group_name
    exec(body, namespace)                                  # noqa: S102 — свой же исходник
    return namespace


def extract_function(name: str, namespace: dict) -> None:
    """Достать из исходника проверки одну вложенную функцию (отступ 4) и исполнить её
    в namespace. Тело — строки глубже отступа 4 до первой строки с отступом ≤ 4."""
    lines = SOURCE_TEXT.splitlines()
    head = f"    def {name}("
    start = next(i for i, ln in enumerate(lines) if ln.startswith(head))
    body = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and not ln.startswith("        "):
            break
        body.append(ln)
    exec("\n".join(ln[4:] for ln in body), namespace)      # noqa: S102 — свой же исходник


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

    # ── ⑦–⑬ КАРТОЧКА #665: ТРИ ПРИЗНАКА СВОЕГО ПИСЬМА И ОТВЕТ ПО ССЫЛКЕ НА ВОПРОС.
    #    Находка контура tapas 26.09: письма до 25.08 не несут «контура <мы>» в первой строке,
    #    и проверка держала их «записками соседей без разбора» (у нас 110 из 142).
    sign_ns = own_letter_namespace("atlas")
    sign = sign_ns["_our_letter_sign"]
    old_kind = stand / "answer.tapas.старый-вид.md"
    old_kind.write_text("2026-08-23 07:26 UTC · пишет COORD (atlas), в ответ на `answer.atlas.x.md`.\n",
                        encoding="utf-8")
    record_case("⑦ письмо старого вида «пишет РОЛЬ (<мы>)» опознано как наше",
                sign(old_kind) == "role", f"признак: {sign(old_kind)}")
    wrong_contour = stand / "ask.atlas.сосед-старого-вида.md"
    wrong_contour.write_text("2026-08-23 07:26 UTC · пишет COORD (tapas), вопрос к вам.\n",
                             encoding="utf-8")
    other_form = stand / "ask.atlas.сосед-новая-форма.md"
    other_form.write_text("2026-09-26 14:57 UTC · пишет PROTO контура Tapas.\n", encoding="utf-8")
    record_case("⑧ ВСТРЕЧНЫЙ: «пишет РОЛЬ (<сосед>)» и «пишет РОЛЬ контура <сосед>» — НЕ наши",
                sign(wrong_contour) is None and sign(other_form) is None,
                f"признаки: {sign(wrong_contour)} · {sign(other_form)}")
    our_box = stand / "atlas-tapas"
    our_box.mkdir()
    headless = our_box / "answer.tapas.без-автора.md"
    headless.write_text("# Atlas → Tapas: заголовок без автора\n", encoding="utf-8")
    record_case("⑨ письмо без автора в НАШЕЙ исходящей папке «<мы>-<сосед>» — наше, признаком «папка»",
                sign(headless) == "folder", f"признак: {sign(headless)}")
    mixed_box = stand / "aia-stud-exchange"
    mixed_box.mkdir()
    mixed = mixed_box / "answer.aia-проба.md"
    mixed.write_text("# AIA → Atlas: письмо соседа в смешанной папке\n", encoding="utf-8")
    record_case("⑩ ВСТРЕЧНЫЙ: то же письмо без автора в СМЕШАННОЙ папке старого обмена — НЕ наше",
                sign(mixed) is None,
                f"признак: {sign(mixed)} — признак папки судит только «<мы>-…», иначе чужое стало бы нашим")
    reverse_src = SOURCE_TEXT.replace('return "role"', "return None").replace('return "folder"', "return None")
    reverse = own_letter_namespace("atlas", reverse_src)["_our_letter_sign"]
    record_case("⑪ ОБРАТНЫЙ ХОД: без признаков ② и ③ письма ⑦ и ⑨ снова не наши",
                reverse_src != SOURCE_TEXT and reverse(old_kind) is None and reverse(headless) is None,
                "разница двух прогонов и есть починка; сойдись они — ⑦ и ⑨ зеленели бы по другой причине")

    # ⑫–⑬ ответ по ссылке: функции сличения берутся из исходника, папки — на стенде
    answer_ns: dict = {"BRIDGES": stand, "Path": Path}
    for fn_name in ("_neighbor_dirs", "_box_files", "_topic", "_answer_cites", "_answers_to"):
        extract_function(fn_name, answer_ns)
    ask_name = "ask.atlas.caller-identity-service-kind-and-receiver-sets-owner.md"
    cited = our_box / "answer.tapas.caller-identity-service-yes-owner-part-after-core-check.md"
    cited.write_text(f"2026-09-13 15:50 UTC · пишет **PROTO контура Atlas**, в ответ на `{ask_name}`.\n",
                     encoding="utf-8")
    silent = our_box / "answer.tapas.совсем-другое.md"
    silent.write_text("2026-09-13 16:00 UTC · пишет **PROTO контура Atlas**, о другом.\n", encoding="utf-8")
    topic = answer_ns["_topic"](ask_name)
    hits = answer_ns["_answers_to"](topic, "tapas", ask_name)
    record_case("⑫ ответ под ДРУГИМ именем темы засчитан по ссылке на файл вопроса в первой строке",
                cited.name in hits and silent.name not in hits,
                f"засчитаны: {hits} — ответ без ссылки (встречный) не засчитан")
    by_topic_only = answer_ns["_answers_to"](topic, "tapas")
    record_case("⑬ ОБРАТНЫЙ ХОД: без имени вопроса (прежнее сличение по темам) ответ снова не найден",
                cited.name not in by_topic_only,
                f"по темам: {by_topic_only} — ровно так проверка 13 суток держала «311 ч без ответа»")

    failed = [case_name for case_name, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 4 (② ③ ⑧ ⑩) и ОБРАТНЫХ ХОДОВ 2 (⑪ ⑬);"
          " ⑥ добавлен по границе @COORD, ⑦–⑬ — карточка #665")
    print("⚖️ Признак берётся ИЗ ЖИВОГО инструмента, а не переписан здесь: переписанная")
    print("   копия зелена к себе самой и о предмете не говорит ничего.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
