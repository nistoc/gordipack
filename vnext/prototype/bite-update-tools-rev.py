#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-update-tools-rev.py — приёмка карточки #604 ②③: update-tools.py умеет взять РОВНО
названную версию источника (--rev), не подменяет источник контура молча, и у «❓»-файлов
честно называет, когда версия появилась и когда пакет её сменил (или что истории нет вовсе).

ПОВОД. Заявка @tapas после апгрейда v4→v6, три находки контура-потребителя:
  ② сосед дал `--source <локальная папка>`, чтобы взять ПРОВЕРЕННУЮ версию пакета — и
    meta.template_source контура МОЛЧА стала указывать на чужую машину, хотя источник
    уже был записан (общий репозиторий). Разово названный --source не имеет права
    становиться постоянной записью без отдельного слова.
  ③ у шести файлов «❓ отпечатка установки нет» простояло на пакете 20.08 ПОЧТИ МЕСЯЦ,
    и строка «❓» не читалась как «застряли»: без даты неизвестно, вчера это или месяц назад.

ВОЗВРАТ OPSSRE (приёмка чужой рукой нашла три беды в первой редакции этого же случая ③):
  ③-1 проверка «источник — git?» смотрела `(path / ".git").is_dir()` — ошибалась в обе
    стороны: 38/45 ложных на выгрузке без истории, 44/45 ложных на git WORKTREE (там `.git`
    ФАЙЛ, не каталог). Чинится спросом у git (`rev-parse --git-dir`), а не именем файла.
  ③-2 дата называла ПОСЛЕДНЕЕ совпадение (соседнюю со сменой), а не ПОЯВЛЕНИЕ версии —
    живой пример: mention.py появился 09.08, пакет держал его так до 05.09, «последнее
    совпадение» назвало бы 04.09. Подпись несёт ОБЕ даты: появления и следующей смены.
  ③-3 обещание «следующий прогон скажет определённо» было ложным: отпечаток пишется
    ТОЛЬКО взятым файлам, и «❓» без него остаются «❓» на всех следующих прогонах тоже.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ (случаи):
  ② --rev берёт названную версию, а не HEAD/latest
  ② source в meta НЕ меняется без --record-source (разовый --source не становится записью)
  ② встречный: --record-source МЕНЯЕТ источник в meta — слово дано явно
  ③ у «❓» печатается дата и коммит ПОЯВЛЕНИЯ версии (не последнего совпадения)
  ③-2 подпись несёт ОБЕ даты: появления и следующей смены («пакет сменил её»)
  ③ встречный: содержимого нет в истории пакета вовсе — сказано так, а не выдумана дата
  ③-3 после --apply без --overwrite-unknown — правда «останутся «❓»», не ложь «скажет
    определённо»; встречный — следующий план ДЕЙСТВИТЕЛЬНО показывает те же «❓»
  ③-1а источник-выгрузка без .git вовсе → «истории у источника нет», а не «нет в истории»
  ③-1б источник с `.git`-ФАЙЛОМ (как у git worktree) → история находится, а не теряется
  ③-1в источник — подкаталог ДРУГОГО git-репозитория (возврат OPSSRE №2) → «каталог внутри
    другого репозитория (<корень>)», а не «нет в истории» — `--git-dir` иначе находит ЧУЖОЙ
    .git выше по дереву и молча ищет не там
  ③-1г источник — репозиторий без единого коммита (граница OPSSRE, записка #5116) → «нет ни
    одного коммита», а не «нет в истории»
  ⑥ КОНТРОЛЬ нарочной поломкой: --rev молча игнорируется — красит РОВНО случаи --rev,
    не трогает случай ③ (он от --rev не зависит)
  ⑦ КОНТРОЛЬ нарочной поломкой: git-детект истории возвращён к `.is_dir()` — красит РОВНО
    ③-1б (там способ проверки и есть предмет разницы) и не трогает ③-1а (там оба способа
    честно отвечают одинаково)
  ⑧ КОНТРОЛЬ нарочной поломкой (возврат OPSSRE №2): снята ИМЕННО проверка `--show-prefix` —
    красит РОВНО ③-1в, не трогает ③-1а (git-dir отказывает раньше) и ③-1б (там prefix и
    так был пуст); красит СВОЕЙ причиной — возвращается ложное «нет в истории»
  ⑨ КОНТРОЛЬ нарочной поломкой: снята проверка «нет ни одного коммита» — красит РОВНО ③-1г
    (возвращается ложное «нет в истории»), не трогает ③-1б (там HEAD есть)
  ⑩ КАРТОЧКА #608, ШАГ 3: update-tools печатает строку о правилах пакета — «правила
    пакета: …» (источник с базой правил rules/pack-rules.db), «в пакете нет базы правил»
    (источник без неё), и в ПЛАНЕ, и после --apply; КОНТРОЛЬ нарочной поломкой — сняты
    оба вызова print_pack_rules_summary, красит РОВНО ⑩а, своей причиной (строка пропадает,
    а не меняется код выхода)
  ⑩г ВОЗВРАТ PROTO (карточка #608, шаг 3, повторная приёмка): инструмента rules-from-pack.py
    нет НИ у контура, НИ в источнике — сказано честно про ОБА места, а не «приедет
    обновлением» (та строка была бы ложью — обновление его не несёт); КОНТРОЛЬ нарочной
    поломкой — снято различение «источник несёт / не несёт», красит РОВНО ⑩г своей причиной

ИСПЫТУЕТСЯ через mezo_target (живой контур или MEZO_SCRIPTS_ROOT — копия для укуса).
ПАКЕТ — ЛОКАЛЬНАЯ КОПИЯ <ШАБЛОН>, ТОЛЬКО ЧТЕНИЕ: git log/show — команды на
чтение; ③-1б кладёт файл-указатель `.git` РЯДОМ С СОБОЙ (не в пакете, см.
make_worktree_like_source) — пакет ни разу не открывается на запись, что проверяет
контроль «пакет не тронут» в конце файла (HEAD · git status · отпечаток git diff, ДО/ПОСЛЕ).

    python <КОНТУР>/vnext-tools/bite-update-tools-rev.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("update-tools.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

# Помощник стенда — из СВОЕЙ папки приёмки (она уже в sys.path выше), а не из инструментов
# испытуемого контура: от испытуемого приёмке нужен только испытуемый инструмент (mezo_target).
# 🪤 Прежде mezo_stand брался из испытуемого контура — и приёмка падала на контуре, чьи
# инструменты старше неё (найдено OPSSRE 13.09 пробой с MEZO_CONTAINER на копию контура от
# 16:49 UTC; выбор PROTO — записка #5110).
import mezo_stand  # noqa: E402
if not hasattr(mezo_stand, "stand_env"):
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {mezo_stand.__file__} нет stand_env (общий помощник среды стенда, "
             "записка #5096) — помощник в папке приёмки старше неё; возьми оба файла из одной версии пакета")

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
    """meta ЖИВОГО контура, только чтение: приёмка обязана его не менять (см. mezo_stand.stand_env)."""
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


PACKAGE_GITDIR = subprocess.run(["git", "-C", str(PACKAGE), "rev-parse", "--absolute-git-dir"],
                                capture_output=True, text=True).stdout.strip()


def make_dump_source(dest: pathlib.Path, rel: str, content: bytes) -> None:
    """Возврат OPSSRE ③-1а: источник — ВЫГРУЗКА БЕЗ ИСТОРИИ (копия диска, не git вовсе).

    Только ЧТЕНИЕ пакета: содержимое кладётся сюда данными приёмки (`content`), не git archive
    из PACKAGE — так проще гарантировать РОВНО тот же байт-в-байт текст, что уйдёт в сравнение.
    """
    p = dest / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def make_worktree_like_source(dest: pathlib.Path, rel: str, content: bytes) -> None:
    """Возврат OPSSRE ③-1б: источник, у которого `.git` — ФАЙЛ, не каталог (как у git worktree).

    ⚖️ ВЫБОР ИЗ ДВУХ СПОСОБОВ, НАЗВАН ЯВНО (карточка #604 ③, OPSSRE предложил оба):
    `git worktree add` в PACKAGE добавил бы запись в PACKAGE/.git/worktrees — временную,
    но ЗАПИСЬ. Выбран способ БЕЗ единой записи в PACKAGE: файл `.git` кладётся ЗДЕСЬ,
    в `dest`, и указывает НАПРЯМУЮ на PACKAGE/.git (`gitdir: <путь>`) — git понимает эту
    форму (ровно так устроены worktree) и резолвит историю через неё, а сам PACKAGE/.git
    при этом НЕ ПОЛУЧАЕТ НИ ОДНОЙ новой записи: git log/show/rev-parse — команды ТОЛЬКО НА
    ЧТЕНИЕ, PACKAGE ни разу не открывается на запись. Проверено прогоном (см. контроль
    «пакет не тронут» в конце этого файла) и отдельно — командой руками перед правкой.
    """
    p = dest / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    (dest / ".git").write_text(f"gitdir: {PACKAGE_GITDIR}\n", encoding="utf-8")


def make_nested_repo_source(outer_repo: pathlib.Path, rel: str, content: bytes) -> pathlib.Path:
    """Возврат OPSSRE ③-1в: источник — подкаталог ДРУГОГО git-репозитория, НЕ его корень.

    `git init` — В НОВОМ временном каталоге (не в PACKAGE, не рядом): это ЧУЖОЙ репозиторий,
    существующий только ради этого случая, к пакету отношения не имеющий. Возвращает путь
    к ВЛОЖЕННОМУ подкаталогу (то, что уходит в --source), а не к корню чужого репозитория.

    ⚖️ ВЫБОР ПЕРЕСМОТРЕН (PROTO, 13.09, граница OPSSRE «репозиторий без коммитов», записка
    #5116): у чужого репозитория ЕСТЬ коммит — посторонний файл в его корне; вложенное
    содержимое НЕ коммитится (его нет в чужой истории). Прежде коммита не было, и это было
    безразлично: `--show-prefix` отвечает одинаково с историей и без. Но с проверкой «нет ни
    одного коммита» поломка ⑧ (снят `--show-prefix`) на пустом чужом репозитории упёрлась бы
    в неё и покраснела бы НЕ ПО СВОЕЙ причине — соседняя починка прикрыла бы её. С коммитом
    поломка ⑧ снова даёт свою ложь: ищет в ЧУЖОЙ истории и печатает «нет в истории».
    """
    subprocess.run(["git", "init", "-q", str(outer_repo)], check=True)
    (outer_repo / "README-outer.txt").write_text("чужой проект\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(outer_repo), "add", "README-outer.txt"], check=True)
    subprocess.run(["git", "-C", str(outer_repo), "-c", "user.name=bite", "-c", "user.email=bite@local",
                    "commit", "-q", "--no-verify", "-m", "outer"], check=True)
    nested = outer_repo / "nested" / "source"
    p = nested / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return nested


def make_empty_repo_source(dest: pathlib.Path, rel: str, content: bytes) -> pathlib.Path:
    """Граница OPSSRE (повтор ③-1, записка #5116): источник — КОРЕНЬ git-репозитория, в котором
    нет ни одного коммита. `--git-dir` и `--show-prefix` отвечают как у настоящего, история пуста.
    `git init` — в новом временном каталоге, к пакету отношения не имеющем."""
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    p = dest / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return dest


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
                      encoding="utf-8", errors="replace", env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"))
    if r.returncode != 0:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: свежий контур не собрался:\n" + (r.stdout or "") + (r.stderr or ""))
    mezo_stand.copy_tool(under_test, db_dir / "scripts")   # испытуемый + соседи — ПОВЕРХ шаблонного
    return db_dir


# Среда для всего, что запускается на стенде, — общий помощник mezo_stand.stand_env (записка #5096):
# контейнер — САМ стенд, а не среда вызывающего. Своя функция приёмки заменена им 13.09 (OPSSRE).
# 🩸 НАЙДЕНО PROTO 13.09 прогоном копии из образца с MEZO_CONTAINER живого контура: среда
# наследовалась испытуемым, mezo_paths берёт контейнер ИЗ СРЕДЫ раньше, чем от расположения
# файла, — и --apply стенда записал meta ЖИВОГО контура (источник и версию). Файлы
# инструментов не тронуты только потому, что у живого контура нет отпечатков установки.


def run(tool: pathlib.Path, *extra, timeout=180):
    env = mezo_stand.stand_env(tool.resolve().parents[2], PYTHONIOENCODING="utf-8")   # …/<стенд>/.mezosync/scripts/<инструмент>
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
CHANGED_REV = _hist[6]                                # СЛЕДУЮЩАЯ (более новая) правка того же пути —
                                                        # для случая ③-2 «пакет сменил её»
HEAD_CONTENT = git_show("HEAD", "scripts/backlog.py")
OLD_CONTENT = git_show(OLD_REV, "scripts/backlog.py")
if norm(HEAD_CONTENT) == norm(OLD_CONTENT):
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: выбранный старый коммит не отличается от HEAD — "
             "случай ② не будет различающим")
OLD_DATE = subprocess.run(["git", "-C", str(PACKAGE), "log", "-1", "--format=%as", OLD_REV],
                          capture_output=True, text=True).stdout.strip()
CHANGED_DATE = subprocess.run(["git", "-C", str(PACKAGE), "log", "-1", "--format=%as", CHANGED_REV],
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

# ═══ ③ у «❓» — версия появления + следующая смена (НЕ «последнее совпадение», возврат
# OPSSRE ③-2); встречный — «нет в истории»
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
appearance_sig = f"версия пакета от {OLD_DATE} (коммит {OLD_REV[:12]})"
changed_sig = f"пакет сменил её {CHANGED_DATE} (коммит {CHANGED_REV[:12]})"
case("③ у «❓» печатается дата и коммит ПОЯВЛЕНИЯ версии, а не последнего совпадения",
     rc2 == 0 and appearance_sig in out2
     and "backlog.py" in out2.split(appearance_sig)[0].splitlines()[-1],
     f"код {rc2} · ищем «{appearance_sig}» рядом с backlog.py")
case("③-2 подпись несёт ОБЕ даты: появления И следующей смены («пакет сменил её»)",
     rc2 == 0 and appearance_sig in out2 and changed_sig in out2
     and out2.index(appearance_sig) < out2.index(changed_sig) < out2.index(appearance_sig) + 200,
     f"ищем рядом «{appearance_sig}; {changed_sig}»")
case("③ встречный: содержимого нет в истории пакета — сказано так, а не выдумана дата",
     rc2 == 0 and "в истории пакета такого содержимого нет" in out2
     and "write-message.py" in out2.split("в истории пакета такого содержимого нет")[0]
         .splitlines()[-1],
     f"код {rc2}")

# ═══ ③-CRLF КАРТОЧКА #626: тот же опыт, что ③, но УСТАНОВЛЕННЫЙ файл явно лежит в форме
# CRLF (mezo_stand.crlf_twin) — как он лежит у контура-потребителя после git-чекаута на
# Windows, а не платформенной случайностью объекта из истории пакета (git-блоб — LF).
# Дата появления обязана найтись всё равно: сравнение по СОДЕРЖИМОМУ (norm — уже
# нормализует CRLF→LF), а не по байтам истории.
t2e = stand / "t2e"
db2e_dir = make_contour(t2e, TARGET)
upd2e = db2e_dir / "scripts" / "update-tools.py"
old_content_crlf = mezo_stand.crlf_twin(OLD_CONTENT.decode("utf-8")).encode("utf-8")
(db2e_dir / "scripts" / "backlog.py").write_bytes(old_content_crlf)
(db2e_dir / "scripts" / "write-message.py").write_text(ghost_marker, encoding="utf-8")
drop_fingerprints(db2e_dir / "mezosync.db", "backlog.py", "write-message.py")
rc2e, out2e = run(upd2e, "--source", str(PACKAGE))
installed_is_crlf = old_content_crlf != OLD_CONTENT and b"\r\n" in old_content_crlf
case("③-CRLF тот же опыт: установленный файл явно в форме CRLF — дата появления версии "
     "всё равно находится",
     installed_is_crlf and rc2e == 0 and appearance_sig in out2e
     and "backlog.py" in out2e.split(appearance_sig)[0].splitlines()[-1],
     f"код {rc2e} · установленный файл явно в форме CRLF: {installed_is_crlf}")

# ═══ ③-3 (возврат OPSSRE): после --apply без --overwrite-unknown — ПРАВДА, а не обещание
# «следующий прогон скажет определённо» (он НЕ скажет — отпечаток пишется только взятым
# файлам, «❓» без него так и останутся «❓»). Тот же t2/db2 — backlog.py и write-message.py
# всё ещё без отпечатка, всё ещё «❓».
rc2b, out2b = run(upd2, "--source", str(PACKAGE), "--apply")
case("③-3 после --apply БЕЗ --overwrite-unknown нет ложного обещания «скажет определённо»",
     rc2b == 0 and "следующий прогон скажет" not in out2b,
     f"код {rc2b} · искомая ложь отсутствует: {'следующий прогон скажет' not in out2b}")
case("③-3 вместо обещания — правда: «останутся «❓»» и рецепт (--overwrite-unknown / ничего)",
     rc2b == 0 and "останутся «❓»" in out2b and "--overwrite-unknown" in out2b,
     f"код {rc2b}")
rc2c, out2c = run(upd2, "--source", str(PACKAGE))          # план ЕЩЁ РАЗ — без --apply
case("③-3 встречный: следующий план ДЕЙСТВИТЕЛЬНО показывает те же «❓» — обещание было ложным не только на словах",
     rc2c == 0 and "backlog.py" in out2c and "❓" in out2c
     and appearance_sig in out2c,
     f"код {rc2c}")

# ═══ ③-1а (возврат OPSSRE): источник — ВЫГРУЗКА БЕЗ ИСТОРИИ. Обязана сказать «истории нет»,
# а НЕ «в истории такого содержимого нет» — это РАЗНЫЕ ответы: второй лжёт, что смотрели.
t2a = stand / "t2a"
db2a_dir = make_contour(t2a, TARGET)
upd2a = db2a_dir / "scripts" / "update-tools.py"
dump_src = stand / "dump-source"
make_dump_source(dump_src, "scripts/backlog.py", HEAD_CONTENT)
(db2a_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2a_dir / "mezosync.db", "backlog.py")
rc2a, out2a = run(upd2a, "--source", str(dump_src))
case("③-1а источник-выгрузка (без .git вовсе) → «истории у источника нет», не выдумана дата",
     rc2a == 0 and "истории у источника нет" in out2a
     and "в истории пакета такого содержимого нет" not in out2a
     and "версия пакета от" not in out2a,
     f"код {rc2a}")

# ═══ ③-1б (возврат OPSSRE, ГЛАВНЫЙ по этому возврату): источник — как git WORKTREE
# (`.git` ФАЙЛ, не каталог). Прежняя проверка `(path / ".git").is_dir()` считала такой
# источник НЕ-гитом и лгала «в истории нет» — 44 ложных находки из 45 у OPSSRE. `.git`
# здесь — ФАЙЛ-УКАЗАТЕЛЬ на PACKAGE/.git (см. make_worktree_like_source): PACKAGE
# при этом НИ РАЗУ не открывается на запись — контроль «пакет не тронут» ниже это проверяет.
t2b = stand / "t2b"
db2b_dir = make_contour(t2b, TARGET)
upd2b = db2b_dir / "scripts" / "update-tools.py"
worktree_src = stand / "worktree-like-source"
make_worktree_like_source(worktree_src, "scripts/backlog.py", HEAD_CONTENT)
(db2b_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2b_dir / "mezosync.db", "backlog.py")
rc2b_wt, out2b_wt = run(upd2b, "--source", str(worktree_src))
case("③-1б источник с `.git`-ФАЙЛОМ (как worktree) → история найдена, не «истории нет»",
     rc2b_wt == 0 and appearance_sig in out2b_wt and "истории у источника нет" not in out2b_wt,
     f"код {rc2b_wt} · ищем «{appearance_sig}»")

# ═══ ③-1в (возврат OPSSRE №2, ГЛАВНЫЙ по этому возврату): источник — подкаталог ДРУГОГО
# git-репозитория, не его корень. `git rev-parse --git-dir` из подкаталога находит .git ЭТОГО
# чужого репозитория (идёт вверх по дереву) — прежняя редакция принимала это за историю
# ПАКЕТА. Обязана сказать «каталог внутри другого репозитория», а НЕ «нет в истории»: второе
# лгало бы, что смотрели в правильном месте.
t2c = stand / "t2c"
db2c_dir = make_contour(t2c, TARGET)
upd2c = db2c_dir / "scripts" / "update-tools.py"
outer_repo = stand / "outer-repo"
nested_src = make_nested_repo_source(outer_repo, "scripts/backlog.py", HEAD_CONTENT)
(db2c_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2c_dir / "mezosync.db", "backlog.py")
rc2c_nested, out2c_nested = run(upd2c, "--source", str(nested_src))
case("③-1в источник — подкаталог чужого репозитория → «каталог внутри другого репозитория»",
     rc2c_nested == 0 and "каталог внутри другого репозитория" in out2c_nested
     and str(outer_repo) in out2c_nested
     and "в истории пакета такого содержимого нет" not in out2c_nested
     and "версия пакета от" not in out2c_nested,
     f"код {rc2c_nested} · назван корень чужого репозитория: {str(outer_repo) in out2c_nested}")

# ═══ ③-1г (граница OPSSRE из повтора ③-1, записка #5116): источник — корень репозитория без
# единого коммита. История пуста; «в истории пакета такого содержимого нет» лгало бы, что искали.
t2d = stand / "t2d"
db2d_dir = make_contour(t2d, TARGET)
upd2d = db2d_dir / "scripts" / "update-tools.py"
empty_repo_src = make_empty_repo_source(stand / "empty-repo-source", "scripts/backlog.py", HEAD_CONTENT)
(db2d_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2d_dir / "mezosync.db", "backlog.py")
rc2d, out2d = run(upd2d, "--source", str(empty_repo_src))
case("③-1г источник — репозиторий без единого коммита → «нет ни одного коммита», не «нет в истории»",
     rc2d == 0 and "нет ни одного коммита" in out2d
     and "в истории пакета такого содержимого нет" not in out2d
     and "версия пакета от" not in out2d,
     f"код {rc2d}")

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
     rc4 == 0 and appearance_sig in out4
     and "в истории пакета такого содержимого нет" in out4,
     f"код {rc4} — ③ обязан остаться зелёным при поломке, которая бьёт только --rev")

# ═══ ⑦ КОНТРОЛЬ нарочной поломкой (возврат OPSSRE): git_history_root() возвращён к старой
# проверке `(path / ".git").is_dir()`. Красить ОБЯЗАНА ровно ③-1б (worktree-подобный
# источник — там разница между способами и есть сам предмет находки OPSSRE) и НЕ обязана
# красить ③-1а (там и старая, и новая проверка одинаково честно отвечают «истории нет» —
# .git там нет вовсе, никакого различия способ проверки не вносит).
broken2_dir = stand / "broken2"
broken2_tool = mezo_stand.copy_tool(TARGET, broken2_dir)
old_check_src = broken2_tool.read_text(encoding="utf-8")
old_check_anchor = "            history_repo, reason = git_history_root(probe_dir)\n"
old_check_replacement = (
    "            history_repo, reason = ((probe_dir, \"\") if (probe_dir / \".git\").is_dir()\n"
    "                                    else (None, \"источник не git-репозиторий "
    "(нарочная поломка ③-1)\"))\n")
if old_check_anchor not in old_check_src:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка для поломки «git_history_root(probe_dir)» не найдена "
             "в испытуемом — переименовали переменную/функцию, поломка бьёт мимо")
broken2_tool.write_text(old_check_src.replace(old_check_anchor, old_check_replacement),
                        encoding="utf-8")

t2b_broken = stand / "t2b-broken"
db2b_broken_dir = make_contour(t2b_broken, broken2_tool)
upd2b_broken = db2b_broken_dir / "scripts" / "update-tools.py"
worktree_src2 = stand / "worktree-like-source-2"
make_worktree_like_source(worktree_src2, "scripts/backlog.py", HEAD_CONTENT)
(db2b_broken_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2b_broken_dir / "mezosync.db", "backlog.py")
rc7a, out7a = run(upd2b_broken, "--source", str(worktree_src2))
case_1b_turned_red = "истории у источника нет" in out7a
case("⑦ поломка (вернули `.is_dir()`) КРАСИТ ровно ③-1б: worktree-подобный источник",
     rc7a == 0 and case_1b_turned_red,
     f"код {rc7a} · «истории у источника нет» напечатано (ложно): {case_1b_turned_red}")

t2a_broken = stand / "t2a-broken"
db2a_broken_dir = make_contour(t2a_broken, broken2_tool)
upd2a_broken = db2a_broken_dir / "scripts" / "update-tools.py"
dump_src2 = stand / "dump-source-2"
make_dump_source(dump_src2, "scripts/backlog.py", HEAD_CONTENT)
(db2a_broken_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2a_broken_dir / "mezosync.db", "backlog.py")
rc7b, out7b = run(upd2a_broken, "--source", str(dump_src2))
case_1a_stayed_green = "истории у источника нет" in out7b
case("⑦ та же поломка НЕ трогает ③-1а: у обеих проверок один честный ответ («истории нет»)",
     rc7b == 0 and case_1a_stayed_green,
     f"код {rc7b} · ответ прежний («истории нет»): {case_1a_stayed_green} — "
     f"назван честно: этот случай поломка НЕ красит, различие способов проверки тут не видно")

# ═══ ⑧ КОНТРОЛЬ нарочной поломкой (возврат OPSSRE №2): убрана ИМЕННО проверка
# `--show-prefix` внутри git_history_root — `--git-dir` остаётся (③-1б по-прежнему находит
# worktree), но чужой репозиторий больше не отсекается. Красить ОБЯЗАНА ровно ③-1в
# (подкаталог чужого репо) и НЕ обязана трогать ③-1а (там `--git-dir` уже отказывает раньше,
# до show-prefix) и ③-1б (там `--show-prefix` и с проверкой был пуст — снятие проверки
# для НЕГО ничего не меняет).
broken3_dir = stand / "broken3"
broken3_tool = mezo_stand.copy_tool(TARGET, broken3_dir)
prefix_check_src = broken3_tool.read_text(encoding="utf-8")
prefix_check_anchor = (
    "    prefix = subprocess.run([\"git\", \"-C\", str(path), \"rev-parse\", \"--show-prefix\"],\n"
    "                            capture_output=True, text=True)\n"
    "    if (prefix.stdout or \"\").strip():\n"
    "        top = subprocess.run([\"git\", \"-C\", str(path), \"rev-parse\", \"--show-toplevel\"],\n"
    "                             capture_output=True, text=True)\n"
    "        outer_root = (top.stdout or \"\").strip() or \"корень не определился\"\n"
    "        return None, f\"каталог внутри другого репозитория ({outer_root})\"\n")
if prefix_check_anchor not in prefix_check_src:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок проверки --show-prefix не найден в испытуемом дословно "
             "— переписали git_history_root, поломка бьёт мимо")
# снимается ТОЛЬКО блок --show-prefix; проверка «нет ни одного коммита» ниже него остаётся
broken3_tool.write_text(prefix_check_src.replace(prefix_check_anchor, ""), encoding="utf-8")

t2c_broken = stand / "t2c-broken"
db2c_broken_dir = make_contour(t2c_broken, broken3_tool)
upd2c_broken = db2c_broken_dir / "scripts" / "update-tools.py"
outer_repo2 = stand / "outer-repo-2"
nested_src2 = make_nested_repo_source(outer_repo2, "scripts/backlog.py", HEAD_CONTENT)
(db2c_broken_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2c_broken_dir / "mezosync.db", "backlog.py")
rc8a, out8a = run(upd2c_broken, "--source", str(nested_src2))
# красит СВОЕЙ причиной: фраза пропала И вернулась прежняя ложь — поиск в ЧУЖОЙ истории
case_1v_turned_red = ("каталог внутри другого репозитория" not in out8a
                      and "в истории пакета такого содержимого нет" in out8a)
case("⑧ поломка (сняли --show-prefix) КРАСИТ ровно ③-1в: подкаталог чужого репозитория",
     rc8a == 0 and case_1v_turned_red,
     f"код {rc8a} · фраза пропала и вернулось ложное «нет в истории»: {case_1v_turned_red}")

t2b_broken3 = stand / "t2b-broken3"
db2b_broken3_dir = make_contour(t2b_broken3, broken3_tool)
upd2b_broken3 = db2b_broken3_dir / "scripts" / "update-tools.py"
worktree_src3 = stand / "worktree-like-source-3"
make_worktree_like_source(worktree_src3, "scripts/backlog.py", HEAD_CONTENT)
(db2b_broken3_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2b_broken3_dir / "mezosync.db", "backlog.py")
rc8b, out8b = run(upd2b_broken3, "--source", str(worktree_src3))
case("⑧ та же поломка НЕ трогает ③-1б: там --show-prefix и раньше был пуст",
     rc8b == 0 and appearance_sig in out8b,
     f"код {rc8b} · ③-1б обязан остаться зелёным — сняли проверку, которая для него не "
     f"срабатывала")

t2a_broken3 = stand / "t2a-broken3"
db2a_broken3_dir = make_contour(t2a_broken3, broken3_tool)
upd2a_broken3 = db2a_broken3_dir / "scripts" / "update-tools.py"
dump_src3 = stand / "dump-source-3"
make_dump_source(dump_src3, "scripts/backlog.py", HEAD_CONTENT)
(db2a_broken3_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2a_broken3_dir / "mezosync.db", "backlog.py")
rc8c, out8c = run(upd2a_broken3, "--source", str(dump_src3))
case("⑧ та же поломка НЕ трогает ③-1а: `--git-dir` там отказывает раньше show-prefix",
     rc8c == 0 and "истории у источника нет" in out8c,
     f"код {rc8c}")

# ═══ ⑨ КОНТРОЛЬ нарочной поломкой (граница OPSSRE, записка #5116): снята ИМЕННО проверка
# «нет ни одного коммита». Красить ОБЯЗАНА ровно ③-1г — и своей причиной: вернулась ложь «нет в
# истории»; НЕ обязана трогать ③-1б (там HEAD есть — проверка для него не срабатывала).
broken4_dir = stand / "broken4"
broken4_tool = mezo_stand.copy_tool(TARGET, broken4_dir)
head_check_src = broken4_tool.read_text(encoding="utf-8")
head_check_anchor = (
    "    head = subprocess.run([\"git\", \"-C\", str(path), \"rev-parse\", \"--verify\", \"-q\", \"HEAD\"],\n"
    "                          capture_output=True, text=True)\n"
    "    if head.returncode != 0:\n"
    "        return None, \"в репозитории-источнике нет ни одного коммита\"\n")
if head_check_anchor not in head_check_src:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок проверки «нет ни одного коммита» не найден в испытуемом "
             "дословно — переписали git_history_root, поломка бьёт мимо")
broken4_tool.write_text(head_check_src.replace(head_check_anchor, ""), encoding="utf-8")

t2d_broken = stand / "t2d-broken"
db2d_broken_dir = make_contour(t2d_broken, broken4_tool)
upd2d_broken = db2d_broken_dir / "scripts" / "update-tools.py"
empty_repo_src2 = make_empty_repo_source(stand / "empty-repo-source-2", "scripts/backlog.py", HEAD_CONTENT)
(db2d_broken_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2d_broken_dir / "mezosync.db", "backlog.py")
rc9a, out9a = run(upd2d_broken, "--source", str(empty_repo_src2))
case_1g_turned_red = ("нет ни одного коммита" not in out9a
                      and "в истории пакета такого содержимого нет" in out9a)
case("⑨ поломка (сняли проверку HEAD) КРАСИТ ровно ③-1г: вернулось ложное «нет в истории»",
     rc9a == 0 and case_1g_turned_red,
     f"код {rc9a} · фраза пропала и вернулась прежняя ложь: {case_1g_turned_red}")

t2b_broken4 = stand / "t2b-broken4"
db2b_broken4_dir = make_contour(t2b_broken4, broken4_tool)
upd2b_broken4 = db2b_broken4_dir / "scripts" / "update-tools.py"
worktree_src4 = stand / "worktree-like-source-4"
make_worktree_like_source(worktree_src4, "scripts/backlog.py", HEAD_CONTENT)
(db2b_broken4_dir / "scripts" / "backlog.py").write_bytes(OLD_CONTENT)
drop_fingerprints(db2b_broken4_dir / "mezosync.db", "backlog.py")
rc9b, out9b = run(upd2b_broken4, "--source", str(worktree_src4))
case("⑨ та же поломка НЕ трогает ③-1б: там HEAD есть",
     rc9b == 0 and appearance_sig in out9b,
     f"код {rc9b}")

# ═══ ⑩ КАРТОЧКА #608, ШАГ 3: update-tools печатает строку о правилах пакета — и когда
# источник несёт базу правил, и когда её нет. rules-from-pack.py копируем в контур ОТДЕЛЬНО
# от TARGET: update-tools зовёт его подпроцессом по строковому пути, а не импортом, и
# copy_tool() по AST-соседям такую связь не видит — граница названа в её же шапке (docstring
# copy_tool: «не чинит уже написанные приёмки, которые копируют файл своей рукой»).
RFP_TOOL = mezo_target.script("rules-from-pack.py")


def make_minimal_source(root: pathlib.Path, with_pack_db: bool) -> pathlib.Path:
    """Минимальный источник для update-tools: пустой scripts/ (диффу нечего брать — нам
    важна только строка о правилах, не сам перенос файлов) и, по флагу, rules/pack-rules.db
    по контракту rules-from-pack.py (та же схема, что у bite-rules-from-pack.py)."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    if with_pack_db:
        rules_dir = root / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        pconn = sqlite3.connect(str(rules_dir / "pack-rules.db"))
        pconn.executescript(
            "CREATE TABLE pack_rules (rule_set TEXT, rule_key TEXT, body TEXT, locked_by TEXT, "
            "text_sha TEXT, pack_updated_at TEXT, pack_commit TEXT, removed_at TEXT, "
            "PRIMARY KEY (rule_set, rule_key));"
            "CREATE TABLE pack_rules_history (rule_set TEXT, rule_key TEXT, text_sha TEXT, "
            "body TEXT, locked_by TEXT, first_commit TEXT, first_seen_at TEXT, replaced_at TEXT, "
            "PRIMARY KEY (rule_set, rule_key, text_sha));"
            "CREATE TABLE pack_rules_meta (key TEXT PRIMARY KEY, value TEXT);"
        )
        pconn.commit()
        pconn.close()
    return root


t10 = stand / "t10"
db10_dir = make_contour(t10, TARGET)
upd10 = db10_dir / "scripts" / "update-tools.py"
mezo_stand.copy_tool(RFP_TOOL, db10_dir / "scripts")   # испытуемый зовёт его подпроцессом

src_with_db = make_minimal_source(stand / "pack-with-rules-db", with_pack_db=True)
src_without_db = make_minimal_source(stand / "pack-without-rules-db", with_pack_db=False)

rc10a, out10a = run(upd10, "--source", str(src_with_db))
case("⑩а update-tools печатает «правила пакета: …» в ПЛАНЕ, когда у источника есть база правил",
     rc10a == 0 and "правила пакета: " in out10a,
     f"код {rc10a} · строка найдена: {'правила пакета: ' in out10a}")

rc10b, out10b = run(upd10, "--source", str(src_without_db))
case("⑩б update-tools печатает «в пакете нет базы правил», когда у источника её нет — не молчит",
     rc10b == 0 and "в пакете нет базы правил" in out10b,
     f"код {rc10b} · строка найдена: {'в пакете нет базы правил' in out10b}")

rc10c, out10c = run(upd10, "--source", str(src_with_db), "--apply")
case("⑩в строка о правилах пакета печатается и ПОСЛЕ --apply, не только в плане",
     rc10c == 0 and "правила пакета: " in out10c,
     f"код {rc10c} · строка найдена: {'правила пакета: ' in out10c}")

# ── ⑩ КОНТРОЛЬ нарочной поломкой (требование задания, п3): update-tools больше НЕ зовёт
# print_pack_rules_summary — случай ⑩а обязан провалиться ИМЕННО по этой причине.
broken5_dir = stand / "broken5"
broken5_tool = mezo_stand.copy_tool(TARGET, broken5_dir)
broken5_src = broken5_tool.read_text(encoding="utf-8")
# Отступ у двух вызовов РАЗНЫЙ (план — глубже вложен, чем итог --apply) — образец режет
# ЦЕЛУЮ строку по отступу, а не литеральный текст с зашитыми пробелами: иначе снятие одного
# отступа оставило бы обрывок пробелов перед следующей строкой и испортило бы синтаксис файла.
call_pattern = re.compile(r"[ \t]*print_pack_rules_summary\(db, tools, src_dir\)\n")
occurrences = len(call_pattern.findall(broken5_src))
if occurrences != 2:
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: строка вызова print_pack_rules_summary встречена "
             f"{occurrences} раз (ждали 2) — испытуемое изменилось, поломка бьёт мимо")
broken5_tool.write_text(call_pattern.sub("", broken5_src), encoding="utf-8")

t10d = stand / "t10d"
db10d_dir = make_contour(t10d, broken5_tool)
upd10d = db10d_dir / "scripts" / "update-tools.py"
mezo_stand.copy_tool(RFP_TOOL, db10d_dir / "scripts")
src_with_db2 = make_minimal_source(stand / "pack-with-rules-db-2", with_pack_db=True)
rc10e, out10e = run(upd10d, "--source", str(src_with_db2))
case("⑩ ПОЛОМКА (сняты оба вызова print_pack_rules_summary) КРАСИТ ровно случай ⑩а — своей "
     "причиной",
     rc10e == 0 and "правила пакета: " not in out10e,
     f"код {rc10e} · строка пропала: {'правила пакета: ' not in out10e}")

# ── ⑩г ОТЗЫВ PROTO (карточка #608, шаг 3): инструмента rules-from-pack.py нет НИ у контура,
# НИ в источнике — update-tools обязан назвать ОБА места, а не соврать «приедет обновлением»
# (та ложь заставила бы ждать инструмент, который никогда не приедет). src_without_db — тот же
# минимальный источник, что и в случае ⑩б: он никогда не несёт rules-from-pack.py
# (make_minimal_source кладёт только пустой scripts/).
# 🩸 КОНТУР БЕЗ ИНСТРУМЕНТА СТЕНД ДЕЛАЕТ САМ, А НЕ ПОЛАГАЕТСЯ НА ПАКЕТ. make_contour() собирает
# контур init-group.py ИЗ РАБОЧЕЙ КОПИИ ПАКЕТА, а с переносом карточки #608 (14.09) пакет несёт
# scripts/rules-from-pack.py — и свежий контур получает его сам. Прежний комментарий здесь
# («контур честно остаётся без него») был верен, пока пакет инструмента не нёс: 14.09 11:04 UTC
# случай провалился на ИСПРАВНОМ update-tools.py — стенд перестал строить свою предпосылку
# (найдено PROTO прогоном после переноса в пакет). ⇒ убираем файл из контура стенда явно
# и проверяем, что его там нет, до запуска.
def drop_rfp_from_stand(db_dir: pathlib.Path) -> None:
    rfp_in_stand = db_dir / "scripts" / "rules-from-pack.py"
    if rfp_in_stand.exists():
        rfp_in_stand.unlink()
    if rfp_in_stand.exists():
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: rules-from-pack.py не убран из контура стенда — случай ⑩г "
                 "проверял бы не то")


t10g = stand / "t10g"
db10g_dir = make_contour(t10g, TARGET)
drop_rfp_from_stand(db10g_dir)           # это и есть случай: у контура инструмента нет
upd10g = db10g_dir / "scripts" / "update-tools.py"
rc10g, out10g = run(upd10g, "--source", str(src_without_db))
case("⑩г строка о правилах пакета честно называет ОБА места, где инструмента нет — не путает "
     "с «приедет обновлением»",
     rc10g == 0 and "нет ни у контура, ни в источнике" in out10g
     and "приедет этим обновлением" not in out10g,
     f"код {rc10g} · строка: {out10g.strip().splitlines()[-1] if out10g.strip() else '(пусто)'}")

# ── ⑩г КОНТРОЛЬ нарочной поломкой: снимаем именно различение «источник несёт инструмент /
# не несёт» — инструмент начинает ВСЕГДА печатать «приедет обновлением», даже когда его нет
# нигде. Красит РОВНО случай ⑩г (там источник тоже пуст — «приедет» там ложь), а случаи
# ⑩а/⑩б/⑩в не трогает: там rules-from-pack.py у контура ЕСТЬ, и до этой ветки исполнение
# вообще не доходит (rfp.exists() истинно раньше).
broken6_dir = stand / "broken6"
broken6_tool = mezo_stand.copy_tool(TARGET, broken6_dir)
broken6_src = broken6_tool.read_text(encoding="utf-8")
anchor6 = (
    '        if (src_dir / "scripts" / "rules-from-pack.py").exists():\n'
    '            print("сверка правил пакета: инструмента rules-from-pack.py у контура нет — он "\n'
    '                  "приедет этим обновлением")\n'
    '        else:\n'
    '            print("сверка правил пакета: инструмента rules-from-pack.py нет ни у контура, "\n'
    '                  "ни в источнике")\n'
    '        return\n'
)
if broken6_src.count(anchor6) != 1:
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: якорь ветвления «приедет / нет нигде» в update-tools.py "
             "найден не ровно один раз — испытуемое изменилось, поломка бьёт мимо")
patched6 = broken6_src.replace(
    anchor6,
    '        print("сверка правил пакета: инструмента rules-from-pack.py у контура нет — он "\n'
    '              "приедет этим обновлением")\n'
    '        return\n',
)
broken6_tool.write_text(patched6, encoding="utf-8")

t10h = stand / "t10h"
db10h_dir = make_contour(t10h, broken6_tool)
drop_rfp_from_stand(db10h_dir)           # та же предпосылка, что у ⑩г
upd10h = db10h_dir / "scripts" / "update-tools.py"
rc10i, out10i = run(upd10h, "--source", str(src_without_db))
case("⑩г ПОЛОМКА (снято различение источника) КРАСИТ ровно случай ⑩г — своей причиной (лжёт "
     "«приедет», хотя нет нигде)",
     rc10i == 0 and "приедет этим обновлением" in out10i
     and "нет ни у контура, ни в источнике" not in out10i,
     f"код {rc10i} · строка: {out10i.strip().splitlines()[-1] if out10i.strip() else '(пусто)'}")

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
