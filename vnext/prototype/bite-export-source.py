#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА карточки 668: контур, собранный из ВЫГРУЗКИ пакета, на обновление без --source отвечает
отказом кодом 2 и называет --source — а не зовёт git clone по подписи сборки.

Предмет. Сборка контура (init-group.py) из каталога пакета без адреса origin кладёт в
meta.template_source подпись «локальный каталог <путь> (не репозиторий)». Это не адрес и не путь.
update-tools.py брал запись как источник и звал по ней git clone: выходило «НЕ ЗАБРАЛОСЬ» — слова о
недоступном источнике там, где забирать нечего по построению. Правка: источник взят из записи и
запись — подпись сборки ⇒ отказ кодом 2 со словами «источник — выгрузка … назови --source», контур
не тронут. Названный --source идёт прежним путём.

Как собрано. Выгрузка — файлы пакета без каталога .git (те, что отслеживает git, взятые из
рабочего дерева; образец сам без git — копируется целиком). Контур собирает НАСТОЯЩАЯ сборка из
этой выгрузки: так приёмка держит и то, что подпись сборки и её образец в update-tools.py сходятся.

Случаи (перед каждым база контура и отставший файл возвращаются к состоянию сразу после сборки):
  ①  без --source: отказ кодом 2, слова «источник — выгрузка» и «назови --source», слов
     «НЕ ЗАБРАЛОСЬ» нет
  ②  отказ контур не трогает (план и --apply): запись в meta, отставший файл, состав каталога те же
  ③  --record-only без --source: тот же отказ кодом 2
  ④  ВСТРЕЧНЫЙ: с названным --source план показывает отставший файл, --apply его забирает
  ⑤  ВСТРЕЧНЫЙ: после --source … --record-source --apply запись — названный источник, и вызов без
     --source идёт обычным путём
  ⑥  ВСТРЕЧНЫЙ: запись, которая не подпись (несуществующий путь), идёт прежним путём —
     «НЕ ЗАБРАЛОСЬ», код 1
  ⑦  ВСТРЕЧНЫЙ: подпись, названная явно через --source, не перехватывается — «НЕ ЗАБРАЛОСЬ», код 1

Нарочные поломки ставятся в update-tools.py собранного контура (после каждой файл возвращается
побайтно) и одна — в init-group.py второй выгрузки, из которой собирается второй контур. У каждой
в таблице BREAKS заранее записано, какие случаи обязаны упасть; итог сверяет множества поимённо.
У поломок с пометкой «прежний отказ» дополнительно сверяется, что вызов без --source снова
отвечает «НЕ ЗАБРАЛОСЬ» кодом 1.

Предпосылка (нет её — исход «не запустилась», код 2): сборка из выгрузки записала источником
текст, который не адрес и не существующий каталог. Запиши сборка что-то пригодное — предмета
карточки нет, и мерить нечего.

ЧЕГО НЕ ПРОВЕРЯЕТ: выгрузку, сделанную именно командой git archive; источник-адрес по сети
(названный --source здесь — каталог на диске); контур из клона с адресом origin (его запись —
адрес, отказ на неё не смотрит: это держат случай ⑥ и bite-self-update.py); режим --merge.

⛔ Живого контура не касается: контур собирается в стенде, инструменты зовутся со средой стенда.
Три исхода: 0 принята · 1 не принята · 2 не запустилась.
Запуск: python <абсолютный путь>/bite-export-source.py [--template <каталог пакета>] [--no-breaks]
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — где образец пакета
import mezo_stand  # noqa: E402 — стенд

UPDATER_NAME = "update-tools.py"
BUILDER_NAME = "init-group.py"
VICTIM_NAME = "guard-utc.py"
STALE_MARK = "отставшая копия приёмки bite-export-source"
SAYS_EXPORT = "источник — выгрузка"
SAYS_NAME_SOURCE = "назови --source"
OLD_REFUSAL = "НЕ ЗАБРАЛОСЬ"

TITLES = {
    "①": "① без --source: отказ кодом 2 называет выгрузку и --source, слов «НЕ ЗАБРАЛОСЬ» нет",
    "②": "② отказ контур не трогает: запись в meta, отставший файл и состав каталога те же",
    "③": "③ --record-only без --source: тот же отказ кодом 2",
    "④": "④ ВСТРЕЧНЫЙ: с названным --source план показывает отставший файл, --apply его забирает",
    "⑤": "⑤ ВСТРЕЧНЫЙ: после --record-source запись — названный источник, вызов без --source работает",
    "⑥": "⑥ ВСТРЕЧНЫЙ: запись, которая не подпись, идёт прежним путём — «НЕ ЗАБРАЛОСЬ», код 1",
    "⑦": "⑦ ВСТРЕЧНЫЙ: подпись, названная явно через --source, не перехватывается",
}

GUARD_LINE = "    export_dir = None if a.source else export_label_dir(source)\n"
REFUSAL_END = ('        print("   Контур не тронут: ни файлы, ни запись источника.")\n'
               "        return 2\n")
META_WRITE = ('        _probe = sqlite3.connect(str(db))\n'
              '        _probe.execute("INSERT INTO meta (key, value) VALUES (\'export_refused\', \'1\') "\n'
              '                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value")\n'
              '        _probe.commit()\n'
              '        _probe.close()\n')

# (название · где · файл · [(было, стало)] · какие случаи обязаны упасть · обязан ли вернуться прежний отказ)
BREAKS = (
    ("П1 подпись сборки не узнаётся", "updater", UPDATER_NAME,
     [('    return found.group("dir") if found else None\n', "    return None\n")], ("①", "③"), True),
    ("П2 отказ выходит кодом 1", "updater", UPDATER_NAME,
     [(REFUSAL_END, REFUSAL_END.replace("return 2", "return 1"))], ("①", "③"), False),
    ("П3 отказ не называет --source", "updater", UPDATER_NAME,
     [("забирать нечего; назови --source <адрес", "забирать нечего; назови источник <адрес")],
     ("①", "③"), False),
    ("П4 отказ срабатывает и на названный --source", "updater", UPDATER_NAME,
     [(GUARD_LINE, "    export_dir = export_label_dir(source)\n")], ("⑦",), False),
    ("П5 подписью считается любая запись, которая не каталог", "updater", UPDATER_NAME,
     [('    found = EXPORT_LABEL.match((recorded or "").strip())\n'
       '    return found.group("dir") if found else None\n',
       '    return None if pathlib.Path(recorded or "").is_dir() else (recorded or "")\n')],
     ("⑥",), False),
    ("П6 отказ правит запись контура", "updater", UPDATER_NAME,
     [(REFUSAL_END, META_WRITE + REFUSAL_END)], ("②",), False),
    ("П7 отказ глядит на запись и при названном --source", "updater", UPDATER_NAME,
     [(GUARD_LINE, '    export_dir = export_label_dir(got.get("template_source"))\n')],
     ("④", "⑤", "⑦"), False),
    ("П8 --record-source не пишет поверх подписи", "updater", UPDATER_NAME,
     [("        write_source = bool(a.record_source) or not recorded_source\n",
       "        write_source = not recorded_source\n")], ("⑤",), False),
    ("П9 отказ не покрывает --record-only", "updater", UPDATER_NAME,
     [(GUARD_LINE,
       "    export_dir = None if (a.source or a.record_only) else export_label_dir(source)\n")],
     ("③",), False),
    ("П10 подпись изменена в сборке, а образец в обновлении прежний (второй контур)", "builder",
     BUILDER_NAME,
     [('or f"локальный каталог {REPO_ROOT} (не репозиторий)"\n',
       'or f"локальный каталог {REPO_ROOT} (без git)"\n')], ("①", "③"), True),
)


class NotStarted(Exception):
    """Приёмке нечем мерить: исход «не запустилась», код 2."""


def tool_env(root: Path) -> dict:
    """Среда инструментов собранного контура: только стенд, без направлений вызывающего."""
    env = mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                               PYTHONDONTWRITEBYTECODE="1", GIT_TERMINAL_PROMPT="0")
    # Свежему контуру незачем знать, какую копию пакета испытывает вызывающий.
    for name in ("MEZO_SCRIPTS_ROOT", "MEZO_LIVE_DB", "MEZO_TEMPLATE"):
        env.pop(name, None)
    return env


def run(tool: Path, *args, root: Path, limit: int = 300):
    """Запустить инструмент на стенде. → (код, весь вывод)."""
    proc = subprocess.run([sys.executable, str(tool), *map(str, args)], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=limit, env=tool_env(root))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def read_meta(db: Path) -> dict:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT key, value FROM meta"))
    finally:
        con.close()


def export_package(template: Path, dest: Path) -> str:
    """Выгрузка пакета: его файлы без каталога .git. → слова, как она собрана."""
    listed = subprocess.run(["git", "-C", str(template), "ls-files", "-z"], capture_output=True)
    names = ([name for name in listed.stdout.decode("utf-8", "replace").split("\0") if name]
             if listed.returncode == 0 else [])
    if names:
        copied = 0
        for name in names:
            source = template / name
            if source.is_file():
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied += 1
        how = f"{copied} файлов, которые отслеживает git, взяты из рабочего дерева"
    else:
        shutil.copytree(template, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        how = "образец сам без git — скопирован целиком"
    if (dest / ".git").exists():
        raise NotStarted(f"в выгрузке оказался каталог .git: {dest}")
    for needed in (dest / "scripts" / BUILDER_NAME, dest / "scripts" / UPDATER_NAME):
        if not needed.is_file():
            raise NotStarted(f"в выгрузке нет файла {needed}")
    return how


def build_contour(export: Path, root: Path) -> str:
    """Собрать контур настоящей сборкой из выгрузки. → запись источника этого контура."""
    code, out = run(export / "scripts" / BUILDER_NAME, "--name", "biteexp",
                    "--path", root / ".mezosync", "--roles", "COORD", root=root, limit=900)
    db = root / ".mezosync" / "mezosync.db"
    if code != 0 or not db.is_file():
        raise NotStarted(f"сборка контура из выгрузки не удалась: код {code} · база "
                         f"{'есть' if db.is_file() else 'НЕТ'} · {out[-300:].strip()}")
    for needed in (UPDATER_NAME, VICTIM_NAME):
        if not (root / ".mezosync" / "scripts" / needed).is_file():
            raise NotStarted(f"в собранном контуре нет инструмента {needed}")
    record = read_meta(db).get("template_source") or ""
    try:
        usable = Path(record).exists()
    except OSError:
        usable = False
    if not record or record.startswith(("http", "git@")) or usable:
        raise NotStarted(f"сборка из выгрузки записала источником «{record}» — это адрес, "
                         "существующий каталог или пусто: предмета карточки нет, мерить нечего")
    return record


def snapshot(db: Path, copy: Path) -> None:
    """Копия базы контура средствами SQLite — целая и при журнале WAL."""
    source = sqlite3.connect(db)
    target = sqlite3.connect(copy)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def plant(target: Path, swaps) -> None:
    """Поставить поломку в файл: каждая подмена обязана найтись ровно один раз."""
    with open(target, encoding="utf-8", newline="") as handle:
        text = handle.read()
    ending = "\r\n" if "\r\n" in text else "\n"
    for old, new in swaps:
        old, new = old.replace("\n", ending), new.replace("\n", ending)
        if text.count(old) != 1:
            raise NotStarted(f"место поломки найдено {text.count(old)} раз (нужно 1) в "
                             f"{target.name}: {old[:60]!r} — испытуемое изменилось, поломка бьёт мимо")
        text = text.replace(old, new, 1)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


class Bench:
    """Один проход всех случаев по одному собранному контуру."""

    def __init__(self, root: Path, export: Path, base_copy: Path):
        self.root, self.export, self.base_copy = root, export, base_copy
        self.db = root / ".mezosync" / "mezosync.db"
        self.tools = root / ".mezosync" / "scripts"
        self.updater = self.tools / UPDATER_NAME
        self.victim = self.tools / VICTIM_NAME
        self.victim_bytes = self.victim.read_bytes()
        self.plain = (None, "")     # что ответил вызов без --source в случае ①

    def reset(self) -> None:
        """База и отставший файл — как сразу после сборки."""
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db) + suffix).unlink(missing_ok=True)
        shutil.copyfile(self.base_copy, self.db)
        self.victim.write_bytes(self.victim_bytes)

    def update(self, *args):
        return run(self.updater, *args, root=self.root)

    def make_stale(self) -> None:
        """Отставший файл: старое содержимое И отпечаток установки ему соответствует."""
        self.victim.write_text("# " + STALE_MARK + "\n", encoding="utf-8")
        con = sqlite3.connect(self.db)
        stamps = json.loads(dict(con.execute("SELECT key, value FROM meta"))
                            .get("template_files_sha") or "{}")
        stamps[self.victim.name] = hashlib.sha256(
            self.victim.read_bytes().replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]
        con.execute("INSERT INTO meta (key, value) VALUES ('template_files_sha', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (json.dumps(stamps, ensure_ascii=False),))
        con.commit()
        con.close()

    def is_stale(self) -> bool:
        return STALE_MARK in self.victim.read_text(encoding="utf-8", errors="replace")

    def contour_files(self) -> list:
        base = self.root / ".mezosync"
        return sorted((path.relative_to(base).as_posix(), path.stat().st_size)
                      for path in base.rglob("*")
                      if path.is_file() and not path.name.startswith("mezosync.db")
                      and "__pycache__" not in path.parts)

    def state(self):
        return read_meta(self.db), self.victim.read_bytes(), self.contour_files()

    # ── случаи: каждый возвращает (прошёл, что видел) ─────────────────────────────────────────
    def case_1(self):
        code, out = self.update()
        self.plain = (code, out)
        ok = (code == 2 and SAYS_EXPORT in out and SAYS_NAME_SOURCE in out
              and OLD_REFUSAL not in out and "Traceback" not in out)
        return ok, (f"код {code} · «{SAYS_EXPORT}»: {SAYS_EXPORT in out} · «{SAYS_NAME_SOURCE}»: "
                    f"{SAYS_NAME_SOURCE in out} · «{OLD_REFUSAL}»: {OLD_REFUSAL in out}")

    def case_2(self):
        self.make_stale()
        before = self.state()
        plan_code, _ = self.update()
        apply_code, _ = self.update("--apply")
        after = self.state()
        return after == before, (f"план код {plan_code} · --apply код {apply_code} · запись та же: "
                                 f"{after[0] == before[0]} · отставший файл тот же: "
                                 f"{after[1] == before[1]} · состав каталога тот же: "
                                 f"{after[2] == before[2]}")

    def case_3(self):
        code, out = self.update("--record-only")
        ok = (code == 2 and SAYS_EXPORT in out and SAYS_NAME_SOURCE in out
              and OLD_REFUSAL not in out and "Traceback" not in out)
        return ok, (f"код {code} · «{SAYS_EXPORT}»: {SAYS_EXPORT in out} · «{SAYS_NAME_SOURCE}»: "
                    f"{SAYS_NAME_SOURCE in out} · «{OLD_REFUSAL}»: {OLD_REFUSAL in out}")

    def case_4(self):
        self.make_stale()
        plan_code, plan_out = self.update("--source", self.export)
        kept = self.is_stale()
        apply_code, apply_out = self.update("--source", self.export, "--apply")
        fresh = not self.is_stale()
        both = plan_out + apply_out
        ok = (plan_code == 0 and VICTIM_NAME in plan_out and "[ПЛАН]" in plan_out and kept
              and apply_code == 0 and "Забрано" in apply_out and fresh
              and SAYS_EXPORT not in both and "Traceback" not in both)
        return ok, (f"план код {plan_code}, файл назван: {VICTIM_NAME in plan_out}, до --apply не "
                    f"тронут: {kept} · --apply код {apply_code}, файл свежий: {fresh}")

    def case_5(self):
        first_code, first_out = self.update("--source", self.export, "--record-source", "--apply")
        recorded = read_meta(self.db).get("template_source", "")
        code, out = self.update()
        ok = (first_code == 0 and recorded == str(self.export) and code == 0 and "[ПЛАН]" in out
              and SAYS_EXPORT not in out and OLD_REFUSAL not in out
              and "Traceback" not in first_out + out)
        return ok, (f"запись источника стала названным каталогом: {recorded == str(self.export)} "
                    f"(код {first_code}) · вызов без --source: код {code}, план показан: "
                    f"{'[ПЛАН]' in out}")

    def case_6(self):
        missing = self.root / "no-such-repo"
        con = sqlite3.connect(self.db)
        con.execute("UPDATE meta SET value = ? WHERE key = 'template_source'", (str(missing),))
        con.commit()
        con.close()
        code, out = self.update()
        ok = code == 1 and OLD_REFUSAL in out and SAYS_EXPORT not in out
        return ok, (f"код {code} · «{OLD_REFUSAL}»: {OLD_REFUSAL in out} · «{SAYS_EXPORT}»: "
                    f"{SAYS_EXPORT in out}")

    def case_7(self):
        label = read_meta(self.db).get("template_source", "")
        code, out = self.update("--source", label)
        ok = code == 1 and OLD_REFUSAL in out and SAYS_EXPORT not in out
        return ok, (f"код {code} · «{OLD_REFUSAL}»: {OLD_REFUSAL in out} · «{SAYS_EXPORT}»: "
                    f"{SAYS_EXPORT in out}")

    def judge(self) -> dict:
        """Все случаи по порядку. → {имя: (прошёл, что видел)}; сбой случая — провал со словом."""
        plan = (("①", self.case_1), ("②", self.case_2), ("③", self.case_3), ("④", self.case_4),
                ("⑤", self.case_5), ("⑥", self.case_6), ("⑦", self.case_7))
        self.plain = (None, "")
        verdicts = {}
        for name, case in plan:
            try:
                self.reset()
                verdicts[name] = case()
            except (sqlite3.Error, OSError, subprocess.TimeoutExpired, ValueError) as problem:
                verdicts[name] = (False, f"случай не досчитан: {type(problem).__name__}: {problem}")
        self.reset()
        return verdicts

    def old_refusal_back(self) -> bool:
        """Вызов без --source в случае ① ответил по-прежнему: «НЕ ЗАБРАЛОСЬ», код 1."""
        return self.plain[0] == 1 and OLD_REFUSAL in self.plain[1]


def new_bench(export: Path, root: Path, home: Path, tag: str):
    """Собрать контур из выгрузки и подготовить проход. → (проход, запись источника)."""
    record = build_contour(export, root)
    base_copy = home / f"base-{tag}.db"
    snapshot(root / ".mezosync" / "mezosync.db", base_copy)
    return Bench(root, export, base_copy), record


def pick_template(args) -> Path:
    if "--template" in args:
        place = args.index("--template")
        if place + 1 >= len(args):
            raise NotStarted("после --template не назван каталог пакета")
        return Path(args[place + 1]).resolve()
    return Path(mezo_paths.template_root(__file__))


def main() -> int:
    args = sys.argv[1:]
    with_breaks = "--no-breaks" not in args
    try:
        template = pick_template(args)
        for needed in (template / "scripts" / BUILDER_NAME, template / "scripts" / UPDATER_NAME):
            if not needed.is_file():
                raise NotStarted(f"у образца пакета нет файла {needed}")
        home = mezo_stand.new("bite-export-")
        export = home / "export"
        how = export_package(template, export)
        bench, record = new_bench(export, home / "contour", home, "main")

        print(f"ПРИЁМКА карточки 668 · образец пакета: {template.as_posix()}")
        print(f"ℹ️ выгрузка: {how}")
        print(f"ℹ️ запись источника у собранного контура: «{record}»")
        verdicts = bench.judge()
        failed = [name for name, (ok, _) in verdicts.items() if not ok]
        for name, (ok, seen) in verdicts.items():
            print(f"  {'✅' if ok else '🔴'} {TITLES[name]}\n        {seen}")

        break_lines, breaks_ok, breaks_run = [], True, with_breaks and not failed
        if with_breaks and failed:
            print("\nНАРОЧНЫЕ ПОЛОМКИ не гонялись: основные случаи не прошли — судить поломки не на чем")
        if breaks_run:
            pristine = bench.updater.read_bytes()
            for number, (title, where, name, swaps, expected, old_back) in enumerate(BREAKS, 1):
                if where == "updater":
                    judged = bench
                    try:
                        plant(bench.updater, swaps)
                        fallen_map = bench.judge()
                    finally:
                        bench.updater.write_bytes(pristine)
                else:
                    second_export = home / f"export-{number:02d}"
                    shutil.copytree(export, second_export)
                    plant(second_export / "scripts" / name, swaps)
                    judged, _ = new_bench(second_export, home / f"contour-{number:02d}", home,
                                          f"break-{number:02d}")
                    fallen_map = judged.judge()
                fallen = [case for case, (ok, _) in fallen_map.items() if not ok]
                exact = set(fallen) == set(expected)
                old_word = ""
                if old_back:
                    returned = judged.old_refusal_back()
                    exact = exact and returned
                    old_word = f" · прежний отказ «{OLD_REFUSAL}» кодом 1 вернулся: {returned}"
                breaks_ok &= exact
                break_lines.append(f"  {'✅' if exact else '🔴'} {title}\n        ждали: "
                                   f"{' '.join(expected)} · упали: {' '.join(fallen) or 'ни один'}"
                                   f"{old_word}")
            if bench.updater.read_bytes() != pristine:
                raise NotStarted("update-tools.py контура после поломок не вернулся к исходному тексту")
            print("\nНАРОЧНЫЕ ПОЛОМКИ (ожидания записаны в таблице BREAKS до прогона):")
            print("\n".join(break_lines))
    except NotStarted as reason:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: {reason}")
        return mezo_stand.finish(2)

    total = len(verdicts)
    accepted = not failed and breaks_ok
    if breaks_run:
        breaks_word = (f"нарочных поломок "
                       f"{sum(1 for line in break_lines if line.lstrip().startswith('✅'))} "
                       f"из {len(BREAKS)} уронили ровно своё")
    else:
        breaks_word = "нарочные поломки не гонялись"
    print(f"\nИТОГ: {'✅ ПРИНЯТА' if accepted else '🔴 НЕ ПРИНЯТА'} — случаев прошло "
          f"{total - len(failed)} из {total}"
          f"{' · упали: ' + ' '.join(failed) if failed else ''} · {breaks_word}")
    return mezo_stand.finish(0 if accepted else 1)


if __name__ == "__main__":
    sys.exit(main())
