#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard-donor-literals — проверка: в коде ядра пакета нет литералов донора.

    python vnext/tools/guard-donor-literals.py                 # рабочее дерево пакета
    python vnext/tools/guard-donor-literals.py --commit X      # версия X из git
    python vnext/tools/guard-donor-literals.py --reconcile-with <каталог goal-gordi-core> [--reconcile-allowed <перечень>]

ПРЕДМЕТ. Пакет вынут из живого контура-донора и везёт его допущения: имена ролей, пути,
репозитории, соседей, порты. Этап Э3 (карточка #677) выносит их из кода; эта проверка
держит ноль после этого. Что считается находкой — слово владельца 2026-10-04 23:52 UTC (чат
координатора) и развилка В1 б 2026-10-05 10:53 UTC: литерал донора, управляющий ПОВЕДЕНИЕМ, в файле
из перечня ядра — и печатаемая подсказка-команда, которую роль копирует и запускает. Прочий
печатаемый текст, строки происхождения, подставные данные приёмок и шаги схемы — вне счёта,
но не молча, а ПЕРЕЧНЕМ исключений.

ТРИ ФАЙЛА ДАННЫХ рядом (литералы донора допустимы только в них — ни в этой проверке, ни в движке):
  core-files.txt             — перечень файлов ядра (раздел [ядро]) и файлов «вне ядра» с
                               причиной (раздел [вне ядра]: путь, табуляция, причина);
  donor-names.json           — имена донора по группам (формат — шапка donor_scan.py);
  donor-literals-allowed.tsv — перечень исключений. Ключ исключения — (файл, имя, вид, текст
                               строки), НЕ номер строки: номера сдвигаются при правке соседей.

ЧТО СЧИТАЕТСЯ НАХОДКОЙ.
  · попадание вида code или shown в файле из перечня ядра, не покрытое исключением.
    Попадания вида comment и docstring — не находки: комментарий о доноре не управляет
    поведением (и это нужный встречный случай, а не послабление);
  · «файл ядра не в перечне»: любой .py под scripts/ (кроме bite-*.py и каталогов migrations/),
    которого нет ни в разделе [ядро], ни в разделе [вне ядра]. Без этого новый файл переноса
    жил бы вне проверки молча;
  · исключение, которому не нашлось попадания, — печатается строкой «исключение без попадания»
    (не провал; с --strict — провал: так видно, что исключение осталось от уже исправленной строки).

ОТКУДА ЧИТАЕТСЯ ПАКЕТ. По умолчанию — рабочее дерево: файл есть на диске — читается с диска, так
видны и ещё не закоммиченные файлы переноса. Корень — каталог выше vnext/tools. --commit X —
версия X через git. Файлы данных — рядом с этим файлом (--data-dir меняет каталог).

КОД ВЫХОДА. 0 — находок нет · 1 — есть находки (с --strict — и исключения без попадания) ·
2 — проверить не удалось: нет файла данных, git, коммита, файл не разобран — словами, чего
именно. «Не проверено» не бывает «прошла»: код 2 — отдельный исход.

--reconcile-with <каталог goal-gordi-core> — сверка с замером этапа Э2 и счётом Э3 (путь
литералом не задан: его называет тот, кто запускает). Версия берётся из e2/metrics.json
(или --reconcile-commit). (а) движок на этой версии воспроизводит e2/hits.tsv по файлам ядра:
множества (файл, строка, группа, имя, вид) для видов code и shown равны. (б) находки проверки
на этой версии равны строкам класса behavior у e3/count-core.py по (файл, строка, имя). Группы,
которых замер Э2 не видел (роль целой строкой в любом регистре, прочие имена), могут найти
строки, которых нет в счёте Э3: их называют поимённо — класс решает владелец.

ПЕРЕЧЕНЬ ИСКЛЮЧЕНИЙ ДЛЯ СВЕРКИ — ТОЙ ЖЕ ВЕРСИИ, ЧТО СУДИТСЯ. Исключение держится за текст строки,
поэтому перечень годится только версии кода, для которой написан: версию, судимую перечнем другой
версии, проверка осудила бы с ложными расхождениями в обе стороны (до правки так и было: версия замера
Э2 судилась перечнем нового кода — 62 находки вместо 52 счёта Э3). Порядок выбора перечня:
  1. --reconcile-allowed <файл> — перечень, который назвал запускающий: он ручается, что файл написан
     для этой версии (для версии замера Э2 такой лежит рядом: donor-literals-allowed-7e2d2b0.tsv);
  2. перечень, лежащий В САМОМ судимом commit (git show <commit>:vnext/tools/donor-literals-allowed.tsv);
  3. ни того ни другого — отказ словами, код 2 «НЕ ПРОВЕРЕНО». Пустой перечень и перечень рабочего
     дерева НЕ подставляются: пустой сделал бы находкой любую строку вне счёта, рабочего дерева — вернул
     бы прежнюю ошибку. Версия замера Э2 (7e2d2b0) старше перечня: в ней его нет, поэтому её сверка идёт
     по п. 1. Из какого источника взят перечень, сверка печатает строкой «перечень исключений: …».
Файл имён и перечень файлов ядра читаются из каталога данных рабочего дерева: это настройки проверки,
а не суждения о строках конкретной версии.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import donor_scan  # noqa: E402  (движок: разбор .py и поиск имён; имена донора берёт из данных)

CHECKED_KINDS = ("code", "shown")          # виды попаданий, которые считаются находкой
COMPARED_KINDS = ("code", "shown")         # виды, по которым движок сверяется с замером Э2
CORE_FILE = "core-files.txt"
NAMES_FILE = "donor-names.json"
ALLOWED_FILE = "donor-literals-allowed.tsv"
SECTION_CORE = "[ядро]"
SECTION_OUTSIDE = "[вне ядра]"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
LINE_WIDTH = 120


class Incomplete(Exception):
    """Проверить не удалось: слова — в тексте исключения."""


class AllowedRow(NamedTuple):
    file: str
    name: str
    kind: str
    cls: str
    text: str
    reason: str
    number: int          # номер строки в файле исключений (для сообщений об ошибках)


# ---------------------------------------------------------------- данные
def load_core_files(path):
    """-> (список файлов ядра, {файл вне ядра: причина})."""
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        raise Incomplete("нет файла перечня файлов ядра: %s" % path)
    core, outside, section = [], {}, SECTION_CORE
    for number, line in enumerate(raw.replace("\r\n", "\n").split("\n"), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            if s not in (SECTION_CORE, SECTION_OUTSIDE):
                raise Incomplete("%s:%d: неизвестный раздел «%s» (есть %s и %s)" % (path, number, s, SECTION_CORE, SECTION_OUTSIDE))
            section = s
            continue
        if section == SECTION_CORE:
            core.append(s)
        else:
            file, _, reason = line.strip().partition("\t")
            if not file.strip() or not reason.strip():
                raise Incomplete("%s:%d: файл «вне ядра» записывается как путь, табуляция, причина" % (path, number))
            outside[file.strip()] = reason.strip()
    return core, outside


def load_allowed(path):
    """-> [AllowedRow] из файла на диске."""
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        raise Incomplete("нет файла перечня исключений: %s" % path)
    return parse_allowed(raw, path)


def parse_allowed(raw, path):
    """-> [AllowedRow]. Строки с «#» в начале — пояснения; первая строка с заголовком «file» пропускается.
    path — только для сообщений об ошибках (файл на диске или «commit:путь»)."""
    rows = []
    for number, line in enumerate(raw.replace("\r\n", "\n").split("\n"), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0] == "file" and not rows:
            continue
        if len(parts) < 6:
            raise Incomplete("%s:%d: колонок %d, ждали 6 (файл, имя, вид, класс, текст, причина)" % (path, number, len(parts)))
        parts = parts[:5] + ["\t".join(parts[5:])]
        rows.append(AllowedRow(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], number))
    return rows


def allowed_of_commit(root, data_dir, commit):
    """Перечень исключений из САМОГО судимого commit (git show <commit>:<путь перечня>).
    Исключение держится за текст строки кода, поэтому годится только той версии, для которой написано:
    версию, судимую перечнем другой версии, проверка осудила бы с ложными расхождениями в обе стороны
    (лишние находки у строк, которых перечень не знает; исключения без попадания у строк, которых в версии нет).
    Перечня в commit нет — отказ словами (Incomplete), а НЕ пустой перечень: с пустым перечнем любая строка
    вне счёта стала бы находкой, и сверка разошлась бы по причине, которой нет."""
    root, data_dir = Path(root), Path(data_dir)
    try:
        rel_dir = data_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise Incomplete("каталог данных %s лежит вне пакета %s: перечень судимого commit по нему не найти — "
                         "назовите файл перечня ключом --reconcile-allowed" % (data_dir, root))
    rel = ALLOWED_FILE if rel_dir in ("", ".") else "%s/%s" % (rel_dir, ALLOWED_FILE)
    rc, _, err = run_git(root, "rev-parse", "--verify", "--quiet", commit + "^{commit}")
    if rc != 0:
        raise Incomplete("в пакете %s нет commit %s%s" % (root, commit, (": " + err) if err else ""))
    rc, out, _ = run_git(root, "show", "%s:%s" % (commit, rel))
    if rc != 0:
        raise Incomplete("в commit %s нет перечня исключений %s: перечень появился в пакете позже этой версии. "
                         "Судить версию перечнем другой версии нельзя — он держится за текст строк и дал бы ложные "
                         "расхождения в обе стороны. Назовите перечень, написанный для этой версии (по соглашению он "
                         "лежит рядом: donor-literals-allowed-<commit>.tsv), ключом --reconcile-allowed"
                         % (commit, rel))
    return parse_allowed(out.decode("utf-8-sig"), "%s:%s" % (commit, rel))


# ---------------------------------------------------------------- источники файлов
def run_git(root, *args, input_bytes=None):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, input=input_bytes)
    except FileNotFoundError:
        raise Incomplete("git не найден: версию из git прочитать нельзя")
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace").strip()


class TreeSource:
    """Рабочее дерево: файл есть на диске — читается с диска (видны и ещё не закоммиченные)."""
    label = "рабочее дерево"

    def __init__(self, root):
        self.root = Path(root)

    def list_py(self):
        files = None
        try:
            rc, out, _ = run_git(self.root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
            if rc == 0:
                files = [f.decode("utf-8") for f in out.split(b"\0") if f]
        except Incomplete:
            files = None
        if files is None:                       # не репозиторий или нет git — обходим каталог
            files = []
            for d, dirs, names in os.walk(self.root):
                dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
                for n in names:
                    files.append(Path(d, n).relative_to(self.root).as_posix())
        return sorted({f for f in files if f.lower().endswith(".py") and (self.root / f).is_file()})

    def read_all(self, paths):
        return {p: donor_scan.read_text((self.root / p).read_bytes()) for p in paths}


class CommitSource:
    """Версия из git по имени коммита; рабочее дерево не читается."""

    def __init__(self, root, commit):
        self.root = Path(root)
        self.commit = commit
        self.label = "commit %s" % commit

    def list_py(self):
        rc, _, err = run_git(self.root, "rev-parse", "--verify", "--quiet", self.commit + "^{commit}")
        if rc != 0:
            raise Incomplete("в пакете %s нет commit %s%s" % (self.root, self.commit, (": " + err) if err else ""))
        rc, out, err = run_git(self.root, "ls-tree", "-r", "--name-only", "-z", self.commit)
        if rc != 0:
            raise Incomplete("git ls-tree для commit %s не отработал: %s" % (self.commit, err))
        return sorted(f.decode("utf-8") for f in out.split(b"\0") if f.lower().endswith(b".py"))

    def read_all(self, paths):
        texts = {}
        proc = subprocess.Popen(["git", "-C", str(self.root), "cat-file", "--batch"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for path in paths:
                proc.stdin.write(("%s:%s\n" % (self.commit, path)).encode("utf-8"))
                proc.stdin.flush()
                header = proc.stdout.readline().decode("utf-8", "replace").split()
                if len(header) == 3 and header[1] == "blob":
                    data = proc.stdout.read(int(header[2]))
                    proc.stdout.read(1)
                    texts[path] = donor_scan.read_text(data)
        finally:
            proc.stdin.close()
            proc.wait()
        return texts


# ---------------------------------------------------------------- проверка
class Result:
    def __init__(self, root, label):
        self.root = root
        self.label = label
        self.core = []              # файлы ядра из перечня
        self.outside = {}           # файлы вне ядра с причиной
        self.hits = []              # все попадания в файлах ядра: любые группы и виды
        self.findings = []          # попадания code/shown без исключения
        self.covered = 0            # попаданий, покрытых исключением
        self.unlisted = []          # файлы под scripts/ вне перечня
        self.missing = []           # файлы из перечня, которых в пакете нет
        self.allowed_total = 0
        self.allowed_matched = 0
        self.unmatched = []         # исключения без попадания
        self.problems = []          # что помешало проверить полностью
        self.scanned = 0
        self.aborted = False        # проверка оборвалась до разбора файлов: чисел итога нет


def exception_key(file, name, kind, text, line=None):
    """Ключ исключения: файл, имя, вид и ТЕКСТ строки. Номер строки в ключ не входит."""
    return (file, name, kind, text)


def is_runtime_script(path):
    parts = path.split("/")
    return (len(parts) > 1 and parts[0] == "scripts" and path.endswith(".py")
            and "migrations" not in parts[1:-1] and not parts[-1].startswith("bite-"))


def find_unlisted(paths, core_set, outside):
    return sorted(p for p in paths if is_runtime_script(p) and p not in core_set and p not in outside)


def check(root, data_dir, commit=None, allowed=None):
    """Проверка пакета. Ничего не печатает и не пишет. Всё, чего не удалось, — в res.problems.
    allowed — уже прочитанный перечень исключений ([AllowedRow]); без него читается файл из data_dir."""
    root, data_dir = Path(root), Path(data_dir)
    source = CommitSource(root, commit) if commit else TreeSource(root)
    res = Result(root, source.label)
    try:
        names = donor_scan.load_names(data_dir / NAMES_FILE)
        res.core, res.outside = load_core_files(data_dir / CORE_FILE)
        if allowed is None:
            allowed = load_allowed(data_dir / ALLOWED_FILE)
        paths = source.list_py()
        texts = source.read_all(paths)
    except (donor_scan.NamesError, Incomplete) as e:
        res.problems.append(str(e))
        res.aborted = True
        return res
    scanner = donor_scan.Scanner(texts, names)
    index = {}
    for row in allowed:
        key = exception_key(row.file, row.name, row.kind, row.text)
        if key in index:
            res.problems.append("дубль исключения: строки %d и %d файла %s" % (index[key].number, row.number, ALLOWED_FILE))
        else:
            index[key] = row
    res.allowed_total = len(index)
    core_set = set(res.core)
    matched = set()
    for path in res.core:
        if not path.endswith(".py"):
            res.problems.append("файл ядра не .py: %s — проверка читает только .py" % path)
            continue
        if path not in texts:
            res.missing.append(path)
            continue
        hits, notes = scanner.scan(path)
        if hits is None:
            res.problems.append("файл ядра не разобран: %s (%s)" % (path, notes[0]))
            continue
        for note in notes:
            res.problems.append("файл ядра разобран не полностью: %s (%s)" % (path, note))
        res.scanned += 1
        res.hits.extend(hits)
        for h in hits:
            if h.kind not in CHECKED_KINDS:
                continue
            key = exception_key(h.file, h.name, h.kind, h.text, h.line)
            if key in index:
                matched.add(key)
                res.covered += 1
            else:
                res.findings.append(h)
    res.allowed_matched = len(matched)
    res.unmatched = [row for key, row in index.items() if key not in matched]
    res.unlisted = find_unlisted(paths, core_set, res.outside)
    res.findings.sort(key=lambda h: (h.file, h.line, h.group, h.name))
    return res


def measures(findings):
    """Три меры одного множества: строки списка · различные строки файлов · файлы."""
    return (len(findings), len({(h.file, h.line) for h in findings}), len({h.file for h in findings}))


def exit_code(res, strict=False):
    if res.findings or res.unlisted:
        return 1
    if strict and res.unmatched:
        return 1
    if res.problems or res.missing:
        return 2
    return 0


def shorten(text, width=LINE_WIDTH):
    return text if len(text) <= width else text[:width - 1] + "…"


def report(res, strict=False, out=print):
    out("проверка литералов донора в коде ядра пакета: %s · %s" % (res.root, res.label))
    for p in res.problems:
        out("не удалось проверить: %s" % p)
    for p in res.missing:
        out("файл из перечня ядра, которого в пакете нет: %s" % p)
    if res.aborted:
        out("итог: НЕ ПРОВЕРЕНО — файлы пакета не прочитаны, числа находок нет")
        out("НЕ ПРОВЕРЕНО: %s" % res.problems[0])
        return
    out("файлов ядра в перечне: %d · прочитано и проверено: %d" % (len(res.core), res.scanned))
    for h in res.findings:
        out("находка: %s:%d · %s · %s · %s" % (h.file, h.line, h.name, h.kind, shorten(h.text)))
    for p in res.unlisted:
        out("находка: файл ядра не в перечне: %s — внесите его в %s (раздел %s) или, с причиной, в раздел %s"
            % (p, CORE_FILE, SECTION_CORE, SECTION_OUTSIDE))
    for row in res.unmatched:
        out("исключение без попадания: %s · %s · %s · %s" % (row.file, row.name, row.kind, shorten(row.text)))
    a, b, c = measures(res.findings)
    out("итог: находок %d (строк списка %d · различных строк файлов %d · файлов %d; файлов ядра не в перечне %d)"
        " · исключений покрыто %d из %d · без попадания %d"
        % (a + len(res.unlisted), a, b, c, len(res.unlisted), res.allowed_matched, res.allowed_total, len(res.unmatched)))
    code = exit_code(res, strict)
    if code == 0:
        out("проверка прошла: литералов донора, управляющих поведением, в файлах ядра нет.")
    elif code == 1:
        out("проверка провалилась: литералы донора в коде ядра есть — их надо вынести в настройки или внести в перечень исключений с причиной.")
    else:
        out("НЕ ПРОВЕРЕНО: %s" % (res.problems[0] if res.problems else "перечисленные выше файлы ядра прочитать не удалось"))


def run_check(root, data_dir, commit=None, strict=False, out=print):
    """Проверка с печатью; возвращает код выхода (0 / 1 / 2). Зовёт и командная строка, и перенос."""
    res = check(root, data_dir, commit)
    report(res, strict, out)
    return exit_code(res, strict)


# ---------------------------------------------------------------- сверка с замером Э2 и счётом Э3
def read_tsv_rows(path):
    """Простое деление по табуляции: модуль csv склеивает строки с кавычками. -> [словарь]."""
    lines = [s.rstrip("\r") for s in Path(path).read_text(encoding="utf-8").split("\n")]
    head = lines[0].split("\t")
    rows = []
    for number, text in enumerate(lines[1:], start=2):
        if not text:
            continue
        parts = text.split("\t")
        if len(parts) < len(head):
            raise Incomplete("%s:%d: колонок %d, ждали %d" % (path, number, len(parts), len(head)))
        parts = parts[:len(head) - 1] + ["\t".join(parts[len(head) - 1:])]
        rows.append(dict(zip(head, parts)))
    return rows


COUNT_LINE = re.compile(r"^СЧЁТ Э3[^:]*: строк списка (\d+) · различных строк файлов (\d+) · файлов (\d+)\s*$", re.M)
BEHAVIOR_LINE = re.compile(r"^(?P<file>[^\s:]+):(?P<line>\d+) · (?P<name>.+?) · ", re.M)


def run_count_core(goal):
    """Строки класса behavior у count-core.py: -> ({(файл, строка, имя)}, (строк, различных, файлов))."""
    script = goal / "e3" / "count-core.py"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(script), "--list", "behavior"], capture_output=True, env=env)
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0:
        first = (out.strip().split("\n") or [""])[0] or r.stderr.decode("utf-8", "replace").strip()[:200]
        raise Incomplete("count-core.py вернул код %d: %s" % (r.returncode, first))
    m = COUNT_LINE.search(out)
    if not m:
        raise Incomplete("в выводе count-core.py нет строки с итоговым счётом — разобрать его нельзя")
    tail = out[m.end():]
    rows = {(x.group("file"), int(x.group("line")), x.group("name")) for x in BEHAVIOR_LINE.finditer(tail)}
    return rows, tuple(int(g) for g in m.groups())


def reconcile(goal, root, data_dir, commit=None, out=print, allowed_file=None):
    """Сверка с замером Э2 и счётом Э3. -> код выхода: 0 сходится · 1 расходится · 2 не проверено.
    Перечень исключений для судимой версии: allowed_file, если назван; иначе — тот, что лежит в самом
    судимом commit; ни того ни другого — отказ словами (код 2), перечень рабочего дерева не подставляется."""
    goal, root = Path(goal), Path(root)
    out("сверка с замером Э2 и счётом Э3: каталог %s" % goal)
    try:
        for rel in ("e2/hits.tsv", "e2/metrics.json", "e3/count-core.py"):
            if not (goal / rel).is_file():
                raise Incomplete("в каталоге замеров нет файла %s" % rel)
        if commit is None:
            commit = str(json.loads((goal / "e2" / "metrics.json").read_text(encoding="utf-8")).get("head") or "")
            if not commit:
                raise Incomplete("в e2/metrics.json нет версии пакета (ключ head); укажите --reconcile-commit")
        if allowed_file is not None:
            allowed = load_allowed(allowed_file)
            allowed_from = "файл %s (назван при запуске)" % allowed_file
        else:
            allowed = allowed_of_commit(root, data_dir, commit)
            allowed_from = "commit %s" % commit
        res = check(root, data_dir, commit, allowed)
        if res.problems or res.missing:
            raise Incomplete("проверка на commit %s не выполнена полностью: %s"
                             % (commit, (res.problems + ["нет файлов ядра: " + ", ".join(res.missing)])[0]))
        hits_rows = read_tsv_rows(goal / "e2" / "hits.tsv")
        cc_rows, cc_measures = run_count_core(goal)
    except (Incomplete, OSError, ValueError) as e:
        out("НЕ ПРОВЕРЕНО: %s" % e)
        return 2
    out("версия пакета: commit %s · файлов ядра в перечне пакета: %d" % (commit, len(res.core)))
    out("перечень исключений: %s · записей %d" % (allowed_from, res.allowed_total))
    core = set(res.core)
    e2_groups = {r["group"] for r in hits_rows}
    code = 0

    # (а) движок против замера Э2 по файлам ядра, виды code и shown
    e2_set = {(r["file"], int(r["line"]), r["group"], r["name"], r["kind"]) for r in hits_rows
              if r["file"] in core and r["kind"] in COMPARED_KINDS}
    mine = {(h.file, h.line, h.group, h.name, h.kind) for h in res.hits
            if h.kind in COMPARED_KINDS and h.group in e2_groups}
    only_e2, only_mine = sorted(e2_set - mine), sorted(mine - e2_set)
    out("(а) движок против замера Э2: совпало %d из %d" % (len(e2_set & mine), len(e2_set)))
    for t in only_e2:
        out("   есть в замере Э2, движок не нашёл: %s:%d · %s · %s · %s" % t)
    for t in only_mine:
        out("   нашёл движок, в замере Э2 нет: %s:%d · %s · %s · %s" % t)
    if only_e2 or only_mine:
        code = 1

    # (б) находки проверки против строк класса behavior у count-core.py
    guard_rows = {(h.file, h.line, h.name) for h in res.findings}
    new_group = {(h.file, h.line, h.name) for h in res.findings if h.group not in e2_groups}
    only_cc = sorted(cc_rows - guard_rows)
    only_guard = sorted(guard_rows - cc_rows)
    explained = [t for t in only_guard if t in new_group]
    unexplained = [t for t in only_guard if t not in new_group]
    gm = measures(res.findings)
    out("(б) находки проверки: %d · %d · %d (строк списка · различных строк файлов · файлов); счёт count-core.py: %d · %d · %d"
        % (gm + cc_measures))
    for t in only_cc:
        out("   в счёте count-core.py есть, проверка не нашла: %s:%d · %s" % t)
    for t in unexplained:
        out("   нашла проверка, в счёте count-core.py нет: %s:%d · %s" % t)
    for t in explained:
        out("   нашла группа, которой замер Э2 не видел, в счёте count-core.py нет (класс решает владелец): %s:%d · %s" % t)
    if only_cc or unexplained:
        code = 1
    if len(cc_rows) != cc_measures[0]:
        out("   счёт count-core.py: в перечне %d строк, в итоговой строке %d — вывод разобран не полностью" % (len(cc_rows), cc_measures[0]))
        code = 1
    if code == 0:
        tail = "" if not explained else ", кроме %d строк новых групп (названы выше)" % len(explained)
        out("(а) и (б) сходятся%s." % tail)
    else:
        out("сверка не сходится: причины названы выше.")
    return code


# ---------------------------------------------------------------- командная строка
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Проверка: в коде ядра пакета нет литералов донора (имён ролей, путей, репозиториев, соседей, "
                    "портов), управляющих поведением. Данные лежат рядом с проверкой: core-files.txt (перечень файлов "
                    "ядра), donor-names.json (имена донора), donor-literals-allowed.tsv (перечень исключений).",
        epilog="Код выхода: 0 — находок нет; 1 — есть находки (с --strict — и исключения без попадания); "
               "2 — проверить не удалось, причина названа словами.")
    ap.add_argument("--commit", metavar="КОММИТ",
                    help="проверить версию из git вместо рабочего дерева")
    ap.add_argument("--root", metavar="КАТАЛОГ", default=str(HERE.parent.parent),
                    help="корень пакета (по умолчанию — каталог выше vnext/tools)")
    ap.add_argument("--data-dir", metavar="КАТАЛОГ", default=str(HERE),
                    help="каталог с файлами данных (по умолчанию — рядом с этой проверкой)")
    ap.add_argument("--strict", action="store_true",
                    help="исключение без попадания тоже провал (по умолчанию только печатается)")
    ap.add_argument("--reconcile-with", metavar="КАТАЛОГ",
                    help="каталог goal-gordi-core: сверить движок с замером Э2 и находки со счётом Э3; "
                         "обычная проверка при этом не выполняется")
    ap.add_argument("--reconcile-commit", metavar="КОММИТ",
                    help="версия пакета для сверки (по умолчанию — из e2/metrics.json)")
    ap.add_argument("--reconcile-allowed", metavar="ФАЙЛ",
                    help="перечень исключений, написанный для версии сверки (по умолчанию — перечень из самого судимого "
                         "commit; в нём перечня нет — отказ, не пустой перечень)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.reconcile_allowed and not args.reconcile_with:
        ap.error("--reconcile-allowed имеет смысл только вместе с --reconcile-with")
    if args.reconcile_with:
        return reconcile(args.reconcile_with, args.root, args.data_dir, args.reconcile_commit,
                         allowed_file=args.reconcile_allowed)
    res = check(args.root, args.data_dir, args.commit)
    report(res, args.strict)
    return exit_code(res, args.strict)


if __name__ == "__main__":
    sys.exit(main())
