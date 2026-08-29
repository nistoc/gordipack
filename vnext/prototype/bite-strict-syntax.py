#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bite-strict-syntax.py — приёмка проверки синтаксических предупреждений (карточка #418).

Случаи (различающий = проверка обязана ответить ИНАЧЕ, а не одинаково):
  ① чистый стенд → тихо, код 0, число файлов и длительность напечатаны
  ② подсажено SyntaxWarning (голый обратный слеш в строке) → красный ПОИМЁННО   РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ: та же строка сырой формой r"…" → тихо                            РАЗЛИЧАЮЩИЙ
  ④ подсажен SyntaxError → красный: не компилируется — хуже предупреждения      РАЗЛИЧАЮЩИЙ
  ⑤ ОБРАТНЫЙ ХОД: в копии проверки фильтр «error» ослеплён до «ignore» —
     подсадка ② перестаёт краснеть ⇒ красноту даёт ИМЕННО строгий фильтр        РАЗЛИЧАЮЩИЙ
  ⑥ пустой стенд → «0 из 0» НЕ зелёный                                          РАЗЛИЧАЮЩИЙ
  ⑦ живые каталоги: настоящий прогон — числа вслух (критерий ② карточки #418:
     «на чистом дереве молчит, и длительность названа замером»)

⛔ Живого контура не касается: подсадки во временном каталоге, живые каталоги только читаются.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402

TOOL = Path(__file__).resolve().parent / "guard-strict-syntax.py"
CASES = DIFFER = 0
ok = True


def case(title, cond, detail, differ=False):
    global CASES, DIFFER, ok
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if cond else '🔴'} {title}")
    print(f"   {detail}")
    ok &= cond
    return cond


def run(tool, *dirs):
    r = subprocess.run([sys.executable, str(tool), "--dirs", *map(str, dirs)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: проверки нет — {TOOL}")
    d = mezo_stand.new("bite-syntax-")
    стенд = d / "tools"
    стенд.mkdir()
    (стенд / "чистый.py").write_text('print("проверок 24")\n', encoding="utf-8")

    # ── ① чистый стенд ─────────────────────────────────────────────────────────
    out, rc = run(TOOL, стенд)
    case("① чистый стенд → тихо, числа напечатаны",
         rc == 0 and "файлов 1" in out and " с" in out,
         f"код {rc} — без этого краснота дальше ничего не доказывает")

    # ── ② SyntaxWarning подсажен ───────────────────────────────────────────────
    # подсадка собирается через chr(92): голый обратный слеш обязан родиться
    # у ИСПЫТУЕМОГО файла, а не жить строкой в самой приёмке — её судит та же проверка
    (стенд / "zzprobe_warn.py").write_text('s = "' + chr(92) + 'd"' + chr(10), encoding="utf-8")
    out, rc = run(TOOL, стенд)
    case("② голый обратный слеш в строке → красный ПОИМЁННО",
         rc == 1 and "zzprobe_warn.py:1" in out and "SyntaxWarning" in out,
         "ровно класс карточки #363: прежде такой файл жил, пока кто-то не наткнётся глазами",
         differ=True)

    # ── ③ встречный: сырая форма ───────────────────────────────────────────────
    (стенд / "zzprobe_warn.py").write_text('s = r"' + chr(92) + 'd"' + chr(10), encoding="utf-8")
    out, rc = run(TOOL, стенд)
    case("③ ВСТРЕЧНЫЙ: та же строка сырой формой r«…» → тихо",
         rc == 0 and "zzprobe_warn" not in out,
         "иначе проверка красила бы ЗАКОННУЮ запись образцов поиска по всему контуру",
         differ=True)
    (стенд / "zzprobe_warn.py").unlink()

    # ── ④ SyntaxError ──────────────────────────────────────────────────────────
    (стенд / "zzprobe_err.py").write_text("def f(:\n", encoding="utf-8")
    out, rc = run(TOOL, стенд)
    case("④ SyntaxError → красный: некомпилируемый инструмент хуже предупреждения",
         rc == 1 and "zzprobe_err.py" in out and "SyntaxError" in out,
         "молчание о нём значило бы «проверка синтаксиса пропускает сломанный синтаксис»",
         differ=True)
    (стенд / "zzprobe_err.py").unlink()

    # ── ⑤ обратный ход: фильтр ослеплён ────────────────────────────────────────
    слепая = d / "guard-blind.py"
    src = TOOL.read_text(encoding="utf-8")
    якорь = 'warnings.simplefilter("error", SyntaxWarning)'
    if src.count(якорь) != 1:
        sys.exit(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь фильтра найден {src.count(якорь)} раз")
    слепая.write_text(src.replace(якорь, 'warnings.simplefilter("ignore", SyntaxWarning)'),
                      encoding="utf-8")
    (стенд / "zzprobe_warn.py").write_text('s = "' + chr(92) + 'd"' + chr(10), encoding="utf-8")
    out_blind, rc_blind = run(слепая, стенд)
    out_live, rc_live = run(TOOL, стенд)
    case("⑤ ОБРАТНЫЙ ХОД: фильтр ослеплён → та же подсадка перестаёт краснеть",
         rc_blind == 0 and rc_live == 1,
         f"слепая копия код {rc_blind}, живая {rc_live} — разница и есть строгий фильтр; "
         "сойдись они — случай ② краснел бы по другой причине", differ=True)
    (стенд / "zzprobe_warn.py").unlink()

    # ── ⑥ пустой стенд ─────────────────────────────────────────────────────────
    пусто = d / "пусто"
    пусто.mkdir()
    out, rc = run(TOOL, пусто)
    case("⑥ пустой каталог → «0 из 0» НЕ зелёный",
         rc == 1 and "НОЛЬ" in out,
         "зелёное на нуле файлов означало бы «проверено и чисто» там, где не проверено ничего",
         differ=True)

    # ── ⑦ живые каталоги — настоящий прогон, числа вслух ───────────────────────
    r = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out_live_dirs = (r.stdout or "") + (r.stderr or "")
    case("⑦ живые каталоги: чисто, и длительность названа числом",
         r.returncode == 0 and "файлов" in out_live_dirs,
         out_live_dirs.strip().splitlines()[0] if out_live_dirs.strip() else "(пусто)")

    print()
    print(f"{'✅ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
