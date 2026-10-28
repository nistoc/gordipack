# -*- coding: utf-8 -*-
"""Приёмка vnext/prototype/bite-shown-count.py: ветвь «колонки "показано" нет» исполняется.

Находка из описания PR #45 (ruff F821): строка отказа этой ветви называла список CANDIDATES,
снятый 2026-08-08 (e528f69, слово владельца «убери этот выбор колонки»), и вместо итога
«правки ещё нет» приёмка падала NameError. Ветвь живёт ровно для контура, в чьей базе у
read_batches нет колонки shown_max, — такой контур тест и собирает: свежий из init-group.py,
колонка снята. Контроль — тот же свежий контур с колонкой: приёмка проходит.

Только временные папки и временные базы: живого контура, сети и секретов тест не касается.
Запуск из корня репозитория (зависимостей нет, нужен Python 3.12+):
    python -m unittest discover -s tests -p "test_bite_shown_count.py" -v
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_GROUP = REPO_ROOT / "scripts" / "init-group.py"
BITE = REPO_ROOT / "vnext" / "prototype" / "bite-shown-count.py"


def clean_env(home, **extra):
    """Среда подпроцесса без признаков живого контура; домашняя и временная папки — свои."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("MEZO_") and k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SESSION_ID")}
    home = Path(home)
    tmp = home / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env.update({"HOME": str(home), "USERPROFILE": str(home),
                "TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    env.update(extra)
    return env


def run_py(script, *args, env):
    p = subprocess.run([sys.executable, str(script), *map(str, args)], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=600)
    return p.returncode, p.stdout + p.stderr


class ShownCountBiteTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gordipack-shown-count-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db = self.tmp / ".mezosync" / "mezosync.db"
        code, out = run_py(INIT_GROUP, "--name", "shown-count-test", "--path", self.tmp / ".mezosync",
                           "--roles", "coord", env=clean_env(self.tmp / "home"))
        self.assertEqual(code, 0, f"init-group.py: код {code}\n{out[-3000:]}")
        # контейнер называем средой: временная папка лежит вне раскладки «пакет рядом с контуром»
        self.env = clean_env(self.tmp / "home", MEZO_CONTAINER=str(self.tmp))

    def test_without_shown_column_reports_exact_name_without_name_error(self):
        if sqlite3.sqlite_version_info < (3, 35, 0):
            self.skipTest(f"ALTER TABLE … DROP COLUMN нужен SQLite 3.35+, здесь {sqlite3.sqlite_version}")
        conn = sqlite3.connect(str(self.db))
        conn.execute("ALTER TABLE read_batches DROP COLUMN shown_max")
        conn.commit()
        conn.close()
        code, out = run_py(BITE, env=self.env)
        self.assertNotIn("Traceback", out, out[-3000:])
        self.assertNotIn("NameError", out)
        self.assertIn("НЕ НАЙДЕНА", out, out[-3000:])
        self.assertIn("'shown_max'", out, "строка отказа обязана назвать имя, которое искали")
        self.assertIn("правки ещё нет", out)
        self.assertEqual(code, 1, "по шапке приёмки: 1 — поля ещё нет")

    def test_with_shown_column_all_properties_hold(self):
        """Контроль: на том же свежем контуре с колонкой приёмка не уходит в ветвь отказа."""
        code, out = run_py(BITE, env=self.env)
        self.assertEqual(code, 0, out[-3000:])
        self.assertNotIn("НЕ НАЙДЕНА", out)
        self.assertIn("ВСЕ СВОЙСТВА ДЕРЖАТСЯ", out)


if __name__ == "__main__":
    unittest.main()
