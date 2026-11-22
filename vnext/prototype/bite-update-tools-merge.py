#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-update-tools-merge.py — приёмка карточки #609: файл, правленый У КОНТУРА, получает
исправления пакета через сведение ТРЁХ текстов (опора · ваш · пакет), а не остаётся
«✋ ПРАВЛЕН У ТЕБЯ — НЕ трогаем» навсегда.

ПОВОД. update-tools.py уже отличал свою правку от версии пакета (отпечаток установки,
meta.template_files_sha), но список «✋» только НАЗЫВАЛ беду («перенеси свою правку сам или
удали файл») — решить её было нечем. Правка пакета, случившаяся ПОСЛЕ отпечатка установки,
до контура не доходила НИКОГДА, и сам контур не знал, есть ли вообще что сводить.

ЗАМЫСЕЛ (тот же, что у правил в карточке #608, rules-from-pack.py): опора файла — уже
существующий отпечаток установки; --merge находит ЕЁ ТЕКСТ в истории пакета ПО ЭТОМУ
ОТПЕЧАТКУ (find_version_by_fingerprint — новая функция рядом с find_version_span) и сводит
три текста инструментом `git merge-file`; черновик — В СТОРОНУ, живой файл не трогается;
--accept-merge кладёт его, только если отметок пересечения не осталось, и переносит опору
на версию пакета, с которой сводили.

СЛУЧАИ (нумерация — по критерию карточки #609):
  ① у «✋» печатается «пакет менял этот файл после опоры: да — коммиты …», когда пакет
    менял путь ПОСЛЕ опоры, и «… не менял», когда не менял (встречный)
  ② --merge на НЕПЕРЕСЕКАЮЩИХСЯ правках даёт черновик с ОБЕИМИ правками; живой файл не
    тронут до --accept-merge
  ③ --merge на ПЕРЕСЕКАЮЩИХСЯ правках даёт черновик с отметками пересечения; --accept-merge
    отказывает, пока они не убраны; после ручной правки черновика — принимает
  ④ после --accept-merge опора файла = версия пакета, С КОТОРОЙ сводили; следующий обычный
    прогон снова видит «✋ ПРАВЛЕН У ТЕБЯ», но с «пакет после опоры не менял»; прежняя опора
    (её отпечаток) в выводе не встречается
  ⑤ (в памяти, нарочные поломки): опора = версия пакета СЕЙЧАС вместо версии установки →
    ② проваливается (правка пакета исчезает из черновика МОЛЧА, без единого пересечения);
    --accept-merge без обновления опоры → ④ проваливается (отпечаток в meta не меняется)
  доп. «опору найти нечем» — источник без истории вовсе, и: отпечаток установки есть, но
    версии с таким отпечатком в истории пакета не нашлось (оба варианта говорят прямо, а
    не выдумывают дату и не падают трассировкой)
  доп. контроль — файл, НЕ правленый у контура (обычное «≠ отличается»), обновляется
    --apply как раньше: новый код не задевает старый путь

ИСПЫТУЕТСЯ через mezo_target (MEZO_SCRIPTS_ROOT — какую копию update-tools.py судим;
MEZO_FORBID_LIVE=1 — отказ, если она вдруг окажется живой).

⛔ ВТОРОЙ ВОЗВРАТ (карточка #609, безопасность): ОБРАЗЕЦ (mezo_paths.template_root) — ТОЛЬКО
ИСТОЧНИК, приёмка в него НЕ ПИШЕТ НИКОГДА. Прежняя редакция коммитила синтетические файлы
для случаев ①–⑤ прямо в template_root — без MEZO_TEMPLATE этот путь резолвится через
local.paths и указывает на НАСТОЯЩИЙ клон пакета (тот, что уходит на публичный GitHub при
ближайшей отправке): запуск «как написано в шапке» унёс бы туда 9+ посторонних коммитов.
Починка: приёмка САМА клонирует образец (`git clone --no-hardlinks <template_root>
<стенд>/pack`) в СВОЙ временный каталог (mezo_stand.new) и коммитит синтетические файлы для
случаев ①–⑤ уже В ЭТОТ КЛОН — PACKAGE ниже указывает на клон, а не на образец. add_pack_commit
отказывает громко (с путём), если цель коммита вдруг окажется не внутри временного каталога
этой приёмки, — защита на случай, если PACKAGE когда-нибудь снова укажет мимо. Это
СОЗНАТЕЛЬНОЕ отличие от bite-update-tools-rev.py (та приёмка пакет только читает).

Контроли внизу файла:
  · «клон приёмки не тронут ВЫЗОВАМИ update-tools.py» — HEAD/status/diff СВОЕГО клона
    сравниваются ДО первого вызова update-tools.py (после того, как приёмка сама закончила
    готовить историю) и ПОСЛЕ всех вызовов. Суд разницей состояния здесь законен: клон свой,
    лежит в своём временном каталоге, соседей у него нет по построению;
  · «образец не тронут» и «meta живого контура не тронута» — суд ПО СВОИМ СЛЕДАМ поимённо
    (карточка #804), а не по разнице состояния. Образец в живом контуре — общий клон пакета:
    HEAD и status в нём двигает любой честный commit соседа, а meta пишет установка
    инструментов. Свои следы прогона: в образце — commit под адресом автора с номером прогона
    и файл scripts/merge-*.py с меткой прогона; в meta — путь своего стенда, версии пакета из
    своего клона и отпечатки своих файлов. Состояние «до и после» печатается справкой.
    У каждого из двух контролей четыре встречных на СВОЕЙ подставке: -а чужая запись случай
    НЕ роняет · -б свой след роняет и назван поимённо · -в предмет недоступен — третий исход
    «НЕ ПРОВЕРЕНО», код выхода 2 · -г свои следы на стенде находятся (вопрос не слеп).
Нарочная поломка «суд по разнице состояния» — ключом, прежний суд возвращается ПОВЕРХ нового:
    --break state-template   ПРОГНОЗ: проваливается ровно «образец-а», остальные проходят
    --break state-meta       ПРОГНОЗ: проваливается ровно «meta-а», остальные проходят

⚖️ ОБРАЗЕЦ БЕЗ ИСТОРИИ (карточка #667). Контур, собранный из ВЫГРУЗКИ пакета (архив без
.git), держит образец обычным каталогом — клонировать нечего, и прежде приёмка падала
«⛔ НЕ ЗАПУСТИЛАСЬ: … does not appear to be a git repository» кодом 1 (общий прогон печатал
это «СЛОМАНО»). Но ни один случай не стои́т на истории САМОГО образца: всю историю, на
которой мерятся ①–⑦, приёмка коммитит сама. Поэтому у выгрузки свой клон собирается иначе —
`git init` во временном каталоге и файлы образца ОДНИМ коммитом, — а случаи те же. Контроль
«образец не тронут» у выгрузки ищет свои следы файлами с меткой прогона (коммитов у каталога
без git нет); справкой печатается отпечаток всех её файлов (HEAD и status у каталога без git
пусты всегда — сравнение их было бы пустым).

⚖️ КОНТУРЫ ЗДЕСЬ — ЛЁГКИЕ, НЕ ЧЕРЕЗ init-group.py: каждому случаю нужны только meta
(table) + один файл в scripts/, а не работающая группа с ролями/лентой/бэклогом. Полный
init-group.py-контур (как у bite-update-tools-rev.py) стоил бы кратно дороже по времени
ради возможностей, которые эти случаи не используют. mezo_stand.copy_tool всё равно берёт
ИМЕННО испытуемую копию (TARGET) и её файлы-соседи (mezo_paths, mezo_stand) — тот же приём,
каким испытуемое подставляют полные приёмки.

    python <КОНТУР>/vnext-tools/bite-update-tools-merge.py
"""
from __future__ import annotations

import hashlib
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

TARGET = mezo_target.script("update-tools.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

import mezo_stand  # noqa: E402 — из папки приёмки, не испытуемого контура (см. bite-update-tools-rev.py)
if not hasattr(mezo_stand, "stand_env"):
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет stand_env — помощник в папке "
             "приёмки старше неё; возьми оба файла из одной версии пакета")

# Нарочная поломка «суд по разнице состояния» (карточка #804): ключ возвращает одному из двух
# контролей прежний суд ПОВЕРХ суда по своим следам. Иных аргументов у приёмки нет.
BREAKS = {"state-template": "образец-а", "state-meta": "meta-а"}
BREAK = None
if sys.argv[1:]:
    if len(sys.argv) == 3 and sys.argv[1] == "--break" and sys.argv[2] in BREAKS:
        BREAK = sys.argv[2]
        print(f"⚖️ НАРОЧНАЯ ПОЛОМКА «{BREAK}»: суд по разнице состояния возвращён. ПРОГНОЗ: "
              f"проваливается ровно встречный случай «{BREAKS[BREAK]}», остальные проходят")
    else:
        print("⛔ НЕ ЗАПУСТИЛАСЬ: аргументы не разобраны. Допустимо: без аргументов либо "
              "--break state-template | --break state-meta")
        sys.exit(2)

# Свои следы этого прогона (карточка #804). Номер прогона стоит в адресе автора каждого коммита
# приёмки и в первой строке каждого её файла; по нему она узнаёт СВОЁ в образце и в meta и не
# путает его ни с честной записью соседа, ни с другим прогоном этой же приёмки.
RUN_ID = os.urandom(4).hex()
OWN_NAME, OWN_EMAIL = "bite609", f"bite609-{RUN_ID}@local"
RUN_NONCE = f"# bite609 прогон {RUN_ID}\n".encode("utf-8")
OWN_COMMITS: list[str] = []          # версии (12 знаков), созданные приёмкой в своём клоне
OWN_FINGERPRINTS: set[str] = set()   # отпечатки текстов, которые она коммитит
CIRCUIT_DBS: list[Path] = []         # базы лёгких контуров стенда


def template_is_repository(root) -> bool:
    """Образец — КОРЕНЬ своего git-репозитория и в нём есть хоть один коммит (карточка #667).
    Выгрузка без .git, каталог внутри чужого репозитория и репозиторий без коммитов — нет:
    клонировать из них нечего."""
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(root).resolve():
        return False
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"],
                          capture_output=True)
    return head.returncode == 0


def files_digest(root) -> str:
    """Отпечаток всех файлов каталога: пути и содержимое (карточка #667, образец-выгрузка)."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:12]


def template_state(root) -> tuple[str, str]:
    """HEAD + `git status --porcelain` образца (template_root) — снимок для контроля
    «образец не тронут» (ВТОРОЙ ВОЗВРАТ, карточка #609). Читает только, ничего не пишет.
    У образца-выгрузки без git (карточка #667) HEAD и status пусты ВСЕГДА — сравнение их
    было бы пустым; вместо них снимается отпечаток всех файлов каталога."""
    if not template_is_repository(root):
        return ("выгрузка без git", f"отпечаток файлов {files_digest(root)}")

    def g(*a) -> bytes:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True).stdout
    return (g("rev-parse", "HEAD").decode().strip(),
           g("status", "--porcelain").decode("utf-8", "replace").strip())


def template_traces(root) -> tuple:
    """Свои следы ЭТОГО прогона в образце (или в каталоге, где их ищут): (словарь, "") либо
    (None, причина).

    След — то, что могла оставить только эта приёмка (карточка #804):
      · commit под адресом автора с номером прогона — по всем веткам и по журналу движений;
      · файл scripts/merge-*.py с меткой прогона в тексте (у образца-выгрузки без git — только это).
    Чужой commit, чужая правка и даже чужой файл с тем же именем сюда не попадают: номера прогона
    в них нет. Каталога нет или git не ответил — None и причина; «следов нет» при этом НЕ
    утверждается. Читает только, ничего не пишет.
    """
    root = Path(root)
    if not root.is_dir():
        return None, f"каталога «{root.name}» нет"
    found: dict[str, int] = {}
    try:
        for p in sorted((root / "scripts").glob("merge-*.py")):
            if p.is_file() and RUN_NONCE.strip() in p.read_bytes():
                found[f"файл scripts/{p.name} с меткой прогона"] = 1
    except OSError as e:
        return None, f"{type(e).__name__}: {e}"[:120]
    if template_is_repository(root):
        r = subprocess.run(["git", "-C", str(root), "log", "--all", "--reflog", "--fixed-strings",
                            f"--author={OWN_EMAIL}", "--format=%H %s"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return None, "git log не ответил: " + (r.stderr or "").strip()[:100]
        for line in r.stdout.splitlines():
            if line.strip():
                found[f"commit {line[:12]} «{line[41:].strip()}»"] = 1
    return found, ""


def template_verdict(root, traces_before, state_before) -> tuple:
    """Суд «образец этим прогоном не тронут» — по своим следам, три исхода
    (mezo_stand.traces_verdict). Под нарочной поломкой «state-template» поверх него возвращается
    прежний суд: состояние каталога изменилось — значит «тронут», чьей бы рукой оно ни менялось."""
    outcome, names, why = mezo_stand.traces_verdict(traces_before, template_traces(root))
    if BREAK == "state-template" and outcome == "clean" and template_state(root) != state_before:
        return "traces", ["состояние каталога изменилось — прежний суд, нарочная поломка"], ""
    return outcome, names, why


def trace_words(outcome, names, why, where, silent) -> str:
    """Слова трёх исходов суда по своим следам — у каждого свои, чтобы третий не читался как первый."""
    if outcome == "clean":
        return f"своих следов в {where} нет"
    if outcome == "traces":
        return "СЛЕДЫ ЕСТЬ: " + ", ".join(names)
    return f"НЕ ПРОВЕРЕНО: {silent} на вопрос о своих следах ({why})"


TEMPLATE_WORDS = ("образце", "образец не ответил")
META_WORDS = ("meta", "база не ответила")


# ⛔ ВТОРОЙ ВОЗВРАТ (карточка #609): снимок берётся ДО ЛЮБОГО действия этой приёмки — раньше
# собственного клонирования тоже. Сравнение — в самом конце файла (контроль «образец не тронут»).
TEMPLATE_ROOT = mezo_paths.template_root(__file__)
TEMPLATE_IS_REPOSITORY = template_is_repository(TEMPLATE_ROOT)
TEMPLATE_BEFORE = template_state(TEMPLATE_ROOT)             # справка, не суд (карточка #804)
TEMPLATE_TRACES_BEFORE = template_traces(TEMPLATE_ROOT)      # суд: свои следы до первого действия

STAND = mezo_stand.new("bite-609-merge-")

# ⛔ ВТОРОЙ ВОЗВРАТ (карточка #609, безопасность): PACKAGE — СВОЙ клон TEMPLATE_ROOT внутри
# СВОЕГО временного каталога, а не сам образец. Прежде PACKAGE = TEMPLATE_ROOT напрямую, и
# без MEZO_TEMPLATE это указывало на НАСТОЯЩИЙ клон пакета (через local.paths) — приёмка
# коммитила бы синтетические файлы для случаев ①–⑤ туда же. Клонирование — ЧТЕНИЕ образца
# (`git clone` не пишет в источник), коммиты ниже идут уже в клон.
PACKAGE = STAND / "pack"
if TEMPLATE_IS_REPOSITORY:
    _clone = subprocess.run(["git", "clone", "--no-hardlinks", str(TEMPLATE_ROOT), str(PACKAGE)],
                            capture_output=True, text=True)
    if _clone.returncode != 0:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: свой клон образца ({TEMPLATE_ROOT}) в стенд ({PACKAGE}) "
                 f"отказал: {_clone.stderr.strip()[:300]}")
else:
    # ⚖️ Карточка #667: образец — выгрузка без истории (см. шапку). Свой «клон» — файлы
    # образца одним коммитом в НОВОМ репозитории внутри своего временного каталога; образец
    # при этом только читается (копирование), как и при `git clone`.
    shutil.copytree(TEMPLATE_ROOT, PACKAGE, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    for _step in (["init", "-q"], ["add", "-A"],
                  ["-c", f"user.name={OWN_NAME}", "-c", f"user.email={OWN_EMAIL}",
                   "commit", "-q", "-m", "bite609: файлы образца-выгрузки одним коммитом"]):
        _r = subprocess.run(["git", "-C", str(PACKAGE), *_step], capture_output=True, text=True)
        if _r.returncode != 0:
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: свой репозиторий из образца-выгрузки ({TEMPLATE_ROOT}) "
                     f"в стенде ({PACKAGE}) не собрался на «git {' '.join(_step[:2])}»: "
                     f"{_r.stderr.strip()[:300]}")
    OWN_COMMITS.append(subprocess.run(["git", "-C", str(PACKAGE), "rev-parse", "HEAD"],
                                      capture_output=True, text=True).stdout.strip()[:12])
    print(f"⚖️ образец — выгрузка без истории git ({TEMPLATE_ROOT}): свой репозиторий собран "
          "из его файлов одним коммитом; историю, на которой стоят случаи, приёмка коммитит "
          "сама, как и в клоне")

RFP_TOOL_PATH = PACKAGE / "scripts" / "rules-from-pack.py"   # копируем, только если есть — не обязателен этим случаям

OK = FAIL = 0
FAILED: list[str] = []    # проваленные случаи поимённо — сверка прогноза нарочной поломки


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)
    if not cond:
        FAILED.append(name)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def git(*args, cwd=PACKAGE, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: git {' '.join(args)} в {cwd} отказал: {r.stderr.strip()[:300]}")
    return r


def pack_state() -> tuple[str, str, str]:
    def g(*a) -> bytes:
        return subprocess.run(["git", "-C", str(PACKAGE), *a], capture_output=True).stdout
    return (g("rev-parse", "HEAD").decode().strip(),
            g("status", "--short").decode("utf-8", "replace").strip(),
            hashlib.sha256(g("diff", "HEAD", "--binary")).hexdigest()[:12])


LIVE_DB = mezo_paths.live_db()


def read_meta(db):
    """Таблица meta базы словарём — справка для контроля, не суд. База не ответила — None."""
    try:
        c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
        try:
            return dict(c.execute("SELECT key, value FROM meta"))
        finally:
            c.close()
    except (sqlite3.Error, OSError):
        return None


def own_meta_marks() -> tuple:
    """Что несёт СВОЁ в meta, пиши испытуемый не в ту базу: так выглядят его записи об источнике."""
    return (("путь своего стенда", [STAND.name]),
            ("своя версия пакета", list(OWN_COMMITS)),
            ("отпечаток своего файла", sorted(OWN_FINGERPRINTS)))


def meta_traces(db) -> tuple:
    """Свои следы ЭТОГО прогона в таблице meta базы: (словарь, "") либо (None, причина).

    След — значение meta, внутри которого стоит своё (карточка #804): путь своего стенда (им
    записан источник), версия пакета из своего клона, отпечаток своего файла. Ищется ВХОЖДЕНИЕМ
    во все значения: отпечатки лежат внутри одного большого значения, точным совпадением их не
    взять. Запись соседа (установка инструментов меняет версию и отпечатки) сюда не попадает —
    своего в ней нет. База не открылась или таблицы meta в ней нет — None и причина.
    Открывает базу СТРОГО НА ЧТЕНИЕ.
    """
    try:
        c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
        try:
            rows = c.execute("SELECT key, value FROM meta").fetchall()
        finally:
            c.close()
    except (sqlite3.Error, OSError) as e:
        return None, f"{type(e).__name__}: {e}"[:120]
    found: dict[str, int] = {}
    for key, value in rows:
        text = str(value or "")
        for kind, marks in own_meta_marks():
            for mark in marks:
                if mark and mark in text:
                    found[f"meta.{key} ← {kind} {mark}"] = 1
    return found, ""


def meta_verdict(db, traces_before, meta_before) -> tuple:
    """Суд «meta этим прогоном не тронута» — по своим следам, три исхода. Под нарочной поломкой
    «state-meta» поверх него возвращается прежний суд: изменился хоть один ключ — значит «тронута»."""
    outcome, names, why = mezo_stand.traces_verdict(traces_before, meta_traces(db))
    if BREAK == "state-meta" and outcome == "clean" and read_meta(db) != meta_before:
        return "traces", ["ключи meta изменились — прежний суд, нарочная поломка"], ""
    return outcome, names, why


LIVE_META_BEFORE = read_meta(LIVE_DB)      # справка, не суд (карточка #804)


def add_pack_commit(rel: str, content: bytes, message: str) -> str:
    """Коммит СВОЕЙ рукой в СВОЙ клон пакета (PACKAGE = <стенд>/pack, НЕ образец) —
    готовит историю, на которой стоят случаи ①-⑤. Возвращает короткий хеш коммита.

    ⛔ ВТОРОЙ ВОЗВРАТ (карточка #609, безопасность): защита ПЕРЕД каждым коммитом — цель
    обязана лежать ВНУТРИ временного каталога этой приёмки (STAND). Если PACKAGE когда-нибудь
    снова укажет мимо (правка выше отменена, поломка, чужая правка) — отказ ГРОМКИЙ, с
    названным путём, а не тихий коммит в чужой репозиторий."""
    try:
        PACKAGE.resolve().relative_to(STAND.resolve())
    except ValueError:
        sys.exit(f"⛔ ЗАЩИТА add_pack_commit: цель коммита ({PACKAGE}) НЕ лежит внутри "
                 f"временного каталога этой приёмки ({STAND}) — отказываюсь коммитить, "
                 f"здесь мог быть образец или чужой репозиторий")
    p = PACKAGE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    git("add", rel)
    git("-c", f"user.name={OWN_NAME}", "-c", f"user.email={OWN_EMAIL}",
       "commit", "-q", "-m", message)
    made = git("rev-parse", "HEAD").stdout.strip()[:12]
    OWN_COMMITS.append(made)                 # свои следы прогона (карточка #804)
    OWN_FINGERPRINTS.add(digest(content))
    return made


def make_light_circuit(name: str, seed: dict[str, bytes], fingerprints: dict[str, str],
                       extra_meta: dict[str, str] | None = None) -> tuple[Path, Path, Path]:
    """Лёгкий контур (см. шапку файла): каталог со scripts/ (испытуемый + соседи + seed) и
    mezosync.db с одной таблицей meta. Возвращает (корень .mezosync, scripts/, mezosync.db).
    """
    root = STAND / name / ".mezosync"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    mezo_stand.copy_tool(TARGET, scripts)          # испытуемая копия + mezo_paths/mezo_stand
    if RFP_TOOL_PATH.exists() and not (scripts / "rules-from-pack.py").exists():
        shutil.copy2(RFP_TOOL_PATH, scripts / "rules-from-pack.py")
    for rel, content in seed.items():
        (scripts / rel).parent.mkdir(parents=True, exist_ok=True)
        (scripts / rel).write_bytes(content)
    db = root / "mezosync.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    values = {"template_source": str(PACKAGE),
             "template_files_sha": json.dumps(fingerprints, ensure_ascii=False)}
    values.update(extra_meta or {})
    for k, v in values.items():
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    CIRCUIT_DBS.append(db)
    return root, scripts, db


def run(scripts: Path, *extra, timeout=120) -> tuple[int, str]:
    # container = РОДИТЕЛЬ .mezosync (scripts = .../<контур>/.mezosync/scripts), а НЕ сам
    # .mezosync — иначе mezo_paths.live_scripts() удвоит хвост (".../.mezosync/.mezosync/scripts")
    # и найдёт пустое место; тот же приём, что у bite-update-tools-rev.py (там parents[2] от файла).
    env = mezo_stand.stand_env(scripts.parent.parent, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(scripts / "update-tools.py"), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def meta_of(db: Path) -> dict:
    c = sqlite3.connect(str(db))
    m = dict(c.execute("SELECT key, value FROM meta"))
    c.close()
    return m


# ═══ ПОДГОТОВКА ИСТОРИИ ПАКЕТА (СВОЙ клон, PACKAGE = <стенд>/pack — пишем в него намеренно,
#     образец (TEMPLATE_ROOT) не трогаем ни разу, см. шапку и ВТОРОЙ ВОЗВРАТ выше) ════

# 🪤 МЕТКА ЗАПУСКА: PACKAGE теперь свой клон в НОВОМ временном каталоге на каждый прогон
# (ВТОРОЙ ВОЗВРАТ выше), но провалившийся прогон свой каталог СОХРАНЯЕТ (mezo_stand),
# и при разборе провала его нередко зовут ПОВТОРНО поверх той же папки образца, откуда
# клонировали, — метка снимает и этот редкий случай совпадения байт, не только гипотезу
# о постоянном каталоге. Без неё `git add` не видел бы изменения, и коммит честно
# отказывал «нечего коммитить», а не тихо создавался. Метка — ОДНА на весь прогон,
# в начале каждого файла-образца: относительные различия L1/L2/L3 внутри запуска не меняет.
# Сама метка RUN_NONCE задана выше, рядом с номером прогона RUN_ID: по ней же приёмка узнаёт
# свои следы в образце (карточка #804).
L1, L2, L3 = RUN_NONCE + b"line1 original\n", b"line2 shared\n", b"line3 original\n"

# ① / ② — merge-A.py: опора (L1,L2,L3), пакет потом меняет ТОЛЬКО L3 (непересекающиеся правки)
OPORA_A = L1 + L2 + L3
OPORA_A_COMMIT = add_pack_commit("scripts/merge-A.py", OPORA_A, "bite609: opora merge-A.py")
PACK_A_NOW = L1 + L2 + b"line3 CHANGED BY PACK\n"
PACK_A_COMMIT = add_pack_commit("scripts/merge-A.py", PACK_A_NOW, "bite609: pack changes L3 only")
OWN_A = RUN_NONCE + b"line1 EDITED BY CIRCUIT\n" + L2 + L3   # контур поменял ТОЛЬКО L1
FP_A = digest(OPORA_A)

# ③ — merge-B.py: опора; ОБЕ стороны меняют L2 ПО-РАЗНОМУ (пересечение)
OPORA_B = L1 + L2 + L3
OPORA_B_COMMIT = add_pack_commit("scripts/merge-B.py", OPORA_B, "bite609: opora merge-B.py")
PACK_B_NOW = L1 + b"line2 CHANGED BY PACK\n" + L3
PACK_B_COMMIT = add_pack_commit("scripts/merge-B.py", PACK_B_NOW, "bite609: pack changes L2")
OWN_B = L1 + b"line2 EDITED BY CIRCUIT\n" + L3   # контур меняет ТУ ЖЕ строку иначе
FP_B = digest(OPORA_B)

# ④ — merge-C.py: свой файл, независимый от A/B, чтобы случаи не делили состояние
OPORA_C = L1 + L2 + L3
OPORA_C_COMMIT = add_pack_commit("scripts/merge-C.py", OPORA_C, "bite609: opora merge-C.py")
PACK_C_NOW = L1 + L2 + b"line3 CHANGED BY PACK (case 4)\n"
PACK_C_COMMIT = add_pack_commit("scripts/merge-C.py", PACK_C_NOW, "bite609: pack changes L3 (case 4)")
OWN_C = RUN_NONCE + b"line1 EDITED BY CIRCUIT (case 4)\n" + L2 + L3
FP_C = digest(OPORA_C)

# ①-встречный — merge-D.py: пакет НЕ менял файл после опоры (опора == пакет сейчас)
OPORA_D = L1 + L2 + L3
OPORA_D_COMMIT = add_pack_commit("scripts/merge-D.py", OPORA_D, "bite609: merge-D.py, pack holds it")
OWN_D = RUN_NONCE + b"line1 EDITED BY CIRCUIT (case D)\n" + L2 + L3   # контур правит, пакет — нет
FP_D = digest(OPORA_D)

# доп. «отпечаток есть, но версии с ним в истории нет» — merge-F.py: реальная история пакета,
# но отпечаток контура — ЗАГЛУШКА, не совпадающая ни с одной версией пути.
OPORA_F = L1 + L2 + L3
OPORA_F_COMMIT = add_pack_commit("scripts/merge-F.py", OPORA_F, "bite609: merge-F.py")
OWN_F = RUN_NONCE + b"line1 EDITED BY CIRCUIT (case F)\n" + L2 + L3
FP_F_BOGUS = "0" * 12   # заведомо не встретится ни в одном digest()

# доп. контроль — merge-G.py: НЕ правлен у контура (обычный «≠ отличается»), должен обновиться
# --apply как раньше. Отпечаток контура = опора; текущий файл контура = опора (не правлен).
OPORA_G = L1 + L2 + L3
OPORA_G_COMMIT = add_pack_commit("scripts/merge-G.py", OPORA_G, "bite609: opora merge-G.py")
PACK_G_NOW = L1 + L2 + b"line3 fresh update from pack\n"
PACK_G_COMMIT = add_pack_commit("scripts/merge-G.py", PACK_G_NOW, "bite609: pack advances merge-G.py")
FP_G = digest(OPORA_G)

# ВОЗВРАТ PROTO (карточка #609) — merge-E.py: ЛОЖНЫЕ ОТМЕТКИ ПЕРЕСЕЧЕНИЯ. Во ВСЕХ
# трёх версиях (опора · ваш · пакет) есть строки, СОДЕРЖАЩИЕ подписи git merge-file ВНУТРИ
# обычного кода (`x = b"<<<<<<< "` / `y = b">>>>>>> "` — ровно то, что уже стоит в самом
# update-tools.py и в этой приёмке как печатаемый текст). Наивный поиск подстроки
# «draft_bytes.count(b"<<<<<<< ")» насчитал бы ложные пересечения на этих строках, хотя
# правки контура и пакета НЕ пересекаются вовсе.
# 🪤 НАЙДЕНО ЭТИМ ПРОГОНОМ, не рассуждением заранее: если строку контура и строку пакета
# положить ВПЛОТНУЮ (без общей неизменной строки между ними), git merge-file сводит их в
# ОДНО пересечение даже при разных строках — у диалога нет общего контекста, чтобы понять,
# что это два независимых места. Разделяющая неизменная строка (line_middle) — ОБЯЗАТЕЛЬНА
# для настоящего клина, не только для ложного; тот же приём уже стоит у merge-A.py (там его
# роль играет L2 между L1 и L3).
MARK_OURS_LINE = b'x = b"<<<<<<< "\n'
MARK_THEIRS_LINE = b'y = b">>>>>>> "\n'
OPORA_E = (RUN_NONCE + MARK_OURS_LINE + MARK_THEIRS_LINE + b"line_own original\n"
          + b"line_middle unchanged\n" + b"line_pack original\n")
OPORA_E_COMMIT = add_pack_commit("scripts/merge-E.py", OPORA_E, "bite609: opora merge-E.py")
PACK_E_NOW = (RUN_NONCE + MARK_OURS_LINE + MARK_THEIRS_LINE + b"line_own original\n"
             + b"line_middle unchanged\n" + b"line_pack CHANGED BY PACK (case E)\n")
PACK_E_COMMIT = add_pack_commit("scripts/merge-E.py", PACK_E_NOW, "bite609: pack changes line_pack only")
OWN_E = (RUN_NONCE + MARK_OURS_LINE + MARK_THEIRS_LINE + b"line_own EDITED BY CIRCUIT (case E)\n"
        + b"line_middle unchanged\n" + b"line_pack original\n")
FP_E = digest(OPORA_E)

# ВОЗВРАТ PROTO (третий возврат, карточка #609, находка COORD, записка #5232): CRLF-СЛУЧАИ.
# На Windows (core.autocrlf=true) файл контура и файл пакета НА ДИСКЕ — CRLF, а опора,
# пришедшая из истории пакета (git show), — LF: история хранит объекты LF, автокрлф
# трогает только рабочее дерево при извлечении. Коммитим в СВОЙ клон, как всегда, LF-байтами
# (так живёт история) — а ПОСЛЕ коммита переписываем файл ПАКЕТА НА ДИСКЕ клона CRLF-байтами,
# БЕЗ нового коммита: рабочее дерево расходится с историей ровно как у настоящего
# autocrlf-чекаута. Файл КОНТУРА (seed лёгкого контура) тоже пишем CRLF напрямую — этот
# путь вообще не коммитится, круга «история/диск» у него нет.
def crlf(data: bytes) -> bytes:
    # карточка #626: своя crlf() заменена общим mezo_stand.crlf_twin — приёмка больше
    # не строит чужую форму своей рукой, берёт ту же, что и остальные приёмки контура.
    return mezo_stand.crlf_twin(data.decode("utf-8")).encode("utf-8")


def is_crlf(data: bytes) -> bool:
    """Практическая проверка «весь файл CRLF»: у КАЖДОГО \\n есть свой \\r перед ним, и
    одиноких \\r (вне пары) нет — ровно то, что оставляет запись crlf() выше."""
    return b"\n" in data and data.count(b"\r") == data.count(b"\n") == data.count(b"\r\n")


def is_lf(data: bytes) -> bool:
    return b"\r" not in data


# ⑥ / ⑥-встречный — merge-I.py: как merge-A.py (случаи ①/②), но CRLF на диске
OPORA_I = L1 + L2 + L3
OPORA_I_COMMIT = add_pack_commit("scripts/merge-I.py", OPORA_I, "bite609: opora merge-I.py")
PACK_I_NOW = L1 + L2 + b"line3 CHANGED BY PACK (case I)\n"
PACK_I_COMMIT = add_pack_commit("scripts/merge-I.py", PACK_I_NOW, "bite609: pack changes L3 (case I)")
(PACKAGE / "scripts" / "merge-I.py").write_bytes(crlf(PACK_I_NOW))   # диск CRLF, история осталась LF
OWN_I = crlf(RUN_NONCE + b"line1 EDITED BY CIRCUIT (case I)\n" + L2 + L3)   # файл контура — CRLF на диске
FP_I = digest(OPORA_I)

# ⑥-встречный (контроль) — merge-J.py: та же форма, ПОЛНОСТЬЮ на LF (ни одного CRLF) —
# доказывает, что находка именно про CRLF, а не про что-то постороннее в новом коде.
OPORA_J = L1 + L2 + L3
OPORA_J_COMMIT = add_pack_commit("scripts/merge-J.py", OPORA_J, "bite609: opora merge-J.py")
PACK_J_NOW = L1 + L2 + b"line3 CHANGED BY PACK (case J)\n"
PACK_J_COMMIT = add_pack_commit("scripts/merge-J.py", PACK_J_NOW, "bite609: pack changes L3 (case J)")
OWN_J = RUN_NONCE + b"line1 EDITED BY CIRCUIT (case J)\n" + L2 + L3
FP_J = digest(OPORA_J)

# ⑦ — merge-K.py: CRLF на диске, ОБЕ стороны меняют L2 ПО-РАЗНОМУ — настоящее пересечение
# обязано остаться честным пересечением и на CRLF (не 0 и не «потерялось молча»).
OPORA_K = L1 + L2 + L3
OPORA_K_COMMIT = add_pack_commit("scripts/merge-K.py", OPORA_K, "bite609: opora merge-K.py")
PACK_K_NOW = L1 + b"line2 CHANGED BY PACK (case K)\n" + L3
PACK_K_COMMIT = add_pack_commit("scripts/merge-K.py", PACK_K_NOW, "bite609: pack changes L2 (case K)")
(PACKAGE / "scripts" / "merge-K.py").write_bytes(crlf(PACK_K_NOW))
OWN_K = crlf(L1 + b"line2 EDITED BY CIRCUIT (case K)\n" + L3)
FP_K = digest(OPORA_K)

# ⑥-смешанный — merge-L.py (решающий прогон PROTO, третий возврат карточки #609): файл КОНТУРА
# на LF, файл ПАКЕТА на диске CRLF (история LF). В ⑥/⑦ обе стороны CRLF, в ⑥-встречном обе LF —
# ни один из них не отличает «стиль черновика взят у файла контура» от «взят у пакета» или
# «CRLF, если он есть хоть у кого-то». Требование «черновик — в стиле файла контура» получает
# здесь свой встречный случай: живые файлы контура бывают и LF, а рабочее дерево пакета — CRLF.
OPORA_L = L1 + L2 + L3
OPORA_L_COMMIT = add_pack_commit("scripts/merge-L.py", OPORA_L, "bite609: opora merge-L.py")
PACK_L_NOW = L1 + L2 + b"line3 CHANGED BY PACK (case L)\n"
PACK_L_COMMIT = add_pack_commit("scripts/merge-L.py", PACK_L_NOW, "bite609: pack changes L3 (case L)")
(PACKAGE / "scripts" / "merge-L.py").write_bytes(crlf(PACK_L_NOW))   # пакет на диске CRLF
OWN_L = RUN_NONCE + b"line1 EDITED BY CIRCUIT (case L)\n" + L2 + L3   # файл контура — LF
FP_L = digest(OPORA_L)

PACK_READY_STATE = pack_state()   # с этой точки update-tools.py САМ пакет больше не меняет
# Свои версии и отпечатки известны все, испытуемый ещё не звался ни разу: вопрос о своих следах
# в meta живого контура — «до» (карточка #804).
LIVE_TRACES_BEFORE = meta_traces(LIVE_DB)


# ═══ ① у «✋» — печатается «менял после опоры: да — коммиты …» / «не менял» (встречный) ════

root_a, scripts_a, db_a = make_light_circuit(
    "case-A", {"merge-A.py": OWN_A}, {"merge-A.py": FP_A})
rc_a1, out_a1 = run(scripts_a, "--source", str(PACKAGE), "--db", str(db_a))
case("① «✋» печатает «пакет менял этот файл после опоры: да» + короткий хеш коммита пакета",
    rc_a1 == 0 and "✋" in out_a1 and "merge-A.py" in out_a1
    and "пакет менял этот файл после опоры" in out_a1 and ": да" in out_a1
    and PACK_A_COMMIT in out_a1,
    f"код {rc_a1} · ищем коммит {PACK_A_COMMIT} рядом с «: да»")

root_d, scripts_d, db_d = make_light_circuit(
    "case-D", {"merge-D.py": OWN_D}, {"merge-D.py": FP_D})
rc_d1, out_d1 = run(scripts_d, "--source", str(PACKAGE), "--db", str(db_d))
case("① встречный: пакет НЕ менял файл после опоры → печатается «не менял», без коммитов",
    rc_d1 == 0 and "✋" in out_d1 and "merge-D.py" in out_d1
    and "пакет после опоры" in out_d1 and "не менял" in out_d1
    and "менял этот файл после опоры" not in out_d1.split("merge-D.py")[-1][:200],
    f"код {rc_d1}")


# ═══ ② --merge на НЕПЕРЕСЕКАЮЩИХСЯ правках — черновик несёт ОБЕ, живой файл не тронут ════

root_a2, scripts_a2, db_a2 = make_light_circuit(
    "case-A-merge", {"merge-A.py": OWN_A}, {"merge-A.py": FP_A})
rc_a2, out_a2 = run(scripts_a2, "--merge", "merge-A.py", "--source", str(PACKAGE), "--db", str(db_a2))
draft_a_lines = [ln for ln in out_a2.splitlines() if ln.startswith("черновик: ")]
draft_a = Path(draft_a_lines[0].split("черновик: ", 1)[1].strip()) if draft_a_lines else None
draft_a_bytes = draft_a.read_bytes() if draft_a and draft_a.exists() else b""
live_a_after_merge = (scripts_a2 / "merge-A.py").read_bytes()
case("② --merge на непересекающихся правках: 0 пересечений",
    rc_a2 == 0 and "пересечений: 0" in out_a2, f"код {rc_a2}")
case("② черновик несёт ОБЕ правки (свою L1 и правку пакета L3)",
    b"EDITED BY CIRCUIT" in draft_a_bytes and b"CHANGED BY PACK" in draft_a_bytes,
    f"черновик: {draft_a}")
case("② живой файл НЕ тронут --merge (остался равен своей правке до сведения)",
    live_a_after_merge == OWN_A, "сравнили байты живого файла контура до/после --merge")


# ═══ ③ --merge на ПЕРЕСЕКАЮЩИХСЯ правках — отметки пересечения; --accept-merge отказывает ═══

root_b, scripts_b, db_b = make_light_circuit(
    "case-B-merge", {"merge-B.py": OWN_B}, {"merge-B.py": FP_B})
rc_b1, out_b1 = run(scripts_b, "--merge", "merge-B.py", "--source", str(PACKAGE), "--db", str(db_b))
draft_b_lines = [ln for ln in out_b1.splitlines() if ln.startswith("черновик: ")]
draft_b = Path(draft_b_lines[0].split("черновик: ", 1)[1].strip()) if draft_b_lines else None
draft_b_bytes = draft_b.read_bytes() if draft_b and draft_b.exists() else b""
case("③ --merge на пересекающихся правках: черновик несёт отметки пересечения",
    rc_b1 == 0 and "пересечений: 0" not in out_b1
    and b"<<<<<<< " in draft_b_bytes and b">>>>>>> " in draft_b_bytes,
    f"код {rc_b1} · отметки в черновике: {b'<<<<<<< ' in draft_b_bytes}")

rc_b2, out_b2 = run(scripts_b, "--accept-merge", "merge-B.py", "--db", str(db_b), "--apply")
live_b_before_resolve = (scripts_b / "merge-B.py").read_bytes()
case("③ --accept-merge ОТКАЗЫВАЕТ, пока в черновике остаются отметки пересечения",
    rc_b2 != 0 and live_b_before_resolve == OWN_B,
    f"код {rc_b2} (ждём отказ) · живой файл не тронут: {live_b_before_resolve == OWN_B}")

# роль разобрала пересечение сама — черновик переписан ЧИСТЫМ сведённым текстом
# ⚖️ НА ПРЕЖНЕЙ копии (без --merge) draft_b остаётся None — не падаем трассировкой, а
# честно красим случай СВОЕЙ причиной (нечего разбирать, --merge не оставил черновика) и
# идём дальше: приёмке важно назвать ВСЕ различающие случаи за один прогон, не только первый.
resolved_b = L1 + "line2 EDITED BY CIRCUIT (принято сверх правки пакета)\n".encode("utf-8") + L3
# ⚖️ РЕШАЮЩИЙ ПРОГОН PROTO: второй вид «черновика нет» — он БЫЛ, но --accept-merge выше принял
# его вместе с отметками и убрал за собой (поломка «отказ снят»). Без этой ветки приёмка падала
# трассировкой на записи в исчезнувший каталог — провал верный, но читался как поломка приёмки.
if draft_b is None or not draft_b.parent.exists():
    case("③ после ручной правки черновика (отметки убраны) --accept-merge ПРИНИМАЕТ",
        False, "черновика нет — " + ("--merge на этой копии не оставил его, разбирать нечего"
                                     if draft_b is None else
                                     "--accept-merge уже принял его С ОТМЕТКАМИ и убрал (см. провал выше)"))
else:
    draft_b.write_bytes(resolved_b)
    rc_b3, out_b3 = run(scripts_b, "--accept-merge", "merge-B.py", "--db", str(db_b), "--apply")
    live_b_after_resolve = (scripts_b / "merge-B.py").read_bytes()
    case("③ после ручной правки черновика (отметки убраны) --accept-merge ПРИНИМАЕТ",
        rc_b3 == 0 and "✅ принято" in out_b3 and live_b_after_resolve == resolved_b,
        f"код {rc_b3}")


# ═══ ④ опора после --accept-merge = версия пакета, С КОТОРОЙ сводили; следующий прогон —
#     «✋», но «пакет после опоры не менял»; прежняя опора в выводе не встречается ════

root_c, scripts_c, db_c = make_light_circuit(
    "case-C-merge", {"merge-C.py": OWN_C}, {"merge-C.py": FP_C})
run(scripts_c, "--merge", "merge-C.py", "--source", str(PACKAGE), "--db", str(db_c))
meta_c_before = meta_of(db_c)
rc_c1, out_c1 = run(scripts_c, "--accept-merge", "merge-C.py", "--db", str(db_c), "--apply")
meta_c_after = meta_of(db_c)
fp_c_after = json.loads(meta_c_after["template_files_sha"]).get("merge-C.py")
expected_fp_c = digest(PACK_C_NOW)
case("④ после --accept-merge опора (meta.template_files_sha) = версия пакета, С КОТОРОЙ сводили",
    rc_c1 == 0 and fp_c_after == expected_fp_c and fp_c_after != FP_C,
    f"код {rc_c1} · было {FP_C} · стало {fp_c_after} · ждём {expected_fp_c}")

rc_c2, out_c2 = run(scripts_c, "--source", str(PACKAGE), "--db", str(db_c))
case("④ следующий обычный прогон снова видит «✋ ПРАВЛЕН У ТЕБЯ»",
    rc_c2 == 0 and "✋" in out_c2 and "merge-C.py" in out_c2, f"код {rc_c2}")
case("④ … но с отметкой «пакет после опоры не менял»",
    "пакет после опоры" in out_c2 and "не менял" in out_c2, f"код {rc_c2}")
case("④ прежняя опора (её отпечаток) в выводе НЕ встречается",
    FP_C not in out_c2, f"прежний отпечаток {FP_C} ищем и не находим")


# ═══ доп. «опору найти нечем»: источник без истории вовсе ════
# ⚖️ Файл здесь назван merge-H.py (не merge-E.py) — «E» занята НОВЫМ случаем возврата
# координатора (ложные отметки пересечения) чуть ниже.

dump_src = STAND / "dump-no-history"
(dump_src / "scripts").mkdir(parents=True)
(dump_src / "scripts" / "merge-H.py").write_bytes(L1 + L2 + b"line3 in dump, no git\n")
root_h, scripts_h, db_h = make_light_circuit(
    "case-H-merge", {"merge-H.py": b"line1 OWN EDIT (case H)\n" + L2 + L3},
    {"merge-H.py": digest(L1 + L2 + L3)})
rc_h, out_h = run(scripts_h, "--merge", "merge-H.py", "--source", str(dump_src), "--db", str(db_h))
case("доп. --merge: источник без истории вовсе → «опору найти нечем: истории пакета нет»",
    rc_h != 0 and "опору найти нечем" in out_h and "истории пакета нет" in out_h,
    f"код {rc_h} (ждём отказ, не трассировку)")


# ═══ ВОЗВРАТ PROTO (карточка #609): ЛОЖНЫЕ ОТМЕТКИ ПЕРЕСЕЧЕНИЯ — merge-E.py (текст
# фикстуры — выше, вместе со всеми остальными, ДО pack_state(); контроль «пакет не тронут»
# ниже обязан видеть коммиты merge-E.py КАК ЧАСТЬ подготовки, а не как правку update-tools.py).
# Правки НЕ пересекаются (контур меняет одну строку, пакет — другую, обе строки-подписи
# остаются НЕТРОНУТЫМИ с обеих сторон, между строками — разделитель line_middle) — настоящих
# пересечений здесь НЕТ ни одного. Наивный поиск подстроки «draft_bytes.count(b"<<<<<<< ")»
# насчитал бы ложные «пересечений: N» на строках-подписях, хотя git merge-file сам развёл
# правки без единого пересечения.

root_e2, scripts_e2, db_e2 = make_light_circuit(
    "case-E-merge", {"merge-E.py": OWN_E}, {"merge-E.py": FP_E})
rc_e1, out_e1 = run(scripts_e2, "--merge", "merge-E.py", "--source", str(PACKAGE), "--db", str(db_e2))
case("E ЛОЖНЫЕ ОТМЕТКИ: строки-подписи ВНУТРИ обычного кода не путаются с настоящим "
    "пересечением — «пересечений: 0», хотя обе подписи буквально есть в тексте",
    rc_e1 == 0 and "пересечений: 0" in out_e1, f"код {rc_e1}")

rc_e2, out_e2 = run(scripts_e2, "--accept-merge", "merge-E.py", "--db", str(db_e2), "--apply")
live_e_after = (scripts_e2 / "merge-E.py").read_bytes()
meta_e_after = meta_of(db_e2)
fp_e_after = json.loads(meta_e_after["template_files_sha"]).get("merge-E.py")
case("E --accept-merge ПРИНИМАЕТ (ложные отметки не мешают), отпечаток обновлён",
    rc_e2 == 0 and "✅ принято" in out_e2 and fp_e_after == digest(PACK_E_NOW),
    f"код {rc_e2} · отпечаток стал {fp_e_after}, ждём {digest(PACK_E_NOW)}")

# ── ПОЛОМКА (требование задания): вернуть детект пересечений к поиску подстроки где
# угодно в тексте — красит РОВНО случай E, своей причиной (ложные «пересечений: N» на
# строках-подписях ВНУТРИ кода); остальные случаи (A-D, F-H) не задевает — там строк с
# подписями git merge-file внутри обычного текста нет.
brokenE_dir = STAND / "brokenE"
brokenE_tool = mezo_stand.copy_tool(TARGET, brokenE_dir)
srcE = brokenE_tool.read_text(encoding="utf-8")
# ⚖️ ЯКОРЬ — ТОЛЬКО СТРОКА ОПРЕДЕЛЕНИЯ (без обратных слэшей внутри тела функции: там живут
# экранированные b"\r\n"/b"\n", и ручной перенабор такого литерала уже один раз разошёлся
# с настоящими байтами файла — поймано ЭТИМ прогоном, не рассуждением). Поломка — РАННИЙ
# return сразу после сигнатуры: остаток функции (докстрока, тело) становится недостижимым
# кодом, но синтаксис цел, и настоящей подмене это не мешает — что и нужно для поломки.
anchorE = "def count_conflicts(data: bytes) -> int:\n"
if srcE.count(anchorE) != 1:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: сигнатура count_conflicts не найдена дословно — "
             "испытуемое изменилось, поломка E бьёт мимо")
brokenE_text = srcE.replace(
    anchorE,
    anchorE
    + '    return data.count(b"<<<<<<< ")  '
      '# ПОЛОМКА карточки #609: вернули поиск подстроки где угодно в тексте\n')
brokenE_tool.write_text(brokenE_text, encoding="utf-8")

root_eb, scripts_eb, db_eb = make_light_circuit(
    "case-E-poison", {"merge-E.py": OWN_E}, {"merge-E.py": FP_E})
mezo_stand.copy_tool(brokenE_tool, scripts_eb)
rc_e3, out_e3 = run(scripts_eb, "--merge", "merge-E.py", "--source", str(PACKAGE), "--db", str(db_eb))
case("E ПОЛОМКА (детект пересечений — снова подстрока где угодно) КРАСИТ ровно случай E: "
    "ложное «пересечений: 1» на строке-подписи внутри кода",
    rc_e3 == 0 and "пересечений: 0" not in out_e3, f"код {rc_e3}")

root_ab, scripts_ab, db_ab = make_light_circuit(
    "case-A-poisonE", {"merge-A.py": OWN_A}, {"merge-A.py": FP_A})
mezo_stand.copy_tool(brokenE_tool, scripts_ab)
rc_ab, out_ab = run(scripts_ab, "--merge", "merge-A.py", "--source", str(PACKAGE), "--db", str(db_ab))
case("E ПОЛОМКА не трогает случай ②: merge-A.py не содержит подписей ВНУТРИ кода, "
    "«пересечений: 0» остаётся верным даже с поломкой",
    rc_ab == 0 and "пересечений: 0" in out_ab, f"код {rc_ab}")


# ═══ доп. «опору найти нечем»: отпечаток есть, но версии с ним в истории пакета нет ════

root_f, scripts_f, db_f = make_light_circuit(
    "case-F-merge", {"merge-F.py": OWN_F}, {"merge-F.py": FP_F_BOGUS})
rc_f, out_f = run(scripts_f, "--merge", "merge-F.py", "--source", str(PACKAGE), "--db", str(db_f))
case("доп. --merge: отпечаток установки есть, но в истории пакета такой версии нет → "
    "«опору найти нечем», а не выдуманная опора",
    rc_f != 0 and "опору найти нечем" in out_f, f"код {rc_f} (ждём отказ)")


# ═══ доп. контроль: файл, НЕ правленый у контура — обновляется --apply как раньше ════

root_g, scripts_g, db_g = make_light_circuit(
    "case-G-control", {"merge-G.py": OPORA_G}, {"merge-G.py": FP_G})
rc_g1, out_g1 = run(scripts_g, "--source", str(PACKAGE), "--db", str(db_g))
case("контроль: файл БЕЗ своей правки показан «≠ отличается» (обычный путь, не own_edits)",
    rc_g1 == 0 and "merge-G.py" in out_g1
    and any(ln.strip().startswith("≠") and "merge-G.py" in ln for ln in out_g1.splitlines()),
    f"код {rc_g1}")
rc_g2, out_g2 = run(scripts_g, "--source", str(PACKAGE), "--db", str(db_g), "--apply")
live_g_after = (scripts_g / "merge-G.py").read_bytes()
case("контроль: --apply берёт версию пакета как раньше (новый код не задел старый путь)",
    rc_g2 == 0 and live_g_after == PACK_G_NOW, f"код {rc_g2}")


# ═══ ⑤ НАРОЧНАЯ ПОЛОМКА №1 (в памяти карточки #609): опора = версия пакета СЕЙЧАС вместо
#     версии установки. Красит РОВНО случай ② — правка пакета исчезает из черновика МОЛЧА,
#     без единого пересечения (0 конфликтов, но черновик = «ours» без изменений пакета).

broken1_dir = STAND / "broken1"
broken1_tool = mezo_stand.copy_tool(TARGET, broken1_dir)
src1 = broken1_tool.read_text(encoding="utf-8")
# ⚖️ Якорь несёт ПРЕДЫДУЩУЮ строку тоже, не только саму строку опоры: голая
# «fp = fingerprints.get(...)» — ПОДСТРОКА более глубокого отступа той же строки в
# main() (там опора для отчёта «✋» ищется тем же выражением) — .count() считает её по
# СИМВОЛАМ, не по границе строки, и находил бы «встречена дважды» на исправном инструменте.
anchor1 = ('    if same_text(mine_bytes, pack_bytes):\n'
          '        sys.exit(f"⛔ «{rel_arg}»: ваш текст и текст пакета уже совпадают дословно — "\n'
          '                 f"сводить нечего")\n'
          '    fp = fingerprints.get(str(rel).replace(chr(92), "/"))\n')
if src1.count(anchor1) != 1:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка получения опоры «fp = fingerprints.get(...)» в "
             "cmd_merge не найдена дословно (или встречена не один раз) — испытуемое "
             "изменилось, поломка ⑤ бьёт мимо")
broken1_text = src1.replace(
    anchor1,
    '    if same_text(mine_bytes, pack_bytes):\n'
    '        sys.exit(f"⛔ «{rel_arg}»: ваш текст и текст пакета уже совпадают дословно — "\n'
    '                 f"сводить нечего")\n'
    '    fp = digest(pack_bytes)  # ПОЛОМКА карточки #609: опора = версия пакета СЕЙЧАС\n')
broken1_tool.write_text(broken1_text, encoding="utf-8")

root_a3, scripts_a3, db_a3 = make_light_circuit(
    "case-A-poison1", {"merge-A.py": OWN_A}, {"merge-A.py": FP_A})
mezo_stand.copy_tool(broken1_tool, scripts_a3)   # испытуемый ПОЛОМАННЫЙ — поверх целого
rc_a3, out_a3 = run(scripts_a3, "--merge", "merge-A.py", "--source", str(PACKAGE), "--db", str(db_a3))
draft_a3_lines = [ln for ln in out_a3.splitlines() if ln.startswith("черновик: ")]
draft_a3 = Path(draft_a3_lines[0].split("черновик: ", 1)[1].strip()) if draft_a3_lines else None
draft_a3_bytes = draft_a3.read_bytes() if draft_a3 and draft_a3.exists() else b""
case("⑤ ПОЛОМКА №1 (опора = пакет сейчас) КРАСИТ ровно случай ②: правка пакета (L3) "
    "пропадает из черновика МОЛЧА — 0 пересечений, но не обе правки",
    rc_a3 == 0 and "пересечений: 0" in out_a3
    and b"EDITED BY CIRCUIT" in draft_a3_bytes and b"CHANGED BY PACK" not in draft_a3_bytes,
    f"код {rc_a3} · своя правка в черновике: {b'EDITED BY CIRCUIT' in draft_a3_bytes} · "
    f"правка пакета в черновике: {b'CHANGED BY PACK' in draft_a3_bytes} (ждём False — "
    f"поломка обязана её потерять)")

# ДОВЕСОК К ПОЛОМКЕ №1, найден ЭТИМ прогоном (не рассуждением заранее — первая редакция
# здесь ждала «не трогает случай ③», и была НЕВЕРНОЙ: с поломкой опора = digest(текущих
# байт пакета) ВСЕГДА совпадает сама с собой (theirs), diff(опора→пакет) пуст ДЛЯ ЛЮБОГО
# файла — значит git merge-file возвращает «ваш текст» без единого пересечения ВСЕГДА,
# в том числе там, где правки пересекаются по-настоящему. Оставлена как факт, а не
# пересказ ожидания: поломка №1 бьёт ШИРЕ случая ②, а не только по нему.
root_b2, scripts_b2, db_b2 = make_light_circuit(
    "case-B-poison1", {"merge-B.py": OWN_B}, {"merge-B.py": FP_B})
mezo_stand.copy_tool(broken1_tool, scripts_b2)
rc_b4, out_b4 = run(scripts_b2, "--merge", "merge-B.py", "--source", str(PACKAGE), "--db", str(db_b2))
case("⑤ ПОЛОМКА №1, довесок: та же беда и на пересекающемся файле — правка пакета (L2) "
    "пропадает МОЛЧА (0 пересечений вместо честного пересечения ours/theirs)",
    rc_b4 == 0 and "пересечений: 0" in out_b4, f"код {rc_b4}")


# ═══ ⑤ НАРОЧНАЯ ПОЛОМКА №2: --accept-merge БЕЗ обновления опоры. Красит РОВНО случай ④ —
#     отпечаток в meta.template_files_sha после --accept-merge не меняется.

broken2_dir = STAND / "broken2"
broken2_tool = mezo_stand.copy_tool(TARGET, broken2_dir)
src2 = broken2_tool.read_text(encoding="utf-8")
anchor2 = '    fingerprints[meta["rel"]] = meta["pack_fingerprint"]\n'
if src2.count(anchor2) != 1:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка обновления опоры в cmd_accept_merge не найдена "
             "дословно — испытуемое изменилось, поломка ⑤ №2 бьёт мимо")
broken2_text = src2.replace(
    anchor2,
    '    pass  # ПОЛОМКА карточки #609: fingerprints[meta["rel"]] = ... снята — опора не обновится\n')
broken2_tool.write_text(broken2_text, encoding="utf-8")

root_c2, scripts_c2, db_c2 = make_light_circuit(
    "case-C-poison2", {"merge-C.py": OWN_C}, {"merge-C.py": FP_C})
run(scripts_c2, "--merge", "merge-C.py", "--source", str(PACKAGE), "--db", str(db_c2))
mezo_stand.copy_tool(broken2_tool, scripts_c2)   # ПОЛОМАННЫЙ инструмент — для --accept-merge
meta_c2_before = meta_of(db_c2)
rc_c3, out_c3 = run(scripts_c2, "--accept-merge", "merge-C.py", "--db", str(db_c2), "--apply")
meta_c2_after = meta_of(db_c2)
fp_c2_after = json.loads(meta_c2_after["template_files_sha"]).get("merge-C.py")
live_c2_after = (scripts_c2 / "merge-C.py").read_bytes()
case("⑤ ПОЛОМКА №2 (--accept-merge без обновления опоры) КРАСИТ ровно случай ④: "
    "живой файл принят, но опора в meta НЕ изменилась",
    rc_c3 == 0 and live_c2_after != OWN_C   # черновик всё же положен в живой файл
    and fp_c2_after == FP_C,                # а опора осталась СТАРОЙ — поломка сработала
    f"код {rc_c3} · опора: было {FP_C} · стало {fp_c2_after} (ждём БЕЗ изменения — поломка)")


# ═══ ВОЗВРАТ PROTO (третий возврат, карточка #609): ⑥ CRLF — файл контура и файл пакета
#     НА ДИСКЕ CRLF, опора из истории LF (находка COORD, записка #5232). Проверяем ДВЕ вещи
#     на одной фикстуре: (а) обычный прогон без --merge по-прежнему верно печатает «✋ …
#     пакет менял этот файл после опоры: да» (item 2 третьего возврата — digest и поиск
#     опоры по отпечатку уже нормализуют, здесь это ПРОВЕРЕНО, а не предположено заранее);
#     (б) --merge на CRLF даёт «пересечений: 0» (была бы 1–3 без приведения к LF), черновик
#     несёт ОБЕ правки и сам в стиле CRLF, как у файла контура ════

root_i, scripts_i, db_i = make_light_circuit(
    "case-I", {"merge-I.py": OWN_I}, {"merge-I.py": FP_I})
rc_i0, out_i0 = run(scripts_i, "--source", str(PACKAGE), "--db", str(db_i))
case("⑥ (item 2) на CRLF «✋» печатает «пакет менял этот файл после опоры: да» — digest "
    "и поиск опоры по отпечатку уже нормализуют концы строк, здесь это ПРОВЕРЕНО",
    rc_i0 == 0 and "✋" in out_i0 and "merge-I.py" in out_i0
    and "пакет менял этот файл после опоры" in out_i0 and ": да" in out_i0
    and PACK_I_COMMIT in out_i0,
    f"код {rc_i0} · ищем коммит {PACK_I_COMMIT} рядом с «: да»")

root_i2, scripts_i2, db_i2 = make_light_circuit(
    "case-I-merge", {"merge-I.py": OWN_I}, {"merge-I.py": FP_I})
rc_i1, out_i1 = run(scripts_i2, "--merge", "merge-I.py", "--source", str(PACKAGE), "--db", str(db_i2))
draft_i_lines = [ln for ln in out_i1.splitlines() if ln.startswith("черновик: ")]
draft_i = Path(draft_i_lines[0].split("черновик: ", 1)[1].strip()) if draft_i_lines else None
draft_i_bytes = draft_i.read_bytes() if draft_i and draft_i.exists() else b""
case("⑥ CRLF, непересекающиеся правки: «пересечений: 0» (была бы 1–3 без приведения к LF "
    "перед git merge-file — находка COORD, записка #5232)",
    rc_i1 == 0 and "пересечений: 0" in out_i1, f"код {rc_i1}")
case("⑥ черновик несёт ОБЕ правки и сам в стиле CRLF, как у файла контура",
    b"EDITED BY CIRCUIT" in draft_i_bytes and b"CHANGED BY PACK" in draft_i_bytes
    and is_crlf(draft_i_bytes),
    f"черновик: {draft_i} · CRLF: {is_crlf(draft_i_bytes)}")

rc_i2, out_i2 = run(scripts_i2, "--accept-merge", "merge-I.py", "--db", str(db_i2), "--apply")
live_i_after = (scripts_i2 / "merge-I.py").read_bytes()
case("⑥ после --accept-merge --apply живой файл принят и остался CRLF",
    rc_i2 == 0 and "✅ принято" in out_i2 and is_crlf(live_i_after),
    f"код {rc_i2} · CRLF: {is_crlf(live_i_after)}")


# ═══ ⑥-встречный: тот же случай ПОЛНОСТЬЮ НА LF (ни одного CRLF) — доказывает, что находка
#     COORD именно про CRLF, а не про что-то постороннее в новом коде ════

root_j, scripts_j, db_j = make_light_circuit(
    "case-J-merge", {"merge-J.py": OWN_J}, {"merge-J.py": FP_J})
rc_j1, out_j1 = run(scripts_j, "--merge", "merge-J.py", "--source", str(PACKAGE), "--db", str(db_j))
case("⑥-встречный: тот же случай на LF — «пересечений: 0», как и раньше (находка COORD "
    "не задевает уже исправный путь)",
    rc_j1 == 0 and "пересечений: 0" in out_j1, f"код {rc_j1}")


# ═══ ⑥-смешанный: контур LF, пакет на диске CRLF — черновик обязан быть в стиле КОНТУРА (LF).
#     Встречный случай к требованию «стиль — у файла контура, а не у пакета» (решающий прогон
#     PROTO: в ⑥/⑦ обе стороны одного стиля, и взятие стиля у пакета там неотличимо) ════

root_l, scripts_l, db_l = make_light_circuit(
    "case-L-merge", {"merge-L.py": OWN_L}, {"merge-L.py": FP_L})
rc_l1, out_l1 = run(scripts_l, "--merge", "merge-L.py", "--source", str(PACKAGE), "--db", str(db_l))
draft_l_lines = [ln for ln in out_l1.splitlines() if ln.startswith("черновик: ")]
draft_l = Path(draft_l_lines[0].split("черновик: ", 1)[1].strip()) if draft_l_lines else None
draft_l_bytes = draft_l.read_bytes() if draft_l and draft_l.exists() else b""
case("⑥-смешанный: контур LF, пакет на диске CRLF — «пересечений: 0», черновик несёт обе "
    "правки и сам в стиле ФАЙЛА КОНТУРА (LF), а не пакета",
    rc_l1 == 0 and "пересечений: 0" in out_l1
    and b"EDITED BY CIRCUIT" in draft_l_bytes and b"CHANGED BY PACK" in draft_l_bytes
    and is_lf(draft_l_bytes),
    f"код {rc_l1} · LF: {is_lf(draft_l_bytes)}")


# ═══ ⑦ CRLF, ПЕРЕСЕКАЮЩИЕСЯ правки: настоящее пересечение остаётся честным пересечением и
#     на CRLF — подсчёт пересечений и поиск отметок (item 1) верны на CRLF-черновике, не
#     только на LF ════

root_k, scripts_k, db_k = make_light_circuit(
    "case-K-merge", {"merge-K.py": OWN_K}, {"merge-K.py": FP_K})
rc_k1, out_k1 = run(scripts_k, "--merge", "merge-K.py", "--source", str(PACKAGE), "--db", str(db_k))
draft_k_lines = [ln for ln in out_k1.splitlines() if ln.startswith("черновик: ")]
draft_k = Path(draft_k_lines[0].split("черновик: ", 1)[1].strip()) if draft_k_lines else None
draft_k_bytes = draft_k.read_bytes() if draft_k and draft_k.exists() else b""
case("⑦ CRLF, пересекающиеся правки: пересечение остаётся честным (не 0), черновик несёт "
    "отметки, черновик сам в стиле CRLF",
    rc_k1 == 0 and "пересечений: 0" not in out_k1
    and b"<<<<<<< " in draft_k_bytes and b">>>>>>> " in draft_k_bytes
    and is_crlf(draft_k_bytes),
    f"код {rc_k1} · CRLF: {is_crlf(draft_k_bytes)}")

rc_k2, out_k2 = run(scripts_k, "--accept-merge", "merge-K.py", "--db", str(db_k), "--apply")
case("⑦ --accept-merge ОТКАЗЫВАЕТ на CRLF-черновике, пока отметки не убраны — поиск "
    "отметок (conflict_marker_lines) верен и на CRLF, не только на LF",
    rc_k2 != 0, f"код {rc_k2} (ждём отказ)")


# ── ПОЛОМКА (третий возврат, item 4): убрать приведение к LF перед git merge-file — красит
# РОВНО новый случай ⑥ (CRLF, непересекающиеся правки: «пересечений: 0» перестаёт быть
# верным); ⑥-встречный (весь на LF, приводить нечего) и ⑦ (и так ожидает пересечение —
# поломка не меняет вердикт «не 0») остаются как были.
brokenCRLF_dir = STAND / "brokenCRLF"
brokenCRLF_tool = mezo_stand.copy_tool(TARGET, brokenCRLF_dir)
srcCRLF = brokenCRLF_tool.read_text(encoding="utf-8")
anchorCRLF1 = ('    ours_f.write_bytes(to_lf(mine_bytes))\n'
              '    base_f.write_bytes(to_lf(opora_bytes))\n'
              '    theirs_f.write_bytes(to_lf(pack_bytes))\n')
anchorCRLF2 = '    draft_bytes = from_lf(r.stdout, circuit_style)\n'
if srcCRLF.count(anchorCRLF1) != 1 or srcCRLF.count(anchorCRLF2) != 1:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок приведения к LF в cmd_merge не найден дословно — "
             "испытуемое изменилось, поломка CRLF бьёт мимо")
brokenCRLF_text = (srcCRLF
    .replace(anchorCRLF1,
             '    ours_f.write_bytes(mine_bytes)  # ПОЛОМКА карточки #609 (третий возврат)\n'
             '    base_f.write_bytes(opora_bytes)  # приведение к LF снято\n'
             '    theirs_f.write_bytes(pack_bytes)\n')
    .replace(anchorCRLF2,
             '    draft_bytes = r.stdout  # ПОЛОМКА карточки #609: обратный перевод в стиль контура снят\n'))
brokenCRLF_tool.write_text(brokenCRLF_text, encoding="utf-8")

root_ic, scripts_ic, db_ic = make_light_circuit(
    "case-I-poisonCRLF", {"merge-I.py": OWN_I}, {"merge-I.py": FP_I})
mezo_stand.copy_tool(brokenCRLF_tool, scripts_ic)
rc_ic, out_ic = run(scripts_ic, "--merge", "merge-I.py", "--source", str(PACKAGE), "--db", str(db_ic))
case("ПОЛОМКА CRLF (приведение к LF снято) КРАСИТ ровно случай ⑥: ложные «пересечений: N» "
    "возвращаются на CRLF-файле с непересекающимися правками",
    rc_ic == 0 and "пересечений: 0" not in out_ic, f"код {rc_ic}")

root_jc, scripts_jc, db_jc = make_light_circuit(
    "case-J-poisonCRLF", {"merge-J.py": OWN_J}, {"merge-J.py": FP_J})
mezo_stand.copy_tool(brokenCRLF_tool, scripts_jc)
rc_jc, out_jc = run(scripts_jc, "--merge", "merge-J.py", "--source", str(PACKAGE), "--db", str(db_jc))
case("ПОЛОМКА CRLF не трогает ⑥-встречный: весь файл на LF, приводить нечего — "
    "«пересечений: 0» остаётся верным даже с поломкой",
    rc_jc == 0 and "пересечений: 0" in out_jc, f"код {rc_jc}")

root_kc, scripts_kc, db_kc = make_light_circuit(
    "case-K-poisonCRLF", {"merge-K.py": OWN_K}, {"merge-K.py": FP_K})
mezo_stand.copy_tool(brokenCRLF_tool, scripts_kc)
rc_kc, out_kc = run(scripts_kc, "--merge", "merge-K.py", "--source", str(PACKAGE), "--db", str(db_kc))
case("ПОЛОМКА CRLF не меняет вердикт ⑦: там и так ждём честное пересечение (не 0) — "
    "поломка не превращает верный отказ в ложный успех",
    rc_kc == 0 and "пересечений: 0" not in out_kc, f"код {rc_kc}")


print()
print(f"{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")

print("---- контроль: клон приёмки (PACKAGE, СВОЙ временный клон) не тронут ВЫЗОВАМИ update-tools.py ----")
# Суд разницей состояния здесь законен и остаётся (карточка #804): клон свой, лежит в своём
# временном каталоге, пишет в него только эта приёмка — соседей нет по построению.
pack_after = pack_state()
case("контроль: клон приёмки тот же, что был ПОСЛЕ подготовки истории приёмкой (сам "
    "update-tools.py в него ни разу не написал: git log/show/rev-parse — только чтение)",
    pack_after == PACK_READY_STATE,
    f"после подготовки: {PACK_READY_STATE[0][:12]} · разница {PACK_READY_STATE[2]}\n"
    f"   сейчас:         {pack_after[0][:12]} · разница {pack_after[2]}")

UNCHECKED = 0


def control(name, outcome, said, reference):
    """Контроль с тремя исходами: прошёл · провален · НЕ ПРОВЕРЕНО — свой знак и свой счёт."""
    global UNCHECKED
    if outcome == "unknown":
        UNCHECKED += 1
        print(f"⏳ {name}: НЕ ПРОВЕРЕНО")
        print(f"   {said}; «следов нет» НЕ утверждается\n   {reference}")
    else:
        case(name, outcome == "clean", f"{said}\n   {reference}")


def state_words(state) -> str:
    if state is None:
        return "снять не удалось"
    if TEMPLATE_IS_REPOSITORY:
        lines = len(state[1].splitlines())
        return f"HEAD {state[0][:12]} · status: " + (f"строк {lines}" if lines else "пусто")
    return f"{state[0]} · {state[1]}"


def method_words(broken: bool) -> str:
    return ("способ: по своим следам, поверх — прежний суд по разнице состояния (нарочная поломка) — "
            if broken else "способ: по своим следам — ")


print("---- контроль (ВТОРОЙ ВОЗВРАТ, карточка #609): ОБРАЗЕЦ (template_root) не тронут ----")
# Суд ПО СВОИМ СЛЕДАМ (карточка #804), а не по разнице состояния: образец в живом контуре — общий
# клон пакета, HEAD и status в нём двигает любой честный commit соседа, а свой commit на боковой
# ветке они не покажут вовсе. HEAD и status (у выгрузки — отпечаток файлов) печатаются справкой.
try:
    TEMPLATE_AFTER = template_state(TEMPLATE_ROOT)
except OSError:
    TEMPLATE_AFTER = None
outcome, names, why = template_verdict(TEMPLATE_ROOT, TEMPLATE_TRACES_BEFORE, TEMPLATE_BEFORE)
control("контроль: образец (template_root) этим прогоном не тронут — ни своим клонированием, ни "
        "коммитами приёмки, ни вызовами update-tools.py (суд по своим следам: commit под адресом "
        "автора с номером прогона, файл с меткой прогона)",
        outcome,
        method_words(BREAK == "state-template") + trace_words(outcome, names, why, *TEMPLATE_WORDS),
        "справка, не суд: состояние образца "
        + ("совпало" if TEMPLATE_AFTER == TEMPLATE_BEFORE
           else "ИЗМЕНИЛОСЬ (так бывает и от честного commit соседа)")
        + f" — было {state_words(TEMPLATE_BEFORE)}; стало {state_words(TEMPLATE_AFTER)}")

print("---- встречные случаи суда по своим следам в образце (карточка #804): свой каталог-подставка ----")
NEIGHBOUR = ("-c", "user.name=neighbour", "-c", "user.email=neighbour@local")
OWN_ID = ("-c", f"user.name={OWN_NAME}", "-c", f"user.email={OWN_EMAIL}")
judge = STAND / "judge-template"
(judge / "scripts").mkdir(parents=True)
git("init", "-q", cwd=judge)
(judge / "scripts" / "tool.py").write_bytes(b"print('tool')\n")
git("add", "-A", cwd=judge)
git(*NEIGHBOUR, "commit", "-q", "-m", "neighbour: first", cwd=judge)
j_traces, j_state = template_traces(judge), template_state(judge)

# образец-а: сосед коммитит, правит рабочую копию и кладёт СВОЙ файл с именем, как у приёмки
(judge / "scripts" / "tool.py").write_bytes(b"print('tool, edited by a neighbour')\n")
git("add", "-A", cwd=judge)
git(*NEIGHBOUR, "commit", "-q", "-m", "neighbour: second", cwd=judge)
(judge / "scripts" / "merge-A.py").write_bytes(b"# a neighbour's file, same name, no run mark\n")
outcome, names, why = template_verdict(judge, j_traces, j_state)
j_moved = template_state(judge) != j_state
case("образец-а ВСТРЕЧНЫЙ: чужой commit и чужая правка образца за время прогона случай НЕ роняют",
     outcome == "clean" and j_moved,
     f"сосед: commit, правка файла и свой файл scripts/merge-A.py без метки прогона; состояние "
     f"каталога изменилось: {'да' if j_moved else 'НЕТ'}; суд: "
     + trace_words(outcome, names, why, *TEMPLATE_WORDS))

# образец-б: свои следы по одному; каждый шаг обязан назвать ровно накопленное
j_steps = []
(judge / "scripts" / "merge-B.py").write_bytes(RUN_NONCE + b"line of the acceptance\n")
j_steps.append(("файл с меткой прогона в рабочей копии", template_verdict(judge, j_traces, j_state), 1, 0))
git("add", "scripts/merge-B.py", cwd=judge)
git(*OWN_ID, "commit", "-q", "-m", "bite609: свой commit в образце", cwd=judge)
j_steps.append(("commit под своим адресом", template_verdict(judge, j_traces, j_state), 1, 1))
side_state = template_state(judge)
side_tree = git("rev-parse", "HEAD^{tree}", cwd=judge).stdout.strip()
side_commit = git(*OWN_ID, "commit-tree", side_tree, "-p", "HEAD", "-m",
                  "bite609: свой commit на боковой ветке", cwd=judge).stdout.strip()
git("update-ref", "refs/heads/side", side_commit, cwd=judge)
j_steps.append(("commit на боковой ветке", template_verdict(judge, j_traces, j_state), 1, 2))
side_same = template_state(judge) == side_state
j_bad = [label for label, (o, n, _), files, commits in j_steps
         if not (o == "traces" and sum(x.startswith("файл ") for x in n) == files
                 and sum(x.startswith("commit ") for x in n) == commits)]
case("образец-б ВСТРЕЧНЫЙ: свой след в образце случай РОНЯЕТ и назван поимённо",
     not j_bad and side_same,
     f"шагов {len(j_steps)}; на последнем: {trace_words(*j_steps[-1][1], *TEMPLATE_WORDS)}"
     + (f" · НЕ ТО на шагах: {j_bad}" if j_bad else "")
     + f"\n   третий след — commit на боковой ветке: HEAD и status при нём "
       f"{'те же, суд по разнице состояния его не увидел бы' if side_same else 'ИЗМЕНИЛИСЬ'}")

# образец-в: каталога нет — третий исход, свои слова и свой код выхода
gone = STAND / "no-such-template"
g_verdict = template_verdict(gone, template_traces(gone), None)
g_words = trace_words(*g_verdict, *TEMPLATE_WORDS)
codes = (mezo_stand.exit_code3(0, 0), mezo_stand.exit_code3(1, 0), mezo_stand.exit_code3(0, 1))
case("образец-в ВСТРЕЧНЫЙ: образец недоступен — третий исход «НЕ ПРОВЕРЕНО»: свои слова и свой код, "
     "не «следов нет»",
     g_verdict[0] == "unknown" and "НЕ ПРОВЕРЕНО" in g_words and "следов в" not in g_words
     and "НЕ ПРОВЕРЕНО" not in trace_words("clean", [], "", *TEMPLATE_WORDS)
     and len(set(codes)) == 3 and codes[2] == 2,
     f"суд: {g_words}; коды (следов нет / следы есть / не проверено): {codes}")

# образец-г: свои следы в СВОЁМ клоне находятся — вопрос к образцу не слеп
own_found = template_traces(PACKAGE)[0]
lost = [h for h in OWN_COMMITS if not any(name.startswith(f"commit {h} ") for name in (own_found or {}))]
files_found = sum(name.startswith("файл ") for name in (own_found or {}))
case("образец-г ВСТРЕЧНЫЙ: свои следы в своём клоне находятся все — вопрос к образцу не слеп",
     own_found is not None and bool(OWN_COMMITS) and not lost and files_found > 0,
     f"своих коммитов {len(OWN_COMMITS)}, найдено {len(OWN_COMMITS) - len(lost)}; файлов с меткой "
     f"прогона {files_found}" + (f" · НЕ НАЙДЕНЫ: {', '.join(lost)}" if lost else ""))

print("---- контроль: meta ЖИВОГО контура не тронута ----")
# Суд ПО СВОИМ СЛЕДАМ (карточка #804), а не по разнице ключей: meta живого контура пишет установка
# и обновление инструментов — честная запись соседа за время прогона меняла ключи и роняла случай.
live_after = read_meta(LIVE_DB)
if LIVE_META_BEFORE is None or live_after is None:
    meta_reference = "справка, не суд: сравнить meta по ключам не удалось — база не ответила"
else:
    changed = sorted(k for k in set(LIVE_META_BEFORE) | set(live_after)
                     if LIVE_META_BEFORE.get(k) != live_after.get(k))
    meta_reference = ("справка, не суд: по ключам meta " + (
        "не изменилась" if not changed else
        "ИЗМЕНИЛАСЬ — " + ", ".join(changed) + " (так бывает и от честной установки инструментов)"))
outcome, names, why = meta_verdict(LIVE_DB, LIVE_TRACES_BEFORE, LIVE_META_BEFORE)
control("контроль: meta ЖИВОГО контура этим прогоном не тронута (суд по своим следам: путь своего "
        "стенда, свои версии пакета и отпечатки своих файлов в значениях meta)",
        outcome,
        method_words(BREAK == "state-meta") + trace_words(outcome, names, why, *META_WORDS),
        meta_reference)

print("---- встречные случаи суда по своим следам в meta (карточка #804): своя база-подставка ----")
SET_META = ("INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
judge_db = STAND / "judge-meta.db"
jc = sqlite3.connect(str(judge_db))
jc.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
for k, v in (("template_source", "каталог пакета соседа"), ("template_commit", "0123456789ab"),
             ("template_files_sha", json.dumps({"tool.py": "aaaaaaaaaaaa"}))):
    jc.execute(SET_META, (k, v))
jc.commit()
m_traces, m_state = meta_traces(judge_db), read_meta(judge_db)

# meta-а: сосед ставит инструменты — меняются версия пакета и отпечатки
jc.execute(SET_META, ("template_commit", "ba9876543210"))
jc.execute(SET_META, ("template_files_sha",
                      json.dumps({"tool.py": "bbbbbbbbbbbb", "new.py": "cccccccccccc"})))
jc.commit()
outcome, names, why = meta_verdict(judge_db, m_traces, m_state)
m_moved = read_meta(judge_db) != m_state
case("meta-а ВСТРЕЧНЫЙ: чужая запись в meta за время прогона (установка инструментов соседом) "
     "случай НЕ роняет",
     outcome == "clean" and m_moved,
     f"сосед сменил версию пакета и отпечатки; ключи изменились: {'да' if m_moved else 'НЕТ'}; суд: "
     + trace_words(outcome, names, why, *META_WORDS))

# meta-б: свои следы по одному; каждый шаг обязан назвать ровно накопленные ключи
m_steps = []
jc.execute(SET_META, ("template_source", str(PACKAGE)))
jc.commit()
m_steps.append(("источник — путь своего клона", meta_verdict(judge_db, m_traces, m_state),
                {"template_source"}))
jc.execute(SET_META, ("template_commit", OWN_COMMITS[-1]))
jc.commit()
m_steps.append(("версия пакета из своего клона", meta_verdict(judge_db, m_traces, m_state),
                {"template_source", "template_commit"}))
jc.execute(SET_META, ("template_files_sha",
                      json.dumps({"tool.py": "bbbbbbbbbbbb", "merge-C.py": sorted(OWN_FINGERPRINTS)[0]})))
jc.commit()
m_steps.append(("отпечаток своего файла внутри большого значения",
                meta_verdict(judge_db, m_traces, m_state),
                {"template_source", "template_commit", "template_files_sha"}))
jc.close()
m_bad = [label for label, (o, n, _), want in m_steps
         if not (o == "traces" and {x.split(" ← ")[0].removeprefix("meta.") for x in n} == want)]
case("meta-б ВСТРЕЧНЫЙ: свой след в meta случай РОНЯЕТ и назван поимённо",
     not m_bad,
     f"шагов {len(m_steps)}; на последнем: {trace_words(*m_steps[-1][1], *META_WORDS)}"
     + (f" · НЕ ТО на шагах: {m_bad}" if m_bad else ""))

# meta-в: база недоступна — файла нет · файл не база · в базе нет таблицы meta
gone_db, junk_db, bare_db = STAND / "no-such-meta.db", STAND / "junk-meta.db", STAND / "bare-meta.db"
junk_db.write_bytes("это не база данных, а просто текст".encode("utf-8") * 8)
sqlite3.connect(str(bare_db)).close()
blind = {p.name: meta_verdict(p, meta_traces(p), None) for p in (gone_db, junk_db, bare_db)}
blind_words = [trace_words(*r, *META_WORDS) for r in blind.values()]
case("meta-в ВСТРЕЧНЫЙ: база недоступна — третий исход «НЕ ПРОВЕРЕНО»: свои слова и свой код, "
     "не «следов нет»",
     all(r[0] == "unknown" for r in blind.values())
     and all("НЕ ПРОВЕРЕНО" in w and "следов в" not in w for w in blind_words)
     and "НЕ ПРОВЕРЕНО" not in trace_words("clean", [], "", *META_WORDS)
     and len(set(codes)) == 3 and codes[2] == 2,
     "исходы: " + ", ".join(f"{k}→{v[0]}" for k, v in blind.items())
     + f"; коды (следов нет / следы есть / не проверено): {codes}")

# meta-г: свои метки в meta контуров стенда находятся — вопрос к живой meta не слеп
kinds = [kind for kind, _ in own_meta_marks()]
seen_kinds = set()
for one in CIRCUIT_DBS:
    for name in (meta_traces(one)[0] or {}):
        seen_kinds.update(kind for kind in kinds if f" ← {kind} " in name)
lost_kinds = [kind for kind in kinds if kind not in seen_kinds]
case("meta-г ВСТРЕЧНЫЙ: свои метки в meta контуров стенда находятся все — вопрос к живой meta не слеп",
     bool(CIRCUIT_DBS) and not lost_kinds,
     f"видов меток {len(kinds)}, найдено на стенде {len(kinds) - len(lost_kinds)} "
     f"(контуров стенда {len(CIRCUIT_DBS)})"
     + (f" · НЕ НАЙДЕНЫ: {', '.join(lost_kinds)}" if lost_kinds else ""))

if BREAK:
    confirmed = len(FAILED) == 1 and FAILED[0].startswith(BREAKS[BREAK] + " ")
    print(f"⚖️ прогноз нарочной поломки «{BREAK}» "
          + ("ПОДТВЕРДИЛСЯ: провален ровно встречный случай «" + BREAKS[BREAK] + "»" if confirmed
             else f"НЕ подтвердился: провалено случаев {len(FAILED)}"))
    if confirmed:
        mezo_stand.expected_break()
if UNCHECKED:
    print(f"⏳ НЕ ПРОВЕРЕНО: {UNCHECKED} — на вопрос о своих следах ответа не было; прогон выходит "
          "кодом 2, а не «прошёл»")
print(f"\n{'🔴' if FAIL else ('⏳' if UNCHECKED else '✅')} ИТОГ (с контролем): {OK} из {OK + FAIL}")
if not FAIL and UNCHECKED:
    # Случаи приняты, не проверен только контроль: в стенде разбирать нечего, а в нём лежит
    # целый клон пакета — объявляем пропуск, чтобы стенд не хранился как отказ мерить (карточка #729).
    mezo_stand.accepted_with_skips()
sys.exit(mezo_stand.finish(mezo_stand.exit_code3(FAIL, UNCHECKED)))
