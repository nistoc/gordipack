# -*- coding: utf-8 -*-
"""
bite-stand-cleanup.py — приёмка помощника mezo_stand.py и утилиты janitor-stands.py.

Проверяет ЗАПУСКОМ, а не чтением: поднимает подставные проверки, смотрит, остался
каталог на диске или нет. Есть НАРОЧНЫЕ ПОЛОМКИ — если их не поймали, приёмка слепа
и её «пройдено» ничего не доказывает.

Случаи (12)–(16) — правка утилиты по карточке #657 (10.10.2026): начало f-строки,
комментарии не читаются, начала, названные руками (--prefix), общий корень gordi
не трогается, короткое начало не берётся. У каждого — своя нарочная поломка в копии
утилиты, и случай обязан на ней провалиться.
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


def janitor(sandbox, tools, *extra, script=None):
    p = subprocess.run([sys.executable, str(script or JANITOR),
                        "--temp-dir", str(sandbox), "--tools-dir", str(tools), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def broken_copy(holder, needle, replacement):
    """Копия утилиты с одной нарочной поломкой. Места нет — громкий отказ, а не тихий пропуск."""
    src = JANITOR.read_text(encoding="utf-8")
    if src.count(needle) != 1:
        sys.exit(f"НЕ ЗАПУСТИЛАСЬ: место для нарочной поломки найдено {src.count(needle)} раз "
                 f"(нужно ровно 1) — утилита менялась, правь приёмку:\n    {needle!r}")
    path = holder / f"janitor-broken-{abs(hash(needle)) % 10**6}.py"
    path.write_text(src.replace(needle, replacement, 1), encoding="utf-8")
    return path


def old_dirs(root, *names):
    """Подставная временная папка: каталоги с копией внутри и датой трёхсуточной давности."""
    root.mkdir(parents=True, exist_ok=True)
    when = time.time() - LONG_AGO
    for n in names:
        d = root / n
        d.mkdir()
        (d / "copy.db").write_bytes(b"x" * 1024)
        os.utime(d, (when, when))
    return root


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
        'import tempfile\nd = tempfile.mkdtemp(prefix="oldstand-")\n', encoding="utf-8")
    old = sandbox / "oldstand-aaaaaa"
    old.mkdir()
    (old / "copy.db").write_bytes(b"x" * 4096)
    long_ago = time.time() - LONG_AGO
    os.utime(old, (long_ago, long_ago))
    young = sandbox / "oldstand-bbbbbb"
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
        # сосед по СВОЕМУ каталогу (как остальные ~270 bite-*.py рядом с janitor-stands.py
        # в живом vnext-tools) — чтобы «из своего» тоже было НЕ ноль, а не только «из всех»
        (own_synth / "bite-fake-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="svoi-check-")\n', encoding="utf-8")
        neighbor_synth = synth / ".mezosync" / "scripts"
        neighbor_synth.mkdir(parents=True)
        (neighbor_synth / "fake-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="synth-check-")\n', encoding="utf-8")

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
    """(12)–(16): правка карточки #657. Каждый случай гоняется на целой утилите и на копии
    с СВОЕЙ нарочной поломкой; на поломке он обязан провалиться, иначе случай ничего не доказывает."""
    work = Path(tempfile.mkdtemp(prefix="janitor-657-"))
    try:
        # исходники подставных проверок
        tools = work / "tools"
        tools.mkdir()
        (tools / "fstr-check.py").write_text(
            'import tempfile\nn = 1\nd = tempfile.mkdtemp(prefix=f"fstr-{n}-")\n', encoding="utf-8")
        (tools / "comment-check.py").write_text(
            "import tempfile\n"
            '# d = tempfile.mkdtemp(prefix="commented-")\n'
            'x = 1  # import mezo_stand; mezo_stand.new("trailing-")\n'
            'd = tempfile.mkdtemp(prefix="hash#inside-")\n', encoding="utf-8")
        (tools / "plain-check.py").write_text(
            'import tempfile\nd = tempfile.mkdtemp(prefix="plain-")\n', encoding="utf-8")

        def prefixes_of(script):
            mod = load(script, f"janitor_{abs(hash(str(script))) % 10**6}")
            found, _ = mod.prefixes_from_sources([tools])
            return found

        # (12) начало f-строки читается до первой подстановки
        def c12(script):
            found = prefixes_of(script)
            return "fstr-" in found and "plain-" in found, found
        ok, found = c12(JANITOR)
        bad, _ = c12(broken_copy(work, "    r'(?:[fF][\"\\']([^\"\\'{]+)|[\"\\']([^\"\\']+)[\"\\'])')",
                                 "    r'(?:[fF][\"\\']([^\"\\'{]+)(?!)|[\"\\']([^\"\\']+)[\"\\'])')"))
        case("(12) начало f-строки читается: prefix=f\"fstr-{n}-\" даёт «fstr-»; "
             "поломка «f-строка не читается» проваливает случай",
             ok and not bad,
             f"на целой: fstr- {'есть' if 'fstr-' in found else 'НЕТ'} · plain- "
             f"{'есть' if 'plain-' in found else 'НЕТ'} · на поломке случай "
             f"{'провалился, как должен' if not bad else 'ПРОШЁЛ — приёмка слепа'}")

        # (13) комментарии не читаются, а «#» внутри строки — не комментарий
        def c13(script):
            found = prefixes_of(script)
            return ("commented-" not in found and "trailing-" not in found
                    and "hash#inside-" in found), found
        ok, found = c13(JANITOR)
        bad, _ = c13(broken_copy(work, "    return \"\".join(lines)\n", "    return text\n"))
        case("(13) комментарий не даёт начала имени (целая строка и хвост строки), "
             "«#» внутри строки — не комментарий; поломка «комментарии читаются» проваливает случай",
             ok and not bad,
             f"на целой: commented- {'взято — ОШИБКА' if 'commented-' in found else 'не взято'} · "
             f"trailing- {'взято — ОШИБКА' if 'trailing-' in found else 'не взято'} · "
             f"hash#inside- {'взято' if 'hash#inside-' in found else 'НЕ взято — ОШИБКА'} · "
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
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
