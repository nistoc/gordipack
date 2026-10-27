# -*- coding: utf-8 -*-
"""Журнал шагов у контура, собранного из базовой схемы (находка из описания PR #45).

Контракт — scripts/schema_step_order.py (BASE_STEPS) и scripts/init-group.py (блок 6а):
  · новый контур несёт в schema_migrations строки шагов, вшитых в базовую схему, — тот же
    журнал и ту же структуру, что у контура из предыдущей базовой схемы, обновлённого шагами;
  · повторный прогон всех шагов журнал не меняет и ничего не дублирует;
  · BASE_STEPS сходится с каталогом migrations/ и с вехой самого свежего файла схемы.

Только временные папки и временные базы: живого контура, сети и секретов тест не касается.
Запуск из корня репозитория (зависимостей нет, нужен Python 3.12+):
    python -m unittest discover -s tests -p "test_base_schema_journal.py" -v
"""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Модули scripts/ импортируются по пути; рабочее дерево не должно обрастать __pycache__.
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
MIGRATIONS = SCRIPTS / "migrations"
sys.path.insert(0, str(SCRIPTS))

import schema_journal  # noqa: E402
import schema_step_order  # noqa: E402

MILESTONE_FILE = re.compile(r"^(\d{8})-milestone-(v\d+)$")


def schema_number(path):
    return int("".join(ch for ch in path.stem.split("_v")[-1] if ch.isdigit()) or 0)


LATEST_SCHEMA = max((REPO_ROOT / "schema").glob("mezosync_v*.sql"), key=schema_number)
BASE_MILESTONE = f"v{schema_number(LATEST_SCHEMA)}"


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


def journal(db):
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT rowid, version, applied_at, note, fingerprint, applied_by "
                            "FROM schema_migrations ORDER BY rowid").fetchall()
        version = conn.execute("SELECT version, steps_total, steps_after_milestone "
                               "FROM schema_version").fetchone()
        verified = schema_journal.verify(conn)
        shape = schema_journal.fingerprint(conn)
    finally:
        conn.close()
    return {"rows": rows, "names": [r[1] for r in rows], "version": version,
            "verified": verified, "shape": shape}


class BaseStepsListTest(unittest.TestCase):
    """BASE_STEPS — список с именами файлов, а не проза: сверяем его с диском и со схемой."""

    def test_ends_with_milestone_of_latest_schema(self):
        self.assertTrue(schema_step_order.BASE_STEPS)
        self.assertEqual(schema_step_order.journal_version(schema_step_order.BASE_STEPS[-1]),
                         BASE_MILESTONE, f"BASE_STEPS обязан кончаться вехой {LATEST_SCHEMA.name}")

    def test_starts_with_milestone_that_has_schema_file(self):
        first = MILESTONE_FILE.match(schema_step_order.BASE_STEPS[0])
        self.assertIsNotNone(first, "первый элемент BASE_STEPS — веха предыдущей базовой схемы")
        self.assertTrue((REPO_ROOT / "schema" / f"mezosync_{first.group(2)}.sql").is_file())

    def test_names_are_files_unique_and_not_in_other_lists(self):
        base = schema_step_order.BASE_STEPS
        self.assertEqual(len(base), len(set(base)), "повтор имени в BASE_STEPS")
        for step in base:
            self.assertTrue((MIGRATIONS / f"{step}.py").is_file(), f"нет файла шага {step}.py")
        self.assertFalse(set(base) & set(schema_step_order.STEPS), "шаг и в BASE_STEPS, и в STEPS")
        self.assertFalse(set(base) & set(schema_step_order.NOT_SCHEMA_STEPS))

    def test_covers_every_step_file_between_its_milestones(self):
        """Дыры в середине нет: каждый файл шага от первой вехи списка до вехи базы — в списке."""
        base = schema_step_order.BASE_STEPS
        lo, hi = base[0][:8], base[-1][:8]
        on_disk = {p.stem for p in MIGRATIONS.glob("*.py") if lo < p.stem[:8] <= hi}
        self.assertEqual(on_disk - set(base) - set(schema_step_order.NOT_SCHEMA_STEPS), set())


class FreshCircuitJournalTest(unittest.TestCase):
    """Свежий контур из init-group.py против контура из предыдущей базы, обновлённого шагами."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gordipack-journal-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, ignore_errors=True)
        cls.env = clean_env(cls.tmp / "home")

        # ① свежий контур — как его собирает пользователь пакета
        cls.container = cls.tmp / "fresh"
        cls.container.mkdir()
        cls.fresh_db = cls.container / ".mezosync" / "mezosync.db"
        code, out = run_py(SCRIPTS / "init-group.py", "--name", "journal-test",
                           "--path", cls.container / ".mezosync", "--roles", "coord",
                           env=cls.env)
        if code != 0 or not cls.fresh_db.is_file():
            raise AssertionError(f"init-group.py: код {code}\n{out[-3000:]}")
        cls.fresh = journal(cls.fresh_db)

        # ② контур из предыдущей базовой схемы, обновлённый шагами BASE_STEPS и STEPS по порядку
        # (так init-group.py собирал новый контур до подъёма базы и так обновлялись контуры ниже неё)
        prev = MILESTONE_FILE.match(schema_step_order.BASE_STEPS[0]).group(2)
        cls.stand = cls.tmp / "upgraded"
        (cls.stand / ".mezosync").mkdir(parents=True)
        cls.stand_db = cls.stand / ".mezosync" / "mezosync.db"
        conn = sqlite3.connect(str(cls.stand_db))
        conn.executescript((REPO_ROOT / "schema" / f"mezosync_{prev}.sql").read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version, note, fingerprint) VALUES (?, ?, ?)",
                     (prev, f"сборка из шаблона gordipack (mezosync_{prev}.sql)",
                      schema_journal.fingerprint(conn)))
        conn.commit()
        conn.close()
        stand_env = clean_env(cls.tmp / "home", MEZO_CONTAINER=str(cls.stand))
        for step in [*schema_step_order.BASE_STEPS[1:], *schema_step_order.STEPS]:
            code, out = run_py(MIGRATIONS / f"{step}.py", "--db", cls.stand_db, env=stand_env)
            if code != 0:
                raise AssertionError(f"шаг {step} на стенде из {prev}: код {code}\n{out[-3000:]}")
        cls.upgraded = journal(cls.stand_db)

    def test_fresh_circuit_journals_steps_baked_into_base_schema(self):
        names = self.fresh["names"]
        for step in schema_step_order.BASE_STEPS:
            name = schema_step_order.journal_version(step)
            self.assertEqual(names.count(name), 1, f"{name} в журнале свежего контура: {names}")
        # строка, которой ждёт случай ⓪ приёмки vnext/prototype/bite-messages-archive.py
        self.assertIn("20260905-messages-archive", names)

    def test_baked_rows_stand_before_base_milestone(self):
        names = self.fresh["names"]
        at = names.index(BASE_MILESTONE)
        self.assertEqual(names[:at], [schema_step_order.journal_version(s)
                                      for s in schema_step_order.BASE_STEPS[:-1]])
        self.assertEqual(names[at + 1:], [schema_step_order.journal_version(s)
                                          for s in schema_step_order.STEPS])
        version, _, after = self.fresh["version"]
        self.assertEqual((version, after), (BASE_MILESTONE, len(schema_step_order.STEPS)))
        self.assertTrue(self.fresh["verified"][0], self.fresh["verified"][1])

    def test_baked_rows_are_marked_as_written_by_builder(self):
        baked = {r[1]: r for r in self.fresh["rows"]}
        for step in schema_step_order.BASE_STEPS[:-1]:
            row = baked[schema_step_order.journal_version(step)]
            self.assertEqual(row[5], "tool:init-group.py")
            self.assertIn("ЗАДНИМ ЧИСЛОМ", row[3])

    def test_same_journal_as_previous_base_upgraded_by_steps(self):
        self.assertEqual(self.fresh["names"], self.upgraded["names"])
        self.assertEqual(self.fresh["version"], self.upgraded["version"])
        self.assertEqual(self.fresh["shape"], self.upgraded["shape"],
                         "структура свежего контура разошлась с обновлённым — строки "
                         "вшитых шагов тогда неправда")

    def test_rerun_of_all_steps_changes_nothing(self):
        """Повтор BASE_STEPS и STEPS на копии свежего контура: код 0, журнал байт в байт тот же."""
        copy = self.tmp / "rerun"
        (copy / ".mezosync").mkdir(parents=True)
        db = copy / ".mezosync" / "mezosync.db"
        src = sqlite3.connect(str(self.fresh_db))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        src.close()
        dst.close()
        env = clean_env(self.tmp / "home", MEZO_CONTAINER=str(copy))
        for step in [*schema_step_order.BASE_STEPS, *schema_step_order.STEPS]:
            code, out = run_py(self.container / ".mezosync" / "scripts" / "migrations" / f"{step}.py",
                               "--db", db, env=env)
            self.assertEqual(code, 0, f"повтор шага {step}: код {code}\n{out[-2000:]}")
        again = journal(db)
        self.assertEqual(again["rows"], self.fresh["rows"])
        self.assertEqual(again["version"], self.fresh["version"])


if __name__ == "__main__":
    unittest.main()
