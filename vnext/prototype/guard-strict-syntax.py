#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""guard-strict-syntax.py — SyntaxWarning И SyntaxError в инструментах контура.

    python <КОНТУР>/vnext-tools/guard-strict-syntax.py
    python <КОНТУР>/vnext-tools/guard-strict-syntax.py --dirs <каталог> [<каталог>…]

ЗАЧЕМ (карточка #418, замер TAXO 29.08). Появление SyntaxWarning в инструменте не
стерегла НИ ОДНА проверка: единственное упоминание в контуре — ПОДАВЛЕНИЕ чужого шума
в guard-machine-paths.py (законное: тот разбирает чужой код). Довод карточки #363 —
«постоянный шум приучает читать мимо предупреждений» — одинаково верен и для следующего
предупреждения, а его никто не заметил бы, пока роль случайно не увидит его в своей
стенограмме. Замер перед включением (29.08 20:27 UTC): 205 файлов · накопленного шума
0 · 0.38 с ⇒ включается ЗЕЛЁНЫМ, а не вечно-красным.

КАК СУДИТ: каждый *.py компилируется В ЭТОМ процессе с фильтром «SyntaxWarning —
ошибка». Находки поимённо (файл:строка и текст), при них код 1. SyntaxError судится
той же меркой: файл, который не компилируется, ещё хуже файла с предупреждением.

ГРАНИЦА ВСЛУХ: судятся ТОЛЬКО каталоги инструментов контура (по умолчанию scripts
и vnext-tools) — не чужой код и не памяти ролей. Подавление чужого шума в
guard-machine-paths.py:118 это правило НЕ трогает (критерий ③ карточки #418):
там глушится ЧУЖОЙ код при разборе, здесь судится СВОЙ при компиляции.

⛔ Живого контура не касается: только чтение файлов, ничего не пишет.
"""
import argparse
import sys
import time
import warnings
from pathlib import Path


def судить(каталоги):
    """→ (files, находки[], сек). Компиляция строгая, находки поимённо."""
    t0 = time.perf_counter()
    files, находки = 0, []
    for d in каталоги:
        d = Path(d)
        if not d.is_dir():
            находки.append(f"⛔ каталог не найден: {d} — это ОТКАЗ, не «чисто»")
            continue
        for p in sorted(d.glob("*.py")):
            files += 1
            src = p.read_text(encoding="utf-8", errors="replace")
            with warnings.catch_warnings():
                warnings.simplefilter("error", SyntaxWarning)
                try:
                    compile(src, str(p), "exec")
                    continue
                except SyntaxError as e:
                    lineno, msg = e.lineno, e.msg
            # Строгий фильтр поднимает SyntaxError и для НАСТОЯЩЕЙ ошибки, и для
            # предупреждения-возведённого-в-ошибку (замер 29.08 20:29 UTC). Происхождение
            # различается повторной компиляцией БЕЗ строгости: компилируется — это было
            # предупреждение; падает и так — ошибка синтаксиса.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    compile(src, str(p), "exec")
                вид = "SyntaxWarning"
            except SyntaxError:
                вид = "SyntaxError"
            находки.append(f"{p.name}:{lineno} {вид}: {msg}")
    return files, находки, time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="SyntaxWarning/SyntaxError в инструментах — строгая компиляция")
    ap.add_argument("--dirs", nargs="+", default=None,
                    help="каталоги для суда (по умолчанию scripts и vnext-tools контура)")
    a = ap.parse_args()
    if a.dirs:
        каталоги = [Path(d) for d in a.dirs]
    else:
        # mezo_paths тянется ЛЕНИВО: приёмка гоняет копию этой проверки в песочнице
        # с --dirs, и там помощника путей рядом нет — без ленивости копия мертва.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mezo_paths
        каталоги = [mezo_paths.live_scripts(), Path(__file__).resolve().parent]
    files, находки, сек = судить(каталоги)
    if находки:
        print(f"🔴 СИНТАКСИЧЕСКИЕ ПРЕДУПРЕЖДЕНИЯ В ИНСТРУМЕНТАХ: {len(находки)} "
              f"(файлов смотрено {files}, {сек:.2f} с)")
        for f in находки[:12]:
            print(f"   🔴 {f}")
        if len(находки) > 12:
            print(f"   … ещё {len(находки) - 12}")
        print("   👉 предупреждение читают один раз, потом читают МИМО — почини или "
              "перепиши строку явной формой (r'…', явное экранирование)")
        return 1
    print(f"✅ синтаксис инструментов чист: файлов {files}, предупреждений 0, {сек:.2f} с")
    if files == 0:
        # «0 из 0» — не чистота: судить было нечего, и это красный, а не зелёный
        print("⛔ файлов НОЛЬ — судить было нечего, «0 из 0» не означает «чисто»")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
