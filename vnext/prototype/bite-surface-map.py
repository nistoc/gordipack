# -*- coding: utf-8 -*-
"""ПРИЁМКА карты «поверхность → сторож» (map-surface-guards.py, заход 4 ⑥).

Главное свойство: пустая клетка ВИДНА строкой, расхождение карты с машинными
объявлениями сторожей — красное В ОБЕ СТОРОНЫ, а осознанное «не сужу» пустой
клеткой не считается.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPTOOL = HERE / "map-surface-guards.py"

GUARDS = ["guard-printed-forms.py", "guard-rule-expiry.py", "check-rule-basis.py",
          "guard-launcher-forms.py", "bite-plain-words.py", "check-false-signature.py",
          "measure-docs-retired.py", "guard-machine-paths.py", "guard-skills-fresh.py",
          # приёмки проверок — их PLANTS сверяются картой (заход 4 ⑦)
          "bite-printed-forms-sources.py", "bite-rule-expiry.py", "bite-rule-basis.py",
          "bite-launcher-forms.py", "bite-false-signature.py", "bite-docs-retired.py",
          "bite-machine-paths.py", "bite-skills-fresh.py"]

CASES, OK = 0, True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")


def run(tools):
    r = subprocess.run([sys.executable, str(MAPTOOL), "--tools", str(tools)],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def fresh_stand(tmp, name):
    d = Path(tmp) / name
    d.mkdir()
    for g in GUARDS:
        shutil.copyfile(HERE / g, d / g)
    return d


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-smap-")

    out, code = run(HERE)
    case("① живой прогон: пустые клетки ПЕЧАТАЮТСЯ строкой, красных 0",
         code == 0 and out.count("БЕЗ ПРОВЕРКИ") >= 2 and "красных 0" in out,
         "пустая клетка — строка, а не отсутствие строки")

    case("④ «не сужу: причина» пустой клеткой НЕ считается",
         "не сужу" in out and "пустых 2" in out,
         "осознанный отказ с причиной — не долг; долг — молчание")

    d = fresh_stand(tmp, "extra")
    g = d / "guard-rule-expiry.py"
    g.write_text(g.read_text(encoding="utf-8").replace(
        "# SURFACES: rules", "# SURFACES: rules ghost-surface"), encoding="utf-8")
    out, code = run(d)
    case("② проверка объявила поверхность, которой нет в карте → красное поимённо",
         code == 1 and "ghost-surface" in out and "guard-rule-expiry.py" in out)

    d = fresh_stand(tmp, "narrow")
    g = d / "guard-launcher-forms.py"
    g.write_text(g.read_text(encoding="utf-8").replace(
        "# SURFACES: phoenix", "# SURFACES:  "), encoding="utf-8")
    out, code = run(d)
    case("③ карта приписывает проверке поверхность, а та её НЕ объявляет → красное",
         code == 1 and "НЕ объявляет" in out and "guard-launcher-forms.py" in out,
         "карта, отставшая от проверки, обязана краснеть, а не молчать")

    d = fresh_stand(tmp, "gone")
    (d / "guard-skills-fresh.py").unlink()
    out, code = run(d)
    case("⑤ файла проверки нет → красное «имя протухло», клетка не лжёт о покрытии",
         code == 1 and "файла проверки НЕТ" in out and "guard-skills-fresh.py" in out)

    d = fresh_stand(tmp, "undecl")
    g = d / "check-rule-basis.py"
    g.write_text(re.sub(r"^# SURFACES:.*\n", "", g.read_text(encoding="utf-8"),
                        count=1, flags=re.M), encoding="utf-8")
    out, code = run(d)
    case("⑥ проверка БЕЗ строки SURFACES — названа счётом, не красное",
         code == 0 and "без машинного объявления" in out and "check-rule-basis.py" in out,
         "отсутствие контракта — не дефект; молчать о нём — дефект")

    # ⑦а: у приёмки урезан PLANTS — источник её проверки остаётся БЕЗ подсадки → красное
    d = fresh_stand(tmp, "plant-cut")
    g = d / "bite-printed-forms-sources.py"
    g.write_text(g.read_text(encoding="utf-8").replace(
        "# PLANTS: canon rules tasks printed vitrina",
        "# PLANTS: canon rules tasks printed"), encoding="utf-8")
    out, code = run(d)
    case("⑦а источник без подсадки в приёмке → красное «зелёное не доказано»",
         code == 1 and "БЕЗ ПОДСАДКИ" in out and "vitrina" in out,
         "ровно так жило зелёное по слепоте: проверка объявляла, приёмка не подсаживала")

    # ⑦б: у приёмки нет строки PLANTS вовсе → красное, а не пропуск
    d = fresh_stand(tmp, "plant-none")
    g = d / "bite-rule-expiry.py"
    g.write_text(re.sub(r"^# PLANTS:.*\n", "", g.read_text(encoding="utf-8"),
                        count=1, flags=re.M), encoding="utf-8")
    out, code = run(d)
    case("⑦б приёмка без строки PLANTS → красное «что доказывает — не сказано»",
         code == 1 and "не объявляет подсадок" in out and "bite-rule-expiry.py" in out)

    print()
    print(f"{'✅ КАРТА ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}")
    if OK:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"📂 стенд сохранён: {tmp}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
