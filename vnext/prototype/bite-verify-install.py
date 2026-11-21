#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-verify-install.py — приёмка карточки #819: команда scripts/verify-install.py сверяет тела
установленных файлов с записью установки (meta.template_files_sha) вне службы, только на чтение.

ЗАЧЕМ. Запись установки хранит пары «ключ файла → отпечаток тела». Служба отдаёт свёртку записи и
число файлов, но тел не перечитывает; сверка имён (guard-install-lag.py) тела тоже не читает.
Сверки «тела на диске равны телам по записи» не было нигде. Здесь проверяется команда, которая её делает.

КОМАНДА ИСПЫТУЕТСЯ НА СТЕНДЕ: приёмка собирает свой контур во временном каталоге (скрипты, база с
таблицей meta, ВТОРОЙ каталог установки, объявленный ключом prototype_install_dir файла путей) и
зовёт копию команды оттуда. Без стенда (mezo_stand) приёмка отказывается работать. Живой контур не
читается и не пишется; испытуемая копия — MEZO_SCRIPTS_ROOT (см. mezo_target).

СЛУЧАИ (имена держатся: по ним сверяется состав упавших при нарочных поломках)
  В1  ① только чтение: сводка ДО и ПОСЛЕ (отпечаток файла базы, побочные файлы базы, число файлов
      обоих каталогов и свёртка их отпечатков) не меняется
  В2  ② тот же код, что у установщика: в файле команды нет hashlib, sha256 и своей сборки ключа;
      встречный — отпечаток, подменённый в КОПИИ установщика, меняет ответ команды без правки её файла
  В3  ③ «совпало» на целом (число = числу пар записи); «нечем сверять» с РАЗНЫМИ причинами:
      записи нет · хранилище не читается · запись не разбирается · второй каталог не найден /
      не объявлен; слова «совпало» при этом исходе нет
  В4а ④ один значащий байт в файле ПЕРВОГО каталога: расходится, назван ровно этот ключ
  В4б ④ один значащий байт в файле ВТОРОГО каталога (имя то же, что в первом): назван ключ с приставкой
  В4в ⑧ граница отпечатка С ДРУГОЙ СТОРОНЫ: пробел в конце строки в СЕРЕДИНЕ файла — значащий байт,
      «расходится» (хвост срезается только у конца файла)
  В5  ⑤ переименование без смены тела: «совпало», строка «имя другое, тело то же» с обоими именами
  В6  ⑥ копия .bak: с изменённым телом — «лишнее тело», без правки — «второе имя того же тела»;
      исход прежний; число названо; список не обрезан
  В7  ⑦ файла записи нет и тела нет нигде: «тела нет на диске», код 1, отдельно от «тело изменено»
  В7б ⑦ файла записи нет, а то же тело держит ДРУГАЯ пара записи (одно имя в двух каталогах — так
      бывает у настоящих контуров): это не переименование — «тела нет на диске», код 1, пара названа
  В8  ⑧ границы отпечатка случаем: LF на CRLF и обратно, хвост файла — «совпало»; граница названа
      в выводе и в справке (встречный с другой стороны границы — случай В4в: он судит тело)
  В9  незнакомый аргумент и --db без значения — отказ словами, код 4; --help и --db=<путь> — код 0
  В10 граница ЗАПИСИ случаем: установщик на стенде принимает правку контура (--accept-merge --apply),
      запись получает отпечаток версии ПАКЕТА — команда отвечает «тело изменено», код 1, и говорит
      об этой границе в выводе и в справке
  В11 старшинство исходов (карточка #821, находка приёмки #819): второй каталог объявлен, но на диске его
      нет, И в файле первого каталога изменён один значащий байт — «расходится», код 1, число
      несверенных пар названо (несверенное не заслоняет найденное расхождение)
  В12 база стенда в режиме WAL: тот же исход, файл базы до и после прогона одинаков побайтно; побочные
      файлы -shm и -wal названы в строке случая
  В13 --db на копию базы вне контура: строка «сверяется: база … · каталог скриптов … · второй каталог — …»
      одна в каждом исходе и называет подставленную базу и каталоги контура как они есть
  В14 слова о строке «сверяется» судит случай (карточка #823): справка --help называет оба ранних исхода, где
      строки нет (установщик рядом не загрузился; контейнер группы не найден); при обычном вызове строка
      «сверяется:» стоит третьей; при незагрузившемся установщике её нет, ИТОГ — «нечем сверять», код 3
НАРОЧНЫЕ ПОЛОМКИ (в КОПИИ команды на стенде; якорь обязан найтись ровно один раз; все случаи части В
гоняются на копии, имена упавших сличаются с ожидаемыми)
  Л1  сверка по именам вместо тел          → В4а, В4б, В4в, В5, В10, В11, В12 (причины: «байт перестал
                                              ловиться» у В4а, В4б, В4в и В11; «переименование стало находкой»
                                              у В5; «принятая правка перестала выглядеть расхождением» у В10;
                                              «исход в режиме WAL другой» у В12)
  Л2  «лишнее тело» не называется          → В6
  Л3  «нечем сверять» выдано за «совпало»  → В3
  Л4  тело у другой пары записи считается переименованием → В7б
  Л5  «нечем сверять» выше «расходится»    → В11 (причина: «старшинство исходов нарушено»)

    python <каталог приёмок>/bite-verify-install.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402,F401
import mezo_target  # noqa: E402
import mezo_stand  # noqa: E402

if not hasattr(mezo_stand, "stand_env"):
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет stand_env (общий помощник среды стенда) — "
             "приёмка работает только на стенде; возьми помощник из той же версии пакета. Код 2 — отказ.")

ROOT = mezo_target.scripts_root()
UPDATE_TOOLS = mezo_target.script("update-tools.py")
COMMAND = ROOT / "verify-install.py"
print(f"⚖️ испытуется: копия {ROOT} (команда {COMMAND.name})")

OK = FAIL = 0


def case(name, cond, detail="", show=False):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail and (show or not cond):
        for line in str(detail).splitlines():
            print(f"   {line}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


ALL_NAMES = ["В1", "В2", "В3", "В4а", "В4б", "В4в", "В5", "В6", "В7", "В7б", "В8", "В9", "В10", "В11", "В12", "В13", "В14"]
TOTAL = len(ALL_NAMES) + 5          # + Л1, Л2, Л3, Л4, Л5

if not COMMAND.is_file():
    # Предмета ещё нет: приёмка не падает трассировкой, а говорит словами, что не прошла.
    print(f"🔴 команды нет: {COMMAND} не найден — случаи {', '.join(ALL_NAMES)} и нарочные поломки "
          f"Л1–Л5 не пройдены, испытывать нечего")
    print(f"\n🔴 ИТОГ: 0 из {TOTAL}")
    sys.exit(mezo_stand.finish(1))

STAND = mezo_stand.new("bite-verify-install-")
SECOND_PREFIX = "prototype-dir::/"       # приставка ключа файла второго каталога (своя, независимая от команды)

FIRST_FILES = {
    "a.py": b"# a\nA = 1\n",
    "b.py": b"# b\r\nB = 1\r\n",                 # тело записано с CRLF: нужен для случая «CRLF на LF»
    "migrations/m1.py": b"# m1\nM = 1\n",
}
SECOND_FILES = {
    "a.py": b"# second a\nSA = 1\n",              # то же имя, что в первом каталоге: ключи не должны слиться
    "p1.py": b"# p1\nP1 = 1\n",
    "p2.py": b"# p2\nP2 = 1\n",
}


def own_digest(data: bytes) -> str:
    """Независимая от команды сборка отпечатка для фикстур: опора приёмки, а не испытуемое."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


class Contour:
    def __init__(self, root: pathlib.Path):
        self.root = root                      # <стенд>/<имя>/.mezosync
        self.scripts = root / "scripts"
        self.second = root / "proto"
        self.db = root / "mezosync.db"
        self.paths_file = root / "local" / "paths.json"

    @property
    def container(self) -> pathlib.Path:
        return self.root.parent


def record_of(c: Contour, with_second: bool = True) -> dict:
    """Запись установки по тому, что лежит на диске СЕЙЧАС: первый каталог рекурсивно, второй сверху."""
    rec = {}
    for p in sorted(c.scripts.rglob("*")):
        if p.is_file() and "__pycache__" not in p.relative_to(c.scripts).parts:
            rec[p.relative_to(c.scripts).as_posix()] = own_digest(p.read_bytes())
    if with_second:
        for p in sorted(c.second.glob("*")):
            if p.is_file():
                rec[SECOND_PREFIX + p.name] = own_digest(p.read_bytes())
    return rec


PREFIX = [""]      # приставка имён контуров: прогон на копии с поломкой живёт в своих каталогах


def build(name: str, command: pathlib.Path = COMMAND, installer_text: str | None = None,
          declare_second: bool = True) -> Contour:
    """Контур для опыта: скрипты (установщик и его соседи, команда, файлы контура), второй каталог,
    база с таблицей meta и записью установки по всем файлам, файл путей со вторым каталогом.
    installer_text — текст КОПИИ установщика вместо настоящего (соседи при этом едут настоящие)."""
    c = Contour(STAND / (PREFIX[0] + name) / ".mezosync")
    c.scripts.mkdir(parents=True)
    mezo_stand.copy_tool(UPDATE_TOOLS, c.scripts)
    if installer_text is not None:
        (c.scripts / "update-tools.py").write_text(installer_text, encoding="utf-8")
    shutil.copy2(command, c.scripts / "verify-install.py")
    for rel, data in FIRST_FILES.items():
        (c.scripts / rel).parent.mkdir(parents=True, exist_ok=True)
        (c.scripts / rel).write_bytes(data)
    c.second.mkdir()
    for rel, data in SECOND_FILES.items():
        (c.second / rel).write_bytes(data)
    con = sqlite3.connect(str(c.db))
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?)",
                (json.dumps(record_of(c)),))
    con.commit()
    con.close()
    if declare_second:
        c.paths_file.parent.mkdir(parents=True, exist_ok=True)
        c.paths_file.write_text(json.dumps({"prototype_install_dir": c.second.resolve().as_posix()}),
                                encoding="utf-8")
    return c


def run(c: Contour, *args, name: str = "verify-install.py", timeout: int = 180):
    env = mezo_stand.stand_env(c.container, PYTHONIOENCODING="utf-8")
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    p = subprocess.run([sys.executable, str(c.scripts / name), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout, cwd=str(c.container))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fold(root: pathlib.Path, top_only: bool = False) -> tuple[int, str]:
    """(число файлов, свёртка путей и байтов) каталога — ВСЕ файлы, и __pycache__ тоже."""
    h, n = hashlib.sha256(), 0
    it = sorted(root.glob("*")) if top_only else sorted(root.rglob("*"))
    for p in it:
        if p.is_file():
            n += 1
            h.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0" + p.read_bytes() + b"\0")
    return n, h.hexdigest()[:12]


def summary(c: Contour) -> dict:
    side = sorted(n for n in os.listdir(c.root) if n.startswith("mezosync.db") and n != "mezosync.db")
    return {"база": hashlib.sha256(c.db.read_bytes()).hexdigest()[:12],
            "побочные файлы базы": side,
            "скрипты (файлов, свёртка)": fold(c.scripts),
            "второй каталог (файлов, свёртка)": fold(c.second)}


def markers(out: str) -> tuple:
    def count(prefix):
        return sum(1 for ln in out.splitlines() if ln.strip().startswith(prefix))
    word = next((w for w in ("СОВПАЛО", "РАСХОДИТСЯ", "НЕЧЕМ СВЕРЯТЬ") if f"ИТОГ: {w}" in out), "?")
    return (word, count("тело изменено:"), count("тела нет на диске:"),
            count("второе имя того же тела:"), count("лишнее тело:"))


def keys_of(out: str, prefix: str) -> list[str]:
    """Ключи строк, начатых prefix: «prefix КЛЮЧ  [подробности]» → КЛЮЧ."""
    res = []
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith(prefix):
            res.append(s[len(prefix):].strip().split("  ")[0].strip())
    return res


def lines_of(out: str, prefix: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith(prefix)]


def pair_count(c: Contour) -> int:
    con = sqlite3.connect(str(c.db))
    row = con.execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()
    con.close()
    return len(json.loads(row[0]))


def write_record(c: Contour) -> None:
    """Переписать запись установки по тому, что лежит на диске СЕЙЧАС (случай досадил свои файлы)."""
    con = sqlite3.connect(str(c.db))
    con.execute("UPDATE meta SET value=? WHERE key='template_files_sha'", (json.dumps(record_of(c)),))
    con.commit()
    con.close()


def record_value(c: Contour, key: str):
    con = sqlite3.connect(str(c.db))
    row = con.execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()
    con.close()
    return json.loads(row[0]).get(key)


# ═══ ФУНКЦИИ СЛУЧАЕВ: каждая → (прошло, тег причины, подробности); command — какая копия судится ═══

def case_b1(command):
    c = build("b1", command)
    before = summary(c)
    rc1, out1 = run(c)
    rc2, out2 = run(c, "--db", str(c.db))
    after = summary(c)
    ok = rc1 == 0 and rc2 == 0 and before == after and not after["побочные файлы базы"]
    detail = (f"код {rc1} / {rc2}\nДО:    {before}\nПОСЛЕ: {after}\n"
              f"побочные файлы базы: до {before['побочные файлы базы'] or 'нет'}, "
              f"после {after['побочные файлы базы'] or 'нет'}")
    return ok, "" if ok else "хранилище или каталоги изменились (или команда не отработала)", detail


def static_report(command) -> tuple[list[str], list[str]]:
    """(найденное лишнее, чего не хватает) в файле команды — разбором дерева, а не поиском по строкам:
    слово в комментарии не вызов."""
    tree = ast.parse(pathlib.Path(command).read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    extra, attrs = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "hashlib" for a in node.names):
            extra.append("import hashlib")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "hashlib":
            extra.append("from hashlib import …")
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
            if node.attr in ("sha256", "sha1", "md5", "blake2b", "hexdigest", "as_posix"):
                extra.append(f"вызов .{node.attr}")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
              and "prototype-dir" in node.value):
            extra.append("своя приставка ключа второго каталога")
    need = ["digest", "fingerprint_key", "second_install_dir", "install_path"]
    return extra, [n for n in need if n not in attrs]


def case_b2(command):
    extra, missing = static_report(command)
    # встречный: отпечаток подменён в КОПИИ установщика, файл команды тот же байт в байт
    text = UPDATE_TOOLS.read_text(encoding="utf-8")
    anchor = 'return hashlib.sha256(data.replace(b"\\r\\n", b"\\n").rstrip()).hexdigest()[:12]'
    if text.count(anchor) != 1:
        return False, "поломка не наложилась", f"якорь функции digest найден {text.count(anchor)} раз(а), нужен ровно 1"
    patched = text.replace(anchor, 'return "000000000000"  # ПОДМЕНА отпечатка (встречный случай)')
    results = []
    for tag, inst in (("норма", None), ("подмена", patched)):
        c = build("b2-" + ("n" if tag == "норма" else "p"), command, installer_text=inst)
        shutil.copy2(c.scripts / "b.py", c.scripts / "b.py.bak")          # копия без правки: второе имя тела
        rc, out = run(c)
        same_file = (c.scripts / "verify-install.py").read_bytes() == pathlib.Path(command).read_bytes()
        results.append((tag, rc, markers(out), same_file))
    (_, rc_n, mk_n, same_n), (_, rc_p, mk_p, same_p) = results
    changed = (rc_n, mk_n) != (rc_p, mk_p)
    ok = not extra and not missing and changed and same_n and same_p
    tag = ""
    if not ok:
        tag = ("в файле команды своя сверка отпечатка/ключа" if extra or missing
               else "ответ не зависит от отпечатка установщика")
    detail = (f"лишнее в файле команды: {extra or 'нет'}\nне хватает обращений к установщику: {missing or 'нет'}\n"
              f"с настоящим отпечатком: код {rc_n} {mk_n}\nс подменённым отпечатком: код {rc_p} {mk_p}\n"
              f"файл команды в обоих контурах равен испытуемому: {same_n and same_p}")
    return ok, tag, detail


def case_b3(command):
    notes, ok_all = [], True
    # целый контур
    c = build("b3-whole", command)
    rc, out = run(c)
    m = re.search(r"сверено файлов: (\d+)", out)
    n_named, n_pairs = (int(m.group(1)) if m else -1), pair_count(c)
    whole = rc == 0 and "ИТОГ: СОВПАЛО" in out and n_named == n_pairs
    notes.append(f"целый: код {rc}, названо файлов {n_named}, пар записи {n_pairs}")
    ok_all &= whole
    # нечем сверять — разные причины
    phrases = {"нет записи": "записи установки нет", "хранилище": "хранилище не читается",
               "не разбирается": "запись не разбирается", "второй не найден": "второй каталог не найден",
               "второй не объявлен": "второй каталог не объявлен"}
    outs = {}

    def con_exec(cc, sql, args=()):
        con = sqlite3.connect(str(cc.db))
        con.execute(sql, args)
        con.commit()
        con.close()

    v = build("b3-norec", command)
    con_exec(v, "DELETE FROM meta WHERE key='template_files_sha'")
    outs["нет записи"] = [run(v)]
    v = build("b3-unreadable", command)
    v.db.write_bytes("это не база данных".encode("utf-8") * 40)
    outs["хранилище"] = [run(v)]
    bad = []
    for i, value in enumerate(("{не json", "[1, 2]", '{"a.py": 5}')):
        v = build(f"b3-bad{i}", command)
        con_exec(v, "UPDATE meta SET value=? WHERE key='template_files_sha'", (value,))
        bad.append(run(v))
    outs["не разбирается"] = bad
    v = build("b3-nosecond", command)
    v.paths_file.write_text(json.dumps({"prototype_install_dir": (v.root / "нет-такого").as_posix()}),
                            encoding="utf-8")
    outs["второй не найден"] = [run(v)]
    v = build("b3-undeclared", command, declare_second=False)
    outs["второй не объявлен"] = [run(v)]
    for kind, runs in outs.items():
        for rc_k, out_k in runs:
            right = (rc_k == 3 and phrases[kind] in out_k and "совпало" not in out_k.lower()
                     and not any(p in out_k for k2, p in phrases.items() if k2 != kind))
            if kind.startswith("второй"):
                right = right and f"не сверено пар: {len(SECOND_FILES)}" in out_k
            notes.append(f"{kind}: код {rc_k} · «{phrases[kind]}» {'есть' if phrases[kind] in out_k else 'НЕТ'} · "
                         f"слово «совпало» {'ЕСТЬ' if 'совпало' in out_k.lower() else 'нет'}"
                         + ("" if right else f"\n{out_k}"))
            ok_all &= right
    tag = "" if ok_all else ("«нечем сверять» читается как «совпало» или причины не различаются"
                             if whole else "целый контур не дал «совпало»")
    return ok_all, tag, "\n".join(notes)


def mutate(path: pathlib.Path, old: bytes, new: bytes) -> None:
    data = path.read_bytes()
    assert data.count(old) == 1, (path, old)
    path.write_bytes(data.replace(old, new))


def case_b4(command, which):
    c = build("b4" + which, command)
    if which == "a":
        mutate(c.scripts / "a.py", b"A = 1", b"A = 2")
        expect = "a.py"
    elif which == "c":
        mutate(c.scripts / "a.py", b"# a\n", b"# a \n")      # пробел в конце строки в СЕРЕДИНЕ файла
        expect = "a.py"
    else:
        mutate(c.second / "a.py", b"SA = 1", b"SA = 2")
        expect = SECOND_PREFIX + "a.py"
    rc, out = run(c)
    changed, gone = keys_of(out, "тело изменено:"), keys_of(out, "тела нет на диске:")
    ok = rc == 1 and "ИТОГ: РАСХОДИТСЯ" in out and changed == [expect] and not gone
    tag = ""
    if not ok:
        tag = "байт перестал ловиться" if "ИТОГ: СОВПАЛО" in out else "назван не тот ключ или лишние расхождения"
    return ok, tag, f"код {rc} · «тело изменено»: {changed} (ждали [{expect!r}]) · «тела нет»: {gone}\n{out}"


def case_b5(command):
    c = build("b5", command)
    (c.scripts / "b.py").rename(c.scripts / "b-renamed.py")
    (c.second / "p2.py").rename(c.second / "p2-moved.py")
    rc, out = run(c)
    ren = lines_of(out, "имя другое, тело то же:")
    two = (any("b.py" in ln and "b-renamed.py" in ln for ln in ren)
           and any("p2.py" in ln and "p2-moved.py" in ln for ln in ren))
    diverging = keys_of(out, "тело изменено:") + keys_of(out, "тела нет на диске:")
    ok = rc == 0 and "ИТОГ: СОВПАЛО" in out and two and not diverging
    tag = ""
    if not ok:
        tag = "переименование стало находкой" if "ИТОГ: РАСХОДИТСЯ" in out else "переименование названо не так"
    return ok, tag, f"код {rc} · строки о переименовании: {ren} · среди расходящихся: {diverging}\n{out}"


def case_b6(command):
    c = build("b6", command)
    (c.scripts / "a.py.bak").write_bytes(FIRST_FILES["a.py"].replace(b"A = 1", b"A = 7"))      # лишнее тело
    (c.scripts / "b.py.bak").write_bytes((c.scripts / "b.py").read_bytes())                      # второе имя
    (c.second / "p1.py.bak").write_bytes(SECOND_FILES["p1.py"].replace(b"P1 = 1", b"P1 = 7"))    # лишнее, во втором
    for i in range(37):
        (c.scripts / f"junk-{i:02d}.bak").write_bytes(f"# junk {i}\nJ = {i}\n".encode())
    rc, out = run(c)
    extra, second = lines_of(out, "лишнее тело:"), lines_of(out, "второе имя того же тела:")
    hx = re.search(r"Лишние тела[^\n]*?: (\d+)", out)
    hs = re.search(r"Вторые имена[^\n]*?: (\d+)", out)
    named = (hx and int(hx.group(1))), (hs and int(hs.group(1)))
    expect = (39, 1)
    ok = (rc == 0 and "ИТОГ: СОВПАЛО" in out and len(extra) == 39 and len(second) == 1 and named == expect
          and any("a.py.bak" in ln for ln in extra) and any("p1.py.bak" in ln for ln in extra)
          and any("b.py.bak" in ln and "b.py" in ln for ln in second)
          and not any("b.py.bak" in ln for ln in extra))
    tag = "" if ok else "лишнее тело не названо или названо иначе"
    return ok, tag, (f"код {rc} · лишних строк {len(extra)} (ждали 39), заголовок {named[0]} · "
                     f"вторых имён строк {len(second)} (ждали 1), заголовок {named[1]}\n{out[-1500:]}")


def case_b7(command):
    c = build("b7", command)
    (c.scripts / "a.py").unlink()
    (c.second / "p1.py").unlink()
    rc, out = run(c)
    gone, changed = keys_of(out, "тела нет на диске:"), keys_of(out, "тело изменено:")
    ok = (rc == 1 and "ИТОГ: РАСХОДИТСЯ" in out and sorted(gone) == sorted(["a.py", SECOND_PREFIX + "p1.py"])
          and not changed)
    return ok, "" if ok else "удаление не названо «тела нет на диске»", \
        f"код {rc} · «тела нет»: {gone} · «тело изменено»: {changed}\n{out}"


def case_b7b(command):
    c = build("b7b", command)
    twin = b"# m\nSAME = 1\n"            # одно тело под одним именем в ОБОИХ каталогах, обе пары в записи
    (c.scripts / "m.py").write_bytes(twin)
    (c.second / "m.py").write_bytes(twin)
    write_record(c)
    rc0, out0 = run(c)
    (c.scripts / "m.py").unlink()
    rc, out = run(c)
    gone, ren = keys_of(out, "тела нет на диске:"), lines_of(out, "имя другое, тело то же:")
    named_twin = any(SECOND_PREFIX + "m.py" in ln for ln in lines_of(out, "тела нет на диске:"))
    ok = (rc0 == 0 and "ИТОГ: СОВПАЛО" in out0 and rc == 1 and "ИТОГ: РАСХОДИТСЯ" in out
          and gone == ["m.py"] and not ren and named_twin)
    tag = ""
    if not ok:
        tag = ("удалённый файл выдан за переименование" if "ИТОГ: СОВПАЛО" in out or ren
               else "удаление при теле у другой пары записи названо не так")
    return ok, tag, (f"до удаления: код {rc0} · после: код {rc} · «тела нет»: {gone} (ждали ['m.py']) · "
                     f"строки о переименовании: {ren} · другая пара названа: {named_twin}\n{out}")


ACCEPT_WORDS = ("--accept-merge", "версии ПАКЕТА")


def case_b10(command):
    c = build("b10", command)
    pack_text = b"# a\nA = 1\nPACK = 2\n"         # версия пакета, с которой сводили
    draft = pack_text + b"LOCAL = 7\n"             # черновик сведения: версия пакета и правка контура
    d = c.root / "merge-work" / "a.py"             # куда установщик кладёт черновик и его описание
    d.mkdir(parents=True)
    (d / "a.py").write_bytes(draft)
    (d / "meta.json").write_text(json.dumps({"rel": "a.py", "pack_fingerprint": own_digest(pack_text),
                                             "pack_rev_at_merge": "стенд"}), encoding="utf-8")
    rc_a, out_a = run(c, "--accept-merge", "a.py", "--apply", "--db", str(c.db), name="update-tools.py")
    accepted = (rc_a == 0 and (c.scripts / "a.py").read_bytes() == draft
                and record_value(c, "a.py") == own_digest(pack_text))
    rc, out = run(c)
    changed = keys_of(out, "тело изменено:")
    stated = all(w in out for w in ACCEPT_WORDS)
    rc_h, out_h = run(c, "--help")
    in_help = rc_h == 0 and all(w in out_h for w in ACCEPT_WORDS)
    ok = accepted and rc == 1 and changed == ["a.py"] and stated and in_help
    tag = ""
    if not ok:
        tag = ("установщик на стенде не принял черновик" if not accepted else
               "принятая правка перестала выглядеть расхождением" if rc != 1 or changed != ["a.py"] else
               "граница записи не названа в выводе или в справке")
    return ok, tag, (f"установщик: код {rc_a}; файл получил черновик, а запись — отпечаток версии пакета: {accepted} · "
                     f"команда: код {rc} · «тело изменено»: {changed} (ждали ['a.py']) · "
                     f"граница в выводе {stated} · в справке {in_help}\n{out_a[-700:]}\n{out}")


BOUNDARY_WORDS = ("окончаниями строк", "расхождением не считается")


def case_b8(command):
    c = build("b8", command)
    (c.scripts / "a.py").write_bytes(FIRST_FILES["a.py"].replace(b"\n", b"\r\n"))         # LF → CRLF
    (c.scripts / "b.py").write_bytes(FIRST_FILES["b.py"].replace(b"\r\n", b"\n"))         # CRLF → LF
    (c.second / "p1.py").write_bytes(SECOND_FILES["p1.py"] + b"   \n\n  \t\n")            # хвост файла
    rc, out = run(c)
    same = rc == 0 and "ИТОГ: СОВПАЛО" in out and not keys_of(out, "тело изменено:")
    stated = all(w in out for w in BOUNDARY_WORDS)
    rc_h, out_h = run(c, "--help")
    in_help = rc_h == 0 and all(w in out_h for w in BOUNDARY_WORDS)
    ok = same and stated and in_help
    tag = "" if ok else ("смена окончаний строк или хвоста стала расхождением" if not same else
                         "граница не названа в выводе или в справке")
    return ok, tag, (f"код {rc} · «совпало» {same} · граница в выводе {stated} · "
                     f"граница в справке {in_help}\n{out}")


def case_b9(command):
    c = build("b9", command)
    rc1, out1 = run(c, "--bogus")
    rc2, out2 = run(c, "--db")
    rc3, out3 = run(c, "--help")
    rc4, out4 = run(c, "лишнее-слово")
    rc5, out5 = run(c, f"--db={c.db}")
    ok = (rc1 == 4 and "незнакомый аргумент" in out1 and "ИТОГ" not in out1 and rc2 == 4 and "ИТОГ" not in out2
          and rc3 == 0 and rc4 == 4 and rc5 == 0 and "ИТОГ: СОВПАЛО" in out5)
    return ok, "" if ok else "отказ по аргументам не код 4 или форма --db=<путь> не принята", \
        f"--bogus: {rc1} · --db без значения: {rc2} · --help: {rc3} · слово: {rc4} · --db=<путь>: {rc5}\n{out1}{out2}"


SCOPE_RE = re.compile(r"^сверяется: база (.+?) · каталог скриптов (.+?) · второй каталог — (.+)$")


def scope_lines(out: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith("сверяется:")]


def same_path(a: str, b) -> bool:
    return os.path.normcase(str(pathlib.Path(a).resolve())) == os.path.normcase(str(pathlib.Path(b).resolve()))


def case_b11(command):
    """Старшинство исходов: второй каталог объявлен, но его нет (пары второго каталога не сверены), И в файле первого каталога
    изменён один значащий байт. Исход — «расходится», код 1, число несверенных пар названо."""
    c = build("b11", command)
    shutil.rmtree(c.second)                                  # объявлен в файле путей, на диске его нет
    mutate(c.scripts / "a.py", b"A = 1", b"A = 2")
    rc, out = run(c)
    changed = keys_of(out, "тело изменено:")
    n_second = len(SECOND_FILES)
    named = f"не сверено пар: {n_second}" in out
    ok = rc == 1 and "ИТОГ: РАСХОДИТСЯ" in out and changed == ["a.py"] and named
    tag = ""
    if not ok:
        tag = "старшинство исходов нарушено" if changed else "байт перестал ловиться"
    return ok, tag, (f"код {rc} · «тело изменено»: {changed} (ждали ['a.py']) · число несверенных пар названо ({n_second}): {named}\n{out}")


def db_header_mode(db: pathlib.Path) -> tuple:
    head = db.read_bytes()[:20]
    return head[18], head[19]           # 1, 1 — журнал отката; 2, 2 — режим WAL


def case_b12(command):
    """База стенда в режиме WAL: тот же исход, файл базы не меняется ни байтом; побочные файлы -shm и -wal названы в строке случая."""
    c = build("b12", command)
    con = sqlite3.connect(str(c.db))
    mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    con.commit()
    con.close()
    mutate(c.scripts / "a.py", b"A = 1", b"A = 2")
    before = hashlib.sha256(c.db.read_bytes()).hexdigest()[:12]
    head_before = db_header_mode(c.db)
    rc, out = run(c)
    after = hashlib.sha256(c.db.read_bytes()).hexdigest()[:12]
    side = sorted(n for n in os.listdir(c.root) if n.startswith("mezosync.db") and n != "mezosync.db")
    changed = keys_of(out, "тело изменено:")
    expected_side = {"mezosync.db-shm", "mezosync.db-wal"}
    ok = (mode == "wal" and head_before == (2, 2) and before == after and rc == 1 and "ИТОГ: РАСХОДИТСЯ" in out
          and changed == ["a.py"] and set(side) <= expected_side)
    tag = ""
    if not ok:
        tag = ("файл базы изменился" if before != after else
               "стенд не в режиме WAL" if mode != "wal" or head_before != (2, 2) else
               "лишние побочные файлы базы" if not set(side) <= expected_side else
               "исход в режиме WAL другой")
    return ok, tag, (f"режим {mode}, заголовок {head_before} · файл базы до {before}, после {after} · код {rc} · «тело изменено»: {changed} · "
                     f"побочные файлы базы после прогона: {side or 'нет'}")


def case_b13(command):
    """--db указывает на копию базы ВНЕ контура: строка «сверяется» одна в каждом исходе и называет подставленную базу, а каталоги
    контура — как они есть (скрипты — контура; второй каталог — по файлу путей рядом с копией, не по файлу контура)."""
    c = build("b13", command)
    outside = STAND / f"{PREFIX[0]}outside-b13"
    (outside / "local").mkdir(parents=True)
    copy_db = outside / "copy.db"
    shutil.copy2(c.db, copy_db)
    notes = []

    def parse(out, label):
        lines = scope_lines(out)
        if len(lines) != 1:
            notes.append(f"{label}: строк «сверяется:» {len(lines)}, ждали одну")
            return None
        m = SCOPE_RE.match(lines[0])
        if not m:
            notes.append(f"{label}: строка не по форме: {lines[0][:120]}")
        return m

    rc_a, out_a = run(c, "--db", str(copy_db))                  # (а) копия без файла путей: второй каталог не объявлен
    m = parse(out_a, "копия без файла путей")
    if m:
        if not same_path(m.group(1), copy_db):
            notes.append(f"(а) база в строке {m.group(1)}, ждали {copy_db}")
        if not same_path(m.group(2), c.scripts):
            notes.append(f"(а) каталог скриптов в строке {m.group(2)}, ждали {c.scripts}")
        if m.group(3).strip() != "не объявлен":
            notes.append(f"(а) второй каталог в строке «{m.group(3)[:60]}», ждали «не объявлен»")
    if rc_a != 3:
        notes.append(f"(а) код {rc_a}, ждали 3 (нечем сверять: второй каталог не объявлен)")
    (outside / "local" / "paths.json").write_text(json.dumps({"prototype_install_dir": c.second.resolve().as_posix()}), encoding="utf-8")
    rc_b, out_b = run(c, "--db", str(copy_db))                  # (б) с файлом путей рядом с копией
    m = parse(out_b, "копия с файлом путей")
    if m:
        if not same_path(m.group(1), copy_db) or not same_path(m.group(2), c.scripts) or not same_path(m.group(3), c.second):
            notes.append(f"(б) строка называет не те места: {m.group(0)[:200]}")
    if rc_b != 0:
        notes.append(f"(б) код {rc_b}, ждали 0")
    con = sqlite3.connect(str(copy_db))
    con.execute("DELETE FROM meta WHERE key='template_files_sha'")
    con.commit()
    con.close()
    rc_c, out_c = run(c, "--db", str(copy_db))                  # (в) в копии записи нет: исход «нечем сверять», строка всё равно одна
    parse(out_c, "копия без записи")
    if rc_c != 3:
        notes.append(f"(в) код {rc_c}, ждали 3")
    rc_d, out_d = run(c)                                          # (г) без --db: база контура
    m = parse(out_d, "без --db")
    if m and not (same_path(m.group(1), c.db) and same_path(m.group(2), c.scripts) and same_path(m.group(3), c.second)):
        notes.append(f"(г) без --db строка называет не те места: {m.group(0)[:200]}")
    ok = not notes and rc_d == 0
    shown = scope_lines(out_b)
    return ok, "" if ok else "строка о том, что сверяется, не одна или называет не то", (
        f"коды: копия без файла путей {rc_a} · с файлом путей {rc_b} · без записи {rc_c} · без --db {rc_d}\n"
        f"строка (б): {shown[0] if shown else '—'}\n" + "\n".join(notes))


def case_b14(command):
    """Слова о строке «сверяется» судит случай: справка называет два ранних исхода без строки; обычный вызов — строка третья;
    установщик не загрузился — строки нет, код 3 (второй ранний исход — «контейнер группы не найден» — назван справкой)."""
    notes = []
    c = build("b14", command)
    rc_h, out_h = run(c, "--help")
    for phrase in ("третьей строкой", "установщик рядом с командой не загрузился", "контейнер группы не найден"):
        if phrase not in out_h:
            notes.append(f"справка не содержит «{phrase}»")
    if rc_h != 0:
        notes.append(f"--help: код {rc_h}, ждали 0")
    rc, out = run(c)
    lines = [x for x in out.splitlines() if x.strip()]
    if len(lines) < 3 or not lines[2].startswith("сверяется:"):
        notes.append(f"при обычном вызове третья строка не «сверяется:»: {lines[2][:80] if len(lines) > 2 else '—'}")
    if len(scope_lines(out)) != 1:
        notes.append(f"при обычном вызове строк «сверяется:» {len(scope_lines(out))}, ждали одну")
    broken = build("b14-noinst", command, installer_text='raise RuntimeError("fixture: installer does not load")\n')
    rc_b, out_b = run(broken)
    if scope_lines(out_b):
        notes.append("при незагрузившемся установщике строка «сверяется:» напечатана")
    if rc_b != 3:
        notes.append(f"при незагрузившемся установщике код {rc_b}, ждали 3")
    ok = not notes
    return ok, "" if ok else "слова о строке «сверяется» разошлись с делом", (
        f"коды: --help {rc_h} · обычный {rc} · установщик не загрузился {rc_b}\n" + "\n".join(notes))


CASE_FUNCS = {
    "В1": case_b1, "В2": case_b2, "В3": case_b3,
    "В4а": lambda cmd: case_b4(cmd, "a"), "В4б": lambda cmd: case_b4(cmd, "b"),
    "В4в": lambda cmd: case_b4(cmd, "c"),
    "В5": case_b5, "В6": case_b6, "В7": case_b7, "В7б": case_b7b, "В8": case_b8, "В9": case_b9,
    "В10": case_b10, "В11": case_b11, "В12": case_b12, "В13": case_b13, "В14": case_b14,
}
TITLES = {
    "В1": "① только чтение: хранилище и каталоги до и после прогона не изменены ни байтом",
    "В2": "② тот же код, что у установщика: своей сверки нет; подмена отпечатка в копии установщика меняет ответ",
    "В3": "③ «совпало» на целом, число = числу пар; «нечем сверять» с разными причинами, без слова «совпало»",
    "В4а": "④ один значащий байт в файле первого каталога — «расходится», назван ровно этот ключ",
    "В4б": "④ один значащий байт в файле второго каталога — «расходится», назван ключ с приставкой",
    "В4в": "⑧ граница с другой стороны: пробел в конце строки в середине файла — «расходится»",
    "В5": "⑤ переименование без смены тела — «совпало», «имя другое, тело то же» с обоими именами",
    "В6": "⑥ копия .bak: изменённое тело — «лишнее тело», тело из записи — «второе имя»; число названо, список цел",
    "В7": "⑦ файла записи нет — «тела нет на диске», код 1, отдельно от «тело изменено»",
    "В7б": "⑦ файла записи нет, а тело держит другая пара записи — «тела нет на диске», не переименование",
    "В8": "⑧ границы отпечатка случаем: окончания строк и хвост файла — «совпало»; граница в выводе и справке",
    "В9": "отказ по аргументам — код 4 словами; --help и --db=<путь> — код 0",
    "В10": "граница записи: правка, принятая установщиком (--accept-merge), — «тело изменено»; сказано в выводе и справке",
    "В11": "старшинство исходов: второй каталог объявлен, но не найден, И изменён байт в первом — «расходится», код 1, несверенное названо",
    "В12": "база стенда в режиме WAL: тот же исход, файл базы не изменён ни байтом, побочные файлы -shm и -wal названы",
    "В13": "--db на копию базы вне контура: строка «сверяется» одна в каждом исходе и называет подставленную базу и каталоги контура",
    "В14": "слова о строке «сверяется» судит случай: справка называет оба ранних исхода; обычный вызов — строка третья; установщик не загрузился — строки нет, код 3",
}


def run_all(command, verbose: bool):
    res = {}
    for name in ALL_NAMES:
        ok, tag, detail = CASE_FUNCS[name](command)
        res[name] = (ok, tag, detail)
        if verbose:
            case(f"{name} {TITLES[name]}", ok, detail, show=(name in ("В1", "В2", "В12", "В13")))
    return res


print("---- часть В: случаи на копии команды ----")
MAIN = run_all(COMMAND, verbose=True)

# ═══ НАРОЧНЫЕ ПОЛОМКИ — в КОПИИ команды на стенде; файл дерева не трогается ═══
BREAKS = {
    "Л1": ("сверка по именам вместо тел: «есть файл — совпало, нет файла — находка»",
           [("        state = judge_pair(on_disk, recorded, holders)\n",
             '        state = "ok" if on_disk is not None else "gone"  # ПОЛОМКА Л1: по именам\n')],
           {"В4а", "В4б", "В4в", "В5", "В10", "В11", "В12"},
           {"В4а": "байт перестал ловиться", "В4б": "байт перестал ловиться",
            "В4в": "байт перестал ловиться", "В5": "переименование стало находкой",
            "В10": "принятая правка перестала выглядеть расхождением",
            "В11": "байт перестал ловиться", "В12": "исход в режиме WAL другой"}),
    "Л2": ("«лишнее тело» не называется",
           [('    return "лишнее"\n', "    return None  # ПОЛОМКА Л2: лишнее не называется\n")],
           {"В6"}, {"В6": "лишнее тело не названо или названо иначе"}),
    "Л3": ("«нечем сверять» выдано за «совпало»",
           [('    print(f"ИТОГ: НЕЧЕМ СВЕРЯТЬ — {reason}")\n',
             '    print(f"ИТОГ: СОВПАЛО — {reason}")  # ПОЛОМКА Л3: нечем сверять выдано за совпало\n')],
           {"В3"}, {}),
    "Л4": ("тело у другой пары записи считается переименованием",
           [("        holders = [k for k in same_body if k not in pairs]      # переименование — только имя ВНЕ записи\n",
             "        holders = same_body  # ПОЛОМКА Л4: имя другой пары записи считается переименованием\n")],
           {"В7б"}, {"В7б": "удалённый файл выдан за переименование"}),
    "Л5": ("«нечем сверять» поставлено выше «расходится»: при несверенных парах изменённое тело не даёт исхода «расходится»",
           [("    if changed or gone:\n        parts = [", "    if (changed or gone) and not unverified:  # ПОЛОМКА Л5: нечем сверять выше расходится\n        parts = [")],
           {"В11"}, {"В11": "старшинство исходов нарушено"}),
}

print("---- часть Л: нарочные поломки в копии команды ----")
cmd_text = COMMAND.read_text(encoding="utf-8")
for tag, (what, edits, expected, reasons) in BREAKS.items():
    broken_dir = STAND / f"break-{tag}"
    broken_dir.mkdir()
    broken = broken_dir / "verify-install.py"
    text, missed = cmd_text, []
    for old, new in edits:
        if text.count(old) != 1:
            missed.append(f"{old.strip()!r}: найдено {text.count(old)} раз(а), нужно ровно 1")
        else:
            text = text.replace(old, new)
    if missed:
        case(f"{tag} {what} — поломка не наложилась", False, "\n".join(missed))
        continue
    broken.write_text(text, encoding="utf-8")
    PREFIX[0] = f"{tag}-"
    res = run_all(broken, verbose=False)
    PREFIX[0] = ""
    failed = {n for n, (ok, _, _) in res.items() if not ok}
    tags_ok = all(res[n][1] == t for n, t in reasons.items())
    detail = (f"судилась копия: {broken}\nупали: {sorted(failed)} · ждали: {sorted(expected)}\n"
              + "\n".join(f"{n}: причина «{res[n][1]}»" for n in sorted(failed)))
    case(f"{tag} ПОЛОМКА «{what}» валит ровно {', '.join(sorted(expected))}" +
         (" — каждого своей причиной" if reasons else ""),
         failed == expected and tags_ok, detail, show=True)

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
