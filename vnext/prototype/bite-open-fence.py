#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-open-fence.py — приёмка: write-message.py не принимает молча записку с НЕЗАКРЫТЫМ блоком кода
(карточка 789).

ПОВОД. 2026-11-15 20:59 UTC `write-message.py --dry-run` на файле «заголовок, строка текста, открытый
ограничитель блока кода в начале строки, одна строка внутри, закрывающего нет» вернул код 0 и ни слова
об обрыве. Текст, оборванный при сборке, уходил в ленту как законченный.

Случаи (у каждого свой ключ и строка итога):
  ①-1 ограничитель из ``` в начале строки, закрывающего нет — отказ кодом 2, слова «незакрытый блок
       кода» и номер строки в выводе, записок +0; и то же в холостом прогоне
  ①-2 то же с ограничителем из ~~~
  ①-3 то же с ограничителем, стоящим с отступом
  ①-4 блок открыт ограничителем из ```, ниже стоит строка из ~~~ — ограничитель ДРУГОГО знака блок
       не закрывает: отказ с номером строки открывающего (случай K2 приёмки чужой рукой, COORD 16.11)
  ①-5 первый блок закрыт, второй открыт ниже и оборван — в отказе номер строки ВТОРОГО, открытого
       ограничителя, а не первого в тексте (случай K4 оттуда же)
  ①-б тот же файл с --allow-open-fence — код 0, записка записана, предупреждение напечатано
  ②-1 ВСТРЕЧНЫЙ: все блоки закрыты, а внутри обычной строки стоит ограничитель цитатой (общее число
       ограничителей в тексте нечётное) — код 0, без предупреждения
  ②-2 ВСТРЕЧНЫЙ: блок из четырёх знаков, внутри которого строка из трёх (вложенный образец), — закрыт
  ②-3 ВСТРЕЧНЫЙ: блок с именем языка после ограничителя — закрыт
  ②-4 ВСТРЕЧНЫЙ: текст вовсе без блоков
  ②-5 ВСТРЕЧНЫЙ: строка начинается с ``` и в ней же закрывается (код внутри строки) — это не
       начало блока: у ограничителя из ` в остатке строки знака ` не бывает
  ③    холостой разбор ВСЕХ записок копии базы новой функцией (импорт функции из файла инструмента):
       «записок N · срабатываний M». Копия берётся только на чтение, путь — --scan-db; без него случай
       честно говорит «проверять нечем» и НЕ проходит молча
  ④    нарочная поломка внутри приёмки: копия инструмента, где проверка выключена, — ①-1 проходит
       молча с кодом 0 (поломка видна), ②-1 и ③ целы

Живой базы приёмка не открывает, когда названа --scan-db: схема для стенда берётся из неё (только на
чтение). Без --scan-db схему берёт живая база контура (тоже только на чтение, через empty_db).
Испытуемый write-message.py — по MEZO_SCRIPTS_ROOT (mezo_target), по умолчанию — установленный в контуре.
Код выхода: 0 — всё сошлось; 1 — не сошлось; 2 — отказ мерить (нет инструмента или базы).
"""
from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

ROLE = "FENCEPROBE"
NL = "\n"
FENCE3 = "`" * 3
FENCE4 = "`" * 4
TILDE3 = "~" * 3
# Якорь нарочной поломки: единственная строка, где проверка собственно вызывается. Заменённая на
# присваивание пустого значения, она оставляет и функцию, и флаг на месте — выключен только вызов.
BREAK_ANCHOR = b"_open_fence = find_open_fence(args.body)"
BREAK_REPLACEMENT = b"_open_fence = None"

OK = FAIL = 0


def case(key: str, name: str, cond: bool, detail: str = "") -> bool:
    global OK, FAIL
    print(("✅ " if cond else "🔴 ") + key + " " + name)
    if detail:
        print("     " + detail)
    if cond:
        OK += 1
    else:
        FAIL += 1
    return cond


def lines(*parts: str) -> str:
    return NL.join(parts) + NL


def count_notes(db: Path) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        con.close()


def seed(db: Path) -> None:
    con = sqlite3.connect(db)
    try:
        con.execute("INSERT OR IGNORE INTO roles (role, lifecycle, lifecycle_by, zone, in_roster,"
                    " created_at) VALUES (?,'alive','проба','приёмка',0,datetime('now'))", (ROLE,))
        con.commit()
    finally:
        con.close()


def load_function(tool: Path):
    """Функция разбора из файла инструмента — импортом, без запуска процесса на каждую записку."""
    sys.path.insert(0, str(tool.parent))
    try:
        spec = importlib.util.spec_from_file_location(f"wm_fence_{abs(hash(str(tool)))}", tool)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return getattr(module, "find_open_fence", None)


def scan_all(function, scan_db: Path):
    """(число записок, [(номер записки, строка открывающего ограничителя, её начало)])."""
    con = sqlite3.connect(f"file:{scan_db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        has_all = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='messages_all'"
                              ).fetchone()[0]
        rows = con.execute(f"SELECT id, body_md FROM {'messages_all' if has_all else 'messages'}"
                           " ORDER BY id").fetchall()
    finally:
        con.close()
    hits = []
    for note_id, body in rows:
        found = function(body or "")
        if found:
            hits.append((note_id, found[0], found[1]))
    return len(rows), hits


class Stand:
    """Одна обстановка: копия испытуемого инструмента и подставная база (схема без строк)."""

    def __init__(self, root: Path, name: str, schema_db: Path, tool_source: Path, breaker: bool):
        self.container = root / name / "container"
        (self.container / ".mezosync").mkdir(parents=True)
        self.db = mezo_stand.empty_db(schema_db, self.container / ".mezosync" / "mezosync.db")
        seed(self.db)
        self.tool = mezo_stand.copy_tool(tool_source, root / name / "tools")
        self.notes = root / name / "notes"
        self.notes.mkdir()
        if breaker:
            data = self.tool.read_bytes()
            found = data.count(BREAK_ANCHOR)
            if found != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломка не построена — якорь найден {found} раз(а), "
                         "а нужен ровно один")
            self.tool.write_bytes(data.replace(BREAK_ANCHOR, BREAK_REPLACEMENT))
        self.counter = 0

    def write(self, text: str, *extra: str):
        self.counter += 1
        note = self.notes / f"note{self.counter}.md"
        note.write_text(text, encoding="utf-8", newline="")
        r = subprocess.run([sys.executable, "-u", "-X", "utf8", str(self.tool), "--role", ROLE,
                            "--db", str(self.db), "--file", str(note), *extra],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(self.container, PYTHONIOENCODING="utf-8"))
        return r.returncode, (r.stdout or "") + (r.stderr or "")


def refusal_case(stand: Stand, key: str, name: str, text: str, line_number: int, label: str) -> bool:
    """Отказ в обычной отправке и в холостом прогоне; в базу не ложится ничего."""
    ok = True
    for mode, extra in (("обычная", ()), ("холостой прогон", ("--dry-run",))):
        before = count_notes(stand.db)
        rc, out = stand.write(text, *extra)
        after = count_notes(stand.db)
        good = (rc == 2 and "незакрытый блок кода" in out and f"строка {line_number}" in out
                and after == before)
        ok &= case(f"{key} [{mode}]", name, good,
                   f"код {rc} (ждём 2) · есть слова и «строка {line_number}»: "
                   f"{'да' if 'незакрытый блок кода' in out and f'строка {line_number}' in out else 'нет'}"
                   f" · записок {before} → {after}" + ("" if good else NL + "     вывод: " + out[-400:]))
    return ok


def counter_case(stand: Stand, key: str, name: str, text: str) -> bool:
    before = count_notes(stand.db)
    rc, out = stand.write(text)
    after = count_notes(stand.db)
    good = rc == 0 and "незакрытый блок кода" not in out and after == before + 1
    return case(key, name, good,
                f"код {rc} (ждём 0) · предупреждения нет: {'да' if 'незакрытый блок кода' not in out else 'нет'}"
                f" · записок {before} → {after}" + ("" if good else NL + "     вывод: " + out[-400:]))


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: незакрытый блок кода в write-message.py")
    ap.add_argument("--scan-db", help="копия базы, ТОЛЬКО на чтение: схема стенда и холостой разбор "
                                      "всех записок (случай ③)")
    a = ap.parse_args()

    tool_source = mezo_target.script("write-message.py")
    print(f"⚖️ испытуется: {mezo_target.label()}")
    scan_db = Path(a.scan_db) if a.scan_db else None
    if scan_db is not None and not scan_db.is_file():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: копия базы не найдена: {scan_db}")
        return mezo_stand.finish(2)
    schema_db = scan_db if scan_db is not None else mezo_paths.live_db_for_check(__file__, "bite-open-fence.py")

    root = mezo_stand.new("bite-open-fence-")
    try:
        good = Stand(root, "good", schema_db, tool_source, breaker=False)

        open3 = lines("# Заголовок записки", "строка текста перед блоком", FENCE3, "строка внутри блока")
        refusal_case(good, "①-1", "ограничитель из ``` без закрывающего — отказ", open3, 3, "```")
        open_tilde = lines("# Заголовок записки", "строка текста перед блоком", TILDE3 + "bash",
                           "строка внутри блока")
        refusal_case(good, "①-2", "ограничитель из ~~~ без закрывающего — отказ", open_tilde, 3, "~~~")
        open_indented = lines("# Заголовок записки", "строка текста перед блоком", "   " + FENCE3 + "python",
                              "   строка внутри блока")
        refusal_case(good, "①-3", "ограничитель с отступом без закрывающего — отказ", open_indented, 3, "отступ")
        # ①-4 и ①-5 — случаи K2 и K4 приёмки чужой рукой (COORD, 16.11). Без них две нарочные поломки
        # функции разбора — «закрывает ограничитель любого знака» и «номер — первого ограничителя
        # в тексте» — проходили приёмку целиком: все открытые блоки случаев ① стояли первыми в тексте,
        # а чужого знака после открытого блока не было ни в одном.
        other_mark = lines("# Заголовок записки", "строка текста перед блоком", FENCE3,
                           "строка внутри блока", TILDE3, "строка после чужого ограничителя")
        refusal_case(good, "①-4", "блок из ``` и строка из ~~~ ниже: другой знак блок не закрывает — отказ",
                     other_mark, 3, "другой знак")
        second_open = lines("# Заголовок записки", "строка текста перед блоком", FENCE3,
                            "внутри первого блока", FENCE3, "текст между блоками", "ещё строка текста",
                            FENCE3 + "python", "второй блок оборван здесь")
        refusal_case(good, "①-5", "первый блок закрыт, второй оборван — в отказе строка второго, не первого",
                     second_open, 8, "второй блок")

        before = count_notes(good.db)
        rc, out = good.write(open3, "--allow-open-fence")
        after = count_notes(good.db)
        case("①-б", "с --allow-open-fence записка проходит, а предупреждение остаётся в выводе",
             rc == 0 and after == before + 1 and "незакрытый блок кода" in out and "строка 3" in out,
             f"код {rc} (ждём 0) · записок {before} → {after}"
             + ("" if "незакрытый блок кода" in out else NL + "     вывод: " + out[-400:]))

        counter_case(good, "②-1", "ограничитель цитатой внутри строки при закрытых блоках — без предупреждения",
                     lines(FENCE3, "код", FENCE3, "в тексте стоит " + FENCE3 + " посреди строки, это цитата"))
        counter_case(good, "②-2", "блок из четырёх знаков со строкой из трёх внутри — закрыт",
                     lines(FENCE4, FENCE3, "вложенный образец", FENCE3, FENCE4))
        counter_case(good, "②-3", "блок с именем языка после ограничителя — закрыт",
                     lines(FENCE3 + "python", "x = 1", FENCE3))
        counter_case(good, "②-4", "текст вовсе без блоков", lines("# Заголовок", "обычный текст без блоков"))
        counter_case(good, "②-5", "строка начинается с ``` и в ней же закрывается — код внутри строки, не блок",
                     lines(FENCE3 + "код" + FENCE3 + " и текст после него", "обычная строка следом"))

        # ③ холостой разбор всех записок копии базы
        hits_good = None
        if scan_db is None:
            case("③", "холостой разбор всех записок — проверять нечем: не назван --scan-db", False,
                 "назови копию базы: --scan-db <путь> (читается только на чтение)")
        else:
            function = load_function(good.tool)
            if function is None:
                case("③", "в файле инструмента нет функции разбора find_open_fence", False)
            else:
                total, hits_good = scan_all(function, scan_db)
                print(f"     записок {total} · срабатываний {len(hits_good)}")
                for note_id, line_number, head in hits_good:
                    print(f"     срабатывание: записка #{note_id}, строка {line_number}: {head}")
                case("③", "холостой разбор всех записок копии базы — срабатываний нет",
                     total > 0 and not hits_good,
                     f"записок {total} · срабатываний {len(hits_good)}"
                     + ("" if total > 0 else " — в копии нет ни одной записки, судить нечем"))

        # ④ нарочная поломка: проверка выключена в копии инструмента
        broken = Stand(root, "broken", schema_db, tool_source, breaker=True)
        before = count_notes(broken.db)
        rc, out = broken.write(open3)
        after = count_notes(broken.db)
        case("④-1", "поломка видна: при выключенной проверке случай ①-1 проходит молча кодом 0",
             rc == 0 and "незакрытый блок кода" not in out and after == before + 1,
             f"код {rc} (ждём 0) · записок {before} → {after}")
        before = count_notes(broken.db)
        rc, out = broken.write(lines(FENCE3, "код", FENCE3, "в тексте стоит " + FENCE3 + " посреди строки"))
        after = count_notes(broken.db)
        case("④-2", "при поломке встречный случай ②-1 цел: код 0 и без предупреждения",
             rc == 0 and "незакрытый блок кода" not in out and after == before + 1,
             f"код {rc} (ждём 0) · записок {before} → {after}")
        if scan_db is None:
            case("④-3", "при поломке случай ③ цел — проверять нечем: не назван --scan-db", False)
        else:
            function = load_function(broken.tool)
            total_b, hits_b = scan_all(function, scan_db) if function else (0, None)
            case("④-3", "при поломке случай ③ цел: тот же разбор, то же число срабатываний",
                 function is not None and hits_good is not None and hits_b == hits_good and total_b > 0,
                 f"записок {total_b} · срабатываний {len(hits_b) if hits_b is not None else 'нет функции'}")
    finally:
        mezo_stand.release(root)

    print("-" * 78)
    print(f"{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
