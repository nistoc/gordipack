#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard-control-chars.py — невидимые управляющие байты в текстовых файлах.

ОТКУДА: передан контуром AIA 2026-09-15 (мост aia-atlas, handover-0915; их находка
STUD-A, записка #5223). Взят в пакет и в общий прогон проверок по слову владельца
2026-09-15 14:05:59 UTC («бери guard-control-chars.py в пакет», карточка #643 ⑤).
Разбор перед взятием — там же, карточка #643: инструмент общий, привязки к AIA в нём нет.

ЧТО ПРОВЕРЯЕТ: ищет в текстовых файлах управляющие байты ниже 0x20 (кроме табуляции,
перевода строки и окончания строки Windows) — в тексте они невидимы, а исполнение ломают.

ПОВОД (2026-09-10, их находка): находка STUD-A (записка #5223) плюс четыре промаха того же дня.
Обратный слэш в ПЕРЕДАВАЕМОМ коде уполовинивается слоем вызова даже внутри закавыченного
блока, и одиночный слэш перед буквой b питон истолковывает как байт 0x08 (backspace).
Ущерб двойной: цитата образца перестаёт совпадать с живым образцом дословно, И последующая
точная правка отказывает словами «строка не найдена», не назвав причину.

ПОЧЕМУ НЕ ПОИСК ПО ОБРАЗЦУ: поиск с обратными слэшами возвращает тишину, которую легко
прочесть как «чисто» (у нуля два слова). Обходить надо по КОДУ БАЙТА.

ДВЕ МЕРКИ, обе печатаются, и печатается их РАЗНИЦА:
  ① по байтам — видит окончание строки Windows (0x0d);
  ② по знакам после чтения текстом — окончания строк приведены к одному виду, поэтому
     0x0d ей НЕВИДИМ по построению.
Без названной разницы читатель не узнает, какая мерка чего не видит.

ЧТО НЕ СУДИТ: 0x0a (перевод строки), 0x09 (табуляция), 0x0d (окончание строки Windows) —
законны: файл, у которого нашлась ТОЛЬКО пара CR LF, находкой не считается — ни как
«мина» по низкой мерке (scan_bytes), ни как «находка» на выходе run(). Всё прочее ниже
0x20 — мина. Двоичные файлы в обход не попадают: отбор по расширению, а не по содержимому.
Каталог .git пропускается.

ГРАНИЦА (чего не проверяет ВООБЩЕ, названо, чтобы «мин нет» не читалось шире замера):
невидимые знаки ВЫШЕ 0x20 — неразрывный пробел, знак нулевой ширины, метку порядка байтов.
Это другой предмет: они законны в тексте и судить их по коду нельзя.

ЛЕЧЕНИЕ — ДВА РАЗНЫХ, И ПУТАТЬ ИХ НЕЛЬЗЯ (замер 2026-09-10 на трёх живых минах):
  --unescape   вернуть ДВА знака: слэш и букву (0x07 → слэш+a, 0x08 → слэш+b, 0x0b → слэш+v,
               0x0c → слэш+f, 0x1b → слэш+e). Это верное лечение для мины, РОЖДЁННОЙ
               уполовиниванием: там, где стои́т один байт, автор писал два знака.
  --fix        просто удалить байт. Верно ТОЛЬКО когда байт не заменял никакого текста.
               На трёх найденных минах удаление дало бы правдоподобно НЕВЕРНЫЙ текст:
               путь «C:(слэш)guts(слэш).atlas(слэш)aia-social-demo» превратился бы
               в «.atlasia-social-demo», а граница слова в образце поиска исчезла бы совсем.
Поэтому --fix на байтах из набора (7, 8, 11, 12, 27) ОТКАЗЫВАЕТ и называет --unescape.

⚖️ ПО УМОЛЧАНИЮ ИНСТРУМЕНТ ТОЛЬКО ЧИТАЕТ: без --fix и без --unescape ни один байт файла
не трогается — лечение включается ЛИШЬ явным флагом. Из общего прогона проверок (guard-all)
инструмент зовётся БЕЗ этих флагов — только чтение.

Код возврата: 0 — мин нет · 1 — есть · 2 — негодный вход (ни одного читаемого файла).

Вызов:
    python guard-control-chars.py <каталог-или-файл> [...] [--unescape | --fix]
    python guard-control-chars.py                       # без пути — свои каталоги по умолчанию
    python guard-control-chars.py --selftest
"""
import inspect
import pathlib
import sys
import tempfile

LEGIT = (10, 9, 13)
EXT = (".md", ".py", ".txt", ".json", ".yml", ".yaml", ".sql", ".cs", ".ts", ".tsx", ".sh")


def default_scan_targets(this_file: pathlib.Path) -> list:
    """Свои каталоги ПО УМОЛЧАНИЮ (когда путь не назван) — вычисляются от расположения
    ЭТОГО файла, а не впечатаны: ни одного пути AIA или машины в исполняемых строках.

    Работают ОБЕ раскладки — тот же приём, каким tool() в guard-all.py ищет звенья
    по обе стороны (раскладка контейнера / раскладка пакета), только наоборот: там
    ищут, ГДЕ лежит звено, здесь — что звену смотреть по умолчанию.
      · раскладка контейнера: этот файл лежит в `<контейнер>/vnext-tools/…`,
        сосед — `<контейнер>/.mezosync/scripts`;
      · раскладка пакета: этот файл лежит в `<пакет>/vnext/prototype/…`,
        сосед — `<пакет>/scripts`.
    Кандидат, которого нет на диске, молча пропускается — а не отказывает: это ЦЕЛИ
    обхода, а не обязательный корень координации (в отличие от mezo_paths.container_root,
    здесь несуществующий кандидат не повод для громкого ERR — просто пусто по нему).
    """
    here = this_file.resolve().parent
    candidates = (
        here,                                    # сам каталог инструмента
        here.parent / ".mezosync" / "scripts",    # раскладка контейнера: сосед vnext-tools
        here.parent.parent / "scripts",           # раскладка пакета: сосед vnext/
    )
    seen, out = set(), []
    for c in candidates:
        if c.is_dir() and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def scan_bytes(data: bytes) -> dict:
    """Мины по КОДУ БАЙТА. Возвращает {код: сколько}. Законные байты пропускаются."""
    out = {}
    for code in set(data):
        if code < 32 and code not in LEGIT:
            out[code] = data.count(code)
    return out


def scan_text(data: bytes) -> dict:
    """Та же проверка ПОСЛЕ чтения текстом — вторая мерка. 0x0d ей невидим по построению."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    text = text.replace(chr(13) + chr(10), chr(10))
    out = {}
    for ch in set(text):
        if ord(ch) < 32 and ord(ch) not in LEGIT:
            out[ord(ch)] = text.count(ch)
    return out


def files_of(paths):
    """Файлы обхода: отбор по расширению, каталог .git пропускается."""
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in EXT and ".git" not in f.parts:
                    yield f


ESCAPED = {7: "a", 8: "b", 11: "v", 12: "f", 27: "e"}


def clean(data: bytes) -> bytes:
    """Вычистить мины, сохранив законные байты. Верно лишь там, где байт не заменял текста."""
    return bytes(c for c in data if c >= 32 or c in LEGIT)


def unescape(data: bytes) -> bytes:
    """Вернуть ДВА знака вместо одного байта: слэш и букву. Лечение мины от уполовинивания."""
    out = bytearray()
    for c in data:
        if c in ESCAPED:
            out.extend(chr(92).encode("utf-8"))
            out.extend(ESCAPED[c].encode("utf-8"))
        else:
            out.append(c)
    return bytes(out)


def run(paths, fix: bool, unesc: bool = False) -> int:
    seen = 0
    crlf_files = 0
    hits = []
    disagree = []
    refused = []
    for f in files_of(paths):
        seen += 1
        data = f.read_bytes()
        if 13 in data:
            crlf_files += 1
        mines = scan_bytes(data)
        by_text = scan_text(data)
        if {k: v for k, v in mines.items() if k != 13} != by_text:
            disagree.append((f, mines, by_text))
        if mines:
            hits.append((f, mines))
            if unesc:
                f.write_bytes(unescape(data))
            elif fix:
                if any(c in ESCAPED for c in mines):
                    refused.append((f, sorted(c for c in mines if c in ESCAPED)))
                else:
                    f.write_bytes(clean(data))
    if seen == 0:
        print("ОТКАЗ: ни одного читаемого файла по этим путям — судить нечего, и это не ноль")
        return 2
    print("прочитано файлов: " + str(seen) + " · с окончанием строки Windows: " + str(crlf_files))
    for f, mines, by_text in disagree:
        print("МЕРКИ РАСХОДЯТСЯ " + str(f) + " — по байтам " + str(mines)
              + ", по знакам " + str(by_text) + " (ожидалось совпадение вне 0x0d)")
    if not hits:
        print("НАЙДЕНО МИН: 0 — это «обход по коду байта прошёл, чисто», а НЕ «не искал»")
        print("разница двух мерок: только 0x0d в " + str(crlf_files) + " файлах — по знакам он"
              + " невидим, по байтам виден; иных расхождений " + str(len(disagree)))
        print("НЕ проверялось: невидимые знаки выше 0x20 (неразрывный пробел, нулевая ширина,"
              + " метка порядка байтов) — другой предмет, по коду не судятся")
        return 0
    refused_set = {f for f, _ in refused}
    for f, mines in hits:
        codes_summary = ", ".join(hex(c) + ": " + str(n) for c, n in sorted(mines.items()))
        healed = (unesc or fix) and f not in refused_set
        hint = ""
        if not (unesc or fix):
            recoverable = [c for c in mines if c in ESCAPED]
            hint = ("  — вернуть слэш и букву: --unescape" if recoverable
                     else "  — байт текста не заменял: --fix")
        print(("ВЫЛЕЧЕНО " if healed else "МИНА ") + str(f) + " — " + codes_summary + hint)
    for f, codes in refused:
        print("ОТКАЗ --fix " + str(f) + " — байты "
              + ", ".join(hex(c) for c in codes)
              + " рождены уполовиниванием: удаление потеряло бы ДВА знака вместо одного."
              + " Лечить словом --unescape")
    print("файлов с минами: " + str(len(hits)) + " из " + str(seen)
          + (" · вылечено " + str(len(hits) - len(refused)) if (unesc or fix) else "")
          + (" · отказано " + str(len(refused)) if refused else ""))
    if refused:
        return 1
    return 0 if (unesc or fix) else 1


def selftest() -> int:
    """Контрасты щупают ГРАНИЦУ: законный байт не должен стать миной, двоичный файл не должен
    попасть в обход, негодный вход обязан дать ОТКАЗ кодом 2, а не ноль."""
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / "чистый.md").write_bytes("строка".encode("utf-8") + bytes([10]))
        (d / "windows.md").write_bytes("строка".encode("utf-8") + bytes([13, 10]))
        (d / "мина.md").write_bytes("до".encode("utf-8") + bytes([8]) + "после".encode("utf-8"))
        (d / "двоичный.png").write_bytes(bytes([8, 8, 8]))
        (d / "табуляция.md").write_bytes("до".encode("utf-8") + bytes([9]) + "после".encode("utf-8"))

        if scan_bytes((d / "мина.md").read_bytes()) != {8: 1}:
            fails.append("мина 0x08 не найдена или найдена не та")
        if scan_bytes((d / "windows.md").read_bytes()) != {}:
            fails.append("окончание строки Windows сочтено миной")
        if scan_bytes((d / "чистый.md").read_bytes()) != {}:
            fails.append("чистый файл сочтён заминированным")
        if scan_bytes((d / "табуляция.md").read_bytes()) != {}:
            fails.append("табуляция сочтена миной")
        if scan_text((d / "мина.md").read_bytes()) != {8: 1}:
            fails.append("мерка по знакам не увидела 0x08")
        if 13 in scan_text((d / "windows.md").read_bytes()):
            fails.append("мерка по знакам увидела 0x0d — тогда разница мерок описана неверно")
        if any(f.suffix == ".png" for f in files_of([d])):
            fails.append("двоичный файл попал в обход")
        if run([d / "нет-такого-пути"], False) != 2:
            fails.append("несуществующий путь не дал ОТКАЗА кодом 2")
        if run([d / "чистый.md"], False) != 0:
            fails.append("чистый файл дал не ноль")
        if run([d / "мина.md"], False) != 1:
            fails.append("файл с миной дал не единицу")
        # ⚡ ВРЕЗАНО 2026-09-15 (карточка #643 ④): файл с окончаниями строк Windows (CR LF)
        # НАХОДКОЙ не считается на выходе run() — не только scan_bytes напрямую (случай выше),
        # но и на уровне, которым его зовёт guard-all: код должен быть 0, а не 1.
        if run([d / "windows.md"], False) != 0:
            fails.append("файл с окончанием строки Windows учтён находкой run()")

        # --fix на байте, рождённом уполовиниванием, обязан ОТКАЗАТЬ и НЕ тронуть файл:
        # удаление потеряло бы ДВА знака (слэш и букву) вместо одного.
        before = (d / "мина.md").read_bytes()
        if run([d / "мина.md"], True) != 1:
            fails.append("--fix на байте от уполовинивания не отказал")
        if (d / "мина.md").read_bytes() != before:
            fails.append("--fix тронул файл, хотя должен был отказать")

        # --unescape возвращает ДВА знака и оставляет текст читаемым
        run([d / "мина.md"], False, True)
        healed_bytes = (d / "мина.md").read_bytes()
        if 8 in healed_bytes:
            fails.append("--unescape не убрал байт 0x08")
        if healed_bytes.decode("utf-8") != "до" + chr(92) + "bпосле":
            fails.append("--unescape вернул не слэш с буквой: " + repr(healed_bytes))
        if run([d / "мина.md"], False) != 0:
            fails.append("после лечения файл всё ещё судится миной")

        # --fix верен там, где байт НИЧЕГО не заменял: 0x01 escape-форме не соответствует
        (d / "шум.md").write_bytes("до".encode("utf-8") + bytes([1]) + "после".encode("utf-8"))
        if run([d / "шум.md"], True) != 0:
            fails.append("--fix не вылечил байт, не рождённый уполовиниванием")
        if (d / "шум.md").read_bytes().decode("utf-8") != "допосле":
            fails.append("--fix на обычном шуме испортил текст")
    for x in fails:
        print("СБОЙ самопроверки: " + x)
    n = inspect.getsource(selftest).count("fails.append(")
    verdict = ("все " + str(n) + " контрастов прошли") if not fails else (
        "провалено " + str(len(fails)) + " из " + str(n))
    print("самопроверка: " + verdict
          + " · мерка числа: охраняемых вызовов fails.append в теле самопроверки, по одному"
          + " на контраст (число печатается разбором своего исходника, а не пишется рукой)")
    return 1 if fails else 0


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    fix = "--fix" in args
    unesc = "--unescape" in args
    if fix and unesc:
        print("ОТКАЗ: --fix и --unescape вместе не имеют смысла — это РАЗНЫЕ лечения")
        return 2
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        paths = default_scan_targets(pathlib.Path(__file__))
        if not paths:
            print("ОТКАЗ: путь не назван, и ни одного каталога по умолчанию не нашлось "
                  "(искал рядом с собой и .mezosync/scripts / scripts — ни раскладка "
                  "контейнера, ни раскладка пакета не подошли) — нужен явный путь, или --selftest")
            return 2
        print("каталог не назван — беру по умолчанию: " + ", ".join(str(p) for p in paths))
    return run(paths, fix, unesc)


if __name__ == "__main__":
    sys.exit(main())
