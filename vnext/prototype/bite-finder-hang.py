#!/usr/bin/env python
# SURFACES: memory, owner-words
# -*- coding: utf-8 -*-
r"""ПРИЁМКА: искатель слова владельца не висит молча на чтении записи разговора — карточка #797.

🩸 ЗАЧЕМ. 16–17.11 find-owner-word.py трижды за сутки встал на чтении записи разговора, которую
дописывала среда: ни байта за минуты, и процесс не снимался даже принудительно. owner-word.py
ждал его без предела — запись адресов словам (карточка #795) простояла 50 минут без строки вывода.

ЧЕМ СУДИТ. Стендом: подсадные записи разговоров с известным содержимым в подменённом домашнем
каталоге и ПОДСТАВНОЕ ЧТЕНИЕ — модуль sitecustomize на стенде (PYTHONPATH только для дочерних
процессов приёмки). В коде искателя проверочных лазеек нет; подмена живёт только здесь:
    FOW_STUB_HANG=<кусок имени> .. открытие такого файла не возвращается (ждёт файла-отпуска
                                   приёмки, не дольше 120 с, потом процесс кончается кодом 9)
    FOW_STUB_NOKILL=1 ............ kill и terminate у процессов искателя ничего не делают — как
                                   у настоящего зависания, где процесс не снимался принудительно
    FOW_STUB_CRASH=<кусок имени> . открытие такого файла падает ошибкой Python

СЛУЧАИ — по критериям карточки:
    К1–К3 контроль без подмены ........... найдено 0 · только спорное 3 · не найдено 1, «не везде» нет
    ① ИСКАТЕЛЬ НЕ ВИСИТ МОЛЧА (подставное чтение не возвращается, kill не действует):
       ①а возвращается в срок ............ предел 3 с, весь прогон короче 15 с, код не 2 (2 — ключ отвергнут)
       ①б непрочитанное названо .......... код 4, «не прочитано файлов 1 из 3», полный путь, «не вернулось»
       ①в остальные файлы прочитаны ...... слово из файла ПОСЛЕ повисшего найдено, код 0, повисший назван
       ①г owner-word.py add дождался ...... предел по умолчанию 30 с, слово записано, непрочитанное названо
    ② «НЕ НАЙДЕНО» НЕ ПЕЧАТАЕТСЯ КАК ЧЕСТНОЕ (читающий процесс падает на файле — от предела не зависит):
       ②а не найдено → код 4, «ИСКАЛ НЕ ВЕЗДЕ», строки «НЕ НАЙДЕНО» нет, причина «упал» с текстом ошибки
       ②б только спорное → код 4, а не 3 · ②в слово из файла после упавшего найдено, код 0
    ③ ВСТРЕЧНЫЙ: всё читается — bite-find-owner-word.py проходит без правки ожиданий
    ④ ЗАПИСЬ СЛОВА (тот же упавший файл):
       ④а найдено в своём чате, чужой не прочитан → ПИШЕТ, называет непрочитанное, след в verified_by
       ④б не прочитан файл НАЗВАННОГО чата → ОТКАЗ «запись разговора не прочитана», строки нет
       ④в ВСТРЕЧНЫЙ: чат названного файла прочитан, текста в нём нет → обычный отказ, НЕ «не прочитана»
       ④г source: у слова, чей файл не прочитан, причина «запись разговора не прочитана»
       ④д контроль: всё прочитано → пишет, слова «не прочитано» в выводе нет
    П ПЕСОЧНИЦА: дочерний процесс со средой dict(os.environ) видит Temp и домашний каталог стенда
    У СЛЕД БРОШЕННОГО ПРОГОНА (заметка TAXO 3, 17.11): в своём TEMP стенда подсажены каталоги —
       в контейнере find-owner-word/ и рядом с ним, верхним уровнем
       Уа старый каталог хода в контейнере (час без записи) убран прогоном искателя
       Уб ВСТРЕЧНЫЙ: в контейнере свежий каталог хода, старый со свежим файлом и чужой старый — целы
       Уг ВСТРЕЧНЫЙ: вне контейнера уборка не трогает ничего — ни старый find-owner-word-* верхним
          уровнем Temp, ни чужой старый каталог
       Ув предел --read-timeout 601 с — отказ, код 2; 600 с — обычный прогон, код 0
    ⑤ НАРОЧНЫЕ ПОЛОМКИ — каждая роняет РОВНО своё семейство, остальные целы:
       ⑤а «предел снят» ............ семейство ①; у ①а признак «процесс не вернулся»
       ⑤б «каналы унаследованы» .... семейство ① (поломка БК TAXO); у ①а признак «вывод держит другой процесс»
       ⑤в «уборка снята» ........... ровно Уа
       ⑤г «имя не проверяется» ..... ровно Уб (поломка Т2 TAXO): без проверки имени удаление не выходит
                                     за контейнер — Уг цел
       ⑤д «контейнер снят» ......... ровно Уа и Уг: уборка снова идёт по всему Temp, как в 18f9aef
⚡ Поломка сперва проходит разбор копии: упавшая копия «прошла» бы любой случай, ждущий провала.
⛔ ПЕСОЧНИЦА ВСЕГО ДЕРЕВА ПРОЦЕССОВ (правило deliberate-break-sandbox-env). Поломки ⑤г и ⑤д РАСШИРЯЮТ
удаление и исполняют его по-настоящему. Поэтому main() до первого прогона ставит в os.environ TEMP, TMP,
TMPDIR, HOME и USERPROFILE стенда — их наследует КАЖДЫЙ дочерний процесс, даже позванный со средой
dict(os.environ); случай П это проверяет, а ③ сверх того получает TEMP стенда явно.
🩸 17.11 14:56–15:02 UTC в редакции 18f9aef здесь стояло «прогоны искателя на стенде идут с TEMP
стенда», а ③ шёл со средой системы: нарочная поломка Т2 TAXO удалила через него ≈58 тыс. каталогов
системного Temp (записка #6608). Утверждение об изоляции было проверено на случаях, которые правились,
а не на КАЖДОМ вызове процесса. Вызовы процессов в этом файле: run_bounded в find, owner, ③ и П —
все со средой стенда.

Зовут так:
    python <КОНТУР>/vnext-tools/bite-finder-hang.py
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
# ⛔ испытуемые — ОТ СЕБЯ, а не по впечатанному пути: приёмка в песочнице рядом с порченой копией
# иначе судила бы живой оригинал
TOOL = HERE / "find-owner-word.py"
OWNER = HERE / "owner-word.py"
BITE_FIND = HERE / "bite-find-owner-word.py"

HANG_MARK = "ffffffff"          # кусок имени файла, на котором подставное чтение встаёт или падает
SHORT_LIMIT = "3"               # предел тишины для прямых прогонов искателя, с
RUN_CAP = 20                    # сколько ждёт приёмка прямого прогона искателя, с
OWNER_CAP = 75                  # сколько ждёт приёмка owner-word.py при пределе по умолчанию 30 с

STALE_AGE = 7200                # «старый» каталог на стенде: два часа без записи (порог искателя — час)

BREAK_LIMIT = ("                if code is not None or time.monotonic() - moved > limit:",
               "                if code is not None:  # поломка ⑤а: предел тишины снят")
BREAK_CHANNELS = ("                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,",
                  "                                        stdin=subprocess.DEVNULL, stdout=None,  # поломка ⑤б")
BREAK_SWEEP = ("    sweep_stale(home, time.time())",
               "    pass  # поломка ⑤в: уборка снята")
# ⛔ ⑤г и ⑤д РАСШИРЯЮТ удаление — только в песочнице всего дерева процессов (main)
BREAK_NAME = ("        if not e.name.startswith(WORK_PREFIX):",
              "        if False:  # поломка ⑤г: имя не проверяется")
BREAK_HOME = ("    home = pathlib.Path(tempfile.gettempdir()) / WORK_HOME",
              "    home = pathlib.Path(tempfile.gettempdir())  # поломка ⑤д: контейнер снят")
SIGN_ALIVE = "процесс не вернулся"
SIGN_HELD = "вывод держит другой процесс"
# (метка, имя, (образец, замена), семейство — начала имён случаев, признак у ①а или None)
BREAKS = [
    ("⑤а", "предел тишины снят", BREAK_LIMIT, ("①",), SIGN_ALIVE),
    ("⑤б", "каналы унаследованы", BREAK_CHANNELS, ("①",), SIGN_HELD),
    ("⑤в", "уборка снята", BREAK_SWEEP, ("Уа",), None),
    ("⑤г", "имя не проверяется", BREAK_NAME, ("Уб",), None),
    ("⑤д", "контейнер снят", BREAK_HOME, ("Уа", "Уг"), None),
]

STUB = r'''
# ПОДСТАВНОЕ ЧТЕНИЕ приёмки bite-finder-hang.py (карточка #797). Живёт только на стенде.
import builtins, os, subprocess, time
_hang = os.environ.get("FOW_STUB_HANG")
_crash = os.environ.get("FOW_STUB_CRASH")
_release = os.environ.get("FOW_STUB_RELEASE", "")
if os.environ.get("FOW_STUB_NOKILL"):
    subprocess.Popen.kill = lambda self: None
    subprocess.Popen.terminate = lambda self: None
_open = builtins.open


def _stub_open(file, *args, **kwargs):
    name = os.path.basename(os.fspath(file)) if isinstance(file, (str, os.PathLike)) else ""
    if _hang and _hang in name:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and not (_release and os.path.exists(_release)):
            time.sleep(0.2)
        os._exit(9)
    if _crash and _crash in name:
        raise RuntimeError("подставное падение читающего процесса на этом файле")
    return _open(file, *args, **kwargs)


builtins.open = _stub_open
'''


def record(ts: str, text: str, human: bool = True) -> str:
    rec = {"type": "user", "timestamp": ts, "message": {"content": text}}
    if human:
        rec["origin"] = {"kind": "human"}
    return json.dumps(rec, ensure_ascii=False)


def make_stand(root: pathlib.Path) -> dict:
    """Три чата: свой · повисающий · после повисающего. Возвращает {метка: путь файла}."""
    layout = {
        "own": ("C--stand--a-svoj", "aaaaaaaa-1111-2222-3333-444444444444.jsonl",
                [record("2026-03-04T10:00:00.000Z", "кобальтовый ключ дня"),
                 record("2026-03-04T10:05:00.000Z", "бирюзовая сова летит", human=False)]),
        "hang": ("C--stand--b-povis", HANG_MARK + "-1111-2222-3333-444444444444.jsonl",
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


def make_db(path: pathlib.Path) -> pathlib.Path:
    """Пустое хранилище слов владельца — схема из миграции 20261114-owner-words.py."""
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE owner_words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, said_at TEXT NOT NULL, chat TEXT NOT NULL,
        text_verbatim TEXT NOT NULL CHECK (length(trim(text_verbatim)) > 0),
        source_file TEXT, source_line INTEGER,
        verified_by TEXT NOT NULL CHECK (length(trim(verified_by)) > 0),
        heard_by TEXT NOT NULL, noted_at TEXT NOT NULL, note TEXT,
        UNIQUE (chat, said_at, text_verbatim))""")
    conn.commit()
    conn.close()
    return path


def rows(db: pathlib.Path) -> list:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT id, said_at, chat, source_file, verified_by FROM owner_words "
                            "ORDER BY id").fetchall()
    finally:
        conn.close()


def run_bounded(cmd: list, env: dict, cap: float):
    """(код или None, вывод, секунды). None — не вернулся за cap: процесс снят, вывод не ждём.
    ⚖️ Вывод брошенного не дочитывается нарочно: повторное ожидание повисло бы ровно там, где
    повис испытуемый, и приёмка встала бы вместе с ним."""
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env)
    try:
        out, _ = proc.communicate(timeout=cap)
    except subprocess.TimeoutExpired:
        # признак механизма (заметка TAXO 2, 17.11): сам ли процесс не вернулся, или он кончился,
        # а канал его вывода держит унаследовавший его процесс — снаружи то и другое «код None»
        rc = proc.poll()
        sign = (f"⏱ {SIGN_ALIVE} за {cap:g} с — снят приёмкой" if rc is None else
                f"⏱ процесс кончился с кодом {rc}, но его {SIGN_HELD} (канал унаследован) — "
                f"приёмка ждала {cap:g} с")
        proc.kill()
        return None, sign, time.monotonic() - t0
    return proc.returncode, out.decode("utf-8", errors="replace"), time.monotonic() - t0


def run_cases(tool: pathlib.Path, bite: pathlib.Path, work: pathlib.Path, label: str) -> dict:
    """Все случаи на одном испытуемом искателе. {имя случая: (прошёл, подробность)}."""
    res: dict = {}

    def case(name: str, ok: bool, detail: str = "") -> None:
        res[name] = (bool(ok), detail)

    home = work / f"home-{label}"
    root = home / ".claude" / "projects"
    paths = make_stand(root)
    stub_dir = work / "stub"
    release = work / "release.flag"
    # свой TEMP стенда: каталоги хода искателя (и брошенные повисшим чтением) остаются на стенде,
    # а не в системном Temp — 17.11 приёмка оставила там 25 каталогов (заметка TAXO 3)
    tmp = work / f"tmp-{label}"
    tmp.mkdir()
    base = dict(os.environ, PYTHONIOENCODING="utf-8", USERPROFILE=str(home), HOME=str(home),
                PYTHONPATH=str(stub_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                FOW_STUB_RELEASE=str(release), TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    for k in ("FOW_STUB_HANG", "FOW_STUB_CRASH", "FOW_STUB_NOKILL"):
        base.pop(k, None)
    hang_env = dict(base, FOW_STUB_HANG=HANG_MARK, FOW_STUB_NOKILL="1")
    crash_env = dict(base, FOW_STUB_CRASH=HANG_MARK)

    def find(word: str, env: dict, *extra: str):
        return run_bounded([sys.executable, str(tool), "--word", word, "--root", str(root), *extra],
                           env, RUN_CAP)

    def owner(db: pathlib.Path, env: dict, *args: str, cap: float = 30):
        return run_bounded([sys.executable, str(OWNER), "--db", str(db), "--finder", str(tool), *args],
                           env, cap)

    # ── К: контроль без подмены ──
    c1, o1, _ = find("охристый замок", base)
    case("К1 контроль: найдено, всё прочитано — код 0, слов «ИСКАЛ НЕ ВЕЗДЕ» и «не прочитан:» нет",
         c1 == 0 and "НАБРАНО ЧЕЛОВЕКОМ" in o1 and "ИСКАЛ НЕ ВЕЗДЕ" not in o1
         and "не прочитан:" not in o1 and "файлов записей просмотрено 3" in o1, f"код {c1}\n{o1}")
    c2, o2, _ = find("бирюзовая сова", base)
    case("К2 контроль: только спорное, всё прочитано — код 3", c2 == 3, f"код {c2}\n{o2}")
    c3, o3, _ = find("нет такого слова на стенде", base)
    case("К3 контроль: не найдено, всё прочитано — код 1 и «НЕ НАЙДЕНО»",
         c3 == 1 and "НЕ НАЙДЕНО" in o3 and "ИСКАЛ НЕ ВЕЗДЕ" not in o3, f"код {c3}\n{o3}")

    # ── ①: чтение не возвращается, kill не действует ──
    h1, oh1, t1 = find("охристый замок", hang_env, "--read-timeout", SHORT_LIMIT)
    # код 2 не засчитывается: «вернулся в срок» без чтения ничего не доказывает. Замер 17.11 12:51 UTC —
    # прежний искатель (main 373eaf4) отверг незнакомый ему ключ --read-timeout за 0,3 с кодом 2,
    # и случай проходил по ложной причине
    case(f"①а повисшее чтение: искатель вернулся в срок и не с кодом 2 (предел {SHORT_LIMIT} с, прогон короче 15 с)",
         h1 is not None and h1 != 2 and t1 < 15, f"код {h1}, {t1:.1f} с (приёмка ждёт {RUN_CAP} с)\n{oh1}")
    case("①б непрочитанное названо: код 4, «не прочитано файлов 1 из 3», полный путь, «не вернулось за 3 с»",
         h1 == 4 and "не прочитано файлов 1 из 3" in oh1
         and f"не прочитан: {paths['hang']} — чтение не вернулось за 3 с" in oh1, f"код {h1}\n{oh1}")
    h2, oh2, t2 = find("лазурный ковш", hang_env, "--read-timeout", SHORT_LIMIT)
    case("①в файл ПОСЛЕ повисшего прочитан новым читающим процессом: найдено, код 0, повисший назван",
         h2 == 0 and "2026-03-04T12:00:00.000Z" in oh2 and f"не прочитан: {paths['hang']}" in oh2,
         f"код {h2}, {t2:.1f} с\n{oh2}")
    db_g = make_db(work / f"g-{label}.db")
    g, og, tg = owner(db_g, hang_env, "add", "--said-at", "2026-03-04 10:00:00 UTC", "--chat", "aaaaaaaa",
                      "--text", "кобальтовый ключ дня", "--heard-by", "COORD", cap=OWNER_CAP)
    rg = rows(db_g) if g is not None else []
    case("①г owner-word.py add при повисшем чтении и пределе по умолчанию: вернулся, слово записано, "
         "непрочитанное названо",
         g == 0 and "ЗАПИСАНО" in og and "не прочитано файлов 1" in og and len(rg) == 1
         and "не прочитано искателем файлов 1" in rg[0][4], f"код {g}, {tg:.1f} с\n{og}")

    # ── ②: читающий процесс падает — от предела не зависит ──
    k1, ok1, _ = find("охристый замок", crash_env)
    case("②а не найдено при непрочитанном: код 4, «ИСКАЛ НЕ ВЕЗДЕ», строки «НЕ НАЙДЕНО» нет, причина «упал»",
         k1 == 4 and "ИСКАЛ НЕ ВЕЗДЕ" in ok1 and "НЕ НАЙДЕНО" not in ok1
         and "упал на этом файле" in ok1 and "подставное падение" in ok1, f"код {k1}\n{ok1}")
    k2, ok2, _ = find("бирюзовая сова", crash_env)
    case("②б только спорное при непрочитанном: код 4, а не 3; спорное напечатано",
         k2 == 4 and "без признака 1" in ok2, f"код {k2}\n{ok2}")
    k3, ok3, _ = find("лазурный ковш", crash_env)
    case("②в файл после упавшего прочитан: найдено, код 0", k3 == 0 and "2026-03-04T12:00:00.000Z" in ok3,
         f"код {k3}\n{ok3}")

    # ── П: песочница всего дерева процессов — дочерний процесс со средой системы видит стенд ──
    probe = "import pathlib, tempfile; print(tempfile.gettempdir()); print(pathlib.Path.home())"
    p, op, _ = run_bounded([sys.executable, "-c", probe], dict(os.environ, PYTHONIOENCODING="utf-8"), 30)
    seen = [ln.strip() for ln in op.splitlines() if ln.strip()]
    inside = len(seen) == 2 and all(
        os.path.normcase(str(pathlib.Path(s).resolve())).startswith(os.path.normcase(str(work.resolve())))
        for s in seen)
    case("П песочница: дочерний процесс со средой dict(os.environ) видит Temp и домашний каталог стенда",
         p == 0 and inside, f"код {p} · стенд {work.resolve()}\n{op}")

    # ── ③: встречный — TEMP стенда явно, поверх песочницы ──
    b, ob, tb = run_bounded([sys.executable, str(bite)],
                            dict(os.environ, PYTHONIOENCODING="utf-8", TEMP=str(tmp), TMP=str(tmp),
                                 TMPDIR=str(tmp)), 300)
    case("③ ВСТРЕЧНЫЙ: всё читается — bite-find-owner-word.py проходит без правки ожиданий",
         b == 0 and "пало 0" in ob, f"код {b}, {tb:.0f} с\n" + "\n".join(ob.splitlines()[-12:]))

    # ── ④: запись слова при непрочитанном файле (тот же упавший файл) ──
    db_a = make_db(work / f"a-{label}.db")
    wa, oa, _ = owner(db_a, crash_env, "add", "--said-at", "2026-03-04 10:00:00 UTC", "--chat", "aaaaaaaa",
                      "--text", "кобальтовый ключ дня", "--heard-by", "COORD")
    ra = rows(db_a)
    case("④а найдено в своём чате, чужой файл не прочитан → ПИШЕТ, называет непрочитанное, след в verified_by",
         wa == 0 and "ЗАПИСАНО" in oa and paths["hang"] in oa and len(ra) == 1
         and "не прочитано искателем файлов 1" in ra[0][4] and ra[0][3] == paths["own"],
         f"код {wa} · строк {len(ra)}\n{oa}")
    db_b = make_db(work / f"b-{label}.db")
    wb, obb, _ = owner(db_b, crash_env, "add", "--said-at", "2026-03-04 11:00:00 UTC", "--chat", HANG_MARK,
                       "--text", "охристый замок открыт", "--heard-by", "COORD")
    case("④б не прочитан файл НАЗВАННОГО чата → ОТКАЗ «запись разговора не прочитана», код 2, строки нет",
         wb == 2 and "запись разговора не прочитана" in obb and paths["hang"] in obb and not rows(db_b),
         f"код {wb}\n{obb}")
    db_c = make_db(work / f"c-{label}.db")
    wc, oc, _ = owner(db_c, crash_env, "add", "--said-at", "2026-03-04 11:00:00 UTC", "--chat", "aaaaaaaa",
                      "--text", "охристый замок открыт", "--heard-by", "COORD")
    case("④в ВСТРЕЧНЫЙ: записи названного чата прочитаны, текста в них нет → обычный отказ, НЕ «не прочитана»",
         wc == 2 and "дословность НЕ подтверждена" in oc and "запись разговора не прочитана" not in oc
         and not rows(db_c), f"код {wc}\n{oc}")
    db_d = make_db(work / f"d-{label}.db")
    conn = sqlite3.connect(db_d)
    conn.execute("INSERT INTO owner_words (said_at, chat, text_verbatim, verified_by, heard_by, noted_at) "
                 "VALUES ('2026-03-04 11:00:00 UTC', ?, 'охристый замок открыт', 'проба стенда', 'COORD', "
                 "'2026-03-04 11:01:00 UTC')", (HANG_MARK,))
    conn.commit()
    conn.close()
    wd, od, _ = owner(db_d, crash_env, "source")
    case("④г source: файл чата слова не прочитан → причина «запись разговора не прочитана», код 1, адрес не записан",
         wd == 1 and "запись разговора не прочитана" in od and rows(db_d)[0][3] is None, f"код {wd}\n{od}")
    db_e = make_db(work / f"e-{label}.db")
    we, oe, _ = owner(db_e, base, "add", "--said-at", "2026-03-04 10:00:00 UTC", "--chat", "aaaaaaaa",
                      "--text", "кобальтовый ключ дня", "--heard-by", "COORD")
    re_ = rows(db_e)
    case("④д контроль: всё прочитано → пишет, слов «не прочитано» в выводе и в verified_by нет",
         we == 0 and "не прочитано" not in oe and len(re_) == 1 and "не прочитано" not in re_[0][4],
         f"код {we}\n{oe}")

    # ── У: след брошенного прогона — в отдельном TEMP, где нет каталогов от повисших прогонов ① ──
    tmp_u = work / f"tmp-u-{label}"
    tmp_u.mkdir()
    old_t = time.time() - STALE_AGE

    box = tmp_u / "find-owner-word"     # контейнер каталогов хода искателя (WORK_HOME)
    box.mkdir()

    def plant(name: str, files: dict, dir_old: bool, where: pathlib.Path = box) -> pathlib.Path:
        """Каталог с файлами {имя: старый ли}; время записи ставится руками."""
        d = where / name
        d.mkdir()
        for fname, is_old in files.items():
            f = d / fname
            f.write_text("{}\n", encoding="utf-8")
            if is_old:
                os.utime(f, (old_t, old_t))
        if dir_old:
            os.utime(d, (old_t, old_t))
        return d

    stale = plant("find-owner-word-stale001", {"job-1.json": True, "out-1.jsonl": True}, True)
    fresh = plant("find-owner-word-fresh001", {"out-1.jsonl": False}, False)
    mixed = plant("find-owner-word-mixed001", {"job-1.json": True, "out-1.jsonl": False}, True)
    alien = plant("other-tool-stale001", {"out-1.jsonl": True}, True)
    top_own = plant("find-owner-word-stale-top", {"job-1.json": True}, True, tmp_u)
    top_alien = plant("other-tool-stale-top", {"out-1.jsonl": True}, True, tmp_u)
    env_u = dict(base, TEMP=str(tmp_u), TMP=str(tmp_u), TMPDIR=str(tmp_u))
    u, ou, _ = find("охристый замок", env_u)
    left = sorted(p.name for p in box.iterdir())
    top = sorted(p.name for p in tmp_u.iterdir())
    case("Уа старый каталог хода в контейнере (два часа без записи) убран прогоном искателя",
         u == 0 and not stale.exists(), f"код {u} · в контейнере: {left}\n{ou}")
    case("Уб ВСТРЕЧНЫЙ: в контейнере свежий каталог хода, старый со свежим файлом и чужой старый — целы, "
         "свой каталог прогона убран",
         fresh.is_dir() and mixed.is_dir() and alien.is_dir()
         and set(left) <= {stale.name, fresh.name, mixed.name, alien.name},
         f"в контейнере: {left}")
    case("Уг ВСТРЕЧНЫЙ: вне контейнера уборка не трогает ничего — старый find-owner-word-* верхним уровнем "
         "Temp и чужой старый каталог целы",
         top_own.is_dir() and top_alien.is_dir(), f"в TEMP стенда верхним уровнем: {top}")
    v1, ov1, _ = find("охристый замок", env_u, "--read-timeout", "601")
    v2, ov2, _ = find("охристый замок", env_u, "--read-timeout", "600")
    case("Ув предел --read-timeout 601 с — отказ «больше 600 с», код 2; 600 с — обычный прогон, код 0",
         v1 == 2 and "ОТКАЗ МЕРИТЬ" in ov1 and "больше 600 с" in ov1 and v2 == 0,
         f"601: код {v1}\n{ov1}\n600: код {v2}\n{ov2}")
    return res


def show(res: dict) -> None:
    for name, (ok, detail) in res.items():
        print(f"  {'✅' if ok else '🔴'} {name}")
        if not ok and detail:
            for ln in detail.strip().splitlines()[:14]:
                print(f"       {ln}")


def main() -> int:
    print("=" * 96)
    print("ПРИЁМКА: искатель слова владельца не висит молча на чтении записи разговора — карточка #797")
    print(f"искатель: {TOOL}")
    print("=" * 96)
    for p in (TOOL, OWNER, BITE_FIND):
        if not p.is_file():
            print(f"⛔ ИСПЫТУЕМОГО НЕТ рядом: {p} — это отказ мерить, а не «чисто»")
            return 2
    failed: list = []
    with tempfile.TemporaryDirectory(prefix="bite-finder-hang-", ignore_cleanup_errors=True) as tmp:
        work = pathlib.Path(tmp)
        # ⛔ ПЕСОЧНИЦА ВСЕГО ДЕРЕВА ПРОЦЕССОВ — до первого дочернего процесса: поломки ⑤г и ⑤д
        # расширяют удаление, и любой вызов, ушедший со средой системы, исполнил бы его в
        # настоящем Temp (17.11, записка #6608). Наследуют все — и позванные с dict(os.environ)
        sand_tmp, sand_home = work / "sandbox-tmp", work / "sandbox-home"
        sand_tmp.mkdir()
        sand_home.mkdir()
        os.environ.update(TEMP=str(sand_tmp), TMP=str(sand_tmp), TMPDIR=str(sand_tmp),
                          HOME=str(sand_home), USERPROFILE=str(sand_home))
        tempfile.tempdir = str(sand_tmp)
        print(f"песочница: TEMP и HOME всего дерева процессов — внутри {work}")
        (work / "stub").mkdir()
        (work / "stub" / "sitecustomize.py").write_text(STUB, encoding="utf-8")
        release = work / "release.flag"
        try:
            print()
            print("── ИСПЫТУЕМЫЙ КАК ЕСТЬ ─────────────────────────────────────────────────────────────")
            res = run_cases(TOOL, BITE_FIND, work, "orig")
            show(res)
            failed += [n for n, (ok, _) in res.items() if not ok]

            original = TOOL.read_text(encoding="utf-8")
            for i, (key, title, (pattern, repl), prefix, sign) in enumerate(BREAKS, 1):
                print()
                print(f"── {key} НАРОЧНАЯ ПОЛОМКА: {title} " + "─" * max(4, 70 - len(title)))
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
                shutil.copy2(BITE_FIND, broken_dir / BITE_FIND.name)
                resb = run_cases(broken, broken_dir / BITE_FIND.name, work, f"broken{i}")
                fell = {n for n, (ok, _) in resb.items() if not ok}
                family = {n for n in resb if n.startswith(prefix)}
                fam = " и ".join(prefix)
                for n in resb:
                    mark = "пал" if n in fell else "цел"
                    print(f"     {'⚡' if (n in fell) == (n in family) else '🔴'} {mark}: {n}")
                exact = fell == family
                print(f"  {'✅' if exact else '🔴'} {key} {title} → не проходит РОВНО «{fam}» "
                      f"({len(family)} из {len(resb)}), остальные целы")
                if not exact:
                    failed.append(f"{key} поломка ломает не ровно «{fam}»")
                    for n in sorted(fell ^ family):
                        print(f"       ⟂ {n}")
                        for ln in resb[n][1].strip().splitlines()[:8]:
                            print(f"          {ln}")
                if sign:
                    first = next((n for n in resb if n.startswith("①а")), None)
                    seen = first is not None and sign in resb[first][1]
                    print(f"  {'✅' if seen else '🔴'} {key} признак у ①а: «{sign}»")
                    if not seen:
                        failed.append(f"{key} признака «{sign}» у ①а нет")
                        if first is not None:
                            for ln in resb[first][1].strip().splitlines()[:6]:
                                print(f"          {ln}")
        finally:
            # отпустить подставные зависания, чтобы брошенные читающие процессы кончились сами
            release.write_text("отпуск", encoding="utf-8")
            time.sleep(1.5)

    total = len(res)
    print()
    print("=" * 96)
    print(f"ИТОГ: {'пало ' + str(len(failed)) if failed else 'все случаи сошлись'} · случаев на испытуемом "
          f"{total} · нарочных поломок {len(BREAKS)}")
    for n in failed:
        print(f"   🔴 {n}")
    print("=" * 96)
    print("⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ, названо прямо:")
    print("   · НАСТОЯЩЕГО зависания чтения: подставное ждёт в обычном сне и снимается; «kill не действует»")
    print("     изображено подменой kill у искателя, а не ядром. Почему живое чтение встаёт, не известно;")
    print("   · что 30 с хватает живому чтению на любом диске: предел выбран по замеру зависаний, а не скорости;")
    print("   · уборку каталога, файлы которого ДЕРЖИТ живой повисший процесс: старый каталог на стенде подсажен")
    print("     без процесса. Это проверила TAXO прямым вызовом sweep_stale 17.11 (держимое цело, уборка")
    print("     на нём не встаёт) — не эта приёмка;")
    print("   · песочница держит только то, что идёт через среду: путь, впечатанный в код испытуемого,")
    print("     она не перенаправит. В find-owner-word.py путь Temp берётся только из tempfile;")
    print("   · зависание ВНЕ чтения файла (обход каталогов, время правки, уборка): их делает сам искатель,")
    print("     без предела.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
