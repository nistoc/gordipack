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
  ㉓–㉗ (карточка #678, этап Э4, шаг Ш1, п. а) печатаемая подсказка несёт ВЫЧИСЛЕННЫЙ путь, а не
      заглушку «<КОНТУР>» (знак «<» в командной строке — перенаправление ввода, команду нельзя копировать):
  ㉓ set-rule.py — шаг схемы · ㉔ guard-all.py — разбор записки моста · ㉕ check-phoenix-invariant.py —
  возврат памяти · ㉖ memory-archive.py — ссылка на правило · ㉗ bite-backlog-tail.py — исполняемая
  строка sys.path (на каталог самого скрипта). Каждое место судится тремя признаками: заглушки нет в
  коде файла · копия гарда печатаемых форм не находит 🔴 · печатаемый путь абсолютный, в прямых косых,
  ведёт в существующий файл (инструмент запускается на стенде, путь сверяется с каталогом стенда).

ИСПЫТУЕМАЯ КОПИЯ. Каталог скриптов берётся через mezo_target (MEZO_SCRIPTS_ROOT, MEZO_FORBID_LIVE),
а не из живого контура: имена инструментов для суда гарда и файлы случаев ㉓–㉗ — из копии. Файлы
vnext (check-phoenix-invariant.py, memory-archive.py) — из каталога самой приёмки. Читаются из ЖИВОГО
контура два источника, своей копии у которых нет: свод правил (копия базы, снятая только на чтение)
и канон CLAUDE.md контейнера.

Нарочные поломки ㉓–㉗: `--break <имя>` (hint-set-rule · hint-guard-all · hint-phoenix-invariant ·
hint-memory-archive · path-backlog-tail · all — все подряд). В КОПИИ одного файла на стенде в одно
место возвращается заглушка; обязан провалиться РОВНО свой случай (список записан заранее в
BREAK_FAILS), остальные целы. Якорь не найден или найден дважды → «поломка не легла», прогон отказан.
"""
import argparse
import ast
import importlib.util
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402 — какую копию испытываем: MEZO_SCRIPTS_ROOT, MEZO_FORBID_LIVE

GUARD = HERE / "guard-printed-forms.py"
LIVE_DB = mezo_paths.live_db()
# Каталог скриптов — ИСПЫТУЕМАЯ КОПИЯ (mezo_target), а не живой каталог: имена инструментов для суда
# гарда, образец абсолютной формы в случае ⑰ и места, откуда случаи ㉓–㉗ берут файлы. Без переменной
# MEZO_SCRIPTS_ROOT это по-прежнему живой каталог (прежнее поведение). ⛔ Живыми остаются два ЧТЕНИЯ:
# свод правил (копия живой базы, снятая только на чтение) и канон CLAUDE.md контейнера — своего свода
# и своего канона у копии нет.
SCRIPTS_UNDER_TEST = mezo_target.scripts_root()
mezo_target.script("read-messages.py")      # живой каталог при MEZO_FORBID_LIVE=1 или пустая копия — отказ, не заём
CANON = mezo_paths.container_root() / "CLAUDE.md"

# ── нарочные поломки случаев ㉓–㉗ (карточка #678, Э4 Ш1, п. а) ───────────────────────────────
# Поломка: в КОПИИ файла (на стенде) в одно место возвращается заглушка пути вместо вычисленного
# выражения. Якорь обязан найтись в файле РОВНО один раз — иначе поломка «не легла», и прогон
# не засчитывается. Список провалов каждой поломки записан ДО прогона (BREAK_FAILS): ждём провала
# РОВНО своего случая, остальные обязаны остаться целыми.
PLACEHOLDER = "<КОНТУР>"
BREAKS = {
    # имя: (метка случая, где лежит файл, имя файла, якорь, замена, что ломаем)
    "hint-set-rule": (
        "㉓", "scripts", "set-rule.py",
        'f"   python {mig}")',
        '"   python <КОНТУР>/.mezosync/scripts/migrations/20260904-rule-skill-delivery.py")',
        "подсказка про шаг схемы снова несёт заглушку"),
    "hint-guard-all": (
        "㉔", "scripts", "guard-all.py",
        'f"\\n      python {SCRIPTS.as_posix()}/write-message.py"',
        '"\\n      python <КОНТУР>/.mezosync/scripts/write-message.py"',
        "подсказка про разбор записки моста снова несёт заглушку"),
    "hint-phoenix-invariant": (
        "㉕", "prototype", "check-phoenix-invariant.py",
        'f" прежде чем возвращать (python {mezo_paths.live_scripts(__file__).as_posix()}/save-phoenix.py"',
        'f" прежде чем возвращать (python <КОНТУР>/.mezosync/scripts/save-phoenix.py"',
        "подсказка про возврат памяти снова несёт заглушку"),
    "hint-memory-archive": (
        "㉖", "prototype", "memory-archive.py",
        'print(f"   python {mezo_paths.live_scripts(__file__).as_posix()}/set-rule.py "',
        'print("   python <КОНТУР>/.mezosync/scripts/set-rule.py "',
        "строка-ссылка на правило снова несёт заглушку"),
    "path-backlog-tail": (
        "㉗", "scripts", "bite-backlog-tail.py",
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))",
        'sys.path.insert(0, r"<КОНТУР>\\.mezosync\\scripts")',
        "строка sys.path снова указывает на заглушку"),
}
BREAK_FAILS = {name: [spec[0]] for name, spec in BREAKS.items()}


def run_all_breaks() -> int:
    """Все нарочные поломки подряд: каждая — отдельным прогоном этой же приёмки с --break."""
    confirmed = 0
    # среда закреплена явно: тот же контейнер, что у вызывающего (MEZO_SCRIPTS_ROOT и MEZO_FORBID_LIVE
    # наследуются как есть — иначе дочерний прогон испытывал бы не ту копию)
    env = mezo_stand.stand_env(mezo_paths.container_root(), PYTHONIOENCODING="utf-8")
    for name in BREAKS:
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--break", name],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=900, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        ok = f"ожидание поломки «{name}» ПОДТВЕРДИЛОСЬ" in out
        confirmed += ok
        line = next((ln for ln in out.splitlines() if "ожидание поломки" in ln), "строки об ожидании нет")
        print(f"{'✅' if ok else '🔴'} {name}: {line.strip()}")
    print(f"поломок {len(BREAKS)}, ожидание подтвердилось {confirmed}")
    return 0 if confirmed == len(BREAKS) else 1


_ap = argparse.ArgumentParser(description="Приёмка гарда печатаемых форм: два источника суда, "
                                          "вычисленный путь в печатаемых подсказках")
_ap.add_argument("--break", dest="break_name", default=None, choices=[*BREAKS, "all"],
                 help="нарочная поломка случаев ㉓–㉗ на КОПИИ файла (all — все подряд)")
ARGS = _ap.parse_args()
if ARGS.break_name == "all":
    raise SystemExit(mezo_stand.finish(run_all_breaks()))

OK = FAIL = 0
SKIPPED: list[tuple[str, str]] = []
FAILED_NAMES: list[str] = []      # имена проваленных случаев — по ним сверяется ожидание нарочной поломки
_seq = [0]


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    if not cond:
        FAILED_NAMES.append(name)
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def case_skip(name, reason):
    SKIPPED.append((name, reason))
    print("⚪", name)
    print(f"   пропущен: не проверено: {reason}")


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
mezo_stand.snapshot_db(LIVE_DB, db)

# ⓪ нетронутая копия судится ровно как живой свод (тем же словарём и списком имён)
real_known = {p.name for p in SCRIPTS_UNDER_TEST.glob("*.py")}
real_defs = mod.canon_defs(CANON)
# 🩹 ДОГОН (карточка #667, приёмка пакета на пустом новом контуре): прежде отсутствие
# канона (CLAUDE.md) обрывало ВЕСЬ прогон — SystemExit до единого случая. Свежая
# выгрузка пакета не несёт CLAUDE.md в контейнере вовсе (не долг сборки — она просто
# не копирует корневые файлы репозитория), и канон здесь нужен ТОЛЬКО случаю ⓪
# (сверка копии свода с живым ТЕМИ ЖЕ сокращениями): все прочие случаи судят своим
# подсаженным словарём DEFS={"s": ROOT}, от CLAUDE.md не зависящим. ⇒ без канона
# честно пропускаем ОДИН случай ⓪, а не все; base_copy (нужна случаям ⑫/⑭ для счёта
# «было») считаем своим словарём — тем же, каким дальше меряют сами случаи.
if real_defs is None:
    case_skip("⓪ копия свода судится ровно как живой (краснота ниже не пуста)",
              f"канона нет на этом контуре ({CANON}) — свежая выгрузка пакета не несёт "
              "CLAUDE.md, базового словаря сокращений нет, и сверка копии с живым "
              "ТЕМ ЖЕ словарём не на чём ставить")
    base_copy = mod.scan_rules(db, KNOWN, sb_scripts, DEFS)
else:
    base_live = mod.scan_rules(LIVE_DB, real_known, SCRIPTS_UNDER_TEST, real_defs)
    base_copy = mod.scan_rules(db, real_known, SCRIPTS_UNDER_TEST, real_defs)
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
# Карточка #361: значок внимания — примета ВНИМАНИЯ, не примета ОТМЕНЫ.
add_rule(db, "zzprobe-22-sign-prescribe",
         "⚠️ Зови так: python .mezosync/scripts/zzprobe-tool.py --x")
add_rule(db, "zzprobe-23-sign-bare",
         "⛔ python .mezosync/scripts/zzprobe-tool.py")
add_rule(db, "zzprobe-24-word-tomb",
         "вместо неё: python .mezosync/scripts/zzprobe-tool.py")

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
# ⚠️ путь для ⑰ и Р8 обязан иметь ВИД `<контейнер>/.mezosync/scripts/…`: именно после такого
# хвоста стоит отрицательный просмотр, который снимает Р8. Путь каталога КОПИИ (…/pack/scripts)
# такого хвоста не несёт — на нём Р8 терял бы зубы (первый прогон после перевода на копию так и
# показал: случай Р8 провалился). Поэтому берётся подставной контейнер на СТЕНДЕ — живой каталог не читается.
abs_scripts = stand / "ct-abs" / ".mezosync" / "scripts"
abs_scripts.mkdir(parents=True)
(abs_scripts / "read-messages.py").write_text("# пустышка стенда\n", encoding="utf-8")
line17 = f"зови: python {abs_scripts.as_posix()}/read-messages.py --role X"
h17 = [k for k, _ in mod.classify(line17, real_known, (), abs_scripts)
       if not k.startswith("🟢")]
case("⑰ встречный: абсолютная С именем (вид .mezosync/scripts, каталог СТЕНДА) → тихо",
     not h17, " · ".join(h17) or "тихо")
case("⑱ граница: грязь в столбце basis НЕ обвиняется", "zzprobe-18-basis" not in by_rule)
# ── карточка #361: значок внимания не гасит ПРЕДПИСАНИЕ ──────────────────────────────
case("⑳ «⚠️ Зови так: <относительная форма>» — предписание СУДИТСЯ, значок не гасит",
     any(k.startswith("🔴") for k in by_rule.get("zzprobe-22-sign-prescribe", [])),
     " · ".join(by_rule.get("zzprobe-22-sign-prescribe", []))
     or "тихо — ЛОЖНОЕ МОЛЧАНИЕ (дефект карточки #361 жив)")
case("⑳б встречный: ГОЛЫЙ значок без предписания — честное надгробие, тихо",
     "zzprobe-23-sign-bare" not in by_rule,
     "значки из словаря не выкинуты — запрет тела карточки соблюдён")
case("⑳в встречный-2: надгробие СЛОВОМ («вместо») — гасится, как прежде",
     "zzprobe-24-word-tomb" not in by_rule)

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
h17w = [k for k, _ in m_r8.classify(line17, real_known, (), abs_scripts) if " G " in k]
case("Р8 снят отрицательный просмотр → ⑰ получает ложную G (без него 149 по контуру)",
     bool(h17w))

# Р9/Р10 — карточка #361, обе стороны ПОРОЗНЬ: снятие одной роняет ровно свой случай.
m_r9 = wmod(stand, guard_src, "if SIGN_MARK.search(t) and not PRESCRIBE.search(t):",
            "if SIGN_MARK.search(t):", "Р9 различитель предписания")
h, _, _ = zz(m_r9, db, KNOWN, sb_scripts, DEFS)
br = {}
for w, k in h:
    br.setdefault(w.split(":")[0], []).append(k)
case("Р9 различитель предписания снят → ⑳ гаснет (значок снова гасит всё), ①/⑳в как были",
     "zzprobe-22-sign-prescribe" not in br
     and any(k.startswith("🔴") for k in br.get("zzprobe-01-rel", []))
     and "zzprobe-24-word-tomb" not in br)

m_r10 = wmod(stand, guard_src,
             "m = WORD_MARK.search(t) or (mention.is_mention(t, kinds=_MENTION_KINDS) or None)",
             "m = None", "Р10 словесная ветвь отзыва")
h, _, _ = zz(m_r10, db, KNOWN, sb_scripts, DEFS)
br = {}
for w, k in h:
    br.setdefault(w.split(":")[0], []).append(k)
case("Р10 словесная ветвь снята → ⑳в получает находку, ⑳ красный, ⑳б тихий как был",
     any(k.startswith("🔴") for k in br.get("zzprobe-24-word-tomb", []))
     and any(k.startswith("🔴") for k in br.get("zzprobe-22-sign-prescribe", []))
     and "zzprobe-23-sign-bare" not in br)

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

# ═══ ㉓–㉗ ПЕЧАТАЕМАЯ ПОДСКАЗКА НЕСЁТ ВЫЧИСЛЕННЫЙ ПУТЬ, А НЕ ЗАГЛУШКУ «<КОНТУР>» ═══════════════
# Карточка #678 (этап Э4, шаг Ш1, п. а). Файлы пакета получались из контура-донора заменой его пути
# на слово-заглушку; у потребителя печатаемая команда несла это слово, а знак «<» в командной
# строке — перенаправление ввода: команду из вывода нельзя было просто скопировать. Теперь путь в
# пяти местах ВЫЧИСЛЯЕТСЯ. Судятся файлы ИСПЫТУЕМОЙ КОПИИ (mezo_target; файлы vnext-tools — из каталога
# самой приёмки), живой каталог не читается, если задан MEZO_SCRIPTS_ROOT.
# Первые четыре — печатаемые команды. Каждая судится ТРЕМЯ признаками разом:
#   · в КОДЕ файла (вне строк документации) нет заглушки;
#   · гард печатаемых форм (КОПИЯ из клона) не находит 🔴 в этой строке;
#   · путь в команде — то, что код ПЕЧАТАЕТ: запуск инструмента на стенде (㉓ ㉕ ㉖) либо ВЫЧИСЛЕНИЕ
#     напечатанного выражения в окружении файла (㉔: guard-all.py запускать целиком слишком тяжело).
#     Путь обязан быть абсолютным, в прямых косых, вести в существующий файл и совпадать с ожидаемым.
# Пятое (㉗) — исполняемая строка sys.path: без заглушки и ведёт в каталог самого скрипта.
# ⚖️ Ожидаемый путь у ㉕ и ㉖ — каталог инструментов СТЕНДА (среда MEZO_CONTAINER закреплена за ним):
# так литерал живого каталога тоже не пройдёт — путь обязан ВЫЧИСЛЯТЬСЯ, а не быть написан.


def source_of(name):
    """Файл места правки в испытуемой копии. Нет файла — отказ, не тихий заём из живого каталога."""
    mark, kind, fname = BREAKS[name][:3]
    if kind == "scripts":
        return mezo_target.script(fname)
    p = HERE / fname
    if not p.is_file():
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: нет файла {p} — {mark} судить нечем "
                         f"(это НЕ «в порядке»)")
    return p


def file_under_test(name):
    """Файл для случая. При --break именно этого места — его КОПИЯ на стенде с возвращённой заглушкой."""
    src = source_of(name)
    if ARGS.break_name != name:
        return src
    _mark, _kind, _fname, anchor, repl, _what = BREAKS[name]
    text = src.read_text(encoding="utf-8").replace("\r\n", "\n")
    found = text.count(anchor)
    if found != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: поломка «{name}» не легла — якорь найден {found} раз(а), "
                         f"ждали один: {anchor[:70]!r}. Строка в файле изменилась — поломку надо пересмотреть")
    copied = mezo_stand.copy_tool(src, stand / "brk" / name)
    copied.write_text(text.replace(anchor, repl), encoding="utf-8", newline="\n")
    return copied


def _node_text(node):
    """Текст литерала; в f-строке выражения заменены на `{…}` с исходным текстом."""
    if isinstance(node, ast.Constant):
        return node.value
    return "".join(v.value if isinstance(v, ast.Constant) else "{" + ast.unparse(v.value) + "}"
                   for v in node.values)


def _string_nodes(tree):
    """Строки и f-строки файла целыми узлами (части f-строки отдельно не отдаются)."""
    inner = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
    return [n for n in ast.walk(tree) if id(n) not in inner
            and (isinstance(n, ast.JoinedStr) or (isinstance(n, ast.Constant) and isinstance(n.value, str)))]


def placeholder_in_code(path):
    """Строки КОДА файла (вне строк документации) с заглушкой → [(номер строки, строка)].
    Комментарии не в счёте — их роль не читает; строки документации — примеры вызова в справке."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    source_lines = path.read_text(encoding="utf-8").split("\n")
    found = []
    for node in _string_nodes(tree):
        text = _node_text(node)
        if id(node) not in docs and PLACEHOLDER in text:
            # точная строка файла: литерал бывает склейкой из нескольких строк
            where = [n for n in range(node.lineno, node.end_lineno + 1) if PLACEHOLDER in source_lines[n - 1]]
            at = where[0] if where else node.lineno
            found.append((at, source_lines[at - 1].strip()[:90]))
    return found


def printed_literal(path, pattern):
    """(дерево, узел) — литерал файла, чей текст подходит под pattern; такого нет — (дерево, None)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in _string_nodes(tree):
        if re.search(pattern, _node_text(node)):
            return tree, node
    return tree, None


def evaluate_in_file(path, tree, node):
    """Значение выражения из файла, вычисленное в его окружении: модульные присваивания, зависящие от
    __file__ (SCRIPTS = Path(__file__).resolve().parent), исполняются, прочее — нет. Не вычислилось → None."""
    ns = {"__file__": str(path), "Path": Path, "pathlib": pathlib, "os": os, "sys": sys}
    for top in tree.body:
        if isinstance(top, ast.Assign) and "__file__" in ast.unparse(top.value):
            try:
                exec(compile(ast.fix_missing_locations(ast.Module(body=[top], type_ignores=[])), str(path), "exec"), ns)
            except Exception:       # noqa: BLE001 — присваивание с чужими именами (mezo_paths…) пропускаем
                continue
    try:
        return eval(compile(ast.fix_missing_locations(ast.Expression(body=node)), str(path), "eval"), ns)
    except Exception:               # noqa: BLE001 — не вычислилось: исход «не проверено», а не «в порядке»
        return None


def guard_reds(path, word):
    """🔴 КОПИИ гарда печатаемых форм в строках файла, где названо word."""
    hits = mod.scan_py(path, real_known, SCRIPTS_UNDER_TEST)
    return [f"{kind.split(' — ')[0]} (:{ln})" for ln, _rank, kind, frag in hits
            if kind.startswith("🔴") and word in frag]


def command_verdict(text, tool_file, expected):
    """Печатаемая команда `python <путь>/<tool_file>` в text: путь без заглушки, абсолютный, в прямых
    косых, существует и совпадает с expected. → (годится, слова)."""
    m = re.search(r"python3?\s+(\S*" + re.escape(tool_file) + ")", text)
    if not m:
        return False, "в напечатанном нет команды с " + tool_file + ": " + \
            " ⏎ ".join(text.strip().splitlines())[:150]
    printed = m.group(1)
    if "<" in printed or ">" in printed:
        return False, f"путь в команде — заглушка, а не путь: {printed}"
    if "\\" in printed:
        return False, f"в пути обратные косые (Bash съест их): {printed}"
    if not re.match(r"^(?:[A-Za-z]:/|/)", printed):
        return False, f"путь не абсолютный: {printed}"
    if Path(printed).resolve() != Path(expected).resolve():
        return False, f"путь ведёт не туда: {printed} (ждали {Path(expected).as_posix()})"
    if not Path(printed).is_file():
        return False, f"по пути нет файла: {printed}"
    return True, f"печатает {printed}"


def stand_container(tag, tools=()):
    """Подставной контейнер: .mezosync/mezosync.db (пустая база) и пустышки инструментов, куда
    подсказка обязана вести. → (корень, путь базы)."""
    ct = stand / f"ct-{tag}"
    (ct / ".mezosync" / "scripts").mkdir(parents=True)
    for t in tools:
        (ct / ".mezosync" / "scripts" / t).write_text("# пустышка стенда\n", encoding="utf-8")
    return ct, ct / ".mezosync" / "mezosync.db"


def run_tool(file, args, container):
    """Запуск инструмента со средой СТЕНДА (MEZO_CONTAINER — стенд): → весь вывод (stdout + stderr)."""
    r = subprocess.run([sys.executable, str(file), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, cwd=str(stand),
                       env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
    return (r.stdout or "") + (r.stderr or "")


def hint_case(title, verdict, path, code_bad, reds):
    """Одна строка итога случая: вердикт печатаемой команды + признаки кода и гарда."""
    ok, words = verdict
    extra = []
    if code_bad:
        extra.append("заглушка в коде файла: " + " · ".join(f":{ln} {text}" for ln, text in code_bad))
    if reds:
        extra.append("гард находит 🔴: " + " · ".join(reds))
    case(title, ok and not code_bad and not reds,
         "; ".join([words, *extra]) if (extra or not ok) else
         f"{words}; заглушки в коде нет; гард 🔴 не находит")


# ㉓ set-rule.py — подсказка про шаг схемы. База без поля решения о доставке: инструмент отказывает и печатает команду.
f23 = file_under_test("hint-set-rule")
ct23, db23 = stand_container("set-rule")
_c = sqlite3.connect(str(db23))
_c.execute("CREATE TABLE rules (rule_key TEXT PRIMARY KEY, body TEXT, version INTEGER, locked_by TEXT)")
_c.commit()
_c.close()
out23 = run_tool(f23, ["--db", str(db23), "--key", "zzprobe", "--skill-delivery", "yes"], ct23)
hint_case("㉓ set-rule.py: подсказка про шаг схемы несёт вычисленный путь, а не заглушку",
          command_verdict(out23, "20260904-rule-skill-delivery.py",
                          f23.resolve().parent / "migrations" / "20260904-rule-skill-delivery.py"),
          f23, placeholder_in_code(f23), guard_reds(f23, "20260904-rule-skill-delivery"))

# ㉔ guard-all.py — подсказка про разбор записки моста. Целиком guard-all.py на стенде не запустить (десятки
# проверок), поэтому вычисляется напечатанное выражение — в окружении файла (SCRIPTS = Path(__file__)…).
f24 = file_under_test("hint-guard-all")
tree24, node24 = printed_literal(f24, r"python\s+\S*write-message\.py --role <ТЫ> --file <нота\.md> --reviewed")
if node24 is None:
    case("㉔ guard-all.py: подсказка про разбор записки моста несёт вычисленный путь, а не заглушку", False,
         "в файле нет печатаемой строки «python …/write-message.py --role <ТЫ> --file … --reviewed» — "
         "подсказку убрали или переписали: случай надо пересмотреть")
else:
    text24 = evaluate_in_file(f24, tree24, node24)
    if text24 is None:
        case_skip("㉔ guard-all.py: подсказка про разбор записки моста несёт вычисленный путь, а не заглушку",
                  "выражение из файла не вычислилось в его окружении — это НЕ «в порядке»")
    else:
        hint_case("㉔ guard-all.py: подсказка про разбор записки моста несёт вычисленный путь, а не заглушку",
                  command_verdict(text24, "write-message.py", f24.resolve().parent / "write-message.py"),
                  f24, placeholder_in_code(f24), guard_reds(f24, "write-message.py"))

# ㉕ check-phoenix-invariant.py — подсказка про возврат памяти. Раздел памяти с телом, не равным новейшей версии истории.
f25 = file_under_test("hint-phoenix-invariant")
ct25, db25 = stand_container("phoenix-invariant", tools=("save-phoenix.py",))
_c = sqlite3.connect(str(db25))
_c.executescript(
    "CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT);"
    "CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, role TEXT, section TEXT, body TEXT, saved_at TEXT);"
    "INSERT INTO phoenix VALUES ('ZZ', 'state', 'новое тело', '2026-10-01 00:00:00');"
    "INSERT INTO phoenix_history (role, section, body, saved_at) VALUES ('ZZ', 'state', 'старое тело', '2026-10-01 00:00:00');")
_c.commit()
_c.close()
out25 = run_tool(f25, ["--db", str(db25)], ct25)
hint_case("㉕ check-phoenix-invariant.py: подсказка про возврат памяти несёт вычисленный путь, а не заглушку",
          command_verdict(out25, "save-phoenix.py", ct25 / ".mezosync" / "scripts" / "save-phoenix.py"),
          f25, placeholder_in_code(f25), guard_reds(f25, "save-phoenix.py"))

# ㉖ memory-archive.py — строка-ссылка на правило в конце показа блоков раздела.
f26 = file_under_test("hint-memory-archive")
ct26, db26 = stand_container("memory-archive", tools=("set-rule.py",))
_c = sqlite3.connect(str(db26))
_c.executescript(
    "CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT);"
    "CREATE TABLE phoenix_archive (id INTEGER PRIMARY KEY);"
    "INSERT INTO phoenix VALUES ('ZZ', 'state', 'тело раздела для показа', '2026-10-01 00:00:00');")
_c.commit()
_c.close()
out26 = run_tool(f26, ["--db", str(db26), "--role", "ZZ", "--section", "state", "--preview"], ct26)
hint_case("㉖ memory-archive.py: строка-ссылка на правило несёт вычисленный путь, а не заглушку",
          command_verdict(out26, "set-rule.py", ct26 / ".mezosync" / "scripts" / "set-rule.py"),
          f26, placeholder_in_code(f26), guard_reds(f26, "set-rule.py"))

# ㉗ bite-backlog-tail.py — ИСПОЛНЯЕМАЯ строка: каталог соседних модулей. Не печатается, поэтому судится
# вычислением аргумента sys.path.insert в окружении файла.
f27 = file_under_test("path-backlog-tail")
src27 = f27.read_text(encoding="utf-8")
tree27 = ast.parse(src27)
calls27 = [n for n in ast.walk(tree27) if isinstance(n, ast.Call) and ast.unparse(n.func) == "sys.path.insert"]
code27 = placeholder_in_code(f27)
if not calls27:
    case("㉗ bite-backlog-tail.py: sys.path указывает на каталог самого скрипта, без заглушки", False,
         "в файле нет вызова sys.path.insert — строку убрали или переписали: случай надо пересмотреть")
else:
    arg27 = calls27[0].args[1]
    val27 = evaluate_in_file(f27, tree27, arg27)
    own_dir = f27.resolve().parent
    good27 = (val27 is not None and Path(val27).resolve() == own_dir
              and (own_dir / "backlog_view.py").is_file())
    case("㉗ bite-backlog-tail.py: sys.path указывает на каталог самого скрипта, без заглушки",
         good27 and not code27,
         (f"строка: {ast.get_source_segment(src27, calls27[0])} → {val27!r}; соседний backlog_view.py на месте"
          if good27 and not code27 else
          f"строка: {ast.get_source_segment(src27, calls27[0])} → {val27!r} (ждали {own_dir.as_posix()})"
          + ("; заглушка в коде файла: " + " · ".join(f":{ln} {t}" for ln, t in code27) if code27 else "")))

# ⑳ живая база не тронута
live_after = (LIVE_DB.stat().st_size, LIVE_DB.stat().st_mtime_ns)
case("⑳ живая база прогоном не изменилась", live_before == live_after)

print(f"\nИТОГ: {OK}/{OK + FAIL}" + (f" · пропущено {len(SKIPPED)}" if SKIPPED else ""))
if SKIPPED:
    print(f"⚪ не проверено {len(SKIPPED)}: " + " · ".join(name for name, _ in SKIPPED))

# ═══ сверка нарочной поломки: ждали провала РОВНО своего случая ═══════════════════════
mismatch = False
if ARGS.break_name:
    expected_fail = set(BREAK_FAILS[ARGS.break_name])
    actual_fail = {n.split()[0] for n in FAILED_NAMES}
    if expected_fail == actual_fail:
        print(f"🧪 ожидание поломки «{ARGS.break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно "
              f"{' '.join(sorted(actual_fail))}")
        # поломка поймана как записано — стенд хранить незачем; код выхода прежний (1)
        mezo_stand.expected_break()
    else:
        mismatch = True
        print(f"⚠️ ожидание поломки «{ARGS.break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
              f"{' '.join(sorted(expected_fail)) or 'ничего'}, провалены "
              f"{' '.join(sorted(actual_fail)) or 'ничего'}")
covered = sorted({m for marks in BREAK_FAILS.values() for m in marks})
print(f"покрытие: нарочной поломкой покрыто случаев {len(covered)} ({' '.join(covered)}) · "
      f"поломок {len(BREAKS)} (по одной на место; совпадение проверяет прогон с --break <имя>)")
if FAIL != 0 or mismatch:
    _code = 1
elif SKIPPED:
    _code = 2
else:
    _code = 0
raise SystemExit(mezo_stand.finish(_code))
