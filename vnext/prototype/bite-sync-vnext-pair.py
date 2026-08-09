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

    print()
    print(f"✅ СТРОИТЕЛЬ ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 СТРОИТЕЛЬ НЕ ПРИНЯТ — числа из него нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
