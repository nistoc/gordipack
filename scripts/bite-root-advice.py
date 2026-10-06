# -*- coding: utf-8 -*-
"""Приёмка: советы в отказе поиска корня ИСПОЛНЯЮТСЯ, а не только напечатаны.

Повод — заявка @PROTO (записка #3713 ②): отказ называл два выхода, и оба были мертвы.
Роль выполняла оба, получала тот же отказ слово в слово и решала, что сломан механизм.

🎯 ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, А ЧТО НЕТ. Проверяется ИСПОЛНИМОСТЬ совета: механизм, запущенный
из каталога без корня, после выполнения совета РАБОТАЕТ. Не проверяется формулировка —
текст можно переписать как угодно, лишь бы названное в нём срабатывало.
⛔ Случай ① («без советов — отказ») без встречных ②③ доказывал бы только то, что механизм
умеет падать. Именно так дефект и прожил: отказ был громким и выглядел исправным.

🪤 КОНТУР ДЛЯ СОВЕТОВ — СОБРАННЫЙ, А НЕ ТОТ, НА КОТОРЫЙ УКАЗЫВАЕТ МЕСТО ПРИЁМКИ (починка (б),
этап Э4 карточки #678, 2026-10-06). Прежде советы ②③④ и случай ⑦ шли в контур по месту самой
приёмки: контейнер — каталог выше её каталога, база — рядом с ним. В живом контуре это живая
база; в клоне пакета — корень клона, где лежал пустой mezosync.db в 0 байт. Замер 06.10: рабочие
копии пакета на 8eaa287 и 7d55cb9 — 6 из 9 и 8 из 11 (②③④ не проходят), живой Atlas — 11 из 11.
Случаи судили МЕСТО файла, а не механизм. Теперь настоящий контур собирает сборщик пакета
init-group.py во временном каталоге, а испытуемые mezo_paths.py и lease.py кладутся в него поверх
собранных: исход один и тот же, где бы приёмка ни лежала.

⑨ ⑩ ⑪ — пустой файл базы НЕ признак контура ни для одного из трёх поисков: корня мезосинка
(mezo_root), каталога группы (container_root) и пакета (template_root). ⑨-бис — нарочная поломка:
на копии mezo_paths.py с прежним признаком «файл есть» все три случая не проходят.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = pathlib.Path(__file__).resolve().parent
OK = FAIL = 0

# Нарочная поломка ⑨-бис: признак базы снова «файл есть», как до починки (б).
BREAK_ANCHOR = "        return path.is_file() and path.stat().st_size > 0\n"
BREAK_TEXT = "        return path.is_file()\n"


def case(name, cond, detail=""):
    global OK, FAIL
    print(f"{'✅' if cond else '⛔'} {name}")
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1


def clean_env(env=None):
    """Среда вызывающего без переменных, которые направили бы поиск в чужой контур или пакет."""
    e = dict(os.environ)
    e.pop("MEZO_CONTAINER", None)
    e.pop("MEZO_TEMPLATE", None)
    e["PYTHONIOENCODING"] = "utf-8"
    if env:
        e.update(env)
    return e


def run(cwd, args, env=None):
    p = subprocess.run([sys.executable, "lease.py", "status", *args], cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=clean_env(env), timeout=60)
    return (p.stdout or "") + (p.returncode and (p.stderr or "") or ""), p.returncode


def py(cwd, code):
    """Одна строка Python в каталоге cwd, где лежит испытуемый mezo_paths.py."""
    p = subprocess.run([sys.executable, "-c", code], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=clean_env(), timeout=60)
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def find_pack():
    """Корень пакета со сборщиком scripts/init-group.py; не нашёлся — None.

    Сперва template_root испытуемого mezo_paths (он не принимает живой контур за пакет и знает
    ключ template файла путей), затем каталог выше этой приёмки — в клоне пакета это сам пакет."""
    candidates = []
    try:
        import mezo_paths
        candidates.append(mezo_paths.template_root(str(SCRIPTS / "mezo_paths.py")))
    except SystemExit:
        pass
    candidates.append(SCRIPTS.parent)

    def live(p):  # каталог .mezosync живого контура несёт тот же сборщик, но пакетом не является
        db = p / "mezosync.db"
        return db.is_file() and db.stat().st_size > 0

    return next((p for p in candidates if (p / "scripts" / "init-group.py").is_file() and not live(p)),
                None)


def build_contour(box, pack):
    """Настоящий контур для советов: сборщик пакета во временном каталоге, испытуемые файлы поверх.

    → (корень контура, база, пусто) либо (None, None, хвост вывода сборщика)."""
    root = box / "контур"
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str(pack / "scripts" / "init-group.py"), "--name", "rootadvice",
                        "--path", str(mez), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                       env=mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8"))
    db = mez / "mezosync.db"
    if r.returncode != 0 or not (mez / "scripts").is_dir() or not db.is_file() or db.stat().st_size == 0:
        return None, None, ((r.stdout or "") + (r.stderr or ""))[-600:]
    for f in ("mezo_paths.py", "lease.py"):
        shutil.copy(SCRIPTS / f, mez / "scripts" / f)
    return root, db, ""


def place_tools(dest, mp_text, with_lease=True):
    """Каталог инструментов: mezo_paths.py с данным текстом и (по желанию) lease.py рядом."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "mezo_paths.py").write_bytes(mp_text.encode("utf-8"))
    if with_lease:
        shutil.copy(SCRIPTS / "lease.py", dest / "lease.py")
    return dest


def empty_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def phantom_cases(base, mp_text):
    """Три поиска рядом с пустым mezosync.db; → {номер: (держится ли, пояснение)}.

    ⑨ корень мезосинка: пустой файл в предке — отказ «корень НЕ НАЙДЕН», он называет пустой файл,
       и файл остаётся пустым (в него ничего не записано).
    ⑩ каталог группы: пустой .mezosync/mezosync.db в предке — отказ «контейнер НЕ НАЙДЕН» с тем же.
    ⑪ пакет: пустой mezosync.db в корне пакета не прячет пакет — template_root его находит."""
    res = {}
    # ⑨
    d9 = base / "корень-с-пустышкой"
    ph9 = empty_db(d9 / "mezosync.db")
    tools9 = place_tools(d9 / "инструменты", mp_text)
    out, code = run(tools9, [])
    held = (code != 0 and "корень мезосинка НЕ НАЙДЕН" in out and "пустой файл" in out
            and ph9.stat().st_size == 0)
    res["⑨"] = (held, f"код {code} · отказ={'корень мезосинка НЕ НАЙДЕН' in out} · пустой файл назван="
                      f"{'пустой файл' in out} · размер пустышки после {ph9.stat().st_size}")
    # ⑩
    d10 = base / "контейнер-с-пустышкой"
    empty_db(d10 / ".mezosync" / "mezosync.db")
    tools10 = place_tools(d10 / "инструменты", mp_text, with_lease=False)
    out, code = py(tools10, "import mezo_paths; print('НАЙДЕН:', mezo_paths.container_root('x.py'))")
    held = code != 0 and "контейнер группы НЕ НАЙДЕН" in out and "пустой файл" in out
    res["⑩"] = (held, f"код {code} · {out.strip().splitlines()[0][:90] if out.strip() else 'пусто'}")
    # ⑪
    d11 = base / "пакет-с-пустышкой"
    empty_db(d11 / "mezosync.db")
    tools11 = place_tools(d11 / "scripts", mp_text, with_lease=False)
    (tools11 / "init-group.py").write_text("# заглушка: признак пакета для template_root\n", encoding="utf-8")
    out, code = py(tools11, "import mezo_paths; print('НАЙДЕН:', mezo_paths.template_root('x.py'))")
    found = out.strip().splitlines()[0] if out.strip() else ""
    # Сравниваются РАЗРЕШЁННЫЕ пути: на Windows временный каталог приходит коротким именем 8.3,
    # а template_root печатает длинное — строки разные при одном и том же каталоге.
    held = (code == 0 and found.startswith("НАЙДЕН: ")
            and pathlib.Path(found[len("НАЙДЕН: "):]).resolve() == d11.resolve())
    res["⑪"] = (held, f"код {code} · {found[:90] or 'пусто'}")
    return res


def main():
    box = mezo_stand.new("root-advice-")
    sirota = box / "нет-корня"
    sirota.mkdir()
    for f in ("mezo_paths.py", "lease.py"):
        shutil.copy(SCRIPTS / f, sirota / f)

    # ① БЕЗ СОВЕТОВ — отказ, и он ГРОМКИЙ
    out, code = run(sirota, [])
    case("① из каталога без корня — отказ, а не тихая работа",
         code != 0 and "корень мезосинка НЕ НАЙДЕН" in out,
         f"код возврата {code}")

    # ①-бис ПУСТАЯ БАЗА НЕ ПОЯВИЛАСЬ — то, ради чего громкий отказ и заводили
    strays = list(box.rglob("mezosync.db"))
    case("①-бис пустая база НЕ создана ни здесь, ни уровнем выше",
         not strays,
         "найдено: " + (", ".join(str(s) for s in strays) if strays else "ничего"))

    # Настоящий контур для советов ②③④ и случая ⑦ — сборщиком пакета (см. шапку)
    pack = find_pack()
    if pack is None:
        print("⛔ НЕ ЗАПУСТИЛАСЬ: пакета со сборщиком scripts/init-group.py не нашлось — ни по\n"
              "   mezo_paths.template_root (MEZO_TEMPLATE или ключ template файла путей), ни выше приёмки.")
        mezo_stand.release(box)
        return 2
    contour, db, note = build_contour(box, pack)
    case("⑧-бис контроль: настоящий контур для советов собран сборщиком пакета",
         contour is not None,
         f"{contour} (сборщик: {pack})" if contour else f"сборщик {pack}: {note}")
    if contour is None:
        mezo_stand.release(box)
        print(f"\nИТОГ: {OK}/{OK + FAIL}")
        return 1

    # ② СОВЕТ ПЕРВЫЙ: переменная среды — ИСПОЛНЯЕТСЯ
    out, code = run(sirota, [], {"MEZO_CONTAINER": str(contour)})
    case("② совет «MEZO_CONTAINER=<контейнер>» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code} · {out.splitlines()[0][:78] if out else 'пусто'}")

    # ③ СОВЕТ ВТОРОЙ: абсолютный путь к базе — ИСПОЛНЯЕТСЯ
    out, code = run(sirota, ["--db", str(db)])
    case("③ совет «абсолютный --db» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code} · {out.splitlines()[0][:78] if out else 'пусто'}")

    # ④ СОВЕТ ТРЕТИЙ: файл путей рядом с механизмом — ИСПОЛНЯЕТСЯ. С карточки #677 (Э3-Р4) это
    # <каталог скриптов>/../local/paths.json, ключ container; прежняя строка container= в
    # local.paths больше не читается (случай ④-бис).
    paths_file = box / "local" / "paths.json"
    paths_file.parent.mkdir()
    paths_file.write_text(json.dumps({"container": str(contour)}), encoding="utf-8")
    out, code = run(sirota, [])
    case("④ совет «ключ container в файле путей» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code}")
    paths_file.unlink()

    # ④-бис ВСТРЕЧНЫЙ к ④: прежняя строка container= в local.paths значением НЕ служит — отказ
    # остаётся, но называет перенос готовой командой шага (иначе старый совет молча умер бы).
    (sirota / "local.paths").write_text(f"container={contour}\n", encoding="utf-8")
    out, code = run(sirota, [])
    case("④-бис встречный: прежний local.paths как значение НЕ читается, отказ даёт команду переноса",
         code != 0 and "больше не читается" in out and "20261005-local-paths-file.py" in out,
         f"код {code}")
    (sirota / "local.paths").unlink()

    # ④-тер ВСТРЕЧНЫЙ: файл путей есть, но ключа container в нём нет — отказ называет ЭТО словами
    paths_file.write_text(json.dumps({"mirror_repo": "x"}), encoding="utf-8")
    out, code = run(sirota, [])
    case("④-тер встречный: файл путей без ключа container — отказ, а не тихий ход",
         code != 0 and "корень мезосинка НЕ НАЙДЕН" in out,
         f"код {code}")
    paths_file.unlink()

    # ⑤ ВСТРЕЧНЫЙ к ②: переменная задана, но ведёт НЕ ТУДА — отказ НАЗЫВАЕТ это
    bad = box / "пусто"
    bad.mkdir()
    out, code = run(sirota, [], {"MEZO_CONTAINER": str(bad)})
    case("⑤ встречный: переменная задана, но базы по ней нет — отказ говорит ИМЕННО это",
         code != 0 and "задана, но" in out,
         "без этого случая ② зеленел бы и на неверном пути, молча вернувшись к поиску вверх")

    # ⑥ ВСТРЕЧНЫЙ к ③: относительный --db корня НЕ заменяет
    out, code = run(sirota, ["--db", "mezosync.db"])
    case("⑥ встречный: ОТНОСИТЕЛЬНЫЙ --db по-прежнему требует корня и отказывает",
         code != 0 and "корень мезосинка НЕ НАЙДЕН" in out,
         "иначе правка ③ превратила бы любой --db в обход поиска корня")

    # ⑦ НАСТОЯЩИЙ КОНТУР НЕ СЛОМАН — испытуемые файлы внутри собранного контура находят его сами
    out, code = run(contour / ".mezosync" / "scripts", [])
    case("⑦ внутри собранного контура механизм работает как прежде",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code}")

    # ⑧ КОНТРОЛЬ: приёмке было что запускать
    case("⑧ контроль: подопытный каталог собран",
         (sirota / "mezo_paths.py").exists() and (sirota / "lease.py").exists(),
         f"{sirota}")

    # ⑨ ⑩ ⑪ ПУСТОЙ ФАЙЛ БАЗЫ — НЕ ПРИЗНАК КОНТУРА (починка (б))
    mp_text = (SCRIPTS / "mezo_paths.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    real = phantom_cases(box / "пустышки", mp_text)
    case("⑨ пустой mezosync.db в предке — не корень мезосинка: отказ его называет, файл не тронут",
         real["⑨"][0], real["⑨"][1])
    case("⑩ пустой .mezosync/mezosync.db в предке — не каталог группы: отказ его называет",
         real["⑩"][0], real["⑩"][1])
    case("⑪ пустой mezosync.db в корне пакета не прячет пакет: template_root его находит",
         real["⑪"][0], real["⑪"][1])

    # ⑨-бис НАРОЧНАЯ ПОЛОМКА: прежний признак «файл есть» — все три случая обязаны НЕ пройти
    if mp_text.count(BREAK_ANCHOR) != 1:
        case("⑨-бис нарочная поломка «признак базы — файл есть» не даёт пройти ⑨ ⑩ ⑪",
             False, f"якорь поломки встречается {mp_text.count(BREAK_ANCHOR)} раз вместо 1 — поломка не легла")
    else:
        broken = phantom_cases(box / "пустышки-поломка", mp_text.replace(BREAK_ANCHOR, BREAK_TEXT))
        held_on_break = [k for k, (held, _) in broken.items() if held]
        case("⑨-бис нарочная поломка «признак базы — файл есть» не даёт пройти ⑨ ⑩ ⑪",
             not held_on_break,
             "на поломке прошли: " + (", ".join(held_on_break) if held_on_break else "ни один")
             + " · " + " · ".join(f"{k}: {v[1][:60]}" for k, v in broken.items()))

    mezo_stand.release(box)  # уборка отложена до исхода прогона
    print(f"\nИТОГ: {OK}/{OK + FAIL}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
