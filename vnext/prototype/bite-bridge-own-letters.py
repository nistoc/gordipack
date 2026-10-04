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

═══ ⑱–㉖ — КАРТОЧКА #673 (04.10, находка контура AIA, их карточка 147)
Во втором слове старого имени «ask.<автор>-<тема>.md» стоит АВТОР, а цикл по папкам соседа
читал его как АДРЕСАТА у всех имён. Два письма AIA в общей папке старого обмена
«aia-stud-exchange» числились у них вопросами к ним самим, а с 27.09 их ответы на те же темы
гасили признак: проверка проходила по неверной причине («отвечен НАШИМ ответом ЕМУ ЖЕ»).
Разбор вида имени вынесен в функции уровня модуля, и приёмка берёт их ИЗ ИСХОДНИКА проверки
(через ast), а не переписывает. ⑱ наше письмо старого вида — «ours» · ⑲ ВСТРЕЧНЫЙ: старый
вопрос соседа в общей с нами папке — «history» · ⑳ новое имя судится как прежде · ㉑ ГРАНИЦА:
папка не наша и имя без дефиса · ㉒ без своего имени группы — прежнее правило · ㉓ ответ соседа
на наше старое письмо ищется У НЕГО. ㉔ — прогон проверки ЦЕЛИКОМ (--full) на КОПИИ контура
«aia» с папками соседа «atlas»; ㉕ ㉖ — две нарочные поломки, каждая на своей копии: ㉕ возвращает
прежнее поведение (наше письмо — вопрос к нам: ложное «отвечен НАШИМ ответом ЕМУ ЖЕ»), ㉖ — путь
AIA буквально (старый вопрос соседа судится: он среди вопросов без ответа).
⛔ ГРАНИЦА ЭТОЙ ЧАСТИ, НАЗВАНА ПРЯМО: ㉔ мерит на ПОДСТАВНЫХ именах и ОДНОЙ связи (мы «aia»,
сосед «atlas»). Живые папки AIA и их 11 старых вопросов приёмка не читает: тот замер (04.10
21:47 UTC) остаётся замером по именам файлов. Ветку «у соседа своих папок нет» эта часть не
судит: её правило не менялось. Сличение идёт по ИМЕНАМ тем — полон ли ответ, машина не знает.
Базу соседа проверка не открывает (из записи о соседе берётся только каталог его контура, а
дальше читаются файлы его папок), поэтому на копии её нет. Возраст вопросов задан временем файла
(30 суток назад): свежие в «без ответа» не попадают (окно 48 ч).

═══ ㉗–㉙ — ДОРАБОТКА КАРТОЧКИ #673 (04.10 22:21 UTC, слово владельца)
Признаки «наше письмо» и «история» не смотрели, в какой папке лежит письмо. Вопрос, по ошибке
названный соседом с дефисом в его новой исходящей («atlas-aia/ask.aia-тема.md» у контура «aia»),
стал бы нашим письмом и ушёл из-под суда, а до #673 он судился. Теперь старые правила имён
действуют только в общей папке старого обмена (функция `_is_shared_old_box`: наше имя — отдельное
слово в имени папки, и имя НЕ начинается с «<сосед>-»). ㉗ вопрос с дефисом в исходящей соседа —
«to_us» · ㉘ ВСТРЕЧНЫЙ: старое имя соседа там же — «not_ours», не «история» · ㉙ НАРОЧНАЯ ПОЛОМКА:
без условия «не начинается с <сосед>-» падают ровно ㉗ ㉘ ㉚, ⑱–㉓ держатся.
㉚–㉛ — ВТОРОЕ МЕСТО ВЫЗОВА того же признака (находка проверки чужой рукой 04.10): поиск ответов
соседа на наше старое письмо (`_neighbor_answers_to_our_old`) тоже зовёт `_is_shared_old_box`, а
ни один случай этого не судил — поломка там оставляла ㉗–㉙ зелёными. ㉚ старый ответ соседа
«answer.<сосед>-<тема>.md» в его исходящей ответом на наше старое письмо не засчитан · ㉛ НАРОЧНАЯ
ПОЛОМКА: в этом месте прежнее условие (67874cb: «наше имя — слово в имени папки») — падает ровно ㉚.
Прогон копии под поломкой ㉙ — НАСТОЯЩИЙ (прежде он держался по построению: на стенде ㉔ не было
письма, которое поломка могла задеть): к стенду добавлен вопрос с дефисом в исходящей соседа
«atlas-aia/ask.aia-дефис.md»; на исправной проверке он среди «без ответа» (контрольный прогон
«good-c»), под поломкой пропадает оттуда и становится «нашим письмом». Стенд самого ㉔ не тронут.
⛔ ГРАНИЦА: таких имён в живых папках сегодня нет (все вопросы atlas-aia и atlas-tapas — с тремя
точками и больше); ㉗–㉛ судят функции на подставных именах и прогон копии под поломкой ㉙.
㉛ судит только функцию: на стенде ㉔ старого ответа в исходящей соседа нет, и итог прогона
считает письма с найденным ответом, а не число ответов — лишний ответ строку не меняет.

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
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
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


OLD_NAME_FUNCTIONS = ("_old_name_by", "_is_shared_old_box", "_neighbor_ask_kind",
                      "_neighbor_answers_to_our_old")
# ㉙: признак общей папки без условия «не начинается с <сосед>-» — каждая папка с нашим именем общая
SHARED_BOX_BREAK = ('    return not (group and box_name.startswith(group + "-"))', "    return True")
# ㉛: во втором месте вызова — прежнее условие 67874cb («наше имя — слово в имени папки»)
ANSWERS_SITE_BREAK = ("elif len(parts) == 3 and _is_shared_old_box(box.name, group, our_group):",
                      'elif len(parts) == 3 and our_group in box.name.split("-"):')
# ㉙: вопрос с дефисом в исходящей соседа — на стенде ㉔ его нет, без него прогон под поломкой
#    держался бы по построению. (путь от каталога соседа, первая строка, вопрос ли)
DASH_QUESTION = (("atlas-aia", "ask.aia-дефис.md"),
                 "2026-09-07 10:02 UTC · пишет **COORD контура Atlas**: его вопрос нам с дефисом в имени.", True)
DASH_WAITING = "· atlas: ask.aia-дефис.md — лежит"


def old_name_unit_verdicts(ask_kind, answers_to_our_old, old_boxes, outbox_boxes) -> list:
    """Ожидания ⑱–㉓, ㉗, ㉘ и ㉚ к функциям разбора вида имени — для нарочных поломок ㉙ и ㉛, где
    те же вызовы делаются над функциями из ПОДМЕНЁННОГО исходника. Вызовы и ожидания — те же, что в
    случаях ниже; поломки сверяют эту таблицу с живыми функциями и называют расхождение, если оно есть.
    → [(номер случая, выполнено ли)]."""
    return [
        ("⑱", ask_kind("ask.aia-тема.md", "aia-stud-exchange", "atlas", "aia") == "ours"),
        ("⑲", ask_kind("ask.atlas-aia-тема.md", "aia-stud-exchange", "atlas", "aia") == "history"),
        ("⑳", ask_kind("ask.aia.тема.md", "atlas-aia", "atlas", "aia") == "to_us"
              and ask_kind("ask.tapas.тема.md", "atlas-tapas", "atlas", "aia") == "not_ours"),
        ("㉑", ask_kind("ask.atlas-тема.md", "atlas-tapas", "atlas", "aia") == "not_ours"
              and ask_kind("ask.aiax-тема.md", "aia-stud-exchange", "atlas", "aia") != "ours"),
        ("㉒", ask_kind("ask.aia-тема.md", "aia-stud-exchange", "atlas", "") == "to_us"),
        ("㉓", answers_to_our_old("ask.aia-тема.md", old_boxes, "atlas", "aia")
              == ["atlas-aia/answer.aia.тема.md"]),
        ("㉗", ask_kind("ask.aia-тема.md", "atlas-aia", "atlas", "aia") == "to_us"),
        ("㉘", ask_kind("ask.atlas-тема.md", "atlas-aia", "atlas", "aia") == "not_ours"),
        ("㉚", answers_to_our_old("ask.aia-тема.md", outbox_boxes, "atlas", "aia") == []),
    ]


def module_function_namespace(names: tuple, source: str = "") -> dict:
    """Функции уровня модуля с этими именами — ИЗ ИСХОДНИКА проверки через ast, а не
    переписанные здесь (переписанная копия зелена к себе самой). Отсутствующих в словаре нет:
    вызывающий сам называет, чего не нашлось. source — подменённый текст; по умолчанию живой."""
    text = source or SOURCE_TEXT
    namespace: dict = {"Path": Path}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(ast.get_source_segment(text, node), namespace)    # noqa: S102 — свой же исходник
    return namespace


def lines_with(output: str, *needles: str) -> list:
    """Строки вывода (без краевых пробелов), где встретились ВСЕ подстроки."""
    return [ln.strip() for ln in output.splitlines() if all(n in ln for n in needles)]


def neighbor_old_names_run(stand: Path, tag: str, break_from: str = "", break_to: str = "",
                           extra_letters: tuple = ()) -> tuple:
    """Прогон проверки целиком (--full) на КОПИИ контура «aia» с папками соседа «atlas» (㉔–㉖).

    Копия — как в seeded_bridge_run: инструменты контура + снимок его базы (живая только
    читается). В базе копии имя группы «aia» и ОДНА связь — с соседом «atlas», чей каталог лежит
    на стенде (nb/…); в настоящие соседние контуры проверка не ходит. Саму базу соседа проверка
    не открывает: из записи о нём берётся только каталог его контура, дальше читаются файлы
    его папок, — поэтому её на стенде нет.
    Папки соседа: общая старого обмена «aia-stud-exchange» (наше письмо старого вида и его старый
    вопрос) и его исходящая «atlas-aia» (его ответ нам и его новый вопрос без ответа). Наша
    исходящая «aia-atlas» несёт наш ответ ему по той же теме, что и наше старое письмо: он-то до
    правки и давал ложное «отвечен НАШИМ ответом ЕМУ ЖЕ». Вопросам выставлено время файла
    «30 суток назад»: свежие в «без ответа» не попадают (окно 48 ч).
    break_from/break_to — нарочная поломка в КОПИИ guard-all.py: подстрока должна встретиться
    ровно один раз, иначе поломка не применилась и прогон не делается.
    extra_letters — письма СВЕРХ стенда ㉔ в папках соседа: ((папка, имя), первая строка, вопрос ли);
    стенд самого ㉔ ими не меняется (㉙ кладёт их только в свои прогоны «good-c» и «break-c»).
    → (применена ли поломка, вывод проверки: stdout + stderr)."""
    live = mezo_paths.container_root(__file__) / ".mezosync"
    root = stand / tag / "own"
    shutil.copytree(live / "scripts", root / ".mezosync" / "scripts")
    if break_from:
        copy_path = root / ".mezosync" / "scripts" / "guard-all.py"
        text = copy_path.read_bytes().decode("utf-8")
        if text.count(break_from) != 1:
            return False, ""
        copy_path.write_bytes(text.replace(break_from, break_to).encode("utf-8"))
    neighbor = stand / tag / "nb"
    db = mezo_stand.snapshot_db(live / "mezosync.db", root / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO meta (key, value) VALUES ('group_name', 'aia') "
                "ON CONFLICT(key) DO UPDATE SET value = 'aia'")
    con.execute("DELETE FROM cross_links")
    con.execute("INSERT INTO cross_links (source_group, target_group, target_db_path) "
                "VALUES ('aia', 'atlas', ?)", (str(neighbor / ".mezosync" / "mezosync.db"),))
    con.commit()
    con.close()
    their_bridges = neighbor / "repo" / ".mezosync" / "bridges"
    letters = [
        (their_bridges / "aia-stud-exchange" / "ask.aia-проба.md", True,
         "2026-09-06 02:40 UTC · пишет **COORD контура Aia**: наше письмо старого вида."),
        (their_bridges / "aia-stud-exchange" / "ask.atlas-aia-старое.md", True,
         "2026-09-06 02:41 UTC · пишет **COORD контура Atlas**: его старый вопрос в общей папке."),
        (their_bridges / "atlas-aia" / "answer.aia.проба.md", False,
         "2026-09-07 10:00 UTC · пишет **COORD контура Atlas**: его ответ нам."),
        (their_bridges / "atlas-aia" / "ask.aia.живой-вопрос.md", True,
         "2026-09-07 10:01 UTC · пишет **COORD контура Atlas**: его новый вопрос нам."),
        (root / "bridges" / "aia-atlas" / "answer.atlas.проба.md", False,
         "2026-09-08 09:00 UTC · пишет **PROTO контура Aia**: наш ответ ему по той же теме."),
    ] + [(their_bridges / box_name / file_name, is_question, first_line)
         for (box_name, file_name), first_line, is_question in extra_letters]
    long_ago = time.time() - 30 * 86400
    for path, is_question, first_line in letters:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(first_line + "\nтело письма\n", encoding="utf-8")
        if is_question:
            os.utime(path, (long_ago, long_ago))
    r = subprocess.run([sys.executable, str(root / ".mezosync" / "scripts" / "guard-all.py"), "--full"],
                       capture_output=True, text=True, encoding="utf-8", timeout=900,
                       env=mezo_stand.stand_env(root))       # копия — контур, где лежит её guard-all
    return True, (r.stdout or "") + (r.stderr or "")


def judge_old_names(output: str) -> list:
    """Шесть ожиданий случая ㉔ к выводу прогона. Каждое — (ключ, что ждём, выполнено ли, что найдено).

    Первое — предпосылка: прогон дошёл до конца раздела моста. Без неё «строки нет» в остальных
    ожиданиях ничего бы не значило: оборванный прогон молчит обо всём."""
    def shown(hits: list) -> str:
        if not hits:
            return "строк нет"
        return f"«{hits[0][:150]}»" + (f" (и ещё {len(hits) - 1})" if len(hits) > 1 else "")

    reached = lines_with(output, "📤 мост: наших собственных писем")
    false_answered = lines_with(output, "«ask.aia-проба.md» отвечен НАШИМ ответом ЕМУ ЖЕ")
    own_old = lines_with(output, "НАШЕ письмо старого вида", "atlas-aia/answer.aia.проба.md")
    counts = lines_with(output, "наших писем 1 (ответ соседа у него найден: 1), его вопросов 1")
    their_old = lines_with(output, "ask.atlas-aia-старое.md")
    live_question = lines_with(output, "· atlas: ask.aia.живой-вопрос.md — лежит")
    return [
        ("reached", "прогон дошёл до конца раздела моста", bool(reached), shown(reached)),
        ("no_false_answered", "наше письмо не «отвечено НАШИМ ответом ЕМУ ЖЕ»",
         not false_answered, shown(false_answered)),
        ("own_old_named", "наше письмо старого вида названо, ответ соседа у него найден",
         bool(own_old), shown(own_old)),
        ("counts", "итог: наших писем 1 (ответ найден 1), его вопросов 1", bool(counts), shown(counts)),
        ("their_old_not_waiting", "его старый вопрос не среди «без ответа»", not their_old, shown(their_old)),
        ("live_question_waiting", "контроль: его новый вопрос без ответа по-прежнему судится",
         bool(live_question), shown(live_question)),
    ]


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

    # ── ⑱–㉖ КАРТОЧКА #673 (04.10, находка контура AIA, их карточка 147): ВИД ИМЕНИ ВОПРОСА В
    #    ПАПКАХ СОСЕДА. Второе слово старого имени — АВТОР, нового — АДРЕСАТ. Функции разбора
    #    берутся ИЗ ИСХОДНИКА проверки (уровень модуля, через ast), а не переписаны здесь.
    old_ns = module_function_namespace(OLD_NAME_FUNCTIONS)
    missing = [fn for fn in OLD_NAME_FUNCTIONS if fn not in old_ns]
    if missing:
        record_case("⑱–㉓ разбор вида имени берётся из исходника проверки", False,
                    f"в исходнике нет функций уровня модуля: {', '.join(missing)} — судить нечем")
    else:
        ask_kind = old_ns["_neighbor_ask_kind"]
        answers_to_our_old = old_ns["_neighbor_answers_to_our_old"]
        own_old_kind = ask_kind("ask.aia-тема.md", "aia-stud-exchange", "atlas", "aia")
        record_case("⑱ наше письмо старого вида «ask.<мы>-<тема>.md» в папке соседа — «ours», не вопрос к нам",
                    own_old_kind == "ours",
                    f"признано: {own_old_kind} — второе слово старого имени автор, а не адресат")
        their_old_kind = ask_kind("ask.atlas-aia-тема.md", "aia-stud-exchange", "atlas", "aia")
        record_case("⑲ ВСТРЕЧНЫЙ: старый вопрос соседа в общей с нами папке — «history», не судится",
                    their_old_kind == "history",
                    f"признано: {their_old_kind} — иначе ⑱ зеленел бы от «ours для всего»")
        new_to_us = ask_kind("ask.aia.тема.md", "atlas-aia", "atlas", "aia")
        new_not_ours = ask_kind("ask.tapas.тема.md", "atlas-tapas", "atlas", "aia")
        record_case("⑳ новое имя «ask.<кому>.<тема>.md» судится как прежде: к нам — «to_us», к третьему — «not_ours»",
                    new_to_us == "to_us" and new_not_ours == "not_ours",
                    f"к нам: {new_to_us} · к третьему: {new_not_ours}")
        foreign_box_kind = ask_kind("ask.atlas-тема.md", "atlas-tapas", "atlas", "aia")
        no_dash_kind = ask_kind("ask.aiax-тема.md", "aia-stud-exchange", "atlas", "aia")
        record_case("㉑ ГРАНИЦА: старое имя в чужой папке — «not_ours», а автор «aiax» без дефиса — не «ours»",
                    foreign_box_kind == "not_ours" and no_dash_kind != "ours",
                    f"чужая папка: {foreign_box_kind} · «aiax-…»: {no_dash_kind} "
                    "(нужен дефис после имени: иначе контур «aia» присвоил бы письма «aiax-…»)")
        no_group_kind = ask_kind("ask.aia-тема.md", "aia-stud-exchange", "atlas", "")
        record_case("㉒ без своего имени группы различать нечего — прежнее правило, вопрос судится («to_us»)",
                    no_group_kind == "to_us", f"признано: {no_group_kind}")
        old_exchange = stand / "old-answers"
        old_boxes = []
        for box_name, answer_name in (("atlas-aia", "answer.aia.тема.md"),
                                      ("aia-stud-exchange", "answer.atlas-aia-другое.md"),
                                      ("atlas-tapas", "answer.tapas.тема.md")):
            box = old_exchange / box_name
            box.mkdir(parents=True)
            (box / answer_name).write_text("ответ\n", encoding="utf-8")
            old_boxes.append(box)
        old_answers = answers_to_our_old("ask.aia-тема.md", old_boxes, "atlas", "aia")
        record_case("㉓ ответ соседа на наше старое письмо найден У НЕГО: ровно «answer.aia.тема.md» его исходящей",
                    old_answers == ["atlas-aia/answer.aia.тема.md"],
                    f"найдено: {old_answers} — другая тема в общей папке и ответ третьему не засчитаны")
        # ㉗ ㉘ ДОРАБОТКА карточки #673 (04.10 22:21 UTC): старые правила имён — только в общей папке старого обмена
        dash_in_outbox = ask_kind("ask.aia-тема.md", "atlas-aia", "atlas", "aia")
        record_case("㉗ вопрос с дефисом «ask.<мы>-<тема>.md» в ИСХОДЯЩЕЙ соседа «atlas-aia» судится, как до #673 («to_us»)",
                    dash_in_outbox == "to_us",
                    f"признано: {dash_in_outbox} — папка «<сосед>-…» его исходящая, не общая папка старого обмена")
        their_dash_in_outbox = ask_kind("ask.atlas-тема.md", "atlas-aia", "atlas", "aia")
        record_case("㉘ ВСТРЕЧНЫЙ: «ask.<сосед>-<тема>.md» в его исходящей — «not_ours», не «history»",
                    their_dash_in_outbox == "not_ours",
                    f"признано: {their_dash_in_outbox} — иначе ㉗ зеленел бы от «в исходящей соседа всё к нам»")
        # ㉚ ВТОРОЕ МЕСТО ВЫЗОВА признака общей папки — поиск ответов соседа на наше старое письмо
        outbox_box = stand / "outbox-old-answer" / "atlas-aia"
        outbox_box.mkdir(parents=True)
        (outbox_box / "answer.atlas-тема.md").write_text("ответ\n", encoding="utf-8")
        outbox_boxes = [outbox_box]
        outbox_answers = answers_to_our_old("ask.aia-тема.md", outbox_boxes, "atlas", "aia")
        record_case("㉚ старый ответ «answer.<сосед>-<тема>.md» в ИСХОДЯЩЕЙ соседа «atlas-aia» ответом на наше "
                    "старое письмо не засчитан",
                    outbox_answers == [],
                    f"найдено: {outbox_answers} — второе место вызова признака общей папки: старые правила "
                    "имён и тут только в общей папке старого обмена")

    # ㉔ прогон проверки ЦЕЛИКОМ на копии контура «aia»: четыре письма в папках соседа и наш ответ ему
    applied, good_output = neighbor_old_names_run(stand, "good")
    good_verdict = judge_old_names(good_output)
    record_case("㉔ прогон на копии контура «aia»: наше старое письмо не вопрос к нам, его старый вопрос не судится, "
                "его новый вопрос судится",
                applied and all(ok for _, _, ok, _ in good_verdict),
                " · ".join(f"{'✓' if ok else '✗'} {tag}: {found}" for _, tag, ok, found in good_verdict))

    # ㉕ НАРОЧНАЯ ПОЛОМКА А — прежнее поведение: наше письмо старого вида разбирается как вопрос к нам
    applied_a, break_a_output = neighbor_old_names_run(stand, "break-a", '        return "ours"',
                                                       '        return "to_us"')
    if applied_a:
        verdict_a = judge_old_names(break_a_output)
        by_key_a = {key: ok for key, _, ok, _ in verdict_a}
        fell_a = [tag for _, tag, ok, _ in verdict_a if not ok]
        held_a = [tag for _, tag, ok, _ in verdict_a if ok]
        record_case("㉕ ПОЛОМКА: «ours» → «to_us» возвращает ложное «отвечен НАШИМ ответом ЕМУ ЖЕ» и красит ㉔",
                    by_key_a["reached"] and not by_key_a["no_false_answered"],
                    f"под поломкой пали: {fell_a} · устояли: {held_a}")
    else:
        record_case("㉕ ПОЛОМКА: «ours» → «to_us» возвращает ложное «отвечен НАШИМ ответом ЕМУ ЖЕ» и красит ㉔",
                    False, "поломка не применилась: подстрока не встретилась в исходнике ровно один раз")

    # ㉖ НАРОЧНАЯ ПОЛОМКА Б — путь AIA буквально: старый вопрос соседа в общей папке судится как вопрос к нам
    applied_b, break_b_output = neighbor_old_names_run(stand, "break-b", '        return "history"',
                                                       '        return "to_us"')
    if applied_b:
        verdict_b = judge_old_names(break_b_output)
        by_key_b = {key: ok for key, _, ok, _ in verdict_b}
        waiting_line = lines_with(break_b_output, "· atlas: ask.atlas-aia-старое.md — лежит")
        fell_b = [tag for _, tag, ok, _ in verdict_b if not ok]
        held_b = [tag for _, tag, ok, _ in verdict_b if ok]
        record_case("㉖ ПОЛОМКА: «history» → «to_us» ставит его старый вопрос среди «без ответа» и красит ㉔",
                    by_key_b["reached"] and bool(waiting_line),
                    (f"в списке: «{waiting_line[0]}»" if waiting_line else "его старого вопроса в списке нет")
                    + f" · пали: {fell_b} · устояли: {held_b}")
    else:
        record_case("㉖ ПОЛОМКА: «history» → «to_us» ставит его старый вопрос среди «без ответа» и красит ㉔",
                    False, "поломка не применилась: подстрока не встретилась в исходнике ровно один раз")

    # Таблица ожиданий для поломок ㉙ и ㉛ сперва сверяется с живыми функциями: разойдись она с
    # случаями выше — поломки судили бы не те вызовы.
    if not missing:
        live_table = old_name_unit_verdicts(ask_kind, answers_to_our_old, old_boxes, outbox_boxes)
        table_diverged = [n for n, ok in live_table if not ok]
        diverged_note = (f" · ⚠️ таблица ожиданий разошлась с живыми функциями: {table_diverged}"
                         if table_diverged else "")

    # ㉙ НАРОЧНАЯ ПОЛОМКА В — признак общей папки без условия «не начинается с <сосед>-»: исходящая
    #    соседа «atlas-aia» становится общей ОБОИМ местам вызова. Падать обязаны ровно ㉗ ㉘ ㉚; ⑱–㉓ —
    #    держаться. Прогон копии — со стендом ㉔ и вопросом с дефисом в исходящей соседа: на исправной
    #    проверке он среди «без ответа» (контроль «good-c»), под поломкой — «наше письмо».
    name_29 = ("㉙ ПОЛОМКА: без условия «не начинается с <сосед>-» падают ровно ㉗ ㉘ ㉚, а на прогоне копии "
               "вопрос с дефисом в исходящей соседа уходит из «без ответа» в «наши письма»")
    if missing:
        record_case(name_29, False, f"в исходнике нет функций уровня модуля: {', '.join(missing)} — судить нечем")
    elif SOURCE_TEXT.count(SHARED_BOX_BREAK[0]) != 1:
        record_case(name_29, False, "поломка не применилась: подстрока не встретилась в исходнике ровно один раз")
    else:
        broken_ns = module_function_namespace(OLD_NAME_FUNCTIONS, SOURCE_TEXT.replace(*SHARED_BOX_BREAK))
        broken_table = old_name_unit_verdicts(broken_ns["_neighbor_ask_kind"],
                                              broken_ns["_neighbor_answers_to_our_old"], old_boxes, outbox_boxes)
        fell_c = [n for n, ok in broken_table if not ok]
        _, good_c_output = neighbor_old_names_run(stand, "good-c", extra_letters=(DASH_QUESTION,))
        good_c_fell = [tag for _, tag, ok, _ in judge_old_names(good_c_output) if not ok]
        dash_good = lines_with(good_c_output, DASH_WAITING)
        applied_c, break_c_output = neighbor_old_names_run(stand, "break-c", *SHARED_BOX_BREAK,
                                                           extra_letters=(DASH_QUESTION,))
        run_fell_c = [tag for _, tag, ok, _ in judge_old_names(break_c_output) if not ok]
        dash_broken = lines_with(break_c_output, DASH_WAITING)
        counts_tag = "итог: наших писем 1 (ответ найден 1), его вопросов 1"
        record_case(name_29,
                    not table_diverged and fell_c == ["㉗", "㉘", "㉚"]
                    and not good_c_fell and bool(dash_good)
                    and applied_c and not dash_broken and run_fell_c == [counts_tag],
                    f"под поломкой пали: {fell_c} · контроль «good-c»: "
                    + (f"«{dash_good[0]}»" if dash_good else "вопроса с дефисом среди «без ответа» НЕТ")
                    + (f", пали {good_c_fell}" if good_c_fell else ", шесть ожиданий ㉔ держатся")
                    + " · под поломкой: "
                    + ("вопрос с дефисом всё ещё среди «без ответа»" if dash_broken
                       else "вопроса с дефисом среди «без ответа» нет")
                    + f", пали {run_fell_c}"
                    + ("" if applied_c else " · ⚠️ поломка в копии проверки не применилась")
                    + diverged_note)

    # ㉛ НАРОЧНАЯ ПОЛОМКА Г — во втором месте вызова (поиск ответов соседа на наше старое письмо)
    #    прежнее условие 67874cb «наше имя — слово в имени папки». Падать обязан ровно ㉚.
    name_31 = "㉛ ПОЛОМКА: во втором месте вызова прежнее условие 67874cb — падает ровно ㉚"
    if missing:
        record_case(name_31, False, f"в исходнике нет функций уровня модуля: {', '.join(missing)} — судить нечем")
    elif SOURCE_TEXT.count(ANSWERS_SITE_BREAK[0]) != 1:
        record_case(name_31, False, "поломка не применилась: подстрока не встретилась в исходнике ровно один раз")
    else:
        broken_ns_d = module_function_namespace(OLD_NAME_FUNCTIONS, SOURCE_TEXT.replace(*ANSWERS_SITE_BREAK))
        fell_d = [n for n, ok in old_name_unit_verdicts(broken_ns_d["_neighbor_ask_kind"],
                                                         broken_ns_d["_neighbor_answers_to_our_old"],
                                                         old_boxes, outbox_boxes) if not ok]
        record_case(name_31, not table_diverged and fell_d == ["㉚"],
                    f"под поломкой пали: {fell_d}" + diverged_note)

    failed = [case_name for case_name, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 10 (② ③ ⑧ ⑩ ⑭ ⑲ ⑳ ㉑ ㉒ ㉘), ОБРАТНЫХ ХОДОВ 2"
          " (⑪ ⑬) и НАРОЧНЫХ ПОЛОМОК 6 (⑮ ⑰ ㉕ ㉖ ㉙ ㉛); ⑥ добавлен по границе @COORD, ⑦–⑰ — карточка #665,"
          " ⑱–㉛ — карточка #673 (㉗–㉛ — доработка 04.10 22:21 UTC)")
    print("⚖️ Признак берётся ИЗ ЖИВОГО инструмента, а не переписан здесь: переписанная")
    print("   копия зелена к себе самой и о предмете не говорит ничего.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
