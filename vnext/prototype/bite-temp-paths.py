# -*- coding: utf-8 -*-
r"""
bite-temp-paths.py — приёмка предупреждения о пути во временную папку Windows (карточка #671).

ЗАЧЕМ. Итоги проверок, на которые ссылаются записки и карточки, лежат во временной папке Windows, а её
чистят уборка черновых папок, срок хранения стендов и автоочистка Windows. check-dangling-refs.py теперь
называет такие пути — тем же вызовом, которым его зовут write-message.py и backlog.py перед записью
(refs_check.py). Это предупреждение, а не отказ: код выхода от него не меняется.

Случаи:
  ① находит путь во временную папку в шести видах: полный путь, короткое имя каталога пользователя,
     %TEMP%, $env:TEMP, /tmp Git Bash, черновая папка чата; два пути в строке — два; черновая папка
     внутри полного пути — одна находка, не две
  ② ВСТРЕЧНЫЙ: путь в контуре и в клоне, C:/tmp, слова о самой папке без конкретной части
     («%TEMP%», «AppData/Local/Temp», «%TEMP%/gordi/…», «scratchpad/<папка>», папка чатов проекта
     «%TEMP%\claude\C--work--proj», «%TEMP%\claude\…\scratchpad») — без предупреждения
  ③ --file: строка, позиция и сам путь названы; код 0 — предупреждение код выхода не меняет
  ④ форма вызова write-message.py и backlog.py (--file --quiet --role --db): путь назван; чистый
     текст — вывод пуст
  ⑤ путь и голый номер вместе: оба предупреждения, код 1 — как у голого номера и раньше
  ⑥ refs_check.py этой раскладки (его зовут write-message.py и backlog.py) смотрит в ЭТУ проверку
     и печатает предупреждение с меткой («комментарий») вместо имени временного файла
  ⑦ НАРОЧНАЯ ПОЛОМКА «проверка выключена»: копия check-dangling-refs.py без вызова report_temp —
     случай ③ на ней проваливается
  ⑧ НАРОЧНАЯ ПОЛОМКА «конкретная часть не нужна»: копия без проверки _concrete — встречный ② на ней
     проваливается (встречный различает, а не просто молчит)

⚖️ Граница: строка замера «с путём во временную папку Windows» в --scan-cards/--scan-messages читает
живую базу и здесь не испытывается.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

CHECKER = HERE / "check-dangling-refs.py"
OK = FAIL = 0


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


chk = load(CHECKER, "chk")
stand = mezo_stand.new("temp-paths-")
mz = stand / ".mezosync"
mz.mkdir()
mezo_stand.empty_db(mezo_paths.live_db(), mz / "mezosync.db")
mezo_stand.seed_roles(mz / "mezosync.db", ["ZZA"])


def run(checker, *args):
    p = subprocess.run([sys.executable, str(checker), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=mezo_stand.stand_env(
                           stand, PYTHONIOENCODING="utf-8", PYTHONPATH=str(HERE)), cwd=str(stand))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


FOUND = [
    ("итог: D:/Users/zz/AppData/Local/Temp/claude/C--x/abc/scratchpad/w12/r4.txt.", 1),
    (r"см. D:\Users\ZZ0000~1.TEM\AppData\Local\Temp\bite-all-failures\bite-x.py.1.txt", 1),
    ("в %TEMP%/bite-all-failures/x.txt", 1),
    ("$env:TEMP\\gp\\a.log", 1),
    ("лежит в /tmp/run1/out.txt", 1),
    ("итоги в scratchpad/w12/d1017/r4.txt", 1),
    ("две: %TEMP%/a/b.txt и scratchpad/w1/c.txt", 2),
]
COUNTER = [
    "D:/work/.atlas/vnext-tools/check-dangling-refs.py",
    "C:/github/gordipack/vnext/prototype/bite-all.py",
    "C:/tmp/x.txt",
    "стенды лежат в %TEMP%, папка AppData/Local/Temp сама по себе",
    "общий каталог %TEMP%/gordi/… и черновая scratchpad/<папка>",
    r"папка чатов проекта %TEMP%\claude\C--work--proj и черновые %TEMP%\claude\…\scratchpad",
]


def judge_find(mod):
    found = [(t, w, len(mod.find_temp(t))) for t, w in FOUND]
    counter = [(t, len(mod.find_temp(t))) for t in COUNTER]
    return found, counter


found, counter = judge_find(chk)
case("① путь во временную папку найден в шести видах; два в строке — два; черновая внутри полного пути — одна",
     all(g == w for _, w, g in found), " · ".join(f"{g}/{w}" for _, w, g in found))
case("② ВСТРЕЧНЫЙ: путь в контуре и клоне, C:/tmp, слова о папке без конкретной части — без предупреждения",
     all(n == 0 for _, n in counter), " · ".join(f"{n}" for _, n in counter))

note = stand / "note.md"
PATH_IN_NOTE = "D:/Users/zz/AppData/Local/Temp/zz-run/итог.txt"
note.write_text(f"# заголовок\nитог прогона — {PATH_IN_NOTE}, карточка #671\n", encoding="utf-8")
clean = stand / "clean.md"
clean.write_text("итог прогона — D:/work/.atlas/vnext-tools/итог.txt, карточка #671\n", encoding="utf-8")
both = stand / "both.md"
both.write_text(f"итог — {PATH_IN_NOTE}, смотри #671\n", encoding="utf-8")


def judge_file(checker):
    code, out = run(checker, "--file", str(note))
    return code, out, ("путей во временную папку Windows — 1" in out and
                       f"строка 2, позиция 16 — {PATH_IN_NOTE}" in out and code == 0)


code3, out3, ok3 = judge_file(CHECKER)
case("③ --file: строка, позиция и путь названы; код 0 — код выхода предупреждение не меняет", ok3,
     f"код {code3} · {[l.strip() for l in out3.splitlines() if 'временную' in l or 'позиция' in l]}")

db = str(mz / "mezosync.db")
code4, out4 = run(CHECKER, "--file", str(note), "--quiet", "--role", "ZZA", "--db", db)
code4c, out4c = run(CHECKER, "--file", str(clean), "--quiet", "--role", "ZZA", "--db", db)
case("④ форма вызова write-message.py и backlog.py (--quiet --role --db): путь назван; чистый текст — пусто",
     PATH_IN_NOTE in out4 and code4 == 0 and out4c.strip() == "" and code4c == 0,
     f"с путём: код {code4}, путь {'назван' if PATH_IN_NOTE in out4 else 'НЕ назван'} · "
     f"чистый: код {code4c}, вывод {'пуст' if not out4c.strip() else repr(out4c[:120])}")

code5, out5 = run(CHECKER, "--file", str(both))
case("⑤ путь и голый номер вместе: оба предупреждения, код 1 (как у голого номера и раньше)",
     code5 == 1 and "временную папку" in out5 and "неразрешимых ссылок — 1" in out5, f"код {code5}")

# ⑥ refs_check.py этой раскладки: пакет (<клон>/scripts) или контейнер (<контейнер>/.mezosync/scripts)
rc_path = next((p for p in (HERE.parent.parent / "scripts" / "refs_check.py",
                            HERE.parent / ".mezosync" / "scripts" / "refs_check.py") if p.is_file()), None)
if rc_path is None:
    case("⑥ refs_check.py этой раскладки смотрит в эту проверку и печатает предупреждение", False,
         "refs_check.py рядом не найден ни в раскладке пакета, ни в раскладке контура")
else:
    rc = load(rc_path, "refs_check_here")
    same = Path(rc.CHECKER).resolve() == CHECKER
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc.warn_dangling(note.read_text(encoding="utf-8"), label="комментарий")
    said = buf.getvalue()
    case("⑥ refs_check.py этой раскладки смотрит в эту проверку и печатает предупреждение с меткой",
         same and PATH_IN_NOTE in said and "комментарий" in said,
         f"{rc_path.as_posix()} → {Path(rc.CHECKER).as_posix()} ({'эта' if same else 'ДРУГАЯ'} проверка) · "
         f"путь {'назван' if PATH_IN_NOTE in said else 'НЕ назван'}")

# ── нарочные поломки — копии проверки рядом в стенде ────────────────────────────────────
source = CHECKER.read_text(encoding="utf-8")
WIRE = "    report_temp(text, where, role=role, full=full, conn=conn)\n"
CONCRETE = "if not tail or not any(_concrete(s) for s in"
for anchor in (WIRE, CONCRETE):
    if anchor not in source:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: в check-dangling-refs.py нет якоря «{anchor.strip()}» — "
                         "нарочная поломка судила бы не тот код")
off = stand / "check-off.py"
off.write_text(source.replace(WIRE, "    pass\n", 1), encoding="utf-8")
_, out7, ok7 = judge_file(off)
case("⑦ НАРОЧНАЯ ПОЛОМКА «проверка выключена»: на копии без report_temp случай ③ проваливается",
     not ok7, f"на копии: путь {'назван — поломка НЕ видна' if PATH_IN_NOTE in out7 else 'не назван — поломка видна'}")
loose = stand / "check-loose.py"
loose.write_text(source.replace(CONCRETE, "if not tail or not any(True for s in", 1), encoding="utf-8")
_, counter8 = judge_find(load(loose, "chk_loose"))
case("⑧ НАРОЧНАЯ ПОЛОМКА «конкретная часть не нужна»: встречный ② на копии проваливается",
     any(n for _, n in counter8), "находок на встречных: " + " · ".join(f"{n}" for _, n in counter8))

print(f"\nИТОГ: {OK}/{OK + FAIL}" + ("" if FAIL == 0 else " — 🔴 ПРЕДУПРЕЖДЕНИЕ О ВРЕМЕННОЙ ПАПКЕ НЕ ПРИНЯТО"))
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
