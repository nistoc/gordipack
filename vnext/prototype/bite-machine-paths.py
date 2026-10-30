#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PLANTS: template-docs
r"""ПРИЁМКА проверки «в образце нет путей одной машины» (карточка #208).

Проверка, которая ищет чужие пути, сама обязана быть испытана поломкой: иначе она
зелёная ровно потому, что ничего не ищет. И — главное — она обязана РАЗЛИЧАТЬ, а не
красить всё подряд: первая её редакция обвинила `http://localhost:5173`, строку
`re.compile(r"STUB-EXPECTED:\s*#\d+")` и таблицу замера в доке. Обвинение без разбора
дороже пропуска: читающий перестаёт верить проверке целиком.

Случаи (различающий = проверка обязана ответить ИНАЧЕ, а не одинаково):
  ① контроль: чистое дерево — молчит, и видно, что смотрела
  ② путь в КОДЕ → красное                                          РАЗЛИЧАЮЩИЙ
  ③ тот же путь в КОММЕНТАРИИ → не красное, названо жёлтым         ВСТРЕЧНЫЙ к ②
  ④ придуманный путь чужой раскладки → не красится                 РАЗЛИЧАЮЩИЙ
  ⑤ путь в исполнимом примере дока → красное                       РАЗЛИЧАЮЩИЙ
  ⑥ тот же путь в блоке-ВЫВОДЕ → жёлтое                            ВСТРЕЧНЫЙ к ⑤
  ⑦ обезличенный заполнитель → не красится                         РАЗЛИЧАЮЩИЙ
  ⑧ сетевой адрес (http://localhost:5173) → не путь                РАЗЛИЧАЮЩИЙ
  ⑨ дерева нет → отказ мерить отдельным кодом, а не «чисто»        РАЗЛИЧАЮЩИЙ
  ⑩ путь в СУЩЕСТВУЮЩИЙ каталог этой машины, которого проверка не знает корнем
     (дом, образец и контур переназначены в стенд) → красное         РАЗЛИЧАЮЩИЙ
     Так копия проверки из выгрузки видит то же, что копия в образце (карточка #731)
  ⑪ путь контура удвоенными разделителями (как в исходнике Python), каталога
     контура на диске нет → красное                                  РАЗЛИЧАЮЩИЙ
  ⑫ системный каталог Windows (SYSTEMROOT) → не красится             ВСТРЕЧНЫЙ к ⑩
     На машине без такого каталога случай не различает
  ⑬ путь в ПРОЗЕ шапки модуля (docstring) → не красное, названо      РАЗЛИЧАЮЩИЙ
     Шапку читают, а не исполняют (карточка #732)
  ⑭ строка-КОМАНДА в той же шапке → красное                         ВСТРЕЧНЫЙ к ⑬
  ⑮ команда с окружением впереди («ИМЯ=значение python …») → красное РАЗЛИЧАЮЩИЙ

Нарочные поломки (--break), каждая на своей копии guard-machine-paths.py в стенде:
  no-head ........... верхний каталог пути не проверяется на существование → ⑩
  no-collapse ....... разделители не сводятся перед сравнением с корнями   → ⑪
  no-system-heads ... системные каталоги Windows не исключаются            → ⑫ (только на Windows)
  doc-as-code ....... шапка снова судится как код целиком                  → ⑬
  doc-all-prose ..... шапка судится прозой целиком, команды в ней тоже     → ⑭
  no-env-prefix ..... образец команды не понимает «ИМЯ=значение» впереди   → ⑮

⛔ Живого контура не касается: всё во временном каталоге.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

HERE = Path(__file__).resolve().parent
TOOL = HERE / "guard-machine-paths.py"
MINE = str(mezo_paths.container_root())          # путь ЭТОЙ машины — выводим, не впечатываем
CASES = DIFFER = 0
FAILED: list[str] = []
RUN_ENV: dict[str, str] = {}      # окружение копии с поломкой; пусто — как у самой приёмки

# Нарочные поломки: (подмены в копии guard-machine-paths.py, случаи, которые обязаны провалиться)
BREAKS = {
    "no-head": (
        [("    return head is not None and head_exists(head)\n", "    return False\n")],
        {"⑩"}),
    "no-collapse": (
        [(r'    norm = re.sub(r"[\\/]+", r"\\", piece).lower()' + "\n",
          r'    norm = piece.replace("/", "\\").lower()' + "\n")],
        {"⑪"}),
    "no-system-heads": (
        [("    if tail.lower() in SYSTEM_HEADS:\n", "    if False:\n")],
        {"⑫"} if os.name == "nt" else set()),
    "doc-as-code": (
        [("            (in_doc if id(node) in doc_ids else in_code).update(range(node.lineno, end + 1))\n",
          "            in_code.update(range(node.lineno, end + 1))\n")],
        {"⑬"}),
    "doc-all-prose": (
        [('            elif path.suffix == ".py" and n in docs and COMMAND_RE.match(line):\n',
          '            elif path.suffix == ".py" and n in docs and False:\n')],
        {"⑭"}),
    "no-env-prefix": (
        [(r'COMMAND_RE = re.compile(r"^\s*[$>]?\s*(?:[A-Za-z_]\w*=\S*\s+)*"' + "\n",
          r'COMMAND_RE = re.compile(r"^\s*[$>]?\s*"' + "\n")],
        {"⑮"}),
}


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    if not ok:
        FAILED.append(title.split()[0])
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def run(root: Path, env: dict[str, str] | None = None):
    full_env = {**os.environ, **RUN_ENV, **(env or {})}
    r = subprocess.run([sys.executable, str(TOOL), "--root", str(root), "--verbose"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       env=full_env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def tree(name: str, files: dict[str, str]) -> Path:
    d = mezo_stand.new(f"bite-mp-{name}-")
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


def main() -> int:
    global TOOL
    ap = argparse.ArgumentParser(description="приёмка guard-machine-paths.py")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка на копии проверки в стенде — ловят ли её случаи")
    a = ap.parse_args()
    ok = True
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: проверки нет — {TOOL}")

    if a.break_name:
        src = TOOL.read_text(encoding="utf-8")
        for old, new in BREAKS[a.break_name][0]:
            if src.count(old) != 1:
                print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда — якорь найден "
                      f"{src.count(old)} раз")
                return 2
            src = src.replace(old, new)
        copy_dir = mezo_stand.new("bite-mp-break-")
        (copy_dir / TOOL.name).write_text(src, encoding="utf-8")
        shutil.copy2(HERE / "mezo_paths.py", copy_dir / "mezo_paths.py")
        TOOL = copy_dir / TOOL.name
        # Копия лежит вне образца: образец и контур ей называются явно — теми же, что у приёмки
        RUN_ENV.update(MEZO_TEMPLATE=str(mezo_paths.template_root()), MEZO_CONTAINER=MINE)
        expected = BREAKS[a.break_name][1]
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(expected)) or 'ни одного — здесь случай не различает'}")

    # ① КОНТРОЛЬ. Без него краснота дальше не значит ничего: молчать можно и от слепоты.
    clean = tree("clean", {
        "tool.py": 'ПУТЬ = "относительный/путь"\nprint("работаю")\n',
        "README.md": "# Заголовок\n\n```\npython tool.py --role PROTO\n```\n",
    })
    out1, code1 = run(clean)
    ok &= case("① контроль: чистое дерево — молчит, и видно, что смотрела",
               code1 == 0 and "живых путей одной машины нет" in out1 and "файлов 2" in out1,
               f"код {code1}; «ничего не нашла» и «ничего не искала» обязаны выглядеть по-разному")

    # ② ПУТЬ В КОДЕ — механизм у чужого человека мёртв.
    in_code = tree("code", {"tool.py": f'БАЗА = r"{MINE}\\.mezosync\\mezosync.db"\n'})
    out2, code2 = run(in_code)
    ok &= case("② путь этой машины В КОДЕ — красное",
               code2 == 1 and "в коде" in out2,
               "у читателя такого каталога нет, и механизм молча не работает", differ=True)

    # ③ ВСТРЕЧНЫЙ: тот же путь в комментарии — там он ПРЕДМЕТ УРОКА, а не приказ.
    in_comment = tree("comment", {
        "tool.py": f'# 12.08 сломалось на пути {MINE}\\.mezosync — оттуда и правило\nX = 1\n'})
    out3, code3 = run(in_comment)
    ok &= case("③ ВСТРЕЧНЫЙ: тот же путь в КОММЕНТАРИИ — не красное, но названо",
               code3 == 0 and "проза или комментарий" in out3,
               "стереть путь из урока значит стереть причину решения", differ=True)

    # ④ ПРИДУМАННЫЙ путь чужой раскладки — не долг: он никуда не ведёт и никого не обманывает.
    # Верхний каталог заведомо несуществующий: с карточки #731 путь в существующий каталог этой машины
    # считается живым, и прежний C:\projects провалил бы случай там, где такой каталог есть (замечание
    # PROTO, записка #6110).
    foreign = tree("foreign", {"tool.py": 'ПРИМЕР = r"C:\\zz-nobody-731-projects\\app\\.mezosync"\n'})
    out4, code4 = run(foreign)
    ok &= case("④ придуманный путь чужой раскладки — не красится",
               code4 == 0,
               "судим по происхождению пути, а не по его виду: иначе форма вызова "
               "становится долгом", differ=True)

    # ⑤ ИСПОЛНИМЫЙ ПРИМЕР В ДОКЕ — читающий скопирует и получит отказ.
    doc = tree("doc", {"README.md": f"# Как звать\n\n```\npython {MINE}/vnext-tools/x.py\n```\n"})
    out5, code5 = run(doc)
    ok &= case("⑤ путь в исполнимом примере дока — красное",
               code5 == 1 and "исполнимый пример" in out5,
               "скопирует, получит отказ и решит, что сломан механизм", differ=True)

    # ⑥ ВСТРЕЧНЫЙ к ⑤: тот же блок, но это ВЫВОД замера, а не команда.
    #    🪤 Оплачено ошибкой: первая редакция красила блок целиком и обвинила таблицу
    #    «этот файл ЕСТЬ, этого НЕТ» — там путь и есть предмет записи.
    output = tree("output", {
        "README.md": f"# Замер\n\n```\n{MINE}\\.mezosync\\schema   НЕТ\n```\n"})
    out6, code6 = run(output)
    ok &= case("⑥ ВСТРЕЧНЫЙ: тот же путь в блоке-ВЫВОДЕ — жёлтое, не обвинение",
               code6 == 0 and "проза или комментарий" in out6,
               "не всякая строка в блоке — команда; исполнять вывод замера никто не станет",
               differ=True)

    # ⑦ ОБЕЗЛИЧЕННЫЙ заполнитель — уже починенная форма, требовать от неё чистоты нельзя.
    # 🪤 ЗДЕСЬ ЛЕЖАТ ДАННЫЕ ОПЫТА, А НЕ ФОРМА ВЫЗОВА. 20.08 сплошная правка шапок заменила
    #    заполнитель настоящим путём — и случай стал ждать молчания там, где проверка
    #    ОБЯЗАНА краснеть. Слепая замена по файлу задевает подопытное наравне с показываемым.
    placeholder = tree("placeholder", {
        "README.md": "# Как звать\n\n```\npython <ваш контейнер>/vnext-tools/x.py\n```\n"})
    out7, code7 = run(placeholder)
    ok &= case("⑦ обезличенный заполнитель — не красится",
               code7 == 0,
               "иначе починка выглядела бы такой же виной, как сам долг", differ=True)

    # ⑧ СЕТЕВОЙ АДРЕС — не путь на диске. Оплачено: первая редакция обвиняла «http://…».
    net = tree("net", {
        "tool.py": 'CLIENT = "http://localhost:5173"\nMARK = "STUB-EXPECTED"\n'})
    out8, code8 = run(net)
    ok &= case("⑧ сетевой адрес и двоеточие в строке — не путь машины",
               code8 == 0,
               "«http://localhost» и «try:\\n» ловились как диск: обвинение без разбора "
               "дороже пропуска", differ=True)

    # ⑨ ДЕРЕВА НЕТ — отказ мерить, отдельным кодом. «Чисто» здесь было бы ложью.
    out9, code9 = run(Path(tempfile.gettempdir()) / "нет-такого-дерева-208")
    ok &= case("⑨ дерева нет — отказ мерить отдельным кодом",
               code9 == 2 and "НЕ ЗАПУСТИЛАСЬ" in out9,
               f"код {code9}; опечатка в пути обязана звучать иначе, чем чистота", differ=True)

    # ⑩ КАРТОЧКА #731 (замер PROTO, записка #6102): путь в СУЩЕСТВУЮЩИЙ каталог этой машины,
    #    которого проверка не знает корнем. Дом, образец и контур переназначены в стенд — как у
    #    копии из выгрузки, которая берёт образцом саму себя. Настоящий дом на диске есть, и путь
    #    в него — путь этой машины, где бы ни лежала проверка.
    elsewhere = mezo_stand.new("bite-mp-elsewhere-")
    env10 = {"HOME": str(elsewhere / "h" / "i"), "USERPROFILE": str(elsewhere / "h" / "i"),
             "MEZO_TEMPLATE": str(elsewhere / "a" / "b"), "MEZO_CONTAINER": str(elsewhere / "c" / "d")}
    unknown = tree("unknown-root", {"tool.py": f'DB = r"{Path.home()}{os.sep}x.db"\n'})
    out10, code10 = run(unknown, env10)
    ok &= case("⑩ путь в существующий каталог этой машины, не названный корнем, — красное",
               code10 == 1 and "в коде" in out10,
               f"код {code10}; где лежит проверка, не меняет того, что есть на диске: копия из "
               "выгрузки видит то же, что копия в образце", differ=True)

    # ⑪ КАРТОЧКА #731: путь контура удвоенными разделителями — так он стои́т в исходнике Python.
    #    Каталога контура на диске НЕТ: путь опознаётся только сравнением с корнем, и без
    #    сведения разделителей сравнение его не узнаёт.
    ghost = r"Q:\zz-nobody-731\box" if os.name == "nt" else "/home/zz-nobody-731/box"
    doubled = (ghost + os.sep + "x.db").replace(os.sep, os.sep * 2)
    twice = tree("doubled", {"tool.py": f'DB = "{doubled}"\n'})
    out11, code11 = run(twice, {"MEZO_CONTAINER": ghost})
    ok &= case("⑪ путь контура удвоенными разделителями — красное",
               code11 == 1 and "в коде" in out11,
               f"код {code11}; запись пути в исходнике не меняет того, куда он ведёт", differ=True)

    # ⑫ ВСТРЕЧНЫЙ к ⑩: системный каталог Windows есть на ЛЮБОЙ машине Windows — путь в него не
    #    раскладка одной машины (SYSTEMROOT в окружении стенда). Где такого каталога нет, случай
    #    не различает: красить там нечем и прежней проверке.
    system = tree("system", {"tool.py": 'ENV = {"SYSTEMROOT": "C:\\\\Windows"}\n'})
    out12, code12 = run(system)
    ok &= case("⑫ ВСТРЕЧНЫЙ к ⑩: системный каталог Windows — не красится",
               code12 == 0,
               f"код {code12}; он есть на любой машине Windows — обвинять его значит обвинять "
               "верный текст" + ("" if os.name == "nt" else "; здесь его нет — случай не различает"),
               differ=(os.name == "nt"))

    # ⑬ КАРТОЧКА #732: путь в ПРОЗЕ шапки модуля — урок, а не механизм. Прежде шапка судилась
    #    как код целиком, и на выгрузке 7395076 так обвинялись 11 строк истории в шапках.
    doc_prose = tree("docprose", {
        "tool.py": f'r"""Урок: 12.08 сломалось на пути {MINE}\\.mezosync — оттуда правило."""\nX = 1\n'})
    out13, code13 = run(doc_prose)
    ok &= case("⑬ путь в ПРОЗЕ шапки модуля — не красное, но названо",
               code13 == 0 and "проза или комментарий" in out13,
               f"код {code13}; шапку читают, а не исполняют — стереть путь из урока значит стереть "
               "причину решения", differ=True)

    # ⑭ ВСТРЕЧНЫЙ к ⑬: строка-КОМАНДА в той же шапке — её скопируют и запустят.
    doc_cmd = tree("doccmd", {
        "tool.py": f'r"""Зовут так:\n    python {MINE}\\vnext-tools\\x.py --role PROTO\n"""\nX = 1\n'})
    out14, code14 = run(doc_cmd)
    ok &= case("⑭ ВСТРЕЧНЫЙ к ⑬: строка-команда в шапке модуля — красное",
               code14 == 1 and "🔴 tool.py:2" in out14,
               f"код {code14}; шапка — не вся проза: команду из неё скопируют и получат отказ",
               differ=True)

    # ⑮ КАРТОЧКА #732: окружение перед командой («ИМЯ=значение python …») не делает её прозой.
    #    Так звали memory-history-fold.py; без этого правка ⑬ увела бы её команды в прозу.
    env_cmd = tree("envcmd", {
        "README.md": f"# Как звать\n\n```\nMEZO_ROLE=PROTO python {MINE}/vnext-tools/x.py\n```\n"})
    out15, code15 = run(env_cmd)
    ok &= case("⑮ команда с окружением впереди — красное",
               code15 == 1 and "исполнимый пример" in out15,
               f"код {code15}; «ИМЯ=значение» перед командой — часть команды, а не проза", differ=True)

    print()
    print(f"{'✅ ПРОВЕРКА ПУТЕЙ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(FAILED) == expected
        print(f"{'🧪' if exact else '⚠️'} поломка «{a.break_name}»: провалились "
              f"{' '.join(FAILED) or 'никто'} · ждали {' '.join(sorted(expected)) or 'никого'} — "
              f"{'ожидание ПОДТВЕРДИЛОСЬ' if exact else 'ожидание НЕ ПОДТВЕРДИЛОСЬ'}")
        if exact:
            mezo_stand.expected_break()
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
