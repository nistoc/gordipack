# -*- coding: utf-8 -*-
"""Общие fixtures для контрактных тестов gordipack.

Что здесь проверяется и чем: скрипты пакета запускаются отдельным процессом, как их
запускает роль, и судятся по контракту — код выхода, вывод, итоговое состояние базы.
Внутренности не импортируются (кроме маленьких модулей-списков вроде
schema_step_order.py), чтобы тесты пережили переписывание кода.

Изоляция: никакого живого контура, сети и секретов. Каждый тест получает свою копию
свежего контура во временной папке; переменные MEZO_*, CLAUDE_CODE_SESSION_ID и
домашняя папка подменяются, чтобы скрипт не нашёл чужую базу или хранилище сессий.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# Скрипты из scripts/ импортируют друг друга по пути; без этого флага рядом с ними
# появились бы __pycache__ — рабочее дерево владельца должно остаться чистым.
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
MIGRATIONS = SCRIPTS / "migrations"
SCHEMA_DIR = REPO_ROOT / "schema"
INIT_GROUP = SCRIPTS / "init-group.py"
SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

# Роли контура, которым собирается общий шаблон. Первая — координатор (как в init-group.py).
DEFAULT_ROLES = ("COORD", "CORE", "STUD")

# Переменные среды, по которым скрипты находят ЖИВОЙ контур или живую роль.
_ENV_DROP_PREFIXES = ("MEZO_",)
_ENV_DROP_NAMES = {"CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR", "PYTHONSTARTUP"}


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshots", action="store_true", default=False,
        help="перезаписать файлы tests/snapshots/ текущим состоянием вместо сравнения")


@pytest.fixture(scope="session")
def update_snapshots(request):
    return request.config.getoption("--update-snapshots")


def clean_env(home, extra=None):
    """Среда подпроцесса без признаков живого контура; домашняя папка — временная."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(_ENV_DROP_PREFIXES) and k not in _ENV_DROP_NAMES}
    home = Path(home)
    (home / "AppData" / "Roaming").mkdir(parents=True, exist_ok=True)
    env.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "PYTHONDONTWRITEBYTECODE": "1",
        # Вывод скриптов — по-русски и с эмодзи; на Windows без этого кодировка канала
        # зависела бы от языка системы раннера, а не от кода пакета.
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    if extra:
        env.update(extra)
    return env


@dataclass
class Result:
    """Итог запуска: код выхода и вывод (stdout + stderr вместе — в `out`)."""
    returncode: int
    stdout: str
    stderr: str
    args: list = field(default_factory=list)

    @property
    def out(self):
        return self.stdout + self.stderr

    def explain(self):
        """Текст для сообщения об ошибке assert: команда, код и хвост вывода."""
        tail = self.out[-4000:]
        return f"команда: {self.args}\nкод выхода: {self.returncode}\nвывод (хвост):\n{tail}"


def run_python(script, *args, cwd=None, input=None, env=None, home=None, timeout=300):
    """Запустить .py отдельным процессом текущего интерпретатора."""
    if env is None:
        env = clean_env(home or cwd or REPO_ROOT)
    argv = [sys.executable, str(script), *[str(a) for a in args]]
    # Без input — пустой stdin: скрипт, спросивший что-то у человека, не повиснет.
    stdin = subprocess.DEVNULL if input is None else None
    p = subprocess.run(argv, cwd=str(cwd) if cwd else None, input=input, stdin=stdin,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=timeout)
    return Result(p.returncode, p.stdout, p.stderr, argv)


def latest_schema_file():
    """Самый свежий schema/mezosync_v<N>.sql — по числу N, а не по алфавиту."""
    def num(p):
        digits = "".join(ch for ch in p.stem.split("_v")[-1] if ch.isdigit())
        return int(digits or 0)
    files = sorted(SCHEMA_DIR.glob("mezosync_v*.sql"), key=num)
    assert files, "в schema/ нет ни одного mezosync_v*.sql"
    return files[-1]


def schema_milestone(schema_file):
    """mezosync_v6.sql → 'v6' (так же init-group.py называет веху базовой схемы)."""
    return "v" + "".join(ch for ch in schema_file.stem.split("_v")[-1] if ch.isdigit())


def load_module(name):
    """Импортировать модуль из scripts/ (только модули с именами без дефиса)."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import importlib
    return importlib.import_module(name)


def schema_shape(conn):
    """Таблицы → {колонка: тип} и список view — то, что фиксирует snapshot схемы."""
    tables = {}
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
        tables[name] = {c[1]: (c[2] or "").upper() for c in cols}
    views = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]
    return {"tables": tables, "views": views}


def schema_sql_dump(conn):
    """Вся структура базы текстом (sqlite_master без данных) — для сравнения «до/после»."""
    return sorted(conn.execute(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%'").fetchall())


def row_counts(conn):
    """Число строк в каждой таблице — для проверки «повторный прогон ничего не дублирует»."""
    return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")}


def run_init_group(container, *args, name="test-circuit", roles=DEFAULT_ROLES,
                   cwd=None, input=None, home=None):
    """Собрать контур init-group.py в <container>/.mezosync. Возвращает Result."""
    argv = ["--name", name, "--path", str(Path(container) / ".mezosync")]
    if roles is not None:
        argv += ["--roles", *roles]
    argv += list(args)
    return run_python(INIT_GROUP, *argv, cwd=cwd or container, input=input,
                      home=home or Path(container).parent / "home")


@dataclass
class Circuit:
    """Собранный контур во временной папке: <root>/.mezosync/{mezosync.db,scripts/}."""
    root: Path
    home: Path
    roles: tuple = DEFAULT_ROLES

    @property
    def mezosync(self):
        return self.root / ".mezosync"

    @property
    def db(self):
        return self.mezosync / "mezosync.db"

    @property
    def scripts(self):
        return self.mezosync / "scripts"

    @property
    def coordinator(self):
        return self.roles[0]

    def env(self, extra=None):
        return clean_env(self.home, extra)

    def run(self, script_name, *args, input=None, env_extra=None, timeout=300):
        """Запустить КОПИЮ скрипта, лежащую в контуре (так её зовёт роль)."""
        return run_python(self.scripts / script_name, *args, cwd=self.root, input=input,
                          env=self.env(env_extra), timeout=timeout)

    def connect(self):
        return sqlite3.connect(str(self.db))

    def query(self, sql, params=()):
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def scalar(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0][0] if rows else None


@pytest.fixture(scope="session")
def circuit_template(tmp_path_factory):
    """Один контур, собранный init-group.py на всю сессию. Тестам — только через `circuit`."""
    base = tmp_path_factory.mktemp("template")
    container = base / "circuit"
    container.mkdir()
    res = run_init_group(container, name="template", home=base / "home")
    if res.returncode != 0:
        pytest.fail("init-group.py не собрал шаблонный контур:\n" + res.explain())
    return {"root": container, "home": base / "home", "result": res}


@pytest.fixture
def circuit(tmp_path, circuit_template):
    """Своя копия свежего контура для каждого теста: тест может менять её как угодно."""
    root = tmp_path / "circuit"
    shutil.copytree(circuit_template["root"], root)
    home = tmp_path / "home"
    home.mkdir()
    return Circuit(root=root, home=home)


@pytest.fixture
def isolated_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return home
