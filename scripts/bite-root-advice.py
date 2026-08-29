# -*- coding: utf-8 -*-
"""Приёмка: советы в отказе поиска корня ИСПОЛНЯЮТСЯ, а не только напечатаны.

Повод — заявка @PROTO (записка #3713 ②): отказ называл два выхода, и оба были мертвы.
Роль выполняла оба, получала тот же отказ слово в слово и решала, что сломан механизм.

🎯 ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, А ЧТО НЕТ. Проверяется ИСПОЛНИМОСТЬ совета: механизм, запущенный
из каталога без корня, после выполнения совета РАБОТАЕТ. Не проверяется формулировка —
текст можно переписать как угодно, лишь бы названное в нём срабатывало.
⛔ Случай ① («без советов — отказ») без встречных ②③ доказывал бы только то, что механизм
умеет падать. Именно так дефект и прожил: отказ был громким и выглядел исправным.
"""
import os
import pathlib
import shutil
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = pathlib.Path(__file__).resolve().parent
LIVE_DB = SCRIPTS.parent / "mezosync.db"
OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(f"{'✅' if cond else '⛔'} {name}")
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1


def run(cwd, args, env=None):
    e = dict(os.environ)
    e.pop("MEZO_CONTAINER", None)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable, "lease.py", "status", *args], cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=e, timeout=60)
    return (p.stdout or "") + (p.returncode and (p.stderr or "") or ""), p.returncode


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

    # ② СОВЕТ ПЕРВЫЙ: переменная среды — ИСПОЛНЯЕТСЯ
    out, code = run(sirota, [], {"MEZO_CONTAINER": str(SCRIPTS.parent.parent)})
    case("② совет «MEZO_CONTAINER=<контейнер>» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code} · {out.splitlines()[0][:78] if out else 'пусто'}")

    # ③ СОВЕТ ВТОРОЙ: абсолютный путь к базе — ИСПОЛНЯЕТСЯ
    out, code = run(sirota, ["--db", str(LIVE_DB)])
    case("③ совет «абсолютный --db» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code} · {out.splitlines()[0][:78] if out else 'пусто'}")

    # ④ СОВЕТ ТРЕТИЙ: файл рядом с механизмом — ИСПОЛНЯЕТСЯ
    (sirota / "local.paths").write_text(f"container={SCRIPTS.parent.parent}\n", encoding="utf-8")
    out, code = run(sirota, [])
    case("④ совет «строка container= в local.paths» РАБОТАЕТ",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code}")
    (sirota / "local.paths").unlink()

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

    # ⑦ ЖИВОЙ КОНТУР НЕ СЛОМАН — правка не должна была ничего изменить там, где всё нашлось
    out, code = run(SCRIPTS, [])
    case("⑦ в живом контуре механизм работает как прежде",
         code == 0 and "ОБЪЯВЛЕНИЯ О ПРАВКЕ" in out,
         f"код {code}")

    # ⑧ КОНТРОЛЬ: приёмке было что запускать
    case("⑧ контроль: подопытный каталог собран",
         (sirota / "mezo_paths.py").exists() and (sirota / "lease.py").exists(),
         f"{sirota}")

    mezo_stand.release(box)  # уборка отложена до исхода прогона
    print(f"\nИТОГ: {OK}/{OK + FAIL}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
