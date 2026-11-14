# -*- coding: utf-8 -*-
r"""ПРИЁМКА выбора испытуемой копии в общем наборе (bite-all.py --target).

Свойство: прогон по КОПИИ и прогон по ЖИВОМУ смотрят на РАЗНЫЕ механизмы, и перепутать их
нельзя. Доказывается нарочной поломкой копии — без неё «прогон по образцу» есть намерение,
а не механизм: он был бы неотличим от прогона по живому.

🪤 И главный случай ⑥ — оплаченный ошибкой постановки опыта. Первая поломка ломала механизм,
которого НЕ ЗОВЁТ НИКТО: набор напечатал «держится 36, сломано 0» при полностью убитом файле.
Вывод «выбор копии не работает» был бы НЕВЕРЕН — не работал мой опыт. Отсюда требование:
набор обязан САМ печатать границу — сколько механизмов он реально испытывает.

⛔ Живого контура не касается: копии строятся во временном каталоге.
⏱ Гоняет набор с --only на отдельных приёмках, а не целиком: предмет здесь — выбор копии.

🪤 17.10 (записка #5902, карточка #680): раскладка копии кладёт в стенд и соседние проверки
(<копия>/../vnext/prototype) — а случая на это не было. Опыт на копии ЖИВЫХ скриптов его бы
и не дал: в живом каталоге лежит своя guard-shift-end.py, save-phoenix.py находит её рядом
с собой, и прогон зелёный с соседями, без них и со сломанным соседом. Различает только копия,
разложенная как клон пакета: скрипты отдельно, соседи — в vnext/prototype (случаи ⑪–⑬).
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import mezo_paths  # пути машины выводятся, не впечатаны (#153)
import mezo_stand  # копия живой базы — ТОЛЬКО через snapshot_db (карточка #505/#659)

HERE = os.path.dirname(os.path.abspath(__file__))
BITE_ALL = os.path.join(HERE, "bite-all.py")
LIVE = str(mezo_paths.live_scripts())
# приёмки, которые ТОЧНО зовут механизм через резолвер (замер: script("read-messages.py"))
ONLY = "to-me-empty"
# приёмка, чьему испытуемому НУЖЕН контур (write-message.py зовёт container_root): без раскладки
# копии «файлы рядом» она отказывает «контейнер группы НЕ НАЙДЕН» — замер 14.10 на прежнем bite-all.py
ONLY_CONTOUR = "default-stamp"
# ⚖️ Зелёное здесь — «держится 1», а не код 0: отказ испытуемого эта приёмка отдаёт кодом 2, набор
# печатает его «не запустилась» и итог кодом 0 — на прежнем bite-all.py ⑧ «прошёл» бы по коду
GREEN_ONE = "держится 1 · сломано 0 · НЕ ПРОВЕРЕНО 0"
# приёмка, чьему испытуемому НУЖНЫ соседние проверки: save-phoenix.py ищет guard-shift-end.py
# через vnext_tool() — четвёртое место <стенд>/vnext/prototype. Без соседей шесть её случаев
# падают «файла нет» (замер 17.10: прошло 12 · провалилось 6)
ONLY_NEIGHBOURS = "shift-end"
NEIGHBOUR_BROKEN = "guard-shift-end.py"
# скрипты пакета — соседи этого каталога: <пакет>/scripts рядом с <пакет>/vnext/prototype
PACK_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")
NEIGHBOURS_LINE = "соседние проверки — копия"

CASES = 0
DIFFERENTIATING = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run(target=None, only=ONLY):
    cmd = [sys.executable, BITE_ALL, "--only", only]
    if target:
        cmd += ["--target", target]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def copy_scripts(tmp, name, break_files=()):
    # Копия строится КАК КОНТУР (.mezosync/scripts + база рядом), а не просто каталогом
    # скриптов: с 20.08 помощник путей отказывает ГРОМКО, если корень не находится, и
    # копия «файлы рядом» перестала быть испытуемой — падала целиком, ещё до предмета.
    # ⚖️ Стенд, не воспроизводящий раскладку, зелен ровно до тех пор, пока испытуемый
    # неразборчив; чинить надо стенд, а не возвращать инструменту снисходительность.
    корень = os.path.join(tmp, name, ".mezosync")
    dst = os.path.join(корень, "scripts")
    shutil.copytree(LIVE, dst)
    mezo_stand.snapshot_db(mezo_paths.live_db(), os.path.join(корень, "mezosync.db"))
    for f in break_files:
        with open(os.path.join(dst, f), "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.exit('НАРОЧНО СЛОМАН В КОПИИ')\n")
    return dst


def copy_flat(tmp, name, break_files=()):
    # Копия «файлы рядом» — как скрипты в клоне пакета: без .mezosync и без базы рядом
    # (находка PROTO, записка #5838: 29 приёмок прогона по клону мерить было нечем).
    dst = os.path.join(tmp, name, "scripts")
    shutil.copytree(LIVE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for f in break_files:
        with open(os.path.join(dst, f), "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.exit('НАРОЧНО СЛОМАН В КОПИИ')\n")
    return dst


def copy_pack_layout(tmp, name, neighbours=True, break_files=()):
    # Копия «как клон пакета»: <name>/scripts — скрипты пакета, <name>/vnext/prototype — соседние
    # проверки (копия этого каталога). Скрипты пакета, а не живые: в живом каталоге лежит своя
    # guard-shift-end.py, и с ней отсутствие соседей не видно (опыт 17.10).
    root = os.path.join(tmp, name)
    dst = os.path.join(root, "scripts")
    shutil.copytree(PACK_SCRIPTS, dst, ignore=shutil.ignore_patterns("__pycache__"))
    if neighbours:
        nb = os.path.join(root, "vnext", "prototype")
        shutil.copytree(HERE, nb, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "local.paths"))
        for f in break_files:
            with open(os.path.join(nb, f), "w", encoding="utf-8") as fh:
                fh.write("import sys\nsys.exit('НАРОЧНО СЛОМАН В КОПИИ')\n")
    return dst


def laid_stand(out):
    """Временный каталог, в котором набор разложил копию контуром (из его подписи), или None."""
    for line in out.splitlines():
        if "разложена во временном каталоге" in line:
            return line.split("разложена во временном каталоге", 1)[1].strip().rstrip(":")
    return None


def main() -> int:
    if not os.path.isdir(LIVE):
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет живого каталога {LIVE} — строить копии не из чего")
        return 1
    # 🪤 Карточка #723: с первой редакции (09.08) временный каталог не убирался никогда —
    #    ≈330 МБ на прогон, 17.10 их лежало 17 (5,4 ГБ). Убираем при ЛЮБОМ исходе: внутри только
    #    копии скриптов и базы, их строит сам прогон заново, осматривать нечего; стенды набора
    #    при провале приёмка убирает и так. Оставленный при провале копился бы до слова владельца.
    tmp = tempfile.mkdtemp(prefix="bite-target-sel-")
    try:
        ok = cases(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        print()
        print(f"🧹 временный каталог приёмки убран: {tmp}" if not os.path.exists(tmp)
              else f"⚠️ временный каталог приёмки убрать не удалось: {tmp}")
    print(f"✅ ВЫБОР КОПИИ ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 ВЫБОР КОПИИ НЕ ПРИНЯТ — числа из прогона по образцу нести нельзя")
    return 0 if ok else 1


def cases(tmp) -> bool:
    ok = True

    # ① ЦЕЛАЯ КОПИЯ — зелёное. Контроль: набор вообще умеет проходить по копии.
    whole = copy_scripts(tmp, "whole")
    out_whole, code_whole = run(whole)
    ok &= case("① целая копия — прогон зелёный (контроль: по копии вообще идём)",
               code_whole == 0 and "СЛОМАНО" not in out_whole,
               f"код {code_whole}; без этого случая краснота на сломанной ничего не значит")

    # ② НАРОЧНАЯ ПОЛОМКА КОПИИ — красное. Ломаем то, что набор ДЕЙСТВИТЕЛЬНО зовёт.
    broken = copy_scripts(tmp, "broken", break_files=("read-messages.py",))
    out_bad, code_bad = run(broken)
    ok &= case("② сломанный в копии механизм — прогон по копии КРАСНЕЕТ",
               code_bad == 1 and "СЛОМАНО" in out_bad,
               f"код {code_bad}; поломка копии обязана быть видна", differ=True)

    # ③ ВСТРЕЧНЫЙ и ГЛАВНЫЙ: та же поломка НЕ трогает прогон по живому.
    #    Без него нельзя утверждать, что копии РАЗНЫЕ, а не одна и та же.
    out_live, code_live = run(None)
    ok &= case("③ живой прогон при сломанной копии остаётся зелёным (встречный к ②)",
               code_live == 0 and "СЛОМАНО" not in out_live,
               "иначе доказано лишь «что-то покраснело», а не что копии различаются",
               differ=True)

    # ④ ПОДПИСЬ НАЗЫВАЕТ КОПИЮ И НЕ ЗАШИТА. Строка «испытан живой модуль» при работе
    #    по шаблону уже однажды соврала — подпись обязана СПРАШИВАТЬ.
    ok &= case("④ подпись называет ИМЕННО испытанную копию, а не общие слова",
               broken in out_bad and "ЖИВОЙ КОНТУР" in out_live and "ЖИВОЙ" not in out_bad,
               "путь копии печатается дословно; у живого прогона — своя пометка", differ=True)

    # ⑤ КОПИИ НЕТ ВОВСЕ — отказ мерить (код 2), не «зелено» и не «сломано».
    out_miss, code_miss = run(os.path.join(tmp, "нет-такого"))
    ok &= case("⑤ несуществующая копия — отказ мерить, отдельный код",
               code_miss == 2 and "НЕ ЗАПУСТИЛСЯ НАБОР" in out_miss,
               f"код {code_miss}; опечатка в пути обязана звучать иначе, чем чистота",
               differ=True)

    # ⑥ ГРАНИЦА НАБОРА ПЕЧАТАЕТСЯ. Оплачено ошибкой опыта: сломанный, но никем не
    #    вызываемый механизм оставляет прогон зелёным — и это ЗАКОННО. Незаконно молчать.
    unused = copy_scripts(tmp, "unused", break_files=("set-rule.py",))
    out_unused, code_unused = run(unused)
    ok &= case("⑥ поломка НИКЕМ не вызываемого механизма: зелёное, но граница названа",
               code_unused == 0 and "ГРАНИЦА НАБОРА" in out_unused
               and "испытано механизмов" in out_unused,
               "зелёное без границы читалось бы как «копия цела» — ложный ноль", differ=True)

    # ⑦ ВСТРЕЧНЫЙ к ⑥: у ЖИВОГО прогона границы копии нет — её печатать нечестно,
    #    живой контур и есть предмет, а не выборка из него.
    ok &= case("⑦ живой прогон не печатает границу копии (встречный к ⑥)",
               "ГРАНИЦА НАБОРА" not in out_live,
               "перенос чужой оговорки на другой случай — тоже способ соврать формой")

    # ⑧ КОПИЯ БЕЗ СВОЕГО КОНТУРА (как скрипты клона пакета) — набор раскладывает её контуром
    #    сам и меряет. До правки (записка #5838) испытуемые не находили контур, и набор красил
    #    «СЛОМАНО» то, что мерить было нечем. Зелёный прогон — убирает свой временный каталог.
    flat = copy_flat(tmp, "flat")
    out_flat, code_flat = run(flat, ONLY_CONTOUR)
    st_flat = laid_stand(out_flat)
    ok &= case("⑧ копия без контура — набор раскладывает её сам: прогон зелёный, каталог назван и убран",
               code_flat == 0 and GREEN_ONE in out_flat and st_flat is not None
               and flat in out_flat and not os.path.exists(st_flat),
               f"код {code_flat}; разложена в {st_flat}; после зелёного прогона каталог "
               f"{'убран' if st_flat and not os.path.exists(st_flat) else 'НЕ убран или не назван'}",
               differ=True)

    # ⑨ ВСТРЕЧНЫЙ к ⑧: раскладка несёт ИСПЫТУЕМЫЙ код, а не берёт его откуда-то ещё. Поломка
    #    в копии без контура обязана покраснеть — иначе ⑧ зелёный потому, что испытывает не то.
    flat_bad = copy_flat(tmp, "flat-broken", break_files=("write-message.py",))
    out_flat_bad, code_flat_bad = run(flat_bad, ONLY_CONTOUR)
    st_bad = laid_stand(out_flat_bad)
    ok &= case("⑨ сломанный механизм в копии без контура — прогон НЕ зелёный (встречный к ⑧)",
               GREEN_ONE not in out_flat_bad and st_bad is not None
               and ("СЛОМАНО" in out_flat_bad or "не запустилась" in out_flat_bad),
               f"код {code_flat_bad}; раскладка копирует испытуемое байт в байт — сломанный "
               "write-message.py эта приёмка называет отказом мерить (код 2), не «сломано»", differ=True)
    if st_bad:
        shutil.rmtree(st_bad, ignore_errors=True)   # сохранён набором для осмотра — здесь осматривать нечего

    # ⑩ ВСТРЕЧНЫЙ к ⑧: копия, уже лежащая контуром (①), не раскладывается заново — её
    #    собственная база и раскладка и есть предмет опыта.
    ok &= case("⑩ копия, лежащая контуром, не раскладывается (встречный к ⑧)",
               laid_stand(out_whole) is None and laid_stand(out_live) is None,
               "раскладка — только там, где своего контура нет", differ=True)

    # ⑪ КОПИЯ КАК КЛОН ПАКЕТА — раскладка несёт и СОСЕДНИЕ проверки: save-phoenix.py в стенде
    #    находит guard-shift-end.py в <стенд>/vnext/prototype. Без этого шесть случаев приёмки
    #    падали «файла нет» (разбор 17.10, bite-all.py::lay_out_contour).
    if not os.path.isdir(PACK_SCRIPTS):
        ok &= case("⑪ копия как клон пакета — раскладка несёт соседние проверки",
                   False, f"скриптов пакета рядом нет ({PACK_SCRIPTS}) — копию клона строить не из чего; "
                   "приёмка живёт в пакете и запускается из него", differ=True)
    else:
        pack = copy_pack_layout(tmp, "pack")
        pack_nb = os.path.join(os.path.dirname(pack), "vnext", "prototype")
        out_pack, code_pack = run(pack, ONLY_NEIGHBOURS)
        st_pack = laid_stand(out_pack)
        ok &= case("⑪ копия как клон пакета — раскладка несёт соседние проверки: прогон зелёный, "
                   "соседи названы, каталог убран",
                   code_pack == 0 and GREEN_ONE in out_pack and st_pack is not None
                   and f"{NEIGHBOURS_LINE} {pack_nb}" in out_pack and not os.path.exists(st_pack),
                   f"код {code_pack}; разложена в {st_pack}; строка «{NEIGHBOURS_LINE} …» "
                   f"{'есть' if NEIGHBOURS_LINE in out_pack else 'НЕТ'}", differ=True)

        # ⑫ ВСТРЕЧНЫЙ к ⑪: те же скрипты БЕЗ соседнего каталога — прогон НЕ зелёный. Без него ⑪
        #    зелёный мог бы оказаться по другой причине (так и вышло в опыте на живых скриптах).
        bare = copy_pack_layout(tmp, "pack-bare", neighbours=False)
        out_bare, code_bare = run(bare, ONLY_NEIGHBOURS)
        st_bare = laid_stand(out_bare)
        # 🪤 Пояснение говорит то, что видно, а не то, что ждали (замечание PROTO, записка #5917):
        #    прежнее «соседей нет» стояло и тогда, когда соседи легли в стенд из чужого места.
        #    Смотрим в стенд, если он ещё лежит. После ЗЕЛЁНОГО прогона набор убирает его сам —
        #    тогда смотреть некуда, и «соседей нет» было бы той же неправдой (поймано поломкой
        #    PROTO 17.10 22:07 UTC: прогон прошёл, а пояснение сказало «в стенде соседей нет»).
        #    🪤 Карточка #723 (поломка OPSSRE, записка #5951): набор молча клал в стенд СВОЙ каталог
        #    без guard-shift-end.py — прогон падал по другой причине, и ⑫ проходил: подмену было видно
        #    только в пояснении. Поэтому соседей в ещё лежащем стенде быть НЕ должно — это часть условия.
        green_bare = GREEN_ONE in out_bare
        nb_bare = os.path.join(st_bare, "vnext", "prototype") if st_bare else None
        nb_in_stand = bool(nb_bare) and os.path.isdir(nb_bare)
        if not st_bare:
            seen = "стенда в выводе нет — смотреть соседей негде"
        elif not os.path.isdir(st_bare):
            seen = "стенд уже убран набором — заглянуть в него нельзя"
        elif nb_in_stand:
            seen = f"в стенде соседи ЕСТЬ ({nb_bare}) — взяты не из копии"
        elif not green_bare:
            seen = f"в стенде соседей нет — save-phoenix.py не находит {NEIGHBOUR_BROKEN}"
        else:
            seen = "в стенде соседей нет"
        ok &= case("⑫ клон без соседнего каталога — прогон НЕ зелёный, соседей в стенде нет (встречный к ⑪)",
                   not green_bare and "СЛОМАНО" in out_bare and st_bare is not None
                   and NEIGHBOURS_LINE not in out_bare and not nb_in_stand,
                   f"код {code_bare}; в копии соседнего каталога нет; {seen}"
                   f"; строка «{NEIGHBOURS_LINE} …» {'есть' if NEIGHBOURS_LINE in out_bare else 'НЕТ'}"
                   f": прогон {'ПРОШЁЛ — соседей в копии нет, значит, они взяты не из неё' if green_bare else 'НЕ прошёл, это видно'}",
                   differ=True)
        if st_bare:
            shutil.rmtree(st_bare, ignore_errors=True)   # сохранён набором для осмотра — здесь осматривать нечего

        # ⑬ ВСТРЕЧНЫЙ к ⑪: соседи берутся ИЗ КОПИИ, а не откуда-то ещё. Сломанный в копии сосед
        #    обязан провалить прогон — иначе стенд нашёл бы целую проверку в другом месте.
        nb_bad = copy_pack_layout(tmp, "pack-nb-broken", break_files=(NEIGHBOUR_BROKEN,))
        out_nb_bad, code_nb_bad = run(nb_bad, ONLY_NEIGHBOURS)
        st_nb_bad = laid_stand(out_nb_bad)
        ok &= case("⑬ сломанный сосед в копии — прогон НЕ зелёный (встречный к ⑪)",
                   GREEN_ONE not in out_nb_bad and "СЛОМАНО" in out_nb_bad and st_nb_bad is not None
                   and NEIGHBOURS_LINE in out_nb_bad,
                   f"код {code_nb_bad}; строка «{NEIGHBOURS_LINE} …» "
                   f"{'есть' if NEIGHBOURS_LINE in out_nb_bad else 'НЕТ'}; поломка {NEIGHBOUR_BROKEN} в "
                   f"<копия>/vnext/prototype {'дошла' if GREEN_ONE not in out_nb_bad else 'НЕ дошла'} до испытуемого",
                   differ=True)
        if st_nb_bad:
            shutil.rmtree(st_nb_bad, ignore_errors=True)

    # критерий ④ карточки #682 — разбор исходников, а не поведение набора
    ok &= tested_choice_cases()

    return ok


# ═══ КРИТЕРИЙ ④ КАРТОЧКИ #682: НИКТО НЕ БЕРЁТ ИСПЫТУЕМОЕ МИМО ОБЩЕГО ВЫБОРА ═══════════════════
# Прежние случаи судят ПОВЕДЕНИЕ набора на копии. Этот судит ИСХОДНИКИ: приёмка, достраивающая
# имя инструмента к mezo_paths.live_scripts(), названной копии не слышит вовсе — и, направленная
# на копию, испытывает живой файл. Поведением это не ловится: прогон зелен и там и там, пока
# копия и живое совпадают (а они совпадают почти всегда — ровно поэтому беда прожила с 05.10).
# 📏 Замер 13.11 19:18 UTC разбором дерева: таких мест было 41 в 37 приёмках, стало 0.
def _tested_via_live(root: pathlib.Path):
    """Приёмки, достраивающие имя инструмента к live_scripts(), минуя mezo_target.

    Признак ОДИН и точный: путь ДЕЛИТСЯ на строку-литерал, кончающуюся на .py или .sql
    (Path / "guard-all.py"), либо os.path.join с такой строкой. Прослеживаются и имена,
    которым значение присвоено (SCRIPTS = live_scripts(); SCRIPTS / "backlog.py").
    ⛔ ГРАНИЦА: разбор видит присвоения внутри ОДНОГО файла. Путь, уехавший в список, поле
    объекта или другой модуль, он не увидит — и молча ни к чему не припишет.
    """
    import ast as _ast
    out = []

    def _called(node):
        f, parts = node.func, []
        while isinstance(f, _ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, _ast.Name):
            parts.append(f.id)
        return ".".join(reversed(parts))

    def _tool_literal(n):
        return (isinstance(n, _ast.Constant) and isinstance(n.value, str)
                and n.value.endswith((".py", ".sql")) and "*" not in n.value)

    # 🎯 ОГОВОРКА ОБЪЯВЛЯЕТСЯ В КОДЕ, А НЕ В ГОЛОВЕ ПРОВЕРКИ. Разбор не умеет отличить
    # испытуемое от СОСЕДА и от снимка базы: и то и другое — «путь плюс имя .py». Приёмка,
    # берущая живой каталог НАМЕРЕННО, пишет рядом маркер MARK — и перестаёт быть находкой.
    # Без маркера проверка краснела бы на верном коде и научила бы себя отключать.
    MARK = "живой-каталог-умышленно"
    for path in sorted(root.glob("bite-*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "live_scripts" not in text:
            continue
        rows_src = text.splitlines()
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            out.append((path.name, 0, "не разбирается — к разряду НЕ приписана"))
            continue
        # ⚠️ Признак судит МЕСТО, а не файл. Прежняя редакция пропускала приёмку, если та
        # где-то зовёт mezo_target — и слепла на смешанных: одно место через общий выбор,
        # другое напрямую через live_scripts. Поймано нарочной поломкой ⑮ 13.11 19:48 UTC:
        # сломанная копия осталась «чистой», потому что её import mezo_target никуда не делся.
        calls = []
        for n in _ast.walk(tree):
            if isinstance(n, _ast.Call) and _called(n).endswith("live_scripts"):
                calls.append(n)
        if not calls:
            continue
        named = {}
        for n in _ast.walk(tree):
            if isinstance(n, _ast.Assign) and n.value is not None:
                inner = [c for c in _ast.walk(n.value) if c in calls]
                if inner:
                    for t in n.targets:
                        if isinstance(t, _ast.Name):
                            named[t.id] = inner[0].lineno

        def _line(node):
            inner = [c for c in _ast.walk(node) if c in calls]
            if inner:
                return inner[0].lineno
            got = {x.id for x in _ast.walk(node) if isinstance(x, _ast.Name)} & set(named)
            return named[next(iter(got))] if got else None

        def _excused(ln):
            """Маркер в строке вызова или в двух строках над ней — исключение ОБЪЯВЛЕНО."""
            lo = max(0, ln - 3)
            return any(MARK in r for r in rows_src[lo:ln])

        for n in _ast.walk(tree):
            if isinstance(n, _ast.BinOp) and isinstance(n.op, _ast.Div) and _tool_literal(n.right):
                ln = _line(n.left)
                if ln is not None and not _excused(ln):
                    out.append((path.name, ln, (_ast.get_source_segment(text, n) or "")[:90]))
            elif isinstance(n, _ast.Call) and _called(n).endswith("join") and n.args:
                ln = _line(n.args[0])
                if ln is not None and not _excused(ln) and any(_tool_literal(a) for a in n.args[1:]):
                    out.append((path.name, ln, (_ast.get_source_segment(text, n) or "")[:90]))
    # одно МЕСТО — одна находка: выражение «SCRIPTS / "x.py"» попадает в обход дважды
    # (как употребление имени и как часть объемлющего выражения), и без этого счёт удваивался
    seen, uniq = set(), []
    for name, ln, seg in out:
        if (name, ln) in seen:
            continue
        seen.add((name, ln))
        uniq.append((name, ln, seg))
    return uniq


def tested_choice_cases() -> bool:
    """Случаи ⑭ и ⑮ критерия ④ карточки #682."""
    here = pathlib.Path(HERE)
    found = _tested_via_live(here)
    ok = case("⑭ ни одна приёмка не берёт испытуемое мимо общего выбора (разбор исходников)",
              not found,
              f"приёмок с такой формой: {len(found)}"
              + ("" if not found else " — " + "; ".join(f"{n}:{ln}" for n, ln, _ in found[:6])),
              differ=True)

    # ⑮ НАРОЧНАЯ ПОЛОМКА: в КОПИИ одной приёмки возвращаем прежнюю форму. Копия кладётся
    #    в отдельный каталог — живые файлы не трогаются (это проверяется случаем же: имя
    #    поломанного файла печатается).
    import tempfile as _tf
    with _tf.TemporaryDirectory(prefix="bite-target-choice-") as tmp:
        broken_dir = pathlib.Path(tmp) / "prototype"
        broken_dir.mkdir()
        sample = here / "bite-guard-all-retired-wiring.py"
        text = sample.read_text(encoding="utf-8")
        hurt = text.replace('mezo_target.script("guard-all.py")',
                            'mezo_paths.live_scripts() / "guard-all.py"', 1)
        if hurt == text:
            return case("⑮ НАРОЧНАЯ ПОЛОМКА: образец для поломки не найден",
                        False, f"в {sample.name} нет строки, которую можно сломать —"
                        " случай ⑭ остался бы без различителя", differ=True) and ok
        (broken_dir / sample.name).write_bytes(hurt.encode("utf-8"))
        hurt_found = _tested_via_live(broken_dir)
        ok &= case("⑮ НАРОЧНАЯ ПОЛОМКА: прежняя форма в копии приёмки ⇒ ⑭ её НАХОДИТ",
                   len(hurt_found) == 1 and hurt_found[0][0] == sample.name,
                   f"в поломанной копии найдено {len(hurt_found)} "
                   + (f"({hurt_found[0][0]}:{hurt_found[0][1]})" if hurt_found else "— разбор слеп"),
                   differ=True)
    return ok


if __name__ == "__main__":
    sys.exit(main())
