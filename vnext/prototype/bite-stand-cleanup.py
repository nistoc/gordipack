# -*- coding: utf-8 -*-
"""
bite-stand-cleanup.py — приёмка помощника mezo_stand.py и утилиты janitor-stands.py.

Проверяет ЗАПУСКОМ, а не чтением: поднимает подставные проверки, смотрит, остался
каталог на диске или нет. Есть НАРОЧНЫЕ ПОЛОМКИ — если их не поймали, приёмка слепа
и её «пройдено» ничего не доказывает.

Случаи (12)–(20) — правка утилиты по карточке #657 (10.10.2026): начало f-строки,
комментарии не читаются, начала, названные руками (--prefix), общий корень gordi
не трогается, короткое начало не берётся, порог в часах различает 2 ч и 72 ч,
«освобождено» считает только удалённое, соединение каталогов наружу не проходится
ни удалением, ни подсчётом размера. У каждого — своя нарочная поломка в копии
утилиты, и случай обязан на ней провалиться. (17)–(19) — по замечаниям приёмки OPSSRE.

Этап Э6 (карточка #680, план COORD e6/stands-coord.md): список начал имён и размер стенда
переехали в mezo_stand.py (решение В2) — у автоуборки по сроку и у утилиты одно правило.
Поэтому нарочная поломка ищет своё место в ОБОИХ файлах (ровно одно на двоих), копия утилиты
едет в свой каталог вместе с mezo_stand.py, и утилита грузится вместе со своим соседом.
(21)–(23) — правка С2: возраст не ниже нуля, показ называет срок автоуборки, размер — os.lstat.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import importlib.util
from pathlib import Path

# ⚡ Утилита грузится С ДИСКА, а не пересказывается: копия признака в приёмке
# сходится с продуктом в день написания и расходится с ним молча.
_spec = importlib.util.spec_from_file_location(
    "janitor_under_test", Path(__file__).with_name("janitor-stands.py"))
LIVE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LIVE)

HERE = Path(__file__).resolve().parent
JANITOR = HERE / "janitor-stands.py"
CASES = 0
OK = True
LONG_AGO = 72 * 3600


def case(title, ok, detail):
    global CASES, OK
    CASES += 1
    OK &= bool(ok)
    print(f"{'OK ' if ok else 'RED'} {title}\n    {detail}")
    return ok


def run_probe(body, env_extra=None, helper=None):
    """Подставная проверка: заводит каталог помощником и завершается как велено."""
    helper = helper or (HERE / "mezo_stand.py")
    d = Path(tempfile.mkdtemp(prefix="probe-host-"))
    shutil.copy2(helper, d / "mezo_stand.py")
    head = (
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "import mezo_stand\n"
        "root = mezo_stand.new('probe-stand-')\n"
        "(root / 'marker.txt').write_text('x', encoding='utf-8')\n"
        "print('STAND=' + str(root))\n"
    )
    (d / "probe.py").write_text(head + body, encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("MEZO_KEEP_STANDS", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "probe.py"], cwd=d, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"STAND=(.+)", out)
    stand = Path(m.group(1).strip()) if m else None
    shutil.rmtree(d, ignore_errors=True)
    return stand, out, p.returncode


def janitor(sandbox, tools, *extra, script=None, env=None):
    p = subprocess.run([sys.executable, str(script or JANITOR),
                        "--temp-dir", str(sandbox), "--tools-dir", str(tools), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(env if env is not None else os.environ, PYTHONIOENCODING="utf-8"))
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def load(path, name):
    """Загрузить утилиту ВМЕСТЕ с mezo_stand.py из её каталога: список начал имён она берёт оттуда,
    и нарочная поломка помощника обязана до неё дойти. Без этого import взял бы уже загруженный
    помощник рядом с приёмкой — и поломка молча не действовала бы."""
    folder = str(Path(path).parent)
    saved = sys.modules.pop("mezo_stand", None)
    sys.path.insert(0, folder)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(folder)
        sys.modules.pop("mezo_stand", None)
        if saved is not None:
            sys.modules["mezo_stand"] = saved
    return mod


def broken_copy(holder, needle, replacement):
    """Копия утилиты с одной нарочной поломкой — в ней самой или в её mezo_stand.py (список начал имён
    и размер стенда живут там с этапа Э6). Оба файла едут в свой каталог: утилита берёт соседа оттуда.
    Места нет или их больше одного на оба файла — громкий отказ, а не тихий пропуск."""
    sources = {name: (HERE / name).read_text(encoding="utf-8") for name in (JANITOR.name, "mezo_stand.py")}
    found = sum(text.count(needle) for text in sources.values())
    if found != 1:
        sys.exit(f"НЕ ЗАПУСТИЛАСЬ: место для нарочной поломки найдено {found} раз в {JANITOR.name} "
                 f"и mezo_stand.py вместе (нужно ровно 1) — утилита менялась, правь приёмку:\n    {needle!r}")
    folder = holder / f"broken-{abs(hash(needle)) % 10**6}"
    folder.mkdir(exist_ok=True)
    for name, text in sources.items():
        (folder / name).write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    return folder / JANITOR.name


def old_dirs(root, *names, age=LONG_AGO):
    """Подставная временная папка: каталоги с копией внутри и датой давностью age секунд
    (по умолчанию трое суток)."""
    root.mkdir(parents=True, exist_ok=True)
    when = time.time() - age
    for n in names:
        d = root / n
        d.mkdir()
        (d / "copy.db").write_bytes(b"x" * 1024)
        os.utime(d, (when, when))
    return root


def link_dir(target, link):
    """Соединение каталогов: на Windows — junction (такие делает bite-stand-keep-last.py), иначе ссылка."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(Path(target).resolve()), str(Path(link).resolve()))
    else:
        os.symlink(target, link, target_is_directory=True)


def main():
    print("=" * 78)
    print("ПРИЁМКА: уборка временных каталогов проверок")
    print("=" * 78)

    # (1) успех — каталог убран
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(0))")
    reported = "убрано временных каталогов: 1" in out
    case("(1) прогон УСПЕШЕН — каталог убран",
         st is not None and not st.exists() and reported,
         f"код {rc} · каталог существует: {st.exists() if st else '-'} · "
         f"отчёт об уборке напечатан: {'да' if reported else 'НЕТ'}")

    # (2) провал — каталог СОХРАНЁН и путь НАПЕЧАТАН
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(1))")
    kept = st is not None and st.exists()
    printed = st is not None and str(st) in out and "СОХРАНЕНЫ" in out
    case("(2) прогон ПРОВАЛИЛСЯ — каталог сохранён, путь напечатан",
         kept and printed and "прогон провалился" in out,
         f"код {rc} · каталог на месте: {kept} · путь в выводе: {printed}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (3) падение без объявления исхода — каталог СОХРАНЁН
    st, out, rc = run_probe("raise SystemExit('упало до объявления исхода')")
    kept = st is not None and st.exists()
    case("(3) упал, не объявив исход — каталог сохранён (неизвестность = провал)",
         kept and "не объявлен" in out,
         f"код {rc} · каталог на месте: {kept} · "
         f"причина названа: {'да' if 'не объявлен' in out else 'НЕТ'}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (4) успех, но велено сохранять — каталог СОХРАНЁН
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(0))", {"MEZO_KEEP_STANDS": "1"})
    kept = st is not None and st.exists()
    case("(4) успех + MEZO_KEEP_STANDS=1 — каталог всё равно сохранён",
         kept and "MEZO_KEEP_STANDS" in out,
         f"каталог на месте: {kept}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (5) НАРОЧНАЯ ПОЛОМКА: убирать всегда => случай (2) обязан провалиться
    broken_dir = Path(tempfile.mkdtemp(prefix="probe-broken-"))
    src = (HERE / "mezo_stand.py").read_text(encoding="utf-8")
    needle = "    why = keep_reason()"
    if needle not in src:
        sys.exit("НЕ ЗАПУСТИЛАСЬ: место для нарочной поломки не найдено — "
                 "помощник менялся, правь приёмку")
    broken = broken_dir / "mezo_stand.py"
    broken.write_text(src.replace(needle, "    why = None", 1), encoding="utf-8")
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(1))", helper=broken)
    caught = not (st is not None and st.exists())
    case("(5) НАРОЧНАЯ ПОЛОМКА (убирать всегда) — приёмка обязана это заметить",
         caught,
         "поломанный помощник убрал каталог даже при провале => случай (2) на нём провалился бы"
         if caught else
         "ПРИЁМКА СЛЕПА: поломанный помощник ведёт себя как целый — случай (2) ничего не доказывает")
    shutil.rmtree(broken_dir, ignore_errors=True)
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # обстановка для утилиты уборки
    sandbox = Path(tempfile.mkdtemp(prefix="probe-temp-"))
    tools = Path(tempfile.mkdtemp(prefix="probe-tools-"))
    (tools / "fake-check.py").write_text(
        'import tempfile\nd = tempfile.mkdtemp(prefix="jprobe-oldstand-")\n', encoding="utf-8")
    old = sandbox / "jprobe-oldstand-aaaaaa"
    old.mkdir()
    (old / "copy.db").write_bytes(b"x" * 4096)
    long_ago = time.time() - LONG_AGO
    os.utime(old, (long_ago, long_ago))
    young = sandbox / "jprobe-oldstand-bbbbbb"
    young.mkdir()

    # (6) показ НЕ удаляет
    out, rc = janitor(sandbox, tools)
    case("(6) утилита уборки БЕЗ --apply — показывает, но не удаляет",
         old.exists() and young.exists() and "ПОКАЗ, НЕ УДАЛЕНИЕ" in out and "подпадает: 1" in out,
         f"старый каталог на месте: {old.exists()} · молодой на месте: {young.exists()}")

    # (7) --apply удаляет ТОЛЬКО старое
    out, rc = janitor(sandbox, tools, "--apply")
    case("(7) утилита уборки С --apply — удалила старое, не тронула молодое",
         not old.exists() and young.exists() and "УДАЛЕНО: 1" in out,
         f"старый удалён: {not old.exists()} · молодой уцелел: {young.exists()}")

    # (8) ноль под порогом печатается СЛОВОМ
    out, rc = janitor(sandbox, tools)
    case("(8) под порог никто не подпал — сказано словом НОЛЬ, а не тишиной",
         "НОЛЬ" in out and "Ни один каталог не старше порога" in out,
         "иначе прогон, ничего не удаливший, читался бы как успешная уборка")

    # (9) начал имён нет — громкий отказ, а не тихое «удалено 0»
    empty_tools = Path(tempfile.mkdtemp(prefix="probe-empty-"))
    (empty_tools / "nothing.py").write_text("x = 1\n", encoding="utf-8")
    out, rc = janitor(sandbox, empty_tools, "--apply")
    case("(9) начал имён в исходниках нет — громкий отказ, а не тихое «удалено 0»",
         rc == 2 and "НЕ ЗАПУСТИЛАСЬ" in out and young.exists(),
         f"код {rc} · отказ назван: {'да' if 'НЕ ЗАПУСТИЛАСЬ' in out else 'НЕТ'}")

    # (10) 🩸 УТИЛИТА САМА НАХОДИТ ВСЕ КАТАЛОГИ ИНСТРУМЕНТОВ, А НЕ ОДИН СВОЙ.
    #      Замер PROTO 2026-08-24 16:43 UTC: каталогов в контуре ДВА, и во втором лежали
    #      7 начал имён, которых не было в первом, — среди них `gordi-src-`, по которому
    #      накопилось 245 каталогов на 0.31 ГБ. Из одного каталога утилита видела 89,
    #      из обоих — 338.
    #      ⚖️ Указать второй можно было и руками, но тогда полнота уборки держалась бы
    #      ПАМЯТЬЮ зовущего: забыл — утилита честно скажет «убрано», умолчав, что смотрела
    #      в половину мест. Свойство должно проверяться, иначе оно держится случайно.
    # ГРУППА F, карточка #659 / разбор COORD (карточка #288, 27.08): LIVE загружена рядом
    # с ЭТОЙ приёмкой (vnext/prototype в пакете). У живого Atlas janitor-stands.py лежит
    # в vnext-tools ПРЯМО ПОД корнем контура, и рядом с корнем — .mezosync/scripts: два
    # места. В пакете аналог лежит в vnext/prototype — на уровень ГЛУБЖЕ, и над ним нет
    # .mezosync/scripts НИ У vnext, НИ У корня пакета: не дефект пакета, а другая раскладка
    # (доказано чтением: pw-F не несёт .mezosync ни в vnext/, ни в корне). Проверять
    # «находит ли код второй каталог» ПАМЯТЬЮ о разложении живой машины — значит держать
    # приёмку на угаданном пути, который в пакете не существует.
    # ⇒ свойство проверяем ПОСТРОЕНИЕМ: копируем janitor-stands.py БЕЗ ПРАВОК на
    # синтетическое место той же ФОРМЫ, что живой контур (свой каталог + СОСЕДНИЙ
    # .mezosync/scripts НАД ним), и зовём те же функции у копии. Так проверка держится
    # формой, которую ищет код, а не случайной раскладкой пакета или живой машины —
    # и остаётся честной в обоих контурах.
    synth = Path(tempfile.mkdtemp(prefix="janitor-topology-"))
    try:
        own_synth = synth / "vnext-tools"
        own_synth.mkdir(parents=True)
        shutil.copy2(JANITOR, own_synth / "janitor-stands.py")
        # список начал имён утилита берёт у mezo_stand.py — он лежит рядом, как в живом vnext-tools
        shutil.copy2(HERE / "mezo_stand.py", own_synth / "mezo_stand.py")
        # сосед по СВОЕМУ каталогу (как остальные ~270 bite-*.py рядом с janitor-stands.py
        # в живом vnext-tools) — чтобы «из своего» тоже было НЕ ноль, а не только «из всех»
        (own_synth / "bite-fake-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="jprobe-svoi-check-")\n', encoding="utf-8")
        neighbor_synth = synth / ".mezosync" / "scripts"
        neighbor_synth.mkdir(parents=True)
        (neighbor_synth / "fake-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="jprobe-synth-check-")\n', encoding="utf-8")

        SYNTH = load(own_synth / "janitor-stands.py", "janitor_synth")
        from_own, _ = SYNTH.prefixes_from_sources(SYNTH.TOOLS_DIR)
        dirs = SYNTH.tool_dirs()
        from_all, _ = SYNTH.prefixes_from_sources(dirs)
        case("(10) утилита сама находит ВСЕ каталоги инструментов, а не только свой "
             "(синтетическая раскладка формы живого контура: свой + сосед .mezosync/scripts)",
             len(dirs) > 1 and len(from_all) > len(from_own),
             f"каталогов найдено {len(dirs)} · начал имён из своего {len(from_own)}, "
             f"из всех {len(from_all)} — полнота уборки не должна держаться памятью зовущего")
    finally:
        shutil.rmtree(synth, ignore_errors=True)

    # (11) ВСТРЕЧНЫЙ к (10): названо ЯВНО — берём названное, а не «всё, что нашли».
    #      Иначе указание пути ничего не значило бы, и случай (9) стал бы недостижим.
    only_empty, _ = LIVE.prefixes_from_sources([empty_tools])
    case("(11) ВСТРЕЧНЫЙ: названный каталог берётся ровно один, поиск не подмешивается",
         not only_empty,
         "иначе явное указание пути перестало бы значить что-либо, а отказ (9) "
         "стал бы недостижим")

    for d in (sandbox, tools, empty_tools):
        shutil.rmtree(d, ignore_errors=True)

    new_cases()

    print("\n" + "=" * 78)
    print(f"{'ПРИЁМКА ПРОЙДЕНА' if OK else 'ПРИЁМКА ПРОВАЛЕНА'} — случаев {CASES}")
    return 0 if OK else 1


def new_cases():
    """(12)–(20): правка карточки #657; (21)–(23) — правка С2 этапа Э6. Каждый случай гоняется на целой утилите и на копии
    с СВОЕЙ нарочной поломкой; на поломке он обязан провалиться, иначе случай ничего не доказывает.

    ⚠️ Все начала имён в строках-примерах этого файла — с корнем «jprobe-». Уборщик читает
    и этот файл как исходник проверки (строка-пример для него неотличима от вызова), и пример
    вида «plain-» стал бы началом, подходящим к чужим каталогам живой временной папки
    (замечание OPSSRE З2, карточка #657, 10.10). Под «jprobe-» живых каталогов нет."""
    work = Path(tempfile.mkdtemp(prefix="janitor-657-"))
    try:
        # исходники подставных проверок
        tools = work / "tools"
        tools.mkdir()
        (tools / "jprobe-fstr-check.py").write_text(
            'import tempfile\nn = 1\nd = tempfile.mkdtemp(prefix=f"jprobe-fstr-{n}-")\n', encoding="utf-8")
        (tools / "comment-check.py").write_text(
            "import tempfile\n"
            '# d = tempfile.mkdtemp(prefix="jprobe-commented-")\n'
            'x = 1  # import mezo_stand; mezo_stand.new("jprobe-trailing-")\n'
            'd = tempfile.mkdtemp(prefix="jprobe-hash#inside-")\n', encoding="utf-8")
        (tools / "jprobe-plain-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="jprobe-plain-")\n', encoding="utf-8")

        def prefixes_of(script):
            mod = load(script, f"janitor_{abs(hash(str(script))) % 10**6}")
            found, _ = mod.prefixes_from_sources([tools])
            return found

        # (12) начало f-строки читается до первой подстановки
        def c12(script):
            found = prefixes_of(script)
            return "jprobe-fstr-" in found and "jprobe-plain-" in found, found
        ok, found = c12(JANITOR)
        bad, _ = c12(broken_copy(work, "    r'(?:[fF][\"\\']([^\"\\'{]+)|[\"\\']([^\"\\']+)[\"\\'])')",
                                 "    r'(?:[fF][\"\\']([^\"\\'{]+)(?!)|[\"\\']([^\"\\']+)[\"\\'])')"))
        case("(12) начало f-строки читается: prefix=f\"jprobe-fstr-{n}-\" даёт «jprobe-fstr-»; "
             "поломка «f-строка не читается» проваливает случай",
             ok and not bad,
             f"на целой: jprobe-fstr- {'есть' if 'jprobe-fstr-' in found else 'НЕТ'} · jprobe-plain- "
             f"{'есть' if 'jprobe-plain-' in found else 'НЕТ'} · на поломке случай "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (13) комментарии не читаются, а «#» внутри строки — не комментарий
        def c13(script):
            found = prefixes_of(script)
            return ("jprobe-commented-" not in found and "jprobe-trailing-" not in found
                    and "jprobe-hash#inside-" in found), found
        ok, found = c13(JANITOR)
        bad, _ = c13(broken_copy(work, "    return \"\".join(lines)\n", "    return text\n"))
        case("(13) комментарий не даёт начала имени (целая строка и хвост строки), "
             "«#» внутри строки — не комментарий; поломка «комментарии читаются» проваливает случай",
             ok and not bad,
             f"на целой: jprobe-commented- {'взято — ОШИБКА' if 'jprobe-commented-' in found else 'не взято'} · "
             f"jprobe-trailing- {'взято — ОШИБКА' if 'jprobe-trailing-' in found else 'не взято'} · "
             f"jprobe-hash#inside- {'взято' if 'jprobe-hash#inside-' in found else 'НЕ взято — ОШИБКА'} · "
             f"на поломке {'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (14) начало, названное руками (--prefix), берётся; без него каталог не трогается
        def c14(script):
            sb = old_dirs(work / f"sb14-{abs(hash(str(script))) % 10**6}", "named-old-aaa")
            out0, _ = janitor(sb, tools, "--apply", script=script)
            untouched = (sb / "named-old-aaa").exists()
            out1, _ = janitor(sb, tools, "--prefix", "named-old-", "--apply", script=script)
            gone = not (sb / "named-old-aaa").exists()
            return untouched and gone and "названо руками" in out1, (untouched, gone)
        ok, (untouched, gone) = c14(JANITOR)
        bad, _ = c14(broken_copy(work, "    named = set(a.prefix)\n", "    named = set()\n"))
        case("(14) --prefix добавляет начало: без него каталог named-old- цел (встречный), "
             "с ним — удалён; поломка «--prefix пропускается» проваливает случай",
             ok and not bad,
             f"без --prefix цел: {untouched} · с --prefix удалён: {gone} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (15) общий корень gordi не берётся ни при каком начале; соседи по началу — берутся
        def c15(script):
            sb = old_dirs(work / f"sb15-{abs(hash(str(script))) % 10**6}", "gordi", "gordi-src-zzz")
            out, _ = janitor(sb, tools, "--prefix", "gordi", "--apply", script=script)
            kept = (sb / "gordi").exists()
            neighbour_gone = not (sb / "gordi-src-zzz").exists()
            return kept and neighbour_gone and "не трогаю gordi" in out, (kept, neighbour_gone)
        ok, (kept, neighbour_gone) = c15(JANITOR)
        bad, _ = c15(broken_copy(work, 'RESERVED_NAMES = {"gordi"}\n', "RESERVED_NAMES = set()\n"))
        case("(15) каталог gordi (общий корень стендов) цел даже при начале «gordi», "
             "gordi-src-zzz удалён; поломка «нет запретных имён» проваливает случай",
             ok and not bad,
             f"gordi цел: {kept} · gordi-src-zzz удалён: {neighbour_gone} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (16) короткое начало не берётся и называется
        def c16(script):
            sb = old_dirs(work / f"sb16-{abs(hash(str(script))) % 10**6}", "abc-foreign")
            out, _ = janitor(sb, tools, "--prefix", "ab", "--apply", script=script)
            kept = (sb / "abc-foreign").exists()
            return kept and "НЕ взяты (короче" in out, kept
        ok, kept = c16(JANITOR)
        bad, _ = c16(broken_copy(work, "MIN_PREFIX_LEN = 4\n", "MIN_PREFIX_LEN = 0\n"))
        case("(16) начало короче 4 знаков («ab») не берётся и названо — чужой каталог abc-foreign цел; "
             "поломка «порога длины нет» проваливает случай",
             ok and not bad,
             f"abc-foreign цел: {kept} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (17) «молодой, но не новый»: каталог 2 ч при пороге 24 ч остаётся, 72 ч — уходит.
        #      Случай (7) судил пару «72 ч против только что созданного», и ошибка единиц
        #      порога между ними не видна: порог в минутах удалил бы всё старше 24 МИНУТ,
        #      в том числе стенды идущих сегодня прогонов (поломка OPSSRE О1, замечание З1).
        def c17(script):
            sb = old_dirs(work / f"sb17-{abs(hash(str(script))) % 10**6}", "jprobe-age-old")
            old_dirs(sb, "jprobe-age-2h", age=2 * 3600)
            janitor(sb, tools, "--prefix", "jprobe-age-", "--apply", script=script)
            young_kept = (sb / "jprobe-age-2h").exists()
            old_gone = not (sb / "jprobe-age-old").exists()
            return young_kept and old_gone, (young_kept, old_gone)
        ok, (young_kept, old_gone) = c17(JANITOR)
        bad, _ = c17(broken_copy(work, "    limit = a.older_than_hours * 3600\n",
                                 "    limit = a.older_than_hours * 60\n"))
        case("(17) каталог 2 ч при пороге 24 ч цел, 72 ч — удалён; поломка «порог в минутах» "
             "проваливает случай",
             ok and not bad,
             f"2 ч цел: {young_kept} · 72 ч удалён: {old_gone} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (18) «освобождено» считает только удалённое целиком (замечание OPSSRE З3).
        #      Неудалённый каталог даёт открытый файл: Windows не удаляет открытое.
        if os.name != "nt":
            print("⚪ (18) не проверено: на этой системе открытый файл удалению не мешает — "
                  "неудачу удаления здесь не поставить")
        else:
            def c18(script):
                sb = old_dirs(work / f"sb18-{abs(hash(str(script))) % 10**6}",
                              "jprobe-busy-aaa", "jprobe-free-bbb")
                big = sb / "jprobe-busy-aaa" / "held.bin"
                big.write_bytes(b"x" * (30 * 1024 * 1024))   # 30 МБ — видно в сотых долях ГБ
                when = time.time() - LONG_AGO
                os.utime(sb / "jprobe-busy-aaa", (when, when))
                with open(big, "rb"):
                    out, _ = janitor(sb, tools, "--prefix", "jprobe-busy-", "--prefix", "jprobe-free-",
                                     "--apply", script=script)
                busy_left = (sb / "jprobe-busy-aaa").exists()
                return (busy_left and "НЕ УДАЛОСЬ: 1" in out and "освобождено 0.00 ГБ" in out), out
            ok, out = c18(JANITOR)
            bad, _ = c18(broken_copy(work, 'f"освобождено {freed / 1024 ** 3:.2f} ГБ"',
                                     'f"освобождено {gb:.2f} ГБ"'))
            line = next((s.strip() for s in out.splitlines() if "освобождено" in s), "строки нет")
            case("(18) «освобождено» — только по удалённым целиком: каталог с открытым файлом 30 МБ "
                 "не удалён и в сумму не вошёл; поломка «считать всё отобранное» проваливает случай",
                 ok and not bad,
                 f"на целой: {line} · на поломке "
                 f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # Соединение каталогов внутри старого стенда, указывающее НАРУЖУ. Такие соединения
        # в живой временной папке есть — их нарочно делает bite-stand-keep-last.py.
        def stand_with_link(name, outside_bytes):
            sb = old_dirs(work / name, "jprobe-link-aaa")
            outside = work / f"{name}-outside"
            outside.mkdir()
            keep = outside / "keep.bin"
            keep.write_bytes(b"x" * outside_bytes)
            link_dir(outside, sb / "jprobe-link-aaa" / "link")
            when = time.time() - LONG_AGO   # соединение обновило дату стенда — вернуть
            os.utime(sb / "jprobe-link-aaa", (when, when))
            return sb, keep

        # (19) удаление стенда не трогает файлы снаружи: ошибка здесь стирает файлы ВНЕ
        #      временной папки (поломка OPSSRE О2, замечание З5).
        def c19(script):
            sb, keep = stand_with_link(f"sb19-{abs(hash(str(script))) % 10**6}", 1024)
            janitor(sb, tools, "--prefix", "jprobe-link-", "--apply", script=script)
            stand_gone = not (sb / "jprobe-link-aaa").exists()
            return stand_gone and keep.exists(), (stand_gone, keep.exists())
        ok, (stand_gone, kept) = c19(JANITOR)
        bad, _ = c19(broken_copy(work, "            shutil.rmtree(d, onerror=_force_writable)\n",
                                 "            for r, _ds, fs in os.walk(d, followlinks=True):\n"
                                 "                for f in fs:\n"
                                 "                    os.remove(os.path.join(r, f))\n"
                                 "            shutil.rmtree(d, onerror=_force_writable)\n"))
        case("(19) старый стенд с соединением каталогов наружу удалён, файл снаружи цел; "
             "поломка «удаление проходит по соединению» проваливает случай",
             ok and not bad,
             f"стенд удалён: {stand_gone} · файл снаружи цел: {kept} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (20) размер стенда не считает файлы за соединением: rmtree их не удаляет, а os.walk
        #      на Windows соединение проходит (для os.path.islink оно не ссылка). Без отсечения
        #      стенд в 1 КБ с соединением на 30 МБ снаружи показывался бы как 30 МБ.
        if os.name != "nt":
            print("⚪ (20) не проверено: здесь os.walk ссылку и так не проходит — "
                  "поломке нечего ломать")
        else:
            def c20(script):
                sb, _ = stand_with_link(f"sb20-{abs(hash(str(script))) % 10**6}", 30 * 1024 * 1024)
                out, _ = janitor(sb, tools, "--prefix", "jprobe-link-", script=script)
                return "освободит 0.00 ГБ" in out, out
            ok, out = c20(JANITOR)
            bad, _ = c20(broken_copy(
                work, "        dirs[:] = [x for x in dirs if not _is_link_path(os.path.join(top, x))]\n", ""))
            line = next((s.strip() for s in out.splitlines() if "освободит" in s), "строки нет")
            case("(20) размер стенда без файлов за соединением каталогов: стенд 1 КБ, снаружи 30 МБ — "
                 "показ «освободит 0.00 ГБ»; поломка «подсчёт проходит соединение» проваливает случай",
                 ok and not bad,
                 f"на целой: {line} · на поломке "
                 f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (21) дата изменения из будущего — возраст ноль, а не «-1.0 ч» (С2 плана Э6). Смотрится и
        #      строка «Самому молодому», и перечень по --all: в перечень идёт возраст каждого каталога
        def c21(script):
            sb = old_dirs(work / f"sb21-{abs(hash(str(script))) % 10**6}", "jprobe-future-aaa", age=-3600)
            out_young, _ = janitor(sb, tools, "--prefix", "jprobe-future-", script=script)
            out_all, _ = janitor(sb, tools, "--prefix", "jprobe-future-", "--all", script=script)
            listed = next((s for s in out_all.splitlines() if s.strip().endswith("jprobe-future-aaa")), "")
            ok = ("Самому молодому 0.0 ч" in out_young
                  and re.search(r"-\d+\.\d ч", out_young + out_all) is None
                  and re.search(r"\b0\.0 ч", listed) is not None)
            return ok, (out_young, listed)
        ok, (out_young, listed) = c21(JANITOR)
        bad, _ = c21(broken_copy(work, "            age = max(0.0, now - d.stat().st_mtime)   "
                                       "# дата из будущего — не «-0.0 ч», а ноль\n",
                                 "            age = now - d.stat().st_mtime\n"))
        young_line = next((s.strip() for s in out_young.splitlines() if "Самому молодому" in s), "строки нет")
        case("(21) каталог с датой из будущего: возраст 0.0 ч, а не отрицательный — в строке «Самому "
             "молодому» и в перечне --all; поломка «возраст без нижней границы» проваливает случай",
             ok and not bad,
             f"на целой: {young_line} · перечень: {listed.strip() or 'строки нет'} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (22) показ называет срок автоуборки mezo_stand.py — из той же переменной, что и сама уборка:
        #      без переменной 48 ч, MEZO_STAND_MAX_AGE_H=6 — 6 ч, =0 — «выключена»
        def c22(script):
            sb = old_dirs(work / f"sb22-{abs(hash(str(script))) % 10**6}", "jprobe-auto-aaa")
            base = {k: v for k, v in os.environ.items() if k != "MEZO_STAND_MAX_AGE_H"}
            lines = []
            for value in (None, "6", "0"):
                env = dict(base) if value is None else dict(base, MEZO_STAND_MAX_AGE_H=value)
                out, _ = janitor(sb, tools, "--prefix", "jprobe-auto-", script=script, env=env)
                lines.append(next((s.strip() for s in out.splitlines() if "автоуборка" in s), "строки нет"))
            ok = ("старше 48 ч" in lines[0] and "Корзину" in lines[0] and "старше 6 ч" in lines[1]
                  and "выключена" in lines[2])
            return ok, lines
        ok, lines = c22(JANITOR)
        bad, _ = c22(broken_copy(work, "    auto = mezo_stand.max_age_hours()\n", "    auto = 48.0\n"))
        case("(22) показ называет срок автоуборки: без переменной 48 ч, MEZO_STAND_MAX_AGE_H=6 — 6 ч, "
             "=0 — выключена; поломка «срок впечатан» проваливает случай",
             ok and not bad,
             f"на целой: {' | '.join(lines)} · на поломке "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (23) размер — os.lstat: ссылка на файл 30 МБ снаружи весит как ссылка, а не как файл
        #      (замечание OPSSRE 10.10, перенесено в Э6). Ссылку на файл Windows без прав
        #      разработчика не даёт — тогда случай не проверяется и это сказано
        probe_dir = work / "symlink-probe"
        probe_dir.mkdir()
        try:
            os.symlink(JANITOR, probe_dir / "l")
            can_link = True
        except (OSError, NotImplementedError):
            can_link = False
        if not can_link:
            print("⚪ (23) не проверено: ссылку на файл эта учётная запись создать не может "
                  "(Windows без прав разработчика) — разницы os.lstat и getsize здесь не поставить")
        else:
            def c23(script):
                tag = abs(hash(str(script))) % 10**6
                sb = old_dirs(work / f"sb23-{tag}", "jprobe-flink-aaa")
                big = work / f"sb23-{tag}-outside.bin"
                big.write_bytes(b"x" * (30 * 1024 * 1024))
                os.symlink(big, sb / "jprobe-flink-aaa" / "big.lnk")
                when = time.time() - LONG_AGO
                os.utime(sb / "jprobe-flink-aaa", (when, when))
                out, _ = janitor(sb, tools, "--prefix", "jprobe-flink-", script=script)
                return "освободит 0.00 ГБ" in out, out
            ok, out = c23(JANITOR)
            bad, _ = c23(broken_copy(work, "                total += os.lstat(os.path.join(top, name)).st_size\n",
                                     "                total += os.path.getsize(os.path.join(top, name))\n"))
            line = next((s.strip() for s in out.splitlines() if "освободит" in s), "строки нет")
            case("(23) размер стенда — os.lstat: ссылка на файл 30 МБ снаружи не входит в «освободит»; "
                 "поломка «размер по getsize» проваливает случай",
                 ok and not bad,
                 f"на целой: {line} · на поломке "
                 f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
