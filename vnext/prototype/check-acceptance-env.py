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
до трёх звеньев присваиваний) внутри bite-*.py (vnext-tools и .mezosync/scripts), БЕЗ env=, закреплённого за стендом
(env=mezo_stand.stand_env(<корень стенда>) — прямо на месте вызова, через переменную
или через .update()/.pop() поверх неё), — если хотя бы ОДИН .py-литерал во ВСЁМ файле
приёмки называет инструмент, который читает MEZO_CONTAINER (прямо словом в тексте, или
через mezo_paths/mezo_stand/mezo_target/mezo_hints/mezo_refs).

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

    python check-acceptance-env.py [--json] [--debt-list ПУТЬ] [--no-debt-list]
exit 0 — новых находок нет (либо всё разрешено/учтено долгом, либо реестра рядом нет —
тогда строка «⚠️» с числом); exit 1 — есть; exit 2 — явно указанного реестра нет.
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


def runs_interpreter(call: ast.Call, scopes: list, module_stmts: list) -> bool:
    """Вызов запускает интерпретатор: sys.executable прямо в вызове ЛИБО в переменной,
    попавшей в его аргументы (PY = sys.executable · cmd = [sys.executable, …]).

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
                if has_sys_executable(value):
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


def scan_dir(root: Path, container: Path, tool_reads: dict):
    """→ (findings [(файл, строка)], excused [(файл, строка, причина)],
    keyed [{key: count}]) — findings/excused как раньше (построчно), keyed — то же самое,
    сгруппированное по ключу реестра «файл·функция·инструмент» для сверки с долгом."""
    findings, excused, keyed = [], [], {}
    if not root.is_dir():
        return findings, excused, keyed
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
            if name is None or not runs_interpreter(node, scopes, module_stmts):
                continue
            if env_is_pinned(node, scopes):
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
    return findings, excused, keyed


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


def report_without_debt(as_json: bool, debt_path: Path, findings: list, excused: list) -> int:
    """Реестра по умолчанию рядом нет (так выглядит контур, собранный из пакета GORDI) —
    находки печатаются предупреждением с числом, код 0. Почему не провал — в шапке файла."""
    files = len({p for p, _n in findings})
    if as_json:
        print(json.dumps({
            "ok": True,
            "findings": [{"file": p, "line": n} for p, n in findings],
            "excused": [{"file": p, "line": n, "reason": r} for p, n, r in excused],
            "debt": {"path": str(debt_path), "missing": True},
        }, ensure_ascii=False, indent=2))
        return 0
    if findings:
        print(f"⚠️ реестра известного долга рядом нет ({debt_path.name}) — известное от нового "
              f"не отличить: вызовов без env= закреплённого стенда {len(findings)} в {files} файлах, "
              f"провалом не считаю")
        print(f"⚠️ судить строго: python {Path(__file__).resolve()} --no-debt-list")
    print(f"итог без реестра долга: находок {len(findings)} — предупреждение, не провал"
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
    args = ap.parse_args()

    container = mezo_paths.container_root(__file__)
    dirs = [container / "vnext-tools", container / ".mezosync" / "scripts"]
    tool_reads = build_tool_reads(dirs)

    all_findings, all_excused, all_keyed = [], [], {}
    for root in dirs:
        f, e, k = scan_dir(root, container, tool_reads)
        all_findings += f
        all_excused += e
        for key, n in k.items():
            all_keyed[key] = all_keyed.get(key, 0) + n

    if args.no_debt_list:
        ok = not all_findings
        if args.json:
            print(json.dumps({
                "ok": ok,
                "findings": [{"file": p, "line": n} for p, n in all_findings],
                "excused": [{"file": p, "line": n, "reason": r} for p, n, r in all_excused],
            }, ensure_ascii=False, indent=2))
            return 0 if ok else 1
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
        return report_without_debt(args.json, debt_path, all_findings, all_excused)
    debt = load_debt(debt_path)
    known_calls, known_files, legitimate_calls, new_items, shrunk = reconcile(all_keyed, debt)
    ok = not new_items

    if args.json:
        print(json.dumps({
            "ok": ok,
            "findings": [{"file": p, "line": n} for p, n in all_findings],
            "excused": [{"file": p, "line": n, "reason": r} for p, n, r in all_excused],
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
    if not ok:
        print("   👉 чини: subprocess.run([sys.executable, TOOL, ...], env=mezo_stand.stand_env(<корень стенда>))")
        print(f"   👉 либо допиши строку в {debt_path.name} (разряд «долг»), либо на СТРОКЕ ВЫЗОВА:")
        print("      ...)   # env: caller — <причина словами>")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
