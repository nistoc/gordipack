#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-loud-cleanup.py — приёмка карточки #817: уборка временного каталога приёмки не молчит об отказе.

ЗАЧЕМ. Приёмки убирали свой временный каталог вызовом shutil.rmtree(path, ignore_errors=True). На Windows
открытый файл и файл «только чтение» удаление срывают, а отказ глушился: каталог оставался, и ни вывод, ни код
выхода об этом не говорили (замер STUD 20.11: остаток у 5 приёмок из 33, у одной — копия базы в 152 МБ на каждый
прогон). Теперь уборку делает mezo_stand.remove_tree(): чего убрать не смогла — называет одной строкой вывода,
вердикт приёмки при этом не меняет.

ЧТО ИСПЫТЫВАЕТСЯ. Файл mezo_stand.py, лежащий рядом с этой приёмкой, — в ДОЧЕРНЕМ процессе и на КОПИИ: каждый
вариант (целый помощник и четыре нарочные поломки) кладётся в свой каталог стенда вместе с подставным скриптом.
Скрипт печатает, какой файл помощника он подключил; не копия — случай не засчитывается. Живой контур и живая база
не читаются и не пишутся, вся работа идёт внутри стенда приёмки.

СЛУЧАИ (имена держатся: по ним сверяется состав упавших при нарочных поломках)
  У1 занятый файл ⇒ сообщение есть: в каталоге открыт файл; уборка возвращает False, каталог на месте, в выводе
     РОВНО ОДНА строка «ВРЕМЕННЫЙ КАТАЛОГ НЕ УБРАН» — с путём каталога, числом оставшихся файлов и байт и первой
     причиной отказа; исключения нет
  У2 свободный каталог ⇒ ни сообщения, ни каталога (встречный к У1): True, каталога нет, строки нет
  У3 файл «только чтение» (так git кладёт .git/objects) — убирается: True, каталога нет, строки нет
  У4 каталога нет вовсе: True, строки нет
  У5 вердикт не подменён: подставная «приёмка» с занятым каталогом печатает свой итог и выходит СВОИМ кодом —
     проверено на коде 0 и на коде 1
  У6 блок with (temp_dir): каталог есть внутри блока, после блока его нет, строки нет
  У7 ссылка или соединение каталогов не тронуты: уборка возвращает False, ссылка на месте, файл за ней цел.
     Строка о ссылке здесь не судится — случай про то, что за ссылку уборка не ходит
  У8 класс по разбору дерева кода (ast), двумя способами: в файлах пакета нет вызова rmtree с ignore_errors=True
     и TemporaryDirectory с ignore_cleanup_errors=True; нет rmtree внутри try, чьи обработчики ничего не печатают
     и не бросают дальше. Исключения — только названные поимённо, с числом мест и причиной (перечни ниже);
     названное исключение, которого в коде уже нет или стало другое число мест, — тоже провал
НАРОЧНЫЕ ПОЛОМКИ (в КОПИИ mezo_stand.py на стенде; образец обязан найтись ровно один раз)
  ЛУ1 уборка снова молчит об остатке (строка убрана)                       → У1
  ЛУ2 строка печатается и тогда, когда каталог убран                       → У2, У3, У6
  ЛУ3 отказ уборки бросается наружу и роняет приёмку                       → У1, У5
  ЛУ4 метка «только чтение» перед удалением не снимается                   → У3
ГРАНИЦА. Открытый файл мешает удалению только на Windows. На другой системе случаи У1 и У5 и поломки ЛУ1, ЛУ3,
ЛУ4 ставить не на чем: они печатаются «не поставлен», исход приёмки — «принята, часть не проверена», код 2.
Случай У8 судится только из клона пакета: в каталогах установленного контура лежат и его собственные файлы,
перечня исключений для них здесь нет — там места молчащего удаления печатаются для сведения, случай не поставлен.

    python <клон пакета>/vnext/prototype/bite-loud-cleanup.py
"""
from __future__ import annotations

import ast
import os
import pathlib
import stat
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402

HELPER = HERE / "mezo_stand.py"
MARK = "ВРЕМЕННЫЙ КАТАЛОГ НЕ УБРАН"
WINDOWS = os.name == "nt"
OK = FAIL = SKIP = 0

# Молчащее удаление, оставленное НАМЕРЕННО: имя файла → (сколько мест, причина). Вид А — глушение ключом.
SILENT_BY_KEY = {
    "find-owner-word.py": (2, "читающий процесс, повисший на чтении, бросается без ожидания и держит свои файлы; "
                              "его каталог убирает следующий прогон (sweep_stale) — так описано в самом файле, "
                              "а строка в выводе искателя сломала бы тех, кто его вывод разбирает"),
}
# Вид Б — rmtree внутри try с обработчиком, который ничего не печатает и не бросает дальше.
SILENT_IN_TRY = {
    "bite-pack-pairs.py": (2, "функция remove() возвращает признак «каталог остался», путь печатает вызывающий"),
}
LOUD_CALLS = {"print", "exit", "case", "append", "write", "_say"}   # вызов любого из них — обработчик не молчит
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

PROBE = r'''# -*- coding: utf-8 -*-
import io
import os
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
import mezo_stand

print("HELPER=" + os.path.abspath(mezo_stand.__file__))
mode, target = sys.argv[1], sys.argv[2]
held = None
if mode in ("held", "verdict"):
    held = open(os.path.join(target, "held.bin"), "ab")     # открыт до конца процесса
if mode == "verdict":
    code = int(sys.argv[3])
    try:
        print("проба: случаи пройдены")
    finally:
        mezo_stand.remove_tree(target)
    print("ИТОГ ПРОБЫ: код " + str(code))
    sys.exit(code)
if mode == "with":
    with mezo_stand.temp_dir("bite-loud-with-") as made:
        open(os.path.join(made, "z.txt"), "w").close()
        print("INSIDE=" + str(os.path.isdir(made)))
        target = made
    print("RET=None")
else:
    print("RET=" + str(mezo_stand.remove_tree(target)))
print("EXISTS=" + str(os.path.lexists(target)))
'''

LEFT_LINE = ('        _say(f"⚠️ ВРЕМЕННЫЙ КАТАЛОГ НЕ УБРАН: {p} · осталось файлов: {files}, байт: {size} · "\n'
             '             f"первая причина: {why}")\n'
             '        return False\n')
BREAKS = {
    "ЛУ1": ("уборка снова молчит об остатке", {"У1"}, True,
            [(LEFT_LINE, "        return False  # ПОЛОМКА ЛУ1: об остатке ни слова\n")]),
    "ЛУ2": ("строка печатается и тогда, когда каталог убран", {"У2", "У3", "У6"}, False,
            [("        if not os.path.lexists(p):\n            return True\n        files, size = _left_in(p)\n",
              "        if not os.path.lexists(p):\n"
              '            _say(f"⚠️ ВРЕМЕННЫЙ КАТАЛОГ НЕ УБРАН: {p} · ПОЛОМКА ЛУ2")\n'
              "            return True\n        files, size = _left_in(p)\n")]),
    "ЛУ3": ("отказ уборки бросается наружу и роняет приёмку", {"У1", "У5"}, True,
            [(LEFT_LINE, '        raise OSError("ПОЛОМКА ЛУ3: отказ уборки брошен наружу")\n'),
             ("    except Exception as exc:                              # noqa: BLE001 — уборка не вправе "
              "уронить приёмку\n",
              "    except ZeroDivisionError as exc:                      # ПОЛОМКА ЛУ3\n")]),
    "ЛУ4": ("метка «только чтение» перед удалением не снимается", {"У3"}, True,
            [("        try:\n            os.chmod(target, stat.S_IWRITE)\n            func(target)\n"
              "        except FileNotFoundError:\n",
              "        try:\n            func(target)                                  # ПОЛОМКА ЛУ4\n"
              "        except FileNotFoundError:\n")]),
}
TITLES = {
    "У1": "занятый файл ⇒ сообщение есть: одна строка с путём, числом файлов и байт и причиной",
    "У2": "свободный каталог ⇒ ни сообщения, ни каталога (встречный к У1)",
    "У3": "файл «только чтение» убирается без строки",
    "У4": "каталога нет вовсе — True, без строки",
    "У5": "вердикт не подменён: свой итог и свой код выхода (0 и 1) при неубранном каталоге",
    "У6": "блок with: внутри блока каталог есть, после блока нет, строки нет",
    "У7": "ссылка или соединение каталогов не тронуты, файл за ней цел",
}
ORDER = ["У1", "У2", "У3", "У4", "У5", "У6", "У7"]


def case(name, verdict, detail=""):
    """verdict: True — прошёл, False — не прошёл, None — не поставлен (detail называет причину)."""
    global OK, FAIL, SKIP
    if verdict is None:
        SKIP += 1
        print(f"⚪ {name} — не поставлен: {detail}")
        return
    print(("✅" if verdict else "🔴"), name)
    if detail and not verdict:
        for line in str(detail).splitlines():
            print(f"   {line}")
    OK, FAIL = OK + (1 if verdict else 0), FAIL + (0 if verdict else 1)


def replaced(text: str, pairs, tag: str):
    """Текст помощника с поломкой; None — образец не найден ровно один раз."""
    for old, new in pairs:
        if text.count(old) != 1:
            print(f"⛔ поломка {tag} не наложилась: образец найден {text.count(old)} раз(а), нужно ровно 1: "
                  f"{old.strip()[:70]!r}")
            return None
        text = text.replace(old, new)
    return text


def lay_variant(stand: pathlib.Path, name: str, helper_text: str) -> pathlib.Path:
    """Каталог варианта: копия помощника (целая или с поломкой), подставной скрипт, своя временная папка."""
    v = stand / name
    (v / "tmp").mkdir(parents=True)
    (v / "work").mkdir()
    (v / "mezo_stand.py").write_bytes(helper_text.encode("utf-8"))
    (v / "probe.py").write_bytes(PROBE.encode("utf-8"))
    return v


def run_probe(variant: pathlib.Path, mode: str, target, *extra):
    # среда дочернего процесса закреплена за стендом (карточка #613): контур вызывающего ему не достаётся,
    # временная папка — своя у каждого варианта помощника
    tmp = str(variant / "tmp")
    env = mezo_stand.stand_env(variant, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                               TMPDIR=tmp, TEMP=tmp, TMP=tmp)
    env.pop("MEZO_KEEP_STANDS", None)
    p = subprocess.run([sys.executable, "-X", "utf8", "probe.py", mode, str(target), *extra], cwd=variant,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120)
    out = (p.stdout or "") + (p.stderr or "")
    copy = os.path.normcase(os.path.abspath(variant / "mezo_stand.py"))
    own = any(s.startswith("HELPER=") and os.path.normcase(s[7:].strip()) == copy for s in out.splitlines())
    return out, p.returncode, own


def make_dir(path: pathlib.Path, files: dict) -> pathlib.Path:
    for rel, data in files.items():
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_link(link: pathlib.Path, target: pathlib.Path) -> bool:
    """Соединение каталогов на Windows, символическая ссылка на других системах; False — завести не удалось."""
    try:
        if WINDOWS:
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            return r.returncode == 0 and os.path.lexists(link)
        os.symlink(target, link, target_is_directory=True)
        return True
    except OSError:
        return False


def drop_link(link: pathlib.Path) -> None:
    try:
        os.rmdir(link) if WINDOWS else os.unlink(link)
    except OSError:
        pass


def tail_of(out: str) -> str:
    return "вывод подставного скрипта: " + " ¦ ".join(s.strip() for s in out.splitlines() if s.strip())[:600]


def judge_all(variant: pathlib.Path) -> dict:
    """Все случаи на одном варианте помощника → {имя: (True | False | None, пояснение)}."""
    res = {}
    work = variant / "work"
    not_copy = "подставной скрипт подключил НЕ копию помощника со стенда — случай не засчитан"

    # У1 — занятый файл
    if not WINDOWS:
        res["У1"] = (None, "открытый файл мешает удалению только на Windows")
    else:
        d = make_dir(work / "held", {"free.txt": b"y", "held.bin": b"12345"})
        out, code, own = run_probe(variant, "held", d)
        lines = [s for s in out.splitlines() if MARK in s]
        ok = (own and code == 0 and "RET=False" in out and "EXISTS=True" in out and "Traceback" not in out
              and len(lines) == 1 and str(d) in lines[0] and "осталось файлов: 1" in lines[0]
              and "байт: 5" in lines[0] and "первая причина: PermissionError" in lines[0]
              and "held.bin" in lines[0])
        res["У1"] = (ok, (not_copy + "\n" if not own else "") + f"код {code} · строк об остатке {len(lines)}\n"
                     + tail_of(out))

    # У2 — свободный каталог
    d = make_dir(work / "free", {"a.txt": b"x", "sub/b.txt": b"y"})
    out, code, own = run_probe(variant, "plain", d)
    res["У2"] = (own and code == 0 and "RET=True" in out and "EXISTS=False" in out and MARK not in out
                 and not d.exists(), (not_copy + "\n" if not own else "") + f"код {code}\n" + tail_of(out))

    # У3 — файл «только чтение»
    d = make_dir(work / "readonly", {"ro.txt": b"x", "sub/ro2.txt": b"y"})
    for f in (d / "ro.txt", d / "sub" / "ro2.txt"):
        os.chmod(f, stat.S_IREAD)
    out, code, own = run_probe(variant, "plain", d)
    res["У3"] = (own and code == 0 and "RET=True" in out and "EXISTS=False" in out and MARK not in out
                 and not d.exists(), (not_copy + "\n" if not own else "") + f"код {code}\n" + tail_of(out))
    if d.exists():                       # под поломкой каталог остался — вернуть право записи, иначе не уберётся стенд
        for f in d.rglob("*"):
            if f.is_file():
                os.chmod(f, stat.S_IWRITE)

    # У4 — каталога нет
    out, code, own = run_probe(variant, "plain", work / "no-such-dir")
    res["У4"] = (own and code == 0 and "RET=True" in out and "EXISTS=False" in out and MARK not in out,
                 (not_copy + "\n" if not own else "") + f"код {code}\n" + tail_of(out))

    # У5 — вердикт не подменён
    if not WINDOWS:
        res["У5"] = (None, "неубранный каталог получается только на Windows (открытый файл)")
    else:
        good, notes = True, []
        for want in (0, 1):
            d = make_dir(work / f"verdict-{want}", {"held.bin": b"12345"})
            out, code, own = run_probe(variant, "verdict", d, str(want))
            this = (own and code == want and f"ИТОГ ПРОБЫ: код {want}" in out and "Traceback" not in out
                    and d.exists())
            good &= this
            notes.append((not_copy + " · " if not own else "") + f"ждали код {want}, получили {code} · "
                         + tail_of(out))
        res["У5"] = (good, "\n".join(notes))

    # У6 — блок with
    out, code, own = run_probe(variant, "with", "-")
    left = sorted(p.name for p in (variant / "tmp").iterdir() if p.name.startswith("bite-loud-with-"))
    res["У6"] = (own and code == 0 and "INSIDE=True" in out and "EXISTS=False" in out and MARK not in out
                 and not left, (not_copy + "\n" if not own else "") + f"код {code} · осталось во временной папке: "
                 f"{left or 'ничего'}\n" + tail_of(out))

    # У7 — ссылка или соединение каталогов
    target = make_dir(work / "link-target", {"keep.txt": b"keep"})
    link = work / "link"
    if not make_link(link, target):
        res["У7"] = (None, "ссылку или соединение каталогов завести не удалось (нет прав или не та файловая система)")
    else:
        try:
            out, code, own = run_probe(variant, "plain", link)
            kept = (target / "keep.txt").is_file() and (target / "keep.txt").read_bytes() == b"keep"
            res["У7"] = (own and code == 0 and "RET=False" in out and "EXISTS=True" in out
                         and os.path.lexists(link) and kept and "Traceback" not in out,
                         (not_copy + "\n" if not own else "") + f"код {code} · файл за ссылкой цел: {kept}\n"
                         + tail_of(out))
        finally:
            drop_link(link)
    return res


# ── У8: класс по разбору дерева кода ──

def scan_roots():
    """Что разбирать → (каталоги, это клон пакета?). Клон — целиком; у контура — два его каталога установки."""
    pack = HERE.parent.parent
    if HERE.parent.name == "vnext" and (pack / "scripts").is_dir():
        return [pack], True
    roots = [HERE]
    scripts = HERE.parent / ".mezosync" / "scripts"
    if scripts.is_dir():
        roots.append(scripts)
    return roots, False


def handler_is_silent(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise):
            return False
        if isinstance(node, ast.Call):
            f = node.func
            if (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")) in LOUD_CALLS:
                return False
    return True


def silent_sites(roots):
    """→ (по ключу {имя: [строки]}, в try {имя: [строки]}, разобрано файлов, не разобранные)."""
    by_key, in_try, parsed, unparsed = {}, {}, 0, []
    for root in roots:
        for p in sorted(root.rglob("*.py")):
            if SKIP_DIRS & set(p.parts):
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                unparsed.append(f"{p.name} ({type(exc).__name__})")
                continue
            parsed += 1
            quiet = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Try) and node.handlers and all(handler_is_silent(h) for h in node.handlers):
                    for stmt in node.body:
                        quiet.update(id(x) for x in ast.walk(stmt))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                kw = {k.arg: k.value for k in node.keywords if k.arg}

                def on(key):
                    return isinstance(kw.get(key), ast.Constant) and kw[key].value is True

                if (name == "rmtree" and on("ignore_errors")) or \
                        (name == "TemporaryDirectory" and on("ignore_cleanup_errors")):
                    by_key.setdefault(p.name, []).append(node.lineno)
                elif name == "rmtree" and "ignore_errors" not in kw and id(node) in quiet:
                    in_try.setdefault(p.name, []).append(node.lineno)
    return by_key, in_try, parsed, unparsed


def class_case():
    title = "У8 класс по разбору дерева кода: молчащего удаления нет, кроме названного с причиной"
    roots, is_pack = scan_roots()
    by_key, in_try, parsed, unparsed = silent_sites(roots)
    if not is_pack:
        # В каталогах контура лежат и его собственные файлы: перечня исключений для них у приёмки нет,
        # и провал по такому файлу был бы не о пакете. Места печатаются для сведения, случай не судится.
        found = {**by_key, **in_try}
        print(f"   ℹ️ в каталогах контура разобрано файлов: {parsed} · мест молчащего удаления: "
              f"{sum(len(v) for v in found.values())} в {len(found)} файлах (для сведения, не судится)")
        for name, lines in sorted(found.items()):
            print(f"   · {name}, строки {sorted(lines)}")
        case(title, None, "класс судится по клону пакета (<клон>/vnext/prototype): в каталогах контура лежат "
                          "и его собственные файлы, перечня исключений для них у приёмки нет")
        return
    seen = {p.name for root in roots for p in root.rglob("*.py") if not (SKIP_DIRS & set(p.parts))}
    problems = []
    for title, found, allowed in (("глушение ключом", by_key, SILENT_BY_KEY),
                                  ("rmtree в молчащем try", in_try, SILENT_IN_TRY)):
        for name, lines in sorted(found.items()):
            if name not in allowed:
                problems.append(f"{title}: {name}, строки {sorted(lines)} — не названо с причиной")
            elif len(lines) != allowed[name][0]:
                problems.append(f"{title}: {name} — мест {len(lines)}, а названо {allowed[name][0]}")
        for name, (count, _why) in sorted(allowed.items()):
            if name in seen and name not in found:
                problems.append(f"{title}: {name} назван исключением ({count} мест), а в коде таких мест уже нет — "
                                f"убери из перечня")
    if unparsed:
        problems.append(f"не разобрано файлов: {len(unparsed)} — {', '.join(unparsed[:8])}")
    if parsed == 0:
        problems.append("не разобрано ни одного файла — судить не по чему")
    named = sum(len(v) for v in by_key.values()) + sum(len(v) for v in in_try.values())
    print(f"   разобрано файлов: {parsed} · мест молчащего удаления: {named}, все названы поимённо"
          if not problems else f"   разобрано файлов: {parsed}")
    for name, lines in sorted({**by_key, **in_try}.items()):
        why = (SILENT_BY_KEY.get(name) or SILENT_IN_TRY.get(name) or (0, "ПРИЧИНА НЕ НАЗВАНА"))[1]
        print(f"   · {name}, строки {sorted(lines)}: {why}")
    case(title, not problems, "\n".join(problems))


def main() -> int:
    print("=" * 100)
    print("ПРИЁМКА: уборка временного каталога приёмки не молчит об отказе — карточка #817")
    print(f"⚖️ испытуется: {HELPER}")
    print("=" * 100)
    if not hasattr(mezo_stand, "remove_tree") or not hasattr(mezo_stand, "temp_dir"):
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет remove_tree или temp_dir — испытывать нечего")
        return 2
    text = HELPER.read_bytes().decode("utf-8").replace("\r\n", "\n")
    stand = mezo_stand.new("bite-loud-cleanup-")

    base = judge_all(lay_variant(stand, "whole", text))
    for name in ORDER:
        verdict, detail = base[name]
        case(f"{name} {TITLES[name]}", verdict, detail)
    class_case()

    for tag, (what, targets, windows_only, pairs) in BREAKS.items():
        title = f"{tag} ПОЛОМКА «{what}» валит ровно {', '.join(sorted(targets))}"
        if windows_only and not WINDOWS:
            case(title, None, "её случаи ставятся только на Windows")
            continue
        broken = replaced(text, pairs, tag)
        if broken is None:
            case(title, False, "образец поломки не найден ровно один раз — помощник менялся, правь приёмку")
            continue
        try:
            compile(broken, "mezo_stand.py", "exec")
        except SyntaxError as exc:
            case(title, False, f"поломка ломает разбор копии: {exc.msg}, строка {exc.lineno}")
            continue
        got = judge_all(lay_variant(stand, tag.lower().replace("лу", "break"), broken))
        fell = {n for n, (verdict, _d) in got.items() if verdict is False}
        case(title, fell == targets, f"упали: {sorted(fell) or 'ни один'} · ждали: {sorted(targets)}\n"
             + "\n".join(f"{n}: {got[n][1]}" for n in sorted(fell ^ targets) if n in got))

    total = len(ORDER) + 1 + len(BREAKS)
    print()
    if FAIL:
        print(f"🔴 ИТОГ: прошло {OK} из {total} · не прошло {FAIL} · не поставлено {SKIP}")
        return 1
    if SKIP:
        print(f"⚪ ИТОГ: ПРИНЯТА, ЧАСТЬ НЕ ПРОВЕРЕНА — прошло {OK} из {total} · не поставлено {SKIP} "
              f"(причина у каждого названа выше)")
        mezo_stand.accepted_with_skips()
        return 2
    print(f"✅ ИТОГ: {OK} из {total}")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
