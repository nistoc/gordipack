# -*- coding: utf-8 -*-
r"""ПРИЁМКА строителя пары «рабочий каталог ↔ шаблон» (vnext/tools/sync-vnext-pair.py).

Главное проверяемое свойство — строитель НЕ ЗЕРКАЛО. Зеркальный строитель зеленеет ровно
тогда, когда положил потребителю инструменты, которые у него падают (замер 09.08: девять
из четырнадцати). Поэтому у случая «переносит вперёд» обязателен встречный «не тянет назад».

⛔ Число случаев словом не пишется — печатает прогон.
⛔ Живых каталогов не касается: временные каталоги в песочнице.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.normpath(os.path.join(HERE, "..", "tools", "sync-vnext-pair.py"))

CASES = 0
DIFFERENTIATING = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand(tmp, name, runtime, template, live=None):
    root = os.path.join(tmp, name)
    paths = {}
    for label, files in (("runtime", runtime), ("template", template), ("live", live or {})):
        d = os.path.join(root, label)
        os.makedirs(d, exist_ok=True)
        paths[label] = d
        for fn, body in files.items():
            with open(os.path.join(d, fn), "wb") as f:
                f.write(body.encode("utf-8"))
    return paths


def run(paths, *extra):
    r = subprocess.run([sys.executable, BUILDER, "--runtime", paths["runtime"],
                        "--template", paths["template"], "--live", paths["live"], *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-sync-pair-")
    ok = True
    BASE = {"a.py": "print(1)\n"}

    # ① НОВОЕ В РАБОЧЕМ — не доехало до потребителя
    p = stand(tmp, "one", {**BASE, "novum.py": "x\n"}, BASE)
    out, code = run(p)
    ok &= case("① файл есть в рабочем, в шаблоне нет — красное «НЕ ДОЕДЕТ»",
               code == 1 and "НЕ ДОЕДЕТ" in out and "novum.py" in out,
               f"код {code}; чего нет в шаблоне — того не будет у потребителя", differ=True)

    # ② ГЛАВНЫЙ ВСТРЕЧНЫЙ: файл только в ШАБЛОНЕ обратно НЕ тянется.
    #    Ровно здесь зеркальный строитель кладёт потребителю падающий инструмент.
    p = stand(tmp, "two", BASE, {**BASE, "needs-schema.py": "x\n"})
    out, code = run(p, "--apply")
    pulled = os.path.exists(os.path.join(p["runtime"], "needs-schema.py"))
    ok &= case("② шаблонный файл обратно НЕ переносится даже при --apply (встречный к ①)",
               code == 0 and not pulled,
               "из десяти приёмок шаблона переносимы две — зеркало сломало бы восемь",
               differ=True)

    # ③ ДРЕЙФ общего файла — виден и переносится вперёд
    p = stand(tmp, "three", {"a.py": "print(1)\n"}, {"a.py": "print(2)\n"})
    out, code = run(p)
    ok &= case("③ общий файл разошёлся — назван «разошлось»",
               code == 1 and "разошлось" in out, "копии расходятся молча — это предмет строителя",
               differ=True)

    # ④ ЗАМЫКАНИЕ: файл тянет то, что зовёт. Перенос половины связки — дефект, который
    #    у потребителя выглядит как «инструмент есть», а он падает на первом же вызове.
    p = stand(tmp, "four",
              {**BASE, "tool.py": 'CHECK = "helper.py"\n', "helper.py": "print(2)\n"}, BASE)
    out, code = run(p, "--apply")
    both = all(os.path.exists(os.path.join(p["template"], n)) for n in ("tool.py", "helper.py"))
    ok &= case("④ перенос тянет ЗАМЫКАНИЕ, а не один файл",
               code == 1 and both,
               "половина связки у потребителя хуже её отсутствия: выглядит установленной",
               differ=True)

    # ⑤ ВСТРЕЧНЫЙ к ④: посторонний файл замыканием НЕ тянется (иначе поедет весь каталог)
    p = stand(tmp, "five", {**BASE, "solo.py": "print(3)\n", "unrelated.py": "print(4)\n"},
              {**BASE, "unrelated.py": "print(4)\n"})
    out, code = run(p, "--apply")
    ok &= case("⑤ несвязанный файл замыканием не тянется (встречный к ④)",
               "solo.py" in out and "unrelated.py" not in out.split("НЕ ДОЕДЕТ")[-1],
               "замыкание должно тянуть связку, а не весь каталог", differ=True)

    # ⑥ ЖИВОЙ КОНТУР ЗОВЁТ ТО, ЧЕГО В РАБОЧЕМ НЕТ — второе направление, и оно ПРОВЕРКА,
    #    а не перенос. Список вызываемого берётся ЗАМЕРОМ по коду живых скриптов.
    p = stand(tmp, "six", BASE, BASE,
              live={"g.py": 'p = SCRIPTS / "vnext-tools" / "ghost.py"\n'})
    out, code = run(p)
    ok &= case("⑥ живой контур зовёт файл, которого в рабочем нет — красное",
               code == 1 and "ЗОВЁТ, А В РАБОЧЕМ НЕТ" in out and "ghost.py" in out,
               "вызов несуществующего инструмента — то же «нет вовсе», только со стороны контура",
               differ=True)

    # ⑦ ВСТРЕЧНЫЙ к ⑥: вызовов не найдено — сказать вслух, а не зачесть за чистоту.
    #    Пустой ответ имеет два разных смысла, и они обязаны звучать по-разному.
    p = stand(tmp, "seven", BASE, BASE, live={"g.py": "print(1)\n"})
    out, code = run(p)
    ok &= case("⑦ вызовов НЕ НАЙДЕНО — названо отдельно, а не зачтено как «все на месте»",
               code == 0 and "НЕ НАЙДЕНО" in out,
               "«их нет» и «замер не сработал» неотличимы, если про это молчать", differ=True)

    # ⑧ ИДЕМПОТЕНТНОСТЬ: повтор после --apply зелёный. Шаг, ломающий себя собственным
    #    успехом, у нас уже был (@COORD 09.08) — проверяем повторным прогоном, не чтением.
    p = stand(tmp, "eight", {**BASE, "novum.py": "x\n"}, BASE)
    run(p, "--apply")
    out, code = run(p)
    ok &= case("⑧ повторный прогон после переноса — зелёный (идемпотентность)",
               code == 0 and "всё, что есть в рабочем, доехало" in out,
               "первый прогон не должен делать состояние непохожим на то, что ждёт второй",
               differ=True)

    # ⑨ ПУСТОЙ РАБОЧИЙ — отказ мерить, а не «всё сведено»
    p = stand(tmp, "nine", {}, BASE)
    out, code = run(p)
    ok &= case("⑨ рабочий каталог пуст — «переносить нечего», а не «сведено»",
               code == 2 and "НЕ «всё сведено»" in out,
               "сравнение с пустотой всегда зелёное — этим уже обжигались")

    # ⑩ ЗАМЕР НЕ ТРОГАЕТ ФАЙЛЫ [встречный ко всем --apply]
    p = stand(tmp, "ten", {**BASE, "novum.py": "x\n"}, BASE)
    run(p)
    ok &= case("⑩ прогон БЕЗ --apply ничего не переносит",
               not os.path.exists(os.path.join(p["template"], "novum.py")),
               "замер, меняющий состояние, нельзя запустить, чтобы просто посмотреть",
               differ=True)

    # ⑪ РАЗЛИЧИЕ ТОЛЬКО ЗАГЛУШКА ПУТИ — не расхождение работы (карточка #297).
    # 🩸 Строитель звал переносить 19 таких файлов; перенос затёр бы заглушки путями
    # ОДНОЙ машины, и потребитель получил бы невыполнимые у себя строки. Роль при этом
    # видит красное «не доедет» и зовёт --apply, будучи уверенной, что чинит доставку.
    sys.path.insert(0, HERE)
    import mezo_paths                                     # noqa: E402
    КОРЕНЬ = str(mezo_paths.container_root()).replace("\\", "/")
    свой = f'"""пример: python {КОРЕНЬ}/vnext-tools/x.py"""\nprint(1)\n'
    шаблонный = '"""пример: python <КОНТУР>/vnext-tools/x.py"""\nprint(1)\n'
    p = stand(tmp, "eleven", {**BASE, "stub.py": свой}, {**BASE, "stub.py": шаблонный})
    out, code = run(p)
    # 🪤 Первая редакция условия резала вывод по «НЕ ДОЕДЕТ» — а когда всё сведено, этой
    # границы в выводе НЕТ ВОВСЕ, и «хвост после неё» оказывался всем выводом целиком.
    # Случай краснел при исправном строителе. Тот же класс, что чиню сегодня повсюду:
    # разбор по границе, которой может не быть, врёт молча и в обе стороны.
    блок = (out.split("🔴 НЕ ДОЕДЕТ")[1].split("\n\n")[0]
            if "🔴 НЕ ДОЕДЕТ" in out else "")
    ok &= case("⑪ различие ТОЛЬКО заглушка пути — в перенос НЕ попадает и названо отдельно",
               "stub.py" not in блок
               and "С ТОЧНОСТЬЮ ДО ЗАГЛУШКИ" in out and "stub.py" in out,
               "файл сведён и назван вслух: молчание тут читалось бы как «совпал байт "
               "в байт», а разница есть — и она законна", differ=True)

    # ⑫ ВСТРЕЧНЫЙ к ⑪: правка СВЕРХ заглушки обязана ехать, иначе починка ослепила строителя.
    свой2 = f'"""пример: python {КОРЕНЬ}/vnext-tools/x.py"""\nprint(2)  # НОВАЯ РАБОТА\n'
    p = stand(tmp, "twelve", {**BASE, "stub.py": свой2}, {**BASE, "stub.py": шаблонный})
    out, code = run(p)
    ok &= case("⑫ ВСТРЕЧНЫЙ: правка СВЕРХ заглушки — по-прежнему «разошлось»",
               "stub.py" in (out.split("🔴 НЕ ДОЕДЕТ")[1]
                             if "🔴 НЕ ДОЕДЕТ" in out else ""),
               "без этого случая ⑪ мог бы зеленеть оттого, что строитель перестал "
               "видеть расхождения вообще", differ=True)

    # ⑬ ЗАГЛУШКА НЕ ТЯНЕТСЯ ЗАМЫКАНИЕМ [обходной путь к ⑪, найден живым замером 27.08].
    # 🩸 Защита ⑪ стояла на прямом списке; замыкание тянуло тот же файл в обход неё,
    # и --apply затёр бы заглушку. В живой паре это было ВИДНО: один файл стоял разом
    # в «сведены с точностью до заглушки» и в «не доедет (тянется замыканием)».
    # Случай ⑪ при этом оставался зелёным — он проверял дверь, а перенос шёл окном.
    зовущий = f'"""новый инструмент"""\nCHECK = "stub.py"\nprint(1)\n'
    p = stand(tmp, "thirteen",
              {**BASE, "tool.py": зовущий, "stub.py": свой},
              {**BASE, "stub.py": шаблонный})
    out, code = run(p, "--apply")
    после = open(os.path.join(p["template"], "stub.py"), encoding="utf-8").read()
    приехал = os.path.exists(os.path.join(p["template"], "tool.py"))
    ok &= case("⑬ файл-заглушка НЕ переносится, даже когда его тянет ЗАМЫКАНИЕ",
               "<КОНТУР>" in после and приехал,
               "половина связки должна доехать, но не ценой затёртой заглушки: "
               "у потребителя вместо неё оказался бы путь ОДНОЙ машины", differ=True)

    # ⑭ ВСТРЕЧНЫЙ к ⑬: файл, который зовут И который разошёлся ПО СУЩЕСТВУ, ехать обязан.
    # Без него ⑬ зеленел бы оттого, что замыкание перестало тянуть что-либо вообще.
    p = stand(tmp, "fourteen",
              {**BASE, "tool.py": зовущий, "stub.py": "print(2)  # НОВАЯ РАБОТА\n"},
              {**BASE, "stub.py": "print(1)\n"})
    run(p, "--apply")
    ok &= case("⑭ ВСТРЕЧНЫЙ: связанный файл с настоящей правкой замыканием ЕДЕТ",
               "НОВАЯ РАБОТА" in open(os.path.join(p["template"], "stub.py"),
                                      encoding="utf-8").read(),
               "иначе починка ⑬ отняла бы у замыкания его работу целиком", differ=True)

    # ⑮–⑱ ДОКУМЕНТЫ ПАРЫ (карточка #303). Строитель сводил только .py и МОЛЧАЛ о .md:
    # два документа не доехали вовсе, расхождение третьего читалось как «всё сведено».
    # Направление — надмножеством строк: перенос разрешён только туда, где он ничего
    # не стирает; «богаче образец» затёр бы историю строкой «доставляю недостающее».
    p = stand(tmp, "fifteen", {**BASE, "doc.md": "a\nb\n", "same.md": "x\n"},
              {**BASE, "same.md": "x\n"})
    out, code = run(p, "--apply")
    доехал = os.path.exists(os.path.join(p["template"], "doc.md"))
    ok &= case("⑮ документ есть в рабочем, в шаблоне нет — назван «НЕ ДОЕДЕТ», --apply переносит",
               code == 1 and "doc.md" in out and "НЕ ДОЕДЕТ" in out and доехал
               and "равны по строкам: 1" in out,
               "нечего стирать — перенос безопасен; равный документ посчитан, не назван",
               differ=True)

    p = stand(tmp, "sixteen", {**BASE, "doc.md": "a\nb\n"},
              {**BASE, "doc.md": "a\nb\nЗАПИСЬ-СДАНО\n"})
    out, code = run(p, "--apply")
    тело = open(os.path.join(p["template"], "doc.md"), encoding="utf-8").read()
    ok &= case("⑯ документ богаче в ОБРАЗЦЕ — назван, и --apply его НЕ трогает",
               "богаче ОБРАЗЕЦ" in out and "ЗАПИСЬ-СДАНО" in тело,
               "перенос рабочий→образец стёр бы историю; уникальная строка образца на месте",
               differ=True)

    p = stand(tmp, "seventeen", {**BASE, "doc.md": "a\nСВОЁ-РАБОЧЕГО\n"},
              {**BASE, "doc.md": "a\nСВОЁ-ОБРАЗЦА\n"})
    out, code = run(p, "--apply")
    тело = open(os.path.join(p["template"], "doc.md"), encoding="utf-8").read()
    своё = open(os.path.join(p["runtime"], "doc.md"), encoding="utf-8").read()
    ok &= case("⑰ документ разошёлся В ОБЕ СТОРОНЫ — сводить рукой, --apply не трогает НИ ОДНУ",
               "В ОБЕ СТОРОНЫ" in out and "СВОЁ-ОБРАЗЦА" in тело and "СВОЁ-РАБОЧЕГО" in своё,
               "автомат тут может только стирать; обе уникальные строки на местах",
               differ=True)

    # ⑱ ВСТРЕЧНЫЙ: «богаче РАБОЧИЙ» едет, и едет В ДОМ документа (этажом выше), без дубля.
    # Без него ⑯–⑰ зеленели бы оттого, что строитель перестал переносить документы вообще.
    p = stand(tmp, "eighteen", {**BASE, "doc.md": "a\nb\nНОВОЕ-РАБОЧЕГО\n"}, BASE)
    выше = os.path.join(os.path.dirname(p["template"]), "doc.md")
    with open(выше, "w", encoding="utf-8") as f:
        f.write("a\nb\n")
    out, code = run(p, "--apply")
    ok &= case("⑱ ВСТРЕЧНЫЙ: «богаче РАБОЧИЙ» --apply переносит — в дом документа, без дубля",
               "богаче РАБОЧИЙ" in out
               and "НОВОЕ-РАБОЧЕГО" in open(выше, encoding="utf-8").read()
               and not os.path.exists(os.path.join(p["template"], "doc.md")),
               "иначе починка отняла бы у сведения документов его работу целиком; "
               "дубль рядом с кодом раздвоил бы истину", differ=True)

    print()
    print(f"✅ СТРОИТЕЛЬ ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 СТРОИТЕЛЬ НЕ ПРИНЯТ — числа из него нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
