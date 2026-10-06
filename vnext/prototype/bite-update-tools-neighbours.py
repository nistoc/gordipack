# -*- coding: utf-8 -*-
r"""bite-update-tools-neighbours.py — приёмка карточек #637/#638 и #678 (Э4 Ш1, пункты «б», «в», «г»).

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

═══ ПРЕДМЕТ (б), (в), (г) — карточка #678 (Э4 Ш1)
  (б) ИМЯ ШАГА СХЕМЫ ЗВЕНОМ НЕ СЧИТАЕТСЯ. Имя шага из scripts/migrations/ стоит в кавычках в
      find-phoenix.py, а одноимённый файл есть и в vnext/prototype — раньше его клали ПЛОСКО
      рядом со скриптами (двойник шага схемы). Теперь такое имя не звено ни у update-tools.py
      (closure_of_prototype_links и разбор ниже), ни у init-group.py (шаг 7б — близнец).
  (в) отпечатки установки шагов схемы — тем же ключом «migrations/<имя>», что кладёт --apply:
      их снимают и --record-only, и init-group.py (шаг 7б′).
  (г) необязательный ключ файла путей prototype_install_dir — второй каталог установки для файлов
      vnext/prototype, которые УЖЕ лежат там: сравниваются и ставятся ТУДА; отпечатки — с
      приставкой «prototype-dir::/»; план называет каталог каждого файла; ничего не удаляется,
      ставятся только .py. Нет ключа — разбор ровно прежний.

═══ СЛУЧАИ #678 (в названии строки — «#678 <пункт>-<номер>»; в таблице ПОЛОМОК — идентификатор)
  без ключа (встречные к «г»)
      к-1  k-plan              без ключа план тот же: звено «+ появится», слов про второй каталог нет
      к-2  k-apply             без ключа --apply кладёт звено в скрипты, соседний каталог не тронут
      к-3  k-record            без ключа --record-only не пишет ни одного ключа с приставкой
  (б) имя шага схемы — не звено
      б-1  b-step-closure      замыкание не называет имя шага схемы (юнит closure_of_prototype_links)
      б-2  b-step-no-flat      план и --apply не кладут двойник шага плоско рядом со скриптами
      б-3  b-step-out-count    «Вне обновления» не считает имя шага схемы
      б-4  b-init-flat         свежая сборка (init-group.py) не кладёт двойник шага плоско
  (в) отпечатки шагов схемы
      в-1  v-record-key        --record-only снимает отпечаток шага ключом migrations/<имя>
      в-2  v-record-eq-apply   после --apply тот же набор ключей и отпечатков даёт --record-only
      в-3  v-init-key          свежая сборка пишет отпечаток каждому шагу схемы
  (г) второй каталог установки
      г-1  g-header            ключ прочитан: план называет второй каталог
      г-2  g-markers           план называет каталог каждого файла («→ скрипты» / «→ второй каталог»)
      г-3  g-compare-there     файл, уже лежащий во втором каталоге, сравнивается ТАМ
      г-4  g-twin-own-key      одноимённые файлы двух каталогов судятся каждый по СВОЕМУ отпечатку
      г-5  g-out-count         «Вне обновления» не считает файлы, лежащие во втором каталоге
      г-6  g-apply-there       --apply ставит файлы второго каталога ТУДА
      г-7  g-link-not-laid     звено из замыкания, уже лежащее во втором каталоге, не кладётся в скрипты
      г-8  g-keys-apart-apply  отпечатки второго каталога — с приставкой, одноимённые не сливаются
      г-9  g-record-second     --record-only снимает отпечатки и со второго каталога
      г-10 g-only-py           ставятся только .py, лишнее не удаляется
      г-11 g-dir-missing       ключ есть, каталога нет — сказано словами
      г-12 g-file-unreadable   файл путей не читается — сказано словами, не трассировка
      г-13 g-key-is-scripts    ключ указывает на каталог скриптов — второго каталога нет, сказано словами
      г-14 g-own-edit          своя правка файла второго каталога не затирается; про --merge сказано
      г-15 g-guard-prefix      guard-all.py не принимает ключ с приставкой за имя файла первого каталога
      г-16 g-help              --help описывает ключ
      г-17 g-history           файл второго каталога без отпечатка: история пакета ищется по vnext/prototype/<имя>
      г-18 g-prefix-hidden     служебная приставка ключа в плане и итоге --apply не показывается
      г-19 g-apply-count       итог --apply называет число файлов, взятых во второй каталог
      г-20 g-record-count      итог --record-only называет число отпечатков второго каталога
      г-21 g-record-note       --record-only при ключе без каталога говорит об этом
      г-22 g-doc               шапка mezo_paths.py (обе копии) называет ключ
      г-23 g-own-history       «✋» у файла второго каталога при источнике с историей: план печатается целиком

═══ ПОЛОМКИ (--break), ЯКОРЬ — строка, встречающаяся в файле РОВНО один раз
  Каждая поломка — копия ОДНОГО испытуемого файла с одной подменённой строкой; для init-group.py —
  копия пакета с подменой в init-group.py. Таблица BREAKS ниже несёт для каждой поломки ЗАРАНЕЕ
  записанное множество случаев, которые она обязана провалить: приёмка сверяет его с фактом
  (множества равны ⇒ «ожидание подтвердилось»; иначе печатает расхождение и сохраняет стенды).
  no-closure        — update-tools.py: строки замыкания обезврежены (#637).
  no-discriminator  — guard-all.py: чтение отпечатков всегда отдаёт пустой словарь (#638).
  Поломки #678 — см. BREAKS: по одной на каждое место правки (update-tools.py, init-group.py,
  mezo_paths.py, guard-all.py), у каждой в таблице названа причина падения.

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
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import types
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

# ── карточка #678 (Э4 Ш1 «б», «в», «г»): ИМЕНА И ЯКОРЯ ───────────────────────────────────────
SECOND_KEY = "prototype_install_dir"      # ключ файла путей (.mezosync/local/paths.json)
SECOND_PREFIX = "prototype-dir::/"        # приставка ключа отпечатка у файла второго каталога
STEP_NAME = "20260907-step-x.py"          # имя шага схемы: есть в scripts/migrations/ И в vnext/prototype
LINK_NAME = "linkfile.py"                 # звено из замыкания (его зовёт alpha.py)
ORPHAN_NAME = "orphan.py"                 # звено, которого не зовёт никто и нет ни в одном каталоге контура
ORPHAN_SECOND = "orphan2.py"              # то же, но лежит во втором каталоге контура
TWIN_NAME = "twin.py"                     # одно имя в scripts/ И в vnext/prototype источника
NOTES_NAME = "pack-notes.md"              # не .py: ставиться не должен
SECOND_DIR_NAME = "vnext-tools"           # как у контура Atlas

# содержимое файлов источника (двойник — версия 2) и контура (версия 1); пишется БАЙТАМИ с LF
SOURCE_FILES = {
    "scripts/alpha.py": f'X = "{LINK_NAME}"\n',
    "scripts/finder.py": f'Y = "{STEP_NAME}"\n',
    f"scripts/migrations/{STEP_NAME}": "# шаг схемы\n",
    f"scripts/{TWIN_NAME}": "# двойник — каталог scripts, версия 2\n",
    f"vnext/prototype/{STEP_NAME}": "# двойник шага схемы из vnext/prototype\n",
    f"vnext/prototype/{LINK_NAME}": "# звено — версия 2\n",
    f"vnext/prototype/{ORPHAN_NAME}": "# этот файл не зовёт никто\n",
    f"vnext/prototype/{ORPHAN_SECOND}": "# этого файла никто не зовёт, у контура он лежит во втором каталоге — версия 2\n",
    f"vnext/prototype/{TWIN_NAME}": "# двойник — каталог vnext/prototype, версия 2\n",
}
INSTALLED_SCRIPTS_TWIN = "# двойник — каталог scripts, версия 1\n"
INSTALLED_SECOND = {
    LINK_NAME: "# звено — версия 1\n",
    TWIN_NAME: "# двойник — каталог vnext/prototype, версия 1\n",
    ORPHAN_SECOND: "# этого файла никто не зовёт, у контура он лежит во втором каталоге — версия 1\n",
}

# якоря update-tools.py — каждый встречается в файле ровно один раз (проверено при сборке)
UT_CLOSURE_STEP = "        if name in schema_steps:"
UT_PLAN_STEP = "                elif f.name in schema_step_names:"
UT_RECORD_RGLOB = 'for f in sorted(tools_now.rglob("*.py"))'
UT_RECORD_SECOND = '                for f in sorted(second_dir.glob("*.py")):'
UT_KEY_READ = "    if res.outcome == mezo_paths.LOCAL_DECLARED:"
UT_MISSING_DIR = "        if res.path is not None and res.path.is_dir():"
UT_UNREADABLE = "    if res.outcome == mezo_paths.LOCAL_UNREADABLE:"
UT_NO_KEY_TAIL = "    return None, None\n\n\n# 🪤 КАРТОЧКА #637 (находка COORD"
UT_IS_SCRIPTS = "    if second_dir is not None and second_dir.resolve() == tools.resolve():"
UT_INDEX = "                if in_second:\n                    src_index[second_rel(f.name)] = f\n"
UT_LINK_LAID = "                    if not in_second:"
UT_OUT_COUNT = "                elif not in_second:"
UT_KEY_FORM = "    return pathlib.Path(rel).as_posix()"
UT_WHERE = '            return "  → второй каталог" if is_second_rel(rel) else "  → скрипты"'
UT_APPLY_WRITE = "            shutil.copy2(src_index[rel], dest_of(rel))"
UT_GLOB_ALL = '            for f in sorted(linked_dir.glob("*.py")):'
UT_HELP = "epilog=HELP_SECOND_DIR,"
UT_MERGE_NOTE = "            if any(is_second_rel(r) for r in own_edits):"
UT_HISTORY_PATH = '                    git_rel_of[second_rel(f.name)] = "vnext/prototype/" + f.name'
UT_SHOWN = "            return rel.name if is_second_rel(rel) else str(rel)"
UT_OWN_APPLY = '("  (второй каталог)" if is_second_rel(x) else "")'
UT_APPLY_COUNT = "{sum(1 for r in taking if is_second_rel(r))}"
UT_RECORD_COUNT = "                        second_taken += 1"
UT_RECORD_NOTE = ('            if second_note:\n                print(f"⚠️ {second_note}")\n'
                  '            print("   Файлы НЕ тронуты')
UT_HEADER = ('            print(f"             второй (файлы vnext/prototype, которые УЖЕ лежат там) — '
             '{second_dir}")')
UT_PLAN_NOTE = '        if second_note:\n            print(f"⚠️ {second_note}")\n        print()\n'
# якоря init-group.py и mezo_paths.py
IG_STEP = "            if name in schema_step_names:\n"
IG_FP = '        fingerprints[f"migrations/{f.name}"] = _fingerprint(f.read_bytes())'
MP_DOC = "    prototype_install_dir   НЕОБЯЗАТЕЛЬНЫЙ"
GA_PREFIX_STRIP = ("            _FINGERPRINTS_CACHE = {k.split('::/')[-1]: v for k, v in json.loads(row[0]).items()} "
                   "if row and row[0] else {}  # ПОЛОМКА guard-prefix-confused — приставка срезана")


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
FAILED: list[str] = []          # названия проваленных случаев
FAILED_IDS: list[str] = []      # их идентификаторы (cid) — по ним сверяется ожидание поломки
SEEN_IDS: list[str] = []        # идентификаторы ВСЕХ прогнанных случаев (в таблице поломок не может быть чужих)
BREAK: str | None = None        # имя нарочной поломки этого прогона (None — прогон без поломки)


def case(title: str, ok: bool, detail, differ: bool = True, cid: str | None = None) -> bool:
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    if cid:
        SEEN_IDS.append(cid)
    if not ok and BREAK and "[под поломкой" not in title:
        title += f" [под поломкой {BREAK}]"
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    if not ok:
        FAILED.append(title)
        FAILED_IDS.append(cid or "?")
    return ok


def broken_copy(src: Path, anchor: str, replacement: str, prefix: str, count: int = 1) -> Path:
    """Копия `src` с подменённой строкой — якорь обязан встретиться в файле РОВНО столько раз,
    сколько названо (по умолчанию один), иначе испытуемое изменилось и поломка бьёт мимо
    (или задевает лишнее). Больше одного раза — только когда поломка и есть «переименование»."""
    text = src.read_text(encoding="utf-8")
    n = text.count(anchor)
    if n != count:
        sys.exit(f"⛔ ЯКОРЬ ПОЛОМКИ ВСТРЕЧЕН {n} РАЗ (ждали {count}) в {src.name} — испытуемое "
                 f"изменилось, поломка бьёт мимо или задевает лишнее")
    dest_dir = mezo_stand.new(prefix)
    (dest_dir / src.name).write_text(text.replace(anchor, replacement), encoding="utf-8")
    # соседи едут рядом — без них подмена не запустится (import mezo_paths/mezo_stand по имени);
    # сам испытуемый файл поверх своей подмены не кладём (случай «шапка mezo_paths.py»)
    for neighbour in ("mezo_paths.py", "mezo_stand.py"):
        n_src = MEZO_SCRIPTS / neighbour
        if n_src.exists() and neighbour != src.name:
            shutil.copy2(n_src, dest_dir / neighbour)
    return dest_dir / src.name


def import_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_fresh_stand(prefix: str, pack_root: Path | None = None) -> tuple[Path, Path]:
    """Настоящий контур из ПАКЕТА (init-group.py) — тот же приём, что у bite-fresh-circuit.py.
    Полная сборка гарантирует РАБОЧИЙ guard-all.py стенда (все таблицы базы, все звенья) —
    урезанный набросок ронял бы сторонние проверки ПОСТОРОННЕЙ причиной, не нашей.

    ⚖️ env= НЕ ВОЗВРАЩАЕТСЯ отсюда третьим звеном — check-acceptance-env.py трассирует
    `env=mezo_stand.stand_env(...)` до трёх присваиваний В СВОЕЙ ФУНКЦИИ, а не сквозь чужую
    (звонящий сам зовёт `mezo_stand.stand_env(root)` у себя — один шаг, виден проверке)."""
    root = mezo_stand.new(prefix)
    env = mezo_stand.stand_env(root)
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str((pack_root or PACK) / "scripts" / "init-group.py"),
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
        same, detail, cid="a3-twin")

    # (а)① ГЛАВНЫЙ — симулируем «контур собран ДО того, как звено стало зваться»
    forget_link(mez, TARGET_NAME)
    r_plan = subprocess.run([sys.executable, str(update_tools), "--source", str(PACK)],
                            capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    plan_out = (r_plan.stdout or "") + (r_plan.stderr or "")
    tag = "" if break_mode != "no-closure" else " [под поломкой no-closure]"
    case(f"(а)① план: звено из замыкания источника показано «+ … появится»{tag}",
        plan_shows_new(plan_out, TARGET_NAME),
        next((l for l in plan_out.splitlines() if TARGET_NAME in l), "звено в плане не названо"),
        cid="a1-plan")

    r_apply = subprocess.run([sys.executable, str(update_tools), "--source", str(PACK), "--apply"],
                             capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    placed = (scripts / TARGET_NAME).exists()
    case(f"(а)① --apply кладёт звено{tag}", placed,
        f"код {r_apply.returncode}; файл {'на месте' if placed else 'НЕТ'}", cid="a1-apply")

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
        + (" · есть строка «не приехало»" if not_arrived else ""), cid="a1-guard")


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
        ok1, next((l for l in plan_out.splitlines() if orphan in l), "имя не встречено в плане"),
        cid="a2-plan")

    r_apply = subprocess.run([sys.executable, str(update_tools), "--source", str(src_copy),
                              "--db", str(stand / ".mezosync" / "mezosync.db"), "--apply"],
                             capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    laid = (scripts / orphan).exists()
    case("(а)② --apply НЕ кладёт незваный файл", not laid,
        f"{orphan}: {'ПОЛОЖЕН — беда' if laid else 'не положен, как и ждали'} (код {r_apply.returncode})",
        cid="a2-apply")


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
    case("(а)④ первый --apply приносит НОВЫЙ update-tools.py", brought_new, f"код {r1.returncode}",
         cid="a4-first")

    r2 = subprocess.run([sys.executable, str(scripts / "update-tools.py"), "--source", str(src_copy)],
                        capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
    out2 = (r2.stdout or "") + (r2.stderr or "")
    tag = "" if break_mode != "no-closure" else " [под поломкой no-closure]"
    case(f"(а)④ ПОВТОРНЫЙ план (уже новым update-tools.py) показывает «+ {TARGET_NAME}»{tag}",
        plan_shows_new(out2, TARGET_NAME),
        next((l for l in out2.splitlines() if TARGET_NAME in l), "звено не названо"), cid="a4-replan")


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
        ok1 is False, out1 or "(пустой вывод)", cid="b1-lost")

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
        ok2 is True and command_named, out2 or "(пустой вывод)", cid="b2-notarrived")

    db3 = make_guard_db("bite-untn-b3-", {})
    ok3, out3 = probe_sub_guard(mod, db3, missing)
    case("(б)③ ГРАНИЦА: у контура нет ни единого отпечатка — провал, различить нечем",
        ok3 is False, out3 or "(пустой вывод)", cid="b3-border")

    # карточка #678 «г», правило (4): отпечаток файла ВТОРОГО каталога несёт приставку и не должен
    # читаться как отпечаток одноимённого файла первого. guard-all.py ищет по голому имени файла
    # (key = target.name), приставка пересечься с ним не может — это и фиксируется (правки в
    # guard-all.py нет, случай держит свойство на будущее).
    db4 = make_guard_db("bite-untn-b4-", {SECOND_PREFIX + missing.name: "abc123abc1230",
                                         "другое-звено.py": "abc123abc1231"})
    ok4, out4 = probe_sub_guard(mod, db4, missing)
    case("(#678 г-15) guard-all.py: отпечаток с приставкой второго каталога НЕ читается как отпечаток звена "
         "первого — «не приехало», а не «ПРОПАЛО»",
        ok4 is True and "ПРОПАЛО" not in out4 and "не приехало" in out4, out4 or "(пустой вывод)",
        cid="g-guard-prefix")


# ══ карточка #678 (Э4 Ш1 «б», «в», «г») ═══════════════════════════════════════════════════════
# Случаи строятся на ЛЁГКИХ контурах (таблица meta + каталог скриптов) и на искусственном
# источнике БЕЗ git: так каждый случай называет своё условие, а не зависит от остального
# содержимого пакета. Исключение — свежая сборка (б)④ и (в)③: настоящий init-group.py из пакета
# (или из его копии с поломкой) — иначе его не проверить.

def fp12(data: bytes) -> str:
    """Отпечаток установки так, как его считают инструменты: СОДЕРЖИМОЕ (LF, без хвоста), 12 знаков."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))        # байтами: на Windows write_text сам дописал бы CR
    return path


def make_source(prefix: str, extra: dict | None = None) -> Path:
    """Искусственный источник (не репозиторий): scripts/ и vnext/prototype/ из SOURCE_FILES."""
    src = mezo_stand.new(prefix)
    for rel, text in {**SOURCE_FILES, **(extra or {})}.items():
        put(src / rel, text)
    return src


def make_contour(prefix: str, update_tools: Path, *, paths=None, scripts_files: dict | None = None,
                 second_files: dict | None = None, stamp: bool = True, stamp_second: bool = True,
                 extra_stamps: dict | None = None) -> types.SimpleNamespace:
    """Лёгкий контур: база с одной таблицей meta, каталог скриптов с копией испытуемого
    update-tools.py (вместе с соседями), по желанию — файл путей и второй каталог установки.

    paths — словарь (пишется как JSON; «<root>» в значении заменяется путём стенда) или строка
    (пишется как есть — для случая «файл путей не читается»); None — файла путей нет вовсе.
    stamp — у положенных файлов есть отпечаток установки (контур, обновлявшийся инструментом);
    stamp=False — контур собран ДО отпечатков. Отпечатки второго каталога — с приставкой."""
    root = mezo_stand.new(prefix)
    mez = root / ".mezosync"
    scripts = mez / "scripts"
    scripts.mkdir(parents=True)
    db = mez / "mezosync.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    stamps: dict = {}
    for rel, text in (scripts_files or {}).items():
        put(scripts / rel, text)
        stamps[rel] = fp12(text.encode("utf-8"))
    second = None
    if second_files is not None:
        second = root / SECOND_DIR_NAME
        second.mkdir()
        for name, text in second_files.items():
            put(second / name, text)
            if stamp_second:
                stamps[SECOND_PREFIX + name] = fp12(text.encode("utf-8"))
    stamps.update(extra_stamps or {})
    if stamp:
        conn.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?)",
                     (json.dumps(stamps, ensure_ascii=False),))
    conn.commit()
    conn.close()
    if paths is not None:
        local = mez / "local"
        local.mkdir()
        if isinstance(paths, dict):
            text = json.dumps({k: v.replace("<root>", str(root)) for k, v in paths.items()},
                              ensure_ascii=False)
        else:
            text = paths
        put(local / "paths.json", text)
    tool = mezo_stand.copy_tool(update_tools, scripts)
    return types.SimpleNamespace(root=root, mez=mez, scripts=scripts, db=db, second=second, tool=tool,
                                 env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"))


def key_contour(prefix: str, update_tools: Path, **kw) -> types.SimpleNamespace:
    """Контур со вторым каталогом и объявленным ключом (как у Atlas: относительный путь от контейнера)."""
    return make_contour(prefix, update_tools, paths={SECOND_KEY: SECOND_DIR_NAME},
                        scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN},
                        second_files=dict(INSTALLED_SECOND), **kw)


def run_ut(c, source: Path | None, *args) -> tuple[int, str]:
    cmd = [sys.executable, str(c.tool)]
    if source is not None:
        cmd += ["--source", str(source), "--db", str(c.db)]
    # среда стенда — вызовом здесь же, а не полем c.env: проверка закреплённой среды
    # (check-acceptance-env.py) прослеживает stand_env только внутри своей функции
    env = mezo_stand.stand_env(c.root, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd + list(args), capture_output=True, text=True, encoding="utf-8",
                       timeout=180, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def read_stamps(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'template_files_sha'").fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row and row[0] else {}


PLAN_ROW = re.compile(r"^\s+([+≠✋❓])\s+(\S+)(.*)$")


def plan_rows(out: str, name: str) -> list[tuple[str, str]]:
    """Строки плана про файл `name`: (знак, остаток строки). Знак — «+ ≠ ✋ ❓»."""
    rows = []
    for line in out.splitlines():
        m = PLAN_ROW.match(line)
        # приставка ключа в имени (если инструмент её показал) здесь срезается: её показ ловит свой случай
        if m and re.sub(r"^prototype-dir::[\\/]", "", m.group(2)) == name:
            rows.append((m.group(1), m.group(3)))
    return rows


def out_of_scope(out: str) -> tuple[int, str]:
    """Строка «Вне обновления: N звеньев … (имена)» — (N, имена); нет строки — (0, "")."""
    for line in out.splitlines():
        m = re.search(r"Вне обновления: (\d+) звеньев источника, которых у тебя нет \((.*?)\)", line)
        if m:
            return int(m.group(1)), m.group(2)
    return 0, ""


def make_git_source(prefix: str) -> Path:
    """Источник — настоящий репозиторий с двумя версиями звена vnext/prototype/linkfile.py:
    в первом коммите звено — версия 1 (то, что лежит у контура), во втором — версия 2.
    Имя и почта автора — флагами -c: ни одной настройки git не пишется."""
    repo = mezo_stand.new(prefix)

    def git(*args):
        r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=bite", "-c", "user.email=bite@example.invalid",
                            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            sys.exit(f"⛔ СТЕНД ИСТОЧНИКА НЕ СОБРАЛСЯ (git {args[0]}): {(r.stderr or r.stdout).strip()[:300]}")

    git("init", "-q")
    first = {**SOURCE_FILES, f"vnext/prototype/{LINK_NAME}": INSTALLED_SECOND[LINK_NAME]}
    for rel, text in first.items():
        put(repo / rel, text)
    git("add", "-A")
    git("commit", "-q", "-m", "версия 1")
    put(repo / "vnext" / "prototype" / LINK_NAME, SOURCE_FILES[f"vnext/prototype/{LINK_NAME}"])
    git("add", "-A")
    git("commit", "-q", "-m", "версия 2")
    # 🪤 ДЛИННЫЙ ПУТЬ СТЕНДА ПОДМЕНЯЕТ ПРИЧИНУ ПРОВАЛА (замер 06.10): git на Windows отказывает в
    # `git show <полное имя коммита>:<путь>`, если путь репозитория — около 190 знаков и больше
    # («failed to stat … Filename too long»: git проверяет, не файл ли этот аргумент, и упирается в предел
    # пути ≈260). update-tools.py зовёт git именно так и принимает отказ за «такого содержимого в истории
    # нет» — случай про историю тогда падает, хотя инструмент ни при чём. Здесь тот же вызов проверяется
    # сразу, и провал называет настоящую причину.
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    probe = subprocess.run(["git", "-C", str(repo), "show", f"{head}:vnext/prototype/{LINK_NAME}"],
                           capture_output=True)
    if probe.returncode != 0:
        sys.exit(f"⛔ СТЕНД ИСТОЧНИКА НЕ ГОДИТСЯ: git не читает файл из коммита по полному имени коммита — "
                 f"так его читает update-tools.py. Путь стенда {len(str(repo))} знаков (предел пути Windows ≈260): "
                 f"{(probe.stderr or b'').decode('utf-8', 'replace').strip()[:200]} 👉 запусти приёмку с коротким TEMP.")
    return repo


def same_bytes(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


# ── без ключа — «разбор тот же» (встречные случаи к (г)) ──────────────────────────────────────
def case_no_key(update_tools: Path):
    src = make_source("bite-untn-k-src-")
    link_src = src / "vnext" / "prototype" / LINK_NAME
    problems = []
    for label, paths in (("файла путей нет вовсе", None),
                         ("файл путей есть, ключа в нём нет", {"annex_dir": "нет-такого-каталога"})):
        c = make_contour("bite-untn-k-plan-", update_tools, paths=paths,
                         scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN},
                         second_files=dict(INSTALLED_SECOND), stamp_second=False)
        code, out = run_ut(c, src)
        link_rows = plan_rows(out, LINK_NAME)
        twin_rows = plan_rows(out, TWIN_NAME)
        count, names = out_of_scope(out)
        bad = []
        if code != 0:
            bad.append(f"код {code}")
        if [s for s, _ in link_rows] != ["+"] or "появится" not in "".join(r for _, r in link_rows):
            bad.append(f"звено {LINK_NAME} не «+ появится»: {link_rows}")
        if "второй (" in out or any("→" in r for _, r in link_rows + twin_rows):
            bad.append("в плане есть слова про второй каталог")
        if [s for s, _ in twin_rows] != ["≠"]:
            bad.append(f"одноимённый файл показан не одним «≠»: {twin_rows}")
        if ORPHAN_NAME not in names or ORPHAN_SECOND not in names:
            bad.append(f"в «Вне обновления» нет обоих незваных ({count}: {names})")
        if bad:
            problems.append(f"{label}: " + "; ".join(bad))
    case("(#678 к-1) без ключа ПЛАН ТОТ ЖЕ: звено — «+ появится», слов про второй каталог нет, "
         "файлы vnext-tools не замечены (каталог рядом лежит, ключа нет)",
        not problems, "; ".join(problems) or "оба вида «без ключа» — как прежде", cid="k-plan")

    c = make_contour("bite-untn-k-apply-", update_tools, paths={"annex_dir": "нет-такого-каталога"},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN},
                     second_files=dict(INSTALLED_SECOND), stamp_second=False)
    before = {n: (c.second / n).read_bytes() for n in INSTALLED_SECOND}
    code, out = run_ut(c, src, "--apply")
    stamps = read_stamps(c.db)
    bad = []
    if code != 0:
        bad.append(f"код {code}")
    if not same_bytes(c.scripts / LINK_NAME, link_src):
        bad.append(f"звено {LINK_NAME} не положено в скрипты")
    for n, b in before.items():
        if (c.second / n).read_bytes() != b:
            bad.append(f"файл соседнего каталога {n} изменён")
    if any("::" in k for k in stamps) or LINK_NAME not in stamps:
        bad.append(f"ключи отпечатков: {sorted(stamps)}")
    case("(#678 к-2) без ключа --apply кладёт звено в скрипты и не трогает соседний каталог vnext-tools; "
         "ключей с приставкой нет",
        not bad, "; ".join(bad) or f"звено в скриптах, vnext-tools нетронут, ключей {len(stamps)}",
        cid="k-apply")

    c = make_contour("bite-untn-k-record-", update_tools, paths={"annex_dir": "нет-такого-каталога"},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN},
                     second_files=dict(INSTALLED_SECOND), stamp=False)
    code, out = run_ut(c, src, "--record-only")
    stamps = read_stamps(c.db)
    want = {TWIN_NAME: fp12(INSTALLED_SCRIPTS_TWIN.encode("utf-8"))}
    case("(#678 к-3) без ключа --record-only снимает отпечатки только со скриптов — ни одного ключа с приставкой",
        code == 0 and stamps == want, f"код {code} · ключи {sorted(stamps)} · ждали {sorted(want)}",
        cid="k-record")


# ── (б) имя шага схемы — не звено ─────────────────────────────────────────────────────────────
def case_schema_step(update_tools: Path):
    src = make_source("bite-untn-s-src-")
    mod = import_module_from(update_tools, "untn_update_tools_schema_step")
    closure = mod.closure_of_prototype_links(src / "scripts", src / "vnext" / "prototype")
    case("(#678 б-1) замыкание звеньев НЕ называет имя шага схемы (оно есть в scripts/migrations/), "
         "а настоящее звено называет",
        LINK_NAME in closure and STEP_NAME not in closure, f"замыкание: {sorted(closure)}",
        cid="b-step-closure")

    c = make_contour("bite-untn-s-plan-", update_tools, paths=None,
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src)
    count, names = out_of_scope(out)
    case("(#678 б-3) «Вне обновления» не считает имя шага схемы: считаются только незваные "
         f"({ORPHAN_NAME}, {ORPHAN_SECOND})",
        code == 0 and count == 2 and STEP_NAME not in names and ORPHAN_NAME in names,
        f"код {code} · {count}: {names}", cid="b-step-out-count")

    c = make_contour("bite-untn-s-apply-", update_tools, paths=None,
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src, "--apply")
    flat_rows = plan_rows(out, STEP_NAME)
    bad = []
    if flat_rows:
        bad.append(f"в плане двойник шага строкой {flat_rows}")
    if (c.scripts / STEP_NAME).exists():
        bad.append("двойник шага схемы положен ПЛОСКО рядом со скриптами")
    if not same_bytes(c.scripts / "migrations" / STEP_NAME, src / "scripts" / "migrations" / STEP_NAME):
        bad.append("сам шаг схемы в migrations/ не положен")
    case("(#678 б-2) план и --apply не кладут двойник шага схемы плоско; сам шаг в migrations/ приезжает",
        code == 0 and not bad,
        "; ".join(bad) or f"код {code} · плоского {STEP_NAME} нет, migrations/{STEP_NAME} есть",
        cid="b-step-no-flat")


def case_init_group(pack_root: Path):
    """(б)④ и (в)③ — один стенд: свежая сборка настоящим init-group.py (из пакета или его копии)."""
    stand, mez = build_fresh_stand("bite-untn-i-", pack_root)
    scripts = mez / "scripts"
    migr_names = sorted(p.name for p in (PACK / "scripts" / "migrations").glob("*.py"))
    dups = [n for n in migr_names if (PACK / "vnext" / "prototype" / n).exists()]
    if not dups:
        case("(#678 б-4) предпосылка: в пакете есть двойник шага схемы в vnext/prototype", False,
             "двойника нет — случай ничего не различает", differ=False, cid="b-init-flat")
    else:
        flat = [n for n in migr_names if (scripts / n).exists()]
        case("(#678 б-4) свежая сборка (init-group.py) НЕ кладёт двойник шага схемы плоско рядом со скриптами",
            not flat, f"двойники в пакете: {dups} · плоско положены: {flat or 'нет'}", cid="b-init-flat")
    stamps = read_stamps(mez / "mezosync.db")
    laid = sorted(p.name for p in (scripts / "migrations").glob("*.py"))
    lacking = [n for n in laid
               if stamps.get(f"migrations/{n}") != fp12((scripts / "migrations" / n).read_bytes())]
    case("(#678 в-3) свежая сборка пишет отпечаток КАЖДОМУ шагу схемы ключом migrations/<имя> — тем же, что --apply",
        bool(laid) and not lacking,
        f"шагов схемы {len(laid)} · без верного отпечатка: {lacking[:3] or 'нет'}"
        + ("…" if len(lacking) > 3 else ""), cid="v-init-key")


# ── (в) --record-only снимает отпечатки шагов схемы ───────────────────────────────────────────
def case_record_migrations(update_tools: Path):
    src = make_source("bite-untn-v-src-")
    step_text = SOURCE_FILES[f"scripts/migrations/{STEP_NAME}"]
    c = make_contour("bite-untn-v1-", update_tools, paths=None, stamp=False,
                     scripts_files={f"migrations/{STEP_NAME}": step_text,
                                    TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src, "--record-only")
    stamps = read_stamps(c.db)
    want = {f"migrations/{STEP_NAME}": fp12(step_text.encode("utf-8")),
            TWIN_NAME: fp12(INSTALLED_SCRIPTS_TWIN.encode("utf-8"))}
    case("(#678 в-1) --record-only снимает отпечаток шага схемы ключом migrations/<имя> (раньше — только верхний уровень)",
        code == 0 and stamps == want, f"код {code} · ключи {sorted(stamps)} · ждали {sorted(want)}",
        cid="v-record-key")

    c = make_contour("bite-untn-v2-", update_tools, paths=None, stamp=False)
    code1, _ = run_ut(c, src, "--apply")
    by_apply = read_stamps(c.db)
    code2, _ = run_ut(c, src, "--record-only")
    by_record = read_stamps(c.db)
    case("(#678 в-2) после --apply --record-only даёт тот же набор ключей и отпечатков (включая migrations/…)",
        code1 == 0 and code2 == 0 and by_apply == by_record and f"migrations/{STEP_NAME}" in by_record,
        f"коды {code1}/{code2} · --apply: {sorted(by_apply)} · --record-only: {sorted(by_record)}",
        cid="v-record-eq-apply")


# ── (г) второй каталог установки ──────────────────────────────────────────────────────────────
def case_second_dir(update_tools: Path):
    src = make_source("bite-untn-g-src-")
    sp = src / "vnext" / "prototype"

    # — ПЛАН (контур с ключом, у файлов есть отпечатки установки) —
    c = key_contour("bite-untn-g-plan-", update_tools)
    code, out = run_ut(c, src)
    header = next((l for l in out.splitlines() if l.lstrip().startswith("второй (")), "")
    case("(#678 г-1) ключ прочитан: план называет второй каталог (его путь) рядом с каталогом скриптов",
        code == 0 and SECOND_DIR_NAME in header and "каталоги ... скрипты" in out,
        header.strip() or "строки «второй (…)» в плане нет", cid="g-header")

    link_rows, twin_rows = plan_rows(out, LINK_NAME), plan_rows(out, TWIN_NAME)
    alpha_rows, orphan2_rows = plan_rows(out, "alpha.py"), plan_rows(out, ORPHAN_SECOND)
    twin_marks = sorted("второй" if "→ второй каталог" in r else "скрипты" if "→ скрипты" in r else "—"
                        for _, r in twin_rows)
    second_link = [r for s, r in link_rows if s != "+"]
    bad = []
    if not second_link or not all("→ второй каталог" in r for r in second_link):
        bad.append(f"{LINK_NAME}: {link_rows}")
    if not alpha_rows or "→ скрипты" not in alpha_rows[0][1]:
        bad.append(f"alpha.py: {alpha_rows}")
    if not orphan2_rows or "→ второй каталог" not in orphan2_rows[0][1]:
        bad.append(f"{ORPHAN_SECOND}: {orphan2_rows}")
    if twin_marks != ["второй", "скрипты"]:
        bad.append(f"{TWIN_NAME}: метки {twin_marks}")
    case("(#678 г-2) план называет каталог КАЖДОГО файла: «→ скрипты» / «→ второй каталог»",
        not bad, "; ".join(bad) or "метки на месте у звена, нового файла, незваного и обоих одноимённых",
        cid="g-markers")

    plan_out = out
    seen_signs = {n: [s for s, _ in plan_rows(out, n)] for n in (LINK_NAME, ORPHAN_SECOND, TWIN_NAME)}
    ok = ("≠" in seen_signs[LINK_NAME] and "≠" in seen_signs[ORPHAN_SECOND]
          and seen_signs[TWIN_NAME].count("≠") == 2)
    case("(#678 г-3) файлы, УЖЕ лежащие во втором каталоге, сравниваются ТАМ: «≠ … обновится» у звена и "
         "у незваного, у одноимённого — по одному «≠» на каталог",
        ok, f"знаки: {seen_signs}", cid="g-compare-there")

    case("(#678 г-4) одноимённые файлы двух каталогов судятся каждый по СВОЕМУ отпечатку: оба «≠», ни «✋», ни «❓»",
        seen_signs[TWIN_NAME] == ["≠", "≠"], f"знаки у {TWIN_NAME}: {seen_signs[TWIN_NAME]}",
        cid="g-twin-own-key")

    count, names = out_of_scope(out)
    case("(#678 г-5) «Вне обновления» не считает файл, лежащий во втором каталоге: считается один незваный "
         f"({ORPHAN_NAME}), а {ORPHAN_SECOND} — нет",
        count == 1 and names == ORPHAN_NAME, f"{count}: {names}", cid="g-out-count")

    plan_link_signs = seen_signs[LINK_NAME]

    # — --apply —
    c = key_contour("bite-untn-g-apply-", update_tools)
    code, out = run_ut(c, src, "--apply")
    stamps = read_stamps(c.db)
    bad = []
    if code != 0:
        bad.append(f"код {code}")
    for name in INSTALLED_SECOND:
        if not same_bytes(c.second / name, sp / name):
            bad.append(f"{name} во втором каталоге не взят версией из vnext/prototype")
    if not same_bytes(c.scripts / TWIN_NAME, src / "scripts" / TWIN_NAME):
        bad.append(f"scripts/{TWIN_NAME} не взят версией из scripts/ источника")
    case("(#678 г-6) --apply ставит файлы второго каталога ТУДА (версией из vnext/prototype), а одноимённый "
         "файл скриптов — версией из scripts/", not bad,
        "; ".join(bad) or f"во втором каталоге обновлены {sorted(INSTALLED_SECOND)}, в скриптах — {TWIN_NAME}",
        cid="g-apply-there")

    case("(#678 г-18) служебная приставка ключа «prototype-dir::» в плане и в итоге --apply не показывается",
        "prototype-dir::" not in plan_out and "prototype-dir::" not in out,
        "приставки в выводе нет" if "prototype-dir::" not in plan_out + out else
        next(l.strip() for l in (plan_out + out).splitlines() if "prototype-dir::" in l),
        cid="g-prefix-hidden")
    case("(#678 г-19) итог --apply называет, сколько файлов взято во второй каталог",
        "из забранных — во второй каталог: 3" in out,
        next((l for l in out.splitlines() if "Забрано файлов" in l), "строки «Забрано файлов» нет"),
        cid="g-apply-count")

    laid_flat = (c.scripts / LINK_NAME).exists()
    case("(#678 г-7) звено из замыкания, УЖЕ лежащее во втором каталоге, не «+ появится» и в скрипты не кладётся",
        "+" not in plan_link_signs and not laid_flat,
        f"знаки у {LINK_NAME} в плане: {plan_link_signs} · в скриптах после --apply: "
        f"{'ЕСТЬ' if laid_flat else 'нет'}", cid="g-link-not-laid")

    want = {TWIN_NAME: fp12((src / "scripts" / TWIN_NAME).read_bytes()),
            SECOND_PREFIX + TWIN_NAME: fp12((sp / TWIN_NAME).read_bytes()),
            SECOND_PREFIX + LINK_NAME: fp12((sp / LINK_NAME).read_bytes()),
            SECOND_PREFIX + ORPHAN_SECOND: fp12((sp / ORPHAN_SECOND).read_bytes())}
    prefixed = {k for k in stamps if k.startswith(SECOND_PREFIX)}
    ok = (all(stamps.get(k) == v for k, v in want.items())
          and prefixed == {k for k in want if k.startswith(SECOND_PREFIX)}
          and stamps.get(TWIN_NAME) != stamps.get(SECOND_PREFIX + TWIN_NAME))
    wrong = [k for k, v in want.items() if stamps.get(k) != v]
    case("(#678 г-8) после --apply отпечатки второго каталога — с приставкой «prototype-dir::/», одноимённый "
         "файл первого каталога держит СВОЙ отпечаток (они разные)",
        ok, (f"ключи: {sorted(stamps)}" + (f" · нет или не те отпечатки у: {wrong}" if wrong else "")
             + (f" · у одноимённых отпечаток один: {stamps.get(TWIN_NAME)}"
                if stamps.get(TWIN_NAME) == stamps.get(SECOND_PREFIX + TWIN_NAME) else "")),
        cid="g-keys-apart-apply")

    # — --record-only (контур без отпечатков) —
    c = key_contour("bite-untn-g-record-", update_tools, stamp=False)
    code, out = run_ut(c, src, "--record-only")
    stamps = read_stamps(c.db)
    want = {TWIN_NAME: fp12(INSTALLED_SCRIPTS_TWIN.encode("utf-8"))}
    want.update({SECOND_PREFIX + n: fp12(t.encode("utf-8")) for n, t in INSTALLED_SECOND.items()})
    case("(#678 г-9) --record-only снимает отпечатки и со второго каталога (с приставкой), и со скриптов",
        code == 0 and stamps == want,
        f"код {code} · ключи {sorted(stamps)} · ждали {sorted(want)}", cid="g-record-second")
    case("(#678 г-20) итог --record-only называет, сколько отпечатков снято у файлов второго каталога",
        "из них у файлов второго каталога: 3" in out,
        next((l for l in out.splitlines() if "Записано происхождение" in l), "строки «Записано происхождение» нет"),
        cid="g-record-count")

    c = make_contour("bite-untn-g-recnote-", update_tools, paths={SECOND_KEY: "<root>/нет-такого-каталога"},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN}, stamp=False)
    code, out = run_ut(c, src, "--record-only")
    note = next((l for l in out.splitlines() if "такого каталога нет" in l), "")
    case("(#678 г-21) --record-only при ключе без каталога: слова про отсутствие каталога печатаются, инструмент не падает",
        code == 0 and bool(note), f"код {code} · " + (note.strip() or "слов про отсутствие каталога нет"),
        cid="g-record-note")

    # — только .py, ничего не удаляется —
    src7 = make_source("bite-untn-g-src7-", {f"vnext/prototype/{NOTES_NAME}": "# заметка пакета — версия 2\n"})
    second7 = dict(INSTALLED_SECOND)
    second7[NOTES_NAME] = "# заметка пакета — версия 1\n"
    second7["only-mine.py"] = "# файл контура, источнику неизвестен\n"
    second7["local-note.txt"] = "заметка контура\n"
    c = make_contour("bite-untn-g-onlypy-", update_tools, paths={SECOND_KEY: SECOND_DIR_NAME},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN}, second_files=second7)
    before = {n: (c.second / n).read_bytes() for n in ("only-mine.py", "local-note.txt", NOTES_NAME)}
    code, out = run_ut(c, src7, "--apply")
    bad = []
    if code != 0:
        bad.append(f"код {code}")
    for n, b in before.items():
        if not (c.second / n).is_file():
            bad.append(f"{n} УДАЛЁН")
        elif (c.second / n).read_bytes() != b:
            bad.append(f"{n} изменён")
    if not same_bytes(c.second / LINK_NAME, sp / LINK_NAME):
        bad.append(f"контроль: звено {LINK_NAME} (.py) не обновлено — случай ничего не доказывает")
    case("(#678 г-10) ставятся только .py: не-.py файл второго каталога (даже с отпечатком) не тронут, "
         "лишние файлы контура не удалены; обычное звено при этом обновлено",
        not bad, "; ".join(bad) or f"{sorted(before)} целы и не изменены, {LINK_NAME} обновлён",
        cid="g-only-py")

    # — ключ есть, но с ним беда —
    c = make_contour("bite-untn-g-nodir-", update_tools, paths={SECOND_KEY: "<root>/нет-такого-каталога"},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src)
    note = next((l for l in out.splitlines() if "такого каталога нет" in l), "")
    case("(#678 г-11) ключ есть, каталога нет: словами сказано, что файлы vnext/prototype не обслуживаются; "
         "шапка про второй каталог НЕ печатается; инструмент не падает",
        code == 0 and bool(note) and "второй (" not in out,
        f"код {code} · " + (note.strip() or "слов про отсутствие каталога нет"), cid="g-dir-missing")

    c = make_contour("bite-untn-g-garbage-", update_tools, paths="{ это не json",
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src)
    note = next((l for l in out.splitlines() if "не читается" in l), "")
    case("(#678 г-12) файл путей не читается: словами сказано, что второй каталог не обслуживается; без трассировки",
        code == 0 and bool(note) and "Traceback" not in out,
        f"код {code} · " + (note.strip() or "слов про нечитаемый файл нет"), cid="g-file-unreadable")

    c = make_contour("bite-untn-g-isscripts-", update_tools, paths={SECOND_KEY: "<root>/.mezosync/scripts"},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN})
    code, out = run_ut(c, src)
    note = next((l for l in out.splitlines() if "указывает на каталог рабочих скриптов" in l), "")
    twin_count = len(plan_rows(out, TWIN_NAME))
    case("(#678 г-13) ключ указывает на сам каталог скриптов: сказано, что второго каталога нет; "
         "одноимённый файл в плане один раз, шапки про второй каталог нет",
        code == 0 and bool(note) and twin_count == 1 and "второй (" not in out,
        f"код {code} · строк про {TWIN_NAME}: {twin_count} · " + (note.strip() or "слов нет"),
        cid="g-key-is-scripts")

    # — своя правка файла второго каталога —
    edited = "# звено — своя правка роли\n"
    second_own = dict(INSTALLED_SECOND)
    second_own[LINK_NAME] = edited
    c = make_contour("bite-untn-g-own-", update_tools, paths={SECOND_KEY: SECOND_DIR_NAME},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN}, second_files=second_own,
                     extra_stamps={SECOND_PREFIX + LINK_NAME: fp12(INSTALLED_SECOND[LINK_NAME].encode("utf-8"))})
    code1, plan = run_ut(c, src)
    code2, applied = run_ut(c, src, "--apply")
    own_signs = [s for s, _ in plan_rows(plan, LINK_NAME)]
    bad = []
    if own_signs.count("✋") != 1:
        bad.append(f"в плане у {LINK_NAME} знаки {own_signs}")
    if "Для файлов второго каталога сведение (--merge) не работает" not in plan:
        bad.append("в плане нет слов, что --merge для второго каталога не работает")
    if (c.second / LINK_NAME).read_bytes() != edited.encode("utf-8"):
        bad.append("своя правка затёрта --apply")
    if "(второй каталог)" not in applied:
        bad.append("после --apply «не тронуто» не называет второй каталог")
    case("(#678 г-14) своя правка файла второго каталога: в плане «✋», про --merge сказано, --apply её не затирает "
         "и называет каталог", code1 == 0 and code2 == 0 and not bad,
        "; ".join(bad) or f"коды {code1}/{code2} · «✋» стоит, правка цела", cid="g-own-edit")

    # — история пакета для файла второго каталога (путь внутри репозитория — vnext/prototype/<имя>) —
    repo = make_git_source("bite-untn-g-git-")
    c = make_contour("bite-untn-g-hist-", update_tools, paths={SECOND_KEY: SECOND_DIR_NAME},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN}, second_files=dict(INSTALLED_SECOND),
                     stamp=False)
    code1, plan = run_ut(c, repo)
    link_rows = plan_rows(plan, LINK_NAME)
    row_ok = (len(link_rows) == 1 and link_rows[0][0] == "≠" and "версия пакета от" in link_rows[0][1]
              and "своей правки нет" in link_rows[0][1])
    code2, _ = run_ut(c, repo, "--apply")
    taken = same_bytes(c.second / LINK_NAME, repo / "vnext" / "prototype" / LINK_NAME)
    case("(#678 г-17) файл второго каталога без отпечатка, чей текст есть в истории пакета: «≠ … версия пакета от …», "
         "своей правки нет, --apply его берёт (история ищется по пути vnext/prototype/<имя>)",
        code1 == 0 and code2 == 0 and row_ok and taken,
        f"коды {code1}/{code2} · строка: {link_rows} · взят: {taken}", cid="g-history")

    # — «✋» у файла второго каталога при источнике с историей пакета —
    edited = "# звено — своя правка роли (версия 1 с правкой)\n"
    second_own = dict(INSTALLED_SECOND)
    second_own[LINK_NAME] = edited
    c = make_contour("bite-untn-g-ownhist-", update_tools, paths={SECOND_KEY: SECOND_DIR_NAME},
                     scripts_files={TWIN_NAME: INSTALLED_SCRIPTS_TWIN}, second_files=second_own,
                     extra_stamps={SECOND_PREFIX + LINK_NAME: fp12(INSTALLED_SECOND[LINK_NAME].encode("utf-8"))})
    code1, plan = run_ut(c, repo)
    code2, applied = run_ut(c, repo, "--apply")
    own_rows = plan_rows(plan, LINK_NAME)
    base_line = next((l.strip() for l in plan.splitlines() if "пакет менял этот файл после опоры" in l), "")
    bad = []
    if code1 != 0:
        bad.append(f"план упал (код {code1}): " + (plan.strip().splitlines() or ["пусто"])[-1][:200])
    if [s for s, _ in own_rows] != ["✋"]:
        bad.append(f"в плане у {LINK_NAME} знаки {[s for s, _ in own_rows]}")
    if ": да" not in base_line:
        bad.append("под «✋» нет «пакет менял этот файл после опоры: да» (опора по отпечатку в истории не найдена)")
    if (c.second / LINK_NAME).read_bytes() != edited.encode("utf-8"):
        bad.append("своя правка затёрта --apply")
    case("(#678 г-23) «✋» у файла второго каталога при источнике с историей: план печатается целиком, под «✋» — "
         "«пакет менял этот файл после опоры: да» (опора ищется по пути vnext/prototype/<имя>)",
        code1 == 0 and code2 == 0 and not bad,
        "; ".join(bad) or f"коды {code1}/{code2} · {base_line[:120]}", cid="g-own-history")

    # — описание ключа: --help —
    c = make_contour("bite-untn-g-help-", update_tools, paths=None)
    code, out = run_ut(c, None, "--help")
    case("(#678 г-16) update-tools.py --help описывает ключ prototype_install_dir (второй каталог установки)",
        code == 0 and SECOND_KEY in out and "ВТОРОЙ КАТАЛОГ УСТАНОВКИ" in out,
        f"код {code} · слов о ключе: {'есть' if SECOND_KEY in out else 'НЕТ'}", cid="g-help")


def case_doc(mezo_paths_file: Path):
    lacking = []
    for label, f in (("scripts/mezo_paths.py", mezo_paths_file),
                     ("vnext/prototype/mezo_paths.py", HERE / "mezo_paths.py")):
        try:
            doc = ast.get_docstring(ast.parse(f.read_text(encoding="utf-8"))) or ""
        except (OSError, SyntaxError) as exc:
            lacking.append(f"{label}: не прочитан ({exc})")
            continue
        if SECOND_KEY not in doc:
            lacking.append(label)
    case("(#678 г-22) перечень ключей в шапке mezo_paths.py (обе копии) называет prototype_install_dir",
        not lacking, f"без ключа в шапке: {lacking}" if lacking else "обе копии называют ключ",
        cid="g-doc")


# ══ ТАБЛИЦА ПОЛОМОК ═══════════════════════════════════════════════════════════════════════════
# kind: ut — копия update-tools.py · ga — копия guard-all.py · ig — копия ПАКЕТА с подменой в
# init-group.py · mp — копия mezo_paths.py. anchor — строка испытуемого, встречающаяся там ровно
# один раз; broken — чем она подменена. expect — идентификаторы случаев, которые поломка ОБЯЗАНА
# провалить (записаны до прогона, по рассуждению о коде; факт сверяется с ними в конце прогона).
# why — одна фраза: что сломано и почему падают именно эти случаи.
_ALL_KEY_CASES = {"g-header", "g-markers", "g-compare-there", "g-link-not-laid", "g-apply-there",
                  "g-keys-apart-apply", "g-twin-own-key", "g-record-second", "g-out-count",
                  "g-only-py", "g-own-edit", "g-dir-missing", "g-key-is-scripts",
                  "g-apply-count", "g-record-count", "g-record-note", "g-history", "g-own-history"}
BREAKS = {
    # ── прежние (карточки #637/#638) ─────────────────────────────────────────────────────────
    "no-closure": dict(
        kind="ut", anchor=CLOSURE_ANCHOR, broken=CLOSURE_BROKEN,
        expect={"a1-plan", "a1-apply", "a1-guard", "a4-replan", "k-plan", "k-apply", "b-step-out-count"},
        why="звенья замыкания не уходят в «+»: у свежего контура звено не появляется (a1, a4), а у лёгкого "
            "контура без ключа звено уходит в «Вне обновления» (k-plan, k-apply, b-step-out-count)"),
    "no-discriminator": dict(
        kind="ga", anchor=DISCR_ANCHOR, broken=DISCR_BROKEN,
        expect={"b2-notarrived", "g-guard-prefix"},
        why="guard-all.py не читает отпечатки: «не приехало» становится «гард не найден» (b2) — и тот же "
            "ответ получает проба с приставкой (g-guard-prefix)"),
    # ── (б) имя шага схемы — не звено ────────────────────────────────────────────────────────
    "closure-schema-step": dict(
        kind="ut", anchor=UT_CLOSURE_STEP,
        broken="        if name in schema_steps and False:  # ПОЛОМКА closure-schema-step — имя шага схемы снова звено",
        expect={"b-step-closure", "b-step-no-flat", "a3-twin"},
        why="замыкание снова называет имя шага схемы: юнит (b-step-closure), двойник шага ложится плоско "
            "(b-step-no-flat) и множество расходится с init-group.py (a3-twin)"),
    "plan-schema-step": dict(
        kind="ut", anchor=UT_PLAN_STEP,
        broken="                elif f.name in schema_step_names and False:  # ПОЛОМКА plan-schema-step",
        expect={"b-step-out-count", "g-out-count"},
        why="двойник шага схемы снова попадает в «Вне обновления» — ломается счёт там, где он проверяется"),
    "init-schema-step": dict(
        kind="ig", anchor=IG_STEP,
        broken="            if name in schema_step_names and False:\n",
        expect={"b-init-flat"},
        why="init-group.py снова кладёт двойник шага схемы плоско рядом со скриптами"),
    # ── (в) отпечатки шагов схемы ────────────────────────────────────────────────────────────
    "record-flat-only": dict(
        kind="ut", anchor=UT_RECORD_RGLOB, broken='for f in sorted(tools_now.glob("*.py"))',
        expect={"v-record-key", "v-record-eq-apply"},
        why="--record-only снова берёт только верхний уровень scripts/: у шагов схемы нет отпечатка"),
    "init-no-migr-fp": dict(
        kind="ig", anchor=IG_FP,
        broken="        pass  # ПОЛОМКА init-no-migr-fp — отпечатки шагов схемы не пишутся",
        expect={"v-init-key"},
        why="свежая сборка не пишет отпечатки шагам схемы"),
    # ── (г) второй каталог установки ─────────────────────────────────────────────────────────
    "second-key-ignored": dict(
        kind="ut", anchor=UT_KEY_READ,
        broken="    if False:  # ПОЛОМКА second-key-ignored — ключ не читается",
        expect=_ALL_KEY_CASES,
        why="объявленный ключ не читается: падают ВСЕ случаи с ключом — в том числе счёт файлов второго каталога "
            "в итогах --apply и --record-only, слова про каталог при --record-only и оба случая с историей "
            "пакета; случаи без ключа, нечитаемого файла путей, --help и шапки — целы"),
    "missing-dir-silent": dict(
        kind="ut", anchor=UT_MISSING_DIR,
        broken="        if True:  # ПОЛОМКА missing-dir-silent — отсутствие каталога не замечено",
        expect={"g-dir-missing", "g-record-note"},
        why="ключ с несуществующим каталогом принимается молча: нет слов про отсутствие ни в плане (g-dir-missing), "
            "ни при --record-only (g-record-note), шапка есть"),
    "unreadable-silent": dict(
        kind="ut", anchor=UT_UNREADABLE,
        broken="    if False:  # ПОЛОМКА unreadable-silent",
        expect={"g-file-unreadable"},
        why="нечитаемый файл путей читается как «ключа нет» — сказать об этом нечем"),
    "default-dir-guess": dict(
        kind="ut", anchor=UT_NO_KEY_TAIL,
        broken=('    guess = pathlib.Path(db).resolve().parent.parent / "vnext-tools"  '
                '# ПОЛОМКА default-dir-guess — без ключа угадывает соседний каталог\n'
                '    return (guess, None) if guess.is_dir() else (None, None)\n\n\n'
                '# 🪤 КАРТОЧКА #637 (находка COORD'),
        expect={"k-plan", "k-apply", "k-record"},
        why="без ключа инструмент угадывает соседний vnext-tools: «без ключа» перестаёт быть прежним разбором"),
    "second-is-scripts": dict(
        kind="ut", anchor=UT_IS_SCRIPTS,
        broken="    if False:  # ПОЛОМКА second-is-scripts",
        expect={"g-key-is-scripts"},
        why="ключ, указывающий на каталог скриптов, принимается за второй каталог: файл в плане дважды"),
    "second-not-indexed": dict(
        kind="ut", anchor=UT_INDEX,
        broken="                if False:  # ПОЛОМКА second-not-indexed\n"
               "                    src_index[second_rel(f.name)] = f\n",
        expect={"g-markers", "g-compare-there", "g-apply-there", "g-keys-apart-apply", "g-twin-own-key",
                "g-own-edit", "g-only-py", "g-apply-count", "g-history", "g-own-history"},
        why="файлы второго каталога не попадают в разбор: ни «≠», ни обновления там, ни счёта в итоге --apply, "
            "ни строк про историю пакета (g-history, g-own-history); случаи, которые про «не лежит в скриптах» "
            "и «не считается», остаются целы"),
    "link-laid-flat": dict(
        kind="ut", anchor=UT_LINK_LAID,
        broken="                    if True:  # ПОЛОМКА link-laid-flat",
        expect={"g-link-not-laid", "g-history", "g-own-history"},
        why="звено, уже лежащее во втором каталоге, всё равно кладётся и в скрипты («+ появится»): плюс к "
            "g-link-not-laid у звена появляется вторая строка плана, а оба случая с историей пакета ждут ровно "
            "одну («≠» в g-history, «✋» в g-own-history)"),
    "second-counted-out": dict(
        kind="ut", anchor=UT_OUT_COUNT,
        broken="                elif True:  # ПОЛОМКА second-counted-out",
        expect={"g-out-count"},
        why="файл, лежащий во втором каталоге, считается ещё и «Вне обновления»"),
    "second-key-collides": dict(
        kind="ut", anchor=UT_KEY_FORM,
        broken="    return pathlib.Path(rel).name  # ПОЛОМКА second-key-collides — ключ без приставки",
        expect={"g-compare-there", "g-twin-own-key", "g-apply-there", "g-keys-apart-apply",
                "g-record-second", "g-own-edit", "g-only-py", "v-record-eq-apply",
                "g-apply-count", "g-own-history"},
        why="ключ отпечатка без приставки (и без «migrations/»): одноимённые файлы двух каталогов "
            "сливаются, а отпечатки второго каталога не находятся — второй каталог судится вслепую "
            "(у «✋» в g-own-history отпечаток не находится, строка «❓»; счёт файлов второго каталога в итоге "
            "--apply — ноль, g-apply-count); шаги схемы под --apply получают другой ключ, чем под "
            "--record-only (v-record-eq-apply)"),
    "where-silent": dict(
        kind="ut", anchor=UT_WHERE, broken='            return ""  # ПОЛОМКА where-silent — каталог файла не назван',
        expect={"g-markers"},
        why="план не называет каталог каждого файла (шапка остаётся)"),
    "apply-to-scripts": dict(
        kind="ut", anchor=UT_APPLY_WRITE,
        broken="            shutil.copy2(src_index[rel], (tools / rel.name) if is_second_rel(rel) else dest_of(rel))"
               "  # ПОЛОМКА apply-to-scripts",
        expect={"g-apply-there", "g-link-not-laid", "g-keys-apart-apply", "g-only-py", "g-history"},
        why="--apply пишет файлы второго каталога в скрипты, а не туда, где они лежат (в том числе файл, "
            "который g-history ждёт взятым во втором каталоге)"),
    "second-any-file": dict(
        kind="ut", anchor=UT_GLOB_ALL, broken='            for f in sorted(linked_dir.glob("*")):  # ПОЛОМКА second-any-file',
        expect={"g-only-py"},
        why="в разбор попадают файлы любого вида, не только .py: не-.py файл второго каталога перезаписан"),
    "help-silent": dict(
        kind="ut", anchor=UT_HELP, broken="epilog=None,",
        expect={"g-help"},
        why="--help не описывает ключ"),
    "own-edit-note": dict(
        kind="ut", anchor=UT_MERGE_NOTE, broken="            if False:  # ПОЛОМКА own-edit-note",
        expect={"g-own-edit"},
        why="в плане нет слов, что --merge для файлов второго каталога не работает"),
    "second-history-path": dict(
        kind="ut", anchor=UT_HISTORY_PATH,
        broken='                    git_rel_of[second_rel(f.name)] = "scripts/" + f.name  # ПОЛОМКА second-history-path',
        expect={"g-history", "g-own-history"},
        why="история пакета ищется по пути scripts/<имя>, а файл второго каталога — vnext/prototype/<имя>: "
            "версия не находится — файл остаётся «❓» (g-history), опора у «✋» не находится (g-own-history)"),
    "helper-shadowed": dict(
        kind="ut", anchor="show_name(", broken="shown(", count=7,
        expect={"g-own-history"},
        why="помощник плана снова зовётся shown — как обычная переменная ниже в main(): после первой "
            "же строки «пакет менял этот файл после опоры» её затирает строка коммитов, и печать плана падает "
            "на «TypeError: 'str' object is not callable» (так упали два случая bite-update-tools-merge.py)"),
    "shown-prefix-visible": dict(
        kind="ut", anchor=UT_SHOWN, broken="            return str(rel)  # ПОЛОМКА shown-prefix-visible",
        expect={"g-prefix-hidden"},
        why="в плане у файла второго каталога виден служебный ярлык «prototype-dir::» вместо имени"),
    "own-apply-unlabelled": dict(
        kind="ut", anchor=UT_OWN_APPLY, broken='("")',
        expect={"g-own-edit"},
        why="--apply не называет второй каталог у «не тронуто твоих правок»"),
    "apply-count-zero": dict(
        kind="ut", anchor=UT_APPLY_COUNT, broken="{0}",
        expect={"g-apply-count"},
        why="итог --apply всегда говорит «во второй каталог: 0»"),
    "record-count-zero": dict(
        kind="ut", anchor=UT_RECORD_COUNT, broken="                        second_taken += 0",
        expect={"g-record-count"},
        why="итог --record-only не считает файлы второго каталога"),
    "record-note-silent": dict(
        kind="ut", anchor=UT_RECORD_NOTE,
        broken='            if False:  # ПОЛОМКА record-note-silent\n                print(f"⚠️ {second_note}")\n'
               '            print("   Файлы НЕ тронуты',
        expect={"g-record-note"},
        why="--record-only молчит о ключе, у которого нет каталога"),
    "header-silent": dict(
        kind="ut", anchor=UT_HEADER, broken="            pass  # ПОЛОМКА header-silent",
        expect={"g-header"},
        why="план не печатает строку про второй каталог (метки у файлов остаются)"),
    "plan-note-silent": dict(
        kind="ut", anchor=UT_PLAN_NOTE,
        broken='        if False:  # ПОЛОМКА plan-note-silent\n            print(f"⚠️ {second_note}")\n        print()\n',
        expect={"g-dir-missing", "g-file-unreadable", "g-key-is-scripts"},
        why="план не печатает слова про беду с ключом (нет каталога · файл не читается · ключ на скрипты)"),
    "mezo-paths-doc": dict(
        kind="mp", anchor=MP_DOC, broken="    second_dir_key_renamed   НЕОБЯЗАТЕЛЬНЫЙ",
        expect={"g-doc"},
        why="перечень ключей в шапке mezo_paths.py не называет prototype_install_dir"),
    "guard-prefix-confused": dict(
        kind="ga", anchor=DISCR_ANCHOR, broken=GA_PREFIX_STRIP,
        expect={"g-guard-prefix"},
        why="guard-all.py срезает приставку «prototype-dir::/»: отпечаток второго каталога читается как отпечаток "
            "звена первого — «ПРОПАЛО» вместо «не приехало»"),
}


def patched_pack(anchor: str, replacement: str, prefix: str) -> Path:
    """Копия ПАКЕТА (без .git) с одной подменённой строкой в scripts/init-group.py — свежую сборку
    поломки строит настоящий init-group.py, только испорченный; сам пакет не тронут."""
    src = PACK / "scripts" / "init-group.py"
    text = src.read_text(encoding="utf-8")
    n = text.count(anchor)
    if n != 1:
        sys.exit(f"⛔ ЯКОРЬ ПОЛОМКИ ВСТРЕЧЕН {n} РАЗ (ждали 1) в init-group.py — испытуемое изменилось")
    root = mezo_stand.new(prefix)
    shutil.copytree(PACK, root / "pack", ignore=shutil.ignore_patterns(".git", "__pycache__"))
    (root / "pack" / "scripts" / "init-group.py").write_text(text.replace(anchor, replacement), encoding="utf-8")
    return root / "pack"


def main() -> int:
    global BREAK
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_mode", default=None, choices=sorted(BREAKS),
                    help="нарочная поломка (одна на место правки); ожидаемые падения — в таблице BREAKS")
    args = ap.parse_args()
    BREAK = args.break_mode

    # испытуемые инструменты ищутся в КОНТУРЕ (mezo_paths.live_scripts); из голого клона
    # пакета их рядом нет — это не провал случаев, а «не запустилась», и сказано словами
    missing = [p for p in (UPDATE_TOOLS, GUARD_ALL) if not Path(p).exists()]
    if missing:
        print("⛔ не запустилась: испытуемых инструментов нет — "
              + " · ".join(str(p) for p in missing)
              + ". Запускай в контуре: приёмка рядом с .mezosync/scripts контура "
                "либо MEZO_CONTAINER, указывающий на контур")
        return 2

    update_tools, guard_all, init_pack, paths_doc = UPDATE_TOOLS, GUARD_ALL, PACK, MEZO_SCRIPTS / "mezo_paths.py"
    brk = BREAKS.get(BREAK) if BREAK else None
    if brk:
        kind = brk["kind"]
        if kind == "ut":
            update_tools = broken_copy(UPDATE_TOOLS, brk["anchor"], brk["broken"], "bite-untn-broken-ut-",
                                       brk.get("count", 1))
        elif kind == "ga":
            guard_all = broken_copy(GUARD_ALL, brk["anchor"], brk["broken"], "bite-untn-broken-ga-")
        elif kind == "ig":
            init_pack = patched_pack(brk["anchor"], brk["broken"], "bite-untn-broken-ig-")
        elif kind == "mp":
            paths_doc = broken_copy(MEZO_SCRIPTS / "mezo_paths.py", brk["anchor"], brk["broken"],
                                    "bite-untn-broken-mp-")

    case_a1_and_a3(update_tools, BREAK)
    case_a2(update_tools)
    case_a4(update_tools, BREAK)
    case_b(guard_all, BREAK)
    case_no_key(update_tools)
    case_schema_step(update_tools)
    case_init_group(init_pack)
    case_record_migrations(update_tools)
    case_second_dir(update_tools)
    case_doc(paths_doc)

    # опечатка в таблице поломок не должна пройти молча: названный там случай обязан существовать
    named = set().union(*(set(b["expect"]) for b in BREAKS.values()))
    unknown_ids = sorted(named - set(SEEN_IDS))

    print()
    print("=" * 78)
    if brk:
        print(f"ПОЛОМКА {BREAK} — {brk['why']}")
    print(f"случаев {CASES}, различающих {DIFFER}")
    if unknown_ids:
        print(f"⛔ В ТАБЛИЦЕ ПОЛОМОК названы случаи, которых приёмка не прогнала: {unknown_ids}")
        return 2
    if brk:
        expected, actual = set(brk["expect"]), set(FAILED_IDS)
        if actual == expected:
            print(f"🧪 ожидание поломки «{BREAK}» ПОДТВЕРДИЛОСЬ: провалены ровно {' '.join(sorted(actual))}")
            mezo_stand.expected_break()
        else:
            print(f"⚠️ ожидание поломки «{BREAK}» НЕ ПОДТВЕРДИЛОСЬ: ждали {' '.join(sorted(expected))}; "
                  f"провалено {' '.join(sorted(actual)) or 'ничего'}"
                  f" · лишние: {' '.join(sorted(actual - expected)) or 'нет'}"
                  f" · не провалены: {' '.join(sorted(expected - actual)) or 'нет'}")
        if FAILED:
            print(f"🔴 ПРОВАЛЕНО {len(FAILED)}: " + " · ".join(FAILED))
        return 1
    if FAILED:
        print(f"🔴 ПРОВАЛЕНО {len(FAILED)}: " + " · ".join(FAILED))
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
