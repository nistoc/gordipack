# -*- coding: utf-8 -*-
"""
mezo_paths.py — ПРОТОТИП механизма R15a: инструмент координации не зависит от рабочего каталога.

ЗАЧЕМ (полевые факты 2026-07-25, не теория):
  · CORE #2669  — `write-message.py` дважды упал `can't open file`, потому что предыдущая команда
    его же работы сделала `cd` в подкаталог репозитория.
  · ING #2673   — тот же класс; у ING он ЗАПИСАН предупреждением в слепке — и протёк ДВАЖДЫ за смену.
  · COORD #2683 — укусил его через 4 минуты после того, как он внёс класс в план как «известную боль».
  ⇒ Три независимых срабатывания за одну смену. Дисциплина здесь доказанно не держит.

ЧТО ЗАКРЫВАЕТ, А ЧТО НЕТ — граница названа честно:
  ✅ ЗАКРЫВАЕТ поиск БД и ресурсов: скрипт находит их от СВОЕГО расположения, а не от CWD.
     Сюда же — ТИХИЙ подкласс: относительный путь к БД при смещённом CWD заставляет
     `sqlite3.connect` МОЛЧА создать пустую БД-фантом (ровно из-за этого заведён гард ⑤;
     в живом контуре такой дефолт до сих пор стоит в `dashboard.py:410`).
     Тихий отказ дороже громкого: громкий стоит повторного вызова, тихий — пяти суток фантома.
  ⛔ НЕ ЗАКРЫВАЕТ запуск самого скрипта относительным путём (`python .mezosync/scripts/x.py`):
     интерпретатор ищет файл ДО того, как этот код начнёт исполняться. Изнутри скрипта это
     нерешаемо в принципе. Вторая половина — R15b, гард `guard-relative-invocations.py`:
     он лечит ИСТОЧНИК относительной формы (канон и памяти), а не память ролей.

Использование в скрипте:
    from mezo_paths import resolve_db
    ap.add_argument("--db", default=None)      # больше не required
    db = resolve_db(args.db, __file__)
"""
from pathlib import Path
import sys

DB_NAME = "mezosync.db"


def mezo_root(script_file) -> Path:
    """Корень контейнера мезосинка — ближайший предок скрипта, где лежит mezosync.db.

    Подъём, а не жёсткое `parent.parent`: скрипт может лежать в scripts/, в scripts/guards/
    или быть вызван из копии-песочницы. Ищем ПРИЗНАК (файл БД), а не угадываем глубину —
    тот же принцип, по которому гард ⑤ судит фантомную БД по «ноль таблиц», а не по месту.
    """
    p = Path(script_file).resolve().parent
    for cand in (p, *p.parents):
        if (cand / DB_NAME).exists():
            return cand
    # Не нашли — отдаём ожидаемое место (scripts/../), чтобы сообщение об ошибке было предметным.
    return Path(script_file).resolve().parent.parent


def default_db(script_file) -> Path:
    return mezo_root(script_file) / DB_NAME


def resolve_db(arg, script_file, must_exist: bool = True) -> Path:
    """Единственная точка, где путь к БД превращается в абсолютный.

    Три случая, и ни один не зависит от CWD:
      1. `--db` не задан        → дефолт от расположения скрипта;
      2. `--db` абсолютный      → как есть (обратная совместимость: все живые вызовы такие);
      3. `--db` ОТНОСИТЕЛЬНЫЙ   → резолвится ОТ КОРНЯ МЕЗОСИНКА, а НЕ от текущего каталога.
         Случай 3 — сердце фикса: сегодня он резолвится от CWD и потому либо падает,
         либо (хуже) молча создаёт фантом.

    must_exist=True: несуществующий путь — ГРОМКАЯ ошибка с названной причиной, не тихое
    создание пустой БД. «Ошибка должна указывать на причину, а не на симптом» (CORE #2669:
    `can't open file` указывал на скрипт, хотя виноват был сменившийся каталог).
    """
    root = mezo_root(script_file)
    if arg is None:
        db = root / DB_NAME
    else:
        p = Path(arg)
        db = p if p.is_absolute() else (root / p)
    db = db.resolve()
    if must_exist and not db.exists():
        sys.exit(
            f"ERR: БД не найдена: {db}\n"
            f"     Корень мезосинка (по расположению скрипта): {root}\n"
            f"     Путь резолвился ОТ КОРНЯ, не от текущего каталога — смена CWD ни при чём.\n"
            f"     Если БД лежит в другом месте, укажи АБСОЛЮТНЫЙ --db."
        )
    return db

# ═══ КОНТЕЙНЕР ГРУППЫ И КОРЕНЬ ШАБЛОНА — БЕЗ ЛИТЕРАЛОВ МАШИНЫ (карточка #153 ③) ═══
# 🪤 До 09.08 путь контейнера был ВПЕЧАТАН в ~75 местах сорока файлов, и все копии уезжали
# в ПУБЛИЧНЫЙ шаблон. Замер шире моей же карточки («18 в 12») — числа в карточках стареют
# так же, как в слепках. Теперь путь живёт НИГДЕ: он ВЫВОДИТСЯ, в порядке:
#   ① переменная среды (явное сильнее выведенного);
#   ② подъём от расположения файла по МАРКЕРУ (.mezosync/mezosync.db — признак, не глубина);
#   ③ local.paths РЯДОМ С ЭТИМ ФАЙЛОМ — локальный непубликуемый файл (в .gitignore):
#      нужен копии, живущей ВНЕ контейнера (шаблон на этой машине);
#   ④ ГРОМКИЙ отказ с рецептом. Тихий дефолт был бы путём машины под другим именем.
_LOCAL = Path(__file__).resolve().parent / "local.paths"


def _local_get(key: str):
    if not _LOCAL.exists():
        return None
    for line in _LOCAL.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return Path(line.split("=", 1)[1].strip())
    return None


def container_root(script_file=None) -> Path:
    import os
    env = os.environ.get("MEZO_CONTAINER")
    if env:
        return Path(env)
    start = Path(script_file or __file__).resolve().parent
    for cand in (start, *start.parents):
        if (cand / ".mezosync" / DB_NAME).exists():
            return cand
    loc = _local_get("container")
    if loc and (loc / ".mezosync" / DB_NAME).exists():
        return loc
    sys.exit("ERR: контейнер группы НЕ НАЙДЕН (маркер .mezosync/mezosync.db не встретился "
             "вверх по дереву).\n     Задай MEZO_CONTAINER=<путь> либо создай рядом с "
             f"mezo_paths.py файл local.paths со строкой container=<путь>.\n"
             f"     Искал от: {start}")


def live_db(script_file=None) -> Path:
    return container_root(script_file) / ".mezosync" / DB_NAME


def live_scripts(script_file=None) -> Path:
    return container_root(script_file) / ".mezosync" / "scripts"


def template_root(script_file=None) -> Path:
    """Корень репозитория-шаблона: маркер scripts/init-group.py; иначе local.paths/среда."""
    import os
    env = os.environ.get("MEZO_TEMPLATE")
    if env:
        return Path(env)
    start = Path(script_file or __file__).resolve().parent
    for cand in (start, *start.parents):
        # 🪤 ОТСЕЧКА, НАЙДЕННАЯ @COORD 2026-08-20 06:12 UTC ПРОГОНОМ У СЕБЯ, И ЭТО ВАЖНО:
        # маркер `scripts/init-group.py` НЕ РАЗЛИЧАЕТ образец и рабочий контур — контур
        # собран ИЗ образца и несёт тот же файл. В МОЕЙ раскладке дефект невидим (моя копия
        # лежит внутри самого образца, и подъём находит верный корень раньше), а у него
        # первым кандидатом шёл его собственный контейнер, и функция уверенно выдавала его
        # за корень образца. Признак живого контура — база рядом; у образца её нет по
        # построению. Обе формы: база в САМОМ кандидате (…/.mezosync/mezosync.db) и в его
        # подкаталоге (…/.atlas). Первая редакция отсечки проверяла только вторую и
        # промахнулась — поймано прогоном, не рассуждением.
        # 🎯 Класс мой же, в третий раз за сутки: признак, одинаковый у обеих сред,
        # не различает того, что обещает именем. Невидимость дефекта зависит от раскладки.
        if (cand / ".mezosync" / DB_NAME).exists() or (cand / DB_NAME).exists():
            continue
        if (cand / "scripts" / "init-group.py").exists():
            return cand
    loc = _local_get("template")
    if loc and (loc / "scripts" / "init-group.py").exists():
        return loc
    sys.exit("ERR: корень шаблона НЕ НАЙДЕН (маркер scripts/init-group.py).\n"
             "     Задай MEZO_TEMPLATE=<путь> либо строку template=<путь> в local.paths.")

