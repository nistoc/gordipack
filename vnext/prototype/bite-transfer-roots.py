# -*- coding: utf-8 -*-
r"""ПРИЁМКА КОРНЕЙ ПЕРЕНОСА: список механизмов для шаблона считается, а не пишется рукой.

КЛАСС НАЗВАЛ @COORD 10.08 (записка #3482), и лучше него не скажешь:
> механизм взят в тулкит, врезан и проверен — и ОСТАЛСЯ НЕВИДИМ ДЛЯ РАСКАТКИ,
> потому что никто не дописал имя в список.
Зависимости переносчик считал сам (with_deps), а КОРНИ знала только рука. Рукописный
список устаревает МОЛЧА и при этом выглядит полным — им нельзя ни ошибиться громко,
ни заметить пропажу.

⚡ ЗАМЕР ПОДТВЕРДИЛ КЛАСС В ПЕРВУЮ ЖЕ МИНУТУ: посчитанные корни нашли `unsaved.py` —
живой механизм, которого рукописный список не знал и который в шаблон не ехал.

⛔ Живой базы не касается: работает с каталогами и временной копией.
⛔ Число случаев печатает прогон.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = [mezo_paths.template_root(), HERE.parent.parent / "gordipack"]
PACK = next((p for p in CANDIDATES if (p / "vnext" / "tools" / "sync-to-template.py").exists()), None)
if PACK is None:
    print(f"⛔ ПЕРЕНОСЧИКА НЕТ: {[str(c) for c in CANDIDATES]} — отказ мерить, не «чисто»")
    sys.exit(2)

spec = importlib.util.spec_from_file_location("sync_under_test",
                                              PACK / "vnext" / "tools" / "sync-to-template.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand():
    """Игрушечная пара «живой контур ↔ шаблон» — предмет строится, а не берётся живой."""
    tmp = Path(tempfile.mkdtemp(prefix="bite-roots-"))
    live, tpl = tmp / "live", tmp / "tpl"
    live.mkdir(), tpl.mkdir()
    (live / "guard-all.py").write_text(
        'import helper\nsub("new-guard.py")\n', encoding="utf-8")
    (live / "helper.py").write_text("x = 1\n", encoding="utf-8")
    (live / "new-guard.py").write_text("print('я механизм')\n", encoding="utf-8")
    (live / "orphan.py").write_text("print('меня никто не зовёт')\n", encoding="utf-8")
    (tpl / "guard-all.py").write_text("старая копия\n", encoding="utf-8")
    return tmp, live, tpl


def main() -> int:
    ok = True
    tmp, live, tpl = stand()
    try:
        new, shared = S.roots(live, tpl)

        # ① МЕХАНИЗМ, КОТОРЫЙ ЗОВЁТ ТОЧКА ВХОДА, ПОПАДАЕТ В ПЕРЕНОС САМ
        ok &= case("① новый механизм, позванный из точки входа, попадает в корни САМ",
                   "new-guard.py" in new,
                   f"корни: {new}; именно этого не делал рукописный список", differ=True)

        # ② ЗАВИСИМОСТЬ ПО ИМПОРТУ ТОЖЕ ДОСТИЖИМА
        ok &= case("② импортируемый модуль достижим (замыкание, а не файл)",
                   "helper.py" in new,
                   "половина связки у потребителя хуже, чем ничего: выглядит доехавшей",
                   differ=True)

        # ③ ВСТРЕЧНЫЙ: файл, которого НИКТО не зовёт, в перенос НЕ едет.
        #    Иначе это зеркало, а зеркало ради зелёного сторожа мы уже оплатили 09.08:
        #    девять перенесённых инструментов у потребителя не работали вовсе.
        ok &= case("③ файл, которого никто не зовёт, в корни НЕ попадает (встречный к ①)",
                   "orphan.py" not in new,
                   "перенос ≠ зеркало: достижимость и есть «механизм нужен роли»", differ=True)

        # ④ ОБЩЕЕ СЧИТАЕТСЯ ПЕРЕСЕЧЕНИЕМ, А НЕ ПЕРЕЧИСЛЯЕТСЯ
        ok &= case("④ общие файлы — пересечение имён, а не список",
                   shared == ["guard-all.py"],
                   f"общие: {shared}", differ=True)

        # ⑤ ЖИВОЙ ЗАМЕР: на настоящей паре корни считаются и не пусты.
        real_new, real_shared = S.roots(S.LIVE, S.TEMPLATE)
        ok &= case("⑤ на живой паре замер работает и что-то находит",
                   len(real_shared) > 10,
                   f"живых корней: новых {len(real_new)} · общих {len(real_shared)}"
                   f"{' · новое: ' + ', '.join(real_new) if real_new else ''}")

        # ⑥ ГРАНИЦА НАЗВАНА В КОДЕ, А НЕ ТОЛЬКО В ГОЛОВЕ: замер видит вызовы по ИМЕНИ
        #    файла; механизм, позванный вычисленным именем, он не увидит.
        src = (PACK / "vnext" / "tools" / "sync-to-template.py").read_text(encoding="utf-8")
        ok &= case("⑥ граница замера названа в самом инструменте",
                   "вычисленным именем" in src,
                   "молчащая граница превращает «не нашли» в «этого нет»")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{'✅ КОРНИ ПЕРЕНОСА ПРИНЯТЫ' if ok else '🔴 НЕ ПРИНЯТЫ'} — случаев {CASES}, "
          f"различающих {DIFFER}; ① и ③ — встречная пара")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
