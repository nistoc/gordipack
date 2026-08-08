#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА сторожа «обязательный довод потерян в вызове».

Сторож зелен на живом коде с первого прогона — и это ровно повод НЕ верить ему на слово:
зелёное по ложной причине выглядит точно так же, как заслуженное.

Случаи (различающий = сторож обязан ответить ИНАЧЕ, а не одинаково):
  ① довод ПОТЕРЯН → находка      контроль: сторож вообще умеет краснеть
  ② довод по ИМЕНИ → молчит                              РАЗЛИЧАЮЩИЙ
  ③ довод ПОЗИЦИОННО (по сигнатуре) → молчит             РАЗЛИЧАЮЩИЙ
  ④ ЗАГЛУШКА рядом не перекрывает настоящую сигнатуру    РАЗЛИЧАЮЩИЙ
  ⑤ **kwargs → не судим                                  РАЗЛИЧАЮЩИЙ
  ⑥ сигнатуры нет вовсе → НЕ СУДИМ, а не обвиняем        РАЗЛИЧАЮЩИЙ
  ⑦ под надзором ноль вызовов → ложный ноль назван вслух РАЗЛИЧАЮЩИЙ

⛔ Живого кода не трогает: свои файлы в песочнице.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).with_name("guard-argument-dropped.py")

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def run(d):
    r = subprocess.run([sys.executable, str(GUARD), "--dir", d],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or "")


def sandbox(files: dict) -> str:
    d = tempfile.mkdtemp(prefix="bite-argdrop-")
    for name, text in files.items():
        Path(d, name).write_text(text, encoding="utf-8")
    return d


DEF = "def machine_block(db_path, role):\n    return []\n"


def main() -> int:
    if not GUARD.exists():
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {GUARD} не найден — приёмке нечего испытывать.")
    ok = True

    out = run(sandbox({"a.py": DEF + "\nmachine_block(db)\n"}))
    ok &= case("① довод потерян — находка есть (сторож умеет краснеть)",
               "ДОВОД НЕ ПЕРЕДАН — 1" in out, "вызов без роли обязан быть назван")

    out = run(sandbox({"a.py": DEF + "\nmachine_block(db, role=r)\n"}))
    ok &= case("② довод по ИМЕНИ — молчит",
               "во всех прямых вызовах довод передан" in out,
               "именованная форма законна и обвинять её нельзя", differ=True)

    out = run(sandbox({"a.py": DEF + "\nmachine_block(db, r)\n"}))
    ok &= case("③ довод ПОЗИЦИОННО — молчит, позиция взята из сигнатуры",
               "во всех прямых вызовах довод передан" in out,
               "магическое число вместо сигнатуры дало бы ложное красное — так и было",
               differ=True)

    stub = ("try:\n    from machine_layer import machine_block\n"
            "except Exception:\n    def machine_block(*_a, **_k):\n        return []\n")
    out = run(sandbox({"lib.py": DEF, "app.py": stub + "\nmachine_block(db, r)\n"}))
    ok &= case("④ ЗАГЛУШКА рядом не перекрывает настоящую сигнатуру",
               "во всех прямых вызовах довод передан" in out,
               "у запасного определения доводов нет; меря по нему, сторож обвинил "
               "пять ВЕРНЫХ вызовов — этот случай сторожит починку", differ=True)

    out = run(sandbox({"a.py": DEF + "\nmachine_block(db, **kw)\n"}))
    ok &= case("⑤ **kwargs — не судим",
               "во всех прямых вызовах довод передан" in out,
               "довод мог прийти в словаре; обвинять вслепую хуже, чем пропустить",
               differ=True)

    out = run(sandbox({"a.py": "machine_block(db)\n"}))     # определения НЕТ
    ok &= case("⑥ сигнатуры нет вовсе — НЕ СУДИМ, а не обвиняем",
               "ДОВОД НЕ ПЕРЕДАН" not in out,
               "без контракта неизвестно, где стоит довод: молчание честнее догадки",
               differ=True)

    out = run(sandbox({"a.py": "print('тут нет ни одного вызова под надзором')\n"}))
    ok &= case("⑦ под надзором НОЛЬ вызовов — ложный ноль назван вслух",
               "НЕ ОКАЗАЛОСЬ НИ ОДНОГО ВЫЗОВА" in out,
               "«чисто» без единой проверенной точки — это не чистота, а тишина",
               differ=True)

    print()
    print(f"{'✅ СТОРОЖ ПРИНЯТ' if ok else '🔴 СТОРОЖ НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
