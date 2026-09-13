#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-update-tools-rev.py — приёмка карточки #604 ②③: update-tools.py умеет взять РОВНО
названную версию источника (--rev), не подменяет источник контура молча, и у «❓»-файлов
называет дату и коммит последнего совпадения с историей пакета.

ПОВОД. Заявка @tapas после апгрейда v4→v6, три находки контура-потребителя:
  ② сосед дал `--source <локальная папка>`, чтобы взять ПРОВЕРЕННУЮ версию пакета — и
    meta.template_source контура МОЛЧА стала указывать на чужую машину, хотя источник
    уже был записан (общий репозиторий). Разово названный --source не имеет права
    становиться постоянной записью без отдельного слова.
  ③ у шести файлов «❓ отпечатка установки нет» простояло на пакете 20.08 ПОЧТИ МЕСЯЦ,
    и строка «❓» не читалась как «застряли»: без даты неизвестно, вчера это или месяц назад.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ (случаи):
  ② --rev берёт названную версию, а не HEAD/latest
  ② source в meta НЕ меняется без --record-source (разовый --source не становится записью)
  ② встречный: --record-source МЕНЯЕТ источник в meta — слово дано явно
  ③ у «❓» печатается дата и коммит ПОСЛЕДНЕГО совпадения с историей источника
  ③ встречный: содержимого нет в истории пакета вовсе — сказано так, а не выдумана дата
  ⑥ КОНТРОЛЬ нарочной поломкой: сломанная копия (--rev молча игнорируется) красит РОВНО
    случаи --rev и не трогает случай ③ (он от --rev не зависит) — иначе приёмка ловила бы
    что угодно, а не то, что называет своим предметом.

ИСПЫТУЕТСЯ через mezo_target (живой контур или MEZO_SCRIPTS_ROOT — копия для укуса).
ПАКЕТ — ЛОКАЛЬНАЯ КОПИЯ <ШАБЛОН>, ТОЛЬКО ЧТЕНИЕ: git log/show/archive/worktree
во временный каталог; ни файлов, ни веток, ни git checkout пакета эта приёмка не трогает —
для подмены версии в стенде используется git archive, как и в самом update-tools.py.

    python <КОНТУР>/vnext-tools/bite-update-tools-rev.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("update-tools.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

# Рабочая копия пакета — ТОЛЬКО ЧТЕНИЕ. Путь выводится, а не пишется: у потребителя пакет
# лежит в другом месте, а в образце приёмка живёт внутри самого пакета (MEZO_TEMPLATE /
# local.paths / подъём до scripts/init-group.py — см. mezo_paths.template_root).
PACKAGE = mezo_paths.template_root(__file__)
INIT = PACKAGE / "scripts" / "init-group.py"


def pack_state() -> tuple[str, str, str]:
    """Состояние рабочей копии пакета: HEAD · `git status --short` · отпечаток `git diff HEAD`."""
    def git(*args) -> bytes:
        return subprocess.run(["git", "-C", str(PACKAGE), *args], capture_output=True).stdout
    return (git("rev-parse", "HEAD").decode().strip(),
            git("status", "--short").decode("utf-8", "replace").strip(),
            hashlib.sha256(git("diff", "HEAD", "--binary")).hexdigest()[:12])


# 🪤 Контроль «пакет не тронут» сравнивает ДО и ПОСЛЕ, а не требует пустоты: рабочая копия
# может нести чужую незакоммиченную работу (например, перенос в пакет, идущий прямо сейчас),
# и это не след приёмки. Прежняя форма «status пуст» красила именно её — поймано прогоном
# PROTO 13.09 посреди переноса. Отпечаток разницы ловит и повторную правку уже изменённого.
PACK_BEFORE = pack_state()


def live_meta() -> dict:
    """meta ЖИВОГО контура, только чтение: приёмка обязана его не менять (см. stand_env)."""
    c = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    m = dict(c.execute("SELECT key, value FROM meta"))
    c.close()
    return m


LIVE_META_BEFORE = live_meta()

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").rstrip()


def git_show(rev: str, rel: str) -> bytes:
    r = subprocess.run(["git", "-C", str(PACKAGE), "show", f"{rev}:{rel}"], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: git show {rev}:{rel} в {PACKAGE} не удался — "
                 "пакету нечем поставить приёмку")
    return r.stdout


def make_contour(root: pathlib.Path, under_test: pathlib.Path) -> pathlib.Path:
    """Свежий контур из ПАКЕТА, с испытуемым update-tools.py (и соседями) НА МЕСТЕ шаблонного.

    🪤 ПОЧЕМУ КОПИРУЕМ TARGET ВНУТРЬ, А НЕ ЗОВЁМ ЕГО СНАРУЖИ С --db/MEZO_CONTAINER:
    update-tools.py находит СВОЙ контур через mezo_paths, а mezo_paths резолвится от
    РАСПОЛОЖЕНИЯ ЗАПУЩЕННОГО ФАЙЛА (второй замок, R15a). Позвать живой update-tools.py
    снаружи с чужим --db означало бы читать БД стенда, но ПИСАТЬ в живые .mezosync/scripts —
    ровно та беда, от которой mezo_target.py и заведён (bite-self-update.py решает это так
    же: испытуемый копируется В свежий контур, а не зовётся из живого места).
    """
    db_dir = root / ".mezosync"
    r = subprocess.run([sys.executable, str(INIT), "--name", "bite604", "--path", str(db_dir),
                       "--roles", "COORD"], capture_output=True, text=True, timeout=300,
                      encoding="utf-8", errors="replace", env=stand_env(root))
    if r.returncode != 0:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: свежий контур не собрался:\n" + (r.stdout or "") + (r.stderr or ""))
    mezo_stand.copy_tool(under_test, db_dir / "scripts")   # испытуемый + соседи — ПОВЕРХ шаблонного
    return db_dir


def stand_env(container: pathlib.Path) -> dict:
    """Среда для всего, что запускается на стенде: контейнер — САМ стенд, а не среда вызывающего.

    🩸 НАЙДЕНО PROTO 13.09 прогоном копии из образца с MEZO_CONTAINER живого контура: среда
    наследовалась испытуемым, mezo_paths берёт контейнер ИЗ СРЕДЫ раньше, чем от расположения
    файла, — и --apply стенда записал meta ЖИВОГО контура (источник и версию). Файлы
    инструментов не тронуты только потому, что у живого контура нет отпечатков установки.
    """
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_CONTAINER=str(container))


def run(tool: pathlib.Path, *extra, timeout=180):
    env = stand_env(tool.resolve().parents[2])   # …/<стенд>/.mezosync/scripts/<инструмент>
    p = subprocess.run([sys.executable, str(tool), *extra], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def meta_of(db: pathlib.Path) -> dict:
    c = sqlite3.connect(str(db))
    m = dict(c.execute("SELECT key, value FROM meta"))
    c.close()
    return m


def drop_fingerprints(db: pathlib.Path, *names: str) -> None:
    c = sqlite3.connect(str(db))
    sha = json.loads(dict(c.execute(
        "SELECT key, value FROM meta WHERE key='template_files_sha'")).get("template_files_sha")
        or "{}")
    for n in names:
        sha.pop(n, None)
    c.execute("UPDATE meta SET value=? WHERE key='template_files_sha'",
             (json.dumps(sha, ensure_ascii=False),))
    c.commit()
    c.close()


# ═══ ВЫБОР СТАРОГО КОММИТА — ЗАМЕРОМ ПО ИСТОРИИ ПАКЕТА, А НЕ ВПИСАН РУКОЙ: вписанный хеш
# протухнет, как только история пакета продвинется настолько, что он выпадет из окна
# (или, наоборот, совпадёт с HEAD после сквош-мержа) — и приёмка станет краснить или
# зеленеть не по своей причине.
_log = subprocess.run(["git", "-C", str(PACKAGE), "log", "--format=%H", "--",
                       "scripts/backlog.py"], capture_output=True, text=True)
_hist = [h for h in (_log.stdout or "").splitlines() if h.strip()]
if len(_hist) < 8:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: у scripts/backlog.py в {PACKAGE} меньше 8 редакций в истории "
             f"({len(_hist)}) — приёмке не на чем стоять")
OLD_REV = _hist[7]                                    # заведомо старше HEAD на 7+ редакций
HEAD_CONTENT = git_show("HEAD", "scripts/backlog.py")
OLD_CONTENT = git_show(OLD_REV, "scripts/backlog.py")
if norm(HEAD_CONTENT) == norm(OLD_CONTENT):
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: выбранный старый коммит не отличается от HEAD — "
             "случай ② не будет различающим")
OLD_DATE = subprocess.run(["git", "-C", str(PACKAGE), "log", "-1", "--format=%as", OLD_REV],
                          capture_output=True, text=True).stdout.strip()

stand = mezo_stand.new("bite-604-rev-")

# ═══ ② --rev берёт названную версию (не HEAD) + source в meta не меняется без слова
t1 = stand / "t1"
db1_dir = make_contour(t1, TARGET)
db1 = db1_dir / "mezosync.db"
upd1 = db1_dir / "scripts" / "update-tools.py"
meta_before = meta_of(db1)

rc1, out1 = run(upd1, "--source", str(PACKAGE), "--rev", OLD_REV, "--apply")
consumer_backlog = db1_dir / "scripts" / "backlog.py"
took_old = consumer_backlog.exists() and norm(consumer_backlog.read_bytes()) == norm(OLD_CONTENT)
case("② --rev берёт названную версию, а не HEAD/latest",
     rc1 == 0 and took_old, f"код {rc1} · содержимое = версии {OLD_REV[:12]}: {took_old}")

meta_after = meta_of(db1)
case("② source в meta НЕ меняется от разового --source без --record-source",
     meta_after.get("template_source") == meta_before.get("template_source")
     and meta_after.get("template_source") != str(PACKAGE),
     f"было {meta_before.get('template_source')} · стало {meta_after.get('template_source')}")

# 🪤 Первый --apply взял СТАРУЮ версию пакета — и вместе с ней мог заменить сам update-tools.py
# стенда, если его отпечаток совпал с установленным (так бывает, когда испытуемый уже лежит
# в пакете). Второй прогон тогда шёл бы старым инструментом без --record-source. Возвращаем
# испытуемого на место — поймано PROTO 13.09 сразу после переноса в пакет.
mezo_stand.copy_tool(TARGET, db1_dir / "scripts")
rc1b, out1b = run(upd1, "--source", str(PACKAGE), "--rev", OLD_REV, "--record-source", "--apply")
meta_after2 = meta_of(db1)
case("② встречный: --record-source МЕНЯЕТ источник в meta — слово дано явно",
     rc1b == 0 and meta_after2.get("template_source") == str(PACKAGE),
     f"стало {meta_after2.get('template_source')}")

# ═══ ③ у «❓» — дата и коммит последнего совпадения; встречный — «нет в истории»
t2 = stand / "t2"
db2_dir = make_contour(t2, TARGET)
db2 = db2_dir / "mezosync.db"
upd2 = db2_dir / "scripts" / "update-tools.py"

(db2_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
ghost_marker = ("# УНИКАЛЬНАЯ ПОДСТАВА bite-update-tools-rev, которой в истории пакета не будет: "
        + hashlib.sha256(os.urandom(16)).hexdigest() + "\n")
(db2_dir / "scripts" / "write-message.py").write_text(ghost_marker, encoding="utf-8")
drop_fingerprints(db2, "backlog.py", "write-message.py")

rc2, out2 = run(upd2, "--source", str(PACKAGE))
case("③ у «❓» печатается дата и коммит ПОСЛЕДНЕГО совпадения с историей источника",
     rc2 == 0 and f"коммит {OLD_REV[:12]}" in out2 and OLD_DATE in out2
     and "backlog.py" in out2.split(f"коммит {OLD_REV[:12]}")[0].splitlines()[-1],
     f"код {rc2} · ищем «{OLD_DATE}, коммит {OLD_REV[:12]}» рядом с backlog.py")
case("③ встречный: содержимого нет в истории пакета — сказано так, а не выдумана дата",
     rc2 == 0 and "в истории пакета такого содержимого нет" in out2
     and "write-message.py" in out2.split("в истории пакета такого содержимого нет")[0]
         .splitlines()[-1],
     f"код {rc2}")

# ═══ ⑥ КОНТРОЛЬ нарочной поломкой: --rev молча игнорируется (rev=a.rev → rev=None)
# 🩸 БЕЗ ЭТОГО СЛУЧАЯ приёмка могла бы зеленеть по СЛУЧАЙНОЙ причине (например, если бы
# --rev тихо не долетал до fetch()). Ломаем РОВНО эту строку и смотрим, что покраснеет:
# должны покраснеть ОБА случая ②, завязанных на --rev, и НИ ОДИН случай ③ — он от --rev
# не зависит вовсе, и его зелёный цвет обязан остаться зелёным.
broken_dir = stand / "broken"
broken_tool = mezo_stand.copy_tool(TARGET, broken_dir)
original_text = broken_tool.read_text(encoding="utf-8")
broken_text = original_text.replace("fetch(source, rev=a.rev)", "fetch(source, rev=None)")
if broken_text == original_text:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка для поломки «fetch(source, rev=a.rev)» не найдена в "
             "испытуемом — переименовали аргумент, поломка бьёт мимо")
broken_tool.write_text(broken_text, encoding="utf-8")

t3 = stand / "t3"
db3_dir = make_contour(t3, broken_tool)
db3 = db3_dir / "mezosync.db"
upd3 = db3_dir / "scripts" / "update-tools.py"
meta3_before = meta_of(db3)
rc3, out3 = run(upd3, "--source", str(PACKAGE), "--rev", OLD_REV, "--apply")
consumer_backlog3 = db3_dir / "scripts" / "backlog.py"
broken_took_old = (consumer_backlog3.exists()
                        and norm(consumer_backlog3.read_bytes()) == norm(OLD_CONTENT))
case("⑥ поломка (--rev игнорируется) КРАСИТ случай «--rev берёт названную версию»",
     not broken_took_old,
     f"сломанный инструмент {'ВСЁ РАВНО взял старую версию (поломка НЕ сработала)' if broken_took_old else 'взял HEAD вместо старой версии — поломка сработала, как и предсказано'}")

t4 = stand / "t4"
db4_dir = make_contour(t4, broken_tool)
db4 = db4_dir / "mezosync.db"
upd4 = db4_dir / "scripts" / "update-tools.py"
(db4_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
(db4_dir / "scripts" / "write-message.py").write_text(ghost_marker, encoding="utf-8")
drop_fingerprints(db4, "backlog.py", "write-message.py")
rc4, out4 = run(upd4, "--source", str(PACKAGE))
case("⑥ та же поломка НЕ трогает случай ③ (он от --rev не зависит)",
     rc4 == 0 and f"коммит {OLD_REV[:12]}" in out4
     and "в истории пакета такого содержимого нет" in out4,
     f"код {rc4} — ③ обязан остаться зелёным при поломке, которая бьёт только --rev")

print("---- контроль: рабочая копия пакета не тронута ----")
pack_after = pack_state()
case("контроль: рабочая копия пакета та же, что до приёмки — приёмка ничего в ней не изменила",
     pack_after == PACK_BEFORE,
     f"до: {PACK_BEFORE[0][:12]} · разница {PACK_BEFORE[2]} · {PACK_BEFORE[1][:160] or '(чисто)'}\n"
     f"   после: {pack_after[0][:12]} · разница {pack_after[2]} · {pack_after[1][:160] or '(чисто)'}")
live_after = live_meta()
changed = sorted(k for k in set(LIVE_META_BEFORE) | set(live_after)
                 if LIVE_META_BEFORE.get(k) != live_after.get(k))
case("контроль: meta живого контура не изменилась — стенд писал только в себя",
     not changed, "изменились ключи: " + (", ".join(changed) or "нет"))

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
