# -*- coding: utf-8 -*-
r"""ПРИЁМКА деления «исчезнувших» строк на «изменена» и «пропала» — карточка #616.

ПОВОД. save-phoenix.py считал «исчезло дословно N» по ОДНОМУ признаку: строки
старого тела, которой нет ДОСЛОВНО в новом. Правка внутри строки и её полное
удаление отчитывались ОДНИМ числом. Живой случай @ING (записка #5003, 07.09
16:38 UTC): пять сохранений подряд, «исчезло дословно 13 (6%)», а «ни одна
строка не исчезла — все 37 были ПЕРЕПИСАНЫ» — первый порыв был откатить
сознательную правку, прочитав её как потерю.

⛔ Живой базы не касается вовсе: судятся ТЕЛА ТЕКСТА через loss_report(),
база не открывается (тот же приём, что у bite-phoenix-block-metric.py) —
в файле нет ни одного импорта sqlite3, проверено чтением. Стенд (mezo_stand)
используется ТОЛЬКО в случае ⑥ — под временную копию испытуемого инструмента,
не под базу.

Какую копию испытываем — ТЕМ ЖЕ рычагом, что и остальные приёмки на копиях
(карточка #148): переменная MEZO_SCRIPTS_ROOT (mezo_target.py). Без неё
испытывается ЖИВОЙ save-phoenix.py — это обычный порядок для УСТАНОВЛЕННОЙ
приёмки, не запрет: сама проверка при этом ничего не портит, потому что
судит только ТЕЛА ТЕКСТА (см. выше — базу не открывает никогда).

🩸 НАХОДКА PROTO 2026-09-14 (второй возврат по карточке): первая редакция
случая ⑥ принимала готовую испорченную копию ИЗВНЕ через переменную
BITE_BROKEN_SAVE_PHOENIX — на установленной приёмке взять эту копию
неоткуда (её строила только моя песочница), и случай ⑥ ПАДАЛ словами
«поломка не запущена», хотя защита цела. ⇒ приёмка строит поломку САМА:
копирует испытуемый инструмент во временный стенд (mezo_stand.new +
mezo_stand.copy_tool — тот же приём, каким соседние приёмки этой карточки
копируют save-phoenix.py вместе с соседями) и правит ЕГО копию.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① переписана НА ТРЕТЬ (структура и часть слов те же) → «изменена»      РАЗЛИЧАЮЩИЙ
  ② удалена БЕЗ похожей замены рядом → «пропала»                         РАЗЛИЧАЮЩИЙ,
                                                                          встречный к ①
  ③ разрезана на ДВЕ примерно равные половины → «изменена» (лучшая из
    половин проходит порог 0.60 — решение НАЗВАНО в save-phoenix.py)      РАЗЛИЧАЮЩИЙ
  ④ КОНТРОЛЬ формы: случай ①, но тело в CRLF (концы строк Windows) —
    тот же вердикт, что и ①                                              КОНТРОЛЬ
  ⑤ КОНТРОЛЬ похожести: рядом с удалённой строкой — совсем ДРУГАЯ ТЕМА
    (ложный кандидат НЕ должен пройти порог) → «пропала», как и ②         КОНТРОЛЬ
  ⑥ ОБРАТНЫЙ ХОД: приёмка САМА строит поломку — копия испытуемого во
    временный стенд, якорная строка вызова похожести заменяется на
    «match = None» («все изменённые снова пропали»). Якорь обязан
    найтись РОВНО ОДИН РАЗ — иначе случай падает словами «якорь не
    найден», а не гадает по устаревшему месту. На порченой копии ①③
    обязаны стать «пропала», ② обязан остаться «пропала» — поломка
    красит РОВНО случаи «изменена»                                       РАЗЛИЧАЮЩИЙ
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths    # noqa: E402
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

print(f"⚖️ испытуется: {mezo_target.label()}")


def load(path: Path, module_name: str):
    tool_dir = path.parent
    if str(tool_dir) not in sys.path:
        sys.path.insert(0, str(tool_dir))
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    _argv, sys.argv = sys.argv, ["bite"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = _argv
    return mod


TARGET_TOOL = mezo_target.script("save-phoenix.py")
saveph = load(TARGET_TOOL, "saveph_main")

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def report(old_body, new_body, module=None):
    m = module or saveph
    share, lines = m.loss_report(old_body, new_body)
    return share, "\n".join(lines)


# ── тела для случаев ①②④⑤: пять содержательных строк без разметки ──
BASE = [
    "критерий приёмки формулируется ДО начала работы, а не после первой находки",
    "вторая содержательная строка тела, тоже длиннее двенадцати знаков ровно",
    "третья содержательная строка тела для количества, длиннее двенадцати знаков",
    "четвёртая содержательная строка тела, тоже длиннее двенадцати знаков точно",
    "пятая содержательная строка тела для ровного счёта, длиннее двенадцати",
]
OLD_BODY = "\n".join(BASE) + "\n"
REWRITTEN_BY_THIRD = ("критерий приёмки формулируется ДО старта работы, "
                       "а не вдогонку первой находке")

ok = True

# ① переписана на треть
new_body1 = "\n".join([REWRITTEN_BY_THIRD] + BASE[1:]) + "\n"
_, r1 = report(OLD_BODY, new_body1)
ok &= case("① переписана НА ТРЕТЬ → «изменена», не «пропала»",
           "изменено 1" in r1 and "пропало 0" in r1 and "✂" not in r1,
           f"отчёт: {r1.splitlines()[-1].strip() if r1.splitlines() else '(пусто)'}",
           differ=True)

# ② удалена без похожей замены
new_body2 = "\n".join(BASE[1:]) + "\n"
_, r2 = report(OLD_BODY, new_body2)
ok &= case("② удалена БЕЗ похожей замены → «пропала» (встречный к ①)",
           "изменено 0" in r2 and "пропало 1" in r2 and "✂" in r2,
           f"отчёт: {r2.splitlines()[-2].strip()}",
           differ=True)

# ③ разрезана на две примерно равные половины
OLD_LINE = BASE[0]
MIDPOINT = len(OLD_LINE) // 2
PART_A, PART_B = OLD_LINE[:MIDPOINT], OLD_LINE[MIDPOINT:]
new_body3 = "\n".join([PART_A, PART_B] + BASE[1:]) + "\n"
_, r3 = report(OLD_BODY, new_body3)
ok &= case("③ разрезана на ДВЕ половины → считается «изменена» (порог 0.60, "
           "лучшая половина ~0.667 — решение названо в save-phoenix.py)",
           "изменено 1" in r3 and "пропало 0" in r3,
           f"отчёт: {r3.splitlines()[-1].strip() if r3.splitlines() else '(пусто)'}",
           differ=True)

# ④ КОНТРОЛЬ формы: та же правка ①, но тело в CRLF (концы строк Windows)
new_body4_crlf = new_body1.replace("\n", "\r\n")
old_body_crlf = OLD_BODY.replace("\n", "\r\n")
_, r4 = report(old_body_crlf, new_body4_crlf)
ok &= case("④ КОНТРОЛЬ формы: тот же случай ① в CRLF → тот же вердикт «изменена»",
           "изменено 1" in r4 and "пропало 0" in r4,
           "конец строки Windows не должен ломать классификацию")

# ⑤ КОНТРОЛЬ похожести: рядом с удалённой строкой — совсем другая тема
OTHER_TOPIC = "порог объёма секции — 400 знаков, ниже него доли не судим вовсе никогда"
new_body5 = "\n".join([OTHER_TOPIC] + BASE[1:]) + "\n"
_, r5 = report(OLD_BODY, new_body5)
ok &= case("⑤ КОНТРОЛЬ похожести: рядом другая ТЕМА, не похожая замена → "
           "остаётся «пропала», как и ②",
           "изменено 0" in r5 and "пропало 1" in r5,
           "посторонний кандидат не обязан пройти порог 0.60")

# ⑥ ОБРАТНЫЙ ХОД: приёмка САМА строит поломку — копия испытуемого инструмента
# во временный стенд (mezo_stand.new + copy_tool: копирует ТАРГЕТ вместе со
# всеми его транзитивными соседями — тот же приём, что у bite-phoenix-empty.py
# и bite-phoenix-truncation-named.py), якорная строка правится на «match = None».
# ⚖️ Якорь ищется РОВНО ОДИН РАЗ: 0 совпадений значит «строку в инструменте
# переписали, приёмка целится в устаревшее место» — тогда случай обязан
# ПРОВАЛИТЬСЯ словами «якорь не найден», а не притвориться, что поломка
# сработала. Больше одного совпадения — та же беда с другой стороны:
# замена задела бы не ту строку, и поломка перестала бы быть ИМЕННО той,
# что названа.
ANCHOR_LINE = "match = difflib.get_close_matches(l, new_only, n=1, cutoff=CHANGED_SIMILARITY)"
source_text = TARGET_TOOL.read_text(encoding="utf-8")
occurrences = source_text.count(ANCHOR_LINE)
if occurrences != 1:
    ok &= case("⑥ ОБРАТНЫЙ ХОД: поломка красит РОВНО случаи «изменена» (① и ③), "
               "случай «пропала» (②) остаётся зелёным",
               False,
               f"⛔ ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ (найдено {occurrences}) — "
               "строка вызова похожести в испытуемом не совпала с ожидаемой: "
               "либо её переписали, либо испытан инструмент БЕЗ карточки #616 "
               "(например, копия ДО правки) — правь якорь приёмки, а не думай",
               differ=True)
else:
    stand = mezo_stand.new("phoenix-changed-vs-gone-")
    broken_copy = mezo_stand.copy_tool(TARGET_TOOL, stand / "broken")
    broken_copy.write_text(source_text.replace(ANCHOR_LINE, "match = None", 1),
                            encoding="utf-8")
    broken_mod = load(broken_copy, "saveph_broken")
    _, rb1 = report(OLD_BODY, new_body1, module=broken_mod)
    _, rb2 = report(OLD_BODY, new_body2, module=broken_mod)
    _, rb3 = report(OLD_BODY, new_body3, module=broken_mod)
    broken_1 = "изменено 0" in rb1 and "пропало 1" in rb1     # было «изменено 1»
    broken_3 = "изменено 0" in rb3 and "пропало 1" in rb3     # было «изменено 1»
    intact_2 = "изменено 0" in rb2 and "пропало 1" in rb2     # как и было
    ok &= case("⑥ ОБРАТНЫЙ ХОД: поломка красит РОВНО случаи «изменена» (① и ③), "
               "случай «пропала» (②) остаётся зелёным",
               broken_1 and broken_3 and intact_2,
               f"① стало «{'пропала' if broken_1 else 'НЕ сломалось'}» · "
               f"③ стало «{'пропала' if broken_3 else 'НЕ сломалось'}» · "
               f"② осталось «{'пропала' if intact_2 else 'СЛОМАЛОСЬ — поломка задела лишнее'}»",
               differ=True)

print()
print(f"{'✅ МЕРКА «ИЗМЕНЕНА/ПРОПАЛА» ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — "
      f"случаев {CASES}, различающих {DIFFER}")
sys.exit(mezo_stand.finish(0 if ok else 1))
