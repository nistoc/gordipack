#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА check-acceptance-env.py (карточка #613 ②).

Предмет: check-acceptance-env.py обязан находить subprocess-вызов инструмента контура
БЕЗ env= закреплённого стенда — и НЕ находить: правильно закреплённый вызов, вызов
с разрешающим комментарием на строке, вызов к инструменту, который контур не читает.

Случаи (различающий = проверка обязана ответить ИНАЧЕ, а не одинаково):
  ① вызов БЕЗ env= к инструменту контура ......... НАХОДКА              РАЗЛИЧАЮЩИЙ
  ② env=mezo_stand.stand_env(d) .................. НЕ находка (контроль)
  ③ env=dict(os.environ) (протекает) .............. НАХОДКА              РАЗЛИЧАЮЩИЙ
  ④ БЕЗ env=, но со строкой-разрешением `# env: caller — …` .. ПРОЩЕНО, не находка
  ⑤ цель — инструмент, контур НЕ читающий ......... НЕ находка (само не сканируется)
  Р1 обратный ход: строка-разрешение ОСЛЕПЛЕНА в копии проверки — ④ становится находкой
     (доказывает, что механизм комментария-разрешения — не украшение, а часть проверки)

Доработка PROTO (реестр известного долга acceptance-env-debt.txt, тот же приход #613):
  а) записанная в реестре находка .................. НЕ провал, считается в долге     РАЗЛИЧАЮЩИЙ
  б) новый вызов В ТОЙ ЖЕ файле, но в ДРУГОЙ функции — не в реестре ...... ПРОВАЛ      РАЗЛИЧАЮЩИЙ
  в) в реестре записано 2, живых стало 1 ........... «долг уменьшился», код 0          РАЗЛИЧАЮЩИЙ
  г) НАРОЧНАЯ ПОЛОМКА (в копии проверки): сверка с реестром — только по имени файла,
     без функции/инструмента — случай (б) на такой копии ПРОХОДИТ (не находит новый
     вызов) ⇒ доказывает, что точность ключа реестра — не украшение
  з) вызов записан реестром разрядом «законно» ....... НЕ провал и НЕ долг           РАЗЛИЧАЮЩИЙ
  и) НАРОЧНАЯ ПОЛОМКА (в копии проверки): реестр покрывает только «долг» — (з) снова
     провал ⇒ законное, записанное реестром вместо комментария, держится именно этим

Реестра рядом нет (контур, собранный из пакета GORDI — доработка PROTO 2026-09-14):
  д) реестра по умолчанию нет ......................... «⚠️» с числом находок, код 0    РАЗЛИЧАЮЩИЙ
  е) --debt-list указывает на несуществующий файл ...... отказ, код 2                   РАЗЛИЧАЮЩИЙ
  ж) НАРОЧНАЯ ПОЛОМКА (в копии проверки): ветка «реестра нет» отключена — (д) на такой
     копии снова даёт провал (код 1) ⇒ общий прогон в новом контуре держит именно она
  Случаи ①–⑤ и Р1 судят РАЗБОР, а не реестр, — поэтому зовут проверку с --no-debt-list:
  без реестра по умолчанию она теперь не провалилась бы.

Интерпретатор в переменной (возврат COORD по карточке #613, записка #5267):
  к) PY = sys.executable → subprocess.run([PY, TOOL, …]) ........ НАХОДКА              РАЗЛИЧАЮЩИЙ
  л) cmd = [sys.executable, TOOL, …] → subprocess.run(cmd) ...... НАХОДКА              РАЗЛИЧАЮЩИЙ
  м) своя обёртка run(cmd, d) с env стенда внутри, снаружи cmd с интерпретатором — НЕ находка
  Поломки (в копии проверки), у каждой приманки своя: «имя внутри списка не прослеживается»
  — (к) пропадает, (л) остаётся; «голое имя-аргумент не прослеживается» — (л) пропадает,
  (к) остаётся; «обёртка run(…) прослеживается как subprocess» — (м) становится находкой.

Нулевой день контура (заявка 29 пакета): реестра рядом нет у свежесобранного контура — это свойство
нового контура, «ℹ️», а не «⚠️». Контур для этих случаев СОБИРАЕТСЯ из пакета сборщиком init-group.py
(так же, как у bite-fresh-circuit.py), а не рисуется рукой: признак читается из ленты настоящей базы.
  н) свежий контур (в ленте нет записок), реестра нет ... «ℹ️ … свойство нового контура», ни одного «⚠️»  РАЗЛИЧАЮЩИЙ
  о) ТОТ ЖЕ контур, но в ленте одна записка ................ «⚠️», как было, ни одного «ℹ️»                  РАЗЛИЧАЮЩИЙ
  п) НАРОЧНАЯ ПОЛОМКА (в копии проверки): нулевой день не различается — (н) на такой копии
     краснеет, а (о) остаётся зелёным ⇒ красит РОВНО (н). Копия с поломкой кладётся в каталог
     из переменной MEZO_BREAKS_DIR (если задана), иначе — в стенд, который убирается при успехе.
  р) встречный к месту: та же копия, но с реестром РЯДОМ (как у живого контура) — строки
     «реестра рядом нет» нет вовсе. Проверка ищет реестр рядом с СОБОЙ, поэтому (н)(о) судят
     КОПИЮ без реестра рядом, а не файл рядом с приёмкой: в живом контуре реестр лежит рядом
     с проверкой, и ветка нулевого дня там не наступает (замер 2026-10-06 12:48 UTC в Atlas:
     (н)(о) провалились на исправной проверке — судили место, а не нулевой день).

Остальная часть — своя песочница: копия check-acceptance-env.py + синтетический стенд. Живой контур
не трогает — все файлы синтетические, живая база не открывается вовсе (контур нулевого дня — свой,
во временном каталоге).
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
import mezo_paths  # noqa: E402

REAL_CHECK = Path(__file__).resolve().parent / "check-acceptance-env.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


FAKE_CONTAINER_TOOL = '''# -*- coding: utf-8 -*-
"""fake-container-tool.py — синтетика приёмки #613, притворяется читающим контур."""
import mezo_paths  # noqa: F401 — этого хватает, чтобы reads_container() ответил True
'''

FAKE_EXTERNAL_TOOL = '''# -*- coding: utf-8 -*-
"""fake-external-tool.py — синтетика приёмки #613: контур НЕ читает."""
print("я контур не читаю")
'''

BITE_CASE1_NO_ENV = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)
'''

BITE_CASE2_PINNED = '''import subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call(d):
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True,
                   env=mezo_stand.stand_env(d))
'''

BITE_CASE3_LEAK_DICT = '''import os, subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    env = dict(os.environ)
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

BITE_CASE4_EXCUSED = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)  # env: caller — тестовая причина случая 4
'''

BITE_CASE5_INDIFFERENT = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-external-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--x"], capture_output=True)
'''

# ── синтетика случаев (к)(л)(м): интерпретатор в переменной (возврат COORD, записка #5267) ──
BITE_CASE9_PY_VAR = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")
PY = sys.executable


def call():
    subprocess.run([PY, TOOL, "--db", "x"], capture_output=True)
'''

BITE_CASE10_CMD_VAR = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    cmd = [sys.executable, TOOL, "--db", "x"]
    subprocess.run(cmd, capture_output=True)
'''

BITE_CASE11_WRAPPER = '''import subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def run(cmd, d):
    return subprocess.run(cmd, capture_output=True, env=mezo_stand.stand_env(d))


def call(d):
    cmd = [sys.executable, TOOL, "--db", "x"]
    run(cmd, d)
'''

# ── синтетика случаев (а)-(г): реестр известного долга ──────────────────────────────
BITE_CASE6_RECORDED = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call1():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)


def call2():
    subprocess.run([sys.executable, TOOL, "--db", "y"], capture_output=True)
'''

BITE_CASE7_SHRUNK = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "z"], capture_output=True)
'''

BITE_CASE8_LEGIT = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "w"], capture_output=True)
'''

DEBT_CONTENT = (
    "# синтетический реестр для приёмки bite-acceptance-env.py — НЕ деталь поставки\n"
    "vnext-tools/bite-case6-recorded.py :: call1 :: fake-container-tool :: 1 :: долг :: "
    "тестовая запись случаев (а)/(б)\n"
    "vnext-tools/bite-case7-shrunk.py :: call :: fake-container-tool :: 2 :: долг :: "
    "тестовая запись случая (в) — записано 2, живых 1\n"
    "vnext-tools/bite-case8-legit.py :: call :: fake-container-tool :: 1 :: законно :: "
    "тестовая запись случая (з) — законный вызов записан реестром, не комментарием\n"
)


def build_stand(checker_source: str):
    """Синтетический стенд: копия проверки (checker_source — возможно, ослеплённая) +
    её сосед mezo_paths.py + выдуманные vnext-tools/.mezosync/scripts с пятью случаями."""
    d = mezo_stand.new("bite-acceptance-env-")
    vt = d / "vnext-tools"
    ms = d / ".mezosync" / "scripts"
    vt.mkdir(parents=True, exist_ok=True)
    ms.mkdir(parents=True, exist_ok=True)
    (vt / "check-acceptance-env.py").write_text(checker_source, encoding="utf-8")
    (vt / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "mezo_stand.py").write_text(
        Path(mezo_stand.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
    (vt / "fake-external-tool.py").write_text(FAKE_EXTERNAL_TOOL, encoding="utf-8")
    (vt / "bite-case1-no-env.py").write_text(BITE_CASE1_NO_ENV, encoding="utf-8")
    (vt / "bite-case2-pinned.py").write_text(BITE_CASE2_PINNED, encoding="utf-8")
    (vt / "bite-case3-leak-dict.py").write_text(BITE_CASE3_LEAK_DICT, encoding="utf-8")
    (vt / "bite-case4-excused.py").write_text(BITE_CASE4_EXCUSED, encoding="utf-8")
    (vt / "bite-case5-indifferent.py").write_text(BITE_CASE5_INDIFFERENT, encoding="utf-8")
    (vt / "bite-case9-py-var.py").write_text(BITE_CASE9_PY_VAR, encoding="utf-8")
    (vt / "bite-case10-cmd-var.py").write_text(BITE_CASE10_CMD_VAR, encoding="utf-8")
    (vt / "bite-case11-wrapper.py").write_text(BITE_CASE11_WRAPPER, encoding="utf-8")
    return d


def build_debt_stand(checker_source: str, debt_content: str):
    """Стенд для случаев (а)-(г): копия проверки + реестр acceptance-env-debt.txt рядом
    с ней (путь по умолчанию — проверка ищет его САМА, без --debt-list) + два
    синтетических файла (case6 — две функции, одна в реестре; case7 — долг завышен)."""
    d = mezo_stand.new("bite-acceptance-env-debt-")
    vt = d / "vnext-tools"
    vt.mkdir(parents=True, exist_ok=True)
    (vt / "check-acceptance-env.py").write_text(checker_source, encoding="utf-8")
    (vt / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
    (vt / "bite-case6-recorded.py").write_text(BITE_CASE6_RECORDED, encoding="utf-8")
    (vt / "bite-case7-shrunk.py").write_text(BITE_CASE7_SHRUNK, encoding="utf-8")
    (vt / "bite-case8-legit.py").write_text(BITE_CASE8_LEGIT, encoding="utf-8")
    (vt / "acceptance-env-debt.txt").write_text(debt_content, encoding="utf-8")
    return d


def call_checker(stand: Path, *extra):
    checker = stand / "vnext-tools" / "check-acceptance-env.py"
    return subprocess.run([sys.executable, str(checker), *extra],
                          capture_output=True, text=True, encoding="utf-8",
                          env=mezo_stand.stand_env(stand))


def run_checker_text(stand: Path, *extra):
    r = call_checker(stand, *extra)
    return r.stdout + r.stderr, r.returncode


def run_checker(stand: Path, *extra):
    r = call_checker(stand, "--json", *extra)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"ok": None, "findings": [], "excused": [], "_raw": (r.stdout + r.stderr)[:800]}
    return data, r.returncode


def names(entries, key="file"):
    return {Path(e[key]).name for e in entries}


def new_key_funcs(data, fname):
    """Имена функций из debt.new_keys, чей файл == fname (для случаев (а)/(б))."""
    return {row["function"] for row in data.get("debt", {}).get("new_keys", [])
            if Path(row["file"]).name == fname}


def shrunk_rows(data, fname):
    return [row for row in data.get("debt", {}).get("shrunk", [])
            if Path(row["file"]).name == fname]


# ── нулевой день контура (заявка 29 пакета): свежий контур собирается из пакета ───────────
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
    """Свежий контур — тем же сборщиком init-group.py, что у bite-fresh-circuit.py.

    → (корень контура, база или None, вывод сборщика). В каталог его скриптов кладётся ещё один
    синтетический вызов без env= (случай ① этой приёмки), чтобы находка была при ЛЮБОМ составе пакета:
    без находок проверка не печатает строку про реестр вовсе, и случай судил бы пустоту."""
    root = mezo_stand.new("bite-acceptance-env-fresh-")
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str(pack / "scripts" / "init-group.py"), "--name", "bite",
                        "--path", str(mez), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       env=mezo_stand.stand_env(root))
    db = mez / "mezosync.db"
    if r.returncode == 0 and db.exists() and (mez / "scripts").is_dir():
        (mez / "scripts" / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
        (mez / "scripts" / "bite-case1-no-env.py").write_text(BITE_CASE1_NO_ENV, encoding="utf-8")
        return root, db, ""
    return root, None, ((r.stdout or "") + (r.stderr or ""))[-600:]


def breaks_dir(stand: Path, name: str) -> Path:
    """Куда класть копию инструмента с нарочной поломкой: <MEZO_BREAKS_DIR>/<имя>, а без переменной —
    внутрь стенда (он убирается при успехе). Так копию поломки можно предъявить глазами."""
    base = os.environ.get("MEZO_BREAKS_DIR")
    d = (Path(base) / name) if base else (stand / "breaks" / name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def zero_day_verdicts(check: Path, container: Path, fresh_db: Path, used_db: Path):
    """Звать проверку НА ДВУХ базах одного контура — без записок в ленте и с одной запиской —
    и вернуть суждения (н) и (о) с подробностью. Звать её прямым вызовом, как зовёт общий прогон
    (без --no-debt-list и без --debt-list): ветка «реестра рядом нет» — именно она."""
    def run(db: Path):
        r = subprocess.run([sys.executable, str(check), "--db", str(db)],
                           capture_output=True, text=True, encoding="utf-8",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
        out = (r.stdout or "") + (r.stderr or "")
        lines = out.splitlines()
        marked = [l for l in lines if "реестра известного долга рядом нет" in l]
        return r.returncode, lines, marked

    rc_n, lines_n, marked_n = run(fresh_db)
    rc_o, lines_o, marked_o = run(used_db)
    fresh_ok = (rc_n == 0 and len(marked_n) == 1 and marked_n[0].startswith("ℹ️")
                and "свойство нового контура" in marked_n[0]
                and not any(l.startswith("⚠️") for l in lines_n))
    used_ok = (rc_o == 0 and len(marked_o) == 1 and marked_o[0].startswith("⚠️")
               and not any(l.startswith("ℹ️") for l in lines_o))
    return (fresh_ok, f"rc={rc_n} · строка про реестр: {marked_n[0][:90] if marked_n else '—'}"
                      f" · «⚠️»: {sum(l.startswith('⚠️') for l in lines_n)}",
            used_ok, f"rc={rc_o} · строка про реестр: {marked_o[0][:90] if marked_o else '—'}"
                     f" · «ℹ️»: {sum(l.startswith('ℹ️') for l in lines_o)}")


def main() -> int:
    if not REAL_CHECK.exists():
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {REAL_CHECK} не найден — приёмке нечего испытывать.")
    ok = True
    real_source = REAL_CHECK.read_text(encoding="utf-8")

    stand = build_stand(real_source)
    data, rc = run_checker(stand, "--no-debt-list")
    found = names(data.get("findings", []))
    excused = names(data.get("excused", []))

    ok &= case("① БЕЗ env= к инструменту контура — НАХОДКА",
               "bite-case1-no-env.py" in found,
               f"находки: {sorted(found)}", differ=True)
    ok &= case("② env=mezo_stand.stand_env(d) — НЕ находка (контроль)",
               "bite-case2-pinned.py" not in found and "bite-case2-pinned.py" not in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}")
    ok &= case("③ env=dict(os.environ) протекает — НАХОДКА",
               "bite-case3-leak-dict.py" in found,
               f"находки: {sorted(found)}", differ=True)
    ok &= case("④ БЕЗ env=, но со строкой-разрешением — ПРОЩЕНО, не находка",
               "bite-case4-excused.py" not in found and "bite-case4-excused.py" in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}", differ=True)
    ok &= case("⑤ цель контур не читает — не находка и не прощение (не сканируется вовсе)",
               "bite-case5-indifferent.py" not in found and "bite-case5-indifferent.py" not in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}", differ=True)
    ok &= case("итог: exit-код совпадает с наличием непрощённых находок",
               (rc != 0) == bool(data.get("findings")),
               f"rc={rc}, findings={len(data.get('findings', []))}")

    # ── (к)(л)(м) интерпретатор в переменной ─────────────────────────────────────────
    ok &= case("(к) PY = sys.executable → subprocess.run([PY, TOOL, …]) — НАХОДКА",
               "bite-case9-py-var.py" in found, f"находки: {sorted(found)}", differ=True)
    ok &= case("(л) cmd = [sys.executable, TOOL, …] → subprocess.run(cmd) — НАХОДКА",
               "bite-case10-cmd-var.py" in found, f"находки: {sorted(found)}", differ=True)
    ok &= case("(м) своя обёртка run(cmd, d) с env стенда внутри — НЕ находка (не считать дважды)",
               "bite-case11-wrapper.py" not in found, f"находки: {sorted(found)}", differ=True)
    anchor_frontier = "    frontier = bare + nested"
    anchor_wrapper = "    if not isinstance(call.func, ast.Attribute):\n        return False"
    for anchor_text, label in ((anchor_frontier, "прослеживание имён"), (anchor_wrapper, "обёртки")):
        if real_source.count(anchor_text) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{label}» найден {real_source.count(anchor_text)} раз")
    broken_k = build_stand(real_source.replace(
        anchor_frontier, "    frontier = bare  # ПОЛОМКА (к): имя внутри списка не прослеживается"))
    found_k = names(run_checker(broken_k, "--no-debt-list")[0].get("findings", []))
    ok &= case("(к) поломка «имя внутри списка не прослеживается»: (к) пропадает, (л) остаётся",
               "bite-case9-py-var.py" not in found_k and "bite-case10-cmd-var.py" in found_k,
               f"находки на копии: {sorted(found_k)}", differ=True)
    broken_l = build_stand(real_source.replace(
        anchor_frontier, "    frontier = nested  # ПОЛОМКА (л): голое имя-аргумент не прослеживается"))
    found_l = names(run_checker(broken_l, "--no-debt-list")[0].get("findings", []))
    ok &= case("(л) поломка «голое имя-аргумент не прослеживается»: (л) пропадает, (к) остаётся",
               "bite-case10-cmd-var.py" not in found_l and "bite-case9-py-var.py" in found_l,
               f"находки на копии: {sorted(found_l)}", differ=True)
    broken_m = build_stand(real_source.replace(
        anchor_wrapper, "    if False:  # ПОЛОМКА (м): обёртка прослеживается как subprocess\n        return False"))
    found_m = names(run_checker(broken_m, "--no-debt-list")[0].get("findings", []))
    ok &= case("(м) поломка «обёртка прослеживается как subprocess»: (м) становится находкой",
               "bite-case11-wrapper.py" in found_m,
               f"находки на копии: {sorted(found_m)}", differ=True)

    # ── Р1 обратный ход: строка-разрешение ОСЛЕПЛЕНА в КОПИИ проверки ──────────────
    anchor = "m = ALLOW_RE.search(line_text)"
    if real_source.count(anchor) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь найден {real_source.count(anchor)} раз")
    blinded_source = real_source.replace(anchor, "m = None  # ОСЛЕПЛЕНО ПРИЁМКОЙ bite-acceptance-env.py")
    stand2 = build_stand(blinded_source)
    data2, rc2 = run_checker(stand2, "--no-debt-list")
    found2 = names(data2.get("findings", []))
    ok &= case("Р1 ослеплённая проверка: ④ становится находкой (разрешение — не украшение)",
               "bite-case4-excused.py" in found2,
               f"находки ослеплённой копии: {sorted(found2)}", differ=True)

    # ── (а)(б)(в) реестр известного долга ───────────────────────────────────────────
    stand3 = build_debt_stand(real_source, DEBT_CONTENT)
    data3, rc3 = run_checker(stand3)
    debt3 = data3.get("debt", {})
    new_funcs_case6 = new_key_funcs(data3, "bite-case6-recorded.py")
    shrunk_case7 = shrunk_rows(data3, "bite-case7-shrunk.py")

    ok &= case("(а) записанная в реестре находка — НЕ провал, считается в долге",
               "call1" not in new_funcs_case6 and debt3.get("known_calls", 0) >= 1,
               f"новые функции case6: {sorted(new_funcs_case6)} · known_calls={debt3.get('known_calls')}",
               differ=True)
    ok &= case("(б) новый вызов в ДРУГОЙ функции того же файла — ПРОВАЛ",
               "call2" in new_funcs_case6,
               f"новые функции case6: {sorted(new_funcs_case6)}", differ=True)
    ok &= case("(в) в реестре 2, живых 1 — «долг уменьшился», код 0 у ЭТОЙ строки",
               len(shrunk_case7) == 1 and shrunk_case7[0].get("recorded") == 2
               and shrunk_case7[0].get("live") == 1,
               f"shrunk case7: {shrunk_case7}", differ=True)
    new_funcs_case8 = new_key_funcs(data3, "bite-case8-legit.py")
    ok &= case("(з) вызов, записанный реестром как «законно», — НЕ провал и НЕ долг",
               not new_funcs_case8 and debt3.get("legitimate_calls", 0) == 1
               and debt3.get("known_calls") == 3,
               f"новые функции case8: {sorted(new_funcs_case8)} · законно={debt3.get('legitimate_calls')}"
               f" · долг={debt3.get('known_calls')}", differ=True)

    # ── (и) НАРОЧНАЯ ПОЛОМКА: реестр покрывает только разряд «долг» ─────────────────
    anchor_legit = "    covered = {**dolg, **legit}"
    if real_source.count(anchor_legit) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь покрытия «законно» найден "
                          f"{real_source.count(anchor_legit)} раз")
    debt_only_source = real_source.replace(
        anchor_legit, "    covered = dict(dolg)  # ПОЛОМКА (и): «законно» ничего не прощает")
    stand8 = build_debt_stand(debt_only_source, DEBT_CONTENT)
    data8, _rc8 = run_checker(stand8)
    ok &= case("(и) поломка «прощает только долг»: (з) снова провал",
               "call" in new_key_funcs(data8, "bite-case8-legit.py"),
               f"новые функции case8 на копии: {sorted(new_key_funcs(data8, 'bite-case8-legit.py'))}"
               f" — должно быть ['call']", differ=True)

    # ── (г) НАРОЧНАЯ ПОЛОМКА: сверка с реестром только по имени файла ──────────────
    anchor_covers = "    return key in dolg"
    if real_source.count(anchor_covers) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь key_covers найден "
                          f"{real_source.count(anchor_covers)} раз")
    filename_only_source = real_source.replace(
        anchor_covers,
        "    return any(k[0] == key[0] for k in dolg)  # ПОЛОМКА (г): только по имени файла")
    stand4 = build_debt_stand(filename_only_source, DEBT_CONTENT)
    data4, rc4 = run_checker(stand4)
    new_funcs_case6_broken = new_key_funcs(data4, "bite-case6-recorded.py")
    ok &= case("(г) поломка «сверка только по имени файла»: (б) ПЕРЕСТАЁТ находиться",
               "call2" not in new_funcs_case6_broken,
               f"новые функции case6 на ослеплённой копии: {sorted(new_funcs_case6_broken)} "
               f"— должно быть ПУСТО (поломка прячет call2)", differ=True)

    # ── (д)(е) реестра рядом нет · явный путь неверен — ТЕКСТОВЫЙ вывод, как его видит
    #    общий прогон проверок (он зовёт проверку без аргументов) ──────────────────────
    strict_count = len(data.get("findings", []))
    out5, rc5 = run_checker_text(stand)
    warn5 = [l for l in out5.splitlines()
             if l.startswith("⚠️") and "реестра известного долга рядом нет" in l]
    ok &= case("(д) реестра рядом нет — строка «⚠️» с числом находок, код 0",
               rc5 == 0 and len(warn5) == 1 and f"стенда {strict_count} в" in warn5[0],
               f"rc={rc5} · строгих находок {strict_count} · строка: {warn5[0] if warn5 else '—'}",
               differ=True)
    missing = stand / "vnext-tools" / "нет-такого-реестра.txt"
    out6, rc6 = run_checker_text(stand, "--debt-list", str(missing))
    ok &= case("(е) --debt-list на несуществующий файл — отказ, код 2",
               rc6 == 2 and "реестр долга не найден" in out6,
               f"rc={rc6} · {out6.strip().splitlines()[-1] if out6.strip() else '—'}", differ=True)

    # ── (ж) НАРОЧНАЯ ПОЛОМКА: ветка «реестра нет» отключена в копии проверки ──────────
    anchor_missing = "    if not debt_path.exists():"
    if real_source.count(anchor_missing) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь ветки «реестра нет» найден "
                          f"{real_source.count(anchor_missing)} раз")
    no_branch_source = real_source.replace(
        anchor_missing, "    if False:  # ПОЛОМКА (ж): реестра нет — читается как пустой")
    stand7 = build_stand(no_branch_source)
    out7, rc7 = run_checker_text(stand7)
    ok &= case("(ж) поломка «ветки реестра нет»: (д) снова провал — новый контур упал бы",
               rc7 == 1,
               f"rc={rc7} на копии без ветки — должно быть 1", differ=True)

    # ── (н)(о)(п) НУЛЕВОЙ ДЕНЬ: свежий контур из пакета — «ℹ️ свойство нового контура», не «⚠️» ──
    pack = find_pack()
    if pack is None:
        raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: пакета с scripts/init-group.py не нашлось (ни по mezo_paths."
                         "template_root(), ни рядом) — свежий контур собрать не из чего, случаи (н)(о)(п) "
                         "не состоялись. Это не «зелёное».")
    fresh_root, fresh_db, build_note = build_fresh_circuit(pack)
    if fresh_db is None:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: сборщик init-group.py не собрал контур: {build_note}")
    used_db = mezo_stand.snapshot_db(fresh_db, fresh_root / ".mezosync" / "mezosync-used.db")
    con = sqlite3.connect(str(used_db))
    con.execute("INSERT INTO messages (writer_role, body_md) VALUES ('COORD', "
                "'проба приёмки: в ленте уже есть записка — день не нулевой')")
    con.commit()
    con.close()
    # Проверка без --debt-list ищет реестр РЯДОМ С СОБОЙ. У живого контура он там лежит, и ветка
    # «реестра рядом нет» не наступает — поэтому судим копию того же текста в каталоге без реестра,
    # как общий прогон зовёт проверку свежего контура (так же лежит и копия поломки (п)).
    real_copy_dir = fresh_root / "check-copy"
    real_copy_dir.mkdir()
    real_copy = real_copy_dir / "check-acceptance-env.py"
    real_copy.write_text(real_source, encoding="utf-8")
    (real_copy_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    real_fresh_ok, real_fresh_note, real_used_ok, real_used_note = zero_day_verdicts(
        real_copy, fresh_root, fresh_db, used_db)
    ok &= case("(н) свежий контур из пакета, реестра нет, в ленте нет записок — «ℹ️ … свойство нового "
               "контура» и ни одного «⚠️»",
               real_fresh_ok, f"копия {real_copy}: {real_fresh_note}", differ=True)
    ok &= case("(о) ТОТ ЖЕ контур, но в ленте одна записка — «⚠️», как было, и ни одного «ℹ️»",
               real_used_ok, real_used_note, differ=True)

    # ── (р) встречный к месту: реестр рядом с копией — ветки «реестра рядом нет» нет вовсе ────
    near_dir = fresh_root / "check-copy-with-debt"
    near_dir.mkdir()
    near_check = near_dir / "check-acceptance-env.py"
    near_check.write_text(real_source, encoding="utf-8")
    (near_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (near_dir / "acceptance-env-debt.txt").write_text("", encoding="utf-8")
    near_fresh_ok, near_fresh_note, _, _ = zero_day_verdicts(near_check, fresh_root, fresh_db, used_db)
    ok &= case("(р) встречный к месту: реестр рядом с копией (как у живого контура) — строки "
               "«реестра рядом нет» нет, (н) на ней не держится",
               (not near_fresh_ok) and "строка про реестр: —" in near_fresh_note,
               f"копия {near_check}: {near_fresh_note}")

    # ── (п) НАРОЧНАЯ ПОЛОМКА: в копии проверки нулевой день не различается ───────────────────
    anchor_zero_day = "        zero_day = bool(getattr(mezo_paths, \"is_zero_day\", lambda _db: False)(db_path))"
    if real_source.count(anchor_zero_day) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь различителя нулевого дня найден "
                         f"{real_source.count(anchor_zero_day)} раз")
    broken_dir = breaks_dir(fresh_root, "zero-day-check")
    broken_check = broken_dir / "check-acceptance-env.py"
    broken_check.write_text(real_source.replace(
        anchor_zero_day, "        zero_day = False  # ПОЛОМКА (п): нулевой день не различается"),
        encoding="utf-8")
    (broken_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    brk_fresh_ok, brk_fresh_note, brk_used_ok, brk_used_note = zero_day_verdicts(
        broken_check, fresh_root, fresh_db, used_db)
    ok &= case("(п) поломка «нулевой день не различается»: красит РОВНО (н), а (о) остаётся зелёным",
               (not brk_fresh_ok) and brk_used_ok,
               f"копия {broken_check}: (н) {'✅' if brk_fresh_ok else '🔴'} — {brk_fresh_note}; "
               f"(о) {'✅' if brk_used_ok else '🔴'} — {brk_used_note}", differ=True)

    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
