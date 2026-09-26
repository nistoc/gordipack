# -*- coding: utf-8 -*-
r"""bite-update-tools-neighbours.py — приёмка карточек #637/#638.

═══ ПРЕДМЕТ (а) — update-tools.py (карточка #637)
guard-all.py пакета зовёт звено из vnext/prototype (check-acceptance-env.py) через
tool()/sub_guard() — то есть свежая сборка (init-group.py, шаг 7б) кладёт его контуру
ПО ЗАМЫКАНИЮ: звено зовёт привезённый скрипт. update-tools.py при ОБНОВЛЕНИИ считал иначе:
звено из vnext/prototype обновлялось, только если уже стоит у контура; новое уходило в
«ℹ️ Вне обновления» НАВСЕГДА — контур, который обновляется, а не собирается заново, никогда
его не получает, и общий прогон печатает «гард не найден». Починка (в update-tools.py):
функция closure_of_prototype_links() — БЛИЗНЕЦ правила init-group.py 7б, но по scripts/
ИСТОЧНИКА; звено из этого замыкания, которого у контура нет, теперь уходит в new_files
(«+ … появится»), как и положенные сборкой.

═══ ПРЕДМЕТ (b) — guard-all.py (карточка #638, слово владельца «B + a»)
«гард не найден» одной строкой не различал «звена у контура НИКОГДА не было» (обновление
его просто ещё не привезло) от «звено СТОЯЛО и пропало» (порча). Починка (в guard-all.py):
installed_fingerprints() читает meta.template_files_sha и различает по имени файла —
есть отпечаток ⇒ «ПРОПАЛО» (провал, как раньше); отпечатков у контура полно, но у ЭТОГО
имени нет ⇒ «не приехало с обновлением» (⚠️ код 0, готовая команда докладки); отпечатков
у контура нет ВООБЩЕ ⇒ различить нечем — провал по-прежнему (ГРАНИЦА, названа не угадана).

═══ СЛУЧАИ
  (а) ① ГЛАВНЫЙ    — стенд без звена из замыкания: план «+ … появится», --apply кладёт,
                      общий прогон стенда для него больше не «гард не найден»
                      (тем же ходом закрывает встречный критерий ② карточки #638:
                      контур из клона пакета, где звена нет, обновлён до вершины — чисто)
      ② ВСТРЕЧНЫЙ  — файл источника, которого не зовёт НИКТО, остаётся «Вне обновления»
      ③ БЛИЗНЕЦ    — множество замыкания update-tools.py = множество звеньев init-group.py 7б
      ④ СОСЕД      — контур со СТАРЫМ update-tools.py: первый --apply приносит НОВЫЙ,
                      повторный план уже показывает «+ звено»
  (б) ① «ПРОПАЛО»       — отпечаток есть, файла нет — провал
      ② «не приехало»   — отпечатков у контура полно, у этого имени нет — ⚠️ код 0
      ③ ГРАНИЦА         — отпечатков у контура нет ВООБЩЕ — провал (различить нечем)

═══ ПОЛОМКИ (--break), ЯКОРЬ — строка, встречающаяся в файле РОВНО один раз
  no-closure        — копия update-tools.py: строка, где звенья замыкания уходят в new_files,
                      обезврежена. Ждём: роняет РОВНО (а)① и (а)④; (а)②, (а)③ — прежние
                      (③ судит саму функцию замыкания, поломка её не касается).
  no-discriminator  — копия guard-all.py: чтение отпечатков всегда отдаёт пустой словарь.
                      Ждём: роняет РОВНО (б)②; (б)①, (б)③ по-прежнему проваливаются (тем же
                      кодом — меняется только слово в детали, не исход).
  Если выходит иначе — приёмка это печатает, а не скрывает.

═══ ГРАНИЦЫ, НАЗВАНЫ ПРЯМО
  · Живого не трогает: копии и стенды — mezo_stand (новый временный каталог на КАЖДЫЙ
    случай), подпроцессы испытуемых — со средой стенда (mezo_stand.stand_env).
  · (а)① собирает НАСТОЯЩИЙ контур через init-group.py пакета (тот же приём, что у
    bite-fresh-circuit.py) — САМОДЕЛЬНЫЙ урезанный стенд не гарантирует, что guard-all.py
    стенда доходит до конца без посторонних отказов (ему нужны все таблицы базы).
  · (б)-случаи испытывают guard_all.sub_guard()/installed_fingerprints() ЮНИТОМ (прямой
    импорт модуля, без подпроцесса) — быстро и не зависит от остального прогона; целостность
    «встроено в общий прогон» доказывает (а)① — общий прогон стенда реально запускается.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_target  # noqa: E402 — испытуемых ищем через MEZO_SCRIPTS_ROOT, не подъёмом на N каталогов

# было: MEZO_SCRIPTS = TREE_ROOT / ".mezosync" / "scripts" (TREE_ROOT = HERE.parent) — верно
# ТОЛЬКО когда приёмка лежит на один уровень под корнем контура (vnext-tools/ в живом
# Atlas). В пакете этот же файл лежит в vnext/prototype/ — уровнем ГЛУБЖЕ, и подъём на один
# каталог даёт vnext/.mezosync/scripts, которого нет НИГДЕ (ни в пакете, ни в контуре):
# отсюда «испытуемых инструментов нет» и код 2 (карточка #659). scripts_root() читает
# MEZO_SCRIPTS_ROOT (ставит bite-all.py по --target) и лишь при его отсутствии падает на
# mezo_paths.live_scripts() — не зависит от того, на сколько уровней приёмка вложена.
MEZO_SCRIPTS = mezo_target.scripts_root()
UPDATE_TOOLS = MEZO_SCRIPTS / "update-tools.py"
GUARD_ALL = MEZO_SCRIPTS / "guard-all.py"
TARGET_NAME = "check-acceptance-env.py"      # звено, из-за которого заведена карточка #637/#638

# ── ЯКОРЯ ПОЛОМОК — каждый встречается в СВОЁМ файле ровно один раз (проверено при сборке) ──
CLOSURE_ANCHOR = "                elif f.name in closure:"
CLOSURE_BROKEN = ("                elif f.name in closure and False:  "
                  "# ПОЛОМКА no-closure — замыкание отключено")
DISCR_ANCHOR = "            _FINGERPRINTS_CACHE = json.loads(row[0]) if row and row[0] else {}"
DISCR_BROKEN = ("            _FINGERPRINTS_CACHE = {}  "
                "# ПОЛОМКА no-discriminator — отпечатки не читаются")


def find_pack() -> Path:
    """Клон пакета — тот же порядок поиска, что у bite-fresh-circuit.py: шаблон контура
    (mezo_paths.template_root), затем раскладки от расположения файла — сам пакет (приёмка
    лежит в его vnext/prototype) и клон рядом с контуром. Путь машины литералом не держим:
    перенос в образец отказывает на нём, а у потребителя он неверен."""
    candidates = []
    try:
        candidates.append(mezo_paths.template_root())
    except SystemExit:
        pass
    candidates += [HERE.parent.parent, HERE.parent.parent / "gordipack",
                   HERE.parent / "gordipack"]
    for c in candidates:
        if c and (c / "scripts" / "init-group.py").exists():
            return c
    sys.exit(f"⛔ ПАКЕТ НЕ НАЙДЕН ни в одном из мест: {[str(c) for c in candidates if c]}")


PACK = find_pack()

CASES = 0
DIFFER = 0
FAILED: list[str] = []


def case(title: str, ok: bool, detail, differ: bool = True) -> bool:
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    if not ok:
        FAILED.append(title)
    return ok


def broken_copy(src: Path, anchor: str, replacement: str, prefix: str) -> Path:
    """Копия `src` с ОДНОЙ подменённой строкой — якорь обязан встретиться в файле РОВНО
    один раз, иначе испытуемое изменилось и поломка бьёт мимо (или задевает лишнее)."""
    text = src.read_text(encoding="utf-8")
    n = text.count(anchor)
    if n != 1:
        sys.exit(f"⛔ ЯКОРЬ ПОЛОМКИ ВСТРЕЧЕН {n} РАЗ (ждали 1) в {src.name} — испытуемое "
                 f"изменилось, поломка бьёт мимо или задевает лишнее")
    dest_dir = mezo_stand.new(prefix)
    (dest_dir / src.name).write_text(text.replace(anchor, replacement), encoding="utf-8")
    # соседи едут рядом — без них подмена не запустится (import mezo_paths/mezo_stand по имени)
    for neighbour in ("mezo_paths.py", "mezo_stand.py"):
        n_src = MEZO_SCRIPTS / neighbour
        if n_src.exists():
            shutil.copy2(n_src, dest_dir / neighbour)
    return dest_dir / src.name


def import_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_fresh_stand(prefix: str) -> tuple[Path, Path]:
    """Настоящий контур из ПАКЕТА (init-group.py) — тот же приём, что у bite-fresh-circuit.py.
    Полная сборка гарантирует РАБОЧИЙ guard-all.py стенда (все таблицы базы, все звенья) —
    урезанный набросок ронял бы сторонние проверки ПОСТОРОННЕЙ причиной, не нашей.

    ⚖️ env= НЕ ВОЗВРАЩАЕТСЯ отсюда третьим звеном — check-acceptance-env.py трассирует
    `env=mezo_stand.stand_env(...)` до трёх присваиваний В СВОЕЙ ФУНКЦИИ, а не сквозь чужую
    (звонящий сам зовёт `mezo_stand.stand_env(root)` у себя — один шаг, виден проверке)."""
    root = mezo_stand.new(prefix)
    env = mezo_stand.stand_env(root)
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str(PACK / "scripts" / "init-group.py"),
                        "--name", "bite-untn", "--path", str(mez), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
    if r.returncode != 0 or not (mez / "scripts" / "guard-all.py").exists():
        out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        sys.exit("⛔ СБОРКА СТЕНДА НЕ ВЫШЛА (init-group.py): "
                 + (out[-1] if out else f"код {r.returncode}"))
    return root, mez


def minimal_contour(prefix: str) -> tuple[Path, Path]:
    """Стенд-заглушка БЕЗ init-group.py — годится там, где guard-all.py стенда не зовём:
    только meta (таблица есть, может быть пустой) и .mezosync/scripts/."""
    root = mezo_stand.new(prefix)
    scripts = root / ".mezosync" / "scripts"
    scripts.mkdir(parents=True)
    db = root / ".mezosync" / "mezosync.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()
    return root, scripts


def plan_shows_new(out: str, name: str) -> bool:
    return bool(re.search(rf"\+\s+{re.escape(name)}\b.*появится", out))


def forget_link(mez: Path, name: str) -> None:
    """Контур «собран ДО того, как звено стало зваться»: у него нет ни файла, ни отпечатка
    установки этого звена. Одно удаление файла дало бы другой случай — «звено стояло и
    ПРОПАЛО» (отпечаток остался), а сосед, который обновляется, звена не имел никогда."""
    (mez / "scripts" / name).unlink()
    conn = sqlite3.connect(str(mez / "mezosync.db"))
    stamps = json.loads(dict(conn.execute("SELECT key, value FROM meta")).get("template_files_sha") or "{}")
    stamps.pop(name, None)
    conn.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (json.dumps(stamps, ensure_ascii=False),))
    conn.commit()
    conn.close()


# ── (а) ① + ③ — один стенд служит обоим: ③ снимает множество ДО того, как ① его портит ──
def case_a1_and_a3(update_tools: Path, break_mode: str):
    stand, mez = build_fresh_stand("bite-untn-a1-")
    env = mezo_stand.stand_env(stand)
    scripts = mez / "scripts"
    if not (scripts / TARGET_NAME).exists():
        case("(а) предпосылка: свежая сборка сама кладёт " + TARGET_NAME, False,
             "звена нет уже в свежей сборке — случай на этом пакете неприменим", differ=False)
        return

    # (а)③ БЛИЗНЕЦ — множество, которое ЗДЕСЬ И СЕЙЧАС положил init-group.py шагом 7б
    pack_script_names = {p.name for p in (PACK / "scripts").glob("*.py")} - {"init-group.py"}
    linked_by_initgroup = {p.name for p in scripts.glob("*.py")} - pack_script_names
    mod = import_module_from(update_tools, "untn_update_tools_under_test")
    raw_closure = mod.closure_of_prototype_links(PACK / "scripts", PACK / "vnext" / "prototype")
    # ⚖️ ИМЕНА, КОТОРЫЕ ЕСТЬ И В scripts/, И В vnext/prototype (мосты вроде mezo_paths.py,
    # продублированные нарочно) — closure_of_prototype_links() их всё равно называет (входят
    # в цепочку ссылок), а init-group.py 7б их НЕ СЧИТАЕТ «звеном»: шаг 7а уже положил файл
    # ИМЕНЕМ раньше 7б, `if not (tools_dir/name).exists()` гасит счётчик. update-tools.py той
    # же причиной пропускает их через `if rel in src_index: continue` — они едут путём
    # scripts/, не путём vnext/prototype. Сравниваем «что реально кладёт 7б» — ТУ ЖЕ часть
    # множества closure_of_prototype_links(), какую видит вызывающий её код.
    mine = raw_closure - pack_script_names
    same = mine == linked_by_initgroup
    detail = (f"{len(mine)} имён совпадают" if same else
             f"РАСХОДЯТСЯ: только у update-tools {sorted(mine - linked_by_initgroup) or '—'}; "
             f"только у init-group.py {sorted(linked_by_initgroup - mine) or '—'}")
    case("(а)③ БЛИЗНЕЦ: множество замыкания update-tools.py = множество звеньев init-group.py 7б",
        same, detail)

    # (а)① ГЛАВНЫЙ — симулируем «контур собран ДО того, как звено стало зваться»
    forget_link(mez, TARGET_NAME)
    r_plan = subprocess.run([sys.executable, str(update_tools), "--source", str(PACK)],
                            capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    plan_out = (r_plan.stdout or "") + (r_plan.stderr or "")
    tag = "" if break_mode != "no-closure" else " [под поломкой no-closure]"
    case(f"(а)① план: звено из замыкания источника показано «+ … появится»{tag}",
        plan_shows_new(plan_out, TARGET_NAME),
        next((l for l in plan_out.splitlines() if TARGET_NAME in l), "звено в плане не названо"))

    r_apply = subprocess.run([sys.executable, str(update_tools), "--source", str(PACK), "--apply"],
                             capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    placed = (scripts / TARGET_NAME).exists()
    case(f"(а)① --apply кладёт звено{tag}", placed,
        f"код {r_apply.returncode}; файл {'на месте' if placed else 'НЕТ'}")

    rg = subprocess.run([sys.executable, str(scripts / "guard-all.py")],
                        capture_output=True, text=True, encoding="utf-8", timeout=280, env=env)
    out = (rg.stdout or "") + (rg.stderr or "")
    line = next((l for l in out.splitlines() if "приёмки: env закреплённого стенда" in l), None)
    # ⚖️ С вариантом «б» отсутствующее звено даёт уже не «гард не найден», а ⚠️ «не приехало»
    # (код 0) — поэтому одного «не гард не найден» мало: звено обязано РЕАЛЬНО стоять и
    # отработать, строки «не приехало» про него быть не должно. Иначе этот случай перестал бы
    # отличать «а» от «б» (найдено PROTO: под поломкой no-closure он проходил).
    not_arrived = any("не приехало" in l and TARGET_NAME in l for l in out.splitlines())
    case(f"(а)① общий прогон стенда: подпроверка звена отработала — ни «гард не найден», "
         f"ни «не приехало»{tag}",
        bool(line) and line.lstrip().startswith("✅") and "гард не найден" not in line
        and not not_arrived,
        (line.strip() if line else "строка подпроверки не встретилась в полном выводе прогона")
        + (" · есть строка «не приехало»" if not_arrived else ""))


# ── (а)② ВСТРЕЧНЫЙ — незваный файл источника остаётся вне обновления ──────────────────────
def case_a2(update_tools: Path):
    src_copy = mezo_stand.new("bite-untn-a2-src-")
    shutil.copytree(PACK / "scripts", src_copy / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    proto_copy = src_copy / "vnext" / "prototype"
    shutil.copytree(PACK / "vnext" / "prototype", proto_copy,
                    ignore=shutil.ignore_patterns("__pycache__"))
    orphan = "bite-untn-orphan-nobody-calls-me.py"
    (proto_copy / orphan).write_text(
        '# -*- coding: utf-8 -*-\n"""подопытный (карточка #637 ②): этот файл источника не '
        'зовёт по имени НИ ОДИН скрипт scripts/, и его у контура нет — обязан остаться вне '
        'обновления, а не выдуматься."""\n', encoding="utf-8")

    stand, scripts = minimal_contour("bite-untn-a2-stand-")
    # ⚖️ У СТЕНДА УЖЕ СТОИТ ВСЁ, КРОМЕ ПОДОПЫТНОГО — единственный различающий остаток. Пустой
    # scripts/ дал бы ~250 «вне обновления» разом (у пустого стенда «нет» вообще всего из
    # vnext/prototype источника), а печать называет только первые 4 имени — подопытный тонул
    # бы среди чужих, и случай был бы не о нём.
    for f in proto_copy.glob("*.py"):
        if f.name != orphan:
            shutil.copy2(f, scripts / f.name)
    env = mezo_stand.stand_env(stand)
    r_plan = subprocess.run([sys.executable, str(update_tools), "--source", str(src_copy),
                             "--db", str(stand / ".mezosync" / "mezosync.db")],
                            capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    plan_out = (r_plan.stdout or "") + (r_plan.stderr or "")
    ok1 = (orphan in plan_out and "Вне обновления" in plan_out
          and not plan_shows_new(plan_out, orphan))
    case("(а)② ВСТРЕЧНЫЙ: незваный файл источника — «Вне обновления», не «+ появится»",
        ok1, next((l for l in plan_out.splitlines() if orphan in l), "имя не встречено в плане"))

    r_apply = subprocess.run([sys.executable, str(update_tools), "--source", str(src_copy),
                              "--db", str(stand / ".mezosync" / "mezosync.db"), "--apply"],
                             capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    laid = (scripts / orphan).exists()
    case("(а)② --apply НЕ кладёт незваный файл", not laid,
        f"{orphan}: {'ПОЛОЖЕН — беда' if laid else 'не положен, как и ждали'} (код {r_apply.returncode})")


# ── (а)④ ПУТЬ СОСЕДА — старая копия обновляется до новой, второй план уже видит звено ─────
def case_a4(update_tools_src_file: Path, break_mode: str):
    stand, mez = build_fresh_stand("bite-untn-a4-")
    env = mezo_stand.stand_env(stand)
    scripts = mez / "scripts"
    if not (scripts / TARGET_NAME).exists():
        case("(а)④ предпосылка не выполнена", False,
             "свежая сборка не положила звено — случай неприменим", differ=False)
        return
    forget_link(mez, TARGET_NAME)                  # контур «старый»: звена никогда не было

    src_copy = mezo_stand.new("bite-untn-a4-src-")
    shutil.copytree(PACK / "scripts", src_copy / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PACK / "vnext" / "prototype", src_copy / "vnext" / "prototype",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(update_tools_src_file, src_copy / "scripts" / "update-tools.py")

    # «Старый» update-tools.py приёмка строит САМА: испытуемый текст без строки замыкания и с
    # пометкой в конце (содержимое заведомо иное, чем у источника). Прежде «старым» был тот, что
    # положила сборка из пакета, — и случай мерил отставание пакета от живого: после сведения
    # пакета старый = новый, и случай проваливался навсегда (найдено PROTO живым прогоном после
    # переноса в пакет, 2026-09-14). Отпечаток установки ставится как у положенного сборкой —
    # иначе обновление сочло бы файл «правленым у тебя» и не тронуло.
    tested_text = Path(update_tools_src_file).read_text(encoding="utf-8")
    if CLOSURE_ANCHOR not in tested_text and CLOSURE_BROKEN not in tested_text:
        case("(а)④ предпосылка: в испытуемом update-tools.py нет строки замыкания", False,
             CLOSURE_ANCHOR.strip(), differ=False)
        return
    old_update_tools = scripts / "update-tools.py"
    old_update_tools.write_text(tested_text.replace(CLOSURE_ANCHOR, CLOSURE_BROKEN, 1)
                                + "\n# старая копия, построенная приёмкой: без замыкания\n",
                                encoding="utf-8")
    old_fp = hashlib.sha256(old_update_tools.read_bytes().replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]
    conn = sqlite3.connect(str(mez / "mezosync.db"))
    stamps = json.loads(dict(conn.execute("SELECT key, value FROM meta")).get("template_files_sha") or "{}")
    stamps["update-tools.py"] = old_fp
    conn.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (json.dumps(stamps, ensure_ascii=False),))
    conn.commit()
    conn.close()
    r1 = subprocess.run([sys.executable, str(old_update_tools), "--source", str(src_copy), "--apply"],
                        capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    brought_new = (scripts / "update-tools.py").exists() and \
        (scripts / "update-tools.py").read_bytes() == (src_copy / "scripts" / "update-tools.py").read_bytes()
    case("(а)④ первый --apply приносит НОВЫЙ update-tools.py", brought_new, f"код {r1.returncode}")

    r2 = subprocess.run([sys.executable, str(scripts / "update-tools.py"), "--source", str(src_copy)],
                        capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    out2 = (r2.stdout or "") + (r2.stderr or "")
    tag = "" if break_mode != "no-closure" else " [под поломкой no-closure]"
    case(f"(а)④ ПОВТОРНЫЙ план (уже новым update-tools.py) показывает «+ {TARGET_NAME}»{tag}",
        plan_shows_new(out2, TARGET_NAME),
        next((l for l in out2.splitlines() if TARGET_NAME in l), "звено не названо"))


# ── (б) discriminator юнитом — прямой вызов sub_guard(), без подпроцесса ──────────────────
def make_guard_db(prefix: str, fingerprints: dict) -> Path:
    root = mezo_stand.new(prefix)
    db = root / "mezosync.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?)",
                (json.dumps(fingerprints, ensure_ascii=False),))
    conn.commit()
    conn.close()
    return db


def probe_sub_guard(guard_mod, db_path: Path, target: Path) -> tuple[bool | None, str]:
    guard_mod.DB = db_path
    guard_mod._FINGERPRINTS_CACHE = None
    guard_mod.RESULTS = []
    buf = StringIO()
    with redirect_stdout(buf):
        guard_mod.sub_guard("зонд-untn", None, set(), script_path=str(target))
    ok = guard_mod.RESULTS[0][1] if guard_mod.RESULTS else None
    return ok, buf.getvalue().strip()


def case_b(guard_all: Path, break_mode: str):
    # guard-all.py резолвит DB = mezo_paths.default_db(__file__) НА ИМПОРТЕ (module-level) —
    # копия поломки живёт в свежем временном каталоге без своего mezosync.db, а наш собственный
    # tree/.mezosync/ несёт только scripts/ (без базы — её мы не копируем, база живая ro).
    # Даём ему ЛЮБОЙ валидный контейнер-заглушку через MEZO_CONTAINER; конкретную DB для
    # каждого под-случая probe_sub_guard() переставляет уже ПОСЛЕ импорта.
    boot_root, _boot_scripts = minimal_contour("bite-untn-b-boot-")
    os.environ["MEZO_CONTAINER"] = str(boot_root)
    mod = import_module_from(guard_all, "untn_guard_all_under_test")
    probe_dir = mezo_stand.new("bite-untn-b-probe-")
    missing = probe_dir / "acceptance-env-guard-probe.py"   # никогда не создаётся — цель отсутствует

    tag = "" if break_mode != "no-discriminator" else " [под поломкой no-discriminator]"

    db1 = make_guard_db("bite-untn-b1-", {missing.name: "deadbeefcafe1"})
    ok1, out1 = probe_sub_guard(mod, db1, missing)
    case("(б)① «ПРОПАЛО» (отпечаток у этого имени есть) — провал, код как раньше",
        ok1 is False, out1 or "(пустой вывод)")

    # ⚖️ Ожидание ФИКСИРОВАНО на «нормальное» (True) независимо от break_mode — тем же приёмом,
    # что у (а)①/(а)④: под поломкой случай обязан покраснеть САМ, а не по заранее подстроенному
    # ожиданию. Так «роняет ровно свой случай» видно ПО ЦВЕТУ (б)②, а не спрятано в условии.
    db2 = make_guard_db("bite-untn-b2-", {"другое-звено.py": "abc123abc1230"})
    ok2, out2 = probe_sub_guard(mod, db2, missing)
    # карточка #638 ①: «печатает готовую команду докладки» — команда с путём к update-tools.py
    # контура и флагом --apply обязана стоять в выводе, не только код 0.
    command_named = "update-tools.py" in out2 and "--apply" in out2 and "..." not in out2
    case(f"(б)② «не приехало» (отпечатков у контура полно, у ЭТОГО имени — нет) — ⚠️ код 0 "
         f"и готовая команда докладки{tag}",
        ok2 is True and command_named, out2 or "(пустой вывод)")

    db3 = make_guard_db("bite-untn-b3-", {})
    ok3, out3 = probe_sub_guard(mod, db3, missing)
    case("(б)③ ГРАНИЦА: у контура нет ни единого отпечатка — провал, различить нечем",
        ok3 is False, out3 or "(пустой вывод)")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_mode", default=None,
                    choices=["no-closure", "no-discriminator"],
                    help="нарочная поломка: no-closure (update-tools.py) | "
                         "no-discriminator (guard-all.py)")
    args = ap.parse_args()
    break_mode = args.break_mode

    # испытуемые инструменты ищутся в КОНТУРЕ (mezo_paths.live_scripts); из голого клона
    # пакета их рядом нет — это не провал случаев, а «не запустилась», и сказано словами
    missing = [p for p in (UPDATE_TOOLS, GUARD_ALL) if not Path(p).exists()]
    if missing:
        print("⛔ не запустилась: испытуемых инструментов нет — "
              + " · ".join(str(p) for p in missing)
              + ". Запускай в контуре: приёмка рядом с .mezosync/scripts контура "
                "либо MEZO_CONTAINER, указывающий на контур")
        return 2

    update_tools = (broken_copy(UPDATE_TOOLS, CLOSURE_ANCHOR, CLOSURE_BROKEN, "bite-untn-broken-ut-")
                   if break_mode == "no-closure" else UPDATE_TOOLS)
    guard_all = (broken_copy(GUARD_ALL, DISCR_ANCHOR, DISCR_BROKEN, "bite-untn-broken-ga-")
                if break_mode == "no-discriminator" else GUARD_ALL)

    case_a1_and_a3(update_tools, break_mode)
    case_a2(update_tools)
    case_a4(update_tools, break_mode)
    case_b(guard_all, break_mode)

    print()
    print("=" * 78)
    if break_mode:
        print(f"ПОЛОМКА {break_mode} — ждём провал РОВНО своего случая, прежние случаи — как были")
    print(f"случаев {CASES}, различающих {DIFFER}")
    if FAILED:
        print(f"🔴 ПРОВАЛЕНО {len(FAILED)}: " + " · ".join(FAILED))
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
