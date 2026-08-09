# -*- coding: utf-8 -*-
r"""ПРИЁМКА признака «доедет ли инструмент до потребителя» (check-copy-asymmetry.py).

Главное проверяемое свойство — АСИММЕТРИЯ. Симметричная сверка («каталоги обязаны совпадать»)
зеленеет ровно тогда, когда к потребителю положили инструменты, которые у него не работают:
замер 09.08 — 9 из 14 перенесённых падали при запуске, а сторож был доволен.

⛔ Число случаев словом не пишется — его печатает прогон.
⛔ Живых каталогов не касается: временные каталоги в песочнице.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_check():
    """Испытуемый: --check, затем рядом, затем в тулките. Разбор — в bite-retired-mechanism.py.

    Коротко: у автора механизм и приёмка в одном каталоге, у меня в разных зонах, и приёмка,
    ищущая соседа рядом с собой, краснеет ВСЕМИ случаями — «испытуемого нет» неотличимо
    от «механизм плох». Отказ мерить обязан звучать отказом.
    """
    for i, a in enumerate(sys.argv):
        if a == "--check" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    here = os.path.join(HERE, "check-copy-asymmetry.py")
    if os.path.exists(here):
        return here
    return os.path.abspath(os.path.join(HERE, "..", ".mezosync", "scripts",
                                        "check-copy-asymmetry.py"))


CHECK = _find_check()
if not os.path.exists(CHECK):
    print(f"⛔ ИСПЫТУЕМОГО НЕТ: {CHECK}\n"
          "   Это НЕ «признак плох» и НЕ «чисто» — это отказ мерить.\n"
          "   Укажи путь: bite-copy-asymmetry.py --check <путь к check-copy-asymmetry.py>")
    sys.exit(2)

CASES = 0
DIFFERENTIATING = 0


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand(tmp, name, runtime_files, template_files):
    rt = os.path.join(tmp, name, "runtime")
    tpl = os.path.join(tmp, name, "template")
    # 🪤 ПИШЕМ БАЙТАМИ, а не текстом. Первая редакция открывала файл в текстовом режиме,
    # и Windows молча превращал «\n» в «\r\n» ПРИ ЗАПИСИ — то есть встречный случай ④
    # («перевод строки дрейфом не считается») проверял не то, что задумано, и краснел
    # на исправном признаке. Приёмка, стерегущая БАЙТЫ, обязана управлять байтами сама.
    for d, files in ((rt, runtime_files), (tpl, template_files)):
        os.makedirs(d, exist_ok=True)
        for fn, body in files.items():
            with open(os.path.join(d, fn), "wb") as f:
                f.write(body.encode("utf-8"))
    r = subprocess.run([sys.executable, CHECK, "--runtime", rt, "--template", tpl],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-copy-asym-")
    ok = True
    A = {"a.py": "print(1)\n"}

    # ① ФАЙЛ ТОЛЬКО У ПОТРЕБИТЕЛЯ — не доедет при раскатке
    out, code = stand(tmp, "one", {**A, "solo.py": "x\n"}, A)
    ok &= case("① файл есть у потребителя, в шаблоне нет — красное «НЕ ДОЕДЕТ»",
               code == 1 and "НЕ ДОЕДЕТ" in out and "solo.py" in out,
               f"код {code}; худший случай — у потребителя нет вовсе, а сверка молчит",
               differ=True)

    # ② ВСТРЕЧНЫЙ и ГЛАВНЫЙ: файл только в ШАБЛОНЕ — это НОРМА, а не дефект.
    #    Ровно здесь симметричная сверка врёт: она требует положить потребителю то,
    #    что у него не работает (замер 09.08: 9 из 14 падали при запуске).
    out, code = stand(tmp, "two", A, {**A, "needs-schema.py": "x\n"})
    ok &= case("② файл только в шаблоне — зелёное, шаблон полнее ПО ПОСТРОЕНИЮ (встречный к ①)",
               code == 0 and "НОРМА" in out and "НЕ ДОЕДЕТ" not in out,
               "иначе зеркало кладёт потребителю инструменты, падающие при запуске",
               differ=True)

    # ③ ДРЕЙФ общего файла — красное с обеих сторон
    out, code = stand(tmp, "three", {"a.py": "print(1)\n"}, {"a.py": "print(2)\n"})
    ok &= case("③ общий файл с разным содержимым — красное «ДРЕЙФ»",
               code == 1 and "ДРЕЙФ" in out,
               "копии разъезжаются молча — это и есть предмет сторожа", differ=True)

    # ④ ВСТРЕЧНЫЙ к ③: разный перевод строки дрейфом НЕ считается.
    #    git на Windows правит его сам; без этого сторож был бы красным всегда и его
    #    перестали бы читать — та же цена, что у непогасимого красного.
    out, code = stand(tmp, "four", {"a.py": "print(1)\n"}, {"a.py": "print(1)\r\n"})
    ok &= case("④ разный перевод строки дрейфом НЕ считается (встречный к ③)",
               code == 0 and "ДРЕЙФ" not in out,
               "иначе красное вечно и по невиновной причине — git правит перевод строки сам",
               differ=True)

    # ⑤ ОБА ПУСТЫ — отказ мерить, а не «совпадают». Пустое сравнение всегда «равно».
    out, code = stand(tmp, "five", {}, {})
    ok &= case("⑤ оба каталога пусты — «сверять нечего», а не «совпадают»",
               code == 2 and "НЕ «совпадают»" in out,
               "сравнение двух отсутствий даёт зелёное — этим уже обжёгся @COORD 09.08",
               differ=True)

    # ⑥ КАТАЛОГА НЕТ — сказано вслух: иначе опечатка в пути выглядит чистотой
    out, code = stand(tmp, "six", A, A)
    bad = subprocess.run([sys.executable, CHECK, "--runtime", os.path.join(tmp, "нет-такого"),
                          "--template", os.path.join(tmp, "six", "template")],
                         capture_output=True, text=True, encoding="utf-8")
    ok &= case("⑥ каталог не найден — отказ мерить, а не «чисто»",
               bad.returncode == 2 and "не найден" in (bad.stdout or ""),
               "опечатка в пути обязана звучать иначе, чем совпадение", differ=True)

    # ⑦ ГРАНИЦА НАЗВАНА В ВЫВОДЕ. Не украшение: без неё зелёное читается как
    #    «копии равносильны», а это НЕПРАВДА — доказано прогоном обеих копий 09.08.
    out, code = stand(tmp, "seven", A, A)
    ok &= case("⑦ зелёное само называет свою границу (файлы ≠ работоспособность)",
               code == 0 and "ГРАНИЦА" in out and "ПРОГОНОМ" in out,
               "каталоги совпали файл в файл, а прогон дал 34 против «сломано 2, не проверено 7»")

    print()
    print(f"✅ ПРИЗНАК ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 ПРИЗНАК НЕ ПРИНЯТ — числа из него нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
