#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА карточки 590: отметку «разобрано» (write-message.py --reviewed) нельзя поставить на письмо,
которое написал НАШ ЖЕ контур.

Предмет. Признак «письмо написали мы» был у читающей стороны — проверка моста (guard-all.py) с наших
писем разбора не спрашивает (карточка 573) — и не был у пишущей: запись отметки принимала её на своё
письмо молча. Восемь таких строк сняты 07.09 по слову владельца. Правка: признак вынесен в общий
модуль шапки письма (bridge_letter.own_letter_sign), его зовут обе стороны; запись отклоняет вызов
до любой записи, когда письмо само называет автором наш контур.

Случаи на испытуемом (каждый — отдельный вызов write-message.py на своей песочнице):
  ①   отметка на наше письмо (первая строка называет наш контур) отклонена до записи
  ①б  то же — письмо вида «пишет РОЛЬ (<мы>)» и письмо с шапкой, где from — наш контур
  ①в  холостой прогон отклоняет так же
  ①г  список из нашего письма и письма соседа отклонён целиком
  ②   ВСТРЕЧНЫЙ: отметка на письмо соседа проходит и ложится в таблицу разборов
  ②б  письмо соседа с шапкой в НАШЕЙ папке принято: шапка сильнее папки
  ③   ВСТРЕЧНЫЙ ВТОРОЙ: письмо без названного автора отметку принимает
  ③б  письмо без автора в нашей исходящей папке принято, и об этом сказано строкой
  ③в  письма с таким именем в папках моста нет — принято, строка «не проверено» называет причину
  ③г  одно имя в двух папках, наше и соседа, — принято: отметка нужна письму соседа
  ③д  имя своего контура в базе не названо — принято, строка «не проверено» называет причину
  ④   признак берётся из общего места: в записи своего экземпляра признака нет, проверка моста
      зовёт тот же модуль
  ④б  каталоги моста: общий модуль и проверка моста находят одни и те же, в одном порядке

Нарочные поломки (каждая — в КОПИИ инструмента на песочнице, со ступенью «копия запустилась»):
  П1 общий признак всегда отвечает «не наше» (подмена в модуле шапки) .... падают ① ①б ①в ①г ③б
  П2 отказ в записи выключен .............................................. падают ① ①б ①в ①г
  П3 любое найденное письмо считается нашим ............................... падают ② ②б ③ ③б ③г
  П4 общий поиск каталогов моста видит только <контур>/bridges ............ падает ④б
П1 меняет ОДИН файл — общий модуль — и этим меняет ответ записи: признак у неё не свой. Ответ
проверки моста под той же подменой держит соседняя приёмка bite-bridge-own-letters.py (случаи ⑪ ⑮).

ЧЕГО НЕ ПРОВЕРЯЕТ: настоящие письма моста (песочница своя, живые папки не читаются); прогон
guard-all.py на песочнице (его сторону держат bite-bridge-own-letters.py и bite-bridge-reviewed.py);
имя с путём внутри (в папках моста такое имя не ищется и идёт как «не проверено»).

⛔ Живой базы и живого моста не касается. Три исхода: 0 прошла · 1 не прошла · 2 не запустилась.
"""
import ast
import importlib.util
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем
import mezo_stand  # noqa: E402 — песочница

WRITE = mezo_target.script("write-message.py")
GUARD = mezo_target.script("guard-all.py")
ROLE = "COORD"
OWN = "atlas"
REFUSAL = "написал наш же контур"
SCHEMA = """
    CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
        timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
        priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
        addressed_by TEXT);
    CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
    CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
        linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
    CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT);
    CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""
TITLES = {
    "①": "① отметка на наше письмо (первая строка называет наш контур) отклонена до записи",
    "①б": "①б то же — письмо вида «пишет РОЛЬ (<мы>)» и письмо с шапкой, где from — наш контур",
    "①в": "①в холостой прогон отклоняет так же",
    "①г": "①г список из нашего письма и письма соседа отклонён целиком",
    "②": "② ВСТРЕЧНЫЙ: отметка на письмо соседа проходит и ложится в таблицу разборов",
    "②б": "②б письмо соседа с шапкой в НАШЕЙ папке принято: шапка сильнее папки",
    "③": "③ ВСТРЕЧНЫЙ ВТОРОЙ: письмо без названного автора отметку принимает",
    "③б": "③б письмо без автора в нашей исходящей папке принято, и об этом сказано строкой",
    "③в": "③в письма с таким именем в папках моста нет — принято, строка «не проверено» называет причину",
    "③г": "③г одно имя в двух папках, наше и соседа, — принято: отметка нужна письму соседа",
    "③д": "③д имя своего контура в базе не названо — принято, строка «не проверено» называет причину",
    "④": "④ признак берётся из общего места: в записи своего экземпляра нет, проверка моста зовёт тот же модуль",
    "④б": "④б каталоги моста: общий модуль и проверка моста находят одни и те же, в одном порядке",
}
# (название · файл копии · [(было, стало)] · какие случаи обязаны упасть)
BREAKS = (
    ("П1 общий признак всегда отвечает «не наше» (подмена в модуле шапки письма)", "bridge_letter.py",
     [('        return "fields" if own_name and head.sender_contour() == norm_contour(own_name) else None\n'
       "    return own_letter_sign_plain(file, own_name)\n",
       "        return None\n    return None\n")],
     ("①", "①б", "①в", "①г", "③б")),
    ("П2 отказ в записи выключен", "write-message.py",
     [("    if _own_letters:\n        for _name, _words, _box in _own_letters:\n",
       "    if False and _own_letters:\n        for _name, _words, _box in _own_letters:\n")],
     ("①", "①б", "①в", "①г")),
    ("П3 любое найденное письмо считается нашим", "write-message.py",
     [("        if all(sign in OWN_SIGN_WORDS for sign in signs):\n"
       "            own.append((name, OWN_SIGN_WORDS[signs[0]], files[0].parent.name))\n",
       "        if True:\n"
       '            own.append((name, "нарочная поломка", files[0].parent.name))\n')],
     ("②", "②б", "③", "③б", "③г")),
    ("П4 общий поиск каталогов моста видит только <контур>/bridges", "bridge_letter.py",
     [("        if candidate.is_dir():\n            found.append(candidate)\n    return found\n",
       "        if candidate.is_dir():\n            pass\n    return found\n")],
     ("④б",)),
)


class NotStarted(Exception):
    """Приёмке нечем мерить: исход «не запустилась», код 2."""


def load_letter(path: Path):
    """Модуль шапки письма из названного файла (у копии под поломкой — её собственный)."""
    if not path.is_file():
        raise NotStarted(f"рядом с испытуемым нет {path.name}: {path}")
    spec = importlib.util.spec_from_file_location("bridge_letter_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(letter, with_name: bool = True):
    """Песочница-контур: база в <корень>/.mezosync, письма в <корень>/bridges, вторая раскладка
    моста — в <корень>/repo.archs/.mezosync/bridges. → (корень, база, имена писем)."""
    root = mezo_stand.new("bite-rev-own-")
    (root / ".mezosync").mkdir()
    db = root / ".mezosync" / "mezosync.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for role in (ROLE, "PROTO"):
        con.execute("INSERT INTO roles VALUES (?, 'alive')", (role,))
    if with_name:
        con.execute("INSERT INTO meta (key, value) VALUES ('group_name', ?)", (OWN,))
    con.commit()
    con.close()
    bridges = root / "bridges"
    ours_box, theirs_box, mixed_box = bridges / f"{OWN}-neigh", bridges / f"neigh-{OWN}", bridges / "old-exchange"
    for box in (ours_box, theirs_box, mixed_box):
        box.mkdir(parents=True)
    (root / "repo.archs" / ".mezosync" / "bridges" / "x-y").mkdir(parents=True)

    def put(box: Path, name: str, text: str) -> str:
        (box / name).write_text(text, encoding="utf-8")
        return name

    when = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
    names = {
        "line": put(mixed_box, "answer.neigh.nashe-po-stroke.md",
                    "2026-09-06 02:40 UTC · пишет **PROTO контура Atlas**. Все метки UTC.\nтекст\n"),
        "role": put(mixed_box, "answer.neigh.nashe-starogo-vida.md",
                    "2026-08-23 07:26 UTC · пишет COORD (atlas), в ответ на вопрос.\nтекст\n"),
        "fields": put(ours_box, "status.neigh.s-polyami.20261118-1000.md",
                      letter.compose(when, ("PROTO", OWN), [("COORD", "neigh")], "status",
                                     f"{OWN}:{OWN}-neigh/status.neigh.s-polyami.20261118-1000", body="текст\n")),
        "theirs": put(theirs_box, "ask.atlas.soseda.md",
                      "2026-09-06 02:40 UTC · пишет **COORD контура Neigh**.\nтекст\n"),
        "theirs_fields": put(ours_box, "status.atlas.dropped.20261118-1100.md",
                             letter.compose(when, ("COORD", "neigh"), [("PROTO", OWN)], "status",
                                            f"neigh:{OWN}-neigh/status.atlas.dropped.20261118-1100", body="текст\n")),
        "unknown": put(mixed_box, "note.bez-avtora.md", "# Заголовок без автора\nтекст\n"),
        "folder": put(ours_box, "answer.neigh.bez-avtora.md", "# Atlas → Neigh: заголовок без автора\nтекст\n"),
        "both": "status.obshchee-imya.md",
        "absent": "answer.neigh.net-takogo.md",
    }
    put(mixed_box, names["both"], "2026-09-06 02:40 UTC · пишет **PROTO контура Atlas**.\nтекст\n")
    put(theirs_box, names["both"], "2026-09-06 02:41 UTC · пишет **COORD контура Neigh**.\nтекст\n")
    for key in ("fields", "theirs_fields"):
        if not letter.read_header(ours_box / names[key]).valid:
            raise NotStarted(f"шапка подставного письма {names[key]} не годна — случаи с шапкой судить нечем")
    return root, db, names


CALLS = [0]          # счётчик вызовов записи: делает тело каждой пробы своим


def write(tool: Path, db: Path, root: Path, names, dry: bool = False):
    """→ (код, вывод обоих потоков в порядке записи)."""
    now = datetime.now(timezone.utc).strftime("%H:%M")
    # Тело у каждого вызова своё. Запись отказывает на повтор той же записки того же автора
    # (код 3, окно 30 минут): одинаковое тело роняло бы случаи с принятой отметкой не по своей
    # причине, и нарочные поломки переставали бы различаться.
    CALLS[0] += 1
    cmd = [sys.executable, str(tool), "--db", str(db), "--role", ROLE,
           "--body", f"[{ROLE} {now} UTC] приёмка отметки о разборе\n\nпроба {CALLS[0]}",
           "--reviewed", ",".join(names)]
    if dry:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace", env=mezo_stand.stand_env(root), timeout=300)
    return r.returncode, r.stdout or ""


def marks(db: Path) -> set:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return {row[0] for row in con.execute("SELECT file_name FROM bridge_reviewed")}
    except sqlite3.OperationalError:
        return set()                              # таблицы ещё нет — отметок не было
    finally:
        con.close()


def notes(db: Path) -> int:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        con.close()


def guard_marker_dirs(root: Path):
    """Каталоги моста так, как их ищет проверка: функция _by_marker ИЗ ЕЁ ИСХОДНИКА, не копия."""
    text = GUARD.read_text(encoding="utf-8")
    node = next((n for n in ast.parse(text).body
                 if isinstance(n, ast.FunctionDef) and n.name == "_by_marker"), None)
    if node is None:
        return None
    namespace: dict = {}
    exec(ast.get_source_segment(text, node), namespace)  # noqa: S102 — свой же исходник
    return namespace["_by_marker"](root, "bridges")


def run_cases(tool: Path) -> dict:
    """Все случаи на названном инструменте. → {ключ: (прошёл, подробность)}."""
    letter = load_letter(tool.parent / "bridge_letter.py")
    root, db, names = build(letter)
    got: dict = {}

    def state() -> str:
        return f"отметок {sorted(marks(db))} · записок {notes(db)}"

    base = notes(db)
    code, out = write(tool, db, root, [names["line"]])
    got["①"] = (code == 2 and REFUSAL in out and not marks(db) and notes(db) == base,
                f"код {code} (ждём 2) · слова отказа {'есть' if REFUSAL in out else 'НЕТ'} · {state()}")
    code_r, out_r = write(tool, db, root, [names["role"]])
    code_f, out_f = write(tool, db, root, [names["fields"]])
    got["①б"] = (code_r == 2 and REFUSAL in out_r and code_f == 2 and REFUSAL in out_f
                 and not marks(db) and notes(db) == base,
                 f"вид «пишет РОЛЬ (<мы>)»: код {code_r} · письмо с шапкой: код {code_f} (ждём 2 и 2) · {state()}")
    code, out = write(tool, db, root, [names["line"]], dry=True)
    got["①в"] = (code == 2 and REFUSAL in out and not marks(db) and notes(db) == base,
                 f"код {code} (ждём 2) · слова отказа {'есть' if REFUSAL in out else 'НЕТ'} · {state()}")
    code, out = write(tool, db, root, [names["line"], names["theirs"]])
    got["①г"] = (code == 2 and REFUSAL in out and not marks(db) and notes(db) == base,
                 f"код {code} (ждём 2) · {state()} — письмо соседа из того же вызова тоже не отмечено")

    code, out = write(tool, db, root, [names["theirs"]])
    got["②"] = (code == 0 and "разбор записан" in out and names["theirs"] in marks(db),
                f"код {code} (ждём 0) · подтверждение {'есть' if 'разбор записан' in out else 'НЕТ'} · {state()}")
    code, out = write(tool, db, root, [names["theirs_fields"]])
    got["②б"] = (code == 0 and names["theirs_fields"] in marks(db),
                 f"код {code} (ждём 0) · отметка {'есть' if names['theirs_fields'] in marks(db) else 'НЕТ'}")
    code, out = write(tool, db, root, [names["unknown"]])
    got["③"] = (code == 0 and names["unknown"] in marks(db),
                f"код {code} (ждём 0) · отметка {'есть' if names['unknown'] in marks(db) else 'НЕТ'}")
    code, out = write(tool, db, root, [names["folder"]])
    got["③б"] = (code == 0 and names["folder"] in marks(db) and "только папка" in out,
                 f"код {code} (ждём 0) · отметка {'есть' if names['folder'] in marks(db) else 'НЕТ'} · "
                 f"строка «только папка» {'есть' if 'только папка' in out else 'НЕТ'}")
    code, out = write(tool, db, root, [names["absent"]])
    got["③в"] = (code == 0 and names["absent"] in marks(db) and "не проверено" in out
                 and "в папках моста нет" in out,
                 f"код {code} (ждём 0) · строка «не проверено» {'есть' if 'не проверено' in out else 'НЕТ'}")
    code, out = write(tool, db, root, [names["both"]])
    got["③г"] = (code == 0 and names["both"] in marks(db),
                 f"код {code} (ждём 0) · отметка {'есть' if names['both'] in marks(db) else 'НЕТ'}")

    root2, db2, names2 = build(letter, with_name=False)
    code, out = write(tool, db2, root2, [names2["line"]])
    got["③д"] = (code == 0 and names2["line"] in marks(db2) and "не проверено" in out
                 and "имя своего контура" in out,
                 f"код {code} (ждём 0) · строка о причине {'есть' if 'имя своего контура' in out else 'НЕТ'}")

    write_text = tool.read_text(encoding="utf-8")
    guard_text = GUARD.read_text(encoding="utf-8")
    calls_shared = "bridge_letter.own_letter_sign(" in write_text
    own_copy = 'return "role"' in write_text or 'return "folder"' in write_text
    guard_calls = ("bridge_letter.own_letter_sign_plain(file, _own_name)" in guard_text
                   and "bridge_letter.own_letter_sign(f, _own_name, head)" in guard_text)
    guard_copy = 'return "role"' in guard_text or 'return "folder"' in guard_text
    got["④"] = (calls_shared and not own_copy and guard_calls and not guard_copy,
                f"запись зовёт общий модуль: {calls_shared} · свой экземпляр в записи: {own_copy} · "
                f"проверка моста зовёт общий модуль: {guard_calls} · свой экземпляр в проверке: {guard_copy}")
    by_guard = guard_marker_dirs(root)
    by_module = letter.bridge_dirs(root)
    got["④б"] = (by_guard is not None and by_guard == by_module and len(by_module) == 2,
                 f"проверка моста: {[p.as_posix()[len(root.as_posix()) + 1:] for p in (by_guard or [])]} · "
                 f"общий модуль: {[p.as_posix()[len(root.as_posix()) + 1:] for p in by_module]} (ждём два одинаковых)")
    return got


def broken_copy(file_name: str, swaps) -> Path:
    """Копия инструмента с соседями на песочнице, в файле file_name — нарочная поломка.
    Каждый образец обязан найтись ровно один раз; копия обязана запуститься."""
    stand = mezo_stand.new("bite-rev-own-break-")
    copy_path = mezo_stand.copy_tool(WRITE, stand)
    target = stand / file_name
    if not target.is_file():
        raise NotStarted(f"в копии нет файла {file_name} — поломку некуда вложить")
    text = target.read_text(encoding="utf-8")
    for old, new in swaps:
        if text.count(old) != 1:
            raise NotStarted(f"образец поломки найден {text.count(old)} раз в {file_name}: {old[:60]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    started = subprocess.run([sys.executable, str(copy_path), "--help"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=mezo_stand.stand_env(stand), timeout=120)
    if started.returncode != 0:
        raise NotStarted(f"копия с поломкой не запустилась (код {started.returncode}): "
                         f"{(started.stderr or '').strip()[-200:]}")
    return copy_path


def main() -> int:
    ok = True
    try:
        base = run_cases(WRITE)
        for key, title in TITLES.items():
            passed, detail = base[key]
            print(f"{'✅' if passed else '🔴'} {title}")
            print(f"   {detail}")
            ok &= passed
        print()
        hit = 0
        for title, file_name, swaps, expected in BREAKS:
            copy_path = broken_copy(file_name, swaps)
            under = run_cases(copy_path)
            fallen = tuple(key for key in TITLES if not under[key][0])
            exact = fallen == tuple(key for key in TITLES if key in expected)
            hit += exact
            ok &= exact
            print(f"{'✅' if exact else '🔴'} {title}: копия запустилась · упали {' '.join(fallen) or 'ни один'} "
                  f"· ждали {' '.join(expected)}")
            if not exact:
                for key in fallen:
                    print(f"   {key}: {under[key][1]}")
    except NotStarted as exc:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: {exc}")
        print("ИТОГ: не запустилась")
        return 2
    print()
    print(f"ИТОГ: {'прошла' if ok else 'не прошла'} — случаев на испытуемом {len(TITLES)} · "
          f"нарочных поломок {len(BREAKS)} · провалили ровно своё {hit} · испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
