# -*- coding: utf-8 -*-
r"""bite-to-template.py — приёмка карточки #576: перенос в публичный образец обезличивает пути сам.

═══ ЧТО СУДИМ
Перенос инструмента в образец делался руками, и дважды за смену 05.09 я едва не увёз туда
путь этой машины (2 файла в 20:48, 4 файла в 22:39). Оба раза поймал сличением ДО отправки,
то есть случайно. Теперь перенос зовёт ТУ ЖЕ функцию обезличивания, что и сверка расхождений.

═══ ГЛАВНОЕ, ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, И ПОЧЕМУ ЭТО НЕ ОЧЕВИДНО
Обезличить путь ЦЕЛИКОМ нельзя: строка, которую код ВЫЧИСЛЯЕТ, после подстановки заглушки
падает у потребителя на первом же прогоне (оплачено соседним контуром, записано в шапке
самой сверки). Значит перенос обязан РАЗЛИЧАТЬ читаемый человеком текст и исполняемый код —
и отказываться, когда путь стои́т во втором.

═══ ГРАНИЦА
Судится ПЕРЕНОС. Верность содержимого по существу он не знает и не обещает — прогон
образца остаётся за человеком, и инструмент говорит это вслух своей последней строкой.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

DRIFT_TOOL = Path(mezo_paths.live_scripts(__file__)) / "guard-scripts-drift.py"
CONTAINER = str(Path(mezo_paths.container_root(__file__)))

results: list[tuple[str, bool, str]] = []


def case(title: str, ok: bool, detail: str) -> None:
    results.append((title, ok, detail))
    print(f"{'✅' if ok else '🔴'} {title}: {detail}")


def transfer(files, src_dir: Path, dst_dir: Path):
    # ⚖️ КАРТОЧКА #613 — ИМЕННАЯ ПРИЧИНА, ПОЧЕМУ ЗДЕСЬ БЕЗ env=stand_env (проверено прогоном,
    # не рассуждением). guard-scripts-drift.py САМ вычисляет "чей это контур" вызовом
    # mezo_paths.container_root(__file__) (строка ~123: `_own_container = ...`) и строит
    # PLACEHOLDERS из НЕГО — а не получает путь параметром. Опыт здесь как раз про то, что
    # этот путь совпадает с CONTAINER (обе стороны считают его ОДИНАКОВО, через ТУ ЖЕ
    # container_root()). Подмена MEZO_CONTAINER на путь стенда рассинхронивает две стороны:
    # DRIFT_TOOL начинает обезличивать ЧУЖОЙ (стендовый) путь, а не CONTAINER — и все случаи,
    # проверяющие обезличивание, красятся ПОСТОРОННЕ (замер: 4 из 8 ложно-красных, включая ①).
    # ⇒ здесь испытуемому НУЖНА среда вызывающего — она направляет его на ТОТ ЖЕ контур,
    # который проверяет сам опыт, а не на чужой.
    r = subprocess.run([sys.executable, str(DRIFT_TOOL), "--to-template", *files,
                        "--vnext-runtime", str(src_dir), "--vnext-template", str(dst_dir)],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_name", choices=["plain-string"], default=None,
                    help="нарочная поломка (карточка #630): plain-string — путь в мирный.py "
                         "кладём обычной (не raw) строкой, как до правки")
    a = ap.parse_args()

    stand = Path(tempfile.mkdtemp(prefix="bite-to-template-"))
    mezo_stand.release(stand)
    # ⚖️ КАРТОЧКА #613 — здесь БЕЗ mezo_stand.stand_env(): именная причина в transfer()
    # (испытуемый сам вычисляет контур через container_root(), и ему нужна СРЕДА
    # ВЫЗЫВАЮЩЕГО, чтобы совпасть с CONTAINER, который проверяет сам опыт).
    source_dir = stand / "исток"
    template_dir = stand / "образец"
    source_dir.mkdir()
    template_dir.mkdir()

    # ── подопытный ①: путь этой машины стои́т ТОЛЬКО в читаемом человеком тексте
    # ⚡ КАРТОЧКА #630: CONTAINER — обычная (не raw) f-строка ЭТОГО файла, но подставляется
    # она в ТЕКСТ ДРУГОГО файла (мирный.py), который сам потом РАЗБИРАЕТСЯ как Python —
    # сверкой (ast/re-разбор строк) и здесь же в случае ④ (py_compile). Путь контейнера
    # под профилем Windows содержит «\U» (C:\Users\...) — ЛЮБОЙ путь под C:\Users, не только
    # этой машины. Не-raw строковый литерал ВНУТРИ мирный.py пытается разобрать «\U» как
    # начало escape `\UXXXXXXXX` (8 hex-знаков) и падает `SyntaxError: truncated \UXXXXXXXX
    # escape» — на КАЖДОМ прогоне из-под C:\Users\..., а не только на этой машине. Заглушка —
    # `r"""..."""`/`r"..."` В ТЕКСТЕ мирный.py (не в этом файле: `f'...'` уже подставляет
    # ЗНАЧЕНИЕ CONTAINER как есть, r-неважен ЗДЕСЬ — важен ТАМ, где строка живёт вторым
    # прогоном). «опасный.py» ниже уже был raw (`Path(r"{CONTAINER}")`) — тем и жил случай
    # ③ на живом контуре <КОНТУР> (там нет «\Users»), пряча беду до чужого каталога.
    if a.break_name == "plain-string":
        benign_text = (
            f'"""Зови так: python {CONTAINER}/vnext-tools/мирный.py --role X"""\n'
            f'import sys\n'
            f'print("подсказка: смотри {CONTAINER}/vnext-tools рядом")\n'
            f'# и в комментарии тоже: {CONTAINER}/vnext-tools\n'
            f'sys.exit(0)\n')
        print(f"⚠️ ПОРЧА «plain-string» ВЗВЕДЕНА — путь в мирный.py обычной (не raw) строкой; "
              f"ждём красного на дереве с «\\U» в пути (эта песочница — как раз такая)\n")
    else:
        benign_text = (
            f'r"""Зови так: python {CONTAINER}/vnext-tools/мирный.py --role X"""\n'
            f'import sys\n'
            f'print(r"подсказка: смотри {CONTAINER}/vnext-tools рядом")\n'
            f'# и в комментарии тоже: {CONTAINER}/vnext-tools\n'
            f'sys.exit(0)\n')
    (source_dir / "мирный.py").write_text(benign_text, encoding="utf-8")

    # ── подопытный ②: тот же путь ВЫЧИСЛЯЕТСЯ кодом. Заглушка здесь — изготовление поломки
    (source_dir / "опасный.py").write_text(
        f'from pathlib import Path\n'
        f'КОРЕНЬ = Path(r"{CONTAINER}") / "vnext-tools"\n'
        f'print(КОРЕНЬ)\n', encoding="utf-8")

    # ── ① перенос кладёт файл обезличенным
    code, output = transfer(["мирный.py"], source_dir, template_dir)
    copy_file = template_dir / "мирный.py"
    remaining = copy_file.read_text(encoding="utf-8").count(CONTAINER) if copy_file.exists() else -1
    case("① перенесённый файл не несёт пути этой машины",
           code == 0 and remaining == 0,
           f"код {code}, вхождений пути {remaining}")

    # ── ② заглушка встала ТУДА ЖЕ, куда её ставит сверка: отпечатки «с точностью до
    #    обезличивания» у источника и копии обязаны совпасть. Это и есть доказательство,
    #    что правило ОДНО, а не два похожих.
    sys.path.insert(0, str(DRIFT_TOOL.parent))
    importlib_util = __import__("importlib").import_module("importlib.util")
    spec = importlib_util.spec_from_file_location("drift", DRIFT_TOOL)
    drift = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(drift)
    # 🩸 ДВЕ РЕДАКЦИИ ЭТОГО СЛУЧАЯ БЫЛИ НЕВЕРНЫ, и обе нашла нарочная поломка, а не глаз:
    #   ① сравнение отпечатков «с точностью до обезличивания» — зелено, когда перенос
    #     не делает НИЧЕГО: сверка обезличивает обе стороны сама;
    #   ② точное совпадение с обезличенным текстом источника — недостижимо и не нужно:
    #     сверка заменяет путь ВЕЗДЕ, а перенос — только в читаемых человеком местах,
    #     и это его смысл, а не изъян.
    # ⇒ Судим то, что и хотели: заглушек ровно столько, сколько путей стояло в читаемых
    #   местах, и вид заглушки ВЗЯТ ИЗ СВЕРКИ. Перенос со своей меткой уронит этот случай,
    #   а случай ① при этом останется зелёным — потому он и различающий.
    placeholders = {m for _, m in drift.PLACEHOLDERS}
    copy_text = copy_file.read_text(encoding="utf-8") if copy_file.exists() else ""
    placeholder_count = sum(copy_text.count(m) for m in placeholders)
    case("② заглушек столько же, сколько путей, и вид заглушки взят ИЗ СВЕРКИ",
           placeholder_count == 3 and placeholders and any(m in copy_text for m in placeholders),
           f"заглушек {placeholder_count} при трёх путях в источнике; виды заглушек — сверкины")

    # ── ③ путь в ИСПОЛНЯЕМОМ месте: отказ, строка названа, файл в образец не попал
    code3, output3 = transfer(["опасный.py"], source_dir, template_dir)
    not_written = not (template_dir / "опасный.py").exists()
    line_named = "строка" in output3 and "ОТКАЗ" in output3
    case("③ путь в исполняемом месте — ОТКАЗ, и строка названа",
           code3 != 0 and not_written and line_named,
           f"код {code3}, в образец не записан: {not_written}, строка названа: {line_named}")

    # ── ③б ВСТРЕЧНЫЙ к ③: мирный файл переносится молча. Без него ③ зелен и у переноса,
    #    который отказывает ВСЕГДА, — а такой перенос бесполезен.
    template_dir2 = stand / "образец2"
    template_dir2.mkdir()          # каталог создаём МЫ: перенос не заводит публичный каталог сам
    code4, _ = transfer(["мирный.py"], source_dir, template_dir2)
    case("③б встречный: файл без исполняемого пути переносится",
           code4 == 0 and (template_dir2 / "мирный.py").exists(),
           f"код {code4}")

    # ── ③в ОТКАЗ СЛОВОМ, А НЕ ПАДЕНИЕМ. Найдено этой же приёмкой: первая редакция переноса
    #    падала трассировкой на несуществующем каталоге, и роль видела семь строк про
    #    внутренности языка вместо одной строки про свой каталог.
    code6, output6 = transfer(["мирный.py"], source_dir, stand / "которого-нет")
    worded = "КАТАЛОГА ОБРАЗЦА НЕТ" in output6 and "Traceback" not in output6
    case("③в каталога образца нет — отказ СЛОВОМ, без падения",
           code6 != 0 and worded,
           f"код {code6}, сказано словом: {worded}")

    # ── ③г БАЙТЫ. Найдено @COORD (записка #4904) на ЖИВОМ переносе, а не на стенде:
    #    первая редакция читала файл байтами, а писала текстом — и каждый «\r\n» доезжал
    #    как «\r\r\n». В образце из 298 файлов испорчен был ровно один: тот единственный,
    #    который успел перенести новый инструмент.
    # ⚡ Почему этого не видела сверка: она нормализует концы строк ПЕРЕД сравнением, то есть
    #    слепа именно к той порче, которую вносил перенос. Правка и проверяющая её сверка
    #    читали ПО-РАЗНОМУ — доказывать надо ПРЯМЫМ сравнением байтов, а не сверкой.
    source_bytes = (source_dir / "мирный.py").read_bytes()
    copy_bytes = copy_file.read_bytes() if copy_file.exists() else b""
    expected_bytes = source_bytes
    for real_path, label in drift.PLACEHOLDERS:
        if real_path:
            expected_bytes = expected_bytes.replace(real_path.encode("utf-8"), label.encode("utf-8"))
    case("③г байты: копия = источник с подставленными заглушками, и ничего больше",
           copy_bytes == expected_bytes,
           "совпало байт в байт" if copy_bytes == expected_bytes
           else f"разошлось: у источника {len(source_bytes)} б, у копии {len(copy_bytes)} б, "
                f"удвоенных концов строк {copy_bytes.count(bytes([13, 13, 10]))}")

    # ── ④ перенесённый файл разбирается: обезличивание не сломало код
    r5 = subprocess.run([sys.executable, "-m", "py_compile", str(copy_file)],
                        capture_output=True, text=True, encoding="utf-8", timeout=120)
    case("④ перенесённый файл разбирается без ошибок",
           r5.returncode == 0, f"код {r5.returncode}")

    # ── ⑤ КОНТРОЛЬ: подопытному было что обезличивать. Без этого случай ① зелен и тогда,
    #    когда пути в файле не было вовсе.
    had_count = (source_dir / "мирный.py").read_text(encoding="utf-8").count(CONTAINER)
    case("⑤ контроль: в подопытном файле путь БЫЛ",
           had_count >= 3, f"вхождений в источнике {had_count}")

    # ── ⑥ ЧУЖАЯ ФОРМА (карточка #626): источник изначально в CRLF, построенной через
    #    mezo_stand.crlf_twin — НЕЗАВИСИМО от того, транслирует ли текущая ОС «\n» в
    #    «\r\n» сама при записи (на Windows write_text() выше это и так делает, и ③г
    #    отчасти уже проверяет CRLF, но лишь СЛУЧАЙНО для этой машины — на другой ОС
    #    источник ③г мог бы остаться чистым \n, и находка карточки #576 при переносе
    #    осталась бы неиспытанной). Тот же признак («копия = источник с заглушками, без
    #    удвоения \r\n») обязан держаться и когда CRLF пришёл НЕ от ОС, а от байт файла.
    crlf_text = (
        f'r"""Зови так: python {CONTAINER}/vnext-tools/мирный_crlf.py --role X"""\n'
        f'import sys\n'
        f'print(r"подсказка: смотри {CONTAINER}/vnext-tools рядом")\n'
        f'sys.exit(0)\n')
    (source_dir / "мирный_crlf.py").write_bytes(mezo_stand.crlf_twin(crlf_text).encode("utf-8"))
    crlf_source_bytes = (source_dir / "мирный_crlf.py").read_bytes()
    # Признак CRLF — часть условия ЭТОГО случая (не отдельный assert: тот прервал бы
    # прогон трассировкой и отключается под python -O; провал обязан звучать своей
    # строкой, не мешая прогону случаев после неё).
    crlf_hits6 = crlf_source_bytes.count(b"\r\n")
    code7, output7 = transfer(["мирный_crlf.py"], source_dir, template_dir)
    copy_file2 = template_dir / "мирный_crlf.py"
    copy_bytes2 = copy_file2.read_bytes() if copy_file2.exists() else b""
    expected_bytes2 = crlf_source_bytes
    for real_path, label in drift.PLACEHOLDERS:
        if real_path:
            expected_bytes2 = expected_bytes2.replace(real_path.encode("utf-8"), label.encode("utf-8"))
    bytes_match6 = copy_bytes2 == expected_bytes2
    case("⑥ источник в CRLF (crlf_twin, не от ОС) — копия = источник с заглушками, без "
         "удвоения \\r\\n",
           code7 == 0 and bytes_match6 and crlf_hits6 > 0,
           (f"стенд несёт CRLF: байтов \\r\\n {crlf_hits6} (crlf_twin); совпало байт в байт"
            if bytes_match6 and crlf_hits6 > 0
            else f"код {code7}; стенд несёт CRLF: байтов \\r\\n {crlf_hits6} (crlf_twin); "
                 f"удвоенных концов строк {copy_bytes2.count(bytes([13, 13, 10]))}"))

    shutil.rmtree(stand, ignore_errors=True)
    red_cases = [item for item, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 2 (③б и ⑤); ③г добавлен по "
          f"находке @COORD; ⑥ добавлен по карточке #626 (CRLF платформонезависимо)")
    print("⚖️ Доказательство порчей — отдельным прогоном рядом: отключение обезличивания")
    print("   роняет ① и ②, «безопасно везде» роняет ③, «каталог не проверяем» роняет ③в.")
    print("   Порча живёт рядом с оригиналом, а не внутри приёмки: иначе приёмка судила бы себя.")
    if a.break_name == "plain-string":
        # ⚡ КАРТОЧКА #630②: встречный случай — эта же приёмка, запущенная из дерева, чей
        # путь содержит «\U» (см. CONTAINER), обязана быть 8 из 8 без порчи и провалиться
        # под порчей «plain-string» — она бьёт РОВНО те случаи, что читают мирный.py как
        # текст ПОСЛЕ его же разбора Python'ом (①②③б③г④); ③, ③в и ⑤ её не видят
        # (опасный.py уже был raw; несуществующий каталог отсекает разбор раньше; ⑤ читает
        # исток тем же питоном, что писал приёмку, — не тем, что разбирает мирный.py заново).
        if red_cases:
            print(f"\n✅ так и надо: под порчей «plain-string» красных {len(red_cases)} из {len(results)}: "
                  f"{' · '.join(red_cases)}")
            return 0
        print(f"\n⚠️ ПОРЧА «plain-string» ВЗВЕДЕНА, А ВСЁ ЗЕЛЁНОЕ — путь дерева не содержит «\\U», "
              f"встречный не поставлен (путь контейнера: {CONTAINER})")
        return 1
    if red_cases:
        print(f"🔴 ПРОВАЛЕНО {len(red_cases)}: {' · '.join(red_cases)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
