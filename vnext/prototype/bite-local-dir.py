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
  Г1б перечень пуст — без --full ни строк, ни провалов; с --full — «перечень … пуст»
  Г2  проходящая местная проверка — «ℹ️ местных проверок: 1», в прошедших «местная · …»
  Г3  падающая местная проверка — провал под именем «местная · …»
  Г4  скрипта нет — провал «скрипт местной проверки не найден» с путём
  Г5  перечень не JSON — провал «местная · перечень»: «перечень не читается»
  Г5б перечень — JSON не той формы ([] · {"check": []}) — «нужен объект»
  Г5в на месте перечня каталог — «перечень не читается»
  Г5г перечень с меткой порядка байтов читается
  Г6  неизвестное поле записи («arg» вместо «args») — провал «неизвестные поля arg»
  Г6б запись не объект · нет имени · пустое имя · нет пути скрипта · args строкой · args
      не из строк — каждая провалом «местная · перечень» со своими словами
  Г7  --skip по имени без приставки — «пропущен по --skip», провала нет
  Г7б --skip по имени С приставкой «местная · » — пропущен, провала нет
  Г8  «{db}» в аргументах заменён путём базы прогона
  Г9  одно имя дважды — провал «местная · перечень»
  Г10 main() guard-all.py зовёт run_local_checks(skip) (разбор исходника)
  Г11 общий прогон на копии контура: строка местных, падающая местная — в списке провалов
  Г11б проверки пакета сняты --skip, местная падает — код 1, в провалах только местная
  Г11в то же и --skip провал — местная пропущена, код 0 (--skip доезжает из main())
  О1  план печатает строку «🏠 местное» с числом файлов; встречный — «каталога нет»
  О2  --apply (свежий файл берётся) не меняет в local/ ни байта
  О3  план с --release: «⇄ <файл>», файл не тронут, копий нет
  О4  --apply --release ✋ и ❓: файлы = пакет, прежний текст — копией в released/<дата-время>/,
      отпечаток = версия пакета, local/ не тронут, следующий план — «совпадают»
  О5  --release файла, которого нет в пакете — отказ словами
  О6  --release файла, равного пакету — «уже равен пакету»
  О7  --release файла без своей правки — «обновится и без --release»
  О8  --release вместе с --merge — отказ
  О9  ключ prototype_install_dir указывает внутрь local/ — «указывает внутрь каталога
      местного», local/ не тронут ни байтом
  О10 одно имя ✋ и в scripts/, и во втором каталоге: голое имя — отказ «назови, какой
      отдать»; б) vnext/prototype/<имя> — отдан второй каталог, копия в …/second-dir/;
      в) scripts/<имя> — отдан рабочий скрипт, копия рядом
  О11 копия прежнего текста не совпала (сбой копирования подставлен) — отказ «не совпала»,
      ни один файл пакета не поставлен
  Б1  backup-db без --apply — строка «попадёт в копию», каталога копии нет
  Б2  backup-db --apply — local-copy/ = local/ побайтно
  Б3  файл убран из local/ — убран и из копии, строка называет число
  Б4  кэш байт-кода (__pycache__) в копию не едет, остальное — едет
  Б8  чужой файл в local-copy/ (не из local/) не тронут, строка называет его
  Б7  local/ пуст при непустой прошлой копии — копия не тронута, строка «пуст»
  Б6  local/ нет — копия не тронута, строка «каталога местного нет»
  Б5  выгрузка внутри local/ — копии нет, строка «НЕ попал»
НАРОЧНЫЕ ПОЛОМКИ (в копиях испытуемых; каждая обязана уронить ровно названное; номер П8 не занят)
  П1  вызов run_local_checks убран из main()            → Г10
  П2  --release без копии прежнего текста               → О4
  П3  --release не ставит версию пакета                  → О4
  П4  строка «🏠 местное» не печатается                  → О1
  П5  исчезнувшие из local/ файлы остаются в копии      → Б3
  П6  кэш байт-кода едет в копию                         → Б4
  П7  копия ложится внутрь самого local/                 → Б5
  П9  пустой local/ стирает прошлую копию                → Б7
  П10 из копии убирается всё, чего нет в local/          → Б8
  П11 отсутствие local/ не называется                    → Б6
  П12 --skip не понимает приставку «местная · »          → Г7б
  П13 провал местной не влияет на код выхода             → Г11б   (копия контура, на месте)
  П14 --skip не доезжает до местных из main()            → Г11в   (копия контура, на месте)
  П15 второй каталог внутри local/ обслуживается         → О9
  П16 копии двух каталогов ложатся в одно место          → О10б
  П17 сверка копии ослаблена до «файл есть»              → О11

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


def broken_copy_many(tool: Path, dest_dir: Path, pairs) -> Path:
    """Копия испытуемого с несколькими заменами; каждая строка обязана найтись ровно один раз."""
    text = tool.read_text(encoding="utf-8")
    for old, new in pairs:
        if text.count(old) != 1:
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: строка поломки встречается {text.count(old)} раз в {tool} "
                     f"(нужно ровно 1): {old!r}")
        text = text.replace(old, new)
    dest_dir.mkdir(parents=True, exist_ok=True)
    mezo_stand.copy_tool(tool, dest_dir)
    (dest_dir / tool.name).write_text(text, encoding="utf-8")
    return dest_dir / tool.name


def read_or_none(path) -> bytes | None:
    """Байты файла либо None — чтобы пропавшая копия давала провал случая, а не обрыв приёмки."""
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


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


def run_local(db: Path, checks, skip=(), full=False, raw: str | None = None,
              source: Path = GUARD_ALL, as_dir: bool = False):
    """Положить перечень (или сырой текст; as_dir — каталог на месте файла) и прогнать
    run_local_checks испытуемого source → (вывод, RESULTS, GREENS)."""
    local = db.parent / "local"
    local.mkdir(parents=True, exist_ok=True)
    lst = local / "checks.json"
    if lst.is_dir():
        lst.rmdir()
    if as_dir:
        lst.unlink(missing_ok=True)
        lst.mkdir()
    elif raw is not None:
        lst.write_text(raw, encoding="utf-8")
    elif checks is None:
        lst.unlink(missing_ok=True)
    else:
        lst.write_text(json.dumps({"checks": checks}, ensure_ascii=False), encoding="utf-8")
    ns = guard_namespace(source, db, full)
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

def list_trouble(res, words: str) -> bool:
    """Провал перечня: ровно одна запись, имя «местная · перечень», провал, названные слова."""
    return (len(res) == 1 and res[0][0] == "местная · перечень" and res[0][1] is False
            and words in res[0][2])


out, res, _ = run_local(g_db, [])
case("Г1б перечень пуст — без --full ни строк, ни провалов", not res and "местн" not in out, out)
out, res, _ = run_local(g_db, [], full=True)
case("Г1б с --full — «местных проверок нет: перечень … пуст»",
     not res and "местных проверок нет" in out and "пуст" in out, out)

out, res, _ = run_local(g_db, None, raw="{не json")
case("Г5 перечень не JSON — провал «местная · перечень»: «перечень не читается»",
     list_trouble(res, "перечень не читается"), f"{res}")
for tag, raw in (("[]", "[]"), ('{"check": []}', '{"check": []}')):
    out, res, _ = run_local(g_db, None, raw=raw)
    case(f"Г5б перечень — JSON не той формы ({tag}) — провал «нужен объект»",
         list_trouble(res, "нужен объект"), f"{res}")
out, res, _ = run_local(g_db, None, as_dir=True)
case("Г5в на месте перечня каталог (чтение отказало) — провал «перечень не читается»",
     list_trouble(res, "перечень не читается"), f"{res}")
out, res, _ = run_local(g_db, None, raw="﻿" + json.dumps(
    {"checks": [{"name": "проба", "script": "checks/ok.py"}]}, ensure_ascii=False))
case("Г5г перечень с меткой порядка байтов (след редактора) читается",
     res == [("местная · проба", True, "✅ местное в порядке")], f"{res}")

out, res, _ = run_local(g_db, [{"name": "опечатка", "script": "checks/ok.py", "arg": ["--x"]}])
case("Г6 неизвестное поле — провал «местная · перечень»: «неизвестные поля arg»",
     list_trouble(res, "неизвестные поля arg"), f"{res}")
for tag, item, words in (("запись не объект", "checks/ok.py", "не объект"),
                         ("нет имени", {"script": "checks/ok.py"}, "нет имени"),
                         ("пустое имя", {"name": "  ", "script": "checks/ok.py"}, "нет имени"),
                         ("нет скрипта", {"name": "без скрипта"}, "нет пути скрипта"),
                         ("args — строка", {"name": "x", "script": "checks/ok.py", "args": "--db"},
                          "не список строк"),
                         ("args — не строки", {"name": "x", "script": "checks/ok.py", "args": [1]},
                          "не список строк")):
    out, res, _ = run_local(g_db, [item])
    case(f"Г6б {tag} — провал «местная · перечень»: «{words}»", list_trouble(res, words), f"{res}")

out, res, _ = run_local(g_db, [{"name": "провал", "script": "checks/bad.py"}], skip=("провал",))
case("Г7 --skip по имени без приставки — «пропущен по --skip», провала нет",
     not res and "пропущен по --skip" in out, f"{out}\n   {res}")
G7B = ([{"name": "провал", "script": "checks/bad.py"}], ("местная · провал",))
out, res, _ = run_local(g_db, G7B[0], skip=G7B[1])
case("Г7б --skip по имени С приставкой «местная · » — пропущен, провала нет",
     not res and "пропущен по --skip" in out, f"{out}\n   {res}")
p12 = broken_copy(GUARD_ALL, STAND / "break-p12", "if name in skip or full_name in skip:",
                  "if name in skip:  # ПОЛОМКА П12")
out, res, _ = run_local(g_db, G7B[0], skip=G7B[1], source=p12)
case("П12 поломка «приставка не понимается» роняет Г7б", bool(res), f"{out}\n   {res}")

ARGV_OUT.unlink(missing_ok=True)
out, res, _ = run_local(g_db, [{"name": "аргументы", "script": "checks/argv.py",
                                "args": ["--db", "{db}", "--x"]}])
got = json.loads(ARGV_OUT.read_text(encoding="utf-8")) if ARGV_OUT.exists() else None
case("Г8 «{db}» заменён путём базы прогона", got == ["--db", str(g_db), "--x"], f"получено {got}")

out, res, _ = run_local(g_db, [{"name": "двойник", "script": "checks/ok.py"},
                               {"name": "двойник", "script": "checks/ok.py"}])
case("Г9 одно имя дважды — провал «местная · перечень»", list_trouble(res, "уже есть"), f"{res}")


def main_calls_local(source_file: Path) -> bool:
    """main() зовёт run_local_checks(skip) — с тем самым skip (доезжает ли он на деле, судит Г11в)."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    return main is not None and any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run_local_checks"
        and [getattr(x, "id", None) for x in n.args] == ["skip"]
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
# Каталога координации у копии нет (atlas.archs не копируется) — объявлено штатно. Без объявления
# «замороженные md» провалена, а --skip её не снимает: guard-all зовёт её check() напрямую, мимо
# --skip, и Г11б/Г11в не смогли бы отделить код выхода местных от проверок пакета.
(c_root / ".mezo-no-coordination").write_text("копия контура приёмки bite-local-dir.py\n", encoding="utf-8")
C_GUARD = c_root / ".mezosync" / "scripts" / "guard-all.py"
C_GUARD_TEXT = C_GUARD.read_bytes()


def full_run(*extra) -> tuple[int, str, list[str]]:
    """Общий прогон копии контура → (код, вывод, имена провалившихся из итоговой строки)."""
    r = subprocess.run([sys.executable, str(C_GUARD), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                       env=mezo_stand.stand_env(c_root, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    last = [l for l in out.splitlines() if l.startswith(("⛔ КРАСНЫХ", "✅ ВСЕ"))]
    reds = []
    if last and last[-1].startswith("⛔ КРАСНЫХ") and " — " in last[-1]:
        reds = [n.strip() for n in last[-1].split(" — ", 1)[1].rsplit(" (", 1)[0].split(", ")]
    return r.returncode, out, reds


rc_a, full_out, reds_a = full_run()
case("Г11 общий прогон: «ℹ️ местных проверок: 2», «местная · провал» в списке провалов, "
     "«местная · проба» в прошедших, код 1",
     "ℹ️ местных проверок: 2" in full_out and "местная · провал" in reds_a
     and "местная · проба" in full_out and rc_a == 1, f"код {rc_a}; провалы: {reds_a}")
# ⚖️ В копии живого контура красны и проверки пакета (память ролей и т.п.) — код 1 был бы и без
# местных. Различают два прогона ниже: красные проверки пакета сняты --skip, и код выхода
# зависит только от местных (находки приёмки чужой рукой Н8, Н12).
pkg_skip = ",".join(n for n in reds_a if not n.startswith("местная · "))


def run_b() -> tuple[bool, str]:
    rc, out, reds = full_run("--skip", pkg_skip)
    return rc == 1 and reds == ["местная · провал"], f"код {rc}; провалы: {reds}"


def run_c() -> tuple[bool, str]:
    rc, out, reds = full_run("--skip", pkg_skip + ",провал")
    return (rc == 0 and not reds and "⏭️ местная · провал — пропущен по --skip" in out,
            f"код {rc}; провалы: {reds}")


ok_b, why_b11 = run_b()
case("Г11б проверки пакета сняты --skip, местная падает — код 1, в провалах только «местная · провал»",
     ok_b, why_b11)
ok_c, why_c11 = run_c()
case("Г11в то же и --skip провал — местная пропущена, код 0 (--skip доезжает из main())",
     ok_c, why_c11)
for tag, old, new, runner in (
        ("П13", "    sys.exit(1 if bad else 0)",
         "    sys.exit(1 if [n for n in bad if not n.startswith('местная')] else 0)  # ПОЛОМКА П13",
         run_b),
        ("П14", "    run_local_checks(skip)",
         "    skip = set(); run_local_checks(skip)  # ПОЛОМКА П14", run_c)):
    text = C_GUARD_TEXT.decode("utf-8")
    if text.count(old) != 1:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: строка поломки {tag} встречается {text.count(old)} раз")
    C_GUARD.write_bytes(text.replace(old, new).encode("utf-8"))
    try:
        broken_ok, _ = runner()
    finally:
        C_GUARD.write_bytes(C_GUARD_TEXT)
    what = "провал местной не меняет код выхода" if tag == "П13" else "--skip не доезжает до местных"
    case(f"{tag} поломка «{what}» роняет Г11{'б' if tag == 'П13' else 'в'}", not broken_ok)


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


def circuit(name: str, tool: Path = UPDATE_TOOLS, with_local: bool = True,
            src: Path = SRC) -> tuple[Path, Path]:
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
    for k, v in (("template_source", str(src)), ("template_files_sha", json.dumps(fps))):
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
          and read_or_none(scripts / "alpha.py") == PACK["alpha.py"]
          and read_or_none(scripts / "gamma.py") == PACK["gamma.py"]
          and kept is not None and read_or_none(kept / "alpha.py") == OWN_A
          and read_or_none(kept / "gamma.py") == OWN_G
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

# ── второй каталог установки (ключ prototype_install_dir) — свой источник SRC2, чтобы файлы
# второго каталога не меняли планы случаев выше (находки приёмки чужой рукой Н3, Н9, Н10)
SRC2 = STAND / "src2"
(SRC2 / "scripts").mkdir(parents=True)
(SRC2 / "vnext" / "prototype").mkdir(parents=True)
for name, data in PACK.items():
    (SRC2 / "scripts" / name).write_bytes(data)
PACK_S, PACK_V, PACK_X = b"# shared: pack scripts\nS = 2\n", b"# shared: pack vnext\nV = 2\n", b"X = 2\n"
OLD_S, OWN_S = b"# shared: old scripts\nS = 1\n", b"# shared: OWN scripts\nS = 1\n"
OLD_V, OWN_V = b"# shared: old vnext\nV = 1\n", b"# shared: OWN vnext\nV = 1\n"
OLD_X = b"X = 1\n"
(SRC2 / "scripts" / "shared.py").write_bytes(PACK_S)
(SRC2 / "vnext" / "prototype" / "shared.py").write_bytes(PACK_V)
(SRC2 / "vnext" / "prototype" / "x.py").write_bytes(PACK_X)
SECOND_KEY = "prototype-dir::/"


def second_circuit(name: str, second: str, tool: Path = UPDATE_TOOLS):
    """Контур со вторым каталогом установки: second — путь от .mezosync/ (например «local/proto»).
    → (scripts/, база, второй каталог, открытое соединение с базой, отпечатки) — отпечатки
    дописывает случай и закрывает соединение через set_fps()."""
    scripts, db = circuit(name, tool=tool, src=SRC2)
    root = db.parent
    sec = root / second
    sec.mkdir(parents=True)
    (root / "local" / "paths.json").write_text(
        json.dumps({"prototype_install_dir": sec.resolve().as_posix()}), encoding="utf-8")
    con = sqlite3.connect(str(db))
    fps = json.loads(con.execute("SELECT value FROM meta WHERE key='template_files_sha'").fetchone()[0])
    return scripts, db, sec, con, fps


def set_fps(con, fps) -> None:
    con.execute("UPDATE meta SET value=? WHERE key='template_files_sha'", (json.dumps(fps),))
    con.commit()
    con.close()


def inside_case(tool: Path, tag: str) -> tuple[bool, str]:
    """О9: второй каталог внутри local/ не обслуживается — x.py там «≠» (обновился бы), а не тронут."""
    s, d, sec, con, fps = second_circuit(tag, "local/proto", tool=tool)
    (sec / "x.py").write_bytes(OLD_X)
    fps[SECOND_KEY + "x.py"] = digest(OLD_X)
    set_fps(con, fps)
    before = tree_digest(d.parent / "local")
    rc, out = ut(s, d, "--apply")
    return (rc == 0 and "указывает внутрь каталога местного" in out
            and tree_digest(d.parent / "local") == before
            and read_or_none(sec / "x.py") == OLD_X), f"код {rc}\n{out}"


ok9, why9 = inside_case(UPDATE_TOOLS, "o9")
case("О9 второй каталог внутри local/ — «указывает внутрь каталога местного», local/ не тронут",
     ok9, why9)
p15 = broken_copy(UPDATE_TOOLS, STAND / "break-p15",
                  "if second_dir is not None and inside(second_dir, local):", "if False:  # ПОЛОМКА П15")
case("П15 поломка «второй каталог внутри local/ обслуживается» роняет О9",
     not inside_case(p15, "p15")[0])


def two_dirs_case(tool: Path, tag: str) -> tuple[bool, bool, bool, str]:
    """О10: shared.py «✋» и в scripts/, и во втором каталоге (вне local/)."""
    s, d, sec, con, fps = second_circuit(tag, "proto2", tool=tool)
    (s / "shared.py").write_bytes(OWN_S)
    (sec / "shared.py").write_bytes(OWN_V)
    fps["shared.py"], fps[SECOND_KEY + "shared.py"] = digest(OLD_S), digest(OLD_V)
    set_fps(con, fps)
    rc_a, out_a = ut(s, d, "--apply", "--release", "shared.py")
    a = (rc_a != 0 and "назови, какой отдать" in out_a and read_or_none(s / "shared.py") == OWN_S
         and read_or_none(sec / "shared.py") == OWN_V and not (d.parent / "released").exists())
    rc_b, out_b = ut(s, d, "--apply", "--release", "vnext/prototype/shared.py")
    kept_b = sorted((d.parent / "released").glob("*")) if (d.parent / "released").is_dir() else []
    b = (rc_b == 0 and read_or_none(sec / "shared.py") == PACK_V and read_or_none(s / "shared.py") == OWN_S
         and len(kept_b) == 1 and read_or_none(kept_b[0] / "second-dir" / "shared.py") == OWN_V
         and not (kept_b[0] / "shared.py").exists())
    rc_c, out_c = ut(s, d, "--apply", "--release", "scripts/shared.py")
    kept_c = sorted((d.parent / "released").glob("*/shared.py")) if (d.parent / "released").is_dir() else []
    c = (rc_c == 0 and read_or_none(s / "shared.py") == PACK_S
         and [read_or_none(p) for p in kept_c] == [OWN_S])
    return a, b, c, (f"коды {rc_a}/{rc_b}/{rc_c}\n--- голое имя\n{out_a}\n--- vnext/prototype/\n{out_b}\n"
                     f"--- scripts/\n{out_c}")


a10, b10, c10, why10 = two_dirs_case(UPDATE_TOOLS, "o10")
case("О10 имя в обоих каталогах без каталога — отказ «назови, какой отдать», ничего не тронуто",
     a10, why10)
case("О10б --release vnext/prototype/shared.py — отдан только второй каталог, копия в …/second-dir/",
     b10, why10)
case("О10в --release scripts/shared.py — отдан рабочий скрипт, копия рядом, а не в second-dir/",
     c10, why10)
p16 = broken_copy(UPDATE_TOOLS, STAND / "break-p16",
                  'keep_dir / "second-dir" / rel.name if is_second_rel(rel) else keep_dir / rel',
                  "keep_dir / rel.name  # ПОЛОМКА П16")
case("П16 поломка «копии двух каталогов в одном месте» роняет О10б", not two_dirs_case(p16, "p16")[1])

# ── сверка копии прежнего текста: сбой копирования подставлен в копию испытуемого (обрезанная
# копия — как при полном диске); обещано: файлы пакета не ставятся (находка Н10б)
SHORT_COPY = ("                shutil.copy2(was, kept)",
              "                kept.write_bytes(was.read_bytes()[:-1])  # СБОЙ КОПИИ, подставлен приёмкой")


def short_copy_case(tool: Path, tag: str) -> tuple[bool, str]:
    s, d = circuit(tag, tool=tool)
    rc, out = ut(s, d, "--apply", "--release", "alpha.py", "--release", "gamma.py")
    return (rc != 0 and "не совпала" in out and read_or_none(s / "alpha.py") == OWN_A
            and read_or_none(s / "gamma.py") == OWN_G and read_or_none(s / "beta.py") == OLD_B,
            f"код {rc}\n{out}")


t11 = broken_copy_many(UPDATE_TOOLS, STAND / "fault-o11", [SHORT_COPY])
ok11, why11 = short_copy_case(t11, "o11")
case("О11 копия прежнего текста не совпала — отказ «не совпала», ни один файл пакета не поставлен",
     ok11, why11)
p17 = broken_copy_many(UPDATE_TOOLS, STAND / "break-p17", [
    SHORT_COPY, ("if kept.read_bytes() != was.read_bytes():", "if not kept.exists():  # ПОЛОМКА П17")])
case("П17 поломка «сверка копии ослаблена до “файл есть”» роняет О11", not short_copy_case(p17, "p17")[0])


# ═══ ЧАСТЬ Б — backup-db.py: каталог местного в копии ════════════════════════════════════════

print("---- часть Б: копия базы уносит каталог местного (снимок живой базы, до минуты) ----")


def backup(tool: Path, db: Path, out_file: Path, apply: bool) -> tuple[int, str]:
    args = [sys.executable, str(tool), "--db", str(db), "--out", str(out_file)] + (["--apply"] if apply else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, env=mezo_stand.stand_env(db.parent.parent, PYTHONIOENCODING="utf-8"))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def backup_case(tool: Path, tag: str, stop_after: str = "b5") -> dict:
    """Шаги по порядку b1 b2 b3 b4 b8 b7 b6 b5 (каждый стоит на состоянии копии после прежних);
    stop_after — последний нужный шаг: прогону с поломкой нужен только свой. → {шаг: прошёл,
    "why": выводы прогонов}."""
    root = STAND / f"b-{tag}" / ".mezosync"
    (root / "scripts").mkdir(parents=True)
    mezo_stand.copy_tool(tool, root / "scripts")
    db = mezo_stand.snapshot_db(live_mezo / "mezosync.db", root / "mezosync.db")
    local = root / "local"
    for rel, data in LOCAL_FILES.items():
        (local / rel).parent.mkdir(parents=True, exist_ok=True)
        (local / rel).write_bytes(data)
    out_file = STAND / f"b-{tag}" / "mirror" / "mezosync.dump.sql"
    out_file.parent.mkdir(parents=True)
    copy_dir = out_file.parent / "local-copy"
    res, outs = {}, []

    def step(key: str, label: str, out_to: Path, apply: bool, judge) -> bool:
        """Прогон и суждение; True — дальше идти не нужно."""
        rc, o = backup(tool, db, out_to, apply)
        res[key] = bool(judge(o))
        outs.append(f"--- {key}: {label} (код {rc})\n{o}")
        return key == stop_after

    def finish() -> dict:
        res["why"] = "\n".join(outs)
        return res

    if step("b1", "без --apply", out_file, False,
            lambda o: "попадёт в копию как" in o and not copy_dir.exists()):
        return finish()
    if step("b2", "первый --apply", out_file, True,
            lambda o: tree_digest(copy_dir) == tree_digest(local)):
        return finish()
    (local / "checks" / "mine.py").unlink()
    if step("b3", "файл убран из local/", out_file, True,
            lambda o: tree_digest(copy_dir) == tree_digest(local)
            and not (copy_dir / "checks" / "mine.py").exists() and "убрано исчезнувших" in o):
        return finish()
    # Б4: кэш байт-кода местного скрипта в копию не едет, остальное — едет
    pyc = local / "checks" / "__pycache__" / "helper.cpython-314.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"\x00pyc\n")
    if step("b4", "кэш байт-кода", out_file, True,
            lambda o: not (copy_dir / "checks" / "__pycache__").exists()
            and (copy_dir / "checks.json").is_file() and (copy_dir / "paths.json").is_file()):
        return finish()
    # Б8: чужой файл в копии (не из local/) — не трогается и называется
    foreign = copy_dir / "foreign-note.txt"
    foreign.write_bytes(b"not from local\n")
    if step("b8", "чужой файл в копии", out_file, True,
            lambda o: read_or_none(foreign) == b"not from local\n"
            and "не из local/: 1 (foreign-note.txt)" in o):
        return finish()
    # Б7: local/ пуст при непустой прошлой копии — копия не тронута, строка «пуст»
    away = root / "local-away"
    local.rename(away)
    local.mkdir()
    copy_before = tree_digest(copy_dir)
    if step("b7", "local/ пуст", out_file, True,
            lambda o: tree_digest(copy_dir) == copy_before and "пуст, а в прошлой копии" in o):
        return finish()
    # Б6: local/ нет — копия не тронута, строка «каталога местного нет»
    local.rmdir()
    if step("b6", "local/ нет", out_file, True,
            lambda o: tree_digest(copy_dir) == copy_before and "каталога местного нет" in o):
        return finish()
    away.rename(local)
    # Б5: выгрузка внутри local/ — копии нет, строка говорит почему
    inner_out = local / "dumps" / "mezosync.dump.sql"
    inner_out.parent.mkdir(parents=True, exist_ok=True)
    step("b5", "выгрузка внутри local/", inner_out, True,
         lambda o: "НЕ попал" in o and not (inner_out.parent / "local-copy").exists())
    return finish()


rb = backup_case(BACKUP_DB, "live")
case("Б1 без --apply — строка «попадёт в копию», каталога копии нет", rb["b1"], rb["why"])
case("Б2 --apply — local-copy/ = local/ побайтно", rb["b2"], rb["why"])
case("Б3 файл убран из local/ — убран и из копии, строка называет", rb["b3"], rb["why"])
case("Б4 кэш байт-кода (__pycache__) в копию не едет, остальное — едет", rb["b4"], rb["why"])
case("Б8 чужой файл в local-copy/ не тронут, строка называет «не из local/»", rb["b8"], rb["why"])
case("Б7 local/ пуст при непустой прошлой копии — копия не тронута, строка «пуст»", rb["b7"], rb["why"])
case("Б6 local/ нет — копия не тронута, строка «каталога местного нет»", rb["b6"], rb["why"])
case("Б5 выгрузка внутри local/ — копии нет, строка «НЕ попал»", rb["b5"], rb["why"])
p5 = broken_copy(BACKUP_DB, STAND / "break-p5", "    for p in gone:\n        p.unlink()\n",
                 "    for p in []:  # ПОЛОМКА П5\n        p.unlink()\n")
case("П5 поломка «исчезнувшее остаётся в копии» роняет Б3", not backup_case(p5, "p5", "b3")["b3"])
p6 = broken_copy(BACKUP_DB, STAND / "break-p6",
                 "if p.is_file() and not LOCAL_COPY_SKIP.intersection(p.relative_to(local).parts))",
                 "if p.is_file())  # ПОЛОМКА П6")
case("П6 поломка «кэш байт-кода едет в копию» роняет Б4", not backup_case(p6, "p6", "b4")["b4"])
p10 = broken_copy(BACKUP_DB, STAND / "break-p10",
                  "    gone = [dst / r for r in sorted(prev - kept) if (dst / r).is_file()]\n",
                  "    gone = [p for p in dst.rglob(\"*\") if p.is_file()\n"
                  "            and p.relative_to(dst).as_posix() not in kept]  # ПОЛОМКА П10\n")
case("П10 поломка «из копии убирается всё не из local/» роняет Б8",
     not backup_case(p10, "p10", "b8")["b8"])
p9 = broken_copy(BACKUP_DB, STAND / "break-p9", "    if not files and prev:\n",
                 "    if False:  # ПОЛОМКА П9\n")
case("П9 поломка «пустой local/ стирает копию» роняет Б7", not backup_case(p9, "p9", "b7")["b7"])
p11 = broken_copy(BACKUP_DB, STAND / "break-p11", "    if not local.is_dir():\n",
                  "    if False:  # ПОЛОМКА П11\n")
case("П11 поломка «нет local/ — не называется» роняет Б6", not backup_case(p11, "p11", "b6")["b6"])
p7 = broken_copy(BACKUP_DB, STAND / "break-p7", "        dst.resolve().relative_to(local.resolve())\n",
                 "        raise ValueError  # ПОЛОМКА П7\n")
case("П7 поломка «копия внутрь самого local/» роняет Б5", not backup_case(p7, "p7")["b5"])

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
