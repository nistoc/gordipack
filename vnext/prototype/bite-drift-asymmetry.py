# -*- coding: utf-8 -*-
r"""ПРИЁМКА: guard-scripts-drift судит пару копий АСИММЕТРИЧНО.

Повод — замер @PROTO (записка #3471). Моя прошлая редакция кричала на ОБЕ стороны одинаково,
и это привело к настоящей поломке: увидев красное, он перенёс 14 файлов из шаблона в рабочий
каталог — девять из них там не работают вовсе. Откатил сам.
🎯 Зеркало ради молчания сторожа кладёт потребителю падающие инструменты, и сторож доволен.

ВЕРНОЕ СВОЙСТВО:
    🔴 есть у ПОТРЕБИТЕЛЯ, нет в ШАБЛОНЕ → при раскатке НЕ ДОЕДЕТ
    🔴 есть в обоих, содержимое разное   → дрейф
    ✅ есть только в ШАБЛОНЕ             → НОРМА (шаблон полнее по построению)

⚠️ Приёмка гоняет сторожа ПО ВРЕМЕННЫМ каталогам — это стало возможно только после того,
как пути стали аргументами. До того его «зелёное» приходилось принимать на веру: проверка,
которого нельзя натравить на копию, нельзя и проверить.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

GUARD = str(mezo_paths.live_scripts() / "guard-scripts-drift.py")
cases, bad = [], 0


def check(name, ok, detail=""):
    global bad
    cases.append((name, ok, detail))
    if not ok:
        bad += 1


def run(rt, tpl):
    """Сторож на ВРЕМЕННЫХ каталогах. Первую пару (рантайм↔репо) уводим туда же,
    чтобы приёмка не трогала ни живой тулкит, ни репозиторий-бэкап."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="drift-run-"))
    (tmp / "rt").mkdir()
    (tmp / "repo").mkdir()
    (tmp / "rt" / "x.py").write_text("# одинаково\n", encoding="utf-8")
    (tmp / "repo" / "x.py").write_text("# одинаково\n", encoding="utf-8")
    r = subprocess.run([sys.executable, GUARD,
                        "--runtime", str(tmp / "rt"), "--repo", str(tmp / "repo"),
                        "--vnext-runtime", str(rt), "--vnext-template", str(tpl)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    shutil.rmtree(tmp, ignore_errors=True)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def pair(consumer_files, template_files):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="drift-pair-"))
    rt, tpl = tmp / "consumer", tmp / "template"
    rt.mkdir()
    tpl.mkdir()
    for name, body in consumer_files.items():
        (rt / name).write_text(body, encoding="utf-8")
    for name, body in template_files.items():
        (tpl / name).write_text(body, encoding="utf-8")
    return tmp, rt, tpl


# ① 🔴 ЕСТЬ У ПОТРЕБИТЕЛЯ, НЕТ В ШАБЛОНЕ — «не доедет»
tmp, rt, tpl = pair({"a.py": "1\n", "своя.py": "2\n"}, {"a.py": "1\n"})
out, _ = run(rt, tpl)
check("① файл потребителя, которого нет в шаблоне — НЕ ДОЕДЕТ, назван поимённо",
      "НЕ ДОЕДЕТ" in out and "своя.py" in out, out.strip()[-200:])
shutil.rmtree(tmp, ignore_errors=True)

# ② ✅ ВСТРЕЧНЫЙ: ТОЛЬКО В ШАБЛОНЕ — НОРМА, и это главный случай правки
tmp, rt, tpl = pair({"a.py": "1\n"}, {"a.py": "1\n", "лишняя.py": "3\n"})
out, _ = run(rt, tpl)
check("② файл только в шаблоне — НОРМА, а не дефект (встречный к ①)",
      "НЕ ДОЕДЕТ" not in out and "НОРМА" in out, out.strip()[-200:])
check("② и такой файл НЕ назван виновником поимённо",
      "🔴 лишняя.py" not in out, out.strip()[-200:])
shutil.rmtree(tmp, ignore_errors=True)

# ③ 🔴 ДРЕЙФ содержимого — по-прежнему красное
tmp, rt, tpl = pair({"a.py": "СТАРОЕ\n"}, {"a.py": "НОВОЕ\n"})
out, _ = run(rt, tpl)
check("③ разное содержимое общего файла — ДРЕЙФ", "РАСХОДЯТСЯ" in out, out.strip()[-200:])
shutil.rmtree(tmp, ignore_errors=True)

# ④ ✅ полное совпадение — тихо, но с НАЗВАННОЙ границей
tmp, rt, tpl = pair({"a.py": "1\n"}, {"a.py": "1\n"})
out, _ = run(rt, tpl)
check("④ совпадение — зелёное", "не доедет — ноль" in out, out.strip()[-200:])
check("④ зелёное САМО называет свою границу (файлы ≠ работоспособность)",
      "ГРАНИЦА" in out and "ПРОГОНОМ" in out, out.strip()[-200:])
shutil.rmtree(tmp, ignore_errors=True)

# ⑤ отказ мерить: каталога нет — это не «совпадает»
tmp, rt, tpl = pair({"a.py": "1\n"}, {"a.py": "1\n"})
out, _ = run(rt, tpl / "нет-такого")
check("⑤ отсутствующий каталог — сверка НЕ ВЫПОЛНЕНА, а не «чисто»",
      "НЕ ВЫПОЛНЕНА" in out, out.strip()[-200:])
shutil.rmtree(tmp, ignore_errors=True)

print("🔬 ПРИЁМКА: асимметрия пары копий в guard-scripts-drift")
for name, ok, detail in cases:
    print(f"   {'✅' if ok else '🔴'} {name}" + (f"   ← {detail}" if detail and not ok else ""))
print(f"   ИТОГ: {len(cases) - bad}/{len(cases)}")
sys.exit(1 if bad else 0)
