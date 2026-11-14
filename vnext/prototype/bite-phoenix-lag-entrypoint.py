#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА ТОЧКИ ВХОДА phoenix_lag.py — отказывает ли прямой запуск и следует ли указатель за файлом.

Карточка 756 (находка STUD, записка #6370 §③). Прямой запуск общей функции отставания памяти
печатал НОЛЬ байт и выходил кодом 0 — то есть отвечал ровно так, как проверка, которой не на что
смотреть. Роль, позвавшая его вместо настоящей проверки, читала молчание как «отставших нет».

🩸 ПОЧЕМУ ЭТА ПРИЁМКА ПОЯВИЛАСЬ ПОЗЖЕ ПРАВКИ, И ЭТО МОЙ ПРОМАХ, А НЕ ПОРЯДОК. Правка (коммит
9fc7f98) была доказана РУЧНЫМИ прогонами в трёх раскладках — и ручной прогон не покраснеет, когда
кто-нибудь вернёт прежнее поведение. Критерии ② и ③ карточки требовали ровно постоянного случая,
и полдня карточка стояла закрытой работой, но не закрытой приёмкой.

⚖️ УСТРОЙСТВО, РАДИ КОТОРОГО СЛУЧАИ РАЗДЕЛЕНЫ НА ДВА РОДА — требование критерия ③ «нарочная
поломка валит РОВНО ОДИН случай». Прежнее поведение (пустой вывод, код 0) живёт в блоке
`__main__`, и если бы указатель судился ТОЖЕ запуском процесса, возврат прежнего поведения
покраснел бы сразу во всех случаях: пустой вывод не содержит никакого указателя.
   ⇒ случай ① судит ПРОЦЕСС (код выхода и непустой вывод),
     случаи ②–⑤ судят ФУНКЦИЮ `_where_is_the_check()` вызовом из кода,
     случай ⑥ судит, что точка входа не сломала библиотеку.
Поэтому поломка блока запуска валит ровно ①, а поломка указателя — ровно его случаи. Разделение
здесь не красота, а единственный способ выполнить критерий.

🔴 ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
   · судится ОТКАЗ и УКАЗАТЕЛЬ, а не правильность самого счёта отставания — его судят
     guard-section-lag.py, bite-memory-lag.py и bite-section-lag-change.py;
   · раскладки собираются КОПИЕЙ модуля в каталоги-пустышки: живой контур и живая база
     не открываются вовсе, ни на чтение, ни на запись;
   · «проверка рядом» в стендах — пустой файл с нужным ИМЕНЕМ: указатель судит наличие файла,
     а не его работоспособность, и приёмка не притворяется, что судит больше.

Исходы: 0 — все случаи прошли · 1 — провал · 2 — НЕЧЕМ ПРОВЕРИТЬ (причина названа строкой).
Прогон:  python <это>                      # случаи
         python <это> --selftest           # нарочные поломки на КОПИИ модуля
"""
import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECK_NAME = "guard-section-lag.py"
PUBLIC_NAMES = ("section_lag", "memory_lag", "lag_line", "state_change",
                "LAG_HOURS", "STATE_CHANGE_NAMES")


def find_module(explicit=None):
    """Где лежит испытуемый модуль. Ищу рядом с собой: приёмка живёт и в контуре
    (vnext-tools/, модуль в ../.mezosync/scripts/), и в клоне пакета
    (vnext/prototype/, модуль в ../../scripts/).
    """
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / ".mezosync" / "scripts" / "phoenix_lag.py",
                      here.parent.parent / "scripts" / "phoenix_lag.py",
                      here.parent.parent / ".mezosync" / "scripts" / "phoenix_lag.py"):
        if candidate.is_file():
            return candidate
    return None


def stand(root, kind, module_src, check_there=True, check_as=CHECK_NAME):
    """Собрать раскладку-пустышку и вернуть путь к КОПИИ модуля в ней.

    kind='контур' .... <стенд>/.mezosync/scripts/phoenix_lag.py + <стенд>/vnext-tools/<проверка>
    kind='пакет' ..... <стенд>/scripts/phoenix_lag.py + <стенд>/vnext/prototype/<проверка>
    Это РОВНО те два случая, которые различает сам указатель; третий — когда рядом нет ничего.
    """
    base = Path(root)
    if kind == "контур":
        mod_dir = base / ".mezosync" / "scripts"
        check_dir = base / "vnext-tools"
    elif kind == "пакет":
        mod_dir = base / "scripts"
        check_dir = base / "vnext" / "prototype"
    else:
        raise ValueError("раскладка бывает «контур» или «пакет», дано: " + repr(kind))
    mod_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(module_src, mod_dir / "phoenix_lag.py")
    if check_there:
        check_dir.mkdir(parents=True, exist_ok=True)
        (check_dir / check_as).write_text("# пустышка: указатель судит ИМЯ файла\n",
                                          encoding="utf-8")
    return mod_dir / "phoenix_lag.py"


def pointer_of(module_path):
    """Позвать `_where_is_the_check()` у КОПИИ модуля в стенде — функцией, не процессом."""
    spec = importlib.util.spec_from_file_location(
        "phoenix_lag_stand_" + str(abs(hash(str(module_path)))), module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module._where_is_the_check()


def run_direct(module_path):
    """Прямой запуск КОПИИ модуля отдельным процессом — так его зовёт рука роли."""
    res = subprocess.run([sys.executable, str(module_path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, (res.stdout or ""), (res.stderr or "")


def judge(module_src):
    """Шесть случаев. Возвращает список (имя, прошёл, что видно)."""
    out = []
    with tempfile.TemporaryDirectory(prefix="bite-lag-entry-") as tmp:
        root = Path(tmp)

        # ① ПРОЦЕСС: прямой запуск ОТКАЗЫВАЕТ, а не молчит с кодом 0.
        contour = stand(root / "s1", "контур", module_src)
        code, stdout, stderr = run_direct(contour)
        said = stdout.strip() or stderr.strip()
        ok1 = code == 2 and bool(said)
        out.append(("① прямой запуск: код выхода 2 и непустой вывод",
                    ok1, f"код {code} · байт вывода {len(stdout)}"))

        # ② УКАЗАТЕЛЬ в раскладке контура называет файл, который ЕСТЬ на диске.
        _, p_contour = pointer_of(contour)
        named = p_contour.replace("python ", "").strip()
        exists = Path(named).is_file() if named.endswith(".py") else False
        ok2 = exists and named.endswith("vnext-tools/" + CHECK_NAME)
        out.append(("② раскладка контура: назван СУЩЕСТВУЮЩИЙ файл vnext-tools/",
                    ok2, named))

        # ③ УКАЗАТЕЛЬ в раскладке пакета называет ДРУГОЕ место. Это и есть доказательство
        #    критерия ②: путь не вписан в код, иначе обе раскладки дали бы одно и то же.
        pack = stand(root / "s2", "пакет", module_src)
        _, p_pack = pointer_of(pack)
        named_pack = p_pack.replace("python ", "").strip()
        ok3 = (named_pack.endswith("vnext/prototype/" + CHECK_NAME)
               and Path(named_pack).is_file()
               and named_pack != named)
        out.append(("③ раскладка пакета: назван ДРУГОЙ существующий файл vnext/prototype/",
                    ok3, named_pack))

        # ④ ПЕРЕИМЕНОВАНИЕ в копии каталога: указатель НЕ называет исчезнувший путь.
        #    Вписанный в код путь продолжал бы уверенно указывать на то, чего нет.
        renamed = stand(root / "s3", "контур", module_src,
                        check_as="guard-section-lag-ПЕРЕИМЕНОВАНА.py")
        _, p_renamed = pointer_of(renamed)
        points_nowhere = ("не найден" in p_renamed
                          and "vnext-tools/" in p_renamed
                          and "vnext/prototype/" in p_renamed)
        ok4 = points_nowhere and not Path(
            p_renamed.replace("python ", "").strip()).is_file()
        out.append(("④ проверка ПЕРЕИМЕНОВАНА: указатель не называет исчезнувший путь",
                    ok4, p_renamed.replace("\n", " ")[:120]))

        # ⑤ ВСТРЕЧНЫЙ: рядом нет НИЧЕГО — тот же честный запасной текст с ДВУМЯ местами.
        #    Без него случай ④ не отличить от случая, который краснеет всегда.
        bare = stand(root / "s4", "контур", module_src, check_there=False)
        _, p_bare = pointer_of(bare)
        ok5 = ("не найден" in p_bare and "vnext-tools/" in p_bare
               and "vnext/prototype/" in p_bare)
        out.append(("⑤ ВСТРЕЧНЫЙ: проверки нет вовсе — названы ОБА места",
                    ok5, p_bare.replace("\n", " ")[:120]))

        # ⑥ ВСТРЕЧНЫЙ: точка входа не сломала библиотеку — импорт отдаёт все публичные имена.
        #    Отказ прямого запуска не должен стоить ничего тем, кто зовёт модуль из кода.
        module, _ = pointer_of(contour)
        missing = [n for n in PUBLIC_NAMES if not hasattr(module, n)]
        out.append(("⑥ ВСТРЕЧНЫЙ: импорт модуля отдаёт все публичные имена",
                    not missing, "нет: " + ", ".join(missing) if missing else "все 6 на месте"))
    return out


# 🪤 Нарочные поломки. Ожидания записаны ЗДЕСЬ, рядом с поломкой, ДО прогона: поломка,
#    перестающая валить свои случаи, — сама находка.
BREAKS = [
    ("A возврат прежнего поведения: пустой вывод и код 0",
     '    raise SystemExit(2)',
     '    raise SystemExit(0)  # НАРОЧНАЯ ПОЛОМКА: отвечаем как пройденная проверка',
     ["①"]),
    ("B путь проверки ВПИСАН в код вместо поиска рядом",
     '    here = Path(__file__).resolve().parent',
     '    return "python /вписанный/путь/guard-section-lag.py"  # НАРОЧНАЯ ПОЛОМКА\n'
     '    here = Path(__file__).resolve().parent',
     ["②", "③", "④", "⑤"]),
]


def selftest(module_src):
    """Каждая поломка — на КОПИИ модуля; живой файл не трогается вовсе."""
    print("🪤 НАРОЧНЫЕ ПОЛОМКИ — на копии модуля, живой файл не тронут")
    text = Path(module_src).read_text(encoding="utf-8")
    all_good = True
    for name, old, new, expect in BREAKS:
        if old not in text:
            print(f"   ⛔ НЕЧЕМ ПРОВЕРИТЬ · {name}: якоря нет в модуле — {old.strip()!r}")
            return 2
        with tempfile.TemporaryDirectory(prefix="bite-lag-broken-") as tmp:
            broken = Path(tmp) / "phoenix_lag.py"
            broken.write_text(text.replace(old, new, 1), encoding="utf-8")
            # Различитель — ИМЕНА (первый знак имени случая), а не ЧИСЛО провалов: поломка,
            # уронившая другой случай в том же количестве, иначе прошла бы за свою.
            fell = [name[0] for name, ok, _ in judge(broken) if not ok]
        exactly = sorted(fell) == sorted(expect)
        all_good = all_good and exactly
        print(f"   {'✅' if exactly else '⛔'} {name}")
        print(f"      провалились: {' '.join(fell) if fell else 'НИ ОДНОГО'}"
              f" · ждали: {' '.join(expect)}")
    print("")
    print("✅ каждая поломка валит РОВНО свои случаи — случаи независимы" if all_good
          else "⛔ поломка валит не свои случаи: либо случай лишний, либо ожидание неверно")
    return 0 if all_good else 1


def main():
    ap = argparse.ArgumentParser(
        description="приёмка точки входа phoenix_lag.py (карточка 756)")
    ap.add_argument("--module", help="путь к испытуемому phoenix_lag.py "
                                     "(по умолчанию ищется рядом)")
    ap.add_argument("--selftest", action="store_true",
                    help="нарочные поломки на копии модуля")
    args = ap.parse_args()

    module_src = find_module(args.module)
    if module_src is None:
        where = args.module or "рядом с приёмкой (.mezosync/scripts или ../scripts)"
        print(f"⛔ НЕЧЕМ ПРОВЕРИТЬ: phoenix_lag.py не найден — {where}")
        print("   «не нашёл испытуемое» и «испытуемое в порядке» — разные факты, "
              "и кода 0 здесь не будет")
        return 2

    print(f"испытуемое: {module_src}")
    if args.selftest:
        return selftest(module_src)

    cases = judge(module_src)
    failed = 0
    for name, ok, seen in cases:
        if not ok:
            failed += 1
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        print(f"       {seen}")
    print("")
    if failed:
        print(f"⛔ ПРОВАЛОВ {failed} из {len(cases)}")
        return 1
    print(f"✅ ПРИНЯТО: {len(cases)} из {len(cases)}, из них встречных 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
