#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""guard-install-lag.py — ОТСТАВАНИЕ УСТАНОВКИ ВТОРОГО НАБОРА: пакет против контура.

ЗАЧЕМ (карточка #758). Второй набор инструментов контура — копия файлов vnext/prototype
пакета. На 2026-11-14 в пакете 294 файла, у контура 248, и 46 имён не установлены.
Об этом отставании НЕ ГОВОРИЛА НИ ОДНА проверка общего прогона, а два места, где оно
видно, объявляли его НОРМОЙ дословно:
  · сверка копий (guard-scripts-drift.py):
        «✅ и 46 есть только в пакете — НОРМА: update-tools.py ставит во второй каталог
         лишь те файлы, что там уже лежат»
  · план обновления (update-tools.py):
        «ℹ️ Вне обновления: 42 звеньев источника, которых у тебя нет … Их не зовёт ни один
         скрипт источника — сборка их не кладёт, обновление не приносит и не выдумывает»
Оба утверждения ВЕРНЫ про механизм и оба молчат о последствии: приёмка, написанная после
этапа Э4 (2026-10-09, карточка #678: перенос контур → пакет снят, пакет — единственный
источник), в контур не приезжает НИКОГДА. Установщик ставит лишь то, что уже лежит, или
то, что зовут рабочие скрипты; приёмку не зовёт никто — она конечная точка.

🪤 РУБЕЖ ВИДЕН ДАТОЙ, А НЕ РАССУЖДЕНИЕМ (замер 2026-11-14, даты появления в пакете):
    05.08 … 14.08 .... 24 файла — эпоха прототипа v-next
    14.08 → 09.10 .... ДВА МЕСЯЦА без единого нового
    09.10 … 14.11 .... 19 файлов — ровно со дня Э4 и по сей день
Совпадение дня первых трёх файлов второго набора с днём Э4 — знак в знак.

⚖️ ЧТО ЭТА ПРОВЕРКА СУДИТ И ЧЕГО НЕ СУДИТ — названо сразу, чтобы зелёное не прочли шире:
  судит ....... СОСТОЯНИЕ УСТАНОВКИ: имя есть в пакете и нет у контура
  НЕ судит .... РАБОТОСПОСОБНОСТЬ установленного. Инструмент зависит от того, что лежит
                рядом с ним, и совпадение имён этого не доказывает. Прецедент в теле
                сверки копий: 14 файлов перенесли из пакета руками, ДЕВЯТЬ не работают
                вовсе — строят стенд из схемы, лежащей рядом с пакетом.
  НЕ судит .... НУЖНОСТЬ. Перечень законных отсутствий ниже — РЕШЕНИЯ РОЛИ с причиной
                и датой, а не вывод машины: вердикт «нужна ли вещь контуру» из текста
                файла не выводится. Замер 2026-11-14 показал это числом: два разных
                признака по одному и тому же тексту дали 35 и 14 «отставших» — значит
                ни один из них не судья.

ЗАПУСК (АБСОЛЮТНЫЙ путь):
    python <КОНТУР>/vnext-tools/guard-install-lag.py            # код 1 при отставании
    python <КОНТУР>/vnext-tools/guard-install-lag.py --selftest  # доказать, что краснеет
    python <КОНТУР>/vnext-tools/guard-install-lag.py --names     # только имена, по одному в строке
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── ЗАКОННЫЕ ОТСУТСТВИЯ: имя → (причина, когда решено) ───────────────────────────────────
# ⛔ Это РЕШЕНИЯ, а не догадки машины: у каждого названы причина и день. Имя, попавшее сюда
# без причины, превратило бы проверку в способ гасить красное — потому пустая причина
# считается дефектом перечня (случай ниже) и краснеет.
# ⚖️ И ВСТРЕЧНОЕ СВОЙСТВО: имя из этого перечня, КОТОРОЕ ПОЯВИЛОСЬ в контуре, тоже краснеет.
# Иначе перечень протухает молча и продолжает оправдывать отсутствие того, что уже стои́т.
LEGITIMATE_ABSENCES = {
    # ⓐ прототип v-next: схема v-next в контуре не раскатана, фаза 4 действует с 16.07.2026
    "cursor-advance.py": ("прототип v-next: по своей же шапке пишет только в песочницу "
                          "и живую базу не открывает вовсе; схема v-next не раскатана",
                          "2026-11-14"),
    "migrate-addressee.py": ("прототип v-next: перенос на схему v-next, которая не раскатана",
                             "2026-11-14"),
    "bite-addressee.py": ("приёмка прототипа v-next: строит стенд из schema_vnext.sql",
                          "2026-11-14"),
    "bite-closure.py": ("приёмка прототипа v-next: судит write-message-vnext.py, "
                        "которого в контуре нет", "2026-11-14"),
    "bite-cursor.py": ("приёмка прототипа v-next: судит cursor-advance.py, которого нет",
                       "2026-11-14"),
    "bite-migration.py": ("приёмка прототипа v-next: судит migrate-live.py, которого нет",
                          "2026-11-14"),
    "bite-task.py": ("приёмка прототипа v-next: строит стенд из schema_vnext.sql",
                     "2026-11-14"),
    "bite-thread.py": ("приёмка прототипа v-next: строит стенд из schema_vnext.sql",
                       "2026-11-14"),
    # ⓑ вердикт вынесен раньше или работа состоялась
    "feed-index.py": ("вердикт PROTO 2026-08-27: замысел указателя переехал "
                      "в read-messages.py; карточка #758 этот вердикт не меняет",
                      "2026-08-27"),
    "migrate-live.py": ("перенос живой базы на схему v-next: накат фазы 4 состоялся "
                        "2026-07-16, повторного переноса не будет", "2026-11-14"),
    # ⓒ предмет — служба, которой в контуре нет
    "bite-periscope-steps-births.py": ("судит службу Gordi.Periscope.Api, которая живёт "
                                       "только в пакете; в контуре её нет", "2026-11-14"),
}


def tools_in(directory):
    """Имена .py верхнего уровня каталога. Второй набор плоский: подкаталогов в нём нет
    ни у пакета, ни у контура (перемерено 2026-11-14), и глубокий обход дал бы ложную
    пару с шагами схемы, которые живут в первом наборе."""
    return {p.name for p in directory.glob("*.py")}


def first_set_names(container):
    """Имена первого набора — рабочие скрипты контура и шаги схемы. Одно имя, два места:
    guard-shift-end.py стои́т именно там, и без этой проверки он читался бы как отсутствующий."""
    scripts = container / ".mezosync" / "scripts"
    names = {p.name for p in scripts.glob("*.py")}
    names |= {p.name for p in (scripts / "migrations").glob("*.py")}
    return names


def resolve_paths():
    """Каталоги из файла путей контура. Впечатанный путь судил бы чужой контур — это уже
    случалось со сверкой копий (находка контура tapas 2026-08-19)."""
    sys.path.insert(0, str(HERE))
    scripts_dir = HERE.parent / ".mezosync" / "scripts"
    if scripts_dir.is_dir():
        sys.path.insert(0, str(scripts_dir))
    try:
        import mezo_paths
    except Exception as exc:                              # noqa: BLE001
        return None, None, f"файл путей читать нечем: mezo_paths не импортируется ({exc})"
    lookup = getattr(mezo_paths, "local_path", None)
    if lookup is None:
        return None, None, "mezo_paths старше файла путей — ключей установки у него нет"
    try:
        pack = lookup("template_checkout", __file__)
        second = lookup("prototype_install_dir", __file__)
    except (SystemExit, Exception) as exc:                # noqa: BLE001
        return None, None, f"файл путей не прочитан ({exc})"
    pack_dir = (pack.path / "vnext" / "prototype"
                if pack.outcome == mezo_paths.LOCAL_DECLARED and pack.path is not None else None)
    second_dir = (second.path
                  if second.outcome == mezo_paths.LOCAL_DECLARED and second.path is not None
                  else None)
    if pack_dir is None:
        return None, None, ("клон пакета не объявлен (ключ template_checkout) — сверять "
                            "установку НЕ С ЧЕМ")
    if not pack_dir.is_dir():
        return None, None, f"каталог второго набора пакета не найден: {pack_dir}"
    if second_dir is None:
        return None, None, ("второй каталог установки не объявлен (ключ "
                            "prototype_install_dir) — у этого контура второго набора нет")
    if not second_dir.is_dir():
        return None, None, f"второй каталог установки объявлен, но не найден: {second_dir}"
    return pack_dir, second_dir, None


def judge(pack_dir, install_dir, container, absences=None):
    """Три разряда по каждому имени пакета. Возвращает (отставшие, законные, протухшие)."""
    absences = LEGITIMATE_ABSENCES if absences is None else absences
    pack = tools_in(pack_dir)
    installed = tools_in(install_dir)
    first = first_set_names(container)
    missing = sorted(pack - installed - first)
    lagging = sorted(n for n in missing if n not in absences)
    legit = sorted(n for n in missing if n in absences)
    # перечень протух: имя оправдано как отсутствующее, а оно установлено
    stale = sorted(n for n in absences if n in installed or n in first)
    no_reason = sorted(n for n, (why, _) in absences.items() if not (why or "").strip())
    return lagging, legit, stale, no_reason, len(pack), len(installed)


def main():
    parser = argparse.ArgumentParser(
        description="отставание установки второго набора инструментов: пакет против контура")
    parser.add_argument("--names", action="store_true",
                        help="печатать только отставшие имена, по одному в строке")
    parser.add_argument("--selftest", action="store_true",
                        help="изъять один установленный инструмент в КОПИИ и показать, "
                             "что проверка краснеет ровно на одном имени")
    parser.add_argument("--pack-dir", help="каталог второго набора пакета (для самопроверки)")
    parser.add_argument("--install-dir", help="каталог установки (для самопроверки)")
    parser.add_argument("--container", help="контейнер контура (для самопроверки)")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if args.pack_dir and args.install_dir:
        pack_dir = Path(args.pack_dir)
        install_dir = Path(args.install_dir)
        container = Path(args.container) if args.container else install_dir.parent
        # 🪤 НАЙДЕНО СВОЕЙ ЖЕ ПРИЁМКОЙ (случай ⑥, 2026-11-14): существование каталогов
        # проверялось ТОЛЬКО в resolve_paths(), и явный путь эту проверку обходил. Пакет,
        # которого нет, читался как пакет из нуля файлов — и проверка печатала «отставания
        # установки нет». Зелёное от пустого каталога неотличимо от зелёного от порядка:
        # это ровно тот класс, ради которого проверка и заведена.
        note = None
        if not pack_dir.is_dir():
            note = f"каталог второго набора пакета не найден: {pack_dir}"
        elif not install_dir.is_dir():
            note = f"каталог установки не найден: {install_dir}"
    else:
        pack_dir, install_dir, note = resolve_paths()
        container = HERE.parent

    if note is not None:
        print(f"⚠️ СВЕРИТЬ НЕЧЕМ: {note}")
        print("   ⚖️ Это НЕ «отставания нет» — это «узнать нечем». Разница существенна: "
              "первое гасит долг, второе его только скрывает.")
        return 0

    lagging, legit, stale, no_reason, n_pack, n_inst = judge(pack_dir, install_dir, container)

    if args.names:
        for name in lagging:
            print(name)
        return 1 if lagging else 0

    print(f"пакет .... {pack_dir}: {n_pack} инструментов второго набора")
    print(f"контур ... {install_dir}: {n_inst} установлено")
    print("")

    if legit:
        print(f"✅ законных отсутствий {len(legit)} — ИМЕНАМИ и с причиной, не числом:")
        for name in legit:
            why, when = LEGITIMATE_ABSENCES[name]
            print(f"   · {name}")
            print(f"       {why} (решено {when})")
        print("")

    if no_reason:
        print(f"⛔ перечень законных отсутствий ДЕФЕКТЕН: без причины {len(no_reason)} — "
              f"{', '.join(no_reason)}")
        print("   👉 имя без причины гасит красное, ничего не объясняя; впиши причину и день")

    if stale:
        print(f"⛔ перечень законных отсутствий ПРОТУХ: {len(stale)} имён оправданы как "
              f"отсутствующие, а они УСТАНОВЛЕНЫ — {', '.join(stale)}")
        print("   👉 убери их из перечня: оправдание установленного учит, что его нет")

    if not lagging:
        print("✅ отставания установки нет: каждое имя пакета либо установлено, либо "
              "названо законным отсутствием с причиной")
        print("   ⚖️ ГРАНИЦА: сверено СОСТОЯНИЕ УСТАНОВКИ, не работоспособность. "
              "Инструмент зависит от того, что лежит рядом, — это доказывает только ПРОГОН.")
        return 1 if (stale or no_reason) else 0

    print(f"⛔ ОТСТАВАНИЕ УСТАНОВКИ: {len(lagging)} инструментов есть в пакете и НЕ "
          f"установлены в контуре, причина для них не названа")
    for name in lagging:
        print(f"   🔴 {name}")
    print("   👉 роль идёт за инструментом по пути из своей памяти и не находит его: "
          "в пакете он есть, у неё — нет.")
    print("   ⚠️ И штатного пути для него нет: перенос контур → пакет снят этапом Э4, "
          "а установщик ставит только то, что уже лежит у контура или что зовут "
          "рабочие скрипты. Приёмку не зовёт никто — значит она не приедет никогда.")
    print("   ⛔ Обратно руками «чтобы проверка замолчала» не докладывать: часть файлов "
          "пакета работает только рядом с его схемой и стендом (прецедент: из 14 "
          "перенесённых девять не работали). Разбирать поимённо.")
    return 1


def selftest():
    """Нарочная поломка: изъятие ОДНОГО установленного инструмента в КОПИИ обоих каталогов.

    Копия, а не живой каталог: проверка, доказывающая свою чувствительность порчей того,
    что судит, оставляет контур без инструмента, если прогон прервётся на середине.
    """
    pack_dir, install_dir, note = resolve_paths()
    if note is not None:
        print(f"⚠️ самопроверке сверять нечем: {note}")
        return 2
    container = HERE.parent
    ok = True
    temp_root = Path(tempfile.mkdtemp(prefix="install-lag-selftest-"))
    try:
        pack_copy = temp_root / "pack"
        inst_copy = temp_root / "install"
        shutil.copytree(pack_dir, pack_copy)
        shutil.copytree(install_dir, inst_copy)

        base_lag, _, _, _, _, _ = judge(pack_copy, inst_copy, container)
        print(f"① нетронутая копия: отставших {len(base_lag)}")

        # ВСТРЕЧНЫЙ: без него случай ② прошёл бы и на проверке, которая краснеет всегда.
        victim = None
        for candidate in sorted(tools_in(inst_copy)):
            if candidate in tools_in(pack_copy) and candidate not in LEGITIMATE_ABSENCES:
                victim = candidate
                break
        if victim is None:
            print("⛔ самопроверка невозможна: в копии нет ни одного установленного имени, "
                  "которое есть и в пакете")
            return 2

        (inst_copy / victim).unlink()
        after_lag, _, _, _, _, _ = judge(pack_copy, inst_copy, container)
        added = sorted(set(after_lag) - set(base_lag))
        print(f"② изъят один установленный ({victim}): отставших {len(after_lag)}")
        if added == [victim]:
            print(f"   ✅ проверка покраснела РОВНО на одном имени — {victim}")
        else:
            ok = False
            print(f"   ⛔ ждали ровно [{victim}], получили {added}")

        # ③ ВСТРЕЧНЫЙ: протухший перечень краснеет. Имя установлено и объявлено отсутствующим.
        installed_name = sorted(tools_in(inst_copy))[0]
        fake = {installed_name: ("нарочно ложная причина для самопроверки", "2026-11-14")}
        _, _, stale, _, _, _ = judge(pack_copy, inst_copy, container, absences=fake)
        if stale == [installed_name]:
            print(f"③ ✅ протухшее оправдание найдено: {installed_name} установлен, "
                  f"а объявлен отсутствующим")
        else:
            ok = False
            print(f"③ ⛔ протухшее оправдание НЕ найдено: ждали [{installed_name}], "
                  f"получили {stale}")

        # ④ ВСТРЕЧНЫЙ: причина пустая — дефект перечня, а не тихое оправдание.
        empty = {"нет-такого-файла.py": ("", "2026-11-14")}
        _, _, _, no_reason, _, _ = judge(pack_copy, inst_copy, container, absences=empty)
        if no_reason == ["нет-такого-файла.py"]:
            print("④ ✅ оправдание без причины названо дефектом перечня")
        else:
            ok = False
            print(f"④ ⛔ оправдание без причины НЕ названо: {no_reason}")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print("")
    print("✅ самопроверка прошла: поломка валит ровно своё имя, три встречных случая на месте"
          if ok else "⛔ САМОПРОВЕРКА ПРОВАЛИЛАСЬ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
