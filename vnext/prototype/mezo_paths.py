# -*- coding: utf-8 -*-
"""
mezo_paths.py — ПРОТОТИП механизма R15a: инструмент координации не зависит от рабочего каталога.

ЗАЧЕМ (полевые факты 2026-07-25, не теория):
  · CORE #2669  — `write-message.py` дважды упал `can't open file`, потому что предыдущая команда
    его же работы сделала `cd` в подкаталог репозитория.
  · ING #2673   — тот же класс; у ING он ЗАПИСАН предупреждением в слепке — и протёк ДВАЖДЫ за смену.
  · COORD #2683 — укусил его через 4 минуты после того, как он внёс класс в план как «известную боль».
  ⇒ Три независимых срабатывания за одну смену. Дисциплина здесь доказанно не держит.

ЧТО ЗАКРЫВАЕТ, А ЧТО НЕТ — граница названа честно:
  ✅ ЗАКРЫВАЕТ поиск БД и ресурсов: скрипт находит их от СВОЕГО расположения, а не от CWD.
     Сюда же — ТИХИЙ подкласс: относительный путь к БД при смещённом CWD заставляет
     `sqlite3.connect` МОЛЧА создать пустую БД-фантом (ровно из-за этого заведён гард ⑤;
     в живом контуре такой дефолт до сих пор стоит в `dashboard.py:410`).
     Тихий отказ дороже громкого: громкий стоит повторного вызова, тихий — пяти суток фантома.
  ⛔ НЕ ЗАКРЫВАЕТ запуск самого скрипта относительным путём (`python .mezosync/scripts/x.py`):
     интерпретатор ищет файл ДО того, как этот код начнёт исполняться. Изнутри скрипта это
     нерешаемо в принципе. Вторая половина — R15b, гард `guard-relative-invocations.py`:
     он лечит ИСТОЧНИК относительной формы (канон и памяти), а не память ролей.

Использование в скрипте:
    from mezo_paths import resolve_db
    ap.add_argument("--db", default=None)      # больше не required
    db = resolve_db(args.db, __file__)

ФАЙЛ ПУТЕЙ КОНТУРА (карточка #677, этап Э3; решение владельца В3 а′, 2026-10-05 10:53 UTC):
пути, которые у каждого контура свои, лежат в ОДНОМ файле <контейнер>/.mezosync/local/paths.json
(JSON: «ключ → путь»; относительный путь считается от контейнера). Читает его одна функция:
    from mezo_paths import local_path
    res = local_path("mirror_repo", __file__)      # → LocalPath: исход, путь, слова, подсказка
У неё четыре РАЗНЫХ исхода (см. local_path): объявлено · не объявлено · файла путей нет ·
файл не читается. Прежние места (строки local.paths и ключи mirror_repo / template_checkout /
disk_layer_tool в таблице meta) как ЗНАЧЕНИЕ больше не читаются: их переносит шаг
migrations/20261005-local-paths-file.py.

ПЕРЕЧЕНЬ КЛЮЧЕЙ ФАЙЛА ПУТЕЙ (читает каждый своё место; читатель один — local_path):
    container · template · template_checkout · mirror_repo · disk_layer_tool · annex_dir ·
    coordination_dir · generated_dir · prompts_dir · spa_src
        — что каждый значит и кто его читает, названо в шапке шага
          migrations/20261005-local-paths-file.py (этот шаг и вписывает их в файл путей контура);
    prototype_install_dir   НЕОБЯЗАТЕЛЬНЫЙ (карточка #678): второй каталог установки — туда update-tools.py
        ставит файлы vnext/prototype пакета, которые УЖЕ там лежат (у контура Atlas это
        <контейнер>/vnext-tools). Нет ключа — update-tools.py ведёт себя как прежде. Ключ не
        вписывается шагом переноса: его объявляет сам контур, у которого такой каталог есть.
"""
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote
import json
import os
import sqlite3
import sys

DB_NAME = "mezosync.db"


# ═══ ПУСТОЙ ФАЙЛ БАЗЫ — НЕ БАЗА (починка (б), этап Э4 карточки #678, 2026-10-06) ═════════════════
# Признак «файл mezosync.db есть» не отличал базу от пустышки нулевой длины. Пустышку оставляет
# sqlite3.connect по несуществующему пути: так 20.08 в корне основного клона пакета появился
# mezosync.db в 0 байт, и поиск корня принимал корень клона за корень мезосинка, а template_root —
# за живой контур вместо пакета. Замер 2026-10-06: четыре приёмки пакета в основном клоне
# провалились не по своей причине (две приёмки памяти, bite-actor-role-hint, bite-memory-volume ①–③).
# ⚖️ Почему «не пуст», а не «есть таблицы»: признак проверяется на каждом шаге подъёма, а открыть
# базу ради него дорого и опасно — открытие несуществующего пути само рождает пустышку. Пустой
# файл — база без единой страницы, контура в нём нет по построению. Живой контур пустым не бывает:
# в режиме WAL заголовок пишется в момент включения режима (замер 2026-10-06 13:13 UTC: 0 → 4096
# байт сразу после PRAGMA journal_mode=WAL, ещё до первой таблицы).
# ⛔ Граница: абсолютный --db на пустой файл resolve_db по-прежнему принимает — путь назван
# вызывающим явно, это не поиск. Других читателей признака вне этого файла починка не трогает.
def _is_db_file(path) -> bool:
    """Файл базы, а не пустышка: существует, это файл, и он не пуст. Беда чтения — «не база»."""
    try:
        path = Path(path)
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _empty_db_note(walk_from, exact=()) -> str:
    """Строки отказа о пустых файлах mezosync.db, которые поиск пропустил: вверх от walk_from
    и в каталогах exact (сам каталог и его .mezosync). Нет таких — пустая строка.
    Беда чтения — молчание: подсказка не вправе уронить отказ, которому помогает."""
    seen = []
    try:
        start = Path(walk_from).resolve()
        dirs = [*(start, *start.parents), *(Path(d) for d in exact if d is not None)]
        for d in dirs:
            for f in (d / DB_NAME, d / ".mezosync" / DB_NAME):
                if f not in seen and f.is_file() and f.stat().st_size == 0:
                    seen.append(f)
    except OSError:
        pass
    return "".join(f"     ⚠️ пустой файл {f.as_posix()} (0 байт) — это не база, пропущен: такой "
                   "оставляет подключение к несуществующему пути, данных в нём нет.\n"
                   for f in seen[:3])


# ═══ НУЖЕН ЛИ ВЫЗЫВАЮЩЕМУ ВТОРОЙ ЗАМОК — ЭТО ВЫЧИСЛЯЕТСЯ, А НЕ УГАДЫВАЕТСЯ ═══
# Врезано 2026-09-06 по приёмке @COORD карточки #575 (её разбор — событие карточки,
# 2026-09-06 04:48 UTC). Прежде здесь и в тексте приёмки стояло основание «в точке отказа
# неизвестно, нужен ли вызывающему каталог группы». @COORD проверила своей рукой:
# ИЗВЕСТНО. В точке отказа есть script_file — путь вызывающего, а свойство выводится
# обходом файлов-соседей, который уже живёт в контуре (neighbours_of в mezo_stand.py).
# 📏 Её замер: четыре инструмента за 0,07 с ⇒ ~0,02 с на один.
#
# ⚖️ ЗАКОННЫЙ ДОВОД ПРОТИВ — И ПОЧЕМУ ОН СНЯТ ПОСТРОЕНИЕМ, А НЕ ОБЕЩАНИЕМ.
# Довод @COORD: разбор дерева кода в пути ОТКАЗА хрупок — там уже что-то сломано,
# и падение разбора превратит понятный отказ в трассировку. Ответ построением:
#   · вся работа стои́т внутри try/except Exception (обёртка _нужен_каталог_группы);
#   · ЛЮБАЯ беда — нечитаемый файл, сломанный синтаксис, отнятые права, чужой мусор
#     в каталоге — отвечает None, а None печатает ПОЛНЫЙ текст, тот самый, что
#     печатался до этой правки;
#   ⇒ худший исход разбора равен вчерашнему поведению, а не трассировке. Не обещание:
#     случай ⑨ приёмки bite-two-locks.py ломает разбор нарочно и судит вывод.
#
# 🪤 ПОЧЕМУ ИМЕНА СЧИТАЮТСЯ, А НЕ ПЕРЕЧИСЛЯЮТСЯ — поймано прогоном 2026-09-06, а не
# рассуждением. Первая редакция искала ровно четыре имени (container_root · live_db ·
# live_scripts · template_root) и разошлась с замером @COORD на ТРЁХ её инструментах
# из четырёх: read-messages.py · write-message.py · save-phoenix.py она назвала
# «не нужен», а он у них НУЖЕН. Причина настоящая: они зовут resolve_db, а resolve_db
# делает `import lease`, lease.check зовёт mezo_paths.live_db() — и каталог группы
# просит СОСЕД ЭТОГО ФАЙЛА, а не вызывающий. Поэтому заразные имена вычисляются
# замыканием по самому этому файлу и его соседям (_заразные_имена), и добавление
# новой такой цепочки не потребует править список руками.
_ИМЕНА_ВТОРОГО_ЗАМКА = ("container_root", "live_db", "live_scripts", "template_root")


def _просит_ли(дерево, имена) -> bool:
    """Ссылается ли разобранный файл хоть на одно из названных имён."""
    import ast
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Attribute) and узел.attr in имена:
            return True
        if isinstance(узел, ast.Name) and узел.id in имена:
            return True
        if isinstance(узел, ast.ImportFrom) and any(a.name in имена for a in узел.names):
            return True
    return False


def _заразные_имена(каталог_вызывающего=None) -> set:
    """Имена ИЗ ЭТОГО файла, у которых на пути стои́т каталог группы.

    Четыре базовых — по определению. Дальше замыкание: функция этого файла заразна,
    если её тело зовёт заразное имя ИЛИ импортирует соседа, который сам просит каталог
    группы. Так сюда попадает resolve_db (через lease.py) — та самая цепочка, которую
    перечисление руками потеряло. Разбираются только соседи, которые ЭТОТ файл вправду
    импортирует: их один, а не шесть десятков, — цена разбора остаётся копеечной.

    🪤 КАТАЛОГ ВЫЗЫВАЮЩЕГО ИДЁТ ПЕРВЫМ, И ЭТО НЕ ОФОРМЛЕНИЕ. Поймано красным случаем ⑩
    приёмки 2026-09-06: `import lease` внутри resolve_db разрешается по sys.path, а его
    первый элемент — каталог ЗАПУЩЕННОГО инструмента, а не каталог этого файла. У нас
    lease.py лежит в .mezosync/scripts и не лежит в vnext-tools ⇒ поиск «рядом с собой»
    отвечал по-разному на ОДИН И ТОТ ЖЕ инструмент, смотря чья копия помощника
    загружена. Ответ должен зависеть от того, КОГО судим, а не от того, кто судит.
    """
    import ast
    свой = Path(__file__).resolve()
    дерево = ast.parse(свой.read_text(encoding="utf-8"))
    имена = set(_ИМЕНА_ВТОРОГО_ЗАМКА)
    рядом = {}
    for место in (каталог_вызывающего, свой.parent):     # порядок = порядок sys.path
        if место is None:
            continue
        for p in Path(место).glob("*.py"):
            if p.resolve() != свой:
                рядом.setdefault(p.stem, p)
    импортируемые = set()
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Import):
            импортируемые |= {a.name.split(".")[0] for a in узел.names}
        elif isinstance(узел, ast.ImportFrom) and узел.level == 0 and узел.module:
            импортируемые.add(узел.module.split(".")[0])
    просящие = set()
    for имя in импортируемые & set(рядом):
        try:
            if _просит_ли(ast.parse(рядом[имя].read_text(encoding="utf-8")), имена):
                просящие.add(имя)
        except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
            continue                       # нечитаемый сосед — не повод падать в отказе
    функции = [у for у in дерево.body if isinstance(у, ast.FunctionDef)]
    росло = True
    while росло:                           # замыкание: цепочка длиной больше одного шага
        росло = False
        for ф in функции:
            if ф.name in имена:
                continue
            зовёт_соседа = any(
                (isinstance(у, ast.Import) and any(a.name.split(".")[0] in просящие
                                                   for a in у.names))
                or (isinstance(у, ast.ImportFrom) and у.module
                    and у.module.split(".")[0] in просящие)
                for у in ast.walk(ф))
            if зовёт_соседа or _просит_ли(ф, имена):
                имена.add(ф.name)
                росло = True
    return имена


def _разбор_нужды(script_file) -> bool:
    """Зовёт ли вызывающий — или кто-то из его файлов-соседей — заразное имя.

    Обход соседей транзитивный, как neighbours_of в mezo_stand.py: у нас read-messages.py
    тянет backlog_view.py, а тот ещё четверых, и просить каталог группы может любой из них.
    Ошибок НЕ ловит — их ловит обёртка; здесь только работа.
    """
    import ast
    инструмент = Path(script_file).resolve()
    свой = Path(__file__).resolve().stem   # сам этот файл — ПОСТАВЩИК имён, не потребитель:
    имена = _заразные_имена(инструмент.parent)   # иначе ответ был бы «нужен» всегда и всем
    рядом = {p.stem: p for p in инструмент.parent.glob("*.py")}
    очередь = [инструмент]
    видели = {инструмент.stem, свой}
    while очередь:
        дерево = ast.parse(очередь.pop().read_text(encoding="utf-8"))
        if _просит_ли(дерево, имена):
            return True
        for узел in ast.walk(дерево):
            if isinstance(узел, ast.Import):
                корни = [a.name.split(".")[0] for a in узел.names]
            elif isinstance(узел, ast.ImportFrom) and узел.level == 0 and узел.module:
                корни = [узел.module.split(".")[0]]
            else:
                continue
            for корень in корни:
                if корень in рядом and корень not in видели:
                    видели.add(корень)
                    очередь.append(рядом[корень])
    return False


def _нужен_каталог_группы(script_file):
    """True — вызывающему (или его соседу) нужен каталог группы, и за первым замком его
    ждёт второй. False — не нужен, хватит короткого совета. None — выяснить НЕ УДАЛОСЬ.
    None и True печатают ПОЛНЫЙ текст: умолчать о втором замке вправе только тот, кто
    ЗНАЕТ, что второго не будет. ⚖️ Обёртка — не украшение, а ответ на довод о хрупкости.

    ⛔ ЧЕГО РАЗБОР НЕ УМЕЕТ, названо прямо: имена, собранные на лету
    (getattr(mezo_paths, "live_" + x)), и соседа, лежащего в ДРУГОМ каталоге. В обоих
    случаях ответ будет «не нужен» ошибочно, и роль увидит короткий совет там, где
    полезнее полный. Цена ошибки в эту сторону — четыре строки, которых не хватило
    одному; в обратную — лекция всем, кому она не нужна.
    """
    try:
        return _разбор_нужды(script_file)
    except Exception:                      # noqa: BLE001 — см. разбор довода выше
        return None                        # отказ не вправе превратиться в трассировку


def mezo_root(script_file) -> Path:
    """Корень контейнера мезосинка — ближайший предок скрипта, где лежит mezosync.db.

    Подъём, а не жёсткое `parent.parent`: скрипт может лежать в scripts/, в scripts/guards/
    или быть вызван из копии-песочницы. Ищем ПРИЗНАК (файл БД), а не угадываем глубину —
    тот же принцип, по которому гард ⑤ судит фантомную БД по «ноль таблиц», а не по месту.
    """
    p = Path(script_file).resolve().parent
    for cand in (p, *p.parents):
        if _is_db_file(cand / DB_NAME):
            return cand
    # ⛔ ГРОМКО, А НЕ ТИХО — сведено 2026-08-20 06:10 UTC по заявке @PROTO (записка #3697 ②).
    # Прежде здесь стоял возврат «ожидаемого места» (parent.parent). Он выглядел безобидной
    # предметностью сообщения, а на деле отдавал ПУТЬ, по которому следующий же
    # `sqlite3.connect` МОЛЧА СОЗДАЁТ ПУСТУЮ БАЗУ. Не рассуждение: 19.08 18:53 UTC при прогоне
    # @PROTO в корне публичного образца так появился `mezosync.db` нулевой длины.
    # Цена названа в шапке этого же файла и была верна про соседний класс, но не исполнялась
    # здесь: «тихий отказ дороже громкого — громкий стоит повторного вызова, тихий — пяти
    # суток пустышки».
    # 🪤 ДО ОТКАЗА — ТЕ ЖЕ ИСТОЧНИКИ, ЧТО У container_root. Врезано 2026-08-21 22:26 UTC
    # по заявке @PROTO (записка #3713 ②), её замер воспроизведён мной перед правкой.
    # Прежде отказ НАЗЫВАЛ два выхода, и оба были мертвы: переменную среды читал только
    # container_root, а про «абсолютный --db» см. правку в resolve_db ниже. Роль выполняла
    # оба совета, получала тот же отказ слово в слово и решала, что сломан механизм,
    # а не её собственное место запуска. Больнее всего у lease.py — его зовут в первые
    # минуты жизни роли.
    # ⚖️ Развилка @PROTO решена в сторону «сделать советы правдой», а не «убрать их
    # из текста»: оба совета разумны, роль попробует их в любом случае, и текст без них
    # оставил бы читателя в тупике без выхода.
    # ⚖️ ПОРЯДОК ЗДЕСЬ ОСТАВЛЕН ПРЕЖНИМ (признак ПЕРВЫМ, среда следом) — и это решение, а не
    # недосмотр (карточка #677, Э3-Р4). Записанная норма для container_root — ① среда ② признак
    # ③ файл путей ④ отказ. Привести к ней mezo_root значило бы поставить MEZO_CONTAINER
    # ПЕРЕД признаком: инструмент, лежащий на стенде, послушал бы среду вызывающего и пошёл бы в
    # ЖИВУЮ базу, если приёмка не закрепила среду за стендом. Закрепляет её только сам запускающий
    # (mezo_stand.stand_env, а не mezo_stand.new), и реестр acceptance-env-debt.txt числом
    # называет, сколько вызовов её не закрепляют: замер 2026-10-05 — 139 вызовов в 87 файлах
    # (check-acceptance-env.py). Через эту функцию без --db ходят все, кто зовёт resolve_db:
    # 45 файлов (39 в .mezosync/scripts, 6 в vnext-tools), и напрямую default_db/mezo_root —
    # ещё 4 боевых инструмента (check-retired-mechanism.py, guard-all.py, guard-command-targets.py,
    # rule_status.py) и приёмка bite-two-locks. Урок 13.09: копия приёмки с MEZO_CONTAINER
    # живого записала meta Atlas. Пока долг в 139 вызовов не выплачен, порядок «среда первой»
    # здесь опаснее прежнего. Объявленный путь (ключ container файла путей) стоит ПОСЛЕ
    # признака и среды и сам стенд в живую базу не уведёт: файл путей стенда — свой.
    # Среда здесь по-прежнему ПОМОГАЕТ там, где признака нет (копия вне контейнера), и громко
    # отказывает, если названа, а базы по ней нет.
    env = os.environ.get("MEZO_CONTAINER")
    loc = local_path("container", script_file)
    loc_dir = loc.path if loc.outcome == LOCAL_DECLARED else None
    for src in (Path(env) if env else None, loc_dir):
        if src is None:
            continue
        # Обе раскладки, как и в отсечке template_root: база может лежать в подкаталоге
        # .mezosync контейнера или прямо в названном каталоге.
        for cand in (src / ".mezosync", src):
            if _is_db_file(cand / DB_NAME):
                return cand
    paths_file = _paths_file_for_advice(loc, script_file)
    sys.exit(
        f"ERR: корень мезосинка НЕ НАЙДЕН: файла {DB_NAME} нет ни в одном предке.\n"
        f"     Искал вверх от: {Path(script_file).resolve().parent}\n"
        + _empty_db_note(Path(script_file).resolve().parent,
                         exact=(Path(env) if env else None, loc_dir))
        + (f"     MEZO_CONTAINER={env} — задана, но {DB_NAME} по ней не найден.\n"
           if env else "")
        + (f"     файл путей: container={loc_dir} — задан, но {DB_NAME} по нему не найден.\n"
           if loc_dir else "")
        + (f"     {loc.words}\n" if loc.outcome == LOCAL_UNREADABLE else "")
        + (f"     ⚠️ {loc.hint}\n" if loc.hint else "")
        + f"     Прежде здесь молча возвращалось «ожидаемое место», и подключение к базе\n"
        f"     по этому пути создавало ПУСТУЮ базу вместо отказа.\n"
        f"     Выходы, и оба ПРОВЕРЕНЫ прогоном:\n"
        f"       · MEZO_CONTAINER=<путь до контейнера>  (или ключ container в файле\n"
        f"         путей {paths_file}) — снимает ОБА замка\n"
        f"       · позвать с АБСОЛЮТНЫМ --db <путь до {DB_NAME}> — снимает ТОЛЬКО ЭТОТ\n"
        # 🪤 ХВОСТ ПРО ВТОРОЙ ЗАМОК — ТОЛЬКО ТЕМ, КОГО ОН ЖДЁТ (карточка #575 ②,
        # приёмка @COORD 2026-09-06). Полный хвост нужен 72% инструментов; остальным
        # он лекция, а лекцию в отказе перестают читать целиком — вместе с выходами.
        # None (разбор не удался) уходит в ПОЛНЫЙ текст: умолчать о втором замке вправе
        # только тот, кто ЗНАЕТ, что второго не будет.
        + ("     ℹ️ Пометки «ОБА / ТОЛЬКО ЭТОТ» — про два замка механизма; ВАС второй\n"
           "     не касается: разбор этого инструмента и его файлов-соседей показал,\n"
           "     что каталог группы им не нужен."
           if _нужен_каталог_группы(script_file) is False else
           "     ⚠️ ЗА ЭТИМ ЗАМКОМ ЕСТЬ ВТОРОЙ, и второй выход до него не довозит.\n"
           "     Многим инструментам нужен не только файл базы, но и КАТАЛОГ ГРУППЫ —\n"
           "     сами они его не просят, а просит их сосед по каталогу. Тогда следом\n"
           "     придёт отказ «контейнер группы НЕ НАЙДЕН», и там --db не поможет.\n"
           "     👉 Если не уверены — берите первый выход: он снимает оба.\n"
           "     📏 Замер @COORD 2026-09-05 (записка #4898): 176 инструментов из 243\n"
           "     (72%) упрутся во второй.")
    )


def default_db(script_file) -> Path:
    return mezo_root(script_file) / DB_NAME


# ═══ ИМЕНА, КОТОРЫХ ЗДЕСЬ НЕ БЫЛО, — ВРЕЗАНЫ 10.08 01:13 UTC ПО ЗАМЕРУ (#145) ═══
# 🪤 Найдено сборкой свежего контура и ЗАПУСКОМ его инструментов: звенья, доехавшие из
# vnext/prototype, падали с `AttributeError: module 'mezo_paths' has no attribute 'live_db'`.
# Причина — ДВА ФАЙЛА С ОДНИМ ИМЕНЕМ и разной начинкой. Каждый по-своему прав, и оба
# выглядят исправными, пока не окажутся рядом.
#
# ═══ СВЕДЕНО К ГРОМКОЙ РЕДАКЦИИ 2026-08-20 06:10 UTC (заявка @PROTO, записка #3697 ②) ═══
# Работа 15.08 «пути машины больше не впечатаны — они выводятся» (`2417f72`, карточка #153 ③)
# доехала только до копии @PROTO; здесь оставалась прежняя, тихая. Порядок поиска контейнера
# теперь ОДИН в обеих копиях:
#   ① переменная среды MEZO_CONTAINER — явное сильнее выведенного;
#   ② подъём от расположения файла по МАРКЕРУ (.mezosync/mezosync.db — признак, не глубина);
#   ③ ключ container в ФАЙЛЕ ПУТЕЙ (<контейнер>/.mezosync/local/paths.json; для копии ВНЕ
#      контейнера — <каталог скриптов>/../local/paths.json) — непубликуемый; с карточки #677
#      он заменил строку container= в local.paths;
#   ④ ГРОМКИЙ отказ с рецептом. Тихий дефолт был бы путём машины под другим именем.
# ⚠️ ЭТО ПОРЯДОК container_root. У mezo_root признак стоит ПЕРВЫМ — причина названа в его теле.
# ⚠️ ЧТО СОХРАНЕНО ЗДЕСЬ И ЧЕГО НЕТ У ОБРАЗЦА — @PROTO прямо предупредила, что переносить
# «как есть» нельзя, у здешних функций свои потребители:
#   · mezo_root/default_db — зовут 3 инструмента; у образца этих имён нет вовсе;
#   · проверка объявлений о правке в resolve_db — 21 инструмент, у образца её нет.
# ⚖️ И РАЗНЫЙ СМЫСЛ ВОЗВРАТА, названный вслух, чтобы не свести по ошибке:
#   mezo_root      → каталог, ГДЕ ЛЕЖИТ база  (…/.atlas/.mezosync)
#   container_root → каталог, ВНУТРИ которого лежит .mezosync  (…/.atlas)
# Проверено прогоном до и после правки: все пять функций отдают то же, что отдавали.
# ═══ ФАЙЛ ПУТЕЙ КОНТУРА: ЕДИНСТВЕННОЕ ЧТЕНИЕ (карточка #677, этап Э3, работа Р4) ═══════════
# Решение владельца В3 а′ (2026-10-05 10:53 UTC, чат COORD): «пути — в файле в отдельной местной
# папке (например .mezosync/local/), которую Э5 берёт как есть. Файл заменяет local.paths и
# ключи meta mirror_repo, template_checkout, disk_layer_tool: одно место для путей вместо
# трёх. Нет файла или ключа — инструмент отказывает словами, а не берёт литерал.»
# Прежде пути контура жили в ТРЁХ местах, и у каждого был свой читатель: строки local.paths
# (_local_get), ключи таблицы meta (по запросу в каждом инструменте) и имена каталогов,
# впечатанные в код. Теперь читатель ОДИН — local_path() ниже.
# ⛔ ПРЕЖНИЕ ИСТОЧНИКИ КАК ЗНАЧЕНИЕ НЕ ЧИТАЮТСЯ — ни как запасной вариант, ни «на всякий случай»:
# запасной вариант и есть то, из-за чего инструмент соседа шёл в каталог на чужой машине.
# Прежний источник функция только ЗАМЕЧАЕТ и тогда добавляет к исходу подсказку с готовой
# командой шага переноса — подсказку, а не значение.
LOCAL_PATHS_PARTS = ("local", "paths.json")        # внутри каталога .mezosync
LOCAL_PATHS_STEP = "20261005-local-paths-file.py"  # шаг переноса из прежних источников
LOCAL_DECLARED = "declared"           # ключ объявлен: путь известен (на диске он есть или нет)
LOCAL_NOT_DECLARED = "not_declared"   # файл есть, ключа в нём нет (или значение пусто)
LOCAL_NO_FILE = "no_file"             # файла путей нет вовсе
LOCAL_UNREADABLE = "unreadable"       # файл есть, но не читается (битый JSON, нет прав, не объект)
_LEGACY_META_KEYS = ("mirror_repo", "template_checkout", "disk_layer_tool")
_LEGACY_FILE_KEYS = ("container", "template")


class LocalPath(NamedTuple):
    """Исход чтения ключа файла путей — четыре РАЗНЫХ исхода, каждый своими словами.

    outcome — LOCAL_DECLARED · LOCAL_NOT_DECLARED · LOCAL_NO_FILE · LOCAL_UNREADABLE;
    key     — какой ключ спрашивали;
    path    — только при «объявлено»: полный путь (относительный считается от контейнера);
    exists  — только при «объявлено»: есть ли этот путь на диске (иначе None);
    file    — файл путей: прочитанный, а при «файла нет» — первый из искавшихся;
    words   — исход одной строкой по-русски: ей и надо печатать причину;
    hint    — готовая команда шага переноса, если ПРЕЖНИЙ источник ещё несёт этот ключ, а в
              файле его нет; иначе None. Это подсказка, а не значение.
    """
    outcome: str
    key: str
    path: Path | None
    exists: bool | None
    file: Path | None
    words: str
    hint: str | None


def _paths_file_candidates(script_file, mezo_dir) -> list:
    """Где искать файл путей — по порядку. mezo_dir назван — только там (следуем за базой)."""
    if mezo_dir is not None:
        return [Path(mezo_dir) / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]]
    start = Path(script_file or __file__).resolve().parent
    # ① каталог скриптов лежит в .mezosync, значит файл — рядом с ним: <скрипты>/../local/paths.json.
    #    Так же ищет его копия инструментов ВНЕ контейнера (она несёт свой файл рядом).
    found = [start.parent / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]]
    # ② инструмент лежит ВНУТРИ контейнера, но не в .mezosync (vnext-tools): файл — у предка.
    for cand in (start, *start.parents):
        p = cand / ".mezosync" / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]
        if p not in found:
            found.append(p)
        # Карточка #685 (находка AIA ④-6): выше СВОЕГО контейнера не поднимаемся. Первый предок
        # с каталогом .mezosync и есть контейнер инструмента; нет в нём файла путей — значит, файла
        # нет, а не «взять у каталога этажом выше» (C:/guts/.mezosync, C:/.mezosync — чужой контур).
        if (cand / ".mezosync").is_dir():
            break
    return found


def _legacy_hint(key: str, candidates: list):
    """Если прежний источник ещё несёт ключ — готовая команда шага переноса, иначе None.

    Значение из прежнего источника НЕ возвращается и не используется: только факт и команда.
    Любая беда чтения — None: подсказка не вправе уронить того, кто её просит.
    """
    where = None
    db = None
    try:
        for c in candidates:
            if _is_db_file(c.parent.parent / DB_NAME):
                db = c.parent.parent / DB_NAME
                break
        if key in _LEGACY_FILE_KEYS:
            old = Path(__file__).resolve().parent / "local.paths"
            if old.is_file():
                for line in old.read_text(encoding="utf-8").splitlines():
                    if line.startswith(key + "=") and line.split("=", 1)[1].strip():
                        where = f"строка {key}= в файле {old.as_posix()}"
                        break
        if where is None and key in _LEGACY_META_KEYS and db is not None:
            uri = "file:" + quote(db.as_posix(), safe="/:") + "?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=2)
            try:
                row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            finally:
                con.close()
            if row and row[0]:
                where = f"запись {key} в таблице meta базы {db.as_posix()}"
    except Exception:  # noqa: BLE001 — подсказка не вправе ронять вызывающего
        return None
    if where is None:
        return None
    step_dir = (db.parent / "scripts" / "migrations") if db is not None \
        else Path(__file__).resolve().parent / "migrations"
    cmd = (f"python {(step_dir / LOCAL_PATHS_STEP).as_posix()}"
           + (f" --db {db.as_posix()}" if db is not None else "") + " --apply")
    return (f"прежний источник ещё несёт «{key}»: {where} — он больше не читается. "
            f"Перенести в файл путей: {cmd}  (без --apply шаг только показывает)")


def local_path(key: str, script_file=None, mezo_dir=None) -> LocalPath:
    """Прочитать ключ из файла путей контура. Исключений наружу НЕ бросает (как find_coordinator).

    Файл: <контейнер>/.mezosync/local/paths.json — JSON-объект «ключ → путь»; относительный
    путь считается от контейнера. Где искать: mezo_dir (каталог с базой) назван — только в
    <mezo_dir>/local/paths.json (так идут за базой песочницы); не назван — от расположения
    script_file: <каталог скриптов>/../local/paths.json, затем у предков .mezosync/local/.

    Четыре РАЗНЫХ исхода (поле outcome, фраза — в words):
      · объявлено    — «объявлено: <путь> (есть на диске | на диске НЕТ)»;
      · не объявлено — файл есть, ключа в нём нет (или значение пусто);
      · файла нет    — файла путей нет ни в одном из мест поиска;
      · не читается  — файл есть, но не читается: битый JSON, нет прав, верх не объект.
    Слитые вместе, они дали бы ложный ноль: «нет файла» и «нет ключа» чинятся разными
    действиями, а «не читается» нельзя выдавать за «не объявлено».

    ⛔ НЕ ЗОВЁТ container_root / live_db / live_scripts / template_root: иначе разбор
    «нужен ли второй замок» (_заразные_имена) записал бы её в заразные, а mezo_root и
    container_root зовут её САМИ.
    """
    cands: list = []
    try:
        cands = _paths_file_candidates(script_file, mezo_dir)
        found = next((c for c in cands if c.exists()), None)
        if found is None:
            first = cands[0]
            tail = "" if mezo_dir is not None else \
                " (и выше по дереву каталогов: .mezosync/local/paths.json)"
            return LocalPath(LOCAL_NO_FILE, key, None, None, first,
                             f"файла путей нет: {first.as_posix()}{tail}",
                             _legacy_hint(key, cands))
        try:
            data = json.loads(found.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as e:        # битый JSON и непрочитанные байты — ValueError
            return LocalPath(LOCAL_UNREADABLE, key, None, None, found,
                             f"файл путей не читается: {found.as_posix()} — "
                             f"{e.__class__.__name__}: {e}", None)
        if not isinstance(data, dict):
            return LocalPath(LOCAL_UNREADABLE, key, None, None, found,
                             f"файл путей не читается: {found.as_posix()} — верхний уровень "
                             f"не объект «ключ → путь»", None)
        raw = data.get(key)
        if key not in data or raw is None or (isinstance(raw, str) and not raw.strip()):
            why = "значение пусто" if key in data else "ключа нет"
            return LocalPath(LOCAL_NOT_DECLARED, key, None, None, found,
                             f"не объявлено: в файле путей {found.as_posix()} {why}: «{key}»",
                             _legacy_hint(key, cands))
        if not isinstance(raw, str):
            return LocalPath(LOCAL_UNREADABLE, key, None, None, found,
                             f"файл путей не читается: {found.as_posix()} — значение ключа "
                             f"«{key}» не строка", None)
        p = Path(raw.strip())
        if not p.is_absolute():
            p = found.parent.parent.parent / p     # <контейнер> = над каталогом .mezosync
        p = Path(os.path.normpath(str(p)))
        there = p.exists()
        return LocalPath(LOCAL_DECLARED, key, p, there, found,
                         f"объявлено: {p.as_posix()} "
                         f"({'есть на диске' if there else 'на диске НЕТ'})", None)
    except Exception as e:  # noqa: BLE001 — исход называется словами, а не роняет вызывающего
        return LocalPath(LOCAL_UNREADABLE, key, None, None, cands[0] if cands else None,
                         f"файл путей не читается: {e.__class__.__name__}: {e}", None)


# ═══ КАТАЛОГ МЕСТНОГО (карточка #679, этап Э5) ═══════════════════════════════════════════════
# Всё, что у контура своё, живёт в <каталог базы>/local/: файл путей (paths.json), перечень
# местных проверок общего прогона (checks.json) и их скрипты, местные настройки инструментов.
# Обновление инструментов (update-tools.py) в этот каталог НЕ пишет — поэтому местное больше не
# правят прямо в файлах пакета, и обновление не встаёт на «✋ ПРАВЛЕН У ТЕБЯ».
LOCAL_CHECKS_FILE = "checks.json"     # перечень местных проверок guard-all.py


def local_dir(db_path) -> Path:
    """Каталог местного контура: <каталог базы>/local.

    Идёт ЗА БАЗОЙ, а не за расположением инструмента: прогон по копии базы (песочница, стенд
    приёмки) видит местное своей копии, а не живого контура — так же, как local_path(…, mezo_dir=…).
    Существование не проверяется: «каталога нет» и «есть» различает вызывающий.
    ⛔ НЕ ЗОВЁТ container_root / live_db — по той же причине, что local_path.
    """
    return Path(db_path).resolve().parent / LOCAL_PATHS_PARTS[0]


def _paths_file_for_advice(res: LocalPath, script_file) -> str:
    """Куда класть файл путей — текстом для отказа: тот, что искали, либо первый из мест."""
    if res.file is not None:
        return res.file.as_posix()
    start = Path(script_file or __file__).resolve().parent
    return (start.parent / LOCAL_PATHS_PARTS[0] / LOCAL_PATHS_PARTS[1]).as_posix()


def container_root(script_file=None) -> Path:
    """Каталог, ВНУТРИ которого лежит .mezosync. Не найден — ОТКАЗ, а не догадка."""
    import os
    env = os.environ.get("MEZO_CONTAINER")
    if env:
        return Path(env)
    start = Path(script_file or __file__).resolve().parent
    for cand in (start, *start.parents):
        if _is_db_file(cand / ".mezosync" / DB_NAME):
            return cand
    loc = local_path("container", script_file)
    loc_dir = loc.path if loc.outcome == LOCAL_DECLARED else None
    if loc_dir and _is_db_file(loc_dir / ".mezosync" / DB_NAME):
        return loc_dir
    # ⚡ ССЫЛКА НА ПЕРВЫЙ ЗАМОК (карточка #575, находка @COORD): сюда чаще всего приходят
    # ПО СОВЕТУ соседнего отказа — он предлагает «--db абсолютным», и этот выход снимает
    # тот замок, но не этот. Роль, не знающая о двух замках, читает второй отказ как
    # «я не справился с первым» и идёт чинить не то. Три живых случая за сутки, последний —
    # внутри чужой приёмки, где он выдал себя за «поломки нет».
    paths_file = _paths_file_for_advice(loc, script_file)
    sys.exit("ERR: контейнер группы НЕ НАЙДЕН (маркер .mezosync/mezosync.db не встретился "
             "вверх по дереву).\n     Задай MEZO_CONTAINER=<путь> либо создай файл путей "
             f"{paths_file} с ключом container.\n"
             f"     Искал от: {start}\n"
             + _empty_db_note(start, exact=(loc_dir,))
             + (f"     файл путей: container={loc_dir} — задан, но {DB_NAME} по нему не найден.\n"
                if loc_dir else "")
             + (f"     {loc.words}\n" if loc.outcome == LOCAL_UNREADABLE else "")
             + (f"     ⚠️ {loc.hint}\n" if loc.hint else "")
             + "     ⚠️ ЭТО ВТОРОЙ ЗАМОК. Если вы пришли сюда по совету «позвать с абсолютным"
             " --db» — тот совет верен про СВОЙ замок и не про этот: файл базы вы назвали,"
             " а каталог группы нужен инструменту (или его соседу) отдельно.\n"
             "     👉 MEZO_CONTAINER снимает оба; --db здесь не поможет.")


def live_db(script_file=None) -> Path:
    """Путь к живой базе контура."""
    return container_root(script_file) / ".mezosync" / DB_NAME


def live_scripts(script_file=None) -> Path:
    """Каталог инструментов контура."""
    return container_root(script_file) / ".mezosync" / "scripts"


# ═══ НУЛЕВОЙ ДЕНЬ КОНТУРА — ОДИН ПРИЗНАК НА ВСЕ ПРОВЕРКИ (заявка 29 пакета) ═══════════════
# Свежий контур, только что собранный из пакета, по построению не имеет того, что копится жизнью:
# базы сравнения объёма памяти (её никто ещё не снимал) и реестра известного долга приёмок (он
# живёт в контуре-источнике и в пакет не едет). Два таких отсутствия печатались «⚠️» — как
# запущенный контур, где точку отсчёта потеряли; новый контур читал это как свою поломку.
# ⚖️ ПРИЗНАК НЕ ПРИДУМАН ЗАНОВО: это тот же признак «по данным», что у карточки #606
# (guard-section-lag.py: «лента пуста вообще ⇒ свежий контур»). Возраст контура, метку сборки и
# «роль без записей» он не берёт нарочно: возраст — догадка о том, сколько жить новому, а пустую
# ленту нельзя получить иначе как «никто ещё не писал».
# ⛔ ГРАНИЦА, называется вслух: нулевой день кончается ПЕРВОЙ ЖЕ запиской в ленту — дальше то же
# отсутствие снова «⚠️». Это намеренно: контур, в котором уже пишут, обязан завести точку отсчёта.
# ⚖️ Любая беда чтения (базы нет, ленты нет, не открылась) отвечает «нет, не нулевой день», а не
# «да»: тогда проверка печатает прежнее «⚠️» — не молчит и не выдаёт болезнь за свойство нового.
def is_zero_day(db) -> bool:
    """Нулевой день контура: во ВСЕЙ ленте записок (messages_all) нет ни одной записки.

    db — путь к базе либо уже открытое соединение sqlite3 (читается только запросом SELECT).
    True — только когда лента проверена и пуста. Нет ленты, нет базы, ошибка чтения — False."""
    own = None
    try:
        if isinstance(db, sqlite3.Connection):
            con = db
        else:
            own = con = sqlite3.connect(f"file:{Path(db).resolve().as_posix()}?mode=ro", uri=True)
        return con.execute("SELECT COUNT(*) FROM messages_all").fetchone()[0] == 0
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return False
    finally:
        if own is not None:
            own.close()


def template_root(script_file=None) -> Path:
    """Корень репозитория-образца: маркер scripts/init-group.py; иначе ключ template файла путей/среда."""
    import os
    env = os.environ.get("MEZO_TEMPLATE")
    if env:
        return Path(env)
    start = Path(script_file or __file__).resolve().parent
    for cand in (start, *start.parents):
        # 🪤 ОТСЕЧКА, ДОБАВЛЕННАЯ ЗДЕСЬ 2026-08-20 06:12 UTC — прогоном, не по образцу.
        # Маркер `scripts/init-group.py` НЕ РАЗЛИЧАЕТ образец и рабочий контур: контур
        # собран ИЗ образца и несёт тот же файл. В раскладке @PROTO это не видно (у неё
        # копия лежит внутри самого образца), а здесь первый же кандидат — наш собственный
        # контейнер, и функция уверенно возвращала его как «корень образца».
        # Признак живого контура — база рядом; у образца её нет по построению.
        # Обе раскладки: база может лежать в САМОМ кандидате (…/.mezosync/mezosync.db,
        # когда кандидат — сам каталог .mezosync) или в его подкаталоге (…/.atlas).
        # Первая редакция отсечки проверяла только вторую форму и промахнулась ровно
        # на здешней раскладке — поймано прогоном сразу после правки, а не рассуждением.
        # Пустой файл базы признаком контура не считается (_is_db_file, починка (б), 06.10).
        if _is_db_file(cand / ".mezosync" / DB_NAME) or _is_db_file(cand / DB_NAME):
            continue
        if (cand / "scripts" / "init-group.py").exists():
            return cand
    loc = local_path("template", script_file)
    loc_dir = loc.path if loc.outcome == LOCAL_DECLARED else None
    if loc_dir and (loc_dir / "scripts" / "init-group.py").exists():
        return loc_dir
    paths_file = _paths_file_for_advice(loc, script_file)
    sys.exit(("ERR: корень образца НЕ НАЙДЕН (маркер scripts/init-group.py).\n"
              f"     Задай MEZO_TEMPLATE=<путь> либо ключ template в файле путей {paths_file}.\n"
              + (f"     файл путей: template={loc_dir} — задан, но scripts/init-group.py по "
                 f"нему не найден.\n" if loc_dir else "")
              + (f"     {loc.words}\n" if loc.outcome == LOCAL_UNREADABLE else "")
              + (f"     ⚠️ {loc.hint}\n" if loc.hint else "")).rstrip("\n"))


def resolve_db(arg, script_file, must_exist: bool = True,
               readonly: bool | None = None) -> Path:
    """Единственная точка, где путь к БД превращается в абсолютный.

    Три случая, и ни один не зависит от CWD:
      1. `--db` не задан        → дефолт от расположения скрипта;
      2. `--db` абсолютный      → как есть (обратная совместимость: все живые вызовы такие);
      3. `--db` ОТНОСИТЕЛЬНЫЙ   → резолвится ОТ КОРНЯ МЕЗОСИНКА, а НЕ от текущего каталога.
         Случай 3 — сердце фикса: сегодня он резолвится от CWD и потому либо падает,
         либо (хуже) молча создаёт фантом.

    must_exist=True: несуществующий путь — ГРОМКАЯ ошибка с названной причиной, не тихое
    создание пустой БД. «Ошибка должна указывать на причину, а не на симптом» (CORE #2669:
    `can't open file` указывал на скрипт, хотя виноват был сменившийся каталог).

    readonly — характер текущего ВЫЗОВА для проверки объявлений о правке (карточка #391):
    True — читающий (под чужим объявлением предупреждение, не отказ), False — пишущий,
    None — не назван, объявление судит по имени файла. Проносится в lease.check как есть.
    """
    # 🪤 ПОРЯДОК ЗДЕСЬ — ЧАСТЬ ПОЧИНКИ, А НЕ ОФОРМЛЕНИЕ (21.08, заявка @PROTO #3713 ②).
    # Прежде первой строкой стоял безусловный `root = mezo_root(script_file)`, и он ВЫХОДИЛ
    # с отказом ДО того, как кто-либо смотрел на arg. Поэтому совет «позови с абсолютным
    # --db» не мог сработать в принципе: путь был правильный, а до него не доходило.
    # ⚖️ Абсолютный путь самодостаточен по построению — корень для него не нужен вовсе.
    p = Path(arg) if arg is not None else None
    if p is not None and p.is_absolute():
        db = p
    else:
        root = mezo_root(script_file)          # корень ищем ТОЛЬКО когда он правда нужен
        db = (root / DB_NAME) if p is None else (root / p)
    db = db.resolve()
    # ── ЕДИНАЯ ТОЧКА ПРОВЕРКИ АРЕНДЫ (карточка #204) ─────────────────────────
    # Почему здесь, а не в каждом инструменте: 23 инструмента зовут эту функцию, и она
    # ЗНАЕТ ИМЯ ВЫЗЫВАЮЩЕГО (script_file). Проверка, переписанная в каждом файле,
    # разъедется — это тот же класс, ради которого заведён один список признаков вместо
    # восьми. ⚖️ Обёрнута мягко: поломка механизма аренды НЕ ИМЕЕТ ПРАВА уронить
    # инструмент — иначе координационная удобность становится единой точкой отказа.
    try:
        import lease
        lease.check(db, script_file, readonly=readonly)
    except SystemExit:
        raise                                   # отказ по аренде — намеренный выход, пропускаем
    except Exception:                           # noqa: BLE001
        pass                                    # модуля нет / база занята — работаем как прежде
    if must_exist and not db.exists():
        # ⚠️ При АБСОЛЮТНОМ --db корень не вычислялся вовсе (и не нужен) — прежний текст
        # отказа ссылался на root и ПАДАЛ на собственном сообщении (UnboundLocalError
        # вместо «БД не найдена»; поймано приёмкой пайка 28.08). Отказ не вправе падать
        # на своём же объяснении: вызывающий видит поломку ИНСТРУМЕНТА, а не пути.
        if p is not None and p.is_absolute():
            откуда = "     Путь передан АБСОЛЮТНЫМ --db — корень не участвовал, проверь путь.\n"
        else:
            откуда = (f"     Корень мезосинка (по расположению скрипта): {root}\n"
                      f"     Путь резолвился ОТ КОРНЯ, не от текущего каталога — смена CWD ни при чём.\n")
        sys.exit(
            f"ERR: БД не найдена: {db}\n" + откуда +
            "     Если БД лежит в другом месте, укажи АБСОЛЮТНЫЙ --db."
        )
    return db


# ═══ ПРИЛОЖЕНИЯ ПРАВИЛ (карточка #652, этап 1 задачи #651) ═══════════════════════════
# ПЕРЕЕХАЛО СЮДА ИЗ set-rule.py (было там единственным читателем). Причина переезда —
# у логики появился ВТОРОЙ читатель: rules-from-pack.py кладёт приложение того же ключа
# при --adopt/--merge/--annexes, и ему нужно ТО ЖЕ самое место, что найдёт --annex у
# set-rule.py. Оставить копию в set-rule.py и завести вторую в rules-from-pack.py значило
# бы держать раскладку («каталог автора рядом — уважаем, иначе — рядом с базой») в двух
# местах сразу — а это ровно класс ошибки, которым уже расходились export-rules.py и
# set-rule.py ДО сегодняшней правки (одна и та же ветка «легаси»-раскладки, списанная
# дважды). Здесь, в mezo_paths.py, её читают ОБА инструмента импортом — не подпроцессом:
# файл без дефиса в имени, обычный `import mezo_paths` уже стоит в обоих.
def annex_dir(db_path) -> Path:
    """Каталог приложений правил ЭТОЙ базы: ключ annex_dir файла путей этой базы, а когда
    ключа нет — стандартная раскладка пакета (<каталог базы>/rules-annex).

    Карточка #677, Э3-Р4: здесь стояла раскладка контура-автора — каталог atlas.archs/.mezosync
    рядом с контейнером, имя чужого репозитория внутри пакета. Теперь она объявляется ключом
    annex_dir (контуру-автору его вписывает шаг переноса migrations/20261005-local-paths-file.py),
    а у всех остальных место стандартное. Файл битый — отказ словами: молча положить приложение
    не туда хуже, чем остановиться.
    Считается от db_path, а НЕ от container_root()/MEZO_CONTAINER: вызывающий может
    сверяться с базой ПЕСОЧНИЦЫ, и приложение обязано идти за НЕЙ."""
    root = Path(db_path).resolve().parent               # каталог .mezosync своей базы
    res = local_path("annex_dir", mezo_dir=root)
    if res.outcome == LOCAL_DECLARED:
        return res.path
    if res.outcome == LOCAL_UNREADABLE:
        sys.exit(f"ERR: место приложений правил не определено — {res.words}")
    return root / "rules-annex"


def annex_path(db_path, key: str) -> Path:
    """Путь к приложению ОДНОГО правила — см. annex_dir()."""
    return annex_dir(db_path) / f"{key}.md"


# ═══ КТО КООРДИНАТОР КОНТУРА — ОДНО ПРАВИЛО ОТБОРА НА ВЕСЬ КОНТУР ══════════════════════
# Карточка #677, этап Э3, работа Р1. Прежде правило несли ТРИ копии кода: gordi-issue.py,
# role-brief.py и rules-from-pack.py. Первые две уже искали слово в Python через casefold()
# (карточка #645: LIKE в SQLite сворачивает регистр только у латиницы, и причина
# «Координатор контура…» с заглавной не находилась вовсе). Третья осталась на SQL LIKE и
# не находила такую причину молча: готовая команда режима --propose получала заполнитель
# «<координатор>» вместо имени. Три копии одного правила разошлись, и никто не заметил;
# одна функция разойтись сама с собой не может.
# ⚖️ ЧТО ЗДЕСЬ, А ЧТО У ВЫЗЫВАЮЩИХ. Здесь — только ОТБОР (живые роли · непустая причина ·
# слово «координатор» без учёта регистра) и честный ИТОГ (одно имя · список найденных ·
# класс сбоя чтения). Слова сообщений остаются у вызывающих: каждый говорит со своим
# читателем и держит свой договор о том, что возвращает и что печатает.
# ⚖️ ПОЧЕМУ СЛОВО ИЩЕТСЯ В PYTHON, А НЕ В SQL: LIKE не сворачивает регистр кириллицы
# («Координатор» ≠ «координатор»), а casefold() сворачивает регистр любого письма. Запрос
# берёт живые роли с непустой причиной, дальше судит Python.
# ⛔ Функция НЕ ЗОВЁТ container_root / live_db / live_scripts / template_root — иначе
# разбор «нужен ли второй замок» (_заразные_имена) записал бы её в заразные, и короткий
# совет в отказах поменялся бы у всех, кто её зовёт.
COORDINATOR_WORD = "координатор"
_ALIVE_ROLES_SQL = ("SELECT role, lifecycle_reason FROM roles "
                    "WHERE lifecycle='alive' AND lifecycle_reason IS NOT NULL")


class CoordinatorLookup(NamedTuple):
    """Итог поиска координатора.

    name  — имя в ВЕРХНЕМ регистре, когда названа РОВНО ОДНА живая роль; иначе None;
    found — отсортированные имена ВСЕХ найденных (пусто · одно · несколько);
    error — класс исключения, если таблицу ролей прочитать не удалось; иначе None.
    """
    name: str | None
    found: list
    error: str | None


def _alive_roles(con):
    return con.execute(_ALIVE_ROLES_SQL).fetchall()


def find_coordinator(source) -> CoordinatorLookup:
    """Кто в этом контуре назван координатором — ИЗ ДАННЫХ (roles.lifecycle_reason живых ролей).

    source — соединение sqlite3 ИЛИ путь к базе. Путь открывается ТОЛЬКО на чтение
    (URI mode=ro): поиск не вправе ни записать в базу, ни создать пустую базу по опечатке
    пути. Соединение вызывающего не закрывается и не меняется.

    Исходы (name · found · error):
      · назван РОВНО ОДИН          → имя · [имя] · None
      · не назван никто            → None · [] · None
      · названо больше одного      → None · [все имена по алфавиту] · None
      · таблицу не прочитать       → None · [] · «класс исключения» (например OperationalError)
    Сбой чтения не поднимается исключением: вызывающий обязан назвать причину своими
    словами, а не упасть трассировкой там, где ждал имя.
    """
    try:
        if isinstance(source, sqlite3.Connection):
            rows = _alive_roles(source)
        else:
            uri = "file:" + quote(Path(source).as_posix(), safe="/:") + "?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=3)
            try:
                rows = _alive_roles(con)
            finally:
                con.close()
    except Exception as e:  # noqa: BLE001 — сбой чтения называется классом, а не роняет вызывающего
        return CoordinatorLookup(None, [], e.__class__.__name__)
    found = sorted(role.upper() for role, reason in rows
                   if reason and COORDINATOR_WORD in reason.casefold())
    name = found[0] if len(found) == 1 else None
    return CoordinatorLookup(name, found, None)
