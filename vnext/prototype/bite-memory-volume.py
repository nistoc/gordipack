#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: проверка роста объёма памяти (guard-all ⑯) — из базы, с ростом, честная про базу сравнения.

ПОВОД (план 3 этап 7, 14.08). Разовая чистка памяти без сторожа отрастает обратно молча.
Сторож информационный: объём не грех, видимой должна быть ДЕЛЬТА от рубежа в meta.

⚖️ С ДВУХ СТОРОН:
  · объёмы и дельта — ИЗ БАЗЫ: роль, добавленная в копию, появляется в счёте (не впечатанный список);
  · потерянная база сравнения — сказано вслух, а не молчание и не выдуманный ноль;
  · строка НЕ красит контур: имя «память: объём» не появляется в перечне красных.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: guard-all зовётся с --db на КОПИЯХ.

НУЛЕВОЙ ДЕНЬ КОНТУРА (заявка 29 пакета): у свежесобранного контура нет базы сравнения объёма памяти
и нет реестра известного долга приёмок — это свойства нового контура, и общий прогон говорит о них
«ℹ️ … свойство нового контура», а не «⚠️». Контур для этих случаев СОБИРАЕТСЯ из пакета сборщиком
init-group.py (как у bite-fresh-circuit.py); нулевой день — по ленте его базы (в ней нет записок).
  ④ свежий контур: строка объёма памяти — «ℹ️ … свойство нового контура», «⚠️ память: объём» нет
  ⑤ свежий контур: строка про реестр долга приёмок — «ℹ️ … свойство нового контура», «⚠️» про него нет
  ⑥ в ленте уже одна записка, базы сравнения нет: «⚠️ … БАЗЫ СРАВНЕНИЯ НЕТ», как было
  ⑦ то же, реестра нет: «⚠️ реестра известного долга рядом нет», как было (базу для суждения общий
    прогон передаёт проверке ЯВНО: у контейнера своя база — с пустой лентой, а судить надо ту, на которую
    натравлен прогон)
  ⑧ НАРОЧНАЯ ПОЛОМКА (копия guard-all.py): у строки объёма нулевой день не различается ⇒ красит РОВНО ④
  ⑨ НАРОЧНАЯ ПОЛОМКА (копия guard-all.py): проверке реестра не передана база ⇒ красит РОВНО ⑦
  ⑩ встречный к месту: реестр рядом с проверкой (как у живого контура) — строк про реестр нет,
    на такой копии не держатся РОВНО ⑤ и ⑦
  ⑪ свежий контур: строка проверки чтения ленты — «ℹ️ активных ролей нет … свойство нового контура»
  ⑫ свежий контур: строка про замороженные md — «ℹ️ … свойство нового контура»
  ⑬ в ленте одна записка трёхчасовой давности (активных ролей нет): «⚠️ активных ролей НЕТ», как было
  ⑭ то же: «⚠️ замороженные md: … НОЛЬ», как было
  ⑮ НАРОЧНАЯ ПОЛОМКА (копия guard-write-without-read.py): нулевой день не различается ⇒ красит РОВНО ⑪
  ⑯ НАРОЧНАЯ ПОЛОМКА (копия guard-all.py): у строки замороженных md нулевой день не различается ⇒
    красит РОВНО ⑫
  Испытуемые здесь ДВА файла контура: guard-all.py и guard-write-without-read.py — оба кладутся копией
  среди инструментов свежего контура (проверку чтения ленты общий прогон ищет рядом с собой).
Общий прогон ищет проверки РЯДОМ С СОБОЙ (guard-all.py, tool()), а проверка реестра ищет реестр рядом
с собой. Поэтому ④–⑦ судят КОПИЮ испытуемого guard-all.py среди инструментов свежего контура — там
же, где копии поломок, — а не файл на его месте: живой guard-all находит живую проверку с реестром
рядом, и ветка «реестра рядом нет» там не наступает (замер 2026-10-06 12:54 UTC в Atlas: ⑤⑦ провалились
на исправном guard-all — судили место, а не нулевой день).
Копии кладутся в каталог из переменной MEZO_BREAKS_DIR (если задана), иначе — в стенд,
который убирается при успехе.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_stand  # копия живой базы — ТОЛЬКО через snapshot_db (карточка #505/#659)
import mezo_target

GUARD = mezo_target.script("guard-all.py")
READ_GUARD = mezo_target.script("guard-write-without-read.py")  # строка чтения ленты (случаи ⑪ ⑬ ⑮)
LIVE_DB = mezo_paths.live_db()

CASES: list[tuple[str, bool, str]] = []


def ensure_baseline(db: Path) -> None:
    """Своя подставная база сравнения (meta.memory_volume_baseline) — когда её в этой
    КОПИИ нет вовсе (карточка #667, пустой свежесобранный контур: точку отсчёта по
    построению пакета там никто не ставил, это честное отсутствие, а не поломка).

    Случаи ①② здесь судят, что строка объёма ЕСТЬ и считает рост по БАЗЕ (не по
    впечатанному списку) — для этого нужно хоть какое-то согласие о точке отсчёта,
    а не её конкретные числа: случай ③ отдельно и честно проверяет САМО отсутствие
    на другой копии и этой правки не касается."""
    con = sqlite3.connect(db)
    has = con.execute(
        "SELECT 1 FROM meta WHERE key='memory_volume_baseline'").fetchone()
    if not has:
        baseline = json.dumps({"date": "2026-09-19", "roles": {}})
        con.execute("INSERT INTO meta (key, value) VALUES "
                   "('memory_volume_baseline', ?)", (baseline,))
        con.commit()
    con.close()


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run_guard(db: Path) -> str:
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def volume_line(out: str) -> str:
    for ln in out.splitlines():
        if "память: объём" in ln:
            return ln
    return ""


# ── нулевой день контура (заявка 29 пакета): контур собирается из пакета, как у bite-fresh-circuit.py ──
DEBT_PHRASE = "реестра известного долга рядом нет"
# Синтетический вызов без env= — чтобы проверка приёмок печатала строку про реестр при ЛЮБОМ составе
# пакета (без находок она молчит, и случай судил бы пустоту).
FAKE_CONTAINER_TOOL = ('# -*- coding: utf-8 -*-\n"""синтетика приёмки: притворяется читающим контур."""\n'
                       'import mezo_paths  # noqa: F401\n')
FAKE_BITE_NO_ENV = ('import subprocess, sys\nfrom pathlib import Path\n'
                    'TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")\n\n\n'
                    'def call():\n    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)\n')


def find_pack():
    """Корень пакета — теми же местами, что у bite-fresh-circuit.py; не нашёлся — None."""
    candidates = []
    try:
        candidates.append(mezo_paths.template_root())
    except SystemExit:
        pass
    here = Path(__file__).resolve().parent
    candidates += [here.parent.parent / "gordipack", here.parent / "gordipack"]
    return next((p for p in candidates if (p / "scripts" / "init-group.py").exists()), None)


def build_fresh_circuit(pack: Path):
    """Свежий контур сборщиком init-group.py пакета. → (корень, база или None, хвост вывода сборщика)."""
    root = mezo_stand.new("bite-memory-volume-fresh-")
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str(pack / "scripts" / "init-group.py"), "--name", "bite",
                        "--path", str(mez), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       env=mezo_stand.stand_env(root))
    db = mez / "mezosync.db"
    if r.returncode == 0 and db.exists() and (mez / "scripts").is_dir():
        (mez / "scripts" / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
        (mez / "scripts" / "bite-fake-no-env.py").write_text(FAKE_BITE_NO_ENV, encoding="utf-8")
        return root, db, ""
    return root, None, ((r.stdout or "") + (r.stderr or ""))[-600:]


def breaks_dir(stand: Path, name: str) -> Path:
    """Куда класть копию инструментов с нарочной поломкой: <MEZO_BREAKS_DIR>/<имя>, а без переменной —
    внутрь стенда (он убирается при успехе). Так копию поломки можно предъявить глазами."""
    base = os.environ.get("MEZO_BREAKS_DIR")
    d = (Path(base) / name) if base else (stand / "breaks" / name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def copy_tools(fresh_root: Path, name: str, guard_text: str, read_text: str) -> Path:
    """Копия ВСЕХ инструментов свежего контура (они самодостаточны); guard-all.py и
    guard-write-without-read.py в ней — данными текстами испытуемых. → путь к копии guard-all.py."""
    bdir = breaks_dir(fresh_root, name)
    shutil.copytree(fresh_root / ".mezosync" / "scripts", bdir / "scripts", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    guard = bdir / "scripts" / "guard-all.py"
    guard.write_text(guard_text, encoding="utf-8")
    (bdir / "scripts" / "guard-write-without-read.py").write_text(read_text, encoding="utf-8")
    return guard


def run_guard_in(guard: Path, db: Path, container: Path) -> str:
    """Общий прогон НА КОНТУРЕ СТЕНДА: среда закреплена за стендом, база названа --db."""
    r = subprocess.run([sys.executable, str(guard), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
    return (r.stdout or "") + (r.stderr or "")


def marked_lines(out: str, phrase: str) -> list[str]:
    return [l.strip() for l in out.splitlines() if phrase in l]


ALL_MARKS = ("④", "⑤", "⑥", "⑦", "⑪", "⑫", "⑬", "⑭")
FEED_PHRASE = "активных ролей"
# не «замороженные md»: это имя стоит и в строке «✅ прошли N: … · замороженные md · …»
FROZEN_PHRASE = "замороженные md: каталог найден"


def one_line(lines: list[str], sign: str, words: str) -> bool:
    return len(lines) == 1 and lines[0].startswith(sign) and words in lines[0]


def zero_day_verdicts(guard: Path, container: Path, fresh_db: Path, used_db: Path):
    """Общий прогон на двух базах ОДНОГО контура: без записок в ленте и с одной запиской. →
    {метка: (✅/🔴, подробность)}. База контейнера — пустая лентой (fresh_db), --db на
    used_db называет ДРУГУЮ: проверка реестра обязана судить ту, что названа, а не ту, что рядом."""
    out_n = run_guard_in(guard, fresh_db, container)
    out_o = run_guard_in(guard, used_db, container)
    # про реестр проверка печатает ДВЕ строки (сама находка и «судить строго») — судим обе
    mem_n, mem_o = marked_lines(out_n, "память: объём"), marked_lines(out_o, "память: объём")
    debt_n = marked_lines(out_n, DEBT_PHRASE) + marked_lines(out_n, "судить строго")
    debt_o = marked_lines(out_o, DEBT_PHRASE) + marked_lines(out_o, "судить строго")
    feed_n, feed_o = marked_lines(out_n, FEED_PHRASE), marked_lines(out_o, FEED_PHRASE)
    frozen_n, frozen_o = marked_lines(out_n, FROZEN_PHRASE), marked_lines(out_o, FROZEN_PHRASE)

    def note(lines, nothing):
        return " | ".join(l[:110] for l in lines) if lines else nothing

    return {
        "④": (one_line(mem_n, "ℹ️", "свойство нового контура"), note(mem_n, "строки про объём нет")),
        "⑤": (len(debt_n) == 2 and all(l.startswith("ℹ️") for l in debt_n)
              and "свойство нового контура" in debt_n[0],
              " | ".join(l[:70] for l in debt_n) if debt_n else "строк про реестр нет"),
        "⑥": (one_line(mem_o, "⚠️", "БАЗЫ СРАВНЕНИЯ НЕТ"), note(mem_o, "строки про объём нет")),
        "⑦": (len(debt_o) == 2 and all(l.startswith("⚠️") for l in debt_o),
              " | ".join(l[:70] for l in debt_o) if debt_o else "строк про реестр нет"),
        "⑪": (one_line(feed_n, "ℹ️", "свойство нового контура"), note(feed_n, "строки про чтение ленты нет")),
        "⑫": (one_line(frozen_n, "ℹ️", "свойство нового контура"), note(frozen_n, "строки про замороженные md нет")),
        "⑬": (one_line(feed_o, "⚠️", "активных ролей НЕТ"), note(feed_o, "строки про чтение ленты нет")),
        "⑭": (one_line(frozen_o, "⚠️", "НОЛЬ"), note(frozen_o, "строки про замороженные md нет")),
    }


# Нарочные поломки КОПИИ испытуемого: в каком файле · якорь (должен встречаться в нём ровно раз) →
# замена, и множество случаев, которые поломка обязана провалить — ровно их, не больше и не меньше.
ZERO_DAY_BREAKS = (
    ("⑧", "zero-day-memory", "guard-all.py",
     '        zero_day = bool(getattr(mezo_paths, "is_zero_day", lambda _db: False)(conn))',
     '        zero_day = False  # ПОЛОМКА (⑧): у строки объёма нулевой день не различается',
     {"④"}, "нулевой день у строки объёма не различается"),
    ("⑨", "zero-day-wiring", "guard-all.py",
     '"--db", str(DB), script_path=tool("check-acceptance-env.py"))',
     'script_path=tool("check-acceptance-env.py"))  # ПОЛОМКА (⑨): проверке реестра база не передана',
     {"⑦"}, "проверке реестра не передана база"),
    ("⑮", "zero-day-feed-reading", "guard-write-without-read.py",
     '    zero_day = bool(getattr(mezo_paths, "is_zero_day", lambda _db: False)(conn))',
     '    zero_day = False  # ПОЛОМКА (⑮): у строки чтения ленты нулевой день не различается',
     {"⑪"}, "у строки чтения ленты нулевой день не различается"),
    ("⑯", "zero-day-frozen-md", "guard-all.py",
     '        if bool(getattr(mezo_paths, "is_zero_day", lambda _db: False)(conn)):',
     '        if False:  # ПОЛОМКА (⑯): у строки замороженных md нулевой день не различается',
     {"⑫"}, "у строки замороженных md нулевой день не различается"),
)
CASE_TITLES = {
    "④": "④ свежий контур: строка объёма памяти — «ℹ️ … свойство нового контура», а не «⚠️»",
    "⑤": "⑤ свежий контур: строки про реестр долга приёмок — «ℹ️ … свойство нового контура», «⚠️» нет",
    "⑥": "⑥ в ленте одна записка, базы сравнения нет — «⚠️ … БАЗЫ СРАВНЕНИЯ НЕТ», как было",
    "⑦": "⑦ в ленте одна записка, реестра нет — «⚠️ реестра известного долга рядом нет», как было "
         "(база названа --db, а у контейнера своя — с пустой лентой)",
    "⑪": "⑪ свежий контур: строка чтения ленты — «ℹ️ активных ролей нет … свойство нового контура»",
    "⑫": "⑫ свежий контур: строка про замороженные md — «ℹ️ … свойство нового контура», а не «⚠️»",
    "⑬": "⑬ в ленте одна записка трёхчасовой давности — «⚠️ активных ролей НЕТ», как было",
    "⑭": "⑭ в ленте одна записка — «⚠️ замороженные md: … НОЛЬ», как было",
}


def run_zero_day_cases() -> None:
    """Случаи ④–⑯: нулевой день контура (заявка 29 пакета). Контур собирается из пакета."""
    pack = find_pack()
    if pack is None:
        raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: пакета с scripts/init-group.py не нашлось (ни по mezo_paths."
                         "template_root(), ни рядом) — свежий контур собрать не из чего, случаи ④–⑯ не "
                         "состоялись. Это не «зелёное».")
    fresh_root, fresh_db, build_note = build_fresh_circuit(pack)
    if fresh_db is None:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: сборщик init-group.py не собрал контур: {build_note}")
    used_db = mezo_stand.snapshot_db(fresh_db, fresh_root / ".mezosync" / "mezosync-used.db")
    con = sqlite3.connect(str(used_db))
    # Записка трёхчасовой давности: день уже не нулевой, а роль-автор вне окна активности проверки
    # чтения ленты (90 мин) — так «активных ролей нет» наступает и на НЕнулевом дне (случай ⑬).
    con.execute("INSERT INTO messages (writer_role, body_md, timestamp) VALUES ('COORD', "
                "'проба приёмки: в ленте уже есть записка — день не нулевой', datetime('now', '-3 hours'))")
    con.commit()
    con.close()

    # Испытуемые — КОПИЕЙ среди инструментов свежего контура (почему — в шапке, случай ⑩).
    sources = {"guard-all.py": GUARD.read_text(encoding="utf-8"),
               "guard-write-without-read.py": READ_GUARD.read_text(encoding="utf-8")}
    real_guard = copy_tools(fresh_root, "zero-day-real", sources["guard-all.py"],
                            sources["guard-write-without-read.py"])
    real = zero_day_verdicts(real_guard, fresh_root, fresh_db, used_db)
    for mark in ALL_MARKS:
        case(CASE_TITLES[mark], real[mark][0], f"копия {real_guard}: {real[mark][1]}")

    for mark, name, fname, anchor, replacement, must_fail, what in ZERO_DAY_BREAKS:
        if sources[fname].count(anchor) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь поломки «{name}» найден в {fname} "
                             f"{sources[fname].count(anchor)} раз (ждали 1) — испытуемое изменилось")
        # копия с одной подменённой строкой в одном из двух испытуемых
        texts = dict(sources)
        texts[fname] = texts[fname].replace(anchor, replacement)
        broken = copy_tools(fresh_root, name, texts["guard-all.py"], texts["guard-write-without-read.py"])
        got = zero_day_verdicts(broken, fresh_root, fresh_db, used_db)
        failed = {m for m, (ok, _note) in got.items() if not ok}
        case(f"{mark} поломка «{what}» ({fname}): красит РОВНО {' '.join(sorted(must_fail))}, "
             f"остальные из {' '.join(ALL_MARKS)} зелёные",
             failed == must_fail,
             f"копия {broken}: провалились {sorted(failed) or 'никто'} (ждали {sorted(must_fail)}); "
             + "; ".join(f"{m} {'✅' if got[m][0] else '🔴'}" for m in ALL_MARKS)
             + f" · строка на копии для {sorted(must_fail)[0]}: {got[sorted(must_fail)[0]][1][:90]}")

    # ⑩ встречный к месту: реестр рядом с проверкой — ветки «реестра рядом нет» нет, ⑤⑦ не держатся
    near_guard = copy_tools(fresh_root, "zero-day-near-debt", sources["guard-all.py"],
                            sources["guard-write-without-read.py"])
    (near_guard.parent / "acceptance-env-debt.txt").write_text("", encoding="utf-8")
    near = zero_day_verdicts(near_guard, fresh_root, fresh_db, used_db)
    near_failed = {m for m, (ok, _note) in near.items() if not ok}
    case("⑩ встречный к месту: реестр рядом с проверкой (как у живого контура) — строк про реестр нет, "
         "не держатся РОВНО ⑤ и ⑦",
         near_failed == {"⑤", "⑦"},
         f"копия {near_guard}: провалились {sorted(near_failed) or 'никто'} (ждали ['⑤', '⑦']) · "
         f"⑤: {near['⑤'][1][:70]}")


def main(zero_day: bool = True) -> int:
    CASES.clear()
    with tempfile.TemporaryDirectory() as tmp:
        # ① Нормальная копия: строка с объёмом и ростом из базы.
        db = Path(tmp) / "a.db"
        mezo_stand.snapshot_db(LIVE_DB, db)
        ensure_baseline(db)
        ln = volume_line(run_guard(db))
        m = re.search(r"объём (\d+) симв по (\d+) ролям", ln)
        case("① строка печатает объём и рост из базы", bool(m) and "рост" in ln, ln[:110])
        n_roles = int(m.group(2)) if m else 0

        # ② Роль, добавленная в копию, появляется в счёте — список не впечатан.
        con = sqlite3.connect(db)
        con.execute("INSERT INTO roles (role, lifecycle) VALUES ('ЗОНДОБЪЁМ', 'alive')")
        con.execute("INSERT INTO phoenix (role, section, body, saved_at) "
                    "VALUES ('ЗОНДОБЪЁМ','state','зонд', datetime('now'))")
        con.commit(); con.close()
        ln2 = volume_line(run_guard(db))
        m2 = re.search(r"по (\d+) ролям", ln2)
        case("② подложная роль в копии видна счётом (роли из БАЗЫ)",
             bool(m2) and int(m2.group(1)) == n_roles + 1,
             f"было {n_roles}, стало {m2.group(1) if m2 else '—'}")

        # ③ Потерянная база сравнения — сказано вслух; контур из-за этого НЕ краснеет.
        db3 = Path(tmp) / "b.db"
        mezo_stand.snapshot_db(LIVE_DB, db3)
        con = sqlite3.connect(db3)
        con.execute("DELETE FROM meta WHERE key='memory_volume_baseline'")
        con.commit(); con.close()
        out3 = run_guard(db3)
        ln3 = volume_line(out3)
        case("③ потерянная база сравнения — сказано вслух, не ноль", "БАЗЫ СРАВНЕНИЯ НЕТ" in ln3, ln3[:110])
        red_line = next((l for l in out3.splitlines() if "КРАСНЫХ" in l), "")
        case("③b имя «память: объём» НЕ в перечне красных (информационная)",
             "память: объём" not in red_line, red_line[:110])

    if zero_day:
        run_zero_day_cases()

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}")
    return 0


MUTANTS = {
    # Текст образца — тот, что guard-all.py печатает сейчас. Прежний образец искал «РУБЕЖА НЕТ», которого
    # там давно нет: поломка не вставала, и самопроверка всегда считала её выжившей (найдено 06.10).
    "M1-базы-сравнения-нет-молчит": lambda s: s.replace(
        'print("⚠️ память: объём — БАЗЫ СРАВНЕНИЯ НЕТ (meta.memory_volume_baseline): рост "\n'
        '                  "мерить не от чего. Это не ноль и не зелёный.")',
        "pass"),
    "M2-строка-объёма-исчезла": lambda s: s.replace(
        '            print(f"✅ память: объём {total_now} симв по {len(vols)} ролям · рост от "',
        '            _ = (f"✅ память: объём {total_now} симв по {len(vols)} ролям · рост от "'),
}


def selftest() -> int:
    # Случаи нулевого дня (④–⑨) собирают свежий контур и свои поломки на КОПИЯХ; самопроверка правит
    # испытуемый файл на месте и судит только ①–③ — поэтому зовёт main без них.
    print("═══ чистый прогон ═══")
    if main(zero_day=False) != 0:
        print("🔴 ПРИЁМКА КРАСНАЯ НА ЧИСТОМ — самопроверка невозможна")
        return 1
    survived = 0
    orig = GUARD.read_text(encoding="utf-8")
    for name, mut in MUTANTS.items():
        bad = mut(orig)
        if bad == orig:
            print(f"⚠️ {name}: паттерн не найден — нарочная поломка НЕ ВСТАЛА, считаю ВЫЖИВШИМ")
            survived += 1
            continue
        GUARD.write_text(bad, encoding="utf-8")
        try:
            print(f"═══ нарочная поломка {name} ═══")
            caught = main(zero_day=False) != 0
        finally:
            GUARD.write_text(orig, encoding="utf-8")
        print(f"{'✅ поймал' if caught else '🔴 НЕ ПОЙМАЛ'}: {name}")
        survived += 0 if caught else 1
    print(f"\nИТОГ: {len(MUTANTS)-survived}/{len(MUTANTS)} нарочных поломок поймано")
    return 1 if survived else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        sys.exit(mezo_stand.finish(selftest()))
    sys.exit(mezo_stand.finish(main()))
