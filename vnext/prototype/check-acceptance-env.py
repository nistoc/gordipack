#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check-acceptance-env.py — приёмки контура (bite-*.py) не должны звать инструменты
контура через subprocess со СРЕДОЙ ВЫЗЫВАЮЩЕГО (карточка #613).

ПРЕДМЕТ. Инструменты контура ищут «живой» контур СНАЧАЛА по переменной MEZO_CONTAINER
и лишь потом — по своему расположению (mezo_paths.container_root). Приёмка, запускающая
инструмент стенда БЕЗ своей среды, отдаёт ему среду вызывающего целиком: у кого
MEZO_CONTAINER указывает на другой (живой) контур, у того испытуемый инструмент стенда
может писать в ЧУЖУЮ базу. `--db` направляет только базу, но не всё остальное —
соседние инструменты, зеркало, meta. Прецедент 13.09 (записки #5093/#5096): копия
приёмки с MEZO_CONTAINER живого записала meta Atlas.

ЧТО ЛОВИТ. Вызов subprocess.run/Popen/check_output/call/check_call с sys.executable
(прямо в вызове или в переменной: PY = sys.executable · cmd = [sys.executable, …] —
до трёх звеньев присваиваний — или в команде, возвращённой функцией: q11 ниже) внутри bite-*.py (vnext-tools и .mezosync/scripts), БЕЗ env=, закреплённого за стендом
(env=mezo_stand.stand_env(<корень стенда>) — прямо на месте вызова, через переменную
или через .update()/.pop() поверх неё), — если хотя бы ОДИН .py-литерал во ВСЁМ файле
приёмки называет инструмент, который читает MEZO_CONTAINER (прямо словом в тексте, или
через mezo_paths/mezo_stand/mezo_target/mezo_hints/mezo_refs).

КОРЕНЬ СТЕНДА, ВЕДУЩИЙ В ЖИВОЙ КОНТУР (карточка #613, слово владельца 2026-11-02 14:21:16 UTC
в чате PROTO; просьба COORD, записка #6232). До этой правки проверка судила только ФОРМУ —
есть ли stand_env( в env= — и вызов env=mezo_stand.stand_env(mezo_paths.container_root())
считался закреплённым, хотя отдаёт испытуемому ровно живой контур вызывающего. Нарочная
поломка COORD m1c из записки #6235 («новых: 0», а журнал среды — живой контур у 5 из 5) была
сделана ДРУГОЙ формой — корнем строкой-путём к живому контуру. Первая правка (PR 72) её
не судила, хотя шапка называла её образцом; судит вторая — форма q01 ниже.
Теперь судится и АРГУМЕНТ: корень стенда (первый аргумент stand_env и значение MEZO_CONTAINER
в самом stand_env или поверх готовой среды) считается ведущим в живой контур, если это
цепочка «предков» — .parent · .parents[N] · .resolve() · Path() · str() · os.path.dirname() —
над одним из оснований:
  · mezo_paths.container_root() / live_db() / live_scripts() — с любым аргументом: все три
    берут MEZO_CONTAINER вызывающего раньше расположения файла, то есть это контур вызывающего;
    и они же под псевдонимом импорта: from mezo_paths import container_root as croot (q02);
  · __file__ — предок файла самой приёмки, а она лежит в живом vnext-tools или .mezosync/scripts;
  · os.environ["MEZO_CONTAINER"] · os.environ.get("MEZO_CONTAINER") · os.getenv("MEZO_CONTAINER");
  · рабочий каталог вызывающего — Path.cwd() · os.getcwd() · Path() без аргументов (q07):
    приёмка, запущенная из живого контура, отдаст именно его;
  · непустая строка-путь (q01). Стенд делают mezo_stand.new или tempfile, а путь, вписанный
    в приёмку строкой, ведёт туда, куда указывает. Сравнивать строку с контуром самой проверки
    нельзя: поломку m1c (строку к живому контуру) проверка судила на подставном контуре, и
    сравнение ответило бы «чужой каталог, не живой» — то есть пропустило бы её. Цена — осторожная
    находка у строки к настоящему стенду; пустая строка ("") не судится — она снимает переменную.
Имя прослеживается по присваиваниям своей области и модуля, до трёх звеньев (тот же приём,
что у интерпретатора в переменной). В своей области судятся только присваивания, которые
могут дойти до места использования: последнее присваивание выше в том же блоке (или в
охватывающем) исполняется наверняка и перекрывает прежние, а вложенные после него (if · try ·
for) судятся все. Так снята ложная находка z07: root = container_root(); root = mezo_stand.new(…);
stand_env(root). Такой вызов считается вызовом БЕЗ закреплённого env=:
находкой с тем же ключом реестра, а в выводе — отдельной строкой с причиной.
Не считается ведущим: путь с присоединённым подкаталогом (`... / "стенд"` — это уже не сам
контур), параметр функции, значение, возвращённое функцией, атрибут объекта (stand.root),
mezo_paths.template_root() (клон пакета, а не живой контур).
Поверх готовой среды прослеживаются env.update(MEZO_CONTAINER=…), env.update({"MEZO_CONTAINER": …}),
env["MEZO_CONTAINER"] = …, перезапись env = {**env, "MEZO_CONTAINER": …} (q05) и env |= {…} (q06) —
в своей области, до строки вызова; в самом env= — словарь {**stand_env(d), "MEZO_CONTAINER": …}
(q03) и dict(stand_env(d), MEZO_CONTAINER=…) (q04). Семь форм q01–q07 судятся по слову владельца
2026-11-03 09:14:10 UTC в чате COORD («Судить все семь», записка #6243); замер 2026-11-03 10:57 UTC
на живом контуре: ни одной из семи в коде нет — находок 113 и живой корень 1, как до правки.
НЕ СУДЯТСЯ — названо границей (пробы COORD, комментарий на карточке #613 2026-11-02 15:30:53 UTC,
и мои пробы этой правки):
  q08 цепочка из четырёх имён и длиннее — звеньев три;
  q09 значение, возвращённое функцией (def live(): return container_root());
  q10 значение параметра по умолчанию (def call(root=container_root()));
  присваивание ПОСЛЕ места использования внутри цикла, когда выше стоит прямое: судится прямое;
  f-строка и путь, собранный сложением строк, — не судятся.
ОСТОРОЖНЫЕ ЛОЖНЫЕ НАХОДКИ — тоже граница, в обратную сторону: перезапись самой среды целиком
(env = stand_env(живой); env = stand_env(стенд) — судятся обе); os.chdir(стенд) перед Path.cwd();
строка-путь к настоящему стенду. В живом коде ни одной (замер выше).
Среда, собранная в другой функции и переданная параметром или возвращённая, не прослеживается —
тоже граница.

ИЗВЕСТНЫЙ ДОЛГ (карточка #613, доработка PROTO 2026-09-14). Подключённая к общему
прогону проверка сразу нашла 134 находки у всех ролей разом — провал среди известного
перестаёт читаться. Поэтому рядом лежит РЕЕСТР `acceptance-env-debt.txt` (по умолчанию —
файл этого же имени рядом со мной): по строке на КЛЮЧ «файл · охватывающая функция ·
имя инструмента» — без номера строки, чтобы не протухать от сдвигов. Провал (код ≠ 0)
даёт только: ① вызов, которого в реестре НЕТ ВООБЩЕ, ② вызовов по ключу БОЛЬШЕ, чем
записано. Если вызовов по ключу МЕНЬШЕ записанного (кто-то уже починил) или ключ пропал
целиком — печатается «долг уменьшился — поправь список: <ключ>», это НЕ провал (код 0):
реестр обязан усыхать за роля, а не молчать о починке. `--no-debt-list` — судить БЕЗ
реестра, как до этой доработки (любая находка без комментария-разрешения — провал).

РЕЕСТРА РЯДОМ НЕТ (доработка PROTO 2026-09-14, найдено прогоном в контуре из пакета GORDI).
Реестр ведёт живой контур-источник; в пакет он не едет — в новом контуре другой состав
файлов, и чужие ключи дали бы десятки ложных «долг уменьшился». Без реестра известное от
нового не отличить, а провал за долг пакета ронял бы общий прогон проверок в КАЖДОМ новом
контуре. Поэтому: реестра по умолчанию нет → находки печатаются строкой «⚠️» с числом
(общий прогон её пробрасывает), код 0; строго — `--no-debt-list`. Реестр, указанный ЯВНО
через `--debt-list`, но отсутствующий — отказ, код 2: там опечатка, а не новый контур.

НУЛЕВОЙ ДЕНЬ (заявка 29 пакета). Отсутствие реестра у контура, который только что собран из пакета
и в котором ещё никто не писал, — свойство нового контура, а не потеря: такие строки идут с «ℹ️»
(«свойство нового контура»), а не с «⚠️». Различитель — общий признак mezo_paths.is_zero_day: во
всей ленте базы нет ни одной записки (тот же, что у карточки #606). `--db` называет базу, по
ленте которой это судится; без него берётся база контейнера. Базы нет, ленты нет или она не
читается — день НЕ нулевой, и строка остаётся «⚠️», как была. Первая же записка в ленту возвращает
«⚠️»: контур, где уже пишут, обязан завести реестр.

ЗАКОННЫЙ СЛУЧАЙ (инструмент контур не читает, среда ему безразлична, --db уже
абсолютный и достаточный и т.п.) — комментарий-разрешение НА ТОЙ ЖЕ СТРОКЕ, ГДЕ ВЫЗОВ:
    subprocess.run([sys.executable, str(TOOL), ...])   # env: caller — <причина словами>
Проверка такую строку пропускает, но печатает ЧИСЛО прощённых — доля прощённого обязана
быть видна, а не расти молча (тот же довод, что у guard-all.py про относительную форму).
Десять уже известных «законных» случаев карточки #613 в файлы ТАК не вписаны — они
записаны в реестр разрядом «законно» (правка PROTO: в сами файлы комментарии не класть).

ЧЕГО НЕ ЛОВИТ (честная граница). Позиция цели у самого вызова не разбирается напрямую:
у большинства приёмок контура имя инструмента стоит МОДУЛЬНОЙ константой или аргументом
местного помощника (call_tool/run_tool). Имя вызываемого инструмента для КЛЮЧА реестра
резолвится так: ① строковый литерал прямо в аргументах вызова; ② имя-переменная —
её присваивание (в своей области или в модуле) с литералом `*.py` внутри правой части;
③ если не резолвилось — любой `"*.py"`/'*.py' литерал во ВСЁМ файле (кроме соседей
mezo_*), через «+», как раньше. Цена упрощения ③: два разных инструмента в одном файле
дадут ОДИН склеенный ключ — замер 2026-09-14 (разбор всех 210 вызовов при заведении
реестра) такого почти не встретил.
Цели-МИГРАЦИИ (.mezosync/scripts/migrations) в словарь «читает ли контур» НЕ входят:
приёмка, зовущая только миграцию, не сканируется вовсе (разряд «проверить» реестра).
Замер 2026-09-14: 11 из 34 миграций читают контур; включение их в словарь меняет ключи
у записей долга и требует переразбора — отдельной работой, не молча.
Интерпретатор, пришедший ПАРАМЕТРОМ функции (def run(cmd): subprocess.run(cmd)),
не прослеживается: судится место, где список собран, если оно само — вызов subprocess.
Интерпретатор или команда, ВОЗВРАЩЁННЫЕ функцией, с PR 75 судятся — раздел q11 ниже.

КОМАНДА ИЗ ВОЗВРАТА ФУНКЦИИ (q11; слово владельца 2026-11-03 13:40:44 UTC в чате COORD
«Все три одним PR 75», записка #6247). Живой образец: direct_answers в bite-launcher-forms.py
брал команду у build_argv из guard-launcher-forms.py (argv = _glf().build_argv(…);
subprocess.run(argv, …)) и звал механизм без env= — проверка этого не видела, а журнал среды
показал 10 запусков с номером чата вызывающего. Теперь:
  · по ВСЕМ .py обоих каталогов разбора (не только bite-*.py) собираются имена функций, чей
    `return` несёт sys.executable — прямо или через имя, прослеженное по присваиваниям своей
    области и модуля до трёх звеньев (return argv, где argv = [sys.executable, …]);
  · итог вызова subprocess.X(…) командой НЕ считается, даже если команда стоит в его аргументах
    (def run(cmd): return subprocess.run(cmd, …) возвращает итог прогона). Без этого отсечения
    замер 2026-11-03 дал 154 имени функций, с ним — 40;
  · вызов subprocess.X(…) судится, если вызов такой функции стоит в его аргументах прямо
    (subprocess.run(make_cmd())) или в значении имени, прослеженного до трёх звеньев
    (argv = make_cmd(); subprocess.run(argv));
  · функция, объявленная в самом файле приёмки, судится по СВОЕМУ определению, а не по чужому
    одноимённому из соседнего файла;
  · метод класса для индекса — такая же функция, по ИМЕНИ метода: subprocess.run(Runner().argv())
    и cmd = r.argv(); subprocess.run(cmd) судятся, в том числе когда класс объявлен в другом файле
    разбора. lambda в САМОМ файле приёмки судится, как интерпретатор в переменной: её тело видно
    в значении имени (mk = lambda: [sys.executable, …]; subprocess.run(mk())) или прямо в вызове
    (пробы PROTO 2026-11-03 22:19 UTC по записке #6254 от COORD: семь форм, у каждой контроль с env=).
Замер 2026-11-03 14:01 UTC на живом контуре с живым реестром: новый вызов ОДИН — сам
direct_answers; он починен в том же PR. Долг «было 101 в 56 → стало 101 в 56», других новых нет.
НЕ СУДЯТСЯ (граница q11): функция, возвращающая команду, полученную ПАРАМЕТРОМ
(def with_db(cmd, db): return cmd + ["--db", db]); два уровня вызовов (функция возвращает вызов
другой такой функции); lambda из ДРУГОГО файла (helper.mk = lambda: [sys.executable, …];
subprocess.run(helper.mk())) — в индекс идут только def; функция вне двух каталогов разбора;
команда, собранная только приращениями (argv += …) без присваивания с sys.executable; КОРЕНЬ
стенда из возврата функции (q09, проба COORD q09-returned: stand_env(live())) — это суд корня
env=, а не команды, и он остаётся границей. ОСТОРОЖНАЯ ЛОЖНАЯ НАХОДКА: индекс — по ИМЕНИ функции, поэтому файл без
своего определения, зовущий чужую одноимённую функцию, которая команду не возвращает, судится
по той, что возвращает. В живом коде такого нет (замер выше: новый вызов один и настоящий).

    python check-acceptance-env.py [--json] [--debt-list ПУТЬ] [--no-debt-list] [--db ПУТЬ]
exit 0 — новых находок нет (либо всё разрешено/учтено долгом, либо реестра рядом нет —
тогда строка «⚠️» с числом, а на нулевом дне контура — «ℹ️»); exit 1 — есть; exit 2 —
явно указанного реестра нет.
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SUBPROCESS_FUNCS = {"run", "Popen", "check_output", "call", "check_call"}
OWN_NEIGHBOURS = {"mezo_paths", "mezo_stand", "mezo_target", "mezo_hints", "mezo_refs"}
PYFILE_RE = re.compile(r'''["']([A-Za-z0-9_\-]+\.py)["']''')
ALLOW_RE = re.compile(r'#\s*env:\s*caller\b(.*)')
DEBT_CATEGORY_DEBT = "долг"
DEBT_CATEGORY_LEGIT = "законно"
DEFAULT_DEBT_NAME = "acceptance-env-debt.txt"
# Помощники mezo_paths, которые берут MEZO_CONTAINER вызывающего раньше расположения файла:
# что бы им ни передали, они отвечают контуром вызывающего.
LIVE_PATH_CALLS = {"container_root", "live_db", "live_scripts"}
# Обёртки, которые не уводят путь из контура: путь остаётся тем же каталогом или его предком.
PATH_WRAPPERS = {"Path", "PurePath", "str", "dirname", "abspath", "realpath", "fspath"}
CONTAINER_VAR = "MEZO_CONTAINER"
# Рабочий каталог вызывающего (q07): приёмка, запущенная из живого контура, отдаст именно его.
CWD_CALLS = {"cwd", "getcwd", "getcwdb"}


def has_sys_executable(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr == "executable"
                and isinstance(n.value, ast.Name) and n.value.id == "sys"):
            return True
    return False


def assigned_values(name: str, pools: list) -> list:
    """Правые части присваиваний имени `name` в данных наборах операторов."""
    values = []
    for stmts in pools:
        for stmt in stmts:
            if isinstance(stmt, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == name for t in stmt.targets):
                values.append(stmt.value)
            elif (isinstance(stmt, ast.AnnAssign) and stmt.value is not None
                    and isinstance(stmt.target, ast.Name) and stmt.target.id == name):
                values.append(stmt.value)
    return values


def is_sys_executable(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "executable"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def outside_runs(node: ast.AST) -> list:
    """Узлы выражения, кроме лежащих внутри вызова subprocess.X(…): итог прогона — не команда,
    даже если команда стоит в его аргументах (def run(cmd): return subprocess.run(cmd, …)
    возвращает итог, а не команду; без этого отсечения индекс q11 замер 2026-11-03 дал
    154 имени функций, с ним — 40)."""
    out, stack = [], [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Call) and call_name(n.func) in SUBPROCESS_FUNCS:
            continue
        out.append(n)
        stack.extend(ast.iter_child_nodes(n))
    return out


def own_return_values(fn) -> list:
    """Значения `return …` самой функции — без вложенных def, lambda и class."""
    values, stack = [], list(fn.body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(n, ast.Return) and n.value is not None:
            values.append(n.value)
        stack.extend(ast.iter_child_nodes(n))
    return values


def returns_command(fn, module_stmts: list) -> bool:
    """Функция возвращает команду с интерпретатором (q11): sys.executable в значении `return` —
    прямо или через имя, прослеженное по присваиваниям её области и модуля до трёх звеньев
    (def build_argv(…): argv = [sys.executable, …]; …; return argv)."""
    pools = [flat_statements(fn), module_stmts]
    frontier = []
    for value in own_return_values(fn):
        nodes = outside_runs(value)
        if any(is_sys_executable(n) for n in nodes):
            return True
        frontier += [n.id for n in nodes if isinstance(n, ast.Name)]  # имя в return (q11)
    seen = set()
    for _link in range(3):
        next_names = []
        for name in frontier:
            if name in seen:
                continue
            seen.add(name)
            for value in assigned_values(name, pools):
                nodes = outside_runs(value)
                if any(is_sys_executable(n) for n in nodes):
                    return True
                next_names += [n.id for n in nodes if isinstance(n, ast.Name)]
        frontier = next_names
    return False


def command_returners(tree) -> tuple:
    """→ (имена всех функций файла, имена тех из них, что возвращают команду с интерпретатором)."""
    module_stmts = flat_statements(tree)
    defined, returning = set(), set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(fn.name)
            if returns_command(fn, module_stmts):
                returning.add(fn.name)
    return defined, returning


def build_command_returners(dirs: list) -> set:
    """Имена функций во ВСЕХ .py каталогов разбора, возвращающих команду с интерпретатором (q11).
    Не только bite-*.py: приёмка берёт команду и у соседнего инструмента — bite-launcher-forms.py
    зовёт build_argv из guard-launcher-forms.py."""
    names = set()
    for root in dirs:
        if not root.is_dir():
            continue
        for f in root.glob("*.py"):
            if f.name.endswith(".bak"):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            names |= command_returners(tree)[1]
    return names


def calls_command_returner(nodes, returners) -> bool:
    return any(isinstance(n, ast.Call) and call_name(n.func) in returners for n in nodes)


def runs_interpreter(call: ast.Call, scopes: list, module_stmts: list, returners=frozenset()) -> bool:
    """Вызов запускает интерпретатор: sys.executable прямо в вызове ЛИБО в переменной,
    попавшей в его аргументы (PY = sys.executable · cmd = [sys.executable, …]), ЛИБО команда
    пришла возвратом функции из `returners` (q11: subprocess.run(make_cmd()) · argv = make_cmd()).

    ⚡ ВОЗВРАТ COORD по карточке #613 (записка #5267): проверка узнавала вызов только
    по «sys.executable» ВНУТРИ него — и 4 места в 3 живых приёмках были невидимы, два
    из них звали write-message.py без среды стенда. Прослеживание — тем же приёмом,
    что у env= и имени цели: по присваиваниям своей области и модуля, до трёх звеньев
    (PY → cmd → вызов). Две формы имени в аргументах разобраны ПОРОЗНЬ — у каждой
    свой случай приёмки и своя нарочная поломка.

    Прослеживается только вызов вида `subprocess.X(...)`: голое `run(...)` в приёмке —
    почти всегда её собственная обёртка, и её внутренний subprocess-вызов судится сам
    (без этого одна и та же дыра считалась бы дважды — замер 14.09: 5 лишних из 18)."""
    if has_sys_executable(call):
        return True
    if not isinstance(call.func, ast.Attribute):
        return False
    scope = enclosing_scope(call, scopes)
    pools = ([scope[1]] if scope else []) + [module_stmts]
    args = list(call.args) + [kw.value for kw in call.keywords if kw.arg == "args"]
    if calls_command_returner([n for a in args for n in ast.walk(a)], returners):
        return True                                                        # subprocess.run(make_cmd())
    bare = [a.id for a in args if isinstance(a, ast.Name)]                 # subprocess.run(cmd)
    nested = [n.id for a in args if not isinstance(a, ast.Name)
              for n in ast.walk(a) if isinstance(n, ast.Name)]             # [PY, TOOL, …]
    frontier = bare + nested
    seen = set()
    for _link in range(3):
        next_names = []
        for name in frontier:
            if name in seen:
                continue
            seen.add(name)
            for value in assigned_values(name, pools):
                if has_sys_executable(value) or calls_command_returner(ast.walk(value), returners):
                    return True
                next_names += [n.id for n in ast.walk(value) if isinstance(n, ast.Name)]
        frontier = next_names
    return False


def flat_statements(scope_node) -> list:
    """Все узлы-операторы области (включая вложенные блоки if/try/for), по порядку."""
    out = []

    def walk_body(body):
        for stmt in body:
            out.append(stmt)
            for field in ("body", "orelse", "finalbody"):
                if hasattr(stmt, field):
                    walk_body(getattr(stmt, field))
            if hasattr(stmt, "handlers"):
                for handler in stmt.handlers:
                    walk_body(handler.body)

    walk_body(scope_node.body)
    return out


def enclosing_scope(node: ast.AST, scopes: list):
    """Самая узкая область (модуль или функция), в которой СТОИТ узел.

    🪤 БЫЛО: судили по «lo <= вызов, минимальная разница» — и вложенная функция,
    ОБЪЯВЛЕННАЯ РАНЬШЕ по файлу (например make_stale() перед более поздним вызовом
    subprocess внутри той же main(), а не внутри make_stale), забирала вызов себе:
    её lo ближе к строке вызова, хотя тело функции туда не дотягивается. Резолв
    переменной env искал присваивание ВНУТРИ make_stale(), не находил (оно в main()) —
    и живой файл bite-self-update.py (env=env, env закреплён строкой выше try)
    выходил ложной находкой. Теперь область обязана ещё и СОДЕРЖАТЬ строку вызова
    (lo <= вызов <= hi), а не просто начинаться раньше неё.
    """
    best, best_range = None, None
    for scope_node, stmts in scopes:
        lo = getattr(scope_node, "lineno", 0)
        hi = max((getattr(s, "lineno", lo) for s in stmts), default=lo)
        if lo <= node.lineno <= hi:
            rng = hi - lo
            if best_range is None or rng < best_range:
                best_range, best = rng, (scope_node, stmts)
    return best


def function_name_of(node: ast.AST, scopes: list) -> str:
    """Имя охватывающей функции узла, либо "<module>" — для ключа реестра."""
    scope = enclosing_scope(node, scopes)
    if not scope:
        return "<module>"
    scope_node = scope[0]
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return scope_node.name
    return "<module>"


def env_is_pinned(call: ast.Call, scopes: list) -> bool:
    """env= вызова закреплён за стендом (содержит stand_env(...) — прямо или через
    переменную, резолвленную по присваиваниям/.update()/.pop() ДО этой строки)."""
    env_kw = next((kw.value for kw in call.keywords if kw.arg == "env"), None)
    if env_kw is None:
        return False
    if not isinstance(env_kw, ast.Name):
        return "stand_env(" in ast.unparse(env_kw)
    scope = enclosing_scope(call, scopes)
    if not scope:
        return False
    text = []
    for stmt in scope[1]:
        if getattr(stmt, "lineno", 10 ** 9) >= call.lineno:
            continue
        touches = False
        if isinstance(stmt, ast.Assign):
            touches = any(isinstance(t, ast.Name) and t.id == env_kw.id for t in stmt.targets)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            c = stmt.value
            touches = (isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name)
                       and c.func.value.id == env_kw.id and c.func.attr in ("update", "pop", "setdefault"))
        if touches:
            text.append(ast.unparse(stmt))
    return "stand_env(" in "\n".join(text)


def call_name(func: ast.AST):
    """Имя вызываемого: `x.y.name(...)` и `name(...)` → "name"; иначе None."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def is_container_var(node) -> bool:
    return isinstance(node, ast.Constant) and node.value == CONTAINER_VAR


def is_env_key(target, env_name: str) -> bool:
    """env["MEZO_CONTAINER"] = … — цель присваивания: ключ MEZO_CONTAINER переменной среды."""
    return (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
            and target.value.id == env_name and is_container_var(target.slice))


def mezo_paths_aliases(pools: list) -> dict:
    """Псевдонимы помощников mezo_paths из `from mezo_paths import X as Y` своей области
    и модуля → {Y: X} (q02: под псевдонимом помощник прежде не узнавался)."""
    aliases = {}
    for stmts in pools:
        for stmt in stmts:
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "mezo_paths":
                aliases.update({a.asname: a.name for a in stmt.names if a.asname})
    return aliases


def statement_lists(scope_node) -> list:
    """Списки операторов области — те же блоки, что обходит flat_statements, но порознь."""
    lists = []

    def walk_body(body):
        lists.append(body)
        for stmt in body:
            for field in ("body", "orelse", "finalbody"):
                sub = getattr(stmt, field, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                    walk_body(sub)
            for handler in getattr(stmt, "handlers", None) or []:
                walk_body(handler.body)

    walk_body(scope_node.body)
    return lists


def assigns_name(stmt, name: str) -> bool:
    return ((isinstance(stmt, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets))
            or (isinstance(stmt, ast.AnnAssign) and stmt.value is not None
                and isinstance(stmt.target, ast.Name) and stmt.target.id == name))


def reaching_values(name: str, use_line, pools: list, scope_node) -> list:
    """Правые части присваиваний имени, которые могут дойти до строки use_line.

    Имя своей области: последнее присваивание, стоящее ВЫШЕ в том же блоке, что и место
    использования (или в блоке, его охватывающем), исполняется наверняка и перекрывает все
    прежние — они не судятся. Так снята ложная находка z07: root = container_root();
    root = mezo_stand.new(…); stand_env(root). Присваивания во вложенных блоках после него
    (if · try · for) могли исполниться, а могли и нет — судятся все. Прямого присваивания
    выше нет — судятся все присваивания области, как прежде. Имени в области нет — все
    присваивания модуля, как прежде.

    → [(правая часть, область для её имён)]: значение из модуля судится уже без своей области."""
    if scope_node is None or use_line is None:
        return [(v, None) for v in assigned_values(name, pools)]
    own = [s for s in pools[0] if assigns_name(s, name)]
    if not own:
        return [(v, None) for v in assigned_values(name, pools[1:])]
    lists = statement_lists(scope_node)

    def straight(stmt) -> bool:
        for body in lists:
            for i, s in enumerate(body):
                if s is stmt:
                    return any(t.lineno <= use_line <= getattr(t, "end_lineno", t.lineno)
                               for t in body[i + 1:])
        return False

    before = [s for s in own if s.lineno < use_line]
    direct = [s for s in before if straight(s)]
    if direct:
        last = max(direct, key=lambda s: s.lineno)
        own = [s for s in before if s.lineno >= last.lineno]
    return [(s.value, scope_node) for s in own]


def live_origin(expr: ast.AST, pools: list, links: int = 3, scope_node=None):
    """Ведёт ли выражение корня стенда в живой контур вызывающего — причина словами или None.

    Разбирается только цепочка «предков» (.parent · .parents[N] · .resolve() · Path() · str() ·
    os.path.dirname()) над основанием; присоединённый подкаталог (`/`) цепочку обрывает: такой
    путь уже не сам контур. Имя — по присваиваниям своей области и модуля, до `links` звеньев;
    в своей области — только те, что могут дойти до места использования (reaching_values)."""
    aliases = mezo_paths_aliases(pools)
    node = expr
    while True:
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            node = node.value
            continue
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and node.value.attr == "parents"):
            node = node.value.value
            continue
        if isinstance(node, ast.Subscript) and is_container_var(node.slice):
            return f"{CONTAINER_VAR} вызывающего ({ast.unparse(node)})"
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            if isinstance(node.func, ast.Name) and aliases.get(name) in LIVE_PATH_CALLS:
                return f"mezo_paths.{aliases[name]}() под именем {name} — контур вызывающего"
            if name in LIVE_PATH_CALLS:
                return f"mezo_paths.{name}() — контур вызывающего"
            if name in ("get", "getenv") and node.args and is_container_var(node.args[0]):
                return f"{CONTAINER_VAR} вызывающего ({ast.unparse(node)})"
            if (name in CWD_CALLS and not node.args) or (
                    name in ("Path", "PurePath") and not node.args and not node.keywords):
                return (f"рабочий каталог вызывающего ({ast.unparse(node)}) — приёмка, запущенная "
                        "из живого контура, отдаст его")
            if (name in ("resolve", "absolute") and isinstance(node.func, ast.Attribute)
                    and not node.args):
                node = node.func.value
                continue
            if name in PATH_WRAPPERS and len(node.args) == 1:
                node = node.args[0]
                continue
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
            # q01: стенд делают mezo_stand.new или tempfile; путь, вписанный строкой, ведёт туда,
            # куда указывает, — с контуром проверки его сравнивать бесполезно (поломка m1c была
            # строкой к живому контуру, а проверка судила подставной).
            return (f"путь строкой {node.value!r} — каталог, вписанный в приёмку, а не стенд "
                    "(абсолютный — каталог машины, относительный — от рабочего каталога)")
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return "предок файла самой приёмки (__file__) — она лежит в живом контуре"
            if links <= 0:
                return None
            for value, value_scope in reaching_values(node.id, getattr(node, "lineno", None), pools, scope_node):
                reason = live_origin(value, pools, links - 1, value_scope)
                if reason:
                    return reason
            return None
        return None


def stand_roots(stand_call: ast.Call) -> list:
    """Выражения, которые станут MEZO_CONTAINER испытуемого: первый аргумент stand_env
    (или container=) и значение MEZO_CONTAINER= поверх него."""
    roots = []
    if stand_call.args:
        roots.append(stand_call.args[0])
    roots += [kw.value for kw in stand_call.keywords if kw.arg in ("container", CONTAINER_VAR)]
    return roots


def env_live_reason(call: ast.Call, scopes: list, module_stmts: list):
    """Закреплённый за стендом env= вызова ведёт в живой контур? Причина словами или None.

    Смотрит те же места, что env_is_pinned: выражение env= на месте вызова либо присваивания
    переменной env, её .update(), `|=` и присваивание по ключу env["MEZO_CONTAINER"] ДО строки
    вызова в своей области. В каждом таком выражении судятся корни всех stand_env(…) и значения
    MEZO_CONTAINER во вставках поверх: словарь {…, "MEZO_CONTAINER": …} и dict(…, MEZO_CONTAINER=…)
    (q03–q06: прежде вставка поверх готовой среды судилась только через .update и ключ)."""
    env_kw = next((kw.value for kw in call.keywords if kw.arg == "env"), None)
    if env_kw is None:
        return None
    scope = enclosing_scope(call, scopes)
    scope_node = scope[0] if scope else None
    pools = ([scope[1]] if scope else []) + [module_stmts]
    sources = []
    if isinstance(env_kw, ast.Name) and scope:
        for stmt in scope[1]:
            if getattr(stmt, "lineno", 10 ** 9) >= call.lineno:
                continue
            if isinstance(stmt, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == env_kw.id for t in stmt.targets):
                sources.append(stmt.value)  # env = … — и сама среда, и её перезапись поверх (q05)
            elif isinstance(stmt, ast.Assign) and any(is_env_key(t, env_kw.id) for t in stmt.targets):
                sources.append(stmt.value)
            elif (isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == env_kw.id):
                sources.append(stmt.value)  # env |= {…} (q06)
            elif (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute)
                    and isinstance(stmt.value.func.value, ast.Name)
                    and stmt.value.func.value.id == env_kw.id
                    and stmt.value.func.attr == "update"):
                sources += [kw.value for kw in stmt.value.keywords if kw.arg == CONTAINER_VAR]
                for arg in stmt.value.args:
                    if isinstance(arg, ast.Dict):
                        sources += [v for k, v in zip(arg.keys, arg.values) if is_container_var(k)]
    else:
        sources.append(env_kw)
    for source in sources:
        for node in ast.walk(source):
            if isinstance(node, ast.Call) and call_name(node.func) == "stand_env":
                roots = stand_roots(node)
            elif isinstance(node, ast.Dict):
                roots = [v for k, v in zip(node.keys, node.values) if is_container_var(k)]
            elif isinstance(node, ast.Call) and call_name(node.func) == "dict":
                roots = [kw.value for kw in node.keywords if kw.arg == CONTAINER_VAR]
            else:
                continue
            for root in roots:
                reason = live_origin(root, pools, scope_node=scope_node)
                if reason:
                    return reason
        if not any(isinstance(n, ast.Call) and call_name(n.func) == "stand_env"
                   for n in ast.walk(source)):
            reason = live_origin(source, pools, scope_node=scope_node)
            if reason:
                return reason
    return None


def reads_container(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "MEZO_CONTAINER" in text:
        return True
    return any(re.search(rf'\b{mod}\b', text) for mod in OWN_NEIGHBOURS)


def build_tool_reads(dirs: list) -> dict:
    reads = {}
    for root in dirs:
        if not root.is_dir():
            continue
        for f in root.glob("*.py"):
            if f.name.endswith(".bak"):
                continue
            reads.setdefault(f.stem, reads_container(f))
    return reads


def find_py_literal(text: str):
    m = PYFILE_RE.search(text)
    return m.group(1)[:-3] if m else None


def file_reading_targets(src: str, own_stem: str, tool_reads: dict) -> list:
    """Все имена (без .py) во ВСЁМ файле, которые читают контур — условие включения файла в разбор и запасное имя цели."""
    names = {m.group(1)[:-3] for m in PYFILE_RE.finditer(src)}
    names.discard(own_stem)
    names -= OWN_NEIGHBOURS
    return sorted(n for n in names if tool_reads.get(n))


def resolve_target(call: ast.Call, scopes: list, module_stmts: list, fallback: list) -> str:
    """Лучшее приближение имени вызываемого инструмента (без .py) — для ключа реестра.

    ① литерал прямо в аргументах вызова; ② имя-переменная — резолв через присваивание
    (своя область, потом модуль), литерал `*.py` в правой части; ③ запасной путь —
    все читающие контур цели файла, через «+» (как раньше, до появления реестра).
    """
    for el in (call.args[0].elts if call.args and isinstance(call.args[0], (ast.List, ast.Tuple))
               else call.args[:1]):
        if isinstance(el, ast.Attribute) and el.attr == "executable":
            continue
        try:
            text = ast.unparse(el)
        except Exception:  # noqa: BLE001 — неразбираемый узел не повод падать
            continue
        found = find_py_literal(text)
        if found:
            return found
        # el сам — имя (TOOL) либо обёртка вокруг имени (str(TOOL), Path(TOOL)): резолвим
        # КАЖДОЕ имя внутри el, не только голое. Без этого «str(МЕХАНИЗМ)» на месте
        # вызова не резолвился вовсе — el был Call, а не Name, и ветка ниже не срабатывала.
        names_in_el = [n for n in ast.walk(el) if isinstance(n, ast.Name)]
        for nm in names_in_el:
            scope = enclosing_scope(call, scopes)
            for stmts in ([scope[1]] if scope else []) + [module_stmts]:
                for stmt in stmts:
                    if isinstance(stmt, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == nm.id for t in stmt.targets):
                        try:
                            rhs = ast.unparse(stmt.value)
                        except Exception:  # noqa: BLE001
                            continue
                        found = find_py_literal(rhs)
                        if found:
                            return found
    return "+".join(fallback) if fallback else "?"


def make_key(relfile: str, function: str, tool: str) -> tuple:
    """ЕДИНАЯ точка сборки ключа реестра — обе стороны (сканирование и реестр) обязаны
    звать ЭТУ функцию, а не собирать кортеж на месте: иначе резолв цели и резолв записи
    реестра могут молча разойтись в форме ключа."""
    return (relfile, function, tool)


def scan_dir(root: Path, container: Path, tool_reads: dict, returners=frozenset()):
    """→ (findings [(файл, строка)], excused [(файл, строка, причина)],
    keyed [{key: count}], live [(файл, строка, причина)]) — findings/excused как раньше
    (построчно), keyed — то же самое, сгруппированное по ключу реестра «файл·функция·инструмент»
    для сверки с долгом; live — те из находок, где env= закреплён за стендом, а корень стенда
    ведёт в живой контур (они же стоят и в findings). returners — имена функций всех каталогов
    разбора, возвращающих команду с интерпретатором (q11); имя, объявленное в самом файле,
    судится по своему определению, а не по чужому одноимённому."""
    findings, excused, keyed, live = [], [], {}, []
    if not root.is_dir():
        return findings, excused, keyed, live
    for f in sorted(root.glob("bite-*.py")):
        if f.name.endswith(".bak"):
            continue
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        reading_targets = file_reading_targets(src, f.stem, tool_reads)
        if not reading_targets:
            continue
        lines = src.splitlines()
        scopes = [(tree, flat_statements(tree))]
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((fn, flat_statements(fn)))
        module_stmts = scopes[0][1]
        defined, own_returning = command_returners(tree)
        file_returners = (set(returners) - defined) | own_returning  # своё определение — главнее
        relfile = str(f.relative_to(container)).replace("\\", "/")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Attribute) and func.attr in SUBPROCESS_FUNCS:
                name = func.attr
            elif isinstance(func, ast.Name) and func.id in SUBPROCESS_FUNCS:
                name = func.id
            if name is None or not runs_interpreter(node, scopes, module_stmts, file_returners):
                continue
            live_reason = None
            if env_is_pinned(node, scopes):
                live_reason = env_live_reason(node, scopes, module_stmts)
                if live_reason is None:
                    continue
            line_text = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
            m = ALLOW_RE.search(line_text)
            if m:
                excused.append((relfile, node.lineno, (m.group(1) or "").strip()
                                or "(причина не названа в тексте)"))
                continue
            findings.append((relfile, node.lineno))
            function = function_name_of(node, scopes)
            tool = resolve_target(node, scopes, module_stmts, reading_targets)
            key = make_key(relfile, function, tool)
            keyed[key] = keyed.get(key, 0) + 1
            if live_reason:
                live.append((relfile, node.lineno, live_reason, key))
    return findings, excused, keyed, live


def load_debt(path: Path):
    """→ dict[key] = (count, category, reason). Малформед-строки пропускаются молча
    (реестр — не код, падать на опечатке в нём дороже, чем один пропущенный ряд)."""
    entries = {}
    if not path.exists():
        return entries
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" :: ", 5)
        if len(parts) != 6:
            continue
        relfile, function, tool, count_s, category, reason = (p.strip() for p in parts)
        try:
            count = int(count_s)
        except ValueError:
            continue
        entries[make_key(relfile, function, tool)] = (count, category, reason)
    return entries


def key_covers(key: tuple, dolg: dict) -> bool:
    """Учтён ли ключ реестром долга — ТОЧНЫМ совпадением «файл · функция · инструмент».

    ⚖️ Не свёртка до `key in dolg` ради читаемости: это ЕДИНАЯ точка, которой обязана
    держаться сверка (см. reconcile) — ослабить её означало бы простить вызов в ДРУГОЙ
    функции того же файла только потому, что файл упомянут в реестре где-то ещё. Ровно
    этот класс поломки нарочно проверяет bite-acceptance-env.py (случай г): копия со
    сверкой «только по имени файла» обязана СЛЕПНУТЬ на новом вызове в новой функции.
    """
    return key in dolg


def reconcile(keyed: dict, debt: dict):
    """Сверить живые находки (по ключу) с реестром долга.

    → (known_calls, known_files, legitimate_calls, new_items, shrunk) — new_items это
    [(key, live_count, recorded_count_or_None)] то, что НЕ покрыто реестром (провал);
    shrunk — [(key, recorded, live)] долг уменьшился (не провал).

    Покрывают ОБА разряда — «долг» и «законно»: законный вызов записан в реестр ВМЕСТО
    комментария-разрешения в самом файле (см. шапку реестра), и без покрытия он был бы
    провалом. Числа «известный долг» и «законно» считаются порознь — законное долгом
    не выглядит. «Долг уменьшился» при пропаже ключа — только у разряда «долг»: у
    «законно» часть целей контур не читает вовсе, и в находках их нет по построению."""
    dolg = {k: v for k, v in debt.items() if v[1] == DEBT_CATEGORY_DEBT}
    legit = {k: v for k, v in debt.items() if v[1] == DEBT_CATEGORY_LEGIT}
    known_calls = sum(v[0] for v in dolg.values())
    known_files = len({k[0] for k in dolg})
    legitimate_calls = sum(v[0] for v in legit.values())
    covered = {**dolg, **legit}

    new_items, shrunk = [], []
    for key, live_n in keyed.items():
        if key in covered:
            rec_n = covered[key][0]
            if live_n > rec_n:
                new_items.append((key, live_n - rec_n, rec_n))
            elif live_n < rec_n:
                shrunk.append((key, rec_n, live_n))
        elif key_covers(key, covered):
            # покрывающая проверка сочла ключ учтённым БЕЗ точного совпадения — на
            # исправной сверке сюда не попасть вовсе (key_covers == key in dolg);
            # ветка существует ради встречного случая (г) на ослеплённой копии.
            pass
        else:
            new_items.append((key, live_n, None))
    for key, (rec_n, _cat, _reason) in dolg.items():
        if key not in keyed:
            shrunk.append((key, rec_n, 0))
    return known_calls, known_files, legitimate_calls, new_items, shrunk


def format_key(key: tuple) -> str:
    return " :: ".join(key)


def print_live(live: list, indent: str = "") -> None:
    """Строки про env=, закреплённый за стендом, корень которого ведёт в живой контур: такие
    вызовы уже посчитаны находками как вызовы без env=, здесь — только где и почему.
    Знак «🔎», а не «ℹ️»/«⚠️»: те два уже значат «свойство нового контура» и «реестра нет»."""
    if not live:
        return
    print(f"{indent}🔎 env= закреплён за стендом, но корень стенда ведёт в живой контур — "
          f"считаю как вызов без env=: {len(live)}")
    for p, n, r, _key in live[:20]:
        print(f"{indent}   {p}:{n} — {r}")
    if len(live) > 20:
        print(f"{indent}   … ещё {len(live) - 20} — полный список: python {Path(__file__).resolve()} --json")


def report_without_debt(as_json: bool, debt_path: Path, findings: list, excused: list,
                        zero_day: bool = False, live_json=None) -> int:
    """Реестра по умолчанию рядом нет (так выглядит контур, собранный из пакета GORDI) —
    находки печатаются предупреждением с числом, код 0. Почему не провал — в шапке файла.

    zero_day — нулевой день контура (заявка 29 пакета): в ленте нет ни одной записки, и отсутствие
    реестра — свойство нового контура, а не потеря. Тогда строки идут с «ℹ️», а не с «⚠️»
    (общий прогон пробрасывает оба знака, но «⚠️» читается как «чини»)."""
    files = len({p for p, _n in findings})
    if as_json:
        print(json.dumps({
            "ok": True,
            "findings": [{"file": p, "line": n} for p, n in findings],
            "excused": [{"file": p, "line": n, "reason": r} for p, n, r in excused],
            "live_env": live_json or [],
            "debt": {"path": str(debt_path), "missing": True, "zero_day": zero_day},
        }, ensure_ascii=False, indent=2))
        return 0
    sign = "ℹ️" if zero_day else "⚠️"
    if findings:
        why = (" — свойство нового контура (в ленте нет ни одной записки), известное от нового "
               "ещё не отличить" if zero_day else " — известное от нового не отличить")
        print(f"{sign} реестра известного долга рядом нет ({debt_path.name}){why}: "
              f"вызовов без env= закреплённого стенда {len(findings)} в {files} файлах, "
              f"провалом не считаю")
        print(f"{sign} судить строго: python {Path(__file__).resolve()} --no-debt-list")
    print(f"итог без реестра долга: находок {len(findings)} — "
          f"{'свойство нового контура' if zero_day else 'предупреждение'}, не провал"
          f" · прощено комментарием: {len(excused)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Приёмки контура: subprocess к инструменту "
                                              "контура без env= закреплённого стенда (карточка #613)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--debt-list", default=None,
                    help="путь к реестру известного долга (по умолчанию — рядом со мной; "
                         "указанного файла нет — отказ, код 2)")
    ap.add_argument("--no-debt-list", action="store_true",
                    help="судить БЕЗ реестра — любая непрощённая находка есть провал (как до карточки #613 ②)")
    ap.add_argument("--db", default=None,
                    help="база контура, по ленте которой судится нулевой день (по умолчанию — база "
                         "контейнера); читается только запросом SELECT, нужна лишь когда реестра рядом нет")
    args = ap.parse_args()

    container = mezo_paths.container_root(__file__)
    dirs = [container / "vnext-tools", container / ".mezosync" / "scripts"]
    tool_reads = build_tool_reads(dirs)
    returners = build_command_returners(dirs)

    all_findings, all_excused, all_keyed, all_live = [], [], {}, []
    for root in dirs:
        f, e, k, lv = scan_dir(root, container, tool_reads, returners)
        all_findings += f
        all_excused += e
        all_live += lv
        for key, n in k.items():
            all_keyed[key] = all_keyed.get(key, 0) + n
    live_json = [{"file": p, "line": n, "reason": r} for p, n, r, _key in all_live]

    if args.no_debt_list:
        ok = not all_findings
        if args.json:
            print(json.dumps({
                "ok": ok,
                "findings": [{"file": p, "line": n} for p, n in all_findings],
                "excused": [{"file": p, "line": n, "reason": r} for p, n, r in all_excused],
                "live_env": live_json,
            }, ensure_ascii=False, indent=2))
            return 0 if ok else 1
        print_live(all_live)
        if ok:
            print(f"✅ ИТОГО (без реестра долга): непрощённых находок нет; прощено комментарием: {len(all_excused)}")
            return 0
        print(f"⛔ ИТОГО (без реестра долга): {len(all_findings)}; прощено комментарием: {len(all_excused)}")
        for p, n in all_findings[:20]:
            print(f"   {p}:{n}")
        return 1

    debt_path = Path(args.debt_list) if args.debt_list else Path(__file__).resolve().with_name(DEFAULT_DEBT_NAME)
    if not debt_path.exists():
        if args.debt_list:
            print(f"⛔ реестр долга не найден: {debt_path} — укажи верный путь или суди без реестра: --no-debt-list")
            return 2
        # Нулевой день — по ленте базы (общий признак mezo_paths.is_zero_day). getattr: у модуля
        # старее этой правки признака нет — тогда прежнее «⚠️», а не падение. Не прочиталось — тоже «⚠️».
        db_path = Path(args.db) if args.db else container / ".mezosync" / mezo_paths.DB_NAME
        zero_day = bool(getattr(mezo_paths, "is_zero_day", lambda _db: False)(db_path))
        if not args.json:
            print_live(all_live)
        return report_without_debt(args.json, debt_path, all_findings, all_excused, zero_day,
                                   live_json)
    debt = load_debt(debt_path)
    known_calls, known_files, legitimate_calls, new_items, shrunk = reconcile(all_keyed, debt)
    ok = not new_items

    if args.json:
        print(json.dumps({
            "ok": ok,
            "findings": [{"file": p, "line": n} for p, n in all_findings],
            "excused": [{"file": p, "line": n, "reason": r} for p, n, r in all_excused],
            "live_env": live_json,
            "debt": {
                "path": str(debt_path),
                "known_calls": known_calls,
                "known_files": known_files,
                "legitimate_calls": legitimate_calls,
                "new_calls": sum(n for _k, n, _r in new_items),
                "new_keys": [{"file": k[0], "function": k[1], "tool": k[2], "count": n,
                             "recorded": r} for k, n, r in new_items],
                "shrunk": [{"file": k[0], "function": k[1], "tool": k[2], "recorded": rec,
                           "live": live} for k, rec, live in shrunk],
            },
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    new_calls = sum(n for _k, n, _r in new_items)
    print(f"{'✅' if ok else '⛔'} известный долг: {known_calls} вызовов в {known_files} файлах "
          f"({debt_path.name}) · законно без env: {legitimate_calls} · новых: {new_calls}"
          f" · прощено комментарием: {len(all_excused)}")
    for key, n, rec in new_items[:20]:
        was_now = f" (записано {rec}, стало {rec + n})" if rec is not None else " (в реестре нет вовсе)"
        print(f"   {format_key(key)} :: +{n}{was_now}")
    if len(new_items) > 20:
        print(f"   … ещё {len(new_items) - 20} — полный список: python {Path(__file__).resolve()} --json")
    for key, rec, live in shrunk:
        print(f"   ℹ️ долг уменьшился — поправь список: {format_key(key)} (было {rec}, стало {live})")
    # при реестре — только новые: записанный в реестр вызов уже назван там с причиной, и строка
    # про него в каждом общем прогоне была бы шумом; полный перечень — в --json, поле live_env
    new_keys = {k for k, _n, _r in new_items}
    print_live([e for e in all_live if e[3] in new_keys], indent="   ")
    if not ok:
        print("   👉 чини: subprocess.run([sys.executable, TOOL, ...], env=mezo_stand.stand_env(<корень стенда>))")
        print(f"   👉 либо допиши строку в {debt_path.name} (разряд «долг»), либо на СТРОКЕ ВЫЗОВА:")
        print("      ...)   # env: caller — <причина словами>")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
