# -*- coding: utf-8 -*-
# PLANTS: canon rules tasks printed vitrina
r"""
bite-printed-forms-sources.py — приёмка захода 1 пула (план snuggly-sniffing-planet.md,
п.1.6): guard-printed-forms.py судит ДВА НОВЫХ ИСТОЧНИКА — свод правил (rules.body,
active) и наказы-файлы планировщика — с раскрытием сокращений канона, предпроходом швов
(«команда разорвана переносом») и признаком G (относительная форма БЕЗ имени файла).

СУД — ПО ПОДСАЖЕННОМУ КЛЮЧУ `zzprobe`, не по общему исходу (урок bite-launcher-forms
27.08: краснота от чужих форм). Живая база только читается; подсадки — в копию.

Случаи (Р* — обратные ходы: ослабление РОВНО одной ветки в КОПИИ сторожа роняет ровно
свой случай; якорь не нашёлся → SystemExit «ПРИЁМКА НЕ СОСТОЯЛАСЬ», не молчание):
  ⓪ контроль: нетронутая КОПИЯ живого свода судится ровно как живой — иначе краснота ниже пуста
  ① относительный путь в правиле → 🔴        ② встречный: абсолютный → тихо
  ③ <s> объявлен и жив → тихо                ④ встречный: НЕ объявлен → 🔴
  ⑤ встречный-2: объявлен, ведёт в пустоту → 🔴 (протухший ключ хуже отсутствия)
  ⑥ <s>\имя.py → 🔴 не откроется в bash      ⑦ встречный: <s>/имя.py → тихо (=③)
  ⑧ ШОВ с мёртвой склейкой → 🔴 «СКЛЕЙКА N+N+1»
  ⑧б ШОВ с исполнимой склейкой → 🟡 «разорвана переносом», не 🔴 и не 🟢
  ⑨ встречный: опись инструментов ПОД целой командой → тихо (держит ветка ③-головы)
  ⑨б встречный-2: голова кончается на `\` (перенос) → тихо (держит ветка ④-головы)
  ⑩ встречный-3: голова без хвоста → тихо    ⑪ встречный-4: python -m → тихо
  ⑫ отозванное правило с грязной формой → НЕ долг, счёт «отозвано» растёт
  ⑬ встречный: та же грязь в active → 🔴 (= ①)
  ⑭ надгробие В ТОЙ ЖЕ строке → тихо, счёт «погашено надгробием» растёт
  ⑮ встречный: надгробие СТРОКОЙ НИЖЕ → 🔴 (класс #151 на новом источнике)
  ⑯ file-map-форма без имени файла → 🔴 G    ⑰ встречный: абсолютная с именем → тихо
  ⑱ граница: грязь в столбце basis → НЕ обвиняется (судится только body)
  ⑲ база недоступна → «НЕ ПРОВЕРЕН» (None+err), канона нет → словаря нет (None)
  ⑲б наказ-файл: грязный SKILL.md → 🔴; каталога нет → None, не «чисто»
  ⑳ контроль: живая база прогоном не изменилась (размер+mtime)
  Р1а раскрытие строк выключено → ③ краснеет, ①② как были, ⑧ красный
  Р1б голое раскрытие убрано → ⑧ гаснет, ③ зелёный, ⑥ красный
  Р2 снято ⑤-хвост → ⑩ получает находку     Р3 снято ④-голова(`\`) → ⑨б получает
  Р4 снято ③-голова(.py) → ⑨ получает       Р5 снято ②-довод → ⑪ получает
  Р6 снят отбор по status → ⑫ объявляется долгом
  Р7 подсадки удалены из копии → zz-находки гаснут (доказательство происхождения)
  Р8 снят отрицательный просмотр G → ⑰ задваивается ложной G
"""
import importlib.util
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

GUARD = HERE / "guard-printed-forms.py"
LIVE_DB = mezo_paths.live_db()
LIVE_SCRIPTS = mezo_paths.live_scripts()
CANON = mezo_paths.container_root() / "CLAUDE.md"

OK = FAIL = 0
_seq = [0]


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weakened(src_text, anchor, replacement, why):
    if anchor not in src_text:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь не найден ({why}): {anchor[:70]!r} "
                         f"— ослаблять нечего, случаи выше могли зеленеть не тем кодом")
    return src_text.replace(anchor, replacement)


def wmod(stand, src_text, anchor, replacement, why):
    _seq[0] += 1
    p = stand / f"weak{_seq[0]}.py"
    p.write_text(weakened(src_text, anchor, replacement, why), encoding="utf-8")
    return load(p, f"gpf_weak{_seq[0]}")


def add_rule(db, key, body, status="active", basis=None):
    con = sqlite3.connect(str(db))
    if status == "revoked":
        con.execute("INSERT INTO rules (rule_key, body, status, revoked_at, revoked_by, "
                    "revoked_reason, basis) VALUES (?,?,?,datetime('now'),'bite','проба',?)",
                    (key, body, status, basis))
    else:
        con.execute("INSERT INTO rules (rule_key, body, status, basis) VALUES (?,?,?,?)",
                    (key, body, status, basis))
    con.commit()
    con.close()


def zz(mod, db, known, scripts, defs):
    """Находки ТОЛЬКО по подсаженным правилам + счётчики. 🟢 «норма канона» — не находка:
    «тихо» в случаях значит «нет 🔴/🟡», зелёная пометка соответствия — не шум."""
    hits, inactive, tomb, err = mod.scan_rules(db, known, scripts, defs)
    if err is not None:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: свод в копии не прочитан ({err})")
    return ([(w, k) for w, k, _ in hits
             if w.startswith("zzprobe-") and not k.startswith("🟢")], inactive, tomb)


mod = load(GUARD, "gpf_live")
guard_src = GUARD.read_text(encoding="utf-8")
stand = mezo_stand.new("bite-pfs-")
live_before = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)

# ── песочница: свой инструмент, свой канон, копия живой базы ─────────────────────────
sb_scripts = stand / "scripts"
sb_scripts.mkdir()
(sb_scripts / "zzprobe-tool.py").write_text("# проба\n", encoding="utf-8")
ROOT = sb_scripts.as_posix()
DEFS = {"s": ROOT}
KNOWN = {"zzprobe-tool.py"}
db = stand / "mezosync.db"
shutil.copy(LIVE_DB, db)

# ⓪ нетронутая копия судится ровно как живой свод (тем же словарём и списком имён)
real_known = {p.name for p in LIVE_SCRIPTS.glob("*.py")}
real_defs = mod.canon_defs(CANON)
if real_defs is None:
    raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: канон не найден — базовый словарь пуст")
base_live = mod.scan_rules(LIVE_DB, real_known, LIVE_SCRIPTS, real_defs)
base_copy = mod.scan_rules(db, real_known, LIVE_SCRIPTS, real_defs)
case("⓪ копия свода судится ровно как живой (краснота ниже не пуста)",
     base_live[:3] == base_copy[:3] and base_live[3] is None,
     f"живой: 🔴🟡 {len(base_live[0])}, вне active {base_live[1]}, надгробий {base_live[2]}")

# ── подсадки ─────────────────────────────────────────────────────────────────────────
add_rule(db, "zzprobe-01-rel", "зови: python .mezosync/scripts/zzprobe-tool.py --x")
add_rule(db, "zzprobe-02-abs", f"зови: python {ROOT}/zzprobe-tool.py --x")
add_rule(db, "zzprobe-03-abbrev", "зови: python <s>/zzprobe-tool.py --x")
add_rule(db, "zzprobe-06-backslash", "зови: python <s>\\zzprobe-tool.py --x")
add_rule(db, "zzprobe-08-seam-dead", "python <s>\nzprobe-tool.py --role X")
add_rule(db, "zzprobe-08b-seam-alive", "python <s>/\nzzprobe-tool.py --role X")
add_rule(db, "zzprobe-09-listing", "python <s>/zzprobe-tool.py\nzzprobe-tool.py — опись прибора")
add_rule(db, "zzprobe-09b-continuation", "python <s>\\\nzzprobe-tool.py take")
add_rule(db, "zzprobe-10-head-only", "python <s>\nпросто пояснение словами")
add_rule(db, "zzprobe-11-dash-m", "python -m\nzzprobe-tool.py check")
add_rule(db, "zzprobe-12-revoked", "зови: python .mezosync/scripts/zzprobe-tool.py", "revoked")
add_rule(db, "zzprobe-14-tombstone",
         "⛔ ОТОЗВАНО: python .mezosync/scripts/zzprobe-tool.py — так больше не зовут")
add_rule(db, "zzprobe-15-tomb-below",
         "зови: python .mezosync/scripts/zzprobe-tool.py\n⛔ так больше не зовут")
# ⚠️ в теле НЕЛЬЗЯ писать «как раньше»: «раньше» — примета надгробия (REVOKED_MARK),
# и подсадка гаснет ЧЕСТНО, но не тем случаем — первый прогон так и покраснел.
add_rule(db, "zzprobe-16-no-name", "зови python .mezosync\\scripts\\… отсюда")
add_rule(db, "zzprobe-18-basis", "чистое правило без форм.",
         basis="python .mezosync/scripts/zzprobe-tool.py")

hits, inactive, tomb = zz(mod, db, KNOWN, sb_scripts, DEFS)
by_rule = {}
for w, k in hits:
    by_rule.setdefault(w.split(":")[0], []).append(k)

case("① относительный путь в правиле → 🔴",
     any(k.startswith("🔴") for k in by_rule.get("zzprobe-01-rel", [])))
case("② встречный: абсолютный → тихо", "zzprobe-02-abs" not in by_rule)
case("③⑦ <s> объявлен и жив → тихо", "zzprobe-03-abbrev" not in by_rule)

# ④⑤ судятся напрямую судом строк: словарь пуст / словарь ведёт в пустоту
h4 = [k for _, k, _ in ((n, k, f) for n, k, f in
      ((i, kk, ff) for i, kk, ff in mod.judged_lines(
          ["зови: python <s>/zzprobe-tool.py --x"], KNOWN, sb_scripts, None)))]
case("④ встречный: <s> НЕ объявлен → 🔴", any(k.startswith("🔴") for k in h4),
     " · ".join(h4) or "находок нет — ЛОЖНОЕ ЗЕЛЁНОЕ")
h5 = [k for _, k, _ in mod.judged_lines(["зови: python <s>/zzprobe-tool.py --x"],
                                        KNOWN, sb_scripts, {"s": ROOT + "-нет-такого"})]
case("⑤ встречный-2: словарь ведёт в пустоту → 🔴 (протухший ключ)",
     any(k.startswith("🔴") for k in h5), " · ".join(h5) or "тихо — ЛОЖНОЕ")

case("⑥ <s>\\имя.py → 🔴 не откроется в bash",
     any("BASH" in k for k in by_rule.get("zzprobe-06-backslash", [])))
case("⑧ шов с мёртвой склейкой → 🔴 с происхождением «СКЛЕЙКА 1+2»",
     any(k.startswith("🔴") and "СКЛЕЙКА 1+2" in k
         for k in by_rule.get("zzprobe-08-seam-dead", [])),
     " · ".join(by_rule.get("zzprobe-08-seam-dead", [])) or "находок нет")
k8b = by_rule.get("zzprobe-08b-seam-alive", [])
case("⑧б шов с исполнимой склейкой → ровно 🟡 «разорвана переносом»",
     any("РАЗОРВАНА ПЕРЕНОСОМ" in k for k in k8b)
     and not any(k.startswith("🔴") for k in k8b),
     " · ".join(k8b) or "находок нет — молчание про шов")
case("⑨ встречный: опись под целой командой → тихо", "zzprobe-09-listing" not in by_rule)
case("⑨б встречный-2: перенос через `\\` в голове → тихо",
     "zzprobe-09b-continuation" not in by_rule)
case("⑩ встречный-3: голова без хвоста → тихо", "zzprobe-10-head-only" not in by_rule)
case("⑪ встречный-4: python -m → тихо", "zzprobe-11-dash-m" not in by_rule)
case("⑫ отозванное с грязью → НЕ долг, счёт «отозвано» вырос",
     "zzprobe-12-revoked" not in by_rule and inactive == base_copy[1] + 1,
     f"вне active: {inactive} (было {base_copy[1]})")
case("⑬ встречный: та же грязь в active → 🔴 (случай ①)",
     any(k.startswith("🔴") for k in by_rule.get("zzprobe-01-rel", [])))
case("⑭ надгробие в ТОЙ ЖЕ строке → тихо, счёт «погашено надгробием» вырос",
     "zzprobe-14-tombstone" not in by_rule and tomb >= base_copy[2] + 1,
     f"погашено: {tomb} (было {base_copy[2]})")
case("⑮ встречный: надгробие СТРОКОЙ НИЖЕ → 🔴 (класс #151)",
     any(k.startswith("🔴") for k in by_rule.get("zzprobe-15-tomb-below", [])))
case("⑯ форма без имени файла → 🔴 G",
     any(" G " in k for k in by_rule.get("zzprobe-16-no-name", [])))
line17 = f"зови: python {LIVE_SCRIPTS.as_posix()}/read-messages.py --role X"
h17 = [k for k, _ in mod.classify(line17, real_known, (), LIVE_SCRIPTS)
       if not k.startswith("🟢")]
case("⑰ встречный: абсолютная С именем (живой литерал .mezosync/scripts) → тихо",
     not h17, " · ".join(h17) or "тихо")
case("⑱ граница: грязь в столбце basis НЕ обвиняется", "zzprobe-18-basis" not in by_rule)

bad = mod.scan_rules(stand / "нет-такой.db", KNOWN, sb_scripts, DEFS)
case("⑲ база недоступна → None+ошибка («НЕ ПРОВЕРЕН» ≠ «чисто»)",
     bad[0] is None and bad[3], str(bad[3])[:80])
case("⑲ канона нет → словаря нет (None), суд без словаря не начинается",
     mod.canon_defs(stand / "нет-канона.md") is None)

tasks = stand / "tasks"
(tasks / "zzprobe-task").mkdir(parents=True)
(tasks / "zzprobe-task" / "SKILL.md").write_text(
    "шаг: python .mezosync/scripts/zzprobe-tool.py --db X\n", encoding="utf-8")
th = mod.scan_tasks(tasks, KNOWN, sb_scripts, DEFS)
case("⑲б наказ-файл: грязный SKILL.md → 🔴 (и относительный, и --db)",
     th and sum(1 for _, k, _ in th if k.startswith("🔴")) >= 2,
     " · ".join(k for _, k, _ in (th or [])))
case("⑲б каталога наказов нет → None, не пустое «чисто»",
     mod.scan_tasks(stand / "нет-каталога", KNOWN, sb_scripts, DEFS) is None)

# ── обратные ходы ────────────────────────────────────────────────────────────────────
ANCHOR_EXPAND = "for kind, frag in classify(expand_abbrev(line, defs), known, (), scripts):"
m_r1a = wmod(stand, guard_src, ANCHOR_EXPAND,
             "for kind, frag in classify(line, known, (), scripts):", "Р1а раскрытие строк")
h, _, _ = zz(m_r1a, db, KNOWN, sb_scripts, DEFS)
br = {}
for w, k in h:
    br.setdefault(w.split(":")[0], []).append(k)
case("Р1а раскрытие выключено → ③ краснеет, ①② как были, ⑧ красный",
     any(k.startswith("🔴") for k in br.get("zzprobe-03-abbrev", []))
     and any(k.startswith("🔴") for k in br.get("zzprobe-01-rel", []))
     and "zzprobe-02-abs" not in br
     and any(k.startswith("🔴") for k in br.get("zzprobe-08-seam-dead", [])))

m_r1b = wmod(stand, guard_src, '.replace(f"<{name}>", root + "/"))', ")",
             "Р1б голое раскрытие")
h, _, _ = zz(m_r1b, db, KNOWN, sb_scripts, DEFS)
br = {}
for w, k in h:
    br.setdefault(w.split(":")[0], []).append(k)
case("Р1б голое раскрытие убрано → ⑧ гаснет, ③ зелёный, ⑥ красный",
     not any(k.startswith("🔴") for k in br.get("zzprobe-08-seam-dead", []))
     and "zzprobe-03-abbrev" not in br
     and any(k.startswith("🔴") for k in br.get("zzprobe-06-backslash", [])))

for title, anchor, repl, victim in [
        ("Р2 снято условие ⑤ (хвост) → ⑩ получает находку",
         'if not re.match(r"^[\\w\\-]+\\.py(\\s|$)", tail):', "if False:",
         "zzprobe-10-head-only"),
        ("Р3 снято условие ④ (`\\` в голове) → ⑨б получает находку",
         'if head.rstrip().endswith("\\\\"):', "if False:", "zzprobe-09b-continuation"),
        ("Р4 снято условие ③ (.py в голове) → ⑨ получает находку",
         'if ".py" in head:', "if False:", "zzprobe-09-listing"),
        ("Р5 снято условие ② (довод) → ⑪ получает находку",
         'if arg.startswith("-") or not ("/" in arg or "\\\\" in arg or arg.startswith("<")):',
         "if False:", "zzprobe-11-dash-m")]:
    m_w = wmod(stand, guard_src, anchor, repl, title)
    h, _, _ = zz(m_w, db, KNOWN, sb_scripts, DEFS)
    victims = [k for w, k in h if w.startswith(victim)]
    clean09 = [k for w, k in h if w.startswith("zzprobe-09-listing")] if victim != "zzprobe-09-listing" else None
    case(title, bool(victims)
         and any(k.startswith("🔴") for w, k in h if w.startswith("zzprobe-08-seam-dead")),
         " · ".join(victims))

m_r6 = wmod(stand, guard_src, 'if status != "active":', "if False:", "Р6 отбор по status")
h, _, _ = zz(m_r6, db, KNOWN, sb_scripts, DEFS)
case("Р6 снят отбор по status → ⑫ объявляется долгом",
     any(k.startswith("🔴") for w, k in h if w.startswith("zzprobe-12-revoked")))

db7 = stand / "r7.db"
shutil.copy(db, db7)
con = sqlite3.connect(str(db7))
con.execute("DELETE FROM rules WHERE rule_key LIKE 'zzprobe-%'")
con.commit()
con.close()
h7, _, _ = zz(mod, db7, KNOWN, sb_scripts, DEFS)
case("Р7 подсадки удалены → zz-находки гаснут (находки БЫЛИ из свода)", not h7)

m_r8 = wmod(stand, guard_src, "(?![\\w\\-]+\\.py)", "", "Р8 отрицательный просмотр G")
h17w = [k for k, _ in m_r8.classify(line17, real_known, (), LIVE_SCRIPTS) if " G " in k]
case("Р8 снят отрицательный просмотр → ⑰ получает ложную G (без него 149 по контуру)",
     bool(h17w))

# ── ㉑㉒ подсадка в КАЖДЫЙ объявленный источник (заход 4 ⑦): гард объявляет
# SURFACES: canon rules tasks printed vitrina — canon/rules/tasks подсажены выше,
# printed и vitrina до 28.08 не подсаживались ВОВСЕ: их зелёное было не доказано.
import re as _re                                       # noqa: E402

dirty_py = sb_scripts / "zzprobe-print.py"
dirty_py.write_text('print("зови: python .mezosync/scripts/zzprobe-tool.py --x")\n',
                    encoding="utf-8")
h21 = [k for _ln, _rk, k, _f in mod.scan_py(dirty_py, KNOWN, sb_scripts)
       if not k.startswith("🟢")]
case("㉑ printed: грязная форма в ПЕЧАТАЕМОЙ строке скрипта → находка",
     bool(h21), " · ".join(h21[:2]))
clean_py = sb_scripts / "zzprobe-print-clean.py"
clean_py.write_text(f'print("зови: python {ROOT}/zzprobe-tool.py --x")\n',
                    encoding="utf-8")
h21b = [k for _ln, _rk, k, _f in mod.scan_py(clean_py, KNOWN, sb_scripts)
        if not k.startswith("🟢")]
case("㉑б встречный: абсолютная печатаемая форма → тихо", not h21b,
     " · ".join(h21b[:2]))

vit = stand / "zzprobe-vitrina.md"
vit.write_text("подвал: python .mezosync/scripts/zzprobe-tool.py --x\n", encoding="utf-8")
tpl21 = [_re.compile(_re.escape("python .mezosync/scripts/zzprobe-tool.py"))]
h22 = mod.scan_md(vit, KNOWN, templates=tpl21, scripts=sb_scripts)
case("㉒ vitrina: форма, напечатанная ГЕНЕРАТОРОМ готовой выборки → долг", bool(h22))
h22b = mod.scan_md(vit, KNOWN, templates=[], scripts=sb_scripts)
case("㉒б встречный: та же строка как ЦИТАТА тела ноты → не долг (история)",
     not h22b, "цитату не чинят — её напечатал не генератор, а прошлое")

# ⑳ живая база не тронута
live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑳ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
