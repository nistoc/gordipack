# -*- coding: utf-8 -*-
r"""bite-bridge-layouts.py — приёмка карточки #684: письма соседа со вторым устройством папки моста.

ПОВОД. 05.10 три письма контура onto к PROTO лежали в его папке C:/github/.onto/bridges/atlas-onto/,
а чтение ленты печатало «письма соседей в мосте: нового нет» — первое письмо (стоп приёмки Э3)
пролежало ≈2,5 ч. Причины две (sync_backoff.py): обход знал только устройство
<контейнер>/<репо>/.mezosync/bridges/<папка>, а у onto папки моста лежат в корне контура —
<контейнер>/bridges/<папка>; и строка «нового нет» не называла, у каких соседей смотрела, — сосед,
которого нет в cross_links, был невидим.

Случаи (стенд — новая база с таблицами meta, cross_links, messages, roles; соседи — папки стенда):
  ① письмо в папке второго устройства (bridges/atlas-onto) с адресатом PROTO названо поимённо:
     час · onto → PROTO (тебе) · имя файла. Сосед — из cross_links, а не из имени папки
     (в «atlas-onto» наше имя первое, и прежний разбор назвал бы соседом «atlas»)
  ② строка о мосте называет соседей обхода: «соседи в обходе: tapas, onto»
  ②-встречный: соседей в cross_links нет — строка так и говорит, а не молчит
  ③ первое устройство не тронуто: tapas.archs/.mezosync/bridges/tapas-atlas — «tapas → PROTO (тебе)»
  ④ папка второго устройства другому контуру (bridges/aia-onto): «контур aia», не «тебе»

Нарочные поломки (копия sync_backoff.py с одним местом в прежнем виде; якорь не нашёлся —
«НЕ ЗАПУСТИЛАСЬ», не молчание):
  Р① обход без второго устройства       → ① и ④ проваливаются (писем из папок onto нет в строке)
  Р② сосед второго устройства — по имени папки → ① и ④ проваливаются (соседом названа «atlas» или «aia»,
     письмо PROTO — «контур onto»)
  Р③ перечня соседей в строке нет        → ② проваливается

Соседа onto нельзя было завести вовсе: bridge-groups.py читал имя группы из базы соседа, а открывать
чужую базу запрещает правило no-scan-external-contours. Случаи bridge-groups.py (испытуемый — из
каталога mezo_target; сосед на стенде — каталог без файла базы):
  ⑤ --target-group onto: сосед записан в cross_links, файл базы соседа не появился (не открывали)
  ⑥ --target-group с --bidirectional — отказ кодом 2, ничего не записано (это запись в чужую базу)
  ⑦ без --target-group и без базы соседа — отказ кодом 2 (прежде «❌» выходил кодом 0)
  Р④ имя соседа читается из его базы      → ⑤ проваливается
  Р⑤ отказ выходит кодом 0                → ⑥ и ⑦ проваливаются

⛔ Живую базу приёмка не открывает: база стенда создаётся с нуля.
"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

CASES = 0
OK = True


class NotRun(Exception):
    """Приёмка не смогла начаться — не «сломано» и не «в порядке»."""


def case(title, verdict, detail):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")


def weakened(src: Path, dest_dir: Path, anchor: str, replacement: str) -> Path:
    """Копия инструмента с одним местом в прежнем виде. Якорь обязан встретиться ровно раз."""
    text = src.read_text(encoding="utf-8")
    found = text.count(anchor)
    if found != 1:
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку некуда вложить — образец найден {found} раз в {src.name}:"
                     f" {anchor[:70]!r}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / src.name
    out.write_text(text.replace(anchor, replacement), encoding="utf-8")
    return out


def load(path: Path, name: str):
    """Модуль из файла; соседи (backlog и др.) ищутся в каталоге испытуемых скриптов."""
    scripts = str(mezo_target.script("sync_backoff.py").parent)
    if scripts not in sys.path:
        sys.path.append(scripts)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def letter(folder: Path, name: str, head: str, mtime: float) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(head + "\n\nтело письма\n", encoding="utf-8")
    os.utime(f, (mtime, mtime))


def stand(root: Path, tag: str, neighbours: bool = True) -> Path:
    """Контур стенда и два соседа: tapas (первое устройство) и onto (второе). → путь базы."""
    c = root / tag
    db = c / ".mezosync" / "mezosync.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO meta VALUES ('group_name', 'atlas');
        CREATE TABLE roles (role TEXT PRIMARY KEY);
        INSERT INTO roles VALUES ('PROTO'), ('COORD');
        CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT);
        CREATE TABLE cross_links (id INTEGER PRIMARY KEY AUTOINCREMENT, source_group TEXT NOT NULL,
            target_group TEXT NOT NULL, target_db_path TEXT NOT NULL, description TEXT,
            last_sync_at TEXT, UNIQUE(source_group, target_group));
    """)
    if neighbours:
        for group in ("tapas", "onto"):
            n = root / f"{tag}-{group}"
            (n / ".mezosync").mkdir(parents=True)
            con.execute("INSERT INTO cross_links (source_group, target_group, target_db_path)"
                        " VALUES ('atlas', ?, ?)", (group, str(n / ".mezosync" / "mezosync.db")))
    con.commit()
    con.close()
    return db


def run(tool: Path, root: Path, tag: str, neighbours: bool = True) -> str:
    """Два чтения: первое ставит отметку, затем соседи кладут письма, второе их называет."""
    sb = load(tool, f"sb_{tag}")
    db = stand(root, tag, neighbours)
    first = sb.news_line(db, "PROTO")
    if "первое чтение" not in first:
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: первое чтение не поставило отметку: {first!r}")
    later = time.time() + 120
    if neighbours:
        letter(root / f"{tag}-onto" / "bridges" / "atlas-onto", "2026-10-08-to-proto-probe.md",
               "Контур .onto, роль COORD — PROTO контура Atlas: проба\n\nКому: PROTO контура Atlas."
               " От кого: COORD контура .onto.", later)
        letter(root / f"{tag}-onto" / "bridges" / "aia-onto", "2026-10-08-to-aia-probe.md",
               "Контур .onto — контуру AIA\n\nКому: PROTO контура AIA.", later + 1)
        letter(root / f"{tag}-tapas" / "tapas.archs" / ".mezosync" / "bridges" / "tapas-atlas",
               "2026-10-08-tapas-probe.md", "Кому: PROTO контура Atlas.", later + 2)
    return sb.news_line(db, "PROTO")


def verdicts(out: str) -> dict:
    lines = out.splitlines()
    onto = [ln for ln in lines if "2026-10-08-to-proto-probe.md" in ln]
    aia = [ln for ln in lines if "2026-10-08-to-aia-probe.md" in ln]
    tapas = [ln for ln in lines if "2026-10-08-tapas-probe.md" in ln]
    return {
        "①": (bool(onto) and "onto → PROTO (тебе)" in onto[0], onto[0].strip() if onto else "письма onto в строке нет"),
        "②": (bool(lines) and "соседи в обходе: tapas, onto" in lines[0],
              lines[0].strip() if lines else "строки нет"),
        "③": (bool(tapas) and "tapas → PROTO (тебе)" in tapas[0], tapas[0].strip() if tapas else "письма tapas нет"),
        "④": (bool(aia) and "контур aia" in aia[0] and "(тебе)" not in aia[0],
              aia[0].strip() if aia else "письма в aia-onto нет в строке"),
    }


def groups_verdicts(tool: Path, root: Path, tag: str) -> dict:
    """bridge-groups.py --target-group: сосед заводится без открытия его базы (⑤–⑦)."""
    db = stand(root, tag, neighbours=False)
    neigh = root / f"{tag}-neigh"
    neigh_db = neigh / ".mezosync" / "mezosync.db"
    neigh.mkdir(parents=True)

    def go(*extra):
        r = subprocess.run([sys.executable, str(tool), "--source-db", str(db), "--target-db", str(neigh_db),
                            *extra], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(root / tag, PYTHONIOENCODING="utf-8"), timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def rows():
        con = sqlite3.connect(str(db))
        found = [g for (g,) in con.execute("SELECT target_group FROM cross_links ORDER BY id")]
        con.close()
        return found

    c6, o6 = go("--target-group", "onto", "--bidirectional")
    rows6 = rows()
    c7, o7 = go()
    c5, _ = go("--target-group", "onto", "--description", "проба")
    rows5 = rows()
    return {
        "⑤": (c5 == 0 and rows5 == ["onto"] and not neigh_db.exists(),
              f"код {c5}; соседи в cross_links: {rows5}; файл базы соседа появился: {neigh_db.exists()}"),
        "⑥": (c6 == 2 and "не сочетается" in o6 and rows6 == [],
              f"код {c6}; отказ словами: {'не сочетается' in o6}; соседей записано: {len(rows6)}"),
        "⑦": (c7 == 2 and "Не найдена target БД" in o7,
              f"код {c7} (ждём 2); отказ словами: {'Не найдена target БД' in o7}"),
    }


GROUPS_TITLES = {
    "⑤": "⑤ bridge-groups --target-group заводит соседа, не открывая его базу",
    "⑥": "⑥ --target-group с --bidirectional — отказ кодом 2, ничего не записано",
    "⑦": "⑦ без имени рукой и без базы соседа — отказ кодом 2, а не 0",
}

GROUPS_BREAKS = [
    ("Р④", "имя соседа читается из его базы", ("⑤",),
     "        target_name = args.target_group\n",
     "        target_name = get_group_name(str(target_path))\n"),
    ("Р⑤", "отказ выходит кодом 0", ("⑥", "⑦"),
     "    sys.exit(main())\n", "    main()\n"),
]

BREAKS = [
    ("Р①", "обход без второго устройства", ("①", "④"),
     'BRIDGE_LAYOUTS = ("*/.mezosync/bridges/*", "bridges/*")',
     'BRIDGE_LAYOUTS = ("*/.mezosync/bridges/*",)'),
    ("Р②", "сосед второго устройства — по имени папки", ("①", "④"),
     "        if d in owners:\n", "        if False:\n"),
    ("Р③", "перечня соседей в строке нет", ("②",),
     "{bridge_word} ({looked_word})", "{bridge_word}"),
]


def main() -> int:
    tool = mezo_target.script("sync_backoff.py")
    print(f"⚖️ испытуется: {tool}")
    root = mezo_stand.new("bite-684-bridge-")
    try:
        out = run(tool, root, "main")
        v = verdicts(out)
        case("① письмо в папке второго устройства (bridges/atlas-onto) названо: onto → PROTO (тебе)", *v["①"])
        case("② строка о мосте называет соседей обхода", *v["②"])
        case("③ первое устройство не тронуто: tapas → PROTO (тебе)", *v["③"])
        case("④ папка второго устройства другому контуру (aia-onto) — «контур aia», не «тебе»", *v["④"])
        empty = run(tool, root, "none", neighbours=False)
        head = empty.splitlines()[0] if empty else ""
        case("②-встречный: соседей в cross_links нет — строка так и говорит",
             "соседей в cross_links нет" in head, head.strip())
        bg = mezo_target.script("bridge-groups.py")
        print(f"⚖️ испытуется: {bg}")
        gv = groups_verdicts(bg, root, "groups")
        for key, title in GROUPS_TITLES.items():
            case(title, *gv[key])
        if not OK:
            # поломки меряют чувствительность случаев на ИСПРАВНОМ обходе; испытуемый, не прошедший
            # их сам (например, прежний обход одного устройства), — «НЕ ПРИНЯТО», а не «не запустилась»
            print("\n⚪ нарочные поломки не гонялись: испытуемый сам не прошёл случаи выше")
            print(f"🔴 ПИСЬМА СОСЕДЕЙ ДВУХ УСТРОЙСТВ — НЕ ПРИНЯТО — случаев {CASES}")
            return 1
        for tag, what, target, anchor, repl in BREAKS:
            broken = weakened(tool, root / f"break-{tag}", anchor, repl)
            bv = verdicts(run(broken, root, f"b{tag[-1]}"))
            fell = [k for k, (ok, _) in bv.items() if not ok]
            case(f"{tag} {what} — проваливаются ровно {', '.join(target)}",
                 fell == list(target), f"провалились: {', '.join(fell) or 'ничего'} · {bv[target[0]][1]}")
        for tag, what, target, anchor, repl in GROUPS_BREAKS:
            broken = weakened(bg, root / f"break-{tag}", anchor, repl)
            bv = groups_verdicts(broken, root, f"g{tag[-1]}")
            fell = [k for k, (ok, _) in bv.items() if not ok]
            case(f"{tag} {what} — проваливаются ровно {', '.join(target)}",
                 fell == list(target), f"провалились: {', '.join(fell) or 'ничего'} · {bv[target[0]][1]}")
    except NotRun as exc:
        print(exc)
        return 2
    print()
    print(f"{'✅' if OK else '🔴'} ПИСЬМА СОСЕДЕЙ ДВУХ УСТРОЙСТВ — {'ПРИНЯТО' if OK else 'НЕ ПРИНЯТО'} — случаев {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
