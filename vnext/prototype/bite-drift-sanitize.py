#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА сверки живого с образцом: обезличенное имя репозитория — не расхождение
(карточка #244).

🎯 КЛАСС. Образец обезличивает «<КОНТУР>\<репозиторий>», сверка знала только заглушку
корня — и файл, отличавшийся РОВНО правильным обезличиванием имени репозитория, больше
суток висел «расходится». Постоянный жёлтый, который нельзя погасить работой, учит
пролистывать сверку целиком — и настоящее расхождение в ней потом не заметят.
Вторая половина: «46753б ≠ 46767б» не говорит, правка это или окончания строк; разбор
одного безобидного различия занял 15 минут руками.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: настоящая правка одной строки → «РАСХОДЯТСЯ»
  ② отличие ТОЛЬКО обезличенным именем репозитория → «обезличено», НЕ расходится   РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ к ②: имя, которого НЕТ на диске, → остаётся расходящимся            РАЗЛИЧАЮЩИЙ
  ④ при расхождении названо ЧИСЛО строк по существу, а не только байты             РАЗЛИЧАЮЩИЙ
  ⑤ разные окончания строк при том же тексте → НЕ «расходятся»                     РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: контейнер, репозитории и обе копии — во временном каталоге
(сверке контейнер называется переменной MEZO_CONTAINER — тем же входом, что у всех путей).
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

СВЕРКА = mezo_paths.live_scripts() / "guard-scripts-drift.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def main() -> int:
    ok = True
    tmp = mezo_stand.new("bite-drift-sanitize-")
    try:
        контейнер = tmp / "контейнер"
        (контейнер / "alpha-repo" / ".git").mkdir(parents=True)   # репозиторий НА ДИСКЕ
        (контейнер / ".mezosync").mkdir(parents=True)
        rt, tpl = tmp / "rt", tmp / "tpl"
        rt.mkdir(), tpl.mkdir()

        КОНТ = str(контейнер)

        # ① настоящая правка — обязана остаться расхождением
        (rt / "edited.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
        (tpl / "edited.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
        # ② отличие только обезличенным именем репозитория, ЛЕЖАЩЕГО на диске
        (rt / "sanitized.py").write_text(
            f"# пример: git -C {КОНТ}\\alpha-repo log\n", encoding="utf-8")
        (tpl / "sanitized.py").write_text(
            "# пример: git -C <КОНТУР>\\<репозиторий> log\n", encoding="utf-8")
        # ③ имя, которого на диске НЕТ, — заглушкой не считается
        (rt / "ghost.py").write_text(
            f"# пример: git -C {КОНТ}\\beta-repo log\n", encoding="utf-8")
        (tpl / "ghost.py").write_text(
            "# пример: git -C <КОНТУР>\\<репозиторий> log\n", encoding="utf-8")
        # ⑤ тот же текст, другие окончания строк
        (rt / "crlf.py").write_bytes(b"x = 1\r\ny = 2\r\n")
        (tpl / "crlf.py").write_bytes(b"x = 1\ny = 2\n")

        env = dict(os.environ, MEZO_CONTAINER=str(контейнер))
        r = subprocess.run(
            [sys.executable, str(СВЕРКА), "--vnext-runtime", str(rt),
             "--vnext-template", str(tpl)],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        out = (r.stdout or "") + (r.stderr or "")

        ok &= case("① контроль: настоящая правка — «РАСХОДЯТСЯ», и файл назван",
                   "РАСХОДЯТСЯ" in out and "edited.py" in out,
                   "без него всё дальнейшее могло бы означать ослепшую сверку")
        ok &= case("② обезличенное имя репозитория С ДИСКА — не расхождение",
                   "sanitized.py" not in out.split("РАСХОДЯТСЯ")[-1]
                   and "обезличено" in out,
                   "постоянный жёлтый, который нельзя погасить работой, учит пролистывать "
                   "сверку целиком", differ=True)
        ok &= case("③ ВСТРЕЧНЫЙ: имени нет на диске — файл ОСТАЁТСЯ расходящимся",
                   "ghost.py" in out,
                   "иначе заглушка «съедала» бы любое имя, и настоящая правка примера "
                   "прошла бы как обезличивание", differ=True)
        ok &= case("④ при расхождении названо число строк по существу",
                   "строк по существу: 1" in out,
                   "«46753б ≠ 46767б» не говорит, правка это или окончания строк; "
                   "различий больше, чем строк в файле, — признак кривой сверки",
                   differ=True)
        ok &= case("⑤ разные окончания строк при том же тексте — не «расходятся»",
                   "crlf.py" not in out.split("РАСХОДЯТСЯ")[-1],
                   "сверка байтов — не сверка содержимого (правило bytes-are-not-content)",
                   differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ СВЕРКА С ОБРАЗЦОМ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
