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

Два контроля внизу файла, независимых:
  · «клон приёмки не тронут ВЫЗОВАМИ update-tools.py» — HEAD/status/diff СВОЕГО клона
    сравниваются ДО первого вызова update-tools.py (после того, как приёмка сама закончила
    готовить историю) и ПОСЛЕ всех вызовов;
  · «образец не тронут» — HEAD и `git status --porcelain` у САМОГО template_root снимаются
    ДО любого действия приёмки (до клонирования тоже) и сравниваются в самом конце: образец
    не должен измениться НИ ОДНИМ байтом за весь прогон, включая собственное клонирование.

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


def template_state(root) -> tuple[str, str]:
    """HEAD + `git status --porcelain` образца (template_root) — снимок для контроля
    «образец не тронут» (ВТОРОЙ ВОЗВРАТ, карточка #609). Читает только, ничего не пишет."""
    def g(*a) -> bytes:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True).stdout
    return (g("rev-parse", "HEAD").decode().strip(),
           g("status", "--porcelain").decode("utf-8", "replace").strip())


# ⛔ ВТОРОЙ ВОЗВРАТ (карточка #609): снимок берётся ДО ЛЮБОГО действия этой приёмки — раньше
# собственного клонирования тоже. Сравнение — в самом конце файла (контроль «образец не тронут»).
TEMPLATE_ROOT = mezo_paths.template_root(__file__)
TEMPLATE_BEFORE = template_state(TEMPLATE_ROOT)

STAND = mezo_stand.new("bite-609-merge-")

# ⛔ ВТОРОЙ ВОЗВРАТ (карточка #609, безопасность): PACKAGE — СВОЙ клон TEMPLATE_ROOT внутри
# СВОЕГО временного каталога, а не сам образец. Прежде PACKAGE = TEMPLATE_ROOT напрямую, и
# без MEZO_TEMPLATE это указывало на НАСТОЯЩИЙ клон пакета (через local.paths) — приёмка
# коммитила бы синтетические файлы для случаев ①–⑤ туда же. Клонирование — ЧТЕНИЕ образца
# (`git clone` не пишет в источник), коммиты ниже идут уже в клон.
PACKAGE = STAND / "pack"
_clone = subprocess.run(["git", "clone", "--no-hardlinks", str(TEMPLATE_ROOT), str(PACKAGE)],
                        capture_output=True, text=True)
if _clone.returncode != 0:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: свой клон образца ({TEMPLATE_ROOT}) в стенд ({PACKAGE}) "
             f"отказал: {_clone.stderr.strip()[:300]}")

RFP_TOOL_PATH = PACKAGE / "scripts" / "rules-from-pack.py"   # копируем, только если есть — не обязателен этим случаям

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


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


def live_meta() -> dict:
    c = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    m = dict(c.execute("SELECT key, value FROM meta"))
    c.close()
    return m


LIVE_META_BEFORE = live_meta()


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
    git("-c", "user.name=bite609", "-c", "user.email=bite609@local",
       "commit", "-q", "-m", message)
    return git("rev-parse", "HEAD").stdout.strip()[:12]


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
RUN_NONCE = f"# bite609 прогон {os.urandom(4).hex()}\n".encode("utf-8")
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

PACK_READY_STATE = pack_state()   # с этой точки update-tools.py САМ пакет больше не меняет


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


print()
print(f"{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")

print("---- контроль: клон приёмки (PACKAGE, СВОЙ временный клон) не тронут ВЫЗОВАМИ update-tools.py ----")
pack_after = pack_state()
case("контроль: клон приёмки тот же, что был ПОСЛЕ подготовки истории приёмкой (сам "
    "update-tools.py в него ни разу не написал: git log/show/rev-parse — только чтение)",
    pack_after == PACK_READY_STATE,
    f"после подготовки: {PACK_READY_STATE[0][:12]} · разница {PACK_READY_STATE[2]}\n"
    f"   сейчас:         {pack_after[0][:12]} · разница {pack_after[2]}")

print("---- контроль (ВТОРОЙ ВОЗВРАТ, карточка #609): ОБРАЗЕЦ (template_root) не тронут ----")
TEMPLATE_AFTER = template_state(TEMPLATE_ROOT)
case("контроль: образец (template_root) не изменился НИ БАЙТОМ за весь прогон — ни своим "
    "клонированием, ни коммитами приёмки, ни вызовами update-tools.py (HEAD и "
    "status --porcelain сняты ДО первого действия и сравнены сейчас)",
    TEMPLATE_AFTER == TEMPLATE_BEFORE,
    f"было:  HEAD {TEMPLATE_BEFORE[0][:12]} · status «{TEMPLATE_BEFORE[1] or 'пусто'}»\n"
    f"   стало: HEAD {TEMPLATE_AFTER[0][:12]} · status «{TEMPLATE_AFTER[1] or 'пусто'}»")

live_after = live_meta()
changed = sorted(k for k in set(LIVE_META_BEFORE) | set(live_after)
                 if LIVE_META_BEFORE.get(k) != live_after.get(k))
case("контроль: meta ЖИВОГО контура не изменилась (сравнение по ключам, не по отпечатку "
    "всего файла базы — его меняют записки других ролей)",
    not changed, "изменились ключи: " + (", ".join(changed) or "нет"))

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ (с контролем): {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
