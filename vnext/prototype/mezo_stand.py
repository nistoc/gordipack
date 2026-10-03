# -*- coding: utf-8 -*-
"""
mezo_stand.py — временные рабочие каталоги проверок: убрать при успехе, СОХРАНИТЬ при провале.

ЗАЧЕМ. Проверки контура создают временный каталог (копия базы, копия скриптов) и не
убирают его никогда. За неделю 18–24.08.2026 так накопилось 3929 каталогов и 34,77 ГБ,
в них 4717 копий рабочей базы координации — во временном каталоге, куда, кроме владельца
машины, имеют доступ ещё три учётных субъекта. Уборка не сломалась: её не писали.

ЧТО ДАЁТ ЭТОТ ПОМОЩНИК. Прогон прошёл — каталоги удаляются молча (одна строка отчёта).
Прогон провалился — каталоги ОСТАЮТСЯ, и их пути ПЕЧАТАЮТСЯ. Без печати путей
«сохраняем для осмотра» было бы обещанием: найти нужный каталог среди тысяч нельзя.

ИСХОД НЕ ОБЪЯВЛЕН = ПРОВАЛ. Если скрипт умер до вызова finish() — упал с ошибкой, вышел
через raise SystemExit, был прерван — каталоги СОХРАНЯЮТСЯ. Направление выбрано намеренно:
лишний каталог стоит двадцать мегабайт, потерянная обстановка упавшей проверки стоит
повторного прогона вслепую.

КАК ПРИМЕНИТЬ (три правки в файле проверки):
    import mezo_stand                                   # 1. рядом с import mezo_paths

    root = mezo_stand.new("bite-r15a-")                 # 2. вместо
                                                        #    Path(tempfile.mkdtemp(prefix="bite-r15a-"))

    sys.exit(mezo_stand.finish(main()))                 # 3. вместо sys.exit(main())

ЗАПУСК ИНСТРУМЕНТОВ СТЕНДА — только со средой стенда (записка #5096):
    subprocess.run([...], env=mezo_stand.stand_env(root))
Без неё инструмент стенда унаследует MEZO_CONTAINER вызывающего и может писать в чужой контур.

СОХРАНИТЬ ВСЁ, ДАЖЕ ПРИ УСПЕХЕ — переменная окружения MEZO_KEEP_STANDS=1. Нужна, когда
разбираешь зелёный прогон и хочешь посмотреть, на чём он был зелёным.

ХРАНИТСЯ ТОЛЬКО ПОСЛЕДНИЙ ПРОВАЛ ПРИЁМКИ (карточка #657, пункт (3); слово владельца «Б1»
02.10.2026 23:47 UTC, чат OPSSRE; план и два дополнения — комментарии карточки, согласованы
с PROTO записками #5422 и #5437). Замер 24.09: стендов старше суток 4 132, 117 ГБ — каждый
провальный прогон оставлял свои, срока у них не было. Теперь:
  · сохраняя стенд, помощник кладёт В НЕГО метку .mezo_stand_kept: полный путь скрипта ·
    его аргументы · корень MEZO_SCRIPTS_ROOT · вид исхода · путь самого стенда · час UTC ·
    час с долями секунды · номер процесса. Пишется только на выходе — прогону, который
    судит содержимое своего стенда, она не мешает, а идущий прогон метки ещё не имеет;
  · сохраняя стенды, помощник убирает стенды ПРЕЖНЕГО прогона ТОГО ЖЕ вызова — только с
    его меткой. Тот же вызов = тот же полный путь скрипта + те же аргументы + тот же корень
    + тот же рабочий каталог: «--break», другой --helper или bite-all с другим --target —
    это другой вызов, и настоящий провал чистого прогона им не стирается (возврат PROTO,
    записка #5452, П1). Рабочий каталог — потому что относительный путь в аргументах из
    другого каталога значит другой файл. Имя файла ключом не служит: тот же bite-x.py из
    пакета у соседнего контура — чужой;
  · провал убирает только прежний ПРОВАЛ; отказ мерить (код 2) и падение убирают только
    прежние отказы и падения — отказ доказывает меньше провала и не вправе стирать его (П2);
  · убираются только метки, поставленные РАНЬШЕ начала этого прогона: из двух параллельных
    прогонов хранится тот, что кончил последним, лишь если он и начал позже (П3);
  · каталог БЕЗ метки не трогается никогда: так выглядит прогон, идущий прямо сейчас, и всё,
    накопленное до этой правки (его убирает janitor-stands.py рукой владельца); метка,
    указывающая на другой каталог (копия стенда рядом), — тоже; ссылка (junction) — тоже;
    занятый каталог (пробное переименование не прошло) не трогается вовсе, а не по частям;
  · стенды, оставленные по MEZO_KEEP_STANDS, не убираются и сами никого не убирают;
  · успех прежний провал НЕ убирает (успешный прогон не доказывает, что сохранённый провал
    больше не нужен), а называет: «стенды прежних неудачных прогонов этого вызова сохранены: N»;
  · код 2 (приёмка отказалась мерить) хранится, но называется своими словами — «прогон
    отказался мерить»;
  · прогон нарочной поломки, чьё ожидание ПОДТВЕРДИЛОСЬ (код 1), — не провал для уборки:
    приёмка зовёт expected_break(), и стенд убирается как при успехе. Код выхода приёмки не
    меняется. При любом другом коде объявление не действует.
⚖️ Границы: кандидатов на уборку ищу среди каталогов с теми же началами имён, что у стендов
этого прогона (полный обход %TEMP% — около 2 с на 21 тыс. каталогов, замер 02.10). Начало
имени, которым этот прогон не пользовался, не смотрится — его стенды остаются до
janitor-stands.py. Инструмент, запущенный С КОПИИ на стенде, каждый раз имеет новый путь —
его прогоны между собой не связываются. Обе стороны безопасные: лишний каталог.
"""
import ast
import atexit
import datetime as dt
import gc
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
from pathlib import Path

__all__ = ["new", "release", "finish", "keep_reason", "copy_tool", "neighbours_of", "stand_env",
           "snapshot_db", "crlf_twin", "expected_break"]

_stands: list[Path] = []
_prefixes: set[str] = set()           # начала имён, которыми этот прогон заводил стенды
_verdict: bool | None = None          # None — исход не объявлен, считаем провалом
_exit_code: int | None = None         # код, объявленный finish(): различает отказ (2) и провал
_expected_break = False               # приёмка объявила: ожидание нарочной поломки подтвердилось
_ALWAYS_KEEP = os.environ.get("MEZO_KEEP_STANDS", "").strip().lower() in ("1", "yes", "true", "да")
KEPT_MARKER = ".mezo_stand_kept"      # имя метки внутри сохранённого стенда (с точкой — служебное)
_KIND_KEEP_ENV = "keep_env"           # вид исхода в метке: сохранено по MEZO_KEEP_STANDS
_KIND_GROUPS = {"failed": "failed", "refused": "other", "undeclared": "other"}  # кто кого вправе убрать
_MKDTEMP_SUFFIX = 8                   # tempfile.mkdtemp дописывает к началу имени 8 случайных знаков
_RUN_STARTED = time.time()            # час начала прогона: убираются только метки, поставленные раньше


def new(prefix: str) -> Path:
    """Создать временный рабочий каталог. Дальше он убирается сам — по исходу прогона."""
    p = Path(tempfile.mkdtemp(prefix=prefix))
    _stands.append(p)
    _prefixes.add(prefix)
    return p


def release(path) -> None:
    """Заменяет `shutil.rmtree(path, ignore_errors=True)` в блоке finally.

    Не удаляет каталог прямо сейчас, а откладывает решение до исхода прогона: при
    успехе он будет убран, при провале — сохранён и напечатан. Нужен там, где уборка
    УЖЕ написана и стои́т в finally: такая уборка честно убирает и при провале тоже,
    то есть уносит обстановку, ради осмотра которой её и сохраняли бы.
    """
    p = Path(path)
    if p not in _stands:
        _stands.append(p)
    # Начало имени здесь не передано — выводим его так, как его строит tempfile.mkdtemp
    # (начало + 8 случайных знаков). Вывод неверен — кандидатов просто не найдётся:
    # уборка дополнительно требует метку того же скрипта, лишнего она не тронет.
    if len(p.name) > _MKDTEMP_SUFFIX:
        _prefixes.add(p.name[:-_MKDTEMP_SUFFIX])


def stand_env(container, **extra) -> dict:
    """Среда для запуска инструментов НА СТЕНДЕ: MEZO_CONTAINER — сам стенд, остальное — как у вызывающего.

    ЗАЧЕМ (замер OPSSRE 13.09, записка #5093; решение PROTO, записка #5096). Инструменты
    ищут «живой» контур СНАЧАЛА по переменной MEZO_CONTAINER и лишь потом — по своему
    расположению. Приёмка, запускающая инструменты стенда без своей среды, отдаёт им среду
    вызывающего: у кого MEZO_CONTAINER указывает на другой контур, у того update-tools.py
    стенда пишет в ЧУЖУЮ базу, а guard-all.py судит смесь двух контуров.
    Направление закрепляет ЗАПУСКАЮЩИЙ, а не mezo_paths: среду ставят нарочно, чтобы
    направить инструменты на песочницу, и отнимать это у среды нельзя.

    extra — переменные поверх (например, PYTHONIOENCODING="utf-8").
    """
    env = dict(os.environ, MEZO_CONTAINER=str(container))
    env.update(extra)
    return env


def neighbours_of(tool) -> list[Path]:
    """Файлы-соседи, без которых инструмент не запустится, — ТРАНЗИТИВНО.

    Сосед — это модуль, подключаемый по голому имени, файл которого лежит в ТОМ ЖЕ
    каталоге, что и сам инструмент. Стандартная библиотека и установленные пакеты
    соседями не считаются: они едут вместе с языком, а не с каталогом.

    Обход транзитивный намеренно: у нас `read-messages.py` тянет `backlog_view.py`,
    а тот — `backlog.py`, а тот ещё четверых. Обход на один шаг привёз бы первого
    и оставил падение на втором — то есть починил бы вид, а не беду.
    """
    tool = Path(tool)
    folder = tool.parent
    siblings = {p.stem: p for p in folder.glob("*.py")}
    found: dict[str, Path] = {}
    queue = [tool]
    seen = {tool.stem}
    while queue:
        source = queue.pop()
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue          # нечитаемое или неразбираемое молча пропускаем: это не наша беда
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            else:
                continue
            for root in roots:
                if root in siblings and root not in seen:
                    seen.add(root)
                    found[root] = siblings[root]
                    queue.append(siblings[root])
    return [found[k] for k in sorted(found)]


def copy_tool(tool, dest) -> Path:
    """Скопировать инструмент на стенд ВМЕСТЕ с его соседями. Вернуть путь копии.

    ⚡ ЗАЧЕМ ЭТО ЕСТЬ (карточка #572, находка @COORD внутри приёмки карточки #571):
    инструмент, вынесенный на стенд ОДНИМ файлом, падает словами «нет такого модуля» —
    и это сообщение одинаково звучит и когда пакета языка вправду нет, и когда сосед
    просто не поехал вместе с копией. Разбирать его должен был человек.
    📏 Замер 2026-09-05: поодиночке не работают 43 инструмента из 60 в .mezosync/scripts
    и 155 из 188 в vnext-tools ⇒ копирование одного файла ломает инструмент ЧАЩЕ, чем нет.

    ⚖️ ЧЕГО ЭТА ФУНКЦИЯ НЕ ДЕЛАЕТ: она не чинит уже написанные приёмки, которые копируют
    файл своей рукой, — их 62. Там отказ остаётся прежним. Функция закрывает дорогу
    НОВЫМ стендам и даёт старым дешёвый способ перейти: одна строка вместо одной.
    """
    tool = Path(tool)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = dest / tool.name
    shutil.copy2(tool, copied)
    for neighbour in neighbours_of(tool):
        target = dest / neighbour.name
        if not target.exists():
            shutil.copy2(neighbour, target)
    return copied


def snapshot_db(src, dst) -> Path:
    """Согласованная копия БД РЕЗЕРВНЫМ КОПИРОВАНИЕМ библиотеки sqlite3, не копированием файла.

    ЗАЧЕМ (карточка #505, два живых случая). Живая база работает в режиме WAL: свежие
    записи лежат в mezosync.db-wal РЯДОМ с основным файлом, а копирование ОДНОГО
    основного файла (shutil.copy/copy2/copyfile) даёт РВАНЫЙ снимок — то, что ещё не
    перенесено из журнала в основной файл, в копию не попадает. Копия при этом НЕ
    отказывает и не портится: она открывается, отвечает на запросы и молча отдаёт
    СТАРОЕ состояние — признаков неисправности нет ни одного.
        · 30.08 (карточка #493 → заведена #505): bite-phoenix-truncation-named.py,
          скопированный сразу после чужой записи в живую базу, дал 5 из 7 — красные
          случаи выглядели как «работа не сделана»; тот же прогон БЕЗ единой правки
          через 6 минут дал 7 из 7.
        · 13.09 (второй живой случай, усилитель критерия): снятие объявления о правке
          на write-message.py осталось в -wal при держащем читателе; копия ОДНОГО
          основного файла видела released_at=None, bite-duplicate-note.py — 🔴 4 провала
          из 5 случаев; после сброса журнала на ТОЙ ЖЕ базе — 5 из 5 без единой правки кода.
    Проверка, построенная на такой копии, красна по ПОСТОРОННЕЙ причине, и её красное
    неотличимо от настоящей находки — дороже пропуска: пропуск теряет одну находку,
    ложное красное учит не верить проверке целиком.

    ПОЧЕМУ НЕ КОПИРОВАНИЕ ФАЙЛА: sqlite3 Connection.backup() снимает согласованный
    снимок ПОД СВОЕЙ БЛОКИРОВКОЙ ЧТЕНИЯ и сам переносит хвост журнала в цель — штатный
    способ самой библиотеки, а не обходной трюк; тот же приём уже стоит в
    sandbox-bootstrap.py (снятие песочницы из живой базы) — здесь он ОДНО общее место
    для приёмок, а не изобретение нового.

    src открывается СТРОГО НА ЧТЕНИЕ (`file:...?mode=ro`, URI) — функция никогда не
    пишет в источник, даже если он живой.

    ⚖️ ПРАВКА ПО ВОЗВРАТУ PROTO (возврат по карточке #505, ошибка была в самой
    заявке п.2 — «если цель уже есть — отказ»): цель, КОТОРАЯ УЖЕ БАЗА SQLITE, теперь
    получает снимок ПОВЕРХ СЕБЯ, а не отказ. `sqlite3.connect(dst)` открывает
    существующий файл (вместе с его СОБСТВЕННЫМ журналом, если он есть — библиотека
    разбирается с ним сама при открытии, руками -wal/-shm рядом с целью не трогаем);
    backup() заменяет содержимое ЦЕЛИКОМ и СОГЛАСОВАННО, тем же приёмом, что и для
    новой цели. Это ровно то, что раньше давал `shutil.copy` (перезапись), но БЕЗ его
    беды — старое содержимое цели (и её собственный незаписанный хвост, если был)
    после снимка не остаётся, там ровно состояние источника.
    ⛔ ОТКАЗ ОСТАЁТСЯ — но ТОЛЬКО когда существующая цель НЕ база SQLite (текстовый
    файл, чужой формат, повреждённый файл): исключение библиотеки при попытке снять
    снимок перехватывается и называется словами вместе с путём; ЭТОТ файл при отказе
    не трогается — снимать поверх мусора нельзя, а угадывать, что с ним делать, не
    дело этой функции.

    ЧЕГО ФУНКЦИЯ НЕ ДЕЛАЕТ: не создаёт родительские каталоги цели (это забота
    вызывающего — обычно уже сделано mezo_stand.new()); не копирует файлы -wal/-shm
    КАК ФАЙЛЫ — backup() переносит их содержимое ВНУТРЬ целевого основного файла;
    не проверяет заранее, база ли цель, — просто пробует снять снимок и честно
    называет причину, если не вышло.
    """
    src = Path(src)
    dst = Path(dst)
    src_conn = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(dst))
    try:
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        except sqlite3.DatabaseError as e:
            raise SystemExit(
                f"ERR: snapshot_db: цель существует, но не открывается как база SQLite: {dst}\n"
                f"     {e}\n"
                f"     Файл НЕ ТРОНУТ. Если он не нужен — убери его сам и повтори."
            )
    finally:
        src_conn.close()
        dst_conn.close()
    return dst


def crlf_twin(text: str) -> str:
    """CRLF-двойник опытного текста — та же строка с окончаниями строк Windows ("\\r\\n").

    ЗАЧЕМ (карточка #626, три случая одного дня 14.09: #609 · #505 · #617). Приёмка
    обычно строит мир опыта в форме СВОЕГО АВТОРА — пишет файлы контура так, как пишет
    сама (обычно "\\n"), и её зелёное свидетельствует только про эту форму, а не про
    предмет. Контуры на Windows (core.autocrlf=true) держат рабочие файлы в CRLF;
    встречный случай «тот же опыт, файлы контура в чужой форме» — общая проверка, что
    подопытный инструмент судит СОДЕРЖИМОЕ, а не байты конкретной записи.

    Сначала текст СВОДИТСЯ к "\\n" (на случай уже смешанных/CRLF окончаний на входе),
    и только потом "\\n" → "\\r\\n" — иначе повторный прогон по уже-CRLF-тексту задвоил
    бы разделитель ("\\r\\r\\n"), как в живой находке @COORD (карточка #576, записка
    #4904): перенос в образец читал байтами, писал текстом, и Windows-запись сама
    превращала "\\n" в "\\r\\n" поверх уже бывшего "\\r\\n".
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n")


def finish(code: int) -> int:
    """Объявить исход прогона. Возвращает тот же код — чтобы писалось одной строкой.

    Ноль — успех, каталоги убираются. Любое другое число — провал, каталоги остаются.
    Код 2 — приёмка отказалась мерить: каталоги остаются так же, но называется это своими словами.
    """
    global _verdict, _exit_code
    _verdict = (code == 0)
    _exit_code = code
    return code


def expected_break() -> None:
    """Приёмка объявляет: это прогон нарочной поломки, и её ожидание ПОДТВЕРДИЛОСЬ.

    ЗАЧЕМ (дополнение-2 к плану карточки #657, согласовано с PROTO запиской #5437). Прогон
    с --break кончается кодом 1, хотя приёмка сделала свою работу: поломка поймана ровно так,
    как записано заранее. Замер 02.10 22:43–22:47 UTC: два круга по 27 поломок одной приёмки
    оставили 54 стенда, ≈4 ГБ, 54 копии живой базы. Хранить обстановку подтверждённой
    поломки незачем — разбирать в ней нечего.
    Код выхода приёмки этим НЕ меняется: его читают общий прогон и сверка поломок. Меняется
    только решение о стенде. Ожидание НЕ подтвердилось — не зови: стенд сохранится как провал.
    Объявление без finish() не действует: упавший прогон сохраняется всегда. Действует только
    при коде 1 — подтверждённая поломка кончается им; при коде 2 (отказ мерить) стенд
    сохраняется, даже если объявление прозвучало (находка PROTO, возврат карточки #657).
    """
    global _expected_break
    _expected_break = True


def _break_confirmed() -> bool:
    """Ожидание нарочной поломки подтвердилось и прогон кончился кодом 1."""
    return _expected_break and _exit_code == 1


def _outcome_kind() -> str:
    """Вид исхода для метки: keep_env · undeclared · refused · failed."""
    if _ALWAYS_KEEP:
        return _KIND_KEEP_ENV
    if _verdict is None:
        return "undeclared"
    return "refused" if _exit_code == 2 else "failed"


def keep_reason() -> str | None:
    """Почему каталоги будут сохранены; None — если будут убраны. Для проверок этого помощника."""
    if _ALWAYS_KEEP:
        return "указано переменной окружения MEZO_KEEP_STANDS"
    if _verdict is None:
        return "исход прогона не объявлен (падение или прерывание) — сохранено на всякий случай"
    if _verdict is False and not _break_confirmed():
        return "прогон отказался мерить" if _exit_code == 2 else "прогон провалился"
    return None


def _script_key() -> str | None:
    """Полный путь запущенного скрипта — ключ «тот же скрипт». None — скрипта-файла нет.

    Берётся при ЗАГРУЗКЕ помощника: к выходу скрипт мог сменить рабочий каталог, и
    относительный sys.argv[0] указал бы не туда.
    """
    main = sys.argv[0] if sys.argv else ""
    if not main or main in ("-c", "-m"):
        return None
    p = Path(main)
    if not p.is_file():
        return None
    return os.path.normcase(str(p.resolve()))


def _norm(path) -> str:
    """Путь для сравнения внутри одного прогона: абсолютный, регистр и разделители сведены."""
    return os.path.normcase(os.path.abspath(path))


def _real(path) -> str:
    """Путь для сравнения МЕЖДУ прогонами: короткое имя 8.3 и длинное сводятся к одному."""
    return os.path.normcase(os.path.realpath(path))


def _call_key() -> dict | None:
    """Ключ «тот же вызов»: скрипт · аргументы · корень MEZO_SCRIPTS_ROOT · рабочий каталог.
    None — скрипта-файла нет.

    ЗАЧЕМ АРГУМЕНТЫ И КОРЕНЬ (возврат PROTO, карточка #657, П1): ключом по одному скрипту
    режимы одной приёмки сливались — чистый провал стирался прогоном с --break (у четырёх
    приёмок подтверждённая поломка кончается кодом 1), с другим --helper или bite-all с
    другим --target. Рабочий каталог — потому что относительный путь в аргументах
    (--helper mezo_stand.py.bak) из другого каталога значит другой файл.
    Берётся при ЗАГРУЗКЕ помощника: к выходу скрипт мог сменить рабочий каталог.
    """
    script = _script_key()
    if script is None:
        return None
    root = os.environ.get("MEZO_SCRIPTS_ROOT", "")
    try:
        cwd = _real(os.getcwd())
    except OSError:
        cwd = ""
    return {
        "script": script,
        "args": json.dumps(sys.argv[1:], ensure_ascii=True),
        "root": _real(root) if root else "",
        "cwd": cwd,
    }


_CALL_KEY = _call_key()


def _read_marker(path: Path) -> dict | None:
    """Метка сохранённого стенда как словарь; None — метку прочитать нельзя (такой стенд не трогаем)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fields = {}
    for line in text.splitlines():
        name, sep, value = line.partition("=")
        if sep:
            fields[name.strip()] = value.strip()
    return fields if fields.get("script") else None


def _is_link(entry: os.DirEntry) -> bool:
    """Ссылка на каталог (symlink или junction). Её не трогаем и не считаем: удаление убрало бы
    саму ссылку, а счётчик назвал бы стенд убранным при целой цели (находка PROTO, #657)."""
    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _previous_kept(call: dict, kinds, before: float | None) -> list[Path]:
    """Сохранённые стенды ПРЕЖНИХ прогонов того же вызова с исходом из kinds.

    Отбор: метка читается · вызов совпал по всем полям ключа · метка указывает на СВОЙ
    каталог (stand=), а не на тот, с которого её скопировали · не ссылка. before — брать
    только метки, поставленные раньше этого часа (начала прогона); None — без отбора по часу.
    Ищутся рядом со стендами этого прогона и только среди имён с теми же началами
    (полный обход %TEMP% слишком дорог для каждого прогона — см. шапку).
    """
    prefixes = [p for p in _prefixes if p]
    if not prefixes:
        return []
    current = {_norm(p) for p in _stands}
    found = []
    for parent in {p.parent for p in _stands}:
        try:
            with os.scandir(parent) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            if not any(entry.name.startswith(pr) for pr in prefixes):
                continue
            try:
                if _is_link(entry) or not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if _norm(entry.path) in current:
                continue
            marker = _read_marker(Path(entry.path) / KEPT_MARKER)
            if marker is None or marker.get("kind") not in kinds:
                continue
            if any(marker.get(name) != value for name, value in call.items()):
                continue
            if marker.get("stand") != _real(entry.path):
                continue
            if before is not None:
                try:
                    if float(marker.get("at_ts", "")) >= before:
                        continue
                except ValueError:
                    continue
            found.append(Path(entry.path))
    return sorted(found)


def _write_markers(call: dict, kind: str, why: str) -> list[Path]:
    """Положить метку в каждый сохраняемый стенд. Вернуть стенды, куда положить не удалось."""
    now = time.time()
    stamp = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    failed = []
    for p in _stands:
        if not p.is_dir():
            continue
        fields = dict(call, kind=kind, stand=_real(p), reason=why, at=stamp,
                      at_ts=repr(now), pid=str(os.getpid()))
        body = "".join(f"{name}={value}\n" for name, value in fields.items())
        try:
            (p / KEPT_MARKER).write_text(body, encoding="utf-8")
        except OSError:
            failed.append(p)
    return failed


def _force_writable(func, path, _exc):
    """Windows не даёт удалить файл, помеченный только для чтения. Снять метку и повторить."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        raise


def _remove_all(paths) -> tuple[int, list[Path]]:
    """Убрать каталоги с повторами. Вернуть (сколько убрано, какие остались)."""
    # ⚠️ Windows не даёт удалить каталог, пока внутри открыт файл. Проверки почти все
    # работают с базой и соединение обычно НЕ закрывают явно — на момент уборки оно ещё
    # живо. Сборка мусора закрывает такие соединения (у них есть финализатор), поэтому
    # сначала зовём её, а потом делаем несколько заходов с крошечной паузой: файл
    # освобождается не мгновенно. Замер 2026-08-24: без этого спотыкались 16 проверок
    # из 51 — и уборка честно печатала предупреждение, которого раньше не было.
    gc.collect()
    removed = 0
    remaining = []
    for p in paths:
        for attempt in range(4):
            try:
                shutil.rmtree(p, onerror=_force_writable)
                removed += 1
                break
            except OSError:
                if attempt == 3:
                    remaining.append(p)
                else:
                    time.sleep(0.15)
    return removed, remaining


def _remove_previous(paths) -> tuple[int, list[Path]]:
    """Убрать стенды прежних прогонов. Вернуть (сколько убрано, какие не тронуты или остались).

    Сначала ПРОБНОЕ ПЕРЕИМЕНОВАНИЕ: Windows не даёт переименовать каталог, в котором открыт
    файл. Занятый стенд (его как раз осматривают) так не трогается вовсе — раньше удаление
    выпотрашивало его частично: метка и часть файлов уходили, а остаток без метки этот
    механизм больше не убрал бы (находка PROTO, возврат карточки #657). Если удаление
    переименованного всё же споткнётся, остаток носит другое имя, а его метка указывает на
    прежнее — следующие прогоны его не тронут, его уберёт janitor-stands.py.
    """
    removed = 0
    left = []
    for p in paths:
        probe = p.with_name(f"{p.name}.removing-{os.getpid()}")
        try:
            os.rename(p, probe)
        except OSError:
            left.append(p)
            continue
        done, rest = _remove_all([probe])
        removed += done
        left.extend(rest)
    return removed, left


def _after_keep(why: str) -> None:
    """Сохраняя стенды: убрать прежний прогон того же вызова с тем же исходом и пометить нынешний."""
    kind = _outcome_kind()
    if _CALL_KEY is None:
        print("   метка не поставлена: скрипт не файл (python -c, импорт) — прежние стенды не убираются")
        return
    if kind == _KIND_KEEP_ENV:
        print("   по MEZO_KEEP_STANDS прежние стенды этой приёмки не убираются")
    else:
        # Провал убирает только прежний провал; отказ мерить и падение — только прежние
        # отказы и падения: отказ доказывает меньше провала и стирать его не вправе (П2).
        group = _KIND_GROUPS[kind]
        kinds = {k for k, g in _KIND_GROUPS.items() if g == group}
        removed, left = _remove_previous(_previous_kept(_CALL_KEY, kinds, before=_RUN_STARTED))
        if removed or left:
            label = "провала" if group == "failed" else "отказа или падения"
            print(f"🧹 стендов прежнего {label} этого вызова убрано: {removed}"
                  + (f" · занято, не тронуто: {len(left)}" if left else ""))
        for p in left:
            print(f"   {p}")
    for p in _write_markers(_CALL_KEY, kind, why):
        print(f"   ⚠️ метку положить не удалось — этот стенд следующим прогоном не уберётся: {p}")


@atexit.register
def _at_exit() -> None:
    if not _stands:
        return
    why = keep_reason()
    if why is not None:
        print(f"\n📂 Временные рабочие каталоги СОХРАНЕНЫ ({why}) — всего {len(_stands)}:")
        for p in _stands:
            print(f"   {p}")
        print("   Осмотрите и удалите; старые уберёт janitor-stands.py.")
        _after_keep(why)
        return
    removed, remaining = _remove_all(_stands)
    print(f"🧹 убрано временных каталогов: {removed}"
          + (f" · занято другим процессом, останутся до уборки janitor-stands.py: {len(remaining)}"
             if remaining else "")
          + (" (ожидание нарочной поломки подтвердилось — для уборки это не провал)"
             if _verdict is False and _break_confirmed() else ""))
    for p in remaining:
        print(f"   {p}")
    if _CALL_KEY is not None:
        previous = _previous_kept(_CALL_KEY, set(_KIND_GROUPS), before=None)
        if previous:
            print(f"📂 стенды прежних неудачных прогонов этого вызова сохранены: {len(previous)} "
                  f"(успех их не убирает; старые уберёт janitor-stands.py)")
