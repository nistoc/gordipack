# -*- coding: utf-8 -*-
"""bite-drift-no-mirror.py — приёмка: guard-scripts-drift.py без зеркала сверяет две другие пары копий
(issue #39 пакета, предложение «а»).

ЗАЧЕМ. При «зеркало не объявлено» и при «каталога зеркала нет» проверка выходила кодом 0 раньше,
чем сверяла пару «vnext-tools ↔ образец» и общие помощники двух рабочих каталогов. Контур без
зеркала видел «✅ drift», пока файл одного имени в .mezosync/scripts и vnext-tools расходился
(замер контура-потребителя: bite-phoenix-empty.py, 34918 и 10968 байт).

Стенд: контур во временном каталоге — .mezosync/scripts с копией испытуемого и его соседями,
vnext-tools с одним файлом helper_common.py того же имени, что и в .mezosync/scripts; образец
не объявлен. Живой базы не касается: подставная база без строк (mezo_stand.empty_db) только
как признак контура.

Случаи:
  ① зеркало не объявлено, общий помощник расходится — код 1, файл назван; строка «пара с
     зеркалом НЕ сверялась» (её общий прогон показывает под итогом проверки); строка, которую общий
     прогон возьмёт итогом провала, — сам вердикт «ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ», а не оговорка
  ② ВСТРЕЧНЫЙ: зеркало не объявлено, помощник совпадает — код 0, «общие помощники … совпадают»:
     сверка шла, а не пропущена
  ③ зеркало объявлено, каталога нет, помощник расходится — код 1, файл назван; «НЕ ЗАВЕДЁН — пара
     с зеркалом НЕ сверялась»; итогом общего прогона — тоже вердикт
  ④ ВСТРЕЧНЫЙ: зеркало объявлено, каталога нет, помощник совпадает — код 0, «совпадают»
  ⑤ КОНТРОЛЬ прежнего пути: зеркало есть и совпадает, помощник расходится — «СОВПАДАЕТ», код 1
  ⑥ файл путей не читается, помощник совпадает — код 1 («зеркало не определено»), и сверка
     помощников всё равно прошла

Нарочные поломки (--break), каждая на своей копии guard-scripts-drift.py:
  early-exit-undeclared .... ветка «не объявлено» выходит, не сверяя пар            → ① ② ⑥
  early-exit-missing ....... ветка «каталога нет» выходит кодом 0, не сверяя пар    → ③ ④
  unreadable-first ......... «не читается» проверено раньше сверки, и она не идёт   → ⑥
  no-words ................. строка «не объявлено» без слов «НЕ сверялась»          → ①
  disclaimer-as-verdict .... оговорка «И этот инструмент НЕ отвечает…» под ⛔        → ① ③

Испытуемый guard-scripts-drift.py — по MEZO_SCRIPTS_ROOT (mezo_target), по умолчанию — установленный.
Запуск:  python <каталог приёмок>/bite-drift-no-mirror.py [--break <имя>]
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("guard-scripts-drift.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
sys.path.insert(0, str(mezo_paths.live_scripts()))
# mezo_stand — из каталога самой приёмки, той же версии пакета; вставка снимается сразу.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
sys.path.pop(0)

UNDECLARED_EXIT = "        sys.exit(1 if (check_against_template() or unreadable) else 0)\n"
MISSING_EXIT = ("        # Две другие пары — как в ветке «не объявлено» выше (issue #39, «а»).\n"
                "        sys.exit(1 if check_against_template() else 0)\n")
WORDS = ("\"ℹ️ зеркало не объявлено — сверка копий пропущена (свойство контура); пара \"\n"
         "                  \"с зеркалом НЕ сверялась, две другие пары сверяются и без него\")\n")

DISCLAIMER = "        print(\"   ⚖️ И этот инструмент НЕ отвечает на вопрос «отстали ли мы от общего \"\n"
DISCLAIMER_BROKEN = DISCLAIMER.replace("⚖️", "⛔")
BREAKS = {
    "early-exit-undeclared": ([(UNDECLARED_EXIT, "        sys.exit(1 if unreadable else 0)\n")],
                              {"①", "②", "⑥"}),
    "early-exit-missing": ([(MISSING_EXIT, "        sys.exit(0)\n")], {"③", "④"}),
    "unreadable-first": ([(UNDECLARED_EXIT,
                           "        sys.exit(1 if (unreadable or check_against_template()) else 0)\n")],
                         {"⑥"}),
    "no-words": ([(WORDS, "\"ℹ️ зеркало не объявлено — сверка копий пропущена (свойство контура)\")\n")],
                 {"①"}),
    # оговорка о границе снова под знаком вердикта — в обеих ветках без зеркала
    "disclaimer-as-verdict": ([("«ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ».\n" + DISCLAIMER,
                                "«ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ».\n" + DISCLAIMER_BROKEN),
                               ("«не объявлено» выше.\n" + DISCLAIMER,
                                "«не объявлено» выше.\n" + DISCLAIMER_BROKEN)],
                              {"①", "③"}),
}

HELPER = "helper_common.py"
SAME = "VALUE = 1\n"
OTHER = "VALUE = 2\n"

OK = FAIL = 0
RED = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: проверка копий без зеркала сверяет две другие пары")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии guard-scripts-drift.py")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-drift-no-mirror-")
    live_db = mezo_paths.live_db()

    # испытуемый с соседями — один раз; каждый случай берёт копию этого набора
    tools = mezo_stand.copy_tool(TARGET, stand / "tool-set").parent
    if a.break_name:
        tool = tools / TARGET.name
        text = tool.read_bytes().decode("utf-8").replace("\r\n", "\n")
        for old, new in BREAKS[a.break_name][0]:
            if text.count(old) != 1:
                print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                      f"(образец найден {text.count(old)} раз): {old.strip()[:70]}")
                return mezo_stand.finish(2)
            text = text.replace(old, new)
        # байтами: запись текстом на Windows сменила бы окончания строк копии
        tool.write_bytes(text.encode("utf-8"))
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    def contour(tag, helper_vnext, paths=None, raw_paths=None, mirror=False):
        """Контур стенда: своя копия набора, помощник в обоих рабочих каталогах, файл путей."""
        c = stand / tag
        own = c / ".mezosync" / "scripts"
        shutil.copytree(tools, own)
        mezo_stand.empty_db(live_db, c / ".mezosync" / "mezosync.db")
        (own / HELPER).write_text(SAME, encoding="utf-8")
        (c / "vnext-tools").mkdir(parents=True)
        (c / "vnext-tools" / HELPER).write_text(helper_vnext, encoding="utf-8")
        if mirror:
            shutil.copytree(own, c / "mirror" / "scripts")
        if paths is not None or raw_paths is not None:
            local = c / ".mezosync" / "local"
            local.mkdir(parents=True)
            (local / "paths.json").write_text(
                raw_paths if raw_paths is not None else json.dumps(paths), encoding="utf-8")
        return c, own / TARGET.name

    def run(c, tool):
        r = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=mezo_stand.stand_env(c, PYTHONIOENCODING="utf-8"),
                           stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def summary(out):
        """Строка, которую общий прогон (guard-all.py, sub_guard) покажет итогом провала: «ИТОГО»,
        иначе ПЕРВАЯ строка со знаком вердикта 🔴 или ⛔ — то же правило, что у него."""
        lines = [l.rstrip() for l in out.strip().splitlines() if l.strip()]
        return (next((l for l in reversed(lines) if "ИТОГО" in l), None)
                or next((l for l in lines if "🔴" in l or "⛔" in l), ""))

    def tail(out):
        return " ⏎ ".join(l.strip() for l in out.strip().splitlines()[-4:])[:300]

    helpers_diverge = "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ"
    helpers_same = "общие помощники двух рабочих каталогов: 1 совпадают"
    not_checked = "пара с зеркалом НЕ сверялась"

    # ① ② — зеркало не объявлено
    c, tool = contour("c1", OTHER)
    rc, out = run(c, tool)
    case("①", "зеркало не объявлено, помощник расходится — код 1, файл назван, «НЕ сверялась»",
         rc == 1 and helpers_diverge in out and HELPER in out and not_checked in out
         and "зеркало не объявлено" in out and helpers_diverge in summary(out),
         f"код {rc} · итог общего прогона: {summary(out).strip()[:90]} · {tail(out)}")
    c, tool = contour("c2", SAME)
    rc, out = run(c, tool)
    case("②", "ВСТРЕЧНЫЙ: зеркало не объявлено, помощник совпадает — код 0, «совпадают»",
         rc == 0 and helpers_same in out and helpers_diverge not in out, f"код {rc} · {tail(out)}")

    # ③ ④ — зеркало объявлено, каталога нет
    # файл путей заводится пустым и сразу получает путь ВНУТРИ контура случая
    missing = {}
    c, tool = contour("c3", OTHER, paths=missing)
    (c / ".mezosync" / "local" / "paths.json").write_text(
        json.dumps({"mirror_repo": str(c / "no-such-mirror")}), encoding="utf-8")
    rc, out = run(c, tool)
    case("③", "каталога зеркала нет, помощник расходится — код 1, файл назван, «НЕ ЗАВЕДЁН — … НЕ сверялась»",
         rc == 1 and helpers_diverge in out and HELPER in out
         and "НЕ ЗАВЕДЁН — пара с зеркалом НЕ сверялась" in out and helpers_diverge in summary(out),
         f"код {rc} · итог общего прогона: {summary(out).strip()[:90]} · {tail(out)}")
    c, tool = contour("c4", SAME, paths=missing)
    (c / ".mezosync" / "local" / "paths.json").write_text(
        json.dumps({"mirror_repo": str(c / "no-such-mirror")}), encoding="utf-8")
    rc, out = run(c, tool)
    case("④", "ВСТРЕЧНЫЙ: каталога зеркала нет, помощник совпадает — код 0, «совпадают»",
         rc == 0 and helpers_same in out and "НЕ ЗАВЕДЁН" in out, f"код {rc} · {tail(out)}")

    # ⑤ — прежний путь: зеркало есть
    c, tool = contour("c5", OTHER, paths={}, mirror=True)
    (c / ".mezosync" / "local" / "paths.json").write_text(
        json.dumps({"mirror_repo": str(c / "mirror")}), encoding="utf-8")
    rc, out = run(c, tool)
    case("⑤", "КОНТРОЛЬ: зеркало есть и совпадает, помощник расходится — «СОВПАДАЕТ», код 1",
         rc == 1 and "СОВПАДАЕТ" in out and helpers_diverge in out, f"код {rc} · {tail(out)}")

    # ⑥ — файл путей не читается
    c, tool = contour("c6", SAME, raw_paths="[1, 2]")
    rc, out = run(c, tool)
    case("⑥", "файл путей не читается — код 1, «зеркало не определено», помощники всё равно сверены",
         rc == 1 and "зеркало не определено" in out and helpers_same in out, f"код {rc} · {tail(out)}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL} · испытан {mezo_target.label()}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'🧪' if exact else '⚠️'} поломка «{a.break_name}»: провалились "
              f"{' '.join(RED) or 'никто'} · ждали {' '.join(sorted(expected))} — "
              f"{'ожидание ПОДТВЕРДИЛОСЬ' if exact else 'ожидание НЕ ПОДТВЕРДИЛОСЬ'}")
        if exact:
            # поломка поймана, как записано, — стенд хранить незачем; код выхода прежний (1)
            mezo_stand.expected_break()
        return mezo_stand.finish(1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
