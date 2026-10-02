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
⑭–⑰ — два места, которых приёмка не видела (COORD при приёмке, записка #5403): папка соседа
«<сосед>-<мы>» (встречная ⑭ + поломка ⑮ «папка содержит имя») и места вызова сличения
ответов в самой проверке (⑯ + поломка ⑰ «вызов без имени вопроса»).

═══ ГРАНИЦА ЭТОЙ ПРИЁМКИ, НАЗВАНА ПРЯМО
Судится ПРИЗНАК различения на подопытных файлах и его влияние на живой прогон.
⛔ Приёмка НЕ строит целый стенд контура (база + каталоги обмена) и потому не судит,
как список ведёт себя при других сочетаниях. Что признак применён именно к списку —
подтверждается живым прогоном: он печатает, сколько наших писем выведено из-под суда.
⚖️ ОДНО ИСКЛЮЧЕНИЕ (карточка #667, пустой новый контур): если в каталоге обмена, который
судит проверка, нет НИ ОДНОГО письма, живому прогону нечего исключать, и «наших 0» там —
правда, а не провал. Тогда ⑤ мерится на КОПИИ: инструменты контура + снимок его базы +
два подставных письма (наше и соседа); ждём «наших 1» — ровно одно, не ноль и не оба.
"""
import ast
import re
import shutil
import sqlite3
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


def judged_bridge_letters(container: Path) -> int | None:
    """Сколько писем ЛЮБОГО автора лежит в каталоге обмена, который судит проверка, —
    предпосылка случая ⑤ (карточка #667). Каталог ищется функцией _by_marker ИЗ ИСХОДНИКА
    проверки (не своей копией) и берётся ПЕРВЫЙ найденный — так же, как guard-all.py
    (BRIDGES = _bridges[0]); INDEX.md письмом не считается и там. Различение «наше / не
    наше» здесь НЕ участвует: предпосылка, построенная на самом признаке, прятала бы его
    поломку («всегда не наше» дало бы ноль и увело ⑤ в другую ветку).
    None — в исходнике нет _by_marker: искать каталог тем же способом нечем."""
    tree = ast.parse(SOURCE_TEXT)
    node = next((n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "_by_marker"), None)
    if node is None:
        return None
    namespace: dict = {}
    exec(ast.get_source_segment(SOURCE_TEXT, node), namespace)  # noqa: S102 — свой же исходник
    found = namespace["_by_marker"](container, "bridges")
    if not found:
        return 0
    return sum(1 for f in found[0].glob("*/*.md") if f.name != "INDEX.md")


def seeded_bridge_run(stand: Path) -> str:
    """Прогон проверки на КОПИИ контура с подставными письмами (⑤ на пустом контуре).

    Копия: инструменты контура + снимок его базы (mezo_stand.snapshot_db, живая база
    только читается) + каталог обмена с двумя письмами — нашим (первая строка «контура
    Atlas», лежит в нашей исходящей «atlas-neigh») и соседа (в его папке «neigh-atlas»).
    Имя группы в копии назначает сама приёмка («atlas»): на новом контуре оно своё, и
    письма, написанные под «atlas», иначе не были бы нашими. Связи с соседями в копии
    стёрты — проверка на копии не ходит в настоящие соседние контуры."""
    live = mezo_paths.container_root(__file__) / ".mezosync"
    root = stand / "seeded"
    shutil.copytree(live / "scripts", root / ".mezosync" / "scripts")
    db = mezo_stand.snapshot_db(live / "mezosync.db", root / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO meta (key, value) VALUES ('group_name', 'atlas') "
                "ON CONFLICT(key) DO UPDATE SET value = 'atlas'")
    con.execute("DELETE FROM cross_links")
    con.commit()
    con.close()
    our_box = root / "bridges" / "atlas-neigh"
    our_box.mkdir(parents=True)
    (our_box / "answer.neigh.проба.md").write_text(
        "2026-09-06 02:40 UTC · пишет **PROTO контура Atlas**. Все метки UTC.\nтело письма\n",
        encoding="utf-8")
    their_box = root / "bridges" / "neigh-atlas"
    their_box.mkdir(parents=True)
    (their_box / "ask.atlas.проба.md").write_text(
        "2026-09-06 02:40 UTC · пишет **COORD контура Neigh**.\nтело письма\n",
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(root / ".mezosync" / "scripts" / "guard-all.py")],
                       capture_output=True, text=True, encoding="utf-8", timeout=900,
                       env=mezo_stand.stand_env(root))  # копия — контур, где лежит её guard-all
    return (r.stdout or "") + (r.stderr or "")


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
    # ⚖️ Карточка #667: в каталоге обмена пустого нового контура писем нет ВОВСЕ — живой
    #    прогон честно говорит «наших 0», и требовать там «больше нуля» значило бы красить
    #    правду. Тогда ⑤ мерится на копии с подставными письмами (seeded_bridge_run), и
    #    требование там ТОЧНЕЕ живого: ровно 1 из 2 — признак, говорящий «наше» про всё,
    #    дал бы 2, говорящий «не наше» про всё — 0.
    letters_total = judged_bridge_letters(mezo_paths.container_root(__file__))
    if letters_total is None:
        record_case("⑤ живой прогон НАЗЫВАЕТ число исключённых писем", False,
                    "в исходнике проверки нет _by_marker — каталог обмена тем же способом "
                    "не найти, предпосылку случая спросить нечем")
    elif letters_total == 0:
        output = seeded_bridge_run(stand)
        match = re.search(r"📤 мост: наших собственных писем (\d+)", output)
        record_case("⑤ прогон НАЗЫВАЕТ число исключённых писем (копия контура с подставными "
                    "письмами: в каталоге обмена контура писем нет ни одного)",
                    match is not None and int(match.group(1)) == 1,
                    (f"сказано: {match.group(0)}" if match else "строки нет — исключение молчаливо")
                    + " · ждём ровно 1: наше письмо из двух (наше и соседа)")
    else:
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

    # ⑭–⑰ — два места, которых приёмка не видела (находка COORD при приёмке, записка #5403).
    # ⑭ папка СОСЕДА, в имени которой наше имя стоит НЕ в начале («tapas-atlas»): встречная ⑩
    #    нашего имени не несла вовсе, и признак «папка содержит имя» прошёл бы её зелёным.
    their_box = stand / "tapas-atlas"
    their_box.mkdir()
    their_headless = their_box / "answer.atlas.без-автора.md"
    their_headless.write_text("# Tapas → Atlas: заголовок без автора\n", encoding="utf-8")
    record_case("⑭ ВСТРЕЧНЫЙ: письмо без автора в папке соседа «<сосед>-<мы>» — НЕ наше",
                sign(their_headless) is None,
                f"признак: {sign(their_headless)} — наше имя в папке есть, но не в начале")
    folder_anchor = 'file.parent.name.lower().startswith(own + "-")'
    contains_src = SOURCE_TEXT.replace(folder_anchor, "own in file.parent.name.lower()")
    contains_sign = own_letter_namespace("atlas", contains_src)["_our_letter_sign"]
    record_case("⑮ ПОЛОМКА: признак папки «содержит имя» вместо «начинается с <мы>-» красит ровно ⑭",
                SOURCE_TEXT.count(folder_anchor) == 1 and contains_sign(their_headless) == "folder"
                and contains_sign(headless) == "folder" and contains_sign(mixed) is None,
                f"под поломкой: ⑭ → {contains_sign(their_headless)} (ждём folder) · ⑨ → "
                f"{contains_sign(headless)} · ⑩ → {contains_sign(mixed)} (соседи не задеты)")

    # ⑯ оба места вызова сличения ответов передают имя вопроса: ⑫ зовёт функцию напрямую
    #    и не видит, что сама проверка зовёт её без имени (на настоящих папках — «311 ч»).
    def calls_with_ask_name(src: str) -> tuple[int, int]:
        tree = ast.parse(src)
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "_answers_to"]
        return len(calls), sum(1 for c in calls if len(c.args) + len(c.keywords) >= 3)
    total_calls, named_calls = calls_with_ask_name(SOURCE_TEXT)
    record_case("⑯ проверка зовёт сличение ответов с именем вопроса во ВСЕХ местах вызова",
                total_calls >= 2 and named_calls == total_calls,
                f"мест вызова {total_calls}, с именем вопроса {named_calls}")
    unnamed_src = re.sub(r"_answers_to\(([^()\n]*(?:\([^()\n]*\))?[^()\n]*?), [^,()\n]+\)\n",
                         r"_answers_to(\1)\n", SOURCE_TEXT)
    broken_total, broken_named = calls_with_ask_name(unnamed_src)
    record_case("⑰ ПОЛОМКА: места вызова без имени вопроса красят ровно ⑯",
                unnamed_src != SOURCE_TEXT and broken_total == total_calls and broken_named < broken_total,
                f"под поломкой: мест вызова {broken_total}, с именем вопроса {broken_named}")

    failed = [case_name for case_name, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 5 (② ③ ⑧ ⑩ ⑭), ОБРАТНЫХ ХОДОВ 2 (⑪ ⑬)"
          " и НАРОЧНЫХ ПОЛОМОК 2 (⑮ ⑰); ⑥ добавлен по границе @COORD, ⑦–⑰ — карточка #665")
    print("⚖️ Признак берётся ИЗ ЖИВОГО инструмента, а не переписан здесь: переписанная")
    print("   копия зелена к себе самой и о предмете не говорит ничего.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
