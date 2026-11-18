#!/usr/bin/env python
# SURFACES: memory, owner-words
# -*- coding: utf-8 -*-
r"""ПРИЁМКА: искатель слова владельца не зовёт resolve() на записи разговора — карточка #797, правка 17.11.

🩸 ЗАЧЕМ. 17.11.2026 установленный find-owner-word.py (редакция 8673e53) встал в живом контуре у двух
ролей: ни строки вывода за 12 минут, время процессора ≈1 с, читающего процесса нет. Пробы 21:46–21:56 UTC
на записи работающего чата (≈922 МБ): os.path.abspath, os.stat и чтение возвращаются сразу, а
os.path.realpath, nt._getfinalpathname и Path.resolve() — нет. Искатель звал resolve() на записи
разговора в ОСНОВНОМ процессе, без предела, в двух местах: у адреса находки и у строки «не прочитан:».
Приёмка bite-finder-hang.py этого не видела: её подставное зависание стоит на чтении.

ЧЕМ СУДИТ. Стендом: подсадные записи разговоров в подменённом домашнем каталоге и ПОДСТАВНОЙ resolve —
модуль sitecustomize на стенде (PYTHONPATH только у дочерних процессов приёмки). В коде искателя
проверочных лазеек нет; подмена живёт только здесь:
    FOW_STUB_RESOLVE_BLOCK=<кусок имени> .. Path.resolve(), os.path.realpath и — на Windows — сам системный
                                            вызов nt._getfinalpathname на таком файле не возвращаются (ждут
                                            файла-отпуска приёмки, не дольше 120 с, потом процесс кончается
                                            кодом 9). Подмена на слое nt добавлена по прогону TAXO 18.11:
                                            без неё код с прямым вызовом nt._getfinalpathname сходился
                                            по всем 10 случаям
    FOW_STUB_CRASH=<кусок имени> .......... открытие такого файла падает — файл остаётся непрочитанным
⚖️ ОЖИДАЕМЫЙ АДРЕС ПРИЁМКА СЧИТАЕТ ИНАЧЕ, ЧЕМ ИСКАТЕЛЬ: настоящим resolve() самого файла в своём
процессе, где подмены нет. Искатель строит адрес из раскрытого каталога записей и относительного пути.
Совпадение двух разных способов и есть предмет случаев К, ① ②б и ③.

СЛУЧАИ:
    С  ПОДМЕНА ДЕЙСТВУЕТ: в дочернем процессе resolve(), realpath и — на Windows — nt._getfinalpathname
       на файле с меткой не возвращаются за 3 с, на файле без метки resolve() возвращается. Без этого
       ① и ② прошли бы по ложной причине
    К1 контроль без подмены: находка, код 0, «файл: <resolve файла>:1»
    К2 контроль: чтение файла падает, resolve обычный — код 4, «не прочитан: <resolve файла>»
    ① НАХОДКА в записи, на которой resolve() не возвращается:
       ①а искатель вернулся в срок, код 0 · ①б адрес «файл:» тот же, что в контроле
    ② НЕПРОЧИТАННАЯ запись, на которой resolve() не возвращается:
       ②а искатель вернулся в срок, код 4 · ②б путь «не прочитан:» тот же, что в контроле
    ③ КАТАЛОГ ЗАПИСЕЙ НАЗВАН НЕ В ОКОНЧАТЕЛЬНОЙ ФОРМЕ — адрес всё равно такой, какой дал бы resolve():
       ③а через «..» (на любой системе)
       ③б коротким именем 8.3 (Windows; случай TAXO, записка #6626). Короткой формы нет или она
          не отличается от длинной — случай НЕ ПРОВЕРЕН, и это названо в строке итога
    П  ПЕСОЧНИЦА: дочерний процесс со средой dict(os.environ) видит Temp, домашний каталог и каталог
       вместо Корзины Windows — все три внутри стенда
    ④ НАРОЧНЫЕ ПОЛОМКИ — ожидание записано ДО прогона, каждая роняет РОВНО своё семейство:
       ④а resolve() возвращён у адреса находки ......... семейство ①; у ①а признак «процесс не вернулся»
       ④б resolve() возвращён у строки «не прочитан:» .. семейство ②; у ②а признак «процесс не вернулся»
       ④в каталог записей не раскрывается .............. семейство ③
       ④г адрес берётся прямым nt._getfinalpathname .... семейства ① и ②; у ①а признак «процесс не вернулся».
          Только Windows: на другой системе поломка НЕ ПОСТАВЛЕНА, и это названо в строке итога
⚡ Поломка сперва проходит разбор копии: упавшая копия «прошла» бы любой случай, ждущий провала.
⛔ ПЕСОЧНИЦА ВСЕГО ДЕРЕВА ПРОЦЕССОВ (правило deliberate-break-sandbox-env). Поломки этой приёмки
удаление и запись НЕ расширяют, но каждый прогон искателя убирает старые каталоги хода в своём Temp.
Поэтому main() до первого дочернего процесса ставит в os.environ TEMP, TMP, TMPDIR, HOME и USERPROFILE
стенда и — шестым местом, вторая редакция правила 18.11 — MEZO_STAND_TEST_BIN: каталог стенда вместо
Корзины Windows для уборки стендов (mezo_stand). Эта приёмка уборку стендов не зовёт; переменная стоит
для любого процесса ниже, который до неё дойдёт. Случай П проверяет все три места: Temp, домашний
каталог и каталог вместо Корзины. Вызовы процессов в этом файле: run_bounded в find, в С и в П —
все со средой стенда.

КОДЫ ВЫХОДА: 0 — все случаи сошлись (непроверенный ③б и непоставленная ④г названы в строке итога) · 1 — случай или
нарочная поломка не сошлись · 2 — испытуемого нет рядом: отказ мерить, а не «чисто».

Зовут так (из клона пакета):
    python <КЛОН>/vnext/prototype/bite-finder-resolve.py
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
# ⛔ испытуемый — ОТ СЕБЯ, а не по впечатанному пути: приёмка рядом с копией судит копию
TOOL = HERE / "find-owner-word.py"

MARK = "eeeeeeee"               # кусок имени файла, на котором подставной resolve не возвращается
RUN_CAP = 15                    # сколько ждёт приёмка прогона искателя, с
IN_TIME = 10                    # «вернулся в срок»: прогон искателя короче этого, с
PROBE_CAP = 3                   # сколько ждёт приёмка пробу подмены, с

SIGN_ALIVE = "процесс не вернулся"

BREAK_HIT = ('            addr.setdefault((ts, f.name, text), (full_path(root, root_real, f), where.get("line")))',
             '            addr.setdefault((ts, f.name, text), (f.resolve().as_posix(), where.get("line")))'
             '  # поломка ④а')
BREAK_UNREAD = ('            print(f"   не прочитан: {full_path(root, root_real, uf)} — {why}")',
                '            print(f"   не прочитан: {uf.resolve().as_posix()} — {why}")  # поломка ④б')
BREAK_ROOT = ("    root_real = root.resolve()",
              "    root_real = root  # поломка ④в: каталог записей не раскрывается")
# ④г — прогон Б2 приёмки чужой рукой (TAXO, 18.11): адрес берётся ПРЯМЫМ системным вызовом, мимо resolve()
# и realpath. Подмена только на Path.resolve и os.path.realpath такой код пропускала: 10 случаев из 10.
BREAK_NT = ("        return (root_real / f.relative_to(root)).as_posix()",
            r'        import nt; return pathlib.Path(nt._getfinalpathname(os.fspath(f))'
            r'.removeprefix("\\\\?\\")).as_posix()  # поломка ④г')
# (метка, имя, (образец, замена), семейство — начала имён случаев, (случай с признаком, признак) или None,
#  только ли Windows — на другой системе поломка не ставится и названа в строке итога)
BREAKS = [
    ("④а", "resolve() возвращён у адреса находки", BREAK_HIT, ("①",), ("①а", SIGN_ALIVE), False),
    ("④б", "resolve() возвращён у строки «не прочитан:»", BREAK_UNREAD, ("②",), ("②а", SIGN_ALIVE), False),
    ("④в", "каталог записей не раскрывается", BREAK_ROOT, ("③",), None, False),
    ("④г", "адрес берётся прямым nt._getfinalpathname", BREAK_NT, ("①", "②"), ("①а", SIGN_ALIVE), True),
]

STUB = r'''
# ПОДСТАВНОЙ resolve приёмки bite-finder-resolve.py (карточка #797). Живёт только на стенде.
import builtins, os, pathlib, time
_block = os.environ.get("FOW_STUB_RESOLVE_BLOCK")
_crash = os.environ.get("FOW_STUB_CRASH")
_release = os.environ.get("FOW_STUB_RELEASE", "")


def _never_returns():
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not (_release and os.path.exists(_release)):
        time.sleep(0.2)
    os._exit(9)


if _block:
    _realpath = os.path.realpath
    _resolve = pathlib.Path.resolve

    def _stub_realpath(path, *args, **kwargs):
        if _block in os.path.basename(os.fspath(path)):
            _never_returns()
        return _realpath(path, *args, **kwargs)

    def _stub_resolve(self, *args, **kwargs):
        if _block in self.name:
            _never_returns()
        return _resolve(self, *args, **kwargs)

    os.path.realpath = _stub_realpath
    pathlib.Path.resolve = _stub_resolve

    # системный слой: прямой вызов nt._getfinalpathname шёл мимо двух подмен выше (прогон TAXO 18.11)
    if os.name == 'nt':
        import nt, ntpath
        _gfp = nt._getfinalpathname

        def _stub_gfp(path, *args, **kwargs):
            if _block in os.path.basename(os.fspath(path)):
                _never_returns()
            return _gfp(path, *args, **kwargs)

        nt._getfinalpathname = _stub_gfp
        ntpath._getfinalpathname = _stub_gfp     # ntpath держит свою ссылку, взятую при запуске

if _crash:
    _open = builtins.open

    def _stub_open(file, *args, **kwargs):
        name = os.path.basename(os.fspath(file)) if isinstance(file, (str, os.PathLike)) else ""
        if _crash in name:
            raise RuntimeError("подставное падение читающего процесса на этом файле")
        return _open(file, *args, **kwargs)

    builtins.open = _stub_open
'''


def record(ts: str, text: str) -> str:
    rec = {"type": "user", "timestamp": ts, "message": {"content": text}, "origin": {"kind": "human"}}
    return json.dumps(rec, ensure_ascii=False)


def make_stand(root: pathlib.Path) -> dict:
    """Три чата: свой · с меткой · после него. Возвращает {метка: ожидаемый адрес файла}.
    Адрес — настоящим resolve() самого файла, в процессе приёмки (подмены здесь нет)."""
    layout = {
        "own": ("C--stand--a-svoj", "aaaaaaaa-1111-2222-3333-444444444444.jsonl",
                [record("2026-03-04T10:00:00.000Z", "кобальтовый ключ дня")]),
        "mark": ("C--stand--b-metka", MARK + "-1111-2222-3333-444444444444.jsonl",
                 [record("2026-03-04T11:00:00.000Z", "охристый замок открыт")]),
        "after": ("C--stand--c-posle", "cccccccc-1111-2222-3333-444444444444.jsonl",
                  [record("2026-03-04T12:00:00.000Z", "лазурный ковш полон")]),
    }
    paths = {}
    for key, (folder, fname, lines) in layout.items():
        d = root / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths[key] = (d / fname).resolve().as_posix()
    return paths


def short_form(path: pathlib.Path) -> str | None:
    """Короткая форма 8.3 пути. None — не Windows, формы нет или она не отличается от длинной."""
    if os.name != "nt":
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
    if not n or n >= len(buf):
        return None
    short = buf.value
    return short if os.path.normcase(short) != os.path.normcase(str(path)) else None


def run_bounded(cmd: list, env: dict, cap: float):
    """(код или None, вывод, секунды). None — не вернулся за cap: процесс снят, вывод не ждём."""
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env)
    try:
        out, _ = proc.communicate(timeout=cap)
    except subprocess.TimeoutExpired:
        rc = proc.poll()
        sign = (f"⏱ {SIGN_ALIVE} за {cap:g} с — снят приёмкой" if rc is None else
                f"⏱ процесс кончился с кодом {rc}, но его вывод держит другой процесс — "
                f"приёмка ждала {cap:g} с")
        proc.kill()
        return None, sign, time.monotonic() - t0
    return proc.returncode, out.decode("utf-8", errors="replace"), time.monotonic() - t0


def run_cases(tool: pathlib.Path, work: pathlib.Path, label: str) -> dict:
    """Все случаи на одном испытуемом искателе. {имя случая: (True · False · None — не проверен, подробность)}."""
    res: dict = {}

    def case(name: str, ok, detail: str = "") -> None:
        res[name] = (ok if ok is None else bool(ok), detail)

    home = work / f"home-{label}"
    root = home / ".claude" / "projects"
    paths = make_stand(root)
    # каталог записей — в ОКОНЧАТЕЛЬНОЙ форме: тогда поломка ④в (каталог не раскрывается) не задевает
    # случаи К, ① и ②, а судится только семейством ③, где каталог назван иначе
    root_long = root.resolve()
    stub_dir = work / "stub"
    release = work / "release.flag"
    tmp = work / f"tmp-{label}"
    tmp.mkdir()
    base = dict(os.environ, PYTHONIOENCODING="utf-8", USERPROFILE=str(home), HOME=str(home),
                PYTHONPATH=str(stub_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                FOW_STUB_RELEASE=str(release), TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    for k in ("FOW_STUB_RESOLVE_BLOCK", "FOW_STUB_CRASH"):
        base.pop(k, None)
    block_env = dict(base, FOW_STUB_RESOLVE_BLOCK=MARK)
    crash_env = dict(base, FOW_STUB_CRASH=MARK)
    both_env = dict(base, FOW_STUB_RESOLVE_BLOCK=MARK, FOW_STUB_CRASH=MARK)

    def find(word: str, env: dict, root_arg: str | None = None):
        return run_bounded([sys.executable, str(tool), "--word", word,
                            "--root", root_arg or str(root_long)], env, RUN_CAP)

    hit_line = f"файл: {paths['mark']}:1"
    unread_line = f"не прочитан: {paths['mark']} — "

    # ── С: подмена действует — иначе ① и ② ничего не доказывают ──
    s1, o1, _ = run_bounded([sys.executable, "-c", "import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve())",
                             paths["mark"]], block_env, PROBE_CAP)
    s2, o2, _ = run_bounded([sys.executable, "-c", "import os, sys; print(os.path.realpath(sys.argv[1]))",
                             paths["mark"]], block_env, PROBE_CAP)
    s3, o3, _ = run_bounded([sys.executable, "-c", "import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve())",
                             paths["after"]], block_env, 30)
    if os.name == "nt":
        s4, o4, _ = run_bounded([sys.executable, "-c", "import nt, sys; print(nt._getfinalpathname(sys.argv[1]))",
                                 paths["mark"]], block_env, PROBE_CAP)
        # ntpath держит СВОЮ ссылку на ту же функцию, взятую при запуске: без отдельной пробы строку
        # подмены «ntpath._getfinalpathname = _stub_gfp» не держал ни один случай (замечание приёмщика)
        s5, o5, _ = run_bounded([sys.executable, "-c",
                                 "import ntpath, sys; print(ntpath._getfinalpathname(sys.argv[1]))",
                                 paths["mark"]], block_env, PROBE_CAP)
        nt_ok = s4 is None and SIGN_ALIVE in o4 and s5 is None and SIGN_ALIVE in o5
        nt_note = (f"\nnt._getfinalpathname с меткой: код {s4} · {o4}"
                   f"\nntpath._getfinalpathname с меткой: код {s5} · {o5}")
    else:
        nt_ok, nt_note = True, "\nnt._getfinalpathname: не Windows — пробы нет"
    case(f"С подмена действует: resolve(), realpath и (на Windows) nt._getfinalpathname и "
         f"ntpath._getfinalpathname на файле с меткой "
         f"не возвращаются за {PROBE_CAP} с, на файле без метки resolve() возвращается",
         s1 is None and s2 is None and s3 == 0 and SIGN_ALIVE in o1 and SIGN_ALIVE in o2 and nt_ok,
         f"resolve с меткой: код {s1} · {o1}\nrealpath с меткой: код {s2} · {o2}\nresolve без метки: код {s3} · {o3}"
         + nt_note)

    # ── К: контроль без подставного resolve ──
    c1, oc1, _ = find("охристый замок", base)
    case("К1 контроль без подмены: находка, код 0, «файл:» — resolve самого файла и строка 1",
         c1 == 0 and "НАБРАНО ЧЕЛОВЕКОМ" in oc1 and hit_line in oc1 and "не прочитан:" not in oc1,
         f"код {c1} · жду «{hit_line}»\n{oc1}")
    c2, oc2, _ = find("охристый замок", crash_env)
    case("К2 контроль: чтение файла падает, resolve обычный — код 4, «не прочитан:» — resolve самого файла",
         c2 == 4 and unread_line in oc2 and "упал на этом файле" in oc2,
         f"код {c2} · жду «{unread_line}»\n{oc2}")

    # ── ①: находка в записи, на которой resolve() не возвращается ──
    h, oh, th = find("охристый замок", block_env)
    case(f"①а находка в записи с невозвращающимся resolve(): искатель вернулся в срок (короче {IN_TIME} с), код 0",
         h == 0 and th < IN_TIME, f"код {h}, {th:.1f} с (приёмка ждёт {RUN_CAP} с)\n{oh}")
    case("①б адрес находки тот же, что в контроле: «файл:» — resolve самого файла и строка 1",
         h == 0 and "НАБРАНО ЧЕЛОВЕКОМ" in oh and hit_line in oh, f"код {h} · жду «{hit_line}»\n{oh}")

    # ── ②: непрочитанная запись, на которой resolve() не возвращается ──
    u, ou, tu = find("охристый замок", both_env)
    case(f"②а непрочитанная запись с невозвращающимся resolve(): искатель вернулся в срок (короче {IN_TIME} с), код 4",
         u == 4 and tu < IN_TIME, f"код {u}, {tu:.1f} с (приёмка ждёт {RUN_CAP} с)\n{ou}")
    case("②б путь непрочитанного тот же, что в контроле: «не прочитан:» — resolve самого файла, причина «упал»",
         u == 4 and unread_line in ou and "упал на этом файле" in ou, f"код {u} · жду «{unread_line}»\n{ou}")

    # ── ③: каталог записей назван не в окончательной форме ──
    dotted = str(root_long) + os.sep + ".." + os.sep + root_long.name
    d, od, _ = find("охристый замок", base, dotted)
    case("③а каталог записей назван через «..»: адрес — как у resolve() самого файла",
         d == 0 and hit_line in od, f"код {d} · корень {dotted} · жду «{hit_line}»\n{od}")
    short = short_form(root_long)
    name_b = "③б каталог записей назван коротким именем 8.3: адрес — как у resolve() самого файла"
    if short is None:
        case(name_b, None, "короткой формы 8.3 у каталога стенда нет или она не отличается от длинной "
                           f"(система {os.name}) — опыт не поставлен")
    else:
        b, ob, _ = find("охристый замок", base, short)
        case(name_b, b == 0 and hit_line in ob, f"код {b} · корень {short} · жду «{hit_line}»\n{ob}")

    # ── П: песочница всего дерева процессов — дочерний процесс со средой системы видит стенд ──
    probe = ("import os, pathlib, tempfile; print(tempfile.gettempdir()); print(pathlib.Path.home()); "
             "print(os.environ.get('MEZO_STAND_TEST_BIN', ''))")
    p, op, _ = run_bounded([sys.executable, "-c", probe], dict(os.environ, PYTHONIOENCODING="utf-8"), 30)
    seen = [ln.strip() for ln in op.splitlines() if ln.strip()]
    inside = len(seen) == 3 and all(
        os.path.normcase(str(pathlib.Path(s).resolve())).startswith(os.path.normcase(str(work.resolve())))
        for s in seen)
    case("П песочница: дочерний процесс со средой dict(os.environ) видит Temp, домашний каталог и каталог "
         "вместо Корзины Windows — все три внутри стенда",
         p == 0 and inside, f"код {p} · стенд {work.resolve()}\n{op}")
    return res


def show(res: dict) -> None:
    for name, (ok, detail) in res.items():
        print(f"  {'⚪ НЕ ПРОВЕРЕН:' if ok is None else '✅' if ok else '🔴'} {name}")
        if not ok and detail:
            for ln in detail.strip().splitlines()[:14]:
                print(f"       {ln}")


def main() -> int:
    print("=" * 96)
    print("ПРИЁМКА: искатель слова владельца не зовёт resolve() на записи разговора — карточка #797")
    print(f"искатель: {TOOL}")
    print("=" * 96)
    if not TOOL.is_file():
        print(f"⛔ ИСПЫТУЕМОГО НЕТ рядом: {TOOL} — это отказ мерить, а не «чисто»")
        return 2
    failed: list = []
    unplanted: list = []
    with tempfile.TemporaryDirectory(prefix="bite-finder-resolve-", ignore_cleanup_errors=True) as tmp:
        work = pathlib.Path(tmp)
        # ⛔ ПЕСОЧНИЦА ВСЕГО ДЕРЕВА ПРОЦЕССОВ — до первого дочернего процесса (правило
        # deliberate-break-sandbox-env): наследуют все, и позванные со средой dict(os.environ)
        sand_tmp, sand_home, sand_bin = work / "sandbox-tmp", work / "sandbox-home", work / "sandbox-bin"
        sand_tmp.mkdir()
        sand_home.mkdir()
        sand_bin.mkdir()
        os.environ.update(TEMP=str(sand_tmp), TMP=str(sand_tmp), TMPDIR=str(sand_tmp),
                          HOME=str(sand_home), USERPROFILE=str(sand_home),
                          MEZO_STAND_TEST_BIN=str(sand_bin))
        tempfile.tempdir = str(sand_tmp)
        print(f"песочница: TEMP, HOME и каталог вместо Корзины у всего дерева процессов — внутри {work}")
        (work / "stub").mkdir()
        (work / "stub" / "sitecustomize.py").write_text(STUB, encoding="utf-8")
        release = work / "release.flag"
        try:
            print()
            print("── ИСПЫТУЕМЫЙ КАК ЕСТЬ ─────────────────────────────────────────────────────────────")
            res = run_cases(TOOL, work, "orig")
            show(res)
            failed += [n for n, (ok, _) in res.items() if ok is False]

            original = TOOL.read_text(encoding="utf-8")
            for i, (key, title, (pattern, repl), prefix, sign, only_nt) in enumerate(BREAKS, 1):
                print()
                print(f"── {key} НАРОЧНАЯ ПОЛОМКА: {title} " + "─" * max(4, 70 - len(title)))
                if only_nt and os.name != "nt":
                    print(f"  ⚪ {key} НЕ ПОСТАВЛЕНА: такой вызов есть только на Windows (система {os.name})")
                    unplanted.append(f"{key} {title}")
                    continue
                broken_dir = work / f"broken-{i}"
                broken_dir.mkdir()
                patched = original.replace(pattern, repl)
                if patched == original or original.count(pattern) != 1:
                    print(f"  🔴 {key} образец поломки не найден или не один — ОПЫТ НЕ ПОСТАВЛЕН")
                    failed.append(f"{key} образец не найден")
                    continue
                try:
                    compile(patched, str(broken_dir / "find-owner-word.py"), "exec")
                except SyntaxError as e:
                    print(f"  🔴 {key} поломка ломает разбор копии — ОПЫТ НЕ ПОСТАВЛЕН: {e.msg}, строка {e.lineno}")
                    failed.append(f"{key} разбор")
                    continue
                broken = broken_dir / "find-owner-word.py"
                broken.write_text(patched, encoding="utf-8")
                resb = run_cases(broken, work, f"broken{i}")
                fell = {n for n, (ok, _) in resb.items() if ok is False}
                # непроверенный случай в семейство не входит: его нельзя ни уронить, ни сохранить
                family = {n for n, (ok, _) in resb.items() if n.startswith(prefix) and ok is not None}
                fam = " и ".join(prefix)
                for n, (ok, _) in resb.items():
                    if ok is None:
                        print(f"     ⚪ не проверен: {n}")
                        continue
                    mark = "пал" if n in fell else "цел"
                    print(f"     {'⚡' if (n in fell) == (n in family) else '🔴'} {mark}: {n}")
                exact = bool(family) and fell == family
                print(f"  {'✅' if exact else '🔴'} {key} {title} → не проходит РОВНО «{fam}» "
                      f"({len(family)} из {len(resb)}), остальные целы")
                if not exact:
                    failed.append(f"{key} поломка ломает не ровно «{fam}»")
                    for n in sorted(fell ^ family):
                        print(f"       ⟂ {n}")
                        for ln in resb[n][1].strip().splitlines()[:8]:
                            print(f"          {ln}")
                if sign:
                    at, text = sign
                    first = next((n for n in resb if n.startswith(at)), None)
                    seen = first is not None and text in resb[first][1]
                    print(f"  {'✅' if seen else '🔴'} {key} признак у {at}: «{text}»")
                    if not seen:
                        failed.append(f"{key} признака «{text}» у {at} нет")
                        if first is not None:
                            for ln in resb[first][1].strip().splitlines()[:6]:
                                print(f"          {ln}")
        finally:
            # отпустить подставные ожидания, чтобы брошенные процессы кончились сами
            release.write_text("отпуск", encoding="utf-8")
            time.sleep(1.5)

    skipped = [n for n, (ok, _) in res.items() if ok is None]
    print()
    print("=" * 96)
    print(f"ИТОГ: {'пало ' + str(len(failed)) if failed else 'все проверенные случаи сошлись'} · случаев на "
          f"испытуемом {len(res)} · не проверено {len(skipped)} · нарочных поломок {len(BREAKS) - len(unplanted)} · "
          f"не поставлено {len(unplanted)}")
    for n in failed:
        print(f"   🔴 {n}")
    for n in skipped:
        print(f"   ⚪ НЕ ПРОВЕРЕН: {n} — {res[n][1]}")
    for n in unplanted:
        print(f"   ⚪ ПОЛОМКА НЕ ПОСТАВЛЕНА: {n} — такой вызов есть только на Windows")
    print("=" * 96)
    print("⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ, названо прямо:")
    print("   · НАСТОЯЩЕГО зависания resolve(): подставной ждёт в обычном сне. Почему живой вызов не")
    print("     возвращается на записи работающего чата, не известно; живой прогон — отдельным замером;")
    print("   · других вызовов, открывающих файл ради его имени (через ctypes и подобные): подмена стоит")
    print("     на Path.resolve, os.path.realpath и — на Windows — на nt._getfinalpathname (поломка ④г);")
    print("   · f.stat() у отбора по дате: последнее обращение к записи в основном процессе без предела;")
    print("     на машине замера оно возвращается сразу, почему — не мерили;")
    print("   · resolve() на самом КАТАЛОГЕ записей: он зовётся один раз и без предела;")
    print("   · ссылку или точку соединения НИЖЕ каталога записей: адрес такой записи искатель больше")
    print("     не раскрывает, а resolve() раскрывал;")
    print("   · зависание самого ЧТЕНИЯ записи — это приёмка bite-finder-hang.py.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
