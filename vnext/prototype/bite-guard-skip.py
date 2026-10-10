r"""
bite-guard-skip.py — приёмка: guard-all.py --skip снимает ЛЮБУЮ проверку по напечатанному имени
и называет имя, которого в прогоне не было (карточка #691).

ПОВОД. Имя сверяли с --skip только sub_guard() и три блока с явным условием. Восемь встроенных
проверок звали check() напрямую: снятая выполнялась, её провал входил в код выхода, вывод молчал.
Незнакомое имя (опечатка) тоже проходило молча. Нашла приёмка Э5 (bite-local-dir.py, Г11б).

СЛУЧАИ
  М1 check() сам сверяет имя с --skip: провал снятой не попадает в итог, строка «⏭️ … пропущен»
  М2 counted() сам сверяет имя: снятое не считается, возвращает False (блок молчит)
  М3 skip_as: проверку с числом в имени снимает постоянное имя
  М4 незнакомое имя — строка «⚠️ --skip «…»» с ближайшими именами
  С0 опора: в общем прогоне копии контура «замороженные md» провалена (каталога координации нет)
  С1 каждая провалившаяся проверка снимается по напечатанному имени — код 0, «все прошли»
  С2·<имя> восемь встроенных проверок: строка пропуска есть, своей строки проверки нет
  С3 общее «память» снимает три замера памяти; их строк нет
  С4 одно имя проверки моста снимает все три; строк о мосте нет
  С5 «сохранённая память: посекционно» снята — строки «память ПО РАЗДЕЛАМ» нет
  С6 опечатка «замороженые md» названа с ближайшим «замороженные md»
  С7 счёт проверок в итоге уменьшился ровно на снятые (16)
  С8 utc (проверка подпроцессом) снимается, как прежде
  С9 «местная · перечень» по --skip не снимается и говорит об этом
  С3б замер памяти снимается и именем, как его строку печатает он сам («кандидатов»), — без строки
      о незнакомом имени
НАРОЧНЫЕ ПОЛОМКИ (копия испытуемого; каждая обязана уронить свой случай)
  П1 check() не сверяет имя с --skip                      → М1
  П2 counted() не сверяет имя                              → М2
  П3 «журнал схемы» без блока и без сверки (прямой check) → С2·журнал схемы
  П4 «память: объём» не снимается общим «память»           → С3
  П5 блок моста не снимается                              → С4
  П6 незнакомые имена не называются                       → С6
  П7 «местная · перечень» снимается по --skip              → С9
  П8 у замера памяти нет печатного имени                  → С3б

⛔ Живая база только читается (снимок через mezo_stand.snapshot_db).

    MEZO_SCRIPTS_ROOT=<клон пакета>/scripts python <клон пакета>/vnext/prototype/bite-guard-skip.py
"""
from __future__ import annotations

import ast
import contextlib
import io
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402
import mezo_stand  # noqa: E402

GUARD_ALL = mezo_target.script("guard-all.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

STAND = mezo_stand.new("bite-691-skip-")
OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail and not cond:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def replaced(text: str, pairs, tag: str) -> str:
    """Текст с нарочной поломкой; каждая строка обязана найтись ровно один раз."""
    for old, new in pairs:
        if text.count(old) != 1:
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: строка поломки {tag} встречается {text.count(old)} раз: {old!r}")
        text = text.replace(old, new)
    return text


# ═══ ЧАСТЬ М — функции испытуемого из его исходника ════════════════════════════════════════════
UNIT_FUNCS = ("_known", "skipped", "check", "counted", "report_unknown_skips")


def unit_ns(source: str) -> dict:
    """check/counted/skipped/… ИЗ ИСХОДНИКА испытуемого — в своё пространство имён."""
    tree = ast.parse(source)
    ns = {"RESULTS": [], "GREENS": [], "FULL": True, "SKIP": set(), "KNOWN": [], "_SKIP_SAID": set()}
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in UNIT_FUNCS:
            exec(ast.get_source_segment(source, node), ns)  # noqa: S102 — исходник испытуемого
            found.add(node.name)
    missing = set(UNIT_FUNCS) - found
    if missing:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в испытуемом нет {', '.join(sorted(missing))}")
    return ns


def run_unit(ns: dict, fn) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def unit_m1(source: str) -> tuple[bool, str]:
    ns = unit_ns(source)
    ns["SKIP"].add("проба")
    out = run_unit(ns, lambda: ns["check"]("проба", False, "беда"))
    return (not ns["RESULTS"] and "⏭️ проба — пропущен по --skip" in out,
            f"RESULTS={ns['RESULTS']} · вывод={out!r}")


def unit_m2(source: str) -> tuple[bool, str]:
    ns = unit_ns(source)
    ns["SKIP"].add("замер")
    got = {}
    out = run_unit(ns, lambda: got.update(r=ns["counted"]("замер"), r2=ns["counted"]("другой")))
    return (got.get("r") is False and got.get("r2") is True and ns["RESULTS"] == [("другой", True, "")]
            and "⏭️ замер — пропущен по --skip" in out, f"вернул {got} · RESULTS={ns['RESULTS']}")


def unit_m3(source: str) -> tuple[bool, str]:
    ns = unit_ns(source)
    ns["SKIP"].add("мост: вопрос")
    out = run_unit(ns, lambda: ns["check"]("мост: вопрос старше 48 ч", False, skip_as=("мост: вопрос",)))
    return (not ns["RESULTS"] and "пропущен по --skip (имя «мост: вопрос»)" in out,
            f"RESULTS={ns['RESULTS']} · вывод={out!r}")


def unit_m4(source: str) -> tuple[bool, str]:
    ns = unit_ns(source)
    ns["SKIP"].update({"журнал схем", "хронология id"})
    out = run_unit(ns, lambda: (ns["check"]("журнал схемы", True), ns["check"]("хронология id", True),
                                ns["report_unknown_skips"]()))
    return ("⚠️ --skip «журнал схем»: проверки с таким именем в этом прогоне не было" in out
            and "ближайшие: журнал схемы" in out and "«хронология id»: проверки" not in out, repr(out))


GUARD_TEXT = GUARD_ALL.read_text(encoding="utf-8")
UNITS = {"М1": unit_m1, "М2": unit_m2, "М3": unit_m3, "М4": unit_m4}
UNIT_NAMES = {"М1": "check() сам сверяет имя с --skip: провал снятой не в итоге, строка пропуска",
              "М2": "counted() сам сверяет имя: снятое не считается и возвращает False",
              "М3": "skip_as: проверку с числом в имени снимает постоянное имя",
              "М4": "незнакомое имя в --skip названо с ближайшими именами"}
for tag, fn in UNITS.items():
    ok, why = fn(GUARD_TEXT)
    case(f"{tag} {UNIT_NAMES[tag]}", ok, why)

P1 = ("    elif skipped(name, *skip_as):\n        return\n",
      "    elif False:  # ПОЛОМКА П1\n        return\n")
P2 = ("    if skipped(name):\n        return False\n",
      "    if False:  # ПОЛОМКА П2\n        return False\n")
for tag, pair, unit in (("П1", P1, "М1"), ("П2", P2, "М2")):
    ok, _ = UNITS[unit](replaced(GUARD_TEXT, [pair], tag))
    case(f"{tag} поломка роняет {unit}", not ok)


# ═══ ЧАСТЬ С — общий прогон на КОПИИ контура ═══════════════════════════════════════════════════
print("---- С: общий прогон на копии контура (около минуты на прогон) ----")
live_mezo = mezo_paths.container_root(__file__) / ".mezosync"
c_root = STAND / "contour"
shutil.copytree(GUARD_ALL.parent, c_root / ".mezosync" / "scripts",
                ignore=shutil.ignore_patterns("__pycache__"))
shutil.copytree(Path(__file__).resolve().parent, c_root / "vnext-tools",
                ignore=shutil.ignore_patterns("__pycache__"))
c_db = mezo_stand.snapshot_db(live_mezo / "mezosync.db", c_root / ".mezosync" / "mezosync.db")
con = sqlite3.connect(str(c_db))
con.execute("DELETE FROM cross_links")      # копия не ходит к настоящим соседям
con.commit()
con.close()
# Каталога координации у копии нет и отказ НЕ объявлен — «замороженные md» провалена нарочно:
# это встроенная проверка с прямым check(), на ней и мерится, снимает ли её --skip.
C_GUARD = c_root / ".mezosync" / "scripts" / "guard-all.py"
C_GUARD_TEXT = C_GUARD.read_bytes()
LOCAL = c_root / ".mezosync" / "local"


def full_run(*extra) -> tuple[int, str, list[str], int]:
    """Общий прогон копии → (код, вывод, имена провалов из итога, число проверок из итога)."""
    r = subprocess.run([sys.executable, str(C_GUARD), "--full", *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                       env=mezo_stand.stand_env(c_root, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    last = [l for l in out.splitlines() if l.startswith(("⛔ КРАСНЫХ", "✅ ВСЕ"))]
    reds, total = [], -1
    if last:
        tail = last[-1]
        if tail.startswith("⛔ КРАСНЫХ") and " — " in tail:
            reds = [n.strip() for n in tail.split(" — ", 1)[1].rsplit(" (", 1)[0].split(", ")]
        if tail.rstrip().endswith("проверок)"):
            total = int(tail.rsplit("(", 1)[1].split()[0])
    return r.returncode, out, reds, total


def own_lines(out: str, name: str) -> list[str]:
    """Строки самой проверки: «✅ имя», «⛔ имя», «   ⚠️ имя: …» — кроме строки пропуска."""
    return [l for l in out.splitlines()
            if (l.startswith((f"✅ {name}", f"⛔ {name}")) or l.lstrip().startswith(f"⚠️ {name}:"))
            and "пропущен по --skip" not in l]


DIRECT = ("хронология id", "отметки прочитанного: регистр", "сохранённая память: регистр",
          "отметки прочитанного: реестр", "форма вызова: источники", "фантомные .db", "журнал схемы",
          "замороженные md")
MEMORY = ("память: кандидаты на устаревание", "память: прежние слова", "память: объём")
MEMORY_MARKS = ("память: кандидатов на устаревание", "📊 ", "память: объём ")
BRIDGE = ("мост соседей", "мост: записки без разбора", "мост соседей: вопросы без ответа")
SKIP_C = ",".join(DIRECT + ("память", "мост: записки без разбора", "сохранённая память: посекционно",
                            "замороженые md", "utc"))
REMOVED = len(DIRECT) + len(MEMORY) + len(BRIDGE) + 1 + 1   # + посекционно + utc

rc0, out0, reds0, total0 = full_run()
case("С0 опора: «замороженные md» провалена в общем прогоне копии (каталога координации нет)",
     "замороженные md" in reds0, f"код {rc0}; провалы: {reds0}")
pre = {n: bool(own_lines(out0, n)) for n in DIRECT}
pre_mem = all(m in out0 for m in MEMORY_MARKS)
pre_bridge = any("мост" in l for l in out0.splitlines())
pre_sect = "память ПО РАЗДЕЛАМ" in out0
if not (all(pre.values()) and pre_mem and pre_bridge and pre_sect):
    print(f"⛔ НЕ ЗАПУСТИЛАСЬ: в опорном прогоне нет строк, отсутствие которых судят случаи — "
          f"встроенные {pre} · память {pre_mem} · мост {pre_bridge} · по разделам {pre_sect}")
    sys.exit(mezo_stand.finish(2))

rc1, out1, reds1, _ = full_run("--skip", ",".join(reds0))
case("С1 каждая провалившаяся проверка снимается по напечатанному имени — код 0, провалов нет",
     rc1 == 0 and not reds1 and all(f"⏭️ {n} — пропущен по --skip" in out1 for n in reds0),
     f"код {rc1}; осталось провалов: {reds1}; снимали: {reds0}")


def judge_c(out: str, total: int) -> dict:
    """Случаи С2–С8 по выводу прогона с SKIP_C → {случай: (годен, пояснение)}."""
    res = {}
    for n in DIRECT:
        res[f"С2·{n}"] = (f"⏭️ {n} — пропущен по --skip" in out and not own_lines(out, n),
                         f"строки проверки: {own_lines(out, n)}")
    mem_said = all(f"⏭️ {m} — пропущен по --skip (имя «память»)" in out for m in MEMORY)
    mem_left = [m for m in MEMORY_MARKS if any(m in l and "пропущен" not in l for l in out.splitlines())]
    res["С3"] = (mem_said and not mem_left, f"строки пропуска все: {mem_said}; осталось: {mem_left}")
    bridge_said = "⏭️ мост соседей — пропущен по --skip (имя «мост: записки без разбора»)" in out
    bridge_left = [l for l in out.splitlines() if "мост" in l and "пропущен по --skip" not in l
                   and not l.startswith("⚠️ --skip")]
    res["С4"] = (bridge_said and not bridge_left, f"строка пропуска: {bridge_said}; осталось: {bridge_left[:3]}")
    res["С5"] = ("⏭️ сохранённая память: посекционно — пропущен по --skip" in out
                 and "память ПО РАЗДЕЛАМ" not in out, "")
    res["С6"] = ("⚠️ --skip «замороженые md»: проверки с таким именем в этом прогоне не было" in out
                 and "ближайшие: замороженные md" in out, "")
    res["С7"] = (total0 - total == REMOVED, f"было {total0}, стало {total}, снято должно {REMOVED}")
    res["С8"] = ("⏭️ utc — пропущен по --skip" in out and not own_lines(out, "utc"), "")
    return res


rc2, out2, _, total2 = full_run("--skip", SKIP_C)
CASE_NAMES = {"С3": "общее «память» снимает три замера памяти; их строк нет",
              "С4": "одно имя проверки моста снимает все три; строк о мосте нет",
              "С5": "«сохранённая память: посекционно» снята — строки «память ПО РАЗДЕЛАМ» нет",
              "С6": "опечатка «замороженые md» названа с ближайшим «замороженные md»",
              "С7": f"счёт проверок уменьшился ровно на снятые ({REMOVED})",
              "С8": "utc (проверка подпроцессом) снимается, как прежде"}
res2 = judge_c(out2, total2)
for key, (ok, why) in res2.items():
    title = CASE_NAMES.get(key) or f"встроенная «{key.split('·', 1)[1]}»: строка пропуска есть, своей строки нет"
    case(f"{key.split('·')[0]} {title}", ok, why)


def judge_c9(out: str, reds: list[str]) -> tuple[bool, str]:
    return ("местная · перечень" in reds
            and "⚠️ --skip «местная · перечень»: эта проверка по --skip не снимается нарочно" in out,
            f"провалы: {reds}")


PRINTED_MEM = "память: кандидатов на устаревание"   # так строку печатает сам замер


def run_c9() -> tuple[bool, str, str]:
    """Прогон С9; заодно в --skip печатное имя замера памяти — его судит С3б."""
    LOCAL.mkdir(parents=True, exist_ok=True)
    (LOCAL / "checks.json").write_text("{ это не json", encoding="utf-8")
    try:
        _, out, reds, _ = full_run("--skip", f"местная · перечень,{PRINTED_MEM}")
    finally:
        (LOCAL / "checks.json").unlink(missing_ok=True)
    return (*judge_c9(out, reds), out)


ok9, why9, out9 = run_c9()
case("С9 «местная · перечень» по --skip не снимается и говорит об этом", ok9, why9)
said_3b = f"⏭️ память: кандидаты на устаревание — пропущен по --skip (имя «{PRINTED_MEM}»)" in out9
left_3b = [l for l in out9.splitlines() if PRINTED_MEM in l and "пропущен по --skip" not in l]
case("С3б замер памяти снимается и печатным именем («кандидатов») — строка пропуска есть, своей строки "
     "и строки о незнакомом имени нет", said_3b and not left_3b, f"строка пропуска: {said_3b}; осталось: {left_3b}")

# ── нарочные поломки на копии контура: одна за раз, копия восстанавливается после каждой
print("---- поломки на копии контура ----")
C_TEXT = C_GUARD_TEXT.decode("utf-8")
BREAKS = (
    ("П3", "С2·журнал схемы", [
        ('    if not skipped("журнал схемы"):', "    if True:  # ПОЛОМКА П3"),
        ('check("журнал схемы", _ok, _why)', 'check("журнал схемы", _ok, _why, skippable=False)')]),
    ("П4", "С3", [('skipped("память: объём", "память"):', 'skipped("память: объём"):  # ПОЛОМКА П4')]),
    ("П5", "С4", [('    if skipped("мост соседей", "мост: записки без разбора", "мост соседей: вопросы без ответа"):',
                   "    if False:  # ПОЛОМКА П5")]),
    ("П6", "С6", [("    report_unknown_skips()\n", "    pass  # ПОЛОМКА П6\n")]),
    ("П7", "С9", [("trouble, skippable=False)", "trouble, skippable=True)  # ПОЛОМКА П7")]),
    ("П8", "С3б", [('"память", "память: кандидатов на устаревание"):', '"память"):  # ПОЛОМКА П8')]),
)
for tag, target, pairs in BREAKS:
    C_GUARD.write_text(replaced(C_TEXT, pairs, tag), encoding="utf-8")
    try:
        if target in ("С9", "С3б"):
            ok_c9, _, outb = run_c9()
            broken_ok = ok_c9 if target == "С9" else (
                f"пропущен по --skip (имя «{PRINTED_MEM}»)" in outb
                and not [l for l in outb.splitlines() if PRINTED_MEM in l and "пропущен по --skip" not in l])
            others = []
        else:
            _, outb, _, totalb = full_run("--skip", SKIP_C)
            resb = judge_c(outb, totalb)
            broken_ok = resb[target][0]
            others = [k for k, (ok, _) in resb.items() if not ok and k != target]
    finally:
        C_GUARD.write_bytes(C_GUARD_TEXT)
    case(f"{tag} поломка роняет {target}" + (f" (заодно: {', '.join(others)})" if others else ""),
         not broken_ok)

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
