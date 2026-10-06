#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update-tools — контур сам забирает свежие инструменты из общего репозитория.

    python <контур>/.mezosync/scripts/update-tools.py            # что изменилось (ничего не пишет)
    python <контур>/.mezosync/scripts/update-tools.py --apply     # забрать
    python <контур>/.mezosync/scripts/update-tools.py --source <путь или URL>   # разово иначе
    python <контур>/.mezosync/scripts/update-tools.py --source <...> --rev <коммит>  # РОВНО эта версия
    python <контур>/.mezosync/scripts/update-tools.py --source <...> --record-source  # ЗАПОМНИТЬ этот источник
    python <контур>/.mezosync/scripts/update-tools.py --merge <файл>                  # свести опору/вашу правку/пакет
    python <контур>/.mezosync/scripts/update-tools.py --accept-merge <файл> --apply   # принять черновик сведения

ЗАЧЕМ. Вопрос владельца 2026-08-19 09:22 UTC: «откуда tapas берёт инструментарий? он ведь
не скачал себе независимый репозиторий, чтобы не зависеть от твоих апгрейдов и чтобы мог
сам скачивать обновления». Ответ на тот момент был: НИОТКУДА — контур получал разовую копию
файлов с рабочего каталога соседа, не хранил ни источника, ни версии, и обновиться мог только
чужой рукой. Это делает контур не самостоятельной командой, а придатком чужой машины.

⚖️ ГРАНИЦЫ, названные заранее:
  · источник берётся ИЗ ЗАПИСИ КОНТУРА (meta.template_source), а не вписан сюда: вписанный
    путь протухает молча и тянет контур к чужой машине;
  · 🪤 --source НА ОДИН РАЗ НЕ СТАНОВИТСЯ ЗАПИСЬЮ МОЛЧА (карточка #604 ②). До этой правки
    любой --source, даже разовый, тут же перезаписывал meta.template_source — сосед (tapas)
    один раз дал --source локальной папки, чтобы взять ПРОВЕРЕННУЮ версию, и запись контура
    молча стала указывать на чужую машину. Теперь meta.template_source трогается только
    когда он ещё пуст (первая запись) ИЛИ по явному --record-source; --rev так же не
    записывается в источник — только в template_commit, тем коммитом, который реально взят;
  · СЛИЧАЕТСЯ СОДЕРЖИМОЕ, а не байты (правило `bytes-are-not-content`): у файлов, переехавших
    между машинами, разные окончания строк, и побайтовая сверка объявила бы правленым всё;
  · ФАЙЛ, ПРАВЛЕННЫЙ У СЕБЯ, НЕ ЗАТИРАЕТСЯ — и теперь это ПРАВДА, а не обещание.
    🪤 До 19.08 эта строка стояла здесь при коде, который её не исполнял: список правленых
    собирался безусловно, а рядом печаталось честное «свои правки НЕ различает». Правда была
    в предупреждении, ложь — в шапке, а шапку роль читает ПЕРВОЙ. Нашёл сосед (контур tapas,
    ответ 19.08 10:46 UTC) и отказался брать инструменты, пока противоречие не снято, —
    справедливо: без честной цены решение принять нельзя.
    КАК РАЗЛИЧАЕТСЯ: при установке и при каждом обновлении записываются отпечатки положенных
    файлов. Свой правленый = отличается И от источника, И от отпечатка установки.
  · ⛔ ОТПЕЧАТКОВ НЕТ (контур собран раньше, чем их стали писать) — различить нечем, и это
    ГОВОРИТСЯ ВСЛУХ. Такие файлы не обновляются молча: нужен явный --overwrite-unknown.
    Кроме одного случая (карточка #677): текст файла НАЙДЕН в истории пакета — значит, это
    старая версия пакета без своей правки; такой файл обновляется как «≠» и получает отпечаток;
  · ФАЙЛ, ПРАВЛЕННЫЙ У СЕБЯ, ПОЛУЧАЕТ ИСПРАВЛЕНИЯ ПАКЕТА ЧЕРЕЗ СВЕДЕНИЕ (карточка #609).
    Отпечаток установки (meta.template_files_sha) — это и есть ОПОРА: версия пакета, от
    которой контур когда-то пошёл. --merge находит ЕЁ ТЕКСТ в истории пакета (по отпечатку,
    а не по содержимому — см. find_version_by_fingerprint) и сводит три текста (опора · ваш ·
    пакет) инструментом `git merge-file`. Черновик кладётся РЯДОМ со скриптами, а не поверх
    живого файла; --accept-merge кладёт его в контур, только если отметок пересечения не
    осталось, и переносит опору на версию пакета, с которой сводили. Без этого шага список
    «✋ правлен у тебя» только НАЗЫВАЛ беду («перенеси свою правку сам»), а решить её было
    нечем — правка пакета, случившаяся ПОСЛЕ отпечатка установки, до контура не доходила
    никогда.
  · ⛔ без --apply не пишется ничего.
"""
from __future__ import annotations

import argparse
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
import mezo_paths  # noqa: E402

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = pathlib.Path(__file__).resolve().parent
# ВОЗВРАТ PROTO (тот же приём, что у rules-from-pack.py, SET_RULE_PY/GORDI_ISSUE_PY): путь —
# от СВОЕГО расположения, а не впечатан, — иначе подсказка годилась бы только автору файла.
GORDI_ISSUE_PY = HERE / "gordi-issue.py"

NEWLINE = chr(10)
UNKNOWN_VERSION = "версия неизвестна"   # заглушка fetch(), когда у источника нет HEAD вовсе

# ВОЗВРАТ PROTO (третий возврат, карточка #609): именованные байт-константы для стиля
# концов строк — та же причина, что у MERGE_LABEL_*: одна константа вместо байт-литерала,
# повторённого в нескольких местах (line_ending_style/to_lf/from_lf/cmd_merge ниже).
CRLF = b"\r\n"
LF = b"\n"

# ВОЗВРАТ PROTO (карточка #609): подписи git merge-file — ОДНА пара констант, а не
# литералы, разведённые по двум местам (сама команда git merge-file и разбор её вывода).
# Разведённые литералы уже разошлись бы однажды незаметно — правка одного места не тронула
# бы другое, и разбор искал бы подпись, которую сама команда больше не печатает.
MERGE_LABEL_OURS = "ваш текст"
MERGE_LABEL_THEIRS = "пакет сейчас"


def conflict_marker_lines(data: bytes) -> list[bytes]:
    """Строки данных, у которых пересечение НАЧИНАЕТСЯ или ЗАКАНЧИВАЕТСЯ — то есть строка
    начинается РОВНО с нашей подписи git merge-file (`<<<<<<< ваш текст` / `>>>>>>> пакет
    сейчас`), а не где угодно внутри строки.

    ВОЗВРАТ PROTO (карточка #609, главная правка): было `draft_bytes.count(b"<<<<<<< ")`
    и поиск подстрок `b"<<<<<<< "`/`b"=======\n"`/`b">>>>>>> "` — поиск ПОДСТРОКИ где угодно
    в тексте. У update-tools.py (и у его же приёмки) эти самые байты стоят в печатаемых
    строках КАК ТЕКСТ ДЛЯ ЧЕЛОВЕКА («отметки пересечения (<<<<<<< / ======= / >>>>>>>)») —
    контур, у которого правлен update-tools.py, получил бы от --merge ложные «пересечений: N»
    и вечный отказ --accept-merge на файле, где пересечений нет вовсе. «=======» отдельно
    НЕ ищем — частый разделитель обычного текста (границу пересечения метят обе НАШИ подписи,
    не одинокий разделитель). Обе формы конца строки (CRLF и LF) приводятся ПЕРЕД разбором —
    та же нормализация, что у same_text/digest везде в инструменте.
    """
    ours = f"<<<<<<< {MERGE_LABEL_OURS}".encode("utf-8")
    theirs = f">>>>>>> {MERGE_LABEL_THEIRS}".encode("utf-8")
    return [line for line in data.replace(b"\r\n", b"\n").split(b"\n")
           if line.startswith(ours) or line.startswith(theirs)]


def count_conflicts(data: bytes) -> int:
    """Число пересечений — по строкам НАЧАЛА (у каждого пересечения РОВНО одна строка
    «<<<<<<< ваш текст»); строка конца («>>>>>>> пакет сейчас») тем же пересечением не
    считается ещё раз — иначе число выходило бы вдвое больше настоящего."""
    ours = f"<<<<<<< {MERGE_LABEL_OURS}".encode("utf-8")
    return sum(1 for line in data.replace(b"\r\n", b"\n").split(b"\n") if line.startswith(ours))


def same_text(a: bytes, b: bytes) -> bool:
    """Содержимое, а не байты: окончания строк приводятся (правило bytes-are-not-content)."""
    return a.replace(b"\r\n", b"\n").rstrip() == b.replace(b"\r\n", b"\n").rstrip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


# ═══ ВТОРОЙ КАТАЛОГ УСТАНОВКИ (карточка #678, этап Э4, шаг Ш1, пункт «г»; решение COORD Т3) ═══
# Раньше обновление ставило файлы только в каталог рабочих скриптов контура. У контура Atlas
# есть ещё один каталог — vnext-tools: копия файлов vnext/prototype пакета (около 250 файлов), и
# обновления он не получал вовсе: файлы там старели молча.
# ⚖️ Каталог НЕОБЯЗАТЕЛЕН и объявляется ключом файла путей контура (.mezosync/local/paths.json),
# а не впечатан в код: у других контуров такого каталога нет, и их поведение не меняется ни на байт.
PROTOTYPE_DIR_KEY = "prototype_install_dir"
# 🪤 КЛЮЧ ОТПЕЧАТКА ВТОРОГО КАТАЛОГА НЕ ДОЛЖЕН СОВПАДАТЬ С КЛЮЧОМ ПЕРВОГО. Одни и те же имена
# бывают в обоих каталогах (mezo_paths.py, mezo_stand.py и другие лежат и в scripts/, и в
# vnext/prototype/), а ключ первого каталога — просто «имя.py» или «migrations/имя.py». Файл
# второго каталога поэтому получает ключ «prototype-dir::/имя.py»: двоеточие в имени каталога на
# Windows невозможно, а у настоящих каталогов контура его не бывает нигде, — значит пересечения
# с ключами первого каталога нет по построению. Этой же приставкой файл второго каталога
# помечается и внутри разбора ниже (поле rel у src_index), чтобы одно и то же имя из двух
# каталогов не слилось в одну запись.
SECOND_DIR_PSEUDO = "prototype-dir::"


def second_rel(name: str) -> pathlib.Path:
    """Запись файла второго каталога: «приставка/имя». Это НЕ путь на диске, а ярлык —
    путь на диске всегда берётся через dest_of() в main()."""
    return pathlib.Path(SECOND_DIR_PSEUDO) / name


def is_second_rel(rel) -> bool:
    return pathlib.Path(rel).parts[:1] == (SECOND_DIR_PSEUDO,)


def fingerprint_key(rel) -> str:
    """Ключ отпечатка установки (meta.template_files_sha) — ЕДИНСТВЕННОЕ место, где он строится
    для разбора и записи: путь относительно scripts/ в прямых косых («migrations/x.py»); у файла
    второго каталога — с приставкой SECOND_DIR_PSEUDO."""
    return pathlib.Path(rel).as_posix()


def second_install_dir(db: pathlib.Path) -> tuple[pathlib.Path | None, str | None]:
    """Второй каталог установки по ключу PROTOTYPE_DIR_KEY файла путей ЭТОЙ базы.

    Возвращает (каталог, None) — ключ есть и каталог на диске есть;
    (None, None) — ключа нет (или файла путей нет): всё как раньше, говорить не о чем;
    (None, слова) — ключ есть, но с ним беда (каталога нет, файл не читается): слова ДЛЯ ЧЕЛОВЕКА,
    их печатает вызывающий, — иначе файлы второго каталога старели бы молча, а печать читалась
    бы как «обновлено».
    Файл путей ищется рядом с базой (mezo_dir), а не от расположения инструмента: обновление
    идёт за базой, отпечатки которой пишет, — так же, как ключи annex_dir и mirror_repo."""
    lookup = getattr(mezo_paths, "local_path", None)
    if lookup is None:        # mezo_paths старше файла путей: ключа у такого контура быть не может
        return None, None
    res = lookup(PROTOTYPE_DIR_KEY, mezo_dir=pathlib.Path(db).resolve().parent)
    if res.outcome == mezo_paths.LOCAL_DECLARED:
        if res.path is not None and res.path.is_dir():
            return res.path, None
        return None, (f"в файле путей объявлен второй каталог установки ({PROTOTYPE_DIR_KEY}="
                      f"{res.path}), но такого каталога нет — файлы vnext/prototype в нём НЕ "
                      f"обслуживаются")
    if res.outcome == mezo_paths.LOCAL_UNREADABLE:
        return None, (f"файл путей не читается — есть ли у контура второй каталог установки, "
                      f"узнать нечем, он НЕ обслуживается ({res.words})")
    return None, None


# 🪤 КАРТОЧКА #637 (находка COORD, записка #5275): guard-all.py пакета зовёт новое звено
# (check-acceptance-env.py) из vnext/prototype, а обновлятор клал в «вне обновления» ЛЮБОЕ
# звено источника, которого у контура ещё нет, — даже то самое, которое зовут свежие scripts/.
# Итог: обновившийся контур получает общий прогон, немой на «гард не найден», а прогон
# читается как готовый. ⚖️ БЛИЗНЕЦ init-group.py 7б — меняешь правило в одном месте, правь
# во втором: то же замыкание (что зовут scripts/*.py и scripts/migrations/*.py транзитивно
# через тела звеньев vnext/prototype), но здесь оно СЧИТАЕТСЯ по scripts/ ИСТОЧНИКА
# (src_dir), а не по каталогу контура, — и не пишет файлы сама, только называет множество
# имён: класть их (и снимать отпечаток) решает уже общий ход main().
def closure_of_prototype_links(scripts_dir: pathlib.Path, proto_dir: pathlib.Path) -> set[str]:
    """Имена файлов `proto_dir` (vnext/prototype источника), которые транзитивно зовут
    `scripts_dir`/*.py и `scripts_dir`/migrations/*.py — ровно то же правило замыкания, что
    кладёт звенья свежему контуру (init-group.py, шаг 7б): сперва котировки `"имя.py"` в телах
    скриптов, затем — по телам самих звеньев вглубь, котировки `"имя.py"` И строчные `import x`.
    Звено, которого нет в `proto_dir`, закрывает свою ветку (сборке нечем его продолжить).

    🪤 КАРТОЧКА #678 (Э4 Ш1 «б»): ИМЯ ШАГА СХЕМЫ ЗВЕНОМ НЕ СЧИТАЕТСЯ. Имя шага («20260907-phoenix-
    records-fts.py») стоит в кавычках в find-phoenix.py — это путь к шагу схемы в migrations/ — и
    прежний разбор принимал его за звено. А одноимённый файл из vnext/prototype существует, и его
    клали ПЛОСКО в каталог скриптов: рядом с настоящим шагом схемы появлялся его двойник. Теперь
    имя, которое есть среди scripts/migrations/*.py источника, в замыкание не входит."""
    schema_steps = {p.name for p in scripts_dir.glob("migrations/*.py")}
    want: set[str] = set()
    for s in [*scripts_dir.glob("*.py"), *scripts_dir.glob("migrations/*.py")]:
        want |= set(re.findall(r'"([a-z0-9_.-]+\.py)"',
                               s.read_text(encoding="utf-8", errors="replace")))
    seen: set[str] = set()
    closure: set[str] = set()
    while want:
        name = want.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in schema_steps:
            continue                    # имя шага схемы, а не звено (см. выше)
        src = proto_dir / name
        if not src.exists():
            continue
        closure.add(name)
        body = src.read_text(encoding="utf-8", errors="replace")
        want |= set(re.findall(r'"([a-z0-9_.-]+\.py)"', body))
        want |= {m + ".py" for m in re.findall(r"^\s*import\s+([a-z_][a-z0-9_]*)",
                                               body, re.M)}
    return closure


# ВОЗВРАТ PROTO (третий возврат, карточка #609, находка COORD, записка #5232): на Windows
# (core.autocrlf=true) файл контура и файл пакета НА ДИСКЕ — CRLF, а опора, пришедшая из
# истории пакета (`git show`), — LF: git сам приводит объекты к LF внутри истории и не
# трогает рабочее дерево при извлечении текста через `show`. cmd_merge раньше подавал
# git merge-file СЫРЫЕ байты всех трёх текстов — на CRLF-контуре опора расходилась с ОБЕИМИ
# сторонами на КАЖДОЙ строке, и «пересечений: 0» превращалось в «пересечений: 3» даже там,
# где обе правки не пересекались вовсе. same_text/digest выше эту беду не ловят — они только
# СРАВНИВАЮТ содержимое, а git merge-file сводит СТРОКИ, и ему нужны на входе одинаковые
# концы строк у всех трёх текстов, а не только равенство пары.
def line_ending_style(data: bytes) -> bytes:
    """Стиль концов строк файла — CRLF или LF, большинством голосов по строкам: голого \\r
    без следующего \\n git не оставляет, поэтому считаем долю CRLF среди ВСЕХ \\n. Файл без
    единого \\n (или пустой) — LF по умолчанию, менять в нём нечего."""
    total_lf = data.count(LF)
    if total_lf == 0:
        return LF
    crlf = data.count(CRLF)
    return CRLF if crlf * 2 >= total_lf else LF


def to_lf(data: bytes) -> bytes:
    """Привести к LF ПЕРЕД git merge-file — тот же приём, что у same_text/digest, но здесь
    результат идёт НА ВХОД внешней команде, а не в сравнение, поэтому оформлен отдельно."""
    return data.replace(CRLF, LF)


def from_lf(data: bytes, style: bytes) -> bytes:
    """Обратный ход to_lf: перевести LF-текст (выход git merge-file) в СТИЛЬ ФАЙЛА КОНТУРА —
    черновик обязан выглядеть так, будто его сохранили тем же редактором, что и весь файл."""
    return data if style == LF else data.replace(LF, style)


def git_history_root(path: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """Есть ли у `path` полноценная git-история — спрошено у git, а не угадано по файлам.

    🩸 ВОЗВРАТ OPSSRE №1 (карточка #604 ③-1): прежняя проверка смотрела `(path / ".git").is_dir()`.
    Она ошибается в ДВЕ стороны разом:
      · выгрузка БЕЗ .git (архив, копия диска) — верно говорит «истории нет»;
      · git WORKTREE — у него `.git` это ФАЙЛ (`gitdir: .../worktrees/<имя>`), не каталог,
        и `.is_dir()` отвечает «не git» ОШИБОЧНО, хотя история там полная и доступна.
    Замер OPSSRE: на выгрузке без .git — 38 ложных находок из 45; на worktree — 44 из 45.
    `git rev-parse --git-dir` понимает ОБЕ формы — он и есть источник правды, не имя файла.

    🩸 ВОЗВРАТ OPSSRE №2 (карточка #604 ③-1в): `git rev-parse --git-dir` идёт ВВЕРХ по дереву
    каталогов, если у `path` нет своего `.git`, и находит .git ЧУЖОГО репозитория — например,
    `path` лежит подкаталогом внутри ДРУГОГО git-проекта (свой пакет скопирован в подпапку
    чужого репо). Прежняя редакция принимала такой найденный git ЗА ИСТОРИЮ ПАКЕТА и искала
    в НЕЙ — то есть не в той истории. Замер OPSSRE: 46 ложных «нет в истории» из 47 (и для
    закоммиченной, и для незакоммиченной внутри чужого репо копии — коммит тут ни при чём,
    беда в том, ЧЕЙ это .git). Различитель — `git rev-parse --show-prefix`: пусто ⇒ `path`
    САМ является корнем рабочего дерева найденного репозитория (историю берём); не пусто ⇒
    `path` — подкаталог ЧУЖОГО репозитория, историю не берём и называем корень чужого явно.

    🩸 ГРАНИЦА OPSSRE (повтор карточки #604 ③-1, записка #5116): репозиторий без единого
    коммита — `--git-dir` и `--show-prefix` отвечают как у настоящего, а история ПУСТА, и
    прежде это печаталось «в истории пакета такого содержимого нет», будто искали и не нашли.
    Различитель — `git rev-parse --verify -q HEAD`: отказ ⇒ коммитов нет, так и говорим.

    Возвращает (path, "") — история есть, опрашивай `path` как обычно;
    (None, причина) — истории нет, причина ДЛЯ ЧЕЛОВЕКА, а не код ошибки.
    """
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        reason = ("источник не git-репозиторий" if "not a git repository" in err.lower()
                 else (err[:200] or "git rev-parse --git-dir отказал без сообщения"))
        return None, reason
    prefix = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-prefix"],
                            capture_output=True, text=True)
    if (prefix.stdout or "").strip():
        top = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        outer_root = (top.stdout or "").strip() or "корень не определился"
        return None, f"каталог внутри другого репозитория ({outer_root})"
    head = subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", "-q", "HEAD"],
                          capture_output=True, text=True)
    if head.returncode != 0:
        return None, "в репозитории-источнике нет ни одного коммита"
    return path, ""


def is_shallow_clone(repo: pathlib.Path) -> bool:
    """Спрошено у git (`--is-shallow-repository`), а не угадано по файлу `.git/shallow` —
    тот же класс ошибки, что и у git_history_root: у worktree `.git` не каталог, и путь
    `.git/shallow` там не существует НЕЗАВИСИМО от того, мелкий репозиторий или полный."""
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip() == "true"


def history_repo_for(source: str, src_dir: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """Где искать историю пакета — общее место для ОБОИХ потребителей истории (карточка #609):
    отчёта по «❓» (find_version_span) и поиска опоры для --merge (find_version_by_fingerprint).

    Было раньше только внутри main() и звалось лишь когда есть хоть один «❓»; вынесено сюда
    без смены поведения — тот же выбор probe_dir (сам --source, если это папка, иначе
    скачанная копия) и та же дотяжка `--fetch --unshallow`, если клон был мелким (--depth 1).
    """
    source_as_dir = pathlib.Path(source)
    probe_dir = source_as_dir if source_as_dir.is_dir() else src_dir
    history_repo, reason = git_history_root(probe_dir)
    if history_repo is not None and is_shallow_clone(history_repo):
        subprocess.run(["git", "-C", str(history_repo), "fetch", "--unshallow"],
                       capture_output=True, text=True)
    return history_repo, reason


def find_version_span(repo: pathlib.Path, git_rel: str, target: bytes,
                      anchor_rev: str | None = None) -> dict:
    """Карточка #604 ③-2 (возврат OPSSRE): подпись несёт ДВЕ даты — появления версии И
    следующей смены, а не одну.

    ⚖️ ЧТО БЫЛО НЕ ТАК — НАЗВАНО ТОЧНО, а не пересказано наоборот. ДЕНЬ прежний код УЖЕ
    печатал верный — коммит, где версия ПОЯВИЛАСЬ (это и есть первое newest-first совпадение
    при обходе истории пути: `git log -- path` перечисляет только коммиты, менявшие путь,
    и одиночное совпадение — всегда коммит появления, второго такого не бывает, пока
    содержимое не встретится ПОВТОРНО после промежуточных правок). НЕВЕРНОЙ была ПОДПИСЬ —
    «последний раз совпадал с пакетом» звучит как «недавно», хотя дата могла быть месячной
    давности, а сколько версия провисела ПОСЛЕ появления, подпись не говорила вовсе. Живой
    пример OPSSRE: mention.py появился в этом виде 09.08 — ЭТУ дату прежний код и печатал
    верно — а пакет держал его так до 05.09; отсутствие второй даты («держали почти месяц»)
    и было находкой. Починка — не смена вычисляемой даты, а ДОБАВЛЕНИЕ второй.

    `anchor_rev`, если дан, ОГРАНИЧИВАЕТ историю ИМ И СТАРШЕ (при --rev не заглядываем ПОСЛЕ
    взятой версии — иначе «пакет сменил её» назвала бы смену, которую этот вызов сознательно
    не брал). Сравнение — ТО ЖЕ same_text, что и везде в инструменте.

    ⚖️ ВОЗВРАТ OPSSRE №2: `anchor_rev` может прийти ЗАГЛУШКОЙ (`UNKNOWN_VERSION` из fetch(),
    когда источник не сумел назвать свой HEAD) — отданная в `git log` как есть, она ломает
    сам вызов (git не понимает такую «версию», история для ВСЕХ файлов молча превращается
    в пустую, и правда «в истории нет» подменяется НЕПРАВДОЙ по той же форме). ВЫБОР — искать
    БЕЗ ГРАНИЦЫ (по всей истории источника), а не отказываться от дат: если версия и правда
    неизвестна, «не заглядывать в будущее после неё» бессмысленно само по себе — там нет
    ничего, после чего заглядывать. Отказ от дат в этом случае убрал бы то немногое верное,
    что мы всё ещё можем сказать (появление и смена внутри ВСЕЙ истории источника), не решив
    ничего взамен. Проверка — на вызывающей стороне (главный ход), не здесь: сюда обязаны
    приходить уже НАСТОЯЩИЙ коммит или None.

    Возвращает {"found": False} — в истории такого содержимого нет вовсе, ЭТО ОТДЕЛЬНЫЙ
    ответ от «истории нет» (git_history_root) — здесь история ЕСТЬ и была просмотрена.
    {"found": True, "date", "commit", "changed_date", "changed_commit"} — появление версии
    и следующая смена; changed_* пусты, если версия держится и сейчас (в границах anchor_rev).
    """
    args = ["git", "-C", str(repo), "log"]
    if anchor_rev:
        args.append(anchor_rev)
    args += ["--format=%H|%as", "--", git_rel]
    log = subprocess.run(args, capture_output=True, text=True)
    commits = [tuple(line.split("|", 1)) for line in (log.stdout or "").splitlines()
              if "|" in line]
    for i, (commit_hash, date) in enumerate(commits):
        show = subprocess.run(["git", "-C", str(repo), "show", f"{commit_hash}:{git_rel}"],
                              capture_output=True)
        if show.returncode == 0 and same_text(target, show.stdout):
            changed = commits[i - 1] if i > 0 else None
            return {"found": True, "date": date, "commit": commit_hash[:12],
                    "changed_date": changed[1] if changed else None,
                    "changed_commit": changed[0][:12] if changed else None}
    return {"found": False}


def find_version_by_fingerprint(repo: pathlib.Path, git_rel: str, fingerprint: str,
                                anchor_rev: str | None = None) -> dict:
    """ОПОРА файла (карточка #609): версия пакета в истории, чей отпечаток (digest()) равен
    `fingerprint` — ровно тому, что записан при установке или прошлом сведении
    (meta.template_files_sha). Найти её ТЕКСТОМ нужно для --merge: опору хранят отпечатком
    (числом), не байтами, а сводить нужно текст.

    Тот же обход истории пути, что у find_version_span (`git log -- git_rel`, новее→старше,
    `anchor_rev` не даёт заглянуть ПОСЛЕ взятой версии — тот же смысл, что там), но сравнение
    ДРУГОЕ: не same_text(target, ...) содержимого целиком, а digest(...) == fingerprint —
    опору ищем по отпечатку, а не по байтам (их с собой не носим).

    Возвращает {"found": False} — версии с таким отпечатком в просмотренной истории нет
    (клон может быть неполным, либо отпечаток — вовсе от другого источника);
    {"found": True, "date", "commit", "text": bytes, "changed": [(commit12, date), ...]} —
    сама версия (ТЕКСТ, нужен для git merge-file) и коммиты пакета, тронувшие путь ПОСЛЕ
    неё (новее→старше, в пределах anchor_rev; пустой список = пакет её держит и сейчас).
    """
    args = ["git", "-C", str(repo), "log"]
    if anchor_rev:
        args.append(anchor_rev)
    args += ["--format=%H|%as", "--", git_rel]
    log = subprocess.run(args, capture_output=True, text=True)
    commits = [tuple(line.split("|", 1)) for line in (log.stdout or "").splitlines()
              if "|" in line]
    for i, (commit_hash, date) in enumerate(commits):
        show = subprocess.run(["git", "-C", str(repo), "show", f"{commit_hash}:{git_rel}"],
                              capture_output=True)
        if show.returncode == 0 and digest(show.stdout) == fingerprint:
            changed = [(h[:12], d) for h, d in commits[:i]]   # новее найденной — их i штук
            return {"found": True, "date": date, "commit": commit_hash[:12],
                    "text": show.stdout, "changed": changed}
    return {"found": False}


def fetch(source: str, rev: str | None = None) -> tuple[pathlib.Path, str, bool]:
    """Возвращает каталог с шаблоном, его версию и признак «это временная копия».

    🩸 УБОРКА ЗДЕСЬ БЫЛА — И МОЛЧА НЕ РАБОТАЛА (замер PROTO 2026-08-24 16:39 UTC).
    Стояло `shutil.rmtree(..., ignore_errors=True)` в двух блоках finally, то есть
    на всех путях выхода. И всё равно во временном каталоге машины лежало 245 копий
    репозитория образца.
    ```
    опыт на КОПИИ одного из остатков:
      rmtree(ignore_errors=True) .............. каталог ОСТАЛСЯ
      rmtree со снятием метки только-чтения ... каталог удалён
    ```
    ⇒ `git clone` помечает файлы внутри `.git` только для чтения; Windows не даёт их
    удалить, а `ignore_errors=True` ГЛОТАЕТ этот отказ. Уборка выполнялась, ничего
    не убирала и ни разу об этом не сказала.
    🎯 Класс наш же и записанный: **молчащий отказ читается как успех.** Здесь он
    прожил дольше обычного именно потому, что уборка была НАПИСАНА — её наличие
    закрывало вопрос, а проверял ли кто-нибудь её действие, никто не спрашивал.
    ⚖️ И заявка называла причину иначе — «уборка стои́т не на всех путях выхода».
    Пути были все; ложным было не место, а действие.
    """
    local = pathlib.Path(source)
    if local.is_dir():
        if rev:
            # 🪤 --rev У ЛОКАЛЬНОЙ ПАПКИ (карточка #604 ②а): рабочую копию источника НЕ
            # трогаем — ни checkout, ни ветку. Нужную версию достаём git archive во
            # ВРЕМЕННЫЙ каталог; local остаётся ровно тем, чем был до вызова.
            resolved = subprocess.run(["git", "-C", str(local), "rev-parse", rev],
                                      capture_output=True, text=True)
            if resolved.returncode != 0:
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: версии {rev} нет в {source} "
                         f"(рабочая копия источника НЕ ТРОНУТА):{NEWLINE}   "
                         + (resolved.stderr or "").strip()[:400])
            commit = (resolved.stdout or "").strip()
            archive = subprocess.run(["git", "-C", str(local), "archive", "--format=tar", commit],
                                     capture_output=True)
            if archive.returncode != 0:
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: git archive версии {rev} из {source} не удался:"
                         f"{NEWLINE}   "
                         + (archive.stderr or b"").decode("utf-8", "replace").strip()[:400])
            tmp = mezo_stand.new("gordi-src-")
            untar = subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive.stdout)
            if untar.returncode != 0:
                mezo_stand.release(tmp)  # уборка отложена до исхода прогона
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: распаковка версии {rev} из {source} не удалась.")
            return tmp, commit[:12], True
        rev_out = subprocess.run(["git", "-C", str(local), "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        return local, (rev_out.stdout or "").strip()[:12] or UNKNOWN_VERSION, False
    tmp = mezo_stand.new("gordi-src-")
    # 🪤 --rev У URL-ИСТОЧНИКА (карточка #604 ②а): --depth 1 везёт только последний коммит,
    # а нужный может быть в истории. Клонируем ПОЛНОСТЬЮ и берём коммит из неё, а не гадаем.
    clone_cmd = (["git", "clone", source, str(tmp)] if rev else
                ["git", "clone", "--depth", "1", source, str(tmp)])
    r = subprocess.run(clone_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона
        sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ из {source}:{NEWLINE}   "
                 + (r.stderr or "").strip()[:400]
                 + f"{NEWLINE}   Это НЕ «обновлений нет» — источник недоступен.")
    if rev:
        co = subprocess.run(["git", "-C", str(tmp), "checkout", "--detach", rev],
                            capture_output=True, text=True)
        if co.returncode != 0:
            mezo_stand.release(tmp)
            sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: версии {rev} нет в {source}:{NEWLINE}   "
                     + (co.stderr or "").strip()[:400])
    rev_out = subprocess.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                         capture_output=True, text=True)
    return tmp, (rev_out.stdout or "").strip()[:12], True


def print_pack_rules_summary(db_path: pathlib.Path, tools_dir: pathlib.Path,
                             src_dir: pathlib.Path) -> None:
    """Строка о правилах пакета в конце прогона (карточка #608, шаг 3) — печатается и в
    плане (без --apply), и после --apply, тем же rules-from-pack.py --summary, которым
    контур сверяется сам. --source — СКАЧАННЫЙ источник, который update-tools уже держит
    (src_dir), а не meta.template_checkout: тот ключ update-tools не пишет и не читает.

    ⛔ НЕ МЕНЯЕТ КОД ВЫХОДА ОБНОВЛЕНИЯ: что бы rules-from-pack.py ни ответил, исход самого
    update-tools этим не сдвигается — здесь только печать, коды выхода не пробрасываются.
    """
    rfp = tools_dir / "rules-from-pack.py"
    if not rfp.exists():
        # ⚖️ ВОЗВРАТ PROTO: «приедет этим обновлением» — правда, только если источник его
        # ДЕЙСТВИТЕЛЬНО несёт. Источник без него — правды в «приедет» нет, и молчать об
        # этом тоже нельзя: назвать оба места, где инструмента нет, а не одно из двух.
        if (src_dir / "scripts" / "rules-from-pack.py").exists():
            print("сверка правил пакета: инструмента rules-from-pack.py у контура нет — он "
                  "приедет этим обновлением")
        else:
            print("сверка правил пакета: инструмента rules-from-pack.py нет ни у контура, "
                  "ни в источнике")
        return
    env = dict(os.environ)
    env.pop("MEZO_CONTAINER", None)   # своя среда — живой контур вызывающего сюда не путаем
    r = subprocess.run(
        [sys.executable, str(rfp), "--summary", "--db", str(db_path), "--source", str(src_dir)],
        capture_output=True, text=True, timeout=120, env=env)
    if r.returncode == 0:
        print((r.stdout or "").strip())
        return
    # ⛔ КОД 2 (И ЛЮБОЙ ДРУГОЙ) — ПЕЧАТАЕМ ЕГО ПРИЧИНУ, НЕ МОЛЧИМ (требование карточки #608).
    reason_lines = [ln for ln in ((r.stderr or "") + (r.stdout or "")).splitlines() if ln.strip()]
    reason = reason_lines[-1] if reason_lines else "(без сообщения)"
    print(f"сверка правил пакета: rules-from-pack.py отказал (код {r.returncode}) — {reason}")


# ── СВЕДЕНИЕ (карточка #609): --merge / --accept-merge ─────────────────────────────────
# ЗАМЫСЕЛ (тот же, что у правил в карточке #608, rules-from-pack.py --merge/--adopt): три
# текста, не два. Сравнить «ваш текст» с «текстом пакета» напрямую нельзя — не видно, кто
# менял. Третья точка — ОПОРА: версия пакета, от которой контур когда-то пошёл. У правил
# опору хранит отдельный ключ meta (pack_rules_base); у скриптов она УЖЕ есть — это
# meta.template_files_sha, отпечаток, который update-tools пишет при каждой установке и
# каждом взятии свежего. Не нужно заводить второе хранилище — нужно только уметь по этому
# отпечатку найти ТЕКСТ версии в истории пакета (find_version_by_fingerprint выше).
#
# ⚖️ ЧЕГО ЭТО НЕ ДЕЛАЕТ, названо прямо (то же «Не входит», что в карточке): --merge не
# сводит АВТОМАТИЧЕСКИ без роли — при пересечениях черновик несёт отметки, и --accept-merge
# отказывает, пока они не убраны. Файлам без отпечатка установки («❓») сводить нечем: опору
# найти нечем, и это говорится прямо, а не молчится (граница названа в самой командной строке).

def merge_work_root(tools: pathlib.Path) -> pathlib.Path:
    """Где лежат черновики сведения — РЯДОМ со скриптами контура, а не в общем временном
    месте (mezo_stand.new()): тот каталог убирается по исходу ОДНОГО запуска процесса, а
    черновик обязан пережить его — между --merge и его разбором ролью и --accept-merge
    обычно проходит ОТДЕЛЬНЫЙ запуск. Живой файл при этом не трогается — черновик лежит
    в СВОЕЙ папке, не поверх tools/<rel>."""
    return tools.parent / "merge-work"


def draft_slug(rel: pathlib.Path) -> str:
    return str(rel).replace(chr(92), "/").replace("/", "__")


def draft_paths(tools: pathlib.Path, rel: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    d = merge_work_root(tools) / draft_slug(rel)
    return d / rel.name, d / "meta.json"


def cmd_merge(tools: pathlib.Path, src_index: dict, git_rel_of: dict, fingerprints: dict,
             history_repo: pathlib.Path | None, history_unavailable: str | None,
             rel_arg: str, rev: str) -> int:
    """Свести опору · ваш текст · пакет для ОДНОГО файла контура. Живой файл НЕ трогается —
    только черновик рядом (draft_paths). git merge-file сам сводит непересекающиеся правки;
    пересечения помечает отметками — их разбирает роль (языковая модель), не этот код."""
    rel = pathlib.Path(rel_arg)
    mine = tools / rel
    if not mine.exists():
        sys.exit(f"⛔ файла «{rel_arg}» у контура нет — сводить нечего")
    if rel not in src_index:
        sys.exit(f"⛔ файла «{rel_arg}» нет в источнике — сводить не с чем")
    pack_bytes = src_index[rel].read_bytes()
    mine_bytes = mine.read_bytes()
    if same_text(mine_bytes, pack_bytes):
        sys.exit(f"⛔ «{rel_arg}»: ваш текст и текст пакета уже совпадают дословно — "
                 f"сводить нечего")
    fp = fingerprints.get(str(rel).replace(chr(92), "/"))
    if fp is None:
        sys.exit(f"⛔ опору найти нечем: у «{rel_arg}» нет отпечатка установки — различить, "
                 f"с какой версии пакета он пошёл, нечем (см. «❓» в обычном прогоне)")
    if history_repo is None:
        sys.exit(f"⛔ опору найти нечем: истории пакета нет — {history_unavailable}")
    git_rel = git_rel_of.get(rel)
    if not git_rel:
        sys.exit(f"⛔ опору найти нечем: путь «{rel_arg}» не встретился внутри истории пакета")
    # 🪤 ВОЗВРАТ OPSSRE №2 — та же граница, что и у bound в main() (см. комментарий там):
    # rev может прийти ЗАГЛУШКОЙ UNKNOWN_VERSION, и в git log её нельзя отдавать как есть.
    bound = rev if rev != UNKNOWN_VERSION else None
    found = find_version_by_fingerprint(history_repo, git_rel, fp, anchor_rev=bound)
    if not found.get("found"):
        sys.exit(f"⛔ опору найти нечем: версия с отпечатком установки «{fp}» в истории "
                 f"пакета не встретилась (клон может быть неполным)")
    opora_bytes = found["text"]

    draft_path, meta_path = draft_paths(tools, rel)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    # ВОЗВРАТ PROTO (третий возврат, карточка #609): стиль концов строк — у ФАЙЛА КОНТУРА,
    # а не у опоры и не у пакета (тот, кто будет читать черновик глазами и редактором,
    # правит именно файл контура). Все три текста, что видит git merge-file, приводятся
    # к LF — иначе на CRLF-контуре опора (из истории, LF) расходится с обеими сторонами на
    # КАЖДОЙ строке, и честные непересекающиеся правки превращаются в ложные пересечения
    # (находка COORD, записка #5232). Черновик на выходе переводится ОБРАТНО в стиль файла
    # контура — иначе роль получит черновик, у которого концы строк внезапно сменились без
    # единой её правки, и следующий git diff будет шуметь по всему файлу.
    circuit_style = line_ending_style(mine_bytes)
    circuit_style_name = "CRLF" if circuit_style == CRLF else "LF"
    print(f"концы строк файла контура: {circuit_style_name} — "
          "опора/ваш текст/пакет перед сведением приведены к LF, черновик — обратно в этот стиль")
    # ⚡ ИМЕНА ВРЕМЕННЫХ ФАЙЛОВ — ПО-АНГЛИЙСКИ (слово владельца: код и имена — по-английски;
    # печатаемый человеку текст — по-русски). Подписи -L у git merge-file ниже ОСТАЮТСЯ
    # русскими — их читает человек, разбирая черновик, это не имя, а показываемый текст.
    ours_f = draft_path.parent / "_ours.tmp"
    base_f = draft_path.parent / "_base.tmp"
    theirs_f = draft_path.parent / "_theirs.tmp"
    ours_f.write_bytes(to_lf(mine_bytes))
    base_f.write_bytes(to_lf(opora_bytes))
    theirs_f.write_bytes(to_lf(pack_bytes))
    r = subprocess.run(
        ["git", "merge-file", "-p",
         "-L", MERGE_LABEL_OURS,
         "-L", f"опора (пакет от {found['date']}, коммит {found['commit']})",
         "-L", MERGE_LABEL_THEIRS, str(ours_f), str(base_f), str(theirs_f)],
        capture_output=True)
    for f in (ours_f, base_f, theirs_f):
        f.unlink(missing_ok=True)
    if r.returncode < 0:
        sys.exit(f"⛔ git merge-file не сумел сравнить тексты (код {r.returncode}): "
                 + (r.stderr or b"").decode("utf-8", "replace").strip()[:400])
    draft_bytes = from_lf(r.stdout, circuit_style)
    draft_path.write_bytes(draft_bytes)
    conflicts = count_conflicts(draft_bytes)
    meta = {"rel": str(rel).replace(chr(92), "/"), "pack_fingerprint": digest(pack_bytes),
            "pack_rev_at_merge": rev, "opora_fingerprint": fp,
            "opora_commit": found["commit"], "opora_date": found["date"]}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"опора: версия пакета от {found['date']} (коммит {found['commit']})")
    print(f"черновик: {draft_path}")
    print(f"пересечений: {conflicts}")
    if conflicts:
        print("⚖️ в черновике остались отметки пересечения (<<<<<<< / ======= / >>>>>>>) — "
              "их обязана разобрать роль (прогони свои проверки после), затем повтори тем "
              f"же именем: --accept-merge {rel_arg} --apply")
    else:
        print(f"пересечений нет — черновик несёт ОБЕ правки; живой файл НЕ тронут. Принять: "
              f"--accept-merge {rel_arg} --apply")
    return 0


def cmd_accept_merge(db_path: pathlib.Path, tools: pathlib.Path, rel_arg: str,
                     apply: bool) -> int:
    """Принять черновик, оставленный --merge: отказ, если в нём ещё есть отметки
    пересечения; иначе — живой файл получает черновик, а опора (meta.template_files_sha)
    переходит на версию пакета, с КОТОРОЙ сводили (сохранена в meta.json рядом с черновиком
    при самом --merge — не пересчитывается заново, чтобы --accept-merge не зависел от
    источника и не звал сеть повторно)."""
    rel = pathlib.Path(rel_arg)
    draft_path, meta_path = draft_paths(tools, rel)
    if not draft_path.exists() or not meta_path.exists():
        sys.exit(f"⛔ черновика для «{rel_arg}» нет — сначала --merge {rel_arg}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    draft_bytes = draft_path.read_bytes()
    if conflict_marker_lines(draft_bytes):
        sys.exit(f"⛔ в черновике «{draft_path}» остались отметки пересечения — разбери их "
                 f"и сохрани файл, затем повтори --accept-merge {rel_arg} --apply")
    if not apply:
        print(f"[ХОЛОСТОЙ ПРОГОН] принял бы «{rel_arg}»: живой файл получит черновик, опорой "
              f"станет версия пакета, с которой сводили (отпечаток {meta['pack_fingerprint']}, "
              f"ревизия пакета при сведении {meta.get('pack_rev_at_merge', '?')}). "
              f"Для записи — флаг --apply.")
        return 0
    mine = tools / rel
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_bytes(draft_bytes)

    conn = sqlite3.connect(str(db_path))
    got = {k: v for k, v in conn.execute("SELECT key, value FROM meta")}
    fingerprints = json.loads(got.get("template_files_sha") or "{}")
    fingerprints[meta["rel"]] = meta["pack_fingerprint"]
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 ("template_files_sha", json.dumps(fingerprints, ensure_ascii=False)))
    conn.commit()
    conn.close()

    for p in (draft_path, meta_path):
        p.unlink(missing_ok=True)
    try:
        draft_path.parent.rmdir()
    except OSError:
        pass   # не пусто (чужой мусор) или занято — не повод падать на уборке черновика

    print(f"✅ принято: {rel_arg} — опора файла теперь версия пакета, с которой сводили "
          f"(отпечаток {meta['pack_fingerprint']})")
    print("   файл по-прежнему отличается от пакета (в нём ваша правка) — следующий обычный "
          "прогон снова покажет «✋ ПРАВЛЕН У ТЕБЯ», но с отметкой «пакет после опоры не "
          "менял»; прежняя опора в выводе не встретится.")
    print(f"👉 если правка контура полезна не только вам — предложи её в пакет: "
          f"python {GORDI_ISSUE_PY} create --role <координатор> --title \"...\" "
          f"--body-file <файл с ## ЗАМЕР / ## КЛАСС / ## ПРЕДЛОЖЕНИЕ> --dry-run "
          f"(форма — как у rules-from-pack.py --propose)")
    return 0


HELP_SECOND_DIR = """ВТОРОЙ КАТАЛОГ УСТАНОВКИ (необязательно; карточка #678).
  Файл путей контура (.mezosync/local/paths.json) может нести ключ prototype_install_dir — каталог,
  куда поставлены файлы vnext/prototype пакета (например, <контейнер>/vnext-tools;
  относительный путь считается от контейнера).
  · Ключа нет — поведение прежнее, потребителей это не касается.
  · Ключ есть — файл vnext/prototype/*.py, который УЖЕ лежит в этом каталоге, сравнивается и
    ставится ТУДА: те же разряды «+ ≠ ✋ ❓», та же история пакета. Звено, которое уже лежит во
    втором каталоге, в каталог рабочих скриптов не кладётся. План называет каталог каждого файла.
  · Отпечатки установки файлов второго каталога пишутся с приставкой «prototype-dir::/» (одни и те
    же имена бывают в обоих каталогах); --record-only снимает отпечатки и со второго каталога.
  · Ничего не удаляется, ставятся только файлы .py. Сведение (--merge) для файлов второго
    каталога не работает — их правку сводят руками.
ШАГИ СХЕМЫ (scripts/migrations/*.py) получают отпечатки установки тем же ключом «migrations/<имя>»
  и при --apply, и при --record-only; имя шага схемы звеном vnext/prototype не считается.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="забрать свежие инструменты из общего репозитория",
                                 epilog=HELP_SECOND_DIR,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="путь или URL; по умолчанию — записанный при сборке контура")
    ap.add_argument("--apply", action="store_true", help="записать (без него — только план)")
    # 🪤 КОНТУР-АВТОР ШАБЛОНА НЕ МОЖЕТ ЗАБИРАТЬ ИЗ НЕГО ФАЙЛЫ: его живые инструменты — ИСТОЧНИК
    # правок, а не отставшая копия, и «обновление» затёрло бы работу в обратную сторону.
    # Но происхождение записать ему всё равно нужно: 19.08 выяснилось, что мы сами не можем
    # ответить, на какой версии шаблона живём. ⇒ отдельный режим: записать и ничего не трогать.
    ap.add_argument("--record-only", action="store_true",
                    help="только записать источник и версию в контур, файлы НЕ трогать")
    ap.add_argument("--overwrite-unknown", action="store_true",
                    help="перезаписать и те файлы, у которых нет отпечатка установки "
                         "(различить свою правку нечем — согласие называется явно)")
    ap.add_argument("--rev", default=None,
                    help="взять из источника РОВНО этот коммит, а не HEAD/latest "
                         "(карточка #604 ②а)")
    ap.add_argument("--record-source", action="store_true",
                    help="ЗАПИСАТЬ meta.template_source этим --source, даже если источник "
                         "уже записан. Без флага источник в meta трогается только при первой "
                         "записи (карточка #604 ②б) — разовый --source в постоянную запись "
                         "не превращается")
    ap.add_argument("--merge", metavar="ФАЙЛ", default=None,
                    help="свести опору · ваш текст · текст пакета для файла контура, "
                         "правленого у себя (карточка #609); черновик — В СТОРОНУ, живой "
                         "файл не трогается")
    ap.add_argument("--accept-merge", dest="accept_merge", metavar="ФАЙЛ", default=None,
                    help="принять черновик --merge (нужен --apply): положить в контур и "
                         "перенести опору на версию пакета, с которой сводили; отказ, пока "
                         "в черновике остаются отметки пересечения")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    modes = sum(bool(x) for x in (a.record_only, a.merge, a.accept_merge))
    if modes > 1:
        sys.exit("⛔ --record-only / --merge / --accept-merge — разные режимы; за один "
                 "вызов можно попросить только один")

    db = a.db or mezo_paths.live_db()
    conn = sqlite3.connect(str(db))
    got = {k: v for k, v in conn.execute("SELECT key, value FROM meta")}
    conn.close()

    # Второй каталог установки (карточка #678 «г»): None — ключа нет, и всё идёт как раньше.
    second_dir, second_note = second_install_dir(db)

    if a.accept_merge:
        # ⚖️ БЕЗ источника и БЕЗ сети: всё нужное (черновик, отпечаток версии пакета,
        # с которой сводили) уже лежит рядом с черновиком — так --accept-merge не зависит
        # от доступности источника и не звонит наружу повторно.
        tools = pathlib.Path(mezo_paths.live_scripts())
        return cmd_accept_merge(db, tools, a.accept_merge, a.apply)

    source = a.source or got.get("template_source")
    if not source:
        sys.exit("⛔ КОНТУР НЕ ЗНАЕТ СВОЕГО ИСТОЧНИКА (meta.template_source пусто). "
                 "Значит он собран до того, как происхождение стали записывать: назови источник "
                 "разово через --source, и он запишется.")

    if a.record_only:
        # ⚖️ --record-only ЯВНО ОЗНАЧАЕТ «записать источник» — это его единственный смысл,
        # поэтому охрана ②б (писать источник только по --record-source/первой записи) сюда
        # не распространяется: слово уже дано самим выбором этого режима.
        src_dir, rev, temporary = fetch(source, rev=a.rev)
        try:
            # ⚖️ ОТПЕЧАТКИ ПИШУТСЯ И ЗДЕСЬ — иначе контур, собранный до появления этой записи,
            # так и остался бы без «до чего он был правлен», и первое же обновление не смогло бы
            # отличить его правку от свежести источника. Отпечаток снимается с ТОГО, ЧТО ЛЕЖИТ
            # СЕЙЧАС: он говорит «вот с чем сравнивать дальше», а не «это пришло из источника».
            tools_now = pathlib.Path(mezo_paths.live_scripts())
            # 🪤 КАРТОЧКА #678 «в»: отпечатки снимаются ТЕМ ЖЕ набором ключей, что кладёт --apply:
            # весь scripts/ источника, шаги схемы тоже — ключ «migrations/<имя>». Раньше брался
            # только верхний уровень, и у контура, записанного этим режимом, шаги схемы были без
            # отпечатка: любое их изменение в пакете читалось как «❓ различить нечем».
            src_scripts = src_dir / "scripts"
            names = {f.relative_to(src_scripts).as_posix() for f in src_scripts.rglob("*.py")}
            linked_dir = src_dir / "vnext" / "prototype"
            linked_names = {f.name for f in linked_dir.glob("*.py")} if linked_dir.is_dir() else set()
            names |= linked_names
            fingerprints = {f.relative_to(tools_now).as_posix(): digest(f.read_bytes())
                      for f in sorted(tools_now.rglob("*.py"))
                      if f.relative_to(tools_now).as_posix() in names}
            second_taken = 0
            if second_dir is not None:
                # Второй каталог (карточка #678 «г»): файлы vnext/prototype, что уже лежат там, —
                # с приставкой в ключе, чтобы не затереть ключ одноимённого файла первого каталога.
                for f in sorted(second_dir.glob("*.py")):
                    if f.name in linked_names:
                        fingerprints[fingerprint_key(second_rel(f.name))] = digest(f.read_bytes())
                        second_taken += 1
            conn = sqlite3.connect(str(db))
            for k, v in (("template_source", source), ("template_commit", rev),
                         ("template_files_sha", json.dumps(fingerprints, ensure_ascii=False)),
                         ("template_recorded_at",
                          conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')")
                          .fetchone()[0] + " UTC")):
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                             "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
            conn.commit()
            conn.close()
            print(f"✅ Записано происхождение: {source} · версия {rev} · "
                  f"отпечатков установки {len(fingerprints)}"
                  + (f" (из них у файлов второго каталога: {second_taken})"
                     if second_dir is not None else ""))
            if second_note:
                print(f"⚠️ {second_note}")
            print("   Файлы НЕ тронуты: это режим записи, а не обновления.")
        finally:
            if temporary:
                mezo_stand.release(src_dir)   # 🩸 было `rmtree(ignore_errors=True)`
        return 0

    tools = pathlib.Path(mezo_paths.live_scripts())
    if second_dir is not None and second_dir.resolve() == tools.resolve():
        # ключ указывает на сам каталог рабочих скриптов: один файл попал бы в разбор дважды
        second_note = (f"ключ {PROTOTYPE_DIR_KEY} указывает на каталог рабочих скриптов ({tools}) — "
                       f"второго каталога нет, ключ не используется")
        second_dir = None
    src_dir, rev, temporary = fetch(source, rev=a.rev)
    try:
        src_tools = src_dir / "scripts"
        if not src_tools.is_dir():
            sys.exit(f"⛔ в источнике нет каталога scripts: {src_dir}")

        def dest_of(rel: pathlib.Path) -> pathlib.Path:
            """Где файл лежит (или ляжет) у контура: у файла второго каталога — там, у остальных —
            среди рабочих скриптов. Единственное место, где запись разбора превращается в путь."""
            return second_dir / rel.name if is_second_rel(rel) else tools / rel

        def show_name(rel: pathlib.Path) -> str:
            """Имя файла в плане: у файла второго каталога — без служебной приставки.
            ⚠️ Имя НЕ `shown`: ниже в main() есть обычная переменная `shown` (строка коммитов у «✋») —
            одноимённая функция ею затиралась, и вывод плана падал на файле с «✋» и историей пакета."""
            return rel.name if is_second_rel(rel) else str(rel)

        def where(rel: pathlib.Path) -> str:
            """Куда идёт файл — печатается только когда объявлен второй каталог: без ключа план
            ровно прежний, потребителей он не касается."""
            if second_dir is None:
                return ""
            return "  → второй каталог" if is_second_rel(rel) else "  → скрипты"

        # 🪤 ИСТОЧНИК — ДВА КАТАЛОГА, А НЕ ОДИН. Обновлятор обходил только scripts/, а семь
        # звеньев, которые зовёт общий прогон, лежат в источнике в vnext/prototype/ и при
        # сборке кладутся потребителю РЯДОМ со скриптами. Они не обновлялись НИКОГДА, и
        # инструмент об этом молчал: частичный охват, читаемый как полный. Нашёл сосед
        # (контур tapas, 19.08 10:46 UTC) — у него два таких звена уже разошлись.
        src_index = {}          # rel -> абсолютный путь у источника (что копировать)
        git_rel_of = {}         # rel -> путь ВНУТРИ git-репозитория источника (для истории, ③)
        for f in sorted(src_tools.rglob("*.py")):
            rel = f.relative_to(src_tools)
            src_index[rel] = f
            git_rel_of[rel] = "scripts/" + rel.as_posix()
        schema_step_names = {p.name for p in src_tools.glob("migrations/*.py")}
        linked_dir = src_dir / "vnext" / "prototype"
        out_of_scope = []
        if linked_dir.is_dir():
            # 🪤 КАРТОЧКА #637: «звена у нас нет» раньше значило ОДНО — «сборка его не клала»,
            # и не различало «сборка положила бы его СЕЙЧАС, зови мы сборку заново» (звено из
            # замыкания новых scripts/) от «сборка его не зовёт вовсе» (правда не звана никем).
            # Первое — не «вне обновления», это ДОЛГ обновления: контур, собранный ДО того как
            # звено стало зваться, без него не соберётся заново сам. Замыкание см. выше.
            closure = closure_of_prototype_links(src_tools, linked_dir)
            for f in sorted(linked_dir.glob("*.py")):
                rel = pathlib.Path(f.name)
                # 🪤 КАРТОЧКА #678 «г»: файл vnext/prototype, который УЖЕ лежит во втором каталоге,
                # сравнивается и ставится ТУДА — под своей записью (с приставкой), независимо от
                # того, что стоит среди рабочих скриптов под тем же именем. Нет ключа — ветка не
                # срабатывает вовсе, и разбор ниже тот же, что был.
                in_second = second_dir is not None and (second_dir / f.name).is_file()
                if in_second:
                    src_index[second_rel(f.name)] = f
                    git_rel_of[second_rel(f.name)] = "vnext/prototype/" + f.name
                if rel in src_index:
                    continue
                if (tools / rel).exists():
                    src_index[rel] = f          # звено уже стои́т у нас — обновляем его
                    git_rel_of[rel] = "vnext/prototype/" + f.name
                elif f.name in closure:
                    if not in_second:           # уже лежит во втором каталоге — в скрипты не кладём
                        src_index[rel] = f      # звено из замыкания источника — появится (+)
                        git_rel_of[rel] = "vnext/prototype/" + f.name
                elif f.name in schema_step_names:
                    pass                        # это имя шага схемы, а не звено (карточка #678 «б»)
                elif not in_second:
                    out_of_scope.append(rel)    # звена у нас нет, и звено его не зовёт вовсе

        fingerprints = json.loads(got.get("template_files_sha") or "{}")

        if a.merge:
            history_repo, history_unavailable = history_repo_for(source, src_dir)
            return cmd_merge(tools, src_index, git_rel_of, fingerprints,
                             history_repo, history_unavailable, a.merge, rev)

        previous_commit = got.get("template_commit", "неизвестна")
        print(f"источник ... {source}" + (f"  (--rev {a.rev})" if a.rev else ""))
        print(f"версия ..... было {previous_commit} · стало {rev}")
        if second_dir is not None:
            print(f"каталоги ... скрипты — {tools}")
            print(f"             второй (файлы vnext/prototype, которые УЖЕ лежат там) — {second_dir}")
        if second_note:
            print(f"⚠️ {second_note}")
        print()

        fresh, own_edits, new_files, unknown = [], [], [], []
        for rel, f in sorted(src_index.items()):
            mine = dest_of(rel)
            if not mine.exists():
                new_files.append(rel)
                continue
            mine_bytes = mine.read_bytes()
            if same_text(mine_bytes, f.read_bytes()):
                continue
            installed_fp = fingerprints.get(fingerprint_key(rel))
            if installed_fp is None:
                unknown.append(rel)
            elif digest(mine_bytes) != installed_fp:
                own_edits.append(rel)          # правлен У СЕБЯ — не трогаем
            else:
                fresh.append(rel)

        # 🪤 КАРТОЧКА #604 ③: у «❓» называем, КОГДА эта версия появилась и когда пакет её
        # сменил — иначе «❓» читается как «не смотрели», а не «застряли месяц назад» (шесть
        # таких файлов у tapas стояли на пакете 20.08 почти месяц, никто не заметил).
        # История нужна только когда есть хоть один «❓» ИЛИ «✋» — иначе это лишний git-вызов
        # впустую. Карточка #609 расширила условие («✋» тоже нужна опора по отпечатку), но
        # САМ ПОИСК истории (git_history_root) оставлен ИНЛАЙНОМ, на том же месте и тем же
        # вызовом, что и был, — не вынесен в history_repo_for(). Причина: прежние приёмки
        # правят этот код нарочной поломкой ПО ТЕКСТУ (ищут строку дословно) — вынеси её в
        # отдельную функцию, и их поломка перестала бы находить свою строку, а «не нашлась
        # строка для поломки» — это отказ приёмки, не число различающих случаев. history_repo_for
        # ниже используется ТОЛЬКО у --merge — там прежнего текста для сравнения нет.
        # ⚖️ ТРИ РАЗНЫХ ОТВЕТА, и путать их нельзя (возврат OPSSRE ③-1): история НЕ СМОТРЕЛАСЬ
        # (источник не git или worktree распознан неверно) ≠ история ПРОСМОТРЕНА и такого
        # содержимого в ней нет ≠ содержимое найдено — с датой появления и датой смены.
        history: dict = {}
        history_repo = None
        history_unavailable = None
        # 🪤 ВОЗВРАТ OPSSRE №2: rev может быть ЗАГЛУШКОЙ UNKNOWN_VERSION (у
        # источника нет HEAD вовсе — см. fetch()). Отданная в git log как есть,
        # она ломает вызов и подменяет правду «в истории нет» неправдой той же
        # формы. Выбор — искать БЕЗ ГРАНИЦЫ (anchor_rev=None), а не
        # отказываться от дат: разбор выбора — в докстроке find_version_span.
        # Карточка #609: граница ТА ЖЕ САМАЯ, и теперь она общая для «❓» (find_version_span)
        # и «✋» (find_version_by_fingerprint) — один bound на обоих потребителей истории.
        bound = rev if rev != UNKNOWN_VERSION else None
        if unknown or own_edits:
            source_as_dir = pathlib.Path(source)
            probe_dir = source_as_dir if source_as_dir.is_dir() else src_dir
            history_repo, reason = git_history_root(probe_dir)
            if history_repo is not None:
                if is_shallow_clone(history_repo):
                    # клон был --depth 1 — истории в нём нет, догружаем ПОЛНОСТЬЮ
                    subprocess.run(["git", "-C", str(history_repo), "fetch", "--unshallow"],
                                   capture_output=True, text=True)
                for rel in unknown:
                    git_rel = git_rel_of.get(rel)
                    history[rel] = (find_version_span(history_repo, git_rel,
                                                       dest_of(rel).read_bytes(),
                                                       anchor_rev=bound)
                                    if git_rel else {"found": False})
            else:
                history_unavailable = reason

        # ═══ КАРТОЧКА #677 (Э3, находка контура AIA 2026-10-05 21:30 UTC): «❓», чей текст
        # НАЙДЕН в истории пакета, своей правки не несёт — это просто старая версия пакета.
        # 🪤 До этой правки инструмент сам печатал «версия пакета от <дата> (коммит …)» и всё равно
        # держал файл в «❓» с требованием --overwrite-unknown: потребитель стоял на шаге
        # обновления, мерил руками то, что инструмент уже знал, и получал письмо-поправку.
        # ⇒ такой файл обновляется как «≠» и получает отпечаток. В «❓» остаётся только текст,
        # которого в просмотренной истории нет, и случаи, когда истории нет вовсе.
        # ⚖️ ГРАНИЦА, названная вслух: роль, НАРОЧНО вернувшая файл к старой версии пакета без
        # отпечатка, отличима от «не трогала» ничем — такой файл обновится. С отпечатком та же
        # роль видна как «✋» (текст разошёлся с отпечатком) — этот путь правка не трогает.
        old_pack = [rel for rel in unknown if (history.get(rel) or {}).get("found")]
        unknown = [rel for rel in unknown if rel not in old_pack]

        # ═══ КАРТОЧКА #609: для «✋» — менял ли пакет файл ПОСЛЕ опоры (отпечатка установки).
        # Опора уже есть — её ТЕКСТ ищется в истории пакета по отпечатку (не по содержимому,
        # как у «❓»: у own_edits текущее содержимое НЕ РАВНО ни опоре, ни пакету — это и
        # значит «правлен у себя», искать нечего им самим).
        base_status: dict = {}
        for rel in own_edits:
            fp = fingerprints.get(fingerprint_key(rel))
            git_rel = git_rel_of.get(rel)
            if history_repo is None:
                base_status[rel] = f"опору найти нечем: истории пакета нет — {history_unavailable}"
                continue
            if not git_rel:
                base_status[rel] = "опору найти нечем: путь не встретился внутри истории пакета"
                continue
            found = find_version_by_fingerprint(history_repo, git_rel, fp, anchor_rev=bound)
            if not found.get("found"):
                base_status[rel] = ("опору найти нечем: версия с отпечатком установки в "
                                    "истории пакета не встретилась")
                continue
            changed = found["changed"]
            if changed:
                shown = ", ".join(f"{h} ({d})" for h, d in changed[:5])
                more = f" и ещё {len(changed) - 5}" if len(changed) > 5 else ""
                base_status[rel] = (f"пакет менял этот файл после опоры (от {found['date']}, "
                                    f"коммит {found['commit']}): да — коммиты {shown}{more}")
            else:
                base_status[rel] = (f"пакет после опоры (от {found['date']}, коммит "
                                    f"{found['commit']}) не менял")

        for rel in new_files:
            print(f"   + {show_name(rel):40} нет у нас — появится{where(rel)}")
        for rel in fresh:
            print(f"   ≠ {show_name(rel):40} отличается — обновится{where(rel)}")
        for rel in old_pack:
            span = history[rel]
            tail = (f"; пакет сменил её {span['changed_date']} (коммит {span['changed_commit']})"
                    if span.get("changed_commit") else "")
            print(f"   ≠ {show_name(rel):40} отличается — обновится: отпечатка установки нет, текст — "
                  f"версия пакета от {span['date']} (коммит {span['commit']}){tail} — своей правки нет"
                  f"{where(rel)}")
        for rel in own_edits:
            print(f"   ✋ {show_name(rel):40} ПРАВЛЕН У ТЕБЯ — НЕ трогаем{where(rel)}")
            print(f"      {base_status.get(rel, 'опору найти нечем: не проверено')}")
        for rel in unknown:
            if history_unavailable is not None:
                tail = f" — истории у источника нет — дату назвать нечем ({history_unavailable})"
            else:
                span = history.get(rel) or {"found": False}
                if span.get("found"):
                    tail = f" — версия пакета от {span['date']} (коммит {span['commit']})"
                    tail += (f"; пакет сменил её {span['changed_date']} (коммит "
                            f"{span['changed_commit']})" if span.get("changed_commit")
                            else "; пакет держит её и сейчас")
                else:
                    tail = " — в истории пакета такого содержимого нет"
            print(f"   ❓ {show_name(rel):40} отличается, но отпечатка установки нет{tail}{where(rel)}")
        if not (fresh or new_files or own_edits or unknown or old_pack):
            print("   инструменты совпадают с источником — забирать нечего")
        print()
        print("⚖️ Сличалось СОДЕРЖИМОЕ, а не байты: окончания строк приведены, иначе "
              "переехавший файл выглядит переписанным целиком.")
        if own_edits:
            print(f"✋ Своих правок: {len(own_edits)} — они НЕ будут затёрты. Хочешь взять свежее — "
                  f"перенеси свою правку сам или удали файл.")
            print("   Или сведи автоматически непересекающиеся места: --merge <файл> положит "
                  "черновик РЯДОМ (живой файл не тронут); без пересечений — сразу "
                  "--accept-merge <файл> --apply.")
            if any(is_second_rel(r) for r in own_edits):
                print("   Для файлов второго каталога сведение (--merge) не работает — свою правку "
                      "в них сводят руками.")
        if old_pack:
            print(f"≠ Без отпечатка установки, но текст — версия пакета из его истории: "
                  f"{len(old_pack)} — своей правки в них нет, обновятся и получат отпечаток.")
        if unknown:
            print(f"❓ Отпечатков установки нет у {len(unknown)} файлов: контур собран "
                  f"раньше, чем их стали писать.{NEWLINE}   Различить «правил ты» и «правил "
                  f"источник» НЕЧЕМ. Молча они не обновятся — нужен --overwrite-unknown, "
                  f"и тогда{NEWLINE}   свои правки в этих файлах будут потеряны. Это цена, "
                  f"названная ДО действия.")
        if out_of_scope:
            print(f"ℹ️ Вне обновления: {len(out_of_scope)} звеньев источника, которых у тебя нет "
                  f"({', '.join(str(x) for x in out_of_scope[:4])}"
                  f"{'…' if len(out_of_scope) > 4 else ''}).{NEWLINE}   Их не зовёт ни один скрипт "
                  f"источника — сборка их не кладёт, обновление не приносит и не выдумывает "
                  f"(звенья, которые скрипты зовут, приезжают строкой «+»).")

        # 🪤 КАРТОЧКА #604 ②б: --source НА ОДИН РАЗ НЕ СТАНОВИТСЯ ЗАПИСЬЮ МОЛЧА. Источник
        # в meta трогается только когда он ещё пуст (первая запись) или по явному
        # --record-source; иначе он остаётся тем, что уже записано. template_commit
        # пишется ВСЕГДА — тем коммитом, который реально взят (a.rev или HEAD).
        recorded_source = got.get("template_source")
        write_source = bool(a.record_source) or not recorded_source

        if not a.apply:
            # находка AIA 05.10: «Ничего не записано» и через три строки «🧹 убрано временных
            # каталогов» читались как противоречие — называем, ЧТО убирается и что это не контур
            copy_note = (" Временную копию источника, взятую для сличения, инструмент убирает при "
                         "выходе — о ней строка «🧹 убрано временных каталогов»." if temporary else "")
            print(f"{NEWLINE}[ПЛАН] В контур ничего не записано.{copy_note} Забрать: тот же вызов "
                  f"с --apply")
            print_pack_rules_summary(db, tools, src_dir)
            return 0

        taking = fresh + new_files + old_pack + (unknown if a.overwrite_unknown else [])
        for rel in taking:
            dest_of(rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_index[rel], dest_of(rel))
        # 🪤 ОТПЕЧАТОК ОБНОВЛЯЕТСЯ ТОЛЬКО У ТОГО, ЧТО МЫ ПОЛОЖИЛИ САМИ. Первая редакция
        # переписывала отпечатки ВСЕХ файлов подряд — в том числе тех, что роль правила
        # у себя и которые мы честно не тронули. Их правка становилась «тем, что мы
        # установили», и следующее обновление затёрло бы её МОЛЧА, считая неправленой.
        # ⇒ Обещание сохранности держалось бы ровно один заход. Поймано приёмкой (⑧),
        # а не рассуждением: контроль без отпечатков проходил, потому что отпечатки
        # тут же появлялись заново.
        updated_fingerprints = dict(fingerprints)
        for rel in taking:
            mine = dest_of(rel)
            if mine.exists():
                updated_fingerprints[fingerprint_key(rel)] = digest(mine.read_bytes())
        meta_updates = [("template_commit", rev),
                        ("template_files_sha", json.dumps(updated_fingerprints, ensure_ascii=False))]
        if write_source:
            meta_updates.append(("template_source", source))
        conn = sqlite3.connect(str(db))
        for k, v in meta_updates:
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        conn.commit()
        conn.close()
        print(f"{NEWLINE}✅ Забрано файлов: {len(taking)} · записана версия {rev} · "
              f"отпечатков установки записано {len(updated_fingerprints)}"
              + (f" · из забранных — во второй каталог: {sum(1 for r in taking if is_second_rel(r))}"
                 if second_dir is not None else ""))
        print("источник в meta: " + (f"записан {source}" if write_source
                                     else f"оставлен {recorded_source}"))
        if own_edits:
            print(f"✋ НЕ тронуто твоих правок: {len(own_edits)} — "
                  + " · ".join(show_name(x) + ("  (второй каталог)" if is_second_rel(x) else "")
                               for x in own_edits))
        if unknown and not a.overwrite_unknown:
            # 🪤 ВОЗВРАТ OPSSRE (карточка #604 ③-3): здесь стояло ложное обещание — «теперь
            # отпечатки есть, и следующий прогон скажет про них определённо». Неправда:
            # отпечаток пишется ТОЛЬКО взятым файлам (и так и должно быть — см. комментарий
            # у updated_fingerprints выше: отпечаток у НЕвзятого файла сделал бы его правку
            # невидимой). Значит эти файлы отпечатка не получат и на СЛЕДУЮЩЕМ прогоне снова
            # придут «❓» — обещание «скажет определённо» никогда не сбывается само.
            print(f"❓ НЕ тронуто без отпечатка: {len(unknown)} — они останутся «❓» и в "
                  f"следующих прогонах: без отпечатка инструмент не отличит твою правку от "
                  f"старой версии пакета. Взять версию пакета — тот же вызов с "
                  f"--overwrite-unknown; оставить свои — ничего не делать.")
        print("👉 ОБЯЗАТЕЛЬНО СЛЕДОМ: прогони свои проверки (guard-all.py). Инструмент, "
              "приехавший и не прогнанный, — это не обновление, а надежда.")
        print_pack_rules_summary(db, tools, src_dir)
        return 0
    finally:
        if temporary:
            mezo_stand.release(src_dir)   # 🩸 было `rmtree(ignore_errors=True)` — см. шапку fetch()


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
