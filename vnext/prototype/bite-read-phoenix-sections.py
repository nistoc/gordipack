#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-read-phoenix-sections — приёмка: полное чтение памяти роли печатает ВСЕ разделы,
даже когда сборщик слоя диска в контуре не объявлен (карточка #670).

    python <каталог приёмок>/bite-read-phoenix-sections.py
    python <каталог приёмок>/bite-read-phoenix-sections.py --break return      # нарочная поломка

ПОВОД. В read-phoenix.py, в ветке «СЛОЙ ДИСКА В ЭТОМ КОНТУРЕ НЕ ОБЪЯВЛЕН», стоял `return` —
выход из ВСЕГО main(), а не из ветки. Цикл по разделам стоял на state, и после него не
печатались §5 ПЛАН, §6 ИСТОРИЯ, §7 LAUNCHER и строка «ОТСУТСТВУЮТ СЕКЦИИ». Код 0, stderr
пуст, последняя строка вывода говорила «об этом сказано, а не промолчано» — обрыв ничем себя
не выдавал. В Atlas сборщик объявлен (запись disk_layer_tool в meta), и ветка не открывалась;
у свежего контура из пакета и у соседних контуров (dominal, onto) записи нет, и КАЖДАЯ роль
при КАЖДОМ полном чтении теряла три раздела. Контур aia исправил это у себя 2026-09-09.

ПОЧЕМУ НИ ОДНА ПРЕЖНЯЯ ПРИЁМКА ЭТОГО НЕ ВИДЕЛА. Обрыв виден, только когда сходятся три
условия сразу: (1) полное чтение, без --section; (2) сборщик НЕ объявлен НА СТЕНДЕ —
MEZO_CONTAINER указывает на стенд, а запись meta в копии базы удалена; (3) проверяются
ЗАГОЛОВКИ разделов, а не код возврата. Прежние приёмки читали с --section, или судили код
и шапку, или шли без среды стенда — тогда container_root находил ЖИВОЙ контур по месту
скрипта, и отрабатывал живой сборщик Atlas. ⇒ Здесь все три условия соблюдены нарочно.

КАК УСТРОЕНО. Стенд: копия испытуемого read-phoenix.py вместе с соседями (mezo_stand.copy_tool)
в <стенд>/.mezosync/scripts, копия базы контура (snapshot_db) в <стенд>/.mezosync/mezosync.db,
запуск со средой стенда (MEZO_CONTAINER = стенд). В копию базы кладутся пять подставных ролей:
R670A — все семь разделов; R670B — без launcher; R670C — без state; R670D — state есть, а plan
и history нет; R670E — все семь разделов, но отметка взгляда у plan позже записи, у history её
нет, у launcher она старше текста (у R670A–R670D отметка равна записи). Испытуемый — тот, на кого
указывает mezo_target (MEZO_SCRIPTS_ROOT; по умолчанию — живой каталог инструментов).
«Прежняя редакция» строится из испытуемой: ветка «не объявлен» после своей последней печати
снова кончается `return`. Для прежнего файла она совпадает с ним самим.
Вызовы ①–⑨ и ⑪–⑬ — с --full и --db: общая подсказка печатается целиком и отметку показа
не пишет, поэтому два прогона одной роли сравнимы побайтно. Но роли зовут read-phoenix.py одним
--role, без --full и без --db (шапка файла, программы запуска ролей): база находится по месту
скрипта, а подсказка идёт другим путём — первый вызов пишет в базу отметку показа, повторный
печатает строку-ссылку. Этот путь меряет ⑩ тем же вызовом, что у ролей, без побайтного сравнения.

ТЕЛА СВЕРЯЮТСЯ ЦЕЛИКОМ. Тела подставных ролей — по 13 строк, метка в ПОСЛЕДНЕЙ строке.
Прежде тело было одной строкой с меткой, ① искал только метку, ⑨ — только заголовки, и
поломка, печатавшая после ветки лишь первую строку тела, проходила все девять случаев
(проверка 2026-10-03: у настоящей роли из копии базы Atlas вывод ⑨ сократился со 129 693
до 73 934 знаков при итоге «9 из 9»). Теперь ①, ⑨, ⑩, ⑪ и ⑬ сверяют каждое тело построчно
сразу под его заголовком, а ④ на многострочных телах различает режимы «объявлен» и
«не объявлен».

СЛУЧАИ:
  ① не объявлен: полное чтение R670A печатает §5, §6, §7 ПОСЛЕ блока «НЕ ОБЪЯВЛЕН»;
    каждое тело стоит под своим заголовком ЦЕЛИКОМ, до последней строки      РАЗЛИЧАЮЩИЙ
  ② не объявлен, у R670B нет launcher: «⛔ §7 …» + «СЕКЦИИ НЕТ В БД» и строка
    «ОТСУТСТВУЮТ СЕКЦИИ: launcher»; §5 и §6 на месте                          РАЗЛИЧАЮЩИЙ
  ③ встречный (равенство): вывод прежней редакции — точное начало нового вывода
  ④ не объявлен против объявлен: всё ДО блока слоя диска и всё ПОСЛЕ него совпадает
    побайтно — меняется только сам блок                                       РАЗЛИЧАЮЩИЙ
  ⑤ встречный: --section plan печатает ровно то же, что прежняя редакция
  ⑥ встречный: сборщик объявлен (заглушка в стенде печатает одну строку) — вывод
    как у прежней редакции, §5–§7 есть, блока «НЕ ОБЪЯВЛЕН» нет
  ⑦ встречный: --section state при «не объявлен» — блок есть, §5 и «ОТСУТСТВУЮТ» нет,
    вывод как у прежней редакции. Ловит поломку pass: ветка проваливается в запуск
    несуществующего сборщика и печатает лишнее «НЕ СОБРАН»
  ⑧ роль без state (R670C): ветка слоя диска не открывается вовсе; §5–§7 и
    «ОТСУТСТВУЮТ СЕКЦИИ: state» есть, вывод как у прежней редакции           РАЗЛИЧАЮЩИЙ
  ⑨ живой по форме: настоящая роль из копии базы (с разделом state), запись meta
    удалена — после блока «НЕ ОБЪЯВЛЕН» каждый следующий раздел назван: заголовком,
    если он есть, или строкой «⛔ … СЕКЦИИ НЕТ В БД»; тело каждого раздела,
    названного заголовком, взято из копии базы и стоит под ним целиком        РАЗЛИЧАЮЩИЙ
    Нет в копии ни одной роли с разделом state (свежий контур: у координатора только §1) —
    разделы state, plan, history и launcher дописываются НА СТЕНДЕ первой живой роли
    реестра (таблица roles), и случай мерит её; что тела подставлены, сказано в строке
    случая. Нет и живой роли в реестре — случай ПРОПУЩЕН и назван, не засчитан.
    ⚠️ У настоящих ролей обычно все семь разделов, и вторая половина («⛔ … СЕКЦИИ НЕТ»)
    здесь не исполняется — её мерит ⑫ на подставной роли.
  ⑩ форма вызова ролей: R670A одним --role, БЕЗ --full и без --db, дважды подряд (первый —
    подсказка целиком и отметка показа в базу, повторный — строка-ссылка); в обоих §5, §6, §7
    с телами целиком после блока «НЕ ОБЪЯВЛЕН»; R670B тем же вызовом — «⛔ §7 …» и
    «ОТСУТСТВУЮТ СЕКЦИИ: launcher». Обрыв, который срабатывает только без --db, остальные
    случаи пропустили бы: они передают --db (проверка 2026-10-03)              РАЗЛИЧАЮЩИЙ
  ⑪ объявлен, файла нет: запись meta указывает путь, которого на стенде нет (каталог
    переименовали, сосед объявил путь к неклонированному репозиторию) — ветка слоя
    диска открывается так же, как при «не объявлен»; полное чтение R670A печатает
    §5–§7 с телами целиком ПОСЛЕ раздела state, хвост с §5 побайтно равен объявленному
    режиму ⑥. Текст самого блока не сверяется: доводка этой ветки вправе сказать иначе
    («НЕ СОБРАН»), но не вправе оборвать чтение                              РАЗЛИЧАЮЩИЙ
  ⑫ не объявлен, у R670D есть state, но нет plan и history: после блока «НЕ ОБЪЯВЛЕН» —
    «⛔ §5 …» и «⛔ §6 …» со строкой «СЕКЦИИ НЕТ В БД», затем §7, затем строка
    «ОТСУТСТВУЮТ СЕКЦИИ: plan, history» — названы ОБА отсутствующих           РАЗЛИЧАЮЩИЙ
    (② мерит отсутствие одного раздела, и только launcher)
  ⑬ не объявлен, у R670E после state три разных отметки взгляда: §5 перечитан позже записи,
    у §6 отметки нет, у §7 она старше текста — §5, §6, §7 с телами целиком ПОСЛЕ блока
    «НЕ ОБЪЯВЛЕН», и отметки в трёх заголовках разные                        РАЗЛИЧАЮЩИЙ
    (⑨ видит только те отметки, что есть у взятой им настоящей роли: на копиях 2026-10-03
    обрыв на разделе, перечитанном позже записи, проходил все двенадцать случаев и в Atlas,
    и в dominal, а на копии без колонки отметок ⑬ это говорит строкой случая)

НАРОЧНЫЕ ПОЛОМКИ (--break <имя>); список провалов каждой записан заранее в BREAK_FAILS:
  return              ветка снова кончается `return` (прежняя ошибка)   ждём ① ② ④ ⑨ ⑩ ⑪ ⑫ ⑬
  break               ветка кончается `break` — цикл обрывается, хвост
                      после цикла печатается                            ждём ① ② ④ ⑨ ⑩ ⑪ ⑫ ⑬
  pass                вместо выхода из ветки `pass` — ветка проваливается
                      в запуск несуществующего сборщика                 ждём ⑦
  no-missing-line     строка «ОТСУТСТВУЮТ СЕКЦИИ» не печатается         ждём ② ⑧ ⑩ ⑫
  first-line          после ветки «не объявлен» тело раздела печатается
                      одной первой строкой (не длиннее 120 знаков)      ждём ① ④ ⑨ ⑩ ⑪ ⑬
  return-no-full      ветка кончается `return` только без --full, с --full
                      идёт дальше (обрыв в форме вызова ролей)          ждём ⑩
  declared-return     `return` только когда путь объявлен, а файла нет —
                      обрыв в одном этом случае                         ждём ⑪
  first-missing-only  строка «ОТСУТСТВУЮТ СЕКЦИИ» называет только первый
                      отсутствующий раздел                              ждём ⑫
  declared-layer-return  после напечатанного вывода ОБЪЯВЛЕННОГО
                      сборщика — `return`: чтение обрывается в
                      объявленном режиме                                ждём ④ ⑥ ⑪

ГРАНИЦЫ, названные вслух:
  · ③ ⑤ — встречные случаи равенства; ни одна поломка из словаря их не роняет, и это
    записано в итоге, а не подразумевается; встречный ⑥ роняет declared-layer-return;
  · «прежняя редакция» строится по тексту испытуемой: если печать «…а не промолчано.»
    переименуют, приёмка откажется мерить (код 2), а не угадает место;
  · read-phoenix.py открывает базу на запись (подсказки пишут отметку показа) — здесь это
    копия на стенде; живая база только читается при снятии копии;
  · тела сверяются по непустым строкам: пустые строки внутри тела и пробелы в конце строк
    не различаются — так сверка не зависит от того, как переводы строк проходят через
    вывод дочернего процесса;
  · строку-ссылку ⑩ требует, только когда в копии базы есть таблица отметок показа
    (hint_seen); нет таблицы — это сказано в строке случая, а не промолчано;
  · ⑨ на свежем контуре мерит роль реестра с подставленными телами: ветку, зависящую
    от реестра ролей, он видит, а настоящие тела памяти — нет (их там просто нет);
  · при --break код выхода 1 и тогда, когда ожидание подтвердилось: исход поломки читается
    по строке «ПОДТВЕРДИЛОСЬ» / «НЕ ПОДТВЕРДИЛОСЬ»;
  · помощник mezo_stand старой редакции (без expected_break — так в vnext-tools контура
    dominal на 2026-09-26) прогон --break не роняет: после «ПОДТВЕРДИЛОСЬ» печатается, что
    стенд подтверждённой поломки сохранится, как у провала, и строка ИТОГ остаётся на месте.

⛔ Живого контура НЕ касается: всё на стенде во временном каталоге.
"""
from __future__ import annotations

import argparse
import ast
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths   # noqa: E402  (пути выводятся, не впечатаны)
import mezo_stand   # noqa: E402  (стенд убирается при успехе, сохраняется при провале)
import mezo_target  # noqa: E402  (какую копию испытываем)

TOOL = "read-phoenix.py"
PREV = "read-phoenix-prev.py"
SEP = "─" * 79
NOT_DECLARED = "ℹ️ СЛОЙ ДИСКА В ЭТОМ КОНТУРЕ НЕ ОБЪЯВЛЕН"
NO_LAYER_HERE = "⚠️ слой диска здесь не собирается"
MISSING = "⚠️ ОТСУТСТВУЮТ СЕКЦИИ:"
NO_SECTION = "   СЕКЦИИ НЕТ В БД."
STUB_LINE = "🧪 ЗАГЛУШКА СЛОЯ ДИСКА (приёмка карточки #670): одна строка"
STUB_REL = "tools/disk_stub_670.py"
# Объявленный путь, которого на стенде нет: случай ⑪.
MISSING_REL = "tools/нет_такого_670.py"
# Печать вывода ОБЪЯВЛЕННОГО сборщика — место поломки declared-layer-return.
DECLARED_PRINT = "print(_r.stdout.rstrip())"
# Последняя печать ветки «не объявлен» — по ней находится место выхода из ветки.
BRANCH_LAST_PRINT = '"и об этом сказано, а не промолчано.")'
HINT_REF = "ℹ️ подсказка «read-phoenix-canon» показана"   # строка-ссылка повторного вызова
MISSING_PRINT = ("print(f\"⚠️ ОТСУТСТВУЮТ СЕКЦИИ: {', '.join(miss)} — сообщи COORD, "
                 "не додумывай их содержание.\")")
ROLE_FULL, ROLE_NO_LAUNCHER, ROLE_NO_STATE = "R670A", "R670B", "R670C"
ROLE_NO_PLAN_HISTORY = "R670D"
ROLE_LOOKS = "R670E"
PLANTED = (ROLE_FULL, ROLE_NO_LAUNCHER, ROLE_NO_STATE, ROLE_NO_PLAN_HISTORY, ROLE_LOOKS)
# Отметки взгляда разделов R670E (случай ⑬): plan перечитан позже записи · у history отметки
# нет · у launcher она старше текста. Остальные разделы — отметка равна записи, как у R670A–D.
LOOKS = {"plan": "2026-10-03 00:05:00", "history": None, "launcher": "2026-10-02 23:55:00"}
AFTER = ("plan", "history", "launcher")
FIXED_TIME = "2026-10-03 00:00:00"

BREAKS = {
    "return": "ветка «не объявлен» снова кончается `return` — прежняя ошибка карточки #670",
    "break": "ветка кончается `break`: цикл по разделам обрывается, хвост после цикла печатается",
    "pass": "вместо выхода из ветки `pass`: ветка проваливается в запуск несуществующего сборщика",
    "no-missing-line": "строка «ОТСУТСТВУЮТ СЕКЦИИ» после цикла не печатается",
    "first-line": "после ветки «не объявлен» тело раздела печатается одной первой строкой "
                  "(не длиннее 120 знаков)",
    "return-no-full": "ветка кончается `return` только без --full (форма вызова ролей), "
                      "с --full идёт к следующему разделу",
    "declared-return": "`return` только когда путь объявлен, а файла по нему нет",
    "first-missing-only": "строка «ОТСУТСТВУЮТ СЕКЦИИ» называет только первый отсутствующий раздел",
    "declared-layer-return": "после напечатанного вывода ОБЪЯВЛЕННОГО сборщика — `return`: "
                             "чтение обрывается в объявленном режиме",
}
# 📋 СПИСОК ПРОВАЛОВ КАЖДОЙ ПОЛОМКИ — ЗАПИСАН ДО ПРОГОНА; прогон с --break сверяет с ним.
BREAK_FAILS = {
    "return": "①②④⑨⑩⑪⑫⑬",
    "break": "①②④⑨⑩⑪⑫⑬",
    "pass": "⑦",
    "no-missing-line": "②⑧⑩⑫",
    "first-line": "①④⑨⑩⑪⑬",
    "return-no-full": "⑩",
    "declared-return": "⑪",
    "first-missing-only": "⑫",
    "declared-layer-return": "④⑥⑪",
}
RUN_IDS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬"

OK = FAIL = DIFFER = 0
FAILED: list[str] = []
SKIPPED: list[str] = []


def case(num, title, ok, detail, differ=False):
    global OK, FAIL, DIFFER
    DIFFER += bool(differ)
    if ok:
        OK += 1
    else:
        FAIL += 1
        FAILED.append(num)
    print(f"{'✅' if ok else '🔴'} {num} {title}")
    print(f"   {detail}")


def skip(num, title, why):
    SKIPPED.append(num)
    print(f"⚪ {num} {title}")
    print(f"   ПРОПУЩЕН, не засчитан: {why}")


class Refuse(Exception):
    """Приёмка не может мерить — отказ кодом 2, а не провал и не успех."""


def _newline(raw: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in raw else b"\n"


def set_branch_exit(raw: bytes, statement: str) -> bytes:
    """Текст, в котором ветка «не объявлен» после своей последней печати кончается `statement`.

    Всё между последней печатью ветки и следующим за ней `try:` (выход и комментарии к нему)
    заменяется строками `statement` (по переводам строки, каждая — с отступом ветки). Место
    не нашлось ровно один раз — отказ, а не догадка.
    """
    nl = _newline(raw)
    lines = raw.split(nl)
    hits = [i for i, l in enumerate(lines) if l.decode("utf-8").rstrip().endswith(BRANCH_LAST_PRINT)]
    if len(hits) != 1:
        raise Refuse(f"последняя печать ветки «не объявлен» найдена {len(hits)} раз — "
                     f"место выхода из ветки не определить")
    start = hits[0] + 1
    end = start
    while end < len(lines) and lines[end].decode("utf-8").strip() != "try:":
        end += 1
    if end >= len(lines) or end == start:
        raise Refuse("после печати ветки «не объявлен» не найден выход из ветки и следующий try:")
    indent = len(lines[start].decode("utf-8")) - len(lines[start].decode("utf-8").lstrip())
    lines[start:end] = [(" " * indent + s).encode("utf-8") for s in statement.split("\n")]
    return nl.join(lines)


def insert_declared_return(raw: bytes) -> bytes:
    """Сразу после последней печати ветки — `return`, но только при объявленном пути.

    Ветка при «не объявлен» остаётся как есть; обрыв появляется в одном случае ⑪.
    """
    if b"_declared_path" not in raw:
        raise Refuse("в испытуемой редакции нет имени _declared_path — поломку не положить")
    nl = _newline(raw)
    lines = raw.split(nl)
    hits = [i for i, l in enumerate(lines) if l.decode("utf-8").rstrip().endswith(BRANCH_LAST_PRINT)]
    if len(hits) != 1:
        raise Refuse(f"последняя печать ветки «не объявлен» найдена {len(hits)} раз — "
                     f"место поломки не определить")
    start = hits[0] + 1
    indent = len(lines[start].decode("utf-8")) - len(lines[start].decode("utf-8").lstrip())
    lines.insert(start, (" " * indent + "if _declared_path: return  "
                         "# нарочная поломка приёмки #670").encode("utf-8"))
    return nl.join(lines)


def insert_return_after_declared_layer(raw: bytes) -> bytes:
    """Сразу после печати вывода объявленного сборщика — `return`.

    Ветка «не объявлен» не трогается: обрыв только там, где сборщик объявлен и найден, —
    его видят ④ и ⑪ (хвост с §5 у объявленного режима пропал) и встречный ⑥ (§5–§7 нет).
    """
    nl = _newline(raw)
    lines = raw.split(nl)
    hits = [i for i, l in enumerate(lines) if l.decode("utf-8").strip() == DECLARED_PRINT]
    if len(hits) != 1:
        raise Refuse(f"поломка «declared-layer-return» НЕ ЛЕГЛА: печать вывода объявленного "
                     f"сборщика найдена {len(hits)} раз")
    line = lines[hits[0]].decode("utf-8")
    indent = line[:len(line) - len(line.lstrip())]
    lines.insert(hits[0] + 1, (indent + "return  # нарочная поломка приёмки #670").encode("utf-8"))
    return nl.join(lines)


def apply_break(raw: bytes, name: str) -> bytes:
    if name == "declared-return":
        return insert_declared_return(raw)
    if name == "declared-layer-return":
        return insert_return_after_declared_layer(raw)
    if name in ("return", "break", "pass"):
        broken = set_branch_exit(raw, name)
        if broken == raw:
            raise Refuse(f"поломка «{name}» НЕ ЛЕГЛА: ветка в испытуемой редакции уже кончается "
                         f"`{name}` — ломать нечего")
        return broken
    if name == "return-no-full":
        broken = set_branch_exit(raw, "if not args.full:\n    return\ncontinue")
        if broken == raw:
            raise Refuse(f"поломка «{name}» НЕ ЛЕГЛА: текст испытуемой не изменился")
        return broken
    if name in ("no-missing-line", "first-missing-only"):
        text = raw.decode("utf-8")
        if text.count(MISSING_PRINT) != 1:
            raise Refuse(f"поломка «{name}» НЕ ЛЕГЛА: печать строки об отсутствующих разделах "
                         f"встречается {text.count(MISSING_PRINT)} раз")
        if name == "no-missing-line":
            return text.replace(MISSING_PRINT, "pass  # нарочная поломка приёмки #670").encode("utf-8")
        return text.replace(MISSING_PRINT, MISSING_PRINT.replace("', '.join(miss)",
                                                                 "', '.join(miss[:1])")).encode("utf-8")
    if name == "first-line":
        # флаг поднимается при выходе из ветки «не объявлен»; дальше тело — одной строкой
        nl = _newline(raw)
        lines = set_branch_exit(raw, "_cut_670 = True; continue").split(nl)
        loop = [i for i, l in enumerate(lines) if l.decode("utf-8").strip() == "for s in wanted:"]
        body = [i for i, l in enumerate(lines) if l.decode("utf-8").strip() == "print(body.strip())"]
        if len(loop) != 1 or len(body) != 1 or loop[0] > body[0]:
            raise Refuse(f"поломка «{name}» НЕ ЛЕГЛА: цикл по разделам найден {len(loop)} раз, "
                         f"печать тела — {len(body)} раз")

        def pad(i):
            line = lines[i].decode("utf-8")
            return " " * (len(line) - len(line.lstrip()))

        lines[body[0]] = (pad(body[0]) + "print(body.strip().splitlines()[0][:120] "
                          "if _cut_670 else body.strip())").encode("utf-8")
        lines.insert(loop[0], (pad(loop[0]) + "_cut_670 = False").encode("utf-8"))
        return nl.join(lines)
    raise Refuse(f"неизвестная поломка «{name}»")


def titles_of(tool: Path) -> dict:
    """Заголовки разделов — из самого испытуемого файла (словарь TITLES), без его запуска."""
    tree = ast.parse(tool.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "TITLES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise Refuse("в испытуемом read-phoenix.py нет словаря TITLES — заголовки сверять не с чем")


def declare(db: Path, value: str | None) -> None:
    con = sqlite3.connect(str(db))
    try:
        con.execute("DELETE FROM meta WHERE key = 'disk_layer_tool'")
        if value:
            con.execute("INSERT INTO meta (key, value) VALUES ('disk_layer_tool', ?)", (value,))
        con.commit()
    finally:
        con.close()


BODY_LINES = 12


def planted_body(role: str, s: str) -> str:
    """Многострочное тело подставной роли; метка — в ПОСЛЕДНЕЙ строке.

    Однострочное тело не отличает «напечатано целиком» от «напечатана первая строка»:
    на нём поломка first-line проходила ① ④ ⑨ (проверка 2026-10-03).
    """
    lines = [f"строка {i:02d} тела раздела {s} роли {role} для приёмки #670"
             for i in range(1, BODY_LINES + 1)]
    return "\n".join(lines + [f"метка-670 {role} {s}: последняя строка тела"])


def body_under(out: str, title_head: str, body: str, start: int = 0) -> bool:
    """Тело стоит в выводе целиком СРАЗУ под своим заголовком (первым после start).

    Сверка по непустым строкам: строка заголовка пропускается, дальше непустые строки
    вывода обязаны совпасть со всеми непустыми строками тела, по порядку.
    """
    h = out.find(title_head, start)
    if h < 0:
        return False
    want = [l.rstrip() for l in body.strip().splitlines() if l.strip()]
    got = [l.rstrip() for l in out[h + 1:].split("\n")[1:] if l.strip()][:len(want)]
    return bool(want) and got == want


def real_bodies(db: Path, role: str) -> dict:
    """Тела разделов роли — из той же копии базы, которую читает испытуемый."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT section, body FROM phoenix WHERE role = ?", (role,)))
    finally:
        con.close()


def _insert_section(con, cols: set, role: str, s: str, body: str, confirmed=FIXED_TIME) -> None:
    if "confirmed_at" in cols:
        con.execute("INSERT INTO phoenix (role, section, body, saved_at, confirmed_at) "
                    "VALUES (?, ?, ?, ?, ?)", (role, s, body, FIXED_TIME, confirmed))
    else:
        con.execute("INSERT INTO phoenix (role, section, body, saved_at) "
                    "VALUES (?, ?, ?, ?)", (role, s, body, FIXED_TIME))


def plant_roles(db: Path, order: list) -> bool:
    """Пять подставных ролей с многострочными телами; время записи одно и то же — вывод сравним.

    У R670A–R670D отметка взгляда равна записи; у R670E она своя у каждого раздела (LOOKS) —
    её мерит ⑬. Вернуть, есть ли в копии колонка отметок взгляда (confirmed_at).
    """
    con = sqlite3.connect(str(db))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(phoenix)")}
        con.execute(f"DELETE FROM phoenix WHERE role IN ({', '.join('?' * len(PLANTED))})",
                    PLANTED)
        plan = {ROLE_FULL: order,
                ROLE_NO_LAUNCHER: [s for s in order if s != "launcher"],
                ROLE_NO_STATE: [s for s in order if s != "state"],
                ROLE_NO_PLAN_HISTORY: [s for s in order if s not in ("plan", "history")]}
        for role, sections in plan.items():
            for s in sections:
                _insert_section(con, cols, role, s, planted_body(role, s))
        for s in order:
            _insert_section(con, cols, ROLE_LOOKS, s, planted_body(ROLE_LOOKS, s),
                            LOOKS.get(s, FIXED_TIME))
        con.commit()
        return "confirmed_at" in cols
    finally:
        con.close()


def real_role(db: Path, order: list):
    """Настоящая роль копии с разделом state: больше разделов — раньше, затем по имени."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        # Подставные роли исключаются ВСЕ: у R670D есть state, и в контуре, где настоящих
        # ролей с state нет, она была бы взята «настоящей» — ⑨ мерил бы подставную.
        rows = con.execute(f"SELECT role, section FROM phoenix WHERE role NOT IN "
                           f"({', '.join('?' * len(PLANTED))})", PLANTED).fetchall()
    finally:
        con.close()
    have: dict = {}
    for role, s in rows:
        have.setdefault(role, set()).add(s)
    cands = sorted((r for r, ss in have.items() if "state" in ss and r == r.upper()),
                   key=lambda r: (-len(have[r] & set(order)), r))
    return (cands[0], have[cands[0]]) if cands else (None, set())


def registered_role(db: Path):
    """Первая по имени живая роль реестра копии (таблица roles), кроме подставных.

    Нужна свежему контуру: у его координатора есть только §1, и без неё ⑨ пропускался —
    а пакетную пару приёмки гоняют именно на свежем контуре. None — реестра нет или в нём
    нет живой роли.
    """
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT role FROM roles WHERE lifecycle = 'alive' ORDER BY role").fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    names = [r for (r,) in rows if r not in PLANTED and r == r.upper()]
    return names[0] if names else None


def plant_registered(db: Path, role: str) -> list:
    """Дописать на стенде роли реестра недостающие state, plan, history, launcher.

    Свои разделы роли не трогаются; вернуть список дописанных.
    """
    con = sqlite3.connect(str(db))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(phoenix)")}
        have = {s for (s,) in con.execute("SELECT section FROM phoenix WHERE role = ?", (role,))}
        added = [s for s in ("state", *AFTER) if s not in have]
        for s in added:
            _insert_section(con, cols, role, s, planted_body(role, s))
        con.commit()
        return added
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка карточки #670: все разделы памяти "
                                             "печатаются и без объявленного слоя диска")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка испытуемой копии перед прогоном")
    a = ap.parse_args()

    target = mezo_target.scripts_root() / TOOL
    if not target.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого {TOOL} нет: {target}")
        return 2
    # Имя буквально, а не переменной: bite-all.exercised() ищет в тексте приёмок вызов
    # script("<имя>.py") и только так узнаёт, что этот механизм испытывается.
    target = mezo_target.script("read-phoenix.py")
    print(f"испытуемый {TOOL}: {mezo_target.label()}")

    stand = mezo_stand.new("bite-rp-sections-")
    try:
        scripts = stand / ".mezosync" / "scripts"
        tool = mezo_stand.copy_tool(target, scripts)
        raw = tool.read_bytes()
        try:
            if a.break_name:
                raw = apply_break(raw, a.break_name)
                tool.write_bytes(raw)          # байтами: концы строк копии не меняются
                print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}»: {BREAKS[a.break_name]}")
                print(f"   ждём провала РОВНО: {' '.join(BREAK_FAILS[a.break_name])} "
                      f"(записано в BREAK_FAILS до прогона)\n")
            prev = scripts / PREV
            prev.write_bytes(set_branch_exit(raw, "return"))
            titles = titles_of(tool)
        except Refuse as e:
            print(f"⛔ НЕ ПРОВЕРЕНО: {e}")
            return 2
        order = list(titles)
        after_state = order[order.index("state") + 1:]
        if [titles[s][:2] for s in AFTER] != ["§5", "§6", "§7"]:
            print(f"⛔ НЕ ПРОВЕРЕНО: заголовки разделов не §5/§6/§7: "
                  f"{[titles[s] for s in AFTER]}")
            return 2

        db = mezo_stand.snapshot_db(mezo_paths.live_db(), stand / ".mezosync" / "mezosync.db")
        try:
            declare(db, None)
            has_looks = plant_roles(db, order)
        except sqlite3.Error as e:
            print(f"⛔ НЕ ПРОВЕРЕНО: копию базы не подготовить ({e})")
            return 2
        stub = stand / STUB_REL
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(f"print({STUB_LINE!r})\n", encoding="utf-8")
        def run(script: Path, role: str, *extra, full: bool = True, with_db: bool = True):
            # Среда закреплена за стендом ЗДЕСЬ, у самого вызова: check-acceptance-env.py
            # прослеживает переменную только внутри функции вызова, внешняя ей не видна.
            run_env = mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8")
            # Показ подсказки засчитывается роли из MEZO_ROLE вызывающего, если она задана (кто_читает);
            # убираем, чтобы ⑩ мерил отметку показа подставной роли, а не той, что зовёт приёмку.
            run_env.pop("MEZO_ROLE", None)
            r = subprocess.run([sys.executable, "-B", str(script),
                                *(["--db", str(db)] if with_db else []),
                                "--role", role, *(["--full"] if full else []), *extra],
                               capture_output=True, text=True, encoding="utf-8",
                               timeout=180, env=run_env)
            return r.stdout or "", r.stderr or "", r.returncode

        def head(key):
            return f"\n## {titles[key]}   [сохранено "

        def clean(err, code):
            return code == 0 and "Traceback" not in err

        def whole_after(text, role, start):
            """Тела подставной роли под заголовками §5–§7 — целиком, начиная со start."""
            return start >= 0 and all(body_under(text, head(s), planted_body(role, s), start)
                                      for s in AFTER)

        # ── ① не объявлен, роль со всеми разделами ───────────────────────────────────
        out_a, err_a, code_a = run(tool, ROLE_FULL)
        pos_block = out_a.find(NOT_DECLARED)
        pos = [out_a.find(head(s)) for s in AFTER]
        bodies = whole_after(out_a, ROLE_FULL, pos_block)
        ok1 = (clean(err_a, code_a) and pos_block >= 0 and min(pos) > pos_block
               and pos == sorted(pos) and bodies
               and all(out_a.count(head(s)) == 1 for s in AFTER))
        case("①", "сборщик не объявлен: полное чтение печатает §5, §6, §7 ПОСЛЕ блока «НЕ ОБЪЯВЛЕН»",
             ok1, f"код {code_a} · блок «НЕ ОБЪЯВЛЕН» {'есть' if pos_block >= 0 else 'НЕТ'} · "
                  f"заголовки §5/§6/§7 на местах {pos} · тела разделов "
                  f"{'напечатаны целиком' if bodies else 'НЕ напечатаны целиком'} · знаков {len(out_a)}",
             differ=True)

        # ── ② не объявлен, роль без launcher ─────────────────────────────────────────
        out_b, err_b, code_b = run(tool, ROLE_NO_LAUNCHER)
        gone_line = f"\n⛔ {titles['launcher']}\n{NO_SECTION}"
        miss_line = f"{MISSING} launcher —"
        has_56 = all(out_b.count(head(s)) == 1 for s in ("plan", "history"))
        ok2 = (clean(err_b, code_b) and NOT_DECLARED in out_b and has_56
               and gone_line in out_b and miss_line in out_b
               and out_b.find(gone_line) > out_b.find(NOT_DECLARED)
               and out_b.find(miss_line) > out_b.find(gone_line))
        case("②", "раздела launcher нет: «⛔ §7 … СЕКЦИИ НЕТ В БД» и «ОТСУТСТВУЮТ СЕКЦИИ: launcher»",
             ok2, f"код {code_b} · §5 и §6 {'есть' if has_56 else 'НЕТ'} · строка «⛔ §7 … СЕКЦИИ "
                  f"НЕТ» {'есть' if gone_line in out_b else 'НЕТ'} · «ОТСУТСТВУЮТ СЕКЦИИ: launcher» "
                  f"{'есть' if miss_line in out_b else 'НЕТ'}", differ=True)

        # ── ③ прежняя редакция — начало нового вывода ────────────────────────────────
        old_a, err_old, code_old = run(prev, ROLE_FULL)
        ok3 = (clean(err_old, code_old) and NOT_DECLARED in old_a and out_a.startswith(old_a)
               and old_a.rstrip().endswith("и об этом сказано, а не промолчано."))
        case("③", "встречный: вывод прежней редакции — точное начало нового (до блока слоя "
             "диска включительно ничего не сдвинулось)",
             ok3, f"прежняя {len(old_a)} знаков, новая {len(out_a)}; совпадение начала: "
                  f"{'да' if out_a.startswith(old_a) else 'НЕТ'}")

        # ── ⑥ (сначала собираем объявленный режим — он нужен ④ и ⑪) ──────────────────
        declare(db, STUB_REL)
        out_d, err_d, code_d = run(tool, ROLE_FULL)
        old_d, err_od, code_od = run(prev, ROLE_FULL)
        declare(db, None)

        # ── ④ не объявлен против объявлен: меняется только блок слоя диска ──────────
        def split(text, marker):
            m = text.find(marker)
            cut = text.rfind(f"\n{SEP}\n", 0, m) if m >= 0 else -1
            t = text.find(f"\n{SEP}\n## {titles['plan']}")
            return (text[:cut] if cut >= 0 else None), (text[t:] if t >= 0 else None)

        pre_u, tail_u = split(out_a, NOT_DECLARED)
        pre_d, tail_d = split(out_d, STUB_LINE)
        ok4 = (pre_u is not None and pre_u == pre_d and tail_u is not None and tail_u == tail_d)
        case("④", "не объявлен против объявлен: всё до блока слоя диска и всё после него — "
             "побайтно одинаково",
             ok4, f"начало: {'совпало' if pre_u is not None and pre_u == pre_d else 'НЕ совпало'} · "
                  f"хвост с §5: {'нет у «не объявлен»' if tail_u is None else ('совпал' if tail_u == tail_d else 'НЕ совпал')} "
                  f"({0 if tail_u is None else len(tail_u)} из {0 if tail_d is None else len(tail_d)} знаков)",
             differ=True)

        # ── ⑤ --section plan не изменился ────────────────────────────────────────────
        out_p, err_p, code_p = run(tool, ROLE_FULL, "--section", "plan")
        old_p, err_op, code_op = run(prev, ROLE_FULL, "--section", "plan")
        ok5 = (clean(err_p, code_p) and out_p == old_p and out_p.count("\n## §") == 1
               and head("plan") in out_p and MISSING not in out_p)
        case("⑤", "встречный: --section plan печатает ровно то же, что прежняя редакция",
             ok5, f"код {code_p} · равенство с прежней: {'да' if out_p == old_p else 'НЕТ'} · "
                  f"заголовков разделов {out_p.count(chr(10) + '## §')}")

        # ── ⑥ сборщик объявлен: как прежде ──────────────────────────────────────────
        ok6 = (clean(err_d, code_d) and clean(err_od, code_od) and out_d == old_d
               and STUB_LINE in out_d and NOT_DECLARED not in out_d
               and all(out_d.count(head(s)) == 1 for s in AFTER))
        case("⑥", "встречный: сборщик объявлен (заглушка) — вывод как у прежней редакции, "
             "§5–§7 есть",
             ok6, f"код {code_d} · строка заглушки {'есть' if STUB_LINE in out_d else 'НЕТ'} · "
                  f"равенство с прежней: {'да' if out_d == old_d else 'НЕТ'}")

        # ── ⑦ --section state при «не объявлен» ─────────────────────────────────────
        out_s, err_s, code_s = run(tool, ROLE_FULL, "--section", "state")
        old_s, _, _ = run(prev, ROLE_FULL, "--section", "state")
        ok7 = (clean(err_s, code_s) and out_s == old_s and NOT_DECLARED in out_s
               and head("plan") not in out_s and MISSING not in out_s)
        case("⑦", "встречный: --section state — блок «НЕ ОБЪЯВЛЕН» есть, §5 и «ОТСУТСТВУЮТ» нет",
             ok7, f"код {code_s} · равенство с прежней: {'да' if out_s == old_s else 'НЕТ'}")

        # ── ⑧ роль без state ─────────────────────────────────────────────────────────
        out_c, err_c, code_c = run(tool, ROLE_NO_STATE)
        old_c, _, _ = run(prev, ROLE_NO_STATE)
        gone_state = f"\n⛔ {titles['state']}\n{NO_SECTION}"
        ok8 = (clean(err_c, code_c) and out_c == old_c and gone_state in out_c
               and NO_LAYER_HERE in out_c and NOT_DECLARED not in out_c
               and all(out_c.count(head(s)) == 1 for s in AFTER)
               and f"{MISSING} state —" in out_c)
        case("⑧", "роль без state: ветка слоя диска не открывается; §5–§7 и «ОТСУТСТВУЮТ "
             "СЕКЦИИ: state» есть",
             ok8, f"код {code_c} · «ОТСУТСТВУЮТ СЕКЦИИ: state» "
                  f"{'есть' if f'{MISSING} state —' in out_c else 'НЕТ'} · равенство с прежней: "
                  f"{'да' if out_c == old_c else 'НЕТ'}", differ=True)

        # ── ⑨ настоящая роль из копии базы (на свежем контуре — роль реестра) ────────
        role, have = real_role(db, order)
        planted_note = ""
        if role is None:
            reg = registered_role(db)
            if reg is not None:
                added = plant_registered(db, reg)
                role = reg
                have = set(real_bodies(db, reg))
                planted_note = (f" · роли с разделом state в копии нет — взята живая роль реестра "
                                f"{reg}, на стенде дописаны {', '.join(added) or 'ничего'} "
                                f"(тела подставлены приёмкой, настоящих нет)")
        if role is None:
            skip("⑨", "живой по форме: настоящая роль копии базы",
                 "в копии нет ни одной роли с разделом state и ни одной живой роли в реестре")
        else:
            out_r, err_r, code_r = run(tool, role)
            pos_r = out_r.find(NOT_DECLARED)
            bodies_r = real_bodies(db, role)
            named, whole = [], {}
            for s in after_state:
                mark = head(s) if s in have else f"\n⛔ {titles[s]}\n{NO_SECTION}"
                named.append(out_r.find(mark) > pos_r >= 0)
                if s in have:
                    whole[s] = pos_r >= 0 and body_under(out_r, head(s), bodies_r[s], pos_r)
            ok9 = clean(err_r, code_r) and pos_r >= 0 and all(named) and all(whole.values())
            case("⑨", f"живой по форме: роль {role} (разделов {len(have)}), запись meta "
                 f"удалена — каждый раздел после state назван, тела целиком",
                 ok9, f"код {code_r} · знаков {len(out_r)} · названы после блока: "
                      f"{', '.join(f'{s}={n}' for s, n in zip(after_state, named))} · тела целиком: "
                      f"{', '.join(f'{s}={w}' for s, w in whole.items()) or 'нечего сверять'}"
                      + planted_note,
                 differ=True)

        # ── ⑩ форма вызова ролей: без --full, первый и повторный вызов ───────────────
        # Роли зовут read-phoenix.py без --full. Тогда подсказка идёт своим путём: первый вызов
        # печатает её целиком и пишет отметку показа в базу, повторный печатает строку-ссылку.
        # ①–⑨ этот путь не проходят, и обрыв, который срабатывает только без --full, они
        # пропустили бы. Побайтно не сравниваем: первый и повторный вывод разные по построению.
        hint_table = True
        con = sqlite3.connect(str(db))
        try:
            con.execute("DELETE FROM hint_seen WHERE role IN (?, ?)", (ROLE_FULL, ROLE_NO_LAUNCHER))
            con.commit()
        except sqlite3.Error:
            hint_table = False
        finally:
            con.close()
        n1, e1, c1 = run(tool, ROLE_FULL, full=False, with_db=False)
        n2, e2, c2 = run(tool, ROLE_FULL, full=False, with_db=False)
        nb, eb, cb = run(tool, ROLE_NO_LAUNCHER, full=False, with_db=False)

        def all_after_block(text, role_):
            p = text.find(NOT_DECLARED)
            hp = [text.find(head(s)) for s in AFTER]
            return (p >= 0 and min(hp) > p and hp == sorted(hp)
                    and all(text.count(head(s)) == 1 for s in AFTER)
                    and whole_after(text, role_, p))

        ok_n1 = clean(e1, c1) and all_after_block(n1, ROLE_FULL)
        ok_n2 = clean(e2, c2) and all_after_block(n2, ROLE_FULL)
        ref2 = HINT_REF in n2
        ok_nb = (clean(eb, cb) and NOT_DECLARED in nb
                 and all(nb.count(head(s)) == 1 for s in ("plan", "history"))
                 and gone_line in nb and miss_line in nb
                 and nb.find(gone_line) > nb.find(NOT_DECLARED)
                 and nb.find(miss_line) > nb.find(gone_line))
        ok10 = ok_n1 and ok_n2 and ok_nb and (ref2 or not hint_table)
        case("⑩", "форма вызова ролей (без --full): первый и повторный вызов печатают §5–§7 "
             "с телами, у роли без launcher — «ОТСУТСТВУЮТ СЕКЦИИ: launcher»",
             ok10, f"первый: код {c1}, §5–§7 с телами {'да' if ok_n1 else 'НЕТ'}, знаков {len(n1)} · "
                   f"повторный: код {c2}, подсказка {'строкой-ссылкой' if ref2 else 'целиком'}, "
                   f"§5–§7 с телами {'да' if ok_n2 else 'НЕТ'}, знаков {len(n2)} · "
                   f"{ROLE_NO_LAUNCHER}: «⛔ §7» и «ОТСУТСТВУЮТ» {'есть' if ok_nb else 'НЕТ'}"
                   + ("" if hint_table else " · таблицы отметок показа в копии нет — путь "
                      "строки-ссылки не пройден"),
             differ=True)

        # ── ⑪ объявлен, файла нет ───────────────────────────────────────────────────
        # Ветка слоя диска открывается по «файла нет», а не по «не объявлен»: обе беды идут
        # одним путём. Блок сверяется не текстом (доводка вправе его изменить), а тем, что
        # после раздела state хвост с §5 тот же, что при объявленном и найденном сборщике.
        declare(db, MISSING_REL)
        out_m, err_m, code_m = run(tool, ROLE_FULL)
        declare(db, None)
        pos_state = out_m.find(head("state"))
        pos_m = [out_m.find(head(s)) for s in AFTER]
        bodies_m = whole_after(out_m, ROLE_FULL, pos_state)
        t_m = out_m.find(f"\n{SEP}\n## {titles['plan']}")
        t_d = out_d.find(f"\n{SEP}\n## {titles['plan']}")
        tail_m = out_m[t_m:] if t_m >= 0 else None
        tail_dd = out_d[t_d:] if t_d >= 0 else None
        ok11 = (clean(err_m, code_m) and pos_state >= 0 and min(pos_m) > pos_state
                and pos_m == sorted(pos_m) and bodies_m
                and all(out_m.count(head(s)) == 1 for s in AFTER)
                and tail_m is not None and tail_m == tail_dd
                and not (Path(stand) / MISSING_REL).exists())
        case("⑪", "объявлен, файла нет: полное чтение печатает §5, §6, §7 с телами после state, "
             "хвост с §5 как у объявленного",
             ok11, f"код {code_m} · заголовки §5/§6/§7 на местах {pos_m} (state на {pos_state}) · "
                   f"тела {'напечатаны целиком' if bodies_m else 'НЕ напечатаны целиком'} · хвост с §5: "
                   f"{'нет' if tail_m is None else ('совпал' if tail_m == tail_dd else 'НЕ совпал')} "
                   f"({0 if tail_m is None else len(tail_m)} из {0 if tail_dd is None else len(tail_dd)} знаков)",
             differ=True)

        # ── ⑫ не объявлен, у роли есть state, но нет plan и history ──────────────────
        # ② мерит отсутствие одного раздела (launcher); у настоящих ролей (⑨) обычно все
        # разделы, и строка «⛔ … СЕКЦИИ НЕТ» после блока на живых данных не печатается.
        # Здесь отсутствуют ДВА раздела, оба после блока: роль обязана узнать, что у неё нет
        # ПЛАНА и ИСТОРИИ, — и в цикле, и в итоговой строке.
        out_e, err_e, code_e = run(tool, ROLE_NO_PLAN_HISTORY)
        pos_e = out_e.find(NOT_DECLARED)
        gone_e = [out_e.find(f"\n⛔ {titles[s]}\n{NO_SECTION}") for s in ("plan", "history")]
        head7 = out_e.find(head("launcher"))
        miss_e = f"{MISSING} plan, history —"
        pos_me = out_e.find(miss_e)
        ok12 = (clean(err_e, code_e) and pos_e >= 0 and min(gone_e) > pos_e
                and gone_e == sorted(gone_e) and head7 > max(gone_e)
                and out_e.count(head("launcher")) == 1 and pos_me > head7)
        case("⑫", "у роли нет plan и history: «⛔ §5 …» и «⛔ §6 … СЕКЦИИ НЕТ В БД» после блока, "
             "§7 на месте, «ОТСУТСТВУЮТ СЕКЦИИ: plan, history»",
             ok12, f"код {code_e} · блок «НЕ ОБЪЯВЛЕН» {'есть' if pos_e >= 0 else 'НЕТ'} · "
                   f"«⛔ §5/§6 … СЕКЦИИ НЕТ» на местах {gone_e} · §7 "
                   f"{'есть' if head7 >= 0 else 'НЕТ'} · «ОТСУТСТВУЮТ СЕКЦИИ: plan, history» "
                   f"{'есть' if pos_me >= 0 else 'НЕТ'}", differ=True)

        # ── ⑬ не объявлен, у роли три разных отметки взгляда после state ─────────────
        # У подставных R670A–R670D отметка равна записи, а ⑨ видит только отметки взятой
        # настоящей роли. Обрыв, который срабатывает на одном виде отметки (перечитано позже
        # записи · отметки нет · отметка старше текста), иначе проходил бы все случаи.
        out_l, err_l, code_l = run(tool, ROLE_LOOKS)
        pos_l = out_l.find(NOT_DECLARED)
        hl = [out_l.find(head(s)) for s in AFTER]

        def look_of(text, key):
            p = text.find(head(key))
            line = text[p + 1:].split("\n", 1)[0] if p >= 0 else ""
            return line.split(" UTC · ", 1)[1].rstrip("]") if " UTC · " in line else None

        looks = [look_of(out_l, s) for s in AFTER]
        looks_differ = None not in looks and len(set(looks)) == len(AFTER)
        ok13 = (clean(err_l, code_l) and pos_l >= 0 and min(hl) > pos_l and hl == sorted(hl)
                and all(out_l.count(head(s)) == 1 for s in AFTER)
                and whole_after(out_l, ROLE_LOOKS, pos_l)
                and (looks_differ or not has_looks))
        case("⑬", "у R670E после state три разных отметки взгляда: §5–§7 с телами целиком "
             "ПОСЛЕ блока «НЕ ОБЪЯВЛЕН»",
             ok13, f"код {code_l} · заголовки §5/§6/§7 на местах {hl} · тела "
                   f"{'напечатаны целиком' if whole_after(out_l, ROLE_LOOKS, pos_l) else 'НЕ напечатаны целиком'} · "
                   + (f"отметки в заголовках {'разные' if looks_differ else 'НЕ разные'} · "
                      if has_looks else "колонки отметок взгляда в копии нет — виды отметок "
                      "не различены, сверены только разделы и тела · ")
                   + f"знаков {len(out_l)}",
             differ=True)

        # ═══ ИТОГ ═══
        covered = set().union(*(set(v) for v in BREAK_FAILS.values()))
        run_ids = [n for n in RUN_IDS if n not in SKIPPED]
        uncovered = [n for n in run_ids if n not in covered]
        mismatch = False
        print("")
        if a.break_name:
            expected = set(BREAK_FAILS[a.break_name]) - set(SKIPPED)
            actual = set(FAILED)
            if expected == actual:
                print(f"🧪 ожидание поломки «{a.break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно "
                      f"{' '.join(n for n in RUN_IDS if n in actual)}")
                # Помощник старой редакции этой функции не знает (vnext-tools контура dominal
                # на 2026-09-26): прямой вызов падал AttributeError после «ПОДТВЕРДИЛОСЬ», и
                # строки ИТОГ не было. Нет функции — сказать строкой, а не упасть.
                mark_expected = getattr(mezo_stand, "expected_break", None)
                if mark_expected is None:
                    print("   ℹ️ в mezo_stand нет expected_break (старая редакция помощника): "
                          "стенд этой поломки сохранится, как у провала")
                else:
                    mark_expected()
            else:
                mismatch = True
                print(f"⚠️ ожидание поломки «{a.break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
                      f"{' '.join(n for n in RUN_IDS if n in expected) or 'ничего'}, провалены "
                      f"{' '.join(n for n in RUN_IDS if n in actual) or 'ничего'}")
        print(f"{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL} · различающих {DIFFER}"
              + (f" · пропущено {len(SKIPPED)} ({' '.join(SKIPPED)})" if SKIPPED else "")
              + f" · ни одной поломкой не покрыты: {' '.join(uncovered) or 'нет'}")
        if a.break_name:
            return 1 if (FAIL or mismatch) else 0
        return 0 if FAIL == 0 else 1
    finally:
        mezo_stand.release(stand)


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
