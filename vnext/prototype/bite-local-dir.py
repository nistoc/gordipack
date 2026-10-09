#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-local-dir.py — приёмка этапа Э5 (карточка #679): местное контура живёт в
<каталог базы>/local/, обновление его не трогает, а файл пакета, правленый у контура, отдаётся
пакету без сведения.

ПОВОД. Потребитель (AIA) вписал свои проверки прямо в guard-all.py пакета. Файл перестал быть
равен пакету, и каждое обновление вставало на «✋ ПРАВЛЕН У ТЕБЯ» и шло через --merge — ручное
сведение. Критерий этапа: обновление со своей правкой guard-all — без ручного сведения.

ЧТО ИСПЫТЫВАЕТСЯ (копии из MEZO_SCRIPTS_ROOT, по умолчанию — живые; см. mezo_target):
  guard-all.py ... местные проверки из local/checks.json (функции local_checks, run_local_checks)
  update-tools.py  строка о каталоге местного; --apply не пишет в local/; --release
  backup-db.py ... каталог местного едет в копию целиком (local-copy/)

СЛУЧАИ
  Г1  перечня нет — местных строк нет, провалов нет; с --full — «местных проверок нет»
  Г2  проходящая местная проверка — «ℹ️ местных проверок: 1», в прошедших «местная · …»
  Г3  падающая местная проверка — провал под именем «местная · …»
  Г4  скрипта нет — провал «скрипт местной проверки не найден» с путём
  Г5  перечень не JSON — провал «перечень не читается»
  Г6  неизвестное поле записи («arg» вместо «args») — провал «неизвестные поля arg»
  Г7  --skip по имени без приставки — «пропущен по --skip», провала нет
  Г8  «{db}» в аргументах заменён путём базы прогона
  Г9  одно имя дважды — провал
  Г10 main() guard-all.py зовёт run_local_checks(skip) (разбор исходника)
  Г11 общий прогон на копии контура: строка местных, падающая местная — в списке провалов
  О1  план печатает строку «🏠 местное» с числом файлов; встречный — «каталога нет»
  О2  --apply (свежий файл берётся) не меняет в local/ ни байта
  О3  план с --release: «⇄ <файл>», файл не тронут, копий нет
  О4  --apply --release ✋ и ❓: файлы = пакет, прежний текст — копией в released/<час>/,
      отпечаток = версия пакета, local/ не тронут, следующий план — «совпадают»
  О5  --release файла, которого нет в пакете — отказ словами
  О6  --release файла, равного пакету — «уже равен пакету»
  О7  --release файла без своей правки — «обновится и без --release»
  О8  --release вместе с --merge — отказ
  Б1  backup-db без --apply — строка «попадёт в копию», каталога копии нет
  Б2  backup-db --apply — local-copy/ = local/ побайтно
  Б3  файл убран из local/ — убран и из копии, строка называет число
  Б4  кэш байт-кода (__pycache__) в копию не едет, остальное — едет
  Б5  выгрузка внутри local/ — копии нет, строка «НЕ попал»
НАРОЧНЫЕ ПОЛОМКИ (в копиях испытуемых; каждая обязана уронить ровно названное)
  П1  вызов run_local_checks убран из main()            → Г10
  П2  --release без копии прежнего текста               → О4
  П3  --release не ставит версию пакета                  → О4
  П4  строка «🏠 местное» не печатается                  → О1
  П5  исчезнувшие из local/ файлы остаются в копии      → Б3
  П6  кэш байт-кода едет в копию                         → Б4
  П7  копия ложится внутрь самого local/                 → Б5

⛔ Живая база только читается (снимок через mezo_stand.snapshot_db). Пакет не трогается:
источник для update-tools — синтетический каталог внутри стенда.

    MEZO_SCRIPTS_ROOT=<клон пакета>/scripts python <клон пакета>/vnext/prototype/bite-local-dir.py
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402
import mezo_stand  # noqa: E402

GUARD_ALL = mezo_target.script("guard-all.py")
UPDATE_TOOLS = mezo_target.script("update-tools.py")
BACKUP_DB = mezo_target.script("backup-db.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

STAND = mezo_stand.new("bite-679-local-")
OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail and not cond:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def tree_digest(root: Path) -> str:
    """Отпечаток каталога: пути и байты всех файлов. Нет каталога — «нет»."""
    if not root.is_dir():
        return "нет"
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0" + p.read_bytes())
    return h.hexdigest()[:12]


def broken_copy(tool: Path, dest_dir: Path, old: str, new: str) -> Path:
    """Копия испытуемого с нарочной поломкой; строка обязана найтись ровно один раз."""
    text = tool.read_text(encoding="utf-8")
    if text.count(old) != 1:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: строка поломки встречается {text.count(old)} раз в {tool} "
                 f"(нужно ровно 1): {old!r}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    mezo_stand.copy_tool(tool, dest_dir)
    (dest_dir / tool.name).write_text(text.replace(old, new), encoding="utf-8")
    return dest_dir / tool.name


# ═══ ЧАСТЬ Г — местные проверки guard-all.py ═══════════════════════════════════════════════════

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GUARD_FUNCS = ("check", "sub_guard", "local_checks", "run_local_checks")
GUARD_CONSTS = ("LOCAL_CHECK_KEYS", "LOCAL_CHECK_PREFIX")


def guard_namespace(source_file: Path, db: Path, full: bool = False) -> dict:
    """Функции местных проверок ИЗ ИСХОДНИКА испытуемого guard-all.py — в своё пространство
    имён с подставными глобальными (база, счётчики). Испытывается настоящий текст функций."""
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    ns = {"json": json, "Path": Path, "subprocess": subprocess, "sys": sys, "os": os,
          "mezo_paths": load_module(source_file.parent / "mezo_paths.py", "mezo_paths_under_test"),
          "DB": db, "FULL": full, "RESULTS": [], "GREENS": [], "SCRIPTS": db.parent / "scripts",
          "installed_fingerprints": lambda: {}}
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in GUARD_FUNCS:
            exec(ast.get_source_segment(source, node), ns)  # noqa: S102 — исходник испытуемого
            found.add(node.name)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in GUARD_CONSTS for t in node.targets):
            exec(ast.get_source_segment(source, node), ns)  # noqa: S102
            found.update(t.id for t in node.targets if isinstance(t, ast.Name))
    missing = set(GUARD_FUNCS + GUARD_CONSTS) - found
    if missing:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {source_file} нет {', '.join(sorted(missing))}")
    return ns


def run_local(db: Path, checks, skip=(), full=False, raw: str | None = None):
    """Положить перечень (или сырой текст) и прогнать run_local_checks → (вывод, RESULTS, GREENS)."""
    local = db.parent / "local"
    local.mkdir(parents=True, exist_ok=True)
    lst = local / "checks.json"
    if raw is not None:
        lst.write_text(raw, encoding="utf-8")
    elif checks is None:
        lst.unlink(missing_ok=True)
    else:
        lst.write_text(json.dumps({"checks": checks}, ensure_ascii=False), encoding="utf-8")
    ns = guard_namespace(GUARD_ALL, db, full)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ns["run_local_checks"](set(skip))
    return buf.getvalue(), ns["RESULTS"], ns["GREENS"]


g_root = STAND / "g" / ".mezosync"
(g_root / "local" / "checks").mkdir(parents=True)
g_db = g_root / "mezosync.db"
sqlite3.connect(str(g_db)).close()
(g_root / "local" / "checks" / "ok.py").write_text("print('✅ местное в порядке')\n", encoding="utf-8")
(g_root / "local" / "checks" / "bad.py").write_text(
    "import sys\nprint('⛔ местная беда: 1')\nsys.exit(1)\n", encoding="utf-8")
ARGV_OUT = STAND / "g" / "argv.json"
(g_root / "local" / "checks" / "argv.py").write_text(
    "import json, sys\nopen(r'" + str(ARGV_OUT) + "', 'w', encoding='utf-8')"
    ".write(json.dumps(sys.argv[1:]))\nprint('✅ аргументы записаны')\n", encoding="utf-8")

print("---- часть Г: местные проверки общего прогона ----")
out, res, _ = run_local(g_db, None)
case("Г1 перечня нет — местных строк и провалов нет", not res and "местн" not in out, out)
out, res, _ = run_local(g_db, None, full=True)
case("Г1 с --full — «местных проверок нет: файла … нет»", "местных проверок нет" in out and not res, out)

out, res, greens = run_local(g_db, [{"name": "проба", "script": "checks/ok.py"}])
case("Г2 проходящая местная проверка — строка «ℹ️ местных проверок: 1» и «местная · проба» в прошедших",
     "ℹ️ местных проверок: 1" in out and res == [("местная · проба", True, "✅ местное в порядке")]
     and "местная · проба" in greens, f"{out}\n   {res}")

out, res, _ = run_local(g_db, [{"name": "провал", "script": "checks/bad.py"}])
case("Г3 падающая местная проверка — провал под именем «местная · провал»",
     len(res) == 1 and res[0][0] == "местная · провал" and res[0][1] is False
     and "местная беда" in res[0][2], f"{out}\n   {res}")

out, res, _ = run_local(g_db, [{"name": "пропажа", "script": "checks/nope.py"}])
case("Г4 скрипта нет — провал «скрипт местной проверки не найден» с путём",
     len(res) == 1 and not res[0][1] and "скрипт местной проверки не найден" in res[0][2]
     and "nope.py" in res[0][2], f"{res}")

out, res, _ = run_local(g_db, None, raw="{не json")
case("Г5 перечень не JSON — провал «перечень не читается»",
     len(res) == 1 and not res[0][1] and "перечень не читается" in res[0][2], f"{res}")

out, res, _ = run_local(g_db, [{"name": "опечатка", "script": "checks/ok.py", "arg": ["--x"]}])
case("Г6 неизвестное поле — провал «неизвестные поля arg»",
     len(res) == 1 and not res[0][1] and "неизвестные поля arg" in res[0][2], f"{res}")

out, res, _ = run_local(g_db, [{"name": "провал", "script": "checks/bad.py"}], skip=("провал",))
case("Г7 --skip по имени без приставки — «пропущен по --skip», провала нет",
     not res and "пропущен по --skip" in out, f"{out}\n   {res}")

ARGV_OUT.unlink(missing_ok=True)
out, res, _ = run_local(g_db, [{"name": "аргументы", "script": "checks/argv.py",
                                "args": ["--db", "{db}", "--x"]}])
got = json.loads(ARGV_OUT.read_text(encoding="utf-8")) if ARGV_OUT.exists() else None
case("Г8 «{db}» заменён путём базы прогона", got == ["--db", str(g_db), "--x"], f"получено {got}")

out, res, _ = run_local(g_db, [{"name": "двойник", "script": "checks/ok.py"},
                               {"name": "двойник", "script": "checks/ok.py"}])
case("Г9 одно имя дважды — провал", len(res) == 1 and not res[0][1] and "уже есть" in res[0][2], f"{res}")


def main_calls_local(source_file: Path) -> bool:
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    return main is not None and any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run_local_checks"
        for n in ast.walk(main))


case("Г10 main() зовёт run_local_checks(skip)", main_calls_local(GUARD_ALL))
p1 = broken_copy(GUARD_ALL, STAND / "break-p1", "    run_local_checks(skip)\n", "    pass\n")
case("П1 поломка «вызов убран» роняет Г10", not main_calls_local(p1))

# Г11 — общий прогон на КОПИИ контура: инструменты испытуемого + снимок живой базы.
print("---- Г11: общий прогон на копии контура (около минуты) ----")
live_mezo = mezo_paths.container_root(__file__) / ".mezosync"
c_root = STAND / "contour"
shutil.copytree(GUARD_ALL.parent, c_root / ".mezosync" / "scripts",
                ignore=shutil.ignore_patterns("__pycache__"))
proto_src = Path(__file__).resolve().parent
shutil.copytree(proto_src, c_root / "vnext-tools", ignore=shutil.ignore_patterns("__pycache__"))
c_db = mezo_stand.snapshot_db(live_mezo / "mezosync.db", c_root / ".mezosync" / "mezosync.db")
con = sqlite3.connect(str(c_db))
con.execute("DELETE FROM cross_links")      # копия не ходит к настоящим соседям
con.commit()
con.close()
(c_root / ".mezosync" / "local" / "checks").mkdir(parents=True)
for f in ("ok.py", "bad.py"):
    shutil.copy2(g_root / "local" / "checks" / f, c_root / ".mezosync" / "local" / "checks" / f)
(c_root / ".mezosync" / "local" / "checks.json").write_text(json.dumps({"checks": [
    {"name": "проба", "script": "checks/ok.py"},
    {"name": "провал", "script": "checks/bad.py"}]}, ensure_ascii=False), encoding="utf-8")
r = subprocess.run([sys.executable, str(c_root / ".mezosync" / "scripts" / "guard-all.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                   env=mezo_stand.stand_env(c_root, PYTHONIOENCODING="utf-8"))
full_out = (r.stdout or "") + (r.stderr or "")
last = [l for l in full_out.splitlines() if l.startswith(("⛔ КРАСНЫХ", "✅ ВСЕ"))]
case("Г11 общий прогон: «ℹ️ местных проверок: 2», «местная · провал» в списке провалов, "
     "«местная · проба» в прошедших, код 1",
     "ℹ️ местных проверок: 2" in full_out and last and "местная · провал" in last[-1]
     and "местная · проба" in full_out and r.returncode == 1,
     f"код {r.returncode}; итог: {last}")


# ═══ ЧАСТЬ О — update-tools.py: каталог местного и --release ═════════════════════════════════

SRC = STAND / "src"
PACK = {"alpha.py": b"# alpha: pack\nA = 2\n", "beta.py": b"# beta: pack\nB = 2\n",
        "gamma.py": b"# gamma: pack\nG = 2\n", "delta.py": b"# delta: pack\nD = 1\n"}
for name, data in PACK.items():
    (SRC / "scripts").mkdir(parents=True, exist_ok=True)
    (SRC / "scripts" / name).write_bytes(data)
OLD_A, OWN_A = b"# alpha: old\nA = 1\n", b"# alpha: OWN EDIT\nA = 1\n"   # ✋: ≠ пакету и ≠ отпечатку
OLD_B = b"# beta: old\nB = 1\n"                                          # ≠: равен отпечатку
OWN_G = b"# gamma: OWN EDIT, no fingerprint\nG = 1\n"                    # ❓: отпечатка нет
LOCAL_FILES = {"paths.json": b"{}\n", "checks.json": b'{"checks": []}\n',
               "checks/mine.py": b"print('ok')\n"}


def circuit(name: str, tool: Path = UPDATE_TOOLS, with_local: bool = True) -> tuple[Path, Path]:
    """Лёгкий контур: scripts/ (испытуемый + соседи + файлы контура), база с таблицей meta,
    по желанию — каталог местного. → (scripts/, база)."""
    root = STAND / name / ".mezosync"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    mezo_stand.copy_tool(tool, scripts)
    for n, data in (("alpha.py", OWN_A), ("beta.py", OLD_B), ("gamma.py", OWN_G),
                    ("delta.py", PACK["delta.py"])):
        (scripts / n).write_bytes(data)
    if with_local:
        for rel, data in LOCAL_FILES.items():
            (root / "local" / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / "local" / rel).write_bytes(data)
    db = root / "mezosync.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    fps = {"alpha.py": digest(OLD_A), "beta.py": digest(OLD_B), "delta.py": digest(PACK["delta.py"])}
    for k, v in (("template_source", str(SRC)), ("template_files_sha", json.dumps(fps))):
        con.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (k, v))
    con.commit()
    con.close()
    return scripts, db


def ut(scripts: Path, db: Path, *extra) -> tuple[int, str]:
    env = mezo_stand.stand_env(scripts.parent.parent, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(scripts / "update-tools.py"), "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def meta_fps(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    row = con.execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()
    con.close()
    return json.loads(row[0]) if row and row[0] else {}


print("---- часть О: обновление и каталог местного ----")
s1, d1 = circuit("o1")
local1 = d1.parent / "local"
rc, out = ut(s1, d1)
case("О1 план: строка «🏠 местное» с числом файлов; ✋ alpha · ≠ beta · ❓ gamma",
     rc == 0 and f"🏠 местное ... {local1.resolve().as_posix()}: файлов 3" in out
     and "✋ alpha.py" in out and "≠ beta.py" in out and "❓ gamma.py" in out, f"код {rc}\n{out}")
s1b, d1b = circuit("o1-no-local", with_local=False)
rc, out = ut(s1b, d1b)
case("О1 встречный: каталога местного нет — «каталога нет»",
     rc == 0 and "🏠 местное ... каталога нет" in out, f"код {rc}\n{out}")

s2, d2 = circuit("o2")
before = tree_digest(d2.parent / "local")
rc, out = ut(s2, d2, "--apply")
case("О2 --apply берёт свежий файл и не меняет в local/ ни байта",
     rc == 0 and (s2 / "beta.py").read_bytes() == PACK["beta.py"]
     and (s2 / "alpha.py").read_bytes() == OWN_A and tree_digest(d2.parent / "local") == before,
     f"код {rc}\n{out}")

s3, d3 = circuit("o3")
rc, out = ut(s3, d3, "--release", "alpha.py")
case("О3 план с --release: «⇄ alpha.py», ✋ alpha нет, файл не тронут, копий нет",
     rc == 0 and "⇄ alpha.py" in out and "✋ alpha.py" not in out
     and (s3 / "alpha.py").read_bytes() == OWN_A and not (d3.parent / "released").exists(),
     f"код {rc}\n{out}")


def release_apply_ok(scripts: Path, db: Path) -> tuple[bool, str]:
    before_local = tree_digest(db.parent / "local")
    rc, out = ut(scripts, db, "--apply", "--release", "alpha.py", "--release", "gamma.py")
    kept_dirs = sorted((db.parent / "released").glob("*")) if (db.parent / "released").is_dir() else []
    kept = kept_dirs[-1] if kept_dirs else None
    fps = meta_fps(db)
    ok = (rc == 0
          and (scripts / "alpha.py").read_bytes() == PACK["alpha.py"]
          and (scripts / "gamma.py").read_bytes() == PACK["gamma.py"]
          and kept is not None and (kept / "alpha.py").read_bytes() == OWN_A
          and (kept / "gamma.py").read_bytes() == OWN_G
          and fps.get("alpha.py") == digest(PACK["alpha.py"])
          and fps.get("gamma.py") == digest(PACK["gamma.py"])
          and tree_digest(db.parent / "local") == before_local)
    return ok, f"код {rc}; копия {kept}; отпечатки {fps}\n{out}"


s4, d4 = circuit("o4")
ok4, why4 = release_apply_ok(s4, d4)
case("О4 --apply --release ✋ и ❓: файлы = пакет, прежний текст — копией, отпечаток = пакет, "
     "local/ не тронут", ok4, why4)
rc, out = ut(s4, d4)
case("О4 следующий план — «совпадают с источником», ни ✋, ни ❓",
     rc == 0 and "инструменты совпадают с источником" in out and "✋" not in out.split("⚖️")[0]
     and "❓" not in out.split("⚖️")[0], f"код {rc}\n{out}")

s5, d5 = circuit("o5")
rc, out = ut(s5, d5, "--release", "nosuch.py")
case("О5 --release файла, которого нет в пакете — отказ словами",
     rc != 0 and "такого файла нет" in out, f"код {rc}\n{out}")
rc, out = ut(s5, d5, "--release", "delta.py")
case("О6 --release файла, равного пакету — «уже равен пакету»",
     rc == 0 and "уже равен пакету" in out, f"код {rc}\n{out}")
rc, out = ut(s5, d5, "--release", "beta.py")
case("О7 --release файла без своей правки — «обновится и без --release»",
     rc == 0 and "обновится и без --release" in out, f"код {rc}\n{out}")
rc, out = ut(s5, d5, "--release", "alpha.py", "--merge", "alpha.py")
case("О8 --release вместе с --merge — отказ", rc != 0 and "обычном обновлении" in out,
     f"код {rc}\n{out}")

print("---- нарочные поломки update-tools.py ----")
p2 = broken_copy(UPDATE_TOOLS, STAND / "break-p2", "                shutil.copy2(was, kept)\n",
                 "                pass  # ПОЛОМКА П2: копии прежнего текста нет\n")
s_p2, d_p2 = circuit("p2", tool=p2)
case("П2 поломка «без копии прежнего текста» роняет О4", not release_apply_ok(s_p2, d_p2)[0])
p3 = broken_copy(UPDATE_TOOLS, STAND / "break-p3", "old_pack + released + (unknown",
                 "old_pack + (unknown")
s_p3, d_p3 = circuit("p3", tool=p3)
case("П3 поломка «версия пакета не ставится» роняет О4", not release_apply_ok(s_p3, d_p3)[0])
p4 = broken_copy(UPDATE_TOOLS, STAND / "break-p4", "        print(local_summary(local))\n",
                 "        pass  # ПОЛОМКА П4\n")
s_p4, d_p4 = circuit("p4", tool=p4)
rc, out = ut(s_p4, d_p4)
case("П4 поломка «строки о местном нет» роняет О1", "🏠 местное" not in out, f"код {rc}")


# ═══ ЧАСТЬ Б — backup-db.py: каталог местного в копии ════════════════════════════════════════

print("---- часть Б: копия базы уносит каталог местного (снимок живой базы, до минуты) ----")


def backup(tool: Path, db: Path, out_file: Path, apply: bool) -> tuple[int, str]:
    args = [sys.executable, str(tool), "--db", str(db), "--out", str(out_file)] + (["--apply"] if apply else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, env=mezo_stand.stand_env(db.parent.parent, PYTHONIOENCODING="utf-8"))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def backup_case(tool: Path, tag: str) -> tuple[bool, bool, bool, bool, bool, str]:
    root = STAND / f"b-{tag}" / ".mezosync"
    (root / "scripts").mkdir(parents=True)
    mezo_stand.copy_tool(tool, root / "scripts")
    db = mezo_stand.snapshot_db(live_mezo / "mezosync.db", root / "mezosync.db")
    for rel, data in LOCAL_FILES.items():
        (root / "local" / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "local" / rel).write_bytes(data)
    out_file = STAND / f"b-{tag}" / "mirror" / "mezosync.dump.sql"
    out_file.parent.mkdir(parents=True)
    copy_dir = out_file.parent / "local-copy"
    rc0, o0 = backup(tool, db, out_file, False)
    b1 = "попадёт в копию как" in o0 and not copy_dir.exists()
    rc1, o1 = backup(tool, db, out_file, True)
    b2 = tree_digest(copy_dir) == tree_digest(root / "local")
    (root / "local" / "checks" / "mine.py").unlink()
    rc2, o2 = backup(tool, db, out_file, True)
    b3 = (tree_digest(copy_dir) == tree_digest(root / "local")
          and not (copy_dir / "checks" / "mine.py").exists() and "убрано исчезнувших" in o2)
    # Б4: кэш байт-кода местного скрипта в копию не едет, остальное — едет
    pyc = root / "local" / "checks" / "__pycache__" / "helper.cpython-314.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"\x00pyc\n")
    rc3, o3 = backup(tool, db, out_file, True)
    b4 = (not (copy_dir / "checks" / "__pycache__").exists()
          and (copy_dir / "checks.json").is_file() and (copy_dir / "paths.json").is_file())
    # Б5: выгрузка внутри local/ — копии нет, строка говорит почему
    inner_out = root / "local" / "dumps" / "mezosync.dump.sql"
    inner_out.parent.mkdir(parents=True, exist_ok=True)
    rc4, o4 = backup(tool, db, inner_out, True)
    b5 = "НЕ попал" in o4 and not (inner_out.parent / "local-copy").exists()
    return b1, b2, b3, b4, b5, (f"коды {rc0}/{rc1}/{rc2}/{rc3}/{rc4}\n--- без --apply\n{o0}\n"
                                f"--- второй --apply\n{o2}\n--- третий --apply (кэш)\n{o3}\n"
                                f"--- выгрузка внутри local/\n{o4}")


b1, b2, b3, b4, b5, why_b = backup_case(BACKUP_DB, "live")
case("Б1 без --apply — строка «попадёт в копию», каталога копии нет", b1, why_b)
case("Б2 --apply — local-copy/ = local/ побайтно", b2, why_b)
case("Б3 файл убран из local/ — убран и из копии, строка называет", b3, why_b)
case("Б4 кэш байт-кода (__pycache__) в копию не едет, остальное — едет", b4, why_b)
case("Б5 выгрузка внутри local/ — копии нет, строка «НЕ попал»", b5, why_b)
p5 = broken_copy(BACKUP_DB, STAND / "break-p5", "    for p in gone:\n        p.unlink()\n",
                 "    for p in []:  # ПОЛОМКА П5\n        p.unlink()\n")
b3_broken = backup_case(p5, "p5")[2]
case("П5 поломка «исчезнувшее остаётся в копии» роняет Б3", not b3_broken)
p6 = broken_copy(BACKUP_DB, STAND / "break-p6",
                 "if p.is_file() and not LOCAL_COPY_SKIP.intersection(p.relative_to(local).parts))",
                 "if p.is_file())  # ПОЛОМКА П6")
b4_broken = backup_case(p6, "p6")[3]
case("П6 поломка «кэш байт-кода едет в копию» роняет Б4", not b4_broken)
p7 = broken_copy(BACKUP_DB, STAND / "break-p7", "        dst.resolve().relative_to(local.resolve())\n",
                 "        raise ValueError  # ПОЛОМКА П7\n")
b5_broken = backup_case(p7, "p7")[4]
case("П7 поломка «копия внутрь самого local/» роняет Б5", not b5_broken)

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
